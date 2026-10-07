//! Variable-time bounded-carry mixed alphabet with selective point preparation.

use super::*;
use std::collections::HashMap;

const TAIL_HORIZON: usize = 16;
const PARENTS: [u16; 12] = [
    0,
    1 << 0,
    1 << 1,
    1 << 1,
    1 << 3,
    1 << 4,
    1 << 5,
    1 << 3,
    1 << 1,
    1 << 8,
    1 << 9,
    1 << 4,
];
const POINT_COST: [usize; 12] = [0, 7, 7, 11, 7, 11, 7, 11, 11, 7, 7, 7];

#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
struct State {
    carry: (i64, i64),
    last: i16,
    high: i16,
    cache_mask: u16,
    used_mask: u16,
}

struct Record {
    cost: usize,
    link: usize,
}

struct Link {
    parent: usize,
    digit: Option<Digit>,
}

pub(super) struct Plan {
    pub digits: Vec<Option<Digit>>,
    pub used_mask: u16,
    pub built_mask: u16,
    pub preparation: usize,
    pub total: usize,
    pub peak_states: usize,
    pub peak_carry_norm: i64,
}

fn options(row: usize, col: usize) -> ([Option<Digit>; 2], usize) {
    if row % 3 == 0 {
        return ([None, None], 1);
    }
    let original = DIGIT_TABLE[row][col].expect("covered baseline residue");
    let mut alternate = LINKED_DIGIT_TABLE[row][col].expect("covered linked residue");
    if (original.a, original.b) == (alternate.a, alternate.b) {
        ([Some(original), None], 1)
    } else {
        assert!((5..=7).contains(&alternate.seed));
        alternate.seed += 4; // Linked slots 5,6,7 become union seeds 9,10,11.
        ([Some(original), Some(alternate)], 2)
    }
}

fn preparation_cost(used: u16) -> (usize, u16) {
    if used == 0 {
        return (0, 0);
    }
    let mut required = used;
    loop {
        let previous = required;
        for (seed, parents) in PARENTS.iter().enumerate() {
            if required & (1 << seed) != 0 {
                required |= parents;
            }
        }
        if required == previous {
            break;
        }
    }
    let points = POINT_COST
        .iter()
        .enumerate()
        .filter(|(seed, _)| required & (1 << seed) != 0)
        .map(|(_, cost)| *cost)
        .sum::<usize>();
    let rotations = usize::from(required & (1 << 3) != 0) + usize::from(required & (1 << 8) != 0);
    let orbit_images = used.count_ones() as usize;
    (points + rotations + orbit_images, required)
}

fn next_carry(old: Option<Digit>, carry: (i64, i64), digit: Option<Digit>) -> (i64, i64) {
    let (da, db) = old.map_or((0, 0), |d| (d.a, d.b));
    let (ea, eb) = digit.map_or((0, 0), |d| (d.a, d.b));
    let x = da + carry.0 - ea;
    let y = db + carry.1 - eb;
    assert_eq!(x % 3, 0);
    let successor = (x + y, -x / 3);
    assert!(small_carry_norm(successor) <= 896);
    successor
}

pub(super) fn recode(a: BigInt, b: BigInt) -> Plan {
    let baseline = baseline_residue_scan(a, b);
    let mut links = vec![Link {
        parent: 0,
        digit: None,
    }];
    let mut current = vec![(
        State {
            carry: (0, 0),
            last: -1,
            high: -1,
            cache_mask: 0,
            used_mask: 0,
        },
        Record { cost: 0, link: 0 },
    )];
    let mut peak_states = 1;
    let mut peak_carry_norm = 0;
    for position in 0..baseline.len() + TAIL_HORIZON {
        let (ra, rb, old) = baseline.get(position).copied().unwrap_or((0, 0, None));
        let mut following: Vec<(State, Record)> = Vec::new();
        let mut locations: HashMap<State, usize> = HashMap::new();
        for (state, record) in current {
            let row = (ra as i64 + state.carry.0).rem_euclid(9) as usize;
            let col = (rb as i64 + state.carry.1).rem_euclid(9) as usize;
            let (choices, count) = options(row, col);
            for digit in choices.into_iter().take(count) {
                let carry = next_carry(old, state.carry, digit);
                peak_carry_norm = peak_carry_norm.max(small_carry_norm(carry));
                let mut next = state;
                next.carry = carry;
                let extra = if let Some(digit) = digit {
                    next.last = position as i16;
                    next.high = digit.seed as i16;
                    next.used_mask |= 1 << digit.seed;
                    if state.last < 0 {
                        6 * position - 2 * (position / 2)
                    } else {
                        let previous = state.last as usize;
                        let gap = position - previous - 1;
                        let cache = if state.high > 0 && state.cache_mask & (1 << state.high) == 0 {
                            2
                        } else {
                            0
                        };
                        if state.high > 0 {
                            next.cache_mask |= 1 << state.high;
                        }
                        6 * (position - previous) - 2 * ((gap + 1) / 2)
                            + if state.high == 0 { 11 } else { 14 }
                            + cache
                    }
                } else {
                    0
                };
                let value = record.cost + extra;
                if let Some(&location) = locations.get(&next) {
                    if value < following[location].1.cost {
                        let link = links.len();
                        links.push(Link {
                            parent: record.link,
                            digit,
                        });
                        following[location].1 = Record { cost: value, link };
                    }
                } else {
                    let link = links.len();
                    links.push(Link {
                        parent: record.link,
                        digit,
                    });
                    locations.insert(next, following.len());
                    following.push((next, Record { cost: value, link }));
                }
            }
        }
        current = following;
        peak_states = peak_states.max(current.len());
    }
    let mut best: Option<(usize, usize, State, usize)> = None;
    for (state, record) in current {
        if state.carry != (0, 0) {
            continue;
        }
        let total = record.cost + preparation_cost(state.used_mask).0;
        let key = (total, record.cost, state);
        if best.as_ref().is_none_or(|old| key < (old.0, old.1, old.2)) {
            best = Some((total, record.cost, state, record.link));
        }
    }
    let (total, evaluator, state, mut link) = best.expect("bounded carry solution");
    let mut digits = Vec::with_capacity(baseline.len() + TAIL_HORIZON);
    while link != 0 {
        digits.push(links[link].digit);
        link = links[link].parent;
    }
    digits.reverse();
    while digits.last().is_some_and(Option::is_none) {
        digits.pop();
    }
    let (preparation, built_mask) = preparation_cost(state.used_mask);
    assert_eq!(total, evaluator + preparation);
    assert_eq!(total, source_cost(&digits, preparation));
    Plan {
        digits,
        used_mask: state.used_mask,
        built_mask,
        preparation,
        total,
        peak_states,
        peak_carry_norm,
    }
}

pub(super) fn prepare(base: J, beta: F, built: u16) -> [J; 12] {
    assert_eq!(base.z, F::ONE);
    let mut point = [J::identity(); 12];
    point[0] = base;
    if built & (1 << 1) != 0 {
        point[1] = base.double();
    }
    if built & (1 << 2) != 0 {
        point[2] = point[1].double();
    }
    if built & (1 << 3) != 0 {
        point[3] = point[1].add_mixed(beta.mul(&base.x), base.y.neg());
    }
    if built & (1 << 4) != 0 {
        point[4] = point[3].double();
    }
    if built & (1 << 5) != 0 {
        point[5] = point[4].add_mixed(base.x, base.y.neg());
    }
    if built & (1 << 6) != 0 {
        point[6] = point[5].double();
    }
    if built & (1 << 7) != 0 {
        point[7] = point[3].add_mixed(base.x, base.y);
    }
    if built & (1 << 8) != 0 {
        point[8] = point[1].omega(beta).add_mixed(base.x, base.y.neg());
    }
    if built & (1 << 9) != 0 {
        point[9] = point[8].double();
    }
    if built & (1 << 10) != 0 {
        point[10] = point[9].double();
    }
    if built & (1 << 11) != 0 {
        point[11] = point[4].double();
    }
    point
}

fn expected_seed<'a>(seeds: &'a Value, base_x: &str, base_y: &str) -> &'a Value {
    seeds
        .as_array()
        .expect("base seed array")
        .iter()
        .find(|row| row["base_x_hex"] == base_x && row["base_y_hex"] == base_y)
        .expect("matching Sage base seed row")
}

pub(super) fn check_fixture(fixture_path: &str, seed_path: &str, result_path: &str) {
    let fixture: Value =
        serde_json::from_slice(&fs::read(fixture_path).expect("read scalar fixture"))
            .expect("parse scalar fixture");
    let seeds: Value =
        serde_json::from_slice(&fs::read(seed_path).expect("read Sage seed fixture"))
            .expect("parse Sage seed fixture");
    let scores: Value =
        serde_json::from_slice(&fs::read(result_path).expect("read selective result"))
            .expect("parse selective result");
    let name = PathBuf::from(fixture_path)
        .file_name()
        .expect("fixture name")
        .to_str()
        .expect("UTF-8 fixture name")
        .to_owned();
    let panel = scores["panels"]
        .as_array()
        .expect("result panels")
        .iter()
        .find(|panel| panel["fixture"] == name)
        .expect("matching result panel");
    let seed_panel = &seeds["panels"][&name];
    assert_eq!(fixture["beta_hex"], seeds["beta_hex"]);
    let beta = fe_from_hex(fixture["beta_hex"].as_str().expect("beta"));
    LazyLock::force(&LATTICE);
    LazyLock::force(&DIGIT_TABLE);
    LazyLock::force(&LINKED_DIGIT_TABLE);
    let cases = fixture["cases"].as_array().expect("fixture cases");
    assert_eq!(panel["cases"].as_u64(), Some(cases.len() as u64));
    assert_eq!(seed_panel["cases"].as_u64(), Some(cases.len() as u64));
    assert_eq!(preparation_cost((1 << 9) - 1).0, 83);
    assert_eq!(preparation_cost((1 << 12) - 1).0, 107);
    let mut total = 0usize;
    let mut seed_checks = 0usize;
    let mut exceptional_adds = 0usize;
    let mut peak_states = 0usize;
    let mut peak_carry_norm = 0i64;
    for (index, case) in cases.iter().enumerate() {
        let scalar = big_from_hex(case["scalar_hex"].as_str().expect("scalar"));
        let (a, b) = short_representative(&scalar);
        assert_eq!(
            a,
            big_from_hex(case["short_a_hex"].as_str().expect("short a"))
        );
        assert_eq!(
            b,
            big_from_hex(case["short_b_hex"].as_str().expect("short b"))
        );
        let plan = recode(a, b);
        let expected = &panel["rows"][index];
        assert_eq!(expected["index"].as_u64(), Some(index as u64));
        assert_eq!(expected["total_M_plus_S"].as_u64(), Some(plan.total as u64));
        assert_eq!(
            expected["preparation_M_plus_S"].as_u64(),
            Some(plan.preparation as u64)
        );
        assert_eq!(
            expected["digit_positions"].as_u64(),
            Some(plan.digits.len() as u64)
        );
        assert_eq!(
            expected["peak_dp_states"].as_u64(),
            Some(plan.peak_states as u64)
        );
        let used = expected["used_seed_ids"].as_array().expect("used seeds");
        let built = expected["built_seed_ids"].as_array().expect("built seeds");
        for seed in 0..12 {
            assert_eq!(
                used.iter().any(|item| item.as_u64() == Some(seed as u64)),
                plan.used_mask & (1 << seed) != 0
            );
            assert_eq!(
                built.iter().any(|item| item.as_u64() == Some(seed as u64)),
                plan.built_mask & (1 << seed) != 0
            );
        }
        let base_x = case["base_x_hex"].as_str().expect("base x");
        let base_y = case["base_y_hex"].as_str().expect("base y");
        let base = J::affine(fe_from_hex(base_x), fe_from_hex(base_y));
        let prepared = prepare(base, beta, plan.built_mask);
        let seed_row = expected_seed(&seed_panel["bases"], base_x, base_y);
        for (seed, point) in prepared.iter().enumerate() {
            if plan.built_mask & (1 << seed) == 0 {
                continue;
            }
            let expected_point = &seed_row["seeds"][seed];
            let (x, y) = point.to_affine().expect("built seed nonidentity");
            assert_eq!(fe_hex(x), expected_point[0].as_str().expect("seed x"));
            assert_eq!(fe_hex(y), expected_point[1].as_str().expect("seed y"));
            seed_checks += 1;
        }
        let (output, counts) = evaluate_mode(&plan.digits, &prepared, beta, false, true);
        exceptional_adds += counts.exceptional_cached_adds;
        if case["expected_identity"].as_bool().unwrap_or(false) {
            assert!(output.is_identity());
        } else {
            let (x, y) = output.to_affine().expect("scalar output");
            assert_eq!(
                fe_hex(x),
                case["expected_x_hex"].as_str().expect("output x")
            );
            assert_eq!(
                fe_hex(y),
                case["expected_y_hex"].as_str().expect("output y")
            );
        }
        if !plan.digits.is_empty() {
            let solo = counts.tau_steps - 2 * counts.tau_pairs;
            let charged = plan.preparation
                + 10 * counts.tau_pairs
                + 6 * solo
                + 11 * counts.mixed_adds
                + 14 * counts.general_adds
                + 2 * counts.cache_entries;
            assert_eq!(charged, plan.total);
        }
        total += plan.total;
        peak_states = peak_states.max(plan.peak_states);
        peak_carry_norm = peak_carry_norm.max(plan.peak_carry_norm);
    }
    assert_eq!(panel["selective_total"].as_u64(), Some(total as u64));
    println!("{{\"verified\":true,\"fixture\":\"{name}\",\"cases\":{},\"seed_checks\":{seed_checks},\"output_checks\":{},\"selected_M_plus_S\":{total},\"peak_dp_states\":{peak_states},\"peak_carry_norm\":{peak_carry_norm},\"exceptional_cached_adds\":{exceptional_adds},\"cpu_speedup_claim\":null}}",
             cases.len(), cases.len());
}

pub(super) fn benchmark_case(fixture_path: &str, index: usize, timed: bool) {
    let fixture: Value =
        serde_json::from_slice(&fs::read(fixture_path).expect("read scalar fixture"))
            .expect("parse scalar fixture");
    let case = &fixture["cases"].as_array().expect("cases")[index];
    let base_x = case["base_x_hex"].as_str().expect("base x");
    let base_y = case["base_y_hex"].as_str().expect("base y");
    let scalar_hex = case["scalar_hex"].as_str().expect("scalar");
    let expected = if case["expected_identity"].as_bool().unwrap_or(false) {
        "identity".to_owned()
    } else {
        format!(
            "{}:{}",
            case["expected_x_hex"].as_str().expect("expected x"),
            case["expected_y_hex"].as_str().expect("expected y")
        )
    };
    let beta = fe_from_hex(fixture["beta_hex"].as_str().expect("beta"));
    LazyLock::force(&LATTICE);
    LazyLock::force(&DIGIT_TABLE);
    LazyLock::force(&LINKED_DIGIT_TABLE);
    let start = Instant::now();
    let scalar = big_from_hex(scalar_hex);
    let base = J::affine(fe_from_hex(base_x), fe_from_hex(base_y));
    let (a, b) = short_representative(&scalar);
    let plan = recode(a, b);
    let prepared = prepare(base, beta, plan.built_mask);
    let (point, _) = evaluate_mode(&plan.digits, &prepared, beta, false, true);
    let actual = match point.to_affine() {
        None => "identity".to_owned(),
        Some((x, y)) => format!("{}:{}", fe_hex(x), fe_hex(y)),
    };
    assert_eq!(actual, expected);
    let elapsed_ms = start.elapsed().as_secs_f64() * 1000.0;
    if timed {
        println!("online_ms={elapsed_ms:.6} verified=1 curve=secp256k1 base_x={base_x} base_y={base_y} scalar={scalar_hex} point={actual} mode=selective_mixed source_M_plus_S={}", plan.total);
    } else {
        println!("verified=1 curve=secp256k1 base_x={base_x} base_y={base_y} scalar={scalar_hex} point={actual} mode=selective_mixed source_M_plus_S={}", plan.total);
    }
}
