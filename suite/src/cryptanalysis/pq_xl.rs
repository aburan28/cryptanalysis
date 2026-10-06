//! # Boolean XL — matrix-based Gröbner-style solver over `F_2 / (v_i² - v_i)`.
//!
//! XL ("eXtended Linearization", Courtois–Klimov–Patarin–Shamir,
//! EUROCRYPT 2000) is a Gröbner-basis-style algorithm that trades
//! Buchberger's one-S-pair-at-a-time approach for a single big matrix
//! reduction over `F_2`.  Concretely:
//!
//! 1. Pick a working degree `D ≥ max_i deg(f_i)`.
//! 2. Enumerate every monomial of degree `≤ D` — this gives a column
//!    space `M_D`.
//! 3. For each input polynomial `f_i` and each monomial `t` with
//!    `deg(t) + deg(f_i) ≤ D`, form the product `f_i · t` and put it
//!    in as a row.
//! 4. Gaussian-eliminate the resulting `F_2` matrix.
//! 5. Each non-zero row of the reduced matrix is a polynomial of the
//!    ideal whose leading term is "new" (or smaller than before) —
//!    add it to the system and iterate if it admits a strictly smaller
//!    leading-term staircase.
//!
//! ## Why XL instead of F4 (or just Buchberger)
//!
//! For systems arising from Weil-descent of Semaev `S_{n+1}` over
//! `F_{2^m}`, the polynomials have **total degree `2^n`** and the
//! Buchberger pair-selection blows up dramatically — even with the
//! normal selection strategy and Gebauer–Möller pruning, the
//! intermediate polynomial sizes explode at `n = 3` (i.e. `S_4`,
//! degree 8) on the toy parameters.
//!
//! XL avoids the pair-selection problem entirely: every reduction
//! that *could* matter is exposed in the matrix, and Gaussian
//! elimination finds the linear dependencies all at once.  For `F_2`
//! the elimination is just **bitwise XOR of bit-vectors**, which is
//! exceptionally fast — modern CPUs do this at memory bandwidth.
//!
//! ## What this module ships
//!
//! - [`boolean_xl`] — run XL once at a given degree `D`, return the
//!   reduced polynomial set.
//! - [`boolean_xl_solve`] — wrapper: run XL, then brute-force enumerate
//!   solutions of the reduced system.  When the reduced system is much
//!   smaller than the original, this is asymptotically the win XL
//!   buys.  At toy scale the constant factors matter and the win can
//!   be modest — but the implementation is here for reference and for
//!   correctness cross-checks against Buchberger and against direct
//!   enumeration.
//!
//! ## References
//!
//! - **N. Courtois, A. Klimov, J. Patarin, A. Shamir**, *Efficient
//!   algorithms for solving overdefined systems of multivariate
//!   polynomial equations*, EUROCRYPT 2000.
//! - **J.-C. Faugère**, *A new efficient algorithm for computing
//!   Gröbner bases without reduction to zero (F5)*, ISSAC 2002 — F5
//!   subsumes XL asymptotically.
//! - **G. Bard**, *Algebraic Cryptanalysis*, Springer 2009 — chapter
//!   14 for an XL exposition specialised to `F_2`.

use crate::cryptanalysis::pq_groebner_f2::{cmp_mono, F2BoolMono, F2BoolPoly};
use std::cmp::Ordering;

// ── Sparse F_2 rows ────────────────────────────────────────────────

/// A sparse row of an `F_2` matrix: the list of column indices where
/// the row is non-zero, kept **sorted ascending**.  Column `0` is the
/// leading (DegRevLex-largest) monomial.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct F2SparseRow {
    pub cols: Vec<usize>,
}

impl F2SparseRow {
    pub fn is_zero(&self) -> bool {
        self.cols.is_empty()
    }

    /// Leading (smallest) column index = largest monomial.
    pub fn lead(&self) -> Option<usize> {
        self.cols.first().copied()
    }

    /// In-place XOR with another row.  Two sorted-ascending lists
    /// merge in linear time, with equal entries cancelling.
    pub fn xor_assign(&mut self, other: &Self) {
        let mut out = Vec::with_capacity(self.cols.len() + other.cols.len());
        let mut i = 0;
        let mut j = 0;
        while i < self.cols.len() && j < other.cols.len() {
            match self.cols[i].cmp(&other.cols[j]) {
                Ordering::Less => {
                    out.push(self.cols[i]);
                    i += 1;
                }
                Ordering::Greater => {
                    out.push(other.cols[j]);
                    j += 1;
                }
                Ordering::Equal => {
                    i += 1;
                    j += 1;
                }
            }
        }
        out.extend_from_slice(&self.cols[i..]);
        out.extend_from_slice(&other.cols[j..]);
        self.cols = out;
    }
}

// ── Monomial enumeration ───────────────────────────────────────────

/// Enumerate every boolean monomial of degree `≤ max_deg` in `n_vars`
/// variables, sorted **descending** by [`cmp_mono`] (so index 0 is the
/// largest monomial).
fn enumerate_monomials(n_vars: usize, max_deg: u32) -> Vec<F2BoolMono> {
    assert!(n_vars <= 32, "XL capped at 32 variables");
    let total = 1u64 << n_vars;
    let mut out: Vec<F2BoolMono> = (0..total)
        .map(F2BoolMono::from_mask)
        .filter(|m| m.degree() <= max_deg)
        .collect();
    out.sort_by(|a, b| cmp_mono(*b, *a));
    out
}

/// Index from monomial to its column in the [`enumerate_monomials`] list.
fn mono_index(monos: &[F2BoolMono]) -> std::collections::HashMap<F2BoolMono, usize> {
    monos.iter().enumerate().map(|(i, m)| (*m, i)).collect()
}

/// Convert a polynomial to a sparse row, given the monomial→column
/// map.  Polynomial terms not in the map (i.e. higher degree than the
/// XL working degree) are dropped — but in normal XL use this can't
/// happen because we choose `D` ≥ max degree.
fn poly_to_row(
    p: &F2BoolPoly,
    mono_to_col: &std::collections::HashMap<F2BoolMono, usize>,
) -> F2SparseRow {
    let mut cols: Vec<usize> = p
        .terms
        .iter()
        .filter_map(|m| mono_to_col.get(m).copied())
        .collect();
    cols.sort_unstable();
    F2SparseRow { cols }
}

/// Convert a sparse row back to a polynomial.
fn row_to_poly(r: &F2SparseRow, monos: &[F2BoolMono], n_vars: usize) -> F2BoolPoly {
    let monos: Vec<F2BoolMono> = r.cols.iter().map(|&c| monos[c]).collect();
    F2BoolPoly::from_monos(monos, n_vars)
}

// ── Macaulay matrix construction ───────────────────────────────────

/// Build the matrix whose rows are `f_i · t` for every `(f_i, t)`
/// with `f_i` from `polys` and `t` a monomial such that
/// `deg(t · f_i.lt()) ≤ max_deg`.
fn build_macaulay_matrix(
    polys: &[F2BoolPoly],
    monos: &[F2BoolMono],
    mono_to_col: &std::collections::HashMap<F2BoolMono, usize>,
    max_deg: u32,
) -> Vec<F2SparseRow> {
    let mut rows = Vec::new();
    for f in polys {
        // The leading monomial's degree bounds how much we can
        // multiply without overflowing `max_deg`.
        let lt_deg = f.lt().map(|m| m.degree()).unwrap_or(0);
        if lt_deg > max_deg {
            continue;
        }
        // Headroom: how high a `t` we can multiply by.
        let headroom = max_deg - lt_deg;
        for t in monos {
            if t.degree() > headroom {
                continue;
            }
            let product = f.mul_mono(*t);
            if product.is_zero() {
                continue;
            }
            rows.push(poly_to_row(&product, mono_to_col));
        }
    }
    rows
}

// ── Gaussian elimination on sparse F_2 rows ────────────────────────

/// Reduce a list of sparse `F_2` rows to row-echelon form in place.
/// Standard column-by-column elimination: find a pivot row for each
/// column, XOR it into every row below to clear that column.
fn gaussian_eliminate_sparse(rows: &mut Vec<F2SparseRow>, n_cols: usize) {
    // Process columns from smallest (= largest monomial) upward.
    // For each column, find a row whose leading entry is this column.
    let mut pivot_idx_for_col: Vec<Option<usize>> = vec![None; n_cols];
    let mut next_row = 0;
    while next_row < rows.len() {
        let lead = match rows[next_row].lead() {
            Some(c) => c,
            None => {
                next_row += 1;
                continue;
            }
        };
        if let Some(piv_idx) = pivot_idx_for_col[lead] {
            // Already have a pivot for column `lead`; XOR rows[next_row]
            // into pivot's clone (or vice versa).  Since we want pivot
            // to keep its smaller index, XOR into next_row and re-scan.
            let pivot_row = rows[piv_idx].clone();
            rows[next_row].xor_assign(&pivot_row);
            // Don't advance — the new leading column may collide again.
        } else {
            pivot_idx_for_col[lead] = Some(next_row);
            next_row += 1;
        }
    }
    // Drop empty rows.
    rows.retain(|r| !r.is_zero());
}

// ── Public XL functions ────────────────────────────────────────────

/// **Run boolean XL once at degree `D`** and return the reduced
/// polynomial set.
///
/// At `D = max_deg(input)`, this is essentially a one-shot linear
/// elimination of all degree-`D` linear combinations.  Increasing `D`
/// generates more `f · t` rows and can reveal new dependencies.  A
/// realistic XL loop iterates `D` upward until either the system
/// becomes zero-dimensional (i.e. has a degree-0 element = constant
/// 1, or the LT staircase covers everything below some bound) or
/// `D` reaches `n_vars` (where the boolean ring has 2^n monomials
/// and we can't do better).
pub fn boolean_xl(polys: Vec<F2BoolPoly>, n_vars: usize, max_deg: u32) -> Vec<F2BoolPoly> {
    assert!(n_vars <= 24, "XL toy implementation capped at 24 variables");
    let monos = enumerate_monomials(n_vars, max_deg);
    let mono_to_col = mono_index(&monos);
    let n_cols = monos.len();
    let mut rows = build_macaulay_matrix(&polys, &monos, &mono_to_col, max_deg);
    gaussian_eliminate_sparse(&mut rows, n_cols);
    rows.into_iter()
        .map(|r| row_to_poly(&r, &monos, n_vars))
        .collect()
}

/// **Iterative boolean XL until the polynomial set stabilises**.
///
/// Starts at `D = max_deg(input)` and grows `D` by 1 each iteration.
/// Terminates when either the reduced polynomial set hasn't changed
/// or `D` reaches `n_vars`.  The output is a system equivalent to
/// the input (same variety) but with leading terms reduced to the XL
/// staircase.
pub fn boolean_xl_iterate(polys: Vec<F2BoolPoly>, n_vars: usize) -> Vec<F2BoolPoly> {
    let mut current = polys;
    let mut prev_lt_signature: Vec<F2BoolMono> = collect_lts(&current);
    prev_lt_signature.sort_by(cmp_mono_owned);
    let mut d = current
        .iter()
        .map(|p| p.lt().map(|m| m.degree()).unwrap_or(0))
        .max()
        .unwrap_or(0)
        .max(1);
    let cap = n_vars as u32;
    while d <= cap {
        let reduced = boolean_xl(current.clone(), n_vars, d);
        let mut new_lts = collect_lts(&reduced);
        new_lts.sort_by(cmp_mono_owned);
        if new_lts == prev_lt_signature {
            // No progress — bump degree.
            d += 1;
            continue;
        }
        prev_lt_signature = new_lts;
        current = reduced;
        d += 1;
    }
    current
}

fn collect_lts(polys: &[F2BoolPoly]) -> Vec<F2BoolMono> {
    polys.iter().filter_map(|p| p.lt()).collect()
}

fn cmp_mono_owned(a: &F2BoolMono, b: &F2BoolMono) -> Ordering {
    cmp_mono(*a, *b)
}

/// **End-to-end XL solve**: run `boolean_xl` once at degree `n_vars`
/// (the maximum useful degree for the boolean ring), then brute-force
/// enumerate `{0,1}^{n_vars}` checking each candidate against the
/// reduced system.
///
/// For the boolean ring `F_2 / (v_i² − v_i)` the maximum monomial
/// degree is `n_vars`, so a single XL pass at that degree already
/// captures every linear combination of `f_i · t` that could arise.
/// The classical XL "iterate while D grows" loop is therefore
/// redundant here — we collapse it to one matrix.
pub fn boolean_xl_solve(polys: Vec<F2BoolPoly>, n_vars: usize) -> Vec<u64> {
    let reduced = boolean_xl(polys, n_vars, n_vars as u32);
    crate::cryptanalysis::pq_groebner_f2::solve_system_f2(&reduced, n_vars)
}

// ── Tests ──────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::pq_groebner_f2::{groebner_basis_f2, solve_system_f2};

    /// Sparse row XOR cancellation: `[0, 2, 5]` XOR `[0, 2, 7]` = `[5, 7]`.
    #[test]
    fn sparse_row_xor_cancels() {
        let mut a = F2SparseRow {
            cols: vec![0, 2, 5],
        };
        let b = F2SparseRow {
            cols: vec![0, 2, 7],
        };
        a.xor_assign(&b);
        assert_eq!(a.cols, vec![5, 7]);
    }

    /// `enumerate_monomials(n, max)` returns the right count.
    #[test]
    fn enumerate_monomials_size() {
        let m = enumerate_monomials(4, 2);
        // C(4, 0) + C(4, 1) + C(4, 2) = 1 + 4 + 6 = 11.
        assert_eq!(m.len(), 11);
    }

    /// **XL agrees with Buchberger on a small system**: build a system
    /// where both terminate fast, compare their solution sets.
    #[test]
    fn xl_agrees_with_buchberger_on_small() {
        // System:  v_0 v_1 + 1 = 0,  v_2 + v_0 = 0  (3 vars).
        // Solutions: v_0=v_1=1 (forced), v_2 = 1.  Just {0b111} = 7.
        let f1 = F2BoolPoly::from_monos(
            vec![
                F2BoolMono::var(0).mul(F2BoolMono::var(1)),
                F2BoolMono::one(),
            ],
            3,
        );
        let f2 = F2BoolPoly::from_monos(vec![F2BoolMono::var(2), F2BoolMono::var(0)], 3);
        let gb_sols: std::collections::HashSet<u64> =
            solve_system_f2(&groebner_basis_f2(vec![f1.clone(), f2.clone()], 3), 3)
                .into_iter()
                .collect();
        let xl_sols: std::collections::HashSet<u64> =
            boolean_xl_solve(vec![f1, f2], 3).into_iter().collect();
        assert_eq!(gb_sols, xl_sols, "XL and Buchberger should agree");
        assert!(gb_sols.contains(&0b111));
    }

    /// **XL handles a 4-variable consistent system**.  Solution:
    /// `v_0 = v_2 = 0, v_1 = v_3 = 1` → bit pattern 0b1010 = 10.
    #[test]
    fn xl_recovers_known_4var_solution() {
        // v_0 = 0
        // v_1 + 1 = 0  →  v_1 = 1
        // v_2 + v_0 = 0  →  v_2 = 0
        // v_3 + v_1 = 0  →  v_3 = 1
        let v_star: u64 = 0b1010;
        let f1 = F2BoolPoly::from_monos(vec![F2BoolMono::var(0)], 4);
        let f2 = F2BoolPoly::from_monos(vec![F2BoolMono::var(1), F2BoolMono::one()], 4);
        let f3 = F2BoolPoly::from_monos(vec![F2BoolMono::var(2), F2BoolMono::var(0)], 4);
        let f4 = F2BoolPoly::from_monos(vec![F2BoolMono::var(3), F2BoolMono::var(1)], 4);
        let sols: std::collections::HashSet<u64> = boolean_xl_solve(vec![f1, f2, f3, f4], 4)
            .into_iter()
            .collect();
        assert_eq!(sols.len(), 1);
        assert!(sols.contains(&v_star));
    }

    /// **XL detects an inconsistent system**: `v_0 = 0` AND `v_0 = 1`
    /// → no solutions.
    #[test]
    fn xl_detects_inconsistent() {
        let f1 = F2BoolPoly::from_monos(vec![F2BoolMono::var(0)], 1);
        let f2 = F2BoolPoly::from_monos(vec![F2BoolMono::var(0), F2BoolMono::one()], 1);
        let sols = boolean_xl_solve(vec![f1, f2], 1);
        assert!(sols.is_empty());
    }

    /// **XL respects boolean-ring idempotency**: any input containing
    /// `v_0² + v_0` is automatically zero in our representation.
    #[test]
    fn xl_handles_idempotency_silently() {
        // v_0² + v_0 = 0 in the boolean ring.  Building the polynomial
        // [v_0, v_0] in `from_monos` cancels → zero polynomial.
        let zero_poly = F2BoolPoly::from_monos(vec![F2BoolMono::var(0), F2BoolMono::var(0)], 2);
        assert!(zero_poly.is_zero());
        // Use a non-trivial f to get a non-empty input.
        let f = F2BoolPoly::from_monos(vec![F2BoolMono::var(0), F2BoolMono::one()], 2);
        let sols = boolean_xl_solve(vec![f], 2);
        // v_0 + 1 = 0 → v_0 = 1.  v_1 free.  Solutions: {1, 3}.
        let sol_set: std::collections::HashSet<u64> = sols.into_iter().collect();
        assert_eq!(sol_set, [0b01u64, 0b11].iter().copied().collect());
    }

    /// **Multivariate-mul cancellation**: `(v_0 + 1) · v_0 = v_0 + v_0 = 0`
    /// in the boolean ring.  Test exercises `mul_mono` going through XL.
    #[test]
    fn xl_mul_mono_cancellation() {
        // Try (v_0 + 1) · v_0 directly — it's 0 by boolean-ring identity.
        // In an XL run with this f and max_deg = 1, the only nontrivial
        // product is f · 1 = f.  Solutions: v_0 = 1, v_1 arbitrary
        // (1 var system + free var).
        let f = F2BoolPoly::from_monos(vec![F2BoolMono::var(0), F2BoolMono::one()], 1);
        let reduced = boolean_xl(vec![f.clone()], 1, 1);
        // The matrix has one row at max_deg = 1; reduction leaves it.
        assert!(!reduced.is_empty());
        // Check that f is in the reduced set (or an equivalent form).
        let sols: std::collections::HashSet<u64> =
            boolean_xl_solve(vec![f], 1).into_iter().collect();
        assert_eq!(sols, [1u64].iter().copied().collect());
    }
}
