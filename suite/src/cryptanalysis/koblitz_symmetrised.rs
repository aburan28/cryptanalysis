//! # Symmetrised decomposition systems for Koblitz curves.
//!
//! The follow-through on `research/notes/index-calculus/RESEARCH_EXOTIC_COORDINATES.md`: the coordinate
//! search found that on a Koblitz curve the rational 2-torsion point
//! `T = (0, 1)` acts on the `x`-line as `x ↦ 1/x`, that the frame
//! `u = 1/(x + 1)` (defined over `F₂`, so the Frobenius survives) turns
//! that into `u ↦ u + 1`, and that the summation polynomial written in the
//! invariants `w = u² + u`, `s = Σu` has half the degree.  That was a
//! statement about polynomials.  This module turns it into decomposition
//! systems the existing oracles can solve, so the claim "smaller system"
//! can be tested against the claim that matters, "faster solve".
//!
//! ## The system
//!
//! Factor base `F_u = { P : u(P) ∈ V }` for a Frobenius-stable subspace
//! `V ∋ 1` (the divisor of `xⁿ − 1` must contain `x − 1`).  Choose a basis
//! `1, b₂, …, b_ℓ` of `V`.  Every `u ∈ V` is `ε + Σ_t c_t b_t`, and the
//! Artin–Schreier map `AS(v) = v² + v` is `F₂`-linear with kernel `{0, 1}`,
//! so `w = AS(u) = Σ_t c_t AS(b_t)` — the bit `ε` drops out.  For `m`
//! summands the unknowns are the `c_{i,t}` (`m(ℓ − 1)` bits) and one bit
//! `ε = Σ_i ε_i`; `w_i` is linear in them, and so is `s = Σ_i u_i + u_R`.
//! The symmetrised polynomial, interpolated and verified in
//! [`crate::cryptanalysis::coordinate_search`], is then Weil-restricted
//! exactly as the `x`-system is: `n` Boolean equations.
//!
//! ```text
//!   m = 2:  w₁ w₂ w_R + w₁ + w₂ + w_R + s = 0                (bilinear, s linear)
//!   m = 3:  the 18-term S₄ of degree 2 in each w, s linear  (Boolean degree 4)
//! ```
//!
//! A root gives each `w_i`, hence `u_i` up to `u_i ↦ u_i + 1` with the
//! parity fixed by `ε`, hence `x_i = 1/u_i + 1` up to sign.  The lifted
//! points sum to `R` or to `R + T`; both are relations over `F_u` since
//! `T ∈ F_u` (`u(T) = 1 ∈ V`), and the oracle reports which — but they
//! are the *same* projected relation, because the index-calculus rows are
//! multiplied by the cofactor and `[h]T = O`.  The `via T` count is a fact
//! about lifting, not a second relation.
//!
//! ## What is compared
//!
//! [`paired_bench`] runs, on the same curve and the same subspace `V`:
//!
//! - **x-chained**: the production system,
//!   [`crate::cryptanalysis::koblitz_groebner::build_decomposition_system`]
//!   on `F_x = {x(P) ∈ V}` — `S₃` for `m = 2`, chained `S₃` links with
//!   `(m − 2)·n` free intermediate unknowns for `m = 3`;
//! - **x-direct** (`m = 3`): the 24-term `S₄` in `x`, no chaining, Boolean
//!   degree 6 — separates "no chaining" from "symmetry";
//! - **sym**: the symmetrised system on `F_u`, Boolean degree 4.
//!
//! Both degrees are counted over the unknowns only, and are what `system_degree`
//! reports in the `deg` column: at `K₁/F₂⁹`, `m = 3` the arms print 9 vars /
//! deg 6 and 7 vars / deg 4.  The target is fixed when a decomposition is
//! attempted, so it is not an unknown; counting it as a variable gives 7 and 5
//! instead, which is the convention
//! `coordinate_search::boolean_degree` uses for the *polynomial* and what
//! `RESEARCH_EXOTIC_COORDINATES.md` §3.2's table reports.  The gap is 2 either
//! way; mixing the two reports it as 3.
//!
//! Every verdict is gated against exhaustive enumeration on its own base,
//! every returned relation is re-summed in the group, and timings are
//! reported separately for found and refuted targets, as the scaling
//! harness does.  The two bases differ as sets — same `V`, different
//! coordinate — so their found/refuted mixes differ too; the counts are
//! printed so nobody compares a median across regimes.
//!
//! ## Honest scope
//!
//! Toy `n ≤ 24` (the curve constructor's limit), `m ≤ 3`.  The
//! Kosters–Yeo trace row the SAT path adds to the `x`-system has no
//! linear analogue in `u`, so the SAT arms run without it on both sides.

use std::collections::HashMap;
use std::time::Instant;

use num_bigint::BigUint;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};

use crate::binary_ecc::curve::point_neg;
use crate::binary_ecc::{BinaryPoint, F2mElement};
use crate::cryptanalysis::ic_boundary::calibrate_word_xor;
use crate::cryptanalysis::koblitz_fast::{FastCurve, FastPoint};
use crate::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, f4_word_ops_thread, first_fall_degree,
    solve_boolean_system_filtered, split_rule_default, FieldStructure, SolveOptions, SolveStats,
    SolverEngine, SymElement, MAX_VARS,
};
use crate::cryptanalysis::koblitz_index_calculus::{
    all_factors_of_x_n_minus_1, build_explicit_frobenius_orbit_factor_base,
    build_frobenius_factor_base_from_divisor, enumerate_decompose, groebner_decompose, point_key,
    points_with_x, span_f2, subspace_basis_for_divisor, FactorBaseDomain, FrobeniusFactorBase,
    KoblitzCurve,
};
use crate::cryptanalysis::pq_groebner_f2::{F2BoolMono, F2BoolPoly};
use crate::cryptanalysis::sat::SolveResult;
use crate::cryptanalysis::semaev_sat::{encode_boolean_system_with, XorEncoding};

fn bits_of(e: &F2mElement) -> u64 {
    e.raw_bits().first().copied().unwrap_or(0)
}

fn from_bits(v: u64, n: u32) -> F2mElement {
    F2mElement::from_biguint(&BigUint::from(v), n)
}

// ── The frame ──────────────────────────────────────────────────────

/// `u = 1/(x + 1)`; `None` at `x = 1`, where `u = ∞`.
pub fn u_of_x(x: &F2mElement, kc: &KoblitzCurve) -> Option<F2mElement> {
    let d = x.add(&F2mElement::one(kc.n));
    d.flt_inverse(&kc.curve.irreducible)
}

/// `x = 1/u + 1`; `None` at `u = 0`, where `x = ∞`.
pub fn x_of_u(u: &F2mElement, kc: &KoblitzCurve) -> Option<F2mElement> {
    Some(
        u.flt_inverse(&kc.curve.irreducible)?
            .add(&F2mElement::one(kc.n)),
    )
}

/// `w = u² + u`, the Artin–Schreier invariant of `u ↦ u + 1`.
pub fn artin_schreier(u: &F2mElement, kc: &KoblitzCurve) -> F2mElement {
    u.square(&kc.curve.irreducible).add(u)
}

// ── Factor base in the u-frame ─────────────────────────────────────

/// `F_u = { P : u(P) ∈ V }` with its bases.
#[derive(Clone, Debug)]
pub struct SymmetrisedFactorBase {
    /// Basis of `V`; `v_basis[0] = 1`.
    pub v_basis: Vec<F2mElement>,
    /// `AS(v_basis[t])` for `t ≥ 1`: a basis of `AS(V)`, dimension `ℓ − 1`.
    pub w_basis: Vec<F2mElement>,
    /// `ℓ = dim V`.
    pub ell: usize,
    pub points: Vec<BinaryPoint>,
    pub index_of: HashMap<(BigUint, BigUint), usize>,
    /// `T = (0, 1)`.
    pub two_torsion: BinaryPoint,
    pub two_torsion_index: usize,
}

/// Indices into [`all_factors_of_x_n_minus_1`] of a divisor containing
/// `x − 1` whose root space has dimension as close as possible to
/// `target_dim` (ties to the smaller).  `None` if `x − 1` is not a listed
/// factor.
pub fn divisor_for_dimension(n: u32, target_dim: u32) -> Option<Vec<usize>> {
    let factors = all_factors_of_x_n_minus_1(n);
    let x1 = factors.iter().position(|&f| f == 0b11)?;
    let others: Vec<(usize, u32)> = factors
        .iter()
        .enumerate()
        .filter(|(i, _)| *i != x1)
        .map(|(i, &f)| (i, 63 - f.leading_zeros()))
        .collect();
    let mut best: Option<(u32, Vec<usize>)> = None;
    for mask in 0..(1u32 << others.len()) {
        let dim = 1 + others
            .iter()
            .enumerate()
            .filter(|(k, _)| (mask >> k) & 1 == 1)
            .map(|(_, &(_, d))| d)
            .sum::<u32>();
        if dim >= n {
            continue;
        }
        let dist = (dim as i64 - target_dim as i64).abs();
        let better = match &best {
            None => true,
            Some((bd, _)) => {
                let bdist = (*bd as i64 - target_dim as i64).abs();
                dist < bdist || (dist == bdist && dim < *bd)
            }
        };
        if better {
            let mut idx = vec![x1];
            idx.extend(
                others
                    .iter()
                    .enumerate()
                    .filter(|(k, _)| (mask >> k) & 1 == 1)
                    .map(|(_, &(i, _))| i),
            );
            best = Some((dim, idx));
        }
    }
    best.map(|(_, idx)| idx)
}

/// Build `F_u` from a divisor of `xⁿ − 1` (indices as in
/// [`all_factors_of_x_n_minus_1`]).  Returns `None` if `1 ∉ V`.
pub fn build_symmetrised_factor_base(
    kc: &KoblitzCurve,
    divisor_indices: &[usize],
) -> Option<SymmetrisedFactorBase> {
    let n = kc.n;
    let raw = subspace_basis_for_divisor(n, divisor_indices, &kc.curve.irreducible)?;
    let span = span_f2(&raw, n);
    let span_bits: std::collections::HashSet<u64> = span.iter().map(bits_of).collect();
    if !span_bits.contains(&1) {
        return None;
    }
    // Re-basis with 1 first: greedy independence over the F_2-span.
    let mut v_basis: Vec<F2mElement> = vec![F2mElement::one(n)];
    let mut current: std::collections::HashSet<u64> = [0u64, 1].into_iter().collect();
    for b in &raw {
        let bb = bits_of(b);
        if current.contains(&bb) {
            continue;
        }
        let added: Vec<u64> = current.iter().map(|&c| c ^ bb).collect();
        current.extend(added);
        v_basis.push(b.clone());
    }
    if v_basis.len() != raw.len() {
        return None;
    }
    // Points in the raw basis's span order, as before the explicit-basis
    // constructor existed, so indices into `points` do not move.
    finish_symmetrised_factor_base(kc, v_basis, span)
}

/// Build `F_u` over an explicit `F₂`-basis of `V` with `v_basis[0] = 1`.
///
/// `V` need not be Frobenius-stable: the symmetrised system uses only
/// `1 ∈ V`, which makes `AS` drop the parity bit.  A non-invariant `V`
/// has no `π`-orbits, so [`frobenius_view_of_symmetrised`] does not apply
/// to it — and on the prime degrees where `2` is primitive, ECC2K-130's
/// `n = 131` among them, a non-invariant `V` is the only kind with more
/// than one point (the invariant `V ∋ 1` are `F₂`, giving `F_u = {T}`, and
/// the whole field).  `None` if the basis is dependent or does not start
/// with `1`.
pub fn build_symmetrised_factor_base_from_basis(
    kc: &KoblitzCurve,
    v_basis: Vec<F2mElement>,
) -> Option<SymmetrisedFactorBase> {
    let n = kc.n;
    if v_basis.first().map(bits_of) != Some(1) {
        return None;
    }
    let span = span_f2(&v_basis, n);
    let span_bits: std::collections::HashSet<u64> = span.iter().map(bits_of).collect();
    if span_bits.len() != 1 << v_basis.len() {
        return None;
    }
    finish_symmetrised_factor_base(kc, v_basis, span)
}

fn finish_symmetrised_factor_base(
    kc: &KoblitzCurve,
    v_basis: Vec<F2mElement>,
    span: Vec<F2mElement>,
) -> Option<SymmetrisedFactorBase> {
    let n = kc.n;
    let ell = v_basis.len();
    let w_basis: Vec<F2mElement> = v_basis[1..].iter().map(|b| artin_schreier(b, kc)).collect();
    if span_f2(&w_basis, n).len() != 1 << (ell - 1) {
        return None;
    }
    let mut points = Vec::new();
    for u in &span {
        if u.is_zero() {
            continue;
        }
        let x = x_of_u(u, kc)?;
        points.extend(points_with_x(&kc.curve, &x));
    }
    let index_of: HashMap<(BigUint, BigUint), usize> = points
        .iter()
        .enumerate()
        .map(|(i, p)| (point_key(p), i))
        .collect();
    let two_torsion = points_with_x(&kc.curve, &F2mElement::zero(n))
        .into_iter()
        .next()?;
    let two_torsion_index = *index_of.get(&point_key(&two_torsion))?;
    Some(SymmetrisedFactorBase {
        v_basis,
        w_basis,
        ell,
        points,
        index_of,
        two_torsion,
        two_torsion_index,
    })
}

/// **The abscissae of `F_u`**, which are closed under the `2`-power
/// Frobenius.
///
/// `u = 1/(x + 1)` is defined over `F_2`, so it commutes with squaring:
/// `x_of_u(u²) = 1/u² + 1 = (1/u + 1)² = x_of_u(u)²`.  `V` is
/// Frobenius-stable by construction, so the image abscissa set is too —
/// which is what lets `F_u` carry the same `π`-orbit structure that the
/// `x`-frame factor base carries, and hence the same `n`-fold saving in
/// relation collection and `n²` in the matrix.
pub fn symmetrised_abscissae(kc: &KoblitzCurve, fb: &SymmetrisedFactorBase) -> Vec<F2mElement> {
    let mut out = Vec::with_capacity(1 << fb.ell);
    for u in span_f2(&fb.v_basis, kc.n) {
        if u.is_zero() {
            continue; // x = ∞
        }
        if let Some(x) = x_of_u(&u, kc) {
            out.push(x);
        }
    }
    out
}

/// **`F_u` as a [`FrobeniusFactorBase`]**, so the end-to-end index
/// calculus can collect relations over it.
///
/// [`SymmetrisedFactorBase`] carries the two bases the symmetrised
/// *system* needs (`V` and `AS(V)`) but none of the orbit structure the
/// *attack* needs: `π`-orbits, signed orbits, and the index maps that
/// become the relation matrix's columns.  Because the abscissa set is
/// Frobenius-closed ([`symmetrised_abscissae`]), the existing
/// orbit-walking constructor builds all of that over exactly the same
/// point set.
///
/// The two views therefore describe one factor base, and
/// [`symmetrised_index_map`] translates between their point orderings.
pub fn frobenius_view_of_symmetrised(
    kc: &KoblitzCurve,
    fb: &SymmetrisedFactorBase,
) -> Option<FrobeniusFactorBase> {
    build_explicit_frobenius_orbit_factor_base(kc, &symmetrised_abscissae(kc, fb))
}

/// Index translation from [`SymmetrisedFactorBase::points`] to
/// [`FrobeniusFactorBase::points`].
///
/// The oracle reports summands in the symmetrised base's ordering; the
/// relation rows are indexed by the Frobenius view's.  `None` if the two
/// point sets differ at all, which is the check that they are the same
/// factor base rather than two that merely look alike.
pub fn symmetrised_index_map(
    fb: &SymmetrisedFactorBase,
    view: &FrobeniusFactorBase,
) -> Option<Vec<usize>> {
    if fb.points.len() != view.points.len() {
        return None;
    }
    let where_in_view: HashMap<(BigUint, BigUint), usize> = view
        .points
        .iter()
        .enumerate()
        .map(|(i, p)| (point_key(p), i))
        .collect();
    fb.points
        .iter()
        .map(|p| where_in_view.get(&point_key(p)).copied())
        .collect()
}

impl SymmetrisedFactorBase {
    /// Sum of the indexed points.
    pub fn sum(&self, kc: &KoblitzCurve, idxs: &[usize]) -> BinaryPoint {
        idxs.iter().fold(BinaryPoint::Infinity, |acc, &i| {
            kc.add(&acc, &self.points[i])
        })
    }
}

/// Exhaustive decomposition over `F_u`: `Some((indices, used_t))` with
/// `Σ = R` (`used_t = false`) or `Σ = R + T` (`used_t = true`, and `T`'s
/// index appended so the returned list really sums to `R`).
pub fn enumerate_symmetrised(
    kc: &KoblitzCurve,
    fb: &SymmetrisedFactorBase,
    target: &BinaryPoint,
    m: usize,
) -> Option<(Vec<usize>, bool)> {
    fn rec(
        kc: &KoblitzCurve,
        fb: &SymmetrisedFactorBase,
        target: &BinaryPoint,
        m: usize,
        start: usize,
    ) -> Option<Vec<usize>> {
        if m == 1 {
            let idx = *fb.index_of.get(&point_key(target))?;
            return (idx >= start).then(|| vec![idx]);
        }
        for i in start..fb.points.len() {
            let rest = kc.add(target, &point_neg(&fb.points[i]));
            if let Some(mut tail) = rec(kc, fb, &rest, m - 1, i) {
                let mut out = vec![i];
                out.append(&mut tail);
                return Some(out);
            }
        }
        None
    }
    if let Some(v) = rec(kc, fb, target, m, 0) {
        return Some((v, false));
    }
    let shifted = kc.add(target, &fb.two_torsion);
    rec(kc, fb, &shifted, m, 0).map(|mut v| {
        v.push(fb.two_torsion_index);
        (v, true)
    })
}

// ── The polynomials ────────────────────────────────────────────────

/// Exponent vectors of the symmetrised summation polynomial over
/// `(w₁, …, w_m, w_R, s)`, all coefficients `1`.  Interpolated by
/// `coordinate_search` on a Koblitz curve; `F₂` coefficients, so valid
/// for every `n` and both `a`.  A test pins them to the interpolation.
pub fn symmetrised_terms(m: usize) -> Option<Vec<Vec<u32>>> {
    Some(match m {
        2 => vec![
            vec![1, 1, 1, 0],
            vec![1, 0, 0, 0],
            vec![0, 1, 0, 0],
            vec![0, 0, 1, 0],
            vec![0, 0, 0, 1],
        ],
        3 => vec![
            vec![2, 2, 2, 0, 0],
            vec![2, 2, 0, 2, 0],
            vec![2, 0, 2, 2, 0],
            vec![0, 2, 2, 2, 0],
            vec![2, 1, 1, 1, 0],
            vec![1, 2, 1, 1, 0],
            vec![1, 1, 2, 1, 0],
            vec![1, 1, 1, 2, 0],
            vec![1, 1, 1, 1, 1],
            vec![2, 0, 0, 0, 0],
            vec![0, 2, 0, 0, 0],
            vec![0, 0, 2, 0, 0],
            vec![0, 0, 0, 2, 0],
            vec![1, 0, 0, 0, 0],
            vec![0, 1, 0, 0, 0],
            vec![0, 0, 1, 0, 0],
            vec![0, 0, 0, 1, 0],
            vec![0, 0, 0, 0, 1],
        ],
        _ => return None,
    })
}

/// Exponent vectors of Semaev's `S_{m+1}` in `x` over `(x₁, …, x_m, x_R)`
/// for `b = 1`, all coefficients `1` (the constant term is `b`).
pub fn plain_terms(m: usize) -> Option<Vec<Vec<u32>>> {
    Some(match m {
        2 => vec![
            vec![2, 2, 0],
            vec![2, 0, 2],
            vec![0, 2, 2],
            vec![1, 1, 1],
            vec![0, 0, 0],
        ],
        3 => vec![
            vec![4, 4, 4, 0],
            vec![4, 4, 0, 4],
            vec![4, 0, 4, 4],
            vec![0, 4, 4, 4],
            vec![4, 2, 2, 2],
            vec![3, 3, 3, 1],
            vec![3, 3, 1, 3],
            vec![3, 1, 3, 3],
            vec![2, 4, 2, 2],
            vec![2, 2, 4, 2],
            vec![2, 2, 2, 4],
            vec![1, 3, 3, 3],
            vec![3, 1, 1, 1],
            vec![2, 2, 2, 0],
            vec![2, 2, 0, 2],
            vec![2, 0, 2, 2],
            vec![1, 3, 1, 1],
            vec![1, 1, 3, 1],
            vec![1, 1, 1, 3],
            vec![0, 2, 2, 2],
            vec![4, 0, 0, 0],
            vec![0, 4, 0, 0],
            vec![0, 0, 4, 0],
            vec![0, 0, 0, 4],
        ],
        _ => return None,
    })
}

/// `v^e` for a symbolic field element: `e = 2^k` is `k` linear squarings,
/// odd exponents multiply once more.
fn sym_pow(v: &SymElement, e: u32, st: &FieldStructure) -> SymElement {
    let mut result: Option<SymElement> = None;
    let mut base = v.clone();
    let mut e = e;
    while e > 0 {
        if e & 1 == 1 {
            result = Some(match result {
                None => base.clone(),
                Some(r) => r.mul(&base, st),
            });
        }
        e >>= 1;
        if e > 0 {
            base = base.square(st);
        }
    }
    result.expect("positive exponent")
}

/// Weil restriction of `Σ_terms Π_i vars[i]^{e_i} = 0` to `n` Boolean
/// equations.  Squares are linear and cost nothing; the Boolean degree of
/// a term is `Σ popcount(e_i)` over the non-constant variables.
pub fn sym_polynomial(
    vars: &[SymElement],
    terms: &[Vec<u32>],
    st: &FieldStructure,
) -> Vec<F2BoolPoly> {
    let n_vars = vars[0].coords[0].n_vars;
    let mut acc = SymElement::zero(st.n, n_vars);
    for term in terms {
        let mut prod: Option<SymElement> = None;
        for (i, &e) in term.iter().enumerate() {
            if e == 0 {
                continue;
            }
            let p = sym_pow(&vars[i], e, st);
            prod = Some(match prod {
                None => p,
                Some(q) => q.mul(&p, st),
            });
        }
        let t = prod.unwrap_or_else(|| SymElement::constant(&F2mElement::one(st.n), st.n, n_vars));
        acc = acc.add(&t);
    }
    acc.coords
}

// ── Systems ────────────────────────────────────────────────────────

/// A decomposition system plus what its roots mean.
#[derive(Clone, Debug)]
pub struct SymmetrisedSystem {
    pub equations: Vec<F2BoolPoly>,
    pub n_vars: usize,
    /// Bits per summand: `ℓ − 1`.
    pub ell_w: usize,
    pub m: usize,
    /// `u(R)`.
    pub u_r: F2mElement,
}

impl SymmetrisedSystem {
    /// The `u`-coordinate of summand `i` that a root gives, before the
    /// `ε_i` choice: `Σ_t c_{i,t} b_{t+1}`.
    pub fn summand_u0(
        &self,
        fb: &SymmetrisedFactorBase,
        root: u64,
        i: usize,
        n: u32,
    ) -> F2mElement {
        let mut acc = F2mElement::zero(n);
        for t in 0..self.ell_w {
            if (root >> (i * self.ell_w + t)) & 1 == 1 {
                acc = acc.add(&fb.v_basis[t + 1]);
            }
        }
        acc
    }
    /// The parity bit `ε = Σ ε_i`.
    pub fn parity(&self, root: u64) -> bool {
        (root >> (self.m * self.ell_w)) & 1 == 1
    }
}

/// Build the symmetrised system for target `R` and `m` summands.  `None`
/// if `m ∉ {2, 3}`, `u(R)` is `0` or `∞`, or the layout exceeds
/// [`MAX_VARS`].
pub fn build_symmetrised_system(
    kc: &KoblitzCurve,
    fb: &SymmetrisedFactorBase,
    target: &BinaryPoint,
    m: usize,
    st: &FieldStructure,
) -> Option<SymmetrisedSystem> {
    let terms = symmetrised_terms(m)?;
    let x_r = match target {
        BinaryPoint::Affine { x, .. } => x,
        BinaryPoint::Infinity => return None,
    };
    let u_r = u_of_x(x_r, kc)?;
    if u_r.is_zero() {
        return None;
    }
    let n = kc.n;
    let ell_w = fb.ell - 1;
    let n_vars = m * ell_w + 1;
    if n_vars > MAX_VARS {
        return None;
    }
    let eps = (m * ell_w) as u32;
    let mut vars: Vec<SymElement> = (0..m)
        .map(|i| SymElement::from_subspace_vars(&fb.w_basis, i * ell_w, n, n_vars))
        .collect();
    vars.push(SymElement::constant(&artin_schreier(&u_r, kc), n, n_vars));
    // s = ε + Σ_i Σ_t c_{i,t} b_{t+1} + u_R
    let mut s = SymElement::constant(&u_r, n, n_vars);
    for i in 0..m {
        s = s.add(&SymElement::from_subspace_vars(
            &fb.v_basis[1..],
            i * ell_w,
            n,
            n_vars,
        ));
    }
    let mut eps_el = SymElement::zero(n, n_vars);
    eps_el.coords[0] = F2BoolPoly::from_monos(vec![F2BoolMono::var(eps)], n_vars);
    s = s.add(&eps_el);
    vars.push(s);
    let equations = sym_polynomial(&vars, &terms, st);
    Some(SymmetrisedSystem {
        equations,
        n_vars,
        ell_w,
        m,
        u_r,
    })
}

/// The direct (unchained) `x`-system: Semaev's `S_{m+1}` in `x` with every
/// summand in the span of `basis`.  Same variable layout as the chained
/// system's first `m·ℓ` bits, so
/// [`crate::cryptanalysis::koblitz_groebner::DecompositionSystem::summand_x`]
/// logic applies.
pub fn build_direct_x_system(
    basis: &[F2mElement],
    x_r: &F2mElement,
    m: usize,
    st: &FieldStructure,
) -> Option<(Vec<F2BoolPoly>, usize)> {
    let terms = plain_terms(m)?;
    let ell = basis.len();
    let n_vars = m * ell;
    if n_vars > MAX_VARS {
        return None;
    }
    let mut vars: Vec<SymElement> = (0..m)
        .map(|i| SymElement::from_subspace_vars(basis, i * ell, st.n, n_vars))
        .collect();
    vars.push(SymElement::constant(x_r, st.n, n_vars));
    Some((sym_polynomial(&vars, &terms, st), n_vars))
}

fn subspace_x(basis: &[F2mElement], root: u64, i: usize, n: u32) -> F2mElement {
    let ell = basis.len();
    let mut acc = F2mElement::zero(n);
    for t in 0..ell {
        if (root >> (i * ell + t)) & 1 == 1 {
            acc = acc.add(&basis[t]);
        }
    }
    acc
}

// ── Lifting ────────────────────────────────────────────────────────

/// Walk sign choices over `points_with_x` for each abscissa; succeed when
/// the sum hits `target`.
fn lift_signs(
    kc: &KoblitzCurve,
    index_of: &HashMap<(BigUint, BigUint), usize>,
    points: &[BinaryPoint],
    xs: &[F2mElement],
    target: &BinaryPoint,
) -> Option<Vec<usize>> {
    fn walk(
        kc: &KoblitzCurve,
        index_of: &HashMap<(BigUint, BigUint), usize>,
        points: &[BinaryPoint],
        xs: &[F2mElement],
        depth: usize,
        acc: &BinaryPoint,
        chosen: &mut Vec<usize>,
        target: &BinaryPoint,
    ) -> bool {
        if depth == xs.len() {
            return acc == target;
        }
        for p in points_with_x(&kc.curve, &xs[depth]) {
            let Some(&idx) = index_of.get(&point_key(&p)) else {
                continue;
            };
            chosen.push(idx);
            let next = kc.add(acc, &points[idx]);
            if walk(kc, index_of, points, xs, depth + 1, &next, chosen, target) {
                return true;
            }
            chosen.pop();
        }
        false
    }
    let mut chosen = Vec::new();
    walk(
        kc,
        index_of,
        points,
        xs,
        0,
        &BinaryPoint::Infinity,
        &mut chosen,
        target,
    )
    .then_some(chosen)
}

/// Lift a root of the symmetrised system to factor-base points summing to
/// `R` (`used_t = false`) or to `R + T` (`used_t = true`, `T` appended).
pub fn lift_symmetrised_root(
    kc: &KoblitzCurve,
    fb: &SymmetrisedFactorBase,
    sys: &SymmetrisedSystem,
    root: u64,
    target: &BinaryPoint,
) -> Option<(Vec<usize>, bool)> {
    lift_symmetrised_root_accepting(kc, fb, sys, root, target, |_| true)
}

/// As [`lift_symmetrised_root`], returning the first lift of the root —
/// over every parity choice and every sign walk — whose index list
/// `accept` approves.  A root stands for a whole orbit of decompositions,
/// and a caller with a side condition (every summand in the image of an
/// endomorphism, say) needs to see all of them.
pub fn lift_symmetrised_root_accepting(
    kc: &KoblitzCurve,
    fb: &SymmetrisedFactorBase,
    sys: &SymmetrisedSystem,
    root: u64,
    target: &BinaryPoint,
    accept: impl Fn(&[usize]) -> bool,
) -> Option<(Vec<usize>, bool)> {
    let m = sys.m;
    let u0: Vec<F2mElement> = (0..m).map(|i| sys.summand_u0(fb, root, i, kc.n)).collect();
    let parity = sys.parity(root);
    let shifted = kc.add(target, &fb.two_torsion);
    for mask in 0..(1u32 << m) {
        if (mask.count_ones() % 2 == 1) != parity {
            continue;
        }
        let mut xs = Vec::with_capacity(m);
        let mut ok = true;
        for i in 0..m {
            let mut u = u0[i].clone();
            if (mask >> i) & 1 == 1 {
                u = u.add(&F2mElement::one(kc.n));
            }
            match x_of_u(&u, kc) {
                Some(x) => xs.push(x),
                None => {
                    ok = false;
                    break;
                }
            }
        }
        if !ok {
            continue;
        }
        for v in lift_signs_all(kc, &fb.index_of, &fb.points, &xs, target) {
            if accept(&v) {
                return Some((v, false));
            }
        }
        for mut v in lift_signs_all(kc, &fb.index_of, &fb.points, &xs, &shifted) {
            v.push(fb.two_torsion_index);
            if accept(&v) {
                return Some((v, true));
            }
        }
    }
    None
}

/// Every sign walk over `points_with_x` whose sum hits `target`.
fn lift_signs_all(
    kc: &KoblitzCurve,
    index_of: &HashMap<(BigUint, BigUint), usize>,
    points: &[BinaryPoint],
    xs: &[F2mElement],
    target: &BinaryPoint,
) -> Vec<Vec<usize>> {
    fn walk(
        kc: &KoblitzCurve,
        index_of: &HashMap<(BigUint, BigUint), usize>,
        points: &[BinaryPoint],
        xs: &[F2mElement],
        depth: usize,
        acc: &BinaryPoint,
        chosen: &mut Vec<usize>,
        target: &BinaryPoint,
        out: &mut Vec<Vec<usize>>,
    ) {
        if depth == xs.len() {
            if acc == target {
                out.push(chosen.clone());
            }
            return;
        }
        for p in points_with_x(&kc.curve, &xs[depth]) {
            let Some(&idx) = index_of.get(&point_key(&p)) else {
                continue;
            };
            chosen.push(idx);
            let next = kc.add(acc, &points[idx]);
            walk(
                kc,
                index_of,
                points,
                xs,
                depth + 1,
                &next,
                chosen,
                target,
                out,
            );
            chosen.pop();
        }
    }
    let mut out = Vec::new();
    walk(
        kc,
        index_of,
        points,
        xs,
        0,
        &BinaryPoint::Infinity,
        &mut Vec::new(),
        target,
        &mut out,
    );
    out
}

// ── Oracles ────────────────────────────────────────────────────────

/// Outcome of one oracle call.
#[derive(Clone, Debug)]
pub struct OracleOutcome {
    /// Factor-base indices summing to the target (with `T` appended when
    /// the root lifted to `R + T`).
    pub relation: Option<Vec<usize>>,
    /// The lifted relation went through `R + T`.
    pub used_t: bool,
    /// The solve completed: a `None` relation is a proof of absence.
    pub complete: bool,
    pub n_vars: usize,
    pub n_equations: usize,
    /// Boolean degree of the system.
    pub degree: u32,
    /// Engine-specific effort: F4 splits, or SAT conflicts.
    pub effort: u64,
    /// Highest Macaulay degree the F4 engine actually built a matrix at
    /// (0 for SAT arms, or when every matrix exceeded the size caps).
    pub built_degree: u32,
    /// Macaulay matrices refused for exceeding the size caps.
    pub oversize: usize,
}

fn system_degree(eqs: &[F2BoolPoly]) -> u32 {
    eqs.iter()
        .flat_map(|p| p.terms.iter())
        .map(|t| t.mask.count_ones())
        .max()
        .unwrap_or(0)
}

/// Symmetrised decomposition by matrix-F4 with splitting.
pub fn symmetrised_groebner_decompose(
    kc: &KoblitzCurve,
    fb: &SymmetrisedFactorBase,
    st: &FieldStructure,
    target: &BinaryPoint,
    m: usize,
    engine: SolverEngine,
    node_budget: usize,
) -> Option<OracleOutcome> {
    symmetrised_groebner_decompose_accepting(kc, fb, st, target, m, engine, node_budget, |_| true)
}

/// As [`symmetrised_groebner_decompose`], but a lifted decomposition is
/// returned only if `accept` approves its factor-base indices; otherwise
/// the search continues to the next root.
pub fn symmetrised_groebner_decompose_accepting(
    kc: &KoblitzCurve,
    fb: &SymmetrisedFactorBase,
    st: &FieldStructure,
    target: &BinaryPoint,
    m: usize,
    engine: SolverEngine,
    node_budget: usize,
    accept: impl Fn(&[usize]) -> bool,
) -> Option<OracleOutcome> {
    let sys = build_symmetrised_system(kc, fb, target, m, st)?;
    let opts = SolveOptions {
        engine,
        max_solutions: usize::MAX,
        node_budget,
        split_rule: split_rule_default(),
    };
    let mut found: Option<(Vec<usize>, bool)> = None;
    let (_, stats): (Vec<u64>, SolveStats) =
        solve_boolean_system_filtered(&sys.equations, sys.n_vars, &opts, |root| {
            match lift_symmetrised_root_accepting(kc, fb, &sys, root, target, &accept) {
                Some(r) => {
                    found = Some(r);
                    true
                }
                None => false,
            }
        });
    let used_t = found.as_ref().map(|r| r.1).unwrap_or(false);
    Some(OracleOutcome {
        relation: found.map(|r| r.0),
        used_t,
        complete: !stats.exhausted,
        n_vars: sys.n_vars,
        n_equations: sys.equations.len(),
        degree: system_degree(&sys.equations),
        effort: stats.splits as u64,
        built_degree: stats.max_degree_built,
        oversize: stats.oversize,
    })
}

/// Direct (unchained) `x`-system decomposition by matrix-F4 with
/// splitting, on the `x`-base `fb_x` (its subspace basis and points).
pub fn direct_x_groebner_decompose(
    kc: &KoblitzCurve,
    basis: &[F2mElement],
    points: &[BinaryPoint],
    index_of: &HashMap<(BigUint, BigUint), usize>,
    st: &FieldStructure,
    target: &BinaryPoint,
    m: usize,
    engine: SolverEngine,
    node_budget: usize,
) -> Option<OracleOutcome> {
    let x_r = match target {
        BinaryPoint::Affine { x, .. } => x.clone(),
        BinaryPoint::Infinity => return None,
    };
    let (equations, n_vars) = build_direct_x_system(basis, &x_r, m, st)?;
    let opts = SolveOptions {
        engine,
        max_solutions: usize::MAX,
        node_budget,
        split_rule: split_rule_default(),
    };
    let mut found: Option<Vec<usize>> = None;
    let (_, stats) = solve_boolean_system_filtered(&equations, n_vars, &opts, |root| {
        let xs: Vec<F2mElement> = (0..m).map(|i| subspace_x(basis, root, i, kc.n)).collect();
        match lift_signs(kc, index_of, points, &xs, target) {
            Some(v) => {
                found = Some(v);
                true
            }
            None => false,
        }
    });
    Some(OracleOutcome {
        relation: found,
        used_t: false,
        complete: !stats.exhausted,
        n_vars,
        n_equations: equations.len(),
        degree: system_degree(&equations),
        effort: stats.splits as u64,
        built_degree: stats.max_degree_built,
        oversize: stats.oversize,
    })
}

/// Generic CDCL loop over a Boolean system: enumerate models, lift each
/// with `lift`, block the ones that do not lift.
fn sat_loop(
    equations: &[F2BoolPoly],
    n_vars: usize,
    conflict_budget: u64,
    max_models: usize,
    mut lift: impl FnMut(u64) -> Option<(Vec<usize>, bool)>,
) -> OracleOutcome {
    let mut enc = encode_boolean_system_with(n_vars, equations, &[], XorEncoding::Native);
    enc.solver.conflict_budget = conflict_budget;
    let degree = system_degree(equations);
    let mut models = 0usize;
    let outcome = |relation: Option<(Vec<usize>, bool)>, complete: bool, effort: u64| {
        let used_t = relation.as_ref().map(|r| r.1).unwrap_or(false);
        OracleOutcome {
            relation: relation.map(|r| r.0),
            used_t,
            complete,
            n_vars,
            n_equations: equations.len(),
            degree,
            effort,
            built_degree: 0,
            oversize: 0,
        }
    };
    loop {
        if enc.trivially_unsat {
            return outcome(None, true, 0);
        }
        match enc.solver.solve() {
            SolveResult::Unsat => return outcome(None, true, enc.solver.conflicts()),
            SolveResult::Unknown => return outcome(None, false, enc.solver.conflicts()),
            SolveResult::Sat => {
                let root = enc.model_assignment();
                if !equations.iter().all(|e| e.eval(root) == 0) {
                    // A bad model is an encoding bug; fail closed.
                    return outcome(None, false, enc.solver.conflicts());
                }
                models += 1;
                if let Some(r) = lift(root) {
                    return outcome(Some(r), true, enc.solver.conflicts());
                }
                if models >= max_models {
                    return outcome(None, false, enc.solver.conflicts());
                }
                let clause: Vec<i32> = (0..n_vars)
                    .map(|i| {
                        let lit = (i + 1) as i32;
                        if (root >> i) & 1 == 1 {
                            -lit
                        } else {
                            lit
                        }
                    })
                    .collect();
                enc.solver.add_clause(clause);
            }
        }
    }
}

/// Symmetrised decomposition by CDCL SAT with native XOR rows.
pub fn symmetrised_sat_decompose(
    kc: &KoblitzCurve,
    fb: &SymmetrisedFactorBase,
    st: &FieldStructure,
    target: &BinaryPoint,
    m: usize,
    conflict_budget: u64,
    max_models: usize,
) -> Option<OracleOutcome> {
    let sys = build_symmetrised_system(kc, fb, target, m, st)?;
    Some(sat_loop(
        &sys.equations,
        sys.n_vars,
        conflict_budget,
        max_models,
        |root| lift_symmetrised_root(kc, fb, &sys, root, target),
    ))
}

/// The production `x`-system (chained for `m = 3`) by CDCL SAT, without
/// the trace row, so it is the same encoding as the symmetrised arm.
pub fn chained_x_sat_decompose(
    kc: &KoblitzCurve,
    basis: &[F2mElement],
    points: &[BinaryPoint],
    index_of: &HashMap<(BigUint, BigUint), usize>,
    st: &FieldStructure,
    target: &BinaryPoint,
    m: usize,
    conflict_budget: u64,
    max_models: usize,
) -> Option<OracleOutcome> {
    let x_r = match target {
        BinaryPoint::Affine { x, .. } => x.clone(),
        BinaryPoint::Infinity => return None,
    };
    let sys = build_decomposition_system(basis, &x_r, &kc.curve.b, m, st)?;
    Some(sat_loop(
        &sys.equations,
        sys.n_vars,
        conflict_budget,
        max_models,
        |root| {
            let xs: Vec<F2mElement> = (0..m)
                .map(|i| sys.summand_x(basis, root, i, kc.n))
                .collect();
            lift_signs(kc, index_of, points, &xs, target).map(|v| (v, false))
        },
    ))
}

// ── Paired benchmark ───────────────────────────────────────────────

/// One arm's aggregate over the targets.
#[derive(Clone, Debug)]
pub struct ArmRun {
    pub arm: &'static str,
    pub n_vars: usize,
    pub n_equations: usize,
    pub degree: u32,
    pub found: usize,
    pub refuted: usize,
    pub inconclusive: usize,
    /// Relations that lifted through `R + T` (the same projected relation
    /// as one through `R`; counted for information only).
    pub via_t: usize,
    pub median_found_ms: f64,
    pub median_refuted_ms: f64,
    pub total_ms: f64,
    pub median_effort: f64,
    /// Verdicts contradicting exhaustive enumeration on the arm's own
    /// base, plus relations that did not re-sum to the target.
    pub gate_failures: usize,
    /// First fall degree of the system at the first target, if computed.
    pub first_fall_degree: Option<u32>,
    /// Highest Macaulay degree the engine built a matrix at, over the
    /// instance's targets.  Below the requested cap it means the larger
    /// matrices exceeded the size caps and the engine fell back.
    pub built_degree: u32,
    /// Targets on which at least one Macaulay matrix was refused for size.
    pub oversize_targets: usize,
}

/// The paired comparison on one instance.
#[derive(Clone, Debug)]
pub struct PairedBench {
    pub a: u8,
    pub n: u32,
    pub ell: usize,
    pub m: usize,
    pub divisor: Vec<usize>,
    pub fb_x_size: usize,
    pub fb_u_size: usize,
    pub targets: usize,
    pub arms: Vec<ArmRun>,
}

/// Knobs for [`paired_bench`].
#[derive(Clone, Debug)]
pub struct PairedOptions {
    pub targets: usize,
    pub seed: u64,
    pub node_budget: usize,
    pub sat: bool,
    pub conflict_budget: u64,
    pub max_models: usize,
    /// Include the direct (unchained) `x`-`S₄` arm for `m = 3`.
    pub direct_x: bool,
    /// Compute first fall degrees up to this Macaulay degree (0 = skip).
    pub ffd_max_degree: u32,
    /// Draw targets from the prime-order subgroup (as index calculus
    /// does) rather than from the whole group.
    pub targets_in_subgroup: bool,
    /// Run the production `x`-chained arm.  At a raised Macaulay degree
    /// that arm costs hours on the larger fields, so a run that only
    /// needs the symmetrised cell can switch it off.
    pub chained_x: bool,
    /// Highest Macaulay degree the F4 engine builds before splitting.
    /// The symmetrised systems have degree 4 (`m = 3`), so at the
    /// default 3 they get no algebraic reduction at all before the
    /// first split; 4 or 5 is what a fair comparison needs.
    pub f4_max_degree: u32,
}

impl Default for PairedOptions {
    fn default() -> Self {
        Self {
            targets: 8,
            seed: 0x5EED,
            node_budget: 200_000,
            sat: true,
            conflict_budget: 2_000_000,
            max_models: 64,
            direct_x: true,
            ffd_max_degree: 4,
            targets_in_subgroup: true,
            chained_x: true,
            f4_max_degree: 3,
        }
    }
}

fn median(mut v: Vec<f64>) -> f64 {
    if v.is_empty() {
        return f64::NAN;
    }
    v.sort_by(|a, b| a.partial_cmp(b).unwrap());
    v[v.len() / 2]
}

struct Acc {
    arm: &'static str,
    n_vars: usize,
    n_eqs: usize,
    degree: u32,
    found: usize,
    refuted: usize,
    inconclusive: usize,
    via_t: usize,
    found_ms: Vec<f64>,
    refuted_ms: Vec<f64>,
    total_ms: f64,
    effort: Vec<f64>,
    gate_failures: usize,
    ffd: Option<u32>,
    built_degree: u32,
    oversize_targets: usize,
}

impl Acc {
    fn new(arm: &'static str) -> Self {
        Acc {
            arm,
            n_vars: 0,
            n_eqs: 0,
            degree: 0,
            found: 0,
            refuted: 0,
            inconclusive: 0,
            via_t: 0,
            found_ms: Vec::new(),
            refuted_ms: Vec::new(),
            total_ms: 0.0,
            effort: Vec::new(),
            gate_failures: 0,
            ffd: None,
            built_degree: 0,
            oversize_targets: 0,
        }
    }
    /// Record one outcome against the truth `(exists, target_sum_check)`.
    fn record(&mut self, o: &OracleOutcome, ms: f64, truth_exists: bool, sum_ok: Option<bool>) {
        self.n_vars = o.n_vars;
        self.n_eqs = o.n_equations;
        self.degree = o.degree;
        self.total_ms += ms;
        self.effort.push(o.effort as f64);
        self.built_degree = self.built_degree.max(o.built_degree);
        if o.oversize > 0 {
            self.oversize_targets += 1;
        }
        match (&o.relation, o.complete) {
            (Some(_), _) => {
                self.found += 1;
                self.found_ms.push(ms);
                if o.used_t {
                    self.via_t += 1;
                }
                if !truth_exists || sum_ok == Some(false) {
                    self.gate_failures += 1;
                }
            }
            (None, true) => {
                self.refuted += 1;
                self.refuted_ms.push(ms);
                if truth_exists {
                    self.gate_failures += 1;
                }
            }
            (None, false) => self.inconclusive += 1,
        }
    }
    fn finish(self) -> ArmRun {
        ArmRun {
            arm: self.arm,
            n_vars: self.n_vars,
            n_equations: self.n_eqs,
            degree: self.degree,
            found: self.found,
            refuted: self.refuted,
            inconclusive: self.inconclusive,
            via_t: self.via_t,
            median_found_ms: median(self.found_ms),
            median_refuted_ms: median(self.refuted_ms),
            total_ms: self.total_ms,
            median_effort: median(self.effort),
            gate_failures: self.gate_failures,
            first_fall_degree: self.ffd,
            built_degree: self.built_degree,
            oversize_targets: self.oversize_targets,
        }
    }
}

/// Run every arm on the same targets and gate every verdict.
pub fn paired_bench(a: u8, n: u32, m: usize, opts: &PairedOptions) -> Option<PairedBench> {
    let kc = KoblitzCurve::new(a, n)?;
    let target_dim = (n + 1).div_ceil(m as u32);
    let divisor = divisor_for_dimension(n, target_dim)?;
    let fb_u = build_symmetrised_factor_base(&kc, &divisor)?;
    let fb_x = build_frobenius_factor_base_from_divisor(&kc, &divisor)?;
    let index_x = fb_x.index_map();
    let st = FieldStructure::new(kc.n, &kc.curve.irreducible);

    let mut rng = StdRng::seed_from_u64(opts.seed);
    let g = kc.generator().clone();
    let r_u64 = kc
        .subgroup_order
        .to_u64_digits()
        .first()
        .copied()
        .unwrap_or(2)
        .max(2);
    let all_points: Vec<BinaryPoint> = if opts.targets_in_subgroup {
        Vec::new()
    } else {
        (0..(1u64 << n))
            .flat_map(|x| points_with_x(&kc.curve, &from_bits(x, n)))
            .collect()
    };
    let mut targets: Vec<BinaryPoint> = Vec::new();
    while targets.len() < opts.targets {
        let p = if opts.targets_in_subgroup {
            kc.mul(&g, &BigUint::from(rng.gen_range(1..r_u64)))
        } else {
            all_points[rng.gen_range(0..all_points.len())].clone()
        };
        // Both systems need u(R) finite and non-zero.
        if let BinaryPoint::Affine { x, .. } = &p {
            if *x == F2mElement::one(n) {
                continue;
            }
        } else {
            continue;
        }
        targets.push(p);
    }

    let mut x_chain = Acc::new("x-chained F4");
    let mut x_direct = Acc::new("x-direct F4");
    let mut sym = Acc::new("sym F4");
    let mut x_chain_sat = Acc::new("x-chained SAT");
    let mut sym_sat = Acc::new("sym SAT");
    let engine = SolverEngine::MatrixF4 {
        max_degree: opts.f4_max_degree,
    };

    for (ti, target) in targets.iter().enumerate() {
        // Truth on each base.
        let truth_x = enumerate_decompose(&kc, &fb_x, &index_x, target, m).is_some();
        let truth_u = enumerate_symmetrised(&kc, &fb_u, target, m).is_some();
        let t_plus = kc.add(target, &fb_u.two_torsion);
        let sum_check_u = |o: &OracleOutcome| -> Option<bool> {
            o.relation.as_ref().map(|idx| {
                let s = fb_u.sum(&kc, idx);
                if o.used_t {
                    // T appended: the list itself sums to R.
                    s == *target || s == t_plus
                } else {
                    s == *target
                }
            })
        };
        let sum_check_x = |idx: &Option<Vec<usize>>| -> Option<bool> {
            idx.as_ref().map(|v| {
                v.iter().fold(BinaryPoint::Infinity, |acc, &i| {
                    kc.add(&acc, &fb_x.points[i])
                }) == *target
            })
        };

        let x_r = match target {
            BinaryPoint::Affine { x, .. } => x.clone(),
            BinaryPoint::Infinity => unreachable!(),
        };

        // x-chained (production path).
        if opts.chained_x {
            let t0 = Instant::now();
            let (rel, stats) = groebner_decompose(
                &kc,
                &fb_x,
                &index_x,
                &st,
                target,
                m,
                engine,
                opts.node_budget,
            );
            let ms = t0.elapsed().as_secs_f64() * 1e3;
            let chained_sys =
                build_decomposition_system(&fb_x.subspace_basis, &x_r, &kc.curve.b, m, &st)?;
            let o = OracleOutcome {
                used_t: false,
                complete: !stats.exhausted,
                n_vars: chained_sys.n_vars,
                n_equations: chained_sys.equations.len(),
                degree: system_degree(&chained_sys.equations),
                effort: stats.splits as u64,
                built_degree: stats.max_degree_built,
                oversize: stats.oversize,
                relation: rel.clone(),
            };
            x_chain.record(&o, ms, truth_x, sum_check_x(&rel));
            if ti == 0 && opts.ffd_max_degree >= 2 {
                x_chain.ffd = first_fall_degree(
                    &chained_sys.equations,
                    chained_sys.n_vars,
                    opts.ffd_max_degree,
                )
                .0;
            }
        }

        // x-direct S₄.
        if m == 3 && opts.direct_x {
            let t0 = Instant::now();
            if let Some(o) = direct_x_groebner_decompose(
                &kc,
                &fb_x.subspace_basis,
                &fb_x.points,
                &index_x,
                &st,
                target,
                m,
                engine,
                opts.node_budget,
            ) {
                let ms = t0.elapsed().as_secs_f64() * 1e3;
                let ok = sum_check_x(&o.relation);
                x_direct.record(&o, ms, truth_x, ok);
                if ti == 0 && opts.ffd_max_degree >= 2 {
                    if let Some((eqs, nv)) =
                        build_direct_x_system(&fb_x.subspace_basis, &x_r, m, &st)
                    {
                        x_direct.ffd = first_fall_degree(&eqs, nv, opts.ffd_max_degree).0;
                    }
                }
            }
        }

        // sym F4.
        let t0 = Instant::now();
        if let Some(o) =
            symmetrised_groebner_decompose(&kc, &fb_u, &st, target, m, engine, opts.node_budget)
        {
            let ms = t0.elapsed().as_secs_f64() * 1e3;
            let ok = sum_check_u(&o);
            sym.record(&o, ms, truth_u, ok);
            if ti == 0 && opts.ffd_max_degree >= 2 {
                if let Some(s) = build_symmetrised_system(&kc, &fb_u, target, m, &st) {
                    sym.ffd = first_fall_degree(&s.equations, s.n_vars, opts.ffd_max_degree).0;
                }
            }
        }

        if opts.sat {
            if opts.chained_x {
                let t0 = Instant::now();
                if let Some(o) = chained_x_sat_decompose(
                    &kc,
                    &fb_x.subspace_basis,
                    &fb_x.points,
                    &index_x,
                    &st,
                    target,
                    m,
                    opts.conflict_budget,
                    opts.max_models,
                ) {
                    let ms = t0.elapsed().as_secs_f64() * 1e3;
                    let ok = sum_check_x(&o.relation);
                    x_chain_sat.record(&o, ms, truth_x, ok);
                }
            }
            let t0 = Instant::now();
            if let Some(o) = symmetrised_sat_decompose(
                &kc,
                &fb_u,
                &st,
                target,
                m,
                opts.conflict_budget,
                opts.max_models,
            ) {
                let ms = t0.elapsed().as_secs_f64() * 1e3;
                let ok = sum_check_u(&o);
                sym_sat.record(&o, ms, truth_u, ok);
            }
        }
    }

    let mut arms = Vec::new();
    if opts.chained_x {
        arms.push(x_chain.finish());
    }
    if m == 3 && opts.direct_x {
        arms.push(x_direct.finish());
    }
    arms.push(sym.finish());
    if opts.sat {
        if opts.chained_x {
            arms.push(x_chain_sat.finish());
        }
        arms.push(sym_sat.finish());
    }
    Some(PairedBench {
        a,
        n,
        ell: fb_u.ell,
        m,
        divisor,
        fb_x_size: fb_x.points.len(),
        fb_u_size: fb_u.points.len(),
        targets: targets.len(),
        arms,
    })
}

/// Text table of a paired benchmark.
pub fn format_paired(b: &PairedBench) -> String {
    use std::fmt::Write as _;
    let mut s = String::new();
    let _ = writeln!(
        s,
        "== K_{}/F_2^{}  m = {}  dim V = {}  |F_x| = {}  |F_u| = {}  targets = {}",
        b.a, b.n, b.m, b.ell, b.fb_x_size, b.fb_u_size, b.targets
    );
    let _ = writeln!(
        s,
        "   {:<14} {:>4} {:>4} {:>3} {:>5} {:>7} {:>6} {:>5} {:>12} {:>12} {:>9} {:>5} {:>4} {:>5}",
        "arm",
        "vars",
        "eqs",
        "deg",
        "found",
        "refuted",
        "inconc",
        "via T",
        "found ms",
        "refuted ms",
        "effort",
        "built",
        "ffd",
        "gate"
    );
    let fmt = |v: f64| {
        if v.is_nan() {
            "-".to_string()
        } else if v >= 100.0 {
            format!("{v:.0}")
        } else {
            format!("{v:.2}")
        }
    };
    for a in &b.arms {
        let _ = writeln!(
            s,
            "   {:<14} {:>4} {:>4} {:>3} {:>5} {:>7} {:>6} {:>5} {:>12} {:>12} {:>9} {:>5} {:>4} {:>5}",
            a.arm,
            a.n_vars,
            a.n_equations,
            a.degree,
            a.found,
            a.refuted,
            a.inconclusive,
            a.via_t,
            fmt(a.median_found_ms),
            fmt(a.median_refuted_ms),
            fmt(a.median_effort),
            match (a.built_degree, a.oversize_targets) {
                (0, _) => "-".to_string(),
                (d, 0) => d.to_string(),
                (d, k) => format!("{d}/{k}!"),
            },
            a.first_fall_degree
                .map(|d| d.to_string())
                .unwrap_or_else(|| "-".into()),
            if a.gate_failures == 0 {
                "ok".to_string()
            } else {
                format!("FAIL {}", a.gate_failures)
            }
        );
    }
    s
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::coordinate_search::{
        detect_symmetries, interpolate_relation, linearising_frame, CoordinateSystem, Curve, Frame,
        Rng64, SymmetryKind,
    };

    fn interpolated_terms(m: usize, symmetrised: bool) -> Vec<Vec<u32>> {
        let k = Curve::koblitz(1, 9);
        let pts = k.affine_points();
        let mut rng = Rng64::new(2);
        let cs = if symmetrised {
            let g = detect_symmetries(&k, &pts, &mut rng)
                .into_iter()
                .find_map(|s| match s.kind {
                    SymmetryKind::TwoTorsion(_) => s.mobius,
                    _ => None,
                })
                .unwrap();
            let frame = linearising_frame(&k.f, &g);
            CoordinateSystem::with_involution(&k.f, &frame, &g, false)
        } else {
            CoordinateSystem::plain(&Frame::weierstrass(), false)
        };
        let r = interpolate_relation(&k, &pts, &cs, m, &mut rng).unwrap();
        let mut terms: Vec<Vec<u32>> = r
            .poly
            .terms
            .iter()
            .map(|(e, c)| {
                assert_eq!(*c, 1, "coefficients must be in F_2");
                e.clone()
            })
            .collect();
        terms.sort();
        terms
    }

    /// **The two views must be one factor base.**
    ///
    /// `F_u` is only useful to the end-to-end attack if it carries the
    /// same `π`-orbit structure the `x`-frame base carries.  This
    /// checks the bridge end to end: the point sets coincide, the
    /// index map is a bijection, every orbit is a genuine `π`-cycle
    /// inside the base, the orbits partition it, and each orbit's
    /// length divides `n` — which is what makes the relation matrix
    /// `n` times narrower.
    #[test]
    fn frobenius_view_of_symmetrised_is_the_same_factor_base() {
        for (a, n, dim) in [(0u8, 9u32, 5u32), (1, 9, 5), (0, 15, 8), (1, 15, 5)] {
            let kc = KoblitzCurve::new(a, n).unwrap();
            let Some(div) = divisor_for_dimension(n, dim) else {
                continue;
            };
            let Some(fb) = build_symmetrised_factor_base(&kc, &div) else {
                continue;
            };
            let view = frobenius_view_of_symmetrised(&kc, &fb)
                .unwrap_or_else(|| panic!("a={a} n={n}: no Frobenius view"));

            // Same points, and the translation is a bijection.
            let map = symmetrised_index_map(&fb, &view)
                .unwrap_or_else(|| panic!("a={a} n={n}: point sets differ"));
            let mut seen = vec![false; view.points.len()];
            for &j in &map {
                assert!(!seen[j], "a={a} n={n}: index map is not injective");
                seen[j] = true;
            }
            assert!(
                seen.iter().all(|&b| b),
                "a={a} n={n}: index map misses a point"
            );

            // Every abscissa really is in V, read back through u.
            let v_span: std::collections::HashSet<u64> =
                span_f2(&fb.v_basis, n).iter().map(bits_of).collect();
            for p in &view.points {
                let BinaryPoint::Affine { x, .. } = p else {
                    panic!("a={a} n={n}: infinity in the factor base")
                };
                let u = u_of_x(x, &kc).expect("x = 1 is not an abscissa of F_u");
                assert!(v_span.contains(&bits_of(&u)), "a={a} n={n}: u(P) ∉ V");
            }

            // The orbits partition the base into genuine π-cycles.
            let mut covered = vec![false; view.points.len()];
            for orbit in &view.orbits {
                assert!(
                    (n as usize).is_multiple_of(orbit.len()),
                    "a={a} n={n}: orbit of length {} does not divide n",
                    orbit.len()
                );
                for (k, &i) in orbit.iter().enumerate() {
                    assert!(!covered[i], "a={a} n={n}: orbits overlap");
                    covered[i] = true;
                    // points[orbit[k+1]] must be π(points[orbit[k]]).
                    let next = view.points[orbit[(k + 1) % orbit.len()]].clone();
                    let img = match &view.points[i] {
                        BinaryPoint::Affine { x, y } => BinaryPoint::Affine {
                            x: x.square(&kc.curve.irreducible),
                            y: y.square(&kc.curve.irreducible),
                        },
                        BinaryPoint::Infinity => BinaryPoint::Infinity,
                    };
                    assert_eq!(img, next, "a={a} n={n}: orbit is not a π-cycle");
                }
            }
            assert!(
                covered.iter().all(|&b| b),
                "a={a} n={n}: orbits miss a point"
            );
        }
    }

    #[test]
    fn hardcoded_polynomials_match_the_interpolation() {
        for m in [2usize, 3] {
            let mut sym = symmetrised_terms(m).unwrap();
            sym.sort();
            assert_eq!(sym, interpolated_terms(m, true), "symmetrised m = {m}");
            let mut plain = plain_terms(m).unwrap();
            plain.sort();
            assert_eq!(plain, interpolated_terms(m, false), "plain m = {m}");
        }
    }

    #[test]
    fn u_factor_base_is_closed_under_t_and_frobenius() {
        for (a, n) in [(0u8, 9u32), (1, 9)] {
            let kc = KoblitzCurve::new(a, n).unwrap();
            let div = divisor_for_dimension(n, 5).unwrap();
            let fb = build_symmetrised_factor_base(&kc, &div).unwrap();
            assert_eq!(fb.v_basis[0], F2mElement::one(n));
            assert!(fb.index_of.contains_key(&point_key(&fb.two_torsion)));
            for p in &fb.points {
                let q = kc.add(p, &fb.two_torsion);
                if q != BinaryPoint::Infinity {
                    assert!(fb.index_of.contains_key(&point_key(&q)), "not T-closed");
                }
                assert!(
                    fb.index_of.contains_key(&point_key(&kc.frobenius(p))),
                    "not π-closed"
                );
                assert!(
                    fb.index_of.contains_key(&point_key(&point_neg(p))),
                    "not −-closed"
                );
            }
        }
    }

    #[test]
    fn divisor_without_x_minus_1_is_rejected() {
        let kc = KoblitzCurve::new(1, 9).unwrap();
        let factors = all_factors_of_x_n_minus_1(9);
        let other = (0..factors.len()).find(|&i| factors[i] != 0b11).unwrap();
        assert!(build_symmetrised_factor_base(&kc, &[other]).is_none());
    }

    #[test]
    fn direct_x_s3_matches_the_production_s3_system() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let div = divisor_for_dimension(9, 5).unwrap();
        let fb_x = build_frobenius_factor_base_from_divisor(&kc, &div).unwrap();
        let st = FieldStructure::new(9, &kc.curve.irreducible);
        let x_r = from_bits(0x1a3, 9);
        let (direct, nv) = build_direct_x_system(&fb_x.subspace_basis, &x_r, 2, &st).unwrap();
        let chained =
            build_decomposition_system(&fb_x.subspace_basis, &x_r, &kc.curve.b, 2, &st).unwrap();
        assert_eq!(nv, chained.n_vars);
        for root in 0..(1u64 << nv) {
            for (p, q) in direct.iter().zip(&chained.equations) {
                assert_eq!(p.eval(root), q.eval(root));
            }
        }
    }

    fn agreement(a: u8, n: u32, m: usize, sat: bool) {
        let opts = PairedOptions {
            targets: 6,
            seed: 7,
            node_budget: 50_000,
            sat,
            conflict_budget: 500_000,
            max_models: 32,
            direct_x: true,
            ffd_max_degree: 0,
            targets_in_subgroup: false,
            chained_x: true,
            f4_max_degree: 3,
        };
        let b = paired_bench(a, n, m, &opts).unwrap();
        for arm in &b.arms {
            assert_eq!(arm.gate_failures, 0, "{}\n{}", arm.arm, format_paired(&b));
            assert_eq!(arm.inconclusive, 0, "{}\n{}", arm.arm, format_paired(&b));
        }
    }

    #[test]
    fn symmetrised_oracles_agree_with_enumeration_m2() {
        agreement(0, 9, 2, true);
        agreement(1, 9, 2, true);
    }

    #[test]
    fn symmetrised_oracles_agree_with_enumeration_m3() {
        agreement(0, 9, 3, true);
    }

    #[test]
    fn symmetrised_system_has_the_predicted_shape() {
        let kc = KoblitzCurve::new(1, 15).unwrap();
        let st = FieldStructure::new(15, &kc.curve.irreducible);
        let div = divisor_for_dimension(15, 8).unwrap();
        let fb = build_symmetrised_factor_base(&kc, &div).unwrap();
        let target = kc.generator().clone();
        let s2 = build_symmetrised_system(&kc, &fb, &target, 2, &st).unwrap();
        assert_eq!(s2.n_vars, 2 * (fb.ell - 1) + 1);
        assert_eq!(s2.equations.len(), 15);
        assert_eq!(system_degree(&s2.equations), 2);
        let s3 = build_symmetrised_system(&kc, &fb, &target, 3, &st).unwrap();
        assert_eq!(s3.n_vars, 3 * (fb.ell - 1) + 1);
        assert_eq!(system_degree(&s3.equations), 4);
    }
}

// ── π − 1 transport on K_0 ─────────────────────────────────────────
//
// On `K_0` the rational points form `E(F_2) ≅ Z/4`, and the endomorphism
// `φ = π − 1` has exactly that kernel.  The second coordinate search
// (`research/notes/index-calculus/RESEARCH_EXOTIC_COORDINATES.md` §10) found that the 4-torsion
// quadruples the collapse factor and identified the mechanism as `φ`
// transporting the instance: a decomposition of `φ(R)` over `F_u` lifts to
// a decomposition of `R + K`, `K ∈ E(F_2)`, over `φ⁻¹(F_u)`.  This section
// implements that lift and measures what it is worth, which turns out to
// be a question about *columns*: the index-calculus rows are multiplied by
// the cofactor `h`, and `[h]` kills `E(F_2)`, so `R + K` and `R` are the
// same target and `P` and `P + K` the same unknown.  The identity
// `[h]φ(P) = [λ − 1][h]P` (on `⟨G⟩` the Frobenius is `[λ]`) makes every
// transported column a known multiple of an `F_u` column.  See
// `transport_bench` for the numbers and the research note §11 for the
// correction this forces on the earlier "targets per solve" accounting.

/// `φ(P) = π(P) − P`.
pub fn frobenius_minus_one(kc: &KoblitzCurve, p: &BinaryPoint) -> BinaryPoint {
    kc.add(&kc.frobenius(p), &point_neg(p))
}

/// Preimages of `φ` over the whole (toy) curve, and its kernel.
#[derive(Clone, Debug)]
pub struct PhiTable {
    pub preimages: HashMap<(BigUint, BigUint), Vec<BinaryPoint>>,
    pub kernel: Vec<BinaryPoint>,
    pub curve_points: usize,
}

/// Tabulate `φ` on every affine point of the curve (`n ≤ 24`).
pub fn phi_table(kc: &KoblitzCurve) -> PhiTable {
    let n = kc.n;
    let mut preimages: HashMap<(BigUint, BigUint), Vec<BinaryPoint>> = HashMap::new();
    let mut kernel = vec![BinaryPoint::Infinity];
    let mut count = 0usize;
    for x in 0..(1u64 << n) {
        for p in points_with_x(&kc.curve, &from_bits(x, n)) {
            count += 1;
            let q = frobenius_minus_one(kc, &p);
            if q == BinaryPoint::Infinity {
                kernel.push(p.clone());
            }
            preimages.entry(point_key(&q)).or_default().push(p);
        }
    }
    PhiTable {
        preimages,
        kernel,
        curve_points: count + 1,
    }
}

impl PhiTable {
    pub fn preimages_of(&self, q: &BinaryPoint) -> &[BinaryPoint] {
        self.preimages
            .get(&point_key(q))
            .map(|v| v.as_slice())
            .unwrap_or(&[])
    }
    pub fn in_kernel(&self, p: &BinaryPoint) -> bool {
        self.kernel.iter().any(|k| k == p)
    }
}

/// Canonical column of a point in the projected relation matrix: the
/// signed Frobenius orbit of `[h]P`, or `None` when `[h]P = O`.
pub fn projected_column(kc: &KoblitzCurve, p: &BinaryPoint) -> Option<(BigUint, BigUint)> {
    let hp = kc.mul(p, &kc.cofactor);
    if hp == BinaryPoint::Infinity {
        return None;
    }
    let mut best = point_key(&hp);
    let mut cur = hp;
    for _ in 0..kc.n {
        for cand in [cur.clone(), point_neg(&cur)] {
            let k = point_key(&cand);
            if k < best {
                best = k;
            }
        }
        cur = kc.frobenius(&cur);
    }
    Some(best)
}

/// Number of distinct projected columns a set of points occupies.
pub fn column_count(kc: &KoblitzCurve, points: &[BinaryPoint]) -> usize {
    points
        .iter()
        .filter_map(|p| projected_column(kc, p))
        .collect::<std::collections::HashSet<_>>()
        .len()
}

/// Outcome of one transported solve.
#[derive(Clone, Debug)]
pub struct TransportOutcome {
    /// Indices into `F_u` of the decomposition of `φ(R)` (with `T`
    /// appended when it went through `φ(R) + T`).
    pub on_fu: Option<Vec<usize>>,
    /// Lifted summands `P_i ∈ φ⁻¹(Q_i)` and the kernel element `K` with
    /// `Σ P_i = R + K`.
    pub lifted: Option<(Vec<BinaryPoint>, BinaryPoint)>,
    pub complete: bool,
    pub effort: u64,
}

/// Solve the symmetrised system for `φ(R)` and lift the result to a
/// decomposition of `R + K`, `K ∈ E(F_2)`.
pub fn transported_symmetrised_decompose(
    kc: &KoblitzCurve,
    fb: &SymmetrisedFactorBase,
    phi: &PhiTable,
    st: &FieldStructure,
    target: &BinaryPoint,
    m: usize,
    engine: SolverEngine,
    node_budget: usize,
) -> Option<TransportOutcome> {
    let phi_r = frobenius_minus_one(kc, target);
    if phi_r == BinaryPoint::Infinity {
        return None;
    }
    // Only decompositions whose every summand has a rational preimage
    // under φ lift; keep searching roots until one does.
    let in_image = |idxs: &[usize]| {
        idxs.iter()
            .all(|&i| !phi.preimages_of(&fb.points[i]).is_empty())
    };
    let o = symmetrised_groebner_decompose_accepting(
        kc,
        fb,
        st,
        &phi_r,
        m,
        engine,
        node_budget,
        in_image,
    )?;
    let lifted = o.relation.as_ref().and_then(|idxs| {
        let mut ps = Vec::with_capacity(idxs.len());
        for &i in idxs {
            let pre = phi.preimages_of(&fb.points[i]);
            ps.push(pre.first()?.clone());
        }
        let sum = ps
            .iter()
            .fold(BinaryPoint::Infinity, |acc, p| kc.add(&acc, p));
        let k = kc.add(&sum, &point_neg(target));
        phi.in_kernel(&k).then_some((ps, k))
    });
    Some(TransportOutcome {
        on_fu: o.relation,
        lifted,
        complete: o.complete,
        effort: o.effort,
    })
}

/// Does `target` decompose as a sum of `m` points of `points` (with
/// repetition)?  `m ∈ {2, 3}`, by pairs and a hash lookup.
pub fn decomposes_over(
    kc: &KoblitzCurve,
    points: &[BinaryPoint],
    target: &BinaryPoint,
    m: usize,
) -> bool {
    let index: HashMap<(BigUint, BigUint), usize> = points
        .iter()
        .enumerate()
        .map(|(i, p)| (point_key(p), i))
        .collect();
    match m {
        2 => (0..points.len()).any(|i| {
            let rest = kc.add(target, &point_neg(&points[i]));
            index.get(&point_key(&rest)).is_some_and(|&j| j >= i)
        }),
        3 => (0..points.len()).any(|i| {
            let r1 = kc.add(target, &point_neg(&points[i]));
            (i..points.len()).any(|j| {
                let rest = kc.add(&r1, &point_neg(&points[j]));
                index.get(&point_key(&rest)).is_some_and(|&k| k >= j)
            })
        }),
        _ => false,
    }
}

/// What the transport is worth, measured on one instance.
#[derive(Clone, Debug)]
pub struct TransportBench {
    pub n: u32,
    pub m: usize,
    pub ell: usize,
    pub fu_points: usize,
    pub fu_columns: usize,
    /// Points of `F_u` in the image of `φ` (index 4 in `E(F_{2^n})`), the
    /// only ones with rational preimages.
    pub fu_in_image: usize,
    pub fprime_points: usize,
    pub fprime_columns: usize,
    pub union_points: usize,
    pub union_columns: usize,
    pub targets: usize,
    /// Direct symmetrised solve on `R` found a decomposition.
    pub direct_found: usize,
    /// Transported solve on `φ(R)` found one and it lifted to `R + K`.
    pub transported_found: usize,
    /// Targets where the two verdicts differ (theory says never).
    pub disagreements: usize,
    /// Lifts whose `K` was not the identity: relations to `R + K ≠ R`.
    pub lifts_off_target: usize,
    /// Enumeration: `R` decomposes over `F_u`, over `φ⁻¹(F_u)`, over the union.
    pub enum_fu: usize,
    pub enum_fprime: usize,
    pub enum_union: usize,
    /// `[h]φ(P) = [λ−1][h]P` held for every `P ∈ φ⁻¹(F_u)`.
    pub column_identity_holds: bool,
    pub median_direct_ms: f64,
    pub median_transported_ms: f64,
}

/// Run the transport comparison on `K_0/F_{2^n}`.
pub fn transport_bench(
    n: u32,
    m: usize,
    targets: usize,
    seed: u64,
    node_budget: usize,
) -> Option<TransportBench> {
    let kc = KoblitzCurve::new(0, n)?;
    // On K_0 the u-frame base is a single point (T_2) for small subspaces:
    // grow the dimension from the m-matched target until it is not.
    let mut fb = None;
    for target_dim in (n + 1).div_ceil(m as u32)..n {
        let divisor = divisor_for_dimension(n, target_dim)?;
        let cand = build_symmetrised_factor_base(&kc, &divisor)?;
        if cand.points.len() >= 8 {
            fb = Some(cand);
            break;
        }
    }
    let fb = fb?;
    let st = FieldStructure::new(n, &kc.curve.irreducible);
    let phi = phi_table(&kc);
    if phi.kernel.len() != 4 {
        return None;
    }
    // F' = φ⁻¹(F_u)
    let fprime: Vec<BinaryPoint> = fb
        .points
        .iter()
        .flat_map(|q| phi.preimages_of(q).iter().cloned())
        .collect();
    let mut union: Vec<BinaryPoint> = fb.points.clone();
    {
        let have: std::collections::HashSet<_> = fb.points.iter().map(point_key).collect();
        for p in &fprime {
            if !have.contains(&point_key(p)) {
                union.push(p.clone());
            }
        }
    }
    // Column identity.
    let lam_minus_one =
        (&kc.lambda + &kc.subgroup_order - BigUint::from(1u32)) % &kc.subgroup_order;
    let column_identity_holds = fprime.iter().all(|p| {
        let q = frobenius_minus_one(&kc, p);
        let hp = kc.mul(p, &kc.cofactor);
        let hq = kc.mul(&q, &kc.cofactor);
        kc.mul(&hp, &lam_minus_one) == hq
    });

    let mut rng = StdRng::seed_from_u64(seed);
    let g = kc.generator().clone();
    let r_u64 = kc
        .subgroup_order
        .to_u64_digits()
        .first()
        .copied()
        .unwrap_or(2)
        .max(2);
    let engine = SolverEngine::default();
    let mut b = TransportBench {
        n,
        m,
        ell: fb.ell,
        fu_points: fb.points.len(),
        fu_columns: column_count(&kc, &fb.points),
        fu_in_image: fb
            .points
            .iter()
            .filter(|q| !phi.preimages_of(q).is_empty())
            .count(),
        fprime_points: fprime.len(),
        fprime_columns: column_count(&kc, &fprime),
        union_points: union.len(),
        union_columns: column_count(&kc, &union),
        targets: 0,
        direct_found: 0,
        transported_found: 0,
        disagreements: 0,
        lifts_off_target: 0,
        enum_fu: 0,
        enum_fprime: 0,
        enum_union: 0,
        column_identity_holds,
        median_direct_ms: f64::NAN,
        median_transported_ms: f64::NAN,
    };
    let mut direct_ms = Vec::new();
    let mut transported_ms = Vec::new();
    while b.targets < targets {
        let target = kc.mul(&g, &BigUint::from(rng.gen_range(1..r_u64)));
        let BinaryPoint::Affine { x, .. } = &target else {
            continue;
        };
        if *x == F2mElement::one(n) {
            continue;
        }
        let phi_r = frobenius_minus_one(&kc, &target);
        if let BinaryPoint::Affine { x, .. } = &phi_r {
            if *x == F2mElement::one(n) {
                continue;
            }
        } else {
            continue;
        }
        b.targets += 1;
        let t0 = Instant::now();
        let direct = symmetrised_groebner_decompose(&kc, &fb, &st, &target, m, engine, node_budget);
        direct_ms.push(t0.elapsed().as_secs_f64() * 1e3);
        let direct_found = direct.as_ref().is_some_and(|o| o.relation.is_some());
        let t0 = Instant::now();
        let tr =
            transported_symmetrised_decompose(&kc, &fb, &phi, &st, &target, m, engine, node_budget);
        transported_ms.push(t0.elapsed().as_secs_f64() * 1e3);
        let transported_found = tr.as_ref().is_some_and(|o| o.lifted.is_some());
        if let Some((_, k)) = tr.as_ref().and_then(|o| o.lifted.as_ref()) {
            if *k != BinaryPoint::Infinity {
                b.lifts_off_target += 1;
            }
        }
        b.direct_found += usize::from(direct_found);
        b.transported_found += usize::from(transported_found);
        if direct_found != transported_found {
            b.disagreements += 1;
        }
        b.enum_fu += usize::from(decomposes_over(&kc, &fb.points, &target, m));
        b.enum_fprime += usize::from(decomposes_over(&kc, &fprime, &target, m));
        b.enum_union += usize::from(decomposes_over(&kc, &union, &target, m));
    }
    b.median_direct_ms = median(direct_ms);
    b.median_transported_ms = median(transported_ms);
    Some(b)
}

pub fn format_transport(b: &TransportBench) -> String {
    use std::fmt::Write as _;
    let mut s = String::new();
    let _ = writeln!(
        s,
        "== K_0/F_2^{}  m = {}  dim V = {}   points/columns:  F_u {}/{} ({} in im φ)   φ⁻¹(F_u) {}/{}   union {}/{}",
        b.n, b.m, b.ell, b.fu_points, b.fu_columns, b.fu_in_image, b.fprime_points, b.fprime_columns, b.union_points, b.union_columns
    );
    let _ = writeln!(
        s,
        "   targets {}: direct found {}, transported found {}, disagreements {}, lifts landing on R + K with K ≠ O: {}",
        b.targets, b.direct_found, b.transported_found, b.disagreements, b.lifts_off_target
    );
    let _ = writeln!(
        s,
        "   enumeration: decomposes over F_u {}, over φ⁻¹(F_u) {}, over the union {}",
        b.enum_fu, b.enum_fprime, b.enum_union
    );
    let _ = writeln!(
        s,
        "   [h]φ(P) = [λ−1][h]P on every P ∈ φ⁻¹(F_u): {};  median ms direct {:.1}, transported {:.1}",
        b.column_identity_holds, b.median_direct_ms, b.median_transported_ms
    );
    s
}

#[cfg(test)]
mod transport_tests {
    use super::*;

    #[test]
    fn phi_kernel_is_the_rational_points_of_k0() {
        let kc = KoblitzCurve::new(0, 7).unwrap();
        let phi = phi_table(&kc);
        assert_eq!(phi.kernel.len(), 4);
        for k in &phi.kernel {
            assert_eq!(kc.frobenius(k), *k, "kernel points are F_2-rational");
        }
        // every affine point has exactly four affine preimages; O has the
        // three affine kernel points (O itself is not enumerated)
        for (k, v) in &phi.preimages {
            if *k == point_key(&BinaryPoint::Infinity) {
                assert_eq!(v.len(), 3);
            } else {
                assert_eq!(v.len(), 4);
            }
        }
    }

    #[test]
    fn transported_relation_lifts_and_projects_to_the_same_column_space() {
        // n = 15: dim-7 V is F_8 + F_32, so the base sits in E[h] and has
        // one projected column — degenerate for index calculus, but the
        // transport mechanics can be checked on it.
        let b = transport_bench(15, 2, 12, 3, 50_000).unwrap();
        assert!(b.column_identity_holds, "[h]φ(P) = [λ−1][h]P");
        assert_eq!(
            b.fprime_points,
            4 * b.fu_in_image,
            "four preimages per point in the image"
        );
        assert!(b.fu_in_image >= 1 && b.fu_in_image <= b.fu_points);
        assert!(b.union_points > b.fu_points, "{}", format_transport(&b));
        // A lift is accepted only when Σ P_i − R ∈ ker φ; the bench counts
        // lifts, so any lift that happened was in the kernel.
        assert!(b.transported_found <= b.targets);
    }

    #[test]
    fn transported_solve_is_phi_of_r_over_the_image_part() {
        // The transported verdict is "φ(R) decomposes over F_u ∩ im φ",
        // which is neither implied by nor implies the direct verdict
        // "R decomposes over F_u".  Check the implication that does hold:
        // a lifted relation is a decomposition of R + K over φ⁻¹(F_u).
        let kc = KoblitzCurve::new(0, 15).unwrap();
        let divisor = divisor_for_dimension(15, 7).unwrap();
        let fb = build_symmetrised_factor_base(&kc, &divisor).unwrap();
        let st = FieldStructure::new(15, &kc.curve.irreducible);
        let phi = phi_table(&kc);
        // Targets built to decompose over φ⁻¹(F_u): R = P₁ + P₂ with P_i
        // preimages of image points of F_u.  Every one must lift.
        let fprime: Vec<BinaryPoint> = fb
            .points
            .iter()
            .flat_map(|q| phi.preimages_of(q).iter().cloned())
            .collect();
        assert!(fprime.len() >= 8);
        let mut lifted = 0;
        let mut tried = 0;
        for i in 0..fprime.len().min(12) {
            let p1 = &fprime[i];
            let p2 = &fprime[(i * 7 + 3) % fprime.len()];
            let target = kc.add(p1, p2);
            let phi_r = frobenius_minus_one(&kc, &target);
            let bad = |p: &BinaryPoint| {
                matches!(p, BinaryPoint::Affine { x, .. } if *x == F2mElement::one(15))
                    || *p == BinaryPoint::Infinity
            };
            if bad(&target) || bad(&phi_r) {
                continue;
            }
            tried += 1;
            let o = transported_symmetrised_decompose(
                &kc,
                &fb,
                &phi,
                &st,
                &target,
                2,
                SolverEngine::default(),
                50_000,
            )
            .unwrap();
            let (ps, kk) = o
                .lifted
                .expect("a constructed decomposition must be found and lifted");
            lifted += 1;
            assert!(phi.in_kernel(&kk));
            for p in &ps {
                let q = frobenius_minus_one(&kc, p);
                assert!(fb.index_of.contains_key(&point_key(&q)), "φ(P_i) ∈ F_u");
            }
            let sum = ps
                .iter()
                .fold(BinaryPoint::Infinity, |acc, p| kc.add(&acc, p));
            assert_eq!(sum, kc.add(&target, &kk));
        }
        assert!(tried >= 4 && lifted == tried, "{lifted}/{tried} lifted");
    }
}

// ── X4′: both frames on one non-invariant `V ∋ 1` ──────────────────
//
// `research/notes/ecc2k130/RESEARCH_ECC2K130_ROUTE_TARGETS.md` §X4′.  On a
// prime degree where 2 is primitive — ECC2K-130's `n = 131`, and the E1
// rungs 13 and 19 — the only Frobenius-stable `V ∋ 1` are `F₂` and the
// field, so both frames must use a non-invariant `V` and both sit on the
// floor `Λ = m`.  What is left is the per-target cost of each oracle, which
// [`subspace_gate_bench`] measures on one shared `V` against the enumeration
// E1's product law charges.

/// A uniformly random `l`-dimensional subspace of `F_{2^n}` that contains
/// `1` and is **not** Frobenius-stable, as a basis with `1` first.
pub fn random_subspace_containing_one(
    kc: &KoblitzCurve,
    l: usize,
    rng: &mut StdRng,
) -> Vec<F2mElement> {
    let n = kc.n;
    assert!(l >= 2 && (l as u32) < n && n < 64, "need 2 ≤ l < n < 64");
    loop {
        let mut basis = vec![F2mElement::one(n)];
        let mut span: std::collections::HashSet<u64> = [0u64, 1].into_iter().collect();
        while basis.len() < l {
            let v = rng.gen_range(2..(1u64 << n));
            if span.contains(&v) {
                continue;
            }
            let added: Vec<u64> = span.iter().map(|&c| c ^ v).collect();
            span.extend(added);
            basis.push(from_bits(v, n));
        }
        let stable = basis
            .iter()
            .all(|b| span.contains(&bits_of(&b.square(&kc.curve.irreducible))));
        if !stable {
            return basis;
        }
    }
}

/// `F_x = { P : x(P) ∈ V }` over a basis of a **non-invariant** `V`, in the
/// shape the `x`-frame oracles take ([`groebner_decompose`],
/// [`enumerate_decompose`] read only the basis and the points).  With no
/// `π`-orbits every point is its own orbit and `±P` its signed orbit, so the
/// base carries `≈ |F|/2` unknowns, not `|F|/2n`.
pub fn plain_subspace_factor_base(
    kc: &KoblitzCurve,
    basis: &[F2mElement],
) -> Option<FrobeniusFactorBase> {
    let n = kc.n;
    let subspace = span_f2(basis, n);
    if subspace.len() != 1 << basis.len() {
        return None;
    }
    let mut points = Vec::new();
    let mut signed_orbits = Vec::new();
    let mut signed_orbit_of = Vec::new();
    for x in &subspace {
        let lifts = points_with_x(&kc.curve, x);
        let o = signed_orbits.len();
        let mut orbit = Vec::new();
        for (k, p) in lifts.into_iter().enumerate() {
            orbit.push(points.len());
            signed_orbit_of.push((o, 0u32, k == 1));
            points.push(p);
        }
        if !orbit.is_empty() {
            signed_orbits.push(orbit);
        }
    }
    let orbits: Vec<Vec<usize>> = (0..points.len()).map(|i| vec![i]).collect();
    let orbit_of: Vec<(usize, u32)> = (0..points.len()).map(|i| (i, 0)).collect();
    Some(FrobeniusFactorBase {
        domain: FactorBaseDomain::LinearSubspace,
        ell: basis.len() as u32,
        f_j: 0,
        linearised_exponents: Vec::new(),
        subspace,
        subspace_basis: basis.to_vec(),
        points,
        orbits,
        orbit_of,
        signed_orbits,
        signed_orbit_of,
    })
}

/// Exhaustive `m = 3` enumeration of one target over `points`, the way E1's
/// product law prices it: every unordered pair `{i ≤ j}` is one step, one
/// single-word curve addition `(R − P_i) − P_j` and one packed lookup in the
/// base.  Returns `(steps to the first decomposition, decompositions)`,
/// counting each multiset once.
fn enumerate_pairs(
    fc: &FastCurve,
    points: &[FastPoint],
    index_of: &HashMap<u64, usize>,
    target: FastPoint,
) -> (Option<u64>, u64) {
    let mut steps = 0u64;
    let mut first = None;
    let mut found = 0u64;
    for i in 0..points.len() {
        let a = fc.add(target, fc.neg(points[i]));
        for (j, &p) in points.iter().enumerate().skip(i) {
            steps += 1;
            let b = fc.add(a, fc.neg(p));
            if let Some(&k) = index_of.get(&b.pack()) {
                if first.is_none() {
                    first = Some(steps);
                }
                if k >= j {
                    found += 1;
                }
            }
        }
    }
    (first, found)
}

/// Wall time of one single-word curve addition on this host — the
/// group-addition equivalent (GAE) every other cost is converted into.
fn measure_ns_per_add(fc: &FastCurve, points: &[FastPoint], reps: usize) -> f64 {
    let mut acc = points[0];
    let t0 = Instant::now();
    for k in 0..reps {
        acc = fc.add(acc, points[k % points.len()]);
    }
    let ns = t0.elapsed().as_nanos() as f64 / reps as f64;
    std::hint::black_box(acc);
    ns
}

/// One target under one oracle.
#[derive(Clone, Debug, serde::Serialize)]
pub struct GateTarget {
    /// `found`, `refuted` or `budget` (the node budget ran out).
    pub verdict: &'static str,
    /// Word XORs charged to this thread by the solve: elimination and
    /// specialisation, not the matrix build or the substitutions.
    pub word_xors: u64,
    pub splits: usize,
    pub ms: f64,
    /// Verdict agrees with exhaustive enumeration on the arm's own base, and
    /// a returned relation re-sums to the target.
    pub gate_ok: bool,
}

/// One oracle at one Macaulay cap on every target.
#[derive(Clone, Debug, serde::Serialize)]
pub struct GateArm {
    pub arm: &'static str,
    pub cap: u32,
    pub n_vars: usize,
    /// The engine builds only the top-degree Macaulay matrix at each node
    /// (its default at `24` unknowns and above, `KIC_F4_MAX_DEGREE_ONLY`
    /// unset) rather than every degree from the system's own up to the cap.
    pub top_degree_only: bool,
    pub degree: u32,
    pub found: usize,
    pub refuted: usize,
    pub budget: usize,
    pub gate_failures: usize,
    /// Mean over every target, budget-limited ones at what they spent.
    pub mean_word_xors: f64,
    pub median_found_word_xors: f64,
    pub median_refuted_word_xors: f64,
    pub mean_splits: f64,
    pub mean_ms: f64,
    pub built_degree: u32,
    pub oversize_targets: usize,
    pub targets: Vec<GateTarget>,
}

/// Enumeration on one base: the reference the product law charges.
#[derive(Clone, Debug, serde::Serialize)]
pub struct GateEnumeration {
    pub base: &'static str,
    pub points: usize,
    /// Steps per target of the full enumeration, `|F|(|F| + 1)/2`.
    pub full_steps: u64,
    /// Mean steps to the first decomposition over the decomposable targets.
    pub mean_first_hit_steps: f64,
    /// Steps of the first-hit rule over every target: to the first
    /// decomposition, or the full enumeration where there is none.
    pub first_hit_steps_total: u64,
    pub decomposable: usize,
    pub mean_decompositions: f64,
    /// Decompositions over every target, each multiset once: what the full
    /// rule harvests.
    pub decompositions_total: u64,
    /// Wall time per step of the full enumeration on this host: one curve
    /// addition and one lookup.
    pub ns_per_step: f64,
    /// The same step in group-addition equivalents, `ns_per_step / ns_per_add`.
    pub gae_per_step: f64,
}

/// The X4′ gate on one rung.
#[derive(Clone, Debug, serde::Serialize)]
pub struct GateBench {
    pub a: u8,
    pub n: u32,
    pub l: usize,
    pub m: usize,
    pub seed: u64,
    /// `V`'s basis as integers, `1` first.
    pub v_basis: Vec<u64>,
    pub v_frobenius_stable: bool,
    pub targets: usize,
    pub node_budget: usize,
    pub engine: String,
    pub enumeration: Vec<GateEnumeration>,
    /// Wall time of one raw 64-bit word XOR on this host, measured as the
    /// boundary ledger measures it ([`calibrate_word_xor`]) — the price the
    /// repository puts on the `word XORs` unit.
    pub ns_per_word_xor: f64,
    /// Wall time per counted word XOR inside the solver's own dense
    /// elimination: what the implementation actually pays, for comparison.
    /// Practicality only; the conversion uses the raw price.
    pub ns_per_word_xor_in_rref: f64,
    /// Wall time of one single-word curve addition on this host.
    pub ns_per_add: f64,
    /// The conversion of the oracles' unit into group-addition equivalents,
    /// `ns_per_word_xor / ns_per_add`, measured with the run.
    pub gae_per_word_xor: f64,
    pub arms: Vec<GateArm>,
}

/// Knobs for [`subspace_gate_bench`].
#[derive(Clone, Debug)]
pub struct GateOptions {
    pub targets: usize,
    pub seed: u64,
    pub node_budget: usize,
    /// `x`-chained Macaulay caps; the symmetrised arm runs at each plus one.
    pub x_caps: Vec<u32>,
}

/// Wall time per counted word XOR inside the solver's own dense elimination
/// of random `size × size` bit matrices.
pub fn measure_ns_per_word_xor_in_rref(size: usize, reps: usize, seed: u64) -> f64 {
    let mut rng = StdRng::seed_from_u64(seed);
    let words = size.div_ceil(64);
    let (mut ns, mut ops) = (0u128, 0u64);
    for _ in 0..reps {
        let mut m: Vec<Vec<u64>> = (0..size)
            .map(|_| (0..words).map(|_| rng.gen::<u64>()).collect())
            .collect();
        let w0 = f4_word_ops_thread();
        let t0 = Instant::now();
        crate::cryptanalysis::koblitz_groebner::rref_f2(&mut m, size);
        ns += t0.elapsed().as_nanos();
        ops += f4_word_ops_thread() - w0;
    }
    ns as f64 / ops.max(1) as f64
}

/// **The X4′ gate on one rung**: the `x`-chained oracle over `F_x` and the
/// symmetrised oracle over `F_u`, both on one random non-invariant `V ∋ 1`
/// of dimension `l`, on the same targets, each verdict gated against
/// exhaustive enumeration on its own base, costs in word XORs per target.
/// The engine is the production default, `InheritedF4`, whose split rule
/// `Auto` resolves to `HighestFree`; the symmetrised arm runs at each
/// `x`-cap plus one (the fair diagonal of the exotic-coordinates note §17).
pub fn subspace_gate_bench(a: u8, n: u32, l: usize, opts: &GateOptions) -> Option<GateBench> {
    let m = 3usize;
    let kc = KoblitzCurve::new(a, n)?;
    let mut rng = StdRng::seed_from_u64(opts.seed ^ ((n as u64) << 32));
    let v = random_subspace_containing_one(&kc, l, &mut rng);
    let fb_u = build_symmetrised_factor_base_from_basis(&kc, v.clone())?;
    let fb_x = plain_subspace_factor_base(&kc, &v)?;
    let index_x = fb_x.index_map();
    let st = FieldStructure::new(kc.n, &kc.curve.irreducible);

    let g = kc.generator().clone();
    let r_u64 = kc
        .subgroup_order
        .to_u64_digits()
        .first()
        .copied()
        .unwrap_or(2)
        .max(2);
    let mut targets: Vec<BinaryPoint> = Vec::new();
    while targets.len() < opts.targets {
        let p = kc.mul(&g, &BigUint::from(rng.gen_range(1..r_u64)));
        // Both systems need u(R) finite and non-zero.
        match &p {
            BinaryPoint::Affine { x, .. } if *x != F2mElement::one(n) => targets.push(p),
            _ => {}
        }
    }

    // The reference: full enumeration on each base, timed, and the truth.
    let fc = FastCurve::new(&kc.curve)?;
    let fast = |pts: &[BinaryPoint]| -> (Vec<FastPoint>, HashMap<u64, usize>) {
        let v: Vec<FastPoint> = pts.iter().map(|p| fc.lift(p)).collect();
        let idx = v.iter().enumerate().map(|(i, p)| (p.pack(), i)).collect();
        (v, idx)
    };
    let fast_targets: Vec<FastPoint> = targets.iter().map(|t| fc.lift(t)).collect();
    let ns_per_add = measure_ns_per_add(&fc, &fast(&fb_x.points).0, 2_000_000);
    let mut enumeration = Vec::new();
    let mut truth: Vec<(bool, bool)> = vec![(false, false); targets.len()];
    for (base, pts) in [("x", &fb_x.points), ("u", &fb_u.points)] {
        let (points, index) = fast(pts);
        let t0 = Instant::now();
        let full = (points.len() * (points.len() + 1) / 2) as u64;
        let (mut first, mut dec, mut decomposable) = (Vec::new(), 0u64, 0usize);
        let mut first_total = 0u64;
        for (ti, &t) in fast_targets.iter().enumerate() {
            let (f, d) = enumerate_pairs(&fc, &points, &index, t);
            first_total += f.unwrap_or(full);
            if let Some(s) = f {
                first.push(s as f64);
                decomposable += 1;
            }
            dec += d;
            if base == "x" {
                truth[ti].0 = f.is_some();
            } else {
                truth[ti].1 = f.is_some();
            }
        }
        let ns_per_step = t0.elapsed().as_nanos() as f64 / (full * targets.len() as u64) as f64;
        enumeration.push(GateEnumeration {
            base,
            points: points.len(),
            full_steps: full,
            mean_first_hit_steps: if first.is_empty() {
                f64::NAN
            } else {
                first.iter().sum::<f64>() / first.len() as f64
            },
            first_hit_steps_total: first_total,
            decomposable,
            mean_decompositions: dec as f64 / targets.len() as f64,
            decompositions_total: dec,
            ns_per_step,
            gae_per_step: ns_per_step / ns_per_add,
        });
    }
    // Cross-check the pair enumeration against the library's.
    for (ti, t) in targets.iter().enumerate() {
        assert_eq!(
            truth[ti].0,
            enumerate_decompose(&kc, &fb_x, &index_x, t, m).is_some()
        );
        assert_eq!(
            truth[ti].1,
            enumerate_symmetrised(&kc, &fb_u, t, m).is_some()
        );
    }

    let mut arms = Vec::new();
    for &cap in &opts.x_caps {
        for (arm, sym) in [("x-chained", false), ("symmetrised", true)] {
            let arm_cap = if sym { cap + 1 } else { cap };
            let engine = SolverEngine::InheritedF4 {
                max_degree: arm_cap,
            };
            let mut rows = Vec::new();
            let (mut n_vars, mut degree, mut built, mut oversize) = (0, 0, 0, 0);
            for (ti, target) in targets.iter().enumerate() {
                let w0 = f4_word_ops_thread();
                let t0 = Instant::now();
                let (relation_ok, found, complete, splits) = if sym {
                    let o = symmetrised_groebner_decompose(
                        &kc,
                        &fb_u,
                        &st,
                        target,
                        m,
                        engine,
                        opts.node_budget,
                    )?;
                    n_vars = o.n_vars;
                    degree = o.degree;
                    built = built.max(o.built_degree);
                    oversize += usize::from(o.oversize > 0);
                    let ok = o.relation.as_ref().map(|idx| {
                        let s = fb_u.sum(&kc, idx);
                        s == *target || (o.used_t && s == kc.add(target, &fb_u.two_torsion))
                    });
                    (ok, o.relation.is_some(), o.complete, o.effort as usize)
                } else {
                    let (rel, stats) = groebner_decompose(
                        &kc,
                        &fb_x,
                        &index_x,
                        &st,
                        target,
                        m,
                        engine,
                        opts.node_budget,
                    );
                    let x_r = match target {
                        BinaryPoint::Affine { x, .. } => x.clone(),
                        BinaryPoint::Infinity => unreachable!(),
                    };
                    let sys = build_decomposition_system(
                        &fb_x.subspace_basis,
                        &x_r,
                        &kc.curve.b,
                        m,
                        &st,
                    )?;
                    n_vars = sys.n_vars;
                    degree = system_degree(&sys.equations);
                    built = built.max(stats.max_degree_built);
                    oversize += usize::from(stats.oversize > 0);
                    let ok = rel.as_ref().map(|idx| {
                        idx.iter().fold(BinaryPoint::Infinity, |acc, &i| {
                            kc.add(&acc, &fb_x.points[i])
                        }) == *target
                    });
                    (ok, rel.is_some(), !stats.exhausted, stats.splits)
                };
                let ms = t0.elapsed().as_secs_f64() * 1e3;
                let word_xors = f4_word_ops_thread() - w0;
                let exists = if sym { truth[ti].1 } else { truth[ti].0 };
                let (verdict, gate_ok) = match (found, complete) {
                    (true, _) => ("found", exists && relation_ok == Some(true)),
                    (false, true) => ("refuted", !exists),
                    (false, false) => ("budget", true),
                };
                rows.push(GateTarget {
                    verdict,
                    word_xors,
                    splits,
                    ms,
                    gate_ok,
                });
            }
            let by = |v: &str| -> Vec<f64> {
                rows.iter()
                    .filter(|r| r.verdict == v)
                    .map(|r| r.word_xors as f64)
                    .collect()
            };
            let k = rows.len() as f64;
            arms.push(GateArm {
                arm,
                cap: arm_cap,
                n_vars,
                top_degree_only: match std::env::var("KIC_F4_MAX_DEGREE_ONLY").as_deref() {
                    Ok("1") => true,
                    Ok("0") => false,
                    _ => n_vars >= 24,
                },
                degree,
                found: rows.iter().filter(|r| r.verdict == "found").count(),
                refuted: rows.iter().filter(|r| r.verdict == "refuted").count(),
                budget: rows.iter().filter(|r| r.verdict == "budget").count(),
                gate_failures: rows.iter().filter(|r| !r.gate_ok).count(),
                mean_word_xors: rows.iter().map(|r| r.word_xors as f64).sum::<f64>() / k,
                median_found_word_xors: median(by("found")),
                median_refuted_word_xors: median(by("refuted")),
                mean_splits: rows.iter().map(|r| r.splits as f64).sum::<f64>() / k,
                mean_ms: rows.iter().map(|r| r.ms).sum::<f64>() / k,
                built_degree: built,
                oversize_targets: oversize,
                targets: rows,
            });
        }
    }

    let ns_per_word_xor = calibrate_word_xor();
    let ns_per_word_xor_in_rref = measure_ns_per_word_xor_in_rref(1024, 8, opts.seed);
    Some(GateBench {
        a,
        n,
        l,
        m,
        seed: opts.seed,
        v_basis: v.iter().map(bits_of).collect(),
        v_frobenius_stable: false,
        targets: targets.len(),
        node_budget: opts.node_budget,
        engine: "InheritedF4, split rule Auto (HighestFree)".into(),
        enumeration,
        ns_per_word_xor,
        ns_per_word_xor_in_rref,
        ns_per_add,
        gae_per_word_xor: ns_per_word_xor / ns_per_add,
        arms,
    })
}

#[cfg(test)]
mod gate_tests {
    use super::*;

    #[test]
    fn non_invariant_bases_exist_where_invariant_ones_degenerate() {
        // n = 13: 2 is primitive, so the only invariant V ∋ 1 of dimension
        // below n is F₂, and F_u over it is {T} alone.
        let kc = KoblitzCurve::new(0, 13).unwrap();
        let one = build_symmetrised_factor_base_from_basis(&kc, vec![F2mElement::one(13)]).unwrap();
        assert_eq!(one.points.len(), 1);
        assert_eq!(one.points[0], one.two_torsion);
        let mut rng = StdRng::seed_from_u64(7);
        let v = random_subspace_containing_one(&kc, 6, &mut rng);
        let fb_u = build_symmetrised_factor_base_from_basis(&kc, v.clone()).unwrap();
        let fb_x = plain_subspace_factor_base(&kc, &v).unwrap();
        assert!(fb_u.points.len() > 16 && fb_x.points.len() > 16);
        // F_u is closed under translation by T, since u ↦ u + 1 and 1 ∈ V —
        // except T itself, whose translate O is u = 0, which F_u leaves out.
        for p in fb_u.points.iter().filter(|p| **p != fb_u.two_torsion) {
            let q = kc.add(p, &fb_u.two_torsion);
            assert!(fb_u.index_of.contains_key(&point_key(&q)));
        }
        let signed: usize = fb_x.signed_orbits.iter().map(Vec::len).sum();
        assert_eq!(signed, fb_x.points.len());
    }

    #[test]
    fn pair_enumeration_over_r_covers_the_decompositions_through_t() {
        // The symmetrised oracle also returns 3-sums to R + T.  F_u is closed
        // under + T away from T itself and contains T, so R and R + T are
        // 3-sums over F_u together, and enumerating R alone decides the
        // question the oracle answers.  Checked on every subgroup target
        // drawn, and against the library's two-pass enumeration.
        for (n, l, count) in [(13u32, 6usize, 300), (15, 6, 300), (19, 8, 100)] {
            let kc = KoblitzCurve::new(0, n).unwrap();
            let mut rng = StdRng::seed_from_u64(0xA7 ^ n as u64);
            let v = random_subspace_containing_one(&kc, l, &mut rng);
            let fb = build_symmetrised_factor_base_from_basis(&kc, v).unwrap();
            let fc = FastCurve::new(&kc.curve).unwrap();
            let pts: Vec<FastPoint> = fb.points.iter().map(|p| fc.lift(p)).collect();
            let idx: HashMap<u64, usize> =
                pts.iter().enumerate().map(|(i, p)| (p.pack(), i)).collect();
            let t2 = fc.lift(&fb.two_torsion);
            let g = kc.generator().clone();
            let r = kc.subgroup_order.to_u64_digits()[0];
            let (mut checked, mut decomposable) = (0, 0);
            while checked < count {
                let t = kc.mul(&g, &BigUint::from(rng.gen_range(1..r)));
                if !matches!(&t, BinaryPoint::Affine { x, .. } if *x != F2mElement::one(n)) {
                    continue;
                }
                let ft = fc.lift(&t);
                let over_r = enumerate_pairs(&fc, &pts, &idx, ft).0.is_some();
                let over_rt = enumerate_pairs(&fc, &pts, &idx, fc.add(ft, t2)).0.is_some();
                assert_eq!(over_r, over_rt, "n = {n}, target {t:?}");
                assert_eq!(over_r, enumerate_symmetrised(&kc, &fb, &t, 3).is_some());
                decomposable += usize::from(over_r);
                checked += 1;
            }
            assert!(
                decomposable > count / 10 && decomposable < count,
                "n = {n}: {decomposable}/{count}"
            );
        }
    }

    #[test]
    fn gate_bench_agrees_with_enumeration_and_counts_its_work() {
        let opts = GateOptions {
            targets: 4,
            seed: 11,
            node_budget: 20_000,
            x_caps: vec![3],
        };
        let b = subspace_gate_bench(0, 13, 6, &opts).unwrap();
        assert_eq!(b.arms.len(), 2);
        for arm in &b.arms {
            assert_eq!(arm.gate_failures, 0, "{arm:?}");
            assert_eq!(arm.found + arm.refuted + arm.budget, 4);
            assert!(arm.mean_word_xors > 0.0, "{arm:?}");
        }
        assert!(b.gae_per_word_xor > 0.0 && b.enumeration.iter().all(|e| e.gae_per_step > 0.5));
    }
}

// ── X5′: the symmetrised `S₃` chained at `m = 4` ───────────────────
//
// `research/notes/ecc2k130/RESEARCH_ECC2K130_ROUTE_TARGETS.md` §X5′.  Three
// symmetrised `S₃` links through two intermediate points,
//
//   P₁ + P₂ + Q₁,   Q₁ + P₃ + Q₂,   Q₂ + P₄ + R,
//
// each of Boolean degree 3, the degree of the `x`-chained links H1 measured.
// `AS` is `F₂`-linear, so `w_Q = AS(u_Q)` is linear in `u_Q`'s free bits, and
// `AS(u + 1) = AS(u)` lets the parity bits fold: `U₁ = u(Q₁) + ε₁ + ε₂` and
// `U₂ = u(Q₂) + ε₁ + ε₂ + ε₃` leave `ε = Σ εᵢ` on the last link alone.
// Layout: the four summands' `ℓ − 1` bits, then `ε`, then `U₁`, then `U₂` —
// so [`SymmetrisedSystem::summand_u0`] and [`SymmetrisedSystem::parity`] read
// a root as they do at `m = 4`, and the four-summand lift applies unchanged.

/// Artin–Schreier `u² + u` in a field given by its modulus alone.
fn artin_schreier_in(u: &F2mElement, irr: &crate::binary_ecc::IrreduciblePoly) -> F2mElement {
    u.square(irr).add(u)
}

/// A uniformly random `l`-dimensional `V ∋ 1` of `F_{2^n}` that is not
/// Frobenius-stable, in a field given by its modulus: the curve-free form of
/// [`random_subspace_containing_one`], for measurements that need only the
/// field.
pub fn random_subspace_containing_one_in(
    n: u32,
    irr: &crate::binary_ecc::IrreduciblePoly,
    l: usize,
    rng: &mut StdRng,
) -> Vec<F2mElement> {
    assert!(l >= 2 && (l as u32) < n && n < 64, "need 2 ≤ l < n < 64");
    loop {
        let mut basis = vec![F2mElement::one(n)];
        let mut span: std::collections::HashSet<u64> = [0u64, 1].into_iter().collect();
        while basis.len() < l {
            let v = rng.gen_range(2..(1u64 << n));
            if span.contains(&v) {
                continue;
            }
            let added: Vec<u64> = span.iter().map(|&c| c ^ v).collect();
            span.extend(added);
            basis.push(from_bits(v, n));
        }
        if !basis
            .iter()
            .all(|b| span.contains(&bits_of(&b.square(irr))))
        {
            return basis;
        }
    }
}

/// **The symmetrised `S₃` chained at `m = 4`** for a target abscissa `x_R`,
/// over `V = span(v_basis)` with `v_basis[0] = 1`: `3n` equations of Boolean
/// degree 3 in `4(ℓ − 1) + 1 + 2n` unknowns.  `None` if `u(R)` is `0` or
/// `∞`, or the layout exceeds [`MAX_VARS`].
pub fn build_chained_symmetrised_system(
    v_basis: &[F2mElement],
    irr: &crate::binary_ecc::IrreduciblePoly,
    x_r: &F2mElement,
    st: &FieldStructure,
) -> Option<SymmetrisedSystem> {
    let n = st.n;
    if v_basis.first().map(bits_of) != Some(1) {
        return None;
    }
    let u_r = x_r.add(&F2mElement::one(n)).flt_inverse(irr)?;
    if u_r.is_zero() {
        return None;
    }
    let terms = symmetrised_terms(2)?;
    let ell_w = v_basis.len() - 1;
    let n_vars = 4 * ell_w + 1 + 2 * n as usize;
    if n_vars > MAX_VARS {
        return None;
    }
    let eps = 4 * ell_w;
    let (off1, off2) = (eps + 1, eps + 1 + n as usize);
    let w_basis: Vec<F2mElement> = v_basis[1..]
        .iter()
        .map(|b| artin_schreier_in(b, irr))
        .collect();
    let unit: Vec<F2mElement> = (0..n)
        .map(|k| F2mElement::from_bit_positions(&[k], n))
        .collect();
    let as_unit: Vec<F2mElement> = unit.iter().map(|e| artin_schreier_in(e, irr)).collect();
    let w: Vec<SymElement> = (0..4)
        .map(|i| SymElement::from_subspace_vars(&w_basis, i * ell_w, n, n_vars))
        .collect();
    let u: Vec<SymElement> = (0..4)
        .map(|i| SymElement::from_subspace_vars(&v_basis[1..], i * ell_w, n, n_vars))
        .collect();
    let u_q1 = SymElement::from_free_vars(off1, n, n_vars);
    let u_q2 = SymElement::from_free_vars(off2, n, n_vars);
    let w_q1 = SymElement::from_subspace_vars(&as_unit, off1, n, n_vars);
    let w_q2 = SymElement::from_subspace_vars(&as_unit, off2, n, n_vars);
    let w_r = SymElement::constant(&artin_schreier_in(&u_r, irr), n, n_vars);
    let mut eps_el = SymElement::zero(n, n_vars);
    eps_el.coords[0] = F2BoolPoly::from_monos(vec![F2BoolMono::var(eps as u32)], n_vars);
    let s1 = u[0].add(&u[1]).add(&u_q1);
    let s2 = u_q1.add(&u[2]).add(&u_q2);
    let s3 = u_q2
        .add(&u[3])
        .add(&SymElement::constant(&u_r, n, n_vars))
        .add(&eps_el);
    let mut equations = sym_polynomial(&[w[0].clone(), w[1].clone(), w_q1.clone(), s1], &terms, st);
    equations.extend(sym_polynomial(
        &[w_q1, w[2].clone(), w_q2.clone(), s2],
        &terms,
        st,
    ));
    equations.extend(sym_polynomial(&[w_q2, w[3].clone(), w_r, s3], &terms, st));
    Some(SymmetrisedSystem {
        equations,
        n_vars,
        ell_w,
        m: 4,
        u_r,
    })
}

/// The chained symmetrised oracle at `m = 4`: solve, then lift each root
/// through the four-summand lift, gated by `accept`.
pub fn chained_symmetrised_groebner_decompose(
    kc: &KoblitzCurve,
    fb: &SymmetrisedFactorBase,
    st: &FieldStructure,
    target: &BinaryPoint,
    engine: SolverEngine,
    node_budget: usize,
) -> Option<OracleOutcome> {
    let x_r = match target {
        BinaryPoint::Affine { x, .. } => x,
        BinaryPoint::Infinity => return None,
    };
    let sys = build_chained_symmetrised_system(&fb.v_basis, &kc.curve.irreducible, x_r, st)?;
    let opts = SolveOptions {
        engine,
        max_solutions: usize::MAX,
        node_budget,
        split_rule: split_rule_default(),
    };
    let mut found: Option<(Vec<usize>, bool)> = None;
    let (_, stats): (Vec<u64>, SolveStats) =
        solve_boolean_system_filtered(&sys.equations, sys.n_vars, &opts, |root| {
            match lift_symmetrised_root_accepting(kc, fb, &sys, root, target, |_| true) {
                Some(r) => {
                    found = Some(r);
                    true
                }
                None => false,
            }
        });
    let used_t = found.as_ref().map(|r| r.1).unwrap_or(false);
    Some(OracleOutcome {
        relation: found.map(|r| r.0),
        used_t,
        complete: !stats.exhausted,
        n_vars: sys.n_vars,
        n_equations: sys.equations.len(),
        degree: system_degree(&sys.equations),
        effort: stats.splits as u64,
        built_degree: stats.max_degree_built,
        oversize: stats.oversize,
    })
}

/// Fall-degree statistics of one system family over its draws.
#[derive(Clone, Debug, serde::Serialize)]
pub struct FallCell {
    pub arm: &'static str,
    pub n_vars: usize,
    pub n_eqs: usize,
    pub degree: u32,
    /// First fall degree per draw; `None` is no fall up to the highest
    /// degree profiled.
    pub falls: Vec<Option<u32>>,
    /// Highest Macaulay degree profiled per draw: below `d_max` means the
    /// matrix exceeded the size caps there and the draw is censored.
    pub profiled_to: Vec<u32>,
    pub fall_min: Option<u32>,
    pub fall_max: Option<u32>,
    pub no_fall: usize,
    pub censored: usize,
    /// Mean rank deficit (rows − rank) of the Macaulay matrix at `D = 2`, `3`.
    pub mean_deficit: Vec<(u32, f64)>,
    pub ms: f64,
}

/// One X5′ rung: both arms on one `V`, the same target abscissae.
#[derive(Clone, Debug, serde::Serialize)]
pub struct X5Rung {
    pub n: u32,
    pub ell: usize,
    pub v_basis: Vec<u64>,
    pub v_frobenius_stable: bool,
    pub draws: usize,
    pub d_max: u32,
    pub seed: u64,
    pub arms: Vec<FallCell>,
}

fn fall_cell(
    arm: &'static str,
    systems: &[(Vec<F2BoolPoly>, usize)],
    d_max: u32,
    ms: f64,
) -> FallCell {
    let mut falls = Vec::new();
    let mut profiled_to = Vec::new();
    let mut deficits: Vec<(u32, Vec<f64>)> = (2..=3).map(|d| (d, Vec::new())).collect();
    for (eqs, n_vars) in systems {
        let (fall, profiles) = first_fall_degree(eqs, *n_vars, d_max);
        falls.push(fall);
        profiled_to.push(profiles.iter().map(|p| p.degree).max().unwrap_or(0));
        for (d, acc) in deficits.iter_mut() {
            if let Some(p) = profiles.iter().find(|p| p.degree == *d) {
                acc.push((p.rows - p.rank) as f64);
            }
        }
    }
    let seen: Vec<u32> = falls.iter().flatten().copied().collect();
    let censored = falls
        .iter()
        .zip(&profiled_to)
        .filter(|(f, &top)| f.is_none() && top < d_max)
        .count();
    let (n_vars, n_eqs, degree) = systems
        .first()
        .map(|(e, v)| (*v, e.len(), system_degree(e)))
        .unwrap_or((0, 0, 0));
    FallCell {
        arm,
        n_vars,
        n_eqs,
        degree,
        fall_min: seen.iter().copied().min(),
        fall_max: seen.iter().copied().max(),
        no_fall: falls.iter().filter(|f| f.is_none()).count(),
        censored,
        mean_deficit: deficits
            .into_iter()
            .map(|(d, v)| {
                (
                    d,
                    if v.is_empty() {
                        f64::NAN
                    } else {
                        v.iter().sum::<f64>() / v.len() as f64
                    },
                )
            })
            .collect(),
        falls,
        profiled_to,
        ms,
    }
}

/// **One X5′ rung**: the symmetrised chain and the `x`-chained `m = 4`
/// system on one `V`, over `draws` uniform target abscissae (`u(R)` finite
/// and non-zero, `b = 1`, no curve), first fall degree to `d_max`.  `V` is
/// random and non-invariant unless `invariant_divisor` names a divisor of
/// `xⁿ − 1` (indices as in [`all_factors_of_x_n_minus_1`]) — the cross-check.
pub fn x5_fall_rung(
    n: u32,
    ell: usize,
    draws: usize,
    d_max: u32,
    seed: u64,
    invariant_divisor: Option<&[usize]>,
) -> Option<X5Rung> {
    use crate::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;
    let irr = find_irreducible_sparse(n)?;
    let st = FieldStructure::new(n, &irr);
    let mut rng = StdRng::seed_from_u64(seed ^ ((n as u64) << 32));
    let (v, stable) = match invariant_divisor {
        None => (
            random_subspace_containing_one_in(n, &irr, ell, &mut rng),
            false,
        ),
        Some(idx) => {
            let raw = subspace_basis_for_divisor(n, idx, &irr)?;
            let span = span_f2(&raw, n);
            if !span.iter().any(|e| bits_of(e) == 1) {
                return None;
            }
            // Re-basis with 1 first.
            let mut basis = vec![F2mElement::one(n)];
            let mut cur: std::collections::HashSet<u64> = [0u64, 1].into_iter().collect();
            for b in &raw {
                let bb = bits_of(b);
                if !cur.contains(&bb) {
                    let added: Vec<u64> = cur.iter().map(|&c| c ^ bb).collect();
                    cur.extend(added);
                    basis.push(b.clone());
                }
            }
            (basis, true)
        }
    };
    let b = F2mElement::one(n);
    let mut xs = Vec::new();
    while xs.len() < draws {
        let x = from_bits(rng.gen_range(0..(1u64 << n)), n);
        if x.is_zero() || x == F2mElement::one(n) {
            continue; // u(R) must be finite and non-zero
        }
        xs.push(x);
    }
    let t0 = Instant::now();
    let sym: Vec<(Vec<F2BoolPoly>, usize)> = xs
        .iter()
        .map(|x| {
            build_chained_symmetrised_system(&v, &irr, x, &st).map(|s| (s.equations, s.n_vars))
        })
        .collect::<Option<_>>()?;
    let sym_cell = {
        let mut c = fall_cell("symmetrised chain", &sym, d_max, 0.0);
        c.ms = t0.elapsed().as_secs_f64() * 1e3;
        c
    };
    let t1 = Instant::now();
    let xch: Vec<(Vec<F2BoolPoly>, usize)> = xs
        .iter()
        .map(|x| build_decomposition_system(&v, x, &b, 4, &st).map(|s| (s.equations, s.n_vars)))
        .collect::<Option<_>>()?;
    let x_cell = {
        let mut c = fall_cell("x-chained", &xch, d_max, 0.0);
        c.ms = t1.elapsed().as_secs_f64() * 1e3;
        c
    };
    Some(X5Rung {
        n,
        ell: v.len(),
        v_basis: v.iter().map(bits_of).collect(),
        v_frobenius_stable: stable,
        draws,
        d_max,
        seed,
        arms: vec![sym_cell, x_cell],
    })
}

/// The X5′ solve at one small rung: the chained symmetrised oracle on
/// `targets` subgroup targets of `K_a/F_{2^n}` over a random non-invariant
/// `V ∋ 1`, every verdict checked against exhaustive 4-sum enumeration over
/// `F_u` and every relation re-summed.
#[derive(Clone, Debug, serde::Serialize)]
pub struct X5Solve {
    pub a: u8,
    pub n: u32,
    pub ell: usize,
    pub points: usize,
    pub targets: usize,
    pub found: usize,
    pub refuted: usize,
    pub budget: usize,
    pub decomposable: usize,
    pub gate_failures: usize,
    pub mean_splits: f64,
    pub mean_word_xors: f64,
    pub mean_ms: f64,
}

pub fn x5_solve_gate(
    a: u8,
    n: u32,
    ell: usize,
    targets: usize,
    node_budget: usize,
    seed: u64,
) -> Option<X5Solve> {
    let kc = KoblitzCurve::new(a, n)?;
    let st = FieldStructure::new(n, &kc.curve.irreducible);
    let mut rng = StdRng::seed_from_u64(seed ^ ((n as u64) << 32));
    let v = random_subspace_containing_one(&kc, ell, &mut rng);
    let fb = build_symmetrised_factor_base_from_basis(&kc, v)?;
    let fc = FastCurve::new(&kc.curve)?;
    let pts: Vec<FastPoint> = fb.points.iter().map(|p| fc.lift(p)).collect();
    let index: HashMap<u64, usize> = pts.iter().enumerate().map(|(i, p)| (p.pack(), i)).collect();
    let g = kc.generator().clone();
    let r = kc
        .subgroup_order
        .to_u64_digits()
        .first()
        .copied()
        .unwrap_or(2)
        .max(2);
    let (mut found, mut refuted, mut budget, mut decomposable, mut gate_failures) = (0, 0, 0, 0, 0);
    let (mut splits, mut xors, mut ms) = (0.0, 0.0, 0.0);
    let mut drawn = 0;
    while drawn < targets {
        let t = kc.mul(&g, &BigUint::from(rng.gen_range(1..r)));
        if !matches!(&t, BinaryPoint::Affine { x, .. } if *x != F2mElement::one(n) && !x.is_zero())
        {
            continue;
        }
        drawn += 1;
        // Exhaustive 4-sums over F_u: R − P_i − P_j − P_k ∈ F_u.
        let ft = fc.lift(&t);
        let mut exists = false;
        'outer: for i in 0..pts.len() {
            let a1 = fc.add(ft, fc.neg(pts[i]));
            for j in i..pts.len() {
                let a2 = fc.add(a1, fc.neg(pts[j]));
                for k in j..pts.len() {
                    if index.contains_key(&fc.add(a2, fc.neg(pts[k])).pack()) {
                        exists = true;
                        break 'outer;
                    }
                }
            }
        }
        decomposable += usize::from(exists);
        let w0 = f4_word_ops_thread();
        let t0 = Instant::now();
        let o = chained_symmetrised_groebner_decompose(
            &kc,
            &fb,
            &st,
            &t,
            SolverEngine::default(),
            node_budget,
        )?;
        ms += t0.elapsed().as_secs_f64() * 1e3;
        xors += (f4_word_ops_thread() - w0) as f64;
        splits += o.effort as f64;
        match (&o.relation, o.complete) {
            (Some(idx), _) => {
                found += 1;
                let sum = fb.sum(&kc, idx);
                let ok = sum == t || (o.used_t && sum == kc.add(&t, &fb.two_torsion));
                if !exists || !ok {
                    gate_failures += 1;
                }
            }
            (None, true) => {
                refuted += 1;
                if exists {
                    gate_failures += 1;
                }
            }
            (None, false) => budget += 1,
        }
    }
    let k = targets as f64;
    Some(X5Solve {
        a,
        n,
        ell: fb.ell,
        points: fb.points.len(),
        targets,
        found,
        refuted,
        budget,
        decomposable,
        gate_failures,
        mean_splits: splits / k,
        mean_word_xors: xors / k,
        mean_ms: ms / k,
    })
}

#[cfg(test)]
mod x5_tests {
    use super::*;

    #[test]
    fn chained_symmetrised_system_vanishes_at_a_planted_four_sum_and_lifts_it() {
        // K₁/F₂¹¹: plant R = P₁ + P₂ + P₃ + P₄ over F_u and evaluate the
        // chain at the root the planted points give; then lift it.
        let kc = KoblitzCurve::new(1, 11).unwrap();
        let st = FieldStructure::new(11, &kc.curve.irreducible);
        let mut rng = StdRng::seed_from_u64(0x55);
        let v = random_subspace_containing_one(&kc, 4, &mut rng);
        let fb = build_symmetrised_factor_base_from_basis(&kc, v.clone()).unwrap();
        let irr = &kc.curve.irreducible;
        let n = 11u32;
        let mut planted = 0;
        for trial in 0..200 {
            let idx: Vec<usize> = (0..4).map(|_| rng.gen_range(0..fb.points.len())).collect();
            let pts: Vec<BinaryPoint> = idx.iter().map(|&i| fb.points[i].clone()).collect();
            let q1 = kc.add(&pts[0], &pts[1]);
            let q2 = kc.add(&q1, &pts[2]);
            let r = kc.add(&q2, &pts[3]);
            let (x1, x2, xr) = match (&q1, &q2, &r) {
                (
                    BinaryPoint::Affine { x: a, .. },
                    BinaryPoint::Affine { x: b, .. },
                    BinaryPoint::Affine { x: c, .. },
                ) => (a.clone(), b.clone(), c.clone()),
                _ => continue,
            };
            if [&x1, &x2, &xr]
                .iter()
                .any(|x| x.is_zero() || **x == F2mElement::one(n))
                || pts.contains(&fb.two_torsion)
            {
                continue;
            }
            let sys = build_chained_symmetrised_system(&fb.v_basis, irr, &xr, &st).unwrap();
            // The root: each summand's coordinates over v_basis[1..] with
            // parities ε_i, and the folded intermediates U₁, U₂.
            let ell_w = sys.ell_w;
            let mut root = 0u64;
            let mut eps = [false; 4];
            for (i, p) in pts.iter().enumerate() {
                let u = match p {
                    BinaryPoint::Affine { x, .. } => u_of_x(x, &kc).unwrap(),
                    _ => unreachable!(),
                };
                // Solve u = ε·1 + Σ c_t b_{t+1} over the basis by brute force.
                let mut hit = false;
                for mask in 0..(1u64 << (ell_w + 1)) {
                    let mut acc = F2mElement::zero(n);
                    if mask & 1 == 1 {
                        acc = acc.add(&F2mElement::one(n));
                    }
                    for t in 0..ell_w {
                        if (mask >> (t + 1)) & 1 == 1 {
                            acc = acc.add(&fb.v_basis[t + 1]);
                        }
                    }
                    if acc == u {
                        eps[i] = mask & 1 == 1;
                        root |= (mask >> 1) << (i * ell_w);
                        hit = true;
                        break;
                    }
                }
                assert!(hit, "u(P_{i}) lies in V");
            }
            let e = eps.iter().fold(false, |a, &b| a ^ b);
            if e {
                root |= 1 << (4 * ell_w);
            }
            let one = F2mElement::one(n);
            let mut uq1 = u_of_x(&x1, &kc).unwrap();
            if eps[0] ^ eps[1] {
                uq1 = uq1.add(&one);
            }
            let mut uq2 = u_of_x(&x2, &kc).unwrap();
            if eps[0] ^ eps[1] ^ eps[2] {
                uq2 = uq2.add(&one);
            }
            root |= bits_of(&uq1) << (4 * ell_w + 1);
            root |= bits_of(&uq2) << (4 * ell_w + 1 + n as usize);
            for (k, eq) in sys.equations.iter().enumerate() {
                assert_eq!(
                    eq.eval(root),
                    0,
                    "trial {trial}: equation {k} does not vanish"
                );
            }
            let lifted =
                lift_symmetrised_root(&kc, &fb, &sys, root, &r).expect("the planted root lifts");
            assert_eq!(fb.sum(&kc, &lifted.0), r);
            planted += 1;
            if planted == 8 {
                break;
            }
        }
        assert_eq!(planted, 8);
    }

    #[test]
    fn x5_solve_agrees_with_four_sum_enumeration() {
        let r = x5_solve_gate(1, 11, 4, 6, 20_000, 0x5EED0005).unwrap();
        assert_eq!(r.gate_failures, 0, "{r:?}");
        assert_eq!(r.found + r.refuted + r.budget, 6);
    }

    #[test]
    fn x5_rung_profiles_both_arms_on_one_v() {
        let r = x5_fall_rung(9, 4, 4, 3, 0x5EED0005, None).unwrap();
        assert_eq!(r.arms.len(), 2);
        assert_eq!(r.arms[0].n_vars, 4 * 3 + 1 + 18);
        assert_eq!(r.arms[1].n_vars, 4 * 4 + 2 * 9);
        assert_eq!(r.arms[0].degree, 3);
        assert_eq!(r.arms[0].n_eqs, 27);
        assert!(r.arms.iter().all(|a| a.falls.len() == 4));
    }
}
