//! One large Boolean Macaulay matrix, built and decided once, with the
//! build and the elimination timed apart — the matrices that the
//! solving-degree sweeps and `f4_degree_bench` reach at high degree.
//!
//! ```bash
//! cargo run --release --example f4_matrix_bench -- --cell 0:13:2:1234 --degree 5
//! F4_F2_ECHELON=cuda cargo run --release --example f4_matrix_bench -- \
//!     --cell 0:13:2:1234 --degree 6 --out /tmp/k0n13d6.json        # on a GPU
//! ```
//!
//! `--cell a:n:m:x` is the decomposition system of the Koblitz curve
//! `K_a/2^n` for `m` summands at the target abscissa `x`, as in
//! `f4_degree_bench`; `--f5 0` turns F5 off.  The caps are raised to two
//! million rows and columns.  With `F4_F2_ECHELON` set, a matrix of at least
//! `F4_F2_ECHELON_MIN_WORDS` words is eliminated on that device and built
//! without F5's symbolic half (`f4_gf2::decide_with`).
//!
//! Stage diagnostic only: one oracle matrix, not an ECDLP cost.

use cryptanalysis_suite::binary_ecc::F2mElement;
use cryptanalysis_suite::cryptanalysis::f4_gf2::{decide_with, KernelOptions, MacaulayCaps};
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, FieldStructure,
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
    let cell: Vec<u64> = arg(&args, "--cell")
        .unwrap_or("0:13:2:1234")
        .split(':')
        .map(|v| v.parse().expect("--cell a:n:m:x"))
        .collect();
    assert_eq!(cell.len(), 4, "--cell a:n:m:x");
    let (a, n, m, raw) = (cell[0] as u8, cell[1] as u32, cell[2] as usize, cell[3]);
    let degree: u32 = arg(&args, "--degree").map_or(5, |v| v.parse().unwrap());
    let f5 = arg(&args, "--f5") != Some("0");
    let caps = MacaulayCaps {
        max_rows: 2_000_000,
        max_cols: 2_000_000,
    };

    let kc = KoblitzCurve::new(a, n).expect("no Koblitz curve at this degree");
    let fb = build_frobenius_factor_base(&kc, 0).expect("no factor base");
    let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
    let x_r = F2mElement::from_biguint(&BigUint::from(raw), n);
    let sys = build_decomposition_system(&fb.subspace_basis, &x_r, &kc.curve.b, m, &st)
        .expect("no decomposition system");
    let t = Instant::now();
    let (decision, k) = decide_with(
        &sys.equations,
        sys.n_vars,
        degree,
        caps,
        KernelOptions { f5 },
    );
    let wall = t.elapsed().as_secs_f64();
    let decision = decision.expect("over the raised caps");
    let backend = std::env::var("F4_F2_ECHELON").unwrap_or_else(|_| "host".into());
    println!(
        "K_{a}/2^{n} m={m} x={raw} D={degree} f5={f5} [{backend}]: {} x {} (eliminated {} rows), \
         rank {}, refuted {}, pinned {}; build {:.3} s, eliminate {:.3} s, total {:.3} s, \
         {:.3e} word XORs",
        k.rows,
        k.cols,
        k.eliminated_rows,
        k.rank,
        decision.refuted,
        decision.forced.len(),
        k.build_ns as f64 / 1e9,
        k.reduce_ns as f64 / 1e9,
        wall,
        k.word_ops as f64
    );
    println!("Stage diagnostic only: one oracle matrix, not an ECDLP cost.");
    if let Some(path) = arg(&args, "--out") {
        assert!(
            !std::path::Path::new(path).exists(),
            "{path} exists; reports are never overwritten"
        );
        let report = json!({
            "harness": "f4_matrix_bench",
            "scope": "one decomposition-system Macaulay matrix; stage diagnostic, not an ECDLP cost",
            "curve": format!("K_{a}/2^{n}"), "m": m, "target_x": raw, "degree": degree,
            "n_vars": sys.n_vars, "f5_requested": f5, "echelon_backend": backend,
            "echelon_min_words": std::env::var("F4_F2_ECHELON_MIN_WORDS").ok(),
            "rows": k.rows, "cols": k.cols, "eliminated_rows": k.eliminated_rows,
            "f5_skipped": k.f5_skipped, "rank": k.rank, "refuted": decision.refuted,
            "pinned": decision.forced.len(), "word_ops": k.word_ops,
            "build_seconds": k.build_ns as f64 / 1e9,
            "eliminate_seconds": k.reduce_ns as f64 / 1e9,
            "wall_seconds": wall,
        });
        std::fs::write(path, serde_json::to_string_pretty(&report).unwrap() + "\n")
            .expect("write report");
    }
}
