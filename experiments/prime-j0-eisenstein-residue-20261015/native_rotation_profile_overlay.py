#!/usr/bin/env python3
"""Instrument the frozen radix-14 recoder without changing its arithmetic."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = "3dead29b00d7c5bd84851bd59b29eb477480daf05e008debaffbfb002c7b8f6b"
WINDOWS_SHA256 = "71136ada79d64d136344c8649fe59a07ceb6cbcc03f30a1e66c3f1bc4848bf5d"

PROFILE = r'''pub(super) fn profile_split_prime_units(scalars: &[[u64;4]]) -> [[u64;3];15] {
    let tables = &*SPLIT_PRIME_TABLES;
    let mut counts = [[0u64;3];15];
    for &words in scalars {
        let scalar = super::Uint(words);
        let residue = if bool::from(scalar.ct_lt(&super::SCALAR_ORDER_WORDS)) {
            scalar
        } else {
            super::U256::sbb(&scalar, &super::SCALAR_ORDER_WORDS).0
        };
        let (representative, _, _) = super::hexagonal_certified_fixed_choice_words(residue.0);
        let (mut a, mut b) = representative;
        for window in 0..SPLIT_PRIME_STEPS {
            let (next_a,next_b,index,sign) = split_prime_unit_step(a,b,&tables.digit_pairs);
            a=next_a;
            b=next_b;
            if index != 0 {
                let (seed,code) = tables.digit_codes[index];
                if seed != 0 { counts[window][(usize::from(code)^sign)/2] += 1; }
            }
        }
        let (ai,aneg) = a.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);
        let (bi,bneg) = b.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);
        let signed_a = if aneg { -(ai as i32) } else { ai as i32 };
        let signed_b = if bneg { -(bi as i32) } else { bi as i32 };
        if signed_a != 0 || signed_b != 0 {
            let index = ((signed_a+445)*891+signed_b+445) as usize;
            let (seed,code) = tables.terminal_codes[index];
            assert_ne!(seed,u16::MAX);
            if seed != 0 { counts[SPLIT_PRIME_STEPS][usize::from(code)/2] += 1; }
        }
    }
    counts
}

'''


def main(root: Path) -> None:
    front = root / "src/bin/eisenstein_fixed.rs"
    windows = root / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    f, w = front.read_text(), windows.read_text()
    assert sha256(f.encode()).hexdigest() == FRONT_SHA256
    assert sha256(w.encode()).hexdigest() == WINDOWS_SHA256
    anchor = "struct SplitPrimeCacheBudgetTables {"
    assert w.count(anchor) == 1
    w = w.replace(anchor, PROFILE + anchor, 1)
    dispatch = '''    if args.len() == 2 && args[0] == "--profile-split-prime-units" {
        let panel: Value = serde_json::from_slice(&fs::read(&args[1]).unwrap()).unwrap();
        let cases = panel["cases"].as_array().unwrap();
        let words = cases.iter().map(|case| {
            let scalar = BigInt::parse_bytes(
                case["scalar_hex"].as_str().unwrap().as_bytes(),16).unwrap();
            scalar_words_256(&scalar).unwrap()
        }).collect::<Vec<_>>();
        let counts = unit_orbit_windows::profile_split_prime_units(&words);
        println!("{}", serde_json::json!({"schema":1,"count":words.len(),
            "unit_class_counts":counts}));
        return;
    }
'''
    needle = "    let args: Vec<String> = std::env::args().skip(1).collect();\n"
    assert f.count(needle) == 1
    f = f.replace(needle, needle + dispatch, 1)
    front.write_text(f)
    windows.write_text(w)
    print("front_sha256=" + sha256(f.encode()).hexdigest())
    print("windows_sha256=" + sha256(w.encode()).hexdigest())


if __name__ == "__main__":
    main(Path(sys.argv[1]))
