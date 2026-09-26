//! Trace-aligned affine bases in u=x+1/x, the dual-Frobenius coordinate.
//! Counts finite sumsets only. No unknown scalar recovery.
//! cargo run --release --example koblitz_affine_quotient_base -- 19
use cryptanalysis_suite::binary_ecc::curve::point_neg;
use cryptanalysis_suite::binary_ecc::{BinaryPoint, F2mElement};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::*;
use num_bigint::BigUint;
use num_traits::ToPrimitive;
use rand::{Rng, SeedableRng};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};

fn trace(x: &F2mElement, kc: &KoblitzCurve) -> bool {
    let mut t = F2mElement::zero(kc.n);
    let mut q = x.clone();
    for _ in 0..kc.n {
        t = t.add(&q);
        q = q.square(&kc.curve.irreducible);
    }
    assert!(t.is_zero() || t == F2mElement::one(kc.n));
    !t.is_zero()
}
fn trace_zero(x: F2mElement, kc: &KoblitzCurve) -> F2mElement {
    if trace(&x, kc) {
        x.add(&F2mElement::one(kc.n))
    } else {
        x
    }
}
fn quotient(p: &BinaryPoint, kc: &KoblitzCurve) -> BinaryPoint {
    let mut q = kc.add(p, p);
    for _ in 1..kc.n {
        q = kc.frobenius(&q);
    }
    q
}
fn targets(kc: &KoblitzCurve) -> Vec<u64> {
    let r = kc.subgroup_order.to_u64().unwrap();
    let lambda = kc.lambda.to_u64().unwrap();
    assert!(r < 4_000_000);
    let mut seen = vec![false; r as usize];
    seen[0] = true;
    let mut reps = Vec::new();
    let mut weight = None;
    for k in 1..r {
        if !seen[k as usize] {
            let mut orbit = BTreeSet::new();
            let mut x = k;
            for _ in 0..kc.n {
                orbit.insert(x);
                orbit.insert(r - x);
                x = x * lambda % r;
            }
            assert_eq!(x, k);
            if let Some(w) = weight {
                assert_eq!(w, orbit.len());
            } else {
                weight = Some(orbit.len());
            }
            for x in orbit {
                assert!(!seen[x as usize]);
                seen[x as usize] = true;
            }
            reps.push(k);
        }
    }
    assert!(seen.into_iter().all(|x| x));
    assert_eq!(reps.len() * weight.unwrap(), r as usize - 1);
    reps
}
struct Base {
    id: Value,
    points: Vec<BinaryPoint>,
    pairs: HashMap<(BigUint, BigUint), Vec<(usize, usize)>>,
    point_keys: HashSet<(BigUint, BigUint)>,
    orbits: usize,
    zero_triples: usize,
}
impl Base {
    fn new(id: Value, points: Vec<BinaryPoint>, kc: &KoblitzCurve) -> Self {
        let point_keys: HashSet<_> = points.iter().map(point_key).collect();
        assert_eq!(point_keys.len(), points.len());
        let mut unseen = point_keys.clone();
        let mut orbits = 0;
        for p in &points {
            assert_ne!(*p, BinaryPoint::Infinity);
            assert_eq!(kc.mul(p, &kc.subgroup_order), BinaryPoint::Infinity);
            assert!(point_keys.contains(&point_key(&kc.frobenius(p))));
            assert!(point_keys.contains(&point_key(&point_neg(p))));
            if !unseen.contains(&point_key(p)) {
                continue;
            }
            let mut q = p.clone();
            for _ in 0..kc.n {
                unseen.remove(&point_key(&q));
                unseen.remove(&point_key(&point_neg(&q)));
                q = kc.frobenius(&q);
            }
            orbits += 1;
        }
        assert!(unseen.is_empty());
        let mut pairs: HashMap<_, Vec<_>> = HashMap::new();
        for i in 0..points.len() {
            for j in i..points.len() {
                pairs
                    .entry(point_key(&kc.add(&points[i], &points[j])))
                    .or_default()
                    .push((i, j));
            }
        }
        let zero_triples = points
            .iter()
            .enumerate()
            .map(|(z, p)| {
                pairs
                    .get(&point_key(&point_neg(p)))
                    .map(|v| v.iter().filter(|(_, j)| *j <= z).count())
                    .unwrap_or(0)
            })
            .sum();
        Self {
            id,
            points,
            pairs,
            point_keys,
            orbits,
            zero_triples,
        }
    }
    fn evaluate(&self, kc: &KoblitzCurve, ks: &[u64], exact: bool) -> Value {
        let mut hits = 0;
        let mut pure_three_hits = 0;
        let mut sum = 0u64;
        let mut histogram = BTreeMap::new();
        let mut counts = Vec::new();
        for k in ks {
            let target = kc.mul(kc.generator(), &BigUint::from(*k));
            let key = point_key(&target);
            let one = usize::from(self.point_keys.contains(&key));
            let two = self.pairs.get(&key).map(Vec::len).unwrap_or(0);
            let mut three = 0;
            let mut witness = None;
            for (z, p) in self.points.iter().enumerate() {
                let rest = kc.add(&target, &point_neg(p));
                if let Some(list) = self.pairs.get(&point_key(&rest)) {
                    for &(i, j) in list {
                        if j <= z {
                            three += 1;
                            if witness.is_none() {
                                witness = Some([i, j, z]);
                            }
                        }
                    }
                }
            }
            if let Some(ids) = witness {
                assert_eq!(
                    ids.iter()
                        .fold(BinaryPoint::Infinity, |s, &i| kc.add(&s, &self.points[i])),
                    target
                );
            }
            let total = one + two + three;
            hits += usize::from(total > 0);
            pure_three_hits += usize::from(three > 0);
            sum += total as u64;
            *histogram.entry(total).or_insert(0usize) += 1;
            counts.push(total);
        }
        let r = kc.subgroup_order.to_u64().unwrap();
        let b = self.points.len() as u64;
        // B union {O}: count all unordered triples, then subtract zero sums.
        let all = (b + 3) * (b + 2) * (b + 1) / 6;
        let zeros = 1 + b / 2 + self.zero_triples as u64;
        let weight = if exact { (r - 1) / ks.len() as u64 } else { 1 };
        if exact {
            assert_eq!(sum * weight + zeros, all, "exact symmetric-cube count");
        }
        json!({"kind":"affine_quotient_base","identity":self.id,"n":kc.n,"a":kc.a,
            "r":r,"field_modulus_low_terms":kc.curve.irreducible.low_terms,"quotient_points":b,
            "projected_signed_orbits":self.orbits,"saturated_affine_lift_points":2*b+1,
            "targets":ks.len(),"target_scalars":ks,"exhaustive_via_symmetry":exact,"target_orbit_size":weight,
            "hits_at_most_three":hits,"hits_exactly_three":pure_three_hits,
            "coverage_at_most_three":hits as f64/ks.len() as f64,"coverage_exactly_three":pure_three_hits as f64/ks.len() as f64,
            "coverage_per_orbit":hits as f64/ks.len() as f64/self.orbits.max(1) as f64,
            "representation_histogram_at_most_three":histogram,"representative_multiplicities":counts,
            "symmetric_cube_total":all,"zero_sum_triples_including_identity":zeros,
            "scope":"point sumsets in quotient coordinates; lengths one, two and three distinguished"})
    }
}
fn conditioned(kc: &KoblitzCurve, sample: &[u64], exact_targets: &[u64]) {
    let n = kc.n;
    let mut rng = rand::rngs::StdRng::seed_from_u64(0x434f4e444954494f);
    let mut candidates = Vec::new();
    let mut attempts = 0usize;
    let mut cardinalities = BTreeMap::new();
    let mut seen_domains = HashSet::new();
    while candidates.len() < 8 && attempts < 128 {
        attempts += 1;
        let raw_offset = F2mElement::from_biguint(&BigUint::from(rng.gen_range(0..(1u64 << n))), n);
        let offset = trace_zero(raw_offset, kc).add(&F2mElement::one(n));
        let mut basis = Vec::new();
        while basis.len() < 3 {
            let raw = rng.gen_range(1..(1u64 << n));
            let b = trace_zero(F2mElement::from_biguint(&BigUint::from(raw), n), kc);
            let mut proposed = basis.clone();
            proposed.push(b);
            if span_f2(&proposed, n)
                .iter()
                .map(|x| x.to_biguint())
                .collect::<HashSet<_>>()
                .len()
                == 1usize << proposed.len()
            {
                basis = proposed;
            }
        }
        let mut us = BTreeMap::new();
        for v in span_f2(&basis, n) {
            let mut u = offset.add(&v);
            assert!(trace(&u, kc));
            if trace(&u.flt_inverse(&kc.curve.irreducible).unwrap(), kc) {
                continue;
            }
            for _ in 0..n {
                us.entry(u.to_biguint()).or_insert_with(|| u.clone());
                u = u.square(&kc.curve.irreducible);
            }
        }
        assert_eq!(us.len() % n as usize, 0);
        *cardinalities.entry(us.len() / n as usize).or_insert(0usize) += 1;
        if us.len() != 4 * n as usize {
            continue;
        }
        if !seen_domains.insert(us.keys().cloned().collect::<Vec<_>>()) {
            continue;
        }
        let points: Vec<_> = us
            .values()
            .flat_map(|u| {
                let ps = points_with_x(&kc.curve, u);
                assert_eq!(ps.len(), 2);
                ps
            })
            .collect();
        let identity = json!({"type":"cardinality_conditioned_affine_u","seed_dimension":3,"attempt":attempts,
            "offset":offset.to_biguint().to_u64().unwrap(),"basis":basis.iter().map(|x|x.to_biguint().to_u64().unwrap()).collect::<Vec<_>>()});
        let base = Base::new(identity, points, kc);
        assert_eq!(base.orbits, 4);
        let result = base.evaluate(kc, sample, false);
        let score = result["coverage_per_orbit"].as_f64().unwrap();
        println!("{result}");
        candidates.push((score, base));
    }
    println!(
        "{}",
        json!({"kind":"conditioned_seed_search","n":n,"attempts":attempts,"accepted":candidates.len(),"orbit_cardinality_histogram":cardinalities,"target_orbits":4,"attempt_cap":128})
    );
    assert_eq!(candidates.len(), 8);
    candidates.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap());
    let remaining = std::env::args().any(|s| s == "--remaining-conditioned");
    for (_, base) in candidates
        .iter()
        .skip(if remaining { 3 } else { 0 })
        .take(if remaining { 5 } else { 3 })
    {
        println!("{}", base.evaluate(kc, exact_targets, true));
    }
}

fn orbit_exchange(kc: &KoblitzCurve, sample: &[u64], exact_targets: &[u64], directory: &str) {
    assert_eq!(kc.n, 19);
    let n = kc.n;
    let seed: Vec<_> = [437455u64, 171788, 13631, 220500]
        .into_iter()
        .map(|x| F2mElement::from_biguint(&BigUint::from(x), n))
        .collect();
    let parent = build_frobenius_union_factor_base(kc, &seed).unwrap();
    let mut parent_points = BTreeMap::new();
    for p in &parent.points {
        let q = quotient(p, kc);
        if q != BinaryPoint::Infinity {
            parent_points.insert(point_key(&q), q);
        }
    }
    let canonical = |p: &BinaryPoint| {
        let mut q = p.clone();
        let mut key = point_key(p);
        for _ in 0..n {
            key = key.min(point_key(&q)).min(point_key(&point_neg(&q)));
            q = kc.frobenius(&q);
        }
        key
    };
    let parent_keys: BTreeSet<_> = parent_points.values().map(canonical).collect();
    assert_eq!(parent_keys.len(), 5);
    let incumbent: Vec<_> = parent_keys.iter().skip(1).cloned().collect();
    let mut all_points = parent_points;
    let raw = std::fs::read_to_string(
        std::path::Path::new(directory).join("affine-conditioned-n19.jsonl"),
    )
    .unwrap();
    let mut seed_count = 0;
    for line in raw.lines() {
        let row: Value = serde_json::from_str(line).unwrap();
        if row["kind"] != "affine_quotient_base" || row["exhaustive_via_symmetry"] != false {
            continue;
        }
        assert_eq!(row["n"], 19);
        assert_eq!(row["projected_signed_orbits"], 4);
        seed_count += 1;
        let id = &row["identity"];
        let offset = F2mElement::from_biguint(&BigUint::from(id["offset"].as_u64().unwrap()), n);
        let basis: Vec<_> = id["basis"]
            .as_array()
            .unwrap()
            .iter()
            .map(|x| F2mElement::from_biguint(&BigUint::from(x.as_u64().unwrap()), n))
            .collect();
        for v in span_f2(&basis, n) {
            let mut u = offset.add(&v);
            assert!(trace(&u, kc));
            if trace(&u.flt_inverse(&kc.curve.irreducible).unwrap(), kc) {
                continue;
            }
            for _ in 0..n {
                for q in points_with_x(&kc.curve, &u) {
                    all_points.insert(point_key(&q), q);
                }
                u = u.square(&kc.curve.irreducible);
            }
        }
    }
    assert_eq!(seed_count, 8);
    let mut groups: BTreeMap<_, Vec<_>> = BTreeMap::new();
    for p in all_points.into_values() {
        groups.entry(canonical(&p)).or_default().push(p);
    }
    for g in groups.values() {
        assert_eq!(g.len(), 2 * n as usize);
    }
    if std::env::args().any(|s| s == "--global-pool") {
        global_pool(kc, &groups, exact_targets, directory);
        return;
    }
    let point_repr =
        |key: &(BigUint, BigUint)| json!([key.0.to_u64().unwrap() - 1, key.1.to_u64().unwrap()]);
    let mut candidates = Vec::new();
    let points: Vec<_> = incumbent
        .iter()
        .flat_map(|key| groups[key].clone())
        .collect();
    let base = Base::new(
        json!({"type":"exchange_incumbent","representatives":incumbent.iter().map(point_repr).collect::<Vec<_>>()}),
        points,
        kc,
    );
    let result = base.evaluate(kc, sample, false);
    let score = result["coverage_per_orbit"].as_f64().unwrap();
    println!("{result}");
    candidates.push((score, base));
    for remove in 0..incumbent.len() {
        for added in groups.keys() {
            if incumbent.contains(added) {
                continue;
            }
            let mut chosen = incumbent.clone();
            chosen[remove] = added.clone();
            chosen.sort();
            let points: Vec<_> = chosen.iter().flat_map(|key| groups[key].clone()).collect();
            let id = json!({"type":"one_orbit_exchange","removed":point_repr(&incumbent[remove]),"added":point_repr(added),"representatives":chosen.iter().map(point_repr).collect::<Vec<_>>()});
            let base = Base::new(id, points, kc);
            assert_eq!(base.orbits, 4);
            assert_eq!(base.points.len(), 152);
            let result = base.evaluate(kc, sample, false);
            let score = result["coverage_per_orbit"].as_f64().unwrap();
            println!("{result}");
            candidates.push((score, base));
        }
    }
    println!(
        "{}",
        json!({"kind":"orbit_exchange_summary","pool_orbits":groups.len(),"incumbent_orbits":4,"candidates_including_incumbent":candidates.len(),"screening_targets":sample.len(),"exact_finalists":5})
    );
    candidates.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap());
    for (_, base) in candidates.iter().take(5) {
        println!("{}", base.evaluate(kc, exact_targets, true));
    }
}

include!("support/koblitz_global_pool.rs");
include!("support/koblitz_full_orbit_search.rs");

fn main() {
    let n = std::env::args()
        .nth(1)
        .unwrap_or("19".to_string())
        .parse::<u32>()
        .unwrap();
    assert!(n == 17 || n == 19);
    let kc = KoblitzCurve::new(1, n).unwrap();
    assert_eq!(kc.cofactor, BigUint::from(2u8));
    let exact_targets = targets(&kc);
    let r = kc.subgroup_order.to_u64().unwrap();
    let mut rng = rand::rngs::StdRng::seed_from_u64(0x414646494e45 + n as u64);
    let mut selected = HashSet::new();
    let mut sample = Vec::new();
    while sample.len() < 256 {
        let k = rng.gen_range(1..r);
        if selected.insert(k) {
            sample.push(k);
        }
    }
    let arguments: Vec<_> = std::env::args().collect();
    if let Some(pos) = arguments.iter().position(|s| s == "--full-orbit-search") {
        let directory = arguments.get(pos + 1).expect("artifact directory");
        let max_rounds = arguments
            .get(pos + 2)
            .map(|value| value.parse().expect("maximum search rounds"))
            .unwrap_or(12);
        let include_shorter = !arguments.iter().any(|value| value == "--exactly-three");
        let kick_seed = arguments
            .iter()
            .position(|value| value == "--kick-seed")
            .map(|position| {
                arguments
                    .get(position + 1)
                    .expect("kick seed")
                    .parse()
                    .expect("integer kick seed")
            });
        full_orbit_search(
            &kc,
            &exact_targets,
            directory,
            max_rounds,
            include_shorter,
            kick_seed,
        );
        return;
    }
    if let Some(pos) = arguments.iter().position(|s| s == "--exchange") {
        orbit_exchange(
            &kc,
            &sample,
            &exact_targets,
            arguments.get(pos + 1).expect("artifact directory"),
        );
        return;
    }
    if std::env::args().any(|s| s == "--conditioned") {
        conditioned(&kc, &sample, &exact_targets);
        return;
    }
    // Independent quotient-side support check for the earlier saturated parent.
    if n == 19 {
        let seed: Vec<_> = [437455u64, 171788, 13631, 220500]
            .into_iter()
            .map(|x| F2mElement::from_biguint(&BigUint::from(x), n))
            .collect();
        let parent = build_frobenius_union_factor_base(&kc, &seed).unwrap();
        let mut points = BTreeMap::new();
        for p in &parent.points {
            let q = quotient(p, &kc);
            if q != BinaryPoint::Infinity {
                points.insert(point_key(&q), q);
            }
        }
        let base = Base::new(
            json!({"type":"earlier_parent_quotient"}),
            points.into_values().collect(),
            &kc,
        );
        assert_eq!(base.points.len(), 190);
        if std::env::args().any(|s| s == "--old-best-control") {
            let canonical = |p: &BinaryPoint| {
                let mut q = p.clone();
                let mut key = point_key(p);
                for _ in 0..n {
                    key = key.min(point_key(&q)).min(point_key(&point_neg(&q)));
                    q = kc.frobenius(&q);
                }
                key
            };
            let orbit_keys: BTreeSet<_> = base.points.iter().map(canonical).collect();
            let drop = orbit_keys.iter().next().unwrap();
            let points: Vec<_> = base
                .points
                .iter()
                .filter(|p| canonical(p) != *drop)
                .cloned()
                .collect();
            let best = Base::new(
                json!({"type":"earlier_best_four_orbit_quotient","omitted_orbit":0}),
                points,
                &kc,
            );
            assert_eq!(best.points.len(), 152);
            assert_eq!(best.orbits, 4);
            let result = best.evaluate(&kc, &exact_targets, true);
            assert_eq!(result["hits_at_most_three"], 6165);
            println!("{result}");
            return;
        }
        let result = base.evaluate(&kc, &exact_targets, true);
        assert_eq!(result["hits_at_most_three"], 6811);
        println!("{result}");
    }
    let mut candidates = Vec::new();
    for ell in 2..=4usize {
        for trial in 0..4 {
            let raw_offset = if trial == 0 {
                F2mElement::zero(n)
            } else {
                F2mElement::from_biguint(&BigUint::from(rng.gen_range(0..(1u64 << n))), n)
            };
            let offset = trace_zero(raw_offset, &kc).add(&F2mElement::one(n));
            assert!(trace(&offset, &kc));
            let mut basis = Vec::new();
            while basis.len() < ell {
                let raw = if trial == 0 {
                    1u64 << (basis.len() + 1)
                } else {
                    rng.gen_range(1..(1u64 << n))
                };
                let b = trace_zero(F2mElement::from_biguint(&BigUint::from(raw), n), &kc);
                let mut proposed = basis.clone();
                proposed.push(b);
                if span_f2(&proposed, n)
                    .iter()
                    .map(|x| x.to_biguint())
                    .collect::<HashSet<_>>()
                    .len()
                    == 1usize << proposed.len()
                {
                    basis = proposed;
                }
            }
            let mut us = BTreeMap::new();
            for v in span_f2(&basis, n) {
                let mut u = offset.add(&v);
                assert!(trace(&u, &kc));
                if trace(&u.flt_inverse(&kc.curve.irreducible).unwrap(), &kc) {
                    continue;
                }
                for _ in 0..n {
                    us.entry(u.to_biguint()).or_insert_with(|| u.clone());
                    u = u.square(&kc.curve.irreducible);
                }
            }
            let points: Vec<_> = us
                .values()
                .flat_map(|u| {
                    let ps = points_with_x(&kc.curve, u);
                    assert_eq!(ps.len(), 2);
                    ps
                })
                .collect();
            let identity = json!({"type":"trace_aligned_affine_u","seed_dimension":ell,"trial":trial,
            "offset":offset.to_biguint().to_u64().unwrap(),"basis":basis.iter().map(|x|x.to_biguint().to_u64().unwrap()).collect::<Vec<_>>()});
            if points.is_empty() {
                println!(
                    "{}",
                    json!({"kind":"empty_affine_seed","identity":identity,"n":n})
                );
                continue;
            }
            let base = Base::new(identity, points, &kc);
            let result = base.evaluate(&kc, &sample, false);
            let score = result["coverage_per_orbit"].as_f64().unwrap();
            println!("{result}");
            candidates.push((score, base));
        }
    }
    candidates.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap());
    for (_, base) in candidates.iter().take(3) {
        println!("{}", base.evaluate(&kc, &exact_targets, true));
    }
}
