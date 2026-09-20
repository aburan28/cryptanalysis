package control

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"os"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/aburan28/cryptanalysis/orchestrator/api"
	"github.com/aburan28/cryptanalysis/orchestrator/internal/dlog"
	"github.com/aburan28/cryptanalysis/orchestrator/internal/store"
)

// A quiet logger: these tests exercise failure paths on purpose and their
// output is not what a reader of `go test` is looking for.
func quiet() *slog.Logger {
	return slog.New(slog.NewTextHandler(io.Discard, nil))
}

type fakeClock struct{ t time.Time }

func (c *fakeClock) now() time.Time      { return c.t }
func (c *fakeClock) add(d time.Duration) { c.t = c.t.Add(d) }

func testServer(t *testing.T) (*Server, *fakeClock, *store.Store) {
	t.Helper()
	st, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { st.Close() })
	clock := &fakeClock{t: time.Unix(1700000000, 0).UTC()}
	s, err := NewServer(st, Config{
		LeaseTTL: 90 * time.Second, HeartbeatInterval: 30 * time.Second,
		Now: clock.now, Logger: quiet(),
	})
	if err != nil {
		t.Fatal(err)
	}
	return s, clock, st
}

// A small real instance: Z_p^* with a prime-order subgroup, and a target
// whose logarithm the test knows.
func testCampaign(t *testing.T, s *Server, name string) api.Campaign {
	t.Helper()
	const p, order = 2000000579, 1000000289
	g, err := dlog.NewGroup(dlog.Zp, p, 0, 0, order)
	if err != nil {
		t.Fatal(err)
	}
	// 3 generates the order-n subgroup after squaring: (Z/pZ)^* has order
	// 2n here, so g^2 lands in the subgroup.
	base := g.ScalarMul(dlog.Point{X: 3}, 2)
	target := g.ScalarMul(base, 424242)
	def, err := s.CreateCampaign(api.Campaign{
		Name: name,
		Group: api.Group{Kind: api.GroupZp, P: p, Order: order,
			Base: g.String(base), Target: g.String(target)},
		Seed: 99, R: 32, DPBits: 6, UnitSteps: 10000,
	})
	if err != nil {
		t.Fatal(err)
	}
	return def
}

func TestCampaignResolutionFillsTheFieldsAnAgentMustNotChoose(t *testing.T) {
	s, clock, _ := testServer(t)
	def, err := s.CreateCampaign(api.Campaign{
		Name:  "auto",
		Group: api.Group{Kind: api.GroupZp, P: 2000000579, Order: 1000000289, Base: "9", Target: "81"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if def.Seed == 0 {
		t.Fatal("a campaign without a seed is a campaign whose agents walk different functions")
	}
	if def.R == 0 || def.UnitSteps == 0 {
		t.Fatalf("unresolved campaign: %+v", def)
	}
	if def.Fingerprint == "" {
		t.Fatal("no fingerprint")
	}
	// The same definition twice is a conflict, not a second campaign with
	// the same name.
	if _, err := s.CreateCampaign(def); err == nil {
		t.Fatal("creating a campaign twice should fail")
	}
	_ = clock
}

func TestFingerprintCoversEverythingThatChangesTheWalk(t *testing.T) {
	base := api.Campaign{
		Name:  "c",
		Group: api.Group{Kind: api.GroupZp, P: 2000000579, Order: 1000000289, Base: "9", Target: "81"},
		Seed:  1, R: 32, DPBits: 8, UnitSteps: 1000,
	}
	want := Fingerprint(base)
	for _, mod := range []func(c *api.Campaign){
		func(c *api.Campaign) { c.Seed = 2 },
		func(c *api.Campaign) { c.R = 64 },
		func(c *api.Campaign) { c.DPBits = 9 },
		func(c *api.Campaign) { c.Group.Target = "27" },
		func(c *api.Campaign) { c.Group.Order = 500000149 },
		func(c *api.Campaign) { c.Group.Kind = api.GroupEC },
	} {
		c := base
		mod(&c)
		if Fingerprint(c) == want {
			t.Fatalf("fingerprint did not change for %+v", c)
		}
	}
	// The unit budget does *not* change the walk function, so it must not
	// change the fingerprint: an operator who re-sizes units mid-campaign
	// would otherwise invalidate the whole corpus.
	c := base
	c.UnitSteps = 5000
	if Fingerprint(c) != want {
		t.Fatal("the unit budget must not be part of the walk's identity")
	}
}

func TestLeasesAreExclusiveAndFencesIncrease(t *testing.T) {
	s, clock, _ := testServer(t)
	def := testCampaign(t, s, "leases")
	c := s.campaign(def.Name)

	a := c.lease("agent-a", s.cfg.LeaseTTL, clock.now())
	b := c.lease("agent-b", s.cfg.LeaseTTL, clock.now())
	if a == nil || b == nil {
		t.Fatal("both agents should get work")
	}
	if a.Unit.ID == b.Unit.ID {
		t.Fatal("two agents were handed the same unit while both leases were live")
	}
	if a.Fence == b.Fence {
		t.Fatal("two live leases share a fence")
	}

	// Let a's lease expire and give the unit to somebody else.
	clock.add(2 * s.cfg.LeaseTTL)
	if n := c.expire(clock.now()); n != 2 {
		t.Fatalf("expected both leases to expire, got %d", n)
	}
	reissued := c.lease("agent-c", s.cfg.LeaseTTL, clock.now())
	if reissued == nil {
		t.Fatal("an expired unit should be re-issued")
	}
	if reissued.Fence <= a.Fence {
		t.Fatalf("re-issued fence %d is not past the old one %d", reissued.Fence, a.Fence)
	}
}

// The fence is what a lease length cannot do: stop a process that was paused
// past its expiry from writing into a unit somebody else now owns.
func TestAStaleAgentCannotWriteOrComplete(t *testing.T) {
	s, clock, _ := testServer(t)
	def := testCampaign(t, s, "fencing")
	c := s.campaign(def.Name)

	old := c.lease("agent-a", s.cfg.LeaseTTL, clock.now())
	clock.add(2 * s.cfg.LeaseTTL)
	c.expire(clock.now())
	fresh := c.lease("agent-b", s.cfg.LeaseTTL, clock.now())
	if fresh.Unit.ID != old.Unit.ID {
		t.Skip("the queue handed out a different unit; not the case under test")
	}

	points := make([]byte, api.PointBytes)
	if _, err := c.addPoints(old.Unit.ID, "agent-a", old.Fence, def.Fingerprint, points); err == nil {
		t.Fatal("a stale agent was allowed to write points")
	}
	if err := c.complete(old.Unit.ID, "agent-a", old.Fence, 1, 1, false, ""); err == nil {
		t.Fatal("a stale agent was allowed to complete the unit")
	}
	// And the current owner still can.
	if err := c.complete(fresh.Unit.ID, "agent-b", fresh.Fence, 10, 0, false, ""); err != nil {
		t.Fatalf("the owner could not complete its own unit: %v", err)
	}
}

func TestPointsFromADifferentWalkAreRefused(t *testing.T) {
	s, clock, _ := testServer(t)
	def := testCampaign(t, s, "fp")
	c := s.campaign(def.Name)
	lease := c.lease("agent-a", s.cfg.LeaseTTL, clock.now())
	_, err := c.addPoints(lease.Unit.ID, "agent-a", lease.Fence, "not-the-fingerprint",
		make([]byte, api.PointBytes))
	if err != ErrFingerprint {
		t.Fatalf("expected a fingerprint refusal, got %v", err)
	}
}

// Fabricated points must not enter the corpus: the server verifies rather
// than trusting, because an agent is just a process somebody else is running.
func TestTheServerVerifiesPoints(t *testing.T) {
	s, clock, _ := testServer(t)
	def := testCampaign(t, s, "verify")
	c := s.campaign(def.Name)
	lease := c.lease("agent-a", s.cfg.LeaseTTL, clock.now())

	junk := make([]byte, 4*api.PointBytes)
	for i := range junk {
		junk[i] = byte(i * 7)
	}
	resp, err := c.addPoints(lease.Unit.ID, "agent-a", lease.Fence, def.Fingerprint, junk)
	if err != nil {
		t.Fatal(err)
	}
	if resp.Accepted != 0 || resp.Rejected != 4 {
		t.Fatalf("junk was accepted: %+v", resp)
	}
	if resp.Stored != 0 {
		t.Fatalf("corpus grew from junk: %+v", resp)
	}
}

// A control plane that comes back without its corpus silently restarts a
// search that was half finished, so restarting is tested with real points.
func TestRestartRestoresTheCorpusAndTheLedger(t *testing.T) {
	dir := t.TempDir()
	st, err := store.Open(dir)
	if err != nil {
		t.Fatal(err)
	}
	clock := &fakeClock{t: time.Unix(1700000000, 0).UTC()}
	s, err := NewServer(st, Config{Now: clock.now, Logger: quiet()})
	if err != nil {
		t.Fatal(err)
	}
	def := testCampaign(t, s, "restart")
	c := s.campaign(def.Name)

	// Real points, produced by walking the campaign's own function in this
	// process: the C walker is not needed to test persistence.
	lease := c.lease("agent-a", s.cfg.LeaseTTL, clock.now())
	pts := syntheticPoints(t, def, 8)
	resp, err := c.addPoints(lease.Unit.ID, "agent-a", lease.Fence, def.Fingerprint, pts)
	if err != nil {
		t.Fatal(err)
	}
	if resp.Accepted == 0 {
		t.Fatalf("the server rejected its own campaign's points: %+v", resp)
	}
	if err := c.complete(lease.Unit.ID, "agent-a", lease.Fence, 1234, resp.Accepted, false, ""); err != nil {
		t.Fatal(err)
	}
	before := c.status()
	st.Close()

	// A new process over the same directory.
	st2, err := store.Open(dir)
	if err != nil {
		t.Fatal(err)
	}
	defer st2.Close()
	s2, err := NewServer(st2, Config{Now: clock.now, Logger: quiet()})
	if err != nil {
		t.Fatal(err)
	}
	after := s2.campaign(def.Name).status()
	if after.Stored != before.Stored {
		t.Fatalf("corpus lost across a restart: %d stored, was %d", after.Stored, before.Stored)
	}
	if after.Units.Done != 1 || after.Units.Next <= lease.Unit.ID {
		t.Fatalf("unit ledger not replayed: %+v", after.Units)
	}
	if after.Steps != before.Steps {
		t.Fatalf("steps lost: %d, was %d", after.Steps, before.Steps)
	}
}

// syntheticPoints produces valid records for a campaign by walking in the
// test process: start from a random (a, b), step by adding the base until a
// distinguished point falls out.  It is not the library's walk -- it does not
// have to be, because a point is admissible if it verifies, whatever walk
// produced it -- and it keeps this file free of a dependency on the C binary.
func syntheticPoints(t *testing.T, def api.Campaign, n int) []byte {
	t.Helper()
	g, err := dlog.NewGroup(dlog.Zp, def.Group.P, 0, 0, def.Group.Order)
	if err != nil {
		t.Fatal(err)
	}
	base, err := g.ParsePoint(def.Group.Base)
	if err != nil {
		t.Fatal(err)
	}
	target, err := g.ParsePoint(def.Group.Target)
	if err != nil {
		t.Fatal(err)
	}
	mask := uint64(1)<<uint(def.DPBits) - 1
	var out []byte
	a, b := uint64(12345), uint64(6789)
	y := g.Add(g.ScalarMul(base, a), g.ScalarMul(target, b))
	for len(out) < n*api.PointBytes {
		y = g.Add(y, base)
		a = (a + 1) % def.Group.Order
		if g.Hash(y)&mask == 0 {
			rec := make([]byte, api.PointBytes)
			dlog.EncodeRecord(rec, dlog.Record{W0: y.X, A: a, B: b})
			out = append(out, rec...)
		}
	}
	return out
}

// ---- the HTTP surface -----------------------------------------------------

func TestAuthIsRequiredWhenATokenIsSet(t *testing.T) {
	st, _ := store.Open(t.TempDir())
	defer st.Close()
	s, err := NewServer(st, Config{Token: "sekrit", Logger: quiet()})
	if err != nil {
		t.Fatal(err)
	}
	srv := httptest.NewServer(s.Handler())
	defer srv.Close()

	resp, err := http.Get(srv.URL + "/v1/status")
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("unauthenticated status returned %d", resp.StatusCode)
	}

	req, _ := http.NewRequest(http.MethodGet, srv.URL+"/v1/status", nil)
	req.Header.Set("Authorization", "Bearer sekrit")
	resp, err = http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("authenticated status returned %d", resp.StatusCode)
	}

	// Liveness must not need a token: a probe that has to be given the
	// cluster's secret is a probe that will one day be given the wrong one.
	resp, err = http.Get(srv.URL + "/healthz")
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("healthz returned %d", resp.StatusCode)
	}
}

func TestDrainStopsLeasesAndFailsReadiness(t *testing.T) {
	s, _, _ := testServer(t)
	testCampaign(t, s, "drain")
	srv := httptest.NewServer(s.Handler())
	defer srv.Close()

	s.Drain(true)
	resp, err := http.Get(srv.URL + "/readyz")
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusServiceUnavailable {
		t.Fatalf("a draining server reported ready (%d)", resp.StatusCode)
	}

	body, _ := json.Marshal(api.LeaseRequest{AgentID: "a"})
	resp, err = http.Post(srv.URL+"/v1/units/lease", "application/json", bytes.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	var lease api.LeaseResponse
	if err := json.NewDecoder(resp.Body).Decode(&lease); err != nil {
		t.Fatal(err)
	}
	if lease.Lease != nil {
		t.Fatal("a draining server handed out a lease")
	}
}

func TestPointsEndpointRejectsAPartialRecord(t *testing.T) {
	s, _, _ := testServer(t)
	def := testCampaign(t, s, "partial")
	srv := httptest.NewServer(s.Handler())
	defer srv.Close()

	url := fmt.Sprintf("%s/v1/units/points?campaign=%s&agent=a&unit=0&fence=1", srv.URL, def.Name)
	resp, err := http.Post(url, "application/octet-stream", bytes.NewReader(make([]byte, 33)))
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("a body that is not a whole number of records returned %d", resp.StatusCode)
	}
}

func TestMetricsAreScrapable(t *testing.T) {
	s, _, _ := testServer(t)
	testCampaign(t, s, "metrics")
	srv := httptest.NewServer(s.Handler())
	defer srv.Close()
	resp, err := http.Get(srv.URL + "/metrics")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	for _, want := range []string{"ca_leases_total", "ca_campaign_points", `campaign="metrics"`} {
		if !bytes.Contains(body, []byte(want)) {
			t.Fatalf("metrics did not mention %q:\n%s", want, body)
		}
	}
}

// A unit that keeps failing is eventually abandoned rather than re-issued
// forever: whatever is wrong with it is not going to be fixed by the fleet
// trying again.
func TestAUnitIsAbandonedAfterRepeatedFailures(t *testing.T) {
	s, clock, _ := testServer(t)
	def := testCampaign(t, s, "abandon")
	c := s.campaign(def.Name)
	var id uint64
	for i := 0; i < MaxAttempts+2; i++ {
		lease := c.lease("agent-a", s.cfg.LeaseTTL, clock.now())
		if lease == nil {
			t.Fatal("no lease")
		}
		if i == 0 {
			id = lease.Unit.ID
		}
		if err := c.complete(lease.Unit.ID, "agent-a", lease.Fence, 0, 0, true, "boom"); err != nil {
			t.Fatal(err)
		}
	}
	st := c.status()
	if st.Units.Abandoned == 0 {
		t.Fatalf("a repeatedly failing unit was never abandoned: %+v (unit %d)", st.Units, id)
	}
}

func TestStateDirectoryIsSelfContained(t *testing.T) {
	dir := t.TempDir()
	st, err := store.Open(dir)
	if err != nil {
		t.Fatal(err)
	}
	defer st.Close()
	s, err := NewServer(st, Config{Logger: quiet()})
	if err != nil {
		t.Fatal(err)
	}
	def := testCampaign(t, s, "files")
	for _, want := range []string{"campaigns/" + def.Name + ".json", "units.jsonl"} {
		if _, err := os.Stat(dir + "/" + want); err != nil {
			t.Fatalf("expected %s in the state directory: %v", want, err)
		}
	}
	_ = strconv.Itoa
}

// An agent id is a registry key, an owner check and a log field, so the
// server decides what one may look like rather than accepting whatever
// arrives.  The rejected shapes below are the ones that actually cause
// trouble: a newline forges a log line, a slash reaches for a path, and an
// unbounded id is an unbounded map key.
func TestAgentIdentityIsValidatedAtTheEdge(t *testing.T) {
	s, _, _ := testServer(t)
	testCampaign(t, s, "ids")
	srv := httptest.NewServer(s.Handler())
	defer srv.Close()

	bad := []string{
		"",
		"agent one",
		"agent/../../etc",
		"agent\ninfo msg=\"forged log line\"",
		strings.Repeat("a", 65),
	}
	for _, id := range bad {
		body, _ := json.Marshal(api.RegisterRequest{Info: api.AgentInfo{ID: id}})
		resp, err := http.Post(srv.URL+"/v1/agents/register", "application/json",
			bytes.NewReader(body))
		if err != nil {
			t.Fatal(err)
		}
		resp.Body.Close()
		if resp.StatusCode != http.StatusBadRequest {
			t.Fatalf("register accepted agent id %q with status %d", id, resp.StatusCode)
		}

		body, _ = json.Marshal(api.LeaseRequest{AgentID: id})
		resp, err = http.Post(srv.URL+"/v1/units/lease", "application/json", bytes.NewReader(body))
		if err != nil {
			t.Fatal(err)
		}
		resp.Body.Close()
		if resp.StatusCode != http.StatusBadRequest {
			t.Fatalf("lease accepted agent id %q with status %d", id, resp.StatusCode)
		}
	}

	// And the shapes a real deployment produces are accepted: a Kubernetes
	// pod name and the hostname-plus-suffix the agent builds for itself.
	for _, id := range []string{"ca-agent-6d4b8c7f9-x2k4p", "ip-10-0-1-23.ec2.internal-a1b2c3"} {
		body, _ := json.Marshal(api.RegisterRequest{Info: api.AgentInfo{ID: id}})
		resp, err := http.Post(srv.URL+"/v1/agents/register", "application/json",
			bytes.NewReader(body))
		if err != nil {
			t.Fatal(err)
		}
		resp.Body.Close()
		if resp.StatusCode != http.StatusOK {
			t.Fatalf("register refused a legitimate agent id %q (%d)", id, resp.StatusCode)
		}
	}
}

// The free-text field an agent may set is cleaned once, at the boundary, so
// that neither the ledger nor the log ever holds a line break somebody else
// chose.
func TestAgentTextIsCleanedBeforeItIsStored(t *testing.T) {
	got := api.CleanText("boom\ninfo msg=\"unit finished\"\r\x00")
	if strings.ContainsAny(got, "\n\r\x00") {
		t.Fatalf("CleanText left a control character in %q", got)
	}
	if !strings.Contains(got, "boom") {
		t.Fatalf("CleanText destroyed the message: %q", got)
	}
	long := api.CleanText(strings.Repeat("x", api.MaxReasonBytes*3))
	if len(long) != api.MaxReasonBytes {
		t.Fatalf("CleanText returned %d bytes, expected %d", len(long), api.MaxReasonBytes)
	}
}
