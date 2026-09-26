//! EXP-R5 — composing one-sided guessing with the mutant route.
//!
//! Iteration 1 killed hybrid slicing on its own but left one usable fact:
//! **one-sided** guessing reaches the `D* = 2` floor at exactly `k₂ = n'`,
//! a collapse fraction `c = 1/2`, flat across sizes and seeds. Iteration 2
//! showed lever L4 (degree falls) lowers the working degree on the hard
//! family. This composes them.
//!
//! ## G-R5 as pre-registered is degenerate — and that is the first finding
//!
//! `research/notes/index-calculus/RESEARCH_DEGREE_REDUCTION.md` registered G-R5 as *"`c(composed) < 1/2`
//! at ≥ 2 operating points"*. The composed route hits `c = 0.000`
//! everywhere — the mutant system is already at `D* = 2` with **no guessing
//! at all**, which is just iteration 2's result restated. The gate passes
//! trivially and measures nothing.
//!
//! That is a gate failure, not a result, and it is the third instance of one
//! error in this thread: a metric that counts guesses while ignoring what
//! each slice costs. Iteration 1 hit it as the boundary optimum; iteration 2
//! as the uncharged extraction. So the collapse fraction is reported here
//! for the record, and the decision moves to **G-R5′**: minimise *total
//! work* over `k` for each route and compare.
//!
//! ```text
//!   raw route      total(k) = 2^k · macaulay(N−k, n,       D*_raw)
//!   composed route total(k) = 2^k · [extract(N−k) + macaulay(N−k, aug, D*_mut)]
//!   baseline                = 2^N · n      (enumeration of V × V)
//! ```
//!
//! Gate **G-R5′**: the composed route is *supported* if its best-`k` total
//! beats both the raw guess-only route and `2^N` enumeration at every
//! operating point; *killed* if it loses to the raw route (the mutants cost
//! more than the guesses they save); *blocked* if it wins on some sizes and
//! the margin is moving the right way.
//!
//! Run: `cargo run --release --example degree_reduction_composed [seed]`
//! Snapshot → `experiments/degree_reduction_composed.json`

use cryptanalysis_suite::cryptanalysis::degree_reduction::{
    log2_enumeration_cost, run_composed_sweep, ComposedSweep, GuessPattern,
};
use cryptanalysis_suite::cryptanalysis::descent_expansion::enumerate_irreducibles;
use cryptanalysis_suite::cryptanalysis::descent_lowgamma::BasisFamily;
use std::time::{SystemTime, UNIX_EPOCH};

const OMEGA: f64 = 2.807;

/// Best `(k, log2 total)` over a sweep, for a route given as a closure.
fn best_over_k(
    sw: &ComposedSweep,
    f: impl Fn(&cryptanalysis_suite::cryptanalysis::degree_reduction::ComposedRow) -> f64,
) -> (u32, f64) {
    sw.rows
        .iter()
        .map(|r| (r.k, f(r)))
        .filter(|(_, c)| c.is_finite())
        .min_by(|a, b| a.1.partial_cmp(&b.1).unwrap())
        .unwrap_or((0, f64::NAN))
}

fn main() {
    let seed = std::env::args()
        .nth(1)
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(7);

    let points: &[(u32, u32)] = &[(10, 5), (12, 6), (14, 7)];
    let families = [BasisFamily::Random, BasisFamily::Coordinate];
    let (targets, slices, rounds) = (6u32, 4u32, 5u32);

    println!("════════════════════════════════════════════════════════════════");
    println!("EXP-R5 — one-sided guessing composed with the mutant route");
    println!("seed={seed}  pattern=one-side  targets/cell={targets}  slices/k={slices}");
    println!("════════════════════════════════════════════════════════════════");

    let mut sweeps: Vec<ComposedSweep> = Vec::new();
    for &family in &families {
        for &(n, n_sub) in points {
            let Some(irr) = enumerate_irreducibles(n, 1).into_iter().next() else {
                continue;
            };
            let Some(sw) = run_composed_sweep(
                family,
                GuessPattern::OneSide,
                n,
                n_sub,
                &irr,
                2 * n_sub - 2,
                targets,
                slices,
                7,
                rounds,
                seed ^ ((n as u64) << 8),
            ) else {
                continue;
            };

            println!(
                "\n── {family:?}  n={n}  N={}  targets={} ──",
                sw.full_vars, sw.targets
            );
            println!(
                "  {:>2} {:>5} {:>11} {:>11} {:>8} {:>11} {:>13}",
                "k", "vars", "raw D*(max)", "mut D*(max)", "newgen", "log2 raw", "log2 composed"
            );
            for r in &sw.rows {
                println!(
                    "  {:>2} {:>5} {:>7.2}({})  {:>7.2}({})  {:>8.1} {:>11.2} {:>13.2}",
                    r.k,
                    r.vars,
                    r.raw_dstar_mean,
                    r.raw_dstar_max,
                    r.mut_dstar_mean,
                    r.mut_dstar_max,
                    r.new_generators_mean,
                    r.log2_raw_total(sw.n, OMEGA),
                    r.log2_composed_total(OMEGA),
                );
            }
            let enume = log2_enumeration_cost(sw.full_vars, sw.n);
            let (kr, cr) = best_over_k(&sw, |r| r.log2_raw_total(sw.n, OMEGA));
            let (kc, cc) = best_over_k(&sw, |r| r.log2_composed_total(OMEGA));
            println!(
                "  collapse fraction (pre-registered G-R5): raw c={:?}  composed c={:?}",
                sw.raw_collapse_fraction(),
                sw.mutant_collapse_fraction()
            );
            println!("  enumeration baseline 2^N·n: log2 = {enume:.2}");
            println!(
                "  best raw      : k={kr:<3} log2 = {cr:.2}  (vs enum {:+.2})",
                enume - cr
            );
            println!(
                "  best composed : k={kc:<3} log2 = {cc:.2}  (vs enum {:+.2})",
                enume - cc
            );
            println!(
                "  composed − raw = {:+.2} bits  [{}]",
                cr - cc,
                if cc < cr {
                    "composed wins"
                } else {
                    "raw guessing wins"
                }
            );
            // Same boundary check iteration 1 introduced: an optimum at the
            // largest k scanned is exhaustive search, not an optimum.
            let raw_int = sw.optimum_is_interior(|r| r.log2_raw_total(sw.n, OMEGA));
            let comp_int = sw.optimum_is_interior(|r| r.log2_composed_total(OMEGA));
            if !raw_int || !comp_int {
                println!(
                    "  [boundary] optimum at the largest k scanned — raw interior: {raw_int}, composed interior: {comp_int}"
                );
            }
            // The one place composition genuinely helps is k=0 (no guessing),
            // which is iteration 2's result; print it so the contrast is visible.
            if let Some(r0) = sw.rows.first() {
                println!(
                    "  at k=0 (no guessing): raw {:.2} vs composed {:.2} → {:+.2} bits for the mutants",
                    r0.log2_raw_total(sw.n, OMEGA),
                    r0.log2_composed_total(OMEGA),
                    r0.log2_raw_total(sw.n, OMEGA) - r0.log2_composed_total(OMEGA)
                );
            }
            let censored: u32 = sw.rows.iter().map(|r| r.censored).sum();
            if censored > 0 {
                println!("  [warn] {censored} slice(s) censored at d_max");
            }
            sweeps.push(sw);
        }
    }

    // ── Verdicts ────────────────────────────────────────────────────
    println!("\n════════════════════════════════════════════════════════════════");
    println!("G-R5 (pre-registered, collapse fraction) — DEGENERATE");
    println!("════════════════════════════════════════════════════════════════");
    println!("\n  The composed route reaches the D*=2 floor at k=0 in every cell,");
    println!("  so c(composed)=0 < 1/2 passes by construction. That is iteration");
    println!("  2's result restated, not evidence about composition: the metric");
    println!("  counts guesses and ignores what each slice costs. Recorded as a");
    println!("  gate failure; G-R5' below is the replacement, scored on work.");

    println!("\n════════════════════════════════════════════════════════════════");
    println!("G-R5' — total work, best k per route");
    println!("════════════════════════════════════════════════════════════════");
    println!(
        "\n  {:>12} {:>4} {:>10} {:>12} {:>14} {:>12}",
        "family", "N", "log2 2^N", "best raw", "best composed", "composed−raw"
    );
    let mut rows: Vec<(String, u32, f64, f64, f64)> = Vec::new();
    for sw in &sweeps {
        let enume = log2_enumeration_cost(sw.full_vars, sw.n);
        let (_, cr) = best_over_k(sw, |r| r.log2_raw_total(sw.n, OMEGA));
        let (_, cc) = best_over_k(sw, |r| r.log2_composed_total(OMEGA));
        println!(
            "  {:>12} {:>4} {:>10.2} {:>12.2} {:>14.2} {:>+12.2}",
            format!("{:?}", sw.family),
            sw.full_vars,
            enume,
            cr,
            cc,
            cr - cc
        );
        rows.push((format!("{:?}", sw.family), sw.full_vars, enume, cr, cc));
    }

    for &family in &families {
        let fam: Vec<&(String, u32, f64, f64, f64)> = rows
            .iter()
            .filter(|r| r.0 == format!("{family:?}"))
            .collect();
        if fam.is_empty() {
            continue;
        }
        let composed_beats_raw = fam.iter().all(|r| r.4 < r.3 - 1e-9);
        let composed_beats_enum = fam.iter().all(|r| r.4 < r.2 - 1e-9);
        let raw_beats_enum = fam.iter().all(|r| r.3 < r.2 - 1e-9);
        let deltas: Vec<f64> = fam.iter().map(|r| r.3 - r.4).collect();
        // "Closing" needs a MATERIAL trend, not any non-negative drift. The
        // first version of this gate called a 0.01-bit-per-step wobble
        // "closing", which would have dressed a flat line as progress.
        // Threshold: the gap must shrink by >= 0.25 bits per size step.
        const CLOSING_BITS_PER_STEP: f64 = 0.25;
        let closing = deltas.len() >= 2
            && deltas
                .windows(2)
                .all(|w| w[1] - w[0] >= CLOSING_BITS_PER_STEP - 1e-9);
        let verdict = if composed_beats_raw && composed_beats_enum {
            "SUPPORTED (composed beats both the raw route and 2^N everywhere)"
        } else if !composed_beats_raw && closing {
            "BLOCKED (composed loses to raw guessing, but the gap is closing materially with N)"
        } else if !composed_beats_raw {
            "KILLED (composed loses to raw guessing and the gap is FLAT, not closing)"
        } else {
            "BLOCKED (beats raw but not 2^N enumeration)"
        };
        println!("\n  {family:?}: → G-R5' {verdict}");
        println!(
            "    raw route beats 2^N: {}   composed beats 2^N: {}",
            raw_beats_enum, composed_beats_enum
        );
        println!(
            "    composed−raw per N: {:?}",
            fam.iter()
                .map(|r| format!("N={}:{:+.2}", r.1, r.3 - r.4))
                .collect::<Vec<_>>()
        );
    }

    // ── Snapshot ────────────────────────────────────────────────────
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let cells = sweeps
        .iter()
        .map(|sw| {
            let enume = log2_enumeration_cost(sw.full_vars, sw.n);
            let (kr, cr) = best_over_k(sw, |r| r.log2_raw_total(sw.n, OMEGA));
            let (kc, cc) = best_over_k(sw, |r| r.log2_composed_total(OMEGA));
            let rows = sw
                .rows
                .iter()
                .map(|r| {
                    format!(
                        "{{\"k\":{},\"vars\":{},\"slices\":{},\"censored\":{},\
                         \"raw_dstar_mean\":{:.4},\"raw_dstar_max\":{},\
                         \"mut_dstar_mean\":{:.4},\"mut_dstar_max\":{},\
                         \"mut_working_mean\":{:.4},\"new_generators_mean\":{:.3},\
                         \"aug_eqs_mean\":{:.3},\"log2_extraction_cost\":{:.4},\
                         \"log2_raw_total\":{:.4},\"log2_composed_total\":{:.4}}}",
                        r.k,
                        r.vars,
                        r.slices,
                        r.censored,
                        r.raw_dstar_mean,
                        r.raw_dstar_max,
                        r.mut_dstar_mean,
                        r.mut_dstar_max,
                        r.mut_working_mean,
                        r.new_generators_mean,
                        r.aug_eqs_mean,
                        r.log2_extraction_cost,
                        r.log2_raw_total(sw.n, OMEGA),
                        r.log2_composed_total(OMEGA),
                    )
                })
                .collect::<Vec<_>>()
                .join(",");
            let fmt = |v: Option<f64>| match v {
                Some(x) => format!("{x:.4}"),
                None => "null".to_string(),
            };
            format!(
                "{{\"family\":\"{:?}\",\"n\":{},\"n_sub\":{},\"full_vars\":{},\"targets\":{},\
                 \"rounds\":{},\"log2_enumeration\":{:.4},\
                 \"raw_collapse_fraction\":{},\"composed_collapse_fraction\":{},\
                 \"best_k_raw\":{},\"best_log2_raw\":{:.4},\
                 \"best_k_composed\":{},\"best_log2_composed\":{:.4},\
                 \"rows\":[{}]}}",
                sw.family,
                sw.n,
                sw.n_sub,
                sw.full_vars,
                sw.targets,
                sw.rounds,
                enume,
                fmt(sw.raw_collapse_fraction()),
                fmt(sw.mutant_collapse_fraction()),
                kr,
                cr,
                kc,
                cc,
                rows
            )
        })
        .collect::<Vec<_>>()
        .join(",");
    let json = format!(
        "{{\n  \"schema\": \"degree_reduction_composed/v1\",\n  \"experiment\": \"EXP-R5\",\n  \
         \"seed\": {seed},\n  \"generated_at\": {ts},\n  \"omega\": {OMEGA},\n  \
         \"pattern\": \"one-side\",\n  \
         \"note\": \"G-R5 (collapse fraction) is degenerate: composed reaches the floor at k=0. \
G-R5' scores total work instead.\",\n  \"cells\": [{cells}]\n}}\n"
    );
    let path = "experiments/degree_reduction_composed.json";
    match std::fs::write(path, &json) {
        Ok(_) => println!("\n[snapshot] wrote {path}"),
        Err(e) => println!("\n[snapshot] FAILED to write {path}: {e}"),
    }
    println!("════════════════════════════════════════════════════════════════");
}
