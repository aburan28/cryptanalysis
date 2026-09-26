use rayon::prelude::*;

fn add_mod(a: u64, b: u64, modulus: u64) -> u64 {
    let sum = a + b;
    if sum >= modulus {
        sum - modulus
    } else {
        sum
    }
}

fn insert_scalar(bits: &mut [u64], scalar: u64, scalar_orbit: &[usize]) {
    if scalar == 0 {
        return;
    }
    let index = scalar_orbit[scalar as usize];
    assert_ne!(index, usize::MAX);
    bits[index / 64] |= 1u64 << (index % 64);
}

fn add_pair_type(
    bits: &mut [u64],
    anchor: u64,
    other: &[u64],
    modulus: u64,
    scalar_orbit: &[usize],
) {
    for &b in other {
        insert_scalar(bits, add_mod(anchor, b, modulus), scalar_orbit);
    }
}

fn add_triple_type(
    bits: &mut [u64],
    anchor: u64,
    second: &[u64],
    third: &[u64],
    modulus: u64,
    scalar_orbit: &[usize],
) {
    for &b in second {
        let partial = add_mod(anchor, b, modulus);
        for &c in third {
            insert_scalar(bits, add_mod(partial, c, modulus), scalar_orbit);
        }
    }
}

fn scalar_support(
    chosen: &[usize],
    anchors: &[u64],
    orbit_scalars: &[Vec<u64>],
    scalar_orbit: &[usize],
    modulus: u64,
    include_shorter: bool,
) -> Vec<u64> {
    let mut bits = vec![0u64; anchors.len().div_ceil(64)];
    for a in 0..chosen.len() {
        let i = chosen[a];
        if include_shorter {
            insert_scalar(&mut bits, anchors[i], scalar_orbit);
        }
        for b in a..chosen.len() {
            let j = chosen[b];
            if include_shorter {
                add_pair_type(
                    &mut bits,
                    anchors[i],
                    &orbit_scalars[j],
                    modulus,
                    scalar_orbit,
                );
            }
            for c in b..chosen.len() {
                let k = chosen[c];
                add_triple_type(
                    &mut bits,
                    anchors[i],
                    &orbit_scalars[j],
                    &orbit_scalars[k],
                    modulus,
                    scalar_orbit,
                );
            }
        }
    }
    bits
}

fn candidate_score(
    retained: &[usize],
    candidate: usize,
    retained_support: &[u64],
    anchors: &[u64],
    orbit_scalars: &[Vec<u64>],
    scalar_orbit: &[usize],
    modulus: u64,
    include_shorter: bool,
) -> u32 {
    let mut bits = retained_support.to_vec();
    let anchor = anchors[candidate];
    if include_shorter {
        insert_scalar(&mut bits, anchor, scalar_orbit);
        add_pair_type(
            &mut bits,
            anchor,
            &orbit_scalars[candidate],
            modulus,
            scalar_orbit,
        );
        for &i in retained {
            add_pair_type(&mut bits, anchor, &orbit_scalars[i], modulus, scalar_orbit);
        }
    }

    add_triple_type(
        &mut bits,
        anchor,
        &orbit_scalars[candidate],
        &orbit_scalars[candidate],
        modulus,
        scalar_orbit,
    );
    for &i in retained {
        add_triple_type(
            &mut bits,
            anchor,
            &orbit_scalars[candidate],
            &orbit_scalars[i],
            modulus,
            scalar_orbit,
        );
    }
    for a in 0..retained.len() {
        for b in a..retained.len() {
            add_triple_type(
                &mut bits,
                anchor,
                &orbit_scalars[retained[a]],
                &orbit_scalars[retained[b]],
                modulus,
                scalar_orbit,
            );
        }
    }
    bits.iter().map(|word| word.count_ones()).sum()
}

fn canonical_point_key(point: &BinaryPoint, kc: &KoblitzCurve) -> (BigUint, BigUint) {
    let mut q = point.clone();
    let mut key = point_key(point);
    for _ in 0..kc.n {
        key = key.min(point_key(&q)).min(point_key(&point_neg(&q)));
        q = kc.frobenius(&q);
    }
    key
}

fn point_repr_for_orbit(index: usize, anchors: &[u64], kc: &KoblitzCurve) -> Value {
    let mut q = kc.mul(kc.generator(), &BigUint::from(anchors[index]));
    let mut best = q.clone();
    let mut best_key = point_key(&best);
    for _ in 0..kc.n {
        for point in [q.clone(), point_neg(&q)] {
            let key = point_key(&point);
            if key < best_key {
                best_key = key;
                best = point;
            }
        }
        q = kc.frobenius(&q);
    }
    match best {
        BinaryPoint::Infinity => unreachable!(),
        BinaryPoint::Affine { x, y } => json!([
            x.to_biguint().to_u64().unwrap(),
            y.to_biguint().to_u64().unwrap()
        ]),
    }
}

fn full_orbit_search(
    kc: &KoblitzCurve,
    exact_targets: &[u64],
    directory: &str,
    max_rounds: usize,
    include_shorter: bool,
    kick_seed: Option<u64>,
) {
    assert_eq!(kc.n, 19);
    let modulus = kc.subgroup_order.to_u64().unwrap();
    let lambda = kc.lambda.to_u64().unwrap();
    let orbit_size = 2 * kc.n as usize;
    let mut scalar_orbit = vec![usize::MAX; modulus as usize];
    scalar_orbit[0] = exact_targets.len();
    let mut orbit_scalars = Vec::with_capacity(exact_targets.len());
    for (index, &anchor) in exact_targets.iter().enumerate() {
        let mut orbit = BTreeSet::new();
        let mut scalar = anchor;
        for _ in 0..kc.n {
            orbit.insert(scalar);
            orbit.insert(modulus - scalar);
            scalar = scalar * lambda % modulus;
        }
        assert_eq!(scalar, anchor);
        assert_eq!(orbit.len(), orbit_size);
        let orbit: Vec<_> = orbit.into_iter().collect();
        for &value in &orbit {
            let previous = std::mem::replace(&mut scalar_orbit[value as usize], index);
            assert!(previous == usize::MAX || previous == index);
        }
        orbit_scalars.push(orbit);
    }
    assert!(scalar_orbit[..modulus as usize]
        .iter()
        .enumerate()
        .all(|(scalar, &index)| scalar == 0 || index < exact_targets.len()));

    let artifact =
        std::fs::read_to_string(std::path::Path::new(directory).join("orbit-global-n19.jsonl"))
            .unwrap();
    let incumbent_row: Value = artifact
        .lines()
        .map(|line| serde_json::from_str(line).unwrap())
        .find(|row: &Value| row["kind"] == "global_pool_optimum")
        .expect("fixed-pool optimum");
    let incumbent_exact_row: Value = artifact
        .lines()
        .map(|line| serde_json::from_str(line).unwrap())
        .find(|row: &Value| row["identity"]["type"] == "global_pool_selected")
        .expect("fixed-pool exact verification");
    let incumbent_points = incumbent_row["selected_representatives"]
        .as_array()
        .expect("selected point representatives");

    let mut canonical_orbit = HashMap::new();
    for (index, &anchor) in exact_targets.iter().enumerate() {
        let point = kc.mul(kc.generator(), &BigUint::from(anchor));
        let previous = canonical_orbit.insert(canonical_point_key(&point, kc), index);
        assert!(previous.is_none());
    }
    let mut chosen: Vec<_> = incumbent_points
        .iter()
        .map(|point| {
            let key = (
                BigUint::from(point[0].as_u64().unwrap() + 1),
                BigUint::from(point[1].as_u64().unwrap()),
            );
            canonical_orbit[&key]
        })
        .collect();
    chosen.sort_unstable();
    chosen.dedup();
    assert_eq!(chosen.len(), 4);

    if let Some(seed) = kick_seed {
        let mut rng = rand::rngs::StdRng::seed_from_u64(seed);
        let first = rng.gen_range(0..chosen.len());
        let mut second = rng.gen_range(0..chosen.len() - 1);
        if second >= first {
            second += 1;
        }
        for position in [first, second] {
            loop {
                let candidate = rng.gen_range(0..exact_targets.len());
                if !chosen.contains(&candidate) {
                    chosen[position] = candidate;
                    break;
                }
            }
        }
        chosen.sort_unstable();
        chosen.dedup();
        assert_eq!(chosen.len(), 4);
    }

    let initial_support = scalar_support(
        &chosen,
        exact_targets,
        &orbit_scalars,
        &scalar_orbit,
        modulus,
        include_shorter,
    );
    let mut current_score: u32 = initial_support.iter().map(|word| word.count_ones()).sum();
    if kick_seed.is_none() {
        let expected_incumbent = if include_shorter {
            incumbent_row["best_covered_target_orbits"]
                .as_u64()
                .unwrap()
        } else {
            incumbent_exact_row["hits_exactly_three"].as_u64().unwrap()
        };
        assert_eq!(current_score as u64, expected_incumbent);
    }
    let objective = if include_shorter {
        "at_most_three"
    } else {
        "exactly_three"
    };
    println!(
        "{}",
        json!({"kind":"full_orbit_search_start","candidate_orbits":exact_targets.len(),
        "orbit_size":orbit_size,"selected_indices":chosen,
        "selected_scalar_representatives":chosen.iter().map(|&i|exact_targets[i]).collect::<Vec<_>>(),
        "objective":objective,"kick_seed":kick_seed,"covered_target_orbits":current_score,"target_orbits":exact_targets.len(),
        "search":"deterministic steepest exact one-orbit exchange over the full signed-Frobenius orbit universe"})
    );

    let mut accepted = 0usize;
    for round in 0..max_rounds {
        let mut proposals = Vec::new();
        for remove_position in 0..chosen.len() {
            let retained: Vec<_> = chosen
                .iter()
                .enumerate()
                .filter_map(|(position, &index)| (position != remove_position).then_some(index))
                .collect();
            let retained_support = scalar_support(
                &retained,
                exact_targets,
                &orbit_scalars,
                &scalar_orbit,
                modulus,
                include_shorter,
            );
            let best = (0..exact_targets.len())
                .into_par_iter()
                .filter(|candidate| !retained.contains(candidate))
                .map(|candidate| {
                    let score = candidate_score(
                        &retained,
                        candidate,
                        &retained_support,
                        exact_targets,
                        &orbit_scalars,
                        &scalar_orbit,
                        modulus,
                        include_shorter,
                    );
                    (candidate, score)
                })
                .max_by(|left, right| left.1.cmp(&right.1).then_with(|| right.0.cmp(&left.0)))
                .unwrap();
            println!(
                "{}",
                json!({"kind":"full_orbit_removal_scan","round":round,
                "objective":objective,
                "remove_position":remove_position,"removed_index":chosen[remove_position],
                "removed_scalar_representative":exact_targets[chosen[remove_position]],
                "best_added_index":best.0,"best_added_scalar_representative":exact_targets[best.0],
                "candidates_scored":exact_targets.len()-retained.len(),
                "best_covered_target_orbits":best.1})
            );
            proposals.push((remove_position, best.0, best.1));
        }
        proposals.sort_by(|left, right| {
            right
                .2
                .cmp(&left.2)
                .then_with(|| left.0.cmp(&right.0))
                .then_with(|| left.1.cmp(&right.1))
        });
        let (remove_position, added, next_score) = proposals[0];
        if next_score <= current_score {
            println!(
                "{}",
                json!({"kind":"full_orbit_one_exchange_local_optimum","round":round,
                "objective":objective,
                "selected_indices":chosen,"covered_target_orbits":current_score,
                "proper_neighbors_scored":chosen.len()*(exact_targets.len()-chosen.len()),
                "evaluations_including_current_reinsertions":chosen.len()*(exact_targets.len()-chosen.len()+1),
                "best_neighbor_covered_target_orbits":next_score})
            );
            break;
        }
        let removed = chosen[remove_position];
        chosen[remove_position] = added;
        chosen.sort_unstable();
        current_score = next_score;
        accepted += 1;
        println!(
            "{}",
            json!({"kind":"full_orbit_exchange_accepted","round":round,
            "objective":objective,
            "removed_index":removed,"removed_scalar_representative":exact_targets[removed],
            "added_index":added,"added_scalar_representative":exact_targets[added],
            "selected_indices":chosen,"covered_target_orbits":current_score})
        );
    }

    let final_support = scalar_support(
        &chosen,
        exact_targets,
        &orbit_scalars,
        &scalar_orbit,
        modulus,
        include_shorter,
    );
    let final_score: u32 = final_support.iter().map(|word| word.count_ones()).sum();
    assert_eq!(final_score, current_score);
    let mut points = BTreeMap::new();
    for &index in &chosen {
        let mut point = kc.mul(kc.generator(), &BigUint::from(exact_targets[index]));
        for _ in 0..kc.n {
            for q in [point.clone(), point_neg(&point)] {
                points.insert(point_key(&q), q);
            }
            point = kc.frobenius(&point);
        }
    }
    assert_eq!(points.len(), 4 * orbit_size);
    let point_representatives: Vec<_> = chosen
        .iter()
        .map(|&index| point_repr_for_orbit(index, exact_targets, kc))
        .collect();
    println!(
        "{}",
        json!({"kind":"full_orbit_search_result","candidate_orbits":exact_targets.len(),
        "objective":objective,"accepted_exchanges":accepted,"selected_indices":chosen,
        "selected_scalar_representatives":chosen.iter().map(|&i|exact_targets[i]).collect::<Vec<_>>(),
        "selected_point_representatives":point_representatives,
        "covered_target_orbits":final_score,"target_orbits":exact_targets.len(),
        "coverage":final_score as f64/exact_targets.len() as f64,
        "selected_support_words":final_support,
        "scope":"exact full-universe one-orbit local optimum for the stated summand objective; independent group-law verification follows"})
    );
    let base = Base::new(
        json!({"type":"full_orbit_one_exchange_selected",
        "scalar_representatives":chosen.iter().map(|&i|exact_targets[i]).collect::<Vec<_>>(),
        "point_representatives":point_representatives}),
        points.into_values().collect(),
        kc,
    );
    let verification = base.evaluate(kc, exact_targets, true);
    let verification_field = if include_shorter {
        "hits_at_most_three"
    } else {
        "hits_exactly_three"
    };
    assert_eq!(
        verification[verification_field].as_u64().unwrap(),
        final_score as u64
    );
    println!("{verification}");
}

#[cfg(test)]
mod full_orbit_tests {
    use super::*;

    fn scalar_tables(kc: &KoblitzCurve, anchors: &[u64]) -> (Vec<Vec<u64>>, Vec<usize>, u64) {
        let modulus = kc.subgroup_order.to_u64().unwrap();
        let lambda = kc.lambda.to_u64().unwrap();
        let mut scalar_orbit = vec![usize::MAX; modulus as usize];
        scalar_orbit[0] = anchors.len();
        let mut orbit_scalars = Vec::new();
        for (index, &anchor) in anchors.iter().enumerate() {
            let mut values = BTreeSet::new();
            let mut current = anchor;
            for _ in 0..kc.n {
                values.insert(current);
                values.insert(modulus - current);
                current = current * lambda % modulus;
            }
            let values: Vec<_> = values.into_iter().collect();
            for &value in &values {
                assert_eq!(scalar_orbit[value as usize], usize::MAX);
                scalar_orbit[value as usize] = index;
            }
            orbit_scalars.push(values);
        }
        assert!(scalar_orbit
            .iter()
            .enumerate()
            .all(|(scalar, &index)| scalar == 0 || index < anchors.len()));
        (orbit_scalars, scalar_orbit, modulus)
    }

    #[test]
    fn incremental_candidate_score_matches_full_support() {
        let kc = KoblitzCurve::new(1, 7).unwrap();
        let anchors = targets(&kc);
        assert!(anchors.len() >= 4);
        let (orbit_scalars, scalar_orbit, modulus) = scalar_tables(&kc, &anchors);
        let retained = [0usize, 1, 2];
        for include_shorter in [false, true] {
            let retained_support = scalar_support(
                &retained,
                &anchors,
                &orbit_scalars,
                &scalar_orbit,
                modulus,
                include_shorter,
            );
            for candidate in 3..anchors.len() {
                let incremental = candidate_score(
                    &retained,
                    candidate,
                    &retained_support,
                    &anchors,
                    &orbit_scalars,
                    &scalar_orbit,
                    modulus,
                    include_shorter,
                );
                let full: u32 = scalar_support(
                    &[0, 1, 2, candidate],
                    &anchors,
                    &orbit_scalars,
                    &scalar_orbit,
                    modulus,
                    include_shorter,
                )
                .iter()
                .map(|word| word.count_ones())
                .sum();
                assert_eq!(incremental, full);
            }
        }
    }

    #[test]
    fn selected_degree_19_support_counts_are_reproducible() {
        let kc = KoblitzCurve::new(1, 19).unwrap();
        let anchors = targets(&kc);
        let (orbit_scalars, scalar_orbit, modulus) = scalar_tables(&kc, &anchors);
        let chosen = [200usize, 1913, 2481, 5643];
        assert_eq!(chosen.map(|index| anchors[index]), [203, 2143, 2901, 9853]);
        let exactly_three: u32 = scalar_support(
            &chosen,
            &anchors,
            &orbit_scalars,
            &scalar_orbit,
            modulus,
            false,
        )
        .iter()
        .map(|word| word.count_ones())
        .sum();
        let at_most_three: u32 = scalar_support(
            &chosen,
            &anchors,
            &orbit_scalars,
            &scalar_orbit,
            modulus,
            true,
        )
        .iter()
        .map(|word| word.count_ones())
        .sum();
        assert_eq!(exactly_three, 6256);
        assert_eq!(at_most_three, 6300);
    }
}
