//! Factor-base yield census: divisor subspaces vs unions of Frobenius translates.
//! Uses a charged pair table as an independent coverage oracle, not a SAT speed claim.
//! cargo run --release --example koblitz_factor_base_yield -- 19 1 128
use cryptanalysis_suite::binary_ecc::curve::point_neg;
use cryptanalysis_suite::binary_ecc::{BinaryPoint, F2mElement};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::*;
use num_bigint::BigUint;
use num_traits::ToPrimitive;
use rand::{Rng, SeedableRng};
use serde_json::{json, Value};
use std::collections::{HashMap, HashSet};
use std::time::Instant;

fn census(
    kc: &KoblitzCurve,
    fb: FrobeniusFactorBase,
    identity: Value,
    build_ms: f64,
    targets: &[(u64, BinaryPoint)],
    exhaustive: bool,
) {
    if fb.points.len() > 768 {
        println!(
            "{}",
            json!({"identity":identity,"status":"point_cap","points":fb.points.len(),"cap":768,"build_ms":build_ms})
        );
        return;
    }
    let projected: HashSet<_> = fb
        .points
        .iter()
        .map(|p| point_key(&kc.mul(p, &kc.cofactor)))
        .collect();
    let start = Instant::now();
    let mut pairs = HashMap::new();
    for i in 0..fb.points.len() {
        for j in i..fb.points.len() {
            pairs
                .entry(point_key(&kc.add(&fb.points[i], &fb.points[j])))
                .or_insert((i, j));
        }
    }
    let pair_ms = start.elapsed().as_secs_f64() * 1000.;
    for m in [2, 3] {
        let start = Instant::now();
        let mut hits = Vec::new();
        for (k, target) in targets {
            let witness = if m == 2 {
                pairs.get(&point_key(target)).map(|&(i, j)| vec![i, j])
            } else {
                fb.points.iter().enumerate().find_map(|(z, p)| {
                    let rest = kc.add(target, &point_neg(p));
                    pairs.get(&point_key(&rest)).map(|&(i, j)| vec![i, j, z])
                })
            };
            if let Some(ids) = witness {
                let sum = ids
                    .iter()
                    .fold(BinaryPoint::Infinity, |s, &i| kc.add(&s, &fb.points[i]));
                assert_eq!(sum, *target);
                hits.push(*k);
            }
        }
        let query_ms = start.elapsed().as_secs_f64() * 1000.;
        println!(
            "{}",
            json!({"kind":"factor_base_yield","identity":identity,
            "n":kc.n,"a":kc.a,"r":kc.subgroup_order.to_string(),"cofactor":kc.cofactor.to_string(),
            "ambient_dimension":fb.ell,"abscissae":fb.subspace.len(),"points":fb.points.len(),
            "orbits":fb.orbits.len(),"projected_points":projected.len(),"m":m,
            "targets":targets.len(),"exhaustive_nonzero_subgroup":exhaustive,
            "target_scalars":targets.iter().map(|(k,_)|*k).collect::<Vec<_>>(),"hit_scalars":hits,
            "coverage":hits.len() as f64 / targets.len() as f64,
            "coverage_per_orbit":hits.len() as f64 / targets.len() as f64 / fb.orbits.len().max(1) as f64,
            "build_ms":build_ms,"pair_table_ms":pair_ms,"query_ms":query_ms,
            "pair_additions":fb.points.len()*(fb.points.len()+1)/2,"pair_table_entries":pairs.len(),
            "sat_variables_before_aux":m*fb.ell as usize+(m-2)*kc.n as usize})
        );
    }
}

fn main() {
    let args: Vec<_> = std::env::args().collect();
    let n: u32 = args.get(1).map(|s| s.parse().unwrap()).unwrap_or(19);
    let a: u8 = args.get(2).map(|s| s.parse().unwrap()).unwrap_or(1);
    let count: usize = args.get(3).map(|s| s.parse().unwrap()).unwrap_or(128);
    assert!(n % 2 == 1 && n <= MAX_N && count > 0);
    let kc = KoblitzCurve::new(a, n).expect("usable curve");
    let r = kc.subgroup_order.to_u64().unwrap();
    let exhaustive = r <= 1024;
    let mut rng = rand::rngs::StdRng::seed_from_u64(0x5949454c44);
    let ks: Vec<_> = if exhaustive {
        (1..r).collect()
    } else {
        (0..count).map(|_| rng.gen_range(1..r)).collect()
    };
    let targets: Vec<_> = ks
        .into_iter()
        .map(|k| (k, kc.mul(kc.generator(), &BigUint::from(k))))
        .collect();
    let factors = all_factors_of_x_n_minus_1(n);
    if factors.len() < 20 {
        for mask in 1..(1usize << factors.len()) {
            let indices: Vec<_> = (0..factors.len())
                .filter(|i| (mask >> i) & 1 == 1)
                .collect();
            let dim: u32 = indices
                .iter()
                .map(|&i| 63 - factors[i].leading_zeros())
                .sum();
            if !(3..=8).contains(&dim) || dim >= n {
                continue;
            }
            let start = Instant::now();
            let fb = build_frobenius_factor_base_from_divisor(&kc, &indices).unwrap();
            let ms = start.elapsed().as_secs_f64() * 1000.;
            census(
                &kc,
                fb,
                json!({"type":"divisor","indices":indices}),
                ms,
                &targets,
                exhaustive,
            );
        }
    }
    for ell in 2..=5usize {
        for seed in 0..3 {
            let basis: Vec<_> = loop {
                let b: Vec<_> = (0..ell)
                    .map(|i| {
                        let x = if seed == 0 {
                            1u64 << i
                        } else {
                            rng.gen_range(1..(1u64 << n))
                        };
                        F2mElement::from_biguint(&BigUint::from(x), n)
                    })
                    .collect();
                let unique: HashSet<_> = span_f2(&b, n).iter().map(|x| x.to_biguint()).collect();
                if unique.len() == 1usize << ell {
                    break b;
                }
            };
            let start = Instant::now();
            let fb = build_frobenius_union_factor_base(&kc, &basis).unwrap();
            let ms = start.elapsed().as_secs_f64() * 1000.;
            let bits: Vec<_> = basis
                .iter()
                .map(|x| x.to_biguint().to_u64().unwrap())
                .collect();
            census(
                &kc,
                fb,
                json!({"type":"frobenius_union","seed_dimension":ell,
                "seed_index":seed,"seed_basis":bits}),
                ms,
                &targets,
                exhaustive,
            );
        }
    }
}
