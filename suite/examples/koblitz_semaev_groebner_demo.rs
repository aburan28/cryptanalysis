//! The decomposition oracle behind the Koblitz-curve index calculus:
//! Semaev's `S₃` Weil-restricted to a Boolean system over the
//! Frobenius-invariant factor base, solved three ways — matrix-F4, CDCL
//! SAT, and exhaustive search as the reference.
//!
//! ```bash
//! cargo run --release --example koblitz_semaev_groebner_demo
//! ```

use cryptanalysis_suite::binary_ecc::BinaryPoint;
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, matrix_f4_f2, FieldStructure, SolverEngine,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base, enumerate_decompose, groebner_decompose,
    koblitz_index_calculus_dlp, sat_decompose, DecompositionStrategy, KoblitzCurve,
    KoblitzIcOptions,
};
use num_bigint::BigUint;
use std::time::Instant;

fn main() {
    let kc = KoblitzCurve::new(0, 9).expect("K_0 over F_2^9");
    let fb = build_frobenius_factor_base(&kc, 0).expect("factor base");
    let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
    let index_of = fb.index_map();
    let g = kc.generator().clone();

    println!();
    println!("=== The system: S₃ = 0 over the invariant subspace, K_0 / F_2^9 ===");
    println!();
    let target = kc.mul(&g, &BigUint::from(53u32));
    let x_r = match &target {
        BinaryPoint::Affine { x, .. } => x.clone(),
        BinaryPoint::Infinity => unreachable!(),
    };
    let sys = build_decomposition_system(&fb.subspace_basis, &x_r, &kc.curve.b, 2, &st).unwrap();
    let max_deg = sys
        .equations
        .iter()
        .flat_map(|e| e.terms.iter())
        .map(|t| t.mask.count_ones())
        .max()
        .unwrap();
    println!("factor base                 : |F| = {}", fb.points.len());
    println!(
        "invariant subspace          : dim ℓ = {}, |V| = {}",
        fb.ell,
        fb.subspace.len()
    );
    println!("unknowns (2 summands × ℓ)   : {}", sys.n_vars);
    println!("equations (Weil restriction): {}", sys.equations.len());
    println!(
        "degree of the system        : {max_deg}  (m = 2; squaring is F_2-linear.  \
         The chained m ≥ 3 system is cubic.)"
    );
    println!();
    for d in 2..=4u32 {
        let t = Instant::now();
        let rows = matrix_f4_f2(&sys.equations, sys.n_vars, d).unwrap();
        println!(
            "  matrix-F4 at degree {d}: {:>4} reduced rows in {:>8.2?}",
            rows.len(),
            t.elapsed()
        );
    }

    println!();
    println!("=== Decomposition: three oracles on the same system ===");
    println!();
    println!(
        "{:>5}  {:>12}  {:>12}  {:>12}  {:>12}",
        "[k]G", "search", "matrix-F4", "SAT", "verdict"
    );
    for k in [3u32, 17, 53, 101] {
        let target = kc.mul(&g, &BigUint::from(k));
        let t = Instant::now();
        let by_search = enumerate_decompose(&kc, &fb, &index_of, &target, 2);
        let t_search = t.elapsed();
        let t = Instant::now();
        let (by_algebra, _) = groebner_decompose(
            &kc,
            &fb,
            &index_of,
            &st,
            &target,
            2,
            SolverEngine::default(),
            20_000,
        );
        let t_alg = t.elapsed();
        let t = Instant::now();
        let (by_sat, sat_stats) = sat_decompose(&kc, &fb, &index_of, &st, &target, 2, 64, Some(2));
        let t_sat = t.elapsed();
        assert_eq!(sat_stats.spurious, 0);
        let all = [by_search.is_some(), by_algebra.is_some(), by_sat.is_some()];
        println!(
            "{:>5}  {:>12.2?}  {:>12.2?}  {:>12.2?}  {:>12}",
            k,
            t_search,
            t_alg,
            t_sat,
            if all.iter().all(|v| *v) {
                "all: yes"
            } else if all.iter().all(|v| !*v) {
                "all: no"
            } else {
                "DISAGREE"
            }
        );
    }

    println!();
    println!("=== Refuting a target without searching ===");
    println!();
    // K_0/F_2^7 has a one-point factor base: nothing decomposes, and the
    // algebra says so from the Macaulay matrix alone.
    let small = KoblitzCurve::new(0, 7).unwrap();
    let small_fb = build_frobenius_factor_base(&small, 0).unwrap();
    let small_idx = small_fb.index_map();
    let small_st = FieldStructure::new(small.n, &small.curve.irreducible);
    let sg = small.generator().clone();
    let mut certified = 0;
    let mut splits = 0;
    let mut sat_refuted = 0;
    for k in 1..29u32 {
        let target = small.mul(&sg, &BigUint::from(k));
        let (out, stats) = groebner_decompose(
            &small,
            &small_fb,
            &small_idx,
            &small_st,
            &target,
            2,
            SolverEngine::default(),
            20_000,
        );
        assert!(out.is_none());
        certified += usize::from(stats.infeasible_branches > 0);
        splits += stats.splits;
        let (sat_out, sat_stats) = sat_decompose(
            &small,
            &small_fb,
            &small_idx,
            &small_st,
            &target,
            2,
            64,
            Some(2),
        );
        assert!(sat_out.is_none());
        sat_refuted += usize::from(sat_stats.refuted);
    }
    println!(
        "K_0 / F_2^7, |F| = {}: none of the {} targets decomposes.",
        small_fb.points.len(),
        28
    );
    println!("  refuted by an F4 certificate : {certified}/28");
    println!("  refuted by SAT (UNSAT)       : {sat_refuted}/28");
    println!("  F4 branches searched         : {splits}");

    println!();
    println!("=== End to end, all three oracles ===");
    println!();
    let d = BigUint::from(53u32);
    let q = kc.mul(&g, &d);
    for (label, strategy) in [
        ("matrix-F4 (Semaev)", DecompositionStrategy::Groebner),
        ("CDCL SAT (Semaev) ", DecompositionStrategy::Sat),
        ("exhaustive search ", DecompositionStrategy::Enumerate),
    ] {
        let opts = KoblitzIcOptions {
            strategy,
            ..KoblitzIcOptions::default()
        };
        let t = Instant::now();
        let rep = koblitz_index_calculus_dlp(&kc, &q, &opts).unwrap();
        println!(
            "{label}  log = {:>4}  relations = {:>2}  F4 reductions = {:>4}  SAT calls = {:>4}  {:>9.2?}",
            rep.log.as_ref().map(|v| v.to_string()).unwrap_or_else(|| "—".into()),
            rep.relations,
            rep.reductions,
            rep.sat_calls,
            t.elapsed()
        );
    }
    println!();
    println!("Same logarithm from all three oracles.  At these sizes exhaustive search");
    println!("is still faster in wall-clock terms — |F| is a few dozen points, so");
    println!("|F|^(m−1) is nothing, while the Macaulay matrix has thousands of");
    println!("columns.  What the algebra buys is the scaling: its cost follows the");
    println!("degree of regularity of the system, not |F|, and it refutes a target");
    println!("outright instead of failing to find something.");
    println!();
}
