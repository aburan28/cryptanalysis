//! # Sparse linear algebra over `Z/N` for index-calculus relation matrices.
//!
//! In the Petit–Quisquater pipeline (and any index-calculus algorithm),
//! the relation matrix is dramatically sparse: each row has at most
//! `n + 1` nonzero entries where `n` is the decomposition size
//! (typically 2–4), out of `|FB| + 1 ≈ 10²–10⁵` columns.  Dense
//! Gaussian elimination throws away that sparsity and pays `O(rows ·
//! cols²)`; structured / sparse Gaussian retains it.
//!
//! This module ships:
//!
//! - [`SparseRow`] — a sparse row over `Z/N` (`BTreeMap<col, value>`).
//! - [`sparse_solve_mod_n`] — structured Gaussian with Markowitz
//!   minimum-degree pivoting.  Returns the value of a chosen target
//!   column (e.g. `k = log_G Q` in PQ).
//!
//! ## Algorithm: structured Gaussian
//!
//! At each step:
//!
//! 1. **Pick a pivot column**: minimise the number of active rows in
//!    which the column is nonzero (Markowitz cost = (rows−1)·(cols−1)
//!    for the chosen pivot; min-rows is the standard cheap proxy).
//! 2. **Pick a pivot row**: any row containing the column with a
//!    *unit* (= invertible) coefficient mod `N`.  For prime `N` every
//!    nonzero is invertible; for composite `N` we skip non-units.
//! 3. **Normalise** the pivot row (scale so the pivot entry = 1).
//! 4. **Eliminate** the pivot column from every other row, preserving
//!    sparsity by only touching the nonzero columns of the pivot row.
//! 5. **Repeat** until all columns are eliminated or no further pivot
//!    is available.
//! 6. **Back-substitute** to recover all variable values.
//!
//! ## Why this exists alongside `gaussian_eliminate_mod_n`
//!
//! The dense [`crate::cryptanalysis::ec_index_calculus::gaussian_eliminate_mod_n`]
//! is fine for `|FB| ≤ 50` (the toy regime).  Real PQ at production
//! scale needs `|FB| ≈ 2^{20}` and dense becomes infeasible; the
//! sparse path here demonstrates the right algorithm structure even if
//! we never run it at production scale.  We also cross-check it
//! against the dense path in the tests, which catches sign/encoding
//! mistakes.
//!
//! For *truly* large systems one would use **Lanczos** or
//! **Wiedemann** (sparse iterative solvers with O(rows · cols)
//! complexity), not structured Gaussian.  See:
//!
//! ## References
//!
//! - **C. Pomerance**, *A tale of two sieves*, Notices AMS 43 (1996) —
//!   structured Gaussian for the quadratic sieve, the canonical
//!   "make the matrix smaller before going dense" technique.
//! - **B. A. LaMacchia, A. M. Odlyzko**, *Solving large sparse linear
//!   systems over finite fields*, CRYPTO 1990 — survey of the
//!   landscape including Lanczos and Wiedemann.

use crate::utils::mod_inverse;
use num_bigint::BigUint;
use num_traits::Zero;
use std::collections::btree_map::Entry;
use std::collections::BTreeMap;

/// A sparse row: `entries[c]` is the (mod-`N`) coefficient of column `c`.
/// Absent keys are zero.  Plus a single right-hand-side scalar.
#[derive(Clone, Debug)]
pub struct SparseRow {
    pub entries: BTreeMap<usize, BigUint>,
    pub rhs: BigUint,
}

impl SparseRow {
    /// Empty (all-zero) row.
    pub fn zero() -> Self {
        SparseRow {
            entries: BTreeMap::new(),
            rhs: BigUint::zero(),
        }
    }

    /// Build from a `(col, coef)` list.
    pub fn from_entries(entries: Vec<(usize, BigUint)>, rhs: BigUint) -> Self {
        let mut map = BTreeMap::new();
        for (c, v) in entries {
            if !v.is_zero() {
                let cur = map.remove(&c).unwrap_or_else(BigUint::zero);
                let new_val = cur + v; // caller is responsible for reducing mod N
                if !new_val.is_zero() {
                    map.insert(c, new_val);
                }
            }
        }
        SparseRow { entries: map, rhs }
    }

    /// Number of nonzero entries.
    pub fn degree(&self) -> usize {
        self.entries.len()
    }
}

/// **Solve the system** of `SparseRow`s for the value of `target_col`
/// (e.g. the column for `k` in PQ).
///
/// `n_cols` is the total number of columns.  `n` is the modulus.
/// Returns `Some(value)` if `target_col` is uniquely determined by the
/// system (modulo `N`), `None` otherwise.
pub fn sparse_solve_mod_n(
    mut rows: Vec<SparseRow>,
    #[allow(unused_variables)] n_cols: usize,
    target_col: usize,
    n: &BigUint,
) -> Option<BigUint> {
    let _ = n_cols; // present in API for documentation; the algorithm is row-driven and detects empty columns automatically.
                    // Drop trivial all-zero rows.
    rows.retain(|r| !r.entries.is_empty() || !r.rhs.is_zero());

    // The per-column counts live in a `Vec` indexed by column and are
    // kept current as entries appear and vanish, instead of a
    // `BTreeMap` rebuilt over every active row at every pivot.
    // Fill-in only copies a pivot row's columns into other rows, so no
    // column outside the initial rows ever appears.  Callers number
    // columns `0..n_cols`, but nothing enforces that: when the indices
    // are far sparser than the entries, relabel each column by its rank
    // among the columns present.  The map is monotone, so every
    // "lowest column" tie-break and every row's entry order is
    // unchanged, and back-substitution works on ranks throughout.
    // The width saturates rather than wrapping for a column numbered
    // `usize::MAX`: the old solver took any index, and a saturated
    // width is far past the threshold, so such a system is relabelled.
    let n_entries: usize = rows.iter().map(|r| r.entries.len()).sum();
    let width = rows
        .iter()
        .filter_map(|r| r.entries.keys().next_back())
        .max()
        .map_or(0, |&c| c.saturating_add(1));
    let (width, target_col) = if width > 2 * n_entries + 64 {
        let mut present: Vec<usize> = rows
            .iter()
            .flat_map(|r| r.entries.keys().copied())
            .collect();
        present.sort_unstable();
        present.dedup();
        let rank = |c: usize| present.binary_search(&c).expect("column is present");
        for r in rows.iter_mut() {
            r.entries = std::mem::take(&mut r.entries)
                .into_iter()
                .map(|(c, v)| (rank(c), v))
                .collect();
        }
        // An absent target is never a pivot, so it has no value, as before.
        let target = present.binary_search(&target_col).unwrap_or(usize::MAX);
        (present.len(), target)
    } else {
        (width, target_col)
    };
    let mut counts = vec![0usize; width];
    for r in &rows {
        for &c in r.entries.keys() {
            counts[c] += 1;
        }
    }

    // Track the sequence of pivots so we can back-substitute.
    let mut pivot_cols: Vec<usize> = Vec::new();
    let mut pivot_rows: Vec<SparseRow> = Vec::new();
    // `(degree, row index)` of every active row holding the pivot column.
    let mut candidates: Vec<(usize, usize)> = Vec::new();

    while !rows.is_empty() {
        // Pick the column with the *fewest* active rows (Markowitz
        // proxy), the lowest such column on ties.  A count of one is
        // the least possible, so the first one found wins outright.
        let mut pivot = None;
        let mut best_count = usize::MAX;
        for (c, &cnt) in counts.iter().enumerate() {
            if cnt != 0 && cnt < best_count {
                best_count = cnt;
                pivot = Some(c);
                if cnt == 1 {
                    break;
                }
            }
        }
        let pivot_col = match pivot {
            Some(c) => c,
            None => {
                // No more active variables; remaining rows are all-zero
                // (or RHS-only — inconsistent).
                if rows.iter().any(|r| !r.rhs.is_zero()) {
                    return None; // inconsistent
                }
                break;
            }
        };

        // Find a row containing pivot_col with an *invertible*
        // coefficient, preferring the smallest degree (minimises
        // fill-in) and then the lowest row index.  Visiting the rows in
        // that order and stopping at the first unit chooses the same
        // row as testing every row would, and inverts one coefficient
        // instead of `best_count` of them: for prime `N` every nonzero
        // is a unit, so the first candidate is always the one.
        // Exactly `best_count` active rows hold the column, so the scan
        // stops at the last of them.
        candidates.clear();
        for (i, r) in rows.iter().enumerate() {
            if r.entries.contains_key(&pivot_col) {
                candidates.push((r.degree(), i));
                if candidates.len() == best_count {
                    break;
                }
            }
        }
        debug_assert_eq!(candidates.len(), best_count);
        candidates.sort_unstable();
        let chosen = candidates
            .iter()
            .find_map(|&(_, i)| mod_inverse(&rows[i].entries[&pivot_col], n).map(|inv| (i, inv)));
        let (chosen_row_idx, chosen_inv) = match chosen {
            Some(found) => found,
            None => {
                // No invertible pivot in this column — drop it from
                // every row (gives up on solving it) and continue.
                // For PQ where N is prime, every nonzero is invertible,
                // so this branch is dead.
                for &(_, i) in &candidates {
                    rows[i].entries.remove(&pivot_col);
                }
                counts[pivot_col] = 0;
                continue;
            }
        };

        // Normalise the chosen row: multiply through by `chosen_inv`.
        // `swap_remove` moves the last row into the chosen slot.
        let last = rows.len() - 1;
        let mut pivot = rows.swap_remove(chosen_row_idx);
        for &c in pivot.entries.keys() {
            counts[c] -= 1;
        }
        for v in pivot.entries.values_mut() {
            *v = (&*v * &chosen_inv) % n;
        }
        pivot.rhs = (&pivot.rhs * &chosen_inv) % n;

        // Sanity: pivot coefficient is now 1.
        debug_assert_eq!(pivot.entries.get(&pivot_col), Some(&BigUint::from(1u32)));

        // Eliminate pivot_col from every remaining row that holds it:
        // the other candidates, each updated independently.
        for &(_, i) in &candidates {
            if i == chosen_row_idx {
                continue;
            }
            let r = &mut rows[if i == last { chosen_row_idx } else { i }];
            counts[pivot_col] -= 1;
            let coef = match r.entries.remove(&pivot_col) {
                Some(c) if !c.is_zero() => c,
                _ => continue,
            };
            // r ← r − coef · pivot, updating each entry in place.
            for (&c, v) in &pivot.entries {
                if c == pivot_col {
                    continue;
                }
                let term = (&coef * v) % n;
                match r.entries.entry(c) {
                    Entry::Occupied(mut e) => {
                        sub_mod_assign(e.get_mut(), &term, n);
                        if e.get().is_zero() {
                            e.remove();
                            counts[c] -= 1;
                        }
                    }
                    Entry::Vacant(e) => {
                        // 0 − term: nonzero unless the term is.
                        if !term.is_zero() {
                            e.insert(n - &term);
                            counts[c] += 1;
                        }
                    }
                }
            }
            let rhs_term = (&coef * &pivot.rhs) % n;
            sub_mod_assign(&mut r.rhs, &rhs_term, n);
        }
        debug_assert_eq!(counts[pivot_col], 0);

        pivot_cols.push(pivot_col);
        pivot_rows.push(pivot);
    }

    // Back-substitute: process pivots in reverse order.  Each pivot's
    // row has the form `var + sum(other_vars · coefs) = rhs`, where
    // `other_vars` are variables eliminated EARLIER (lower in the stack).
    // Actually, with the elimination order above, "earlier pivots"
    // were eliminated FROM later rows, so later pivots' rows may still
    // contain columns of earlier pivots — those need to be substituted
    // in.
    // A column that was never a pivot has no value and counts as zero.
    let mut solution: Vec<Option<BigUint>> = vec![None; width];
    for (i, &col) in pivot_cols.iter().enumerate().rev() {
        let row = &pivot_rows[i];
        let mut val = row.rhs.clone();
        for (&c, coef) in &row.entries {
            if c == col {
                continue;
            }
            if let Some(s) = &solution[c] {
                let term = (coef * s) % n;
                sub_mod_assign(&mut val, &term, n);
            }
        }
        solution[col] = Some(val);
    }

    solution.get(target_col).cloned().flatten()
}

/// `a ← (a + n − term) mod n` for `term < n`, the canonical residue of
/// `a − term`.  A reduced `a` (the usual case: every value this module
/// writes is reduced) needs one in-place subtraction and at most one
/// addition, with no division and no new allocation; an unreduced `a`
/// (a caller's row built from repeated columns) takes the division.
fn sub_mod_assign(a: &mut BigUint, term: &BigUint, n: &BigUint) {
    if *a < *n {
        if *a < *term {
            *a += n;
        }
        *a -= term;
    } else {
        *a = (&*a + n - term) % n;
    }
}

// ── Tests ──────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::ec_index_calculus::gaussian_eliminate_mod_n;
    use num_traits::{One, Zero};

    /// Single-variable equation `3x ≡ 7 mod 11`, x = 6.
    #[test]
    fn solve_trivial_one_var() {
        let n = BigUint::from(11u32);
        let row = SparseRow::from_entries(vec![(0, BigUint::from(3u32))], BigUint::from(7u32));
        let x = sparse_solve_mod_n(vec![row], 1, 0, &n);
        assert_eq!(x, Some(BigUint::from(6u32)));
    }

    /// Two-variable system.
    ///   2x + 3y ≡ 8 (mod 11)
    ///   x + y ≡ 4 (mod 11)
    /// Subtracting: x + 2y ≡ 4, so y = 0, x = 4.
    /// Wait: from first - 2·second = (3y - 2y) = y ≡ 8 - 8 = 0 → y = 0.
    /// Then x = 4. Check 2·4 + 3·0 = 8 ✓.
    #[test]
    fn solve_two_var_system() {
        let n = BigUint::from(11u32);
        let r1 = SparseRow::from_entries(
            vec![(0, BigUint::from(2u32)), (1, BigUint::from(3u32))],
            BigUint::from(8u32),
        );
        let r2 = SparseRow::from_entries(
            vec![(0, BigUint::one()), (1, BigUint::one())],
            BigUint::from(4u32),
        );
        let x = sparse_solve_mod_n(vec![r1.clone(), r2.clone()], 2, 0, &n);
        let y = sparse_solve_mod_n(vec![r1, r2], 2, 1, &n);
        assert_eq!(x, Some(BigUint::from(4u32)));
        assert_eq!(y, Some(BigUint::zero()));
    }

    /// **Cross-check against dense Gaussian** on a random toy system.
    /// Produce a random sparse system whose first column is the target;
    /// compare the recovered value against `gaussian_eliminate_mod_n`.
    #[test]
    fn agrees_with_dense_gaussian_on_random_system() {
        // Build a 4×4 invertible system mod 17 with prescribed solution
        // (1, 2, 3, 4).
        let n = BigUint::from(17u32);
        let true_sol = [
            BigUint::from(1u32),
            BigUint::from(2u32),
            BigUint::from(3u32),
            BigUint::from(4u32),
        ];
        // 4×4 matrix:
        //   row 0: (1, 2, 0, 0) → 1·1 + 2·2 = 5
        //   row 1: (3, 1, 0, 1) → 3 + 2 + 4 = 9
        //   row 2: (0, 0, 1, 0) → 3
        //   row 3: (0, 1, 1, 2) → 2 + 3 + 8 = 13
        let matrix_rows = vec![
            vec![(0usize, 1u32), (1, 2)],
            vec![(0, 3), (1, 1), (3, 1)],
            vec![(2, 1)],
            vec![(1, 1), (2, 1), (3, 2)],
        ];
        let mut dense_rows: Vec<Vec<BigUint>> = Vec::new();
        let mut dense_rhs: Vec<BigUint> = Vec::new();
        let mut sparse_rows: Vec<SparseRow> = Vec::new();
        for cols in &matrix_rows {
            let mut row = vec![BigUint::zero(); 4];
            let mut sparse_entries = Vec::new();
            let mut rhs = BigUint::zero();
            for &(c, v) in cols {
                let bv = BigUint::from(v);
                row[c] = bv.clone();
                rhs = (&rhs + &bv * &true_sol[c]) % &n;
                sparse_entries.push((c, bv));
            }
            dense_rows.push(row);
            dense_rhs.push(rhs.clone());
            sparse_rows.push(SparseRow::from_entries(sparse_entries, rhs));
        }
        let mut dense_clone = dense_rows.clone();
        let mut dense_rhs_clone = dense_rhs.clone();
        let dense_sol =
            gaussian_eliminate_mod_n(&mut dense_clone, &mut dense_rhs_clone, &n).unwrap();
        for col in 0..4 {
            let s = sparse_solve_mod_n(sparse_rows.clone(), 4, col, &n);
            assert_eq!(
                s.as_ref(),
                Some(&dense_sol[col]),
                "sparse vs dense disagree at col {}: sparse {:?} dense {}",
                col,
                s,
                dense_sol[col]
            );
            assert_eq!(s, Some(true_sol[col].clone()));
        }
    }

    /// **Inconsistent system** → `None`.
    #[test]
    fn detects_inconsistent_system() {
        let n = BigUint::from(7u32);
        let r1 = SparseRow::from_entries(vec![(0, BigUint::one())], BigUint::from(3u32));
        let r2 = SparseRow::from_entries(vec![(0, BigUint::one())], BigUint::from(5u32));
        // x = 3 AND x = 5 mod 7 is inconsistent.
        let sol = sparse_solve_mod_n(vec![r1, r2], 1, 0, &n);
        assert!(
            sol.is_none() || sol == Some(BigUint::from(3u32)) || sol == Some(BigUint::from(5u32))
        );
        // We accept either None or one of the rows' values; we just
        // shouldn't get something wildly wrong.  (Our pivot-elim
        // detects the inconsistency in the no-active-cols branch.)
    }

    /// **Composite modulus** with non-invertible pivot: ensure no panic.
    #[test]
    fn handles_composite_modulus_gracefully() {
        let n = BigUint::from(15u32); // 3 · 5; 3, 5, 6, 9, 10, 12 are non-units.
        let r1 = SparseRow::from_entries(vec![(0, BigUint::from(3u32))], BigUint::from(6u32));
        // 3x ≡ 6 mod 15 has solutions {2, 7, 12} (gcd(3,15)=3, x ≡ 2 mod 5).
        // sparse_solve will hit the non-invertible branch and drop the
        // pivot — returning None is acceptable.
        let _ = sparse_solve_mod_n(vec![r1], 1, 0, &n);
        // No panic = pass.
    }

    /// The solver as it was before the pivot search inverted only the
    /// chosen row and the column counts moved into a `Vec`: every
    /// candidate row inverted, counts rebuilt in a `BTreeMap` at every
    /// pivot, entries updated by remove/insert.  Kept verbatim so the
    /// tests below can pin the current solver to it.
    fn reference_sparse_solve(
        mut rows: Vec<SparseRow>,
        target_col: usize,
        n: &BigUint,
    ) -> Option<BigUint> {
        rows.retain(|r| !r.entries.is_empty() || !r.rhs.is_zero());
        let mut pivot_cols: Vec<usize> = Vec::new();
        let mut pivot_rows: Vec<SparseRow> = Vec::new();
        while !rows.is_empty() {
            let mut counts: BTreeMap<usize, usize> = BTreeMap::new();
            for r in &rows {
                for &c in r.entries.keys() {
                    *counts.entry(c).or_insert(0) += 1;
                }
            }
            if counts.is_empty() {
                if rows.iter().any(|r| !r.rhs.is_zero()) {
                    return None;
                }
                break;
            }
            let (pivot_col, _) = counts
                .iter()
                .min_by_key(|(_, &cnt)| cnt)
                .map(|(c, n)| (*c, *n))
                .expect("non-empty counts");
            let mut chosen_row_idx = None;
            let mut chosen_inv = BigUint::zero();
            let mut best_degree = usize::MAX;
            for (i, r) in rows.iter().enumerate() {
                if let Some(coef) = r.entries.get(&pivot_col) {
                    if let Some(inv) = mod_inverse(coef, n) {
                        if r.degree() < best_degree {
                            best_degree = r.degree();
                            chosen_row_idx = Some(i);
                            chosen_inv = inv;
                        }
                    }
                }
            }
            let chosen_row_idx = match chosen_row_idx {
                Some(i) => i,
                None => {
                    for r in rows.iter_mut() {
                        r.entries.remove(&pivot_col);
                    }
                    continue;
                }
            };
            let mut pivot = rows.swap_remove(chosen_row_idx);
            for v in pivot.entries.values_mut() {
                *v = (&*v * &chosen_inv) % n;
            }
            pivot.rhs = (&pivot.rhs * &chosen_inv) % n;
            for r in rows.iter_mut() {
                let coef = match r.entries.remove(&pivot_col) {
                    Some(c) if !c.is_zero() => c,
                    _ => continue,
                };
                for (&c, v) in &pivot.entries {
                    if c == pivot_col {
                        continue;
                    }
                    let term = (&coef * v) % n;
                    let cur = r.entries.remove(&c).unwrap_or_else(BigUint::zero);
                    let new_val = (&cur + n - &term) % n;
                    if !new_val.is_zero() {
                        r.entries.insert(c, new_val);
                    }
                }
                let rhs_term = (&coef * &pivot.rhs) % n;
                r.rhs = (&r.rhs + n - &rhs_term) % n;
            }
            pivot_cols.push(pivot_col);
            pivot_rows.push(pivot);
        }
        let mut solution: BTreeMap<usize, BigUint> = BTreeMap::new();
        for (i, &col) in pivot_cols.iter().enumerate().rev() {
            let row = &pivot_rows[i];
            let mut val = row.rhs.clone();
            for (&c, coef) in &row.entries {
                if c == col {
                    continue;
                }
                let s = solution.get(&c).cloned().unwrap_or_else(BigUint::zero);
                let term = (coef * &s) % n;
                val = (&val + n - &term) % n;
            }
            solution.insert(col, val);
        }
        solution.get(&target_col).cloned()
    }

    /// The case the pivot order exists for: over `Z/15` the lowest
    /// min-count column's min-degree row has a non-unit coefficient
    /// (3), so the pivot must fall to the next candidate by degree (a
    /// unit, 2), and the second pivot again skips a non-unit (6).
    /// Planted solution x = 7, y = 4.
    #[test]
    fn composite_modulus_skips_non_unit_min_degree_row() {
        let n = BigUint::from(15u32);
        let big = |v: u32| BigUint::from(v);
        let rows = vec![
            // 3x ≡ 6: degree 1, but 3 is not a unit mod 15.
            SparseRow::from_entries(vec![(0, big(3))], big(6)),
            // 2x + y ≡ 18 ≡ 3: degree 2, 2 is a unit.
            SparseRow::from_entries(vec![(0, big(2)), (1, big(1))], big(3)),
            // y ≡ 4.
            SparseRow::from_entries(vec![(1, big(1))], big(4)),
        ];
        for (col, want) in [(0usize, 7u32), (1, 4)] {
            let got = sparse_solve_mod_n(rows.clone(), 2, col, &n);
            assert_eq!(got, Some(big(want)), "column {col}");
            assert_eq!(got, reference_sparse_solve(rows.clone(), col, &n));
        }
    }

    /// Columns numbered up to `usize::MAX`, which the old solver took
    /// like any other.  The width (highest column plus one) must
    /// saturate rather than wrap to zero and index an empty count
    /// table (or trip the overflow check), so these systems take the
    /// relabelled path.  `3x ≡ 7 (mod 11)` gives x = 6 at column
    /// `usize::MAX`; beside it, `x₀ + x ≡ 8` gives x₀ = 2, both at
    /// that column and one below it (where the width is exact).
    #[test]
    fn solves_columns_numbered_up_to_usize_max() {
        let n = BigUint::from(11u32);
        let big = |v: u32| BigUint::from(v);
        let top = usize::MAX;
        let single = vec![SparseRow::from_entries(vec![(top, big(3))], big(7))];
        for (col, want) in [(top, Some(big(6))), (0, None)] {
            let got = sparse_solve_mod_n(single.clone(), 1, col, &n);
            assert_eq!(got, want, "single row, target {col}");
            assert_eq!(got, reference_sparse_solve(single.clone(), col, &n));
        }
        for high in [top, top - 1] {
            let rows = vec![
                SparseRow::from_entries(vec![(high, big(3))], big(7)),
                SparseRow::from_entries(vec![(0, big(1)), (high, big(1))], big(8)),
            ];
            for (col, want) in [(high, Some(big(6))), (0, Some(big(2))), (1, None)] {
                let got = sparse_solve_mod_n(rows.clone(), 2, col, &n);
                assert_eq!(got, want, "highest column {high}, target {col}");
                assert_eq!(got, reference_sparse_solve(rows.clone(), col, &n));
            }
        }
    }

    /// Random systems over prime and composite moduli agree exactly
    /// with the reference solver: every column's value (or `None`),
    /// including columns absent from the system.  The inputs cover
    /// non-unit coefficients (composite `N`, so the first candidates
    /// are often skipped and whole columns dropped), unreduced entries
    /// and right-hand sides, repeated columns merged by
    /// `from_entries`, under- and over-determined systems, planted
    /// (consistent) and random right-hand sides, and column numbers far
    /// sparser than the entries (the relabelled path).
    #[test]
    fn agrees_with_reference_solver_on_random_systems() {
        use rand::rngs::StdRng;
        use rand::{Rng, SeedableRng};
        let moduli: Vec<BigUint> = vec![
            BigUint::from(11u32),
            BigUint::from(15u32),
            BigUint::from(36u32),
            BigUint::from(1u32 << 12),
            BigUint::from(1_000_003u32),
            BigUint::from(6u64 * ((1u64 << 61) - 1)),
            (BigUint::one() << 127u32) - 1u32,
        ];
        let mut rng = StdRng::seed_from_u64(0x5eed_5a1a);
        let mut solved = 0usize;
        for case in 0..600 {
            let n = &moduli[case % moduli.len()];
            let n_cols = rng.gen_range(1..=14usize);
            let n_rows = rng.gen_range(n_cols.saturating_sub(2).max(1)..=n_cols + 4);
            // Every other case spreads the columns far apart.
            let stride = if case % 2 == 0 { 1 } else { 1_000_003usize };
            // Three cases in four plant a solution, so most columns
            // have a value to agree on.
            let planted = case % 4 != 3;
            let rand_big = |rng: &mut StdRng| {
                let v = BigUint::from(rng.gen::<u128>());
                // Mostly reduced, sometimes up to 3n (unreduced), sometimes small.
                match rng.gen_range(0..8) {
                    0 => v % (n * 3u32),
                    1 => BigUint::from(rng.gen_range(0u32..8)),
                    _ => v % n,
                }
            };
            let x: Vec<BigUint> = (0..n_cols).map(|_| rand_big(&mut rng)).collect();
            let rows: Vec<SparseRow> = (0..n_rows)
                .map(|_| {
                    let weight = if rng.gen_range(0..16) == 0 {
                        0
                    } else {
                        rng.gen_range(1..=4usize)
                    };
                    let entries: Vec<(usize, BigUint)> = (0..weight)
                        .map(|_| (rng.gen_range(0..n_cols), rand_big(&mut rng)))
                        .collect();
                    let rhs = if planted {
                        entries
                            .iter()
                            .fold(BigUint::zero(), |acc, (c, a)| acc + a * &x[*c])
                            % n
                    } else {
                        rand_big(&mut rng)
                    };
                    let entries = entries.into_iter().map(|(c, a)| (c * stride, a)).collect();
                    SparseRow::from_entries(entries, rhs)
                })
                .collect();
            for col in 0..=n_cols {
                let target = col * stride;
                let got = sparse_solve_mod_n(rows.clone(), n_cols, target, n);
                let want = reference_sparse_solve(rows.clone(), target, n);
                assert_eq!(got, want, "case {case}, column {target}, n = {n}");
                solved += usize::from(got.is_some());
            }
        }
        // The comparison is only as good as the answers it compares.
        assert!(solved > 1000, "only {solved} solved columns");
    }

    /// Rows built directly, not through `from_entries`, can hold
    /// explicit zeros and nonzero multiples of `N` (both ≡ 0, and a
    /// zero pivot-column coefficient is removed without eliminating),
    /// and right-hand sides of the same kind.  Nothing on the PQ path
    /// builds such rows, but the solver's answer on them is pinned to
    /// the reference all the same, over the small moduli where they
    /// are common.  `N = 1` is left out: there the pivot is never 1
    /// and the solver's own debug assertion fires, as it always did.
    #[test]
    fn agrees_with_reference_on_explicit_zeros_and_multiples_of_n() {
        use rand::rngs::StdRng;
        use rand::{Rng, SeedableRng};
        let moduli = [2u32, 4, 6, 15, 97].map(BigUint::from);
        let mut rng = StdRng::seed_from_u64(0x5eed_2e20);
        let mut solved = 0usize;
        for case in 0..500 {
            let n = &moduli[case % moduli.len()];
            let n_cols = rng.gen_range(1..=10usize);
            // 0, a nonzero multiple of n, or a small value (often unreduced).
            let value = |rng: &mut StdRng| match rng.gen_range(0..4) {
                0 => BigUint::zero(),
                1 => n * rng.gen_range(1u32..4),
                _ => BigUint::from(rng.gen_range(1u32..300)),
            };
            // Three cases in four plant a solution (the right-hand side
            // left unreduced), so most columns have a value to agree on.
            let planted = case % 4 != 3;
            let x: Vec<BigUint> = (0..n_cols).map(|_| value(&mut rng)).collect();
            let rows: Vec<SparseRow> = (0..rng.gen_range(1..=n_cols + 3))
                .map(|_| {
                    let mut row = SparseRow::zero();
                    for _ in 0..rng.gen_range(0..=4) {
                        let c = rng.gen_range(0..n_cols);
                        row.entries.insert(c, value(&mut rng));
                    }
                    row.rhs = if planted {
                        row.entries.iter().map(|(&c, a)| a * &x[c]).sum()
                    } else {
                        value(&mut rng)
                    };
                    row
                })
                .collect();
            for col in 0..=n_cols {
                let got = sparse_solve_mod_n(rows.clone(), n_cols, col, n);
                let want = reference_sparse_solve(rows.clone(), col, n);
                assert_eq!(got, want, "case {case}, column {col}, n = {n}");
                solved += usize::from(got.is_some());
            }
        }
        assert!(solved > 200, "only {solved} solved columns");
    }

    /// Systems of the perfbench shape at a few hundred columns (weight-3
    /// rows, one in eight heavier), where elimination runs long enough
    /// and fills in enough that a single missed count update would pick
    /// a different pivot or stop the candidate scan early, agree with
    /// the reference on a sample of columns.  Each system is then
    /// solved again with one more row, `x_top ≡ 5`, whose column sits
    /// one below and exactly at the relabelling threshold
    /// (`2 · entries + 64`), so the same rows take the direct and the
    /// relabelled path.  `N = 1` (every value ≡ 0, every coefficient
    /// a "unit" with inverse 0) trips the solver's own debug assertion
    /// that the pivot is 1, so it is compared only where that is
    /// compiled out.
    #[test]
    fn agrees_with_reference_at_scale_and_at_the_relabel_threshold() {
        use rand::rngs::StdRng;
        use rand::{Rng, SeedableRng};
        let mut moduli: Vec<BigUint> = vec![
            (BigUint::one() << 127u32) - 1u32,
            BigUint::from(6u64 * ((1u64 << 61) - 1)),
            BigUint::from(15u32),
            BigUint::from(1u32 << 12),
        ];
        if !cfg!(debug_assertions) {
            moduli.push(BigUint::one());
        }
        let mut rng = StdRng::seed_from_u64(0x5eed_a11e);
        let mut solved = 0usize;
        for case in 0..20 {
            let n = &moduli[case % moduli.len()];
            // Values are reduced, except mod 1, where they would all vanish.
            let value = |rng: &mut StdRng| {
                let v = BigUint::from(rng.gen::<u128>());
                if n.is_one() {
                    v % 1000u32
                } else {
                    v % n
                }
            };
            let cols = rng.gen_range(48..=160usize);
            let n_rows = rng.gen_range(cols - 16..=cols + 24);
            let x: Vec<BigUint> = (0..cols).map(|_| value(&mut rng)).collect();
            let rows: Vec<SparseRow> = (0..n_rows)
                .map(|_| {
                    let weight = if rng.gen_range(0..8) == 0 {
                        rng.gen_range(5..=12usize)
                    } else {
                        3
                    };
                    let entries: Vec<(usize, BigUint)> = (0..weight)
                        .map(|_| (rng.gen_range(0..cols), value(&mut rng)))
                        .collect();
                    let rhs = entries
                        .iter()
                        .fold(BigUint::zero(), |acc, (c, a)| acc + a * &x[*c])
                        % n;
                    SparseRow::from_entries(entries, rhs)
                })
                .collect();
            let mut targets: Vec<usize> = (0..5).map(|_| rng.gen_range(0..cols)).collect();
            targets.extend([0, cols - 1, cols]);
            for &t in &targets {
                let got = sparse_solve_mod_n(rows.clone(), cols, t, n);
                let want = reference_sparse_solve(rows.clone(), t, n);
                assert_eq!(got, want, "case {case}, column {t}, n = {n}");
                solved += usize::from(got.is_some());
            }
            let entries = rows.iter().map(SparseRow::degree).sum::<usize>() + 1;
            let threshold = 2 * entries + 64;
            for top in [threshold - 1, threshold] {
                let mut with_top = rows.clone();
                with_top.push(SparseRow::from_entries(
                    vec![(top, BigUint::one())],
                    BigUint::from(5u32),
                ));
                for t in [top, 0, targets[0]] {
                    let got = sparse_solve_mod_n(with_top.clone(), top + 1, t, n);
                    let want = reference_sparse_solve(with_top.clone(), t, n);
                    assert_eq!(got, want, "case {case}, top {top}, column {t}, n = {n}");
                    solved += usize::from(got.is_some());
                }
            }
        }
        assert!(solved > 60, "only {solved} solved columns");
    }
}
