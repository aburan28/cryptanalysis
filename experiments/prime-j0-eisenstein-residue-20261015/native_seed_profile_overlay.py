#!/usr/bin/env python3
"""Summarize per-seed lookup skew on frozen independently generated scalars."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = "b2d8ba41c651e203697efbcd90d27e40ed6f698f40b82f0fcb5b53d4ae0231f2"
WINDOWS_SHA256 = "afa29391de879b7d8f1f01b313058efe7313ee0cd3e6f042312aaedb34c57193"

PROFILE = r'''pub(super) fn profile_split_prime_seeds(scalars: &[[u64;4]]) -> Vec<[u64;6]> {
    let tables = &*SPLIT_PRIME_TABLES;
    let mut hist = vec![vec![0u32;22756];SPLIT_PRIME_STEPS];
    hist.push(vec![0u32;30071]);
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
            let (next_a,next_b,index,_) = split_prime_unit_step(a,b,&tables.digit_pairs);
            a=next_a;
            b=next_b;
            if index != 0 {
                let (seed,_) = tables.digit_codes[index];
                if seed != 0 { hist[window][usize::from(seed)] += 1; }
            }
        }
        let (ai,aneg) = a.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);
        let (bi,bneg) = b.split_prime_table_index(SPLIT_PRIME_TERMINAL_LIMIT);
        let signed_a = if aneg { -(ai as i32) } else { ai as i32 };
        let signed_b = if bneg { -(bi as i32) } else { bi as i32 };
        if signed_a != 0 || signed_b != 0 {
            let index = ((signed_a+445)*891+signed_b+445) as usize;
            let (seed,_) = tables.terminal_codes[index];
            assert_ne!(seed,u16::MAX);
            if seed != 0 { hist[SPLIT_PRIME_STEPS][usize::from(seed)] += 1; }
        }
    }
    hist.into_iter().map(|mut values| {
        values.sort_unstable_by(|a,b| b.cmp(a));
        [values.iter().map(|&x| u64::from(x)).sum(),
         values.iter().filter(|&&x| x != 0).count() as u64,
         values.iter().take(100).map(|&x| u64::from(x)).sum(),
         values.iter().take(1000).map(|&x| u64::from(x)).sum(),
         values.iter().take(5000).map(|&x| u64::from(x)).sum(),
         u64::from(values[0])]
    }).collect()
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
    dispatch = '''    if args.len() == 2 && args[0] == "--profile-split-prime-seeds" {
        let panel: Value = serde_json::from_slice(&fs::read(&args[1]).unwrap()).unwrap();
        let cases = panel["cases"].as_array().unwrap();
        let words = cases.iter().map(|case| {
            let scalar = BigInt::parse_bytes(
                case["scalar_hex"].as_str().unwrap().as_bytes(),16).unwrap();
            scalar_words_256(&scalar).unwrap()
        }).collect::<Vec<_>>();
        let summary = unit_orbit_windows::profile_split_prime_seeds(&words);
        println!("{}", serde_json::json!({"schema":1,"count":words.len(),
            "columns":["total","distinct","top100","top1000","top5000","max"],
            "seed_usage":summary}));
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
