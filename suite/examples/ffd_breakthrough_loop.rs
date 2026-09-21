//! # FFD breakthrough loop — the executable shell of `research/notes/index-calculus/RESEARCH_FFD_WORKFLOW.md`.
//!
//! One invocation = one snapshot of the falsification-driven loop:
//!
//! 1. Runs the currently-decidable experiments (EXP-A curve-independence,
//!    the operating-point scaling sweep for P1, the regime sweep for P6).
//! 2. Applies the **pre-registered decision gates** (G-P5, G-P1, G-P6) to
//!    the fresh data and prints a verdict per prediction.
//! 3. Writes a reproducible JSON snapshot to `experiments/ffd_loop_<ts>.json`
//!    so the numbers survive the ephemeral container and feed the ledger.
//! 4. Prints the **next experiment** to run (the queue head whose gate is
//!    closest to decidable but still blocked).
//!
//! This does not *replace* judgement — it mechanises steps 0, 3, and the
//! arithmetic of step 4 in the workflow, so a human (or the autolab) starts
//! each iteration from a verdict, not from raw numbers.
//!
//! ```bash
//! cargo run --release --example ffd_breakthrough_loop
//! ```

use cryptanalysis_suite::binary_ecc::F2mElement;
use cryptanalysis_suite::cryptanalysis::descent_algebraic::{early_defect, rank_profile};
use cryptanalysis_suite::cryptanalysis::descent_expansion::{
    enumerate_irreducibles, spearman, system_expansion_report,
};
use cryptanalysis_suite::cryptanalysis::descent_lowgamma::{
    descend_on_subspace, measure_on_subspace, run_lowgamma_cell, BasisFamily, FactorSubspace,
    LowGammaCell,
};
use cryptanalysis_suite::cryptanalysis::pc_degree_avg::{
    mean_dstar_spread, measure_avg, run_pc_curve_independence_sweep, run_pc_operating_point_sweep,
    run_pc_regime_sweep, AvgRow,
};
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use std::time::{SystemTime, UNIX_EPOCH};

/// Pre-registered gate thresholds (mirror research/notes/index-calculus/RESEARCH_FFD_WORKFLOW.md §4).
const G_P5_SPREAD_SUPPORT: f64 = 0.5; // spread below this ⇒ curve-independence supported
const G_P6_OVERDET_RATIO: f64 = 2.0; // ρ ≥ this should collapse D* to ≈ 2
const G_P6_COLLAPSE_MEAN: f64 = 2.05; // mean D* below this counts as "collapsed"
const G_P2_SUPPORT: f64 = 0.6; // Spearman ρ_s ≥ this ⇒ P2 supported
const G_P2_KILL: f64 = 0.2; // |ρ_s| < this ⇒ P2 killed

fn main() {
    let seed = 0x0FFD_1009; // fixed for reproducibility of this snapshot
    let targets = 64;

    println!("════════════════════════════════════════════════════════════════");
    println!(" FFD breakthrough loop — snapshot");
    println!(" (gates: research/notes/index-calculus/RESEARCH_FFD_WORKFLOW.md §4)");
    println!("════════════════════════════════════════════════════════════════");

    // ── EXP-A: curve-independence (P5) ──────────────────────────────
    let n_a = 8;
    let nsub_a = 3;
    let n_curves = 8;
    let exp_a = run_pc_curve_independence_sweep(n_a, nsub_a, n_curves, 12, targets, seed);
    let spread = mean_dstar_spread(&exp_a);
    let p5 = judge_p5(spread);
    println!("\n[EXP-A] curve-independence  n={n_a} n'={nsub_a}  ({n_curves} curves)");
    for (i, r) in exp_a.iter().enumerate() {
        println!(
            "   curve #{i}: mean D*={}  hist {}",
            fmt_mean(r),
            r.refutation.histogram_str()
        );
    }
    println!(
        "   → spread(mean D*) = {}   GATE G-P5: {}",
        spread
            .map(|s| format!("{s:.3}"))
            .unwrap_or_else(|| "—".into()),
        p5
    );

    // ── P1: operating-point scaling, split by parity ────────────────
    let opp = run_pc_operating_point_sweep(6..=12, 1, 16, targets, seed.wrapping_add(1));
    println!("\n[EXP/scale] operating-point (margin=1, ρ≳1), split by parity:");
    print_table(&opp);
    let odd: Vec<&AvgRow> = opp.iter().filter(|r| r.n % 2 == 1).collect();
    let even: Vec<&AvgRow> = opp.iter().filter(|r| r.n % 2 == 0).collect();
    let p1_odd = judge_p1(&odd, "odd");
    let p1_even = judge_p1(&even, "even");
    println!("   GATE G-P1 (odd  parity): {p1_odd}");
    println!("   GATE G-P1 (even parity): {p1_even}");

    // ── P6: over-determination collapse ─────────────────────────────
    let regime = run_pc_regime_sweep(10, 14, targets, seed.wrapping_add(2));
    println!("\n[EXP/regime] determination-ratio at fixed n=10:");
    print_table(&regime);
    let p6 = judge_p6(&regime);
    println!("   GATE G-P6 (over-determination ⇒ D*→2): {p6}");

    // ── EXP-C/G-P2: expansion vs D* across bases (the central test) ──
    let (p2, p2_rho, p2_n, p2_gspread, p2_dspread) =
        run_p2(8, 3, 24, targets, seed.wrapping_add(3));
    println!("\n[EXP-C] G-P2: system-γ vs mean D* across {p2_n} bases (n=8,n'=3)");
    println!(
        "   γ spread={p2_gspread:.3}  D* spread={p2_dspread:.3}  Spearman ρ_s={}",
        p2_rho
            .map(|r| format!("{r:+.3}"))
            .unwrap_or_else(|| "—".into()),
    );
    println!("   GATE G-P2 (γ ↔ D* positive monotone): {p2}");

    // ── EXP-E: structured (subfield) vs random across the full γ range ──
    // The decisive test P2 was missing: a genuine LOW-D* structured case.
    let ee = run_exp_e(8, 4, 32, seed.wrapping_add(4));
    println!("\n[EXP-E] structured vs random factor base (n=8, n'=4, 2n'=n):");
    println!(
        "    {:<11} {:>8} {:>9} {:>10}",
        "family", "γ mean", "D* mean", "decomp"
    );
    for c in &ee {
        println!(
            "    {:<11} {:>8.3} {:>9} {:>9.0}%",
            format!("{:?}", c.family),
            c.gamma_mean,
            c.dstar_mean
                .map(|d| format!("{d:.2}"))
                .unwrap_or_else(|| "—".into()),
            c.decomp_rate * 100.0,
        );
    }
    let p2e = judge_p2_structured(&ee);
    println!("   GATE G-P2 (structured contrast): {p2e}");

    // ── EXP-F: the ALGEBRAIC discriminator (early rank defect vs D*) ────
    // After both graph invariants failed (P2, P2″), test whether a
    // Hilbert-function defect — read from the coefficients — predicts D*.
    let ef = run_exp_f(8, 4, 24, 3, seed.wrapping_add(5));
    println!("\n[EXP-F] algebraic discriminator: early rank defect vs D* (n=8, n'=4):");
    println!(
        "    {:<11} {:>13} {:>9}",
        "family", "early-defect", "D* mean"
    );
    for c in &ef {
        println!(
            "    {:<11} {:>13.4} {:>9}",
            format!("{:?}", c.family),
            c.early_defect,
            c.dstar_mean
                .map(|d| format!("{d:.2}"))
                .unwrap_or_else(|| "—".into()),
        );
    }
    let (p3alg, p3_rho) = judge_p3_algebraic(&ef);
    println!(
        "   GATE G-P3-alg (defect ↑ ⇒ D* ↓, Spearman ρ_s={}): {p3alg}",
        p3_rho
            .map(|r| format!("{r:+.3}"))
            .unwrap_or_else(|| "—".into()),
    );

    // ── Snapshot to experiments/ ────────────────────────────────────
    // Fixed seed ⇒ reproducible run ⇒ a single canonical file (overwritten
    // each run) rather than a timestamped pile. `generated_at` records the
    // wall clock inside the JSON for provenance.
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let path = "experiments/ffd_loop_latest.json".to_string();
    let json = build_json(
        seed, targets, ts, &exp_a, spread, &p5, &opp, &p1_odd, &p1_even, &regime, &p6, &p2, p2_rho,
        p2_gspread, p2_dspread, &ee, &p2e, &ef, &p3alg, p3_rho,
    );
    match std::fs::write(&path, &json) {
        Ok(_) => println!("\n[snapshot] wrote {path}"),
        Err(e) => println!("\n[snapshot] FAILED to write {path}: {e}"),
    }

    // ── Next experiment (queue head still blocked) ──────────────────
    println!(
        "\n[next] {}",
        next_experiment(&p5, &p1_odd, &p1_even, &p2, &p2e, &p3alg)
    );
    println!("════════════════════════════════════════════════════════════════");
}

/// EXP-C: across irreducible bases at fixed `(n, n')`, pair the system-graph
/// spectral expansion `γ` (averaged over a few random targets, since `D*`
/// is curve-independent per P5) with the measured mean `D*` (over a batch
/// of non-decomposable targets), then Spearman-correlate. Returns
/// `(verdict, ρ_s, n_bases, γ_spread, D*_spread)`.
fn run_p2(
    n: u32,
    n_sub: u32,
    max_bases: usize,
    targets: u32,
    seed: u64,
) -> (Verdict, Option<f64>, usize, f64, f64) {
    let bases = enumerate_irreducibles(n, max_bases);
    let mut gx = Vec::new();
    let mut dy = Vec::new();
    let mut rng = StdRng::seed_from_u64(seed);
    for irr in &bases {
        // γ: average system spectral expansion over a few random (b, x₃).
        let mut grng = StdRng::seed_from_u64(seed ^ 0x9E37);
        let mut gs = Vec::new();
        for _ in 0..6 {
            let b = rand_nz(&mut grng, n);
            let x3 = rand_nz(&mut grng, n);
            gs.push(system_expansion_report(n, n_sub, irr, &b, &x3).gamma_spectral);
        }
        let gmean = gs.iter().sum::<f64>() / gs.len() as f64;
        // D*: mean over a batch of non-decomposable targets.
        let b = rand_nz(&mut rng, n);
        let row = measure_avg(n, n_sub, irr, &b, 14, targets.min(48), 4000, &mut rng);
        if let Some(m) = row.refutation.mean {
            gx.push(gmean);
            dy.push(m);
        }
    }
    let rho = spearman(&gx, &dy);
    let gspread = spread(&gx);
    let dspread = spread(&dy);
    let verdict = judge_p2(rho, gspread);
    (verdict, rho, bases.len(), gspread, dspread)
}

/// EXP-E: measure (γ, D*, decomp-rate) for the structured factor-base
/// families {Subfield, Coordinate, Random} at the operating point `2n' = n`.
fn run_exp_e(n: u32, n_sub: u32, trials: u32, seed: u64) -> Vec<LowGammaCell> {
    let irr = enumerate_irreducibles(n, 1)
        .into_iter()
        .next()
        .expect("a degree-n irreducible exists");
    let d_max = 2 * n_sub + 2;
    [
        BasisFamily::Subfield,
        BasisFamily::Coordinate,
        BasisFamily::Random,
    ]
    .into_iter()
    .filter_map(|fam| run_lowgamma_cell(fam, n, n_sub, &irr, d_max, trials, seed))
    .collect()
}

/// One EXP-F cell: a factor-base family's mean early rank defect and mean D*.
struct AlgCell {
    family: BasisFamily,
    early_defect: f64,
    dstar_mean: Option<f64>,
}

/// EXP-F: the algebraic discriminator. For each family, average the early
/// rank defect (`Σ_{D≤cutoff} δ(D) / cols`) and the refutation degree D*
/// over `trials` random `(b, x₃)`. The hypothesis P3-alg: defect ↑ ⇒ D* ↓
/// (the structure that lowers D* is excess low-degree syzygies, visible in
/// the coefficient algebra where graph invariants were blind).
fn run_exp_f(n: u32, n_sub: u32, trials: u32, cutoff: u32, seed: u64) -> Vec<AlgCell> {
    let irr = enumerate_irreducibles(n, 1)
        .into_iter()
        .next()
        .expect("a degree-n irreducible exists");
    let d_max = 2 * n_sub;
    let mut rng = StdRng::seed_from_u64(seed);
    let mut out = Vec::new();
    for fam in [
        BasisFamily::Subfield,
        BasisFamily::Coordinate,
        BasisFamily::Random,
    ] {
        let mut de = Vec::new();
        let mut ds = Vec::new();
        for t in 0..trials as u64 {
            let v = match fam {
                BasisFamily::Random => {
                    FactorSubspace::build(fam, n, n_sub, &irr, seed ^ (0x900 + t))
                }
                _ => FactorSubspace::build(fam, n, n_sub, &irr, 0),
            };
            let Some(v) = v else { continue };
            let b = rand_nz(&mut rng, n);
            let x3 = rand_nz(&mut rng, n);
            let eqs = descend_on_subspace(n, &v, &irr, &b, &x3);
            let prof = rank_profile(&eqs, 2 * n_sub, n, d_max);
            de.push(early_defect(&prof, cutoff));
            let pt = measure_on_subspace(n, &v, &irr, &b, &x3, 2 * n_sub + 2);
            if let Some(d) = pt.refutation_degree {
                ds.push(d as f64);
            }
        }
        if de.is_empty() {
            continue;
        }
        out.push(AlgCell {
            family: fam,
            early_defect: de.iter().sum::<f64>() / de.len() as f64,
            dstar_mean: if ds.is_empty() {
                None
            } else {
                Some(ds.iter().sum::<f64>() / ds.len() as f64)
            },
        });
    }
    out
}

/// G-P3-alg: does the early rank defect predict D* across families? The
/// theory-predicted relation is **negative** (more defect ⇒ lower D*).
/// *Supported* if Spearman ρ_s ≤ −0.6 across the cells (and the easy
/// subfield indeed has the largest defect); *killed* if |ρ_s| < 0.2;
/// else *inconclusive*.
fn judge_p3_algebraic(cells: &[AlgCell]) -> (Verdict, Option<f64>) {
    let xs: Vec<f64> = cells.iter().map(|c| c.early_defect).collect();
    let ys: Vec<f64> = cells.iter().filter_map(|c| c.dstar_mean).collect();
    if xs.len() < 3 || ys.len() != xs.len() {
        return (
            Verdict {
                status: "blocked",
                detail: format!("only {} complete cells (need ≥3)", ys.len().min(xs.len())),
            },
            None,
        );
    }
    let rho = spearman(&xs, &ys);
    let v = match rho {
        None => Verdict {
            status: "blocked",
            detail: "degenerate (zero variance) defect or D*".into(),
        },
        Some(r) if r <= -0.6 => Verdict {
            status: "supported",
            detail: format!(
                "ρ_s {r:+.3} ≤ −0.6: higher early rank defect ⇒ lower D* — the ALGEBRAIC predictor works where graph invariants failed"
            ),
        },
        Some(r) if r.abs() < 0.2 => Verdict {
            status: "killed",
            detail: format!("ρ_s {r:+.3}: early defect does not track D* either"),
        },
        Some(r) => Verdict {
            status: "inconclusive",
            detail: format!("ρ_s {r:+.3} in (−0.6, −0.2]∪[0.2, 1): suggestive, widen the sweep"),
        },
    };
    (v, rho)
}

/// G-P2 via the structured contrast: the bridge predicts the *easier*
/// (lower-D*) factor base should be the *lower*-γ one. If the structured
/// subfield has the lowest D* but **not** the lowest γ, that contradicts
/// "D* increases with γ" — a breakthrough-NEGATIVE signal.
fn judge_p2_structured(cells: &[LowGammaCell]) -> Verdict {
    let find = |f: BasisFamily| cells.iter().find(|c| c.family == f);
    let (sub, rnd) = match (find(BasisFamily::Subfield), find(BasisFamily::Random)) {
        (Some(s), Some(r)) => (s, r),
        _ => {
            return Verdict {
                status: "blocked",
                detail: "subfield infeasible at this (n,n') — need n' | n".into(),
            };
        }
    };
    let (sd, rd) = match (sub.dstar_mean, rnd.dstar_mean) {
        (Some(a), Some(b)) => (a, b),
        _ => {
            return Verdict {
                status: "blocked",
                detail: "a family produced no non-decomposable D* sample".into(),
            };
        }
    };
    let structured_easier = sd + 0.05 < rd;
    let structured_lower_gamma = sub.gamma_mean + 1e-3 < rnd.gamma_mean;
    if structured_easier && !structured_lower_gamma {
        Verdict {
            status: "killed",
            detail: format!(
                "subfield D* {sd:.2}<{rd:.2} (easier) yet γ {:.3}≥{:.3} (not lower): γ does NOT explain ease → bridge contradicted",
                sub.gamma_mean, rnd.gamma_mean
            ),
        }
    } else if structured_easier && structured_lower_gamma {
        Verdict {
            status: "supported",
            detail: format!(
                "subfield both easier (D* {sd:.2}<{rd:.2}) and lower-γ ({:.3}<{:.3}) — γ tracks ease",
                sub.gamma_mean, rnd.gamma_mean
            ),
        }
    } else {
        Verdict {
            status: "inconclusive",
            detail: format!("subfield not clearly easier (D* {sd:.2} vs {rd:.2})"),
        }
    }
}

fn spread(v: &[f64]) -> f64 {
    if v.is_empty() {
        return 0.0;
    }
    let lo = v.iter().cloned().fold(f64::INFINITY, f64::min);
    let hi = v.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    hi - lo
}

fn rand_nz(rng: &mut StdRng, n: u32) -> F2mElement {
    loop {
        let bits: Vec<u32> = (0..n).filter(|_| rng.gen::<bool>()).collect();
        let e = F2mElement::from_bit_positions(&bits, n);
        if !e.is_zero() {
            return e;
        }
    }
}

// ── Gate judgements ─────────────────────────────────────────────────

#[derive(Clone)]
struct Verdict {
    status: &'static str, // supported | killed | blocked | inconclusive
    detail: String,
}
impl std::fmt::Display for Verdict {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{} ({})", self.status.to_uppercase(), self.detail)
    }
}

/// G-P5: small mean-D* spread across curves ⇒ curve-independence supported.
fn judge_p5(spread: Option<f64>) -> Verdict {
    match spread {
        None => Verdict {
            status: "blocked",
            detail: "fewer than 2 defined means".into(),
        },
        Some(s) if s < G_P5_SPREAD_SUPPORT => Verdict {
            status: "supported",
            detail: format!("spread {s:.3} < {G_P5_SPREAD_SUPPORT}"),
        },
        Some(s) => Verdict {
            status: "killed",
            detail: format!("spread {s:.3} ≥ {G_P5_SPREAD_SUPPORT}: D* depends on curve"),
        },
    }
}

/// G-P1: positive slope of mean D* vs n (within a parity class), ≥ 3 points.
fn judge_p1(rows: &[&AvgRow], label: &str) -> Verdict {
    let pts: Vec<(f64, f64)> = rows
        .iter()
        .filter_map(|r| r.refutation.mean.map(|m| (r.n as f64, m)))
        .collect();
    if pts.len() < 3 {
        return Verdict {
            status: "blocked",
            detail: format!("{label}: only {} points (need ≥3)", pts.len()),
        };
    }
    let slope = ols_slope(&pts);
    if slope > 0.02 {
        Verdict {
            status: "supported",
            detail: format!("{label}: slope {slope:+.3}/n over {} pts", pts.len()),
        }
    } else if slope.abs() <= 0.02 {
        Verdict {
            status: "inconclusive",
            detail: format!("{label}: flat slope {slope:+.3} (reach-limited)"),
        }
    } else {
        Verdict {
            status: "killed",
            detail: format!("{label}: negative slope {slope:+.3}"),
        }
    }
}

/// G-P2: Spearman ρ_s between system-γ and mean D* across bases.
/// *Supported* if ρ_s ≥ 0.6; *killed* if |ρ_s| < 0.2 (no relation);
/// *inconclusive* otherwise (reformulate γ). *blocked* if γ does not vary
/// enough across the available bases (nothing to correlate with).
fn judge_p2(rho: Option<f64>, gamma_spread: f64) -> Verdict {
    if gamma_spread < 1e-3 {
        return Verdict {
            status: "blocked",
            detail: format!("γ spread {gamma_spread:.4} too small across bases"),
        };
    }
    match rho {
        None => Verdict {
            status: "blocked",
            detail: "too few (γ, D*) pairs".into(),
        },
        Some(r) if r >= G_P2_SUPPORT => Verdict {
            status: "supported",
            detail: format!("ρ_s {r:+.3} ≥ {G_P2_SUPPORT}"),
        },
        Some(r) if r.abs() < G_P2_KILL => Verdict {
            status: "killed",
            detail: format!(
                "ρ_s {r:+.3}, |ρ_s| < {G_P2_KILL}: no γ↔D* relation among generic bases"
            ),
        },
        Some(r) => Verdict {
            status: "inconclusive",
            detail: format!("ρ_s {r:+.3} in ({G_P2_KILL},{G_P2_SUPPORT}): reformulate γ"),
        },
    }
}

/// G-P6: rows with ρ ≥ 2 should have mean D* ≈ 2.
fn judge_p6(rows: &[AvgRow]) -> Verdict {
    let overdet: Vec<&AvgRow> = rows
        .iter()
        .filter(|r| r.ratio() >= G_P6_OVERDET_RATIO)
        .collect();
    if overdet.is_empty() {
        return Verdict {
            status: "blocked",
            detail: "no ρ ≥ 2 cells in sweep".into(),
        };
    }
    let all_collapsed = overdet
        .iter()
        .all(|r| r.refutation.mean.is_some_and(|m| m <= G_P6_COLLAPSE_MEAN));
    if all_collapsed {
        Verdict {
            status: "supported",
            detail: format!(
                "all {} over-determined cells have mean D* ≤ {G_P6_COLLAPSE_MEAN}",
                overdet.len()
            ),
        }
    } else {
        Verdict {
            status: "killed",
            detail: "an over-determined cell did NOT collapse to D*≈2".into(),
        }
    }
}

/// Ordinary-least-squares slope of y on x.
fn ols_slope(pts: &[(f64, f64)]) -> f64 {
    let n = pts.len() as f64;
    let sx: f64 = pts.iter().map(|p| p.0).sum();
    let sy: f64 = pts.iter().map(|p| p.1).sum();
    let sxx: f64 = pts.iter().map(|p| p.0 * p.0).sum();
    let sxy: f64 = pts.iter().map(|p| p.0 * p.1).sum();
    let denom = n * sxx - sx * sx;
    if denom.abs() < 1e-12 {
        0.0
    } else {
        (n * sxy - sx * sy) / denom
    }
}

/// Pick the next experiment to run: the highest-priority gate that is not
/// yet supported (mirrors the §5 queue, re-prioritised from verdicts).
fn next_experiment(
    p5: &Verdict,
    p1_odd: &Verdict,
    p1_even: &Verdict,
    p2: &Verdict,
    p2e: &Verdict,
    p3alg: &Verdict,
) -> String {
    if p5.status == "blocked" {
        return "EXP-A: widen curve-independence batch (need ≥2 defined means)".into();
    }
    // The live thread: the ALGEBRAIC discriminator (EXP-F). After both graph
    // invariants (P2 spectral, P2″ treewidth) failed, this is the predictor
    // that might actually work — so its verdict drives the queue.
    match p3alg.status {
        "supported" => {
            return "EXP-G: the early rank-defect (Hilbert-function) predictor TRACKS D* where graph invariants failed. Next: (a) confirm the defect↔D* law across more (n,n') and at larger reach (sparse-F4, EXP-D); (b) formalise it — is δ(D) the right algebraic proxy for the last-fall degree? — and draft the screening invariant + a corrected §3 of the proposal (replace expansion with Hilbert-defect).".into();
        }
        "inconclusive" => {
            return "EXP-F: widen the algebraic-discriminator sweep (more targets, more (n,n') with n'|n, and vary cutoff) to sharpen the defect↔D* Spearman past the −0.6 bar.".into();
        }
        "killed" => {
            return "STOP → breakthrough-NEGATIVE (strong form). Neither graph invariants NOR the Hilbert-function defect predict D*. Write up: 'the solving degree of Weil-descended Semaev systems is not predicted by incidence-graph OR low-degree Hilbert-defect invariants; the subfield speedup resists local prediction.'".into();
        }
        _ => {}
    }
    if p3alg.status == "blocked" && p2e.status == "killed" {
        return "EXP-F: build out the algebraic discriminator (graph invariants P2/P2″ are dead); need ≥3 complete (defect, D*) cells.".into();
    }
    if p1_odd.status == "blocked" || p1_even.status == "blocked" {
        return "EXP-D: build sparse-F4 backend to reach 2n'≳14 (G-P1 reach-limited)".into();
    }
    let _ = (p1_even, p2);
    "Re-run the loop; no blocked gate has a cheaper experiment than the current queue head.".into()
}

// ── Output helpers ──────────────────────────────────────────────────

fn fmt_mean(r: &AvgRow) -> String {
    r.refutation
        .mean
        .map(|m| format!("{m:.3}"))
        .unwrap_or_else(|| "—".into())
}

fn print_table(rows: &[AvgRow]) {
    println!(
        "    {:>3} {:>3} {:>5} {:>5} {:>9} {:>12}",
        "n", "n'", "ρ", "N", "mean D*", "hist"
    );
    for r in rows {
        println!(
            "    {:>3} {:>3} {:>5.2} {:>5} {:>9} {:>12}",
            r.n,
            r.n_sub,
            r.ratio(),
            r.n_targets,
            fmt_mean(r),
            r.refutation.histogram_str()
        );
    }
}

/// Hand-rolled JSON (avoids requiring serde derives on the harness types;
/// the snapshot is flat and stable).
#[allow(clippy::too_many_arguments)]
fn build_json(
    seed: u64,
    targets: u32,
    generated_at: u64,
    exp_a: &[AvgRow],
    spread: Option<f64>,
    p5: &Verdict,
    opp: &[AvgRow],
    p1_odd: &Verdict,
    p1_even: &Verdict,
    regime: &[AvgRow],
    p6: &Verdict,
    p2: &Verdict,
    p2_rho: Option<f64>,
    p2_gspread: f64,
    p2_dspread: f64,
    ee: &[LowGammaCell],
    p2e: &Verdict,
    ef: &[AlgCell],
    p3alg: &Verdict,
    p3_rho: Option<f64>,
) -> String {
    let row_json = |r: &AvgRow| {
        format!(
            "{{\"n\":{},\"n_sub\":{},\"vars\":{},\"eqs\":{},\"ratio\":{:.4},\"n_targets\":{},\"mean_dstar\":{},\"min_dstar\":{},\"max_dstar\":{},\"none\":{},\"hist\":\"{}\"}}",
            r.n,
            r.n_sub,
            r.num_vars,
            r.num_eqs,
            r.ratio(),
            r.n_targets,
            r.refutation.mean.map(|m| format!("{m:.4}")).unwrap_or_else(|| "null".into()),
            r.refutation.min.map(|v| v.to_string()).unwrap_or_else(|| "null".into()),
            r.refutation.max.map(|v| v.to_string()).unwrap_or_else(|| "null".into()),
            r.refutation.n_none,
            r.refutation.histogram_str(),
        )
    };
    let arr = |rows: &[AvgRow]| rows.iter().map(row_json).collect::<Vec<_>>().join(",");
    let verdict = |v: &Verdict| {
        format!(
            "{{\"status\":\"{}\",\"detail\":\"{}\"}}",
            v.status,
            v.detail.replace('"', "'")
        )
    };
    let cell_json = |c: &LowGammaCell| {
        format!(
            "{{\"family\":\"{:?}\",\"n\":{},\"n_sub\":{},\"trials\":{},\"decomp_rate\":{:.4},\"gamma_mean\":{:.4},\"dstar_mean\":{},\"nondecomp\":{}}}",
            c.family,
            c.n,
            c.n_sub,
            c.trials,
            c.decomp_rate,
            c.gamma_mean,
            c.dstar_mean.map(|d| format!("{d:.4}")).unwrap_or_else(|| "null".into()),
            c.nondecomp,
        )
    };
    let ee_arr = ee.iter().map(cell_json).collect::<Vec<_>>().join(",");
    let alg_json = |c: &AlgCell| {
        format!(
            "{{\"family\":\"{:?}\",\"early_defect\":{:.5},\"dstar_mean\":{}}}",
            c.family,
            c.early_defect,
            c.dstar_mean
                .map(|d| format!("{d:.4}"))
                .unwrap_or_else(|| "null".into()),
        )
    };
    let ef_arr = ef.iter().map(alg_json).collect::<Vec<_>>().join(",");
    format!(
        "{{\n  \"schema\": \"ffd_breakthrough_loop/v4\",\n  \"seed\": {seed},\n  \"generated_at\": {generated_at},\n  \"targets_per_cell\": {targets},\n  \"exp_a_curve_independence\": {{\n    \"spread_mean_dstar\": {},\n    \"gate_p5\": {},\n    \"rows\": [{}]\n  }},\n  \"scaling_operating_point\": {{\n    \"gate_p1_odd\": {},\n    \"gate_p1_even\": {},\n    \"rows\": [{}]\n  }},\n  \"regime_n10\": {{\n    \"gate_p6\": {},\n    \"rows\": [{}]\n  }},\n  \"exp_c_expansion_vs_dstar\": {{\n    \"gate_p2\": {},\n    \"spearman_rho\": {},\n    \"gamma_spread\": {:.4},\n    \"dstar_spread\": {:.4}\n  }},\n  \"exp_e_structured_contrast\": {{\n    \"gate_p2_structured\": {},\n    \"cells\": [{}]\n  }},\n  \"exp_f_algebraic_discriminator\": {{\n    \"gate_p3_algebraic\": {},\n    \"spearman_rho\": {},\n    \"cells\": [{}]\n  }}\n}}\n",
        spread.map(|s| format!("{s:.4}")).unwrap_or_else(|| "null".into()),
        verdict(p5),
        arr(exp_a),
        verdict(p1_odd),
        verdict(p1_even),
        arr(opp),
        verdict(p6),
        arr(regime),
        verdict(p2),
        p2_rho.map(|r| format!("{r:.4}")).unwrap_or_else(|| "null".into()),
        p2_gspread,
        p2_dspread,
        verdict(p2e),
        ee_arr,
        verdict(p3alg),
        p3_rho.map(|r| format!("{r:.4}")).unwrap_or_else(|| "null".into()),
        ef_arr,
    )
}
