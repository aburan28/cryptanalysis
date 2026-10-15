#!/usr/bin/env python3
"""Use direct centered radix digits and one affine accumulation bucket."""

from hashlib import sha256
import json
from pathlib import Path
import sys

SOURCE_SHA256 = "c0ab21bcc6975c2d1b823cc8f800ca78e8d2a84757db1846729f0b4f3889b512"


def splice(source: str, first: str, last: str, replacement: str) -> str:
    start = source.index(first)
    end = source.index(last, start)
    return source[:start] + replacement + source[end:]


def main(root: Path) -> None:
    path = root / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    source = path.read_text()
    assert sha256(source.encode()).hexdigest() == SOURCE_SHA256
    source = source.replace("const SPLIT_PRIME_DIGIT_LIMIT: usize = 4033;",
                            "const SPLIT_PRIME_DIGIT_LIMIT: usize = 6105;")
    source = source.replace("const SPLIT_PRIME_TERMINAL_LIMIT: usize = 140;",
                            "const SPLIT_PRIME_TERMINAL_LIMIT: usize = 178;")

    source = splice(source, "fn split_prime_unit_step(\n", "\nstruct SplitPrimeTables {", """fn split_prime_unit_step(
    a: Signed192, b: Signed192, _tables: &SplitPrimeTables,
) -> (Signed192, Signed192, usize, usize) {
    let residue_word = a.add(b.times_split_prime_small(SPLIT_PRIME_TAU_RESIDUE));
    let (quotient, signed_rem, residue) =
        residue_word.div_rem_small_radix(SPLIT_PRIME_NORM as u64);
    let digit = if residue <= SPLIT_PRIME_DIGIT_LIMIT {
        residue as i32
    } else {
        residue as i32 - SPLIT_PRIME_NORM
    };
    // div_rem_small_radix truncates toward zero. Convert to the quotient
    // for the nonnegative residue, then account for a negative digit.
    let adjustment = if signed_rem < 0 { -1 } else { 0 }
        + if digit < 0 { 1 } else { 0 };
    let k = quotient.add(Signed192::from_i32(adjustment));
    let next_a = k.times_split_prime_small(109).sub(b);
    let next_b = k;
    (next_a, next_b, digit.unsigned_abs() as usize, usize::from(digit < 0))
}
""")

    source = splice(source, "struct SplitPrimeTables {", "\nstatic SPLIT_PRIME_TABLES: LazyLock<SplitPrimeTables> =", """struct SplitPrimeTables {
    digit_windows: Vec<Box<[U256Affine]>>,
    terminal_pairs: Box<[U256Affine]>,
    terminal_row_start: [u16; 179],
    terminal_row_min: [i16; 178],
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
            let ordinary = affine_multiples(base, 112).pop().unwrap();
            let tau = base.tau().neg().into_affine();
            base = ordinary.add_mixed(tau).into_affine();
        }
        let mut pair_digits = Vec::new();
        let mut terminal_row_start = [0u16; 179];
        let mut terminal_row_min = [0i16; 178];
        for a in 0..178i32 {
            terminal_row_start[a as usize] = pair_digits.len() as u16;
            let mut first = true;
            for b in -103..=103i32 {
                let norm = a*a + 3*a*b + 3*b*b;
                if norm >= 7921 || (a == 0 && b < 0) { continue; }
                if first { terminal_row_min[a as usize] = b as i16; first = false; }
                pair_digits.push((a as i16, b as i16));
            }
            assert!(!first);
        }
        terminal_row_start[178] = pair_digits.len() as u16;
        assert_eq!(pair_digits.len(), 14_344);
        assert_eq!(pair_digits[0], (0, 0));
        let terminal_pairs = build_u256_window(&pair_digits, base);
        let entries = digit_windows.iter().map(|row| row.len()).sum::<usize>();
        assert_eq!(entries, 18 * 6106);
        assert_eq!(size_of::<U256Affine>(), 64);
        let retained_bytes = (entries + terminal_pairs.len()) * size_of::<U256Affine>()
            + size_of::<[super::U256; 3]>()
            + size_of::<Self>()
            + digit_windows.capacity() * size_of::<Box<[U256Affine]>>();
        Self { digit_windows, terminal_pairs,
               terminal_row_start, terminal_row_min, retained_bytes }
    }
}
""")

    start = source.index("pub(super) fn multiply_u256_tau_split_prime_radix(")
    begin = source.index("    let mut buckets = [U256XYZZ::identity(); 3];", start)
    end_anchor = "    let point = bucket.affine_hex_binary_inverse();\n"
    end = source.index(end_anchor, begin) + len(end_anchor)
    source = source[:begin] + """    let mut bucket = U256XYZZ::identity();
    let mut terms = 0usize;
    let mut ops = SplitPrimeOpCounts::default();
    for row in &tables.digit_windows {
        let (next_a, next_b, index, sign) = split_prime_unit_step(a, b, tables);
        a = next_a;
        b = next_b;
        if index != 0 {
            let mut point = row[index];
            ops.digit_point_reads += 1;
            if sign != 0 {
                point.y = u256_sub(super::U256::ZERO, point.y);
                ops.sign_flips += 1;
            }
            if !bucket.is_identity() { ops.mixed_add_nontrivial += 1; }
            bucket = bucket.add_mixed(point);
            terms += 1;
        }
    }
    let (ai, aneg) = a.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);
    let (bi, bneg) = b.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);
    let signed_a = if aneg { -(ai as i64) } else { ai as i64 };
    let signed_b = if bneg { -(bi as i64) } else { bi as i64 };
    let terminal_norm = signed_a*signed_a + 3*signed_a*signed_b
        + 3*signed_b*signed_b;
    assert!(terminal_norm < 7921, "direct norm-12211 terminal bound");
    let negate = signed_a < 0 || (signed_a == 0 && signed_b < 0);
    let ca = if negate { -signed_a } else { signed_a } as usize;
    let cb = if negate { -signed_b } else { signed_b };
    let row_start = tables.terminal_row_start[ca] as usize;
    let row_offset = usize::try_from(
        cb - i64::from(tables.terminal_row_min[ca])).unwrap();
    let index = row_start + row_offset;
    assert!(index < tables.terminal_row_start[ca + 1] as usize);
    if index != 0 {
        let mut point = tables.terminal_pairs[index];
        ops.terminal_point_reads += 1;
        if negate {
            point.y = u256_sub(super::U256::ZERO, point.y);
            ops.sign_flips += 1;
        }
        if !bucket.is_identity() { ops.mixed_add_nontrivial += 1; }
        bucket = bucket.add_mixed(point);
        terms += 1;
    }
    let point = bucket.affine_hex_binary_inverse();
""" + source[end:]

    test_begin = source.index("    #[test]\n    fn split_prime_12211_residue_quotients_exhaustive()")
    test_end = source.index("    #[test]\n    fn split_prime_no_fallback_random_replay()", test_begin)
    source = source[:test_begin] + """    #[test]
    fn split_prime_12211_direct_residue_quotients_exhaustive() {
        fn small_value(value: Signed192) -> i32 {
            assert_eq!(value.limbs[1..], [0, 0]);
            let magnitude = i32::try_from(value.limbs[0]).unwrap();
            if value.negative { -magnitude } else { magnitude }
        }
        let tables = &*SPLIT_PRIME_TABLES;
        let mut checked_steps = 0usize;
        for residue in 0..SPLIT_PRIME_NORM {
            let digit = if residue <= 6105 { residue } else { residue - 12211 };
            for b in [-7i32, 0, 7] {
                for shift in [-SPLIT_PRIME_NORM, 0, SPLIT_PRIME_NORM] {
                    let a = residue - SPLIT_PRIME_TAU_RESIDUE * b + shift;
                    let numerator = a - digit + SPLIT_PRIME_TAU_RESIDUE * b;
                    assert_eq!(numerator.rem_euclid(SPLIT_PRIME_NORM), 0);
                    let k = numerator.div_euclid(SPLIT_PRIME_NORM);
                    let (next_a, next_b, index, sign) =
                        split_prime_unit_step(Signed192::from_i32(a),
                                              Signed192::from_i32(b), tables);
                    assert_eq!(index, digit.unsigned_abs() as usize);
                    assert_eq!(sign, usize::from(digit < 0));
                    assert_eq!(small_value(next_a), 109*k-b);
                    assert_eq!(small_value(next_b), k);
                    checked_steps += 1;
                }
            }
        }
        assert_eq!(checked_steps, 12211 * 9);
        println!("direct_norm12211_residues=12211 quotient_cases={checked_steps}");
    }

    #[test]
    fn split_prime_12211_direct_terminal_indices_exhaustive() {
        let tables = &*SPLIT_PRIME_TABLES;
        let mut count = 0usize;
        for a in 0..178i32 {
            for b in -103..=103i32 {
                let norm = a*a + 3*a*b + 3*b*b;
                if norm >= 7921 || (a == 0 && b < 0) { continue; }
                let offset = usize::try_from(
                    b - i32::from(tables.terminal_row_min[a as usize])).unwrap();
                let index = tables.terminal_row_start[a as usize] as usize + offset;
                assert_eq!(index, count, "terminal pair ({a},{b})");
                count += 1;
            }
        }
        assert_eq!(count, 14_344);
        assert_eq!(tables.terminal_pairs.len(), count);
        println!("direct_norm12211_terminal_indices={count}");
    }

    #[test]
    fn split_prime_direct_signed_digit_images_exhaustive() {
        let tables = &*SPLIT_PRIME_TABLES;
        let mut checked = 0usize;
        for row in &tables.digit_windows {
            assert_eq!(row.len(), 6106);
            for &entry in row.iter() {
                let reference = U256OrbitXAffine::from_affine(entry);
                for sign in 0..2 {
                    let mut actual = U256XYZZ::from_affine(entry);
                    if sign != 0 {
                        actual.y = u256_sub(super::super::U256::ZERO, actual.y);
                    }
                    let expected = reference.unit(sign);
                    assert_eq!(actual.x.0, expected.x.0);
                    assert_eq!(actual.y.0, expected.y.0);
                    checked += 1;
                }
            }
        }
        assert_eq!(checked, 18 * 6106 * 2);
        println!("direct_digit_sign_images={checked}");
    }

""" + source[test_end:]
    path.write_text(source)
    receipt = root / "native-bench-overlay.json"
    metadata = json.loads(receipt.read_text())
    metadata.update({
        "variant": "split_prime_12211_direct_one_bucket",
        "direct_one_bucket_overlay_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "generated_module_sha256": sha256(path.read_bytes()).hexdigest(),
    })
    receipt.write_text(json.dumps(metadata, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"variant": metadata["variant"],
                      "generated_module_sha256": metadata["generated_module_sha256"]}))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: native_overlay.py GENERATED_NORM12211_CARGO_DIR")
    main(Path(sys.argv[1]))
