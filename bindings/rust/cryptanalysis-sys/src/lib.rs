//! Raw FFI bindings to `libcryptanalysis`, a discrete-logarithm cryptanalysis
//! toolkit (BSGS, Pollard rho, kangaroo, grumpy giants, Pohlig-Hellman,
//! Cheon's attack, index calculus).
//!
//! This crate binds the flat C ABI declared in `include/cryptanalysis/ca_ffi.h`,
//! `ca_types.h` and `ca_indexcalc.h`.  The C sources are compiled by `build.rs`
//! with the `cc` crate, so a working C compiler is the only build requirement.
//!
//! Everything here is `unsafe` and mirrors the C header one-to-one; use the
//! `cryptanalysis` crate for a safe wrapper.
//!
//! # Element words
//!
//! Group elements cross the boundary as `[u64; 4]` in *public* form (never
//! Montgomery):
//!
//! * `Z_p^*`: `w[0]` = residue in `[1, p)`, `w[1..3] = 0`
//! * `E(F_p)`: `w[0] = x`, `w[1] = y`, `w[2] = 1` for the point at infinity
//!
//! Every function returning `c_int` returns a `ca_status` (`0` = [`CA_OK`]);
//! the message for the last failure on the calling thread is available from
//! [`ca_last_error`].

#![no_std]
#![allow(non_camel_case_types)]
#![deny(missing_docs)]

use core::ffi::{c_char, c_double, c_int, c_uint};

/// Opaque group context (`ca_ctx`).  Only ever handled through a pointer.
pub enum CaCtx {}

/// Opaque index-calculus context (`ca_ic_ctx`).  Only ever handled through a pointer.
pub enum CaIcCtx {}

/// Element words as passed across the ABI (`uint64_t[4]`).
pub type CaWords = [u64; 4];

// ---- ca_status ------------------------------------------------------------

/// `CA_OK`: success.
pub const CA_OK: c_int = 0;
/// `CA_ERR_INVALID`: invalid argument (bad modulus, point not on curve, ...).
pub const CA_ERR_INVALID: c_int = 1;
/// `CA_ERR_NOT_FOUND`: the search space was exhausted without a solution.
pub const CA_ERR_NOT_FOUND: c_int = 2;
/// `CA_ERR_NOMEM`: allocation failure.
pub const CA_ERR_NOMEM: c_int = 3;
/// `CA_ERR_LIMIT`: an explicit work/memory/time limit was reached.
pub const CA_ERR_LIMIT: c_int = 4;
/// `CA_ERR_UNSUPPORTED`: the operation is not supported for this group/params.
pub const CA_ERR_UNSUPPORTED: c_int = 5;
/// `CA_ERR_INTERNAL`: internal consistency failure (should not happen).
pub const CA_ERR_INTERNAL: c_int = 6;
/// `CA_ERR_SINGULAR`: linear system had no usable solution.
pub const CA_ERR_SINGULAR: c_int = 7;

// ---- group kinds (ca_ctx_kind) -------------------------------------------

/// `ca_ctx_kind` result for the multiplicative group `Z_p^*`.
pub const CA_GROUP_ZP: c_int = 1;
/// `ca_ctx_kind` result for an elliptic curve group `E(F_p)`.
pub const CA_GROUP_EC: c_int = 2;

// ---- ca_solver (ca_ffi_options.solver) -----------------------------------

/// `CA_SOLVER_AUTO`: BSGS for small prime factors, rho for large ones.
pub const CA_SOLVER_AUTO: i32 = 0;
/// `CA_SOLVER_BSGS`.
pub const CA_SOLVER_BSGS: i32 = 1;
/// `CA_SOLVER_RHO`.
pub const CA_SOLVER_RHO: i32 = 2;
/// `CA_SOLVER_KANGAROO`.
pub const CA_SOLVER_KANGAROO: i32 = 3;
/// `CA_SOLVER_GRUMPY`.
pub const CA_SOLVER_GRUMPY: i32 = 4;
/// `CA_SOLVER_BRUTE`.
pub const CA_SOLVER_BRUTE: i32 = 5;

// ---- ca_ic_method ----------------------------------------------------------

/// `CA_IC_LINEAR_SIEVE`: Coppersmith-Odlyzko-Schroeppel linear sieve (default).
pub const CA_IC_LINEAR_SIEVE: c_int = 0;
/// `CA_IC_RANDOM_EXPONENT`: textbook random-exponent relation collection.
pub const CA_IC_RANDOM_EXPONENT: c_int = 1;

// ---- POD structs -----------------------------------------------------------

/// Work statistics common to all solvers (`ca_stats`).
///
/// Zeroed by the caller or by the solver entry point; solvers only ever add
/// to the counters.
#[repr(C)]
#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct CaStats {
    /// Group operations performed (adds/muls).
    pub group_ops: u64,
    /// Algorithm-specific step counter.
    pub iterations: u64,
    /// Entries stored in lookup tables.
    pub table_entries: u64,
    /// Useful collisions / relations found.
    pub collisions: u64,
    /// Approximate peak heap usage of tables.
    pub bytes_peak: u64,
    /// Wall-clock time spent.
    pub seconds: c_double,
    /// Threads used.
    pub threads: u32,
    /// Padding; always zero.
    pub reserved: u32,
}

/// Solver options for the flat ABI (`ca_ffi_options`).
///
/// Obtain defaults with [`ca_ffi_options_default`] rather than zeroing: several
/// fields use `-1`/`1`/`0.7` as their "auto" value.
#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct CaFfiOptions {
    /// rho: worker threads (0 => 1).
    pub threads: u32,
    /// Padding; always zero.
    pub reserved0: u32,
    /// RNG seed (0 => random).
    pub seed: u64,
    /// Work limit in group operations (0 => unlimited).
    pub max_ops: u64,
    /// bsgs: baby-step table size (0 => sqrt(width)).
    pub bsgs_table_size: u64,
    /// rho: number of partitions (0 => auto).
    pub rho_r: u32,
    /// rho: distinguished-point bits (-1 => auto).
    pub rho_dp_bits: i32,
    /// rho: parallel walks per thread (0 => auto).
    pub rho_walks_per_thread: u32,
    /// rho: 1 => use the negation map when available.
    pub rho_negation_map: i32,
    /// rho: cap on distinguished-point table entries (0 => unlimited).
    pub rho_max_table_entries: u64,
    /// kangaroo: herd size (0 => auto).
    pub kangaroo_herd_size: u32,
    /// kangaroo: distinguished-point bits (-1 => auto).
    pub kangaroo_dp_bits: i32,
    /// kangaroo: number of jump sizes (0 => auto).
    pub kangaroo_jumps: u32,
    /// Padding; always zero.
    pub reserved1: u32,
    /// grumpy giants: m (0 => alpha*sqrt(width)).
    pub grumpy_m: u64,
    /// grumpy giants: alpha (0 => 0.7).
    pub grumpy_alpha: c_double,
    /// dlog driver: `ca_solver` (0 auto, 1 bsgs, 2 rho, 3 kangaroo, 4 grumpy, 5 brute).
    pub solver: i32,
    /// Padding; always zero.
    pub reserved2: i32,
    /// auto: BSGS for prime factors <= this (0 => 2^36).
    pub bsgs_max_prime: u64,
}

/// Index-calculus parameters (`ca_ic_params`).
///
/// Obtain defaults with [`ca_ic_params_default`].
#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct CaIcParams {
    /// `ca_ic_method` (see [`CA_IC_LINEAR_SIEVE`], [`CA_IC_RANDOM_EXPONENT`]).
    pub method: c_int,
    /// B; 0 => auto from the size of p.
    pub factor_base_bound: u32,
    /// C (linear sieve only); 0 => auto.
    pub sieve_radius: u32,
    /// Relation collection threads; 0 => 1.
    pub threads: u32,
    /// Relations beyond #unknowns; 0 => auto.
    pub extra_relations: u32,
    /// RNG seed; 0 => random.
    pub seed: u64,
    /// Random-exponent method: abort bound (0 = none).
    pub max_relation_tries: u64,
    /// Stage reports on stderr.
    pub verbose: c_int,
}

/// Index-calculus statistics (`ca_ic_stats`).
#[repr(C)]
#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct CaIcStats {
    /// Primes in the factor base.
    pub factor_base_size: u32,
    /// Columns of the relation matrix.
    pub unknowns: u32,
    /// Relations collected.
    pub relations: u32,
    /// Factor-base logs verified.
    pub verified_logs: u32,
    /// Values passed to trial division.
    pub sieve_candidates: u64,
    /// Random-exponent method: candidates tested.
    pub smooth_tests: u64,
    /// Seconds spent collecting relations.
    pub sieve_seconds: c_double,
    /// Seconds spent in linear algebra.
    pub linalg_seconds: c_double,
    /// Total seconds.
    pub total_seconds: c_double,
    /// Lanczos iterations.
    pub lanczos_iterations: u32,
    /// Threads used.
    pub threads: u32,
}

extern "C" {
    // ---- ca_types.h --------------------------------------------------------

    /// Library version string, e.g. `"0.1.0"`.
    pub fn ca_version() -> *const c_char;
    /// Static description of a status code.
    pub fn ca_status_string(s: c_int) -> *const c_char;
    /// Thread-local description of the last error raised by this thread.
    /// Never null; points at a buffer that stays valid for the thread's lifetime
    /// but is overwritten by the next error.
    pub fn ca_last_error() -> *const c_char;

    // ---- groups ------------------------------------------------------------

    /// Create a `Z_p^*` context (`order` = order of the subgroup of interest,
    /// or 0 for the full group).  Returns null on invalid parameters.
    pub fn ca_ctx_new_zp(p: u64, order: u64) -> *mut CaCtx;
    /// Create an `E(F_p): y^2 = x^3 + a x + b` context.  Returns null on invalid parameters.
    pub fn ca_ctx_new_ec(p: u64, a: u64, b: u64, order: u64) -> *mut CaCtx;
    /// Free a context (null is fine).
    pub fn ca_ctx_free(ctx: *mut CaCtx);
    /// [`CA_GROUP_ZP`] or [`CA_GROUP_EC`].
    pub fn ca_ctx_kind(ctx: *const CaCtx) -> c_int;
    /// The field prime.
    pub fn ca_ctx_p(ctx: *const CaCtx) -> u64;
    /// The (sub)group order.
    pub fn ca_ctx_order(ctx: *const CaCtx) -> u64;
    /// The cofactor.
    pub fn ca_ctx_cofactor(ctx: *const CaCtx) -> u64;
    /// Override the order and cofactor (the only mutating context call).
    pub fn ca_ctx_set_order(ctx: *mut CaCtx, order: u64, cofactor: u64);
    /// Curve coefficient `a` (EC only).
    pub fn ca_ctx_curve_a(ctx: *const CaCtx) -> u64;
    /// Curve coefficient `b` (EC only).
    pub fn ca_ctx_curve_b(ctx: *const CaCtx) -> u64;

    // ---- elements ----------------------------------------------------------

    /// 1 if `w` is a valid element of the group.
    pub fn ca_ctx_validate(ctx: *const CaCtx, w: *const u64) -> c_int;
    /// Write the identity into `out`.
    pub fn ca_ctx_identity(ctx: *const CaCtx, out: *mut u64) -> c_int;
    /// 1 if `w` is the identity.
    pub fn ca_ctx_is_identity(ctx: *const CaCtx, w: *const u64) -> c_int;
    /// `out = a * b` (group law).
    pub fn ca_ctx_op(ctx: *const CaCtx, out: *mut u64, a: *const u64, b: *const u64) -> c_int;
    /// `out = a^-1`.
    pub fn ca_ctx_inv(ctx: *const CaCtx, out: *mut u64, a: *const u64) -> c_int;
    /// `out = a^k` (scalar multiplication).
    pub fn ca_ctx_mul(ctx: *const CaCtx, out: *mut u64, a: *const u64, k: u64) -> c_int;
    /// 1 if `a == b`.
    pub fn ca_ctx_equal(ctx: *const CaCtx, a: *const u64, b: *const u64) -> c_int;
    /// Order of `a`, written to `*order`.
    pub fn ca_ctx_elem_order(ctx: *const CaCtx, a: *const u64, order: *mut u64) -> c_int;
    /// Find a generator of the subgroup of the context's order.
    pub fn ca_ctx_find_generator(ctx: *const CaCtx, out: *mut u64, seed: u64) -> c_int;
    /// A pseudo-random element (multiplied by the cofactor when it is > 1).
    pub fn ca_ctx_random_element(ctx: *const CaCtx, out: *mut u64, seed: u64) -> c_int;
    /// EC only: a point with the given x coordinate, if one exists.
    pub fn ca_ctx_lift_x(ctx: *const CaCtx, out: *mut u64, x: u64) -> c_int;
    /// Point counting for `y^2 = x^3 + a x + b` over `F_p`.
    pub fn ca_ec_order(p: u64, a: u64, b: u64, order: *mut u64) -> c_int;

    // ---- options / layout guards ------------------------------------------

    /// Fill `o` with the defaults.
    pub fn ca_ffi_options_default(o: *mut CaFfiOptions);
    /// `sizeof(ca_ffi_options)` as compiled into the C library.
    pub fn ca_ffi_options_size() -> usize;
    /// `sizeof(ca_stats)` as compiled into the C library.
    pub fn ca_stats_size() -> usize;
    /// `sizeof(ca_ic_params)` as compiled into the C library.
    pub fn ca_ic_params_size() -> usize;
    /// `sizeof(ca_ic_stats)` as compiled into the C library.
    pub fn ca_ic_stats_size() -> usize;

    // ---- discrete logarithm solvers ---------------------------------------
    // Interval solvers: x in [lo, hi]; lo == hi == 0 means the whole group.
    // `o` and `st` may be null.

    /// Baby-step giant-step.
    pub fn ca_ffi_bsgs(
        ctx: *const CaCtx,
        base: *const u64,
        target: *const u64,
        lo: u64,
        hi: u64,
        o: *const CaFfiOptions,
        x: *mut u64,
        st: *mut CaStats,
    ) -> c_int;
    /// Pollard's kangaroo (lambda) method.
    pub fn ca_ffi_kangaroo(
        ctx: *const CaCtx,
        base: *const u64,
        target: *const u64,
        lo: u64,
        hi: u64,
        o: *const CaFfiOptions,
        x: *mut u64,
        st: *mut CaStats,
    ) -> c_int;
    /// Grumpy giants.
    pub fn ca_ffi_grumpy(
        ctx: *const CaCtx,
        base: *const u64,
        target: *const u64,
        lo: u64,
        hi: u64,
        o: *const CaFfiOptions,
        x: *mut u64,
        st: *mut CaStats,
    ) -> c_int;
    /// Pollard rho over the whole group (needs the context order).
    pub fn ca_ffi_rho(
        ctx: *const CaCtx,
        base: *const u64,
        target: *const u64,
        o: *const CaFfiOptions,
        x: *mut u64,
        st: *mut CaStats,
    ) -> c_int;
    /// Pohlig-Hellman + the solver selected in `o`.
    pub fn ca_ffi_dlog(
        ctx: *const CaCtx,
        base: *const u64,
        target: *const u64,
        o: *const CaFfiOptions,
        x: *mut u64,
        st: *mut CaStats,
    ) -> c_int;

    // ---- Cheon -------------------------------------------------------------

    /// Cheon's attack: recover `alpha` from `g`, `g^alpha`, `g^(alpha^d)` with `d | order - 1`.
    pub fn ca_ffi_cheon(
        ctx: *const CaCtx,
        gen: *const u64,
        g_alpha: *const u64,
        g_alpha_d: *const u64,
        d: u64,
        max_exps: u64,
        alpha: *mut u64,
        st: *mut CaStats,
    ) -> c_int;
    /// Build a Cheon instance `(g^alpha, g^(alpha^d))` for experiments.
    pub fn ca_ffi_cheon_instance(
        ctx: *const CaCtx,
        gen: *const u64,
        alpha: u64,
        d: u64,
        g_alpha: *mut u64,
        g_alpha_d: *mut u64,
    ) -> c_int;
    /// Best divisor `d` of `p - 1` for the attack; `cost_exps` (may be null)
    /// receives the estimated cost in exponentiations.
    pub fn ca_ffi_cheon_best_divisor(p: u64, cost_exps: *mut c_double) -> u64;

    // ---- index calculus ----------------------------------------------------

    /// Fill `p` with the defaults.
    pub fn ca_ic_params_default(p: *mut CaIcParams);
    /// Choose `(B, C)` automatically for a modulus of the given bit length.
    pub fn ca_ic_auto_params(bits: c_uint, b: *mut u32, c: *mut u32);
    /// Precompute the factor-base logarithms w.r.t. `g` modulo the odd prime `p`.
    pub fn ca_ic_precompute(
        p: u64,
        g: u64,
        params: *const CaIcParams,
        out: *mut *mut CaIcCtx,
        st: *mut CaIcStats,
    ) -> c_int;
    /// Free an index-calculus context (null is fine).
    pub fn ca_ic_free(ctx: *mut CaIcCtx);
    /// Individual logarithm: `x` with `g^x == h (mod p)`, `x in [0, ord(g))`.
    /// Mutates the context (caches the log of `g` on first use).
    pub fn ca_ic_log(ctx: *mut CaIcCtx, h: u64, x: *mut u64, st: *mut CaStats) -> c_int;
    /// One-shot convenience wrapper.
    pub fn ca_ic_solve(
        p: u64,
        g: u64,
        h: u64,
        params: *const CaIcParams,
        x: *mut u64,
        st: *mut CaIcStats,
    ) -> c_int;
    /// Same as [`ca_ic_solve`], re-exported through the flat ABI.
    pub fn ca_ffi_ic_solve(
        p: u64,
        g: u64,
        h: u64,
        params: *const CaIcParams,
        x: *mut u64,
        st: *mut CaIcStats,
    ) -> c_int;
    /// The modulus of a precomputed context.
    pub fn ca_ic_modulus(ctx: *const CaIcCtx) -> u64;
    /// Number of primes in the factor base.
    pub fn ca_ic_factor_base_size(ctx: *const CaIcCtx) -> u32;
    /// Log (w.r.t. the internal primitive root) of the i-th factor-base prime;
    /// returns 0 and sets `*known = 0` if it was not determined.
    pub fn ca_ic_factor_base_log(
        ctx: *const CaIcCtx,
        i: u32,
        prime: *mut u32,
        known: *mut c_int,
    ) -> u64;
    /// The primitive root used internally.
    pub fn ca_ic_primitive_root(ctx: *const CaIcCtx) -> u64;

    // ---- number theory helpers -------------------------------------------

    /// 1 if `n` is prime.
    pub fn ca_ffi_is_prime(n: u64) -> c_int;
    /// Smallest prime strictly greater than `n`.
    pub fn ca_ffi_next_prime(n: u64) -> u64;
    /// Smallest primitive root modulo the prime `p`.
    pub fn ca_ffi_primitive_root(p: u64) -> u64;
    /// `b^e mod m`.
    pub fn ca_ffi_powmod(b: u64, e: u64, m: u64) -> u64;
    /// `a^-1 mod m` (0 if it does not exist).
    pub fn ca_ffi_invmod(a: u64, m: u64) -> u64;
    /// Factor `n` into up to `cap` (prime, exponent) pairs; returns the total
    /// count (which may exceed `cap`, in which case only `cap` were written).
    pub fn ca_ffi_factorize(n: u64, primes: *mut u64, exps: *mut c_uint, cap: c_uint) -> c_uint;
}

#[cfg(test)]
mod tests {
    use super::*;
    use core::mem::size_of;

    #[test]
    fn struct_sizes_match_c() {
        unsafe {
            assert_eq!(size_of::<CaFfiOptions>(), ca_ffi_options_size());
            assert_eq!(size_of::<CaStats>(), ca_stats_size());
            assert_eq!(size_of::<CaIcParams>(), ca_ic_params_size());
            assert_eq!(size_of::<CaIcStats>(), ca_ic_stats_size());
        }
    }

    #[test]
    fn defaults_look_sane() {
        let mut o = CaFfiOptions {
            threads: 0,
            reserved0: 0,
            seed: 0,
            max_ops: 0,
            bsgs_table_size: 0,
            rho_r: 0,
            rho_dp_bits: 0,
            rho_walks_per_thread: 0,
            rho_negation_map: 0,
            rho_max_table_entries: 0,
            kangaroo_herd_size: 0,
            kangaroo_dp_bits: 0,
            kangaroo_jumps: 0,
            reserved1: 0,
            grumpy_m: 0,
            grumpy_alpha: 0.0,
            solver: 0,
            reserved2: 0,
            bsgs_max_prime: 0,
        };
        unsafe { ca_ffi_options_default(&mut o) };
        assert_eq!(o.threads, 1);
        assert_eq!(o.rho_dp_bits, -1);
        assert_eq!(o.kangaroo_dp_bits, -1);
        assert_eq!(o.rho_negation_map, 1);
        assert_eq!(o.grumpy_alpha, 0.7);
        assert_eq!(o.solver, CA_SOLVER_AUTO);
    }

    #[test]
    fn version_and_helpers() {
        unsafe {
            let v = ca_version();
            assert!(!v.is_null());
            assert_eq!(*v, b'0' as c_char);
            assert_eq!(ca_ffi_is_prime(1000003), 1);
            assert_eq!(ca_ffi_powmod(2, 10, 1000), 24);
        }
    }
}
