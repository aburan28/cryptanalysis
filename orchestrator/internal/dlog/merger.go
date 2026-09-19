package dlog

import (
	"encoding/binary"
	"errors"
	"math"
	"sync"
)

// PointBytes is one wire record: w0, w1, a, b as little-endian uint64s.
const PointBytes = 32

// Record is a distinguished point as an agent reports it: the element's
// canonical coordinates and the exponents with Y = a*G + b*H.
type Record struct {
	W0, W1 uint64
	A, B   uint64
}

// DecodeRecord reads one 32-byte record.
func DecodeRecord(b []byte) (Record, error) {
	if len(b) < PointBytes {
		return Record{}, errors.New("short record")
	}
	return Record{
		W0: binary.LittleEndian.Uint64(b[0:8]),
		W1: binary.LittleEndian.Uint64(b[8:16]),
		A:  binary.LittleEndian.Uint64(b[16:24]),
		B:  binary.LittleEndian.Uint64(b[24:32]),
	}, nil
}

// EncodeRecord writes one 32-byte record.
func EncodeRecord(dst []byte, r Record) {
	binary.LittleEndian.PutUint64(dst[0:8], r.W0)
	binary.LittleEndian.PutUint64(dst[8:16], r.W1)
	binary.LittleEndian.PutUint64(dst[16:24], r.A)
	binary.LittleEndian.PutUint64(dst[24:32], r.B)
}

// Merger holds a campaign's corpus and solves it.
//
// It is the one piece of the control plane that is not allowed to be
// approximate.  Two disciplines:
//
//   - Nothing enters the corpus unverified.  A record must be a real group
//     element, really distinguished under this campaign's cutoff, and must
//     really satisfy Y = a*G + b*H.  The check costs two scalar
//     multiplications against the 2^dpBits walk steps that produced the
//     point, so it is affordable even when every agent is assumed hostile.
//   - Nothing leaves it unverified either.  A collision gives a candidate
//     x, and the candidate is checked against x*G == H before it is
//     reported.  A 64-bit hash collision, a buggy walker or a malicious
//     agent therefore costs a rejected point, never a wrong answer.
type Merger struct {
	mu sync.RWMutex

	g            *Group
	base, target Point
	dpMask       uint64
	verify       bool

	seen map[[2]uint64]Record

	solved   bool
	x        uint64
	added    uint64
	dupes    uint64
	rejected uint64
	collided uint64
}

// NewMerger builds a merger for one campaign.  dpBits is the campaign's
// distinguished-point cutoff; verify should only be false for a corpus this
// process produced itself.
func NewMerger(g *Group, base, target Point, dpBits int32, verify bool) (*Merger, error) {
	if dpBits < 0 || dpBits > 58 {
		return nil, errors.New("dpBits out of range")
	}
	if !g.Valid(base) || !g.Valid(target) {
		return nil, errors.New("base or target is not in the group")
	}
	var mask uint64
	if dpBits > 0 {
		mask = 1<<uint(dpBits) - 1
	}
	return &Merger{
		g: g, base: base, target: target, dpMask: mask, verify: verify,
		seen: make(map[[2]uint64]Record, 1024),
	}, nil
}

func (m *Merger) point(r Record) Point {
	if m.g.Kind == Zp {
		return Point{X: r.W0}
	}
	return Point{X: r.W0, Y: r.W1}
}

// admissible is the gate every record passes through.
func (m *Merger) admissible(r Record) bool {
	if r.A >= m.g.Order || r.B >= m.g.Order {
		return false
	}
	pt := m.point(r)
	if !m.g.Valid(pt) || m.g.IsIdentity(pt) {
		return false
	}
	if m.g.Hash(pt)&m.dpMask != 0 {
		return false
	}
	sum := m.g.Add(m.g.ScalarMul(m.base, r.A), m.g.ScalarMul(m.target, r.B))
	return m.g.Equal(sum, pt)
}

// Counts is what one upload did to the corpus.
type Counts struct {
	Accepted   uint64
	Duplicates uint64
	Rejected   uint64
}

// AddRecords ingests records and returns what happened to them.  It never
// returns an error for a bad record: an agent that submits rubbish is a fact
// about the fleet, reported in Rejected, not a failure of the server.
func (m *Merger) AddRecords(rs []Record) Counts {
	m.mu.Lock()
	defer m.mu.Unlock()
	var c Counts
	for _, r := range rs {
		if m.verify && !m.admissible(r) {
			c.Rejected++
			m.rejected++
			continue
		}
		key := [2]uint64{r.W0, r.W1}
		prev, ok := m.seen[key]
		if !ok {
			m.seen[key] = r
			c.Accepted++
			m.added++
			continue
		}
		if prev.A == r.A && prev.B == r.B {
			// The same trail reported twice: a replayed unit, a retried
			// upload, or a walk meeting its own earlier point.
			c.Duplicates++
			m.dupes++
			continue
		}
		c.Accepted++
		m.added++
		m.collided++
		if !m.solved {
			m.trySolve(prev, r)
		}
	}
	return c
}

// AddBytes ingests a flat array of records.  A trailing partial record is
// reported rather than guessed at: that is what a killed agent's upload
// looks like, and inventing the missing bytes would put a point in the
// corpus that no walk ever produced.
func (m *Merger) AddBytes(b []byte) (Counts, error) {
	whole := len(b) / PointBytes
	rs := make([]Record, 0, whole)
	for i := 0; i < whole; i++ {
		r, err := DecodeRecord(b[i*PointBytes:])
		if err != nil {
			return Counts{}, err
		}
		rs = append(rs, r)
	}
	c := m.AddRecords(rs)
	if len(b)%PointBytes != 0 {
		return c, errors.New("trailing partial record")
	}
	return c, nil
}

// trySolve turns a collision into a discrete logarithm.
//
// (a1 - a2) + (b1 - b2) x == 0 (mod n), so (b1 - b2) x == a2 - a1.  When
// b1 - b2 shares a factor with n the congruence has gcd solutions and each
// is tried; n is prime in the cases that matter, and this is the path that
// keeps the composite ones correct rather than silently wrong.
func (m *Merger) trySolve(p, q Record) bool {
	n := m.g.Order
	c := subMod(p.B, q.B, n)
	d := subMod(q.A, p.A, n)
	if c == 0 {
		return false
	}
	gg := gcd(c, n)
	if d%gg != 0 {
		return false
	}
	nn := n / gg
	inv := invMod((c/gg)%nn, nn)
	if inv == 0 && nn != 1 {
		return false
	}
	x0 := mulMod((d/gg)%nn, inv, nn)
	tries := gg
	if tries > 65536 {
		tries = 65536
	}
	for k := uint64(0); k < tries; k++ {
		x := x0 + k*nn
		if x >= n {
			break
		}
		if m.g.Equal(m.g.ScalarMul(m.base, x), m.target) {
			m.solved = true
			m.x = x
			return true
		}
	}
	return false
}

// Solved reports the verified discrete logarithm once there is one.
func (m *Merger) Solved() (uint64, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.x, m.solved
}

// Stats is the corpus as the status endpoint reports it.
type Stats struct {
	Stored     uint64
	Accepted   uint64
	Duplicates uint64
	Rejected   uint64
	Collisions uint64
	Solved     bool
	X          uint64
}

func (m *Merger) Stats() Stats {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return Stats{
		Stored: uint64(len(m.seen)), Accepted: m.added, Duplicates: m.dupes,
		Rejected: m.rejected, Collisions: m.collided, Solved: m.solved, X: m.x,
	}
}

// ExpectedPoints is about 1.25*sqrt(n)/2^dpBits, the corpus a full search
// produces.  What a control plane sizes its storage from, and what the
// status page's progress fraction is against.
func ExpectedPoints(order uint64, dpBits int32) float64 {
	return ExpectedSteps(order) / float64(uint64(1)<<uint(dpBits))
}

// ExpectedSteps is the expected work of a full search, 1.25*sqrt(n) steps.
// It is an expectation and not a deadline: the chance of not having
// collided after c times this is about exp(-pi c^2 / 4), which is still 17%
// at 1.5x.
func ExpectedSteps(order uint64) float64 {
	return 1.25 * sqrtU64(order)
}

func sqrtU64(n uint64) float64 {
	if n == 0 {
		return 0
	}
	// float64 has 53 bits of mantissa and n has up to 64, so the square root
	// is computed in floating point and then corrected by one Newton step in
	// integers, which is exact enough for a size estimate.
	x := float64(n)
	s := uint64(math.Sqrt(x))
	for s > 0 && s > n/s {
		s--
	}
	for (s + 1) <= n/(s+1) {
		s++
	}
	return float64(s)
}
