#!/usr/bin/env python3
"""Generate the mixed-radix scalar evaluator with one axial point table."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
BASE = HERE / "native_bench_cli.py"


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise ValueError(f"expected one source anchor, found {source.count(old)}: {old[:80]}")
    return source.replace(old, new, 1)


AXIAL_RUST = r"""
const MIXED640_AXIAL_LIMITS: [usize; 14] = [
    1023, 1023, 1023, 1023, 1023, 1023,
    1278, 1278, 1278, 1278, 1278, 1278, 1278, 780,
];

struct Mixed640AxialTables {
    full9: FrontierAtlas,
    full640: Radix640Atlas,
    final640: Radix640Atlas,
    windows: Vec<Box<[U256Affine]>>,
    retained_bytes: usize,
}

impl Mixed640AxialTables {
    fn new() -> Self {
        let full9 = FrontierAtlas::from_bytes(FRONTIER9_FULL_ATLAS, 9, 512, 21_847);
        let full640 = Radix640Atlas::from_bytes(RADIX640_FULL_ATLAS, 640, 34_135);
        let final640 = Radix640Atlas::from_bytes(RADIX640_FINAL_ATLAS, 391, 45_163);
        let mut windows = Vec::with_capacity(RADIX640_SCHEDULE.len());
        let mut base = Jacobian::generator();
        for (index, &radix) in RADIX640_SCHEDULE.iter().enumerate() {
            let points = affine_multiples(base, MIXED640_AXIAL_LIMITS[index]);
            let row = points.iter().enumerate().map(|(position, &point)| {
                if position == 0 {
                    U256Affine { x: super::U256::ZERO, y: super::U256::ZERO }
                } else {
                    let affine = point.into_affine();
                    U256Affine { x: super::hybrid_pair_mont(affine.x),
                                 y: super::hybrid_pair_mont(affine.y) }
                }
            }).collect::<Vec<_>>().into_boxed_slice();
            windows.push(row);
            if index + 1 < RADIX640_SCHEDULE.len() {
                if radix == 512 {
                    for _ in 0..9 { base = base.double(); }
                } else {
                    base = affine_multiples(base, radix).pop().unwrap();
                }
            }
        }
        let entries = windows.iter().map(|row| row.len()).sum::<usize>();
        assert_eq!(entries, 15_878);
        assert_eq!(size_of::<U256Affine>(), 64);
        let retained_bytes = entries * size_of::<U256Affine>()
            + FRONTIER9_FULL_ATLAS.len() + RADIX640_FULL_ATLAS.len()
            + RADIX640_FINAL_ATLAS.len() + size_of::<Self>()
            + windows.capacity() * size_of::<Box<[U256Affine]>>()
            + SOLINAS_UNIT_CONSTANT_BYTES;
        assert!(retained_bytes < 6_000_000);
        Self { full9, full640, final640, windows, retained_bytes }
    }
}

static MIXED640_AXIAL_TABLES: LazyLock<Mixed640AxialTables> =
    LazyLock::new(Mixed640AxialTables::new);

pub(super) fn warm_mixed640_axial_table() -> usize {
    std::sync::LazyLock::force(&super::EXACT_RECIPROCAL_CHECK);
    std::sync::LazyLock::force(&super::FIXED_SCALAR_LATTICE);
    std::sync::LazyLock::force(&U256_BETA_UNITS);
    MIXED640_AXIAL_TABLES.retained_bytes
}

pub(super) fn multiply_u256_tau_mixed640_axial(
    scalar_words: [u64; 4],
) -> (String, (Signed192, Signed192), usize, usize, bool, usize, usize) {
    let scalar = super::Uint(scalar_words);
    let residue = if bool::from(scalar.ct_lt(&super::SCALAR_ORDER_WORDS)) {
        scalar
    } else {
        super::U256::sbb(&scalar, &super::SCALAR_ORDER_WORDS).0
    };
    let (representative, fallback, corner) =
        super::hexagonal_certified_fixed_choice_words(residue.0);
    let tables = &*MIXED640_AXIAL_TABLES;
    let (mut a, mut b) = representative;
    let mut buckets = [U256XYZZ::identity(); 2];
    let mut terms = 0usize;
    for (index, &radix) in RADIX640_SCHEDULE.iter().enumerate() {
        let digit = if index < 6 {
            let ra = a.rem_euclid_power_of_two(9);
            let rb = b.rem_euclid_power_of_two(9);
            let choice = tables.full9.digit_residue(ra, rb);
            a = a.sub(Signed192::from_i32(choice.0.0)).div_exact_power_of_two(9);
            b = b.sub(Signed192::from_i32(choice.0.1)).div_exact_power_of_two(9);
            choice.0
        } else {
            let (qa, signed_ra, ra) = a.div_rem_radix640_fast();
            let (qb, signed_rb, rb) = b.div_rem_radix640_fast();
            let atlas = if index == 13 { &tables.final640 } else { &tables.full640 };
            let choice = atlas.digit_residue(ra, rb);
            a = qa.adjust_small_radix_quotient(signed_ra, choice.0.0, 640);
            b = qb.adjust_small_radix_quotient(signed_rb, choice.0.1, 640);
            choice.0
        };
        for (bucket, coordinate) in [digit.0, digit.1].into_iter().enumerate() {
            if coordinate == 0 { continue; }
            let position = coordinate.unsigned_abs() as usize;
            assert!(position <= MIXED640_AXIAL_LIMITS[index]);
            let mut point = tables.windows[index][position];
            if coordinate < 0 { point.y = u256_sub(super::U256::ZERO, point.y); }
            buckets[bucket] = buckets[bucket].add_mixed(point);
            terms += 1;
        }
        debug_assert!(radix == 512 || radix == 640);
    }
    assert!(a.is_zero() && b.is_zero(), "mixed-radix axial recoding did not terminate");
    let point = buckets[0].add_xyzz(buckets[1].tau()).affine_hex_binary_inverse();
    (point, representative, terms.saturating_sub(1),
     tables.retained_bytes, fallback, corner, 0)
}

#[cfg(test)]
mod mixed640_axial_tests {
    use super::*;

    fn independent_binary_point(scalar: &BigInt) -> Jacobian {
        let (_, bytes) = scalar.to_bytes_be();
        let generator = Jacobian::generator().into_affine();
        let mut point = Jacobian::identity();
        for byte in bytes {
            for bit in (0..8).rev() {
                point = point.double();
                if (byte >> bit) & 1 != 0 { point = point.add_mixed(generator); }
            }
        }
        point
    }

    #[test]
    fn axial_holdout_matches_independent_binary() {
        let panel: serde_json::Value = serde_json::from_str(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"), "/src/bin/mixed640_bench_fixture.json"
        ))).unwrap();
        let cases = panel["cases"].as_array().unwrap();
        assert_eq!(cases.len(), 128);
        for (index, case) in cases.iter().enumerate() {
            let scalar = BigInt::parse_bytes(
                case["scalar_hex"].as_str().unwrap().as_bytes(), 16).unwrap();
            let words = super::super::scalar_words_256(&scalar).unwrap();
            let candidate = multiply_u256_tau_mixed640_axial(words);
            assert_eq!(candidate.0, case["point_hex"].as_str().unwrap(),
                       "fixture {index}");
            let reduced = &scalar % &SCALAR_LATTICE.n;
            assert_eq!(candidate.0, independent_binary_point(&reduced).affine_hex(),
                       "independent binary {index}");
        }
        println!("mixed640_axial_holdout_cases={} retained_bytes={}",
                 cases.len(), warm_mixed640_axial_table());
    }
}

"""


def main(target: Path) -> None:
    spec = importlib.util.spec_from_file_location("mixed640_bench_cli", BASE)
    bench = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(bench)
    bench.main("selective", target)
    target = target.resolve()
    module_path = target / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    module = replace_once(module_path.read_text(),
        "pub(super) fn warm_mixed640_pretau_table() -> usize {\n",
        AXIAL_RUST + "pub(super) fn warm_mixed640_pretau_table() -> usize {\n")
    module_path.write_text(module)
    front_path = target / "src/bin/eisenstein_fixed.rs"
    front = front_path.read_text()
    front = replace_once(front,
        "    let retained_bytes = unit_orbit_windows::warm_mixed640_pretau_table();\n",
        "    let retained_bytes = unit_orbit_windows::warm_mixed640_axial_table();\n")
    front = replace_once(front,
        "        unit_orbit_windows::multiply_u256_tau_mixed640_pretau_tree(\n",
        "        unit_orbit_windows::multiply_u256_tau_mixed640_axial(\n")
    front_path.write_text(front)
    receipt_path = target / "native-bench-overlay.json"
    receipt = json.loads(receipt_path.read_text())
    receipt.update({
        "variant": "mixed640_axial",
        "axial_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "generated_module_sha256": sha256(module_path.read_bytes()).hexdigest(),
        "generated_front_sha256": sha256(front_path.read_bytes()).hexdigest(),
    })
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: native_axial_bench.py TARGET_DIR")
    main(Path(sys.argv[1]))
