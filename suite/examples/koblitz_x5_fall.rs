//! **X5′: the first fall degree of the symmetrised `S₃` chained at `m = 4`,
//! paired with the `x`-chained `m = 4` system, against H1.**
//!
//! Companion to §X5′ of `research/notes/ecc2k130/RESEARCH_ECC2K130_ROUTE_TARGETS.md`,
//! which registered the rungs, `ℓ`, the draws, `d_max`, `V`, the cross-check
//! and the one solve before this driver existed.
//!
//! ```text
//! cargo run --release --example koblitz_x5_fall -- --json experiments/27_koblitz_x5_fall.json
//! ```
//!
//! Each rung is written to the JSON as soon as it finishes.

use std::env;
use std::fs;

use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::all_factors_of_x_n_minus_1;
use cryptanalysis_suite::cryptanalysis::koblitz_symmetrised::{
    x5_fall_rung, x5_solve_gate, X5Rung, X5Solve,
};
use serde::Serialize;

#[derive(Serialize)]
struct Report {
    /// `F4_F2_MAX_ROWS` / `F4_F2_MAX_COLS` when raised (`--allow-raised-caps`):
    /// an unregistered supplement that removes the censoring, never the
    /// registered run.
    raised_caps: Option<(String, String)>,
    rungs: Vec<X5Rung>,
    cross_check: Option<X5Rung>,
    solve: Option<X5Solve>,
}

fn print_rung(tag: &str, r: &X5Rung) {
    for a in &r.arms {
        let f = |v: Option<u32>| v.map(|d| d.to_string()).unwrap_or_else(|| "—".into());
        println!(
            "{tag} n={:>2} ℓ={} {:<17} vars {:>2} eqs {:>2} deg {} | FFD min {} max {} no fall {}/{} censored {} | deficit {:?} | {:.0} ms",
            r.n, r.ell, a.arm, a.n_vars, a.n_eqs, a.degree, f(a.fall_min), f(a.fall_max), a.no_fall,
            r.draws, a.censored, a.mean_deficit, a.ms
        );
    }
}

fn main() {
    // The registered engine and matrices are the defaults: every knob that
    // changes what is built or counted must be unset.  The one exception is
    // the size caps under `--allow-raised-caps`, recorded in the output.
    let raised = env::args().any(|a| a == "--allow-raised-caps");
    let caps = ["F4_F2_MAX_ROWS", "F4_F2_MAX_COLS"];
    for var in [
        "F4_F2_MAX_ROWS",
        "F4_F2_MAX_COLS",
        "IC_REDUCTION_CACHE",
        "KIC_F4_INHERIT",
        "SOLVER_SPLIT_RULE",
        "KIC_F4_MAX_DEGREE_ONLY",
    ] {
        if raised && caps.contains(&var) {
            continue;
        }
        assert!(
            env::var(var).is_err(),
            "the registered run needs {var} unset"
        );
    }
    let args: Vec<String> = env::args().skip(1).collect();
    let mut rungs: Vec<u32> = vec![9, 11, 13, 15, 17, 19];
    let mut draws = 16usize;
    let mut d_max = 4u32;
    let mut seed = 0x5EED_0005u64;
    let mut json: Option<String> = None;
    let mut skip_extras = false;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--rungs" => {
                i += 1;
                rungs = args[i]
                    .split(',')
                    .map(|v| v.parse().expect("--rungs"))
                    .collect();
            }
            "--draws" => {
                i += 1;
                draws = args[i].parse().expect("--draws");
            }
            "--d-max" => {
                i += 1;
                d_max = args[i].parse().expect("--d-max");
            }
            "--seed" => {
                i += 1;
                seed = args[i].parse().expect("--seed");
            }
            "--json" => {
                i += 1;
                json = Some(args[i].clone());
            }
            "--rungs-only" => skip_extras = true,
            "--allow-raised-caps" => {}
            other => panic!("unknown argument {other}"),
        }
        i += 1;
    }
    let ell = |n: u32| ((n as f64 + 24f64.log2()) / 4.0).ceil() as usize;
    let mut report = Report {
        raised_caps: raised.then(|| {
            (
                env::var(caps[0]).unwrap_or_default(),
                env::var(caps[1]).unwrap_or_default(),
            )
        }),
        rungs: Vec::new(),
        cross_check: None,
        solve: None,
    };
    let write = |r: &Report| {
        if let Some(path) = &json {
            fs::write(path, serde_json::to_string_pretty(r).unwrap()).expect("write json");
        }
    };
    for &n in &rungs {
        let r = x5_fall_rung(n, ell(n), draws, d_max, seed, None).expect("rung builds");
        print_rung("rung", &r);
        report.rungs.push(r);
        write(&report);
    }
    if skip_extras {
        return;
    }
    // Cross-check: n = 15, the invariant V = ker (x + 1)(x⁴ + x + 1).
    let factors = all_factors_of_x_n_minus_1(15);
    let idx: Vec<usize> = [0b11u64, 0b10011]
        .iter()
        .map(|f| {
            factors
                .iter()
                .position(|g| g == f)
                .expect("factor of x^15 - 1")
        })
        .collect();
    let c = x5_fall_rung(15, 5, draws, d_max, seed, Some(&idx)).expect("cross-check builds");
    print_rung("cross-check (invariant V)", &c);
    report.cross_check = Some(c);
    write(&report);
    // The one solve: K₁/F₂¹¹, 16 subgroup targets, against 4-sum enumeration.
    let s = x5_solve_gate(1, 11, ell(11), 16, 20_000, seed).expect("solve builds");
    println!(
        "solve K_1/F_2^11 ℓ={} |F_u|={} | found {} refuted {} budget {} (decomposable {}/{}) gate failures {} | splits {:.1} word XORs {:.3e} {:.1} ms",
        s.ell, s.points, s.found, s.refuted, s.budget, s.decomposable, s.targets, s.gate_failures, s.mean_splits,
        s.mean_word_xors, s.mean_ms
    );
    report.solve = Some(s);
    write(&report);
}
