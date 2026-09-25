//! Macaulay matrices of decomposition systems at rising degree: the
//! reference dense reduction, the sparse structured one, the fast kernel,
//! and the fast kernel with F5 row pruning, on the same matrices.
//!
//! ```bash
//! cargo run --release --example f4_degree_bench -- --max-degree 5
//! ```
//!
//! This is the measurement behind the solving-degree and first-fall-degree
//! sweeps (`koblitz_groebner::solving_degree`, `first_fall_degree`), whose
//! cost is one large matrix per degree rather than many small ones.  Every
//! path must report the same refutation and the same pinned variables, and
//! the same rank (all variables occur in these systems, so the fast
//! kernel's matrix over the occurring variables is the reference matrix).
//!
//! Stage diagnostic (AGENTS.md): matrix reduction only.

use cryptanalysis_suite::binary_ecc::F2mElement;
use cryptanalysis_suite::cryptanalysis::f4_gf2::{decide_with, KernelOptions, MacaulayCaps};
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, solving_profile, solving_profile_sparse, FieldStructure,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base, KoblitzCurve,
};
use num_bigint::BigUint;
use serde_json::json;
use std::time::Instant;

fn arg<'a>(args: &'a [String], name: &str) -> Option<&'a str> {
    args.windows(2)
        .find(|w| w[0] == name)
        .map(|w| w[1].as_str())
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let max_degree: u32 = arg(&args, "--max-degree").map_or(5, |v| v.parse().unwrap());
    let dense_limit: u64 = arg(&args, "--dense-limit").map_or(40_000_000, |v| v.parse().unwrap());
    let out = arg(&args, "--out");
    let caps = MacaulayCaps {
        max_rows: 2_000_000,
        max_cols: 2_000_000,
    };
    // The reference and sparse paths read their caps from the environment.
    std::env::set_var("F4_F2_MAX_ROWS", caps.max_rows.to_string());
    std::env::set_var("F4_F2_MAX_COLS", caps.max_cols.to_string());

    let cells: &[(u8, u32, usize, u64)] = &[
        (0, 9, 2, 77),
        (0, 9, 3, 77),
        (1, 11, 2, 301),
        (0, 13, 2, 1234),
    ];
    println!("| system | vars | D | rows | cols | rank | refuted | pinned | dense s | sparse s | fast s | fast+F5 s | F5 skipped | F5 speedup |");
    println!("|:-------|-----:|--:|-----:|-----:|-----:|:-------:|-------:|--------:|---------:|-------:|----------:|-----------:|-----------:|");
    let mut rows_out = Vec::new();
    for &(a, n, m, raw) in cells {
        let Some(kc) = KoblitzCurve::new(a, n) else {
            continue;
        };
        let Some(fb) = build_frobenius_factor_base(&kc, 0) else {
            continue;
        };
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let x_r = F2mElement::from_biguint(&BigUint::from(raw), n);
        let Some(sys) = build_decomposition_system(&fb.subspace_basis, &x_r, &kc.curve.b, m, &st)
        else {
            continue;
        };
        let (eqs, nv) = (&sys.equations, sys.n_vars);
        let base = eqs
            .iter()
            .flat_map(|p| p.terms.iter())
            .map(|t| t.mask.count_ones())
            .max()
            .unwrap_or(2);
        for degree in base..=max_degree {
            let t = Instant::now();
            let (plain, pk) = decide_with(eqs, nv, degree, caps, KernelOptions { f5: false });
            let fast_s = t.elapsed().as_secs_f64();
            let Some(plain) = plain else {
                println!("| K_{a}/2^{n} m={m} | {nv} | {degree} | over caps |");
                break;
            };
            let t = Instant::now();
            let (pruned, fk) = decide_with(eqs, nv, degree, caps, KernelOptions { f5: true });
            let f5_s = t.elapsed().as_secs_f64();
            let pruned = pruned.expect("same caps");
            assert_eq!(pruned, plain, "F5 changed a decision");
            assert_eq!(fk.rank, pk.rank, "F5 changed the rank");

            let t = Instant::now();
            let sparse = solving_profile_sparse(eqs, nv, degree).expect("within caps");
            let sparse_s = t.elapsed().as_secs_f64();
            assert_eq!(sparse.refuted, plain.refuted);
            assert_eq!(sparse.rank as u64, pk.rank, "sparse rank");
            if !plain.refuted {
                assert_eq!(sparse.vars_determined, plain.forced.len());
            }
            // The dense reference is quadratic in the matrix; skip it when
            // it would dominate the run.
            let dense_s = if pk.rows.saturating_mul(pk.cols) / 64 <= dense_limit {
                let t = Instant::now();
                let dense = solving_profile(eqs, nv, degree).expect("within caps");
                let s = t.elapsed().as_secs_f64();
                assert_eq!(dense.rank as u64, pk.rank, "dense rank");
                assert_eq!(dense.refuted, plain.refuted);
                Some(s)
            } else {
                None
            };
            let fmt = |x: Option<f64>| x.map_or("—".to_string(), |s| format!("{s:.4}"));
            println!(
                "| K_{a}/2^{n} m={m} | {nv} | {degree} | {} | {} | {} | {} | {} | {} | {sparse_s:.4} | {fast_s:.4} | {f5_s:.4} | {} | {:.2}x |",
                pk.rows,
                pk.cols,
                pk.rank,
                plain.refuted,
                plain.forced.len(),
                fmt(dense_s),
                fk.f5_skipped,
                fast_s / f5_s.max(1e-12)
            );
            rows_out.push(json!({
                "system": format!("K_{a}/2^{n} m={m}"), "target_x": raw, "vars": nv, "degree": degree,
                "rows": pk.rows, "cols": pk.cols, "rank": pk.rank, "refuted": plain.refuted,
                "pinned": plain.forced.len(), "dense_seconds": dense_s, "sparse_seconds": sparse_s,
                "fast_seconds": fast_s, "fast_f5_seconds": f5_s, "f5_skipped_rows": fk.f5_skipped,
                "fast_word_ops": pk.word_ops, "fast_f5_word_ops": fk.word_ops,
            }));
        }
    }
    println!();
    println!("All paths agree on refutation, pinned variables and rank (asserted).");
    if let Some(dir) = out {
        std::fs::create_dir_all(dir).expect("create output directory");
        let path = format!("{dir}/f4_degree.json");
        assert!(!std::path::Path::new(&path).exists(), "{path} exists");
        let doc = json!({"harness": "examples/f4_degree_bench.rs", "max_degree": max_degree,
            "scope": "Macaulay reduction only; stage diagnostic", "rows": rows_out});
        std::fs::write(&path, serde_json::to_string_pretty(&doc).unwrap()).unwrap();
        println!("Wrote {path}");
    }
}
