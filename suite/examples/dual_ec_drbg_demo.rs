//! Dual EC DRBG backdoor demo (Shumow & Ferguson, 2007).
//!
//! Recovers the internal state of a Dual EC DRBG instantiated on NIST P-256
//! from a single observed 240-bit output block, by exploiting knowledge of
//! the discrete log relating the two public points: `Q = d * P`.
//!
//! Uses the real spec's 16-bit top-truncation, so the brute force is 2^16.
//!
//! Run with:
//!   cargo run --release --example dual_ec_drbg_demo

use cryptanalysis_suite::cryptanalysis::ec_index_calculus::sqrt_mod_p;
use cryptanalysis_suite::ecc::p256_point::ct_scalar_mul_p256;
use cryptanalysis_suite::ecc::{CurveParams, Point};
use cryptanalysis_suite::utils::mod_inverse;
use num_bigint::{BigUint, RandBigInt};
use num_traits::One;
use rand::thread_rng;
use std::time::Instant;

const BITS_TRUNCATED: usize = 16;
const OUTPUT_BITS: usize = 256 - BITS_TRUNCATED;

fn x_of(p: &Point) -> BigUint {
    p.x_coord().expect("point at infinity unexpected").clone()
}

/// One DRBG iteration: state -> (new_state, output_block).
fn drbg_step(
    state: &BigUint,
    p_pt: &Point,
    q_pt: &Point,
    curve: &CurveParams,
) -> (BigUint, BigUint) {
    let s_new = x_of(&ct_scalar_mul_p256(p_pt, state, curve));
    let r = x_of(&ct_scalar_mul_p256(q_pt, &s_new, curve));
    let mask = (BigUint::one() << OUTPUT_BITS) - BigUint::one();
    (s_new, r & mask)
}

fn main() {
    println!("=== Dual EC DRBG backdoor demo (Rust, NIST P-256) ===");
    println!("truncating top {BITS_TRUNCATED} bits  ->  search space 2^{BITS_TRUNCATED}\n");

    let curve = CurveParams::p256();
    let p_pt = curve.generator();

    let mut rng = thread_rng();
    let order = &curve.n;

    // 1. Attacker picks backdoor d, sets Q = d * P, publishes Q.
    let d = rng.gen_biguint_below(order);
    let q_pt = ct_scalar_mul_p256(&p_pt, &d, &curve);
    let e = mod_inverse(&d, order).expect("d coprime to n");

    // 2. Victim seeds the DRBG and emits two output blocks.
    let s0 = rng.gen_biguint_below(order);
    let (s1, out1) = drbg_step(&s0, &p_pt, &q_pt, &curve);
    let (s2, out2) = drbg_step(&s1, &p_pt, &q_pt, &curve);

    println!("observed block 1: {:#x}", out1);
    println!("observed block 2: {:#x}\n", out2);

    // 3. Brute-force the 16 truncated bits. For each candidate x, lift to a
    //    point R on the curve; then e*R = s1 * (e*Q) = s1 * P, whose
    //    x-coordinate IS the next state s2.
    println!("attacker brute-forcing 2^{BITS_TRUNCATED} candidates...");
    let t0 = Instant::now();
    let mask = (BigUint::one() << OUTPUT_BITS) - BigUint::one();
    let prime = &curve.p;
    let b = &curve.b;
    let a = &curve.a;

    let mut found: Option<(u32, BigUint)> = None;
    let mut tried = 0u64;

    'outer: for top in 0u32..(1u32 << BITS_TRUNCATED) {
        let x_full = (BigUint::from(top) << OUTPUT_BITS) | &out1;
        if &x_full >= prime {
            continue;
        }
        // y^2 = x^3 + a*x + b  (a = p - 3 for P-256)
        let x2 = (&x_full * &x_full) % prime;
        let x3 = (&x2 * &x_full) % prime;
        let ax = (a * &x_full) % prime;
        let rhs = (x3 + ax + b) % prime;
        let Some(y) = sqrt_mod_p(&rhs, prime) else {
            continue;
        };
        let y2 = (prime - &y) % prime;

        for cand_y in [&y, &y2] {
            tried += 1;
            let r_pt = Point::Affine {
                x: curve.fe(x_full.clone()),
                y: curve.fe(cand_y.clone()),
            };
            // s2_guess = x(e * R)
            let s2_guess = x_of(&ct_scalar_mul_p256(&r_pt, &e, &curve));
            // Verify against the second observed block.
            let pred_out2 = x_of(&ct_scalar_mul_p256(&q_pt, &s2_guess, &curve)) & &mask;
            if pred_out2 == out2 {
                found = Some((top, s2_guess));
                break 'outer;
            }
        }
    }

    let dt = t0.elapsed();
    let (top, s2_recovered) = found.expect("attack should always succeed");
    println!("[+] recovered after {tried} tries in {:.2?}", dt);
    println!("    top {BITS_TRUNCATED} bits: {:#06x}", top);
    println!("    s2 recovered: {:#x}", s2_recovered);
    println!("    s2 actual:    {:#x}", s2);
    assert_eq!(s2_recovered, s2);

    // 4. Predict the next block from the recovered state.
    let (_, out3_actual) = drbg_step(&s2, &p_pt, &q_pt, &curve);
    let (_, out3_pred) = drbg_step(&s2_recovered, &p_pt, &q_pt, &curve);
    assert_eq!(out3_actual, out3_pred);
    println!("\nactual block 3:    {:#x}", out3_actual);
    println!("predicted block 3: {:#x}", out3_pred);
    println!("\n[+] future output fully predictable from one observed block.");
}
