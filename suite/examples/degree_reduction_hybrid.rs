//! EXP-R1 — can we *buy* a lower Gröbner solving degree `D*`, and is the
//! price ever worth paying?
//!
//! The FFD program established (P6) that over-determination collapses `D*`
//! to the Nullstellensatz floor of 2, and recorded that as a nuisance — the
//! reason a single-sample harness saw a spuriously flat `D*`. This
//! experiment turns it around: the determination ratio `ρ = #eqs/#vars` is
//! **not** fixed by the problem. An attacker guesses `k` of the `N = 2n'`
//! descended Boolean variables and solves the `2^k` resulting slices; each
//! slice has `ρ = n/(N−k)`, so `ρ` — and therefore the solving degree — is a
//! dial the attacker turns.
//!
//! The accounting is exact because the targets are **non-decomposable**: the
//! descended system is unsatisfiable, hence so is every slice, hence every
//! slice refutes and the `2^k` slices partition what the direct solve
//! covered. Total work is `2^k · E[cols(N−k, D*)^ω]`.
//!
//! ## The baseline, and why `k = 0` is the wrong one
//!
//! Beating the direct solve (`k = 0`) is not the bar. The `k = N` endpoint
//! of this same family *is* brute-force enumeration of `V × V`, so at toy
//! sizes the cost model will report that guessing more always helps — it is
//! drifting toward exhaustive search, which really is fastest when `2^N` is
//! small. A gate keyed on `k = 0` would measure that artifact and call it a
//! result.
//!
//! So this experiment scores the hybrid against **`2^N` enumeration**,
//! charged generously (`O(1)` amortised per point), and reports the scaling
//! quantity that actually decides the lever: the **collapse fraction**
//! `c = k₂/N`, where `k₂` is the smallest `k` at which every slice has
//! reached `D* = 2`. Total hybrid work is then `2^{cN}·poly`, so the lever
//! is a speedup only if `c < 1`, and survives to cryptographic size only if
//! `c` does not drift upward with `N`.
//!
//! Gate **G-R1** (pre-registered, `research/notes/index-calculus/RESEARCH_DEGREE_REDUCTION.md`):
//! *supported* if the best hybrid beats `2^N` enumeration at every measured
//! `N` **and** the collapse fraction `c` is non-increasing in `N`;
//! *killed* if the margin is negative and worsening, or `c` rises toward 1;
//! *blocked* if the margin is negative but closing with `N` (the crossover
//! is real but past current reach).
//!
//! Run: `cargo run --release --example degree_reduction_hybrid [seed]`
//! Snapshot → `experiments/degree_reduction_hybrid.json`

use cryptanalysis_suite::cryptanalysis::degree_reduction::{
    run_hybrid_sweep, GuessPattern, HybridSweep,
};
use cryptanalysis_suite::cryptanalysis::descent_expansion::enumerate_irreducibles;
use cryptanalysis_suite::cryptanalysis::descent_lowgamma::BasisFamily;
use std::time::{SystemTime, UNIX_EPOCH};

/// Linear-algebra exponents to report. 2.807 is Strassen (a realistic bound
/// for the dense bit-packed elimination this repo actually runs); 2.0 is the
/// optimistic sparse/Wiedemann limit, which is the *hardest* case for the
/// lever because it discounts the degree collapse the most.
const OMEGAS: [f64; 2] = [2.807, 2.0];

fn main() {
    let seed = std::env::args()
        .nth(1)
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(7);

    // Critical operating points `2n' = n` — the ECDLP-relevant regime where
    // the system is just-determined before slicing (`ρ = 1`).
    let points: &[(u32, u32)] = &[(10, 5), (12, 6), (14, 7)];
    let patterns = [
        GuessPattern::Balanced,
        GuessPattern::OneSide,
        GuessPattern::Spread,
    ];

    println!("════════════════════════════════════════════════════════════════");
    println!("EXP-R1 — hybrid slicing: buying D* down with 2^k enumeration");
    println!("seed={seed}   critical regime 2n'=n   family=Coordinate");
    println!("════════════════════════════════════════════════════════════════");

    let mut sweeps: Vec<HybridSweep> = Vec::new();

    for &(n, n_sub) in points {
        let Some(irr) = enumerate_irreducibles(n, 1).into_iter().next() else {
            println!("\n[skip] n={n} — no irreducible found");
            continue;
        };
        let n_full = 2 * n_sub;
        for &pattern in &patterns {
            let Some(sw) = run_hybrid_sweep(
                BasisFamily::Coordinate,
                pattern,
                n,
                n_sub,
                &irr,
                n_full.saturating_sub(2), // scan almost to the enumeration endpoint
                8,                        // non-decomposable targets
                8,                        // slices sampled per (target, k)
                7,                        // d_max
                seed ^ ((n as u64) << 8),
            ) else {
                println!("\n[skip] n={n} n'={n_sub} {} — infeasible", pattern.label());
                continue;
            };

            println!(
                "\n── n={n}  n'={n_sub}  N={n_full}  eqs={n}  pattern={}  targets={} ──",
                pattern.label(),
                sw.targets
            );
            println!(
                "  {:>2} {:>5} {:>6} {:>9} {:>5} {:>9} {:>10} {:>11}",
                "k", "vars", "rho", "mean D*", "max", "Δ_low", "log2 slice", "log2 total"
            );
            for r in &sw.rows {
                println!(
                    "  {:>2} {:>5} {:>6.2} {:>9.2} {:>5} {:>9.5} {:>10.1} {:>11.1}",
                    r.k,
                    r.vars,
                    r.rho,
                    r.dstar_mean,
                    r.dstar_max,
                    r.delta_low_mean,
                    r.log2_slice_cost(OMEGAS[0]),
                    r.log2_total_cost(OMEGAS[0]),
                );
            }
            println!(
                "  brute-force enumeration of V×V: log2 = {:.1}",
                sw.log2_enumeration()
            );
            match sw.collapse_fraction() {
                Some(c) => println!(
                    "  D* collapses to the floor at k₂ = {} → c = k₂/N = {c:.3}",
                    (c * sw.full_vars as f64).round() as u32
                ),
                None => println!("  D* never fully collapses within the scanned k range"),
            }
            for &omega in &OMEGAS {
                let (k_star, saving) = sw.best(omega).unwrap_or((0, f64::NAN));
                let margin = sw.margin_vs_enumeration(omega).unwrap_or(f64::NAN);
                let interior = sw.optimum_is_interior(omega);
                let verdict = if !interior {
                    "BOUNDARY — optimum ran off the scan; this is exhaustive search"
                } else if margin > 0.0 {
                    "interior optimum, BEATS enumeration"
                } else {
                    "interior optimum, loses to enumeration"
                };
                println!(
                    "  ω={omega:<5} k*={k_star:<3} vs direct {saving:+.2}   vs enumeration {margin:+.2}   [{verdict}]"
                );
            }
            let censored: u32 = sw.rows.iter().map(|r| r.censored).sum();
            if censored > 0 {
                println!("  [warn] {censored} slice(s) did not refute by d_max — degrees censored");
            }
            sweeps.push(sw);
        }
    }

    // ── Verdict against G-R1 ────────────────────────────────────────
    println!("\n════════════════════════════════════════════════════════════════");
    println!("G-R1 verdict — hybrid vs brute-force enumeration");
    println!("════════════════════════════════════════════════════════════════");

    // Collapse fraction per pattern, across N — the scaling half of the gate.
    println!("\n  collapse fraction c = k₂/N (D* at the floor on every slice)");
    print!("  {:>10}", "pattern");
    for &(_, n_sub) in points {
        print!("  {:>8}", format!("N={}", 2 * n_sub));
    }
    println!();
    let mut c_trend_ok = true;
    for &pattern in &patterns {
        print!("  {:>10}", pattern.label());
        let mut series: Vec<f64> = Vec::new();
        for &(n, n_sub) in points {
            let c = sweeps
                .iter()
                .find(|s| s.n == n && s.n_sub == n_sub && s.pattern == pattern)
                .and_then(|s| s.collapse_fraction());
            match c {
                Some(v) => {
                    print!("  {v:>8.3}");
                    series.push(v);
                }
                // "—" = the unsliced system was already at the floor,
                // so there is no collapse to measure in this cell.
                None => print!("  {:>8}", "—"),
            }
        }
        // Non-increasing (within a tolerance for sampling noise) is the gate.
        let ok = series.windows(2).all(|w| w[1] <= w[0] + 1e-9);
        if !ok {
            c_trend_ok = false;
        }
        println!("   {}", if ok { "non-increasing" } else { "RISING" });
    }

    for &omega in &OMEGAS {
        let mut per_point: Vec<(u32, u32, f64, f64, &'static str)> = Vec::new();
        for &(n, n_sub) in points {
            let best = sweeps
                .iter()
                .filter(|s| s.n == n && s.n_sub == n_sub)
                .filter_map(|s| {
                    let m = s.margin_vs_enumeration(omega)?;
                    let (k, _) = s.best(omega)?;
                    Some((k, m, s.log2_enumeration(), s.pattern.label()))
                })
                .max_by(|a, b| a.1.partial_cmp(&b.1).unwrap());
            if let Some((k, m, base, lab)) = best {
                per_point.push((2 * n_sub, k, m, base, lab));
            }
        }
        println!("\n  ω = {omega}");
        println!(
            "  {:>4} {:>4} {:>12} {:>13} {:>10}",
            "N", "k*", "log2 2^N", "margin", "pattern"
        );
        for (nn, k, m, base, lab) in &per_point {
            println!("  {nn:>4} {k:>4} {base:>12.1} {m:>+13.2} {lab:>10}");
        }
        let all_beat = per_point.iter().all(|p| p.2 > 0.0);
        let closing = per_point.windows(2).all(|w| w[1].2 >= w[0].2 - 1e-9);
        let any_interior = sweeps.iter().any(|s| s.optimum_is_interior(omega));
        let verdict = if !any_interior {
            "KILLED (degenerate: at every operating point the cost optimum sits at the \n            largest k scanned, i.e. the model is choosing exhaustive search. The \n            degree collapse buys no interior optimum, so the reported margins are \n            artifacts of where the scan was truncated, not a speedup.)"
        } else if all_beat && c_trend_ok {
            "SUPPORTED (interior optimum, beats 2^N everywhere, collapse fraction not rising)"
        } else if all_beat {
            "BLOCKED (beats 2^N at measured N, but the collapse fraction RISES with N — the scaling half of the gate fails)"
        } else if closing {
            "BLOCKED (loses to 2^N, but the margin is closing with N — crossover past current reach)"
        } else {
            "KILLED (loses to 2^N and the gap is not closing)"
        };
        println!("  → G-R1 @ ω={omega}: {verdict}");
        if let (Some(a), Some(b)) = (per_point.first(), per_point.last()) {
            if b.0 > a.0 && any_interior {
                let rate = (b.2 - a.2) / ((b.0 - a.0) as f64);
                println!("    margin trend: {:+.2} bits per unit N", rate);
                if rate > 0.0 && b.2 < 0.0 {
                    println!(
                        "    linear extrapolation → crossover near N ≈ {:.0} (an extrapolation, not a measurement)",
                        b.0 as f64 - b.2 / rate
                    );
                }
            }
        }
    }

    // ── Snapshot ────────────────────────────────────────────────────
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let mut cells = Vec::new();
    for s in &sweeps {
        let rows = s
            .rows
            .iter()
            .map(|r| {
                let hist = r
                    .dstar_hist
                    .iter()
                    .map(|(d, c)| format!("\"{d}\":{c}"))
                    .collect::<Vec<_>>()
                    .join(",");
                format!(
                    "{{\"k\":{},\"vars\":{},\"rho\":{:.4},\"slices\":{},\"censored\":{},\
                     \"dstar_mean\":{:.4},\"dstar_max\":{},\"dstar_hist\":{{{}}},\
                     \"delta_low_mean\":{:.6},\"first_fall_mean\":{:.4},\
                     \"log2_total_cost_w2807\":{:.4},\"log2_total_cost_w2\":{:.4}}}",
                    r.k,
                    r.vars,
                    r.rho,
                    r.slices,
                    r.censored,
                    r.dstar_mean,
                    r.dstar_max,
                    hist,
                    r.delta_low_mean,
                    r.first_fall_mean,
                    r.log2_total_cost(2.807),
                    r.log2_total_cost(2.0),
                )
            })
            .collect::<Vec<_>>()
            .join(",");
        let fmt = |v: Option<f64>| match v {
            Some(x) if x.is_finite() => format!("{x:.4}"),
            _ => "null".to_string(),
        };
        cells.push(format!(
            "{{\"n\":{},\"n_sub\":{},\"full_vars\":{},\"pattern\":\"{}\",\"targets\":{},\
             \"d_max\":{},\"log2_enumeration\":{:.4},\"collapse_fraction\":{},\
             \"margin_vs_enumeration_w2807\":{},\"margin_vs_enumeration_w2\":{},\
             \"best_k_w2807\":{},\"rows\":[{}]}}",
            s.n,
            s.n_sub,
            s.full_vars,
            s.pattern.label(),
            s.targets,
            s.d_max,
            s.log2_enumeration(),
            fmt(s.collapse_fraction()),
            fmt(s.margin_vs_enumeration(2.807)),
            fmt(s.margin_vs_enumeration(2.0)),
            s.best(2.807).map(|b| b.0).unwrap_or(0),
            rows
        ));
    }
    let json = format!(
        "{{\n  \"schema\": \"degree_reduction_hybrid/v2\",\n  \"experiment\": \"EXP-R1\",\n  \
         \"seed\": {seed},\n  \"generated_at\": {ts},\n  \"family\": \"Coordinate\",\n  \
         \"baseline\": \"2^N enumeration of V x V, O(1) amortised per point\",\n  \
         \"cells\": [{}]\n}}\n",
        cells.join(",")
    );
    let path = "experiments/degree_reduction_hybrid.json";
    match std::fs::write(path, &json) {
        Ok(_) => println!("\n[snapshot] wrote {path}"),
        Err(e) => println!("\n[snapshot] FAILED to write {path}: {e}"),
    }
    println!("════════════════════════════════════════════════════════════════");
}
