package control

import (
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"math"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/aburan28/cryptanalysis/orchestrator/api"
	"github.com/aburan28/cryptanalysis/orchestrator/internal/dlog"
	"github.com/aburan28/cryptanalysis/orchestrator/internal/store"
)

// Config is what an operator sets.  Everything has a default that is safe on
// a laptop and sane in a cluster; the only setting with no default is the
// token, because a control plane that invents its own shared secret is one
// nobody can authenticate to.
type Config struct {
	LeaseTTL          time.Duration // how long a unit lease lives
	HeartbeatInterval time.Duration // what agents are told to use
	MaxUploadBytes    int64         // per points upload
	Token             string        // bearer token; empty disables auth
	Now               func() time.Time
	Logger            *slog.Logger
}

func (c *Config) defaults() {
	if c.LeaseTTL <= 0 {
		// Three heartbeats: an agent that misses one to a slow upload keeps
		// its unit, and a dead one frees it inside a minute.
		c.LeaseTTL = 90 * time.Second
	}
	if c.HeartbeatInterval <= 0 {
		c.HeartbeatInterval = 30 * time.Second
	}
	if c.MaxUploadBytes <= 0 {
		// 64 MiB is two million points, far more than a unit produces; the
		// limit exists so that a broken agent cannot make the server
		// allocate without bound.
		c.MaxUploadBytes = 64 << 20
	}
	if c.Now == nil {
		c.Now = func() time.Time { return time.Now().UTC() }
	}
	if c.Logger == nil {
		c.Logger = slog.Default()
	}
}

// Server is the control plane.
type Server struct {
	cfg   Config
	st    *store.Store
	start time.Time

	mu        sync.RWMutex
	campaigns map[string]*campaign
	agents    map[string]*api.Agent
	draining  bool

	metrics metrics
}

type metrics struct {
	leases, points, uploads, rejects, fenceRejects, expiries atomicCounter
}

// NewServer builds a control plane over a state directory and restores
// whatever is in it.
func NewServer(st *store.Store, cfg Config) (*Server, error) {
	cfg.defaults()
	s := &Server{cfg: cfg, st: st, start: cfg.Now(),
		campaigns: map[string]*campaign{}, agents: map[string]*api.Agent{}}
	if err := s.restore(); err != nil {
		return nil, err
	}
	return s, nil
}

// restore reloads campaigns, their unit ledgers and their corpora.
//
// Restoring the corpus is the part that matters: without it a restarted
// control plane would look like a fresh campaign and quietly redo a search
// that was half finished.  It is also the slowest part of a boot, because
// every point is re-verified on the way in, so it is logged with counts.
func (s *Server) restore() error {
	err := s.st.LoadCampaigns(func(name string, raw []byte) error {
		var def api.Campaign
		if err := json.Unmarshal(raw, &def); err != nil {
			return err
		}
		c, err := newCampaign(def, s.st)
		if err != nil {
			return err
		}
		s.campaigns[name] = c
		return nil
	})
	if err != nil {
		return fmt.Errorf("loading campaigns: %w", err)
	}
	units, err := s.st.ReplayUnits(func(r store.UnitRecord) {
		if c, ok := s.campaigns[r.Campaign]; ok {
			c.restoreUnit(r)
		}
	})
	if err != nil {
		return fmt.Errorf("replaying the unit ledger: %w", err)
	}
	for name, c := range s.campaigns {
		points, err := c.restoreCorpus()
		if err != nil {
			// A bad blob must not stop the control plane from starting: the
			// rest of the corpus is still worth having, and the fleet is
			// waiting.  Say so loudly instead.
			s.cfg.Logger.Error("restoring corpus", "campaign", name, "error", err,
				"restored", points)
		}
		st := c.status()
		s.cfg.Logger.Info("campaign restored", "campaign", name, "points", st.Points,
			"stored", st.Stored, "units", units, "solved", st.Solved)
	}
	return nil
}

// Fingerprint is the campaign identity every agent echoes: a hash over
// everything that defines the walk function.  Two campaigns with different
// fingerprints produce points that can never collide with each other.
func Fingerprint(c api.Campaign) string {
	h := sha256.New()
	fmt.Fprintf(h, "v1\n%s\n%d\n%d\n%d\n%d\n%s\n%s\n%d\n%d\n%d\n",
		c.Group.Kind, c.Group.P, c.Group.A, c.Group.B, c.Group.Order,
		c.Group.Base, c.Group.Target, c.Seed, c.R, c.DPBits)
	return hex.EncodeToString(h.Sum(nil)[:16])
}

// ResolveCampaign fills in the fields an operator did not set and computes
// the fingerprint.  It is the only place a campaign is allowed to acquire a
// seed or a cutoff: an agent that resolved its own would walk a function
// nobody else walks, and nothing would ever collide.
func ResolveCampaign(c api.Campaign, now time.Time, randSeed func() uint64) (api.Campaign, error) {
	if err := c.Group.Validate(); err != nil {
		return c, err
	}
	if c.Seed == 0 {
		c.Seed = randSeed()
		if c.Seed == 0 {
			c.Seed = 1
		}
	}
	if c.R == 0 {
		c.R = 32
	}
	if c.DPBits == 0 {
		// Aim for a corpus of about a million points for a full search, the
		// same target the C library resolves to.  Below that the per-point
		// overheads (a round trip, a row) start to matter next to the
		// 2^dpBits steps that produce one.
		expected := dlog.ExpectedSteps(c.Group.Order)
		perPoint := expected / 1048576.0
		if perPoint >= 2 {
			c.DPBits = int32(math.Floor(math.Log2(perPoint)))
		}
		if c.DPBits > 48 {
			c.DPBits = 48
		}
	}
	if c.UnitSteps == 0 {
		// A unit should be minutes of work, not hours: long units make a
		// spot interruption expensive and make progress invisible.  1/1000
		// of the expected search, floored so that tiny instances still have
		// units bigger than their startup cost.
		steps := uint64(dlog.ExpectedSteps(c.Group.Order) / 1000)
		if steps < 1<<16 {
			steps = 1 << 16
		}
		c.UnitSteps = steps
	}
	if c.CreatedAt.IsZero() {
		c.CreatedAt = now
	}
	c.Fingerprint = Fingerprint(c)
	return c, c.Validate()
}

// CreateCampaign resolves, persists and starts a campaign.
func (s *Server) CreateCampaign(def api.Campaign) (api.Campaign, error) {
	def, err := ResolveCampaign(def, s.cfg.Now(), randomSeed)
	if err != nil {
		return def, err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, exists := s.campaigns[def.Name]; exists {
		return def, fmt.Errorf("campaign %q already exists", def.Name)
	}
	c, err := newCampaign(def, s.st)
	if err != nil {
		return def, err
	}
	if err := s.st.SaveCampaign(def.Name, def); err != nil {
		return def, err
	}
	s.campaigns[def.Name] = c
	s.cfg.Logger.Info("campaign created", "campaign", def.Name, "fingerprint", def.Fingerprint,
		"dpBits", def.DPBits, "unitSteps", def.UnitSteps,
		"expectedPoints", dlog.ExpectedPoints(def.Group.Order, def.DPBits))
	return def, nil
}

// Drain stops handing out new leases.  Units in flight are left alone: they
// finish, or their leases expire and they go back to the queue when the
// server is not draining any more.
func (s *Server) Drain(on bool) {
	s.mu.Lock()
	s.draining = on
	s.mu.Unlock()
	s.cfg.Logger.Info("drain", "draining", on)
}

// Expire is the lease sweeper; Run calls it on a ticker.
func (s *Server) Expire() int {
	now := s.cfg.Now()
	s.mu.RLock()
	list := make([]*campaign, 0, len(s.campaigns))
	for _, c := range s.campaigns {
		list = append(list, c)
	}
	s.mu.RUnlock()
	n := 0
	for _, c := range list {
		n += c.expire(now)
	}
	if n > 0 {
		s.metrics.expiries.add(uint64(n))
		s.cfg.Logger.Info("leases expired", "units", n)
	}
	// Agents that have stopped beating are dropped from the registry: it is
	// a view of the live fleet, and a list of pods that no longer exist is
	// worse than an empty one.
	cutoff := now.Add(-4 * s.cfg.HeartbeatInterval)
	s.mu.Lock()
	for id, a := range s.agents {
		if a.LastSeen.Before(cutoff) {
			delete(s.agents, id)
		}
	}
	s.mu.Unlock()
	return n
}

// Run sweeps until the context is done.
func (s *Server) Run(stop <-chan struct{}) {
	t := time.NewTicker(time.Second)
	defer t.Stop()
	for {
		select {
		case <-stop:
			return
		case <-t.C:
			s.Expire()
		}
	}
}

// ---- HTTP -----------------------------------------------------------------

// Handler is the whole API.  Routes are explicit rather than pattern-matched
// so that an unknown path is a 404 and not an accident.
func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", s.handleHealth)
	mux.HandleFunc("/readyz", s.handleReady)
	mux.HandleFunc("/metrics", s.auth(s.handleMetrics))
	mux.HandleFunc("/v1/status", s.auth(s.handleStatus))
	mux.HandleFunc("/v1/campaigns", s.auth(s.handleCampaigns))
	mux.HandleFunc("/v1/campaigns/", s.auth(s.handleCampaign))
	mux.HandleFunc("/v1/agents/register", s.auth(s.handleRegister))
	mux.HandleFunc("/v1/agents/heartbeat", s.auth(s.handleHeartbeat))
	mux.HandleFunc("/v1/units/lease", s.auth(s.handleLease))
	mux.HandleFunc("/v1/units/points", s.auth(s.handlePoints))
	mux.HandleFunc("/v1/units/complete", s.auth(s.handleComplete))
	return logging(s.cfg.Logger, mux)
}

// auth is a constant-time bearer check.  An empty token disables it, which
// is for a laptop and for tests; the deployment manifests always set one.
func (s *Server) auth(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if s.cfg.Token != "" {
			got := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
			if subtle.ConstantTimeCompare([]byte(got), []byte(s.cfg.Token)) != 1 {
				writeErr(w, http.StatusUnauthorized, "unauthorized", "")
				return
			}
		}
		next(w, r)
	}
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

// readyz reports not-ready while draining, so that a rolling update takes
// the pod out of the load balancer before it stops handing out leases.
func (s *Server) handleReady(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	draining := s.draining
	s.mu.RUnlock()
	if draining {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"status": "draining"})
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "ready"})
}

func (s *Server) handleCampaigns(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		st := s.Status(false)
		writeJSON(w, http.StatusOK, st.Campaigns)
	case http.MethodPost:
		var def api.Campaign
		if !readJSON(w, r, &def, 1<<20) {
			return
		}
		out, err := s.CreateCampaign(def)
		if err != nil {
			writeErr(w, http.StatusBadRequest, "cannot create campaign", err.Error())
			return
		}
		writeJSON(w, http.StatusCreated, out)
	default:
		writeErr(w, http.StatusMethodNotAllowed, "method not allowed", "")
	}
}

func (s *Server) handleCampaign(w http.ResponseWriter, r *http.Request) {
	name := strings.TrimPrefix(r.URL.Path, "/v1/campaigns/")
	name = strings.Trim(name, "/")
	c := s.campaign(name)
	if c == nil {
		writeErr(w, http.StatusNotFound, "no such campaign", "")
		return
	}
	writeJSON(w, http.StatusOK, c.status())
}

func (s *Server) handleRegister(w http.ResponseWriter, r *http.Request) {
	var req api.RegisterRequest
	if !readJSON(w, r, &req, 1<<16) {
		return
	}
	id := strings.TrimSpace(req.Info.ID)
	if err := api.ValidateAgentID(id); err != nil {
		// Refused at the edge rather than sanitised later: this id becomes a
		// registry key, an owner check on every write, and a field in every
		// log line about this agent.
		writeErr(w, http.StatusBadRequest, "invalid agent id", err.Error())
		return
	}
	req.Info.ID = id
	req.Info.Hostname = api.CleanText(req.Info.Hostname)
	req.Info.Version = api.CleanText(req.Info.Version)
	req.Info.Platform = api.CleanText(req.Info.Platform)
	now := s.cfg.Now()
	s.mu.Lock()
	a, ok := s.agents[id]
	if !ok {
		a = &api.Agent{AgentInfo: req.Info, FirstSeen: now}
		s.agents[id] = a
	}
	a.AgentInfo = req.Info
	a.LastSeen = now
	s.mu.Unlock()
	writeJSON(w, http.StatusOK, api.RegisterResponse{
		AgentID: id, Interval: s.cfg.HeartbeatInterval, Server: api.Version,
	})
}

func (s *Server) handleHeartbeat(w http.ResponseWriter, r *http.Request) {
	var req api.HeartbeatRequest
	if !readJSON(w, r, &req, 1<<16) {
		return
	}
	if err := api.ValidateAgentID(req.AgentID); err != nil {
		writeErr(w, http.StatusBadRequest, "invalid agent id", err.Error())
		return
	}
	now := s.cfg.Now()
	s.mu.Lock()
	a, ok := s.agents[req.AgentID]
	if !ok {
		a = &api.Agent{AgentInfo: api.AgentInfo{ID: req.AgentID}, FirstSeen: now}
		s.agents[req.AgentID] = a
	}
	a.LastSeen = now
	a.Unit = req.Unit
	draining := s.draining
	s.mu.Unlock()

	resp := api.HeartbeatResponse{OK: true, Drain: draining}
	if req.Unit != nil {
		// A heartbeat is also a lease renewal, which is what makes the
		// agent's "am I still the owner?" question free.
		found := false
		for _, c := range s.list() {
			if expires, ok := c.renew(*req.Unit, req.AgentID, req.Fence,
				s.cfg.LeaseTTL, now); ok {
				resp.Expires = expires
				found = true
				break
			}
		}
		if !found {
			resp.Lost = true
		}
	}
	writeJSON(w, http.StatusOK, resp)
}

func (s *Server) handleLease(w http.ResponseWriter, r *http.Request) {
	var req api.LeaseRequest
	if !readJSON(w, r, &req, 1<<16) {
		return
	}
	if err := api.ValidateAgentID(req.AgentID); err != nil {
		writeErr(w, http.StatusBadRequest, "invalid agent id", err.Error())
		return
	}
	s.mu.RLock()
	draining := s.draining
	s.mu.RUnlock()
	if draining {
		writeJSON(w, http.StatusOK, api.LeaseResponse{Empty: true, Retry: 30 * time.Second})
		return
	}
	now := s.cfg.Now()
	for _, c := range s.list() {
		if req.Campaign != "" && c.def.Name != req.Campaign {
			continue
		}
		if lease := c.lease(req.AgentID, s.cfg.LeaseTTL, now); lease != nil {
			s.metrics.leases.add(1)
			s.mu.Lock()
			if a, ok := s.agents[req.AgentID]; ok {
				id := lease.Unit.ID
				a.Unit = &id
				a.Units++
				a.LastSeen = now
			}
			s.mu.Unlock()
			writeJSON(w, http.StatusOK, api.LeaseResponse{Lease: lease})
			return
		}
	}
	// No work is a normal answer, not an error: the campaign may be solved,
	// or the fleet may be bigger than the campaign needs right now.
	writeJSON(w, http.StatusOK, api.LeaseResponse{Empty: true, Retry: 15 * time.Second})
}

// handlePoints takes a raw record array, not JSON: the corpus is 32-byte
// records and base64 in a JSON envelope would cost a third more bytes on
// every upload for no benefit.
func (s *Server) handlePoints(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeErr(w, http.StatusMethodNotAllowed, "method not allowed", "")
		return
	}
	q := r.URL.Query()
	name := q.Get("campaign")
	agent := q.Get("agent")
	unit, err1 := strconv.ParseUint(q.Get("unit"), 10, 64)
	fence, err2 := strconv.ParseUint(q.Get("fence"), 10, 64)
	if name == "" || err1 != nil || err2 != nil {
		writeErr(w, http.StatusBadRequest, "campaign, agent, unit and fence are required", "")
		return
	}
	if err := api.ValidateAgentID(agent); err != nil {
		writeErr(w, http.StatusBadRequest, "invalid agent id", err.Error())
		return
	}
	c := s.campaign(name)
	if c == nil {
		writeErr(w, http.StatusNotFound, "no such campaign", "")
		return
	}
	// From here on the campaign is named by the record the server holds, not
	// by the query string that found it: one is a validated name this server
	// created, the other is whatever arrived on the wire.
	campaignName := c.def.Name
	body := http.MaxBytesReader(w, r.Body, s.cfg.MaxUploadBytes)
	data, err := io.ReadAll(body)
	if err != nil {
		writeErr(w, http.StatusRequestEntityTooLarge, "upload too large", err.Error())
		return
	}
	if len(data)%api.PointBytes != 0 {
		writeErr(w, http.StatusBadRequest, "body is not a whole number of records",
			fmt.Sprintf("%d bytes is not a multiple of %d", len(data), api.PointBytes))
		return
	}
	resp, err := c.addPoints(unit, agent, fence, q.Get("fingerprint"), data)
	switch {
	case errors.Is(err, ErrFence), errors.Is(err, ErrNoSuchUnit):
		// 409, not 401: the agent was legitimate and simply lost the race.
		// The correct response is to stop and take a new lease, which is
		// what a conflict tells it.
		s.metrics.fenceRejects.add(1)
		writeErr(w, http.StatusConflict, "lease lost", err.Error())
		return
	case errors.Is(err, ErrFingerprint):
		writeErr(w, http.StatusPreconditionFailed, "campaign fingerprint mismatch", err.Error())
		return
	case err != nil:
		writeErr(w, http.StatusInternalServerError, "cannot store points", err.Error())
		return
	}
	s.metrics.uploads.add(1)
	s.metrics.points.add(resp.Accepted)
	s.metrics.rejects.add(resp.Rejected)
	if resp.Solved {
		s.cfg.Logger.Info("campaign solved", "campaign", campaignName, "x", resp.X, "unit", unit)
	}
	if resp.Rejected > 0 {
		s.cfg.Logger.Warn("points rejected", "campaign", campaignName, "agent", agent,
			"unit", unit, "rejected", resp.Rejected)
	}
	s.mu.Lock()
	if a, ok := s.agents[agent]; ok {
		a.Points += resp.Accepted
		a.LastSeen = s.cfg.Now()
	}
	s.mu.Unlock()
	writeJSON(w, http.StatusOK, resp)
}

func (s *Server) handleComplete(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	name := q.Get("campaign")
	unit, err := strconv.ParseUint(q.Get("unit"), 10, 64)
	if name == "" || err != nil {
		writeErr(w, http.StatusBadRequest, "campaign and unit are required", "")
		return
	}
	var req api.CompleteRequest
	if !readJSON(w, r, &req, 1<<16) {
		return
	}
	if err := api.ValidateAgentID(req.AgentID); err != nil {
		writeErr(w, http.StatusBadRequest, "invalid agent id", err.Error())
		return
	}
	// The one free-text field in the protocol, cleaned once here so that
	// neither the ledger nor the log ever holds a newline an agent chose.
	req.Reason = api.CleanText(req.Reason)
	c := s.campaign(name)
	if c == nil {
		writeErr(w, http.StatusNotFound, "no such campaign", "")
		return
	}
	if err := c.complete(unit, req.AgentID, req.Fence, req.Steps, req.Points, req.Failed,
		req.Reason); err != nil {
		if errors.Is(err, ErrFence) || errors.Is(err, ErrNoSuchUnit) {
			s.metrics.fenceRejects.add(1)
			writeErr(w, http.StatusConflict, "lease lost", err.Error())
			return
		}
		writeErr(w, http.StatusInternalServerError, "cannot complete unit", err.Error())
		return
	}
	if req.Failed {
		s.cfg.Logger.Warn("unit failed", "campaign", c.def.Name, "unit", unit,
			"agent", req.AgentID, "reason", req.Reason)
	}
	s.mu.Lock()
	if a, ok := s.agents[req.AgentID]; ok {
		a.Steps += req.Steps
		a.Unit = nil
		a.LastSeen = s.cfg.Now()
	}
	s.mu.Unlock()
	writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
}

func (s *Server) handleStatus(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, s.Status(r.URL.Query().Get("agents") == "true"))
}

// Status is the one object for the CLI, a dashboard and the alarms.
func (s *Server) Status(withAgents bool) api.Status {
	now := s.cfg.Now()
	s.mu.RLock()
	names := make([]string, 0, len(s.campaigns))
	for n := range s.campaigns {
		names = append(names, n)
	}
	live, known := 0, len(s.agents)
	var agents []api.Agent
	cutoff := now.Add(-2 * s.cfg.HeartbeatInterval)
	for _, a := range s.agents {
		if a.LastSeen.After(cutoff) {
			live++
		}
		if withAgents {
			agents = append(agents, *a)
		}
	}
	s.mu.RUnlock()
	sort.Strings(names)
	out := api.Status{
		Version: api.Version,
		Uptime:  now.Sub(s.start).Round(time.Second).String(),
		Agents:  api.AgentSummary{Live: live, Known: known, List: agents},
	}
	for _, n := range names {
		if c := s.campaign(n); c != nil {
			out.Campaigns = append(out.Campaigns, c.status())
		}
	}
	return out
}

// handleMetrics emits Prometheus text format.  Hand-written rather than via
// a client library: six counters and a handful of gauges do not justify a
// dependency in a binary that ships to every node.
func (s *Server) handleMetrics(w http.ResponseWriter, r *http.Request) {
	st := s.Status(false)
	var b strings.Builder
	write := func(name, help, kind string, value float64, labels string) {
		fmt.Fprintf(&b, "# HELP %s %s\n# TYPE %s %s\n%s%s %g\n", name, help, name, kind, name,
			labels, value)
	}
	write("ca_leases_total", "Unit leases handed out.", "counter",
		float64(s.metrics.leases.get()), "")
	write("ca_points_accepted_total", "Distinguished points accepted.", "counter",
		float64(s.metrics.points.get()), "")
	write("ca_points_rejected_total", "Points that failed verification.", "counter",
		float64(s.metrics.rejects.get()), "")
	write("ca_uploads_total", "Point uploads.", "counter", float64(s.metrics.uploads.get()), "")
	write("ca_fence_rejects_total", "Writes refused because the lease was lost.", "counter",
		float64(s.metrics.fenceRejects.get()), "")
	write("ca_lease_expiries_total", "Leases that expired and were re-queued.", "counter",
		float64(s.metrics.expiries.get()), "")
	write("ca_agents_live", "Agents that have beaten recently.", "gauge",
		float64(st.Agents.Live), "")
	for _, c := range st.Campaigns {
		l := fmt.Sprintf("{campaign=%q}", c.Campaign.Name)
		write("ca_campaign_points", "Points in the corpus.", "gauge", float64(c.Stored), l)
		write("ca_campaign_steps", "Walk steps reported by finished units.", "gauge",
			float64(c.Steps), l)
		write("ca_campaign_expected_steps", "Expected steps for a full search.", "gauge",
			c.ExpectedSteps, l)
		write("ca_campaign_units_leased", "Units in flight.", "gauge", float64(c.Units.Leased), l)
		write("ca_campaign_units_pending", "Units waiting to be re-issued.", "gauge",
			float64(c.Units.Pending), l)
		solved := 0.0
		if c.Solved {
			solved = 1
		}
		write("ca_campaign_solved", "1 once the discrete logarithm is known.", "gauge", solved, l)
	}
	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	_, _ = io.WriteString(w, b.String())
}

// ---- helpers --------------------------------------------------------------

func (s *Server) campaign(name string) *campaign {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.campaigns[name]
}

func (s *Server) list() []*campaign {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]*campaign, 0, len(s.campaigns))
	names := make([]string, 0, len(s.campaigns))
	for n := range s.campaigns {
		names = append(names, n)
	}
	sort.Strings(names)
	for _, n := range names {
		out = append(out, s.campaigns[n])
	}
	return out
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	enc := json.NewEncoder(w)
	enc.SetIndent("", "  ")
	_ = enc.Encode(v)
}

func writeErr(w http.ResponseWriter, code int, msg, detail string) {
	writeJSON(w, code, api.Error{Error: msg, Detail: detail})
}

func readJSON(w http.ResponseWriter, r *http.Request, v any, limit int64) bool {
	if r.Method != http.MethodPost && r.Method != http.MethodPut {
		writeErr(w, http.StatusMethodNotAllowed, "method not allowed", "")
		return false
	}
	dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, limit))
	dec.DisallowUnknownFields()
	if err := dec.Decode(v); err != nil {
		writeErr(w, http.StatusBadRequest, "bad request body", err.Error())
		return false
	}
	return true
}

// logging records one line per request.  Structured, because the first thing
// anybody asks of a fleet's logs is "what did agent X do", and grep over
// free text does not answer it.
func logging(l *slog.Logger, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rec := &statusRecorder{ResponseWriter: w, code: http.StatusOK}
		next.ServeHTTP(rec, r)
		level := slog.LevelDebug
		if rec.code >= 500 {
			level = slog.LevelError
		} else if rec.code >= 400 {
			level = slog.LevelWarn
		}
		// The method and path come from the request line, so they are cleaned
		// before they reach a log that an operator reads and a collector
		// parses.  slog's JSON handler escapes them anyway; this is for the
		// text handler a laptop run uses, and for anything that tails the
		// file.
		l.Log(r.Context(), level, "request", "method", api.CleanText(r.Method),
			"path", api.CleanText(r.URL.Path), "status", rec.code, "bytes", rec.bytes,
			"ms", time.Since(start).Milliseconds(), "remote", r.RemoteAddr)
	})
}

type statusRecorder struct {
	http.ResponseWriter
	code  int
	bytes int
}

func (s *statusRecorder) WriteHeader(code int) {
	s.code = code
	s.ResponseWriter.WriteHeader(code)
}

func (s *statusRecorder) Write(b []byte) (int, error) {
	n, err := s.ResponseWriter.Write(b)
	s.bytes += n
	return n, err
}
