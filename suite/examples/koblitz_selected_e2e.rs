//! Paired end-to-end index-calculus benchmark on the selected n=19 base.
//!
//! ```text
//! cargo run --release --example koblitz_selected_e2e -- optimized 1 4242 10000 8
//! cargo run --release --example koblitz_selected_e2e -- signed 1 4242 2000000 1
//! cargo run --release --example koblitz_selected_e2e -- frobenius 1 4242 2000000 1
//! ```
//!
//! Each process includes curve setup, factor-base materialisation,
//! SAT relation collection, modular linear algebra, and verified recovery
//! of the planted unknown scalar. JSON is emitted only after verification.

use cryptanalysis_suite::binary_ecc::F2mElement;
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_explicit_frobenius_orbit_factor_base, koblitz_index_calculus_dlp_with_factor_base,
    DecompositionStrategy, KoblitzCurve, KoblitzIcOptions, SatDecompositionOptions,
};
use cryptanalysis_suite::cryptanalysis::semaev_sat::XorEncoding;
use num_bigint::BigUint;
use serde_json::json;
use std::time::Instant;

fn main() {
    let arguments: Vec<_> = std::env::args().collect();
    let arm = arguments.get(1).map(String::as_str).unwrap_or("optimized");
    let (collapse_negation, stop_on_verified_rank) = match arm {
        "optimized" => (true, true),
        "signed" => (true, false),
        "frobenius" => (false, false),
        _ => panic!("arm must be optimized, signed, or frobenius"),
    };
    let run_seed: u64 = arguments
        .get(2)
        .map(|value| value.parse().expect("integer run seed"))
        .unwrap_or(1);
    let secret: u64 = arguments
        .get(3)
        .map(|value| value.parse().expect("integer secret"))
        .unwrap_or(4242);
    let conflict_budget: u64 = arguments
        .get(4)
        .map(|value| value.parse().expect("integer conflict budget"))
        .unwrap_or(2_000_000);
    let relation_batch_size: usize = arguments
        .get(5)
        .map(|value| value.parse().expect("integer relation batch size"))
        .unwrap_or(1);

    let end_to_end_start = Instant::now();
    let kc = KoblitzCurve::new(1, 19).expect("degree-19 Koblitz curve");
    assert!(secret > 0 && BigUint::from(secret) < kc.subgroup_order);
    let factor_base_start = Instant::now();
    let representatives: Vec<_> = [16795u64, 1315, 8461, 6685]
        .into_iter()
        .map(|value| F2mElement::from_biguint(&BigUint::from(value), kc.n))
        .collect();
    let factor_base = build_explicit_frobenius_orbit_factor_base(&kc, &representatives)
        .expect("selected factor base");
    let factor_base_ns = factor_base_start.elapsed().as_nanos();
    assert_eq!(factor_base.points.len(), 152);
    assert_eq!(factor_base.orbits.len(), 8);
    assert_eq!(factor_base.unknowns(), 4);

    let target = kc.mul(kc.generator(), &BigUint::from(secret));
    let sampler_seed = 0xe2e0_0000_0000_0000u64 ^ run_seed;
    let options = KoblitzIcOptions {
        m: 3,
        descent_m: None,
        extra_relations: 2,
        max_trials: 64,
        seed: sampler_seed,
        strategy: DecompositionStrategy::Sat,
        max_models: 1024,
        sat_macaulay_degree: None,
        sat_options: SatDecompositionOptions {
            encoding: XorEncoding::Native,
            branch_on_summands: true,
            restrict_to_factor_base: true,
            trace_constraint: true,
            conflict_budget,
            symmetry_breaking: false,
        },
        collapse_negation,
        stop_on_verified_rank,
        relation_batch_size,
        ..KoblitzIcOptions::default()
    };
    let driver_start = Instant::now();
    let report = koblitz_index_calculus_dlp_with_factor_base(&kc, &target, &factor_base, &options)
        .expect("index-calculus report");
    let driver_ns = driver_start.elapsed().as_nanos();
    let end_to_end_ns = end_to_end_start.elapsed().as_nanos();
    let verified = report.log.as_ref() == Some(&BigUint::from(secret))
        && report
            .log
            .as_ref()
            .is_some_and(|recovered| kc.mul(kc.generator(), recovered) == target);
    let output = json!({
        "kind":"koblitz_selected_factor_base_e2e",
        "arm":arm,
        "collapse_negation":collapse_negation,
        "stop_on_verified_rank":stop_on_verified_rank,
        "n":kc.n,
        "a":kc.a,
        "subgroup_order":kc.subgroup_order.to_string(),
        "secret":secret,
        "sampler_seed":sampler_seed,
        "factor_base_points":factor_base.points.len(),
        "frobenius_orbits":factor_base.orbits.len(),
        "signed_frobenius_orbits":factor_base.unknowns(),
        "relation_unknowns":report.orbit_count,
        "relations":report.relations,
        "trials":report.trials,
        "sat_calls":report.sat_calls,
        "sat_models":report.sat_models,
        "sat_conflicts":report.sat_conflicts,
        "per_target_conflict_budget":conflict_budget,
        "relation_batch_size":report.relation_batch_size,
        "relation_batches":report.relation_batches,
        "rayon_threads":rayon::current_num_threads(),
        "sat_refutations":report.sat_refutations,
        "sat_unknowns":report.sat_unknowns,
        "sat_invalid_models":report.sat_invalid_models,
        "direct_relation":report.direct_relation,
        "factor_base_ns":factor_base_ns,
        "relation_collection_ns":report.relation_collection_ns,
        "linear_algebra_ns":report.linear_algebra_ns,
        "linear_solve_attempts":report.linear_solve_attempts,
        "driver_ns":driver_ns,
        "end_to_end_ns":end_to_end_ns,
        "verified_unknown_scalar_recovery":verified,
        "scope":"complete toy n=19 index-calculus run; arms expose signed relation compression and verified rank-aware stopping"
    });
    println!("{output}");
    assert!(verified, "end-to-end scalar recovery failed: {output}");
    assert!(
        !report.direct_relation,
        "degenerate direct relation invalidates the run"
    );
    assert_eq!(report.sat_invalid_models, 0);
}
