#!/usr/bin/env python3
"""Replace selected x rotations by a two-x affine table for radix-14 batches."""

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
    recode = once(recode, "let tables = &*SPLIT_PRIME_TABLES;",
                  "let tables = &*SPLIT_PRIME_TWO_X_TABLES;")
    rust = r'''
struct SplitPrimeTwoXTables {
    digit_pairs: Box<[(i16,i16)]>,
    digit_codes: Box<[(u16,u8)]>,
    digit_windows: Vec<Box<[U256TwoXAffine]>>,
    terminal_pairs: Box<[U256TwoXAffine]>,
    terminal_codes: Box<[(u16,u8)]>,
    retained_bytes: usize,
}

impl SplitPrimeTwoXTables {
    fn new() -> Self {
        // Build the same exact seed sets and window bases, convert them, and
        // release the temporary ordinary affine rows before returning.
        let ordinary = SplitPrimeTables::new();
        let SplitPrimeTables {
            digit_pairs,digit_codes,digit_windows,terminal_pairs,terminal_codes,
            retained_bytes: _,
        } = ordinary;
        let digit_windows = digit_windows.into_iter().map(|row| {
            row.iter().copied().map(U256TwoXAffine::from_affine)
               .collect::<Vec<_>>().into_boxed_slice()
        }).collect::<Vec<_>>();
        let terminal_pairs = terminal_pairs.iter().copied()
            .map(U256TwoXAffine::from_affine).collect::<Vec<_>>().into_boxed_slice();
        let entries = digit_windows.iter().map(|row| row.len()).sum::<usize>();
        assert_eq!(entries,14*22756);
        assert_eq!(terminal_pairs.len(),30071);
        assert_eq!(size_of::<U256TwoXAffine>(),96);
        let retained_bytes = (entries+terminal_pairs.len())*size_of::<U256TwoXAffine>()
            + digit_pairs.len()*size_of::<(i16,i16)>()
            + (digit_codes.len()+terminal_codes.len())*size_of::<(u16,u8)>()
            + size_of::<[super::U256;3]>() + size_of::<Self>()
            + digit_windows.capacity()*size_of::<Box<[U256TwoXAffine]>>();
        Self { digit_pairs,digit_codes,digit_windows,terminal_pairs,
               terminal_codes,retained_bytes }
    }
}

static SPLIT_PRIME_TWO_X_TABLES: LazyLock<SplitPrimeTwoXTables> =
    LazyLock::new(SplitPrimeTwoXTables::new);

pub(super) fn warm_split_prime_two_x_table() -> usize {
    std::sync::LazyLock::force(&super::EXACT_RECIPROCAL_CHECK);
    std::sync::LazyLock::force(&super::FIXED_SCALAR_LATTICE);
    SPLIT_PRIME_TWO_X_TABLES.retained_bytes
}

fn split_prime_two_x_affine_leaves(scalar_words: [u64;4])
    -> [Option<U256Affine>; SPLIT_PRIME_STEPS+1] {
__RECODE__
    let mut leaves = [None;SPLIT_PRIME_STEPS+1];
    for (window,&(seed,unit)) in choices.iter().enumerate() {
        if seed == 0 { continue; }
        let point = if window < SPLIT_PRIME_STEPS {
            tables.digit_windows[window][seed]
        } else {
            tables.terminal_pairs[seed]
        };
        leaves[window] = Some(point.unit(unit));
    }
    leaves
}

pub(super) fn multiply_u256_tau_split_prime_two_x_affine_batch(
    scalar_words: &[[u64;4]],
) -> Vec<String> {
    let lanes = scalar_words.iter().map(|&words|
        split_prime_two_x_affine_leaves(words).into_iter().collect::<Vec<_>>())
        .collect::<Vec<_>>();
    affine_layer_reduce(lanes).into_iter().map(affine_layer_hex).collect()
}
'''.replace("__RECODE__",recode)
    insertion = old_windows.index("\n#[cfg(test)]\nmod split_prime_tests",start)
    new_windows = old_windows[:insertion] + "\n" + rust + old_windows[insertion:]
    new_windows = once(new_windows, "tables: &SplitPrimeTables,\n) -> (Signed192, Signed192, usize, usize) {",
                       "digit_pairs: &[(i16,i16)],\n) -> (Signed192, Signed192, usize, usize) {")
    new_windows = once(new_windows, "let (raw_da, raw_db) = tables.digit_pairs[index];",
                       "let (raw_da, raw_db) = digit_pairs[index];")
    assert new_windows.count("split_prime_unit_step(a,b,tables)") == 3
    new_windows = new_windows.replace("split_prime_unit_step(a,b,tables)",
                                      "split_prime_unit_step(a,b,&tables.digit_pairs)")

    test_anchor = "    #[test]\n    fn radix_136531_affine_layer_batch_matches_independent_binary() {"
    test = r'''    #[test]
    fn radix_136531_two_x_affine_batch_matches_independent_binary() {
        let panel: serde_json::Value = serde_json::from_str(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"), "/src/bin/mixed640_bench_fixture.json"
        ))).unwrap();
        let cases = panel["cases"].as_array().unwrap();
        let words = cases.iter().map(|case| {
            let scalar = BigInt::parse_bytes(
                case["scalar_hex"].as_str().unwrap().as_bytes(),16).unwrap();
            super::super::scalar_words_256(&scalar).unwrap()
        }).collect::<Vec<_>>();
        let actual = multiply_u256_tau_split_prime_two_x_affine_batch(&words);
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
        assert_eq!(multiply_u256_tau_split_prime_two_x_affine_batch(&[[0u64;4]]),
                   vec!["identity".to_owned()]);
    }

'''
    new_windows = once(new_windows,test_anchor,test+test_anchor)

    bench_start = old_front.index("fn benchmark_mixed640_affine_layer(")
    bench_end = old_front.index("\nfn main() {",bench_start)
    bench = old_front[bench_start:bench_end]
    bench = once(bench,"fn benchmark_mixed640_affine_layer(",
                 "fn benchmark_mixed640_two_x_affine(")
    bench = once(bench,"unit_orbit_windows::multiply_u256_tau_split_prime_affine_layer_batch(",
                 "unit_orbit_windows::multiply_u256_tau_split_prime_two_x_affine_batch(")
    bench = once(bench,"unit_orbit_windows::warm_split_prime_table()",
                 "unit_orbit_windows::warm_split_prime_two_x_table()")
    bench = once(bench,"scheme=affine_layer_tree\");",
                 "scheme=affine_two_x_tree\");")
    new_front = old_front[:bench_end] + "\n" + bench + old_front[bench_end:]
    new_front = once(new_front,
        "    if args.len() == 3 && args[0] == \"--benchmark-split-prime-affine-layer\" {",
        "    if args.len() == 3 && args[0] == \"--benchmark-split-prime-affine-two-x\" {\n"
        "        benchmark_mixed640_two_x_affine(\n"
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
        raise SystemExit("usage: native_two_x_overlay.py CARGO_ROOT")
    main(Path(sys.argv[1]))
