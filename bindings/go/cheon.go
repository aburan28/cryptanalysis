package cryptanalysis

import "runtime"

// Cheon recovers alpha from (gen, gen^alpha, gen^(alpha^d)) using Cheon's
// attack on the strong Diffie-Hellman problem, where d divides the group
// order minus one (see [CheonBestDivisor]).  maxExps bounds the number of
// exponentiations (0 => unlimited; exceeding it yields ErrLimit).
func (g *Group) Cheon(gen, gAlpha, gAlphaD Elem, d, maxExps uint64) (uint64, Stats, error) {
	defer runtime.KeepAlive(g)
	return ffiCheon(g.handle(), gen, gAlpha, gAlphaD, d, maxExps)
}

// CheonInstance builds a test instance: it returns gen^alpha and
// gen^(alpha^d).
func (g *Group) CheonInstance(gen Elem, alpha, d uint64) (gAlpha, gAlphaD Elem, err error) {
	defer runtime.KeepAlive(g)
	return ffiCheonInstance(g.handle(), gen, alpha, d)
}

// CheonBestDivisor picks the divisor d of p-1 that minimises the cost of
// Cheon's attack in a group of prime order p and returns it together with
// the estimated number of exponentiations.
func CheonBestDivisor(p uint64) (d uint64, costExps float64) { return ffiCheonBestDivisor(p) }
