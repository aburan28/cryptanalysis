package dlog

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
)

// The C library is the reference implementation of the walk, the element
// hash and the point encoding.  These tests run the real `ca` binary and
// require this package to agree with it exactly:
//
//   - every point `ca dist-walk` produces must pass this package's
//     verification, which includes reproducing the library's element hash
//     through its Montgomery representation.  One wrong constant there and
//     every honest point looks undistinguished, which in production would
//     show up as a fleet doing perfect work that the server throws away.
//   - the discrete logarithm this package computes from the corpus must be
//     the one the C merger computes, and the one that was planted.
//
// The tests skip when there is no binary to compare against, which is the
// case on a machine that has not built the library; CI builds it first.

func caBinary(t *testing.T) string {
	t.Helper()
	if p := os.Getenv("CA_BIN"); p != "" {
		return p
	}
	// The repository layout: orchestrator/internal/dlog -> ../../../build/ca
	p, err := filepath.Abs(filepath.Join("..", "..", "..", "build", "ca"))
	if err != nil {
		t.Skipf("cannot resolve the ca binary: %v", err)
	}
	if _, err := os.Stat(p); err != nil {
		t.Skipf("no ca binary at %s (build it with `make lib`, or set CA_BIN)", p)
	}
	return p
}

type genOut struct {
	Group string `json:"group"`
	P     uint64 `json:"p"`
	A     uint64 `json:"a"`
	B     uint64 `json:"b"`
	Order uint64 `json:"order"`
	G     string `json:"g"`
	H     string `json:"h"`
	X     uint64 `json:"x"`
}

func runJSON(t *testing.T, out any, name string, args ...string) {
	t.Helper()
	cmd := exec.Command(name, args...)
	var stderr strings.Builder
	cmd.Stderr = &stderr
	raw, err := cmd.Output()
	if err != nil {
		t.Fatalf("%s %s: %v (%s)", name, strings.Join(args, " "), err, stderr.String())
	}
	if err := json.Unmarshal(raw, out); err != nil {
		t.Fatalf("decoding %s output %q: %v", name, raw, err)
	}
}

// walkUnits runs `ca dist-walk` for a range of units and returns the raw
// corpus, exactly as an agent would upload it.
func walkUnits(t *testing.T, ca string, gen genOut, seed uint64, dpBits int32, units int,
	steps uint64) [][]byte {
	t.Helper()
	dir := t.TempDir()
	var corpus [][]byte
	for u := 0; u < units; u++ {
		path := filepath.Join(dir, "u"+strconv.Itoa(u)+".bin")
		args := []string{"dist-walk", "--group", gen.Group, "--p", strconv.FormatUint(gen.P, 10),
			"--order", strconv.FormatUint(gen.Order, 10), "--g", gen.G, "--h", gen.H,
			"--campaign-seed", strconv.FormatUint(seed, 10),
			"--dp-bits", strconv.FormatInt(int64(dpBits), 10),
			"--unit", strconv.Itoa(u), "--steps", strconv.FormatUint(steps, 10),
			"--walks", "16", "--out", path}
		if gen.Group == "ec" {
			args = append(args, "--a", strconv.FormatUint(gen.A, 10), "--b", strconv.FormatUint(gen.B, 10))
		}
		var summary struct {
			Points uint64 `json:"points"`
		}
		runJSON(t, &summary, ca, args...)
		blob, err := os.ReadFile(path)
		if err != nil {
			t.Fatalf("reading unit %d: %v", u, err)
		}
		if uint64(len(blob))/PointBytes != summary.Points {
			t.Fatalf("unit %d: %d bytes but the walker reported %d points",
				u, len(blob), summary.Points)
		}
		corpus = append(corpus, blob)
	}
	return corpus
}

func TestAgreesWithTheLibraryOnZp(t *testing.T) {
	ca := caBinary(t)
	var gen genOut
	runJSON(t, &gen, ca, "gen", "--group", "zp", "--p", "2000000579", "--order", "1000000289",
		"--seed", "7")

	g, err := NewGroup(Zp, gen.P, 0, 0, gen.Order)
	if err != nil {
		t.Fatal(err)
	}
	base, err := g.ParsePoint(gen.G)
	if err != nil {
		t.Fatal(err)
	}
	target, err := g.ParsePoint(gen.H)
	if err != nil {
		t.Fatal(err)
	}
	// The instance the library generated must be the instance this package
	// thinks it is: x*G == H with the x the generator printed.
	if !g.Equal(g.ScalarMul(base, gen.X), target) {
		t.Fatal("this package disagrees with the library about the instance")
	}

	const seed, dpBits = 12345, 6
	m, err := NewMerger(g, base, target, dpBits, true)
	if err != nil {
		t.Fatal(err)
	}
	for i, blob := range walkUnits(t, ca, gen, seed, dpBits, 8, 20000) {
		c, err := m.AddBytes(blob)
		if err != nil {
			t.Fatalf("unit %d: %v", i, err)
		}
		if c.Rejected != 0 {
			t.Fatalf("unit %d: %d of the library's own points were rejected; the hash or the "+
				"verification disagrees with the C implementation", i, c.Rejected)
		}
	}
	x, ok := m.Solved()
	if !ok {
		t.Fatalf("no collision after 8 units; stats %+v", m.Stats())
	}
	if x != gen.X {
		t.Fatalf("solved x = %d, planted %d", x, gen.X)
	}
}

func TestAgreesWithTheLibraryOnACurve(t *testing.T) {
	ca := caBinary(t)
	// A curve with a large prime-order subgroup: `ca gen` picks the group,
	// this test does not get to choose a convenient one.
	var gen genOut
	runJSON(t, &gen, ca, "gen", "--group", "ec", "--p", "1000000007", "--a", "3", "--b", "11",
		"--seed", "3")
	if gen.Order < 4096 {
		t.Skipf("generated subgroup too small (%d)", gen.Order)
	}

	g, err := NewGroup(EC, gen.P, gen.A, gen.B, gen.Order)
	if err != nil {
		t.Fatal(err)
	}
	base, err := g.ParsePoint(gen.G)
	if err != nil {
		t.Fatalf("parsing the library's generator %q: %v", gen.G, err)
	}
	target, err := g.ParsePoint(gen.H)
	if err != nil {
		t.Fatal(err)
	}
	if !g.Equal(g.ScalarMul(base, gen.X), target) {
		t.Fatal("this package disagrees with the library about the curve instance")
	}

	const seed, dpBits = 777, 4
	m, err := NewMerger(g, base, target, dpBits, true)
	if err != nil {
		t.Fatal(err)
	}
	var accepted uint64
	for i, blob := range walkUnits(t, ca, gen, seed, dpBits, 12, 20000) {
		c, err := m.AddBytes(blob)
		if err != nil {
			t.Fatalf("unit %d: %v", i, err)
		}
		if c.Rejected != 0 {
			t.Fatalf("unit %d: %d of the library's own curve points were rejected", i, c.Rejected)
		}
		accepted += c.Accepted
	}
	if accepted == 0 {
		t.Fatal("no points at all: the walk produced nothing to check")
	}
	x, ok := m.Solved()
	if !ok {
		t.Fatalf("no collision after 12 units; stats %+v", m.Stats())
	}
	if x != gen.X {
		t.Fatalf("solved x = %d, planted %d", x, gen.X)
	}
}

// The C merger and this one must reach the same answer from the same corpus.
// Two implementations that agree on a number neither of them was told is a
// much better check than either against itself.
func TestTheTwoMergersAgree(t *testing.T) {
	ca := caBinary(t)
	var gen genOut
	runJSON(t, &gen, ca, "gen", "--group", "zp", "--p", "2000000579", "--order", "1000000289",
		"--seed", "11")
	g, _ := NewGroup(Zp, gen.P, 0, 0, gen.Order)
	base, _ := g.ParsePoint(gen.G)
	target, _ := g.ParsePoint(gen.H)

	const seed, dpBits = 5150, 6
	corpus := walkUnits(t, ca, gen, seed, dpBits, 8, 20000)

	dir := t.TempDir()
	var paths []string
	for i, blob := range corpus {
		p := filepath.Join(dir, "u"+strconv.Itoa(i)+".bin")
		if err := os.WriteFile(p, blob, 0o600); err != nil {
			t.Fatal(err)
		}
		paths = append(paths, p)
	}

	var cOut struct {
		Accepted   uint64 `json:"accepted"`
		Duplicates uint64 `json:"duplicates"`
		Rejected   uint64 `json:"rejected"`
		Stored     uint64 `json:"stored"`
		Solved     bool   `json:"solved"`
		X          uint64 `json:"x"`
	}
	args := append([]string{"dist-merge", "--group", "zp", "--p", strconv.FormatUint(gen.P, 10),
		"--order", strconv.FormatUint(gen.Order, 10), "--g", gen.G, "--h", gen.H,
		"--campaign-seed", strconv.FormatUint(seed, 10), "--dp-bits", strconv.Itoa(dpBits)}, paths...)
	runJSON(t, &cOut, ca, args...)

	m, _ := NewMerger(g, base, target, dpBits, true)
	for _, blob := range corpus {
		if _, err := m.AddBytes(blob); err != nil {
			t.Fatal(err)
		}
	}
	got := m.Stats()

	if !cOut.Solved || !got.Solved {
		t.Fatalf("one merger solved and the other did not: C %v, Go %v", cOut.Solved, got.Solved)
	}
	if cOut.X != got.X || got.X != gen.X {
		t.Fatalf("x: C %d, Go %d, planted %d", cOut.X, got.X, gen.X)
	}
	if cOut.Rejected != got.Rejected || got.Rejected != 0 {
		t.Fatalf("rejected: C %d, Go %d", cOut.Rejected, got.Rejected)
	}
	// The stored count is the size of the corpus by distinct point, which
	// both implementations must agree on exactly -- they are looking at the
	// same bytes with the same key.
	if cOut.Stored != got.Stored {
		t.Fatalf("stored: C %d, Go %d", cOut.Stored, got.Stored)
	}
	if cOut.Duplicates != got.Duplicates {
		t.Fatalf("duplicates: C %d, Go %d", cOut.Duplicates, got.Duplicates)
	}
}

// A unit replayed is a unit reproduced: the scheduler's retry story depends
// on this, and it is cheap to assert against the real walker.
func TestUnitsAreReplayable(t *testing.T) {
	ca := caBinary(t)
	var gen genOut
	runJSON(t, &gen, ca, "gen", "--group", "zp", "--p", "2000000579", "--order", "1000000289",
		"--seed", "3")
	first := walkUnits(t, ca, gen, 99, 6, 2, 10000)
	second := walkUnits(t, ca, gen, 99, 6, 2, 10000)
	for i := range first {
		if string(first[i]) != string(second[i]) {
			t.Fatalf("unit %d differed between two runs", i)
		}
	}
	if len(first[0]) == 0 {
		t.Fatal("the walk produced no points to compare")
	}
}
