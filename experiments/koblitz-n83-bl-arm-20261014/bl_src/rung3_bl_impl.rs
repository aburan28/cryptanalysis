    // -----------------------------------------------------------------------
    // Bernstein–Lange arm for strong rung 3 (cryptanalysis
    // experiments/koblitz-n83-bl-arm-20261014). Inserted by
    // restore_sources.py into `mod wide` of a copy of crypto 770f6a69's
    // examples/koblitz_rho_batch_ks_strong_online.rs; the substitutions it
    // makes to `run` (R3_SUBS there) are: the jump table may come from
    // KIC_BL_JUMP_SEED instead of the batch seed, a precomputed table may be
    // preloaded before the target is built (each entry a trail with b = 0 of
    // fixture 0, so `resolve_distinguished_point` solves a hit unchanged),
    // the successful collision's stored b is recorded, and one extra JSON
    // line is printed. With neither variable set, `run` is the frozen file's.
    //
    // KIC_BL_MODE=precompute walks from c·G with the same jumps, partition,
    // canonicalization (rung 3: FastCanon128), distinguished-point rule,
    // lanes and batched step as `run`'s rung-3 loop; the step block is that
    // loop's. KIC_BL_MODE=verify-table checks a table record by record.
    // -----------------------------------------------------------------------

    include!("bl_table_io.rs");

    thread_local! {
        static BL_HIT_B: std::cell::Cell<u64> = const { std::cell::Cell::new(u64::MAX) };
    }

    fn bl_env_u64(name: &str) -> Option<u64> {
        std::env::var(name)
            .ok()
            .map(|v| v.parse().unwrap_or_else(|_| panic!("{name} must be an integer")))
    }

    /// The batch seed the jump table is drawn from.
    fn bl_jump_batch_seed(batch_seed: u64) -> u64 {
        bl_env_u64("KIC_BL_JUMP_SEED").unwrap_or(batch_seed)
    }

    /// Preload KIC_BL_TABLE_IN (BLAKE3 checked against KIC_BL_TABLE_BLAKE3)
    /// as trails of fixture 0 with b = 0. Returns (milliseconds, entries).
    fn bl_preload(table: &mut HashMap<(u8, u128, u128), Trail>, fixtures: u32) -> (f64, usize) {
        let Ok(path) = std::env::var("KIC_BL_TABLE_IN") else {
            return (0.0, 0);
        };
        assert_eq!(fixtures, 1, "a precomputed table serves one fixture per process");
        assert!(
            std::env::var("KIC_BL_JUMP_SEED").is_ok(),
            "a precomputed table needs the jump seed it was built with (KIC_BL_JUMP_SEED)"
        );
        let expected = std::env::var("KIC_BL_TABLE_BLAKE3").expect("KIC_BL_TABLE_BLAKE3 is required");
        let started = Instant::now();
        let (rows, _, _) = bl_read_table(&path, Some(&expected));
        table.reserve(rows.len() + (1 << 16));
        for (x, y, log) in rows {
            table.insert(
                (1, x, y),
                Trail {
                    a: log,
                    b: 0,
                    target: 0,
                },
            );
        }
        (started.elapsed().as_secs_f64() * 1000.0, table.len())
    }

    pub fn bl_main(args: &[String]) {
        let process_started = Instant::now();
        let mode = std::env::var("KIC_BL_MODE").unwrap();
        let n: u32 = args[1].parse().unwrap();
        let a: u8 = args[2].parse().unwrap();
        assert!((64..=127).contains(&n), "the rung-3 BL arm is the wide path, 64 <= n <= 127");
        let rung = bl_env_u64("KIC_RHO_RUNG").unwrap_or(3);
        assert_eq!(rung, 3, "the BL arm is built on rung 3 (lockstep lanes)");
        let lanes_n = bl_env_u64("KIC_RHO_LANES").unwrap_or(32) as usize;
        let dp_bits = bl_env_u64("KIC_RHO_DP_BITS").unwrap_or(8) as u32;
        assert!(dp_bits < 32 && lanes_n > 0);
        let curve = KoblitzCurve::new(a, n).expect("frozen exact rung must construct");
        let gf = Gf2_128::new(&curve.curve.irreducible);
        let nb = NormalBasis128::new(&gf);
        let f = Field128 {
            gf: &gf,
            nb: &nb,
            a: u128::from(a),
        };
        let modulus = curve.subgroup_order.to_u64_digits()[0];
        let lambda = curve.lambda.to_u64_digits()[0];
        let automorphisms = signed_automorphism_size(lambda, modulus, n);
        let generator = match curve.generator() {
            BinaryPoint::Affine { x, y } => WPoint::Affine {
                x: gf.from_element(&x),
                y: gf.from_element(&y),
            },
            BinaryPoint::Infinity => WPoint::Infinity,
        };
        let canon = Canon128::Fast(FastCanon128::new(&nb, lambda, modulus));
        let identity = json!({"n": n, "a": a, "subgroup_order": modulus.to_string(), "lambda": lambda.to_string(),
            "automorphism_size": automorphisms, "field": "library Gf2_128",
            "walk": "strong rung 3, koblitz_rho_batch_ks_strong_online wide path (crypto 770f6a69)",
            "rho_params": {"rung": 3, "lanes": lanes_n, "dp_bits": dp_bits}});
        let dp_mask = (1u64 << dp_bits) - 1;
        match mode.as_str() {
            "precompute" => {
                let jump_seed = bl_env_u64("KIC_BL_JUMP_SEED").expect("KIC_BL_JUMP_SEED is required");
                let precompute_seed =
                    bl_env_u64("KIC_BL_PRECOMPUTE_SEED").expect("KIC_BL_PRECOMPUTE_SEED is required");
                let mut charges = Charges::default();
                let jump_digest =
                    blake3::hash(format!("KIC-KS-BATCH-JUMPS-v1|{n}|{a}|{}", jump_seed).as_bytes());
                let mut jump_rng = StdRng::seed_from_u64(u64::from_le_bytes(
                    jump_digest.as_bytes()[..8].try_into().unwrap(),
                ));
                let jumps: Vec<WJump> = (0..JUMPS)
                    .map(|_| loop {
                        let s = jump_rng.gen_range(1..modulus);
                        charges.scalar_multiplications += 1;
                        let point = scalar_mul(&f, generator, s);
                        if point != WPoint::Infinity {
                            break WJump { point, a: s, b: 0 };
                        }
                    })
                    .collect();
                let setup_ms = process_started.elapsed().as_secs_f64() * 1000.0;
                let mut stopper = BlStop::from_env_or_args(
                    std::env::var("KIC_BL_BUDGET_MS").ok().map(|v| v.parse().expect("KIC_BL_BUDGET_MS")),
                    bl_env_u64("KIC_BL_STOP_STEPS"),
                    bl_env_u64("KIC_BL_STOP_ROUNDS"),
                );
                let start_digest =
                    blake3::hash(format!("KIC-BL-PRECOMPUTE-v1|{n}|{a}|{precompute_seed}").as_bytes());
                let mut rng = StdRng::seed_from_u64(u64::from_le_bytes(
                    start_digest.as_bytes()[..8].try_into().unwrap(),
                ));
                let walk_cap = 8u64 << dp_bits;
                let mut table: HashMap<(u8, u128, u128), u64> = HashMap::new();
                // The budget clock and the reported precompute interval are one clock.
                stopper.started = Instant::now();
                let started = stopper.started;
                let stride_a = rng.gen_range(1..modulus);
                let stride = scalar_mul(&f, generator, stride_a);
                let mut cursor_a = rng.gen_range(0..modulus);
                let mut cursor = scalar_mul(&f, generator, cursor_a);
                charges.scalar_multiplications += 2;
                let (mut rounds, mut steps, mut walks, mut fruitless, mut capped) = (0u64, 0u64, 0u64, 0u64, 0u64);
                let (mut new_points, mut duplicate_points, mut covered_points) = (0u64, 0u64, 0u64);
                let (mut duplicate_walk_steps, mut abandoned_walk_steps, mut infinity_points) = (0u64, 0u64, 0u64);
                let mut lanes: Vec<Lane> = (0..lanes_n)
                    .map(|_| Lane {
                        state: WState {
                            point: WPoint::Infinity,
                            a: 0,
                            b: 0,
                        },
                        previous: [WPoint::Infinity; 4],
                        length: 0,
                        live: false,
                    })
                    .collect();
                let mut denominators: Vec<u128> = vec![0; lanes_n];
                let mut jump_index: Vec<usize> = vec![0; lanes_n];
                let mut active: Vec<usize> = Vec::with_capacity(lanes_n);
                let mut scratch: Vec<u128> = Vec::new();
                while !stopper.reached(rounds, steps) {
                    rounds += 1;
                    for lane in lanes.iter_mut().filter(|lane| !lane.live) {
                        loop {
                            walks += 1;
                            let start = cursor;
                            let start_a = cursor_a;
                            cursor = point_add(&f, cursor, stride);
                            cursor_a = (cursor_a + stride_a) % modulus;
                            charges.group_additions += 1;
                            if start == WPoint::Infinity {
                                continue;
                            }
                            lane.state = canon.apply(
                                WState {
                                    point: start,
                                    a: start_a,
                                    b: 0,
                                },
                                &mut charges,
                            );
                            lane.previous = [WPoint::Infinity; 4];
                            lane.length = 0;
                            lane.live = true;
                            break;
                        }
                    }
                    for lane in lanes.iter_mut() {
                        if lane.live && dp_hash(lane.state.point) & dp_mask == 0 {
                            lane.live = false;
                            if lane.state.point == WPoint::Infinity {
                                infinity_points += 1;
                                continue;
                            }
                            let key = raw_key(lane.state.point);
                            if let std::collections::hash_map::Entry::Vacant(slot) = table.entry(key) {
                                slot.insert(lane.state.a);
                                new_points += 1;
                                covered_points += lane.length + 1;
                            } else {
                                duplicate_points += 1;
                                duplicate_walk_steps += lane.length;
                            }
                        }
                    }
                    // The rung-3 step block of `run`.
                    active.clear();
                    for (li, lane) in lanes.iter().enumerate() {
                        if !lane.live {
                            continue;
                        }
                        let ji = raw_partition(lane.state.point);
                        charges.partition_hashes += 1;
                        let j = active.len();
                        jump_index[j] = ji;
                        denominators[j] = match (lane.state.point, jumps[ji].point) {
                            (WPoint::Affine { x: x1, .. }, WPoint::Affine { x: x2, .. }) => {
                                x1 ^ x2
                            }
                            _ => 0,
                        };
                        active.push(li);
                    }
                    gf.batch_inv(&mut denominators[..active.len()], &mut scratch);
                    for (j, &li) in active.iter().enumerate() {
                        let lane = &mut lanes[li];
                        let jump = &jumps[jump_index[j]];
                        let sum = match (lane.state.point, jump.point) {
                            (WPoint::Affine { x: x1, y: y1 }, WPoint::Affine { x: x2, y: y2 })
                                if denominators[j] != 0 =>
                            {
                                let slope = f.mul(y1 ^ y2, denominators[j]);
                                add_with_slope(&f, x1, y1, x2, slope)
                            }
                            _ => point_add(&f, lane.state.point, jump.point),
                        };
                        let next = WState {
                            point: sum,
                            a: (lane.state.a + jump.a) % modulus,
                            b: lane.state.b,
                        };
                        charges.group_additions += 1;
                        let next = canon.apply(next, &mut charges);
                        steps += 1;
                        lane.length += 1;
                        if next.point == lane.state.point || lane.previous.contains(&next.point) {
                            fruitless += 1;
                            abandoned_walk_steps += lane.length;
                            lane.live = false;
                            continue;
                        }
                        if lane.length > walk_cap {
                            capped += 1;
                            abandoned_walk_steps += lane.length;
                            lane.live = false;
                            continue;
                        }
                        lane.previous = [
                            lane.state.point,
                            lane.previous[0],
                            lane.previous[1],
                            lane.previous[2],
                        ];
                        lane.state = next;
                    }
                }
                let precompute_ms = started.elapsed().as_secs_f64() * 1000.0;
                let rows: Vec<(u128, u128, u64)> = table.iter().map(|(&(_, x, y), &log)| (x, y, log)).collect();
                drop(table);
                let out = std::env::var("KIC_BL_TABLE_OUT").expect("KIC_BL_TABLE_OUT is required");
                let write_started = Instant::now();
                let (entries, blake3_hex) = bl_write_table(&out, rows);
                let write_ms = write_started.elapsed().as_secs_f64() * 1000.0;
                println!("{}", json!({
                    "kind": "bl_precompute", "family": "rung3", "identity": identity,
                    "bl_jump_seed": jump_seed, "precompute_seed": precompute_seed,
                    "stop_rule": {"budget_ms": stopper.budget_ms, "stop_steps": stopper.stop_steps, "stop_rounds": stopper.stop_rounds},
                    "setup_ms_excluded": setup_ms, "precompute_ms": precompute_ms, "table_write_ms": write_ms,
                    "rounds": rounds, "steps": steps, "walks": walks, "fruitless": fruitless, "escapes": 0, "capped": capped,
                    "new_points": new_points, "duplicate_points": duplicate_points, "covered_points": covered_points,
                    "duplicate_walk_steps": duplicate_walk_steps, "abandoned_walk_steps": abandoned_walk_steps,
                    "group_additions": charges.group_additions, "scalar_multiplications": charges.scalar_multiplications,
                    "infinity_points": infinity_points,
                    "table_entries": entries, "table_blake3": blake3_hex, "record_bytes": BL_RECORD_BYTES,
                    "ns_per_step": if steps > 0 { precompute_ms * 1e6 / steps as f64 } else { 0.0 },
                    "peak_rss_bytes": bl_peak_rss_bytes(),
                }));
            }
            "verify-table" => {
                let path = std::env::var("KIC_BL_TABLE_IN").expect("KIC_BL_TABLE_IN is required");
                let expected = std::env::var("KIC_BL_TABLE_BLAKE3").ok();
                let threads = bl_env_u64("KIC_BL_VERIFY_THREADS").unwrap_or(1).max(1) as usize;
                let (rows, digest, read_ms) = bl_read_table(&path, expected.as_deref());
                let started = Instant::now();
                let chunk = rows.len().div_ceil(threads).max(1);
                let (f, canon) = (&f, &canon);
                let bad: Vec<(usize, &'static str)> = std::thread::scope(|scope| {
                    let handles: Vec<_> = rows
                        .chunks(chunk)
                        .enumerate()
                        .map(|(c, part)| {
                            scope.spawn(move || {
                                let mut charges = Charges::default();
                                let mut bad = Vec::new();
                                for (i, &(x, y, log)) in part.iter().enumerate() {
                                    let index = c * chunk + i;
                                    let point = WPoint::Affine { x, y };
                                    let fixed = canon.apply(WState { point, a: 1, b: 0 }, &mut charges);
                                    if !(log > 0 && log < modulus) {
                                        bad.push((index, "log out of range"));
                                    } else if dp_hash(point) & dp_mask != 0 {
                                        bad.push((index, "not distinguished"));
                                    } else if fixed.point != point {
                                        bad.push((index, "not canonical"));
                                    } else if scalar_mul(f, generator, log) != point {
                                        bad.push((index, "[a]G differs from the point"));
                                    }
                                }
                                bad
                            })
                        })
                        .collect();
                    handles.into_iter().flat_map(|h| h.join().unwrap()).collect()
                });
                let ok = bad.is_empty();
                println!("{}", json!({
                    "kind": "bl_table_verification", "family": "rung3", "identity": identity, "dp_bits": dp_bits,
                    "entries": rows.len(), "blake3": digest, "read_ms": read_ms, "threads": threads,
                    "verify_ms": started.elapsed().as_secs_f64() * 1000.0,
                    "checks": ["log in [1, r)", "distinguished under the walk's dp_hash", "own signed-Frobenius representative (FastCanon128)", "[a]G equals the stored point"],
                    "bad": bad.len(), "bad_first": bad.iter().take(20).map(|(i, why)| json!([i, why])).collect::<Vec<_>>(),
                    "status": if ok { "PASS" } else { "FAIL" },
                }));
                if !ok {
                    std::process::exit(3);
                }
            }
            other => panic!("unknown KIC_BL_MODE {other}"),
        }
    }

