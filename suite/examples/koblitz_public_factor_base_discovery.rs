//! Target-independent census of algebraic GGMP divisor factor bases.
//!
//! Usage:
//! `koblitz_public_factor_base_discovery <n> <a> <m> <dimension>`
//!
//! The census uses only the factorisation of `T^n-1`, rational points above
//! each linearised kernel, cofactor-class reachability, and equality of
//! cofactor-projected points up to signed Frobenius. It neither enumerates the
//! target subgroup nor constructs a target or any discrete-log label.

use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    all_factors_of_x_n_minus_1, build_frobenius_factor_base_from_divisor, point_key,
    projected_signed_orbit_count, KoblitzCurve,
};
use serde_json::json;
use std::collections::HashSet;
use std::time::Instant;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    assert_eq!(
        args.len(),
        5,
        "usage: koblitz_public_factor_base_discovery <n> <a> <m> <dimension>"
    );
    let n: u32 = args[1].parse().expect("n");
    let a: u8 = args[2].parse().expect("a");
    let m: usize = args[3].parse().expect("m");
    let wanted_dimension: usize = args[4].parse().expect("dimension");
    assert!(m >= 2 && wanted_dimension > 0 && wanted_dimension < n as usize);

    let total_start = Instant::now();
    let curve_start = Instant::now();
    let curve = KoblitzCurve::new(a, n).expect("usable curve");
    let curve_ns = curve_start.elapsed().as_nanos();
    let factors = all_factors_of_x_n_minus_1(n);
    assert!(!factors.is_empty() && factors.len() < 20);
    let factor_degrees: Vec<_> = factors
        .iter()
        .map(|factor| 63 - factor.leading_zeros())
        .collect();

    let mut candidates = Vec::new();
    for mask in 1usize..(1usize << factors.len()) {
        let indices: Vec<_> = (0..factors.len())
            .filter(|index| (mask >> index) & 1 == 1)
            .collect();
        let dimension: usize = indices
            .iter()
            .map(|index| factor_degrees[*index] as usize)
            .sum();
        if dimension != wanted_dimension {
            continue;
        }

        let build_start = Instant::now();
        let factor_base = build_frobenius_factor_base_from_divisor(&curve, &indices)
            .expect("factor divisor must define its advertised kernel");
        let build_ns = build_start.elapsed().as_nanos();
        let admission_start = Instant::now();
        let m_cofactor_admissible = factor_base.m_can_decompose(&curve, m);
        let admission_ns = admission_start.elapsed().as_nanos();
        let projection_start = Instant::now();
        let projected_signed_orbits = projected_signed_orbit_count(&curve, &factor_base);
        let projected_points = factor_base
            .points
            .iter()
            .map(|point| point_key(&curve.mul(point, &curve.cofactor)))
            .collect::<HashSet<_>>()
            .len();
        let projection_ns = projection_start.elapsed().as_nanos();
        candidates.push(json!({
            "divisor_indices":indices,
            "divisor_polynomial":factor_base.f_j,
            "linearised_exponents":factor_base.linearised_exponents.clone(),
            "dimension":factor_base.ell,
            "abscissae":factor_base.subspace.len(),
            "rational_points":factor_base.points.len(),
            "signed_frobenius_orbits_before_projection":factor_base.unknowns(),
            "projected_points":projected_points,
            "projected_signed_frobenius_orbits":projected_signed_orbits,
            "m_cofactor_admissible":m_cofactor_admissible,
            "timing_ns":{
                "factor_base_construction":build_ns,
                "cofactor_admission":admission_ns,
                "projection_census":projection_ns
            }
        }));
    }
    assert!(
        !candidates.is_empty(),
        "no divisor has the requested dimension"
    );

    // Frozen public rule: among cofactor-admissible candidates, maximize the
    // number of rational factor-base points; then minimize the number of
    // projected signed-Frobenius columns; then choose lexicographically lower
    // divisor indices. No target or relation is available to this process.
    let mut admitted: Vec<_> = candidates
        .iter()
        .filter(|candidate| candidate["m_cofactor_admissible"] == true)
        .collect();
    admitted.sort_by(|left, right| {
        right["rational_points"]
            .as_u64()
            .cmp(&left["rational_points"].as_u64())
            .then_with(|| {
                left["projected_signed_frobenius_orbits"]
                    .as_u64()
                    .cmp(&right["projected_signed_frobenius_orbits"].as_u64())
            })
            .then_with(|| {
                left["divisor_indices"]
                    .to_string()
                    .cmp(&right["divisor_indices"].to_string())
            })
    });
    let selected = admitted
        .first()
        .expect("no requested divisor passes the cofactor-class gate");

    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "schema":"koblitz_public_factor_base_discovery.v1",
            "n":n,"a":a,"m":m,
            "group_order":curve.group_order.to_string(),
            "subgroup_order":curve.subgroup_order.to_string(),
            "cofactor":curve.cofactor.to_string(),
            "requested_dimension":wanted_dimension,
            "sizing_gate":{"m_times_dimension":m*wanted_dimension,"n":n,"passes":m*wanted_dimension >= n as usize},
            "factor_degrees":factor_degrees,
            "candidates":candidates,
            "selected":selected,
            "selection_rule":"cofactor admissible; maximize rational points; minimize projected signed-Frobenius columns; lexicographically lower divisor indices",
            "forbidden_inputs":{
                "target_constructed":false,
                "target_subgroup_enumerated":false,
                "discrete_log_labels_constructed":false,
                "relation_yield_used":false,
                "solver_timing_used":false
            },
            "timing_ns":{"curve_and_subgroup_construction":curve_ns,"end_to_end":total_start.elapsed().as_nanos()}
        }))
        .expect("JSON")
    );
}
