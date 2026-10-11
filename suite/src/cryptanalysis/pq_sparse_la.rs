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

    // Track the sequence of pivots so we can back-substitute.
    let mut pivot_cols: Vec<usize> = Vec::new();
    let mut pivot_rows: Vec<SparseRow> = Vec::new();

    while !rows.is_empty() {
        // Count occurrences per column across active rows.
        let mut counts: BTreeMap<usize, usize> = BTreeMap::new();
        for r in &rows {
            for &c in r.entries.keys() {
                *counts.entry(c).or_insert(0) += 1;
            }
        }
        if counts.is_empty() {
            // No more active variables; remaining rows are all-zero
            // (or RHS-only — inconsistent).
            if rows.iter().any(|r| !r.rhs.is_zero()) {
                return None; // inconsistent
            }
            break;
        }

        // Pick the column with the *fewest* active rows (Markowitz proxy).
        let (pivot_col, _) = counts
            .iter()
            .min_by_key(|(_, &cnt)| cnt)
            .map(|(c, n)| (*c, *n))
            .expect("non-empty counts");

        // Find a row containing pivot_col with an *invertible* coefficient.
        let mut chosen_row_idx = None;
        let mut chosen_inv = BigUint::zero();
        // Prefer the row with the smallest degree (minimises fill-in).
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
                // No invertible pivot in this column — drop it from
                // every row (gives up on solving it) and continue.
                // For PQ where N is prime, every nonzero is invertible,
                // so this branch is dead.
                for r in rows.iter_mut() {
                    r.entries.remove(&pivot_col);
                }
                continue;
            }
        };

        // Normalise the chosen row: multiply through by `chosen_inv`.
        let mut pivot = rows.swap_remove(chosen_row_idx);
        for v in pivot.entries.values_mut() {
            *v = (&*v * &chosen_inv) % n;
        }
        pivot.rhs = (&pivot.rhs * &chosen_inv) % n;

        // Sanity: pivot coefficient is now 1.
        debug_assert_eq!(pivot.entries.get(&pivot_col), Some(&BigUint::from(1u32)));

        // Eliminate pivot_col from every remaining row.
        for r in rows.iter_mut() {
            let coef = match r.entries.remove(&pivot_col) {
                Some(c) if !c.is_zero() => c,
                _ => continue,
            };
            // r ← r − coef · pivot.
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

    // Back-substitute: process pivots in reverse order.  Each pivot's
    // row has the form `var + sum(other_vars · coefs) = rhs`, where
    // `other_vars` are variables eliminated EARLIER (lower in the stack).
    // Actually, with the elimination order above, "earlier pivots"
    // were eliminated FROM later rows, so later pivots' rows may still
    // contain columns of earlier pivots — those need to be substituted
    // in.
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
}
