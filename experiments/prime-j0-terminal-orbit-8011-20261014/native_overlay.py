#!/usr/bin/env python3
"""Fold the norm-8011 terminal ball by its six Eisenstein units."""

from hashlib import sha256
import json
from pathlib import Path
import sys

SOURCE_SHA256 = "4e55ee73ed2aa2254eecf63bd2bb6f034c655c56320d53cb2a4eaa7439c01783"


def main(root: Path) -> None:
    path = root / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    source = path.read_text()
    assert sha256(source.encode()).hexdigest() == SOURCE_SHA256

    def replace_once(old: str, new: str) -> None:
        nonlocal source
        assert source.count(old) == 1, (old[:80], source.count(old))
        source = source.replace(old, new, 1)

    replace_once("    terminal_pairs: Box<[U256Affine]>,", "    terminal_orbits: Box<[U256Affine]>,\n    terminal_codes: Box<[u16]>,")
    replace_once("        let terminal_pairs = build_u256_window(&pair_digits, base);", """        // Each nonzero norm-bounded point has six unit images, three of
        // which are sign-canonical. Store one affine point per full orbit.
        let sign_canonical = |(a, b): (i32, i32)| a > 0 || (a == 0 && b >= 0);
        let mut orbit_seeds = Vec::new();
        for &(a, b) in &pair_digits {
            let pair = (i32::from(a), i32::from(b));
            let canonical = unit_images(pair).into_iter()
                .filter(|&image| sign_canonical(image)).min().unwrap();
            if canonical == pair { orbit_seeds.push((a, b)); }
        }
        assert_eq!(orbit_seeds.len(), 1280);
        let mut orbit_lookup = std::collections::BTreeMap::new();
        for (index, &(a, b)) in orbit_seeds.iter().enumerate() {
            for (unit, image) in unit_images((i32::from(a), i32::from(b)))
                .into_iter().enumerate() {
                if sign_canonical(image) {
                    let code = u16::try_from(index * 6 + unit).unwrap();
                    if image == (0, 0) {
                        orbit_lookup.entry(image).or_insert(code);
                    } else {
                        assert!(orbit_lookup.insert(image, code).is_none());
                    }
                }
            }
        }
        assert_eq!(orbit_lookup.len(), pair_digits.len());
        let terminal_codes = pair_digits.iter().map(|&(a, b)| {
            orbit_lookup[&(i32::from(a), i32::from(b))]
        }).collect::<Vec<_>>().into_boxed_slice();
        let terminal_orbits = build_u256_window(&orbit_seeds, base);""")
    replace_once("            + terminal_pairs.len() * size_of::<U256Affine>()", "            + terminal_orbits.len() * size_of::<U256Affine>()\n            + terminal_codes.len() * size_of::<u16>()")
    replace_once("               terminal_pairs,\n               terminal_row_start", "               terminal_orbits, terminal_codes,\n               terminal_row_start")

    start = source.index("    let mut bucket = U256XYZZ::identity();\n    for (power, part) in buckets.into_iter().enumerate() {", source.index("pub(super) fn multiply_u256_tau_split_prime_radix"))
    end = source.index("    debug_assert!(ops.mixed_add_nontrivial", start)
    source = source[:start] + """    // Fold the terminal point into the same three unit buckets as the digits.
    let (ai, aneg) = a.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);
    let (bi, bneg) = b.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);
    let signed_a = if aneg { -(ai as i64) } else { ai as i64 };
    let signed_b = if bneg { -(bi as i64) } else { bi as i64 };
    let terminal_norm = signed_a*signed_a + 3*signed_a*signed_b
        + 3*signed_b*signed_b;
    assert!(terminal_norm < 2116, "norm-8011 terminal bound");
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
    let unit = code % 6;
    if orbit != 0 {
        let mut point = tables.terminal_orbits[orbit];
        ops.terminal_point_reads += 1;
        if (unit & 1 != 0) != negate {
            point.y = u256_sub(super::U256::ZERO, point.y);
            ops.sign_flips += 1;
        }
        if !buckets[unit / 2].is_identity() { ops.mixed_add_nontrivial += 1; }
        buckets[unit / 2] = buckets[unit / 2].add_mixed(point);
        terms += 1;
    }
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

    replace_once("        assert_eq!(tables.terminal_pairs.len(), count);", """        assert_eq!(tables.terminal_codes.len(), count);
        assert_eq!(tables.terminal_orbits.len(), 1280);
        let mut seeds = Vec::new();
        for a in 0..92i32 {
            for b in -54..=54i32 {
                let pair = (a, b);
                if norm(pair) >= 2116 || (a == 0 && b < 0) { continue; }
                let canonical = unit_images(pair).into_iter()
                    .filter(|&(x, y)| x > 0 || (x == 0 && y >= 0)).min().unwrap();
                if canonical == pair { seeds.push(pair); }
            }
        }
        assert_eq!(seeds.len(), 1280);
        for a in 0..92i32 {
            for b in -54..=54i32 {
                let pair = (a, b);
                if norm(pair) >= 2116 || (a == 0 && b < 0) { continue; }
                let row = tables.terminal_row_start[a as usize] as usize;
                let offset = usize::try_from(b - i32::from(tables.terminal_row_min[a as usize])).unwrap();
                let code = usize::from(tables.terminal_codes[row + offset]);
                assert_eq!(unit_images(seeds[code / 6])[code % 6], pair);
            }
        }""")
    path.write_text(source)
    receipt = root / "native-bench-overlay.json"
    metadata = json.loads(receipt.read_text())
    metadata.update({
        "variant": "split_prime_8011_three_bucket_terminal_orbit",
        "terminal_orbit_overlay_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "generated_module_sha256": sha256(path.read_bytes()).hexdigest(),
    })
    receipt.write_text(json.dumps(metadata, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"variant": metadata["variant"],
                      "generated_module_sha256": metadata["generated_module_sha256"]}))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: native_overlay.py GENERATED_NORM8011_CARGO_DIR")
    main(Path(sys.argv[1]))
