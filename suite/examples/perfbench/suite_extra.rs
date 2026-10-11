//! Kernels for the modules that exist only in `cryptanalysis_suite` (they
//! have no counterpart in the `crypto` crate): the F_2 Macaulay kernel
//! (`f4_gf2`), its lockstep batch driver (`f4_batch`) and the host half of
//! the GPU backend (`f4_gpu`); integer factorisation (`factoring`: QS, the
//! NFS line siever and GF(2) dependency solver, GNFS end to end, p − 1,
//! Brent rho); the weak-curve attacks (`weak_curves`: Smart, MOV,
//! Pohlig–Hellman); and the prime-field automorphism-orbit index calculus
//! (`prime_orbit_index_calculus`).
//!
//! Areas: F4 over F_2 is `bool_gb`; factorisation (relation sieving,
//! relation-matrix algebra and the p − 1 / rho factor finders) is
//! `relation`, as is the orbit index calculus; the weak-curve attacks and
//! the orbit rho baseline are `dlp`.
//!
//! Every kernel fixes its seeds and its thread count where the entry point
//! takes one (`QsParams::threads`, `NfsParams::threads` = 1), so the
//! fingerprint does not depend on `RAYON_NUM_THREADS`.  The F4 lockstep
//! kernel reads the solver's environment switches (`F4_F2_*`, the engine
//! override) exactly as the research pipelines do; the runner leaves them
//! unset.

use crate::harness::{Closure, Fp, Kernel, Tier, Workload};
use cryptanalysis_suite::binary_ecc::BinaryPoint;
use cryptanalysis_suite::cryptanalysis::ec_index_calculus_curves::CurveKind;
use cryptanalysis_suite::cryptanalysis::f4_batch::{
    solve_lockstep, BatchDecider, CpuDecider, DecisionRequest, LockstepOutcome, LockstepReport,
};
use cryptanalysis_suite::cryptanalysis::f4_gf2::{
    self, Decision, KernelCounters, KernelOptions, MacaulayCaps,
};
use cryptanalysis_suite::cryptanalysis::f4_gpu::PackedBatch;
use cryptanalysis_suite::cryptanalysis::factoring::arith::{is_prime_u64, is_probable_prime};
use cryptanalysis_suite::cryptanalysis::factoring::nfs::linalg::{
    filtered_excess, find_dependencies, parity_vector, LinalgStats,
};
use cryptanalysis_suite::cryptanalysis::factoring::nfs::poly::IntPoly;
use cryptanalysis_suite::cryptanalysis::factoring::nfs::polysel::{base_m, skewness};
use cryptanalysis_suite::cryptanalysis::factoring::nfs::sieve::{
    sieve_segment, FactorBases, Relation, SieveConfig,
};
use cryptanalysis_suite::cryptanalysis::factoring::{
    gnfs, pm1, qs, rho, GnfsParams, NfsParams, NfsReport, Pm1Params, QsParams, RhoParams,
};
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, FieldStructure, SolveOptions, SolveStats, SolverEngine,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base, KoblitzCurve,
};
use cryptanalysis_suite::cryptanalysis::pq_groebner_f2::F2BoolPoly;
use cryptanalysis_suite::cryptanalysis::prime_orbit_index_calculus::{
    generate_instance, rho_baseline, run_known_answer, GeneratedInstance, OrbitIcOptions, RhoJumps,
    RhoReport, ScaledShape,
};
use cryptanalysis_suite::cryptanalysis::weak_curves::arith::{AffinePoint, Ec};
use cryptanalysis_suite::cryptanalysis::weak_curves::{
    anomalous_curve_cm, mov_attack, pohlig_hellman_attack, smart_attack, MovOptions,
    PohligHellmanOptions, SmartOptions,
};
use cryptanalysis_suite::ecc::curve::CurveParams;
use cryptanalysis_suite::ecc::point::Point;
use num_bigint::{BigInt, BigUint, RandBigInt};
use num_traits::{One, ToPrimitive, Zero};
use rand::{rngs::StdRng, Rng, SeedableRng};
use rayon::prelude::*;
use std::collections::HashMap;

// ── Fingerprint helpers ──────────────────────────────────────────────────

fn fp_big(fp: Fp, x: &BigUint) -> Fp {
    fp.words(&x.to_u64_digits())
}

fn fp_opt_big(fp: Fp, x: &Option<BigUint>) -> Fp {
    match x {
        Some(v) => fp_big(fp.bool(true), v),
        None => fp.bool(false),
    }
}

fn fp_linalg(fp: Fp, s: &LinalgStats) -> Fp {
    // Every field but `seconds`.
    fp.usize(s.rows_in)
        .usize(s.cols_in)
        .usize(s.rows_filtered)
        .usize(s.cols_filtered)
        .usize(s.dense_rows)
        .usize(s.dense_cols)
        .usize(s.rank)
        .usize(s.dependencies)
}

fn fp_counters(fp: Fp, k: &KernelCounters) -> Fp {
    // Every counter but the three nanosecond timers.
    fp.bool(k.built)
        .bool(k.oversize)
        .u64(k.rows)
        .u64(k.cols)
        .u64(k.eliminated_rows)
        .u64(k.eliminated_cols)
        .u64(k.f5_skipped)
        .u64(k.rank)
        .u64(k.word_ops)
}

/// A position-dependent fold of many words into one, one multiply a word,
/// for outputs large enough that the byte-wise [`Fp`] would dominate the
/// kernel's own cost.  Every word still reaches the fingerprint.
struct Fold(u64);

impl Fold {
    fn new() -> Self {
        Fold(0x9e37_79b9_7f4a_7c15)
    }
    #[inline]
    fn word(&mut self, x: u64) {
        self.0 = (self.0 ^ x).wrapping_mul(0xff51_afd7_ed55_8ccd);
        self.0 ^= self.0 >> 29;
    }
}

fn fold_poly(f: &mut Fold, p: &F2BoolPoly) {
    f.word(p.n_vars as u64);
    f.word(p.terms.len() as u64);
    for t in &p.terms {
        f.word(t.mask);
    }
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

// ── bool_gb: the F_2 Macaulay kernel and the lockstep splitting search ───

/// The caps `f4_gf2::default_caps` returns with no environment override,
/// fixed here so the replay kernels do not read the environment.
const CAPS: MacaulayCaps = MacaulayCaps {
    max_rows: 20_000,
    max_cols: 40_000,
};

/// Target scalars of `examples/f4_batch_bench.rs`.
fn target_scalar(i: u32) -> BigUint {
    BigUint::from(1u64 + (i as u64).wrapping_mul(2_654_435_761) % 1_000_003)
}

/// The `m`-summand Semaev decomposition systems of `targets` points
/// `[k_i]G` on the Koblitz curve `K_a/2^n`, over its first Frobenius
/// factor base: the systems `groebner_decompose_batch` hands the lockstep
/// solver.
fn koblitz_systems(a: u8, n: u32, m: usize, targets: u32) -> Vec<(Vec<F2BoolPoly>, usize)> {
    let kc = KoblitzCurve::new(a, n).expect("Koblitz curve");
    let fb = build_frobenius_factor_base(&kc, 0).expect("factor base");
    let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
    let g = kc.generator().clone();
    (0..targets)
        .filter_map(|i| {
            let BinaryPoint::Affine { x, .. } = kc.mul(&g, &target_scalar(i)) else {
                return None;
            };
            build_decomposition_system(&fb.subspace_basis, &x, &kc.curve.b, m, &st)
                .map(|s| (s.equations, s.n_vars))
        })
        .collect()
}

/// The solver options of `groebner_decompose` at node budget 4096, on the
/// matrix-F4 engine through degree 3: the engine the lockstep driver runs
/// (the default engine, inherited F4, is solved system by system by the
/// recursive solver instead and never reaches the batch decider).
fn lockstep_options() -> SolveOptions {
    SolveOptions {
        engine: SolverEngine::MatrixF4 { max_degree: 3 },
        max_solutions: usize::MAX,
        node_budget: 4096,
        ..SolveOptions::default()
    }
}

/// Forwards to the host kernel and keeps a copy of every request (as
/// `examples/f4_batch_bench.rs` part 2 does).
struct Recorder {
    requests: Vec<(Vec<F2BoolPoly>, usize, u32)>,
}

impl BatchDecider for Recorder {
    fn name(&self) -> String {
        "recorder".into()
    }

    fn decide(
        &mut self,
        requests: &[DecisionRequest<'_>],
        caps: MacaulayCaps,
    ) -> Vec<(Option<Decision>, KernelCounters)> {
        for r in requests {
            self.requests.push((r.polys.to_vec(), r.n_vars, r.degree));
        }
        CpuDecider.decide(requests, caps)
    }
}

/// The Macaulay decisions the lockstep searches on `systems` request, in
/// the order they request them.
fn recorded_requests(systems: &[(Vec<F2BoolPoly>, usize)]) -> Vec<(Vec<F2BoolPoly>, usize, u32)> {
    let mut rec = Recorder {
        requests: Vec::new(),
    };
    let _ = solve_lockstep(systems, &lockstep_options(), &mut rec, &|_, _| false);
    assert!(
        !rec.requests.is_empty(),
        "the lockstep solver requested nothing"
    );
    rec.requests
}

fn fp_lockstep(outcomes: &[LockstepOutcome], report: &LockstepReport) -> u64 {
    let mut fp = Fp::new()
        .usize(report.rounds)
        .usize(report.requests)
        .usize(report.max_round)
        .usize(outcomes.len());
    for o in outcomes {
        fp = fp.words(&o.solutions);
        fp = fp_solve_stats(fp, &o.stats);
        fp = fp.bool(o.accepted.is_some()).u64(o.accepted.unwrap_or(0));
    }
    fp.finish()
}

struct LockstepWork {
    systems: Vec<(Vec<F2BoolPoly>, usize)>,
    opts: SolveOptions,
}

impl Workload for LockstepWork {
    fn run(&mut self) -> u64 {
        let (outcomes, report) =
            solve_lockstep(&self.systems, &self.opts, &mut CpuDecider, &|_, _| false);
        fp_lockstep(&outcomes, &report)
    }
}

fn f4batch_lockstep_k1_17_m2_x24() -> Box<dyn Workload> {
    Box::new(LockstepWork {
        systems: koblitz_systems(1, 17, 2, 24),
        opts: lockstep_options(),
    })
}

/// Recorded requests, replayed through one of the kernel's entry points.
struct Replay {
    requests: Vec<(Vec<F2BoolPoly>, usize, u32)>,
}

fn replay_k1_17_m2_x24() -> Replay {
    Replay {
        requests: recorded_requests(&koblitz_systems(1, 17, 2, 24)),
    }
}

struct DecideReplay(Replay);

impl Workload for DecideReplay {
    fn run(&mut self) -> u64 {
        let opts = KernelOptions { f5: true };
        let mut fp = Fp::new().usize(self.0.requests.len());
        for (polys, n_vars, degree) in &self.0.requests {
            let (d, k) = f4_gf2::decide_with(polys, *n_vars, *degree, CAPS, opts);
            fp = fp_counters(fp, &k);
            match d {
                None => fp = fp.bool(false),
                Some(d) => {
                    fp = fp.bool(true).bool(d.refuted).usize(d.forced.len());
                    for (v, b) in d.forced {
                        fp = fp.u64(u64::from(v)).bool(b);
                    }
                }
            }
        }
        fp.finish()
    }
}

fn f4gf2_decide_replay_k1_17() -> Box<dyn Workload> {
    Box::new(DecideReplay(replay_k1_17_m2_x24()))
}

/// Every eighth recorded degree-3 request, lifted to degree 4 — where the
/// F5 and field-equation criteria fire on these quadratic systems (they
/// cannot below `D = 2·deg f`), so the F5 plan's symbolic preprocessing
/// runs.
fn f4gf2_decide_d4_f5_k1_17() -> Box<dyn Workload> {
    let requests = replay_k1_17_m2_x24()
        .requests
        .into_iter()
        .filter(|r| r.2 == 3)
        .step_by(8)
        .map(|(p, v, _)| (p, v, 4))
        .collect();
    Box::new(DecideReplay(Replay { requests }))
}

struct ProfileReplay(Replay);

impl Workload for ProfileReplay {
    fn run(&mut self) -> u64 {
        let opts = KernelOptions { f5: true };
        let mut fp = Fp::new().usize(self.0.requests.len());
        for (polys, n_vars, degree) in &self.0.requests {
            let (p, k) = f4_gf2::profile_with(polys, *n_vars, *degree, CAPS, opts);
            fp = fp_counters(fp, &k);
            match p {
                None => fp = fp.bool(false),
                Some(p) => {
                    fp = fp
                        .bool(true)
                        .u64(p.rank)
                        .bool(p.refuted)
                        .usize(p.forced.len());
                    for (v, b) in p.forced {
                        fp = fp.u64(u64::from(v)).bool(b);
                    }
                }
            }
        }
        fp.finish()
    }
}

fn f4gf2_profile_replay_k1_17() -> Box<dyn Workload> {
    Box::new(ProfileReplay(replay_k1_17_m2_x24()))
}

/// Every other recorded request (the full readback costs about four
/// decisions).
struct RowsReplay(Replay);

impl Workload for RowsReplay {
    fn run(&mut self) -> u64 {
        let opts = KernelOptions { f5: true };
        let mut fp = Fp::new().usize(self.0.requests.len());
        let mut fold = Fold::new();
        for (polys, n_vars, degree) in self.0.requests.iter().step_by(2) {
            let (rows, k) = f4_gf2::matrix_rows_with(polys, *n_vars, *degree, CAPS, opts);
            fp = fp_counters(fp, &k);
            match rows {
                None => fp = fp.bool(false),
                Some(rows) => {
                    fp = fp.bool(true).usize(rows.len());
                    for r in &rows {
                        fold_poly(&mut fold, r);
                    }
                }
            }
        }
        fp.u64(fold.0).finish()
    }
}

fn f4gf2_matrix_rows_replay_k1_17() -> Box<dyn Workload> {
    Box::new(RowsReplay(replay_k1_17_m2_x24()))
}

struct PackReplay(Replay);

impl Workload for PackReplay {
    fn run(&mut self) -> u64 {
        let requests: Vec<DecisionRequest<'_>> = self
            .0
            .requests
            .iter()
            .map(|(p, v, d)| DecisionRequest {
                polys: p,
                n_vars: *v,
                degree: *d,
            })
            .collect();
        let b = PackedBatch::pack_with(&requests, true);
        let mut fold = Fold::new();
        fold.word(b.terms.len() as u64);
        for &t in &b.terms {
            fold.word(t);
        }
        for v in [
            &b.poly_start,
            &b.sys_poly_start,
            &b.sys_meta,
            &b.skip_bits,
            &b.skip_start,
        ] {
            fold.word(v.len() as u64);
            for &x in v {
                fold.word(u64::from(x));
            }
        }
        Fp::new()
            .u64(fold.0)
            .u64(b.scratch_words)
            .usize(b.len())
            .finish()
    }
}

fn f4gpu_pack_f5_replay_k1_17() -> Box<dyn Workload> {
    Box::new(PackReplay(replay_k1_17_m2_x24()))
}

// ── relation: factoring ──────────────────────────────────────────────────

fn big(s: &str) -> BigUint {
    s.parse().expect("decimal")
}

fn fp_nfs_report(fp: Fp, r: &NfsReport) -> Fp {
    let mut fp = fp_opt_big(fp, &r.factor);
    fp = fp_opt_big(fp, &r.cofactor)
        .bool(r.verified)
        .str(r.failure.as_deref().unwrap_or(""))
        .bool(r.found_in_polyselect)
        .str(&r.polynomial);
    fp = fp_big(fp, &r.m)
        .u64(r.inert_prime)
        .u64(r.rational_bound)
        .u64(r.algebraic_bound)
        .usize(r.rational_fb_size)
        .usize(r.algebraic_fb_size)
        .u64(r.large_prime_bound)
        .usize(r.quadratic_characters)
        .u64(r.sieve_half_width)
        .u64(r.lines_sieved)
        .u64(r.cells_sieved)
        .u64(r.candidates)
        .usize(r.full_relations)
        .usize(r.partial_relations)
        .usize(r.dependencies_tried)
        .usize(r.sqrt_attempts.len());
    fp_linalg(fp, &r.linalg)
}

/// QS on `n = p·q` with one thread and a fixed seed.
fn qs_kernel(p: &str, q: &str) -> Box<dyn Workload> {
    let n = big(p) * big(q);
    let params = QsParams {
        threads: 1,
        seed: 1,
        ..QsParams::default()
    };
    Box::new(Closure(move || {
        let r = qs(&n, &params, None);
        assert!(r.verified, "qs failed: {:?}", r.failure);
        let mut fp = fp_opt_big(Fp::new(), &r.factor);
        fp = fp_opt_big(fp, &r.cofactor)
            .u64(r.multiplier)
            .usize(r.factor_base_size)
            .u64(r.largest_prime)
            .u64(u64::from(r.sieve_half_width))
            .u64(r.large_prime_bound)
            .usize(r.primes_per_a)
            .u64(r.a_values)
            .u64(r.polynomials)
            .u64(r.candidates)
            .usize(r.full_relations)
            .usize(r.partial_relations)
            .usize(r.dependencies_tried);
        fp_linalg(fp, &r.linalg).finish()
    }))
}

fn qs_semiprime_20d() -> Box<dyn Workload> {
    // 3267000013 · 10000000019 (the qs unit test's 20-digit case).
    qs_kernel("3267000013", "10000000019")
}

fn qs_semiprime_30d() -> Box<dyn Workload> {
    qs_kernel("100000000000000003", "1000000000039")
}

fn qs_semiprime_40d() -> Box<dyn Workload> {
    qs_kernel("10000000000000000051", "100000000000000000039")
}

/// The first primes above `10^24` and `10^25` (found in setup).
fn qs_semiprime_50d() -> Box<dyn Workload> {
    let next_prime = |x: BigUint| {
        let mut c = x + 1u32;
        while !is_probable_prime(&c) {
            c += 1u32;
        }
        c
    };
    let p = next_prime(BigUint::from(10u32).pow(24));
    let q = next_prime(BigUint::from(10u32).pow(25));
    qs_kernel(&p.to_string(), &q.to_string())
}

/// A fixed GNFS polynomial pair: the degree-3 base-`m` expansion (leading
/// coefficient 1) of the 40-digit semiprime of the `qs` tests, with the
/// sieve parameters `nfs::run_core` picks for 40 digits.
struct NfsSetup {
    f: IntPoly,
    m: BigUint,
    fb: FactorBases,
    rat_lp: u64,
    alg_lp: u64,
    a_half: i64,
}

fn nfs_setup_40d() -> NfsSetup {
    let n = big("10000000000000000051") * big("100000000000000000039");
    let (f, m) = base_m(&n, 3, 1).expect("base-m polynomial");
    // default_bounds(40) = (30000, 30000, 3e8); a_half = 0.35·√(area·skew/2).
    let bound = 30_000u64;
    let area = 3e8f64;
    let skew = skewness(&f);
    let a_half = (0.35 * (area * skew / 2.0).sqrt()).clamp(8192.0, (1u64 << 31) as f64) as i64;
    let fb = FactorBases::build(&f, &m, bound, bound);
    NfsSetup {
        f,
        m,
        fb,
        rat_lp: bound * 80,
        alg_lp: bound * 80,
        a_half,
    }
}

impl NfsSetup {
    fn config(&self) -> SieveConfig<'_> {
        SieveConfig {
            f: &self.f,
            m: BigInt::from(self.m.clone()),
            m_f64: self.m.to_f64().unwrap_or(f64::MAX),
            fb: &self.fb,
            rat_lp: self.rat_lp,
            alg_lp: self.alg_lp,
            slack_bits: 4.0,
            min_sieve_prime: 30,
        }
    }
}

fn fold_relation(f: &mut Fold, r: &Relation) {
    f.word(r.a as u64);
    f.word(r.b);
    f.word(u64::from(r.rat_negative));
    f.word(r.rat.len() as u64);
    for &p in &r.rat {
        f.word(p);
    }
    f.word(r.alg.len() as u64);
    for &(p, root) in &r.alg {
        f.word(p);
        f.word(root);
    }
}

/// Lines `b = 1 ..= LINES` of the 40-digit pair over `[−A, A)`, one line
/// per rayon task, results in line order.
const NFS_SIEVE_LINES: u64 = 8;

struct NfsSieve(NfsSetup);

impl Workload for NfsSieve {
    fn run(&mut self) -> u64 {
        let s = &self.0;
        let cfg = s.config();
        let outs: Vec<_> = (1..=NFS_SIEVE_LINES)
            .into_par_iter()
            .map(|b| sieve_segment(&cfg, b, -s.a_half, s.a_half))
            .collect();
        let mut fp = Fp::new().u64(s.a_half as u64);
        let mut fold = Fold::new();
        for o in &outs {
            fp = fp.u64(o.candidates).u64(o.cells).usize(o.relations.len());
            for r in &o.relations {
                fold_relation(&mut fold, r);
            }
        }
        fp.u64(fold.0).finish()
    }
}

fn nfs_line_sieve_40d_b8() -> Box<dyn Workload> {
    Box::new(NfsSieve(nfs_setup_40d()))
}

/// Relation rows as `nfs::run_core` builds them (sign, rational primes and
/// algebraic ideals, parity-reduced; no quadratic characters), sieved on
/// the 40-digit pair until singleton removal leaves `surplus` more rows
/// than columns.
fn nfs_rows_40d(surplus: usize) -> Vec<Vec<u32>> {
    let s = nfs_setup_40d();
    let cfg = s.config();
    let mut keys: HashMap<(u64, u64), u32> = HashMap::new();
    let mut rows: Vec<Vec<u32>> = Vec::new();
    let mut b = 1u64;
    loop {
        let batch: Vec<_> = (b..b + 16)
            .into_par_iter()
            .map(|bb| sieve_segment(&cfg, bb, -s.a_half, s.a_half))
            .collect();
        b += 16;
        for o in batch {
            for rel in &o.relations {
                let mut key = |k: (u64, u64)| {
                    let next = keys.len() as u32;
                    *keys.entry(k).or_insert(next)
                };
                let mut cols = Vec::new();
                if rel.rat_negative {
                    cols.push(key((0, 1)));
                }
                for &p in &rel.rat {
                    cols.push(key((p, u64::MAX)));
                }
                for &(p, r) in &rel.alg {
                    cols.push(key((p, r)));
                }
                rows.push(parity_vector(cols));
            }
        }
        let (r, c) = filtered_excess(&rows);
        if r >= c + surplus {
            return rows;
        }
        assert!(b < 4096, "the 40-digit sieve did not reach its excess");
    }
}

fn nfs_linalg_deps_40d() -> Box<dyn Workload> {
    let rows = nfs_rows_40d(32);
    Box::new(Closure(move || {
        let (deps, stats) = find_dependencies(&rows, 32, 32);
        let mut fp = fp_linalg(Fp::new(), &stats).usize(deps.len());
        for d in &deps {
            fp = fp.usize(d.len());
            for &i in d {
                fp = fp.usize(i);
            }
        }
        fp.finish()
    }))
}

fn gnfs_semiprime_30d() -> Box<dyn Workload> {
    let n = big("100000000000000003") * big("1000000000039");
    let params = GnfsParams {
        nfs: NfsParams {
            threads: 1,
            ..NfsParams::default()
        },
        ..GnfsParams::default()
    };
    Box::new(Closure(move || {
        let r = gnfs(&n, &params, None);
        assert!(r.verified, "gnfs failed: {:?}", r.failure);
        fp_nfs_report(Fp::new(), &r).finish()
    }))
}

/// A `bits`-bit prime `p` with `p − 1 = 2·s·L`: `s` a product of primes
/// below 1000 and `L` the prime just above `large`, so p − 1 finds it in
/// stage 2 once it reaches `L`.
fn pm1_prime(bits: u64, large: u64, rng: &mut StdRng) -> BigUint {
    let mut l = large | 1;
    while !is_prime_u64(l) {
        l += 2;
    }
    let small = [
        3u64, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71,
    ];
    loop {
        let mut p = BigUint::from(2 * l);
        while p.bits() < bits - 6 {
            p *= small[rng.gen_range(0..small.len())];
        }
        let p = p + 1u32;
        if is_probable_prime(&p) {
            return p;
        }
    }
}

fn pm1_stage2_95bit() -> Box<dyn Workload> {
    let mut rng = StdRng::seed_from_u64(0x0070_6d31);
    let p = pm1_prime(50, 3_000_000, &mut rng);
    // q = 2·L' + 1 with L' prime > 2^40: q − 1 is not B2-smooth.
    let q = loop {
        let l = rng.gen_range(1u64 << 44..1u64 << 45);
        if is_prime_u64(l) && is_prime_u64(2 * l + 1) {
            break BigUint::from(2 * l + 1);
        }
    };
    let n = &p * &q;
    let params = Pm1Params::default();
    Box::new(Closure(move || {
        let r = pm1(&n, &params);
        assert!(r.verified, "p-1 found no factor");
        let fp = fp_opt_big(Fp::new(), &r.factor);
        fp_opt_big(fp, &r.cofactor)
            .u64(u64::from(r.stage))
            .usize(r.stage1_primes)
            .usize(r.stage2_primes)
            .finish()
    }))
}

fn random_prime_u64(bits: u32, rng: &mut StdRng) -> u64 {
    loop {
        let c = (rng.gen::<u64>() >> (64 - bits)) | (1 << (bits - 1)) | 1;
        if is_prime_u64(c) {
            return c;
        }
    }
}

fn fp_rho(fp: Fp, r: &cryptanalysis_suite::cryptanalysis::factoring::RhoResult) -> Fp {
    let fp = fp_opt_big(fp, &r.factor);
    fp_opt_big(fp, &r.cofactor)
        .bool(r.verified)
        .u64(r.iterations)
        .u64(r.c.unwrap_or(0))
}

/// Brent rho on 24 62-bit semiprimes (two 31-bit primes each): the `u64`
/// walk (`n < 2^63`).
fn rho_factor_u64_62bit_x24() -> Box<dyn Workload> {
    let mut rng = StdRng::seed_from_u64(0x0072_686f_3632);
    let ns: Vec<BigUint> = (0..24)
        .map(|_| {
            let p = random_prime_u64(31, &mut rng);
            let q = random_prime_u64(31, &mut rng);
            BigUint::from(p) * q
        })
        .collect();
    let params = RhoParams::default();
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for n in &ns {
            let r = rho(n, &params);
            assert!(r.verified, "rho found no factor");
            fp = fp_rho(fp, &r);
        }
        fp.finish()
    }))
}

/// Brent rho on four 115-bit `n`, each with a 35-bit factor: the
/// `BigUint` walk.
fn rho_factor_big_115bit_x4() -> Box<dyn Workload> {
    let mut rng = StdRng::seed_from_u64(0x7268_6f31_3135);
    let ns: Vec<BigUint> = (0..4)
        .map(|_| {
            let p = random_prime_u64(35, &mut rng);
            let q = loop {
                let c = rng.gen_biguint(80) | (BigUint::one() << 79u32) | BigUint::one();
                if is_probable_prime(&c) {
                    break c;
                }
            };
            q * p
        })
        .collect();
    let params = RhoParams::default();
    Box::new(Closure(move || {
        let mut fp = Fp::new();
        for n in &ns {
            let r = rho(n, &params);
            assert!(r.verified, "rho found no factor");
            fp = fp_rho(fp, &r);
        }
        fp.finish()
    }))
}

// ── relation / dlp: prime-field automorphism-orbit index calculus ───────

fn fp_rho_report(fp: Fp, r: &RhoReport) -> Fp {
    fp.usize(r.walks)
        .u64(u64::from(r.dp_bits))
        .u64(r.steps)
        .u64(r.setup_ops)
        .u64(r.distinguished_points)
        .bool(r.recovered.is_some())
        .u64(r.recovered.unwrap_or(0))
        .bool(r.verified)
}

fn orbit_instance(kind: CurveKind, bits: u32, seed: u64) -> GeneratedInstance {
    generate_instance(ScaledShape::of_kind(kind), bits, None, seed).expect("certified instance")
}

/// Known-answer index calculus (default options: large primes, learning
/// descents) on a 34-bit `j = 0` curve, eight targets, rho skipped.
fn orbit_ic_j0_34bit_x8() -> Box<dyn Workload> {
    let inst = orbit_instance(CurveKind::J0, 34, 5);
    let points: Vec<_> = inst.targets(8, 1).iter().map(|&(_, q)| q).collect();
    let opts = OrbitIcOptions {
        skip_rho: true,
        ..OrbitIcOptions::default()
    };
    Box::new(Closure(move || {
        let rep = run_known_answer(&inst.curve, &points, &opts);
        let l = &rep.logs;
        let mut fp = Fp::new()
            .usize(rep.automorphism_order)
            .usize(l.orbits)
            .usize(l.points)
            .u64(l.factor_base_draws)
            .u64(l.trials)
            .usize(l.relations)
            .u64(l.rejected_relations)
            .u64(l.full_relations)
            .u64(l.combined_relations)
            .u64(l.distinct_large_primes)
            .u64(l.known_large_primes)
            .u64(u64::from(l.collection_rounds))
            .u64(l.walk_restarts)
            .u64(l.oracle_ops)
            .u64(l.probe_ops)
            .usize(l.system.components)
            .usize(l.system.determined_components)
            .usize(l.system.inconsistent_components)
            .usize(l.system.solved_columns)
            .usize(l.certified_columns)
            .usize(l.uncertified_columns);
        for d in &rep.descents {
            fp = fp
                .u64(d.trials)
                .u64(d.oracle_ops)
                .u64(d.probe_ops)
                .bool(d.through_large_prime)
                .u64(d.learned)
                .u64(d.restarts)
                .u64(d.recovered.unwrap_or(u64::MAX))
                .bool(d.verified);
        }
        fp.finish()
    }))
}

/// The orbit pipeline's rho baseline (distinguished points, walks sharing
/// one inversion per step, `bsgs_fast` Montgomery arithmetic) on four
/// targets of a 40-bit generic curve.
fn orbit_rho_baseline_40bit_x4() -> Box<dyn Workload> {
    let inst = orbit_instance(CurveKind::Generic, 40, 3);
    let points: Vec<_> = inst.targets(4, 7).iter().map(|&(_, q)| q).collect();
    let table = RhoJumps::new(&inst.curve, 11);
    Box::new(Closure(move || {
        let mut fp = Fp::new().u64(table.ops);
        for (i, &q) in points.iter().enumerate() {
            let r = rho_baseline(&inst.curve, &table, q, 100 + i as u64, 0);
            assert!(r.verified, "rho baseline did not recover target {i}");
            fp = fp_rho_report(fp, &r);
        }
        fp.finish()
    }))
}

// ── dlp: weak-curve attacks ──────────────────────────────────────────────

fn affine_xy(p: &AffinePoint) -> (BigUint, BigUint) {
    match p {
        AffinePoint::Affine(x, y) => (x.clone(), y.clone()),
        AffinePoint::Infinity => panic!("identity"),
    }
}

/// Smart's attack on a 256-bit anomalous CM curve (`D = −11`).
fn smart_anomalous_256() -> Box<dyn Workload> {
    let mut rng = StdRng::seed_from_u64(256);
    let ac = anomalous_curve_cm(256, 11, &mut rng).expect("anomalous CM curve");
    let curve = ac.to_curve_params();
    let g = curve.generator();
    let secret = rng.gen_biguint_below(&curve.p);
    let q = g.scalar_mul(&secret, &curve.a_fe());
    let opts = SmartOptions::default();
    Box::new(Closure(move || {
        let out = smart_attack(&curve, &g, &q, &opts).expect("Smart's attack");
        assert_eq!(out.scalar, secret);
        fp_big(Fp::new(), &out.scalar)
            .u64(out.p_bits)
            .usize(out.lifts_tried)
            .usize(out.degenerate_lifts)
            .finish()
    }))
}

/// Supersingular `y² = x³ + x` over a `bits`-bit `p = 4·h·n − 1` with a
/// prime `n` of `n_bits` bits (`#E = p + 1`, embedding degree 2); the
/// construction of the `mov` unit tests.
fn supersingular_k2(bits: u64, n_bits: u64, seed: u64) -> CurveParams {
    let mut rng = StdRng::seed_from_u64(seed);
    let n = loop {
        let c = rng.gen_biguint(n_bits) | (BigUint::one() << (n_bits - 1)) | BigUint::one();
        if is_probable_prime(&c) {
            break c;
        }
    };
    let (p, h) = loop {
        let h = rng.gen_biguint(bits - n_bits - 2) | (BigUint::one() << (bits - n_bits - 3));
        let p = ((&h * &n) << 2u32) - 1u32;
        if p.bits() == bits && is_probable_prime(&p) {
            break (p, h);
        }
    };
    let ec = Ec::new(&p, &BigUint::one(), &BigUint::zero());
    let cof = &h << 2u32;
    let g = loop {
        let r = ec.mul(&ec.random_point(&mut rng), &cof);
        if r != AffinePoint::Infinity {
            break r;
        }
    };
    let (gx, gy) = affine_xy(&g);
    CurveParams {
        name: "supersingular-k2",
        p,
        a: BigUint::one(),
        b: BigUint::zero(),
        gx,
        gy,
        n,
        h: 0,
    }
}

/// MOV on a 160-bit supersingular curve with a 30-bit prime subgroup: the
/// reduced Tate pairing into `F_{p²}` and the DLP there (Pollard rho).
fn mov_supersingular_k2_160() -> Box<dyn Workload> {
    let curve = supersingular_k2(160, 30, 21);
    let order = &curve.p + 1u32;
    let g = curve.generator();
    let d = BigUint::from(412_345_678u64) % &curve.n;
    let q = g.scalar_mul(&d, &curve.a_fe());
    let opts = MovOptions::default();
    Box::new(Closure(move || {
        let out = mov_attack(&curve, &g, &q, &curve.n, &order, &opts).expect("MOV");
        assert_eq!(out.scalar, d);
        let mut fp = fp_big(Fp::new(), &out.scalar)
            .u64(u64::from(out.embedding_degree))
            .u64(out.target_field_bits)
            .usize(out.pairing_attempts)
            .str(&format!("{:?}", out.dlp_solver))
            .u64(out.dlp_group_ops);
        fp = fp_big(fp, &out.curve_order_extension);
        for s in out.alpha.iter().chain(&out.beta) {
            fp = fp.str(s);
        }
        fp.finish()
    }))
}

/// Pohlig–Hellman on a 128-bit supersingular `y² = x³ + x`, `p ≡ 3 (4)`,
/// whose order `p + 1 = 4·k·q₁q₂` has a 26-bit and a 25-bit prime: BSGS below
/// 2^24 is out, so every large digit is a Pollard rho over the batched
/// affine arithmetic of `weak_curves::arith`.  The factorisation is
/// supplied, so the kernel is the DLP, not the factoring.
fn pohlig_hellman_smooth_128() -> Box<dyn Workload> {
    let mut rng = StdRng::seed_from_u64(0x0070_6831_3238);
    let qs: Vec<u64> = [26u32, 25]
        .iter()
        .map(|&b| random_prime_u64(b, &mut rng))
        .collect();
    let base: BigUint = qs.iter().fold(BigUint::from(4u32), |acc, &q| acc * q);
    // p = base·k − 1 with k a product of small primes, 128 bits.
    let small = [3u64, 5, 7, 11, 13];
    let (p, k_factors) = loop {
        let mut k = BigUint::one();
        let mut kf: Vec<u64> = Vec::new();
        while (&base * &k).bits() < 128 {
            let s = small[rng.gen_range(0..small.len())];
            k *= s;
            kf.push(s);
        }
        let p = &base * &k - 1u32;
        if p.bits() == 128 && is_probable_prime(&p) {
            break (p, kf);
        }
    };
    let order = &p + 1u32;
    let mut exps: HashMap<u64, u32> = HashMap::new();
    *exps.entry(2).or_default() += 2;
    for &s in &k_factors {
        *exps.entry(s).or_default() += 1;
    }
    for &q in &qs {
        *exps.entry(q).or_default() += 1;
    }
    let mut factors: Vec<(BigUint, u32)> = exps
        .into_iter()
        .map(|(q, e)| (BigUint::from(q), e))
        .collect();
    factors.sort();
    let ec = Ec::new(&p, &BigUint::one(), &BigUint::zero());
    let (gx, gy) = affine_xy(&ec.random_point(&mut rng));
    let curve = CurveParams {
        name: "supersingular-smooth",
        p,
        a: BigUint::one(),
        b: BigUint::zero(),
        gx,
        gy,
        n: order.clone(),
        h: 1,
    };
    let g = curve.generator();
    let secret = rng.gen_biguint_below(&order);
    let q: Point = g.scalar_mul(&secret, &curve.a_fe());
    let opts = PohligHellmanOptions::default();
    Box::new(Closure(move || {
        let out = pohlig_hellman_attack(&curve, &g, &q, &order, Some(&factors), &opts)
            .expect("Pohlig-Hellman");
        assert_eq!(&secret % &out.order_of_g, out.scalar);
        let mut fp = fp_big(Fp::new(), &out.scalar);
        fp = fp_big(fp, &out.order_of_g)
            .u64(out.largest_prime_bits)
            .u64(out.group_ops)
            .usize(out.steps.len());
        for s in &out.steps {
            fp = fp_big(fp, &s.prime).u64(u64::from(s.exponent));
            fp = fp_big(fp, &s.residue)
                .str(&format!("{:?}", s.solver))
                .u64(s.group_ops);
        }
        fp.finish()
    }))
}

pub fn register(kernels: &mut Vec<Kernel>) {
    let mut add = |id, area, desc, tier, setup| {
        kernels.push(Kernel {
            id,
            area,
            desc,
            tier,
            setup,
        })
    };
    // bool_gb
    add(
        "bool_gb/f4batch_lockstep_k1_17_m2_x24",
        "bool_gb",
        "f4_batch::solve_lockstep (CpuDecider, MatrixF4 max_degree 3, budget 4096, all roots) on the S3 decomposition systems of 24 targets on K_1/2^17",
        Tier::Quick,
        f4batch_lockstep_k1_17_m2_x24 as fn() -> Box<dyn Workload>,
    );
    add(
        "bool_gb/f4gf2_decide_replay_k1_17",
        "bool_gb",
        "f4_gf2::decide_with (F5 on, default caps) sequentially over every Macaulay decision the K_1/2^17 x24 lockstep search requests",
        Tier::Quick,
        f4gf2_decide_replay_k1_17,
    );
    add(
        "bool_gb/f4gf2_decide_d4_f5_k1_17",
        "bool_gb",
        "f4_gf2::decide_with (F5 on) at degree 4 over every 8th recorded degree-3 K_1/2^17 x24 decision: F5 and field-equation row criteria active",
        Tier::Quick,
        f4gf2_decide_d4_f5_k1_17,
    );
    add(
        "bool_gb/f4gf2_profile_replay_k1_17",
        "bool_gb",
        "f4_gf2::profile_with (F5 on) over the recorded K_1/2^17 x24 decisions: rank and linear rows over all variables",
        Tier::Quick,
        f4gf2_profile_replay_k1_17,
    );
    add(
        "bool_gb/f4gf2_matrix_rows_replay_k1_17",
        "bool_gb",
        "f4_gf2::matrix_rows_with (F5 on) over every other recorded K_1/2^17 x24 decision: full reduced rows read back",
        Tier::Quick,
        f4gf2_matrix_rows_replay_k1_17,
    );
    add(
        "bool_gb/f4gpu_pack_f5_replay_k1_17",
        "bool_gb",
        "f4_gpu::PackedBatch::pack_with(f5) over the recorded K_1/2^17 x24 decisions: host-side packing and F5 row masks",
        Tier::Quick,
        f4gpu_pack_f5_replay_k1_17,
    );
    // relation: factoring
    add(
        "relation/qs_semiprime_20d",
        "relation",
        "factoring::qs (SIQS, 1 thread, seed 1) on the 20-digit semiprime 3267000013 * 10000000019",
        Tier::Quick,
        qs_semiprime_20d,
    );
    add(
        "relation/qs_semiprime_30d",
        "relation",
        "factoring::qs (SIQS, 1 thread, seed 1) on the 31-digit semiprime (10^17+3)(10^12+39)",
        Tier::Quick,
        qs_semiprime_30d,
    );
    add(
        "relation/qs_semiprime_40d",
        "relation",
        "factoring::qs (SIQS, 1 thread, seed 1) on the 41-digit semiprime (10^19+51)(10^20+39)",
        Tier::Quick,
        qs_semiprime_40d,
    );
    add(
        "relation/qs_semiprime_50d",
        "relation",
        "factoring::qs (SIQS, 1 thread, seed 1) on the 50-digit semiprime nextprime(10^24)*nextprime(10^25)",
        Tier::Full,
        qs_semiprime_50d,
    );
    add(
        "relation/nfs_line_sieve_40d_b8",
        "relation",
        "nfs::sieve::sieve_segment on lines b=1..8 over [-A,A) of the degree-3 base-m pair of the 41-digit semiprime (bounds 30000, LP x80)",
        Tier::Quick,
        nfs_line_sieve_40d_b8,
    );
    add(
        "relation/nfs_linalg_deps_40d",
        "relation",
        "nfs::linalg::find_dependencies (singletons, SGE, dense M4RI Gauss-Jordan) on NFS relation rows of the 41-digit pair, surplus 32",
        Tier::Quick,
        nfs_linalg_deps_40d,
    );
    add(
        "relation/gnfs_semiprime_30d",
        "relation",
        "factoring::gnfs end to end (1 thread) on the 31-digit semiprime (10^17+3)(10^12+39)",
        Tier::Quick,
        gnfs_semiprime_30d,
    );
    add(
        "relation/pm1_stage2_95bit",
        "relation",
        "factoring::pm1 (B1=1e5, B2=5e6) on p*q, p-1 = 2*smooth*L with L~3e6 prime (found in stage 2), q-1 not smooth",
        Tier::Quick,
        pm1_stage2_95bit,
    );
    add(
        "relation/rho_factor_u64_62bit_x24",
        "relation",
        "factoring::rho (Brent, u64 walk) on 24 62-bit semiprimes with 31-bit factors",
        Tier::Quick,
        rho_factor_u64_62bit_x24,
    );
    add(
        "relation/rho_factor_big_115bit_x4",
        "relation",
        "factoring::rho (Brent, BigUint walk) on four 115-bit n, each with a 35-bit factor",
        Tier::Quick,
        rho_factor_big_115bit_x4,
    );
    add(
        "relation/orbit_ic_j0_34bit_x8",
        "relation",
        "prime_orbit_index_calculus::run_known_answer (defaults: large primes, learning; rho skipped) on a 34-bit j=0 curve, 8 targets",
        Tier::Quick,
        orbit_ic_j0_34bit_x8,
    );
    // dlp
    add(
        "dlp/orbit_rho_baseline_40bit_x4",
        "dlp",
        "prime_orbit_index_calculus::rho_baseline (distinguished points, shared inversion, 32 jumps) on 4 targets of a 40-bit generic curve",
        Tier::Quick,
        orbit_rho_baseline_40bit_x4,
    );
    add(
        "dlp/weak_smart_anomalous_256",
        "dlp",
        "weak_curves::smart_attack on a 256-bit anomalous CM curve (D=-11), verified by Point::scalar_mul",
        Tier::Quick,
        smart_anomalous_256,
    );
    add(
        "dlp/weak_mov_supersingular_k2_160",
        "dlp",
        "weak_curves::mov_attack on a 160-bit supersingular y^2=x^3+x with a 30-bit subgroup: Tate pairing into F_p^2 and Pollard rho there",
        Tier::Quick,
        mov_supersingular_k2_160,
    );
    add(
        "dlp/weak_pohlig_hellman_smooth_128",
        "dlp",
        "weak_curves::pohlig_hellman_attack (factorisation supplied) on a 128-bit supersingular curve, p+1 = 4k*q1*q2 with 26- and 25-bit q_i (rho digits)",
        Tier::Quick,
        pohlig_hellman_smooth_128,
    );
}
