#!/usr/bin/env python3
"""Delay order-three x rotations until after class-wise affine batch sums."""

from hashlib import sha256
from pathlib import Path
import sys

WINDOWS_SHA256 = "cecb27d0fc425425607c7867ab4616d5c0bac7889d90b4ccfefaf2181be6d3fd"
FRONT_SHA256 = "f3c3b072af59b7835b3fd79b895202e22ad27f0cb4fff537a36aab4a13bcb60f"


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

    start = old_windows.index("fn split_prime_affine_leaves(")
    recode_start = old_windows.index("    let scalar = super::Uint(scalar_words);", start)
    recode_end = old_windows.index("\n    let mut leaves = [None; SPLIT_PRIME_STEPS+1];", recode_start)
    recode = old_windows[recode_start:recode_end]
    rust = r'''
fn split_prime_signed_class_leaves(scalar_words: [u64;4])
    -> [Vec<U256Affine>;3] {
__RECODE__
    let mut classes: [Vec<U256Affine>;3] = std::array::from_fn(|_| Vec::new());
    for (window,&(seed,unit)) in choices.iter().enumerate() {
        if seed == 0 { continue; }
        let mut point = if window < SPLIT_PRIME_STEPS {
            tables.digit_windows[window][seed]
        } else {
            tables.terminal_pairs[seed]
        };
        if unit & 1 != 0 {
            point.y = u256_sub(super::U256::ZERO,point.y);
        }
        classes[unit/2].push(point);
    }
    classes
}

pub(super) fn multiply_u256_tau_split_prime_affine_unit_class_batch(
    scalar_words: &[[u64;4]],
) -> Vec<String> {
    let mut class_lanes = Vec::with_capacity(3*scalar_words.len());
    for &words in scalar_words {
        for class in split_prime_signed_class_leaves(words) {
            class_lanes.push(class.into_iter().map(Some).collect::<Vec<_>>());
        }
    }
    let class_sums = affine_layer_reduce(class_lanes);
    let scalar_lanes = (0..scalar_words.len()).map(|index| {
        (0..3).map(|class| {
            class_sums[3*index+class].map(|point|
                if class == 0 { point } else { point.unit_solinas(2*class) })
        }).collect::<Vec<_>>()
    }).collect::<Vec<_>>();
    affine_layer_reduce(scalar_lanes).into_iter().map(affine_layer_hex).collect()
}
'''.replace("__RECODE__",recode)
    insertion = old_windows.index("\n#[cfg(test)]\nmod split_prime_tests",start)
    new_windows = old_windows[:insertion] + "\n" + rust + old_windows[insertion:]

    test_anchor = "    #[test]\n    fn radix_136531_affine_layer_batch_matches_independent_binary() {"
    test = r'''    #[test]
    fn radix_136531_affine_unit_class_matches_independent_binary() {
        let panel: serde_json::Value = serde_json::from_str(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"), "/src/bin/mixed640_bench_fixture.json"
        ))).unwrap();
        let cases = panel["cases"].as_array().unwrap();
        let words = cases.iter().map(|case| {
            let scalar = BigInt::parse_bytes(
                case["scalar_hex"].as_str().unwrap().as_bytes(),16).unwrap();
            super::super::scalar_words_256(&scalar).unwrap()
        }).collect::<Vec<_>>();
        let actual = multiply_u256_tau_split_prime_affine_unit_class_batch(&words);
        let reference = multiply_u256_tau_split_prime_affine_layer_batch(&words);
        assert_eq!(actual.len(),128);
        for (index,case) in cases.iter().enumerate() {
            let scalar = BigInt::parse_bytes(
                case["scalar_hex"].as_str().unwrap().as_bytes(),16).unwrap();
            let reduced = &scalar % &SCALAR_LATTICE.n;
            assert_eq!(actual[index],reference[index]);
            assert_eq!(actual[index],case["point_hex"].as_str().unwrap());
            assert_eq!(actual[index],independent_binary_point(&reduced).affine_hex());
        }
        assert_eq!(multiply_u256_tau_split_prime_affine_unit_class_batch(&[[0u64;4]]),
                   vec!["identity".to_owned()]);
    }

'''
    new_windows = once(new_windows,test_anchor,test+test_anchor)

    bench_start = old_front.index("fn benchmark_mixed640_affine_layer(")
    bench_end = old_front.index("\nfn main() {",bench_start)
    bench = old_front[bench_start:bench_end]
    bench = once(bench,"fn benchmark_mixed640_affine_layer(",
                 "fn benchmark_mixed640_affine_unit_class(")
    bench = once(bench,"unit_orbit_windows::multiply_u256_tau_split_prime_affine_layer_batch(",
                 "unit_orbit_windows::multiply_u256_tau_split_prime_affine_unit_class_batch(")
    bench = once(bench,"scheme=affine_layer_tree\");",
                 "scheme=affine_unit_class_tree\");")
    new_front = old_front[:bench_end] + "\n" + bench + old_front[bench_end:]
    new_front = once(new_front,
        "    if args.len() == 3 && args[0] == \"--benchmark-split-prime-affine-layer\" {",
        "    if args.len() == 3 && args[0] == \"--benchmark-split-prime-affine-class\" {\n"
        "        benchmark_mixed640_affine_unit_class(\n"
        "            args[2].parse().expect(\"batch repetitions\"),\n"
        "            args[1].parse().expect(\"batch size\"));\n"
        "        return;\n"
        "    }\n"
        "    if args.len() == 3 && args[0] == \"--benchmark-split-prime-affine-layer\" {")
    windows.write_text(new_windows)
    front.write_text(new_front)
    print("windows_sha256="+sha256(new_windows.encode()).hexdigest())
    print("front_sha256="+sha256(new_front.encode()).hexdigest())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: native_affine_unit_overlay.py CARGO_ROOT")
    main(Path(sys.argv[1]))
