#!/usr/bin/env python3
"""Replace the generated three-bucket evaluator with the adaptive schedule."""

from hashlib import sha256
import json
from pathlib import Path
import sys

from adaptive_schedule import best_schedule


HERE = Path(__file__).resolve().parent


def plan_byte(counts):
    schedule, cost = best_schedule(counts)
    assert cost["projective_joins"] <= 1
    groups = [0, 0, 0]
    anchors = [0, 0]
    for group, (members, anchor) in enumerate(schedule.groups):
        for member in members:
            groups[member] = group
        anchors[group] = anchor
    return sum(groups[c] << c for c in range(3)) | (anchors[0] << 3) | (anchors[1] << 5)


def plan_table():
    entries = []
    for n in range(21):
        for n0 in range(n + 1):
            for n1 in range(n - n0 + 1):
                offset = (n * (n + 1) * (n + 2) // 6
                          + n0 * (n + 1) - n0 * max(n0 - 1, 0) // 2 + n1)
                assert offset == len(entries)
                entries.append(plan_byte((n0, n1, n - n0 - n1)))
    assert len(entries) == 1771
    return entries


def main(root: Path):
    module = root / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    front = root / "src/bin/eisenstein_fixed.rs"
    source = module.read_text()
    marker = "pub(super) fn multiply_u256_tau_split_prime_radix("
    assert source.count(marker) == 1
    start = source.index(marker)
    stop = source.index("    // The fused table covers the small terminal norm.", start)
    old = source[start:stop]
    assert "let mut buckets = [U256XYZZ::identity(); 3];" in old
    entries = plan_table()
    lut = "const SPLIT_PRIME_ADAPTIVE_PLANS: [u8; 1771] = [\n"
    for offset in range(0, len(entries), 32):
        lut += "    " + ", ".join(str(value) for value in entries[offset:offset + 32]) + ",\n"
    lut += "];\n\n"
    replacement = '''pub(super) fn multiply_u256_tau_split_prime_radix(
    scalar_words: [u64; 4],
) -> (String, (Signed192, Signed192), usize, usize, bool, usize, usize, SplitPrimeOpCounts) {
    let scalar = super::Uint(scalar_words);
    let residue = if bool::from(scalar.ct_lt(&super::SCALAR_ORDER_WORDS)) {
        scalar
    } else {
        super::U256::sbb(&scalar, &super::SCALAR_ORDER_WORDS).0
    };
    let (representative, fallback, corner) =
        super::hexagonal_certified_fixed_choice_words(residue.0);
    let tables = &*SPLIT_PRIME_TABLES;
    let (mut a, mut b) = representative;
    let mut selected = [(0usize, 0usize); SPLIT_PRIME_STEPS];
    let mut counts = [0usize; 3];
    for (slot, _) in selected.iter_mut().zip(&tables.digit_windows) {
        let (next_a, next_b, index, unit) = split_prime_unit_step(a, b, tables);
        a = next_a;
        b = next_b;
        *slot = (index, unit);
        if index != 0 { counts[unit / 2] += 1; }
    }
    let n = counts.iter().sum::<usize>();
    let n0 = counts[0];
    let n1 = counts[1];
    let plan_index = n * (n + 1) * (n + 2) / 6
        + n0 * (n + 1) - n0 * n0.saturating_sub(1) / 2 + n1;
    let plan = SPLIT_PRIME_ADAPTIVE_PLANS[plan_index] as usize;
    let anchors = [(plan >> 3) & 3, (plan >> 5) & 3];
    let mut buckets = [U256XYZZ::identity(); 2];
    let mut terms = 0usize;
    let mut ops = SplitPrimeOpCounts::default();
    for ((index, unit), row) in selected.into_iter().zip(&tables.digit_windows) {
        if index == 0 { continue; }
        let power = unit / 2;
        let group = (plan >> power) & 1;
        let relative = (power + 3 - anchors[group]) % 3;
        let point = row[index].unit_solinas(2 * relative + (unit & 1));
        ops.digit_point_reads += 1;
        if relative != 0 { ops.digit_x_const_multiplies += 1; }
        if unit & 1 != 0 { ops.sign_flips += 1; }
        if !buckets[group].is_identity() { ops.mixed_add_nontrivial += 1; }
        buckets[group] = buckets[group].add_mixed(point);
        terms += 1;
    }
    let mut bucket = U256XYZZ::identity();
    for (group, part) in buckets.into_iter().enumerate() {
        if anchors[group] != 0 && !part.is_identity() {
            ops.bucket_x_const_multiplies += 1;
        }
        if !bucket.is_identity() && !part.is_identity() {
            ops.projective_join_nontrivial += 1;
        }
        bucket = bucket.add_xyzz(part.rotate_power_solinas(anchors[group]));
    }
'''
    source = source[:start] + replacement + source[stop:]
    anchor = "    pub bucket_x_const_multiplies: usize,\n"
    assert source.count(anchor) == 1
    source = source.replace(anchor, anchor + "    pub digit_x_const_multiplies: usize,\n")
    assert source.count("     tables.retained_bytes, fallback, corner, 0, ops)") == 1
    source = source.replace("     tables.retained_bytes, fallback, corner, 0, ops)",
                            "     tables.retained_bytes + SPLIT_PRIME_ADAPTIVE_PLANS.len(),\n"
                            "     fallback, corner, 0, ops)")
    anchor = "    SPLIT_PRIME_TABLES.retained_bytes\n}"
    assert source.count(anchor) == 1
    source = source.replace(anchor,
                            "    SPLIT_PRIME_TABLES.retained_bytes + SPLIT_PRIME_ADAPTIVE_PLANS.len()\n}")
    source = source[:source.index(marker)] + lut + source[source.index(marker):]
    module.write_text(source)
    front_source = front.read_text()
    marker = "    let bucket_x_const_multiplies = answer.7.bucket_x_const_multiplies;"
    assert front_source.count(marker) == 1
    front_source = front_source.replace(marker, marker +
                                        "\n    let digit_x_const_multiplies = answer.7.digit_x_const_multiplies;")
    marker = " bucket_x_const_multiplies={bucket_x_const_multiplies}"
    assert front_source.count(marker) == 1
    front_source = front_source.replace(marker, marker +
        " digit_x_const_multiplies={digit_x_const_multiplies}")
    front.write_text(front_source)
    receipt = {"variant": "split_prime_4831_adaptive_unit_partition",
               "parent_function_region_sha256": sha256(old.encode()).hexdigest(),
               "adaptive_overlay_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
               "plan_entries": len(entries),
               "plan_sha256": sha256(bytes(entries)).hexdigest(),
               "generated_module_sha256": sha256(module.read_bytes()).hexdigest(),
               "generated_front_sha256": sha256(front.read_bytes()).hexdigest()}
    (root / "adaptive-overlay.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: adaptive_overlay.py THREE_BUCKET_GENERATED_CRATE")
    main(Path(sys.argv[1]))
