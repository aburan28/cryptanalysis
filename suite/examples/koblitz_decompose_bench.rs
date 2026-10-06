//! Wall-clock benchmark of the production Koblitz decomposition oracle
//! (`groebner_decompose` with the default engine) on fixed targets.
//!
//! Prints the wall time, the solver's counted statistics, the F4 stage
//! profile and a fingerprint of every decomposition found, so two
//! revisions can be compared for identical behaviour and counts.  Stage
//! diagnostic only (AGENTS.md §8): a wall-clock note, no end-to-end claim.
//!
//! ```text
//! cargo run --release --example koblitz_decompose_bench -- [a] [n] [targets] [m]
//! ```

use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    f4_profile, f4_profile_reset, SolverEngine,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base, groebner_decompose, KoblitzCurve,
};
use num_bigint::BigUint;
use serde_json::json;
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};

fn target_scalar(i: u32) -> BigUint {
    BigUint::from(1u64 + (i as u64).wrapping_mul(2_654_435_761) % 1_000_003)
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let a: u8 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(1);
    let n: u32 = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(17);
    let targets: u32 = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(8);
    let m: usize = args.get(4).and_then(|s| s.parse().ok()).unwrap_or(2);

    let kc = KoblitzCurve::new(a, n).expect("Koblitz curve");
    let fb = build_frobenius_factor_base(&kc, 0).expect("factor base");
    let index_of = fb.index_map();
    let st = cryptanalysis_suite::cryptanalysis::koblitz_groebner::FieldStructure::new(
        kc.n,
        &kc.curve.irreducible,
    );
    let g = kc.generator().clone();
    f4_profile_reset();
    let started = std::time::Instant::now();
    let mut h = DefaultHasher::new();
    let (mut found, mut reductions, mut refutations, mut propagations, mut splits) =
        (0u32, 0usize, 0usize, 0usize, 0usize);
    for i in 0..targets {
        let target = kc.mul(&g, &target_scalar(i));
        let (dec, stats) = groebner_decompose(
            &kc,
            &fb,
            &index_of,
            &st,
            &target,
            m,
            SolverEngine::default(),
            20_000,
        );
        dec.hash(&mut h);
        found += dec.is_some() as u32;
        reductions += stats.reductions;
        refutations += stats.infeasible_branches;
        propagations += stats.propagations;
        splits += stats.splits;
    }
    let wall_ms = started.elapsed().as_secs_f64() * 1e3;
    let p = f4_profile();
    println!(
        "{}",
        json!({
            "a": a, "n": n, "m": m, "targets": targets, "wall_ms": wall_ms,
            "found": found, "decompositions_fp": format!("{:016x}", h.finish()),
            "reductions": reductions, "refutations": refutations,
            "propagations": propagations, "splits": splits,
            "f4_calls": p.calls, "word_ops": p.word_ops,
            "specialise_word_ops": p.specialise_word_ops, "rows": p.rows, "cols": p.cols,
            "build_ms": p.build_ns as f64 / 1e6, "reduce_ms": p.reduce_ns as f64 / 1e6,
            "readback_ms": p.readback_ns as f64 / 1e6,
        })
    );
}
