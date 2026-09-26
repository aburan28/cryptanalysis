//! # F4 over the boolean ring `F_2[v_0, …, v_{n−1}] / (v_i² − v_i)`.
//!
//! Faugère's F4 (1999) is Buchberger's algorithm with the reductions
//! batched: at each step it takes **every** critical pair of the lowest
//! degree, writes the two halves of each S-polynomial as rows of one
//! matrix, adds a reducer row for every monomial some basis element's
//! leading monomial divides (*symbolic preprocessing*), and reduces the
//! whole matrix at once.  Rows whose pivot is a monomial no basis
//! element leads join the basis.  Over `F_2` the matrix is bit-packed,
//! sixty-four columns to a word, so a reduction step is a run of 64-bit
//! XORs — the unit this module counts.
//!
//! [`pq_groebner_f2`](crate::cryptanalysis::pq_groebner_f2) reduces the
//! same pairs one at a time on sorted monomial lists.  This module is the
//! batched version of the same computation, and a test holds it to that:
//! wherever the Buchberger output is certified to be a Gröbner basis of
//! the boolean ideal, the two reduced bases are identical.
//!
//! ## The field pairs, which the boolean ring needs
//!
//! In `F_2[v]/(v² − v)` a Gröbner basis must also be closed under the
//! products `v_i · g` for every variable `v_i` of `LM(g)`: those are the
//! S-polynomials of `g` against the field equations `v_i² + v_i`, and
//! multiplying by a variable already in the leading monomial is not
//! order-compatible there — `v_0·(v_0v_1 + v_0 + v_1) = v_0`, a smaller
//! leading monomial.  An engine that forms only the S-polynomials of its
//! own basis can stop early: on `{v_0v_1 + v_0 + v_1}` it returns the
//! generator itself, three standard monomials for an ideal with one
//! solution.  This engine queues a **field pair** `(g, v_i)` for every
//! basis element and every variable of its leading monomial, at sugar
//! degree `deg LM(g) + 1`, and reduces it in the same matrices as the
//! critical pairs.
//!
//! A field product is a single row, not half of a pair, so Faugère's
//! "the pivot is not a leading monomial of an input row" test for new
//! elements does not apply to it.  The test used here is the one that
//! holds for both: a reduced row is **new** iff its pivot is divisible by
//! no active basis leading monomial.  Symbolic preprocessing makes that
//! exact, because every such divisible monomial other than an S-pair's
//! common leading monomial receives a reducer row led by it.
//!
//! ## Pair criteria
//!
//! Critical pairs go through the Gebauer–Möller installation (Becker and
//! Weispfenning's `UPDATE`): the chain criterion on the new pairs and on
//! the queued ones, and Buchberger's product criterion.  These hold for
//! the ideal `I + ⟨v_i² + v_i⟩` of the polynomial ring, whose basis
//! elements other than the field equations are exactly the boolean
//! polynomials here, with square-free leading monomials; the field pairs
//! are never pruned and never used to prune.
//!
//! ## What is counted
//!
//! `word_xors`: 64-bit XORs in the eliminations — the forward pass of
//! every step and of the initial echelon, and the backward pass of the
//! final inter-reduction — counting only the words between a pivot's
//! lead and its last non-zero word, which is the work performed.  The
//! construction of the matrices (the products, the column map, the
//! packing) is **not** in that count; its wall time is reported beside
//! it as `build_ns`, so a reader can see what share of the run the unit
//! covers.  Solution extraction counts its monomial tests separately.
//!
//! ## Solutions, without enumeration
//!
//! The ideal of a boolean system is radical and zero-dimensional, so its
//! reduced basis has exactly as many standard monomials as the system
//! has solutions.  A variable is either the leading monomial of a linear
//! basis element or itself standard — *free*.  Every linear element
//! reads `v_p + (free variables) + c`, so an assignment of the free
//! variables determines the point, and there are at most
//! `#solutions − 1` of them.  [`solutions_from_reduced_basis`]
//! enumerates those assignments and keeps the points every basis element
//! vanishes at; the cost is `2^{#free}`, not `2^n`.
//!
//! ## References
//!
//! - J.-C. Faugère, *A new efficient algorithm for computing Gröbner
//!   bases (F4)*, J. Pure Appl. Algebra 139 (1999).
//! - T. Becker, V. Weispfenning, *Gröbner Bases*, Springer 1993 —
//!   `UPDATE`, p. 230.
//! - M. Brickenstein, *Boolean Gröbner bases*, PhD thesis, TU
//!   Kaiserslautern 2010 — the boolean ring and its field pairs.

use std::collections::HashSet;
use std::time::{Duration, Instant};

use rayon::prelude::*;

use crate::cryptanalysis::fx_hash::{FxMap, FxSet};
use crate::cryptanalysis::pq_groebner_f2::{cmp_mono, mono_key, F2BoolMono, F2BoolPoly};

/// What one F4 run cost, and how far it got.
#[derive(Clone, Copy, Debug, Default, serde::Serialize)]
pub struct F4Stats {
    /// F4 steps: one matrix each, after the initial echelon.
    pub steps: u64,
    /// Critical pairs reduced, and field pairs reduced.
    pub pairs_reduced: u64,
    pub field_pairs_reduced: u64,
    /// Pairs Buchberger's product criterion dropped.
    pub pairs_product_skipped: u64,
    /// Pairs the Gebauer–Möller chain criterion dropped.
    pub pairs_chain_skipped: u64,
    /// Rows symbolic preprocessing added as reducers.
    pub reducer_rows: u64,
    /// Largest matrix built, and the sum of rows over every matrix.
    pub matrix_rows_max: u64,
    pub matrix_cols_max: u64,
    pub matrix_rows_sum: u64,
    /// The unit: 64-bit XORs performed by the eliminations.
    pub word_xors: u64,
    /// Divisibility tests made by symbolic preprocessing, one word
    /// operation each; reported, not in `word_xors`.
    pub divisor_tests: u64,
    /// Elements added to the basis after the initial echelon.
    pub new_elements: u64,
    /// Highest step degree processed.
    pub degree_reached: u32,
    /// Highest step degree at which the basis gained an element: the
    /// solving degree, comparable to `GbStats::solving_degree`.
    pub solving_degree: u32,
    /// Highest degree of any row in any matrix.
    pub max_poly_degree: u32,
    /// Elements of the reduced basis returned.
    pub basis_len: u64,
    /// Largest matrix held, in bytes of packed words.
    pub peak_matrix_bytes: u64,
    /// Wall time spent building matrices (products, columns, packing)
    /// and eliminating them.
    pub build_ns: u64,
    pub eliminate_ns: u64,
    pub wall_ns: u64,
    /// The budget ran out; the returned set is not a Gröbner basis.
    pub timed_out: bool,
    /// A matrix would have exceeded [`MAX_MATRIX_WORDS`].
    pub oversize: bool,
    pub pairs_left: u64,
}

/// The largest matrix a step may build, in 64-bit words (1 GiB).
pub const MAX_MATRIX_WORDS: u64 = 1 << 27;

const NONE: u32 = u32::MAX;

#[derive(Clone, Copy, Debug)]
enum PairKind {
    /// The S-polynomial of basis elements `i` and `j`.
    Critical(usize, usize),
    /// `v · g_i` for a variable `v` of `LM(g_i)`: the S-polynomial of
    /// `g_i` against the field equation `v² + v`.
    Field(usize, u32),
}

#[derive(Clone, Copy, Debug)]
struct Pair {
    kind: PairKind,
    /// The lcm of the two leading monomials (critical pairs only).
    lcm: u64,
    /// Selection degree: `deg lcm`, or `deg LM(g) + 1` for a field pair.
    deg: u32,
}

/// A bit-packed row.  Words outside `[start, end)` are zero.
struct Row {
    bits: Vec<u64>,
    start: usize,
    end: usize,
}

impl Row {
    fn lead(&mut self) -> Option<usize> {
        while self.start < self.end {
            let w = self.bits[self.start];
            if w != 0 {
                return Some(self.start * 64 + w.trailing_zeros() as usize);
            }
            self.start += 1;
        }
        None
    }
}

/// The columns of one matrix: monomials in descending order, so the
/// first set bit of a row is its leading monomial.
struct Columns {
    monos: Vec<u64>,
    index: FxMap<u64, usize>,
}

impl Columns {
    fn from_monomials(set: impl IntoIterator<Item = u64>) -> Self {
        let mut monos: Vec<u64> = set.into_iter().collect();
        monos.sort_unstable_by_key(|&m| std::cmp::Reverse(mono_key(F2BoolMono::from_mask(m))));
        monos.dedup();
        let index = monos.iter().enumerate().map(|(i, &m)| (m, i)).collect();
        Self { monos, index }
    }

    fn words(&self) -> usize {
        self.monos.len().div_ceil(64).max(1)
    }

    fn pack(&self, p: &F2BoolPoly) -> Row {
        let mut bits = vec![0u64; self.words()];
        let (mut start, mut end) = (usize::MAX, 0usize);
        for t in &p.terms {
            let c = self.index[&t.mask];
            bits[c / 64] ^= 1u64 << (c % 64);
            start = start.min(c / 64);
            end = end.max(c / 64 + 1);
        }
        if start == usize::MAX {
            start = 0;
        }
        Row { bits, start, end }
    }

    fn unpack(&self, row: &Row, n_vars: usize) -> F2BoolPoly {
        let mut monos = Vec::new();
        for w in row.start..row.end {
            let mut word = row.bits[w];
            while word != 0 {
                let c = w * 64 + word.trailing_zeros() as usize;
                word &= word - 1;
                monos.push(F2BoolMono::from_mask(self.monos[c]));
            }
        }
        F2BoolPoly::from_monos(monos, n_vars)
    }
}

/// Rows × words of a matrix's non-leading rows below which the reductions
/// by the leading block run on one thread.
const PAR_WORDS: usize = 1 << 16;

/// Forward elimination: each row in turn is reduced by the pivots found
/// so far and becomes a pivot if anything survives.  Returns the pivot
/// rows with their lead columns, or `None` if the deadline passed.
///
/// The leading block of rows with pairwise distinct leads — the reducers
/// of symbolic preprocessing — become pivots untouched, and every later
/// row is first reduced by them alone for as long as its lead is one of
/// theirs.  Those reductions are independent across rows and run in
/// parallel; the serial pass then resumes each row exactly where the
/// one-row-at-a-time loop would stand at that point, so the pivots and
/// the XOR count are identical to it.
fn echelon(
    mut rows: Vec<Row>,
    n_cols: usize,
    word_xors: &mut u64,
    deadline: Option<Instant>,
) -> Option<Vec<(usize, Row)>> {
    let mut pivot_of = vec![NONE; n_cols];
    let mut pivots: Vec<(usize, Row)> = Vec::with_capacity(rows.len());
    // the leading block: rows until the first repeated lead (zero rows
    // are skipped by the serial loop too)
    let mut fixed = 0usize;
    while fixed < rows.len() {
        match rows[fixed].lead() {
            Some(lead) if pivot_of[lead] != NONE => break,
            Some(lead) => pivot_of[lead] = 0,
            None => {}
        }
        fixed += 1;
    }
    let rest = rows.split_off(fixed);
    for mut row in rows {
        if let Some(lead) = row.lead() {
            pivot_of[lead] = pivots.len() as u32;
            pivots.push((lead, row));
        }
    }
    let mut rest = rest;
    {
        let (pivot_of, fixed_pivots) = (&pivot_of, &pivots);
        let expired = std::sync::atomic::AtomicBool::new(false);
        let by_fixed = |row: &mut Row| -> u64 {
            if deadline.is_some_and(|d| Instant::now() >= d) {
                expired.store(true, std::sync::atomic::Ordering::Relaxed);
                return 0;
            }
            let mut xors = 0u64;
            while let Some(lead) = row.lead() {
                let p = pivot_of[lead];
                if p == NONE {
                    break;
                }
                let pivot = &fixed_pivots[p as usize].1;
                let (from, to) = (lead / 64, pivot.end);
                for (a, b) in row.bits[from..to].iter_mut().zip(&pivot.bits[from..to]) {
                    *a ^= *b;
                }
                xors += (to - from) as u64;
                row.end = row.end.max(to);
            }
            xors
        };
        let words = n_cols.div_ceil(64).max(1);
        *word_xors += if rest.len() > 1 && rest.len() * words > PAR_WORDS {
            rest.par_iter_mut().map(by_fixed).sum::<u64>()
        } else {
            rest.iter_mut().map(by_fixed).sum::<u64>()
        };
        if expired.load(std::sync::atomic::Ordering::Relaxed) {
            return None;
        }
    }
    for (k, mut row) in rest.into_iter().enumerate() {
        if k % 128 == 0 && deadline.is_some_and(|d| Instant::now() >= d) {
            return None;
        }
        while let Some(lead) = row.lead() {
            match pivot_of[lead] {
                NONE => {
                    pivot_of[lead] = pivots.len() as u32;
                    pivots.push((lead, row));
                    break;
                }
                p => {
                    let pivot = &pivots[p as usize].1;
                    let (from, to) = (lead / 64, pivot.end);
                    for (a, b) in row.bits[from..to].iter_mut().zip(&pivot.bits[from..to]) {
                        *a ^= *b;
                    }
                    *word_xors += (to - from) as u64;
                    row.end = row.end.max(to);
                }
            }
        }
    }
    Some(pivots)
}

fn is_one(p: &F2BoolPoly) -> bool {
    p.terms.len() == 1 && p.terms[0].mask == 0
}

fn degree(p: &F2BoolPoly) -> u32 {
    p.terms.iter().map(|t| t.degree()).max().unwrap_or(0)
}

struct State {
    n_vars: usize,
    polys: Vec<F2BoolPoly>,
    lm: Vec<u64>,
    active: Vec<bool>,
    pairs: Vec<Pair>,
}

impl State {
    /// Becker–Weispfenning `UPDATE` for the critical pairs, plus the
    /// field pairs of the new element.
    fn insert(&mut self, h_poly: F2BoolPoly, st: &mut F4Stats) {
        let h = self.polys.len();
        let lh = h_poly.lt().expect("a new element is non-zero").mask;
        self.polys.push(h_poly);
        self.lm.push(lh);
        self.active.push(false);

        let dh = lh.count_ones();
        let mut bits = lh;
        while bits != 0 {
            let v = bits.trailing_zeros();
            bits &= bits - 1;
            self.pairs.push(Pair {
                kind: PairKind::Field(h, v),
                lcm: lh,
                deg: dh + 1,
            });
        }

        // New pairs (h, g): keep one per minimal lcm (chain criterion).
        let mut c: Vec<(usize, u64)> = (0..h)
            .filter(|&g| self.active[g])
            .map(|g| (g, lh | self.lm[g]))
            .collect();
        let mut d: Vec<(usize, u64)> = Vec::with_capacity(c.len());
        while let Some((g1, l1)) = c.pop() {
            let coprime = lh & self.lm[g1] == 0;
            let covered = c.iter().chain(d.iter()).any(|&(_, l2)| l2 & !l1 == 0);
            if coprime || !covered {
                d.push((g1, l1));
            } else {
                st.pairs_chain_skipped += 1;
            }
        }
        // Old pairs whose lcm `h` divides strictly on both sides.
        let lm = &self.lm;
        let mut dropped = 0u64;
        self.pairs.retain(|p| match p.kind {
            PairKind::Field(..) => true,
            PairKind::Critical(i, j) => {
                let keep = lh & !p.lcm != 0 || (lm[i] | lh) == p.lcm || (lm[j] | lh) == p.lcm;
                if !keep {
                    dropped += 1;
                }
                keep
            }
        });
        st.pairs_chain_skipped += dropped;
        // Product criterion on what survived.
        for (g, l) in d {
            if lh & self.lm[g] == 0 {
                st.pairs_product_skipped += 1;
            } else {
                self.pairs.push(Pair {
                    kind: PairKind::Critical(g, h),
                    lcm: l,
                    deg: l.count_ones(),
                });
            }
        }
        for g in 0..h {
            if self.active[g] && lh & !self.lm[g] == 0 {
                self.active[g] = false;
            }
        }
        self.active[h] = true;
    }

    /// Active basis elements whose leading monomial divides `m`, the
    /// shortest first.
    fn reducer_for(&self, m: u64, active: &[usize], st: &mut F4Stats) -> Option<usize> {
        let mut best: Option<usize> = None;
        for &g in active {
            st.divisor_tests += 1;
            if self.lm[g] & !m == 0
                && best.is_none_or(|b| self.polys[g].terms.len() < self.polys[b].terms.len())
            {
                best = Some(g);
            }
        }
        best
    }
}

/// **Compute the reduced Gröbner basis** of the ideal `initial` generates
/// in `F_2[v]/(v² − v)` by F4, within an optional wall-clock budget.
///
/// On a budget or size overrun the returned set generates the same ideal
/// but is not a Gröbner basis, and the stats say so.
pub fn groebner_basis_f4(
    initial: Vec<F2BoolPoly>,
    n_vars: usize,
    budget: Option<Duration>,
) -> (Vec<F2BoolPoly>, F4Stats) {
    let started = Instant::now();
    let deadline = budget.map(|b| started + b);
    let mut st = F4Stats::default();
    let one = || vec![F2BoolPoly::one(n_vars)];
    let finish = |basis: Vec<F2BoolPoly>, mut st: F4Stats| {
        st.basis_len = basis.len() as u64;
        st.wall_ns = started.elapsed().as_nanos() as u64;
        (basis, st)
    };

    let inputs: Vec<F2BoolPoly> = initial.into_iter().filter(|p| !p.is_zero()).collect();
    if inputs.iter().any(is_one) {
        return finish(one(), st);
    }
    for p in &inputs {
        st.max_poly_degree = st.max_poly_degree.max(degree(p));
    }

    // The initial echelon: distinct leading monomials to start from.
    let t = Instant::now();
    let cols = Columns::from_monomials(inputs.iter().flat_map(|p| p.terms.iter().map(|t| t.mask)));
    let rows: Vec<Row> = inputs.iter().map(|p| cols.pack(p)).collect();
    st.build_ns += t.elapsed().as_nanos() as u64;
    let t = Instant::now();
    let Some(pivots) = echelon(rows, cols.monos.len(), &mut st.word_xors, deadline) else {
        st.timed_out = true;
        st.eliminate_ns += t.elapsed().as_nanos() as u64;
        return finish(inputs, st);
    };
    st.eliminate_ns += t.elapsed().as_nanos() as u64;
    let mut start: Vec<F2BoolPoly> = pivots.iter().map(|(_, r)| cols.unpack(r, n_vars)).collect();
    if start.iter().any(is_one) {
        return finish(one(), st);
    }
    start.sort_by(|a, b| cmp_mono(a.lt().unwrap(), b.lt().unwrap()));

    let mut s = State {
        n_vars,
        polys: Vec::new(),
        lm: Vec::new(),
        active: Vec::new(),
        pairs: Vec::new(),
    };
    for p in start {
        s.insert(p, &mut st);
    }

    while !s.pairs.is_empty() {
        if deadline.is_some_and(|d| Instant::now() >= d) {
            st.timed_out = true;
            break;
        }
        let d = s.pairs.iter().map(|p| p.deg).min().unwrap();
        let (selected, rest): (Vec<Pair>, Vec<Pair>) = s.pairs.drain(..).partition(|p| p.deg == d);
        s.pairs = rest;
        st.steps += 1;
        st.degree_reached = st.degree_reached.max(d);

        let t = Instant::now();
        // The rows the step reduces: both halves of every critical pair
        // (their common leading monomial is the lcm, which one half will
        // pivot and the other lose), and every field product.
        let mut seen_rows: FxSet<(u64, usize)> = FxSet::default();
        let mut half_rows: Vec<F2BoolPoly> = Vec::new();
        let mut field_rows: Vec<F2BoolPoly> = Vec::new();
        let mut lcm_columns: FxSet<u64> = FxSet::default();
        for p in &selected {
            match p.kind {
                PairKind::Critical(i, j) => {
                    st.pairs_reduced += 1;
                    lcm_columns.insert(p.lcm);
                    for g in [i, j] {
                        let mult = p.lcm & !s.lm[g];
                        if seen_rows.insert((mult, g)) {
                            half_rows.push(s.polys[g].mul_mono(F2BoolMono::from_mask(mult)));
                        }
                    }
                }
                PairKind::Field(g, v) => {
                    st.field_pairs_reduced += 1;
                    // A field multiplier lies inside `LM(g)` and a half's is
                    // disjoint from it, so the two kinds of key never meet.
                    let mult = 1u64 << v;
                    if seen_rows.insert((mult, g)) {
                        let prod = s.polys[g].mul_mono(F2BoolMono::from_mask(mult));
                        if !prod.is_zero() {
                            field_rows.push(prod);
                        }
                    }
                }
            }
        }

        // Symbolic preprocessing.  Every monomial other than an S-pair's
        // lcm is examined once; a divisible one gets a reducer led by it.
        let active: Vec<usize> = (0..s.polys.len()).filter(|&g| s.active[g]).collect();
        let mut examined: FxSet<u64> = lcm_columns.clone();
        let mut no_divisor: FxSet<u64> = FxSet::default();
        let mut queue: Vec<u64> = Vec::new();
        for p in half_rows.iter().chain(field_rows.iter()) {
            for t in &p.terms {
                if examined.insert(t.mask) {
                    queue.push(t.mask);
                }
            }
        }
        let mut reducers: Vec<F2BoolPoly> = Vec::new();
        while let Some(m) = queue.pop() {
            match s.reducer_for(m, &active, &mut st) {
                Some(g) => {
                    let r = s.polys[g].mul_mono(F2BoolMono::from_mask(m & !s.lm[g]));
                    debug_assert_eq!(
                        r.lt().map(|t| t.mask),
                        Some(m),
                        "a reducer must lead with its monomial"
                    );
                    for t in &r.terms {
                        if examined.insert(t.mask) {
                            queue.push(t.mask);
                        }
                    }
                    reducers.push(r);
                }
                None => {
                    no_divisor.insert(m);
                }
            }
        }
        st.reducer_rows += reducers.len() as u64;

        let n_rows = reducers.len() + half_rows.len() + field_rows.len();
        let cols = Columns::from_monomials(examined.iter().copied());
        let words = cols.words() as u64;
        if words * n_rows as u64 > MAX_MATRIX_WORDS {
            st.oversize = true;
            st.build_ns += t.elapsed().as_nanos() as u64;
            s.pairs.extend(selected);
            break;
        }
        st.matrix_rows_max = st.matrix_rows_max.max(n_rows as u64);
        st.matrix_cols_max = st.matrix_cols_max.max(cols.monos.len() as u64);
        st.matrix_rows_sum += n_rows as u64;
        st.peak_matrix_bytes = st.peak_matrix_bytes.max(words * n_rows as u64 * 8);
        // Reducers first, each on a column of its own; then the S-rows by
        // leading monomial, so the second half of a pair meets the first.
        let mut s_rows: Vec<&F2BoolPoly> = half_rows.iter().chain(field_rows.iter()).collect();
        // stable: rows sharing a leading monomial keep their order
        s_rows.sort_by_cached_key(|p| std::cmp::Reverse(mono_key(p.lt().unwrap())));
        for p in reducers.iter().chain(s_rows.iter().copied()) {
            st.max_poly_degree = st.max_poly_degree.max(degree(p));
        }
        let rows: Vec<Row> = reducers
            .iter()
            .chain(s_rows)
            .map(|p| cols.pack(p))
            .collect();
        st.build_ns += t.elapsed().as_nanos() as u64;

        let t = Instant::now();
        let Some(pivots) = echelon(rows, cols.monos.len(), &mut st.word_xors, deadline) else {
            st.timed_out = true;
            st.eliminate_ns += t.elapsed().as_nanos() as u64;
            break;
        };
        st.eliminate_ns += t.elapsed().as_nanos() as u64;

        let mut fresh: Vec<F2BoolPoly> = pivots
            .iter()
            .filter(|(lead, _)| no_divisor.contains(&cols.monos[*lead]))
            .map(|(_, r)| cols.unpack(r, n_vars))
            .collect();
        if fresh.iter().any(is_one) {
            return finish(one(), st);
        }
        if !fresh.is_empty() {
            st.solving_degree = st.solving_degree.max(d);
        }
        fresh.sort_by(|a, b| cmp_mono(a.lt().unwrap(), b.lt().unwrap()));
        for p in fresh {
            st.new_elements += 1;
            s.insert(p, &mut st);
        }
    }
    st.pairs_left = s.pairs.len() as u64;
    if st.timed_out || st.oversize {
        let basis: Vec<F2BoolPoly> = (0..s.polys.len())
            .filter(|&g| s.active[g])
            .map(|g| s.polys[g].clone())
            .collect();
        return finish(basis, st);
    }
    let active: Vec<F2BoolPoly> = (0..s.polys.len())
        .filter(|&g| s.active[g])
        .map(|g| s.polys[g].clone())
        .collect();
    let reduced = interreduce(active, s.n_vars, &mut st);
    finish(reduced, st)
}

/// Keep one element per minimal leading monomial, then reduce every tail
/// by Gauss–Jordan on the symbolic-preprocessing matrix of that minimal
/// basis.  Returns the reduced Gröbner basis, sorted by leading monomial,
/// largest first.
fn interreduce(mut elements: Vec<F2BoolPoly>, n_vars: usize, st: &mut F4Stats) -> Vec<F2BoolPoly> {
    let t = Instant::now();
    elements.sort_by(|a, b| cmp_mono(a.lt().unwrap(), b.lt().unwrap()));
    let mut minimal: Vec<F2BoolPoly> = Vec::new();
    for p in elements {
        let l = p.lt().unwrap().mask;
        if !minimal.iter().any(|q| q.lt().unwrap().mask & !l == 0) {
            minimal.push(p);
        }
    }
    let lms: Vec<u64> = minimal.iter().map(|p| p.lt().unwrap().mask).collect();
    let mut examined: FxSet<u64> = lms.iter().copied().collect();
    let mut queue: Vec<u64> = Vec::new();
    for p in &minimal {
        for t in &p.terms[1..] {
            if examined.insert(t.mask) {
                queue.push(t.mask);
            }
        }
    }
    let mut reducers: Vec<F2BoolPoly> = Vec::new();
    while let Some(m) = queue.pop() {
        let mut best: Option<usize> = None;
        for (k, &l) in lms.iter().enumerate() {
            st.divisor_tests += 1;
            if l & !m == 0 && best.is_none_or(|b| minimal[k].terms.len() < minimal[b].terms.len()) {
                best = Some(k);
            }
        }
        if let Some(k) = best {
            let r = minimal[k].mul_mono(F2BoolMono::from_mask(m & !lms[k]));
            for t in &r.terms {
                if examined.insert(t.mask) {
                    queue.push(t.mask);
                }
            }
            reducers.push(r);
        }
    }
    let cols = Columns::from_monomials(examined.iter().copied());
    let mut rows: Vec<(usize, Row)> = minimal
        .iter()
        .chain(reducers.iter())
        .map(|p| {
            let mut r = cols.pack(p);
            let lead = r.lead().expect("non-zero");
            (lead, r)
        })
        .collect();
    let n_rows = rows.len() as u64;
    st.matrix_rows_max = st.matrix_rows_max.max(n_rows);
    st.matrix_cols_max = st.matrix_cols_max.max(cols.monos.len() as u64);
    st.matrix_rows_sum += n_rows;
    st.peak_matrix_bytes = st.peak_matrix_bytes.max(cols.words() as u64 * n_rows * 8);
    st.build_ns += t.elapsed().as_nanos() as u64;

    // Every row already leads on a column of its own, so the forward pass
    // is empty; the backward pass clears each pivot column from every row
    // above it, rightmost pivot first.
    let t = Instant::now();
    rows.sort_by_key(|(lead, _)| *lead);
    for k in (0..rows.len()).rev() {
        let (lead, from) = (rows[k].0, rows[k].0 / 64);
        let (bit_word, bit) = (lead / 64, 1u64 << (lead % 64));
        let (above, rest) = rows.split_at_mut(k);
        let pivot = &rest[0].1;
        for (_, row) in above.iter_mut() {
            if row.bits[bit_word] & bit != 0 {
                let to = pivot.end;
                for (a, b) in row.bits[from..to].iter_mut().zip(&pivot.bits[from..to]) {
                    *a ^= *b;
                }
                st.word_xors += (to - from) as u64;
                row.end = row.end.max(to);
            }
        }
    }
    st.eliminate_ns += t.elapsed().as_nanos() as u64;
    let lm_set: HashSet<u64> = lms.iter().copied().collect();
    let mut out: Vec<F2BoolPoly> = rows
        .iter()
        .filter(|(lead, _)| lm_set.contains(&cols.monos[*lead]))
        .map(|(_, r)| cols.unpack(r, n_vars))
        .collect();
    out.sort_by(|a, b| cmp_mono(b.lt().unwrap(), a.lt().unwrap()));
    out
}

/// **The solutions of a reduced boolean Gröbner basis**, without
/// enumerating `{0,1}^n`.
///
/// Every variable is either the leading monomial of a linear element
/// `v_p + Σ c_q v_q + c` (with every `v_q` free) or free itself, so an
/// assignment of the free variables fixes the point.  The number of free
/// variables is at most the number of solutions less one, since the
/// basis of a radical zero-dimensional ideal has as many standard
/// monomials as the ideal has points.  Returns `None` above `max_free`
/// free variables, which on a reduced basis means the ideal has more than
/// `2^max_free` solutions, or the input was not a reduced basis.
///
/// `tests` counts monomial tests, one per term evaluated.
pub fn solutions_from_reduced_basis(
    gb: &[F2BoolPoly],
    n_vars: usize,
    max_free: usize,
    tests: &mut u64,
) -> Option<Vec<u64>> {
    if gb.iter().any(is_one) {
        return Some(Vec::new());
    }
    let mut linear_of = vec![None; n_vars];
    for (k, g) in gb.iter().enumerate() {
        let l = g.lt()?.mask;
        if l.count_ones() == 1 {
            linear_of[l.trailing_zeros() as usize] = Some(k);
        }
    }
    let free: Vec<usize> = (0..n_vars).filter(|&v| linear_of[v].is_none()).collect();
    if free.len() > max_free {
        return None;
    }
    let pivots: Vec<(usize, usize)> = (0..n_vars)
        .filter_map(|v| linear_of[v].map(|k| (v, k)))
        .collect();
    let mut out = Vec::new();
    for a in 0u64..(1u64 << free.len()) {
        let mut point = 0u64;
        for (bit, &v) in free.iter().enumerate() {
            if (a >> bit) & 1 == 1 {
                point |= 1u64 << v;
            }
        }
        for &(v, k) in &pivots {
            // The tail involves free variables and the constant only.
            *tests += gb[k].terms.len() as u64;
            if gb[k].eval(point) == 1 {
                point |= 1u64 << v;
            }
        }
        let mut ok = true;
        for g in gb {
            *tests += g.terms.len() as u64;
            if g.eval(point) != 0 {
                ok = false;
                break;
            }
        }
        if ok {
            out.push(point);
        }
    }
    Some(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::pq_groebner_f2::{groebner_basis_f2, reduce, spoly};
    use rand::rngs::StdRng;
    use rand::{Rng, SeedableRng};

    fn poly(masks: &[u64], n: usize) -> F2BoolPoly {
        F2BoolPoly::from_monos(masks.iter().map(|&m| F2BoolMono::from_mask(m)).collect(), n)
    }

    fn brute_force(eqs: &[F2BoolPoly], n: usize) -> Vec<u64> {
        (0u64..1 << n)
            .filter(|v| eqs.iter().all(|e| e.eval(*v) == 0))
            .collect()
    }

    fn standard_monomials(gb: &[F2BoolPoly], n: usize) -> u64 {
        let lms: Vec<u64> = gb.iter().filter_map(|p| p.lt()).map(|m| m.mask).collect();
        (0u64..1 << n)
            .filter(|&m| !lms.iter().any(|&l| l & !m == 0))
            .count() as u64
    }

    /// The Gröbner-basis certificate, checked directly: every
    /// S-polynomial and every field product reduces to zero.
    fn is_boolean_groebner_basis(gb: &[F2BoolPoly]) -> bool {
        for (i, g) in gb.iter().enumerate() {
            let l = g.lt().unwrap().mask;
            let mut bits = l;
            while bits != 0 {
                let v = bits.trailing_zeros();
                bits &= bits - 1;
                if !reduce(&g.mul_mono(F2BoolMono::from_mask(1 << v)), gb).is_zero() {
                    return false;
                }
            }
            for h in &gb[i + 1..] {
                if !reduce(&spoly(g, h), gb).is_zero() {
                    return false;
                }
            }
        }
        true
    }

    fn random_quadratic(n: usize, m: usize, rng: &mut StdRng) -> Vec<F2BoolPoly> {
        (0..m)
            .map(|_| {
                let mut monos = Vec::new();
                for i in 0..n {
                    for j in 0..i {
                        if rng.gen_bool(0.5) {
                            monos.push((1u64 << i) | (1 << j));
                        }
                    }
                    if rng.gen_bool(0.5) {
                        monos.push(1u64 << i);
                    }
                }
                if rng.gen_bool(0.5) {
                    monos.push(0);
                }
                poly(&monos, n)
            })
            .collect()
    }

    /// **The field pairs are what makes it a boolean basis.**  On
    /// `v_0v_1 + v_0 + v_1`, whose only root is `(0, 0)`, the basis is
    /// `{v_0, v_1}`: `v_0·g = v_0` and `v_1·g = v_1`.  The repository's
    /// Buchberger used to return the generator itself — three standard
    /// monomials for one solution — and was closed under the field
    /// equations after this engine was written (34154ed9); the two now
    /// agree here, and the ledger's §14–§17 rows record which engine
    /// they measured.
    #[test]
    fn the_field_pairs_close_the_toy_ideal() {
        let g = poly(&[3, 1, 2], 2);
        let (gb, st) = groebner_basis_f4(vec![g.clone()], 2, None);
        let mut lts: Vec<u64> = gb.iter().map(|p| p.lt().unwrap().mask).collect();
        lts.sort();
        assert_eq!(lts, vec![1, 2]);
        assert!(gb.iter().all(|p| p.terms.len() == 1), "{gb:?}");
        assert_eq!(standard_monomials(&gb, 2), 1);
        assert!(st.field_pairs_reduced > 0);
        let buchberger = groebner_basis_f2(vec![g], 2);
        assert_eq!(
            standard_monomials(&buchberger, 2),
            1,
            "Buchberger closes under the field equations too"
        );
    }

    /// **Certified on random systems**: the output is a Gröbner basis of
    /// the boolean ideal (every S-polynomial and field product reduces to
    /// zero), it has exactly as many standard monomials as the system has
    /// solutions, an inconsistent system gives `{1}`, and the extraction
    /// recovers every solution and nothing else.
    #[test]
    fn the_basis_is_a_certified_boolean_groebner_basis() {
        let mut rng = StdRng::seed_from_u64(20260922);
        let (mut consistent, mut inconsistent) = (0, 0);
        for trial in 0..60 {
            let n = 4 + trial % 7;
            let m = n - 2 + trial % 5;
            let eqs = random_quadratic(n, m, &mut rng);
            let (gb, st) = groebner_basis_f4(eqs.clone(), n, None);
            assert!(!st.timed_out && !st.oversize);
            let sols = brute_force(&eqs, n);
            assert!(is_boolean_groebner_basis(&gb), "trial {trial}: not closed");
            assert_eq!(
                standard_monomials(&gb, n),
                sols.len() as u64,
                "trial {trial}"
            );
            if sols.is_empty() {
                inconsistent += 1;
                assert_eq!(gb.len(), 1);
                assert!(is_one(&gb[0]));
            } else {
                consistent += 1;
            }
            let mut tests = 0;
            let mut got = solutions_from_reduced_basis(&gb, n, 24, &mut tests).unwrap();
            got.sort_unstable();
            assert_eq!(got, sols, "trial {trial}: extraction");
            // Every generator lies in the ideal the basis generates.
            for e in &eqs {
                assert!(
                    reduce(e, &gb).is_zero(),
                    "trial {trial}: a generator escaped"
                );
            }
        }
        assert!(
            consistent > 5 && inconsistent > 5,
            "{consistent} / {inconsistent}"
        );
    }

    /// **Batched Buchberger is Buchberger.**  Wherever the Buchberger
    /// output is certified a boolean basis — everywhere, since it closes
    /// under the field equations — the reduced bases must coincide
    /// polynomial for polynomial: the reduced Gröbner basis of an ideal
    /// is unique.
    #[test]
    fn f4_and_buchberger_agree_where_buchberger_is_certified() {
        use crate::cryptanalysis::ic_boundary::random_binary_instance;
        use crate::cryptanalysis::pq_descent_symbolic::descend;
        let mut rng = StdRng::seed_from_u64(5);
        let mut compared = 0;
        for &(n, np, seed) in &[(7u32, 4u32, 1u64), (9, 5, 2), (11, 6, 3)] {
            let inst = random_binary_instance(n, seed, 1 << 20).unwrap();
            let words: Vec<u64> = (0..np).map(|k| 1u64 << k).collect();
            for _ in 0..4 {
                let x_r = rng.gen::<u64>() & ((1u64 << n) - 1);
                let sys = descend(&inst.gf, inst.b, x_r, &words, 2).unwrap();
                let bb = groebner_basis_f2(sys.equations.clone(), sys.n_vars);
                if !is_boolean_groebner_basis(&bb) {
                    continue;
                }
                let (f4, _) = groebner_basis_f4(sys.equations.clone(), sys.n_vars, None);
                assert_eq!(f4, bb, "n = {n}, n' = {np}: the reduced bases differ");
                compared += 1;
            }
        }
        assert!(compared >= 8, "only {compared} systems were comparable");
    }

    /// The extraction enumerates free variables only.  The standard
    /// monomials include `1` and every free variable, and there are as
    /// many of them as solutions, so `1 + #free ≤ #solutions`.
    #[test]
    fn extraction_enumerates_only_the_free_variables() {
        let mut rng = StdRng::seed_from_u64(99);
        let mut consistent = 0;
        for _ in 0..20 {
            let eqs = random_quadratic(9, 9, &mut rng);
            let (gb, _) = groebner_basis_f4(eqs.clone(), 9, None);
            let sols = brute_force(&eqs, 9).len() as u64;
            let mut tests = 0;
            let got = solutions_from_reduced_basis(&gb, 9, 24, &mut tests).unwrap();
            assert_eq!(got.len() as u64, sols);
            if sols > 0 {
                consistent += 1;
                let free = (0..9)
                    .filter(|&v| !gb.iter().any(|g| g.lt().unwrap().mask == 1u64 << v))
                    .count() as u64;
                assert!(free < sols, "{free} free variables for {sols} solutions");
            }
        }
        assert!(consistent > 3);
    }

    /// A budget is honoured and reported, not silently turned into a
    /// wrong basis.
    #[test]
    fn the_budget_is_reported() {
        let mut rng = StdRng::seed_from_u64(3);
        let eqs = random_quadratic(18, 17, &mut rng);
        let (_, st) = groebner_basis_f4(eqs, 18, Some(Duration::from_nanos(1)));
        assert!(st.timed_out);
    }
}
