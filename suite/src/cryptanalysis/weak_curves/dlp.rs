//! Generic discrete-logarithm solvers: baby-step giant-step, Pollard rho
//! with an r-adding walk and distinguished points, and Pohlig–Hellman.
//!
//! Everything here is written against the [`DlpGroup`] trait, so the
//! same code solves the elliptic-curve DLP (Pohlig–Hellman attack), the
//! finite-field DLP that the MOV reduction produces in `F_{p^k}*`, and
//! the multiplicative DLP a nodal singular cubic maps to.
//!
//! # Pollard rho (Pollard 1978; Teske 2001; van Oorschot–Wiener 1999)
//!
//! To solve `h = g^d` in a group of prime order `ℓ`, pick `r = 32`
//! random multipliers `M_j = g^{a_j} h^{b_j}` and walk
//! `X ← X · M_{H(X) mod r}` while tracking `X = g^a h^b`.  Teske showed
//! an r-adding walk with `r ≥ 16` behaves like a random mapping, so two
//! walks collide after about `√(πℓ/2)` steps in total.  Collisions are
//! detected only at *distinguished points* (a hash with `w` low zero
//! bits), which lets many walks run side by side: here they are
//! advanced together through [`DlpGroup::op_many`], which the
//! elliptic-curve group implements with one shared field inversion
//! (Montgomery's trick).  A collision `g^{a₁}h^{b₁} = g^{a₂}h^{b₂}`
//! with `b₁ ≢ b₂` gives `d = (a₂ − a₁)/(b₁ − b₂) mod ℓ`.
//!
//! # Pohlig–Hellman (Pohlig–Hellman 1978)
//!
//! For `ord(g) = ∏ qᵢ^{eᵢ}`, the residue `d mod qᵢ^{eᵢ}` is found digit
//! by digit in the order-`qᵢ` subgroup, and the residues are combined
//! with the CRT.  The cost is `Σ eᵢ·√qᵢ` group operations, so the DLP is
//! only as hard as the largest prime factor of the order.  The exact
//! order of `g` is computed first from the supplied factorisation, so a
//! generator whose order is a proper divisor of the stated order is
//! handled correctly.
//!
//! References: J. M. Pollard, *Monte Carlo methods for index
//! computation (mod p)*, Math. Comp. 32 (1978); E. Teske, *On random
//! walks for Pollard's rho method*, Math. Comp. 70 (2001); P. C. van
//! Oorschot and M. J. Wiener, *Parallel collision search with
//! cryptanalytic applications*, J. Cryptology 12 (1999); S. Pohlig and
//! M. Hellman, *An improved algorithm for computing logarithms over
//! GF(p)*, IEEE Trans. IT 24 (1978); D. Shanks, *Class number, a theory
//! of factorization and genera* (1971) for BSGS.

use super::arith::{add_mod, is_probable_prime, mix64, sub_mod};
use super::WeakCurveError;
use num_bigint::{BigUint, RandBigInt};
use num_traits::{One, ToPrimitive, Zero};
use rand::rngs::StdRng;
use rand::Rng;
use serde::Serialize;
use std::collections::HashMap;
use std::hash::Hash;
use std::time::Instant;

/// A finite abelian group written multiplicatively, as the generic DLP
/// solvers need it.
pub trait DlpGroup {
    /// Group element.  Equality must be equality in the group, so the
    /// representation must be canonical (affine points, reduced
    /// polynomials).
    type Elem: Clone + Eq + Hash + std::fmt::Debug;

    /// The identity.
    fn identity(&self) -> Self::Elem;
    /// The group law.
    fn op(&self, a: &Self::Elem, b: &Self::Elem) -> Self::Elem;
    /// Inverse.
    fn invert(&self, a: &Self::Elem) -> Self::Elem;
    /// A well-mixed 64-bit hash of the canonical representation; drives
    /// the rho partition and the distinguished-point test.
    fn hash64(&self, a: &Self::Elem) -> u64;

    /// `a^k` by left-to-right square-and-multiply.
    fn pow(&self, a: &Self::Elem, k: &BigUint) -> Self::Elem {
        let mut acc = self.identity();
        for i in (0..k.bits()).rev() {
            acc = self.op(&acc, &acc);
            if k.bit(i) {
                acc = self.op(&acc, a);
            }
        }
        acc
    }

    /// `xs[i] ← xs[i] · ys[i]` for all `i`.  Groups whose law needs an
    /// inversion override this to share it across the batch.
    fn op_many(&self, xs: &mut [Self::Elem], ys: &[&Self::Elem]) {
        for (x, y) in xs.iter_mut().zip(ys) {
            *x = self.op(x, y);
        }
    }
}

/// Tuning for the prime-order solvers.
#[derive(Clone, Debug, Serialize)]
pub struct SolverOptions {
    /// Use BSGS for prime orders below `2^bsgs_max_bits` (memory is
    /// `2^{bsgs_max_bits/2}` elements); Pollard rho above.
    pub bsgs_max_bits: u32,
    /// Number of rho walks advanced together.
    pub rho_walks: usize,
    /// Number of multipliers in the r-adding walk (Teske: ≥ 16).
    pub rho_partitions: usize,
    /// Distinguished-point bits; `None` picks from the group size.
    pub dp_bits: Option<u32>,
    /// Give up after this many times the expected `√(πℓ/2)` steps.
    pub max_work_factor: f64,
    /// Seed for every random choice, so runs are reproducible.
    pub seed: u64,
}

impl Default for SolverOptions {
    fn default() -> Self {
        SolverOptions {
            bsgs_max_bits: 24,
            rho_walks: 64,
            rho_partitions: 32,
            dp_bits: None,
            max_work_factor: 40.0,
            seed: 0x00c0_ffee,
        }
    }
}

/// Which algorithm solved a prime-order subproblem.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub enum PrimeSolver {
    /// The subgroup element was the identity (digit 0).
    Trivial,
    /// Baby-step giant-step.
    Bsgs,
    /// Pollard rho with distinguished points.
    PollardRho,
}

/// One digit/prime-power step of a Pohlig–Hellman run.
#[derive(Clone, Debug, Serialize)]
pub struct PrimePowerStep {
    /// The prime `q`.
    #[serde(serialize_with = "super::ser::big")]
    pub prime: BigUint,
    /// Its exponent `e` in the order of the base.
    pub exponent: u32,
    /// `d mod q^e`.
    #[serde(serialize_with = "super::ser::big")]
    pub residue: BigUint,
    /// Solver used for the digits (the most expensive one used).
    pub solver: PrimeSolver,
    /// Group operations spent on the digit solves.
    pub group_ops: u64,
    /// Wall-clock milliseconds.
    pub elapsed_ms: f64,
}

/// Result of [`pohlig_hellman`].
#[derive(Clone, Debug, Serialize)]
pub struct PhSolution {
    /// `d mod ord(g)`, verified: `g^d = h`.
    #[serde(serialize_with = "super::ser::big")]
    pub d: BigUint,
    /// Exact order of `g`.
    #[serde(serialize_with = "super::ser::big")]
    pub order: BigUint,
    /// Factorisation of `ord(g)`.
    #[serde(serialize_with = "super::ser::big_pairs")]
    pub order_factors: Vec<(BigUint, u32)>,
    /// Per-prime-power steps.
    pub steps: Vec<PrimePowerStep>,
    /// Total group operations in digit solves.
    pub group_ops: u64,
}

fn log2_big(n: &BigUint) -> f64 {
    let bits = n.bits();
    if bits <= 52 {
        return n.to_f64().unwrap_or(0.0).max(1.0).log2();
    }
    let shift = bits - 52;
    (n >> shift).to_f64().unwrap_or(1.0).log2() + shift as f64
}

/// Baby-step giant-step for `h = g^d`, `d ∈ [0, bound)`.  Returns
/// `(d, group operations)`.
pub fn bsgs<G: DlpGroup>(
    grp: &G,
    g: &G::Elem,
    h: &G::Elem,
    bound: &BigUint,
) -> Option<(BigUint, u64)> {
    let m = bound.sqrt() + 1u32;
    let m_u = m.to_u64()?;
    let mut table: HashMap<G::Elem, u64> = HashMap::with_capacity(m_u as usize);
    let mut cur = grp.identity();
    let mut ops = 0u64;
    for j in 0..m_u {
        table.entry(cur.clone()).or_insert(j);
        cur = grp.op(&cur, g);
        ops += 1;
    }
    // cur = g^m; giant step multiplies by g^{-m}.
    let giant = grp.invert(&cur);
    let mut y = h.clone();
    for i in 0..=m_u {
        if let Some(&j) = table.get(&y) {
            let d = BigUint::from(i) * &m + j;
            if &d < bound {
                return Some((d, ops));
            }
        }
        y = grp.op(&y, &giant);
        ops += 1;
    }
    None
}

/// Pollard rho for `h = g^d` in a group where `g` has prime order `ell`.
/// Returns `(d, group operations)`, or `None` if the step budget
/// (`max_work_factor · √(πℓ/2)`) runs out.  The answer is verified.
pub fn pollard_rho<G: DlpGroup>(
    grp: &G,
    g: &G::Elem,
    h: &G::Elem,
    ell: &BigUint,
    opts: &SolverOptions,
    rng: &mut StdRng,
) -> Option<(BigUint, u64)> {
    let id = grp.identity();
    if *h == id {
        return Some((BigUint::zero(), 0));
    }
    if *g == id {
        return None;
    }
    let r = opts.rho_partitions.max(4);
    let walks = opts.rho_walks.max(1);
    let log_expected = 0.5 * (log2_big(ell) + (std::f64::consts::PI / 2.0).log2());
    let dp_bits = opts.dp_bits.unwrap_or_else(|| {
        let spare = log_expected - (walks as f64).log2() - 5.0;
        spare.clamp(0.0, 30.0) as u32
    });
    let dp_mask: u64 = (1u64 << dp_bits) - 1;
    let max_steps = (opts.max_work_factor * 2f64.powf(log_expected)).max(1e4) as u64 + walks as u64;
    let max_walk_len = (32u64 << dp_bits).max(1024);

    let mut ops = 0u64;
    let rand_elem = |rng: &mut StdRng, ops: &mut u64| {
        let a = rng.gen_biguint_below(ell);
        let b = rng.gen_biguint_below(ell);
        let x = grp.op(&grp.pow(g, &a), &grp.pow(h, &b));
        *ops += 2 * ell.bits();
        (x, a, b)
    };
    // Walk multipliers M_j = g^{ma_j} h^{mb_j}.
    let mut ma = Vec::with_capacity(r);
    let mut mb = Vec::with_capacity(r);
    let mut mults = Vec::with_capacity(r);
    for _ in 0..r {
        let (m, a, b) = rand_elem(rng, &mut ops);
        ma.push(a);
        mb.push(b);
        mults.push(m);
    }
    // Restart table: a walk that has just produced a distinguished point
    // restarts from X·T_i·T_j (two group operations) instead of a fresh
    // g^a h^b (two scalar multiplications).
    const RESTARTS: usize = 64;
    let mut restarts = Vec::with_capacity(RESTARTS);
    for _ in 0..RESTARTS {
        restarts.push(rand_elem(rng, &mut ops));
    }
    // Each walk's logarithm is (a0, b0) + Σ_j cnt[j]·(ma_j, mb_j); the
    // counters avoid two big-integer additions per step.
    struct Walk {
        a0: BigUint,
        b0: BigUint,
        cnt: Vec<u64>,
        len: u64,
    }
    let log_of = |w: &Walk| {
        let mut a = w.a0.clone();
        let mut b = w.b0.clone();
        for (j, &c) in w.cnt.iter().enumerate() {
            if c > 0 {
                a += &ma[j] * c;
                b += &mb[j] * c;
            }
        }
        (a % ell, b % ell)
    };
    let mut xs = Vec::with_capacity(walks);
    let mut ws = Vec::with_capacity(walks);
    let mut hs = Vec::with_capacity(walks);
    for _ in 0..walks {
        let (x, a, b) = rand_elem(rng, &mut ops);
        hs.push(grp.hash64(&x));
        xs.push(x);
        ws.push(Walk {
            a0: a,
            b0: b,
            cnt: vec![0; r],
            len: 0,
        });
    }
    let mut dps: HashMap<G::Elem, (BigUint, BigUint)> = HashMap::new();
    let mut steps = 0u64;
    let mut idx = vec![0usize; walks];
    let mut pending: Vec<(usize, usize, usize)> = Vec::new();
    while steps < max_steps {
        for i in 0..walks {
            idx[i] = (hs[i] % r as u64) as usize;
        }
        {
            let addends: Vec<&G::Elem> = idx.iter().map(|&j| &mults[j]).collect();
            grp.op_many(&mut xs, &addends);
        }
        steps += walks as u64;
        ops += walks as u64;
        // Restarts are drawn in walk order below but applied together after
        // the pass, two batched operations for all of them (one shared
        // inversion on a curve) instead of two single ones each.  Nothing
        // in the pass reads a restarted walk's point again, so deferring
        // them changes no walk, no draw and no count.
        pending.clear();
        for i in 0..walks {
            let w = &mut ws[i];
            w.cnt[idx[i]] += 1;
            w.len += 1;
            let hv = grp.hash64(&xs[i]);
            hs[i] = hv;
            let distinguished = (hv >> 20) & dp_mask == 0;
            if !distinguished && w.len <= max_walk_len {
                continue;
            }
            if distinguished {
                let (a1, b1) = log_of(w);
                if let Some((a2, b2)) = dps.get(&xs[i]) {
                    if *b2 != b1 {
                        // a1 + b1·d = a2 + b2·d  ⇒  d = (a2 − a1)/(b1 − b2)
                        let num = sub_mod(a2, &a1, ell);
                        let den = sub_mod(&b1, b2, ell);
                        if let Some(inv) = den.modinv(ell) {
                            let d = (num * inv) % ell;
                            if grp.pow(g, &d) == *h {
                                return Some((d, ops));
                            }
                        }
                    }
                } else {
                    dps.insert(xs[i].clone(), (a1, b1));
                }
            }
            // Restart (after a distinguished point, or a walk that is
            // probably trapped in a cycle) from X·T_u·T_v.
            let (a, b) = log_of(w);
            let (u, v) = (rng.gen_range(0..RESTARTS), rng.gen_range(0..RESTARTS));
            let (_, au, bu) = &restarts[u];
            let (_, av, bv) = &restarts[v];
            pending.push((i, u, v));
            ops += 2;
            w.a0 = add_mod(&add_mod(&a, au, ell), av, ell);
            w.b0 = add_mod(&add_mod(&b, bu, ell), bv, ell);
            w.cnt.iter_mut().for_each(|c| *c = 0);
            w.len = 0;
        }
        if !pending.is_empty() {
            let mut moved: Vec<G::Elem> = pending.iter().map(|&(i, _, _)| xs[i].clone()).collect();
            let first: Vec<&G::Elem> = pending.iter().map(|&(_, u, _)| &restarts[u].0).collect();
            grp.op_many(&mut moved, &first);
            let second: Vec<&G::Elem> = pending.iter().map(|&(_, _, v)| &restarts[v].0).collect();
            grp.op_many(&mut moved, &second);
            for (&(i, _, _), x) in pending.iter().zip(moved) {
                hs[i] = grp.hash64(&x);
                xs[i] = x;
            }
        }
    }
    None
}

/// Solve `h = g^d` where `g` has prime order `ell`, choosing BSGS or
/// Pollard rho by size.  The result is verified.
pub fn solve_prime_order<G: DlpGroup>(
    grp: &G,
    g: &G::Elem,
    h: &G::Elem,
    ell: &BigUint,
    opts: &SolverOptions,
    rng: &mut StdRng,
) -> Result<(BigUint, PrimeSolver, u64), WeakCurveError> {
    let id = grp.identity();
    if *h == id {
        return Ok((BigUint::zero(), PrimeSolver::Trivial, 0));
    }
    if *g == id {
        return Err(WeakCurveError::NotInSubgroup);
    }
    if ell.bits() as u32 <= opts.bsgs_max_bits {
        return match bsgs(grp, g, h, ell) {
            Some((d, ops)) => Ok((d, PrimeSolver::Bsgs, ops)),
            None => Err(WeakCurveError::NotInSubgroup),
        };
    }
    let mut total = 0u64;
    for _attempt in 0..3 {
        if let Some((d, ops)) = pollard_rho(grp, g, h, ell, opts, rng) {
            return Ok((d, PrimeSolver::PollardRho, total + ops));
        }
        total += (opts.max_work_factor * log2_big(ell).exp2().sqrt()) as u64;
    }
    Err(WeakCurveError::SolverFailed(format!(
        "Pollard rho found no collision for a {}-bit prime order within budget \
         (is the target in the subgroup?)",
        ell.bits()
    )))
}

/// Exact order of `g` given a factorisation of a multiple of it.
/// Returns the order and its factorisation.
pub fn element_order<G: DlpGroup>(
    grp: &G,
    g: &G::Elem,
    multiple_factors: &[(BigUint, u32)],
) -> (BigUint, Vec<(BigUint, u32)>) {
    let id = grp.identity();
    let mut n = multiple_factors
        .iter()
        .fold(BigUint::one(), |acc, (q, e)| acc * q.pow(*e));
    let mut out = Vec::new();
    for (q, e) in multiple_factors {
        let mut e_left = *e;
        while e_left > 0 {
            let cand = &n / q;
            if grp.pow(g, &cand) == id {
                n = cand;
                e_left -= 1;
            } else {
                break;
            }
        }
        if e_left > 0 {
            out.push((q.clone(), e_left));
        }
    }
    (n, out)
}

/// Chinese remaindering for pairwise-coprime moduli.
pub fn crt(residues: &[(BigUint, BigUint)]) -> Option<BigUint> {
    let mut m = BigUint::one();
    let mut x = BigUint::zero();
    for (mi, ri) in residues {
        let inv = (&m % mi).modinv(mi)?;
        let diff = sub_mod(&(ri % mi), &(&x % mi), mi);
        let t = (diff * inv) % mi;
        x += t * &m;
        m *= mi;
    }
    Some(x % m)
}

/// Pohlig–Hellman: solve `h = g^d` given the factorisation of a multiple
/// of `ord(g)`.  Every factor must be prime.  The answer is `d mod
/// ord(g)` and is verified (`g^d = h`); a target outside `⟨g⟩` yields
/// [`WeakCurveError::NotInSubgroup`].
pub fn pohlig_hellman<G: DlpGroup>(
    grp: &G,
    g: &G::Elem,
    h: &G::Elem,
    multiple_factors: &[(BigUint, u32)],
    opts: &SolverOptions,
    rng: &mut StdRng,
) -> Result<PhSolution, WeakCurveError> {
    for (q, _) in multiple_factors {
        if !is_probable_prime(q) {
            return Err(WeakCurveError::InvalidInput(format!(
                "factor {q} of the order is not prime"
            )));
        }
    }
    let (order, factors) = element_order(grp, g, multiple_factors);
    let mut steps = Vec::with_capacity(factors.len());
    let mut residues = Vec::with_capacity(factors.len());
    let mut total_ops = 0u64;
    for (q, e) in &factors {
        let t0 = Instant::now();
        let qe = q.pow(*e);
        let cof = &order / &qe;
        let gi = grp.pow(g, &cof);
        let hi = grp.pow(h, &cof);
        // γ = gi^{q^{e−1}} has order exactly q.
        let gamma = grp.pow(&gi, &q.pow(e - 1));
        let gi_inv = grp.invert(&gi);
        let mut x = BigUint::zero();
        let mut qj = BigUint::one();
        let mut ops = 0u64;
        let mut solver = PrimeSolver::Trivial;
        for j in 0..*e {
            // h_j = (gi^{−x} · hi)^{q^{e−1−j}}
            let t = grp.op(&grp.pow(&gi_inv, &x), &hi);
            let hj = grp.pow(&t, &q.pow(e - 1 - j));
            let (dj, used, o) = solve_prime_order(grp, &gamma, &hj, q, opts, rng)?;
            ops += o;
            if used == PrimeSolver::PollardRho
                || (used == PrimeSolver::Bsgs && solver == PrimeSolver::Trivial)
            {
                solver = used;
            }
            x += dj * &qj;
            qj *= q;
        }
        total_ops += ops;
        residues.push((qe, x.clone()));
        steps.push(PrimePowerStep {
            prime: q.clone(),
            exponent: *e,
            residue: x,
            solver,
            group_ops: ops,
            elapsed_ms: t0.elapsed().as_secs_f64() * 1e3,
        });
    }
    let d = crt(&residues).unwrap_or_default();
    if grp.pow(g, &d) != *h {
        return Err(WeakCurveError::NotInSubgroup);
    }
    Ok(PhSolution {
        d,
        order,
        order_factors: factors,
        steps,
        group_ops: total_ops,
    })
}

// ── Concrete groups ─────────────────────────────────────────────────────

use super::arith::{low_u64, AffinePoint, Ec};

impl DlpGroup for Ec {
    type Elem = AffinePoint;

    fn identity(&self) -> AffinePoint {
        AffinePoint::Infinity
    }
    fn op(&self, a: &AffinePoint, b: &AffinePoint) -> AffinePoint {
        self.add(a, b)
    }
    fn invert(&self, a: &AffinePoint) -> AffinePoint {
        self.neg(a)
    }
    fn hash64(&self, a: &AffinePoint) -> u64 {
        match a {
            AffinePoint::Infinity => 0x1d3a_5f0e_9c2b_4471,
            AffinePoint::Affine(x, y) => mix64(low_u64(x) ^ (low_u64(y) & 1).rotate_left(63)),
        }
    }
    fn pow(&self, a: &AffinePoint, k: &BigUint) -> AffinePoint {
        self.mul(a, k)
    }
    fn op_many(&self, xs: &mut [AffinePoint], ys: &[&AffinePoint]) {
        self.add_batch(xs, ys)
    }
}

#[cfg(test)]
mod tests {
    use super::super::arith::{seeded_rng, Ec};
    use super::*;

    fn big(s: &str) -> BigUint {
        BigUint::parse_bytes(s.as_bytes(), 10).unwrap()
    }

    /// `y² = x³ + 2` over the 128-bit prime below: the group has order
    /// 9·87721·1350388531·414225013639·669550864369 and the point `G`
    /// has order (that)/9 (the 3-part is `Z/3 × Z/3`).
    fn curve128() -> (Ec, AffinePoint, BigUint) {
        let p = big("295681886263824732693820920129885041569");
        let ec = Ec::new(&p, &BigUint::zero(), &BigUint::from(2u32));
        let g = AffinePoint::Affine(
            big("292999454487241629135152166766043019954"),
            big("24885659077271486073460513969014021704"),
        );
        assert!(ec.is_on_curve(&g));
        (ec, g, big("295681886263824732712120563203402323269"))
    }

    #[test]
    fn bsgs_and_rho_solve_prime_subgroups() {
        let (ec, g, n) = curve128();
        // BSGS in the subgroup of order 87721 (17 bits).
        let q1 = BigUint::from(87721u32);
        let g1 = ec.mul(&g, &(&n / &q1));
        let h1 = ec.mul(&g1, &BigUint::from(54321u32));
        let (d1, ops) = bsgs(&ec, &g1, &h1, &q1).unwrap();
        assert_eq!(d1, BigUint::from(54321u32));
        assert!(ops <= 2 * 297);
        // Pollard rho in the subgroup of order 1350388531 (31 bits).
        let q2 = big("1350388531");
        let g2 = ec.mul(&g, &(&n / &q2));
        let d = big("987654321");
        let h2 = ec.mul(&g2, &d);
        let mut rng = seeded_rng(7);
        let (d2, _) = pollard_rho(&ec, &g2, &h2, &q2, &SolverOptions::default(), &mut rng).unwrap();
        assert_eq!(d2, d);
    }

    #[test]
    fn pohlig_hellman_handles_non_generator_order() {
        let (ec, g, _n) = curve128();
        // Work in the 87721·3^2 part only: g' = g·(big primes).
        let g2 = ec.mul(&g, &big("374523123518915061149833073296021"));
        let d = BigUint::from(12345u32);
        let h = ec.mul(&g2, &d);
        let facs = vec![(BigUint::from(3u32), 2), (BigUint::from(87721u32), 1)];
        let mut rng = seeded_rng(1);
        let sol = pohlig_hellman(&ec, &g2, &h, &facs, &SolverOptions::default(), &mut rng).unwrap();
        assert_eq!(sol.order, BigUint::from(87721u32));
        assert_eq!(sol.d, d % 87721u32);
    }

    #[test]
    fn crt_small() {
        let r = crt(&[
            (BigUint::from(3u32), BigUint::from(2u32)),
            (BigUint::from(5u32), BigUint::from(3u32)),
            (BigUint::from(7u32), BigUint::from(2u32)),
        ]);
        assert_eq!(r, Some(BigUint::from(23u32)));
    }
}
