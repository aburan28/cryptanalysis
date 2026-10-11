#!/usr/bin/env python3
"""Materialize the phase-optimal tau-only atlas in the direct-XYZZ native evaluator."""

from hashlib import sha256
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
DIRECT = HERE.parent / "prime-j0-direct-rho-20261011/materialize.py"
WINDOW = "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
ATLAS = "atlas-r1024-full-dual-rho0.bin"
PANEL = "phase-optimal-holdout-inputs.json"
PATHS = "phase-optimal-holdout-paths.jsonl"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def once(source, old, new):
    assert source.count(old) == 1, (old[:100], source.count(old))
    return source.replace(old, new)


RUST_TEST = r'''
    #[test]
    fn phase_optimal_tau_cover_matches_disjoint_holdout_and_binary_points() {
        let panel: serde_json::Value = serde_json::from_str(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"), "/phase-optimal-holdout-inputs.json"
        ))).unwrap();
        let scalars = panel["scalars_hex"].as_array().unwrap();
        assert_eq!(scalars.len(), 4096);
        let certified: Vec<&str> = include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"), "/phase-optimal-holdout-paths.jsonl"
        )).lines().collect();
        assert_eq!(certified.len(), scalars.len());
        let tables = &*DUAL_RHO_TABLES;
        let mut active_rho = 0usize;
        let mut rho_terms = 0usize;
        let mut additions = 0usize;
        let mut gauge_products = 0usize;
        let mut retained_bytes = None;
        for (index, text) in scalars.iter().enumerate() {
            let scalar = BigInt::parse_bytes(text.as_str().unwrap().as_bytes(), 16).unwrap();
            let words = super::super::scalar_words_256(&scalar).unwrap();
            let candidate = multiply_u256_tau_dual_rho0_direct_gauge_xyzz_tau(words);
            let control = multiply_u256_tau_adic_orbit_gauge_xyzz_tau(words);
            assert_eq!(candidate.0, control.0, "point {index}");
            assert_eq!(candidate.1, control.1, "representative {index}");
            if let Some(previous) = retained_bytes {
                assert_eq!(candidate.3, previous, "retained bytes {index}");
            } else {
                retained_bytes = Some(candidate.3);
            }
            let certificate: serde_json::Value =
                serde_json::from_str(certified[index]).unwrap();
            assert_eq!(certificate["index"].as_u64().unwrap(), index as u64);
            let mut a = candidate.1.0;
            let mut b = candidate.1.1;
            let mut this_rho = 0usize;
            let mut nonzero = 0usize;
            for window in 0..12 {
                let ra = a.rem_euclid_power_of_two(10);
                let rb = b.rem_euclid_power_of_two(10);
                let (digit, seed, map, unit) = tables.full.digit_residue(ra, rb);
                let row = &certificate["phase_optimal"]["digits"][window];
                let expected = (
                    row[0].as_i64().unwrap() as i32,
                    row[1].as_i64().unwrap() as i32,
                    row[2].as_u64().unwrap() as usize,
                    row[3].as_u64().unwrap() as usize,
                    row[4].as_u64().unwrap() as usize,
                );
                assert_eq!((digit.0, digit.1, seed, map, unit), expected,
                           "certificate {index} window {window}");
                assert!(map < 3, "tau-only map {index} window {window}");
                a = a.sub(Signed192::from_i32(digit.0)).div_exact_power_of_two(10);
                b = b.sub(Signed192::from_i32(digit.1)).div_exact_power_of_two(10);
                this_rho += usize::from(seed != 0 && map == 3);
                nonzero += usize::from(seed != 0);
            }
            assert_eq!((a.to_small_i32() as i64, b.to_small_i32() as i64),
                       (certificate["phase_optimal"]["terminal"][0].as_i64().unwrap(),
                        certificate["phase_optimal"]["terminal"][1].as_i64().unwrap()),
                       "terminal {index}");
            nonzero += usize::from((a.to_small_i32(), b.to_small_i32()) != (0, 0));
            assert_eq!(candidate.2, nonzero.saturating_sub(1),
                       "term counter {index}");
            active_rho += usize::from(this_rho != 0);
            rho_terms += this_rho;
            additions += candidate.2;
            gauge_products += candidate.6;
            if index < 128 {
                let reduced = &scalar % &SCALAR_LATTICE.n;
                assert_eq!(candidate.0, independent_binary_point(&reduced).affine_hex(),
                           "independent binary {index}");
            }
        }
        assert_eq!((active_rho, rho_terms, additions), (0, 0, 49152));
        println!("phase_optimal_tau_cases={} active_rho={} rho_terms={} additions={} gauge_products={} retained_bytes={}",
                 scalars.len(), active_rho, rho_terms, additions,
                 gauge_products, retained_bytes.unwrap());
    }

'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--base-crate", type=Path,
                        help="source-pinned existing native crate for sparse checkouts")
    args = parser.parse_args()
    output = args.output.resolve()
    assert not output.exists(), "output directory already exists"
    for name in ("check.json", "native-atlas-check.json", "holdout-check.json"):
        assert json.loads((HERE / name).read_bytes())["status"] == "passed"
    atlas = HERE / "atlas-r1024-full-phase-optimal.bin"
    atlas_check = json.loads((HERE / "native-atlas-check.json").read_bytes())
    assert digest(atlas) == atlas_check["atlas_sha256"]
    holdout = json.loads((HERE / "holdout-check.json").read_bytes())
    assert digest(HERE / "holdout-paths.jsonl") == holdout["certificate_sha256"]
    if args.base_crate is None:
        subprocess.run([sys.executable, str(DIRECT), str(output)],
                       check=True, capture_output=True)
    else:
        shutil.copytree(args.base_crate.resolve(), output,
                        ignore=shutil.ignore_patterns("target"))
    parent_raw = (output / "materialization.json").read_bytes()
    shutil.copyfile(atlas, output / ATLAS)
    shutil.copyfile(HERE / "holdout-inputs.json", output / PANEL)
    shutil.copyfile(HERE / "holdout-paths.jsonl", output / PATHS)
    window = output / WINDOW
    marker = "    #[test]\n    fn xyzz_rho_direct_matches_group_sum_across_projective_gauges() {"
    source = window.read_text()
    source = once(source, "struct AlignedDualRhoAtlas([u8; 1_667_480]);",
                  "struct AlignedDualRhoAtlas([u8; 1_691_796]);")
    source = once(source,
                  "assert_eq!((radix, classes, seed_count), (1024, 174_764, 67_338));",
                  "assert_eq!((radix, classes, seed_count), (1024, 174_764, 73_417));")
    source = once(source, "assert_eq!(entries, 817_344);",
                  "assert_eq!(entries, 890_292);")
    # The source crate's compressed-cover fixture is invalid after replacing
    # that atlas; the new frozen-panel test checks the replacement instead.
    old_test = "    #[test]\n    fn cycle_compressed_cover_matches_disjoint_holdout_and_binary_points() {"
    if old_test in source:
        begin = source.index(old_test)
        end = source.index("    #[test]\n", begin + len(old_test))
        source = source[:begin] + source[end:]
    window.write_text(once(source, marker, RUST_TEST + marker))
    parent = json.loads(parent_raw)
    receipt = {"schema": 1, "status": "materialized",
               "materializer_sha256": digest(Path(__file__)),
               "base_crate_window_sha256": digest(args.base_crate.resolve() / WINDOW)
               if args.base_crate is not None else None,
               "parent_materialization_sha256": sha256(parent_raw).hexdigest(),
               "parent_generated_sha256": parent["generated_sha256"],
               "generated_sha256": {name: digest(output / name)
                                    for name in (WINDOW, "src/bin/eisenstein_fixed.rs")},
               "assets_sha256": {name: digest(output / name)
                                 for name in (ATLAS, PANEL, PATHS)}}
    (output / "phase-materialization.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
