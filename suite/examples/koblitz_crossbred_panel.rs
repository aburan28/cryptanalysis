//! Crossbred against the other decomposition oracles, end to end.
//!
//! ```bash
//! cargo run --release --example koblitz_crossbred_panel
//! cargo run --release --example koblitz_crossbred_panel -- --json
//! ```
//!
//! The oracle ladder in `examples/crossbred_bench.rs` prices one
//! decomposition attempt.  This runs the whole index-calculus pipeline
//! with the strategy as the only variable and reports **relations per
//! second**, which is the metric Route 1 of
//! `research/notes/ecc2k130/RESEARCH_ECC2K130_ROUTES.md` asks for.  See
//! `RESEARCH_ECC2K130_CROSSBRED.md` for what the numbers mean.
//!
//! Everything but `strategy` is held identical across the arms: same
//! curve, factor base, `m`, seed, trial cap and linear algebra.  A row
//! that does not recover the planted scalar is not a result, and the
//! `solved` column says so.
//!
//! What this does **not** buy: relation collection stays `Θ(2^n)` with
//! any oracle polynomial in the factor base
//! (`RESEARCH_SEMAEV_DECOMPOSITION.md`), so a faster oracle moves the
//! constant and the reach, never the exponent.

use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    koblitz_index_calculus_dlp, DecompositionStrategy, KoblitzCurve, KoblitzIcOptions,
};
use num_bigint::BigUint;
use std::time::Instant;

/// One arm of the panel.
struct Row {
    strategy: &'static str,
    n: u32,
    m: usize,
    relations: usize,
    trials: usize,
    wall_ms: f64,
    relations_per_s: f64,
    solved: bool,
}

fn run(
    label: &'static str,
    strategy: DecompositionStrategy,
    a: u8,
    n: u32,
    m: usize,
    secret: u64,
    seed: u64,
    max_trials: usize,
) -> Option<Row> {
    let kc = KoblitzCurve::new(a, n)?;
    let q = kc.mul(kc.generator(), &BigUint::from(secret));
    let opts = KoblitzIcOptions {
        m,
        strategy,
        max_trials,
        seed,
        // The generic `aG + bQ = O` shortcut would solve the instance
        // without ever calling the oracle under test, so it is counted
        // and skipped rather than credited.
        allow_direct_relation: false,
        ..Default::default()
    };
    let t = Instant::now();
    let report = koblitz_index_calculus_dlp(&kc, &q, &opts)?;
    let wall = t.elapsed().as_secs_f64();
    let collection = (report.relation_collection_ns as f64) / 1e9;
    Some(Row {
        strategy: label,
        n,
        m,
        relations: report.relations,
        trials: report.trials,
        wall_ms: wall * 1e3,
        relations_per_s: if collection > 0.0 {
            report.relations as f64 / collection
        } else {
            f64::INFINITY
        },
        solved: report.log.as_ref() == Some(&BigUint::from(secret)),
    })
}

fn main() {
    let json = std::env::args().any(|a| a == "--json");
    let mut rows = Vec::new();

    // Every (a, n, m) the oracle ladder covers and that has a prime
    // order subgroup, each arm on the same instance and seed.
    for (a, n, m, secret) in [
        (0u8, 7u32, 2usize, 5u64),
        (1, 7, 2, 3),
        (0, 9, 2, 11),
        (1, 9, 2, 7),
        (0, 9, 3, 11),
    ] {
        for (label, strategy) in [
            ("crossbred", DecompositionStrategy::Crossbred),
            ("groebner", DecompositionStrategy::Groebner),
            ("sat", DecompositionStrategy::Sat),
            ("enumerate", DecompositionStrategy::Enumerate),
        ] {
            if let Some(row) = run(label, strategy, a, n, m, secret, 0xB0B, 20_000) {
                rows.push(row);
            }
        }
    }

    if json {
        println!("[");
        for (i, r) in rows.iter().enumerate() {
            let comma = if i + 1 == rows.len() { "" } else { "," };
            println!(
                "  {{\"strategy\":\"{}\",\"n\":{},\"m\":{},\"relations\":{},\"trials\":{},\
                 \"wall_ms\":{:.3},\"relations_per_s\":{:.3},\"solved\":{}}}{}",
                r.strategy,
                r.n,
                r.m,
                r.relations,
                r.trials,
                r.wall_ms,
                r.relations_per_s,
                r.solved,
                comma
            );
        }
        println!("]");
        return;
    }

    println!();
    println!("=== Relations per second, whole pipeline, strategy the only variable ===");
    println!();
    println!(
        "| {:<9} | {:>2} | {:>1} | {:>9} | {:>6} | {:>9} | {:>13} | {:>6} |",
        "strategy", "n", "m", "relations", "trials", "wall (ms)", "relations/s", "solved"
    );
    println!(
        "|{:-<11}|{:->4}|{:->3}|{:->11}|{:->8}|{:->11}|{:->15}|{:->8}|",
        "", "", "", "", "", "", "", ""
    );
    for r in &rows {
        println!(
            "| {:<9} | {:>2} | {:>1} | {:>9} | {:>6} | {:>9.1} | {:>13.1} | {:>6} |",
            r.strategy,
            r.n,
            r.m,
            r.relations,
            r.trials,
            r.wall_ms,
            r.relations_per_s,
            if r.solved { "yes" } else { "NO" }
        );
    }
    println!();
    println!("A row whose `solved` is not `yes` is not a result.");
    println!("Relation collection stays Theta(2^n) with any oracle polynomial in the");
    println!("factor base; this prices the constant, not the exponent.");
}
