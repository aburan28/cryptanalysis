#!/usr/bin/env python3
"""Add scalar-local digit-point synthesis to the frozen radix-32 native source."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = '6cd0962b58b4673708af813a913474791400a7297142e4e5970e7af11faf0b34'
WINDOWS_SHA256 = '3bba985851048b4fa7431e8ace04658e341b0ccda469116e7c9bcbb7b54cba3d'

WINDOWS_INSERT = r'''
static ALT_ON_DEMAND_DIGITS: LazyLock<Box<[(i16,i16)]>> = LazyLock::new(|| {
    (0..=ALT_SPLIT_PRIME_DIGIT_LIMIT as i32)
        .map(nearest_alt_split_prime_digit).collect::<Vec<_>>().into_boxed_slice()
});

pub(super) fn multiply_u256_tau_alt_on_demand_batch(
    scalar_words: &[[u64;4]],
) -> (Vec<String>, usize) {
    let mut answers = Vec::with_capacity(scalar_words.len());
    let mut max_selected = 0usize;
    for &words in scalar_words {
        let scalar = super::Uint(words);
        let residue = if bool::from(scalar.ct_lt(&super::SCALAR_ORDER_WORDS)) {
            scalar
        } else {
            super::U256::sbb(&scalar, &super::SCALAR_ORDER_WORDS).0
        };
        let (representative, _, _) =
            super::hexagonal_certified_fixed_choice_words(residue.0);
        let digit_pairs = &*ALT_ON_DEMAND_DIGITS;
        let (mut a, mut b) = representative;
        let mut digits = Vec::with_capacity(ALT_SPLIT_PRIME_STEPS);
        for _ in 0..ALT_SPLIT_PRIME_STEPS {
            let (next_a,next_b,index,sign) =
                alt_split_prime_unit_step(a,b,digit_pairs);
            let (raw_a,raw_b) = digit_pairs[index];
            let digit = if sign == 0 { (raw_a,raw_b) }
                        else { (-raw_a,-raw_b) };
            digits.push(digit);
            a=next_a;
            b=next_b;
        }
        let (ai,aneg) = a.alt_split_prime_table_index(ALT_SPLIT_PRIME_TERMINAL_LIMIT);
        let (bi,bneg) = b.alt_split_prime_table_index(ALT_SPLIT_PRIME_TERMINAL_LIMIT);
        let terminal = (if aneg { -(ai as i16) } else { ai as i16 },
                        if bneg { -(bi as i16) } else { bi as i16 });
        let terminal_norm = i32::from(terminal.0).pow(2)
            + 3*i32::from(terminal.0)*i32::from(terminal.1)
            + 3*i32::from(terminal.1).pow(2);
        assert!(terminal_norm < 5000);
        let mut selected = digits.iter().copied().collect::<std::collections::BTreeSet<_>>();
        selected.insert(terminal);
        selected.remove(&(0,0));
        let mut selected = std::iter::once((0i16,0i16))
            .chain(selected.into_iter()).collect::<Vec<_>>();
        max_selected = max_selected.max(selected.len());
        let points = build_u256_window(&selected,Jacobian::generator());
        let ids = selected.drain(..).enumerate()
            .map(|(index,pair)| (pair,index))
            .collect::<std::collections::BTreeMap<_,_>>();
        let mut accumulator = if terminal == (0,0) {
            U256Jacobian::identity()
        } else {
            U256Jacobian::from_affine(points[ids[&terminal]])
        };
        for digit in digits.into_iter().rev() {
            accumulator = alt_horner_mul_pi(accumulator);
            if digit != (0,0) {
                accumulator = accumulator.add_mixed(points[ids[&digit]]);
            }
        }
        answers.push(accumulator.affine_hex_binary_inverse());
    }
    (answers,max_selected)
}

'''

FRONT_INSERT = r'''
    if args.len() == 2 && args[0] == "--pilot-alt-on-demand" {
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
        let start = Instant::now();
        let (actual,max_selected) =
            unit_orbit_windows::multiply_u256_tau_alt_on_demand_batch(&words);
        let total_ms = start.elapsed().as_secs_f64()*1000.0;
        for (index,point) in actual.iter().enumerate() {
            assert_eq!(point,inputs[index].1,"pilot case {index}");
        }
        println!("verified=1 count={count} online_ms={total_ms:.6} preparation_ms=0.000000 max_selected={max_selected} point={}",actual.last().unwrap());
        return;
    }
'''


def main(root: Path):
    front = root / 'src/bin/eisenstein_fixed.rs'
    windows = root / 'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    assert sha256(front.read_bytes()).hexdigest() == FRONT_SHA256
    assert sha256(windows.read_bytes()).hexdigest() == WINDOWS_SHA256
    front_text = front.read_text()
    windows_text = windows.read_text()
    anchor = '    if args.len() == 2 && args[0] == "--pilot-alt-horner" {'
    assert front_text.count(anchor) == 1
    front.write_text(front_text.replace(anchor,FRONT_INSERT+anchor,1))
    anchor = 'static ALT_SPLIT_PRIME_TWO_X_TABLES: LazyLock<AltSplitPrimeTwoXTables> ='
    assert windows_text.count(anchor) == 1
    windows.write_text(windows_text.replace(anchor,WINDOWS_INSERT+anchor,1))
    print('front_sha256='+sha256(front.read_bytes()).hexdigest())
    print('windows_sha256='+sha256(windows.read_bytes()).hexdigest())


if __name__ == '__main__':
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]))
