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
use num_traits::{One, ToPrimitive, Zero};
use rand::rngs::StdRng;
use rand::SeedableRng;

use crate::utils::mod_inverse;

/// Seed of the restart RNG when [`RhoOptions::seed`] is `None`.
const FLOYD_DEFAULT_SEED: u64 = 0xCAFE_BABE_DEAD_BEEF;

const ERR_NO_COLLISION: &str = "rho exceeded max_iterations without finding a collision";
const ERR_ALL_STERILE: &str = "rho exhausted max_restarts hitting sterile collisions; group too small or partition too coarse";
const ERR_NOT_A_LOG: &str = "rho collision does not satisfy g^x = h: the target is not \
                             in <g>, or n is not the order of g";

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
    /// `None` ⇒ a fixed default seed, so runs are reproducible.
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

    let mut rng = StdRng::seed_from_u64(opts.seed.unwrap_or(FLOYD_DEFAULT_SEED));
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
                let is_log = |x: &BigUint| eq(&pow(g, x), h);
                match floyd_collision(&t_a, &t_b, &h_a, &h_b, n, is_log)? {
                    Some(x) => {
                        return Ok(RhoSolution {
                            x,
                            iterations: total_iters,
                        })
                    }
                    None => {
                        sterile = true;
                        break;
                    }
                }
            }
        }
        if !sterile {
            // Hit max_iterations without any collision — give up
            // rather than cycle restarts that won't help.
            return Err(ERR_NO_COLLISION);
        }
        // else: sterile collision — loop, restart from new (a₀, b₀).
    }
    Err(ERR_ALL_STERILE)
}

/// Resolve a Floyd collision `g^{a_T} h^{b_T} = g^{a_H} h^{b_H}`:
/// `Ok(Some(x))` is the logarithm, `Ok(None)` a sterile collision (the
/// caller restarts).  `is_log(x)` tests a candidate against `h`: it picks
/// the right candidate when `b_H − b_T` shares a factor with `n`, and it
/// refuses a logarithm that is not one, which is what a collision gives
/// when `h` is outside `<g>` or `n` is not the order of `g`.
///
/// Collisions happen once per restart, so this stays in `BigUint` even
/// for the single-word `Z_p^*` walk, which converts its exponents and
/// calls it: both walks then resolve a collision with the same code.
fn floyd_collision(
    t_a: &BigUint,
    t_b: &BigUint,
    h_a: &BigUint,
    h_b: &BigUint,
    n: &BigUint,
    is_log: impl Fn(&BigUint) -> bool,
) -> Result<Option<BigUint>, &'static str> {
    let lhs = sub_mod(t_a, h_a, n);
    let rhs = sub_mod(h_b, t_b, n);
    if rhs.is_zero() {
        return Ok(None);
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
                        if is_log(&x_cand) {
                            return Ok(Some(x_cand));
                        }
                        x_cand = (&x_cand + &m) % n;
                    }
                }
            }
        }
        return Ok(None);
    }
    let rhs_inv = mod_inverse(&rhs, n).ok_or("inverse of (b_h − b_t) does not exist")?;
    let x = (&lhs * &rhs_inv) % n;
    // A collision solves g^x = h only when h is in <g> and n is
    // ord(g); otherwise the congruence has an answer that is
    // simply wrong.  Never report one unchecked.
    if !is_log(&x) {
        return Err(ERR_NOT_A_LOG);
    }
    Ok(Some(x))
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
///
/// For an odd `p < 2^64` and `n < 2^64` the walkers run on machine
/// words (see the single-word section below), with the same results.
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

    let solutions = match WordZp::new(p, n) {
        Some(w) => dp_walks_word(&w, g, targets, p, n, opts, &mut rng)?,
        None => dp_walks_big(g, targets, p, n, opts, &mut rng)?,
    };

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

/// The walkers of [`pollard_rho_dp_dlp_zp_multi`] on `BigUint`: the
/// reference [`dp_walks_word`] reproduces, and the path for `p` or `n` of
/// two words or more.  Returns each target's verified logarithm, if found.
fn dp_walks_big(
    g: &BigUint,
    targets: &[BigUint],
    p: &BigUint,
    n: &BigUint,
    opts: &DpRhoOptions,
    rng: &mut StdRng,
) -> Result<Vec<Option<BigUint>>, &'static str> {
    let m = targets.len();
    let (dp_mask, dp_bytes_zero) = dp_rule(opts.dp_bits);
    let is_distinguished = |x: &BigUint| is_distinguished_be(x, dp_mask, dp_bytes_zero);

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
        let Some(target_idx) = pick_target(rng, &solutions) else {
            break;
        };
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
                    if let Some(log) = dp_collision(&a, &b, a_prev, b_prev, g, h, p, n)? {
                        solutions[target_idx] = Some(log);
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
    Ok(solutions)
}

/// Pick the target a new walker serves: uniformly among the unsolved
/// ones (`None` once every target is solved).  The draw is a
/// `gen_biguint_below`, whichever walk calls it, so both walks consume the
/// RNG identically.
fn pick_target(rng: &mut StdRng, solutions: &[Option<BigUint>]) -> Option<usize> {
    let unsolved = || (0..solutions.len()).filter(|&i| solutions[i].is_none());
    let count = unsolved().count();
    if count == 0 {
        return None;
    }
    let k = rng
        .gen_biguint_below(&BigUint::from(count as u64))
        .iter_u64_digits()
        .next()
        .unwrap_or(0) as usize
        % count;
    // The k-th unsolved index, counting in index order, without collecting
    // them: a walker is picked every few hundred steps.
    unsolved().nth(k)
}

/// `(dp_mask, dp_bytes_zero)` for [`is_distinguished_be`]: `dp_bits < 8`
/// tests the low bits of the last byte; `dp_bits >= 8` asks for
/// `dp_bits / 8` whole zero bytes and tests no further bits.
fn dp_rule(dp_bits: u8) -> (u8, u8) {
    let dp_mask: u8 = if dp_bits >= 8 {
        0xFF
    } else {
        (1u8 << dp_bits) - 1
    };
    let dp_bytes_zero: u8 = if dp_bits >= 8 { dp_bits / 8 } else { 0 };
    (dp_mask, dp_bytes_zero)
}

/// The distinguished-point test on the big-endian serialisation of `x`.
/// This is the definition; [`WordDp`] restates it on a machine word.
fn is_distinguished_be(x: &BigUint, dp_mask: u8, dp_bytes_zero: u8) -> bool {
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
}

/// Same-target collision at a DP reached from `(a, b)` and earlier from
/// `(a_prev, b_prev)`: the logarithm of `h` when the collision is
/// non-degenerate and the candidate checks out against `h`, else `None`.
#[allow(clippy::too_many_arguments)]
fn dp_collision(
    a: &BigUint,
    b: &BigUint,
    a_prev: &BigUint,
    b_prev: &BigUint,
    g: &BigUint,
    h: &BigUint,
    p: &BigUint,
    n: &BigUint,
) -> Result<Option<BigUint>, &'static str> {
    let lhs = sub_mod(a, a_prev, n);
    let rhs = sub_mod(b_prev, b, n);
    if !rhs.is_zero() && rhs.gcd(n).is_one() {
        let rhs_inv = mod_inverse(&rhs, n).ok_or("modular inverse unexpectedly absent")?;
        let candidate = (&lhs * &rhs_inv) % n;
        // Verify candidate is correct.
        if &crate::utils::mod_pow(g, &candidate, p) == h {
            return Ok(Some(candidate));
        }
    }
    Ok(None)
}

// ── Convenience helpers for the most common groups ───────────────────────────

/// Solve the multiplicative DLP `g^x = h (mod p)` in a subgroup of
/// order `n`.  Convenience wrapper around [`pollard_rho_dlp`]; for an odd
/// `p < 2^64` and `n < 2^64` it runs the same walk on machine words (see
/// the single-word section below), with the same result and iteration
/// count.
pub fn pollard_rho_dlp_zp(
    g: &BigUint,
    h: &BigUint,
    p: &BigUint,
    n: &BigUint,
    opts: &RhoOptions,
) -> Result<RhoSolution, &'static str> {
    match WordZp::new(p, n) {
        Some(w) => rho_floyd_word(&w, g, h, p, n, opts),
        None => rho_floyd_big(g, h, p, n, opts),
    }
}

/// [`pollard_rho_dlp`] with `Z_p^*` closures: the reference
/// [`rho_floyd_word`] reproduces, and the path for `p` or `n` of two
/// words or more.
fn rho_floyd_big(
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

// ── Single-word Z_p^* walks (odd p < 2^64) ───────────────────────────────────
//
// At the sizes rho is actually run on, `p` fits in one word, yet on
// `BigUint` a step costs about six heap-allocating operations plus a
// `to_bytes_be` serialisation for the partition (and a second one for the
// DP test): at a 36-bit `p`, allocation and serialisation are most of the
// time and the multiply-and-reduce the step exists for is a small part.
// When `p` is odd and below 2^64 and `n` is below 2^64, the walks below
// run the same steps on `u64` state, and everything they report is
// unchanged:
//
// - the partition is `x mod 256 mod 3`, which is what the last byte of
//   `x.to_bytes_be()` gives (`0` serialises as `[0]`);
// - the DP test is [`WordDp`], the byte rule restated on a word,
//   including its whole-byte rounding and its length clause;
// - the random starts are the same `gen_biguint_below` calls on the same
//   `StdRng`, converted to a word after the draw, so the RNG stream is
//   the same draw for draw;
// - collisions go through the same `BigUint` code as the reference walk
//   ([`floyd_collision`], [`dp_collision`]); they happen once per restart
//   or DP hit, so their cost does not matter;
// - the DP tables are keyed by the word instead of its serialisation,
//   which is the same map, since serialisation is injective.
//
// Anything else (`p` even or below 3, `p` or `n` of two words or more)
// takes the `BigUint` walk, which stays the reference: the tests run both
// walks on the same inputs and require equal results, iteration counts
// and final RNG state, and hold both public functions to a verbatim copy
// of the code before the word walks.

/// Arithmetic for a single-word `Z_p^*` walk: Montgomery multiplication
/// modulo an odd `p < 2^64`, and exponent arithmetic modulo `n < 2^64`.
///
/// A walk carries its element in both forms ([`WordPoint`]): Montgomery
/// form for the multiplications, and canonical (in `[0, p)`) for the
/// partition, the DP test and the collision test, which read the value
/// itself at every step.
///
/// [`crate::cryptanalysis::bsgs_fast::FastField`] is the same idea for
/// `p < 2^63`; its REDC adds `m·p` and needs the headroom.  The REDC here
/// subtracts, which fits one word for every odd `p < 2^64` (see
/// [`Self::redc`]).
#[derive(Clone, Copy, Debug)]
struct WordZp {
    p: u64,
    /// `p^-1 mod 2^64`
    p_inv: u64,
    /// `2^64 mod p`, the Montgomery form of 1
    r: u64,
    /// `2^128 mod p`
    r2: u64,
    /// the exponent modulus (the subgroup order)
    n: u64,
}

impl WordZp {
    /// The word arithmetic for `(p, n)`, or `None` when the walk must stay
    /// on `BigUint`: `p` even or below 3, or `p` or `n` not below 2^64.
    /// `n < 2` is left to the `BigUint` walk, which rejects it.
    fn new(p: &BigUint, n: &BigUint) -> Option<Self> {
        let p = p.to_u64()?;
        let n = n.to_u64()?;
        if p < 3 || p.is_multiple_of(2) || n < 2 {
            return None;
        }
        // p^-1 mod 2^64 by Newton iteration: x_{k+1} = x_k (2 - p x_k)
        // doubles the number of correct low bits, from the 3 that x = p
        // has (p² ≡ 1 mod 8 for odd p) to 96 after five rounds.
        let mut p_inv = p;
        for _ in 0..5 {
            p_inv = p_inv.wrapping_mul(2u64.wrapping_sub(p.wrapping_mul(p_inv)));
        }
        debug_assert_eq!(p.wrapping_mul(p_inv), 1);
        let r = ((1u128 << 64) % p as u128) as u64;
        let r2 = ((r as u128 * r as u128) % p as u128) as u64;
        Some(Self { p, p_inv, r, r2, n })
    }

    /// `t·2^-64 mod p` in `[0, p)`, for `t < p·2^64`.
    ///
    /// With `m = t·p^-1 mod 2^64`, `t − m·p` is divisible by 2^64 and the
    /// low words cancel exactly, so the quotient is `hi(t) − hi(m·p)`.
    /// Both terms are below `p`, so the difference lies in `(−p, p)` and
    /// one conditional add of `p` finishes it; no intermediate exceeds a
    /// word, whatever the top bit of `p`.
    #[inline(always)]
    fn redc(&self, t: u128) -> u64 {
        let m = (t as u64).wrapping_mul(self.p_inv);
        let mp_hi = ((m as u128 * self.p as u128) >> 64) as u64;
        let (d, borrow) = ((t >> 64) as u64).overflowing_sub(mp_hi);
        if borrow {
            d.wrapping_add(self.p)
        } else {
            d
        }
    }

    /// `a·b·2^-64 mod p`, for `a, b < p`.
    #[inline(always)]
    fn mul(&self, a: u64, b: u64) -> u64 {
        self.redc(a as u128 * b as u128)
    }

    /// Montgomery form `x·2^64 mod p` of a group element given as a
    /// `BigUint` of any size (the callers' `g` and `h` need not be reduced).
    fn mont(&self, x: &BigUint) -> u64 {
        let x = (x % self.p).to_u64().expect("x mod p is below p < 2^64");
        self.mul(x, self.r2)
    }

    /// `base^e` for `base` in Montgomery form; the result is in Montgomery
    /// form too.  `e = 0` gives 1, as `crate::utils::mod_pow` does.
    fn pow(&self, base: u64, mut e: u64) -> u64 {
        let mut acc = self.r;
        let mut sq = base;
        while e > 0 {
            if e & 1 == 1 {
                acc = self.mul(acc, sq);
            }
            sq = self.mul(sq, sq);
            e >>= 1;
        }
        acc
    }

    /// `base^(2^i)` for `i < 64`, for `base` in Montgomery form: the table
    /// [`Self::pow_by_table`] reads.
    fn pow_table(&self, base: u64) -> [u64; 64] {
        let mut table = [0; 64];
        let mut sq = base;
        for t in &mut table {
            *t = sq;
            sq = self.mul(sq, sq);
        }
        table
    }

    /// `base^e` from `table = pow_table(base)`, in Montgomery form: the
    /// same residue as [`Self::pow`], for one multiplication per set bit of
    /// `e`.  `pow` also squares at every bit, and its branch on the bit
    /// mispredicts about half the time on a random exponent.  A DP walker
    /// starts from two fresh powers every few hundred steps (`2^dp_bits`
    /// on average), so there the starts are a real share of the run; the
    /// table, built once per base, costs 64 squarings, less than one `pow`
    /// of a full-width exponent.
    fn pow_by_table(&self, table: &[u64; 64], mut e: u64) -> u64 {
        let mut acc = self.r;
        while e != 0 {
            acc = self.mul(acc, table[e.trailing_zeros() as usize]);
            e &= e - 1;
        }
        acc
    }

    /// The walk position of canonical `x < p` with exponents `a`, `b`.
    #[cfg(test)]
    fn point(&self, x: u64, a: u64, b: u64) -> WordPoint {
        WordPoint {
            xm: self.mul(x, self.r2),
            x,
            a,
            b,
        }
    }

    /// The start `g^a · h^b mod p`, from `g^a` and `h^b` in Montgomery
    /// form.
    fn start(&self, g_a: u64, h_b: u64, a: u64, b: u64) -> WordPoint {
        let xm = self.mul(g_a, h_b);
        WordPoint {
            xm,
            x: self.redc(xm as u128),
            a,
            b,
        }
    }

    /// An exponent drawn below `n`, as a word.
    fn exponent(&self, e: &BigUint) -> u64 {
        e.to_u64().expect("an exponent below n < 2^64")
    }

    /// One rho step, with exponents `a, b < n`; `g_r`, `h_r` are the
    /// Montgomery forms of `g` and `h`.  Mirrors the `BigUint` step
    /// exactly: partition by the low byte of `x` mod 3, then `x·g` with
    /// `a + 1`, `x·h` with `b + 1`, or `x²` with `(2a, 2b)`.
    ///
    /// All three products are formed and one is kept, without a branch.
    /// The bucket is a pseudo-random function of `x`, so a branch on it
    /// mispredicts about two steps in three, and each miss stalls a chain
    /// in which every step waits for the last; two spare multiplications
    /// cost less.  They are independent of the bucket, so they run while
    /// the bucket is still being computed from `x`, and the chain per step
    /// is one product, the choice, and the REDC back to canonical `x`.
    #[inline(always)]
    fn step(&self, s: WordPoint, g_r: u64, h_r: u64) -> WordPoint {
        let part = (s.x as u8) % 3;
        let (by_g, by_h) = (part == 0, part == 1);
        let xm = pick(
            by_g,
            self.mul(s.xm, g_r),
            pick(by_h, self.mul(s.xm, h_r), self.mul(s.xm, s.xm)),
        );
        let a = pick(by_g, self.inc(s.a), pick(by_h, s.a, self.dbl(s.a)));
        let b = pick(by_g, s.b, pick(by_h, self.inc(s.b), self.dbl(s.b)));
        WordPoint {
            xm,
            x: self.redc(xm as u128),
            a,
            b,
        }
    }

    /// `(a + 1) mod n` for `a < n`.
    #[inline(always)]
    fn inc(&self, a: u64) -> u64 {
        if a + 1 == self.n {
            0
        } else {
            a + 1
        }
    }

    /// `2a mod n` for `a < n`, without forming `2a` (it may not fit).
    #[inline(always)]
    fn dbl(&self, a: u64) -> u64 {
        let c = self.n - a;
        if a >= c {
            a - c
        } else {
            a + a
        }
    }
}

/// `a` if `take`, else `b`: the choice [`WordZp::step`] makes between its
/// three products and between its exponent updates, with both arguments
/// already computed.
///
/// A plain `if`, which the backend emits as a conditional move.  The
/// intended tool is `std::hint::select_unpredictable`, a promise to the
/// backend that the condition is unpredictable so that it does not rewrite
/// the move as a branch; it is stable only from Rust 1.88 and the crate
/// builds on 1.87.  The bucket is pseudo-random, and a branch on it
/// mispredicts about two steps in three, so keeping the move is the point.
/// The plain `if` leaves that to the compiler, so the guarantee here is
/// what the compiler is seen to do, and it was checked: with rustc 1.87
/// and 1.94 the walks contain no data-dependent branch (callgrind
/// `--branch-sim` counts a few hundred conditional mispredictions in a
/// Floyd run of 1.4 M branches, all of them the loop's own), and with 1.94
/// the two entry points compile to the same machine code, up to constant
/// addresses, as with `select_unpredictable`.  A mask (`-(take as u64)`
/// with `&`/`|`) was tried too: with 1.94 it is branch-free as well, but
/// compiles to different code and measured no faster.  Look at the code
/// again when moving to a new toolchain or architecture.
#[inline(always)]
fn pick(take: bool, a: u64, b: u64) -> u64 {
    if take {
        a
    } else {
        b
    }
}

/// A single-word walk's position: the element `x = g^a · h^b mod p`, in
/// Montgomery form and canonical, and its exponents.
#[derive(Clone, Copy, Debug)]
struct WordPoint {
    /// `x·2^64 mod p`
    xm: u64,
    /// `x`, in `[0, p)`
    x: u64,
    a: u64,
    b: u64,
}

/// [`is_distinguished_be`] restated on a word `x < 2^64`.
///
/// For `dp_bits < 8` the byte rule is the plain test of the low `dp_bits`
/// bits.  For `dp_bits >= 8` it has two quirks the word form keeps.  It
/// works in whole bytes: the low `k = dp_bits / 8` bytes must be zero and
/// the remaining `dp_bits mod 8` bits are not tested, so `dp_bits = 12`
/// asks for 8 zero bits, not 12.  And an `x` whose serialisation has at
/// most `k` bytes, which is `x < 2^{8k}` (zero included, as `[0]`), is
/// distinguished by length alone; for `k >= 8` that is every word.
#[derive(Clone, Copy, Debug)]
struct WordDp {
    /// `x` below this is distinguished by length (0: no length clause)
    short: u64,
    /// the low bits that must be zero otherwise
    mask: u64,
}

impl WordDp {
    fn new(dp_bits: u8) -> Self {
        match dp_bits {
            0..=7 => Self {
                short: 0,
                mask: (1u64 << dp_bits) - 1,
            },
            8..=63 => {
                let short = 1u64 << (8 * (dp_bits / 8));
                Self {
                    short,
                    mask: short - 1,
                }
            }
            _ => Self { short: 0, mask: 0 },
        }
    }

    #[inline(always)]
    fn test(self, x: u64) -> bool {
        x < self.short || x & self.mask == 0
    }
}

/// [`rho_floyd_big`] on words: the same restarts, draws and steps.
fn rho_floyd_word(
    w: &WordZp,
    g: &BigUint,
    h: &BigUint,
    p: &BigUint,
    n: &BigUint,
    opts: &RhoOptions,
) -> Result<RhoSolution, &'static str> {
    let mut rng = StdRng::seed_from_u64(opts.seed.unwrap_or(FLOYD_DEFAULT_SEED));
    let (g_r, h_r) = (w.mont(g), w.mont(h));
    let mut total_iters: u64 = 0;

    for _restart in 0..=opts.max_restarts {
        let (a0, b0) = if total_iters == 0 {
            (1, 0)
        } else {
            let a0 = w.exponent(&rng.gen_biguint_below(n));
            (a0, w.exponent(&rng.gen_biguint_below(n)))
        };
        let mut t = w.start(w.pow(g_r, a0), w.pow(h_r, b0), a0, b0);
        let mut hare = t;

        let mut iters: u64 = 0;
        let mut sterile = false;
        while iters < opts.max_iterations {
            t = w.step(t, g_r, h_r);
            hare = w.step(w.step(hare, g_r, h_r), g_r, h_r);
            iters += 1;
            total_iters += 1;

            if t.x == hare.x {
                let is_log = |x: &BigUint| &crate::utils::mod_pow(g, x, p) == h;
                let [t_a, t_b, h_a, h_b] = [t.a, t.b, hare.a, hare.b].map(BigUint::from);
                match floyd_collision(&t_a, &t_b, &h_a, &h_b, n, is_log)? {
                    Some(x) => {
                        return Ok(RhoSolution {
                            x,
                            iterations: total_iters,
                        })
                    }
                    None => {
                        sterile = true;
                        break;
                    }
                }
            }
        }
        if !sterile {
            return Err(ERR_NO_COLLISION);
        }
    }
    Err(ERR_ALL_STERILE)
}

/// [`dp_walks_big`] on words: the same target picks, draws, steps and
/// table decisions.
fn dp_walks_word(
    w: &WordZp,
    g: &BigUint,
    targets: &[BigUint],
    p: &BigUint,
    n: &BigUint,
    opts: &DpRhoOptions,
    rng: &mut StdRng,
) -> Result<Vec<Option<BigUint>>, &'static str> {
    let m = targets.len();
    let dp = WordDp::new(opts.dp_bits);
    // Power tables for the walker starts ([`WordZp::pow_by_table`]); a
    // target's is built when a walker first serves it, so a budget that
    // never reaches a target costs nothing for it.
    let g_pows = w.pow_table(w.mont(g));
    let mut h_pows: Vec<Option<[u64; 64]>> = vec![None; m];

    let mut tables: Vec<HashMap<u64, (u64, u64)>> = vec![HashMap::new(); m];
    let mut solutions: Vec<Option<BigUint>> = vec![None; m];

    for _walker in 0..opts.max_walkers {
        let Some(target_idx) = pick_target(rng, &solutions) else {
            break;
        };
        let h_pows =
            h_pows[target_idx].get_or_insert_with(|| w.pow_table(w.mont(&targets[target_idx])));
        let (g_r, h_r) = (g_pows[0], h_pows[0]);

        let a = w.exponent(&rng.gen_biguint_below(n));
        let b = w.exponent(&rng.gen_biguint_below(n));
        let (g_a, h_b) = (w.pow_by_table(&g_pows, a), w.pow_by_table(h_pows, b));
        let mut s = w.start(g_a, h_b, a, b);

        for _step in 0..opts.max_steps_per_walker {
            s = w.step(s, g_r, h_r);
            if dp.test(s.x) {
                if let Some(&(a_prev, b_prev)) = tables[target_idx].get(&s.x) {
                    let [a, b, a_prev, b_prev] = [s.a, s.b, a_prev, b_prev].map(BigUint::from);
                    let h = &targets[target_idx];
                    if let Some(log) = dp_collision(&a, &b, &a_prev, &b_prev, g, h, p, n)? {
                        solutions[target_idx] = Some(log);
                    }
                } else {
                    tables[target_idx].insert(s.x, (s.a, s.b));
                }
                break;
            }
        }
        if solutions.iter().all(|s| s.is_some()) {
            break;
        }
    }
    Ok(solutions)
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

    /// A target outside <g> has no logarithm.  A collision still yields a
    /// congruence with a solution; it must be refused, not returned.
    /// (`g = 4` has order 65633 mod 131267; `2` is a non-residue, outside.)
    #[test]
    fn rho_refuses_a_target_outside_the_subgroup() {
        let p = BigUint::from(131267u32);
        let q = BigUint::from(65633u32);
        let g = BigUint::from(4u32);
        let h = BigUint::from(2u32);
        let opts = RhoOptions {
            max_iterations: 1_000_000,
            ..RhoOptions::default()
        };
        assert!(pollard_rho_dlp_zp(&g, &h, &p, &q, &opts).is_err());
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

    // ── Single-word walks against the BigUint reference ──

    use rand::Rng;

    /// `(p, q)` with `p` and `q` prime and `q | p − 1`, from tiny moduli
    /// to the top of the single-word range, so that walks in the order-`q`
    /// subgroup collide within a few thousand steps.
    const SUBGROUPS: [(u64, u64); 6] = [
        (23, 11),
        (47, 23),
        (1019, 509),
        (131_267, 65_633),
        (18_446_744_073_709_551_437, 6_199),  // 2^64 − 179
        (18_446_744_073_709_551_293, 46_273), // 2^64 − 323
    ];

    /// An element of order `q` in `Z_p^*`, for `p`, `q` as in [`SUBGROUPS`].
    fn order_q_element(p: &BigUint, q: &BigUint) -> BigUint {
        let e = (p - 1u32) / q;
        (2u32..)
            .map(|t| BigUint::from(t).modpow(&e, p))
            .find(|g| !g.is_one())
            .expect("Z_p^* has an element of order q")
    }

    /// A random word of random bit length (so small values are common).
    fn any_word(rng: &mut StdRng) -> u64 {
        rng.gen::<u64>() >> rng.gen_range(0..64)
    }

    /// A random odd modulus `3 <= p < 2^64` of random bit length.
    fn odd_modulus(rng: &mut StdRng) -> u64 {
        let bits = rng.gen_range(2..=64);
        (rng.gen::<u64>() >> (64 - bits)) | 1 | (1 << (bits - 1))
    }

    /// `(g, h, p, n)` for a differential run.  Most are planted DLPs in an
    /// order-`q` subgroup, so that runs succeed and report iteration counts;
    /// they include inputs the solvers do not assume: `g` and `h`
    /// unreduced (often past 2^64), `h` outside `<g>`, and a composite
    /// `n = c·q` (which drives the gcd branch of the Floyd collision).  The
    /// rest are arbitrary odd moduli, possibly composite, with an `n`
    /// unrelated to anything: the walks must still agree step for step.
    fn instance(rng: &mut StdRng) -> (BigUint, Vec<BigUint>, BigUint, BigUint) {
        let targets = rng.gen_range(1..=3);
        if rng.gen_bool(0.7) {
            let (p, q) = SUBGROUPS[rng.gen_range(0..SUBGROUPS.len())];
            let x_max = q;
            let (p, q) = (BigUint::from(p), BigUint::from(q));
            let mut g = order_q_element(&p, &q);
            let hs = (0..targets)
                .map(|_| {
                    let mut h = g.modpow(&BigUint::from(rng.gen_range(0..x_max)), &p);
                    if rng.gen_bool(0.05) {
                        h = BigUint::from(rng.gen::<u64>());
                    }
                    if rng.gen_bool(0.1) {
                        h += &p * rng.gen::<u64>();
                    }
                    h
                })
                .collect();
            if rng.gen_bool(0.1) {
                g += &p * rng.gen::<u64>();
            }
            let n = if rng.gen_bool(0.25) {
                &q * rng.gen_range(2u32..=6)
            } else {
                q
            };
            (g, hs, p, n)
        } else {
            let p = odd_modulus(rng);
            let n = any_word(rng).max(2);
            let g = if rng.gen_bool(0.5) {
                BigUint::from(rng.gen::<u128>())
            } else {
                BigUint::from(rng.gen_range(0..p))
            };
            let hs = (0..targets)
                .map(|_| BigUint::from(rng.gen_range(0..p)))
                .collect();
            (g, hs, BigUint::from(p), BigUint::from(n))
        }
    }

    /// Which moduli take the single-word walks.
    #[test]
    fn rho_word_walks_cover_odd_single_word_moduli() {
        let big = |x: u128| BigUint::from(x);
        let two64 = 1u128 << 64;
        for (p, n, word) in [
            (3, 2, true),
            (23, 11, true),
            (two64 - 59, two64 - 1, true),
            (two64 - 1, 5, true),
            (two64 - 2, 5, false), // even
            (2, 2, false),
            (1, 2, false),
            (two64 + 37, 5, false), // p of two words
            (23, two64, false),     // n of two words
            (23, 1, false),         // rejected by the BigUint walk
        ] {
            assert_eq!(WordZp::new(&big(p), &big(n)).is_some(), word, "p {p} n {n}");
        }
    }

    /// The word DP test is the byte rule, for every `dp_bits` and for
    /// words of every length, including the boundaries of the length
    /// clause and of the whole-byte rounding.
    #[test]
    fn rho_word_dp_test_matches_byte_rule() {
        let mut rng = StdRng::seed_from_u64(0xd15_7000);
        let mut xs: Vec<u64> = (0..=600).collect();
        for k in 0..64 {
            xs.extend([1u64 << k, (1u64 << k) - 1, (1u64 << k) + 1]);
        }
        for k in 1..8 {
            for _ in 0..40 {
                xs.push(any_word(&mut rng) << (8 * k));
            }
        }
        xs.extend([u64::MAX, u64::MAX - 1]);
        xs.extend((0..2000).map(|_| any_word(&mut rng)));

        for dp_bits in 0..=u8::MAX {
            let (dp_mask, dp_bytes_zero) = dp_rule(dp_bits);
            let word = WordDp::new(dp_bits);
            for &x in &xs {
                assert_eq!(
                    word.test(x),
                    is_distinguished_be(&BigUint::from(x), dp_mask, dp_bytes_zero),
                    "dp_bits {dp_bits}, x {x:#x}"
                );
            }
        }
    }

    /// One word step, the Montgomery powers (by squaring and by table) and
    /// the start agree with `BigUint` arithmetic on random states, in all
    /// three buckets (the step is branch-free, so each bucket is a
    /// different selection of the same products), across odd moduli from 3
    /// to just below 2^64 (prime and composite) and exponent moduli up to
    /// 2^64 − 1.
    #[test]
    fn rho_word_step_matches_biguint_step() {
        let mut rng = StdRng::seed_from_u64(0x57e9);
        let mut moduli = vec![
            3,
            5,
            7,
            23,
            (1 << 63) - 25,
            (1 << 63) + 1,
            u64::MAX,
            u64::MAX - 58,
        ];
        moduli.extend(SUBGROUPS.iter().map(|&(p, _)| p));
        moduli.extend((0..200).map(|_| odd_modulus(&mut rng)));

        for p in moduli {
            let n = match rng.gen_range(0..4) {
                0 => u64::MAX,
                1 => 2,
                _ => any_word(&mut rng).max(2),
            };
            let (pb, nb) = (BigUint::from(p), BigUint::from(n));
            let w = WordZp::new(&pb, &nb).unwrap();
            for _ in 0..200 {
                let g = BigUint::from(rng.gen::<u128>() >> rng.gen_range(0..128));
                let h = BigUint::from(rng.gen_range(0..p));
                let (g_r, h_r) = (w.mont(&g), w.mont(&h));
                let x = match rng.gen_range(0..8) {
                    0 => 0,
                    1 => p - 1,
                    _ => rng.gen_range(0..p),
                };
                let (a, b) = (rng.gen_range(0..n), rng.gen_range(0..n));

                // The reference: the BigUint step of `rho_floyd_big` and
                // `dp_walks_big`, written out.
                let (xb, ab, bb) = (BigUint::from(x), BigUint::from(a), BigUint::from(b));
                let expect = match *xb.to_bytes_be().last().unwrap() % 3 {
                    0 => ((&xb * &g) % &pb, (&ab + 1u32) % &nb, bb),
                    1 => ((&xb * &h) % &pb, ab, (&bb + 1u32) % &nb),
                    _ => ((&xb * &xb) % &pb, (&ab * 2u32) % &nb, (&bb * 2u32) % &nb),
                };
                let s1 = w.step(w.point(x, a, b), g_r, h_r);
                assert_eq!(
                    (
                        BigUint::from(s1.x),
                        BigUint::from(s1.a),
                        BigUint::from(s1.b)
                    ),
                    expect,
                    "p {p} n {n} x {x} a {a} b {b} g {g} h {h}"
                );
                // The Montgomery form carried along is that of the new `x`.
                assert_eq!(s1.xm, w.point(s1.x, 0, 0).xm, "p {p} x {x}");

                let e = any_word(&mut rng);
                let (ea, eb) = (rng.gen_range(0..n), rng.gen_range(0..n));
                let start = (crate::utils::mod_pow(&g, &BigUint::from(ea), &pb)
                    * crate::utils::mod_pow(&h, &BigUint::from(eb), &pb))
                    % &pb;
                assert_eq!(
                    w.redc(w.pow(g_r, e) as u128),
                    g.modpow(&BigUint::from(e), &pb).to_u64().unwrap(),
                    "p {p} g {g} e {e}"
                );
                assert_eq!(w.pow_by_table(&w.pow_table(g_r), e), w.pow(g_r, e));
                let s0 = w.start(w.pow(g_r, ea), w.pow(h_r, eb), ea, eb);
                assert_eq!(BigUint::from(s0.x), start);
                assert_eq!((s0.xm, s0.a, s0.b), (w.point(s0.x, 0, 0).xm, ea, eb));
            }
        }
    }

    /// Floyd: the word walk returns exactly what the `BigUint` walk
    /// returns (logarithm, iteration count, or the same error), over
    /// random instances, seeds, iteration caps and restart budgets.  The
    /// iteration count covers every restart, so equal counts pin the
    /// restart draws as well as the steps.
    #[test]
    fn rho_floyd_word_walk_matches_biguint_walk() {
        /// Runs both walks on one instance; returns whether it solved, and
        /// whether it solved only after a restart.
        fn run(g: &BigUint, h: &BigUint, p: &BigUint, n: &BigUint, opts: &RhoOptions) -> [bool; 2] {
            let w = WordZp::new(p, n).expect("a single-word instance");
            let big = rho_floyd_big(g, h, p, n, opts);
            let word = rho_floyd_word(&w, g, h, p, n, opts);
            assert_eq!(word, big, "p {p} n {n} g {g} h {h} {opts:?}");
            assert_eq!(pollard_rho_dlp_zp(g, h, p, n, opts), big);
            if big.is_err() {
                return [false, false];
            }
            // A run that would have ended sterile without restarts solved
            // after drawing a random restart.
            let first_only = RhoOptions {
                max_restarts: 0,
                ..opts.clone()
            };
            [
                true,
                rho_floyd_word(&w, g, h, p, n, &first_only) == Err(ERR_ALL_STERILE),
            ]
        }

        let mut rng = StdRng::seed_from_u64(0xf107d);
        let (mut solved, mut restarted) = (0, 0);
        let mut tally = |[s, r]: [bool; 2]| {
            solved += s as usize;
            restarted += r as usize;
        };
        for _ in 0..300 {
            let (g, hs, p, n) = instance(&mut rng);
            for h in &hs {
                let opts = RhoOptions {
                    max_iterations: [1, 3, 50, 400, 4000][rng.gen_range(0..5)],
                    max_restarts: rng.gen_range(0..=5),
                    seed: rng.gen_bool(0.8).then(|| rng.gen()),
                };
                tally(run(&g, h, &p, &n, &opts));
            }
        }
        // With a composite exponent modulus `n = c·q` a first collision is
        // often sterile (the gcd branch finds no candidate), so with a
        // restart budget these runs go through the restart draws.
        for _ in 0..300 {
            let (p, q) = SUBGROUPS[rng.gen_range(0..4)];
            let x = BigUint::from(rng.gen_range(0..q));
            let (p, q) = (BigUint::from(p), BigUint::from(q));
            let g = order_q_element(&p, &q);
            let opts = RhoOptions {
                max_iterations: 4000,
                max_restarts: 16,
                seed: Some(rng.gen()),
            };
            let n = &q * rng.gen_range(2u32..=6);
            tally(run(&g, &g.modpow(&x, &p), &p, &n, &opts));
        }
        assert!(
            solved >= 200,
            "only {solved} runs solved: the test has lost its teeth"
        );
        assert!(
            restarted >= 20,
            "only {restarted} solves went through a restart"
        );
    }

    /// Distinguished points: the word walkers return the same solutions as
    /// the `BigUint` walkers and leave the RNG in the same state, over
    /// random instances, `dp_bits` from 0 to 255 and tight walker budgets
    /// (so which targets finish within budget depends on every draw and
    /// step).
    #[test]
    fn rho_dp_word_walks_match_biguint_walks() {
        let mut rng = StdRng::seed_from_u64(0xd9_3a1c);
        let (mut solved, mut unsolved) = (0, 0);
        for _ in 0..250 {
            let (g, hs, p, n) = instance(&mut rng);
            let w = WordZp::new(&p, &n).expect("a single-word instance");
            let opts = DpRhoOptions {
                dp_bits: [0, 1, 2, 3, 4, 5, 7, 8, 9, 12, 15, 16, 17, 24, 56, 64, 255]
                    [rng.gen_range(0..17)],
                max_walkers: rng.gen_range(1..=300),
                max_steps_per_walker: rng.gen_range(1..=400),
                seed: None,
            };
            let mut rng_big = StdRng::seed_from_u64(rng.gen());
            let mut rng_word = rng_big.clone();
            let big = dp_walks_big(&g, &hs, &p, &n, &opts, &mut rng_big);
            let word = dp_walks_word(&w, &g, &hs, &p, &n, &opts, &mut rng_word);
            assert_eq!(word, big, "p {p} n {n} g {g} targets {hs:?} {opts:?}");
            assert!(
                rng_word == rng_big,
                "RNG streams diverged: p {p} n {n} {opts:?}"
            );
            for sol in big.unwrap() {
                match sol {
                    Some(_) => solved += 1,
                    None => unsolved += 1,
                }
            }
        }
        assert!(
            solved >= 100 && unsolved >= 100,
            "{solved} solved, {unsolved} not"
        );
    }

    /// The `BigUint` walks remain the path above 2^64 and still solve:
    /// `p = 2^64 + 37`, subgroup order `q = 25873`.
    #[test]
    fn rho_biguint_walks_solve_above_two_to_the_64() {
        let p = (BigUint::one() << 64) + 37u32;
        let q = BigUint::from(25_873u32);
        assert!(WordZp::new(&p, &q).is_none());
        let g = order_q_element(&p, &q);
        let h = g.modpow(&BigUint::from(12_345u32), &p);

        let opts = RhoOptions {
            max_iterations: 1 << 16,
            seed: Some(264),
            ..RhoOptions::default()
        };
        let sol = pollard_rho_dlp_zp(&g, &h, &p, &q, &opts).unwrap();
        assert_eq!(sol.x, BigUint::from(12_345u32));

        let targets = [h, g.modpow(&BigUint::from(777u32), &p)];
        let opts = DpRhoOptions {
            dp_bits: 3,
            seed: Some(264),
            ..DpRhoOptions::default()
        };
        let sols = pollard_rho_dp_dlp_zp_multi(&g, &targets, &p, &q, &opts).unwrap();
        assert_eq!(sols[0].x, BigUint::from(12_345u32));
        assert_eq!(sols[1].x, BigUint::from(777u32));
    }

    /// A target outside `<g>` has no logarithm, but a collision still gives
    /// a congruence with a solution: the word walk refuses it as the
    /// `BigUint` walk and the code before the word walks do (the check is
    /// in [`floyd_collision`], which both walks share).  For `p` up to
    /// 131267 a collision comes within a few thousand steps, so there the
    /// refusal is the only outcome; the larger moduli run out of
    /// iterations first, and the three must agree on that too.
    #[test]
    fn rho_both_walks_refuse_a_target_outside_the_subgroup() {
        let mut rng = StdRng::seed_from_u64(0x7f5c9);
        for (p, q) in SUBGROUPS {
            let (p, q) = (BigUint::from(p), BigUint::from(q));
            let g = order_q_element(&p, &q);
            let h = (2u32..)
                .map(BigUint::from)
                .find(|t| !t.modpow(&q, &p).is_one())
                .expect("Z_p^* has an element outside <g>");
            let w = WordZp::new(&p, &q).expect("a single-word instance");
            for _ in 0..4 {
                let opts = RhoOptions {
                    max_iterations: 20_000,
                    max_restarts: 4,
                    seed: Some(rng.gen()),
                };
                let got = rho_floyd_word(&w, &g, &h, &p, &q, &opts);
                assert_eq!(got, rho_floyd_big(&g, &h, &p, &q, &opts), "p {p}");
                assert_eq!(
                    got,
                    original::pollard_rho_dlp_zp(&g, &h, &p, &q, &opts),
                    "p {p}"
                );
                if p < BigUint::from(131_268u32) {
                    assert_eq!(got, Err(ERR_NOT_A_LOG), "p {p}");
                }
            }
        }
    }

    /// Both public walks return exactly what the code before the
    /// single-word walks returned (logarithm, iteration count or error), on
    /// the word path and on the `BigUint` path (`p` above 2^64, and even
    /// `p` below it).  The tests above hold the word walks to the `BigUint`
    /// walks; this holds the `BigUint` walks, whose collision handling and
    /// target pick the word walks now share, to the original.
    #[test]
    fn rho_public_walks_match_the_original_code() {
        let mut rng = StdRng::seed_from_u64(0x1dc0de);
        let p64 = (BigUint::one() << 64) + 37u32;
        let q64 = BigUint::from(25_873u32);
        let g64 = order_q_element(&p64, &q64);
        let mut on_word_path = [0usize; 2];
        for i in 0..240 {
            let (g, hs, p, n) = match i % 4 {
                0 => {
                    let hs = (0..rng.gen_range(1..=3))
                        .map(|_| g64.modpow(&BigUint::from(rng.gen_range(0..25_873u32)), &p64))
                        .collect();
                    (g64.clone(), hs, p64.clone(), q64.clone())
                }
                1 => {
                    let p = odd_modulus(&mut rng) & !1;
                    let hs = (0..rng.gen_range(1..=3))
                        .map(|_| BigUint::from(rng.gen_range(0..p)))
                        .collect();
                    let (g, n) = (rng.gen_range(0..p), any_word(&mut rng).max(2));
                    (BigUint::from(g), hs, BigUint::from(p), BigUint::from(n))
                }
                _ => instance(&mut rng),
            };
            on_word_path[WordZp::new(&p, &n).is_some() as usize] += 1;

            for h in &hs {
                let opts = RhoOptions {
                    max_iterations: [1, 3, 50, 400, 4000][rng.gen_range(0..5)],
                    max_restarts: rng.gen_range(0..=5),
                    seed: rng.gen_bool(0.8).then(|| rng.gen()),
                };
                assert_eq!(
                    pollard_rho_dlp_zp(&g, h, &p, &n, &opts),
                    original::pollard_rho_dlp_zp(&g, h, &p, &n, &opts),
                    "p {p} n {n} g {g} h {h} {opts:?}"
                );
            }
            let opts = DpRhoOptions {
                dp_bits: [0, 1, 3, 4, 7, 8, 9, 16, 64][rng.gen_range(0..9)],
                max_walkers: rng.gen_range(1..=150),
                max_steps_per_walker: rng.gen_range(1..=300),
                seed: rng.gen_bool(0.8).then(|| rng.gen()),
            };
            assert_eq!(
                pollard_rho_dp_dlp_zp_multi(&g, &hs, &p, &n, &opts),
                original::pollard_rho_dp_dlp_zp_multi(&g, &hs, &p, &n, &opts),
                "p {p} n {n} g {g} targets {hs:?} {opts:?}"
            );
        }
        assert!(on_word_path[0] >= 100 && on_word_path[1] >= 100);

        // The degenerate inputs are refused with the same errors.
        let (g, h, p) = (
            BigUint::from(4u32),
            BigUint::from(12u32),
            BigUint::from(23u32),
        );
        for n in [0u32, 1] {
            let n = BigUint::from(n);
            let opts = RhoOptions::default();
            assert_eq!(
                pollard_rho_dlp_zp(&g, &h, &p, &n, &opts),
                original::pollard_rho_dlp_zp(&g, &h, &p, &n, &opts)
            );
            let opts = DpRhoOptions::default();
            let hs = [h.clone()];
            assert_eq!(
                pollard_rho_dp_dlp_zp_multi(&g, &hs, &p, &n, &opts),
                original::pollard_rho_dp_dlp_zp_multi(&g, &hs, &p, &n, &opts)
            );
        }
        let (n, opts) = (BigUint::from(11u32), DpRhoOptions::default());
        assert_eq!(
            pollard_rho_dp_dlp_zp_multi(&g, &[], &p, &n, &opts),
            original::pollard_rho_dp_dlp_zp_multi(&g, &[], &p, &n, &opts)
        );
    }

    /// The word exponent arithmetic at the edges of `n`: `a = n − 1`, where
    /// `inc` wraps, and `a` around `n / 2`, where `dbl` switches between
    /// `2a` and `2a − n`, for `n` up to `2^64 − 1`, where `a + a` itself
    /// would overflow.  The random states of `rho_word_step_matches_biguint_step`
    /// reach these values only by chance.
    #[test]
    fn rho_word_exponent_arithmetic_at_the_edges_of_n() {
        let mut rng = StdRng::seed_from_u64(0xed6e0f17);
        let mut orders = vec![
            2,
            3,
            4,
            255,
            256,
            257,
            1 << 32,
            (1 << 63) - 1,
            1 << 63,
            (1 << 63) + 1,
            u64::MAX - 1,
            u64::MAX,
        ];
        orders.extend((0..100).map(|_| any_word(&mut rng).max(2)));
        for n in orders {
            let w = WordZp::new(&BigUint::from(23u32), &BigUint::from(n)).unwrap();
            let half = n / 2;
            let mut exps = vec![0, 1, n - 1, n - 2, half, half.saturating_sub(1), half + 1];
            exps.extend((0..50).map(|_| rng.gen_range(0..n)));
            for a in exps.into_iter().filter(|&a| a < n) {
                let (a128, n128) = (a as u128, n as u128);
                assert_eq!(w.inc(a) as u128, (a128 + 1) % n128, "inc: n {n} a {a}");
                assert_eq!(w.dbl(a) as u128, (2 * a128) % n128, "dbl: n {n} a {a}");
            }
        }
    }

    /// Both public walks against the original code on inputs at the edges
    /// of the single-word path: moduli from 3 to `2^64 − 1` (prime and
    /// composite, with and without the top bit), exponent moduli at the
    /// top of the word, elements `0`, `p`, `p ± 1` and unreduced past
    /// `2^64`, zero budgets (`max_iterations`, `max_walkers`,
    /// `max_steps_per_walker`), up to six targets with repeats, and every
    /// `dp_bits` boundary of the byte rule.  With an `n` unrelated to the
    /// group, the first non-degenerate Floyd collision fails the
    /// `g^x = h` check and is refused with `ERR_NOT_A_LOG`, so equal
    /// outcomes there pin only whether and when a collision comes; the
    /// planted runs on the primes pin the logarithm and the iteration
    /// count.
    #[test]
    fn rho_public_walks_match_the_original_code_at_the_edges() {
        let mut rng = StdRng::seed_from_u64(0xed6e50fc0de);
        let moduli: [u64; 18] = [
            3,
            5,
            7,
            9,
            15,
            21,
            255,
            257,
            65_535,
            65_537,
            (1 << 32) - 1,
            (1 << 32) + 1,
            (1 << 63) - 25,
            (1 << 63) + 1,
            u64::MAX,
            u64::MAX - 58,
            18_446_744_073_709_551_437,
            131_267,
        ];
        let orders: [u64; 11] = [
            2,
            3,
            4,
            255,
            256,
            1 << 32,
            1 << 63,
            (1 << 63) + 1,
            u64::MAX - 1,
            u64::MAX,
            65_633,
        ];
        let dp_bits: [u8; 22] = [
            0, 1, 2, 3, 6, 7, 8, 9, 15, 16, 17, 23, 24, 31, 32, 48, 55, 56, 63, 64, 65, 255,
        ];
        let two64 = BigUint::one() << 64;
        let element = |rng: &mut StdRng, p: u64| -> BigUint {
            let pb = BigUint::from(p);
            match rng.gen_range(0..10) {
                0 => BigUint::zero(),
                1 => BigUint::one(),
                2 => BigUint::from(p - 1),
                3 => pb,
                4 => pb + 1u32,
                5 => &two64 + rng.gen::<u64>(),
                6 => BigUint::from(u128::MAX),
                _ => BigUint::from(rng.gen_range(0..p)),
            }
        };

        // The primes among `moduli`: for these `n = p − 1` is a multiple of
        // every element's order, so planted targets can be solved.
        let primes: [u64; 9] = [
            3,
            5,
            7,
            257,
            65_537,
            131_267,
            (1 << 63) - 25,
            u64::MAX - 58,
            18_446_744_073_709_551_437,
        ];

        let mut floyd = [0usize; 3];
        let mut dp = [0usize; 2];
        let mut dp_targets = [0usize; 2];
        for &p in &moduli {
            let pb = BigUint::from(p);
            for _ in 0..40 {
                let planted = primes.contains(&p) && rng.gen_bool(0.4);
                let n = if planted {
                    p - 1
                } else if rng.gen_bool(0.7) {
                    orders[rng.gen_range(0..orders.len())]
                } else {
                    any_word(&mut rng).max(2)
                };
                let nb = BigUint::from(n);
                let w = WordZp::new(&pb, &nb).expect("a single-word instance");
                let g = element(&mut rng, p);
                let pool: Vec<BigUint> = (0..3)
                    .map(|_| {
                        if planted {
                            g.modpow(&BigUint::from(rng.gen_range(0..n)), &pb)
                        } else {
                            element(&mut rng, p)
                        }
                    })
                    .collect();
                let hs: Vec<BigUint> = (0..rng.gen_range(1..=6))
                    .map(|_| pool[rng.gen_range(0..pool.len())].clone())
                    .collect();

                let opts = RhoOptions {
                    max_iterations: [0, 1, 2, 7, 100, 3000][rng.gen_range(0..6)],
                    max_restarts: [0, 1, 3, 16][rng.gen_range(0..4)],
                    seed: rng.gen_bool(0.8).then(|| rng.gen()),
                };
                let got = pollard_rho_dlp_zp(&g, &hs[0], &pb, &nb, &opts);
                let want = original::pollard_rho_dlp_zp(&g, &hs[0], &pb, &nb, &opts);
                assert_eq!(got, want, "p {p} n {n} g {g} h {} {opts:?}", hs[0]);
                floyd[match want {
                    Ok(_) => 0,
                    Err(ERR_NO_COLLISION) => 1,
                    Err(_) => 2,
                }] += 1;

                let opts = DpRhoOptions {
                    dp_bits: dp_bits[rng.gen_range(0..dp_bits.len())],
                    max_walkers: [0, 1, 2, 17, 200][rng.gen_range(0..5)],
                    max_steps_per_walker: [0, 1, 2, 40, 300][rng.gen_range(0..5)],
                    seed: rng.gen_bool(0.8).then(|| rng.gen()),
                };
                let got = pollard_rho_dp_dlp_zp_multi(&g, &hs, &pb, &nb, &opts);
                let want = original::pollard_rho_dp_dlp_zp_multi(&g, &hs, &pb, &nb, &opts);
                assert_eq!(got, want, "p {p} n {n} g {g} targets {hs:?} {opts:?}");
                dp[want.is_ok() as usize] += 1;

                // The public result says only which target failed first; the
                // walkers' per-target results and the RNG state they leave
                // pin every draw on these inputs as well.
                let mut rng_big = StdRng::seed_from_u64(rng.gen());
                let mut rng_word = rng_big.clone();
                let big = dp_walks_big(&g, &hs, &pb, &nb, &opts, &mut rng_big);
                let word = dp_walks_word(&w, &g, &hs, &pb, &nb, &opts, &mut rng_word);
                assert_eq!(word, big, "p {p} n {n} g {g} targets {hs:?} {opts:?}");
                assert!(rng_word == rng_big, "RNG streams diverged: p {p} n {n}");
                for sol in big.unwrap() {
                    dp_targets[sol.is_some() as usize] += 1;
                }
            }
        }
        // Every outcome is reached often enough to count as tested.  A DP
        // run succeeds only when all its targets verify, which the planted
        // runs on the small primes do; the per-target count is the larger
        // sample.
        assert!(floyd.iter().all(|&c| c >= 40), "Floyd outcomes {floyd:?}");
        assert!(dp[0] >= 40 && dp[1] >= 20, "DP outcomes {dp:?}");
        assert!(
            dp_targets.iter().all(|&c| c >= 100),
            "DP targets {dp_targets:?}"
        );
    }

    /// Multi-target DP runs to completion against the original: six planted
    /// targets, a repeat of one and an unreduced copy of another, so the
    /// target pick draws from every size of unsolved set as targets are
    /// solved, and the same with a target outside `<g>` added.  The
    /// unreduced copy never solves and keeps the pick going until the
    /// walker budget runs out.  Then eight planted targets, all solved.
    #[test]
    fn rho_dp_multi_target_runs_match_the_original_code_to_completion() {
        let (p, q) = (BigUint::from(131_267u32), BigUint::from(65_633u32));
        let g = order_q_element(&p, &q);
        let mut rng = StdRng::seed_from_u64(0x87a26e7);
        for round in 0..6 {
            let mut hs: Vec<BigUint> = (0..6)
                .map(|_| g.modpow(&BigUint::from(rng.gen_range(0..65_633u32)), &p))
                .collect();
            hs.push(hs[1].clone());
            hs.push(&hs[4] + &p);
            if round % 2 == 1 {
                // 2 has order 2q modulo this safe prime, so it is not in <g>.
                hs.insert(3, BigUint::from(2u32));
            }
            let opts = DpRhoOptions {
                dp_bits: [3, 4, 5][round % 3],
                max_walkers: 20_000,
                max_steps_per_walker: 400,
                seed: (round != 0).then(|| rng.gen()),
            };
            let got = pollard_rho_dp_dlp_zp_multi(&g, &hs, &p, &q, &opts);
            let want = original::pollard_rho_dp_dlp_zp_multi(&g, &hs, &p, &q, &opts);
            assert_eq!(got, want, "round {round} {opts:?}");
            // The unreduced target is never matched by `g^x mod p`, so
            // neither code solves it: both give the same error.
            assert!(want.is_err());
        }
        // Without the unreduced and foreign targets every target solves.
        let hs: Vec<BigUint> = (0..8)
            .map(|i| g.modpow(&BigUint::from(1_000u32 + 7_919 * i), &p))
            .collect();
        let opts = DpRhoOptions {
            dp_bits: 4,
            max_walkers: 20_000,
            max_steps_per_walker: 400,
            seed: Some(0x5eed),
        };
        let got = pollard_rho_dp_dlp_zp_multi(&g, &hs, &p, &q, &opts);
        let want = original::pollard_rho_dp_dlp_zp_multi(&g, &hs, &p, &q, &opts);
        assert_eq!(got, want);
        assert_eq!(want.map(|v| v.len()), Ok(8));
    }

    /// `pollard_rho_dlp_zp` (with the generic walk it wraps) and
    /// `pollard_rho_dp_dlp_zp_multi` as they were before the single-word
    /// walks, verbatim: the reference
    /// `rho_public_walks_match_the_original_code` holds both paths to.
    mod original {
        use super::super::{sub_mod, DpRhoOptions, RhoOptions, RhoSolution};
        use crate::utils::mod_inverse;
        use num_bigint::{BigUint, RandBigInt};
        use num_integer::Integer;
        use num_traits::{One, Zero};
        use rand::rngs::StdRng;
        use rand::SeedableRng;
        use std::collections::HashMap;

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
                        // A collision solves g^x = h only when h is in <g> and n is
                        // ord(g); otherwise the congruence has an answer that is
                        // simply wrong.  Never report one unchecked.
                        if !eq(&pow(g, &x), h) {
                            return Err(
                                "rho collision does not satisfy g^x = h: the target is not \
                                        in <g>, or n is not the order of g",
                            );
                        }
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
            let pow =
                |base: &BigUint, k: &BigUint| -> BigUint { crate::utils::mod_pow(base, k, p) };

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
                                let rhs_inv = mod_inverse(&rhs, n)
                                    .ok_or("modular inverse unexpectedly absent")?;
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
    }
}
