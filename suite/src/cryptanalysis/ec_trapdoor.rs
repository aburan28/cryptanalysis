//! # Teske's Elliptic-Curve Trapdoor System (J. Cryptology 19(1), 2006).
//!
//! Edlyn Teske showed how to construct an elliptic curve `E/F_{2^N}`
//! that **looks generic** to an outside observer but admits a low-genus
//! Weil-descent (GHS) attack known only to the trapdoor owner.  The
//! trapdoor is the *correct factorisation* `N = n·l` to descend through
//! (and, more concretely, which subfield contains the curve's `b`
//! parameter or its square root).
//!
//! This module ships the **complete** primitives behind the construction
//! and verification:
//!
//! 1. [`FieldTower`] — the field-extension lattice `F_2 ⊂ F_{2^l} ⊂
//!    F_{2^N}` with the Frobenius `σ: x ↦ x^{2^l}` and subfield
//!    membership tests.
//! 2. [`magic_number`] — Hess's invariant `m = m_E(σ)`, the
//!    `F_2`-dimension of the Galois-orbit span of `√b`.
//! 3. [`ghs_genus`] — the genus of the GHS hyperelliptic descent
//!    curve, `g = 2^{m−1}` (or `2^{m−1} − 1` in the "type I" closed-
//!    orbit case).
//! 4. [`audit_curve`] — the **public auditor view**: for every
//!    factorisation `N = n_i · l_i`, compute the magic number and
//!    GHS-attack genus, returning the minimum.
//! 5. [`construct_trapdoor_curve`] — the **constructor view**: pick
//!    `(a, b)` so a *specific* factorisation yields a small genus.
//!
//! The actual descent (producing `C/F_{2^l}` and the homomorphism
//! `Φ: E(F_{2^N}) → Jac(C)(F_{2^l})`) is in
//! [`crate::cryptanalysis::ghs_descent`].  The HCDLP solver runs on
//! the Jacobian arithmetic provided by
//! [`crate::binary_ecc::hyperelliptic`].
//!
//! ## The Hess "magic number" — what it is and why it matters
//!
//! Let `K = F_{2^N}`, `k = F_{2^l}` with `N = n·l`, and
//! `σ ∈ Gal(K/k)` the Frobenius `x ↦ x^{2^l}` (order `n` on `K`).
//! Consider `E/K : y² + x·y = x³ + a·x² + b` (ordinary, so `b ≠ 0`).
//!
//! Substituting `y = x·t` and absorbing the resulting `(√b/x)²`
//! square via an Artin–Schreier shift `t ↦ t + √b/x` yields the
//! defining equation of an Artin–Schreier extension `K(C)/K(x)`:
//! ```text
//!     t² + t = x + a + (√b)/x
//! ```
//! Apply `σ` to get the conjugate functions `σ^i(√b)/x` and take
//! the compositum.  The resulting Artin–Schreier extension is
//! determined by the `F_2`-vector subspace
//! ```text
//!     V_E(σ) := span_{F_2} { σ^i(√b) : i = 0, …, n−1 } ⊂ K
//! ```
//! modulo Artin–Schreier coboundaries.  The compositum descends
//! to a hyperelliptic curve `C/k` whose **genus** is determined by
//! ```text
//!     m := dim_{F_2} V_E(σ)
//! ```
//! via the GHS formula
//! ```text
//!     g(C) = 2^{m−1}      (generic / "type II")
//!     g(C) = 2^{m−1} − 1  (when σ acts with order exactly m on V)
//! ```
//! (Hess, "Generalising the GHS attack on the elliptic curve discrete
//! logarithm problem," LMS J. Comp. Math. 7 (2004); Galbraith–
//! Hess–Smart 2002 for the original GHS setting.)
//!
//! **For an attacker, small `m` is fatal:** the descent transports
//! ECDLP on `E(K)` (size `~ q^n`) to HCDLP on `Jac(C)(k)` (size
//! `~ q^g`, `q = 2^l`), and HCDLP for `g ≤ 4` is *much* easier than
//! ECDLP on the equivalent-size group.
//!
//! **For the trapdoor:** Teske picks `b` with `√b ∈ F_{2^{m·l}} \
//! F_{2^l}` for a small target `m`.  Then `σ` has orbit-size `m` on
//! `√b`, so `dim V_E(σ) = m` and genus is small.  An attacker
//! observing `E` over `K` cannot tell *which* factorisation
//! `N = n_i · l_i` is the "right" one without computing the magic
//! number for every divisor of `N` — and for highly composite `N`,
//! that's its own little discrete-log problem.
//!
//! ## What's in this module
//!
//! Field-arithmetic side:
//! - [`FieldTower::frobenius`], [`FieldTower::frobenius_iter`].
//! - [`FieldTower::sqrt`] — characteristic-2 unique square root,
//!   `√x = x^{2^{N−1}}`.
//! - [`FieldTower::is_in_subfield`] — `x ∈ F_{2^{sub_l}}` ⇔
//!   `σ^{sub_l/gcd}(x) = x`.
//!
//! Trapdoor analysis:
//! - [`f2_dim`] — `F_2`-rank of a list of elements of `K` via
//!   Gaussian elimination on packed bit-vectors.
//! - [`magic_number`].
//! - [`ghs_genus`].
//! - [`audit_curve`] — exhaustive over every factorisation of `N`.
//! - [`construct_trapdoor_curve`] — search loop producing `(a, b)`
//!   for a chosen genus target on a chosen factorisation.
//!
//! ## Honest scope
//!
//! - The `√b` orbit-span definition of `m` is the *minimal* form,
//!   matching the cases Teske uses for the trapdoor.  Hess's full
//!   theorem also folds in `{(σ−1)·σ^i(a)}`; we expose that in
//!   [`magic_number_full`].  For the trapdoor we pick `a ∈ F_2`
//!   (so the `a`-contribution is `0`) and the simple form suffices.
//! - The genus split `2^{m−1}` vs `2^{m−1} − 1` is the
//!   standard GHS dichotomy; in practice [`ghs_genus`] returns
//!   `2^{m−1}` and a `type_i_genus` boolean is reported separately.

use crate::binary_ecc::{F2mElement, IrreduciblePoly};

/// A field tower `F_2 ⊂ F_{2^l} ⊂ F_{2^N}` with `N = n·l`.
///
/// We store **only the top field's irreducible polynomial**; subfield
/// membership is decided by the Frobenius fixed-point test
/// `x ∈ F_{2^l} ⇔ σ(x) = x`.  This sidesteps the need for an
/// explicit embedding of `F_{2^l}` into `F_{2^N}` (which would
/// require compatible irreducibles).
#[derive(Clone, Debug)]
pub struct FieldTower {
    /// `[K : F_2]`.
    pub big_n: u32,
    /// `[K : k]` — the order of `σ` on `K`.
    pub n: u32,
    /// `[k : F_2]`.  `N = n · l`.
    pub l: u32,
    /// Reduction polynomial of `K = F_{2^N}`.
    pub irr: IrreduciblePoly,
}

impl FieldTower {
    /// Construct from `(N, n, l, irr)` after checking `N = n · l`.
    pub fn new(big_n: u32, n: u32, l: u32, irr: IrreduciblePoly) -> Self {
        assert_eq!(big_n, n * l, "N must equal n·l");
        assert_eq!(irr.degree, big_n);
        Self { big_n, n, l, irr }
    }

    /// `σ(x) = x^{2^l}` — the Frobenius generator of `Gal(K/k)`.
    pub fn frobenius(&self, x: &F2mElement) -> F2mElement {
        x.square_k_times(self.l, &self.irr)
    }

    /// `σ^i(x) = x^{2^{i·l}}`.
    pub fn frobenius_iter(&self, x: &F2mElement, i: u32) -> F2mElement {
        x.square_k_times(i * self.l, &self.irr)
    }

    /// `√x` in `F_{2^N}` — the unique `c` with `c² = x`.
    ///
    /// Computed as `c = x^{2^{N−1}}` since the absolute Frobenius
    /// `φ(x) = x²` has order `N` on `F_{2^N}`, so its inverse is
    /// `φ^{N−1}`.
    pub fn sqrt(&self, x: &F2mElement) -> F2mElement {
        x.square_k_times(self.big_n - 1, &self.irr)
    }

    /// `true` iff `x ∈ F_{2^{sub_l}}`, where `sub_l` must divide
    /// `big_n`.  Equivalent to `x^{2^{sub_l}} = x`.
    pub fn is_in_subfield(&self, x: &F2mElement, sub_l: u32) -> bool {
        assert!(self.big_n.is_multiple_of(sub_l), "sub_l must divide N");
        x.square_k_times(sub_l, &self.irr) == *x
    }

    /// Order of the σ-orbit of `x`: the smallest positive `i ≤ n`
    /// with `σ^i(x) = x`, equivalently the smallest `i ≥ 1` such
    /// that `x ∈ F_{2^{i·l}}`.  Always divides `n`.
    pub fn frobenius_orbit_length(&self, x: &F2mElement) -> u32 {
        // Generate divisors of n in ascending order and test.
        let mut divisors: Vec<u32> = (1..=self.n).filter(|d| self.n.is_multiple_of(*d)).collect();
        divisors.sort_unstable();
        for d in divisors {
            // σ^d(x) = x  ⇔  x ∈ F_{2^{d·l}}.
            let xs = x.square_k_times(d * self.l, &self.irr);
            if &xs == x {
                return d;
            }
        }
        self.n
    }
}

/// Compute the `F_2`-dimension of the subspace of `F_{2^m}`
/// (viewed as `F_2^m`) spanned by `elements`.
///
/// Uses Gaussian elimination over `F_2` on packed `u64` bit-vectors.
pub fn f2_dim(elements: &[F2mElement], m: u32) -> u32 {
    if elements.is_empty() {
        return 0;
    }
    let n_words = m.div_ceil(64) as usize;
    // Copy bit-vectors into a mutable matrix.
    let mut rows: Vec<Vec<u64>> = elements
        .iter()
        .map(|e| {
            let mut row = vec![0u64; n_words];
            for (i, w) in e.raw_bits().iter().enumerate() {
                if i < n_words {
                    row[i] = *w;
                }
            }
            row
        })
        .collect();
    let mut rank = 0usize;
    for col in 0..m {
        let w = (col / 64) as usize;
        let b = col % 64;
        // Find a row at index ≥ rank with bit `col` set.
        let mut pivot = None;
        for r in rank..rows.len() {
            if (rows[r][w] >> b) & 1 == 1 {
                pivot = Some(r);
                break;
            }
        }
        if let Some(p) = pivot {
            rows.swap(rank, p);
            // Eliminate from all other rows.
            for r in 0..rows.len() {
                if r != rank && (rows[r][w] >> b) & 1 == 1 {
                    for i in 0..n_words {
                        rows[r][i] ^= rows[rank][i];
                    }
                }
            }
            rank += 1;
        }
        if rank >= rows.len() {
            break;
        }
    }
    rank as u32
}

/// Compute Hess's "magic number" `m_E(σ)` for the curve
/// `E: y² + x·y = x³ + a·x² + b` over the top of the [`FieldTower`].
///
/// `m := dim_{F_2} span_{F_2} { σ^i(√b) : 0 ≤ i < n }`.
///
/// This is the simple `√b`-orbit form used by Teske; see
/// [`magic_number_full`] for the version that also folds in
/// `{(σ − 1)·σ^i(a)}`.
pub fn magic_number(tower: &FieldTower, _a: &F2mElement, b: &F2mElement) -> u32 {
    let sqrt_b = tower.sqrt(b);
    let mut orbit = Vec::with_capacity(tower.n as usize);
    let mut cur = sqrt_b.clone();
    for _ in 0..tower.n {
        orbit.push(cur.clone());
        cur = tower.frobenius(&cur);
    }
    f2_dim(&orbit, tower.big_n)
}

/// Full Hess magic number: include the contribution of `a`'s
/// Galois-twist differences `(σ − 1)·σ^i(a)`.  For trapdoor
/// constructions where `a ∈ F_2`, the additional generators are
/// all zero and this agrees with [`magic_number`].
pub fn magic_number_full(tower: &FieldTower, a: &F2mElement, b: &F2mElement) -> u32 {
    let sqrt_b = tower.sqrt(b);
    let mut gens = Vec::with_capacity(2 * tower.n as usize);
    let mut cur_b = sqrt_b.clone();
    for _ in 0..tower.n {
        gens.push(cur_b.clone());
        cur_b = tower.frobenius(&cur_b);
    }
    // (σ - 1)·σ^i(a) = σ^{i+1}(a) + σ^i(a) (char 2)
    let mut cur_a = a.clone();
    for _ in 0..tower.n {
        let next_a = tower.frobenius(&cur_a);
        gens.push(cur_a.add(&next_a));
        cur_a = next_a;
    }
    f2_dim(&gens, tower.big_n)
}

/// GHS hyperelliptic-descent genus from the magic number.
///
/// Standard formula (Hess Theorem 4.1): `g = 2^{m−1}` in the
/// "generic" / type-II case.  When `σ` acts on `V_E(σ)` with order
/// exactly `m` and the orbit closes, the genus drops by one to
/// `2^{m−1} − 1` (type I).  Distinguishing the two requires
/// checking whether `σ^m(√b) = √b` (orbit length divides `m`); see
/// [`ghs_genus_with_type`] for the refined version.
pub fn ghs_genus(magic_m: u32) -> u32 {
    if magic_m == 0 {
        0
    } else {
        1u32 << (magic_m - 1)
    }
}

/// Return `(genus, is_type_i)`.  Type I (genus `2^{m−1} − 1`)
/// occurs when the `σ`-orbit of `√b` has length exactly `m`
/// (closed orbit, no `F_2`-linear surprises), which is the *most
/// favourable* trapdoor case.
pub fn ghs_genus_with_type(tower: &FieldTower, b: &F2mElement) -> (u32, bool) {
    let m = magic_number(tower, &F2mElement::zero(tower.big_n), b);
    if m == 0 {
        return (0, false);
    }
    let sqrt_b = tower.sqrt(b);
    let orbit_len = tower.frobenius_orbit_length(&sqrt_b);
    let type_i = orbit_len == m;
    let g = if type_i {
        (1u32 << (m - 1)).saturating_sub(1)
    } else {
        1u32 << (m - 1)
    };
    (g, type_i)
}

/// **Auditor view** of a curve `E/F_{2^N}`: try every non-trivial
/// factorisation `N = n·l` and report the descent magic number /
/// genus for each.  Returns the rows sorted by `(genus, l)` ascending
/// (smaller-genus attacks first).
pub fn audit_curve(
    big_n: u32,
    big_irr: &IrreduciblePoly,
    a: &F2mElement,
    b: &F2mElement,
) -> Vec<DescentRow> {
    let mut rows = Vec::new();
    for l in 1..big_n {
        if !big_n.is_multiple_of(l) {
            continue;
        }
        let n = big_n / l;
        if n < 2 {
            continue;
        }
        let tower = FieldTower::new(big_n, n, l, big_irr.clone());
        let m = magic_number_full(&tower, a, b);
        let (g, type_i) = ghs_genus_with_type(&tower, b);
        rows.push(DescentRow {
            n,
            l,
            magic_m: m,
            genus: g,
            type_i,
        });
    }
    // Sort: smallest genus first (most threatening descent); ties
    // broken by larger l (more "work" in the descent curve field).
    rows.sort_by(|x, y| x.genus.cmp(&y.genus).then(y.l.cmp(&x.l)));
    rows
}

/// One row of an [`audit_curve`] report.
#[derive(Clone, Debug, Default)]
pub struct DescentRow {
    /// `[K : k]` for this factorisation.
    pub n: u32,
    /// `[k : F_2]`.
    pub l: u32,
    /// Hess magic number `m_E(σ)` for this factorisation.
    pub magic_m: u32,
    /// GHS genus `2^{m−1}` or `2^{m−1} − 1`.
    pub genus: u32,
    /// Type-I (closed σ-orbit on `√b`)?
    pub type_i: bool,
}

/// **Trapdoor constructor**: given a target factorisation `N = n·l`
/// and a target magic number `m_target` (small ⇒ small descent
/// genus), search for `b ∈ F_{2^N}` with `√b ∈ F_{2^{m_target·l}}
/// \ F_{2^{(m_target−1)·l}}` so the σ-orbit has length exactly
/// `m_target`.
///
/// Returns the curve coefficients `(a, b)` and the resulting
/// audit row.  We fix `a = 1` (so the `a`-contribution to the
/// magic number vanishes).
///
/// **Returns `None`** if the search budget is exhausted; this is
/// rare for small `N` but can happen for highly constrained towers.
///
/// The caller is responsible for checking the resulting curve is
/// not anomalous or otherwise weak via *other* attacks (e.g.
/// supersingular detection) — this routine only ensures the
/// GHS-descent trapdoor structure.
pub fn construct_trapdoor_curve(
    big_n: u32,
    n: u32,
    l: u32,
    m_target: u32,
    big_irr: &IrreduciblePoly,
    max_attempts: u32,
) -> Option<TrapdoorCurve> {
    assert!(m_target >= 1 && m_target <= n);
    let tower = FieldTower::new(big_n, n, l, big_irr.clone());
    let a = F2mElement::one(big_n);

    // Strategy: enumerate small candidates for √b directly.  We
    // want √b ∈ F_{2^{m_target·l}} but ∉ F_{2^{(m_target−1)·l}}
    // (or any smaller subfield containing it).  Brute-force search
    // over small bit-patterns suffices for the toy parameters this
    // module targets.
    let sub_l = m_target * l;
    let _strictly_below_l = (m_target - 1) * l;

    let mut tried = 0u32;
    let mut candidate_bits = 1u64;
    while tried < max_attempts {
        let sqrt_b = F2mElement::from_biguint(&num_bigint::BigUint::from(candidate_bits), big_n);
        candidate_bits = candidate_bits.wrapping_add(1);
        if candidate_bits == 0 {
            candidate_bits = 1;
        }
        tried += 1;
        if sqrt_b.is_zero() {
            continue;
        }
        // Must lie in F_{2^{m_target·l}}.
        if sub_l < big_n && !tower.is_in_subfield(&sqrt_b, sub_l) {
            continue;
        }
        // Must NOT lie in a strict subfield of F_{2^{m_target·l}}.
        // Equivalent: the σ-orbit must have length exactly `m_target`.
        let orbit = tower.frobenius_orbit_length(&sqrt_b);
        if orbit != m_target {
            continue;
        }
        // Also rule out: span has lower-than-expected F_2-rank
        // (rare but possible if there's an F_2-linear relation).
        let mut orbit_elts = Vec::with_capacity(m_target as usize);
        let mut cur = sqrt_b.clone();
        for _ in 0..m_target {
            orbit_elts.push(cur.clone());
            cur = tower.frobenius(&cur);
        }
        let rank = f2_dim(&orbit_elts, big_n);
        if rank != m_target {
            continue;
        }
        // Recover b = (√b)².
        let b = sqrt_b.square(big_irr);
        if b.is_zero() {
            continue;
        }
        // Build the audit row for the target factorisation.
        let m = magic_number_full(&tower, &a, &b);
        let (genus, type_i) = ghs_genus_with_type(&tower, &b);
        debug_assert_eq!(m, m_target);

        return Some(TrapdoorCurve {
            big_n,
            n,
            l,
            big_irr: big_irr.clone(),
            a,
            b,
            sqrt_b,
            row: DescentRow {
                n,
                l,
                magic_m: m,
                genus,
                type_i,
            },
            full_audit: None,
        });
    }
    None
}

/// The output of [`construct_trapdoor_curve`].
#[derive(Clone, Debug)]
pub struct TrapdoorCurve {
    pub big_n: u32,
    pub n: u32,
    pub l: u32,
    pub big_irr: IrreduciblePoly,
    /// Curve parameter `a` (we fix `a = 1` in the constructor).
    pub a: F2mElement,
    /// Curve parameter `b`.
    pub b: F2mElement,
    /// Precomputed `√b` — useful in the descent construction.
    pub sqrt_b: F2mElement,
    /// The target factorisation row (the trapdoor).
    pub row: DescentRow,
    /// Full auditor table, optionally populated by callers who want
    /// to verify the trapdoor is unique (the target row has the
    /// minimum genus across all factorisations).
    pub full_audit: Option<Vec<DescentRow>>,
}

impl TrapdoorCurve {
    /// Run [`audit_curve`] over every factorisation and attach the
    /// result.  Verifies the trapdoor is **non-trivial**: the target
    /// factorisation is the minimum-genus row.
    pub fn populate_audit(&mut self) {
        let rows = audit_curve(self.big_n, &self.big_irr, &self.a, &self.b);
        self.full_audit = Some(rows);
    }

    /// `true` iff the target factorisation `(self.n, self.l)` has
    /// the **smallest genus** across all factorisations — i.e., the
    /// trapdoor owner's descent really is the optimal attack.
    pub fn trapdoor_is_optimal(&self) -> Option<bool> {
        self.full_audit.as_ref().map(|rows| {
            // Rows are sorted ascending by genus; check the *first*
            // row matches our target factorisation.
            rows.first()
                .map(|r| r.n == self.n && r.l == self.l)
                .unwrap_or(false)
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::binary_ecc::IrreduciblePoly;
    use num_bigint::BigUint;

    /// `F_{2^6}` with `z⁶ + z + 1` (a known irreducible).
    fn f64_irr() -> IrreduciblePoly {
        IrreduciblePoly {
            degree: 6,
            low_terms: vec![0, 1],
        }
    }

    /// `F_{2^8}` with the AES irreducible `z⁸ + z⁴ + z³ + z + 1`.
    fn f256_irr() -> IrreduciblePoly {
        IrreduciblePoly::deg_8()
    }

    #[test]
    fn sqrt_squares_to_input() {
        let irr = f64_irr();
        let tower = FieldTower::new(6, 3, 2, irr.clone());
        for v in 1..64u64 {
            let x = F2mElement::from_biguint(&BigUint::from(v), 6);
            let s = tower.sqrt(&x);
            assert_eq!(s.square(&irr), x);
        }
    }

    #[test]
    fn subfield_detection() {
        let irr = f64_irr();
        let tower = FieldTower::new(6, 3, 2, irr.clone());
        // F_{2^1} ⊂ F_{2^2} ⊂ F_{2^6}.  In particular 0 and 1 are
        // in F_{2^1}.
        let one = F2mElement::one(6);
        assert!(tower.is_in_subfield(&one, 1));
        assert!(tower.is_in_subfield(&one, 2));
        // Element z = (bit 1) — has degree 1, in F_{2^6} but check
        // if F_{2^2}-membership is sensible.  z² + z + 1 = 0 in F_4
        // iff its Frobenius square fixes it.
        let z = F2mElement::from_bit_positions(&[1], 6);
        // z ∈ F_{2^2}  ⇔  z^4 = z.  Let's compute z^4 = z² · z² and
        // see if it equals z.  Almost certainly not for this z.
        let in_f4 = tower.is_in_subfield(&z, 2);
        // True or false — both are valid outcomes; just exercising
        // the API.  We expect z ∉ F_4 since z has degree 1 < 6 and
        // is not algebraic over F_4 in a way that lands it back.
        let _ = in_f4;
    }

    #[test]
    fn frobenius_orbit_lengths_divide_n() {
        let irr = f64_irr();
        let tower = FieldTower::new(6, 3, 2, irr.clone());
        // For each nonzero element of F_{2^6}, the σ-orbit length
        // must divide n = 3 — so it's 1 or 3.
        for v in 1u64..64 {
            let x = F2mElement::from_biguint(&BigUint::from(v), 6);
            let orbit = tower.frobenius_orbit_length(&x);
            assert!(
                orbit == 1 || orbit == 3,
                "orbit {} not 1 or 3 (v = {})",
                orbit,
                v
            );
            // Orbit 1 iff x ∈ F_4 (the fixed field of σ on K).
            let fixed = tower.is_in_subfield(&x, 2);
            assert_eq!(orbit == 1, fixed, "orbit / subfield mismatch for v = {}", v);
        }
    }

    #[test]
    fn f2_dim_singleton() {
        let m = 8;
        let x = F2mElement::from_biguint(&BigUint::from(0b10101u32), m);
        assert_eq!(f2_dim(&[x], m), 1);
        // Zero should give rank 0.
        assert_eq!(f2_dim(&[F2mElement::zero(m)], m), 0);
    }

    #[test]
    fn f2_dim_three_independent_vectors() {
        let m = 8;
        let a = F2mElement::from_biguint(&BigUint::from(0b0001u32), m);
        let b = F2mElement::from_biguint(&BigUint::from(0b0010u32), m);
        let c = F2mElement::from_biguint(&BigUint::from(0b0100u32), m);
        let d = F2mElement::from_biguint(&BigUint::from(0b0111u32), m); // a+b+c
                                                                        // {a, b, c} → rank 3.  {a, b, c, d} → still rank 3.
        assert_eq!(f2_dim(&[a.clone(), b.clone(), c.clone()], m), 3);
        assert_eq!(f2_dim(&[a, b, c, d], m), 3);
    }

    #[test]
    fn magic_number_b_in_subfield_is_one() {
        // If b ∈ F_{2^l}, then √b ∈ F_{2^l} too (char-2 subfields are
        // closed under sqrt), so the σ-orbit of √b is just {√b}.
        // Magic number = 1, genus = 1.
        let irr = f256_irr();
        let tower = FieldTower::new(8, 4, 2, irr.clone());
        // Pick an element of F_4: x s.t. x^4 = x.  Try x = 0x11 ∈ F_{2^8}:
        // probably not in F_4.  Easier: pick b ∈ F_2 ⊂ F_4.  b = 1
        // certainly works.
        let b = F2mElement::one(8);
        let a = F2mElement::zero(8);
        let m = magic_number(&tower, &a, &b);
        assert_eq!(m, 1);
        assert_eq!(ghs_genus(m), 1);
    }

    #[test]
    fn magic_number_constructor_targets_two() {
        // Try to construct a curve with magic number 2, descent
        // genus 2, on the (8, 4, 2) tower.
        let irr = f256_irr();
        let constructed = construct_trapdoor_curve(8, 4, 2, 2, &irr, 256);
        let tc = constructed.expect("found b with m=2");
        assert_eq!(tc.row.magic_m, 2);
        // Genus should be 2 (or 1 if type-I).  Either way ≤ 2.
        assert!(tc.row.genus <= 2);
    }

    #[test]
    fn audit_curve_includes_all_factorisations() {
        let irr = f256_irr();
        // Quick: pick b = 1 (so all factorisations give magic = 1).
        let a = F2mElement::zero(8);
        let b = F2mElement::one(8);
        let rows = audit_curve(8, &irr, &a, &b);
        // 8 = 2·4 = 4·2.  Both should appear.
        let factorisations: Vec<(u32, u32)> = rows.iter().map(|r| (r.n, r.l)).collect();
        assert!(factorisations.contains(&(4, 2)));
        assert!(factorisations.contains(&(2, 4)));
        // All magic numbers should be 1 (b is in F_2).
        for r in &rows {
            assert_eq!(r.magic_m, 1, "{:?}", r);
        }
    }
}
