#!/usr/bin/env python3
"""Try norm-110557 digit prime with 15 full two-x rows under 32 MiB."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = "3dead29b00d7c5bd84851bd59b29eb477480daf05e008debaffbfb002c7b8f6b"
WINDOWS_SHA256 = "71136ada79d64d136344c8649fe59a07ceb6cbcc03f30a1e66c3f1bc4848bf5d"


def replace(text: str, old: str, new: str, count: int = 1) -> str:
    assert text.count(old) == count, (old, text.count(old))
    return text.replace(old, new)


def main(root: Path) -> None:
    front = root / "src/bin/eisenstein_fixed.rs"
    windows = root / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    f, w = front.read_text(), windows.read_text()
    assert sha256(f.encode()).hexdigest() == FRONT_SHA256
    assert sha256(w.encode()).hexdigest() == WINDOWS_SHA256

    start = w.index("const SPLIT_PRIME_NORM: i32 =")
    end = w.index("#[derive(Clone, Copy, Debug, Default)]", start)
    core = w[start:end]
    core = core.replace("SPLIT_PRIME_", "ALT_SPLIT_PRIME_")
    core = core.replace("split_prime", "alt_split_prime")
    core = core.replace("SplitPrimeTables", "AltSplitPrimeTables")
    for name in ("orbit_omega_pair", "orbit_canonical", "orbit_code", "orbit_affine"):
        core = core.replace(name, "alt_" + name)
    for old, new in (
        ("ALT_SPLIT_PRIME_NORM: i32 = 136531", "ALT_SPLIT_PRIME_NORM: i32 = 110557"),
        ("ALT_SPLIT_PRIME_TAU_RESIDUE: i32 = 371", "ALT_SPLIT_PRIME_TAU_RESIDUE: i32 = 334"),
        ("ALT_SPLIT_PRIME_STEPS: usize = 14", "ALT_SPLIT_PRIME_STEPS: usize = 15"),
        ("ALT_SPLIT_PRIME_DIGIT_LIMIT: usize = 68265", "ALT_SPLIT_PRIME_DIGIT_LIMIT: usize = 55278"),
        ("ALT_SPLIT_PRIME_TERMINAL_LIMIT: usize = 445", "ALT_SPLIT_PRIME_TERMINAL_LIMIT: usize = 100"),
        ("(739*lift+136531).div_euclid(273062)", "(665*lift+110557).div_euclid(221114)"),
        ("let a = lift-371*b;", "let a = lift-334*b;"),
        ("times_alt_split_prime_small(368)", "times_alt_split_prime_small(331)"),
        ("affine_multiples(base, 371)", "affine_multiples(base, 334)"),
        ("assert_eq!(digit_pairs.len(), 68266);", "assert_eq!(digit_pairs.len(), 55279);"),
        ("assert_eq!(max_norm, 45387);", "assert!(max_norm < 40000);"),
        ("assert_eq!(digit_seeds.len(),22756);", "assert!(digit_seeds.len() < u16::MAX as usize);"),
        ("for a in -445..=445i32", "for a in -100..=100i32"),
        ("for b in -445..=445i32", "for b in -100..=100i32"),
        ("if norm < 49729", "if norm < 5000"),
        ("assert_eq!(terminal_pairs_full.len(),180421);", "assert!(!terminal_pairs_full.is_empty());"),
        ("assert_eq!(terminal_seeds.len(),30071);", "assert!(terminal_seeds.len() < u16::MAX as usize);"),
        ("891*891", "201*201"),
        ("((i32::from(pair.0)+445)*891+i32::from(pair.1)+445)", "((i32::from(pair.0)+100)*201+i32::from(pair.1)+100)"),
        ("assert_eq!(entries, 14*22756);", "assert_eq!(entries, ALT_SPLIT_PRIME_STEPS*digit_windows[0].len());"),
    ):
        core = replace(core, old, new)

    start2 = w.index("struct SplitPrimeTwoXTables {")
    end2 = w.index("fn split_prime_two_x_affine_leaves(", start2)
    table = w[start2:end2]
    table = table.replace("SplitPrimeTwoXTables", "AltSplitPrimeTwoXTables")
    table = table.replace("SplitPrimeTables", "AltSplitPrimeTables")
    table = table.replace("SPLIT_PRIME_TWO_X_TABLES", "ALT_SPLIT_PRIME_TWO_X_TABLES")
    table = table.replace("split_prime_two_x_table", "alt_split_prime_two_x_table")
    table = replace(table, "assert_eq!(entries,14*22756);",
                    "assert_eq!(entries,ALT_SPLIT_PRIME_STEPS*digit_windows[0].len());")
    table = replace(table, "assert_eq!(terminal_pairs.len(),30071);",
                    "assert!(!terminal_pairs.is_empty());")
    table = replace(table, "        Self { digit_pairs,digit_codes,digit_windows,terminal_pairs,",
                    "        assert!(retained_bytes < 32*1024*1024);\n"
                    "        Self { digit_pairs,digit_codes,digit_windows,terminal_pairs,")

    start3 = w.index("fn split_prime_two_x_affine_leaves(")
    end3 = w.index("// The seven even-numbered digit windows", start3)
    leaves = w[start3:end3]
    leaves = leaves.replace("split_prime", "alt_split_prime")
    leaves = leaves.replace("SPLIT_PRIME_", "ALT_SPLIT_PRIME_")
    leaves = replace(leaves, "assert!(terminal_norm < 49729,\"nearest-digit norm-136531 terminal bound\");",
                     "assert!(terminal_norm < 5000,\"norm-110557 terminal bound\");")
    leaves = replace(leaves, "((signed_a+445)*891+signed_b+445)",
                     "((signed_a+100)*201+signed_b+100)")
    assert "multiply_u256_tau_alt_split_prime_two_x_affine_batch" in leaves

    insertion = w.index("\n#[cfg(test)]\nmod split_prime_tests")
    w = w[:insertion] + "\n" + core + table + leaves + w[insertion:]
    windows.write_text(w)

    start = f.index("fn benchmark_mixed640_two_x_uniform(")
    end = f.index("fn benchmark_mixed640_affine_layer_uniform(", start)
    benchmark = f[start:end]
    benchmark = benchmark.replace("two_x_uniform", "alt_radix_uniform")
    benchmark = benchmark.replace("warm_split_prime_two_x_table", "warm_alt_split_prime_two_x_table")
    benchmark = benchmark.replace("multiply_u256_tau_split_prime_two_x_affine_batch",
                                  "multiply_u256_tau_alt_split_prime_two_x_affine_batch")
    f = f[:end] + benchmark + f[end:]
    dispatch = '''    if args.len() == 3 && args[0] == "--benchmark-alt-radix-uniform" {
        benchmark_mixed640_alt_radix_uniform(
            args[2].parse().expect("uniform passes"),
            args[1].parse().expect("batch size"));
        return;
    }
'''
    needle = "    let args: Vec<String> = std::env::args().skip(1).collect();\n"
    f = replace(f, needle, needle + dispatch)
    front.write_text(f)
    print("front_sha256=" + sha256(front.read_bytes()).hexdigest())
    print("windows_sha256=" + sha256(windows.read_bytes()).hexdigest())


if __name__ == "__main__":
    main(Path(sys.argv[1]))
