//! Independent targets for high-yield factor bases selected from the census.
//! cargo run --release --example koblitz_factor_base_validate -- <census.jsonl> 4 2000
//! Reports raw per-target results, including every censored SAT attempt.
use cryptanalysis_suite::binary_ecc::{BinaryPoint, F2mElement};
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::FieldStructure;
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::*;
use num_bigint::BigUint;
use num_traits::ToPrimitive;
use rand::{Rng, SeedableRng};
use serde_json::{json, Value};
use std::time::Instant;
fn main() {
    let args: Vec<_> = std::env::args().collect();
    let path = args.get(1).expect("census JSONL path");
    let count: usize = args.get(2).map(|s| s.parse().unwrap()).unwrap_or(4);
    let cap: u64 = args.get(3).map(|s| s.parse().unwrap()).unwrap_or(2000);
    let mut rows: Vec<Value> = std::fs::read_to_string(path)
        .unwrap()
        .lines()
        .map(|l| serde_json::from_str(l).unwrap())
        .filter(|r: &Value| {
            r["kind"] == "factor_base_yield"
                && r["m"] == 3
                && r["projected_points"].as_u64().unwrap() > 1
        })
        .collect();
    rows.sort_by(|a, b| {
        b["coverage_per_orbit"]
            .as_f64()
            .partial_cmp(&a["coverage_per_orbit"].as_f64())
            .unwrap()
    });
    rows.truncate(3);
    for row in rows {
        let n = row["n"].as_u64().unwrap() as u32;
        let a = row["a"].as_u64().unwrap() as u8;
        let kc = KoblitzCurve::new(a, n).unwrap();
        let id = &row["identity"];
        let start = Instant::now();
        let fb = if id["type"] == "divisor" {
            let indices: Vec<_> = id["indices"]
                .as_array()
                .unwrap()
                .iter()
                .map(|i| i.as_u64().unwrap() as usize)
                .collect();
            build_frobenius_factor_base_from_divisor(&kc, &indices).unwrap()
        } else {
            let basis: Vec<_> = id["seed_basis"]
                .as_array()
                .unwrap()
                .iter()
                .map(|i| F2mElement::from_biguint(&BigUint::from(i.as_u64().unwrap()), n))
                .collect();
            build_frobenius_union_factor_base(&kc, &basis).unwrap()
        };
        let base_ms = start.elapsed().as_secs_f64() * 1000.;
        let st = FieldStructure::new(n, &kc.curve.irreducible);
        let index = fb.index_map();
        let mut rng = rand::rngs::StdRng::seed_from_u64(0x484f4c444f5554);
        let r = kc.subgroup_order.to_u64().unwrap();
        for sample in 0..count {
            let k = rng.gen_range(1..r);
            let target = kc.mul(kc.generator(), &BigUint::from(k));
            let start = Instant::now();
            let reference = enumerate_decompose(&kc, &fb, &index, &target, 3);
            let search_ms = start.elapsed().as_secs_f64() * 1000.;
            let start = Instant::now();
            let (out, stats) = sat_decompose_with(
                &kc,
                &fb,
                &index,
                &st,
                &target,
                3,
                128,
                None,
                SatDecompositionOptions {
                    conflict_budget: cap,
                    restrict_to_factor_base: true,
                    ..Default::default()
                },
            );
            let sat_ms = start.elapsed().as_secs_f64() * 1000.;
            assert_eq!(stats.spurious, 0);
            if out.is_some() || stats.refuted {
                assert_eq!(out.is_some(), reference.is_some());
            }
            if let Some(ids) = &out {
                let sum = ids
                    .iter()
                    .fold(BinaryPoint::Infinity, |s, &i| kc.add(&s, &fb.points[i]));
                assert_eq!(sum, target);
            }
            println!(
                "{}",
                json!({"kind":"factor_base_sat_validation","n":n,"a":a,"identity":id,
                "sample":sample,"target_scalar":k,"points":fb.points.len(),"orbits":fb.orbits.len(),
                "reference_found":reference.is_some(),"sat_found":out.is_some(),"refuted":stats.refuted,
                "exhausted":stats.exhausted,"conflicts":stats.conflicts,"models":stats.models,
                "conflict_cap":cap,"base_ms":base_ms,"search_ms":search_ms,"sat_ms":sat_ms})
            );
        }
    }
}
