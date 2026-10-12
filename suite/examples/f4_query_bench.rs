//! One target-dependent Boolean point-decomposition query, including system
//! construction, F4 search, independent equation evaluation, and curve replay.
//! Device upload, launches, synchronization and download occur inside the
//! solver's measured interval when the CUDA echelon path is selected.

use cryptanalysis_suite::binary_ecc::{BinaryPoint, F2mElement};
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, f4_profile, f4_profile_reset, solve_boolean_system_filtered,
    FieldStructure, SolveOptions, SolverEngine, SplitRule,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base, points_with_x, KoblitzCurve,
};
use num_bigint::BigUint;
use serde_json::json;
use std::time::Instant;

fn arg<'a>(args: &'a [String], name: &str) -> Option<&'a str> {
    args.windows(2)
        .find(|w| w[0] == name)
        .map(|w| w[1].as_str())
}

fn closes(kc: &KoblitzCurve, xs: &[F2mElement], targets: &[BinaryPoint]) -> bool {
    fn walk(
        kc: &KoblitzCurve,
        xs: &[F2mElement],
        targets: &[BinaryPoint],
        depth: usize,
        sum: &BinaryPoint,
    ) -> bool {
        if depth == xs.len() {
            return targets.contains(sum);
        }
        points_with_x(&kc.curve, &xs[depth])
            .iter()
            .any(|p| walk(kc, xs, targets, depth + 1, &kc.add(sum, p)))
    }
    !targets.is_empty() && walk(kc, xs, targets, 0, &BinaryPoint::Infinity)
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let cell: Vec<u64> = arg(&args, "--cell")
        .unwrap_or("0:9:2:77")
        .split(':')
        .map(|s| s.parse().expect("--cell a:n:m:x"))
        .collect();
    assert_eq!(cell.len(), 4, "--cell a:n:m:x");
    let (a, n, m, raw) = (cell[0] as u8, cell[1] as u32, cell[2] as usize, cell[3]);
    let degree: u32 = arg(&args, "--degree").map_or(5, |s| s.parse().unwrap());
    let engine_name = arg(&args, "--engine").unwrap_or("f4");
    let engine = match engine_name {
        "f4" => SolverEngine::MatrixF4 { max_degree: degree },
        "f5" => SolverEngine::MatrixF5 { max_degree: degree },
        _ => panic!("--engine must be f4 or f5"),
    };
    let node_budget: usize = arg(&args, "--node-budget").map_or(4096, |s| s.parse().unwrap());
    let max_solutions: usize = arg(&args, "--max-solutions").map_or(256, |s| s.parse().unwrap());

    // Curve and factor-base preparation is reusable across target points.
    let kc = KoblitzCurve::new(a, n).expect("unsupported Koblitz curve");
    let fb = build_frobenius_factor_base(&kc, 0).expect("factor-base construction failed");
    let field_modulus = (1u64 << kc.curve.irreducible.degree)
        | kc.curve
            .irreducible
            .low_terms
            .iter()
            .fold(0u64, |bits, &degree| bits | (1u64 << degree));
    let basis_coordinates: Vec<String> = fb
        .subspace_basis
        .iter()
        .map(|coordinate| coordinate.to_biguint().to_string())
        .collect();
    let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
    let opts = SolveOptions {
        engine,
        max_solutions,
        node_budget,
        split_rule: SplitRule::LowestFree,
    };

    f4_profile_reset();
    let start = Instant::now();
    let x_r = F2mElement::from_biguint(&BigUint::from(raw), n);
    let targets = points_with_x(&kc.curve, &x_r);
    let converted = Instant::now();
    let sys = build_decomposition_system(&fb.subspace_basis, &x_r, &kc.curve.b, m, &st)
        .expect("decomposition system exceeds variable limit");
    let built = Instant::now();
    let mut independent_checks = 0usize;
    let mut curve_lifts = 0usize;
    let mut accepted = None;
    let mut callback_ns = 0u128;
    let (roots, stats) =
        solve_boolean_system_filtered(&sys.equations, sys.n_vars, &opts, |point| {
            let callback_start = Instant::now();
            independent_checks += 1;
            // Re-evaluate each original Boolean equation without the solver's
            // polynomial-evaluation method or its reduced matrix rows.
            let verified = sys.equations.iter().all(|eq| {
                !eq.terms.iter().fold(false, |parity, term| {
                    parity ^ ((point & term.mask) == term.mask)
                })
            });
            assert!(verified, "solver returned a non-root");
            let xs: Vec<_> = (0..m)
                .map(|i| sys.summand_x(&fb.subspace_basis, point, i, n))
                .collect();
            curve_lifts += 1;
            let good = closes(&kc, &xs, &targets);
            if good {
                accepted = Some(point);
            }
            callback_ns += callback_start.elapsed().as_nanos();
            good
        });
    let solved = Instant::now();
    let algebra_profile = f4_profile();
    let summary = cryptanalysis_suite::cryptanalysis::f4_gpu::offload_summary();
    let summarized = Instant::now();
    let phase_ns = [
        converted.duration_since(start).as_nanos(),
        built.duration_since(converted).as_nanos(),
        solved.duration_since(built).as_nanos(),
        summarized.duration_since(solved).as_nanos(),
    ];
    let online_ns = summarized.duration_since(start).as_nanos();
    assert_eq!(phase_ns.iter().sum::<u128>(), online_ns);
    assert!(callback_ns <= phase_ns[2]);
    let status = if accepted.is_some() {
        "verified-decomposition"
    } else if stats.exhausted {
        "node-cap"
    } else if roots.len() == max_solutions {
        "solution-cap"
    } else {
        "complete-no-decomposition"
    };
    let report = json!({
        "harness": "f4_query_bench", "status": status,
        "input": {"curve_a": a, "field_degree": n, "summands": m,
            "target_x": raw, "max_degree": degree, "node_budget": node_budget,
            "max_solutions": max_solutions, "engine": engine_name,
            "field_modulus": field_modulus,
            "curve_b": kc.curve.b.to_biguint().to_string(),
            "curve_order": kc.group_order.to_string(),
            "subgroup_order": kc.subgroup_order.to_string(),
            "cofactor": kc.cofactor.to_string(),
            "factor_base_points": fb.points.len(), "factor_base_dimension": fb.ell,
            "factor_base_basis": basis_coordinates},
        "system": {"variables": sys.n_vars, "equations": sys.equations.len()},
        "result": {"accepted_assignment": accepted, "roots_recorded": roots.len(),
            "independent_equation_checks": independent_checks, "curve_lifts": curve_lifts,
            "target_points": targets.len(), "exhausted": stats.exhausted},
        "solver": {"reductions": stats.reductions, "splits": stats.splits,
            "infeasible_branches": stats.infeasible_branches,
            "propagations": stats.propagations, "max_degree_built": stats.max_degree_built,
            "oversize": stats.oversize},
        "algebra": algebra_profile,
        "gpu": {"mode": summary.mode, "device": summary.device,
            "matrices": summary.matrices, "words": summary.words,
            "upload_eliminate_download_seconds": summary.seconds},
        "phase_ns": {"target_conversion": phase_ns[0], "system_build": phase_ns[1],
            "solve_including_callback": phase_ns[2], "offload_summary": phase_ns[3],
            "independent_equation_and_curve_callback_subset": callback_ns},
        "online_ns": online_ns,
        "timing_boundary": "target conversion through independent equations and curve replay, including all F4 calls and CUDA transfers/synchronization",
        "qualified_speedup": null
    });
    println!("{}", serde_json::to_string(&report).unwrap());
    if let Some(path) = arg(&args, "--out") {
        assert!(
            !std::path::Path::new(path).exists(),
            "output already exists"
        );
        std::fs::write(path, serde_json::to_string_pretty(&report).unwrap() + "\n")
            .expect("write report");
    }
}
