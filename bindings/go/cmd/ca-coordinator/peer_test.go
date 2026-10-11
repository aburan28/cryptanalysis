package main

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	ca "github.com/aburan28/cryptanalysis/bindings/go"
)

// newPeeredHub builds a hub that gossips with the given URLs.
func newPeeredHub(t *testing.T, ctx *ca.Ctx, name string, peers ...string) (*Hub, *ca.State, *httptest.Server) {
	t.Helper()
	state, err := ca.NewState(ctx)
	if err != nil {
		t.Fatalf("state: %v", err)
	}
	t.Cleanup(state.Close)
	ps := make([]Peer, 0, len(peers))
	for i, u := range peers {
		ps = append(ps, Peer{Name: fmt.Sprintf("%s-peer%d", name, i), URL: u})
	}
	h := NewHub(ctx, state, &Config{
		PeerInterval: 10 * time.Millisecond,
		PeerTimeout:  2 * time.Second,
		Peers:        ps,
	})
	srv := httptest.NewServer(h.Handler())
	t.Cleanup(srv.Close)
	return h, state, srv
}

// Two hubs that have never heard of each other's agents converge, and the
// federation is what carries the records: no agent talks to both.
func TestHubsConvergeByPeering(t *testing.T) {
	ctx, _ := testFixture(t, 31337)

	// A holds the work; B starts empty and peers with A.
	hubA, stateA, srvA := newPeeredHub(t, ctx, "a")
	_ = hubA
	if _, err := ca.RunLane(ctx, stateA, ca.LaneParams{Peer: "a.0", MaxWalkers: 16, CheckinEvery: 2}); err != nil {
		t.Fatalf("lane: %v", err)
	}
	if stateA.LogLen() == 0 {
		t.Fatal("no check-ins to federate")
	}

	hubB, stateB, _ := newPeeredHub(t, ctx, "b", srvA.URL)
	pctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	hubB.StartPeering(pctx)

	// The first exchange only greets; the second carries the records.
	deadline := time.Now().Add(10 * time.Second)
	for stateB.LogLen() < stateA.LogLen() && time.Now().Before(deadline) {
		time.Sleep(20 * time.Millisecond)
	}
	if stateB.LogLen() != stateA.LogLen() {
		t.Fatalf("B holds %d of A's %d check-ins", stateB.LogLen(), stateA.LogLen())
	}

	st := hubB.PeerStats()
	if len(st) != 1 {
		t.Fatalf("peer stats: %d rows, want 1", len(st))
	}
	if st[0].CheckinsIn == 0 || st[0].DPsAccepted == 0 {
		t.Errorf("peer row shows nothing taken: %+v", st[0])
	}
	if st[0].DPsRejected != 0 {
		t.Errorf("a peer's own records were rejected: %+v", st[0])
	}
}

// Gossip is two-way even though each exchange is one request: B pushes what
// it has to A as well as taking A's.
func TestPeeringPushesAsWellAsPulls(t *testing.T) {
	ctx, _ := testFixture(t, 4242)
	_, stateA, srvA := newPeeredHub(t, ctx, "a")
	hubB, stateB, _ := newPeeredHub(t, ctx, "b", srvA.URL)

	if _, err := ca.RunLane(ctx, stateB, ca.LaneParams{Peer: "b.0", MaxWalkers: 16, CheckinEvery: 2}); err != nil {
		t.Fatalf("lane: %v", err)
	}
	want := stateB.LogLen()
	if want == 0 {
		t.Fatal("no check-ins to federate")
	}

	pctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	hubB.StartPeering(pctx)

	deadline := time.Now().Add(10 * time.Second)
	for stateA.LogLen() < want && time.Now().Before(deadline) {
		time.Sleep(20 * time.Millisecond)
	}
	if stateA.LogLen() != want {
		t.Fatalf("A holds %d of B's %d check-ins", stateA.LogLen(), want)
	}
	if st := hubB.PeerStats(); st[0].CheckinsOut == 0 {
		t.Errorf("nothing was pushed: %+v", st[0])
	}
}

// A peer serving a different job is refused record by record, exactly as a
// lying agent would be: peering grants no authority.
func TestPeeringRefusesAForeignJob(t *testing.T) {
	ctxA, _ := testFixture(t, 111)
	ctxB, _ := testFixture(t, 222)
	if ctxA.Job().ID() == ctxB.Job().ID() {
		t.Skip("fixtures collided")
	}

	_, stateA, srvA := newPeeredHub(t, ctxA, "a")
	if _, err := ca.RunLane(ctxA, stateA, ca.LaneParams{Peer: "a.0", MaxWalkers: 16, CheckinEvery: 2}); err != nil {
		t.Fatalf("lane: %v", err)
	}
	if stateA.LogLen() == 0 {
		t.Fatal("no check-ins to offer")
	}

	hubB, stateB, _ := newPeeredHub(t, ctxB, "b", srvA.URL)
	pctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	hubB.StartPeering(pctx)

	deadline := time.Now().Add(3 * time.Second)
	for hubB.PeerStats()[0].Syncs < 3 && time.Now().Before(deadline) {
		time.Sleep(20 * time.Millisecond)
	}
	if n := stateB.LogLen(); n != 0 {
		t.Errorf("B merged %d records from a hub running a different job", n)
	}
}

// An unreachable peer is counted and retried, and never stops the hub.
func TestUnreachablePeerIsCountedNotFatal(t *testing.T) {
	ctx, _ := testFixture(t, 99)
	dead := httptest.NewServer(nil)
	url := dead.URL
	dead.Close() // nothing listens there now

	hub, state, _ := newPeeredHub(t, ctx, "a", url)
	pctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	hub.StartPeering(pctx)

	deadline := time.Now().Add(3 * time.Second)
	for hub.PeerStats()[0].Errors < 2 && time.Now().Before(deadline) {
		time.Sleep(20 * time.Millisecond)
	}
	st := hub.PeerStats()[0]
	if st.Errors < 2 {
		t.Fatalf("a dead peer produced %d errors, want retries", st.Errors)
	}
	if st.LastError == "" {
		t.Error("no error recorded for operators to see")
	}
	if state.LogLen() != 0 {
		t.Error("a dead peer somehow contributed records")
	}
}

// name=url and a bare url both parse; anything that would silently not
// federate is refused at startup rather than at 3am.
func TestParsePeers(t *testing.T) {
	ps, err := parsePeers([]string{"eu=http://eu:8080", "http://us:8080/"}, "tok")
	if err != nil {
		t.Fatal(err)
	}
	if len(ps) != 2 || ps[0].Name != "eu" || ps[0].URL != "http://eu:8080" {
		t.Fatalf("parsed %+v", ps)
	}
	if ps[1].Name != "http://us:8080/" {
		t.Errorf("a bare url should name itself, got %q", ps[1].Name)
	}
	if ps[0].Token != "tok" {
		t.Error("peers should inherit the hub's token")
	}
	for _, bad := range []string{"eu=ftp://x", "not-a-url", "eu="} {
		if _, err := parsePeers([]string{bad}, ""); err == nil {
			t.Errorf("%q was accepted", bad)
		}
	}
	if _, err := parsePeers([]string{"http://x:1", "a=http://x:1"}, ""); err == nil {
		t.Error("the same peer listed twice was accepted")
	}
}

// The peer that matters is not the one that is down -- that errors at once
// -- but the one that accepts the connection and then says nothing.
// Unbounded, it holds its loop forever: never retried, never counted, and
// so invisible to whoever is watching the fleet.
func TestHungPeerIsAbandonedAndCounted(t *testing.T) {
	ctx, _ := testFixture(t, 1234)

	release := make(chan struct{})
	hung := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		select {
		case <-release:
		case <-r.Context().Done():
		}
	}))
	t.Cleanup(func() {
		close(release)
		hung.Close()
	})

	state, err := ca.NewState(ctx)
	if err != nil {
		t.Fatalf("state: %v", err)
	}
	t.Cleanup(state.Close)
	hub := NewHub(ctx, state, &Config{
		PeerInterval: 10 * time.Millisecond,
		PeerTimeout:  150 * time.Millisecond,
		Peers:        []Peer{{Name: "hung", URL: hung.URL}},
	})
	pctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	hub.StartPeering(pctx)

	// Two errors means it gave up on the first exchange and came back for
	// another: the retry the docs promise.
	deadline := time.Now().Add(5 * time.Second)
	for hub.PeerStats()[0].Errors < 2 && time.Now().Before(deadline) {
		time.Sleep(20 * time.Millisecond)
	}
	st := hub.PeerStats()[0]
	if st.Errors < 2 {
		t.Fatalf("a hung peer produced %d errors in 5s; the loop is stuck", st.Errors)
	}
	if st.LastError == "" {
		t.Error("nothing recorded for an operator to see")
	}
}

// A hub told which shard it is notices records meant for another one.
// This is the only warning of a mistake that is otherwise silent and
// expensive: agents disagreeing about the URL order send the two halves
// of a collision to different hubs, and everything still looks healthy.
func TestMisroutedCheckinsAreCounted(t *testing.T) {
	ctx, _ := testFixture(t, 555)
	mine := 1
	state, err := ca.NewState(ctx)
	if err != nil {
		t.Fatalf("state: %v", err)
	}
	t.Cleanup(state.Close)
	hub := NewHub(ctx, state, &Config{Shard: &mine})

	src, err := ca.NewState(ctx)
	if err != nil {
		t.Fatalf("state: %v", err)
	}
	t.Cleanup(src.Close)
	if _, err := ca.RunLane(ctx, src, ca.LaneParams{Peer: "a.0#1", MaxWalkers: 8, CheckinEvery: 2}); err != nil {
		t.Fatalf("lane: %v", err)
	}
	if _, err := ca.RunLane(ctx, src, ca.LaneParams{Peer: "b.0#3", MaxWalkers: 8, CheckinEvery: 2}); err != nil {
		t.Fatalf("lane: %v", err)
	}

	want := 0
	for i := 0; i < src.LogLen(); i++ {
		e, ok := src.LogAt(i)
		if !ok {
			continue
		}
		if checkinShard(e.Line) != mine {
			want++
		}
		hub.absorb(e.Line)
	}
	if want == 0 {
		t.Skip("the fixture produced nothing for the other shard")
	}
	if got := hub.Stats().Misrouted; got != int64(want) {
		t.Errorf("counted %d misrouted, want %d", got, want)
	}
	// Kept, not refused: a configuration mistake must not cost work.
	if state.LogLen() != src.LogLen() {
		t.Errorf("hub holds %d of %d records; misrouted ones were dropped",
			state.LogLen(), src.LogLen())
	}
}

func TestCheckinShardReadsThePeerName(t *testing.T) {
	cases := map[string]int{
		"ci 1 lane#7 3 4 U: D: S:-": 7,
		"ci 1 lane 3 4 U: D: S:-":   -1,
		"ci 1 lane#x 3 4":           -1,
		"ci 1 a.b.c#0 1 2":          0,
		"short":                     -1,
	}
	for line, want := range cases {
		if got := checkinShard(line); got != want {
			t.Errorf("checkinShard(%q) = %d, want %d", line, got, want)
		}
	}
}
