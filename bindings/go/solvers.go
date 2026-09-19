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
