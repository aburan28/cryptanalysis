// Exact support optimization for the fixed mathematical orbit pool.
fn global_pool(
    kc: &KoblitzCurve,
    groups: &BTreeMap<(BigUint, BigUint), Vec<BinaryPoint>>,
    exact_targets: &[u64],
    directory: &str,
) {
    let n = kc.n;
    let m = groups.len();
    assert_eq!(m, 37);
    let r = kc.subgroup_order.to_u64().unwrap();
    let words = exact_targets.len().div_ceil(64);
    let group_points: Vec<_> = groups.values().collect();
    let keys: Vec<_> = groups.keys().cloned().collect();
    let mut target_index = HashMap::new();
    for (index, k) in exact_targets.iter().enumerate() {
        let mut q = kc.mul(kc.generator(), &BigUint::from(*k));
        for _ in 0..n {
            for point in [q.clone(), point_neg(&q)] {
                if let Some(previous) = target_index.insert(point_key(&point), index) {
                    assert_eq!(previous, index);
                }
            }
            q = kc.frobenius(&q);
        }
    }
    assert_eq!(target_index.len(), r as usize - 1);
    let insert = |bits: &mut Vec<u64>, point: &BinaryPoint| {
        if *point != BinaryPoint::Infinity {
            let i = target_index[&point_key(point)];
            bits[i / 64] |= 1u64 << (i % 64);
        }
    };
    let mut singles = vec![vec![0u64; words]; m];
    let mut pairs = vec![Vec::<u64>::new(); m * m];
    let mut triples = vec![Vec::<u64>::new(); m * m * m];
    let mut triple_types = 0usize;
    for i in 0..m {
        let anchor = &group_points[i][0];
        assert_eq!(point_key(anchor), keys[i]);
        insert(&mut singles[i], anchor);
        for j in i..m {
            let partial: Vec<_> = group_points[j].iter().map(|q| kc.add(anchor, q)).collect();
            let mut pair = vec![0; words];
            for q in &partial {
                insert(&mut pair, q);
            }
            pairs[i * m + j] = pair;
            for k in j..m {
                let mut support = vec![0; words];
                for q in &partial {
                    if *q == BinaryPoint::Infinity {
                        insert(&mut support, &group_points[k][0]);
                        continue;
                    }
                    for p in group_points[k] {
                        insert(&mut support, &kc.add(q, p));
                    }
                }
                triples[(i * m + j) * m + k] = support;
                triple_types += 1;
            }
        }
        println!(
            "{}",
            json!({"kind":"global_pool_precompute_progress","anchor_orbits_done":i+1,
            "pool_orbits":m,"triplet_types_processed":triple_types})
        );
    }
    assert_eq!(triple_types, m * (m + 1) * (m + 2) / 6);
    // Normalize one summand from the least-indexed orbit to its anchor.
    // The other summands remain in their respective signed Frobenius
    // orbits, so the cached support contains every possible target orbit.
    let support_for = |chosen: &[usize], bits: &mut Vec<u64>| {
        bits.fill(0);
        let merge = |bits: &mut Vec<u64>, other: &Vec<u64>| {
            for (x, y) in bits.iter_mut().zip(other) {
                *x |= *y;
            }
        };
        for (a, &i) in chosen.iter().enumerate() {
            merge(bits, &singles[i]);
            for (b, &j) in chosen.iter().enumerate().skip(a) {
                merge(bits, &pairs[i * m + j]);
                for &k in chosen.iter().skip(b) {
                    merge(bits, &triples[(i * m + j) * m + k]);
                }
            }
        }
    };
    let mut scratch = vec![0; words];
    let mut checked_controls = 0;
    let previous =
        std::fs::read_to_string(std::path::Path::new(directory).join("orbit-exchange-n19.jsonl"))
            .unwrap();
    for line in previous.lines() {
        let d: Value = serde_json::from_str(line).unwrap();
        if d["exhaustive_via_symmetry"] != true {
            continue;
        }
        let mut chosen: Vec<_> = d["identity"]["representatives"]
            .as_array()
            .unwrap()
            .iter()
            .map(|p| {
                let key = (
                    BigUint::from(p[0].as_u64().unwrap() + 1),
                    BigUint::from(p[1].as_u64().unwrap()),
                );
                keys.binary_search(&key).unwrap()
            })
            .collect();
        chosen.sort();
        support_for(&chosen, &mut scratch);
        assert_eq!(
            scratch.iter().map(|x| x.count_ones() as u64).sum::<u64>(),
            d["hits_at_most_three"].as_u64().unwrap()
        );
        checked_controls += 1;
    }
    assert_eq!(checked_controls, 5);
    let mut best = 0u64;
    let mut winners = Vec::new();
    let mut scanned = 0usize;
    let mut histogram = BTreeMap::new();
    for a in 0..m {
        for b in a + 1..m {
            for c in b + 1..m {
                for d in c + 1..m {
                    let chosen = [a, b, c, d];
                    support_for(&chosen, &mut scratch);
                    let coverage = scratch.iter().map(|x| x.count_ones() as u64).sum::<u64>();
                    scanned += 1;
                    *histogram.entry(coverage).or_insert(0usize) += 1;
                    if coverage > best {
                        best = coverage;
                        winners.clear();
                    }
                    if coverage == best {
                        winners.push(chosen.to_vec());
                    }
                }
            }
        }
    }
    assert_eq!(scanned, m * (m - 1) * (m - 2) * (m - 3) / 24);
    let chosen = winners[0].clone();
    let point_repr = |i: &usize| {
        json!([
            keys[*i].0.to_u64().unwrap() - 1,
            keys[*i].1.to_u64().unwrap()
        ])
    };
    support_for(&chosen, &mut scratch);
    println!(
        "{}",
        json!({"kind":"global_pool_optimum","pool_orbits":m,
        "pool_representatives":(0..m).map(|i|point_repr(&i)).collect::<Vec<_>>(),
        "four_orbit_subsets_examined":scanned,"triplet_support_types":triple_types,
        "independent_exact_controls":checked_controls,"target_orbits":exact_targets.len(),
        "target_orbit_size":(r as usize-1)/exact_targets.len(),"best_covered_target_orbits":best,
        "maximizing_subsets":winners,"selected_indices":chosen,
        "selected_representatives":chosen.iter().map(point_repr).collect::<Vec<_>>(),
        "coverage_histogram":histogram,"selected_support_words":scratch,
        "scope":"global optimum among four-element subsets of this fixed 37-orbit pool"})
    );
    let points: Vec<_> = chosen
        .iter()
        .flat_map(|&i| group_points[i].iter().cloned())
        .collect();
    let selected = Base::new(
        json!({"type":"global_pool_selected",
        "representatives":chosen.iter().map(point_repr).collect::<Vec<_>>(),"pool_indices":chosen}),
        points,
        kc,
    );
    let verification = selected.evaluate(kc, exact_targets, true);
    assert_eq!(verification["hits_at_most_three"].as_u64().unwrap(), best);
    println!("{verification}");
}
