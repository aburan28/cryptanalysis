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
        assert_eq!(args.len(), 5, "usage: <seed|closure> <geometric_columns> <query_count> <out.json>");
        let policy = args[1].as_str();
        assert!(policy == "seed" || policy == "closure");
        let columns: usize = args[2].parse().expect("columns");
        let query_count: usize = args[3].parse().expect("query count");
        assert!(columns > 0 && query_count > 0);
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
        let mut index: HashMap<u64, PairRecord> = HashMap::with_capacity(
            columns * (columns + 1) * n,
        );
        let mut pair_sums = 0u64;
        let mut duplicate_keys = 0u64;
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
                        if index.insert(key, record).is_some() {
                            duplicate_keys += 1;
                        }
                    }
                }
            }
            if left % 25 == 24 || left + 1 == columns {
                maybe_progress(&progress, json!({"phase":"index_build",
                    "policy":policy,"left_completed":left+1,"geometric_columns":columns,
                    "pair_sums":pair_sums,"distinct_keys":index.len(),
                    "elapsed_ms":index_started.elapsed().as_secs_f64()*1000.0}));
            }
        }
        let index_ms = index_started.elapsed().as_secs_f64() * 1000.0;
        maybe_progress(&progress, json!({"phase":"index_complete","policy":policy,
            "pair_sums":pair_sums,"distinct_keys":index.len(),"index_ms":index_ms}));

        let query_started = Instant::now();
        let mut random_state = 20261008u64;
        let mut echelon = Echelon {
            r,
            columns: base.columns,
            pivots: vec![None; base.columns],
            rank: 0,
        };
        let mut hits = 0usize;
        let mut group_checks = 0u64;
        let mut lookups = 0u64;
        let mut query_rows = Vec::with_capacity(query_count);
        for query_index in 0..query_count {
            let scalar = 1 + splitmix64(&mut random_state) % (r - 1);
            let target = fast.scalar_mul(generator, &BigUint::from(scalar));
            assert!(target.is_some());
            let mut witness = None;
            let mut query_lookups = 0u64;
            for &third in &base.points {
                let Some((tx, _)) = fast.add(target, negative(third)) else {
                    continue;
                };
                query_lookups += 1;
                let (key, target_shift) =
                    normal.canonical_sparse(normal.to_normal.apply(tx));
                let Some(pair) = index.get(&key).copied() else {
                    continue;
                };
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
                group_checks += 1;
                assert_eq!(fast.add(first, second), t, "canonical pair recovery");
                assert_eq!(fast.add(t, third), target, "triple witness");
                let indices = [locate(&base, first), locate(&base, second),
                               locate(&base, third)];
                witness = Some(indices);
                break;
            }
            lookups += query_lookups;
            let mut novel = false;
            if let Some(indices) = witness {
                hits += 1;
                let mut row = vec![0u64; base.columns + 1];
                for index in indices {
                    let (column, coefficient) = base.labels[index];
                    row[column] = (row[column] + coefficient) % r;
                }
                row[base.columns] = scalar;
                novel = echelon.insert(row);
            }
            query_rows.push(json!({"query_index":query_index,"scalar":scalar,
                "target_point":target.map(|(x,y)| [x,y]),
                "lookups":query_lookups,"hit":witness.is_some(),
                "novel_row":novel,"witness_indices":witness}));
            if (query_index + 1) % 8 == 0 || query_index + 1 == query_count {
                maybe_progress(&progress, json!({"phase":"query",
                    "policy":policy,"queries_completed":query_index+1,
                    "hits":hits,"rank":echelon.rank,"lookups":lookups}));
            }
        }
        let query_ms = query_started.elapsed().as_secs_f64() * 1000.0;
        let record = json!({"schema_version":1,"policy":policy,
            "field_degree":53,"curve_a":0,"subgroup_order":r,
            "geometric_columns":columns,"independent_log_columns":base.columns,
            "actual_usable_B":base.points.len(),"scanned_x":scanned_x,
            "base_hash_blake3":base_hash,
            "query_law":"SplitMix64 word reduced modulo r-1, plus one",
            "query_seed":20261008u64,"query_count":query_count,
            "verified_hits":hits,"novel_rows":echelon.rank,
            "rank":echelon.rank,"lookups":lookups,"group_checks":group_checks,
            "pair_sums":pair_sums,"distinct_pair_x_orbit_keys":index.len(),
            "duplicate_pair_keys":duplicate_keys,
            "base_build_ms_exploratory":base_build_ms,
            "index_build_ms_exploratory":index_ms,
            "query_ms_exploratory":query_ms,
            "rows":query_rows});
        fs::write(&args[4], serde_json::to_vec_pretty(&record).expect("serialize record"))
            .expect("write record");
        println!("{}", json!({"policy":policy,"hits":hits,"rank":echelon.rank,
                                  "index_keys":index.len()}));
    }
}

fn main() {
    arithmetic::run();
}
