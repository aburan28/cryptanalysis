#!/usr/bin/env python3
"""Evaluate the norm-110557 digits by Horner recurrence with one digit row."""

from hashlib import sha256
from pathlib import Path
import sys

WINDOWS_SHA256 = 'f5dcba53fd1db7eb5b2c47cc9ccc3cc85c1c60ca45e1efb53e5f4aab5ff23154'
FRONT_SHA256 = 'a8937e606def2c871a34bb8e35c28566a5adbbe0069abdf08d71f3b99757e0ef'

HORNER_TABLE = '''
struct AltHornerTables {
    digit_pairs: Box<[(i16,i16)]>,
    digit_codes: Box<[(u16,u8)]>,
    digit_window: Box<[U256TwoXAffine]>,
    terminal_pairs: Box<[U256Affine]>,
    terminal_codes: Box<[(u16,u8)]>,
    retained_bytes: usize,
}

impl AltHornerTables {
    fn new() -> Self {
        let digit_pairs = (0..=ALT_SPLIT_PRIME_DIGIT_LIMIT as i32)
            .map(nearest_alt_split_prime_digit).collect::<Vec<_>>().into_boxed_slice();
        assert_eq!(digit_pairs.len(),55279);
        let digit_set = digit_pairs.iter().copied().map(alt_orbit_canonical)
            .collect::<std::collections::BTreeSet<_>>();
        let mut digit_seeds = digit_set.into_iter().collect::<Vec<_>>();
        digit_seeds.retain(|&pair| pair != (0,0));
        digit_seeds.insert(0,(0,0));
        assert!(digit_seeds.len() < u16::MAX as usize);
        let digit_ids = digit_seeds.iter().enumerate()
            .map(|(index,&pair)| (pair,index as u16))
            .collect::<std::collections::BTreeMap<_,_>>();
        let digit_codes = digit_pairs.iter().copied().map(|pair| {
            let seed = alt_orbit_canonical(pair);
            (digit_ids[&seed],alt_orbit_code(pair,seed))
        }).collect::<Vec<_>>().into_boxed_slice();
        let base = Jacobian::generator();
        let digit_window = build_u256_window(&digit_seeds,base).iter().copied()
            .map(U256TwoXAffine::from_affine)
            .collect::<Vec<_>>().into_boxed_slice();
        // The terminal point starts the Horner recurrence and is based at G.
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
        assert!(terminal_seeds.len() < u16::MAX as usize);
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
        let retained_bytes = digit_window.len()*size_of::<U256TwoXAffine>()
            + terminal_pairs.len()*size_of::<U256Affine>()
            + digit_pairs.len()*size_of::<(i16,i16)>()
            + (digit_codes.len()+terminal_codes.len())*size_of::<(u16,u8)>()
            + size_of::<[super::U256;3]>() + size_of::<Self>();
        assert!(retained_bytes < 32*1024*1024);
        Self { digit_pairs,digit_codes,digit_window,terminal_pairs,
               terminal_codes,retained_bytes }
    }
}

static ALT_HORNER_TABLES: LazyLock<AltHornerTables> =
    LazyLock::new(AltHornerTables::new);

fn alt_horner_mul_pi(point: U256Jacobian) -> U256Jacobian {
    if point.is_identity() { return point; }
    // 334 = 256 + 64 + 8 + 4 + 2, and pi = 334 - tau.
    let p2 = point.double();
    let p4 = p2.double();
    let p8 = p4.double();
    let p16 = p8.double();
    let p32 = p16.double();
    let p64 = p32.double();
    let p128 = p64.double();
    let p256 = p128.double();
    let multiple = p256.add_projective(p64).add_projective(p8)
        .add_projective(p4).add_projective(p2);
    let tau = point.tau();
    let neg_tau = U256Jacobian {
        y: u256_sub(super::U256::ZERO,tau.y), ..tau
    };
    multiple.add_projective(neg_tau)
}

'''


def main(root: Path) -> None:
    front = root/'src/bin/eisenstein_fixed.rs'
    path = root/'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    source = path.read_bytes()
    front_source = front.read_bytes()
    assert sha256(source).hexdigest() == WINDOWS_SHA256
    assert sha256(front_source).hexdigest() == FRONT_SHA256
    text = source.decode()
    anchor = 'static ALT_SPLIT_PRIME_TWO_X_TABLES: LazyLock<AltSplitPrimeTwoXTables> ='
    assert text.count(anchor) == 1
    text = text.replace(anchor,HORNER_TABLE+anchor)
    warm_start = text.index('pub(super) fn warm_alt_split_prime_two_x_table()')
    warm_end = text.index('\n}\n',warm_start)+2
    warm = '''pub(super) fn warm_alt_split_prime_two_x_table() -> usize {
    std::sync::LazyLock::force(&super::EXACT_RECIPROCAL_CHECK);
    std::sync::LazyLock::force(&super::FIXED_SCALAR_LATTICE);
    ALT_HORNER_TABLES.retained_bytes
}'''
    text = text[:warm_start]+warm+text[warm_end:]
    start = text.index('fn alt_split_prime_two_x_affine_leaves(')
    end = text.index('\n\n\n#[cfg(test)]',start)
    old = text[start:end]
    prefix = old[:old.index('    // Issue the two cache-line requests')]
    prefix = prefix.replace(
        'fn alt_split_prime_two_x_affine_leaves(scalar_words: [u64;4])\n'
        '    -> [Option<U256Affine>; ALT_SPLIT_PRIME_STEPS+1] {',
        'fn alt_horner_scalar_hex(scalar_words: [u64;4]) -> String {')
    assert 'fn alt_horner_scalar_hex' in prefix
    assert prefix.count('let tables = &*ALT_SPLIT_PRIME_TWO_X_TABLES;') == 1
    prefix = prefix.replace('let tables = &*ALT_SPLIT_PRIME_TWO_X_TABLES;',
                            'let tables = &*ALT_HORNER_TABLES;')
    prefix = prefix.replace('for (window,_) in tables.digit_windows.iter().enumerate() {',
                            'for window in 0..ALT_SPLIT_PRIME_STEPS {')
    assert 'for window in 0..ALT_SPLIT_PRIME_STEPS' in prefix
    tail = '''    let (seed,unit) = choices[ALT_SPLIT_PRIME_STEPS];
    let mut accumulator = if seed == 0 { U256Jacobian::identity() } else {
        U256Jacobian::from_affine(tables.terminal_pairs[seed].unit(unit))
    };
    for &(seed,unit) in choices[..ALT_SPLIT_PRIME_STEPS].iter().rev() {
        accumulator = alt_horner_mul_pi(accumulator);
        if seed != 0 {
            accumulator = accumulator.add_mixed(tables.digit_window[seed].unit(unit));
        }
    }
    accumulator.affine_hex_binary_inverse()
}

pub(super) fn multiply_u256_tau_alt_split_prime_two_x_affine_batch(
    scalar_words: &[[u64;4]],
) -> Vec<String> {
    scalar_words.iter().copied().map(alt_horner_scalar_hex).collect()
}
'''
    updated = (text[:start]+prefix+tail+text[end:]).encode()
    path.write_bytes(updated)
    front_text = front_source.decode()
    dispatch = '''    if args.len() == 2 && args[0] == "--pilot-alt-horner" {
        let count: usize = args[1].parse().expect("pilot count");
        let panel: Value = serde_json::from_str(include_str!("mixed640_uniform_fixture.json"))
            .expect("parse fixture");
        let cases = panel["cases"].as_array().unwrap();
        assert!(count > 0 && count <= cases.len());
        let inputs = cases.iter().take(count).map(|case| {
            let scalar = BigInt::parse_bytes(
                case["scalar_hex"].as_str().unwrap().as_bytes(),16).unwrap();
            (scalar_words_256(&scalar).unwrap(),case["point_hex"].as_str().unwrap())
        }).collect::<Vec<_>>();
        let words = inputs.iter().map(|&(words,_)| words).collect::<Vec<_>>();
        let preparation_start = Instant::now();
        let retained_bytes = unit_orbit_windows::warm_alt_split_prime_two_x_table();
        let preparation_ms = preparation_start.elapsed().as_secs_f64()*1000.0;
        let start = Instant::now();
        let actual = unit_orbit_windows::multiply_u256_tau_alt_split_prime_two_x_affine_batch(&words);
        let online_ms = start.elapsed().as_secs_f64()*1000.0;
        assert_eq!(actual.len(),count);
        for (index,point) in actual.iter().enumerate() {
            assert_eq!(point,inputs[index].1,"pilot case {index}");
        }
        println!("verified=1 count={count} online_ms={online_ms:.6} preparation_ms={preparation_ms:.6} retained_bytes={retained_bytes} point={}",actual.last().unwrap());
        return;
    }
'''
    needle = '    let args: Vec<String> = std::env::args().skip(1).collect();\n'
    assert front_text.count(needle) == 1
    front_text = front_text.replace(needle,needle+dispatch,1)
    front_updated = front_text.encode()
    front.write_bytes(front_updated)
    print('input_sha256='+sha256(source).hexdigest())
    print('output_sha256='+sha256(updated).hexdigest())
    print('front_input_sha256='+sha256(front_source).hexdigest())
    print('front_output_sha256='+sha256(front_updated).hexdigest())


if __name__ == '__main__':
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]))
