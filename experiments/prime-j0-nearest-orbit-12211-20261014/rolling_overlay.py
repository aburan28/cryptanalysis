#!/usr/bin/env python3
"""Evaluate six-unit orbit seeds by a descending, one-bucket unit gauge."""
from hashlib import sha256
from pathlib import Path
import sys

PARENT_SHA256 = '2f31c4e0b4ed0fc67d3eb72866644364d1c0c256a7e7c20e97335df1ff3e7dc2'


def main(root):
    path = root/'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    source = path.read_text()
    assert sha256(source.encode()).hexdigest() == PARENT_SHA256
    start = source.index('pub(super) fn multiply_u256_tau_split_prime_radix(\n')
    end = source.index('\n#[cfg(test)]\nmod split_prime_tests {',start)
    source = source[:start] + '''pub(super) fn multiply_u256_tau_split_prime_radix(
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
    // The last slot holds the terminal term. Choices contain only a seed and
    // unit code; all points remain in the original precomputed affine rows.
    let mut choices = [(0usize,0usize); SPLIT_PRIME_STEPS+1];
    for (window,_) in tables.digit_windows.iter().enumerate() {
        let (next_a,next_b,index,sign) = split_prime_unit_step(a,b,tables);
        a=next_a;
        b=next_b;
        if index != 0 {
            let (seed,code) = tables.digit_codes[index];
            choices[window]=(usize::from(seed),usize::from(code)^sign);
        }
    }
    let (ai,aneg) = a.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);
    let (bi,bneg) = b.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);
    let signed_a = if aneg { -(ai as i64) } else { ai as i64 };
    let signed_b = if bneg { -(bi as i64) } else { bi as i64 };
    let terminal_norm = signed_a*signed_a+3*signed_a*signed_b
        +3*signed_b*signed_b;
    assert!(terminal_norm < 1156,"nearest-digit norm-12211 terminal bound");
    let negate = signed_a < 0 || (signed_a == 0 && signed_b < 0);
    let ca = if negate { -signed_a } else { signed_a } as usize;
    let cb = if negate { -signed_b } else { signed_b };
    let row_start = tables.terminal_row_start[ca] as usize;
    let row_offset = usize::try_from(
        cb-i64::from(tables.terminal_row_min[ca])).unwrap();
    let index = row_start+row_offset;
    assert!(index < tables.terminal_row_start[ca+1] as usize);
    if index != 0 {
        let (seed,code) = tables.terminal_codes[index];
        choices[SPLIT_PRIME_STEPS] =
            (usize::from(seed),usize::from(code)^usize::from(negate));
    }

    let mut bucket=U256XYZZ::identity();
    let mut gauge=0usize;
    let mut occupied=false;
    let mut terms=0usize;
    let mut ops=SplitPrimeOpCounts::default();
    // Horner order: S_0 + omega(S_1 + omega(S_2)). At each transition the
    // whole accumulator is rotated once; selected affine points stay plain.
    for class in [2usize,1,0] {
        let mut class_started=false;
        for (window,&(seed,unit)) in choices.iter().enumerate() {
            if seed == 0 || unit/2 != class { continue; }
            if !class_started {
                if occupied {
                    let delta=(gauge+3-class)%3;
                    if delta != 0 && !bucket.is_identity() {
                        bucket=bucket.rotate_power_solinas(delta);
                        ops.bucket_x_const_multiplies+=1;
                    }
                }
                gauge=class;
                occupied=true;
                class_started=true;
            }
            let mut point=if window < SPLIT_PRIME_STEPS {
                ops.digit_point_reads+=1;
                tables.digit_windows[window][seed]
            } else {
                ops.terminal_point_reads+=1;
                tables.terminal_pairs[seed]
            };
            if unit & 1 != 0 {
                point.y=u256_sub(super::U256::ZERO,point.y);
                ops.sign_flips+=1;
            }
            if !bucket.is_identity() { ops.mixed_add_nontrivial+=1; }
            bucket=bucket.add_mixed(point);
            terms+=1;
        }
    }
    if occupied && gauge != 0 && !bucket.is_identity() {
        bucket=bucket.rotate_power_solinas(gauge);
        ops.bucket_x_const_multiplies+=1;
    }
    assert!(ops.bucket_x_const_multiplies <= 2);
    let point=bucket.affine_hex_binary_inverse();
    debug_assert!(ops.mixed_add_nontrivial+ops.projective_join_nontrivial
                  <= terms.saturating_sub(1));
    (point,representative,
     ops.mixed_add_nontrivial+ops.projective_join_nontrivial,
     tables.retained_bytes,fallback,corner,0,ops)
}
''' + source[end:]
    path.write_text(source)
    print(sha256(path.read_bytes()).hexdigest())


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: rolling_overlay.py CARGO_ROOT')
    main(Path(sys.argv[1]))
