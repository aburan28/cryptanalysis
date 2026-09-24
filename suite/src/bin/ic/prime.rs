//! `ic prime` — index calculus on prime-field curves, by curve type.
//!
//! The other experiment commands run binary Koblitz and subfield curves
//! over `GF(2^n)`.  This one covers the prime-field types: generic curves
//! (NIST P-192 … P-521, the SECG `r1` curves, Brainpool, SM2, GOST), the
//! `j = 0` Koblitz-style curves (`secp256k1` and the `secpXXXk1` family)
//! and `j = 1728` curves.
//!
//! Given `--curve NAME` it reports the index-calculus structure of the
//! real curve — type, `j`-invariant, automorphism group, the GLV
//! eigenvalue and the `ζ`-equivariance of Semaev's `S₃` on a `j = 0`
//! curve, and the rho cost with and without the automorphism fold — and
//! then, like the binary rungs, runs the pipeline on a scaled-down curve
//! *of the same shape* (`a = −3` kept for a NIST curve, `b = 7` for
//! secp256k1) with a certified group order and planted logarithms.  The
//! deployed curve itself is never solved.
//!
//! Two solvers:
//!
//! - `orbit` (default): the automorphism-orbit pipeline of
//!   [`prime_orbit_index_calculus`](cryptanalysis_suite::cryptanalysis::prime_orbit_index_calculus)
//!   — one logarithm database, a descent per target, and the batched rho
//!   baseline on each, compared in group operations in the three timing
//!   classes of the binary `vs_rho` block.
//! - `semaev`: the reference Semaev `S₃` solvers of
//!   [`ec_index_calculus_curves`](cryptanalysis_suite::cryptanalysis::ec_index_calculus_curves),
//!   for cross-validation on prime-order curves up to 24 bits.

use super::{experiment, params};
use clap::{Args, ValueEnum};
use cryptanalysis_suite::cryptanalysis::bsgs_fast::FastPoint;
use cryptanalysis_suite::cryptanalysis::ec_index_calculus_curves::{
    endomorphism_facts, solve_scaled_instance, CurveKind, EndomorphismFacts, PrimeIcOptions,
    SolverRun, MAX_SEMAEV_BITS,
};
use cryptanalysis_suite::cryptanalysis::prime_orbit_index_calculus::{
    base_orbits, generate_instance, run_known_answer, BaseSizing, Coefficient, GeneratedInstance,
    OrbitIcOptions, OrbitIcReport, ScaledShape, MIN_FIELD_BITS,
};
use cryptanalysis_suite::ecc::{curve::CurveParams, point::Point};
use num_bigint::BigUint;
use num_traits::ToPrimitive;
use serde_json::{json, Value};
use std::io::Write;
use std::time::Instant;

/// Largest scaled field `ic prime` builds.  The certificate, rho and the
/// large-prime precomputation reach further; the full-decomposition
/// control, at `≈ r/|Aut|` operations, does not, and the operation budget
/// ends it as incomplete well before.
pub const MAX_PRIME_BITS: u32 = 40;

/// A prime-field curve type, as `--type` spells it.
#[derive(Clone, Copy, Debug, PartialEq, Eq, ValueEnum)]
pub enum TypeArg {
    /// `y² = x³ + a x + b`, automorphisms `{±1}` (P-192, P-224, …).
    Generic,
    /// `y² = x³ + b`, `j = 0`, order-6 automorphisms (secp256k1, …).
    #[value(alias = "koblitz")]
    J0,
    /// `y² = x³ + a x`, `j = 1728`, order-4 automorphisms.
    J1728,
}
impl TypeArg {
    fn kind(self) -> CurveKind {
        match self {
            TypeArg::Generic => CurveKind::Generic,
            TypeArg::J0 => CurveKind::J0,
            TypeArg::J1728 => CurveKind::J1728,
        }
    }
}

/// Which index-calculus implementation runs.
#[derive(Clone, Copy, Debug, PartialEq, Eq, ValueEnum)]
pub enum PrimeSolver {
    /// Factor base of full automorphism orbits, a logarithm database and a
    /// descent per target, against a batched rho.
    Orbit,
    /// The reference Semaev S3 solvers, prime-order curves up to 24 bits.
    Semaev,
}
impl PrimeSolver {
    fn name(self) -> &'static str {
        match self {
            PrimeSolver::Orbit => "orbit",
            PrimeSolver::Semaev => "semaev",
        }
    }
}

#[derive(Clone, Debug, Args)]
pub struct PrimeArgs {
    /// A built-in prime-field curve (see ic list): report its index-calculus
    /// structure and run a scaled-down curve of the same shape.
    #[arg(long, conflicts_with = "curve_type")]
    pub curve: Option<String>,
    /// The curve type to scale down when no --curve is named (default generic).
    #[arg(long = "type", value_enum, value_name = "TYPE")]
    pub curve_type: Option<TypeArg>,
    /// Field size of the scaled-down curve, in bits.
    #[arg(long, default_value_t = 24,
          value_parser = clap::value_parser!(u32).range(MIN_FIELD_BITS as i64..=MAX_PRIME_BITS as i64))]
    pub bits: u32,
    /// Index-calculus implementation.
    #[arg(long, value_enum, default_value_t = PrimeSolver::Orbit)]
    pub solver: PrimeSolver,
    /// Known-answer targets descended against one logarithm database (orbit).
    /// A descent's cost is heavy-tailed, so a charged ratio from a handful
    /// of targets is noisy.
    #[arg(long, default_value_t = 32, value_parser = clap::value_parser!(u64).range(1..=4096))]
    pub targets: u64,
    /// Planted logarithm of the first target; defaults to 53 unless --random-target.
    #[arg(long, value_parser = clap::value_parser!(u64).range(1..), conflicts_with = "random_target")]
    pub known_log: Option<u64>,
    /// Draw the first target's logarithm reproducibly from --seed.
    #[arg(long)]
    pub random_target: bool,
    /// Seeds the curve search, the targets, the factor base and every walk.
    #[arg(long, default_value_t = 1)]
    pub seed: u64,
    /// Factor-base orbits (orbit); 0 sizes the base: to the batch of targets
    /// with large primes (--orbits-per-target), else by --width.
    #[arg(long, default_value_t = 0)]
    pub orbits: usize,
    /// Size the base by width instead, in units of √r / |Aut| (orbit; 2
    /// without large primes).  A full-decomposition descent costs about
    /// √r / width.
    #[arg(long, conflicts_with = "orbits_per_target")]
    pub width: Option<f64>,
    /// With large primes, factor-base orbits per target, at least 16 in all
    /// (orbit; default 0.5).  The precompute and the descents then balance,
    /// and both grow as √r.
    #[arg(long)]
    pub orbits_per_target: Option<f64>,
    /// Relations collected per orbit before the logarithms are solved (orbit).
    #[arg(long, default_value_t = 1.5)]
    pub relations_per_orbit: f64,
    /// Collect relations by full 2-decomposition instead of the
    /// single-large-prime variation (orbit): the control, `≈ r/|Aut|`
    /// operations where large primes need `≈ √(m·r/|Aut|)`.
    #[arg(long)]
    pub no_large_primes: bool,
    /// Group-operation budget for the logarithm precomputation (orbit).
    #[arg(long, default_value_t = 1u64 << 32)]
    pub max_ops: u64,
    /// Skip the rho baseline (orbit).
    #[arg(long)]
    pub no_rho: bool,
    /// Factor-base points or orbits (semaev); 0 sizes it from the group order.
    #[arg(long, default_value_t = 0)]
    pub factor_base: usize,
    /// Relations collected beyond the factor-base size (semaev).
    #[arg(long, default_value_t = 6, value_parser = clap::value_parser!(u64).range(0..=4096))]
    pub extra_relations: u64,
    /// Decomposition trials allowed per relation (semaev).
    #[arg(long, default_value_t = 20_000, value_parser = clap::value_parser!(u64).range(1..=1_000_000))]
    pub max_trials: u64,
    /// Independent attempts each solver gets before it is reported as failed (semaev).
    #[arg(long, default_value_t = 3, value_parser = clap::value_parser!(u64).range(1..=16))]
    pub attempts: u64,
    /// On a j0 curve, use the Eisenstein-lattice factor base (semaev).
    #[arg(long)]
    pub eisenstein: bool,
}

fn point_json(p: &Point) -> Value {
    match p {
        Point::Infinity => Value::Null,
        Point::Affine { x, y } => json!({"x": params::hex(&x.value), "y": params::hex(&y.value)}),
    }
}

fn facts_json(f: &EndomorphismFacts) -> Value {
    json!({
        "type": f.kind.as_str(),
        "j_invariant": f.j_invariant.as_ref().map(params::hex),
        "automorphism_order": f.automorphism_order,
        "rho_speedup": f.rho_speedup,
        "cube_root_of_unity": f.cube_root_of_unity.as_ref().map(params::hex),
        "glv_lambda": f.glv_lambda.as_ref().map(params::hex),
        "s3_zeta_equivariant": f.s3_zeta_equivariant,
        "cofactor": f.cofactor,
    })
}

/// `log2 √(π n / 2)`, the plain rho step count, without leaving `f64`.
fn log2_rho(n: &BigUint) -> f64 {
    let log2_n = n.to_f64().map_or(n.bits() as f64, f64::log2);
    0.5 * (log2_n + (std::f64::consts::PI / 2.0).log2())
}

/// The structural report on a deployed curve: exact on its parameters,
/// and no discrete logarithm is attempted.
fn named_curve_json(c: &CurveParams) -> Value {
    let f = endomorphism_facts(c);
    let rho = log2_rho(&c.n);
    let w = f64::from(f.automorphism_order);
    let mut v = facts_json(&f);
    v["name"] = json!(c.name);
    v["field_bits"] = json!(c.p.bits());
    v["subgroup_order_bits"] = json!(c.n.bits());
    v["log2_rho_steps"] = json!(rho);
    v["log2_rho_steps_folded"] = json!(rho - 0.5 * w.log2());
    // r/|Aut|: the leading term of the orbit pipeline's precomputation.
    v["log2_r_over_automorphism_order"] =
        json!(2.0 * rho - (std::f64::consts::PI / 2.0).log2() - w.log2());
    v["evidence_scope"] = json!("structure_only");
    v
}

fn coefficient_json(c: Coefficient) -> Value {
    match c {
        Coefficient::Random => json!("random"),
        Coefficient::Fixed(v) => json!(v),
    }
}

fn shape_json(s: &ScaledShape) -> Value {
    json!({"type": s.kind.as_str(), "a": coefficient_json(s.a), "b": coefficient_json(s.b),
           "max_cofactor": s.max_cofactor})
}

fn instance_json(inst: &GeneratedInstance, seed: u64) -> Value {
    let c = &inst.curve;
    let params = c.params("scaled");
    let cert = &inst.certificate;
    json!({
        "type": c.kind.as_str(),
        "field_bits": inst.field_bits(),
        "p": params.p.to_string(),
        "a": params.a.to_string(),
        "b": params.b.to_string(),
        "group_order": cert.group_order.to_string(),
        "cofactor": cert.cofactor,
        "subgroup_order": cert.subgroup_order.to_string(),
        "generator": point_json(&c.generator()),
        "order_certificate": {
            "method": "bsgs over the Hasse interval; N = h·r, r prime and wider than the interval, [h]P ≠ O",
            "hasse_interval": [cert.hasse_lo.to_string(), cert.hasse_hi.to_string()],
            "bsgs_steps": cert.bsgs_steps,
        },
        "curves_tried": inst.curves_tried,
        "seed": seed,
        "endomorphism": facts_json(&endomorphism_facts(&params)),
    })
}

fn semaev_solver_json(s: &SolverRun) -> Value {
    json!({
        "method": s.method,
        "recovered": s.recovered.as_ref().map(ToString::to_string),
        "verified": s.verified,
        "attempts": s.attempts,
        "seconds": s.seconds,
    })
}

/// `rho / ic`, or `None` when index calculus spent nothing.
fn ratio(rho: f64, ic: f64) -> Option<f64> {
    (ic > 0.0).then(|| rho / ic)
}

fn orbit_json(rep: &OrbitIcReport, targets: &[(u64, FastPoint)], opts: &OrbitIcOptions) -> Value {
    let t = targets.len() as f64;
    let pre = rep.precompute_ops() as f64;
    let des = rep.mean_descent_ops();
    let rho = rep.mean_rho_ops();
    let rho_pre = rep.rho_precompute_ops as f64;
    let n_rho = rep.rhos.len().max(1) as f64;
    let mean_steps = rep.rhos.iter().map(|r| r.steps).sum::<u64>() as f64 / n_rho;
    let mean_setup = rep.rhos.iter().map(|r| r.setup_ops).sum::<u64>() as f64 / n_rho;
    // The folded walk would pay the same setup.
    let folded = rep
        .rhos
        .first()
        .map(|r| r.expected_steps_folded + mean_setup);
    let logs = &rep.logs;
    let per_descent: Vec<Value> = rep
        .descents
        .iter()
        .zip(targets)
        .map(|(d, &(k, _))| {
            json!({"expected": k.to_string(), "recovered": d.recovered.map(|v| v.to_string()),
                   "verified": d.verified, "ops": OrbitIcReport::descent_ops(d), "trials": d.trials,
                   "through_large_prime": d.through_large_prime, "seconds": d.seconds})
        })
        .collect();
    let per_rho: Vec<Value> = rep
        .rhos
        .iter()
        .zip(targets)
        .map(|(r, &(k, _))| {
            json!({"expected": k.to_string(), "recovered": r.recovered.map(|v| v.to_string()),
                   "verified": r.verified, "steps": r.steps, "setup_ops": r.setup_ops,
                   "seconds": r.seconds})
        })
        .collect();
    let rho_run = !rep.rhos.is_empty();
    json!({
        "factor_base": {
            "orbits": logs.orbits,
            "points": logs.points,
            "automorphism_order": rep.automorphism_order,
            "certified_orbits": logs.certified_columns,
            "draws": logs.factor_base_draws,
            "sizing": opts.sizing().as_str(),
            "orbits_per_target": opts.orbits_per_target,
            "width": opts.width,
        },
        "logs": {
            "collection": if opts.large_primes { "large_primes" } else { "full_decompositions" },
            "trials": logs.trials,
            "relations": logs.relations,
            "full_relations": logs.full_relations,
            "combined_relations": logs.combined_relations,
            "distinct_large_primes": logs.distinct_large_primes,
            "known_large_primes": logs.known_large_primes,
            "rejected_relations": logs.rejected_relations,
            "oracle_ops": logs.oracle_ops,
            "probe_ops": logs.probe_ops,
            "components": logs.system.components,
            "determined_components": logs.system.determined_components,
            "inconsistent_components": logs.system.inconsistent_components,
            "certified_columns": logs.certified_columns,
            "uncertified_columns": logs.uncertified_columns,
            "seconds": logs.seconds,
        },
        "descent": {
            "verified": rep.descents_verified(),
            "through_large_primes": rep.descents_through_large_primes(),
            "mean_ops": des,
            "total_ops": rep.descent_ops_total(),
            "per_target": per_descent,
        },
        "rho": if rho_run { json!({
            "walk": "32 r-adding walks sharing one inversion per step, distinguished points; no automorphism fold",
            "walks": rep.rhos[0].walks,
            "dp_bits": rep.rhos[0].dp_bits,
            "verified": rep.rhos_verified(),
            "precompute_ops": rep.rho_precompute_ops,
            "mean_steps": mean_steps,
            "mean_setup_ops": mean_setup,
            "mean_ops": rho,
            "expected_steps": rep.rhos[0].expected_steps,
            "expected_steps_folded": rep.rhos[0].expected_steps_folded,
            "per_target": per_rho,
        }) } else { Value::Null },
        "vs_rho": if rho_run { json!({
            "unit": "group operations: affine additions, each sharing a batched inversion; setup scalar multiplications charged 1.5·bits(r) on both sides, certification checks on neither",
            "targets": targets.len(),
            "charged": {"ic_ops_per_target": des, "rho_ops_per_target": rho,
                        "ratio": ratio(rho, des),
                        "folded_rho_ops_per_target_expected": folded,
                        "ratio_vs_folded_expectation": folded.and_then(|f| ratio(f, des))},
            "amortised": {"ic_ops_per_target": pre / t + des, "rho_ops_per_target": rho_pre / t + rho,
                          "ratio": ratio(rho_pre / t + rho, pre / t + des)},
            "whole_process": {"ic_ops": pre + des * t, "rho_ops": rho_pre + rho * t,
                              "ratio": ratio(rho_pre + rho * t, pre + des * t)},
            "verdict": {
                "all_verified": rep.descents_verified() == targets.len() && rep.rhos_verified() == targets.len(),
                "charged_ic_cheaper": des < rho,
                "charged_ic_cheaper_than_folded_rho": folded.is_some_and(|f| des < f),
                "whole_process_ic_cheaper": pre + des * t < rho_pre + rho * t,
            },
        }) } else { Value::Null },
    })
}

pub fn run(args: PrimeArgs, quiet: bool) -> Result<Value, String> {
    let begin = Instant::now();
    let named =
        match &args.curve {
            Some(name) => Some(params::prime_curve(name).ok_or_else(|| {
                format!("{name:?} is not a built-in prime-field curve; use ic list")
            })?),
            None => None,
        };
    let shape = match (&named, args.curve_type) {
        (Some(c), _) => ScaledShape::of_curve(c),
        (None, Some(t)) => ScaledShape::of_kind(t.kind()),
        (None, None) => ScaledShape::of_kind(CurveKind::Generic),
    };
    let kind = shape.kind;
    if args.solver == PrimeSolver::Semaev {
        if args.bits > MAX_SEMAEV_BITS {
            return Err(format!(
                "--solver semaev is O(p^(3/2)) in the general arithmetic; keep --bits at most {MAX_SEMAEV_BITS}"
            ));
        }
        if kind == CurveKind::J1728 {
            return Err(
                "--solver semaev needs a prime-order curve, and every j1728 curve has the \
                        rational 2-torsion point (0, 0); use --solver orbit"
                    .into(),
            );
        }
    }
    if args.eisenstein && (args.solver != PrimeSolver::Semaev || kind != CurveKind::J0) {
        return Err("--eisenstein applies to --solver semaev on j0 curves only".into());
    }
    if !quiet {
        println!("ic — prime-field index calculus by curve type");
        if let Some(c) = &named {
            let f = endomorphism_facts(c);
            println!(
                "Named curve: {} ({}, {}-bit field, cofactor {}); |Aut| = {}; rho ≈ 2^{:.1} steps (2^{:.1} folded); structure only, never solved",
                c.name,
                f.kind.as_str(),
                c.p.bits(),
                c.h,
                f.automorphism_order,
                log2_rho(&c.n),
                log2_rho(&c.n) - 0.5 * f64::from(f.automorphism_order).log2()
            );
        }
        let _ = std::io::stdout().flush();
    }
    let known = if args.random_target {
        None
    } else {
        Some(args.known_log.unwrap_or(53))
    };
    let inst = generate_instance(shape, args.bits, known, args.seed)?;
    let c = &inst.curve;
    if !quiet {
        let params = c.params("scaled");
        println!(
            "Scaled instance: {} y² = x³ + {}x + {} over GF({}) ({} bits); #E = {} = {} · {} (certified); |Aut| = {}",
            kind.as_str(),
            params.a,
            params.b,
            params.p,
            inst.field_bits(),
            inst.certificate.group_order,
            inst.certificate.cofactor,
            inst.certificate.subgroup_order,
            c.automorphism_order()
        );
        let _ = std::io::stdout().flush();
    }
    let mut report = json!({
        "schema_version": 1,
        "operation": "prime",
        "evidence_scope": "synthetic_known_answer",
        "solver": args.solver.name(),
        "curve_type": kind.as_str(),
        "named_curve": named.as_ref().map(named_curve_json),
        "shape": shape_json(&shape),
        "instance": instance_json(&inst, args.seed),
    });
    let complete = match args.solver {
        PrimeSolver::Orbit => {
            let targets = inst.targets(args.targets as usize, args.seed);
            let points: Vec<FastPoint> = targets.iter().map(|&(_, q)| q).collect();
            let defaults = OrbitIcOptions::default();
            let opts = OrbitIcOptions {
                orbits: args.orbits,
                width: args.width.unwrap_or(defaults.width),
                orbits_per_target: match (args.width, args.orbits_per_target) {
                    (Some(_), _) => 0.0,
                    (None, k) => k.unwrap_or(defaults.orbits_per_target),
                },
                relations_per_orbit: args.relations_per_orbit,
                large_primes: !args.no_large_primes,
                max_ops: args.max_ops,
                skip_rho: args.no_rho,
                seed: args.seed,
                ..defaults
            };
            if !quiet {
                let sized = match opts.sizing() {
                    BaseSizing::Explicit => "as given".to_string(),
                    BaseSizing::Batch => {
                        format!("to the batch, {} per target", opts.orbits_per_target)
                    }
                    BaseSizing::Width => format!("to width {}", opts.width),
                };
                println!(
                    "Targets: {}; factor base of {} orbits, sized {sized}; precompute budget {} group operations",
                    targets.len(),
                    base_orbits(c, &opts, targets.len()),
                    opts.max_ops
                );
                let _ = std::io::stdout().flush();
            }
            let rep = run_known_answer(c, &points, &opts);
            let logs_sound = rep.logs.rejected_relations == 0
                && rep.logs.uncertified_columns == 0
                && rep.logs.system.inconsistent_components == 0;
            let first = &rep.descents[0];
            report["result"] = json!({"expected": targets[0].0.to_string(),
                "recovered": first.recovered.map(|v| v.to_string()), "verified": first.verified});
            let body = orbit_json(&rep, &targets, &opts);
            for (k, v) in body.as_object().expect("object") {
                report[k] = v.clone();
            }
            logs_sound
                && rep.descents_verified() == targets.len()
                && (args.no_rho || rep.rhos_verified() == targets.len())
        }
        PrimeSolver::Semaev => {
            let scaled = inst.scaled();
            let opts = PrimeIcOptions {
                factor_base: args.factor_base,
                extra_relations: args.extra_relations as usize,
                max_trials_per_relation: args.max_trials as usize,
                attempts: args.attempts as usize,
                rho_max_steps: 0,
                eisenstein: args.eisenstein,
                seed: args.seed,
            };
            let rep = solve_scaled_instance(&scaled, &opts)?;
            report["result"] = json!({"expected": scaled.known_log.to_string(),
                "recovered": rep.ic.recovered.as_ref().map(ToString::to_string),
                "verified": rep.ic.verified});
            report["index_calculus"] = json!({
                "factor_base": rep.factor_base,
                "factor_base_unit": if kind == CurveKind::J0 { "orbits" } else { "points" },
                "summands": 2,
                "solver": semaev_solver_json(&rep.ic),
            });
            report["rho"] = json!({
                "solver": semaev_solver_json(&rep.rho),
                "walk": "plain r-adding walk with Floyd cycle detection; no automorphism fold",
                "automorphism_order": rep.automorphism_order,
                "expected_steps": rep.rho_expected_steps,
                "expected_steps_folded": rep.rho_expected_steps_folded,
            });
            report["vs_rho"] = json!({
                "unit": "seconds of num-bigint arithmetic on both sides; operations are not instrumented",
                "timing_class": "whole_process_single_target",
                "rho_seconds_over_ic_seconds": ratio(rep.rho.seconds, rep.ic.seconds),
            });
            rep.ic.verified && rep.rho.verified
        }
    };
    report["status"] = json!(if complete { "complete" } else { "incomplete" });
    report["elapsed_seconds"] = json!(begin.elapsed().as_secs_f64());
    report["resources"] = experiment::resources();
    report["scope"] = json!(concat!(
        "A scaled-down curve of the requested type and shape with a certified group order and ",
        "planted logarithms. The orbit solver precomputes one factor-base logarithm database over ",
        "full automorphism orbits, descends every target against it and runs a batched rho on each; ",
        "the semaev solver runs the reference S3 solvers. Every logarithm is accepted only after ",
        "[d]G == Q. A named curve is inspected for structure only and is never solved."
    ));
    report["limitations"] = json!([
        "No imported target was used; the deployed curve's own discrete logarithm is never attempted.",
        "With large primes and a base sized to the batch, the precomputation and the T descents each cost on the order of sqrt(T r/|Aut|) group operations: rho's square-root scaling, not better. The whole-process gain over rho is one database amortised over T targets, about sqrt(|Aut| T) against independent unfolded walks; a folded batch rho that shares distinguished points between targets (Kuhn-Struik) amortises the same way and is not the baseline here.",
        "Without large primes (the control) the precomputation costs about r/|Aut| group operations, linear in the subgroup order.",
        "The rho baseline does not fold by the automorphism group; the folded expectation is analytic, and a charged comparison against it is reported separately.",
        "Operation counts compare implementations only to within the cost of one affine addition on each side; wall time is reported beside them.",
        "This run does not establish scaling beyond the sizes it ran, or challenge readiness."
    ]);
    Ok(report)
}
