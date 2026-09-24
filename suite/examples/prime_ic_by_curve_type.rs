//! Index calculus against rho on prime-field curves, by curve type.
//!
//! For each type — generic (as P-192 … P-521), `j = 0` (as secp256k1),
//! `j = 1728` — each way of collecting relations (full 2-decompositions,
//! or the single-large-prime variation) and each field size, build a
//! certified known-answer instance, precompute one automorphism-orbit
//! logarithm database ([`prime_orbit_index_calculus`]), descend `T`
//! targets against it, and run the batched rho baseline on each.  Costs are
//! group operations (affine additions, a batched inversion shared on both
//! sides):
//!
//! - `precompute` — probes and oracle differences for the database;
//! - `descent` — mean per target, database paid;
//! - `rho` — mean group operations per target (walk steps plus seeding
//!   the walks), unfolded; the `√|Aut|`-folded step expectation plus the
//!   same seeding is printed beside it.  Rho's jump table is shared by the
//!   targets like the database is, and enters the amortised and whole
//!   ratios the same way.
//!
//! The three ratios are the binary `vs_rho` block's timing classes, as
//! `rho / IC` (above 1 means index calculus spent less): **charged**
//! (descent alone), **amortised** (precompute spread over the `T`
//! targets, plus descent) and **whole** (everything, once).  A second
//! table fits `ops ∝ r^α` per series.
//!
//! ```bash
//! cargo run --release --example prime_ic_by_curve_type
//! cargo run --release --example prime_ic_by_curve_type -- 16 28 32   # bits 16..=28 step 4, 32 targets
//! ```
//!
//! [`prime_orbit_index_calculus`]: cryptanalysis_suite::cryptanalysis::prime_orbit_index_calculus

use cryptanalysis_suite::cryptanalysis::ec_index_calculus_curves::CurveKind;
use cryptanalysis_suite::cryptanalysis::prime_orbit_index_calculus::{
    generate_instance, run_known_answer, OrbitIcOptions, ScaledShape,
};

/// Least-squares slope of `ln y` against `ln x`.
fn loglog_slope(points: &[(f64, f64)]) -> f64 {
    let pts: Vec<(f64, f64)> = points
        .iter()
        .filter(|(x, y)| *x > 0.0 && *y > 0.0)
        .map(|(x, y)| (x.ln(), y.ln()))
        .collect();
    if pts.len() < 2 {
        return f64::NAN;
    }
    let n = pts.len() as f64;
    let (sx, sy) = pts.iter().fold((0.0, 0.0), |(a, b), (x, y)| (a + x, b + y));
    let (mx, my) = (sx / n, sy / n);
    let (num, den) = pts.iter().fold((0.0, 0.0), |(a, b), (x, y)| {
        (a + (x - mx) * (y - my), b + (x - mx) * (x - mx))
    });
    num / den
}

fn main() {
    let args: Vec<u32> = std::env::args()
        .skip(1)
        .filter_map(|a| a.parse().ok())
        .collect();
    let lo = args.first().copied().unwrap_or(16);
    let hi = args.get(1).copied().unwrap_or(24);
    let targets = args.get(2).copied().unwrap_or(16) as usize;

    println!("| type | relations | \\|Aut\\| | bits | r | orbits (certified) | verified IC / rho | precompute | descent | rho | folded rho | charged | amortised | whole | IC s | rho s |");
    println!("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|");
    let mut fits: Vec<(String, f64, f64, f64)> = Vec::new();
    for kind in [CurveKind::Generic, CurveKind::J0, CurveKind::J1728] {
        for large_primes in [false, true] {
            let mode = if large_primes { "large primes" } else { "full" };
            let (mut pre_s, mut des_s, mut rho_s) = (Vec::new(), Vec::new(), Vec::new());
            for bits in (lo..=hi).step_by(4) {
                let Ok(inst) = generate_instance(ScaledShape::of_kind(kind), bits, None, 1) else {
                    println!(
                        "| {} | {mode} | | {bits} | no certified curve | | | | | | | | | | | |",
                        kind.as_str()
                    );
                    continue;
                };
                let ts = inst.targets(targets, 1);
                let points: Vec<_> = ts.iter().map(|&(_, q)| q).collect();
                let opts = OrbitIcOptions {
                    large_primes,
                    ..OrbitIcOptions::default()
                };
                let rep = run_known_answer(&inst.curve, &points, &opts);
                let t = ts.len() as f64;
                let (pre, des, rho, rho_pre) = (
                    rep.precompute_ops() as f64,
                    rep.mean_descent_ops(),
                    rep.mean_rho_ops(),
                    rep.rho_precompute_ops as f64,
                );
                // The folded walk's expected steps, plus the same setup.
                let setup = rep.rhos.iter().map(|r| r.setup_ops).sum::<u64>() as f64 / t;
                let folded = rep
                    .rhos
                    .first()
                    .map_or(f64::NAN, |r| r.expected_steps_folded + setup);
                let ic_s = rep.logs.seconds + rep.descents.iter().map(|d| d.seconds).sum::<f64>();
                let rho_sec: f64 = rep.rhos.iter().map(|r| r.seconds).sum();
                println!(
                "| {} | {mode} | {} | {bits} | {} | {} ({}) | {}/{} / {}/{} | {pre:.3e} | {des:.3e} | {rho:.3e} | {folded:.3e} | {:.2} | {:.3} | {:.4} | {ic_s:.3} | {rho_sec:.3} |",
                kind.as_str(),
                rep.automorphism_order,
                inst.curve.r,
                rep.logs.orbits,
                rep.logs.certified_columns,
                rep.descents_verified(),
                ts.len(),
                rep.rhos_verified(),
                ts.len(),
                rho / des,
                (rho_pre / t + rho) / (pre / t + des),
                (rho_pre + rho * t) / (pre + des * t),
            );
                let rf = inst.curve.r as f64;
                pre_s.push((rf, pre));
                des_s.push((rf, des));
                rho_s.push((rf, rho));
            }
            fits.push((
                format!("{} / {mode}", kind.as_str()),
                loglog_slope(&pre_s),
                loglog_slope(&des_s),
                loglog_slope(&rho_s),
            ));
        }
    }
    println!();
    println!("| series | precompute ∝ r^α | descent ∝ r^α | rho ∝ r^α |");
    println!("|---|---:|---:|---:|");
    for (name, pre, des, rho) in fits {
        println!("| {name} | {pre:.2} | {des:.2} | {rho:.2} |");
    }
}
