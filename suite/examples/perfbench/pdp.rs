//! Area `pdp`: point decomposition — summation polynomials, their Weil
//! descent, and the decomposition oracles the index-calculus pipelines
//! call (`R = P_1 + … + P_m` over a Frobenius-invariant factor base).
//!
//! Cells follow the frozen L1 ladder of `examples/pdp_bench.rs`
//! (`docs/ic/perf/OPTIMIZATION_PLAN.md` §2, §6): balanced `m·ℓ ≈ n`, the
//! factor base chosen by the same rule (most points over `K_0`, `K_1` and
//! every divisor of the right degree), and targets that are either
//! **planted** (a sum of `m` base points, so a decomposition exists) or
//! **random** (`[k]G`, usually not decomposable, so the oracle has to
//! refute).  Curves, bases, pair tables and targets are built in the
//! untimed setup; the timed region is the oracle or construction alone.
//!
//! The Gröbner solve of a *prebuilt* system is `bool_gb`'s; the kernels
//! here time what the oracle does around it (system instantiation, lift)
//! and the other engines (enumeration, meet in the middle, SAT, the
//! pairs-and-solve `S₄` oracle).
//!
//! The kernels assume the solver and cache knobs are unset
//! (`SOLVER_SPLIT_RULE`, `F4_F2_MAX_ROWS`/`_COLS`, `IC_PREPROCESS_CACHE`,
//! `IC_TEMPLATE_MEMO`, `KIC_*`), as the index runner leaves them.  The
//! `instantiate_*` kernels time the per-thread `DecompositionTemplate`
//! memo that the discarded warm-up run fills, exactly as a decomposition
//! run pays it once per base and then per target.
//!
//! These are the crypto crate's `pdp` kernels, same IDs and inputs.  This
//! crate's `SolveStats` and `SatDecompositionStats` have no `unsupported`
//! flag, so a solve fingerprints the counters it has.
//!
//! Where the time went in the crypto crate's copies of these modules, from
//! which this crate's were forked (callgrind, one thread, survey of
//! 2026-09-26; not re-measured here): enumeration is the generic
//! `Vec`-backed `F2mElement` arithmetic of `KoblitzCurve::add` (Fermat
//! inversion, `reduce_words`, allocation); meet in the middle and the
//! pair-table build are `FastCurve::add_many` and `Gf2::batch_inv`; the
//! `S₄` subspace oracle is `roots_in_subspace` and `Poly::rem_monic`;
//! `descend` is half `F2BoolPoly::from_monos`' sorts; system construction
//! is `F2BoolPoly::add` and allocation; symbolic `S₅`/`S₆` is SipHash on
//! the monomial set.

use crate::harness::{Closure, Fp, Kernel, Tier, Workload};
use cryptanalysis_suite::binary_ecc::{BinaryPoint, F2mElement};
use cryptanalysis_suite::cryptanalysis::binary_semaev_s4::{weil_descend_s4, AnfPoly};
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, FieldStructure, SolveStats, SolverEngine,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base_from_divisor, enumerate_decompose, find_irreducible_sparse,
    groebner_decompose, invariant_factors, sat_decompose, FrobeniusFactorBase, KoblitzCurve,
    PairSumTable, SatDecompositionStats,
};
use cryptanalysis_suite::cryptanalysis::koblitz_relation_solver::{
    IncrementalRelationSolver, RowStatus,
};
use cryptanalysis_suite::cryptanalysis::koblitz_symmetrised::{
    build_symmetrised_factor_base, divisor_for_dimension, symmetrised_groebner_decompose,
};
use cryptanalysis_suite::cryptanalysis::polynomial_reuse::build_decomposition_system_reusing;
use cryptanalysis_suite::cryptanalysis::pq_descent_symbolic::descend;
use cryptanalysis_suite::cryptanalysis::pq_groebner_f2::F2BoolPoly;
use cryptanalysis_suite::cryptanalysis::semaev_decomp::{Gf2, SubspaceOracle};
use cryptanalysis_suite::cryptanalysis::semaev_leading_form::{semaev, F2Poly};
use num_bigint::BigUint;
use rand::{rngs::StdRng, Rng, SeedableRng};
use std::collections::HashMap;

// ── Fingerprint helpers ─────────────────────────────────────────────

fn fp_decomp(fp: Fp, d: &Option<Vec<usize>>) -> Fp {
    match d {
        None => fp.u64(u64::MAX),
        Some(idxs) => {
            let mut fp = fp.usize(idxs.len());
            for &i in idxs {
                fp = fp.usize(i);
            }
            fp
        }
    }
}

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

fn fp_sat_stats(fp: Fp, s: &SatDecompositionStats) -> Fp {
    fp.usize(s.solver_calls)
        .usize(s.models)
        .bool(s.refuted)
        .bool(s.exhausted)
        .usize(s.spurious)
        .usize(s.implied_rows)
        .u64(s.conflicts)
}

/// An ANF in a canonical order (its monomial set is order-free).
fn fp_anf(fp: Fp, p: &AnfPoly) -> Fp {
    let mut monos: Vec<&Vec<u32>> = p.monomials().collect();
    monos.sort_unstable();
    let mut fp = fp.usize(monos.len());
    for m in monos {
        fp = fp.usize(m.len());
        for &v in m {
            fp = fp.u64(u64::from(v));
        }
    }
    fp
}

// ── Ladder cells (setup only) ───────────────────────────────────────

/// One ladder cell: curve, factor base and the frozen targets
/// (`true` = planted).
struct Cell {
    kc: KoblitzCurve,
    fb: FrobeniusFactorBase,
    index_of: HashMap<(BigUint, BigUint), usize>,
    st: FieldStructure,
    m: usize,
    targets: Vec<(bool, BinaryPoint)>,
}

/// The base rule of `examples/pdp_bench.rs::choose_base`: over `K_0`
/// and `K_1`, every subset of [`invariant_factors`] of total degree `ell`
/// whose base reaches every cofactor class with `m` summands, keeping
/// the one with the most points (first in `(a, subset)` order on a tie).
fn choose_base(n: u32, ell: u32, m: usize) -> (KoblitzCurve, FrobeniusFactorBase) {
    let mut best: Option<(KoblitzCurve, FrobeniusFactorBase)> = None;
    for a in 0u8..=1 {
        let Some(kc) = KoblitzCurve::new(a, n) else {
            continue;
        };
        let degs: Vec<usize> = invariant_factors(&kc)
            .iter()
            .map(|f| f.degree().unwrap_or(0))
            .collect();
        let k = degs.len().min(16);
        for mask in 1u32..1 << k {
            let idx: Vec<usize> = (0..k).filter(|&i| mask >> i & 1 == 1).collect();
            if idx.iter().map(|&i| degs[i]).sum::<usize>() != ell as usize {
                continue;
            }
            let Some(fb) = build_frobenius_factor_base_from_divisor(&kc, &idx) else {
                continue;
            };
            if !fb.m_can_decompose(&kc, m) {
                continue;
            }
            if best
                .as_ref()
                .is_none_or(|b| fb.points.len() > b.1.points.len())
            {
                best = Some((kc.clone(), fb));
            }
        }
    }
    best.expect("ladder cell has an admissible base")
}

/// `planted` sums of `m` base points (affine only) and `random` points
/// `[k]G`, from a fixed seed.
fn cell(n: u32, ell: u32, m: usize, planted: usize, random: usize, seed: u64) -> Cell {
    let (kc, fb) = choose_base(n, ell, m);
    let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
    let index_of = fb.index_map();
    let mut rng = StdRng::seed_from_u64(seed ^ (u64::from(n) << 8) ^ m as u64);
    let mut targets = Vec::new();
    while targets.len() < planted {
        let t = (0..m).fold(BinaryPoint::Infinity, |acc, _| {
            kc.add(&acc, &fb.points[rng.gen_range(0..fb.points.len())])
        });
        if matches!(t, BinaryPoint::Affine { .. }) {
            targets.push((true, t));
        }
    }
    while targets.len() < planted + random {
        let k = BigUint::from(rng.gen_range(1u64..u64::MAX));
        let t = kc.mul(kc.generator(), &k);
        if matches!(t, BinaryPoint::Affine { .. }) {
            targets.push((false, t));
        }
    }
    Cell {
        kc,
        fb,
        index_of,
        st,
        m,
        targets,
    }
}

fn x_of(p: &BinaryPoint) -> &F2mElement {
    match p {
        BinaryPoint::Affine { x, .. } => x,
        BinaryPoint::Infinity => unreachable!("targets are affine"),
    }
}

// ── Decomposition oracles ───────────────────────────────────────────

/// `enumerate_decompose`: the exhaustive `|F|^{m−1}` reference oracle.
fn enumerate_on(n: u32, ell: u32, m: usize, planted: usize, random: usize) -> Box<dyn Workload> {
    let c = cell(n, ell, m, planted, random, 0x5044_5042);
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for (_, t) in &c.targets {
            fp = fp_decomp(fp, &enumerate_decompose(&c.kc, &c.fb, &c.index_of, t, c.m));
        }
        fp.finish()
    }))
}

fn enumerate_m2_n23() -> Box<dyn Workload> {
    enumerate_on(23, 11, 2, 8, 8)
}

fn enumerate_m3_n15() -> Box<dyn Workload> {
    enumerate_on(15, 5, 3, 8, 8)
}

/// `groebner_decompose` end to end: template instantiation, the default
/// engine's solve, and the lift of each root.
fn groebner_on(n: u32, ell: u32, m: usize, planted: usize, random: usize) -> Box<dyn Workload> {
    let c = cell(n, ell, m, planted, random, 0x4752_4f42);
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for (_, t) in &c.targets {
            let (d, stats) = groebner_decompose(
                &c.kc,
                &c.fb,
                &c.index_of,
                &c.st,
                t,
                c.m,
                SolverEngine::default(),
                20_000,
            );
            fp = fp_solve_stats(fp_decomp(fp, &d), &stats);
        }
        fp.finish()
    }))
}

fn groebner_m2_n17() -> Box<dyn Workload> {
    groebner_on(17, 8, 2, 8, 8)
}

fn groebner_m3_n9() -> Box<dyn Workload> {
    groebner_on(9, 3, 3, 16, 16)
}

/// `sat_decompose` with the ladder's settings (64 models, degree-2
/// Macaulay preprocessing).
fn sat_on(n: u32, ell: u32, m: usize, planted: usize, random: usize) -> Box<dyn Workload> {
    let c = cell(n, ell, m, planted, random, 0x5341_5442);
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for (_, t) in &c.targets {
            let (d, stats) = sat_decompose(&c.kc, &c.fb, &c.index_of, &c.st, t, c.m, 64, Some(2));
            fp = fp_sat_stats(fp_decomp(fp, &d), &stats);
        }
        fp.finish()
    }))
}

fn sat_m6_n7() -> Box<dyn Workload> {
    sat_on(7, 1, 6, 4, 4)
}

fn sat_m2_n17() -> Box<dyn Workload> {
    sat_on(17, 8, 2, 2, 2)
}

/// `PairSumTable::build`: every pair sum of the base, sorted by key.
fn pair_table_build_n31_l10() -> Box<dyn Workload> {
    let c = cell(31, 10, 3, 32, 32, 0x5041_4952);
    Box::new(Closure(move || {
        let table = PairSumTable::build(&c.kc, &c.fb).expect("table fits");
        let mut fp = Fp::new().usize(table.len()).str(table.tier());
        for (_, t) in &c.targets {
            let key = table.probe_key(table.curve().lift(t));
            for &(k, i, j) in table.lookup(key) {
                fp = fp.u64(k).u64(u64::from(i)).u64(u64::from(j));
            }
        }
        fp.finish()
    }))
}

/// `PairSumTable::decompose` (meet in the middle): `|F|^{m−2}` lookups
/// a target, the result re-checked in the general group arithmetic.
fn mitm_on(n: u32, ell: u32, m: usize, planted: usize, random: usize) -> Box<dyn Workload> {
    let c = cell(n, ell, m, planted, random, 0x4d49_544d);
    let table = PairSumTable::build(&c.kc, &c.fb).expect("table fits");
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for (_, t) in &c.targets {
            fp = fp_decomp(fp, &table.decompose(&c.kc, &c.fb, t, c.m));
        }
        fp.finish()
    }))
}

fn mitm_m3_n31() -> Box<dyn Workload> {
    mitm_on(31, 10, 3, 256, 256)
}

fn mitm_m4_n31() -> Box<dyn Workload> {
    mitm_on(31, 6, 4, 64, 64)
}

/// `SubspaceOracle::decompose`, the pairs-and-solve `S₄` oracle
/// (`semaev_decomp`): for each pair of subspace abscissae, the quartic
/// in the third and its roots in the subspace by `gcd(q, L_V mod q)`.
/// Random abscissae, `2^{3ℓ}/6 ≈ 2^{n−2}`, so some decompose and most
/// are refuted after all `2^ℓ(2^ℓ+1)/2` pairs.
fn subspace_oracle_n20_l7() -> Box<dyn Workload> {
    let n = 20;
    let irr = find_irreducible_sparse(n).expect("irreducible exists");
    let gf = Gf2::new(&irr);
    let mask = (1u64 << n) - 1;
    let mut rng = StdRng::seed_from_u64(0x5355_4253);
    let basis: Vec<u64> = (0..7).map(|i| 1u64 << (3 * i % n)).collect();
    let b = rng.gen::<u64>() & mask | 1;
    let oracle = SubspaceOracle::new(&basis, b, &gf);
    let targets: Vec<u64> = (0..8).map(|_| rng.gen::<u64>() & mask).collect();
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for &xr in &targets {
            let (w, pairs) = oracle.decompose(xr, &gf);
            fp = fp.u64(pairs);
            fp = match w {
                Some([a, b, c]) => fp.u64(1).u64(a).u64(b).u64(c),
                None => fp.u64(0),
            };
        }
        fp.finish()
    }))
}

/// `symmetrised_groebner_decompose`: the Artin–Schreier-frame system
/// of `koblitz_symmetrised` (the `sym F4` arm of `paired_bench`, with its
/// default options: matrix-F4 to degree 3, 200,000 nodes, subgroup
/// targets with `x ≠ 1`).
fn symmetrised_on(a: u8, n: u32, m: usize, targets: usize) -> Box<dyn Workload> {
    let kc = KoblitzCurve::new(a, n).expect("Koblitz curve exists");
    let divisor = divisor_for_dimension(n, (n + 1).div_ceil(m as u32)).expect("divisor");
    let fb = build_symmetrised_factor_base(&kc, &divisor).expect("symmetrised base");
    let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
    let r = kc.subgroup_order.to_u64_digits()[0].max(2);
    let mut rng = StdRng::seed_from_u64(0x5359_4d4d);
    let mut ts = Vec::new();
    while ts.len() < targets {
        let p = kc.mul(kc.generator(), &BigUint::from(rng.gen_range(1..r)));
        if matches!(&p, BinaryPoint::Affine { x, .. } if *x != F2mElement::one(n)) {
            ts.push(p);
        }
    }
    let engine = SolverEngine::MatrixF4 { max_degree: 3 };
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for t in &ts {
            let o = symmetrised_groebner_decompose(&kc, &fb, &st, t, m, engine, 200_000)
                .expect("system builds");
            fp = fp_decomp(fp, &o.relation)
                .bool(o.used_t)
                .bool(o.complete)
                .usize(o.n_vars)
                .usize(o.n_equations)
                .u64(u64::from(o.degree))
                .u64(o.effort)
                .u64(u64::from(o.built_degree))
                .usize(o.oversize);
        }
        fp.finish()
    }))
}

fn symmetrised_groebner_m3_n15() -> Box<dyn Workload> {
    symmetrised_on(1, 15, 3, 8)
}

fn symmetrised_groebner_m2_n17() -> Box<dyn Workload> {
    symmetrised_on(1, 17, 2, 8)
}

// ── Weil descent: building the Boolean systems ──────────────────────

/// `build_decomposition_system` from scratch (the symbolic field
/// arithmetic the template memo replaces), one system a target.
fn build_system_on(n: u32, ell: u32, m: usize, targets: usize) -> Box<dyn Workload> {
    let c = cell(n, ell, m, targets / 2, targets - targets / 2, 0x4255_494c);
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for (_, t) in &c.targets {
            let sys = build_decomposition_system(
                &c.fb.subspace_basis,
                x_of(t),
                &c.kc.curve.b,
                c.m,
                &c.st,
            )
            .expect("buildable");
            fp = fp_polys(fp.usize(sys.n_vars), &sys.equations);
        }
        fp.finish()
    }))
}

fn build_system_m2_n23() -> Box<dyn Workload> {
    build_system_on(23, 11, 2, 8)
}

fn build_system_m3_n15() -> Box<dyn Workload> {
    build_system_on(15, 5, 3, 32)
}

/// `build_decomposition_system_reusing`: the per-thread template
/// (built by the warm-up) instantiated for each target — `n` polynomial
/// additions a target.  This is what `groebner_decompose` and
/// `sat_decompose` call.
fn instantiate_on(n: u32, ell: u32, m: usize, targets: usize) -> Box<dyn Workload> {
    let c = cell(n, ell, m, targets / 2, targets - targets / 2, 0x494e_5354);
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for (_, t) in &c.targets {
            let sys = build_decomposition_system_reusing(
                &c.fb.subspace_basis,
                x_of(t),
                &c.kc.curve.b,
                c.m,
                &c.st,
            )
            .expect("buildable");
            fp = fp_polys(fp.usize(sys.n_vars), &sys.equations);
        }
        fp.finish()
    }))
}

fn instantiate_m2_n23() -> Box<dyn Workload> {
    instantiate_on(23, 11, 2, 256)
}

fn instantiate_m3_n15() -> Box<dyn Workload> {
    instantiate_on(15, 5, 3, 256)
}

/// `pq_descent_symbolic::descend`, the Weil descent the ic framework's
/// `descent-algebraic` oracle runs per target: `S_{m+1}` expanded over
/// linear forms in `F_{2^n}[v]/(v² − v)` and split into coordinates.
fn descend_on(n: u32, n_prime: u32, summands: u32, targets: usize) -> Box<dyn Workload> {
    let irr = find_irreducible_sparse(n).expect("irreducible exists");
    let gf = Gf2::new(&irr);
    let mask = (1u64 << n) - 1;
    let mut rng = StdRng::seed_from_u64(0x4445_5343 ^ u64::from(n) << 8 ^ u64::from(summands));
    let v_basis: Vec<u64> = (0..n_prime).map(|_| rng.gen::<u64>() & mask).collect();
    let b = rng.gen::<u64>() & mask | 1;
    let xs: Vec<u64> = (0..targets).map(|_| rng.gen::<u64>() & mask).collect();
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for &x_r in &xs {
            let sys = descend(&gf, b, x_r, &v_basis, summands).expect("dimension fits");
            fp = fp_polys(
                fp.usize(sys.n_vars).usize(sys.field_monomials),
                &sys.equations,
            );
        }
        fp.finish()
    }))
}

fn descend_s3_n31_np20() -> Box<dyn Workload> {
    descend_on(31, 20, 2, 64)
}

fn descend_s4_n23_np6() -> Box<dyn Workload> {
    descend_on(23, 6, 3, 2)
}

/// `binary_semaev_s4::weil_descend_s4`: the symmetrised `S₄` in
/// e-space and the x-to-e correspondence, for the Koblitz `b = 1`.
fn weil_descend_s4_sym_n17_l4() -> Box<dyn Workload> {
    let n = 17;
    let irr = find_irreducible_sparse(n).expect("irreducible exists");
    let gf = Gf2::new(&irr);
    let one = F2mElement::one(n);
    let mask = (1u64 << n) - 1;
    let mut rng = StdRng::seed_from_u64(0x5334_5359);
    let xs: Vec<F2mElement> = (0..8)
        .map(|_| gf.to_element(rng.gen::<u64>() & mask))
        .collect();
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for x_r in &xs {
            let s = weil_descend_s4(n, 4, &irr, &one, x_r);
            fp = fp.usize(s.correspondence.len());
            for row in &s.correspondence {
                for p in row {
                    fp = fp_anf(fp, p);
                }
            }
            fp = fp.usize(s.semaev.len());
            for p in &s.semaev {
                fp = fp_anf(fp, p);
            }
        }
        fp.finish()
    }))
}

// ── Summation polynomials ───────────────────────────────────────────

/// A symbolic polynomial's monomial set, sorted.
fn fp_f2poly(fp: Fp, p: &F2Poly) -> Fp {
    let mut monos: Vec<_> = p.terms.iter().collect();
    monos.sort_unstable();
    let mut fp = fp.usize(monos.len());
    for m in monos {
        fp = fp.bytes(m);
    }
    fp
}

/// `semaev_leading_form::semaev(4)`: the binary `S₅` symbolic in `a₆`,
/// by the Sylvester resultant `Res_Y(S₃, S₄)`.
fn semaev_s5_symbolic() -> Box<dyn Workload> {
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for _ in 0..16 {
            fp = fp_f2poly(fp, &semaev(4));
        }
        fp.finish()
    }))
}

/// `semaev_leading_form::semaev(5)`: the binary `S₆ = Res_Y(S₄, S₄)`.
fn semaev_s6_symbolic() -> Box<dyn Workload> {
    Box::new(Closure(move || fp_f2poly(Fp::new(), &semaev(5)).finish()))
}

// ── Relation linear algebra fed by the oracle ───────────────────────

/// `IncrementalRelationSolver::add_row`: `unknowns + 40` sparse
/// relation rows (three orbit columns and the target column, as the
/// `m = 3` driver feeds them) over a 61-bit prime.
fn relation_solver_u1024() -> Box<dyn Workload> {
    let unknowns = 1024usize;
    let p = (1u64 << 61) - 1;
    let modulus = BigUint::from(p);
    let mut rng = StdRng::seed_from_u64(0x5245_4c53);
    let rows: Vec<Vec<u64>> = (0..unknowns + 40)
        .map(|_| {
            let mut row = vec![0u64; unknowns + 2];
            for _ in 0..3 {
                row[rng.gen_range(0..unknowns)] = rng.gen_range(1..p);
            }
            row[unknowns] = rng.gen_range(1..p);
            row[unknowns + 1] = rng.gen_range(0..p);
            row
        })
        .collect();
    Box::new(Closure(move || {
        let mut solver = IncrementalRelationSolver::new(unknowns, &modulus).expect("fits a word");
        let mut fp = Fp::new();
        for row in &rows {
            fp = fp.u64(match solver.add_row(row.clone()) {
                RowStatus::Independent => 0,
                RowStatus::Dependent => 1,
                RowStatus::Inconsistent => 2,
            });
        }
        fp.usize(solver.rank())
            .usize(solver.dependent_rows())
            .u64(solver.target().unwrap_or(u64::MAX))
            .finish()
    }))
}

pub fn register(kernels: &mut Vec<Kernel>) {
    let mut add =
        |id: &'static str, desc: &'static str, tier: Tier, setup: fn() -> Box<dyn Workload>| {
            kernels.push(Kernel {
                id,
                area: "pdp",
                desc,
                tier,
                setup,
            });
        };
    add(
        "pdp/enumerate_m2_n23",
        "enumerate_decompose, ladder cell n=23 l=11 m=2, 8 planted + 8 random targets",
        Tier::Quick,
        enumerate_m2_n23,
    );
    add(
        "pdp/enumerate_m3_n15",
        "enumerate_decompose, ladder cell n=15 l=5 m=3, 8 planted + 8 random targets",
        Tier::Quick,
        enumerate_m3_n15,
    );
    add(
        "pdp/groebner_m2_n17",
        "groebner_decompose (default engine, 20k nodes), cell n=17 l=8 m=2, 8 planted + 8 random",
        Tier::Quick,
        groebner_m2_n17,
    );
    add(
        "pdp/groebner_m3_n9",
        "groebner_decompose (default engine, 20k nodes), cell n=9 l=3 m=3, 16 planted + 16 random",
        Tier::Quick,
        groebner_m3_n9,
    );
    add(
        "pdp/sat_m6_n7",
        "sat_decompose (64 models, Macaulay degree 2), cell n=7 l=1 m=6, 4 planted + 4 random",
        Tier::Quick,
        sat_m6_n7,
    );
    add(
        "pdp/sat_m2_n17",
        "sat_decompose (64 models, Macaulay degree 2), cell n=17 l=8 m=2, 2 planted + 2 random",
        Tier::Quick,
        sat_m2_n17,
    );
    add(
        "pdp/pair_table_build_n31_l10",
        "PairSumTable::build on cell n=31 l=10 (all pair sums, keyed and sorted)",
        Tier::Quick,
        pair_table_build_n31_l10,
    );
    add(
        "pdp/mitm_m3_n31",
        "PairSumTable::decompose, cell n=31 l=10 m=3, 256 planted + 256 random targets",
        Tier::Quick,
        mitm_m3_n31,
    );
    add(
        "pdp/mitm_m4_n31",
        "PairSumTable::decompose, cell n=31 l=6 m=4, 64 planted + 64 random targets",
        Tier::Quick,
        mitm_m4_n31,
    );
    add(
        "pdp/subspace_oracle_n20_l7",
        "semaev_decomp::SubspaceOracle::decompose (pairs-and-solve S4), n=20 l=7, 8 random abscissae",
        Tier::Quick,
        subspace_oracle_n20_l7,
    );
    add(
        "pdp/build_system_m2_n23",
        "build_decomposition_system from scratch (symbolic Weil descent of S3), n=23 l=11, 8 targets",
        Tier::Quick,
        build_system_m2_n23,
    );
    add(
        "pdp/build_system_m3_n15",
        "build_decomposition_system from scratch (chained S3), n=15 l=5 m=3, 32 targets",
        Tier::Quick,
        build_system_m3_n15,
    );
    add(
        "pdp/instantiate_m2_n23",
        "build_decomposition_system_reusing (template instantiation), n=23 l=11 m=2, 256 targets",
        Tier::Quick,
        instantiate_m2_n23,
    );
    add(
        "pdp/instantiate_m3_n15",
        "build_decomposition_system_reusing (template instantiation), n=15 l=5 m=3, 256 targets",
        Tier::Quick,
        instantiate_m3_n15,
    );
    add(
        "pdp/descend_s3_n31_np20",
        "pq_descent_symbolic::descend S3 (2 summands), n=31 n'=20, 64 targets",
        Tier::Quick,
        descend_s3_n31_np20,
    );
    add(
        "pdp/descend_s4_n23_np6",
        "pq_descent_symbolic::descend S4 (3 summands), n=23 n'=6, 2 targets",
        Tier::Quick,
        descend_s4_n23_np6,
    );
    add(
        "pdp/weil_descend_s4_sym_n17_l4",
        "binary_semaev_s4::weil_descend_s4 (symmetrised S4, e-space), n=17 l=4, 8 targets",
        Tier::Quick,
        weil_descend_s4_sym_n17_l4,
    );
    add(
        "pdp/semaev_s5_symbolic",
        "semaev_leading_form::semaev(4) x16: binary S5 by Sylvester resultant, symbolic in a6",
        Tier::Quick,
        semaev_s5_symbolic,
    );
    add(
        "pdp/semaev_s6_symbolic",
        "semaev_leading_form::semaev(5): binary S6 = Res(S4, S4), symbolic in a6",
        Tier::Full,
        semaev_s6_symbolic,
    );
    add(
        "pdp/symmetrised_groebner_m3_n15",
        "symmetrised_groebner_decompose (matrix-F4 deg 3, 200k nodes), K_1/2^15 m=3, 8 subgroup targets",
        Tier::Quick,
        symmetrised_groebner_m3_n15,
    );
    add(
        "pdp/symmetrised_groebner_m2_n17",
        "symmetrised_groebner_decompose (matrix-F4 deg 3, 200k nodes), K_1/2^17 m=2, 8 subgroup targets",
        Tier::Quick,
        symmetrised_groebner_m2_n17,
    );
    add(
        "pdp/relation_solver_u1024",
        "IncrementalRelationSolver::add_row, 1064 sparse rows over 1024 unknowns mod 2^61-1",
        Tier::Quick,
        relation_solver_u1024,
    );
}
