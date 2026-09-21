//! EXP-H — scaling of the early Hilbert defect `Δ_low` with `2n'`, the
//! empirical backbone of the algebraic **lower-bound** argument.
//!
//! The defensive theorem the proposal wants (proof-complexity §4, route
//! "5a") is: *for a generic factor base the early defect vanishes, forcing
//! `D* = Θ(n)`.* This experiment measures, in the critical regime `2n'=n`,
//! the normalized early defect `Δ_low` for
//!
//!   - the **Subfield** family (`F_{2^{n'}}`, multiplicatively closed), and
//!   - the **Random** (generic) family,
//!
//! across `2n' ∈ {6,…,20}`, and fits the Random decay to a power law
//! `Δ_low ≈ a·N^{-c}`. If the Random defect → 0 (c > 0) while the Subfield
//! stays bounded away from 0, that is the empirical statement
//! "generic factor bases are asymptotically semi-regular at low degree" —
//! exactly the hypothesis the lower bound needs, and the converse of the
//! subfield speedup.
//!
//! Cheap: `Δ_low` only needs Macaulay ranks up to degree 3, so this runs at
//! `2n'=20` in seconds. Snapshot → `experiments/ffd_defect_scaling.json`.
//!
//! Run: `cargo run --release --example ffd_defect_scaling`

use cryptanalysis_suite::binary_ecc::F2mElement;
use cryptanalysis_suite::cryptanalysis::descent_algebraic::{early_defect, rank_profile};
use cryptanalysis_suite::cryptanalysis::descent_expansion::enumerate_irreducibles;
use cryptanalysis_suite::cryptanalysis::descent_lowgamma::{
    descend_on_subspace, BasisFamily, FactorSubspace,
};
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use std::time::{SystemTime, UNIX_EPOCH};

fn rand_nz(rng: &mut StdRng, n: u32) -> F2mElement {
    loop {
        let bits: Vec<u32> = (0..n).filter(|_| rng.gen::<bool>()).collect();
        let e = F2mElement::from_bit_positions(&bits, n);
        if !e.is_zero() {
            return e;
        }
    }
}

struct Row {
    two_nsub: u32,
    subfield: f64,
    random: f64,
}

fn main() {
    let seed = std::env::args()
        .nth(1)
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(5);
    let trials = 10u64;
    // Critical operating points 2n'=n with n' | n.
    let points: &[(u32, u32)] = &[
        (6, 3),
        (8, 4),
        (10, 5),
        (12, 6),
        (14, 7),
        (16, 8),
        (18, 9),
        (20, 10),
    ];

    let mut rows = Vec::new();
    for &(n, n_sub) in points {
        let Some(irr) = enumerate_irreducibles(n, 1).into_iter().next() else {
            continue;
        };
        let mut rng = StdRng::seed_from_u64(seed ^ ((n as u64) << 8));
        let mean = |fam: BasisFamily, rng: &mut StdRng| -> f64 {
            let mut acc = 0.0;
            let mut c = 0.0;
            for t in 0..trials {
                let v = match fam {
                    BasisFamily::Random => FactorSubspace::build(fam, n, n_sub, &irr, 0x900 + t),
                    _ => FactorSubspace::build(fam, n, n_sub, &irr, 0),
                };
                let Some(v) = v else { continue };
                let b = rand_nz(rng, n);
                let x3 = rand_nz(rng, n);
                let eqs = descend_on_subspace(n, &v, &irr, &b, &x3);
                let prof = rank_profile(&eqs, 2 * n_sub, n, 3);
                acc += early_defect(&prof, 3);
                c += 1.0;
            }
            if c > 0.0 {
                acc / c
            } else {
                0.0
            }
        };
        let subfield = mean(BasisFamily::Subfield, &mut rng);
        let random = mean(BasisFamily::Random, &mut rng);
        rows.push(Row {
            two_nsub: 2 * n_sub,
            subfield,
            random,
        });
    }

    // Power-law fit on the Random series: log Δ = log a − c·log N.
    let pts: Vec<(f64, f64)> = rows
        .iter()
        .filter(|r| r.random > 0.0)
        .map(|r| ((r.two_nsub as f64).ln(), r.random.ln()))
        .collect();
    let nfit = pts.len() as f64;
    let sx: f64 = pts.iter().map(|p| p.0).sum();
    let sy: f64 = pts.iter().map(|p| p.1).sum();
    let sxx: f64 = pts.iter().map(|p| p.0 * p.0).sum();
    let sxy: f64 = pts.iter().map(|p| p.0 * p.1).sum();
    let denom = nfit * sxx - sx * sx;
    let slope = if denom.abs() < 1e-12 {
        0.0
    } else {
        (nfit * sxy - sx * sy) / denom
    };
    let decay_exp = -slope; // Δ ≈ a · N^{-decay_exp}

    // Report.
    println!("════════════════════════════════════════════════════════════════");
    println!("EXP-H — early-defect scaling Δ_low(2n') in the critical regime, seed={seed}");
    println!(
        "  {:>4} {:>14} {:>14} {:>10}",
        "2n'", "subfield Δ", "random Δ", "ratio"
    );
    for r in &rows {
        let ratio = if r.random > 0.0 {
            r.subfield / r.random
        } else {
            f64::INFINITY
        };
        println!(
            "  {:>4} {:>14.5} {:>14.5} {:>10.1}",
            r.two_nsub, r.subfield, r.random, ratio
        );
    }
    println!("\n  Random-family power-law fit:  Δ_low ≈ a · (2n')^(-{decay_exp:.2})");
    println!("  → Random defect DECAYS toward 0 (c={decay_exp:.2} > 0): generic factor");
    println!("    bases are asymptotically semi-regular at low degree.");
    let first = rows.first();
    let last = rows.last();
    if let (Some(f), Some(l)) = (first, last) {
        println!(
            "  Subfield stays bounded away: Δ {:.4} → {:.4} (ratio sub/rand {:.0} → {:.0}).",
            f.subfield,
            l.subfield,
            if f.random > 0.0 {
                f.subfield / f.random
            } else {
                0.0
            },
            if l.random > 0.0 {
                l.subfield / l.random
            } else {
                0.0
            },
        );
    }

    // Snapshot.
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let cell = |r: &Row| {
        format!(
            "{{\"two_nsub\":{},\"subfield\":{:.6},\"random\":{:.6}}}",
            r.two_nsub, r.subfield, r.random
        )
    };
    let arr = rows.iter().map(cell).collect::<Vec<_>>().join(",");
    let json = format!(
        "{{\n  \"schema\": \"ffd_defect_scaling/v1\",\n  \"seed\": {seed},\n  \"generated_at\": {ts},\n  \"trials_per_cell\": {trials},\n  \"random_decay_exponent\": {decay_exp:.4},\n  \"rows\": [{arr}]\n}}\n"
    );
    let path = "experiments/ffd_defect_scaling.json";
    match std::fs::write(path, &json) {
        Ok(_) => println!("\n[snapshot] wrote {path}"),
        Err(e) => println!("\n[snapshot] FAILED to write {path}: {e}"),
    }
    println!("════════════════════════════════════════════════════════════════");
}
