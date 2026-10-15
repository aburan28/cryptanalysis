#!/usr/bin/env python3
"""Add distinct-scalar stream benchmarks with a frozen point fixture."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = "b825b50c2dabf897fafb217c8d73d774b8934ff460665e921f2fd6284b504196"
FIXTURE_SHA256 = "6b7ce3b515d0980b9975398b8b31e5e1cfdc9e54510d04faf29fee3f3bacf778"


def benchmark(kind):
    if kind == "two_x":
        warm = "warm_split_prime_two_x_table"
        multiply = "multiply_u256_tau_split_prime_two_x_affine_batch"
    else:
        warm = "warm_split_prime_cache_budget_table"
        multiply = "multiply_u256_tau_split_prime_cache_budget_affine_batch"
    return f'''
fn benchmark_mixed640_{kind}_stream(repetitions: usize, batch_size: usize) {{
    assert_eq!(repetitions,96);
    assert_eq!(batch_size,128);
    let panel: Value = serde_json::from_str(include_str!("mixed640_stream_fixture.json"))
        .expect("parse distinct-scalar stream fixture");
    let cases = panel["cases"].as_array().expect("stream cases");
    assert_eq!(cases.len(),128*96);
    let inputs = cases.iter().map(|case| {{
        let scalar_hex = case["scalar_hex"].as_str().expect("scalar");
        let scalar = BigInt::parse_bytes(scalar_hex.as_bytes(),16).expect("scalar hex");
        (scalar_words_256(&scalar).expect("scalar words"),
         case["point_hex"].as_str().expect("point"))
    }}).collect::<Vec<_>>();
    let words = inputs.iter().map(|&(value,_)| value).collect::<Vec<_>>();
    let preparation_start = Instant::now();
    let retained_bytes = unit_orbit_windows::{warm}();
    let preparation_ms = preparation_start.elapsed().as_secs_f64()*1000.0;
    let mut answers = Vec::with_capacity(inputs.len());
    let start = Instant::now();
    for chunk in words.chunks(batch_size) {{
        answers.extend(std::hint::black_box(
            unit_orbit_windows::{multiply}(std::hint::black_box(chunk))));
    }}
    let online_ms = start.elapsed().as_secs_f64()*1000.0;
    assert_eq!(answers.len(),inputs.len());
    for (index,point) in answers.iter().enumerate() {{
        assert_eq!(point,inputs[index].1,"stream case {{index}}");
    }}
    let count=answers.len();
    let last_point=answers.last().expect("nonempty");
    let last_scalar=cases.last().unwrap()["scalar_hex"].as_str().unwrap();
    println!("verified=1 online_ms={{online_ms:.6}} preparation_ms={{preparation_ms:.6}} retained_bytes={{retained_bytes}} count={{count}} batch_id=stream128x96 fixture_sha256={FIXTURE_SHA256} scalar={{last_scalar}} point={{last_point}} batch_size={{batch_size}} scheme={kind}_stream");
}}
'''


def main(root):
    front = root / "src/bin/eisenstein_fixed.rs"
    fixture = root / "src/bin/mixed640_stream_fixture.json"
    source = front.read_text()
    assert sha256(source.encode()).hexdigest() == FRONT_SHA256
    assert sha256(fixture.read_bytes()).hexdigest() == FIXTURE_SHA256
    insertion = source.index("\nfn main()")
    updated = source[:insertion] + benchmark("two_x") + benchmark("cache_budget") + source[insertion:]
    dispatch = '''    if args.len() == 3 && args[0] == "--benchmark-split-prime-affine-two-x-stream" {
        benchmark_mixed640_two_x_stream(
            args[2].parse().expect("stream passes"),
            args[1].parse().expect("batch size"));
        return;
    }
    if args.len() == 3 && args[0] == "--benchmark-split-prime-affine-cache-budget-stream" {
        benchmark_mixed640_cache_budget_stream(
            args[2].parse().expect("stream passes"),
            args[1].parse().expect("batch size"));
        return;
    }
'''
    needle = "    let args: Vec<String> = std::env::args().skip(1).collect();\n"
    assert updated.count(needle) == 1
    updated = updated.replace(needle, needle + dispatch, 1)
    front.write_text(updated)
    print("front_sha256=" + sha256(updated.encode()).hexdigest())


if __name__ == "__main__":
    main(Path(sys.argv[1]))
