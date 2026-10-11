//! Solving degree vs first fall degree on Koblitz decomposition systems.
//!
//! The Petit–Quisquater complexity argument for ECDLP over `F_{2^n}` is
//! stated in terms of the *first fall degree*, and assumes it tracks the
//! degree at which the system is actually solved.  Kosters–Yeo
//! (arXiv:1503.08001) show that assumption can fail.  This sweep measures
//! both quantities on the same systems, against a matched random control.
//!
//! ```sh
//! cargo run --release --example dreg_sweep
//! cargo run --release --example dreg_sweep -- --d-max 6 --trials 16
//! ```

use cryptanalysis_suite::cryptanalysis::koblitz_bench::{
    dreg_summary, format_dreg_table, subspace_ladder, DregSummary,
};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let flag = |name: &str, default: usize| -> usize {
        args.iter()
            .position(|a| a == name)
            .and_then(|i| args.get(i + 1))
            .and_then(|v| v.parse().ok())
            .unwrap_or(default)
    };
    let d_max = flag("--d-max", 5) as u32;
    let trials = flag("--trials", 8);
    let n_max = flag("--n-max", 21) as u32;
    let max_ell = flag("--max-ell", 12) as u32;
    let seed = flag("--seed", 0x5EED) as u64;
    let with_control = !args.iter().any(|a| a == "--no-control");
    let only_m = args
        .iter()
        .position(|a| a == "--m")
        .and_then(|i| args.get(i + 1))
        .map(|v| {
            v.split(',')
                .filter_map(|x| x.trim().parse::<usize>().ok())
                .collect::<Vec<_>>()
        })
        .unwrap_or_else(|| vec![2, 3]);

    println!("# Solving degree vs first fall degree");
    println!();
    println!("d_max = {d_max}, trials = {trials}, seed = {seed:#x}");
    println!();

    let mut rows: Vec<DregSummary> = Vec::new();
    for (n, ell) in subspace_ladder(n_max, max_ell) {
        for &m in &only_m {
            let started = std::time::Instant::now();
            if let Some(r) = dreg_summary(n, 0, m, d_max, trials, seed, with_control) {
                eprintln!(
                    "n={n} ell={ell} m={m}: vars={} refute={:?} ({:.1}s)",
                    r.n_vars,
                    r.refute_mean,
                    started.elapsed().as_secs_f64()
                );
                rows.push(r);
            }
        }
    }

    println!("{}", format_dreg_table(&rows));
    println!(
        "`gap` = D_solve − FFD.  `ctrl` is the mean solving degree of random\n\
         systems of identical shape; where it matches D_solve, the Semaev\n\
         structure is buying nothing.  `unres` counts draws that neither\n\
         resolved by `d_max` nor fit the Macaulay size caps."
    );
}
