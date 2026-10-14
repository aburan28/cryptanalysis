#!/usr/bin/env python3
"""Generate the affine digit, three-bucket norm-4831 evaluator."""
from pathlib import Path
import importlib.util
import json
import sys
from hashlib import sha256

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'prime-j0-mixed640-materialized-tree-20261013' / 'native_split_prime_4831.py'

def main(target: Path):
    spec = importlib.util.spec_from_file_location('native_split_prime_4831', BASE)
    base = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(base)
    base.main(target)
    p = target / 'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    s = p.read_text()
    def once(a, b):
        nonlocal s
        assert s.count(a) == 1, (a[:70], s.count(a))
        s = s.replace(a, b, 1)
    once('digit_windows: Vec<Box<[U256TwoXAffine]>>', 'digit_windows: Vec<Box<[U256Affine]>>')
    once('fn split_prime_orbit_row(base: Jacobian, seeds: &[i16])\n    -> Box<[U256TwoXAffine]> {', 'fn split_prime_orbit_row(base: Jacobian, seeds: &[i16])\n    -> Box<[U256Affine]> {')
    once('        U256TwoXAffine::from_affine(point)\n    }).collect::<Vec<_>>().into_boxed_slice()\n}', '        point\n    }).collect::<Vec<_>>().into_boxed_slice()\n}')
    once('assert_eq!(entries, 16_120);\n        assert_eq!(size_of::<U256Affine>(), 64);\n        assert_eq!(size_of::<U256TwoXAffine>(), 96);', 'assert_eq!(entries, 16_120);\n        assert_eq!(size_of::<U256Affine>(), 64);')
    once('                * size_of::<U256TwoXAffine>()\n            + terminal_pairs.len()', '                * size_of::<U256Affine>()\n            + terminal_pairs.len()')
    once('digit_windows.capacity() * size_of::<Box<[U256TwoXAffine]>>()', 'digit_windows.capacity() * size_of::<Box<[U256Affine]>>()')
    old = '''    let mut bucket = U256XYZZ::identity();
        let mut terms = 0usize;
        for row in &tables.digit_windows {
            let (next_a, next_b, index, unit) = split_prime_unit_step(a, b, tables);
            a = next_a;
            b = next_b;
            if index != 0 {
                bucket = bucket.add_mixed(row[index].unit(unit));
                terms += 1;
            }
        }
    '''
    new = '''    let mut buckets = [U256XYZZ::identity(); 3];
        let mut terms = 0usize;
        let mut ops = SplitPrimeOpCounts::default();
        for row in &tables.digit_windows {
            let (next_a, next_b, index, unit) = split_prime_unit_step(a, b, tables);
            a = next_a;
            b = next_b;
            if index != 0 {
                let mut point = row[index];
                ops.digit_point_reads += 1;
                if unit & 1 != 0 {
                    point.y = u256_sub(super::U256::ZERO, point.y);
                    ops.sign_flips += 1;
                }
                if !buckets[unit / 2].is_identity() { ops.mixed_add_nontrivial += 1; }
                buckets[unit / 2] = buckets[unit / 2].add_mixed(point);
                terms += 1;
            }
        }
        let mut bucket = U256XYZZ::identity();
        for (power, part) in buckets.into_iter().enumerate() {
            if power != 0 && !part.is_identity() { ops.bucket_x_const_multiplies += 1; }
            if !bucket.is_identity() && !part.is_identity() {
                ops.projective_join_nontrivial += 1;
            }
            bucket = bucket.add_xyzz(part.rotate_power_solinas(power));
        }
    '''
    old = old.replace('\n    ', '\n')
    new = new.replace('\n    ', '\n')
    once(old, new)
    once('pub(super) fn multiply_u256_tau_split_prime_radix(', '''#[derive(Clone, Copy, Debug, Default)]
pub(super) struct SplitPrimeOpCounts {
    pub mixed_add_nontrivial: usize,
    pub projective_join_nontrivial: usize,
    pub bucket_x_const_multiplies: usize,
    pub digit_point_reads: usize,
    pub terminal_point_reads: usize,
    pub sign_flips: usize,
}

pub(super) fn multiply_u256_tau_split_prime_radix(''')
    once('pub(super) fn multiply_u256_tau_split_prime_radix(\n    scalar_words: [u64; 4],\n) -> (String, (Signed192, Signed192), usize, usize, bool, usize, usize) {',
         'pub(super) fn multiply_u256_tau_split_prime_radix(\n    scalar_words: [u64; 4],\n) -> (String, (Signed192, Signed192), usize, usize, bool, usize, usize, SplitPrimeOpCounts) {')
    once('''        if index != 0 {
            let mut point = tables.terminal_pairs[index];
            if negate { point.y = u256_sub(super::U256::ZERO, point.y); }
            bucket = bucket.add_mixed(point);
            terms += 1;
        }
    let point = bucket.affine_hex_binary_inverse();
    (point, representative, terms.saturating_sub(1),
     tables.retained_bytes, fallback, corner, 0)''',
         '''        if index != 0 {
            let mut point = tables.terminal_pairs[index];
            ops.terminal_point_reads += 1;
            if negate {
                point.y = u256_sub(super::U256::ZERO, point.y);
                ops.sign_flips += 1;
            }
            if !bucket.is_identity() { ops.mixed_add_nontrivial += 1; }
            bucket = bucket.add_mixed(point);
            terms += 1;
        }
    let point = bucket.affine_hex_binary_inverse();
    debug_assert!(ops.mixed_add_nontrivial + ops.projective_join_nontrivial
                  <= terms.saturating_sub(1));
    (point, representative,
     ops.mixed_add_nontrivial + ops.projective_join_nontrivial,
     tables.retained_bytes, fallback, corner, 0, ops)''')
    start = s.index('    #[test]\n    fn split_prime_digit_two_x_orbits_exhaustive()')
    end = s.index('    #[test]\n    fn split_prime_no_fallback_random_replay()', start)
    test = '''    #[test]
        fn split_prime_bucket_unit_images_exhaustive() {
            let tables = &*SPLIT_PRIME_TABLES;
            let mut checked = 0usize;
            for row in &tables.digit_windows {
                assert_eq!(row.len(), 806);
                for &entry in row.iter() {
                    let reference = U256OrbitXAffine::from_affine(entry);
                    for unit in 0..6 {
                        let mut actual = U256XYZZ::from_affine(entry)
                            .rotate_power_solinas(unit / 2);
                        if unit & 1 != 0 {
                            actual.y = u256_sub(super::super::U256::ZERO, actual.y);
                        }
                        let expected = reference.unit(unit);
                        assert_eq!(actual.x.0, expected.x.0);
                        assert_eq!(actual.y.0, expected.y.0);
                        checked += 1;
                    }
                }
            }
            assert_eq!(checked, 20 * 806 * 6);
            println!("bucket_digit_unit_images={checked}");
        }

    '''
    test = test.replace('\n    ', '\n')
    s = s[:start] + test + s[end:]
    p.write_text(s)
    front = target / 'src/bin/eisenstein_fixed.rs'
    front_source = front.read_text()
    front_anchor = '    let point = &answer.0;\n    assert_eq!(point, case["point_hex"].as_str().expect("expected point"));'
    assert front_source.count(front_anchor) == 1
    front_source = front_source.replace(front_anchor,
        front_anchor + '\n    let mixed_add_nontrivial = answer.7.mixed_add_nontrivial;'
        + '\n    let projective_join_nontrivial = answer.7.projective_join_nontrivial;'
        + '\n    let bucket_x_const_multiplies = answer.7.bucket_x_const_multiplies;'
        + '\n    let digit_point_reads = answer.7.digit_point_reads;'
        + '\n    let terminal_point_reads = answer.7.terminal_point_reads;'
        + '\n    let sign_flips = answer.7.sign_flips;')
    front_marker = 'retained_bytes={retained_bytes} case_id={case_index}'
    assert front_source.count(front_marker) == 1
    front_source = front_source.replace(front_marker,
        'retained_bytes={retained_bytes} mixed_add_nontrivial={mixed_add_nontrivial} projective_join_nontrivial={projective_join_nontrivial} bucket_x_const_multiplies={bucket_x_const_multiplies} digit_point_reads={digit_point_reads} terminal_point_reads={terminal_point_reads} sign_flips={sign_flips} case_id={case_index}')
    front.write_text(front_source)
    receipt_path = target / 'native-bench-overlay.json'
    receipt = json.loads(receipt_path.read_text())
    receipt['variant'] = 'split_prime_4831_three_bucket_affine_digit'
    receipt['three_bucket_overlay_sha256'] = sha256(Path(__file__).read_bytes()).hexdigest()
    receipt['generated_module_sha256'] = sha256(p.read_bytes()).hexdigest()
    receipt['generated_front_sha256'] = sha256(front.read_bytes()).hexdigest()
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: three_bucket_overlay.py TARGET_DIR')
    main(Path(sys.argv[1]))
