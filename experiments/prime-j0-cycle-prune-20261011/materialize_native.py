#!/usr/bin/env python3
"""Materialize the cycle-refined cover in the direct-XYZZ-rho native evaluator."""

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
PANEL = "cycle-refined-holdout-inputs.json"
PATHS = "cycle-refined-holdout-paths.jsonl"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def once(source, old, new):
    assert source.count(old) == 1, (old[:100], source.count(old))
    return source.replace(old, new)


RUST_TEST = r'''
    #[test]
    fn cycle_refined_cover_matches_disjoint_holdout_and_binary_points() {
        let panel: serde_json::Value = serde_json::from_str(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"), "/cycle-refined-holdout-inputs.json"
        ))).unwrap();
        let scalars = panel["scalars_hex"].as_array().unwrap();
        assert_eq!(scalars.len(), 4096);
        let certified: Vec<&str> = include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"), "/cycle-refined-holdout-paths.jsonl"
        )).lines().collect();
        assert_eq!(certified.len(), scalars.len());
        let tables = &*DUAL_RHO_TABLES;
        let mut active_rho = 0usize;
        let mut rho_terms = 0usize;
        let mut additions = 0usize;
        let mut gauge_products = 0usize;
        for (index, text) in scalars.iter().enumerate() {
            let scalar = BigInt::parse_bytes(text.as_str().unwrap().as_bytes(), 16).unwrap();
            let words = super::super::scalar_words_256(&scalar).unwrap();
            let candidate = multiply_u256_tau_dual_rho0_direct_gauge_xyzz_tau(words);
            let control = multiply_u256_tau_adic_orbit_gauge_xyzz_tau(words);
            assert_eq!(candidate.0, control.0, "point {index}");
            assert_eq!(candidate.1, control.1, "representative {index}");
            assert_eq!(candidate.3, warm_format(66), "retained bytes {index}");
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
                let row = &certificate["refined"]["digits"][window];
                let expected = (
                    row[0].as_i64().unwrap() as i32,
                    row[1].as_i64().unwrap() as i32,
                    row[2].as_u64().unwrap() as usize,
                    row[3].as_u64().unwrap() as usize,
                    row[4].as_u64().unwrap() as usize,
                );
                assert_eq!((digit.0, digit.1, seed, map, unit), expected,
                           "certificate {index} window {window}");
                a = a.sub(Signed192::from_i32(digit.0)).div_exact_power_of_two(10);
                b = b.sub(Signed192::from_i32(digit.1)).div_exact_power_of_two(10);
                this_rho += usize::from(seed != 0 && map == 3);
                nonzero += usize::from(seed != 0);
            }
            assert_eq!((a.to_small_i32() as i64, b.to_small_i32() as i64),
                       (certificate["refined"]["terminal"][0].as_i64().unwrap(),
                        certificate["refined"]["terminal"][1].as_i64().unwrap()),
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
        assert_eq!((active_rho, rho_terms, additions), (1442, 1741, 49152));
        assert_eq!(gauge_products, 19535);
        println!("cycle_refined_cases={} active_rho={} rho_terms={} additions={} gauge_products={} retained_bytes={}",
                 scalars.len(), active_rho, rho_terms, additions,
                 gauge_products, warm_format(66));
    }

'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    assert not output.exists(), "output directory already exists"
    for name in ("cover-check.json", "native-atlas-check.json", "holdout-check.json"):
        assert json.loads((HERE / name).read_bytes())["status"] == "passed"
    atlas_source = HERE / "atlas-r1024-full-dual-refined.bin"
    atlas_check = json.loads((HERE / "native-atlas-check.json").read_bytes())
    assert digest(atlas_source) == atlas_check["atlas_sha256"]
    holdout = json.loads((HERE / "holdout-check.json").read_bytes())
    assert digest(HERE / "holdout-paths.jsonl") == holdout["certificate_sha256"]
    subprocess.run([sys.executable, str(DIRECT), str(output)],
                   check=True, capture_output=True)
    parent_raw = (output / "materialization.json").read_bytes()
    shutil.copyfile(atlas_source, output / ATLAS)
    shutil.copyfile(HERE / "holdout-inputs.json", output / PANEL)
    shutil.copyfile(HERE / "holdout-paths.jsonl", output / PATHS)
    window = output / WINDOW
    marker = "    #[test]\n    fn xyzz_rho_direct_matches_group_sum_across_projective_gauges() {"
    window.write_text(once(window.read_text(), marker, RUST_TEST + marker))
    parent = json.loads(parent_raw)
    receipt = {"schema": 1, "status": "materialized",
               "materializer_sha256": digest(Path(__file__)),
               "parent_materialization_sha256": sha256(parent_raw).hexdigest(),
               "parent_generated_sha256": parent["generated_sha256"],
               "generated_sha256": {name: digest(output / name)
                                    for name in (WINDOW, "src/bin/eisenstein_fixed.rs")},
               "assets_sha256": {name: digest(output / name)
                                 for name in (ATLAS, PANEL, PATHS)}}
    (output / "cycle-materialization.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
