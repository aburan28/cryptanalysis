//! **`C₄`: one `S₅` solve over `F_{p⁴}`, measured.**
//!
//! Companion to `cryptanalysis_suite::cryptanalysis::gaudry_quartic` and §11.16–11.17
//! of `research/notes/index-calculus/RESEARCH_RESIDUAL_WALKS.md`.
//!
//! ```text
//! # scaling of the same solver on generic planted systems, degree d = 2..7
//! cargo run --release --example gaudry_quartic_c4 -- --generic 2,3,4,5,6,7 --json experiments/24_gaudry_quartic_generic.json
//! # the registered measurement: a constructed residual, then random ones
//! cargo run --release --example gaudry_quartic_c4 -- --p 269 --seed 1 --residuals 3 --json experiments/24_gaudry_quartic_c4.json
//! ```
//!
//! Every solve of the second form is checked against the meet-in-the-middle
//! oracle, and the constructed residual must return its planted
//! decomposition.

use std::collections::HashMap;
use std::env;
use std::fs;
use std::time::Instant;

use cryptanalysis_suite::cryptanalysis::gaudry_quartic::{
    base_quadruples, factor_base, mitm_decompositions, solve_s5_subspace, solve_system4, Curve4,
    Pt4, QuarticSolve, SymmetrisedS5,
};
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use serde::Serialize;

#[derive(Serialize)]
struct GenericRow {
    equation_degree: u8,
    solve: QuarticSolve,
    planted_found: bool,
}

#[derive(Serialize)]
struct ResidualRow {
    index: usize,
    constructed: bool,
    solve: QuarticSolve,
    solver_quadruples: Vec<[u64; 4]>,
    oracle_quadruples: Vec<[u64; 4]>,
    agree: bool,
    planted_found: Option<bool>,
}

#[derive(Serialize)]
struct Report {
    p: u64,
    seed: u64,
    base: usize,
    fp_muls_per_add: f64,
    precompute_muls: u64,
    precompute_ms: f64,
    residuals: Vec<ResidualRow>,
}

fn generic(d: u8, seed: u64) -> GenericRow {
    let p = 269u64;
    let mut rng = StdRng::seed_from_u64(seed);
    let root: [u64; 4] = std::array::from_fn(|_| rng.gen_range(0..p));
    let mut monos = Vec::new();
    for a in 0..=d {
        for b in 0..=(d - a) {
            for c in 0..=(d - a - b) {
                for e in 0..=(d - a - b - c) {
                    monos.push([a, b, c, e]);
                }
            }
        }
    }
    let eval = |c: &HashMap<[u8; 4], u64>| -> u64 {
        c.iter().fold(0u64, |acc, (m, &k)| {
            let mut t = k;
            for i in 0..4 {
                for _ in 0..m[i] {
                    t = t * root[i] % p;
                }
            }
            (acc + t) % p
        })
    };
    let comps: Vec<HashMap<[u8; 4], u64>> = (0..4)
        .map(|_| {
            let mut c: HashMap<[u8; 4], u64> =
                monos.iter().map(|m| (*m, rng.gen_range(0..p))).collect();
            let v = eval(&c);
            let e = c.entry([0, 0, 0, 0]).or_insert(0);
            *e = (*e + p - v) % p;
            c
        })
        .collect();
    let mut st = QuarticSolve::default();
    let sols = solve_system4(&comps, d, 4 * (d - 1) + 1, p, &mut rng, &mut st, true);
    let planted_found = sols.as_ref().is_some_and(|s| s.contains(&root));
    println!(
        "generic d={d}: cols {:>6} rows {:>6} dim {:>5} | C = {:.3e} (echelon {:.3e}, nf {:.3e}, charpoly {:.3e}, eigen {:.3e}, roots {:.3e}) | planted {planted_found} | {:.1} s",
        st.cols, st.rows, st.dim, st.total_muls as f64, st.echelon_muls as f64, st.nf_muls as f64,
        st.charpoly_muls as f64, st.eigenvector_muls as f64, st.roots_muls as f64, st.total_ms / 1e3
    );
    GenericRow {
        equation_degree: d,
        solve: st,
        planted_found,
    }
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let mut p = 269u64;
    let mut seed = 1u64;
    let mut residuals = 3usize;
    let mut json: Option<String> = None;
    let mut generic_degrees: Option<Vec<u8>> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--p" => {
                i += 1;
                p = args[i].parse().expect("--p");
            }
            "--seed" => {
                i += 1;
                seed = args[i].parse().expect("--seed");
            }
            "--residuals" => {
                i += 1;
                residuals = args[i].parse().expect("--residuals");
            }
            "--json" => {
                i += 1;
                json = Some(args[i].clone());
            }
            "--generic" => {
                i += 1;
                generic_degrees = Some(
                    args[i]
                        .split(',')
                        .map(|v| v.parse().expect("--generic"))
                        .collect(),
                );
            }
            other => panic!("unknown argument {other}"),
        }
        i += 1;
    }

    if let Some(ds) = generic_degrees {
        let rows: Vec<GenericRow> = ds.iter().map(|&d| generic(d, seed)).collect();
        if let Some(path) = json {
            fs::write(&path, serde_json::to_string_pretty(&rows).unwrap()).expect("write json");
            println!("wrote {path}");
        }
        return;
    }

    let mut rng = StdRng::seed_from_u64(seed);
    let curve = Curve4::random(p, &mut rng);
    let f = &curve.f;
    let base = factor_base(&curve, &mut rng);
    // F_p multiplications per affine addition, measured on this field.
    let fp_per_add = {
        let q = base[1];
        let mut acc = base[0];
        f.reset_muls();
        for _ in 0..64 {
            acc = curve.add(&acc, &q);
        }
        f.muls() as f64 / 64.0
    };
    let t = Instant::now();
    f.reset_muls();
    let pre = SymmetrisedS5::precompute(&curve, &mut rng);
    let precompute_ms = t.elapsed().as_secs_f64() * 1e3;
    println!(
        "p={p} seed={seed}: base {} points, {fp_per_add:.1} F_p muls per addition, symmetrised S5 in {:.1} s ({:.3e} muls, {} monomials)",
        base.len(),
        precompute_ms / 1e3,
        pre.precompute_muls as f64,
        pre.monos.len()
    );

    let mut rows = Vec::new();
    for idx in 0..residuals {
        let constructed = idx == 0;
        let (r, planted) = if constructed {
            // R = P_a + P_b + P_c + P_d for distinct base points.
            let mut ids: Vec<usize> = Vec::new();
            while ids.len() < 4 {
                let k = rng.gen_range(0..base.len());
                if !ids.contains(&k) {
                    ids.push(k);
                }
            }
            let r = ids
                .iter()
                .fold(Pt4::INF, |acc, &k| curve.add(&acc, &base[k]));
            let mut xs: [u64; 4] = std::array::from_fn(|k| base[ids[k]].x.0[0]);
            xs.sort_unstable();
            (r, Some(xs))
        } else {
            let r = loop {
                let x = f.random(&mut rng);
                if let Some(pt) = curve.lift_x(&x, &mut rng) {
                    break pt;
                }
            };
            (r, None)
        };
        let mut st = QuarticSolve::default();
        f.reset_muls();
        eprintln!(
            "residual {idx} ({}):",
            if constructed { "constructed" } else { "random" }
        );
        let sols = solve_s5_subspace(&curve, &pre, &r.x, &mut rng, &mut st, true);
        let solver_q = sols
            .as_ref()
            .map(|s| base_quadruples(s, &base))
            .unwrap_or_default();
        let oracle_q = mitm_decompositions(&curve, &base, &r);
        let agree = sols.is_some() && solver_q == oracle_q;
        let planted_found = planted.map(|xs| solver_q.contains(&xs));
        println!(
            "residual {idx}{}: {} | dim {} rows {} cols {} | C4 = {:.4e} (weil {:.2e}, echelon {:.3e}, nf {:.3e}, charpoly {:.3e}, roots {:.2e}, eigen {:.3e}) | rational eigenvalues {} | solver {:?} oracle {:?} agree {agree} planted {planted_found:?} | {:.0} s",
            if constructed { " (constructed)" } else { "" },
            st.outcome, st.dim, st.rows, st.cols, st.total_muls as f64, st.weil_muls as f64,
            st.echelon_muls as f64, st.nf_muls as f64, st.charpoly_muls as f64, st.roots_muls as f64,
            st.eigenvector_muls as f64, st.rational_eigenvalues, solver_q, oracle_q, st.total_ms / 1e3
        );
        rows.push(ResidualRow {
            index: idx,
            constructed,
            solve: st,
            solver_quadruples: solver_q.into_iter().collect(),
            oracle_quadruples: oracle_q.into_iter().collect(),
            agree,
            planted_found,
        });
        // Write after every residual: a long run keeps what it finished.
        if let Some(path) = &json {
            let report = Report {
                p,
                seed,
                base: base.len(),
                fp_muls_per_add: fp_per_add,
                precompute_muls: pre.precompute_muls,
                precompute_ms,
                residuals: rows
                    .iter()
                    .map(|r| ResidualRow {
                        index: r.index,
                        constructed: r.constructed,
                        solve: r.solve.clone(),
                        solver_quadruples: r.solver_quadruples.clone(),
                        oracle_quadruples: r.oracle_quadruples.clone(),
                        agree: r.agree,
                        planted_found: r.planted_found,
                    })
                    .collect(),
            };
            fs::write(path, serde_json::to_string_pretty(&report).unwrap()).expect("write json");
        }
    }
}
