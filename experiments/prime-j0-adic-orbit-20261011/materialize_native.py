#!/usr/bin/env python3
"""Materialize a separate native mode for direct 2-adic orbit lookup."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-orbit-quotient-20261011"
SPEC = importlib.util.spec_from_file_location("quotient_native_parent",
                                              PARENT / "materialize_native.py")
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
MAIN_SOURCE = prior.MAIN_SOURCE
WINDOW_SOURCE = prior.WINDOW_SOURCE
FULL_ASSET = "atlas-r1024-full-adic-orbit.bin"
PANEL_ASSET = "adic-orbit-fresh-inputs.json"
LEGACY_ROOT = "/Volumes/SSD990/llm/tmp/prime-j0-r944-persistent"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def replace_once(source, old, new):
    assert source.count(old) == 1, old[:120]
    return source.replace(old, new)


def package_includes(output, main_source, window_source):
    """Replace inherited absolute includes with byte-identical crate assets."""
    repository = HERE.parent.parent.resolve()
    expression = re.compile(
        r'include_(bytes|str)!\(\s*"' + re.escape(LEGACY_ROOT)
        + r'/([^"]+)"\s*\)'
    )
    included = {}

    def rewrite(source):
        def substitute(match):
            kind, relative = match.groups()
            assert ".." not in Path(relative).parts
            original = repository / relative
            assert original.is_file(), original
            location = Path("repo-assets") / relative
            target = output / location
            if str(location) not in included:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, target)
                included[str(location)] = digest(target)
            return (f'include_{kind}!(concat!(env!("CARGO_MANIFEST_DIR"), '
                    f'"/{location.as_posix()}"))')

        return expression.sub(substitute, source)

    path_attribute = f'#[path = "{LEGACY_ROOT}/suite/src/ct_bignum.rs"]'
    main_source = replace_once(main_source, path_attribute,
                               '#[path = "ct_bignum.rs"]')
    ct_source = repository / "suite/src/ct_bignum.rs"
    assert ct_source.is_file()
    ct_target = output / "src/bin/ct_bignum.rs"
    shutil.copyfile(ct_source, ct_target)
    included["src/bin/ct_bignum.rs"] = digest(ct_target)
    main_source = rewrite(main_source)
    window_source = rewrite(window_source)
    assert LEGACY_ROOT not in main_source and LEGACY_ROOT not in window_source
    assert len(included) >= 40
    return main_source, window_source, dict(sorted(included.items()))


RUST_ATLAS = r'''
const ADIC_ORBIT_FULL_ATLAS: &[u8] = include_bytes!(concat!(
    env!("CARGO_MANIFEST_DIR"), "/atlas-r1024-full-adic-orbit.bin"));

struct AdicOrbitFullAtlas {
    codes: &'static [u8],
    seeds: &'static [u8],
}

impl AdicOrbitFullAtlas {
    fn from_bytes(bytes: &'static [u8]) -> Self {
        assert_eq!(&bytes[..4], b"AO14");
        let radix = u32::from_le_bytes(bytes[4..8].try_into().unwrap());
        let classes = u32::from_le_bytes(bytes[8..12].try_into().unwrap()) as usize;
        let seed_count = u32::from_le_bytes(bytes[12..16].try_into().unwrap()) as usize;
        assert_eq!((radix, classes, seed_count), (1024, 174_764, 83_051));
        let seed_start = 16 + 3 * classes;
        assert_eq!(bytes.len(), seed_start + 4 * seed_count);
        let atlas = Self { codes: &bytes[16..seed_start], seeds: &bytes[seed_start..] };
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

    fn class_index(ra: usize, rb: usize) -> (usize, usize) {
        const OFFSETS: [usize; 11] =
            [0, 1, 2, 4, 12, 44, 172, 684, 2732, 10924, 43692];
        assert!(ra < 1024 && rb < 1024);
        let value = ra | rb;
        if value == 0 { return (0, 0); }
        let valuation = value.trailing_zeros() as usize;
        let m = 10 - valuation;
        let mask = (1i32 << m) - 1;
        let mut a = (ra >> valuation) as i32;
        let mut b = (rb >> valuation) as i32;
        let power = match (a & 1, b & 1) {
            (1, 0) => 0,
            (0, 1) => {
                let rotated = ((a + 3 * b) & mask, (-a - 2 * b) & mask);
                (a, b) = rotated;
                1
            },
            (1, 1) => {
                let rotated = ((-2 * a - 3 * b) & mask, (a + b) & mask);
                (a, b) = rotated;
                2
            },
            _ => unreachable!(),
        };
        debug_assert_eq!((a & 1, b & 1), (1, 0));
        let sign = usize::from(m > 1 && a >= (1i32 << (m - 1)));
        if sign != 0 { a = (-a) & mask; b = (-b) & mask; }
        if m == 1 {
            debug_assert_eq!((a, b), (1, 0));
            return (1, 2 * power);
        }
        let half = 1usize << (m - 1);
        debug_assert!(a > 0 && a < half as i32 && (a & 1) == 1 && (b & 1) == 0);
        let index = OFFSETS[m] + ((a as usize - 1) / 2) * half + (b as usize / 2);
        debug_assert!(index < 174_764);
        (index, 2 * power + sign)
    }

    fn digit_residue(&self, ra: usize, rb: usize)
        -> ((i32, i32), usize, usize, usize)
    {
        let (class_index, transform) = Self::class_index(ra, rb);
        let offset = 3 * class_index;
        let code = (self.codes[offset] as usize)
            | ((self.codes[offset + 1] as usize) << 8)
            | ((self.codes[offset + 2] as usize) << 16);
        let (seed_id, exponent, canonical_unit) =
            (code >> 5, (code >> 3) & 3, code & 7);
        assert!(seed_id < self.seeds.len() / 4
                && exponent <= 2 && canonical_unit < 6);
        let unit_code = 2 * ((canonical_unit / 2 + 3 - transform / 2) % 3)
            + ((canonical_unit & 1) ^ (transform & 1));
        let offset = 4 * seed_id;
        let seed = (
            i16::from_le_bytes(self.seeds[offset..offset + 2]
                               .try_into().unwrap()) as i32,
            i16::from_le_bytes(self.seeds[offset + 2..offset + 4]
                               .try_into().unwrap()) as i32,
        );
        let digit = match exponent {
            0 => seed,
            1 => (-3 * seed.1, seed.0 + 3 * seed.1),
            2 => {
                let first = (-3 * seed.1, seed.0 + 3 * seed.1);
                (-3 * first.1, first.0 + 3 * first.1)
            },
            _ => unreachable!(),
        };
        let digit = unit_images(digit)[unit_code];
        assert_eq!((digit.0.rem_euclid(1024) as usize,
                    digit.1.rem_euclid(1024) as usize), (ra, rb));
        (digit, seed_id, exponent, unit_code)
    }
}
'''


def patch_main_source(source):
    for old, new in (
        ("(123..=162)", "(123..=163)"),
        ("(124..=162)", "(124..=163)"),
        ("(125..=162)", "(125..=163)"),
    ):
        source = replace_once(source, old, new)
    source = replace_once(source, "let actual = if unit_orbit_format == 162 {",
        "let actual = if unit_orbit_format == 163 {\n"
        "        unit_orbit_windows::multiply_u256_tau_adic_orbit_gauge_xyzz_tau(\n"
        "            scalar_words.expect(\"direct-index radix-1024 requires unsigned 256-bit scalar\")\n"
        "        ).0\n"
        "    } else if unit_orbit_format == 162 {")
    source = replace_once(source, "let mode = if unit_orbit_format == 162 {",
        "let mode = if unit_orbit_format == 163 {\n"
        "        \"unit_orbit_u256_tau_adic_orbit_gauge_xyzz_tau_fixed\"\n"
        "    } else if unit_orbit_format == 162 {")
    source = replace_once(source,
        '            || args[0].starts_with("--check-scalar-unit-orbit-u256-tau-orbit-quotient-gauge-xyzz-tau")',
        '            || args[0].starts_with("--check-scalar-unit-orbit-u256-tau-adic-orbit-gauge-xyzz-tau")\n'
        '            || args[0].starts_with("--benchmark-scalar-unit-orbit-u256-tau-adic-orbit-gauge-xyzz-tau")\n'
        '            || args[0].starts_with("--check-scalar-unit-orbit-u256-tau-orbit-quotient-gauge-xyzz-tau")')
    source = replace_once(source,
        'let format = if args[0].contains("unit-orbit-u256-tau-orbit-quotient-gauge-xyzz-tau-fixed-fixture") {',
        'let format = if args[0].contains("unit-orbit-u256-tau-adic-orbit-gauge-xyzz-tau-fixed-fixture") {\n'
        '            163\n'
        '        } else if args[0].contains("unit-orbit-u256-tau-orbit-quotient-gauge-xyzz-tau-fixed-fixture") {')
    source = replace_once(source,
        '            || args[0] == "--benchmark-scalar-unit-orbit-u256-tau-orbit-quotient-gauge-xyzz-tau-fixed-case"',
        '            || args[0] == "--benchmark-scalar-unit-orbit-u256-tau-adic-orbit-gauge-xyzz-tau-fixed-case"\n'
        '            || args[0] == "--check-scalar-unit-orbit-u256-tau-adic-orbit-gauge-xyzz-tau-fixed-case"\n'
        '            || args[0] == "--benchmark-scalar-unit-orbit-u256-tau-orbit-quotient-gauge-xyzz-tau-fixed-case"')
    source = replace_once(source,
        'if args[0].contains("unit-orbit-u256-tau-orbit-quotient-gauge-xyzz-tau") {',
        'if args[0].contains("unit-orbit-u256-tau-adic-orbit-gauge-xyzz-tau") {\n'
        '                163\n'
        '            } else if args[0].contains("unit-orbit-u256-tau-orbit-quotient-gauge-xyzz-tau") {')
    return source


def main():
    assert len(sys.argv) == 2, "usage: materialize_native.py OUTPUT_DIRECTORY"
    output = Path(sys.argv[1]).resolve()
    assert not output.exists(), "output directory already exists"
    subprocess.run([sys.executable, str(PARENT / "materialize_native.py"),
                    str(output)], check=True, capture_output=True)
    parent = json.loads((output / "materialization.json").read_bytes())
    for name, expected in parent["generated_sha256"].items():
        assert digest(output / name) == expected
    shutil.copyfile(HERE / FULL_ASSET, output / FULL_ASSET)
    shutil.copyfile(HERE / "fresh-inputs.json", output / PANEL_ASSET)
    assert digest(HERE / FULL_ASSET) == digest(output / FULL_ASSET)
    assert digest(HERE / "fresh-inputs.json") == digest(output / PANEL_ASSET)

    group_path = HERE / "group-check.json"
    group = json.loads(group_path.read_bytes())
    assert group["status"] == "passed"
    panel = group["results"]["adic"]
    assert panel["cases"] == 4096
    assert group["atlas_sha256"]["adic"] == digest(HERE / FULL_ASSET)
    assert group["panel_sha256"] == digest(HERE / "fresh-inputs.json")

    window_path = output / WINDOW_SOURCE
    source = window_path.read_text()
    source = replace_once(source, "struct Tau2TerminalResidualAtlas {",
                          RUST_ATLAS + "\nstruct Tau2TerminalResidualAtlas {")
    table = prior.RUST_TABLE.replace("OrbitQuotientTables", "AdicOrbitTables") \
        .replace("OrbitQuotientFullAtlas", "AdicOrbitFullAtlas") \
        .replace("ORBIT_QUOTIENT_FULL_ATLAS", "ADIC_ORBIT_FULL_ATLAS") \
        .replace("ORBIT_QUOTIENT_TABLES", "ADIC_ORBIT_TABLES")
    source = replace_once(source, "struct TauBucketAtlas {",
                          table + "\nstruct TauBucketAtlas {")
    start = "pub(super) fn multiply_u256_tau_orbit_quotient_gauge_xyzz_tau("
    end = "\nfn multiply_u256_sector_with"
    assert source.count(start) == source.count(end) == 1
    old_function = source[source.index(start):source.index(end)]
    cloned = old_function.replace(
        "multiply_u256_tau_orbit_quotient_gauge_xyzz_tau",
        "multiply_u256_tau_adic_orbit_gauge_xyzz_tau"
    ).replace("OrbitQuotientTables", "AdicOrbitTables"
    ).replace("ORBIT_QUOTIENT_TABLES", "ADIC_ORBIT_TABLES")
    source = replace_once(source, end, "\n" + cloned + end)
    source = replace_once(source, "pub(super) fn warm_format(format: u8) -> usize {\n",
        "pub(super) fn warm_format(format: u8) -> usize {\n"
        "    if format == 63 {\n"
        "        std::sync::LazyLock::force(&super::EXACT_RECIPROCAL_CHECK);\n"
        "        std::sync::LazyLock::force(&super::FIXED_SCALAR_LATTICE);\n"
        "        std::sync::LazyLock::force(&U256_BETA_CANONICAL);\n"
        "        return ADIC_ORBIT_TABLES.retained_bytes + SOLINAS_UNIT_CONSTANT_BYTES;\n"
        "    }\n")
    test = prior.RUST_TEST.replace("orbit_quotient", "adic_orbit") \
        .replace("multiply_u256_tau_orbit_quotient_gauge_xyzz_tau",
                 "multiply_u256_tau_adic_orbit_gauge_xyzz_tau") \
        .replace("orbit-quotient-fresh-inputs.json", PANEL_ASSET) \
        .replace("warm_format(62)", "warm_format(63)") \
        .replace("__ADDITIONS__", f"{panel['mixed_additions']:_}") \
        .replace("__ROTATIONS__", f"{panel['gauge_rotations']:_}")
    source = replace_once(source,
        "    #[test]\n    fn orbit_quotient_matches_fresh_panel_and_controls() {",
        test + "    #[test]\n"
        "    fn orbit_quotient_matches_fresh_panel_and_controls() {")
    main_path = output / MAIN_SOURCE
    main_source, source, included = package_includes(
        output, patch_main_source(main_path.read_text()), source)
    main_path.write_text(main_source)
    window_path.write_text(source)
    receipt = {"schema": 1, "timing_class": "correctness_only",
               "materializer_sha256": digest(Path(__file__)),
               "parent_materialization": parent,
               "group_receipt_sha256": digest(group_path),
               "assets_sha256": {name: digest(output / name)
                                 for name in (FULL_ASSET, PANEL_ASSET)},
               "included_assets_sha256": included,
               "generated_sha256": {name: digest(output / name)
                                    for name in (MAIN_SOURCE, WINDOW_SOURCE)}}
    (output / "materialization.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
