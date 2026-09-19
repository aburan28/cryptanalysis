// Package control is the control plane: it owns the campaigns, hands out
// work units, holds the corpus and solves it.
//
// The scheduling model is deliberately small, because the work being
// scheduled is unusually forgiving:
//
//   - A unit is a budget of walk steps, identified by an id that also seeds
//     its starting points.  Handing the same unit to two agents wastes one
//     agent's time and corrupts nothing, because a unit is replayable.
//   - Losing a unit entirely costs nothing but the steps: the search is a
//     random walk, not a partition of a space, so there is no "gap" a lost
//     unit leaves behind.  That is why an expired lease is re-queued rather
//     than chased, and why an agent that dies mid-unit is not an incident.
//   - Every write an agent makes carries a fence.  Leases expire, and an
//     agent that was paused past its expiry will wake up and try to report;
//     the fence is what stops it writing into a unit somebody else now
//     holds.  A lease length cannot do that, however long it is.
//
// What the control plane will not do: trust an agent.  Points are verified
// against the campaign before they enter the corpus, and the discrete
// logarithm is verified against the target before it is reported.
package control

import (
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/aburan28/cryptanalysis/orchestrator/api"
	"github.com/aburan28/cryptanalysis/orchestrator/internal/dlog"
	"github.com/aburan28/cryptanalysis/orchestrator/internal/store"
)

// MaxAttempts is how often a unit is re-issued after its lease expires or
// an agent reports it failed.  A unit that fails this often is failing for
// a reason that is not about the unit -- a bad binary, a broken host -- and
// re-issuing it forever would pin the fleet to that reason.
const MaxAttempts = 3

var (
	// ErrFence is returned when an agent writes under a lease the unit has
	// moved past.  It is not retryable: the agent must get a new lease.
	ErrFence = errors.New("stale fence: the unit has been re-leased")
	// ErrFingerprint means the agent computed points under a different walk
	// function.  Its points would never collide with the corpus, so they are
	// refused loudly rather than stored.
	ErrFingerprint = errors.New("campaign fingerprint mismatch")
	ErrNoSuchUnit  = errors.New("unknown unit")
	ErrSolved      = errors.New("campaign is already solved")
)

// campaign is one running search.
type campaign struct {
	def    api.Campaign
	group  *dlog.Group
	base   dlog.Point
	target dlog.Point
	merger *dlog.Merger
	st     *store.Store

	mu sync.Mutex
	// inFlight holds only leased units.  Finished units are counters and a
	// line in the ledger: a campaign runs for millions of units and a map of
	// all of them would be the control plane's largest allocation for no
	// benefit.
	inFlight map[uint64]*api.Unit
	retry    []uint64 // units whose lease expired or that failed, to re-issue
	next     uint64   // the lowest unit id never issued
	fence    uint64   // monotonic; every lease gets a fresh one

	doneCount, abandonedCount int
	steps, points             uint64
	solvedAt                  *time.Time
}

func newCampaign(def api.Campaign, st *store.Store) (*campaign, error) {
	if err := def.Validate(); err != nil {
		return nil, err
	}
	kind := dlog.Zp
	if def.Group.Kind == api.GroupEC {
		kind = dlog.EC
	}
	g, err := dlog.NewGroup(kind, def.Group.P, def.Group.A, def.Group.B, def.Group.Order)
	if err != nil {
		return nil, err
	}
	base, err := g.ParsePoint(def.Group.Base)
	if err != nil {
		return nil, fmt.Errorf("base: %w", err)
	}
	target, err := g.ParsePoint(def.Group.Target)
	if err != nil {
		return nil, fmt.Errorf("target: %w", err)
	}
	m, err := dlog.NewMerger(g, base, target, def.DPBits, true)
	if err != nil {
		return nil, err
	}
	return &campaign{
		def: def, group: g, base: base, target: target, merger: m, st: st,
		inFlight: map[uint64]*api.Unit{},
	}, nil
}

// restoreUnit replays one ledger line at boot.  Only two things matter: that
// a finished unit is not issued again, and that the next id is past every id
// that has ever been issued.
func (c *campaign) restoreUnit(r store.UnitRecord) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if r.Unit >= c.next {
		c.next = r.Unit + 1
	}
	if r.Fence > c.fence {
		c.fence = r.Fence
	}
	switch api.UnitState(r.State) {
	case api.UnitDone:
		c.doneCount++
		c.steps += r.Steps
		c.points += r.Points
	case api.UnitAbandoned:
		c.abandonedCount++
	}
}

// restoreCorpus re-ingests the stored blobs.  The corpus is the campaign's
// only irreplaceable state, so a control plane that came back without it
// would silently restart a search that is half done.
//
// Verification is left on: the points are re-checked on the way back in.  It
// costs a couple of scalar multiplications per point at boot, and it means a
// corrupted blob on disk is found at startup rather than by never colliding.
func (c *campaign) restoreCorpus() (uint64, error) {
	keys, err := c.st.CorpusKeys(c.def.Name)
	if err != nil {
		return 0, err
	}
	var total uint64
	for _, key := range keys {
		blob, err := c.st.GetCorpus(key)
		if err != nil {
			return total, fmt.Errorf("reading %s: %w", key, err)
		}
		counts, err := c.merger.AddBytes(blob)
		if err != nil {
			// A trailing partial record: the blob was written by an older
			// version or truncated on disk.  Take what parsed and say so.
			return total, fmt.Errorf("blob %s: %w", key, err)
		}
		total += counts.Accepted
	}
	if _, solved := c.merger.Solved(); solved && c.solvedAt == nil {
		now := time.Now().UTC()
		c.solvedAt = &now
	}
	return total, nil
}

// lease hands out a unit, preferring one that needs re-walking.
//
// Returns nil when there is nothing to do, which is a normal state: the
// campaign is solved, or every unit is in flight and the fleet is larger
// than the campaign's concurrency.
func (c *campaign) lease(agent string, ttl time.Duration, now time.Time) *api.Lease {
	c.mu.Lock()
	defer c.mu.Unlock()
	if _, solved := c.merger.Solved(); solved {
		return nil
	}
	var id uint64
	if n := len(c.retry); n > 0 {
		id = c.retry[n-1]
		c.retry = c.retry[:n-1]
	} else {
		id = c.next
		c.next++
	}
	c.fence++
	u, ok := c.inFlight[id]
	if !ok {
		u = &api.Unit{Campaign: c.def.Name, ID: id, MaxSteps: c.def.UnitSteps, Walks: c.def.UnitWalks}
		c.inFlight[id] = u
	}
	u.State = api.UnitLeased
	u.Owner = agent
	u.Fence = c.fence
	u.Attempts++
	u.LeaseTill = now.Add(ttl)
	u.UpdatedAt = now
	unit := *u
	return &api.Lease{Campaign: c.def, Unit: unit, Fence: unit.Fence, Expires: unit.LeaseTill}
}

// renew extends a lease.  False means the agent no longer owns the unit and
// must stop walking it: its points would be refused anyway.
func (c *campaign) renew(id uint64, agent string, fence uint64, ttl time.Duration,
	now time.Time) (time.Time, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	u, ok := c.inFlight[id]
	if !ok || u.Owner != agent || u.Fence != fence {
		return time.Time{}, false
	}
	u.LeaseTill = now.Add(ttl)
	u.UpdatedAt = now
	return u.LeaseTill, true
}

// checkOwner is the gate on every write: the unit must exist, the agent must
// own it, and its fence must be the current one.
func (c *campaign) checkOwner(id uint64, agent string, fence uint64) error {
	u, ok := c.inFlight[id]
	if !ok {
		return ErrNoSuchUnit
	}
	if u.Owner != agent || u.Fence != fence {
		return ErrFence
	}
	return nil
}

// addPoints stores a unit's points and merges them.
//
// The blob is written before the merge and the merge before the reply, in
// that order and for that reason: a point that is acknowledged but not
// durable is a point the fleet will not walk again and the server cannot
// produce.
func (c *campaign) addPoints(id uint64, agent string, fence uint64, fingerprint string,
	data []byte) (api.PointsResponse, error) {
	if fingerprint != "" && fingerprint != c.def.Fingerprint {
		return api.PointsResponse{}, ErrFingerprint
	}
	c.mu.Lock()
	if err := c.checkOwner(id, agent, fence); err != nil {
		c.mu.Unlock()
		return api.PointsResponse{}, err
	}
	c.mu.Unlock()

	if len(data) == 0 {
		return api.PointsResponse{}, nil
	}
	if _, err := c.st.PutCorpus(c.def.Name, id, data); err != nil {
		return api.PointsResponse{}, fmt.Errorf("storing points: %w", err)
	}
	counts, err := c.merger.AddBytes(data)
	if err != nil {
		// A trailing partial record is the shape of a killed agent's upload.
		// The whole records in it are already merged and stored; the
		// remainder is reported so the agent can resend.
		return api.PointsResponse{}, fmt.Errorf("%w", err)
	}
	x, solved := c.merger.Solved()
	if solved {
		c.mu.Lock()
		if c.solvedAt == nil {
			now := time.Now().UTC()
			c.solvedAt = &now
		}
		c.mu.Unlock()
	}
	stats := c.merger.Stats()
	return api.PointsResponse{
		Accepted: counts.Accepted, Duplicates: counts.Duplicates, Rejected: counts.Rejected,
		Stored: stats.Stored, Solved: solved, X: x,
	}, nil
}

// complete finishes a unit, successfully or not.
func (c *campaign) complete(id uint64, agent string, fence uint64, steps, points uint64,
	failed bool, reason string) error {
	c.mu.Lock()
	if err := c.checkOwner(id, agent, fence); err != nil {
		c.mu.Unlock()
		return err
	}
	u := c.inFlight[id]
	u.Steps += steps
	u.Points += points
	state := api.UnitDone
	if failed {
		if u.Attempts >= MaxAttempts {
			state = api.UnitAbandoned
			c.abandonedCount++
		} else {
			// Back to the queue under a new fence when it is next leased.
			state = api.UnitPending
			u.State = state
			u.Owner = ""
			c.retry = append(c.retry, id)
			c.mu.Unlock()
			return nil
		}
	} else {
		c.doneCount++
		c.steps += steps
		c.points += points
	}
	rec := store.UnitRecord{
		Campaign: c.def.Name, Unit: id, State: string(state), Steps: u.Steps, Points: u.Points,
		Attempts: u.Attempts, Fence: fence, At: time.Now().Unix(),
	}
	delete(c.inFlight, id)
	c.mu.Unlock()
	return c.st.AppendUnit(rec)
}

// expire re-queues units whose lease ran out.  The agent holding one may
// still be alive and walking; that is fine, and its points are still
// welcome right up until somebody else takes the unit, at which point its
// fence goes stale and it is told to stop.
func (c *campaign) expire(now time.Time) int {
	c.mu.Lock()
	defer c.mu.Unlock()
	n := 0
	for id, u := range c.inFlight {
		if u.State != api.UnitLeased || now.Before(u.LeaseTill) {
			continue
		}
		if u.Attempts >= MaxAttempts {
			u.State = api.UnitAbandoned
			c.abandonedCount++
			delete(c.inFlight, id)
			_ = c.st.AppendUnit(store.UnitRecord{
				Campaign: c.def.Name, Unit: id, State: string(api.UnitAbandoned),
				Steps: u.Steps, Points: u.Points, Attempts: u.Attempts, Fence: u.Fence,
				At: now.Unix(),
			})
			n++
			continue
		}
		u.State = api.UnitPending
		u.Owner = ""
		u.UpdatedAt = now
		c.retry = append(c.retry, id)
		n++
	}
	return n
}

func (c *campaign) status() api.CampaignStatus {
	c.mu.Lock()
	leased, pending := 0, len(c.retry)
	for _, u := range c.inFlight {
		if u.State == api.UnitLeased {
			leased++
		}
	}
	out := api.CampaignStatus{
		Campaign: c.def,
		Units: api.UnitCounts{
			Pending: pending, Leased: leased, Done: c.doneCount,
			Abandoned: c.abandonedCount, Next: c.next,
		},
		Steps:    c.steps,
		SolvedAt: c.solvedAt,
	}
	c.mu.Unlock()

	stats := c.merger.Stats()
	out.Points = stats.Accepted
	out.Duplicates = stats.Duplicates
	out.Rejected = stats.Rejected
	out.Stored = stats.Stored
	out.Solved = stats.Solved
	out.X = stats.X
	out.ExpectedPoints = dlog.ExpectedPoints(c.def.Group.Order, c.def.DPBits)
	out.ExpectedSteps = dlog.ExpectedSteps(c.def.Group.Order)
	return out
}
