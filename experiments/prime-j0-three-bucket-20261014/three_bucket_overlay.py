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
        for row in &tables.digit_windows {
            let (next_a, next_b, index, unit) = split_prime_unit_step(a, b, tables);
            a = next_a;
            b = next_b;
            if index != 0 {
                let mut point = row[index];
                if unit & 1 != 0 { point.y = u256_sub(super::U256::ZERO, point.y); }
                buckets[unit / 2] = buckets[unit / 2].add_mixed(point);
                terms += 1;
            }
        }
        let mut bucket = U256XYZZ::identity();
        for (power, part) in buckets.into_iter().enumerate() {
            bucket = bucket.add_xyzz(part.rotate_power_solinas(power));
        }
    '''
    old = old.replace('\n    ', '\n')
    new = new.replace('\n    ', '\n')
    once(old, new)
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
    receipt_path = target / 'native-bench-overlay.json'
    receipt = json.loads(receipt_path.read_text())
    receipt['variant'] = 'split_prime_4831_three_bucket_affine_digit'
    receipt['three_bucket_overlay_sha256'] = sha256(Path(__file__).read_bytes()).hexdigest()
    receipt['generated_module_sha256'] = sha256(p.read_bytes()).hexdigest()
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: three_bucket_overlay.py TARGET_DIR')
    main(Path(sys.argv[1]))
