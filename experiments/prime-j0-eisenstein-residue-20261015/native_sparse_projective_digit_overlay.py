#!/usr/bin/env python3
"""Replace scalar-local pair-field digit synthesis with native projective synthesis."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = 'eb5b0a700cf6896339443474d2ee77cec1214ddfe585bb784d9da96cd6f8ae86'
WINDOWS_SHA256 = 'efb7105d2df6ddef47883dffc5fb64e8801bd7d7467d7f4c9dfa2d4ead87f473'

OLD_POINTS = '''        let points = build_u256_window(&selected,Jacobian::generator());'''
NEW_POINTS = '''        // One shared native-field dyadic basis synthesizes only this scalar's
        // selected Eisenstein digits. Keep the digit points projective.
        let generator = Jacobian::generator().into_affine();
        let native_generator = U256Jacobian::from_affine(U256Affine {
            x: super::hybrid_pair_mont(generator.x),
            y: super::hybrid_pair_mont(generator.y),
        });
        let native_tau = native_generator.tau();
        let mut a_powers = [U256Jacobian::identity();7];
        let mut b_powers = [U256Jacobian::identity();7];
        a_powers[0] = native_generator;
        b_powers[0] = native_tau;
        for bit in 1..7 {
            a_powers[bit] = a_powers[bit-1].double();
            b_powers[bit] = b_powers[bit-1].double();
        }
        let points = selected.iter().map(|&(da,db)| {
            let mut point = U256Jacobian::identity();
            for (value,powers) in [(da,&a_powers),(db,&b_powers)] {
                let magnitude = value.unsigned_abs() as usize;
                assert!(magnitude < 128);
                for bit in 0..7 {
                    if magnitude & (1usize << bit) != 0 {
                        let mut term = powers[bit];
                        if value < 0 {
                            term.y = u256_sub(super::U256::ZERO,term.y);
                        }
                        point = point.add_projective(term);
                    }
                }
            }
            assert_eq!(point.is_identity(),(da,db)==(0,0));
            point
        }).collect::<Vec<_>>();'''


def main(root: Path):
    front = root / 'src/bin/eisenstein_fixed.rs'
    windows = root / 'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    assert sha256(front.read_bytes()).hexdigest() == FRONT_SHA256
    assert sha256(windows.read_bytes()).hexdigest() == WINDOWS_SHA256
    front_text = front.read_text()
    windows_text = windows.read_text()
    assert front_text.count('--pilot-alt-on-demand') == 1
    front_text = front_text.replace('--pilot-alt-on-demand', '--pilot-alt-projective-digits', 1)
    before = 'unit_orbit_windows::multiply_u256_tau_alt_on_demand_batch(&words)'
    after = 'unit_orbit_windows::multiply_u256_tau_alt_projective_digits_batch(&words)'
    assert front_text.count(before) == 1
    front_text = front_text.replace(before, after, 1)
    assert windows_text.count(OLD_POINTS) == 1
    windows_text = windows_text.replace(OLD_POINTS, NEW_POINTS, 1)
    assert windows_text.count('pub(super) fn multiply_u256_tau_alt_on_demand_batch(') == 1
    windows_text = windows_text.replace('pub(super) fn multiply_u256_tau_alt_on_demand_batch(',
                                        'pub(super) fn multiply_u256_tau_alt_projective_digits_batch(',1)
    before = 'U256Jacobian::from_affine(points[ids[&terminal]])'
    assert windows_text.count(before) == 1
    windows_text = windows_text.replace(before, 'points[ids[&terminal]]', 1)
    before = 'accumulator.add_mixed(points[ids[&digit]])'
    assert windows_text.count(before) == 1
    windows_text = windows_text.replace(before, 'accumulator.add_projective(points[ids[&digit]])', 1)
    front.write_text(front_text)
    windows.write_text(windows_text)
    print('front_sha256='+sha256(front.read_bytes()).hexdigest())
    print('windows_sha256='+sha256(windows.read_bytes()).hexdigest())


if __name__ == '__main__':
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]))
