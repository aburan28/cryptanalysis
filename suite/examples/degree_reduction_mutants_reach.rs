//! EXP-R3b — does L4's net saving survive at larger `N`?
//!
//! ## Why this experiment exists
//!
//! EXP-R3 (iteration 2) measured the mutant route at `N ∈ {10, 12, 14}` and
//! found the Random-family net saving *growing*: `+0.94 → +1.75 → +1.62`
//! bits. R3′ recorded that as `regime-dependent` and the thread's queue
//! called reaching for the trend the cheapest remaining item with a positive
//! result at stake. This is that reach: the same cells at
//! `N ∈ {16, 18, 20}`, with the same accounting.
//!
//! Three sizes is a short lever arm for a trend claim. Six is still short,
//! but it is the difference between "the saving grew over the only sizes we
//! could reach" and "the saving grew and then did *this*".
//!
//! ## What was already seen, and what the gate is registered on
//!
//! A feasibility probe run before this experiment established that the cells
//! complete at `N = 16, 18, 20` (3.4 s / 11 s / 41 s per 2 targets) and
//! reported their **degrees**. So the degree numbers below were seen before
//! the gate was written, and a gate on them would be worthless.
//!
//! Gate **G-R3b** is therefore registered on the **net saving in bits**,
//! which the probe did not compute and which nobody had seen when the gate
//! was written:
//!
//! * *supported* — net saving `> 0` at all of `N = 16, 18, 20`, **and** the
//!   mean saving over `{16,18,20}` is not more than `0.25` bits below the
//!   mean over `{10,12,14}` (the same materiality threshold G-R5′ uses).
//! * *killed* — net saving `≤ 0` at any of `N = 16, 18, 20`.
//! * *flat* — positive everywhere but the mean has fallen by more than
//!   `0.25` bits: the trend EXP-R3 saw does not continue, though the lever
//!   still pays.
//!
//! The probe's degree finding is reported below as an **observation**, not a
//! gated prediction, and labelled as such.
//!
//! ## What is unchanged from EXP-R3
//!
//! Same cost model (`rows(D)·cols(D)^{ω−1}`, `rows(D) = eqs·cols(D−2)`),
//! same charging of the extraction, same `worsened > 0` soundness invariant,
//! same 8 matched non-decomposable targets per cell. Only the operating
//! points move, so the two tables are directly comparable.
//!
//! Run: `cargo run --release --example degree_reduction_mutants_reach [seed]`
//! Snapshot → `experiments/degree_reduction_mutants_reach.json`

use cryptanalysis_suite::cryptanalysis::degree_reduction::{
    log2_enumeration_cost, log2_expected_cost, run_mutant_cell, MutantRow,
};
use cryptanalysis_suite::cryptanalysis::descent_expansion::enumerate_irreducibles;
use cryptanalysis_suite::cryptanalysis::descent_lowgamma::BasisFamily;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

const OMEGA: f64 = 2.807;
/// Materiality threshold for "the trend continued", reused from G-R5′.
const MATERIAL_BITS: f64 = 0.25;

struct Cell {
    family: BasisFamily,
    row: MutantRow,
    base: f64,
    solve: f64,
    total: f64,
    saving: f64,
    /// `log2(2^N · eqs)` — the enumeration boundary of §3. Positive margin
    /// means the Groebner route beats brute force; negative means it loses.
    enum_cost: f64,
    margin: f64,
    seed: u64,
    secs: f64,
}

fn main() {
    let seeds: Vec<u64> = {
        let given: Vec<u64> = std::env::args()
            .skip(1)
            .filter_map(|s| s.parse::<u64>().ok())
            .collect();
        if given.is_empty() {
            vec![7, 11, 23]
        } else {
            given
        }
    };

    // The original three points and the three this experiment adds. Both are
    // measured here so the trend is one table under one accounting.
    let old: &[(u32, u32)] = &[(10, 5), (12, 6), (14, 7)];
    let new: &[(u32, u32)] = &[(16, 8), (18, 9), (20, 10)];
    let families = [
        BasisFamily::Random,
        BasisFamily::Coordinate,
        BasisFamily::Subfield,
    ];
    let rounds = 6u32;
    let targets = 8u32;

    println!("════════════════════════════════════════════════════════════════");
    println!("EXP-R3b — does L4's net saving survive at larger N?");
    println!("seeds={seeds:?}  critical regime 2n'=n  targets/cell={targets}  rounds<={rounds}");
    println!("════════════════════════════════════════════════════════════════");

    let mut cells: Vec<Cell> = Vec::new();
    for &seed in &seeds {
        for &family in &families {
            println!("\n── seed {seed}, family = {family:?} ──");
            println!(
                "  {:>3} {:>4} {:>6} {:>8} {:>8} {:>7} {:>8} {:>7} {:>8} {:>7}",
                "N",
                "eqs",
                "falls",
                "sat.eqs",
                "D* base",
                "D* aug",
                "working",
                "improv",
                "log2 sav",
                "secs"
            );
            for &(n, n_sub) in old.iter().chain(new) {
                let Some(irr) = enumerate_irreducibles(n, 1).into_iter().next() else {
                    continue;
                };
                let t0 = Instant::now();
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
                let secs = t0.elapsed().as_secs_f64();
                let base = log2_expected_cost(&r.dstar_base_hist, r.full_vars, r.n, OMEGA);
                let solve = log2_expected_cost(
                    &r.dstar_aug_hist,
                    r.full_vars,
                    r.aug_eqs_mean.round() as u32,
                    OMEGA,
                );
                let total = (r.log2_extraction_cost.exp2() + solve.exp2()).log2();
                let saving = base - total;
                let enum_cost = log2_enumeration_cost(r.full_vars, r.n);
                let margin = enum_cost - total;
                println!(
                "  {:>3} {:>4} {:>6.1} {:>8.1} {:>8.2} {:>7.2} {:>8.2} {:>4}/{:<2} {:>+8.2} {:>7.1}",
                r.full_vars,
                r.n,
                r.falls_mean,
                r.aug_eqs_mean,
                r.dstar_base_mean,
                r.dstar_aug_mean,
                r.working_degree_mean,
                r.improved,
                r.targets,
                saving,
                secs
            );
                if r.worsened > 0 {
                    println!(
                        "  [UNSOUND] {} target(s) got WORSE — adding ideal elements cannot do that",
                        r.worsened
                    );
                }
                cells.push(Cell {
                    family,
                    row: r,
                    base,
                    solve,
                    total,
                    saving,
                    enum_cost,
                    margin,
                    seed,
                    secs,
                });
            }
        }
    }

    let unsound: u32 = cells.iter().map(|c| c.row.worsened).sum();
    if unsound > 0 {
        println!("\n  → INVALID: {unsound} target(s) got worse under augmentation.");
        println!("    Adding ideal elements cannot raise D*, so the extractor is unsound.");
        println!("    Fix it before reading anything else in this run.");
        return;
    }

    // ── Observation (not gated): where the floor stops being reached ──
    println!("\n════════════════════════════════════════════════════════════════");
    println!("Observation (seen in the feasibility probe, so NOT gated)");
    println!("════════════════════════════════════════════════════════════════");
    println!("\n  Does the augmented system still collapse to the D*=2 floor?\n");
    println!(
        "  {:>12} {:>4} {:>8} {:>8} {:>9}",
        "family", "N", "D* base", "D* aug", "at floor?"
    );
    for c in &cells {
        println!(
            "  {:>12} {:>4} {:>8.2} {:>8.2} {:>9}",
            format!("{:?}", c.family),
            c.row.full_vars,
            c.row.dstar_base_mean,
            c.row.dstar_aug_mean,
            if c.row.dstar_aug_mean <= 2.0 + 1e-9 {
                "yes"
            } else {
                "NO"
            }
        );
    }

    // ── G-R3b: the pre-registered cost gate ──
    println!("\n════════════════════════════════════════════════════════════════");
    println!("G-R3b verdict (pre-registered on the net saving, in bits)");
    println!("════════════════════════════════════════════════════════════════");
    for &family in &families {
        let fam: Vec<&Cell> = cells.iter().filter(|c| c.family == family).collect();
        if fam.is_empty() {
            continue;
        }
        // In the critical regime `full_vars == 2n' == n`, so the field
        // degree identifies the operating point on its own.
        let at = |ps: &[(u32, u32)], seed: u64| -> Vec<f64> {
            fam.iter()
                .filter(|c| c.seed == seed && ps.iter().any(|&(n, _)| c.row.n == n))
                .map(|c| c.saving)
                .collect()
        };
        let mean = |v: &[f64]| {
            if v.is_empty() {
                f64::NAN
            } else {
                v.iter().sum::<f64>() / v.len() as f64
            }
        };
        println!("\n  {family:?}:");
        let mut verdicts = Vec::new();
        for &seed in &seeds {
            let (o, nn) = (at(old, seed), at(new, seed));
            if nn.is_empty() {
                continue;
            }
            let (mo, mn) = (mean(&o), mean(&nn));
            let all_pos = nn.iter().all(|&s| s > 0.0);
            let v = if !all_pos {
                "KILLED"
            } else if mn >= mo - MATERIAL_BITS {
                "SUPPORTED"
            } else {
                "FLAT"
            };
            verdicts.push(v);
            println!(
                "    seed {seed:>3}: {:.2} -> {:.2} bits   reach: {}   → {v}",
                mo,
                mn,
                nn.iter()
                    .map(|s| format!("{s:+.2}"))
                    .collect::<Vec<_>>()
                    .join("  ")
            );
        }
        // A gate whose verdict depends on the seed has not decided anything.
        // Saying so is the verdict; picking the majority would be choosing
        // the answer after seeing it.
        let stable = verdicts.windows(2).all(|w| w[0] == w[1]);
        if stable {
            println!(
                "    → G-R3b: {} (same on all {} seeds)",
                verdicts[0],
                seeds.len()
            );
        } else {
            println!(
                "    → G-R3b: UNSTABLE across seeds ({}) — no verdict. The cells sit on",
                verdicts.join("/")
            );
            println!("      the gate boundary, so the seed picks the answer.");
        }
    }

    // ── The column that actually decides: the 2^N boundary ──
    //
    // AGENTS.md §3: progress is the ratio to a stated boundary, not the
    // constant. The gate above scores L4 against the RAW Groebner solve,
    // which is the wrong reference for an attack claim — it is a comparison
    // between two things that may both lose. §3 of the charter fixes the
    // boundary as `2^N` enumeration, so that is what the route has to beat.
    println!("\n════════════════════════════════════════════════════════════════");
    println!("Ratio to the boundary (§3: 2^N enumeration) — the column that decides");
    println!("════════════════════════════════════════════════════════════════");
    println!(
        "\n  {:>12} {:>4} {:>10} {:>10} {:>11} {:>10} {:>11}",
        "family", "N", "enum 2^N", "raw solve", "raw margin", "aug total", "aug margin"
    );
    let mut margins: Vec<(u32, f64)> = Vec::new();
    for &family in &families {
        for &seed in &seeds[..1] {
            for c in cells
                .iter()
                .filter(|c| c.family == family && c.seed == seed)
            {
                println!(
                    "  {:>12} {:>4} {:>10.2} {:>10.2} {:>+11.2} {:>10.2} {:>+11.2}",
                    format!("{:?}", c.family),
                    c.row.full_vars,
                    c.enum_cost,
                    c.base,
                    c.enum_cost - c.base,
                    c.total,
                    c.margin
                );
                if c.family == BasisFamily::Random {
                    margins.push((c.row.full_vars, c.margin));
                }
            }
        }
    }
    let beats = cells.iter().filter(|c| c.margin > 0.0).count();
    println!(
        "\n  Cells where the augmented route BEATS 2^N enumeration: {beats} of {}",
        cells.len()
    );
    margins.sort_by_key(|&(n, _)| n);
    if let (Some(&(n0, m0)), Some(&(n1, m1))) = (margins.first(), margins.last()) {
        let dir = if m1 < m0 { "WIDENING" } else { "narrowing" };
        println!(
            "  Random margin at N={n0}: {m0:+.2} bits;  at N={n1}: {m1:+.2} bits  → gap {dir}"
        );
        println!(
            "  Per size step that is {:+.3} bits of ground {} against brute force.",
            (m1 - m0) / ((n1 - n0) as f64 / 2.0),
            if m1 < m0 { "LOST" } else { "gained" }
        );
    }
    // The one column that trends toward the boundary, and why it is not a
    // result. Printed here so the artifact carries the caveat with the
    // number, rather than leaving it to whoever quotes the table.
    let sub: Vec<&Cell> = cells
        .iter()
        .filter(|c| c.family == BasisFamily::Subfield && c.seed == seeds[0])
        .collect();
    if let (Some(a), Some(b)) = (sub.first(), sub.last()) {
        println!(
            "\n  Note: the RAW Subfield solve closes on the boundary, {:+.2} -> {:+.2} bits",
            a.enum_cost - a.base,
            b.enum_cost - b.base
        );
        println!(
            "  over N={}..{}. That is arithmetic, not cryptanalysis: Subfield's D* sits",
            a.row.full_vars, b.row.full_vars
        );
        println!("  at the Nullstellensatz floor (~2.1), so a poly(N) solve against a 2^N");
        println!("  baseline must cross eventually. It measures that family's DEGENERACY");
        println!("  (the FFD program's L1 result), not a lever of this thread — and L4");
        println!(
            "  makes it worse, not better: augmented margin {:+.2} vs raw {:+.2} at N={}.",
            a.margin,
            a.enum_cost - a.base,
            a.row.full_vars
        );
    }
    println!("\n  Reminder: the saving is against the RAW Groebner solve, not against");
    println!("  the 2^N enumeration boundary. Per AGENTS.md §3 a positive number");
    println!("  here is not attack progress on its own — §6 of the charter carries");
    println!("  the boundary column.");

    // ── Snapshot ────────────────────────────────────────────────────
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let body = cells
        .iter()
        .map(|c| {
            format!(
                "{{\"family\":\"{:?}\",\"seed\":{},\"n\":{},\"vars\":{},\"eqs\":{},\"targets\":{},\
                 \"dstar_base\":{:.4},\"dstar_aug\":{:.4},\"working_degree\":{:.4},\
                 \"improved\":{},\"worsened\":{},\"falls\":{:.2},\"aug_eqs\":{:.2},\
                 \"log2_base\":{:.4},\"log2_extract\":{:.4},\"log2_solve\":{:.4},\
                 \"log2_total\":{:.4},\"log2_saving\":{:.4},\"log2_enum\":{:.4},\
                 \"boundary_margin\":{:.4},\"secs\":{:.1}}}",
                c.family,
                c.seed,
                c.row.n,
                c.row.full_vars,
                c.row.n,
                c.row.targets,
                c.row.dstar_base_mean,
                c.row.dstar_aug_mean,
                c.row.working_degree_mean,
                c.row.improved,
                c.row.worsened,
                c.row.falls_mean,
                c.row.aug_eqs_mean,
                c.base,
                c.row.log2_extraction_cost,
                c.solve,
                c.total,
                c.saving,
                c.enum_cost,
                c.margin,
                c.secs
            )
        })
        .collect::<Vec<_>>()
        .join(",\n    ");
    let json = format!(
        "{{\n  \"schema\": \"degree_reduction_mutants_reach/v1\",\n  \
         \"experiment\": \"EXP-R3b\",\n  \"generated_at\": {ts},\n  \
         \"seeds\": {seeds:?},\n  \"omega\": {OMEGA},\n  \"targets_per_cell\": {targets},\n  \
         \"cells\": [\n    {body}\n  ]\n}}\n"
    );
    let out = "experiments/degree_reduction_mutants_reach.json";
    match std::fs::write(out, &json) {
        Ok(_) => println!("\n[snapshot] wrote {out}"),
        Err(e) => println!("\n[snapshot] FAILED to write {out}: {e}"),
    }
    println!("════════════════════════════════════════════════════════════════");
}
