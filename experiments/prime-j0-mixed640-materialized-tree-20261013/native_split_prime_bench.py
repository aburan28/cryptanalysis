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
         unit_compressed: bool = False, packed_correction: bool = False) -> None:
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
                    + ("_packed_correction" if packed_correction else "")),
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
    else:
        raise SystemExit("usage: native_split_prime_bench.py [--linear|--fused-terminal|--short-fused|--unit-fused|--unit-packed] TARGET_DIR")
