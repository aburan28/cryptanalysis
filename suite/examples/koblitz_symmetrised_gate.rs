//! **X4′: the symmetrised oracle against the `x`-chained oracle and
//! enumeration, on one non-invariant `V ∋ 1` per rung.**
//!
//! Companion to §X4′ of `research/notes/ecc2k130/RESEARCH_ECC2K130_ROUTE_TARGETS.md`,
//! which registered the rungs, `l`, the targets, the engine, the caps, the
//! budget and the verdict rules before this driver existed.
//!
//! ```text
//! cargo run --release --example koblitz_symmetrised_gate -- --rungs 13,15,19,23 --targets 16 --x-caps 3 --json experiments/26_koblitz_symmetrised_gate.json
//! ```
//!
//! `l = ⌈(n + log₂ 6)/3⌉`, E1's factor-base dimension at `m = 3`.  Each rung
//! is written to the JSON as soon as it finishes.

use std::env;
use std::fs;

use cryptanalysis_suite::cryptanalysis::koblitz_symmetrised::{
    subspace_gate_bench, GateBench, GateOptions,
};

fn main() {
    // The registered engine is the default one: every knob that changes what
    // it builds, reuses or counts must be unset.
    for var in [
        "IC_REDUCTION_CACHE",
        "KIC_F4_INHERIT",
        "SOLVER_SPLIT_RULE",
        "KIC_F4_MAX_DEGREE_ONLY",
        "KIC_F4_CLOSURE_ROUNDS",
        "KIC_F4_SOLVER_FULL_READBACK",
        "F4_F2_MAX_ROWS",
        "F4_F2_MAX_COLS",
    ] {
        assert!(
            env::var(var).is_err(),
            "the registered run needs {var} unset"
        );
    }
    let args: Vec<String> = env::args().skip(1).collect();
    let mut rungs: Vec<u32> = vec![13, 15, 19, 23];
    let mut opts = GateOptions {
        targets: 16,
        seed: 0x5EED_0004,
        node_budget: 20_000,
        x_caps: vec![3],
    };
    let mut json: Option<String> = None;
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
            "--targets" => {
                i += 1;
                opts.targets = args[i].parse().expect("--targets");
            }
            "--seed" => {
                i += 1;
                opts.seed = args[i].parse().expect("--seed");
            }
            "--node-budget" => {
                i += 1;
                opts.node_budget = args[i].parse().expect("--node-budget");
            }
            "--x-caps" => {
                i += 1;
                opts.x_caps = args[i]
                    .split(',')
                    .map(|v| v.parse().expect("--x-caps"))
                    .collect();
            }
            "--json" => {
                i += 1;
                json = Some(args[i].clone());
            }
            other => panic!("unknown argument {other}"),
        }
        i += 1;
    }
    let mut rows: Vec<GateBench> = Vec::new();
    for &n in &rungs {
        let l = ((n as f64 + 6f64.log2()) / 3.0).ceil() as usize;
        let b = subspace_gate_bench(0, n, l, &opts).expect("rung builds");
        let k = b.targets as f64;
        let e: Vec<String> = b
            .enumeration
            .iter()
            .map(|e| {
                let full = e.full_steps as f64 * k * e.gae_per_step / e.decompositions_total as f64;
                let first = e.first_hit_steps_total as f64 * e.gae_per_step / e.decomposable as f64;
                format!(
                    "{}: |F| {} decomposable {}/{} ({:.2} each) {:.2} GAE/step | GAE per relation: full {:.0}, first-hit {:.0}",
                    e.base, e.points, e.decomposable, b.targets, e.mean_decompositions, e.gae_per_step,
                    full, first
                )
            })
            .collect();
        println!(
            "K_0/F_2^{n} l={l} | {:.1} ns/add, {:.4} GAE/word XOR (in rref {:.4}) | {}",
            b.ns_per_add,
            b.gae_per_word_xor,
            b.ns_per_word_xor_in_rref / b.ns_per_add,
            e.join(" | ")
        );
        for a in &b.arms {
            println!(
                "   {:<12} cap {} vars {:>2} deg {} | found {:>2} refuted {:>2} budget {:>2} gate failures {} | word XORs mean {:.3e} (found {:.3e}, refuted {:.3e}) | GAE per relation {:.0} | splits {:.1} | {:.1} ms | built {} oversize {}",
                a.arm, a.cap, a.n_vars, a.degree, a.found, a.refuted, a.budget, a.gate_failures,
                a.mean_word_xors, a.median_found_word_xors, a.median_refuted_word_xors,
                a.mean_word_xors * k * b.gae_per_word_xor / a.found as f64,
                a.mean_splits, a.mean_ms, a.built_degree, a.oversize_targets
            );
        }
        rows.push(b);
        if let Some(path) = &json {
            fs::write(path, serde_json::to_string_pretty(&rows).unwrap()).expect("write json");
        }
    }
}
