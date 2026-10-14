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


def main(target: Path, variant: str = "3301", fused_terminal: bool = False) -> None:
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
        "variant": f"split_prime_radix_{variant}" + ("_fused_terminal" if fused_terminal else ""),
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
    else:
        raise SystemExit("usage: native_split_prime_bench.py [--linear|--fused-terminal|--short-fused] TARGET_DIR")
