//! Bounded N83 S3 pair-root state probe on the frozen W3 representative list.
//!
//! This measures a necessary root-kernel stage only. It does not construct a
//! searchable index, find a six-point decomposition, or recover a DLP.

use crypto_lib::binary_ecc::IrreduciblePoly;
use crypto_lib::cryptanalysis::koblitz_fast_arith::s3_x_roots_128;
use crypto_lib::cryptanalysis::semaev_decomp::Gf2_128;
use serde_json::{json, Value};
use std::fs;
use std::time::Instant;

fn parse_word(value: &Value) -> u128 {
    value
        .as_str()
        .expect("input word must be an exact decimal string")
        .parse::<u128>()
        .expect("valid u128 word")
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    assert_eq!(
        args.len(),
        4,
        "usage: n83_w3_pair_root_probe input.json left_limit out.json"
    );
    let input_bytes = fs::read(&args[1]).expect("read input");
    let input: Value = serde_json::from_slice(&input_bytes).expect("parse input JSON");
    assert_eq!(input["curve_id"], "EC1N83Ckb1h2bcb59d56ad6");
    assert_eq!(input["field_degree"], 83);
    assert_eq!(input["field_polynomial_low_terms"], json!([0, 2, 4, 7]));
    assert_eq!(input["representative_count"], 539);
    let pairs = input["representatives_xy_decimal"]
        .as_array()
        .expect("representative array");
    assert_eq!(pairs.len(), 539);
    let reps: Vec<u128> = pairs
        .iter()
        .map(|pair| parse_word(&pair.as_array().expect("point pair")[0]))
        .collect();
    let left_limit = args[2].parse::<usize>().expect("left limit integer");
    assert!((1..=reps.len()).contains(&left_limit));

    let irr = IrreduciblePoly {
        degree: 83,
        low_terms: vec![0, 2, 4, 7],
    };
    let gf = Gf2_128::new(&irr);
    let mut shifted = Vec::with_capacity(reps.len());
    for &x in &reps {
        assert!(x > 0 && x <= gf.mask);
        let mut row = Vec::with_capacity(83);
        let mut value = x;
        for _ in 0..83 {
            row.push(value);
            value = gf.sqr(value);
        }
        assert_eq!(value, x, "Frobenius orbit must close");
        shifted.push(row);
    }

    let started = Instant::now();
    let mut calls = 0u64;
    let mut roots_found = 0u64;
    let mut checksum = 0u128;
    let mut samples = Vec::new();
    for left in 0..left_limit {
        for right in 0..reps.len() {
            for relative in 0..83 {
                calls += 1;
                let a = shifted[left][0];
                let b = shifted[right][relative];
                if let Some(roots) = s3_x_roots_128(&gf, 1, a, b) {
                    roots_found += 1;
                    checksum ^= roots[0].rotate_left((calls % 127) as u32) ^ roots[1];
                    if samples.len() < 64 && (left != right || relative != 0) {
                        samples.push(json!({
                            "left": left,
                            "right": right,
                            "relative": relative,
                            "left_x": a.to_string(),
                            "right_x": b.to_string(),
                            "roots": [roots[0].to_string(), roots[1].to_string()],
                        }));
                    }
                }
            }
        }
    }
    let elapsed_ns = started.elapsed().as_nanos();
    assert_eq!(calls, (left_limit * reps.len() * 83) as u64);
    let record = json!({
        "schema_version": 1,
        "kind": "n83_w3_pair_root_kernel_probe",
        "status": "PRODUCER_PASS_PENDING_INDEPENDENT_REPLAY",
        "curve_id": "EC1N83Ckb1h2bcb59d56ad6",
        "field_degree": 83,
        "field_polynomial_low_terms": [0, 2, 4, 7],
        "representative_count": reps.len(),
        "left_limit": left_limit,
        "s3_calls": calls,
        "s3_roots_found": roots_found,
        "root_checksum_decimal": checksum.to_string(),
        "root_kernel_wall_ns_exploratory": elapsed_ns.to_string(),
        "sampled_roots": samples,
        "claim_boundary": "N83 S3 pair-root stage only; no searchable index, six-summand PDP, ordinary-query yield, DLP, rho pair, or speedup"
    });
    fs::write(
        &args[3],
        serde_json::to_vec_pretty(&record).expect("serialize result"),
    )
    .expect("write result");
    println!(
        "{}",
        serde_json::to_string(&json!({
            "status": record["status"],
            "left_limit": left_limit,
            "s3_calls": calls,
            "s3_roots_found": roots_found,
            "root_kernel_wall_ns_exploratory": record["root_kernel_wall_ns_exploratory"],
        }))
        .unwrap()
    );
}
