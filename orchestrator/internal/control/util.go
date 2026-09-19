package control

import (
	"crypto/rand"
	"encoding/binary"
	"sync/atomic"
)

// atomicCounter is a counter that is read from the metrics handler while
// request handlers increment it.
type atomicCounter struct{ v atomic.Uint64 }

func (c *atomicCounter) add(n uint64) { c.v.Add(n) }
func (c *atomicCounter) get() uint64  { return c.v.Load() }

// randomSeed draws a campaign seed from the operating system.
//
// crypto/rand rather than math/rand, for one blunt reason: two campaigns
// that accidentally share a seed share a walk function, and their corpora
// would then merge into each other's -- producing collisions between points
// from different instances, which solve nothing and look like a working
// search until somebody checks the answer.  A seeded PRNG that two control
// planes start identically (a container image, a fixed clock, a restored
// snapshot) is exactly how that happens.
func randomSeed() uint64 {
	var b [8]byte
	if _, err := rand.Read(b[:]); err != nil {
		// The OS entropy source failing is not something to paper over with
		// a timestamp: a predictable campaign seed is a correctness problem,
		// not a performance one, so the caller gets zero and refuses.
		return 0
	}
	s := binary.LittleEndian.Uint64(b[:])
	if s == 0 {
		s = 1
	}
	return s
}
