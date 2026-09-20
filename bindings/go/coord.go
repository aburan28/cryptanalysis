package cryptanalysis

// Distributed rho: the Go side of ca_coord.h.
//
// This file is a thin, safe wrapper over the C core -- the job, the
// derived context, the CRDT and the wire format -- and nothing more.
// Deciding what is true (is this point real, does this collision solve
// the instance, is this the discrete logarithm) stays in the C library,
// in one implementation, so a coordinator written here cannot disagree
// with an agent written there.
//
// The coordinator service that uses it is cmd/ca-coordinator.

/*
#cgo CFLAGS: -O3 -std=gnu11 -D_GNU_SOURCE -DCA_BUILDING -I${SRCDIR}/../../include -I${SRCDIR}/../../src
#cgo LDFLAGS: -lpthread -lm
#include <stdlib.h>
#include <cryptanalysis/ca_coord.h>
*/
import "C"

import (
	"errors"
	"fmt"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"time"
	"unsafe"
)

// LineMax is the longest wire line, including the terminator.
const LineMax = C.CA_COORD_LINE_MAX

// PeerMax is the longest peer name, including the terminator.
const PeerMax = C.CA_COORD_PEER_MAX

// ChannelProtocol is the token in the reverse channel's Upgrade header.
const ChannelProtocol = "ca-rho/1"

// Env vars an agent and the coordinator both honour.
const (
	URLEnv   = "CA_COORDINATOR_URL"
	TokenEnv = "CA_COORDINATOR_TOKEN"
)

// ErrJob reports a job document that does not parse or whose id does not
// match its contents.
var ErrJob = errors.New("cryptanalysis: bad job document")

// Job is a parsed job document.  It is carried by value; the canonical
// text (what /v1/job serves, and the preimage of the id) is String.
type Job struct {
	text string
	id   uint64

	Order    uint64
	DPBits   int32
	Branches uint32
	Negation bool
	UnitSize uint64
	Seed     uint64
}

// ID is the job id: the 64-bit hash of the canonical text.  It is an
// agreement check between participants, not a commitment -- see
// docs/COORDINATOR.md.
func (j Job) ID() uint64 { return j.id }

// IDString is the id as the wire and the logs spell it.
func (j Job) IDString() string { return fmt.Sprintf("%016x", j.id) }

// String is the canonical one-line encoding.
func (j Job) String() string { return j.text }

// ParseJob parses (and re-verifies the id of) a job document.
func ParseJob(text string) (Job, error) {
	line := strings.TrimSpace(text)
	if strings.ContainsAny(line, "\n\r") {
		line = strings.SplitN(line, "\n", 2)[0]
		line = strings.TrimSpace(line)
	}
	cline := C.CString(line)
	defer C.free(unsafe.Pointer(cline))
	var cj C.ca_coord_job
	if rc := C.ca_coord_job_decode(&cj, cline); rc != C.CA_OK {
		return Job{}, fmt.Errorf("%w: %s", ErrJob, lastError())
	}
	return Job{
		text:     line,
		id:       uint64(cj.id),
		Order:    uint64(cj.order),
		DPBits:   int32(cj.dp_bits),
		Branches: uint32(cj.r),
		Negation: cj.negation_map != 0,
		UnitSize: uint64(cj.unit_size),
		Seed:     uint64(cj.seed),
	}, nil
}

// Ctx is everything derivable from a job: the group, the branch table,
// the distinguished-point mask.  It is immutable and safe to share.
type Ctx struct {
	job Job
	ptr *C.ca_coord_ctx
}

// OpenCtx derives the context for a job.
func OpenCtx(job Job) (*Ctx, error) {
	cline := C.CString(job.text)
	defer C.free(unsafe.Pointer(cline))
	var cj C.ca_coord_job
	if rc := C.ca_coord_job_decode(&cj, cline); rc != C.CA_OK {
		return nil, fmt.Errorf("%w: %s", ErrJob, lastError())
	}
	var ptr *C.ca_coord_ctx
	if rc := C.ca_coord_ctx_open(&ptr, &cj); rc != C.CA_OK {
		return nil, fmt.Errorf("cryptanalysis: cannot derive job context: %s", lastError())
	}
	ctx := &Ctx{job: job, ptr: ptr}
	runtime.SetFinalizer(ctx, func(c *Ctx) { c.Close() })
	return ctx, nil
}

// Job returns the document this context was derived from.
func (c *Ctx) Job() Job { return c.job }

// ExpectedSteps is sqrt(pi n / 2), over sqrt 2 with the negation map.
func (c *Ctx) ExpectedSteps() float64 {
	defer runtime.KeepAlive(c)
	return float64(C.ca_coord_expected_steps(c.ptr))
}

// ExpectedDPs is the number of distinguished points expected at the solve.
func (c *Ctx) ExpectedDPs() float64 {
	defer runtime.KeepAlive(c)
	return float64(C.ca_coord_expected_dps(c.ptr))
}

// Close releases the context.  Using it afterwards panics rather than
// reading freed memory.
func (c *Ctx) Close() {
	if c.ptr != nil {
		C.ca_coord_ctx_close(c.ptr)
		c.ptr = nil
		runtime.SetFinalizer(c, nil)
	}
}

// Outcome is what applying one check-in did.
type Outcome struct {
	Fresh       bool // this (peer, seq) had not been seen
	AcceptedDPs int
	RejectedDPs int // failed verification: the sender is lying or broken
	SolvedNow   bool
}

// Progress is the aggregate view, for a status page or a log line.
type Progress struct {
	Steps             uint64  `json:"steps"`
	DPsStored         uint64  `json:"dps"`
	DeadTrails        uint64  `json:"dead_trails"`
	UnitsCompleted    uint64  `json:"units_completed"`
	UnitsActive       uint64  `json:"units_active"`
	Peers             uint64  `json:"peers"`
	Checkins          uint64  `json:"checkins"`
	RejectedDPs       uint64  `json:"rejected_dps"`
	SterileCollisions uint64  `json:"sterile_collisions"`
	ExpectedSteps     float64 `json:"expected_steps"`
	Fraction          float64 `json:"fraction"`
	Solved            bool    `json:"solved"`
	Solution          uint64  `json:"solution"`
}

// State is the merge of every check-in seen: a CRDT, so merging is
// commutative, associative and idempotent and two states converge
// whatever order anything arrives in, however often.
//
// The C object has its own lock, so State is safe for concurrent use;
// the Go mutex here guards only the pointer's lifetime against Close.
type State struct {
	mu  sync.RWMutex
	ptr *C.ca_coord_state
	ctx *Ctx
}

// NewState creates an empty state for a job.
func NewState(ctx *Ctx) (*State, error) {
	var ptr *C.ca_coord_state
	if rc := C.ca_coord_state_init(&ptr, ctx.ptr); rc != C.CA_OK {
		return nil, fmt.Errorf("cryptanalysis: cannot create state: %s", lastError())
	}
	st := &State{ptr: ptr, ctx: ctx}
	runtime.SetFinalizer(st, func(s *State) { s.Close() })
	return st, nil
}

// Close releases the state.
func (s *State) Close() {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.ptr != nil {
		C.ca_coord_state_free(s.ptr)
		s.ptr = nil
		runtime.SetFinalizer(s, nil)
	}
}

// ApplyLine merges one encoded check-in, verifying every distinguished
// point it carries against the group: the point is a real element, it
// really is distinguished, and a*G + b*H really equals it.  Two scalar
// multiplications to check work worth 2^dp_bits steps, which is why a
// coordinator can accept records from strangers.
//
// A line for another job, or one claiming an unverifiable solution, is
// an error; a line whose points fail verification is not an error, it is
// an Outcome with RejectedDPs set.
func (s *State) ApplyLine(line string) (Outcome, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if s.ptr == nil {
		return Outcome{}, errors.New("cryptanalysis: state is closed")
	}
	cline := C.CString(line)
	defer C.free(unsafe.Pointer(cline))
	var ci C.ca_coord_checkin
	if rc := C.ca_coord_checkin_decode(&ci, cline); rc != C.CA_OK {
		return Outcome{}, fmt.Errorf("cryptanalysis: %s", lastError())
	}
	var oc C.ca_coord_outcome
	if rc := C.ca_coord_apply(s.ptr, s.ctx.ptr, &ci, C.uint64_t(nowSecs()), 1, &oc); rc != C.CA_OK {
		return Outcome{}, fmt.Errorf("cryptanalysis: %s", lastError())
	}
	return Outcome{
		Fresh:       oc.fresh != 0,
		AcceptedDPs: int(oc.accepted_dps),
		RejectedDPs: int(oc.rejected_dps),
		SolvedNow:   oc.solved_now != 0,
	}, nil
}

// Solution returns the discrete logarithm once some merge has produced
// and verified it.
func (s *State) Solution() (uint64, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if s.ptr == nil {
		return 0, false
	}
	var x C.uint64_t
	if C.ca_coord_solution(s.ptr, &x) == 0 {
		return 0, false
	}
	return uint64(x), true
}

// Progress reports the merged view.  leaseSecs decides which claims
// still count as active.
func (s *State) Progress(leaseSecs uint64) Progress {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if s.ptr == nil {
		return Progress{}
	}
	var p C.ca_coord_progress
	C.ca_coord_progress_get(s.ptr, s.ctx.ptr, C.uint64_t(nowSecs()), C.uint64_t(leaseSecs), &p)
	return Progress{
		Steps:             uint64(p.steps),
		DPsStored:         uint64(p.dps_stored),
		DeadTrails:        uint64(p.dead_trails),
		UnitsCompleted:    uint64(p.units_completed),
		UnitsActive:       uint64(p.units_active),
		Peers:             uint64(p.peers),
		Checkins:          uint64(p.checkins),
		RejectedDPs:       uint64(p.rejected_dps),
		SterileCollisions: uint64(p.sterile_collisions),
		ExpectedSteps:     float64(p.expected_steps),
		Fraction:          float64(p.fraction),
		Solved:            p.have_solution != 0,
		Solution:          uint64(p.solution),
	}
}

// LogEntry is one check-in in the append-only log, in its wire form.
type LogEntry struct {
	Peer string
	Seq  uint64
	Line string
}

// LogLen is the number of check-ins merged so far.
func (s *State) LogLen() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if s.ptr == nil {
		return 0
	}
	return int(C.ca_coord_log_count(s.ptr))
}

// LogAt copies one log entry.  ok is false if index is out of range.
func (s *State) LogAt(index int) (LogEntry, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if s.ptr == nil || index < 0 {
		return LogEntry{}, false
	}
	line := make([]byte, LineMax)
	peer := make([]byte, PeerMax)
	var seq C.uint64_t
	ok := C.ca_coord_log_get(s.ptr, C.size_t(index), (*C.char)(unsafe.Pointer(&line[0])),
		C.size_t(len(line)), (*C.char)(unsafe.Pointer(&peer[0])), C.size_t(len(peer)), &seq)
	if ok == 0 {
		return LogEntry{}, false
	}
	return LogEntry{
		Peer: cstr(peer),
		Seq:  uint64(seq),
		Line: cstr(line),
	}, true
}

// VersionVector maps each peer to the highest sequence number this state
// holds for it.  It is what makes one round trip enough: the holder of a
// vector is owed exactly the entries above it.
func (s *State) VersionVector() VersionVector {
	vv := VersionVector{}
	n := s.LogLen()
	for i := 0; i < n; i++ {
		if e, ok := s.LogAt(i); ok {
			if e.Seq > vv[e.Peer] {
				vv[e.Peer] = e.Seq
			}
		}
	}
	return vv
}

// DeltaFrom returns the check-in lines the holder of vv lacks, oldest
// first.
func (s *State) DeltaFrom(vv VersionVector) []string {
	var out []string
	n := s.LogLen()
	for i := 0; i < n; i++ {
		e, ok := s.LogAt(i)
		if !ok {
			continue
		}
		if e.Seq <= vv[e.Peer] {
			continue
		}
		out = append(out, e.Line)
	}
	return out
}

// VersionVector is a peer -> highest-sequence map.
type VersionVector map[string]uint64

// ParseVersionVector reads the wire form: "<peer>:<seq> …", with or
// without a leading "vv".  Unparsable entries are skipped rather than
// failing the whole line: a vector is a hint, and the worst a wrong one
// can do is cost a resend.
func ParseVersionVector(s string) VersionVector {
	vv := VersionVector{}
	for _, field := range strings.Fields(s) {
		if field == "vv" {
			continue
		}
		i := strings.LastIndex(field, ":")
		if i <= 0 {
			continue
		}
		name := field[:i]
		if len(name) >= PeerMax {
			continue
		}
		seq, err := strconv.ParseUint(field[i+1:], 10, 64)
		if err != nil {
			continue
		}
		if seq > vv[name] {
			vv[name] = seq
		}
	}
	return vv
}

// String is the wire form, without the leading keyword.
func (vv VersionVector) String() string {
	var b strings.Builder
	for peer, seq := range vv {
		b.WriteByte(' ')
		b.WriteString(peer)
		b.WriteByte(':')
		b.WriteString(strconv.FormatUint(seq, 10))
	}
	return b.String()
}

func cstr(b []byte) string {
	if i := strings.IndexByte(string(b), 0); i >= 0 {
		return string(b[:i])
	}
	return string(b)
}

func nowSecs() uint64 { return uint64(time.Now().Unix()) }

// GroupKind selects which concrete group a job is over.
type GroupKind int

// The two groups the library ships.
const (
	GroupZp GroupKind = 1
	GroupEC GroupKind = 2
)

// JobParams describes an instance to distribute.  DPBits < 0 takes the
// library default (a quarter of log2 n); Branches and UnitSize take 32
// and 256 at zero.
type JobParams struct {
	Kind         GroupKind
	P            uint64
	A, B         uint64 // curve coefficients (EC only)
	Order        uint64
	Base, Target Elem
	DPBits       int32
	Branches     uint32
	Negation     bool
	UnitSize     uint64
	Seed         uint64
}

// NewJob mints a job document.  Everything that changes the walk is
// hashed into the id, so two participants agree on the id exactly when
// they agree on the walk.
func NewJob(p *JobParams) (Job, error) {
	var base, target [4]C.uint64_t
	for i := 0; i < 4 && i < len(p.Base); i++ {
		base[i] = C.uint64_t(p.Base[i])
	}
	for i := 0; i < 4 && i < len(p.Target); i++ {
		target[i] = C.uint64_t(p.Target[i])
	}
	neg := C.int(0)
	if p.Negation {
		neg = 1
	}
	var cj C.ca_coord_job
	rc := C.ca_coord_job_init_raw(&cj, C.ca_group_kind(p.Kind), C.uint64_t(p.P), C.uint64_t(p.A),
		C.uint64_t(p.B), C.uint64_t(p.Order), &base[0], &target[0], C.int32_t(p.DPBits),
		C.uint32_t(p.Branches), neg, C.uint64_t(p.UnitSize), C.uint64_t(p.Seed))
	if rc != C.CA_OK {
		return Job{}, fmt.Errorf("cryptanalysis: cannot build the job: %s", lastError())
	}
	buf := make([]byte, LineMax)
	n := C.ca_coord_job_encode(&cj, (*C.char)(unsafe.Pointer(&buf[0])), C.size_t(len(buf)))
	if n == 0 {
		return Job{}, errors.New("cryptanalysis: job does not encode")
	}
	return ParseJob(string(buf[:n]))
}

// LaneParams tunes one lane: one goroutine's worth of sequential
// walking.  Peer is the lane's id and must be unique across the fleet
// ("<node>.<lane>" by convention).
type LaneParams struct {
	Peer         string
	CheckinEvery uint64
	LeaseSecs    uint64
	ClaimWindow  uint32
	MaxWalkers   uint64
	MaxUnits     uint64
}

// LaneResult is what a lane did before returning.
type LaneResult struct {
	Walkers        uint64
	Steps          uint64
	DPs            uint64
	DeadTrails     uint64
	UnitsCompleted uint64
	Checkins       uint64
	Solved         bool
	Solution       uint64
}

// RunLane claims units and walks them until the instance is solved or
// the budget is spent, merging its own check-ins into st.  Set
// MaxWalkers to bound one call: the check-ins it produced are then the
// log entries appended since, which the caller ships (see the agent's
// PublishLine).
//
// This blocks and releases no Go scheduler slot, so call it from a
// dedicated goroutine.
func RunLane(ctx *Ctx, st *State, p LaneParams) (LaneResult, error) {
	st.mu.RLock()
	defer st.mu.RUnlock()
	if st.ptr == nil {
		return LaneResult{}, errors.New("cryptanalysis: state is closed")
	}
	var cp C.ca_coord_lane_params
	C.ca_coord_lane_params_default(&cp, nil)
	if len(p.Peer) >= PeerMax {
		return LaneResult{}, fmt.Errorf("cryptanalysis: peer name is longer than %d", PeerMax-1)
	}
	for i := 0; i < len(p.Peer); i++ {
		cp.peer[i] = C.char(p.Peer[i])
	}
	cp.peer[len(p.Peer)] = 0
	if p.CheckinEvery != 0 {
		cp.checkin_every = C.uint64_t(p.CheckinEvery)
	}
	if p.LeaseSecs != 0 {
		cp.lease_secs = C.uint64_t(p.LeaseSecs)
	}
	if p.ClaimWindow != 0 {
		cp.claim_window = C.uint32_t(p.ClaimWindow)
	}
	cp.max_walkers = C.uint64_t(p.MaxWalkers)
	cp.max_units = C.uint64_t(p.MaxUnits)

	var res C.ca_coord_lane_result
	if rc := C.ca_coord_lane_run(ctx.ptr, st.ptr, &cp, nil, nil, nil, nil, &res); rc != C.CA_OK {
		return LaneResult{}, fmt.Errorf("cryptanalysis: %s", lastError())
	}
	return LaneResult{
		Walkers:        uint64(res.walkers),
		Steps:          uint64(res.steps),
		DPs:            uint64(res.dps),
		DeadTrails:     uint64(res.dead_trails),
		UnitsCompleted: uint64(res.units_completed),
		Checkins:       uint64(res.checkins),
		Solved:         res.have_solution != 0,
		Solution:       uint64(res.solution),
	}, nil
}

// Agent is the dial-out end of the reverse channel: one outbound
// connection, held open, reconnected with exponential backoff, merging
// what the coordinator pushes into the state it was given.  It needs no
// inbound reachability and no address of its own.
type Agent struct {
	ptr *C.ca_coord_agent
	mu  sync.Mutex
}

// AgentStats are the agent's own counters.
type AgentStats struct {
	Received, Sent, Rejected, Connects, Reconnects uint64
	Connected                                      bool
	LastError                                      string
}

// Dial starts an agent.  url is "http://host:port[/prefix]" or
// "host:port"; an https:// URL is refused rather than silently
// downgraded, because there is no TLS here -- put a terminator in front.
// It returns immediately; the first connection happens in the
// background, so an unreachable coordinator never delays the walk.
func Dial(url, token, peer string, ctx *Ctx, st *State) (*Agent, error) {
	st.mu.RLock()
	defer st.mu.RUnlock()
	if st.ptr == nil {
		return nil, errors.New("cryptanalysis: state is closed")
	}
	curl, ctok, cpeer := C.CString(url), C.CString(token), C.CString(peer)
	defer C.free(unsafe.Pointer(curl))
	defer C.free(unsafe.Pointer(ctok))
	defer C.free(unsafe.Pointer(cpeer))
	if token == "" {
		ctok = nil
	}
	var ptr *C.ca_coord_agent
	if rc := C.ca_coord_agent_start(&ptr, curl, ctok, cpeer, ctx.ptr, st.ptr); rc != C.CA_OK {
		return nil, fmt.Errorf("cryptanalysis: cannot start the agent: %s", lastError())
	}
	return &Agent{ptr: ptr}, nil
}

// PublishLine queues an encoded check-in for the coordinator.  It is
// non-blocking: if the connection is down the line waits for the next
// one.
func (a *Agent) PublishLine(line string) error {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.ptr == nil {
		return errors.New("cryptanalysis: agent is stopped")
	}
	cline := C.CString(line)
	defer C.free(unsafe.Pointer(cline))
	var ci C.ca_coord_checkin
	if rc := C.ca_coord_checkin_decode(&ci, cline); rc != C.CA_OK {
		return fmt.Errorf("cryptanalysis: %s", lastError())
	}
	C.ca_coord_agent_publish(a.ptr, &ci)
	return nil
}

// Flush waits until the queue has drained, or the timeout passes.  Call
// it before exiting: the queue lives in this process, and the last
// check-in is the one carrying the solution.
func (a *Agent) Flush(timeout time.Duration) bool {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.ptr == nil {
		return true
	}
	return C.ca_coord_agent_flush(a.ptr, C.uint64_t(timeout.Milliseconds())) != 0
}

// Stats snapshots the agent's counters.
func (a *Agent) Stats() AgentStats {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.ptr == nil {
		return AgentStats{}
	}
	var s C.ca_coord_agent_stats
	C.ca_coord_agent_stats_get(a.ptr, &s)
	return AgentStats{
		Received:   uint64(s.received),
		Sent:       uint64(s.sent),
		Rejected:   uint64(s.rejected),
		Connects:   uint64(s.connects),
		Reconnects: uint64(s.reconnects),
		Connected:  s.connected != 0,
		LastError:  C.GoString(&s.last_error[0]),
	}
}

// Stop closes the connection and releases the agent.
func (a *Agent) Stop() {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.ptr != nil {
		C.ca_coord_agent_stop(a.ptr)
		a.ptr = nil
	}
}
