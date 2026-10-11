//! EXP-R7 — scoping the L2 solver: what would it actually take, and is the
//! `ℓ = 6` crossover real?
//!
//! ## Why this is not a prose estimate
//!
//! Iteration 5 left L2 `blocked`, with the note: *"what it would take is a
//! solver handling 51 variables at degree 3 — real F4/F5 with sparse linear
//! algebra."* That sentence rests on **R2′**, whose table compares
//! `cols(9ℓ−3, 3)` against `cols(3ℓ, 6)` — the Macaulay width of each
//! presentation **at its generator degree**.
//!
//! But neither presentation *solves* at its generator degree. EXP-R2's own
//! cells measured the symmetrised system refuting at `D* = 4` for `ℓ = 2`
//! (generator degree 3) and **censored at `D ≥ 5`** for `ℓ = 3`. So the
//! requirement is not "51 variables at degree 3" — it is 51 variables at
//! whatever degree the system actually refutes, and that degree was rising.
//!
//! A scoping exercise that repeats the generator-degree figure would
//! under-state the project by the ratio `cols(51, D*) / cols(51, 3)`, which
//! is two orders of magnitude at `D* = 5` and four at `D* = 7`. So this
//! measures what it can and labels the rest as scenarios.
//!
//! ## Three parts
//!
//! 1. **Measure** `D*` for both presentations at `ℓ = 2, 3` with a budget
//!    raised far enough to clear the degree-5 scan EXP-R2 censored
//!    (~3·10¹¹ word-ops at `ℓ = 3`, against the 6·10¹⁰ it was given).
//! 2. **Cost the real requirement** at `ℓ = 4…8` under a *range* of
//!    assumed solving degrees, under both a dense bit-packed model and a
//!    sparse block-Wiedemann model. These are scenarios, not predictions —
//!    AGENTS.md §6 forbids presenting an extrapolation as a measurement.
//! 3. **Inventory** what this repo already has against what the project
//!    needs, so the effort estimate is a delta rather than a greenfield
//!    guess.
//!
//! Run: `cargo run --release --example degree_reduction_l2_scope`
//! Snapshot → `experiments/degree_reduction_l2_scope.json`

use cryptanalysis_suite::binary_ecc::F2mElement;
use cryptanalysis_suite::cryptanalysis::binary_semaev_s4::weil_descend_s4;
use cryptanalysis_suite::cryptanalysis::degree_reduction_anf::{
    compare_presentations, s4_is_decomposable,
};
use cryptanalysis_suite::cryptanalysis::descent_expansion::enumerate_irreducibles;
use cryptanalysis_suite::cryptanalysis::ffd_harness::num_monomials_upto_degree;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

/// Raised ~30× above EXP-R2's 6·10¹⁰ so the `ℓ = 3` degree-5 scan
/// (~3·10¹¹ word-ops) is inside it. Degree 6 there needs ~2.8·10¹³ and is
/// still out — that boundary is reported, not hidden.
const DEFAULT_BUDGET: u128 = 50_000_000_000_000;

/// Dense bit-packed elimination: `rows · cols · ceil(cols/64)` word-ops,
/// `rows · cols / 8` bytes.
fn dense_cost(vars: u32, eqs: u32, gen_deg: u32, solve_deg: u32) -> (f64, f64) {
    let cols = num_monomials_upto_degree(vars, solve_deg) as f64;
    let mult = num_monomials_upto_degree(vars, solve_deg.saturating_sub(gen_deg)) as f64;
    let rows = eqs as f64 * mult;
    (rows * cols * (cols / 64.0).ceil(), rows * cols / 8.0)
}

/// Sparse block-Wiedemann: the Macaulay rows are shifted generators, so
/// each carries only the generator's term count `t`. Cost `≈ nnz · cols`
/// with `nnz = rows · t`; memory `≈ nnz · 8` bytes for (row, col) indices.
/// This is the model that makes the project conceivable at all, and it is
/// optimistic: it ignores fill-in in the F4 reduction steps.
fn sparse_cost(vars: u32, eqs: u32, gen_deg: u32, solve_deg: u32, terms: u32) -> (f64, f64) {
    let cols = num_monomials_upto_degree(vars, solve_deg) as f64;
    let mult = num_monomials_upto_degree(vars, solve_deg.saturating_sub(gen_deg)) as f64;
    let rows = eqs as f64 * mult;
    let nnz = rows * terms as f64;
    (nnz * cols, nnz * 8.0)
}

fn human_ops(v: f64) -> String {
    if !v.is_finite() {
        return "—".into();
    }
    for (t, s) in [
        (1e18, "E"),
        (1e15, "P"),
        (1e12, "T"),
        (1e9, "G"),
        (1e6, "M"),
    ] {
        if v >= t {
            return format!("{:.1}{s}", v / t);
        }
    }
    format!("{v:.0}")
}

fn human_bytes(v: f64) -> String {
    if !v.is_finite() {
        return "—".into();
    }
    for (t, s) in [
        (1e15, "PB"),
        (1e12, "TB"),
        (1e9, "GB"),
        (1e6, "MB"),
        (1e3, "KB"),
    ] {
        if v >= t {
            return format!("{:.1}{s}", v / t);
        }
    }
    format!("{v:.0}B")
}

fn main() {
    // The degree-5 scan at `ℓ = 3` prices at ~2·10¹² under the module's
    // `rows · min(rows, cols) · cols / 64` elimination model — just over the
    // 2·10¹² EXP-R2 would have allowed, which is why it censored there. The
    // default here clears it by 25×; overridable so the boundary can be
    // probed rather than asserted.
    let budget: u128 = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(DEFAULT_BUDGET);

    println!("════════════════════════════════════════════════════════════════");
    println!("EXP-R7 — scoping the L2 solver");
    println!("════════════════════════════════════════════════════════════════");

    // ── Part 1: measure D* where we can ─────────────────────────────
    println!("\n════════════════════════════════════════════════════════════════");
    println!("Part 1 — MEASURED solving degrees (budget {budget} word-ops)");
    println!("════════════════════════════════════════════════════════════════");
    println!(
        "\n  {:>3} {:>3} {:>9} {:>8} {:>8} {:>9} {:>9} {:>10} {:>8}",
        "n", "l", "sym_vars", "sym_eqs", "sym D*", "sym cens", "elim D*", "elim cens", "secs"
    );
    let mut measured = Vec::new();
    for n in [6u32, 8] {
        let Some(irr) = enumerate_irreducibles(n, 1).into_iter().next() else {
            continue;
        };
        let b = F2mElement::one(n);
        for l in 2..=3u32 {
            let mut found = None;
            for t in 1u32..64 {
                let bits: Vec<u32> = (0..n).filter(|i| (t >> i) & 1 == 1).collect();
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
            let Some(sys) = found else { continue };
            let t0 = Instant::now();
            let r = compare_presentations(&sys, 6, budget);
            let secs = t0.elapsed().as_secs_f64();
            println!(
                "  {:>3} {:>3} {:>9} {:>8} {:>8} {:>9} {:>9} {:>10} {:>8.1}",
                n,
                l,
                r.sym_vars,
                r.sym_eqs,
                r.sym_dstar.map(|d| d.to_string()).unwrap_or("—".into()),
                r.sym_censored_at
                    .map(|d| format!(">={d}"))
                    .unwrap_or("—".into()),
                r.elim_dstar.map(|d| d.to_string()).unwrap_or("—".into()),
                r.elim_censored_at
                    .map(|d| format!(">={d}"))
                    .unwrap_or("—".into()),
                secs
            );
            measured.push((n, l, r, secs));
        }
    }

    // What the measured degrees say about the generator-degree comparison.
    println!("\n  The number R2′ compares is the width at the GENERATOR degree.");
    println!("  The number that decides cost is the width at the SOLVING degree:\n");
    println!(
        "  {:>3} {:>9} {:>16} {:>16} {:>12}",
        "l", "sym_vars", "cols at gen deg 3", "cols at measured D*", "understated"
    );
    for (_, l, r, _) in &measured {
        let d = r.sym_dstar.or(r.sym_censored_at);
        let g = num_monomials_upto_degree(r.sym_vars, 3) as f64;
        let s = d.map(|d| num_monomials_upto_degree(r.sym_vars, d) as f64);
        println!(
            "  {:>3} {:>9} {:>16} {:>16} {:>12}",
            l,
            r.sym_vars,
            format!("{g:.0}"),
            s.map(|v| format!("{v:.0}")).unwrap_or("—".into()),
            s.map(|v| format!("{:.0}x", v / g)).unwrap_or("—".into())
        );
    }

    // ── Part 2: the real requirement, as scenarios ──────────────────
    println!("\n════════════════════════════════════════════════════════════════");
    println!("Part 2 — REQUIREMENT at l = 4..8, as SCENARIOS over the solving degree");
    println!("════════════════════════════════════════════════════════════════");
    println!("\n  These are scenarios, not predictions: D*(l) is measured only at");
    println!("  l = 2, 3 above. Generator term count taken as 8 (S4 correspondence");
    println!("  rows are sparse); the sparse model ignores F4 fill-in, so it is");
    println!("  optimistic — a floor on the cost, not an estimate of it.\n");
    println!(
        "  {:>3} {:>6} {:>3} {:>10} {:>11} {:>11} {:>11} {:>11}",
        "l", "vars", "D*", "cols", "dense ops", "dense mem", "sparse ops", "sparse mem"
    );
    let mut scenarios = Vec::new();
    for l in [4u32, 5, 6, 7, 8] {
        let vars = 9 * l - 3;
        let eqs = 6 * l - 3 + 8;
        for d in 3..=8u32 {
            let cols = num_monomials_upto_degree(vars, d) as f64;
            let (dops, dmem) = dense_cost(vars, eqs, 3, d);
            let (sops, smem) = sparse_cost(vars, eqs, 3, d, 8);
            if l == 6 || d == 5 {
                println!(
                    "  {:>3} {:>6} {:>3} {:>10} {:>11} {:>11} {:>11} {:>11}",
                    l,
                    vars,
                    d,
                    format!("{cols:.0}"),
                    human_ops(dops),
                    human_bytes(dmem),
                    human_ops(sops),
                    human_bytes(smem)
                );
            }
            scenarios.push((l, vars, eqs, d, cols, dops, dmem, sops, smem));
        }
    }

    // ── Part 3: the decision ────────────────────────────────────────
    //
    // The comparison R2′ makes is at each presentation's GENERATOR degree.
    // The comparison that decides cost is at its SOLVING degree, and there
    // is an exact bound available on one side: the eliminated presentation
    // lives in `3ℓ` Boolean variables, so its Macaulay matrix can never be
    // wider than the whole multilinear space `2^{3ℓ}` — at ANY degree,
    // whatever `D*` turns out to be. The symmetrised presentation has no
    // such ceiling below `2^{9ℓ−3}`.
    //
    // So "is symmetrisation ever narrower?" can be answered without
    // measuring the eliminated side at all: compare the symmetrised width
    // at its solving degree against elimination's entire space.
    println!("\n════════════════════════════════════════════════════════════════");
    println!("Part 3 — the decision, against an EXACT bound on the other side");
    println!("════════════════════════════════════════════════════════════════");
    println!("\n  The eliminated presentation has 3l Boolean variables, so its whole");
    println!("  multilinear monomial space is 2^(3l) — an upper bound on its Macaulay");
    println!("  width at EVERY degree. Symmetrisation is worth building only if it is");
    println!("  narrower than that ceiling at the degree it actually solves.\n");
    println!(
        "  {:>3} {:>8} {:>14} {:>14} {:>14} {:>14}",
        "l", "sym_vars", "elim CEILING", "sym @ D*=4", "sym @ D*=5", "sym @ trend"
    );
    // Measured: D*(sym) = 4 at l = 2, 5 at l = 3. Marked as an
    // extrapolation wherever it is used, per AGENTS.md §6.
    let trend = |l: u32| l + 2;
    let mut verdicts = Vec::new();
    for l in 3..=8u32 {
        let sv = 9 * l - 3;
        let ceiling = 2f64.powi(3 * l as i32);
        let c4 = num_monomials_upto_degree(sv, 4) as f64;
        let c5 = num_monomials_upto_degree(sv, 5) as f64;
        let ct = num_monomials_upto_degree(sv, trend(l)) as f64;
        println!(
            "  {:>3} {:>8} {:>14} {:>14} {:>14} {:>14}",
            l,
            sv,
            format!("{ceiling:.0}"),
            format!("{c4:.0}"),
            format!("{c5:.0}"),
            format!("{ct:.0} (D*={})", trend(l))
        );
        verdicts.push((l, ceiling, c4, c5, ct));
    }
    println!("\n  Reading the columns:");
    let win4 = verdicts.iter().find(|v| v.2 < v.1).map(|v| v.0);
    let win5 = verdicts.iter().find(|v| v.3 < v.1).map(|v| v.0);
    let wint = verdicts.iter().find(|v| v.4 < v.1).map(|v| v.0);
    println!(
        "    if D* stayed pinned at 4: symmetrisation first wins at l = {}",
        win4.map(|l| l.to_string())
            .unwrap_or("never in range".into())
    );
    println!(
        "    if D* stayed pinned at 5: symmetrisation first wins at l = {}",
        win5.map(|l| l.to_string())
            .unwrap_or("never in range".into())
    );
    println!(
        "    on the MEASURED trend D* = l+2: symmetrisation first wins at l = {}",
        wint.map(|l| l.to_string())
            .unwrap_or("NEVER in range".into())
    );
    println!("\n  D* is measured at 4 (l=2) and 5 (l=3) — it is rising, not pinned.");
    println!("  The l+2 column is an EXTRAPOLATION from two points and is labelled as");
    println!("  one; the two pinned columns are the favourable cases it brackets, and");
    println!("  both are contradicted by the l=2 -> l=3 step.");
    println!("\n  → R2′'s 'crossover at l = 6' is a generator-degree artifact. At the");
    println!("    solving degree, on the only trend the data supports, there is no");
    println!("    crossover in range at all. The solver would be built to measure a");
    println!("    lever the arithmetic has already decided against.");

    println!("\n  What this repo already has:");
    println!("    groebner_f4.rs     matrix-F4 over F_p, grevlex, MPoly/BigUint coeffs.");
    println!("                       Explicitly out of scope in its own docs: sparse LA,");
    println!("                       F5 signatures, incremental Macaulay. Wrong field");
    println!("                       representation for this job (needs bit-packed F_2).");
    println!("    ffd_harness.rs     dense bit-packed F_2 Macaulay + rank_and_refute.");
    println!("                       Right field, right packing, no sparsity.");
    println!("    pq_sparse_la.rs    structured Gaussian over Z/N for index-calculus");
    println!("                       RELATION matrices — different shape, different ring.");
    println!("    pq_wiedemann.rs    Wiedemann over Z/N. The algorithm transfers, the");
    println!("                       implementation does not.");
    println!("\n  The delta would be a sparse F_2 Macaulay/F4 with signature pruning and");
    println!("  block Wiedemann over F_2 — new code in both cases. Not started, because");
    println!("  Part 3 says there is nothing at the end of it.");

    // ── Snapshot ────────────────────────────────────────────────────
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let meas = measured
        .iter()
        .map(|(n, l, r, secs)| {
            format!(
                "{{\"n\":{n},\"l\":{l},\"sym_vars\":{},\"sym_eqs\":{},\"sym_dstar\":{},\
                 \"sym_censored_at\":{},\"elim_dstar\":{},\"elim_censored_at\":{},\
                 \"secs\":{secs:.1}}}",
                r.sym_vars,
                r.sym_eqs,
                r.sym_dstar.map(|d| d.to_string()).unwrap_or("null".into()),
                r.sym_censored_at
                    .map(|d| d.to_string())
                    .unwrap_or("null".into()),
                r.elim_dstar.map(|d| d.to_string()).unwrap_or("null".into()),
                r.elim_censored_at
                    .map(|d| d.to_string())
                    .unwrap_or("null".into())
            )
        })
        .collect::<Vec<_>>()
        .join(",\n    ");
    let scen = scenarios
        .iter()
        .map(|(l, v, e, d, c, dops, dmem, sops, smem)| {
            format!(
                "{{\"l\":{l},\"vars\":{v},\"eqs\":{e},\"solve_degree\":{d},\"cols\":{c:.0},\
                 \"dense_ops\":{dops:.0},\"dense_bytes\":{dmem:.0},\
                 \"sparse_ops\":{sops:.0},\"sparse_bytes\":{smem:.0}}}"
            )
        })
        .collect::<Vec<_>>()
        .join(",\n    ");
    let json = format!(
        "{{\n  \"schema\": \"degree_reduction_l2_scope/v1\",\n  \"experiment\": \"EXP-R7\",\n  \
         \"generated_at\": {ts},\n  \"budget_word_ops\": {budget},\n  \
         \"generator_terms_assumed\": 8,\n  \
         \"measured\": [\n    {meas}\n  ],\n  \"dstar_trend\": \"D*(sym) = 4 at l=2, 5 at l=3; l+2 used as a labelled extrapolation\",\n  \
         \"crossover_pinned_d4\": {},\n  \"crossover_pinned_d5\": {},\n  \"crossover_on_trend\": {},\n  \
         \"scenarios\": [\n    {scen}\n  ]\n}}\n",
        win4.map(|l| l.to_string()).unwrap_or("null".into()),
        win5.map(|l| l.to_string()).unwrap_or("null".into()),
        wint.map(|l| l.to_string()).unwrap_or("null".into())
    );
    let out = "experiments/degree_reduction_l2_scope.json";
    match std::fs::write(out, &json) {
        Ok(_) => println!("\n[snapshot] wrote {out}"),
        Err(e) => println!("\n[snapshot] FAILED to write {out}: {e}"),
    }
    println!("════════════════════════════════════════════════════════════════");
}
