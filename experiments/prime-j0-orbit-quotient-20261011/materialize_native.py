#!/usr/bin/env python3
"""Materialize source-pinned native orbit-quotient scalar multiplication."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-power2-cache-budget-20261011"
MAIN_SOURCE = "src/bin/eisenstein_fixed.rs"
WINDOW_SOURCE = "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
FULL_ASSET = "atlas-r1024-full-orbit-quotient.bin"
PANEL_ASSET = "orbit-quotient-fresh-inputs.json"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def replace_once(source, old, new):
    assert source.count(old) == 1, old[:120]
    return source.replace(old, new)


RUST_ATLAS = r'''
const ORBIT_QUOTIENT_FULL_ATLAS: &[u8] = include_bytes!(concat!(
    env!("CARGO_MANIFEST_DIR"), "/atlas-r1024-full-orbit-quotient.bin"));

struct OrbitQuotientFullAtlas {
    words: &'static [u8],
    rank: &'static [u8],
    codes: &'static [u8],
    seeds: &'static [u8],
}

impl OrbitQuotientFullAtlas {
    fn from_bytes(bytes: &'static [u8]) -> Self {
        assert_eq!(&bytes[..4], b"OQ13");
        let radix = u32::from_le_bytes(bytes[4..8].try_into().unwrap()) as usize;
        let classes = u32::from_le_bytes(bytes[8..12].try_into().unwrap()) as usize;
        let seed_count = u32::from_le_bytes(bytes[12..16].try_into().unwrap()) as usize;
        let word_count = u32::from_le_bytes(bytes[16..20].try_into().unwrap()) as usize;
        assert_eq!((radix, classes, seed_count, word_count),
                   (1024, 174_764, 83_051, 16_384));
        let rank_start = 20 + 8 * word_count;
        let code_start = rank_start + 4 * (word_count + 1);
        let seed_start = code_start + 3 * classes;
        assert_eq!(bytes.len(), seed_start + 4 * seed_count);
        let atlas = Self {
            words: &bytes[20..rank_start],
            rank: &bytes[rank_start..code_start],
            codes: &bytes[code_start..seed_start],
            seeds: &bytes[seed_start..],
        };
        assert_eq!(&atlas.seeds[..4], &[0, 0, 0, 0]);
        let mut prefix = 0usize;
        for index in 0..word_count {
            let offset = 8 * index;
            let word = u64::from_le_bytes(
                atlas.words[offset..offset + 8].try_into().unwrap());
            let offset = 4 * index;
            let stored = u32::from_le_bytes(
                atlas.rank[offset..offset + 4].try_into().unwrap()) as usize;
            assert_eq!(stored, prefix);
            prefix += word.count_ones() as usize;
        }
        assert_eq!(prefix, classes);
        assert_eq!(u32::from_le_bytes(atlas.rank[4 * word_count..]
                   .try_into().unwrap()) as usize, classes);
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
        assert!(ra < 1024 && rb < 1024);
        let mut canonical = usize::MAX;
        let mut transform = 0usize;
        for (index, image) in unit_images((ra as i32, rb as i32))
            .iter().enumerate()
        {
            let slot = (image.0.rem_euclid(1024) as usize) * 1024
                     + image.1.rem_euclid(1024) as usize;
            if slot < canonical {
                canonical = slot;
                transform = index;
            }
        }
        let word_index = canonical / 64;
        let bit = canonical % 64;
        let offset = 8 * word_index;
        let word = u64::from_le_bytes(
            self.words[offset..offset + 8].try_into().unwrap());
        assert_ne!(word & (1u64 << bit), 0);
        let offset = 4 * word_index;
        let prefix = u32::from_le_bytes(
            self.rank[offset..offset + 4].try_into().unwrap()) as usize;
        let lower = if bit == 0 { 0 } else { word & ((1u64 << bit) - 1) };
        let dense = prefix + lower.count_ones() as usize;
        let offset = 3 * dense;
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
            }
            _ => unreachable!(),
        };
        let digit = unit_images(digit)[unit_code];
        assert_eq!((digit.0.rem_euclid(1024) as usize,
                    digit.1.rem_euclid(1024) as usize), (ra, rb));
        (digit, seed_id, exponent, unit_code)
    }
}
'''


RUST_TABLE = r'''
struct OrbitQuotientTables {
    full: OrbitQuotientFullAtlas,
    terminal: Tau2TerminalResidualAtlas,
    windows: Vec<Box<[U256Affine]>>,
    retained_bytes: usize,
}

impl OrbitQuotientTables {
    fn new() -> Self {
        let full = OrbitQuotientFullAtlas::from_bytes(ORBIT_QUOTIENT_FULL_ATLAS);
        let terminal = Tau2TerminalResidualAtlas::from_bytes(
            POWER2_TAU2_TERMINAL_ATLAS);
        let mut windows = Vec::with_capacity(13);
        let mut base = Jacobian::generator();
        for index in 0..13 {
            let seeds = if index == 12 { terminal.seed_digits() }
                        else { full.seed_digits() };
            windows.push(build_u256_window(&seeds, base));
            if index < 12 {
                for _ in 0..10 { base = base.double(); }
            }
        }
        let entries = windows.iter().map(|row| row.len()).sum::<usize>();
        assert_eq!(entries, 1_005_900);
        assert_eq!(size_of::<U256Affine>(), 64);
        let retained_bytes = entries * size_of::<U256Affine>()
            + ORBIT_QUOTIENT_FULL_ATLAS.len() + POWER2_TAU2_TERMINAL_ATLAS.len()
            + size_of::<Self>() + windows.capacity() * size_of::<Box<[U256Affine]>>();
        assert!(retained_bytes + SOLINAS_UNIT_CONSTANT_BYTES < 67_108_864);
        Self { full, terminal, windows, retained_bytes }
    }
}

static ORBIT_QUOTIENT_TABLES: LazyLock<OrbitQuotientTables> =
    LazyLock::new(OrbitQuotientTables::new);
'''

RUST_TEST = r'''
    #[test]
    fn orbit_quotient_matches_fresh_panel_and_controls() {
        let panel: serde_json::Value = serde_json::from_str(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"), "/orbit-quotient-fresh-inputs.json"
        ))).unwrap();
        let scalars = panel["scalars_hex"].as_array().unwrap();
        assert_eq!(scalars.len(), 4096);
        let mut additions = 0usize;
        let mut rotations = 0usize;
        let mut direct_additions = 0usize;
        let mut direct_rotations = 0usize;
        for (index, text) in scalars.iter().enumerate() {
            let scalar = BigInt::parse_bytes(text.as_str().unwrap().as_bytes(), 16).unwrap();
            let words = super::super::scalar_words_256(&scalar).unwrap();
            let candidate = multiply_u256_tau_orbit_quotient_gauge_xyzz_tau(words);
            let direct = multiply_u256_tau_power2_tau2_gauge_xyzz_tau(words);
            let two_image = multiply_u256_tau_power2_residual_gauge_xyzz_tau(words);
            assert_eq!(candidate.0, direct.0, "direct point {index}");
            assert_eq!(candidate.0, two_image.0, "two-image point {index}");
            assert_eq!(candidate.1, direct.1, "representative {index}");
            assert_eq!((candidate.4, candidate.5), (direct.4, direct.5),
                       "representative metadata {index}");
            assert_eq!(candidate.3, warm_format(62));
            assert!(candidate.2 <= 12 && candidate.6 <= 6, "bounds {index}");
            additions += candidate.2;
            rotations += candidate.6;
            direct_additions += direct.2;
            direct_rotations += direct.6;
            if index < 128 {
                let reduced = &scalar % &SCALAR_LATTICE.n;
                assert_eq!(candidate.0, independent_binary_point(&reduced).affine_hex(),
                           "independent binary {index}");
            }
        }
        assert_eq!((additions, rotations), (__ADDITIONS__, __ROTATIONS__));
        println!("orbit_quotient_cases={} retained_bytes={} additions={} gauge_products={} direct_additions={} direct_gauge_products={}",
                 scalars.len(), warm_format(62), additions, rotations,
                 direct_additions, direct_rotations);
    }

'''


def patch_main_source(source):
    for old, new in (
        ("(123..=161)", "(123..=162)"),
        ("(124..=161)", "(124..=162)"),
        ("(125..=161)", "(125..=162)"),
    ):
        source = replace_once(source, old, new)
    source = replace_once(source, "let actual = if unit_orbit_format == 161 {",
        "let actual = if unit_orbit_format == 162 {\n"
        "        unit_orbit_windows::multiply_u256_tau_orbit_quotient_gauge_xyzz_tau(\n"
        "            scalar_words.expect(\"orbit quotient radix-1024 requires unsigned 256-bit scalar\")\n"
        "        ).0\n"
        "    } else if unit_orbit_format == 161 {")
    source = replace_once(source, "let mode = if unit_orbit_format == 161 {",
        "let mode = if unit_orbit_format == 162 {\n"
        "        \"unit_orbit_u256_tau_orbit_quotient_gauge_xyzz_tau_fixed\"\n"
        "    } else if unit_orbit_format == 161 {")
    source = replace_once(source,
        '            || args[0].starts_with("--check-scalar-unit-orbit-u256-tau-power2-tau2-gauge-xyzz-tau")',
        '            || args[0].starts_with("--check-scalar-unit-orbit-u256-tau-orbit-quotient-gauge-xyzz-tau")\n'
        '            || args[0].starts_with("--benchmark-scalar-unit-orbit-u256-tau-orbit-quotient-gauge-xyzz-tau")\n'
        '            || args[0].starts_with("--check-scalar-unit-orbit-u256-tau-power2-tau2-gauge-xyzz-tau")')
    source = replace_once(source,
        'let format = if args[0].contains("unit-orbit-u256-tau-power2-tau2-gauge-xyzz-tau-fixed-fixture") {',
        'let format = if args[0].contains("unit-orbit-u256-tau-orbit-quotient-gauge-xyzz-tau-fixed-fixture") {\n'
        '            162\n'
        '        } else if args[0].contains("unit-orbit-u256-tau-power2-tau2-gauge-xyzz-tau-fixed-fixture") {')
    source = replace_once(source,
        '            || args[0] == "--benchmark-scalar-unit-orbit-u256-tau-power2-tau2-gauge-xyzz-tau-fixed-case"',
        '            || args[0] == "--benchmark-scalar-unit-orbit-u256-tau-orbit-quotient-gauge-xyzz-tau-fixed-case"\n'
        '            || args[0] == "--check-scalar-unit-orbit-u256-tau-orbit-quotient-gauge-xyzz-tau-fixed-case"\n'
        '            || args[0] == "--benchmark-scalar-unit-orbit-u256-tau-power2-tau2-gauge-xyzz-tau-fixed-case"')
    source = replace_once(source,
        'if args[0].contains("unit-orbit-u256-tau-power2-tau2-gauge-xyzz-tau") {',
        'if args[0].contains("unit-orbit-u256-tau-orbit-quotient-gauge-xyzz-tau") {\n'
        '                162\n'
        '            } else if args[0].contains("unit-orbit-u256-tau-power2-tau2-gauge-xyzz-tau") {')
    return source


def main():
    assert len(sys.argv) == 2, "usage: materialize_native.py OUTPUT_DIRECTORY"
    output = Path(sys.argv[1]).resolve()
    assert not output.exists(), "output directory already exists"
    subprocess.run([sys.executable, str(PARENT / "materialize_native.py"),
                    str(output)], check=True, capture_output=True)
    parent = json.loads((output / "materialization.json").read_bytes())
    assert parent["timing_class"] == "correctness_only"
    for name, expected in parent["generated_sha256"].items():
        assert digest(output / name) == expected
    shutil.copyfile(HERE / FULL_ASSET, output / FULL_ASSET)
    shutil.copyfile(HERE / "fresh-inputs.json", output / PANEL_ASSET)
    assert digest(HERE / FULL_ASSET) == digest(output / FULL_ASSET)
    assert digest(HERE / "fresh-inputs.json") == digest(output / PANEL_ASSET)

    group_path = HERE / "group-check.json"
    group = json.loads(group_path.read_bytes())
    assert group["status"] == "passed"
    panel = group["results"]["quotient"]
    assert panel["cases"] == 4096
    assert group["atlas_sha256"]["quotient"]["full"] == digest(HERE / FULL_ASSET)
    assert group["panel_sha256"] == digest(HERE / "fresh-inputs.json")

    window_path = output / WINDOW_SOURCE
    source = window_path.read_text()
    source = replace_once(source, "struct Tau2TerminalResidualAtlas {",
                          RUST_ATLAS + "\nstruct Tau2TerminalResidualAtlas {")
    source = replace_once(source, "struct TauBucketAtlas {",
                          RUST_TABLE + "\nstruct TauBucketAtlas {")
    start = "pub(super) fn multiply_u256_tau_power2_tau2_gauge_xyzz_tau("
    end = "\nfn multiply_u256_sector_with"
    assert source.count(start) == source.count(end) == 1
    original = source[source.index(start):source.index(end)]
    cloned = original.replace(
        "multiply_u256_tau_power2_tau2_gauge_xyzz_tau",
        "multiply_u256_tau_orbit_quotient_gauge_xyzz_tau"
    ).replace("Power2Tau2Tables", "OrbitQuotientTables"
    ).replace("POWER2_TAU2_TABLES", "ORBIT_QUOTIENT_TABLES")
    source = replace_once(source, end, "\n" + cloned + end)
    source = replace_once(source, "pub(super) fn warm_format(format: u8) -> usize {\n",
        "pub(super) fn warm_format(format: u8) -> usize {\n"
        "    if format == 62 {\n"
        "        std::sync::LazyLock::force(&super::EXACT_RECIPROCAL_CHECK);\n"
        "        std::sync::LazyLock::force(&super::FIXED_SCALAR_LATTICE);\n"
        "        std::sync::LazyLock::force(&U256_BETA_CANONICAL);\n"
        "        return ORBIT_QUOTIENT_TABLES.retained_bytes + SOLINAS_UNIT_CONSTANT_BYTES;\n"
        "    }\n")
    test = RUST_TEST.replace("__ADDITIONS__",
        f"{panel['mixed_additions']:_}").replace("__ROTATIONS__",
        f"{panel['gauge_rotations']:_}")
    source = replace_once(source,
        "    #[test]\n    fn frontier16_bucket_all_points_match_independent_group_sums() {",
        test + "    #[test]\n"
        "    fn frontier16_bucket_all_points_match_independent_group_sums() {")
    window_path.write_text(source)
    main_path = output / MAIN_SOURCE
    main_path.write_text(patch_main_source(main_path.read_text()))
    receipt = {
        "schema": 1,
        "timing_class": "correctness_only",
        "materializer_sha256": digest(Path(__file__)),
        "parent_materialization": parent,
        "group_receipt_sha256": digest(group_path),
        "assets_sha256": {name: digest(output / name)
                          for name in (FULL_ASSET, PANEL_ASSET)},
        "generated_sha256": {name: digest(output / name)
                             for name in (MAIN_SOURCE, WINDOW_SOURCE)},
    }
    (output / "materialization.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
