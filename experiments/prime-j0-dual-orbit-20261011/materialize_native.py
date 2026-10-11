#!/usr/bin/env python3
"""Materialize the folded rho0 path beside the pinned fused control."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
FUSED = HERE.parent / "prime-j0-fused-orbit-20261011"
SPEC = importlib.util.spec_from_file_location("dual_rho_fused_native",
                                              FUSED / "materialize_native.py")
fused = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fused)
MAIN_SOURCE = fused.MAIN_SOURCE
WINDOW_SOURCE = fused.WINDOW_SOURCE
ATLAS = "atlas-r1024-full-dual-rho0.bin"
PANEL = "dual-rho0-fresh-inputs.json"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def once(source, old, new):
    assert source.count(old) == 1, (old[:110], source.count(old))
    return source.replace(old, new)


def atlas_source():
    source = fused.RUST_ATLAS
    for old, new in (
        ("AlignedFusedOrbitAtlas", "AlignedDualRhoAtlas"),
        ("FUSED_ORBIT_FULL_ATLAS", "DUAL_RHO_FULL_ATLAS"),
        ("FusedOrbitFullAtlas", "DualRhoFullAtlas"),
        ("1_730_332", "1_667_480"),
        ("atlas-r1024-full-fused-orbit.bin", ATLAS),
        ('b"FO18"', 'b"DR20"'),
        ("83_051", "67_338"),
        ("let (seed_id, exponent, canonical_unit) =", "let (seed_id, map_id, canonical_unit) ="),
        ("exponent <= 2", "map_id <= 3"),
        ("(digit, seed_id, exponent, unit_code)", "(digit, seed_id, map_id, unit_code)"),
    ):
        assert old in source, old
        source = source.replace(old, new)
    return source


def table_source(source):
    start = source.index("struct FusedOrbitTables {")
    end = source.index("struct TauBucketAtlas {", start)
    table = source[start:end]
    for old, new in (
        ("FusedOrbitTables", "DualRhoTables"),
        ("FusedOrbitFullAtlas", "DualRhoFullAtlas"),
        ("FUSED_ORBIT_FULL_ATLAS", "DUAL_RHO_FULL_ATLAS"),
        ("AlignedFusedOrbitAtlas", "AlignedDualRhoAtlas"),
        ("FUSED_ORBIT_TABLES", "DUAL_RHO_TABLES"),
        ("1_005_900", "817_344"),
    ):
        assert old in table, old
        table = table.replace(old, new)
    return table


def function_source(source):
    start = source.index("pub(super) fn multiply_u256_tau_fused_orbit_gauge_xyzz_tau(")
    end = source.index("\nfn multiply_u256_sector_with", start)
    function = source[start:end]
    for old, new in (
        ("multiply_u256_tau_fused_orbit_gauge_xyzz_tau", "multiply_u256_tau_dual_rho0_folded_gauge_xyzz_tau"),
        ("FusedOrbitTables", "DualRhoTables"),
        ("FUSED_ORBIT_TABLES", "DUAL_RHO_TABLES"),
        ("[U256XYZZ::identity(); 3]", "[U256XYZZ::identity(); 4]"),
        ("for exponent in 0..3 {", "for exponent in 0..4 {"),
        ("assert!(gauge_products <= 6);", "assert!(gauge_products <= 8);"),
    ):
        function = once(function, old, new)
    function = once(function,
        "let point = buckets[0].add_xyzz(\n"
        "        buckets[1].add_xyzz(buckets[2].tau()).tau()\n"
        "    ).affine_hex_binary_inverse();",
        "let rho = buckets[3];\n"
        "    let zero = buckets[0].add_xyzz(rho);\n"
        "    let one = buckets[1].add_xyzz(rho);\n"
        "    let point = zero.add_xyzz(\n"
        "        one.add_xyzz(buckets[2].tau()).tau()\n"
        "    ).affine_hex_binary_inverse();")
    return function


RUST_TEST = r'''
    #[test]
    fn dual_rho0_folded_matches_fresh_panel_and_controls() {
        let panel: serde_json::Value = serde_json::from_str(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"), "/dual-rho0-fresh-inputs.json"
        ))).unwrap();
        let scalars = panel["scalars_hex"].as_array().unwrap();
        assert_eq!(scalars.len(), 4096);
        let mut additions = 0usize;
        let mut rotations = 0usize;
        let mut fused_additions = 0usize;
        let mut fused_rotations = 0usize;
        for (index, text) in scalars.iter().enumerate() {
            let scalar = BigInt::parse_bytes(text.as_str().unwrap().as_bytes(), 16).unwrap();
            let words = super::super::scalar_words_256(&scalar).unwrap();
            let candidate = multiply_u256_tau_dual_rho0_folded_gauge_xyzz_tau(words);
            let direct = multiply_u256_tau_adic_orbit_gauge_xyzz_tau(words);
            let fused = multiply_u256_tau_fused_orbit_gauge_xyzz_tau(words);
            assert_eq!(candidate.0, direct.0, "direct point {index}");
            assert_eq!(candidate.0, fused.0, "fused point {index}");
            assert_eq!(candidate.1, direct.1, "representative {index}");
            assert_eq!((candidate.4, candidate.5), (direct.4, direct.5),
                       "representative metadata {index}");
            assert_eq!(candidate.3, warm_format(65));
            assert!(candidate.2 <= 12 && candidate.6 <= 8, "bounds {index}");
            additions += candidate.2;
            rotations += candidate.6;
            fused_additions += fused.2;
            fused_rotations += fused.6;
            if index < 128 {
                let reduced = &scalar % &SCALAR_LATTICE.n;
                assert_eq!(candidate.0, independent_binary_point(&reduced).affine_hex(),
                           "independent binary {index}");
            }
        }
        assert_eq!(additions, 49_152);
        assert_eq!(fused_additions, 49_152);
        println!("dual_rho0_folded_cases={} retained_bytes={} additions={} gauge_products={} fused_additions={} fused_gauge_products={}",
                 scalars.len(), warm_format(65), additions, rotations,
                 fused_additions, fused_rotations);
    }

'''


def patch_main(source):
    for old, new in (
        ("(123..=164)", "(123..=165)"),
        ("(124..=164)", "(124..=165)"),
        ("(125..=164)", "(125..=165)"),
    ):
        source = once(source, old, new)
    source = once(source, "let actual = if unit_orbit_format == 164 {",
        "let actual = if unit_orbit_format == 165 {\n"
        "        unit_orbit_windows::multiply_u256_tau_dual_rho0_folded_gauge_xyzz_tau(\n"
        "            scalar_words.expect(\"dual rho0 requires unsigned 256-bit scalar\")\n"
        "        ).0\n"
        "    } else if unit_orbit_format == 164 {")
    source = once(source, "let mode = if unit_orbit_format == 164 {",
        "let mode = if unit_orbit_format == 165 {\n"
        "        \"unit_orbit_u256_tau_dual_rho0_folded_gauge_xyzz_tau_fixed\"\n"
        "    } else if unit_orbit_format == 164 {")
    old = '            || args[0].starts_with("--check-scalar-unit-orbit-u256-tau-fused-orbit-gauge-xyzz-tau")'
    source = once(source, old,
        '            || args[0].starts_with("--check-scalar-unit-orbit-u256-tau-dual-rho0-folded-gauge-xyzz-tau")\n'
        '            || args[0].starts_with("--benchmark-scalar-unit-orbit-u256-tau-dual-rho0-folded-gauge-xyzz-tau")\n' + old)
    old = 'let format = if args[0].contains("unit-orbit-u256-tau-fused-orbit-gauge-xyzz-tau-fixed-fixture") {'
    source = once(source, old,
        'let format = if args[0].contains("unit-orbit-u256-tau-dual-rho0-folded-gauge-xyzz-tau-fixed-fixture") {\n'
        '            165\n        } else if args[0].contains("unit-orbit-u256-tau-fused-orbit-gauge-xyzz-tau-fixed-fixture") {')
    old = '            || args[0] == "--benchmark-scalar-unit-orbit-u256-tau-fused-orbit-gauge-xyzz-tau-fixed-case"'
    source = once(source, old,
        '            || args[0] == "--benchmark-scalar-unit-orbit-u256-tau-dual-rho0-folded-gauge-xyzz-tau-fixed-case"\n'
        '            || args[0] == "--check-scalar-unit-orbit-u256-tau-dual-rho0-folded-gauge-xyzz-tau-fixed-case"\n' + old)
    old = 'if args[0].contains("unit-orbit-u256-tau-fused-orbit-gauge-xyzz-tau") {'
    source = once(source, old,
        'if args[0].contains("unit-orbit-u256-tau-dual-rho0-folded-gauge-xyzz-tau") {\n'
        '                165\n            } else if args[0].contains("unit-orbit-u256-tau-fused-orbit-gauge-xyzz-tau") {')
    return source


def main():
    assert len(sys.argv) == 2, "usage: materialize_native.py OUTPUT_DIRECTORY"
    output = Path(sys.argv[1]).resolve()
    assert not output.exists(), "output directory already exists"
    atlas_receipt = json.loads((HERE / "native-atlas.json").read_bytes())
    assert atlas_receipt["status"] == "constructed"
    assert atlas_receipt["atlas_sha256"] == digest(HERE / ATLAS)
    subprocess.run([sys.executable, str(FUSED / "materialize_native.py"),
                    str(output)], check=True, capture_output=True)
    parent = json.loads((output / "materialization.json").read_bytes())
    for name, expected in parent["generated_sha256"].items():
        assert digest(output / name) == expected
    shutil.copyfile(HERE / ATLAS, output / ATLAS)
    shutil.copyfile(HERE / "fresh-inputs.json", output / PANEL)

    window_path = output / WINDOW_SOURCE
    source = window_path.read_text()
    source = once(source, "struct Tau2TerminalResidualAtlas {",
                  atlas_source() + "\nstruct Tau2TerminalResidualAtlas {")
    source = once(source, "struct TauBucketAtlas {",
                  table_source(source) + "struct TauBucketAtlas {")
    source = once(source, "\nfn multiply_u256_sector_with",
                  "\n" + function_source(source) + "\nfn multiply_u256_sector_with")
    source = once(source, "pub(super) fn warm_format(format: u8) -> usize {\n",
        "pub(super) fn warm_format(format: u8) -> usize {\n"
        "    if format == 65 {\n"
        "        std::sync::LazyLock::force(&super::EXACT_RECIPROCAL_CHECK);\n"
        "        std::sync::LazyLock::force(&super::FIXED_SCALAR_LATTICE);\n"
        "        std::sync::LazyLock::force(&U256_BETA_CANONICAL);\n"
        "        return DUAL_RHO_TABLES.retained_bytes + SOLINAS_UNIT_CONSTANT_BYTES;\n"
        "    }\n")
    source = once(source,
        "    #[test]\n    fn fused_orbit_matches_fresh_panel_and_controls() {",
        RUST_TEST + "    #[test]\n    fn fused_orbit_matches_fresh_panel_and_controls() {")
    window_path.write_text(source)
    main_path = output / MAIN_SOURCE
    main_path.write_text(patch_main(main_path.read_text()))
    receipt = {"schema": 1, "timing_class": "correctness_only",
               "materializer_sha256": digest(Path(__file__)),
               "parent_materialization": parent,
               "assets_sha256": {name: digest(output / name)
                                 for name in (ATLAS, PANEL)},
               "generated_sha256": {name: digest(output / name)
                                    for name in (MAIN_SOURCE, WINDOW_SOURCE)}}
    (output / "materialization.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
