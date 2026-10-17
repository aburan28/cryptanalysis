#!/usr/bin/env python3
"""Store one affine (x,y) point and compute beta rotations on selection."""

from hashlib import sha256
from pathlib import Path
import sys

WINDOWS_SHA256 = 'f5dcba53fd1db7eb5b2c47cc9ccc3cc85c1c60ca45e1efb53e5f4aab5ff23154'


def main(root: Path) -> None:
    path = root/'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    source = path.read_bytes()
    assert sha256(source).hexdigest() == WINDOWS_SHA256
    text = source.decode()
    warm_start = text.index('pub(super) fn warm_alt_split_prime_two_x_table()')
    warm_end = text.index('\n}\n',warm_start)+2
    warm = '''pub(super) fn warm_alt_split_prime_two_x_table() -> usize {
    std::sync::LazyLock::force(&super::EXACT_RECIPROCAL_CHECK);
    std::sync::LazyLock::force(&super::FIXED_SCALAR_LATTICE);
    let bytes = ALT_SPLIT_PRIME_TABLES.retained_bytes;
    assert!(bytes < 32*1024*1024);
    bytes
}'''
    text = text[:warm_start]+warm+text[warm_end:]
    start = text.index('fn alt_split_prime_two_x_affine_leaves(')
    end = text.index('pub(super) fn multiply_u256_tau_alt_split_prime_two_x_affine_batch(',start)
    body = text[start:end]
    assert body.count('let tables = &*ALT_SPLIT_PRIME_TWO_X_TABLES;') == 1
    assert body.count('let point: &U256TwoXAffine') == 1
    body = body.replace('let tables = &*ALT_SPLIT_PRIME_TWO_X_TABLES;',
                        'let tables = &*ALT_SPLIT_PRIME_TABLES;')
    body = body.replace('let point: &U256TwoXAffine', 'let point: &U256Affine')
    body = body.replace('point as *const U256TwoXAffine as *const i8',
                        'point as *const U256Affine as *const i8')
    body = body.replace('ptr.add(64)', 'ptr.add(32)')
    assert 'ALT_SPLIT_PRIME_TWO_X_TABLES' not in body
    assert 'U256TwoXAffine' not in body
    updated = (text[:start]+body+text[end:]).encode()
    path.write_bytes(updated)
    print('input_sha256='+sha256(source).hexdigest())
    print('output_sha256='+sha256(updated).hexdigest())


if __name__ == '__main__':
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]))
