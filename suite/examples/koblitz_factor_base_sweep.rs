//! Divisor-factor-base census and bounded SAT-only group decomposition.
//! cargo run --release --example koblitz_factor_base_sweep -- 15 1 6 8 100000
//! Arguments: n, curve a, maximum base dimension, targets, conflicts/target.
//! JSONL includes construction, all successes/failures, and UNKNOWN counts.
use cryptanalysis_suite::binary_ecc::BinaryPoint;
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::FieldStructure;
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::*;
use num_bigint::BigUint;
use num_traits::ToPrimitive;
use rand::{Rng, SeedableRng};
use serde_json::json;
use std::collections::HashSet;
use std::time::Instant;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let n = args.get(1).map(|s| s.parse().unwrap()).unwrap_or(15u32);
    let a = args.get(2).map(|s| s.parse().unwrap()).unwrap_or(1u8);
    let max_dim = args.get(3).map(|s| s.parse().unwrap()).unwrap_or(6usize);
    let count = args.get(4).map(|s| s.parse().unwrap()).unwrap_or(8usize);
    let variant = args.get(6).map(String::as_str).unwrap_or("plain");
    let restrict = variant.contains("domain");
    let trace = variant.contains("trace");
    let cap = args
        .get(5)
        .map(|s| s.parse().unwrap())
        .unwrap_or(100_000u64);
    assert!(n % 2 == 1 && n <= MAX_N && max_dim <= 8 && count > 0);
    let start = Instant::now();
    let kc = KoblitzCurve::new(a, n).expect("usable curve");
    let curve_ms = start.elapsed().as_secs_f64() * 1000.;
    let st = FieldStructure::new(n, &kc.curve.irreducible);
    let factors = all_factors_of_x_n_minus_1(n);
    assert!(factors.len() < 20);
    let r = kc.subgroup_order.to_u64().unwrap();
    let mut rng = rand::rngs::StdRng::seed_from_u64(0x464143544f52);
    let targets: Vec<_> = (0..count)
        .map(|_| {
            let k = rng.gen_range(1..r);
            (k, kc.mul(kc.generator(), &BigUint::from(k)))
        })
        .collect();
    for mask in 1..(1usize << factors.len()) {
        let indices: Vec<usize> = (0..factors.len())
            .filter(|i| (mask >> i) & 1 == 1)
            .collect();
        let dim: usize = indices
            .iter()
            .map(|&i| (63 - factors[i].leading_zeros()) as usize)
            .sum();
        if dim < 3 || dim > max_dim || dim >= n as usize {
            continue;
        }
        let start = Instant::now();
        let fb = build_frobenius_factor_base_from_divisor(&kc, &indices).expect("valid divisor");
        let base_ms = start.elapsed().as_secs_f64() * 1000.;
        let index = fb.index_map();
        let projected: HashSet<_> = fb
            .points
            .iter()
            .map(|p| point_key(&kc.mul(p, &kc.cofactor)))
            .collect();
        for m in [2, 3] {
            let start = Instant::now();
            let admissible = fb.m_can_decompose(&kc, m);
            let admission_ms = start.elapsed().as_secs_f64() * 1000.;
            let mut found = 0;
            let mut refuted = 0;
            let mut unknown = 0;
            let mut disagreements = 0;
            let mut search_hits = 0;
            let mut records = Vec::new();
            for (k, target) in &targets {
                let start = Instant::now();
                let reference = enumerate_decompose(&kc, &fb, &index, target, m);
                let search_ms = start.elapsed().as_secs_f64() * 1000.;
                search_hits += usize::from(reference.is_some());
                if !admissible {
                    assert!(reference.is_none(), "cofactor gate must be necessary");
                    continue;
                }
                let start = Instant::now();
                let (out, stats) = sat_decompose_with(
                    &kc,
                    &fb,
                    &index,
                    &st,
                    target,
                    m,
                    128,
                    None,
                    SatDecompositionOptions {
                        conflict_budget: cap,
                        restrict_to_factor_base: restrict,
                        trace_constraint: trace,
                        ..Default::default()
                    },
                );
                let sat_ms = start.elapsed().as_secs_f64() * 1000.;
                assert_eq!(stats.spurious, 0);
                if let Some(ref ids) = out {
                    let sum = ids
                        .iter()
                        .fold(BinaryPoint::Infinity, |p, &i| kc.add(&p, &fb.points[i]));
                    assert_eq!(&sum, target, "SAT decomposition must verify in the group");
                    found += 1;
                } else if stats.refuted {
                    refuted += 1;
                } else {
                    unknown += 1;
                }
                if out.is_some() || stats.refuted {
                    disagreements += usize::from(out.is_some() != reference.is_some());
                }
                records.push(json!({"target_scalar":k,"search_found":reference.is_some(),
                    "sat_found":out.is_some(),"refuted":stats.refuted,"exhausted":stats.exhausted,
                    "conflicts":stats.conflicts,"models":stats.models,"search_ms":search_ms,"sat_ms":sat_ms}));
            }
            println!(
                "{}",
                json!({"kind":"factor_base_census","n":n,"a":a,"r":r,"cofactor":kc.cofactor.to_string(),
                "divisor_indices":indices,"divisor_polynomial":fb.f_j,"ell":dim,"m":m,
                "points":fb.points.len(),"orbits":fb.unknowns(),"projected_points":projected.len(),
                "cofactor_admissible":admissible,"curve_ms":curve_ms,"base_ms":base_ms,"admission_ms":admission_ms,
                "targets":count,"search_hits":search_hits,"sat_found":found,"sat_refuted":refuted,"sat_unknown":unknown,
                "disagreements":disagreements,"restrict_to_factor_base":restrict,"trace_constraint":trace,"conflict_cap":cap,"samples":records})
            );
            assert_eq!(disagreements, 0, "invalid census evidence");
        }
    }
}
