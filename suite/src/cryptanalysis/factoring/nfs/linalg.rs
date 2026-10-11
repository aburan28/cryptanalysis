//! Linear algebra over GF(2): relation filtering, structured Gaussian
//! elimination and a dense bit-packed Gauss–Jordan null-space solver.
//!
//! Both sieves ([`qs`](mod@crate::cryptanalysis::factoring::qs) and the NFS core)
//! end the same way: every relation is a sparse vector of exponent
//! **parities** over some set of columns (primes, prime ideals, large
//! primes, signs, quadratic characters), and a subset of relations whose
//! vectors sum to zero gives a congruence of squares.  This module finds
//! such subsets.
//!
//! # Pipeline
//!
//! 1. **Singleton removal.**  A column met by exactly one relation can
//!    never cancel, so that relation cannot be in any dependency; drop it
//!    and repeat until stable.  With large primes this discards most
//!    partial relations and is also the *stopping test* the sieves use
//!    ([`filtered_excess`]).
//! 2. **Excess trimming.**  Keep only `cols + surplus` relations (the
//!    heaviest are dropped), then re-run singleton removal.
//! 3. **Structured Gaussian elimination** (LaMacchia–Odlyzko, Pomerance–
//!    Smith).  Repeatedly take a column of weight `w ≤ 64` (lightest
//!    first), pivot on its lightest row, add that row to the other
//!    `w − 1` and delete both row and column.  Every step removes one row
//!    and one column, so the excess is preserved while the matrix shrinks
//!    — weight-2 columns (large primes seen twice) are the common case.
//!    Fill-in only costs time here, because the next step is dense
//!    anyway; on NFS matrices this removes 65–80% of the dimension.
//! 4. **Dense Gauss–Jordan** on the remaining `C × R` matrix, packed 64
//!    bits to a word, with the Method of Four Russians (eight columns per
//!    table).  Cost `O(C²·R / 512)` word operations: about 2 s for
//!    `C ≈ 8000`.  Every free column gives a null vector.
//!
//! This replaces the block Lanczos / block Wiedemann solvers of real NFS
//! implementations, which are needed from `C ≈ 10⁵` upward.
//!
//! References: B. LaMacchia and A. Odlyzko, *Solving large sparse linear
//! systems over finite fields*, CRYPTO '90; C. Pomerance and J. Smith,
//! *Reduction of huge, sparse matrices over finite fields via created
//! catastrophes*, Experimental Math. 1 (1992).

use serde::Serialize;
use std::time::Instant;

/// Sizes at each stage of the GF(2) solve.
#[derive(Clone, Debug, Default, Serialize)]
pub struct LinalgStats {
    /// Relations (rows) handed in.
    pub rows_in: usize,
    /// Distinct columns among them.
    pub cols_in: usize,
    /// Rows left after singleton removal and excess trimming.
    pub rows_filtered: usize,
    /// Columns left after singleton removal and excess trimming.
    pub cols_filtered: usize,
    /// Rows of the dense matrix after structured elimination.
    pub dense_rows: usize,
    /// Columns of the dense matrix after structured elimination.
    pub dense_cols: usize,
    /// Rank of the dense matrix.
    pub rank: usize,
    /// Null vectors returned.
    pub dependencies: usize,
    /// Wall-clock seconds spent in this module.
    pub seconds: f64,
}

/// Highest column weight structured elimination pivots on.
const SGE_MAX_WEIGHT: u32 = 64;
/// Columns heavier than this are never tracked for elimination.
const SGE_TRACK_LIMIT: u32 = 200;
/// Skip a pivot whose row is longer than this (limits fill-in cost).
const SGE_MAX_PIVOT_LEN: usize = 4000;

/// Normalise a list of column indices with multiplicity into the sorted
/// set of columns with **odd** multiplicity.
pub fn parity_vector(mut cols: Vec<u32>) -> Vec<u32> {
    cols.sort_unstable();
    let mut out = Vec::with_capacity(cols.len());
    let mut i = 0;
    while i < cols.len() {
        let mut j = i;
        while j < cols.len() && cols[j] == cols[i] {
            j += 1;
        }
        if (j - i) % 2 == 1 {
            out.push(cols[i]);
        }
        i = j;
    }
    out
}

/// Symmetric difference of two sorted `u32` sets.
fn sym_diff(a: &[u32], b: &[u32]) -> Vec<u32> {
    let mut out = Vec::with_capacity(a.len() + b.len());
    let (mut i, mut j) = (0, 0);
    while i < a.len() && j < b.len() {
        match a[i].cmp(&b[j]) {
            std::cmp::Ordering::Less => {
                out.push(a[i]);
                i += 1;
            }
            std::cmp::Ordering::Greater => {
                out.push(b[j]);
                j += 1;
            }
            std::cmp::Ordering::Equal => {
                i += 1;
                j += 1;
            }
        }
    }
    out.extend_from_slice(&a[i..]);
    out.extend_from_slice(&b[j..]);
    out
}

fn max_col(rows: &[Vec<u32>]) -> usize {
    rows.iter()
        .filter_map(|r| r.last())
        .map(|&c| c as usize + 1)
        .max()
        .unwrap_or(0)
}

/// Iterated singleton removal over the rows flagged `alive`.  Returns the
/// number of live rows and live (non-empty) columns.
fn remove_singletons(rows: &[Vec<u32>], alive: &mut [bool]) -> (usize, usize) {
    let ncols = max_col(rows);
    let mut weight = vec![0u32; ncols];
    for (r, row) in rows.iter().enumerate() {
        if alive[r] {
            for &c in row {
                weight[c as usize] += 1;
            }
        }
    }
    loop {
        let mut changed = false;
        for (r, row) in rows.iter().enumerate() {
            if alive[r] && (row.is_empty() || row.iter().any(|&c| weight[c as usize] == 1)) {
                // An empty row is a dependency by itself; keep it.
                if row.is_empty() {
                    continue;
                }
                alive[r] = false;
                changed = true;
                for &c in row {
                    weight[c as usize] -= 1;
                }
            }
        }
        if !changed {
            break;
        }
    }
    let live_rows = alive.iter().filter(|&&a| a).count();
    let live_cols = weight.iter().filter(|&&w| w > 0).count();
    (live_rows, live_cols)
}

/// After singleton removal: `(rows, columns)` that survive.  The sieves
/// stop once `rows ≥ columns + surplus`.
pub fn filtered_excess(rows: &[Vec<u32>]) -> (usize, usize) {
    let mut alive = vec![true; rows.len()];
    remove_singletons(rows, &mut alive)
}

/// Which rows survive singleton removal.
pub fn singleton_survivors(rows: &[Vec<u32>]) -> Vec<bool> {
    let mut alive = vec![true; rows.len()];
    remove_singletons(rows, &mut alive);
    alive
}

/// Structured Gaussian elimination state.  Instead of carrying, for each
/// row, the set of original relations it sums (whose symmetric differences
/// dominate the cost), each row records the pivots that were added to it;
/// a pivot's list is frozen when it is eliminated, so the sets are
/// recovered at the end by one parity sweep over this DAG.
struct Sge {
    cols: Vec<Vec<u32>>,
    applied: Vec<Vec<u32>>,
    pivots: Vec<u32>,
    alive: Vec<bool>,
    weight: Vec<u32>,
    tracked: Vec<bool>,
    col_rows: Vec<Vec<u32>>,
}

impl Sge {
    fn detach(&mut self, r: u32, c: u32) {
        let cu = c as usize;
        self.weight[cu] -= 1;
        if self.tracked[cu] {
            if let Some(pos) = self.col_rows[cu].iter().position(|&x| x == r) {
                self.col_rows[cu].swap_remove(pos);
            }
        }
    }

    fn attach(&mut self, r: u32, c: u32) {
        let cu = c as usize;
        self.weight[cu] += 1;
        if self.tracked[cu] {
            if self.weight[cu] > SGE_TRACK_LIMIT {
                self.tracked[cu] = false;
                self.col_rows[cu] = Vec::new();
            } else {
                self.col_rows[cu].push(r);
            }
        }
    }

    fn kill_row(&mut self, r: u32) {
        let row = std::mem::take(&mut self.cols[r as usize]);
        for &c in &row {
            self.detach(r, c);
        }
        self.alive[r as usize] = false;
    }

    /// The original relations whose sum is the sum of the current rows
    /// `top` (each listed once): parity propagation down the pivot DAG,
    /// latest pivots first.
    fn expand(&self, top: &[usize]) -> Vec<usize> {
        let mut parity = vec![false; self.cols.len()];
        for &r in top {
            parity[r] ^= true;
        }
        let mut out = Vec::new();
        let order = top
            .iter()
            .copied()
            .chain(self.pivots.iter().rev().map(|&p| p as usize));
        let mut done = vec![false; self.cols.len()];
        for v in order {
            if done[v] {
                continue;
            }
            done[v] = true;
            if !parity[v] {
                continue;
            }
            out.push(v);
            for &p in &self.applied[v] {
                parity[p as usize] ^= true;
            }
        }
        out.sort_unstable();
        out
    }

    /// Eliminate column `c`; returns false if it was skipped.
    fn eliminate(&mut self, c: usize) -> bool {
        let rows = self.col_rows[c].clone();
        if rows.is_empty() {
            return false;
        }
        if rows.len() == 1 {
            self.kill_row(rows[0]);
            return true;
        }
        let pivot = *rows
            .iter()
            .min_by_key(|&&r| self.cols[r as usize].len())
            .expect("non-empty");
        if self.cols[pivot as usize].len() > SGE_MAX_PIVOT_LEN {
            self.tracked[c] = false;
            self.col_rows[c] = Vec::new();
            return false;
        }
        let pcols = self.cols[pivot as usize].clone();
        for &r in &rows {
            if r == pivot {
                continue;
            }
            let old = std::mem::take(&mut self.cols[r as usize]);
            // Columns of the pivot toggle in row r.
            let mut i = 0;
            for &pc in &pcols {
                while i < old.len() && old[i] < pc {
                    i += 1;
                }
                if i < old.len() && old[i] == pc {
                    self.detach(r, pc);
                } else {
                    self.attach(r, pc);
                }
            }
            self.cols[r as usize] = sym_diff(&old, &pcols);
            self.applied[r as usize].push(pivot);
        }
        self.kill_row(pivot);
        self.pivots.push(pivot);
        true
    }
}

/// Bit `j` of row `i`.
#[inline]
fn get_bit(mat: &[u64], words: usize, i: usize, j: usize) -> bool {
    mat[i * words + j / 64] >> (j % 64) & 1 == 1
}

/// `row[dst] ^= row[src]`.
#[inline]
fn xor_rows(mat: &mut [u64], words: usize, dst: usize, src: usize) {
    if dst == src {
        return;
    }
    let (d, s) = if dst < src {
        let (a, b) = mat.split_at_mut(src * words);
        (&mut a[dst * words..(dst + 1) * words], &b[..words])
    } else {
        let (a, b) = mat.split_at_mut(dst * words);
        (&mut b[..words], &a[src * words..(src + 1) * words])
    };
    for (x, y) in d.iter_mut().zip(s) {
        *x ^= *y;
    }
}

/// Reduced row echelon form of the `nc × nr` bit matrix, in place, by the
/// **Method of Four Russians** (Arlazarov et al. 1970; Bard 2006): columns
/// are processed eight at a time; the (at most eight) pivots of a group
/// are found and mutually reduced, all `2⁸` combinations of them are
/// tabulated, and every other row is cleared on the group with a single
/// table lookup and one row XOR — eight times fewer row operations than
/// plain Gauss–Jordan.  Returns the pivot column of each of the first
/// `rank` rows.
fn dense_rref(mat: &mut [u64], nc: usize, nr: usize, words: usize) -> Vec<usize> {
    const K: usize = 8;
    let mut pivots: Vec<usize> = Vec::new();
    let mut table = vec![0u64; (1 << K) * words];
    let mut rank = 0usize;
    let mut j0 = 0usize;
    while j0 < nr && rank < nc {
        let jend = (j0 + K).min(nr);
        // 1. Pivots of this column group, kept mutually reduced.
        let mut group: Vec<(usize, usize)> = Vec::with_capacity(K);
        let mut cand = rank;
        while group.len() < jend - j0 && cand < nc {
            for &(pr, pc) in &group {
                if get_bit(mat, words, cand, pc) {
                    xor_rows(mat, words, cand, pr);
                }
            }
            let found = (j0..jend)
                .find(|&c| !group.iter().any(|&(_, pc)| pc == c) && get_bit(mat, words, cand, c));
            if let Some(c) = found {
                let pos = rank + group.len();
                if pos != cand {
                    let (a, b) = mat.split_at_mut(cand * words);
                    a[pos * words..(pos + 1) * words].swap_with_slice(&mut b[..words]);
                }
                for &(pr, _) in &group {
                    if get_bit(mat, words, pr, c) {
                        xor_rows(mat, words, pr, pos);
                    }
                }
                group.push((pos, c));
            }
            cand += 1;
        }
        let g = group.len();
        if g > 0 {
            // 2. Table of all combinations of the group's pivot rows.
            table[..words].fill(0);
            for idx in 1usize..(1 << g) {
                let t = idx.trailing_zeros() as usize;
                let prev = idx & (idx - 1);
                let row = group[t].0;
                for k in 0..words {
                    table[idx * words + k] = table[prev * words + k] ^ mat[row * words + k];
                }
            }
            // 3. Clear the group's pivot columns in every other row.
            for i in 0..nc {
                if i >= rank && i < rank + g {
                    continue;
                }
                let mut idx = 0usize;
                for (t, &(_, pc)) in group.iter().enumerate() {
                    idx |= (get_bit(mat, words, i, pc) as usize) << t;
                }
                if idx != 0 {
                    let row = &mut mat[i * words..(i + 1) * words];
                    for (x, y) in row.iter_mut().zip(&table[idx * words..(idx + 1) * words]) {
                        *x ^= *y;
                    }
                }
            }
            pivots.extend(group.iter().map(|&(_, c)| c));
            rank += g;
        }
        j0 = jend;
    }
    pivots
}

/// Find up to `max_deps` subsets of `rows` whose parity vectors sum to
/// zero.  Each row must already be a sorted parity vector
/// ([`parity_vector`]).  `surplus` is how many more rows than columns to
/// keep after filtering (more gives more dependencies; 64 is ample).
pub fn find_dependencies(
    rows: &[Vec<u32>],
    max_deps: usize,
    surplus: usize,
) -> (Vec<Vec<usize>>, LinalgStats) {
    let t0 = Instant::now();
    let mut stats = LinalgStats {
        rows_in: rows.len(),
        ..Default::default()
    };
    let ncols = max_col(rows);
    {
        let mut seen = vec![false; ncols];
        for row in rows {
            for &c in row {
                seen[c as usize] = true;
            }
        }
        stats.cols_in = seen.iter().filter(|&&s| s).count();
    }

    // 1. Singleton removal.
    let mut alive = vec![true; rows.len()];
    let (mut live_rows, mut live_cols) = remove_singletons(rows, &mut alive);

    // 2. Trim the excess: drop the heaviest rows beyond cols + surplus.
    if live_rows > live_cols + surplus {
        let mut order: Vec<usize> = (0..rows.len()).filter(|&r| alive[r]).collect();
        order.sort_by_key(|&r| std::cmp::Reverse(rows[r].len()));
        let drop = live_rows - live_cols - surplus;
        for &r in order.iter().take(drop) {
            alive[r] = false;
        }
        (live_rows, live_cols) = remove_singletons(rows, &mut alive);
    }
    stats.rows_filtered = live_rows;
    stats.cols_filtered = live_cols;

    // 3. Structured Gaussian elimination.
    let mut sge = Sge {
        cols: Vec::with_capacity(rows.len()),
        applied: vec![Vec::new(); rows.len()],
        pivots: Vec::new(),
        alive: alive.clone(),
        weight: vec![0; ncols],
        tracked: vec![true; ncols],
        col_rows: vec![Vec::new(); ncols],
    };
    for (r, row) in rows.iter().enumerate() {
        if alive[r] {
            sge.cols.push(row.clone());
            for &c in row {
                sge.weight[c as usize] += 1;
            }
        } else {
            sge.cols.push(Vec::new());
        }
    }
    for c in 0..ncols {
        if sge.weight[c] > SGE_TRACK_LIMIT {
            sge.tracked[c] = false;
        }
    }
    for (r, row) in sge.cols.iter().enumerate() {
        if sge.alive[r] {
            for &c in row {
                if sge.tracked[c as usize] {
                    sge.col_rows[c as usize].push(r as u32);
                }
            }
        }
    }
    for wlimit in 1..=SGE_MAX_WEIGHT {
        loop {
            let mut changed = false;
            for c in 0..ncols {
                let w = sge.weight[c];
                if sge.tracked[c] && w >= 1 && w <= wlimit && sge.eliminate(c) {
                    changed = true;
                }
            }
            if !changed {
                break;
            }
        }
    }

    // Empty rows are dependencies on their own.
    let mut deps: Vec<Vec<usize>> = Vec::new();
    let live: Vec<usize> = (0..rows.len()).filter(|&r| sge.alive[r]).collect();
    for &r in &live {
        if sge.cols[r].is_empty() && deps.len() < max_deps {
            deps.push(sge.expand(&[r]));
        }
    }
    let live: Vec<usize> = live
        .into_iter()
        .filter(|&r| !sge.cols[r].is_empty())
        .collect();

    // 4. Dense Gauss–Jordan: one equation per column, one variable per row.
    let mut col_map = vec![u32::MAX; ncols];
    let mut nc = 0usize;
    for &r in &live {
        for &c in &sge.cols[r] {
            if col_map[c as usize] == u32::MAX {
                col_map[c as usize] = nc as u32;
                nc += 1;
            }
        }
    }
    let nr = live.len();
    stats.dense_rows = nr;
    stats.dense_cols = nc;
    let words = nr.div_ceil(64);
    let mut mat = vec![0u64; nc * words];
    for (j, &r) in live.iter().enumerate() {
        for &c in &sge.cols[r] {
            let i = col_map[c as usize] as usize;
            mat[i * words + j / 64] |= 1u64 << (j % 64);
        }
    }
    let pivot_of_eq = dense_rref(&mut mat, nc, nr, words);
    let rank = pivot_of_eq.len();
    let mut is_pivot = vec![false; nr];
    for &j in &pivot_of_eq {
        is_pivot[j] = true;
    }
    stats.rank = rank;
    for j in 0..nr {
        if deps.len() >= max_deps {
            break;
        }
        if is_pivot[j] {
            continue;
        }
        let (w, bit) = (j / 64, 1u64 << (j % 64));
        let mut top = vec![live[j]];
        for (i, &pj) in pivot_of_eq.iter().enumerate() {
            if mat[i * words + w] & bit != 0 {
                top.push(live[pj]);
            }
        }
        let combo = sge.expand(&top);
        if !combo.is_empty() {
            deps.push(combo);
        }
    }
    stats.dependencies = deps.len();
    stats.seconds = t0.elapsed().as_secs_f64();
    (deps, stats)
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::{rngs::SmallRng, Rng, SeedableRng};

    fn check_dep(rows: &[Vec<u32>], dep: &[usize]) -> bool {
        let mut all = Vec::new();
        for &r in dep {
            all.extend_from_slice(&rows[r]);
        }
        parity_vector(all).is_empty()
    }

    #[test]
    fn parity_vector_cancels_pairs() {
        assert_eq!(parity_vector(vec![3, 1, 3, 2, 1, 1]), vec![1, 2]);
    }

    #[test]
    fn random_sparse_matrix_dependencies_are_valid() {
        let mut rng = SmallRng::seed_from_u64(7);
        let ncols = 400u32;
        let rows: Vec<Vec<u32>> = (0..460)
            .map(|_| {
                let k = rng.gen_range(2..12);
                // Skew towards small columns, as with small primes.
                parity_vector(
                    (0..k)
                        .map(|_| {
                            let x: f64 = rng.gen();
                            ((x * x) * ncols as f64) as u32
                        })
                        .collect(),
                )
            })
            .collect();
        let (deps, stats) = find_dependencies(&rows, 32, 64);
        assert!(!deps.is_empty(), "{stats:?}");
        for d in &deps {
            assert!(check_dep(&rows, d));
        }
        // Distinct dependencies.
        let mut sorted: Vec<Vec<usize>> = deps
            .iter()
            .map(|d| {
                let mut d = d.clone();
                d.sort();
                d
            })
            .collect();
        sorted.sort();
        sorted.dedup();
        assert_eq!(sorted.len(), deps.len());
    }

    #[test]
    fn duplicate_row_is_a_dependency() {
        let rows = vec![vec![0, 5], vec![1, 2], vec![0, 5], vec![3]];
        let (deps, _) = find_dependencies(&rows, 4, 64);
        assert!(deps.iter().any(|d| {
            let mut d = d.clone();
            d.sort();
            d == vec![0, 2]
        }));
    }
}
