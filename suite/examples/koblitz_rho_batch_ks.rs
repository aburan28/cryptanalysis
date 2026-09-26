#![recursion_limit = "256"]
//! Kuhn–Struik batched Pollard rho over the Koblitz public-fixture corpus.
//!
//! Arithmetic, canonicalization and partition are copied verbatim from
//! `koblitz_rho_fixture.rs` (packed backend) so per-step cost matches the
//! independent comparator. Jumps are multiples of G only and one
//! distinguished-point table persists across targets, so later targets can
//! finish on the trails of earlier, already-solved ones. Targets are derived
//! exactly as the frozen `packed <batch_seed>` independent runs derive them.

use cryptanalysis_suite::binary_ecc::BinaryPoint;
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::KoblitzCurve;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use serde_json::json;
use std::collections::{BTreeSet, HashMap};
use std::fs;
use std::time::Instant;

const JUMPS: usize = 32;
const PRECOMPUTED: u32 = u32::MAX;

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

/// A jump `[a]G`: the walk's jumps are multiples of the generator only, so
/// they carry no `Q` coefficient.
#[derive(Clone, Copy)]
struct RawJump {
    point: RawPoint,
    a: u64,
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

fn raw_on_curve(curve: &KoblitzCurve, point: RawPoint) -> bool {
    let RawPoint::Affine { x, y } = point else {
        return true;
    };
    let x_squared = raw_square(curve, x);
    let left = raw_square(curve, y) ^ raw_mul_field(curve, x, y);
    let right = raw_mul_field(curve, x_squared, x) ^ if curve.a == 1 { x_squared } else { 0 } ^ 1;
    left == right
}

fn public_point_targets(curve: &KoblitzCurve, modulus: u64) -> Option<Vec<RawPoint>> {
    let path = std::env::var("KIC_RHO_TARGET_POINTS_JSONL").ok()?;
    let input = fs::read_to_string(path).expect("rho point target file must be readable");
    let limit = 1u64 << curve.n;
    let points = input
        .lines()
        .map(|line| {
            let [x, y]: [u64; 2] =
                serde_json::from_str(line).expect("rho point target must be JSON [x,y]");
            assert!(
                x < limit && y < limit,
                "rho point coordinates must be field elements"
            );
            let point = RawPoint::Affine { x, y };
            assert!(
                raw_on_curve(curve, point),
                "rho point target must be on the curve"
            );
            assert_eq!(
                raw_scalar_mul(curve, point, modulus),
                RawPoint::Infinity,
                "rho point target must belong to the prime-order subgroup"
            );
            point
        })
        .collect::<Vec<_>>();
    Some(points)
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

fn dp_hash(point: RawPoint) -> u64 {
    let (_, x, y) = raw_key(point);
    let mut v = x.rotate_left(7) ^ y ^ 0x2545_f491_4f6c_dd1d;
    v ^= v >> 33;
    v = v.wrapping_mul(0xff51_afd7_ed55_8ccd);
    v ^= v >> 33;
    v = v.wrapping_mul(0xc4ce_b9fe_1a85_ec53);
    v ^ (v >> 33)
}

#[derive(Clone, Copy)]
struct Trail {
    a: u64,
    b: u64,
    target: u32,
}

fn main() {
    let args: Vec<_> = std::env::args().collect();
    assert_eq!(
        args.len(),
        6,
        "usage: <n> <a> <mode> <fixtures> <batch_seed>"
    );
    let n: u32 = args[1].parse().unwrap();
    let a: u8 = args[2].parse().unwrap();
    let mode = Quotient::parse(&args[3]);
    let fixtures: u32 = args[4].parse().unwrap();
    let batch_seed: u64 = args[5].parse().unwrap();
    let dp_bits: u32 = std::env::var("KIC_RHO_DP_BITS")
        .map(|v| v.parse().expect("KIC_RHO_DP_BITS must be an integer"))
        .unwrap_or(8);
    assert!(dp_bits < 32);
    let shared_corpus = std::env::var("KIC_RHO_BATCH_CORPUS").ok();
    assert!(matches!(n, 7 | 11 | 13 | 17 | 19 | 23 | 37 | 41 | 53));
    assert!(fixtures > 0);

    let process_started = Instant::now();
    let curve = KoblitzCurve::new(a, n).expect("frozen exact rung must construct");
    let modulus = curve.subgroup_order.to_u64_digits()[0];
    let lambda = curve.lambda.to_u64_digits()[0];
    let automorphisms = match mode {
        Quotient::Ordinary => 1,
        Quotient::Negation => 2,
        Quotient::SignedFrobenius => signed_automorphism_size(lambda, modulus, n),
    };
    let generator = raw_point(curve.generator());
    let point_targets = public_point_targets(&curve, modulus);
    if let Some(points) = &point_targets {
        assert_eq!(
            points.len(),
            fixtures as usize,
            "rho point target count must equal fixtures argument"
        );
    }
    let mut charges = Charges::default();

    let setup_started = Instant::now();
    let jump_digest =
        blake3::hash(format!("KIC-KS-BATCH-JUMPS-v1|{n}|{a}|{batch_seed}").as_bytes());
    let mut jump_rng = StdRng::seed_from_u64(u64::from_le_bytes(
        jump_digest.as_bytes()[..8].try_into().unwrap(),
    ));
    let jumps: Vec<RawJump> = (0..JUMPS)
        .map(|_| loop {
            let s = jump_rng.gen_range(1..modulus);
            charges.scalar_multiplications += 1;
            let point = raw_scalar_mul(&curve, generator, s);
            if point != RawPoint::Infinity {
                break RawJump { point, a: s };
            }
        })
        .collect();
    let setup_ms = setup_started.elapsed().as_secs_f64() * 1000.0;

    let dp_mask = (1u64 << dp_bits) - 1;
    let walk_cap = 8u64 << dp_bits;
    let ideal_single =
        (std::f64::consts::PI * modulus as f64 / (2.0 * automorphisms as f64)).sqrt();
    let step_cap = (ideal_single.ceil() as u64)
        .saturating_mul(2_000)
        .max(1_000_000);
    let mut table: HashMap<(u8, u64, u64), Trail> = HashMap::new();
    let mut solved: Vec<u64> = Vec::with_capacity(fixtures as usize);

    // Bernstein–Lange precomputation: G-only walks whose distinguished points
    // have known logarithms. Charged separately from the target loop.
    let precompute_walks: u64 = std::env::var("KIC_RHO_PRECOMPUTE_WALKS")
        .map(|v| {
            v.parse()
                .expect("KIC_RHO_PRECOMPUTE_WALKS must be an integer")
        })
        .unwrap_or(0);
    let precompute_started = Instant::now();
    let mut precompute_steps = 0u64;
    if precompute_walks > 0 {
        let digest = blake3::hash(format!("KIC-KS-PRECOMPUTE-v1|{n}|{a}|{batch_seed}").as_bytes());
        let mut rng = StdRng::seed_from_u64(u64::from_le_bytes(
            digest.as_bytes()[..8].try_into().unwrap(),
        ));
        let stride_a = rng.gen_range(1..modulus);
        let stride = raw_scalar_mul(&curve, generator, stride_a);
        let mut cursor_a = rng.gen_range(1..modulus);
        let mut cursor = raw_scalar_mul(&curve, generator, cursor_a);
        'pre: for _ in 0..precompute_walks {
            let (start, start_a) = (cursor, cursor_a);
            cursor = raw_add(&curve, cursor, stride);
            cursor_a = (cursor_a + stride_a) % modulus;
            if start == RawPoint::Infinity {
                continue;
            }
            let mut state = raw_canonicalize(
                &curve,
                RawState {
                    point: start,
                    a: start_a,
                    b: 0,
                },
                mode,
                modulus,
                lambda,
                &mut charges,
            );
            let mut previous = [RawPoint::Infinity; 4];
            let mut length = 0u64;
            while dp_hash(state.point) & dp_mask != 0 {
                let jump = &jumps[raw_partition(state.point)];
                let next = raw_canonicalize(
                    &curve,
                    RawState {
                        point: raw_add(&curve, state.point, jump.point),
                        a: (state.a + jump.a) % modulus,
                        b: 0,
                    },
                    mode,
                    modulus,
                    lambda,
                    &mut charges,
                );
                precompute_steps += 1;
                length += 1;
                if next.point == state.point || previous.contains(&next.point) || length > walk_cap
                {
                    continue 'pre;
                }
                previous = [state.point, previous[0], previous[1], previous[2]];
                state = next;
            }
            table.entry(raw_key(state.point)).or_insert(Trail {
                a: state.a,
                b: 0,
                target: PRECOMPUTED,
            });
        }
    }
    let precompute_ms = precompute_started.elapsed().as_secs_f64() * 1000.0;
    let freeze_table = std::env::var("KIC_RHO_FREEZE_TABLE").is_ok_and(|v| v == "1");
    let precompute_table_entries = table.len();
    let mut total_steps = 0u64;
    let mut cross_solves = 0u32;

    for index in 0..fixtures {
        let material = match &shared_corpus {
            Some(corpus) => {
                format!("KIC-SHARED-PUBLIC-FIXTURE-v1|{n}|{a}|{corpus}|{batch_seed}|{index}")
            }
            None => format!(
                "TASK-KIC-DIRECT-BATCH-20260910|rho|{n}|{a}|{}|{batch_seed}|{index}",
                mode.name()
            ),
        };
        let digest = blake3::hash(material.as_bytes());
        let seed = u64::from_le_bytes(digest.as_bytes()[..8].try_into().unwrap());
        let mut rng = StdRng::seed_from_u64(seed);
        // Consume the same RNG word in both modes, so the walk schedule remains
        // frozen even though a point-only run has no target discrete-log label.
        let generated_d0 = rng.gen_range(1..modulus);
        let started = Instant::now();
        let q = if let Some(points) = &point_targets {
            points[index as usize]
        } else {
            charges.scalar_multiplications += 1;
            raw_scalar_mul(&curve, generator, generated_d0)
        };
        let table_before = table.len();
        // Successive walk starts step by a fixed stride: one addition per walk
        // instead of a fresh scalar multiplication.
        let stride_a = rng.gen_range(1..modulus);
        let stride = raw_scalar_mul(&curve, generator, stride_a);
        let mut cursor_a = rng.gen_range(0..modulus);
        let mut cursor = raw_add(&curve, raw_scalar_mul(&curve, generator, cursor_a), q);
        charges.scalar_multiplications += 2;
        charges.group_additions += 1;

        let mut steps = 0u64;
        let mut walks = 0u64;
        let mut fruitless = 0u64;
        let mut capped = 0u64;
        let mut wasted_merges = 0u64;
        let mut recovered = None;
        let mut via_target = None;
        'walks: while steps < step_cap {
            walks += 1;
            let start = cursor;
            let start_a = cursor_a;
            cursor = raw_add(&curve, cursor, stride);
            cursor_a = (cursor_a + stride_a) % modulus;
            charges.group_additions += 1;
            if start == RawPoint::Infinity {
                continue;
            }
            let mut state = raw_canonicalize(
                &curve,
                RawState {
                    point: start,
                    a: start_a,
                    b: 1,
                },
                mode,
                modulus,
                lambda,
                &mut charges,
            );
            let mut previous = [RawPoint::Infinity; 4];
            let mut length = 0u64;
            while dp_hash(state.point) & dp_mask != 0 {
                let jump = &jumps[raw_partition(state.point)];
                charges.partition_hashes += 1;
                let next = RawState {
                    point: raw_add(&curve, state.point, jump.point),
                    a: (state.a + jump.a) % modulus,
                    b: state.b,
                };
                charges.group_additions += 1;
                let next = raw_canonicalize(&curve, next, mode, modulus, lambda, &mut charges);
                steps += 1;
                length += 1;
                if next.point == state.point || previous.contains(&next.point) {
                    fruitless += 1;
                    continue 'walks;
                }
                if length > walk_cap {
                    capped += 1;
                    continue 'walks;
                }
                previous = [state.point, previous[0], previous[1], previous[2]];
                state = next;
            }
            let key = raw_key(state.point);
            charges.table_queries += 1;
            let Some(&hit) = table.get(&key) else {
                if !freeze_table {
                    table.insert(
                        key,
                        Trail {
                            a: state.a,
                            b: state.b,
                            target: index,
                        },
                    );
                    charges.table_inserts += 1;
                }
                continue;
            };
            // Both trails reach this point: a + b·d = a' + b'·d' with d' known or = d.
            let candidate = if hit.target == index {
                let denominator = sub_mod(state.b, hit.b, modulus);
                inverse_mod(denominator, modulus)
                    .map(|inv| mul_mod(sub_mod(hit.a, state.a, modulus), inv, modulus))
            } else {
                let base = if hit.target == PRECOMPUTED {
                    0
                } else {
                    solved[hit.target as usize]
                };
                let known =
                    (hit.a as u128 + mul_mod(hit.b, base, modulus) as u128) % modulus as u128;
                inverse_mod(state.b, modulus)
                    .map(|inv| mul_mod(sub_mod(known as u64, state.a, modulus), inv, modulus))
            };
            let Some(candidate) = candidate else {
                wasted_merges += 1;
                continue;
            };
            charges.scalar_multiplications += 1;
            if raw_scalar_mul(&curve, generator, candidate) == q {
                recovered = Some(candidate);
                via_target = Some(hit.target);
                break;
            }
            charges.failed_collisions += 1;
        }
        let solve_ms = started.elapsed().as_secs_f64() * 1000.0;
        let recovered = recovered.expect("batched rho exceeded the per-target step cap");
        if point_targets.is_none() {
            assert_eq!(recovered, generated_d0);
        }
        let via = via_target.unwrap();
        if via != index {
            cross_solves += 1;
        }
        solved.push(recovered);
        total_steps += steps;
        let q_key = raw_key(q);
        println!(
            "{}",
            json!({
                "kind":"rho_ks_batch_fixture",
                "evidence_class":"measured_rho_observation",
                "n":n,"a":a,"quotient_mode":mode.name(),"automorphism_size":automorphisms,
                "fixture_index":index,"fixture_seed":seed,"batch_seed":batch_seed,
                "target_source":if point_targets.is_some() {"explicit_public_points"} else {"derived_known_scalar"},
                "published_fixture_scalar":point_targets.is_none().then_some(generated_d0),
                "recovered_fixture_scalar":recovered,
                "published_q":[q_key.1,q_key.2],"verified":true,
                "solved_via_target":via,"solved_via_precomputed":via == PRECOMPUTED,"cross_target_solve":via != index,
                "walk_steps":steps,"walks":walks,"fruitless_two_cycles":fruitless,
                "capped_walks":capped,"wasted_merges":wasted_merges,
                "table_entries_before":table_before,"table_entries_after":table.len(),
                "total_ms":solve_ms,
                "ideal_independent_steps":ideal_single,
            })
        );
    }
    let process_ms = process_started.elapsed().as_secs_f64() * 1000.0;
    println!(
        "{}",
        json!({
            "kind":"rho_ks_batch_summary","producer_version":"v4_point_input",
            "n":n,"a":a,"quotient_mode":mode.name(),"automorphism_size":automorphisms,
            "fixtures":fixtures,"batch_seed":batch_seed,"corpus":shared_corpus,"dp_bits":dp_bits,"jump_count":JUMPS,
            "target_source":if point_targets.is_some() {"explicit_public_points"} else {"derived_known_scalar"},
            "all_verified":true,"cross_target_solves":cross_solves,
            "total_walk_steps":total_steps,"table_entries":table.len(),
            "table_payload_lower_bound_bytes":table.len() * (1 + 4 * std::mem::size_of::<u64>()),
            "setup_ms":setup_ms,"in_process_ms":process_ms,
            "precompute_walks":precompute_walks,"freeze_table":freeze_table,"precompute_steps":precompute_steps,"precompute_ms":precompute_ms,"precompute_table_entries":precompute_table_entries,
            "charges":{
                "group_additions":charges.group_additions,
                "scalar_multiplications":charges.scalar_multiplications,
                "canonicalizations":charges.canonicalizations,
                "frobenius_maps":charges.frobenius_maps,
                "negations_examined":charges.negations_examined,
                "partition_hashes":charges.partition_hashes,
                "table_queries":charges.table_queries,
                "table_inserts":charges.table_inserts,
                "failed_collisions":charges.failed_collisions
            },
            "scope":if point_targets.is_some() {
                "public synthetic point-only targets; no scalar labels supplied to producer"
            } else {
                "published synthetic toy fixtures; no external point, unknown scalar, or production key"
            }
        })
    );
}
