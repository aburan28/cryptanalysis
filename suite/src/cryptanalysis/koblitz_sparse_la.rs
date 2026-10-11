//! # Relation filtering and block Wiedemann for the Koblitz logarithm precompute.
//!
//! The factor-base logarithm database
//! ([`super::koblitz_index_calculus::solve_factor_base_logs`]) is the
//! solution of one linear system over `Z/rZ`:
//!
//! ```text
//!     Σ_o c_{i,o} · x_o  ≡  h·a_i   (mod r)         one row per relation,
//! ```
//!
//! with `x_o` the unknown logarithm of projected column `o`.  Each row
//! has at most `m` nonzero entries (`m` summands per decomposition), so
//! for a factor base with thousands of columns the matrix is extremely
//! sparse and dense Gaussian elimination — `O(rows · cols²)` big-integer
//! operations, repeated on every attempt — is the wrong tool.  This
//! module gives the ECDLP pipeline the two stages every number-field
//! sieve driver puts between relation collection and the logarithm
//! solve:
//!
//! 1. **Filtering** ([`filter_relations`]): duplicate rows are dropped;
//!    a column that occurs in exactly one row (a *singleton*) is
//!    eliminated together with that row and recovered afterwards by
//!    back-substitution; surplus rows beyond a target excess are
//!    removed, choosing rows whose removal cascades through the
//!    weight-2 columns (the clique rule); and light columns are merged
//!    away by structured Gaussian elimination under a fill-in bound.
//!    Every elimination is recorded so the eliminated unknowns are
//!    reconstructed exactly from the core solution.
//! 2. **Block Wiedemann** ([`block_wiedemann_kernel`]): the reduced core
//!    is made square by folding its excess rows into random earlier
//!    rows, homogenised to `M (x, 1)ᵀ = 0`, and a kernel vector is found
//!    from the Krylov sequence `X Mⁱ Y` (`m × n` blocks) through a
//!    shifted minimal approximant basis — the matrix Berlekamp–Massey
//!    step of Coppersmith's algorithm.  Only sparse matrix-times-block
//!    products touch the matrix, and they run in parallel over rows.
//!
//! The solution is checked against every original row before it is
//! returned, and the caller certifies each logarithm in the group
//! (`[x_o]G == R_o`), so a wrong answer cannot escape.  The dense solver
//! in [`super::ec_index_calculus::gaussian_eliminate_mod_n`] remains the
//! reference the tests cross-check against.
//!
//! ## References
//!
//! - D. Wiedemann, *Solving sparse linear equations over finite fields*,
//!   IEEE Trans. Inf. Theory 32 (1986).
//! - D. Coppersmith, *Solving homogeneous linear equations over GF(2)
//!   via block Wiedemann algorithm*, Math. Comp. 62 (1994).
//! - E. Kaltofen, *Analysis of Coppersmith's block Wiedemann algorithm
//!   for the parallel solution of sparse linear systems*, Math. Comp. 64
//!   (1995).
//! - B. Beckermann, G. Labahn, *A uniform approach for the fast
//!   computation of matrix-type Padé approximants*, SIAM J. Matrix Anal.
//!   Appl. 15 (1994); P. Giorgi, C.-P. Jeannerod, G. Villard, *On the
//!   complexity of polynomial matrix computations*, ISSAC 2003 (the
//!   iterative order basis used for the matrix Berlekamp–Massey step).
//! - C. Bouvier, *The filtering step of discrete logarithm and integer
//!   factorization algorithms*, 2013 (singleton, clique and merge
//!   rules as run by CADO-NFS).

use num_bigint::BigUint;
use rand::{rngs::StdRng, Rng, SeedableRng};
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use std::cmp::Reverse;
use std::collections::{BinaryHeap, HashMap, HashSet};

// ── Modular arithmetic over Z/rZ with r < 2^63 ─────────────────────

#[inline]
fn mulmod(a: u64, b: u64, m: u64) -> u64 {
    ((a as u128 * b as u128) % m as u128) as u64
}

#[inline]
fn addmod(a: u64, b: u64, m: u64) -> u64 {
    let s = a + b;
    if s >= m {
        s - m
    } else {
        s
    }
}

#[inline]
fn submod(a: u64, b: u64, m: u64) -> u64 {
    if a >= b {
        a - b
    } else {
        a + (m - b)
    }
}

#[inline]
fn negmod(a: u64, m: u64) -> u64 {
    if a == 0 {
        0
    } else {
        m - a
    }
}

/// Modular inverse by the extended Euclidean algorithm; `None` when
/// `a` and `m` are not coprime (impossible for prime `m` and `a ≠ 0`).
fn invmod(a: u64, m: u64) -> Option<u64> {
    let (mut old_r, mut r) = (a as i128, m as i128);
    let (mut old_s, mut s) = (1i128, 0i128);
    while r != 0 {
        let q = old_r / r;
        (old_r, r) = (r, old_r - q * r);
        (old_s, s) = (s, old_s - q * s);
    }
    if old_r != 1 {
        return None;
    }
    Some(old_s.rem_euclid(m as i128) as u64)
}

fn to_u64_mod(v: &BigUint, m: u64) -> u64 {
    let reduced = v % BigUint::from(m);
    reduced.to_u64_digits().first().copied().unwrap_or(0)
}

/// The largest modulus the `u64` arithmetic here supports: sums of two
/// residues must not overflow.
pub const MAX_MODULUS_BITS: u64 = 63;

/// Whether a subgroup order can be handled by this module.
pub fn modulus_supported(r: &BigUint) -> bool {
    r.bits() <= MAX_MODULUS_BITS && *r >= BigUint::from(2u32)
}

// ── Sparse rows ────────────────────────────────────────────────────

/// One relation row `Σ c · x_col ≡ rhs (mod r)`: `(column, coefficient)`
/// pairs sorted by column, coefficients nonzero and reduced.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct SparseRow {
    pub entries: Vec<(u32, u64)>,
    pub rhs: u64,
}

impl SparseRow {
    /// Build a row from unsorted, possibly repeated, unreduced entries.
    pub fn new(mut entries: Vec<(u32, u64)>, rhs: u64, modulus: u64) -> Self {
        entries.sort_by_key(|&(c, _)| c);
        let mut merged: Vec<(u32, u64)> = Vec::with_capacity(entries.len());
        for (c, v) in entries {
            let v = v % modulus;
            match merged.last_mut() {
                Some((lc, lv)) if *lc == c => *lv = addmod(*lv, v, modulus),
                _ => merged.push((c, v)),
            }
        }
        merged.retain(|&(_, v)| v != 0);
        Self {
            entries: merged,
            rhs: rhs % modulus,
        }
    }

    /// A row from the dense big-integer form the relation collector
    /// produces.
    pub fn from_dense(row: &[BigUint], rhs: &BigUint, modulus: u64) -> Self {
        let entries = row
            .iter()
            .enumerate()
            .filter_map(|(c, v)| {
                let v = to_u64_mod(v, modulus);
                (v != 0).then_some((c as u32, v))
            })
            .collect();
        Self {
            entries,
            rhs: to_u64_mod(rhs, modulus),
        }
    }

    /// Number of nonzero coefficients.
    pub fn weight(&self) -> usize {
        self.entries.len()
    }

    fn coefficient(&self, col: u32) -> Option<u64> {
        self.entries
            .binary_search_by_key(&col, |&(c, _)| c)
            .ok()
            .map(|i| self.entries[i].1)
    }

    /// `Σ c · x_col mod r` for a full assignment `x`.
    fn evaluate(&self, x: &[u64], modulus: u64) -> u64 {
        self.entries.iter().fold(0u64, |acc, &(c, v)| {
            addmod(acc, mulmod(v, x[c as usize], modulus), modulus)
        })
    }

    /// `self − factor · other`, entries merged by column.
    fn axpy(&self, factor: u64, other: &SparseRow, modulus: u64) -> SparseRow {
        let mut entries = Vec::with_capacity(self.entries.len() + other.entries.len());
        let (mut i, mut j) = (0, 0);
        while i < self.entries.len() || j < other.entries.len() {
            let take_self = j >= other.entries.len()
                || (i < self.entries.len() && self.entries[i].0 < other.entries[j].0);
            let take_other = i >= self.entries.len()
                || (j < other.entries.len() && other.entries[j].0 < self.entries[i].0);
            if take_self {
                entries.push(self.entries[i]);
                i += 1;
            } else if take_other {
                let (c, v) = other.entries[j];
                entries.push((c, negmod(mulmod(factor, v, modulus), modulus)));
                j += 1;
            } else {
                let (c, a) = self.entries[i];
                let b = other.entries[j].1;
                let v = submod(a, mulmod(factor, b, modulus), modulus);
                if v != 0 {
                    entries.push((c, v));
                }
                i += 1;
                j += 1;
            }
        }
        SparseRow {
            entries,
            rhs: submod(self.rhs, mulmod(factor, other.rhs, modulus), modulus),
        }
    }
}

// ── Filtering ──────────────────────────────────────────────────────

/// Controls for [`filter_relations`].
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct FilterOptions {
    /// Drop rows identical to an earlier one.
    pub remove_duplicates: bool,
    /// Eliminate singleton columns with their rows (recovered by
    /// back-substitution).
    pub remove_singletons: bool,
    /// Remove surplus rows until `rows − columns` is at most this.
    /// `usize::MAX` keeps every row.
    pub target_excess: usize,
    /// Merge away columns of weight at most this by structured Gaussian
    /// elimination (`1` restricts the stage to singletons, `0` disables
    /// it).
    pub merge_max_weight: usize,
    /// A merge is skipped when it would leave a row heavier than this.
    pub max_row_weight: usize,
}

impl Default for FilterOptions {
    fn default() -> Self {
        Self {
            remove_duplicates: true,
            remove_singletons: true,
            target_excess: 32,
            merge_max_weight: 8,
            max_row_weight: 32,
        }
    }
}

/// What filtering did to the system.
#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct FilterReport {
    pub rows_in: usize,
    pub columns_in: usize,
    pub nonzeros_in: usize,
    pub duplicates_removed: usize,
    pub singletons_removed: usize,
    pub excess_rows_removed: usize,
    pub merged_columns: usize,
    /// Rows that became `0 ≡ 0` during merging (linear combinations of
    /// others) and were dropped.
    pub dependent_rows_dropped: usize,
    /// Columns left in no row (never determined by the core).
    pub uncovered_columns: usize,
    pub rows_out: usize,
    pub columns_out: usize,
    pub nonzeros_out: usize,
}

/// The reduced system plus everything needed to undo the reduction.
#[derive(Clone, Debug)]
pub struct FilteredSystem {
    modulus: u64,
    columns: usize,
    /// Rows of the core, over the original column numbering.
    pub core_rows: Vec<SparseRow>,
    /// Original ids of the columns that remain in the core, ascending.
    pub core_columns: Vec<u32>,
    /// `(pivot row, pivot column)` in elimination order.
    eliminated: Vec<(SparseRow, u32)>,
    pub report: FilterReport,
}

/// The filter found a contradiction, which only a wrong relation can
/// produce.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Inconsistent;

struct Workspace {
    modulus: u64,
    rows: Vec<Option<SparseRow>>,
    /// Active rows containing each column (unordered).
    col_rows: Vec<Vec<usize>>,
    col_eliminated: Vec<bool>,
    active_rows: usize,
    eliminated: Vec<(SparseRow, u32)>,
    report: FilterReport,
}

impl Workspace {
    fn column_weight(&self, c: u32) -> usize {
        self.col_rows[c as usize].len()
    }

    fn active_columns(&self) -> usize {
        (0..self.col_rows.len())
            .filter(|&c| !self.col_eliminated[c] && !self.col_rows[c].is_empty())
            .count()
    }

    fn detach(&mut self, row_id: usize) -> Option<SparseRow> {
        let row = self.rows[row_id].take()?;
        for &(c, _) in &row.entries {
            let list = &mut self.col_rows[c as usize];
            if let Some(pos) = list.iter().position(|&r| r == row_id) {
                list.swap_remove(pos);
            }
        }
        self.active_rows -= 1;
        Some(row)
    }

    fn attach(&mut self, row_id: usize, row: SparseRow) {
        for &(c, _) in &row.entries {
            self.col_rows[c as usize].push(row_id);
        }
        self.rows[row_id] = Some(row);
        self.active_rows += 1;
    }

    /// Eliminate column `c` (weight ≥ 1) with its lightest row as pivot.
    /// Returns the columns whose weight changed, or `Err` on a
    /// contradiction.
    fn eliminate(
        &mut self,
        c: u32,
        max_row_weight: usize,
    ) -> Result<Option<Vec<u32>>, Inconsistent> {
        let m = self.modulus;
        let members = self.col_rows[c as usize].clone();
        if members.is_empty() {
            return Ok(None);
        }
        let pivot_id = members
            .iter()
            .copied()
            .min_by_key(|&r| {
                (
                    self.rows[r].as_ref().map_or(usize::MAX, SparseRow::weight),
                    r,
                )
            })
            .expect("nonempty");
        let pivot_weight = self.rows[pivot_id].as_ref().expect("active").weight();
        // Fill-in bound: every other row grows by at most pivot_weight − 2.
        for &r in &members {
            if r == pivot_id {
                continue;
            }
            let w = self.rows[r].as_ref().expect("active").weight();
            if w + pivot_weight - 2 > max_row_weight {
                return Ok(None);
            }
        }
        let pivot = self.detach(pivot_id).expect("active");
        let pc = pivot.coefficient(c).expect("member");
        let inv = invmod(pc, m).ok_or(Inconsistent)?;
        let mut touched: Vec<u32> = pivot.entries.iter().map(|&(c, _)| c).collect();
        for &r in &members {
            if r == pivot_id {
                continue;
            }
            let row = self.detach(r).expect("active");
            let factor = mulmod(row.coefficient(c).expect("member"), inv, m);
            let reduced = row.axpy(factor, &pivot, m);
            debug_assert!(reduced.coefficient(c).is_none());
            if reduced.entries.is_empty() {
                if reduced.rhs != 0 {
                    return Err(Inconsistent);
                }
                self.report.dependent_rows_dropped += 1;
                continue;
            }
            touched.extend(reduced.entries.iter().map(|&(c, _)| c));
            self.attach(r, reduced);
        }
        self.col_eliminated[c as usize] = true;
        self.eliminated.push((pivot, c));
        touched.sort_unstable();
        touched.dedup();
        touched.retain(|&t| t != c);
        Ok(Some(touched))
    }

    /// Eliminate every singleton column, cascading.
    fn cascade_singletons(&mut self, seeds: Vec<u32>) -> Result<(), Inconsistent> {
        let mut stack = seeds;
        while let Some(c) = stack.pop() {
            if self.col_eliminated[c as usize] || self.column_weight(c) != 1 {
                continue;
            }
            if let Some(touched) = self.eliminate(c, usize::MAX)? {
                self.report.singletons_removed += 1;
                stack.extend(touched.into_iter().filter(|&t| self.column_weight(t) == 1));
            }
        }
        Ok(())
    }

    fn remove_row(&mut self, row_id: usize) -> Result<(), Inconsistent> {
        let row = self.detach(row_id).expect("active");
        self.report.excess_rows_removed += 1;
        let seeds = row.entries.iter().map(|&(c, _)| c).collect();
        self.cascade_singletons(seeds)
    }
}

fn find_root(parent: &mut [usize], mut x: usize) -> usize {
    while parent[x] != x {
        parent[x] = parent[parent[x]];
        x = parent[x];
    }
    x
}

/// Reduce a relation system before the sparse solve.  `columns` is the
/// number of unknowns; every row's columns must be below it.
pub fn filter_relations(
    rows: Vec<SparseRow>,
    columns: usize,
    modulus: u64,
    opts: &FilterOptions,
) -> Result<FilteredSystem, Inconsistent> {
    let mut report = FilterReport {
        rows_in: rows.len(),
        columns_in: columns,
        nonzeros_in: rows.iter().map(SparseRow::weight).sum(),
        ..FilterReport::default()
    };
    // Duplicates and trivial rows.
    let mut kept: Vec<SparseRow> = Vec::with_capacity(rows.len());
    let mut seen: HashSet<SparseRow> = HashSet::new();
    for row in rows {
        if row.entries.is_empty() {
            if row.rhs != 0 {
                return Err(Inconsistent);
            }
            report.dependent_rows_dropped += 1;
            continue;
        }
        if opts.remove_duplicates {
            if seen.contains(&row) {
                report.duplicates_removed += 1;
                continue;
            }
            seen.insert(row.clone());
        }
        kept.push(row);
    }
    drop(seen);

    let mut ws = Workspace {
        modulus,
        rows: Vec::with_capacity(kept.len()),
        col_rows: vec![Vec::new(); columns],
        col_eliminated: vec![false; columns],
        active_rows: 0,
        eliminated: Vec::new(),
        report,
    };
    for (id, row) in kept.into_iter().enumerate() {
        ws.rows.push(None);
        ws.attach(id, row);
    }

    // Singletons.
    if opts.remove_singletons {
        let seeds: Vec<u32> = (0..columns as u32)
            .filter(|&c| ws.column_weight(c) == 1)
            .collect();
        ws.cascade_singletons(seeds)?;
    }

    // Excess: remove rows, preferring those whose removal cascades
    // through the largest connected component of weight-2 columns
    // (the clique rule), heaviest row first.
    if opts.target_excess != usize::MAX && opts.remove_singletons {
        loop {
            let active_cols = ws.active_columns();
            if ws.active_rows <= active_cols.saturating_add(opts.target_excess) {
                break;
            }
            let to_remove = ws.active_rows - active_cols - opts.target_excess;
            let n = ws.rows.len();
            let mut parent: Vec<usize> = (0..n).collect();
            for c in 0..columns {
                if ws.col_eliminated[c] || ws.col_rows[c].len() != 2 {
                    continue;
                }
                let (a, b) = (ws.col_rows[c][0], ws.col_rows[c][1]);
                let (ra, rb) = (find_root(&mut parent, a), find_root(&mut parent, b));
                if ra != rb {
                    parent[ra] = rb;
                }
            }
            let mut size: HashMap<usize, usize> = HashMap::new();
            let mut heaviest: HashMap<usize, (usize, usize)> = HashMap::new();
            for id in 0..n {
                let Some(row) = ws.rows[id].as_ref() else {
                    continue;
                };
                let root = find_root(&mut parent, id);
                *size.entry(root).or_insert(0) += 1;
                let entry = heaviest.entry(root).or_insert((0, id));
                if row.weight() > entry.0 {
                    *entry = (row.weight(), id);
                }
            }
            let mut components: Vec<(usize, usize, usize)> = size
                .iter()
                .map(|(&root, &s)| (s, heaviest[&root].0, heaviest[&root].1))
                .collect();
            components.sort_unstable_by(|a, b| b.cmp(a));
            let mut removed = 0;
            for &(_, _, row_id) in components.iter().take(to_remove) {
                if ws.rows[row_id].is_some() {
                    ws.remove_row(row_id)?;
                    removed += 1;
                }
            }
            if removed == 0 {
                break;
            }
        }
    }

    // Merge light columns, lightest first, under the fill-in bound.
    if opts.merge_max_weight >= 2 {
        let mut heap: BinaryHeap<Reverse<(usize, u32)>> = BinaryHeap::new();
        for c in 0..columns {
            let w = ws.col_rows[c].len();
            if !ws.col_eliminated[c] && (1..=opts.merge_max_weight).contains(&w) {
                heap.push(Reverse((w, c as u32)));
            }
        }
        while let Some(Reverse((w, c))) = heap.pop() {
            if ws.col_eliminated[c as usize] || ws.column_weight(c) != w {
                continue; // stale entry
            }
            let Some(touched) = ws.eliminate(c, opts.max_row_weight)? else {
                continue; // fill-in bound; retried if its weight changes
            };
            if w == 1 {
                ws.report.singletons_removed += 1;
            } else {
                ws.report.merged_columns += 1;
            }
            for t in touched {
                let tw = ws.column_weight(t);
                if !ws.col_eliminated[t as usize] && (1..=opts.merge_max_weight).contains(&tw) {
                    heap.push(Reverse((tw, t)));
                }
            }
        }
    }

    let core_rows: Vec<SparseRow> = ws.rows.iter().flatten().cloned().collect();
    let core_columns: Vec<u32> = (0..columns as u32)
        .filter(|&c| !ws.col_eliminated[c as usize] && !ws.col_rows[c as usize].is_empty())
        .collect();
    let mut report = ws.report;
    report.uncovered_columns = (0..columns)
        .filter(|&c| !ws.col_eliminated[c] && ws.col_rows[c].is_empty())
        .count();
    report.rows_out = core_rows.len();
    report.columns_out = core_columns.len();
    report.nonzeros_out = core_rows.iter().map(SparseRow::weight).sum();
    Ok(FilteredSystem {
        modulus,
        columns,
        core_rows,
        core_columns,
        eliminated: ws.eliminated,
        report,
    })
}

impl FilteredSystem {
    /// Number of unknowns of the original system.
    pub fn columns(&self) -> usize {
        self.columns
    }

    /// Recover the full solution from the core one (indexed like
    /// [`Self::core_columns`]) by back-substituting the elimination
    /// stack, then propagating through `original_rows` while some row
    /// has exactly one unknown, then solving whatever remains densely.
    /// `None` when the original system does not determine every column
    /// (the caller collects more relations).
    pub fn reconstruct(
        &self,
        core_solution: &[u64],
        original_rows: &[SparseRow],
    ) -> Option<Vec<u64>> {
        let m = self.modulus;
        assert_eq!(
            core_solution.len(),
            self.core_columns.len(),
            "core solution width"
        );
        let mut value: Vec<Option<u64>> = vec![None; self.columns];
        for (&c, &v) in self.core_columns.iter().zip(core_solution) {
            value[c as usize] = Some(v);
        }
        let solve_row = |row: &SparseRow, col: u32, value: &[Option<u64>]| -> Option<u64> {
            let mut acc = row.rhs;
            let mut pivot = None;
            for &(c, v) in &row.entries {
                if c == col {
                    pivot = Some(v);
                } else {
                    acc = submod(acc, mulmod(v, value[c as usize]?, m), m);
                }
            }
            Some(mulmod(acc, invmod(pivot?, m)?, m))
        };
        // Stack in reverse: a pivot row's other columns are core columns
        // or were eliminated later.
        let mut deferred = Vec::new();
        for (row, col) in self.eliminated.iter().rev() {
            match solve_row(row, *col, &value) {
                Some(v) => value[*col as usize] = Some(v),
                None => deferred.push((row, *col)),
            }
        }
        // Propagation over the original rows (and deferred pivots) while
        // some row has exactly one unknown.
        let mut progress = true;
        while progress && value.iter().any(Option::is_none) {
            progress = false;
            for (row, col) in &deferred {
                if value[*col as usize].is_none() {
                    if let Some(v) = solve_row(row, *col, &value) {
                        value[*col as usize] = Some(v);
                        progress = true;
                    }
                }
            }
            for row in original_rows {
                let mut unknown = None;
                let mut count = 0;
                for &(c, _) in &row.entries {
                    if value[c as usize].is_none() {
                        unknown = Some(c);
                        count += 1;
                        if count > 1 {
                            break;
                        }
                    }
                }
                if count == 1 {
                    let c = unknown.expect("one unknown");
                    if let Some(v) = solve_row(row, c, &value) {
                        value[c as usize] = Some(v);
                        progress = true;
                    }
                }
            }
        }
        // Residual dense solve over the columns still unknown.
        let unknown: Vec<u32> = (0..self.columns as u32)
            .filter(|&c| value[c as usize].is_none())
            .collect();
        if !unknown.is_empty() {
            let index: HashMap<u32, usize> =
                unknown.iter().enumerate().map(|(i, &c)| (c, i)).collect();
            let mut rows = Vec::new();
            let mut rhs = Vec::new();
            for row in original_rows {
                if !row.entries.iter().any(|&(c, _)| index.contains_key(&c)) {
                    continue;
                }
                let mut dense = vec![0u64; unknown.len()];
                let mut b = row.rhs;
                for &(c, v) in &row.entries {
                    match index.get(&c) {
                        Some(&i) => dense[i] = v,
                        None => b = submod(b, mulmod(v, value[c as usize].expect("known"), m), m),
                    }
                }
                rows.push(dense);
                rhs.push(b);
            }
            let solved = dense_solve_unique(rows, rhs, m)?;
            for (&c, v) in unknown.iter().zip(solved) {
                value[c as usize] = Some(v);
            }
        }
        value.into_iter().collect()
    }
}

/// Gauss–Jordan over `Z/rZ` in `u64`; `Some` only for a unique solution.
pub fn dense_solve_unique(
    mut rows: Vec<Vec<u64>>,
    mut rhs: Vec<u64>,
    modulus: u64,
) -> Option<Vec<u64>> {
    let cols = rows.first().map_or(0, Vec::len);
    if cols == 0 {
        return rhs.iter().all(|&b| b == 0).then_some(Vec::new());
    }
    let mut pivot_row = 0;
    let mut pivots = Vec::with_capacity(cols);
    for col in 0..cols {
        let Some(p) = (pivot_row..rows.len()).find(|&r| rows[r][col] != 0) else {
            return None; // free column: not unique
        };
        rows.swap(pivot_row, p);
        rhs.swap(pivot_row, p);
        let inv = invmod(rows[pivot_row][col], modulus)?;
        for v in rows[pivot_row].iter_mut() {
            *v = mulmod(*v, inv, modulus);
        }
        rhs[pivot_row] = mulmod(rhs[pivot_row], inv, modulus);
        let pivot = rows[pivot_row].clone();
        let pb = rhs[pivot_row];
        for r in 0..rows.len() {
            if r == pivot_row || rows[r][col] == 0 {
                continue;
            }
            let f = rows[r][col];
            for k in col..cols {
                if pivot[k] != 0 {
                    rows[r][k] = submod(rows[r][k], mulmod(f, pivot[k], modulus), modulus);
                }
            }
            rhs[r] = submod(rhs[r], mulmod(f, pb, modulus), modulus);
        }
        pivots.push(pivot_row);
        pivot_row += 1;
    }
    // Remaining rows must read 0 ≡ 0.
    if (pivot_row..rows.len()).any(|r| rhs[r] != 0) {
        return None;
    }
    Some(pivots.iter().map(|&r| rhs[r]).collect())
}

// ── Sparse matrices and block operators ────────────────────────────

/// Compressed-sparse-row matrix over `Z/rZ`.
#[derive(Clone, Debug)]
pub struct CsrMatrix {
    pub n_rows: usize,
    pub n_cols: usize,
    row_ptr: Vec<usize>,
    col_idx: Vec<u32>,
    vals: Vec<u64>,
    modulus: u64,
}

/// Rows below this many are multiplied serially.
const PARALLEL_ROWS: usize = 2048;

impl CsrMatrix {
    /// From rows over columns `0..n_cols` (right-hand sides ignored).
    pub fn from_rows(rows: &[SparseRow], n_cols: usize, modulus: u64) -> Self {
        let mut row_ptr = Vec::with_capacity(rows.len() + 1);
        let mut col_idx = Vec::new();
        let mut vals = Vec::new();
        row_ptr.push(0);
        for row in rows {
            for &(c, v) in &row.entries {
                debug_assert!((c as usize) < n_cols);
                col_idx.push(c);
                vals.push(v);
            }
            row_ptr.push(col_idx.len());
        }
        Self {
            n_rows: rows.len(),
            n_cols,
            row_ptr,
            col_idx,
            vals,
            modulus,
        }
    }

    /// Number of stored entries.
    pub fn nnz(&self) -> usize {
        self.vals.len()
    }

    #[inline]
    fn row_into(&self, i: usize, x: &[u64], n: usize, out: &mut [u64]) {
        let m = self.modulus;
        out.iter_mut().for_each(|v| *v = 0);
        for k in self.row_ptr[i]..self.row_ptr[i + 1] {
            let c = self.col_idx[k] as usize;
            let a = self.vals[k];
            let src = &x[c * n..(c + 1) * n];
            for (o, &s) in out.iter_mut().zip(src) {
                *o = addmod(*o, mulmod(a, s, m), m);
            }
        }
    }

    /// `y = A · x` for `n` column vectors stored row-major
    /// (`x[c * n + j]`), in parallel over rows.
    pub fn mul_block(&self, x: &[u64], n: usize, y: &mut [u64]) {
        debug_assert_eq!(x.len(), self.n_cols * n);
        debug_assert_eq!(y.len(), self.n_rows * n);
        if self.n_rows >= PARALLEL_ROWS {
            y.par_chunks_mut(n)
                .enumerate()
                .for_each(|(i, out)| self.row_into(i, x, n, out));
        } else {
            for (i, out) in y.chunks_mut(n).enumerate() {
                self.row_into(i, x, n, out);
            }
        }
    }
}

/// A square linear operator on block vectors, as block Wiedemann sees it.
pub trait BlockOperator: Sync {
    /// Dimension `N` of the square operator.
    fn dim(&self) -> usize;
    /// `y = M · x` on `n` column vectors stored row-major.
    fn apply(&self, x: &[u64], n: usize, y: &mut [u64]);
    /// The modulus.
    fn modulus(&self) -> u64;
}

impl BlockOperator for CsrMatrix {
    fn dim(&self) -> usize {
        assert_eq!(self.n_rows, self.n_cols, "square operator");
        self.n_rows
    }
    fn apply(&self, x: &[u64], n: usize, y: &mut [u64]) {
        self.mul_block(x, n, y)
    }
    fn modulus(&self) -> u64 {
        self.modulus
    }
}

/// `M = [[A, −b], [0, 0]]` of dimension `N + 1`: a kernel vector `(x, t)`
/// with `t ≠ 0` gives `A (x / t) = b`.  Never materialised.
pub struct Homogenised<'a> {
    pub a: &'a CsrMatrix,
    pub b: &'a [u64],
}

impl BlockOperator for Homogenised<'_> {
    fn dim(&self) -> usize {
        self.a.dim() + 1
    }
    fn apply(&self, x: &[u64], n: usize, y: &mut [u64]) {
        let big_n = self.a.dim();
        let m = self.a.modulus;
        let (ya, yt) = y.split_at_mut(big_n * n);
        self.a.mul_block(&x[..big_n * n], n, ya);
        let t = &x[big_n * n..];
        for (i, out) in ya.chunks_mut(n).enumerate() {
            let bi = self.b[i];
            if bi == 0 {
                continue;
            }
            for (o, &tj) in out.iter_mut().zip(t) {
                *o = submod(*o, mulmod(bi, tj, m), m);
            }
        }
        yt.iter_mut().for_each(|v| *v = 0);
    }
    fn modulus(&self) -> u64 {
        self.a.modulus
    }
}

// ── Block Wiedemann ────────────────────────────────────────────────

/// Block sizes and safety margin for [`block_wiedemann_kernel`].
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct BlockWiedemannOptions {
    /// Rows of the left projection `X` (`m`).
    pub block_m: usize,
    /// Columns of the right block `Y` (`n`).
    pub block_n: usize,
    /// Sequence terms beyond `⌈N/m⌉ + ⌈N/n⌉`.
    pub margin: usize,
}

impl Default for BlockWiedemannOptions {
    fn default() -> Self {
        Self {
            block_m: 4,
            block_n: 4,
            margin: 8,
        }
    }
}

/// What one block Wiedemann run did.
#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct BlockWiedemannReport {
    pub dimension: usize,
    pub block_m: usize,
    pub block_n: usize,
    /// Krylov terms computed (`X Mⁱ Y`, `i < sequence_length`).
    pub sequence_length: usize,
    /// Nominal degree of the generator column that produced the kernel
    /// vector.
    pub generator_degree: usize,
    /// Extra applications of `M` needed after evaluating that column.
    pub extra_steps: usize,
    /// Matrix–block products performed in total.
    pub products: usize,
}

/// One column of the approximant basis: `f` (coefficients over the `n`
/// right vectors), the residual `[a | I] · [f; g] mod λ^L` (column-major
/// `m`-vectors per order), and the shifted degree bound `δ`.
struct BasisColumn {
    f: Vec<Vec<u64>>,
    residual: Vec<u64>,
    delta: usize,
}

/// Shifted minimal approximant basis of order `L` for `[a(λ) | I_m]`
/// with shift `(0ⁿ, 1ᵐ)`: every column `[f; g]` satisfies
/// `a·f + g ≡ 0 (mod λ^L)` with `deg f ≤ δ`, `deg g ≤ δ − 1`, hence the
/// block recurrence `Σ_{k≤δ} S_{s−k} f_k = 0` for `δ ≤ s < L`.
fn minimal_approximant_basis(
    seq: &[Vec<u64>],
    m: usize,
    n: usize,
    modulus: u64,
) -> Vec<BasisColumn> {
    let big_l = seq.len();
    let mut cols: Vec<BasisColumn> = Vec::with_capacity(n + m);
    for j in 0..n {
        let mut e = vec![0u64; n];
        e[j] = 1;
        let mut residual = vec![0u64; big_l * m];
        for (t, s) in seq.iter().enumerate() {
            for i in 0..m {
                residual[t * m + i] = s[i * n + j];
            }
        }
        cols.push(BasisColumn {
            f: vec![e],
            residual,
            delta: 0,
        });
    }
    for i in 0..m {
        let mut residual = vec![0u64; big_l * m];
        residual[i] = 1;
        cols.push(BasisColumn {
            f: vec![vec![0u64; n]],
            residual,
            delta: 1,
        });
    }
    let mut order: Vec<usize> = (0..n + m).collect();
    let mut pivots: Vec<(usize, usize)> = Vec::with_capacity(m);
    for t in 0..big_l {
        order.sort_by_key(|&j| (cols[j].delta, j));
        pivots.clear();
        for &j in &order {
            for &(p, row) in &pivots {
                let c = cols[j].residual[t * m + row];
                if c == 0 {
                    continue;
                }
                // column j -= c · column p  (δ_p ≤ δ_j by the ordering)
                let (pj, pp) = if j < p {
                    let (lo, hi) = cols.split_at_mut(p);
                    (&mut lo[j], &hi[0])
                } else {
                    let (lo, hi) = cols.split_at_mut(j);
                    (&mut hi[0], &lo[p])
                };
                let width = pp.f.len();
                if pj.f.len() < width {
                    pj.f.resize(width, vec![0u64; n]);
                }
                for (fj, fp) in pj.f.iter_mut().zip(&pp.f) {
                    for (a, &b) in fj.iter_mut().zip(fp) {
                        if b != 0 {
                            *a = submod(*a, mulmod(c, b, modulus), modulus);
                        }
                    }
                }
                for k in t * m..big_l * m {
                    let b = pp.residual[k];
                    if b != 0 {
                        pj.residual[k] = submod(pj.residual[k], mulmod(c, b, modulus), modulus);
                    }
                }
            }
            if let Some(row) = (0..m).find(|&i| cols[j].residual[t * m + i] != 0) {
                // Normalise the pivot so later reductions are one product.
                let inv = invmod(cols[j].residual[t * m + row], modulus).expect("prime modulus");
                if inv != 1 {
                    let col = &mut cols[j];
                    for fk in col.f.iter_mut() {
                        for a in fk.iter_mut() {
                            *a = mulmod(*a, inv, modulus);
                        }
                    }
                    for k in t * m..big_l * m {
                        col.residual[k] = mulmod(col.residual[k], inv, modulus);
                    }
                }
                pivots.push((j, row));
            }
        }
        for &(p, _) in &pivots {
            let col = &mut cols[p];
            col.f.insert(0, vec![0u64; n]);
            col.residual
                .copy_within(t * m..(big_l - 1) * m, (t + 1) * m);
            col.residual[t * m..(t + 1) * m]
                .iter_mut()
                .for_each(|v| *v = 0);
            col.delta += 1;
        }
    }
    cols
}

/// A nonzero kernel vector of a singular square operator by block
/// Wiedemann, or `None` if none of the generator columns produced one
/// (retry with another seed, or the operator is nonsingular).
pub fn block_wiedemann_kernel(
    op: &impl BlockOperator,
    opts: &BlockWiedemannOptions,
    seed: u64,
) -> Option<(Vec<u64>, BlockWiedemannReport)> {
    let big_n = op.dim();
    let modulus = op.modulus();
    let m = opts.block_m.max(1);
    let n = opts.block_n.max(1);
    if big_n == 0 {
        return None;
    }
    let big_l = big_n.div_ceil(m) + big_n.div_ceil(n) + opts.margin.max(2);
    let mut rng = StdRng::seed_from_u64(seed ^ 0x424c_4f43_4b57_4945);
    let x: Vec<u64> = (0..m * big_n).map(|_| rng.gen_range(0..modulus)).collect();
    // Y = M Z for random Z (Coppersmith): a generator of the Y-sequence
    // evaluated on Z lands in the kernel of M instead of vanishing.
    let z: Vec<u64> = (0..big_n * n).map(|_| rng.gen_range(0..modulus)).collect();
    let mut y = vec![0u64; big_n * n];
    op.apply(&z, n, &mut y);
    let mut report = BlockWiedemannReport {
        dimension: big_n,
        block_m: m,
        block_n: n,
        sequence_length: big_l,
        products: 1,
        ..BlockWiedemannReport::default()
    };

    // Krylov sequence S_t = X Mᵗ Y = X Mᵗ⁺¹ Z.
    let mut seq: Vec<Vec<u64>> = Vec::with_capacity(big_l);
    let mut v = y.clone();
    let mut w = vec![0u64; big_n * n];
    for t in 0..big_l {
        let mut s = vec![0u64; m * n];
        for i in 0..m {
            let xi = &x[i * big_n..(i + 1) * big_n];
            let row: Vec<u64> = (0..n)
                .map(|j| {
                    let mut acc = 0u128;
                    for (r, &xr) in xi.iter().enumerate() {
                        acc += xr as u128 * v[r * n + j] as u128;
                        if acc >> 126 != 0 {
                            acc %= modulus as u128;
                        }
                    }
                    (acc % modulus as u128) as u64
                })
                .collect();
            s[i * n..(i + 1) * n].copy_from_slice(&row);
        }
        seq.push(s);
        if t + 1 < big_l {
            op.apply(&v, n, &mut w);
            report.products += 1;
            std::mem::swap(&mut v, &mut w);
        }
    }

    let basis = minimal_approximant_basis(&seq, m, n, modulus);
    let mut order: Vec<usize> = (0..basis.len()).collect();
    order.sort_by_key(|&j| basis[j].delta);
    drop(y);
    let mut buf = vec![0u64; big_n];
    let z_times = |f: &[u64], out: &mut [u64]| {
        for (r, o) in out.iter_mut().enumerate() {
            let mut acc = 0u64;
            for (j, &fj) in f.iter().enumerate() {
                if fj != 0 {
                    acc = addmod(acc, mulmod(z[r * n + j], fj, modulus), modulus);
                }
            }
            *o = acc;
        }
    };
    for &j in &order {
        let col = &basis[j];
        let Some(e) = col.f.iter().rposition(|fk| fk.iter().any(|&a| a != 0)) else {
            continue;
        };
        // Horner from the top power: u = Σ_{k≤e} M^{e−k} Z f_k, so f_0
        // multiplies Mᵉ and f_e multiplies the identity.  The recurrence
        // gives M^{δ−e+1} u = 0, so some Mⁱu below that is in the kernel.
        let mut u = vec![0u64; big_n];
        z_times(&col.f[0], &mut u);
        for fk in &col.f[1..=e] {
            op.apply(&u, 1, &mut buf);
            report.products += 1;
            z_times(fk, &mut u);
            for (a, &b) in u.iter_mut().zip(&buf) {
                *a = addmod(*a, b, modulus);
            }
        }
        if u.iter().all(|&a| a == 0) {
            continue;
        }
        // Push through M until it dies; the last nonzero image is in
        // the kernel.
        let limit = col.delta.saturating_sub(e) + 4;
        for step in 0..=limit {
            op.apply(&u, 1, &mut buf);
            report.products += 1;
            if buf.iter().all(|&a| a == 0) {
                report.generator_degree = col.delta;
                report.extra_steps = step;
                return Some((u, report));
            }
            std::mem::swap(&mut u, &mut buf);
        }
    }
    None
}

// ── The sparse solve: filter → fold → block Wiedemann → reconstruct ──

/// Controls for [`solve_sparse_system`].
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct SparseSolveOptions {
    pub filter: FilterOptions,
    pub wiedemann: BlockWiedemannOptions,
    /// Base rows each excess row is folded into.
    pub fold: usize,
    /// Independent `(fold, X, Y)` draws before giving up.
    pub attempts: usize,
    pub seed: u64,
}

impl Default for SparseSolveOptions {
    fn default() -> Self {
        Self {
            filter: FilterOptions::default(),
            wiedemann: BlockWiedemannOptions::default(),
            fold: 3,
            attempts: 3,
            seed: 0x5350_4152_5345_4c41,
        }
    }
}

/// What [`solve_sparse_system`] did.
#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct SparseSolveReport {
    pub filter: FilterReport,
    /// Rows and columns of the square system handed to Wiedemann.
    pub core_dimension: usize,
    pub core_nonzeros: usize,
    pub wiedemann: Option<BlockWiedemannReport>,
    /// Draws of `(fold, X, Y)` used.
    pub attempts: usize,
    /// Columns recovered by back-substitution, propagation and the
    /// residual dense solve after the core.
    pub reconstructed_columns: usize,
}

/// Outcome of [`solve_sparse_system`].
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum SparseSolveOutcome {
    /// The unique solution over every column, verified against every row.
    Solved(Vec<u64>),
    /// The rows do not (yet) determine every column, or the solve did
    /// not converge within the attempts.
    Undetermined,
    /// A contradiction: some relation is wrong.
    Inconsistent,
}

/// Fold rows `C..R` of a full-column-rank system into rows `< C` at
/// random with random coefficients, giving a square system with the same
/// solution.
fn fold_square(
    rows: &[SparseRow],
    n_cols: usize,
    modulus: u64,
    fold: usize,
    rng: &mut StdRng,
) -> Vec<SparseRow> {
    let mut square: Vec<SparseRow> = rows[..n_cols].to_vec();
    for extra in &rows[n_cols..] {
        for _ in 0..fold.max(1) {
            let i = rng.gen_range(0..n_cols);
            let c = rng.gen_range(1..modulus);
            square[i] = square[i].axpy(negmod(c, modulus), extra, modulus);
        }
    }
    square
}

/// Solve `Σ c_{i,o} x_o ≡ rhs_i (mod r)` for every `x_o` by filtering,
/// block Wiedemann on the reduced core, and exact reconstruction.
/// `columns` is the number of unknowns.  The solution is verified against
/// every input row before it is returned.
pub fn solve_sparse_system(
    rows: &[SparseRow],
    columns: usize,
    modulus: u64,
    opts: &SparseSolveOptions,
) -> (SparseSolveOutcome, SparseSolveReport) {
    let mut report = SparseSolveReport::default();
    // Cheap necessary condition: every column occurs somewhere.
    let mut covered = vec![false; columns];
    for row in rows {
        for &(c, _) in &row.entries {
            covered[c as usize] = true;
        }
    }
    if covered.iter().any(|&c| !c) || rows.len() < columns {
        report.filter.rows_in = rows.len();
        report.filter.columns_in = columns;
        report.filter.uncovered_columns = covered.iter().filter(|&&c| !c).count();
        return (SparseSolveOutcome::Undetermined, report);
    }
    let filtered = match filter_relations(rows.to_vec(), columns, modulus, &opts.filter) {
        Ok(f) => f,
        Err(Inconsistent) => return (SparseSolveOutcome::Inconsistent, report),
    };
    report.filter = filtered.report.clone();
    let core_cols = filtered.core_columns.len();
    if filtered.core_rows.len() < core_cols {
        return (SparseSolveOutcome::Undetermined, report);
    }
    report.core_dimension = core_cols;

    // Solve the core.
    let mut core_solution: Option<Vec<u64>> = None;
    if core_cols == 0 {
        core_solution = Some(Vec::new());
    } else {
        // Renumber core columns densely.
        let index: HashMap<u32, u32> = filtered
            .core_columns
            .iter()
            .enumerate()
            .map(|(i, &c)| (c, i as u32))
            .collect();
        let core: Vec<SparseRow> = filtered
            .core_rows
            .iter()
            .map(|row| SparseRow {
                entries: row.entries.iter().map(|&(c, v)| (index[&c], v)).collect(),
                rhs: row.rhs,
            })
            .collect();
        report.core_nonzeros = core.iter().map(SparseRow::weight).sum();
        let mut rng = StdRng::seed_from_u64(opts.seed ^ 0x464f_4c44_5351_5552);
        for attempt in 0..opts.attempts.max(1) {
            report.attempts = attempt + 1;
            let square = fold_square(&core, core_cols, modulus, opts.fold, &mut rng);
            let a = CsrMatrix::from_rows(&square, core_cols, modulus);
            let b: Vec<u64> = square.iter().map(|r| r.rhs).collect();
            let op = Homogenised { a: &a, b: &b };
            let Some((z, wr)) = block_wiedemann_kernel(&op, &opts.wiedemann, rng.gen()) else {
                continue;
            };
            report.wiedemann = Some(wr);
            let t = z[core_cols];
            let Some(inv) = (t != 0).then(|| invmod(t, modulus)).flatten() else {
                continue;
            };
            let x: Vec<u64> = z[..core_cols]
                .iter()
                .map(|&v| mulmod(v, inv, modulus))
                .collect();
            if core.iter().all(|row| row.evaluate(&x, modulus) == row.rhs) {
                core_solution = Some(x);
                break;
            }
        }
    }
    let Some(core_solution) = core_solution else {
        return (SparseSolveOutcome::Undetermined, report);
    };
    let Some(full) = filtered.reconstruct(&core_solution, rows) else {
        return (SparseSolveOutcome::Undetermined, report);
    };
    report.reconstructed_columns = columns - core_cols;
    if rows
        .iter()
        .all(|row| row.evaluate(&full, modulus) == row.rhs)
    {
        (SparseSolveOutcome::Solved(full), report)
    } else {
        (SparseSolveOutcome::Inconsistent, report)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::ec_index_calculus::gaussian_eliminate_mod_n;

    const P: u64 = 1_439_393; // r for K_1 / 2^31
    const Q: u64 = (1u64 << 61) - 1; // Mersenne prime, near the width limit

    /// Rank of the coefficient matrix by plain forward elimination in
    /// `u128`, independent of the solver under test.
    fn reference_rank(rows: &[SparseRow], columns: usize, modulus: u64) -> usize {
        let p = modulus as u128;
        let mut m: Vec<Vec<u128>> = rows
            .iter()
            .map(|r| {
                let mut d = vec![0u128; columns];
                for &(c, v) in &r.entries {
                    d[c as usize] = v as u128;
                }
                d
            })
            .collect();
        let mut rank = 0;
        for col in 0..columns {
            let Some(piv) = (rank..m.len()).find(|&r| m[r][col] != 0) else {
                continue;
            };
            m.swap(rank, piv);
            let inv = invmod(m[rank][col] as u64, modulus).unwrap() as u128;
            for r in rank + 1..m.len() {
                if m[r][col] == 0 {
                    continue;
                }
                let f = m[r][col] * inv % p;
                for k in col..columns {
                    m[r][k] = (m[r][k] + p - f * m[rank][k] % p) % p;
                }
            }
            rank += 1;
        }
        rank
    }

    /// The unique solution by the big-integer reference solver, or
    /// `None` when the system is inconsistent or has free columns.
    fn dense_reference(rows: &[SparseRow], columns: usize, modulus: u64) -> Option<Vec<u64>> {
        if reference_rank(rows, columns, modulus) < columns {
            return None;
        }
        let mut m: Vec<Vec<BigUint>> = rows
            .iter()
            .map(|r| {
                let mut d = vec![BigUint::from(0u32); columns];
                for &(c, v) in &r.entries {
                    d[c as usize] = BigUint::from(v);
                }
                d
            })
            .collect();
        let mut b: Vec<BigUint> = rows.iter().map(|r| BigUint::from(r.rhs)).collect();
        let sol = gaussian_eliminate_mod_n(&mut m, &mut b, &BigUint::from(modulus))?;
        let sol: Vec<u64> = sol.iter().map(|v| to_u64_mod(v, modulus)).collect();
        // The reference returns a partial solution when the system is
        // underdetermined; only accept it when it satisfies every row.
        rows.iter()
            .all(|r| r.evaluate(&sol, modulus) == r.rhs)
            .then_some(sol)
    }

    /// Random relation-shaped system (row weight ≤ `weight`) with a
    /// planted solution.
    fn planted_system(
        rng: &mut StdRng,
        rows: usize,
        columns: usize,
        weight: usize,
        modulus: u64,
    ) -> (Vec<SparseRow>, Vec<u64>) {
        let x: Vec<u64> = (0..columns).map(|_| rng.gen_range(0..modulus)).collect();
        let mut out = Vec::with_capacity(rows);
        for _ in 0..rows {
            let w = rng.gen_range(1..=weight);
            let entries: Vec<(u32, u64)> = (0..w)
                .map(|_| (rng.gen_range(0..columns) as u32, rng.gen_range(1..modulus)))
                .collect();
            let mut row = SparseRow::new(entries, 0, modulus);
            row.rhs = row.evaluate(&x, modulus);
            out.push(row);
        }
        (out, x)
    }

    #[test]
    fn modular_helpers_agree_with_big_integers() {
        let mut rng = StdRng::seed_from_u64(1);
        for _ in 0..200 {
            let a = rng.gen_range(0..Q);
            let b = rng.gen_range(0..Q);
            let big = |v: u64| BigUint::from(v);
            assert_eq!(big(mulmod(a, b, Q)), (big(a) * big(b)) % big(Q));
            assert_eq!(big(addmod(a, b, Q)), (big(a) + big(b)) % big(Q));
            assert_eq!(submod(a, b, Q), addmod(a, negmod(b, Q), Q));
            if a != 0 {
                assert_eq!(mulmod(a, invmod(a, Q).unwrap(), Q), 1);
            }
        }
        assert_eq!(invmod(0, P), None);
        assert_eq!(invmod(6, 9), None);
    }

    #[test]
    fn sparse_row_construction_merges_and_reduces() {
        let row = SparseRow::new(vec![(3, P + 2), (1, 5), (3, P - 2), (0, P)], 2 * P + 7, P);
        assert_eq!(row.entries, vec![(1, 5)]);
        assert_eq!(row.rhs, 7);
        let dense = vec![
            BigUint::from(0u32),
            BigUint::from(P + 4),
            BigUint::from(3u32),
        ];
        let from_dense = SparseRow::from_dense(&dense, &BigUint::from(P), P);
        assert_eq!(from_dense.entries, vec![(1, 4), (2, 3)]);
        assert_eq!(from_dense.rhs, 0);
        let a = SparseRow::new(vec![(0, 2), (2, 5)], 9, P);
        let b = SparseRow::new(vec![(0, 1), (1, 7), (2, 5)], 4, P);
        let c = a.axpy(1, &b, P);
        assert_eq!(c.entries, vec![(0, 1), (1, P - 7)]);
        assert_eq!(c.rhs, 5);
    }

    #[test]
    fn dense_u64_solver_matches_the_big_integer_reference() {
        let mut rng = StdRng::seed_from_u64(2);
        for trial in 0..40 {
            let n = rng.gen_range(1..12);
            let extra = rng.gen_range(0..3);
            let (rows, x) = planted_system(&mut rng, n + extra, n, n.min(4), P);
            let dense: Vec<Vec<u64>> = rows
                .iter()
                .map(|r| {
                    let mut d = vec![0u64; n];
                    for &(c, v) in &r.entries {
                        d[c as usize] = v;
                    }
                    d
                })
                .collect();
            let rhs: Vec<u64> = rows.iter().map(|r| r.rhs).collect();
            let ours = dense_solve_unique(dense, rhs, P);
            let reference = dense_reference(&rows, n, P);
            assert_eq!(ours.is_some(), reference.is_some(), "trial {trial}");
            if let Some(sol) = ours {
                assert_eq!(sol, x, "trial {trial}");
            }
        }
    }

    #[test]
    fn filtering_preserves_the_solution_and_reconstructs_every_column() {
        let mut rng = StdRng::seed_from_u64(3);
        let mut merged_any = false;
        let mut purged_any = false;
        for trial in 0..60 {
            let columns = rng.gen_range(5..80);
            let rows_n = columns + rng.gen_range(0..columns);
            let weight = rng.gen_range(2..=4);
            let (rows, x) = planted_system(&mut rng, rows_n, columns, weight, P);
            let opts = FilterOptions {
                target_excess: rng.gen_range(0..8),
                merge_max_weight: rng.gen_range(0..10),
                max_row_weight: rng.gen_range(4..40),
                ..FilterOptions::default()
            };
            let filtered = filter_relations(rows.clone(), columns, P, &opts).expect("consistent");
            let rep = &filtered.report;
            merged_any |= rep.merged_columns > 0;
            purged_any |= rep.excess_rows_removed > 0;
            assert_eq!(rep.rows_in, rows_n);
            assert_eq!(rep.rows_out, filtered.core_rows.len());
            assert_eq!(rep.columns_out, filtered.core_columns.len());
            // The planted solution satisfies every core row (they are
            // combinations of the originals).
            for row in &filtered.core_rows {
                assert_eq!(
                    row.evaluate(&x, P),
                    row.rhs,
                    "trial {trial}: core row broken"
                );
                for &(c, _) in &row.entries {
                    assert!(filtered.core_columns.contains(&c));
                }
            }
            // Reconstruct from the planted core values: exact whenever the
            // original system determines every column.
            let core: Vec<u64> = filtered
                .core_columns
                .iter()
                .map(|&c| x[c as usize])
                .collect();
            let full = filtered.reconstruct(&core, &rows);
            let determined = dense_reference(&rows, columns, P).is_some();
            assert_eq!(full.is_some(), determined, "trial {trial}: determinacy");
            if let Some(full) = full {
                assert_eq!(full, x, "trial {trial}");
            }
        }
        assert!(
            merged_any && purged_any,
            "the random trials exercised merge and purge"
        );
    }

    #[test]
    fn filtering_detects_duplicates_singletons_and_contradictions() {
        let r = |e: Vec<(u32, u64)>, rhs| SparseRow::new(e, rhs, P);
        let rows = vec![
            r(vec![(0, 1), (1, 1)], 3),
            r(vec![(0, 1), (1, 1)], 3), // duplicate
            r(vec![(1, 2), (2, 1)], 4),
            r(vec![(2, 1), (3, 5)], 6), // column 3 is a singleton
            r(vec![(0, 1), (2, 1)], 2),
        ];
        let f = filter_relations(
            rows.clone(),
            4,
            P,
            &FilterOptions {
                merge_max_weight: 0,
                ..FilterOptions::default()
            },
        )
        .unwrap();
        assert_eq!(f.report.duplicates_removed, 1);
        assert_eq!(f.report.singletons_removed, 1);
        assert_eq!(f.core_columns, vec![0, 1, 2]);
        assert_eq!(f.core_rows.len(), 3);
        // A contradictory pair.
        let bad = vec![r(vec![(0, 1)], 1), r(vec![(0, 1)], 2)];
        assert!(filter_relations(bad, 1, P, &FilterOptions::default()).is_err());
        let empty = vec![r(vec![], 5)];
        assert!(filter_relations(empty, 1, P, &FilterOptions::default()).is_err());
    }

    #[test]
    fn approximant_basis_reproduces_scalar_berlekamp_massey() {
        // A scalar linear recurrence of order 5: the basis must contain
        // a column of degree 5 whose f is the connection polynomial.
        let modulus = P;
        let coeffs = [3u64, 7, 11, 13, 17];
        let mut s: Vec<u64> = vec![1, 2, 3, 4, 5];
        for t in 5..40 {
            let mut v = 0;
            for (k, &c) in coeffs.iter().enumerate() {
                v = addmod(v, mulmod(c, s[t - 1 - k], modulus), modulus);
            }
            s.push(v);
        }
        let seq: Vec<Vec<u64>> = s.iter().map(|&v| vec![v]).collect();
        let basis = minimal_approximant_basis(&seq, 1, 1, modulus);
        let best = basis.iter().min_by_key(|c| c.delta).unwrap();
        assert_eq!(best.delta, 5);
        // f(λ) = f_0 + f_1 λ + … with Σ_k s_{t−k} f_k = 0 for t ≥ 5.
        for t in 5..40 {
            let mut acc = 0;
            for (k, fk) in best.f.iter().enumerate() {
                acc = addmod(acc, mulmod(s[t - k], fk[0], modulus), modulus);
            }
            assert_eq!(acc, 0, "recurrence at t = {t}");
        }
        // And it is the true connection polynomial up to scaling.
        let scale = invmod(best.f[0][0], modulus).unwrap();
        for (k, &c) in coeffs.iter().enumerate() {
            assert_eq!(mulmod(best.f[k + 1][0], scale, modulus), negmod(c, modulus));
        }
    }

    #[test]
    fn approximant_basis_satisfies_the_block_recurrence() {
        let mut rng = StdRng::seed_from_u64(4);
        for &(m, n, big_n) in &[
            (1usize, 1usize, 9usize),
            (2, 2, 13),
            (3, 2, 20),
            (2, 4, 17),
            (4, 4, 40),
        ] {
            // A random dense square matrix; the sequence X Mᵗ Y.
            let mat: Vec<u64> = (0..big_n * big_n).map(|_| rng.gen_range(0..P)).collect();
            let x: Vec<u64> = (0..m * big_n).map(|_| rng.gen_range(0..P)).collect();
            let y: Vec<u64> = (0..big_n * n).map(|_| rng.gen_range(0..P)).collect();
            let big_l = big_n.div_ceil(m) + big_n.div_ceil(n) + 6;
            let mut v = y.clone();
            let mut seq = Vec::new();
            for _ in 0..big_l {
                let mut s = vec![0u64; m * n];
                for i in 0..m {
                    for j in 0..n {
                        for r in 0..big_n {
                            s[i * n + j] =
                                addmod(s[i * n + j], mulmod(x[i * big_n + r], v[r * n + j], P), P);
                        }
                    }
                }
                seq.push(s);
                let mut w = vec![0u64; big_n * n];
                for r in 0..big_n {
                    for j in 0..n {
                        for c in 0..big_n {
                            w[r * n + j] = addmod(
                                w[r * n + j],
                                mulmod(mat[r * big_n + c], v[c * n + j], P),
                                P,
                            );
                        }
                    }
                }
                v = w;
            }
            let basis = minimal_approximant_basis(&seq, m, n, P);
            assert_eq!(basis.len(), m + n);
            let total: usize = basis.iter().map(|c| c.delta).sum();
            assert!(total <= m + m * big_l, "degree budget");
            for col in &basis {
                for t in col.delta..big_l {
                    let mut acc = vec![0u64; m];
                    for (k, fk) in col.f.iter().enumerate() {
                        if k > t {
                            break;
                        }
                        for i in 0..m {
                            for j in 0..n {
                                acc[i] = addmod(acc[i], mulmod(seq[t - k][i * n + j], fk[j], P), P);
                            }
                        }
                    }
                    assert!(
                        acc.iter().all(|&a| a == 0),
                        "m={m} n={n}: recurrence fails at t={t}"
                    );
                }
            }
            // The n lowest-degree columns carry the Kalman degree N.
            let mut deltas: Vec<usize> = basis.iter().map(|c| c.delta).collect();
            deltas.sort_unstable();
            let low: usize = deltas[..n].iter().sum();
            assert!(
                low >= big_n && low <= big_n + n,
                "m={m} n={n}: low degrees {deltas:?}"
            );
        }
    }

    #[test]
    fn block_wiedemann_solves_random_sparse_systems() {
        let mut rng = StdRng::seed_from_u64(5);
        for &(m, n) in &[(1usize, 1usize), (2, 2), (4, 2), (2, 4), (4, 4), (8, 8)] {
            for &modulus in &[P, Q] {
                for trial in 0..4 {
                    let big_n = rng.gen_range(1..70);
                    let (rows, x) = planted_system(&mut rng, big_n, big_n, 4, modulus);
                    let a = CsrMatrix::from_rows(&rows, big_n, modulus);
                    let b: Vec<u64> = rows.iter().map(|r| r.rhs).collect();
                    let nonsingular = dense_reference(&rows, big_n, modulus).is_some();
                    let op = Homogenised { a: &a, b: &b };
                    let opts = BlockWiedemannOptions {
                        block_m: m,
                        block_n: n,
                        margin: 8,
                    };
                    let found = block_wiedemann_kernel(&op, &opts, rng.gen());
                    let Some((z, report)) = found else {
                        // Only a singular A can defeat the kernel search.
                        assert!(
                            !nonsingular,
                            "m={m} n={n} trial {trial}: no kernel vector for a nonsingular system"
                        );
                        continue;
                    };
                    assert!(z.iter().any(|&v| v != 0));
                    // z is in the kernel of the homogenised operator.
                    let mut img = vec![0u64; big_n + 1];
                    op.apply(&z, 1, &mut img);
                    assert!(
                        img.iter().all(|&v| v == 0),
                        "m={m} n={n}: not a kernel vector"
                    );
                    if nonsingular {
                        let t = z[big_n];
                        assert_ne!(t, 0, "kernel vector must have t ≠ 0 for nonsingular A");
                        let inv = invmod(t, modulus).unwrap();
                        let sol: Vec<u64> = z[..big_n]
                            .iter()
                            .map(|&v| mulmod(v, inv, modulus))
                            .collect();
                        assert_eq!(sol, x, "m={m} n={n} trial {trial} dim {big_n}");
                    }
                    assert_eq!(report.dimension, big_n + 1);
                    assert!(
                        report.sequence_length >= (big_n + 1).div_ceil(m) + (big_n + 1).div_ceil(n)
                    );
                }
            }
        }
    }

    #[test]
    fn block_wiedemann_finds_kernel_vectors_of_singular_matrices() {
        let mut rng = StdRng::seed_from_u64(6);
        for trial in 0..10 {
            let big_n = rng.gen_range(3..40);
            // Rank-deficient: the last row is a combination of two others.
            let (mut rows, _) = planted_system(&mut rng, big_n, big_n, 3, P);
            let (i, j) = (rng.gen_range(0..big_n - 1), rng.gen_range(0..big_n - 1));
            let combo = rows[i].axpy(rng.gen_range(1..P), &rows[j], P);
            let last = rows.len() - 1;
            rows[last] = combo;
            let a = CsrMatrix::from_rows(&rows, big_n, P);
            let opts = BlockWiedemannOptions::default();
            let mut found = false;
            for attempt in 0..3 {
                if let Some((z, _)) = block_wiedemann_kernel(&a, &opts, trial * 10 + attempt) {
                    assert!(z.iter().any(|&v| v != 0));
                    let mut img = vec![0u64; big_n];
                    a.apply(&z, 1, &mut img);
                    assert!(
                        img.iter().all(|&v| v == 0),
                        "trial {trial}: not in the kernel"
                    );
                    found = true;
                    break;
                }
            }
            assert!(
                found,
                "trial {trial}: singular matrix of dimension {big_n} yielded no kernel vector"
            );
        }
    }

    #[test]
    fn parallel_and_serial_block_products_agree() {
        let mut rng = StdRng::seed_from_u64(7);
        let big_n = PARALLEL_ROWS + 17;
        let (rows, _) = planted_system(&mut rng, big_n, big_n, 4, P);
        let a = CsrMatrix::from_rows(&rows, big_n, P);
        let n = 3;
        let x: Vec<u64> = (0..big_n * n).map(|_| rng.gen_range(0..P)).collect();
        let mut y = vec![0u64; big_n * n];
        a.mul_block(&x, n, &mut y);
        for (i, out) in y.chunks(n).enumerate() {
            let mut expect = vec![0u64; n];
            a.row_into(i, &x, n, &mut expect);
            assert_eq!(out, &expect[..], "row {i}");
        }
        assert_eq!(a.nnz(), rows.iter().map(SparseRow::weight).sum::<usize>());
    }

    #[test]
    fn sparse_solve_matches_dense_on_relation_shaped_systems() {
        let mut rng = StdRng::seed_from_u64(8);
        let mut solved = 0;
        let mut undetermined = 0;
        for trial in 0..50 {
            let columns = rng.gen_range(1..120);
            let rows_n = columns + rng.gen_range(0..columns + 4);
            let weight = rng.gen_range(2..=4);
            let modulus = if trial % 2 == 0 { P } else { Q };
            let (rows, x) = planted_system(&mut rng, rows_n, columns, weight, modulus);
            let opts = SparseSolveOptions {
                filter: FilterOptions {
                    target_excess: rng.gen_range(0..40),
                    merge_max_weight: rng.gen_range(0..10),
                    ..FilterOptions::default()
                },
                wiedemann: BlockWiedemannOptions {
                    block_m: rng.gen_range(1..5),
                    block_n: rng.gen_range(1..5),
                    margin: 8,
                },
                seed: trial,
                ..SparseSolveOptions::default()
            };
            let (outcome, report) = solve_sparse_system(&rows, columns, modulus, &opts);
            let reference = dense_reference(&rows, columns, modulus);
            match outcome {
                SparseSolveOutcome::Solved(sol) => {
                    assert_eq!(sol, x, "trial {trial}");
                    assert!(
                        reference.is_some(),
                        "trial {trial}: sparse solved an underdetermined system?"
                    );
                    assert_eq!(report.filter.rows_in, rows_n);
                    assert_eq!(
                        report.core_dimension + report.reconstructed_columns,
                        columns
                    );
                    solved += 1;
                }
                SparseSolveOutcome::Undetermined => {
                    // The sparse path may fail to converge on a determined
                    // system only through the random fold; with three
                    // attempts that should be rare, so demand agreement.
                    assert!(
                        reference.is_none(),
                        "trial {trial}: dense determined it but sparse gave up ({report:?})"
                    );
                    undetermined += 1;
                }
                SparseSolveOutcome::Inconsistent => {
                    panic!("trial {trial}: consistent system reported inconsistent")
                }
            }
        }
        assert!(
            solved >= 10 && undetermined >= 1,
            "solved {solved}, undetermined {undetermined}"
        );
    }

    #[test]
    fn sparse_solve_flags_a_wrong_relation() {
        let mut rng = StdRng::seed_from_u64(9);
        let (mut rows, _) = planted_system(&mut rng, 40, 20, 3, P);
        // Make sure it is determined before corrupting.
        let (before, _) = solve_sparse_system(&rows, 20, P, &SparseSolveOptions::default());
        assert!(matches!(before, SparseSolveOutcome::Solved(_)));
        rows[7].rhs = addmod(rows[7].rhs, 1, P);
        let (after, _) = solve_sparse_system(&rows, 20, P, &SparseSolveOptions::default());
        assert!(
            matches!(
                after,
                SparseSolveOutcome::Inconsistent | SparseSolveOutcome::Undetermined
            ),
            "a corrupted relation must not yield a verified solution: {after:?}"
        );
    }

    #[test]
    fn sparse_solve_handles_a_larger_system() {
        // Rows of weight exactly 3 with a sixfold excess, so every column
        // is covered many times over and the purge has work to do.
        let mut rng = StdRng::seed_from_u64(10);
        let columns = 3000usize;
        let x: Vec<u64> = (0..columns).map(|_| rng.gen_range(0..P)).collect();
        let rows: Vec<SparseRow> = (0..6 * columns)
            .map(|_| {
                let entries: Vec<(u32, u64)> = (0..3)
                    .map(|_| (rng.gen_range(0..columns) as u32, rng.gen_range(1..P)))
                    .collect();
                let mut row = SparseRow::new(entries, 0, P);
                row.rhs = row.evaluate(&x, P);
                row
            })
            .collect();
        let begin = std::time::Instant::now();
        let (outcome, report) =
            solve_sparse_system(&rows, columns, P, &SparseSolveOptions::default());
        println!(
            "3000-column sparse solve in {:.3}s: {report:?}",
            begin.elapsed().as_secs_f64()
        );
        match outcome {
            SparseSolveOutcome::Solved(sol) => assert_eq!(sol, x),
            other => panic!("expected a solution: {other:?} ({report:?})"),
        }
        assert!(
            report.filter.excess_rows_removed > 0,
            "purge ran: {report:?}"
        );
        assert!(
            report.core_dimension < columns,
            "filtering shrank the core: {report:?}"
        );
        assert_eq!(
            report.core_dimension + report.reconstructed_columns,
            columns
        );
        assert!(report.wiedemann.is_some());
    }

    /// Timing on a relation-shaped system at a chosen size, against the
    /// dense reference where that is affordable.  Run with
    /// `KOBLITZ_SPARSE_LA_COLUMNS=20000 cargo test --release --lib
    /// sparse_solve_benchmark -- --ignored --nocapture`.
    #[test]
    #[ignore]
    fn sparse_solve_benchmark() {
        let columns: usize = std::env::var("KOBLITZ_SPARSE_LA_COLUMNS")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(20_000);
        let weight: usize = std::env::var("KOBLITZ_SPARSE_LA_WEIGHT")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(3);
        let excess = columns / 10 + 64;
        let mut rng = StdRng::seed_from_u64(11);
        let x: Vec<u64> = (0..columns).map(|_| rng.gen_range(0..P)).collect();
        // Cover every column at least once, then random rows of the weight.
        let mut rows: Vec<SparseRow> = Vec::with_capacity(columns + excess);
        for c in 0..columns as u32 {
            let mut entries = vec![(c, rng.gen_range(1..P))];
            for _ in 1..weight {
                entries.push((rng.gen_range(0..columns) as u32, rng.gen_range(1..P)));
            }
            let mut row = SparseRow::new(entries, 0, P);
            row.rhs = row.evaluate(&x, P);
            rows.push(row);
        }
        for _ in 0..excess {
            let entries: Vec<(u32, u64)> = (0..weight)
                .map(|_| (rng.gen_range(0..columns) as u32, rng.gen_range(1..P)))
                .collect();
            let mut row = SparseRow::new(entries, 0, P);
            row.rhs = row.evaluate(&x, P);
            rows.push(row);
        }
        for block in [1usize, 2, 4, 8] {
            let opts = SparseSolveOptions {
                wiedemann: BlockWiedemannOptions {
                    block_m: block,
                    block_n: block,
                    margin: 8,
                },
                ..SparseSolveOptions::default()
            };
            let begin = std::time::Instant::now();
            let (outcome, report) = solve_sparse_system(&rows, columns, P, &opts);
            let secs = begin.elapsed().as_secs_f64();
            let ok = matches!(&outcome, SparseSolveOutcome::Solved(sol) if *sol == x);
            println!(
                "columns {columns} rows {} weight {weight} block {block}×{block}: {} in {secs:.3}s; core {} (nnz {}), attempts {}, {:?}",
                rows.len(),
                if ok { "solved" } else { "FAILED" },
                report.core_dimension,
                report.core_nonzeros,
                report.attempts,
                report.wiedemann
            );
            assert!(ok, "{outcome:?}");
        }
        if columns <= 3000 {
            let begin = std::time::Instant::now();
            let reference = dense_reference(&rows, columns, P);
            println!(
                "dense big-integer reference: {:.3}s",
                begin.elapsed().as_secs_f64()
            );
            assert_eq!(reference.as_ref(), Some(&x));
        }
    }
}
