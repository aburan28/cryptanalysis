//! **`r∞` at `k = 4`, measured: the linear algebra against rho.**
//!
//! Companion to §11.18–11.19 of
//! `research/notes/index-calculus/RESEARCH_RESIDUAL_WALKS.md`.  Relations come
//! from the meet-in-the-middle oracle (not the `S₅` solve, whose cost `r∞`
//! does not depend on); they are filtered and solved as §11.7 does, the
//! logarithm is verified, and rho runs `--rho-runs` times on the same group.
//!
//! ```text
//! cargo run --release --example gaudry_quartic_la -- --sizes 269,521,769,1033 --seeds 2 --rho-runs 16 --json experiments/25_gaudry_quartic_la.json
//! ```

use std::env;
use std::fs;

use cryptanalysis_suite::cryptanalysis::gaudry_quartic::{run_k4_la, K4LaReport};

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let mut sizes: Vec<u64> = vec![269, 521, 769, 1033];
    let mut seeds = 2u64;
    let mut rho_runs = 16usize;
    let mut json: Option<String> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--sizes" => {
                i += 1;
                sizes = args[i]
                    .split(',')
                    .map(|v| v.parse().expect("--sizes"))
                    .collect();
            }
            "--seeds" => {
                i += 1;
                seeds = args[i].parse().expect("--seeds");
            }
            "--rho-runs" => {
                i += 1;
                rho_runs = args[i].parse().expect("--rho-runs");
            }
            "--json" => {
                i += 1;
                json = Some(args[i].clone());
            }
            other => panic!("unknown argument {other}"),
        }
        i += 1;
    }
    let mut rows: Vec<K4LaReport> = Vec::new();
    for &p in &sizes {
        for seed in 1..=seeds {
            let r = run_k4_la(p, seed, rho_runs);
            println!(
                "p={:>5} seed={} n=2^{:.1} |F|={:>4} | residuals {:>7} decomp {:>5} rate {:.4} (1/24 = 0.0417) | relations {:>5} core {:>4} φ {:.3} weight {:.2} | LA {:.3e} mod-n muls over {} attempts, /N² = {:.2} | rho S {:.3} ± {:.3} ({} runs, all correct: {}) | r = {:.3} | solved {} correct {} | {:.0} s",
                r.p, r.seed, r.bits, r.base, r.residuals, r.decompositions, r.decomposition_rate,
                r.relations, r.unknowns, r.phi, r.row_weight, r.la_ops as f64, r.la_attempts,
                r.wiedemann_constant, r.rho_s_mean, r.rho_s_sd, r.rho.len(),
                r.rho.iter().all(|x| x.correct), r.r, r.solved, r.correct, r.wall_ms / 1e3
            );
            rows.push(r);
            if let Some(path) = &json {
                fs::write(path, serde_json::to_string_pretty(&rows).unwrap()).expect("write json");
            }
        }
    }
}
