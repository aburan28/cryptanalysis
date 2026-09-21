//! Complete, public-synthetic IC/rho jobs for the candidate tournament.
//! Uses the production research library; JSON stdin contains no known scalar.
use cryptanalysis_suite::binary_ecc::{BinaryPoint, F2mElement};
use cryptanalysis_suite::cryptanalysis::koblitz_factor_base_search::FactorBaseSpec;
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    koblitz_signed_frobenius_rho_with_progress, point_key, points_with_x, DecompositionStrategy,
    FactorBaseLogSolver, IndividualLogSolver, KoblitzCurve, KoblitzIcOptions,
    KoblitzSignedRhoOptions, LinearAlgebra, PairSumTable, RelationCollector, RelationWorkUnit,
};
use cryptanalysis_suite::cryptanalysis::koblitz_sparse_la::SparseSolveOptions;
use num_bigint::BigUint;
use serde::Deserialize;
use serde_json::{json, Value};
use std::io::Read;
use std::time::Instant;

/// The amd64 Valgrind client-request ABI, as specified in valgrind.h.
/// Outside Valgrind the rotation preamble and self-exchange have no effect.
/// DUMP_STATS_AT writes the interval then resets counters; collection stays on.
#[inline(never)]
fn dump(label: &'static [u8]) {
    assert_eq!(label.last(), Some(&0));
    #[cfg(target_arch = "x86_64")]
    unsafe {
        let args = [0x4354_0003usize, label.as_ptr() as usize, 0, 0, 0, 0];
        std::arch::asm!(
            "rol rdi, 3", "rol rdi, 13", "rol rdi, 61", "rol rdi, 51",
            "xchg rbx, rbx",
            in("rax") args.as_ptr(), inout("rdx") 0usize => _, out("rdi") _,
            options(nostack)
        );
    }
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Job {
    mode: String,
    degree: u32,
    curve_a: u8,
    target_seeds: Vec<u64>,
    algorithm_seed: u64,
    factor_base: FactorBaseSpec,
    config: Config,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(default, deny_unknown_fields)]
struct Config {
    solver: String,
    linear_algebra: String,
    batch_trials: u64,
    max_trials: u64,
    summands: usize,
    collection_window: Option<usize>,
    sparse: SparseSolveOptions,
    factor_base_orbits: Option<usize>,
    factor_base_cube_root: bool,
}
impl Default for Config {
    fn default() -> Self {
        Self {
            solver: "pair_table".into(),
            linear_algebra: "sparse".into(),
            batch_trials: 64,
            max_trials: 4096,
            summands: 3,
            collection_window: None,
            sparse: SparseSolveOptions::default(),
            factor_base_orbits: None,
            factor_base_cube_root: false,
        }
    }
}

fn point(p: &BinaryPoint) -> Value {
    match p {
        BinaryPoint::Infinity => Value::Null,
        BinaryPoint::Affine { x, y } => {
            json!([x.to_biguint().to_string(), y.to_biguint().to_string()])
        }
    }
}

// Same public hash-to-curve domain as ic workflow. No target scalar is created.
fn target(c: &KoblitzCurve, seed: u64) -> Result<BinaryPoint, String> {
    for counter in 0u64..1_000_000 {
        let mut h = blake3::Hasher::new();
        h.update(b"ic-workflow-public-target-v1\0");
        h.update(&c.n.to_le_bytes());
        h.update(&[c.a]);
        h.update(&c.k.to_le_bytes());
        h.update(&c.b_index.to_le_bytes());
        h.update(&seed.to_le_bytes());
        h.update(&counter.to_le_bytes());
        let digest = h.finalize();
        let x =
            u64::from_le_bytes(digest.as_bytes()[..8].try_into().unwrap()) & ((1u64 << c.n) - 1);
        let x = F2mElement::from_biguint(&BigUint::from(x), c.n);
        let mut lifts = points_with_x(&c.curve, &x);
        lifts.sort_by_key(point_key);
        if lifts.is_empty() {
            continue;
        }
        let q = c.mul(
            &lifts[usize::from(digest.as_bytes()[8] & 1) % lifts.len()],
            &c.cofactor,
        );
        if q != BinaryPoint::Infinity {
            return Ok(q);
        }
    }
    Err("hash-to-curve exhausted".into())
}

fn run(job: &Job) -> Result<Value, String> {
    if !(5..=31).contains(&job.degree) || job.degree.is_multiple_of(2) || job.curve_a > 1 {
        return Err("worker accepts bounded odd-degree Koblitz fixtures (5..31)".into());
    }
    if job.target_seeds.is_empty() || job.target_seeds.len() > 100 {
        return Err("target count must be 1..100".into());
    }
    let cfg = &job.config;
    if cfg.batch_trials == 0
        || cfg.batch_trials > 4096
        || cfg.max_trials > 65536
        || cfg.max_trials < cfg.batch_trials
        || !(2..=4).contains(&cfg.summands)
    {
        return Err("invalid collection limits".into());
    }
    let start = Instant::now();
    let c = KoblitzCurve::new(job.curve_a, job.degree).ok_or("curve has no usable subgroup")?;
    let targets = job
        .target_seeds
        .iter()
        .map(|&s| target(&c, s))
        .collect::<Result<Vec<_>, _>>()?;
    let metadata = json!({
        "degree": c.n, "curve_a": c.a,
        "irreducible": {"degree": c.curve.irreducible.degree, "low_terms": c.curve.irreducible.low_terms},
        "subgroup_order": c.subgroup_order.to_string(), "group_order": c.group_order.to_string(),
        "cofactor": c.cofactor.to_string(), "lambda": c.lambda.to_string(),
        "generator": point(c.generator()), "targets": targets.iter().map(point).collect::<Vec<_>>(),
        "target_seeds": job.target_seeds, "target_scalar_constructed": false
    });
    dump(b"curve_and_targets\0");
    if job.mode == "fixture" {
        return Ok(json!({"schema_version":1,"status":"fixture","fixture":metadata}));
    }
    if job.mode == "rho" {
        let mut solutions = Vec::new();
        for (i, q) in targets.iter().enumerate() {
            let options = KoblitzSignedRhoOptions {
                seed: job.algorithm_seed ^ (i as u64).wrapping_mul(0x9e37_79b9_7f4a_7c15),
                max_iterations_per_restart: cfg.max_trials,
                ..KoblitzSignedRhoOptions::default()
            };
            let r = koblitz_signed_frobenius_rho_with_progress(&c, q, &options, &mut |_| {});
            solutions.push(
                json!({"index":i,"recovered":r.recovered_log.as_ref().map(ToString::to_string),
                "verified":r.verified,"iterations":r.iterations,"restarts":r.restarts_attempted,
                "walk_group_additions":r.charges.walk_group_additions}),
            );
        }
        dump(b"rho_solve\0");
        let verified = solutions.iter().zip(&targets).all(|(s, q)| {
            s["recovered"]
                .as_str()
                .and_then(|x| x.parse::<BigUint>().ok())
                .is_some_and(|d| d < c.subgroup_order && c.mul(c.generator(), &d) == *q)
        });
        dump(b"final_verification\0");
        return Ok(
            json!({"schema_version":1,"mode":"rho","status":if verified{"complete"}else{"incomplete"},
            "fixture":metadata,"solutions":solutions,"automorphism_order":2*c.n,
            "elapsed_seconds":start.elapsed().as_secs_f64()}),
        );
    }
    if job.mode != "ic" {
        return Err("unknown mode".into());
    }
    let strategy = match cfg.solver.as_str() {
        "pair_table" => DecompositionStrategy::PairTable,
        "enumerate" => DecompositionStrategy::Enumerate,
        _ => return Err("this worker supports pair_table and enumerate".into()),
    };
    let la = match cfg.linear_algebra.as_str() {
        "dense" => LinearAlgebra::Dense,
        "sparse" => LinearAlgebra::Sparse(cfg.sparse),
        _ => return Err("unknown linear algebra mode".into()),
    };
    let opts = KoblitzIcOptions {
        m: cfg.summands,
        seed: job.algorithm_seed,
        max_trials: cfg.max_trials as usize,
        strategy,
        linear_algebra: la,
        collection_window: cfg.collection_window,
        allow_direct_relation: false,
        ..KoblitzIcOptions::default()
    };
    if cfg
        .factor_base_orbits
        .is_some_and(|n| !(1..=8).contains(&n))
        || (cfg.factor_base_orbits.is_some() && cfg.factor_base_cube_root)
    {
        return Err("invalid factor-base policy".into());
    }
    let effective_base = if cfg.factor_base_orbits.is_some() || cfg.factor_base_cube_root {
        let FactorBaseSpec::SubgroupOrbits { seed, .. } = &job.factor_base else {
            return Err("orbit policy requires a subgroup-orbit base recipe".into());
        };
        let points = if let Some(orbits) = cfg.factor_base_orbits {
            2 * c.n as usize * orbits
        } else {
            let r = c.subgroup_order.to_u64_digits()[0];
            let mut b = 1u64;
            while b * b * b < r / 2 {
                b += 1;
            }
            (b as usize).max(2 * c.n as usize)
        };
        FactorBaseSpec::SubgroupOrbits {
            seed: *seed,
            points,
        }
    } else {
        job.factor_base.clone()
    };
    let fb = effective_base.materialize(&c)?;
    let pair = if strategy == DecompositionStrategy::PairTable {
        Some(PairSumTable::build(&c, &fb).ok_or("pair table unavailable")?)
    } else {
        None
    };
    let collector = RelationCollector::with_pair_table(&c, &fb, &opts, pair.as_ref())
        .ok_or("unsupported decomposition")?;
    let mut system = FactorBaseLogSolver::new(&c, &fb, &opts).ok_or("no projected columns")?;
    let expected_columns = system.columns();
    dump(b"factor_base_and_tables\0");
    let mut relations = Vec::new();
    let mut trials = 0;
    let mut solve_attempts = 0;
    let mut outcome = None;
    while trials < cfg.max_trials && outcome.is_none() {
        let count = cfg.batch_trials.min(cfg.max_trials - trials);
        let (rows, _) = collector.collect(RelationWorkUnit {
            seed: job.algorithm_seed,
            start: trials,
            count,
        });
        trials += count;
        dump(b"collection_and_decomposition\0");
        system.push(&rows);
        solve_attempts += 1;
        outcome = system.try_solve();
        relations.extend(rows);
        dump(b"verify_filter_and_linear_algebra\0");
    }
    let base = fb.points.iter().map(point).collect::<Vec<_>>();
    let report = system.report();
    let Some((table, solved)) = outcome else {
        return Ok(
            json!({"schema_version":1,"mode":"ic","status":"incomplete","fixture":metadata,
            "trials":trials,"columns":expected_columns,"relations":relations,
            "factor_base":base,"rejected_relations":report.rejected_relations}),
        );
    };
    if solved.rejected_relations != 0 || !table.verify(&c) {
        return Err("invalid relation or factor-base log certificate".into());
    }
    let columns = table
        .columns
        .iter()
        .map(|(p, l)| json!({"point":point(p),"log":l.to_string()}))
        .collect::<Vec<_>>();
    dump(b"log_certification\0");
    let solver = IndividualLogSolver::new(&c, &fb, &table, &opts, pair.as_ref())
        .ok_or("descent setup failed")?;
    let mut solutions = Vec::new();
    for (i, q) in targets.iter().enumerate() {
        let answer = solver.solve(q);
        solutions.push(
            json!({"index":i,"recovered":answer.as_ref().map(|(d,_)|d.to_string()),
            "trials":answer.as_ref().map(|(_,r)|r.trials)}),
        );
    }
    dump(b"individual_log\0");
    let verified = solutions.iter().zip(&targets).all(|(s, q)| {
        s["recovered"]
            .as_str()
            .and_then(|x| x.parse::<BigUint>().ok())
            .is_some_and(|d| d < c.subgroup_order && c.mul(c.generator(), &d) == *q)
    });
    dump(b"final_verification\0");
    Ok(
        json!({"schema_version":1,"mode":"ic","status":if verified{"complete"}else{"incomplete"},
        "fixture":metadata,"solutions":solutions,"factor_base":base,"relations":relations,
        "column_logs":columns,"columns":expected_columns,"trials":trials,"solve_attempts":solve_attempts,
        "accepted_relations":solved.relations,"duplicate_relations":solved.duplicate_relations,
        "rejected_relations":solved.rejected_relations,"summands":cfg.summands,
        "effective_factor_base":effective_base,
        "sparse_report":solved.sparse_report,"elapsed_seconds":start.elapsed().as_secs_f64()}),
    )
}

fn main() {
    let mut input = String::new();
    std::io::stdin()
        .take(1_048_577)
        .read_to_string(&mut input)
        .expect("stdin");
    let result = if input.len() > 1_048_576 {
        Err("job too large".into())
    } else {
        serde_json::from_str::<Job>(&input)
            .map_err(|e| e.to_string())
            .and_then(|job| {
                dump(b"startup_and_input\0");
                run(&job)
            })
    };
    let report = result
        .unwrap_or_else(|reason| json!({"schema_version":1,"status":"error","reason":reason}));
    let success = matches!(report["status"].as_str(), Some("complete" | "fixture"));
    println!("{}", report);
    if !success {
        std::process::exit(2);
    }
}
