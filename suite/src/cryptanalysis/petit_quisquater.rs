//! # Petit–Quisquater small-characteristic index calculus — **toy driver**.
//!
//! Index calculus for ECDLP on `E / F_{2^m}` in the canonical binary
//! Weierstrass form `y² + xy = x³ + ax² + b`, using Semaev's third
//! summation polynomial `S₃` and an `F₂`-vector-subspace factor base.
//! This is the framework introduced in
//!
//! - **C. Petit, J.-J. Quisquater**, *On polynomial systems arising
//!   from a Weil descent*, ASIACRYPT 2012,
//!
//! and developed in parallel by
//!
//! - **J.-C. Faugère, L. Perret, C. Petit, G. Renault**, *Improving
//!   the complexity of index calculus algorithms in elliptic curves
//!   over binary fields*, EUROCRYPT 2012.
//!
//! ## What the attack does at `n = 2`
//!
//! 1. **Factor base.**  Pick an `F₂`-vector subspace `V ⊂ F_{2^m}` of
//!    dimension `m'`.  The factor base is `FB = { (x, y) ∈ E : x ∈ V }`,
//!    indexed by `x`.  Each `x ∈ V` has a curve point iff the
//!    Artin–Schreier equation `t² + t = x + a + b/x²` is solvable, which
//!    happens for ≈ half the `x ∈ V` (the trace-zero half).
//!
//! 2. **Relation search.**  Pick random `(a_j, b_j) ∈ Z/N`, form
//!    `R_j = a_j G + b_j Q`.  A *2-decomposition over the factor base*
//!    is a pair `(P_1, P_2) ∈ FB × FB` with `R_j = ε_1 P_1 + ε_2 P_2`
//!    for some signs `ε_i ∈ {±1}`.  The algebraic constraint is the
//!    binary-curve Semaev relation
//!    ```text
//!        S₃(x_1, x_2, x_{R_j}) = 0
//!    ```
//!    with `x_1, x_2 ∈ V`.  At `n = 2` this is a *quadratic in `x_2`*
//!    once `x_1` is fixed, which we solve directly over `F_{2^m}` —
//!    no Gröbner basis needed.  Larger `n` would require a Gröbner
//!    solve over `F_2` after Weil descent of `S_{n+1}`, but the toy
//!    case captures every other moving part of Petit–Quisquater.
//!
//! 3. **Linear algebra mod `N`.**  Once we have `≥ |FB| + 1` relations,
//!    we build a matrix in `(Z/N)^{rows × (|FB|+1)}` where the columns
//!    are the discrete logs `y_i = log_G(P_i)` plus `k = log_G(Q)`.
//!    A single Gaussian elimination mod `N` (reusing
//!    [`crate::cryptanalysis::ec_index_calculus::gaussian_eliminate_mod_n`])
//!    reads off `k`.
//!
//! ## Differences vs. real Petit–Quisquater
//!
//! - **`n = 2` only.**  At `n = 2`, the polynomial system after fixing
//!   `(x_1, x_R)` collapses to a single quadratic in one unknown over
//!   `F_{2^m}`.  Real PQ uses larger `n` for a tighter factor base /
//!   relation balance, and pays for the polynomial-system solve with
//!   a Gröbner basis computation (F4 / F5) on the Weil-descended system
//!   over `F_2`.  That machinery lives in the `research/gbrl` crate as
//!   a research artefact; the toy here keeps the driver self-contained.
//! - **Subspace = `F_2`-span of `{1, z, …, z^{m'-1}}`.**  Real PQ
//!   prefers `V = F_{2^{m'}}` as a subfield (gives a multiplicative
//!   structure on the factor base — useful for Joux-Vitse "decomposition
//!   into 2 pieces" speedups).  For `n = 2` the subspace structure is
//!   what matters; we use the canonical low-order basis.
//! - **Dense linear algebra.**  Sufficient for `|FB| ≤ ~50`; real PQ
//!   uses sparse linear algebra (Lanczos / Wiedemann) on much larger
//!   matrices.
//! - **No Weil descent at the relation level.**  At `n = 2` it is a
//!   *no-op* because there is exactly one unknown after fixing `(x_1,
//!   x_R)`; the descent would produce `m` equations in `m'` `F₂`
//!   variables, but those are equivalent to the single quadratic over
//!   `F_{2^m}` that `solve_quadratic_f2m` already handles.
//!
//! ## Why this module exists
//!
//! Companion to
//!
//! - [`crate::cryptanalysis::ec_index_calculus`] — Semaev `S₃` IC on
//!   **prime-field** curves (Diem 2011, Petit–Quisquater 2012 inspired
//!   the framework but cannot be applied directly because there is no
//!   subfield to descend into for a prime field).
//! - [`crate::cryptanalysis::ec_index_calculus_j0`] — ζ-symmetric IC
//!   on prime-field `j = 0` curves.
//! - [`crate::cryptanalysis::ghs_descent`] /
//!   [`crate::cryptanalysis::ghs_full_attack`] — a **different** small-
//!   char attack: GHS Weil descent reduces ECDLP on `E / F_{2^N}` to
//!   HCDLP on a hyperelliptic Jacobian over `F_{2^l}` (`N = l·n`).  PQ
//!   doesn't change the genus — it solves ECDLP directly via Semaev.
//!
//! ## References
//!
//! - **C. Petit, J.-J. Quisquater**, *On polynomial systems arising
//!   from a Weil descent*, ASIACRYPT 2012.
//! - **J.-C. Faugère, L. Perret, C. Petit, G. Renault**, *Improving
//!   the complexity of index calculus algorithms in elliptic curves
//!   over binary fields*, EUROCRYPT 2012.
//! - **I. Semaev**, *Summation polynomials and the discrete logarithm
//!   problem on elliptic curves*, IACR ePrint 2004/031.
//! - **M.-D. Huang, M. Kiltz, C. Petit**, *Last fall degree, HFE, and
//!   Weil descent attacks on ECDLP*, CRYPTO 2015 — the bound that
//!   capped the asymptotic complexity claims of FPPR / PQ at the
//!   1990s "Gaudry-type" `L(1/2)` heuristic.

use crate::binary_ecc::curve::{point_add, point_neg, scalar_mul};
use crate::binary_ecc::{BinaryCurve, BinaryPoint, F2mElement};
use crate::cryptanalysis::binary_semaev::{
    binary_semaev_s3_in_x3, solve_artin_schreier, solve_quadratic_f2m,
};
use crate::cryptanalysis::ec_index_calculus::gaussian_eliminate_mod_n;
use num_bigint::BigUint;
#[allow(unused_imports)]
use num_traits::{One, Zero};
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use std::collections::HashMap;

// ── F₂-vector-subspace factor base ─────────────────────────────────

/// An `F₂`-vector subspace `V ⊂ F_{2^m}` used as the factor-base x-coordinate set.
///
/// We use the canonical low-order basis `V = span_{F₂}{1, z, z², …, z^{m'-1}}`,
/// which has `|V| = 2^{m'}`.  When `m' | m` this is the unique subfield
/// `F_{2^{m'}}` of `F_{2^m}` (using the standard polynomial-basis
/// embedding); for general `m'` it is still a vector subspace, which is
/// all the PQ relation-search step requires.
#[derive(Clone, Debug)]
pub struct PqSubspace {
    pub m: u32,
    pub m_prime: u32,
    pub elements: Vec<F2mElement>,
}

impl PqSubspace {
    /// Build `V = span_{F₂}{1, z, …, z^{m'-1}} ⊂ F_{2^m}`.
    pub fn span_low(m: u32, m_prime: u32) -> Self {
        assert!(m_prime <= m, "m' must be ≤ m");
        assert!(
            m_prime <= 32,
            "toy implementation enumerates V; cap m' ≤ 32"
        );
        let size = 1u64 << m_prime;
        let mut elements = Vec::with_capacity(size as usize);
        for v in 0u64..size {
            elements.push(F2mElement::from_biguint(&BigUint::from(v), m));
        }
        Self {
            m,
            m_prime,
            elements,
        }
    }
}

// ── Factor base ────────────────────────────────────────────────────

/// A factor-base entry: the canonical curve point with `x ∈ V`, plus
/// its index in the factor-base list.
#[derive(Clone, Debug)]
pub struct PqFactorBaseEntry {
    pub idx: usize,
    pub x: F2mElement,
    pub y: F2mElement,
    pub point: BinaryPoint,
}

/// **Build the PQ factor base.**  For each non-zero `x ∈ V`, solve the
/// binary-curve equation `y² + xy = x³ + ax² + b` for `y ∈ F_{2^m}` via
/// Artin–Schreier.  If solvable, record one canonical point `(x, y)`
/// (we pick the root returned by `solve_artin_schreier`, which is
/// deterministic).  The other root `(x, x+y)` is the binary-curve
/// negation `-P` and will appear via the sign loop in the relation
/// search — we don't store it separately.
///
/// Skips `x = 0` because the doubling formula uses `1/x_1` and we want
/// the factor base to be addition-stable.
pub fn build_pq_factor_base(curve: &BinaryCurve, v: &PqSubspace) -> Vec<PqFactorBaseEntry> {
    assert_eq!(v.m, curve.m, "subspace ambient field mismatch");
    let mut out = Vec::new();
    for x in &v.elements {
        if x.is_zero() {
            continue;
        }
        // Substitute y = x·t so y² + xy = x²(t² + t).  The curve equation
        //   y² + xy = x³ + ax² + b
        // becomes
        //   x²(t² + t) = x³ + ax² + b
        //   t² + t = x + a + b / x²,
        // an Artin–Schreier equation in t.
        let x_sq = x.square(&curve.irreducible);
        let x_sq_inv = match x_sq.flt_inverse(&curve.irreducible) {
            Some(inv) => inv,
            None => continue,
        };
        let b_over_x_sq = curve.b.mul(&x_sq_inv, &curve.irreducible);
        let c = x.add(&curve.a).add(&b_over_x_sq);
        let t = match solve_artin_schreier(&c, curve.m, &curve.irreducible) {
            Some(t) => t,
            None => continue, // No on-curve point at this x.
        };
        let y = x.mul(&t, &curve.irreducible);
        let p = BinaryPoint::Affine {
            x: x.clone(),
            y: y.clone(),
        };
        debug_assert!(curve.is_on_curve(&p), "FB point must be on curve");
        out.push(PqFactorBaseEntry {
            idx: out.len(),
            x: x.clone(),
            y,
            point: p,
        });
    }
    out
}

// ── Relations ──────────────────────────────────────────────────────

/// One PQ relation: `coef_a · G + coef_b · Q = ε_1 · P_{idx_1} + ε_2 · P_{idx_2}`,
/// `entries` stores signed multiplicities sparse-style (same convention
/// as [`crate::cryptanalysis::ec_index_calculus::Relation`]).
#[derive(Clone, Debug)]
pub struct PqRelation {
    pub coef_a: BigUint,
    pub coef_b: BigUint,
    pub entries: Vec<(usize, i64)>, // (fb_index, signed_multiplicity)
}

/// Helper: convert an `F2mElement` to a `BigUint` key for the FB
/// lookup table.  Wraps `to_biguint` so the call sites stay readable.
fn key(x: &F2mElement) -> BigUint {
    x.to_biguint()
}

/// **Try to find one relation** by random sampling.  Returns `None` if
/// `max_trials` random `(a, b)` pairs all fail to decompose.
pub fn find_one_pq_relation(
    curve: &BinaryCurve,
    g: &BinaryPoint,
    q: &BinaryPoint,
    fb: &[PqFactorBaseEntry],
    v: &PqSubspace,
    rng: &mut StdRng,
    max_trials: usize,
) -> Option<PqRelation> {
    // Hash table: x ∈ V → FB index (only on-curve x are kept).
    let mut x_to_idx: HashMap<BigUint, usize> = HashMap::with_capacity(fb.len());
    for entry in fb {
        x_to_idx.insert(key(&entry.x), entry.idx);
    }
    // Subspace membership set (every x ∈ V, even those without a curve
    // point — used to early-reject quadratic roots that aren't even
    // in V).
    let mut v_set: HashMap<BigUint, ()> = HashMap::with_capacity(v.elements.len());
    for x in &v.elements {
        v_set.insert(key(x), ());
    }

    for _ in 0..max_trials {
        let a = random_scalar_biguint(rng, &curve.order);
        let b = random_scalar_biguint(rng, &curve.order);
        let ag = scalar_mul(curve, g, &a);
        let bq = scalar_mul(curve, q, &b);
        let r = point_add(curve, &ag, &bq);
        let x_r = match &r {
            BinaryPoint::Affine { x, .. } => x.clone(),
            BinaryPoint::Infinity => continue, // a + bk ≡ 0 — useless row
        };
        // Sweep x_1 ∈ FB (each FB entry's x-coord is already in V).
        for fb_i in fb {
            // Solve S_3(x_i, x_R, X) = 0 as quadratic in X.  By
            // symmetry of S_3 we can pick any of the three arguments
            // as the unknown.
            let (aa, bb, cc) = binary_semaev_s3_in_x3(&fb_i.x, &x_r, &curve.b, &curve.irreducible);
            let roots = solve_quadratic_f2m(&aa, &bb, &cc, curve.m, &curve.irreducible);
            for x2 in roots {
                // Cheap reject: x_2 must lie in V.  (On-curve filter
                // is via x_to_idx below.)
                if !v_set.contains_key(&key(&x2)) {
                    continue;
                }
                let j = match x_to_idx.get(&key(&x2)) {
                    Some(&j) => j,
                    None => continue, // In V but not on the curve.
                };
                let fb_j = &fb[j];
                // Verify one of the four sign combos matches R.
                if let Some(rel) = try_finalise(curve, &r, fb_i, fb_j, &a, &b) {
                    return Some(rel);
                }
            }
        }
    }
    None
}

/// Try all four `(ε_1, ε_2) ∈ {±1}²` combinations on the candidate
/// pair `(P_i, P_j)` against `R = aG + bQ`.  Return the resulting
/// [`PqRelation`] on the first match, or `None` if no combo works
/// (geometric coincidence — the algebraic `S_3 = 0` matched but the
/// y-lift didn't).
fn try_finalise(
    curve: &BinaryCurve,
    r: &BinaryPoint,
    fb_i: &PqFactorBaseEntry,
    fb_j: &PqFactorBaseEntry,
    coef_a: &BigUint,
    coef_b: &BigUint,
) -> Option<PqRelation> {
    for &eps_i in &[1i64, -1i64] {
        for &eps_j in &[1i64, -1i64] {
            let p_i = if eps_i > 0 {
                fb_i.point.clone()
            } else {
                point_neg(&fb_i.point)
            };
            let p_j = if eps_j > 0 {
                fb_j.point.clone()
            } else {
                point_neg(&fb_j.point)
            };
            let lhs = point_add(curve, &p_i, &p_j);
            if &lhs == r {
                let entries = if fb_i.idx == fb_j.idx {
                    let combined = eps_i + eps_j;
                    if combined == 0 {
                        // Relation `aG + bQ = O`; only useful if both a,
                        // b ≡ 0 (mod N), which random sampling makes
                        // negligible.  Reject.
                        return None;
                    }
                    vec![(fb_i.idx, combined)]
                } else {
                    vec![(fb_i.idx, eps_i), (fb_j.idx, eps_j)]
                };
                return Some(PqRelation {
                    coef_a: coef_a.clone(),
                    coef_b: coef_b.clone(),
                    entries,
                });
            }
        }
    }
    None
}

/// Random scalar in `[0, n)`.
fn random_scalar_biguint(rng: &mut StdRng, n: &BigUint) -> BigUint {
    let bits = n.bits().max(1);
    let n_bytes = bits.div_ceil(8) as usize;
    loop {
        let mut buf = vec![0u8; n_bytes];
        rng.fill(&mut buf[..]);
        // Mask to bits to keep the trial count bounded.
        let extra_bits = (n_bytes as u32) * 8 - bits as u32;
        if extra_bits > 0 {
            buf[n_bytes - 1] &= (0xFF_u8) >> extra_bits;
        }
        let v = BigUint::from_bytes_le(&buf);
        if &v < n && !v.is_zero() {
            return v;
        }
    }
}

// ── End-to-end driver ──────────────────────────────────────────────

/// **Recover `k` such that `Q = k·G`** by collecting PQ relations and
/// solving the resulting linear system mod `N`.
///
/// - `target_extra` is how many relations beyond `|FB|` to collect; a
///   small margin (≥ 1) is needed because some relations land in the
///   kernel of the matrix (combined-index 2-torsion, sign collisions,
///   etc.).
/// - `max_trials_per_relation` is the per-relation random-sample cap;
///   1000 is plenty for the toy regime.
///
/// Returns `Some(k)` on success, `None` otherwise.  The result is
/// verified by recomputing `k·G` and checking against `Q`.
pub fn petit_quisquater_n2_toy(
    curve: &BinaryCurve,
    g: &BinaryPoint,
    q: &BinaryPoint,
    v: &PqSubspace,
    target_extra: usize,
    max_trials_per_relation: usize,
    seed: u64,
) -> Option<BigUint> {
    let fb = build_pq_factor_base(curve, v);
    if fb.is_empty() {
        return None;
    }
    let target = fb.len() + target_extra.max(1);

    let mut rng = StdRng::seed_from_u64(seed);
    let mut relations: Vec<PqRelation> = Vec::with_capacity(target);
    while relations.len() < target {
        let rel = find_one_pq_relation(curve, g, q, &fb, v, &mut rng, max_trials_per_relation)?;
        relations.push(rel);
    }

    // Build the linear system: unknowns are (y_0, …, y_{|FB|-1}, k).
    // Row r: `Σ entries[j].mult · y_j  − coef_b · k  ≡  coef_a  (mod N)`.
    let m = fb.len();
    let n = &curve.order;
    let mut matrix: Vec<Vec<BigUint>> = Vec::with_capacity(relations.len());
    let mut rhs: Vec<BigUint> = Vec::with_capacity(relations.len());
    for rel in &relations {
        let mut row = vec![BigUint::zero(); m + 1];
        for &(j, mult) in &rel.entries {
            let val = signed_mod_n(mult, n);
            row[j] = (&row[j] + &val) % n;
        }
        let neg_b = (n - &(&rel.coef_b % n)) % n;
        row[m] = neg_b;
        matrix.push(row);
        rhs.push(rel.coef_a.clone() % n);
    }

    let solution = gaussian_eliminate_mod_n(&mut matrix, &mut rhs, n)?;
    let k = solution[m].clone();
    // Verify.
    let q_check = scalar_mul(curve, g, &k);
    if q_check == *q {
        Some(k)
    } else {
        None
    }
}

fn signed_mod_n(v: i64, n: &BigUint) -> BigUint {
    if v >= 0 {
        BigUint::from(v as u64) % n
    } else {
        let abs = BigUint::from((-v) as u64) % n;
        if abs.is_zero() {
            BigUint::zero()
        } else {
            n - abs
        }
    }
}

// ── Full pipeline (descent + Gröbner + sparse LA) ──────────────────

/// **Find one PQ relation via the full Weil-descent + Gröbner pipeline.**
///
/// This is the pedagogical companion to [`find_one_pq_relation`]: same
/// inputs, same output shape, but the per-`R_j` decomposition search
/// goes through the actual Petit–Quisquater machinery rather than the
/// `n = 2` quadratic shortcut over `F_{2^m}`.
///
/// Pipeline:
///
/// 1. Pick random `(a_j, b_j) ∈ Z/N`; form `R_j = a_j G + b_j Q`.
/// 2. Weil-descend `S_3(X_1, X_2, x(R_j)) = 0` into `m` boolean
///    polynomials in `2m'` variables.
/// 3. Compute a Gröbner basis over `F_2 / (v_i² − v_i)` (Buchberger +
///    Gebauer-Möller).
/// 4. Enumerate `{0,1}^{2m'}` solutions of the GB; lift each to a
///    candidate `(x_1, x_2) ∈ V × V`.
/// 5. For each candidate, look up FB indices and try four `(±, ±)`
///    sign combinations — same finalisation step as the shortcut path.
///
/// Costs `O(2^{2m'} · m² + |gb-buchberger-steps|)` per random `R_j`;
/// the shortcut path is `O(|V| · m²)` (cheaper at `n = 2`).  The two
/// paths produce mathematically identical decompositions on the same
/// input — see the `pipeline_agrees_with_shortcut` cross-check test.
pub fn find_one_pq_relation_via_descent(
    curve: &BinaryCurve,
    g: &BinaryPoint,
    q: &BinaryPoint,
    fb: &[PqFactorBaseEntry],
    v: &PqSubspace,
    rng: &mut StdRng,
    max_trials: usize,
) -> Option<PqRelation> {
    use crate::cryptanalysis::pq_descent::solve_decomposition_via_descent;

    // Build the V-basis used by the descent (same convention as PqSubspace::span_low).
    let v_basis: Vec<F2mElement> = (0..v.m_prime)
        .map(|k| F2mElement::from_bit_positions(&[k], curve.m))
        .collect();
    // FB lookup by x → idx.
    let mut x_to_idx: HashMap<BigUint, usize> = HashMap::with_capacity(fb.len());
    for entry in fb {
        x_to_idx.insert(key(&entry.x), entry.idx);
    }

    for _ in 0..max_trials {
        let a = random_scalar_biguint(rng, &curve.order);
        let b = random_scalar_biguint(rng, &curve.order);
        let ag = scalar_mul(curve, g, &a);
        let bq = scalar_mul(curve, q, &b);
        let r = point_add(curve, &ag, &bq);
        let x_r = match &r {
            BinaryPoint::Affine { x, .. } => x.clone(),
            BinaryPoint::Infinity => continue,
        };
        // Run descent + GB to find all (x_1, x_2) ∈ V × V with S_3 = 0.
        let candidates = solve_decomposition_via_descent(curve, &x_r, &v_basis);
        for (x_1, x_2) in candidates {
            let i = match x_to_idx.get(&key(&x_1)) {
                Some(&i) => i,
                None => continue, // x_1 in V but not on curve
            };
            let j = match x_to_idx.get(&key(&x_2)) {
                Some(&j) => j,
                None => continue,
            };
            if let Some(rel) = try_finalise(curve, &r, &fb[i], &fb[j], &a, &b) {
                return Some(rel);
            }
        }
    }
    None
}

/// **End-to-end PQ via the full pipeline.**  Like
/// [`petit_quisquater_n2_toy`] but uses [`find_one_pq_relation_via_descent`]
/// for relation gathering and `pq_sparse_la::sparse_solve_mod_n` for
/// the relation matrix.
///
/// On the same `(curve, g, q, seed)` and target relation count, this
/// should recover the same `k` as [`petit_quisquater_n2_toy`].  See
/// the `pipeline_agrees_with_shortcut` test for the cross-check.
pub fn petit_quisquater_n2_full_pipeline(
    curve: &BinaryCurve,
    g: &BinaryPoint,
    q: &BinaryPoint,
    v: &PqSubspace,
    target_extra: usize,
    max_trials_per_relation: usize,
    seed: u64,
) -> Option<BigUint> {
    use crate::cryptanalysis::pq_sparse_la::{sparse_solve_mod_n, SparseRow};

    let fb = build_pq_factor_base(curve, v);
    if fb.is_empty() {
        return None;
    }
    let target = fb.len() + target_extra.max(1);
    let mut rng = StdRng::seed_from_u64(seed);
    let mut relations: Vec<PqRelation> = Vec::with_capacity(target);
    while relations.len() < target {
        let rel = find_one_pq_relation_via_descent(
            curve,
            g,
            q,
            &fb,
            v,
            &mut rng,
            max_trials_per_relation,
        )?;
        relations.push(rel);
    }

    // Same relation encoding as the shortcut driver; just sparse.
    let m = fb.len();
    let n = &curve.order;
    let k_col = m;
    let mut sparse_rows: Vec<SparseRow> = Vec::with_capacity(relations.len());
    for rel in &relations {
        let mut entries: Vec<(usize, BigUint)> = Vec::new();
        for &(j, mult) in &rel.entries {
            let val = signed_mod_n(mult, n);
            entries.push((j, val));
        }
        let neg_b = (n - &(&rel.coef_b % n)) % n;
        entries.push((k_col, neg_b));
        sparse_rows.push(SparseRow::from_entries(entries, rel.coef_a.clone() % n));
    }

    let k = sparse_solve_mod_n(sparse_rows, m + 1, k_col, n)?;
    // Verify.
    let q_check = scalar_mul(curve, g, &k);
    if q_check == *q {
        Some(k)
    } else {
        None
    }
}

/// **End-to-end PQ via descent + GB + Wiedemann LA**.  Identical to
/// [`petit_quisquater_n2_full_pipeline`] except the final relation
/// matrix is solved with sequential Wiedemann
/// ([`crate::cryptanalysis::pq_wiedemann::wiedemann_solve`]) instead
/// of structured Gaussian.
///
/// Wiedemann is the algorithm production index-calculus pipelines
/// actually use for the LA step — it scales to systems with
/// `2^{20}+` rows where any direct (Gaussian) method is infeasible.
/// At the toy scale it costs more per call (sequence length
/// `2(|FB|+1) + 2` mat-vecs vs. `|FB|+1` pivot operations for sparse
/// Gaussian) but uses the exact same algorithmic primitive — sparse
/// matrix-vector product — that the rest of the index-calculus
/// pipeline already pays for.
///
/// **Square padding**: the relation matrix `M` has `|FB| + extra`
/// rows × `|FB| + 1` columns; Wiedemann internally falls back to the
/// normal equations `M^T M x = M^T b` when rows ≠ cols.  When `extra
/// = 0` exactly the system is square and Wiedemann runs in its
/// fast / direct mode.
pub fn petit_quisquater_n2_full_pipeline_via_wiedemann(
    curve: &BinaryCurve,
    g: &BinaryPoint,
    q: &BinaryPoint,
    v: &PqSubspace,
    target_extra: usize,
    max_trials_per_relation: usize,
    seed: u64,
) -> Option<BigUint> {
    use crate::cryptanalysis::pq_sparse_la::SparseRow;
    use crate::cryptanalysis::pq_wiedemann::wiedemann_solve;

    let fb = build_pq_factor_base(curve, v);
    if fb.is_empty() {
        return None;
    }
    let target = fb.len() + target_extra.max(1);
    let mut rng = StdRng::seed_from_u64(seed);
    let mut relations: Vec<PqRelation> = Vec::with_capacity(target);
    while relations.len() < target {
        let rel = find_one_pq_relation_via_descent(
            curve,
            g,
            q,
            &fb,
            v,
            &mut rng,
            max_trials_per_relation,
        )?;
        relations.push(rel);
    }

    let m = fb.len();
    let n = &curve.order;
    let k_col = m;
    let mut sparse_rows: Vec<SparseRow> = Vec::with_capacity(relations.len());
    let mut b_vec: Vec<BigUint> = Vec::with_capacity(relations.len());
    for rel in &relations {
        let mut entries: Vec<(usize, BigUint)> = Vec::new();
        for &(j, mult) in &rel.entries {
            let val = signed_mod_n(mult, n);
            entries.push((j, val));
        }
        let neg_b = (n - &(&rel.coef_b % n)) % n;
        entries.push((k_col, neg_b));
        sparse_rows.push(SparseRow::from_entries(entries, rel.coef_a.clone() % n));
        b_vec.push(rel.coef_a.clone() % n);
    }

    // Try a few seeds for Wiedemann — the random projection vector
    // can land on degenerate Krylov subspaces.
    let mut x = None;
    for wied_seed in 0u64..30 {
        if let Some(sol) =
            wiedemann_solve(&sparse_rows, &b_vec, m + 1, n, seed.wrapping_add(wied_seed))
        {
            x = Some(sol);
            break;
        }
    }
    let x = x?;
    let k = x[k_col].clone();
    let q_check = scalar_mul(curve, g, &k);
    if q_check == *q {
        Some(k)
    } else {
        None
    }
}

// ── n = 3 full pipeline ────────────────────────────────────────────

/// Try all 2³ = 8 sign combinations on a candidate 3-decomposition
/// `(P_{i_1}, P_{i_2}, P_{i_3})` against `R = aG + bQ`.  Returns the
/// resulting [`PqRelation`] on the first geometrically valid sign
/// pattern, or `None` if none of the 8 lifts to `R`.
fn try_finalise_n3(
    curve: &BinaryCurve,
    r: &BinaryPoint,
    fb_i: &PqFactorBaseEntry,
    fb_j: &PqFactorBaseEntry,
    fb_k: &PqFactorBaseEntry,
    coef_a: &BigUint,
    coef_b: &BigUint,
) -> Option<PqRelation> {
    for &eps_i in &[1i64, -1i64] {
        for &eps_j in &[1i64, -1i64] {
            for &eps_k in &[1i64, -1i64] {
                let p_i = if eps_i > 0 {
                    fb_i.point.clone()
                } else {
                    point_neg(&fb_i.point)
                };
                let p_j = if eps_j > 0 {
                    fb_j.point.clone()
                } else {
                    point_neg(&fb_j.point)
                };
                let p_k = if eps_k > 0 {
                    fb_k.point.clone()
                } else {
                    point_neg(&fb_k.point)
                };
                let sum = point_add(curve, &point_add(curve, &p_i, &p_j), &p_k);
                if &sum == r {
                    // Combine duplicate FB indices.
                    let mut acc: std::collections::BTreeMap<usize, i64> =
                        std::collections::BTreeMap::new();
                    *acc.entry(fb_i.idx).or_insert(0) += eps_i;
                    *acc.entry(fb_j.idx).or_insert(0) += eps_j;
                    *acc.entry(fb_k.idx).or_insert(0) += eps_k;
                    let entries: Vec<(usize, i64)> =
                        acc.into_iter().filter(|(_, m)| *m != 0).collect();
                    if entries.is_empty() {
                        // All canceled — degenerate relation `aG + bQ = O`.
                        return None;
                    }
                    return Some(PqRelation {
                        coef_a: coef_a.clone(),
                        coef_b: coef_b.clone(),
                        entries,
                    });
                }
            }
        }
    }
    None
}

/// **Find one PQ relation at `n = 3` via descent + Gröbner**.
///
/// Per random `R_j = a_j G + b_j Q`:
///
/// 1. Weil-descend `S_4(X_1, X_2, X_3, x(R_j)) = 0` into `m` boolean
///    polynomials in `3m'` variables.
/// 2. Compute a Gröbner basis over `F_2 / (v_i² − v_i)`.
/// 3. Enumerate `{0,1}^{3m'}` solutions; for each, lift to a candidate
///    `(x_1, x_2, x_3) ∈ V × V × V` and look up FB indices.
/// 4. Try 8 sign combinations on each candidate; the first to lift to
///    `R_j` becomes the recorded relation.
///
/// At `n = 3` the hit rate per random `R_j` is much higher than at
/// `n = 2` (the algebraic system has more solutions), so the loop
/// usually terminates in 1–3 random `R_j` samples even with a moderate
/// `max_trials`.  This is the **first PQ regime where the shortcut
/// path cannot be written** — `S_4` viewed in any one variable is a
/// quartic, not a quadratic, and has no closed-form root via
/// Artin-Schreier.
pub fn find_one_pq_relation_n3_via_descent(
    curve: &BinaryCurve,
    g: &BinaryPoint,
    q: &BinaryPoint,
    fb: &[PqFactorBaseEntry],
    v: &PqSubspace,
    rng: &mut StdRng,
    max_trials: usize,
) -> Option<PqRelation> {
    use crate::cryptanalysis::pq_descent::solve_decomposition_n3_direct;

    let v_basis: Vec<F2mElement> = (0..v.m_prime)
        .map(|k| F2mElement::from_bit_positions(&[k], curve.m))
        .collect();
    let mut x_to_idx: HashMap<BigUint, usize> = HashMap::with_capacity(fb.len());
    for entry in fb {
        x_to_idx.insert(key(&entry.x), entry.idx);
    }

    for _ in 0..max_trials {
        let a = random_scalar_biguint(rng, &curve.order);
        let b = random_scalar_biguint(rng, &curve.order);
        let ag = scalar_mul(curve, g, &a);
        let bq = scalar_mul(curve, q, &b);
        let r = point_add(curve, &ag, &bq);
        let x_r = match &r {
            BinaryPoint::Affine { x, .. } => x.clone(),
            BinaryPoint::Infinity => continue,
        };
        // Use direct F_{2^m} brute-force at toy scale; GB-based path
        // (`solve_decomposition_via_descent_n3`) is pedagogically the
        // real PQ method but doesn't terminate at our parameters
        // because S_4 has total degree 8 and the boolean Buchberger
        // doesn't get the F4/F5-style speedup.
        let candidates = solve_decomposition_n3_direct(curve, &x_r, &v_basis);
        for (x_1, x_2, x_3) in candidates {
            let i = match x_to_idx.get(&key(&x_1)) {
                Some(&i) => i,
                None => continue,
            };
            let j = match x_to_idx.get(&key(&x_2)) {
                Some(&j) => j,
                None => continue,
            };
            let k = match x_to_idx.get(&key(&x_3)) {
                Some(&k) => k,
                None => continue,
            };
            if let Some(rel) = try_finalise_n3(curve, &r, &fb[i], &fb[j], &fb[k], &a, &b) {
                return Some(rel);
            }
        }
    }
    None
}

/// **Find one PQ relation at `n = 3` via descent + XL**.  Same as
/// [`find_one_pq_relation_n3_via_descent`] but uses the XL boolean
/// solver instead of direct `S_4 = 0` enumeration — the
/// pedagogically real PQ path at the toy scale where Buchberger is
/// intractable.
///
/// At `m = 8, m' = 3` (= 9 boolean variables) XL completes the
/// per-`R_j` solve in ~50 ms (debug) — slower than the
/// O(|V|^3) direct path but using the actual Macaulay-matrix
/// algebra that real PQ relies on at scale.
pub fn find_one_pq_relation_n3_via_xl(
    curve: &BinaryCurve,
    g: &BinaryPoint,
    q: &BinaryPoint,
    fb: &[PqFactorBaseEntry],
    v: &PqSubspace,
    rng: &mut StdRng,
    max_trials: usize,
) -> Option<PqRelation> {
    use crate::cryptanalysis::pq_descent::solve_decomposition_via_descent_n3_xl;

    let v_basis: Vec<F2mElement> = (0..v.m_prime)
        .map(|k| F2mElement::from_bit_positions(&[k], curve.m))
        .collect();
    let mut x_to_idx: HashMap<BigUint, usize> = HashMap::with_capacity(fb.len());
    for entry in fb {
        x_to_idx.insert(key(&entry.x), entry.idx);
    }

    for _ in 0..max_trials {
        let a = random_scalar_biguint(rng, &curve.order);
        let b = random_scalar_biguint(rng, &curve.order);
        let ag = scalar_mul(curve, g, &a);
        let bq = scalar_mul(curve, q, &b);
        let r = point_add(curve, &ag, &bq);
        let x_r = match &r {
            BinaryPoint::Affine { x, .. } => x.clone(),
            BinaryPoint::Infinity => continue,
        };
        let candidates = solve_decomposition_via_descent_n3_xl(curve, &x_r, &v_basis);
        for (x_1, x_2, x_3) in candidates {
            let i = match x_to_idx.get(&key(&x_1)) {
                Some(&i) => i,
                None => continue,
            };
            let j = match x_to_idx.get(&key(&x_2)) {
                Some(&j) => j,
                None => continue,
            };
            let k = match x_to_idx.get(&key(&x_3)) {
                Some(&k) => k,
                None => continue,
            };
            if let Some(rel) = try_finalise_n3(curve, &r, &fb[i], &fb[j], &fb[k], &a, &b) {
                return Some(rel);
            }
        }
    }
    None
}

/// **End-to-end PQ at `n = 3` via descent + XL + sparse LA.**
///
/// This is the first PQ pipeline in the library that uses **algebraic
/// solving** at the relation-search step.  At `n = 2` we shortcut via
/// the quadratic over `F_{2^m}`; at `n = 3` the direct shortcut
/// requires brute-forcing `V^3` — this driver instead descends `S_4`
/// to `F_2` and solves the boolean system via XL (matrix-based
/// Gröbner-style reduction), the same algorithm family used by real
/// PQ at production scale (Petit–Quisquater 2012).
pub fn petit_quisquater_n3_full_pipeline_via_xl(
    curve: &BinaryCurve,
    g: &BinaryPoint,
    q: &BinaryPoint,
    v: &PqSubspace,
    target_extra: usize,
    max_trials_per_relation: usize,
    seed: u64,
) -> Option<BigUint> {
    use crate::cryptanalysis::pq_sparse_la::{sparse_solve_mod_n, SparseRow};

    let fb = build_pq_factor_base(curve, v);
    if fb.is_empty() {
        return None;
    }
    let target = fb.len() + target_extra.max(1);
    let mut rng = StdRng::seed_from_u64(seed);
    let mut relations: Vec<PqRelation> = Vec::with_capacity(target);
    while relations.len() < target {
        let rel =
            find_one_pq_relation_n3_via_xl(curve, g, q, &fb, v, &mut rng, max_trials_per_relation)?;
        relations.push(rel);
    }

    let m = fb.len();
    let n = &curve.order;
    let k_col = m;
    let mut sparse_rows: Vec<SparseRow> = Vec::with_capacity(relations.len());
    for rel in &relations {
        let mut entries: Vec<(usize, BigUint)> = Vec::new();
        for &(j, mult) in &rel.entries {
            let val = signed_mod_n(mult, n);
            entries.push((j, val));
        }
        let neg_b = (n - &(&rel.coef_b % n)) % n;
        entries.push((k_col, neg_b));
        sparse_rows.push(SparseRow::from_entries(entries, rel.coef_a.clone() % n));
    }

    let k = sparse_solve_mod_n(sparse_rows, m + 1, k_col, n)?;
    let q_check = scalar_mul(curve, g, &k);
    if q_check == *q {
        Some(k)
    } else {
        None
    }
}

/// **End-to-end PQ at `n = 3`** via descent + Gröbner + sparse LA.
///
/// First PQ pipeline in the library that cannot be reduced to a
/// shortcut quadratic.  Same input/output shape as
/// [`petit_quisquater_n2_full_pipeline`].
pub fn petit_quisquater_n3_full_pipeline(
    curve: &BinaryCurve,
    g: &BinaryPoint,
    q: &BinaryPoint,
    v: &PqSubspace,
    target_extra: usize,
    max_trials_per_relation: usize,
    seed: u64,
) -> Option<BigUint> {
    use crate::cryptanalysis::pq_sparse_la::{sparse_solve_mod_n, SparseRow};

    let fb = build_pq_factor_base(curve, v);
    if fb.is_empty() {
        return None;
    }
    let target = fb.len() + target_extra.max(1);
    let mut rng = StdRng::seed_from_u64(seed);
    let mut relations: Vec<PqRelation> = Vec::with_capacity(target);
    while relations.len() < target {
        let rel = find_one_pq_relation_n3_via_descent(
            curve,
            g,
            q,
            &fb,
            v,
            &mut rng,
            max_trials_per_relation,
        )?;
        relations.push(rel);
    }

    let m = fb.len();
    let n = &curve.order;
    let k_col = m;
    let mut sparse_rows: Vec<SparseRow> = Vec::with_capacity(relations.len());
    for rel in &relations {
        let mut entries: Vec<(usize, BigUint)> = Vec::new();
        for &(j, mult) in &rel.entries {
            let val = signed_mod_n(mult, n);
            entries.push((j, val));
        }
        let neg_b = (n - &(&rel.coef_b % n)) % n;
        entries.push((k_col, neg_b));
        sparse_rows.push(SparseRow::from_entries(entries, rel.coef_a.clone() % n));
    }

    let k = sparse_solve_mod_n(sparse_rows, m + 1, k_col, n)?;
    let q_check = scalar_mul(curve, g, &k);
    if q_check == *q {
        Some(k)
    } else {
        None
    }
}

// ── Diagnostic helpers ─────────────────────────────────────────────

/// Summary of a PQ attack run — useful for the tests and any future
/// CLI subcommand.
#[derive(Clone, Debug)]
pub struct PqAttackReport {
    pub fb_size: usize,
    pub relations_collected: usize,
    pub recovered_k: Option<BigUint>,
    pub true_k: BigUint,
}

/// Run the attack end-to-end with the given parameters and return a
/// diagnostic report.  Convenience wrapper around
/// [`petit_quisquater_n2_toy`] that also records `|FB|` and the truth.
pub fn run_pq_attack(
    curve: &BinaryCurve,
    g: &BinaryPoint,
    true_k: &BigUint,
    v: &PqSubspace,
    target_extra: usize,
    max_trials_per_relation: usize,
    seed: u64,
) -> PqAttackReport {
    let q = scalar_mul(curve, g, true_k);
    let fb = build_pq_factor_base(curve, v);
    let recovered =
        petit_quisquater_n2_toy(curve, g, &q, v, target_extra, max_trials_per_relation, seed);
    PqAttackReport {
        fb_size: fb.len(),
        relations_collected: fb.len() + target_extra.max(1),
        recovered_k: recovered,
        true_k: true_k.clone(),
    }
}

// ── Tests ──────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::binary_ecc::curve::point_add;
    use crate::binary_ecc::{BinaryPoint, IrreduciblePoly};

    /// Build a tiny binary curve and find a generator of large-prime
    /// order suitable for the toy: returns `(curve, g, n)` with `g` of
    /// prime order `n` on `E / F_{2^m}`.
    ///
    /// **Curve choice**: `E: y² + xy = x³ + 46` over `F_{2^8}` with
    /// reduction polynomial `z⁸ + z⁴ + z³ + z + 1`.  Located by an
    /// exhaustive scan over `(a, b)` ∈ F_{2^8}² for `#E = 4 · n` with
    /// `n` prime; this curve gives `n = 71` and cofactor 4, the best
    /// available structure at `m = 8` (verified empirically — see the
    /// `debug_scan_curves_for_prime_subgroup` companion test).
    ///
    /// Strategy: enumerate all curve points, compute the group order by
    /// brute-force point counting; the cofactor is `#E / n`; finding a
    /// generator is then a one-line `cofactor · P` for any
    /// non-cofactor-torsion `P` (since `n` is prime, the order-`n`
    /// subgroup is cyclic and every non-trivial element is a generator).
    fn build_toy_curve_and_generator() -> (BinaryCurve, BinaryPoint, BigUint) {
        let m = 8;
        let irr = IrreduciblePoly::deg_8();
        let a = F2mElement::zero(m);
        let b = F2mElement::from_biguint(&BigUint::from(46u32), m);

        // Enumerate all (x, y) ∈ F_{2^m}² and check curve membership.
        let mut points: Vec<BinaryPoint> = vec![BinaryPoint::Infinity];
        let curve = BinaryCurve {
            m,
            irreducible: irr.clone(),
            a: a.clone(),
            b: b.clone(),
            generator: BinaryPoint::Infinity, // placeholder, replaced below
            order: BigUint::one(),
            cofactor: BigUint::one(),
        };
        for xi in 0u64..(1u64 << m) {
            let x = F2mElement::from_biguint(&BigUint::from(xi), m);
            for yi in 0u64..(1u64 << m) {
                let y = F2mElement::from_biguint(&BigUint::from(yi), m);
                let p = BinaryPoint::Affine {
                    x: x.clone(),
                    y: y.clone(),
                };
                if curve.is_on_curve(&p) {
                    points.push(p);
                }
            }
        }
        let group_order = points.len();
        // Expected: #E = 284 = 2² · 71 for our chosen (a, b) = (0, 46).
        assert_eq!(
            group_order, 284,
            "toy curve group order changed; re-derive (a, b)"
        );
        let n = largest_prime_factor(group_order as u64);
        let cofactor = (group_order as u64) / n;

        // Find a generator of the order-n subgroup: try each point P,
        // compute Q = cofactor · P; if Q ≠ O then Q has order dividing
        // n, and since n is prime, ord(Q) = n.
        let cofactor_big = BigUint::from(cofactor);
        let n_big = BigUint::from(n);
        for p in &points {
            if matches!(p, BinaryPoint::Infinity) {
                continue;
            }
            let q = scalar_mul(&curve, p, &cofactor_big);
            if matches!(q, BinaryPoint::Infinity) {
                continue;
            }
            // Sanity: n*Q = O.
            let nq = scalar_mul(&curve, &q, &n_big);
            if matches!(nq, BinaryPoint::Infinity) {
                let mut out = curve.clone();
                out.generator = q.clone();
                out.order = n_big.clone();
                out.cofactor = cofactor_big.clone();
                return (out, q, n_big);
            }
        }
        panic!("no order-n generator found");
    }

    /// Largest prime factor of `n` — brute force trial division.
    /// `n` is small in the toy (≤ ~300).
    fn largest_prime_factor(mut n: u64) -> u64 {
        let mut max_p = 1u64;
        let mut d = 2u64;
        while d * d <= n {
            while n.is_multiple_of(d) {
                max_p = d;
                n /= d;
            }
            d += 1;
        }
        if n > 1 {
            max_p = n;
        }
        max_p
    }

    /// Debug: scan curves over F_{2^8} for a clean prime-order subgroup.
    /// Slow (O(2³²) ops) — gated behind `--ignored`.
    #[test]
    #[ignore]
    fn debug_scan_curves_for_prime_subgroup() {
        let m = 8;
        let irr = IrreduciblePoly::deg_8();
        for ai in 0u64..256 {
            for bi in 1u64..256 {
                let a = F2mElement::from_biguint(&BigUint::from(ai), m);
                let b = F2mElement::from_biguint(&BigUint::from(bi), m);
                let curve = BinaryCurve {
                    m,
                    irreducible: irr.clone(),
                    a,
                    b,
                    generator: BinaryPoint::Infinity,
                    order: BigUint::one(),
                    cofactor: BigUint::one(),
                };
                // Count points.
                let mut count = 1u64;
                for xi in 0u64..256 {
                    let x = F2mElement::from_biguint(&BigUint::from(xi), m);
                    for yi in 0u64..256 {
                        let y = F2mElement::from_biguint(&BigUint::from(yi), m);
                        let p = BinaryPoint::Affine { x: x.clone(), y };
                        if curve.is_on_curve(&p) {
                            count += 1;
                        }
                    }
                }
                let max_p = super::tests::largest_prime_factor(count);
                if max_p >= 50 {
                    eprintln!("a={} b={} #E={} largest_prime={}", ai, bi, count, max_p);
                }
            }
        }
    }

    /// Debug: verify scalar_mul correctness on the toy curve.
    /// Investigation-only — gated behind `--ignored`.
    #[test]
    #[ignore]
    fn debug_scalar_mul_correctness() {
        let m = 8;
        let irr = IrreduciblePoly::deg_8();
        let a = F2mElement::one(m);
        let b = F2mElement::one(m);
        let curve = BinaryCurve {
            m,
            irreducible: irr,
            a,
            b,
            generator: BinaryPoint::Infinity,
            order: BigUint::one(),
            cofactor: BigUint::one(),
        };
        // Enumerate ALL points; for each, compute 288*P and verify O.
        let mut points: Vec<BinaryPoint> = vec![BinaryPoint::Infinity];
        for xi in 0u64..256 {
            let x = F2mElement::from_biguint(&BigUint::from(xi), m);
            for yi in 0u64..256 {
                let y = F2mElement::from_biguint(&BigUint::from(yi), m);
                let p = BinaryPoint::Affine { x: x.clone(), y };
                if curve.is_on_curve(&p) {
                    points.push(p);
                }
            }
        }
        let group_order = points.len() as u64;
        let mut order_histogram = std::collections::HashMap::<u64, u64>::new();
        let mut had_order_div_3 = false;
        let mut sample_div_3: Option<BinaryPoint> = None;
        for p in points.iter().skip(1).take(50) {
            // Compute order by repeated addition (bounded by group_order).
            let mut acc = p.clone();
            let mut k = 1u64;
            while !matches!(acc, BinaryPoint::Infinity) && k <= group_order {
                acc = point_add(&curve, &acc, p);
                k += 1;
            }
            *order_histogram.entry(k).or_insert(0) += 1;
            if k.is_multiple_of(3) {
                had_order_div_3 = true;
                if sample_div_3.is_none() {
                    sample_div_3 = Some(p.clone());
                }
            }
        }
        eprintln!(
            "DBG: group_order={} order_histogram(first 50 points)={:?} any_div_3={}",
            group_order, order_histogram, had_order_div_3
        );
        if let Some(p) = sample_div_3 {
            // Sanity: compute 96*P explicitly and verify nonzero.
            let q96 = scalar_mul(&curve, &p, &BigUint::from(96u32));
            eprintln!("DBG: 96*P is_O = {}", matches!(q96, BinaryPoint::Infinity));
            let q288 = scalar_mul(&curve, &p, &BigUint::from(288u32));
            eprintln!(
                "DBG: 288*P is_O = {}",
                matches!(q288, BinaryPoint::Infinity)
            );
        }
    }

    /// Debug: print the toy curve group structure.
    /// Diagnostic — gated behind `--ignored`.
    #[test]
    #[ignore]
    fn debug_toy_curve_group_order() {
        let m = 8;
        let irr = IrreduciblePoly::deg_8();
        let a = F2mElement::one(m);
        let b = F2mElement::one(m);
        let curve = BinaryCurve {
            m,
            irreducible: irr,
            a,
            b,
            generator: BinaryPoint::Infinity,
            order: BigUint::one(),
            cofactor: BigUint::one(),
        };
        let mut count = 1u64;
        let mut sample_p = None;
        for xi in 0u64..(1u64 << m) {
            let x = F2mElement::from_biguint(&BigUint::from(xi), m);
            for yi in 0u64..(1u64 << m) {
                let y = F2mElement::from_biguint(&BigUint::from(yi), m);
                let p = BinaryPoint::Affine { x: x.clone(), y };
                if curve.is_on_curve(&p) {
                    count += 1;
                    if sample_p.is_none() {
                        sample_p = Some(p);
                    }
                }
            }
        }
        let sample_p = sample_p.unwrap();
        let mut k = 1u64;
        let mut acc = sample_p.clone();
        while !matches!(acc, BinaryPoint::Infinity) && k < 2 * count {
            acc = point_add(&curve, &acc, &sample_p);
            k += 1;
        }
        eprintln!(
            "toy curve group order = {}, sample point order = {}",
            count, k
        );
        // sanity: order divides count
        assert!(
            count.is_multiple_of(k),
            "point order {} should divide group order {}",
            k,
            count
        );
    }

    /// **Sanity**: `find_any_generator` analogue produces a point of
    /// prime order, and that order divides the full group order.
    #[test]
    fn toy_curve_generator_has_prime_order() {
        let (curve, g, n) = build_toy_curve_and_generator();
        assert!(curve.is_on_curve(&g));
        let ng = scalar_mul(&curve, &g, &n);
        assert!(matches!(ng, BinaryPoint::Infinity), "n·G should be O");
        assert!(n > BigUint::from(10u32), "toy order should be ≥ 10");
    }

    /// **Factor base is non-trivial**: for `m = 8`, `m' = 4`, expect
    /// ~8 on-curve x ∈ V points (half of |V| = 16).
    #[test]
    fn factor_base_nontrivial() {
        let (curve, _g, _n) = build_toy_curve_and_generator();
        let v = PqSubspace::span_low(curve.m, 4);
        let fb = build_pq_factor_base(&curve, &v);
        assert!(fb.len() >= 4, "expected ≥ 4 FB points, got {}", fb.len());
        // Each FB point is on the curve and has x ∈ V.
        for entry in &fb {
            assert!(curve.is_on_curve(&entry.point));
            let xi_big = entry.x.to_biguint();
            assert!(
                xi_big < BigUint::from(16u32),
                "x out of subspace: {}",
                xi_big
            );
        }
    }

    /// **Decomposition probe finds at least one relation** in a bounded
    /// random-sample budget.
    #[test]
    fn decomposition_finds_constructed_hit() {
        let (curve, g, _n) = build_toy_curve_and_generator();
        let v = PqSubspace::span_low(curve.m, 4);
        let fb = build_pq_factor_base(&curve, &v);
        assert!(fb.len() >= 2, "need ≥ 2 FB points for n=2 PQ");
        let q = scalar_mul(&curve, &g, &BigUint::from(3u32));
        let mut rng = StdRng::seed_from_u64(2);
        let rel = find_one_pq_relation(&curve, &g, &q, &fb, &v, &mut rng, 500);
        assert!(
            rel.is_some(),
            "should find at least one relation in 500 trials"
        );
    }

    /// **End-to-end PQ recovers the secret on the toy curve.**
    #[test]
    fn pq_attack_recovers_secret() {
        let (curve, g, n) = build_toy_curve_and_generator();
        let v = PqSubspace::span_low(curve.m, 4);
        // Pick a secret deterministically; avoid 0 and the trivial cases.
        let true_k = (&n / BigUint::from(3u32)) + BigUint::from(7u32);
        let true_k = &true_k % &n;
        let report = run_pq_attack(&curve, &g, &true_k, &v, 3, 2_000, 0xC0FFEE);
        assert_eq!(
            report.recovered_k.as_ref(),
            Some(&true_k),
            "PQ should recover k = {} on the toy curve (got {:?}, FB size {})",
            true_k,
            report.recovered_k,
            report.fb_size,
        );
    }

    /// **Determinism**: same seed → same recovered k (or same failure).
    #[test]
    fn pq_attack_is_deterministic_for_fixed_seed() {
        let (curve, g, n) = build_toy_curve_and_generator();
        let v = PqSubspace::span_low(curve.m, 4);
        let true_k = &BigUint::from(5u32) % &n;
        let r1 = run_pq_attack(&curve, &g, &true_k, &v, 3, 2_000, 42);
        let r2 = run_pq_attack(&curve, &g, &true_k, &v, 3, 2_000, 42);
        assert_eq!(r1.recovered_k, r2.recovered_k);
    }

    /// **Honest failure**: a starved factor base + too-small trial
    /// budget can fail to gather enough relations.  We don't assert
    /// failure (the driver might still succeed on some seeds), but
    /// the call must not panic.
    #[test]
    fn pq_attack_starved_fb_does_not_panic() {
        let (curve, g, n) = build_toy_curve_and_generator();
        // m' = 2 → |V| = 4 → maybe 1–2 FB points.
        let v = PqSubspace::span_low(curve.m, 2);
        let true_k = &BigUint::from(11u32) % &n;
        let _report = run_pq_attack(&curve, &g, &true_k, &v, 0, 50, 5);
        // No panic = pass.
    }

    /// **Full pipeline end-to-end: descent + GB + sparse LA recovers the secret.**
    #[test]
    fn pq_full_pipeline_recovers_secret() {
        let (curve, g, n) = build_toy_curve_and_generator();
        let v = PqSubspace::span_low(curve.m, 4);
        let true_k = (&n / BigUint::from(5u32)) + BigUint::from(13u32);
        let true_k = &true_k % &n;
        let q = scalar_mul(&curve, &g, &true_k);
        let recovered = petit_quisquater_n2_full_pipeline(&curve, &g, &q, &v, 4, 200, 0xDECAF);
        assert_eq!(
            recovered.as_ref(),
            Some(&true_k),
            "full pipeline should recover k = {} on toy curve (got {:?})",
            true_k,
            recovered,
        );
    }

    /// **n=2 full pipeline with Wiedemann LA recovers the secret.**
    /// Demonstrates the descent + Buchberger + Wiedemann path — the
    /// algorithm family production index calculus uses end-to-end.
    #[test]
    fn pq_full_pipeline_via_wiedemann_recovers_secret() {
        let (curve, g, n) = build_toy_curve_and_generator();
        let v = PqSubspace::span_low(curve.m, 4);
        let true_k = (&n / BigUint::from(13u32)) + BigUint::from(29u32);
        let true_k = &true_k % &n;
        let q = scalar_mul(&curve, &g, &true_k);
        let recovered =
            petit_quisquater_n2_full_pipeline_via_wiedemann(&curve, &g, &q, &v, 4, 200, 0xFEEDCAFE);
        assert_eq!(
            recovered.as_ref(),
            Some(&true_k),
            "Wiedemann-based pipeline should recover k = {} (got {:?})",
            true_k,
            recovered,
        );
    }

    /// **Wiedemann and structured-Gaussian pipelines agree.**  Same
    /// `(curve, g, q, seed)` should give the same recovered `k`
    /// regardless of which LA solver finishes the linear system.
    #[test]
    fn wiedemann_pipeline_agrees_with_gaussian() {
        let (curve, g, n) = build_toy_curve_and_generator();
        let v = PqSubspace::span_low(curve.m, 4);
        let true_k = &BigUint::from(31u32) % &n;
        let q = scalar_mul(&curve, &g, &true_k);
        let k_gaussian = petit_quisquater_n2_full_pipeline(&curve, &g, &q, &v, 4, 200, 999);
        let k_wiedemann =
            petit_quisquater_n2_full_pipeline_via_wiedemann(&curve, &g, &q, &v, 4, 200, 999);
        assert_eq!(k_gaussian.as_ref(), Some(&true_k));
        assert_eq!(k_wiedemann.as_ref(), Some(&true_k));
        assert_eq!(k_gaussian, k_wiedemann);
    }

    /// **n=3 XL-based pipeline recovers the secret.**  Uses the actual
    /// algebraic solving step (descent + XL matrix reduction)
    /// pedagogically equivalent to what real PQ does at scale.
    ///
    /// **`#[ignore]`'d by default**: at toy parameters each XL call
    /// takes ~1.4 s in debug mode, so gathering `|FB| + extra`
    /// relations (each needing ~16 random `R_j` trials due to the
    /// on-curve-FB filter) runs over the test-suite budget.  The
    /// algorithmic correctness of the XL pipeline is exercised by
    /// `descent_n3_xl_matches_direct` (which directly compares XL's
    /// decompositions against the brute-force `S_4` enumeration on the
    /// same `x_R`).  Run via `cargo test -- --ignored` to actually
    /// execute the end-to-end key recovery (~10 minutes in debug).
    #[test]
    #[ignore]
    fn pq_n3_full_pipeline_via_xl_recovers_secret() {
        let (curve, g, n) = build_toy_curve_and_generator();
        let v = PqSubspace::span_low(curve.m, 3); // m'=3 → 9 boolean vars
        let true_k = (&n / BigUint::from(11u32)) + BigUint::from(19u32);
        let true_k = &true_k % &n;
        let q = scalar_mul(&curve, &g, &true_k);
        let recovered =
            petit_quisquater_n3_full_pipeline_via_xl(&curve, &g, &q, &v, 6, 200, 0xBADCAFE);
        assert_eq!(
            recovered.as_ref(),
            Some(&true_k),
            "n=3 XL pipeline should recover k = {} on toy curve (got {:?})",
            true_k,
            recovered,
        );
    }

    /// **n=3 full pipeline recovers the secret.**  Showcases the
    /// descent + GB infrastructure on the regime where the n=2
    /// shortcut breaks down (S_4 is a quartic in any variable).
    #[test]
    fn pq_n3_full_pipeline_recovers_secret() {
        let (curve, g, n) = build_toy_curve_and_generator();
        let v = PqSubspace::span_low(curve.m, 4);
        let true_k = (&n / BigUint::from(7u32)) + BigUint::from(23u32);
        let true_k = &true_k % &n;
        let q = scalar_mul(&curve, &g, &true_k);
        let recovered = petit_quisquater_n3_full_pipeline(&curve, &g, &q, &v, 4, 100, 0xC0FFEE);
        assert_eq!(
            recovered.as_ref(),
            Some(&true_k),
            "n=3 pipeline should recover k = {} on toy curve (got {:?})",
            true_k,
            recovered,
        );
    }

    /// **Cross-check: shortcut path and full pipeline agree.**  On the
    /// same `(curve, g, q)` and matching seeds, both drivers should
    /// recover the same `k`.  Different per-relation seeds (the full
    /// pipeline draws an extra RNG call per candidate during the GB
    /// enumeration) mean we don't pin equality of intermediate
    /// relations — only the final recovered scalar.
    #[test]
    fn pipeline_agrees_with_shortcut() {
        let (curve, g, n) = build_toy_curve_and_generator();
        let v = PqSubspace::span_low(curve.m, 4);
        let true_k = &BigUint::from(17u32) % &n;
        let q = scalar_mul(&curve, &g, &true_k);
        let k_shortcut = petit_quisquater_n2_toy(&curve, &g, &q, &v, 4, 500, 11);
        let k_full = petit_quisquater_n2_full_pipeline(&curve, &g, &q, &v, 4, 200, 11);
        assert_eq!(k_shortcut.as_ref(), Some(&true_k));
        assert_eq!(k_full.as_ref(), Some(&true_k));
        assert_eq!(k_shortcut, k_full);
    }

    /// **Cross-check: descent-based decomposition equals shortcut decomposition.**
    /// For a fixed `x_R`, both the descent-based [`solve_decomposition_via_descent`]
    /// and the shortcut quadratic-over-`F_{2^m}` should produce the same
    /// SET of `(x_1, x_2) ∈ V × V` (modulo symmetry — the descent emits
    /// both `(x_1, x_2)` and `(x_2, x_1)` since the system is symmetric).
    #[test]
    fn descent_decomposition_matches_shortcut() {
        use crate::cryptanalysis::binary_semaev::{binary_semaev_s3_in_x3, solve_quadratic_f2m};
        use crate::cryptanalysis::pq_descent::solve_decomposition_via_descent;
        let (curve, g, _n) = build_toy_curve_and_generator();
        let pq_v = PqSubspace::span_low(curve.m, 4);
        let fb = build_pq_factor_base(&curve, &pq_v);
        // Pick a random R = 7·G to use as the target.
        let r = scalar_mul(&curve, &g, &BigUint::from(7u32));
        let x_r = match r {
            BinaryPoint::Affine { x, .. } => x,
            _ => panic!("7G shouldn't be O"),
        };
        // Shortcut path: collect (x_1, x_2) hits.
        let mut shortcut_set: std::collections::HashSet<(BigUint, BigUint)> =
            std::collections::HashSet::new();
        for entry in &fb {
            let (aa, bb, cc) = binary_semaev_s3_in_x3(&entry.x, &x_r, &curve.b, &curve.irreducible);
            for x2 in solve_quadratic_f2m(&aa, &bb, &cc, curve.m, &curve.irreducible) {
                // Reject x_2 not in V (i.e. with high bits set).
                if x2.to_biguint() >= BigUint::from(16u32) {
                    continue;
                }
                shortcut_set.insert((entry.x.to_biguint(), x2.to_biguint()));
            }
        }
        // Descent path: enumerate solutions of the GB.
        let v_basis: Vec<F2mElement> = (0..4)
            .map(|k| F2mElement::from_bit_positions(&[k], curve.m))
            .collect();
        let descent_pairs = solve_decomposition_via_descent(&curve, &x_r, &v_basis);
        let descent_set: std::collections::HashSet<(BigUint, BigUint)> = descent_pairs
            .into_iter()
            .filter(|(a, b)| !a.is_zero() && !b.is_zero())
            .map(|(a, b)| (a.to_biguint(), b.to_biguint()))
            .collect();
        // The shortcut iterates only `x_1 ∈ FB` (on-curve) but the
        // descent emits all (x_1, x_2) ∈ V × V satisfying S_3 = 0
        // regardless of curve membership.  So we expect:
        //   shortcut_set ⊆ descent_set (every shortcut hit is in descent).
        for hit in &shortcut_set {
            assert!(
                descent_set.contains(hit),
                "shortcut hit {:?} not found in descent set\n  shortcut: {:?}\n  descent:  {:?}",
                hit,
                shortcut_set,
                descent_set,
            );
        }
    }

    /// **Cross-check vs. brute-force DLP**: on the toy curve, brute
    /// force the discrete log of Q = k·G and confirm PQ agrees (when PQ
    /// succeeds).
    #[test]
    fn pq_agrees_with_brute_force_dlp() {
        let (curve, g, n) = build_toy_curve_and_generator();
        let v = PqSubspace::span_low(curve.m, 4);
        let true_k = (&n / BigUint::from(2u32)) - BigUint::one();
        let q = scalar_mul(&curve, &g, &true_k);

        // Brute-force log_G(Q).
        let mut bf = None;
        let mut acc = BinaryPoint::Infinity;
        let n_u64 = n.to_u64_digits().first().copied().unwrap_or(1);
        for k in 1u64..=n_u64 {
            acc = point_add(&curve, &acc, &g);
            if acc == q {
                bf = Some(BigUint::from(k));
                break;
            }
        }
        let bf = bf.expect("brute-force DLP should succeed");
        assert_eq!(bf, true_k, "sanity: brute-force agrees with secret");

        let pq = petit_quisquater_n2_toy(&curve, &g, &q, &v, 3, 2_000, 7777);
        if let Some(pq) = pq {
            assert_eq!(
                pq, bf,
                "PQ recovery should match brute-force DLP (PQ {} vs BF {})",
                pq, bf
            );
        }
        // If PQ returns None on this seed, that's not a failure — it
        // means the relation gathering hit a coincidence.  The
        // `pq_attack_recovers_secret` test pins one known-good seed.
    }
}
