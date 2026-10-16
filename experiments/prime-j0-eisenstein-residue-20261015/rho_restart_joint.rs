//! Same-input two-scalar norm-4033 Horner pilot for rho restart points.
use std::time::Instant;
use num_bigint::BigInt;
use serde_json::Value;
use super::{scalar_words_256, unit_orbit_windows};

pub(super) fn run(fixture_path: &str, count: usize) {
    let fixture: Value = serde_json::from_str(
        &std::fs::read_to_string(fixture_path).expect("read frozen fixture"))
        .expect("parse frozen fixture");
    let rows = fixture["cases"].as_array().expect("cases");
    assert!(count > 0 && count <= rows.len());
    let inputs = rows.iter().take(count).map(|row| {
        let a = BigInt::parse_bytes(
            row["a_hex"].as_str().expect("a").as_bytes(),16).expect("a hex");
        let b = BigInt::parse_bytes(
            row["b_hex"].as_str().expect("b").as_bytes(),16).expect("b hex");
        (scalar_words_256(&a).expect("a words"),
         scalar_words_256(&b).expect("b words"),
         row["point_hex"].as_str().expect("expected").to_owned())
    }).collect::<Vec<_>>();
    let generator_start = Instant::now();
    let generator_bytes = unit_orbit_windows::warm_alt_split_prime_two_x_table();
    let generator_preparation_ms = generator_start.elapsed().as_secs_f64()*1000.0;
    let q_start = Instant::now();
    let q_table = unit_orbit_windows::prepare_joint_q(
        fixture["q_hex"].as_str().expect("Q"));
    let q_preparation_ms = q_start.elapsed().as_secs_f64()*1000.0;
    let retained_bytes = generator_bytes + q_table.retained_bytes;
    let start = Instant::now();
    let answers = inputs.iter().map(|(a,b,_)|
        unit_orbit_windows::multiply_u256_tau_joint(*a,*b,&q_table))
        .collect::<Vec<_>>();
    let online_ms = start.elapsed().as_secs_f64()*1000.0;
    for (index,(actual,(_,_,expected))) in answers.iter().zip(inputs.iter()).enumerate() {
        assert_eq!(actual,expected,"rho joint case {index}");
    }
    println!("verified=1 count={count} online_ms={online_ms:.6} \
              generator_preparation_ms={generator_preparation_ms:.6} \
              q_preparation_ms={q_preparation_ms:.6} retained_bytes={retained_bytes} \
              mode=joint point={}",answers.last().expect("nonempty"));
}
