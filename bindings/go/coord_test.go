package cryptanalysis_test

import (
	"strings"
	"testing"

	ca "github.com/aburan28/cryptanalysis/bindings/go"
)

// A small instance with a planted secret, so every run is checkable.
// p = 2q+1 with q = 1000151, a real prime-order subgroup.
func testJob(t *testing.T, secret uint64) (ca.Job, *ca.Ctx, uint64) {
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
	if x == 0 {
		x = 1
	}
	h, err := g.Mul(gen, x)
	if err != nil {
		t.Fatalf("mul: %v", err)
	}
	job, err := ca.NewJob(&ca.JobParams{
		Kind: ca.GroupZp, P: g.P(), Order: g.Order(),
		Base: gen, Target: h,
		DPBits: 5, Branches: 16, UnitSize: 32, Seed: 7,
	})
	if err != nil {
		t.Fatalf("job: %v", err)
	}
	ctx, err := ca.OpenCtx(job)
	if err != nil {
		t.Fatalf("ctx: %v", err)
	}
	t.Cleanup(ctx.Close)
	return job, ctx, x
}

func TestJobRoundTrip(t *testing.T) {
	job, ctx, _ := testJob(t, 123456)

	back, err := ca.ParseJob(job.String())
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	if back.ID() != job.ID() {
		t.Errorf("id changed across a round trip: %x != %x", back.ID(), job.ID())
	}
	if back.Order != 1000151 || back.DPBits != 5 || back.UnitSize != 32 {
		t.Errorf("fields did not survive: %+v", back)
	}
	if got := ctx.ExpectedSteps(); got < 1000 || got > 1e7 {
		t.Errorf("expected steps out of range for a 2^20 group: %g", got)
	}

	// A document altered in transit is refused, not walked: two agents
	// on different branch tables silently stop colliding.
	altered := strings.Replace(job.String(), " dp=5 ", " dp=6 ", 1)
	if altered == job.String() {
		t.Fatal("test bug: nothing was altered")
	}
	if _, err := ca.ParseJob(altered); err == nil {
		t.Error("an altered job document was accepted")
	}

	// A trailing newline is what /v1/job serves.
	if _, err := ca.ParseJob(job.String() + "\n"); err != nil {
		t.Errorf("a served job did not parse: %v", err)
	}
}

func TestVersionVectorWire(t *testing.T) {
	vv := ca.ParseVersionVector("vv alice.0:7 bob.1:3 alice.0:2")
	if vv["alice.0"] != 7 {
		t.Errorf("a lower repeat lowered the vector: %v", vv)
	}
	if vv["bob.1"] != 3 {
		t.Errorf("missing entry: %v", vv)
	}
	// A vector is a hint: garbage entries are skipped, not fatal, and
	// the worst a wrong one costs is a resend.
	vv = ca.ParseVersionVector("vv broken alice.0:notanumber carol.2:9 :5")
	if len(vv) != 1 || vv["carol.2"] != 9 {
		t.Errorf("unparsable entries were not skipped: %v", vv)
	}
	if got := ca.ParseVersionVector(vv.String()); got["carol.2"] != 9 {
		t.Errorf("vector did not survive its own encoding: %v", got)
	}
}

// The merge is a CRDT: order-independent, idempotent, and it refuses
// what it cannot verify.
func TestStateMergeAndRefusals(t *testing.T) {
	_, ctx, secret := testJob(t, 55555)

	src, err := ca.NewState(ctx)
	if err != nil {
		t.Fatalf("state: %v", err)
	}
	defer src.Close()
	if _, err := ca.RunLane(ctx, src, ca.LaneParams{
		Peer: "a.0", MaxWalkers: 24, CheckinEvery: 4,
	}); err != nil {
		t.Fatalf("lane: %v", err)
	}
	lines := src.DeltaFrom(ca.VersionVector{})
	if len(lines) < 3 {
		t.Fatalf("a lane produced only %d check-ins", len(lines))
	}

	forward, err := ca.NewState(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer forward.Close()
	reverse, err := ca.NewState(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer reverse.Close()
	for _, l := range lines {
		if _, err := forward.ApplyLine(l); err != nil {
			t.Fatalf("apply: %v", err)
		}
	}
	for _, l := range lines { // idempotent: the same lines again
		if _, err := forward.ApplyLine(l); err != nil {
			t.Fatalf("re-apply: %v", err)
		}
	}
	for i := len(lines) - 1; i >= 0; i-- { // and order-independent
		if _, err := reverse.ApplyLine(lines[i]); err != nil {
			t.Fatalf("apply reversed: %v", err)
		}
	}
	f, r := forward.Progress(120), reverse.Progress(120)
	if f.DPsStored != r.DPsStored || f.Steps != r.Steps || f.Checkins != r.Checkins {
		t.Errorf("merge is order-dependent:\n forward %+v\n reverse %+v", f, r)
	}
	if f.RejectedDPs != 0 {
		t.Errorf("genuine records were rejected: %d", f.RejectedDPs)
	}
	if f.Solved && f.Solution != secret {
		t.Errorf("solved with the wrong x: %d != %d", f.Solution, secret)
	}

	// A line for another job is refused.
	other := strings.Replace(lines[0], "ci ", "ci 1", 1)
	if _, err := forward.ApplyLine(other); err == nil {
		t.Error("a foreign job's check-in was accepted")
	}
	// So is a forged point: same shape, wrong coefficients.
	for _, l := range lines {
		if !strings.Contains(l, "D:") || strings.Contains(l, "D: ") {
			continue
		}
		forged := forgeCoefficient(l)
		if forged == l {
			continue
		}
		oc, err := forward.ApplyLine(forged)
		if err != nil {
			continue // refused outright, also fine
		}
		if oc.RejectedDPs == 0 && oc.AcceptedDPs > 0 {
			t.Error("a forged point was accepted")
		}
		break
	}
}

// forgeCoefficient bumps the `a` of the first distinguished point in a
// check-in line, which must make a*G + b*H stop matching the point.
func forgeCoefficient(line string) string {
	i := strings.Index(line, "D:")
	if i < 0 {
		return line
	}
	rest := line[i+2:]
	end := strings.Index(rest, ";")
	if end < 0 {
		return line
	}
	fields := strings.Split(rest[:end], ",")
	if len(fields) != 8 {
		return line
	}
	fields[6] = "1"
	return line[:i+2] + strings.Join(fields, ",") + rest[end:]
}

func TestDeltaAndLog(t *testing.T) {
	_, ctx, _ := testJob(t, 8080)
	a, err := ca.NewState(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer a.Close()
	if _, err := ca.RunLane(ctx, a, ca.LaneParams{Peer: "a.0", MaxWalkers: 16, CheckinEvery: 4}); err != nil {
		t.Fatalf("lane: %v", err)
	}

	all := a.DeltaFrom(ca.VersionVector{})
	if len(all) != a.LogLen() {
		t.Errorf("the empty vector is owed the whole log: %d != %d", len(all), a.LogLen())
	}
	// Owed nothing once the vectors agree -- the property that makes one
	// round trip enough.
	if got := a.DeltaFrom(a.VersionVector()); len(got) != 0 {
		t.Errorf("still owed %d entries after matching vectors", len(got))
	}
	// Partial knowledge is owed exactly the tail.
	vv := a.VersionVector()
	full := vv["a.0"]
	vv["a.0"] = full - 1
	if got := a.DeltaFrom(vv); len(got) != 1 {
		t.Errorf("a vector one behind is owed one entry, got %d", len(got))
	}
	if e, ok := a.LogAt(0); !ok || e.Peer != "a.0" || e.Seq == 0 || !strings.HasPrefix(e.Line, "ci ") {
		t.Errorf("log entry 0 is wrong: %+v ok=%v", e, ok)
	}
	if _, ok := a.LogAt(a.LogLen()); ok {
		t.Error("reading past the end of the log succeeded")
	}
}
