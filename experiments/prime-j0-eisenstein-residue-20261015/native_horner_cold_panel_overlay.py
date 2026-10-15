#!/usr/bin/env python3
"""Add a bounded, exact single-scalar pilot to the frozen prefetch reference."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = 'a8937e606def2c871a34bb8e35c28566a5adbbe0069abdf08d71f3b99757e0ef'
WINDOWS_SHA256 = 'f5dcba53fd1db7eb5b2c47cc9ccc3cc85c1c60ca45e1efb53e5f4aab5ff23154'
FIXTURE_SHA256 = 'a1c4964f174e36ea26f6a1897128f651a2ce7251e4bf4ffd532ff09221e721d3'

DISPATCH = '''    if args.len() == 1 && args[0] == "--pilot-alt-prefetch-one" {
        let panel: Value = serde_json::from_str(include_str!("mixed640_uniform_fixture.json"))
            .expect("parse fixture");
        let case = &panel["cases"].as_array().unwrap()[0];
        let scalar = BigInt::parse_bytes(
            case["scalar_hex"].as_str().unwrap().as_bytes(),16).unwrap();
        let words = [scalar_words_256(&scalar).unwrap()];
        let expected = case["point_hex"].as_str().unwrap();
        let preparation_start = Instant::now();
        let retained_bytes = unit_orbit_windows::warm_alt_split_prime_two_x_table();
        let preparation_ms = preparation_start.elapsed().as_secs_f64()*1000.0;
        let start = Instant::now();
        let actual = unit_orbit_windows::multiply_u256_tau_alt_split_prime_two_x_affine_batch(&words);
        let online_ms = start.elapsed().as_secs_f64()*1000.0;
        assert_eq!(actual.len(),1);
        assert_eq!(actual[0],expected,"pilot point");
        println!("verified=1 count=1 online_ms={online_ms:.6} preparation_ms={preparation_ms:.6} retained_bytes={retained_bytes} point={}",actual[0]);
        return;
    }
'''

def main(root: Path) -> None:
    front = root/'src/bin/eisenstein_fixed.rs'
    windows = root/'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    fixture = root/'src/bin/mixed640_uniform_fixture.json'
    assert sha256(front.read_bytes()).hexdigest() == FRONT_SHA256
    assert sha256(windows.read_bytes()).hexdigest() == WINDOWS_SHA256
    assert sha256(fixture.read_bytes()).hexdigest() == FIXTURE_SHA256
    source = front.read_text()
    anchor = '    let args: Vec<String> = std::env::args().skip(1).collect();\n'
    assert source.count(anchor) == 1
    front.write_text(source.replace(anchor,anchor+DISPATCH,1))
    print('front_output_sha256='+sha256(front.read_bytes()).hexdigest())

if __name__ == '__main__':
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]))
