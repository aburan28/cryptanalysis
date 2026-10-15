#!/usr/bin/env python3
"""Prototype radix-14 sums entirely in the balanced Eisenstein pair field."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = "3dead29b00d7c5bd84851bd59b29eb477480daf05e008debaffbfb002c7b8f6b"
WINDOWS_SHA256 = "71136ada79d64d136344c8649fe59a07ceb6cbcc03f30a1e66c3f1bc4848bf5d"

PAIR_CODE = r'''
// Each retained point has four signed 128-bit coefficients: balanced x and y
// in the 2^128 Montgomery pair field. Unit rotation is a coordinate change.
struct SplitPrimePairTables {
    digit_pairs: Box<[(i16,i16)]>,
    digit_codes: Box<[(u16,u8)]>,
    digit_windows: Vec<Box<[super::CompactPairPoint]>>,
    terminal_pairs: Box<[super::CompactPairPoint]>,
    terminal_codes: Box<[(u16,u8)]>,
    retained_bytes: usize,
}

fn split_prime_pair_from_mont(value: super::U256) -> super::Pair {
    let ctx = &super::HYBRID_FIELD.0;
    let p = &super::DECODE_CONSTANTS.0;
    let value = num_bigint::BigInt::from(ctx.from_montgomery(&value).to_biguint());
    let radix = num_bigint::BigInt::from(1u8) << 128usize;
    let x = (value * radix) % p;
    let a = num_bigint::BigInt::from(super::PI_A);
    let b = -num_bigint::BigInt::from(super::PI_B_MAG);
    let q1 = super::round_div((&a - &b) * &x, p.clone());
    let q2 = super::round_div(-&b * &x, p.clone());
    let pa = &x - &q1 * &a + &q2 * &b;
    let pb = -&q1 * &b - &q2 * (&a - &b);
    let pair = super::Pair {
        a: super::Signed::from_decimal(&pa.to_string()),
        b: super::Signed::from_decimal(&pb.to_string()),
    };
    debug_assert_eq!(super::hybrid_pair_mont(pair).0, value_to_mont_for_check(&x, ctx).0);
    pair
}

fn value_to_mont_for_check(
    x: &num_bigint::BigInt,
    ctx: &super::MontgomeryContext<4>,
) -> super::U256 {
    // x already represents value * 2^128. Divide by that radix through the
    // known field inverse before comparing the conventional Montgomery image.
    let p = &super::DECODE_CONSTANTS.0;
    let decoded = ((x * &super::DECODE_CONSTANTS.2) % p + p) % p;
    ctx.to_montgomery(&super::U256::from_biguint(&decoded.to_biguint().unwrap()))
}

fn split_prime_compact_pair(point: U256Affine) -> super::CompactPairPoint {
    let affine = super::Jacobian {
        x: split_prime_pair_from_mont(point.x),
        y: split_prime_pair_from_mont(point.y),
        z: super::Pair::one(),
    };
    super::CompactPairPoint::from_affine(affine)
}

impl SplitPrimePairTables {
    fn new() -> Self {
        let ordinary = SplitPrimeTables::new();
        let SplitPrimeTables {
            digit_pairs, digit_codes, digit_windows, terminal_pairs,
            terminal_codes, retained_bytes: _,
        } = ordinary;
        let digit_windows = digit_windows.into_iter().map(|row| row.iter().copied()
            .map(split_prime_compact_pair).collect::<Vec<_>>().into_boxed_slice())
            .collect::<Vec<_>>();
        let terminal_pairs = terminal_pairs.iter().copied()
            .map(split_prime_compact_pair).collect::<Vec<_>>().into_boxed_slice();
        let retained_bytes = digit_windows.iter().map(|row| row.len()
            * size_of::<super::CompactPairPoint>()).sum::<usize>()
            + terminal_pairs.len()*size_of::<super::CompactPairPoint>()
            + digit_pairs.len()*size_of::<(i16,i16)>()
            + (digit_codes.len()+terminal_codes.len())*size_of::<(u16,u8)>()
            + size_of::<[super::U256;3]>() + size_of::<Self>()
            + digit_windows.capacity()*size_of::<Box<[super::CompactPairPoint]>>();
        assert!(retained_bytes < 32*1024*1024);
        Self { digit_pairs, digit_codes, digit_windows, terminal_pairs,
               terminal_codes, retained_bytes }
    }
}

static SPLIT_PRIME_PAIR_TABLES: LazyLock<SplitPrimePairTables> =
    LazyLock::new(SplitPrimePairTables::new);

pub(super) fn warm_split_prime_pair_table() -> usize {
    std::sync::LazyLock::force(&super::EXACT_RECIPROCAL_CHECK);
    std::sync::LazyLock::force(&super::FIXED_SCALAR_LATTICE);
    SPLIT_PRIME_PAIR_TABLES.retained_bytes
}

fn split_prime_pair_unit(point: super::CompactPairPoint, code: usize) -> super::Jacobian {
    let mut point = point.into_affine();
    for _ in 0..code/2 { point = point.omega(); }
    if code & 1 == 1 { point = point.neg(); }
    point
}

pub(super) fn multiply_u256_tau_split_prime_pair_batch(
    scalar_words: &[[u64;4]],
) -> Vec<String> {
    let points = scalar_words.iter().map(|&words| {
        split_prime_pair_leaves(words).into_iter().flatten().fold(
            super::Jacobian::identity(), |acc, point| acc.add_mixed(point))
    }).collect::<Vec<_>>();
    let active = points.iter().enumerate().filter(|(_, point)| !point.is_identity())
        .map(|(index, point)| (index, *point)).collect::<Vec<_>>();
    let affine = super::batch_to_affine(
        &active.iter().map(|(_, point)| *point).collect::<Vec<_>>());
    let ctx = &super::HYBRID_FIELD.0;
    let mut answers = vec!["identity".to_owned(); points.len()];
    for ((index, _), point) in active.into_iter().zip(affine) {
        let x = super::hybrid_pair_mont(point.x);
        let y = super::hybrid_pair_mont(point.y);
        answers[index] = format!("{}:{}",
            hex::encode(ctx.from_montgomery(&x).to_bytes_be()),
            hex::encode(ctx.from_montgomery(&y).to_bytes_be()));
    }
    answers
}
'''


def main(root: Path) -> None:
    front = root / "src/bin/eisenstein_fixed.rs"
    windows = root / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    f, w = front.read_text(), windows.read_text()
    assert sha256(f.encode()).hexdigest() == FRONT_SHA256
    assert sha256(w.encode()).hexdigest() == WINDOWS_SHA256
    begin = w.index("fn split_prime_affine_leaves(")
    end = w.index("\nfn affine_layer_reduce(", begin)
    recoder = w[begin:end]
    recoder = recoder.replace("split_prime_affine_leaves", "split_prime_pair_leaves")
    recoder = recoder.replace("Option<U256Affine>", "Option<super::Jacobian>")
    recoder = recoder.replace("SPLIT_PRIME_TABLES", "SPLIT_PRIME_PAIR_TABLES")
    recoder = recoder.replace("Some(point.unit_solinas(unit))", "Some(split_prime_pair_unit(point, unit))")
    assert "Some(split_prime_pair_unit(point, unit))" in recoder
    insert = w.index("\n#[cfg(test)]\nmod split_prime_tests")
    w = w[:insert] + "\n" + PAIR_CODE + "\n" + recoder + w[insert:]
    windows.write_text(w)
    begin = f.index("fn benchmark_mixed640_affine_layer_uniform(")
    end = f.index("\nfn main()", begin)
    benchmark = f[begin:end]
    assert benchmark.count("fn benchmark_mixed640_affine_layer_uniform(") == 1
    benchmark = benchmark.replace("affine_layer_uniform", "pair_accumulation_uniform")
    benchmark = benchmark.replace("warm_split_prime_table", "warm_split_prime_pair_table")
    benchmark = benchmark.replace("multiply_u256_tau_split_prime_affine_layer_batch",
                                  "multiply_u256_tau_split_prime_pair_batch")
    f = f[:end] + "\n" + benchmark + f[end:]
    dispatch = '''    if args.len() == 3 && args[0] == "--benchmark-split-prime-pair-accumulation-uniform" {
        benchmark_mixed640_pair_accumulation_uniform(
            args[2].parse().expect("uniform passes"),
            args[1].parse().expect("batch size"));
        return;
    }
'''
    needle = "    let args: Vec<String> = std::env::args().skip(1).collect();\n"
    assert f.count(needle) == 1
    front.write_text(f.replace(needle, needle + dispatch, 1))
    print("front_sha256=" + sha256(front.read_bytes()).hexdigest())
    print("windows_sha256=" + sha256(windows.read_bytes()).hexdigest())


if __name__ == "__main__":
    main(Path(sys.argv[1]))
