//! # Index calculus on hyperelliptic Jacobians over `F_p`.
//!
//! The Adleman–DeMarrais–Huang / Gaudry attack on the discrete
//! logarithm problem in `Jac(C)(F_p)` for `C : y² = f(x)` of genus
//! `g`, built on the Mumford / Cantor substrate in
//! [`crate::prime_hyperelliptic`].
//!
//! ## The algorithm
//!
//! Write `∞` for the point at infinity (`deg f = 2g+1`, so there is
//! exactly one).  Every degree-1 place `P = (x_0, y_0) ∈ C(F_p)`
//! gives a divisor class `[P] − [∞]`, whose Mumford representation is
//! `(x − x_0, y_0)`.  Those classes are the **factor base**
//! `F = {F_1, …, F_m}`; `m ≤ #C(F_p) ≈ p` after the `±` identification
//! `[(x, −y)] = −[(x, y)]`.
//!
//! 1. **Relation search.**  Produce candidates `R = a·D_1 + b·D_2` and
//!    reduce with Cantor — either by drawing `a, b` afresh
//!    (`RelationSearch::Random`, `2⌈log₂ N⌉` group operations each) or
//!    by stepping an `r`-adding walk (`RelationSearch::Walk`, one group
//!    operation each; the default).  The reduced representative is
//!    `(u, v)` with `deg u ≤ g`, and the class is
//!    `Σ_i m_i ([P_i] − [∞])` exactly when `u` splits into linear
//!    factors over `F_p`, `u = Π (x − x_i)^{m_i}`, with
//!    `P_i = (x_i, v(x_i))`.  That event is *smoothness*; its
//!    probability over a random class is `≈ 1/g!` for a factor base
//!    holding every degree-1 place, which is why the attack is
//!    interesting for fixed small `g` and large `p` and is *not* a
//!    threat to genus 1.
//! 2. **Linear algebra.**  Each smooth `R` yields
//!    `Σ_i c_i · log_{D_1} F_i − b · log_{D_1} D_2 ≡ a (mod N)`.
//!    Collect `m + extra` such rows and solve mod the prime order `N`
//!    of `D_1`.  Each row has at most `g + 1` non-zeros whatever `m`
//!    is, so the default solve is sparse (`LinearAlgebra::Sparse`);
//!    dense elimination ([`gaussian_eliminate_mod_n`]) is kept as the
//!    reference it has to beat.
//! 3. **Read off** `log_{D_1} D_2` and verify `D_2 = k·D_1` before
//!    returning it.  An unverified `k` is never returned.
//!
//! ## Cost, and what this module is for
//!
//! With the full degree-1 factor base and the walk, the relation stage
//! costs `≈ (m+1)·g!` group operations — `O(p)` at fixed `g` — against
//! `O(p^{g/2})` for Pollard rho on a group of size `≈ p^g`.  So the
//! asymptotic crossover is at `g = 4`, and Gaudry's variant — a
//! *reduced* factor base of size `p^{2/(g+1)}`, which this module
//! supports through `fb_size` — moves it to `g = 3`.
//!
//! The smoothness oracle runs on every candidate, so its per-call cost
//! sits directly on that stage; it is counted
//! ([`HecIndexCalculusReport::smoothness_field_ops`]) rather than
//! assumed away, since `AGENTS.md` puts an oracle's per-call work
//! inside the cost unit.  At `deg u ≤ 2` the default oracle decides
//! smoothness with one Legendre symbol instead of `O(p)` evaluations.
//!
//! What remains largest is the walk's own precomputation: the branch
//! divisors, roughly half the relation stage at `p = 251` even with
//! short step coefficients.
//!
//! The measured comparison against rho on the same instances, in the
//! unit `S = total group operations / sqrt(N)`, lives in
//! [`crate::cryptanalysis::hyperelliptic_ic_bench`] and
//! `research/notes/index-calculus/RESEARCH_HYPERELLIPTIC_IC_RHO.md`.  This module *measures*; it does
//! not claim.
//!
//! ## Scope
//!
//! - Odd characteristic, `deg f = 2g+1`, `f` squarefree — the
//!   "imaginary" model, one place at infinity.
//! - `p` small enough to enumerate: `p` must fit in a `u64`, and the
//!   factor-base build is `O(p)`.  The root finding no longer is —
//!   `SmoothnessTest::Gcd` is `O(log p)` per candidate at genus 2 —
//!   so the factor-base build is now the binding `O(p)` step.
//! - `N` = order of `D_1` must be **prime**: the solver inverts
//!   pivots mod `N`.  [`prime_order_of`] computes it for toy
//!   Jacobians and refuses a composite answer.

use std::collections::HashMap;

use num_bigint::BigUint;
use num_traits::{One, Zero};
use rand::rngs::StdRng;
use rand::{RngCore, SeedableRng};

use crate::cryptanalysis::ec_index_calculus::{gaussian_eliminate_mod_n, sqrt_mod_p};
use crate::prime_hyperelliptic::{FpPoly, HyperellipticCurveP, MumfordDivisorP};
use crate::utils::mod_inverse;

// ── Factor base ────────────────────────────────────────────────────────

/// One degree-1 place `P = (x, y)` of `C`, held as the divisor class
/// `[P] − [∞]`.
///
/// Only one of `±P` is stored: the representative has
/// `y ≤ (p−1)/2`, and a decomposition that meets `(x, p−y)` records
/// the coefficient `−1` against this entry instead.  Weierstrass
/// points (`y = 0`) are their own negative and always carry `+1`.
#[derive(Clone, Debug)]
pub struct HecFactorBaseEntry {
    pub x: BigUint,
    pub y: BigUint,
    pub divisor: MumfordDivisorP,
}

/// The factor base, plus the `x ↦ index` map the decomposition needs.
#[derive(Clone, Debug)]
pub struct HecFactorBase {
    pub entries: Vec<HecFactorBaseEntry>,
    by_x: HashMap<Vec<u32>, usize>,
}

impl HecFactorBase {
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// Index of the entry with this `x`-coordinate, if present.
    pub fn index_of_x(&self, x: &BigUint) -> Option<usize> {
        self.by_x.get(&x.to_u32_digits()).copied()
    }
}

/// Build the factor base: the places `(x, y)` with `y ≤ (p−1)/2`,
/// in increasing `x`, truncated to `max_size` entries.
///
/// Truncating is Gaudry's reduced factor base: relations whose
/// decomposition leaves the truncated set are simply discarded, so a
/// smaller base costs more trials per relation but a smaller solve.
/// `max_size = usize::MAX` keeps every place.
///
/// At most one of `±P` appears, because both would make the relation
/// matrix carry a column and its negative.
pub fn build_factor_base(curve: &HyperellipticCurveP, max_size: usize) -> HecFactorBase {
    let p = &curve.p;
    let p_u = p
        .to_u64_digits()
        .first()
        .copied()
        .filter(|_| p.to_u64_digits().len() <= 1)
        .expect("build_factor_base: p must fit in u64");
    let half = (p - BigUint::one()) >> 1;

    let mut entries = Vec::new();
    let mut by_x = HashMap::new();
    for xi in 0..p_u {
        if entries.len() >= max_size {
            break;
        }
        let x = BigUint::from(xi);
        let y_sq = curve.f.eval(&x);
        let y = match sqrt_mod_p(&y_sq, p) {
            Some(y) => y,
            None => continue,
        };
        // Canonical representative of the ± pair.
        let y = if y > half { p - &y } else { y };
        let divisor = mumford_of_place(curve, &x, &y);
        by_x.insert(x.to_u32_digits(), entries.len());
        entries.push(HecFactorBaseEntry { x, y, divisor });
    }
    HecFactorBase { entries, by_x }
}

/// `[P] − [∞]` in Mumford form: `(x − x_0, y_0)`.
///
/// Unlike [`MumfordDivisorP::from_point`] this also accepts the
/// Weierstrass points `y_0 = 0`, whose class `(x − x_0, 0)` is the
/// 2-torsion element the factor base needs a column for.
fn mumford_of_place(curve: &HyperellipticCurveP, x0: &BigUint, y0: &BigUint) -> MumfordDivisorP {
    debug_assert!(curve.is_on_curve(x0, y0));
    let p = &curve.p;
    let u = FpPoly::from_coeffs(vec![(p - x0) % p, BigUint::one()], p.clone());
    let v = FpPoly::constant(y0.clone(), p.clone());
    MumfordDivisorP { u, v }
}

// ── Smoothness test / decomposition ────────────────────────────────────

/// Split `u` into linear factors over `F_p` by evaluating at every
/// `x ∈ F_p`, returning `(root, multiplicity)` pairs.
///
/// `None` when `u` does **not** split completely — the multiplicities
/// found do not account for `deg u`, so some irreducible factor has
/// degree `≥ 2` and the divisor is not smooth over degree-1 places.
///
/// `O(p · deg u)`; the point of the module is the relation structure,
/// not a Cantor–Zassenhaus.
pub fn split_into_linear_factors(u: &FpPoly, p: &BigUint) -> Option<Vec<(BigUint, usize)>> {
    let mut ops = 0usize;
    split_into_linear_factors_counted(u, p, &mut ops)
}

/// As [`split_into_linear_factors`], adding to `ops` the `F_p`
/// multiplications it performs.
///
/// This is the smoothness oracle, and `AGENTS.md` puts "any work an
/// oracle does per call" inside the cost unit.  It is not a detail: at
/// `p = 251` the root finding costs more field multiplications per trial
/// than the walk step it follows, so a count that omitted it would
/// report a relation stage roughly half its true price — the exact shape
/// of a relabelling.
pub fn split_into_linear_factors_counted(
    u: &FpPoly,
    p: &BigUint,
    ops: &mut usize,
) -> Option<Vec<(BigUint, usize)>> {
    split_counted_with(u, p, ops, &SmoothnessTest::default())
}

/// How smoothness is decided.
///
/// The oracle runs on **every** candidate, so its per-call cost sits
/// directly on the relation stage.  Once the walk brought a candidate
/// down to one group operation, this became the dominant field cost —
/// at `p = 251` the scan spent ~600 multiplications per trial against
/// the walk's single Jacobian operation.
#[derive(Clone, Debug, PartialEq, Eq, Default)]
pub enum SmoothnessTest {
    /// Evaluate `u` at every `x ∈ F_p`.  `O(p)` multiplications per
    /// call, and the reference the fast test has to match answer-for-
    /// answer.
    Scan,
    /// `u` splits into linear factors iff its radical equals
    /// `gcd(u, x^p − x)`, and `x^p mod u` costs `O(log p)`
    /// multiplications of degree-`< g` polynomials by square-and-
    /// multiply.  Roots then come from the quadratic formula at
    /// `deg ≤ 2`; higher degrees fall back to the scan (see below).
    #[default]
    Gcd,
}

/// As [`split_into_linear_factors_counted`], choosing the oracle.
pub fn split_counted_with(
    u: &FpPoly,
    p: &BigUint,
    ops: &mut usize,
    test: &SmoothnessTest,
) -> Option<Vec<(BigUint, usize)>> {
    match test {
        SmoothnessTest::Scan => split_by_scan(u, p, ops),
        SmoothnessTest::Gcd => split_by_gcd(u, p, ops),
    }
}

/// Multiply two polynomials mod `m`, charging the coefficient
/// multiplications both the product and the reduction perform.
fn poly_mul_mod(a: &FpPoly, b: &FpPoly, m: &FpPoly, ops: &mut usize) -> FpPoly {
    let (la, lb) = (a.coeffs.len().max(1), b.coeffs.len().max(1));
    *ops += la * lb;
    let prod = a.mul(b);
    let (dp, dm) = (prod.degree().unwrap_or(0), m.degree().unwrap_or(1));
    if dp >= dm {
        *ops += (dp - dm + 1) * (dm + 1);
    }
    prod.rem(m)
}

/// `x^p mod u`, by square-and-multiply on the exponent.
fn x_pow_p_mod(u: &FpPoly, p: &BigUint, ops: &mut usize) -> FpPoly {
    let x = FpPoly::x(p.clone());
    let mut result = FpPoly::one(p.clone()).rem(u);
    let mut base = x.rem(u);
    for i in 0..p.bits() {
        if p.bit(i) {
            result = poly_mul_mod(&result, &base, u, ops);
        }
        if i + 1 < p.bits() {
            base = poly_mul_mod(&base, &base, u, ops);
        }
    }
    result
}

/// Derivative of `f` over `F_p`.
fn derivative(f: &FpPoly, p: &BigUint) -> FpPoly {
    let coeffs: Vec<BigUint> = f
        .coeffs
        .iter()
        .enumerate()
        .skip(1)
        .map(|(i, c)| (c * BigUint::from(i as u64)) % p)
        .collect();
    FpPoly::from_coeffs(coeffs, p.clone())
}

/// Roots of a **squarefree, completely split** monic `d`.
///
/// Degrees 1 and 2 close in form.  Above that it is Cantor–Zassenhaus
/// equal-degree splitting: for a random `b`, `gcd(d, (x+b)^((p−1)/2) −
/// 1)` is a non-trivial factor with probability about `1/2`, because
/// the shifted roots split into residues and non-residues.  Genus 3
/// reaches this branch — `deg u ≤ g` — and without it the oracle would
/// fall back to the `O(p)` scan exactly where the interesting
/// measurement is.
fn roots_of_split_poly(d: &FpPoly, p: &BigUint, ops: &mut usize) -> Option<Vec<BigUint>> {
    let deg = d.degree()?;
    match deg {
        0 => Some(Vec::new()),
        1 => {
            // d = x + c  ⟹  root −c (d is monic here).
            Some(vec![(p - &d.coeff(0)) % p])
        }
        2 => {
            // Monic x² + a₁x + a₀: roots (−a₁ ± sqrt(a₁² − 4a₀))/2.
            let a1 = d.coeff(1);
            let a0 = d.coeff(0);
            let disc = (&a1 * &a1 + p * p - (BigUint::from(4u32) * &a0) % p) % p;
            *ops += 2;
            // Tonelli–Shanks is a modular exponentiation: ~1.5·log₂ p
            // multiplications, the same order as the x^p step above.
            *ops += (p.bits() as usize * 3) / 2;
            let root = sqrt_mod_p(&disc, p)?;
            let two_inv = mod_inverse(&BigUint::from(2u32), p)?;
            let neg_a1 = (p - &a1) % p;
            let r1 = ((&neg_a1 + &root) % p * &two_inv) % p;
            let r2 = ((&neg_a1 + p - &root) % p * &two_inv) % p;
            *ops += 2;
            Some(vec![r1, r2])
        }
        _ => {
            // Cantor–Zassenhaus.  Deterministic seed: the caller is a
            // measurement harness, and a root finder that returns
            // different work for the same input would make the field-op
            // column unreproducible.
            let mut rng = StdRng::seed_from_u64(0x5ca1_ab1e ^ deg as u64);
            let exp = (p - BigUint::one()) >> 1;
            for _ in 0..64 {
                let b = rand_below(&mut rng, p);
                let shifted = FpPoly::from_coeffs(vec![b, BigUint::one()], p.clone());
                let powered = poly_powmod(&shifted, &exp, d, ops);
                let h = powered.sub(&FpPoly::one(p.clone()));
                if h.is_zero() {
                    continue;
                }
                let factor = d.gcd(&h).monic();
                *ops += (deg + 1) * (deg + 1);
                let fdeg = factor.degree().unwrap_or(0);
                if fdeg == 0 || fdeg == deg {
                    continue; // trivial split; try another b
                }
                let other = d.divrem(&factor).0.monic();
                let mut roots = roots_of_split_poly(&factor, p, ops)?;
                roots.extend(roots_of_split_poly(&other, p, ops)?);
                roots.sort_unstable();
                return Some(roots);
            }
            None
        }
    }
}

/// `base^e mod m`, by square-and-multiply, charging its coefficient
/// multiplications.
fn poly_powmod(base: &FpPoly, e: &BigUint, m: &FpPoly, ops: &mut usize) -> FpPoly {
    let p = &m.p;
    let mut result = FpPoly::one(p.clone()).rem(m);
    let mut acc = base.rem(m);
    for i in 0..e.bits() {
        if e.bit(i) {
            result = poly_mul_mod(&result, &acc, m, ops);
        }
        if i + 1 < e.bits() {
            acc = poly_mul_mod(&acc, &acc, m, ops);
        }
    }
    result
}

/// Smoothness by `gcd(u, x^p − x)`, with the roots read off in closed
/// form.
///
/// `u` splits into linear factors over `F_p` exactly when its radical
/// `u/gcd(u, u')` — the product of its distinct irreducible factors —
/// equals `gcd(u, x^p − x)`, which is the product of its distinct
/// *linear* factors.  Comparing degrees is enough, both being monic
/// divisors of `u` and one dividing the other.
fn split_by_gcd(u: &FpPoly, p: &BigUint, ops: &mut usize) -> Option<Vec<(BigUint, usize)>> {
    let deg = u.degree()?;
    if deg == 0 {
        return Some(Vec::new());
    }

    // Degrees 1 and 2 — the only ones genus 2 ever produces — need no
    // `x^p` at all: a monic quadratic splits over `F_p` exactly when its
    // discriminant is a square, which is one Legendre symbol.  Going
    // through the general machinery here would cost `log₂ p` polynomial
    // squarings to learn what one exponentiation already says.
    if deg <= 2 {
        return split_low_degree(u, p, ops);
    }

    let du = derivative(u, p);
    let radical = if du.is_zero() {
        // Only possible when p | every exponent; fall back rather than
        // reason about it, since it cannot occur for deg u ≤ g < p.
        return split_by_scan(u, p, ops);
    } else {
        let g = u.gcd(&du);
        *ops += (deg + 1) * (deg + 1);
        u.divrem(&g).0.monic()
    };

    let xp = x_pow_p_mod(u, p, ops);
    let xp_minus_x = xp.sub(&FpPoly::x(p.clone()));
    let linear_part = u.gcd(&xp_minus_x).monic();
    *ops += (deg + 1) * (deg + 1);

    if linear_part.degree() != radical.degree() {
        // Some irreducible factor has degree ≥ 2: not smooth.
        return None;
    }

    let roots = match roots_of_split_poly(&linear_part, p, ops) {
        Some(r) => r,
        // Degree ≥ 3 radical: no closed form here, so use the scan
        // rather than return a wrong answer.
        None => return split_by_scan(u, p, ops),
    };

    // Multiplicities, by dividing each root out of `u` while it goes.
    let mut out = Vec::with_capacity(roots.len());
    let mut rest = u.clone();
    let mut total = 0usize;
    for x in roots {
        let lin = FpPoly::from_coeffs(vec![(p - &x) % p, BigUint::one()], p.clone());
        let mut mult = 0usize;
        loop {
            *ops += rest.degree().unwrap_or(0);
            let (q, r) = rest.divrem(&lin);
            if !r.is_zero() {
                break;
            }
            rest = q;
            mult += 1;
        }
        if mult > 0 {
            total += mult;
            out.push((x, mult));
        }
    }
    // The degree check above says this holds; assert it rather than
    // trust it, since a wrong "smooth" would poison the relation matrix
    // with a row that is not a relation.
    if total != deg {
        return None;
    }
    out.sort_unstable_by(|a, b| a.0.cmp(&b.0));
    Some(out)
}

/// Closed-form split for `deg u ∈ {1, 2}`.
///
/// `deg 1` always splits.  For monic `x² + a₁x + a₀` the discriminant
/// `a₁² − 4a₀` decides it: a non-residue means an irreducible quadratic
/// (not smooth), zero means a double root, and a square gives the two
/// roots by the usual formula.
fn split_low_degree(u: &FpPoly, p: &BigUint, ops: &mut usize) -> Option<Vec<(BigUint, usize)>> {
    match u.degree()? {
        1 => {
            // Monic x + c has the single root −c.
            let inv_lead = mod_inverse(&u.coeff(1), p)?;
            *ops += 1;
            let c = (&u.coeff(0) * &inv_lead) % p;
            Some(vec![((p - c) % p, 1)])
        }
        2 => {
            let lead_inv = mod_inverse(&u.coeff(2), p)?;
            *ops += 2;
            let a1 = (&u.coeff(1) * &lead_inv) % p;
            let a0 = (&u.coeff(0) * &lead_inv) % p;
            let four_a0 = (BigUint::from(4u32) * &a0) % p;
            let disc = (&a1 * &a1 % p + p - four_a0) % p;
            *ops += 2;
            let neg_a1 = (p - &a1) % p;
            let two_inv = mod_inverse(&BigUint::from(2u32), p)?;

            if disc.is_zero() {
                // Double root −a₁/2.
                *ops += 1;
                let r = (&neg_a1 * &two_inv) % p;
                return Some(vec![(r, 2)]);
            }
            // One Euler/Tonelli exponentiation: ~1.5·log₂ p mul-mods.
            *ops += (p.bits() as usize * 3) / 2;
            let root = sqrt_mod_p(&disc, p)?; // None ⟹ irreducible ⟹ not smooth
            let r1 = ((&neg_a1 + &root) % p * &two_inv) % p;
            let r2 = ((&neg_a1 + p - &root) % p * &two_inv) % p;
            *ops += 2;
            let (lo, hi) = if r1 <= r2 { (r1, r2) } else { (r2, r1) };
            Some(vec![(lo, 1), (hi, 1)])
        }
        _ => None,
    }
}

fn split_by_scan(u: &FpPoly, p: &BigUint, ops: &mut usize) -> Option<Vec<(BigUint, usize)>> {
    let deg = u.degree()?;
    if deg == 0 {
        return Some(Vec::new());
    }
    let p_u = *p.to_u64_digits().first()? as u128;
    if p.to_u64_digits().len() > 1 {
        return None;
    }

    let mut roots = Vec::new();
    let mut total = 0usize;
    let mut rest = u.clone();
    for xi in 0..p_u as u64 {
        if total == deg {
            break;
        }
        let x = BigUint::from(xi);
        // Horner: one multiplication per coefficient.
        *ops += rest.degree().unwrap_or(0);
        if !rest.eval(&x).is_zero() {
            continue;
        }
        // Divide out (x − xi) as often as it goes.
        let lin = FpPoly::from_coeffs(vec![(p - &x) % p, BigUint::one()], p.clone());
        let mut mult = 0usize;
        loop {
            // Dividing by a monic linear factor is synthetic division:
            // one multiplication per remaining coefficient.
            *ops += rest.degree().unwrap_or(0);
            let (q, r) = rest.divrem(&lin);
            if !r.is_zero() {
                break;
            }
            rest = q;
            mult += 1;
        }
        total += mult;
        roots.push((x, mult));
    }
    if total == deg {
        Some(roots)
    } else {
        None
    }
}

/// Decompose a reduced divisor over the factor base.
///
/// Returns the coefficient vector `[(index, coefficient)]` with
/// `D ≡ Σ coefficient · F_index` in `Jac(C)(F_p)`, or `None` when `D`
/// is not smooth, or is smooth but meets a place outside a truncated
/// factor base.
pub fn decompose_over_factor_base(
    curve: &HyperellipticCurveP,
    d: &MumfordDivisorP,
    fb: &HecFactorBase,
) -> Option<Vec<(usize, i64)>> {
    let mut ops = 0usize;
    decompose_over_factor_base_counted(curve, d, fb, &mut ops)
}

/// As [`decompose_over_factor_base`], adding its `F_p` multiplications
/// to `ops`.
pub fn decompose_over_factor_base_counted(
    curve: &HyperellipticCurveP,
    d: &MumfordDivisorP,
    fb: &HecFactorBase,
    ops: &mut usize,
) -> Option<Vec<(usize, i64)>> {
    decompose_counted_with(curve, d, fb, ops, &SmoothnessTest::default())
}

/// As [`decompose_over_factor_base_counted`], choosing the oracle.
pub fn decompose_counted_with(
    curve: &HyperellipticCurveP,
    d: &MumfordDivisorP,
    fb: &HecFactorBase,
    ops: &mut usize,
    test: &SmoothnessTest,
) -> Option<Vec<(usize, i64)>> {
    let p = &curve.p;
    let half = (p - BigUint::one()) >> 1;
    let roots = split_counted_with(&d.u, p, ops, test)?;

    let mut acc: HashMap<usize, i64> = HashMap::new();
    for (x, mult) in roots {
        *ops += d.v.degree().unwrap_or(0);
        let y = d.v.eval(&x);
        // `u | v² − f` guarantees this, but the attack is only as
        // sound as the representation it reads.
        debug_assert!(curve.is_on_curve(&x, &y));
        let idx = fb.index_of_x(&x)?;
        let sign: i64 = if y.is_zero() || y <= half { 1 } else { -1 };
        debug_assert_eq!(fb.entries[idx].y, if sign > 0 { y.clone() } else { p - &y });
        *acc.entry(idx).or_insert(0) += sign * mult as i64;
    }

    let mut out: Vec<(usize, i64)> = acc.into_iter().filter(|&(_, c)| c != 0).collect();
    out.sort_unstable_by_key(|&(i, _)| i);
    Some(out)
}

// ── Relations ──────────────────────────────────────────────────────────

/// One relation `a·D_1 + b·D_2 = Σ c_i F_i`.
#[derive(Clone, Debug)]
pub struct HecRelation {
    pub coef_a: BigUint,
    pub coef_b: BigUint,
    /// `(factor-base index, coefficient)`, coefficients non-zero.
    pub entries: Vec<(usize, i64)>,
}

impl HecIndexCalculusReport {
    /// Group operations per trial, excluding precomputation — the
    /// quantity the relation-search mode actually changes.  `Random`
    /// sits at `2⌈log₂ N⌉`; `Walk` sits at 1.
    pub fn ops_per_trial(&self) -> f64 {
        if self.trials == 0 {
            0.0
        } else {
            (self.jacobian_ops - self.precompute_ops) as f64 / self.trials as f64
        }
    }
}

/// Counters for the `S = operations / sqrt(N)` accounting `AGENTS.md`
/// requires of any comparison against Pollard rho.
///
/// `jacobian_ops` counts Cantor compositions and doublings charged to
/// the relation stage; the linear-algebra stage is reported as its
/// own row-operation count, because the two are not the same unit and
/// conflating them is exactly how a cost gets relabelled rather than
/// removed.
#[derive(Clone, Debug, Default)]
pub struct HecIndexCalculusReport {
    pub factor_base_size: usize,
    pub trials: usize,
    pub smooth_trials: usize,
    /// Smooth, but met a place outside a truncated factor base.
    pub discarded_off_base: usize,
    pub relations: usize,
    pub jacobian_ops: usize,
    /// Of those, the walk's step precomputation — a fixed cost that
    /// amortises over trials and so dominates at toy `N`, exactly as
    /// rho's branch precomputation does.  Split out for the same
    /// reason: the per-trial price is the thing the walk changed.
    pub precompute_ops: usize,
    /// `F_p` multiplications spent in the smoothness oracle (root
    /// finding and the decomposition's evaluations).  Reported in field
    /// operations, not group operations — the caller converts, because
    /// only a measurement can say what the ratio is on a given machine.
    pub smoothness_field_ops: usize,
    pub solve_row_ops: usize,
    pub solved: bool,
}

impl HecIndexCalculusReport {
    /// Observed smoothness probability — compare against `1/g!` for
    /// the full degree-1 base.
    pub fn smoothness_rate(&self) -> f64 {
        if self.trials == 0 {
            0.0
        } else {
            self.smooth_trials as f64 / self.trials as f64
        }
    }
}

/// How relations are drawn.
///
/// The cost difference is the whole point: `Random` pays a fresh pair of
/// scalar multiplications, `2⌈log₂ N⌉` group operations, for every
/// candidate divisor; `Walk` pays **one** group operation per candidate
/// by stepping an existing `R = a·D₁ + b·D₂` to `R + S_j` and adding the
/// step's known `(a_j, b_j)` to its coefficients — the same trick that
/// makes an `r`-adding rho walk cheap.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum RelationSearch {
    /// Independent `(a, b)` per trial.  Simple, and the reference the
    /// walk has to beat.
    Random,
    /// `r`-adding walk, perturbed every `restart_interval` trials.
    ///
    /// The perturbation is not optional bookkeeping.  A deterministic
    /// walk enters a cycle after `O(sqrt(N))` steps, and this attack
    /// needs `m + 1 ≈ p/2` relations out of a group of size `N ≈ p²` —
    /// the same order — so an undisturbed walk would start re-deriving
    /// relations it already has, exactly when it still needs new ones.
    /// It escapes by adding a **randomly chosen** step rather than by
    /// building a fresh point: the choice comes from the RNG instead of
    /// the position hash, so the trajectory leaves its orbit for one
    /// group operation instead of `2⌈log₂ N⌉`.
    Walk {
        branches: usize,
        restart_interval: usize,
        /// Bit length of the step coefficients `a_j, b_j`.
        ///
        /// Each branch costs `2·step_bits` group operations to build,
        /// and precomputation is the relation stage's largest term once
        /// the per-trial cost is one operation.  Short coefficients do
        /// not weaken anything: a relation is an algebraic identity
        /// verified as it is recorded, so the distribution of the steps
        /// affects only how fast smooth divisors turn up, which the
        /// trial count measures directly.
        step_bits: u32,
    },
}

impl RelationSearch {
    /// The walk this module uses unless told otherwise.
    pub fn walk() -> Self {
        // 16 branches, matching the rho reference: Teske's analysis says
        // an r-adding walk is within a few percent of the random-map
        // ideal from r = 16, and every extra branch is a scalar-mult
        // pair of precomputation that has to amortise over the trials.
        Self::Walk {
            branches: 16,
            restart_interval: 64,
            step_bits: 8,
        }
    }
}

/// How the relation system is solved.
///
/// The matrix is extremely sparse by construction: a genus-`g` relation
/// touches at most `g` factor-base columns, plus the `k` column, so each
/// row carries `≤ g + 1` non-zeros regardless of `m`.  A dense `O(m³)`
/// elimination ignores that and, once the relation stage is walked
/// rather than re-drawn, becomes the dominant cost.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum LinearAlgebra {
    /// Dense Gaussian elimination mod `N`.  Simple, and the reference
    /// the sparse solve has to beat.
    Dense,
    /// Sparse elimination mod `N` with Markowitz-style pivoting: at each
    /// step take the factor-base column with fewest remaining rows, and
    /// within it the shortest row.  Only `k` is read off, so columns
    /// that never become pivots are simply never formed.
    Sparse,
}

/// Parameters of the relation search and solve.
#[derive(Clone, Debug)]
pub struct HecIndexCalculusParams {
    /// Factor base cap; `usize::MAX` for every degree-1 place.
    pub fb_size: usize,
    /// Rows collected beyond `fb_size + 1` unknowns.
    pub extra_relations: usize,
    /// Give up after this many candidate divisors in total.
    pub max_trials: usize,
    pub seed: u64,
    /// How candidates are produced; see [`RelationSearch`].
    pub search: RelationSearch,
    /// How the relation system is solved; see [`LinearAlgebra`].
    pub linear_algebra: LinearAlgebra,
    /// How smoothness is decided; see [`SmoothnessTest`].
    pub smoothness: SmoothnessTest,
}

impl Default for HecIndexCalculusParams {
    fn default() -> Self {
        Self {
            fb_size: usize::MAX,
            extra_relations: 8,
            max_trials: 200_000,
            seed: 0,
            search: RelationSearch::walk(),
            linear_algebra: LinearAlgebra::Sparse,
            smoothness: SmoothnessTest::Gcd,
        }
    }
}

/// Branch selector for the adding walk: a hash of the Mumford
/// representation, so equal classes take equal steps.
fn walk_branch(d: &MumfordDivisorP, branches: usize) -> usize {
    let mut acc: u64 = 0;
    for poly in [&d.u, &d.v] {
        for limb in poly.coeffs.iter().flat_map(|c| c.to_u64_digits()) {
            acc = acc.wrapping_mul(0x9e37_79b9_7f4a_7c15).wrapping_add(limb);
        }
        acc = acc.wrapping_mul(0x9e37_79b9_7f4a_7c15).wrapping_add(1);
    }
    (acc >> 32) as usize % branches.max(1)
}

/// Uniform-ish `BigUint` in `[0, n)`.
///
/// Samples 64 bits beyond `n` and reduces, so the modulo bias is
/// below `2^-64` — irrelevant to a relation search, and stated rather
/// than hidden because this is not a sampler to reuse for key
/// material.
fn rand_below(rng: &mut StdRng, n: &BigUint) -> BigUint {
    let bytes = (n.bits() as usize).div_ceil(8) + 8;
    let mut buf = vec![0u8; bytes];
    rng.fill_bytes(&mut buf);
    BigUint::from_bytes_be(&buf) % n
}

/// Collect relations by walking `R = a·D_1 + b·D_2` for random
/// `(a, b)` and keeping the smooth reduced representatives.
///
/// Stops at `wanted` relations or `params.max_trials` draws,
/// whichever comes first; the report says which.
#[allow(clippy::too_many_arguments)]
pub fn collect_relations(
    curve: &HyperellipticCurveP,
    d1: &MumfordDivisorP,
    d2: &MumfordDivisorP,
    n: &BigUint,
    fb: &HecFactorBase,
    wanted: usize,
    params: &HecIndexCalculusParams,
    report: &mut HecIndexCalculusReport,
) -> Vec<HecRelation> {
    let mut rng = StdRng::seed_from_u64(params.seed);
    let mut relations = Vec::with_capacity(wanted);

    // One scalar multiplication pair, in group operations.  Both modes
    // are charged this whenever they build a divisor from scratch.
    let scalar_pair_ops = 2 * (n.bits() as usize + 1);

    // Precomputed steps S_j = a_j·D₁ + b_j·D₂ for the walk.  Charged up
    // front, like rho's branches: a precomputation left out of the
    // accounting is a cost moved, not removed.
    let (branches, restart_interval, step_bits) = match params.search {
        RelationSearch::Random => (0usize, usize::MAX, 0),
        RelationSearch::Walk {
            branches,
            restart_interval,
            step_bits,
        } => (branches.max(1), restart_interval.max(1), step_bits.max(1)),
    };
    // Steps with `step_bits`-bit coefficients cost `2·step_bits`
    // operations each instead of `2⌈log₂ N⌉`.
    let step_bound = BigUint::one() << step_bits;
    let step_build_ops = 2 * step_bits as usize;
    let mut steps: Vec<(BigUint, BigUint, MumfordDivisorP)> = Vec::with_capacity(branches);
    for _ in 0..branches {
        let a = rand_below(&mut rng, &step_bound) + BigUint::one();
        let b = rand_below(&mut rng, &step_bound) + BigUint::one();
        let s = d1
            .scalar_mul(&a, curve)
            .add(&d2.scalar_mul(&b, curve), curve);
        report.jacobian_ops += step_build_ops;
        report.precompute_ops += step_build_ops;
        steps.push((a, b, s));
    }

    // Current walk position; `None` forces a fresh start.
    let mut current: Option<(BigUint, BigUint, MumfordDivisorP)> = None;
    let mut since_restart = 0usize;

    while relations.len() < wanted && report.trials < params.max_trials {
        report.trials += 1;

        let (a, b, r) = match (&params.search, current.take()) {
            // Fresh independent draw: two scalar multiplications.
            (RelationSearch::Random, _) | (_, None) => {
                let a = rand_below(&mut rng, n);
                let b = rand_below(&mut rng, n);
                let r = d1
                    .scalar_mul(&a, curve)
                    .add(&d2.scalar_mul(&b, curve), curve);
                report.jacobian_ops += scalar_pair_ops;
                if matches!(params.search, RelationSearch::Walk { .. }) {
                    // A restart is precomputation too: it buys position,
                    // not a candidate the cheap step could not reach.
                    report.precompute_ops += scalar_pair_ops;
                }
                since_restart = 0;
                (a, b, r)
            }
            // One step of the walk: one group operation.
            (RelationSearch::Walk { .. }, Some((a, b, r))) => {
                let (aj, bj, sj) = &steps[walk_branch(&r, steps.len())];
                let next = r.add(sj, curve);
                report.jacobian_ops += 1;
                ((a + aj) % n, (b + bj) % n, next)
            }
        };

        if let RelationSearch::Walk { .. } = params.search {
            since_restart += 1;
            if since_restart >= restart_interval {
                // Escape the orbit with one randomly chosen step.  The
                // index comes from the RNG, not from the position, so
                // the next point is off the deterministic trajectory —
                // which is the whole job of a restart, at one group
                // operation instead of a fresh pair of scalar
                // multiplications.
                let j = (rng.next_u64() as usize) % steps.len();
                let (aj, bj, sj) = &steps[j];
                let jumped = r.add(sj, curve);
                report.jacobian_ops += 1;
                report.precompute_ops += 1;
                current = Some(((&a + aj) % n, (&b + bj) % n, jumped));
                since_restart = 0;
            } else {
                current = Some((a.clone(), b.clone(), r.clone()));
            }
        }

        if r.is_identity() {
            // a·D₁ + b·D₂ = 0 is a relation with no factor-base part;
            // it is still a valid row and pins the logarithm directly.
            relations.push(HecRelation {
                coef_a: a,
                coef_b: b,
                entries: Vec::new(),
            });
            report.smooth_trials += 1;
            continue;
        }
        let mut field_ops = 0usize;
        let decomposed = decompose_counted_with(curve, &r, fb, &mut field_ops, &params.smoothness);
        report.smoothness_field_ops += field_ops;
        match decomposed {
            Some(entries) => {
                report.smooth_trials += 1;
                relations.push(HecRelation {
                    coef_a: a,
                    coef_b: b,
                    entries,
                });
            }
            None => {
                // Distinguish "not smooth" from "smooth off base" so a
                // truncated base can be tuned on evidence.
                let mut probe_ops = 0usize;
                let smooth = split_counted_with(&r.u, &curve.p, &mut probe_ops, &params.smoothness)
                    .is_some();
                // The probe re-runs the oracle, so it is charged too.
                report.smoothness_field_ops += probe_ops;
                if smooth {
                    report.smooth_trials += 1;
                    report.discarded_off_base += 1;
                }
            }
        }
    }
    report.relations = relations.len();
    relations
}

// ── End-to-end DLP ─────────────────────────────────────────────────────

/// **Solve `D_2 = k · D_1` in `Jac(C)(F_p)`** by index calculus.
///
/// `n` must be the order of `D_1` and must be **prime** — the solve
/// inverts pivots modulo it.  Use [`prime_order_of`] to obtain one.
///
/// Returns `Some(k)` only after verifying `k·D_1 = D_2`: an
/// under-determined system yields `None`, never an unchecked answer.
pub fn hec_index_calculus_dlp(
    curve: &HyperellipticCurveP,
    d1: &MumfordDivisorP,
    d2: &MumfordDivisorP,
    n: &BigUint,
    params: &HecIndexCalculusParams,
) -> (Option<BigUint>, HecIndexCalculusReport) {
    let mut report = HecIndexCalculusReport::default();
    let fb = build_factor_base(curve, params.fb_size);
    report.factor_base_size = fb.len();
    if fb.is_empty() {
        return (None, report);
    }

    let m = fb.len();
    let wanted = m + 1 + params.extra_relations;
    let relations = collect_relations(curve, d1, d2, n, &fb, wanted, params, &mut report);
    if relations.len() < m + 1 {
        return (None, report);
    }

    // Unknowns: (y_1, …, y_m, k), where y_i = log_{D₁} F_i.
    // Row: Σ c_i y_i − b k ≡ a  (mod n).
    let mut rows: Vec<Vec<(usize, BigUint)>> = Vec::with_capacity(relations.len());
    let mut rhs: Vec<BigUint> = Vec::with_capacity(relations.len());
    for rel in &relations {
        let mut row: HashMap<usize, BigUint> = HashMap::new();
        for &(j, c) in &rel.entries {
            let e = row.entry(j).or_insert_with(BigUint::zero);
            *e = (&*e + signed_mod(c, n)) % n;
        }
        row.insert(m, (n - &(&rel.coef_b % n)) % n);
        let mut sparse: Vec<(usize, BigUint)> =
            row.into_iter().filter(|(_, v)| !v.is_zero()).collect();
        sparse.sort_unstable_by_key(|&(j, _)| j);
        rows.push(sparse);
        rhs.push(&rel.coef_a % n);
    }

    let k = match params.linear_algebra {
        LinearAlgebra::Sparse => {
            let (k, ops) = match sparse_solve_for_k(rows, rhs, m, n) {
                Some(v) => v,
                None => return (None, report),
            };
            report.solve_row_ops = ops;
            k
        }
        LinearAlgebra::Dense => {
            let mut matrix: Vec<Vec<BigUint>> = Vec::with_capacity(rows.len());
            for row in &rows {
                let mut dense = vec![BigUint::zero(); m + 1];
                for (j, v) in row {
                    dense[*j] = v.clone();
                }
                matrix.push(dense);
            }
            report.solve_row_ops = rows.len() * (m + 1) * (m + 1);
            let solution = match gaussian_eliminate_mod_n(&mut matrix, &mut rhs, n) {
                Some(s) => s,
                None => return (None, report),
            };
            solution[m].clone()
        }
    };

    if &d1.scalar_mul(&k, curve) == d2 {
        report.solved = true;
        (Some(k), report)
    } else {
        (None, report)
    }
}

/// Eliminate every factor-base unknown from the sparse system and read
/// off `k` (column index `m`).
///
/// Returns `(k, mul_mods)` — the multiplication count is **measured**,
/// not estimated, because the whole point of the sparse path is that its
/// cost no longer follows `rows·m²`, so an estimate would not track it.
/// `None` when the system does not determine `k`.
fn sparse_solve_for_k(
    mut rows: Vec<Vec<(usize, BigUint)>>,
    mut rhs: Vec<BigUint>,
    m: usize,
    n: &BigUint,
) -> Option<(BigUint, usize)> {
    let mut ops = 0usize;
    // column -> rows still carrying it (may contain stale entries; they
    // are filtered on use, which is cheaper than eager deletion).
    let mut col_rows: HashMap<usize, Vec<usize>> = HashMap::new();
    for (i, row) in rows.iter().enumerate() {
        for (j, _) in row {
            col_rows.entry(*j).or_default().push(i);
        }
    }
    let mut eliminated = vec![false; rows.len()];

    loop {
        // Markowitz-lite: the factor-base column with the fewest live
        // rows, and within it the shortest row — this is what keeps
        // fill-in from turning the sparse solve back into a dense one.
        let mut best: Option<(usize, usize, usize)> = None; // (count, col, row)
        for (&col, holders) in col_rows.iter() {
            if col == m {
                continue;
            }
            let live: Vec<usize> = holders
                .iter()
                .copied()
                .filter(|&i| !eliminated[i] && rows[i].iter().any(|(j, _)| *j == col))
                .collect();
            if live.is_empty() {
                continue;
            }
            let count = live.len();
            let row = *live
                .iter()
                .min_by_key(|&&i| rows[i].len())
                .expect("live is non-empty");
            if best.map(|(c, _, _)| count < c).unwrap_or(true) {
                best = Some((count, col, row));
            }
        }
        let (_, col, pivot) = match best {
            Some(v) => v,
            None => break, // nothing left but the k column
        };

        // Normalise the pivot row.
        let pivot_val = rows[pivot]
            .iter()
            .find(|(j, _)| *j == col)
            .map(|(_, v)| v.clone())?;
        let inv = mod_inverse(&pivot_val, n)?;
        for (_, v) in rows[pivot].iter_mut() {
            *v = (&*v * &inv) % n;
            ops += 1;
        }
        rhs[pivot] = (&rhs[pivot] * &inv) % n;
        ops += 1;
        let pivot_row = rows[pivot].clone();
        let pivot_rhs = rhs[pivot].clone();
        eliminated[pivot] = true;

        // Eliminate `col` from every other live row carrying it.
        let holders = col_rows.get(&col).cloned().unwrap_or_default();
        for i in holders {
            if i == pivot || eliminated[i] {
                continue;
            }
            let factor = match rows[i].iter().find(|(j, _)| *j == col) {
                Some((_, v)) => v.clone(),
                None => continue,
            };
            let mut merged: HashMap<usize, BigUint> = rows[i].iter().cloned().collect();
            for (j, v) in &pivot_row {
                let term = (&factor * v) % n;
                ops += 1;
                let e = merged.entry(*j).or_insert_with(BigUint::zero);
                *e = (&*e + n - &term) % n;
            }
            rhs[i] = (&rhs[i] + n - &((&factor * &pivot_rhs) % n)) % n;
            ops += 1;
            let mut sparse: Vec<(usize, BigUint)> =
                merged.into_iter().filter(|(_, v)| !v.is_zero()).collect();
            sparse.sort_unstable_by_key(|&(j, _)| j);
            for (j, _) in &sparse {
                col_rows.entry(*j).or_default().push(i);
            }
            rows[i] = sparse;
        }
    }

    // A surviving row is `coef·k ≡ rhs`; any of them gives `k`.
    for (i, row) in rows.iter().enumerate() {
        if eliminated[i] {
            continue;
        }
        if row.len() == 1 && row[0].0 == m {
            let inv = mod_inverse(&row[0].1, n)?;
            ops += 1;
            return Some(((&rhs[i] * &inv) % n, ops));
        }
    }
    None
}

fn signed_mod(v: i64, n: &BigUint) -> BigUint {
    if v >= 0 {
        BigUint::from(v as u64) % n
    } else {
        (n - BigUint::from(v.unsigned_abs()) % n) % n
    }
}

// ── Order of a divisor class ───────────────────────────────────────────

/// Trial-division factorisation of a toy Jacobian order.
pub fn factorise_small(mut n: BigUint) -> Vec<(BigUint, u32)> {
    let mut out = Vec::new();
    let mut d = BigUint::from(2u32);
    while &d * &d <= n {
        let mut e = 0;
        while (&n % &d).is_zero() {
            n /= &d;
            e += 1;
        }
        if e > 0 {
            out.push((d.clone(), e));
        }
        d += 1u32;
    }
    if n > BigUint::one() {
        out.push((n, 1));
    }
    out
}

/// Exact order of `d` in `Jac(C)(F_p)`, given the group order
/// `jac_order`, and **only if that order is prime**.
///
/// Returns `None` when the order is composite: the index-calculus
/// solve needs a field, and a composite modulus belongs to
/// Pohlig–Hellman over the prime factors, not here.
pub fn prime_order_of(
    curve: &HyperellipticCurveP,
    d: &MumfordDivisorP,
    jac_order: &BigUint,
) -> Option<BigUint> {
    let mut order = jac_order.clone();
    for (q, e) in factorise_small(jac_order.clone()) {
        for _ in 0..e {
            let candidate = &order / &q;
            if d.scalar_mul(&candidate, curve).is_identity() {
                order = candidate;
            } else {
                break;
            }
        }
    }
    let factors = factorise_small(order.clone());
    if factors.len() == 1 && factors[0].1 == 1 && order > BigUint::one() {
        Some(order)
    } else {
        None
    }
}

/// Order of `d` in `Jac(C)(F_p)` **without** knowing the group order,
/// by Baby-step Giant-step over the Hasse–Weil interval.
///
/// `#Jac(C)(F_p) ∈ [(sqrt(p) − 1)^{2g}, (sqrt(p) + 1)^{2g}]`, so some
/// multiple of `ord(d)` lies there; BSGS finds one in `O(sqrt(W))`
/// group operations, `W` being the interval width (`≈ 4g·p^{g−1/2}`).
/// Factoring that multiple and dividing out gives the exact order.
///
/// This exists because the genus-2 route to the group order goes
/// through an `L`-polynomial that is genus-2 only.  Counting the
/// Jacobian is not the point of this module; having a prime-order
/// subgroup to work in is, and that does not require the group order.
/// The Hasse–Weil interval `[(sqrt(p) − 1)^{2g}, (sqrt(p) + 1)^{2g}]`
/// containing `#Jac(C)(F_p)`.
///
/// Useful without any point counting: it says how large a subgroup has
/// to be to carry most of the group, which is the condition that makes
/// an index-calculus-vs-rho comparison meaningful — rho searches the
/// subgroup, index calculus pays for a factor base sized by the whole
/// curve, so a tiny subgroup in a large Jacobian flatters rho for a
/// reason that has nothing to do with either algorithm.
pub fn hasse_interval(curve: &HyperellipticCurveP) -> Option<(u128, u128)> {
    let g = curve.genus as i32;
    let p_f = curve.p.to_u64_digits().first().copied()? as f64;
    let root = p_f.sqrt();
    let lo = (root - 1.0).powi(2 * g).floor().max(1.0) as u128;
    let hi = (root + 1.0).powi(2 * g).ceil() as u128;
    Some((lo, hi))
}

pub fn divisor_order_bsgs(
    curve: &HyperellipticCurveP,
    d: &MumfordDivisorP,
    max_baby_steps: usize,
) -> Option<BigUint> {
    let (lo, hi) = hasse_interval(curve)?;
    let width = hi.saturating_sub(lo).max(1);

    let steps = (width as f64).sqrt().ceil() as usize + 1;
    if steps > max_baby_steps {
        return None; // would cost more than the caller allowed
    }

    // Baby steps: −j·D for j ∈ [0, steps), keyed by Mumford rep.
    let neg_d = d.neg(curve);
    let mut table: HashMap<DivisorKey, usize> = HashMap::new();
    let mut acc = MumfordDivisorP::identity(curve.p.clone());
    for j in 0..steps {
        table.entry(divisor_key(&acc)).or_insert(j);
        acc = acc.add(&neg_d, curve);
    }

    // Giant steps: (lo + i·steps)·D.
    let stride = d.scalar_mul(&BigUint::from(steps as u64), curve);
    let mut cur = d.scalar_mul(&BigUint::from(lo), curve);
    let giant_max = (width as usize) / steps + 2;
    for i in 0..=giant_max {
        if let Some(&j) = table.get(&divisor_key(&cur)) {
            // (lo + i·steps)·D = −j·D  ⟹  (lo + i·steps + j)·D = 0.
            let m = BigUint::from(lo) + BigUint::from((i * steps + j) as u64);
            if m.is_zero() {
                continue;
            }
            if !d.scalar_mul(&m, curve).is_identity() {
                continue; // f64 interval arithmetic slipped; keep going
            }
            return Some(exact_order_from_multiple(curve, d, &m));
        }
        cur = cur.add(&stride, curve);
    }
    None
}

/// A hashable stand-in for a reduced divisor: its Mumford coefficients.
type DivisorKey = (Vec<Vec<u32>>, Vec<Vec<u32>>);

fn divisor_key(d: &MumfordDivisorP) -> DivisorKey {
    (
        d.u.coeffs.iter().map(|c| c.to_u32_digits()).collect(),
        d.v.coeffs.iter().map(|c| c.to_u32_digits()).collect(),
    )
}

/// Given `m` with `m·d = 0`, divide out prime factors while the result
/// still annihilates `d`.
fn exact_order_from_multiple(
    curve: &HyperellipticCurveP,
    d: &MumfordDivisorP,
    m: &BigUint,
) -> BigUint {
    let mut order = m.clone();
    for (q, e) in factorise_small(m.clone()) {
        for _ in 0..e {
            let candidate = &order / &q;
            if candidate > BigUint::zero() && d.scalar_mul(&candidate, curve).is_identity() {
                order = candidate;
            } else {
                break;
            }
        }
    }
    order
}

/// Largest prime factor of `n`, by trial division.  Toy sizes only.
pub fn largest_prime_factor(n: &BigUint) -> BigUint {
    factorise_small(n.clone())
        .into_iter()
        .map(|(q, _)| q)
        .max()
        .unwrap_or_else(BigUint::one)
}

/// Pick a generator of the (unique) subgroup of prime order `l`:
/// multiply a place by the cofactor until the result is non-trivial.
///
/// Returns `None` if every factor-base place lands in the identity,
/// which for `l | #Jac` cannot happen unless `l ∤ #Jac`.
pub fn subgroup_generator(
    curve: &HyperellipticCurveP,
    fb: &HecFactorBase,
    jac_order: &BigUint,
    l: &BigUint,
) -> Option<MumfordDivisorP> {
    let cofactor = jac_order / l;
    for e in &fb.entries {
        let d = e.divisor.scalar_mul(&cofactor, curve);
        if !d.is_identity() {
            return Some(d);
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::prime_hyperelliptic::brute_force_jac_order_via_lpoly;

    /// `y² = x⁵ + 3x³ + 2x² + x + 1` over `F_p`, genus 2.
    fn toy_curve(p: u64) -> HyperellipticCurveP {
        let p = BigUint::from(p);
        let f = FpPoly::from_coeffs(
            vec![
                BigUint::from(1u32),
                BigUint::from(1u32),
                BigUint::from(2u32),
                BigUint::from(3u32),
                BigUint::zero(),
                BigUint::from(1u32),
            ],
            p.clone(),
        );
        HyperellipticCurveP::new(p, f, 2)
    }

    #[test]
    fn factor_base_holds_one_of_each_pm_pair() {
        let curve = toy_curve(41);
        let fb = build_factor_base(&curve, usize::MAX);
        assert!(!fb.is_empty());
        let half = (&curve.p - BigUint::one()) >> 1;
        for e in &fb.entries {
            assert!(curve.is_on_curve(&e.x, &e.y));
            assert!(e.y <= half, "non-canonical representative in factor base");
            assert_eq!(fb.index_of_x(&e.x).map(|i| &fb.entries[i].x), Some(&e.x));
        }
    }

    #[test]
    fn splitting_agrees_with_reconstruction() {
        let p = BigUint::from(41u32);
        // (x − 3)²(x − 7)
        let lin = |c: u32| {
            FpPoly::from_coeffs(
                vec![(&p - BigUint::from(c)) % &p, BigUint::one()],
                p.clone(),
            )
        };
        let u = lin(3).mul(&lin(3)).mul(&lin(7));
        let roots = split_into_linear_factors(&u, &p).expect("splits");
        assert_eq!(
            roots,
            vec![(BigUint::from(3u32), 2), (BigUint::from(7u32), 1)]
        );
        // x² + 1 is irreducible mod 41? 41 ≡ 1 (mod 4) so it splits;
        // use a genuinely irreducible quadratic instead: x² − r for a
        // non-residue r.
        let mut non_residue = None;
        for r in 2u32..41 {
            if sqrt_mod_p(&BigUint::from(r), &p).is_none() {
                non_residue = Some(r);
                break;
            }
        }
        let r = non_residue.expect("a non-residue exists");
        let irred = FpPoly::from_coeffs(
            vec![
                (&p - BigUint::from(r)) % &p,
                BigUint::zero(),
                BigUint::one(),
            ],
            p.clone(),
        );
        assert!(split_into_linear_factors(&irred, &p).is_none());
    }

    #[test]
    fn decomposition_reproduces_the_divisor() {
        let curve = toy_curve(41);
        let fb = build_factor_base(&curve, usize::MAX);
        // Two distinct places: `deg u = 2 = g`, so Cantor composes
        // without reducing and the class is smooth by construction.
        // Three would reduce, and a reduced representative of a sum of
        // smooth classes is not itself smooth in general — that is the
        // whole reason the relation search is a search.
        let d = fb.entries[0].divisor.add(&fb.entries[1].divisor, &curve);
        let entries = decompose_over_factor_base(&curve, &d, &fb).expect("smooth by construction");
        let mut rebuilt = MumfordDivisorP::identity(curve.p.clone());
        for (i, c) in entries {
            let base = &fb.entries[i].divisor;
            let term = if c >= 0 {
                base.scalar_mul(&BigUint::from(c as u64), &curve)
            } else {
                base.neg(&curve)
                    .scalar_mul(&BigUint::from(c.unsigned_abs()), &curve)
            };
            rebuilt = rebuilt.add(&term, &curve);
        }
        assert_eq!(rebuilt, d);
    }

    #[test]
    fn solves_a_toy_jacobian_dlp() {
        let curve = toy_curve(41);
        let jac = brute_force_jac_order_via_lpoly(&curve);
        let fb = build_factor_base(&curve, usize::MAX);

        // Largest prime factor of #Jac, and a generator of that
        // subgroup.
        let l = factorise_small(jac.clone())
            .into_iter()
            .map(|(q, _)| q)
            .max()
            .expect("non-trivial Jacobian");
        assert!(l > BigUint::from(50u32), "toy subgroup too small: {l}");
        let d1 = subgroup_generator(&curve, &fb, &jac, &l).expect("generator exists");
        assert_eq!(prime_order_of(&curve, &d1, &jac).as_ref(), Some(&l));

        let k = &l / BigUint::from(3u32) + BigUint::from(7u32);
        let d2 = d1.scalar_mul(&k, &curve);

        let params = HecIndexCalculusParams {
            fb_size: usize::MAX,
            extra_relations: 5,
            max_trials: 50_000,
            seed: 20260915,
            search: RelationSearch::Random,
            linear_algebra: LinearAlgebra::Dense,
            smoothness: SmoothnessTest::Scan,
        };
        let (found, report) = hec_index_calculus_dlp(&curve, &d1, &d2, &l, &params);
        assert_eq!(found, Some(k), "report: {report:?}");
        assert!(report.solved);
        assert!(report.smoothness_rate() > 0.0);
    }

    /// Build a solvable instance on the toy curve: `(D₁, D₂, N, k)`.
    fn toy_instance(
        p: u64,
    ) -> (
        HyperellipticCurveP,
        MumfordDivisorP,
        MumfordDivisorP,
        BigUint,
        BigUint,
    ) {
        let curve = toy_curve(p);
        let jac = brute_force_jac_order_via_lpoly(&curve);
        let fb = build_factor_base(&curve, usize::MAX);
        let l = factorise_small(jac.clone())
            .into_iter()
            .map(|(q, _)| q)
            .max()
            .expect("non-trivial Jacobian");
        let d1 = subgroup_generator(&curve, &fb, &jac, &l).expect("generator exists");
        let k = &l / BigUint::from(3u32) + BigUint::from(7u32);
        let d2 = d1.scalar_mul(&k, &curve);
        (curve, d1, d2, l, k)
    }

    /// `C : y² = x⁷ + x³ + c x + 1` over `F_p`, genus 3.
    fn genus3_curve(p: u64, c: u64) -> HyperellipticCurveP {
        let p = BigUint::from(p);
        let f = FpPoly::from_coeffs(
            vec![
                BigUint::one(),
                BigUint::from(c) % &p,
                BigUint::zero(),
                BigUint::one(),
                BigUint::zero(),
                BigUint::zero(),
                BigUint::zero(),
                BigUint::one(),
            ],
            p.clone(),
        );
        HyperellipticCurveP::new(p, f, 3)
    }

    #[test]
    fn bsgs_order_agrees_with_the_l_polynomial_at_genus_two() {
        // Two independent routes to the same number: BSGS over the
        // Hasse-Weil interval, which knows nothing about the curve, and
        // the genus-2 L-polynomial, which counts points.  They are
        // wrong in different ways, so agreement is worth more than
        // either alone — and BSGS is the only one available at genus 3,
        // where the measurement actually goes.
        for p_u in [23u64, 41, 61] {
            let curve = toy_curve(p_u);
            let jac = brute_force_jac_order_via_lpoly(&curve);
            let fb = build_factor_base(&curve, usize::MAX);
            for e in fb.entries.iter().take(3) {
                let via_bsgs = divisor_order_bsgs(&curve, &e.divisor, 50_000)
                    .expect("BSGS should find an order at this size");
                // The L-polynomial route: the order divides #Jac, and
                // dividing out prime factors gives the same answer.
                let via_lpoly = exact_order_from_multiple(&curve, &e.divisor, &jac);
                assert_eq!(
                    via_bsgs, via_lpoly,
                    "p={p_u}: BSGS {via_bsgs} vs L-polynomial {via_lpoly}"
                );
                assert!((&jac % &via_bsgs).is_zero(), "order must divide #Jac");
            }
        }
    }

    #[test]
    fn solves_a_genus_three_dlp() {
        // Genus 3 is where the asymptotic crossover against rho is
        // supposed to live, so the pipeline has to work there before
        // any measurement of it means anything.  No L-polynomial is
        // available at this genus, so the order comes from BSGS over
        // the Hasse–Weil interval.
        let mut solved = false;
        // Scan `c` for a curve with a usable prime-order subgroup:
        // most genus-3 Jacobians here factor into small primes, and a
        // 37-element subgroup measures nothing.
        'outer: for c in 1..6u64 {
            let curve = genus3_curve(41, c);
            let fb = build_factor_base(&curve, usize::MAX);
            for e in fb.entries.iter().take(4) {
                let order = match divisor_order_bsgs(&curve, &e.divisor, 20_000) {
                    Some(o) => o,
                    None => continue,
                };
                assert!(e.divisor.scalar_mul(&order, &curve).is_identity());
                let l = largest_prime_factor(&order);
                if l < BigUint::from(500u32) {
                    continue;
                }
                let d1 = e.divisor.scalar_mul(&(&order / &l), &curve);
                assert_eq!(
                    divisor_order_bsgs(&curve, &d1, 20_000).as_ref(),
                    Some(&l),
                    "cofactor multiple should have exactly order l"
                );
                let k = &l / BigUint::from(3u32) + BigUint::from(4u32);
                let d2 = d1.scalar_mul(&k, &curve);
                let params = HecIndexCalculusParams {
                    fb_size: usize::MAX,
                    extra_relations: 8,
                    max_trials: 500_000,
                    seed: 4,
                    search: RelationSearch::walk(),
                    linear_algebra: LinearAlgebra::Sparse,
                    smoothness: SmoothnessTest::Gcd,
                };
                let (found, report) = hec_index_calculus_dlp(&curve, &d1, &d2, &l, &params);
                assert_eq!(found, Some(k), "genus-3 report: {report:?}");
                // Smoothness at genus 3 should be near 1/3! = 0.167, well
                // below genus 2's 0.5 — the cost the extra genus buys.
                assert!(
                    report.smoothness_rate() < 0.45,
                    "genus-3 smoothness {} looks like genus 2",
                    report.smoothness_rate()
                );
                solved = true;
                break 'outer;
            }
        }
        assert!(solved, "no usable genus-3 subgroup found");
    }

    #[test]
    fn cantor_zassenhaus_roots_agree_with_the_scan_at_degree_three() {
        // deg u = 3 is what genus 3 produces and what the closed forms
        // do not cover, so the CZ path is the one carrying the fast
        // oracle there.  Exhaustive over monic cubics for two primes.
        for p_u in [11u64, 23] {
            let p = BigUint::from(p_u);
            for a2 in 0..p_u {
                for a1 in 0..p_u {
                    for a0 in 0..p_u {
                        let u = FpPoly::from_coeffs(
                            vec![
                                BigUint::from(a0),
                                BigUint::from(a1),
                                BigUint::from(a2),
                                BigUint::one(),
                            ],
                            p.clone(),
                        );
                        let (mut o1, mut o2) = (0usize, 0usize);
                        assert_eq!(
                            split_by_scan(&u, &p, &mut o1),
                            split_by_gcd(&u, &p, &mut o2),
                            "p={p_u} u=x^3+{a2}x^2+{a1}x+{a0}"
                        );
                    }
                }
            }
        }
    }

    #[test]
    fn gcd_oracle_agrees_with_the_scan_on_every_monic_quadratic() {
        // Exhaustive over all monic u of degree ≤ 2 for several p: the
        // fast oracle is only worth having if it is the *same* oracle.
        // A disagreement in the "smooth" direction would put a row in
        // the relation matrix that is not a relation.
        for p_u in [11u64, 13, 41, 61] {
            let p = BigUint::from(p_u);
            for a1 in 0..p_u {
                for a0 in 0..p_u {
                    for deg in [1usize, 2] {
                        let u = if deg == 1 {
                            FpPoly::from_coeffs(vec![BigUint::from(a0), BigUint::one()], p.clone())
                        } else {
                            FpPoly::from_coeffs(
                                vec![BigUint::from(a0), BigUint::from(a1), BigUint::one()],
                                p.clone(),
                            )
                        };
                        let (mut o1, mut o2) = (0usize, 0usize);
                        let scan = split_by_scan(&u, &p, &mut o1);
                        let gcd = split_by_gcd(&u, &p, &mut o2);
                        assert_eq!(
                            scan, gcd,
                            "p={p_u} u={:?}: scan {scan:?} vs gcd {gcd:?}",
                            u.coeffs
                        );
                    }
                }
            }
        }
    }

    #[test]
    fn gcd_oracle_is_cheaper_than_the_scan_and_gets_the_same_answer() {
        let (curve, d1, d2, l, k) = toy_instance(251);
        let scan = HecIndexCalculusParams {
            fb_size: usize::MAX,
            extra_relations: 8,
            max_trials: 200_000,
            seed: 11,
            search: RelationSearch::walk(),
            linear_algebra: LinearAlgebra::Sparse,
            smoothness: SmoothnessTest::Scan,
        };
        let fast = HecIndexCalculusParams {
            smoothness: SmoothnessTest::Gcd,
            ..scan.clone()
        };
        let (scan_k, scan_rep) = hec_index_calculus_dlp(&curve, &d1, &d2, &l, &scan);
        let (fast_k, fast_rep) = hec_index_calculus_dlp(&curve, &d1, &d2, &l, &fast);

        assert_eq!(scan_k.as_ref(), Some(&k));
        assert_eq!(fast_k.as_ref(), Some(&k), "fast report: {fast_rep:?}");
        // Same seed and the same oracle answers mean the same walk and
        // the same relations, so the trial counts must match exactly —
        // this is what makes the field-op comparison a like-for-like.
        assert_eq!(scan_rep.trials, fast_rep.trials);
        assert!(
            fast_rep.smoothness_field_ops * 4 < scan_rep.smoothness_field_ops,
            "gcd {} vs scan {} field ops",
            fast_rep.smoothness_field_ops,
            scan_rep.smoothness_field_ops
        );
    }

    #[test]
    fn walk_solves_and_costs_far_less_than_redrawing() {
        let (curve, d1, d2, l, k) = toy_instance(41);
        let base = HecIndexCalculusParams {
            fb_size: usize::MAX,
            extra_relations: 5,
            max_trials: 50_000,
            seed: 20260916,
            search: RelationSearch::Random,
            linear_algebra: LinearAlgebra::Sparse,
            smoothness: SmoothnessTest::Gcd,
        };
        let (rnd_k, rnd) = hec_index_calculus_dlp(&curve, &d1, &d2, &l, &base);
        let walked = HecIndexCalculusParams {
            search: RelationSearch::walk(),
            ..base
        };
        let (walk_k, walk) = hec_index_calculus_dlp(&curve, &d1, &d2, &l, &walked);

        assert_eq!(rnd_k.as_ref(), Some(&k));
        assert_eq!(walk_k.as_ref(), Some(&k), "walk report: {walk:?}");
        // The walk pays one group operation per trial where the random
        // draw pays 2⌈log₂ N⌉, so on comparable trial counts it must
        // come out well ahead.  This is the whole claim of the walk; if
        // it ever stops holding, the walk has stopped being a walk.
        // Per trial, excluding precomputation: the walk pays one group
        // operation, the random draw pays 2⌈log₂ N⌉.  Total ops are the
        // wrong comparison at this toy `N`, where the walk's 32-branch
        // precomputation has barely amortised — which is itself the
        // reason the report separates the two.
        assert!(walk.ops_per_trial() < 1.5, "walk {:?}", walk);
        assert!(
            rnd.ops_per_trial() > 4.0 * walk.ops_per_trial(),
            "random {:.1} vs walk {:.1} ops/trial",
            rnd.ops_per_trial(),
            walk.ops_per_trial()
        );
    }

    #[test]
    fn sparse_solve_agrees_with_dense_and_is_cheaper() {
        let (curve, d1, d2, l, k) = toy_instance(41);
        let dense = HecIndexCalculusParams {
            fb_size: usize::MAX,
            extra_relations: 5,
            max_trials: 50_000,
            seed: 7,
            search: RelationSearch::walk(),
            linear_algebra: LinearAlgebra::Dense,
            smoothness: SmoothnessTest::Scan,
        };
        let sparse = HecIndexCalculusParams {
            linear_algebra: LinearAlgebra::Sparse,
            ..dense.clone()
        };
        let (dense_k, dense_rep) = hec_index_calculus_dlp(&curve, &d1, &d2, &l, &dense);
        let (sparse_k, sparse_rep) = hec_index_calculus_dlp(&curve, &d1, &d2, &l, &sparse);

        // Same seed, same relations, so the two solvers see the same
        // system and must agree on its answer.
        assert_eq!(dense_k.as_ref(), Some(&k));
        assert_eq!(sparse_k, dense_k, "sparse report: {sparse_rep:?}");
        assert!(
            sparse_rep.solve_row_ops < dense_rep.solve_row_ops,
            "sparse {} vs dense {} mul-mods",
            sparse_rep.solve_row_ops,
            dense_rep.solve_row_ops
        );
    }

    #[test]
    fn the_smoothness_oracle_is_charged() {
        let (curve, d1, d2, l, _k) = toy_instance(41);
        let params = HecIndexCalculusParams {
            fb_size: usize::MAX,
            extra_relations: 5,
            max_trials: 50_000,
            seed: 3,
            search: RelationSearch::walk(),
            linear_algebra: LinearAlgebra::Sparse,
            smoothness: SmoothnessTest::Gcd,
        };
        let (_k, report) = hec_index_calculus_dlp(&curve, &d1, &d2, &l, &params);
        // Every trial runs the oracle, so its field-operation count can
        // never be zero while trials were taken — a zero here would mean
        // the cost had gone missing from the accounting, not that it
        // was not paid.
        assert!(report.trials > 0);
        assert!(
            report.smoothness_field_ops >= report.trials,
            "oracle charged {} mul-mods over {} trials",
            report.smoothness_field_ops,
            report.trials
        );
    }

    #[test]
    fn truncated_factor_base_still_solves_or_reports_why() {
        let curve = toy_curve(41);
        let jac = brute_force_jac_order_via_lpoly(&curve);
        let full = build_factor_base(&curve, usize::MAX);
        let l = factorise_small(jac.clone())
            .into_iter()
            .map(|(q, _)| q)
            .max()
            .unwrap();
        let d1 = subgroup_generator(&curve, &full, &jac, &l).unwrap();
        let k = BigUint::from(11u32);
        let d2 = d1.scalar_mul(&k, &curve);

        let params = HecIndexCalculusParams {
            fb_size: full.len() / 2,
            extra_relations: 5,
            max_trials: 200_000,
            seed: 7,
            search: RelationSearch::Random,
            linear_algebra: LinearAlgebra::Dense,
            smoothness: SmoothnessTest::Scan,
        };
        let (found, report) = hec_index_calculus_dlp(&curve, &d1, &d2, &l, &params);
        // A reduced base trades trials for solve size; either it got
        // there, or the report says how many smooth divisors it threw
        // away off-base.  What it must never do is answer wrongly.
        match found {
            Some(x) => assert_eq!(x, k),
            None => assert!(report.discarded_off_base > 0 || report.relations < full.len() / 2 + 1),
        }
    }
}
