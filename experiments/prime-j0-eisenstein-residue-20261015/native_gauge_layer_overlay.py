#!/usr/bin/env python3
"""Batch affine leaves by cube-root gauge, then rotate three class sums."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = "3dead29b00d7c5bd84851bd59b29eb477480daf05e008debaffbfb002c7b8f6b"
WINDOWS_SHA256 = "71136ada79d64d136344c8649fe59a07ceb6cbcc03f30a1e66c3f1bc4848bf5d"


def main(root: Path) -> None:
    front = root / "src/bin/eisenstein_fixed.rs"
    windows = root / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    f, w = front.read_text(), windows.read_text()
    assert sha256(f.encode()).hexdigest() == FRONT_SHA256
    assert sha256(w.encode()).hexdigest() == WINDOWS_SHA256

    begin = w.index("fn split_prime_affine_leaves(")
    end = w.index("fn affine_layer_reduce(", begin)
    leaf = w[begin:end]
    leaf = leaf.replace("split_prime_affine_leaves", "split_prime_gauge_affine_leaves")
    leaf = leaf.replace("-> [Option<U256Affine>; SPLIT_PRIME_STEPS+1]", 
                        "-> [Vec<Option<U256Affine>>; 3]")
    leaf = leaf.replace("let mut leaves = [None; SPLIT_PRIME_STEPS+1];",
                        "let mut leaves: [Vec<Option<U256Affine>>;3] = std::array::from_fn(|_| Vec::new());")
    leaf = leaf.replace("leaves[window] = Some(point.unit_solinas(unit));", '''let class = unit / 2;
        let mut signed = point;
        if unit & 1 != 0 { signed.y = u256_sub(super::U256::ZERO, signed.y); }
        leaves[class].push(Some(signed));''')
    assert "leaves[class].push(Some(signed));" in leaf

    batch = '''pub(super) fn multiply_u256_tau_split_prime_gauge_affine_batch(
    scalar_words: &[[u64;4]],
) -> Vec<String> {
    let groups = scalar_words.iter().map(|&words| split_prime_gauge_affine_leaves(words))
        .collect::<Vec<_>>();
    let mut class_lanes = Vec::with_capacity(3 * groups.len());
    for group in &groups {
        for row in group { class_lanes.push(row.clone()); }
    }
    let class_sums = affine_layer_reduce(class_lanes);
    let mut lanes = Vec::with_capacity(groups.len());
    for sums in class_sums.chunks_exact(3) {
        let mut row = Vec::with_capacity(3);
        for (class, sum) in sums.iter().enumerate() {
            row.push(sum.map(|mut point| {
                if class != 0 { point.x = u256_mul(point.x, U256_BETA_UNITS[class]); }
                point
            }));
        }
        lanes.push(row);
    }
    affine_layer_reduce(lanes).into_iter().map(affine_layer_hex).collect()
}

'''
    anchor = "fn affine_layer_reduce("
    assert w.count(anchor) == 1
    w = w.replace(anchor, leaf + batch + anchor, 1)

    begin = f.index("fn benchmark_mixed640_affine_layer_uniform(")
    end = f.index("\nfn main()", begin)
    benchmark = f[begin:end]
    assert benchmark.count("fn benchmark_mixed640_affine_layer_uniform(") == 1
    benchmark = benchmark.replace("affine_layer_uniform", "gauge_layer_uniform")
    benchmark = benchmark.replace("multiply_u256_tau_split_prime_affine_layer_batch",
                                  "multiply_u256_tau_split_prime_gauge_affine_batch")
    f = f[:end] + "\n" + benchmark + f[end:]
    dispatch = '''    if args.len() == 3 && args[0] == "--benchmark-split-prime-gauge-layer-uniform" {
        benchmark_mixed640_gauge_layer_uniform(
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
