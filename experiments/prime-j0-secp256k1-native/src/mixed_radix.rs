//! Conditional radix-two exits from the fixed width-four tau digit chain.

use super::*;
use num_traits::ToPrimitive;

#[derive(Clone, Copy, Eq, PartialEq)]
enum Radix {
    Tau,
    Two,
    Rho,
    BarRho,
}

#[derive(Clone, Copy)]
pub(super) struct Action {
    radix: Radix,
    digit: Option<Digit>,
}

#[derive(Default)]
pub(super) struct Counts {
    pub(super) tau_steps: usize,
    pub(super) tau_pairs: usize,
    pub(super) doubles: usize,
    pub(super) rho_steps: usize,
    pub(super) bar_rho_steps: usize,
    pub(super) mixed_adds: usize,
    pub(super) general_adds: usize,
    pub(super) cache_entries: usize,
    pub(super) exceptional_cached_adds: usize,
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
            (x, y) = match action.radix {
                Radix::Two => (2 * x, 2 * y),
                Radix::Tau => (-3 * &y, &x + 3 * &y),
                Radix::Rho => (&x - 3 * &y, &x + 4 * &y),
                Radix::BarRho => (4 * &x + 3 * &y, &y - &x),
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

pub(super) fn recode_zero_tau(mut a: BigInt, mut b: BigInt) -> Vec<Action> {
    #[cfg(debug_assertions)]
    let original = (a.clone(), b.clone());
    let mut actions = Vec::new();
    while !a.is_zero() || !b.is_zero() {
        assert!(actions.len() < 512, "zero-tau expansion did not terminate");
        let both_even = signed_residue(&a, 2) == 0 && signed_residue(&b, 2) == 0;
        // A tau step has zero digit when a is divisible by three; prefer it
        // to a double, allowing the existing tau-pair evaluator to fuse it.
        if both_even && signed_residue(&a, 3) != 0 {
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
            (x, y) = match action.radix {
                Radix::Two => (2 * x, 2 * y),
                Radix::Tau => (-3 * &y, &x + 3 * &y),
                Radix::Rho => (&x - 3 * &y, &x + 4 * &y),
                Radix::BarRho => (4 * &x + 3 * &y, &y - &x),
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

fn half_exit_wins(a: &BigInt, b: &BigInt) -> bool {
    match (a.to_i64(), b.to_i64()) {
        (Some(x), Some(y)) if (-395..=395).contains(&x)
                           && (-228..=228).contains(&y) => {
            x * x + 3 * x * y + 3 * y * y > 39_083
        }
        _ => true,
    }
}

const SHARED_Z_TAIL: &[u8; 5_329] = include_bytes!("../shared-z-tail4096.bin");
const UNITS: [(i64, i64); 6] =
    [(-2, 1), (-1, 0), (-1, 1), (1, -1), (1, 0), (2, -1)];
const UNIT_INVERSES: [(i64, i64); 6] =
    [(1, -1), (-1, 0), (2, -1), (-2, 1), (1, 0), (-1, 1)];

fn ring_product((a, b): (i64, i64), (c, d): (i64, i64)) -> (i64, i64) {
    (a * c - 3 * b * d, a * d + b * c + 3 * b * d)
}

fn small_norm(a: i64, b: i64) -> i64 {
    a * a + 3 * a * b + 3 * b * b
}

fn digit_for(a: i64, b: i64) -> Digit {
    let digit = DIGIT_TABLE[a.rem_euclid(9) as usize][b.rem_euclid(9) as usize]
        .expect("tail digit residue");
    assert_eq!((digit.a, digit.b), (a, b));
    digit
}

fn decode_tail_action(a: i64, b: i64, code: u8) -> (Radix, Option<(i64, i64)>, i64, i64) {
    let (radix, digit) = match code {
        0 => (Radix::Tau, if a % 3 == 0 { None } else {
            let d = DIGIT_TABLE[a.rem_euclid(9) as usize][b.rem_euclid(9) as usize]
                .expect("tail tau digit");
            Some((d.a, d.b))
        }),
        1 => (Radix::Two, None),
        2 => (Radix::Rho, None),
        3 => (Radix::BarRho, None),
        4 | 5 => {
            let parity = (a.rem_euclid(2), b.rem_euclid(2));
            let unit = UNITS.into_iter().filter(|u|
                (u.0.rem_euclid(2), u.1.rem_euclid(2)) == parity)
                .nth((code - 4) as usize).expect("half-exit unit");
            (Radix::Two, Some(unit))
        }
        6 => {
            let residue = (a - b).rem_euclid(7);
            let unit = UNITS.into_iter().find(|u|
                (u.0 - u.1).rem_euclid(7) == residue)
                .expect("rho-exit unit");
            (Radix::Rho, Some(unit))
        }
        7 => {
            let residue = (a - 3 * b).rem_euclid(7);
            let unit = UNITS.into_iter().find(|u|
                (u.0 - 3 * u.1).rem_euclid(7) == residue)
                .expect("conjugate-rho-exit unit");
            (Radix::BarRho, Some(unit))
        }
        _ => panic!("invalid shared-Z tail action"),
    };
    let x = a - digit.map_or(0, |d| d.0);
    let y = b - digit.map_or(0, |d| d.1);
    let quotient = match radix {
        Radix::Tau => {
            assert_eq!(x.rem_euclid(3), 0);
            (x + y, -x / 3)
        }
        Radix::Two => {
            assert_eq!(x.rem_euclid(2), 0);
            assert_eq!(y.rem_euclid(2), 0);
            (x / 2, y / 2)
        }
        Radix::Rho => {
            assert_eq!((x - y).rem_euclid(7), 0);
            ((4 * x + 3 * y) / 7, (y - x) / 7)
        }
        Radix::BarRho => {
            assert_eq!((x - 3 * y).rem_euclid(7), 0);
            ((x - 3 * y) / 7, (x + 4 * y) / 7)
        }
    };
    (radix, digit, quotient.0, quotient.1)
}

fn tail_actions(mut a: i64, mut b: i64, mut pending_tau: bool) -> Vec<Action> {
    assert!((0..=4_096).contains(&small_norm(a, b)));
    let mut actions = Vec::with_capacity(7);
    while a != 0 || b != 0 {
        assert!(actions.len() < 7, "tail table did not terminate");
        let ((ca, cb), unit_index) = UNITS.into_iter().enumerate()
            .map(|(index, unit)| (ring_product((a, b), unit), index))
            .min().expect("six unit images");
        assert!((-128..=-2).contains(&ca));
        let row = (ca + 128) as usize;
        let offset = u16::from_le_bytes([
            SHARED_Z_TAIL[4_948 + 2 * row], SHARED_Z_TAIL[4_949 + 2 * row]]) as usize;
        let minimum = i64::from(SHARED_Z_TAIL[5_202 + row]);
        assert!(cb >= minimum);
        let index = (offset + (cb - minimum) as usize) * 2 + usize::from(pending_tau);
        assert!(index < 4_948);
        let (radix, canonical_digit, x, y) = decode_tail_action(
            ca, cb, SHARED_Z_TAIL[index]);
        let inverse = UNIT_INVERSES[unit_index];
        let (next_a, next_b) = ring_product((x, y), inverse);
        let digit = canonical_digit.map(|d| {
            let (da, db) = ring_product(d, inverse);
            digit_for(da, db)
        });
        let terminal = next_a == 0 && next_b == 0;
        let pair = pending_tau && radix == Radix::Tau && digit.is_none() && !terminal;
        pending_tau = radix == Radix::Tau && !pair && !terminal;
        actions.push(Action { radix, digit });
        (a, b) = (next_a, next_b);
    }
    assert!(actions.last().is_some_and(|action| action.digit.is_some()));
    actions
}

// Closed-form mixed τ/2/ρ/conjugate-ρ policy. The norm cutoff makes a
// zero-digit τ step preferable to a double near the end of the chain.
fn recode_degree_seven(mut a: BigInt, mut b: BigInt, use_tail: bool) -> Vec<Action> {
    #[cfg(debug_assertions)]
    let original = (a.clone(), b.clone());
    let mut actions = Vec::new();
    let mut pending_tau = false;
    while !a.is_zero() || !b.is_zero() {
        assert!(actions.len() < 256, "degree-seven expansion did not terminate");
        if use_tail {
            if let (Some(x), Some(y)) = (a.to_i64(), b.to_i64()) {
                if (-128..=128).contains(&x) && (-73..=73).contains(&y)
                    && small_norm(x, y) <= 4_096 {
                    actions.extend(tail_actions(x, y, pending_tau));
                    break;
                }
            }
        }
        let even = signed_residue(&a, 2) == 0 && signed_residue(&b, 2) == 0;
        let has_digit = signed_residue(&a, 3) != 0;
        let digit = if has_digit {
            Some(DIGIT_TABLE[signed_residue(&a, 9)][signed_residue(&b, 9)]
                .expect("original width-four residue"))
        } else {
            None
        };
        let terminal_digit = digit.is_some_and(|d|
            a == BigInt::from(d.a) && b == BigInt::from(d.b));
        let radix = if has_digit {
            if terminal_digit {
                Radix::Tau
            } else if even {
                Radix::Two
            } else if signed_residue(&(&a - &b), 7) == 0 {
                Radix::Rho
            } else if signed_residue(&(&a - 3 * &b), 7) == 0 {
                Radix::BarRho
            } else {
                Radix::Tau
            }
        } else if even && !pending_tau && half_exit_wins(&a, &b) {
            Radix::Two
        } else {
            Radix::Tau
        };
        let used_digit = if radix == Radix::Tau { digit } else { None };
        match radix {
            Radix::Tau => {
                if let Some(d) = used_digit {
                    a -= d.a;
                    b -= d.b;
                }
                assert_eq!(signed_residue(&a, 3), 0);
                (a, b) = (&a + &b, -a / 3);
            }
            Radix::Two => {
                a /= 2;
                b /= 2;
            }
            Radix::Rho => {
                let x = (4 * &a + 3 * &b) / 7;
                let y = (&b - &a) / 7;
                (a, b) = (x, y);
            }
            Radix::BarRho => {
                let x = (&a - 3 * &b) / 7;
                let y = (&a + 4 * &b) / 7;
                (a, b) = (x, y);
            }
        }
        let terminal = a.is_zero() && b.is_zero();
        let pair = pending_tau && radix == Radix::Tau
            && used_digit.is_none() && !terminal;
        pending_tau = radix == Radix::Tau && !pair && !terminal;
        actions.push(Action { radix, digit: used_digit });
    }
    assert!(actions.last().is_some_and(|action| action.digit.is_some()));
    #[cfg(debug_assertions)]
    {
        let (mut x, mut y) = (BigInt::ZERO, BigInt::ZERO);
        for action in actions.iter().rev() {
            (x, y) = match action.radix {
                Radix::Two => (2 * x, 2 * y),
                Radix::Tau => (-3 * &y, &x + 3 * &y),
                Radix::Rho => (&x - 3 * &y, &x + 4 * &y),
                Radix::BarRho => (4 * &x + 3 * &y, &y - &x),
            };
            if let Some(d) = action.digit {
                x += d.a;
                y += d.b;
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

pub(super) fn source_cost(actions: &[Action]) -> usize {
    assert!(actions.iter().all(|action|
        matches!(action.radix, Radix::Tau | Radix::Two)));
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

pub(super) fn action_fingerprint(actions: &[Action]) -> u64 {
    const PRIME: u64 = 0x100000001b3;
    let mut value = 0xcbf29ce484222325u64;
    for action in actions {
        let radix = match action.radix {
            Radix::Tau => 1u8,
            Radix::Two => 2u8,
            Radix::Rho => 3u8,
            Radix::BarRho => 4u8,
        };
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

pub(super) fn check_zero_tau_action_fingerprints(fixture_path: &str, fingerprint_path: &str) {
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
        let actions = recode_zero_tau(a, b);
        assert_eq!(row["actions"].as_u64(), Some(actions.len() as u64));
        assert_eq!(row["fnv64"].as_str(), Some(format!("{:016x}",
            action_fingerprint(&actions)).as_str()));
    }
    println!("{}", serde_json::json!({"verified": true, "fixture": name,
        "action_stream_checks": cases.len(), "cpu_speedup_claim": null}));
}

pub(super) fn evaluate(actions: &[Action], seeds: &[J; 9], beta: F) -> (J, Counts) {
    evaluate_inner(actions, seeds, beta, false)
}

pub(super) fn evaluate_shared_z(actions: &[Action], seeds: &[J; 9], beta: F) -> (J, Counts) {
    evaluate_inner(actions, seeds, beta, true)
}

fn evaluate_inner(actions: &[Action], seeds: &[J; 9], beta: F,
                  shared_z: bool) -> (J, Counts) {
    let aligned = shared_z.then(|| align_common_z(seeds));
    let seeds = aligned.as_ref().map_or(seeds, |(_, points)| points);
    let mut counts = Counts::default();
    let mut images = [[J::identity(); 3]; 9];
    for seed in 0..9 {
        images[seed] = orbit(seeds[seed], beta);
    }
    let mut cache: [Option<(F, F)>; 9] = [None; 9];
    if !shared_z {
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
            } else {
                match action.radix {
                    Radix::Tau => {
                        accumulator = accumulator.tau(one_minus_beta);
                        counts.tau_steps += 1;
                    }
                    Radix::Two => {
                        accumulator = accumulator.double();
                        counts.doubles += 1;
                    }
                    Radix::Rho => {
                        accumulator = accumulator.rho(beta, false);
                        counts.rho_steps += 1;
                    }
                    Radix::BarRho => {
                        accumulator = accumulator.rho(beta, true);
                        counts.bar_rho_steps += 1;
                    }
                }
            }
        }
        if let Some(digit) = digit {
            let mut point = images[digit.seed][(digit.power + gauge) % 3];
            if digit.sign < 0 {
                point = point.neg();
            }
            if accumulator.is_identity() {
                accumulator = point;
            } else if shared_z || digit.seed == 0 {
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
    if let Some((common_z, _)) = aligned {
        accumulator.z = accumulator.z.mul(&common_z);
    }
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

pub(super) fn check_zero_tau_fixture(fixture_path: &str, seed_path: &str, score_path: &str) {
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
    let mut zero_tau_choices = 0usize;
    let mut seed_checks = 0usize;
    let mut exceptional_adds = 0usize;
    for (case, row) in cases.iter().zip(rows) {
        assert_eq!(case["index"], row["index"]);
        assert_eq!(row["status"].as_str(), Some("verified"));
        let scalar = big_from_hex(case["scalar_hex"].as_str().expect("scalar"));
        let (a, b) = short_representative(&scalar);
        assert_eq!(a, big_from_hex(case["short_a_hex"].as_str().expect("short a")));
        assert_eq!(b, big_from_hex(case["short_b_hex"].as_str().expect("short b")));
        let actions = recode_zero_tau(a.clone(), b.clone());
        let policy_cost = source_cost(&actions);
        let selective = selective::recode(a, b);
        let choose_policy = policy_cost < selective.total;
        assert_eq!(row["policy_M_plus_S"].as_u64(), Some(policy_cost as u64));
        assert_eq!(row["selective_M_plus_S"].as_u64(), Some(selective.total as u64));
        assert_eq!(row["selected"].as_str(),
            Some(if choose_policy { "zero_tau" } else { "selective" }));
        let chosen_cost = if choose_policy { policy_cost } else { selective.total };
        assert_eq!(row["selected_M_plus_S"].as_u64(), Some(chosen_cost as u64));
        let x = case["base_x_hex"].as_str().expect("base x");
        let y = case["base_y_hex"].as_str().expect("base y");
        let base = J::affine(fe_from_hex(x), fe_from_hex(y));
        let (point, exceptional) = if choose_policy {
            zero_tau_choices += 1;
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
            assert_eq!(recount, policy_cost);
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
    assert_eq!(panel["zero_tau_choices"].as_u64(), Some(zero_tau_choices as u64));
    println!("{}", serde_json::json!({"verified": true, "fixture": name,
        "cases": cases.len(), "zero_tau_choices": zero_tau_choices,
        "output_checks": cases.len(), "seed_checks": seed_checks,
        "selected_M_plus_S": total, "exceptional_cached_adds": exceptional_adds,
        "cpu_speedup_claim": null}));
}

pub(super) fn benchmark_case(fixture_path: &str, index: usize, timed: bool) {
    let fixture: Value = serde_json::from_slice(&fs::read(fixture_path).expect("fixture"))
        .expect("fixture JSON");
    let case = &fixture["cases"].as_array().expect("cases")[index];
    let base_x = case["base_x_hex"].as_str().expect("base x");
    let base_y = case["base_y_hex"].as_str().expect("base y");
    let scalar_hex = case["scalar_hex"].as_str().expect("scalar");
    let expected = if case["expected_identity"].as_bool().unwrap_or(false) {
        "identity".to_owned()
    } else {
        format!("{}:{}", case["expected_x_hex"].as_str().expect("expected x"),
                case["expected_y_hex"].as_str().expect("expected y"))
    };
    let beta = fe_from_hex(fixture["beta_hex"].as_str().expect("beta"));
    LazyLock::force(&LATTICE);
    LazyLock::force(&DIGIT_TABLE);
    LazyLock::force(&LINKED_DIGIT_TABLE);
    let start = Instant::now();
    let scalar = big_from_hex(scalar_hex);
    let base = J::affine(fe_from_hex(base_x), fe_from_hex(base_y));
    let (a, b) = short_representative(&scalar);
    let actions = recode(a.clone(), b.clone());
    let greedy_cost = source_cost(&actions);
    let selective = selective::recode(a.clone(), b.clone());
    let choose_greedy = greedy_cost < selective.total;
    let (point, exceptional) = if choose_greedy {
        let seeds = prepare(base, beta);
        let (point, counts) = evaluate(&actions, &seeds, beta);
        (point, counts.exceptional_cached_adds)
    } else {
        let seeds = selective::prepare(base, beta, selective.built_mask);
        let (point, counts) = evaluate_mode(&selective.digits, &seeds, beta, false, true);
        (point, counts.exceptional_cached_adds)
    };
    let actual = match point.to_affine() {
        None => "identity".to_owned(),
        Some((x, y)) => format!("{}:{}", fe_hex(x), fe_hex(y)),
    };
    assert_eq!(actual, expected, "benchmark output mismatch");
    let elapsed_ms = start.elapsed().as_secs_f64() * 1000.0;
    if !timed {
        assert_eq!(a, big_from_hex(case["short_a_hex"].as_str().expect("short a")));
        assert_eq!(b, big_from_hex(case["short_b_hex"].as_str().expect("short b")));
    }
    let arm = if choose_greedy { "radix_two" } else { "selective" };
    let cost = if choose_greedy { greedy_cost } else { selective.total };
    if timed {
        println!("online_ms={elapsed_ms:.6} verified=1 curve=secp256k1 base_x={base_x} base_y={base_y} scalar={scalar_hex} point={actual} mode=mixed_radix arm={arm} source_M_plus_S={cost} exceptional_cached_adds={exceptional}");
    } else {
        println!("verified=1 curve=secp256k1 base_x={base_x} base_y={base_y} scalar={scalar_hex} point={actual} mode=mixed_radix arm={arm} source_M_plus_S={cost} exceptional_cached_adds={exceptional}");
    }
}

pub(super) fn benchmark_zero_tau_case(fixture_path: &str, index: usize,
                                      timed: bool, shared_z: bool) {
    let fixture: Value = serde_json::from_slice(&fs::read(fixture_path).expect("fixture"))
        .expect("fixture JSON");
    let case = &fixture["cases"].as_array().expect("cases")[index];
    let base_x = case["base_x_hex"].as_str().expect("base x");
    let base_y = case["base_y_hex"].as_str().expect("base y");
    let scalar_hex = case["scalar_hex"].as_str().expect("scalar");
    let expected = if case["expected_identity"].as_bool().unwrap_or(false) {
        "identity".to_owned()
    } else {
        format!("{}:{}", case["expected_x_hex"].as_str().expect("expected x"),
                case["expected_y_hex"].as_str().expect("expected y"))
    };
    let beta = fe_from_hex(fixture["beta_hex"].as_str().expect("beta"));
    LazyLock::force(&LATTICE);
    LazyLock::force(&DIGIT_TABLE);
    LazyLock::force(&LINKED_DIGIT_TABLE);
    let start = Instant::now();
    let scalar = big_from_hex(scalar_hex);
    let base = J::affine(fe_from_hex(base_x), fe_from_hex(base_y));
    let (a, b) = short_representative(&scalar);
    let actions = recode_zero_tau(a.clone(), b.clone());
    let policy_cost = source_cost(&actions);
    let selective = (!shared_z).then(|| selective::recode(a.clone(), b.clone()));
    let choose_policy = selective.as_ref().is_none_or(|plan| policy_cost < plan.total);
    let (point, exceptional, cost) = if choose_policy {
        let seeds = prepare(base, beta);
        let (point, counts) = if shared_z {
            evaluate_shared_z(&actions, &seeds, beta)
        } else {
            evaluate(&actions, &seeds, beta)
        };
        let cost = if shared_z {
            assert_eq!(counts.cache_entries, 0);
            assert_eq!(counts.general_adds, 0);
            83 + 57 + 6 * counts.tau_steps + 7 * counts.doubles
                - 2 * counts.tau_pairs + 11 * counts.mixed_adds
        } else {
            policy_cost
        };
        (point, counts.exceptional_cached_adds, cost)
    } else {
        let selective = selective.expect("selective plan");
        let seeds = selective::prepare(base, beta, selective.built_mask);
        let (point, counts) = evaluate_mode(&selective.digits, &seeds, beta, false, true);
        (point, counts.exceptional_cached_adds, selective.total)
    };
    let actual = match point.to_affine() {
        None => "identity".to_owned(),
        Some((x, y)) => format!("{}:{}", fe_hex(x), fe_hex(y)),
    };
    assert_eq!(actual, expected, "benchmark output mismatch");
    let elapsed_ms = start.elapsed().as_secs_f64() * 1000.0;
    if !timed {
        assert_eq!(a, big_from_hex(case["short_a_hex"].as_str().expect("short a")));
        assert_eq!(b, big_from_hex(case["short_b_hex"].as_str().expect("short b")));
    }
    let arm = if choose_policy { "zero_tau" } else { "selective" };
    let mode = if shared_z { "shared_z_zero_tau" } else { "zero_tau" };
    if timed {
        println!("online_ms={elapsed_ms:.6} verified=1 curve=secp256k1 base_x={base_x} base_y={base_y} scalar={scalar_hex} point={actual} mode={mode} arm={arm} source_M_plus_S={cost} exceptional_cached_adds={exceptional}");
    } else {
        println!("verified=1 curve=secp256k1 base_x={base_x} base_y={base_y} scalar={scalar_hex} point={actual} mode={mode} arm={arm} source_M_plus_S={cost} exceptional_cached_adds={exceptional}");
    }
}

pub(super) fn check_degree_seven_case(fixture_path: &str, index: usize,
                                      use_tail: bool, timed: bool) {
    let fixture: Value = serde_json::from_slice(&fs::read(fixture_path).expect("fixture"))
        .expect("fixture JSON");
    let case = &fixture["cases"].as_array().expect("cases")[index];
    let base_x = case["base_x_hex"].as_str().expect("base x");
    let base_y = case["base_y_hex"].as_str().expect("base y");
    let scalar_hex = case["scalar_hex"].as_str().expect("scalar");
    let expected = if case["expected_identity"].as_bool().unwrap_or(false) {
        "identity".to_owned()
    } else {
        format!("{}:{}", case["expected_x_hex"].as_str().expect("expected x"),
                case["expected_y_hex"].as_str().expect("expected y"))
    };
    let beta = fe_from_hex(fixture["beta_hex"].as_str().expect("beta"));
    LazyLock::force(&LATTICE);
    LazyLock::force(&DIGIT_TABLE);
    let start = Instant::now();
    let scalar = big_from_hex(scalar_hex);
    let base = J::affine(
        fe_from_hex(base_x), fe_from_hex(base_y));
    let (a, b) = short_representative(&scalar);
    let actions = recode_degree_seven(a.clone(), b.clone(), use_tail);
    let seeds = prepare(base, beta);
    let (point, counts) = evaluate_shared_z(&actions, &seeds, beta);
    assert_eq!(counts.cache_entries, 0);
    assert_eq!(counts.general_adds, 0);
    let source = 83 + 57 + 6 * counts.tau_steps + 7 * counts.doubles
        + 13 * (counts.rho_steps + counts.bar_rho_steps)
        - 2 * counts.tau_pairs + 11 * counts.mixed_adds;
    let actual = match point.to_affine() {
        None => "identity".to_owned(),
        Some((x, y)) => format!("{}:{}", fe_hex(x), fe_hex(y)),
    };
    assert_eq!(actual, expected, "degree-seven output mismatch");
    let elapsed_ms = start.elapsed().as_secs_f64() * 1000.0;
    if !timed {
        assert_eq!(a, big_from_hex(case["short_a_hex"].as_str().expect("short a")));
        assert_eq!(b, big_from_hex(case["short_b_hex"].as_str().expect("short b")));
    }
    let mode = if use_tail { "shared_z_degree_seven_tail" }
               else { "shared_z_degree_seven" };
    if timed {
        println!("online_ms={elapsed_ms:.6} verified=1 mode={mode} curve=secp256k1 base_x={base_x} base_y={base_y} scalar={scalar_hex} point={actual} source_M_plus_S={source} rho_steps={} bar_rho_steps={} tau_steps={} doubles={} mixed_adds={} cpu_speedup_claim=null",
                 counts.rho_steps, counts.bar_rho_steps, counts.tau_steps,
                 counts.doubles, counts.mixed_adds);
    } else {
        println!("verified=1 mode={mode} curve=secp256k1 base_x={base_x} base_y={base_y} scalar={scalar_hex} point={actual} source_M_plus_S={source} rho_steps={} bar_rho_steps={} tau_steps={} doubles={} mixed_adds={} cpu_speedup_claim=null",
                 counts.rho_steps, counts.bar_rho_steps, counts.tau_steps,
                 counts.doubles, counts.mixed_adds);
    }
}

#[cfg(test)]
mod tail_tests {
    use super::*;

    #[test]
    fn compact_tail_reconstructs_every_state_and_pending_pair() {
        LazyLock::force(&DIGIT_TABLE);
        let mut checked = 0;
        for a in -128..=128 {
            for b in -73..=73 {
                if !(1..=4_096).contains(&small_norm(a, b)) {
                    continue;
                }
                for pending_tau in [false, true] {
                    let actions = tail_actions(a, b, pending_tau);
                    assert!(actions.len() <= 7);
                    let (mut x, mut y) = (0, 0);
                    for action in actions.into_iter().rev() {
                        (x, y) = match action.radix {
                            Radix::Tau => (-3 * y, x + 3 * y),
                            Radix::Two => (2 * x, 2 * y),
                            Radix::Rho => (x - 3 * y, x + 4 * y),
                            Radix::BarRho => (4 * x + 3 * y, y - x),
                        };
                        if let Some(digit) = action.digit {
                            x += digit.a;
                            y += digit.b;
                        }
                    }
                    assert_eq!((x, y), (a, b), "state ({a}, {b}, {pending_tau})");
                    checked += 1;
                }
            }
        }
        assert_eq!(checked, 29_688);
    }
}
