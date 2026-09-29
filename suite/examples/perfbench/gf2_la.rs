//! Area `gf2_la`: dense and sparse linear algebra over F_2 (Four Russians
//! elimination, echelon forms, rank).
//!
//! The matrices are the ones the research pipelines reduce: the dense
//! Macaulay matrices of frozen Koblitz decomposition systems
//! (`koblitz_bench::decomposition_macaulay`, the cells `gf2_elim_bench`
//! uses where they fit the builder's default caps), the ANF Macaulay
//! matrices of the symmetrised `S₄` presentation the refutation-degree
//! thread reduces with `pc_degree_harness::rank_and_refute`, their sparse
//! index-list forms for `sparse_macaulay`, and random matrices of the same
//! shapes.  Kernel names carry the cell: `k{n}m{m}d{d}` is curve degree
//! `n`, `m` summands, Macaulay degree `d`.
//!
//! Every counted entry point fingerprints its `word_ops` as well as the
//! reduced matrix: the word-XOR count is the research unit these stages
//! are priced in, so a change that alters it alters the research
//! accounting and is not an engineering change.
//!
//! Where an API is internally parallel (`gf2_elim` and the Four Russians
//! kernel of `koblitz_groebner` clear rows on rayon above a size
//! threshold) each row's update is independent and the counted sum is an
//! integer sum, so the result is the same at any thread count.
//!
//! Instruction counts: rayon runs `par_iter` work on its pool thread even
//! at `RAYON_NUM_THREADS=1`, and callgrind's `--toggle-collect` only
//! collects on the thread that entered the measured region, so the
//! parallel row clearing of the large `gf2_elim` kernels is missed
//! (`rref_random_4940x8357`: 0.29 G of 1.00 G instructions counted).
//! `KIC_GF2_PARALLEL_WORDS=18446744073709551615` forces the serial path
//! (same output), or the harness can build the pool with
//! `use_current_thread()` under `--instr`.

use crate::harness::{Closure, Fp, Fresh, Kernel, Tier, Workload};
use cryptanalysis_suite::binary_ecc::F2mElement;
use cryptanalysis_suite::cryptanalysis::binary_semaev_s4::weil_descend_s4;
use cryptanalysis_suite::cryptanalysis::degree_reduction_anf::{
    anf_macaulay_rows, s4_is_decomposable, symmetrised_presentation,
};
use cryptanalysis_suite::cryptanalysis::descent_expansion::enumerate_irreducibles;
use cryptanalysis_suite::cryptanalysis::gf2_elim;
use cryptanalysis_suite::cryptanalysis::koblitz_bench::{decomposition_macaulay, rref_f2_legacy};
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, DecompositionSystem, FieldStructure,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::invariant_subspace_basis;
use cryptanalysis_suite::cryptanalysis::matrix_f5_f2::F5Criterion;
use cryptanalysis_suite::cryptanalysis::pc_degree_harness::{
    rank_and_refute, sparse_rank_and_refute,
};
use cryptanalysis_suite::cryptanalysis::sparse_macaulay::{
    eliminate_high_columns, SparseElimination,
};
use num_bigint::BigUint;
use rand::{rngs::StdRng, Rng, SeedableRng};
use std::collections::HashSet;

// ── Inputs ─────────────────────────────────────────────────────────

fn random_matrix(rows: usize, cols: usize, seed: u64) -> Vec<Vec<u64>> {
    let mut rng = StdRng::seed_from_u64(seed);
    let words = cols.div_ceil(64);
    (0..rows)
        .map(|_| {
            let mut row: Vec<u64> = (0..words).map(|_| rng.gen()).collect();
            if !cols.is_multiple_of(64) {
                row[words - 1] &= (1u64 << (cols % 64)) - 1;
            }
            row
        })
        .collect()
}

/// A random matrix whose rows have exactly `weight` set columns — the
/// row weight of a freshly built Macaulay matrix, without its structure.
fn random_weight_matrix(rows: usize, cols: usize, weight: usize, seed: u64) -> Vec<Vec<u64>> {
    let mut rng = StdRng::seed_from_u64(seed);
    let words = cols.div_ceil(64);
    (0..rows)
        .map(|_| {
            let mut row = vec![0u64; words];
            let mut set = 0;
            while set < weight {
                let c = rng.gen_range(0..cols);
                if row[c / 64] >> (c % 64) & 1 == 0 {
                    row[c / 64] |= 1 << (c % 64);
                    set += 1;
                }
            }
            row
        })
        .collect()
}

/// The dense Macaulay matrix of a frozen decomposition cell, within the
/// builder's default size caps.  Returns `(variables, columns, rows)`.
fn macaulay(n: u32, m: usize, d: u32, seed: u64) -> (usize, usize, Vec<Vec<u64>>) {
    decomposition_macaulay(n, 0, m, d, seed)
        .unwrap_or_else(|| panic!("cell n={n} m={m} d={d} unavailable"))
}

/// The same system `decomposition_macaulay` expands (same field, factor
/// base, target draw).
fn decomposition_system(n: u32, m: usize, seed: u64) -> DecompositionSystem {
    let (irr, basis) = invariant_subspace_basis(n, 0).expect("invariant subspace");
    let st = FieldStructure::new(n, &irr);
    let b = F2mElement::one(n);
    let mut rng = StdRng::seed_from_u64(seed);
    let x_r = F2mElement::from_biguint(&BigUint::from(rng.gen::<u64>()), n);
    build_decomposition_system(&basis, &x_r, &b, m, &st).expect("decomposition system")
}

/// Every monomial mask over `n_vars` variables of degree at most `max_deg`.
fn monomials_up_to(n_vars: usize, max_deg: u32) -> Vec<u64> {
    fn walk(start: usize, n_vars: usize, left: u32, mask: u64, out: &mut Vec<u64>) {
        out.push(mask);
        if left == 0 {
            return;
        }
        for v in start..n_vars {
            walk(v + 1, n_vars, left - 1, mask | 1 << v, out);
        }
    }
    let mut out = Vec::new();
    walk(0, n_vars, max_deg, 0, &mut out);
    out
}

fn poly_degree(p: &cryptanalysis_suite::cryptanalysis::pq_groebner_f2::F2BoolPoly) -> u32 {
    p.terms
        .iter()
        .map(|t| t.mask.count_ones())
        .max()
        .unwrap_or(0)
}

/// The column boundaries the sparse eliminators take, derived from the
/// column monomials of the cell's Macaulay matrix: `(low_start,
/// leading_band_end)` as `sparse_macaulay::{low_column_start,
/// leading_band_end}` would read them.  The columns are every monomial of
/// every product `t·p` (odd multiplicities, `deg t ≤ d − deg p`) in
/// degree-first descending order, so both are counts by degree; the
/// count is checked against the dense builder's column count.
fn column_boundaries(sys: &DecompositionSystem, d: u32, n_cols: usize) -> (usize, usize) {
    let mut cols: HashSet<u64> = HashSet::new();
    let mut all = Vec::new();
    for p in &sys.equations {
        let pdeg = poly_degree(p);
        if pdeg > d {
            continue;
        }
        for mult in monomials_up_to(sys.n_vars, d - pdeg) {
            all.clear();
            all.extend(p.terms.iter().map(|t| t.mask | mult));
            all.sort_unstable();
            let mut i = 0;
            while i < all.len() {
                let mut j = i;
                while j < all.len() && all[j] == all[i] {
                    j += 1;
                }
                if (j - i) % 2 == 1 {
                    cols.insert(all[i]);
                }
                i = j;
            }
        }
    }
    assert_eq!(cols.len(), n_cols, "column set does not match the builder");
    let top = cols.iter().map(|m| m.count_ones()).max().unwrap_or(0);
    let low_start = cols.iter().filter(|m| m.count_ones() >= 2).count();
    let band_end = cols.iter().filter(|m| m.count_ones() == top).count();
    (low_start, band_end)
}

/// Dense rows as ascending column-index lists, the form
/// `build_macaulay_sparse` hands the sparse eliminators.
fn to_sparse(m: &[Vec<u64>]) -> Vec<Vec<u32>> {
    m.iter()
        .map(|row| {
            let mut out = Vec::new();
            for (k, &w) in row.iter().enumerate() {
                let mut w = w;
                while w != 0 {
                    out.push((k * 64 + w.trailing_zeros() as usize) as u32);
                    w &= w - 1;
                }
            }
            out
        })
        .collect()
}

/// The symmetrised-`S₄` presentation at `(n, l)` for the first
/// non-decomposable target `x_R` (bit pattern `t = 1, 2, …`), as the
/// refutation-degree scans pick it; returns its ANF Macaulay matrix at
/// degree `d` as `(rows, columns)`.
fn anf_s4_macaulay(n: u32, l: u32, d: u32) -> (Vec<Vec<u64>>, usize) {
    let irr = enumerate_irreducibles(n, 1)
        .into_iter()
        .next()
        .expect("irreducible");
    let b = F2mElement::one(n);
    for t in 1u32..64 {
        let bits: Vec<u32> = (0..n).filter(|i| (t >> i) & 1 == 1).collect();
        let x_r = F2mElement::from_bit_positions(&bits, n);
        let sys = weil_descend_s4(n, l, &irr, &b, &x_r);
        if !s4_is_decomposable(&sys) {
            let (eqs, vars) = symmetrised_presentation(&sys);
            let (rows, cols, _) = anf_macaulay_rows(&eqs, vars, d);
            return (rows, cols);
        }
    }
    panic!("no non-decomposable target at n={n} l={l}");
}

// ── Fingerprints ───────────────────────────────────────────────────

/// A matrix, row by row.  Each row is folded at word granularity (one
/// multiply per word, deterministic on every platform) and the fold fed
/// to [`Fp`], so hashing a multi-megabyte result stays a small, fixed
/// share of the timed region instead of eight byte steps per word.
fn fp_rows(mut fp: Fp, rows: &[Vec<u64>]) -> Fp {
    fp = fp.usize(rows.len());
    for row in rows {
        let mut h = row.len() as u64;
        for &w in row {
            h = (h ^ w).wrapping_mul(0x9e37_79b9_7f4a_7c15);
            h ^= h >> 29;
        }
        fp = fp.u64(h);
    }
    fp
}

fn fp_sparse_rows(mut fp: Fp, rows: &[Vec<u32>]) -> Fp {
    fp = fp.usize(rows.len());
    for row in rows {
        let mut h = row.len() as u64;
        for &c in row {
            h = (h ^ c as u64).wrapping_mul(0x9e37_79b9_7f4a_7c15);
            h ^= h >> 29;
        }
        fp = fp.u64(h);
    }
    fp
}

fn fp_sparse_elimination(e: &SparseElimination) -> u64 {
    let fp = Fp::new()
        .usize(e.high_rank)
        .usize(e.vanished)
        .usize(e.max_weight);
    fp_sparse_rows(fp, &e.linear_rows).finish()
}

/// Leading column of each of the first `rank` rows: the pivot columns,
/// which any row echelon form of the same row space shares.
fn fp_leads(mut fp: Fp, rows: &[Vec<u64>], rank: usize) -> Fp {
    for row in &rows[..rank] {
        let lead = row
            .iter()
            .position(|&w| w != 0)
            .map(|k| k * 64 + row[k].trailing_zeros() as usize)
            .unwrap_or(usize::MAX);
        fp = fp.usize(lead);
    }
    fp
}

// ── Workloads ──────────────────────────────────────────────────────

fn rref_fp(m: &mut [Vec<u64>], cols: usize) -> u64 {
    let rank = gf2_elim::rref(m, cols);
    let mut fp = Fp::new().usize(rank);
    for row in m.iter() {
        fp = fp.words(row);
    }
    fp.finish()
}

fn rref_random_2048() -> Box<dyn Workload> {
    Box::new(Fresh::new(random_matrix(2048, 2048, 1), |m| {
        rref_fp(m, 2048)
    }))
}

/// `gf2_elim::rref_counted` — the kernel `koblitz_groebner::rref_f2`
/// sends every matrix of at least 128 rows and 256 columns to.
fn rref_counted(matrix: Vec<Vec<u64>>, cols: usize) -> Box<dyn Workload> {
    Box::new(Fresh::new(matrix, move |m| {
        let mut ops = 0u64;
        let rank = gf2_elim::rref_counted(m, cols, &mut ops);
        fp_rows(Fp::new().usize(rank).u64(ops), m).finish()
    }))
}

/// `gf2_elim::echelon_counted`.
fn echelon_counted(matrix: Vec<Vec<u64>>, cols: usize) -> Box<dyn Workload> {
    Box::new(Fresh::new(matrix, move |m| {
        let mut ops = 0u64;
        let rank = gf2_elim::echelon_counted(m, cols, &mut ops);
        fp_rows(Fp::new().usize(rank).u64(ops), m).finish()
    }))
}

/// `koblitz_bench::rref_f2_legacy` — `koblitz_groebner`'s own kernels
/// (block-4 Four Russians with a per-thread arena, or column-at-a-time
/// when the matrix is small or wider than four times its height), which
/// also serve `echelon_f2_counted` and every matrix below the `gf2_elim`
/// cut-off.
fn legacy_rref(matrix: Vec<Vec<u64>>, cols: usize) -> Box<dyn Workload> {
    Box::new(Fresh::new(matrix, move |m| {
        let mut ops = 0u64;
        let rank = rref_f2_legacy(m, cols, &mut ops);
        fp_rows(Fp::new().usize(rank).u64(ops), m).finish()
    }))
}

fn rref_macaulay_k23m2d4() -> Box<dyn Workload> {
    let (_, cols, m) = macaulay(23, 2, 4, 1);
    rref_counted(m, cols)
}

fn rref_macaulay_k17m2d5() -> Box<dyn Workload> {
    let (_, cols, m) = macaulay(17, 2, 5, 1);
    rref_counted(m, cols)
}

fn rref_macaulay_k5m3d5() -> Box<dyn Workload> {
    let (_, cols, m) = macaulay(5, 3, 5, 0x5EED);
    rref_counted(m, cols)
}

fn rref_macaulay_k15m3d4() -> Box<dyn Workload> {
    let (_, cols, m) = macaulay(15, 3, 4, 1);
    rref_counted(m, cols)
}

fn rref_macaulay_k11m2d5() -> Box<dyn Workload> {
    let (_, cols, m) = macaulay(11, 2, 5, 1);
    rref_counted(m, cols)
}

/// Sixteen target draws of the small `n = 23, m = 2, d = 3` cell, each
/// reduced in turn: the per-call overheads (table sizing, strip set-up)
/// that a solver reducing many small matrices pays.
fn rref_macaulay_k23m2d3_x16() -> Box<dyn Workload> {
    let cells: Vec<(usize, Vec<Vec<u64>>)> = (1..=16u64)
        .map(|seed| {
            let (_, cols, m) = macaulay(23, 2, 3, seed);
            (cols, m)
        })
        .collect();
    Box::new(Fresh::new(cells, |cells| {
        let mut fp = Fp::new();
        for (cols, m) in cells.iter_mut() {
            let mut ops = 0u64;
            let rank = gf2_elim::rref_counted(m, *cols, &mut ops);
            fp = fp_rows(fp.usize(rank).u64(ops), m);
        }
        fp.finish()
    }))
}

fn echelon_macaulay_k23m2d4() -> Box<dyn Workload> {
    let (_, cols, m) = macaulay(23, 2, 4, 1);
    echelon_counted(m, cols)
}

fn echelon_macaulay_k5m3d5() -> Box<dyn Workload> {
    let (_, cols, m) = macaulay(5, 3, 5, 0x5EED);
    echelon_counted(m, cols)
}

fn legacy_rref_macaulay_k5m3d5() -> Box<dyn Workload> {
    let (_, cols, m) = macaulay(5, 3, 5, 0x5EED);
    legacy_rref(m, cols)
}

/// 1334 × 13884: wider than four times its height, so the legacy
/// selector takes the column-at-a-time kernel.
fn legacy_rref_macaulay_k23m3d3() -> Box<dyn Workload> {
    let (_, cols, m) = macaulay(23, 3, 3, 1);
    legacy_rref(m, cols)
}

/// Uniform random matrix of the `k5m3d5` Macaulay shape (4940 × 8357).
fn rref_random_4940x8357() -> Box<dyn Workload> {
    rref_counted(random_matrix(4940, 8357, 2), 8357)
}

/// The `k5m3d5` shape at its initial row weight (17 per row), random
/// support.
fn rref_random_4940x8357_w17() -> Box<dyn Workload> {
    rref_counted(random_weight_matrix(4940, 8357, 17, 3), 8357)
}

/// `pc_degree_harness::rank_and_refute` on the symmetrised-`S₄` ANF
/// Macaulay matrix at `n = 6, ℓ = 3, d = 4` (10 461 × 12 951), the
/// refutation-degree scan's own input.  The matrix is consumed; the
/// function returns `(rank, refuted)`.  The pivot columns of the reduced
/// rows are fingerprinted too: they are fixed by the row space, so any
/// echelon strategy must reproduce them.
fn rank_refute_anf_s4_n6l3d4() -> Box<dyn Workload> {
    let (rows, cols) = anf_s4_macaulay(6, 3, 4);
    Box::new(Fresh::new(rows, move |m| {
        let (rank, refuted) = rank_and_refute(m, cols);
        fp_leads(Fp::new().usize(rank).bool(refuted), m, rank).finish()
    }))
}

/// `sparse_macaulay::eliminate_high_columns` on the index-list form of a
/// decomposition cell, eliminating up to its degree-≤1 boundary.
fn sparse_high(n: u32, m: usize, d: u32, seed: u64) -> Box<dyn Workload> {
    let (_, cols, dense) = macaulay(n, m, d, seed);
    let (low_start, _) = column_boundaries(&decomposition_system(n, m, seed), d, cols);
    Box::new(Fresh::new(to_sparse(&dense), move |rows| {
        let e = eliminate_high_columns(std::mem::take(rows), cols, low_start);
        fp_sparse_elimination(&e)
    }))
}

fn sparse_high_macaulay_k5m3d5() -> Box<dyn Workload> {
    sparse_high(5, 3, 5, 0x5EED)
}

fn sparse_high_macaulay_k23m2d4() -> Box<dyn Workload> {
    sparse_high(23, 2, 4, 1)
}

/// `pc_degree_harness::sparse_rank_and_refute` (hash-map pivots, sorted
/// index-list rows) on the `k5m3d5` cell.  It returns only `(rank,
/// refuted)`; the pivots are internal.
fn sparse_rank_refute_macaulay_k5m3d5() -> Box<dyn Workload> {
    let (_, _, dense) = macaulay(5, 3, 5, 0x5EED);
    Box::new(Fresh::new(to_sparse(&dense), |rows| {
        let (rank, refuted) = sparse_rank_and_refute(std::mem::take(rows));
        Fp::new().usize(rank).bool(refuted).finish()
    }))
}

/// `matrix_f5_f2::F5Criterion::new` on a decomposition cell: the
/// lower-degree echelons (`PrefixEchelon`, leading-column reduction with
/// suffix XORs) that decide which Macaulay rows the F5 step skips, then
/// `prunes` for every `(generator, multiplier)` pair, as the `MatrixF5`
/// engine's row builder queries it.  Fingerprints every counter and every
/// verdict.
fn f5_criterion(n: u32, m: usize, d: u32, seed: u64) -> Box<dyn Workload> {
    let sys = decomposition_system(n, m, seed);
    let mask = if sys.n_vars == 64 {
        u64::MAX
    } else {
        (1u64 << sys.n_vars) - 1
    };
    let candidates: Vec<Vec<u64>> = sys
        .equations
        .iter()
        .map(|p| {
            let pdeg = poly_degree(p);
            if pdeg > d {
                Vec::new()
            } else {
                monomials_up_to(sys.n_vars, d - pdeg)
            }
        })
        .collect();
    Box::new(Closure(move || {
        let c = F5Criterion::new(&sys.equations, sys.n_vars, d, mask);
        let (rows, zero) = c.lower_level_rows();
        let (koszul, frob) = c.pruned_by_part();
        let mut fp = Fp::new()
            .u64(c.word_ops())
            .u64(c.pruned_count())
            .u64(rows)
            .u64(zero)
            .u64(koszul)
            .u64(frob);
        for (i, ts) in candidates.iter().enumerate() {
            let mut h = ts.len() as u64;
            for &t in ts {
                h = (h << 1 | c.prunes(i, t) as u64).rotate_left(7) ^ t;
                h = h.wrapping_mul(0x9e37_79b9_7f4a_7c15);
            }
            fp = fp.u64(h);
        }
        fp.finish()
    }))
}

fn f5_criterion_k5m3d7() -> Box<dyn Workload> {
    f5_criterion(5, 3, 7, 0x5EED)
}

fn f5_criterion_k23m2d6() -> Box<dyn Workload> {
    f5_criterion(23, 2, 6, 1)
}

// ── Registry ───────────────────────────────────────────────────────

pub fn register(kernels: &mut Vec<Kernel>) {
    let mut add = |id: &'static str, tier: Tier, desc: &'static str, setup| {
        kernels.push(Kernel {
            id,
            area: "gf2_la",
            desc,
            tier,
            setup,
        })
    };
    add(
        "gf2_la/rref_random_2048",
        Tier::Quick,
        "gf2_elim::rref on a dense uniformly random 2048x2048 matrix (seed 1)",
        rref_random_2048,
    );
    add(
        "gf2_la/rref_macaulay_k23m2d4",
        Tier::Quick,
        "gf2_elim::rref_counted on the n=23 m=2 d=4 decomposition Macaulay matrix (5842x8449, seed 1)",
        rref_macaulay_k23m2d4,
    );
    add(
        "gf2_la/rref_macaulay_k17m2d5",
        Tier::Quick,
        "gf2_elim::rref_counted on the n=17 m=2 d=5 decomposition Macaulay matrix (11849x6773, seed 1)",
        rref_macaulay_k17m2d5,
    );
    add(
        "gf2_la/rref_macaulay_k5m3d5",
        Tier::Quick,
        "gf2_elim::rref_counted on the n=5 m=3 d=5 decomposition Macaulay matrix (4940x8357, seed 0x5EED)",
        rref_macaulay_k5m3d5,
    );
    add(
        "gf2_la/rref_macaulay_k15m3d4",
        Tier::Quick,
        "gf2_elim::rref_counted on the n=15 m=3 d=4 decomposition Macaulay matrix (6105x13966, seed 1)",
        rref_macaulay_k15m3d4,
    );
    add(
        "gf2_la/rref_macaulay_k23m2d3_x16",
        Tier::Quick,
        "gf2_elim::rref_counted on 16 draws of the n=23 m=2 d=3 cell (529x1464 each, seeds 1..16)",
        rref_macaulay_k23m2d3_x16,
    );
    add(
        "gf2_la/echelon_macaulay_k23m2d4",
        Tier::Quick,
        "gf2_elim::echelon_counted on the n=23 m=2 d=4 decomposition Macaulay matrix (5842x8449, seed 1)",
        echelon_macaulay_k23m2d4,
    );
    add(
        "gf2_la/echelon_macaulay_k5m3d5",
        Tier::Quick,
        "gf2_elim::echelon_counted on the n=5 m=3 d=5 decomposition Macaulay matrix (4940x8357, seed 0x5EED)",
        echelon_macaulay_k5m3d5,
    );
    add(
        "gf2_la/legacy_rref_macaulay_k5m3d5",
        Tier::Quick,
        "koblitz_bench::rref_f2_legacy (block-4 Four Russians arena kernel) on the n=5 m=3 d=5 Macaulay matrix",
        legacy_rref_macaulay_k5m3d5,
    );
    add(
        "gf2_la/legacy_rref_macaulay_k23m3d3",
        Tier::Quick,
        "koblitz_bench::rref_f2_legacy (column-at-a-time kernel) on the wide n=23 m=3 d=3 Macaulay matrix (1334x13884)",
        legacy_rref_macaulay_k23m3d3,
    );
    add(
        "gf2_la/rref_random_4940x8357",
        Tier::Quick,
        "gf2_elim::rref_counted on a uniformly random matrix of the k5m3d5 shape (4940x8357, seed 2)",
        rref_random_4940x8357,
    );
    add(
        "gf2_la/rref_random_4940x8357_w17",
        Tier::Quick,
        "gf2_elim::rref_counted on a random 4940x8357 matrix of row weight 17, the k5m3d5 initial weight (seed 3)",
        rref_random_4940x8357_w17,
    );
    add(
        "gf2_la/rank_refute_anf_s4_n6l3d4",
        Tier::Quick,
        "pc_degree_harness::rank_and_refute on the symmetrised-S4 ANF Macaulay matrix n=6 l=3 d=4 (10461x12951)",
        rank_refute_anf_s4_n6l3d4,
    );
    add(
        "gf2_la/sparse_high_macaulay_k5m3d5",
        Tier::Quick,
        "sparse_macaulay::eliminate_high_columns on the n=5 m=3 d=5 Macaulay matrix as index lists",
        sparse_high_macaulay_k5m3d5,
    );
    add(
        "gf2_la/sparse_rank_refute_macaulay_k5m3d5",
        Tier::Quick,
        "pc_degree_harness::sparse_rank_and_refute on the n=5 m=3 d=5 Macaulay matrix as index lists",
        sparse_rank_refute_macaulay_k5m3d5,
    );
    add(
        "gf2_la/f5_criterion_k5m3d7",
        Tier::Quick,
        "matrix_f5_f2::F5Criterion::new (lower-degree prefix echelons) + every prunes() verdict, n=5 m=3 system at d=7",
        f5_criterion_k5m3d7,
    );
    add(
        "gf2_la/rref_macaulay_k11m2d5",
        Tier::Full,
        "gf2_elim::rref_counted on the n=11 m=2 d=5 decomposition Macaulay matrix (14861x21196, seed 1)",
        rref_macaulay_k11m2d5,
    );
    add(
        "gf2_la/f5_criterion_k23m2d6",
        Tier::Quick,
        "matrix_f5_f2::F5Criterion::new + every prunes() verdict, n=23 m=2 system at d=6 (5842-row level-4 echelon)",
        f5_criterion_k23m2d6,
    );
    add(
        "gf2_la/sparse_high_macaulay_k23m2d4",
        Tier::Full,
        "sparse_macaulay::eliminate_high_columns on the n=23 m=2 d=4 Macaulay matrix as index lists",
        sparse_high_macaulay_k23m2d4,
    );
}
