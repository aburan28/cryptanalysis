//! # Matrix-F5 over the Boolean ring: the F5 criterion for the Koblitz Macaulay matrices.
//!
//! [`super::koblitz_groebner::matrix_f4_f2`] builds, at a degree `d`, every
//! product `t·f_i` with `deg t ≤ d − deg f_i` and row-reduces the lot.  Most
//! of what makes that expensive is rows that reduce to **zero**: products
//! that are already linear combinations of the others.  Faugère's F5
//! criterion names a large family of them in advance — the ones a *trivial*
//! syzygy predicts — so they are never built, never packed and never
//! eliminated.  This module is that criterion, in the matrix form Bardet,
//! Faugère and Salvy use to analyse semi-regular systems, adapted to the
//! Boolean ring the Koblitz oracle works in.
//!
//! ## The criterion, and why the Boolean ring needs its own
//!
//! Order the generators `f_1, …, f_m` and write `d_i = deg f_i`.  Over a
//! polynomial ring the F5 criterion says: the row `t·f_i` is redundant at
//! degree `d` whenever `t` is the leading monomial of some element of the
//! ideal `⟨f_1, …, f_{i−1}⟩` in degree `d − d_i`, because with
//! `g = t + (lower terms)` in that ideal,
//!
//! ```text
//!     t·f_i = (t + g)·f_i + g·f_i,
//! ```
//!
//! where `(t+g)·f_i` is a sum of rows of `f_i` with smaller multipliers
//! and `g·f_i` lies in the span of the rows of `f_1, …, f_{i−1}`.  Induction
//! over the signature order `(i, t)` makes every pruned row a combination
//! of the rows kept.  Over `F_2` with the field equations `x² = x` there is
//! a second trivial syzygy, the Frobenius one: `f_i² = f_i`, i.e.
//! `(f_i + 1)·f_i = 0`, and with it `s·(f_i + 1)·f_i = 0` for every
//! monomial `s`.
//!
//! The textbook adaptation — "prune `t·f_i` when `t ∈ LM⟨f_1, …, f_i⟩`",
//! with `f_i` itself included to stand for the Frobenius syzygy — is **not
//! sound** in the Boolean ring, because multiplying by a monomial is not
//! order-compatible there: `x₁·(x₁x₂ + x₁ + x₂) = x₁`, a *smaller* leading
//! monomial.  The induction over signatures then runs the wrong way and a
//! pruned row can leave the row space (the test
//! `naive_f2_criterion_is_unsound_in_the_boolean_ring` keeps the
//! counterexample).  What is sound is to use the Frobenius syzygies as the
//! polynomials they are.  Let
//!
//! ```text
//!     W_i(d) = V_{i−1}(d − d_i)  +  span{ s·(f_i + 1) : deg s ≤ d − 2·d_i },
//!     V_j(e) = span{ s·f_k : k ≤ j, deg s ≤ e − d_k }.
//! ```
//!
//! Then for `t ∈ LM(W_i(d))` with witness `g = g' + σ` (`g' ∈ V_{i−1}`,
//! `σ` in the Frobenius span, `LM(g) = t`),
//!
//! ```text
//!     t·f_i = (t + g)·f_i + g'·f_i + σ·f_i = (t + g)·f_i + g'·f_i,
//! ```
//!
//! since `σ·f_i = 0` identically.  Every monomial of `t + g` is below `t`
//! in a degree-compatible order, so has degree `≤ d − d_i` and names a row
//! of `f_i` with smaller signature, and `g'·f_i` is a combination of rows of
//! `f_1, …, f_{i−1}` at degree `d`, because `(s·f_i)·f_k` expands into
//! multiples of `f_k` of degree `≤ d`.  That is the criterion implemented
//! here: **prune `(t, i)` iff `t ∈ LM(W_i(d))`.**  Pruning never changes the
//! row space, so a solver that reads consequences off the reduced rows gets
//! the same consequences from fewer rows.
//!
//! ## Cost accounting
//!
//! The leading-monomial sets come from echelonising the lower-degree
//! Macaulay matrices `V_j(e)` incrementally in generator order, one pass
//! per distinct `e = d − d_i`.  That work is real and is charged in the
//! same unit as the reduction it saves — 64-bit word XORs — through
//! [`F5Criterion::word_ops`], so a caller adding the two sees the
//! method's cost, not the phase's.  On a quadratic system at `d = 3` the
//! lower levels are the linear equations (level 1) and the equations
//! themselves plus linear equations times variables (level 2): a few
//! hundred rows over a few hundred columns against the degree-3 matrix's
//! thousands.
//!
//! ## What this is and is not
//!
//! This is the F5 *criterion* as a row filter over the Macaulay matrix,
//! with the same elimination kernels and the same output as the F4 step —
//! the ingredient of F5 that removes reductions to zero, without F5's
//! incremental basis construction or signature-compatible reduction, which
//! a fixed-degree matrix that only needs the row space does not require.
//! The zero reductions it removes are the trivial ones.  Semaev systems
//! have many non-trivial syzygies at low degree (their first fall degree
//! is where the attack lives), and those are not predicted here.
//! [`F5Report`] separates the two so a reader sees which share was
//! removable in principle.
//!
//! ## References
//!
//! - J.-C. Faugère, *A new efficient algorithm for computing Gröbner bases
//!   without reduction to zero (F5)*, ISSAC 2002.
//! - M. Bardet, J.-C. Faugère, B. Salvy, *On the complexity of Gröbner
//!   basis computation of semi-regular overdetermined algebraic
//!   equations*, ICPSS 2004 — the matrix-F5 formulation.
//! - M. Bardet, J.-C. Faugère, B. Salvy, B.-Y. Yang, *Asymptotic behaviour
//!   of the degree of regularity of semi-regular polynomial systems*,
//!   MEGA 2005 — the `F_2` variant with field equations.
//! - C. Eder, J.-C. Faugère, *A survey on signature-based algorithms for
//!   computing Gröbner bases*, J. Symbolic Comput. 80 (2017).

use crate::cryptanalysis::koblitz_groebner::{
    all_variable_mask, macaulay_columns, monomials_up_to_mask, occurring_vars,
};
use crate::cryptanalysis::pq_groebner_f2::{F2BoolMono, F2BoolPoly};
use std::collections::{HashMap, HashSet};

/// Degree of a Boolean polynomial (`0` for a constant or zero).
fn poly_degree(p: &F2BoolPoly) -> u32 {
    p.terms
        .iter()
        .map(|t| t.mask.count_ones())
        .max()
        .unwrap_or(0)
}

/// Product `p · s` as a set of monomial masks with even multiplicities
/// cancelled — the same row construction as the F4 builder, kept here so
/// the criterion's rows and the matrix's rows cannot disagree.
fn product_monos(p: &F2BoolPoly, s: u64) -> Vec<u64> {
    let mut all: Vec<u64> = p.terms.iter().map(|t| t.mask | s).collect();
    all.sort_unstable();
    let mut out = Vec::with_capacity(all.len());
    let mut i = 0;
    while i < all.len() {
        let mut j = i;
        while j < all.len() && all[j] == all[i] {
            j += 1;
        }
        if (j - i) % 2 == 1 {
            out.push(all[i]);
        }
        i = j;
    }
    out
}

/// A row echelon basis grown one row at a time, in generator order.
///
/// Columns are monomials in descending order, so a packed row's leading
/// monomial is its lowest set column.  Inserting a row reduces its leading
/// column against existing pivots until it either becomes a new pivot or
/// vanishes.  The pivot columns present after the rows of `f_1, …, f_j`
/// have been inserted are exactly `LM(V_j(e))`, and `created_at` records
/// which prefix each pivot first appeared in so that every prefix's
/// leading-monomial set can be read off one structure.
struct PrefixEchelon {
    columns: Vec<u64>,
    index: HashMap<u64, usize>,
    words: usize,
    /// `pivot[c]` is the index into `rows` of the row leading at column `c`.
    pivot: Vec<Option<usize>>,
    rows: Vec<Vec<u64>>,
    /// Prefix (generator index, 1-based) whose insertion created the pivot.
    created_at: Vec<usize>,
    word_ops: u64,
    inserted: u64,
    zero_reductions: u64,
}

fn leading_column(row: &[u64]) -> Option<usize> {
    row.iter()
        .enumerate()
        .find(|(_, &w)| w != 0)
        .map(|(i, &w)| i * 64 + w.trailing_zeros() as usize)
}

impl PrefixEchelon {
    fn new(columns: Vec<u64>) -> Self {
        let index = columns.iter().enumerate().map(|(i, &m)| (m, i)).collect();
        let words = columns.len().div_ceil(64).max(1);
        Self {
            pivot: vec![None; columns.len()],
            columns,
            index,
            words,
            rows: Vec::new(),
            created_at: Vec::new(),
            word_ops: 0,
            inserted: 0,
            zero_reductions: 0,
        }
    }

    fn pack(&self, monos: &[u64]) -> Option<Vec<u64>> {
        let mut row = vec![0u64; self.words];
        for m in monos {
            let &c = self.index.get(m)?;
            row[c / 64] |= 1u64 << (c % 64);
        }
        Some(row)
    }

    /// Reduce `row`'s leading column against `self` (and `extra`, a
    /// temporary echelon over the same columns) until it is a fresh
    /// leading column or zero.  Returns that column.
    fn reduce_leading(&mut self, row: &mut [u64], extra: Option<&TempEchelon>) -> Option<usize> {
        loop {
            let c = leading_column(row)?;
            let w = c / 64;
            if let Some(r) = self.pivot[c] {
                let pivot = &self.rows[r];
                for (dst, &src) in row[w..].iter_mut().zip(&pivot[w..]) {
                    *dst ^= src;
                }
                self.word_ops += (self.words - w) as u64;
                continue;
            }
            if let Some(extra) = extra {
                if let Some(r) = extra.pivot.get(&c) {
                    let pivot = &extra.rows[*r];
                    for (dst, &src) in row[w..].iter_mut().zip(&pivot[w..]) {
                        *dst ^= src;
                    }
                    self.word_ops += (self.words - w) as u64;
                    continue;
                }
            }
            return Some(c);
        }
    }

    /// Insert one row of generator `prefix` (1-based).
    fn insert(&mut self, mut row: Vec<u64>, prefix: usize) {
        self.inserted += 1;
        match self.reduce_leading(&mut row, None) {
            Some(c) => {
                self.pivot[c] = Some(self.rows.len());
                self.rows.push(row);
                self.created_at.push(prefix);
            }
            None => self.zero_reductions += 1,
        }
    }

    /// Leading monomials of `V_j(e)` for `j = prefix`.
    fn leading_monomials(&self, prefix: usize) -> impl Iterator<Item = u64> + '_ {
        self.rows
            .iter()
            .zip(&self.created_at)
            .filter(move |(_, &created)| created <= prefix)
            .filter_map(|(row, _)| leading_column(row))
            .map(|c| self.columns[c])
    }
}

/// Pivots added on top of a [`PrefixEchelon`] for one generator's
/// Frobenius span, then discarded.
#[derive(Default)]
struct TempEchelon {
    pivot: HashMap<usize, usize>,
    rows: Vec<Vec<u64>>,
}

/// The F5 criterion evaluated for one system at one degree: which
/// multipliers of which generator are pruned, and what it cost to know.
#[derive(Clone, Debug)]
pub struct F5Criterion {
    /// `pruned[i]` is the set of multiplier monomials `t` with
    /// `t ∈ LM(W_i(d))`; `t·f_i` is redundant at this degree.
    pruned: Vec<HashSet<u64>>,
    /// Word XORs spent echelonising the lower-degree matrices.
    word_ops: u64,
    /// Rows inserted into the lower-degree echelons.
    lower_rows: u64,
    /// Of those, rows that reduced to zero.
    lower_zero_reductions: u64,
    /// Pruned multipliers predicted by the Koszul part `V_{i−1}(d − d_i)`.
    koszul_pruned: u64,
    /// Pruned multipliers predicted only once the Frobenius span is added.
    frobenius_pruned: u64,
}

impl F5Criterion {
    /// Evaluate the criterion for `polys` (in the given order) at `degree`,
    /// with multipliers drawn from `multiplier_mask`.
    ///
    /// The lower-level matrices are built over the variables occurring in
    /// the system together with the multiplier mask, which is the subring
    /// every row of the degree-`degree` matrix lives in.
    pub fn new(polys: &[F2BoolPoly], n_vars: usize, degree: u32, multiplier_mask: u64) -> Self {
        let m = polys.len();
        let mut out = Self {
            pruned: vec![HashSet::new(); m],
            word_ops: 0,
            lower_rows: 0,
            lower_zero_reductions: 0,
            koszul_pruned: 0,
            frobenius_pruned: 0,
        };
        if polys.is_empty() {
            return out;
        }
        let degrees: Vec<u32> = polys.iter().map(poly_degree).collect();
        // A constant generator (`1`, or zero) is outside the criterion's
        // hypotheses; the solver never passes one, so prune nothing.
        if degrees.contains(&0) {
            return out;
        }
        let column_mask = occurring_vars(polys) | (multiplier_mask & all_variable_mask(n_vars));

        // Distinct lower levels e = d − d_i, each echelonised once.
        let mut levels: Vec<u32> = degrees
            .iter()
            .filter(|&&di| di <= degree)
            .map(|&di| degree - di)
            .collect();
        levels.sort_unstable();
        levels.dedup();

        for e in levels {
            let columns = match macaulay_columns(&[monomials_up_to_mask(column_mask, e)]) {
                Some(c) => c,
                None => continue,
            };
            let mut echelon = PrefixEchelon::new(columns);
            for (i, (p, &di)) in polys.iter().zip(&degrees).enumerate() {
                let prefix = i + 1;
                // The criterion for f_i at this level is read before f_i's
                // own rows enter: W_i(d) = V_{i−1}(e) + Frobenius span of f_i.
                if di <= degree && degree - di == e {
                    let mut pruned: HashSet<u64> = echelon.leading_monomials(i).collect();
                    out.koszul_pruned += pruned.len() as u64;
                    if degree >= 2 * di {
                        let gap = degree - 2 * di;
                        let mut temp = TempEchelon::default();
                        let f_plus_one = p.add(&F2BoolPoly::one(p.n_vars));
                        for s in monomials_up_to_mask(multiplier_mask, gap) {
                            let monos = product_monos(&f_plus_one, s);
                            if monos.is_empty() {
                                continue;
                            }
                            let Some(mut row) = echelon.pack(&monos) else {
                                continue;
                            };
                            if let Some(c) = echelon.reduce_leading(&mut row, Some(&temp)) {
                                temp.pivot.insert(c, temp.rows.len());
                                temp.rows.push(row);
                            }
                        }
                        for &c in temp.pivot.keys() {
                            if pruned.insert(echelon.columns[c]) {
                                out.frobenius_pruned += 1;
                            }
                        }
                    }
                    out.pruned[i] = pruned;
                }
                if di > e {
                    continue;
                }
                for s in monomials_up_to_mask(multiplier_mask, e - di) {
                    let monos = product_monos(p, s);
                    if monos.is_empty() {
                        continue;
                    }
                    if let Some(row) = echelon.pack(&monos) {
                        echelon.insert(row, prefix);
                    }
                }
            }
            out.word_ops += echelon.word_ops;
            out.lower_rows += echelon.inserted;
            out.lower_zero_reductions += echelon.zero_reductions;
        }
        out
    }

    /// Is the row `t·f_i` (generator index `i`, 0-based) pruned?
    pub fn prunes(&self, i: usize, t: u64) -> bool {
        self.pruned.get(i).is_some_and(|set| set.contains(&t))
    }

    /// Total multipliers pruned across all generators.
    pub fn pruned_count(&self) -> u64 {
        self.pruned.iter().map(|s| s.len() as u64).sum()
    }

    /// Word XORs spent evaluating the criterion.
    pub fn word_ops(&self) -> u64 {
        self.word_ops
    }

    /// Rows inserted into the lower-degree echelons and how many of them
    /// reduced to zero.
    pub fn lower_level_rows(&self) -> (u64, u64) {
        (self.lower_rows, self.lower_zero_reductions)
    }

    /// How many pruned multipliers each part of the criterion predicted:
    /// `(koszul, frobenius)`.
    pub fn pruned_by_part(&self) -> (u64, u64) {
        (self.koszul_pruned, self.frobenius_pruned)
    }
}

/// What one matrix-F5 step did, beside its rows.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct F5Report {
    /// Degree the matrix was built at.
    pub degree: u32,
    /// Rows the plain F4 step would have built.
    pub rows_f4: u64,
    /// Rows the criterion removed.
    pub rows_pruned: u64,
    /// Rows actually built and reduced.
    pub rows_built: u64,
    /// Columns of the matrix.
    pub cols: u64,
    /// Rank of the reduced matrix (equal to the F4 rank: same row space).
    pub rank: u64,
    /// Rows built that still reduced to zero — the non-trivial syzygies
    /// the criterion does not see.
    pub zero_reductions: u64,
    /// Word XORs in the degree-`degree` elimination.
    pub reduce_word_ops: u64,
    /// Word XORs spent evaluating the criterion.
    pub criterion_word_ops: u64,
    /// Rows of the lower-degree echelons the criterion built.
    pub criterion_rows: u64,
}

impl F5Report {
    /// Total word XORs charged to the step: elimination plus criterion.
    pub fn word_ops(&self) -> u64 {
        self.reduce_word_ops + self.criterion_word_ops
    }
}

/// **Matrix-F5 step over `F_2`**: the Macaulay matrix of `polys` at
/// `degree` with the F5 criterion applied, reduced to row echelon form and
/// returned as polynomials — the same row space as
/// [`super::koblitz_groebner::matrix_f4_f2`] from fewer rows.
///
/// Returns `None` if the matrix would exceed the size limits the F4 step
/// uses.
pub fn matrix_f5_f2(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
) -> Option<(Vec<F2BoolPoly>, F5Report)> {
    use crate::cryptanalysis::koblitz_groebner::{
        f5_rows_monos_with_mask, macaulay_row_count, pack_rows, rref_f2_counted,
    };
    let mut report = F5Report {
        degree,
        ..Default::default()
    };
    if polys.is_empty() {
        return Some((Vec::new(), report));
    }
    let mask = all_variable_mask(n_vars);
    let criterion = F5Criterion::new(polys, n_vars, degree, mask);
    report.criterion_word_ops = criterion.word_ops();
    report.criterion_rows = criterion.lower_level_rows().0;
    report.rows_f4 = macaulay_row_count(polys, n_vars, degree)? as u64;
    let rows_monos = f5_rows_monos_with_mask(polys, n_vars, degree, mask, &criterion)?;
    report.rows_built = rows_monos.len() as u64;
    report.rows_pruned = report.rows_f4 - report.rows_built;
    if rows_monos.is_empty() {
        return Some((Vec::new(), report));
    }
    let cols = macaulay_columns(&rows_monos)?;
    let mut matrix = pack_rows(&rows_monos, &cols);
    let mut word_ops = 0u64;
    let rank = rref_f2_counted(&mut matrix, cols.len(), &mut word_ops);
    report.cols = cols.len() as u64;
    report.rank = rank as u64;
    report.zero_reductions = report.rows_built - rank as u64;
    report.reduce_word_ops = word_ops;
    let n_vars_out = polys[0].n_vars;
    // one polynomial per pivot row, independently: dense rows after the
    // back-substitution make this as long as the elimination on one thread
    use rayon::prelude::*;
    let out = matrix[..rank]
        .par_iter()
        .map(|row| {
            // walk the set bits, not every column
            let mut monos: Vec<F2BoolMono> = Vec::new();
            for (w, &word) in row.iter().enumerate() {
                let mut bits = word;
                while bits != 0 {
                    let c = w * 64 + bits.trailing_zeros() as usize;
                    bits &= bits - 1;
                    monos.push(F2BoolMono::from_mask(cols[c]));
                }
            }
            F2BoolPoly::from_monos(monos, n_vars_out)
        })
        .filter(|p| !p.is_zero())
        .collect();
    Some((out, report))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::koblitz_groebner::matrix_f4_f2;

    fn poly(n_vars: usize, monos: &[&[u32]]) -> F2BoolPoly {
        F2BoolPoly::from_monos(
            monos
                .iter()
                .map(|vars| {
                    F2BoolMono::from_mask(vars.iter().fold(0u64, |acc, &v| acc | (1u64 << v)))
                })
                .collect(),
            n_vars,
        )
    }

    /// Deterministic random Boolean polynomial of degree ≤ `deg`.
    fn random_poly(n_vars: usize, deg: u32, terms: usize, seed: &mut u64) -> F2BoolPoly {
        let mut next = || {
            *seed ^= *seed << 13;
            *seed ^= *seed >> 7;
            *seed ^= *seed << 17;
            *seed
        };
        let mut monos = Vec::new();
        for _ in 0..terms {
            let d = (next() % (deg as u64 + 1)) as u32;
            let mut mask = 0u64;
            for _ in 0..d {
                mask |= 1u64 << (next() % n_vars as u64);
            }
            monos.push(F2BoolMono::from_mask(mask));
        }
        F2BoolPoly::from_monos(monos, n_vars)
    }

    /// Reduced row echelon basis of a polynomial list (no multiplication),
    /// as a canonical set.
    fn row_space_canonical(polys: &[F2BoolPoly], n_vars: usize) -> Vec<F2BoolPoly> {
        use crate::cryptanalysis::koblitz_groebner::{pack_rows, rref_f2_counted};
        let rows_monos: Vec<Vec<u64>> = polys
            .iter()
            .filter(|p| !p.is_zero())
            .map(|p| p.terms.iter().map(|t| t.mask).collect())
            .collect();
        if rows_monos.is_empty() {
            return Vec::new();
        }
        let cols = macaulay_columns(&rows_monos).unwrap();
        let mut matrix = pack_rows(&rows_monos, &cols);
        let mut ops = 0;
        let rank = rref_f2_counted(&mut matrix, cols.len(), &mut ops);
        let mut rows: Vec<F2BoolPoly> = matrix
            .iter()
            .take(rank)
            .map(|row| {
                let monos: Vec<F2BoolMono> = (0..cols.len())
                    .filter(|c| row[c / 64] & (1u64 << (c % 64)) != 0)
                    .map(|c| F2BoolMono::from_mask(cols[c]))
                    .collect();
                F2BoolPoly::from_monos(monos, n_vars)
            })
            .collect();
        rows.sort_by(|a, b| format!("{a:?}").cmp(&format!("{b:?}")));
        rows
    }

    #[test]
    fn f5_rows_span_the_f4_row_space_on_random_systems() {
        let mut seed = 0x9e37_79b9_7f4a_7c15u64;
        for trial in 0..40 {
            let n_vars = 5 + (trial % 4);
            let m = 3 + (trial % 5);
            let polys: Vec<F2BoolPoly> = (0..m)
                .map(|k| {
                    let deg = if k % 3 == 0 { 1 } else { 2 };
                    random_poly(n_vars, deg, 4 + k, &mut seed)
                })
                .filter(|p| poly_degree(p) >= 1)
                .collect();
            if polys.is_empty() {
                continue;
            }
            for degree in 2..=4u32 {
                let f4 = matrix_f4_f2(&polys, n_vars, degree).unwrap();
                let (f5, report) = matrix_f5_f2(&polys, n_vars, degree).unwrap();
                assert_eq!(
                    row_space_canonical(&f4, n_vars),
                    row_space_canonical(&f5, n_vars),
                    "trial {trial} degree {degree}: row spaces differ"
                );
                assert_eq!(f4.len() as u64, report.rank, "rank must agree");
                assert_eq!(report.rows_built + report.rows_pruned, report.rows_f4);
            }
        }
    }

    #[test]
    fn frobenius_criterion_prunes_the_leading_monomial_multiple() {
        // One quadratic generator at degree 4: the only trivial syzygy is
        // Frobenius, so exactly one multiplier — LM(f) — is pruned, and the
        // pruned row is still in the span.
        let n_vars = 4;
        let f = poly(n_vars, &[&[0, 1], &[2], &[]]);
        let (_, report) = matrix_f5_f2(std::slice::from_ref(&f), n_vars, 4).unwrap();
        assert_eq!(report.rows_pruned, 1);
        let c = F5Criterion::new(
            std::slice::from_ref(&f),
            n_vars,
            4,
            all_variable_mask(n_vars),
        );
        assert!(c.prunes(0, f.lt().unwrap().mask));
        assert_eq!(c.pruned_by_part(), (0, 1));
    }

    #[test]
    fn koszul_criterion_prunes_leading_monomials_of_earlier_generators() {
        // Two linear generators, degree 2: t·f_2 is pruned for t = LM(f_1)
        // (Koszul) and t = LM(f_2) (Frobenius, since 2 ≥ 2·1).
        let n_vars = 4;
        let f1 = poly(n_vars, &[&[0], &[1]]);
        let f2 = poly(n_vars, &[&[2], &[3], &[]]);
        let c = F5Criterion::new(
            &[f1.clone(), f2.clone()],
            n_vars,
            2,
            all_variable_mask(n_vars),
        );
        assert!(c.prunes(1, f1.lt().unwrap().mask));
        assert!(c.prunes(1, f2.lt().unwrap().mask));
        assert!(c.prunes(0, f1.lt().unwrap().mask));
        assert!(!c.prunes(0, f2.lt().unwrap().mask));
        let f4 = matrix_f4_f2(&[f1.clone(), f2.clone()], n_vars, 2).unwrap();
        let (f5, report) = matrix_f5_f2(&[f1, f2], n_vars, 2).unwrap();
        assert_eq!(
            row_space_canonical(&f4, n_vars),
            row_space_canonical(&f5, n_vars)
        );
        assert_eq!(report.rows_pruned, 3);
    }

    /// The `F_2` criterion quoted from the semi-regularity literature —
    /// "prune `t·f_i` for `t ∈ LM⟨f_1..f_i⟩`", with `f_i` included to stand
    /// for the Frobenius syzygy — is unsound in the Boolean ring, because
    /// `x₁·(x₁x₂ + x₁ + x₂) = x₁` has a smaller leading monomial than its
    /// multiplier.  Pinned so nobody "simplifies" the criterion back to it.
    #[test]
    fn naive_f2_criterion_is_unsound_in_the_boolean_ring() {
        let n_vars = 3;
        let f = poly(n_vars, &[&[0, 1], &[0], &[1]]);
        let degree = 5;
        // Naive pruned set: LM of V_1(3) = span{s·f : deg s ≤ 1}.
        let level: Vec<F2BoolPoly> = monomials_up_to_mask(all_variable_mask(n_vars), 1)
            .into_iter()
            .map(|s| f.mul_mono(F2BoolMono::from_mask(s)))
            .collect();
        let naive: HashSet<u64> = row_space_canonical(&level, n_vars)
            .iter()
            .filter_map(|p| p.lt().map(|m| m.mask))
            .collect();
        assert!(
            naive.contains(&0b01) && naive.contains(&0b10),
            "x₀ and x₁ are naive LMs"
        );
        // Rows kept by the naive rule, and their span:
        let kept: Vec<F2BoolPoly> = monomials_up_to_mask(all_variable_mask(n_vars), degree - 2)
            .into_iter()
            .filter(|t| !naive.contains(t))
            .map(|t| f.mul_mono(F2BoolMono::from_mask(t)))
            .collect();
        let full = matrix_f4_f2(std::slice::from_ref(&f), n_vars, degree).unwrap();
        let naive_space = row_space_canonical(&kept, n_vars);
        assert!(
            naive_space.len() < full.len(),
            "the naive criterion must lose rank here, or the counterexample is gone"
        );
        // The sound criterion keeps the full row space.
        let (f5, report) = matrix_f5_f2(&[f], n_vars, degree).unwrap();
        assert_eq!(f5.len(), full.len());
        assert_eq!(
            row_space_canonical(&full, n_vars),
            row_space_canonical(&f5, n_vars)
        );
        assert!(report.rows_pruned > 0);
    }

    #[test]
    fn criterion_prunes_nothing_for_quadratics_at_degree_three() {
        // W_i(3) = V_{i−1}(1): with no linear generators there is nothing
        // to prune, so the F5 step is exactly the F4 step.
        let n_vars = 6;
        let mut seed = 42;
        let polys: Vec<F2BoolPoly> = (0..5)
            .map(|_| random_poly(n_vars, 2, 6, &mut seed))
            .filter(|p| poly_degree(p) == 2)
            .collect();
        let (_, report) = matrix_f5_f2(&polys, n_vars, 3).unwrap();
        assert_eq!(report.rows_pruned, 0);
    }
}
