//! Area `sat`: SAT solving: CDCL with native XOR clauses, Semaev/Boolean encodings.
//!
//! Every kernel builds its solvers in the untimed `prepare` (a
//! [`sat::Solver`] is consumed by a solve and is not `Clone`), then times
//! `Solver::solve` alone and fingerprints the verdict, the model, and the
//! solver's counted units: `conflicts()`, `n_clauses()` and every work
//! counter in `SolverStats` except the `ns_*` phase timings.  Every SAT
//! model is checked against its instance before it is fingerprinted.
//!
//! * `semaev_s4_*` — the symmetrised binary-Semaev `S₄` decomposition
//!   instances of the reference corpus (`semaev_corpus::CORPUS`, the
//!   EC-Index-Calculus-Benchmarks parameters), encoded by
//!   `semaev_sat::encode_semaev_s4_with` exactly as `semaev_sat_bench`
//!   encodes them.  Satisfiable instances are decoded and checked against
//!   `S₄` over `F_{2ⁿ}`; unsatisfiable ones are the instances exhaustive
//!   search proves have no decomposition.  The `_encode_` kernel times the
//!   encoder itself (Weil descent + install).
//! * `koblitz_bool_*` — the Weil-restricted Koblitz decomposition systems
//!   `sat_decompose` / `koblitz_symmetrised` hand to
//!   `semaev_sat::encode_boolean_system_with`, native XOR and the CNF
//!   control (the latter under a conflict budget, ending `Unknown`).
//! * `random3sat_*`, `xor_planted_*` — seeded generic CNF at the 3-SAT
//!   threshold (both verdicts) and a planted parity-heavy mix, through
//!   `add_clause` / `add_xor`.
//!
//! Instances were chosen per kernel so a run takes 50–300 ms at one
//! thread; solve cost varies over three orders of magnitude between
//! instances of one family.
//!
//! These are the crypto crate's `sat` kernels, same IDs and inputs; this
//! crate's `sat` and `semaev_sat` are the same solver and encoders.

use crate::harness::{Fp, Kernel, Tier, Workload};
use cryptanalysis_suite::binary_ecc::BinaryPoint;
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, FieldStructure,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base, KoblitzCurve,
};
use cryptanalysis_suite::cryptanalysis::pq_groebner_f2::F2BoolPoly;
use cryptanalysis_suite::cryptanalysis::sat::{check_model, Lit, SolveResult, Solver, SolverStats};
use cryptanalysis_suite::cryptanalysis::semaev_corpus::{CorpusInstance, CORPUS};
use cryptanalysis_suite::cryptanalysis::semaev_sat::{
    encode_boolean_system_with, encode_semaev_s4_with, S4Options, S4SatEncoding, XorEncoding,
};

// ── Workload: rebuild a non-`Clone` input before every sample ───────

/// Like `harness::Fresh`, for inputs that cannot be cloned: `build` runs
/// in the untimed `prepare`, `body` consumes the result in `run`.
struct Rebuild<T, B: FnMut() -> T, F: FnMut(&mut T) -> u64> {
    build: B,
    work: Option<T>,
    body: F,
}

impl<T, B: FnMut() -> T, F: FnMut(&mut T) -> u64> Workload for Rebuild<T, B, F> {
    fn prepare(&mut self) {
        self.work = Some((self.build)());
    }
    fn run(&mut self) -> u64 {
        let work = self.work.as_mut().expect("prepare runs before run");
        (self.body)(work)
    }
}

fn rebuild<T: 'static>(
    build: impl FnMut() -> T + 'static,
    body: impl FnMut(&mut T) -> u64 + 'static,
) -> Box<dyn Workload> {
    Box::new(Rebuild {
        build,
        work: None,
        body,
    })
}

// ── Fingerprints ────────────────────────────────────────────────────

/// Every counted unit of a solve; the `ns_*` timings are excluded.
fn fp_stats(fp: Fp, s: &SolverStats) -> Fp {
    fp.u64(s.decisions)
        .u64(s.conflicts)
        .u64(s.restarts)
        .u64(s.propagations)
        .u64(s.xor_passes)
        .u64(s.xor_propagations)
        .u64(s.xor_conflicts)
        .u64(s.xor_repivots)
        .u64(s.learnt_clauses)
        .u64(s.xor_row_ops)
        .u64(s.xor_row_scans)
        .u64(s.xor_reason_lits)
        .u64(s.clause_visits)
        .u64(s.clause_lit_visits)
        .u64(s.analyze_lit_visits)
        .u64(s.learnt_lits_raw)
        .u64(s.learnt_lits_kept)
        .u64(s.conflict_level_sum)
        .u64(s.max_level)
}

fn verdict_code(r: SolveResult) -> u64 {
    match r {
        SolveResult::Sat => 1,
        SolveResult::Unsat => 2,
        SolveResult::Unknown => 3,
    }
}

/// Verdict, counters, clause count and (when SAT) the whole model packed
/// into words.
fn fp_solve(fp: Fp, res: SolveResult, s: &Solver) -> Fp {
    let mut fp = fp
        .u64(verdict_code(res))
        .u64(s.conflicts())
        .usize(s.n_clauses());
    fp = fp_stats(fp, &s.stats);
    if res == SolveResult::Sat {
        let model = s.model();
        let mut words = vec![0u64; model.len().div_ceil(64)];
        for (i, &b) in model.iter().enumerate() {
            words[i / 64] |= (b as u64) << (i % 64);
        }
        fp = fp.words(&words);
    }
    fp
}

// ── Seeded generator (independent of any crate's RNG stream) ────────

struct SplitMix(u64);

impl SplitMix {
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9e37_79b9_7f4a_7c15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
        z ^ (z >> 31)
    }
    fn below(&mut self, n: u64) -> u64 {
        ((self.next() as u128 * n as u128) >> 64) as u64
    }
}

// ── Semaev S4 corpus ────────────────────────────────────────────────

fn corpus(names: &[&str]) -> Vec<&'static CorpusInstance> {
    names
        .iter()
        .map(|n| {
            CORPUS
                .iter()
                .find(|c| c.name == *n)
                .unwrap_or_else(|| panic!("corpus instance {n}"))
        })
        .collect()
}

fn encode_s4(c: &CorpusInstance, encoding: XorEncoding) -> S4SatEncoding {
    encode_semaev_s4_with(
        c.n,
        c.l,
        &c.irr(),
        &c.b(),
        &c.x_r(),
        S4Options {
            encoding,
            break_symmetry: true,
        },
    )
}

/// Solve each corpus instance; a SAT answer is decoded and checked to be a
/// genuine decomposition, and every verdict must match exhaustive search.
fn semaev_s4(names: &'static [&'static str], encoding: XorEncoding) -> Box<dyn Workload> {
    let insts = corpus(names);
    let build_insts = insts.clone();
    rebuild(
        move || {
            build_insts
                .iter()
                .map(|c| encode_s4(c, encoding))
                .collect::<Vec<_>>()
        },
        move |encs: &mut Vec<S4SatEncoding>| {
            let mut fp = Fp::new();
            for (c, enc) in insts.iter().zip(encs.iter_mut()) {
                let res = enc.solver.solve();
                assert_eq!(res == SolveResult::Sat, c.truly_sat, "{}", c.name);
                if res == SolveResult::Sat {
                    let xs = enc.decode();
                    assert!(c.is_decomposition(&xs), "{}: bad model", c.name);
                }
                fp = fp_solve(fp.str(c.name), res, &enc.solver);
            }
            fp.finish()
        },
    )
}

const N15L5_SAT: &[&str] = &["n15l5-2-S", "n15l5-4-S", "n15l5-8-S", "n15l5-10-S"];
const N15L5_UNSAT: &[&str] = &["n15l5-11-U"];
const N17L6_SAT: &[&str] = &["n17l6-8-S"];
const N17L6_UNSAT: &[&str] = &["n17l6-11-U"];
const N19L6_SAT: &[&str] = &["n19l6-1-S"];
const N15L5_CNF: &[&str] = &["n15l5-8-S", "n15l5-10-S"];

fn semaev_s4_n15l5_sat() -> Box<dyn Workload> {
    semaev_s4(N15L5_SAT, XorEncoding::Native)
}
fn semaev_s4_n15l5_unsat() -> Box<dyn Workload> {
    semaev_s4(N15L5_UNSAT, XorEncoding::Native)
}
fn semaev_s4_n17l6_sat() -> Box<dyn Workload> {
    semaev_s4(N17L6_SAT, XorEncoding::Native)
}
fn semaev_s4_n17l6_unsat() -> Box<dyn Workload> {
    semaev_s4(N17L6_UNSAT, XorEncoding::Native)
}
fn semaev_s4_n19l6_sat() -> Box<dyn Workload> {
    semaev_s4(N19L6_SAT, XorEncoding::Native)
}
fn semaev_s4_n15l5_cnf() -> Box<dyn Workload> {
    semaev_s4(N15L5_CNF, XorEncoding::Cnf)
}

/// The encoder alone (Weil descent of `S₄` plus clause/row installation),
/// the per-target setup cost every SAT decomposition call pays.
fn semaev_s4_encode_n19l6() -> Box<dyn Workload> {
    let insts = corpus(&["n19l6-1-S", "n19l6-11-U", "n19l6-2-S", "n19l6-12-U"]);
    Box::new(crate::harness::Closure(move || {
        let mut fp = Fp::new();
        for c in &insts {
            let enc = encode_s4(c, XorEncoding::Native);
            fp = fp
                .u64(u64::from(enc.n_x_vars))
                .u64(u64::from(enc.n_e_vars))
                .u64(u64::from(enc.n_aux_vars))
                .bool(enc.trivially_unsat)
                .u64(u64::from(enc.solver.n_vars()))
                .usize(enc.solver.n_clauses())
                .usize(enc.solver.n_xors());
        }
        fp.finish()
    }))
}

// ── Koblitz decomposition systems via encode_boolean_system_with ───

/// The Weil-restricted decomposition systems of eight targets on
/// `K_a / F_{2ⁿ}` with the factor base of divisor index `fi`: targets
/// `0..4` are planted sums of `m` factor-base points, `4..8` are fixed
/// multiples of the generator — the systems `sat_decompose` /
/// `koblitz_symmetrised` build.  `pick` selects which ones the kernel
/// solves (the solve cost varies over three orders of magnitude).
fn koblitz_bool_systems(
    a: u8,
    n: u32,
    fi: usize,
    m: usize,
    pick: &[usize],
) -> Vec<(Vec<F2BoolPoly>, usize)> {
    let kc = KoblitzCurve::new(a, n).expect("Koblitz curve exists");
    let fb = build_frobenius_factor_base(&kc, fi).expect("factor base exists");
    assert!(fb.m_can_decompose(&kc, m), "cell admissible for m");
    let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
    let mut rng = SplitMix(15);
    let g = kc.generator().clone();
    let targets: Vec<BinaryPoint> = (0..8u64)
        .map(|i| {
            if i < 4 {
                (0..m).fold(BinaryPoint::Infinity, |acc, _| {
                    kc.add(&acc, &fb.points[rng.below(fb.points.len() as u64) as usize])
                })
            } else {
                let k = num_bigint::BigUint::from(1 + i.wrapping_mul(2_654_435_761) % 1_000_003);
                kc.mul(&g, &k)
            }
        })
        .collect();
    pick.iter()
        .map(|&i| {
            let BinaryPoint::Affine { x: x_r, .. } = &targets[i] else {
                panic!("target {i} is the point at infinity");
            };
            let sys = build_decomposition_system(&fb.subspace_basis, x_r, &kc.curve.b, m, &st)
                .expect("system fits in 64 unknowns");
            (sys.equations.clone(), sys.n_vars)
        })
        .collect()
}

/// Encode each system (untimed, in `prepare`) and time the solves under
/// `budget` conflicts each; a SAT model is checked against the system.
fn koblitz_bool(
    systems: Vec<(Vec<F2BoolPoly>, usize)>,
    encoding: XorEncoding,
    budget: u64,
) -> Box<dyn Workload> {
    let for_build = systems.clone();
    rebuild(
        move || {
            for_build
                .iter()
                .map(|(eqs, n)| {
                    let mut enc = encode_boolean_system_with(*n, eqs, &[], encoding);
                    enc.solver.conflict_budget = budget;
                    enc
                })
                .collect::<Vec<_>>()
        },
        move |encs| {
            let mut fp = Fp::new();
            for ((eqs, _), enc) in systems.iter().zip(encs.iter_mut()) {
                let res = enc.solver.solve();
                fp = fp_solve(fp, res, &enc.solver);
                if res == SolveResult::Sat {
                    let a = enc.model_assignment();
                    assert!(eqs.iter().all(|e| e.eval(a) == 0), "bad model");
                    fp = fp.u64(a);
                }
            }
            fp.finish()
        },
    )
}

fn koblitz_bool_native_m3_n15() -> Box<dyn Workload> {
    koblitz_bool(
        koblitz_bool_systems(0, 15, 1, 3, &[1, 2, 7]),
        XorEncoding::Native,
        u64::MAX,
    )
}

fn koblitz_bool_cnf_m3_n15() -> Box<dyn Workload> {
    koblitz_bool(
        koblitz_bool_systems(0, 15, 1, 3, &[0, 3]),
        XorEncoding::Cnf,
        KOBLITZ_CNF_BUDGET,
    )
}

/// Conflict budget of the CNF control: both systems exhaust it, so the
/// kernel is a fixed amount of search ending in `Unknown`, as a budgeted
/// `sat_decompose_with` call that gives up does.
const KOBLITZ_CNF_BUDGET: u64 = 1500;

fn koblitz_bool_native_m2_n19() -> Box<dyn Workload> {
    koblitz_bool(
        koblitz_bool_systems(0, 19, 0, 2, &[0, 6]),
        XorEncoding::Native,
        u64::MAX,
    )
}

// ── Generic CNF / parity instances ─────────────────────────────────

fn random_3sat(n: u32, m: usize, seed: u64) -> Vec<Vec<Lit>> {
    let mut rng = SplitMix(seed);
    (0..m)
        .map(|_| {
            let mut c: Vec<Lit> = Vec::with_capacity(3);
            while c.len() < 3 {
                let v = 1 + rng.below(u64::from(n)) as Lit;
                if c.iter().any(|&l| l.abs() == v) {
                    continue;
                }
                c.push(if rng.next() & 1 == 1 { v } else { -v });
            }
            c
        })
        .collect()
}

/// Random 3-SAT at clause/variable ratio `m / n`, several seeds; the
/// verdicts are whatever they are (both occur near the threshold).
fn random3sat(n: u32, m: usize, seeds: &'static [u64]) -> Box<dyn Workload> {
    let instances: Vec<Vec<Vec<Lit>>> = seeds.iter().map(|&s| random_3sat(n, m, s)).collect();
    let for_build = instances.clone();
    rebuild(
        move || {
            for_build
                .iter()
                .map(|cls| {
                    let mut s = Solver::new(n);
                    for c in cls {
                        s.add_clause(c.clone());
                    }
                    s
                })
                .collect::<Vec<_>>()
        },
        move |solvers| {
            let mut fp = Fp::new();
            for (cls, s) in instances.iter().zip(solvers.iter_mut()) {
                let res = s.solve();
                assert_ne!(res, SolveResult::Unknown, "no budget is set");
                if res == SolveResult::Sat {
                    assert!(check_model(cls, &s.model()), "model violates a clause");
                }
                fp = fp_solve(fp, res, s);
            }
            fp.finish()
        },
    )
}

fn random3sat_n200_r426() -> Box<dyn Workload> {
    random3sat(200, 852, &[1, 3, 4, 6, 10])
}

fn random3sat_n150_r426() -> Box<dyn Workload> {
    random3sat(150, 639, &[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
}

/// A planted parity-heavy instance: `rows` random XORs of width `width`
/// over `n` variables (consistent with a hidden assignment) plus `m`
/// random 3-clauses that assignment satisfies; the first `free` variables
/// are given branching priority, as the Semaev encoders do.
struct XorInstance {
    n: u32,
    xors: Vec<(Vec<u32>, bool)>,
    clauses: Vec<Vec<Lit>>,
}

fn xor_planted(n: u32, rows: usize, width: usize, m: usize, seed: u64) -> XorInstance {
    let mut rng = SplitMix(seed);
    let hidden: Vec<bool> = (0..n).map(|_| rng.next() & 1 == 1).collect();
    let xors = (0..rows)
        .map(|_| {
            let mut vars: Vec<u32> = Vec::with_capacity(width);
            while vars.len() < width {
                let v = 1 + rng.below(u64::from(n)) as u32;
                if !vars.contains(&v) {
                    vars.push(v);
                }
            }
            let rhs = vars
                .iter()
                .fold(false, |acc, &v| acc ^ hidden[(v - 1) as usize]);
            (vars, rhs)
        })
        .collect();
    let mut clauses = Vec::with_capacity(m);
    while clauses.len() < m {
        let mut c: Vec<Lit> = Vec::with_capacity(3);
        while c.len() < 3 {
            let v = 1 + rng.below(u64::from(n)) as Lit;
            if c.iter().any(|&l| l.abs() == v) {
                continue;
            }
            c.push(if rng.next() & 1 == 1 { v } else { -v });
        }
        if c.iter().any(|&l| hidden[(l.abs() - 1) as usize] == (l > 0)) {
            clauses.push(c);
        }
    }
    XorInstance { n, xors, clauses }
}

fn xor_mix(insts: Vec<XorInstance>) -> Box<dyn Workload> {
    let insts = std::rc::Rc::new(insts);
    let for_build = insts.clone();
    rebuild(
        move || {
            for_build
                .iter()
                .map(|x| {
                    let mut s = Solver::new(x.n);
                    for c in &x.clauses {
                        s.add_clause(c.clone());
                    }
                    for (vars, rhs) in &x.xors {
                        s.add_xor(vars, *rhs);
                    }
                    s
                })
                .collect::<Vec<_>>()
        },
        move |solvers| {
            let mut fp = Fp::new();
            for (x, s) in insts.iter().zip(solvers.iter_mut()) {
                let res = s.solve();
                assert_eq!(res, SolveResult::Sat, "planted instance");
                let model = s.model();
                assert!(s.check_xors(&model), "model violates a parity row");
                assert!(check_model(&x.clauses, &model), "model violates a clause");
                fp = fp_solve(fp, res, s);
            }
            fp.finish()
        },
    )
}

fn xor_planted_n120() -> Box<dyn Workload> {
    xor_mix(
        (0..6)
            .map(|i| xor_planted(120, 90, 5, 350, 0x5eed_0000 + i))
            .collect(),
    )
}

pub fn register(kernels: &mut Vec<Kernel>) {
    let mut add = |id: &'static str, desc: &'static str, tier: Tier, setup| {
        kernels.push(Kernel {
            id,
            area: "sat",
            desc,
            tier,
            setup,
        })
    };
    add(
        "sat/semaev_s4_n15l5_sat_x4",
        "Solver::solve on four n15l5 -S Semaev S4 corpus instances (native XOR, symmetry broken)",
        Tier::Quick,
        semaev_s4_n15l5_sat,
    );
    add(
        "sat/semaev_s4_n15l5_unsat_x1",
        "Solver::solve on the unsatisfiable n15l5-11-U Semaev S4 corpus instance (native XOR)",
        Tier::Quick,
        semaev_s4_n15l5_unsat,
    );
    add(
        "sat/semaev_s4_n17l6_sat_x1",
        "Solver::solve on the n17l6-8-S Semaev S4 corpus instance (native XOR)",
        Tier::Quick,
        semaev_s4_n17l6_sat,
    );
    add(
        "sat/semaev_s4_n17l6_unsat_x1",
        "Solver::solve on the unsatisfiable n17l6-11-U Semaev S4 corpus instance (native XOR)",
        Tier::Full,
        semaev_s4_n17l6_unsat,
    );
    add(
        "sat/semaev_s4_n19l6_sat_x1",
        "Solver::solve on the n19l6-1-S Semaev S4 corpus instance (native XOR)",
        Tier::Full,
        semaev_s4_n19l6_sat,
    );
    add(
        "sat/semaev_s4_n15l5_cnf_x2",
        "Solver::solve on two n15l5 -S Semaev S4 instances, parity Tseitin-expanded to CNF",
        Tier::Quick,
        semaev_s4_n15l5_cnf,
    );
    add(
        "sat/semaev_s4_encode_n19l6_x4",
        "semaev_sat::encode_semaev_s4_with on four n19l6 corpus targets (Weil descent + install)",
        Tier::Quick,
        semaev_s4_encode_n19l6,
    );
    add(
        "sat/koblitz_bool_native_m3_n15_x3",
        "Solver::solve on 3 Koblitz K0/F2^15 m=3 decomposition systems (encode_boolean_system_with, native XOR)",
        Tier::Quick,
        koblitz_bool_native_m3_n15,
    );
    add(
        "sat/koblitz_bool_cnf_m3_n15_b1500_x2",
        "Solver::solve, 1500-conflict budget, on 2 Koblitz K0/F2^15 m=3 systems (CNF parity)",
        Tier::Quick,
        koblitz_bool_cnf_m3_n15,
    );
    add(
        "sat/koblitz_bool_native_m2_n19_x2",
        "Solver::solve on 2 Koblitz K0/F2^19 m=2 decomposition systems (native XOR)",
        Tier::Quick,
        koblitz_bool_native_m2_n19,
    );
    add(
        "sat/random3sat_n200_r426_x5",
        "Solver::solve on five seeded random 3-SAT instances, n=200, m/n=4.26 (SAT and UNSAT)",
        Tier::Quick,
        random3sat_n200_r426,
    );
    add(
        "sat/random3sat_n150_r426_x12",
        "Solver::solve on twelve seeded random 3-SAT instances, n=150, m/n=4.26 (6 SAT, 6 UNSAT)",
        Tier::Quick,
        random3sat_n150_r426,
    );
    add(
        "sat/xor_planted_n120_x6",
        "Solver::solve on six planted instances: 90 width-5 XOR rows + 350 3-clauses, n=120",
        Tier::Quick,
        xor_planted_n120,
    );
}
