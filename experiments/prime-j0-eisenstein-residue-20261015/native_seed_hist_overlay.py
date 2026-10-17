#!/usr/bin/env python3
"""Export complete seed histograms for cross-stream cache-hit validation."""

from hashlib import sha256
from pathlib import Path
import sys

from native_seed_profile_overlay import PROFILE

FRONT_SHA256 = "909f2f91fffcb27461f4b3fed7d15b29193b5a61abcf128ad086f7ef8fbf8a6e"
WINDOWS_SHA256 = "42c2be6187daeac320859531f6a035625fd0fcf63980a3448dd5ac1bcb632150"


def main(root: Path) -> None:
    front = root / "src/bin/eisenstein_fixed.rs"
    windows = root / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    f, w = front.read_text(), windows.read_text()
    assert sha256(f.encode()).hexdigest() == FRONT_SHA256
    assert sha256(w.encode()).hexdigest() == WINDOWS_SHA256
    hist = PROFILE.replace("profile_split_prime_seeds", "profile_split_prime_seed_hist")
    hist = hist.replace("-> Vec<[u64;6]>", "-> Vec<Vec<u32>>")
    start = hist.index("    hist.into_iter().map(|mut values| {")
    end = hist.index("}).collect()", start) + len("}).collect()")
    hist = hist[:start] + "    hist" + hist[end:]
    assert "pub(super) fn profile_split_prime_seed_hist" in hist
    assert "-> Vec<Vec<u32>>" in hist
    anchor = "struct SplitPrimeCacheBudgetTables {"
    assert w.count(anchor) == 1
    w = w.replace(anchor, hist + anchor, 1)
    dispatch = '''    if args.len() == 2 && args[0] == "--profile-split-prime-seed-hist" {
        let panel: Value = serde_json::from_slice(&fs::read(&args[1]).unwrap()).unwrap();
        let cases = panel["cases"].as_array().unwrap();
        let words = cases.iter().map(|case| {
            let scalar = BigInt::parse_bytes(
                case["scalar_hex"].as_str().unwrap().as_bytes(),16).unwrap();
            scalar_words_256(&scalar).unwrap()
        }).collect::<Vec<_>>();
        let hist = unit_orbit_windows::profile_split_prime_seed_hist(&words);
        println!("{}", serde_json::json!({"schema":1,"count":words.len(),"hist":hist}));
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
