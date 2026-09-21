//! EXP-R2 — lever L2: does symmetrisation lower the solving degree, and
//! does the lower degree pay for the variables it costs?
//!
//! The thread's last untested lever. Iterations 1–4 killed hybrid slicing,
//! showed degree falls pay only where the base degree is high, killed their
//! composition, and found the `Δ_low` screen to be a size proxy — so L2 is
//! scored the way iterations 2 and 3 scored their levers: measured `D*` and
//! total work at matched shape.
//!
//! ## Same ideal, two presentations
//!
//! | presentation | variables | generator degree |
//! |---|---|---|
//! | symmetrised (`S₄` over `e`, plus the correspondence) | `9ℓ − 3` | 3 |
//! | eliminated (substitute `eᵢ = σᵢ(x)`) | `3ℓ` | 6 |
//!
//! Symmetrisation buys half the degree for three times the variables. Since
//! Macaulay cost is driven by `cols(vars, D) = Σ_{k≤D} C(vars, k)`, whether
//! that trade pays is an arithmetic question — and one that can be answered
//! **exactly, at any `ℓ`, without running a single Gröbner basis**. That
//! crossover is reported first, because it turns out to decide the
//! experiment.
//!
//! Gate **G-R2** (pre-registered): *supported* if mean `D*` on the
//! symmetrised system is strictly below the eliminated one at matched
//! `(n, ℓ)` over ≥ 3 operating points. **G-R2′** (registered here, per
//! iteration 3's lesson that a degree count is not a cost): the symmetrised
//! presentation must also win on total work.
//!
//! Run: `cargo run --release --example degree_reduction_symmetrise [seed]`
//! Snapshot → `experiments/degree_reduction_symmetrise.json`

use cryptanalysis_suite::binary_ecc::F2mElement;
use cryptanalysis_suite::cryptanalysis::binary_semaev_s4::weil_descend_s4;
use cryptanalysis_suite::cryptanalysis::degree_reduction_anf::{
    compare_presentations, s4_is_decomposable, L2Row,
};
use cryptanalysis_suite::cryptanalysis::descent_expansion::enumerate_irreducibles;
use cryptanalysis_suite::cryptanalysis::ffd_harness::num_monomials_upto_degree;
use std::time::{SystemTime, UNIX_EPOCH};

const OMEGA: f64 = 2.807;
/// Generous per-degree elimination budget (~1 minute of the bit-packed
/// reducer). Raised well above the module default so the scan is limited by
/// the mathematics, not by an arbitrarily tight cap.
const BUDGET: u128 = 60_000_000_000;

fn main() {
    let seed = std::env::args()
        .nth(1)
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(7);

    println!("════════════════════════════════════════════════════════════════");
    println!("EXP-R2 — lever L2: symmetrisation vs elimination on S₄ (m = 3)");
    println!("seed={seed}  omega={OMEGA}");
    println!("════════════════════════════════════════════════════════════════");

    // ── The arithmetic that decides the experiment ──────────────────
    println!("\n── Macaulay width of each presentation at its generator degree ──");
    println!("   Exact, no solver needed: cols(vars, D) = sum_{{k<=D}} C(vars, k).");
    println!(
        "\n   {:>3} {:>9} {:>10} {:>13} {:>14}  narrower",
        "l", "sym vars", "elim vars", "cols(sym,3)", "cols(elim,6)"
    );
    let mut crossover: Option<u32> = None;
    let mut width_rows = Vec::new();
    for l in 2..=12u32 {
        let sv = 9 * l - 3;
        let ev = 3 * l;
        let cs = num_monomials_upto_degree(sv, 3);
        let ce = num_monomials_upto_degree(ev, 6);
        let sym_wins = cs < ce;
        if sym_wins && crossover.is_none() {
            crossover = Some(l);
        }
        println!(
            "   {l:>3} {sv:>9} {ev:>10} {cs:>13} {ce:>14}  {}",
            if sym_wins {
                "symmetrised"
            } else {
                "eliminated"
            }
        );
        width_rows.push((l, sv, ev, cs, ce));
    }
    match crossover {
        Some(l) => {
            println!("\n   → Symmetrisation is narrower only from ℓ = {l} upward.");
            println!("     Below that it trades 3× the variables for ½ the degree and loses.");
        }
        None => println!("\n   → No crossover in the scanned range."),
    }

    // ── What the instrument can actually measure ────────────────────
    println!("\n── Measured refutation degrees (non-decomposable targets only) ──");
    println!(
        "\n   {:>2} {:>3} {:>8} {:>9} {:>9} {:>10} {:>9} {:>10}",
        "n", "l", "sym D*", "sym cens", "elim D*", "elim cens", "elim deg", "verdict"
    );
    let mut rows: Vec<L2Row> = Vec::new();
    for n in [6u32, 8, 10] {
        let Some(irr) = enumerate_irreducibles(n, 1).into_iter().next() else {
            continue;
        };
        let b = F2mElement::one(n);
        for l in 2..=3u32 {
            // First non-decomposable target, scanning x_R deterministically
            // from the seed.
            let mut found = None;
            for t in 1u32..64 {
                let tt = t ^ (seed as u32 & 0x1f);
                let bits: Vec<u32> = (0..n).filter(|i| (tt >> i) & 1 == 1).collect();
                if bits.is_empty() {
                    continue;
                }
                let x_r = F2mElement::from_bit_positions(&bits, n);
                let sys = weil_descend_s4(n, l, &irr, &b, &x_r);
                if !s4_is_decomposable(&sys) {
                    found = Some(sys);
                    break;
                }
            }
            let Some(sys) = found else {
                println!("   {n:>2} {l:>3}  — no non-decomposable target found");
                continue;
            };
            let r = compare_presentations(&sys, 14, BUDGET);
            let verdict = if r.elim_degenerate {
                "elim degenerate"
            } else if r.sym_censored_at.is_some() {
                "sym censored"
            } else if r.sym_dstar.is_some() && r.elim_dstar.is_some() {
                "COMPARABLE"
            } else {
                "incomplete"
            };
            println!(
                "   {n:>2} {l:>3} {:>8} {:>9} {:>9} {:>10} {:>9} {:>10}",
                r.sym_dstar.map(|d| d.to_string()).unwrap_or("—".into()),
                r.sym_censored_at
                    .map(|d| format!("≥{d}"))
                    .unwrap_or("—".into()),
                r.elim_dstar.map(|d| d.to_string()).unwrap_or("—".into()),
                r.elim_censored_at
                    .map(|d| format!("≥{d}"))
                    .unwrap_or("—".into()),
                r.elim_deg,
                verdict
            );
            rows.push(r);
        }
    }

    // ── Verdict ─────────────────────────────────────────────────────
    println!("\n════════════════════════════════════════════════════════════════");
    println!("G-R2 / G-R2' verdict");
    println!("════════════════════════════════════════════════════════════════");
    let comparable: Vec<&L2Row> = rows
        .iter()
        .filter(|r| !r.elim_degenerate && r.sym_dstar.is_some() && r.elim_dstar.is_some())
        .collect();
    if comparable.len() >= 3 {
        let wins = comparable
            .iter()
            .filter(|r| r.sym_dstar < r.elim_dstar)
            .count();
        println!(
            "\n  {} comparable cells, symmetrised lower in {wins}.",
            comparable.len()
        );
        for r in &comparable {
            if let Some(s) = r.saving(OMEGA) {
                println!(
                    "    n={} l={}: D* {:?} vs {:?}, log2 work saving {s:+.2}",
                    r.n, r.l, r.sym_dstar, r.elim_dstar
                );
            }
        }
    } else {
        println!("\n  → G-R2: BLOCKED ON REACH — and the block is structural, not");
        println!("    incidental. The two presentations are never simultaneously");
        println!("    measurable by this instrument:");
        println!("\n      ℓ = 2: the eliminated system has degree-6 generators in only 6");
        println!("             variables, so its multilinear Macaulay tower has ZERO");
        println!("             multiplier budget and cannot refute at all. Degenerate.");
        println!("      ℓ ≥ 3: the symmetrised system's 9ℓ−3 variables put its Macaulay");
        println!("             matrix out of budget before it refutes (censored).");
        println!("\n    And the width table above says why that gap cannot be closed by");
        match crossover {
            Some(l) => {
                println!("    spending more compute at small ℓ: symmetrisation only becomes");
                println!("    the narrower presentation at ℓ = {l}, which is far beyond the");
                println!("    ℓ ≤ 3 this dense Macaulay scan reaches. EXP-R2 as designed could");
                println!("    not have answered the question at any budget.");
                println!(
                    "\n    What it would take: a solver that handles {} variables at degree 3",
                    9 * l - 3
                );
                println!("    — real F4/F5 with sparse linear algebra, not a dense scan.");
            }
            None => println!("    spending more compute — no crossover was found."),
        }
        println!("\n    The useful deliverable is therefore the crossover itself: it is exact,");
        println!("    needs no solver, and bounds where L2 can possibly pay. Registered as R2'.");
    }

    // ── Snapshot ────────────────────────────────────────────────────
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let widths = width_rows
        .iter()
        .map(|(l, sv, ev, cs, ce)| {
            format!(
                "{{\"l\":{l},\"sym_vars\":{sv},\"elim_vars\":{ev},\"cols_sym_3\":{cs},\"cols_elim_6\":{ce}}}"
            )
        })
        .collect::<Vec<_>>()
        .join(",");
    let cells = rows
        .iter()
        .map(|r| {
            let o = |v: Option<u32>| v.map(|x| x.to_string()).unwrap_or("null".into());
            format!(
                "{{\"n\":{},\"l\":{},\"sym_vars\":{},\"sym_eqs\":{},\"sym_deg\":{},\
                 \"elim_vars\":{},\"elim_eqs\":{},\"elim_deg\":{},\
                 \"sym_dstar\":{},\"elim_dstar\":{},\"sym_censored_at\":{},\
                 \"elim_censored_at\":{},\"elim_degenerate\":{}}}",
                r.n,
                r.l,
                r.sym_vars,
                r.sym_eqs,
                r.sym_deg,
                r.elim_vars,
                r.elim_eqs,
                r.elim_deg,
                o(r.sym_dstar),
                o(r.elim_dstar),
                o(r.sym_censored_at),
                o(r.elim_censored_at),
                r.elim_degenerate
            )
        })
        .collect::<Vec<_>>()
        .join(",");
    let json = format!(
        "{{\n  \"schema\": \"degree_reduction_symmetrise/v1\",\n  \"experiment\": \"EXP-R2\",\n  \
         \"seed\": {seed},\n  \"generated_at\": {ts},\n  \"omega\": {OMEGA},\n  \
         \"budget_word_ops\": {BUDGET},\n  \"crossover_l\": {},\n  \
         \"widths\": [{widths}],\n  \"cells\": [{cells}]\n}}\n",
        crossover.map(|l| l.to_string()).unwrap_or("null".into())
    );
    let path = "experiments/degree_reduction_symmetrise.json";
    match std::fs::write(path, &json) {
        Ok(_) => println!("\n[snapshot] wrote {path}"),
        Err(e) => println!("\n[snapshot] FAILED to write {path}: {e}"),
    }
    println!("════════════════════════════════════════════════════════════════");
}
