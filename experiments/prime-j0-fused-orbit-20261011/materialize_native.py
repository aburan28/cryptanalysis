#!/usr/bin/env python3
"""Materialize a portable native mode for fused orbit records."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ADIC = HERE.parent / "prime-j0-adic-orbit-20261011"
SPEC = importlib.util.spec_from_file_location("fused_native_parent",
                                              ADIC / "materialize_native.py")
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
MAIN_SOURCE = prior.MAIN_SOURCE
WINDOW_SOURCE = prior.WINDOW_SOURCE
FULL_ASSET = "atlas-r1024-full-fused-orbit.bin"
PANEL_ASSET = "fused-orbit-fresh-inputs.json"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def replace_once(source, old, new):
    assert source.count(old) == 1, old[:120]
    return source.replace(old, new)


RUST_ATLAS = r'''
#[repr(align(8))]
struct AlignedFusedOrbitAtlas([u8; 1_730_332]);

static FUSED_ORBIT_FULL_ATLAS: AlignedFusedOrbitAtlas =
    AlignedFusedOrbitAtlas(*include_bytes!(concat!(
        env!("CARGO_MANIFEST_DIR"), "/atlas-r1024-full-fused-orbit.bin")));

struct FusedOrbitFullAtlas {
    records: &'static [u8],
    seeds: &'static [u8],
}

impl FusedOrbitFullAtlas {
    fn from_bytes(bytes: &'static [u8]) -> Self {
        assert_eq!(&bytes[..4], b"FO18");
        let radix = u32::from_le_bytes(bytes[4..8].try_into().unwrap());
        let classes = u32::from_le_bytes(bytes[8..12].try_into().unwrap()) as usize;
        let seed_count = u32::from_le_bytes(bytes[12..16].try_into().unwrap()) as usize;
        assert_eq!((radix, classes, seed_count), (1024, 174_764, 83_051));
        let seed_start = 16 + 8 * classes;
        assert_eq!(bytes.len(), seed_start + 4 * seed_count);
        let atlas = Self { records: &bytes[16..seed_start], seeds: &bytes[seed_start..] };
        assert_eq!(&atlas.seeds[..4], &[0, 0, 0, 0]);
        for ra in 0..1024 {
            for rb in 0..1024 {
                let (digit, _, _, _) = atlas.digit_residue(ra, rb);
                assert!(norm(digit) <= 1024 * 1024);
            }
        }
        atlas
    }

    fn seed_digits(&self) -> Vec<(i16, i16)> {
        self.seeds.chunks_exact(4).map(|chunk| (
            i16::from_le_bytes(chunk[..2].try_into().unwrap()),
            i16::from_le_bytes(chunk[2..].try_into().unwrap()),
        )).collect()
    }

    fn digit_residue(&self, ra: usize, rb: usize)
        -> ((i32, i32), usize, usize, usize)
    {
        let (class_index, transform) = AdicOrbitFullAtlas::class_index(ra, rb);
        let offset = 8 * class_index;
        let record = u64::from_le_bytes(
            self.records[offset..offset + 8].try_into().unwrap());
        let code = (record & 0xffff_ffff) as usize;
        let da = ((record >> 32) as u16) as i16 as i32;
        let db = ((record >> 48) as u16) as i16 as i32;
        let (seed_id, exponent, canonical_unit) =
            (code >> 5, (code >> 3) & 3, code & 7);
        assert!(seed_id < self.seeds.len() / 4
                && exponent <= 2 && canonical_unit < 6);
        let unit_code = 2 * ((canonical_unit / 2 + 3 - transform / 2) % 3)
            + ((canonical_unit & 1) ^ (transform & 1));
        let inverse = 2 * ((3 - transform / 2) % 3) + (transform & 1);
        let digit = unit_images((da, db))[inverse];
        assert_eq!((digit.0.rem_euclid(1024) as usize,
                    digit.1.rem_euclid(1024) as usize), (ra, rb));
        (digit, seed_id, exponent, unit_code)
    }
}
'''


def patch_main(source):
    for old, new in (
        ("(123..=163)", "(123..=164)"),
        ("(124..=163)", "(124..=164)"),
        ("(125..=163)", "(125..=164)"),
    ):
        source = replace_once(source, old, new)
    source = replace_once(source, "let actual = if unit_orbit_format == 163 {",
        "let actual = if unit_orbit_format == 164 {\n"
        "        unit_orbit_windows::multiply_u256_tau_fused_orbit_gauge_xyzz_tau(\n"
        "            scalar_words.expect(\"fused radix-1024 requires unsigned 256-bit scalar\")\n"
        "        ).0\n"
        "    } else if unit_orbit_format == 163 {")
    source = replace_once(source, "let mode = if unit_orbit_format == 163 {",
        "let mode = if unit_orbit_format == 164 {\n"
        "        \"unit_orbit_u256_tau_fused_orbit_gauge_xyzz_tau_fixed\"\n"
        "    } else if unit_orbit_format == 163 {")
    source = replace_once(source,
        '            || args[0].starts_with("--check-scalar-unit-orbit-u256-tau-adic-orbit-gauge-xyzz-tau")',
        '            || args[0].starts_with("--check-scalar-unit-orbit-u256-tau-fused-orbit-gauge-xyzz-tau")\n'
        '            || args[0].starts_with("--benchmark-scalar-unit-orbit-u256-tau-fused-orbit-gauge-xyzz-tau")\n'
        '            || args[0].starts_with("--check-scalar-unit-orbit-u256-tau-adic-orbit-gauge-xyzz-tau")')
    source = replace_once(source,
        'let format = if args[0].contains("unit-orbit-u256-tau-adic-orbit-gauge-xyzz-tau-fixed-fixture") {',
        'let format = if args[0].contains("unit-orbit-u256-tau-fused-orbit-gauge-xyzz-tau-fixed-fixture") {\n'
        '            164\n'
        '        } else if args[0].contains("unit-orbit-u256-tau-adic-orbit-gauge-xyzz-tau-fixed-fixture") {')
    source = replace_once(source,
        '            || args[0] == "--benchmark-scalar-unit-orbit-u256-tau-adic-orbit-gauge-xyzz-tau-fixed-case"',
        '            || args[0] == "--benchmark-scalar-unit-orbit-u256-tau-fused-orbit-gauge-xyzz-tau-fixed-case"\n'
        '            || args[0] == "--check-scalar-unit-orbit-u256-tau-fused-orbit-gauge-xyzz-tau-fixed-case"\n'
        '            || args[0] == "--benchmark-scalar-unit-orbit-u256-tau-adic-orbit-gauge-xyzz-tau-fixed-case"')
    source = replace_once(source,
        'if args[0].contains("unit-orbit-u256-tau-adic-orbit-gauge-xyzz-tau") {',
        'if args[0].contains("unit-orbit-u256-tau-fused-orbit-gauge-xyzz-tau") {\n'
        '                164\n'
        '            } else if args[0].contains("unit-orbit-u256-tau-adic-orbit-gauge-xyzz-tau") {')
    return source


def main():
    assert len(sys.argv) == 2, "usage: materialize_native.py OUTPUT_DIRECTORY"
    output = Path(sys.argv[1]).resolve()
    assert not output.exists(), "output directory already exists"
    subprocess.run([sys.executable, str(ADIC / "materialize_native.py"),
                    str(output)], check=True, capture_output=True)
    parent = json.loads((output / "materialization.json").read_bytes())
    for name, expected in parent["generated_sha256"].items():
        assert digest(output / name) == expected
    for name in (FULL_ASSET,):
        shutil.copyfile(HERE / name, output / name)
    shutil.copyfile(HERE / "fresh-inputs.json", output / PANEL_ASSET)
    group_path = HERE / "group-check.json"
    group = json.loads(group_path.read_bytes())
    assert group["status"] == "passed"
    panel = group["results"]["fused"]
    assert panel["cases"] == 4096
    assert group["atlas_sha256"]["fused"] == digest(HERE / FULL_ASSET)
    assert group["panel_sha256"] == digest(HERE / "fresh-inputs.json")

    window_path = output / WINDOW_SOURCE
    source = window_path.read_text()
    source = replace_once(source, "struct Tau2TerminalResidualAtlas {",
                          RUST_ATLAS + "\nstruct Tau2TerminalResidualAtlas {")
    table = prior.prior.RUST_TABLE.replace("OrbitQuotientTables", "FusedOrbitTables") \
        .replace("OrbitQuotientFullAtlas::from_bytes(ORBIT_QUOTIENT_FULL_ATLAS)",
                 "FusedOrbitFullAtlas::from_bytes(&FUSED_ORBIT_FULL_ATLAS.0)") \
        .replace("OrbitQuotientFullAtlas", "FusedOrbitFullAtlas") \
        .replace("ORBIT_QUOTIENT_FULL_ATLAS.len()", "size_of::<AlignedFusedOrbitAtlas>()") \
        .replace("ORBIT_QUOTIENT_TABLES", "FUSED_ORBIT_TABLES")
    source = replace_once(source, "struct TauBucketAtlas {",
                          table + "\nstruct TauBucketAtlas {")
    start = "pub(super) fn multiply_u256_tau_adic_orbit_gauge_xyzz_tau("
    end = "\nfn multiply_u256_sector_with"
    assert source.count(start) == source.count(end) == 1
    function = source[source.index(start):source.index(end)]
    cloned = function.replace(
        "multiply_u256_tau_adic_orbit_gauge_xyzz_tau",
        "multiply_u256_tau_fused_orbit_gauge_xyzz_tau"
    ).replace("AdicOrbitTables", "FusedOrbitTables"
    ).replace("ADIC_ORBIT_TABLES", "FUSED_ORBIT_TABLES")
    source = replace_once(source, end, "\n" + cloned + end)
    source = replace_once(source, "pub(super) fn warm_format(format: u8) -> usize {\n",
        "pub(super) fn warm_format(format: u8) -> usize {\n"
        "    if format == 64 {\n"
        "        std::sync::LazyLock::force(&super::EXACT_RECIPROCAL_CHECK);\n"
        "        std::sync::LazyLock::force(&super::FIXED_SCALAR_LATTICE);\n"
        "        std::sync::LazyLock::force(&U256_BETA_CANONICAL);\n"
        "        return FUSED_ORBIT_TABLES.retained_bytes + SOLINAS_UNIT_CONSTANT_BYTES;\n"
        "    }\n")
    test = prior.prior.RUST_TEST.replace("orbit_quotient", "fused_orbit") \
        .replace("multiply_u256_tau_orbit_quotient_gauge_xyzz_tau",
                 "multiply_u256_tau_fused_orbit_gauge_xyzz_tau") \
        .replace("multiply_u256_tau_power2_tau2_gauge_xyzz_tau(words)",
                 "multiply_u256_tau_adic_orbit_gauge_xyzz_tau(words)") \
        .replace("orbit-quotient-fresh-inputs.json", PANEL_ASSET) \
        .replace("warm_format(62)", "warm_format(64)") \
        .replace("__ADDITIONS__", f"{panel['mixed_additions']:_}") \
        .replace("__ROTATIONS__", f"{panel['gauge_rotations']:_}")
    source = replace_once(source,
        "    #[test]\n    fn adic_orbit_matches_fresh_panel_and_controls() {",
        test + "    #[test]\n    fn adic_orbit_matches_fresh_panel_and_controls() {")
    main_path = output / MAIN_SOURCE
    main_path.write_text(patch_main(main_path.read_text()))
    window_path.write_text(source)
    receipt = {"schema": 1, "timing_class": "correctness_only",
               "materializer_sha256": digest(Path(__file__)),
               "parent_materialization": parent,
               "group_receipt_sha256": digest(group_path),
               "assets_sha256": {name: digest(output / name)
                                 for name in (FULL_ASSET, PANEL_ASSET)},
               "included_assets_sha256": parent["included_assets_sha256"],
               "generated_sha256": {name: digest(output / name)
                                    for name in (MAIN_SOURCE, WINDOW_SOURCE)}}
    (output / "materialization.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
