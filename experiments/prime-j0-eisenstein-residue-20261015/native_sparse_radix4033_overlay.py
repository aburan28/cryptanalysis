#!/usr/bin/env python3
"""Change the scalar-local graph path to the 64+omega Eisenstein radix."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = '2251cf1c67bed140c20b8323dff2196f3b5e394ce10fa186213a9736f45b958d'
WINDOWS_SHA256 = '7bc9f9beedbdf36af2b9a8eb01d68fa9f5aa101bf9ca0c21069cd43bc30377be'

OLD_SELECTOR = '''fn nearest_alt_split_prime_digit(residue: i32) -> (i16, i16) {
    if residue == 0 { return (0, 0); }
    let mut best = (i32::MAX, i32::MAX, i32::MAX, i32::MAX, i32::MAX);
    for lift_number in -2..=2i32 {
        let lift = residue + lift_number*ALT_SPLIT_PRIME_NORM;
        let center = (-443*lift).div_euclid(98126);
        for b in center-2..=center+2 {
            let a = lift+220*b;
            let norm = a*a+3*a*b+3*b*b;
            let score = (norm,b.abs(),a.abs(),a,b);
            if score < best { best = score; }
        }
    }
    (i16::try_from(best.3).unwrap(),i16::try_from(best.4).unwrap())
}'''

NEW_SELECTOR = '''fn nearest_alt_split_prime_digit(residue: i32) -> (i16, i16) {
    if residue == 0 { return (0, 0); }
    let mut best = (i32::MAX, i32::MAX, i32::MAX, i32::MAX, i32::MAX);
    for lift_number in -2..=2i32 {
        let lift = residue + lift_number*ALT_SPLIT_PRIME_NORM;
        // a+65b == residue (mod 4033); minimizing the hexagonal norm
        // gives b close to 127*lift/(2*4033).
        let center = (127*lift).div_euclid(8066);
        for b in center-2..=center+2 {
            let a = lift-65*b;
            let norm = a*a+3*a*b+3*b*b;
            let score = (norm,b.abs(),a.abs(),a,b);
            if score < best { best = score; }
        }
    }
    (i16::try_from(best.3).unwrap(),i16::try_from(best.4).unwrap())
}'''

OLD_STEP = '''    let numerator_a = shifted_a.times_alt_split_prime_small(127)
        .add(shifted_b.times_alt_split_prime_small(96));
    let numerator_b = shifted_a.times_alt_split_prime_small(-32)
        .add(shifted_b.times_alt_split_prime_small(31));'''

NEW_STEP = '''    // Inverse of multiplication by 65-tau:
    // [[65,3],[-1,62]]^(-1) = [[62,-3],[1,65]] / 4033.
    let numerator_a = shifted_a.times_alt_split_prime_small(62)
        .add(shifted_b.times_alt_split_prime_small(-3));
    let numerator_b = shifted_a
        .add(shifted_b.times_alt_split_prime_small(65));'''

OLD_HORNER = '''fn alt_horner_mul_pi(point: U256Jacobian) -> U256Jacobian {
    if point.is_identity() { return point; }
    // τ=1-ω, hence 31+32τ=63-32ω. Let q=32P:
    // (2q-P)-ωq = (63-32ω)P.
    let mut q = point;
    for _ in 0..5 { q = q.double(); }
    let omega_q = q.rotate_power(1);
    let twice_q = q.double();
    let neg_point = U256Jacobian {
        y: u256_sub(super::U256::ZERO,point.y), ..point
    };
    let neg_omega_q = U256Jacobian {
        y: u256_sub(super::U256::ZERO,omega_q.y), ..omega_q
    };
    twice_q.add_projective(neg_point).add_projective(neg_omega_q)
}'''

NEW_HORNER = '''fn alt_horner_mul_pi(point: U256Jacobian) -> U256Jacobian {
    if point.is_identity() { return point; }
    // 65-tau = 64+omega. One rotation and one projective addition.
    let omega_point = point.rotate_power(1);
    let mut q = point;
    for _ in 0..6 { q = q.double(); }
    q.add_projective(omega_point)
}'''


def replace_once(source: str, before: str, after: str) -> str:
    assert source.count(before) == 1, before[:80]
    return source.replace(before, after, 1)


def main(root: Path):
    front = root / 'src/bin/eisenstein_fixed.rs'
    windows = root / 'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    assert sha256(front.read_bytes()).hexdigest() == FRONT_SHA256
    assert sha256(windows.read_bytes()).hexdigest() == WINDOWS_SHA256
    front_text = replace_once(front.read_text(), '--pilot-alt-rotated-step',
                              '--pilot-radix4033')
    windows_text = windows.read_text()
    for before, after in (
        ('const ALT_SPLIT_PRIME_NORM: i32 = 7009;',
         'const ALT_SPLIT_PRIME_NORM: i32 = 4033;'),
        ('const ALT_SPLIT_PRIME_TAU_RESIDUE: i32 = -220;',
         'const ALT_SPLIT_PRIME_TAU_RESIDUE: i32 = 65;'),
        ('const ALT_SPLIT_PRIME_STEPS: usize = 20;',
         'const ALT_SPLIT_PRIME_STEPS: usize = 22;'),
        ('const ALT_SPLIT_PRIME_DIGIT_LIMIT: usize = 3504;',
         'const ALT_SPLIT_PRIME_DIGIT_LIMIT: usize = 2016;'),
        ('assert_eq!(digit_pairs.len(), 3505);',
         'assert_eq!(digit_pairs.len(), 2017);'),
        ('assert_eq!(digit_pairs.len(),3505);',
         'assert_eq!(digit_pairs.len(),2017);'),
        (OLD_SELECTOR, NEW_SELECTOR),
        (OLD_STEP, NEW_STEP),
        (OLD_HORNER, NEW_HORNER)):
        windows_text = replace_once(windows_text, before, after)
    front.write_text(front_text)
    windows.write_text(windows_text)
    print('front_sha256='+sha256(front.read_bytes()).hexdigest())
    print('windows_sha256='+sha256(windows.read_bytes()).hexdigest())


if __name__ == '__main__':
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]))
