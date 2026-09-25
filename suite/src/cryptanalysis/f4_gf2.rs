//! # Fast `F_2` Macaulay kernels for the Boolean matrix-F4 engine.
//!
//! [`super::koblitz_groebner`] reduces every node of its splitting search
//! with one or two Macaulay matrices.  The matrices are small — a few
//! hundred rows over a few hundred columns on the frozen ladder — and
//! there are tens of thousands of them per relation, so the reference
//! implementation's cost was never the elimination alone: building a
//! matrix (a hash map from monomial to column, two sorts, one heap row per
//! product) and reading every reduced row back into a sorted polynomial
//! cost as much again.  This module removes both, and reduces what is left
//! with less work, without changing a single answer.
//!
//! ## Columns without hashing
//!
//! A column is a Boolean monomial of degree at most `D` over the variables
//! that occur.  Its position in descending DegRevLex order is computable:
//! within one degree, DegRevLex descending is ascending integer order of
//! the mask, which is colex order of the variable subset, so
//!
//! ```text
//!     rank(x) = base[deg x] + Σ_i C(c_i, i)      (c_1 < c_2 < … compact indices)
//! ```
//!
//! is monotone in the column order.  One stamped array indexed by rank
//! replaces the hash map, and a scan (or a sort of the distinct ranks when
//! the rank space is sparse) replaces both sorts.  Rows are written by XOR,
//! so terms that collide under the Boolean product cancel with no sort.
//!
//! ## Deciding without the full reduction
//!
//! The splitting solver reads exactly two facts off a reduction: does the
//! row space contain the constant `1`, and which rows have collapsed to
//! `v` or `v + 1`.  Both live in the span of the degree-≤1 columns, which
//! DegRevLex puts last.  After forward elimination over the high columns
//! alone, the rows left with a zero high part span precisely the row space
//! intersected with that span (any combination that involves a pivot row
//! keeps a nonzero entry in that pivot's column), so the reduced echelon
//! form of those rows — at most 65 columns wide, one `u128` each — is the
//! low block of the full reduced echelon form, and answers both questions
//! identically.  No back substitution over the high columns and no
//! polynomial readback is performed.
//!
//! ## Only the variables that occur
//!
//! The reference builder shifts every equation by monomials over *all*
//! `n_vars` variables, including the ones the search has already
//! substituted away.  A row whose multiplier contains such a variable has
//! every monomial divisible by it, so those rows occupy columns no other
//! row touches and cannot contribute a linear consequence in the remaining
//! variables (a constant `1` among them would already be a refutation one
//! degree lower, which the other rows contain).  They are therefore not
//! built.  The size caps are nevertheless applied in the reference units:
//! a nonempty row with slack `s = D − deg p − deg u` stands for
//! `Σ_{j ≤ s} C(N, j)` reference rows (`N` non-occurring variables), and a
//! column whose largest slack is `s` for as many reference columns, so a
//! matrix is declared oversize exactly when the reference builder would
//! have refused it and the search takes the same path.
//!
//! ## What is exact
//!
//! [`decide`] returns the same refutation flag and the same forced
//! assignments, in the same order, as reading them off the reference
//! reduced rows; [`matrix_rows`] returns the reference reduced rows
//! bit-for-bit.  Both report the reference row and column counts.  The
//! 64-bit word XORs they report are their own, which is the point.

use std::cell::RefCell;
use std::sync::OnceLock;

use super::fx_hash::FxMap;
use super::pq_groebner_f2::{F2BoolMono, F2BoolPoly};

/// Size caps of one Macaulay matrix, in the reference builder's units:
/// nonempty rows over all `n_vars` variables, and distinct monomials.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct MacaulayCaps {
    /// Largest number of nonempty rows accepted.
    pub max_rows: usize,
    /// Largest number of distinct monomials accepted.
    pub max_cols: usize,
}

/// What the reduced rows of one Macaulay matrix decide.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Decision {
    /// The row space contains the constant `1`.
    pub refuted: bool,
    /// Rows of the form `v` (`false`) or `v + 1` (`true`), in increasing
    /// variable order — the order of their pivots.  Empty when `refuted`:
    /// once `1` is in the ideal every `v = v·1` is too, including variables
    /// the system no longer contains, and nothing reads them.
    pub forced: Vec<(u32, bool)>,
}

impl Decision {
    /// A refutation or at least one forced variable.
    pub fn is_decisive(&self) -> bool {
        self.refuted || !self.forced.is_empty()
    }
}

/// Counters of one kernel call, in the fields of
/// [`super::koblitz_groebner::F4Profile`].
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct KernelCounters {
    /// A matrix was built (possibly empty).  `false` for an empty input
    /// system and for an oversize matrix.
    pub built: bool,
    /// The matrix exceeded the caps.
    pub oversize: bool,
    /// Rows in reference units.
    pub rows: u64,
    /// Columns in reference units.
    pub cols: u64,
    /// Rows actually eliminated.
    pub eliminated_rows: u64,
    /// Columns actually eliminated.
    pub eliminated_cols: u64,
    /// 64-bit word XORs performed by this kernel.
    pub word_ops: u64,
    /// Nanoseconds building the matrix.
    pub build_ns: u128,
    /// Nanoseconds eliminating.
    pub reduce_ns: u128,
    /// Nanoseconds extracting the answer.
    pub readback_ns: u128,
}

/// Rank spaces up to this many entries are indexed directly; larger ones
/// fall back to a hash map.
const RANK_LIMIT: u64 = 1 << 20;

/// `C(n, k)` for `n, k ≤ 64`, saturating at `u64::MAX`.
fn binom() -> &'static [[u64; 65]; 65] {
    static TABLE: OnceLock<Box<[[u64; 65]; 65]>> = OnceLock::new();
    TABLE.get_or_init(|| {
        let mut t = Box::new([[0u64; 65]; 65]);
        for n in 0..=64 {
            t[n][0] = 1;
            for k in 1..=n {
                let above = if k < n { t[n - 1][k] } else { 0 };
                t[n][k] = t[n - 1][k - 1].saturating_add(above);
            }
        }
        t
    })
}

/// `Σ_{j ≤ s} C(n, j)`: the multipliers of degree at most `s` over `n`
/// variables.
fn upto(n: usize, s: usize) -> u64 {
    let b = binom();
    (0..=s.min(n)).fold(0u64, |acc, j| acc.saturating_add(b[n][j]))
}

/// Mask of the variables `0 .. n_vars`.
fn all_vars(n_vars: usize) -> u64 {
    if n_vars >= 64 {
        u64::MAX
    } else {
        (1u64 << n_vars) - 1
    }
}

/// Highest term degree of `p` (0 for the zero polynomial).
fn poly_degree(p: &F2BoolPoly) -> u32 {
    p.terms
        .iter()
        .map(|t| t.mask.count_ones())
        .max()
        .unwrap_or(0)
}

/// Every subset of `bits` (single-bit masks) of size at most `k`, as
/// `(mask, size)`, the empty set first.
fn for_each_multiplier(bits: &[u64], k: usize, mut f: impl FnMut(u64, usize)) {
    f(0, 0);
    let v = bits.len();
    let mut idx = [0usize; 64];
    for j in 1..=k.min(v) {
        for (t, slot) in idx.iter_mut().enumerate().take(j) {
            *slot = t;
        }
        loop {
            let mask = idx[..j].iter().fold(0u64, |m, &i| m | bits[i]);
            f(mask, j);
            // Next j-combination of 0..v in lexicographic order.
            let mut t = j;
            let mut advanced = false;
            while t > 0 {
                t -= 1;
                if idx[t] < v - j + t {
                    idx[t] += 1;
                    for s in t + 1..j {
                        idx[s] = idx[s - 1] + 1;
                    }
                    advanced = true;
                    break;
                }
            }
            if !advanced {
                break;
            }
        }
    }
}

/// Per-thread buffers, reused across calls so a reduction allocates
/// nothing once warm.
#[derive(Default)]
struct Scratch {
    /// Provisional column key of every monomial occurrence, row-major.
    prov: Vec<u32>,
    /// Start of each candidate row in `prov`; one extra entry at the end.
    row_start: Vec<u32>,
    /// Slack `D − deg p − deg u` of each candidate row.
    row_slack: Vec<u8>,
    /// Rank-space stamps: `stamp[r] == generation` marks rank `r` seen.
    stamp: Vec<u32>,
    generation: u32,
    /// Rank (or hash id) → distinct index while building, then → column.
    remap: Vec<u32>,
    /// Distinct monomials: `(rank or id, mask, largest row slack)`.
    distinct: Vec<(u32, u64, u8)>,
    /// Column → monomial mask, in column order.
    col_mask: Vec<u64>,
    /// Row-major bit matrix of the nonempty rows.
    matrix: Vec<u64>,
    /// Slack of each stored row.
    stored_slack: Vec<u8>,
    /// Per-slack OR of the stored rows (reference column count).
    class_or: Vec<u64>,
    /// Elimination: leading-column buckets.
    head: Vec<u32>,
    next: Vec<u32>,
    pivots: Vec<u32>,
    low_rows: Vec<u32>,
    low: Vec<u128>,
    /// Hash strategy for rank spaces above [`RANK_LIMIT`].
    hash: FxMap<u64, u32>,
    /// Sorting buffer for the exact oversize count.
    row_buf: Vec<u64>,
}

thread_local! {
    static SCRATCH: RefCell<Scratch> = RefCell::new(Scratch::default());
}

/// Shape of a built matrix.
struct Built {
    rows: usize,
    cols: usize,
    stride: usize,
    low_start: usize,
    ref_rows: u64,
    ref_cols: u64,
}

enum BuildOutcome {
    /// No nonempty row: the reference returns no rows either.
    Empty,
    Oversize,
    Built(Built),
}

/// The multiplier set, in both modes.
struct Layout {
    /// Variables multipliers range over, as single-bit masks.
    bits: Vec<u64>,
    /// Variables the reference multiplies by that are not in `bits`.
    missing: usize,
    /// Compact index of each variable in `bits` (by bit position).
    pos: [u8; 64],
    /// Rank offset of each degree, `base[d]`.
    base: [u64; 65],
    /// Size of the rank space.
    rank_space: u64,
}

impl Layout {
    fn new(occurring: u64, n_vars: usize, degree: u32) -> Self {
        let bits: Vec<u64> = (0..64u32)
            .filter(|b| occurring >> b & 1 == 1)
            .map(|b| 1u64 << b)
            .collect();
        let mut pos = [0u8; 64];
        for (i, b) in bits.iter().enumerate() {
            pos[b.trailing_zeros() as usize] = i as u8;
        }
        let v = bits.len();
        let dm = (degree as usize).min(v);
        let b = binom();
        let mut base = [0u64; 65];
        // Highest degree first: base[dm] = 0, base[d] = base[d + 1] + C(v, d + 1).
        for d in (0..dm).rev() {
            base[d] = base[d + 1].saturating_add(b[v][d + 1]);
        }
        let rank_space = base[0].saturating_add(1);
        let missing = (all_vars(n_vars) & !occurring).count_ones() as usize;
        Layout {
            bits,
            missing,
            pos,
            base,
            rank_space,
        }
    }

    #[inline]
    fn rank(&self, x: u64) -> u32 {
        let b = binom();
        let d = x.count_ones() as usize;
        let mut r = self.base[d];
        let mut m = x;
        let mut k = 1usize;
        while m != 0 {
            let bit = m.trailing_zeros() as usize;
            r += b[self.pos[bit] as usize][k];
            k += 1;
            m &= m - 1;
        }
        r as u32
    }
}

/// Build the Macaulay matrix of `polys` at `degree` into the scratch.
///
/// With `compact`, multipliers range over the variables occurring in the
/// row-generating equations; otherwise over all `n_vars` (the reference
/// matrix exactly).  Either way the caps are enforced in reference units.
fn build(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
    compact: bool,
    caps: MacaulayCaps,
    s: &mut Scratch,
) -> BuildOutcome {
    let generating: Vec<(&F2BoolPoly, u32)> = polys
        .iter()
        .filter(|p| !p.is_zero())
        .map(|p| (p, poly_degree(p)))
        .filter(|&(_, d)| d <= degree)
        .collect();
    let term_vars = generating
        .iter()
        .flat_map(|(p, _)| p.terms.iter())
        .fold(0u64, |acc, t| acc | t.mask);
    let occurring = if compact {
        term_vars
    } else {
        term_vars | all_vars(n_vars)
    };
    let layout = Layout::new(occurring, n_vars, degree);
    let v = layout.bits.len();
    let missing = layout.missing;

    // Reference rows, before cancellation: an upper bound on the count.
    let b = binom();
    let mut rows_bound = 0u64;
    for &(_, pdeg) in &generating {
        let k = (degree - pdeg) as usize;
        for j in 0..=k.min(v) {
            rows_bound = rows_bound.saturating_add(b[v][j].saturating_mul(upto(missing, k - j)));
        }
    }
    if rows_bound > caps.max_rows as u64
        && exact_reference_rows_exceed(&generating, &layout, degree, caps.max_rows as u64, s)
    {
        return BuildOutcome::Oversize;
    }

    // Candidate rows: provisional column keys of every product term.
    s.prov.clear();
    s.row_start.clear();
    s.row_slack.clear();
    s.distinct.clear();
    let use_rank = layout.rank_space <= RANK_LIMIT;
    if use_rank {
        let r = layout.rank_space as usize;
        if s.stamp.len() < r {
            s.stamp.resize(r, 0);
            s.remap.resize(r, 0);
        }
        s.generation = s.generation.wrapping_add(1);
        if s.generation == 0 {
            s.stamp.iter_mut().for_each(|x| *x = 0);
            s.generation = 1;
        }
    } else {
        s.hash.clear();
    }
    let generation = s.generation;
    for &(p, pdeg) in &generating {
        let k = (degree - pdeg) as usize;
        for_each_multiplier(&layout.bits, k, |u, du| {
            let slack = (k - du) as u8;
            s.row_start.push(s.prov.len() as u32);
            s.row_slack.push(slack);
            for t in &p.terms {
                let x = t.mask | u;
                let (key, di) = if use_rank {
                    let r = layout.rank(x) as usize;
                    if s.stamp[r] != generation {
                        s.stamp[r] = generation;
                        s.remap[r] = s.distinct.len() as u32;
                        s.distinct.push((r as u32, x, slack));
                    }
                    (r as u32, s.remap[r] as usize)
                } else {
                    let next_id = s.distinct.len() as u32;
                    let id = *s.hash.entry(x).or_insert(next_id);
                    if id == next_id {
                        s.distinct.push((id, x, slack));
                    }
                    (id, id as usize)
                };
                let entry = &mut s.distinct[di];
                entry.2 = entry.2.max(slack);
                s.prov.push(key);
            }
        });
    }
    s.row_start.push(s.prov.len() as u32);
    let candidates = s.row_slack.len();
    if s.distinct.is_empty() || candidates == 0 {
        return BuildOutcome::Empty;
    }

    // Reference columns, before cancellation: an upper bound.
    let cols_bound = if missing == 0 {
        s.distinct.len() as u64
    } else {
        s.distinct.iter().fold(0u64, |acc, e| {
            acc.saturating_add(upto(missing, e.2 as usize))
        })
    };
    if cols_bound > caps.max_cols as u64 && exact_reference_cols_exceed(missing, caps, s) {
        return BuildOutcome::Oversize;
    }

    // Column order: descending DegRevLex.
    let n_cols = s.distinct.len();
    s.col_mask.clear();
    s.col_mask.resize(n_cols, 0);
    if use_rank {
        let r = layout.rank_space as usize;
        if r <= 8 * n_cols + 64 {
            let mut next = 0u32;
            for rank in 0..r {
                if s.stamp[rank] == generation {
                    s.remap[rank] = next;
                    next += 1;
                }
            }
        } else {
            s.distinct.sort_unstable_by_key(|e| e.0);
            for (col, e) in s.distinct.iter().enumerate() {
                s.remap[e.0 as usize] = col as u32;
            }
        }
        for e in &s.distinct {
            s.col_mask[s.remap[e.0 as usize] as usize] = e.1;
        }
    } else {
        s.distinct
            .sort_unstable_by_key(|e| (std::cmp::Reverse(e.1.count_ones()), e.1));
        if s.remap.len() < n_cols {
            s.remap.resize(n_cols, 0);
        }
        for (col, e) in s.distinct.iter().enumerate() {
            s.remap[e.0 as usize] = col as u32;
            s.col_mask[col] = e.1;
        }
    }
    let low_start = s
        .col_mask
        .iter()
        .rposition(|m| m.count_ones() >= 2)
        .map_or(0, |i| i + 1);

    // Fill.  XOR cancels colliding products; empty rows are dropped.
    let stride = n_cols.div_ceil(64);
    s.matrix.clear();
    s.matrix.resize(candidates * stride, 0);
    s.stored_slack.clear();
    let classes = degree as usize + 1;
    s.class_or.clear();
    s.class_or.resize(classes * stride, 0);
    let mut stored = 0usize;
    let mut ref_rows = 0u64;
    for row in 0..candidates {
        let dst = stored * stride;
        let (lo, hi) = (s.row_start[row] as usize, s.row_start[row + 1] as usize);
        for &key in &s.prov[lo..hi] {
            let c = s.remap[key as usize] as usize;
            s.matrix[dst + c / 64] ^= 1u64 << (c % 64);
        }
        let words = &s.matrix[dst..dst + stride];
        if words.iter().all(|&w| w == 0) {
            continue;
        }
        let slack = s.row_slack[row];
        let class = &mut s.class_or[slack as usize * stride..(slack as usize + 1) * stride];
        for (acc, &w) in class.iter_mut().zip(words) {
            *acc |= w;
        }
        s.stored_slack.push(slack);
        ref_rows = ref_rows.saturating_add(upto(missing, slack as usize));
        stored += 1;
    }
    if stored == 0 {
        return BuildOutcome::Empty;
    }
    if ref_rows > caps.max_rows as u64 {
        return BuildOutcome::Oversize;
    }
    // Reference columns: each surviving monomial counts once per
    // non-occurring multiplier its largest-slack row admits.
    let mut ref_cols = 0u64;
    let mut covered = vec![0u64; stride];
    for class in (0..classes).rev() {
        let mask = &s.class_or[class * stride..(class + 1) * stride];
        let mut fresh = 0u64;
        for (cov, &m) in covered.iter_mut().zip(mask) {
            fresh += (m & !*cov).count_ones() as u64;
            *cov |= m;
        }
        ref_cols = ref_cols.saturating_add(fresh.saturating_mul(upto(missing, class)));
    }
    if ref_cols > caps.max_cols as u64 {
        return BuildOutcome::Oversize;
    }
    BuildOutcome::Built(Built {
        rows: stored,
        cols: n_cols,
        stride,
        low_start,
        ref_rows,
        ref_cols,
    })
}

/// Exact reference row count for the rare case its bound exceeds the cap:
/// forms each candidate row's monomials, drops those cancelled in pairs,
/// and stops as soon as the count passes `max_rows`.
fn exact_reference_rows_exceed(
    generating: &[(&F2BoolPoly, u32)],
    layout: &Layout,
    degree: u32,
    max_rows: u64,
    s: &mut Scratch,
) -> bool {
    let mut count = 0u64;
    let mut exceeded = false;
    for &(p, pdeg) in generating {
        let k = (degree - pdeg) as usize;
        for_each_multiplier(&layout.bits, k, |u, du| {
            if exceeded {
                return;
            }
            s.row_buf.clear();
            s.row_buf.extend(p.terms.iter().map(|t| t.mask | u));
            s.row_buf.sort_unstable();
            let mut i = 0;
            let mut nonempty = false;
            while i < s.row_buf.len() {
                let mut j = i;
                while j < s.row_buf.len() && s.row_buf[j] == s.row_buf[i] {
                    j += 1;
                }
                if (j - i) % 2 == 1 {
                    nonempty = true;
                    break;
                }
                i = j;
            }
            if nonempty {
                count = count.saturating_add(upto(layout.missing, k - du));
                exceeded = count > max_rows;
            }
        });
        if exceeded {
            return true;
        }
    }
    false
}

/// Exact reference column count for the rare case its bound exceeds the
/// cap, from the candidate rows already in the scratch.
fn exact_reference_cols_exceed(missing: usize, caps: MacaulayCaps, s: &mut Scratch) -> bool {
    // Largest slack of a row in which each distinct monomial survives.
    let mut best: Vec<i16> = vec![-1; s.distinct.len()];
    let use_rank_keys = !s.distinct.is_empty() && s.hash.is_empty();
    let candidates = s.row_slack.len();
    for row in 0..candidates {
        let (lo, hi) = (s.row_start[row] as usize, s.row_start[row + 1] as usize);
        s.row_buf.clear();
        s.row_buf
            .extend(s.prov[lo..hi].iter().map(|&k| u64::from(k)));
        s.row_buf.sort_unstable();
        let slack = s.row_slack[row] as i16;
        let mut i = 0;
        while i < s.row_buf.len() {
            let mut j = i;
            while j < s.row_buf.len() && s.row_buf[j] == s.row_buf[i] {
                j += 1;
            }
            if (j - i) % 2 == 1 {
                let key = s.row_buf[i] as usize;
                let di = if use_rank_keys {
                    s.remap[key] as usize
                } else {
                    key
                };
                best[di] = best[di].max(slack);
            }
            i = j;
        }
    }
    let total = best.iter().filter(|&&b| b >= 0).fold(0u64, |acc, &b| {
        acc.saturating_add(upto(missing, b as usize))
    });
    total > caps.max_cols as u64
}

/// Leading column of `row` at or after word `from`.
#[inline]
fn lead_from(row: &[u64], from: usize) -> Option<usize> {
    row[from..]
        .iter()
        .position(|&w| w != 0)
        .map(|i| (from + i) * 64 + row[from + i].trailing_zeros() as usize)
}

/// `rows[dst] ^= rows[src]` over words `from..stride`.
#[inline]
fn xor_row_suffix(m: &mut [u64], stride: usize, dst: usize, src: usize, from: usize) {
    debug_assert_ne!(dst, src);
    if dst < src {
        let (a, b) = m.split_at_mut(src * stride);
        let d = &mut a[dst * stride + from..dst * stride + stride];
        let p = &b[from..stride];
        for (x, &y) in d.iter_mut().zip(p) {
            *x ^= y;
        }
    } else {
        let (a, b) = m.split_at_mut(dst * stride);
        let p = &a[src * stride + from..src * stride + stride];
        let d = &mut b[from..stride];
        for (x, &y) in d.iter_mut().zip(p) {
            *x ^= y;
        }
    }
}

/// Forward elimination over columns `0 .. stop`.
///
/// Rows are bucketed by leading column, so a column's pivot is found
/// without scanning and only the rows that actually lead there are
/// touched.  Returns the rank; `s.pivots` holds the pivot rows in column
/// order and `s.low_rows` the nonzero rows whose leading column is at or
/// past `stop`.
fn echelon(m: &mut [u64], rows: usize, stride: usize, stop: usize, s: &mut Scratch) -> u64 {
    const NIL: u32 = u32::MAX;
    let mut ops = 0u64;
    s.head.clear();
    s.head.resize(stop, NIL);
    s.next.clear();
    s.next.resize(rows, NIL);
    s.pivots.clear();
    s.low_rows.clear();
    for r in 0..rows {
        match lead_from(&m[r * stride..(r + 1) * stride], 0) {
            Some(c) if c < stop => {
                s.next[r] = s.head[c];
                s.head[c] = r as u32;
            }
            Some(_) => s.low_rows.push(r as u32),
            None => {}
        }
    }
    for c in 0..stop {
        let first = s.head[c];
        if first == NIL {
            continue;
        }
        let piv = first as usize;
        s.pivots.push(first);
        let from = c / 64;
        let mut r = s.next[piv];
        while r != NIL {
            let row = r as usize;
            let after = s.next[row];
            xor_row_suffix(m, stride, row, piv, from);
            ops += (stride - from) as u64;
            match lead_from(&m[row * stride..(row + 1) * stride], from) {
                Some(c2) if c2 < stop => {
                    s.next[row] = s.head[c2];
                    s.head[c2] = r;
                }
                Some(_) => s.low_rows.push(r),
                None => {}
            }
            r = after;
        }
    }
    ops
}

/// Bits `start .. start + width` of `row` (`width ≤ 128`).
fn extract_bits(row: &[u64], start: usize, width: usize) -> u128 {
    let mut out = 0u128;
    let mut got = 0usize;
    while got < width {
        let bit = start + got;
        let w = bit / 64;
        let off = bit % 64;
        let take = (64 - off).min(width - got);
        let chunk = (row[w] >> off)
            & if take == 64 {
                u64::MAX
            } else {
                (1u64 << take) - 1
            };
        out |= u128::from(chunk) << got;
        got += take;
    }
    out
}

/// Reduced echelon form of `rows` (bit `j` = column `j`), pivots in
/// increasing column order; returns the rank, the pivot rows first.
fn rref_u128(rows: &mut [u128], width: usize) -> usize {
    let mut rank = 0usize;
    for col in 0..width {
        let bit = 1u128 << col;
        let Some(p) = (rank..rows.len()).find(|&i| rows[i] & bit != 0) else {
            continue;
        };
        rows.swap(rank, p);
        let pivot = rows[rank];
        for (i, row) in rows.iter_mut().enumerate() {
            if i != rank && *row & bit != 0 {
                *row ^= pivot;
            }
        }
        rank += 1;
        if rank == rows.len() {
            break;
        }
    }
    rank
}

/// Default caps: the reference builder's, with the same environment
/// overrides (read once per call rather than once per row).
pub fn default_caps() -> MacaulayCaps {
    let read = |key: &str, default: usize| {
        std::env::var(key)
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(default)
    };
    MacaulayCaps {
        max_rows: read("F4_F2_MAX_ROWS", 20_000),
        max_cols: read("F4_F2_MAX_COLS", 40_000),
    }
}

/// **Decide** what the degree-`degree` Macaulay matrix of `polys` says:
/// refutation and forced assignments, exactly as the reference reduced
/// rows would.  `None` when the matrix exceeds `caps` (in reference
/// units).
///
/// An empty `polys` builds nothing and reports `built = false`, as the
/// reference does.
pub fn decide(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
    caps: MacaulayCaps,
) -> (Option<Decision>, KernelCounters) {
    let mut k = KernelCounters::default();
    if polys.is_empty() {
        return (Some(Decision::default()), k);
    }
    SCRATCH.with(|cell| {
        let s = &mut *cell.borrow_mut();
        let t0 = std::time::Instant::now();
        let outcome = build(polys, n_vars, degree, true, caps, s);
        k.build_ns = t0.elapsed().as_nanos();
        let b = match outcome {
            BuildOutcome::Oversize => {
                k.oversize = true;
                return (None, k);
            }
            BuildOutcome::Empty => {
                k.built = true;
                return (Some(Decision::default()), k);
            }
            BuildOutcome::Built(b) => b,
        };
        k.built = true;
        k.rows = b.ref_rows;
        k.cols = b.ref_cols;
        k.eliminated_rows = b.rows as u64;
        k.eliminated_cols = b.cols as u64;

        let t1 = std::time::Instant::now();
        let mut m = std::mem::take(&mut s.matrix);
        k.word_ops = echelon(&mut m, b.rows, b.stride, b.low_start, s);
        let width = b.cols - b.low_start;
        s.low.clear();
        for &r in &s.low_rows {
            let r = r as usize;
            s.low.push(extract_bits(
                &m[r * b.stride..(r + 1) * b.stride],
                b.low_start,
                width,
            ));
        }
        s.matrix = m;
        let rank = rref_u128(&mut s.low, width);
        k.reduce_ns = t1.elapsed().as_nanos();

        let t2 = std::time::Instant::now();
        let low_masks = &s.col_mask[b.low_start..];
        let const_bit = match low_masks.last() {
            Some(&0) => 1u128 << (width - 1),
            _ => 0,
        };
        let mut d = Decision::default();
        for &row in &s.low[..rank] {
            if const_bit != 0 && row == const_bit {
                d.refuted = true;
                continue;
            }
            let vars = row & !const_bit;
            if vars.count_ones() == 1 {
                let var = low_masks[vars.trailing_zeros() as usize].trailing_zeros();
                d.forced.push((var, row & const_bit != 0));
            }
        }
        if d.refuted {
            d.forced.clear();
        }
        k.readback_ns = t2.elapsed().as_nanos();
        (Some(d), k)
    })
}

/// **The reference reduced rows**, bit-for-bit: the full reduced echelon
/// form of the degree-`degree` Macaulay matrix of `polys` over all
/// `n_vars` variables, rows in pivot order, each a polynomial with its
/// terms in descending monomial order.  `None` when the matrix exceeds
/// `caps`.
pub fn matrix_rows(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
    caps: MacaulayCaps,
) -> (Option<Vec<F2BoolPoly>>, KernelCounters) {
    let mut k = KernelCounters::default();
    if polys.is_empty() {
        return (Some(Vec::new()), k);
    }
    let n_vars_out = polys[0].n_vars;
    SCRATCH.with(|cell| {
        let s = &mut *cell.borrow_mut();
        let t0 = std::time::Instant::now();
        let outcome = build(polys, n_vars, degree, false, caps, s);
        k.build_ns = t0.elapsed().as_nanos();
        let b = match outcome {
            BuildOutcome::Oversize => {
                k.oversize = true;
                return (None, k);
            }
            BuildOutcome::Empty => {
                k.built = true;
                return (Some(Vec::new()), k);
            }
            BuildOutcome::Built(b) => b,
        };
        k.built = true;
        k.rows = b.ref_rows;
        k.cols = b.ref_cols;
        k.eliminated_rows = b.rows as u64;
        k.eliminated_cols = b.cols as u64;

        let t1 = std::time::Instant::now();
        let mut m = std::mem::take(&mut s.matrix);
        let mut ops = echelon(&mut m, b.rows, b.stride, b.cols, s);
        // Back substitution, last pivot first, so every pivot row is
        // already clear of the later pivot columns when it is used.
        let pivots = std::mem::take(&mut s.pivots);
        let stride = b.stride;
        let lead: Vec<usize> = pivots
            .iter()
            .map(|&r| {
                let r = r as usize;
                lead_from(&m[r * stride..(r + 1) * stride], 0).expect("pivot rows are nonzero")
            })
            .collect();
        for i in (0..pivots.len()).rev() {
            let (src, col) = (pivots[i] as usize, lead[i]);
            let (w, bit) = (col / 64, 1u64 << (col % 64));
            for &dst in &pivots[..i] {
                let dst = dst as usize;
                if m[dst * stride + w] & bit != 0 {
                    xor_row_suffix(&mut m, stride, dst, src, w);
                    ops += (stride - w) as u64;
                }
            }
        }
        k.word_ops = ops;
        k.reduce_ns = t1.elapsed().as_nanos();

        let t2 = std::time::Instant::now();
        let mut out = Vec::with_capacity(pivots.len());
        for &r in &pivots {
            let r = r as usize;
            let mut terms = Vec::new();
            for (w, &word) in m[r * stride..(r + 1) * stride].iter().enumerate() {
                let mut bits = word;
                while bits != 0 {
                    let c = w * 64 + bits.trailing_zeros() as usize;
                    terms.push(F2BoolMono::from_mask(s.col_mask[c]));
                    bits &= bits - 1;
                }
            }
            out.push(F2BoolPoly {
                terms,
                n_vars: n_vars_out,
            });
        }
        s.pivots = pivots;
        s.matrix = m;
        k.readback_ns = t2.elapsed().as_nanos();
        (Some(out), k)
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::koblitz_groebner::{
        build_decomposition_system, matrix_f4_f2_reference, FieldStructure,
    };
    use crate::cryptanalysis::koblitz_index_calculus::{
        build_frobenius_factor_base, find_irreducible, KoblitzCurve,
    };
    use rand::{rngs::StdRng, Rng, SeedableRng};

    const CAPS: MacaulayCaps = MacaulayCaps {
        max_rows: 20_000,
        max_cols: 40_000,
    };

    fn is_constant_one(p: &F2BoolPoly) -> bool {
        p.terms.len() == 1 && p.terms[0].mask == 0
    }

    fn forced_assignment(p: &F2BoolPoly) -> Option<(u32, bool)> {
        let (mut var, mut has_const) = (None, false);
        for t in &p.terms {
            if t.mask == 0 {
                has_const = true;
            } else if t.mask.count_ones() == 1 && var.is_none() {
                var = Some(t.mask.trailing_zeros());
            } else {
                return None;
            }
        }
        var.map(|v| (v, has_const))
    }

    /// What the splitting solver reads off reference rows: the refutation,
    /// and — only when there is none — the forced assignments.
    fn decision_of(rows: &[F2BoolPoly]) -> Decision {
        let refuted = rows.iter().any(is_constant_one);
        Decision {
            refuted,
            forced: if refuted {
                Vec::new()
            } else {
                rows.iter().filter_map(forced_assignment).collect()
            },
        }
    }

    fn random_system(rng: &mut StdRng, n_vars: usize, max_deg: u32) -> Vec<F2BoolPoly> {
        let n_eqs = 1 + rng.gen::<usize>() % 10;
        (0..n_eqs)
            .map(|_| {
                let n_terms = 1 + rng.gen::<usize>() % 6;
                let monos: Vec<F2BoolMono> = (0..n_terms)
                    .map(|_| {
                        let mut mask = 0u64;
                        for _ in 0..(rng.gen::<u32>() % (max_deg + 1)) {
                            mask |= 1u64 << (rng.gen::<u32>() % n_vars as u32);
                        }
                        F2BoolMono::from_mask(mask)
                    })
                    .collect();
                F2BoolPoly::from_monos(monos, n_vars)
            })
            .filter(|p| !p.is_zero())
            .collect()
    }

    /// Compare both kernels with the reference on one system at one
    /// degree, caps included.
    fn check(polys: &[F2BoolPoly], n_vars: usize, degree: u32, caps: MacaulayCaps) -> bool {
        let reference = matrix_f4_f2_reference(polys, n_vars, degree, caps);
        let (rows, rk) = matrix_rows(polys, n_vars, degree, caps);
        let (decision, dk) = decide(polys, n_vars, degree, caps);
        match reference {
            None => {
                assert!(rows.is_none(), "exact kernel accepted an oversize matrix");
                assert!(
                    decision.is_none(),
                    "decision kernel accepted an oversize matrix"
                );
                assert!(rk.oversize && dk.oversize);
                false
            }
            Some((ref_rows, ref_shape)) => {
                let rows = rows.expect("exact kernel refused a matrix the reference built");
                assert_eq!(rows, ref_rows, "reduced rows differ at degree {degree}");
                let decision =
                    decision.expect("decision kernel refused a matrix the reference built");
                assert_eq!(decision, decision_of(&ref_rows), "decision differs");
                if let Some((r, c)) = ref_shape {
                    assert_eq!((rk.rows, rk.cols), (r, c), "exact kernel shape");
                    assert_eq!((dk.rows, dk.cols), (r, c), "decision kernel shape");
                }
                true
            }
        }
    }

    #[test]
    fn random_systems_agree_with_the_reference() {
        let mut rng = StdRng::seed_from_u64(0x000F_46F2_2026);
        let mut built = 0;
        for case in 0..400 {
            let n_vars = 3 + case % 10;
            let max_deg = 1 + (case as u32 % 3);
            let polys = random_system(&mut rng, n_vars, max_deg);
            if polys.is_empty() {
                continue;
            }
            for degree in max_deg..=max_deg + 2 {
                built += usize::from(check(&polys, n_vars, degree, CAPS));
            }
        }
        assert!(built > 800, "only {built} matrices compared");
    }

    /// Unused variables are where the compact build and the reference
    /// differ in what they build, so the caps must still agree exactly.
    #[test]
    fn caps_agree_with_the_reference_when_variables_are_unused() {
        let mut rng = StdRng::seed_from_u64(0xCA95);
        let mut refused = 0;
        let mut accepted = 0;
        for case in 0..300 {
            let used = 3 + case % 6;
            let n_vars = used + 1 + case % 5;
            let polys = random_system(&mut rng, used, 2);
            if polys.is_empty() {
                continue;
            }
            let polys: Vec<F2BoolPoly> = polys
                .into_iter()
                .map(|p| F2BoolPoly { n_vars, ..p })
                .collect();
            for degree in 2..=4 {
                let reference = matrix_f4_f2_reference(&polys, n_vars, degree, CAPS);
                let Some((_, Some((rows, cols)))) = reference else {
                    continue;
                };
                // Caps straddling the true reference counts.
                for (dr, dc) in [(0i64, 0i64), (-1, 0), (0, -1), (1, 1)] {
                    let caps = MacaulayCaps {
                        max_rows: (rows as i64 + dr).max(0) as usize,
                        max_cols: (cols as i64 + dc).max(0) as usize,
                    };
                    if check(&polys, n_vars, degree, caps) {
                        accepted += 1;
                    } else {
                        refused += 1;
                    }
                }
            }
        }
        assert!(accepted > 100 && refused > 100, "{accepted} / {refused}");
    }

    /// Decomposition systems, and the systems the splitting search hands
    /// the kernel after substituting variables away.
    #[test]
    fn decomposition_systems_agree_with_the_reference() {
        let mut compared = 0;
        for (a, n, m) in [(0u8, 9u32, 2usize), (0, 9, 3), (1, 11, 2), (0, 13, 2)] {
            let Some(kc) = KoblitzCurve::new(a, n) else {
                continue;
            };
            let Some(fb) = build_frobenius_factor_base(&kc, 0) else {
                continue;
            };
            let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
            let mut rng = StdRng::seed_from_u64(u64::from(n) * 31 + m as u64);
            for _ in 0..4 {
                let raw = rng.gen::<u64>() % (1u64 << n);
                let x_r = crate::binary_ecc::F2mElement::from_biguint(
                    &num_bigint::BigUint::from(raw.max(1)),
                    n,
                );
                let Some(sys) =
                    build_decomposition_system(&fb.subspace_basis, &x_r, &kc.curve.b, m, &st)
                else {
                    continue;
                };
                let mut eqs = sys.equations.clone();
                for step in 0..4 {
                    let base = eqs.iter().map(poly_degree).max().unwrap_or(0).max(2);
                    for degree in base..=base + 1 {
                        compared += usize::from(check(&eqs, sys.n_vars, degree, CAPS));
                    }
                    // Substitute one more variable, as the search does.
                    let var = (step * 3 + 1) % sys.n_vars;
                    let bit = 1u64 << var;
                    eqs = eqs
                        .iter()
                        .map(|p| {
                            let monos: Vec<F2BoolMono> = p
                                .terms
                                .iter()
                                .filter_map(|t| {
                                    if t.mask & bit == 0 {
                                        Some(*t)
                                    } else if step % 2 == 0 {
                                        Some(F2BoolMono::from_mask(t.mask & !bit))
                                    } else {
                                        None
                                    }
                                })
                                .collect();
                            F2BoolPoly::from_monos(monos, p.n_vars)
                        })
                        .filter(|p| !p.is_zero())
                        .collect();
                    if eqs.is_empty() {
                        break;
                    }
                }
            }
        }
        assert!(compared > 40, "only {compared} matrices compared");
    }

    #[test]
    fn empty_and_trivial_inputs() {
        let (d, k) = decide(&[], 4, 3, CAPS);
        assert_eq!(d, Some(Decision::default()));
        assert!(!k.built);
        let one = F2BoolPoly::one(3);
        let (d, _) = decide(std::slice::from_ref(&one), 3, 2, CAPS);
        assert!(d.unwrap().refuted);
        let v = F2BoolPoly::from_monos(vec![F2BoolMono::var(2), F2BoolMono::one()], 3);
        let (d, _) = decide(std::slice::from_ref(&v), 3, 2, CAPS);
        assert_eq!(d.unwrap().forced, vec![(2, true)]);
        // A polynomial of degree above the Macaulay degree builds no row.
        let cubic = F2BoolPoly::from_monos(vec![F2BoolMono::from_mask(0b111)], 3);
        let (d, k) = decide(std::slice::from_ref(&cubic), 3, 2, CAPS);
        assert_eq!(d, Some(Decision::default()));
        assert!(k.built);
    }

    #[test]
    fn sixty_four_variables_do_not_overflow() {
        let n_vars = 64;
        let p = F2BoolPoly::from_monos(
            vec![
                F2BoolMono::from_mask(1u64 << 63 | 1),
                F2BoolMono::var(63),
                F2BoolMono::one(),
            ],
            n_vars,
        );
        let q = F2BoolPoly::from_monos(vec![F2BoolMono::var(0), F2BoolMono::one()], n_vars);
        for degree in 2..=3 {
            check(&[p.clone(), q.clone()], n_vars, degree, CAPS);
        }
        let _ = find_irreducible(3);
    }
}
