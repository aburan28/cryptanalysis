#!/usr/bin/env python3
"""Fuse the smaller rotated unit bucket into bucket zero per scalar."""

from hashlib import sha256
import json
from pathlib import Path
import sys

MODULE_SHA256 = "c0ab21bcc6975c2d1b823cc8f800ca78e8d2a84757db1846729f0b4f3889b512"
FRONT_SHA256 = "814042f0ab527b43c4813a2f71dbbc81cafeaad3bbaf5f436c119cef9262ee19"


def main(root: Path) -> None:
    module = root / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    front = root / "src/bin/eisenstein_fixed.rs"
    source = module.read_text()
    front_source = front.read_text()
    assert sha256(source.encode()).hexdigest() == MODULE_SHA256
    assert sha256(front_source.encode()).hexdigest() == FRONT_SHA256

    old = "    pub bucket_x_const_multiplies: usize,\n"
    assert source.count(old) == 1
    source = source.replace(old, old + "    pub point_x_const_multiplies: usize,\n    pub fused_bucket: usize,\n", 1)
    anchor = "pub(super) fn multiply_u256_tau_split_prime_radix(\n"
    assert source.count(anchor) == 1
    helper = """fn split_prime_add_fused_point(
    buckets: &mut [U256XYZZ; 3], ops: &mut SplitPrimeOpCounts,
    mut point: U256Affine, unit: usize, negate: bool, fused: usize,
) {
    assert!(unit < 6 && (fused == 1 || fused == 2));
    if (unit & 1 != 0) != negate {
        point.y = u256_sub(super::U256::ZERO, point.y);
        ops.sign_flips += 1;
    }
    let group = unit / 2;
    let destination = if group == fused {
        point.x = u256_mul_const_solinas(point.x, U256_BETA_CANONICAL[fused]);
        ops.point_x_const_multiplies += 1;
        0
    } else { group };
    if !buckets[destination].is_identity() { ops.mixed_add_nontrivial += 1; }
    buckets[destination] = buckets[destination].add_mixed(point);
}

"""
    source = source.replace(anchor, helper + anchor, 1)

    func_start = source.index(anchor)
    start = source.index("    let mut buckets = [U256XYZZ::identity(); 3];", func_start)
    end_anchor = "    let point = bucket.affine_hex_binary_inverse();\n"
    end = source.index(end_anchor, start) + len(end_anchor)
    source = source[:start] + """    // Recode before group addition so the smaller rotated bucket can be fused.
    let mut digit_codes = [(0usize, 0usize); SPLIT_PRIME_STEPS];
    let mut group_counts = [0usize; 3];
    for slot in 0..SPLIT_PRIME_STEPS {
        let (next_a, next_b, index, unit) = split_prime_unit_step(a, b, tables);
        a = next_a;
        b = next_b;
        digit_codes[slot] = (index, unit);
        if index != 0 { group_counts[unit / 2] += 1; }
    }
    let (ai, aneg) = a.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);
    let (bi, bneg) = b.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);
    let signed_a = if aneg { -(ai as i64) } else { ai as i64 };
    let signed_b = if bneg { -(bi as i64) } else { bi as i64 };
    let terminal_norm = signed_a*signed_a + 3*signed_a*signed_b
        + 3*signed_b*signed_b;
    assert!(terminal_norm < 4900, "norm-12211 terminal bound");
    let negate = signed_a < 0 || (signed_a == 0 && signed_b < 0);
    let ca = if negate { -signed_a } else { signed_a } as usize;
    let cb = if negate { -signed_b } else { signed_b };
    let row_start = tables.terminal_row_start[ca] as usize;
    let row_offset = usize::try_from(
        cb - i64::from(tables.terminal_row_min[ca])).unwrap();
    let index = row_start + row_offset;
    assert!(index < tables.terminal_row_start[ca + 1] as usize);
    let code = usize::from(tables.terminal_codes[index]);
    let orbit = code / 6;
    let terminal_unit = code % 6;
    if orbit != 0 { group_counts[terminal_unit / 2] += 1; }
    let fused = if group_counts[1] <= group_counts[2] { 1 } else { 2 };

    let mut buckets = [U256XYZZ::identity(); 3];
    let mut terms = 0usize;
    let mut ops = SplitPrimeOpCounts::default();
    ops.fused_bucket = fused;
    for (slot, row) in tables.digit_windows.iter().enumerate() {
        let (digit_index, unit) = digit_codes[slot];
        if digit_index != 0 {
            ops.digit_point_reads += 1;
            split_prime_add_fused_point(
                &mut buckets, &mut ops, row[digit_index], unit, false, fused);
            terms += 1;
        }
    }
    if orbit != 0 {
        ops.terminal_point_reads += 1;
        split_prime_add_fused_point(
            &mut buckets, &mut ops, tables.terminal_orbits[orbit],
            terminal_unit, negate, fused);
        terms += 1;
    }
    debug_assert!(buckets[fused].is_identity());
    let mut bucket = U256XYZZ::identity();
    for (power, part) in buckets.into_iter().enumerate() {
        if power != 0 && !part.is_identity() { ops.bucket_x_const_multiplies += 1; }
        if !bucket.is_identity() && !part.is_identity() {
            ops.projective_join_nontrivial += 1;
        }
        bucket = bucket.add_xyzz(part.rotate_power_solinas(power));
    }
    let point = bucket.affine_hex_binary_inverse();
""" + source[end:]

    anchor = "                    let expected = reference.unit(unit);\n"
    assert source.count(anchor) >= 1
    pos = source.index(anchor, source.index("fn split_prime_bucket_unit_images_exhaustive"))
    insert = """                    let mut direct = entry;
                    direct.x = u256_mul_const_solinas(
                        direct.x, U256_BETA_CANONICAL[unit / 2]);
                    if unit & 1 != 0 {
                        direct.y = u256_sub(super::super::U256::ZERO, direct.y);
                    }
                    assert_eq!(direct.x.0, expected.x.0);
                    assert_eq!(direct.y.0, expected.y.0);
"""
    # Place the independent affine rotation check after expected is bound.
    source = source[:pos+len(anchor)] + insert + source[pos+len(anchor):]
    module.write_text(source)

    old = "    let bucket_x_const_multiplies = answer.7.bucket_x_const_multiplies;\n"
    assert front_source.count(old) == 1
    front_source = front_source.replace(old, old + "    let point_x_const_multiplies = answer.7.point_x_const_multiplies;\n    let fused_bucket = answer.7.fused_bucket;\n", 1)
    old = "bucket_x_const_multiplies={bucket_x_const_multiplies} digit_point_reads="
    assert front_source.count(old) == 1
    front_source = front_source.replace(old,
        "bucket_x_const_multiplies={bucket_x_const_multiplies} point_x_const_multiplies={point_x_const_multiplies} fused_bucket={fused_bucket} digit_point_reads=", 1)
    front.write_text(front_source)

    receipt = root / "native-bench-overlay.json"
    metadata = json.loads(receipt.read_text())
    metadata.update({
        "variant": "split_prime_12211_adaptive_two_bucket_fusion",
        "adaptive_fusion_overlay_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "generated_module_sha256": sha256(module.read_bytes()).hexdigest(),
        "generated_front_sha256": sha256(front.read_bytes()).hexdigest(),
    })
    receipt.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"variant": metadata["variant"],
                      "generated_module_sha256": metadata["generated_module_sha256"]}))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: native_overlay.py GENERATED_NORM12211_CARGO_DIR")
    main(Path(sys.argv[1]))
