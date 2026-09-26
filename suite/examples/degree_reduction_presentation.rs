//! EXP-R4d — does lever L4 act *through* `Δ_low`?
//!
//! ## The question, and why it is still open
//!
//! R4 predicted that every lever acts through the early Hilbert defect,
//! and was **killed as stated** in iteration 4 — but the thing killed was
//! the *statistic*: a pooled, instance-level `ρ_s` across systems of
//! different shape, which R4′ showed cannot compare instances at all.
//! Iteration 6 then found the defect is a strong **family-level**
//! discriminator for factor-base families (`−0.85` blocked rank). That
//! leaves R4's actual question unanswered rather than settled.
//!
//! ## The design, which removes the objection that killed R4
//!
//! Three presentations of the **same system, at the same variable count,
//! on the same target**: the raw descended system, the system after one
//! saturation round, and the fully saturated system. They differ only in
//! how many degree-3 falls have been folded into the generating set — a
//! *dose* axis for L4. Nothing here is cross-shape, so R4′'s objection
//! does not apply and whatever the correlation says, it says about the
//! lever rather than about the sizes.
//!
//! Two statistics, per gate **G-R4d** (registered in the charter before
//! this file was written):
//!
//! 1. **Paired lever effect** — per target, `dΔ = Δ_low(sat) − Δ_low(raw)`
//!    against `dD* = D*(sat) − D*(raw)`, blocked on `(family, N)`. If the
//!    lever works through the defect, the targets whose defect rose most
//!    are the ones whose `D*` fell most: a *negative* correlation.
//! 2. **Presentation-family level** — aggregate to
//!    `(operating point, presentation)` means and run the same three
//!    size-controlled statistics EXP-R4b used.
//!
//! *Supported* if both reach `≤ −0.6`; *killed* if neither does; *partial*
//! if one does.
//!
//! **Degeneracy clause** (registered in advance, because it is the likely
//! outcome): EXP-R3/R3b show the augmented system pinned at `D* = 2` over
//! wide ranges, so `dD*` may be constant at some cells. A constant
//! response admits no correlation; those cells are reported as
//! **degenerate**, not scored and not averaged in as 0, and their count is
//! printed next to the verdict — a gate that passes only because the
//! degenerate cells were dropped is not a pass.
//!
//! Run: `cargo run --release --example degree_reduction_presentation [seed]`
//! Snapshot → `experiments/degree_reduction_presentation.json`

use cryptanalysis_suite::cryptanalysis::degree_reduction::{
    run_presentation_cell, size_control, BlockedObs, PresentationRow, SizeControl, PRESENTATIONS,
};
use cryptanalysis_suite::cryptanalysis::descent_expansion::enumerate_irreducibles;
use cryptanalysis_suite::cryptanalysis::descent_lowgamma::BasisFamily;
use std::collections::BTreeMap;
use std::time::{SystemTime, UNIX_EPOCH};

fn fmt(v: Option<f64>) -> String {
    v.map(|x| format!("{x:+.4}")).unwrap_or("n/a".into())
}

fn report(label: &str, c: &SizeControl) {
    println!(
        "\n── {label}: {} points in {} blocks ──",
        c.n_cells, c.n_blocks
    );
    println!("   {:>34} {}", "pooled rho_s", fmt(c.pooled));
    println!(
        "   {:>34} {}",
        "mean per-block rho_s",
        fmt(c.mean_per_block)
    );
    println!("   {:>34} {}", "blocked rank r", fmt(c.blocked_rank));
    println!("   {:>34} {}", "fixed-effects r", fmt(c.fixed_effects));
}

fn strong(v: Option<f64>) -> bool {
    matches!(v, Some(x) if x <= -0.6)
}

fn main() {
    let seed = std::env::args()
        .nth(1)
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(7);
    let points: &[(u32, u32)] = &[(10, 5), (12, 6), (14, 7), (16, 8)];
    let families = [
        BasisFamily::Random,
        BasisFamily::Coordinate,
        BasisFamily::Subfield,
    ];
    let targets = 16u32;
    let rounds = 6u32;

    println!("════════════════════════════════════════════════════════════════");
    println!("EXP-R4d — does lever L4 act *through* Δ_low?");
    println!("seed={seed}  critical regime 2n'=n  targets/cell={targets}  rounds<={rounds}");
    println!("════════════════════════════════════════════════════════════════");

    let mut cells: BTreeMap<(String, u32), Vec<PresentationRow>> = BTreeMap::new();
    for &family in &families {
        println!("\n── family = {family:?} ──");
        println!(
            "  {:>3} {:>6} {:>10} {:>10} {:>10} {:>8} {:>8} {:>8} {:>7}",
            "N", "rows", "Δ raw", "Δ 1-round", "Δ sat", "D* raw", "D* 1-r", "D* sat", "dD* var"
        );
        for &(n, n_sub) in points {
            let Some(irr) = enumerate_irreducibles(n, 1).into_iter().next() else {
                continue;
            };
            let rows = run_presentation_cell(
                family,
                n,
                n_sub,
                &irr,
                targets,
                7,
                rounds,
                seed ^ ((n as u64) << 8),
            );
            if rows.is_empty() {
                println!("  {:>3} — infeasible at this (n, n')", 2 * n_sub);
                continue;
            }
            let m = |f: &dyn Fn(&PresentationRow) -> f64| -> f64 {
                rows.iter().map(f).sum::<f64>() / rows.len() as f64
            };
            // Does dD* vary at all in this cell? If not, nothing can
            // correlate with it here and the cell is degenerate.
            let dd: Vec<f64> = rows
                .iter()
                .map(|r| r.dstar[2] as f64 - r.dstar[0] as f64)
                .collect();
            let varies = dd.iter().any(|v| (v - dd[0]).abs() > 1e-12);
            println!(
                "  {:>3} {:>6} {:>10.5} {:>10.5} {:>10.5} {:>8.2} {:>8.2} {:>8.2} {:>7}",
                2 * n_sub,
                rows.len(),
                m(&|r| r.defect[0]),
                m(&|r| r.defect[1]),
                m(&|r| r.defect[2]),
                m(&|r| r.dstar[0] as f64),
                m(&|r| r.dstar[1] as f64),
                m(&|r| r.dstar[2] as f64),
                if varies { "yes" } else { "NO" }
            );
            cells.insert((format!("{family:?}"), 2 * n_sub), rows);
        }
    }

    // ── Statistic 1: the paired lever effect ────────────────────────
    println!("\n════════════════════════════════════════════════════════════════");
    println!("Statistic 1 — paired lever effect: does dΔ_low predict dD*?");
    println!("════════════════════════════════════════════════════════════════");
    let mut paired = Vec::new();
    let mut degenerate = Vec::new();
    let mut live = Vec::new();
    for ((fam, n), rows) in &cells {
        let dd: Vec<f64> = rows
            .iter()
            .map(|r| r.dstar[2] as f64 - r.dstar[0] as f64)
            .collect();
        let varies = dd.iter().any(|v| (v - dd[0]).abs() > 1e-12);
        if !varies {
            degenerate.push((fam.clone(), *n, dd[0]));
            continue;
        }
        live.push((fam.clone(), *n));
        for r in rows {
            paired.push(BlockedObs {
                block: format!("{fam} N={n}"),
                x: r.defect[2] - r.defect[0],
                y: r.dstar[2] as f64 - r.dstar[0] as f64,
            });
        }
    }
    println!(
        "\n  cells with a CONSTANT dD* (degenerate, not scored): {} of {}",
        degenerate.len(),
        cells.len()
    );
    for (fam, n, v) in &degenerate {
        println!("     {fam:<12} N={n:<3} every target has dD* = {v:+.0}");
    }
    let c_pair = if paired.is_empty() {
        None
    } else {
        Some(size_control(&paired))
    };
    if let Some(c) = &c_pair {
        report("PAIRED (sat − raw), blocked on (family, N)", c);
        println!(
            "\n   live cells: {}",
            live.iter()
                .map(|(f, n)| format!("{f} N={n}"))
                .collect::<Vec<_>>()
                .join(", ")
        );
    } else {
        println!("\n  → every cell is degenerate: dD* never varies, so statistic 1 is");
        println!("    undefined everywhere. That is an answer about the lever, not a");
        println!("    missing measurement — see the verdict.");
    }

    // ── Statistic 2: the presentation-family level ──────────────────
    println!("\n════════════════════════════════════════════════════════════════");
    println!("Statistic 2 — presentation-family level (EXP-R4b panel B analogue)");
    println!("════════════════════════════════════════════════════════════════");
    let mut fam_obs = Vec::new();
    for ((fam, n), rows) in &cells {
        for i in 0..3 {
            let k = rows.len() as f64;
            fam_obs.push(BlockedObs {
                block: format!("{fam} N={n}"),
                x: rows.iter().map(|r| r.defect[i]).sum::<f64>() / k,
                y: rows.iter().map(|r| r.dstar[i] as f64).sum::<f64>() / k,
            });
        }
    }
    let c_fam = size_control(&fam_obs);
    report("PRESENTATION means (raw / one-round / saturated)", &c_fam);
    // The dose axis ends at a constant, which is itself the finding.
    let total: usize = cells.values().map(|r| r.len()).sum();
    let nonzero: usize = cells
        .values()
        .flatten()
        .filter(|r| r.defect[2] != 0.0)
        .count();
    println!(
        "\n   Targets whose SATURATED presentation still has Δ_low > 0: {nonzero} of {total}."
    );
    println!("   Saturation drives the defect to exactly zero, every time — which it");
    println!("   must: the degree-3 defect IS the space of degree-3 falls, and");
    println!("   saturation adds precisely those as generators. So Δ_low cannot score a");
    println!("   lever's OUTPUT: the lever's action is to consume the quantity.");
    println!(
        "\n   per block ({} presentations each):",
        PRESENTATIONS.len()
    );
    for (k, n, r) in &c_fam.per_block {
        println!("     {k:<18} ({n} points): {}", fmt(*r));
    }

    // ── Statistic 3: why both came out POSITIVE ─────────────────────
    //
    // Statistics 1 and 2 both report the wrong sign, strongly. That is not
    // noise, and the cause is visible in the raw cells: stratify each cell's
    // targets by their D* and look at the mean defect in each stratum.
    println!("\n════════════════════════════════════════════════════════════════");
    println!("Statistic 3 — the sign inversion, and where it comes from");
    println!("════════════════════════════════════════════════════════════════");
    println!("\n  Within each (family, N) cell, mean Δ_low of the targets at each D*:\n");
    println!(
        "  {:>11} {:>4} {:>34} {:>11}",
        "family", "N", "D* → (mean Δ_low, targets)", "within ρ_s"
    );
    let mut inversions = 0usize;
    let mut decidable = 0usize;
    for ((fam, n), rows) in &cells {
        let mut by: BTreeMap<u32, Vec<f64>> = BTreeMap::new();
        for r in rows {
            by.entry(r.dstar[0]).or_default().push(r.defect[0]);
        }
        let desc = by
            .iter()
            .map(|(d, v)| {
                format!(
                    "{d}→({:.5},{})",
                    v.iter().sum::<f64>() / v.len() as f64,
                    v.len()
                )
            })
            .collect::<Vec<_>>()
            .join(" ");
        let xs: Vec<f64> = rows.iter().map(|r| r.defect[0]).collect();
        let ys: Vec<f64> = rows.iter().map(|r| r.dstar[0] as f64).collect();
        let rho = cryptanalysis_suite::cryptanalysis::descent_expansion::spearman(&xs, &ys);
        if let Some(v) = rho {
            decidable += 1;
            if v > 0.0 {
                inversions += 1;
            }
        }
        println!(
            "  {:>11} {:>4} {:>34} {:>11}",
            fam,
            n,
            desc,
            rho.map(|v| format!("{v:+.3}")).unwrap_or("n/a".into())
        );
    }
    println!(
        "\n  Cells where the WITHIN-group relation runs positive: {inversions} of {decidable}"
    );
    println!("  decidable cells — the opposite sign to the between-family law.");
    println!("\n  Mechanism: Δ_low is summed over degrees ≤ 3, so a system can only");
    println!("  show a degree-3 defect if its Macaulay tower actually REACHES degree 3");
    println!("  in a deficient state. A target that refutes at D* = 2 never exercises");
    println!("  degree 3, so its cutoff-3 defect is near zero by construction. Inside a");
    println!("  homogeneous group the statistic is therefore partly a proxy for \"did");
    println!("  this instance need degree 3\" — which IS D*, positively.");
    println!("\n  Between families the structural differences dominate and the sign");
    println!("  flips back to the FFD program's law. Both are real; they are answers");
    println!("  to different questions, and the defect does not carry a single sign.");

    // ── G-R4d verdict ───────────────────────────────────────────────
    println!("\n════════════════════════════════════════════════════════════════");
    println!("G-R4d verdict");
    println!("════════════════════════════════════════════════════════════════");
    let s1 = c_pair
        .as_ref()
        .map(|c| strong(c.blocked_rank))
        .unwrap_or(false);
    let s2 = strong(c_fam.blocked_rank);
    let verdict = match (s1, s2) {
        (true, true) => "SUPPORTED — L4 acts through the defect on both readings",
        (true, false) => "PARTIAL — the paired effect holds, the family level does not",
        (false, true) => "PARTIAL — the family level holds, the paired effect does not",
        (false, false) => "KILLED — neither reading reaches -0.6",
    };
    println!(
        "\n  statistic 1 (paired, blocked rank): {}",
        c_pair
            .as_ref()
            .map(|c| fmt(c.blocked_rank))
            .unwrap_or("undefined".into())
    );
    println!(
        "  statistic 2 (family, blocked rank): {}",
        fmt(c_fam.blocked_rank)
    );
    println!("\n  → G-R4d: {verdict}");
    if !degenerate.is_empty() {
        println!(
            "\n  With {} of {} cells degenerate. Per the gate's degeneracy clause this",
            degenerate.len(),
            cells.len()
        );
        println!("  is reported, not dropped: a pass that depends on which cells were");
        println!("  scorable is not a pass. Where dD* is constant the lever still WORKS —");
        println!("  it drives every target to the same floor — but it cannot be shown to");
        println!("  work *through* a predictor, because there is nothing left to predict.");
    }

    // ── Snapshot ────────────────────────────────────────────────────
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let enc = |c: &SizeControl| {
        let f = |v: Option<f64>| v.map(|x| format!("{x:.6}")).unwrap_or("null".into());
        format!(
            "{{\"n_cells\":{},\"n_blocks\":{},\"pooled\":{},\"mean_per_block\":{},\
             \"blocked_rank\":{},\"fixed_effects\":{}}}",
            c.n_cells,
            c.n_blocks,
            f(c.pooled),
            f(c.mean_per_block),
            f(c.blocked_rank),
            f(c.fixed_effects)
        )
    };
    let body = cells
        .iter()
        .map(|((fam, n), rows)| {
            let k = rows.len() as f64;
            let mean = |f: &dyn Fn(&PresentationRow) -> f64| rows.iter().map(f).sum::<f64>() / k;
            let dd: Vec<f64> = rows
                .iter()
                .map(|r| r.dstar[2] as f64 - r.dstar[0] as f64)
                .collect();
            format!(
                "{{\"family\":\"{fam}\",\"vars\":{n},\"targets\":{},\
                 \"defect_raw\":{:.6},\"defect_one\":{:.6},\"defect_sat\":{:.6},\
                 \"dstar_raw\":{:.4},\"dstar_one\":{:.4},\"dstar_sat\":{:.4},\
                 \"ddstar_varies\":{}}}",
                rows.len(),
                mean(&|r| r.defect[0]),
                mean(&|r| r.defect[1]),
                mean(&|r| r.defect[2]),
                mean(&|r| r.dstar[0] as f64),
                mean(&|r| r.dstar[1] as f64),
                mean(&|r| r.dstar[2] as f64),
                dd.iter().any(|v| (v - dd[0]).abs() > 1e-12)
            )
        })
        .collect::<Vec<_>>()
        .join(",\n    ");
    let json = format!(
        "{{\n  \"schema\": \"degree_reduction_presentation/v1\",\n  \
         \"experiment\": \"EXP-R4d\",\n  \"generated_at\": {ts},\n  \"seed\": {seed},\n  \
         \"targets_per_cell\": {targets},\n  \
         \"degenerate_cells\": {},\n  \"total_cells\": {},\n  \
         \"paired\": {},\n  \"presentation_family\": {},\n  \"cells\": [\n    {body}\n  ]\n}}\n",
        degenerate.len(),
        cells.len(),
        c_pair.as_ref().map(enc).unwrap_or("null".into()),
        enc(&c_fam)
    );
    let out = "experiments/degree_reduction_presentation.json";
    match std::fs::write(out, &json) {
        Ok(_) => println!("\n[snapshot] wrote {out}"),
        Err(e) => println!("\n[snapshot] FAILED to write {out}: {e}"),
    }
    println!("════════════════════════════════════════════════════════════════");
}
