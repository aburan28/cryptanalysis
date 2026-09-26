//! Quasi-subfield polynomials over `F_{2^n}`, and an exhaustive census of
//! them at small parameters.
//!
//! Huang, Kosters, Petit, Yeo and Yun (*Quasi-subfield polynomials and
//! the elliptic curve discrete logarithm problem*, J. Math. Cryptol.
//! 14(1):25–38, 2020) build index-calculus factor bases from the roots
//! of
//!
//! ```text
//!     L(X) = X^{q^{n0}} − λ(X)
//! ```
//!
//! when `L` splits completely in `F_{q^n}` and `deg λ` is small; the
//! subfield case is `λ(X) = X`.  Their Definition 3.1 calls `L` a
//! **quasi-subfield polynomial** when
//!
//! ```text
//!     log_q(deg λ) < n0² / n .
//! ```
//!
//! Their paper closes on an open problem, quoted here because it is the
//! thing this module measures:
//!
//! > It remains an open problem to find (or rule out) the existence of
//! > quasi-subfield polynomials where `deg λ` is small enough to improve
//! > on the best (generic) algorithms for ECDLP.  A question of
//! > particular interest is whether the bound on `deg λ` provided by
//! > Lemma 4.1 is tight: in fact removing the term `n mod n0` in this
//! > bound would show that our approach cannot beat generic algorithms.
//!
//! # The search, in characteristic 2
//!
//! Take `q = 2`.  A monic `2`-linearised polynomial
//! `L(X) = X^{2^{n0}} + Σ_{i<n0} c_i X^{2^i}` acts `F_2`-linearly on
//! `F_{2^n}`, and it splits completely there with a root set that is an
//! `F_2`-subspace **iff that linear map has kernel of dimension exactly
//! `n0`**.  So "splits completely" is a rank condition on an `n × n`
//! matrix over `F_2`, which is cheap, and the whole question becomes a
//! finite search over the coefficient vector `(c_0, …, c_{n0−1})`.
//!
//! `λ(X) = Σ_{i<n0} c_i X^{2^i}` has `deg λ = 2^j` with
//! `j = max{ i : c_i ≠ 0 }`, so the quasi-subfield condition is
//! `j < n0²/n`: **every coefficient from index `⌈n0²/n⌉` upward must
//! vanish.**  That is what `search` enumerates, over the coefficients
//! that are allowed to be non-zero.
//!
//! # Why the answer is not obvious
//!
//! Counting heuristically: the search space has `2^{t·n}` points with
//! `t = ⌈n0²/n⌉`, and a random `F_2`-linear map has an `n0`-dimensional
//! kernel with probability of order `2^{−n0²}`.  Since `t·n ≈ n0²`, the
//! expected number of solutions is of order **one** — the question sits
//! exactly on the first-moment threshold, which is why a statistical
//! argument does not settle it and an exhaustive census does.
//!
//! [`lemma_4_1_bound`] reports the paper's lower bound in both forms,
//! with and without the `n mod n0` term, so a census that finds a
//! quasi-subfield polynomial below the stripped bound is direct evidence
//! that the term cannot be removed.

use crate::binary_ecc::f2m::IrreduciblePoly;
use crate::cryptanalysis::koblitz_index_calculus::find_irreducible;
use crate::cryptanalysis::semaev_decomp::Gf2;

/// One quasi-subfield polynomial found by the census.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct QsfPolynomial {
    /// `n` in `F_{2^n}`.
    pub n: u32,
    /// `n0`, the exponent in the leading term `X^{2^{n0}}`.
    pub n0: u32,
    /// `c_0 … c_{n0−1}`, the coefficients of `λ`; entry `i` multiplies
    /// `X^{2^i}`.  The leading `X^{2^{n0}}` is implicit and monic.
    pub lambda: Vec<u64>,
    /// `j = max{ i : c_i ≠ 0 }`, so `deg λ = 2^j`.  `None` when `λ = 0`,
    /// which cannot split completely for `n0 ≥ 1` and is reported only
    /// for completeness.
    pub j: Option<u32>,
}

impl QsfPolynomial {
    /// `log₂(deg λ)`, the quantity the paper's Definition 3.1 bounds.
    pub fn log2_deg_lambda(&self) -> Option<u32> {
        self.j
    }
    /// Is this a subfield polynomial, `λ(X) = X`?
    pub fn is_subfield(&self) -> bool {
        self.j == Some(0) && self.lambda[0] == 1
    }
}

/// The largest `j` a quasi-subfield polynomial may have, i.e. the
/// largest integer strictly below `n0²/n`.  `None` when `n0²/n ≤ 0`.
///
/// Coefficients `c_i` for `i > j_max` must vanish, so the search runs
/// over indices `0 ..= j_max`.
pub fn max_j(n: u32, n0: u32) -> Option<u32> {
    if n == 0 || n0 == 0 {
        return None;
    }
    // largest j with j·n < n0²
    let num = (n0 as u64) * (n0 as u64);
    let mut j = 0u32;
    while ((j + 1) as u64) * (n as u64) < num {
        j += 1;
    }
    // j = 0 is admissible only when 0 < n0²/n, always true here.
    Some(j)
}

/// The paper's Lemma 4.1 lower bound on `log₂(deg λ)`, in both forms.
///
/// Composing `λ` with itself `⌊n/n0⌋` times and using
/// `X^{2^n} ≡ X mod L` forces
/// `deg(λ)^{⌊n/n0⌋} · 2^{n mod n0} ≥ 2^{n0}`, hence
/// `log₂ deg λ ≥ (n0 − (n mod n0)) / ⌊n/n0⌋`.
///
/// Returns `(with_term, without_term)` as exact rationals scaled by the
/// denominator `⌊n/n0⌋`: the bound holds iff
/// `j · ⌊n/n0⌋ ≥ numerator`.  The second entry drops `n mod n0`, which
/// is the strengthening the paper says would rule the approach out.
pub fn lemma_4_1_bound(n: u32, n0: u32) -> Option<(f64, f64)> {
    if n0 == 0 || n0 > n {
        return None;
    }
    let floor = (n / n0) as f64;
    if floor == 0.0 {
        return None;
    }
    let r = (n % n0) as f64;
    Some((((n0 as f64) - r) / floor, (n0 as f64) / floor))
}

/// The `n × n` matrix over `F_2` of the map `X ↦ L(X)`, as `n` column
/// bitmasks: column `k` is `L(z^k)` in the polynomial basis.
fn linear_map_columns(gf: &Gf2, n: u32, n0: u32, lambda: &[u64]) -> Vec<u64> {
    (0..n)
        .map(|k| {
            let x = 1u64 << k;
            // leading term X^{2^{n0}}
            let mut acc = gf.sqr_k(x, n0);
            for (i, &c) in lambda.iter().enumerate() {
                if c != 0 {
                    acc ^= gf.mul(c, gf.sqr_k(x, i as u32));
                }
            }
            acc
        })
        .collect()
}

/// Dimension of the kernel of the `F_2`-linear map given by `columns`.
fn kernel_dim(mut columns: Vec<u64>, n: u32) -> u32 {
    let mut rank = 0u32;
    let mut row = 0u32;
    let ncols = columns.len();
    let mut col = 0usize;
    while row < n && col < ncols {
        // find a column with a set bit at position `row` at or after col
        let mut pivot = None;
        for (c, item) in columns.iter().enumerate().take(ncols).skip(col) {
            if (item >> row) & 1 == 1 {
                pivot = Some(c);
                break;
            }
        }
        match pivot {
            None => {
                row += 1;
            }
            Some(p) => {
                columns.swap(col, p);
                let pivot_col = columns[col];
                for c in 0..ncols {
                    if c != col && (columns[c] >> row) & 1 == 1 {
                        columns[c] ^= pivot_col;
                    }
                }
                rank += 1;
                col += 1;
                row += 1;
            }
        }
    }
    n - rank
}

/// Does this monic linearised polynomial split completely in `F_{2^n}`
/// with an `n0`-dimensional root space?
pub fn splits_completely(gf: &Gf2, n: u32, n0: u32, lambda: &[u64]) -> bool {
    let cols = linear_map_columns(gf, n, n0, lambda);
    kernel_dim(cols, n) == n0
}

/// Report of an exhaustive census at one `(n, n0)`.
#[derive(Clone, Debug)]
pub struct Census {
    pub n: u32,
    pub n0: u32,
    /// Largest admissible `j`; coefficients above it are forced to zero.
    pub j_max: u32,
    /// Coefficient vectors examined.
    pub examined: u64,
    /// How many split completely with an `n0`-dimensional kernel.
    pub found: u64,
    /// The smallest `j` achieved by any of them.
    pub min_j: Option<u32>,
    /// Up to a few witnesses, smallest `j` first.
    pub witnesses: Vec<QsfPolynomial>,
    /// First-moment prediction `2^{(j_max+1)·n − n0²}`.
    pub expected: f64,
    /// Lemma 4.1's bound with and without the `n mod n0` term.
    pub bound_with_term: f64,
    pub bound_without_term: f64,
}

impl Census {
    /// Does the census contain a polynomial below the bound obtained by
    /// deleting `n mod n0` — the paper's "question of particular
    /// interest"?  Such a witness shows the term cannot be removed.
    pub fn refutes_stripped_bound(&self) -> bool {
        match self.min_j {
            Some(j) => (j as f64) < self.bound_without_term,
            None => false,
        }
    }
}

/// Exhaustively enumerate every monic `2`-linearised
/// `L(X) = X^{2^{n0}} + Σ_{i ≤ j_max} c_i X^{2^i}` over `F_{2^n}` and
/// report those that split completely.
///
/// `keep` caps how many witnesses are retained; the counts are exact
/// regardless.  The search visits `2^{(j_max+1)·n}` vectors, so it is
/// meant for small `n`; [`Census::examined`] records the true count.
pub fn census(n: u32, n0: u32, keep: usize) -> Option<Census> {
    if n0 == 0 || n0 >= n || n > 40 {
        return None;
    }
    let j_max = max_j(n, n0)?;
    let t = (j_max + 1) as usize;
    let total_bits = (t as u32) * n;
    if total_bits > 34 {
        return None; // refuse searches beyond a few seconds of work
    }
    let irr: IrreduciblePoly = find_irreducible(n)?;
    let gf = Gf2::new(&irr);

    let (bound_with_term, bound_without_term) = lemma_4_1_bound(n, n0)?;
    let mut best: Vec<QsfPolynomial> = Vec::new();
    let mut found = 0u64;
    let mut min_j: Option<u32> = None;

    let total: u64 = 1u64 << total_bits;
    let field_mask = (1u64 << n) - 1;
    let mut lambda = vec![0u64; n0 as usize];
    for code in 0..total {
        for (i, slot) in lambda.iter_mut().enumerate().take(t) {
            *slot = (code >> ((i as u32) * n)) & field_mask;
        }
        if !splits_completely(&gf, n, n0, &lambda) {
            continue;
        }
        found += 1;
        let j = (0..t).rev().find(|&i| lambda[i] != 0).map(|i| i as u32);
        if let Some(jv) = j {
            if min_j.is_none_or(|m| jv < m) {
                min_j = Some(jv);
            }
        }
        if best.len() < keep {
            best.push(QsfPolynomial {
                n,
                n0,
                lambda: lambda.clone(),
                j,
            });
        }
    }
    best.sort_by_key(|w| w.j.unwrap_or(u32::MAX));
    Some(Census {
        n,
        n0,
        j_max,
        examined: total,
        found,
        min_j,
        witnesses: best,
        expected: 2f64.powi(total_bits as i32 - (n0 * n0) as i32),
        bound_with_term,
        bound_without_term,
    })
}

/// One-line rendering of a census row.
pub fn format_census(c: &Census) -> String {
    format!(
        "n={:>3} n0={:>2}  j_max={}  searched 2^{:<2}  found {:>8}  min j {:>4}  \
         expected {:>9.2}  L4.1 bound {:.3} (stripped {:.3}){}",
        c.n,
        c.n0,
        c.j_max,
        (c.examined as f64).log2().round() as i64,
        c.found,
        c.min_j.map(|j| j.to_string()).unwrap_or_else(|| "-".into()),
        c.expected,
        c.bound_with_term,
        c.bound_without_term,
        if c.refutes_stripped_bound() {
            "  <- below stripped bound"
        } else {
            ""
        }
    )
}

// ---------------------------------------------------------------------
// The Frobenius-stable sub-question, and why it reaches further
// ---------------------------------------------------------------------

/// An `F_2`-subspace `V ⊆ F_{2^n}` is stable under the Frobenius
/// `σ : X ↦ X²` exactly when `V = ker g(σ)` for a divisor `g` of
/// `t^n − 1` over `F_2`, and then the subspace polynomial of `V` **is**
/// `g(σ)`: `L_V(X) = Σ g_i X^{2^i}`.
///
/// So for Frobenius-stable `V` the coefficients `c_i` are the
/// coefficients of `g`, they lie in `F_2`, and
/// `log₂ deg λ = ` the second-highest degree carrying a non-zero
/// coefficient of `g`.  The quasi-subfield condition becomes a
/// statement about **gaps in divisors of `t^n − 1`**:
///
/// ```text
///     g = t^{n0} + (terms of degree < n0²/n) .
/// ```
///
/// This is decidable in time polynomial in `n` for each divisor, and
/// the divisors are products of the irreducible factors of `t^n − 1`,
/// which are indexed by the 2-cyclotomic cosets mod `n`.  That reaches
/// field sizes the exhaustive census never could.
///
/// The irreducible factors of `t^n − 1` over `F_2`, as the sizes of the
/// 2-cyclotomic cosets mod `n` together with the cosets themselves.
/// Requires `n` odd (for even `n`, `t^n − 1` is not squarefree).
pub fn cyclotomic_cosets(n: u32) -> Option<Vec<Vec<u32>>> {
    if n == 0 || n.is_multiple_of(2) {
        return None;
    }
    let mut seen = vec![false; n as usize];
    let mut out = Vec::new();
    for s in 0..n {
        if seen[s as usize] {
            continue;
        }
        let mut coset = Vec::new();
        let mut x = s;
        loop {
            if seen[x as usize] {
                break;
            }
            seen[x as usize] = true;
            coset.push(x);
            x = (x * 2) % n;
        }
        coset.sort_unstable();
        out.push(coset);
    }
    Some(out)
}

/// Multiply two `F_2` polynomials given as coefficient bitmasks.
fn poly_mul_f2(a: u128, b: u128) -> u128 {
    let mut r = 0u128;
    let mut bb = b;
    let mut shift = 0;
    while bb != 0 {
        if bb & 1 == 1 {
            r ^= a << shift;
        }
        bb >>= 1;
        shift += 1;
    }
    r
}

/// Remainder of `a` modulo `b` over `F_2`, both coefficient bitmasks.
fn poly_rem_f2(mut a: u128, b: u128) -> u128 {
    debug_assert!(b != 0);
    let db = 127 - b.leading_zeros();
    while a != 0 {
        let da = 127 - a.leading_zeros();
        if da < db {
            break;
        }
        a ^= b << (da - db);
    }
    a
}

/// Product of two `F_2` polynomials reduced modulo `g`.
fn poly_mulmod_f2(a: u128, b: u128, g: u128) -> u128 {
    poly_rem_f2(poly_mul_f2(a, b), g)
}

/// Does `g` divide `t^n − 1` over `F_2`?
///
/// Computed as `t^n ≡ 1 (mod g)` by square-and-multiply, so `t^n` is
/// never represented: only polynomials of degree below `deg g` are.
/// That keeps the test exact for any `n`, where forming the bitmask of
/// `t^n` directly would silently wrap once `n` reached the width of the
/// word.  `deg g` must stay below 64 so that a product fits.
pub fn divides_t_n_minus_one(g: u128, n: u32) -> bool {
    if g <= 1 {
        return false;
    }
    let dg = 127 - g.leading_zeros();
    if dg == 0 || dg >= 64 {
        return false;
    }
    // t^n mod g by square-and-multiply on the exponent.
    let mut result = 1u128;
    let mut base = poly_rem_f2(2u128, g); // t mod g
    let mut e = n;
    while e > 0 {
        if e & 1 == 1 {
            result = poly_mulmod_f2(result, base, g);
        }
        base = poly_mulmod_f2(base, base, g);
        e >>= 1;
    }
    result == 1
}

/// A Frobenius-stable quasi-subfield candidate: a divisor of `t^n − 1`.
#[derive(Clone, Debug)]
pub struct StableCandidate {
    pub n: u32,
    pub n0: u32,
    /// `g` as a coefficient bitmask, bit `i` = coefficient of `t^i`.
    pub g: u128,
    /// Second-highest degree with a non-zero coefficient, so
    /// `deg λ = 2^j`.
    pub j: u32,
}

/// Frobenius-stable subspaces of dimension `n0` in `F_{2^n}` whose
/// subspace polynomial already satisfies the quasi-subfield gap, found
/// by enumerating `g = t^{n0} + (terms of degree ≤ j_max)` and testing
/// divisibility of `t^n − 1`.
///
/// Only `2^{j_max+1}` candidates are examined rather than the
/// `2^{(j_max+1)·n}` of the full census, which is what lets this reach
/// field sizes the census cannot.
pub fn stable_candidates(n: u32, n0: u32) -> Option<Vec<StableCandidate>> {
    if n == 0 || n.is_multiple_of(2) || n0 == 0 || n0 >= n || n0 >= 64 {
        return None;
    }
    let j_max = max_j(n, n0)?;
    if j_max >= 24 {
        return None;
    }
    let mut out = Vec::new();
    for low in 0u64..(1u64 << (j_max + 1)) {
        if low == 0 {
            continue; // λ = 0 cannot split
        }
        let g = (1u128 << n0) | (low as u128);
        if !divides_t_n_minus_one(g, n) {
            continue;
        }
        let j = 63 - low.leading_zeros();
        out.push(StableCandidate { n, n0, g, j });
    }
    out.sort_by_key(|c| c.j);
    Some(out)
}

/// The smallest `log₂ deg λ` achievable by a Frobenius-stable subspace
/// of dimension `n0` in `F_{2^n}`, and whether it clears Definition 3.1.
pub fn stable_min_j(n: u32, n0: u32) -> Option<(u32, bool)> {
    let cands = stable_candidates(n, n0)?;
    let best = cands.first()?;
    let qsf = (best.j as f64) < (n0 as f64) * (n0 as f64) / (n as f64);
    Some((best.j, qsf))
}

/// Dimensions of the Frobenius-stable `F_2`-subspaces of `F_{2^n}`.
///
/// A subspace is Frobenius-stable exactly when it is the kernel of a
/// linearised polynomial with coefficients in `F_2`, i.e. of an element
/// of `F_2[σ]`; under the isomorphism `F_2[t] ≅ F_2[σ]` sending
/// `t^n − 1 ↦ X^{2^n} − X`, those kernels correspond to the divisors of
/// `t^n − 1`, and the kernel dimension is the divisor's degree.  So the
/// achievable dimensions are the subset sums of the degrees of the
/// irreducible factors of `t^n − 1` — equivalently, of the cyclotomic
/// coset sizes of `2` mod `n`.
///
/// This is what decides whether a field admits a usable invariant
/// factor base at all, and it is decided by arithmetic of `n` alone,
/// before any curve is chosen.
pub fn stable_subspace_dimensions(n: u32) -> Option<Vec<u32>> {
    let cosets = cyclotomic_cosets(n)?;
    let mut reachable = vec![false; n as usize + 1];
    reachable[0] = true;
    for c in &cosets {
        let d = c.len();
        // Descending, so each factor is used at most once.
        for target in (d..=n as usize).rev() {
            if reachable[target - d] {
                reachable[target] = true;
            }
        }
    }
    Some((0..=n).filter(|&d| reachable[d as usize]).collect())
}

/// Whether `F_{2^n}` admits **no** usable Frobenius-stable factor base:
/// the only stable subspaces are the trivial ones — dimension `0`, the
/// prime field `F_2` (dimension 1), the trace hyperplane (dimension
/// `n − 1`), and the whole field.
///
/// This happens exactly when `2` is a primitive root mod `n`, so
/// `t^n − 1 = (t + 1) · f` with `f` irreducible of degree `n − 1`.
///
/// `n = 131` — the ECC2K-130 field — is such an `n`.  Every construction
/// whose factor base is the kernel of an `F_2`-coefficient linearised
/// polynomial degenerates there: the quasi-subfield factor bases of
/// Huang–Kosters–Petit–Yeo–Yun, and the Frobenius-invariant factor
/// bases that
/// [`crate::cryptanalysis::koblitz_index_calculus`] builds for subfield
/// curves alike.  A dimension-1 base is the prime field and a
/// dimension-130 base cannot be materialised, so neither is a factor
/// base in any useful sense.
pub fn stable_dimensions_are_trivial(n: u32) -> Option<bool> {
    let dims = stable_subspace_dimensions(n)?;
    Some(dims == vec![0, 1, n - 1, n])
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The subfield itself is the reference point: when `n0 | n`,
    /// `λ(X) = X` splits completely and its root set is `F_{2^{n0}}`.
    #[test]
    fn the_subfield_polynomial_splits_when_n0_divides_n() {
        let irr = find_irreducible(12).unwrap();
        let gf = Gf2::new(&irr);
        for n0 in [1u32, 2, 3, 4, 6] {
            let mut lambda = vec![0u64; n0 as usize];
            lambda[0] = 1; // λ(X) = X
            assert!(
                splits_completely(&gf, 12, n0, &lambda),
                "X^(2^{n0}) - X must split in F_2^12 when {n0} | 12"
            );
        }
        // 5 does not divide 12, so X^{2^5} - X does not split there.
        let mut lambda = vec![0u64; 5];
        lambda[0] = 1;
        assert!(!splits_completely(&gf, 12, 5, &lambda));
    }

    /// The kernel dimension really is the number of roots' log.
    #[test]
    fn kernel_dimension_counts_the_roots() {
        let irr = find_irreducible(8).unwrap();
        let gf = Gf2::new(&irr);
        // λ(X) = X gives the subfield F_4 inside F_256: 4 roots.
        let lambda = vec![1u64, 0];
        let cols = linear_map_columns(&gf, 8, 2, &lambda);
        assert_eq!(kernel_dim(cols, 8), 2);
        // Count the roots by brute force and check 2^dim matches.
        let roots = (0..256u64)
            .filter(|&x| {
                let mut acc = gf.sqr_k(x, 2);
                acc ^= gf.mul(1, x);
                acc == 0
            })
            .count();
        assert_eq!(roots, 4);
    }

    /// `max_j` implements "strictly below `n0²/n`".
    #[test]
    fn max_j_is_the_definition_threshold() {
        // n = 7, n0 = 3: 9/7 = 1.28..., so j ≤ 1.
        assert_eq!(max_j(7, 3), Some(1));
        // n = 13, n0 = 5: 25/13 = 1.92..., so j ≤ 1.
        assert_eq!(max_j(13, 5), Some(1));
        // n = 12, n0 = 6: 36/12 = 3 exactly, so j ≤ 2 (strict).
        assert_eq!(max_j(12, 6), Some(2));
        // n = 11, n0 = 5: 25/11 = 2.27..., so j ≤ 2.
        assert_eq!(max_j(11, 5), Some(2));
    }

    /// Lemma 4.1's two forms, on the case the paper's remark singles
    /// out: `n ≡ 1 mod n0` is its worst case.
    #[test]
    fn lemma_bound_matches_the_papers_worst_case() {
        // n = 7, n0 = 3: floor 2, n mod n0 = 1 -> (3-1)/2 = 1.
        let (with, without) = lemma_4_1_bound(7, 3).unwrap();
        assert!((with - 1.0).abs() < 1e-12);
        assert!((without - 1.5).abs() < 1e-12);
        // Stripping the term raises the bound above the j_max of 1,
        // so the stripped form would forbid a quasi-subfield polynomial
        // here — which is exactly what a witness would refute.
        assert!(without > max_j(7, 3).unwrap() as f64);
    }

    /// A small exhaustive census runs and its counts are self-consistent.
    #[test]
    fn census_is_self_consistent_at_n7() {
        let c = census(7, 3, 4).unwrap();
        assert_eq!(c.examined, 1u64 << 14);
        assert_eq!(c.j_max, 1);
        // Every retained witness really does split.
        let gf = Gf2::new(&find_irreducible(7).unwrap());
        for w in &c.witnesses {
            assert!(splits_completely(&gf, 7, 3, &w.lambda));
            assert!(w.j.unwrap() <= c.j_max);
        }
        assert!(c.found >= c.witnesses.len() as u64);
    }

    /// Independent check of the census's witnesses: count roots by brute
    /// force over the whole field rather than by the rank of a matrix.
    /// A degree-`2^{n0}` split polynomial must have exactly `2^{n0}`
    /// roots in `F_{2^n}`.
    #[test]
    fn census_witnesses_really_have_that_many_roots() {
        for (n, n0) in [(7u32, 3u32), (7, 4)] {
            let c = census(n, n0, 3).unwrap();
            assert!(c.found > 0, "expected witnesses at n={n}, n0={n0}");
            let gf = Gf2::new(&find_irreducible(n).unwrap());
            for w in &c.witnesses {
                let roots = (0..(1u64 << n))
                    .filter(|&x| {
                        let mut acc = gf.sqr_k(x, n0);
                        for (i, &ci) in w.lambda.iter().enumerate() {
                            if ci != 0 {
                                acc ^= gf.mul(ci, gf.sqr_k(x, i as u32));
                            }
                        }
                        acc == 0
                    })
                    .count();
                assert_eq!(
                    roots,
                    1usize << n0,
                    "n={n} n0={n0} lambda={:?} should have 2^{n0} roots",
                    w.lambda
                );
            }
        }
    }

    /// The `n = 7`, `n0 = 4` witness worked out by hand: as an operator
    /// `L = σ⁴ + σ² + σ + 1` on `F_128`, and `t⁴ + t² + t + 1`
    /// factors as `(t + 1)(t³ + t² + 1)`, both divisors of `t⁷ + 1`, so
    /// the kernel has dimension 4.  `deg λ = 4`, and `log₂ 4 = 2` is
    /// strictly below `n0²/n = 16/7`, so it is a quasi-subfield
    /// polynomial that is not a subfield one.
    #[test]
    fn the_hand_checked_witness_is_a_genuine_quasi_subfield_polynomial() {
        let n = 7u32;
        let n0 = 4u32;
        let gf = Gf2::new(&find_irreducible(n).unwrap());
        // λ(X) = X⁴ + X² + X, i.e. c_0 = c_1 = c_2 = 1, c_3 = 0.
        let lambda = vec![1u64, 1, 1, 0];
        assert!(splits_completely(&gf, n, n0, &lambda));
        let j = 2u32; // deg λ = 2² = 4
        assert!((j as f64) < (n0 * n0) as f64 / n as f64, "Definition 3.1");
        assert!(j <= max_j(n, n0).unwrap());
        // It is not the subfield polynomial: 4 does not divide 7.
        let mut subfield = vec![0u64; n0 as usize];
        subfield[0] = 1;
        assert!(!splits_completely(&gf, n, n0, &subfield));
        // And it sits strictly below the bound obtained by deleting the
        // `n mod n0` term, which is the paper's question of interest.
        let (with_term, without_term) = lemma_4_1_bound(n, n0).unwrap();
        assert!((j as f64) >= with_term, "Lemma 4.1 as stated must hold");
        assert!(
            (j as f64) < without_term,
            "the stripped bound would forbid this polynomial, but it exists"
        );
    }

    /// The divisor primitives: `t^n − 1` is divisible by exactly the
    /// polynomials the definition says, checked against brute force.
    #[test]
    fn divisibility_test_matches_brute_force() {
        for n in [7u32, 9, 11, 15] {
            let target = (1u128 << n) | 1u128;
            for g in 1u128..(1u128 << 6) {
                if g < 2 {
                    continue;
                }
                let claimed = divides_t_n_minus_one(g, n);
                // brute force: multiply g by every quotient up to degree n
                let dg = 127 - g.leading_zeros();
                let mut ok = false;
                for q in 1u128..(1u128 << (n - dg + 1)) {
                    if poly_mul_f2(g, q) == target {
                        ok = true;
                        break;
                    }
                }
                assert_eq!(claimed, ok, "n={n} g={g:b}");
            }
        }
    }

    /// The structural claim the census suggests: every quasi-subfield
    /// polynomial over `F_{2^n}` comes from a Frobenius-stable subspace,
    /// i.e. from a divisor of `t^n − 1` with the right gap.  Here the
    /// two computations are run side by side on every cell the
    /// exhaustive census can reach, and they must agree on *existence*.
    #[test]
    fn divisor_prediction_matches_the_exhaustive_census() {
        for n in [7u32, 9, 11, 13, 15] {
            for n0 in 1..n {
                let Some(jm) = max_j(n, n0) else { continue };
                if (jm + 1) * n > 22 {
                    continue;
                }
                let Some(c) = census(n, n0, 1) else { continue };
                let stable = stable_min_j(n, n0);
                let census_says = c.found > 0;
                let divisors_say = matches!(stable, Some((_, true)));
                assert_eq!(
                    census_says, divisors_say,
                    "n={n} n0={n0}: census found {} but divisors predict {:?}",
                    c.found, stable
                );
            }
        }
    }

    /// The regression the sweep caught: forming `t^n` as a bitmask wraps
    /// silently once `n` reaches the word width, which manufactured
    /// divisors out of nothing.  `t^{n0} + 1` divides `t^n + 1` exactly
    /// when `n0 | n`, and that must hold at every `n`, large ones
    /// included.
    #[test]
    fn divisibility_is_exact_past_the_word_width() {
        for n in [7u32, 31, 127, 131, 163, 233, 283, 409, 571] {
            for n0 in 2u32..40 {
                let g = (1u128 << n0) | 1u128; // t^{n0} + 1
                assert_eq!(
                    divides_t_n_minus_one(g, n),
                    n % n0 == 0,
                    "t^{n0}+1 divides t^{n}+1 iff {n0} divides {n}"
                );
            }
        }
    }

    /// ECC2K-130 lives in `F_{2^131}`, and `2` is a primitive root mod
    /// `131`: `t^131 − 1` factors as `(t + 1)` times an irreducible of
    /// degree `130`, so there is no divisor of intermediate degree and
    /// no non-trivial Frobenius-stable subspace to use as a factor
    /// base.
    ///
    /// This is unconditional for the `F_2[σ]` class.  It does not by
    /// itself rule out a quasi-subfield polynomial with coefficients in
    /// `F_{2^131}`, whose kernel need not be Frobenius-stable; what
    /// stands behind that wider claim is the census agreement recorded
    /// in `research/notes/index-calculus/RESEARCH_QUASI_SUBFIELD.md`, which is evidence at reachable
    /// `n`, not a proof.
    #[test]
    fn f2_131_admits_no_non_trivial_stable_subspace() {
        assert_eq!(
            stable_subspace_dimensions(131).unwrap(),
            vec![0, 1, 130, 131],
            "t^131 - 1 = (t+1) * (irreducible of degree 130)"
        );
        assert_eq!(stable_dimensions_are_trivial(131), Some(true));
        // And the criterion agrees with the coset structure it is
        // derived from, computed independently here.
        let sizes: Vec<usize> = cyclotomic_cosets(131)
            .unwrap()
            .iter()
            .map(|c| c.len())
            .collect();
        let mut sorted = sizes.clone();
        sorted.sort_unstable();
        assert_eq!(sorted, vec![1, 130]);
    }

    /// The contrast case.  `n = 73` is the one prime cell the reach
    /// sweep flagged as interesting, and it is interesting precisely
    /// because `2` has small order mod `73`, so intermediate divisor
    /// degrees — dimension 9 among them — exist.
    #[test]
    fn f2_73_does_admit_intermediate_stable_subspaces() {
        let dims = stable_subspace_dimensions(73).unwrap();
        assert!(dims.contains(&9), "the n = 73, n0 = 9 cell needs dim 9");
        assert_eq!(stable_dimensions_are_trivial(73), Some(false));
    }

    /// Every field in the binary-curve range where `2` is a primitive
    /// root is equally barren.  These are the NIST/SECG binary field
    /// degrees; the ones that are not barren are named explicitly so a
    /// regression shows up as a changed classification, not a silent
    /// pass.
    #[test]
    fn primitive_root_fields_are_barren_and_the_others_are_not() {
        for n in [131u32, 163, 283, 653] {
            if let Some(true) = stable_dimensions_are_trivial(n) {
                continue;
            }
            // Not barren: then it must genuinely have an intermediate
            // dimension, which is a fact about n we can restate.
            let dims = stable_subspace_dimensions(n).unwrap();
            assert!(
                dims.iter().any(|&d| d > 1 && d < n - 1),
                "n = {n} classified as non-barren but has no intermediate dimension: {dims:?}"
            );
        }
        // 233 and 409 are composite-order cases with real intermediate
        // dimensions available.
        for n in [233u32, 409] {
            let dims = stable_subspace_dimensions(n).unwrap();
            assert!(
                dims.iter().any(|&d| d > 1 && d < n - 1),
                "n = {n}: {dims:?}"
            );
        }
    }
}
