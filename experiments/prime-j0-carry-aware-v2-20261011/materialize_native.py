#!/usr/bin/env python3
"""Materialize the width-two carry recoder beside the direct-XYZZ-rho control."""

from hashlib import sha256
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
WINDOW = "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
MAIN = "src/bin/eisenstein_fixed.rs"
ASSET = "offers-r1024-dual-priority.bin"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def once(source, old, new):
    assert source.count(old) == 1, (old[:90], source.count(old))
    return source.replace(old, new)


RUST_TEST = r'''
    #[test]
    fn carry_width2_matches_direct_rho_on_disjoint_panel() {
        let panel: serde_json::Value = serde_json::from_str(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"), "/carry-holdout-inputs.json"
        ))).unwrap();
        let scalars = panel["scalars_hex"].as_array().unwrap();
        assert_eq!(scalars.len(), 4096);
        let certified: Vec<&str> = include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"), "/holdout-paths-width2.jsonl"
        )).lines().collect();
        assert_eq!(certified.len(), scalars.len());
        let tables = &*DUAL_RHO_TABLES;
        let mut active_rho = 0usize;
        let mut rho_terms = 0usize;
        let mut gauge_products = 0usize;
        let mut examined = 0usize;
        for (index, text) in scalars.iter().enumerate() {
            let scalar = BigInt::parse_bytes(text.as_str().unwrap().as_bytes(), 16).unwrap();
            let words = super::super::scalar_words_256(&scalar).unwrap();
            let candidate = multiply_u256_tau_dual_rho0_carry_direct_xyzz_tau(words);
            let fixed = multiply_u256_tau_dual_rho0_direct_gauge_xyzz_tau(words);
            assert_eq!(candidate.0, fixed.0, "point {index}");
            assert_eq!(candidate.1, fixed.1, "representative {index}");
            assert_eq!(candidate.3, warm_format(67), "retained bytes {index}");
            gauge_products += candidate.6;
            let (choices, nonidentity, scanned) =
                carry_recode(candidate.1, &tables.full, &tables.terminal);
            let certificate: serde_json::Value =
                serde_json::from_str(certified[index]).unwrap();
            for window in 0..12 {
                let row = &certificate["digits"][window];
                let expected = (
                    row[2].as_u64().unwrap() as usize,
                    row[3].as_u64().unwrap() as usize,
                    row[4].as_u64().unwrap() as usize,
                );
                assert_eq!(choices[window], expected,
                           "certificate {index} window {window}");
            }
            examined += scanned;
            let this_rho = choices.iter().take(12).filter(|&&(seed, map, _)|
                seed != 0 && map == 3).count();
            active_rho += usize::from(this_rho != 0);
            rho_terms += this_rho;
            assert_eq!(candidate.2, nonidentity.saturating_sub(1),
                       "term counter {index}");
            if index < 128 {
                let reduced = &scalar % &SCALAR_LATTICE.n;
                assert_eq!(candidate.0, independent_binary_point(&reduced).affine_hex(),
                           "independent binary {index}");
            }
        }
        assert_eq!((active_rho, rho_terms), (2846, 4679));
        assert_eq!(gauge_products, 20941);
        assert_eq!(examined, 113623);
        println!("carry_width2_cases={} active_rho={} rho_terms={} gauge_products={} examined_offers={}",
                 scalars.len(), active_rho, rho_terms, gauge_products, examined);
    }

'''


def patch_window(source):
    carry_source = (HERE / "native_carry.rs").read_text()
    source = once(source, "struct Tau2TerminalResidualAtlas {",
                  carry_source + "\nstruct Tau2TerminalResidualAtlas {")
    begin = source.index("fn multiply_u256_tau_dual_rho0_with(")
    end = source.index("pub(super) fn multiply_u256_tau_dual_rho0_folded_gauge_xyzz_tau(", begin)
    control = source[begin:end]
    candidate = once(control, "fn multiply_u256_tau_dual_rho0_with(",
                     "fn multiply_u256_tau_dual_rho0_carry_with(")
    start = candidate.index("    let (mut a, mut b) = representative;")
    stop = candidate.index("    let mut buckets =", start)
    candidate = candidate[:start] + \
        "    let (choices, nonidentity, _examined) = carry_recode(\n" \
        "        representative, &tables.full, &tables.terminal);\n\n" + \
        candidate[stop:]
    candidate = once(candidate,
                     "tables.retained_bytes + SOLINAS_UNIT_CONSTANT_BYTES,",
                     "tables.retained_bytes + SOLINAS_UNIT_CONSTANT_BYTES\n"
                     "         + size_of::<AlignedCarryOfferIndex>(),")
    candidate += '''pub(super) fn multiply_u256_tau_dual_rho0_carry_direct_xyzz_tau(
    scalar_words: [u64; 4],
) -> (String, (Signed192, Signed192), usize, usize, bool, usize, usize) {
    multiply_u256_tau_dual_rho0_carry_with(scalar_words, true)
}

'''
    source = source[:end] + candidate + source[end:]
    source = once(source, "    if format == 65 || format == 66 {",
                  "    if format == 67 {\n"
                  "        std::sync::LazyLock::force(&CARRY_OFFERS);\n"
                  "        return warm_format(66) + size_of::<AlignedCarryOfferIndex>();\n"
                  "    }\n"
                  "    if format == 65 || format == 66 {")
    marker = "    #[test]\n    fn xyzz_rho_direct_matches_group_sum_across_projective_gauges() {"
    source = once(source, marker, RUST_TEST + marker)
    return source


def patch_main(source):
    for old, new in ((("123..=166"), ("123..=167")),
                     (("124..=166"), ("124..=167")),
                     (("125..=166"), ("125..=167"))):
        source = once(source, old, new)
    source = once(source, "    let actual = if unit_orbit_format == 166 {",
                  "    let actual = if unit_orbit_format == 167 {\n"
                  "        unit_orbit_windows::multiply_u256_tau_dual_rho0_carry_direct_xyzz_tau(\n"
                  "            scalar_words.expect(\"carry rho requires unsigned 256-bit scalar\")\n"
                  "        ).0\n"
                  "    } else if unit_orbit_format == 166 {")
    source = once(source, "    let mode = if unit_orbit_format == 166 {",
                  "    let mode = if unit_orbit_format == 167 {\n"
                  "        \"unit_orbit_u256_tau_dual_rho0_carry_direct_xyzz_tau_fixed\"\n"
                  "    } else if unit_orbit_format == 166 {")
    control = '            || args[0].starts_with("--check-scalar-unit-orbit-u256-tau-dual-rho0-direct-gauge-xyzz-tau")'
    source = once(source, control,
                  '            || args[0].starts_with("--check-scalar-unit-orbit-u256-tau-dual-rho0-carry-direct-xyzz-tau")\n'
                  '            || args[0].starts_with("--benchmark-scalar-unit-orbit-u256-tau-dual-rho0-carry-direct-xyzz-tau")\n'
                  + control)
    control = '            || args[0] == "--check-scalar-unit-orbit-u256-tau-dual-rho0-direct-gauge-xyzz-tau-fixed-case"'
    source = once(source, control,
                  '            || args[0] == "--check-scalar-unit-orbit-u256-tau-dual-rho0-carry-direct-xyzz-tau-fixed-case"\n'
                  '            || args[0] == "--benchmark-scalar-unit-orbit-u256-tau-dual-rho0-carry-direct-xyzz-tau-fixed-case"\n'
                  + control)
    control = '        let format = if args[0].contains("unit-orbit-u256-tau-dual-rho0-direct-gauge-xyzz-tau-fixed-fixture") {'
    source = once(source, control,
                  '        let format = if args[0].contains("unit-orbit-u256-tau-dual-rho0-carry-direct-xyzz-tau-fixed-fixture") {\n'
                  '            167\n'
                  '        } else if args[0].contains("unit-orbit-u256-tau-dual-rho0-direct-gauge-xyzz-tau-fixed-fixture") {')
    control = '            if args[0].contains("unit-orbit-u256-tau-dual-rho0-direct-gauge-xyzz-tau") {'
    source = once(source, control,
                  '            if args[0].contains("unit-orbit-u256-tau-dual-rho0-carry-direct-xyzz-tau") {\n'
                  '                167\n'
                  '            } else if args[0].contains("unit-orbit-u256-tau-dual-rho0-direct-gauge-xyzz-tau") {')
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--direct-materializer", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert not output.exists(), "output directory already exists"
    index_check = json.loads((HERE / "offer-index-check.json").read_bytes())
    holdout_check = json.loads((HERE / "holdout-verify.json").read_bytes())
    assert index_check["status"] == holdout_check["status"] == "passed"
    assert index_check["offer_index_sha256"] == digest(HERE / ASSET)
    panel = HERE / "holdout-inputs.json"
    subprocess.run([sys.executable, str(args.direct_materializer.resolve()),
                    str(output)], check=True, capture_output=True)
    parent = json.loads((output / "materialization.json").read_bytes())
    shutil.copyfile(panel, output / "carry-holdout-inputs.json")
    shutil.copyfile(HERE / ASSET, output / ASSET)
    shutil.copyfile(HERE / "holdout-paths-width2.jsonl",
                    output / "holdout-paths-width2.jsonl")
    window = output / WINDOW
    window.write_text(patch_window(window.read_text()))
    main_path = output / MAIN
    main_path.write_text(patch_main(main_path.read_text()))
    receipt = {"schema": 1, "status": "materialized",
               "materializer_sha256": digest(Path(__file__)),
               "carry_source_sha256": digest(HERE / "native_carry.rs"),
               "parent_materialization_sha256": sha256(json.dumps(
                   parent, sort_keys=True).encode()).hexdigest(),
               "generated_sha256": {name: digest(output / name)
                                    for name in (WINDOW, MAIN)},
               "assets_sha256": {name: digest(output / name)
                                 for name in (ASSET, "dual-rho0-fresh-inputs.json",
                                              "carry-holdout-inputs.json",
                                              "holdout-paths-width2.jsonl")}}
    (output / "carry-materialization.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
