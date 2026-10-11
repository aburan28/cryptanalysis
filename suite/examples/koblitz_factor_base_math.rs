//! Mathematical holdout: sumset coverage, multiplicity, additive energy,
//! and rank after cofactor/Frobenius/negation identifications. No logarithm recovery.
//! cargo run --release --example koblitz_factor_base_math -- <census.jsonl> 4096
use cryptanalysis_suite::binary_ecc::curve::point_neg;
use cryptanalysis_suite::binary_ecc::{BinaryPoint, F2mElement};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::*;
use num_bigint::BigUint;
use num_traits::ToPrimitive;
use rand::{Rng, SeedableRng};
use serde_json::{json, Value};
use std::collections::{HashMap, HashSet};

fn modpow(mut a: u64, mut e: u64, r: u64) -> u64 {
    let mut z = 1;
    while e > 0 {
        if e & 1 == 1 {
            z = z * a % r;
        }
        a = a * a % r;
        e >>= 1;
    }
    z
}
fn add_row(mut row: Vec<u64>, echelon: &mut [Option<Vec<u64>>], r: u64) -> bool {
    for j in 0..row.len() {
        if row[j] == 0 {
            continue;
        }
        if let Some(p) = &echelon[j] {
            let c = row[j];
            for k in j..row.len() {
                row[k] = (row[k] + r - c * p[k] % r) % r;
            }
        } else {
            let inv = modpow(row[j], r - 2, r);
            for k in j..row.len() {
                row[k] = row[k] * inv % r;
            }
            echelon[j] = Some(row);
            return true;
        }
    }
    false
}
// Retain complete projected signed orbits and their torsion fibers.
// The source is already a nonlinear, full-coordinate saturated base.
fn drop_projected_orbit(
    kc: &KoblitzCurve,
    mut fb: FrobeniusFactorBase,
    drop: usize,
) -> FrobeniusFactorBase {
    let canonical = |p: &BinaryPoint| {
        let mut q = kc.mul(p, &kc.cofactor);
        if q == BinaryPoint::Infinity {
            return None;
        }
        let mut key = point_key(&q);
        for _ in 0..kc.n {
            key = key.min(point_key(&q)).min(point_key(&point_neg(&q)));
            q = kc.frobenius(&q);
        }
        Some(key)
    };
    let keys: Vec<_> = fb.points.iter().map(canonical).collect();
    let classes: std::collections::BTreeSet<_> = keys.iter().flatten().cloned().collect();
    let remove = classes.iter().nth(drop).expect("projected orbit index");
    let keep: Vec<_> = keys.iter().map(|k| k.as_ref() != Some(remove)).collect();
    let mut remap = vec![usize::MAX; fb.points.len()];
    let mut points = Vec::new();
    for (i, p) in fb.points.iter().enumerate() {
        if keep[i] {
            remap[i] = points.len();
            points.push(p.clone());
        }
    }
    let mut orbits = Vec::new();
    let mut orbit_of = vec![(0, 0); points.len()];
    for orbit in &fb.orbits {
        if keep[orbit[0]] {
            assert!(orbit.iter().all(|&i| keep[i]));
            let indices: Vec<_> = orbit.iter().map(|&i| remap[i]).collect();
            for (power, &i) in indices.iter().enumerate() {
                orbit_of[i] = (orbits.len(), power as u32);
            }
            orbits.push(indices);
        } else {
            assert!(orbit.iter().all(|&i| !keep[i]));
        }
    }
    let mut signed_orbits = Vec::new();
    let mut signed_orbit_of = vec![(0, 0, false); points.len()];
    for orbit in &fb.signed_orbits {
        if keep[orbit[0]] {
            assert!(orbit.iter().all(|&i| keep[i]));
            let signed_orbit = signed_orbits.len();
            let indices: Vec<_> = orbit.iter().map(|&i| remap[i]).collect();
            for (&old, &new) in orbit.iter().zip(&indices) {
                let (_, power, negated) = fb.signed_orbit_of[old];
                signed_orbit_of[new] = (signed_orbit, power, negated);
            }
            signed_orbits.push(indices);
        } else {
            assert!(orbit.iter().all(|&i| !keep[i]));
        }
    }
    let xs: HashSet<_> = points
        .iter()
        .filter_map(|p| match p {
            BinaryPoint::Affine { x, .. } => Some(x.to_biguint()),
            _ => None,
        })
        .collect();
    fb.subspace.retain(|x| xs.contains(&x.to_biguint()));
    fb.points = points;
    fb.orbits = orbits;
    fb.orbit_of = orbit_of;
    fb.signed_orbits = signed_orbits;
    fb.signed_orbit_of = signed_orbit_of;
    fb
}

// Representatives of F_r^* / <lambda,-1>. These are public point labels;
// no logarithms are computed. Checking the partition is part of the certificate.
fn signed_target_orbits(r: u64, lambda: u64, n: u32) -> (Vec<u64>, usize) {
    assert!(r <= 4_000_000, "explicit target-partition memory guard");
    assert_eq!(modpow(lambda, n as u64, r), 1);
    let mut seen = vec![false; r as usize];
    seen[0] = true;
    let mut representatives = Vec::new();
    let mut orbit_size = None;
    for k in 1..r {
        if seen[k as usize] {
            continue;
        }
        let mut members = std::collections::BTreeSet::new();
        let mut x = k;
        for _ in 0..n {
            members.insert(x);
            members.insert(r - x);
            x = x * lambda % r;
        }
        assert_eq!(x, k);
        if let Some(size) = orbit_size {
            assert_eq!(size, members.len());
        } else {
            orbit_size = Some(members.len());
        }
        for x in members {
            assert!(!seen[x as usize], "target orbits overlap");
            seen[x as usize] = true;
        }
        representatives.push(k);
    }
    let size = orbit_size.unwrap();
    assert!(seen.iter().all(|&v| v));
    assert_eq!(representatives.len() * size, (r - 1) as usize);
    (representatives, size)
}

#[cfg(test)]
mod orbit_tests {
    use super::*;
    #[test]
    fn target_partition_handles_full_and_short_frobenius_orbits() {
        assert_eq!(signed_target_orbits(7, 2, 3), (vec![1], 6));
        assert_eq!(signed_target_orbits(7, 1, 3), (vec![1, 2, 3], 2));
        let (reps, size) = signed_target_orbits(31, 2, 5);
        assert_eq!(size, 10);
        assert_eq!(reps.len(), 3);
    }
}

fn main() {
    let args: Vec<_> = std::env::args().collect();
    let path = args.get(1).expect("census path");
    let count: usize = args.get(2).map(|s| s.parse().unwrap()).unwrap_or(4096);
    assert!(count > 0);
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
    let exact_orbits = args.iter().any(|s| s == "--exact-orbits");
    let parent_only = args.iter().any(|s| s == "--parent-only");
    let drop_orbit: Option<usize> = args
        .get(4)
        .filter(|s| !s.starts_with("--"))
        .map(|s| s.parse().unwrap());
    rows.truncate(if drop_orbit.is_some() || parent_only {
        1
    } else {
        5
    });
    for row in rows {
        let n = row["n"].as_u64().unwrap() as u32;
        let a = row["a"].as_u64().unwrap() as u8;
        let kc = KoblitzCurve::new(a, n).unwrap();
        let saturated = args.get(3).map(|s| s == "two-torsion").unwrap_or(false);
        let id = &row["identity"];
        let fb = if id["type"] == "divisor" {
            let ids: Vec<_> = id["indices"]
                .as_array()
                .unwrap()
                .iter()
                .map(|i| i.as_u64().unwrap() as usize)
                .collect();
            build_frobenius_factor_base_from_divisor(&kc, &ids).unwrap()
        } else {
            let b: Vec<_> = id["seed_basis"]
                .as_array()
                .unwrap()
                .iter()
                .map(|i| F2mElement::from_biguint(&BigUint::from(i.as_u64().unwrap()), n))
                .collect();
            build_frobenius_union_factor_base(&kc, &b).unwrap()
        };
        let fb = if saturated {
            saturate_factor_base_two_torsion(&kc, &fb).unwrap()
        } else {
            fb
        };
        let fb = if let Some(drop) = drop_orbit {
            assert!(saturated);
            drop_projected_orbit(&kc, fb, drop)
        } else {
            fb
        };
        if exact_orbits {
            let keys: HashSet<_> = fb.points.iter().map(point_key).collect();
            for p in &fb.points {
                assert!(keys.contains(&point_key(&kc.frobenius(p))));
                assert!(keys.contains(&point_key(&point_neg(p))));
            }
        }
        let r = kc.subgroup_order.to_u64().unwrap();
        let lambda = kc.lambda.to_u64().unwrap();
        assert!(r < (1u64 << 31));
        // Identify projected points under +/- Frobenius without computing
        // any discrete logarithm: coefficients are known powers of lambda.
        let mut orbit_map = HashMap::new();
        let mut columns = 0;
        for p in &fb.points {
            let p = kc.mul(p, &kc.cofactor);
            if p == BinaryPoint::Infinity || orbit_map.contains_key(&point_key(&p)) {
                continue;
            }
            let mut q = p;
            let mut c = 1;
            for _ in 0..n {
                for (v, coef) in [(q.clone(), c), (point_neg(&q), (r - c) % r)] {
                    let key = point_key(&v);
                    if let Some(&(old_col, old_coef)) = orbit_map.get(&key) {
                        assert_eq!((old_col, old_coef), (columns, coef));
                    } else {
                        orbit_map.insert(key, (columns, coef));
                    }
                }
                q = kc.frobenius(&q);
                c = c * lambda % r;
            }
            columns += 1;
        }
        let labels: Vec<_> = fb
            .points
            .iter()
            .map(|p| orbit_map.get(&point_key(&kc.mul(p, &kc.cofactor))).copied())
            .collect();
        let mut classes = HashMap::new();
        for c in fb.cofactor_classes(&kc) {
            *classes.entry(point_key(&c)).or_insert(0usize) += 1;
        }
        let mut class_sizes: Vec<_> = classes.values().copied().collect();
        class_sizes.sort_unstable();
        let mut pairs: HashMap<_, Vec<(usize, usize)>> = HashMap::new();
        for i in 0..fb.points.len() {
            for j in i..fb.points.len() {
                pairs
                    .entry(point_key(&kc.add(&fb.points[i], &fb.points[j])))
                    .or_default()
                    .push((i, j));
            }
        }
        let energy: u64 = pairs
            .values()
            .map(|pairs| {
                let c: u64 = pairs.iter().map(|(i, j)| if i == j { 1 } else { 2 }).sum();
                c * c
            })
            .sum();
        // Burnside's lemma for unordered triples in the zero cofactor class:
        // (identity-fixed + 3*transposition-fixed + 2*3-cycle-fixed)/6.
        let mut class_points = HashMap::new();
        for c in fb.cofactor_classes(&kc) {
            class_points.entry(point_key(&c)).or_insert(c);
        }
        let mut identity_fixed = 0u64;
        let mut transposition_fixed = 0u64;
        let mut cycle_fixed = 0u64;
        for (key, p) in &class_points {
            let np = classes[key] as u64;
            let twice = kc.add(p, p);
            transposition_fixed += np
                * classes
                    .get(&point_key(&point_neg(&twice)))
                    .copied()
                    .unwrap_or(0) as u64;
            if kc.add(&twice, p) == BinaryPoint::Infinity {
                cycle_fixed += np;
            }
            for (other_key, q) in &class_points {
                let inverse = point_neg(&kc.add(p, q));
                identity_fixed += np
                    * classes[other_key] as u64
                    * classes.get(&point_key(&inverse)).copied().unwrap_or(0) as u64;
            }
        }
        let admitted_multisets = (identity_fixed + 3 * transposition_fixed + 2 * cycle_fixed) / 6;
        assert_eq!(
            (identity_fixed + 3 * transposition_fixed + 2 * cycle_fixed) % 6,
            0
        );
        let zero_multisets: usize = fb
            .points
            .iter()
            .enumerate()
            .map(|(z, p)| {
                pairs
                    .get(&point_key(&point_neg(p)))
                    .map(|list| list.iter().filter(|(_, j)| *j <= z).count())
                    .unwrap_or(0)
            })
            .sum();
        let exact_mean = (admitted_multisets - zero_multisets as u64) as f64 / (r - 1) as f64;
        let mut training: HashSet<u64> = row["target_scalars"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| v.as_u64().unwrap())
            .collect();
        if drop_orbit.is_some() && !exact_orbits {
            let prior_path = std::path::Path::new(path)
                .parent()
                .unwrap()
                .join(format!("math-holdout-n{n}.jsonl"));
            let prior = std::fs::read_to_string(prior_path).expect("exclude prior holdout targets");
            for line in prior.lines() {
                let prior: Value = serde_json::from_str(line).unwrap();
                training.extend(
                    prior["target_scalars"]
                        .as_array()
                        .unwrap()
                        .iter()
                        .map(|k| k.as_u64().unwrap()),
                );
            }
        }
        let exhaustive = r <= 1024;
        let mut rng = rand::rngs::StdRng::seed_from_u64(if drop_orbit.is_some() {
            0x535542534554
        } else {
            0x484f4c444f5554
        });
        let mut target_orbit_size = 1;
        let ks: Vec<u64> = if exact_orbits {
            let (reps, size) = signed_target_orbits(r, lambda, n);
            target_orbit_size = size;
            reps
        } else if exhaustive {
            (1..r).collect()
        } else {
            let mut chosen = HashSet::new();
            let mut out = Vec::new();
            assert!(count < r as usize - training.len() - 1);
            while out.len() < count {
                let k = rng.gen_range(1..r);
                if !training.contains(&k) && chosen.insert(k) {
                    out.push(k);
                }
            }
            out
        };
        let mut echelon = vec![None; columns];
        let mut rank = 0;
        let mut full_rank_at = None;
        let mut hits = 0;
        let mut sum = 0u64;
        let mut sum2 = 0u64;
        let mut max = 0;
        let mut histogram = std::collections::BTreeMap::new();
        let mut multiplicities = Vec::new();
        for (trial, k) in ks.iter().enumerate() {
            let target = kc.mul(kc.generator(), &BigUint::from(*k));
            let mut multiplicity = 0u64;
            let mut witness = None;
            for (z, p) in fb.points.iter().enumerate() {
                let rest = kc.add(&target, &point_neg(p));
                if let Some(list) = pairs.get(&point_key(&rest)) {
                    for &(i, j) in list {
                        if j <= z {
                            multiplicity += 1;
                            if witness.is_none() {
                                witness = Some([i, j, z]);
                            }
                        }
                    }
                }
            }
            multiplicities.push(multiplicity);
            *histogram.entry(multiplicity).or_insert(0usize) += 1;
            sum += multiplicity;
            sum2 += multiplicity * multiplicity;
            max = max.max(multiplicity);
            if let Some(ids) = witness {
                hits += 1;
                assert_eq!(
                    ids.iter()
                        .fold(BinaryPoint::Infinity, |s, &i| kc.add(&s, &fb.points[i])),
                    target
                );
                let mut vector = vec![0; columns];
                for i in ids {
                    if let Some((j, c)) = labels[i] {
                        vector[j] = (vector[j] + c) % r;
                    }
                }
                if add_row(vector, &mut echelon, r) {
                    rank += 1;
                }
                if rank == columns && full_rank_at.is_none() {
                    full_rank_at = Some(trial + 1);
                }
            }
        }
        if exact_orbits || exhaustive {
            assert_eq!(
                sum * target_orbit_size as u64 + zero_multisets as u64,
                admitted_multisets,
                "orbit-weighted count must equal independent Burnside count"
            );
        }
        let len = ks.len() as f64;
        let mean = sum as f64 / len;
        println!(
            "{}",
            json!({"kind":"factor_base_mathematics","identity":id,"two_torsion_saturated":saturated,"dropped_projected_orbit":drop_orbit,"n":n,"a":a,"r":r,
            "cofactor":kc.cofactor.to_string(),"field_modulus_low_terms":kc.curve.irreducible.low_terms,
            "points":fb.points.len(),"frobenius_orbits":fb.orbits.len(),"projected_signed_orbits":columns,
            "cofactor_class_sizes":class_sizes,"pair_sumset_size":pairs.len(),"additive_energy":energy,
            "cofactor_admissible_unordered_triples":admitted_multisets,"zero_sum_unordered_triples":zero_multisets,
            "exact_mean_representations_nonzero_subgroup":exact_mean,
            "targets":ks.len(),"target_scalars":ks,"exhaustive_nonzero_subgroup":exhaustive,
            "training_targets_excluded":!exhaustive && !exact_orbits,
            "exhaustive_via_symmetry":exact_orbits,"target_orbit_size":target_orbit_size,
            "represented_nonzero_targets":ks.len()*target_orbit_size,
            "covered_nonzero_targets":hits*target_orbit_size,
            "representative_multiplicities":multiplicities,"hits":hits,"coverage":hits as f64/len,
            "coverage_per_signed_orbit":hits as f64/len/columns as f64,
            "unordered_representation_mean":mean,"unordered_representation_variance":sum2 as f64/len-mean*mean,
            "unordered_representation_max":max,"representation_histogram":histogram,
            "coefficient_matrix_rank":rank,"full_rank_at_target":full_rank_at,
            "scope":"finite sumsets and coefficient rank only; no logarithms recovered"})
        );
    }
}
