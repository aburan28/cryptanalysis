//! Crossbred against matrix-F4 and exhaustive search, on the Boolean
//! systems of Koblitz-curve index calculus.
//!
//! Three engines answer the same question — *does `x_R` decompose over
//! the invariant factor base?* — and this prices them in one unit.
//!
//! ```bash
//! cargo run --release --example crossbred_bench            # default ladder
//! cargo run --release --example crossbred_bench -- 9 11 13 # chosen n
//! ```
//!
//! ## The unit, and the boundary
//!
//! Everything is reported in **bit operations**, with one stated
//! conversion: a 64-bit word XOR is 64 bit operations.  That is a
//! definition, not a measurement, and it is the only conversion used.
//!
//! The boundary is exhaustive search over the Boolean system: `2^v`
//! points, each evaluating `T` monomials across all equations, so
//! `2^v · T` bit operations.  That is what an oracle has to beat to be
//! doing algebra rather than search, and it is the column every other
//! row is divided by.
//!
//! Note what this does **not** claim.  Per `research/notes/index-calculus/RESEARCH_SEMAEV_DECOMPOSITION.md`,
//! a faster decomposition oracle does not move the exponent of the
//! attack — relation collection stays `Θ(2^n)` with any oracle that is
//! polynomial in the factor base.  This table prices the oracle, which
//! is one phase, and says so.

use cryptanalysis_suite::binary_ecc::BinaryPoint;
use cryptanalysis_suite::cryptanalysis::crossbred::{
    extract_crossbred, format_sweep, solve_crossbred, sweep, CrossbredParams, SearchOptions,
};
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, matrix_f4_f2_counted, solve_boolean_system, FieldStructure,
    SolveOptions, SolverEngine,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base, KoblitzCurve,
};
use cryptanalysis_suite::cryptanalysis::pq_groebner_f2::F2BoolPoly;
use num_bigint::BigUint;
use std::time::Instant;

/// Bit operations per 64-bit word XOR.  The one conversion in this file.
const BITS_PER_WORD_OP: u64 = 64;

/// Exhaustive search over the Boolean system, as the reference oracle.
/// Returns the roots and the bit-operation count.
fn brute_force(system: &[F2BoolPoly], n_vars: usize) -> (Vec<u64>, u64) {
    let terms: u64 = system.iter().map(|p| p.terms.len() as u64).sum();
    let roots = (0..(1u64 << n_vars))
        .filter(|&p| system.iter().all(|q| q.eval(p) == 0))
        .collect();
    (roots, (1u64 << n_vars) * terms)
}

/// Matrix-F4 at the first degree that decides, with its word-op count.
/// Returns whether the reduction produced the infeasibility certificate.
fn f4_verdict(system: &[F2BoolPoly], n_vars: usize, max_degree: u32) -> (bool, u64, u32) {
    let base = system
        .iter()
        .flat_map(|p| p.terms.iter())
        .map(|t| t.mask.count_ones())
        .max()
        .unwrap_or(2)
        .max(2);
    let mut total = 0u64;
    for d in base..=max_degree.max(base) {
        match matrix_f4_f2_counted(system, n_vars, d) {
            Some((rows, ops)) => {
                total += ops;
                let refuted = rows
                    .iter()
                    .any(|p| p.terms.len() == 1 && p.terms[0].mask == 0);
                if refuted {
                    return (true, total, d);
                }
                if d == max_degree.max(base) {
                    return (false, total, d);
                }
            }
            None => return (false, total, d),
        }
    }
    (false, total, base)
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    // Bare `n`, or `n:m` — field degree and (optional) summand count.
    // A bare integer uses m = 2, matching the documented `9 11 13` form.
    let cases: Vec<(u32, usize)> = if args.is_empty() {
        vec![(9, 2), (13, 2), (7, 3), (9, 3)]
    } else {
        args.iter()
            .filter_map(|a| {
                if let Some((n, m)) = a.split_once(':') {
                    Some((n.parse().ok()?, m.parse().ok()?))
                } else {
                    Some((a.parse().ok()?, 2))
                }
            })
            .collect()
    };

    // ── The (D, k) sweep ───────────────────────────────────────────
    //
    // Where does a crossbred space exist at all?  `kernel_dim` has to
    // reach `n_vars − k` before the search phase is determined; the
    // `filters` column is the part a GPU would run.
    println!();
    println!("=== Crossbred space by (D, k), K_0 / F_2^9, m = 2 ===");
    println!();
    {
        let kc = KoblitzCurve::new(0, 9).expect("K_0 / F_2^9");
        let fb = build_frobenius_factor_base(&kc, 0).expect("factor base");
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let g = kc.generator().clone();
        let target = kc.mul(&g, &BigUint::from(53u32));
        let x_r = match &target {
            BinaryPoint::Affine { x, .. } => x.clone(),
            BinaryPoint::Infinity => unreachable!(),
        };
        let sys =
            build_decomposition_system(&fb.subspace_basis, &x_r, &kc.curve.b, 2, &st).unwrap();
        println!(
            "unknowns v = {}, equations = {}, ℓ = {}",
            sys.n_vars,
            sys.equations.len(),
            fb.ell
        );
        println!();
        let cells = sweep(
            &sys.equations,
            sys.n_vars,
            &[2, 3, 4],
            &(2..sys.n_vars.min(8)).collect::<Vec<_>>(),
            20_000,
        );
        print!("{}", format_sweep(&cells));
    }

    // ── The engine comparison ──────────────────────────────────────
    println!();
    println!("=== Oracle cost per target, three engines, same verdicts ===");
    println!();
    println!(
        "| n | m | ℓ | v | deg | targets | reference | agree | brute (bit ops) | F4 (bit ops) | \
         crossbred (bit ops) | xb/brute | xb/F4 | D | k | kernel | filters | xb wall | F4 wall | xb/F4 wall |"
    );
    println!(
        "|--:|--:|--:|--:|----:|--------:|:----------|:-----:|----------------:|-------------:|\
         --------------------:|---------:|------:|--:|--:|-------:|--------:|--------:|"
    );

    for &(n, m) in &cases {
        let kc = match KoblitzCurve::new(0, n) {
            Some(c) => c,
            None => continue,
        };
        let fb = match build_frobenius_factor_base(&kc, 0) {
            Some(f) => f,
            None => continue,
        };
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let g = kc.generator().clone();

        // One system to pick `k` on, then the same `k` for every target.
        let probe = kc.mul(&g, &BigUint::from(7u32));
        let x_probe = match &probe {
            BinaryPoint::Affine { x, .. } => x.clone(),
            BinaryPoint::Infinity => continue,
        };
        let probe_sys =
            match build_decomposition_system(&fb.subspace_basis, &x_probe, &kc.curve.b, m, &st) {
                Some(s) => s,
                None => continue,
            };
        let v = probe_sys.n_vars;
        let sys_deg = probe_sys
            .equations
            .iter()
            .flat_map(|e| e.terms.iter())
            .map(|t| t.mask.count_ones())
            .max()
            .unwrap_or(0);
        // Exhaustive search is the boundary where it is runnable; past
        // that the independent reference is F4-plus-splitting, which is
        // a different algorithm on the same system.
        let brute_ok = v <= 24;

        // Smallest `k` whose crossbred space determines the remaining
        // variables — the choice the algorithm actually has to make.
        let mut chosen: Option<(usize, u32)> = None;
        'pick: for d in sys_deg..=(sys_deg + 2) {
            for k in 2..v.min(18) {
                let params = CrossbredParams {
                    macaulay_degree: d,
                    enumerated: k,
                    target_degree: 1,
                    max_rows: 20_000,
                };
                if let Some(xb) = extract_crossbred(&probe_sys.equations, v, &params) {
                    if xb.stats.kernel_dim >= v - k {
                        chosen = Some((k, d));
                        break 'pick;
                    }
                }
            }
        }
        let (k, deg) = match chosen {
            Some(c) => c,
            None => {
                println!(
                    "| {n} | {m} | {} | {v} | {sys_deg} | — | — | — | — | — | — | — | — | — | — \
                     | — | — | no crossbred space |",
                    fb.ell
                );
                continue;
            }
        };

        let params = CrossbredParams {
            macaulay_degree: deg,
            enumerated: k,
            target_degree: 1,
            max_rows: 20_000,
        };

        let (mut brute_ops, mut f4_ops, mut xb_ops) = (0u64, 0u64, 0u64);
        let (mut kernel, mut filters) = (0usize, 0usize);
        let mut agree = true;
        let mut targets = 0u32;
        let mut wall = std::time::Duration::ZERO;
        let mut f4_wall = std::time::Duration::ZERO;
        let mut brute_wall = std::time::Duration::ZERO;

        for t in 1..=12u32 {
            let point = kc.mul(&g, &BigUint::from(t * 7 + 1));
            let x_r = match &point {
                BinaryPoint::Affine { x, .. } => x.clone(),
                BinaryPoint::Infinity => continue,
            };
            let sys =
                match build_decomposition_system(&fb.subspace_basis, &x_r, &kc.curve.b, m, &st) {
                    Some(s) => s,
                    None => continue,
                };
            targets += 1;

            // The reference root set.  Exhaustive search where it fits —
            // then the check is set equality, which is the strong one.
            //
            // Past that, F4-plus-splitting is run under its default
            // `max_solutions` cap, so its list is a *prefix* of the root
            // set, not the root set.  Comparing for equality there would
            // be comparing against a truncation, so the check weakens to
            // containment in that direction only: every root F4 found
            // must be one crossbred found.  Crossbred's own roots are
            // verified against the original equations inside
            // `solve_crossbred`, so the pair of checks is still
            // two-sided — it is the completeness half that is capped,
            // not the soundness half.
            let (roots, exact) = if brute_ok {
                let tb = Instant::now();
                let (roots, bops) = brute_force(&sys.equations, v);
                brute_wall += tb.elapsed();
                brute_ops += bops;
                (roots, true)
            } else {
                let (mut roots, _) = solve_boolean_system(
                    &sys.equations,
                    v,
                    &SolveOptions {
                        engine: SolverEngine::MatrixF4 { max_degree: 4 },
                        ..Default::default()
                    },
                );
                roots.sort_unstable();
                (roots, false)
            };

            let tf = Instant::now();
            let (refuted, fops, _) = f4_verdict(&sys.equations, v, 4);
            f4_wall += tf.elapsed();
            f4_ops += fops * BITS_PER_WORD_OP;
            // F4's certificate must not contradict the reference.
            if refuted && !roots.is_empty() {
                agree = false;
            }

            let t0 = Instant::now();
            let xb = extract_crossbred(&sys.equations, v, &params).expect("extraction");
            let (mut got, stats) = solve_crossbred(&sys.equations, &xb, &SearchOptions::default());
            wall += t0.elapsed();
            kernel = xb.stats.kernel_dim;
            filters = xb.stats.filters;
            xb_ops += (xb.stats.word_ops
                + stats.transform_word_ops
                + stats.filter_word_ops
                + stats.solve_row_ops)
                * BITS_PER_WORD_OP;

            if stats.exhausted {
                agree = false;
            }
            let mut expect = roots;
            got.sort_unstable();
            expect.sort_unstable();
            // Soundness, always: every crossbred root really is a root.
            if !got
                .iter()
                .all(|&r| sys.equations.iter().all(|p| p.eval(r) == 0))
            {
                agree = false;
            }
            // Completeness: equality against exhaustive search, or
            // containment against the capped reference.
            if exact {
                if got != expect {
                    agree = false;
                }
            } else if !expect.iter().all(|r| got.contains(r)) {
                agree = false;
            }
        }

        if targets == 0 {
            continue;
        }
        let per = |x: u64| x / targets as u64;
        let (b, f, x) = (per(brute_ops), per(f4_ops), per(xb_ops));
        let show = |v: u64| {
            if v == 0 {
                "—".to_string()
            } else {
                v.to_string()
            }
        };
        let ratio = |num: u64, den: u64| {
            if den > 0 {
                format!("{:.3}", num as f64 / den as f64)
            } else {
                "—".to_string()
            }
        };
        println!(
            "| {n} | {m} | {} | {v} | {sys_deg} | {targets} | {} | {} | {} | {} | {x} | {} | {} \
             | {deg} | {k} | {kernel} | {filters} | {:.1} ms | {:.1} ms | {} |",
            fb.ell,
            if brute_ok {
                "exhaustive, =="
            } else {
                "F4 capped, ⊆"
            },
            if agree { "yes" } else { "NO" },
            show(b),
            show(f),
            ratio(x, b),
            ratio(x, f),
            wall.as_secs_f64() * 1000.0 / targets as f64,
            f4_wall.as_secs_f64() * 1000.0 / targets as f64,
            if f4_wall.as_secs_f64() > 0.0 {
                format!("{:.3}", wall.as_secs_f64() / f4_wall.as_secs_f64())
            } else {
                "—".to_string()
            },
        );
    }

    println!();
    println!("Unit: bit operations, one 64-bit word XOR = {BITS_PER_WORD_OP} bit ops.");
    println!("Boundary: exhaustive search over the Boolean system, 2^v · (total monomials).");
    println!();
    println!("The `agree` column is the correctness gate, and it has two strengths.");
    println!("  `exhaustive, ==` : crossbred's root set equals exhaustive search's, exactly.");
    println!("  `F4 capped, ⊆`   : past v = 24 exhaustive search does not fit, and F4+splitting");
    println!("                     runs under its default max_solutions cap, so its list is a");
    println!("                     prefix of the root set.  The check is then two one-sided");
    println!("                     ones: every crossbred root verifies against the original");
    println!("                     equations, and every root F4 found is one crossbred found.");
    println!("A row that does not say `yes` is not a result.");
    println!();
    println!("What this prices is the decomposition oracle only.  Relation collection stays");
    println!("Θ(2^n) with any oracle polynomial in the factor base — see");
    println!(
        "research/notes/index-calculus/RESEARCH_SEMAEV_DECOMPOSITION.md, `What this does not buy`."
    );
}
