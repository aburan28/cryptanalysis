//! EXP-R4′ — is the `Δ_low` screen fixable by renormalising, or is the
//! problem deeper than units?
//!
//! Iteration 1 found the FFD program's `Δ_low` screen reads wrong across
//! systems of different shape: under slicing, `D*` falls monotonically while
//! `Δ_low` wanders. The obvious diagnosis was **units** — `Δ_low` is
//! normalised by `cols(D_low)`, a monomial count that shrinks with the
//! variable count — and the obvious fix a better denominator. That
//! diagnosis was never tested; this experiment tests it.
//!
//! ## Why this is the queue head
//!
//! L2 (symmetrisation) is the thread's only untested lever, and it *changes
//! the variable count*. So `Δ_low` cannot score it until we know whether a
//! shape-corrected defect exists — or whether the obstruction is something
//! a denominator cannot fix.
//!
//! ## The design separates the two candidate causes
//!
//! | group | what varies | what is held | tests |
//! |---|---|---|---|
//! | `within-shape` | family, target | `(vars, eqs)`, `ρ` | the regime the law was fitted in |
//! | `rho-varies` | `k` (slicing) | `eqs` | shape **and** `ρ` both move |
//! | `rho-matched` | `(n, n')` at `2n'=n` | `ρ ≈ 1` | shape moves, `ρ` does not |
//!
//! Five candidate defect summaries are scored on each group. If some
//! variant rescues `rho-varies`, the problem was units and we have the
//! screen. If the law holds on `within-shape` and `rho-matched` but fails on
//! `rho-varies` for **every** variant, then the obstruction is not units at
//! all: over-determination flips the law's sign, and no rescaling fixes a
//! sign flip. The prescription would become "compare at matched `ρ`".
//!
//! Gate **G-R4′**: a variant is *supported* if it reaches `ρ_s ≤ −0.6` on
//! **all three** groups. *Killed* if no variant does. The `rho-matched`
//! column decides the diagnosis: if variants pass there but fail on
//! `rho-varies`, the cause is regime, not shape.
//!
//! Run: `cargo run --release --example degree_reduction_defect [seed]`
//! Snapshot → `experiments/degree_reduction_defect.json`

use cryptanalysis_suite::cryptanalysis::degree_reduction::{
    collect_defect_cells, collect_rho_matched_cells, DefectCell, DEFECT_VARIANTS,
};
use cryptanalysis_suite::cryptanalysis::descent_expansion::{enumerate_irreducibles, spearman};
use cryptanalysis_suite::cryptanalysis::descent_lowgamma::BasisFamily;
use std::time::{SystemTime, UNIX_EPOCH};

/// Spearman of one variant against `D*` over the cells in a group.
fn rho_for(cells: &[&DefectCell], variant_idx: usize) -> Option<f64> {
    let xs: Vec<f64> = cells.iter().map(|c| c.defects[variant_idx]).collect();
    let ys: Vec<f64> = cells.iter().map(|c| c.dstar as f64).collect();
    spearman(&xs, &ys)
}

fn main() {
    let seed = std::env::args()
        .nth(1)
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(7);

    let families = [
        BasisFamily::Random,
        BasisFamily::Coordinate,
        BasisFamily::Subfield,
    ];
    let cutoff = 3u32;
    let d_max = 7u32;

    println!("════════════════════════════════════════════════════════════════");
    println!("EXP-R4' — can a renormalised defect score across system shapes?");
    println!("seed={seed}  cutoff={cutoff}");
    println!("════════════════════════════════════════════════════════════════");

    let mut cells: Vec<DefectCell> = Vec::new();

    // Groups `within-shape` and `rho-varies`, at the critical operating
    // point where the FFD law was fitted.
    for &(n, n_sub) in &[(12u32, 6u32), (14u32, 7u32)] {
        let Some(irr) = enumerate_irreducibles(n, 1).into_iter().next() else {
            continue;
        };
        cells.extend(collect_defect_cells(
            n,
            n_sub,
            &irr,
            &families,
            &[2, 4, 6, 8],
            48,
            d_max,
            cutoff,
            seed ^ ((n as u64) << 8),
        ));
    }

    // Group `rho-matched`: shape moves, `ρ ≈ 1` held.
    let points: Vec<(u32, u32)> = vec![(8, 4), (10, 5), (12, 6), (14, 7)];
    let irrs: Vec<_> = points
        .iter()
        .filter_map(|&(n, _)| enumerate_irreducibles(n, 1).into_iter().next())
        .collect();
    if irrs.len() == points.len() {
        cells.extend(collect_rho_matched_cells(
            &points, &irrs, &families, 48, d_max, cutoff, seed,
        ));
    }

    // ── Analysis ────────────────────────────────────────────────────
    //
    // Two methodological points, both of which the first version of this
    // driver got wrong and both of which changed the numbers:
    //
    // 1. "Within shape" must hold `vars` FIXED. Pooling vars=12 and vars=14
    //    into one group is already a cross-shape comparison wearing the
    //    wrong label.
    // 2. The −0.6 threshold is calibrated against EXP-G's ρ_s = −0.79, which
    //    was measured on **cell means** (one point per (family, size)), not
    //    on individual instances. Correlating raw instances against a
    //    threshold fitted to aggregates compares unlike things and makes
    //    everything fail for a reason unrelated to shape. The pooled groups
    //    are therefore aggregated to (family, vars) means first.

    /// Mean of a variant and of `D*` over a set of cells → one point.
    fn aggregate(cells: &[&DefectCell], variant_idx: usize) -> (f64, f64) {
        let n = cells.len().max(1) as f64;
        (
            cells.iter().map(|c| c.defects[variant_idx]).sum::<f64>() / n,
            cells.iter().map(|c| c.dstar as f64).sum::<f64>() / n,
        )
    }

    /// Spearman over (family, vars) cell means — the EXP-G methodology.
    fn rho_aggregated(cells: &[&DefectCell], variant_idx: usize) -> Option<f64> {
        let mut keys: Vec<(String, u32)> = cells
            .iter()
            .map(|c| (format!("{:?}", c.family), c.vars))
            .collect();
        keys.sort();
        keys.dedup();
        let mut xs = Vec::new();
        let mut ys = Vec::new();
        for (fam, vars) in &keys {
            let grp: Vec<&DefectCell> = cells
                .iter()
                .filter(|c| format!("{:?}", c.family) == *fam && c.vars == *vars)
                .copied()
                .collect();
            if grp.is_empty() {
                continue;
            }
            let (x, y) = aggregate(&grp, variant_idx);
            xs.push(x);
            ys.push(y);
        }
        spearman(&xs, &ys)
    }

    /// Mean of the per-`vars` Spearman — the **size-controlled** statistic.
    ///
    /// This is the control that decides whether a strong *pooled*
    /// correlation is real structure or just a size proxy: both `D*` and a
    /// size-normalised defect vary systematically with `N`, so pooling
    /// across sizes can manufacture a correlation out of that shared trend
    /// alone. Holding `vars` fixed removes it.
    fn rho_within_vars(cells: &[&DefectCell], variant_idx: usize) -> Option<f64> {
        let mut sizes: Vec<u32> = cells.iter().map(|c| c.vars).collect();
        sizes.sort_unstable();
        sizes.dedup();
        let vals: Vec<f64> = sizes
            .iter()
            .filter_map(|v| {
                let sel: Vec<&DefectCell> =
                    cells.iter().filter(|c| c.vars == *v).copied().collect();
                rho_for(&sel, variant_idx)
            })
            .collect();
        if vals.is_empty() {
            None
        } else {
            Some(vals.iter().sum::<f64>() / vals.len() as f64)
        }
    }

    let pick = |g: &str| -> Vec<&DefectCell> { cells.iter().filter(|c| c.group == g).collect() };

    // Group 1 — within shape: one correlation per fixed `vars`, over
    // instances (aggregating here would leave 3 points per size).
    println!("\n── group within-shape (vars held fixed; family & target vary) ──");
    let ws = pick("within-shape");
    let mut ws_sizes: Vec<u32> = ws.iter().map(|c| c.vars).collect();
    ws_sizes.sort_unstable();
    ws_sizes.dedup();
    let mut within_mean: Vec<Option<f64>> = vec![None; DEFECT_VARIANTS.len()];
    {
        print!("   {:>14}", "variant");
        for v in &ws_sizes {
            print!("  vars={v:<7}");
        }
        println!("      mean");
        for (i, v) in DEFECT_VARIANTS.iter().enumerate() {
            print!("   {:>14}", v.label());
            let mut vals = Vec::new();
            for size in &ws_sizes {
                let sel: Vec<&DefectCell> =
                    ws.iter().filter(|c| c.vars == *size).copied().collect();
                match rho_for(&sel, i) {
                    Some(r) => {
                        print!("  {r:>10.3} ");
                        vals.push(r);
                    }
                    None => print!("  {:>10} ", "n/a"),
                }
            }
            if vals.is_empty() {
                println!("       n/a");
            } else {
                let m = vals.iter().sum::<f64>() / vals.len() as f64;
                within_mean[i] = Some(m);
                println!("  {m:>8.3}");
            }
        }
    }

    // Groups 2 and 3 — pooled, aggregated to (family, vars) cell means.
    let mut pooled: Vec<(&str, Vec<Option<f64>>)> = Vec::new();
    for g in ["rho-varies", "rho-matched"] {
        let sel = pick(g);
        let mut vars: Vec<u32> = sel.iter().map(|c| c.vars).collect();
        vars.sort_unstable();
        vars.dedup();
        let rho_lo = sel.iter().map(|c| c.rho).fold(f64::INFINITY, f64::min);
        let rho_hi = sel.iter().map(|c| c.rho).fold(f64::NEG_INFINITY, f64::max);
        println!(
            "\n── group {g}: {} instances → (family,vars) cell means, vars {vars:?}, rho {rho_lo:.2}–{rho_hi:.2} ──",
            sel.len()
        );
        println!("   {:>14} {:>10}", "variant", "rho_s");
        let mut rs = Vec::new();
        for (i, v) in DEFECT_VARIANTS.iter().enumerate() {
            let r = rho_aggregated(&sel, i);
            match r {
                Some(x) => println!("   {:>14} {:>10.3}", v.label(), x),
                None => println!("   {:>14} {:>10}", v.label(), "n/a"),
            }
            rs.push(r);
        }
        pooled.push((g, rs));
    }

    // ── The decisive contrast: pooled vs size-controlled ────────────
    println!("\n════════════════════════════════════════════════════════════════");
    println!("Is the pooled correlation structure, or a size proxy?");
    println!("════════════════════════════════════════════════════════════════");
    println!("\n  Both D* and a size-normalised defect move systematically with N, so");
    println!("  pooling across sizes can manufacture a correlation from that shared");
    println!("  trend alone. Holding vars fixed removes it. If 'pooled' is strong and");
    println!("  'size-controlled' is weak, the pooled figure is a size proxy.");
    for g in ["rho-varies", "rho-matched"] {
        let sel = pick(g);
        println!("\n  group {g}");
        println!(
            "   {:>14} {:>10} {:>18}",
            "variant", "pooled", "size-controlled"
        );
        for (i, v) in DEFECT_VARIANTS.iter().enumerate() {
            let pooled_r = rho_aggregated(&sel, i);
            let ctrl = rho_within_vars(&sel, i);
            let f = |r: Option<f64>| match r {
                Some(x) => format!("{x:.3}"),
                None => "n/a".to_string(),
            };
            println!("   {:>14} {:>10} {:>18}", v.label(), f(pooled_r), f(ctrl));
        }
    }

    // ── Verdict ─────────────────────────────────────────────────────
    println!("\n════════════════════════════════════════════════════════════════");
    println!("G-R4' verdict");
    println!("════════════════════════════════════════════════════════════════");
    println!(
        "\n   {:>14} {:>14} {:>12} {:>13} {:>10}",
        "variant", "within-shape", "rho-varies", "rho-matched", "all ≤ −0.6"
    );
    let mut any_passes = false;
    let mut per_variant: Vec<(String, Vec<Option<f64>>)> = Vec::new();
    for (i, v) in DEFECT_VARIANTS.iter().enumerate() {
        let rs = vec![within_mean[i], pooled[0].1[i], pooled[1].1[i]];
        let ok = rs.iter().all(|r| matches!(r, Some(x) if *x <= -0.6));
        if ok {
            any_passes = true;
        }
        let fmt = |r: &Option<f64>| match r {
            Some(x) => format!("{x:.3}"),
            None => "n/a".to_string(),
        };
        println!(
            "   {:>14} {:>14} {:>12} {:>13} {:>10}",
            v.label(),
            fmt(&rs[0]),
            fmt(&rs[1]),
            fmt(&rs[2]),
            if ok { "yes" } else { "no" }
        );
        per_variant.push((v.label().to_string(), rs));
    }

    let passes_matched: Vec<&String> = per_variant
        .iter()
        .filter(|(_, rs)| matches!(rs[2], Some(x) if x <= -0.6))
        .map(|(l, _)| l)
        .collect();
    let passes_varies: Vec<&String> = per_variant
        .iter()
        .filter(|(_, rs)| matches!(rs[1], Some(x) if x <= -0.6))
        .map(|(l, _)| l)
        .collect();
    let passes_within: Vec<&String> = per_variant
        .iter()
        .filter(|(_, rs)| matches!(rs[0], Some(x) if x <= -0.6))
        .map(|(l, _)| l)
        .collect();

    if any_passes {
        println!("\n  → G-R4' SUPPORTED. A variant scores across all three groups, so the");
        println!("    obstruction WAS units and that variant is the cross-shape screen.");
    } else {
        println!("\n  → G-R4' KILLED. No variant scores on all three groups.");
        println!("\n    passes within-shape: {passes_within:?}");
        println!("    passes rho-matched : {passes_matched:?}");
        println!("    passes rho-varies  : {passes_varies:?}");

        // Compare the pooled figure against its size-controlled counterpart
        // on the strongest group, and let the gap speak.
        let sel = pick("rho-matched");
        let mut gaps = Vec::new();
        for (i, v) in DEFECT_VARIANTS.iter().enumerate() {
            if let (Some(p), Some(c)) = (rho_aggregated(&sel, i), rho_within_vars(&sel, i)) {
                gaps.push((v.label(), p, c));
            }
        }
        let confounded = gaps
            .iter()
            .filter(|(_, p, _)| *p <= -0.6)
            .all(|(_, _, c)| *c > -0.6);
        if confounded && !gaps.is_empty() {
            println!("\n    Diagnosis: the strong pooled numbers are a SIZE PROXY, not a screen.");
            for (l, p, c) in &gaps {
                println!("      {l:>14}: pooled {p:+.3}  →  size-controlled {c:+.3}");
            }
            println!("\n    Every variant that clears the bar pooled fails it once vars is held");
            println!("    fixed. D* and a size-normalised defect both trend with N, and pooling");
            println!("    across sizes reads that shared trend as correlation. So no rescaling");
            println!("    delivers a cross-shape screen — the quantity being rescaled does not");
            println!("    carry enough structure once the size trend is removed.");
            println!("\n    Worth checking upstream: the FFD program's own rho_s = -0.79 was");
            println!("    also pooled across 2n' in {{4..14}}, so it may share this property.");
            println!("    That is a caveat to test, not a refutation — the quantity measured");
            println!("    there (cell means over ten operating points) is related but not");
            println!("    identical to this one.");
            println!("\n    Prescription for L2: do not lean on Delta_low to score it. Compare");
            println!("    symmetrised against raw on MATCHED (vars, eqs, rho) and score on");
            println!("    measured D* and total work, as iterations 2 and 3 did.");
        } else if passes_within.is_empty() {
            println!("\n    Note: nothing clears the bar within a fixed shape. Read the");
            println!("    relative ordering across groups rather than the absolute level.");
        } else {
            println!("\n    Mixed pattern — read the per-group tables before concluding.");
        }
    }

    // ── Snapshot ────────────────────────────────────────────────────
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let cell_json = cells
        .iter()
        .map(|c| {
            format!(
                "{{\"group\":\"{}\",\"family\":\"{:?}\",\"vars\":{},\"eqs\":{},\"rho\":{:.4},\"dstar\":{},\"defects\":[{}]}}",
                c.group,
                c.family,
                c.vars,
                c.eqs,
                c.rho,
                c.dstar,
                c.defects
                    .iter()
                    .map(|d| format!("{d:.6}"))
                    .collect::<Vec<_>>()
                    .join(",")
            )
        })
        .collect::<Vec<_>>()
        .join(",");
    let summary = per_variant
        .iter()
        .map(|(l, rs)| {
            let f = |r: &Option<f64>| match r {
                Some(x) => format!("{x:.4}"),
                None => "null".to_string(),
            };
            format!(
                "{{\"variant\":\"{l}\",\"within_shape\":{},\"rho_varies\":{},\"rho_matched\":{}}}",
                f(&rs[0]),
                f(&rs[1]),
                f(&rs[2])
            )
        })
        .collect::<Vec<_>>()
        .join(",");
    let json = format!(
        "{{\n  \"schema\": \"degree_reduction_defect/v1\",\n  \"experiment\": \"EXP-R4prime\",\n  \
         \"seed\": {seed},\n  \"generated_at\": {ts},\n  \"cutoff\": {cutoff},\n  \
         \"variants\": [{}],\n  \"summary\": [{summary}],\n  \"cells\": [{cell_json}]\n}}\n",
        DEFECT_VARIANTS
            .iter()
            .map(|v| format!("\"{}\"", v.label()))
            .collect::<Vec<_>>()
            .join(",")
    );
    let path = "experiments/degree_reduction_defect.json";
    match std::fs::write(path, &json) {
        Ok(_) => println!("\n[snapshot] wrote {path}"),
        Err(e) => println!("\n[snapshot] FAILED to write {path}: {e}"),
    }
    println!("════════════════════════════════════════════════════════════════");
}
