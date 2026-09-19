package cryptanalysis

import "runtime"

// ICMethod selects the relation collector of the index calculus.
type ICMethod int

// Relation collection methods (mirroring ca_ic_method).
const (
	ICLinearSieve    ICMethod = 0 // Coppersmith-Odlyzko-Schroeppel linear sieve (default)
	ICRandomExponent ICMethod = 1 // textbook random exponents + trial division
)

// ICParams mirrors ca_ic_params.  Zero values mean "automatic"; start from
// [DefaultICParams].  A nil *ICParams means library defaults.
type ICParams struct {
	Method           ICMethod
	FactorBaseBound  uint32 // B; 0 => auto from the size of p
	SieveRadius      uint32 // C (linear sieve only); 0 => auto
	Threads          uint32 // relation collection threads; 0 => 1
	ExtraRelations   uint32 // relations beyond #unknowns; 0 => auto
	Seed             uint64 // 0 => random
	MaxRelationTries uint64 // random-exponent method: abort bound (0 = none)
	Verbose          bool   // stage reports on stderr
}

// DefaultICParams returns the library's default index-calculus parameters.
func DefaultICParams() ICParams { return defaultICParams() }

// ICAutoParams returns the automatic (B, C) choice for a modulus of the
// given bit length.
func ICAutoParams(bits uint) (factorBaseBound, sieveRadius uint32) { return icAutoParams(bits) }

// ICStats mirrors ca_ic_stats.
type ICStats struct {
	FactorBaseSize    uint32 // primes in the factor base
	Unknowns          uint32 // columns of the relation matrix
	Relations         uint32 // relations collected
	VerifiedLogs      uint32 // factor-base logs verified
	SieveCandidates   uint64 // values passed to trial division
	SmoothTests       uint64 // random-exponent method: candidates tested
	SieveSeconds      float64
	LinalgSeconds     float64
	TotalSeconds      float64
	LanczosIterations uint32
	Threads           uint32
}

// ICSolve finds x with g^x == h (mod p) by index calculus (one-shot: the
// factor base is precomputed and thrown away).  Use [NewICContext] to
// compute several logarithms to the same base.
func ICSolve(p, g, h uint64, params *ICParams) (uint64, ICStats, error) {
	return ffiICSolve(p, g, h, params)
}

// ICContext holds the precomputed factor-base logarithms for a modulus p
// and base g, so that individual logarithms are cheap.
type ICContext struct {
	h     icHandle
	stats ICStats
}

// NewICContext runs the precomputation (relation collection and linear
// algebra) for logarithms to base g modulo the odd prime p.
func NewICContext(p, g uint64, params *ICParams) (*ICContext, error) {
	h, st, err := icPrecompute(p, g, params)
	if err != nil {
		return nil, err
	}
	c := &ICContext{h: h, stats: st}
	runtime.SetFinalizer(c, (*ICContext).Close)
	return c, nil
}

// Close frees the context; safe to call more than once.
func (c *ICContext) Close() {
	if c.h != nil {
		icFree(c.h)
		c.h = nil
		runtime.SetFinalizer(c, nil)
	}
}

func (c *ICContext) handle() icHandle {
	if c.h == nil {
		panic(ErrClosed)
	}
	return c.h
}

// Stats returns the statistics of the precomputation.
func (c *ICContext) Stats() ICStats { return c.stats }

// Log returns x in [0, ord(g)) with g^x == h (mod p).
func (c *ICContext) Log(h uint64) (uint64, Stats, error) {
	defer runtime.KeepAlive(c)
	return icLog(c.handle(), h)
}

// Modulus returns p.
func (c *ICContext) Modulus() uint64 { defer runtime.KeepAlive(c); return icModulus(c.handle()) }

// FactorBaseSize returns the number of primes in the factor base.
func (c *ICContext) FactorBaseSize() uint32 {
	defer runtime.KeepAlive(c)
	return icFactorBaseSize(c.handle())
}

// PrimitiveRoot returns the primitive root the logarithms are computed
// with respect to internally.
func (c *ICContext) PrimitiveRoot() uint64 {
	defer runtime.KeepAlive(c)
	return icPrimitiveRoot(c.handle())
}

// FactorBaseLog returns the i-th factor-base prime and its logarithm with
// respect to [ICContext.PrimitiveRoot]; known is false when the logarithm
// was not determined.
func (c *ICContext) FactorBaseLog(i uint32) (prime uint32, log uint64, known bool) {
	defer runtime.KeepAlive(c)
	return icFactorBaseLog(c.handle(), i)
}
