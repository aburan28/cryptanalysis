//! # Crossbred: Macaulay preprocessing, then bit-sliced exhaustive search.
//!
//! Joux and Vitse's answer to the question this repository keeps
//! running into — a Gröbner basis on a Weil-descended Semaev system is
//! an all-or-nothing computation whose degree of regularity decides
//! everything — is to stop halfway and finish by enumeration.
//!
//! Split the `n` Boolean unknowns into `k` that will be **enumerated**
//! and `n − k` that will be **solved for**.  Build the Macaulay matrix
//! of the system at degree `D` as usual, but instead of reducing it to
//! a basis, look for the `F_2`-combinations of its rows whose degree
//! *in the non-enumerated variables alone* drops to `d` (here `d = 1`).
//! Those combinations — the **crossbred polynomials** — are still in
//! the ideal, so every solution of the original system satisfies them;
//! but once the `k` enumerated variables are fixed, each one is a
//! **linear** form in the remaining `n − k`.  So the search phase is
//! `2^k` linear solves rather than `2^n` evaluations, and the algebra
//! only had to reach degree `D`, not the degree of regularity.
//!
//! ## Why this module exists here
//!
//! [`crate::cryptanalysis::koblitz_groebner`] solves the same systems
//! with matrix-F4 plus splitting, and
//! [`crate::cryptanalysis::semaev_decomp`] solves the `S₄` decomposition
//! by enumerating pairs.  Crossbred sits between them, and its search
//! phase is the part of this whole problem family that maps onto a GPU
//! without an argument: `2^k` independent points, no shared state, and
//! the per-point work is a bitwise AND against a precomputed table.
//!
//! `research/notes/index-calculus/RESEARCH_RESIDUAL_WALKS.md` §11.7 names the Joux–Vitse family as
//! one of the two things that cut the index-calculus constant by orders
//! of magnitude.  This is the Boolean half of that family, measured in
//! the same units as everything else: `word_ops` on both phases, so a
//! crossbred row can be put next to an F4 row in one table.
//!
//! ## The preprocessing, concretely
//!
//! Let `E ⊆ {0,…,n−1}` be the enumerated variables (this module always
//! takes `E = {0,…,k−1}`, so an assignment of `E` is the low `k` bits of
//! a point).  For a Boolean monomial `t` write
//!
//! ```text
//!     specialised_degree(t) = popcount(t & !E)
//! ```
//!
//! — its degree in the variables that will *not* be enumerated.  Order
//! the Macaulay columns so the monomials with `specialised_degree > d`
//! come first; call those the **bad** columns.  A row combination that
//! is zero on every bad column is exactly a crossbred polynomial.  So
//! the preprocessing is one left-kernel computation: row-reduce
//! `[M_bad | I]` and keep the `I`-part of every row whose `M_bad` part
//! vanished.
//!
//! That left kernel is a vector space, and this module returns a basis
//! of it.  Its dimension is the honest measure of whether crossbred
//! applies to a given system at a given `(D, k, d)`: dimension zero
//! means the preprocessing bought nothing and the search phase would be
//! unconstrained.
//!
//! ## The search, concretely
//!
//! With `d = 1` each crossbred polynomial `P` splits as
//!
//! ```text
//!     P  =  c_0(x_E)  +  Σ_j  c_j(x_E) · y_j
//! ```
//!
//! where `y_j` runs over the non-enumerated variables and every `c` is a
//! Boolean function of the enumerated variables only, given in algebraic
//! normal form by construction.  Evaluating one `c` at all `2^k` points
//! at once is the **Möbius transform** of its ANF vector, `k · 2^{k−1}`
//! bit operations for the whole cube, and the result is naturally
//! bit-sliced at 64 points per word.  [`mobius_transform`] does that in
//! place.
//!
//! Two kinds of crossbred polynomial come out, and they are used
//! differently:
//!
//! - `specialised_degree = 0` — the polynomial involves *only*
//!   enumerated variables, so it is a **filter**: a point can only be
//!   part of a solution if the polynomial evaluates to zero there.
//!   Filters combine with a bitwise `AND` of complemented tables, 64
//!   points per instruction, and reject almost everything.  This is the
//!   kernel a GPU would run.
//! - `specialised_degree = 1` — the polynomial is a linear form once the
//!   point is fixed.  Surviving points assemble their rows into a small
//!   `F_2` system and solve it.
//!
//! Every candidate is verified against the **original** equations before
//! it is returned, so nothing spurious escapes even if the crossbred
//! extraction is wrong.
//!
//! ## Honest scope
//!
//! - Solving is implemented for `d = 1` only.  Extraction runs at any
//!   `d` — it is the same kernel computation — because the dimension of
//!   the crossbred space as a function of `d` is worth measuring even
//!   where this module cannot then search.
//! - When a fixed assignment leaves the linear system rank-deficient,
//!   the affine solution space is enumerated up to
//!   [`SearchOptions::max_kernel_dim`]; beyond that the run sets
//!   `exhausted` rather than silently dropping solutions.
//! - The preprocessing is a dense left kernel.  That is `O(R²·(B+R)/64)`
//!   word operations on an `R`-row Macaulay matrix, and it is why
//!   `max_rows` exists.
//!
//! ## References
//!
//! - A. Joux, V. Vitse, *A crossbred algorithm for solving Boolean
//!   polynomial systems*, NuTMiC 2017 — the algorithm.
//! - C. Bouillaguet, H.-C. Chen, C.-M. Cheng, T. Chou, R. Niederhagen,
//!   B.-Y. Yang, *Fast exhaustive search for polynomial systems in F₂*,
//!   CHES 2010 — the bit-sliced enumeration the search phase inherits.
//! - J.-C. Faugère, L. Perret, C. Petit, G. Renault, *Improving the
//!   complexity of index calculus algorithms in elliptic curves over
//!   binary fields*, EUROCRYPT 2012 — the systems this is applied to.

use crate::cryptanalysis::pq_groebner_f2::{F2BoolMono, F2BoolPoly};

/// Parameters of one crossbred run.
#[derive(Clone, Copy, Debug)]
pub struct CrossbredParams {
    /// Degree `D` the Macaulay matrix is built at.
    pub macaulay_degree: u32,
    /// Number of variables `k` fixed by enumeration.  This module always
    /// enumerates variables `0 … k−1`, so an assignment is the low `k`
    /// bits of a point.
    pub enumerated: usize,
    /// Target degree `d` in the non-enumerated variables.  Solving is
    /// implemented for `d = 1`.
    pub target_degree: u32,
    /// Cap on Macaulay rows, so an oversized system fails rather than
    /// exhausting memory.
    pub max_rows: usize,
}

impl Default for CrossbredParams {
    fn default() -> Self {
        Self {
            macaulay_degree: 3,
            enumerated: 8,
            target_degree: 1,
            max_rows: 4_000,
        }
    }
}

/// What the preprocessing cost and found.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct ExtractStats {
    /// Rows of the Macaulay matrix actually built.
    pub macaulay_rows: usize,
    /// Distinct monomials occurring across those rows.
    pub macaulay_cols: usize,
    /// Columns whose monomial has specialised degree `> d` — the ones
    /// the row combination has to kill.
    pub bad_cols: usize,
    /// Dimension of the left kernel: how many independent crossbred
    /// polynomials exist at this `(D, k, d)`.
    pub kernel_dim: usize,
    /// Of those, how many involve only enumerated variables (specialised
    /// degree `0`) and can therefore be used as bitwise filters.
    pub filters: usize,
    /// 64-bit word XORs performed in the kernel elimination.
    pub word_ops: u64,
}

/// The crossbred polynomials of one system, with the parameters that
/// produced them.
#[derive(Clone, Debug)]
pub struct CrossbredSystem {
    /// A basis of the crossbred space: every element lies in the ideal
    /// generated by the input and has specialised degree `≤ d`.
    pub polys: Vec<F2BoolPoly>,
    /// Total Boolean variables of the original system.
    pub n_vars: usize,
    /// `k`, as in [`CrossbredParams`].
    pub enumerated: usize,
    /// `d`, as in [`CrossbredParams`].
    pub target_degree: u32,
    /// Preprocessing measurements.
    pub stats: ExtractStats,
}

impl CrossbredSystem {
    /// Variables solved for rather than enumerated: `n − k`.
    pub fn solved_vars(&self) -> usize {
        self.n_vars - self.enumerated
    }

    /// Mask of the enumerated variables.
    fn enum_mask(&self) -> u64 {
        mask_of(self.enumerated)
    }
}

/// Bitmask of the low `k` bits, safe at `k = 64`.
fn mask_of(k: usize) -> u64 {
    if k >= 64 {
        u64::MAX
    } else {
        (1u64 << k) - 1
    }
}

/// Degree of a Boolean monomial in the variables that are *not*
/// enumerated.
fn specialised_degree(mask: u64, enum_mask: u64) -> u32 {
    (mask & !enum_mask).count_ones()
}

// ── Preprocessing: the left kernel ─────────────────────────────────

/// All Boolean monomials of degree `≤ deg` over `n_vars` variables.
///
/// A Boolean monomial is a subset of the variables, so this enumerates
/// subsets by size.  Kept local to this module rather than shared with
/// `koblitz_groebner`, which has its own copy, because the two want
/// different orderings.
fn monomials_up_to(n_vars: usize, deg: u32) -> Vec<u64> {
    let mut out = vec![0u64];
    let mut level = vec![0u64];
    for _ in 0..deg {
        let mut next = Vec::new();
        for &m in &level {
            let top = 64 - m.leading_zeros();
            for v in top..n_vars as u32 {
                next.push(m | (1u64 << v));
            }
        }
        out.extend(next.iter().copied());
        level = next;
        if level.is_empty() {
            break;
        }
    }
    out
}

/// One Macaulay row, as the set of monomials it contains.
fn shift_row(p: &F2BoolPoly, mult: u64) -> Vec<u64> {
    // Multiplying by a monomial is a union of masks in the Boolean
    // ring, so two distinct terms can collide — and colliding means
    // cancelling, in characteristic 2.  Keep the odd multiplicities.
    let mut all: Vec<u64> = p.terms.iter().map(|t| t.mask | mult).collect();
    all.sort_unstable();
    let mut row = Vec::with_capacity(all.len());
    let mut i = 0;
    while i < all.len() {
        let mut j = i;
        while j < all.len() && all[j] == all[i] {
            j += 1;
        }
        if (j - i) % 2 == 1 {
            row.push(all[i]);
        }
        i = j;
    }
    row
}

/// **Extract the crossbred polynomials** of `system` at the given
/// parameters.
///
/// Returns `None` if the Macaulay matrix would exceed
/// [`CrossbredParams::max_rows`], or if `k` is not a proper split of the
/// variables.  A successful return with `stats.kernel_dim == 0` is a
/// real answer: no crossbred polynomial exists at this `(D, k, d)`, and
/// the caller should raise `D` or lower `k`.
pub fn extract_crossbred(
    system: &[F2BoolPoly],
    n_vars: usize,
    params: &CrossbredParams,
) -> Option<CrossbredSystem> {
    if params.enumerated >= n_vars || n_vars > 64 {
        return None;
    }
    let enum_mask = mask_of(params.enumerated);

    // 1. Macaulay rows: every product `p · m` with `deg(p·m) ≤ D`.
    let mut rows_monos: Vec<Vec<u64>> = Vec::new();
    for p in system {
        let pdeg = p
            .terms
            .iter()
            .map(|t| t.mask.count_ones())
            .max()
            .unwrap_or(0);
        if pdeg > params.macaulay_degree {
            continue;
        }
        for mult in monomials_up_to(n_vars, params.macaulay_degree - pdeg) {
            let row = shift_row(p, mult);
            if !row.is_empty() {
                rows_monos.push(row);
            }
            if rows_monos.len() > params.max_rows {
                return None;
            }
        }
    }
    if rows_monos.is_empty() {
        return Some(CrossbredSystem {
            polys: Vec::new(),
            n_vars,
            enumerated: params.enumerated,
            target_degree: params.target_degree,
            stats: ExtractStats::default(),
        });
    }

    // 2. Columns, bad ones first.  Within each group the order is
    //    irrelevant to the kernel; it is fixed only so the run is
    //    reproducible.
    let mut cols: Vec<u64> = rows_monos.iter().flatten().copied().collect();
    cols.sort_unstable();
    cols.dedup();
    cols.sort_by_key(|&m| {
        let bad = specialised_degree(m, enum_mask) > params.target_degree;
        (!bad, m)
    });
    let n_bad = cols
        .iter()
        .filter(|&&m| specialised_degree(m, enum_mask) > params.target_degree)
        .count();
    let index: std::collections::HashMap<u64, usize> =
        cols.iter().enumerate().map(|(i, m)| (*m, i)).collect();

    let n_rows = rows_monos.len();

    // 3. Augmented matrix `[M_bad | I]`, packed by bit.  Only the bad
    //    columns need to be carried: the good part of a crossbred
    //    polynomial is recovered from the combination afterwards.
    let aug_cols = n_bad + n_rows;
    let words = aug_cols.div_ceil(64);
    let mut aug: Vec<Vec<u64>> = rows_monos
        .iter()
        .enumerate()
        .map(|(r, monos)| {
            let mut row = vec![0u64; words];
            for m in monos {
                let c = index[m];
                if c < n_bad {
                    row[c / 64] |= 1u64 << (c % 64);
                }
            }
            let c = n_bad + r;
            row[c / 64] |= 1u64 << (c % 64);
            row
        })
        .collect();

    // 4. Forward-eliminate the bad block.  Rows left with an empty bad
    //    part span the left kernel.
    let mut word_ops = 0u64;
    let mut pivot_row = 0usize;
    for c in 0..n_bad {
        let (w, bit) = (c / 64, 1u64 << (c % 64));
        let piv = match (pivot_row..n_rows).find(|&r| aug[r][w] & bit != 0) {
            Some(p) => p,
            None => continue,
        };
        aug.swap(pivot_row, piv);
        for r in (pivot_row + 1)..n_rows {
            if aug[r][w] & bit != 0 {
                let (lo, hi) = aug.split_at_mut(r);
                let src = &lo[pivot_row];
                let dst = &mut hi[0];
                for k in 0..words {
                    dst[k] ^= src[k];
                }
                word_ops += words as u64;
            }
        }
        pivot_row += 1;
        if pivot_row == n_rows {
            break;
        }
    }

    // 5. Rebuild each kernel row as a polynomial: XOR together the
    //    Macaulay rows its combination selects, keeping the good
    //    monomials (the bad ones cancelled by construction).
    let mut polys = Vec::new();
    for row in aug.iter().skip(pivot_row) {
        let mut acc: Vec<u64> = Vec::new();
        for r in 0..n_rows {
            let c = n_bad + r;
            if row[c / 64] & (1u64 << (c % 64)) != 0 {
                acc.extend_from_slice(&rows_monos[r]);
            }
        }
        acc.sort_unstable();
        let mut monos: Vec<F2BoolMono> = Vec::new();
        let mut i = 0;
        while i < acc.len() {
            let mut j = i;
            while j < acc.len() && acc[j] == acc[i] {
                j += 1;
            }
            if (j - i) % 2 == 1 {
                monos.push(F2BoolMono::from_mask(acc[i]));
            }
            i = j;
        }
        if monos.is_empty() {
            // A syzygy of the shifted system: true but empty.
            continue;
        }
        debug_assert!(monos
            .iter()
            .all(|m| specialised_degree(m.mask, enum_mask) <= params.target_degree));
        polys.push(F2BoolPoly::from_monos(monos, n_vars));
    }

    let filters = polys
        .iter()
        .filter(|p| {
            p.terms
                .iter()
                .all(|t| specialised_degree(t.mask, enum_mask) == 0)
        })
        .count();

    Some(CrossbredSystem {
        stats: ExtractStats {
            macaulay_rows: n_rows,
            macaulay_cols: cols.len(),
            bad_cols: n_bad,
            kernel_dim: polys.len(),
            filters,
            word_ops,
        },
        polys,
        n_vars,
        enumerated: params.enumerated,
        target_degree: params.target_degree,
    })
}

// ── The Möbius transform ───────────────────────────────────────────

/// Masks selecting the indices whose bit `i` is set, within a 64-bit
/// word, for `i < 6`.
const WITHIN_WORD: [u64; 6] = [
    0xAAAA_AAAA_AAAA_AAAA,
    0xCCCC_CCCC_CCCC_CCCC,
    0xF0F0_F0F0_F0F0_F0F0,
    0xFF00_FF00_FF00_FF00,
    0xFFFF_0000_FFFF_0000,
    0xFFFF_FFFF_0000_0000,
];

/// **In-place Möbius (zeta) transform** of a packed truth table over `k`
/// variables: `f[p] ← XOR_{s ⊆ p} f[s]`.
///
/// Given the algebraic normal form of a Boolean function — bit `s` set
/// iff the monomial `Π_{i ∈ s} x_i` occurs — this produces its
/// evaluation table, bit `p` set iff the function is `1` at the
/// assignment `p`.  `k · 2^{k−1}` bit operations for the entire cube,
/// which is what makes the search phase's precomputation negligible
/// beside the search.
///
/// The transform is its own inverse over `F_2`.
pub fn mobius_transform(bits: &mut [u64], k: u32) {
    let n_words = (1usize << k).div_ceil(64);
    debug_assert!(bits.len() >= n_words);
    for i in 0..k {
        if i < 6 {
            let mask = WITHIN_WORD[i as usize];
            let step = 1u32 << i;
            for w in bits[..n_words].iter_mut() {
                *w ^= (*w & !mask) << step;
            }
        } else {
            let stride = 1usize << (i - 6);
            let mut base = 0usize;
            while base < n_words {
                for w in (base + stride)..(base + 2 * stride).min(n_words) {
                    bits[w] ^= bits[w - stride];
                }
                base += 2 * stride;
            }
        }
    }
}

// ── The search phase ───────────────────────────────────────────────

/// Knobs for [`solve_crossbred`].
#[derive(Clone, Copy, Debug)]
pub struct SearchOptions {
    /// Stop after this many verified solutions.  `0` means no limit.
    pub max_solutions: usize,
    /// Largest affine solution space this will enumerate when a fixed
    /// assignment leaves the linear system rank-deficient.  Exceeding it
    /// sets [`SearchStats::exhausted`].
    pub max_kernel_dim: u32,
    /// Cap on the bits of memory the evaluation tables may take, as a
    /// power of two of enumerated points.  Refuses to run above it.
    pub max_enumerated_bits: u32,
}

impl Default for SearchOptions {
    fn default() -> Self {
        Self {
            max_solutions: 0,
            max_kernel_dim: 12,
            max_enumerated_bits: 22,
        }
    }
}

/// What the search cost and found.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct SearchStats {
    /// Enumerated assignments swept: `2^k`.
    pub points: u64,
    /// Assignments that survived the bitwise filters.
    pub survivors: u64,
    /// Linear systems actually assembled and solved.
    pub linear_solves: u64,
    /// Candidate full assignments produced by those solves.
    pub candidates: u64,
    /// Candidates that satisfied the original system.
    pub verified: u64,
    /// 64-bit word operations in the Möbius precomputation.
    pub transform_word_ops: u64,
    /// 64-bit word operations in the filter sweep.
    pub filter_word_ops: u64,
    /// Row operations in the per-point linear solves.
    pub solve_row_ops: u64,
    /// Set if a rank-deficient system exceeded `max_kernel_dim`, so the
    /// solution list may be incomplete.
    pub exhausted: bool,
}

/// **Solve** the original system by crossbred search.
///
/// `original` is the system the crossbred polynomials were extracted
/// from; every candidate is checked against it, so a wrong extraction
/// loses solutions but never invents them.
///
/// Returns the verified solutions as point masks — bit `i` is the value
/// of variable `i`, matching [`F2BoolPoly::eval`].
///
/// Implemented for `target_degree == 1`; anything else returns an empty
/// result with `exhausted` set, because the search would be solving a
/// non-linear system it has no engine for.
pub fn solve_crossbred(
    original: &[F2BoolPoly],
    xb: &CrossbredSystem,
    opts: &SearchOptions,
) -> (Vec<u64>, SearchStats) {
    let mut stats = SearchStats::default();
    let k = xb.enumerated as u32;
    if xb.target_degree != 1 || k > opts.max_enumerated_bits || xb.polys.is_empty() {
        stats.exhausted = true;
        return (Vec::new(), stats);
    }
    let enum_mask = xb.enum_mask();
    let n_solved = xb.solved_vars();
    let n_points = 1usize << k;
    let words = n_points.div_ceil(64);
    stats.points = n_points as u64;

    // Slot 0 is the constant term; slot `1 + j` is the coefficient of
    // the `j`-th non-enumerated variable, which is variable `k + j`.
    let n_slots = 1 + n_solved;

    // Separate the filters (specialised degree 0 throughout) from the
    // polynomials that carry a linear part.  Filters are swept 64
    // points at a time; the rest are assembled per surviving point.
    let mut filter_tables: Vec<Vec<u64>> = Vec::new();
    let mut linear_tables: Vec<Vec<Vec<u64>>> = Vec::new();

    for p in &xb.polys {
        let mut slots: Vec<Vec<u64>> = vec![vec![0u64; words]; n_slots];
        let mut is_filter = true;
        for t in &p.terms {
            let rest = t.mask & !enum_mask;
            let e = (t.mask & enum_mask) as usize;
            let slot = match rest.count_ones() {
                0 => 0,
                1 => {
                    is_filter = false;
                    1 + (rest.trailing_zeros() as usize - xb.enumerated)
                }
                // Extraction guarantees this cannot happen; treat it as
                // a refusal rather than a panic.
                _ => {
                    stats.exhausted = true;
                    return (Vec::new(), stats);
                }
            };
            slots[slot][e / 64] ^= 1u64 << (e % 64);
        }
        for s in slots.iter_mut() {
            mobius_transform(s, k);
            stats.transform_word_ops += (k as u64) * words as u64;
        }
        if is_filter {
            filter_tables.push(std::mem::take(&mut slots[0]));
        } else {
            linear_tables.push(slots);
        }
    }

    // Alive mask: a point survives iff every filter vanishes on it.
    let mut alive = vec![u64::MAX; words];
    if !n_points.is_multiple_of(64) {
        let last = n_points / 64;
        alive[last] = mask_of(n_points % 64);
        for w in alive.iter_mut().skip(last + 1) {
            *w = 0;
        }
    }
    for table in &filter_tables {
        for w in 0..words {
            alive[w] &= !table[w];
        }
        stats.filter_word_ops += words as u64;
    }

    let mut out: Vec<u64> = Vec::new();
    'points: for w in 0..words {
        let mut live = alive[w];
        while live != 0 {
            let bit = live.trailing_zeros() as usize;
            live &= live - 1;
            let point = (w * 64 + bit) as u64;
            stats.survivors += 1;

            // Assemble the linear system at this assignment.
            let mut rows: Vec<(u64, bool)> = Vec::with_capacity(linear_tables.len());
            for slots in &linear_tables {
                let mut coeffs = 0u64;
                for (j, slot) in slots.iter().enumerate().skip(1) {
                    if slot[w] & (1u64 << bit) != 0 {
                        coeffs |= 1u64 << (j - 1);
                    }
                }
                let rhs = slots[0][w] & (1u64 << bit) != 0;
                if coeffs != 0 || rhs {
                    rows.push((coeffs, rhs));
                }
            }
            stats.linear_solves += 1;

            let solutions = match solve_linear_f2(&mut rows, n_solved, opts, &mut stats) {
                Some(s) => s,
                None => {
                    stats.exhausted = true;
                    continue;
                }
            };
            for y in solutions {
                let full = point | (y << xb.enumerated);
                stats.candidates += 1;
                if original.iter().all(|p| p.eval(full) == 0) {
                    stats.verified += 1;
                    if !out.contains(&full) {
                        out.push(full);
                        if opts.max_solutions != 0 && out.len() >= opts.max_solutions {
                            break 'points;
                        }
                    }
                }
            }
        }
    }

    (out, stats)
}

/// Solve `rows · y = rhs` over `F_2` in `n` unknowns, returning every
/// solution of the affine space.
///
/// `None` means the solution space was larger than
/// [`SearchOptions::max_kernel_dim`] and was not enumerated.
fn solve_linear_f2(
    rows: &mut [(u64, bool)],
    n: usize,
    opts: &SearchOptions,
    stats: &mut SearchStats,
) -> Option<Vec<u64>> {
    let mut pivot_col_of_row: Vec<usize> = Vec::new();
    let mut r = 0usize;
    for c in 0..n {
        let bit = 1u64 << c;
        let piv = (r..rows.len()).find(|&i| rows[i].0 & bit != 0);
        let piv = match piv {
            Some(p) => p,
            None => continue,
        };
        rows.swap(r, piv);
        for i in 0..rows.len() {
            if i != r && rows[i].0 & bit != 0 {
                let (c0, r0) = rows[r];
                rows[i].0 ^= c0;
                rows[i].1 ^= r0;
                stats.solve_row_ops += 1;
            }
        }
        pivot_col_of_row.push(c);
        r += 1;
        if r == rows.len() {
            break;
        }
    }
    // Inconsistent: a row `0 = 1`.
    if rows.iter().any(|&(c, rhs)| c == 0 && rhs) {
        return Some(Vec::new());
    }

    let pivots: std::collections::HashSet<usize> = pivot_col_of_row.iter().copied().collect();
    let free: Vec<usize> = (0..n).filter(|c| !pivots.contains(c)).collect();
    if free.len() as u32 > opts.max_kernel_dim {
        return None;
    }

    let mut out = Vec::with_capacity(1 << free.len());
    for assign in 0..(1u64 << free.len()) {
        let mut y = 0u64;
        for (i, &c) in free.iter().enumerate() {
            if assign & (1 << i) != 0 {
                y |= 1u64 << c;
            }
        }
        for (i, &c) in pivot_col_of_row.iter().enumerate() {
            let (coeffs, rhs) = rows[i];
            // Reduced echelon form: the pivot row has this column and
            // free columns only.
            let mut v = rhs;
            let mut rest = coeffs & !(1u64 << c);
            while rest != 0 {
                let j = rest.trailing_zeros();
                rest &= rest - 1;
                v ^= y & (1u64 << j) != 0;
            }
            if v {
                y |= 1u64 << c;
            }
        }
        out.push(y);
    }
    Some(out)
}

// ── Sweeping the parameter space ───────────────────────────────────

/// One `(D, k)` cell of a crossbred parameter sweep.
#[derive(Clone, Copy, Debug)]
pub struct SweepCell {
    /// Macaulay degree.
    pub macaulay_degree: u32,
    /// Enumerated variables.
    pub enumerated: usize,
    /// Preprocessing measurements, or `None` if the matrix was refused.
    pub extract: Option<ExtractStats>,
}

/// Measure the crossbred space over a grid of `(D, k)`.
///
/// This is the measurement that decides whether crossbred applies to a
/// family of systems at all: `kernel_dim` has to reach at least
/// `n − k` before the search phase is determined, and `filters` is what
/// makes the sweep cheap.
pub fn sweep(
    system: &[F2BoolPoly],
    n_vars: usize,
    degrees: &[u32],
    enumerated: &[usize],
    max_rows: usize,
) -> Vec<SweepCell> {
    let mut out = Vec::new();
    for &d in degrees {
        for &k in enumerated {
            let params = CrossbredParams {
                macaulay_degree: d,
                enumerated: k,
                target_degree: 1,
                max_rows,
            };
            out.push(SweepCell {
                macaulay_degree: d,
                enumerated: k,
                extract: extract_crossbred(system, n_vars, &params).map(|x| x.stats),
            });
        }
    }
    out
}

/// Render a sweep as a table, one row per `(D, k)`.
pub fn format_sweep(cells: &[SweepCell]) -> String {
    let mut s = String::from(
        "|  D |  k | rows | cols | bad | kernel | filters | word ops |\n\
         |---:|---:|-----:|-----:|----:|-------:|--------:|---------:|\n",
    );
    for c in cells {
        match &c.extract {
            Some(e) => s.push_str(&format!(
                "| {:2} | {:2} | {:4} | {:4} | {:3} | {:6} | {:7} | {:8} |\n",
                c.macaulay_degree,
                c.enumerated,
                e.macaulay_rows,
                e.macaulay_cols,
                e.bad_cols,
                e.kernel_dim,
                e.filters,
                e.word_ops
            )),
            None => s.push_str(&format!(
                "| {:2} | {:2} |    — |    — |   — |      — |       — |        — |\n",
                c.macaulay_degree, c.enumerated
            )),
        }
    }
    s
}

#[cfg(test)]
mod tests {
    use super::*;

    use crate::cryptanalysis::koblitz_groebner::{build_decomposition_system, FieldStructure};
    use crate::cryptanalysis::koblitz_index_calculus::{build_frobenius_factor_base, KoblitzCurve};

    /// Brute force over all `2^n` points: the ground truth every other
    /// path is compared with.
    fn brute_force(system: &[F2BoolPoly], n_vars: usize) -> Vec<u64> {
        (0..(1u64 << n_vars))
            .filter(|&p| system.iter().all(|q| q.eval(p) == 0))
            .collect()
    }

    fn poly(monos: &[u64], n_vars: usize) -> F2BoolPoly {
        F2BoolPoly::from_monos(
            monos.iter().map(|&m| F2BoolMono::from_mask(m)).collect(),
            n_vars,
        )
    }

    /// The Möbius transform turns an ANF into an evaluation table.
    #[test]
    fn mobius_transform_evaluates_the_anf() {
        // f = x0·x2 + x1 + 1 over k = 3 variables.
        let anf_monos = [0b101u64, 0b010, 0b000];
        for k in 3..=8u32 {
            let words = (1usize << k).div_ceil(64);
            let mut bits = vec![0u64; words];
            for &m in &anf_monos {
                bits[(m as usize) / 64] ^= 1u64 << (m % 64);
            }
            mobius_transform(&mut bits, k);
            for p in 0..(1usize << k) {
                let expect = ((p & 0b101) == 0b101) as u32 ^ ((p >> 1) & 1) as u32 ^ 1;
                let got = (bits[p / 64] >> (p % 64)) & 1;
                assert_eq!(got as u32, expect, "k={k} point {p}");
            }
        }
    }

    /// It is an involution over `F_2`.
    #[test]
    fn mobius_transform_is_its_own_inverse() {
        let k = 7u32;
        let words = (1usize << k).div_ceil(64);
        let mut state = 0x9E37_79B9_7F4A_7C15u64;
        let original: Vec<u64> = (0..words)
            .map(|_| {
                state ^= state << 13;
                state ^= state >> 7;
                state ^= state << 17;
                state
            })
            .collect();
        let mut bits = original.clone();
        mobius_transform(&mut bits, k);
        mobius_transform(&mut bits, k);
        assert_eq!(bits, original);
    }

    /// Every crossbred polynomial must vanish on every solution of the
    /// system it came from — that is the whole correctness argument for
    /// the search phase.
    #[test]
    fn crossbred_polynomials_vanish_on_every_solution() {
        let n_vars = 10;
        // A small quadratic system with a handful of roots.
        let system = vec![
            poly(&[0b1_0000_0001, 0b10, 0b1], n_vars),
            poly(&[0b11_0000, 0b100, 0b0], n_vars),
            poly(&[0b1_0100, 0b1000_0000, 0b10], n_vars),
            poly(&[0b110, 0b1_0000, 0b0], n_vars),
        ];
        let roots = brute_force(&system, n_vars);
        assert!(!roots.is_empty(), "test system has no roots");

        for k in [3usize, 4, 5] {
            let params = CrossbredParams {
                macaulay_degree: 3,
                enumerated: k,
                target_degree: 1,
                max_rows: 20_000,
            };
            let xb = extract_crossbred(&system, n_vars, &params).unwrap();
            for p in &xb.polys {
                // Specialised degree really is bounded.
                for t in &p.terms {
                    assert!(
                        specialised_degree(t.mask, mask_of(k)) <= 1,
                        "k={k}: crossbred polynomial kept a bad monomial"
                    );
                }
                // …and it is in the ideal.
                for &r in &roots {
                    assert_eq!(p.eval(r), 0, "k={k}: crossbred polynomial misses a root");
                }
            }
        }
    }

    /// Crossbred finds exactly the roots brute force finds.
    #[test]
    fn crossbred_agrees_with_brute_force_on_a_random_system() {
        let n_vars = 12;
        let mut state = 0x243F_6A88_85A3_08D3u64;
        let mut rand = || {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            state
        };
        let mut seen_solvable = false;
        let mut seen_unsolvable = false;

        for trial in 0..24 {
            // Random quadratics in 12 variables.
            let system: Vec<F2BoolPoly> = (0..10)
                .map(|_| {
                    let mut monos = Vec::new();
                    for _ in 0..6 {
                        let r = rand();
                        let i = (r % n_vars as u64) as u32;
                        let j = ((r >> 8) % n_vars as u64) as u32;
                        monos.push((1u64 << i) | (1u64 << j));
                    }
                    if rand() & 1 == 0 {
                        monos.push(0);
                    }
                    poly(&monos, n_vars)
                })
                .collect();

            let expect = brute_force(&system, n_vars);
            if expect.is_empty() {
                seen_unsolvable = true;
            } else {
                seen_solvable = true;
            }

            let params = CrossbredParams {
                macaulay_degree: 3,
                enumerated: 6,
                target_degree: 1,
                max_rows: 20_000,
            };
            let xb = extract_crossbred(&system, n_vars, &params).unwrap();
            if xb.polys.is_empty() {
                // No crossbred space at these parameters: nothing to
                // compare, and the sweep is the place that reports it.
                continue;
            }
            let (mut got, stats) = solve_crossbred(&system, &xb, &SearchOptions::default());
            assert!(!stats.exhausted, "trial {trial}: search gave up");
            got.sort_unstable();
            let mut expect = expect.clone();
            expect.sort_unstable();
            assert_eq!(got, expect, "trial {trial}");
        }
        assert!(
            seen_solvable && seen_unsolvable,
            "the comparison never saw both verdicts, so it could pass vacuously"
        );
    }

    /// On the real thing: the Weil-descended Semaev system of a Koblitz
    /// decomposition.  Crossbred must reach the same verdict as brute
    /// force, and must find the planted decomposition.
    #[test]
    fn crossbred_solves_a_koblitz_decomposition_system() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let basis = &fb.subspace_basis;

        let p1 = fb.points[0].clone();
        let p2 = fb.points[3].clone();
        let r = kc.add(&p1, &p2);
        let x_r = match &r {
            crate::binary_ecc::BinaryPoint::Affine { x, .. } => x.clone(),
            _ => panic!("P1 + P2 = O"),
        };
        let sys = build_decomposition_system(basis, &x_r, &kc.curve.b, 2, &st).unwrap();
        let expect = brute_force(&sys.equations, sys.n_vars);
        assert!(
            !expect.is_empty(),
            "the planted decomposition must be a root"
        );

        let params = CrossbredParams {
            macaulay_degree: 3,
            enumerated: 4,
            target_degree: 1,
            max_rows: 20_000,
        };
        let xb = extract_crossbred(&sys.equations, sys.n_vars, &params).unwrap();
        assert!(
            xb.stats.kernel_dim > 0,
            "no crossbred space on the real system at D=3, k=4"
        );

        let (mut got, stats) = solve_crossbred(&sys.equations, &xb, &SearchOptions::default());
        assert!(!stats.exhausted, "search gave up on the Koblitz system");
        got.sort_unstable();
        let mut expect = expect;
        expect.sort_unstable();
        assert_eq!(got, expect);
        assert_eq!(stats.points, 1 << 4);
    }

    /// The `m = 2` system is **bilinear** in the two summands, so
    /// splitting the variables at `k = ℓ` — one summand enumerated, the
    /// other solved for — leaves no monomial of specialised degree `2`
    /// at all.  Crossbred then needs no Macaulay lift: `D = 2`, the
    /// degree of the system itself, already has `bad_cols == 0`.
    ///
    /// This is worth pinning because it says crossbred does not
    /// *discover* anything on `m = 2`: at `k = ℓ` it degenerates to
    /// exactly the pairs-and-solve structure
    /// [`crate::cryptanalysis::semaev_decomp`] already implements.  The
    /// case where crossbred has something to add is `m ≥ 3`, where the
    /// chained system is cubic and no such split exists.
    #[test]
    fn the_m2_system_is_bilinear_so_splitting_at_ell_needs_no_lift() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let x_r = match kc.add(&fb.points[0], &fb.points[3]) {
            crate::binary_ecc::BinaryPoint::Affine { x, .. } => x,
            _ => panic!("P1 + P2 = O"),
        };
        let sys =
            build_decomposition_system(&fb.subspace_basis, &x_r, &kc.curve.b, 2, &st).unwrap();
        assert_eq!(
            sys.n_vars,
            2 * fb.ell as usize,
            "m = 2 has exactly 2ℓ unknowns"
        );

        let params = CrossbredParams {
            macaulay_degree: 2,
            enumerated: fb.ell as usize,
            target_degree: 1,
            max_rows: 20_000,
        };
        let xb = extract_crossbred(&sys.equations, sys.n_vars, &params).unwrap();
        assert_eq!(
            xb.stats.bad_cols, 0,
            "the bilinear system should have no monomial quadratic in one summand"
        );
        assert_eq!(
            xb.stats.kernel_dim,
            sys.equations.len(),
            "with nothing to kill, every equation is already a crossbred polynomial"
        );
        assert_eq!(xb.stats.word_ops, 0, "and the elimination does no work");

        // Below `k = ℓ` the split cuts through a summand and the
        // quadratic terms reappear.
        let narrow = CrossbredParams {
            enumerated: fb.ell as usize - 1,
            ..params
        };
        let xb2 = extract_crossbred(&sys.equations, sys.n_vars, &narrow).unwrap();
        assert!(xb2.stats.bad_cols > 0);
    }

    /// On the chained `m = 3` system — cubic, and the case that matters
    /// — crossbred must find every root the F4-plus-splitting oracle
    /// finds, and everything it returns must be a genuine root.
    ///
    /// The containment is one-sided on purpose: `SolveOptions::default`
    /// caps `max_solutions` at 32 and `solve_rec` returns at the cap
    /// *without* setting `exhausted`, so the F4 list is a prefix of the
    /// root set rather than the root set.  Equality against it would be
    /// equality against a truncation.
    #[test]
    fn crossbred_covers_the_f4_oracle_on_the_cubic_m3_system() {
        use crate::cryptanalysis::koblitz_groebner::{
            solve_boolean_system, SolveOptions, SolverEngine,
        };

        // `n = 9`: the invariant subspace of `K_0 / F_2^7` contains only
        // one abscissa of a curve point, so nothing decomposes there and
        // the comparison would be vacuous.
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);

        let mut compared = 0;
        // Plant the decomposition: `R = P_a + P_b + P_c` over the factor
        // base, so a root provably exists.
        for (a, b, c) in [(0usize, 1usize, 2usize), (0, 3, 5)] {
            let sum = kc.add(&kc.add(&fb.points[a], &fb.points[b]), &fb.points[c]);
            let x_r = match &sum {
                crate::binary_ecc::BinaryPoint::Affine { x, .. } => x.clone(),
                _ => continue,
            };
            let sys =
                match build_decomposition_system(&fb.subspace_basis, &x_r, &kc.curve.b, 3, &st) {
                    Some(s) => s,
                    None => continue,
                };
            let v = sys.n_vars;

            let params = CrossbredParams {
                macaulay_degree: 3,
                enumerated: 12,
                target_degree: 1,
                max_rows: 20_000,
            };
            let xb = extract_crossbred(&sys.equations, v, &params).unwrap();
            let (got, stats) = solve_crossbred(&sys.equations, &xb, &SearchOptions::default());
            assert!(!stats.exhausted, "({a},{b},{c}): crossbred gave up");
            assert!(!got.is_empty(), "({a},{b},{c}): planted root not found");

            // Soundness: everything returned is a root.
            for &r in &got {
                assert!(
                    sys.equations.iter().all(|p| p.eval(r) == 0),
                    "({a},{b},{c}): crossbred returned a non-root"
                );
            }
            // Completeness, against the capped reference.
            let (f4, _) = solve_boolean_system(
                &sys.equations,
                v,
                &SolveOptions {
                    engine: SolverEngine::MatrixF4 { max_degree: 4 },
                    ..Default::default()
                },
            );
            for r in &f4 {
                assert!(
                    got.contains(r),
                    "({a},{b},{c}): crossbred missed a root F4 found ({r:#x})"
                );
            }
            if !f4.is_empty() {
                compared += 1;
            }
        }
        assert!(
            compared > 0,
            "the comparison never saw a solvable system, so it could pass vacuously"
        );
    }

    /// An unsatisfiable system must come back empty, not merely
    /// unverified — crossbred has to be able to say no.
    #[test]
    fn crossbred_refutes_an_unsatisfiable_system() {
        let n_vars = 8;
        // x0 + x1, x0 + x1 + 1 — no common root.
        let system = vec![poly(&[0b01, 0b10], n_vars), poly(&[0b01, 0b10, 0], n_vars)];
        assert!(brute_force(&system, n_vars).is_empty());

        let params = CrossbredParams {
            macaulay_degree: 2,
            enumerated: 3,
            target_degree: 1,
            max_rows: 20_000,
        };
        let xb = extract_crossbred(&system, n_vars, &params).unwrap();
        let (got, _) = solve_crossbred(&system, &xb, &SearchOptions::default());
        assert!(got.is_empty());
    }

    /// The sweep runs and its table is well formed.
    #[test]
    fn sweep_reports_every_cell() {
        let n_vars = 10;
        let system = vec![
            poly(&[0b1_0000_0001, 0b10, 0b1], n_vars),
            poly(&[0b11_0000, 0b100, 0b0], n_vars),
        ];
        let cells = sweep(&system, n_vars, &[2, 3], &[3, 4, 5], 20_000);
        assert_eq!(cells.len(), 6);
        let table = format_sweep(&cells);
        assert_eq!(table.lines().count(), 8);
    }
}
