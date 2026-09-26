//! Run the Petit–Kosters–Messeng resistance audit on every
//! standardised prime-field curve in the zoo.
//!
//! Direct response to the CryptoPro / Nikolaev CTCrypt 2024 slide
//! ("yes, P-224 satisfies the criterion") — produces an at-a-glance
//! resistance table for NIST, SECG, Brainpool, FRP, SM2, and GOST
//! curves.
//!
//! ```bash
//! cargo run --example pkm_audit_demo --release
//! ```

use cryptanalysis_suite::cryptanalysis::pkm_criterion::{audit, PkmAuditReport};
use cryptanalysis_suite::ecc::curve::CurveParams;

fn main() {
    let curves: Vec<CurveParams> = vec![
        CurveParams::p192(),
        CurveParams::p224(),
        CurveParams::p256(),
        CurveParams::p384(),
        CurveParams::p521(),
        CurveParams::secp256k1(),
        CurveParams::secp192k1(),
        CurveParams::secp224k1(),
        CurveParams::brainpool_p192r1(),
        CurveParams::brainpool_p224r1(),
        CurveParams::brainpool_p256r1(),
        CurveParams::brainpool_p384r1(),
        CurveParams::brainpool_p512r1(),
        CurveParams::frp256v1(),
        CurveParams::sm2(),
        CurveParams::gost_cryptopro_a(),
        CurveParams::gost_cryptopro_b(),
        CurveParams::gost_cryptopro_c(),
        CurveParams::gost_tc26_256_a(),
        CurveParams::gost_tc26_512_a(),
        CurveParams::gost_tc26_512_b(),
    ];

    let reports: Vec<PkmAuditReport> = curves.iter().map(audit).collect();

    println!();
    println!(
        "{:24} {:>6}  {:>6}  {:>6}  {:>6}  {:>6}  {:>6}",
        "curve", "bits", "spec", "trace", "n-1", "embed", "OVERALL"
    );
    println!("{}", "─".repeat(78));
    for r in &reports {
        println!(
            "{:24} {:>6}  {:>6.3}  {:>6.3}  {:>6.3}  {:>6.3}  {:>6.3}",
            r.curve_name,
            r.field_bits,
            r.special_prime.score,
            r.trace_factors.score,
            r.order_neighbourhood.score,
            r.embedding_window.score,
            r.overall_score,
        );
    }
    println!();
    println!("Per-curve detail:");
    println!();
    for r in &reports {
        r.print();
        println!();
    }
}
