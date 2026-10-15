#!/usr/bin/env python3
"""Add the same long-interval scalar batch timer to both native variants."""
from hashlib import sha256
from pathlib import Path
import sys

PARENT_SHA256 = '814042f0ab527b43c4813a2f71dbbc81cafeaad3bbaf5f436c119cef9262ee19'


def main(root):
    path = root / 'src/bin/eisenstein_fixed.rs'
    source = path.read_text()
    assert sha256(source.encode()).hexdigest() == PARENT_SHA256
    marker = '\nfn main() {\n'
    assert source.count(marker) == 1
    source = source.replace(marker, '''
fn benchmark_mixed640_batch(repetitions: usize) {
    assert!((1..=100).contains(&repetitions));
    let panel: Value = serde_json::from_str(include_str!("mixed640_bench_fixture.json"))
        .expect("parse frozen fixture");
    let cases = panel["cases"].as_array().expect("fixture cases");
    assert_eq!(cases.len(),128);
    let inputs = cases.iter().map(|case| {
        let scalar_hex = case["scalar_hex"].as_str().expect("scalar");
        let scalar = BigInt::parse_bytes(scalar_hex.as_bytes(),16).expect("scalar hex");
        (scalar_words_256(&scalar).expect("scalar words"),
         case["point_hex"].as_str().expect("point"))
    }).collect::<Vec<_>>();
    let preparation_start = Instant::now();
    let retained_bytes = unit_orbit_windows::warm_split_prime_table();
    let preparation_ms = preparation_start.elapsed().as_secs_f64() * 1000.0;
    let mut answers = Vec::with_capacity(repetitions*inputs.len());
    let start = Instant::now();
    for _ in 0..repetitions {
        for &(words,_) in &inputs {
            let answer = std::hint::black_box(
                unit_orbit_windows::multiply_u256_tau_split_prime_radix(
                    std::hint::black_box(words)));
            answers.push(answer.0);
        }
    }
    let online_ms = start.elapsed().as_secs_f64()*1000.0;
    for (index,point) in answers.iter().enumerate() {
        assert_eq!(point,inputs[index % inputs.len()].1,"batch case {index}");
    }
    let count=answers.len();
    let last_point=answers.last().expect("nonempty");
    let last_scalar=cases.last().unwrap()["scalar_hex"].as_str().unwrap();
    println!("verified=1 online_ms={online_ms:.6} preparation_ms={preparation_ms:.6} retained_bytes={retained_bytes} count={count} batch_id=all128x{repetitions} fixture_sha256=7f4672b7b676969fe40056d0f14c6ecf45ad36109870cdf3466ebafd9e7b22d8 scalar={last_scalar} point={last_point}");
}
''' + marker)
    marker = '''    if args.len() == 2 && args[0] == "--benchmark-mixed640-packet" {'''
    assert source.count(marker) == 1
    source = source.replace(marker, '''    if args.len() == 2 && args[0] == "--benchmark-mixed640-batch" {
        benchmark_mixed640_batch(args[1].parse().expect("batch repetitions"));
        return;
    }
''' + marker)
    path.write_text(source)
    print(sha256(path.read_bytes()).hexdigest())


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: native_batch_overlay.py CARGO_ROOT')
    main(Path(sys.argv[1]))
