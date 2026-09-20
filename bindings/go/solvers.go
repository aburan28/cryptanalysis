package cryptanalysis

import "runtime"

// BSGS runs baby-step giant-step for base^x = target with x in [lo, hi]
// (lo == hi == 0 means the whole group, using the context order).
func (g *Group) BSGS(base, target Elem, lo, hi uint64, opts *Options) (uint64, Stats, error) {
	defer runtime.KeepAlive(g)
	return ffiBSGS(g.handle(), base, target, lo, hi, opts)
}

// Kangaroo runs Pollard's kangaroo (lambda) method for x in [lo, hi].
func (g *Group) Kangaroo(base, target Elem, lo, hi uint64, opts *Options) (uint64, Stats, error) {
	defer runtime.KeepAlive(g)
	return ffiKangaroo(g.handle(), base, target, lo, hi, opts)
}

// Grumpy runs the Bernstein-Lange "two grumpy giants and a baby" method
// for x in [lo, hi].
func (g *Group) Grumpy(base, target Elem, lo, hi uint64, opts *Options) (uint64, Stats, error) {
	defer runtime.KeepAlive(g)
	return ffiGrumpy(g.handle(), base, target, lo, hi, opts)
}

// Rho runs (parallel) Pollard rho on the whole group; the context order
// must be the order of base.
func (g *Group) Rho(base, target Elem, opts *Options) (uint64, Stats, error) {
	defer runtime.KeepAlive(g)
	return ffiRho(g.handle(), base, target, opts)
}

// Dlog solves base^x = target with Pohlig-Hellman on top of the solver
// selected by opts.Solver (auto by default).  The context order must be
// the order of base.
func (g *Group) Dlog(base, target Elem, opts *Options) (uint64, Stats, error) {
	defer runtime.KeepAlive(g)
	return ffiDlog(g.handle(), base, target, opts)
}

// Precomp solves base^x = target with the Bernstein-Lange free-precomputation
// method: a one-time table for base (built with the given number of worker
// threads) then this target solved online.  It is one-shot -- the table is
// built, used once and freed -- so the returned Stats cover the whole n^2/3
// build plus the n^1/3 online phase.  Pass dpBits < 0, tableSize 0, coverage 0
// and threads 0 for the defaults; seed 0 is random.  base must generate the
// whole group of order g.Order().
func (g *Group) Precomp(base, target Elem, dpBits int32, tableSize uint64, coverage float64,
	threads uint32, seed uint64) (uint64, Stats, error) {
	defer runtime.KeepAlive(g)
	return ffiPrecomp(g.handle(), base, target, dpBits, tableSize, coverage, threads, seed)
}
