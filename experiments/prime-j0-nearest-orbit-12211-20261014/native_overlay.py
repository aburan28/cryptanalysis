#!/usr/bin/env python3
"""Fold the checked nearest-digit native table by six Eisenstein units."""
from hashlib import sha256
from pathlib import Path
import sys

PARENT_SHA256 = '24a86874bc6e573d801a4326b1053f72698621a6cad699a0bdd91c5c054876b9'


def replace_once(source, old, new):
    assert source.count(old) == 1, (old[:60], source.count(old))
    return source.replace(old, new)


def splice(source, first, last, replacement):
    start = source.index(first)
    end = source.index(last, start)
    return source[:start] + replacement + source[end:]


def main(root):
    path = root/'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    source = path.read_text()
    assert sha256(source.encode()).hexdigest() == PARENT_SHA256
    source = splice(source, 'struct SplitPrimeTables {',
                    '\nstatic SPLIT_PRIME_TABLES: LazyLock<SplitPrimeTables> =', '''fn orbit_omega_pair((a,b): (i16,i16)) -> (i16,i16) {
    let (a,b) = (i32::from(a),i32::from(b));
    ((a+3*b).try_into().unwrap(),(-a-2*b).try_into().unwrap())
}

fn orbit_canonical(pair: (i16,i16)) -> (i16,i16) {
    let mut best = pair;
    let mut value = pair;
    for _ in 0..3 {
        best = best.min(value).min((-value.0,-value.1));
        value = orbit_omega_pair(value);
    }
    best
}

fn orbit_code(pair: (i16,i16), seed: (i16,i16)) -> u8 {
    let mut value = seed;
    for power in 0..3u8 {
        if value == pair { return 2*power; }
        if (-value.0,-value.1) == pair { return 2*power+1; }
        value = orbit_omega_pair(value);
    }
    panic!("pair absent from orbit");
}

fn orbit_affine(mut point: U256Affine, code: usize) -> U256Affine {
    assert!(code < 6);
    if code / 2 != 0 {
        point.x = u256_mul(point.x, U256_BETA_UNITS[code/2]);
    }
    if code & 1 != 0 {
        point.y = u256_sub(super::U256::ZERO, point.y);
    }
    point
}

struct SplitPrimeTables {
    digit_pairs: Box<[(i16, i16)]>,
    digit_codes: Box<[(u16, u8)]>,
    digit_windows: Vec<Box<[U256Affine]>>,
    terminal_pairs: Box<[U256Affine]>,
    terminal_codes: Box<[(u16,u8)]>,
    terminal_row_start: [u16; 69],
    terminal_row_min: [i16; 68],
    retained_bytes: usize,
}

impl SplitPrimeTables {
    fn new() -> Self {
        let digit_pairs = (0..=SPLIT_PRIME_DIGIT_LIMIT as i32)
            .map(nearest_split_prime_digit).collect::<Vec<_>>().into_boxed_slice();
        assert_eq!(digit_pairs.len(), 6106);
        let max_norm = digit_pairs.iter().map(|&(a,b)| {
            let a = i32::from(a); let b = i32::from(b);
            a*a + 3*a*b + 3*b*b
        }).max().unwrap();
        assert_eq!(max_norm, 3997);
        let digit_set = digit_pairs.iter().copied().map(orbit_canonical)
            .collect::<std::collections::BTreeSet<_>>();
        let mut digit_seeds = digit_set.into_iter().collect::<Vec<_>>();
        digit_seeds.retain(|&pair| pair != (0,0));
        digit_seeds.insert(0,(0,0));
        assert_eq!(digit_seeds.len(),2036);
        let digit_ids = digit_seeds.iter().enumerate()
            .map(|(index,&pair)| (pair,index as u16))
            .collect::<std::collections::BTreeMap<_,_>>();
        let digit_codes = digit_pairs.iter().copied().map(|pair| {
            let seed = orbit_canonical(pair);
            (digit_ids[&seed],orbit_code(pair,seed))
        }).collect::<Vec<_>>().into_boxed_slice();
        let mut base = Jacobian::generator();
        let mut digit_windows = Vec::with_capacity(SPLIT_PRIME_STEPS);
        for _ in 0..SPLIT_PRIME_STEPS {
            digit_windows.push(build_u256_window(&digit_seeds, base));
            let ordinary = affine_multiples(base, 112).pop().unwrap();
            let tau = base.tau().neg().into_affine();
            base = ordinary.add_mixed(tau).into_affine();
        }
        let mut pair_digits = Vec::new();
        let mut terminal_row_start = [0u16; 69];
        let mut terminal_row_min = [0i16; 68];
        for a in 0..68i32 {
            terminal_row_start[a as usize] = pair_digits.len() as u16;
            let mut first = true;
            for b in -40..=40i32 {
                let norm = a*a + 3*a*b + 3*b*b;
                if norm >= 1156 || (a == 0 && b < 0) { continue; }
                if first { terminal_row_min[a as usize] = b as i16; first = false; }
                pair_digits.push((a as i16, b as i16));
            }
            assert!(!first);
        }
        terminal_row_start[68] = pair_digits.len() as u16;
        assert_eq!(pair_digits.len(), 2095);
        let terminal_set = pair_digits.iter().copied().map(orbit_canonical)
            .collect::<std::collections::BTreeSet<_>>();
        let mut terminal_seeds = terminal_set.into_iter().collect::<Vec<_>>();
        terminal_seeds.retain(|&pair| pair != (0,0));
        terminal_seeds.insert(0,(0,0));
        assert_eq!(terminal_seeds.len(),699);
        let terminal_ids = terminal_seeds.iter().enumerate()
            .map(|(index,&pair)| (pair,index as u16))
            .collect::<std::collections::BTreeMap<_,_>>();
        let terminal_codes = pair_digits.iter().copied().map(|pair| {
            let seed = orbit_canonical(pair);
            (terminal_ids[&seed],orbit_code(pair,seed))
        }).collect::<Vec<_>>().into_boxed_slice();
        let terminal_pairs = build_u256_window(&terminal_seeds, base);
        let entries = digit_windows.iter().map(|row| row.len()).sum::<usize>();
        assert_eq!(entries, 18*2036);
        assert_eq!(size_of::<U256Affine>(),64);
        let retained_bytes = (entries + terminal_pairs.len()) * size_of::<U256Affine>()
            + digit_pairs.len() * size_of::<(i16,i16)>()
            + (digit_codes.len()+terminal_codes.len())*size_of::<(u16,u8)>()
            + size_of::<[super::U256;3]>() + size_of::<Self>()
            + digit_windows.capacity()*size_of::<Box<[U256Affine]>>();
        Self { digit_pairs,digit_codes,digit_windows,terminal_pairs,terminal_codes,
               terminal_row_start,terminal_row_min,retained_bytes }
    }
}
''')
    source = replace_once(source, '''        if index != 0 {
            let mut point = row[index];
            ops.digit_point_reads += 1;
            if sign != 0 {
                point.y = u256_sub(super::U256::ZERO, point.y);
                ops.sign_flips += 1;
            }
            if !bucket.is_identity() { ops.mixed_add_nontrivial += 1; }
            bucket = bucket.add_mixed(point);
            terms += 1;
        }''', '''        if index != 0 {
            let (seed, code) = tables.digit_codes[index];
            let unit = usize::from(code) ^ sign;
            let point = orbit_affine(row[usize::from(seed)],unit);
            ops.digit_point_reads += 1;
            ops.bucket_x_const_multiplies += usize::from(unit / 2 != 0);
            ops.sign_flips += unit & 1;
            if !bucket.is_identity() { ops.mixed_add_nontrivial += 1; }
            bucket = bucket.add_mixed(point);
            terms += 1;
        }''')
    source = replace_once(source, '''    if index != 0 {
        let mut point = tables.terminal_pairs[index];
        ops.terminal_point_reads += 1;
        if negate {
            point.y = u256_sub(super::U256::ZERO, point.y);
            ops.sign_flips += 1;
        }
        if !bucket.is_identity() { ops.mixed_add_nontrivial += 1; }
        bucket = bucket.add_mixed(point);
        terms += 1;
    }''', '''    if index != 0 {
        let (seed,code) = tables.terminal_codes[index];
        let unit = usize::from(code) ^ usize::from(negate);
        let point = orbit_affine(tables.terminal_pairs[usize::from(seed)],unit);
        ops.terminal_point_reads += 1;
        ops.bucket_x_const_multiplies += usize::from(unit / 2 != 0);
        ops.sign_flips += unit & 1;
        if !bucket.is_identity() { ops.mixed_add_nontrivial += 1; }
        bucket = bucket.add_mixed(point);
        terms += 1;
    }''')
    source = replace_once(source, '''        assert_eq!(tables.terminal_pairs.len(), count);''',
                          '''        assert_eq!(tables.terminal_codes.len(), count);
        assert_eq!(tables.terminal_pairs.len(),699);''')
    source = splice(source, '    #[test]\n    fn split_prime_direct_signed_digit_images_exhaustive()',
                    '    #[test]\n    fn split_prime_no_fallback_random_replay()', '''    #[test]
    fn split_prime_orbit_terminal_images_exhaustive() {
        let tables = &*SPLIT_PRIME_TABLES;
        let mut pairs = Vec::new();
        for a in 0..68i32 {
            for b in -40..=40i32 {
                let norm = a*a+3*a*b+3*b*b;
                if norm < 1156 && (a != 0 || b >= 0) {
                    pairs.push((a as i16,b as i16));
                }
            }
        }
        assert_eq!(pairs.len(),2095);
        let mut base = Jacobian::generator();
        for _ in 0..SPLIT_PRIME_STEPS {
            let ordinary = affine_multiples(base,112).pop().unwrap();
            let tau = base.tau().neg().into_affine();
            base = ordinary.add_mixed(tau).into_affine();
        }
        let expanded = build_u256_window(&pairs,base);
        for (index,&expected) in expanded.iter().enumerate() {
            let (seed,code) = tables.terminal_codes[index];
            let actual = orbit_affine(tables.terminal_pairs[usize::from(seed)],
                                      usize::from(code));
            assert_eq!(actual.x.0,expected.x.0);
            assert_eq!(actual.y.0,expected.y.0);
        }
        println!("orbit_terminal_images={}",pairs.len());
    }

    #[test]
    fn split_prime_orbit_digit_images_exhaustive() {
        let tables = &*SPLIT_PRIME_TABLES;
        let mut checked = 0usize;
        let mut base = Jacobian::generator();
        for row in &tables.digit_windows {
            assert_eq!(row.len(),2036);
            let expanded = build_u256_window(&tables.digit_pairs,base);
            for (index,&entry) in expanded.iter().enumerate() {
                let (seed,code) = tables.digit_codes[index];
                for extra_sign in 0..2 {
                    let actual = orbit_affine(row[usize::from(seed)],
                                              usize::from(code)^extra_sign);
                    let mut expected = entry;
                    if extra_sign != 0 {
                        expected.y = u256_sub(super::super::U256::ZERO,expected.y);
                    }
                    assert_eq!(actual.x.0,expected.x.0);
                    assert_eq!(actual.y.0,expected.y.0);
                    checked += 1;
                }
            }
            let ordinary = affine_multiples(base,112).pop().unwrap();
            let tau = base.tau().neg().into_affine();
            base = ordinary.add_mixed(tau).into_affine();
        }
        assert_eq!(checked,18*6106*2);
        println!("orbit_digit_images={checked}");
    }

''')
    path.write_text(source)
    print(sha256(path.read_bytes()).hexdigest())


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: native_overlay.py CARGO_ROOT')
    main(Path(sys.argv[1]))
