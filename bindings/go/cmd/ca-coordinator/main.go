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

func main() {
	var (
		jobPath   = flag.String("job", "", "job document to serve (a file written by `ca coord-job`)")
		listen    = flag.String("listen", ":8080", "address to serve on")
		tokenFile = flag.String("token-file", "", "file whose first line is the required bearer token")
		requireTk = flag.Bool("require-token", false, "refuse to start without a token")
		logPath   = flag.String("log", "", "append every accepted check-in to this file, and replay it at start")
		leaseSecs = flag.Uint64("lease-secs", 120, "seconds a silent claim counts as active (reporting only)")
		pushEvery = flag.Duration("push-interval", 500*time.Millisecond, "how often an idle channel is examined")
		idle      = flag.Duration("idle-timeout", 5*time.Minute, "drop a channel silent this long; pings go at a third of it")
		report    = flag.Duration("report-interval", 30*time.Second, "how often to log a progress line (0 disables)")
		logFormat = flag.String("log-format", "json", "log format: json or text")
	)
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

	log := newLogger(*logFormat)
	slog.SetDefault(log)

	if *jobPath == "" {
		log.Error("no -job given; the coordinator serves exactly one job document")
		os.Exit(2)
	}
	job, err := loadJob(*jobPath)
	if err != nil {
		log.Error("cannot load the job", "path", *jobPath, "err", err)
		os.Exit(1)
	}
	token, err := loadToken(*tokenFile)
	if err != nil {
		log.Error("cannot read the token", "err", err)
		os.Exit(1)
	}
	if token == "" && *requireTk {
		log.Error("-require-token was set but no token was given (-token-file or " + ca.TokenEnv + ")")
		os.Exit(2)
	}
	if token == "" && !strings.HasPrefix(*listen, "127.0.0.1") && !strings.HasPrefix(*listen, "localhost") {
		log.Warn("serving with no token: anyone who can reach this can read the job and write to the log",
			"listen", *listen)
	}

	ctx, err := ca.OpenCtx(job)
	if err != nil {
		log.Error("cannot derive the job context", "err", err)
		os.Exit(1)
	}
	defer ctx.Close()
	state, err := ca.NewState(ctx)
	if err != nil {
		log.Error("cannot create the state", "err", err)
		os.Exit(1)
	}
	defer state.Close()

	// Durability, if asked for.  The hub's state is in memory and a pod
	// is replaceable by design; losing it costs no work, because agents
	// keep their own tables and re-push.  What a log buys is that a
	// replacement starts where the last one stopped instead of waiting
	// for the fleet to refill it.  Replay is safe at any time: the merge
	// is idempotent.
	var sink *checkinLog
	if *logPath != "" {
		sink, err = openCheckinLog(*logPath)
		if err != nil {
			log.Error("cannot open the check-in log", "path", *logPath, "err", err)
			os.Exit(1)
		}
		defer sink.Close()
		n, bad, err := sink.Replay(state)
		if err != nil {
			log.Error("cannot replay the check-in log", "err", err)
			os.Exit(1)
		}
		log.Info("check-in log replayed", "path", *logPath, "merged", n, "rejected", bad)
	}

	hub := NewHub(ctx, state, Config{
		Token:        token,
		PushInterval: *pushEvery,
		IdleTimeout:  *idle,
		LeaseSecs:    *leaseSecs,
		OnCheckIn: func(line string) {
			if sink != nil {
				sink.Append(line)
			}
		},
		Log: log,
	})

	srv := &http.Server{
		Addr:    *listen,
		Handler: hub.Handler(),
		// No write timeout: a reverse channel is a long-lived hijacked
		// connection and a deadline would cut it.  ReadHeaderTimeout
		// still bounds a client that opens a socket and says nothing.
		ReadHeaderTimeout: 15 * time.Second,
		IdleTimeout:       *idle,
		ErrorLog:          nil,
	}

	log.Info("serving",
		"job", job.IDString(),
		"listen", *listen,
		"token", token != "",
		"expected_steps", ctx.ExpectedSteps(),
		"expected_dps", ctx.ExpectedDPs(),
	)

	root, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	if *report > 0 {
		go reportLoop(root, hub, state, *leaseSecs, *report, log)
	}

	errCh := make(chan error, 1)
	go func() {
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			errCh <- err
		}
	}()

	select {
	case err := <-errCh:
		log.Error("server failed", "err", err)
		os.Exit(1)
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
	p := state.Progress(*leaseSecs)
	log.Info("stopped", "steps", p.Steps, "dps", p.DPsStored, "checkins", p.Checkins,
		"solved", p.Solved, "solution", p.Solution)
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
