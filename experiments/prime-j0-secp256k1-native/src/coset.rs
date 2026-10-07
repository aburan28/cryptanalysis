//! Three nearby lattice representatives, scored by complete point-path cost.

use super::*;

struct Selection {
    representatives: Vec<(BigInt, BigInt)>,
    selective: selective::Plan,
    policies: Vec<Vec<mixed_radix::Action>>,
    costs: [usize; 4],
    choice: usize,
}

fn select(scalar: &BigInt) -> Selection {
    let representatives = ranked_representatives(scalar);
    assert_eq!(representatives.len(), 3);
    let selective = selective::recode(representatives[0].0.clone(),
                                      representatives[0].1.clone());
    let policies: Vec<_> = representatives.iter().map(|(a, b)|
        mixed_radix::recode_zero_tau(a.clone(), b.clone())).collect();
    let costs = [selective.total,
                 mixed_radix::source_cost(&policies[0]),
                 mixed_radix::source_cost(&policies[1]),
                 mixed_radix::source_cost(&policies[2])];
    let choice = (0..4).min_by_key(|&index| (costs[index], index)).unwrap();
    Selection { representatives, selective, policies, costs, choice }
}

fn run(base: J, beta: F, selection: &Selection) -> (J, usize, usize) {
    if selection.choice == 0 {
        let seeds = selective::prepare(base, beta, selection.selective.built_mask);
        let (point, counts) = evaluate_mode(&selection.selective.digits, &seeds,
                                             beta, false, true);
        let cost = selection.selective.preparation + 10 * counts.tau_pairs
            + 6 * (counts.tau_steps - 2 * counts.tau_pairs)
            + 11 * counts.mixed_adds + 14 * counts.general_adds
            + 2 * counts.cache_entries;
        assert_eq!(cost, selection.costs[0]);
        (point, counts.exceptional_cached_adds, 0)
    } else {
        let seeds = prepare(base, beta);
        let (point, counts) = mixed_radix::evaluate(
            &selection.policies[selection.choice - 1], &seeds, beta);
        let cost = 83 + 6 * counts.tau_steps + 7 * counts.doubles
            - 2 * counts.tau_pairs + 11 * counts.mixed_adds
            + 14 * counts.general_adds + 2 * counts.cache_entries;
        assert_eq!(cost, selection.costs[selection.choice]);
        (point, counts.exceptional_cached_adds, 9)
    }
}

fn checked_output(point: J, case: &Value) -> String {
    let actual = match point.to_affine() {
        None => "identity".to_owned(),
        Some((x, y)) => format!("{}:{}", fe_hex(x), fe_hex(y)),
    };
    let expected = if case["expected_identity"].as_bool().unwrap_or(false) {
        "identity".to_owned()
    } else {
        format!("{}:{}", case["expected_x_hex"].as_str().expect("expected x"),
                case["expected_y_hex"].as_str().expect("expected y"))
    };
    assert_eq!(actual, expected, "coset scalar output");
    actual
}

fn selective_fingerprint(digits: &[Option<Digit>]) -> u64 {
    const PRIME: u64 = 0x100000001b3;
    let mut value = 0xcbf29ce484222325u64;
    for digit in digits {
        for byte in [1u8, u8::from(digit.is_some())] {
            value = (value ^ u64::from(byte)).wrapping_mul(PRIME);
        }
        if let Some(digit) = digit {
            for byte in digit.a.to_le_bytes().into_iter()
                .chain(digit.b.to_le_bytes())
                .chain([digit.seed as u8])
            {
                value = (value ^ u64::from(byte)).wrapping_mul(PRIME);
            }
        }
    }
    value
}

pub(super) fn check_streams(fixture_path: &str, fingerprint_path: &str) {
    let fixture: Value = serde_json::from_slice(&fs::read(fixture_path).expect("fixture"))
        .expect("fixture JSON");
    let frozen: Value = serde_json::from_slice(&fs::read(fingerprint_path).expect("fingerprints"))
        .expect("fingerprint JSON");
    let name = PathBuf::from(fixture_path).file_name().expect("fixture name")
        .to_str().expect("UTF-8 name").to_owned();
    let panel = frozen["panels"].as_array().expect("panels").iter()
        .find(|item| item["fixture"] == name).expect("matching panel");
    let cases = fixture["cases"].as_array().expect("cases");
    let rows = panel["rows"].as_array().expect("rows");
    assert_eq!(cases.len(), rows.len());
    for (case, row) in cases.iter().zip(rows) {
        assert_eq!(case["index"], row["index"]);
        let scalar = big_from_hex(case["scalar_hex"].as_str().expect("scalar"));
        let selection = select(&scalar);
        let lengths = [selection.selective.digits.len(),
                       selection.policies[0].len(), selection.policies[1].len(),
                       selection.policies[2].len()];
        let fingerprints = [selective_fingerprint(&selection.selective.digits),
                            mixed_radix::action_fingerprint(&selection.policies[0]),
                            mixed_radix::action_fingerprint(&selection.policies[1]),
                            mixed_radix::action_fingerprint(&selection.policies[2])];
        for index in 0..4 {
            assert_eq!(row["lengths"][index].as_u64(), Some(lengths[index] as u64));
            assert_eq!(row["fnv64"][index].as_str(),
                       Some(format!("{:016x}", fingerprints[index]).as_str()));
        }
    }
    println!("{}", serde_json::json!({"verified":true, "fixture":name,
        "cases":cases.len(), "action_stream_checks":4 * cases.len(),
        "cpu_speedup_claim":null}));
}

fn seed_row<'a>(fixture: &'a Value, name: &str, x: &str, y: &str) -> &'a Value {
    fixture["panels"][name]["bases"].as_array().expect("seed bases")
        .iter().find(|row| row["base_x_hex"] == x && row["base_y_hex"] == y)
        .expect("Sage seed row")
}

pub(super) fn check_fixture(fixture_path: &str, seed_path: &str, score_path: &str) {
    let raw = fs::read(fixture_path).expect("fixture");
    let fixture: Value = serde_json::from_slice(&raw).expect("fixture JSON");
    let seed_fixture: Value = serde_json::from_slice(&fs::read(seed_path).expect("seed fixture"))
        .expect("seed JSON");
    let scores: Value = serde_json::from_slice(&fs::read(score_path).expect("scores"))
        .expect("score JSON");
    let name = PathBuf::from(fixture_path).file_name().expect("fixture name")
        .to_str().expect("UTF-8 name").to_owned();
    let panel = scores["panels"].as_array().expect("score panels").iter()
        .find(|item| item["fixture"] == name).expect("matching score panel");
    let cases = fixture["cases"].as_array().expect("cases");
    let rows = panel["rows"].as_array().expect("score rows");
    assert_eq!(cases.len(), rows.len());
    assert_eq!(fixture["beta_hex"], seed_fixture["beta_hex"]);
    let beta = fe_from_hex(fixture["beta_hex"].as_str().expect("beta"));
    let mut total = 0usize;
    let mut choices = [0usize; 4];
    let mut seed_checks = 0usize;
    let mut exceptional_adds = 0usize;
    for (case, row) in cases.iter().zip(rows) {
        assert_eq!(case["index"], row["index"]);
        let scalar = big_from_hex(case["scalar_hex"].as_str().expect("scalar"));
        let selection = select(&scalar);
        assert_eq!(selection.representatives[0].0,
                   big_from_hex(case["short_a_hex"].as_str().expect("short a")));
        assert_eq!(selection.representatives[0].1,
                   big_from_hex(case["short_b_hex"].as_str().expect("short b")));
        let paths = row["paths"].as_array().expect("source paths");
        assert_eq!(paths.len(), 4);
        for index in 0..4 {
            assert_eq!(paths[index]["total_M_plus_S"].as_u64(),
                       Some(selection.costs[index] as u64));
            if index > 0 {
                assert_eq!(selection.representatives[index - 1].0,
                           big_from_hex(paths[index]["a_hex"].as_str().expect("a")));
                assert_eq!(selection.representatives[index - 1].1,
                           big_from_hex(paths[index]["b_hex"].as_str().expect("b")));
            }
        }
        assert_eq!(row["selected_path_index"].as_u64(), Some(selection.choice as u64));
        assert_eq!(row["selected_M_plus_S"].as_u64(),
                   Some(selection.costs[selection.choice] as u64));
        let x = case["base_x_hex"].as_str().expect("base x");
        let y = case["base_y_hex"].as_str().expect("base y");
        let base = J::affine(fe_from_hex(x), fe_from_hex(y));
        if selection.choice == 0 {
            let seeds = selective::prepare(base, beta, selection.selective.built_mask);
            let expected = seed_row(&seed_fixture, &name, x, y);
            for (index, seed) in seeds.iter().enumerate() {
                if selection.selective.built_mask & (1 << index) == 0 { continue; }
                let (sx, sy) = seed.to_affine().expect("seed nonidentity");
                assert_eq!(fe_hex(sx), expected["seeds"][index][0].as_str().expect("seed x"));
                assert_eq!(fe_hex(sy), expected["seeds"][index][1].as_str().expect("seed y"));
                seed_checks += 1;
            }
        } else {
            let seeds = prepare(base, beta);
            for (seed, expected) in seeds.iter().zip(case["seed_affine"].as_array().expect("seeds")) {
                let (sx, sy) = seed.to_affine().expect("seed nonidentity");
                assert_eq!(fe_hex(sx), expected[0].as_str().expect("seed x"));
                assert_eq!(fe_hex(sy), expected[1].as_str().expect("seed y"));
                seed_checks += 1;
            }
        }
        let (point, exceptional, _) = run(base, beta, &selection);
        checked_output(point, case);
        choices[selection.choice] += 1;
        exceptional_adds += exceptional;
        total += selection.costs[selection.choice];
    }
    assert_eq!(panel["selected_total"].as_u64(), Some(total as u64));
    println!("{}", serde_json::json!({"verified":true, "fixture":name,
        "cases":cases.len(), "choices":choices, "seed_checks":seed_checks,
        "output_checks":cases.len(), "selected_M_plus_S":total,
        "exceptional_cached_adds":exceptional_adds, "cpu_speedup_claim":null}));
}

pub(super) fn benchmark_case(fixture_path: &str, index: usize, timed: bool) {
    let fixture: Value = serde_json::from_slice(&fs::read(fixture_path).expect("fixture"))
        .expect("fixture JSON");
    let case = &fixture["cases"].as_array().expect("cases")[index];
    let x = case["base_x_hex"].as_str().expect("base x");
    let y = case["base_y_hex"].as_str().expect("base y");
    let scalar_hex = case["scalar_hex"].as_str().expect("scalar");
    let beta = fe_from_hex(fixture["beta_hex"].as_str().expect("beta"));
    LazyLock::force(&LATTICE);
    LazyLock::force(&DIGIT_TABLE);
    LazyLock::force(&LINKED_DIGIT_TABLE);
    let start = Instant::now();
    let scalar = big_from_hex(scalar_hex);
    let base = J::affine(fe_from_hex(x), fe_from_hex(y));
    let selection = select(&scalar);
    let (point, exceptional, _) = run(base, beta, &selection);
    let actual = checked_output(point, case);
    let elapsed_ms = start.elapsed().as_secs_f64() * 1000.0;
    if timed {
        println!("online_ms={elapsed_ms:.6} verified=1 curve=secp256k1 base_x={x} base_y={y} scalar={scalar_hex} point={actual} mode=coset choice={} source_M_plus_S={} exceptional_cached_adds={exceptional}",
                 selection.choice, selection.costs[selection.choice]);
    } else {
        println!("verified=1 curve=secp256k1 base_x={x} base_y={y} scalar={scalar_hex} point={actual} mode=coset choice={} source_M_plus_S={} exceptional_cached_adds={exceptional}",
                 selection.choice, selection.costs[selection.choice]);
    }
}
