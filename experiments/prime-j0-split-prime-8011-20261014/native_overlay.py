#!/usr/bin/env python3
"""Retarget the verified three-bucket generated Rust module to norm 8011."""

from hashlib import sha256
import json
from pathlib import Path
import sys


def main(target: Path) -> None:
    module = target / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    source = module.read_text()
    start = source.index("const SPLIT_PRIME_NORM: i32 = 4831;")
    end = source.index("    #[test]\n    fn split_prime_no_fallback_random_replay()", start)
    middle = source[start:end]

    def once(old: str, new: str) -> None:
        nonlocal middle
        count = middle.count(old)
        assert count == 1, (old, count)
        middle = middle.replace(old, new, 1)

    for old, new in (
        ("const SPLIT_PRIME_NORM: i32 = 4831;", "const SPLIT_PRIME_NORM: i32 = 8011;"),
        ("const SPLIT_PRIME_TAU_RESIDUE: i32 = 71;", "const SPLIT_PRIME_TAU_RESIDUE: i32 = 91;"),
        ("const SPLIT_PRIME_STEPS: usize = 20;", "const SPLIT_PRIME_STEPS: usize = 19;"),
        ("const SPLIT_PRIME_DIGIT_LIMIT: usize = 2415;", "const SPLIT_PRIME_DIGIT_LIMIT: usize = 2640;"),
        ("const SPLIT_PRIME_TERMINAL_LIMIT: usize = 112;", "const SPLIT_PRIME_TERMINAL_LIMIT: usize = 92;"),
        ("let next_a = k.times_split_prime_small(68).sub(shifted_b);", "let next_a = k.times_split_prime_small(88).sub(shifted_b);"),
        ("terminal_row_start: [u16; 113]", "terminal_row_start: [u16; 93]"),
        ("terminal_row_min: [i16; 112]", "terminal_row_min: [i16; 92]"),
        ("let multiples = affine_multiples(base, 1564);", "let multiples = affine_multiples(base, 2640);"),
        ("assert_eq!(*seeds.last().unwrap(), 1564);", "assert_eq!(*seeds.last().unwrap(), 2640);"),
        ("// pi = 71 - tau.", "// pi = 91 - tau."),
        ("affine_multiples(base, 71).pop()", "affine_multiples(base, 91).pop()"),
        ("let mut terminal_row_start = [0u16; 113];", "let mut terminal_row_start = [0u16; 93];"),
        ("let mut terminal_row_min = [0i16; 112];", "let mut terminal_row_min = [0i16; 92];"),
        ("terminal_row_start[112] = pair_digits.len() as u16;", "terminal_row_start[92] = pair_digits.len() as u16;"),
        ("assert_eq!(pair_digits.len(), 5680);", "assert_eq!(pair_digits.len(), 3838);"),
        ("assert_eq!(entries, 16_120);", "assert_eq!(entries, 25_384);"),
        ("assert!(terminal_norm < 3136, \"norm-4831 terminal bound\");",
         "assert!(terminal_norm < 2116, \"norm-8011 terminal bound\");"),
        ("centered(4761 * residue)", "centered(7921 * residue)"),
        ("centered(69 * residue)", "centered(89 * residue)"),
        ("seeds.extend((1..=1564)", "seeds.extend((1..=2640)"),
        ("norm((da, db)) <= i64::from(1564 * 1564)",
         "norm((da, db)) <= i64::from(2640 * 2640)"),
        ("small_value(next_a), 68*k-(b-db)", "small_value(next_a), 88*k-(b-db)"),
        ("assert_eq!(checked_steps, 4831 * 9);", "assert_eq!(checked_steps, 8011 * 9);"),
        ("norm4831_residues=4831", "norm8011_residues=8011"),
        ("assert_eq!(count, 5680);", "assert_eq!(count, 3838);"),
        ("norm4831_terminal_indices", "norm8011_terminal_indices"),
        ("assert_eq!(row.len(), 806);", "assert_eq!(row.len(), 1336);"),
        ("assert_eq!(checked, 20 * 806 * 6);", "assert_eq!(checked, 19 * 1336 * 6);"),
    ):
        once(old, new)

    for old, new, count in (
        ("assert_eq!(seeds.len(), 806);", "assert_eq!(seeds.len(), 1336);", 2),
        ("for a in 0..112i32 {", "for a in 0..92i32 {", 2),
        ("for b in -65..=65i32 {", "for b in -54..=54i32 {", 2),
        ("norm >= 3136", "norm >= 2116", 2),
        ("fn split_prime_4831_", "fn split_prime_8011_", 2),
    ):
        assert middle.count(old) == count, (old, middle.count(old))
        middle = middle.replace(old, new)
    assert "4831" not in middle and "1564" not in middle
    module.write_text(source[:start] + middle + source[end:])
    receipt = target / "native-bench-overlay.json"
    metadata = json.loads(receipt.read_text())
    metadata.update({
        "variant": "split_prime_8011_three_bucket_affine_digit",
        "norm8011_overlay_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "generated_module_sha256": sha256(module.read_bytes()).hexdigest(),
    })
    receipt.write_text(json.dumps(metadata, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"variant": metadata["variant"],
                      "generated_module_sha256": metadata["generated_module_sha256"]}))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: native_overlay.py GENERATED_THREE_BUCKET_CARGO_DIR")
    main(Path(sys.argv[1]))
