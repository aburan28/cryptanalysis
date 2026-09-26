package main

import (
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Finding 6: an unauthenticated hub must be a deliberate, loud choice.  The
// startup policy is:
//
//   - no token, no -allow-anonymous  => refuse to start (error)
//   - no token, -allow-anonymous     => start, warn prominently
//   - token set                      => start, authenticated
func TestAuthDecision(t *testing.T) {
	cases := []struct {
		name                        string
		token                       string
		requireTk, allowAnon, insec bool
		wantAnon, wantWarn, wantErr bool
		warnHas                     string
	}{
		{name: "no token, no flag: refused", wantErr: true},
		{name: "no token, allow-anonymous: starts with warning",
			allowAnon: true, wantAnon: true, wantWarn: true, warnHas: "-allow-anonymous"},
		{name: "no token, insecure alias: starts with warning",
			insec: true, wantAnon: true, wantWarn: true, warnHas: "WITHOUT AUTHENTICATION"},
		{name: "token set: starts authenticated", token: "s3cret"},
		{name: "token set, allow-anonymous: token wins, warns",
			token: "s3cret", allowAnon: true, wantWarn: true, warnHas: "ignored"},
		{name: "require-token + allow-anonymous: contradictory",
			requireTk: true, allowAnon: true, wantErr: true},
		{name: "require-token alone, token set: starts", token: "s3cret", requireTk: true},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			anon, warn, err := authDecision(c.token, c.requireTk, c.allowAnon, c.insec)
			if (err != nil) != c.wantErr {
				t.Fatalf("err = %v, wantErr = %v", err, c.wantErr)
			}
			if err != nil {
				return
			}
			if anon != c.wantAnon {
				t.Errorf("anon = %v, want %v", anon, c.wantAnon)
			}
			if (warn != "") != c.wantWarn {
				t.Errorf("warn = %q, wantWarn = %v", warn, c.wantWarn)
			}
			if c.warnHas != "" && !strings.Contains(warn, c.warnHas) {
				t.Errorf("warn = %q, want it to contain %q", warn, c.warnHas)
			}
		})
	}
}

// The refusal path is exercised end to end through run(), which returns
// before it ever binds a socket, so no server has to be torn down.
func TestRunRefusesWithoutToken(t *testing.T) {
	ctx, _ := testFixture(t, 4242)
	dir := t.TempDir()
	jobPath := filepath.Join(dir, "job.txt")
	if err := os.WriteFile(jobPath, []byte(ctx.Job().String()+"\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	log := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))

	// No token, no -allow-anonymous: refuse, exit 2.
	code, err := run(&options{jobPath: jobPath, listen: "127.0.0.1:0"}, log)
	if err == nil || code != 2 {
		t.Fatalf("no-token start: code %d err %v; want code 2 and an error", code, err)
	}
	if !strings.Contains(err.Error(), "token") {
		t.Errorf("error should mention the missing token: %v", err)
	}

	// Contradictory flags: also refused.
	code, err = run(&options{jobPath: jobPath, listen: "127.0.0.1:0", requireTk: true, allowAnon: true}, log)
	if err == nil || code != 2 {
		t.Fatalf("contradictory flags: code %d err %v; want code 2 and an error", code, err)
	}
}
