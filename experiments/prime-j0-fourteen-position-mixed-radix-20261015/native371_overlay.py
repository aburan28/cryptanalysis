#!/usr/bin/env python3
"""Derive the fixed fourteen-position 371-tau native timing gate."""

from hashlib import sha256
from pathlib import Path
import sys

PARENT_SHA256 = "aff42df465e44e2f3fe1d10c524b6a336a76c5091791894cac5cba618cc441ee"


def once(source, old, new):
    assert source.count(old) == 1, (old[:80], source.count(old))
    return source.replace(old, new)


def main(root):
    path = root / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    original = path.read_text()
    assert sha256(original.encode()).hexdigest() == PARENT_SHA256
    start = original.index("const SPLIT_PRIME_NORM: i32 = 71023;")
    end = original.index("\npub(super) fn warm_mixed640_pretau_table()", start)
    section = original[start:end]
    changes = (
        ("const SPLIT_PRIME_NORM: i32 = 71023;", "const SPLIT_PRIME_NORM: i32 = 136531;"),
        ("const SPLIT_PRIME_TAU_RESIDUE: i32 = 268;", "const SPLIT_PRIME_TAU_RESIDUE: i32 = 371;"),
        ("const SPLIT_PRIME_STEPS: usize = 15;", "const SPLIT_PRIME_STEPS: usize = 14;"),
        ("const SPLIT_PRIME_DIGIT_LIMIT: usize = 35511;", "const SPLIT_PRIME_DIGIT_LIMIT: usize = 68265;"),
        ("const SPLIT_PRIME_TERMINAL_LIMIT: usize = 163;", "const SPLIT_PRIME_TERMINAL_LIMIT: usize = 445;"),
        ("(533*lift+71023).div_euclid(142046)", "(739*lift+136531).div_euclid(273062)"),
        ("let a = lift-268*b;", "let a = lift-371*b;"),
        ("k.times_split_prime_small(265)", "k.times_split_prime_small(368)"),
        ("assert_eq!(digit_pairs.len(), 35512);", "assert_eq!(digit_pairs.len(), 68266);"),
        ("assert_eq!(max_norm, 23497);", "assert_eq!(max_norm, 45387);"),
        ("assert_eq!(digit_seeds.len(),11838);", "assert_eq!(digit_seeds.len(),22756);"),
        ("affine_multiples(base, 268)", "affine_multiples(base, 371)"),
        ("for a in -163..=163i32 {", "for a in -445..=445i32 {"),
        ("for b in -163..=163i32 {", "for b in -445..=445i32 {"),
        ("if norm < 6724 { terminal_pairs_full.push", "if norm < 49729 { terminal_pairs_full.push"),
        ("assert_eq!(terminal_pairs_full.len(),24373);", "assert_eq!(terminal_pairs_full.len(),180421);"),
        ("assert_eq!(terminal_seeds.len(),4063);", "assert_eq!(terminal_seeds.len(),30071);"),
        ("vec![(u16::MAX,0u8);327*327]", "vec![(u16::MAX,0u8);891*891]"),
        ("((i32::from(pair.0)+163)*327+i32::from(pair.1)+163)",
         "((i32::from(pair.0)+445)*891+i32::from(pair.1)+445)"),
        ("assert_eq!(entries, 15*11838);", "assert_eq!(entries, 14*22756);"),
        ("assert!(terminal_norm < 6724", "assert!(terminal_norm < 49729"),
        ("((signed_a+163)*327+signed_b+163)", "((signed_a+445)*891+signed_b+445)"),
        ("nearest-digit norm-71023 terminal bound", "nearest-digit norm-136531 terminal bound"),
        ("assert_eq!((a+268*b-residue).rem_euclid(71023),0);",
         "assert_eq!((a+371*b-residue).rem_euclid(136531),0);"),
        ("assert!(a*a+3*a*b+3*b*b <= 23497);",
         "assert!(a*a+3*a*b+3*b*b <= 45387);"),
    )
    for old, new in changes:
        section = once(section, old, new)
    assert section.count("radix_71023") == 4
    section = section.replace("radix_71023", "radix_136531")
    output = original[:start] + section + original[end:]
    path.write_text(output)
    print(sha256(output.encode()).hexdigest())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: native371_overlay.py CARGO_ROOT")
    main(Path(sys.argv[1]))
