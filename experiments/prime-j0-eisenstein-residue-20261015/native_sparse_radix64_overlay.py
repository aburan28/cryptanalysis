#!/usr/bin/env python3
"""Apply the 63+64*tau radix to the frozen sparse-Horner native source."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = '6cd0962b58b4673708af813a913474791400a7297142e4e5970e7af11faf0b34'
WINDOWS_SHA256 = 'c89602515460ab1e5f4a309b78bc28313ad991c46cec58b53e3383ac292378a8'

SELECTOR = '''fn nearest_alt_split_prime_digit(residue: i32) -> (i16, i16) {
    if residue == 0 { return (0, 0); }
    let mut best = (i32::MAX, i32::MAX, i32::MAX, i32::MAX, i32::MAX);
    for lift_number in -2..=2i32 {
        let lift = residue + lift_number*ALT_SPLIT_PRIME_NORM;
        let center = (-891*lift).div_euclid(396942);
        for b in center-2..=center+2 {
            let a = lift+444*b;
            let norm = a*a+3*a*b+3*b*b;
            let score = (norm,b.abs(),a.abs(),a,b);
            if score < best { best = score; }
        }
    }
    (i16::try_from(best.3).unwrap(),i16::try_from(best.4).unwrap())
}

fn alt_split_prime_unit_step(
    a: Signed192, b: Signed192, digit_pairs: &[(i16,i16)],
) -> (Signed192, Signed192, usize, usize) {
    let residue_word = a.add(b.times_alt_split_prime_small(ALT_SPLIT_PRIME_TAU_RESIDUE));
    let (_, _, residue) = residue_word.div_rem_small_radix(ALT_SPLIT_PRIME_NORM as u64);
    let negative = residue > ALT_SPLIT_PRIME_DIGIT_LIMIT;
    let index = if negative { ALT_SPLIT_PRIME_NORM as usize-residue as usize }
                else { residue as usize };
    let (raw_da,raw_db) = digit_pairs[index];
    let da = if negative { -i32::from(raw_da) } else { i32::from(raw_da) };
    let db = if negative { -i32::from(raw_db) } else { i32::from(raw_db) };
    let shifted_a = a.sub(Signed192::from_i32(da));
    let shifted_b = b.sub(Signed192::from_i32(db));
    let numerator_a = shifted_a.times_alt_split_prime_small(255)
        .add(shifted_b.times_alt_split_prime_small(192));
    let numerator_b = shifted_a.times_alt_split_prime_small(-64)
        .add(shifted_b.times_alt_split_prime_small(63));
    let (next_a,rem_a,residue_a) = numerator_a.div_rem_small_radix(ALT_SPLIT_PRIME_NORM as u64);
    let (next_b,rem_b,residue_b) = numerator_b.div_rem_small_radix(ALT_SPLIT_PRIME_NORM as u64);
    assert_eq!((rem_a,residue_a,rem_b,residue_b),(0,0,0,0));
    (next_a,next_b,index,usize::from(negative))
}

'''

MULTIPLIER = '''fn alt_horner_mul_pi(point: U256Jacobian) -> U256Jacobian {
    if point.is_identity() { return point; }
    // 63+64*tau = 64*(1+tau)-1.
    let mut multiple = point.add_projective(point.tau());
    for _ in 0..6 { multiple = multiple.double(); }
    let neg_point = U256Jacobian {
        y: u256_sub(super::U256::ZERO,point.y), ..point
    };
    multiple.add_projective(neg_point)
}

'''


def replace_section(source,begin,end,replacement):
    assert source.count(begin) == source.count(end) == 1
    start = source.index(begin)
    stop = source.index(end,start)
    return source[:start]+replacement+source[stop:]


def main(root: Path):
    front = root/'src/bin/eisenstein_fixed.rs'
    windows = root/'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    assert sha256(front.read_bytes()).hexdigest() == FRONT_SHA256
    assert sha256(windows.read_bytes()).hexdigest() == WINDOWS_SHA256
    source = windows.read_text()
    for before,after in (
        ('const ALT_SPLIT_PRIME_NORM: i32 = 114049;',
         'const ALT_SPLIT_PRIME_NORM: i32 = 28353;'),
        ('const ALT_SPLIT_PRIME_TAU_RESIDUE: i32 = -892;',
         'const ALT_SPLIT_PRIME_TAU_RESIDUE: i32 = -444;'),
        ('const ALT_SPLIT_PRIME_STEPS: usize = 15;',
         'const ALT_SPLIT_PRIME_STEPS: usize = 17;'),
        ('const ALT_SPLIT_PRIME_DIGIT_LIMIT: usize = 57024;',
         'const ALT_SPLIT_PRIME_DIGIT_LIMIT: usize = 14176;'),
        ('assert_eq!(digit_pairs.len(), 55279);',
         'assert_eq!(digit_pairs.len(), 14177);'),
        ('assert_eq!(digit_pairs.len(),57025);',
         'assert_eq!(digit_pairs.len(),14177);'),
        ('"norm-114049 terminal bound"',
         '"norm-28353 terminal bound"')):
        assert source.count(before) == 1, before
        source = source.replace(before,after,1)
    source = replace_section(source,'fn nearest_alt_split_prime_digit(',
                             'fn alt_orbit_omega_pair(',SELECTOR)
    source = replace_section(source,'fn alt_horner_mul_pi(',
                             'static ALT_SPLIT_PRIME_TWO_X_TABLES:',MULTIPLIER)
    windows.write_text(source)
    print('front_sha256='+sha256(front.read_bytes()).hexdigest())
    print('windows_sha256='+sha256(windows.read_bytes()).hexdigest())


if __name__ == '__main__':
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]))
