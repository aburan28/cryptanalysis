//! `ic budget` — what one decomposition may cost, before any run is started.
//!
//! The other cost figures this tool produces are measured after the fact: the
//! `vs_rho` block of `ic workflow` times a run that already happened, and it is
//! reachable only from inside a workflow with `baseline.rho` set. This command
//! answers the question asked *before* spending anything, analytically, at
//! degrees far past the 63 the curve constructors reach.
//!
//! The model lives in
//! [`cryptanalysis::index_calculus_budget`](cryptanalysis_suite::cryptanalysis::index_calculus_budget);
//! this module only turns it into arguments and a report.

use clap::Args;
use cryptanalysis_suite::cryptanalysis::index_calculus_budget as budget;
use serde_json::{json, Value};
use std::time::Instant;

use super::experiment;

/// Degrees a run report would otherwise have to guess at. Nine standardised
/// binary extension degrees, the two challenge sizes included.
const STANDARD_DEGREES: [u32; 9] = [113, 127, 131, 163, 233, 239, 283, 409, 571];

#[derive(Clone, Debug, Args)]
pub struct BudgetArgs {
    /// Extension degree n. Unlike the run commands this is not capped at 63:
    /// nothing is constructed, only charged.
    #[arg(long, value_parser = clap::value_parser!(u32).range(3..=4096))]
    pub degree: Option<u32>,
    /// Charge every standardised binary degree instead of one.
    #[arg(long, conflicts_with = "degree")]
    pub standard: bool,
    /// Factor-base points per relation. Omit to table every arity up to
    /// --max-arity.
    #[arg(long, value_parser = clap::value_parser!(u32).range(2..=16))]
    pub summands: Option<u32>,
    /// Charge this exact factor-base dimension rather than the best one.
    #[arg(long, requires = "summands")]
    pub dimension: Option<u32>,
    /// Largest arity to table.
    #[arg(long, default_value_t = 6, value_parser = clap::value_parser!(u32).range(2..=16))]
    pub max_arity: u32,
    /// Charge without crediting the Frobenius orbit quotient, which isolates
    /// exactly what that quotient buys.
    #[arg(long)]
    pub no_frobenius: bool,
}

fn cell_json(c: &budget::BudgetCell) -> Value {
    json!({
        "summands": c.m,
        "dimension": c.l,
        "orbit_reduction": c.orbit_reduction,
        "log2_factor_base": c.log2_factor_base,
        "log2_linear_algebra_dimension": c.log2_la_dimension,
        "log2_linear_algebra": c.log2_linear_algebra,
        "log2_memory_entries": c.log2_la_dimension,
        "log2_decomposition_probability": c.log2_decomposition_probability,
        "log2_attempts": c.log2_attempts,
        "log2_budget": c.log2_budget,
        "free_oracle_loses": c.free_oracle_loses,
        "boolean_variables": c.boolean_variables,
        "boolean_degree": c.boolean_degree,
        "log2_anf_monomials": c.log2_anf_monomials,
        "log2_anf_deficit": c.log2_anf_deficit,
        "anf_blocks": c.anf_blocks,
        "required_solver_exponent": c.required_solver_exponent,
        "viable": c.viable(),
    })
}

fn degree_json(n: u32, args: &BudgetArgs) -> Value {
    let frob = !args.no_frobenius;
    let cells: Vec<Value> = match (args.summands, args.dimension) {
        (Some(m), Some(l)) => vec![cell_json(&budget::evaluate(n, m as usize, l, frob))],
        (Some(m), None) => budget::best_cell(n, m as usize, frob)
            .iter()
            .map(cell_json)
            .collect(),
        _ => (2..=args.max_arity)
            .filter_map(|m| budget::best_cell(n, m as usize, frob))
            .map(|c| cell_json(&c))
            .collect(),
    };
    json!({
        "degree": n,
        "log2_rho": budget::rho_log2(n),
        "stable_dimensions_note": concat!(
            "Frobenius-stable dimensions are the subset sums of the cyclotomic ",
            "coset sizes; a dimension outside them is still a legal factor base, ",
            "it simply forfeits the orbit quotient."
        ),
        "minimum_viable_arity": budget::minimum_viable_arity(n, frob, args.max_arity as usize),
        "minimum_viable_arity_without_frobenius":
            budget::minimum_viable_arity(n, false, args.max_arity as usize),
        "cells": cells,
    })
}

pub fn run(args: BudgetArgs, quiet: bool) -> Result<Value, String> {
    let begin = Instant::now();
    let degrees: Vec<u32> = if args.standard {
        STANDARD_DEGREES.to_vec()
    } else {
        vec![args.degree.ok_or("supply --degree or --standard")?]
    };
    if let (Some(m), Some(l)) = (args.summands, args.dimension) {
        if l >= degrees[0] {
            return Err(format!(
                "dimension {l} is not below the degree {}; a factor base \
                 spanning the whole field is not one",
                degrees[0]
            ));
        }
        let _ = m;
    }
    if !quiet {
        println!("ic — charging index calculus against rho");
        use std::io::Write;
        let _ = std::io::stdout().flush();
    }
    let reports: Vec<Value> = degrees.iter().map(|&n| degree_json(n, &args)).collect();
    Ok(json!({
        "schema_version": 1,
        "operation": "budget",
        "status": "complete",
        "evidence_scope": "analytic_cost_model",
        "frobenius_orbit_quotient_credited": !args.no_frobenius,
        "degrees": reports,
        "elapsed_seconds": begin.elapsed().as_secs_f64(),
        "resources": experiment::resources(),
        "scope": concat!(
            "Exact arithmetic under the declared cost model: relation collection ",
            "and sparse linear algebra charged against the same rho budget, ",
            "inverted for what one decomposition may spend. No curve is ",
            "constructed, no decomposition is attempted and no discrete ",
            "logarithm is solved."
        ),
        "limitations": [
            "No imported target was used.",
            "A verdict under a cost model, not an attack and not a lower bound on ECDLP.",
            concat!(
                "Sparse linear algebra is charged at m*D^2. A method with a ",
                "materially lower exponent would relax the gate on the ",
                "factor-base dimension and could revive arity 3."
            ),
            concat!(
                "Forming the descended system is charged at one operation per ",
                "ANF monomial. That binds every method which materialises the ",
                "system -- Groebner, WDSat, CNF-SAT, crossbred, msolve -- but ",
                "not one that never materialises it."
            ),
            concat!(
                "Decompositions are assumed to behave like uniform random ",
                "m-multisets of the factor base, the standard heuristic of ",
                "this literature."
            ),
            concat!(
                "Polylog factors are dropped on both sides, so the comparison ",
                "is fair to within them but not to within constants."
            ),
            concat!(
                "Orbit reduction is computed for odd prime degrees; composite ",
                "degrees are charged with no orbit quotient rather than with a ",
                "wrong one."
            )
        ]
    }))
}
