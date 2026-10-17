#!/usr/bin/env python3
"""Store precomputed rotations in alternating digit rows, compact points elsewhere."""

from hashlib import sha256
from pathlib import Path
import sys

WINDOWS_SHA256 = 'f5dcba53fd1db7eb5b2c47cc9ccc3cc85c1c60ca45e1efb53e5f4aab5ff23154'

MIXED_TABLE = '''
// Eight of fifteen digit rows store a second x coordinate. The other rows and
// terminal table compute the beta rotation only when that unit is selected.
const ALT_MIXED_FULL_ROW_MASK: u16 = 0x5555;

enum AltMixedRow {
    Full(Box<[U256TwoXAffine]>),
    Compact(Box<[U256Affine]>),
}

impl AltMixedRow {
    fn prefetch(&self, seed: usize) {
        #[cfg(target_arch = "x86_64")]
        {
            let (ptr, second): (*const i8, usize) = match self {
                Self::Full(row) => (&row[seed] as *const U256TwoXAffine as *const i8,64),
                Self::Compact(row) => (&row[seed] as *const U256Affine as *const i8,32),
            };
            unsafe {
                core::arch::x86_64::_mm_prefetch(ptr, core::arch::x86_64::_MM_HINT_T0);
                core::arch::x86_64::_mm_prefetch(ptr.add(second), core::arch::x86_64::_MM_HINT_T0);
            }
        }
        #[cfg(not(target_arch = "x86_64"))]
        let _ = seed;
    }

    fn select(&self, seed: usize, unit: usize) -> U256Affine {
        match self {
            Self::Full(row) => row[seed].unit(unit),
            Self::Compact(row) => row[seed].unit(unit),
        }
    }
}

struct AltMixedTables {
    digit_pairs: Box<[(i16,i16)]>,
    digit_codes: Box<[(u16,u8)]>,
    digit_windows: Vec<AltMixedRow>,
    terminal_pairs: Box<[U256Affine]>,
    terminal_codes: Box<[(u16,u8)]>,
    retained_bytes: usize,
}

impl AltMixedTables {
    fn new() -> Self {
        let ordinary = AltSplitPrimeTables::new();
        let AltSplitPrimeTables {
            digit_pairs,digit_codes,digit_windows,terminal_pairs,terminal_codes,
            retained_bytes: _,
        } = ordinary;
        let (mut full_entries,mut compact_entries) = (0usize,0usize);
        let digit_windows = digit_windows.into_iter().enumerate().map(|(index,row)| {
            if (ALT_MIXED_FULL_ROW_MASK >> index) & 1 != 0 {
                full_entries += row.len();
                AltMixedRow::Full(row.iter().copied().map(U256TwoXAffine::from_affine)
                    .collect::<Vec<_>>().into_boxed_slice())
            } else {
                compact_entries += row.len();
                AltMixedRow::Compact(row)
            }
        }).collect::<Vec<_>>();
        assert_eq!(digit_windows.len(),ALT_SPLIT_PRIME_STEPS);
        assert_eq!(ALT_MIXED_FULL_ROW_MASK.count_ones(),8);
        let retained_bytes = full_entries*size_of::<U256TwoXAffine>()
            + (compact_entries+terminal_pairs.len())*size_of::<U256Affine>()
            + digit_pairs.len()*size_of::<(i16,i16)>()
            + (digit_codes.len()+terminal_codes.len())*size_of::<(u16,u8)>()
            + size_of::<[super::U256;3]>() + size_of::<Self>()
            + digit_windows.capacity()*size_of::<AltMixedRow>();
        assert!(retained_bytes < 32*1024*1024);
        Self { digit_pairs,digit_codes,digit_windows,terminal_pairs,
               terminal_codes,retained_bytes }
    }
}

static ALT_MIXED_TABLES: LazyLock<AltMixedTables> =
    LazyLock::new(AltMixedTables::new);

'''


def main(root: Path) -> None:
    path = root/'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    source = path.read_bytes()
    assert sha256(source).hexdigest() == WINDOWS_SHA256
    text = source.decode()
    marker = 'static ALT_SPLIT_PRIME_TWO_X_TABLES: LazyLock<AltSplitPrimeTwoXTables> ='
    assert text.count(marker) == 1
    text = text.replace(marker,MIXED_TABLE+marker)
    warm_start = text.index('pub(super) fn warm_alt_split_prime_two_x_table()')
    warm_end = text.index('\n}\n',warm_start)+2
    warm = '''pub(super) fn warm_alt_split_prime_two_x_table() -> usize {
    std::sync::LazyLock::force(&super::EXACT_RECIPROCAL_CHECK);
    std::sync::LazyLock::force(&super::FIXED_SCALAR_LATTICE);
    ALT_MIXED_TABLES.retained_bytes
}'''
    text = text[:warm_start]+warm+text[warm_end:]
    start = text.index('fn alt_split_prime_two_x_affine_leaves(')
    end = text.index('pub(super) fn multiply_u256_tau_alt_split_prime_two_x_affine_batch(',start)
    old = text[start:end]
    prefix = old[:old.index('    // Issue the two cache-line requests')]
    assert prefix.count('let tables = &*ALT_SPLIT_PRIME_TWO_X_TABLES;') == 1
    prefix = prefix.replace('let tables = &*ALT_SPLIT_PRIME_TWO_X_TABLES;',
                            'let tables = &*ALT_MIXED_TABLES;')
    tail = '''    #[cfg(target_arch = "x86_64")]
    for (window,&(seed,_)) in choices.iter().enumerate() {
        if seed == 0 { continue; }
        if window < ALT_SPLIT_PRIME_STEPS {
            tables.digit_windows[window].prefetch(seed);
        } else {
            let ptr = &tables.terminal_pairs[seed] as *const U256Affine as *const i8;
            unsafe {
                core::arch::x86_64::_mm_prefetch(ptr, core::arch::x86_64::_MM_HINT_T0);
                core::arch::x86_64::_mm_prefetch(ptr.add(32), core::arch::x86_64::_MM_HINT_T0);
            }
        }
    }
    let mut leaves = [None;ALT_SPLIT_PRIME_STEPS+1];
    for (window,&(seed,unit)) in choices.iter().enumerate() {
        if seed == 0 { continue; }
        leaves[window] = Some(if window < ALT_SPLIT_PRIME_STEPS {
            tables.digit_windows[window].select(seed,unit)
        } else {
            tables.terminal_pairs[seed].unit(unit)
        });
    }
    leaves
}

'''
    updated = (text[:start]+prefix+tail+text[end:]).encode()
    path.write_bytes(updated)
    print('input_sha256='+sha256(source).hexdigest())
    print('output_sha256='+sha256(updated).hexdigest())


if __name__ == '__main__':
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]))
