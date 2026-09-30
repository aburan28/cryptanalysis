//! Area `bool_gb`: Boolean (F_2) Gröbner bases: F4/F5 over F_2, Macaulay/XL, crossbred, FES.
//!
//! The Koblitz kernels solve the Weil-restricted Semaev systems the
//! decomposition oracle (`koblitz_index_calculus::groebner_decompose`)
//! builds, for fixed planted targets (sums of `m` factor-base points, so a
//! root exists) and fixed random targets.  The systems are built in the
//! untimed setup with `build_decomposition_system`; the timed region is
//! the Boolean solve alone, which is the stage this area owns.  Chained
//! (`m ≥ 3`) systems are handed over in the interleaved variable order,
//! exactly as `groebner_decompose` hands them to the default engine.
//!
//! Instruction counts (`perfbench run --instr` under callgrind with
//! `--toggle-collect=*perfbench_measured_region*`) see only the calling
//! thread.  Work that rayon dispatches to its pool — `gf2_elim`'s parallel
//! clears and `pack_rows` above their size gates, the matrix-F5 readback,
//! `pq_f4_f2`'s table build, the wide engine's subtree search — runs on a
//! pool worker even at `RAYON_NUM_THREADS=1` and is not counted.  Measured
//! per run on this file's kernels: the region misses about 18% of
//! `matrix_f4_deg4_m2_n23`, 36% of `matrix_f5_deg4_m2_n23`, 5% of
//! `f4_basis_m2_n17` and 97% of the `wide_*` kernels; the `solve_*`,
//! `crossbred_*` and `fes_*` kernels run entirely on the calling thread.

use crate::harness::{Closure, Fp, Kernel, Tier, Workload};
use cryptanalysis_suite::binary_ecc::BinaryPoint;
use cryptanalysis_suite::cryptanalysis::crossbred::{
    extract_crossbred, solve_crossbred, CrossbredParams, SearchOptions,
};
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, f4_word_ops_thread, matrix_f4_f2_counted, permute_poly,
    solve_boolean_system, FieldStructure, SolveOptions, SolveStats, SolverEngine, SplitRule,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base, KoblitzCurve,
};
use cryptanalysis_suite::cryptanalysis::matrix_f5_f2::matrix_f5_f2;
use cryptanalysis_suite::cryptanalysis::mq_fes::{
    gray_find_all_wide, gray_incremental_find_all, moebius_find_all, QuadraticForm,
};
use cryptanalysis_suite::cryptanalysis::mq_monica::monica_find_all;
use cryptanalysis_suite::cryptanalysis::pq_f4_f2::groebner_basis_f4;
use cryptanalysis_suite::cryptanalysis::pq_groebner_f2::{F2BoolMono, F2BoolPoly};
use cryptanalysis_suite::cryptanalysis::wide_groebner::wide_groebner_decompose;
use num_bigint::BigUint;
use rand::{rngs::StdRng, Rng, SeedableRng};

// ── Fingerprint helpers ─────────────────────────────────────────────

fn fp_poly(fp: Fp, p: &F2BoolPoly) -> Fp {
    let mut fp = fp.usize(p.n_vars).usize(p.terms.len());
    for t in &p.terms {
        fp = fp.u64(t.mask);
    }
    fp
}

fn fp_polys(mut fp: Fp, ps: &[F2BoolPoly]) -> Fp {
    fp = fp.usize(ps.len());
    for p in ps {
        fp = fp_poly(fp, p);
    }
    fp
}

fn fp_solve_stats(fp: Fp, s: &SolveStats) -> Fp {
    fp.usize(s.reductions)
        .usize(s.infeasible_branches)
        .usize(s.propagations)
        .usize(s.splits)
        .bool(s.exhausted)
        .u64(u64::from(s.max_degree_built))
        .usize(s.oversize)
        .usize(s.eliminated)
}

// ── Koblitz decomposition systems (setup only) ──────────────────────

/// One Boolean system: equations (in the order the solver receives them)
/// and the number of unknowns.
#[derive(Clone)]
struct BoolSystem {
    equations: Vec<F2BoolPoly>,
    n_vars: usize,
}

/// Fixed random-target scalars, the sequence `groebner_stage_bench` uses.
fn target_scalar(i: u32) -> BigUint {
    BigUint::from(1u64 + (i as u64).wrapping_mul(2_654_435_761) % 1_000_003)
}

/// The decomposition systems of `planted` planted and `random` random
/// targets on `K_a / F_2^n` (factor-base divisor `fi`, `m` summands).
/// Chains are permuted into the interleaved order when `interleave`.
fn koblitz_systems(
    a: u8,
    n: u32,
    fi: usize,
    m: usize,
    planted: usize,
    random: u32,
    seed: u64,
    interleave: bool,
) -> Vec<BoolSystem> {
    let kc = KoblitzCurve::new(a, n).expect("Koblitz curve exists");
    let fb = build_frobenius_factor_base(&kc, fi).expect("factor base exists");
    assert!(fb.m_can_decompose(&kc, m), "cell admissible for m");
    let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
    let mut rng = StdRng::seed_from_u64(seed);
    let mut targets = Vec::new();
    while targets.len() < planted {
        let t = (0..m).fold(BinaryPoint::Infinity, |acc, _| {
            kc.add(&acc, &fb.points[rng.gen_range(0..fb.points.len())])
        });
        if matches!(t, BinaryPoint::Affine { .. }) {
            targets.push(t);
        }
    }
    let g = kc.generator().clone();
    for i in 0..random {
        targets.push(kc.mul(&g, &target_scalar(i)));
    }
    targets
        .iter()
        .filter_map(|t| match t {
            BinaryPoint::Affine { x, .. } => Some(x.clone()),
            BinaryPoint::Infinity => None,
        })
        .map(|x_r| {
            let sys = build_decomposition_system(&fb.subspace_basis, &x_r, &kc.curve.b, m, &st)
                .expect("system fits in 64 unknowns");
            let equations = if interleave && m >= 3 {
                let perm = sys.interleaved_order(kc.n);
                sys.equations
                    .iter()
                    .map(|e| permute_poly(e, &perm))
                    .collect()
            } else {
                sys.equations.clone()
            };
            BoolSystem {
                equations,
                n_vars: sys.n_vars,
            }
        })
        .collect()
}

/// Solve every system; fingerprint the roots (in the order returned), the
/// solver's counters, and the word operations the solve charged on this
/// thread (the stage's counted unit, which `groebner_stage_bench` records
/// and AGENTS.md §10 asks to pin beside the output).
fn solve_all(systems: &[BoolSystem], opts: &SolveOptions) -> u64 {
    let mut fp = Fp::new();
    for s in systems {
        let before = f4_word_ops_thread();
        let (roots, stats) = solve_boolean_system(&s.equations, s.n_vars, opts);
        let word_ops = f4_word_ops_thread().wrapping_sub(before);
        fp = fp_solve_stats(fp.words(&roots), &stats).u64(word_ops);
    }
    fp.finish()
}

fn opts(engine: SolverEngine) -> SolveOptions {
    SolveOptions {
        engine,
        max_solutions: usize::MAX,
        node_budget: 20_000,
        split_rule: SplitRule::Auto,
    }
}

// ── Solver kernels ──────────────────────────────────────────────────

fn solve_inherited_m2_n23() -> Box<dyn Workload> {
    let systems = koblitz_systems(1, 23, 0, 2, 4, 4, 23, true);
    let o = opts(SolverEngine::InheritedF4 { max_degree: 3 });
    Box::new(Closure(move || solve_all(&systems, &o)))
}

fn solve_inherited_m3_n15() -> Box<dyn Workload> {
    let systems = koblitz_systems(0, 15, 1, 3, 4, 4, 15, true);
    let o = opts(SolverEngine::InheritedF4 { max_degree: 3 });
    Box::new(Closure(move || solve_all(&systems, &o)))
}

fn solve_inherited_m4_n15() -> Box<dyn Workload> {
    let systems = koblitz_systems(0, 15, 1, 4, 2, 2, 154, true);
    let o = opts(SolverEngine::InheritedF4 { max_degree: 3 });
    Box::new(Closure(move || solve_all(&systems, &o)))
}

fn solve_inherited_m3_n23() -> Box<dyn Workload> {
    let systems = koblitz_systems(0, 23, 0, 3, 1, 1, 233, true);
    let o = opts(SolverEngine::InheritedF4 { max_degree: 3 });
    Box::new(Closure(move || solve_all(&systems, &o)))
}

fn solve_matrixf4_m2_n17() -> Box<dyn Workload> {
    let systems = koblitz_systems(1, 17, 0, 2, 4, 4, 17, false);
    let o = opts(SolverEngine::MatrixF4 { max_degree: 3 });
    Box::new(Closure(move || solve_all(&systems, &o)))
}

fn solve_matrixf4_m3_n15() -> Box<dyn Workload> {
    let systems = koblitz_systems(0, 15, 1, 3, 1, 1, 15, false);
    let o = opts(SolverEngine::MatrixF4 { max_degree: 3 });
    Box::new(Closure(move || solve_all(&systems, &o)))
}

fn solve_matrixf5_m2_n17() -> Box<dyn Workload> {
    let systems = koblitz_systems(1, 17, 0, 2, 4, 4, 17, false);
    let o = opts(SolverEngine::MatrixF5 { max_degree: 3 });
    Box::new(Closure(move || solve_all(&systems, &o)))
}

fn solve_buchberger_m2_n9() -> Box<dyn Workload> {
    let systems = koblitz_systems(0, 9, 0, 2, 1, 1, 9, false);
    let o = opts(SolverEngine::Buchberger);
    Box::new(Closure(move || solve_all(&systems, &o)))
}

// ── One Macaulay step / full basis ──────────────────────────────────

fn matrix_f4_deg4_m2_n23() -> Box<dyn Workload> {
    let s = koblitz_systems(1, 23, 0, 2, 1, 0, 230, false).remove(0);
    Box::new(Closure(move || {
        let (rows, ops) = matrix_f4_f2_counted(&s.equations, s.n_vars, 4).expect("fits");
        fp_polys(Fp::new().u64(ops), &rows).finish()
    }))
}

fn matrix_f4_deg4_m3_n15() -> Box<dyn Workload> {
    let s = koblitz_systems(0, 15, 1, 3, 1, 0, 150, true).remove(0);
    Box::new(Closure(move || {
        let (rows, ops) = matrix_f4_f2_counted(&s.equations, s.n_vars, 4).expect("fits");
        fp_polys(Fp::new().u64(ops), &rows).finish()
    }))
}

fn matrix_f4_deg3_m3_n23() -> Box<dyn Workload> {
    let s = koblitz_systems(0, 23, 0, 3, 1, 0, 230, true).remove(0);
    Box::new(Closure(move || {
        let (rows, ops) = matrix_f4_f2_counted(&s.equations, s.n_vars, 3).expect("fits");
        fp_polys(Fp::new().u64(ops), &rows).finish()
    }))
}

fn matrix_f5_deg4_m2_n23() -> Box<dyn Workload> {
    let s = koblitz_systems(1, 23, 0, 2, 1, 0, 230, false).remove(0);
    Box::new(Closure(move || {
        let (rows, r) = matrix_f5_f2(&s.equations, s.n_vars, 4).expect("fits");
        let fp = Fp::new()
            .u64(u64::from(r.degree))
            .u64(r.rows_f4)
            .u64(r.rows_pruned)
            .u64(r.rows_built)
            .u64(r.cols)
            .u64(r.rank)
            .u64(r.zero_reductions)
            .u64(r.reduce_word_ops)
            .u64(r.criterion_word_ops)
            .u64(r.criterion_rows);
        fp_polys(fp, &rows).finish()
    }))
}

fn f4_basis_m2_n17() -> Box<dyn Workload> {
    let systems = koblitz_systems(1, 17, 0, 2, 2, 2, 17, false);
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for s in &systems {
            let (basis, st) = groebner_basis_f4(s.equations.clone(), s.n_vars, None);
            fp = fp_polys(fp, &basis)
                .u64(st.steps)
                .u64(st.pairs_reduced)
                .u64(st.field_pairs_reduced)
                .u64(st.pairs_product_skipped)
                .u64(st.pairs_chain_skipped)
                .u64(st.reducer_rows)
                .u64(st.matrix_rows_max)
                .u64(st.matrix_cols_max)
                .u64(st.matrix_rows_sum)
                .u64(st.word_xors)
                .u64(st.divisor_tests)
                .u64(st.new_elements)
                .u64(u64::from(st.solving_degree))
                .bool(st.oversize);
        }
        fp.finish()
    }))
}

fn f4_basis_random_n18() -> Box<dyn Workload> {
    let system = random_quadratic_polys(18, 36, 18);
    Box::new(Closure(move || {
        let (basis, st) = groebner_basis_f4(system.clone(), 18, None);
        fp_polys(Fp::new(), &basis)
            .u64(st.steps)
            .u64(st.matrix_rows_sum)
            .u64(st.word_xors)
            .u64(u64::from(st.solving_degree))
            .finish()
    }))
}

// ── Crossbred ───────────────────────────────────────────────────────

fn crossbred_m2_n23() -> Box<dyn Workload> {
    let systems = koblitz_systems(1, 23, 0, 2, 2, 2, 23, false);
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for s in &systems {
            let params = CrossbredParams {
                macaulay_degree: 3,
                enumerated: s.n_vars / 2,
                target_degree: 1,
                max_rows: 20_000,
            };
            let xb = extract_crossbred(&s.equations, s.n_vars, &params).expect("fits");
            let (roots, st) = solve_crossbred(&s.equations, &xb, &SearchOptions::default());
            let e = xb.stats;
            fp = fp_polys(fp, &xb.polys)
                .usize(e.macaulay_rows)
                .usize(e.macaulay_cols)
                .usize(e.bad_cols)
                .usize(e.kernel_dim)
                .usize(e.filters)
                .u64(e.word_ops)
                .words(&roots)
                .u64(st.points)
                .u64(st.survivors)
                .u64(st.linear_solves)
                .u64(st.candidates)
                .u64(st.verified)
                .u64(st.transform_word_ops)
                .u64(st.filter_word_ops)
                .u64(st.solve_row_ops)
                .bool(st.exhausted);
        }
        fp.finish()
    }))
}

// ── FES (quadratic exhaustive search) ───────────────────────────────

/// `m` random quadratic forms in `n` variables with a planted common zero.
fn random_quadratic_polys(n: usize, m: usize, seed: u64) -> Vec<F2BoolPoly> {
    let mut rng = StdRng::seed_from_u64(seed);
    let planted: u64 = rng.gen::<u64>() & ((1u64 << n) - 1);
    let mut monos: Vec<u64> = vec![0];
    for i in 0..n {
        monos.push(1 << i);
        for j in i + 1..n {
            monos.push((1 << i) | (1 << j));
        }
    }
    (0..m)
        .map(|_| {
            let chosen: Vec<u64> = monos
                .iter()
                .copied()
                .filter(|_| rng.gen::<bool>())
                .collect();
            let val = chosen.iter().filter(|&&t| t & planted == t).count() & 1;
            let mut terms: Vec<F2BoolMono> =
                chosen.into_iter().map(F2BoolMono::from_mask).collect();
            if val == 1 {
                terms.push(F2BoolMono::from_mask(0));
            }
            F2BoolPoly::from_monos(terms, n)
        })
        .collect()
}

fn forms_of(polys: &[F2BoolPoly]) -> Vec<QuadraticForm> {
    polys
        .iter()
        .map(|p| QuadraticForm::from_poly(p).expect("quadratic"))
        .collect()
}

fn fes_gray_m2_n23() -> Box<dyn Workload> {
    let systems: Vec<Vec<QuadraticForm>> = koblitz_systems(1, 23, 0, 2, 4, 4, 23, false)
        .iter()
        .map(|s| forms_of(&s.equations))
        .collect();
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for forms in &systems {
            let roots = gray_incremental_find_all(forms, usize::MAX).expect("fits");
            fp = fp.words(&roots);
        }
        fp.finish()
    }))
}

fn fes_gray_random_n28() -> Box<dyn Workload> {
    let forms = forms_of(&random_quadratic_polys(28, 32, 28));
    Box::new(Closure(move || {
        let roots = gray_incremental_find_all(&forms, usize::MAX).expect("fits");
        Fp::new().words(&roots).finish()
    }))
}

fn fes_wide_random_n30() -> Box<dyn Workload> {
    let forms = forms_of(&random_quadratic_polys(30, 32, 30));
    Box::new(Closure(move || {
        // Lane count is host dependent (16 AVX-512, 8 AVX2); the solution
        // set is not, but its order is, so it is sorted before hashing.
        match gray_find_all_wide(&forms, usize::MAX) {
            Some((mut roots, _lanes)) => {
                roots.sort_unstable();
                Fp::new().bool(true).words(&roots).finish()
            }
            None => Fp::new().bool(false).finish(),
        }
    }))
}

fn fes_moebius_random_n22() -> Box<dyn Workload> {
    let forms = forms_of(&random_quadratic_polys(22, 24, 22));
    Box::new(Closure(move || {
        let roots = moebius_find_all(&forms, usize::MAX).expect("fits");
        Fp::new().words(&roots).finish()
    }))
}

fn fes_monica_random_n25() -> Box<dyn Workload> {
    let forms = forms_of(&random_quadratic_polys(25, 32, 25));
    Box::new(Closure(move || match monica_find_all(&forms, usize::MAX) {
        Some(roots) => Fp::new().bool(true).words(&roots).finish(),
        None => Fp::new().bool(false).finish(),
    }))
}

// ── Wide (u128) chained engine ──────────────────────────────────────

/// `wide_groebner_decompose` on fixed targets.  The engine searches its
/// subtrees in parallel and returns whichever decomposition a thread finds
/// first, so a found decomposition (and the node count on the way to it)
/// can differ between runs at more than one thread.  A complete refutation
/// visits the whole tree whatever the frontier, so its verdict and every
/// counter are thread-count independent and are fingerprinted; a found
/// decomposition is fingerprinted as "found, and sums to the target" only.
fn wide_kernel(
    a: u8,
    n: u32,
    fi: usize,
    m: usize,
    planted: usize,
    random: u32,
) -> Box<dyn Workload> {
    let kc = KoblitzCurve::new(a, n).expect("Koblitz curve exists");
    let fb = build_frobenius_factor_base(&kc, fi).expect("factor base exists");
    assert!(fb.m_can_decompose(&kc, m), "cell admissible for m");
    let index_of = fb.index_map();
    let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
    let g = kc.generator().clone();
    let mut rng = StdRng::seed_from_u64(u64::from(n) * 100 + m as u64);
    let mut pts: Vec<BinaryPoint> = Vec::new();
    while pts.len() < planted {
        let t = (0..m).fold(BinaryPoint::Infinity, |acc, _| {
            kc.add(&acc, &fb.points[rng.gen_range(0..fb.points.len())])
        });
        if matches!(t, BinaryPoint::Affine { .. }) {
            pts.push(t);
        }
    }
    pts.extend((0..random).map(|i| kc.mul(&g, &target_scalar(1000 + i))));
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for t in &pts {
            let (found, s) = wide_groebner_decompose(&kc, &fb, &index_of, &st, t, m, 10_000_000);
            fp = match found {
                Some(idxs) => {
                    let sum = idxs
                        .iter()
                        .fold(BinaryPoint::Infinity, |acc, &i| kc.add(&acc, &fb.points[i]));
                    fp.u64(1).bool(sum == *t)
                }
                None => fp
                    .u64(0)
                    .usize(s.nodes)
                    .usize(s.reductions)
                    .usize(s.refuted)
                    .usize(s.leaves)
                    .usize(s.max_rows)
                    .usize(s.max_cols)
                    .bool(s.exhausted),
            };
        }
        fp.finish()
    }))
}

fn wide_refute_m3_n31() -> Box<dyn Workload> {
    wide_kernel(0, 31, 0, 3, 0, 2)
}

fn wide_refute_m4_n31() -> Box<dyn Workload> {
    wide_kernel(0, 31, 0, 4, 0, 1)
}

fn wide_mixed_m4_n15() -> Box<dyn Workload> {
    wide_kernel(0, 15, 1, 4, 0, 2)
}

fn wide_found_m5_n15() -> Box<dyn Workload> {
    wide_kernel(0, 15, 1, 5, 0, 2)
}

pub fn register(kernels: &mut Vec<Kernel>) {
    let mut k =
        |id: &'static str, desc: &'static str, tier: Tier, setup: fn() -> Box<dyn Workload>| {
            kernels.push(Kernel {
                id,
                area: "bool_gb",
                desc,
                tier,
                setup,
            })
        };
    k(
        "bool_gb/solve_inherited_m2_n23",
        "solve_boolean_system, default InheritedF4{3}, K_1/2^23 m=2 (22 vars): 4 planted + 4 random targets, all roots",
        Tier::Quick,
        solve_inherited_m2_n23,
    );
    k(
        "bool_gb/solve_inherited_m3_n15",
        "solve_boolean_system, default InheritedF4{3}, K_0/2^15 (divisor 1) m=3 chain (27 vars, interleaved): 4 planted + 4 random",
        Tier::Quick,
        solve_inherited_m3_n15,
    );
    k(
        "bool_gb/solve_inherited_m4_n15",
        "solve_boolean_system, default InheritedF4{3}, K_0/2^15 (divisor 1) m=4 chain (46 vars, interleaved): 2 planted + 2 random",
        Tier::Full,
        solve_inherited_m4_n15,
    );
    k(
        "bool_gb/solve_inherited_m3_n23",
        "solve_boolean_system, default InheritedF4{3}, K_0/2^23 m=3 chain (56 vars, interleaved): 1 planted + 1 random",
        Tier::Full,
        solve_inherited_m3_n23,
    );
    k(
        "bool_gb/solve_matrixf4_m2_n17",
        "solve_boolean_system, from-scratch MatrixF4{3}, K_1/2^17 m=2 (16 vars): 4 planted + 4 random targets",
        Tier::Quick,
        solve_matrixf4_m2_n17,
    );
    k(
        "bool_gb/solve_matrixf4_m3_n15",
        "solve_boolean_system, from-scratch MatrixF4{3}, K_0/2^15 (divisor 1) m=3 chain (layout order): 1 planted + 1 random",
        Tier::Full,
        solve_matrixf4_m3_n15,
    );
    k(
        "bool_gb/solve_matrixf5_m2_n17",
        "solve_boolean_system, MatrixF5{3}, K_1/2^17 m=2 (16 vars): 4 planted + 4 random targets",
        Tier::Quick,
        solve_matrixf5_m2_n17,
    );
    k(
        "bool_gb/solve_buchberger_m2_n9",
        "solve_boolean_system, Buchberger reference engine, K_0/2^9 m=2 (12 vars): 1 planted + 1 random",
        Tier::Full,
        solve_buchberger_m2_n9,
    );
    k(
        "bool_gb/matrix_f4_deg4_m2_n23",
        "matrix_f4_f2_counted at degree 4 on one K_1/2^23 m=2 system (22 vars): build + reduce + readback",
        Tier::Quick,
        matrix_f4_deg4_m2_n23,
    );
    k(
        "bool_gb/matrix_f4_deg4_m3_n15",
        "matrix_f4_f2_counted at degree 4 on one K_0/2^15 (divisor 1) m=3 chain system (27 vars, interleaved)",
        Tier::Quick,
        matrix_f4_deg4_m3_n15,
    );
    k(
        "bool_gb/matrix_f4_deg3_m3_n23",
        "matrix_f4_f2_counted at degree 3 on one K_0/2^23 m=3 chain system (56 vars, interleaved)",
        Tier::Quick,
        matrix_f4_deg3_m3_n23,
    );
    k(
        "bool_gb/matrix_f5_deg4_m2_n23",
        "matrix_f5_f2 at degree 4 on one K_1/2^23 m=2 system (F5 criterion + reduce)",
        Tier::Quick,
        matrix_f5_deg4_m2_n23,
    );
    k(
        "bool_gb/f4_basis_m2_n17",
        "pq_f4_f2::groebner_basis_f4 reduced basis of K_1/2^17 m=2 systems: 2 planted + 2 random",
        Tier::Quick,
        f4_basis_m2_n17,
    );
    k(
        "bool_gb/f4_basis_random_n18",
        "pq_f4_f2::groebner_basis_f4 of 36 random planted quadratics in 18 vars (seed 18)",
        Tier::Quick,
        f4_basis_random_n18,
    );
    k(
        "bool_gb/crossbred_m2_n23",
        "extract_crossbred(D=3,k=11) + solve_crossbred on K_1/2^23 m=2: 2 planted + 2 random",
        Tier::Quick,
        crossbred_m2_n23,
    );
    k(
        "bool_gb/fes_gray_m2_n23",
        "gray_incremental_find_all (libfes-lite Gray walk) on 8 K_1/2^23 m=2 systems (22 vars, 23 eqs)",
        Tier::Quick,
        fes_gray_m2_n23,
    );
    k(
        "bool_gb/fes_gray_random_n28",
        "gray_incremental_find_all on 32 random planted quadratics in 28 vars (seed 28)",
        Tier::Quick,
        fes_gray_random_n28,
    );
    k(
        "bool_gb/fes_wide_random_n30",
        "gray_find_all_wide (AVX-512/AVX2 lanes, runtime dispatch) on 32 random quadratics in 30 vars",
        Tier::Quick,
        fes_wide_random_n30,
    );
    k(
        "bool_gb/fes_moebius_random_n22",
        "moebius_find_all on 24 random planted quadratics in 22 vars (seed 22)",
        Tier::Quick,
        fes_moebius_random_n22,
    );
    k(
        "bool_gb/fes_monica_random_n25",
        "monica_find_all on 32 random planted quadratics in 25 vars (seed 25)",
        Tier::Quick,
        fes_monica_random_n25,
    );
    k(
        "bool_gb/wide_refute_m3_n31",
        "wide_groebner_decompose, K_0/2^31 m=3 (46 vars), 2 random targets (complete refutations)",
        Tier::Quick,
        wide_refute_m3_n31,
    );
    k(
        "bool_gb/wide_refute_m4_n31",
        "wide_groebner_decompose, K_0/2^31 m=4 (82 vars), 1 random target (complete refutation)",
        Tier::Full,
        wide_refute_m4_n31,
    );
    k(
        "bool_gb/wide_mixed_m4_n15",
        "wide_groebner_decompose, K_0/2^15 (divisor 1) m=4, 2 random targets (one refuted, one decomposed)",
        Tier::Quick,
        wide_mixed_m4_n15,
    );
    k(
        "bool_gb/wide_found_m5_n15",
        "wide_groebner_decompose, K_0/2^15 (divisor 1) m=5, 2 random targets (both decompose; verdict+verification fingerprinted)",
        Tier::Quick,
        wide_found_m5_n15,
    );
}
