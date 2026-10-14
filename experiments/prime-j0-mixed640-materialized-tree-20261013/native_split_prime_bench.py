#!/usr/bin/env python3
"""Generate the source-pinned split-prime scalar benchmark front door."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
BASE = HERE / "native_bench_cli.py"


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise ValueError(f"expected one source anchor, found {source.count(old)}: {old[:80]}")
    return source.replace(old, new, 1)


def replace_region(source: str, start: str, end: str, new: str) -> str:
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError(f"nonunique region anchors: {start[:60]}, {end[:60]}")
    first = source.index(start)
    last = source.index(end, first)
    return source[:first] + new + source[last:]


SPLIT_PRIME_RUST = r"""
const SPLIT_PRIME_NORM: i32 = 3301;
const SPLIT_PRIME_TAU_RESIDUE: i32 = 1576;
const SPLIT_PRIME_STEPS: usize = 21;
const SPLIT_PRIME_DIGIT_LIMIT: usize = 1650;
const SPLIT_PRIME_TERMINAL_LIMIT: usize = 663;

impl Signed192 {
    fn times_split_prime_small(self, factor: i32) -> Self {
        let mut limbs = [0u64; 3];
        let mut carry = 0u128;
        let magnitude = u128::from(factor.unsigned_abs());
        for (index, word) in self.limbs.iter().enumerate() {
            let product = u128::from(*word) * magnitude + carry;
            limbs[index] = product as u64;
            carry = product >> 64;
        }
        assert_eq!(carry, 0, "split-prime coefficient overflow");
        Self { negative: (self.negative != (factor < 0)) && limbs != [0; 3], limbs }
    }

    fn split_prime_table_index(self, limit: usize) -> (usize, bool) {
        assert_eq!(self.limbs[1], 0);
        assert_eq!(self.limbs[2], 0);
        let index = self.limbs[0] as usize;
        assert!(index <= limit, "split-prime terminal bound exceeded");
        (index, self.negative)
    }
}

fn split_prime_step(a: Signed192, b: Signed192) -> (Signed192, Signed192, i32) {
    // In Z[tau]/(86-21*tau), tau = 1576 mod 3301.
    let residue_word = a.add(b.times_split_prime_small(SPLIT_PRIME_TAU_RESIDUE));
    let (quotient, signed_rem, positive_rem) =
        residue_word.div_rem_small_radix(SPLIT_PRIME_NORM as u64);
    let digit = if positive_rem > SPLIT_PRIME_DIGIT_LIMIT {
        positive_rem as i32 - SPLIT_PRIME_NORM
    } else {
        positive_rem as i32
    };
    let k = quotient.adjust_small_radix_quotient(
        signed_rem, digit, SPLIT_PRIME_NORM);
    let next_a = k.times_split_prime_small(23).sub(b.times_split_prime_small(11));
    let next_b = k.times_split_prime_small(21).sub(b.times_split_prime_small(10));
    (next_a, next_b, digit)
}

struct SplitPrimeTables {
    digit_windows: Vec<Box<[U256Affine]>>,
    terminal_plain: Box<[U256Affine]>,
    terminal_tau: Box<[U256Affine]>,
    retained_bytes: usize,
}

fn split_prime_affine_row(base: Jacobian, max_abs: usize) -> Box<[U256Affine]> {
    affine_multiples(base, max_abs).iter().enumerate().map(|(position, &point)| {
        if position == 0 {
            U256Affine { x: super::U256::ZERO, y: super::U256::ZERO }
        } else {
            let affine = point.into_affine();
            U256Affine { x: super::hybrid_pair_mont(affine.x),
                         y: super::hybrid_pair_mont(affine.y) }
        }
    }).collect::<Vec<_>>().into_boxed_slice()
}

impl SplitPrimeTables {
    fn new() -> Self {
        let mut base = Jacobian::generator();
        let mut digit_windows = Vec::with_capacity(SPLIT_PRIME_STEPS);
        for _ in 0..SPLIT_PRIME_STEPS {
            digit_windows.push(split_prime_affine_row(base, SPLIT_PRIME_DIGIT_LIMIT));
            // pi = 86 - 21*tau. All of this is reusable table preparation.
            let ordinary = affine_multiples(base, 86).pop().unwrap();
            let tau = affine_multiples(base.tau(), 21).pop().unwrap().neg().into_affine();
            base = ordinary.add_mixed(tau).into_affine();
        }
        let terminal_plain = split_prime_affine_row(base, SPLIT_PRIME_TERMINAL_LIMIT);
        let terminal_tau = split_prime_affine_row(base.tau(), SPLIT_PRIME_TERMINAL_LIMIT);
        let entries = digit_windows.iter().map(|row| row.len()).sum::<usize>()
            + terminal_plain.len() + terminal_tau.len();
        assert_eq!(entries, 35_999);
        assert_eq!(size_of::<U256Affine>(), 64);
        let retained_bytes = entries * size_of::<U256Affine>()
            + size_of::<Self>()
            + digit_windows.capacity() * size_of::<Box<[U256Affine]>>();
        Self { digit_windows, terminal_plain, terminal_tau, retained_bytes }
    }
}

static SPLIT_PRIME_TABLES: LazyLock<SplitPrimeTables> =
    LazyLock::new(SplitPrimeTables::new);

pub(super) fn warm_split_prime_table() -> usize {
    std::sync::LazyLock::force(&super::EXACT_RECIPROCAL_CHECK);
    std::sync::LazyLock::force(&super::FIXED_SCALAR_LATTICE);
    SPLIT_PRIME_TABLES.retained_bytes
}

pub(super) fn multiply_u256_tau_split_prime_radix(
    scalar_words: [u64; 4],
) -> (String, (Signed192, Signed192), usize, usize, bool, usize, usize) {
    let scalar = super::Uint(scalar_words);
    let residue = if bool::from(scalar.ct_lt(&super::SCALAR_ORDER_WORDS)) {
        scalar
    } else {
        super::U256::sbb(&scalar, &super::SCALAR_ORDER_WORDS).0
    };
    let (representative, fallback, corner) =
        super::hexagonal_certified_fixed_choice_words(residue.0);
    let tables = &*SPLIT_PRIME_TABLES;
    let (mut a, mut b) = representative;
    let mut bucket = U256XYZZ::identity();
    let mut terms = 0usize;
    for row in &tables.digit_windows {
        let (next_a, next_b, digit) = split_prime_step(a, b);
        a = next_a;
        b = next_b;
        if digit != 0 {
            let mut point = row[digit.unsigned_abs() as usize];
            if digit < 0 { point.y = u256_sub(super::U256::ZERO, point.y); }
            bucket = bucket.add_mixed(point);
            terms += 1;
        }
    }
    for (coordinate, row) in [(a, &tables.terminal_plain),
                              (b, &tables.terminal_tau)] {
        let (position, negative) =
            coordinate.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);
        if position != 0 {
            let mut point = row[position];
            if negative { point.y = u256_sub(super::U256::ZERO, point.y); }
            bucket = bucket.add_mixed(point);
            terms += 1;
        }
    }
    let point = bucket.affine_hex_binary_inverse();
    (point, representative, terms.saturating_sub(1),
     tables.retained_bytes, fallback, corner, 0)
}

#[cfg(test)]
mod split_prime_tests {
    use super::*;

    fn independent_binary_point(scalar: &BigInt) -> Jacobian {
        let (_, bytes) = scalar.to_bytes_be();
        let generator = Jacobian::generator().into_affine();
        let mut point = Jacobian::identity();
        for byte in bytes {
            for bit in (0..8).rev() {
                point = point.double();
                if (byte >> bit) & 1 != 0 { point = point.add_mixed(generator); }
            }
        }
        point
    }

    #[test]
    fn split_prime_holdout_matches_independent_binary() {
        let panel: serde_json::Value = serde_json::from_str(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"), "/src/bin/mixed640_bench_fixture.json"
        ))).unwrap();
        let cases = panel["cases"].as_array().unwrap();
        assert_eq!(cases.len(), 128);
        for (index, case) in cases.iter().enumerate() {
            let scalar = BigInt::parse_bytes(
                case["scalar_hex"].as_str().unwrap().as_bytes(), 16).unwrap();
            let words = super::super::scalar_words_256(&scalar).unwrap();
            let candidate = multiply_u256_tau_split_prime_radix(words);
            assert_eq!(candidate.0, case["point_hex"].as_str().unwrap(),
                       "fixture {index}");
            let reduced = &scalar % &SCALAR_LATTICE.n;
            assert_eq!(candidate.0, independent_binary_point(&reduced).affine_hex(),
                       "independent binary {index}");
        }
        println!("split_prime_holdout_cases={} retained_bytes={}",
                 cases.len(), warm_split_prime_table());
    }
}

"""


FUSED_TERMINAL_REPLACEMENTS = {
    "    terminal_tau: Box<[U256Affine]>,\n":
        "    terminal_tau: Box<[U256Affine]>,\n"
        "    terminal_pairs: Box<[U256Affine]>,\n"
        "    terminal_row_start: [u16; 113],\n"
        "    terminal_row_min: [i16; 112],\n",
    "        let entries = digit_windows.iter().map(|row| row.len()).sum::<usize>()\n":
        "        let mut pair_digits = Vec::new();\n"
        "        let mut terminal_row_start = [0u16; 113];\n"
        "        let mut terminal_row_min = [0i16; 112];\n"
        "        for a in 0..112i32 {\n"
        "            terminal_row_start[a as usize] = pair_digits.len() as u16;\n"
        "            let mut first = true;\n"
        "            for b in -65..=65i32 {\n"
        "                let norm = a*a + 3*a*b + 3*b*b;\n"
        "                if norm >= 3136 || (a == 0 && b < 0) { continue; }\n"
        "                if first { terminal_row_min[a as usize] = b as i16; first = false; }\n"
        "                pair_digits.push((a as i16, b as i16));\n"
        "            }\n"
        "            assert!(!first);\n"
        "        }\n"
        "        terminal_row_start[112] = pair_digits.len() as u16;\n"
        "        assert_eq!(pair_digits.len(), 5680);\n"
        "        assert_eq!(pair_digits[0], (0, 0));\n"
        "        let terminal_pairs = build_u256_window(&pair_digits, base);\n"
        "        let entries = digit_windows.iter().map(|row| row.len()).sum::<usize>()\n",
    "        assert_eq!(entries, 35_999);":
        "        assert_eq!(entries, 35_999);",
    "            + size_of::<Self>()\n            + digit_windows.capacity()":
        "            + terminal_pairs.len() * size_of::<U256Affine>()\n"
        "            + size_of::<Self>()\n            + digit_windows.capacity()",
    "        Self { digit_windows, terminal_plain, terminal_tau, retained_bytes }":
        "        Self { digit_windows, terminal_plain, terminal_tau,\n"
        "               terminal_pairs, terminal_row_start, terminal_row_min, retained_bytes }",
    "    for (coordinate, row) in [(a, &tables.terminal_plain),\n":
        "    // The fused table covers the small terminal norm. Axis rows are\n"
        "    // retained for exact fallback under the original coordinate bound.\n"
        "    let (ai, aneg) = a.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);\n"
        "    let (bi, bneg) = b.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);\n"
        "    let signed_a = if aneg { -(ai as i64) } else { ai as i64 };\n"
        "    let signed_b = if bneg { -(bi as i64) } else { bi as i64 };\n"
        "    let terminal_norm = signed_a*signed_a + 3*signed_a*signed_b\n"
        "        + 3*signed_b*signed_b;\n"
        "    if terminal_norm < 3136 {\n"
        "        let negate = signed_a < 0 || (signed_a == 0 && signed_b < 0);\n"
        "        let ca = if negate { -signed_a } else { signed_a } as usize;\n"
        "        let cb = if negate { -signed_b } else { signed_b };\n"
        "        let row_start = tables.terminal_row_start[ca] as usize;\n"
        "        let row_offset = usize::try_from(\n"
        "            cb - i64::from(tables.terminal_row_min[ca])).unwrap();\n"
        "        let index = row_start + row_offset;\n"
        "        assert!(index < tables.terminal_row_start[ca + 1] as usize);\n"
        "        if index != 0 {\n"
        "            let mut point = tables.terminal_pairs[index];\n"
        "            if negate { point.y = u256_sub(super::U256::ZERO, point.y); }\n"
        "            bucket = bucket.add_mixed(point);\n"
        "            terms += 1;\n"
        "        }\n"
        "    } else {\n"
        "    for (coordinate, row) in [(a, &tables.terminal_plain),\n",
    "    let point = bucket.affine_hex_binary_inverse();":
        "    }\n"
        "    let point = bucket.affine_hex_binary_inverse();",
}


UNIT_STEP_RUST = r"""fn split_prime_unit_step(
    a: Signed192, b: Signed192, tables: &SplitPrimeTables,
) -> (Signed192, Signed192, usize, usize) {
    let residue_word = a.add(b.times_split_prime_small(SPLIT_PRIME_TAU_RESIDUE));
    let (quotient, signed_rem, residue) =
        residue_word.div_rem_small_radix(SPLIT_PRIME_NORM as u64);
    let packed = usize::from(tables.residue_codes[residue]);
    let index = packed / 6;
    let unit = packed % 6;
    let digit_quotient = i32::from(tables.digit_quotient[residue]);
    let carry = if signed_rem < 0 { 1 } else { 0 };
    let k = quotient.add(Signed192::from_i32(-digit_quotient - carry));
    let shifted_b = b.sub(Signed192::from_i32(i32::from(tables.digit_b[residue])));
    let next_a = k.times_split_prime_small(23).sub(shifted_b.times_split_prime_small(11));
    let next_b = k.times_split_prime_small(21).sub(shifted_b.times_split_prime_small(10));
    (next_a, next_b, index, unit)
}

"""


UNIT_ROW_RUST = r"""fn split_prime_orbit_row(base: Jacobian, seeds: &[i16])
    -> Box<[U256OrbitXAffine]> {
    let multiples = affine_multiples(base, 1064);
    seeds.iter().map(|&seed| {
        let point = if seed == 0 {
            U256Affine { x: super::U256::ZERO, y: super::U256::ZERO }
        } else {
            let affine = multiples[seed as usize].into_affine();
            U256Affine { x: super::hybrid_pair_mont(affine.x),
                         y: super::hybrid_pair_mont(affine.y) }
        };
        U256OrbitXAffine::from_affine(point)
    }).collect::<Vec<_>>().into_boxed_slice()
}

"""


UNIT_LUT_RUST = r"""        let mut residue_codes = vec![u16::MAX; SPLIT_PRIME_NORM as usize];
        let mut digit_b = vec![0i16; SPLIT_PRIME_NORM as usize];
        let mut digit_quotient = vec![0i16; SPLIT_PRIME_NORM as usize];
        let mut seeds = vec![0i16];
        residue_codes[0] = 0;
        for seed in 1..=SPLIT_PRIME_DIGIT_LIMIT as i32 {
            if residue_codes[seed as usize] != u16::MAX { continue; }
            let index = seeds.len();
            seeds.push(seed as i16);
            for (unit, (da, db)) in unit_images((seed, 0)).into_iter().enumerate() {
                let residue = (da + SPLIT_PRIME_TAU_RESIDUE * db)
                    .rem_euclid(SPLIT_PRIME_NORM) as usize;
                assert_eq!(residue_codes[residue], u16::MAX);
                residue_codes[residue] = (index * 6 + unit) as u16;
                digit_b[residue] = db as i16;
                digit_quotient[residue] =
                    ((da + SPLIT_PRIME_TAU_RESIDUE * db)
                        .div_euclid(SPLIT_PRIME_NORM)) as i16;
            }
        }
        assert_eq!(seeds.len(), 551);
        assert_eq!(*seeds.last().unwrap(), 1064);
        assert!(residue_codes.iter().all(|&code| code != u16::MAX));
"""


UNIT_RETAINED_RUST = r"""        let entries = digit_windows.iter().map(|row| row.len()).sum::<usize>()
            + terminal_plain.len() + terminal_tau.len();
        assert_eq!(entries, 12_899);
        assert_eq!(size_of::<U256Affine>(), 64);
        assert_eq!(size_of::<U256OrbitXAffine>(), 128);
        let retained_bytes = digit_windows.iter().map(|row| row.len()).sum::<usize>()
                * size_of::<U256OrbitXAffine>()
            + (terminal_plain.len() + terminal_tau.len() + terminal_pairs.len())
                * size_of::<U256Affine>()
            + residue_codes.len() * size_of::<u16>()
            + digit_b.len() * size_of::<i16>()
            + digit_quotient.len() * size_of::<i16>()
            + size_of::<[super::U256; 3]>()
            + size_of::<Self>()
            + digit_windows.capacity() * size_of::<Box<[U256OrbitXAffine]>>();
"""


UNIT_ONLINE_RUST = r"""    for row in &tables.digit_windows {
        let (next_a, next_b, index, unit) = split_prime_unit_step(a, b, tables);
        a = next_a;
        b = next_b;
        if index != 0 {
            bucket = bucket.add_mixed(row[index].unit(unit));
            terms += 1;
        }
    }
"""


UNIT_PACKED_STEP_RUST = r"""fn split_prime_unit_step(
    a: Signed192, b: Signed192, tables: &SplitPrimeTables,
) -> (Signed192, Signed192, usize, usize) {
    let residue_word = a.add(b.times_split_prime_small(SPLIT_PRIME_TAU_RESIDUE));
    let (quotient, signed_rem, residue) =
        residue_word.div_rem_small_radix(SPLIT_PRIME_NORM as u64);
    let packed = tables.residue_packed[residue];
    let index = (packed & 1023) as usize;
    let unit = ((packed >> 10) & 7) as usize;
    let correction_a = ((packed >> 13) & 63) as i32 - 20;
    let correction_b = ((packed >> 19) & 63) as i32 - 7;
    let carry = if signed_rem < 0 { 1 } else { 0 };
    let next_a = quotient.times_split_prime_small(23)
        .sub(b.times_split_prime_small(11))
        .add(Signed192::from_i32(correction_a - 23 * carry));
    let next_b = quotient.times_split_prime_small(21)
        .sub(b.times_split_prime_small(10))
        .add(Signed192::from_i32(correction_b - 21 * carry));
    (next_a, next_b, index, unit)
}

"""


UNIT_PACKED_LUT_RUST = r"""        let mut residue_packed = vec![u32::MAX; SPLIT_PRIME_NORM as usize];
        let mut seeds = vec![0i16];
        residue_packed[0] = (20u32 << 13) | (7u32 << 19);
        for seed in 1..=SPLIT_PRIME_DIGIT_LIMIT as i32 {
            if residue_packed[seed as usize] != u32::MAX { continue; }
            let index = seeds.len();
            seeds.push(seed as i16);
            for (unit, (da, db)) in unit_images((seed, 0)).into_iter().enumerate() {
                let digit_word = da + SPLIT_PRIME_TAU_RESIDUE * db;
                let residue = digit_word.rem_euclid(SPLIT_PRIME_NORM) as usize;
                assert_eq!(residue_packed[residue], u32::MAX);
                let digit_q = digit_word.div_euclid(SPLIT_PRIME_NORM);
                let correction_a = -23 * digit_q + 11 * db;
                let correction_b = -21 * digit_q + 10 * db;
                assert!((-20..=43).contains(&correction_a));
                assert!((-7..=28).contains(&correction_b));
                residue_packed[residue] = index as u32
                    | ((unit as u32) << 10)
                    | (((correction_a + 20) as u32) << 13)
                    | (((correction_b + 7) as u32) << 19);
            }
        }
        assert_eq!(seeds.len(), 551);
        assert_eq!(*seeds.last().unwrap(), 1064);
        assert!(residue_packed.iter().all(|&word| word != u32::MAX));
"""


PACKED_LUT_TEST_RUST = r"""    #[test]
    fn split_prime_packed_lookup_exhaustive() {
        fn centered(value: i32) -> i32 {
            let residue = value.rem_euclid(SPLIT_PRIME_NORM);
            residue.min(SPLIT_PRIME_NORM - residue)
        }
        fn canonical_seed(residue: i32) -> i32 {
            [centered(residue), centered(1726 * residue),
             centered(1574 * residue)].into_iter().min().unwrap()
        }
        fn small_value(value: Signed192) -> i32 {
            assert_eq!(value.limbs[1..], [0, 0]);
            let magnitude = i32::try_from(value.limbs[0]).unwrap();
            if value.negative { -magnitude } else { magnitude }
        }
        let tables = &*SPLIT_PRIME_TABLES;
        let mut seeds = vec![0i32];
        seeds.extend((1..=1064).filter(|&seed| canonical_seed(seed) == seed));
        assert_eq!(seeds.len(), 551);
        let mut checked_steps = 0usize;
        for residue in 0..SPLIT_PRIME_NORM {
            let packed = tables.residue_packed[residue as usize];
            let index = (packed & __INDEX_MASK__) as usize;
            let seed = if __SPLIT_TABLE__ { index as i32 } else { seeds[index] };
            let unit = ((packed >> __UNIT_SHIFT__) & 7) as usize;
            let correction_a = ((packed >> __A_SHIFT__) & 63) as i32 - 20;
            let correction_b = ((packed >> __B_SHIFT__) & 63) as i32 - 7;
            assert_eq!(seed, canonical_seed(residue), "seed residue {residue}");
            assert!(unit < 6, "unit residue {residue}");
            let (da, db) = unit_images((seed, 0))[unit];
            let digit_word = da + SPLIT_PRIME_TAU_RESIDUE * db;
            assert_eq!(digit_word.rem_euclid(SPLIT_PRIME_NORM), residue);
            assert!(norm((da, db)) <= i64::from(1064 * 1064));
            let digit_q = digit_word.div_euclid(SPLIT_PRIME_NORM);
            assert_eq!(correction_a, -23 * digit_q + 11 * db);
            assert_eq!(correction_b, -21 * digit_q + 10 * db);
            for b in [-7i32, 0, 7] {
                for shift in [-SPLIT_PRIME_NORM, 0, SPLIT_PRIME_NORM] {
                    let a = residue - SPLIT_PRIME_TAU_RESIDUE * b + shift;
                    let numerator = (a - da) + SPLIT_PRIME_TAU_RESIDUE * (b - db);
                    assert_eq!(numerator.rem_euclid(SPLIT_PRIME_NORM), 0);
                    let k = numerator.div_euclid(SPLIT_PRIME_NORM);
                    let expected_a = 23 * k - 11 * (b - db);
                    let expected_b = 21 * k - 10 * (b - db);
                    let (next_a, next_b, actual_index, actual_unit) =
                        split_prime_unit_step(Signed192::from_i32(a),
                                              Signed192::from_i32(b), tables);
                    assert_eq!(actual_index, index);
                    assert_eq!(actual_unit, unit);
                    assert_eq!(small_value(next_a), expected_a,
                               "next a residue {residue} b {b} shift {shift}");
                    assert_eq!(small_value(next_b), expected_b,
                               "next b residue {residue} b {b} shift {shift}");
                    checked_steps += 1;
                }
            }
        }
        assert_eq!(checked_steps, 3301 * 9);
        println!("packed_lookup_residues=3301 checked_steps={checked_steps}");
    }

"""


def packed_lut_test_source(split_seed_tables: bool) -> str:
    fields = {
        "__INDEX_MASK__": "2047" if split_seed_tables else "1023",
        "__UNIT_SHIFT__": "11" if split_seed_tables else "10",
        "__A_SHIFT__": "14" if split_seed_tables else "13",
        "__B_SHIFT__": "20" if split_seed_tables else "19",
        "__SPLIT_TABLE__": "true" if split_seed_tables else "false",
    }
    source = PACKED_LUT_TEST_RUST
    for old, new in fields.items():
        source = source.replace(old, new)
    assert "__" not in source
    return source


UNIT_PACKED_RETAINED_RUST = r"""        let entries = digit_windows.iter().map(|row| row.len()).sum::<usize>()
            + terminal_plain.len() + terminal_tau.len();
        assert_eq!(entries, 12_899);
        assert_eq!(size_of::<U256Affine>(), 64);
        assert_eq!(size_of::<U256OrbitXAffine>(), 128);
        let retained_bytes = digit_windows.iter().map(|row| row.len()).sum::<usize>()
                * size_of::<U256OrbitXAffine>()
            + (terminal_plain.len() + terminal_tau.len() + terminal_pairs.len())
                * size_of::<U256Affine>()
            + residue_packed.len() * size_of::<u32>()
            + size_of::<[super::U256; 3]>()
            + size_of::<Self>()
            + digit_windows.capacity() * size_of::<Box<[U256OrbitXAffine]>>();
"""


UNIT_SPLIT_ROW_RUST = r"""fn split_prime_orbit_row(base: Jacobian, _seeds: &[i16])
    -> Box<[U256OrbitXAffine]> {
    // m = low + 32*high, 0 <= low < 32 and 0 <= high <= 33.
    let low = affine_multiples(base, 32);
    let high = affine_multiples(low[32], 33);
    low.into_iter().take(32).chain(high).enumerate().map(|(position, point)| {
        let point = if position == 0 || position == 32 {
            U256Affine { x: super::U256::ZERO, y: super::U256::ZERO }
        } else {
            let affine = point.into_affine();
            U256Affine { x: super::hybrid_pair_mont(affine.x),
                         y: super::hybrid_pair_mont(affine.y) }
        };
        U256OrbitXAffine::from_affine(point)
    }).collect::<Vec<_>>().into_boxed_slice()
}

"""


UNIT_SPLIT_ONLINE_RUST = r"""    for row in &tables.digit_windows {
        let (next_a, next_b, seed, unit) = split_prime_unit_step(a, b, tables);
        a = next_a;
        b = next_b;
        let low = seed & 31;
        let high = seed >> 5;
        if low != 0 {
            bucket = bucket.add_mixed(row[low].unit(unit));
            terms += 1;
        }
        if high != 0 {
            bucket = bucket.add_mixed(row[32 + high].unit(unit));
            terms += 1;
        }
    }
"""


TERMINAL_ORBIT_BUILD_RUST = r"""        let mut orbit_digits = Vec::new();
        let mut orbit_indices = std::collections::BTreeMap::new();
        let mut terminal_orbit_codes = Vec::with_capacity(pair_digits.len());
        for &pair in &pair_digits {
            let images = unit_images((i32::from(pair.0), i32::from(pair.1)));
            let representative = *images.iter().min().unwrap();
            let index = *orbit_indices.entry(representative).or_insert_with(|| {
                let index = orbit_digits.len();
                orbit_digits.push((representative.0 as i16, representative.1 as i16));
                index
            });
            let unit = unit_images(representative).iter().position(|&image| {
                image == (i32::from(pair.0), i32::from(pair.1))
            }).unwrap();
            terminal_orbit_codes.push((index * 6 + unit) as u16);
        }
        assert_eq!(orbit_digits.len(), 1280);
        assert_eq!(orbit_digits[0], (0, 0));
        let terminal_orbits = build_u256_window(&orbit_digits, base).iter()
            .copied().map(U256TwoXAffine::from_affine)
            .collect::<Vec<_>>().into_boxed_slice();
        let terminal_orbit_codes = terminal_orbit_codes.into_boxed_slice();
"""


TERMINAL_ORBIT_TEST_RUST = r"""    #[test]
    fn split_prime_terminal_orbit_exhaustive() {
        let tables = &SPLIT_PRIME_TABLES;
        let mut pairs = Vec::new();
        for a in 0..92i32 {
            for b in -54..=54i32 {
                let norm = a*a + 3*a*b + 3*b*b;
                if norm < 2116 && (a > 0 || b >= 0) {
                    pairs.push((a as i16, b as i16));
                }
            }
        }
        assert_eq!(pairs.len(), 3838);
        assert_eq!(tables.terminal_orbits.len(), 1280);
        // Table construction advances the base by pi^21.
        let mut base = Jacobian::generator();
        for _ in 0..SPLIT_PRIME_STEPS {
            let ordinary = affine_multiples(base, 86).pop().unwrap();
            let tau = affine_multiples(base.tau(), 21).pop().unwrap().neg().into_affine();
            base = ordinary.add_mixed(tau).into_affine();
        }
        let direct = build_u256_window(&pairs, base);
        for (index, &pair) in pairs.iter().enumerate() {
            let word = tables.terminal_orbit_codes[index] as usize;
            let point = tables.terminal_orbits[word / 6].unit(word % 6);
            assert_eq!(point.x.0, direct[index].x.0, "terminal x {pair:?}");
            assert_eq!(point.y.0, direct[index].y.0, "terminal y {pair:?}");
        }
        println!("terminal_orbit_pairs=3838 terminal_orbits=1280");
    }

"""


def fold_terminal_orbits(source: str) -> str:
    source = replace_once(source,
        "    terminal_pairs: Box<[U256Affine]>,\n",
        "    terminal_orbits: Box<[U256TwoXAffine]>,\n"
        "    terminal_orbit_codes: Box<[u16]>,\n")
    source = replace_once(source,
        "        let terminal_pairs = build_u256_window(&pair_digits, base);\n",
        TERMINAL_ORBIT_BUILD_RUST)
    source = replace_once(source,
        "(terminal_plain.len() + terminal_tau.len() + terminal_pairs.len())\n"
        "                * size_of::<U256Affine>()",
        "(terminal_plain.len() + terminal_tau.len())\n"
        "                * size_of::<U256Affine>()\n"
        "            + terminal_orbits.len() * size_of::<U256TwoXAffine>()\n"
        "            + terminal_orbit_codes.len() * size_of::<u16>()")
    source = replace_once(source,
        "               terminal_plain, terminal_tau, terminal_pairs,\n"
        "               terminal_row_start, terminal_row_min, retained_bytes }",
        "               terminal_plain, terminal_tau,\n"
        "               terminal_orbits, terminal_orbit_codes,\n"
        "               terminal_row_start, terminal_row_min, retained_bytes }")
    source = replace_once(source,
        "            let mut point = tables.terminal_pairs[index];\n",
        "            let word = tables.terminal_orbit_codes[index] as usize;\n"
        "            let mut point = tables.terminal_orbits[word / 6].unit(word % 6);\n")
    anchor = "    #[test]\n    fn split_prime_holdout_matches_independent_binary() {"
    return replace_once(source, anchor, TERMINAL_ORBIT_TEST_RUST + anchor)


TERMINAL_NO_FALLBACK_TEST_RUST = r"""    #[test]
    fn split_prime_no_fallback_random_replay() {
        let mut scalars = vec![BigInt::from(0), BigInt::from(1),
                               &SCALAR_LATTICE.n - 1, SCALAR_LATTICE.n.clone(),
                               &SCALAR_LATTICE.n + 1,
                               (BigInt::from(1) << 256) - 1];
        let mut state = 0x6a09e667f3bcc909u64;
        for _ in 0..512 {
            let mut bytes = [0u8; 32];
            for chunk in bytes.chunks_exact_mut(8) {
                state ^= state << 13;
                state ^= state >> 7;
                state ^= state << 17;
                chunk.copy_from_slice(&state.to_be_bytes());
            }
            scalars.push(BigInt::from_bytes_be(num_bigint::Sign::Plus, &bytes));
        }
        for (index, scalar) in scalars.iter().enumerate() {
            let words = super::super::scalar_words_256(scalar).unwrap();
            let actual = multiply_u256_tau_split_prime_radix(words).0;
            let expected = independent_binary_point(&(scalar % &SCALAR_LATTICE.n))
                .affine_hex();
            assert_eq!(actual, expected, "scalar case {index}");
        }
        println!("split_prime_no_fallback_replays={}", scalars.len());
    }

"""


def drop_terminal_axis_fallback(source: str) -> str:
    source = replace_once(source,
        "const SPLIT_PRIME_TERMINAL_LIMIT: usize = 642;",
        "const SPLIT_PRIME_TERMINAL_LIMIT: usize = 91;")
    source = replace_once(source,
        "    terminal_plain: Box<[U256Affine]>,\n"
        "    terminal_tau: Box<[U256Affine]>,\n", "")
    source = replace_once(source,
        "        let terminal_plain = split_prime_affine_row(base, SPLIT_PRIME_TERMINAL_LIMIT);\n"
        "        let terminal_tau = split_prime_affine_row(base.tau(), SPLIT_PRIME_TERMINAL_LIMIT);\n", "")
    source = replace_region(source,
        "fn split_prime_affine_row(", "fn split_prime_orbit_row(", "")
    source = replace_once(source,
        "        let entries = digit_windows.iter().map(|row| row.len()).sum::<usize>()\n"
        "            + terminal_plain.len() + terminal_tau.len();\n"
        "        assert_eq!(entries, 2_672);\n",
        "        let entries = digit_windows.iter().map(|row| row.len()).sum::<usize>();\n"
        "        assert_eq!(entries, 1_386);\n")
    source = replace_once(source,
        "            + (terminal_plain.len() + terminal_tau.len())\n"
        "                * size_of::<U256Affine>()\n", "")
    source = replace_once(source,
        "               terminal_plain, terminal_tau,\n", "")
    source = replace_once(source,
        "    // The fused table covers the small terminal norm. Axis rows are\n"
        "    // retained for exact fallback under the original coordinate bound.\n",
        "    // Every exact 21-step trajectory has terminal norm below 46².\n"
        "    // Reject an implementation mismatch before indexing the compact ball.\n")
    source = replace_once(source,
        "    if terminal_norm < 2116 {\n",
        "    assert!(terminal_norm < 2116, \"split-prime terminal norm bound\");\n")
    source = replace_region(source,
        "    } else {\n    for (coordinate, row) in [(a, &tables.terminal_plain),",
        "    let point = bucket.affine_hex_binary_inverse();", "")
    anchor = "    #[test]\n    fn split_prime_holdout_matches_independent_binary() {"
    return replace_once(source, anchor, TERMINAL_NO_FALLBACK_TEST_RUST + anchor)


DIGIT_TWO_X_TEST_RUST = r"""    #[test]
    fn split_prime_digit_two_x_orbits_exhaustive() {
        let tables = &SPLIT_PRIME_TABLES;
        let mut checked = 0usize;
        for row in &tables.digit_windows {
            assert_eq!(row.len(), 66);
            for &entry in row.iter() {
                let reference = U256OrbitXAffine::from_affine(entry.unit(0));
                for unit in 0..6 {
                    let actual = entry.unit(unit);
                    let expected = reference.unit(unit);
                    assert_eq!(actual.x.0, expected.x.0);
                    assert_eq!(actual.y.0, expected.y.0);
                    checked += 1;
                }
            }
        }
        assert_eq!(checked, 21 * 66 * 6);
        println!("digit_two_x_unit_images={checked}");
    }

"""


def use_two_x_digit_rows(source: str) -> str:
    source = replace_once(source,
        "    digit_windows: Vec<Box<[U256OrbitXAffine]>>,\n",
        "    digit_windows: Vec<Box<[U256TwoXAffine]>>,\n")
    source = replace_once(source,
        "fn split_prime_orbit_row(base: Jacobian, _seeds: &[i16])\n"
        "    -> Box<[U256OrbitXAffine]> {",
        "fn split_prime_orbit_row(base: Jacobian, _seeds: &[i16])\n"
        "    -> Box<[U256TwoXAffine]> {")
    source = replace_once(source,
        "        U256OrbitXAffine::from_affine(point)\n"
        "    }).collect::<Vec<_>>().into_boxed_slice()\n}",
        "        U256TwoXAffine::from_affine(point)\n"
        "    }).collect::<Vec<_>>().into_boxed_slice()\n}")
    source = replace_once(source,
        "        assert_eq!(size_of::<U256OrbitXAffine>(), 128);\n",
        "        assert_eq!(size_of::<U256TwoXAffine>(), 96);\n")
    source = replace_once(source,
        "digit_windows.iter().map(|row| row.len()).sum::<usize>()\n"
        "                * size_of::<U256OrbitXAffine>()",
        "digit_windows.iter().map(|row| row.len()).sum::<usize>()\n"
        "                * size_of::<U256TwoXAffine>()")
    source = replace_once(source,
        "digit_windows.capacity() * size_of::<Box<[U256OrbitXAffine]>>()",
        "digit_windows.capacity() * size_of::<Box<[U256TwoXAffine]>>()")
    anchor = "    #[test]\n    fn split_prime_holdout_matches_independent_binary() {"
    return replace_once(source, anchor, DIGIT_TWO_X_TEST_RUST + anchor)


def use_direct_two_x_seed_rows(source: str) -> str:
    """Materialize canonical seeds directly, with six units from each two-x entry."""
    old_row = UNIT_SPLIT_ROW_RUST.replace("U256OrbitXAffine", "U256TwoXAffine")
    new_row = UNIT_ROW_RUST.replace("U256OrbitXAffine", "U256TwoXAffine")
    source = replace_once(source, old_row, new_row)
    direct_online = UNIT_ONLINE_RUST.replace(
        "row[index].unit(unit)", "row[tables.seed_index[index] as usize].unit(unit)")
    source = replace_once(source, UNIT_SPLIT_ONLINE_RUST, direct_online)
    source = replace_once(source,
        "    residue_packed: Box<[u32]>,\n",
        "    residue_packed: Box<[u32]>,\n"
        "    seed_index: [u16; SPLIT_PRIME_DIGIT_LIMIT + 1],\n")
    source = replace_once(source,
        "        assert_eq!(*seeds.last().unwrap(), 1064);\n",
        "        assert_eq!(*seeds.last().unwrap(), 1064);\n"
        "        let mut seed_index = [u16::MAX; SPLIT_PRIME_DIGIT_LIMIT + 1];\n"
        "        for (index, &seed) in seeds.iter().enumerate() {\n"
        "            seed_index[seed as usize] = index as u16;\n"
        "        }\n")
    source = replace_once(source,
        "        Self { digit_windows, residue_packed: residue_packed.into_boxed_slice(),\n",
        "        Self { digit_windows, residue_packed: residue_packed.into_boxed_slice(),\n"
        "               seed_index,\n")
    source = replace_once(source, "        assert_eq!(entries, 1_386);\n",
                          "        assert_eq!(entries, 11_571);\n")
    source = replace_once(source, "            assert_eq!(row.len(), 66);\n",
                          "            assert_eq!(row.len(), 551);\n")
    source = replace_once(source, "        assert_eq!(checked, 21 * 66 * 6);\n",
                          "        assert_eq!(checked, 21 * 551 * 6);\n")
    return source


BATCH_AFFINE_ADD_RUST = r"""fn split_prime_batch_affine_add(
    pairs: &[(U256Affine, U256Affine)], output: &mut [U256Affine],
) {
    assert_eq!(pairs.len(), output.len());
    assert!(pairs.len() <= SPLIT_PRIME_STEPS);
    if pairs.is_empty() { return; }
    let ctx = &super::HYBRID_FIELD.0;
    let one = ctx.r_mod_n;
    let mut prefixes = [one; SPLIT_PRIME_STEPS];
    let mut product = one;
    for (index, &(left, right)) in pairs.iter().enumerate() {
        let denominator = u256_sub(right.x, left.x);
        assert!(!bool::from(denominator.ct_is_zero()),
                "split-prime affine pair denominator");
        prefixes[index] = product;
        product = u256_mul(product, denominator);
    }
    let mut suffix_inverse = super::hybrid_binary_invert(product, ctx);
    for index in (0..pairs.len()).rev() {
        let (left, right) = pairs[index];
        let denominator = u256_sub(right.x, left.x);
        let inverse = u256_mul(suffix_inverse, prefixes[index]);
        suffix_inverse = u256_mul(suffix_inverse, denominator);
        let slope = u256_mul(u256_sub(right.y, left.y), inverse);
        let x = u256_sub(u256_sub(u256_square(slope), left.x), right.x);
        let y = u256_sub(u256_mul(slope, u256_sub(left.x, x)), left.y);
        output[index] = U256Affine { x, y };
    }
}

"""


BATCH_AFFINE_ONLINE_RUST = r"""    let zero = U256Affine { x: super::U256::ZERO, y: super::U256::ZERO };
    let mut selected: [Option<U256Affine>; SPLIT_PRIME_STEPS] = [None; SPLIT_PRIME_STEPS];
    let mut pairs = [(zero, zero); SPLIT_PRIME_STEPS];
    let mut pair_slots = [0usize; SPLIT_PRIME_STEPS];
    let mut pair_count = 0usize;
    for (slot, row) in tables.digit_windows.iter().enumerate() {
        let (next_a, next_b, seed, unit) = split_prime_unit_step(a, b, tables);
        a = next_a;
        b = next_b;
        let low = seed & 31;
        let high = seed >> 5;
        match (low != 0, high != 0) {
            (true, true) => {
                pairs[pair_count] = (row[low].unit(unit), row[32 + high].unit(unit));
                pair_slots[pair_count] = slot;
                pair_count += 1;
            }
            (true, false) => selected[slot] = Some(row[low].unit(unit)),
            (false, true) => selected[slot] = Some(row[32 + high].unit(unit)),
            (false, false) => {},
        }
    }
    let mut fused = [zero; SPLIT_PRIME_STEPS];
    split_prime_batch_affine_add(&pairs[..pair_count], &mut fused[..pair_count]);
    for index in 0..pair_count {
        selected[pair_slots[index]] = Some(fused[index]);
    }
    for point in selected.into_iter().flatten() {
        bucket = bucket.add_mixed(point);
        terms += 1;
    }
"""


BATCH_AFFINE_TEST_RUST = r"""    #[test]
    fn split_prime_batch_affine_pairs_match_group_law() {
        let row = &SPLIT_PRIME_TABLES.digit_windows[0];
        let zero = U256Affine { x: super::super::U256::ZERO,
                                y: super::super::U256::ZERO };
        let mut pairs = [(zero, zero); SPLIT_PRIME_STEPS];
        let mut output = [zero; SPLIT_PRIME_STEPS];
        for index in 0..SPLIT_PRIME_STEPS {
            let low = 1 + index % 31;
            let high = 1 + index % 33;
            let unit = index % 6;
            pairs[index] = (row[low].unit(unit), row[32 + high].unit(unit));
        }
        split_prime_batch_affine_add(&pairs, &mut output);
        for index in 0..SPLIT_PRIME_STEPS {
            let expected = U256Jacobian::from_affine(pairs[index].0)
                .add_mixed(pairs[index].1).affine_hex_binary_inverse();
            let actual = U256XYZZ::from_affine(output[index])
                .affine_hex_binary_inverse();
            assert_eq!(actual, expected, "batch pair {index}");
        }
        println!("batch_affine_pairs={SPLIT_PRIME_STEPS}");
    }

"""


def batch_fuse_digit_rows(source: str) -> str:
    source = replace_once(source, "impl SplitPrimeTables {\n",
                          BATCH_AFFINE_ADD_RUST + "impl SplitPrimeTables {\n")
    source = replace_once(source, UNIT_SPLIT_ONLINE_RUST, BATCH_AFFINE_ONLINE_RUST)
    anchor = "    #[test]\n    fn split_prime_holdout_matches_independent_binary() {"
    return replace_once(source, anchor, BATCH_AFFINE_TEST_RUST + anchor)


def split_unit_seed_tables(source: str) -> str:
    source = replace_once(source, UNIT_ROW_RUST, UNIT_SPLIT_ROW_RUST)
    source = replace_once(source, UNIT_ONLINE_RUST, UNIT_SPLIT_ONLINE_RUST)
    source = replace_once(source,
        "    let index = (packed & 1023) as usize;\n"
        "    let unit = ((packed >> 10) & 7) as usize;\n"
        "    let correction_a = ((packed >> 13) & 63) as i32 - 20;\n"
        "    let correction_b = ((packed >> 19) & 63) as i32 - 7;",
        "    let index = (packed & 2047) as usize;\n"
        "    let unit = ((packed >> 11) & 7) as usize;\n"
        "    let correction_a = ((packed >> 14) & 63) as i32 - 20;\n"
        "    let correction_b = ((packed >> 20) & 63) as i32 - 7;")
    source = replace_once(source,
        "        residue_packed[0] = (20u32 << 13) | (7u32 << 19);",
        "        residue_packed[0] = (20u32 << 14) | (7u32 << 20);")
    source = replace_once(source,
        "                residue_packed[residue] = index as u32\n"
        "                    | ((unit as u32) << 10)\n"
        "                    | (((correction_a + 20) as u32) << 13)\n"
        "                    | (((correction_b + 7) as u32) << 19);",
        "                residue_packed[residue] = seed as u32\n"
        "                    | ((unit as u32) << 11)\n"
        "                    | (((correction_a + 20) as u32) << 14)\n"
        "                    | (((correction_b + 7) as u32) << 20);")
    source = replace_once(source,
        "            let index = seeds.len();\n            seeds.push(seed as i16);",
        "            seeds.push(seed as i16);")
    source = replace_once(source, "        assert_eq!(entries, 12_857);",
                          "        assert_eq!(entries, 2_672);")
    return source


def unitize_split_source(source: str) -> str:
    source = replace_region(source, "fn split_prime_step(",
                            "struct SplitPrimeTables {", UNIT_STEP_RUST)
    source = replace_once(source,
        "    digit_windows: Vec<Box<[U256Affine]>>,\n",
        "    digit_windows: Vec<Box<[U256OrbitXAffine]>>,\n"
        "    residue_codes: Box<[u16]>,\n"
        "    digit_b: Box<[i16]>,\n"
        "    digit_quotient: Box<[i16]>,\n")
    source = replace_once(source, "impl SplitPrimeTables {\n",
                          UNIT_ROW_RUST + "impl SplitPrimeTables {\n")
    source = replace_once(source, "        let mut base = Jacobian::generator();\n",
                          UNIT_LUT_RUST + "        let mut base = Jacobian::generator();\n")
    source = replace_once(source,
        "digit_windows.push(split_prime_affine_row(base, SPLIT_PRIME_DIGIT_LIMIT));",
        "digit_windows.push(split_prime_orbit_row(base, &seeds));")
    source = replace_region(source,
        "        let entries = digit_windows.iter().map(|row| row.len()).sum::<usize>()\n",
        "        Self { digit_windows", UNIT_RETAINED_RUST)
    source = replace_once(source,
        "        Self { digit_windows, terminal_plain, terminal_tau,\n"
        "               terminal_pairs, terminal_row_start, terminal_row_min, retained_bytes }",
        "        Self { digit_windows, residue_codes: residue_codes.into_boxed_slice(),\n"
        "               digit_b: digit_b.into_boxed_slice(),\n"
        "               digit_quotient: digit_quotient.into_boxed_slice(),\n"
        "               terminal_plain, terminal_tau, terminal_pairs,\n"
        "               terminal_row_start, terminal_row_min, retained_bytes }")
    source = replace_region(source,
        "    for row in &tables.digit_windows {\n",
        "    // The fused table covers", UNIT_ONLINE_RUST)
    return source


def pack_unit_corrections(source: str) -> str:
    source = replace_once(source, UNIT_STEP_RUST, UNIT_PACKED_STEP_RUST)
    source = replace_once(source, UNIT_LUT_RUST, UNIT_PACKED_LUT_RUST)
    source = replace_once(source, UNIT_RETAINED_RUST, UNIT_PACKED_RETAINED_RUST)
    source = replace_once(source,
        "    residue_codes: Box<[u16]>,\n"
        "    digit_b: Box<[i16]>,\n"
        "    digit_quotient: Box<[i16]>,\n",
        "    residue_packed: Box<[u32]>,\n")
    source = replace_once(source,
        "        Self { digit_windows, residue_codes: residue_codes.into_boxed_slice(),\n"
        "               digit_b: digit_b.into_boxed_slice(),\n"
        "               digit_quotient: digit_quotient.into_boxed_slice(),\n",
        "        Self { digit_windows, residue_packed: residue_packed.into_boxed_slice(),\n")
    return source


UNIT_TIGHT_TERMINAL_REPLACEMENTS = {
    "const SPLIT_PRIME_TERMINAL_LIMIT: usize = 663;":
        "const SPLIT_PRIME_TERMINAL_LIMIT: usize = 642;",
    "    terminal_row_start: [u16; 113],":
        "    terminal_row_start: [u16; 93],",
    "    terminal_row_min: [i16; 112],":
        "    terminal_row_min: [i16; 92],",
    "        let mut terminal_row_start = [0u16; 113];":
        "        let mut terminal_row_start = [0u16; 93];",
    "        let mut terminal_row_min = [0i16; 112];":
        "        let mut terminal_row_min = [0i16; 92];",
    "        for a in 0..112i32 {":
        "        for a in 0..92i32 {",
    "            for b in -65..=65i32 {":
        "            for b in -54..=54i32 {",
    "                if norm >= 3136 || (a == 0 && b < 0) { continue; }":
        "                if norm >= 2116 || (a == 0 && b < 0) { continue; }",
    "        terminal_row_start[112] = pair_digits.len() as u16;":
        "        terminal_row_start[92] = pair_digits.len() as u16;",
    "        assert_eq!(pair_digits.len(), 5680);":
        "        assert_eq!(pair_digits.len(), 3838);",
    "        assert_eq!(entries, 12_899);":
        "        assert_eq!(entries, 12_857);",
    "    if terminal_norm < 3136 {":
        "    if terminal_norm < 2116 {",
}


LINEAR_REPLACEMENTS = {
    "const SPLIT_PRIME_NORM: i32 = 3301;":
        "const SPLIT_PRIME_NORM: i32 = 3307;",
    "const SPLIT_PRIME_TAU_RESIDUE: i32 = 1576;":
        "const SPLIT_PRIME_TAU_RESIDUE: i32 = 56;",
    "const SPLIT_PRIME_DIGIT_LIMIT: usize = 1650;":
        "const SPLIT_PRIME_DIGIT_LIMIT: usize = 1653;",
    "// In Z[tau]/(86-21*tau), tau = 1576 mod 3301.":
        "// In Z[tau]/(56+tau), tau = -56 mod 3307.",
    "let residue_word = a.add(b.times_split_prime_small(SPLIT_PRIME_TAU_RESIDUE));":
        "let residue_word = a.sub(b.times_split_prime_small(SPLIT_PRIME_TAU_RESIDUE));",
    "let next_a = k.times_split_prime_small(23).sub(b.times_split_prime_small(11));":
        "let next_a = k.times_split_prime_small(59).add(b);",
    "let next_b = k.times_split_prime_small(21).sub(b.times_split_prime_small(10));":
        "let next_b = k.neg();",
    "// pi = 86 - 21*tau. All of this is reusable table preparation.":
        "// pi = 56 + tau. All of this is reusable table preparation.",
    "let ordinary = affine_multiples(base, 86).pop().unwrap();":
        "let ordinary = affine_multiples(base, 56).pop().unwrap();",
    "let tau = affine_multiples(base.tau(), 21).pop().unwrap().neg().into_affine();":
        "let tau = base.tau().into_affine();",
    "assert_eq!(entries, 35_999);":
        "assert_eq!(entries, 36_062);",
}


SHORT_REPLACEMENTS = {
    "const SPLIT_PRIME_NORM: i32 = 3301;":
        "const SPLIT_PRIME_NORM: i32 = 5113;",
    "const SPLIT_PRIME_TAU_RESIDUE: i32 = 1576;":
        "const SPLIT_PRIME_TAU_RESIDUE: i32 = 70;",
    "const SPLIT_PRIME_STEPS: usize = 21;":
        "const SPLIT_PRIME_STEPS: usize = 20;",
    "const SPLIT_PRIME_DIGIT_LIMIT: usize = 1650;":
        "const SPLIT_PRIME_DIGIT_LIMIT: usize = 2556;",
    "const SPLIT_PRIME_TERMINAL_LIMIT: usize = 663;":
        "const SPLIT_PRIME_TERMINAL_LIMIT: usize = 499;",
    "// In Z[tau]/(86-21*tau), tau = 1576 mod 3301.":
        "// In Z[tau]/(70+tau), tau = -70 mod 5113.",
    "let residue_word = a.add(b.times_split_prime_small(SPLIT_PRIME_TAU_RESIDUE));":
        "let residue_word = a.sub(b.times_split_prime_small(SPLIT_PRIME_TAU_RESIDUE));",
    "let next_a = k.times_split_prime_small(23).sub(b.times_split_prime_small(11));":
        "let next_a = k.times_split_prime_small(73).add(b);",
    "let next_b = k.times_split_prime_small(21).sub(b.times_split_prime_small(10));":
        "let next_b = k.neg();",
    "// pi = 86 - 21*tau. All of this is reusable table preparation.":
        "// pi = 70 + tau. All of this is reusable table preparation.",
    "let ordinary = affine_multiples(base, 86).pop().unwrap();":
        "let ordinary = affine_multiples(base, 70).pop().unwrap();",
    "let tau = affine_multiples(base.tau(), 21).pop().unwrap().neg().into_affine();":
        "let tau = base.tau().into_affine();",
    "assert_eq!(entries, 35_999);":
        "assert_eq!(entries, 52_140);",
}


def main(target: Path, variant: str = "3301", fused_terminal: bool = False,
         unit_compressed: bool = False, packed_correction: bool = False,
         tight_terminal: bool = False, split_seed_tables: bool = False,
         terminal_orbits: bool = False, no_terminal_fallback: bool = False,
         digit_two_x: bool = False, batch_affine_digits: bool = False,
         direct_two_x_seeds: bool = False) -> None:
    if variant not in ("3301", "3307", "5113"):
        raise ValueError("variant must be 3301, 3307, or 5113")
    spec = importlib.util.spec_from_file_location("mixed640_bench_cli", BASE)
    bench = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(bench)
    bench.main("selective", target)
    target = target.resolve()
    module_path = target / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    split_source = SPLIT_PRIME_RUST
    if fused_terminal:
        if variant not in ("3301", "5113"):
            raise ValueError("fused terminal is defined for norm 3301 or 5113")
        for old, new in FUSED_TERMINAL_REPLACEMENTS.items():
            split_source = replace_once(split_source, old, new)
    if unit_compressed:
        if variant != "3301" or not fused_terminal:
            raise ValueError("unit compression requires norm 3301 and fused terminal")
        split_source = unitize_split_source(split_source)
    if packed_correction:
        if not unit_compressed:
            raise ValueError("packed correction requires unit compression")
        split_source = pack_unit_corrections(split_source)
    if tight_terminal:
        if not packed_correction:
            raise ValueError("tight terminal requires packed unit compression")
        for old, new in UNIT_TIGHT_TERMINAL_REPLACEMENTS.items():
            split_source = replace_once(split_source, old, new)
    if split_seed_tables:
        if not tight_terminal:
            raise ValueError("split seed tables require tight packed unit compression")
        split_source = split_unit_seed_tables(split_source)
    if terminal_orbits:
        if not split_seed_tables:
            raise ValueError("terminal orbits require split seed tables")
        split_source = fold_terminal_orbits(split_source)
    if no_terminal_fallback:
        if not terminal_orbits:
            raise ValueError("removing terminal fallback requires terminal orbits")
        split_source = drop_terminal_axis_fallback(split_source)
    if digit_two_x:
        if not no_terminal_fallback:
            raise ValueError("two-x digit rows require axis-free terminal table")
        split_source = use_two_x_digit_rows(split_source)
    if direct_two_x_seeds:
        if not digit_two_x or batch_affine_digits:
            raise ValueError("direct two-x seeds require two-x rows without batch fusion")
        split_source = use_direct_two_x_seed_rows(split_source)
    if batch_affine_digits:
        if not digit_two_x:
            raise ValueError("batch affine digits require two-x digit rows")
        split_source = batch_fuse_digit_rows(split_source)
    if packed_correction:
        anchor = "    #[test]\n    fn split_prime_holdout_matches_independent_binary() {"
        split_source = replace_once(split_source, anchor,
                                    packed_lut_test_source(split_seed_tables) + anchor)
    module = replace_once(module_path.read_text(),
        "pub(super) fn warm_mixed640_pretau_table() -> usize {\n",
        split_source + "pub(super) fn warm_mixed640_pretau_table() -> usize {\n")
    if variant == "3307":
        for old, new in LINEAR_REPLACEMENTS.items():
            module = replace_once(module, old, new)
    if variant == "5113":
        for old, new in SHORT_REPLACEMENTS.items():
            module = replace_once(module, old, new)
    module_path.write_text(module)
    front_path = target / "src/bin/eisenstein_fixed.rs"
    front = replace_once(front_path.read_text(),
        "    let retained_bytes = unit_orbit_windows::warm_mixed640_pretau_table();\n",
        "    let retained_bytes = unit_orbit_windows::warm_split_prime_table();\n")
    front = replace_once(front,
        "        unit_orbit_windows::multiply_u256_tau_mixed640_pretau_tree(\n",
        "        unit_orbit_windows::multiply_u256_tau_split_prime_radix(\n")
    front_path.write_text(front)
    receipt_path = target / "native-bench-overlay.json"
    receipt = json.loads(receipt_path.read_text())
    receipt.update({
        "variant": (f"split_prime_radix_{variant}"
                    + ("_fused_terminal" if fused_terminal else "")
                    + ("_unit_compressed" if unit_compressed else "")
                    + ("_packed_correction" if packed_correction else "")
                    + ("_tight_terminal" if tight_terminal else "")
                    + ("_split_seed_tables" if split_seed_tables else "")
                    + ("_terminal_orbits" if terminal_orbits else "")
                    + ("_no_terminal_fallback" if no_terminal_fallback else "")
                    + ("_digit_two_x" if digit_two_x else "")
                    + ("_direct_two_x_seeds" if direct_two_x_seeds else "")
                    + ("_batch_affine_digits" if batch_affine_digits else "")),
        "split_prime_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "generated_module_sha256": sha256(module_path.read_bytes()).hexdigest(),
        "generated_front_sha256": sha256(front_path.read_bytes()).hexdigest(),
    })
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) == 2:
        main(Path(sys.argv[1]))
    elif len(sys.argv) == 3 and sys.argv[1] == "--linear":
        main(Path(sys.argv[2]), "3307")
    elif len(sys.argv) == 3 and sys.argv[1] == "--fused-terminal":
        main(Path(sys.argv[2]), fused_terminal=True)
    elif len(sys.argv) == 3 and sys.argv[1] == "--short-fused":
        main(Path(sys.argv[2]), "5113", fused_terminal=True)
    elif len(sys.argv) == 3 and sys.argv[1] == "--unit-fused":
        main(Path(sys.argv[2]), fused_terminal=True, unit_compressed=True)
    elif len(sys.argv) == 3 and sys.argv[1] == "--unit-packed":
        main(Path(sys.argv[2]), fused_terminal=True, unit_compressed=True,
             packed_correction=True)
    elif len(sys.argv) == 3 and sys.argv[1] == "--unit-packed-tight":
        main(Path(sys.argv[2]), fused_terminal=True, unit_compressed=True,
             packed_correction=True, tight_terminal=True)
    elif len(sys.argv) == 3 and sys.argv[1] == "--unit-split-table":
        main(Path(sys.argv[2]), fused_terminal=True, unit_compressed=True,
             packed_correction=True, tight_terminal=True, split_seed_tables=True)
    elif len(sys.argv) == 3 and sys.argv[1] == "--unit-split-terminal-orbit":
        main(Path(sys.argv[2]), fused_terminal=True, unit_compressed=True,
             packed_correction=True, tight_terminal=True, split_seed_tables=True,
             terminal_orbits=True)
    elif len(sys.argv) == 3 and sys.argv[1] == "--unit-split-terminal-orbit-no-fallback":
        main(Path(sys.argv[2]), fused_terminal=True, unit_compressed=True,
             packed_correction=True, tight_terminal=True, split_seed_tables=True,
             terminal_orbits=True, no_terminal_fallback=True)
    elif len(sys.argv) == 3 and sys.argv[1] == "--unit-split-terminal-orbit-no-fallback-two-x":
        main(Path(sys.argv[2]), fused_terminal=True, unit_compressed=True,
             packed_correction=True, tight_terminal=True, split_seed_tables=True,
             terminal_orbits=True, no_terminal_fallback=True, digit_two_x=True)
    elif len(sys.argv) == 3 and sys.argv[1] == "--unit-split-batch-affine":
        main(Path(sys.argv[2]), fused_terminal=True, unit_compressed=True,
             packed_correction=True, tight_terminal=True, split_seed_tables=True,
             terminal_orbits=True, no_terminal_fallback=True, digit_two_x=True,
             batch_affine_digits=True)
    elif len(sys.argv) == 3 and sys.argv[1] == "--unit-direct-two-x":
        main(Path(sys.argv[2]), fused_terminal=True, unit_compressed=True,
             packed_correction=True, tight_terminal=True, split_seed_tables=True,
             terminal_orbits=True, no_terminal_fallback=True, digit_two_x=True,
             direct_two_x_seeds=True)
    else:
        raise SystemExit("usage: native_split_prime_bench.py [--linear|--fused-terminal|--short-fused|--unit-fused|--unit-packed|--unit-packed-tight|--unit-split-table] TARGET_DIR")
