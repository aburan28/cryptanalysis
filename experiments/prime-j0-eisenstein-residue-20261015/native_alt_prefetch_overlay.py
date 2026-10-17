#!/usr/bin/env python3
"""Prefetch frozen norm-110557 table choices before affine gather."""

from hashlib import sha256
from pathlib import Path
import sys

WINDOWS_SHA256 = 'ee2297e049142e7447a1eac01da947095dba145f463657506b6a90adb9f3864d'


def main(root: Path) -> None:
    path = root/'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    source = path.read_bytes()
    assert sha256(source).hexdigest() == WINDOWS_SHA256
    text = source.decode()
    start = text.index('fn alt_split_prime_two_x_affine_leaves(')
    end = text.index('pub(super) fn multiply_u256_tau_alt_split_prime_two_x_affine_batch(', start)
    body = text[start:end]
    marker = '    let mut leaves = [None;ALT_SPLIT_PRIME_STEPS+1];\n'
    assert body.count(marker) == 1
    prefetch = '''    // Issue the two cache-line requests for each selected entry before gathering.
    // Other architectures retain the same table lookup and point arithmetic.
    #[cfg(target_arch = "x86_64")]
    for (window,&(seed,_)) in choices.iter().enumerate() {
        if seed == 0 { continue; }
        let point: &U256TwoXAffine = if window < ALT_SPLIT_PRIME_STEPS {
            &tables.digit_windows[window][seed]
        } else {
            &tables.terminal_pairs[seed]
        };
        let ptr = point as *const U256TwoXAffine as *const i8;
        unsafe {
            core::arch::x86_64::_mm_prefetch(ptr, core::arch::x86_64::_MM_HINT_T0);
            core::arch::x86_64::_mm_prefetch(ptr.add(64), core::arch::x86_64::_MM_HINT_T0);
        }
    }
'''
    body = body.replace(marker, prefetch + marker)
    updated = (text[:start]+body+text[end:]).encode()
    path.write_bytes(updated)
    print('input_sha256='+sha256(source).hexdigest())
    print('output_sha256='+sha256(updated).hexdigest())


if __name__ == '__main__':
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]))
