package cryptanalysis

// This is the only file in the package that imports "C".  It compiles the
// C library from ../../src (through the src_*.c wrappers next to this file)
// and exposes a thin, unexported layer over the flat ABI in ca_ffi.h.  The
// idiomatic API lives in the other files and only ever sees plain Go types.

/*
#cgo CFLAGS: -O3 -std=gnu11 -D_GNU_SOURCE -DCA_BUILDING -I${SRCDIR}/../../include -I${SRCDIR}/../../src
#cgo LDFLAGS: -lpthread -lm
#include <stdlib.h>
#include <cryptanalysis/cryptanalysis.h>
*/
import "C"

import (
	"fmt"
	"math"
	"runtime"
	"unsafe"
)

// ctxHandle is an opaque group context (ca_ctx *).
type ctxHandle = *C.ca_ctx

// icHandle is an opaque index-calculus context (ca_ic_ctx *).
type icHandle = *C.ca_ic_ctx

func init() {
	// Layout sanity check: the POD structs the Go side converts field by
	// field must have the size the compiled library expects.
	check := func(name string, got, want uintptr) {
		if got != want {
			panic(fmt.Sprintf("cryptanalysis: %s size mismatch: cgo %d, library %d", name, got, want))
		}
	}
	check("ca_ffi_options", C.sizeof_struct_ca_ffi_options, uintptr(C.ca_ffi_options_size()))
	check("ca_stats", C.sizeof_struct_ca_stats, uintptr(C.ca_stats_size()))
	check("ca_ic_params", C.sizeof_struct_ca_ic_params, uintptr(C.ca_ic_params_size()))
	check("ca_ic_stats", C.sizeof_struct_ca_ic_stats, uintptr(C.ca_ic_stats_size()))
}

// layoutSizes reports (cgo sizeof, library sizeof) for the four POD structs;
// used by the tests to double-check the init-time assertion.
func layoutSizes() [4][2]uintptr {
	return [4][2]uintptr{
		{C.sizeof_struct_ca_ffi_options, uintptr(C.ca_ffi_options_size())},
		{C.sizeof_struct_ca_stats, uintptr(C.ca_stats_size())},
		{C.sizeof_struct_ca_ic_params, uintptr(C.ca_ic_params_size())},
		{C.sizeof_struct_ca_ic_stats, uintptr(C.ca_ic_stats_size())},
	}
}

// ---- helpers --------------------------------------------------------------

// ep returns the C view of an element's four words.
func ep(e *Elem) *C.uint64_t { return (*C.uint64_t)(unsafe.Pointer(&e[0])) }

// lastError reads the thread-local ca_last_error().  Callers must hold the
// OS thread (see withThread) so that the message belongs to the call that
// just failed.
func lastError() string { return C.GoString(C.ca_last_error()) }

// withThread pins the goroutine to its OS thread for the duration of f.
// ca_last_error() is thread-local, so a failing C call and the subsequent
// read of its message must happen on the same thread.
func withThread(f func()) {
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	f()
}

// statusErr converts a C return code (plus the thread-local message) into
// an error; it returns nil for CA_OK.  Must be called under withThread.
func statusErr(rc C.int) error {
	if rc == 0 {
		return nil
	}
	return &Error{Status: Status(rc), Msg: lastError()}
}

func statusString(s Status) string {
	return C.GoString(C.ca_status_string(C.ca_status(s)))
}

func version() string { return C.GoString(C.ca_version()) }

// ---- options / stats conversion ------------------------------------------

func (o *Options) toC(c *C.ca_ffi_options) {
	*c = C.ca_ffi_options{}
	c.threads = C.uint32_t(o.Threads)
	c.seed = C.uint64_t(o.Seed)
	c.max_ops = C.uint64_t(o.MaxOps)
	c.bsgs_table_size = C.uint64_t(o.BSGSTableSize)
	c.rho_r = C.uint32_t(o.RhoR)
	c.rho_dp_bits = C.int32_t(o.RhoDPBits)
	c.rho_walks_per_thread = C.uint32_t(o.RhoWalksPerThread)
	if o.RhoNegationMap {
		c.rho_negation_map = 1
	}
	c.rho_max_table_entries = C.uint64_t(o.RhoMaxTableEntries)
	c.kangaroo_herd_size = C.uint32_t(o.KangarooHerdSize)
	c.kangaroo_dp_bits = C.int32_t(o.KangarooDPBits)
	c.kangaroo_jumps = C.uint32_t(o.KangarooJumps)
	c.grumpy_m = C.uint64_t(o.GrumpyM)
	c.grumpy_alpha = C.double(o.GrumpyAlpha)
	c.solver = C.int32_t(o.Solver)
	c.bsgs_max_prime = C.uint64_t(o.BSGSMaxPrime)
}

func optionsFromC(c *C.ca_ffi_options) Options {
	return Options{
		Threads:            uint32(c.threads),
		Seed:               uint64(c.seed),
		MaxOps:             uint64(c.max_ops),
		BSGSTableSize:      uint64(c.bsgs_table_size),
		RhoR:               uint32(c.rho_r),
		RhoDPBits:          int32(c.rho_dp_bits),
		RhoWalksPerThread:  uint32(c.rho_walks_per_thread),
		RhoNegationMap:     c.rho_negation_map != 0,
		RhoMaxTableEntries: uint64(c.rho_max_table_entries),
		KangarooHerdSize:   uint32(c.kangaroo_herd_size),
		KangarooDPBits:     int32(c.kangaroo_dp_bits),
		KangarooJumps:      uint32(c.kangaroo_jumps),
		GrumpyM:            uint64(c.grumpy_m),
		GrumpyAlpha:        float64(c.grumpy_alpha),
		Solver:             Solver(c.solver),
		BSGSMaxPrime:       uint64(c.bsgs_max_prime),
	}
}

func defaultOptions() Options {
	var c C.ca_ffi_options
	C.ca_ffi_options_default(&c)
	return optionsFromC(&c)
}

// cOptions returns a pointer to a C options struct filled from o, or NULL
// when o is nil (the library then uses its defaults).
func cOptions(o *Options, buf *C.ca_ffi_options) *C.ca_ffi_options {
	if o == nil {
		return nil
	}
	o.toC(buf)
	return buf
}

func statsFromC(c *C.ca_stats) Stats {
	return Stats{
		GroupOps:     uint64(c.group_ops),
		Iterations:   uint64(c.iterations),
		TableEntries: uint64(c.table_entries),
		Collisions:   uint64(c.collisions),
		BytesPeak:    uint64(c.bytes_peak),
		Seconds:      float64(c.seconds),
		Threads:      uint32(c.threads),
	}
}

func (p *ICParams) toC(c *C.ca_ic_params) {
	*c = C.ca_ic_params{}
	c.method = C.ca_ic_method(p.Method)
	c.factor_base_bound = C.uint32_t(p.FactorBaseBound)
	c.sieve_radius = C.uint32_t(p.SieveRadius)
	c.threads = C.uint32_t(p.Threads)
	c.extra_relations = C.uint32_t(p.ExtraRelations)
	c.seed = C.uint64_t(p.Seed)
	c.max_relation_tries = C.uint64_t(p.MaxRelationTries)
	if p.Verbose {
		c.verbose = 1
	}
}

func icParamsFromC(c *C.ca_ic_params) ICParams {
	return ICParams{
		Method:           ICMethod(c.method),
		FactorBaseBound:  uint32(c.factor_base_bound),
		SieveRadius:      uint32(c.sieve_radius),
		Threads:          uint32(c.threads),
		ExtraRelations:   uint32(c.extra_relations),
		Seed:             uint64(c.seed),
		MaxRelationTries: uint64(c.max_relation_tries),
		Verbose:          c.verbose != 0,
	}
}

func defaultICParams() ICParams {
	var c C.ca_ic_params
	C.ca_ic_params_default(&c)
	return icParamsFromC(&c)
}

func cICParams(p *ICParams, buf *C.ca_ic_params) *C.ca_ic_params {
	if p == nil {
		return nil
	}
	p.toC(buf)
	return buf
}

func icStatsFromC(c *C.ca_ic_stats) ICStats {
	return ICStats{
		FactorBaseSize:    uint32(c.factor_base_size),
		Unknowns:          uint32(c.unknowns),
		Relations:         uint32(c.relations),
		VerifiedLogs:      uint32(c.verified_logs),
		SieveCandidates:   uint64(c.sieve_candidates),
		SmoothTests:       uint64(c.smooth_tests),
		SieveSeconds:      float64(c.sieve_seconds),
		LinalgSeconds:     float64(c.linalg_seconds),
		TotalSeconds:      float64(c.total_seconds),
		LanczosIterations: uint32(c.lanczos_iterations),
		Threads:           uint32(c.threads),
	}
}

// ---- groups ---------------------------------------------------------------

func ctxNewZp(p, order uint64) (h ctxHandle, err error) {
	withThread(func() {
		h = C.ca_ctx_new_zp(C.uint64_t(p), C.uint64_t(order))
		if h == nil {
			err = &Error{Status: StatusInvalid, Msg: lastError()}
		}
	})
	return
}

func ctxNewEC(p, a, b, order uint64) (h ctxHandle, err error) {
	withThread(func() {
		h = C.ca_ctx_new_ec(C.uint64_t(p), C.uint64_t(a), C.uint64_t(b), C.uint64_t(order))
		if h == nil {
			err = &Error{Status: StatusInvalid, Msg: lastError()}
		}
	})
	return
}

func ctxFree(h ctxHandle)                  { C.ca_ctx_free(h) }
func ctxKind(h ctxHandle) Kind             { return Kind(C.ca_ctx_kind(h)) }
func ctxP(h ctxHandle) uint64              { return uint64(C.ca_ctx_p(h)) }
func ctxOrder(h ctxHandle) uint64          { return uint64(C.ca_ctx_order(h)) }
func ctxCofactor(h ctxHandle) uint64       { return uint64(C.ca_ctx_cofactor(h)) }
func ctxCurveA(h ctxHandle) uint64         { return uint64(C.ca_ctx_curve_a(h)) }
func ctxCurveB(h ctxHandle) uint64         { return uint64(C.ca_ctx_curve_b(h)) }
func ctxSetOrder(h ctxHandle, n, c uint64) { C.ca_ctx_set_order(h, C.uint64_t(n), C.uint64_t(c)) }

func ctxValidate(h ctxHandle, w Elem) bool { return C.ca_ctx_validate(h, ep(&w)) != 0 }

func ctxIdentity(h ctxHandle) Elem {
	var out Elem
	C.ca_ctx_identity(h, ep(&out))
	return out
}

func ctxIsIdentity(h ctxHandle, w Elem) bool { return C.ca_ctx_is_identity(h, ep(&w)) != 0 }

func ctxEqual(h ctxHandle, a, b Elem) bool { return C.ca_ctx_equal(h, ep(&a), ep(&b)) != 0 }

func ctxOp(h ctxHandle, a, b Elem) (out Elem, err error) {
	withThread(func() { err = statusErr(C.ca_ctx_op(h, ep(&out), ep(&a), ep(&b))) })
	return
}

func ctxInv(h ctxHandle, a Elem) (out Elem, err error) {
	withThread(func() { err = statusErr(C.ca_ctx_inv(h, ep(&out), ep(&a))) })
	return
}

func ctxMul(h ctxHandle, a Elem, k uint64) (out Elem, err error) {
	withThread(func() { err = statusErr(C.ca_ctx_mul(h, ep(&out), ep(&a), C.uint64_t(k))) })
	return
}

func ctxElemOrder(h ctxHandle, a Elem) (order uint64, err error) {
	var o C.uint64_t
	withThread(func() { err = statusErr(C.ca_ctx_elem_order(h, ep(&a), &o)) })
	return uint64(o), err
}

func ctxFindGenerator(h ctxHandle, seed uint64) (out Elem, err error) {
	withThread(func() { err = statusErr(C.ca_ctx_find_generator(h, ep(&out), C.uint64_t(seed))) })
	return
}

func ctxRandomElement(h ctxHandle, seed uint64) (out Elem, err error) {
	withThread(func() { err = statusErr(C.ca_ctx_random_element(h, ep(&out), C.uint64_t(seed))) })
	return
}

func ctxLiftX(h ctxHandle, x uint64) (out Elem, err error) {
	withThread(func() { err = statusErr(C.ca_ctx_lift_x(h, ep(&out), C.uint64_t(x))) })
	return
}

func ecOrder(p, a, b uint64) (n uint64, err error) {
	var o C.uint64_t
	withThread(func() {
		err = statusErr(C.ca_ec_order(C.uint64_t(p), C.uint64_t(a), C.uint64_t(b), &o))
	})
	return uint64(o), err
}

// ---- solvers --------------------------------------------------------------

// intervalSolver is the common shape of ca_ffi_bsgs/kangaroo/grumpy.
type intervalSolver func(*C.ca_ctx, *C.uint64_t, *C.uint64_t, C.uint64_t, C.uint64_t,
	*C.ca_ffi_options, *C.uint64_t, *C.ca_stats) C.int

func runInterval(fn intervalSolver, h ctxHandle, base, target Elem, lo, hi uint64,
	opts *Options) (x uint64, st Stats, err error) {
	var cx C.uint64_t
	var cst C.ca_stats
	var buf C.ca_ffi_options
	o := cOptions(opts, &buf)
	withThread(func() {
		err = statusErr(fn(h, ep(&base), ep(&target), C.uint64_t(lo), C.uint64_t(hi), o, &cx, &cst))
	})
	return uint64(cx), statsFromC(&cst), err
}

// groupSolver is the common shape of ca_ffi_rho/dlog.
type groupSolver func(*C.ca_ctx, *C.uint64_t, *C.uint64_t, *C.ca_ffi_options,
	*C.uint64_t, *C.ca_stats) C.int

func runGroup(fn groupSolver, h ctxHandle, base, target Elem, opts *Options) (x uint64, st Stats, err error) {
	var cx C.uint64_t
	var cst C.ca_stats
	var buf C.ca_ffi_options
	o := cOptions(opts, &buf)
	withThread(func() {
		err = statusErr(fn(h, ep(&base), ep(&target), o, &cx, &cst))
	})
	return uint64(cx), statsFromC(&cst), err
}

func ffiBSGS(h ctxHandle, base, target Elem, lo, hi uint64, o *Options) (uint64, Stats, error) {
	return runInterval(func(c *C.ca_ctx, b, t *C.uint64_t, lo, hi C.uint64_t, o *C.ca_ffi_options,
		x *C.uint64_t, s *C.ca_stats) C.int {
		return C.ca_ffi_bsgs(c, b, t, lo, hi, o, x, s)
	}, h, base, target, lo, hi, o)
}

func ffiKangaroo(h ctxHandle, base, target Elem, lo, hi uint64, o *Options) (uint64, Stats, error) {
	return runInterval(func(c *C.ca_ctx, b, t *C.uint64_t, lo, hi C.uint64_t, o *C.ca_ffi_options,
		x *C.uint64_t, s *C.ca_stats) C.int {
		return C.ca_ffi_kangaroo(c, b, t, lo, hi, o, x, s)
	}, h, base, target, lo, hi, o)
}

func ffiGrumpy(h ctxHandle, base, target Elem, lo, hi uint64, o *Options) (uint64, Stats, error) {
	return runInterval(func(c *C.ca_ctx, b, t *C.uint64_t, lo, hi C.uint64_t, o *C.ca_ffi_options,
		x *C.uint64_t, s *C.ca_stats) C.int {
		return C.ca_ffi_grumpy(c, b, t, lo, hi, o, x, s)
	}, h, base, target, lo, hi, o)
}

func ffiRho(h ctxHandle, base, target Elem, o *Options) (uint64, Stats, error) {
	return runGroup(func(c *C.ca_ctx, b, t *C.uint64_t, o *C.ca_ffi_options,
		x *C.uint64_t, s *C.ca_stats) C.int {
		return C.ca_ffi_rho(c, b, t, o, x, s)
	}, h, base, target, o)
}

func ffiDlog(h ctxHandle, base, target Elem, o *Options) (uint64, Stats, error) {
	return runGroup(func(c *C.ca_ctx, b, t *C.uint64_t, o *C.ca_ffi_options,
		x *C.uint64_t, s *C.ca_stats) C.int {
		return C.ca_ffi_dlog(c, b, t, o, x, s)
	}, h, base, target, o)
}

func ffiPrecomp(h ctxHandle, base, target Elem, dpBits int32, tableSize uint64, coverage float64,
	threads uint32, seed uint64) (x uint64, st Stats, err error) {
	var cx C.uint64_t
	var cst C.ca_stats
	withThread(func() {
		err = statusErr(C.ca_ffi_precomp(h, ep(&base), ep(&target), C.int32_t(dpBits),
			C.uint64_t(tableSize), C.double(coverage), C.uint32_t(threads), C.uint64_t(seed),
			&cx, &cst))
	})
	return uint64(cx), statsFromC(&cst), err
}

// ---- Cheon ----------------------------------------------------------------

func ffiCheon(h ctxHandle, gen, gAlpha, gAlphaD Elem, d, maxExps uint64) (alpha uint64, st Stats, err error) {
	var ca C.uint64_t
	var cst C.ca_stats
	withThread(func() {
		err = statusErr(C.ca_ffi_cheon(h, ep(&gen), ep(&gAlpha), ep(&gAlphaD),
			C.uint64_t(d), C.uint64_t(maxExps), &ca, &cst))
	})
	return uint64(ca), statsFromC(&cst), err
}

func ffiCheonInstance(h ctxHandle, gen Elem, alpha, d uint64) (gAlpha, gAlphaD Elem, err error) {
	withThread(func() {
		err = statusErr(C.ca_ffi_cheon_instance(h, ep(&gen), C.uint64_t(alpha), C.uint64_t(d),
			ep(&gAlpha), ep(&gAlphaD)))
	})
	return
}

func ffiCheonBestDivisor(p uint64) (uint64, float64) {
	var cost C.double
	d := C.ca_ffi_cheon_best_divisor(C.uint64_t(p), &cost)
	return uint64(d), float64(cost)
}

// ---- curve dispatch (GLV endomorphism) ------------------------------------

func ffiCurveDetect(p, a, b, order uint64) (info CurveInfo, err error) {
	var ce C.int32_t
	var ca C.uint32_t
	var cb, cl C.uint64_t
	var cs C.double
	withThread(func() {
		err = statusErr(C.ca_ffi_curve_detect(C.uint64_t(p), C.uint64_t(a), C.uint64_t(b),
			C.uint64_t(order), &ce, &ca, &cb, &cl, &cs))
	})
	if err != nil {
		return CurveInfo{}, err
	}
	return CurveInfo{
		Endo:       CurveEndo(ce),
		AutOrder:   uint32(ca),
		Beta:       uint64(cb),
		Lambda:     uint64(cl),
		RhoSpeedup: float64(cs),
	}, nil
}

func ffiCurveByName(name string) (p, a, b, order uint64, err error) {
	cn := C.CString(name)
	defer C.free(unsafe.Pointer(cn))
	var cp, ca, cb, co C.uint64_t
	withThread(func() {
		err = statusErr(C.ca_ffi_curve_by_name(cn, &cp, &ca, &cb, &co))
	})
	return uint64(cp), uint64(ca), uint64(cb), uint64(co), err
}

func ffiCurveName(i int) string {
	p := C.ca_ffi_curve_name(C.size_t(i))
	if p == nil {
		return ""
	}
	return C.GoString(p)
}

func ffiCurveSolve(h ctxHandle, base, target Elem, seed uint64) (uint64, CurveInfo, Stats, error) {
	var cx, cl C.uint64_t
	var ce C.int32_t
	var ca C.uint32_t
	var cst C.ca_stats
	var err error
	withThread(func() {
		err = statusErr(C.ca_ffi_curve_solve(h, ep(&base), ep(&target), C.uint64_t(seed), &cx, &ce,
			&ca, &cl, &cst))
	})
	info := CurveInfo{
		Endo:       CurveEndo(ce),
		AutOrder:   uint32(ca),
		Lambda:     uint64(cl),
		RhoSpeedup: math.Sqrt(float64(ca)),
	}
	return uint64(cx), info, statsFromC(&cst), err
}

// ---- index calculus -------------------------------------------------------

func ffiICSolve(p, g, h uint64, params *ICParams) (x uint64, st ICStats, err error) {
	var cx C.uint64_t
	var cst C.ca_ic_stats
	var buf C.ca_ic_params
	cp := cICParams(params, &buf)
	withThread(func() {
		err = statusErr(C.ca_ffi_ic_solve(C.uint64_t(p), C.uint64_t(g), C.uint64_t(h), cp, &cx, &cst))
	})
	return uint64(cx), icStatsFromC(&cst), err
}

func icPrecompute(p, g uint64, params *ICParams) (h icHandle, st ICStats, err error) {
	var cst C.ca_ic_stats
	var buf C.ca_ic_params
	cp := cICParams(params, &buf)
	withThread(func() {
		err = statusErr(C.int(C.ca_ic_precompute(C.uint64_t(p), C.uint64_t(g), cp, &h, &cst)))
	})
	return h, icStatsFromC(&cst), err
}

func icFree(h icHandle) { C.ca_ic_free(h) }

func icLog(h icHandle, target uint64) (x uint64, st Stats, err error) {
	var cx C.uint64_t
	var cst C.ca_stats
	withThread(func() {
		err = statusErr(C.int(C.ca_ic_log(h, C.uint64_t(target), &cx, &cst)))
	})
	return uint64(cx), statsFromC(&cst), err
}

func icModulus(h icHandle) uint64        { return uint64(C.ca_ic_modulus(h)) }
func icFactorBaseSize(h icHandle) uint32 { return uint32(C.ca_ic_factor_base_size(h)) }
func icPrimitiveRoot(h icHandle) uint64  { return uint64(C.ca_ic_primitive_root(h)) }

func icFactorBaseLog(h icHandle, i uint32) (prime uint32, log uint64, known bool) {
	var cp C.uint32_t
	var ck C.int
	l := C.ca_ic_factor_base_log(h, C.uint32_t(i), &cp, &ck)
	return uint32(cp), uint64(l), ck != 0
}

func icAutoParams(bits uint) (b, c uint32) {
	var cb, cc C.uint32_t
	C.ca_ic_auto_params(C.uint(bits), &cb, &cc)
	return uint32(cb), uint32(cc)
}

// ---- number theory --------------------------------------------------------

func isPrime(n uint64) bool         { return C.ca_ffi_is_prime(C.uint64_t(n)) != 0 }
func nextPrime(n uint64) uint64     { return uint64(C.ca_ffi_next_prime(C.uint64_t(n))) }
func primitiveRoot(p uint64) uint64 { return uint64(C.ca_ffi_primitive_root(C.uint64_t(p))) }
func invMod(a, m uint64) uint64     { return uint64(C.ca_ffi_invmod(C.uint64_t(a), C.uint64_t(m))) }
func powMod(b, e, m uint64) uint64 {
	return uint64(C.ca_ffi_powmod(C.uint64_t(b), C.uint64_t(e), C.uint64_t(m)))
}

// maxFactors bounds the number of distinct prime factors of a 64-bit
// integer (the product of the first 16 primes already exceeds 2^64).
const maxFactors = 16

func factorize(n uint64) []Factor {
	var primes [maxFactors]C.uint64_t
	var exps [maxFactors]C.uint
	cnt := C.ca_ffi_factorize(C.uint64_t(n), &primes[0], &exps[0], maxFactors)
	if cnt > maxFactors {
		cnt = maxFactors
	}
	out := make([]Factor, int(cnt))
	for i := range out {
		out[i] = Factor{P: uint64(primes[i]), E: uint32(exps[i])}
	}
	return out
}
