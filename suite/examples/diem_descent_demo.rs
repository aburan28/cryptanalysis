//! Toy demonstration of Diem-style descent on `E / F_25` with the
//! factor base in `F_5 ⊂ F_25`.
//!
//! ```bash
//! cargo run --release --example diem_descent_demo
//! ```

use cryptanalysis_suite::cryptanalysis::diem_descent::{
    build_factor_base, find_2_decomposition, ECurveFpk, Fpk,
};

fn main() {
    let p = 5u64;
    let k = 2u32;
    let irr = 2u64; // θ² = 2
    let a = Fpk::from_coeffs(vec![1, 1], p, k);
    let b = Fpk::from_coeffs(vec![2, 0], p, k);
    let curve = ECurveFpk::new(a.clone(), b.clone(), p, k, irr);

    println!();
    println!("=== Diem descent toy on E: y² = x³ + (1+θ) x + 2 over F_25 ===");
    println!();

    let fb = build_factor_base(&curve);
    println!(
        "Factor base FB = {{ P : x(P) ∈ F_5 }} :  {} points",
        fb.len()
    );
    for (i, p) in fb.iter().enumerate() {
        let x = p.x.as_ref().unwrap();
        let y = p.y.as_ref().unwrap();
        println!("  FB[{}]  =  ( {:?},  {:?} )", i, x.coeffs, y.coeffs);
    }

    if fb.len() < 2 {
        println!();
        println!("Factor base too small for a 2-decomposition demo; abort.");
        return;
    }

    println!();
    println!("Looking for 2-decompositions of {} candidate targets:", 5);
    let g = &fb[0];
    let q = &fb[fb.len() - 1];

    use num_bigint::BigUint;
    let mut found = 0;
    let mut tried = 0;
    for a in 1..=5u32 {
        for b in 1..=5u32 {
            tried += 1;
            let target = curve.add(
                &curve.scalar_mul(&BigUint::from(a), g),
                &curve.scalar_mul(&BigUint::from(b), q),
            );
            if let Some(dec) = find_2_decomposition(&curve, &fb, &target) {
                found += 1;
                if found <= 3 {
                    println!(
                        "  R = {}·G + {}·Q   →   ε₁·FB[{}] + ε₂·FB[{}]   ({:+}, {:+})",
                        a, b, dec.indices.0, dec.indices.1, dec.signs.0, dec.signs.1
                    );
                }
            }
        }
    }
    println!();
    println!(
        "Summary: {} / {} targets had a 2-decomposition over FB ⊂ F_5.",
        found, tried
    );
}
