//! Probe the next solving-degree closure on the public-synthetic n=31,
//! dimension-16 Koblitz decomposition cell.

use cryptanalysis_suite::binary_ecc::BinaryPoint;
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, f4_build_subprofile, f4_build_subprofile_reset, f4_layout_stats,
    f4_layout_stats_reset, f4_profile, f4_profile_reset, solve_boolean_system,
    solving_profile_sparse, split_rule_default, FieldStructure, SolveOptions, SolverEngine,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base_from_divisor, KoblitzCurve,
};
use cryptanalysis_suite::cryptanalysis::koblitz_symmetrised::{
    build_symmetrised_factor_base, build_symmetrised_system, divisor_for_dimension,
};
use num_bigint::BigUint;
use serde_json::json;
use std::time::Instant;

fn main() {
    let kind = std::env::args().nth(1).unwrap_or_else(|| "sym".to_owned());
    let degree: u32 = std::env::args()
        .nth(2)
        .map(|value| value.parse().expect("degree"))
        .unwrap_or(4);
    let solve = std::env::args().nth(3).as_deref() == Some("solve");
    assert!(matches!(kind.as_str(), "x" | "sym"));

    let n = 31u32;
    let curve = KoblitzCurve::new(0, n).expect("K_0/F_2^31");
    let divisor = divisor_for_dimension(n, 16).expect("dimension-16 divisor");
    let structure = FieldStructure::new(n, &curve.curve.irreducible);
    let target = curve.mul(curve.generator(), &BigUint::from(66_142u64));
    let (equations, n_vars) = if kind == "x" {
        let base = build_frobenius_factor_base_from_divisor(&curve, &divisor)
            .expect("Frobenius factor base");
        let BinaryPoint::Affine { x: target_x, .. } = &target else {
            panic!("fixture target must be affine");
        };
        let system = build_decomposition_system(
            &base.subspace_basis,
            target_x,
            &curve.curve.b,
            2,
            &structure,
        )
        .expect("quadratic S3 system");
        (system.equations, system.n_vars)
    } else {
        let base =
            build_symmetrised_factor_base(&curve, &divisor).expect("symmetrised factor base");
        let system = build_symmetrised_system(&curve, &base, &target, 2, &structure)
            .expect("symmetrised quadratic system");
        (system.equations, system.n_vars)
    };

    if solve {
        f4_profile_reset();
        f4_layout_stats_reset();
        f4_build_subprofile_reset();
        let started = Instant::now();
        let (roots, stats) = solve_boolean_system(
            &equations,
            n_vars,
            &SolveOptions {
                engine: SolverEngine::MatrixF4 { max_degree: degree },
                max_solutions: if kind == "x" { 1 } else { usize::MAX },
                node_budget: 50_000,
                split_rule: split_rule_default(),
            },
        );
        let profile = f4_profile();
        let (layout_hits, layout_misses) = f4_layout_stats();
        let (row_build_ns, matrix_pack_ns) = f4_build_subprofile();
        println!(
            "{}",
            json!({
                "schema_version":"1.0",
                "kind":kind,
                "degree":degree,
                "elapsed_ms":started.elapsed().as_secs_f64()*1000.0,
                "roots":roots.len(),
                "solve_stats":{
                    "reductions":stats.reductions,
                    "infeasible_branches":stats.infeasible_branches,
                    "propagations":stats.propagations,
                    "splits":stats.splits,
                    "exhausted":stats.exhausted,
                    "max_degree_built":stats.max_degree_built,
                    "oversize":stats.oversize
                },
                "f4_profile":{
                    "calls":profile.calls,
                    "build_ns":profile.build_ns,
                    "reduce_ns":profile.reduce_ns,
                    "readback_ns":profile.readback_ns,
                    "rows":profile.rows,
                    "cols":profile.cols,
                    "word_ops":profile.word_ops,
                    "oversize":profile.oversize
                },
                "layout_stats":{"hits":layout_hits,"misses":layout_misses},
                "build_subprofile":{"row_build_ns":row_build_ns,"matrix_pack_ns":matrix_pack_ns},
                "claim_boundary":"Public-synthetic exact solver-stage profile only"
            })
        );
        return;
    }

    let started = Instant::now();
    let profile = solving_profile_sparse(&equations, n_vars, degree);
    let profile_json = profile.map(|p| {
        json!({
            "rows":p.rows,
            "cols":p.cols,
            "rank":p.rank,
            "vars_determined":p.vars_determined,
            "vars_occurring":p.vars_occurring,
            "refuted":p.refuted,
            "resolves":p.resolves()
        })
    });
    println!(
        "{}",
        json!({
            "schema_version":"1.0",
            "kind":kind,
            "n":n,
            "dimension":16,
            "variables":n_vars,
            "equations":equations.len(),
            "degree":degree,
            "elapsed_ms":started.elapsed().as_secs_f64()*1000.0,
            "profile":profile_json,
            "claim_boundary":"Public-synthetic sparse solving-profile probe only"
        })
    );
}
