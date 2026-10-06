//! **How fast can we reject a point?** — and is the SAT machinery
//! earning its keep at it?
//!
//! An index-calculus run tests many random points `R` and keeps the
//! rare one that decomposes over the factor base — roughly `1/m!` of
//! them for an `m`-point decomposition.  So most of an attack's time
//! goes on proving that a point does *not* decompose, and rejection
//! speed, not solve speed, is what decides whether the pipeline can
//! run the attack at all.
//!
//! Rejection is also the honest benchmark: proving unsatisfiability
//! means exhausting the space, so there is none of the trajectory luck
//! that makes satisfiable timings swing by an order of magnitude.
//!
//! The baseline to beat is embarrassingly simple — evaluate the
//! symmetrised `S₄` at every sorted triple of the factor base.  This
//! reports both, plus conflicts against the triple count, which says
//! whether the solver is *pruning* the space or merely walking it.
//!
//! ```bash
//! cargo run --release --example semaev_unsat
//! ```

use cryptanalysis_suite::cryptanalysis::sat::SolveResult;
use cryptanalysis_suite::cryptanalysis::semaev_corpus::CORPUS;
use cryptanalysis_suite::cryptanalysis::semaev_sat::{
    encode_semaev_s4_with, S4Options, XorEncoding,
};
use std::time::Instant;

fn main() {
    let budget: u64 = std::env::args()
        .nth(1)
        .and_then(|a| a.parse().ok())
        .unwrap_or(20_000_000);

    println!(
        "\n  {:<8} {:>3} {:>10} {:>11} {:>11} {:>8} {:>12} {:>10}",
        "family", "l", "triples", "SAT reject", "brute force", "ratio", "conflicts", "confl/tri"
    );
    for family in ["n15l5", "n17l6", "n19l6"] {
        let insts: Vec<_> = CORPUS
            .iter()
            .filter(|c| c.name.starts_with(family) && !c.truly_sat)
            .collect();
        if insts.is_empty() {
            continue;
        }
        let l = insts[0].l;
        let span = 1u64 << l;
        // Sorted triples with repetition from a set of `span` elements.
        let triples = span * (span + 1) * (span + 2) / 6;

        let mut sat_secs = 0.0f64;
        let mut conflicts = 0u64;
        let mut unfinished = 0u32;
        for inst in &insts {
            let mut enc = encode_semaev_s4_with(
                inst.n,
                inst.l,
                &inst.irr(),
                &inst.b(),
                &inst.x_r(),
                S4Options {
                    encoding: XorEncoding::Native,
                    break_symmetry: true,
                },
            );
            enc.solver.conflict_budget = budget;
            let t = Instant::now();
            let res = enc.solver.solve();
            sat_secs += t.elapsed().as_secs_f64();
            conflicts += enc.solver.stats.conflicts;
            match res {
                SolveResult::Unsat => {}
                SolveResult::Sat => panic!("{}: corpus label says unsatisfiable", inst.name),
                SolveResult::Unknown => unfinished += 1,
            }
        }

        let t = Instant::now();
        for inst in &insts {
            assert!(
                inst.decide_exhaustively().is_none(),
                "{}: brute force found a decomposition",
                inst.name
            );
        }
        let brute_secs = t.elapsed().as_secs_f64();

        let n = insts.len() as f64;
        let (sat_per, brute_per) = (sat_secs / n, brute_secs / n);
        println!(
            "  {family:<8} {l:>3} {triples:>10} {:>10.2}s {:>10.2}s {:>7.1}× {:>12.0} {:>10.2}",
            sat_per,
            brute_per,
            sat_per / brute_per,
            conflicts as f64 / n,
            conflicts as f64 / n / triples as f64
        );
        if unfinished > 0 {
            println!("           ({unfinished} instances hit the conflict budget)");
        }
    }
    println!(
        "\n  conflicts/triple ≈ 1 means the solver is walking the whole\n  \
         candidate space, one conflict per triple — not pruning it.\n"
    );
}
