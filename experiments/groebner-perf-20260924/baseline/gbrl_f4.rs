#![allow(dead_code)]
// F4 Gröbner basis algorithm — STRUCTURAL SCAFFOLD ONLY.
//
// This file defines the public API and data structures for an F4 engine that
// would drop into the existing rl_server / strategy framework. The hot inner
// pieces (symbolic preprocessing, Macaulay matrix construction, sparse
// reduction) are stubbed with `unimplemented!` and detailed TODOs.
//
// Why F4 vs Buchberger:
//   - Buchberger processes one S-polynomial at a time.
//   - F4 batches ALL pairs of a given lcm-degree into one matrix and reduces
//     them simultaneously via Gaussian elimination. Same Gröbner basis output,
//     ~10× faster on cyclic-n and dramatically faster on Semaev systems with
//     m ≥ 3 (where Buchberger gets stuck on basis-size blow-up).
//
// References for an implementor:
//   - Faugère (1999), "A new efficient algorithm for computing Gröbner bases (F4)".
//     The original. Sections 2-3 give Macaulay matrix construction; section 4
//     covers symbolic preprocessing.
//   - msolve (https://msolve.lip6.fr/) — open-source C implementation. Source
//     is the cleanest way to see modern engineering tradeoffs (sparse linbox,
//     finite-field SIMD).
//   - openf4 (https://github.com/nauotit/openf4) — smaller reference impl.

use crate::monomial::Monomial;
use crate::pair::CriticalPair;
use crate::poly::Poly;
use crate::spoly::spoly;
use std::collections::{HashMap, HashSet};

// Mirrors BuchbergerState's field layout so the RL env can swap engines with
// no env.rs changes.
pub struct F4State {
    pub basis: Vec<Poly>,
    pub sugars: Vec<u32>,
    pub pairs: Vec<CriticalPair>,
    pub nvars: usize,
    pub step_count: usize,
    pub arith_ops: usize,
}

pub struct F4StepResult {
    /// Number of new basis polynomials added by this matrix-reduction round.
    pub added: usize,
    pub matrix_rows: usize,
    pub matrix_cols: usize,
    pub resource_exhausted: bool,
}

impl F4State {
    pub fn new(initial: Vec<Poly>) -> Self {
        let nvars = initial.first().map(|p| p.nvars).unwrap_or(0);
        let sugars: Vec<u32> = initial.iter().map(|p| p.total_degree()).collect();
        let mut state = F4State {
            basis: initial,
            sugars,
            pairs: Vec::new(),
            nvars,
            step_count: 0,
            arith_ops: 0,
        };
        // Identical to BuchbergerState::new initial pair gen.
        for i in 0..state.basis.len() {
            for j in (i + 1)..state.basis.len() {
                state.install_pair_raw(i, j);
            }
        }
        state
    }

    fn install_pair_raw(&mut self, i: usize, j: usize) {
        // Same coprime-LM short-circuit as Buchberger; full GM is later.
        let (lmi, lmj) = match (self.basis[i].lm(), self.basis[j].lm()) {
            (Some(a), Some(b)) => (a.clone(), b.clone()),
            _ => return,
        };
        if lmi.gcd_is_one(&lmj) {
            return;
        }
        let lcm = lmi.lcm(&lmj);
        let dfi = lcm.degree() - lmi.degree();
        let dfj = lcm.degree() - lmj.degree();
        let sugar = (self.sugars[i] + dfi).max(self.sugars[j] + dfj);
        self.pairs.push(CriticalPair { i, j, lcm, sugar });
    }

    pub fn is_done(&self) -> bool {
        self.pairs.is_empty()
    }

    /// Process ONE F4 round: pick all pairs at the minimum lcm degree, build
    /// the Macaulay matrix, reduce, install nonzero rows as new basis polys.
    ///
    /// The RL action analog is: which *degree bucket* to drain next. (Plain F4
    /// always picks the minimum; signature-based variants like F5 use the
    /// Möller-Mora ordering. A learned policy could pick across non-min degrees.)
    pub fn step(&mut self, degree_idx: usize) -> F4StepResult {
        self.step_bounded(degree_idx, usize::MAX, usize::MAX)
    }

    /// Process one degree bucket with hard matrix-shape caps. The cap is
    /// checked immediately after symbolic preprocessing and before dense row
    /// reduction, so callers can record resource exhaustion without spending
    /// the reduction budget.
    pub fn step_bounded(
        &mut self,
        degree_idx: usize,
        max_rows: usize,
        max_cols: usize,
    ) -> F4StepResult {
        self.step_count += 1;
        let selected = self.select_pairs_by_degree(degree_idx);
        let s_polys = self.spolynomials_from_pairs(&selected);
        let (rows, columns) = symbolic_preprocess(s_polys, &self.basis);
        let matrix_rows = rows.len();
        let matrix_cols = columns.len();
        if matrix_rows > max_rows || matrix_cols > max_cols {
            return F4StepResult {
                added: 0,
                matrix_rows,
                matrix_cols,
                resource_exhausted: true,
            };
        }
        let reduced = matrix_reduce(rows, &columns);
        let mut added = 0;
        for p in reduced {
            if !p.is_zero() && !already_in_basis_as_lm(&p, &self.basis) {
                let idx = self.basis.len();
                self.basis.push(p);
                self.sugars.push(self.basis[idx].total_degree());
                gebauer_moller_install(self, idx);
                added += 1;
            }
        }
        F4StepResult {
            added,
            matrix_rows,
            matrix_cols,
            resource_exhausted: false,
        }
    }

    /// Bucket the queued pairs by lcm degree, return the indices in
    /// bucket # `degree_idx` (0 = lowest degree). The default F4 strategy is
    /// always degree_idx = 0 (drain the lowest first).
    fn select_pairs_by_degree(&mut self, degree_idx: usize) -> Vec<CriticalPair> {
        let mut degrees: Vec<u32> = self.pairs.iter().map(|p| p.lcm.degree()).collect();
        degrees.sort_unstable();
        degrees.dedup();
        let Some(&degree) = degrees.get(degree_idx) else {
            return Vec::new();
        };
        let mut selected = Vec::new();
        let mut rest = Vec::new();
        for pair in self.pairs.drain(..) {
            if pair.lcm.degree() == degree {
                selected.push(pair);
            } else {
                rest.push(pair);
            }
        }
        self.pairs = rest;
        selected
    }

    fn spolynomials_from_pairs(&self, pairs: &[CriticalPair]) -> Vec<Poly> {
        pairs
            .iter()
            .map(|p| spoly(&self.basis[p.i], &self.basis[p.j]))
            .collect()
    }
}

// === Stubs that need real implementation ==============================

/// Symbolic preprocessing (Faugère 1999, §3.3).
///
/// Given a set of polynomials to reduce against `basis`, walk each polynomial's
/// non-leading monomials, and for every monomial m that has a basis poly g with
/// LM(g) dividing m, add the *shifted* g (m/LM(g) * g) as an extra row so the
/// matrix-stage reduction can cancel m. Returns:
///   - rows: S-polys ∪ all shifted reductors
///   - columns: the union of monomials appearing in any row, sorted descending.
///
/// TODO: implement. Use a worklist over monomials to discover new reductors.
pub fn symbolic_preprocess(s_polys: Vec<Poly>, basis: &[Poly]) -> (Vec<Poly>, Vec<Monomial>) {
    let mut rows = s_polys;
    let mut seen: HashSet<(usize, Monomial)> = HashSet::new();
    let mut work: Vec<Monomial> = rows
        .iter()
        .flat_map(|p| p.terms.iter().map(|t| t.mono.clone()))
        .collect();
    while let Some(mono) = work.pop() {
        for (idx, g) in basis.iter().enumerate() {
            let Some(lm) = g.lm() else {
                continue;
            };
            let Some(multiplier) = mono.div(lm) else {
                continue;
            };
            if !seen.insert((idx, multiplier.clone())) {
                continue;
            }
            let shifted = g.mul_term(crate::field::Fp::one(), &multiplier);
            for term in &shifted.terms {
                work.push(term.mono.clone());
            }
            rows.push(shifted);
            break;
        }
    }
    let mut columns: Vec<Monomial> = rows
        .iter()
        .flat_map(|p| p.terms.iter().map(|t| t.mono.clone()))
        .collect();
    columns.sort_by(|a, b| b.cmp(a));
    columns.dedup();
    (rows, columns)
}

/// Macaulay matrix reduction. `rows` are polynomials viewed over the global
/// monomial set `columns` (sorted descending). Performs row-echelon reduction
/// over Fp, returns the reduced rows (still as Polys).
///
/// TODO: dense implementation first (cubic, easy), then sparse. For Fp this is
/// just Gaussian elimination with pivots ordered by leading column. Build a
/// matrix `M[B][cols] : Fp` from the rows, run REF, extract back to polys.
/// Track arith_ops for parity with BuchbergerState reporting.
pub fn matrix_reduce(rows: Vec<Poly>, columns: &[Monomial]) -> Vec<Poly> {
    if rows.is_empty() || columns.is_empty() {
        return Vec::new();
    }
    let index: HashMap<Monomial, usize> = columns
        .iter()
        .cloned()
        .enumerate()
        .map(|(i, m)| (m, i))
        .collect();
    let mut matrix: Vec<Vec<crate::field::Fp>> = rows
        .iter()
        .map(|p| {
            let mut row = vec![crate::field::Fp::zero(); columns.len()];
            for term in &p.terms {
                row[*index.get(&term.mono).expect("term missing from columns")] = term.coef;
            }
            row
        })
        .collect();
    let mut pivot_row = 0usize;
    for col in 0..columns.len() {
        let Some(found) = (pivot_row..matrix.len()).find(|&r| !matrix[r][col].is_zero()) else {
            continue;
        };
        matrix.swap(pivot_row, found);
        let inv = matrix[pivot_row][col]
            .inv()
            .expect("nonzero pivot invertible");
        for value in &mut matrix[pivot_row] {
            *value = *value * inv;
        }
        for r in 0..matrix.len() {
            if r == pivot_row || matrix[r][col].is_zero() {
                continue;
            }
            let factor = matrix[r][col];
            for c in col..columns.len() {
                matrix[r][c] = matrix[r][c] - factor * matrix[pivot_row][c];
            }
        }
        pivot_row += 1;
        if pivot_row == matrix.len() {
            break;
        }
    }
    matrix
        .into_iter()
        .filter_map(|row| {
            let terms: Vec<crate::poly::Term> = row
                .into_iter()
                .enumerate()
                .filter(|(_, c)| !c.is_zero())
                .map(|(i, c)| crate::poly::Term {
                    coef: c,
                    mono: columns[i].clone(),
                })
                .collect();
            let poly = Poly::from_terms(terms, columns[0].nvars());
            if poly.is_zero() {
                None
            } else {
                Some(poly)
            }
        })
        .collect()
}

/// Quick check: does `p`'s leading monomial coincide with an existing basis
/// LM? (Same LM → already in the ideal up to a unit; don't re-add.)
fn already_in_basis_as_lm(p: &Poly, basis: &[Poly]) -> bool {
    let lm = match p.lm() {
        Some(m) => m,
        None => return false,
    };
    basis.iter().any(|g| g.lm() == Some(lm))
}

/// Reuse the GM pruning logic from buchberger.rs when a new poly is added.
/// In a real impl this would be either copied in or refactored to a shared
/// helper. Stubbed here to keep this file self-contained.
fn gebauer_moller_install(_state: &mut F4State, _new_idx: usize) {
    // Conservative correctness-first installation for the bounded probe.
    // This intentionally installs every non-coprime pair; GM pruning is a
    // separate optimization task and is not claimed by this implementation.
    let idx = _new_idx;
    let lm_h = match _state.basis[idx].lm() {
        Some(m) => m.clone(),
        None => return,
    };
    for k in 0..idx {
        let Some(lm_k) = _state.basis[k].lm() else {
            continue;
        };
        if lm_k.gcd_is_one(&lm_h) {
            continue;
        }
        let lcm = lm_k.lcm(&lm_h);
        let sugar = (_state.sugars[k] + lcm.degree() - lm_k.degree())
            .max(_state.sugars[idx] + lcm.degree() - lm_h.degree());
        _state.pairs.push(CriticalPair {
            i: k,
            j: idx,
            lcm,
            sugar,
        });
    }
}

// === Notes on RL integration ==========================================
//
// Strategy hook in F4 is different from Buchberger: instead of "which pair",
// it's "which degree bucket" (and within a degree bucket, optionally "which
// symbolic-preprocess reductors to include"). The current pair-feature
// pipeline doesn't directly transfer. A future env.rs would expose:
//   - degree_buckets: Vec<(degree, n_pairs_in_bucket, avg_sugar, max_sugar)>
//   - and action ∈ {0..n_buckets}, defaulting to 0 = lowest degree.
// The PointerPolicy architecture (per-item embedding → logit) works as-is.

#[cfg(test)]
mod tests {
    use super::*;
    use crate::buchberger::BuchbergerState;
    use crate::field::Fp;
    use crate::poly::Term;

    fn mono(exp: &[u32]) -> Monomial {
        Monomial { exp: exp.to_vec() }
    }

    #[test]
    fn dense_matrix_reduce_returns_rref_rows() {
        let x = mono(&[1, 0]);
        let y = mono(&[0, 1]);
        let rows = vec![
            Poly::from_terms(
                vec![
                    Term {
                        coef: Fp::new(1),
                        mono: x.clone(),
                    },
                    Term {
                        coef: Fp::new(1),
                        mono: y.clone(),
                    },
                ],
                2,
            ),
            Poly::from_terms(
                vec![
                    Term {
                        coef: Fp::new(1),
                        mono: x.clone(),
                    },
                    Term {
                        coef: Fp::new(-1),
                        mono: y.clone(),
                    },
                ],
                2,
            ),
        ];
        let reduced = matrix_reduce(rows, &[x.clone(), y.clone()]);
        assert_eq!(reduced.len(), 2);
        assert_eq!(reduced[0].terms[0].coef, Fp::one());
        assert_eq!(reduced[1].terms[0].coef, Fp::one());
        assert_ne!(reduced[0].terms[0].mono, reduced[1].terms[0].mono);
    }

    #[test]
    fn symbolic_preprocess_adds_a_shifted_reducer() {
        let x = mono(&[1, 0]);
        let y = mono(&[0, 1]);
        let x2 = mono(&[2, 0]);
        let reducer = Poly::from_terms(
            vec![
                Term {
                    coef: Fp::one(),
                    mono: x2.clone(),
                },
                Term {
                    coef: Fp::one(),
                    mono: y.clone(),
                },
            ],
            2,
        );
        let input = Poly::from_terms(
            vec![
                Term {
                    coef: Fp::one(),
                    mono: x2.clone(),
                },
                Term {
                    coef: Fp::one(),
                    mono: x.mul(&y),
                },
            ],
            2,
        );
        let (rows, columns) = symbolic_preprocess(vec![input], &[reducer]);
        assert!(rows.len() >= 2);
        assert!(columns.iter().any(|m| m == &x2));
        assert!(rows.iter().any(|p| p.terms.iter().any(|t| t.mono == y)));
    }

    #[test]
    fn bounded_step_completes_tiny_common_factor_system() {
        let x = mono(&[1, 0]);
        let y = mono(&[0, 1]);
        let x2 = mono(&[2, 0]);
        let xy = x.mul(&y);
        let basis = vec![
            Poly::from_terms(
                vec![Term {
                    coef: Fp::one(),
                    mono: x2,
                }],
                2,
            ),
            Poly::from_terms(
                vec![Term {
                    coef: Fp::one(),
                    mono: xy,
                }],
                2,
            ),
        ];
        let mut state = F4State::new(basis);
        let result = state.step_bounded(0, 64, 64);
        assert!(!result.resource_exhausted);
        assert!(state.is_done());
    }

    #[test]
    fn bounded_f4_matches_buchberger_leading_monomials_on_tiny_system() {
        let x = mono(&[1, 0]);
        let y = mono(&[0, 1]);
        let basis = vec![
            Poly::from_terms(
                vec![Term {
                    coef: Fp::one(),
                    mono: x.mul(&x),
                }],
                2,
            ),
            Poly::from_terms(
                vec![Term {
                    coef: Fp::one(),
                    mono: x.mul(&y),
                }],
                2,
            ),
        ];
        let mut f4 = F4State::new(basis.clone());
        let f4_step = f4.step_bounded(0, 64, 64);
        assert!(!f4_step.resource_exhausted);
        let mut buch = BuchbergerState::new(basis);
        while !buch.is_done() {
            buch.step(0);
        }
        let mut f4_lms: Vec<_> = f4.basis.iter().filter_map(|p| p.lm()).cloned().collect();
        let mut buch_lms: Vec<_> = buch.basis.iter().filter_map(|p| p.lm()).cloned().collect();
        f4_lms.sort();
        buch_lms.sort();
        assert_eq!(f4_lms, buch_lms);
    }

    #[test]
    fn bounded_step_reports_resource_exhaustion_before_reduction() {
        let x = mono(&[1, 0]);
        let y = mono(&[0, 1]);
        let basis = vec![
            Poly::from_terms(
                vec![Term {
                    coef: Fp::one(),
                    mono: x.mul(&x),
                }],
                2,
            ),
            Poly::from_terms(
                vec![Term {
                    coef: Fp::one(),
                    mono: x.mul(&y),
                }],
                2,
            ),
        ];
        let mut state = F4State::new(basis);
        let before = state.basis.len();
        let result = state.step_bounded(0, 0, 0);
        assert!(result.resource_exhausted);
        assert_eq!(state.basis.len(), before);
    }
}
