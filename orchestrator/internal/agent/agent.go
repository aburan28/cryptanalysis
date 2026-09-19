package agent

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"math/rand"
	"os"
	"runtime"
	"sync"
	"time"

	"github.com/aburan28/cryptanalysis/orchestrator/api"
)

// Config is what an agent needs.  Everything except the server URL has a
// working default, because an agent is deployed by copying a unit file or a
// pod spec and every required setting is one more thing to get wrong.
type Config struct {
	Server   string
	Token    string
	Campaign string // empty: take work from any campaign
	Labels   map[string]string
	ID       string // empty: hostname plus a random suffix

	// IdleBackoff is how long to wait when the control plane has no work.
	IdleBackoff time.Duration
	// MaxUnits stops the agent after this many units (0: forever).  Used by
	// tests and by batch-style runs on preemptible capacity.
	MaxUnits int

	Logger *slog.Logger
	Now    func() time.Time
}

func (c *Config) defaults() {
	if c.IdleBackoff <= 0 {
		c.IdleBackoff = 15 * time.Second
	}
	if c.Logger == nil {
		c.Logger = slog.Default()
	}
	if c.Now == nil {
		c.Now = time.Now
	}
	if c.ID == "" {
		host, _ := os.Hostname()
		if host == "" {
			host = "agent"
		}
		c.ID = host + "-" + randomSuffix()
	}
}

// Agent is one worker process.
type Agent struct {
	cfg      Config
	client   *api.Client
	walker   Walker
	interval time.Duration

	mu      sync.Mutex
	units   int
	points  uint64
	steps   uint64
	lastErr error
}

func New(cfg Config, client *api.Client, walker Walker) *Agent {
	cfg.defaults()
	return &Agent{cfg: cfg, client: client, walker: walker, interval: 30 * time.Second}
}

func (a *Agent) ID() string { return a.cfg.ID }

// Run works until the context is cancelled or MaxUnits is reached.
//
// The shape of the loop is dictated by one fact: a unit in flight is
// disposable.  Anything that goes wrong -- the server restarting, the lease
// being taken, the process being told to stop -- ends with the points so far
// uploaded if possible and the unit handed back, never with the agent
// trying to hold on to work it can no longer prove it owns.
func (a *Agent) Run(ctx context.Context) error {
	info := api.AgentInfo{
		ID: a.cfg.ID, Version: api.Version, Platform: runtime.GOOS + "/" + runtime.GOARCH,
		CPUs: runtime.NumCPU(), Labels: a.cfg.Labels,
	}
	info.Hostname, _ = os.Hostname()

	reg, err := a.client.Register(ctx, info)
	if err != nil {
		return err
	}
	if reg.Interval > 0 {
		a.interval = reg.Interval
	}
	a.cfg.Logger.Info("registered", "agent", a.cfg.ID, "server", a.cfg.Server,
		"walker", a.walker.Describe(), "heartbeat", a.interval)

	for {
		if ctx.Err() != nil {
			return nil
		}
		a.mu.Lock()
		done := a.cfg.MaxUnits > 0 && a.units >= a.cfg.MaxUnits
		a.mu.Unlock()
		if done {
			a.cfg.Logger.Info("unit budget reached", "units", a.cfg.MaxUnits)
			return nil
		}

		resp, err := a.client.Lease(ctx, api.LeaseRequest{AgentID: a.cfg.ID,
			Campaign: a.cfg.Campaign})
		if err != nil {
			if ctx.Err() != nil {
				return nil
			}
			a.setErr(err)
			a.cfg.Logger.Error("lease failed", "error", err)
			if !sleepCtx(ctx, a.cfg.IdleBackoff) {
				return nil
			}
			continue
		}
		if resp.Lease == nil {
			// No work is normal: the campaign may be solved or fully in
			// flight.  The server tells the agent how long to wait so that
			// the backoff is a fleet-wide decision, not a local guess.
			wait := resp.Retry
			if wait <= 0 {
				wait = a.cfg.IdleBackoff
			}
			a.cfg.Logger.Debug("no work", "retryIn", wait)
			if !sleepCtx(ctx, wait) {
				return nil
			}
			continue
		}
		if err := a.runUnit(ctx, resp.Lease); err != nil && ctx.Err() == nil {
			a.setErr(err)
			a.cfg.Logger.Error("unit failed", "unit", resp.Lease.Unit.ID, "error", err)
			if !sleepCtx(ctx, time.Second) {
				return nil
			}
		}
	}
}

// runUnit walks one lease and reports it.
func (a *Agent) runUnit(ctx context.Context, lease *api.Lease) error {
	// A lease arrives over the network, and an agent acts on it in two ways
	// that deserve a check first: it puts the campaign's parameters on a
	// subprocess command line, and it puts the campaign's name in every log
	// line about this unit.  The server validated all of it on the way in,
	// but "the server said so" is a thin argument when CA_SERVER is a flag,
	// DNS is a thing, and the only authentication is a shared token.  The
	// same rule the server applied is cheap to apply again here.
	if err := lease.Campaign.Validate(); err != nil {
		a.cfg.Logger.Error("refusing a malformed lease", "unit", lease.Unit.ID, "error", err)
		return fmt.Errorf("malformed lease: %w", err)
	}
	log := a.cfg.Logger.With("campaign", api.CleanText(lease.Campaign.Name),
		"unit", lease.Unit.ID, "fence", lease.Fence)
	log.Info("unit started", "steps", lease.Unit.MaxSteps)

	// The walk runs under a context the heartbeat can cancel: if the lease
	// is lost, every further step is work whose output will be refused, and
	// continuing to spend a GPU or a core on it is the one thing worse than
	// stopping.
	walkCtx, cancel := context.WithCancel(ctx)
	defer cancel()

	var (
		hbWG   sync.WaitGroup
		lostMu sync.Mutex
		lost   bool
	)
	hbWG.Add(1)
	go func() {
		defer hbWG.Done()
		t := time.NewTicker(a.interval)
		defer t.Stop()
		unit := lease.Unit.ID
		for {
			select {
			case <-walkCtx.Done():
				return
			case <-t.C:
				hb, err := a.client.Heartbeat(walkCtx, api.HeartbeatRequest{
					AgentID: a.cfg.ID, Unit: &unit, Fence: lease.Fence,
				})
				if err != nil {
					// A heartbeat that cannot be delivered is not by itself
					// a lost lease: the network may be briefly gone and the
					// lease may well outlive it.  Keep walking and try
					// again; the server will expire the unit if it must.
					log.Warn("heartbeat failed", "error", err)
					continue
				}
				if hb.Lost {
					lostMu.Lock()
					lost = true
					lostMu.Unlock()
					log.Warn("lease lost; stopping the walk")
					cancel()
					return
				}
				if hb.Drain {
					log.Info("server is draining; will stop after this unit")
				}
			}
		}
	}()

	result, walkErr := a.walker.Walk(walkCtx, lease)
	cancel()
	hbWG.Wait()

	lostMu.Lock()
	wasLost := lost
	lostMu.Unlock()

	// Upload whatever was produced, even on a cancelled walk: those points
	// cost real steps, they are valid, and the corpus is the only thing in
	// this system that cannot be recreated cheaply.  The one case where the
	// upload is skipped is a lost lease, where the server would refuse it.
	var uploaded api.PointsResponse
	if len(result.Bytes) > 0 && !wasLost {
		up, err := a.client.SendPoints(context.WithoutCancel(ctx), lease.Campaign.Name, a.cfg.ID,
			lease.Campaign.Fingerprint, lease.Unit.ID, lease.Fence, result.Bytes)
		switch {
		case errors.Is(err, api.ErrLeaseLost):
			wasLost = true
			log.Warn("points refused: the lease had moved on")
		case errors.Is(err, api.ErrFingerprint):
			// The agent is walking a different function from the server's
			// campaign.  Nothing it produces can ever be useful, so this is
			// fatal rather than a retry.
			return err
		case err != nil:
			log.Error("upload failed", "error", err, "points", result.Points)
		default:
			uploaded = up
			log.Info("points uploaded", "points", result.Points, "accepted", up.Accepted,
				"duplicates", up.Duplicates, "rejected", up.Rejected, "stored", up.Stored)
			if up.Rejected > 0 {
				// The server verified and refused: either this agent is
				// broken or it is walking the wrong function.  Either way an
				// operator needs to see it.
				log.Error("the server rejected points from this agent", "rejected", up.Rejected)
			}
			if up.Solved {
				log.Info("campaign solved", "x", up.X)
			}
		}
	}

	a.mu.Lock()
	a.units++
	a.points += uploaded.Accepted
	a.steps += result.Steps
	a.mu.Unlock()

	if wasLost {
		return nil // somebody else owns the unit; nothing more to report
	}

	failed := walkErr != nil
	reason := ""
	if failed {
		reason = walkErr.Error()
		if errors.Is(walkErr, context.Canceled) {
			// A shutdown, not a broken unit: hand it back so the remaining
			// budget is walked by somebody, and let the points already
			// uploaded stand.
			reason = "agent stopped"
		}
	}
	err := a.client.Complete(context.WithoutCancel(ctx), lease.Campaign.Name, lease.Unit.ID,
		api.CompleteRequest{
			AgentID: a.cfg.ID, Fence: lease.Fence, Steps: result.Steps,
			Points: result.Points, Failed: failed, Reason: reason,
		})
	if err != nil && !errors.Is(err, api.ErrLeaseLost) {
		return err
	}
	log.Info("unit finished", "points", result.Points, "steps", result.Steps,
		"seconds", result.Duration.Seconds(), "failed", failed)
	if failed && !errors.Is(walkErr, context.Canceled) {
		return walkErr
	}
	return nil
}

// Stats is what the agent's own status endpoint reports.
type Stats struct {
	ID     string `json:"id"`
	Units  int    `json:"units"`
	Points uint64 `json:"points"`
	Steps  uint64 `json:"steps"`
	Error  string `json:"lastError,omitempty"`
}

func (a *Agent) Stats() Stats {
	a.mu.Lock()
	defer a.mu.Unlock()
	s := Stats{ID: a.cfg.ID, Units: a.units, Points: a.points, Steps: a.steps}
	if a.lastErr != nil {
		s.Error = a.lastErr.Error()
	}
	return s
}

func (a *Agent) setErr(err error) {
	a.mu.Lock()
	a.lastErr = err
	a.mu.Unlock()
}

func sleepCtx(ctx context.Context, d time.Duration) bool {
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return false
	case <-t.C:
		return true
	}
}

func randomSuffix() string {
	const alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
	r := rand.New(rand.NewSource(time.Now().UnixNano() ^ int64(os.Getpid())))
	b := make([]byte, 6)
	for i := range b {
		b[i] = alphabet[r.Intn(len(alphabet))]
	}
	return string(b)
}
