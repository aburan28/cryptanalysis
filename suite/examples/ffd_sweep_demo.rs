//! FFD measurement sweep on binary-Semaev `S₃` systems.
//!
//! Runs the harness for `n ∈ {3..=7}` and prints the Macaulay-matrix
//! rank vs. the generic-system prediction at each degree, and reports
//! the first fall degree (smallest `D` where actual rank exceeds the
//! generic prediction).
//!
//! ```bash
//! cargo run --example ffd_sweep_demo --release
//! ```

use cryptanalysis_suite::cryptanalysis::ffd_harness::{print_sweep, run_sweep};

fn main() {
    let rows = run_sweep(3..=7, 4, 0x0FFD_DEAD);
    print_sweep(&rows);

    // Summary: number of curves with an observed fall.
    let with_fall = rows.iter().filter(|r| r.fall_degree.is_some()).count();
    println!(
        "Summary: {} of {} systems showed a fall-signal in D ≤ 4.",
        with_fall,
        rows.len()
    );
}
