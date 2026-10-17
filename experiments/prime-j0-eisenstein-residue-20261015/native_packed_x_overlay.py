#!/usr/bin/env python3
"""Add a 65-byte Eisenstein-x affine table to the frozen uniform native source."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = "3dead29b00d7c5bd84851bd59b29eb477480daf05e008debaffbfb002c7b8f6b"
WINDOWS_SHA256 = "71136ada79d64d136344c8649fe59a07ceb6cbcc03f30a1e66c3f1bc4848bf5d"

PACKED_TYPE = r'''
// Coordinates a,b are signed 128-bit magnitudes representing x*2^128.
// Byte 32 carries their signs; bytes 33..65 store y in U256 Montgomery form.
#[derive(Clone, Copy)]
struct U256PackedXAffine([u8; 65]);

impl U256PackedXAffine {
    fn from_compact(point: CompactPairPoint, identity: bool) -> Self {
        if identity { return Self([0; 65]); }
        let affine = point.into_affine();
        let y = super::hybrid_pair_mont(affine.y);
        let mut bytes = [0u8; 65];
        for coordinate in 0..2 {
            for limb in 0..2 {
                let start = 16 * coordinate + 8 * limb;
                bytes[start..start+8].copy_from_slice(&point.limbs[coordinate][limb].to_le_bytes());
            }
        }
        bytes[32] = point.signs & 3;
        for limb in 0..4 {
            bytes[33+8*limb..41+8*limb].copy_from_slice(&y.0[limb].to_le_bytes());
        }
        Self(bytes)
    }

    fn unit(self, code: usize) -> U256Affine {
        assert!(code < 6);
        let coordinate = |index: usize| {
            let mut limbs = [0u64; 8];
            for limb in 0..2 {
                let start = 16 * index + 8 * limb;
                limbs[limb] = u64::from_le_bytes(self.0[start..start+8].try_into().unwrap());
            }
            super::Signed { negative: self.0[32] & (1 << index) != 0,
                            magnitude: super::Uint(limbs) }.normalized()
        };
        let mut x = super::Pair { a: coordinate(0), b: coordinate(1) };
        for _ in 0..code/2 { x = x.omega(); }
        let x = super::hybrid_pair_mont(x);
        let mut words = [0u64; 4];
        for limb in 0..4 {
            words[limb] = u64::from_le_bytes(self.0[33+8*limb..41+8*limb].try_into().unwrap());
        }
        let mut y = super::Uint(words);
        if code & 1 != 0 { y = u256_sub(super::U256::ZERO, y); }
        U256Affine { x, y }
    }
}

fn build_packed_x_window(digits: &[(i16, i16)], base: Jacobian)
    -> Box<[U256PackedXAffine]> {
    build_window(digits, base).iter().copied().enumerate()
        .map(|(index, point)| U256PackedXAffine::from_compact(point, index == 0))
        .collect::<Vec<_>>().into_boxed_slice()
}
'''


def replace_once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, (old[:80], text.count(old))
    return text.replace(old, new, 1)


def main(root: Path) -> None:
    front = root / "src/bin/eisenstein_fixed.rs"
    windows = root / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    f = front.read_text()
    w = windows.read_text()
    assert sha256(f.encode()).hexdigest() == FRONT_SHA256
    assert sha256(w.encode()).hexdigest() == WINDOWS_SHA256

    table_start = w.index("struct SplitPrimeTables {")
    table_end = w.index("static SPLIT_PRIME_TABLES:", table_start)
    table = w[table_start:table_end]
    table = table.replace("SplitPrimeTables", "SplitPrimePackedXTables")
    table = table.replace("U256Affine", "U256PackedXAffine")
    table = table.replace("build_u256_window", "build_packed_x_window")
    table = table.replace("assert_eq!(size_of::<U256PackedXAffine>(),64);",
                          "assert_eq!(size_of::<U256PackedXAffine>(),65);")
    table = table.replace("            + size_of::<[super::U256;3]>() + size_of::<Self>()",
                          "            + size_of::<Self>()")
    assert "assert_eq!(size_of::<U256PackedXAffine>(),65);" in table

    leaves_start = w.index("fn split_prime_two_x_affine_leaves(")
    leaves_end = w.index("// The seven even-numbered digit windows", leaves_start)
    leaves = w[leaves_start:leaves_end]
    leaves = leaves.replace("split_prime_two_x_affine_leaves", "split_prime_packed_x_affine_leaves")
    leaves = leaves.replace("multiply_u256_tau_split_prime_two_x_affine_batch",
                            "multiply_u256_tau_split_prime_packed_x_affine_batch")
    leaves = leaves.replace("SPLIT_PRIME_TWO_X_TABLES", "SPLIT_PRIME_PACKED_X_TABLES")
    static = '''static SPLIT_PRIME_PACKED_X_TABLES: LazyLock<SplitPrimePackedXTables> =
    LazyLock::new(SplitPrimePackedXTables::new);

pub(super) fn warm_split_prime_packed_x_table() -> usize {
    std::sync::LazyLock::force(&super::EXACT_RECIPROCAL_CHECK);
    std::sync::LazyLock::force(&super::FIXED_SCALAR_LATTICE);
    SPLIT_PRIME_PACKED_X_TABLES.retained_bytes
}

'''
    w = replace_once(w, "struct SplitPrimeTwoXTables {",
                     PACKED_TYPE + "\n" + table + static + leaves +
                     "struct SplitPrimeTwoXTables {")

    begin = f.index("fn benchmark_mixed640_two_x_uniform(")
    end = f.index("fn benchmark_mixed640_affine_layer_uniform(", begin)
    benchmark = f[begin:end]
    benchmark = benchmark.replace("two_x_uniform", "packed_x_uniform")
    benchmark = benchmark.replace("warm_split_prime_two_x_table", "warm_split_prime_packed_x_table")
    benchmark = benchmark.replace("multiply_u256_tau_split_prime_two_x_affine_batch",
                                  "multiply_u256_tau_split_prime_packed_x_affine_batch")
    f = f[:end] + benchmark + f[end:]
    dispatch = '''    if args.len() == 3 && args[0] == "--benchmark-split-prime-packed-x-uniform" {
        benchmark_mixed640_packed_x_uniform(
            args[2].parse().expect("uniform passes"),
            args[1].parse().expect("batch size"));
        return;
    }
'''
    needle = "    let args: Vec<String> = std::env::args().skip(1).collect();\n"
    f = replace_once(f, needle, needle + dispatch)
    front.write_text(f)
    windows.write_text(w)
    print("front_sha256=" + sha256(f.encode()).hexdigest())
    print("windows_sha256=" + sha256(w.encode()).hexdigest())


if __name__ == "__main__":
    main(Path(sys.argv[1]))
