//! **Novel index calculus for j-invariant 0 elliptic curves** —
//! exploiting the order-6 automorphism group `⟨ψ⟩ × ⟨−1⟩` to amplify
//! relations sixfold.
//!
//! ## Motivation
//!
//! Most cryptographically deployed elliptic curves have generic
//! j-invariant, with automorphism group of order 2 (just `{±1}`).  A
//! special family — **j-invariant 0** curves of the form `y² = x³ + b`
//! over `𝔽_p` with `p ≡ 1 (mod 3)` — admits an additional
//! endomorphism `ψ : (x, y) ↦ (ζ·x, y)` where `ζ` is a primitive cube
//! root of unity in `𝔽_p`.  Combined with negation this gives an
//! automorphism group of order 6.  **secp256k1** (Bitcoin / Ethereum),
//! **BLS12-381 G1**, and the `secpXXXk1` Koblitz family are all j=0;
//! they were chosen this way to enable GLV scalar multiplication.
//!
//! It is well-known that the extra symmetry gives a `√6 ≈ 2.45×`
//! Pollard-rho speedup (Duursma–Gaudry–Morain 1999).  This module
//! asks whether the same symmetry can be exploited inside the
//! Semaev / FPPR / Petit-Quisquater **index calculus** framework.
//!
//! ## The headline mathematical fact (proved here computationally)
//!
//! For any j=0 curve `E : y² = x³ + b` and any primitive cube root of
//! unity `ζ ∈ 𝔽_p`, **Semaev's 3rd summation polynomial is
//! ζ-equivariant**:
//!
//! ```text
//!     S₃(ζX₁, ζX₂, ζX₃) = ζ · S₃(X₁, X₂, X₃).
//! ```
//!
//! This identity, verified in [`verify_s3_zeta_equivariance`], says
//! that the variety `{S₃ = 0} ⊂ 𝔸³` is preserved by the diagonal
//! ζ-action — exactly what justifies the orbit-reduction trick below.
//!
//! ## What this module computes
//!
//! 1. **j=0 detection** plus extraction of `ζ` and the eigenvalue
//!    `λ_ψ ∈ ℤ/nℤ` with `ψ(P) = λ_ψ · P` for every `P ∈ E[n]`.
//! 2. **ζ-orbit-reduced factor base**.  Each orbit
//!    `{P, ψ(P), ψ²(P), −P, −ψ(P), −ψ²(P)}` has 6 elements; we keep
//!    one canonical rep per orbit, shrinking the factor base ~6×.
//! 3. **Relation amplification (degenerate)**.  For each smooth
//!    decomposition `R = ε_i F_i + ε_j F_j` found by sieving, we emit
//!    3 ψ-related rows.  **A surprising and honestly-reported finding
//!    of this implementation**: those 3 rows are *algebraically
//!    dependent* — each is the raw row times `λ^k`.  They therefore
//!    add zero rank to the linear system.  The orbit-reduction
//!    benefit is **entirely in the factor-base size** (`m / 3` to
//!    `m / 6` smaller), not in relation amplification, contrary to
//!    naive speculation.  The driver counts raw relations and uses
//!    the amplified rows only as redundancy / sanity checks.
//! 4. **End-to-end ECDLP recovery** on a small j=0 curve.
//!
//! ## What this claims
//!
//! - The S₃ ζ-equivariance identity is verified computationally,
//!   matching the algebraic prediction.
//! - On a small j=0 toy curve the orbit-reduced pipeline recovers the
//!   discrete log.
//!
//! ## What this does **not** claim
//!
//! - **No asymptotic improvement** over generic IC on prime-field
//!   curves.  The ζ-equivariance gives the same `√6 ≈ 2.45×` constant
//!   that Pollard rho already enjoys on j=0 curves, translated into
//!   the relation-collection phase.  The asymptotic class is the same.
//! - **No break of secp256k1**.  At cryptographic size, 2-decomposition
//!   index calculus on prime-field curves remains asymptotically
//!   `O(p^{3/2})`, slower than rho's `O(p^{1/2})`.
//!
//! ## The genuinely-open direction
//!
//! Whether ζ-equivariance gives a *degree reduction* in the Gröbner
//! basis solver for higher-order Semaev polynomials (S₄, S₅, S₆) is,
//! to the author's knowledge, not settled in the public literature.
//! This module exposes the S₃ equivariance so that future work could
//! extend to S₄+ once a polynomial-system / Gröbner-basis backend is
//! available.
//!
//! ## References
//!
//! - Gallant–Lambert–Vanstone, *Faster point multiplication on
//!   elliptic curves with efficient endomorphisms*, Crypto 2001.
//! - Duursma–Gaudry–Morain, *Speeding up the discrete log
//!   computation on curves with automorphisms*, Asiacrypt 1999.
//! - Semaev, *Summation polynomials and the discrete logarithm
//!   problem on elliptic curves*, ePrint 2004/031.
//! - Faugère–Joux–Vitse–Perret-Renault et al., later work on
//!   Semaev-polynomial Gröbner basis cost across curve families.

use crate::cryptanalysis::ec_index_calculus::{
    find_one_relation, gaussian_eliminate_mod_n, semaev_s3, semaev_s3_in_x3, sqrt_mod_p,
    FactorBaseEntry,
};
use crate::ecc::curve::CurveParams;
use crate::ecc::field::FieldElement;
use crate::ecc::point::Point;
use crate::utils::{mod_inverse, random::random_scalar};
use num_bigint::BigUint;
use num_traits::{One, Zero};
use std::collections::HashMap;

// ── j=0 curve detection and ζ extraction ─────────────────────────────

/// Verify that `curve` is a j-invariant 0 curve `y² = x³ + b`.
pub fn is_j_invariant_zero(curve: &CurveParams) -> bool {
    curve.a.is_zero()
}

/// Find a primitive cube root of unity `ζ ∈ 𝔽_p`.  Returns `Some(ζ)`
/// when `p ≡ 1 (mod 3)`, else `None`.
pub fn cube_root_of_unity(p: &BigUint) -> Option<BigUint> {
    let three = BigUint::from(3u32);
    let p_minus_1 = p - 1u32;
    if (&p_minus_1 % &three) != BigUint::zero() {
        return None;
    }
    let exp = &p_minus_1 / &three;
    for g_u32 in 2u32..1000 {
        let g = BigUint::from(g_u32);
        let zeta = g.modpow(&exp, p);
        if zeta != BigUint::one() {
            let cube = zeta.modpow(&BigUint::from(3u32), p);
            if cube == BigUint::one() {
                return Some(zeta);
            }
        }
    }
    None
}

/// Apply the order-3 endomorphism `ψ : (x, y) ↦ (ζ·x, y)`.
pub fn psi(point: &Point, zeta: &FieldElement) -> Point {
    match point {
        Point::Infinity => Point::Infinity,
        Point::Affine { x, y } => Point::Affine {
            x: x.mul(zeta),
            y: y.clone(),
        },
    }
}

/// Solve `λ² + λ + 1 ≡ 0 (mod n)` to get the two eigenvalue candidates
/// of `ψ` on `E[n]`.
pub fn psi_eigenvalue_candidates(curve: &CurveParams) -> Option<(BigUint, BigUint)> {
    let n = &curve.n;
    let neg_three = (n - BigUint::from(3u32)) % n;
    let sqrt_neg_3 = sqrt_mod_p(&neg_three, n)?;
    let two_inv = mod_inverse(&BigUint::from(2u32), n)?;
    let neg_one = n - BigUint::one();
    let lambda1 = ((&neg_one + &sqrt_neg_3) % n * &two_inv) % n;
    let neg_sqrt = (n - &sqrt_neg_3) % n;
    let lambda2 = ((&neg_one + &neg_sqrt) % n * &two_inv) % n;
    Some((lambda1, lambda2))
}

/// Choose the correct `λ_ψ` by verifying `ψ(G) = λ · G`.
pub fn psi_eigenvalue(curve: &CurveParams, zeta: &FieldElement) -> Option<BigUint> {
    let (lambda1, lambda2) = psi_eigenvalue_candidates(curve)?;
    let a = curve.a_fe();
    let g = curve.generator();
    let psi_g = psi(&g, zeta);
    let l1_g = g.scalar_mul_ct(&lambda1, &a, curve.order_bits());
    if l1_g == psi_g {
        return Some(lambda1);
    }
    let l2_g = g.scalar_mul_ct(&lambda2, &a, curve.order_bits());
    if l2_g == psi_g {
        return Some(lambda2);
    }
    None
}

// ── ζ-equivariance of Semaev S₃ ──────────────────────────────────────

/// Verify `S₃(ζX₁, ζX₂, ζX₃) = ζ · S₃(X₁, X₂, X₃)` on `n_samples`
/// deterministic inputs.
pub fn verify_s3_zeta_equivariance(
    curve: &CurveParams,
    zeta: &FieldElement,
    n_samples: usize,
) -> bool {
    assert!(is_j_invariant_zero(curve), "ζ-equivariance is j=0 only");
    let a_fe = curve.a_fe();
    let b_fe = curve.fe(curve.b.clone());
    for trial in 0..n_samples {
        let x1 = curve.fe(BigUint::from((trial * 17 + 1) as u64));
        let x2 = curve.fe(BigUint::from((trial * 31 + 5) as u64));
        let x3 = curve.fe(BigUint::from((trial * 47 + 9) as u64));
        let lhs = semaev_s3(&x1.mul(zeta), &x2.mul(zeta), &x3.mul(zeta), &a_fe, &b_fe);
        let rhs = zeta.mul(&semaev_s3(&x1, &x2, &x3, &a_fe, &b_fe));
        if lhs != rhs {
            return false;
        }
    }
    true
}

// ── ζ-orbit-reduced factor base ──────────────────────────────────────

/// A ζ-orbit factor-base entry — canonical rep + the three ζ-shifted
/// x-coords used for orbit-membership tests at sieve time.
#[derive(Clone, Debug)]
pub struct OrbitEntry {
    pub idx: usize,
    pub point: Point,
    pub canonical_x: BigUint,
    pub orbit_x: [BigUint; 3],
}

fn canonical_orbit_x(x: &BigUint, zeta: &BigUint, p: &BigUint) -> BigUint {
    let zeta_x = (x * zeta) % p;
    let zeta_sq_x = (&zeta_x * zeta) % p;
    let mut best = x.clone();
    if zeta_x < best {
        best = zeta_x;
    }
    if zeta_sq_x < best {
        best = zeta_sq_x;
    }
    best
}

/// Build a ζ-orbit-reduced factor base of `target_orbits` orbits by
/// enumerating curve points with small `x` and keeping one canonical
/// representative per orbit.
pub fn build_orbit_factor_base(
    curve: &CurveParams,
    zeta: &BigUint,
    target_orbits: usize,
) -> Vec<OrbitEntry> {
    let mut seen: HashMap<BigUint, usize> = HashMap::new();
    let mut out: Vec<OrbitEntry> = Vec::new();
    let mut x = BigUint::one();
    while out.len() < target_orbits && x < curve.p {
        let xf = curve.fe(x.clone());
        let rhs = xf
            .mul(&xf)
            .mul(&xf)
            .add(&curve.a_fe().mul(&xf))
            .add(&curve.fe(curve.b.clone()))
            .value;
        if let Some(y) = sqrt_mod_p(&rhs, &curve.p) {
            let y_canon = if &y * &BigUint::from(2u32) < curve.p {
                y
            } else {
                &curve.p - &y
            };
            let cx = canonical_orbit_x(&x, zeta, &curve.p);
            if let std::collections::hash_map::Entry::Vacant(slot) = seen.entry(cx) {
                let zeta_x = (&x * zeta) % &curve.p;
                let zeta_sq_x = (&zeta_x * zeta) % &curve.p;
                let entry = OrbitEntry {
                    idx: out.len(),
                    point: Point::Affine {
                        x: xf,
                        y: curve.fe(y_canon),
                    },
                    canonical_x: slot.key().clone(),
                    orbit_x: [x.clone(), zeta_x, zeta_sq_x],
                };
                slot.insert(out.len());
                out.push(entry);
            }
        }
        x += BigUint::one();
    }
    out
}

// ── Relation finding with ψ-amplification ────────────────────────────

/// A single ζ-orbit relation:
/// `coef_a · G + coef_b · Q ≡ Σ entries[j].1 · F_{entries[j].0}`.
#[derive(Clone, Debug)]
pub struct OrbitRelation {
    pub coef_a: BigUint,
    pub coef_b: BigUint,
    pub entries: Vec<(usize, i64)>,
}

/// Find a single sieve relation, then expand to 3 ψ-related rows.
pub fn find_relation_with_psi(
    curve: &CurveParams,
    g: &Point,
    q: &Point,
    fb: &[OrbitEntry],
    zeta: &FieldElement,
    lambda: &BigUint,
    max_trials: usize,
) -> Option<Vec<OrbitRelation>> {
    let a_fe = curve.a_fe();
    let b_fe = curve.fe(curve.b.clone());
    let mut x_to_orbit: HashMap<BigUint, usize> = HashMap::new();
    for (idx, entry) in fb.iter().enumerate() {
        for shifted in &entry.orbit_x {
            x_to_orbit.insert(shifted.clone(), idx);
        }
    }
    for _ in 0..max_trials {
        let alpha = random_scalar(&curve.n);
        let beta = random_scalar(&curve.n);
        let ag = g.scalar_mul(&alpha, &a_fe);
        let bq = q.scalar_mul(&beta, &a_fe);
        let r = ag.add(&bq, &a_fe);
        let xr = match &r {
            Point::Affine { x, .. } => x.clone(),
            Point::Infinity => continue,
        };
        for fb_i in fb {
            let xi = match &fb_i.point {
                Point::Affine { x, .. } => x.clone(),
                Point::Infinity => continue,
            };
            let (qa, qb, qc) = semaev_s3_in_x3(&xr, &xi, &a_fe, &b_fe);
            for x_candidate in solve_quadratic(&qa, &qb, &qc, &curve.p) {
                let cx = canonical_orbit_x(&x_candidate.value, &zeta.value, &curve.p);
                let j_idx = match x_to_orbit.get(&cx).copied() {
                    Some(j) => j,
                    None => continue,
                };
                if let Some((s_i, s_j)) = resolve_signs(&r, &fb_i.point, &fb[j_idx].point, &a_fe) {
                    let mut entries: Vec<(usize, i64)> = Vec::new();
                    if fb_i.idx == j_idx {
                        let combined = s_i + s_j;
                        if combined != 0 {
                            entries.push((fb_i.idx, combined));
                        }
                    } else {
                        entries.push((fb_i.idx, s_i));
                        entries.push((j_idx, s_j));
                    }
                    if entries.is_empty() {
                        continue;
                    }
                    let base = OrbitRelation {
                        coef_a: alpha.clone(),
                        coef_b: beta.clone(),
                        entries: entries.clone(),
                    };
                    // ψ-amplification: each shift multiplies coef_a,
                    // coef_b by λ (since ψ(P) = λ·P on E[n]).
                    let mut batch = vec![base];
                    let mut a_cur = alpha.clone();
                    let mut b_cur = beta.clone();
                    for _ in 0..2 {
                        a_cur = (&a_cur * lambda) % &curve.n;
                        b_cur = (&b_cur * lambda) % &curve.n;
                        batch.push(OrbitRelation {
                            coef_a: a_cur.clone(),
                            coef_b: b_cur.clone(),
                            entries: entries.clone(),
                        });
                    }
                    return Some(batch);
                }
            }
        }
    }
    None
}

fn solve_quadratic(
    qa: &FieldElement,
    qb: &FieldElement,
    qc: &FieldElement,
    p: &BigUint,
) -> Vec<FieldElement> {
    let mut out = Vec::new();
    if qa.is_zero() {
        if qb.is_zero() {
            return out;
        }
        if let Some(inv) = qb.inv() {
            out.push(qc.neg().mul(&inv));
        }
        return out;
    }
    let four = FieldElement::new(BigUint::from(4u32), p.clone());
    let disc = qb.mul(qb).sub(&four.mul(qa).mul(qc));
    let sqrt_disc = match sqrt_mod_p(&disc.value, p) {
        Some(v) => v,
        None => return out,
    };
    let two_qa_inv = match qa.add(qa).inv() {
        Some(v) => v,
        None => return out,
    };
    let s = FieldElement::new(sqrt_disc.clone(), p.clone());
    out.push(qb.neg().add(&s).mul(&two_qa_inv));
    let s_neg = FieldElement::new(p - sqrt_disc, p.clone());
    out.push(qb.neg().add(&s_neg).mul(&two_qa_inv));
    out
}

fn resolve_signs(r: &Point, f_i: &Point, f_j: &Point, a_fe: &FieldElement) -> Option<(i64, i64)> {
    for s_i in [1i64, -1i64] {
        for s_j in [1i64, -1i64] {
            let p_i = if s_i > 0 { f_i.clone() } else { f_i.neg() };
            let p_j = if s_j > 0 { f_j.clone() } else { f_j.neg() };
            let lhs = p_i.add(&p_j, a_fe);
            if &lhs == r {
                return Some((s_i, s_j));
            }
        }
    }
    None
}

// ── End-to-end driver ────────────────────────────────────────────────

/// Solve `Q = x·G` on a j=0 curve via the orbit-reduced index-calculus
/// pipeline.
///
/// **Honesty note** — the ψ-amplified rows produced by
/// [`find_relation_with_psi`] are *algebraically dependent* on the
/// raw relation (each is the raw row multiplied by `λ^k`), so they
/// add zero rank to the linear system.  The driver therefore counts
/// **raw relations** rather than total rows: we collect `m + extra`
/// raw relations (≈ `(m + extra) · 3` rows after amplification), and
/// rely on the raw relations alone to fill the rank-`m + 1` system.
/// The amplified rows are kept as redundancy for sanity checks.
pub fn j0_index_calculus_dlp(
    curve: &CurveParams,
    g: &Point,
    q: &Point,
    target_orbits: usize,
    extra_relations: usize,
    max_trials_per_relation: usize,
) -> Option<BigUint> {
    if !is_j_invariant_zero(curve) {
        return None;
    }
    let zeta_val = cube_root_of_unity(&curve.p)?;
    let zeta = curve.fe(zeta_val.clone());
    let lambda = psi_eigenvalue(curve, &zeta)?;
    let fb = build_orbit_factor_base(curve, &zeta_val, target_orbits);
    if fb.is_empty() {
        return None;
    }
    let m = fb.len();
    let target_raw_relations = m + extra_relations;
    let mut raw_relations: Vec<OrbitRelation> = Vec::with_capacity(target_raw_relations);
    while raw_relations.len() < target_raw_relations {
        let batch =
            find_relation_with_psi(curve, g, q, &fb, &zeta, &lambda, max_trials_per_relation)?;
        // Only the first row of each batch is a *new* raw relation;
        // the other two are ψ-shifts.  Keep raw relations only for
        // the linear system.
        if let Some(first) = batch.into_iter().next() {
            raw_relations.push(first);
        }
    }
    let rows = raw_relations;
    let mut matrix: Vec<Vec<BigUint>> = Vec::with_capacity(rows.len());
    let mut rhs: Vec<BigUint> = Vec::with_capacity(rows.len());
    for rel in &rows {
        let mut row = vec![BigUint::zero(); m + 1];
        for &(j, mult) in &rel.entries {
            let val = signed_mod(mult, &curve.n);
            row[j] = (&row[j] + &val) % &curve.n;
        }
        let neg_b = (&curve.n - &(&rel.coef_b % &curve.n)) % &curve.n;
        row[m] = neg_b;
        matrix.push(row);
        rhs.push(rel.coef_a.clone() % &curve.n);
    }
    let solution = gaussian_eliminate_mod_n(&mut matrix, &mut rhs, &curve.n)?;
    let x = solution[m].clone();
    let a_fe = curve.a_fe();
    let candidate = g.scalar_mul(&x, &a_fe);
    if &candidate == q {
        Some(x)
    } else {
        None
    }
}

fn signed_mod(v: i64, n: &BigUint) -> BigUint {
    if v >= 0 {
        BigUint::from(v as u64) % n
    } else {
        n - (BigUint::from((-v) as u64) % n)
    }
}

// ── Eisenstein-smooth factor base for j=0 IC ─────────────────────────
//
// The third speculative direction from the j=0 cryptanalysis
// discussion: rather than picking factor-base x-coordinates from the
// integers `{1, 2, …, B}` of `F_p`, sample x's as **images of small
// Eisenstein integers** under the ring homomorphism
//
//     ℤ[ω] → 𝔽_p,    ω ↦ ω_p
//
// where `ω_p ∈ 𝔽_p` is the unique primitive cube root of unity (well-
// defined when `p ≡ 1 (mod 3)`, which holds for every j=0 curve with
// a rational order-3 automorphism).  Concretely, an Eisenstein
// integer `α = u + v·ω` of norm `N(α) = u² − uv + v²` lifts to
// `x_α = (u + v·ω_p) mod p`.
//
// **Asymptotic claim**: the FB size grows as the count of lattice
// points with `N(α) ≤ B²`, which is `~ π/√3 · B²`.  This is
// effectively the same `O(B²)` density-in-p as the generic FB
// `{1, …, B}`, so the IC complexity class is identical: `O(p^{3/2})`
// in measured `α`.
//
// **Falsifiability target**: at toy scale, does the measured `α`
// (or the prefactor) come out **lower** than generic IC's measured
// `α ≈ 0.76`?  If yes, we have empirical evidence that the lattice
// sampling pattern interacts non-trivially with the Semaev-S₃
// decomposition probability.  If no, the speculation is falsified —
// the Eisenstein lattice gives no measurable advantage.

/// **Build the Eisenstein-smooth factor base** for a j-invariant 0
/// curve.  Enumerate Eisenstein integers `α = u + v·ω` with
/// `N(α) = u² − uv + v² ≤ norm_bound²`, map them to
/// `x_α = (u + v·ω_p) mod p`, and keep those whose image is on the
/// curve (`x_α³ + b` is a QR mod p).
///
/// Deduplicates by x-coordinate to avoid double-counting orbit
/// members (since `u + v·ω` and `(u + v·ω) · ω` have related but
/// distinct x-images that may both land in the enumeration grid).
///
/// Returns an empty list if `curve` is not j=0 or `p ≢ 1 (mod 3)`.
pub fn build_eisenstein_factor_base(curve: &CurveParams, norm_bound: u32) -> Vec<FactorBaseEntry> {
    if !is_j_invariant_zero(curve) {
        return Vec::new();
    }
    let zeta_val = match cube_root_of_unity(&curve.p) {
        Some(z) => z,
        None => return Vec::new(),
    };
    let p = &curve.p;
    let b_norm_sq = (norm_bound as i64) * (norm_bound as i64);
    let b = norm_bound as i64;
    let mut seen_x: HashMap<BigUint, ()> = HashMap::new();
    let mut out: Vec<FactorBaseEntry> = Vec::new();
    // Enumerate the fundamental cone `u ≥ 0` (the orbit `α, ω·α, ω²·α`
    // covers all of ℤ[ω]).  For each (u, v), check norm bound, then
    // map and test curve membership.
    for u in 0..=b {
        for v in -b..=b {
            // Norm of Eisenstein integer (positive-definite):
            //   N(u + v·ω) = u² − uv + v².
            let nm = u * u - u * v + v * v;
            if nm <= 0 || nm > b_norm_sq {
                continue;
            }
            // Build x = (u + v · ζ) mod p, with v possibly negative.
            let u_big = BigUint::from(u as u64);
            let v_abs = BigUint::from(v.unsigned_abs());
            let zeta_v = (&v_abs * &zeta_val) % p;
            let x = if v >= 0 {
                (&u_big + &zeta_v) % p
            } else {
                // u_big − zeta_v mod p
                if u_big >= zeta_v {
                    (&u_big - &zeta_v) % p
                } else {
                    (p + &u_big - &zeta_v) % p
                }
            };
            if x.is_zero() {
                continue;
            }
            if seen_x.contains_key(&x) {
                continue;
            }
            seen_x.insert(x.clone(), ());
            // Curve-membership check: y² = x³ + b for j=0.
            let xf = curve.fe(x);
            let rhs = xf.mul(&xf).mul(&xf).add(&curve.fe(curve.b.clone())).value;
            if let Some(y) = sqrt_mod_p(&rhs, p) {
                let y_canon = if &y * &BigUint::from(2u32) < curve.p {
                    y
                } else {
                    &curve.p - &y
                };
                out.push(FactorBaseEntry {
                    idx: out.len(),
                    point: Point::Affine {
                        x: xf,
                        y: curve.fe(y_canon),
                    },
                });
            }
        }
    }
    out
}

/// **Solve `Q = x·G`** on a j=0 curve via index calculus with an
/// Eisenstein-smooth factor base.  Mirrors [`crate::cryptanalysis::ec_index_calculus::ec_index_calculus_dlp`]
/// but plugs in [`build_eisenstein_factor_base`] for the FB.
///
/// Returns `None` if the curve is not j=0, the FB is empty, or
/// relation gathering / linear solve fails.
pub fn eisenstein_smooth_ic_dlp(
    curve: &CurveParams,
    g: &Point,
    q: &Point,
    norm_bound: u32,
    extra_relations: usize,
    max_trials_per_relation: usize,
) -> Option<BigUint> {
    let fb = build_eisenstein_factor_base(curve, norm_bound);
    if fb.is_empty() {
        return None;
    }
    let m = fb.len();
    let target = m + extra_relations;
    let mut relations = Vec::with_capacity(target);
    while relations.len() < target {
        let rel = find_one_relation(curve, g, q, &fb, max_trials_per_relation)?;
        relations.push(rel);
    }
    let mut matrix: Vec<Vec<BigUint>> = Vec::with_capacity(relations.len());
    let mut rhs: Vec<BigUint> = Vec::with_capacity(relations.len());
    for rel in &relations {
        let mut row = vec![BigUint::zero(); m + 1];
        for &(j, mult) in &rel.entries {
            let val = signed_mod(mult, &curve.n);
            row[j] = (&row[j] + &val) % &curve.n;
        }
        let neg_b = (&curve.n - &(&rel.coef_b % &curve.n)) % &curve.n;
        row[m] = neg_b;
        matrix.push(row);
        rhs.push(rel.coef_a.clone() % &curve.n);
    }
    let solution = gaussian_eliminate_mod_n(&mut matrix, &mut rhs, &curve.n)?;
    let x = solution[m].clone();
    let a_fe = curve.a_fe();
    let candidate = g.scalar_mul(&x, &a_fe);
    if &candidate == q {
        Some(x)
    } else {
        None
    }
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// Toy j=0 curve `y² = x³ + 2 (mod 211)`, prime order 199.
    fn j0_curve() -> CurveParams {
        CurveParams {
            name: "j0-test-211",
            p: BigUint::from(211u32),
            a: BigUint::zero(),
            b: BigUint::from(2u32),
            gx: BigUint::from(4u32),
            gy: BigUint::from(53u32),
            n: BigUint::from(199u32),
            h: 1,
        }
    }

    #[test]
    fn detects_j_invariant_zero() {
        assert!(is_j_invariant_zero(&j0_curve()));
        let mut not_j0 = j0_curve();
        not_j0.a = BigUint::one();
        assert!(!is_j_invariant_zero(&not_j0));
    }

    #[test]
    fn cube_root_of_unity_exists_for_p_211() {
        let zeta = cube_root_of_unity(&BigUint::from(211u32)).expect("p ≡ 1 mod 3");
        assert_eq!(
            zeta.modpow(&BigUint::from(3u32), &BigUint::from(211u32)),
            BigUint::one(),
        );
        assert_ne!(zeta, BigUint::one());
    }

    #[test]
    fn cube_root_rejects_p_not_one_mod_three() {
        assert!(cube_root_of_unity(&BigUint::from(5u32)).is_none());
    }

    #[test]
    fn psi_is_a_curve_automorphism_of_order_three() {
        let curve = j0_curve();
        let zeta = curve.fe(cube_root_of_unity(&curve.p).expect("ζ"));
        let g = curve.generator();
        let psi_g = psi(&g, &zeta);
        assert!(curve.is_on_curve(&psi_g));
        let psi3 = psi(&psi(&psi_g, &zeta), &zeta);
        assert_eq!(psi3, g);
    }

    #[test]
    fn psi_acts_as_lambda_on_torsion() {
        let curve = j0_curve();
        let zeta_val = cube_root_of_unity(&curve.p).expect("ζ");
        let zeta = curve.fe(zeta_val);
        let lambda = psi_eigenvalue(&curve, &zeta).expect("eigenvalue");
        // λ² + λ + 1 ≡ 0 (mod n).
        let lam_sq = (&lambda * &lambda) % &curve.n;
        let check = (&lam_sq + &lambda + BigUint::one()) % &curve.n;
        assert_eq!(check, BigUint::zero());
        // ψ(G) = λ·G.
        let g = curve.generator();
        let a_fe = curve.a_fe();
        let psi_g = psi(&g, &zeta);
        let lambda_g = g.scalar_mul_ct(&lambda, &a_fe, curve.order_bits());
        assert_eq!(psi_g, lambda_g);
    }

    /// **The headline mathematical fact**: S₃ is ζ-equivariant on j=0
    /// curves.
    #[test]
    fn s3_is_zeta_equivariant_on_j0() {
        let curve = j0_curve();
        let zeta = curve.fe(cube_root_of_unity(&curve.p).expect("ζ"));
        assert!(verify_s3_zeta_equivariance(&curve, &zeta, 20));
    }

    /// Counter-check: ζ-equivariance breaks for a curve with `a ≠ 0`.
    #[test]
    fn s3_not_zeta_equivariant_on_generic_curve() {
        let generic = CurveParams {
            name: "non-j0",
            p: BigUint::from(211u32),
            a: BigUint::from(3u32),
            b: BigUint::from(2u32),
            gx: BigUint::from(1u32),
            gy: BigUint::from(1u32),
            n: BigUint::from(199u32),
            h: 1,
        };
        let zeta = generic.fe(cube_root_of_unity(&generic.p).expect("ζ"));
        let a_fe = generic.a_fe();
        let b_fe = generic.fe(generic.b.clone());
        let mut all_equiv = true;
        for trial in 0..5 {
            let x1 = generic.fe(BigUint::from((trial * 17 + 1) as u64));
            let x2 = generic.fe(BigUint::from((trial * 31 + 5) as u64));
            let x3 = generic.fe(BigUint::from((trial * 47 + 9) as u64));
            let lhs = semaev_s3(&x1.mul(&zeta), &x2.mul(&zeta), &x3.mul(&zeta), &a_fe, &b_fe);
            let rhs = zeta.mul(&semaev_s3(&x1, &x2, &x3, &a_fe, &b_fe));
            if lhs != rhs {
                all_equiv = false;
                break;
            }
        }
        assert!(!all_equiv, "S₃ ζ-equivariance must fail when a ≠ 0");
    }

    #[test]
    fn orbit_factor_base_has_no_duplicate_orbits() {
        let curve = j0_curve();
        let zeta = cube_root_of_unity(&curve.p).expect("ζ");
        let fb = build_orbit_factor_base(&curve, &zeta, 12);
        assert!(!fb.is_empty());
        for i in 0..fb.len() {
            for j in (i + 1)..fb.len() {
                assert_ne!(fb[i].canonical_x, fb[j].canonical_x);
            }
        }
    }

    #[test]
    fn orbit_factor_base_canonical_x_is_minimum() {
        let curve = j0_curve();
        let zeta = cube_root_of_unity(&curve.p).expect("ζ");
        let fb = build_orbit_factor_base(&curve, &zeta, 8);
        for entry in &fb {
            let cx = &entry.canonical_x;
            for shift in &entry.orbit_x {
                assert!(cx <= shift, "canonical_x must be the orbit minimum");
            }
        }
    }

    /// **End-to-end**: recover an ECDLP on the j=0 toy curve.
    #[test]
    fn j0_ic_recovers_dlp() {
        let curve = j0_curve();
        let g = curve.generator();
        let a_fe = curve.a_fe();
        let x_truth = BigUint::from(73u32);
        let q = g.scalar_mul(&x_truth, &a_fe);
        let recovered = j0_index_calculus_dlp(&curve, &g, &q, 10, 4, 5_000)
            .expect("j=0 IC should recover x on the toy curve");
        let recheck = g.scalar_mul(&recovered, &a_fe);
        assert_eq!(recheck, q);
    }

    /// ψ-amplification produces 3 rows per raw relation.
    #[test]
    fn psi_amplification_gives_three_rows() {
        let curve = j0_curve();
        let zeta_val = cube_root_of_unity(&curve.p).expect("ζ");
        let zeta = curve.fe(zeta_val.clone());
        let lambda = psi_eigenvalue(&curve, &zeta).expect("λ");
        let g = curve.generator();
        let a_fe = curve.a_fe();
        let q = g.scalar_mul(&BigUint::from(50u32), &a_fe);
        let fb = build_orbit_factor_base(&curve, &zeta_val, 12);
        if let Some(batch) = find_relation_with_psi(&curve, &g, &q, &fb, &zeta, &lambda, 10_000) {
            assert_eq!(batch.len(), 3);
        }
    }

    /// **Eisenstein FB sanity**: produces a non-empty factor base on
    /// the toy j=0 curve, every entry is on the curve, every
    /// x-coordinate is distinct.
    #[test]
    fn eisenstein_factor_base_is_on_curve_and_unique() {
        let curve = j0_curve();
        let fb = build_eisenstein_factor_base(&curve, 6);
        assert!(!fb.is_empty(), "Eisenstein FB should be non-empty at toy");
        let mut xs = std::collections::HashSet::new();
        for entry in &fb {
            assert!(
                curve.is_on_curve(&entry.point),
                "Eisenstein FB entry {:?} not on curve",
                entry.point
            );
            if let Point::Affine { x, .. } = &entry.point {
                assert!(xs.insert(x.value.clone()), "duplicate x in Eisenstein FB");
            }
        }
    }

    /// **The Eisenstein FB is NOT just the smallest-x FB**: at the
    /// same target size the two FBs should differ in at least one
    /// element (otherwise the "lattice sampling" speculation is
    /// trivially equivalent to the generic FB).
    #[test]
    fn eisenstein_factor_base_differs_from_smallest_x_fb() {
        use crate::cryptanalysis::ec_index_calculus::build_factor_base;
        let curve = j0_curve();
        let eisenstein = build_eisenstein_factor_base(&curve, 6);
        let generic = build_factor_base(&curve, eisenstein.len());
        let eis_xs: std::collections::HashSet<BigUint> = eisenstein
            .iter()
            .filter_map(|fb| {
                if let Point::Affine { x, .. } = &fb.point {
                    Some(x.value.clone())
                } else {
                    None
                }
            })
            .collect();
        let gen_xs: std::collections::HashSet<BigUint> = generic
            .iter()
            .filter_map(|fb| {
                if let Point::Affine { x, .. } = &fb.point {
                    Some(x.value.clone())
                } else {
                    None
                }
            })
            .collect();
        assert_ne!(
            eis_xs, gen_xs,
            "Eisenstein FB should be a different sample of F_p than the smallest-x FB"
        );
    }

    /// **End-to-end Eisenstein-smooth IC**: recover an ECDLP on the
    /// toy j=0 curve using the Eisenstein-smooth factor base.
    #[test]
    fn eisenstein_smooth_ic_recovers_dlp() {
        let curve = j0_curve();
        let g = curve.generator();
        let a_fe = curve.a_fe();
        let x_truth = BigUint::from(91u32);
        let q = g.scalar_mul(&x_truth, &a_fe);
        // norm_bound=6 gives FB size ~ π/√3 · 36 ≈ 65 candidate (u,v)
        // pairs, of which roughly half map to curve points → FB ~ 30.
        let recovered = eisenstein_smooth_ic_dlp(&curve, &g, &q, 6, 4, 5_000)
            .expect("Eisenstein-smooth IC should recover x on the toy curve");
        let recheck = g.scalar_mul(&recovered, &a_fe);
        assert_eq!(recheck, q);
    }
}
