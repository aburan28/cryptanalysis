//! Paired SAT ablation: lexicographic summand ordering on/off.
//!
//! ```bash
//! cargo run --release --example koblitz_sat_symmetry_ablation -- 15 1 3 8 200000
//! ```
//!
//! Arguments: degree, curve a, summands, targets, conflict cap per target.
//! Every verdict is cross-checked against exhaustive search; a
//! disagreement aborts.  Prints one JSON line per target and arm, then a
//! summary of conflicts and wall time per arm.
use cryptanalysis_suite::binary_ecc::BinaryPoint;
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::FieldStructure;
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::*;
use num_bigint::BigUint;
use num_traits::ToPrimitive;
use rand::{Rng, SeedableRng};
use serde_json::json;
use std::time::Instant;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let n: u32 = args.get(1).map(|s| s.parse().unwrap()).unwrap_or(15);
    let a: u8 = args.get(2).map(|s| s.parse().unwrap()).unwrap_or(1);
    let m: usize = args.get(3).map(|s| s.parse().unwrap()).unwrap_or(3);
    let count: usize = args.get(4).map(|s| s.parse().unwrap()).unwrap_or(8);
    let cap: u64 = args.get(5).map(|s| s.parse().unwrap()).unwrap_or(200_000);
    let kc = KoblitzCurve::new(a, n).expect("usable curve");
    let fb = build_frobenius_factor_base(&kc, 0).expect("factor base");
    let st = FieldStructure::new(n, &kc.curve.irreducible);
    let index = fb.index_map();
    let r = kc.subgroup_order.to_u64().unwrap();
    let mut rng = rand::rngs::StdRng::seed_from_u64(0x53594d);
    let targets: Vec<(u64, BinaryPoint)> = (0..count)
        .map(|_| {
            let k = rng.gen_range(1..r);
            (k, kc.mul(kc.generator(), &BigUint::from(k)))
        })
        .collect();
    let mut totals = [(0u64, 0f64, 0usize, 0usize); 2];
    for (k, target) in &targets {
        let reference = enumerate_decompose(&kc, &fb, &index, target, m);
        for (arm, symmetry_breaking) in [false, true].into_iter().enumerate() {
            let start = Instant::now();
            let (out, stats) = sat_decompose_with(
                &kc,
                &fb,
                &index,
                &st,
                target,
                m,
                128,
                Some(2),
                SatDecompositionOptions {
                    conflict_budget: cap,
                    symmetry_breaking,
                    ..Default::default()
                },
            );
            let ms = start.elapsed().as_secs_f64() * 1000.0;
            assert_eq!(stats.spurious, 0);
            if out.is_some() || stats.refuted {
                assert_eq!(
                    out.is_some(),
                    reference.is_some(),
                    "SAT verdict disagrees with search"
                );
            }
            if let Some(ids) = &out {
                let sum = ids
                    .iter()
                    .fold(BinaryPoint::Infinity, |s, &i| kc.add(&s, &fb.points[i]));
                assert_eq!(&sum, target);
            }
            totals[arm].0 += stats.conflicts;
            totals[arm].1 += ms;
            totals[arm].2 += usize::from(out.is_some() || stats.refuted);
            totals[arm].3 += usize::from(stats.exhausted);
            println!(
                "{}",
                json!({"kind":"sat_symmetry_ablation","n":n,"a":a,"m":m,"target_scalar":k,
                    "symmetry_breaking":symmetry_breaking,"search_found":reference.is_some(),
                    "sat_found":out.is_some(),"refuted":stats.refuted,"exhausted":stats.exhausted,
                    "conflicts":stats.conflicts,"models":stats.models,"sat_ms":ms})
            );
        }
    }
    for (arm, label) in ["symmetry_breaking=false", "symmetry_breaking=true"]
        .into_iter()
        .enumerate()
    {
        println!(
            "{}",
            json!({"kind":"sat_symmetry_summary","n":n,"a":a,"m":m,"arm":label,"targets":count,
                "decided":totals[arm].2,"exhausted":totals[arm].3,
                "total_conflicts":totals[arm].0,"total_ms":totals[arm].1})
        );
    }
}
