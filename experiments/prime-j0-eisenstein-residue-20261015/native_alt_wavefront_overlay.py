#!/usr/bin/env python3
"""Transpose recode, prefetch, and gather across eight scalar lanes."""

from hashlib import sha256
from pathlib import Path
import sys

WINDOWS_SHA256 = 'f5dcba53fd1db7eb5b2c47cc9ccc3cc85c1c60ca45e1efb53e5f4aab5ff23154'


def main(root: Path) -> None:
    path = root/'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    source = path.read_bytes()
    assert sha256(source).hexdigest() == WINDOWS_SHA256
    text = source.decode()
    start = text.index('fn alt_split_prime_two_x_affine_leaves(')
    end = text.index('\n\n\n#[cfg(test)]', start)
    old = text[start:end]
    prefix = old[:old.index('    // Issue the two cache-line requests')]
    assert prefix.count('    let mut choices = ') == 1
    prefix = prefix.replace(
        'fn alt_split_prime_two_x_affine_leaves(scalar_words: [u64;4])\n'
        '    -> [Option<U256Affine>; ALT_SPLIT_PRIME_STEPS+1] {',
        'fn alt_split_prime_two_x_choices(scalar_words: [u64;4])\n'
        '    -> [(usize,usize); ALT_SPLIT_PRIME_STEPS+1] {')
    assert 'fn alt_split_prime_two_x_choices' in prefix
    replacement = prefix + '''    choices
}

#[inline]
fn alt_split_prime_prefetch_choices(
    choices: &[(usize,usize); ALT_SPLIT_PRIME_STEPS+1],
    tables: &AltSplitPrimeTwoXTables,
) {
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
    #[cfg(not(target_arch = "x86_64"))]
    let _ = (choices,tables);
}

#[inline]
fn alt_split_prime_gather_choices(
    choices: &[(usize,usize); ALT_SPLIT_PRIME_STEPS+1],
    tables: &AltSplitPrimeTwoXTables,
) -> Vec<Option<U256Affine>> {
    let mut leaves = [None;ALT_SPLIT_PRIME_STEPS+1];
    for (window,&(seed,unit)) in choices.iter().enumerate() {
        if seed == 0 { continue; }
        let point = if window < ALT_SPLIT_PRIME_STEPS {
            tables.digit_windows[window][seed]
        } else {
            tables.terminal_pairs[seed]
        };
        leaves[window] = Some(point.unit(unit));
    }
    leaves.into_iter().collect()
}

pub(super) fn multiply_u256_tau_alt_split_prime_two_x_affine_batch(
    scalar_words: &[[u64;4]],
) -> Vec<String> {
    let tables = &*ALT_SPLIT_PRIME_TWO_X_TABLES;
    let mut lanes = Vec::with_capacity(scalar_words.len());
    for wave in scalar_words.chunks(8) {
        let choices = wave.iter().copied().map(alt_split_prime_two_x_choices)
            .collect::<Vec<_>>();
        for choice in &choices { alt_split_prime_prefetch_choices(choice,tables); }
        for choice in &choices { lanes.push(alt_split_prime_gather_choices(choice,tables)); }
    }
    affine_layer_reduce(lanes).into_iter().map(affine_layer_hex).collect()
}
'''
    updated = (text[:start]+replacement+text[end:]).encode()
    path.write_bytes(updated)
    print('input_sha256='+sha256(source).hexdigest())
    print('output_sha256='+sha256(updated).hexdigest())


if __name__ == '__main__':
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]))
