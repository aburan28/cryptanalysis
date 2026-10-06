//! Area `relation`: relation collection and the index-calculus pipelines
//! around it — the Koblitz pair-table rungs of `docs/ic/params/*.json`
//! that `ca-ic workflow` runs, the relation linear algebra mod `r`
//! (filtering + block Wiedemann, `koblitz_sparse_la`; the BigUint
//! Wiedemann and structured Gaussian elimination of `pq_wiedemann` /
//! `pq_sparse_la`), and the prime-field residual walks of `residual_walk`.
//!
//! The Koblitz kernels drive the library exactly as
//! `src/cli/tools/ic/workflow.rs` does for a rung:
//! `KoblitzCurve::subfield(1, n, a, 1)`, the rung's factor base
//! materialised from its spec (untimed), the folded pair table the v5
//! reference records for all three rungs, aimed work units through
//! `RelationCollector::collect_aimed`, `FactorBaseLogSolver` with the
//! default sparse linear algebra (extension units until the columns are
//! determined), then `IndividualLogSolver::solve` on every target, the
//! targets in parallel as the workflow's solve stage runs them.  The
//! fingerprints cover every relation, every counter the rung pins
//! (trials, relations, summands scanned, descent trials) and every
//! logarithm, never a wall time.
//!
//! The linear-algebra kernels solve planted systems (a random solution
//! `x`, rows drawn with the shape of an `m = 3` relation), so a solve
//! always has an answer to find; the modulus is the `k0n53` rung's
//! 45-bit subgroup order.
//!
//! The rung kernels reproduce the v5 reference's pinned counters exactly
//! (`k0n31`: 128 trials, 78 relations, 277,760 summands scanned, 52
//! descent trials; `k0n41`: 17,408 / 67 / 2,770,944 / 726; 32 of 32
//! logarithms each), checked on this crate when the kernels were added.
//!
//! These are the crypto crate's `relation` kernels, same IDs and inputs.
//! This crate's `IndividualLogSolver` has no `solve_report`: `solve`
//! returns the descent's report only with a logarithm, so the descent
//! fingerprint of an unsolved target is a marker alone.
//!
//! Where the time went in the crypto crate's copies of these modules, from
//! which this crate's were forked (callgrind, one thread, survey of
//! 2026-09-28, on a host with AVX-512F but no VPCLMULQDQ, so the scalar
//! `Gf2` path is also the native one; not re-measured here): the `k0n31`
//! rung is two-thirds `FrobeniusFactorBase::m_can_decompose`, the
//! cofactor-class walk in generic `binary_ecc` arithmetic (Fermat
//! inversions) that every `RelationCollector` construction pays; the scans
//! (collection and descent) are `Gf2::batch_inv`, `FastCurve::add_many_lazy`
//! and the Frobenius canonical key; the folded pair table computes every
//! pair sum and key twice (count pass, fill pass); `koblitz_sparse_la` is
//! `u128 %` (`__umodti3`) in `CsrMatrix::row_into` and the approximant
//! basis; the `pq_*` solvers are BigUint division and allocation
//! (`sparse_solve_mod_n` is 62 % `mod_inverse`, one per candidate pivot
//! row); the residual walk is dense `RelationSystem::insert`, `i128`
//! extended Euclid in `inv_mod` and SipHash.

use crate::harness::{Closure, Fp, Fresh, Kernel, Tier, Workload};
use cryptanalysis_suite::cryptanalysis::koblitz_factor_base_search::FactorBaseSpec;
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_subgroup_orbit_factor_base, point_key, CollectedRelation, CollectionReport,
    ColumnCoverage, DecompositionStrategy, FactorBaseLogSolver, FactorBaseLogTable,
    FrobeniusFactorBase, IndividualLogReport, IndividualLogSolver, KoblitzCurve, KoblitzIcOptions,
    LinearAlgebra, LogTableReport, PairSumTable, RelationCollector, RelationWorkUnit,
};
use cryptanalysis_suite::cryptanalysis::koblitz_sparse_la::{
    block_wiedemann_kernel, solve_sparse_system, BlockWiedemannOptions, BlockWiedemannReport,
    CsrMatrix, SparseRow, SparseSolveOptions, SparseSolveOutcome, SparseSolveReport,
};
use cryptanalysis_suite::cryptanalysis::pq_sparse_la::{
    sparse_solve_mod_n, SparseRow as PqSparseRow,
};
use cryptanalysis_suite::cryptanalysis::pq_wiedemann::wiedemann_solve;
use cryptanalysis_suite::cryptanalysis::residual_walk::{
    generate_instance, run_strategy, FactorBase as WalkFactorBase, Instance, Strategy,
    StrategyReport, WalkOptions,
};
use num_bigint::BigUint;
use rand::{rngs::StdRng, Rng, SeedableRng};
use rayon::prelude::*;

// ── Fingerprint helpers ─────────────────────────────────────────────

fn fp_big(fp: Fp, x: &BigUint) -> Fp {
    fp.words(&x.to_u64_digits())
}

fn fp_relations(mut fp: Fp, rels: &[CollectedRelation]) -> Fp {
    fp = fp.usize(rels.len());
    for r in rels {
        fp = fp.u64(r.trial).u64(r.a).usize(r.points.len());
        for &p in &r.points {
            fp = fp.usize(p);
        }
    }
    fp
}

fn fp_collection(fp: Fp, rep: &CollectionReport) -> Fp {
    fp.usize(rep.trials)
        .usize(rep.relations)
        .u64(rep.summands_scanned)
}

fn fp_wiedemann(fp: Fp, w: &BlockWiedemannReport) -> Fp {
    fp.usize(w.dimension)
        .usize(w.block_m)
        .usize(w.block_n)
        .usize(w.sequence_length)
        .usize(w.generator_degree)
        .usize(w.extra_steps)
        .usize(w.products)
}

fn fp_sparse_report(fp: Fp, s: &SparseSolveReport) -> Fp {
    let f = &s.filter;
    let mut fp = fp
        .usize(f.rows_in)
        .usize(f.columns_in)
        .usize(f.nonzeros_in)
        .usize(f.duplicates_removed)
        .usize(f.singletons_removed)
        .usize(f.excess_rows_removed)
        .usize(f.merged_columns)
        .usize(f.dependent_rows_dropped)
        .usize(f.uncovered_columns)
        .usize(f.rows_out)
        .usize(f.columns_out)
        .usize(f.nonzeros_out)
        .usize(s.core_dimension)
        .usize(s.core_nonzeros)
        .usize(s.attempts)
        .usize(s.reconstructed_columns);
    match &s.wiedemann {
        None => fp = fp.u64(u64::MAX),
        Some(w) => fp = fp_wiedemann(fp.u64(1), w),
    }
    fp
}

/// Everything a log-table report counts; the seconds are left out.
fn fp_log_report(fp: Fp, r: &LogTableReport) -> Fp {
    let fp = fp
        .usize(r.columns)
        .usize(r.trials)
        .usize(r.relations)
        .bool(r.verified)
        .usize(r.solve_attempts)
        .bool(r.sparse)
        .usize(r.rejected_relations)
        .usize(r.duplicate_relations);
    match &r.sparse_report {
        None => fp.u64(u64::MAX),
        Some(s) => fp_sparse_report(fp.u64(1), s),
    }
}

fn fp_table(mut fp: Fp, t: &FactorBaseLogTable) -> Fp {
    fp = fp.usize(t.columns.len());
    for (p, log) in &t.columns {
        let (x, y) = point_key(p);
        fp = fp_big(fp_big(fp_big(fp, &x), &y), log);
    }
    fp
}

/// A target's descent: the recovered logarithm, the probes drawn and the
/// relation that gave it.  This crate's `IndividualLogSolver::solve`
/// returns the report only with a logarithm, so an unsolved target is a
/// marker alone.
fn fp_descent(fp: Fp, r: &Option<(BigUint, IndividualLogReport)>) -> Fp {
    let Some((d, r)) = r else {
        return fp.u64(u64::MAX);
    };
    let fp = fp_big(fp.u64(1), d).usize(r.trials);
    match &r.relation {
        None => fp.u64(u64::MAX),
        Some(rel) => {
            let mut fp = fp.u64(rel.a).u64(rel.b).usize(rel.points.len());
            for &p in &rel.points {
                fp = fp.usize(p);
            }
            fp
        }
    }
}

// ── Koblitz rungs (`ic workflow`) ───────────────────────────────────

/// The factor base of `docs/ic/params/k0n31.json`: the divisor base
/// `{0, 1, 6}` pruned to the orbits that decompose the rung's targets.
const K0N31_SPEC: &str = r#"{"kind":"pruned","parent":{"indices":[0,1,6],"kind":"divisor"},
 "retained_abscissa_orbits":[2,5129,5130,5133,5134,5144,5145,5149,5384,5385,5387,5388,5390,
 5400,5403,5404,5405,5406,70664,70665,70667,70669,70671,70680,70681,70685,70922,70924,70925,
 70926,70936,70938,70940,70941,70942]}"#;

enum Target {
    Known(u64),
    Random(u64),
}

/// One rung's parameters, as its `docs/ic/params` file states them (the
/// workflow's defaults where the file is silent).
struct RungParams {
    degree: u32,
    unit_trials: u64,
    units: usize,
    max_units: usize,
    window: Option<usize>,
    aim: bool,
    max_trials: usize,
    seed: u64,
    summands: usize,
    descent_summands: Option<usize>,
    targets: Vec<Target>,
}

/// `ic_options_with_descent` + `with_linear_algebra(Sparse, default)`
/// of `src/cli/tools/ic/experiment.rs`, for the pair-table solver.
fn rung_options(p: &RungParams) -> KoblitzIcOptions {
    KoblitzIcOptions {
        m: p.summands,
        descent_m: p.descent_summands,
        collection_window: p.window,
        strategy: DecompositionStrategy::PairTable,
        collapse_negation: true,
        collapse_projected_orbits: true,
        crossbred: None,
        allow_direct_relation: false,
        max_trials: p.max_trials,
        seed: p.seed,
        linear_algebra: LinearAlgebra::Sparse(SparseSolveOptions::default()),
        ..KoblitzIcOptions::default()
    }
}

fn rung_curve(degree: u32) -> KoblitzCurve {
    KoblitzCurve::subfield(1, degree, 0, 1).expect("Koblitz curve a = 0")
}

/// `known_scalar` of the workflow: a fixed log, or one drawn from the
/// target's own seed.
fn target_points(
    c: &KoblitzCurve,
    targets: &[Target],
) -> Vec<cryptanalysis_suite::binary_ecc::BinaryPoint> {
    let r = c.subgroup_order.to_u64_digits()[0];
    targets
        .iter()
        .map(|t| {
            let k = match *t {
                Target::Known(k) => k,
                Target::Random(seed) => {
                    StdRng::seed_from_u64(seed ^ 0x534f_4c56_4552_5447).gen_range(1..r)
                }
            };
            c.mul(c.generator(), &BigUint::from(k))
        })
        .collect()
}

fn unit(p: &RungParams, u: usize) -> RelationWorkUnit {
    RelationWorkUnit {
        seed: p.seed,
        start: u as u64 * p.unit_trials,
        count: p.unit_trials,
    }
}

fn aim_of(cov: &Option<ColumnCoverage>) -> Option<Vec<u32>> {
    cov.as_ref()
        .map(|c| c.missing_points())
        .filter(|pts| !pts.is_empty())
}

/// Collect, solve the factor-base logs (extending as the workflow does)
/// and return the table, folding everything into `fp`.
fn precompute(
    c: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    p: &RungParams,
    ic: &KoblitzIcOptions,
    pair: &PairSumTable,
    mut fp: Fp,
) -> (FactorBaseLogTable, Fp) {
    let collector = RelationCollector::with_pair_table(c, fb, ic, Some(pair))
        .expect("base decomposes with this summand count");
    let new_cov = || {
        p.aim
            .then(|| ColumnCoverage::new(c, fb).expect("projected columns"))
    };
    let mut coverage = new_cov();
    let mut merged: Vec<CollectedRelation> = Vec::new();
    for u in 0..p.units {
        let aim = aim_of(&coverage);
        let (rels, rep) = collector.collect_aimed(unit(p, u), aim.as_deref());
        fp = fp_collection(fp_relations(fp, &rels), &rep);
        if let Some(cov) = coverage.as_mut() {
            cov.add(&rels);
        }
        merged.extend(rels);
    }
    let mut solver = FactorBaseLogSolver::new(c, fb, ic).expect("projected columns");
    solver.push(&merged);
    let mut outcome = solver.try_solve();
    let mut extend = new_cov();
    if let Some(cov) = extend.as_mut() {
        cov.add(&merged);
    }
    let mut next = p.units;
    while outcome.is_none() && next < p.max_units {
        let aim = aim_of(&extend);
        let (rels, rep) = collector.collect_aimed(unit(p, next), aim.as_deref());
        fp = fp_collection(fp_relations(fp, &rels), &rep);
        if let Some(cov) = extend.as_mut() {
            cov.add(&rels);
        }
        solver.push(&rels);
        outcome = solver.try_solve();
        next += 1;
    }
    fp = fp.usize(next);
    match outcome {
        Some((table, report)) => {
            fp = fp_table(fp_log_report(fp.u64(1), &report), &table);
            (table, fp)
        }
        None => {
            fp = fp_log_report(fp.u64(0), &solver.report());
            (
                FactorBaseLogTable {
                    columns: Vec::new(),
                },
                fp,
            )
        }
    }
}

fn descend_all(
    c: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    table: &FactorBaseLogTable,
    ic: &KoblitzIcOptions,
    pair: &PairSumTable,
    targets: &[cryptanalysis_suite::binary_ecc::BinaryPoint],
    fp: Fp,
) -> Fp {
    let solver = IndividualLogSolver::new(c, fb, table, ic, Some(pair)).expect("descent solver");
    let reports: Vec<Option<(BigUint, IndividualLogReport)>> = targets
        .par_iter()
        .with_max_len(1)
        .map(|q| solver.solve(q))
        .collect();
    reports.iter().fold(fp.usize(reports.len()), fp_descent)
}

struct Rung {
    params: RungParams,
    curve: KoblitzCurve,
    fb: FrobeniusFactorBase,
    ic: KoblitzIcOptions,
    targets: Vec<cryptanalysis_suite::binary_ecc::BinaryPoint>,
}

fn rung(params: RungParams, fb: impl FnOnce(&KoblitzCurve) -> FrobeniusFactorBase) -> Rung {
    let curve = rung_curve(params.degree);
    let fb = fb(&curve);
    let ic = rung_options(&params);
    let targets = target_points(&curve, &params.targets);
    Rung {
        params,
        curve,
        fb,
        ic,
        targets,
    }
}

fn folded(r: &Rung) -> PairSumTable {
    PairSumTable::build_folded_within(&r.curve, &r.fb, PairSumTable::DEFAULT_BYTE_BUDGET)
        .expect("folded pair table fits")
}

fn k0n31() -> Rung {
    let mut targets = vec![Target::Known(654_009), Target::Known(1_153_191)];
    targets.extend((100..130).map(Target::Random));
    rung(
        RungParams {
            degree: 31,
            unit_trials: 64,
            units: 2,
            max_units: 32,
            window: None,
            aim: false,
            max_trials: 200_000,
            seed: 1,
            summands: 3,
            descent_summands: None,
            targets,
        },
        |c| {
            let spec: FactorBaseSpec = serde_json::from_str(K0N31_SPEC).expect("spec parses");
            spec.materialize(c).expect("k0n31 base")
        },
    )
}

fn k0n41(targets: usize) -> Rung {
    rung(
        RungParams {
            degree: 41,
            unit_trials: 1024,
            units: 1,
            max_units: 2048,
            window: Some(164),
            aim: true,
            max_trials: 100_000,
            seed: 1,
            summands: 3,
            descent_summands: None,
            targets: (100..100 + targets as u64).map(Target::Random).collect(),
        },
        |c| build_subgroup_orbit_factor_base(c, 1, 4759).expect("k0n41 base"),
    )
}

fn k0n53(targets: usize) -> Rung {
    rung(
        RungParams {
            degree: 53,
            unit_trials: 2048,
            units: 1,
            max_units: 2048,
            window: Some(477),
            aim: true,
            max_trials: 20_000_000,
            seed: 1,
            summands: 3,
            descent_summands: Some(2),
            targets: (100..100 + targets as u64).map(Target::Random).collect(),
        },
        |c| build_subgroup_orbit_factor_base(c, 1, 15_000).expect("k0n53 base"),
    )
}

/// The whole rung after selection: pair table, collection with its
/// extension, factor-base logs, and the descent of every target.
fn whole_rung(r: Rung) -> Box<dyn Workload> {
    Box::new(Closure(move || {
        let pair = folded(&r);
        let fp = Fp::new().str(pair.tier()).usize(pair.len());
        let (table, fp) = precompute(&r.curve, &r.fb, &r.params, &r.ic, &pair, fp);
        descend_all(&r.curve, &r.fb, &table, &r.ic, &pair, &r.targets, fp).finish()
    }))
}

fn k0n31_rung() -> Box<dyn Workload> {
    whole_rung(k0n31())
}

fn k0n41_rung() -> Box<dyn Workload> {
    whole_rung(k0n41(32))
}

/// One unaimed work unit of the rung's collection (probe range fixed),
/// through the folded table built in setup.
fn collect_unit(r: Rung, u: usize, trials: u64) -> Box<dyn Workload> {
    let pair = folded(&r);
    Box::new(Closure(move || {
        let collector = RelationCollector::with_pair_table(&r.curve, &r.fb, &r.ic, Some(&pair))
            .expect("base decomposes");
        let work = RelationWorkUnit {
            seed: r.params.seed,
            start: u as u64 * trials,
            count: trials,
        };
        let (rels, rep) = collector.collect_aimed(work, None);
        fp_collection(fp_relations(Fp::new(), &rels), &rep).finish()
    }))
}

fn k0n53_collect() -> Box<dyn Workload> {
    collect_unit(k0n53(0), 7, 1024)
}

fn k0n41_collect() -> Box<dyn Workload> {
    collect_unit(k0n41(0), 3, 4096)
}

/// The folded pair table alone (4.6 % of the `k0n53` rung in the crypto
/// crate's survey).
fn pair_table(r: Rung) -> Box<dyn Workload> {
    Box::new(Closure(move || {
        let pair = folded(&r);
        let mut fp = Fp::new().str(pair.tier()).usize(pair.len());
        if let Some(st) = pair.folded_storage() {
            fp = fp
                .u64(u64::from(st.bucket_shift))
                .u64(st.present_mask)
                .bool(st.tagged);
            fp = fp.usize(st.bucket_start.len());
            for &b in st.bucket_start {
                fp = fp.u64(u64::from(b));
            }
            // A bucket's words are an unordered set: the parallel build
            // fills them in thread order, so fingerprint each sorted.
            fp = fp.usize(st.words.len());
            let mut bucket: Vec<u32> = Vec::new();
            for w in st.bucket_start.windows(2) {
                bucket.clear();
                bucket.extend_from_slice(&st.words[w[0] as usize..w[1] as usize]);
                bucket.sort_unstable();
                for &x in &bucket {
                    fp = fp.u64(u64::from(x));
                }
            }
            fp = fp.words(st.present);
        }
        fp.finish()
    }))
}

fn k0n41_pair_table() -> Box<dyn Workload> {
    pair_table(k0n41(0))
}

fn k0n53_pair_table() -> Box<dyn Workload> {
    pair_table(k0n53(0))
}

/// The descent of four random targets (two summands, walked probes)
/// against the `k0n53` log table, which setup computes once.
fn k0n53_descent() -> Box<dyn Workload> {
    let r = k0n53(4);
    let pair = folded(&r);
    let (table, _) = precompute(&r.curve, &r.fb, &r.params, &r.ic, &pair, Fp::new());
    assert!(!table.is_empty(), "k0n53 log table solved");
    Box::new(Closure(move || {
        descend_all(&r.curve, &r.fb, &table, &r.ic, &pair, &r.targets, Fp::new()).finish()
    }))
}

// ── Relation linear algebra mod r ───────────────────────────────────

/// The `k0n53` rung's subgroup order (45 bits, prime).
const R53: u64 = 21_044_858_204_113;

/// `rows` planted relations over `cols` columns, `weight` entries each
/// with full-size coefficients, and their solution.
fn planted_rows(cols: usize, rows: usize, weight: usize, seed: u64) -> Vec<SparseRow> {
    let mut rng = StdRng::seed_from_u64(seed);
    let x: Vec<u64> = (0..cols).map(|_| rng.gen_range(0..R53)).collect();
    (0..rows)
        .map(|i| {
            // Row i < cols names column i, so every column is covered.
            let mut entries: Vec<(u32, u64)> = Vec::with_capacity(weight);
            if i < cols {
                entries.push((i as u32, rng.gen_range(1..R53)));
            }
            while entries.len() < weight {
                let c = rng.gen_range(0..cols) as u32;
                if entries.iter().all(|&(d, _)| d != c) {
                    entries.push((c, rng.gen_range(1..R53)));
                }
            }
            let rhs = entries.iter().fold(0u128, |acc, &(c, v)| {
                (acc + v as u128 * x[c as usize] as u128) % R53 as u128
            }) as u64;
            SparseRow::new(entries, rhs, R53)
        })
        .collect()
}

fn fp_outcome(fp: Fp, o: &SparseSolveOutcome) -> Fp {
    match o {
        SparseSolveOutcome::Solved(x) => fp.u64(1).words(x),
        SparseSolveOutcome::Undetermined => fp.u64(2),
        SparseSolveOutcome::Inconsistent => fp.u64(3),
    }
}

/// The pipeline's sparse solve (filter, merge, block Wiedemann on the
/// core, reconstruct) on a planted `m = 3`-shaped system.
fn sparse_solve_c4800() -> Box<dyn Workload> {
    let cols = 4800;
    let rows = planted_rows(cols, cols + 48, 3, 0x5eed_0001);
    let opts = SparseSolveOptions::default();
    Box::new(Closure(move || {
        let (outcome, rep) = solve_sparse_system(&rows, cols, R53, &opts);
        fp_sparse_report(fp_outcome(Fp::new(), &outcome), &rep).finish()
    }))
}

/// `block_wiedemann_kernel` on a square CSR operator with a planted
/// kernel vector (every row is orthogonal to it through its last column).
fn block_wiedemann_n() -> Box<dyn Workload> {
    let n = 768usize;
    let weight = 12;
    let mut rng = StdRng::seed_from_u64(0x5eed_0002);
    let v: Vec<u64> = (0..n).map(|_| rng.gen_range(1..R53)).collect();
    let inv_last = BigUint::from(v[n - 1])
        .modpow(&BigUint::from(R53 - 2), &BigUint::from(R53))
        .to_u64_digits()[0];
    let rows: Vec<SparseRow> = (0..n)
        .map(|_| {
            let mut entries: Vec<(u32, u64)> = Vec::with_capacity(weight + 1);
            while entries.len() < weight {
                let c = rng.gen_range(0..n - 1) as u32;
                if entries.iter().all(|&(d, _)| d != c) {
                    entries.push((c, rng.gen_range(1..R53)));
                }
            }
            let dot = entries.iter().fold(0u128, |acc, &(c, a)| {
                (acc + a as u128 * v[c as usize] as u128) % R53 as u128
            }) as u64;
            // a_last · v_last = −dot
            let last = ((R53 - dot) % R53) as u128 * inv_last as u128 % R53 as u128;
            entries.push(((n - 1) as u32, last as u64));
            SparseRow::new(entries, 0, R53)
        })
        .collect();
    let csr = CsrMatrix::from_rows(&rows, n, R53);
    let opts = BlockWiedemannOptions::default();
    Box::new(Closure(move || {
        match block_wiedemann_kernel(&csr, &opts, 7) {
            None => Fp::new().u64(u64::MAX).finish(),
            Some((k, rep)) => fp_wiedemann(Fp::new().words(&k), &rep).finish(),
        }
    }))
}

/// The Petit–Quisquater BigUint solvers on a planted `m = 3`-shaped
/// system mod the Mersenne prime `2^127 − 1`.
fn pq_rows(cols: usize, rows: usize, seed: u64) -> (Vec<PqSparseRow>, Vec<BigUint>, BigUint) {
    let n = (BigUint::from(1u8) << 127) - 1u8;
    let mut rng = StdRng::seed_from_u64(seed);
    let big = |rng: &mut StdRng| BigUint::from(rng.gen::<u128>()) % &n;
    let x: Vec<BigUint> = (0..cols).map(|_| big(&mut rng)).collect();
    let mut out = Vec::with_capacity(rows);
    let mut rhs = Vec::with_capacity(rows);
    for _ in 0..rows {
        let mut entries: Vec<(usize, BigUint)> = Vec::new();
        while entries.len() < 3 {
            let c = rng.gen_range(0..cols);
            if entries.iter().all(|(d, _)| *d != c) {
                entries.push((c, big(&mut rng)));
            }
        }
        let b = entries
            .iter()
            .fold(BigUint::from(0u8), |acc, (c, v)| (acc + v * &x[*c]) % &n);
        rhs.push(b.clone());
        out.push(PqSparseRow::from_entries(entries, b));
    }
    (out, rhs, n)
}

fn pq_wiedemann_c160() -> Box<dyn Workload> {
    let (rows, rhs, n) = pq_rows(160, 160, 0x5eed_0003);
    Box::new(Closure(move || {
        match wiedemann_solve(&rows, &rhs, 160, &n, 11) {
            None => Fp::new().u64(u64::MAX),
            Some(x) => x.iter().fold(Fp::new().usize(x.len()), fp_big),
        }
        .finish()
    }))
}

fn pq_sparse_c640() -> Box<dyn Workload> {
    let (rows, _, n) = pq_rows(640, 672, 0x5eed_0004);
    // The solver consumes its rows: a fresh copy each sample.
    Box::new(Fresh::new(rows, move |rows: &mut Vec<PqSparseRow>| {
        match sparse_solve_mod_n(std::mem::take(rows), 640, 320, &n) {
            None => Fp::new().u64(u64::MAX),
            Some(v) => fp_big(Fp::new().u64(1), &v),
        }
        .finish()
    }))
}

// ── Residual walks (prime field) ────────────────────────────────────

fn fp_strategy(fp: Fp, r: &StrategyReport) -> Fp {
    let mut fp = fp
        .u64(r.p)
        .u64(r.n)
        .usize(r.factor_base)
        .u64(r.oracle_ops)
        .u64(r.oracle_hits)
        .u64(r.neighbour_collisions)
        .u64(r.samples)
        .u64(r.accepted)
        .usize(r.table_entries)
        .u64(r.walks)
        .u64(r.abandoned_walks)
        .u64(r.setup_ops)
        .u64(r.walk_ops)
        .u64(r.replay_ops)
        .u64(r.verify_ops)
        .u64(r.total_ops)
        .u64(r.collisions_trivial)
        .u64(r.collisions_direct)
        .u64(r.collisions_fb_only)
        .u64(r.collisions_mixed)
        .u64(r.full_decompositions)
        .u64(r.relations_verified)
        .u64(r.relations_failed_verification)
        .u64(r.relations_independent)
        .u64(r.relations_dependent)
        .usize(r.rank)
        .bool(r.solved);
    fp = match r.recovered {
        None => fp.u64(u64::MAX),
        Some(d) => fp.u64(d),
    };
    match r.ops_at_solve {
        None => fp.u64(u64::MAX),
        Some(o) => fp.u64(o),
    }
}

/// The `kappa` protocol's tuned local-mutation walk
/// (`examples/residual_walk_bench.rs`), three seeds at 22 bits, B = 256.
fn residual_walk_batch() -> Box<dyn Workload> {
    let cases: Vec<(Instance, WalkFactorBase, WalkOptions)> = (1..=3u64)
        .map(|seed| {
            let inst = generate_instance(22, seed);
            let fb = WalkFactorBase::build(&inst.curve, 256);
            let opts = WalkOptions {
                k: 3,
                max_ops: 1 << 34,
                seed,
                negation_map: true,
                diff_table: true,
                segment_len: 512,
                continue_after_collision: true,
                ..WalkOptions::default()
            };
            (inst, fb, opts)
        })
        .collect();
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for (inst, fb, opts) in &cases {
            fp = fp_strategy(
                fp,
                &run_strategy(inst, fb, Strategy::LocalMutationWalk, opts),
            );
        }
        fp.finish()
    }))
}

pub fn register(kernels: &mut Vec<Kernel>) {
    let mut add = |id, desc, tier, setup| {
        kernels.push(Kernel {
            id,
            area: "relation",
            desc,
            tier,
            setup,
        })
    };
    add(
        "relation/koblitz_rung_k0n31",
        "ic workflow k0n31 rung after selection: folded pair table, 2x64-probe collection (+extension), sparse logs, descent of 32 targets",
        Tier::Quick,
        k0n31_rung,
    );
    add(
        "relation/koblitz_rung_k0n41",
        "ic workflow k0n41-subgroup-aimed rung after selection: folded table, aimed w=164 collection until determined, sparse logs, descent of 32 targets",
        Tier::Full,
        k0n41_rung,
    );
    add(
        "relation/koblitz_collect_k0n53_w477_u1024",
        "RelationCollector::collect_aimed, one unaimed 1024-probe unit at k0n53 (window 477, m = 3, folded pair table)",
        Tier::Quick,
        k0n53_collect,
    );
    add(
        "relation/koblitz_collect_k0n41_w164_u4096",
        "RelationCollector::collect_aimed, one unaimed 4096-probe unit at k0n41 (window 164, m = 3, folded pair table)",
        Tier::Quick,
        k0n41_collect,
    );
    add(
        "relation/koblitz_pair_table_k0n41_folded",
        "PairSumTable::build_folded_within on the k0n41 rung's 4759-point subgroup-orbit base",
        Tier::Quick,
        k0n41_pair_table,
    );
    add(
        "relation/koblitz_pair_table_k0n53_folded",
        "PairSumTable::build_folded_within on the k0n53 rung's 15,000-point subgroup-orbit base",
        Tier::Full,
        k0n53_pair_table,
    );
    add(
        "relation/koblitz_descent_k0n53_m2_x4",
        "IndividualLogSolver::solve (m = 2 walked descent) of 4 random k0n53 targets against the solved log table",
        Tier::Quick,
        k0n53_descent,
    );
    add(
        "relation/sparse_solve_r45_c4800_w3",
        "koblitz_sparse_la::solve_sparse_system (filter, merge, block Wiedemann on a ~750 core) on a planted weight-3 system, 4800 columns + 48 rows, mod the k0n53 order",
        Tier::Quick,
        sparse_solve_c4800,
    );
    add(
        "relation/block_wiedemann_r45_n768_w13",
        "koblitz_sparse_la::block_wiedemann_kernel (4x4 blocks) on a 768-square CSR operator, 13 entries a row, planted kernel",
        Tier::Quick,
        block_wiedemann_n,
    );
    add(
        "relation/pq_wiedemann_m127_c160",
        "pq_wiedemann::wiedemann_solve on a planted square weight-3 system, 160 columns mod 2^127-1",
        Tier::Quick,
        pq_wiedemann_c160,
    );
    add(
        "relation/pq_sparse_solve_m127_c640",
        "pq_sparse_la::sparse_solve_mod_n (structured elimination) for one column of a planted weight-3 system, 640 columns + 32 rows mod 2^127-1",
        Tier::Quick,
        pq_sparse_c640,
    );
    add(
        "relation/residual_walk_lmw_b22_x3",
        "residual_walk::run_strategy LocalMutationWalk (k = 3, negation map, diff table, segments of 512), 22-bit curves, B = 256, seeds 1-3",
        Tier::Quick,
        residual_walk_batch,
    );
}
