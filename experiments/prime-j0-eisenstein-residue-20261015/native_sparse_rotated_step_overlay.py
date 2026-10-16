#!/usr/bin/env python3
"""Evaluate the 31+32τ Horner radix as 63-32ω in the native point path."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = '292f178a908cccc3f661c80aa0798461d23a011843e3621a26a472388b586703'
WINDOWS_SHA256 = 'c0c22d7029d375d791c05f63e68fe22445825114951ebc3dbf356e9879376e8a'

OLD = '''fn alt_horner_mul_pi(point: U256Jacobian) -> U256Jacobian {
    if point.is_identity() { return point; }
    // 31+32*tau = 32*(1+tau)-1.
    let mut multiple = point.add_projective(point.tau());
    for _ in 0..5 { multiple = multiple.double(); }
    let neg_point = U256Jacobian {
        y: u256_sub(super::U256::ZERO,point.y), ..point
    };
    multiple.add_projective(neg_point)
}'''

NEW = '''fn alt_horner_mul_pi(point: U256Jacobian) -> U256Jacobian {
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


def main(root: Path):
    front = root / 'src/bin/eisenstein_fixed.rs'
    windows = root / 'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    assert sha256(front.read_bytes()).hexdigest() == FRONT_SHA256
    assert sha256(windows.read_bytes()).hexdigest() == WINDOWS_SHA256
    front_text = front.read_text()
    windows_text = windows.read_text()
    assert front_text.count('--pilot-alt-digit-graph') == 1
    assert windows_text.count(OLD) == 1
    front_text = front_text.replace('--pilot-alt-digit-graph',
                                    '--pilot-alt-rotated-step', 1)
    windows_text = windows_text.replace(OLD, NEW, 1)
    front.write_text(front_text)
    windows.write_text(windows_text)
    print('front_sha256='+sha256(front.read_bytes()).hexdigest())
    print('windows_sha256='+sha256(windows.read_bytes()).hexdigest())


if __name__ == '__main__':
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]))
