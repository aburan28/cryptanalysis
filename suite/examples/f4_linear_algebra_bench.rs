//! Matched native S3 harness; identical source is built against both revisions.
use cryptanalysis_suite::{
    binary_ecc::F2mElement,
    cryptanalysis::{
        koblitz_groebner::{
            build_decomposition_system, matrix_f4_f2_counted, solve_boolean_system, FieldStructure,
            SolveOptions,
        },
        koblitz_index_calculus::find_irreducible,
    },
};
use num_bigint::BigUint;
use serde_json::json;
use std::time::Instant;

fn fe(x: u64, n: u32) -> F2mElement {
    F2mElement::from_biguint(&BigUint::from(x), n)
}

fn main() {
    let args: Vec<_> = std::env::args().collect();
    let n: u32 = args[1].parse().unwrap();
    let ell: usize = args[2].parse().unwrap();
    let m: usize = args[3].parse().unwrap();
    let fresh = args[4] == "fresh";
    let start = Instant::now();
    let st = FieldStructure::new(n, &find_irreducible(n).unwrap());
    let basis: Vec<_> = (0..ell).map(|k| fe(1 << k, n)).collect();
    let b = fe(if fresh { 3 } else { 1 }, n);
    println!(
        "{}",
        json!({"phase":"setup","field_setup_ns":start.elapsed().as_nanos()})
    );
    let count = if n <= 5 { 1u64 << n } else { 32 };
    for index in 0..count {
        let offset = if fresh && n > 5 { 32 } else { 0 };
        let r = ((index + offset) * 13 + 3) % (1u64 << n);
        let start = Instant::now();
        let sys = build_decomposition_system(&basis, &fe(r, n), &b, m, &st).unwrap();
        let encoding_ns = start.elapsed().as_nanos();
        let start = Instant::now();
        let (mut found, stats) = solve_boolean_system(
            &sys.equations,
            sys.n_vars,
            &SolveOptions {
                max_solutions: usize::MAX,
                node_budget: 100000,
                ..Default::default()
            },
        );
        let solver_ns = start.elapsed().as_nanos();
        found.sort_unstable();
        let start = Instant::now();
        let truth: Vec<_> = (0..1u64 << sys.n_vars)
            .filter(|&x| sys.equations.iter().all(|p| p.eval(x) == 0))
            .collect();
        let correct = found == truth && !stats.exhausted;
        let verification_ns = start.elapsed().as_nanos();
        let start = Instant::now();
        let (rows, xors) = matrix_f4_f2_counted(&sys.equations, sys.n_vars, 3).unwrap();
        let root_f4_ns = start.elapsed().as_nanos();
        println!(
            "{}",
            json!({"phase":"target","target":r,
            "input_hash":blake3::hash(&serde_json::to_vec(&sys).unwrap()).to_hex().to_string(),
            "output_hash":blake3::hash(&serde_json::to_vec(&rows).unwrap()).to_hex().to_string(),
            "encoding_ns":encoding_ns,"solver_ns":solver_ns,"verification_ns":verification_ns,
            "root_f4_ns":root_f4_ns,"root_word_xors":xors,"solutions":found,
            "reductions":stats.reductions,"exhausted":stats.exhausted,"correct":correct})
        );
        assert!(correct);
    }
}
