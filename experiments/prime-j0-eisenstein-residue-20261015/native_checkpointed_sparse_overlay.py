#!/usr/bin/env python3
"""Five checkpoint rows for fifteen sparse-radix digits, three per block."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = '6cd0962b58b4673708af813a913474791400a7297142e4e5970e7af11faf0b34'
WINDOWS_SHA256 = 'c89602515460ab1e5f4a309b78bc28313ad991c46cec58b53e3383ac292378a8'

TABLES = '''const CHECKPOINT_WIDTH: usize = 3;
const CHECKPOINT_ROWS: usize = ALT_SPLIT_PRIME_STEPS/CHECKPOINT_WIDTH;

fn checkpoint_base_step(base: Jacobian) -> Jacobian {
    // The same 127+128*tau action used by the scalar Horner path.
    let mixed = base.add_mixed(base.tau().into_affine());
    let scaled = affine_multiples(mixed,128).pop().unwrap();
    scaled.add_mixed(base.neg().into_affine()).into_affine()
}

struct AltCheckpointTables {
    digit_pairs: Box<[(i16,i16)]>,
    digit_codes: Box<[(u16,u8)]>,
    digit_windows: Vec<Box<[U256TwoXAffine]>>,
    terminal_pairs: Box<[U256Affine]>,
    terminal_codes: Box<[(u16,u8)]>,
    retained_bytes: usize,
}

impl AltCheckpointTables {
    fn new() -> Self {
        assert_eq!(ALT_SPLIT_PRIME_STEPS,CHECKPOINT_ROWS*CHECKPOINT_WIDTH);
        let digit_pairs = (0..=ALT_SPLIT_PRIME_DIGIT_LIMIT as i32)
            .map(nearest_alt_split_prime_digit).collect::<Vec<_>>().into_boxed_slice();
        assert_eq!(digit_pairs.len(),57025);
        let digit_set = digit_pairs.iter().copied().map(alt_orbit_canonical)
            .collect::<std::collections::BTreeSet<_>>();
        let mut digit_seeds = digit_set.into_iter().collect::<Vec<_>>();
        digit_seeds.retain(|&pair| pair != (0,0));
        digit_seeds.insert(0,(0,0));
        assert_eq!(digit_seeds.len(),19009);
        let digit_ids = digit_seeds.iter().enumerate()
            .map(|(index,&pair)| (pair,index as u16))
            .collect::<std::collections::BTreeMap<_,_>>();
        let digit_codes = digit_pairs.iter().copied().map(|pair| {
            let seed = alt_orbit_canonical(pair);
            (digit_ids[&seed],alt_orbit_code(pair,seed))
        }).collect::<Vec<_>>().into_boxed_slice();
        let mut base = Jacobian::generator();
        let mut digit_windows = Vec::with_capacity(CHECKPOINT_ROWS);
        for _ in 0..CHECKPOINT_ROWS {
            digit_windows.push(build_u256_window(&digit_seeds,base).iter().copied()
                .map(U256TwoXAffine::from_affine).collect::<Vec<_>>().into_boxed_slice());
            for _ in 0..CHECKPOINT_WIDTH { base = checkpoint_base_step(base); }
        }
        // Base is now pi^15 G. The terminal pair must use this base.
        let mut terminal_pairs_full = Vec::new();
        for a in -100..=100i32 {
            for b in -100..=100i32 {
                let norm = a*a+3*a*b+3*b*b;
                if norm < 5000 { terminal_pairs_full.push((a as i16,b as i16)); }
            }
        }
        let terminal_set = terminal_pairs_full.iter().copied().map(alt_orbit_canonical)
            .collect::<std::collections::BTreeSet<_>>();
        let mut terminal_seeds = terminal_set.into_iter().collect::<Vec<_>>();
        terminal_seeds.retain(|&pair| pair != (0,0));
        terminal_seeds.insert(0,(0,0));
        let terminal_ids = terminal_seeds.iter().enumerate()
            .map(|(index,&pair)| (pair,index as u16))
            .collect::<std::collections::BTreeMap<_,_>>();
        let mut terminal_codes = vec![(u16::MAX,0u8);201*201];
        for pair in terminal_pairs_full.iter().copied() {
            let seed = alt_orbit_canonical(pair);
            let index = ((i32::from(pair.0)+100)*201+i32::from(pair.1)+100) as usize;
            terminal_codes[index]=(terminal_ids[&seed],alt_orbit_code(pair,seed));
        }
        let terminal_codes = terminal_codes.into_boxed_slice();
        let terminal_pairs = build_u256_window(&terminal_seeds,base);
        let entries = digit_windows.iter().map(|row| row.len()).sum::<usize>();
        assert_eq!(entries,CHECKPOINT_ROWS*digit_seeds.len());
        let retained_bytes = entries*size_of::<U256TwoXAffine>()
            + terminal_pairs.len()*size_of::<U256Affine>()
            + digit_pairs.len()*size_of::<(i16,i16)>()
            + (digit_codes.len()+terminal_codes.len())*size_of::<(u16,u8)>()
            + size_of::<[super::U256;3]>() + size_of::<Self>()
            + digit_windows.capacity()*size_of::<Box<[U256TwoXAffine]>>();
        assert!(retained_bytes < 32*1024*1024);
        Self { digit_pairs,digit_codes,digit_windows,terminal_pairs,
               terminal_codes,retained_bytes }
    }
}

static ALT_HORNER_TABLES: LazyLock<AltCheckpointTables> =
    LazyLock::new(AltCheckpointTables::new);

'''

EVALUATE = '''    let (terminal_seed,terminal_unit) = choices[ALT_SPLIT_PRIME_STEPS];
    let mut accumulator = if terminal_seed == 0 { U256Jacobian::identity() } else {
        U256Jacobian::from_affine(tables.terminal_pairs[terminal_seed].unit(terminal_unit))
    };
    for block in 0..CHECKPOINT_ROWS {
        let row = &tables.digit_windows[block];
        let mut partial = U256Jacobian::identity();
        for local in (0..CHECKPOINT_WIDTH).rev() {
            if local != CHECKPOINT_WIDTH-1 { partial = alt_horner_mul_pi(partial); }
            let (seed,unit) = choices[block*CHECKPOINT_WIDTH+local];
            if seed != 0 { partial = partial.add_mixed(row[seed].unit(unit)); }
        }
        accumulator = accumulator.add_projective(partial);
    }
    accumulator.affine_hex_binary_inverse()
}

'''


def main(root: Path):
    front = root/'src/bin/eisenstein_fixed.rs'
    windows = root/'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    assert sha256(front.read_bytes()).hexdigest() == FRONT_SHA256
    assert sha256(windows.read_bytes()).hexdigest() == WINDOWS_SHA256
    source = windows.read_text()
    start = source.index('struct AltHornerTables {')
    end = source.index('fn alt_horner_mul_pi(',start)
    assert source[start:end].count('static ALT_HORNER_TABLES:') == 1
    source = source[:start]+TABLES+source[end:]
    start = source.index('    let (seed,unit) = choices[ALT_SPLIT_PRIME_STEPS];',
                         source.index('fn alt_horner_scalar_hex('))
    end = source.index('pub(super) fn multiply_u256_tau_alt_split_prime_two_x_affine_batch(',start)
    source = source[:start]+EVALUATE+source[end:]
    windows.write_text(source)
    print('front_sha256='+sha256(front.read_bytes()).hexdigest())
    print('windows_sha256='+sha256(windows.read_bytes()).hexdigest())


if __name__ == '__main__':
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]))
