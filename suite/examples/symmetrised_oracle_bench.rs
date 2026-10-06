//! Paired decomposition-oracle benchmark: the production `x`-system against
//! the symmetrised Artin–Schreier-frame system, on the same curve and the
//! same invariant subspace, with every verdict gated by enumeration.
//!
//! ```bash
//! cargo run --release --example symmetrised_oracle_bench                 # ladder n = 9, 15, 17 (m = 2, 3) and n = 23 (m = 2)
//! cargo run --release --example symmetrised_oracle_bench -- --full       # also n = 23 at m = 3 (long)
//! cargo run --release --example symmetrised_oracle_bench -- --only 1 15 3 --direct-all --no-sat --targets 4
//! cargo run --release --example symmetrised_oracle_bench -- --only 1 23 3 --node-budget 20000 --conflict-budget 200000
//! ```
//!
//! An arm that exhausts its node or conflict budget on a target reports it
//! as inconclusive rather than running for hours; the budgets are printed.
//!
//! `n` must be prime: for composite `n` the group order is divisible by
//! the orders of the subfield curves and no prime-order subgroup exceeds
//! its cofactor, so `KoblitzCurve::new` refuses it (`n = 21` is out).
//!
//! Columns: Boolean unknowns / equations / degree of the arm's system;
//! found / refuted / inconclusive targets (mixes differ between the two
//! bases, so medians are split by verdict and never compared across
//! regimes); `via T` = relations that lifted through `R + T`; median
//! milliseconds per verdict; median effort (F4 splits or SAT conflicts);
//! first fall degree; and the enumeration gate.

use cryptanalysis_suite::cryptanalysis::koblitz_symmetrised::{
    format_paired, paired_bench, PairedOptions,
};
use std::time::Instant;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let flag = |f: &str| args.iter().any(|a| a == f);
    let value = |f: &str| {
        args.iter()
            .position(|a| a == f)
            .and_then(|i| args.get(i + 1))
            .and_then(|v| v.parse::<usize>().ok())
    };
    let full = flag("--full");
    let mut opts = PairedOptions::default();
    if let Some(t) = value("--targets") {
        opts.targets = t;
    }
    if flag("--no-sat") {
        opts.sat = false;
    }
    if flag("--no-direct") {
        opts.direct_x = false;
    }
    if flag("--no-x") {
        opts.chained_x = false;
    }
    if flag("--whole-group") {
        opts.targets_in_subgroup = false;
    }
    let direct_all = flag("--direct-all");
    if let Some(b) = value("--node-budget") {
        opts.node_budget = b;
    }
    if let Some(d) = value("--f4-degree") {
        opts.f4_max_degree = d as u32;
    }
    if let Some(c) = value("--conflict-budget") {
        opts.conflict_budget = c as u64;
    }
    // --only a n m: run a single instance.
    let only: Option<(u8, u32, usize)> = args.iter().position(|a| a == "--only").and_then(|i| {
        Some((
            args.get(i + 1)?.parse().ok()?,
            args.get(i + 2)?.parse().ok()?,
            args.get(i + 3)?.parse().ok()?,
        ))
    });

    println!("=== Paired oracle benchmark: x-system vs symmetrised system ===");
    println!(
        "targets = {}, node budget = {}, SAT conflict budget = {}, targets in <G> = {}",
        opts.targets, opts.node_budget, opts.conflict_budget, opts.targets_in_subgroup
    );
    println!();

    let mut ladder: Vec<(u8, u32, usize)> = vec![
        (0, 9, 2),
        (1, 9, 2),
        (0, 9, 3),
        (1, 9, 3),
        (0, 15, 2),
        (1, 15, 2),
        (0, 15, 3),
        (1, 15, 3),
        (0, 17, 2),
        (1, 17, 2),
        (0, 17, 3),
        (1, 17, 3),
        (0, 23, 2),
        (1, 23, 2),
    ];
    if full {
        ladder.push((0, 23, 3));
        ladder.push((1, 23, 3));
    }
    if let Some(one) = only {
        ladder = vec![one];
    }
    for (a, n, m) in ladder {
        let t0 = Instant::now();
        // The direct x-S4 arm is Boolean degree 7; past n = 9 its Macaulay
        // matrices exceed the engine's limits and it only splits.  Keep it
        // where it can finish.
        let mut o = opts.clone();
        if n > 9 && !direct_all {
            o.direct_x = false;
        }
        match paired_bench(a, n, m, &o) {
            Some(b) => {
                print!("{}", format_paired(&b));
                println!(
                    "   divisor indices {:?}  ({:.1} s)",
                    b.divisor,
                    t0.elapsed().as_secs_f64()
                );
            }
            None => println!("== K_{a}/F_2^{n} m = {m}: no instance (dimension or size limit)"),
        }
        println!();
    }
}
