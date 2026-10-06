//! EXP-R3 — lever L4: do *precomputed degree falls* lower the solving degree?
//!
//! ## The correction this experiment rests on
//!
//! `research/notes/index-calculus/RESEARCH_DEGREE_REDUCTION.md` iteration 1 framed L4 as "add the relation
//! EXP-J identified." That was wrong, and the error is instructive. EXP-J's
//! relation is `Σ_i ℓ_i · f_i ≡ 0` — a **pure syzygy**. It vanishes
//! identically, so it contributes no polynomial; adding it to the generating
//! set adds nothing at all. Pure syzygies cost the solver zero reductions (a
//! constant factor, which is what F5's criterion removes), not degrees.
//!
//! The object that *does* buy a degree is a **degree fall**: a combination of
//! degree-`D` rows whose degree-`D` part cancels leaving a **nonzero**
//! remainder of degree `≤ D−1`. Its value is not that the solver cannot find
//! it — at degree `D` it is already in the row space — but that once the
//! remainder `g` is a *generator*, the rows `x_k · g` become available at
//! degree `D`, and those are degree-`D+1` products of the original
//! generators. The Macaulay tower genuinely accelerates. This is the mutant
//! mechanism of MutantXL and the degree-fall strategy used against HFE.
//!
//! So this experiment separates the two populations, keeps only the falls
//! that are independent of the generators already present, and iterates to
//! saturation.
//!
//! ## The cost model, and why it differs from EXP-R1
//!
//! L4 pays for a lower degree with a *wider* matrix — more generators means
//! more Macaulay rows. A `cols^ω` model is blind to that and would score the
//! trade as free. This experiment therefore uses
//! `rows(D) · cols(D)^{ω−1}` with `rows(D) = eqs · cols(D−2)`, so the extra
//! generators are charged for — **and it charges for the extraction itself**.
//! That second part is not a detail. Every saturation round builds the
//! degree-3 rows of the system as it stands and takes a kernel, so the
//! augmented route still has to climb to degree 3 even when the augmented
//! *solve* then finishes at degree 2. Scoring only the cheap final solve
//! would book the same degree twice and roughly double the apparent saving.
//! The honest comparison is therefore
//! `D*_base` against the **working degree** `max(3, D*_aug)`, and
//! `cost_base` against `cost_extraction + cost_augmented_solve`.
//!
//! Gate **G-R3** (pre-registered): *supported* if augmenting strictly lowers
//! mean `D*` at matched targets over ≥ 3 operating points; *killed* if `D*`
//! is unchanged — which would mean the solver was finding these relations for
//! free and L4 is empty. Invariant checked throughout: `D*` must never *rise*
//! (adding ideal elements cannot make a system harder); any `worsened > 0`
//! means the extraction is unsound.
//!
//! Run: `cargo run --release --example degree_reduction_mutants [seed]`
//! Snapshot → `experiments/degree_reduction_mutants.json`

use cryptanalysis_suite::cryptanalysis::degree_reduction::{
    log2_expected_cost, run_mutant_cell, MutantRow,
};
use cryptanalysis_suite::cryptanalysis::descent_expansion::enumerate_irreducibles;
use cryptanalysis_suite::cryptanalysis::descent_lowgamma::BasisFamily;
use std::time::{SystemTime, UNIX_EPOCH};

const OMEGA: f64 = 2.807;

fn main() {
    let seed = std::env::args()
        .nth(1)
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(7);

    let points: &[(u32, u32)] = &[(10, 5), (12, 6), (14, 7)];
    let families = [
        BasisFamily::Random,
        BasisFamily::Coordinate,
        BasisFamily::Subfield,
    ];
    let rounds = 6u32;
    let targets = 8u32;

    println!("════════════════════════════════════════════════════════════════");
    println!("EXP-R3 — lever L4: degree falls (mutants) vs the raw system");
    println!(
        "seed={seed}  critical regime 2n'=n  targets/cell={targets}  saturation rounds≤{rounds}"
    );
    println!("════════════════════════════════════════════════════════════════");

    let mut rows: Vec<(BasisFamily, MutantRow)> = Vec::new();

    for &family in &families {
        println!("\n── family = {family:?} ──");
        println!(
            "  {:>3} {:>4} {:>7} {:>6} {:>6} {:>6} {:>8} {:>8} {:>7} {:>8} {:>7}",
            "N",
            "eqs",
            "cancel",
            "pure",
            "falls",
            "new",
            "sat.eqs",
            "D* base",
            "D* aug",
            "working",
            "improv"
        );
        for &(n, n_sub) in points {
            let Some(irr) = enumerate_irreducibles(n, 1).into_iter().next() else {
                continue;
            };
            let Some(r) = run_mutant_cell(
                family,
                n,
                n_sub,
                &irr,
                targets,
                7,
                rounds,
                seed ^ ((n as u64) << 8),
            ) else {
                println!("  {:>3} — infeasible at this (n, n')", 2 * n_sub);
                continue;
            };
            println!(
                "  {:>3} {:>4} {:>7.1} {:>6.1} {:>6.1} {:>6.1} {:>8.1} {:>8.2} {:>7.2} {:>8.2} {:>4}/{:<2}",
                r.full_vars,
                r.n,
                r.cancel_dim_mean,
                r.pure_syzygies_mean,
                r.falls_mean,
                r.new_generators_mean,
                r.aug_eqs_mean,
                r.dstar_base_mean,
                r.dstar_aug_mean,
                r.working_degree_mean,
                r.improved,
                r.targets
            );
            if r.worsened > 0 {
                println!(
                    "  [UNSOUND] {} target(s) got WORSE — adding ideal elements cannot do that",
                    r.worsened
                );
            }
            rows.push((family, r));
        }
    }

    // ── Cost accounting: does the degree saving survive the wider matrix? ──
    println!("\n════════════════════════════════════════════════════════════════");
    println!("Cost accounting (rows·cols^(ω−1), ω={OMEGA}) — extra generators charged for");
    println!("════════════════════════════════════════════════════════════════");
    println!(
        "\n  {:>12} {:>4} {:>10} {:>10} {:>10} {:>10} {:>9}",
        "family", "N", "log2 base", "extract", "aug solve", "log2 tot", "saving"
    );
    let mut savings: Vec<(BasisFamily, u32, f64)> = Vec::new();
    for (fam, r) in &rows {
        let base = log2_expected_cost(&r.dstar_base_hist, r.full_vars, r.n, OMEGA);
        let solve = log2_expected_cost(
            &r.dstar_aug_hist,
            r.full_vars,
            r.aug_eqs_mean.round() as u32,
            OMEGA,
        );
        // Total for the augmented route = extraction + final solve, summed in
        // linear space.
        let total = (r.log2_extraction_cost.exp2() + solve.exp2()).log2();
        println!(
            "  {:>12} {:>4} {:>10.2} {:>10.2} {:>10.2} {:>10.2} {:>+9.2}",
            format!("{fam:?}"),
            r.full_vars,
            base,
            r.log2_extraction_cost,
            solve,
            total,
            base - total
        );
        savings.push((*fam, r.full_vars, base - total));
    }
    println!("\n  'extract' is the saturation rounds' degree-3 work; 'aug solve' the");
    println!("  final augmented Macaulay. The saving is against their SUM, not the");
    println!("  solve alone — the augmented route still climbs to degree 3.");

    // ── Verdict ─────────────────────────────────────────────────────
    //
    // G-R3 was pre-registered as a statement about *degrees*, so it is scored
    // on degrees — moving a gate after seeing the data is exactly what the
    // pre-registration is there to prevent. The cost question the degree gate
    // turns out not to cover is registered separately as R3', and scored here
    // for the first time.
    println!("\n════════════════════════════════════════════════════════════════");
    println!("G-R3 verdict (pre-registered: does augmenting lower D*?)");
    println!("════════════════════════════════════════════════════════════════");
    let unsound: u32 = rows.iter().map(|(_, r)| r.worsened).sum();
    if unsound > 0 {
        println!("\n  → G-R3: INVALID — {unsound} target(s) got worse under augmentation.");
        println!("    Adding ideal elements cannot raise D*, so the extraction is unsound.");
        println!("    Fix the extractor before reading anything else in this run.");
        return;
    }
    for &family in &families {
        let cells: Vec<&MutantRow> = rows
            .iter()
            .filter(|(f, _)| *f == family)
            .map(|(_, r)| r)
            .collect();
        if cells.is_empty() {
            continue;
        }
        let drops: Vec<f64> = cells
            .iter()
            .map(|r| r.dstar_base_mean - r.dstar_aug_mean)
            .collect();
        let mean_drop = drops.iter().sum::<f64>() / drops.len() as f64;
        let any_headroom = cells.iter().any(|r| r.dstar_base_mean > 2.0 + 1e-9);
        let all_drop = cells
            .iter()
            .zip(&drops)
            .all(|(r, d)| *d > 1e-9 || r.dstar_base_mean <= 2.0 + 1e-9);
        let verdict = if !any_headroom {
            "N/A (already at the D*=2 floor)"
        } else if all_drop && cells.len() >= 3 {
            "SUPPORTED (D* strictly lower wherever there was headroom)"
        } else if mean_drop > 0.0 {
            "BLOCKED (lowers D* on some cells with headroom but not all)"
        } else {
            "KILLED (D* unchanged — the solver was finding these for free)"
        };
        println!(
            "\n  {family:?}: mean D* drop {mean_drop:+.2} over {} cells → {verdict}",
            cells.len()
        );
    }
    println!("\n  Invariant held: no target got worse in any cell — adding ideal");
    println!("  elements never raises D*, as required.");

    println!("\n════════════════════════════════════════════════════════════════");
    println!("G-R3' verdict (NEW: does the degree saving survive its own cost?)");
    println!("════════════════════════════════════════════════════════════════");
    println!("\n  The degree gate above is necessary but not sufficient. Extraction");
    println!("  has to climb to degree 3, so a system that already solved at");
    println!("  degree ~2 pays for a degree it did not need. Net saving decides.");
    for &family in &families {
        let fam_savings: Vec<(u32, f64)> = savings
            .iter()
            .filter(|(f, _, _)| *f == family)
            .map(|(_, n, s)| (*n, *s))
            .collect();
        if fam_savings.is_empty() {
            continue;
        }
        let all_pos = fam_savings.iter().all(|(_, s)| *s > 0.0);
        let all_neg = fam_savings.iter().all(|(_, s)| *s < 0.0);
        let mean = fam_savings.iter().map(|(_, s)| *s).sum::<f64>() / fam_savings.len() as f64;
        let base_mean = rows
            .iter()
            .filter(|(f, _)| *f == family)
            .map(|(_, r)| r.dstar_base_mean)
            .sum::<f64>()
            / fam_savings.len() as f64;
        let verdict = if all_pos {
            "SUPPORTED (net positive at every N)"
        } else if all_neg {
            "KILLED for this family (extraction costs more than it saves)"
        } else {
            "BLOCKED (sign varies with N)"
        };
        println!(
            "\n  {family:?}: base D* {base_mean:.2}, net saving {mean:+.2} bits mean, \
             per-N {:?}\n    → {verdict}",
            fam_savings
                .iter()
                .map(|(n, s)| format!("N={n}:{s:+.2}"))
                .collect::<Vec<_>>()
        );
    }

    // ── Snapshot ────────────────────────────────────────────────────
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let hist = |h: &std::collections::BTreeMap<u32, u32>| {
        h.iter()
            .map(|(d, c)| format!("\"{d}\":{c}"))
            .collect::<Vec<_>>()
            .join(",")
    };
    let cells = rows
        .iter()
        .map(|(fam, r)| {
            let base = log2_expected_cost(&r.dstar_base_hist, r.full_vars, r.n, OMEGA);
            let solve = log2_expected_cost(
                &r.dstar_aug_hist,
                r.full_vars,
                r.aug_eqs_mean.round() as u32,
                OMEGA,
            );
            // The augmented route's cost is extraction + solve. Storing the
            // solve alone would put a saving in the snapshot that the console
            // verdict does not agree with.
            let total = (r.log2_extraction_cost.exp2() + solve.exp2()).log2();
            format!(
                "{{\"family\":\"{fam:?}\",\"n\":{},\"n_sub\":{},\"full_vars\":{},\"targets\":{},\
                 \"cancel_dim_mean\":{:.3},\"pure_syzygies_mean\":{:.3},\"falls_mean\":{:.3},\
                 \"new_generators_mean\":{:.3},\"productive_rounds_mean\":{:.3},\
                 \"total_added_mean\":{:.3},\"aug_eqs_mean\":{:.3},\
                 \"dstar_base_mean\":{:.4},\"dstar_aug_mean\":{:.4},\
                 \"dstar_base_hist\":{{{}}},\"dstar_aug_hist\":{{{}}},\
                 \"improved\":{},\"worsened\":{},\"working_degree_mean\":{:.4},\
                 \"log2_cost_base\":{:.4},\"log2_cost_extraction\":{:.4},\
                 \"log2_cost_aug_solve\":{:.4},\"log2_cost_aug_total\":{:.4},\
                 \"net_log2_saving\":{:.4}}}",
                r.n,
                r.n_sub,
                r.full_vars,
                r.targets,
                r.cancel_dim_mean,
                r.pure_syzygies_mean,
                r.falls_mean,
                r.new_generators_mean,
                r.productive_rounds_mean,
                r.total_added_mean,
                r.aug_eqs_mean,
                r.dstar_base_mean,
                r.dstar_aug_mean,
                hist(&r.dstar_base_hist),
                hist(&r.dstar_aug_hist),
                r.improved,
                r.worsened,
                r.working_degree_mean,
                base,
                r.log2_extraction_cost,
                solve,
                total,
                base - total,
            )
        })
        .collect::<Vec<_>>()
        .join(",");
    let json = format!(
        "{{\n  \"schema\": \"degree_reduction_mutants/v1\",\n  \"experiment\": \"EXP-R3\",\n  \
         \"seed\": {seed},\n  \"generated_at\": {ts},\n  \"omega\": {OMEGA},\n  \
         \"saturation_rounds\": {rounds},\n  \
         \"cost_model\": \"rows(D)*cols(D)^(omega-1), rows(D)=eqs*cols(D-2); the augmented \
route is charged extraction + solve, since extraction must climb to degree 3\",\n  \
         \"cells\": [{cells}]\n}}\n"
    );
    let path = "experiments/degree_reduction_mutants.json";
    match std::fs::write(path, &json) {
        Ok(_) => println!("\n[snapshot] wrote {path}"),
        Err(e) => println!("\n[snapshot] FAILED to write {path}: {e}"),
    }
    println!("════════════════════════════════════════════════════════════════");
}
