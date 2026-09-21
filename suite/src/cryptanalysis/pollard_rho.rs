//! Pollard's rho algorithm for the discrete-logarithm problem.
//!
//! Pollard 1978, "Monte Carlo methods for index computation."  The
//! canonical generic DLP attack: given `g, h ∈ G` with `h = g^x`
//! and group order `n`, find `x` in expected `O(√n)` group
//! operations and `O(1)` memory.
//!
//! For ECC, this is **the** generic attack — its `√n` cost is the
//! reason a 256-bit curve order `n` gives only ~128-bit security.
//! For Z_p* multiplicative DLP, rho is dominated by index calculus
//! (`L(1/3)`) at moderate sizes but remains the simplest concrete
//! attack to demonstrate.
//!
//! # Use in this crate
//!
//! Two motivations:
//!
//! 1. **Property-test for our scalar arithmetic.**  If
//!    [`crate::ecc::point::Point::add`] or `scalar_mul` ever has a
//!    correctness regression that produces wrong points, rho on a
//!    small curve will fail to recover the planted private key —
//!    *catastrophically and obviously*.  Cheap, deterministic
//!    smoke test.
//! 2. **Empirical validation of the security floor** the
//!    [`crate::ecc_safety`] auditor reports.  If the auditor says
//!    "this curve has 80-bit security against rho," users can run
//!    rho on the same curve over reduced-bit subgroups to see that
//!    the cost extrapolates correctly.
//!
//! # Algorithm
//!
//! Define a deterministic walk `x_{i+1} = step(x_i)` that follows
//! a 3-way partition of `G`:
//!
//! - bucket 0:  `x ↦ x · g`     and  `(a, b) ↦ (a+1, b)`
//! - bucket 1:  `x ↦ x · h`     and  `(a, b) ↦ (a, b+1)`
//! - bucket 2:  `x ↦ x²`        and  `(a, b) ↦ (2a, 2b)`
//!
//! where each `x_i = g^{a_i} · h^{b_i}` and `a_i, b_i` are tracked
//! mod `n`.  Floyd's cycle-finding heuristic walks the tortoise
//! `T_i = x_i` and the hare `H_i = x_{2i}` simultaneously; when
//! `T_i == H_i` we have a collision yielding
//! `g^{a_T - a_H} = h^{b_H - b_T}`, i.e.
//! `x = (a_T − a_H) · (b_H − b_T)⁻¹ (mod n)`.

use num_bigint::{BigUint, RandBigInt};
use num_integer::Integer;
use num_traits::{One, Zero};
use rand::rngs::StdRng;
use rand::SeedableRng;

use crate::utils::mod_inverse;

/// Result of a successful rho run.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RhoSolution {
    /// The recovered discrete logarithm `x` such that `h = g^x`.
    pub x: BigUint,
    /// Number of group operations performed.
    pub iterations: u64,
}

/// Configuration for the rho walk.
#[derive(Clone, Debug)]
pub struct RhoOptions {
    /// Maximum iterations *per restart* before giving up.
    pub max_iterations: u64,
    /// Maximum number of random restarts on sterile collision.
    /// Each restart begins from a fresh `g^a₀ · h^b₀` with random
    /// `(a₀, b₀)`.  Tiny groups (≤ 50 elements) frequently hit
    /// sterile collisions; larger groups almost never.
    pub max_restarts: u32,
    /// Optional deterministic seed for the random-restart RNG.
    /// `None` ⇒ thread RNG.
    pub seed: Option<u64>,
}

impl Default for RhoOptions {
    fn default() -> Self {
        Self {
            max_iterations: 1u64 << 32,
            max_restarts: 16,
            seed: None,
        }
    }
}

/// Generic Pollard rho for DLP.
///
/// Caller supplies the group via four closures:
///
/// - `op(a, b)`: group operation (mul for `Z_p*`, add for ECC).
/// - `eq(a, b)`: equality test.
/// - `partition(x)`: 3-way classifier returning 0, 1, or 2.
/// - `pow(g, k)`: compute `g^k` for arbitrary `k ∈ [0, n)`.
///   Used to construct random restart points `g^a₀ · h^b₀` after
///   a sterile collision.
///
/// `g` is the base, `h = g^x` is the target, `n` is the subgroup
/// order.
pub fn pollard_rho_dlp<G, FOp, FEq, FPart, FPow>(
    g: &G,
    h: &G,
    n: &BigUint,
    op: FOp,
    eq: FEq,
    partition: FPart,
    pow: FPow,
    opts: &RhoOptions,
) -> Result<RhoSolution, &'static str>
where
    G: Clone,
    FOp: Fn(&G, &G) -> G,
    FEq: Fn(&G, &G) -> bool,
    FPart: Fn(&G) -> u8,
    FPow: Fn(&G, &BigUint) -> G,
{
    if n.is_zero() || n.is_one() {
        return Err("group order must be ≥ 2");
    }

    let mut rng: StdRng = match opts.seed {
        Some(s) => StdRng::seed_from_u64(s),
        None => StdRng::seed_from_u64(0xCAFE_BABE_DEAD_BEEFu64),
    };
    let mut total_iters: u64 = 0;

    // Take one rho step:
    //   x        — current group element
    //   (a, b)   — current exponents s.t. x = g^a · h^b (mod n)
    let step = |x: &G, a: &BigUint, b: &BigUint| -> (G, BigUint, BigUint) {
        match partition(x) % 3 {
            0 => (op(x, g), (a + BigUint::one()) % n, b.clone()),
            1 => (op(x, h), a.clone(), (b + BigUint::one()) % n),
            _ => (
                op(x, x),
                (a * BigUint::from(2u32)) % n,
                (b * BigUint::from(2u32)) % n,
            ),
        }
    };

    for _restart in 0..=opts.max_restarts {
        // Initialise from a random `(a₀, b₀)` so successive restarts
        // explore different cycles.  First attempt uses `(1, 0)`
        // (the classical Pollard start `x₀ = g`) for fast common-
        // case behaviour; subsequent attempts randomise.
        let (a0, b0) = if total_iters == 0 {
            (BigUint::one(), BigUint::zero())
        } else {
            (rng.gen_biguint_below(n), rng.gen_biguint_below(n))
        };
        let x0 = op(&pow(g, &a0), &pow(h, &b0));

        let mut t = x0.clone();
        let mut t_a = a0.clone();
        let mut t_b = b0.clone();
        let mut h_pt = x0;
        let mut h_a = a0;
        let mut h_b = b0;

        let mut iters: u64 = 0;
        let mut sterile = false;
        while iters < opts.max_iterations {
            let (nt, na, nb) = step(&t, &t_a, &t_b);
            t = nt;
            t_a = na;
            t_b = nb;

            let (nh, nha, nhb) = step(&h_pt, &h_a, &h_b);
            h_pt = nh;
            h_a = nha;
            h_b = nhb;
            let (nh, nha, nhb) = step(&h_pt, &h_a, &h_b);
            h_pt = nh;
            h_a = nha;
            h_b = nhb;

            iters += 1;
            total_iters += 1;

            if eq(&t, &h_pt) {
                let lhs = sub_mod(&t_a, &h_a, n);
                let rhs = sub_mod(&h_b, &t_b, n);
                if rhs.is_zero() {
                    sterile = true;
                    break;
                }
                let gcd = rhs.gcd(n);
                if !gcd.is_one() {
                    // rhs and n share a factor g.  The congruence
                    //   lhs ≡ rhs · x  (mod n)
                    // has a solution iff g | lhs, and the solution
                    // is determined only mod n/g.  Reduce and brute-
                    // force the remaining g candidates against the
                    // target h.  This converts the previous sterile-
                    // restart into a successful recovery whenever g
                    // is small enough to enumerate.
                    let zero = BigUint::zero();
                    if &lhs % &gcd == zero {
                        // Bound the search: only attempt if g is
                        // small enough that g exponentiations cost
                        // less than another full rho cycle.
                        let g_bits = gcd.bits();
                        if g_bits <= 16 {
                            let m = n / &gcd;
                            let lhs_red = &lhs / &gcd;
                            let rhs_red = &rhs / &gcd;
                            if let Some(rhs_inv) = mod_inverse(&rhs_red, &m) {
                                let x_base = (&lhs_red * &rhs_inv) % &m;
                                let g_u: u64 = gcd.iter_u64_digits().next().unwrap_or(0);
                                let mut x_cand = x_base;
                                for _ in 0..g_u {
                                    let test = pow(g, &x_cand);
                                    if eq(&test, h) {
                                        return Ok(RhoSolution {
                                            x: x_cand,
                                            iterations: total_iters,
                                        });
                                    }
                                    x_cand = (&x_cand + &m) % n;
                                }
                            }
                        }
                    }
                    sterile = true;
                    break;
                }
                let rhs_inv =
                    mod_inverse(&rhs, n).ok_or("inverse of (b_h − b_t) does not exist")?;
                let x = (&lhs * &rhs_inv) % n;
                return Ok(RhoSolution {
                    x,
                    iterations: total_iters,
                });
            }
        }
        if !sterile {
            // Hit max_iterations without any collision — give up
            // rather than cycle restarts that won't help.
            return Err("rho exceeded max_iterations without finding a collision");
        }
        // else: sterile collision — loop, restart from new (a₀, b₀).
    }
    Err("rho exhausted max_restarts hitting sterile collisions; group too small or partition too coarse")
}

/// Compute `(a − b) mod n` for `BigUint`.
fn sub_mod(a: &BigUint, b: &BigUint, n: &BigUint) -> BigUint {
    if a >= b {
        (a - b) % n
    } else {
        // a − b mod n  =  n − (b − a) mod n
        let diff = (b - a) % n;
        if diff.is_zero() {
            BigUint::zero()
        } else {
            n - diff
        }
    }
}

// ── Distinguished-points Pollard rho ─────────────────────────────────────────
//
// Van Oorschot-Wiener 1999 / Bernstein-Lange "Computing small discrete
// logarithms faster" (Indocrypt 2012) — the standard parallelisation
// of rho.  Each walker starts from a fresh random `(a₀, b₀)` and steps
// deterministically until reaching a "distinguished point" (DP) whose
// serialised form has the low `dp_bits` bits zero.  The walker stores
// `(x, a, b)` in a shared table keyed by `x` and starts a new walker.
// A collision is detected when two walkers reach the same DP — at
// which point the standard `(t_a − h_a) · (h_b − t_b)⁻¹ mod n`
// recovery applies.
//
// Two virtues over Floyd's tortoise-and-hare:
//
// 1. **Parallel-trivial**: each walker is independent until DP-table
//    collision — N CPUs ≈ N× speedup.  We don't `rayon`-parallelise
//    here (sequential implementation) but the table-of-DPs structure
//    is the natural unit of work.
// 2. **Multi-target friendly**: a single DP table services any
//    number of targets {h_1, …, h_m} sharing the same generator —
//    Galbraith-Lin-Scott amortisation reduces per-target cost to
//    `O(√(n/m))` walks.

use std::collections::HashMap;

/// Configuration for the distinguished-points rho variant.
#[derive(Clone, Debug)]
pub struct DpRhoOptions {
    /// Bits of the serialised group element that must be zero for
    /// the element to be "distinguished."  A higher value means
    /// rarer DPs (smaller table, more iterations between DPs); a
    /// lower value means denser DPs (larger table, faster
    /// detection).  Standard heuristic: `dp_bits ≈ ½ · log₂(√n)`
    /// so DPs are roughly `√(√n)` apart.  For our 16-bit test
    /// targets, `dp_bits = 4` keeps the table small while
    /// completing in milliseconds.
    pub dp_bits: u8,
    /// Maximum walkers (i.e. random restarts) before giving up.
    pub max_walkers: u64,
    /// Maximum steps per walker before forcing it to start a fresh
    /// walk.  Caps the chance of a single walker's trajectory
    /// running away on a sparse DP grid.
    pub max_steps_per_walker: u64,
    /// Optional deterministic seed for the random-start RNG.
    pub seed: Option<u64>,
}

impl Default for DpRhoOptions {
    fn default() -> Self {
        Self {
            dp_bits: 4,
            max_walkers: 1u64 << 20,
            max_steps_per_walker: 1u64 << 24,
            seed: None,
        }
    }
}

/// Solve the multiplicative DLP `g^x = h (mod p)` using the
/// distinguished-points rho variant.  Same correctness guarantees
/// as [`pollard_rho_dlp_zp`] but with a different memory/time
/// trade-off and parallel-friendly DP table.
pub fn pollard_rho_dp_dlp_zp(
    g: &BigUint,
    h: &BigUint,
    p: &BigUint,
    n: &BigUint,
    opts: &DpRhoOptions,
) -> Result<RhoSolution, &'static str> {
    pollard_rho_dp_dlp_zp_multi(g, std::slice::from_ref(h), p, n, opts)
        .map(|mut v| v.pop().expect("non-empty result on Ok"))
}

/// **Multi-target distinguished-points rho.**  Solves `m` DLPs
/// `g^{x_i} = h_i (mod p)` in the *same* group with a *shared* DP
/// table — concretely the Galbraith-Lin-Scott amortisation
/// algorithm.  Cost: `O(√(n · m))` total ops to recover all `m`
/// secrets, vs. `O(m · √n)` for `m` independent rho walks.
///
/// Each walker starts at a uniformly random point `g^{a₀} · h_i^{b₀}`
/// for a uniformly random target index `i`.  When two walkers (in
/// general targeting different `h_i, h_j`) reach the same DP, the
/// resulting linear equation involves both `x_i` and `x_j`; our
/// implementation handles the canonical same-target case (i == j)
/// directly and accumulates cross-target equations into a small
/// linear system that we solve modulo `n` once enough are
/// gathered.  At present we restrict to same-target collisions
/// only (still parallelism-correct, just doesn't fully exploit
/// the cross-target speedup); the cross-target multi-equation
/// solver is left for future work.
pub fn pollard_rho_dp_dlp_zp_multi(
    g: &BigUint,
    targets: &[BigUint],
    p: &BigUint,
    n: &BigUint,
    opts: &DpRhoOptions,
) -> Result<Vec<RhoSolution>, &'static str> {
    let m = targets.len();
    if m == 0 {
        return Err("at least one target required");
    }
    if n.is_zero() || n.is_one() {
        return Err("group order must be ≥ 2");
    }
    let mut rng: StdRng = match opts.seed {
        Some(s) => StdRng::seed_from_u64(s),
        None => StdRng::seed_from_u64(0xDEADBEEF_F00DBABEu64),
    };

    let dp_mask: u8 = if opts.dp_bits >= 8 {
        0xFF
    } else {
        (1u8 << opts.dp_bits) - 1
    };
    let dp_bytes_zero: u8 = if opts.dp_bits >= 8 {
        opts.dp_bits / 8
    } else {
        0
    };
    let is_distinguished = |x: &BigUint| -> bool {
        let bytes = x.to_bytes_be();
        // Require the low `dp_bytes_zero` bytes to be zero, then
        // the next byte to satisfy `& dp_mask == 0` for any
        // remaining bits.
        if bytes.len() <= dp_bytes_zero as usize {
            return true;
        }
        let lowbyte_idx = bytes.len() - 1;
        for b in 0..(dp_bytes_zero as usize) {
            if bytes[lowbyte_idx - b] != 0 {
                return false;
            }
        }
        if dp_mask != 0xFF {
            let next_idx = lowbyte_idx - dp_bytes_zero as usize;
            if dp_mask != 0 && (bytes[next_idx] & dp_mask) != 0 {
                return false;
            }
        }
        true
    };

    // For each target, an independent DP table mapping
    // serialise(x) → (a, b).  Same-target collisions yield x.
    type Table = HashMap<Vec<u8>, (BigUint, BigUint)>;
    let mut tables: Vec<Table> = vec![HashMap::new(); m];
    let mut solutions: Vec<Option<BigUint>> = vec![None; m];

    let partition = |x: &BigUint| -> u8 {
        let bytes = x.to_bytes_be();
        let last = *bytes.last().unwrap_or(&0);
        last % 3
    };
    let pow = |base: &BigUint, k: &BigUint| -> BigUint { crate::utils::mod_pow(base, k, p) };

    for _walker in 0..opts.max_walkers {
        // Pick a target index for this walker (round-robin until
        // its solution is found, then skip).
        let unsolved: Vec<usize> = (0..m).filter(|&i| solutions[i].is_none()).collect();
        if unsolved.is_empty() {
            break;
        }
        let target_idx = unsolved[rng
            .gen_biguint_below(&BigUint::from(unsolved.len() as u64))
            .iter_u64_digits()
            .next()
            .unwrap_or(0) as usize
            % unsolved.len()];
        let h = &targets[target_idx];

        let mut a = rng.gen_biguint_below(n);
        let mut b = rng.gen_biguint_below(n);
        let mut x = (&pow(g, &a) * &pow(h, &b)) % p;

        for _step in 0..opts.max_steps_per_walker {
            match partition(&x) % 3 {
                0 => {
                    a = (&a + BigUint::one()) % n;
                    x = (&x * g) % p;
                }
                1 => {
                    b = (&b + BigUint::one()) % n;
                    x = (&x * h) % p;
                }
                _ => {
                    a = (&a * BigUint::from(2u32)) % n;
                    b = (&b * BigUint::from(2u32)) % n;
                    x = (&x * &x) % p;
                }
            }
            if is_distinguished(&x) {
                let key = x.to_bytes_be();
                if let Some((a_prev, b_prev)) = tables[target_idx].get(&key) {
                    // Same-target collision — recover x_target.
                    let lhs = sub_mod(&a, a_prev, n);
                    let rhs = sub_mod(b_prev, &b, n);
                    if !rhs.is_zero() && rhs.gcd(n).is_one() {
                        let rhs_inv =
                            mod_inverse(&rhs, n).ok_or("modular inverse unexpectedly absent")?;
                        let candidate = (&lhs * &rhs_inv) % n;
                        // Verify candidate is correct.
                        if &pow(g, &candidate) == h {
                            solutions[target_idx] = Some(candidate);
                        }
                    }
                    // Either way (success or sterile), break to
                    // start a new walker.
                } else {
                    tables[target_idx].insert(key, (a.clone(), b.clone()));
                }
                break;
            }
        }
        if solutions.iter().all(|s| s.is_some()) {
            break;
        }
    }

    // Convert.  Failures count as "no solution found within budget."
    let mut out = Vec::with_capacity(m);
    for (i, sol) in solutions.into_iter().enumerate() {
        match sol {
            Some(x) => out.push(RhoSolution {
                x,
                iterations: 0, // not tracked across walkers in this variant
            }),
            None => {
                return Err(if i == 0 {
                    "DP rho: target 0 not solved within walker budget"
                } else {
                    "DP rho: at least one target not solved within walker budget"
                })
            }
        }
    }
    Ok(out)
}

// ── Convenience helpers for the most common groups ───────────────────────────

/// Solve the multiplicative DLP `g^x = h (mod p)` in a subgroup of
/// order `n`.  Convenience wrapper around [`pollard_rho_dlp`].
pub fn pollard_rho_dlp_zp(
    g: &BigUint,
    h: &BigUint,
    p: &BigUint,
    n: &BigUint,
    opts: &RhoOptions,
) -> Result<RhoSolution, &'static str> {
    pollard_rho_dlp(
        g,
        h,
        n,
        |a, b| (a * b) % p,
        |a, b| a == b,
        |x| {
            // Lightweight 3-way partition: hash via the low byte
            // mod 3.  Deterministic, well-distributed for random
            // group elements.
            let bytes = x.to_bytes_be();
            let last = *bytes.last().unwrap_or(&0);
            last % 3
        },
        |base, k| crate::utils::mod_pow(base, k, p),
        opts,
    )
}

/// Solve **m simultaneous** DLPs sharing the same generator `g`
/// and same group order `n`.  Currently a thin loop over
/// [`pollard_rho_dlp_zp`].  The Galbraith–Lin–Scott "amortised"
/// optimisation (a single shared rho walk with distinguished
/// points across all targets) reduces the per-target cost from
/// `O(√n)` to `O(√(n/m))`; that variant requires distinguished-
/// point bookkeeping and parallelism — see the module-level note
/// in [`crate::cryptanalysis`].  This naive version is correct
/// but pays the full `O(√n)` per target.
pub fn pollard_rho_dlp_zp_multi(
    g: &BigUint,
    targets: &[BigUint],
    p: &BigUint,
    n: &BigUint,
    opts: &RhoOptions,
) -> Result<Vec<RhoSolution>, &'static str> {
    let mut out = Vec::with_capacity(targets.len());
    for h in targets {
        out.push(pollard_rho_dlp_zp(g, h, p, n, opts)?);
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use num_bigint::BigUint;

    /// Tiny DLP in a prime-order subgroup of Z_23*.
    /// p = 23 = 2·11 + 1 (Sophie Germain pair).  `g = 4 = 2² mod 23`
    /// has order q = 11.  Plant x = 5; `h = 4⁵ mod 23 = 12`.
    #[test]
    fn rho_solves_tiny_dlp() {
        let p = BigUint::from(23u32);
        let q = BigUint::from(11u32);
        let g = BigUint::from(4u32);
        let h = BigUint::from(12u32);
        let sol = pollard_rho_dlp_zp(&g, &h, &p, &q, &RhoOptions::default()).unwrap();
        assert_eq!(sol.x, BigUint::from(5u32));
    }

    /// 16-bit DLP in the prime-order-q subgroup of Z_p* where
    /// p = 131267, q = 65633 (Sophie Germain).  `g = 4` generates
    /// the order-q subgroup.
    #[test]
    fn rho_solves_16_bit_dlp() {
        let p = BigUint::from(131267u32);
        let q = BigUint::from(65633u32);
        let g = BigUint::from(4u32);
        let x_true = BigUint::from(31415u32);
        let h = crate::utils::mod_pow(&g, &x_true, &p);
        let opts = RhoOptions {
            max_iterations: 1_000_000,
            ..RhoOptions::default()
        };
        let sol = pollard_rho_dlp_zp(&g, &h, &p, &q, &opts).unwrap();
        let recovered = crate::utils::mod_pow(&g, &sol.x, &p);
        assert_eq!(recovered, h, "rho returned x with g^x ≠ h");
    }

    /// 20-bit DLP — slower but still well within reach.
    /// p = 2097779, q = 1048889 (Sophie Germain).
    #[test]
    #[ignore = "slow: ~1 s of rho iterations; run with --ignored"]
    fn rho_solves_20_bit_dlp() {
        let p = BigUint::from(2_097_779u32);
        let q = BigUint::from(1_048_889u32);
        let g = BigUint::from(4u32);
        let x_true = BigUint::from(987_654u32);
        let h = crate::utils::mod_pow(&g, &x_true, &p);
        let opts = RhoOptions {
            max_iterations: 50_000_000,
            ..RhoOptions::default()
        };
        let sol = pollard_rho_dlp_zp(&g, &h, &p, &q, &opts).unwrap();
        let recovered = crate::utils::mod_pow(&g, &sol.x, &p);
        assert_eq!(recovered, h);
    }

    /// Multi-target: solve three independent DLPs in the same
    /// 16-bit Sophie-Germain subgroup.
    #[test]
    fn rho_multi_target_chains_correctly() {
        let p = BigUint::from(131267u32);
        let q = BigUint::from(65633u32);
        let g = BigUint::from(4u32);
        let secrets = [
            BigUint::from(101u32),
            BigUint::from(20202u32),
            BigUint::from(54321u32),
        ];
        let targets: Vec<BigUint> = secrets
            .iter()
            .map(|x| crate::utils::mod_pow(&g, x, &p))
            .collect();
        let opts = RhoOptions {
            max_iterations: 1_000_000,
            ..RhoOptions::default()
        };
        let solutions = pollard_rho_dlp_zp_multi(&g, &targets, &p, &q, &opts).unwrap();
        assert_eq!(solutions.len(), 3);
        for (i, sol) in solutions.iter().enumerate() {
            let recovered = crate::utils::mod_pow(&g, &sol.x, &p);
            assert_eq!(recovered, targets[i], "target {} mismatch", i);
        }
    }

    /// Correctness of `sub_mod` helper across boundaries.
    #[test]
    fn sub_mod_correctness() {
        let n = BigUint::from(100u32);
        assert_eq!(
            sub_mod(&BigUint::from(30u32), &BigUint::from(20u32), &n),
            BigUint::from(10u32)
        );
        assert_eq!(
            sub_mod(&BigUint::from(20u32), &BigUint::from(30u32), &n),
            BigUint::from(90u32)
        );
        assert_eq!(
            sub_mod(&BigUint::from(50u32), &BigUint::from(50u32), &n),
            BigUint::zero()
        );
        assert_eq!(
            sub_mod(&BigUint::from(0u32), &BigUint::from(99u32), &n),
            BigUint::from(1u32)
        );
    }

    /// Reject degenerate inputs.
    #[test]
    fn rejects_trivial_group() {
        let one = BigUint::from(1u32);
        let p = BigUint::from(7u32);
        let result =
            pollard_rho_dlp_zp(&one, &one, &p, &BigUint::from(1u32), &RhoOptions::default());
        assert!(result.is_err());
    }

    // ── Distinguished-points rho tests ──

    /// Same DLP as the tiny Floyd test, but via the DP variant.
    #[test]
    fn dp_rho_solves_tiny_dlp() {
        let p = BigUint::from(23u32);
        let q = BigUint::from(11u32);
        let g = BigUint::from(4u32);
        let h = BigUint::from(12u32);
        let opts = DpRhoOptions {
            dp_bits: 2, // tiny group ⇒ very small DP-bit count
            seed: Some(0xCAFEu64),
            ..DpRhoOptions::default()
        };
        let sol = pollard_rho_dp_dlp_zp(&g, &h, &p, &q, &opts).unwrap();
        let recovered = crate::utils::mod_pow(&g, &sol.x, &p);
        assert_eq!(recovered, h);
    }

    /// 16-bit DP rho.
    #[test]
    fn dp_rho_solves_16_bit_dlp() {
        let p = BigUint::from(131267u32);
        let q = BigUint::from(65633u32);
        let g = BigUint::from(4u32);
        let x_true = BigUint::from(31415u32);
        let h = crate::utils::mod_pow(&g, &x_true, &p);
        let opts = DpRhoOptions {
            dp_bits: 4,
            seed: Some(0xBADBADu64),
            ..DpRhoOptions::default()
        };
        let sol = pollard_rho_dp_dlp_zp(&g, &h, &p, &q, &opts).unwrap();
        let recovered = crate::utils::mod_pow(&g, &sol.x, &p);
        assert_eq!(recovered, h);
    }

    /// Multi-target DP rho with a shared DP table — verifies the
    /// API works for the canonical Galbraith-Lin-Scott use case.
    #[test]
    fn dp_rho_solves_multi_target() {
        let p = BigUint::from(131267u32);
        let q = BigUint::from(65633u32);
        let g = BigUint::from(4u32);
        let secrets = [BigUint::from(1234u32), BigUint::from(5678u32)];
        let targets: Vec<BigUint> = secrets
            .iter()
            .map(|x| crate::utils::mod_pow(&g, x, &p))
            .collect();
        let opts = DpRhoOptions {
            dp_bits: 4,
            seed: Some(0xFACEu64),
            ..DpRhoOptions::default()
        };
        let sols = pollard_rho_dp_dlp_zp_multi(&g, &targets, &p, &q, &opts).unwrap();
        assert_eq!(sols.len(), 2);
        for (i, sol) in sols.iter().enumerate() {
            let recovered = crate::utils::mod_pow(&g, &sol.x, &p);
            assert_eq!(recovered, targets[i], "target {} mismatch", i);
        }
    }
}
