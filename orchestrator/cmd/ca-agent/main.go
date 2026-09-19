// Command ca-agent leases work units from a control plane and walks them.
//
//	ca-agent --server http://control:8080 --token ... --ca /usr/bin/ca
//
// The agent is meant to be boring to deploy: one binary, one required flag,
// no state on disk, and a clean exit on SIGTERM.  That is what makes it
// runnable as a preemptible pod, on a spot instance, or in a systemd unit
// with Restart=always, without any of those needing to know anything about
// the search.
//
// It exposes its own tiny HTTP surface (--health-listen) only for probes:
// /healthz is liveness, /readyz reports whether the walker binary works and
// the control plane is reachable, and /stats is what a person wants when
// they ssh into one node to ask what it has been doing.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/aburan28/cryptanalysis/orchestrator/api"
	"github.com/aburan28/cryptanalysis/orchestrator/internal/agent"
)

func env(name, def string) string {
	if v := os.Getenv(name); v != "" {
		return v
	}
	return def
}

func main() {
	fs := flag.NewFlagSet("ca-agent", flag.ExitOnError)
	server := fs.String("server", env("CA_SERVER", ""), "control plane URL (required)")
	token := fs.String("token", os.Getenv("CA_TOKEN"), "bearer token")
	tokenFile := fs.String("token-file", env("CA_TOKEN_FILE", ""),
		"read the bearer token from this file (a Kubernetes secret mount)")
	caBin := fs.String("ca", env("CA_BIN", "ca"), "the library's ca binary")
	campaign := fs.String("campaign", env("CA_CAMPAIGN", ""), "only take work from this campaign")
	id := fs.String("id", env("CA_AGENT_ID", ""), "agent id (default: hostname plus a suffix)")
	tmp := fs.String("tmp", env("CA_TMPDIR", ""), "where unit output is written before upload")
	labels := fs.String("labels", env("CA_LABELS", ""), "comma-separated k=v labels")
	maxUnits := fs.Int("max-units", 0, "stop after this many units (0: forever)")
	healthAddr := fs.String("health-listen", env("CA_HEALTH_LISTEN", ":8081"),
		"address for /healthz, /readyz and /stats (empty: disabled)")
	logLevel := fs.String("log-level", env("CA_LOG_LEVEL", "info"), "debug, info, warn or error")
	idle := fs.Duration("idle-backoff", 15*time.Second, "wait when there is no work")
	if err := fs.Parse(os.Args[1:]); err != nil {
		os.Exit(2)
	}
	if *server == "" {
		fmt.Fprintln(os.Stderr, "error: --server (or CA_SERVER) is required")
		os.Exit(2)
	}
	var level slog.Level
	if err := level.UnmarshalText([]byte(*logLevel)); err != nil {
		level = slog.LevelInfo
	}
	log := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: level}))

	if *tokenFile != "" {
		blob, err := os.ReadFile(*tokenFile)
		if err != nil {
			log.Error("reading the token file", "error", err)
			os.Exit(1)
		}
		*token = strings.TrimSpace(string(blob))
	}

	// Probe the walker before registering.  An agent that cannot walk should
	// fail immediately and visibly rather than register, take a unit, and
	// hold it until the lease expires -- which is how one broken image
	// slows a whole fleet down without anything looking broken.
	version, err := agent.ProbeBinary(*caBin)
	if err != nil {
		log.Error("the ca binary does not work", "binary", *caBin, "error", err)
		os.Exit(1)
	}
	log.Info("walker ready", "binary", *caBin, "library", version)

	a := agent.New(agent.Config{
		Server: *server, Token: *token, Campaign: *campaign, ID: *id,
		Labels: parseLabels(*labels), IdleBackoff: *idle, MaxUnits: *maxUnits, Logger: log,
	}, api.NewClient(*server, *token), &agent.CLIWalker{Binary: *caBin, TempDir: *tmp})

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	var ready atomic.Bool
	if *healthAddr != "" {
		go serveProbes(*healthAddr, a, &ready, log)
	}

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		s := <-sig
		// One SIGTERM stops the walk and lets the agent upload what it has
		// and hand the unit back.  A second one is somebody who means it.
		log.Info("signal received; finishing the current unit", "signal", s.String())
		cancel()
		<-sig
		log.Warn("second signal; exiting now")
		os.Exit(130)
	}()

	ready.Store(true)
	if err := a.Run(ctx); err != nil {
		log.Error("agent stopped", "error", err)
		os.Exit(1)
	}
	log.Info("agent stopped", "stats", a.Stats())
}

func parseLabels(s string) map[string]string {
	if s == "" {
		return nil
	}
	out := map[string]string{}
	for _, part := range strings.Split(s, ",") {
		k, v, ok := strings.Cut(strings.TrimSpace(part), "=")
		if ok && k != "" {
			out[k] = v
		}
	}
	return out
}

func serveProbes(addr string, a *agent.Agent, ready *atomic.Bool, log *slog.Logger) {
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok\n"))
	})
	mux.HandleFunc("/readyz", func(w http.ResponseWriter, r *http.Request) {
		if !ready.Load() {
			w.WriteHeader(http.StatusServiceUnavailable)
			return
		}
		w.WriteHeader(http.StatusOK)
	})
	mux.HandleFunc("/stats", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		enc := json.NewEncoder(w)
		enc.SetIndent("", "  ")
		_ = enc.Encode(a.Stats())
	})
	srv := &http.Server{Addr: addr, Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Warn("probe listener stopped", "error", err)
	}
}
