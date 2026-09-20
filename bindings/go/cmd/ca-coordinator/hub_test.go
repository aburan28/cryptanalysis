package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	ca "github.com/aburan28/cryptanalysis/bindings/go"
)

// A small instance with a planted secret, so every run is checkable.
func testFixture(t *testing.T, secret uint64) (*ca.Ctx, uint64) {
	t.Helper()
	g, err := ca.NewZp(2000303, 1000151)
	if err != nil {
		t.Fatalf("group: %v", err)
	}
	t.Cleanup(g.Close)
	gen, err := g.FindGenerator(1)
	if err != nil {
		t.Fatalf("generator: %v", err)
	}
	x := secret % g.Order()
	h, err := g.Mul(gen, x)
	if err != nil {
		t.Fatalf("mul: %v", err)
	}
	job, err := ca.NewJob(ca.JobParams{
		Kind: ca.GroupZp, P: g.P(), Order: g.Order(),
		Base: gen, Target: h, DPBits: 5, Branches: 16, UnitSize: 32, Seed: 7,
	})
	if err != nil {
		t.Fatalf("job: %v", err)
	}
	ctx, err := ca.OpenCtx(job)
	if err != nil {
		t.Fatalf("ctx: %v", err)
	}
	t.Cleanup(ctx.Close)
	return ctx, x
}

func newTestHub(t *testing.T, ctx *ca.Ctx, cfg Config) (*Hub, *ca.State, *httptest.Server) {
	t.Helper()
	state, err := ca.NewState(ctx)
	if err != nil {
		t.Fatalf("state: %v", err)
	}
	t.Cleanup(state.Close)
	if cfg.PushInterval == 0 {
		cfg.PushInterval = 20 * time.Millisecond
	}
	hub := NewHub(ctx, state, cfg)
	srv := httptest.NewServer(hub.Handler())
	t.Cleanup(srv.Close)
	return hub, state, srv
}

func get(t *testing.T, url, token string) (int, string) {
	t.Helper()
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		t.Fatal(err)
	}
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	return resp.StatusCode, string(body)
}

// The token is access control: it gates reads and writes alike, because
// an unauthenticated stranger could otherwise flood the log with
// verifiable but useless check-ins.  /healthz stays outside it, because
// a load balancer carries no credential.
func TestAuthAndRoutes(t *testing.T) {
	ctx, _ := testFixture(t, 4242)
	_, _, srv := newTestHub(t, ctx, Config{Token: "s3cret"})

	if code, body := get(t, srv.URL+"/healthz", ""); code != http.StatusOK || !strings.Contains(body, "true") {
		t.Errorf("healthz needs no token: %d %s", code, body)
	}
	for _, tok := range []string{"", "wrong", "s3cre", "s3crett"} {
		if code, _ := get(t, srv.URL+"/v1/job", tok); code != http.StatusUnauthorized {
			t.Errorf("token %q was accepted: %d", tok, code)
		}
	}
	code, body := get(t, srv.URL+"/v1/job", "s3cret")
	if code != http.StatusOK {
		t.Fatalf("job: %d %s", code, body)
	}
	// An agent configured with only a URL gets a usable job from it.
	job, err := ca.ParseJob(body)
	if err != nil {
		t.Fatalf("served job does not parse: %v", err)
	}
	if job.ID() != ctx.Job().ID() {
		t.Errorf("served the wrong job: %x != %x", job.ID(), ctx.Job().ID())
	}

	code, body = get(t, srv.URL+"/v1/status", "s3cret")
	if code != http.StatusOK {
		t.Fatalf("status: %d %s", code, body)
	}
	var status struct {
		JobID string `json:"job_id"`
		Steps uint64 `json:"steps"`
		Hub   Stats  `json:"hub"`
	}
	if err := json.Unmarshal([]byte(body), &status); err != nil {
		t.Fatalf("status is not JSON: %v (%s)", err, body)
	}
	if status.JobID != ctx.Job().IDString() {
		t.Errorf("status names the wrong job: %s", status.JobID)
	}
	if status.Hub.Unauthorized < 4 {
		t.Errorf("refusals were not counted: %+v", status.Hub)
	}

	if code, body := get(t, srv.URL+"/metrics", "s3cret"); code != http.StatusOK ||
		!strings.Contains(body, "carho_agents_connected") {
		t.Errorf("metrics: %d %s", code, body)
	}
	// A channel without the upgrade header is a 426, not a hang.
	if code, _ := get(t, srv.URL+"/v1/channel", "s3cret"); code != http.StatusUpgradeRequired {
		t.Errorf("channel without an upgrade: %d", code)
	}
	if code, _ := get(t, srv.URL+"/nope", "s3cret"); code != http.StatusNotFound {
		t.Errorf("unknown route: %d", code)
	}
}

// The pollable fallback carries the same facts as the channel.
func TestSyncRoundTrip(t *testing.T) {
	ctx, _ := testFixture(t, 31337)
	_, hubState, srv := newTestHub(t, ctx, Config{})

	mine, err := ca.NewState(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer mine.Close()
	if _, err := ca.RunLane(ctx, mine, ca.LaneParams{Peer: "a.0", MaxWalkers: 16, CheckinEvery: 4}); err != nil {
		t.Fatalf("lane: %v", err)
	}

	var body strings.Builder
	body.WriteString("vv" + mine.VersionVector().String() + "\n")
	for _, l := range mine.DeltaFrom(ca.VersionVector{}) {
		body.WriteString(l + "\n")
	}
	resp, err := http.Post(srv.URL+"/v1/sync", "text/plain", strings.NewReader(body.String()))
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("sync: %d", resp.StatusCode)
	}
	if hubState.LogLen() != mine.LogLen() {
		t.Errorf("the hub merged %d of %d check-ins", hubState.LogLen(), mine.LogLen())
	}
	if p := hubState.Progress(120); p.RejectedDPs != 0 {
		t.Errorf("the hub rejected %d genuine points", p.RejectedDPs)
	}

	// A second caller, knowing nothing, is owed everything the hub has.
	theirs, err := ca.NewState(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer theirs.Close()
	resp2, err := http.Post(srv.URL+"/v1/sync", "text/plain", strings.NewReader("vv\n"))
	if err != nil {
		t.Fatal(err)
	}
	defer resp2.Body.Close()
	out, _ := io.ReadAll(resp2.Body)
	got := 0
	for _, line := range strings.Split(string(out), "\n") {
		if !strings.HasPrefix(line, "ci ") {
			continue
		}
		if _, err := theirs.ApplyLine(line); err != nil {
			t.Errorf("the hub returned a line we refused: %v", err)
			continue
		}
		got++
	}
	if got != mine.LogLen() {
		t.Errorf("owed %d check-ins, got %d", mine.LogLen(), got)
	}
}

// A check-in for another job is refused, counted, and cannot reach the
// state.
func TestForeignJobRefused(t *testing.T) {
	ctx, _ := testFixture(t, 11)
	hub, hubState, srv := newTestHub(t, ctx, Config{})

	other, _ := testFixture(t, 12)
	mine, err := ca.NewState(other)
	if err != nil {
		t.Fatal(err)
	}
	defer mine.Close()
	if _, err := ca.RunLane(other, mine, ca.LaneParams{Peer: "x.0", MaxWalkers: 8, CheckinEvery: 4}); err != nil {
		t.Fatalf("lane: %v", err)
	}
	var body strings.Builder
	for _, l := range mine.DeltaFrom(ca.VersionVector{}) {
		body.WriteString(l + "\n")
	}
	resp, err := http.Post(srv.URL+"/v1/sync", "text/plain", strings.NewReader(body.String()))
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if hubState.LogLen() != 0 {
		t.Errorf("a foreign job's check-ins were merged: %d", hubState.LogLen())
	}
	if hub.Stats().Rejected == 0 {
		t.Error("refusals were not counted")
	}
}

// The durability hook sees every accepted check-in, and replaying the
// file it writes reproduces the state -- which is what makes a restarted
// pod resume rather than start empty.
func TestCheckinLogRoundTrip(t *testing.T) {
	ctx, _ := testFixture(t, 555)
	path := filepath.Join(t.TempDir(), "sub", "checkins.log")
	sink, err := openCheckinLog(path)
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	var mu sync.Mutex
	seen := 0
	_, hubState, srv := newTestHub(t, ctx, Config{OnCheckIn: func(line string) {
		mu.Lock()
		seen++
		mu.Unlock()
		sink.Append(line)
	}})

	mine, err := ca.NewState(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer mine.Close()
	if _, err := ca.RunLane(ctx, mine, ca.LaneParams{Peer: "a.0", MaxWalkers: 16, CheckinEvery: 4}); err != nil {
		t.Fatalf("lane: %v", err)
	}
	var body strings.Builder
	for _, l := range mine.DeltaFrom(ca.VersionVector{}) {
		body.WriteString(l + "\n")
	}
	resp, err := http.Post(srv.URL+"/v1/sync", "text/plain", strings.NewReader(body.String()))
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if err := sink.Close(); err != nil {
		t.Fatalf("close: %v", err)
	}

	mu.Lock()
	got := seen
	mu.Unlock()
	if got == 0 {
		t.Fatal("the durability hook never ran")
	}
	if fi, err := os.Stat(path); err != nil || fi.Size() == 0 {
		t.Fatalf("nothing was written: %v", err)
	}

	// A replacement starts from the file.
	reopened, err := openCheckinLog(path)
	if err != nil {
		t.Fatal(err)
	}
	defer reopened.Close()
	fresh, err := ca.NewState(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer fresh.Close()
	merged, rejected, err := reopened.Replay(fresh)
	if err != nil {
		t.Fatalf("replay: %v", err)
	}
	if rejected != 0 {
		t.Errorf("replay rejected %d entries it had written itself", rejected)
	}
	if merged != hubState.LogLen() {
		t.Errorf("replayed %d of %d check-ins", merged, hubState.LogLen())
	}
	// Replaying twice is a no-op: the merge is idempotent, which is why
	// a flat append-only file is enough.
	again, _, err := reopened.Replay(fresh)
	if err != nil {
		t.Fatal(err)
	}
	if again != 0 {
		t.Errorf("a second replay merged %d entries", again)
	}
}

// The property the whole service exists for: agents that never listen on
// anything, each dialling out, converge -- and the solution reaches the
// agent that did not find it, over a socket that agent opened.
func TestAgentsConvergeThroughTheHub(t *testing.T) {
	if testing.Short() {
		t.Skip("walks a real instance")
	}
	ctx, secret := testFixture(t, 246813)
	hub, _, srv := newTestHub(t, ctx, Config{Token: "tok", PushInterval: 20 * time.Millisecond})

	type agent struct {
		name  string
		state *ca.State
		conn  *ca.Agent
	}
	agents := make([]*agent, 2)
	for i := range agents {
		st, err := ca.NewState(ctx)
		if err != nil {
			t.Fatal(err)
		}
		defer st.Close()
		name := fmt.Sprintf("a%d", i)
		conn, err := ca.Dial(srv.URL, "tok", name, ctx, st)
		if err != nil {
			t.Fatalf("dial: %v", err)
		}
		defer conn.Stop()
		agents[i] = &agent{name: name, state: st, conn: conn}
	}

	var wg sync.WaitGroup
	done := make(chan struct{})
	for i, a := range agents {
		wg.Add(1)
		go func(i int, a *agent) {
			defer wg.Done()
			sent := 0
			for {
				select {
				case <-done:
					return
				default:
				}
				if _, ok := a.state.Solution(); ok {
					return
				}
				// Walk a little, then ship whatever the lane added to
				// the log.  (The lane merges its own check-ins first,
				// so what is in the log is already a fact.)
				if _, err := ca.RunLane(ctx, a.state, ca.LaneParams{
					Peer: a.name + ".0", MaxWalkers: 8, CheckinEvery: 4, ClaimWindow: 1,
				}); err != nil {
					t.Errorf("lane: %v", err)
					return
				}
				for ; sent < a.state.LogLen(); sent++ {
					if e, ok := a.state.LogAt(sent); ok {
						if err := a.conn.PublishLine(e.Line); err != nil {
							t.Errorf("publish: %v", err)
							return
						}
					}
				}
				time.Sleep(10 * time.Millisecond)
			}
		}(i, a)
	}

	deadline := time.After(60 * time.Second)
	ok := false
	for !ok {
		select {
		case <-deadline:
			close(done)
			wg.Wait()
			t.Fatalf("no convergence; hub: %+v", hub.Stats())
		case <-time.After(100 * time.Millisecond):
		}
		ok = true
		for _, a := range agents {
			if _, solved := a.state.Solution(); !solved {
				ok = false
			}
		}
	}
	close(done)
	wg.Wait()

	for _, a := range agents {
		x, solved := a.state.Solution()
		if !solved || x != secret {
			t.Errorf("%s: solved=%v x=%d, want %d", a.name, solved, x, secret)
		}
		s := a.conn.Stats()
		if s.Connects == 0 || s.Sent == 0 {
			t.Errorf("%s never used its connection: %+v", a.name, s)
		}
		if s.Rejected != 0 {
			t.Errorf("%s rejected %d records from the hub", a.name, s.Rejected)
		}
	}
	// At least one agent learned something it did not walk itself: that
	// is the reverse channel doing its job.
	if agents[0].conn.Stats().Received == 0 && agents[1].conn.Stats().Received == 0 {
		t.Error("nothing came back down either channel")
	}
	hs := hub.Stats()
	if hs.Accepted == 0 || hs.Pushed == 0 {
		t.Errorf("the hub merged or pushed nothing: %+v", hs)
	}
	if hs.Rejected != 0 {
		t.Errorf("the hub rejected %d genuine records", hs.Rejected)
	}
}
