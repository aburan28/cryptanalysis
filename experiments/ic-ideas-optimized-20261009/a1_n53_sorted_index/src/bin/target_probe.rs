#![recursion_limit = "256"]

// Reuse the frozen field, curve, base, and echelon implementation from the
// measured four-summand runner without changing its source or binary digest.
mod arithmetic {
    include!(concat!(env!("OUT_DIR"), "/legacy.rs"));

    use std::fs;

    #[derive(Clone, Copy)]
    struct PairRecord {
        left: u16,
        right: u16,
        relative: u8,
        second_negative: bool,
        canonical_shift: u8,
    }

    fn negative(point: FastPoint) -> FastPoint {
        point.map(|(x, y)| (x, x ^ y))
    }

    fn locate(base: &Base, point: FastPoint) -> usize {
        let (x, _) = point.expect("pair witness must be affine");
        *base
            .by_x
            .get(&x)
            .expect("witness x belongs to base")
            .iter()
            .find(|&&index| base.points[index] == point)
            .expect("witness point belongs to base")
    }

    fn maybe_progress(path: &Option<String>, value: serde_json::Value) {
        if let Some(path) = path {
            let pending = format!("{path}.partial");
            fs::write(&pending, value.to_string()).expect("write progress");
            fs::rename(&pending, path).expect("publish progress");
        }
    }

    pub fn run() {
        let args: Vec<String> = std::env::args().collect();
        assert_eq!(args.len(), 6, "usage: <closure> <geometric_columns> <target.json> <seed_logs.json> <out.json>");
        let policy = args[1].as_str();
        assert_eq!(policy, "closure");
        let columns: usize = args[2].parse().expect("columns");
        assert_eq!(columns, 600);
        let target_words: [u64; 2] = serde_json::from_slice(
            &fs::read(&args[3]).expect("read public target point"))
            .expect("target point coordinate pair");
        let log_record: serde_json::Value = serde_json::from_slice(
            &fs::read(&args[4]).expect("read independently replayed base logs"))
            .expect("base log receipt");
        assert_eq!(log_record["full_rank"], true);
        let logs: Vec<u64> = serde_json::from_value(log_record["solved_seed_logs"].clone())
            .expect("60 solved seed logs");
        assert_eq!(logs.len(), 60);
        let progress = std::env::var("A1_PAIR_PROGRESS_PATH").ok();
        let curve = KoblitzCurve::new(0, 53).expect("N53 Koblitz rung");
        let r = curve.subgroup_order.to_u64().expect("u64 subgroup order");
        let fast = FastBinaryCurve::new(&curve.curve.irreducible, 0).expect("fast curve");
        let gf = Gf2::new(&curve.curve.irreducible);
        let b = gf.from_element(&curve.curve.b);
        let generator = match curve.generator() {
            crypto_lib::binary_ecc::BinaryPoint::Affine { x, y } => {
                Some((fast.word(x), fast.word(y)))
            }
            crypto_lib::binary_ecc::BinaryPoint::Infinity => panic!("generator at infinity"),
        };
        assert_eq!(fast.scalar_mul(generator, &BigUint::from(r)), None);
        let base_started = Instant::now();
        let (points, labels, representatives, geometric_representatives, scanned_x) =
            if policy == "seed" {
                let (points, labels, reps, scanned) = construct_base(&fast, &curve, b, columns, r);
                let geometric_reps = reps.clone();
                (points, labels, reps, geometric_reps, scanned)
            } else {
                construct_multiplier_closure(&fast, &curve, b, columns, r)
            };
        let mut by_x: HashMap<u64, Vec<usize>> = HashMap::new();
        for (index, point) in points.iter().enumerate() {
            if let Some((x, _)) = point {
                by_x.entry(*x).or_default().push(index);
            }
        }
        let base = Base {
            points,
            labels,
            by_x,
            columns: representatives.len(),
        };
        assert_eq!(base.points.len(), columns * 106);
        let mut base_hasher = blake3::Hasher::new();
        base_hasher.update(b"n53-pair-index-signed-frobenius-base-v1");
        for (point, &(column, coefficient)) in base.points.iter().zip(&base.labels) {
            let (x, y) = point.expect("base point must be affine");
            for value in [x, y, column as u64, coefficient] {
                base_hasher.update(&value.to_le_bytes());
            }
        }
        let base_hash = base_hasher.finalize().to_hex().to_string();
        let base_build_ms = base_started.elapsed().as_secs_f64() * 1000.0;
        maybe_progress(&progress, json!({"phase":"base_complete","policy":policy,
                                        "base_build_ms":base_build_ms}));

        let normal = NormalBasis::new(&gf);
        let n = 53usize;
        let shifted: Vec<Vec<FastPoint>> = geometric_representatives
            .iter()
            .map(|&point| {
                let mut row = Vec::with_capacity(n);
                let [x, y] = point.expect("geometric representative");
                let mut current = (x, y);
                for _ in 0..n {
                    row.push(Some(current));
                    current = (gf.sqr(current.0), gf.sqr(current.1));
                }
                row
            })
            .collect();
        let index_started = Instant::now();
        // The dense pair stream fits in a flat 16-byte record. Sorting the
        // records gives exact, collision-free lookup with less index memory
        // than a hash table at this load factor.
        let mut index: Vec<(u64, PairRecord)> = Vec::with_capacity(
            columns * (columns + 1) * n,
        );
        let mut pair_sums = 0u64;
        for left in 0..columns {
            let p = shifted[left][0];
            for right in left..columns {
                for relative in 0..n {
                    for second_negative in [false, true] {
                        let mut q = shifted[right][relative];
                        if second_negative {
                            q = negative(q);
                        }
                        let Some((x, _)) = fast.add(p, q) else {
                            continue;
                        };
                        pair_sums += 1;
                        let (key, shift) = normal.canonical_sparse(normal.to_normal.apply(x));
                        let record = PairRecord {
                            left: left as u16,
                            right: right as u16,
                            relative: relative as u8,
                            second_negative,
                            canonical_shift: shift as u8,
                        };
                        index.push((key, record));
                    }
                }
            }
            if left % 25 == 24 || left + 1 == columns {
                maybe_progress(&progress, json!({"phase":"index_build",
                    "policy":policy,"left_completed":left+1,"geometric_columns":columns,
                    "pair_sums":pair_sums,"pair_records":index.len(),
                    "elapsed_ms":index_started.elapsed().as_secs_f64()*1000.0}));
            }
        }
        index.sort_unstable_by_key(|entry| entry.0);
        let mut unique = 0usize;
        for read in 0..index.len() {
            if unique == 0 || index[read].0 != index[unique - 1].0 {
                index[unique] = index[read];
                unique += 1;
            }
        }
        let duplicate_keys = index.len() - unique;
        index.truncate(unique);
        let index_ms = index_started.elapsed().as_secs_f64() * 1000.0;
        maybe_progress(&progress, json!({"phase":"index_complete","policy":policy,
            "pair_sums":pair_sums,"distinct_keys":index.len(),"index_ms":index_ms}));

        let online_started = Instant::now();
        let validation_started = Instant::now();
        let target = Some((target_words[0], target_words[1]));
        let (x, y) = target.expect("affine public target");
        let on_curve = (gf.sqr(y) ^ gf.mul(x, y))
            == (gf.mul(gf.sqr(x), x) ^ b);
        assert!(on_curve, "public target must lie on the curve");
        assert_eq!(fast.scalar_mul(target, &BigUint::from(r)), None,
                   "public target must lie in the subgroup");
        let target_query_ns = validation_started.elapsed().as_nanos();

        let pdp_started = Instant::now();
        let mut relation_check_ns = 0u128;
        let mut witness = None;
        let mut lookups = 0u64;
        for &third in &base.points {
            let Some((tx, _)) = fast.add(target, negative(third)) else {
                continue;
            };
            lookups += 1;
            let (key, target_shift) =
                normal.canonical_sparse(normal.to_normal.apply(tx));
            let Ok(position) = index.binary_search_by_key(&key, |entry| entry.0) else {
                continue;
            };
            let pair = index[position].1;
            let check_started = Instant::now();
            let shift = (pair.canonical_shift as usize + n - target_shift as usize) % n;
            let mut first = shifted[pair.left as usize][shift];
            let mut second = shifted[pair.right as usize]
                [(shift + pair.relative as usize) % n];
            if pair.second_negative {
                second = negative(second);
            }
            let t = fast.add(target, negative(third));
            let sum = fast.add(first, second);
            if sum != t {
                first = negative(first);
                second = negative(second);
            }
            assert_eq!(fast.add(first, second), t, "canonical pair recovery");
            assert_eq!(fast.add(t, third), target, "triple witness");
            let indices = [locate(&base, first), locate(&base, second),
                           locate(&base, third)];
            relation_check_ns += check_started.elapsed().as_nanos();
            witness = Some(indices);
            break;
        }
        let target_pdp_ns = pdp_started.elapsed().as_nanos() - relation_check_ns;
        let mut target_descent_ns = 0u128;
        let mut target_recovery_check_ns = 0u128;
        let mut recovered_scalar = None;
        if let Some(indices) = witness {
            let descent_started = Instant::now();
            let mut scalar = 0u64;
            for index in indices {
                let (column, coefficient) = base.labels[index];
                scalar = (scalar + mulmod(coefficient, logs[column], r)) % r;
            }
            target_descent_ns = descent_started.elapsed().as_nanos();
            let replay_started = Instant::now();
            assert_eq!(fast.scalar_mul(generator, &BigUint::from(scalar)), target,
                       "recovered target scalar must replay on the public point");
            target_recovery_check_ns = replay_started.elapsed().as_nanos();
            recovered_scalar = Some(scalar);
        }
        let online_wall_ns = online_started.elapsed().as_nanos();
        let charged_online_ns = target_query_ns + target_pdp_ns + relation_check_ns
            + target_descent_ns + target_recovery_check_ns;
        maybe_progress(&progress, json!({"phase":"target_complete",
            "status":if recovered_scalar.is_some() {"verified_recovery"}
                     else {"no_decomposition"},
            "lookups":lookups,"recovered_scalar":recovered_scalar}));
        let record = json!({"schema_version":1,"policy":policy,
            "index_layout":"sorted-u64-record-v1",
            "field_degree":53,"curve_a":0,"subgroup_order":r,
            "geometric_columns":columns,"independent_log_columns":base.columns,
            "actual_usable_B":base.points.len(),"scanned_x":scanned_x,
            "base_hash_blake3":base_hash,
            "target_point":target_words,"target_input_law":"frozen public point",
            "status":if recovered_scalar.is_some() {"verified_recovery"}
                     else {"no_decomposition"},
            "witness_indices":witness,"lookups":lookups,
            "recovered_scalar":recovered_scalar,
            "pair_sums":pair_sums,"distinct_pair_x_orbit_keys":index.len(),
            "duplicate_pair_keys":duplicate_keys,
            "base_build_ms_exploratory":base_build_ms,
            "index_build_ms_exploratory":index_ms,
            "online_wall_ns_exploratory":online_wall_ns,
            "charged_online_ns_exploratory":charged_online_ns,
            "phase_ns_exploratory":{
                "target_query":target_query_ns,
                "target_PDP":target_pdp_ns,
                "target_relation_check":relation_check_ns,
                "target_descent":target_descent_ns,
                "target_recovery_check":target_recovery_check_ns}});
        fs::write(&args[5], serde_json::to_vec_pretty(&record).expect("serialize record"))
            .expect("write record");
        println!("{}", json!({"status":record["status"],
            "recovered_scalar":recovered_scalar,"lookups":lookups,
            "index_keys":index.len()}));
    }
}

fn main() {
    arithmetic::run();
}
