#!/usr/bin/env python3
"""Generate the 20-step norm-4831 native scalar evaluator overlay."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent


def replace_once(source: str, old: str, new: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"expected one anchor, found {count}: {old[:80]}")
    return source.replace(old, new, 1)


EXHAUSTIVE_TEST = r"""    #[test]
    fn split_prime_4831_residue_quotients_exhaustive() {
        fn centered(value: i32) -> i32 {
            let residue = value.rem_euclid(SPLIT_PRIME_NORM);
            residue.min(SPLIT_PRIME_NORM - residue)
        }
        fn canonical_seed(residue: i32) -> i32 {
            [centered(residue), centered(4761 * residue),
             centered(69 * residue)].into_iter().min().unwrap()
        }
        fn small_value(value: Signed192) -> i32 {
            assert_eq!(value.limbs[1..], [0, 0]);
            let magnitude = i32::try_from(value.limbs[0]).unwrap();
            if value.negative { -magnitude } else { magnitude }
        }
        let tables = &*SPLIT_PRIME_TABLES;
        let mut seeds = vec![0i32];
        seeds.extend((1..=1564).filter(|&seed| canonical_seed(seed) == seed));
        assert_eq!(seeds.len(), 806);
        let mut checked_steps = 0usize;
        for residue in 0..SPLIT_PRIME_NORM {
            let code = usize::from(tables.residue_codes[residue as usize]);
            let index = code / 6;
            let unit = code % 6;
            let seed = seeds[index];
            assert_eq!(seed, canonical_seed(residue), "seed residue {residue}");
            let (da, db) = unit_images((seed, 0))[unit];
            let digit_word = da + SPLIT_PRIME_TAU_RESIDUE * db;
            assert_eq!(digit_word.rem_euclid(SPLIT_PRIME_NORM), residue);
            assert!(norm((da, db)) <= i64::from(1564 * 1564));
            assert_eq!(i32::from(tables.digit_b[residue as usize]), db);
            assert_eq!(i32::from(tables.digit_quotient[residue as usize]),
                       digit_word.div_euclid(SPLIT_PRIME_NORM));
            for b in [-7i32, 0, 7] {
                for shift in [-SPLIT_PRIME_NORM, 0, SPLIT_PRIME_NORM] {
                    let a = residue - SPLIT_PRIME_TAU_RESIDUE * b + shift;
                    let numerator = a - da + SPLIT_PRIME_TAU_RESIDUE * (b-db);
                    assert_eq!(numerator.rem_euclid(SPLIT_PRIME_NORM), 0);
                    let k = numerator.div_euclid(SPLIT_PRIME_NORM);
                    let (next_a, next_b, actual_index, actual_unit) =
                        split_prime_unit_step(Signed192::from_i32(a),
                                              Signed192::from_i32(b), tables);
                    assert_eq!((actual_index, actual_unit), (index, unit));
                    assert_eq!(small_value(next_a), 68*k-(b-db),
                               "next a residue {residue} b {b} shift {shift}");
                    assert_eq!(small_value(next_b), k,
                               "next b residue {residue} b {b} shift {shift}");
                    checked_steps += 1;
                }
            }
        }
        assert_eq!(checked_steps, 4831 * 9);
        println!("norm4831_residues=4831 quotient_cases={checked_steps}");
    }

"""


TERMINAL_INDEX_TEST = r"""    #[test]
    fn split_prime_4831_terminal_indices_exhaustive() {
        let tables = &*SPLIT_PRIME_TABLES;
        let mut count = 0usize;
        for a in 0..112i32 {
            for b in -65..=65i32 {
                let norm = a*a + 3*a*b + 3*b*b;
                if norm >= 3136 || (a == 0 && b < 0) { continue; }
                let offset = usize::try_from(
                    b - i32::from(tables.terminal_row_min[a as usize])).unwrap();
                let index = tables.terminal_row_start[a as usize] as usize + offset;
                assert_eq!(index, count, "terminal pair ({a},{b})");
                count += 1;
            }
        }
        assert_eq!(count, 5680);
        assert_eq!(tables.terminal_pairs.len(), count);
        println!("norm4831_terminal_indices={count}");
    }

"""


def main(target: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "native_split_prime_bench", HERE / "native_split_prime_bench.py")
    base = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(base)
    base.main(target, fused_terminal=True, unit_compressed=True)
    target = target.resolve()
    module = target / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    source = module.read_text()
    substitutions = {
        "const SPLIT_PRIME_NORM: i32 = 3301;":
            "const SPLIT_PRIME_NORM: i32 = 4831;",
        "const SPLIT_PRIME_TAU_RESIDUE: i32 = 1576;":
            "const SPLIT_PRIME_TAU_RESIDUE: i32 = 71;",
        "const SPLIT_PRIME_STEPS: usize = 21;":
            "const SPLIT_PRIME_STEPS: usize = 20;",
        "const SPLIT_PRIME_DIGIT_LIMIT: usize = 1650;":
            "const SPLIT_PRIME_DIGIT_LIMIT: usize = 2415;",
        "const SPLIT_PRIME_TERMINAL_LIMIT: usize = 663;":
            "const SPLIT_PRIME_TERMINAL_LIMIT: usize = 112;",
        "let next_a = k.times_split_prime_small(23).sub(shifted_b.times_split_prime_small(11));":
            "let next_a = k.times_split_prime_small(68).sub(shifted_b);",
        "let next_b = k.times_split_prime_small(21).sub(shifted_b.times_split_prime_small(10));":
            "let next_b = k;",
        "let multiples = affine_multiples(base, 1064);":
            "let multiples = affine_multiples(base, 1564);",
        "        assert_eq!(seeds.len(), 551);":
            "        assert_eq!(seeds.len(), 806);",
        "        assert_eq!(*seeds.last().unwrap(), 1064);":
            "        assert_eq!(*seeds.last().unwrap(), 1564);",
        "// pi = 86 - 21*tau. All of this is reusable table preparation.":
            "// pi = 71 - tau. All of this is reusable table preparation.",
        "let ordinary = affine_multiples(base, 86).pop().unwrap();":
            "let ordinary = affine_multiples(base, 71).pop().unwrap();",
        "let tau = affine_multiples(base.tau(), 21).pop().unwrap().neg().into_affine();":
            "let tau = base.tau().neg().into_affine();",
        "        assert_eq!(entries, 12_899);":
            "        assert_eq!(entries, 16_346);",
        "// retained for exact fallback under the original coordinate bound.":
            "// retained for an independently checked terminal path.",
    }
    for old, new in substitutions.items():
        source = replace_once(source, old, new)
    source = replace_once(source,
        "    digit_windows: Vec<Box<[U256OrbitXAffine]>>,\n",
        "    digit_windows: Vec<Box<[U256TwoXAffine]>>,\n")
    source = replace_once(source,
        "fn split_prime_orbit_row(base: Jacobian, seeds: &[i16])\n"
        "    -> Box<[U256OrbitXAffine]> {",
        "fn split_prime_orbit_row(base: Jacobian, seeds: &[i16])\n"
        "    -> Box<[U256TwoXAffine]> {")
    source = replace_once(source,
        "        U256OrbitXAffine::from_affine(point)\n"
        "    }).collect::<Vec<_>>().into_boxed_slice()\n}",
        "        U256TwoXAffine::from_affine(point)\n"
        "    }).collect::<Vec<_>>().into_boxed_slice()\n}")
    source = replace_once(source,
        "        assert_eq!(entries, 16_346);\n"
        "        assert_eq!(size_of::<U256Affine>(), 64);\n"
        "        assert_eq!(size_of::<U256OrbitXAffine>(), 128);",
        "        assert_eq!(entries, 16_346);\n"
        "        assert_eq!(size_of::<U256Affine>(), 64);\n"
        "        assert_eq!(size_of::<U256TwoXAffine>(), 96);")
    source = replace_once(source,
        "digit_windows.iter().map(|row| row.len()).sum::<usize>()\n"
        "                * size_of::<U256OrbitXAffine>()",
        "digit_windows.iter().map(|row| row.len()).sum::<usize>()\n"
        "                * size_of::<U256TwoXAffine>()")
    old_capacity = "digit_windows.capacity() * size_of::<Box<[U256OrbitXAffine]>>()"
    source = replace_once(source, old_capacity,
                          old_capacity.replace("OrbitX", "TwoX"))
    source = replace_once(source,
        "    terminal_plain: Box<[U256Affine]>,\n"
        "    terminal_tau: Box<[U256Affine]>,\n", "")
    source = replace_once(source,
        "        let terminal_plain = split_prime_affine_row(base, SPLIT_PRIME_TERMINAL_LIMIT);\n"
        "        let terminal_tau = split_prime_affine_row(base.tau(), SPLIT_PRIME_TERMINAL_LIMIT);\n",
        "")
    source = replace_once(source,
        "        let entries = digit_windows.iter().map(|row| row.len()).sum::<usize>()\n"
        "            + terminal_plain.len() + terminal_tau.len();\n"
        "        assert_eq!(entries, 16_346);",
        "        let entries = digit_windows.iter().map(|row| row.len()).sum::<usize>();\n"
        "        assert_eq!(entries, 16_120);")
    source = replace_once(source,
        "(terminal_plain.len() + terminal_tau.len() + terminal_pairs.len())\n"
        "                * size_of::<U256Affine>()",
        "terminal_pairs.len() * size_of::<U256Affine>()")
    source = replace_once(source,
        "               terminal_plain, terminal_tau, terminal_pairs,\n",
        "               terminal_pairs,\n")
    source = replace_once(source,
        "    if terminal_norm < 3136 {\n",
        "    assert!(terminal_norm < 3136, \"norm-4831 terminal bound\");\n")
    source = replace_once(source,
        "    } else {\n"
        "    for (coordinate, row) in [(a, &tables.terminal_plain),\n"
        "                              (b, &tables.terminal_tau)] {\n"
        "        let (position, negative) =\n"
        "            coordinate.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);\n"
        "        if position != 0 {\n"
        "            let mut point = row[position];\n"
        "            if negative { point.y = u256_sub(super::U256::ZERO, point.y); }\n"
        "            bucket = bucket.add_mixed(point);\n"
        "            terms += 1;\n"
        "        }\n"
        "    }\n"
        "    }\n"
        "    let point = bucket.affine_hex_binary_inverse();",
        "    let point = bucket.affine_hex_binary_inverse();")
    anchor = "    #[test]\n    fn split_prime_holdout_matches_independent_binary() {"
    two_x_test = (base.DIGIT_TWO_X_TEST_RUST
                  .replace("row.len(), 66", "row.len(), 806")
                  .replace("21 * 66 * 6", "20 * 806 * 6"))
    source = replace_once(source, anchor,
                          EXHAUSTIVE_TEST + TERMINAL_INDEX_TEST + two_x_test
                          + base.TERMINAL_NO_FALLBACK_TEST_RUST + anchor)
    module.write_text(source)
    receipt_path = target / "native-bench-overlay.json"
    receipt = json.loads(receipt_path.read_text())
    receipt.update({
        "variant": "split_prime_radix_4831_unit_direct_two_x_fused_terminal",
        "split_prime_4831_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "generated_module_sha256": sha256(module.read_bytes()).hexdigest(),
    })
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: native_split_prime_4831.py TARGET_DIR")
    main(Path(sys.argv[1]))
