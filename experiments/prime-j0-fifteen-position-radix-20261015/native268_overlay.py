#!/usr/bin/env python3
"""Turn the frozen norm-19183 batch source into the 15-position 268-tau candidate."""
from hashlib import sha256
from pathlib import Path
import sys

PARENT_SHA256 = 'e195374c4e6fde368bdba106c769c6335cd319f9f5547e8e2291089fe055335e'


def once(source, old, new):
    assert source.count(old) == 1, (old[:80],source.count(old))
    return source.replace(old,new)


def main(root):
    path = root / 'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    original = path.read_text()
    assert sha256(original.encode()).hexdigest() == PARENT_SHA256
    start = original.index('const SPLIT_PRIME_NORM: i32 = 19183;')
    end = original.index('\npub(super) fn warm_mixed640_pretau_table()',start)
    section = original[start:end]
    changes = (
        ('const SPLIT_PRIME_NORM: i32 = 19183;',
         'const SPLIT_PRIME_NORM: i32 = 71023;'),
        ('const SPLIT_PRIME_TAU_RESIDUE: i32 = 140;',
         'const SPLIT_PRIME_TAU_RESIDUE: i32 = 268;'),
        ('const SPLIT_PRIME_STEPS: usize = 17;',
         'const SPLIT_PRIME_STEPS: usize = 15;'),
        ('const SPLIT_PRIME_DIGIT_LIMIT: usize = 9591;',
         'const SPLIT_PRIME_DIGIT_LIMIT: usize = 35511;'),
        ('const SPLIT_PRIME_TERMINAL_LIMIT: usize = 155;',
         'const SPLIT_PRIME_TERMINAL_LIMIT: usize = 163;'),
        ('(277*lift+19183).div_euclid(38366)',
         '(533*lift+71023).div_euclid(142046)'),
        ('let a = lift-140*b;', 'let a = lift-268*b;'),
        ('k.times_split_prime_small(137)', 'k.times_split_prime_small(265)'),
        ('assert_eq!(digit_pairs.len(), 9592);',
         'assert_eq!(digit_pairs.len(), 35512);'),
        ('assert_eq!(max_norm, 6348);', 'assert_eq!(max_norm, 23497);'),
        ('assert_eq!(digit_seeds.len(),3198);',
         'assert_eq!(digit_seeds.len(),11838);'),
        ('affine_multiples(base, 140)', 'affine_multiples(base, 268)'),
        ('for a in -155..=155i32 {', 'for a in -163..=163i32 {'),
        ('for b in -155..=155i32 {', 'for b in -163..=163i32 {'),
        ('if norm < 6084 { terminal_pairs_full.push',
         'if norm < 6724 { terminal_pairs_full.push'),
        ('assert_eq!(terminal_pairs_full.len(),22057);',
         'assert_eq!(terminal_pairs_full.len(),24373);'),
        ('assert_eq!(terminal_seeds.len(),3677);',
         'assert_eq!(terminal_seeds.len(),4063);'),
        ('vec![(u16::MAX,0u8);311*311]',
         'vec![(u16::MAX,0u8);327*327]'),
        ('((i32::from(pair.0)+155)*311+i32::from(pair.1)+155)',
         '((i32::from(pair.0)+163)*327+i32::from(pair.1)+163)'),
        ('assert_eq!(entries, 17*3198);',
         'assert_eq!(entries, 15*11838);'),
        ('assert!(terminal_norm < 6084', 'assert!(terminal_norm < 6724'),
        ('((signed_a+155)*311+signed_b+155)',
         '((signed_a+163)*327+signed_b+163)'),
        ('nearest-digit norm-19183 terminal bound',
         'nearest-digit norm-71023 terminal bound'),
        ('assert_eq!((a+140*b-residue).rem_euclid(19183),0);',
         'assert_eq!((a+268*b-residue).rem_euclid(71023),0);'),
        ('assert!(a*a+3*a*b+3*b*b <= 6348);',
         'assert!(a*a+3*a*b+3*b*b <= 23497);'),
    )
    for old,new in changes:
        section = once(section,old,new)
    assert section.count('radix_19183') == 4
    section = section.replace('radix_19183','radix_71023')
    output = original[:start]+section+original[end:]
    path.write_text(output)
    print(sha256(output.encode()).hexdigest())


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: native268_overlay.py CARGO_ROOT')
    main(Path(sys.argv[1]))
