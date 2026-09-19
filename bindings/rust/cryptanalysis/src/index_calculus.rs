//! Index calculus for discrete logarithms in `(Z/pZ)^*`.
//!
//! Two entry points: [`solve`] for a one-shot logarithm and [`IcContext`]
//! when several logarithms to the same base are needed (the expensive
//! factor-base precomputation is then shared).
//!
//! ```
//! use cryptanalysis::index_calculus::{self, IcParams};
//! let params = IcParams { seed: 3, ..IcParams::default() };
//! let (x, stats) = index_calculus::solve(1_000_003, 2, 424_242, &params).unwrap();
//! assert_eq!(cryptanalysis::powmod(2, x, 1_000_003), 424_242);
//! assert!(stats.factor_base_size > 0);
//! ```

use std::fmt;
use std::mem::MaybeUninit;
use std::ptr::NonNull;

use cryptanalysis_sys as sys;

use crate::error::{check, Result};
use crate::options::Stats;

/// Relation-collection method.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Default)]
pub enum IcMethod {
    /// Coppersmith-Odlyzko-Schroeppel linear sieve, `L_p[1/2, 1]` (default).
    #[default]
    LinearSieve,
    /// Textbook random-exponent method, `L_p[1/2, 2]`.  Kept for comparison.
    RandomExponent,
}

/// Index-calculus parameters (`ca_ic_params`).  `Default` gives the library
/// defaults, in which every tunable is "auto".
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct IcParams {
    /// Relation-collection method.
    pub method: IcMethod,
    /// Factor-base bound B (0 => auto from the size of p).
    pub factor_base_bound: u32,
    /// Sieve radius C, linear sieve only (0 => auto).
    pub sieve_radius: u32,
    /// Relation-collection threads (0 => 1).
    pub threads: u32,
    /// Relations beyond the number of unknowns (0 => auto).
    pub extra_relations: u32,
    /// RNG seed (0 => random).
    pub seed: u64,
    /// Random-exponent method: abort bound on relation tries (0 => none).
    pub max_relation_tries: u64,
    /// Print stage reports on stderr.
    pub verbose: bool,
}

impl Default for IcParams {
    fn default() -> Self {
        let mut raw = MaybeUninit::<sys::CaIcParams>::uninit();
        // SAFETY: ca_ic_params_default fully initialises the struct.
        let raw = unsafe {
            sys::ca_ic_params_default(raw.as_mut_ptr());
            raw.assume_init()
        };
        IcParams::from_raw(&raw)
    }
}

impl IcParams {
    /// Convert to the C representation.
    pub fn to_raw(&self) -> sys::CaIcParams {
        sys::CaIcParams {
            method: match self.method {
                IcMethod::LinearSieve => sys::CA_IC_LINEAR_SIEVE,
                IcMethod::RandomExponent => sys::CA_IC_RANDOM_EXPONENT,
            },
            factor_base_bound: self.factor_base_bound,
            sieve_radius: self.sieve_radius,
            threads: self.threads,
            extra_relations: self.extra_relations,
            seed: self.seed,
            max_relation_tries: self.max_relation_tries,
            verbose: i32::from(self.verbose),
        }
    }

    /// Build from the C representation.
    pub fn from_raw(raw: &sys::CaIcParams) -> IcParams {
        IcParams {
            method: if raw.method == sys::CA_IC_RANDOM_EXPONENT {
                IcMethod::RandomExponent
            } else {
                IcMethod::LinearSieve
            },
            factor_base_bound: raw.factor_base_bound,
            sieve_radius: raw.sieve_radius,
            threads: raw.threads,
            extra_relations: raw.extra_relations,
            seed: raw.seed,
            max_relation_tries: raw.max_relation_tries,
            verbose: raw.verbose != 0,
        }
    }
}

/// Statistics from the precomputation stage (`ca_ic_stats`).
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct IcStats {
    /// Primes in the factor base.
    pub factor_base_size: u32,
    /// Columns of the relation matrix.
    pub unknowns: u32,
    /// Relations collected.
    pub relations: u32,
    /// Factor-base logs verified (`g^log == prime`).
    pub verified_logs: u32,
    /// Values passed to trial division.
    pub sieve_candidates: u64,
    /// Random-exponent method: candidates tested for smoothness.
    pub smooth_tests: u64,
    /// Seconds spent collecting relations.
    pub sieve_seconds: f64,
    /// Seconds spent in linear algebra.
    pub linalg_seconds: f64,
    /// Total seconds.
    pub total_seconds: f64,
    /// Lanczos iterations.
    pub lanczos_iterations: u32,
    /// Threads used.
    pub threads: u32,
}

impl IcStats {
    fn from_raw(raw: &sys::CaIcStats) -> IcStats {
        IcStats {
            factor_base_size: raw.factor_base_size,
            unknowns: raw.unknowns,
            relations: raw.relations,
            verified_logs: raw.verified_logs,
            sieve_candidates: raw.sieve_candidates,
            smooth_tests: raw.smooth_tests,
            sieve_seconds: raw.sieve_seconds,
            linalg_seconds: raw.linalg_seconds,
            total_seconds: raw.total_seconds,
            lanczos_iterations: raw.lanczos_iterations,
            threads: raw.threads,
        }
    }
}

/// The automatic `(B, C)` choice (factor-base bound, sieve radius) for a
/// modulus of the given bit length.
pub fn auto_params(bits: u32) -> (u32, u32) {
    let (mut b, mut c) = (0u32, 0u32);
    // SAFETY: valid out pointers.
    unsafe { sys::ca_ic_auto_params(bits, &mut b, &mut c) };
    (b, c)
}

/// One-shot: find `x` with `g^x == h (mod p)`, `x in [0, ord(g))`, for an odd
/// prime `p`.  Returns `x` and the precomputation statistics.
pub fn solve(p: u64, g: u64, h: u64, params: &IcParams) -> Result<(u64, IcStats)> {
    let raw = params.to_raw();
    let mut x = 0u64;
    let mut st = sys::CaIcStats::default();
    // SAFETY: all pointers are valid for the duration of the call.
    check(unsafe { sys::ca_ffi_ic_solve(p, g, h, &raw, &mut x, &mut st) })?;
    Ok((x, IcStats::from_raw(&st)))
}

/// A precomputed factor-base table for logarithms to a fixed base `g` modulo
/// `p`.  Frees the underlying `ca_ic_ctx` on drop.
///
/// `ca_ic_log` caches the logarithm of `g` inside the context on first use,
/// so [`IcContext::log`] takes `&mut self`; the type is `Send` but not `Sync`.
pub struct IcContext {
    ptr: NonNull<sys::CaIcCtx>,
}

// SAFETY: the context is a heap structure with no thread affinity; it may be
// moved to another thread.  It is deliberately *not* Sync because ca_ic_log
// writes to it.
unsafe impl Send for IcContext {}

impl Drop for IcContext {
    fn drop(&mut self) {
        // SAFETY: the pointer came from ca_ic_precompute and is freed once.
        unsafe { sys::ca_ic_free(self.ptr.as_ptr()) }
    }
}

impl fmt::Debug for IcContext {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("IcContext")
            .field("modulus", &self.modulus())
            .field("primitive_root", &self.primitive_root())
            .field("factor_base_size", &self.factor_base_size())
            .finish()
    }
}

impl IcContext {
    /// Compute the factor-base logarithms modulo the odd prime `p` with respect
    /// to `g` (any element of `(Z/pZ)^*`; the base change is done in
    /// [`IcContext::log`]).
    pub fn precompute(p: u64, g: u64, params: &IcParams) -> Result<(IcContext, IcStats)> {
        let raw = params.to_raw();
        let mut out: *mut sys::CaIcCtx = std::ptr::null_mut();
        let mut st = sys::CaIcStats::default();
        // SAFETY: all pointers are valid for the duration of the call.
        check(unsafe { sys::ca_ic_precompute(p, g, &raw, &mut out, &mut st) })?;
        let ptr = NonNull::new(out).ok_or_else(|| {
            crate::Error::with_message(
                sys::CA_ERR_INTERNAL,
                "ca_ic_precompute returned CA_OK with a null context".to_owned(),
            )
        })?;
        Ok((IcContext { ptr }, IcStats::from_raw(&st)))
    }

    /// Individual logarithm: `x` with `g^x == h (mod p)`, `x in [0, ord(g))`.
    pub fn log(&mut self, h: u64) -> Result<(u64, Stats)> {
        let mut x = 0u64;
        let mut st = sys::CaStats::default();
        // SAFETY: valid, exclusively borrowed context and out pointers.
        check(unsafe { sys::ca_ic_log(self.ptr.as_ptr(), h, &mut x, &mut st) })?;
        Ok((x, Stats::from_raw(&st)))
    }

    /// The modulus `p`.
    pub fn modulus(&self) -> u64 {
        // SAFETY: valid context.
        unsafe { sys::ca_ic_modulus(self.ptr.as_ptr()) }
    }

    /// Number of primes in the factor base.
    pub fn factor_base_size(&self) -> u32 {
        // SAFETY: valid context.
        unsafe { sys::ca_ic_factor_base_size(self.ptr.as_ptr()) }
    }

    /// The primitive root used internally as the reference base.
    pub fn primitive_root(&self) -> u64 {
        // SAFETY: valid context.
        unsafe { sys::ca_ic_primitive_root(self.ptr.as_ptr()) }
    }

    /// The `i`-th factor-base prime and its logarithm with respect to
    /// [`IcContext::primitive_root`], or `None` if that log was not determined
    /// (or `i` is out of range).
    pub fn factor_base_log(&self, i: u32) -> Option<(u32, u64)> {
        if i >= self.factor_base_size() {
            return None;
        }
        let mut prime = 0u32;
        let mut known = 0i32;
        // SAFETY: valid context and out pointers.
        let log =
            unsafe { sys::ca_ic_factor_base_log(self.ptr.as_ptr(), i, &mut prime, &mut known) };
        (known != 0).then_some((prime, log))
    }
}
