#!/usr/bin/env python3
"""Retarget the verified norm-8011 terminal-orbit module to norm 12211."""

from hashlib import sha256
import json
from pathlib import Path
import sys

SOURCE_SHA256 = "33f2bb96f63ecc6ce6b334fd6fc2674fb251925a8c231d24f77dbcbb64abcc46"


def main(root: Path) -> None:
    path = root / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    source = path.read_text()
    assert sha256(source.encode()).hexdigest() == SOURCE_SHA256
    start = source.index("const SPLIT_PRIME_NORM: i32 = 8011;")
    end = source.index("    #[test]\n    fn split_prime_no_fallback_random_replay()", start)
    middle = source[start:end]

    changes = (
        ("const SPLIT_PRIME_NORM: i32 = 8011;", "const SPLIT_PRIME_NORM: i32 = 12211;"),
        ("const SPLIT_PRIME_TAU_RESIDUE: i32 = 91;", "const SPLIT_PRIME_TAU_RESIDUE: i32 = 112;"),
        ("const SPLIT_PRIME_STEPS: usize = 19;", "const SPLIT_PRIME_STEPS: usize = 18;"),
        ("const SPLIT_PRIME_DIGIT_LIMIT: usize = 2640;", "const SPLIT_PRIME_DIGIT_LIMIT: usize = 4033;"),
        ("const SPLIT_PRIME_TERMINAL_LIMIT: usize = 92;", "const SPLIT_PRIME_TERMINAL_LIMIT: usize = 140;"),
        ("times_split_prime_small(88)", "times_split_prime_small(109)"),
        ("terminal_row_start: [u16; 93]", "terminal_row_start: [u16; 141]"),
        ("terminal_row_min: [i16; 92]", "terminal_row_min: [i16; 140]"),
        ("affine_multiples(base, 2640)", "affine_multiples(base, 4033)"),
        ("assert_eq!(seeds.len(), 1336);", "assert_eq!(seeds.len(), 2036);"),
        ("assert_eq!(*seeds.last().unwrap(), 2640);", "assert_eq!(*seeds.last().unwrap(), 4033);"),
        ("// pi = 91 - tau.", "// pi = 112 - tau."),
        ("affine_multiples(base, 91).pop()", "affine_multiples(base, 112).pop()"),
        ("let mut terminal_row_start = [0u16; 93];", "let mut terminal_row_start = [0u16; 141];"),
        ("let mut terminal_row_min = [0i16; 92];", "let mut terminal_row_min = [0i16; 140];"),
        ("for a in 0..92i32 {", "for a in 0..140i32 {"),
        ("for b in -54..=54i32 {", "for b in -81..=81i32 {"),
        ("norm >= 2116", "norm >= 4900"),
        ("norm(pair) >= 2116", "norm(pair) >= 4900"),
        ("terminal_row_start[92]", "terminal_row_start[140]"),
        ("assert_eq!(pair_digits.len(), 3838);", "assert_eq!(pair_digits.len(), 8872);"),
        ("assert_eq!(orbit_seeds.len(), 1280);", "assert_eq!(orbit_seeds.len(), 2958);"),
        ("assert_eq!(entries, 25_384);", "assert_eq!(entries, 36_648);"),
        ("terminal_norm < 2116", "terminal_norm < 4900"),
        ("norm-8011 terminal bound", "norm-12211 terminal bound"),
        ("split_prime_8011_", "split_prime_12211_"),
        ("centered(7921 * residue)", "centered(12100 * residue)"),
        ("centered(89 * residue)", "centered(110 * residue)"),
        ("seeds.extend((1..=2640)", "seeds.extend((1..=4033)"),
        ("i64::from(2640 * 2640)", "i64::from(4033 * 4033)"),
        ("88*k-(b-db)", "109*k-(b-db)"),
        ("checked_steps, 8011 * 9", "checked_steps, 12211 * 9"),
        ("norm8011_residues=8011", "norm12211_residues=12211"),
        ("assert_eq!(count, 3838);", "assert_eq!(count, 8872);"),
        ("tables.terminal_orbits.len(), 1280", "tables.terminal_orbits.len(), 2958"),
        ("seeds.len(), 1280", "seeds.len(), 2958"),
        ("norm8011_terminal_indices", "norm12211_terminal_indices"),
        ("row.len(), 1336", "row.len(), 2036"),
        ("checked, 19 * 1336 * 6", "checked, 18 * 2036 * 6"),
    )
    for old, new in changes:
        assert old in middle, old
        middle = middle.replace(old, new)
    assert not any(x in middle for x in ("8011", "2640", "1336", "3838", "1280", "2116"))
    path.write_text(source[:start] + middle + source[end:])
    receipt = root / "native-bench-overlay.json"
    metadata = json.loads(receipt.read_text())
    metadata.update({
        "variant": "split_prime_12211_three_bucket_terminal_orbit",
        "norm12211_overlay_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "generated_module_sha256": sha256(path.read_bytes()).hexdigest(),
    })
    receipt.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"variant": metadata["variant"],
                      "generated_module_sha256": metadata["generated_module_sha256"]}))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: native_overlay.py GENERATED_NORM8011_ORBIT_CARGO_DIR")
    main(Path(sys.argv[1]))
