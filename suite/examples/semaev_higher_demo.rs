//! Compute the first several Semaev summation polynomials over a toy
//! prime-field curve and report monomial counts / degrees.
//!
//! ```bash
//! cargo run --release --example semaev_higher_demo
//! ```

use cryptanalysis_suite::cryptanalysis::semaev_higher::{
    s3_in_last, s4_in_last_proper, s5_in_last, s6_in_last,
};
use cryptanalysis_suite::ecc::field::FieldElement;
use num_bigint::BigUint;

fn fe(v: u64, p: &BigUint) -> FieldElement {
    FieldElement::new(BigUint::from(v), p.clone())
}

fn main() {
    let p = BigUint::from(271u32);
    let a = fe(2, &p);
    let b = fe(3, &p);

    let x1 = fe(7, &p);
    let x2 = fe(11, &p);
    let x3 = fe(19, &p);
    let x4 = fe(23, &p);
    let x5 = fe(29, &p);

    println!();
    println!("=== Semaev S_n on y² = x³ + 2x + 3 over F_271 ===");
    println!();

    let s3 = s3_in_last(&x1, &x2, &a, &b);
    println!(
        "S_3(7, 11, X)           deg = {:?}  coeffs = {}",
        s3.degree(),
        s3.coeffs.len()
    );

    let s4 = s4_in_last_proper(&x1, &x2, &x3, &a, &b);
    println!(
        "S_4(7, 11, 19, X)       deg = {:?}  coeffs = {}",
        s4.degree(),
        s4.coeffs.len()
    );

    let s5 = s5_in_last(&x1, &x2, &x3, &x4, &a, &b);
    println!(
        "S_5(7, 11, 19, 23, X)   deg = {:?}  coeffs = {}",
        s5.degree(),
        s5.coeffs.len()
    );

    let s6 = s6_in_last(&x1, &x2, &x3, &x4, &x5, &a, &b);
    println!(
        "S_6(7, …, 29, X)        deg = {:?}  coeffs = {}",
        s6.degree(),
        s6.coeffs.len()
    );

    println!();
    println!("Theoretical degree progression: 2, 4, 8, 16, 32, ...");
    println!(
        "Observed: 2 (S_3), {} (S_4), {} (S_5), {} (S_6).",
        s4.degree().unwrap(),
        s5.degree().unwrap(),
        s6.degree().unwrap()
    );
}
