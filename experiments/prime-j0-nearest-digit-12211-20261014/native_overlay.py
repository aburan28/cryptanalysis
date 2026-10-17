#!/usr/bin/env python3
"""Replace centered integer digits with exact minimum-norm Eisenstein digits."""
from hashlib import sha256
from pathlib import Path
import sys

SOURCE_SHA256 = 'c02b681d22e66eefe23ba4ec46c428be0159a6f2772ce42801f705da55cdd7df'


def splice(source, first, last, replacement):
    start = source.index(first)
    end = source.index(last, start)
    return source[:start] + replacement + source[end:]


def main(root):
    path = root / 'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    source = path.read_text()
    assert sha256(source.encode()).hexdigest() == SOURCE_SHA256
    source = source.replace('const SPLIT_PRIME_TERMINAL_LIMIT: usize = 178;',
                            'const SPLIT_PRIME_TERMINAL_LIMIT: usize = 68;')
    source = splice(source, 'fn split_prime_unit_step(\n', '\nstruct SplitPrimeTables {', '''fn nearest_split_prime_digit(residue: i32) -> (i16, i16) {
    if residue == 0 { return (0, 0); }
    let mut best = (i32::MAX, i32::MAX, i32::MAX, i32::MAX, i32::MAX);
    for lift in [residue, residue-SPLIT_PRIME_NORM] {
        let center = (2*lift+110).div_euclid(221);
        for b in [center-1, center, center+1] {
            let a = lift-112*b;
            let norm = a*a+3*a*b+3*b*b;
            let score = (norm,b.abs(),a.abs(),a,b);
            if score < best { best = score; }
        }
    }
    (i16::try_from(best.3).unwrap(), i16::try_from(best.4).unwrap())
}

fn split_prime_unit_step(
    a: Signed192, b: Signed192, tables: &SplitPrimeTables,
) -> (Signed192, Signed192, usize, usize) {
    let residue_word = a.add(b.times_split_prime_small(SPLIT_PRIME_TAU_RESIDUE));
    let (quotient, signed_rem, residue) =
        residue_word.div_rem_small_radix(SPLIT_PRIME_NORM as u64);
    let negative = residue > SPLIT_PRIME_DIGIT_LIMIT;
    let index = if negative { SPLIT_PRIME_NORM as usize - residue as usize }
                else { residue as usize };
    let (raw_da, raw_db) = tables.digit_pairs[index];
    let da = if negative { -i32::from(raw_da) } else { i32::from(raw_da) };
    let db = if negative { -i32::from(raw_db) } else { i32::from(raw_db) };
    let digit_residue = da + SPLIT_PRIME_TAU_RESIDUE * db;
    let t = (digit_residue - residue as i32) / SPLIT_PRIME_NORM;
    assert_eq!((digit_residue - residue as i32) % SPLIT_PRIME_NORM, 0);
    let adjustment = if signed_rem < 0 { -1 } else { 0 } - t;
    let k = quotient.add(Signed192::from_i32(adjustment));
    let shifted_b = b.sub(Signed192::from_i32(db));
    let next_a = k.times_split_prime_small(109).sub(shifted_b);
    (next_a, k, index, usize::from(negative))
}
''')
    source = splice(source, 'struct SplitPrimeTables {', '\nstatic SPLIT_PRIME_TABLES: LazyLock<SplitPrimeTables> =', '''struct SplitPrimeTables {
    digit_pairs: Box<[(i16, i16)]>,
    digit_windows: Vec<Box<[U256Affine]>>,
    terminal_pairs: Box<[U256Affine]>,
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
        let mut base = Jacobian::generator();
        let mut digit_windows = Vec::with_capacity(SPLIT_PRIME_STEPS);
        for _ in 0..SPLIT_PRIME_STEPS {
            digit_windows.push(build_u256_window(&digit_pairs, base));
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
        assert_eq!(pair_digits[0], (0, 0));
        let terminal_pairs = build_u256_window(&pair_digits, base);
        let entries = digit_windows.iter().map(|row| row.len()).sum::<usize>();
        assert_eq!(entries, 18 * 6106);
        assert_eq!(size_of::<U256Affine>(), 64);
        let retained_bytes = (entries + terminal_pairs.len()) * size_of::<U256Affine>()
            + digit_pairs.len() * size_of::<(i16, i16)>()
            + size_of::<[super::U256; 3]>()
            + size_of::<Self>()
            + digit_windows.capacity() * size_of::<Box<[U256Affine]>>();
        Self { digit_pairs, digit_windows, terminal_pairs,
               terminal_row_start, terminal_row_min, retained_bytes }
    }
}
''')
    source = source.replace('assert!(terminal_norm < 7921, "direct norm-12211 terminal bound");',
                            'assert!(terminal_norm < 1156, "nearest-digit norm-12211 terminal bound");')
    start = source.index('    #[test]\n    fn split_prime_12211_direct_residue_quotients_exhaustive()')
    end = source.index('    #[test]\n    fn split_prime_direct_signed_digit_images_exhaustive()', start)
    source = source[:start] + '''    #[test]
    fn split_prime_12211_nearest_residue_quotients_exhaustive() {
        fn small_value(value: Signed192) -> i32 {
            assert_eq!(value.limbs[1..], [0, 0]);
            let magnitude = i32::try_from(value.limbs[0]).unwrap();
            if value.negative { -magnitude } else { magnitude }
        }
        let tables = &*SPLIT_PRIME_TABLES;
        let mut checked_steps = 0usize;
        for residue in 0..SPLIT_PRIME_NORM {
            let index = if residue <= 6105 { residue as usize }
                        else { (12211-residue) as usize };
            let sign = usize::from(residue > 6105);
            let (raw_da,raw_db) = tables.digit_pairs[index];
            let da = if sign != 0 { -i32::from(raw_da) } else { i32::from(raw_da) };
            let db = if sign != 0 { -i32::from(raw_db) } else { i32::from(raw_db) };
            assert_eq!((da+112*db-residue).rem_euclid(12211), 0);
            assert!(da*da+3*da*db+3*db*db <= 3997);
            for b in [-7i32, 0, 7] {
                for shift in [-SPLIT_PRIME_NORM, 0, SPLIT_PRIME_NORM] {
                    let a = residue - SPLIT_PRIME_TAU_RESIDUE*b + shift;
                    let k = (a-da+112*(b-db)).div_euclid(SPLIT_PRIME_NORM);
                    let (next_a,next_b,got_index,got_sign) =
                        split_prime_unit_step(Signed192::from_i32(a),
                                              Signed192::from_i32(b), tables);
                    assert_eq!((got_index,got_sign),(index,sign));
                    assert_eq!(small_value(next_a), 109*k-(b-db));
                    assert_eq!(small_value(next_b), k);
                    checked_steps += 1;
                }
            }
        }
        assert_eq!(checked_steps, 12211*9);
        println!("nearest_norm12211_residues=12211 quotient_cases={checked_steps}");
    }

    #[test]
    fn split_prime_12211_nearest_terminal_indices_exhaustive() {
        let tables = &*SPLIT_PRIME_TABLES;
        let mut count = 0usize;
        for a in 0..68i32 {
            for b in -40..=40i32 {
                let norm = a*a+3*a*b+3*b*b;
                if norm >= 1156 || (a == 0 && b < 0) { continue; }
                let offset = usize::try_from(
                    b-i32::from(tables.terminal_row_min[a as usize])).unwrap();
                let index = tables.terminal_row_start[a as usize] as usize + offset;
                assert_eq!(index, count, "terminal pair ({a},{b})");
                count += 1;
            }
        }
        assert_eq!(count, 2095);
        assert_eq!(tables.terminal_pairs.len(), count);
        println!("nearest_norm12211_terminal_indices={count}");
    }

''' + source[end:]
    path.write_text(source)
    print(sha256(path.read_bytes()).hexdigest())

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: native_overlay.py CARGO_ROOT')
    main(Path(sys.argv[1]))
