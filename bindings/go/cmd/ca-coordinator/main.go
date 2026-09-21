package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"sync"
	"syscall"
	"time"

	ca "github.com/aburan28/cryptanalysis/bindings/go"
)

func jsonEncoder(w io.Writer) *json.Encoder { return json.NewEncoder(w) }

// options are the flag values, parsed by main and used by run.
//
// The split exists because os.Exit does not run deferred functions: main
// parses and exits, run acquires things and releases them on the way
// out, and nothing that has to be closed is acquired next to an
// os.Exit.
type options struct {
	jobPath   string
	listen    string
	tokenFile string
	requireTk bool
	logPath   string
	leaseSecs uint64
	pushEvery time.Duration
	idle      time.Duration
	report    time.Duration
	logFormat string
	peers     peerList
	peerEvery time.Duration
}

// peerList collects repeated -peer flags.  Each is name=url, or just a url
// (the host then names it), and the peer's token comes from -peer-token-file
// or falls back to this hub's own token, which is the usual case: one
// campaign, one shared secret.
type peerList []string

func (p *peerList) String() string { return strings.Join(*p, ",") }
func (p *peerList) Set(v string) error {
	if strings.TrimSpace(v) == "" {
		return errors.New("empty -peer")
	}
	*p = append(*p, v)
	return nil
}

// parsePeers turns the flags into Peers, refusing anything that would
// silently not federate.
func parsePeers(raw []string, token string) ([]Peer, error) {
	out := make([]Peer, 0, len(raw))
	seen := map[string]bool{}
	for _, item := range raw {
		name, url := "", strings.TrimSpace(item)
		if i := strings.Index(item, "="); i > 0 {
			name = strings.TrimSpace(item[:i])
			url = strings.TrimSpace(item[i+1:])
		}
		if !strings.HasPrefix(url, "http://") && !strings.HasPrefix(url, "https://") {
			return nil, fmt.Errorf("peer %q: need an http:// or https:// URL", item)
		}
		if name == "" {
			name = url
		}
		if seen[url] {
			return nil, fmt.Errorf("peer %q: listed twice", url)
		}
		seen[url] = true
		out = append(out, Peer{Name: name, URL: url, Token: token})
	}
	return out, nil
}

func main() {
	var o options
	flag.StringVar(&o.jobPath, "job", "", "job document to serve (a file written by `ca coord-job`)")
	flag.StringVar(&o.listen, "listen", ":8080", "address to serve on")
	flag.StringVar(&o.tokenFile, "token-file", "", "file whose first line is the required bearer token")
	flag.BoolVar(&o.requireTk, "require-token", false, "refuse to start without a token")
	flag.StringVar(&o.logPath, "log", "", "append every accepted check-in to this file, and replay it at start")
	flag.Uint64Var(&o.leaseSecs, "lease-secs", 120, "seconds a silent claim counts as active (reporting only)")
	flag.DurationVar(&o.pushEvery, "push-interval", 500*time.Millisecond, "how often an idle channel is examined")
	flag.DurationVar(&o.idle, "idle-timeout", 5*time.Minute, "drop a channel silent this long; pings go at a third of it")
	flag.DurationVar(&o.report, "report-interval", 30*time.Second, "how often to log a progress line (0 disables)")
	flag.StringVar(&o.logFormat, "log-format", "json", "log format: json or text")
	flag.Var(&o.peers, "peer", "another coordinator to gossip with, as name=url or url (repeatable)")
	flag.DurationVar(&o.peerEvery, "peer-interval", 5*time.Second, "how often each peer is synced")
	flag.Usage = func() {
		fmt.Fprintf(flag.CommandLine.Output(),
			"ca-coordinator: the rendezvous a distributed-rho fleet dials out to.\n\n"+
				"Agents open every connection (GET /v1/channel with Upgrade: %s) and the hub\n"+
				"answers on the same socket, so an agent needs no inbound reachability.\n"+
				"It is a rendezvous, not an authority: losing it loses no work.\n\n"+
				"Routes: /healthz /readyz /v1/job /v1/status /v1/sync /v1/channel /metrics\n"+
				"Environment: %s (token, overridden by -token-file)\n\n"+
				"Usage:\n", ca.ChannelProtocol, ca.TokenEnv)
		flag.PrintDefaults()
	}
	flag.Parse()

	log := newLogger(o.logFormat)
	slog.SetDefault(log)

	code, err := run(&o, log)
	if err != nil {
		log.Error("coordinator failed", "err", err)
	}
	os.Exit(code)
}

// run does the work and returns the process's exit status.  Everything
// it acquires is released before it returns.
func run(o *options, log *slog.Logger) (int, error) {
	if o.jobPath == "" {
		return 2, errors.New("no -job given; the coordinator serves exactly one job document")
	}
	job, err := loadJob(o.jobPath)
	if err != nil {
		return 1, fmt.Errorf("cannot load the job from %s: %w", o.jobPath, err)
	}
	token, err := loadToken(o.tokenFile)
	if err != nil {
		return 1, fmt.Errorf("cannot read the token: %w", err)
	}
	if token == "" && o.requireTk {
		return 2, errors.New("-require-token was set but no token was given (-token-file or " + ca.TokenEnv + ")")
	}
	if token == "" && !strings.HasPrefix(o.listen, "127.0.0.1") && !strings.HasPrefix(o.listen, "localhost") {
		log.Warn("serving with no token: anyone who can reach this can read the job and write to the log",
			"listen", o.listen)
	}

	ctx, err := ca.OpenCtx(job)
	if err != nil {
		return 1, fmt.Errorf("cannot derive the job context: %w", err)
	}
	defer ctx.Close()
	state, err := ca.NewState(ctx)
	if err != nil {
		return 1, fmt.Errorf("cannot create the state: %w", err)
	}
	defer state.Close()

	// Durability, if asked for.  The hub's state is in memory and a pod
	// is replaceable by design; losing it costs no work, because agents
	// keep their own tables and re-push.  What a log buys is that a
	// replacement starts where the last one stopped instead of waiting
	// for the fleet to refill it.  Replay is safe at any time: the merge
	// is idempotent.
	var sink *checkinLog
	if o.logPath != "" {
		sink, err = openCheckinLog(o.logPath)
		if err != nil {
			return 1, fmt.Errorf("cannot open the check-in log %s: %w", o.logPath, err)
		}
		defer sink.Close()
		n, bad, err := sink.Replay(state)
		if err != nil {
			return 1, fmt.Errorf("cannot replay the check-in log: %w", err)
		}
		log.Info("check-in log replayed", "path", o.logPath, "merged", n, "rejected", bad)
	}

	peers, err := parsePeers(o.peers, token)
	if err != nil {
		return 2, err
	}
	hub := NewHub(ctx, state, &Config{
		Token:        token,
		PushInterval: o.pushEvery,
		IdleTimeout:  o.idle,
		LeaseSecs:    o.leaseSecs,
		Peers:        peers,
		PeerInterval: o.peerEvery,
		OnCheckIn: func(line string) {
			if sink != nil {
				sink.Append(line)
			}
		},
		Log: log,
	})

	srv := &http.Server{
		Addr:    o.listen,
		Handler: hub.Handler(),
		// No write timeout: a reverse channel is a long-lived hijacked
		// connection and a deadline would cut it.  ReadHeaderTimeout
		// still bounds a client that opens a socket and says nothing.
		ReadHeaderTimeout: 15 * time.Second,
		IdleTimeout:       o.idle,
	}

	log.Info("serving",
		"job", job.IDString(),
		"listen", o.listen,
		"token", token != "",
		"peers", len(peers),
		"expected_steps", ctx.ExpectedSteps(),
		"expected_dps", ctx.ExpectedDPs(),
	)

	root, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	if o.report > 0 {
		go reportLoop(root, hub, state, o.leaseSecs, o.report, log)
	}
	// Federation starts with the server and stops with it.  A hub with no
	// peers starts nothing.
	hub.StartPeering(root)
	for _, p := range peers {
		log.Info("peering", "peer", p.Name, "url", p.URL, "every", o.peerEvery)
	}

	errCh := make(chan error, 1)
	go func() {
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			errCh <- err
		}
	}()

	select {
	case err := <-errCh:
		return 1, fmt.Errorf("server failed: %w", err)
	case <-root.Done():
		log.Info("shutting down")
	}

	// Hijacked connections are not tracked by Shutdown, so agents see
	// their channel close and reconnect with backoff -- which is the
	// same path a pod eviction takes, and costs no work.
	shutCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := srv.Shutdown(shutCtx); err != nil {
		log.Warn("shutdown was not clean", "err", err)
	}
	p := state.Progress(o.leaseSecs)
	log.Info("stopped", "steps", p.Steps, "dps", p.DPsStored, "checkins", p.Checkins,
		"solved", p.Solved, "solution", p.Solution)
	return 0, nil
}

func newLogger(format string) *slog.Logger {
	opts := &slog.HandlerOptions{Level: slog.LevelInfo}
	if strings.EqualFold(format, "text") {
		return slog.New(slog.NewTextHandler(os.Stderr, opts))
	}
	return slog.New(slog.NewJSONHandler(os.Stderr, opts))
}

func loadJob(path string) (ca.Job, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return ca.Job{}, err
	}
	return ca.ParseJob(string(b))
}

// loadToken prefers the file (a Kubernetes Secret is mounted as one)
// and falls back to the environment.  Never a flag: a command line is
// visible to every process on the host.
func loadToken(path string) (string, error) {
	if path != "" {
		b, err := os.ReadFile(path)
		if err != nil {
			return "", err
		}
		tok := strings.TrimSpace(strings.SplitN(string(b), "\n", 2)[0])
		if tok == "" {
			return "", fmt.Errorf("%s: empty", path)
		}
		return tok, nil
	}
	return strings.TrimSpace(os.Getenv(ca.TokenEnv)), nil
}

func reportLoop(ctx context.Context, hub *Hub, state *ca.State, lease uint64, every time.Duration, log *slog.Logger) {
	t := time.NewTicker(every)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
		}
		p := state.Progress(lease)
		s := hub.Stats()
		log.Info("progress",
			"agents", s.Agents, "steps", p.Steps,
			"percent", fmt.Sprintf("%.1f", 100*p.Fraction),
			"dps", p.DPsStored, "units_done", p.UnitsCompleted, "units_active", p.UnitsActive,
			"accepted", s.Accepted, "pushed", s.Pushed, "rejected", s.Rejected,
			"unauthorized", s.Unauthorized, "solved", p.Solved)
	}
}

// checkinLog is an append-only file of check-in lines: the wire form is
// already the storage form, so this is a plain text file that `grep`
// reads and the merge can replay in any order.
type checkinLog struct {
	mu sync.Mutex
	f  *os.File
}

func openCheckinLog(path string) (*checkinLog, error) {
	if dir := filepath.Dir(path); dir != "" {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return nil, err
		}
	}
	// 0640: the log carries the fleet's distinguished points, which are
	// public facts about the job, but it is still operational data and
	// there is no reason for it to be world-readable.
	f, err := os.OpenFile(path, os.O_RDWR|os.O_CREATE|os.O_APPEND, 0o640)
	if err != nil {
		return nil, err
	}
	return &checkinLog{f: f}, nil
}

// Replay merges everything already on disk.  Duplicates and
// out-of-order entries are harmless: the merge is idempotent and
// order-independent, which is the whole reason this can be a flat file.
func (l *checkinLog) Replay(state *ca.State) (merged, rejected int, err error) {
	l.mu.Lock()
	defer l.mu.Unlock()
	if _, err := l.f.Seek(0, io.SeekStart); err != nil {
		return 0, 0, err
	}
	sc := newLineScanner(l.f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if !strings.HasPrefix(line, "ci ") {
			continue
		}
		oc, err := state.ApplyLine(line)
		if err != nil {
			rejected++
			continue
		}
		if oc.Fresh {
			merged++
		}
		rejected += oc.RejectedDPs
	}
	if err := sc.Err(); err != nil {
		return merged, rejected, err
	}
	_, err = l.f.Seek(0, io.SeekEnd)
	return merged, rejected, err
}

func (l *checkinLog) Append(line string) {
	l.mu.Lock()
	defer l.mu.Unlock()
	if _, err := l.f.WriteString(line + "\n"); err != nil {
		slog.Warn("check-in log write failed", "err", err)
	}
}

func (l *checkinLog) Close() error {
	l.mu.Lock()
	defer l.mu.Unlock()
	return l.f.Close()
}
