// Command ca-control is the campaign control plane.
//
//	ca-control serve   --state /var/lib/ca-control --listen :8080
//	ca-control create  --state ... --name c1 --group ec --p ... --g ... --h ...
//	ca-control status  --server http://localhost:8080
//
// `serve` is the only long-running mode.  It answers agents, holds the
// corpus, and solves it; everything else here is an operator command that
// talks to a running one, except `create`, which can also write straight
// into a state directory before the server starts.
//
// Deployment shapes this file more than anything else:
//
//   - Configuration is flags with environment defaults, so one container
//     image serves a Kubernetes Deployment (env) and a systemd unit (flags
//     in the unit file) without a config file to template.
//   - SIGTERM drains first and exits second: Kubernetes sends SIGTERM and
//     then waits, and a control plane that dies instantly turns every
//     in-flight unit into a lease that has to time out.
//   - Nothing is written outside the state directory, so the container can
//     run read-only with one volume.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/aburan28/cryptanalysis/orchestrator/api"
	"github.com/aburan28/cryptanalysis/orchestrator/internal/control"
	"github.com/aburan28/cryptanalysis/orchestrator/internal/store"
)

func env(name, def string) string {
	if v := os.Getenv(name); v != "" {
		return v
	}
	return def
}

func envDur(name string, def time.Duration) time.Duration {
	if v := os.Getenv(name); v != "" {
		if d, err := time.ParseDuration(v); err == nil {
			return d
		}
	}
	return def
}

func main() {
	if len(os.Args) < 2 {
		usage()
	}
	var err error
	switch os.Args[1] {
	case "serve":
		err = serve(os.Args[2:])
	case "create":
		err = create(os.Args[2:])
	case "status":
		err = status(os.Args[2:])
	case "version":
		fmt.Printf("{\"version\":%q}\n", api.Version)
	default:
		usage()
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
}

func usage() {
	fmt.Fprint(os.Stderr, `usage: ca-control <command> [flags]

  serve    run the control plane
  create   define a campaign (against a server, or straight into a state dir)
  status   print a running control plane's status as JSON
  version  print the wire protocol version

Every flag can be set from the environment: CA_LISTEN, CA_STATE, CA_TOKEN,
CA_LEASE_TTL, CA_HEARTBEAT, CA_LOG_LEVEL, CA_SERVER.
`)
	os.Exit(2)
}

func logger(level string) *slog.Logger {
	var l slog.Level
	if err := l.UnmarshalText([]byte(level)); err != nil {
		l = slog.LevelInfo
	}
	// JSON to stdout: this runs under systemd's journal and under a
	// Kubernetes log collector, and both of them are happier with one
	// object per line than with a format somebody has to write a parser for.
	return slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: l}))
}

func serve(args []string) error {
	fs := flag.NewFlagSet("serve", flag.ExitOnError)
	listen := fs.String("listen", env("CA_LISTEN", ":8080"), "address to listen on")
	state := fs.String("state", env("CA_STATE", "./state"), "state directory")
	token := fs.String("token", os.Getenv("CA_TOKEN"), "bearer token agents must present")
	tokenFile := fs.String("token-file", env("CA_TOKEN_FILE", ""),
		"read the bearer token from this file (a Kubernetes secret mount)")
	leaseTTL := fs.Duration("lease-ttl", envDur("CA_LEASE_TTL", 90*time.Second), "lease lifetime")
	heartbeat := fs.Duration("heartbeat", envDur("CA_HEARTBEAT", 30*time.Second),
		"heartbeat interval agents are told to use")
	logLevel := fs.String("log-level", env("CA_LOG_LEVEL", "info"), "debug, info, warn or error")
	certFile := fs.String("tls-cert", env("CA_TLS_CERT", ""), "TLS certificate (optional)")
	keyFile := fs.String("tls-key", env("CA_TLS_KEY", ""), "TLS key (optional)")
	shutdown := fs.Duration("shutdown-grace", envDur("CA_SHUTDOWN_GRACE", 20*time.Second),
		"how long to let requests finish after SIGTERM")
	if err := fs.Parse(args); err != nil {
		return err
	}
	log := logger(*logLevel)

	if *tokenFile != "" {
		blob, err := os.ReadFile(*tokenFile)
		if err != nil {
			return fmt.Errorf("reading the token file: %w", err)
		}
		*token = strings.TrimSpace(string(blob))
	}
	if *token == "" {
		// Not fatal: a laptop and the test suite run without one.  Loud,
		// because an open control plane on a network is a fleet anybody can
		// feed points to, and the merger's verification limits the damage
		// but does not make it fine.
		log.Warn("no token set: the control plane is unauthenticated")
	}

	st, err := store.Open(*state)
	if err != nil {
		return err
	}
	defer st.Close()

	srv, err := control.NewServer(st, control.Config{
		LeaseTTL: *leaseTTL, HeartbeatInterval: *heartbeat, Token: *token, Logger: log,
	})
	if err != nil {
		return err
	}

	stop := make(chan struct{})
	go srv.Run(stop)

	httpSrv := &http.Server{
		Addr:    *listen,
		Handler: srv.Handler(),
		// An agent uploading a large corpus over a slow link needs a
		// generous write timeout; the read header timeout is what protects
		// against a client that connects and says nothing.
		ReadHeaderTimeout: 10 * time.Second,
		ReadTimeout:       5 * time.Minute,
		WriteTimeout:      5 * time.Minute,
		IdleTimeout:       120 * time.Second,
		ErrorLog:          slog.NewLogLogger(log.Handler(), slog.LevelWarn),
	}
	ln, err := net.Listen("tcp", *listen)
	if err != nil {
		return err
	}
	log.Info("listening", "addr", ln.Addr().String(), "state", st.Dir(), "tls", *certFile != "")

	errCh := make(chan error, 1)
	go func() {
		if *certFile != "" {
			errCh <- httpSrv.ServeTLS(ln, *certFile, *keyFile)
			return
		}
		errCh <- httpSrv.Serve(ln)
	}()

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	select {
	case err := <-errCh:
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			return err
		}
	case s := <-sig:
		log.Info("signal received; draining", "signal", s.String())
		// Drain first: readyz starts failing, the load balancer stops
		// sending new agents here, and the ones already talking to us finish
		// their requests.  Only then does the listener close.
		srv.Drain(true)
		time.Sleep(time.Second)
		ctx, cancel := context.WithTimeout(context.Background(), *shutdown)
		defer cancel()
		if err := httpSrv.Shutdown(ctx); err != nil {
			log.Warn("graceful shutdown timed out", "error", err)
		}
	}
	close(stop)
	log.Info("stopped")
	return nil
}

func create(args []string) error {
	fs := flag.NewFlagSet("create", flag.ExitOnError)
	server := fs.String("server", env("CA_SERVER", ""),
		"control plane to create the campaign on (empty: write into --state)")
	state := fs.String("state", env("CA_STATE", "./state"), "state directory, when offline")
	token := fs.String("token", os.Getenv("CA_TOKEN"), "bearer token")
	name := fs.String("name", "", "campaign name")
	group := fs.String("group", "ec", "zp or ec")
	p := fs.Uint64("p", 0, "field prime")
	a := fs.Uint64("a", 0, "curve coefficient a")
	b := fs.Uint64("b", 0, "curve coefficient b")
	order := fs.Uint64("order", 0, "order of the subgroup being searched")
	base := fs.String("g", "", "base element (\"123\" or \"x,y\")")
	target := fs.String("h", "", "target element")
	seed := fs.Uint64("seed", 0, "campaign seed (0: the server draws one)")
	r := fs.Uint("r", 0, "adding-walk multipliers (0: default)")
	dpBits := fs.Int("dp-bits", 0, "distinguished-point bits (0: resolve from the order)")
	unitSteps := fs.Uint64("unit-steps", 0, "walk steps per unit (0: resolve)")
	unitWalks := fs.Uint("unit-walks", 0, "concurrent walks per unit (0: the library decides)")
	if err := fs.Parse(args); err != nil {
		return err
	}
	def := api.Campaign{
		Name: *name,
		Group: api.Group{
			Kind: api.GroupKind(*group), P: *p, A: *a, B: *b, Order: *order,
			Base: *base, Target: *target,
		},
		Seed: *seed, R: uint32(*r), DPBits: int32(*dpBits),
		UnitSteps: *unitSteps, UnitWalks: uint32(*unitWalks),
	}
	if *server != "" {
		out, err := api.NewClient(*server, *token).CreateCampaign(context.Background(), def)
		if err != nil {
			return err
		}
		return printJSON(out)
	}
	// Offline: write the campaign into a state directory so that a control
	// plane can be started with its work already defined.  Useful for a
	// Kubernetes init container and for a systemd unit's ExecStartPre.
	st, err := store.Open(*state)
	if err != nil {
		return err
	}
	defer st.Close()
	srv, err := control.NewServer(st, control.Config{})
	if err != nil {
		return err
	}
	out, err := srv.CreateCampaign(def)
	if err != nil {
		return err
	}
	return printJSON(out)
}

func status(args []string) error {
	fs := flag.NewFlagSet("status", flag.ExitOnError)
	server := fs.String("server", env("CA_SERVER", "http://localhost:8080"), "control plane")
	token := fs.String("token", os.Getenv("CA_TOKEN"), "bearer token")
	agents := fs.Bool("agents", false, "include the agent list")
	watch := fs.Duration("watch", 0, "repeat every interval (0: once)")
	if err := fs.Parse(args); err != nil {
		return err
	}
	c := api.NewClient(*server, *token)
	for {
		st, err := c.Status(context.Background(), *agents)
		if err != nil {
			return err
		}
		if err := printJSON(st); err != nil {
			return err
		}
		if *watch <= 0 {
			return nil
		}
		time.Sleep(*watch)
	}
}

func printJSON(v any) error {
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	return enc.Encode(v)
}

var _ = strconv.Itoa
