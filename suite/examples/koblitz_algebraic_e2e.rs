//! Fully charged unknown-scalar run over a GGMP linearised-polynomial factor base.
//!
//! The factor base is selected from a factor of `T^n-1`; this program never
//! constructs factor-base logarithms or a subgroup log table.  The scalar is
//! used only by the harness to create a public target and verify the answer.

use cryptanalysis_suite::binary_ecc::BinaryPoint;
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::SolverEngine;
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base, build_frobenius_factor_base_from_divisor,
    koblitz_index_calculus_dlp_with_factor_base, DecompositionStrategy, FactorBaseDomain,
    KoblitzCurve, KoblitzIcOptions, SatDecompositionOptions,
};
use cryptanalysis_suite::cryptanalysis::pollard_rho::{pollard_rho_dlp, RhoOptions};
use cryptanalysis_suite::cryptanalysis::semaev_sat::XorEncoding;
use cryptanalysis_suite::utils::mod_inverse;
use num_bigint::BigUint;
use num_traits::{One, Zero};
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use serde_json::json;
use std::time::Instant;

fn point_json(point: &BinaryPoint) -> serde_json::Value {
    match point {
        BinaryPoint::Infinity => serde_json::Value::Null,
        BinaryPoint::Affine { x, y } => json!({
            "x":x.to_biguint().to_string(),
            "y":y.to_biguint().to_string()
        }),
    }
}

#[derive(Clone)]
struct QuotientState {
    point: BinaryPoint,
    a: BigUint,
    b: BigUint,
}

fn canonicalize(curve: &KoblitzCurve, state: QuotientState) -> QuotientState {
    if state.point == BinaryPoint::Infinity {
        return state;
    }
    let modulus = &curve.subgroup_order;
    let mut current = state.point.clone();
    let mut lambda_k = BigUint::one();
    let mut best: Option<(Option<(BigUint, BigUint)>, BinaryPoint, BigUint)> = None;
    for _ in 0..curve.n {
        for (negated, candidate) in [
            (false, current.clone()),
            (
                true,
                cryptanalysis_suite::binary_ecc::curve::point_neg(&current),
            ),
        ] {
            let key = match &candidate {
                BinaryPoint::Infinity => None,
                BinaryPoint::Affine { x, y } => Some((x.to_biguint(), y.to_biguint())),
            };
            let factor = if negated && !lambda_k.is_zero() {
                modulus - &lambda_k
            } else {
                lambda_k.clone()
            };
            if best.as_ref().is_none_or(|(old, _, _)| key < *old) {
                best = Some((key, candidate, factor));
            }
        }
        current = curve.frobenius(&current);
        lambda_k = (&lambda_k * &curve.lambda) % modulus;
    }
    let (_, point, factor) = best.expect("nonempty signed Frobenius orbit");
    QuotientState {
        point,
        a: (&state.a * &factor) % modulus,
        b: (&state.b * &factor) % modulus,
    }
}

fn sub_mod(left: &BigUint, right: &BigUint, modulus: &BigUint) -> BigUint {
    if left >= right {
        (left - right) % modulus
    } else {
        let difference = (right - left) % modulus;
        if difference.is_zero() {
            BigUint::zero()
        } else {
            modulus - difference
        }
    }
}

fn automorphism_rho(
    curve: &KoblitzCurve,
    target: &BinaryPoint,
    seed: u64,
) -> (BigUint, u64, u64, u32) {
    let modulus = &curve.subgroup_order;
    let mut rng = StdRng::seed_from_u64(seed);
    let mut additions = 0u64;
    let mut iterations = 0u64;
    for restart in 0..64u32 {
        // A fruitless cycle is a property of the functional graph, so merely
        // changing the start point can return to the same bad cycle. Derive a
        // fresh deterministic jump table for every charged restart.
        let jumps: Vec<(BinaryPoint, BigUint, BigUint)> = (0..16)
            .map(|_| {
                let a = BigUint::from(rng.gen_range(1..modulus.to_u64_digits()[0]));
                let b = BigUint::from(rng.gen_range(1..modulus.to_u64_digits()[0]));
                let point = curve.add(&curve.mul(curve.generator(), &a), &curve.mul(target, &b));
                (point, a, b)
            })
            .collect();
        let bucket = |point: &BinaryPoint| -> usize {
            match point {
                BinaryPoint::Infinity => 0,
                BinaryPoint::Affine { x, y } => {
                    let x0 = x.to_biguint().iter_u64_digits().next().unwrap_or(0);
                    let y0 = y.to_biguint().iter_u64_digits().next().unwrap_or(0);
                    (x0 ^ y0.rotate_left(17)) as usize % jumps.len()
                }
            }
        };
        let step = |state: QuotientState| {
            let jump = &jumps[bucket(&state.point)];
            canonicalize(
                curve,
                QuotientState {
                    point: curve.add(&state.point, &jump.0),
                    a: (&state.a + &jump.1) % modulus,
                    b: (&state.b + &jump.2) % modulus,
                },
            )
        };
        let a = BigUint::from(rng.gen_range(1..modulus.to_u64_digits()[0]));
        let b = BigUint::from(rng.gen_range(1..modulus.to_u64_digits()[0]));
        let initial = canonicalize(
            curve,
            QuotientState {
                point: curve.add(&curve.mul(curve.generator(), &a), &curve.mul(target, &b)),
                a,
                b,
            },
        );
        let mut tortoise = step(initial.clone());
        let mut hare = step(step(initial));
        additions += 3;
        for _ in 0..(1u64 << 28) {
            iterations += 1;
            if tortoise.point == hare.point {
                let numerator = sub_mod(&tortoise.a, &hare.a, modulus);
                let denominator = sub_mod(&hare.b, &tortoise.b, modulus);
                if let Some(inverse) = mod_inverse(&denominator, modulus) {
                    let candidate = (&numerator * inverse) % modulus;
                    if curve.mul(curve.generator(), &candidate) == *target {
                        return (candidate, iterations, additions, restart);
                    }
                }
                break;
            }
            tortoise = step(tortoise);
            hare = step(step(hare));
            additions += 3;
        }
    }
    panic!("signed-Frobenius quotient rho exhausted restarts")
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    assert!(
        matches!(args.len(), 9 | 10),
        "usage: koblitz_algebraic_e2e <ic|rho|rho-auto> <n> <a> <m> <secret> <seed> <conflict-budget> <max-trials> [single:<index>|divisor:<i,j,...>]"
    );
    let mode = args[1].as_str();
    let n: u32 = args[2].parse().expect("n");
    let a: u8 = args[3].parse().expect("a");
    let m: usize = args[4].parse().expect("m");
    let secret: u64 = args[5].parse().expect("secret");
    let seed: u64 = args[6].parse().expect("seed");
    let conflict_budget: u64 = args[7].parse().expect("conflict budget");
    let max_trials: usize = args[8].parse().expect("max trials");
    let factor_spec = args.get(9).map(String::as_str).unwrap_or("single:0");
    assert!(matches!(mode, "ic" | "rho" | "rho-auto"));

    let total = Instant::now();
    let curve_start = Instant::now();
    let curve = KoblitzCurve::new(a, n).expect("usable prime-order subgroup");
    let curve_ns = curve_start.elapsed().as_nanos();
    assert!(BigUint::from(secret) < curve.subgroup_order && secret > 0);
    let target_start = Instant::now();
    let target = curve.mul(curve.generator(), &BigUint::from(secret));
    let target_ns = target_start.elapsed().as_nanos();

    if mode == "rho-auto" {
        let rho_start = Instant::now();
        let (solution, iterations, additions, restarts) = automorphism_rho(&curve, &target, seed);
        let rho_ns = rho_start.elapsed().as_nanos();
        let verified =
            solution == BigUint::from(secret) && curve.mul(curve.generator(), &solution) == target;
        let attempts = u64::from(restarts) + 1;
        println!(
            "{}",
            serde_json::to_string_pretty(&json!({
                "kind":"koblitz_unknown_scalar_automorphism_rho_control",
                "mode":"rho-auto",
                "scope":"signed-Frobenius quotient r-adding Pollard rho control",
                "n":n,"a":a,"subgroup_order":curve.subgroup_order.to_string(),
                "target":point_json(&target),"seed":seed,
                "iterations":iterations,"walk_step_additions":additions,"restarts":restarts,
                "jump_table_additions":16*attempts,"initial_state_additions":attempts,
                "reported_group_additions":additions+17*attempts,
                "rho_setup_scalar_multiplications":34*attempts,
                "target_construction_scalar_multiplications":1,
                "verified_unknown_scalar_recovery":verified,
                "automorphism_optimized":true,"automorphism_group_bound":2*n,
                "timing_ns":{"curve_construction":curve_ns,"target_construction":target_ns,"rho":rho_ns,"end_to_end":total.elapsed().as_nanos()}
            })).unwrap()
        );
        assert!(verified);
        return;
    }

    if mode == "rho" {
        let rho_start = Instant::now();
        let solution = pollard_rho_dlp(
            curve.generator(),
            &target,
            &curve.subgroup_order,
            |left, right| curve.add(left, right),
            |left, right| left == right,
            |point| match point {
                BinaryPoint::Infinity => 0,
                BinaryPoint::Affine { x, .. } => {
                    (x.to_biguint().iter_u64_digits().next().unwrap_or(0) % 3) as u8
                }
            },
            |point, scalar| curve.mul(point, scalar),
            &RhoOptions {
                max_iterations: 1u64 << 28,
                max_restarts: 64,
                seed: Some(seed),
            },
        )
        .expect("generic Pollard rho run");
        let rho_ns = rho_start.elapsed().as_nanos();
        let verified = solution.x == BigUint::from(secret)
            && curve.mul(curve.generator(), &solution.x) == target;
        println!(
            "{}",
            serde_json::to_string_pretty(&json!({
                "kind":"koblitz_unknown_scalar_generic_rho_control",
                "mode":"rho",
                "scope":"same-curve generic Pollard rho control; not automorphism optimized",
                "n":n,"a":a,"subgroup_order":curve.subgroup_order.to_string(),
                "target":point_json(&target),"seed":seed,
                "iterations":solution.iterations,"verified_unknown_scalar_recovery":verified,
                "automorphism_optimized":false,
                "timing_ns":{"curve_construction":curve_ns,"target_construction":target_ns,"rho":rho_ns,"end_to_end":total.elapsed().as_nanos()}
            })).unwrap()
        );
        assert!(verified);
        return;
    }

    let factor_base_start = Instant::now();
    let (factor_base, factor_kind, factor_indices) =
        if let Some(index) = factor_spec.strip_prefix("single:") {
            let index: usize = index.parse().expect("single factor index");
            (
                build_frobenius_factor_base(&curve, index)
                    .expect("GGMP single-factor linearised-polynomial factor base"),
                "ggmp_single_factor_kernel",
                vec![index],
            )
        } else if let Some(indices) = factor_spec.strip_prefix("divisor:") {
            let indices: Vec<usize> = indices
                .split(',')
                .map(|value| value.parse().expect("divisor factor index"))
                .collect();
            assert!(!indices.is_empty(), "divisor needs at least one factor");
            (
                build_frobenius_factor_base_from_divisor(&curve, &indices)
                    .expect("GGMP divisor linearised-polynomial factor base"),
                "ggmp_divisor_kernel",
                indices,
            )
        } else {
            panic!("factor specification must start with single: or divisor:")
        };
    let factor_base_ns = factor_base_start.elapsed().as_nanos();
    assert_eq!(factor_base.domain, FactorBaseDomain::LinearSubspace);
    let factor = factor_base.f_j;
    let factor_exponents = factor_base.linearised_exponents.clone();

    let options = KoblitzIcOptions {
        m,
        descent_m: None,
        collection_window: None,
        factor_index: factor_indices[0],
        extra_relations: 2,
        max_trials,
        seed,
        strategy: DecompositionStrategy::Sat,
        engine: SolverEngine::default(),
        weil_charts: None,
        node_budget: 0,
        max_models: 64,
        sat_macaulay_degree: None,
        sat_options: SatDecompositionOptions {
            encoding: XorEncoding::Native,
            branch_on_summands: true,
            restrict_to_factor_base: true,
            trace_constraint: true,
            conflict_budget,
            symmetry_breaking: false,
        },
        collapse_negation: true,
        stop_on_verified_rank: true,
        relation_batch_size: 1,
        allow_direct_relation: false,
        collapse_projected_orbits: true,
        crossbred: None,
        wdsat_binary: None,
        wdsat_timeout_ms: 5_000,
        linear_algebra:
            cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::LinearAlgebra::Dense,
        f4_batch: None,
    };
    let solve_start = Instant::now();
    let report =
        koblitz_index_calculus_dlp_with_factor_base(&curve, &target, &factor_base, &options)
            .expect("index-calculus report");
    let solve_ns = solve_start.elapsed().as_nanos();
    let verified = report.log.as_ref() == Some(&BigUint::from(secret))
        && report
            .log
            .as_ref()
            .is_some_and(|value| curve.mul(curve.generator(), value) == target);
    let output = json!({
        "kind":"koblitz_unknown_scalar_algebraic_factor_base_e2e",
        "mode":"ic",
        "scope":"complete toy index-calculus pipeline over a factor base with no constructed point logs",
        "n":n,"a":a,"m":m,"subgroup_order":curve.subgroup_order.to_string(),
        "target":point_json(&target),"seed":seed,
        "factor_base_predicate":{
            "kind":factor_kind,
            "factor_spec":factor_spec,
            "divisor_indices":factor_indices,
            "factor_bitmask":factor,
            "linearised_exponents":factor_exponents,
            "enumerates_target_subgroup":false,
            "uses_discrete_log_labels":false,
            "factor_base_logs_constructed":false
        },
        "factor_base":{
            "ell":factor_base.ell,"points":factor_base.points.len(),
            "signed_frobenius_orbits_before_projection":factor_base.unknowns(),
            "projected_signed_frobenius_orbits":report.orbit_count,
            "m_cofactor_admissible":report.m_cofactor_admissible
        },
        "options":{"conflict_budget_per_target":conflict_budget,"max_trials":max_trials,"max_models":64,"parallel_threads":1},
        "report":{
            "relations":report.relations,"trials":report.trials,"relation_batches":report.relation_batches,
            "direct_relations_skipped":report.direct_relations_skipped,
            "m_cofactor_admissible":report.m_cofactor_admissible,
            "collapse_projected_orbits":report.collapse_projected_orbits,
            "linear_solve_attempts":report.linear_solve_attempts,"sat_calls":report.sat_calls,
            "sat_models":report.sat_models,"sat_refutations":report.sat_refutations,
            "sat_unknowns":report.sat_unknowns,"sat_invalid_models":report.sat_invalid_models,
            "sat_conflicts":report.sat_conflicts,"direct_relation":report.direct_relation,
            "verified_unknown_scalar_recovery":verified,
            "recovered_scalar":report.log.as_ref().map(ToString::to_string)
        },
        "timing_ns":{
            "curve_and_subgroup_construction":curve_ns,"target_construction":target_ns,
            "factor_base_predicate_and_materialisation":factor_base_ns,
            "projected_orbit_construction":report.projected_orbit_construction_ns,
            "cofactor_admission":report.cofactor_admission_ns,
            "relation_collection":report.relation_collection_ns,"linear_algebra":report.linear_algebra_ns,
            "driver_solve":solve_ns,"end_to_end":total.elapsed().as_nanos()
        },
        "interpretation":"A failed or resource-capped run is operationally inconclusive; success is accepted only after the recovered scalar reproduces the public target point"
    });
    println!("{}", serde_json::to_string_pretty(&output).unwrap());
    assert!(
        !report.direct_relation,
        "direct relation bypassed the matrix"
    );
    assert_eq!(report.sat_invalid_models, 0);
    assert!(verified, "unknown scalar was not recovered and verified");
}
