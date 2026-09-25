//! Solving degree at **fixed surplus**: the `m = 3` ladder
//! `RESEARCH_DESCENT_CROSSOVER.md` §7 asks for.
//!
//! `dreg_sweep` takes `ℓ` from the Frobenius-invariant subspaces, so its
//! surplus `S = n − 3ℓ` jumps with `n`.  This takes each cell's `(n, ℓ)`
//! explicitly, over random subspaces, so pairs of cells can share `S`.
//! Every draw's solutions are counted exactly first; only draws with none
//! are measured, so a degree that does not resolve on a fully built matrix
//! is a lower bound on the refutation degree and not a satisfiable system.
//!
//! ```sh
//! F4_F2_MAX_ROWS=50000000 F4_F2_MAX_COLS=50000000 \
//!   cargo run --release --example dreg_ladder -- \
//!     --cells 7:3:7,13:5:6 --unsat 4 --ffd-max 5 --controls 1 --seed 20260923
//! ```
//!
//! Each cell's draws come from their own seed (`seed`, `n`, `ℓ`), so a cell
//! reproduces run alone or in any order.  One JSON line per draw on stdout;
//! the summary table on stderr at the end.

use cryptanalysis_suite::cryptanalysis::koblitz_bench::{
    ladder_control, ladder_draw, LadderDraw, LadderOutcome,
};
use rand::rngs::StdRng;
use rand::SeedableRng;

fn outcome_json(o: &LadderOutcome) -> String {
    match o {
        LadderOutcome::Satisfiable => r#"{"kind":"satisfiable"}"#.into(),
        LadderOutcome::Resolved { degree, refuted } => {
            format!(r#"{{"kind":"resolved","degree":{degree},"refuted":{refuted}}}"#)
        }
        LadderOutcome::AtLeast(d) => format!(r#"{{"kind":"at_least","degree":{d}}}"#),
        LadderOutcome::CapsHit { built } => format!(
            r#"{{"kind":"caps_hit","built":{}}}"#,
            built.map_or("null".to_string(), |b| b.to_string())
        ),
    }
}

fn outcome_short(o: &LadderOutcome) -> String {
    match o {
        LadderOutcome::Satisfiable => "sat".into(),
        LadderOutcome::Resolved {
            degree,
            refuted: true,
        } => format!("{degree}"),
        LadderOutcome::Resolved {
            degree,
            refuted: false,
        } => format!("{degree}p"),
        LadderOutcome::AtLeast(d) => format!("≥{d}"),
        LadderOutcome::CapsHit { built } => {
            format!("caps@{}", built.map_or("-".into(), |b| b.to_string()))
        }
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let flag = |name: &str| {
        args.iter()
            .position(|a| a == name)
            .and_then(|i| args.get(i + 1))
            .cloned()
    };
    let num = |name: &str, default: u64| flag(name).and_then(|v| v.parse().ok()).unwrap_or(default);
    let cells: Vec<(u32, usize, u32)> = flag("--cells")
        .unwrap_or_else(|| "7:3:7".into())
        .split(',')
        .map(|c| {
            let p: Vec<u64> = c
                .split(':')
                .map(|x| x.parse().expect("cell is n:ell:d_max"))
                .collect();
            assert_eq!(p.len(), 3, "cell is n:ell:d_max");
            (p[0] as u32, p[1] as usize, p[2] as u32)
        })
        .collect();
    let want_unsat = num("--unsat", 4) as usize;
    let max_draws = num("--max-draws", 4096) as usize;
    let ffd_max = num("--ffd-max", 5) as u32;
    let controls = num("--controls", 0) as usize;
    let seed = num("--seed", 0x5EED);

    // `--unsat-index K`: measure only the cell's K-th unsatisfiable draw
    // (from 0), replaying the draws before it through the exact solution
    // count alone.  `--control-only`: run only the cell's control.  Both give
    // what the sequential run gives at that position, from the same seed, so a
    // cell can be measured one process per draw and a restart loses only the
    // draws in flight.
    let only_unsat = flag("--unsat-index").map(|v| v.parse::<usize>().expect("--unsat-index K"));
    let control_only = args.iter().any(|a| a == "--control-only");
    if only_unsat.is_some() || control_only {
        assert_eq!(cells.len(), 1, "one cell per process in this mode");
        let (n, ell, d_max) = cells[0];
        let cell_seed = seed ^ (u64::from(n) << 40) ^ ((ell as u64) << 32);
        if let Some(k) = only_unsat {
            measure_one(n, ell, d_max, ffd_max, cell_seed, k, max_draws);
        }
        if control_only {
            let n_vars = 3 * ell + n as usize;
            for t in 0..controls.max(1) {
                let terms = ladder_terms_per_eq(
                    n,
                    ell,
                    cell_seed ^ 0x0C01_7201_u64.wrapping_mul(t as u64 + 1),
                );
                let started = std::time::Instant::now();
                let o = ladder_control(
                    n_vars,
                    3,
                    terms,
                    d_max,
                    cell_seed
                        .wrapping_mul(0x9E37_79B9_7F4A_7C15)
                        .wrapping_add(t as u64),
                );
                println!(
                    r#"{{"cell":"n{n}l{ell}","control":{t},"n_vars":{n_vars},"n_eqs":{},"terms_per_eq":{terms},"d_max":{d_max},"outcome":{},"secs":{:.3}}}"#,
                    n_vars + 4,
                    outcome_json(&o),
                    started.elapsed().as_secs_f64()
                );
                eprintln!("n={n} ℓ={ell}: control {t} -> {}", outcome_short(&o));
            }
        }
        return;
    }

    let mut table = Vec::new();
    for &(n, ell, d_max) in &cells {
        let cell_seed = seed ^ (u64::from(n) << 40) ^ ((ell as u64) << 32);
        let mut rng = StdRng::seed_from_u64(cell_seed);
        let mut unsat: Vec<LadderDraw> = Vec::new();
        let (mut drawn, mut sat) = (0usize, 0usize);
        let mut shape = None;
        while unsat.len() < want_unsat && drawn < max_draws {
            let d = ladder_draw(n, ell, d_max, ffd_max, &mut rng).expect("cell builds");
            drawn += 1;
            shape = Some((d.n_vars, d.n_eqs));
            println!(
                r#"{{"cell":"n{n}l{ell}","n":{n},"ell":{ell},"surplus":{},"d_max":{d_max},"draw":{},"n_vars":{},"n_eqs":{},"v_basis":{:?},"x_r":{},"solutions":{},"outcome":{},"ffd":{},"secs":{:.3}}}"#,
                n as i64 - 3 * ell as i64,
                drawn - 1,
                d.n_vars,
                d.n_eqs,
                d.v_basis,
                d.x_r,
                d.solutions,
                outcome_json(&d.outcome),
                d.ffd.map_or("null".to_string(), |f| f.to_string()),
                d.secs
            );
            if d.outcome == LadderOutcome::Satisfiable {
                sat += 1;
            } else {
                eprintln!(
                    "n={n} ℓ={ell}: unsat draw {} -> {} ({:.1}s)",
                    unsat.len(),
                    outcome_short(&d.outcome),
                    d.secs
                );
                unsat.push(d);
            }
        }
        let (n_vars, n_eqs) = shape.unwrap_or((0, 0));
        let mut ctrl = Vec::new();
        for t in 0..controls {
            // Degree 3 and the systems' own term density, as `dreg_summary` does.
            let terms = ladder_terms_per_eq(
                n,
                ell,
                cell_seed ^ 0x0C01_7201_u64.wrapping_mul(t as u64 + 1),
            );
            let started = std::time::Instant::now();
            let o = ladder_control(
                n_vars,
                3,
                terms,
                d_max,
                cell_seed
                    .wrapping_mul(0x9E37_79B9_7F4A_7C15)
                    .wrapping_add(t as u64),
            );
            println!(
                r#"{{"cell":"n{n}l{ell}","control":{t},"n_vars":{n_vars},"n_eqs":{},"terms_per_eq":{terms},"d_max":{d_max},"outcome":{},"secs":{:.3}}}"#,
                n_vars + 4,
                outcome_json(&o),
                started.elapsed().as_secs_f64()
            );
            eprintln!("n={n} ℓ={ell}: control {t} -> {}", outcome_short(&o));
            ctrl.push(o);
        }
        table.push((n, ell, d_max, n_vars, n_eqs, drawn, sat, unsat, ctrl));
    }

    eprintln!();
    eprintln!("| n | ℓ | S | vars | eqs | d_max | draws | sat | unsat outcomes | FFD | control |");
    eprintln!("|--:|--:|--:|--:|--:|--:|--:|--:|:--|:--|:--|");
    for (n, ell, d_max, n_vars, n_eqs, drawn, sat, unsat, ctrl) in &table {
        let outs: Vec<String> = unsat.iter().map(|d| outcome_short(&d.outcome)).collect();
        let ffds: Vec<String> = unsat
            .iter()
            .map(|d| d.ffd.map_or(">".into(), |f| f.to_string()))
            .collect();
        let cs: Vec<String> = ctrl.iter().map(outcome_short).collect();
        eprintln!(
            "| {n} | {ell} | {} | {n_vars} | {n_eqs} | {d_max} | {drawn} | {sat} | {} | {} | {} |",
            *n as i64 - 3 * *ell as i64,
            outs.join(" "),
            ffds.join(" "),
            if cs.is_empty() {
                "-".into()
            } else {
                cs.join(" ")
            }
        );
    }
}

/// The cell's `k`-th unsatisfiable draw, measured; the draws before it only
/// counted.  Prints the draw's JSON line exactly as the sequential run does.
fn measure_one(
    n: u32,
    ell: usize,
    d_max: u32,
    ffd_max: u32,
    cell_seed: u64,
    k: usize,
    max_draws: usize,
) {
    use cryptanalysis_suite::binary_ecc::F2mElement;
    use cryptanalysis_suite::cryptanalysis::koblitz_bench::{
        chained_s3_solution_count, ladder_measure, ladder_sample,
    };
    use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;
    let irr = find_irreducible_sparse(n).expect("field");
    let b = F2mElement::one(n);
    let mut rng = StdRng::seed_from_u64(cell_seed);
    let mut unsat_seen = 0usize;
    for drawn in 0..max_draws {
        let (basis, x_r) = ladder_sample(n, ell, &mut rng);
        if chained_s3_solution_count(&basis, &x_r, &b, &irr) > 0 {
            continue;
        }
        if unsat_seen < k {
            unsat_seen += 1;
            continue;
        }
        let d = ladder_measure(n, &basis, &x_r, d_max, ffd_max).expect("cell builds");
        println!(
            r#"{{"cell":"n{n}l{ell}","n":{n},"ell":{ell},"surplus":{},"d_max":{d_max},"draw":{drawn},"n_vars":{},"n_eqs":{},"v_basis":{:?},"x_r":{},"solutions":{},"outcome":{},"ffd":{},"secs":{:.3},"unsat_index":{k}}}"#,
            n as i64 - 3 * ell as i64,
            d.n_vars,
            d.n_eqs,
            d.v_basis,
            d.x_r,
            d.solutions,
            outcome_json(&d.outcome),
            d.ffd.map_or("null".to_string(), |f| f.to_string()),
            d.secs
        );
        eprintln!(
            "n={n} ℓ={ell}: unsat draw {k} (draw {drawn}) -> {} ({:.1}s)",
            outcome_short(&d.outcome),
            d.secs
        );
        return;
    }
    eprintln!("n={n} ℓ={ell}: no unsatisfiable draw {k} within {max_draws} draws");
}

/// Mean terms per equation of one fresh draw of the cell, for the control's
/// density -- the same statistic `dreg_summary` feeds its control.
fn ladder_terms_per_eq(n: u32, ell: usize, seed: u64) -> usize {
    use cryptanalysis_suite::binary_ecc::F2mElement;
    use cryptanalysis_suite::cryptanalysis::koblitz_bench::random_subspace_basis;
    use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
        build_decomposition_system, FieldStructure,
    };
    use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;
    use num_bigint::BigUint;
    use rand::Rng;
    let mut rng = StdRng::seed_from_u64(seed);
    let irr = find_irreducible_sparse(n).unwrap();
    let st = FieldStructure::new(n, &irr);
    let basis = random_subspace_basis(n, ell, &mut rng);
    let x_r = F2mElement::from_biguint(&BigUint::from(rng.gen::<u64>() & ((1u64 << n) - 1)), n);
    let sys = build_decomposition_system(&basis, &x_r, &F2mElement::one(n), 3, &st).unwrap();
    sys.equations.iter().map(|e| e.terms.len()).sum::<usize>() / sys.equations.len().max(1)
}
