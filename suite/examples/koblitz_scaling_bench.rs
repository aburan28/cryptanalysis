//! Baseline measurements for the Koblitz index-calculus scaling target.
//!
//! ```bash
//! cargo run --release --example koblitz_scaling_bench           # tables
//! cargo run --release --example koblitz_scaling_bench -- --json # machine-readable
//! ```
//!
//! See `research/notes/ecc2k130/RESEARCH_KOBLITZ_SCALING_TARGET.md` for what the numbers are
//! for and which of them a run is trying to move.

use cryptanalysis_suite::cryptanalysis::koblitz_bench::{
    bench_instance, format_ffd_table, format_oracle_table, max_m_within_budget, n_vars_for,
    subspace_ladder, sweep_ffd, sweep_systems, to_json,
};

fn main() {
    let json = std::env::args().any(|a| a == "--json");

    // Structure: no curve needed, so this runs far past MAX_N.
    let ladder = subspace_ladder(63, 6);
    let ns: Vec<u32> = ladder.iter().map(|(n, _)| *n).collect();
    let systems = sweep_systems(&ns, &[2, 3, 4], 3, 0x5EED);
    // The fall degree depends on the target draw, so average it.
    let ffd = sweep_ffd(&ns, &[2, 3, 4], 3, 0x5EED, 16);

    // Oracle cost: needs a curve with a prime-order subgroup.
    let mut oracles = Vec::new();
    for (a, n, m) in [
        (0u8, 7u32, 2usize),
        (1, 7, 2),
        (0, 9, 2),
        (1, 9, 2),
        (0, 9, 3),
        // K_1/F_2^15 at m = 3 mostly refutes, so the sweep covers both
        // regimes: finding a decomposition and proving there is none.
        (1, 15, 3),
    ] {
        if let Some(b) = bench_instance(a, n, 0, m, 8, 0xB0B, 20_000, 8, Some(2)) {
            oracles.push(b);
        }
    }

    if json {
        println!("{}", to_json(&systems, &oracles));
        return;
    }

    println!();
    println!("=== The ladder: n with a small Frobenius-invariant subspace ===");
    println!();
    println!(
        "{:>4} {:>4} {:>8} {:>10}",
        "n", "ℓ", "|V| = 2^ℓ", "m at 64 vars"
    );
    for (n, ell) in &ladder {
        println!(
            "{:>4} {:>4} {:>8} {:>10}",
            n,
            ell,
            1u64 << ell,
            max_m_within_budget(*n, *ell, 64)
                .map(|m| m.to_string())
                .unwrap_or_else(|| "—".into())
        );
    }

    println!();
    println!("=== System structure and first fall degree (16 target draws each) ===");
    println!();
    print!("{}", format_ffd_table(&ffd));

    println!();
    println!("=== Unknowns: m·ℓ subspace coordinates + (m−2)·n chaining ===");
    println!();
    println!(
        "{:>4} {:>4} {:>7} {:>7} {:>7} {:>7}",
        "n", "ℓ", "m=2", "m=3", "m=4", "m≈n/ℓ"
    );
    for (n, ell) in &ladder {
        let m_useful = (*n as f64 / *ell as f64).ceil() as usize;
        println!(
            "{:>4} {:>4} {:>7} {:>7} {:>7} {:>7}",
            n,
            ell,
            n_vars_for(*n, *ell, 2),
            n_vars_for(*n, *ell, 3),
            n_vars_for(*n, *ell, 4),
            n_vars_for(*n, *ell, m_useful.max(2)),
        );
    }

    println!();
    println!("=== Oracle cost on solvable instances (8 targets each) ===");
    println!();
    print!("{}", format_oracle_table(&oracles));
    let bad: usize = oracles.iter().map(|b| b.disagreements).sum();
    println!();
    println!("oracle disagreements across every instance: {bad}  (must be 0)");
    println!();
}
