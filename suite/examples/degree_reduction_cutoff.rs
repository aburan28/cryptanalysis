//! EXP-R6 — is the `Δ_low` screen's within-family sign inversion repairable?
//!
//! ## The question
//!
//! EXP-R4d (iteration 8) found `ρ_s(Δ_low, D*)` **positive** inside a
//! homogeneous group, against the `−0.85` the same data gives between
//! factor-base families, and explained it by **censoring at the cutoff**: a
//! target that refutes at `D* = 2` never exercises degree 3, so its
//! cutoff-3 defect is ~0 by construction.
//!
//! That explanation predicts a repair. If the inversion is an artifact of
//! *where the cutoff sits*, then measuring at a degree every system must
//! pass through should restore the negative sign — and the FFD screen would
//! become usable inside a construction, not only between constructions.
//! This tests that, because it is the screen's value to the defensive
//! program that is at stake rather than any lever of this thread.
//!
//! ## Six readings, not one
//!
//! Per target: the **per-degree** fractions `δ(2), δ(3), δ(4)` and the
//! **cumulative** `Δ_low` at cutoffs 2, 3, 4. The screen uses the
//! cumulative form at cutoff 3; the other five say whether that choice is
//! what produces the sign.
//!
//! Gate **G-R6** (registered in the charter before this file):
//! *repairable* if any reading reaches within-family `ρ_s ≤ −0.6` on a
//! majority of decidable cells; *structurally unrepairable* if every
//! reading is positive on a majority; *partial* otherwise.
//!
//! **Disclosure**: a 6-cell single-seed probe run before the gate was
//! written already showed cutoff 2 behaving like cutoff 3. The gate is
//! therefore not blind on those two readings; its value is breadth — 3
//! families × 4 sizes × 3 seeds × six readings, against the probe's two
//! readings at a twelfth of the cells.
//!
//! ## Why the variance decomposition is reported too
//!
//! The claim under test is that a real between-family signal rides on an
//! instance-level component of the *opposite* sign. If so, the between
//! component should carry most of each reading's variance, and the screen's
//! correctness between families and its wrongness within them are two
//! readings of one decomposition rather than two separate facts.
//!
//! Run: `cargo run --release --example degree_reduction_cutoff [seeds...]`
//! Snapshot → `experiments/degree_reduction_cutoff.json`

use cryptanalysis_suite::cryptanalysis::degree_reduction::{
    run_defect_profile_cell, size_control, BlockedObs, DefectProfileRow, PROFILE_READINGS,
};
use cryptanalysis_suite::cryptanalysis::descent_expansion::{enumerate_irreducibles, spearman};
use cryptanalysis_suite::cryptanalysis::descent_lowgamma::BasisFamily;
use std::collections::BTreeMap;
use std::time::{SystemTime, UNIX_EPOCH};

fn fmt(v: Option<f64>) -> String {
    v.map(|x| format!("{x:+.3}")).unwrap_or("n/a".into())
}

fn main() {
    let seeds: Vec<u64> = {
        let g: Vec<u64> = std::env::args()
            .skip(1)
            .filter_map(|s| s.parse::<u64>().ok())
            .collect();
        if g.is_empty() {
            vec![7, 11, 23]
        } else {
            g
        }
    };
    let points: &[(u32, u32)] = &[(10, 5), (12, 6), (14, 7), (16, 8)];
    let families = [
        BasisFamily::Random,
        BasisFamily::Coordinate,
        BasisFamily::Subfield,
    ];
    let targets = 24u32;

    println!("════════════════════════════════════════════════════════════════");
    println!("EXP-R6 — is the Δ_low screen's within-family sign inversion repairable?");
    println!(
        "seeds={seeds:?}  targets/cell={targets}  readings={}",
        PROFILE_READINGS.len()
    );
    println!("════════════════════════════════════════════════════════════════");

    // (seed, family, N) -> rows
    let mut cells: BTreeMap<(u64, String, u32), Vec<DefectProfileRow>> = BTreeMap::new();
    for &seed in &seeds {
        for &family in &families {
            for &(n, n_sub) in points {
                let Some(irr) = enumerate_irreducibles(n, 1).into_iter().next() else {
                    continue;
                };
                let rows = run_defect_profile_cell(
                    family,
                    n,
                    n_sub,
                    &irr,
                    targets,
                    7,
                    seed ^ ((n as u64) << 8),
                );
                if !rows.is_empty() {
                    cells.insert((seed, format!("{family:?}"), 2 * n_sub), rows);
                }
            }
        }
    }

    // ── Within-family sign, per reading ─────────────────────────────
    println!("\n════════════════════════════════════════════════════════════════");
    println!("Within-family ρ_s(reading, D*) — one correlation per cell");
    println!("════════════════════════════════════════════════════════════════");
    println!("\n  Cells are (seed, family, N). 'neg' counts cells reaching ρ_s ≤ −0.6.\n");
    println!(
        "  {:>18} {:>10} {:>10} {:>10} {:>8}",
        "reading", "decidable", "negative", "positive", "mean ρ_s"
    );
    let mut summary = Vec::new();
    for (i, name) in PROFILE_READINGS.iter().enumerate() {
        let (mut dec, mut neg, mut pos) = (0usize, 0usize, 0usize);
        let mut vals = Vec::new();
        for rows in cells.values() {
            let xs: Vec<f64> = rows.iter().map(|r| r.readings()[i]).collect();
            let ys: Vec<f64> = rows.iter().map(|r| r.dstar as f64).collect();
            if let Some(v) = spearman(&xs, &ys) {
                dec += 1;
                vals.push(v);
                if v <= -0.6 {
                    neg += 1;
                }
                if v > 0.0 {
                    pos += 1;
                }
            }
        }
        let mean = if vals.is_empty() {
            None
        } else {
            Some(vals.iter().sum::<f64>() / vals.len() as f64)
        };
        println!(
            "  {:>18} {:>10} {:>10} {:>10} {:>8}",
            name,
            dec,
            neg,
            pos,
            fmt(mean)
        );
        summary.push((name.to_string(), dec, neg, pos, mean));
    }

    // ── Between-family, for contrast, on the same data ──────────────
    println!("\n════════════════════════════════════════════════════════════════");
    println!("Between-family, same data: family means blocked on (seed, N)");
    println!("════════════════════════════════════════════════════════════════");
    println!(
        "\n  {:>18} {:>14} {:>14} {:>14}",
        "reading", "blocked rank", "mean per-block", "fixed-effects"
    );
    let mut between = Vec::new();
    for (i, name) in PROFILE_READINGS.iter().enumerate() {
        let mut obs = Vec::new();
        for ((seed, _fam, n), rows) in &cells {
            let k = rows.len() as f64;
            obs.push(BlockedObs {
                block: format!("s{seed} N={n}"),
                x: rows.iter().map(|r| r.readings()[i]).sum::<f64>() / k,
                y: rows.iter().map(|r| r.dstar as f64).sum::<f64>() / k,
            });
        }
        let c = size_control(&obs);
        println!(
            "  {:>18} {:>14} {:>14} {:>14}",
            name,
            fmt(c.blocked_rank),
            fmt(c.mean_per_block),
            fmt(c.fixed_effects)
        );
        between.push((name.to_string(), c));
    }

    // ── Variance decomposition ──────────────────────────────────────
    println!("\n════════════════════════════════════════════════════════════════");
    println!("Variance decomposition — where each reading's spread lives");
    println!("════════════════════════════════════════════════════════════════");
    println!(
        "\n  {:>18} {:>16} {:>16}",
        "reading", "between-family", "within-family"
    );
    let mut decomp = Vec::new();
    for (i, name) in PROFILE_READINGS.iter().enumerate() {
        // Pool at fixed (seed, N): total variance of all targets vs the
        // variance of the family means.
        let (mut sw, mut sb, mut nw, mut nb) = (0.0f64, 0.0f64, 0usize, 0usize);
        let mut by_block: BTreeMap<(u64, u32), Vec<(f64, usize)>> = BTreeMap::new();
        for ((seed, _f, n), rows) in &cells {
            let k = rows.len() as f64;
            let m = rows.iter().map(|r| r.readings()[i]).sum::<f64>() / k;
            for r in rows {
                sw += (r.readings()[i] - m).powi(2);
                nw += 1;
            }
            by_block
                .entry((*seed, *n))
                .or_default()
                .push((m, rows.len()));
        }
        for means in by_block.values() {
            let gm = means.iter().map(|(m, _)| m).sum::<f64>() / means.len() as f64;
            for (m, cnt) in means {
                sb += *cnt as f64 * (m - gm).powi(2);
                nb += 1;
            }
        }
        let tot = sw + sb;
        let (pb, pw) = if tot > 0.0 {
            (100.0 * sb / tot, 100.0 * sw / tot)
        } else {
            (f64::NAN, f64::NAN)
        };
        println!("  {:>18} {:>15.1}% {:>15.1}%", name, pb, pw);
        decomp.push((name.to_string(), pb, pw));
        let _ = (nw, nb);
    }

    // ── G-R6 verdict ────────────────────────────────────────────────
    println!("\n════════════════════════════════════════════════════════════════");
    println!("G-R6 verdict");
    println!("════════════════════════════════════════════════════════════════");
    let any_repairs = summary.iter().any(|(_, d, n, _, _)| *d > 0 && 2 * n > *d);
    let all_positive = summary.iter().all(|(_, d, _, p, _)| *d > 0 && 2 * p > *d);
    let verdict = if any_repairs {
        "REPAIRABLE — some cutoff restores the negative sign within families"
    } else if all_positive {
        "STRUCTURALLY UNREPAIRABLE — every reading runs positive within families"
    } else {
        "PARTIAL — no reading repairs it, but not all run positive either"
    };
    println!("\n  → G-R6: {verdict}");
    if all_positive && !any_repairs {
        println!("\n  No choice of cutoff fixes the sign. That rules out the cutoff-");
        println!("  censoring story as the WHOLE explanation: if the inversion were an");
        println!("  artifact of measuring at degree 3, measuring at degree 2 — which");
        println!("  every system passes through — would not reproduce it.");
        println!("\n  The reading that survives: rank deficiency at degree D and");
        println!("  refutation at degree D are competing descriptions of one row space.");
        println!("  A system that has refuted by D has the maximal row space (it");
        println!("  contains 1); a system that has not is exactly the one carrying a");
        println!("  deficit. So inside a group where the structural defect is constant,");
        println!("  the part of Δ_low that varies IS a restatement of D*, positively.");
        println!("  Nothing to tune away — the screen is between-family by construction.");
    }

    // ── Snapshot ────────────────────────────────────────────────────
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let f = |v: Option<f64>| v.map(|x| format!("{x:.6}")).unwrap_or("null".into());
    let readings = summary
        .iter()
        .zip(&between)
        .zip(&decomp)
        .map(|(((name, dec, neg, pos, mean), (_, c)), (_, pb, pw))| {
            format!(
                "{{\"reading\":\"{name}\",\"decidable_cells\":{dec},\"cells_negative\":{neg},\
                 \"cells_positive\":{pos},\"mean_within_rho\":{},\
                 \"between_blocked_rank\":{},\"between_mean_per_block\":{},\
                 \"between_fixed_effects\":{},\"variance_between_pct\":{pb:.2},\
                 \"variance_within_pct\":{pw:.2}}}",
                f(*mean),
                f(c.blocked_rank),
                f(c.mean_per_block),
                f(c.fixed_effects)
            )
        })
        .collect::<Vec<_>>()
        .join(",\n    ");
    let json = format!(
        "{{\n  \"schema\": \"degree_reduction_cutoff/v1\",\n  \"experiment\": \"EXP-R6\",\n  \
         \"generated_at\": {ts},\n  \"seeds\": {seeds:?},\n  \"targets_per_cell\": {targets},\n  \
         \"cells\": {},\n  \"verdict\": \"{}\",\n  \"readings\": [\n    {readings}\n  ]\n}}\n",
        cells.len(),
        if any_repairs {
            "repairable"
        } else if all_positive {
            "structurally_unrepairable"
        } else {
            "partial"
        }
    );
    let out = "experiments/degree_reduction_cutoff.json";
    match std::fs::write(out, &json) {
        Ok(_) => println!("\n[snapshot] wrote {out}"),
        Err(e) => println!("\n[snapshot] FAILED to write {out}: {e}"),
    }
    println!("════════════════════════════════════════════════════════════════");
}
