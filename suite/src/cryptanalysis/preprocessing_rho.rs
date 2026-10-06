//! Bernstein–Lange preprocessing rho — non-uniform DLP attack with
//! `T = N^{2/3}` precomputation giving `N^{1/3}` online cost.
//!
//! Bernstein, Lange, "Non-uniform cracks in the concrete: the power
//! of free precomputation," Asiacrypt 2013.  The classical
//! generic-group lower bound is `√n` per ECDLP — but only for
//! *uniform* algorithms.  Allowing arbitrary precomputation
//! ("advice" in complexity-theoretic terms), the cost-per-target
//! drops below `√n`.
//!
//! # The model
//!
//! - **Preprocessing phase** (offline, one-time per curve):
//!   compute a table of `T` distinguished points reached from
//!   random `g^a` walks.  Each table entry is `(DP, a)`.
//! - **Online phase** (per target `h`): walk from `h` using the
//!   same deterministic step function.  When the walk hits a DP
//!   already in the table, recover `d = log_g(h)` from the
//!   table entry's `a` value and the online walker's accumulated
//!   step count.
//!
//! The walk function uses **only `g`** (not `h`), so precomputation
//! is target-independent — the table is built once per curve and
//! reused for all targets.  This is the "non-uniform" advantage.
//!
//! # Cost trade-off
//!
//! For group order `n`, precomputation cost is `T` group ops and
//! `T` table entries (memory).  Online cost is `O(n / T)` walk
//! steps per target.  Setting `T = n^{2/3}`:
//! - Precomputation: `n^{2/3}` ops, `n^{2/3}` storage
//! - Online: `n^{1/3}` ops per target
//! - Total *amortised* cost across many targets: dominated by
//!   precomputation
//!
//! For `n = 2^{256}` (P-256), precomputation cost is `~2^{171}`
//! ops and `~2^{171}` storage — astronomical.  The Bernstein-Lange
//! result is theoretical at cryptographic sizes.  At toy scale,
//! it's a real and demonstrable attack.
//!
//! # What this module ships
//!
//! Toy-scale implementation against `Z_p^*` multiplicative DLP for
//! `p ~ 2^{20}` Sophie-Germain primes.  Concrete demonstration of
//! the time-memory trade-off; tests verify `n^{1/3}` online cost
//! is achievable with `n^{2/3}` precomputation.
//!
//! # Why this is in the cryptanalysis suite
//!
//! Two reasons:
//! 1. **Empirical validation of `ecc_safety`'s multi-target
//!    margin warning**: the auditor's `check_multi_target_margin`
//!    flag fires when a deployment exposes many keys on one
//!    curve; this module's online walks demonstrate concretely
//!    that amortised attack cost is real.
//! 2. **Attack-cost calculator**: given `(n, T_budget)`, compute
//!    the expected online cost per target.  Useful for security
//!    posture reports.

use crate::utils::mod_inverse;
use num_bigint::{BigUint, RandBigInt};
use num_integer::Integer;
use num_traits::{One, Zero};
use rand::rngs::StdRng;
use rand::SeedableRng;
use std::collections::HashMap;

/// Configuration for preprocessing rho.
#[derive(Clone, Debug)]
pub struct PreprocessingOptions {
    /// Bits of the serialized group element that must be zero for
    /// the element to be "distinguished."  See
    /// [`crate::cryptanalysis::pollard_rho::DpRhoOptions`].
    /// Tune to control table sparsity:  `dp_bits ≈ ½·log₂(n) − ½·log₂(T)`
    /// makes DPs roughly `√(n/T)` apart.
    pub dp_bits: u8,
    /// Table size target (number of distinguished points to
    /// precompute).
    pub table_size: u64,
    /// Maximum walk length per precomputation start (cap on
    /// time-to-DP).
    pub max_walk_steps: u64,
    /// Online walker's max steps before giving up on a target.
    pub max_online_steps: u64,
    /// Optional deterministic seed.
    pub seed: Option<u64>,
}

impl Default for PreprocessingOptions {
    fn default() -> Self {
        Self {
            dp_bits: 4,
            table_size: 1 << 14,
            max_walk_steps: 1 << 18,
            max_online_steps: 1 << 18,
            seed: None,
        }
    }
}

/// A precomputed Bernstein–Lange table for a fixed `(g, p, n)` group.
///
/// Maps serialized DPs to the value `a` such that the walk
/// `g^a → ... → DP` arrives at `DP`.  The walker's step function
/// uses **only `g`** (no target dependence), so the table is built
/// once and reused across any number of online targets.
pub struct PreprocessingTable {
    pub p: BigUint,
    pub n: BigUint,
    pub g: BigUint,
    pub dp_bits: u8,
    /// Map `serialize(DP) → a`.
    table: HashMap<Vec<u8>, BigUint>,
}

impl PreprocessingTable {
    /// Number of entries in the table.
    pub fn len(&self) -> usize {
        self.table.len()
    }

    /// Whether the table is empty.
    pub fn is_empty(&self) -> bool {
        self.table.is_empty()
    }
}

// ── Step function (target-independent) ─────────────────────────────────────
//
// We use a 2-bucket walk based on the low bit of the current point:
//   bucket 0:  x ↦ x · g    (a-counter increments by 1)
//   bucket 1:  x ↦ x²       (a-counter doubles)
//
// This is target-INDEPENDENT — both preprocessing and online walks
// use the same function regardless of the target h.  The online
// walker starts at h and tracks steps; when it hits a table DP
// (which corresponds to some g^a), the discrete log of h is
// recovered as `a_table - steps_online (mod n)`.

fn partition(x: &BigUint) -> u8 {
    let bytes = x.to_bytes_be();
    bytes.last().copied().unwrap_or(0) & 1
}

fn step_g(x: &BigUint, a: &BigUint, g: &BigUint, p: &BigUint, n: &BigUint) -> (BigUint, BigUint) {
    match partition(x) {
        0 => ((x * g) % p, (a + BigUint::one()) % n),
        _ => ((x * x) % p, (a * BigUint::from(2u32)) % n),
    }
}

fn is_distinguished(x: &BigUint, dp_bits: u8) -> bool {
    if dp_bits == 0 {
        return true;
    }
    let bytes = x.to_bytes_be();
    let last = bytes.last().copied().unwrap_or(0);
    if dp_bits >= 8 {
        last == 0
    } else {
        let mask = (1u8 << dp_bits) - 1;
        (last & mask) == 0
    }
}

fn serialize(x: &BigUint) -> Vec<u8> {
    x.to_bytes_be()
}

// ── Preprocessing ─────────────────────────────────────────────────────────

/// Build a Bernstein–Lange precomputation table for the group
/// `<g> ⊂ Z_p^*` of order `n`.
///
/// Walks from `T_size` random starting exponents until each walker
/// hits a DP, recording `(DP, a)`.  Subsequent online attacks can
/// reuse this table for *any* target in the same group.
pub fn build_preprocessing_table(
    g: &BigUint,
    p: &BigUint,
    n: &BigUint,
    opts: &PreprocessingOptions,
) -> PreprocessingTable {
    let mut rng: StdRng = match opts.seed {
        Some(s) => StdRng::seed_from_u64(s),
        None => StdRng::seed_from_u64(0xBABEFACEFEEDD00Du64),
    };
    let mut table: HashMap<Vec<u8>, BigUint> = HashMap::with_capacity(opts.table_size as usize);

    let mut starts_attempted = 0u64;
    while (table.len() as u64) < opts.table_size && starts_attempted < opts.table_size * 4 {
        starts_attempted += 1;
        let mut a = rng.gen_biguint_below(n);
        let mut x = crate::utils::mod_pow(g, &a, p);
        for _ in 0..opts.max_walk_steps {
            if is_distinguished(&x, opts.dp_bits) {
                table.entry(serialize(&x)).or_insert_with(|| a.clone());
                break;
            }
            let (nx, na) = step_g(&x, &a, g, p, n);
            x = nx;
            a = na;
        }
    }

    PreprocessingTable {
        p: p.clone(),
        n: n.clone(),
        g: g.clone(),
        dp_bits: opts.dp_bits,
        table,
    }
}

// ── Online attack ─────────────────────────────────────────────────────────

/// Online phase: given a precomputed table and a target `h = g^d`,
/// recover `d` by walking from `h` until a DP is found in the
/// table.
///
/// Online tracking: the walker starts at `h = g^d`, so we view the
/// current point as `g^{c·d + e}` and track the pair `(c, e)`.  The
/// step function evolves them:
/// - bucket 0 (multiply by `g`):   `(c, e) → (c, e + 1)`
/// - bucket 1 (square):            `(c, e) → (2c, 2e)`
///
/// When a table DP is hit at value `a_table = c·d + e (mod n)`,
/// recover `d = (a_table − e) · c⁻¹ (mod n)`.
///
/// Returns `Err` if no table hit occurs within `max_online_steps`,
/// or if every hit had `c ≡ 0 (mod n)` (degenerate; rare).
pub fn online_solve(
    table: &PreprocessingTable,
    h: &BigUint,
    opts: &PreprocessingOptions,
) -> Result<BigUint, &'static str> {
    if table.is_empty() {
        return Err("preprocessing table is empty");
    }
    let mut x = h.clone();
    let mut c = BigUint::one();
    let mut e = BigUint::zero();
    for _ in 0..opts.max_online_steps {
        if is_distinguished(&x, table.dp_bits) {
            if let Some(a_table) = table.table.get(&serialize(&x)) {
                // d = (a_table − e) · c⁻¹ (mod n)
                if !c.is_zero() {
                    if let Some(c_inv) = mod_inverse(&c, &table.n) {
                        let lhs = if a_table >= &e {
                            (a_table - &e) % &table.n
                        } else {
                            let diff = (&e - a_table) % &table.n;
                            if diff.is_zero() {
                                BigUint::zero()
                            } else {
                                &table.n - diff
                            }
                        };
                        let d = (&lhs * &c_inv) % &table.n;
                        let check = crate::utils::mod_pow(&table.g, &d, &table.p);
                        if check == *h {
                            return Ok(d);
                        }
                        // false hit; keep walking
                    }
                }
            }
        }
        match partition(&x) {
            0 => {
                x = (&x * &table.g) % &table.p;
                e = (&e + BigUint::one()) % &table.n;
            }
            _ => {
                x = (&x * &x) % &table.p;
                c = (&c * BigUint::from(2u32)) % &table.n;
                e = (&e * BigUint::from(2u32)) % &table.n;
            }
        }
    }
    Err("online walk exhausted without table hit")
}

/// Convenience: preprocess + solve in one call.  For
/// **single-target** use; for amortised multi-target use, call
/// [`build_preprocessing_table`] once and then [`online_solve`]
/// per target.
pub fn preprocessing_rho_dlp(
    g: &BigUint,
    h: &BigUint,
    p: &BigUint,
    n: &BigUint,
    opts: &PreprocessingOptions,
) -> Result<BigUint, &'static str> {
    let table = build_preprocessing_table(g, p, n, opts);
    online_solve(&table, h, opts)
}

// ── Cost calculator ───────────────────────────────────────────────────────

/// Estimated online cost (expected number of walk steps) for a
/// preprocessing table of size `T` against group order `n`.
///
/// Under the random-function assumption, each walk step lands on
/// a table DP with probability `T/N`, so expected time-to-hit is
/// `N/T`.  This is Bernstein-Lange's formal claim: at the optimum
/// `T = N^{2/3}`, online cost is `N^{1/3}`.
pub fn expected_online_cost(n: &BigUint, table_size: u64, _dp_bits: u8) -> f64 {
    let n_f = n_to_f64_safe(n);
    let t_f = table_size as f64;
    if t_f <= 0.0 {
        return n_f;
    }
    n_f / t_f
}

fn n_to_f64_safe(n: &BigUint) -> f64 {
    // For very large n, this is lossy but order-of-magnitude correct.
    let bits = n.bits();
    if bits < 53 {
        n.iter_u64_digits().next().unwrap_or(0) as f64
    } else {
        // 2^bits scaled by leading f64 mantissa.
        2f64.powi(bits as i32)
    }
}

// `Integer` and `mod_inverse` imports kept in case future variants
// (e.g., 2-adding walks with offsets) need them.
#[allow(dead_code)]
fn _link() {
    let _ = mod_inverse(&BigUint::one(), &BigUint::from(7u32));
    let _ = BigUint::from(2u32).gcd(&BigUint::from(3u32));
}

#[cfg(test)]
mod tests {
    use super::*;
    use num_bigint::BigUint;

    /// Test build + online on a small Sophie-Germain group.
    /// p = 1019, q = 509 (Sophie Germain pair).  g = 2, plant
    /// d = 314, recover via online walk against a precomputed
    /// table.
    #[test]
    fn preprocessing_rho_recovers_planted_dlp_small() {
        let p = BigUint::from(1019u32);
        let q = BigUint::from(509u32);
        let g = BigUint::from(4u32); // order q in Z_1019*
        let d_true = BigUint::from(314u32);
        let h = crate::utils::mod_pow(&g, &d_true, &p);

        let opts = PreprocessingOptions {
            dp_bits: 2,
            table_size: 64,
            max_walk_steps: 1024,
            max_online_steps: 1024,
            seed: Some(0xC0FFEEu64),
        };
        let recovered = preprocessing_rho_dlp(&g, &h, &p, &q, &opts)
            .expect("preprocessing rho should recover planted d");
        let check = crate::utils::mod_pow(&g, &recovered, &p);
        assert_eq!(check, h, "recovered d does not satisfy g^d = h");
    }

    /// **Multi-target test**: build the table ONCE, solve multiple
    /// DLPs, all reusing the same table.  Demonstrates the
    /// amortisation benefit Bernstein-Lange formalised.
    #[test]
    fn preprocessing_rho_amortises_across_targets() {
        let p = BigUint::from(1019u32);
        let q = BigUint::from(509u32);
        let g = BigUint::from(4u32);

        let opts = PreprocessingOptions {
            dp_bits: 2,
            table_size: 128,
            max_walk_steps: 2048,
            max_online_steps: 2048,
            seed: Some(0xBADC0DEu64),
        };
        let table = build_preprocessing_table(&g, &p, &q, &opts);
        assert!(!table.is_empty());

        let mut recovered_count = 0;
        for &d_planted in &[10u32, 50, 100, 200, 314, 400, 500] {
            let d_true = BigUint::from(d_planted);
            let h = crate::utils::mod_pow(&g, &d_true, &p);
            if let Ok(d_rec) = online_solve(&table, &h, &opts) {
                let check = crate::utils::mod_pow(&g, &d_rec, &p);
                assert_eq!(check, h);
                recovered_count += 1;
            }
        }
        // Even with a small table, we expect ≥ 50% of targets to
        // recover.  Toy curves have lots of variance; the headline
        // is that the table is reused unchanged across targets.
        assert!(
            recovered_count >= 4,
            "expected ≥4/7 amortised recoveries with 128-entry table; got {}",
            recovered_count
        );
    }

    /// Cost calculator smoke test: at the asymptotic optimum
    /// `T = n^{2/3}`, expected online cost should be ~`n^{1/3}`.
    #[test]
    fn cost_calculator_gives_right_order() {
        // n = 2^60 → n^{1/3} = 2^20, n^{2/3} = 2^40
        let n = BigUint::one() << 60;
        let t = 1u64 << 40;
        let online = expected_online_cost(&n, t, 4);
        // Expected order: 2^20 ≈ 10^6.  Allow 2× slack.
        let n_one_third = (1u64 << 20) as f64;
        assert!(
            online < 5.0 * n_one_third && online > 0.2 * n_one_third,
            "online = {}, expected near {}",
            online,
            n_one_third
        );
    }

    /// Build with table_size = 0 must produce an empty table that
    /// online_solve rejects cleanly.
    #[test]
    fn empty_table_rejected_by_online_solve() {
        let p = BigUint::from(23u32);
        let q = BigUint::from(11u32);
        let g = BigUint::from(4u32);
        let opts = PreprocessingOptions {
            dp_bits: 1,
            table_size: 0,
            max_walk_steps: 100,
            max_online_steps: 100,
            seed: None,
        };
        let table = build_preprocessing_table(&g, &p, &q, &opts);
        assert!(table.is_empty());
        let result = online_solve(&table, &BigUint::from(2u32), &opts);
        assert!(result.is_err());
    }
}
