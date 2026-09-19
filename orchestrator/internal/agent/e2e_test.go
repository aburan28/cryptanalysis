package agent_test

import (
	"context"
	"encoding/json"
	"io"
	"log/slog"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"sync"
	"testing"
	"time"

	"github.com/aburan28/cryptanalysis/orchestrator/api"
	"github.com/aburan28/cryptanalysis/orchestrator/internal/agent"
	"github.com/aburan28/cryptanalysis/orchestrator/internal/control"
	"github.com/aburan28/cryptanalysis/orchestrator/internal/store"
)

// The end-to-end test this whole layer exists to pass: several agents, each
// a separate goroutine running the real `ca` binary in a separate process,
// leasing units from one control plane, and between them producing a
// collision that solves an instance none of them could see.
//
// It is the only test that proves the thing the design claims -- that the
// parallelism is van Oorschot-Wiener parallelism and not N independent
// searches -- because the unit budget is far below the expected work of one
// search, so no single agent can solve it alone.

func caBinary(t *testing.T) string {
	t.Helper()
	if p := os.Getenv("CA_BIN"); p != "" {
		return p
	}
	p, err := filepath.Abs(filepath.Join("..", "..", "..", "build", "ca"))
	if err != nil || fileMissing(p) {
		t.Skipf("no ca binary at %s (build it with `make lib`, or set CA_BIN)", p)
	}
	return p
}

func fileMissing(p string) bool {
	_, err := os.Stat(p)
	return err != nil
}

func quiet() *slog.Logger { return slog.New(slog.NewTextHandler(io.Discard, nil)) }

type instance struct {
	P, Order uint64
	G, H     string
	X        uint64
}

func generate(t *testing.T, ca string) instance {
	t.Helper()
	out, err := exec.Command(ca, "gen", "--group", "zp", "--p", "2000000579",
		"--order", "1000000289", "--seed", "21").Output()
	if err != nil {
		t.Fatalf("ca gen: %v", err)
	}
	var g struct {
		P     uint64 `json:"p"`
		Order uint64 `json:"order"`
		G     string `json:"g"`
		H     string `json:"h"`
		X     uint64 `json:"x"`
	}
	if err := json.Unmarshal(out, &g); err != nil {
		t.Fatal(err)
	}
	return instance{P: g.P, Order: g.Order, G: g.G, H: g.H, X: g.X}
}

func TestAFleetSolvesAnInstanceNoAgentCouldSolveAlone(t *testing.T) {
	ca := caBinary(t)
	inst := generate(t, ca)

	st, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer st.Close()
	srv, err := control.NewServer(st, control.Config{
		LeaseTTL: 30 * time.Second, HeartbeatInterval: 2 * time.Second,
		Token: "test-token", Logger: quiet(),
	})
	if err != nil {
		t.Fatal(err)
	}
	stop := make(chan struct{})
	go srv.Run(stop)
	defer close(stop)

	http := httptest.NewServer(srv.Handler())
	defer http.Close()

	// The unit budget is about a twentieth of the expected search, so an
	// agent that ran only its own units could not expect to collide with
	// itself: the answer has to come from the merged corpus.
	def, err := srv.CreateCampaign(api.Campaign{
		Name:      "e2e",
		Group:     api.Group{Kind: api.GroupZp, P: inst.P, Order: inst.Order, Base: inst.G, Target: inst.H},
		Seed:      1234567,
		R:         32,
		DPBits:    6,
		UnitSteps: 2000,
		UnitWalks: 16,
	})
	if err != nil {
		t.Fatal(err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
	defer cancel()

	const fleet = 4
	var wg sync.WaitGroup
	for i := 0; i < fleet; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			a := agent.New(agent.Config{
				Server: http.URL, Token: "test-token", ID: "agent-" + strconv.Itoa(i),
				IdleBackoff: 100 * time.Millisecond, Logger: quiet(),
			}, api.NewClient(http.URL, "test-token"),
				&agent.CLIWalker{Binary: ca, TempDir: t.TempDir()})
			if err := a.Run(ctx); err != nil {
				t.Errorf("agent %d: %v", i, err)
			}
		}(i)
	}

	// Wait for the campaign to be solved, then stop the fleet.
	deadline := time.Now().Add(80 * time.Second)
	var final api.CampaignStatus
	for time.Now().Before(deadline) {
		final = srv.Status(false).Campaigns[0]
		if final.Solved {
			break
		}
		time.Sleep(100 * time.Millisecond)
	}
	cancel()
	wg.Wait()

	if !final.Solved {
		t.Fatalf("not solved in time: %+v", final)
	}
	if final.X != inst.X {
		t.Fatalf("solved x = %d, planted %d", final.X, inst.X)
	}
	if final.Rejected != 0 {
		t.Fatalf("the server rejected %d points from its own fleet", final.Rejected)
	}
	if final.Units.Done < 2 {
		t.Fatalf("only %d units finished; the answer did not come from merged work",
			final.Units.Done)
	}
	if final.Stored == 0 || final.Points == 0 {
		t.Fatalf("no corpus: %+v", final)
	}
	if final.Campaign.Fingerprint != def.Fingerprint {
		t.Fatal("the campaign changed under the fleet")
	}
	t.Logf("solved x=%d after %d units, %d points (%d stored), %d steps",
		final.X, final.Units.Done, final.Points, final.Stored, final.Steps)
}

// An agent handed a lease it does not own any more must stop rather than
// spend a core on work the server will refuse.
func TestAnAgentStopsWhenItsLeaseIsTaken(t *testing.T) {
	ca := caBinary(t)
	inst := generate(t, ca)

	st, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer st.Close()
	// A lease that expires almost immediately, so the sweeper takes the unit
	// away while the agent is still walking it.
	srv, err := control.NewServer(st, control.Config{
		LeaseTTL: time.Second, HeartbeatInterval: 200 * time.Millisecond, Logger: quiet(),
	})
	if err != nil {
		t.Fatal(err)
	}
	stop := make(chan struct{})
	go srv.Run(stop)
	defer close(stop)
	http := httptest.NewServer(srv.Handler())
	defer http.Close()

	if _, err := srv.CreateCampaign(api.Campaign{
		Name:  "steal",
		Group: api.Group{Kind: api.GroupZp, P: inst.P, Order: inst.Order, Base: inst.G, Target: inst.H},
		Seed:  42, R: 32, DPBits: 20,
		UnitSteps: 200_000_000, // long enough that the lease expires first
		UnitWalks: 16,
	}); err != nil {
		t.Fatal(err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	a := agent.New(agent.Config{
		Server: http.URL, ID: "slowpoke", IdleBackoff: 100 * time.Millisecond,
		MaxUnits: 1, Logger: quiet(),
	}, api.NewClient(http.URL, ""), &agent.CLIWalker{Binary: ca, TempDir: t.TempDir()})

	done := make(chan error, 1)
	go func() { done <- a.Run(ctx) }()

	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("agent returned %v", err)
		}
	case <-ctx.Done():
		t.Fatal("the agent kept walking a unit it had lost")
	}
	// It stopped early: the unit's budget was 200 M steps, which takes
	// minutes, and the agent gave up within the test's timeout.
	if s := a.Stats(); s.Units != 1 {
		t.Fatalf("expected one attempted unit, got %+v", s)
	}
}
