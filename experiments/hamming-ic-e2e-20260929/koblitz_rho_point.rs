#![recursion_limit = "256"]
//! One supplied-point Pollard-rho reference for the N53 W3-root IC comparison.
//!
//! The CLI accepts a public point and a walk seed, never its known fixture
//! scalar. The packed walk recovers and independently verifies that scalar.

use crypto_lib::binary_ecc::curve::point_neg;
use crypto_lib::binary_ecc::BinaryPoint;
use crypto_lib::cryptanalysis::koblitz_index_calculus::KoblitzCurve;
use num_bigint::BigUint;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use serde_json::json;
use std::collections::{BTreeSet, HashMap};
use std::time::Instant;

const TASK_ID: &str = "TASK-KIC-SAT-RHO-CROSSOVER-20260909";
const JUMPS: usize = 32;
const MAX_RESTARTS: u64 = 128;
/// Fruitless-collision restart budget for larger fields (n≥41).
const MAX_RESTARTS_LARGE: u64 = 100_000;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Quotient {
    Ordinary,
    Negation,
    SignedFrobenius,
}

impl Quotient {
    fn parse(value: &str) -> Self {
        match value {
            "ordinary" => Self::Ordinary,
            "negation_only" => Self::Negation,
            "signed_frobenius" => Self::SignedFrobenius,
            _ => panic!("unknown quotient mode {value}"),
        }
    }

    fn name(self) -> &'static str {
        match self {
            Self::Ordinary => "ordinary",
            Self::Negation => "negation_only",
            Self::SignedFrobenius => "signed_frobenius",
        }
    }

    fn uses_negation(self) -> bool {
        self != Self::Ordinary
    }
}

#[derive(Clone)]
struct State {
    point: BinaryPoint,
    a: u64,
    b: u64,
}

#[derive(Clone)]
struct Jump {
    point: BinaryPoint,
    a: u64,
    b: u64,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum RawPoint {
    Infinity,
    Affine { x: u64, y: u64 },
}

#[derive(Clone, Copy)]
struct RawState {
    point: RawPoint,
    a: u64,
    b: u64,
}

#[derive(Clone, Copy)]
struct RawJump {
    point: RawPoint,
    a: u64,
    b: u64,
}

#[derive(Default)]
struct Charges {
    group_additions: u64,
    scalar_multiplications: u64,
    canonicalizations: u64,
    frobenius_maps: u64,
    negations_examined: u64,
    partition_hashes: u64,
    table_queries: u64,
    table_inserts: u64,
    failed_collisions: u64,
    fruitless_cycle_restarts: u64,
}

fn point_key(point: &BinaryPoint) -> (u8, u64, u64) {
    match point {
        BinaryPoint::Infinity => (0, 0, 0),
        BinaryPoint::Affine { x, y } => (
            1,
            x.raw_bits().first().copied().unwrap_or(0),
            y.raw_bits().first().copied().unwrap_or(0),
        ),
    }
}

fn raw_point(point: &BinaryPoint) -> RawPoint {
    match point {
        BinaryPoint::Infinity => RawPoint::Infinity,
        BinaryPoint::Affine { x, y } => RawPoint::Affine {
            x: x.raw_bits().first().copied().unwrap_or(0),
            y: y.raw_bits().first().copied().unwrap_or(0),
        },
    }
}

fn raw_key(point: RawPoint) -> (u8, u64, u64) {
    match point {
        RawPoint::Infinity => (0, 0, 0),
        RawPoint::Affine { x, y } => (1, x, y),
    }
}

fn raw_reduce(curve: &KoblitzCurve, mut wide: u128) -> u64 {
    if curve.n <= 31 && wide <= u64::MAX as u128 {
        let mut narrow = wide as u64;
        let mask = (1u64 << curve.n) - 1;
        while narrow >> curve.n != 0 {
            let high = narrow >> curve.n;
            narrow &= mask;
            for &term in &curve.curve.irreducible.low_terms {
                narrow ^= high << term;
            }
        }
        return narrow;
    }
    let mask = (1u128 << curve.n) - 1;
    while wide >> curve.n != 0 {
        let high = wide >> curve.n;
        wide &= mask;
        for &term in &curve.curve.irreducible.low_terms {
            wide ^= high << term;
        }
    }
    wide as u64
}

fn raw_square(curve: &KoblitzCurve, value: u64) -> u64 {
    if curve.n <= 31 {
        let mut wide = value;
        wide = (wide | (wide << 16)) & 0x0000_ffff_0000_ffff;
        wide = (wide | (wide << 8)) & 0x00ff_00ff_00ff_00ff;
        wide = (wide | (wide << 4)) & 0x0f0f_0f0f_0f0f_0f0f;
        wide = (wide | (wide << 2)) & 0x3333_3333_3333_3333;
        wide = (wide | (wide << 1)) & 0x5555_5555_5555_5555;
        return raw_reduce(curve, wide as u128);
    }
    raw_reduce(curve, carryless_product(value, value))
}

fn carryless_product_software(left: u64, right: u64) -> u128 {
    let mut product = 0u128;
    let mut value = right;
    while value != 0 {
        let bit = value.trailing_zeros();
        product ^= (left as u128) << bit;
        value &= value - 1;
    }
    product
}

#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "aes")]
unsafe fn carryless_product_pmull(left: u64, right: u64) -> u128 {
    std::arch::aarch64::vmull_p64(left, right)
}

fn carryless_product(left: u64, right: u64) -> u128 {
    #[cfg(target_arch = "aarch64")]
    if std::arch::is_aarch64_feature_detected!("aes") {
        // SAFETY: the runtime feature check above proves PMULL availability.
        return unsafe { carryless_product_pmull(left, right) };
    }
    carryless_product_software(left, right)
}

fn raw_mul_field(curve: &KoblitzCurve, left: u64, right: u64) -> u64 {
    raw_reduce(curve, carryless_product(left, right))
}

fn raw_inverse(curve: &KoblitzCurve, value: u64) -> u64 {
    assert_ne!(value, 0);
    let exponent = (1u64 << curve.n) - 2;
    let mut result = 1u64;
    let mut base = value;
    for bit in 0..curve.n {
        if (exponent >> bit) & 1 == 1 {
            result = raw_mul_field(curve, result, base);
        }
        base = raw_square(curve, base);
    }
    result
}

fn raw_neg(point: RawPoint) -> RawPoint {
    match point {
        RawPoint::Infinity => RawPoint::Infinity,
        RawPoint::Affine { x, y } => RawPoint::Affine { x, y: y ^ x },
    }
}

fn raw_double(curve: &KoblitzCurve, point: RawPoint) -> RawPoint {
    let RawPoint::Affine { x, y } = point else {
        return RawPoint::Infinity;
    };
    if x == 0 {
        return RawPoint::Infinity;
    }
    let lambda = x ^ raw_mul_field(curve, y, raw_inverse(curve, x));
    let x3 = raw_square(curve, lambda) ^ lambda ^ curve.a as u64;
    let y3 = raw_square(curve, x) ^ raw_mul_field(curve, lambda ^ 1, x3);
    RawPoint::Affine { x: x3, y: y3 }
}

fn raw_add(curve: &KoblitzCurve, left: RawPoint, right: RawPoint) -> RawPoint {
    match (left, right) {
        (RawPoint::Infinity, point) | (point, RawPoint::Infinity) => point,
        (RawPoint::Affine { x: x1, y: y1 }, RawPoint::Affine { x: x2, y: y2 }) => {
            if x1 == x2 {
                return if y1 ^ y2 == x1 {
                    RawPoint::Infinity
                } else {
                    raw_double(curve, left)
                };
            }
            let lambda = raw_mul_field(curve, y1 ^ y2, raw_inverse(curve, x1 ^ x2));
            let x3 = raw_square(curve, lambda) ^ lambda ^ x1 ^ x2 ^ curve.a as u64;
            let y3 = raw_mul_field(curve, lambda, x1 ^ x3) ^ x3 ^ y1;
            RawPoint::Affine { x: x3, y: y3 }
        }
    }
}

fn raw_scalar_mul(curve: &KoblitzCurve, point: RawPoint, scalar: u64) -> RawPoint {
    let mut result = RawPoint::Infinity;
    for bit in (0..64 - scalar.leading_zeros()).rev() {
        result = raw_double(curve, result);
        if (scalar >> bit) & 1 == 1 {
            result = raw_add(curve, result, point);
        }
    }
    result
}

fn mul_mod(left: u64, right: u64, modulus: u64) -> u64 {
    ((left as u128 * right as u128) % modulus as u128) as u64
}

fn signed_automorphism_size(lambda: u64, modulus: u64, n: u32) -> usize {
    let mut scalars = BTreeSet::new();
    let mut current = 1u64;
    for _ in 0..n {
        scalars.insert(current);
        scalars.insert((modulus - current) % modulus);
        current = mul_mod(current, lambda, modulus);
    }
    assert_eq!(current, 1);
    scalars.len()
}

fn sub_mod(left: u64, right: u64, modulus: u64) -> u64 {
    if left >= right {
        left - right
    } else {
        modulus - (right - left)
    }
}

fn inverse_mod(value: u64, modulus: u64) -> Option<u64> {
    if value == 0 {
        return None;
    }
    let (mut old_r, mut r) = (modulus as i128, value as i128);
    let (mut old_t, mut t) = (0i128, 1i128);
    while r != 0 {
        let quotient = old_r / r;
        (old_r, r) = (r, old_r - quotient * r);
        (old_t, t) = (t, old_t - quotient * t);
    }
    (old_r == 1).then_some(old_t.rem_euclid(modulus as i128) as u64)
}

fn canonicalize(
    curve: &KoblitzCurve,
    state: State,
    mode: Quotient,
    modulus: u64,
    lambda: u64,
    charges: &mut Charges,
) -> State {
    charges.canonicalizations += 1;
    if state.point == BinaryPoint::Infinity || mode == Quotient::Ordinary {
        return state;
    }

    let powers = if mode == Quotient::SignedFrobenius {
        curve.n
    } else {
        1
    };
    let mut point = state.point.clone();
    let mut multiplier = 1u64;
    let mut best_key = point_key(&point);
    let mut best_point = point.clone();
    let mut best_multiplier = multiplier;

    for exponent in 0..powers {
        let key = point_key(&point);
        if key < best_key {
            best_key = key;
            best_point = point.clone();
            best_multiplier = multiplier;
        }
        if mode.uses_negation() {
            charges.negations_examined += 1;
            let negative = point_neg(&point);
            let negative_key = point_key(&negative);
            if negative_key < best_key {
                best_key = negative_key;
                best_point = negative;
                best_multiplier = if multiplier == 0 {
                    0
                } else {
                    modulus - multiplier
                };
            }
        }
        if exponent + 1 < powers {
            point = curve.frobenius(&point);
            multiplier = mul_mod(multiplier, lambda, modulus);
            charges.frobenius_maps += 1;
        }
    }

    State {
        point: best_point,
        a: mul_mod(state.a, best_multiplier, modulus),
        b: mul_mod(state.b, best_multiplier, modulus),
    }
}

fn raw_canonicalize(
    curve: &KoblitzCurve,
    state: RawState,
    mode: Quotient,
    modulus: u64,
    lambda: u64,
    charges: &mut Charges,
) -> RawState {
    charges.canonicalizations += 1;
    if state.point == RawPoint::Infinity || mode == Quotient::Ordinary {
        return state;
    }
    let powers = if mode == Quotient::SignedFrobenius {
        curve.n
    } else {
        1
    };
    let mut point = state.point;
    let mut multiplier = 1u64;
    let mut best_key = raw_key(point);
    let mut best_point = point;
    let mut best_multiplier = multiplier;
    for exponent in 0..powers {
        let key = raw_key(point);
        if key < best_key {
            best_key = key;
            best_point = point;
            best_multiplier = multiplier;
        }
        if mode.uses_negation() {
            charges.negations_examined += 1;
            let negative = raw_neg(point);
            if raw_key(negative) < best_key {
                best_key = raw_key(negative);
                best_point = negative;
                best_multiplier = modulus - multiplier;
            }
        }
        if exponent + 1 < powers {
            point = match point {
                RawPoint::Infinity => RawPoint::Infinity,
                RawPoint::Affine { x, y } => RawPoint::Affine {
                    x: raw_square(curve, x),
                    y: raw_square(curve, y),
                },
            };
            multiplier = mul_mod(multiplier, lambda, modulus);
            charges.frobenius_maps += 1;
        }
    }
    RawState {
        point: best_point,
        a: mul_mod(state.a, best_multiplier, modulus),
        b: mul_mod(state.b, best_multiplier, modulus),
    }
}

fn partition(point: &BinaryPoint) -> usize {
    let (_, x, y) = point_key(point);
    let mut value = x ^ y.rotate_left(21) ^ 0x9e37_79b9_7f4a_7c15;
    value ^= value >> 30;
    value = value.wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value ^= value >> 27;
    value = value.wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^= value >> 31;
    value as usize % JUMPS
}

fn raw_partition(point: RawPoint) -> usize {
    let (_, x, y) = raw_key(point);
    let mut value = x ^ y.rotate_left(21) ^ 0x9e37_79b9_7f4a_7c15;
    value ^= value >> 30;
    value = value.wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value ^= value >> 27;
    value = value.wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^= value >> 31;
    value as usize % JUMPS
}

fn random_state(
    curve: &KoblitzCurve,
    q: &BinaryPoint,
    rng: &mut StdRng,
    modulus: u64,
    charges: &mut Charges,
) -> State {
    loop {
        let a = rng.gen_range(0..modulus);
        let b = rng.gen_range(0..modulus);
        charges.scalar_multiplications += 2;
        charges.group_additions += 1;
        let point = curve.add(
            &curve.mul(curve.generator(), &BigUint::from(a)),
            &curve.mul(q, &BigUint::from(b)),
        );
        if point != BinaryPoint::Infinity {
            return State { point, a, b };
        }
    }
}

fn make_jumps(
    curve: &KoblitzCurve,
    q: &BinaryPoint,
    rng: &mut StdRng,
    modulus: u64,
    charges: &mut Charges,
) -> Vec<Jump> {
    (0..JUMPS)
        .map(|_| loop {
            let state = random_state(curve, q, rng, modulus, charges);
            if state.point != BinaryPoint::Infinity {
                break Jump {
                    point: state.point,
                    a: state.a,
                    b: state.b,
                };
            }
        })
        .collect()
}

fn raw_random_state(
    curve: &KoblitzCurve,
    generator: RawPoint,
    q: RawPoint,
    rng: &mut StdRng,
    modulus: u64,
    charges: &mut Charges,
) -> RawState {
    loop {
        let a = rng.gen_range(0..modulus);
        let b = rng.gen_range(0..modulus);
        charges.scalar_multiplications += 2;
        charges.group_additions += 1;
        let point = raw_add(
            curve,
            raw_scalar_mul(curve, generator, a),
            raw_scalar_mul(curve, q, b),
        );
        if point != RawPoint::Infinity {
            return RawState { point, a, b };
        }
    }
}

fn raw_make_jumps(
    curve: &KoblitzCurve,
    generator: RawPoint,
    q: RawPoint,
    rng: &mut StdRng,
    modulus: u64,
    charges: &mut Charges,
) -> Vec<RawJump> {
    (0..JUMPS)
        .map(|_| {
            let state = raw_random_state(curve, generator, q, rng, modulus, charges);
            RawJump {
                point: state.point,
                a: state.a,
                b: state.b,
            }
        })
        .collect()
}

fn solve_fixture(
    curve: &KoblitzCurve,
    mode: Quotient,
    fixture_index: u64,
    fixture_seed: u64,
) -> serde_json::Value {
    let modulus = curve.subgroup_order.to_u64_digits()[0];
    let lambda = curve.lambda.to_u64_digits()[0];
    let signed_size = signed_automorphism_size(lambda, modulus, curve.n);
    let fixture_seed = std::env::var("KIC_RHO_WALK_SEED")
        .ok()
        .map(|value| {
            value
                .parse::<u64>()
                .expect("KIC_RHO_WALK_SEED must be an integer")
        })
        .unwrap_or(fixture_seed);
    let fixed_target = std::env::var("KIC_RHO_FIXED_TARGET_SCALAR")
        .ok()
        .map(|value| {
            value
                .parse::<u64>()
                .expect("KIC_RHO_FIXED_TARGET_SCALAR must be an integer")
        });
    let mut rng = StdRng::seed_from_u64(fixture_seed);
    let d0 = fixed_target.unwrap_or_else(|| rng.gen_range(1..modulus));
    assert!(
        (1..modulus).contains(&d0),
        "fixed target scalar must be in [1,r)"
    );
    let target_generation_started = Instant::now();
    let q = curve.mul(curve.generator(), &BigUint::from(d0));
    let target_generation_ms = target_generation_started.elapsed().as_secs_f64() * 1000.0;
    let mut charges = Charges {
        scalar_multiplications: 1,
        ..Charges::default()
    };
    let started = Instant::now();
    let jumps = make_jumps(curve, &q, &mut rng, modulus, &mut charges);
    let setup_ms = started.elapsed().as_secs_f64() * 1000.0;
    let walk_started = Instant::now();
    let mut table: HashMap<(u8, u64, u64), (u64, u64)> = HashMap::new();
    let ideal_steps = (std::f64::consts::PI * modulus as f64
        / (2.0
            * match mode {
                Quotient::Ordinary => 1.0,
                Quotient::Negation => 2.0,
                Quotient::SignedFrobenius => signed_size as f64,
            }))
    .sqrt();
    // Toy rungs finish with 200×√(πr/2A); n≥41 needs more headroom —
    // distinguished-point density and restart waste grow with the field.
    let safety = if curve.n >= 41 { 2_000 } else { 200 };
    let max_steps = (ideal_steps.ceil() as u64)
        .saturating_mul(safety)
        .max(10_000);
    let mut steps = 0u64;
    let mut restarts = 0u64;
    let mut recovered = None;
    let restart_cap = if curve.n >= 41 {
        MAX_RESTARTS_LARGE
    } else {
        MAX_RESTARTS
    };

    'restart: while restarts <= restart_cap && steps < max_steps {
        let initial = random_state(curve, &q, &mut rng, modulus, &mut charges);
        let mut state = canonicalize(curve, initial, mode, modulus, lambda, &mut charges);
        loop {
            let key = point_key(&state.point);
            charges.table_queries += 1;
            if let Some(&(old_a, old_b)) = table.get(&key) {
                let numerator = sub_mod(old_a, state.a, modulus);
                let denominator = sub_mod(state.b, old_b, modulus);
                if let Some(inverse) = inverse_mod(denominator, modulus) {
                    let candidate = mul_mod(numerator, inverse, modulus);
                    charges.scalar_multiplications += 1;
                    if curve.mul(curve.generator(), &BigUint::from(candidate)) == q {
                        recovered = Some(candidate);
                        break 'restart;
                    }
                    charges.failed_collisions += 1;
                } else {
                    charges.failed_collisions += 1;
                }
                charges.fruitless_cycle_restarts += 1;
                restarts += 1;
                continue 'restart;
            }
            table.insert(key, (state.a, state.b));
            charges.table_inserts += 1;
            let jump_index = partition(&state.point);
            charges.partition_hashes += 1;
            let jump = &jumps[jump_index];
            state = State {
                point: curve.add(&state.point, &jump.point),
                a: (state.a + jump.a) % modulus,
                b: (state.b + jump.b) % modulus,
            };
            charges.group_additions += 1;
            state = canonicalize(curve, state, mode, modulus, lambda, &mut charges);
            steps += 1;
            if steps >= max_steps {
                break 'restart;
            }
        }
    }
    let walk_ms = walk_started.elapsed().as_secs_f64() * 1000.0;
    let recovered = recovered.expect("public rho fixture exceeded the frozen step/restart cap");
    assert_eq!(recovered, d0);
    let table_entries = table.len();
    let generator_point_key = point_key(curve.generator());
    let q_point_key = point_key(&q);

    json!({
        "schema_version":"1.0",
        "task_id":TASK_ID,
        "kind":"rho_public_fixture",
        "evidence_class":"measured_rho_observation",
        "n":curve.n,
        "a":curve.curve.a.raw_bits().first().copied().unwrap_or(0),
        "subgroup_order":modulus,
        "lambda":lambda,
        "quotient_mode":mode.name(),
        "arithmetic_backend":"reference_f2m",
        "automorphism_size":match mode {
            Quotient::Ordinary => 1,
            Quotient::Negation => 2,
            Quotient::SignedFrobenius => signed_size as u32,
        },
        "fixture_index":fixture_index,
        "fixture_seed":fixture_seed,
        "published_fixture_scalar":d0,
        "target_generation_ms_excluded":target_generation_ms,
        "recovered_fixture_scalar":recovered,
        "generator":[generator_point_key.1,generator_point_key.2],
        "published_q":[q_point_key.1,q_point_key.2],
        "generator_point_key":[generator_point_key.1,generator_point_key.2],
        "published_q_point_key":[q_point_key.1,q_point_key.2],
        "field_modulus_low_terms":curve.curve.irreducible.low_terms,
        "verified":true,
        "ideal_steps":ideal_steps,
        "walk_steps":steps,
        "restarts":restarts,
        "jump_count":JUMPS,
        "distinguished_bits":0,
        "table_entries":table_entries,
        "table_payload_lower_bound_bytes":table_entries * (1 + 5 * std::mem::size_of::<u64>()),
        "setup_ms":setup_ms,
        "walk_ms":walk_ms,
        "total_ms":target_generation_ms + setup_ms + walk_ms,
        "charges":{
            "group_additions":charges.group_additions,
            "scalar_multiplications":charges.scalar_multiplications,
            "canonicalizations":charges.canonicalizations,
            "frobenius_maps":charges.frobenius_maps,
            "negations_examined":charges.negations_examined,
            "partition_hashes":charges.partition_hashes,
            "table_queries":charges.table_queries,
            "table_inserts":charges.table_inserts,
            "failed_collisions":charges.failed_collisions,
            "fruitless_cycle_restarts":charges.fruitless_cycle_restarts
        },
        "scope":"published synthetic toy fixture; no external point, unknown scalar, or production key"
    })
}

fn solve_public_point_packed(
    curve: &KoblitzCurve,
    mode: Quotient,
    walk_seed: u64,
    q: RawPoint,
) -> serde_json::Value {
    let modulus = curve.subgroup_order.to_u64_digits()[0];
    let lambda = curve.lambda.to_u64_digits()[0];
    let signed_size = signed_automorphism_size(lambda, modulus, curve.n);
    let generator = raw_point(curve.generator());
    let mut rng = StdRng::seed_from_u64(walk_seed);
    let mut charges = Charges::default();
    let online_started = Instant::now();
    let target_validation_started = Instant::now();
    assert_eq!(raw_scalar_mul(curve, q, modulus), RawPoint::Infinity);
    let target_validation_ms = target_validation_started.elapsed().as_secs_f64() * 1000.0;
    charges.scalar_multiplications += 1;
    let started = Instant::now();
    let jumps = raw_make_jumps(curve, generator, q, &mut rng, modulus, &mut charges);
    let setup_ms = started.elapsed().as_secs_f64() * 1000.0;
    let walk_started = Instant::now();
    let mut table: HashMap<(u8, u64, u64), (u64, u64)> = HashMap::new();
    let ideal_steps = (std::f64::consts::PI * modulus as f64
        / (2.0
            * match mode {
                Quotient::Ordinary => 1.0,
                Quotient::Negation => 2.0,
                Quotient::SignedFrobenius => signed_size as f64,
            }))
    .sqrt();
    // Toy rungs finish with 200×√(πr/2A); n≥41 needs more headroom —
    // distinguished-point density and restart waste grow with the field.
    let safety = if curve.n >= 41 { 2_000 } else { 200 };
    let max_steps = (ideal_steps.ceil() as u64)
        .saturating_mul(safety)
        .max(10_000);
    let mut steps = 0u64;
    let mut restarts = 0u64;
    let mut recovered = None;
    let restart_cap = if curve.n >= 41 {
        MAX_RESTARTS_LARGE
    } else {
        MAX_RESTARTS
    };

    'restart: while restarts <= restart_cap && steps < max_steps {
        let initial = raw_random_state(curve, generator, q, &mut rng, modulus, &mut charges);
        let mut state = raw_canonicalize(curve, initial, mode, modulus, lambda, &mut charges);
        loop {
            let key = raw_key(state.point);
            charges.table_queries += 1;
            if let Some(&(old_a, old_b)) = table.get(&key) {
                let numerator = sub_mod(old_a, state.a, modulus);
                let denominator = sub_mod(state.b, old_b, modulus);
                if let Some(inverse) = inverse_mod(denominator, modulus) {
                    let candidate = mul_mod(numerator, inverse, modulus);
                    charges.scalar_multiplications += 1;
                    if raw_scalar_mul(curve, generator, candidate) == q {
                        recovered = Some(candidate);
                        break 'restart;
                    }
                    charges.failed_collisions += 1;
                } else {
                    charges.failed_collisions += 1;
                }
                charges.fruitless_cycle_restarts += 1;
                restarts += 1;
                continue 'restart;
            }
            table.insert(key, (state.a, state.b));
            charges.table_inserts += 1;
            let jump = raw_make_jump_ref(&jumps, raw_partition(state.point));
            charges.partition_hashes += 1;
            state = RawState {
                point: raw_add(curve, state.point, jump.point),
                a: (state.a + jump.a) % modulus,
                b: (state.b + jump.b) % modulus,
            };
            charges.group_additions += 1;
            state = raw_canonicalize(curve, state, mode, modulus, lambda, &mut charges);
            steps += 1;
            if steps >= max_steps {
                break 'restart;
            }
        }
    }
    let walk_ms = walk_started.elapsed().as_secs_f64() * 1000.0;
    let recovered = recovered.expect("packed public-point rho exceeded cap");
    let validation_started = Instant::now();
    let reference_q = curve.mul(curve.generator(), &BigUint::from(recovered));
    assert_eq!(raw_point(&reference_q), q);
    let validation_ms = validation_started.elapsed().as_secs_f64() * 1000.0;
    let online_ms = online_started.elapsed().as_secs_f64() * 1000.0;
    let table_entries = table.len();
    let generator_point_key = raw_key(generator);
    let q_point_key = raw_key(q);

    json!({
        "schema_version":"1.0",
        "task_id":TASK_ID,
        "kind":"rho_public_point",
        "evidence_class":"measured_rho_observation",
        "n":curve.n,
        "a":curve.a,
        "subgroup_order":modulus,
        "lambda":lambda,
        "quotient_mode":mode.name(),
        "arithmetic_backend":"packed_u64_polynomial_basis",
        "automorphism_size":match mode {
            Quotient::Ordinary => 1,
            Quotient::Negation => 2,
            Quotient::SignedFrobenius => signed_size as u32,
        },
        "walk_seed":walk_seed,
        "recovered_scalar":recovered,
        "generator":[generator_point_key.1,generator_point_key.2],
        "target_point":[q_point_key.1,q_point_key.2],
        "generator_point_key":[generator_point_key.1,generator_point_key.2],
        "target_point_key":[q_point_key.1,q_point_key.2],
        "field_modulus_low_terms":curve.curve.irreducible.low_terms,
        "verified":true,
        "reference_group_validation":true,
        "ideal_steps":ideal_steps,
        "walk_steps":steps,
        "restarts":restarts,
        "jump_count":JUMPS,
        "distinguished_bits":0,
        "table_entries":table_entries,
        "table_payload_lower_bound_bytes":table_entries * (1 + 5 * std::mem::size_of::<u64>()),
        "setup_ms":setup_ms,
        "target_validation_ms":target_validation_ms,
        "walk_ms":walk_ms,
        "validation_ms":validation_ms,
        "online_ms":online_ms,
        "online_interval":"from supplied-point subgroup validation through independent recovered-scalar verification; launch and input loading excluded",
        "charges":{
            "group_additions":charges.group_additions,
            "scalar_multiplications":charges.scalar_multiplications,
            "canonicalizations":charges.canonicalizations,
            "frobenius_maps":charges.frobenius_maps,
            "negations_examined":charges.negations_examined,
            "partition_hashes":charges.partition_hashes,
            "table_queries":charges.table_queries,
            "table_inserts":charges.table_inserts,
            "failed_collisions":charges.failed_collisions,
            "fruitless_cycle_restarts":charges.fruitless_cycle_restarts
        },
        "scope":"one supplied published N53 point; no target scalar passed to solver"
    })
}

fn raw_make_jump_ref(jumps: &[RawJump], index: usize) -> &RawJump {
    &jumps[index]
}

fn main() {
    let args: Vec<_> = std::env::args().collect();
    assert_eq!(
        args.len(),
        6,
        "usage: <n> <a> <mode> <target_point.json> <walk_seed>"
    );
    let n: u32 = args[1].parse().unwrap();
    let a: u8 = args[2].parse().unwrap();
    let mode = Quotient::parse(&args[3]);
    let target: [u64; 2] = serde_json::from_slice(&std::fs::read(&args[4]).expect("target file"))
        .expect("target point must be a [x,y] array");
    let walk_seed: u64 = args[5].parse().unwrap();
    assert!(matches!(n, 7 | 11 | 13 | 17 | 19 | 23 | 37 | 41 | 53 | 61));
    let curve = KoblitzCurve::new(a, n).expect("frozen exact rung must construct");
    let q = RawPoint::Affine {
        x: target[0],
        y: target[1],
    };
    println!("{}", solve_public_point_packed(&curve, mode, walk_seed, q));
}

#[cfg(test)]
mod packed_tests {
    use super::*;

    #[test]
    fn packed_rho_arithmetic_matches_reference() {
        for (n, a) in [
            (7, 1),
            (11, 1),
            (13, 0),
            (17, 1),
            (19, 1),
            (23, 1),
            (37, 0),
            (41, 0),
        ] {
            let curve = KoblitzCurve::new(a, n).unwrap();
            let generator = raw_point(curve.generator());
            for scalar in 0..128u64 {
                assert_eq!(
                    raw_scalar_mul(&curve, generator, scalar),
                    raw_point(&curve.mul(curve.generator(), &BigUint::from(scalar)))
                );
            }
            let left = raw_scalar_mul(&curve, generator, 37);
            let right = raw_scalar_mul(&curve, generator, 91);
            assert_eq!(
                raw_add(&curve, left, right),
                raw_point(&curve.add(
                    &curve.mul(curve.generator(), &BigUint::from(37u64)),
                    &curve.mul(curve.generator(), &BigUint::from(91u64)),
                ))
            );
            let RawPoint::Affine { x, .. } = left else {
                panic!("nonzero scalar must be affine");
            };
            let reference = crypto_lib::binary_ecc::F2mElement::from_biguint(&BigUint::from(x), n);
            assert_eq!(
                raw_square(&curve, x),
                reference
                    .square(&curve.curve.irreducible)
                    .raw_bits()
                    .first()
                    .copied()
                    .unwrap_or(0)
            );
        }
    }
}
