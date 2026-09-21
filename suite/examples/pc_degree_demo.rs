//! Refutation-degree (last-fall / PC-degree) sweep on binary-Semaev PDP.
//!
//! Where `ffd_sweep_demo` measures the **first** fall degree of the
//! unrestricted `S₃` system, this demo measures the number that actually
//! decides security: the **refutation degree** `D*` of a genuinely
//! *unsatisfiable* (non-decomposable) point-decomposition instance,
//! restricted to a factor-base subspace `V` of dimension `n' = ⌊n/2⌋`.
//!
//! `D*` is — up to `O(1)` — the Huang–Kosters–Yeo last fall degree and
//! the Gröbner solving degree (Clegg–Edmonds–Impagliazzo). The proposal's
//! prediction #1 (`research/notes/index-calculus/RESEARCH_FFD_PROOF_COMPLEXITY.md` §6) is that `D*`
//! climbs with `n` while the first fall degree stays roughly flat.
//!
//! ```bash
//! cargo run --example pc_degree_demo --release
//! ```

use cryptanalysis_suite::cryptanalysis::pc_degree_harness::{print_pc_sweep, run_pc_sweep};

fn main() {
    // n' = ⌊n/2⌋ inside run_pc_sweep, so vars = 2n' = n (for even n).
    let rows = run_pc_sweep(4..=8, 12, 0x0FFD_DEC0);
    print_pc_sweep(&rows);

    let refuted = rows
        .iter()
        .filter(|r| r.refutation_degree.is_some())
        .count();
    println!(
        "Summary: {} of {} non-decomposable instances produced a refutation\n\
         within the degree budget.",
        refuted,
        rows.len()
    );
}
