//! Where does the time go in a Semaev `S₄` solve?
//!
//! Timing each call would cost more than the calls do, so this counts
//! operations instead: clauses examined, literals walked, row XORs
//! performed.  Enough to tell which engine is hot.
//!
//! ```bash
//! cargo run --release --example semaev_profile
//! ```

use cryptanalysis_suite::binary_ecc::IrreduciblePoly;
use cryptanalysis_suite::cryptanalysis::sat::SolveResult;
use cryptanalysis_suite::cryptanalysis::semaev_corpus::CORPUS;
use cryptanalysis_suite::cryptanalysis::semaev_sat::{
    encode_semaev_s4_with, S4Options, XorEncoding,
};
use std::time::Instant;

fn main() {
    for family in ["n15l5", "n17l6", "n19l6"] {
        let mut agg = cryptanalysis_suite::cryptanalysis::sat::SolverStats::default();
        let mut secs = 0.0f64;
        let mut n = 0u64;
        for inst in CORPUS
            .iter()
            .filter(|c| c.name.starts_with(family) && c.truly_sat)
        {
            let irr: IrreduciblePoly = inst.irr();
            let mut enc = encode_semaev_s4_with(
                inst.n,
                inst.l,
                &irr,
                &inst.b(),
                &inst.x_r(),
                S4Options {
                    encoding: XorEncoding::Native,
                    break_symmetry: true,
                },
            );
            enc.solver.conflict_budget = 40_000_000;
            let t = Instant::now();
            assert_eq!(enc.solver.solve(), SolveResult::Sat, "{}", inst.name);
            secs += t.elapsed().as_secs_f64();
            let s = enc.solver.stats;
            agg.conflicts += s.conflicts;
            agg.decisions += s.decisions;
            agg.propagations += s.propagations;
            agg.xor_passes += s.xor_passes;
            agg.xor_repivots += s.xor_repivots;
            agg.xor_row_ops += s.xor_row_ops;
            agg.xor_row_scans += s.xor_row_scans;
            agg.xor_propagations += s.xor_propagations;
            agg.xor_reason_lits += s.xor_reason_lits;
            agg.clause_visits += s.clause_visits;
            agg.clause_lit_visits += s.clause_lit_visits;
            agg.analyze_lit_visits += s.analyze_lit_visits;
            agg.learnt_lits_raw += s.learnt_lits_raw;
            agg.learnt_lits_kept += s.learnt_lits_kept;
            agg.conflict_level_sum += s.conflict_level_sum;
            agg.max_level = agg.max_level.max(s.max_level);
            agg.ns_propagate_clauses += s.ns_propagate_clauses;
            agg.ns_propagate_xors += s.ns_propagate_xors;
            agg.ns_analyze += s.ns_analyze;
            agg.ns_minimize += s.ns_minimize;
            agg.ns_reduce_db += s.ns_reduce_db;
            n += 1;
        }
        let c = agg.conflicts.max(1) as f64;
        println!(
            "\n=== {family} · {n} instances · {secs:.1}s · {} conflicts ===",
            agg.conflicts
        );
        println!("  per conflict:");
        println!(
            "    decisions              {:>10.1}",
            agg.decisions as f64 / c
        );
        println!(
            "    propagations           {:>10.1}",
            agg.propagations as f64 / c
        );
        println!(
            "    clause visits          {:>10.1}",
            agg.clause_visits as f64 / c
        );
        println!(
            "    clause literal scans   {:>10.1}",
            agg.clause_lit_visits as f64 / c
        );
        println!(
            "    analyze literal walks  {:>10.1}",
            agg.analyze_lit_visits as f64 / c
        );
        println!(
            "    parity passes          {:>10.1}",
            agg.xor_passes as f64 / c
        );
        println!(
            "    parity row scans       {:>10.1}",
            agg.xor_row_scans as f64 / c
        );
        println!(
            "    parity re-pivots       {:>10.1}",
            agg.xor_repivots as f64 / c
        );
        println!(
            "    parity row XORs        {:>10.1}",
            agg.xor_row_ops as f64 / c
        );
        println!("  clause lengths:");
        println!(
            "    parity reason (mean)   {:>10.1}",
            agg.xor_reason_lits as f64 / agg.xor_propagations.max(1) as f64
        );
        println!(
            "    learnt before min      {:>10.1}",
            agg.learnt_lits_raw as f64 / c
        );
        println!(
            "    learnt after min       {:>10.1}",
            agg.learnt_lits_kept as f64 / c
        );
        println!("  search shape:");
        println!(
            "    mean level at conflict {:>10.1}",
            agg.conflict_level_sum as f64 / c
        );
        println!("    deepest level          {:>10}", agg.max_level);
        let tot = secs * 1e9;
        println!("  where the time goes:");
        for (name, ns) in [
            ("clause propagation", agg.ns_propagate_clauses),
            ("parity propagation", agg.ns_propagate_xors),
            ("conflict analysis", agg.ns_analyze),
            ("  of which minimize", agg.ns_minimize),
            ("clause forgetting", agg.ns_reduce_db),
        ] {
            println!(
                "    {name:<22} {:>8.1}%  ({:>6.1} µs/conflict)",
                ns as f64 / tot * 100.0,
                ns as f64 / 1000.0 / c
            );
        }
        let acct =
            (agg.ns_propagate_clauses + agg.ns_propagate_xors + agg.ns_analyze + agg.ns_reduce_db)
                as f64;
        println!(
            "    {:<22} {:>8.1}%",
            "unaccounted",
            (tot - acct) / tot * 100.0
        );
        println!("  µs per conflict          {:>10.1}", secs * 1e6 / c);
    }
}
