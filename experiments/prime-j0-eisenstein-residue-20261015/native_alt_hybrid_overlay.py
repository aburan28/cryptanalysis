#!/usr/bin/env python3
"""Use two or three batched affine layers before XYZZ final joins."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = "2f4f14749e4c655a7dfd56d09eae077f2142c802377ab0f5f0f52b35d7272be0"
WINDOWS_SHA256 = "ee2297e049142e7447a1eac01da947095dba145f463657506b6a90adb9f3864d"

HYBRID_CODE = r'''
fn alt_hybrid_batch_hex(points: Vec<U256XYZZ>) -> Vec<String> {
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

pub(super) fn multiply_u256_tau_alt_hybrid_batch<const LEVELS: usize>(
    scalar_words: &[[u64;4]],
) -> Vec<String> {
    assert!(LEVELS == 2 || LEVELS == 3);
    let lanes = scalar_words.iter().map(|&words|
        alt_split_prime_two_x_affine_leaves(words).into_iter().collect::<Vec<_>>())
        .collect::<Vec<_>>();
    let partial = alt_hybrid_affine_prefix(lanes, LEVELS);
    let points = partial.into_iter().map(|row|
        mixed640_single_tree(row.into_iter().flatten()
            .map(Mixed640TreeNode::Affine).collect::<Vec<_>>()))
        .collect::<Vec<_>>();
    alt_hybrid_batch_hex(points)
}
'''


def main(root: Path) -> None:
    front = root / "src/bin/eisenstein_fixed.rs"
    windows = root / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    f, w = front.read_text(), windows.read_text()
    assert sha256(f.encode()).hexdigest() == FRONT_SHA256
    assert sha256(w.encode()).hexdigest() == WINDOWS_SHA256

    start = w.index("fn affine_layer_reduce(")
    end = w.index("\nfn affine_layer_hex(", start)
    prefix = w[start:end]
    assert prefix.count("while lanes.iter().any(|row| row.len() > 1) {") == 1
    prefix = prefix.replace("fn affine_layer_reduce(", "fn alt_hybrid_affine_prefix(")
    prefix = prefix.replace("mut lanes: Vec<Vec<Option<U256Affine>>>)\n    -> Vec<Option<U256Affine>> {",
                            "mut lanes: Vec<Vec<Option<U256Affine>>>, levels: usize)\n"
                            "    -> Vec<Vec<Option<U256Affine>>> {")
    prefix = prefix.replace("while lanes.iter().any(|row| row.len() > 1) {",
                            "for _ in 0..levels {")
    prefix = prefix.replace("lanes.into_iter().map(|row| row.first().copied().flatten()).collect()",
                            "lanes")
    assert "fn alt_hybrid_affine_prefix" in prefix

    insert = w.index("\n#[cfg(test)]\nmod split_prime_tests")
    w = w[:insert] + "\n" + prefix + "\n" + HYBRID_CODE + w[insert:]
    windows.write_text(w)

    start = f.index("fn benchmark_mixed640_alt_radix_uniform(")
    end = f.index("fn benchmark_mixed640_affine_layer_uniform(", start)
    benchmark = f[start:end]
    for levels in (2, 3):
        new = benchmark.replace("alt_radix_uniform", f"alt_hybrid{levels}_uniform")
        new = new.replace("multiply_u256_tau_alt_split_prime_two_x_affine_batch",
                          f"multiply_u256_tau_alt_hybrid_batch::<{levels}>")
        f = f[:end] + new + f[end:]
        end += len(new)
    dispatch = ""
    for levels in (2, 3):
        dispatch += f'''    if args.len() == 3 && args[0] == "--benchmark-alt-hybrid{levels}-uniform" {{
        benchmark_mixed640_alt_hybrid{levels}_uniform(
            args[2].parse().expect("uniform passes"),
            args[1].parse().expect("batch size"));
        return;
    }}
'''
    needle = "    let args: Vec<String> = std::env::args().skip(1).collect();\n"
    assert f.count(needle) == 1
    front.write_text(f.replace(needle, needle + dispatch, 1))
    print("front_sha256=" + sha256(front.read_bytes()).hexdigest())
    print("windows_sha256=" + sha256(windows.read_bytes()).hexdigest())


if __name__ == "__main__":
    main(Path(sys.argv[1]))
