#!/usr/bin/env python3
"""Join gauge-class affine sums in XYZZ, batch-invert only final outputs."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = "5ef632cd74ea7bc3ec38ce7b815481bf91cd56e8d2444621e1d010a95ea8edee"
WINDOWS_SHA256 = "3650b42e1ff33c761efd7fd73a3dac4c12a21111afe5fbc8ac73b4e0782557bd"

FINAL = r'''fn gauge_projective_affine_hex(points: &[U256XYZZ]) -> Vec<String> {
    if points.is_empty() { return Vec::new(); }
    let ctx = &super::HYBRID_FIELD.0;
    let one = ctx.r_mod_n;
    let mut prefix = Vec::with_capacity(points.len()+1);
    prefix.push(one);
    for point in points {
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

pub(super) fn multiply_u256_tau_split_prime_gauge_projective_batch(
    scalar_words: &[[u64;4]],
) -> Vec<String> {
    let groups = scalar_words.iter().map(|&words| split_prime_gauge_affine_leaves(words))
        .collect::<Vec<_>>();
    let mut class_lanes = Vec::with_capacity(3 * groups.len());
    for group in &groups {
        for row in group { class_lanes.push(row.clone()); }
    }
    let class_sums = affine_layer_reduce(class_lanes);
    let mut buckets = Vec::with_capacity(groups.len());
    for sums in class_sums.chunks_exact(3) {
        let mut bucket = U256XYZZ::identity();
        for (class, sum) in sums.iter().enumerate() {
            if let Some(mut point) = *sum {
                if class != 0 { point.x = u256_mul(point.x, U256_BETA_UNITS[class]); }
                bucket = bucket.add_mixed(point);
            }
        }
        buckets.push(bucket);
    }
    gauge_projective_affine_hex(&buckets)
}

'''


def main(root: Path) -> None:
    front = root / "src/bin/eisenstein_fixed.rs"
    windows = root / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    f, w = front.read_text(), windows.read_text()
    assert sha256(f.encode()).hexdigest() == FRONT_SHA256
    assert sha256(w.encode()).hexdigest() == WINDOWS_SHA256
    anchor = "fn affine_layer_reduce("
    assert w.count(anchor) == 1
    w = w.replace(anchor, FINAL + anchor, 1)

    begin = f.index("fn benchmark_mixed640_gauge_layer_uniform(")
    end = f.index("\nfn main()", begin)
    benchmark = f[begin:end]
    assert benchmark.count("fn benchmark_mixed640_gauge_layer_uniform(") == 1
    benchmark = benchmark.replace("gauge_layer_uniform", "gauge_projective_uniform")
    benchmark = benchmark.replace("multiply_u256_tau_split_prime_gauge_affine_batch",
                                  "multiply_u256_tau_split_prime_gauge_projective_batch")
    f = f[:end] + "\n" + benchmark + f[end:]
    dispatch = '''    if args.len() == 3 && args[0] == "--benchmark-split-prime-gauge-projective-uniform" {
        benchmark_mixed640_gauge_projective_uniform(
            args[2].parse().expect("uniform passes"),
            args[1].parse().expect("batch size"));
        return;
    }
'''
    needle = "    let args: Vec<String> = std::env::args().skip(1).collect();\n"
    assert f.count(needle) == 1
    f = f.replace(needle, needle + dispatch, 1)
    front.write_text(f)
    windows.write_text(w)
    print("front_sha256=" + sha256(f.encode()).hexdigest())
    print("windows_sha256=" + sha256(w.encode()).hexdigest())


if __name__ == "__main__":
    main(Path(sys.argv[1]))
