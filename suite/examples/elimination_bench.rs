//! Dense vs sparse Macaulay elimination, head to head.
//!
//! ```sh
//! F4_F2_MAX_ROWS=2000000 F4_F2_MAX_COLS=200000 \
//!   cargo run --release --example elimination_bench -- --n 5 --m 3 --d 6
//! ```

use cryptanalysis_suite::cryptanalysis::koblitz_bench::{
    elimination_comparison, sparse_elimination_cost,
};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let flag = |name: &str, default: u64| -> u64 {
        args.iter()
            .position(|a| a == name)
            .and_then(|i| args.get(i + 1))
            .and_then(|v| v.parse().ok())
            .unwrap_or(default)
    };
    let n = flag("--n", 5) as u32;
    let m = flag("--m", 3) as usize;
    let d = flag("--d", 6) as u32;
    let seed = flag("--seed", 0x5EED);

    // `--sparse-only`: time the sparse path alone, for cells where the dense
    // pass would never finish.  It prints the matrix and the cost, and
    // deliberately not whether the system resolved: a cost probe that also
    // reported a degree would be a measurement taken before its registration.
    if args.iter().any(|a| a == "--sparse-only") {
        match sparse_elimination_cost(n, 0, m, d, seed) {
            Some(c) => {
                println!("n={} m={} degree={} vars={}", c.n, c.m, c.degree, c.n_vars);
                println!(
                    "  matrix      {} rows x {} cols ({} high)",
                    c.rows, c.cols, c.high_cols
                );
                println!("  build       {:.1} ms", c.build_ms);
                println!("  sparse      {:.1} ms", c.sparse_ms);
                println!(
                    "  row weight  {} -> {} (cols = {})",
                    c.start_max_weight, c.max_weight, c.cols
                );
            }
            None => println!("cell unavailable (size caps or no invariant subspace)"),
        }
        return;
    }

    match elimination_comparison(n, 0, m, d, seed) {
        Some(c) => {
            println!("n={} m={} degree={} vars={}", c.n, c.m, c.degree, c.n_vars);
            println!(
                "  matrix      {} rows x {} cols ({} high)",
                c.rows, c.cols, c.high_cols
            );
            println!("  dense       {:.1} ms", c.dense_ms);
            println!("  sparse      {:.1} ms", c.sparse_ms);
            println!("  speedup     {:.2}x", c.ratio());
            println!(
                "  row weight  {} -> {} (cols = {})",
                c.start_max_weight, c.max_weight, c.cols
            );
            println!("  agree       {}", c.agree);
            if !c.agree {
                eprintln!("PATHS DISAGREE - the speedup is meaningless");
                std::process::exit(1);
            }
        }
        None => println!("cell unavailable (size caps or no invariant subspace)"),
    }
}
