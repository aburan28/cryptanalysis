#!/usr/bin/env python3
"""Build an affine-by-layer batch tree from the pinned radix-14 source."""

from hashlib import sha256
from pathlib import Path
import sys

WINDOWS_SHA256 = "7272a3a818dac0fd38e028f91ba4bb75630a40849fc2375bdd0d14b20483ce62"
FRONT_SHA256 = "4df1be9f9046774f1f8720e1ba8e4c379df559c7171b636221fa9f572ac03cc8"


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

    start = old_windows.index("fn multiply_u256_tau_split_prime_radix_projective(")
    recode_start = old_windows.index("    let scalar = super::Uint(scalar_words);", start)
    recode_end = old_windows.index("\n    let mut bucket=U256XYZZ::identity();", recode_start)
    recode = old_windows[recode_start:recode_end]
    rust = r'''
#[derive(Clone, Copy)]
struct AffineLayerJob {
    lane: usize,
    position: usize,
    left: U256Affine,
    right: U256Affine,
    numerator: super::U256,
    denominator: super::U256,
}

fn split_prime_affine_leaves(scalar_words: [u64; 4])
    -> [Option<U256Affine>; SPLIT_PRIME_STEPS+1] {
__RECODE__
    let mut leaves = [None; SPLIT_PRIME_STEPS+1];
    for (window,&(seed,unit)) in choices.iter().enumerate() {
        if seed == 0 { continue; }
        let point = if window < SPLIT_PRIME_STEPS {
            tables.digit_windows[window][seed]
        } else {
            tables.terminal_pairs[seed]
        };
        leaves[window] = Some(point.unit_solinas(unit));
    }
    leaves
}

fn affine_layer_reduce(mut lanes: Vec<Vec<Option<U256Affine>>>)
    -> Vec<Option<U256Affine>> {
    let ctx = &super::HYBRID_FIELD.0;
    while lanes.iter().any(|row| row.len() > 1) {
        let mut next = Vec::with_capacity(lanes.len());
        let mut jobs = Vec::<AffineLayerJob>::new();
        for (lane,row) in lanes.iter().enumerate() {
            let mut new_row = Vec::with_capacity((row.len()+1)/2);
            for pair in row.chunks(2) {
                let position = new_row.len();
                if pair.len() == 1 {
                    new_row.push(pair[0]);
                    continue;
                }
                match (pair[0],pair[1]) {
                    (None,None) => new_row.push(None),
                    (Some(point),None) | (None,Some(point)) =>
                        new_row.push(Some(point)),
                    (Some(left),Some(right)) => {
                        let dx = u256_sub(right.x,left.x);
                        let dy = u256_sub(right.y,left.y);
                        let (numerator,denominator) = if !bool::from(dx.ct_is_zero()) {
                            (dy,dx)
                        } else if !bool::from(dy.ct_is_zero()) {
                            new_row.push(None);
                            continue;
                        } else {
                            let denominator = u256_add(left.y,left.y);
                            if bool::from(denominator.ct_is_zero()) {
                                new_row.push(None);
                                continue;
                            }
                            let xx = u256_square(left.x);
                            (u256_add(u256_add(xx,xx),xx),denominator)
                        };
                        jobs.push(AffineLayerJob {
                            lane,position,left,right,numerator,denominator,
                        });
                        new_row.push(None);
                    }
                }
            }
            next.push(new_row);
        }
        if !jobs.is_empty() {
            let mut prefix = Vec::with_capacity(jobs.len()+1);
            prefix.push(ctx.r_mod_n);
            for job in &jobs {
                prefix.push(u256_mul(*prefix.last().unwrap(),job.denominator));
            }
            let mut inverse = super::hybrid_binary_invert(*prefix.last().unwrap(),ctx);
            for (index,job) in jobs.iter().enumerate().rev() {
                let inverse_denominator = u256_mul(inverse,prefix[index]);
                inverse = u256_mul(inverse,job.denominator);
                let slope = u256_mul(job.numerator,inverse_denominator);
                let x = u256_sub(u256_sub(u256_square(slope),job.left.x),job.right.x);
                let y = u256_sub(u256_mul(slope,u256_sub(job.left.x,x)),job.left.y);
                next[job.lane][job.position] = Some(U256Affine {x,y});
            }
        }
        lanes = next;
    }
    lanes.into_iter().map(|row| row.first().copied().flatten()).collect()
}

fn affine_layer_hex(point: Option<U256Affine>) -> String {
    let Some(point) = point else { return "identity".to_owned(); };
    let ctx = &super::HYBRID_FIELD.0;
    format!("{}:{}",hex::encode(ctx.from_montgomery(&point.x).to_bytes_be()),
            hex::encode(ctx.from_montgomery(&point.y).to_bytes_be()))
}

pub(super) fn multiply_u256_tau_split_prime_affine_layer_batch(
    scalar_words: &[[u64;4]],
) -> Vec<String> {
    let lanes = scalar_words.iter().map(|&words|
        split_prime_affine_leaves(words).into_iter().collect::<Vec<_>>())
        .collect::<Vec<_>>();
    affine_layer_reduce(lanes).into_iter().map(affine_layer_hex).collect()
}
'''
    rust = rust.replace("__RECODE__", recode)
    insertion = old_windows.index("\n#[cfg(test)]\nmod split_prime_tests", start)
    new_windows = old_windows[:insertion] + "\n" + rust + old_windows[insertion:]

    test_anchor = "    #[test]\n    fn radix_136531_digit_residues_exhaustive() {"
    test = r'''    #[test]
    fn radix_136531_affine_layer_batch_matches_independent_binary() {
        let panel: serde_json::Value = serde_json::from_str(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"), "/src/bin/mixed640_bench_fixture.json"
        ))).unwrap();
        let cases = panel["cases"].as_array().unwrap();
        let words = cases.iter().map(|case| {
            let scalar = BigInt::parse_bytes(
                case["scalar_hex"].as_str().unwrap().as_bytes(),16).unwrap();
            super::super::scalar_words_256(&scalar).unwrap()
        }).collect::<Vec<_>>();
        let actual = multiply_u256_tau_split_prime_affine_layer_batch(&words);
        assert_eq!(actual.len(),128);
        for (index,case) in cases.iter().enumerate() {
            let scalar = BigInt::parse_bytes(
                case["scalar_hex"].as_str().unwrap().as_bytes(),16).unwrap();
            let reduced = &scalar % &SCALAR_LATTICE.n;
            assert_eq!(actual[index],case["point_hex"].as_str().unwrap());
            assert_eq!(actual[index],independent_binary_point(&reduced).affine_hex());
        }
        assert_eq!(multiply_u256_tau_split_prime_affine_layer_batch(&[[0u64;4]]),
                   vec!["identity".to_owned()]);
        let p = SPLIT_PRIME_TABLES.digit_windows[0][1];
        let negative = U256Affine {x:p.x,y:u256_sub(super::super::U256::ZERO,p.y)};
        assert!(affine_layer_reduce(vec![vec![Some(p),Some(negative)]])[0].is_none());
        let doubled = affine_layer_reduce(vec![vec![Some(p),Some(p)]])[0];
        assert_eq!(affine_layer_hex(doubled),
                   U256XYZZ::from_affine(p).double().affine_hex_binary_inverse());
    }

'''
    new_windows = once(new_windows,test_anchor,test+test_anchor)

    bench_start = old_front.index("fn benchmark_mixed640_batch_inverse(")
    bench_end = old_front.index("\nfn main() {",bench_start)
    bench = old_front[bench_start:bench_end]
    bench = once(bench,"fn benchmark_mixed640_batch_inverse(",
                 "fn benchmark_mixed640_affine_layer(")
    bench = once(bench,"unit_orbit_windows::multiply_u256_tau_split_prime_batch_inverse(",
                 "unit_orbit_windows::multiply_u256_tau_split_prime_affine_layer_batch(")
    bench = once(bench,"batch_size={batch_size}\");",
                 "batch_size={batch_size} scheme=affine_layer_tree\");")
    new_front = old_front[:bench_end] + "\n" + bench + old_front[bench_end:]
    new_front = once(new_front,
        "    if args.len() == 3 && args[0] == \"--benchmark-split-prime-batch-inverse-size\" {",
        "    if args.len() == 3 && args[0] == \"--benchmark-split-prime-affine-layer\" {\n"
        "        benchmark_mixed640_affine_layer(\n"
        "            args[2].parse().expect(\"batch repetitions\"),\n"
        "            args[1].parse().expect(\"batch size\"));\n"
        "        return;\n"
        "    }\n"
        "    if args.len() == 3 && args[0] == \"--benchmark-split-prime-batch-inverse-size\" {")
    windows.write_text(new_windows)
    front.write_text(new_front)
    print("windows_sha256="+sha256(new_windows.encode()).hexdigest())
    print("front_sha256="+sha256(new_front.encode()).hexdigest())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: native_affine_layer_overlay.py CARGO_ROOT")
    main(Path(sys.argv[1]))
