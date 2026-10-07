//! Conditional radix-two exits from the fixed width-four tau digit chain.

use super::*;

#[derive(Clone, Copy, Eq, PartialEq)]
enum Radix {
    Tau,
    Two,
}

#[derive(Clone, Copy)]
struct Action {
    radix: Radix,
    digit: Option<Digit>,
}

#[derive(Default)]
struct Counts {
    tau_steps: usize,
    tau_pairs: usize,
    doubles: usize,
    mixed_adds: usize,
    general_adds: usize,
    cache_entries: usize,
    exceptional_cached_adds: usize,
}

fn recode(mut a: BigInt, mut b: BigInt) -> Vec<Action> {
    #[cfg(debug_assertions)]
    let original = (a.clone(), b.clone());
    let mut actions = Vec::new();
    while !a.is_zero() || !b.is_zero() {
        assert!(actions.len() < 512, "mixed-radix expansion did not terminate");
        if signed_residue(&a, 2) == 0 && signed_residue(&b, 2) == 0 {
            actions.push(Action { radix: Radix::Two, digit: None });
            a /= 2;
            b /= 2;
        } else {
            let digit = if signed_residue(&a, 3) == 0 {
                None
            } else {
                let entry = DIGIT_TABLE[signed_residue(&a, 9)][signed_residue(&b, 9)]
                    .expect("original width-four residue");
                a -= entry.a;
                b -= entry.b;
                Some(entry)
            };
            assert_eq!(signed_residue(&a, 3), 0);
            actions.push(Action { radix: Radix::Tau, digit });
            (a, b) = (&a + &b, -a / 3);
        }
    }
    assert!(actions.last().is_some_and(|action| action.digit.is_some()));
    #[cfg(debug_assertions)]
    {
        let (mut x, mut y) = (BigInt::ZERO, BigInt::ZERO);
        for action in actions.iter().rev() {
            (x, y) = if action.radix == Radix::Two {
                (2 * x, 2 * y)
            } else {
                (-3 * &y, &x + 3 * &y)
            };
            if let Some(digit) = action.digit {
                x += digit.a;
                y += digit.b;
            }
        }
        assert_eq!((x, y), original);
    }
    actions
}

fn pair_count(actions: &[Action]) -> usize {
    let mut index = actions.len() as isize - 2;
    let mut count = 0;
    while index >= 0 {
        let position = index as usize;
        if position > 0 && actions[position].radix == Radix::Tau
            && actions[position].digit.is_none()
            && actions[position - 1].radix == Radix::Tau
        {
            count += 1;
            index -= 2;
        } else {
            index -= 1;
        }
    }
    count
}

fn source_cost(actions: &[Action]) -> usize {
    let tau_steps = actions[..actions.len() - 1].iter()
        .filter(|action| action.radix == Radix::Tau).count();
    let doubles = actions[..actions.len() - 1].iter()
        .filter(|action| action.radix == Radix::Two).count();
    let pairs = pair_count(actions);
    let mut charged = Vec::new();
    for action in actions {
        if let Some(digit) = action.digit {
            charged.push(digit.seed);
        }
    }
    charged.pop();
    let mixed = charged.iter().filter(|&&seed| seed == 0).count();
    let general = charged.len() - mixed;
    let mut cached = [false; 9];
    for seed in charged {
        if seed > 0 {
            cached[seed] = true;
        }
    }
    let cache = cached.into_iter().filter(|used| *used).count();
    83 + 6 * tau_steps + 7 * doubles - 2 * pairs
        + 11 * mixed + 14 * general + 2 * cache
}

fn action_fingerprint(actions: &[Action]) -> u64 {
    const PRIME: u64 = 0x100000001b3;
    let mut value = 0xcbf29ce484222325u64;
    for action in actions {
        let radix = if action.radix == Radix::Tau { 1u8 } else { 2u8 };
        for byte in [radix, u8::from(action.digit.is_some())] {
            value = (value ^ u64::from(byte)).wrapping_mul(PRIME);
        }
        if let Some(digit) = action.digit {
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

pub(super) fn check_action_fingerprints(fixture_path: &str, fingerprint_path: &str) {
    let fixture: Value = serde_json::from_slice(&fs::read(fixture_path).expect("fixture"))
        .expect("fixture JSON");
    let expected: Value = serde_json::from_slice(&fs::read(fingerprint_path).expect("fingerprints"))
        .expect("fingerprint JSON");
    let name = PathBuf::from(fixture_path).file_name().expect("fixture name")
        .to_str().expect("UTF-8 name").to_owned();
    let panel = expected["panels"].as_array().expect("panels").iter()
        .find(|item| item["fixture"] == name).expect("matching panel");
    let cases = fixture["cases"].as_array().expect("cases");
    let rows = panel["rows"].as_array().expect("rows");
    assert_eq!(cases.len(), rows.len());
    LazyLock::force(&LATTICE);
    LazyLock::force(&DIGIT_TABLE);
    for (case, row) in cases.iter().zip(rows) {
        assert_eq!(case["index"], row["index"]);
        let scalar = big_from_hex(case["scalar_hex"].as_str().expect("scalar"));
        let (a, b) = short_representative(&scalar);
        let actions = recode(a, b);
        assert_eq!(row["actions"].as_u64(), Some(actions.len() as u64));
        assert_eq!(row["fnv64"].as_str(), Some(format!("{:016x}", action_fingerprint(&actions)).as_str()));
    }
    println!("{}", serde_json::json!({"verified": true, "fixture": name,
        "action_stream_checks": cases.len(), "cpu_speedup_claim": null}));
}

fn evaluate(actions: &[Action], seeds: &[J; 9], beta: F) -> (J, Counts) {
    let mut counts = Counts::default();
    let mut images = [[J::identity(); 3]; 9];
    for seed in 0..9 {
        images[seed] = orbit(seeds[seed], beta);
    }
    let mut cache: [Option<(F, F)>; 9] = [None; 9];
    for action in actions.iter().take(actions.len() - 1) {
        if let Some(digit) = action.digit {
            if digit.seed > 0 && cache[digit.seed].is_none() {
                let z = seeds[digit.seed].z;
                let z2 = z.sqr();
                cache[digit.seed] = Some((z2, z2.mul(&z)));
                counts.cache_entries += 1;
            }
        }
    }
    let pairs = pair_count(actions);
    let mut gauge = (3 - (2 * pairs) % 3) % 3;
    let one_minus_beta = F::ONE.sub(&beta);
    let mut accumulator = J::identity();
    let mut index = actions.len() as isize - 1;
    while index >= 0 {
        let action = actions[index as usize];
        let pair = !accumulator.is_identity() && action.radix == Radix::Tau
            && action.digit.is_none() && index > 0
            && actions[index as usize - 1].radix == Radix::Tau;
        let digit = if pair {
            index -= 1;
            Some(actions[index as usize].digit)
        } else {
            None
        }.unwrap_or(action.digit);
        if !accumulator.is_identity() {
            if pair {
                accumulator = accumulator.tau_pair_cheap();
                gauge = (gauge + 2) % 3;
                counts.tau_steps += 2;
                counts.tau_pairs += 1;
            } else if action.radix == Radix::Tau {
                accumulator = accumulator.tau(one_minus_beta);
                counts.tau_steps += 1;
            } else {
                accumulator = accumulator.double();
                counts.doubles += 1;
            }
        }
        if let Some(digit) = digit {
            let mut point = images[digit.seed][(digit.power + gauge) % 3];
            if digit.sign < 0 {
                point = point.neg();
            }
            if accumulator.is_identity() {
                accumulator = point;
            } else if digit.seed == 0 {
                assert_eq!(point.z, F::ONE);
                accumulator = accumulator.add_mixed(point.x, point.y);
                counts.mixed_adds += 1;
            } else {
                let (z2, z3) = cache[digit.seed].expect("cached seed powers");
                let (sum, exceptional) = accumulator.add_cached(point, z2, z3);
                accumulator = sum;
                counts.general_adds += 1;
                counts.exceptional_cached_adds += usize::from(exceptional);
            }
        }
        index -= 1;
    }
    assert_eq!(counts.tau_pairs, pairs);
    assert_eq!(gauge, 0);
    (accumulator, counts)
}

fn seed_row<'a>(fixture: &'a Value, name: &str, x: &str, y: &str) -> &'a Value {
    fixture["panels"][name]["bases"].as_array().expect("seed bases")
        .iter().find(|row| row["base_x_hex"] == x && row["base_y_hex"] == y)
        .expect("Sage seed row")
}

pub(super) fn check_fixture(fixture_path: &str, seed_path: &str, score_path: &str) {
    let fixture: Value = serde_json::from_slice(&fs::read(fixture_path).expect("fixture"))
        .expect("fixture JSON");
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
    LazyLock::force(&LATTICE);
    LazyLock::force(&DIGIT_TABLE);
    LazyLock::force(&LINKED_DIGIT_TABLE);
    let mut total = 0usize;
    let mut selected_radix_two = 0usize;
    let mut seed_checks = 0usize;
    let mut exceptional_adds = 0usize;
    for (case, row) in cases.iter().zip(rows) {
        assert_eq!(case["index"], row["index"]);
        let scalar = big_from_hex(case["scalar_hex"].as_str().expect("scalar"));
        let (a, b) = short_representative(&scalar);
        assert_eq!(a, big_from_hex(case["short_a_hex"].as_str().expect("short a")));
        assert_eq!(b, big_from_hex(case["short_b_hex"].as_str().expect("short b")));
        let actions = recode(a.clone(), b.clone());
        let greedy_cost = source_cost(&actions);
        let selective = selective::recode(a, b);
        let choose_greedy = greedy_cost < selective.total;
        assert_eq!(row["greedy_M_plus_S"].as_u64(), Some(greedy_cost as u64));
        assert_eq!(row["selective_M_plus_S"].as_u64(), Some(selective.total as u64));
        assert_eq!(row["selected"].as_str(), Some(if choose_greedy { "radix_two" } else { "selective" }));
        let chosen_cost = if choose_greedy { greedy_cost } else { selective.total };
        assert_eq!(row["selected_M_plus_S"].as_u64(), Some(chosen_cost as u64));
        let x = case["base_x_hex"].as_str().expect("base x");
        let y = case["base_y_hex"].as_str().expect("base y");
        let base = J::affine(fe_from_hex(x), fe_from_hex(y));
        let (point, exceptional) = if choose_greedy {
            selected_radix_two += 1;
            let seeds = prepare(base, beta);
            for (seed, expected) in seeds.iter().zip(case["seed_affine"].as_array().expect("original seeds")) {
                let (sx, sy) = seed.to_affine().expect("seed nonidentity");
                assert_eq!(fe_hex(sx), expected[0].as_str().expect("seed x"));
                assert_eq!(fe_hex(sy), expected[1].as_str().expect("seed y"));
                seed_checks += 1;
            }
            let (point, counts) = evaluate(&actions, &seeds, beta);
            let recount = 83 + 6 * counts.tau_steps + 7 * counts.doubles
                - 2 * counts.tau_pairs + 11 * counts.mixed_adds
                + 14 * counts.general_adds + 2 * counts.cache_entries;
            assert_eq!(recount, greedy_cost);
            (point, counts.exceptional_cached_adds)
        } else {
            let seeds = selective::prepare(base, beta, selective.built_mask);
            let expected = seed_row(&seed_fixture, &name, x, y);
            for (index, seed) in seeds.iter().enumerate() {
                if selective.built_mask & (1 << index) == 0 { continue; }
                let (sx, sy) = seed.to_affine().expect("seed nonidentity");
                assert_eq!(fe_hex(sx), expected["seeds"][index][0].as_str().expect("seed x"));
                assert_eq!(fe_hex(sy), expected["seeds"][index][1].as_str().expect("seed y"));
                seed_checks += 1;
            }
            let (point, counts) = evaluate_mode(&selective.digits, &seeds, beta, false, true);
            let recount = selective.preparation + 10 * counts.tau_pairs
                + 6 * (counts.tau_steps - 2 * counts.tau_pairs)
                + 11 * counts.mixed_adds + 14 * counts.general_adds
                + 2 * counts.cache_entries;
            assert_eq!(recount, selective.total);
            (point, counts.exceptional_cached_adds)
        };
        exceptional_adds += exceptional;
        if case["expected_identity"].as_bool().unwrap_or(false) {
            assert!(point.is_identity());
        } else {
            let (px, py) = point.to_affine().expect("scalar output");
            assert_eq!(fe_hex(px), case["expected_x_hex"].as_str().expect("expected x"));
            assert_eq!(fe_hex(py), case["expected_y_hex"].as_str().expect("expected y"));
        }
        total += chosen_cost;
    }
    assert_eq!(panel["selected_total"].as_u64(), Some(total as u64));
    assert_eq!(panel["radix_two_choices"].as_u64(), Some(selected_radix_two as u64));
    println!("{}", serde_json::json!({"verified": true, "fixture": name,
        "cases": cases.len(), "radix_two_choices": selected_radix_two,
        "output_checks": cases.len(), "seed_checks": seed_checks,
        "selected_M_plus_S": total, "exceptional_cached_adds": exceptional_adds,
        "cpu_speedup_claim": null}));
}
