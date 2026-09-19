// Package agent is the worker side: lease a unit, walk it, report the
// points, repeat.
//
// The agent contains no cryptanalysis.  It runs the library's own `ca
// dist-walk`, which is the same binary the project tests and benchmarks, and
// its whole job is the part that is about a fleet rather than about a walk:
// getting a lease, respecting it, uploading what it produced, and dying
// quietly when it is told to.
//
// Nothing here is stateful across restarts.  A killed agent loses at most
// the points of the unit in flight, and that unit is replayable by anyone --
// which is why the agent is safe to run on spot capacity, as a preemptible
// pod, or on a laptop that gets closed.
package agent

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/aburan28/cryptanalysis/orchestrator/api"
)

// WalkResult is one finished `ca dist-walk` invocation.
type WalkResult struct {
	Points   uint64
	Steps    uint64
	Bytes    []byte
	Campaign uint64 // the library's own campaign id, for a sanity check
	Duration time.Duration
}

// Walker runs one unit.  An interface so that the agent loop can be tested
// without the C binary, and so that a future in-process or FPGA-backed
// walker can be dropped in without touching the loop.
type Walker interface {
	Walk(ctx context.Context, lease *api.Lease) (WalkResult, error)
	Describe() string
}

// CLIWalker runs the library's `ca` binary.
type CLIWalker struct {
	Binary string
	// TempDir is where the record file is written before it is uploaded.
	// On Kubernetes this should be an emptyDir: the file is worthless after
	// the upload and must not survive the pod.
	TempDir string
	Threads int
}

func (w *CLIWalker) Describe() string { return "ca dist-walk (" + w.Binary + ")" }

// Args builds the command line for a lease.  Every campaign parameter is
// passed explicitly -- seed, r and dp-bits -- rather than left to the
// library's own resolution: an agent and a server that resolve a default
// differently would walk two different functions and produce corpora that
// never collide, and nothing in either process would report an error.
func (w *CLIWalker) Args(lease *api.Lease, out string) []string {
	c := lease.Campaign
	args := []string{"dist-walk",
		"--group", string(c.Group.Kind),
		"--p", strconv.FormatUint(c.Group.P, 10),
		"--order", strconv.FormatUint(c.Group.Order, 10),
		"--g", c.Group.Base,
		"--h", c.Group.Target,
		"--campaign-seed", strconv.FormatUint(c.Seed, 10),
		"--r", strconv.FormatUint(uint64(c.R), 10),
		"--dp-bits", strconv.FormatInt(int64(c.DPBits), 10),
		"--unit", strconv.FormatUint(lease.Unit.ID, 10),
		"--steps", strconv.FormatUint(lease.Unit.MaxSteps, 10),
		"--out", out,
	}
	if c.Group.Kind == api.GroupEC {
		args = append(args, "--a", strconv.FormatUint(c.Group.A, 10),
			"--b", strconv.FormatUint(c.Group.B, 10))
	}
	if lease.Unit.Walks > 0 {
		args = append(args, "--walks", strconv.FormatUint(uint64(lease.Unit.Walks), 10))
	}
	return args
}

type walkSummary struct {
	Status   string `json:"status"`
	Campaign uint64 `json:"campaign"`
	Unit     uint64 `json:"unit"`
	Points   uint64 `json:"points"`
	Steps    uint64 `json:"steps"`
	Bytes    uint64 `json:"bytes"`
}

func (w *CLIWalker) Walk(ctx context.Context, lease *api.Lease) (WalkResult, error) {
	dir := w.TempDir
	if dir == "" {
		dir = os.TempDir()
	}
	f, err := os.CreateTemp(dir, "unit-*.bin")
	if err != nil {
		return WalkResult{}, err
	}
	path := f.Name()
	f.Close()
	defer os.Remove(path)

	start := time.Now()
	cmd := exec.CommandContext(ctx, w.Binary, w.Args(lease, path)...)
	// The walker's own summary is on stdout; anything on stderr is the
	// library's error text and belongs in the failure message.
	var stderr strings.Builder
	cmd.Stderr = &stderr
	raw, err := cmd.Output()
	if err != nil {
		// A cancelled context is the normal shutdown path, not a failure of
		// the unit: the caller decides what to do with whatever was written.
		if ctx.Err() != nil {
			data, readErr := os.ReadFile(path)
			if readErr == nil && len(data) >= api.PointBytes {
				whole := len(data) / api.PointBytes * api.PointBytes
				return WalkResult{Points: uint64(whole / api.PointBytes), Bytes: data[:whole],
					Duration: time.Since(start)}, ctx.Err()
			}
			return WalkResult{Duration: time.Since(start)}, ctx.Err()
		}
		return WalkResult{}, fmt.Errorf("%s: %w: %s", w.Binary, err,
			strings.TrimSpace(stderr.String()))
	}
	var sum walkSummary
	if err := json.Unmarshal(raw, &sum); err != nil {
		return WalkResult{}, fmt.Errorf("cannot read the walker's summary %q: %w", raw, err)
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return WalkResult{}, err
	}
	if uint64(len(data)) != sum.Bytes {
		// The walker says how many bytes it wrote; a file that disagrees
		// means something else is writing to it, and uploading it would put
		// points in the corpus that no walk produced.
		return WalkResult{}, fmt.Errorf("walker wrote %d bytes, file holds %d", sum.Bytes,
			len(data))
	}
	return WalkResult{Points: sum.Points, Steps: sum.Steps, Bytes: data, Campaign: sum.Campaign,
		Duration: time.Since(start)}, nil
}

// ProbeBinary checks that the walker exists and speaks the expected
// protocol, at startup rather than on the first lease.  An agent that cannot
// walk should fail its readiness probe immediately, not take a unit and
// hold it for a lease period first.
func ProbeBinary(binary string) (string, error) {
	out, err := exec.Command(binary, "version").Output()
	if err != nil {
		return "", fmt.Errorf("%s version: %w", binary, err)
	}
	var v struct {
		Version string `json:"version"`
	}
	if err := json.Unmarshal(out, &v); err != nil {
		return strings.TrimSpace(string(out)), nil
	}
	return v.Version, nil
}

// lineWriter turns a subprocess's output into log lines without holding the
// whole thing in memory.  Unused by the JSON path above, kept for the
// verbose mode the agent CLI exposes.
type lineWriter struct {
	mu sync.Mutex
	fn func(string)
	b  strings.Builder
}

func (l *lineWriter) Write(p []byte) (int, error) {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.b.Write(p)
	s := bufio.NewScanner(strings.NewReader(l.b.String()))
	l.b.Reset()
	for s.Scan() {
		l.fn(s.Text())
	}
	return len(p), nil
}
