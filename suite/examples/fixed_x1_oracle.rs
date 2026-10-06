//! Is there a sub-`2^{2ℓ}` decomposition oracle?
//!
//! `research/notes/index-calculus/RESEARCH_SEMAEV_DECOMPOSITION.md` ends on a boundary rather than a
//! result: with any oracle that enumerates the factor base, relation
//! collection costs `Θ(2^n)` however fast the inner loop is, because a
//! larger factor base needs fewer tries and makes each try
//! proportionally more expensive, and the two cancel *exactly*.  The one
//! thing that would change that is an oracle costing **less than
//! `2^{2ℓ}`** per target, and that note names the route worth trying:
//!
//! > Gröbner basis (F4/F5) on the descended system for fixed `X₁`, which
//! > is a bivariate problem in `2ℓ` unknowns — the premise being to
//! > exploit the algebra rather than search around it.
//!
//! This is that experiment.  For each of the `2^ℓ` choices of `X₁`,
//! build the Weil restriction of the symmetrised `S₄` with `X₁` fixed —
//! `n = 3ℓ` Boolean equations in the `2ℓ` unknowns of `X₂` and `X₃` —
//! and decide it algebraically.  If the deciding degree stays constant
//! as `ℓ` grows, the whole oracle costs `2^ℓ · poly(ℓ)` and the answer
//! is yes.  If it grows with `ℓ`, it is no.
//!
//! ```bash
//! cargo run --release --example fixed_x1_oracle           # ℓ = 3..8
//! cargo run --release --example fixed_x1_oracle -- 3 4 5  # chosen ℓ
//! ```
//!
//! ## Boundary and unit
//!
//! The boundary is `2^{2ℓ}`, the cost of the pairs-and-solve oracle
//! `semaev_decomp` implements, and the table's job is the **fitted
//! exponent** `c` in `cost ≈ 2^{cℓ}`.  `c < 2` is a result; `c ≥ 2` is
//! not.  Costs are 64-bit word XORs in the Macaulay eliminations, which
//! is the same unit `crossbred_bench` uses.
//!
//! The correctness gate is `semaev_decomp::decompose`: on every target,
//! this route must reach the same verdict.

use cryptanalysis_suite::binary_ecc::F2mElement;
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    matrix_f4_f2_counted, sym_semaev_s4, FieldStructure, SymElement,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::find_irreducible;
use cryptanalysis_suite::cryptanalysis::pq_groebner_f2::F2BoolPoly;
use cryptanalysis_suite::cryptanalysis::semaev_decomp::{decompose, Gf2};

/// The **deciding degree**: the lowest Macaulay degree at which the
/// reduction either refutes the system (the constant `1` appears) or
/// pins every unknown.
///
/// This is the quantity the whole question turns on.  The fixed-`X₁`
/// route costs `2^ℓ` systems times whatever one system costs, and one
/// system at a *fixed* degree `D` costs `C(2ℓ + D, D)^ω` — polynomial
/// in `ℓ`.  So if the deciding degree stays bounded as `ℓ` grows, the
/// oracle is `2^ℓ · poly(ℓ)` and beats `2^{2ℓ}`; if it grows with `ℓ`,
/// the binomial is exponential and it does not.
///
/// Returns `(deciding degree, word ops, decided)`.  `decided = false`
/// means no degree up to `max_degree` settled it.
fn decide(system: &[F2BoolPoly], n_vars: usize, max_degree: u32) -> (u32, u64, bool) {
    let base = system
        .iter()
        .flat_map(|p| p.terms.iter())
        .map(|t| t.mask.count_ones())
        .max()
        .unwrap_or(2)
        .max(2);
    let mut total = 0u64;
    for d in base..=max_degree.max(base) {
        let Some((rows, ops)) = matrix_f4_f2_counted(system, n_vars, d) else {
            return (d, total, false);
        };
        total += ops;
        // Refuted: the reduction produced the constant 1.
        if rows
            .iter()
            .any(|p| p.terms.len() == 1 && p.terms[0].mask == 0)
        {
            return (d, total, true);
        }
        // Determined: every variable has been pinned to a value.
        let pinned = rows
            .iter()
            .filter(|p| {
                (p.terms.len() == 1 && p.terms[0].mask.count_ones() == 1)
                    || (p.terms.len() == 2
                        && p.terms.iter().any(|t| t.mask == 0)
                        && p.terms.iter().any(|t| t.mask.count_ones() == 1))
            })
            .flat_map(|p| p.terms.iter())
            .map(|t| t.mask)
            .fold(0u64, |a, b| a | b)
            .count_ones() as usize;
        if pinned >= n_vars {
            return (d, total, true);
        }
    }
    (max_degree, total, false)
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let ells: Vec<u32> = if args.is_empty() {
        vec![3, 4, 5, 6, 7, 8]
    } else {
        args.iter().filter_map(|a| a.parse().ok()).collect()
    };

    println!();
    println!("=== Fixed-X1 oracle: does the deciding degree stay bounded? ===");
    println!();
    println!(
        "| ℓ | n | unknowns | targets | agree | X1 sampled | decided | deciding degree \
         (min/median/max) | ops / system | ops / target = 2^ℓ · that | log2 |"
    );
    println!(
        "|--:|--:|---------:|--------:|:-----:|-----------:|--------:|\
         --------------------------------:|-------------:|---------------------------:|-----:|"
    );

    let mut fit: Vec<(f64, f64)> = Vec::new();
    let mut degree_by_ell: Vec<(u32, f64)> = Vec::new();

    for &l in &ells {
        let n = 3 * l;
        let Some(irr) = find_irreducible(n) else {
            continue;
        };
        let st = FieldStructure::new(n, &irr);
        let gf = Gf2::new(&irr);
        let basis: Vec<F2mElement> = (0..l)
            .map(|k| F2mElement::from_bit_positions(&[k], n))
            .collect();
        let two = 2 * l as usize;
        // The deciding degree can be as high as the variable count; let
        // it run that far rather than capping it and reporting a
        // truncation as a measurement.
        let max_degree = two as u32;

        let mut agree = true;
        let mut targets = 0u32;
        let mut degrees: Vec<u32> = Vec::new();
        let mut ops_per_system: Vec<u64> = Vec::new();
        let mut undecided = 0u64;
        let mut sampled = 0u64;
        let mut saw_yes = false;
        let mut saw_no = false;

        for t in 1..=6u64 {
            let xr_raw = (t * 2_654_435_761) % (1u64 << n);
            if xr_raw == 0 {
                continue;
            }
            let x_r = F2mElement::from_biguint(&num_bigint::BigUint::from(xr_raw), n);
            targets += 1;

            let reference = decompose(xr_raw, l, &gf).is_some();
            if reference {
                saw_yes = true;
            } else {
                saw_no = true;
            }

            // Correctness runs over every X1; the degree statistic is
            // sampled, because the degree is a property of the system
            // shape and every X1 gives the same shape.
            let mut found = false;
            let sample_stride = 1u64.max((1u64 << l) / 8);
            for x1_bits in 0..(1u64 << l) {
                let mut x1 = F2mElement::zero(n);
                for (k, b) in basis.iter().enumerate() {
                    if (x1_bits >> k) & 1 == 1 {
                        x1 = x1.add(b);
                    }
                }
                let system = sym_semaev_s4(
                    &SymElement::constant(&x1, n, two),
                    &SymElement::from_subspace_vars(&basis, 0, n, two),
                    &SymElement::from_subspace_vars(&basis, l as usize, n, two),
                    &x_r,
                    &st,
                );
                if x1_bits % sample_stride == 0 {
                    let (deg, ops, decided) = decide(&system, two, max_degree);
                    sampled += 1;
                    if decided {
                        degrees.push(deg);
                        ops_per_system.push(ops);
                    } else {
                        undecided += 1;
                    }
                }
                // The gate: exhaustive search over 2^{2ℓ}, which is
                // exactly what the algebra is trying to replace.
                if !found {
                    for pt in 0..(1u64 << two) {
                        if system.iter().all(|e| e.eval(pt) == 0) {
                            found = true;
                            break;
                        }
                    }
                }
            }
            if found != reference {
                agree = false;
            }
        }
        if !(saw_yes && saw_no) {
            eprintln!("note: ℓ={l} saw only one verdict across its targets");
        }

        degrees.sort_unstable();
        let (dmin, dmed, dmax) = if degrees.is_empty() {
            (0, 0, 0)
        } else {
            (
                degrees[0],
                degrees[degrees.len() / 2],
                degrees[degrees.len() - 1],
            )
        };
        let mean_ops = if ops_per_system.is_empty() {
            0
        } else {
            ops_per_system.iter().sum::<u64>() / ops_per_system.len() as u64
        };
        let per_target = mean_ops.saturating_mul(1u64 << l);
        let log2 = if per_target > 0 {
            (per_target as f64).log2()
        } else {
            0.0
        };
        if per_target > 0 {
            fit.push((l as f64, log2));
            degree_by_ell.push((l, dmed as f64));
        }
        println!(
            "| {l} | {n} | {two} | {targets} | {} | {sampled} | {} | {dmin}/{dmed}/{dmax} | \
             {mean_ops} | {per_target} | {log2:.2} |",
            if agree { "yes" } else { "NO" },
            sampled - undecided,
        );
    }

    if fit.len() >= 2 {
        let slope = |pts: &[(f64, f64)]| -> f64 {
            let k = pts.len() as f64;
            let sx: f64 = pts.iter().map(|p| p.0).sum();
            let sy: f64 = pts.iter().map(|p| p.1).sum();
            let sxx: f64 = pts.iter().map(|p| p.0 * p.0).sum();
            let sxy: f64 = pts.iter().map(|p| p.0 * p.1).sum();
            (k * sxy - sx * sy) / (k * sxx - sx * sx)
        };
        let c = slope(&fit);
        let dslope = slope(
            &degree_by_ell
                .iter()
                .map(|&(l, d)| (l as f64, d))
                .collect::<Vec<_>>(),
        );
        println!();
        println!("Deciding degree against ℓ: slope {dslope:.3}.");
        println!("  A slope near 0 would mean a bounded degree, hence 2^ℓ · poly(ℓ) overall.");
        println!("  A slope near 1 means the degree tracks the variable count, and the");
        println!("  Macaulay binomial C(2ℓ + D, D) is then exponential in ℓ.");
        println!();
        println!("Fitted exponent: cost ≈ 2^({c:.3}·ℓ), against the 2^(2ℓ) boundary.");
        if c < 2.0 {
            println!("  {c:.3} < 2 — sub-2^(2ℓ) over the measured range.");
        } else {
            println!("  {c:.3} ≥ 2 — NOT sub-2^(2ℓ) over the measured range.");
        }
        println!();
        println!("Read the exponent with the range in mind: over ℓ = 3..8 the polynomial");
        println!("factor C(2ℓ + D, D) still dominates the 2^ℓ sweep, so the fitted slope is");
        println!("an overestimate of the asymptote.  The deciding-degree slope is the");
        println!("structural number, and it is the one that decides the question.");
    }

    println!();
    println!("Unit: 64-bit word XORs in the Macaulay eliminations.");
    println!("Boundary: 2^(2ℓ), the pairs-and-solve oracle of semaev_decomp.");
    println!("`agree` compares against semaev_decomp::decompose on every target; a row that");
    println!("does not say `yes` is not a result.  `decided` counts the sampled X1 systems the");
    println!("algebra settled at some degree — an undecided system is one the method cannot");
    println!("close at all, and those are excluded from the degree and cost statistics.");
    println!();
    println!("The deciding degree is a property of the ideal, not of the engine: F5 avoids");
    println!("zero reductions but does not lower the degree of regularity, so a better");
    println!("Groebner implementation moves the constant here and not the slope.");
}
