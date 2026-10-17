#!/usr/bin/env python3
"""Add a verified repeated-stream timing mode without changing scalar arithmetic."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = '6cd0962b58b4673708af813a913474791400a7297142e4e5970e7af11faf0b34'
ANCHOR = '    if args.len() == 2 && args[0] == "--pilot-alt-horner" {'
REPEAT_MODE = '''    if args.len() == 2 && args[0] == "--benchmark-alt-horner-repeats" {
        let passes: usize = args[1].parse().expect("repeat count");
        assert!((1..=16).contains(&passes));
        let panel: Value = serde_json::from_str(include_str!("mixed640_uniform_fixture.json"))
            .expect("parse fixture");
        let cases = panel["cases"].as_array().unwrap();
        assert_eq!(cases.len(),128*96);
        let inputs = cases.iter().map(|case| {
            let scalar = BigInt::parse_bytes(
                case["scalar_hex"].as_str().unwrap().as_bytes(),16).unwrap();
            (scalar_words_256(&scalar).unwrap(),case["point_hex"].as_str().unwrap())
        }).collect::<Vec<_>>();
        let words = inputs.iter().map(|&(words,_)| words).collect::<Vec<_>>();
        let preparation_start = Instant::now();
        let retained_bytes = unit_orbit_windows::warm_alt_split_prime_two_x_table();
        let preparation_ms = preparation_start.elapsed().as_secs_f64()*1000.0;
        let start = Instant::now();
        let mut actual = Vec::with_capacity(words.len()*passes);
        for _ in 0..passes {
            actual.extend(unit_orbit_windows::multiply_u256_tau_alt_split_prime_two_x_affine_batch(&words));
        }
        let online_ms = start.elapsed().as_secs_f64()*1000.0;
        assert_eq!(actual.len(),words.len()*passes);
        for (index,point) in actual.iter().enumerate() {
            assert_eq!(point,inputs[index%words.len()].1,"repeat case {index}");
        }
        println!("verified=1 count={} unique_points={} passes={passes} online_ms={online_ms:.6} preparation_ms={preparation_ms:.6} retained_bytes={retained_bytes} point={}",actual.len(),words.len(),actual.last().unwrap());
        return;
    }
'''


def main(root: Path):
    front = root/'src/bin/eisenstein_fixed.rs'
    assert sha256(front.read_bytes()).hexdigest() == FRONT_SHA256
    source = front.read_text()
    assert source.count(ANCHOR) == 1
    source = source.replace(ANCHOR,REPEAT_MODE+ANCHOR,1)
    front.write_text(source)
    print('front_sha256='+sha256(front.read_bytes()).hexdigest())


if __name__ == '__main__':
    assert len(sys.argv)==2
    main(Path(sys.argv[1]))
