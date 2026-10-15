#!/usr/bin/env python3
"""Transform the checked norm-53593 native source into radix 190-tau."""
from hashlib import sha256
from pathlib import Path
import sys

PARENT_SHA256 = '59e5a2f2e381cd91577940e5a784d2e72d81e91a9fdec2969f2065b1e0e1226c'


def once(source, old, new):
    assert source.count(old) == 1, (old[:70], source.count(old))
    return source.replace(old, new)


def splice(source, start, end, new):
    i = source.index(start)
    j = source.index(end, i)
    return source[:i] + new + source[j:]


def main(root):
    path = root / 'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    original = path.read_text()
    assert sha256(original.encode()).hexdigest() == PARENT_SHA256
    start = original.index('const SPLIT_PRIME_NORM: i32 = 53593;')
    end = original.index('\npub(super) fn warm_mixed640_pretau_table()', start)
    section = original[start:end]
    for old, new in [
        ('const SPLIT_PRIME_NORM: i32 = 53593;', 'const SPLIT_PRIME_NORM: i32 = 35533;'),
        ('const SPLIT_PRIME_TAU_RESIDUE: i32 = 233;', 'const SPLIT_PRIME_TAU_RESIDUE: i32 = 190;'),
        ('const SPLIT_PRIME_DIGIT_LIMIT: usize = 26796;', 'const SPLIT_PRIME_DIGIT_LIMIT: usize = 17766;'),
        ('const SPLIT_PRIME_TERMINAL_LIMIT: usize = 7;', 'const SPLIT_PRIME_TERMINAL_LIMIT: usize = 155;'),
        ('(463*lift+53593).div_euclid(107186)', '(377*lift+35533).div_euclid(71066)'),
        ('let a = lift-233*b;', 'let a = lift-190*b;'),
        ('k.times_split_prime_small(230)', 'k.times_split_prime_small(187)'),
        ('affine_multiples(base, 233)', 'affine_multiples(base, 190)'),
        ('assert_eq!(digit_pairs.len(), 26797);', 'assert_eq!(digit_pairs.len(), 17767);'),
        ('assert_eq!(max_norm, 17787);', 'assert_eq!(max_norm, 11719);'),
        ('assert_eq!(digit_seeds.len(),8933);', 'assert_eq!(digit_seeds.len(),5923);'),
        ('assert_eq!(entries, 16*8933);', 'assert_eq!(entries, 16*5923);'),
        ('radix_53593', 'radix_35533'),
        ('for residue in 0..SPLIT_PRIME_NORM {', 'for residue in 0..SPLIT_PRIME_NORM {'),
    ]:
        if old == 'affine_multiples(base, 233)':
            assert section.count(old) == 1
            section = section.replace(old, new)
        elif old == 'radix_53593':
            assert section.count(old) >= 2
            section = section.replace(old, new)
        elif old == 'for residue in 0..SPLIT_PRIME_NORM {':
            continue
        else:
            section = once(section, old, new)
    section = once(section, '''        let mut terminal_pairs_full = Vec::new();
        for a in -7..=7i32 {
            for b in -7..=7i32 {
                let norm = a*a+3*a*b+3*b*b;
                if norm < 16 { terminal_pairs_full.push((a as i16,b as i16)); }
            }
        }
        assert_eq!(terminal_pairs_full.len(),55);''', '''        let mut terminal_pairs_full = Vec::new();
        for a in -155..=155i32 {
            for b in -155..=155i32 {
                let norm = a*a+3*a*b+3*b*b;
                if norm < 6084 { terminal_pairs_full.push((a as i16,b as i16)); }
            }
        }
        assert_eq!(terminal_pairs_full.len(),22057);''')
    section = once(section, 'assert_eq!(terminal_seeds.len(),10);',
                   'assert_eq!(terminal_seeds.len(),3677);')
    section = once(section, '''        let terminal_codes = terminal_pairs_full.iter().copied().map(|pair| {
            let seed = orbit_canonical(pair);
            (terminal_ids[&seed],orbit_code(pair,seed))
        }).collect::<Vec<_>>().into_boxed_slice();''', '''        let mut terminal_codes = vec![(u16::MAX,0u8);311*311];
        for pair in terminal_pairs_full.iter().copied() {
            let seed = orbit_canonical(pair);
            let index = ((i32::from(pair.0)+155)*311+i32::from(pair.1)+155) as usize;
            terminal_codes[index]=(terminal_ids[&seed],orbit_code(pair,seed));
        }
        let terminal_codes=terminal_codes.into_boxed_slice();''')
    section = splice(section, '''    assert!(terminal_norm < 16,"nearest-digit norm-53593 terminal bound");''',
                     '\n    let mut bucket=U256XYZZ::identity();', '''    assert!(terminal_norm < 6084,"nearest-digit norm-35533 terminal bound");
    if signed_a != 0 || signed_b != 0 {
        let index = ((signed_a+155)*311+signed_b+155) as usize;
        let (seed,code)=tables.terminal_codes[index];
        assert_ne!(seed,u16::MAX);
        choices[SPLIT_PRIME_STEPS]=(usize::from(seed),usize::from(code));
    }
''')
    section = section.replace('53593','35533').replace('17787','11719')
    # The section's test prints and congruence checks contain explicit T/Q.
    section = section.replace('a+233*b-residue','a+190*b-residue')
    original = original[:start] + section + original[end:]
    path.write_text(original)
    print(sha256(path.read_bytes()).hexdigest())


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: native190_overlay.py CARGO_ROOT')
    main(Path(sys.argv[1]))
