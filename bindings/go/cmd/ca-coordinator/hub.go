// Package main implements ca-coordinator: the rendezvous a fleet of
// distributed-rho agents dials out to.
//
// # Why this exists, and what it is not
//
// Parallel rho normally assumes the workers can reach each other.  On a
// cloud fleet almost none can: private subnets, NAT, spot instances,
// containers with no inbound rule.  What is reachable from everywhere is
// one URL behind somebody's load balancer.  So the topology is a hub,
// every connection is opened by the agent, and the hub answers on that
// same socket -- the reverse channel -- to push other agents'
// distinguished points and the solution to a machine it could never have
// dialled.
//
// It is a rendezvous, not an authority.  It holds the same CRDT every
// agent holds, verifies every point with the same two scalar
// multiplications (through the C library, in one implementation), and
// hands out no work: agents claim units themselves under a lease.
// Losing it loses no work -- agents keep walking and reconverge when it
// returns -- which is why it is safe to run as a single replica and
// restart it whenever Kubernetes feels like it.
//
// Deliberately absent: work assignment, a database, leader election,
// anything that would make this the thing the campaign cannot survive.
package main

import (
	"bufio"
	"context"
	"crypto/subtle"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	ca "github.com/aburan28/cryptanalysis/bindings/go"
)

// Config is everything the hub needs to run.
type Config struct {
	// Bearer token agents must present.  Empty disables authentication,
	// which is only defensible on a private network.
	Token string
	// How often an idle channel is examined for check-ins to push.
	PushInterval time.Duration
	// Drop a channel that has been silent this long.  The hub pings at a
	// third of this, so a proxy's idle timeout must be above it.
	IdleTimeout time.Duration
	// Lease length used when reporting which units are active.
	LeaseSecs uint64
	// Called with every check-in newly accepted from an agent, after it
	// is merged: the durability hook.  Runs on the connection's
	// goroutine and must be safe for concurrent use.
	OnCheckIn func(line string)
	Log       *slog.Logger
}

// Stats are the counters /v1/status and /metrics report.
type Stats struct {
	Agents        int64 `json:"agents"`
	ChannelsTotal int64 `json:"channels"`
	Accepted      int64 `json:"accepted"`
	Rejected      int64 `json:"rejected"`
	Pushed        int64 `json:"pushed"`
	Unauthorized  int64 `json:"unauthorized"`
}

// Hub serves one job.
type Hub struct {
	ctx   *ca.Ctx
	state *ca.State
	cfg   Config
	log   *slog.Logger

	agents        atomic.Int64
	channelsTotal atomic.Int64
	accepted      atomic.Int64
	rejected      atomic.Int64
	pushed        atomic.Int64
	unauthorized  atomic.Int64

	started time.Time
}

// NewHub builds a hub over an existing state.
func NewHub(ctx *ca.Ctx, state *ca.State, cfg Config) *Hub {
	if cfg.PushInterval <= 0 {
		cfg.PushInterval = 500 * time.Millisecond
	}
	if cfg.IdleTimeout <= 0 {
		cfg.IdleTimeout = 5 * time.Minute
	}
	if cfg.LeaseSecs == 0 {
		cfg.LeaseSecs = 120
	}
	if cfg.Log == nil {
		cfg.Log = slog.Default()
	}
	return &Hub{ctx: ctx, state: state, cfg: cfg, log: cfg.Log, started: time.Now()}
}

// Stats snapshots the counters.
func (h *Hub) Stats() Stats {
	return Stats{
		Agents:        h.agents.Load(),
		ChannelsTotal: h.channelsTotal.Load(),
		Accepted:      h.accepted.Load(),
		Rejected:      h.rejected.Load(),
		Pushed:        h.pushed.Load(),
		Unauthorized:  h.unauthorized.Load(),
	}
}

// absorb merges one check-in line and runs the durability hook.  The
// verification that matters happens inside ApplyLine, in C.
func (h *Hub) absorb(line string) (accepted, rejected int) {
	oc, err := h.state.ApplyLine(line)
	if err != nil {
		h.rejected.Add(1)
		return 0, 1
	}
	if oc.Fresh {
		h.accepted.Add(1)
		if h.cfg.OnCheckIn != nil {
			h.cfg.OnCheckIn(line)
		}
	}
	if oc.RejectedDPs > 0 {
		h.rejected.Add(int64(oc.RejectedDPs))
	}
	if oc.SolvedNow {
		if x, ok := h.state.Solution(); ok {
			h.log.Info("solved", "x", x, "job", h.ctx.Job().IDString())
		}
	}
	return oc.AcceptedDPs, oc.RejectedDPs
}

// Handler is the hub's HTTP surface.
//
// The routes are matched on the tail of the path so that a hub
// published under a prefix by an ingress answers the same.
func (h *Hub) Handler() http.Handler {
	mux := http.NewServeMux()
	// Outside the token on purpose: a load balancer carries no
	// credential, and the answer says nothing about the job.
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{"ok": true})
	})
	mux.HandleFunc("/readyz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{"ok": true, "job": h.ctx.Job().IDString()})
	})
	mux.Handle("/v1/job", h.auth(http.HandlerFunc(h.handleJob)))
	mux.Handle("/v1/status", h.auth(http.HandlerFunc(h.handleStatus)))
	mux.Handle("/v1/sync", h.auth(http.HandlerFunc(h.handleSync)))
	mux.Handle("/v1/channel", h.auth(http.HandlerFunc(h.handleChannel)))
	mux.Handle("/metrics", h.auth(http.HandlerFunc(h.handleMetrics)))
	return routeOnTail(mux)
}

// hubRoutes are the paths the mux answers, and the tails routeOnTail
// recognises under a prefix.
var hubRoutes = []string{
	"/healthz", "/readyz",
	"/v1/job", "/v1/status", "/v1/sync", "/v1/channel",
	"/metrics",
}

// routeOnTail lets a hub published under a prefix answer the same as one
// at the root.  An ingress that routes `/rho` to this service forwards
// `/rho/v1/channel` unchanged unless it is configured to rewrite, and the
// C agent sends whatever prefix its coordinator URL carried -- so the
// tail is what identifies the route.  Every route begins with a slash, so
// a suffix match cannot split a path segment, and a request that matches
// nothing reaches the mux unchanged and 404s there.
//
// This widens no access: the token still guards the same handlers.
func routeOnTail(mux http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		p := strings.TrimSuffix(r.URL.Path, "/")
		for _, route := range hubRoutes {
			if p == route {
				mux.ServeHTTP(w, r)
				return
			}
			if strings.HasSuffix(p, route) {
				r2 := r.Clone(r.Context())
				u := *r.URL
				u.Path = route
				r2.URL = &u
				mux.ServeHTTP(w, r2)
				return
			}
		}
		mux.ServeHTTP(w, r)
	})
}

// auth checks the bearer token in constant time.  It is access control,
// not integrity: every record in the log is self-verifying, so the token
// keeps strangers from flooding the log and buys nothing else.
func (h *Hub) auth(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if h.cfg.Token == "" {
			next.ServeHTTP(w, r)
			return
		}
		const prefix = "Bearer "
		got := r.Header.Get("Authorization")
		if !strings.HasPrefix(got, prefix) ||
			subtle.ConstantTimeCompare([]byte(got[len(prefix):]), []byte(h.cfg.Token)) != 1 {
			h.unauthorized.Add(1)
			writeJSON(w, http.StatusUnauthorized, map[string]any{
				"error": "bad or missing bearer token",
			})
			return
		}
		next.ServeHTTP(w, r)
	})
}

// handleJob serves the job document, so an agent configured with only a
// URL needs nothing on disk.
func (h *Hub) handleJob(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	fmt.Fprintln(w, h.ctx.Job().String())
}

func (h *Hub) handleStatus(w http.ResponseWriter, r *http.Request) {
	p := h.state.Progress(h.cfg.LeaseSecs)
	writeJSON(w, http.StatusOK, struct {
		JobID string  `json:"job_id"`
		Up    float64 `json:"uptime_seconds"`
		ca.Progress
		Hub Stats `json:"hub"`
	}{
		JobID:    h.ctx.Job().IDString(),
		Up:       time.Since(h.started).Seconds(),
		Progress: p,
		Hub:      h.Stats(),
	})
}

// handleSync is the pollable fallback: the body is the caller's version
// vector and whatever check-ins it holds; the reply is our vector and
// the check-ins it lacks.  Anything that cannot hold a socket open --
// `ca coord-status`, a cron job, a probe -- uses this.
func (h *Hub) handleSync(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{"error": "POST only"})
		return
	}
	var known ca.VersionVector
	sc := bufio.NewScanner(io.LimitReader(r.Body, 1<<22))
	sc.Buffer(make([]byte, 0, 64<<10), ca.LineMax)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		switch {
		case strings.HasPrefix(line, "ci "):
			h.absorb(line)
		case strings.HasPrefix(line, "vv"):
			known = ca.ParseVersionVector(line)
		}
	}
	// Built first and sent with a length, rather than streamed: a
	// streamed body outgrows net/http's write buffer and goes out
	// chunked, and every byte of this is meant for a client that has to
	// parse it.  A proxy may still chunk it, which the C client handles,
	// but the hub should not be the one introducing it.
	var body strings.Builder
	fmt.Fprintf(&body, "vv%s\n", h.state.VersionVector())
	for _, line := range h.state.DeltaFrom(known) {
		fmt.Fprintln(&body, line)
	}
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.Header().Set("Content-Length", strconv.Itoa(body.Len()))
	_, _ = io.WriteString(w, body.String())
}

// handleMetrics is Prometheus text format, so the chart's ServiceMonitor
// has something to scrape.
func (h *Hub) handleMetrics(w http.ResponseWriter, r *http.Request) {
	s := h.Stats()
	p := h.state.Progress(h.cfg.LeaseSecs)
	w.Header().Set("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
	m := []struct {
		name, help, typ string
		value           float64
	}{
		{"carho_agents_connected", "Agents holding a reverse channel open right now.", "gauge", float64(s.Agents)},
		{"carho_channels_total", "Reverse channels opened since start.", "counter", float64(s.ChannelsTotal)},
		{"carho_checkins_accepted_total", "Check-ins merged from agents.", "counter", float64(s.Accepted)},
		{"carho_records_rejected_total", "Records refused: forged point, foreign job, malformed line.", "counter", float64(s.Rejected)},
		{"carho_checkins_pushed_total", "Check-ins pushed down reverse channels.", "counter", float64(s.Pushed)},
		{"carho_unauthorized_total", "Requests refused for a bad or missing token.", "counter", float64(s.Unauthorized)},
		{"carho_steps_total", "Group operations walked by the whole fleet.", "counter", float64(p.Steps)},
		{"carho_expected_steps", "Expected steps to the solve, sqrt(pi n / 2).", "gauge", p.ExpectedSteps},
		{"carho_progress_fraction", "Steps over expected steps; 1.0 is the median solve time.", "gauge", p.Fraction},
		{"carho_distinguished_points", "Distinguished points in the shared table.", "gauge", float64(p.DPsStored)},
		{"carho_units_completed", "Work units finished.", "gauge", float64(p.UnitsCompleted)},
		{"carho_units_active", "Work units with a live lease.", "gauge", float64(p.UnitsActive)},
		{"carho_peers", "Distinct lanes ever heard from.", "gauge", float64(p.Peers)},
		{"carho_solved", "1 once the instance is solved.", "gauge", boolFloat(p.Solved)},
	}
	for _, e := range m {
		fmt.Fprintf(w, "# HELP %s %s\n# TYPE %s %s\n%s %g\n", e.name, e.help, e.name, e.typ, e.name, e.value)
	}
}

func boolFloat(b bool) float64 {
	if b {
		return 1
	}
	return 0
}

// handleChannel is the reverse channel: an HTTP upgrade, after which the
// same socket carries one line per message in both directions.  The
// upgrade is the WebSocket move, and it is what gets this through an
// ingress or an ALB.
func (h *Hub) handleChannel(w http.ResponseWriter, r *http.Request) {
	if !strings.EqualFold(r.Header.Get("Upgrade"), ca.ChannelProtocol) {
		writeJSON(w, http.StatusUpgradeRequired, map[string]any{
			"error": "upgrade to " + ca.ChannelProtocol,
		})
		return
	}
	hj, ok := w.(http.Hijacker)
	if !ok {
		writeJSON(w, http.StatusInternalServerError, map[string]any{
			"error": "connection cannot be hijacked",
		})
		return
	}
	conn, rw, err := hj.Hijack()
	if err != nil {
		h.log.Warn("hijack failed", "err", err)
		return
	}
	defer conn.Close()
	if _, err := rw.WriteString("HTTP/1.1 101 Switching Protocols\r\nUpgrade: " +
		ca.ChannelProtocol + "\r\nConnection: Upgrade\r\n\r\n"); err != nil {
		return
	}
	if err := rw.Flush(); err != nil {
		return
	}
	h.runChannel(r.Context(), conn, rw)
}

// channel is one agent's connection: a reader (this goroutine) and a
// pusher, sharing the socket's write half.
type channel struct {
	hub   *Hub
	conn  net.Conn
	out   *bufio.ReadWriter
	wmu   sync.Mutex
	known atomic.Pointer[ca.VersionVector]
}

func (c *channel) send(line string) error {
	c.wmu.Lock()
	defer c.wmu.Unlock()
	if err := c.conn.SetWriteDeadline(time.Now().Add(30 * time.Second)); err != nil {
		return err
	}
	if _, err := c.out.WriteString(line + "\n"); err != nil {
		return err
	}
	return c.out.Flush()
}

func (h *Hub) runChannel(reqCtx context.Context, conn net.Conn, rw *bufio.ReadWriter) {
	ch := &channel{hub: h, conn: conn, out: rw}
	empty := ca.VersionVector{}
	ch.known.Store(&empty)

	h.agents.Add(1)
	h.channelsTotal.Add(1)
	defer h.agents.Add(-1)

	ctx, cancel := context.WithCancel(context.WithoutCancel(reqCtx))
	defer cancel()

	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		h.pushLoop(ctx, ch)
	}()
	defer wg.Wait()

	sc := bufio.NewScanner(rw)
	sc.Buffer(make([]byte, 0, 64<<10), ca.LineMax)
	for {
		// The read deadline is the idle timeout: a silent agent is a
		// dead socket, not a slow walker (its lease is separate, and
		// expires on its own schedule).
		if err := conn.SetReadDeadline(time.Now().Add(h.cfg.IdleTimeout)); err != nil {
			return
		}
		if !sc.Scan() {
			return
		}
		line := strings.TrimSpace(sc.Text())
		switch {
		case strings.HasPrefix(line, "hello "), strings.HasPrefix(line, "pull "):
			rest := line
			if strings.HasPrefix(line, "hello ") {
				// hello <job-id> <peer> [<peer>:<seq> …]
				fields := strings.Fields(line)
				if len(fields) < 3 {
					_ = ch.send("err malformed hello")
					return
				}
				if fields[1] != fmt.Sprint(h.ctx.Job().ID()) {
					_ = ch.send("err different job")
					h.rejected.Add(1)
					return
				}
				rest = strings.Join(fields[3:], " ")
			}
			vv := ca.ParseVersionVector(rest)
			ch.known.Store(&vv)
		case strings.HasPrefix(line, "ci "):
			acc, rej := h.absorb(line)
			if err := ch.send(fmt.Sprintf("ack %d %d", acc, rej)); err != nil {
				return
			}
		case line == "ping" || line == "":
			// keepalive
		}
	}
}

// pushLoop is the half that makes the channel reverse: it wakes on a
// timer, asks the state what this agent is missing, and writes it down
// the socket the agent opened.  An idle channel gets a ping instead,
// because the NAT and the proxy in between both drop silent connections.
func (h *Hub) pushLoop(ctx context.Context, ch *channel) {
	tick := time.NewTicker(h.cfg.PushInterval)
	defer tick.Stop()
	ping := h.cfg.IdleTimeout / 3
	if ping <= 0 {
		ping = time.Minute
	}
	lastWrite := time.Now()
	for {
		select {
		case <-ctx.Done():
			return
		case <-tick.C:
		}
		known := *ch.known.Load()
		delta, reached := h.state.DeltaSince(known)
		if len(delta) == 0 {
			if time.Since(lastWrite) >= ping {
				if err := ch.send("ping"); err != nil {
					_ = ch.conn.Close()
					return
				}
				lastWrite = time.Now()
			}
			continue
		}
		for _, line := range delta {
			if err := ch.send(line); err != nil {
				_ = ch.conn.Close()
				return
			}
			h.pushed.Add(1)
		}
		lastWrite = time.Now()
		// Credit the agent with exactly the lines that went out, not with
		// the hub's state as it stands now: a check-in that arrived while
		// the delta was being sent was not in it, and marking it known
		// would hold it back until this socket drops.
		ch.known.Store(&reached)
	}
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	enc := jsonEncoder(w)
	if err := enc.Encode(v); err != nil && !errors.Is(err, io.ErrClosedPipe) {
		slog.Debug("write failed", "err", err)
	}
}
