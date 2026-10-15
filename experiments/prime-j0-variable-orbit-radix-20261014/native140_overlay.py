#!/usr/bin/env python3
"""Turn the frozen norm-35533 batch source into the 17-position 140-tau candidate."""
from hashlib import sha256
from pathlib import Path
import sys

PARENT_SHA256 = '858089fac6083f123c4a9e86afe9cef9db9d24dfdc78df3546d4bed74165e52e'


def once(source, old, new):
    assert source.count(old) == 1, (old[:80], source.count(old))
    return source.replace(old, new)


def main(root):
    path = root / 'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    original = path.read_text()
    assert sha256(original.encode()).hexdigest() == PARENT_SHA256
    start = original.index('const SPLIT_PRIME_NORM: i32 = 35533;')
    end = original.index('\npub(super) fn warm_mixed640_pretau_table()', start)
    section = original[start:end]
    changes = (
        ('const SPLIT_PRIME_NORM: i32 = 35533;', 'const SPLIT_PRIME_NORM: i32 = 19183;'),
        ('const SPLIT_PRIME_TAU_RESIDUE: i32 = 190;', 'const SPLIT_PRIME_TAU_RESIDUE: i32 = 140;'),
        ('const SPLIT_PRIME_STEPS: usize = 16;', 'const SPLIT_PRIME_STEPS: usize = 17;'),
        ('const SPLIT_PRIME_DIGIT_LIMIT: usize = 17766;', 'const SPLIT_PRIME_DIGIT_LIMIT: usize = 9591;'),
        ('(377*lift+35533).div_euclid(71066)', '(277*lift+19183).div_euclid(38366)'),
        ('let a = lift-190*b;', 'let a = lift-140*b;'),
        ('k.times_split_prime_small(187)', 'k.times_split_prime_small(137)'),
        ('assert_eq!(digit_pairs.len(), 17767);', 'assert_eq!(digit_pairs.len(), 9592);'),
        ('assert_eq!(max_norm, 11719);', 'assert_eq!(max_norm, 6348);'),
        ('assert_eq!(digit_seeds.len(),5923);', 'assert_eq!(digit_seeds.len(),3198);'),
        ('affine_multiples(base, 190)', 'affine_multiples(base, 140)'),
        ('assert_eq!(entries, 16*5923);', 'assert_eq!(entries, 17*3198);'),
        ('nearest-digit norm-35533 terminal bound', 'nearest-digit norm-19183 terminal bound'),
        ('assert_eq!((a+190*b-residue).rem_euclid(35533),0);',
         'assert_eq!((a+140*b-residue).rem_euclid(19183),0);'),
        ('assert!(a*a+3*a*b+3*b*b <= 11719);',
         'assert!(a*a+3*a*b+3*b*b <= 6348);'),
    )
    for old, new in changes:
        section = once(section, old, new)
    assert section.count('radix_35533') == 4
    section = section.replace('radix_35533', 'radix_19183')
    output = original[:start] + section + original[end:]
    path.write_text(output)
    print(sha256(output.encode()).hexdigest())


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: native140_overlay.py CARGO_ROOT')
    main(Path(sys.argv[1]))
