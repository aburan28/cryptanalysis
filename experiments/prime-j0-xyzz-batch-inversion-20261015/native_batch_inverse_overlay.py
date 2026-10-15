#!/usr/bin/env python3
"""Derive a 128-scalar XYZZ batch-recovery arm from the fixed radix14 crate."""

from hashlib import sha256
from pathlib import Path
import sys

WINDOWS_SHA256 = "b45a8c0034ee9b2bae9f29fd27b39b864d7cf1e153efead92f854e85825276da"
FRONT_SHA256 = "906b58087bec06fbb12ec5d1954ecdace2af3c44b8bb78c6589954554f450015"


def once(source, old, new):
    assert source.count(old) == 1, (old[:80], source.count(old))
    return source.replace(old, new)


def main(root):
    windows = root / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    front = root / "src/bin/eisenstein_fixed.rs"
    old_windows = windows.read_text()
    old_front = front.read_text()
    assert sha256(old_windows.encode()).hexdigest() == WINDOWS_SHA256
    assert sha256(old_front.encode()).hexdigest() == FRONT_SHA256

    start = old_windows.index("pub(super) fn multiply_u256_tau_split_prime_radix(")
    end = old_windows.index("\n#[cfg(test)]\nmod split_prime_tests", start)
    body = old_windows[start:end]
    body = once(body, "pub(super) fn multiply_u256_tau_split_prime_radix(",
                "fn multiply_u256_tau_split_prime_radix_projective(")
    body = once(body,
        ") -> (String, (Signed192, Signed192), usize, usize, bool, usize, usize, SplitPrimeOpCounts) {",
        ") -> (U256XYZZ, (Signed192, Signed192), usize, usize, bool, usize, usize, SplitPrimeOpCounts) {")
    body = once(body, "let point=bucket.affine_hex_binary_inverse();", "let point=bucket;")
    body += """

pub(super) fn multiply_u256_tau_split_prime_radix(
    scalar_words: [u64; 4],
) -> (String, (Signed192, Signed192), usize, usize, bool, usize, usize, SplitPrimeOpCounts) {
    let (point,representative,adds,bytes,fallback,corner,unused,ops) =
        multiply_u256_tau_split_prime_radix_projective(scalar_words);
    (point.affine_hex_binary_inverse(),representative,adds,bytes,
     fallback,corner,unused,ops)
}

pub(super) fn multiply_u256_tau_split_prime_batch_inverse(
    scalar_words: &[[u64; 4]],
) -> Vec<String> {
    let points = scalar_words.iter().map(|&words|
        multiply_u256_tau_split_prime_radix_projective(words).0).collect::<Vec<_>>();
    if points.is_empty() { return Vec::new(); }
    let ctx = &super::HYBRID_FIELD.0;
    let one = ctx.r_mod_n;
    let mut prefix = Vec::with_capacity(points.len()+1);
    prefix.push(one);
    for point in &points {
        let factor = if point.is_identity() { one } else { point.zzz };
        prefix.push(ctx.mont_mul(prefix.last().unwrap(),&factor));
    }
    let mut inverse = super::hybrid_binary_invert(*prefix.last().unwrap(),ctx);
    let mut answers = vec![String::new();points.len()];
    for index in (0..points.len()).rev() {
        let point = points[index];
        let factor = if point.is_identity() { one } else { point.zzz };
        let inv_zzz = ctx.mont_mul(&inverse,&prefix[index]);
        inverse = ctx.mont_mul(&inverse,&factor);
        answers[index] = if point.is_identity() {
            "identity".to_owned()
        } else {
            let inv_z = ctx.mont_mul(&point.zz,&inv_zzz);
            let inv_zz = ctx.mont_sqr(&inv_z);
            let x = ctx.mont_mul(&point.x,&inv_zz);
            let y = ctx.mont_mul(&point.y,&inv_zzz);
            format!("{}:{}",hex::encode(ctx.from_montgomery(&x).to_bytes_be()),
                    hex::encode(ctx.from_montgomery(&y).to_bytes_be()))
        };
    }
    answers
}
"""
    new_windows = old_windows[:start] + body + old_windows[end:]
    test_end = new_windows.index("\n}\n\npub(super) fn warm_mixed640_pretau_table()", start)
    new_windows = new_windows[:test_end] + """

    #[test]
    fn radix_136531_batch_inverse_matches_independent_binary() {
        let panel: serde_json::Value = serde_json::from_str(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"), "/src/bin/mixed640_bench_fixture.json"
        ))).unwrap();
        let cases=panel["cases"].as_array().unwrap();
        let words = cases.iter().map(|case| {
            let scalar=BigInt::parse_bytes(
                case["scalar_hex"].as_str().unwrap().as_bytes(),16).unwrap();
            super::super::scalar_words_256(&scalar).unwrap()
        }).collect::<Vec<_>>();
        let answers=multiply_u256_tau_split_prime_batch_inverse(&words);
        assert_eq!(answers.len(),128);
        for (index,case) in cases.iter().enumerate() {
            let scalar=BigInt::parse_bytes(
                case["scalar_hex"].as_str().unwrap().as_bytes(),16).unwrap();
            assert_eq!(answers[index],case["point_hex"].as_str().unwrap());
            let reduced=&scalar % &SCALAR_LATTICE.n;
            assert_eq!(answers[index],independent_binary_point(&reduced).affine_hex());
        }
        assert_eq!(multiply_u256_tau_split_prime_batch_inverse(&[[0u64;4]]),
                   vec!["identity".to_owned()]);
    }
""" + new_windows[test_end:]

    benchmark = """
fn benchmark_mixed640_batch_inverse(repetitions: usize) {
    assert!((1..=100).contains(&repetitions));
    let panel: Value = serde_json::from_str(include_str!("mixed640_bench_fixture.json"))
        .expect("parse frozen fixture");
    let cases = panel["cases"].as_array().expect("fixture cases");
    assert_eq!(cases.len(),128);
    let inputs = cases.iter().map(|case| {
        let scalar_hex = case["scalar_hex"].as_str().expect("scalar");
        let scalar = BigInt::parse_bytes(scalar_hex.as_bytes(),16).expect("scalar hex");
        (scalar_words_256(&scalar).expect("scalar words"),
         case["point_hex"].as_str().expect("point"))
    }).collect::<Vec<_>>();
    let words = inputs.iter().map(|&(value,_)| value).collect::<Vec<_>>();
    let preparation_start = Instant::now();
    let retained_bytes = unit_orbit_windows::warm_split_prime_table();
    let preparation_ms = preparation_start.elapsed().as_secs_f64() * 1000.0;
    let mut answers = Vec::with_capacity(repetitions*inputs.len());
    let start = Instant::now();
    for _ in 0..repetitions {
        answers.extend(std::hint::black_box(
            unit_orbit_windows::multiply_u256_tau_split_prime_batch_inverse(
                std::hint::black_box(&words))));
    }
    let online_ms = start.elapsed().as_secs_f64()*1000.0;
    for (index,point) in answers.iter().enumerate() {
        assert_eq!(point,inputs[index % inputs.len()].1,"batch case {index}");
    }
    let count=answers.len();
    let last_point=answers.last().expect("nonempty");
    let last_scalar=cases.last().unwrap()["scalar_hex"].as_str().unwrap();
    println!("verified=1 online_ms={online_ms:.6} preparation_ms={preparation_ms:.6} retained_bytes={retained_bytes} count={count} batch_id=all128x{repetitions} fixture_sha256=7f4672b7b676969fe40056d0f14c6ecf45ad36109870cdf3466ebafd9e7b22d8 scalar={last_scalar} point={last_point}");
}

"""
    new_front = once(old_front, "fn main() {\n    let args: Vec<String>",
                     benchmark + "fn main() {\n    let args: Vec<String>")
    new_front = once(new_front,
        '    if args.len() == 2 && args[0] == "--benchmark-mixed640-batch" {',
        '    if args.len() == 2 && args[0] == "--benchmark-split-prime-batch-inverse" {\n'
        '        benchmark_mixed640_batch_inverse(args[1].parse().expect("batch repetitions"));\n'
        '        return;\n'
        '    }\n'
        '    if args.len() == 2 && args[0] == "--benchmark-mixed640-batch" {')
    windows.write_text(new_windows)
    front.write_text(new_front)
    print("windows_sha256=" + sha256(new_windows.encode()).hexdigest())
    print("front_sha256=" + sha256(new_front.encode()).hexdigest())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: native_batch_inverse_overlay.py CARGO_ROOT")
    main(Path(sys.argv[1]))
