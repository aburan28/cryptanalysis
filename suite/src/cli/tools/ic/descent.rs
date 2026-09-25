//! `ic descent` — the degree a Weil-descent system actually reaches.
//!
//! Petit and Quisquater's Table 2 (ASIACRYPT 2012, p. 461) reports, per
//! `(curve family, n, n', m)` cell, the average maximal degree a Gröbner
//! basis reached, the average time and the peak memory — and its point
//! is that the degree came out *below* the bound derived for a generic
//! system.  This runs the same measurement on this repository's descent
//! systems.
//!
//!     ic descent --out docs/ic/runs/ic-descent-degrees-YYYY-MM-DD.json
//!     ic descent --cells 11:6:2,11:4:3 --targets 16
//!
//! It prices **one decomposition oracle call**, so by `AGENTS.md` §2 it
//! is a stage diagnostic and never a speed.  The whole-pipeline unit
//! `S` lives in `ic boundary`.

use clap::Args;
use serde_json::{json, Value};

use crate::cryptanalysis::ic_descent_degrees::{
    format_engine_markdown, format_markdown, max_n_prime, price_descent_cell, price_engine_cell,
    semi_regular_degree, DescentCell, EngineCell,
};
use crate::cryptanalysis::ic_framework::solvers::{
    solver_by_name, validate_solver_params,
};
use crate::cryptanalysis::ic_framework::stages::Params;

#[derive(Args, Clone)]
pub struct DescentArgs {
    /// Curve families to run: `K` for the Koblitz curve, `R` for a
    /// random binary curve of the same degree.
    #[arg(long, value_delimiter = ',', default_value = "K,R")]
    pub families: Vec<String>,
    /// Cells as `n:n':m`, e.g. `11:6:2,11:4:3`.  Default is the ladder
    /// below, which takes `n' = ceil(n/m)` — the square-system choice.
    /// The descent is symbolic and holds up to 64 boolean variables
    /// (`n' ≤ 32` at `m = 2`, `n' ≤ 21` at `m = 3`); what limits a cell
    /// above that is the engine and the budget.
    #[arg(long, value_delimiter = ',')]
    pub cells: Option<Vec<String>>,
    /// Targets per cell.
    #[arg(long, default_value_t = 8)]
    pub targets: usize,
    #[arg(long, default_value_t = 0x0DE5_CE47)]
    pub seed: u64,
    /// Wall-clock budget per target, in seconds.  A run that exceeds it
    /// stops and the row says so, rather than the cell hanging: twelve
    /// boolean variables at three summands ran five hours here without
    /// finishing.  Zero means no budget.
    #[arg(long, default_value_t = 120)]
    pub budget_seconds: u64,
    /// Price registered `SystemSolver` engines instead of the built-in
    /// Buchberger, all on the same targets: `name` or `name:k=v,k=v`.
    /// Repeat the flag once per engine (parameters use commas, so the
    /// engines cannot share one flag).  Without it the command
    /// reproduces the frozen §14/§16 tables exactly.
    #[arg(long = "solver")]
    pub solvers: Vec<String>,
    /// With `--solver`: how many times every engine solves every target.
    /// The runs are interleaved per target and the engine order rotates
    /// each repetition, so drift on the host falls on every engine.
    #[arg(long, default_value_t = 1)]
    pub repeats: usize,
}

/// `name:k=v,k=v` → `(name, params)`.
fn parse_engine(spec: &str) -> Result<(String, Params), String> {
    let (name, rest) = spec.split_once(':').unwrap_or((spec, ""));
    let mut params = Params::default();
    for kv in rest.split(',').filter(|s| !s.is_empty()) {
        let (k, v) = kv
            .split_once('=')
            .ok_or_else(|| format!("parameter `{kv}` is not key=value"))?;
        params.set(k.trim(), v.trim());
    }
    Ok((name.to_string(), params))
}

/// `n' = ceil(n/m)` makes the descent square: `m·n'` unknowns against
/// `n` equations.  Cells past the descent's cap are dropped rather
/// than clamped, because clamping would silently change the shape of
/// the system being reported.
fn default_cells() -> Vec<(u32, u32, u32)> {
    let mut out = Vec::new();
    for m in [2u32, 3] {
        for n in [7u32, 9, 11, 13, 15] {
            let n_prime = n.div_ceil(m);
            if n_prime >= 2 && n_prime <= max_n_prime(m) {
                out.push((n, n_prime, m));
            }
        }
    }
    out
}

fn parse_cells(specs: &[String]) -> Result<Vec<(u32, u32, u32)>, String> {
    specs
        .iter()
        .map(|s| {
            let parts: Vec<&str> = s.split(':').collect();
            let [n, np, m] = parts[..] else {
                return Err(format!("cell `{s}` is not `n:n':m`"));
            };
            let parse = |v: &str, what: &str| {
                v.parse::<u32>()
                    .map_err(|_| format!("cell `{s}`: {what} `{v}` is not a number"))
            };
            Ok((parse(n, "n")?, parse(np, "n'")?, parse(m, "m")?))
        })
        .collect()
}

pub fn run(args: DescentArgs, json_only: bool) -> Result<Value, String> {
    let cells = match &args.cells {
        Some(specs) => parse_cells(specs)?,
        None => default_cells(),
    };
    for (n, np, m) in &cells {
        if !(2..=3).contains(m) {
            return Err(format!("m must be 2 or 3, got {m}"));
        }
        if *np > max_n_prime(*m) {
            return Err(format!(
                "n' = {np} exceeds the descent's monomial-mask cap {} at m = {m}",
                max_n_prime(*m)
            ));
        }
        // The field arithmetic reaches n = 63 and the descent's mask
        // m·n' = 64; the bound is the curve constructors' cost: the
        // random family counts points exhaustively, 2^n x-coordinates,
        // which is minutes at n = 33 and grows fourfold per two degrees.
        // 36 is also as far as the vector exhaustive search reaches.
        if *n < 5 || *n > 36 {
            return Err(format!("field degree {n} outside 5..=36"));
        }
    }
    for f in &args.families {
        if f != "K" && f != "R" {
            return Err(format!("family `{f}` is not K or R"));
        }
    }

    if !args.solvers.is_empty() {
        return run_engines(&args, &cells, json_only);
    }

    let started = std::time::Instant::now();
    let mut measured: Vec<DescentCell> = Vec::new();
    let mut skipped: Vec<Value> = Vec::new();
    for family in &args.families {
        for (n, n_prime, m) in &cells {
            if !json_only {
                eprintln!("  {family} n={n} n'={n_prime} m={m} …");
            }
            let budget = (args.budget_seconds > 0)
                .then(|| std::time::Duration::from_secs(args.budget_seconds));
            match price_descent_cell(
                family,
                *n,
                *n_prime,
                *m,
                args.targets.max(1),
                args.seed,
                budget,
            ) {
                Some(cell) => measured.push(cell),
                None => skipped.push(json!({
                    "family": family, "n": n, "n_prime": n_prime, "m": m,
                    "why": "no instance of this family at this degree, or past the descent cap",
                })),
            }
        }
    }

    // The phenomenon, counted: cells whose reached degree is below the
    // degree a semi-regular system of the same shape would reach.
    let with_bound: Vec<&DescentCell> = measured
        .iter()
        .filter(|c| c.d_av_over_semireg.is_some())
        .collect();
    let below = with_bound
        .iter()
        .filter(|c| c.d_av_over_semireg.unwrap() < 1.0)
        .count();

    Ok(json!({
        "schema_version": 1,
        "operation": "descent-degrees",
        "status": if measured.is_empty() { "incomplete" } else { "complete" },
        "what_this_is": "For each (curve family, field degree n, subspace dimension n', summands m): the Weil descent of the Semaev polynomial over a random target, solved by a boolean-ring Buchberger, reporting the maximal degree the run reached against the degree a semi-regular system of the same equation degrees would reach, with the monomial-operation count as the metric and wall time and the engine's peak footprint beside it.",
        "what_this_is_not": [
            "not a speed: this prices one decomposition oracle call on one target, which AGENTS.md section 2 calls a stage diagnostic and never a speed",
            "not a reproduction of Petit-Quisquater Table 2: their system is symmetrised to m^2+1 variables, this descent is the plain one in m*n' variables, so the degrees are not comparable row by row",
            "not a wall-clock benchmark: ms is a practicality note, the metric is the monomial-operation count",
            "not a claim about any deployed curve: the largest field here is GF(2^15)"
        ],
        "config": {
            "families": args.families,
            "cells": cells.iter().map(|(n, np, m)| json!({"n": n, "n_prime": np, "m": m})).collect::<Vec<_>>(),
            "targets": args.targets,
            "seed": args.seed,
            "budget_seconds_per_target": args.budget_seconds,
        },
        "boundary": {
            "what": "the semi-regular degree: the index of the first non-positive coefficient of (1+t)^v / prod_i (1 + t^{d_i}), for v boolean variables and equation degrees d_i (Bardet-Faugere-Salvy)",
            "why": "it is what a system with no exploitable structure reaches, so a measured degree below it is structure the solver found",
        },
        "cells_measured": measured.len(),
        "cells_with_a_timed_out_run": measured.iter().filter(|c| c.timed_out > 0).count(),
        "cells_skipped": skipped,
        "cells_below_the_semi_regular_degree": below,
        "cells_with_a_bound": with_bound.len(),
        "elapsed_seconds": started.elapsed().as_secs_f64(),
        "markdown": format_markdown(&measured),
        "cells": measured,
        "semi_regular_degree_check": {
            "quadratic_16_vars_16_eqs": semi_regular_degree(16, &[2; 16]),
            "quadratic_16_vars_32_eqs": semi_regular_degree(16, &[2; 32]),
        },
    }))
}

/// `--solver`: every named engine on every target of every cell, paired.
fn run_engines(
    args: &DescentArgs,
    cells: &[(u32, u32, u32)],
    json_only: bool,
) -> Result<Value, String> {
    let mut engines = Vec::new();
    let mut described = Vec::new();
    for spec in &args.solvers {
        let (name, params) = parse_engine(spec)?;
        if engines.iter().any(|(n, _, _): &(String, _, _)| *n == name) {
            return Err(format!("engine `{name}` listed twice"));
        }
        let solver = solver_by_name(&name)?;
        validate_solver_params(&name, &params)?;
        described.push(json!({
            "engine": name,
            "spec": spec,
            "describe": solver.describe(),
            "finds_every_solution": solver.finds_every_solution(),
        }));
        engines.push((name, solver, params));
    }
    let budget =
        (args.budget_seconds > 0).then(|| std::time::Duration::from_secs(args.budget_seconds));
    let started = std::time::Instant::now();
    let mut measured: Vec<EngineCell> = Vec::new();
    let mut skipped: Vec<Value> = Vec::new();
    for family in &args.families {
        for (n, n_prime, m) in cells {
            if !json_only {
                eprintln!(
                    "  {family} n={n} n'={n_prime} m={m} × {} engines × {} repeats …",
                    engines.len(),
                    args.repeats.max(1)
                );
            }
            match price_engine_cell(
                &engines,
                family,
                *n,
                *n_prime,
                *m,
                args.targets.max(1),
                args.seed,
                budget,
                args.repeats,
            ) {
                Some(cell) => measured.push(cell),
                None => skipped.push(json!({
                    "family": family, "n": n, "n_prime": n_prime, "m": m,
                    "why": "no instance of this family at this degree, or past the descent cap",
                })),
            }
        }
    }
    let disagreements: Vec<Value> = measured
        .iter()
        .flat_map(|c| {
            c.engines.iter().filter(|e| !e.agrees_with_reference).map(move |e| {
                json!({"family": c.family, "n": c.n, "n_prime": c.n_prime, "m": c.summands, "engine": e.engine})
            })
        })
        .collect();
    Ok(json!({
        "schema_version": 1,
        "operation": "descent-engines",
        "status": if measured.is_empty() { "incomplete" } else { "complete" },
        "what_this_is": "For each (curve family, n, n', m) cell: the Weil descent of the Semaev polynomial over the same seeded targets as the descent-degrees table, solved by every listed engine in every repetition, interleaved per target with the engine order rotated each repetition. Each engine's answers are checked against the reference engine's (fes-f2 where it applies, else exhaustive); each system carries a blake3 fingerprint and each cell a digest of the reference answers, so a rerun can prove it solved the same inputs and decided them the same way. The ms column is the mean over targets of the per-target median over repetitions.",
        "what_this_is_not": [
            "not a speed: this prices one decomposition oracle call on one target, which AGENTS.md section 2 calls a stage diagnostic and never a speed",
            "not a common unit: each engine counts in its own unit (ops column, unit named per engine); only wall time is common, and it is a host-dependent practicality note",
            "not a group relation: a boolean root is not yet a point decomposition until it is lifted and checked on the curve, which the whole-pipeline run does",
            "not one leaderboard: a first-solution engine (sat-cdcl) and the complete-enumeration engines are different workloads and are listed apart"
        ],
        "config": {
            "families": args.families,
            "cells": cells.iter().map(|(n, np, m)| json!({"n": n, "n_prime": np, "m": m})).collect::<Vec<_>>(),
            "targets": args.targets,
            "seed": args.seed,
            "budget_seconds_per_call": args.budget_seconds,
            "repeats": args.repeats.max(1),
            "engines": described,
            "worker_threads": 1,
        },
        "cells_measured": measured.len(),
        "cells_skipped": skipped,
        "disagreements": disagreements,
        "elapsed_seconds": started.elapsed().as_secs_f64(),
        "markdown": format_engine_markdown(&measured),
        "cells": measured,
    }))
}
