//! Averaged refutation-degree (last-fall / PC-degree) sweep.
//!
//! Where `pc_degree_demo` reports one noisy `D*` per `n`, this demo
//! reports the `D*` *distribution* (min / mean / max + histogram) over a
//! batch of non-decomposable (unsatisfiable) targets per `n` — the stable
//! form that the proposal's prediction #1 actually talks about
//! (`research/notes/index-calculus/RESEARCH_FFD_PROOF_COMPLEXITY.md` §6): mean `D*` should climb with
//! `n` while the first-fall mean stays roughly flat.
//!
//! ```bash
//! cargo run --example pc_degree_avg_demo --release
//! ```

use cryptanalysis_suite::cryptanalysis::pc_degree_avg::{
    print_pc_avg_sweep, run_pc_avg_sweep, run_pc_operating_point_sweep, run_pc_regime_sweep,
};

fn main() {
    // 1) Default sweep: n' = ⌊n/2⌋ per n (the exactly/over-determined edge).
    println!("== [1] default sweep (n' = ⌊n/2⌋) ==");
    let rows = run_pc_avg_sweep(4..=8, 12, 64, 0x0FFD_A6DE);
    print_pc_avg_sweep(&rows);

    // 2) Determination-ratio regime sweep at fixed n: vary n' = 1..⌊n/2⌋ so
    //    ρ = n/(2n') sweeps from very over-determined down toward ρ ≈ 1.
    //    Isolates the effect of ρ on D* with the field held constant.
    println!("\n== [2] determination-ratio regime at fixed n = 10 ==");
    let regime = run_pc_regime_sweep(10, 14, 64, 0x0FFD_BE61);
    print_pc_avg_sweep(&regime);

    // 3) Operating-point scaling: grow n while holding 2n' just below n
    //    (margin = 1 ⇒ ρ ≳ 1). The asymptotic axis prediction #1 is about:
    //    does mean D* climb with n at fixed ρ ≈ 1?
    println!("\n== [3] operating-point scaling (margin = 1, ρ ≳ 1) ==");
    let opp = run_pc_operating_point_sweep(6..=12, 1, 16, 64, 0x0FFD_0BDE);
    print_pc_avg_sweep(&opp);
}
