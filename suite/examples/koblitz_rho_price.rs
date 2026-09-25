//! What one step of the signed-Frobenius rho costs, in the unit the
//! Koblitz collection thread prices everything else in.
//!
//! That thread's `vs rho` divides by `rho_group_additions / √r`: one unit
//! per walk addition and nothing else.  But every step of the walk also
//! canonicalises its point over the `2n` signed Frobenius conjugates —
//! `n − 1` squarings of `x` and up to `n − 1` of `y` in the implemented
//! walk — hashes it, and probes a cache, while the index-calculus side of
//! the same comparison pays for its own Frobenius work.  This measures,
//! in one process on one host:
//!
//! - the unit, one batched affine addition (`add_many` over 1,024
//!   points), exactly as `koblitz_phase_prices` measures it;
//! - the implemented walk end to end, `walk_ns / iterations`, on real
//!   targets: everything a step does;
//! - the two canonicalisations on their own: the implemented squaring
//!   chain, and the normal-basis rotation (`FrobeniusCanon`) the
//!   index-calculus tables use.
//!
//!     cargo run --release --example koblitz_rho_price -- 41 16
use cryptanalysis_suite::cryptanalysis::koblitz_fast::{
    BatchScratch, FastCurve, FastPoint, FrobeniusCanon,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::*;
use num_bigint::BigUint;
use std::time::Instant;

const ADDS: usize = 2_000_000;
const CANONS: usize = 2_000_000;

fn main() {
    let degree: u32 = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(41);
    let targets: u64 = std::env::args()
        .nth(2)
        .and_then(|s| s.parse().ok())
        .unwrap_or(16);
    let a: u8 = std::env::args()
        .nth(3)
        .and_then(|s| s.parse().ok())
        .unwrap_or(0);
    let kc = KoblitzCurve::new(a, degree).expect("curve");
    let fc = FastCurve::new(&kc.curve).expect("fast curve");
    let r = kc.subgroup_order.to_u64_digits()[0];
    let sqrt_r = (r as f64).sqrt();

    // The unit.
    let g = fc.lift(kc.generator());
    let seedfb = build_subgroup_orbit_factor_base(&kc, 1, 64).expect("seed base");
    let batch: Vec<FastPoint> = (0..1024)
        .map(|i| fc.lift(&seedfb.points[i % seedfb.points.len()]))
        .collect();
    let mut scratch = BatchScratch::default();
    let mut out: Vec<FastPoint> = Vec::with_capacity(batch.len());
    let rounds = ADDS / batch.len();
    let t = Instant::now();
    for _ in 0..rounds {
        out.clear();
        fc.add_many(g, &batch, &mut out, &mut scratch);
    }
    let add_ns = t.elapsed().as_secs_f64() * 1e9 / (rounds * batch.len()) as f64;
    std::hint::black_box(out.len());
    println!("K_{a} / GF(2^{degree}), r = 2^{:.2}", (r as f64).log2());
    println!("unit: one batched group addition = {add_ns:.2} ns");

    // The two canonicalisations, alone, on points of the subgroup.
    let pts: Vec<FastPoint> = (0..4096u64).map(|i| fc.mul_u64(g, 1 + i * 7919)).collect();
    let field = &fc.field;
    let t = Instant::now();
    let mut sink = 0u64;
    for i in 0..CANONS {
        let p = pts[i % pts.len()];
        // The implemented walk: the x orbit by a squaring chain, then y
        // lifted to the winning power only.
        let mut x = p.x;
        let mut best_x = x;
        let mut best_k = 0u32;
        for k in 1..degree {
            x = field.sqr(x);
            if x < best_x {
                best_x = x;
                best_k = k;
            }
        }
        let y = field.sqr_k(p.y, best_k);
        sink ^= best_x ^ y.min(best_x ^ y);
    }
    let chain_ns = t.elapsed().as_secs_f64() * 1e9 / CANONS as f64;
    let canon = FrobeniusCanon::new(field, degree).expect("normal basis");
    let t = Instant::now();
    for i in 0..CANONS {
        let p = pts[i % pts.len()];
        let (c, shift) = canon.canon_with_shift(p.x);
        // The name alone is not the point: the walk adds to the
        // representative, so y must follow x to the same conjugate.
        // Here by squarings, the implemented lift; a normal-basis
        // inverse map would be cheaper, which is why this is an upper
        // bound on what the rotation canonicalisation costs.
        let y = field.sqr_k(p.y, shift);
        sink ^= c ^ y;
    }
    let nb_ns = t.elapsed().as_secs_f64() * 1e9 / CANONS as f64;
    std::hint::black_box(sink);
    println!(
        "canonicalisation, implemented squaring chain: {chain_ns:.1} ns = {:.2} units",
        chain_ns / add_ns
    );
    println!(
        "canonicalisation, normal-basis rotation (+ y by squarings): {nb_ns:.1} ns = {:.2} units",
        nb_ns / add_ns
    );

    // The implemented walk end to end.
    let mut steps = 0u64;
    let mut walk_ns = 0u128;
    let mut setup_ns = 0u128;
    let mut verify_ns = 0u128;
    let mut adds = 0u64;
    let mut ok = 0u64;
    for k in 0..targets {
        let d = 1 + (k * 0x9E37_79B9 + 12_345) % (r - 1);
        let q = kc.mul(kc.generator(), &BigUint::from(d));
        let opts = KoblitzSignedRhoOptions {
            seed: 0x5EED ^ k,
            ..Default::default()
        };
        let rep = koblitz_signed_frobenius_rho_with_progress(&kc, &q, &opts, &mut |_| {});
        steps += rep.iterations;
        walk_ns += rep.walk_ns;
        setup_ns += rep.setup_ns;
        verify_ns += rep.verification_ns;
        adds += rep.charges.walk_group_additions;
        ok += u64::from(rep.verified && rep.recovered_log == Some(BigUint::from(d)));
    }
    let per_step = walk_ns as f64 / steps as f64;
    println!("\nwalk, {targets} targets, {ok} verified");
    println!(
        "  steps a target                {:>12.0}",
        steps as f64 / targets as f64
    );
    println!(
        "  S as the thread counts it     {:>12.4}   (walk additions / √r)",
        adds as f64 / targets as f64 / sqrt_r
    );
    println!(
        "  ns a step, everything         {per_step:>12.1}   = {:.2} units",
        per_step / add_ns
    );
    println!(
        "  setup ns a target             {:>12.0}   = {:.0} units",
        setup_ns as f64 / targets as f64,
        setup_ns as f64 / targets as f64 / add_ns
    );
    println!(
        "  S priced by time              {:>12.4}   (walk + setup + verification, in units, / √r)",
        (walk_ns + setup_ns + verify_ns) as f64 / add_ns / targets as f64 / sqrt_r
    );
}
