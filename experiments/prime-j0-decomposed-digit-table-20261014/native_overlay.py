#!/usr/bin/env python3
"""Replace the frozen 17-position orbit table with a shared unit-basis table."""
from hashlib import sha256
from pathlib import Path
import sys

PARENT_SHA256 = 'e195374c4e6fde368bdba106c769c6335cd319f9f5547e8e2291089fe055335e'

TABLES = r'''struct SplitPrimeTables {
    digit_pairs: Box<[(i16, i16)]>,
    digit_windows: Vec<Box<[U256Affine]>>,
    terminal_pairs: Box<[U256Affine]>,
    retained_bytes: usize,
}

impl SplitPrimeTables {
    fn new() -> Self {
        let digit_pairs = (0..=SPLIT_PRIME_DIGIT_LIMIT as i32)
            .map(nearest_split_prime_digit).collect::<Vec<_>>().into_boxed_slice();
        assert_eq!(digit_pairs.len(), 9592);
        assert_eq!(digit_pairs.iter().map(|&(a,b)| {
            let (a,b)=(i32::from(a),i32::from(b));
            a*a+3*a*b+3*b*b
        }).max(), Some(6348));
        assert_eq!(digit_pairs.iter().map(|&(a,b)| {
            let (a,b)=(i32::from(a),i32::from(b));
            (a+b).abs().max(b.abs())
        }).max(), Some(92));

        // The second coordinate uses omega=1-tau, an inexpensive j=0 unit.
        // For d=a+b*tau, d=(a+b)-b*omega. The same positive multiple table
        // serves both coordinate buckets; each bucket is rotated only once.
        let positive_digits = (0..=92i16).map(|i| (i,0))
            .collect::<Vec<_>>();
        let terminal_digits = (0..=90i16).map(|i| (i,0))
            .collect::<Vec<_>>();
        let mut base = Jacobian::generator();
        let mut digit_windows = Vec::with_capacity(SPLIT_PRIME_STEPS);
        for _ in 0..SPLIT_PRIME_STEPS {
            digit_windows.push(build_u256_window(&positive_digits, base));
            let ordinary = affine_multiples(base, 140).pop().unwrap();
            let tau = base.tau().neg().into_affine();
            base = ordinary.add_mixed(tau).into_affine();
        }
        let terminal_pairs = build_u256_window(&terminal_digits, base);
        assert_eq!(digit_windows.iter().map(|row| row.len()).sum::<usize>(),17*93);
        assert_eq!(terminal_pairs.len(),91);
        assert_eq!(size_of::<U256Affine>(),64);
        let retained_bytes = (17*93+91)*size_of::<U256Affine>()
            + digit_pairs.len()*size_of::<(i16,i16)>()
            + size_of::<[super::U256;3]>() + size_of::<Self>()
            + digit_windows.capacity()*size_of::<Box<[U256Affine]>>();
        Self { digit_pairs,digit_windows,terminal_pairs,retained_bytes }
    }
}

'''

MULTIPLY = r'''pub(super) fn multiply_u256_tau_split_prime_radix(
    scalar_words: [u64; 4],
) -> (String, (Signed192, Signed192), usize, usize, bool, usize, usize, SplitPrimeOpCounts) {
    let scalar = super::Uint(scalar_words);
    let residue = if bool::from(scalar.ct_lt(&super::SCALAR_ORDER_WORDS)) {
        scalar
    } else {
        super::U256::sbb(&scalar, &super::SCALAR_ORDER_WORDS).0
    };
    let (representative, fallback, corner) =
        super::hexagonal_certified_fixed_choice_words(residue.0);
    let tables = &*SPLIT_PRIME_TABLES;
    let (mut a, mut b) = representative;
    // Coordinate zero is 1, coordinate one is omega=1-tau.
    let mut choices = [(0i16,0i16); SPLIT_PRIME_STEPS+1];
    for window in 0..SPLIT_PRIME_STEPS {
        let (next_a,next_b,index,sign) = split_prime_unit_step(a,b,tables);
        a=next_a;
        b=next_b;
        let (raw_da,raw_db) = tables.digit_pairs[index];
        let da = if sign != 0 { -i32::from(raw_da) } else { i32::from(raw_da) };
        let db = if sign != 0 { -i32::from(raw_db) } else { i32::from(raw_db) };
        let (x,y) = (da+db,-db);
        assert!(x.abs() <= 92 && y.abs() <= 92);
        choices[window]=(x.try_into().unwrap(),y.try_into().unwrap());
    }
    let (ai,aneg) = a.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);
    let (bi,bneg) = b.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);
    let signed_a = if aneg { -(ai as i32) } else { ai as i32 };
    let signed_b = if bneg { -(bi as i32) } else { bi as i32 };
    let terminal_norm = signed_a*signed_a+3*signed_a*signed_b
        +3*signed_b*signed_b;
    assert!(terminal_norm < 6084,"nearest-digit norm-19183 terminal bound");
    let (terminal_x,terminal_y)=(signed_a+signed_b,-signed_b);
    assert!(terminal_x.abs() <= 90 && terminal_y.abs() <= 90);
    choices[SPLIT_PRIME_STEPS]=(
        terminal_x.try_into().unwrap(),terminal_y.try_into().unwrap());

    let mut buckets=[U256XYZZ::identity(),U256XYZZ::identity()];
    let mut ops=SplitPrimeOpCounts::default();
    let mut terms=0usize;
    for class in 0..2usize {
        for (window,&(x,y)) in choices.iter().enumerate() {
            let coefficient=if class == 0 { x } else { y };
            if coefficient == 0 { continue; }
            let magnitude=coefficient.unsigned_abs() as usize;
            let mut point=if window < SPLIT_PRIME_STEPS {
                ops.digit_point_reads+=1;
                tables.digit_windows[window][magnitude]
            } else {
                ops.terminal_point_reads+=1;
                tables.terminal_pairs[magnitude]
            };
            if coefficient < 0 {
                point.y=u256_sub(super::U256::ZERO,point.y);
                ops.sign_flips+=1;
            }
            if !buckets[class].is_identity() { ops.mixed_add_nontrivial+=1; }
            buckets[class]=buckets[class].add_mixed(point);
            terms+=1;
        }
    }
    let mut second=buckets[1];
    if !second.is_identity() {
        second=second.rotate_power_solinas(1);
        ops.bucket_x_const_multiplies+=1;
    }
    let result=if buckets[0].is_identity() { second }
               else if second.is_identity() { buckets[0] }
               else {
                   ops.projective_join_nontrivial+=1;
                   buckets[0].add_xyzz(second)
               };
    let point=result.affine_hex_binary_inverse();
    debug_assert!(ops.mixed_add_nontrivial+ops.projective_join_nontrivial
                  <= terms.saturating_sub(1));
    (point,representative,
     ops.mixed_add_nontrivial+ops.projective_join_nontrivial,
     tables.retained_bytes,fallback,corner,0,ops)
}

'''


def main(root):
    path = root / 'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    original = path.read_text()
    assert sha256(original.encode()).hexdigest() == PARENT_SHA256
    start = original.index('struct SplitPrimeTables {')
    end = original.index('static SPLIT_PRIME_TABLES:', start)
    source = original[:start] + TABLES + original[end:]
    start = source.index('pub(super) fn multiply_u256_tau_split_prime_radix(')
    end = source.index('#[cfg(test)]\nmod split_prime_tests', start)
    source = source[:start] + MULTIPLY + source[end:]
    path.write_text(source)
    print(sha256(source.encode()).hexdigest())


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: native_overlay.py CARGO_ROOT')
    main(Path(sys.argv[1]))
