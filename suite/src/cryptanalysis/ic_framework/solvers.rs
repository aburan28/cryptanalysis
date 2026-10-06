//! # Polynomial-system solvers, as plug-ins.
//!
//! The [`SystemSolver`] plug point takes a boolean system and returns
//! its solutions with a cost record.  It knows nothing about elliptic
//! curves, which is the point: a Gröbner implementer can work here
//! without reading a line of curve arithmetic, and the framework can
//! ask "what does this pipeline cost if the decomposition oracle solves
//! its systems with *that* engine instead" without touching anything
//! else.
//!
//! ## What ships here
//!
//! | name | engine | native unit |
//! |:--|:--|:--|
//! | `f4-f2` | Faugère's F4: batched pairs, symbolic preprocessing, bit-packed elimination, field pairs; a full reduced basis | word XORs (elimination only) |
//! | `buchberger-f2` | boolean-ring Buchberger with the coprime and chain criteria and the field-equation pairs, one pair at a time | monomial operations |
//! | `matrix-f4` | the Koblitz oracle's hybrid: Macaulay matrices to a fixed degree, then splitting | word XORs (elimination only) |
//! | `matrix-f5` | the same hybrid, rows the Boolean F5 criterion predicts to vanish left out | word XORs (elimination only) |
//! | `inherited-f4` | the same hybrid, children specialising their parent's reduced basis | word XORs (elimination, specialisation and linear elimination only) |
//! | `crossbred-f2` | Joux–Vitse: a Macaulay left kernel, then `2^k` linear solves | word operations (partial) |
//! | `xl-f2` | XL: multiply out to a degree, then linearise | monomial operations (modelled) |
//! | `sat-cdcl` | CDCL with Tseitin monomials; parity encoded as CNF by default, native XOR opt-in | conflicts |
//! | `fes-f2` | fast exhaustive search, libfes-lite Gray code, quadratic systems only | word XORs (Gray-code steps) |
//! | `fes-f2-wide` | the same over 8 or 16 sub-cubes per step in the lanes of an AVX2 or AVX-512 register, ≤ 32 equations | vector XORs (Gray-code steps) |
//! | `exhaustive` | evaluate every equation at every point, stopping at the first that fails | monomial tests |
//!
//! The exhaustive searches are not strawmen.  They are the
//! **reference** the others are measured against, in the sense
//! `AGENTS.md` §1 means: the best algorithm that already solves the same
//! problem, priced in the same unit on the same instances.  `fes-f2-wide`
//! is the strongest wherever it applies, `fes-f2` next — two XORs per
//! point of `{0,1}^n`, or per sixteen points in the vector form, against
//! a pass over the terms — and a solver that cannot beat the strongest
//! one on a cell has not earned its place in that cell, however good its
//! asymptotics are said to be.
//!
//! ## Why every unit here is qualified
//!
//! The framework prices a count at the calibrated word-XOR ratio only
//! when the unit is exactly `word XORs`, meaning the count covers the
//! engine's whole run.  None of these does: F4's elimination is under a
//! third of its wall time at twelve unknowns (the products, symbolic
//! preprocessing and packing are the rest), and the hybrids count their
//! eliminations but not their matrix builds.  Pricing either at the XOR
//! ratio would flatter it by an order of magnitude, so each names what
//! its count covers and the runner prices it by wall time instead.  The
//! native count stays in the report as the engine's own regression
//! measure.
//!
//! ## Adding an engine — F4, F5, or anything else
//!
//! Implement [`SystemSolver`] and register it in [`solver_registry`].
//! The contract is short and all of it matters:
//!
//! - **Count something.**  `SolverCost::ops` with an `op_unit` naming
//!   it.  Wall time is never the metric (`AGENTS.md` §6); an engine
//!   that reports only time cannot be compared across hosts and will
//!   not be accepted into the table as a speed.
//! - **Respect the budget.**  Return [`SolverVerdict::BudgetExceeded`],
//!   never a wrong answer and never an unbounded run.
//! - **Never guess `Unsatisfiable`.**  Say it only when the system is
//!   decided.  An engine that reports a timeout as "no solution"
//!   quietly lowers the hit rate of every relation phase built on it.
//! - **Report a degree if you have one.**  `solving_degree` is the
//!   highest degree at which the run learned something; it is the one
//!   comparable against a degree bound.  `degree_reached` may be higher
//!   and is a property of the strategy.
//!
//! See `docs/ic/FRAMEWORK.md` for a worked example of adding one.

use std::collections::BTreeMap;
use std::time::{Duration, Instant};

use super::stages::{BooleanSystem, Params, SolverCost, SolverVerdict, SystemShape, SystemSolver};
use crate::cryptanalysis::koblitz_groebner::{
    f4_word_ops_thread, solve_boolean_system, SolveOptions, SolverEngine, SplitRule,
};
use crate::cryptanalysis::pq_f4_f2::{groebner_basis_f4, solutions_from_reduced_basis};
use crate::cryptanalysis::pq_groebner_f2::{groebner_basis_f2_within, solve_system_f2, F2BoolPoly};
use crate::cryptanalysis::semaev_sat::XorEncoding;

/// The largest system `exhaustive` and the model-enumerating solvers
/// will attempt, since they are `2^n` in the variable count.
const ENUMERATION_CAP: usize = 26;

/// The largest system `xl-f2` will attempt.  The repository's XL runs
/// one pass at degree `n_vars`, so its matrix has `2^{n_vars}` columns
/// and it has no budget hook: on a 12-unknown, 13-equation descent it
/// measured about 150 seconds a call against Buchberger's 7
/// milliseconds on the same systems.  Declining above ten unknowns is
/// what keeps a sweep row from running for hours; the row is then
/// skipped and says why.
const XL_CAP: usize = 10;

fn is_one(gb: &[F2BoolPoly]) -> bool {
    gb.len() == 1 && gb[0].terms.len() == 1 && gb[0].terms[0].degree() == 0
}

/// Solutions of a system by direct evaluation, with the monomial tests
/// **performed**: a point stops at the first equation it fails, so the
/// count is the work done, not the `2^n · Σ_i |terms_i|` model an earlier
/// revision reported (which overstated the work by the short-circuit
/// factor and understated the per-test cost by the same factor).
fn points_satisfying(equations: &[F2BoolPoly], n_vars: usize) -> (Vec<u64>, u64) {
    let mut out = Vec::new();
    let mut tests = 0u64;
    for v in 0..1u64 << n_vars {
        let mut ok = true;
        for e in equations {
            tests += e.terms.len() as u64;
            if e.eval(v) != 0 {
                ok = false;
                break;
            }
        }
        if ok {
            out.push(v);
        }
    }
    (out, tests)
}

/// Check every returned point against the original equations, counting
/// the monomial tests.  An engine's answer is never trusted unchecked.
fn verified(points: Vec<u64>, system: &BooleanSystem, tests: &mut u64) -> Vec<u64> {
    points
        .into_iter()
        .filter(|&v| {
            system.equations.iter().all(|e| {
                *tests += e.terms.len() as u64;
                e.eval(v) == 0
            })
        })
        .collect()
}

// ── F4 ─────────────────────────────────────────────────────────────

/// Faugère's F4 over the boolean ring, computing the full reduced basis
/// ([`crate::cryptanalysis::pq_f4_f2`]), with the field pairs a boolean
/// basis needs and solutions read off the linear elements rather than
/// enumerated.
pub struct F4F2;

impl SystemSolver for F4F2 {
    fn name(&self) -> &str {
        "f4-f2"
    }

    fn describe(&self) -> String {
        "F4 over F_2[v]/(v²−v): normal strategy, Gebauer–Möller, field pairs, bit-packed elimination, reduced basis"
            .into()
    }

    fn accepts(&self, shape: &SystemShape) -> bool {
        shape.n_vars <= 64
    }

    fn solve(
        &self,
        system: &BooleanSystem,
        _params: &Params,
        budget: Option<Duration>,
    ) -> (SolverVerdict, SolverCost) {
        let started = Instant::now();
        let (gb, st) = groebner_basis_f4(system.equations.clone(), system.n_vars, budget);
        let mut tests = 0u64;
        let mut extra = BTreeMap::new();
        for (k, v) in [
            ("steps", st.steps),
            ("pairs_reduced", st.pairs_reduced),
            ("field_pairs_reduced", st.field_pairs_reduced),
            ("pairs_product_skipped", st.pairs_product_skipped),
            ("pairs_chain_skipped", st.pairs_chain_skipped),
            ("reducer_rows", st.reducer_rows),
            ("matrix_rows_max", st.matrix_rows_max),
            ("matrix_cols_max", st.matrix_cols_max),
            ("matrix_rows_sum", st.matrix_rows_sum),
            ("divisor_tests", st.divisor_tests),
            ("new_elements", st.new_elements),
            ("basis_len", st.basis_len),
            ("build_ns", st.build_ns),
            ("eliminate_ns", st.eliminate_ns),
            ("pairs_left", st.pairs_left),
            ("oversize", st.oversize as u64),
        ] {
            extra.insert(k.to_string(), v);
        }
        let mut cost = SolverCost {
            ops: st.word_xors,
            op_unit: "word XORs (elimination only)".into(),
            wall_ns: 0,
            peak_bytes: st.peak_matrix_bytes,
            degree_reached: Some(st.degree_reached),
            solving_degree: Some(st.solving_degree),
            timed_out: st.timed_out,
            extra,
        };
        let verdict = if st.timed_out || st.oversize {
            SolverVerdict::BudgetExceeded
        } else {
            match solutions_from_reduced_basis(&gb, system.n_vars, 24, &mut tests) {
                // More than 2^24 solutions, or not a reduced basis: never
                // guess, and never enumerate the whole space behind the
                // caller's back.
                None => SolverVerdict::BudgetExceeded,
                Some(points) => {
                    let points = verified(points, system, &mut tests);
                    if points.is_empty() {
                        SolverVerdict::Unsatisfiable
                    } else {
                        SolverVerdict::Solved(points)
                    }
                }
            }
        };
        cost.extra.insert("extraction_tests".into(), tests);
        cost.wall_ns = started.elapsed().as_nanos() as u64;
        (verdict, cost)
    }
}

// ── The Koblitz oracle's hybrid engines ────────────────────────────

/// Which of the hybrid engines of
/// [`crate::cryptanalysis::koblitz_groebner`] a plug-in runs.
#[derive(Clone, Copy)]
enum HybridKind {
    MatrixF4,
    MatrixF5,
    InheritedF4,
}

/// Macaulay matrices to a fixed degree, reduced with the bit-packed
/// kernels the Koblitz oracle is tuned on, propagation of every forced
/// variable, and a split on a free variable when the algebra stalls
/// ([`solve_boolean_system`]).  Not a Gröbner basis computation: the
/// matrices stop at `max_degree` and the tree does the rest, which is
/// why `solving_degree` is not reported and `degree_reached` is the
/// highest matrix built.
///
/// The run is bounded by the node budget and the matrix-size caps of
/// that module, not by a wall clock: it has no interrupt hook, and this
/// wrapper does not add one to a module another thread is tuning.
pub struct HybridF4 {
    kind: HybridKind,
}

impl HybridF4 {
    fn engine(&self, max_degree: u32) -> SolverEngine {
        match self.kind {
            HybridKind::MatrixF4 => SolverEngine::MatrixF4 { max_degree },
            HybridKind::MatrixF5 => SolverEngine::MatrixF5 { max_degree },
            HybridKind::InheritedF4 => SolverEngine::InheritedF4 { max_degree },
        }
    }
}

fn split_rule(name: &str) -> Result<SplitRule, String> {
    match name {
        "auto" => Ok(SplitRule::Auto),
        "lowest" => Ok(SplitRule::LowestFree),
        "highest" => Ok(SplitRule::HighestFree),
        "frequent" => Ok(SplitRule::MostFrequent),
        "mom" => Ok(SplitRule::MinTermWeight),
        other => Err(format!(
            "unknown split rule `{other}`; try auto, lowest, highest, frequent or mom"
        )),
    }
}

impl SystemSolver for HybridF4 {
    fn name(&self) -> &str {
        match self.kind {
            HybridKind::MatrixF4 => "matrix-f4",
            HybridKind::MatrixF5 => "matrix-f5",
            HybridKind::InheritedF4 => "inherited-f4",
        }
    }

    fn describe(&self) -> String {
        match self.kind {
            HybridKind::MatrixF4 => "boolean Macaulay matrices to a fixed degree, propagation, splitting (koblitz_groebner MatrixF4)",
            HybridKind::MatrixF5 => "the same with rows the Boolean F5 criterion predicts to vanish left out (MatrixF5)",
            HybridKind::InheritedF4 => "the same with each child specialising its parent's reduced basis (InheritedF4, the Koblitz oracle's default)",
        }
        .into()
    }

    fn parameters(&self) -> &[(&str, &str)] {
        &[
            (
                "max_degree",
                "highest Macaulay degree built before splitting (default 3)",
            ),
            (
                "split",
                "auto, lowest, highest, frequent or mom (default auto)",
            ),
            (
                "node_budget",
                "reductions before the run gives up (default 4096)",
            ),
        ]
    }

    fn accepts(&self, shape: &SystemShape) -> bool {
        shape.n_vars <= 64
    }

    fn solve(
        &self,
        system: &BooleanSystem,
        params: &Params,
        _budget: Option<Duration>,
    ) -> (SolverVerdict, SolverCost) {
        use crate::cryptanalysis::algebra_cache::{enabled, Layer};
        let started = Instant::now();
        let max_degree = params.u64_or("max_degree", 3).unwrap_or(3) as u32;
        let split = params.get("split").unwrap_or("auto");
        let opts = SolveOptions {
            engine: self.engine(max_degree),
            max_solutions: 1 << 20,
            node_budget: params.u64_or("node_budget", 4096).unwrap_or(4096) as usize,
            split_rule: split_rule(split).unwrap_or(SplitRule::Auto),
        };
        // The module's environment switches can change the engine; the
        // report says so rather than labelling one engine's cost as
        // another's.
        let resolved = opts.resolve();
        let before = f4_word_ops_thread();
        let (points, st) = solve_boolean_system(&system.equations, system.n_vars, &opts);
        let ops = f4_word_ops_thread().wrapping_sub(before);
        let mut tests = 0u64;
        let points = verified(points, system, &mut tests);
        let mut extra = BTreeMap::new();
        for (k, v) in [
            ("reductions", st.reductions as u64),
            ("infeasible_branches", st.infeasible_branches as u64),
            ("propagations", st.propagations as u64),
            ("splits", st.splits as u64),
            ("eliminated", st.eliminated as u64),
            ("oversize", st.oversize as u64),
            ("max_degree", max_degree as u64),
            ("verification_tests", tests),
            (
                "engine_overridden_by_environment",
                (format!("{:?}", resolved.engine) != format!("{:?}", opts.engine)) as u64,
            ),
            ("reduction_cache_on", enabled(Layer::ExactReduction) as u64),
        ] {
            extra.insert(k.to_string(), v);
        }
        let cost = SolverCost {
            ops,
            op_unit: match self.kind {
                HybridKind::InheritedF4 => {
                    "word XORs (elimination, specialisation and linear elimination only)"
                }
                _ => "word XORs (elimination only)",
            }
            .into(),
            wall_ns: started.elapsed().as_nanos() as u64,
            peak_bytes: 0,
            degree_reached: Some(st.max_degree_built),
            solving_degree: None,
            timed_out: st.exhausted,
            extra,
        };
        let verdict = if st.exhausted {
            SolverVerdict::BudgetExceeded
        } else if points.is_empty() {
            SolverVerdict::Unsatisfiable
        } else {
            SolverVerdict::Solved(points)
        };
        (verdict, cost)
    }
}

// ── Crossbred ──────────────────────────────────────────────────────

/// Joux–Vitse crossbred ([`crate::cryptanalysis::crossbred`]): the left
/// kernel of a degree-`D` Macaulay matrix restricted to the columns of
/// degree above one in the last `n − k` variables, then a bit-sliced
/// sweep of the first `k` and a linear solve per surviving point.  Its
/// parameters decide whether it applies at all; the defaults are the
/// module's, not a tuning, and a system they do not fit is reported as
/// over budget, never as unsatisfiable.
pub struct CrossbredF2;

impl SystemSolver for CrossbredF2 {
    fn name(&self) -> &str {
        "crossbred-f2"
    }

    fn describe(&self) -> String {
        "Joux–Vitse crossbred: Macaulay left kernel at degree D, then 2^k bit-sliced linear solves"
            .into()
    }

    fn parameters(&self) -> &[(&str, &str)] {
        &[
            ("D", "Macaulay degree of the preprocessing (default 3)"),
            ("k", "variables enumerated (default 8, capped at n − 1)"),
            (
                "max_rows",
                "Macaulay rows the preprocessing may build (default 4000)",
            ),
            (
                "max_kernel_dim",
                "affine solution space enumerated per point (default 12)",
            ),
        ]
    }

    fn accepts(&self, shape: &SystemShape) -> bool {
        shape.n_vars >= 2 && shape.n_vars <= 64
    }

    fn solve(
        &self,
        system: &BooleanSystem,
        params: &Params,
        _budget: Option<Duration>,
    ) -> (SolverVerdict, SolverCost) {
        use crate::cryptanalysis::crossbred::{
            extract_crossbred, solve_crossbred, CrossbredParams, SearchOptions,
        };
        let started = Instant::now();
        let n = system.n_vars;
        let xp = CrossbredParams {
            macaulay_degree: params.u64_or("D", 3).unwrap_or(3) as u32,
            enumerated: (params.u64_or("k", 8).unwrap_or(8) as usize).min(n - 1),
            target_degree: 1,
            max_rows: params.u64_or("max_rows", 4000).unwrap_or(4000) as usize,
        };
        let opts = SearchOptions {
            max_solutions: 0,
            max_kernel_dim: params.u64_or("max_kernel_dim", 12).unwrap_or(12) as u32,
            ..SearchOptions::default()
        };
        let mut extra = BTreeMap::new();
        let (verdict, ops) = match extract_crossbred(&system.equations, n, &xp) {
            None => (SolverVerdict::BudgetExceeded, 0),
            Some(xb) => {
                let (points, ss) = solve_crossbred(&system.equations, &xb, &opts);
                for (k, v) in [
                    ("macaulay_rows", xb.stats.macaulay_rows as u64),
                    ("macaulay_cols", xb.stats.macaulay_cols as u64),
                    ("kernel_dim", xb.stats.kernel_dim as u64),
                    ("filters", xb.stats.filters as u64),
                    ("points", ss.points),
                    ("survivors", ss.survivors),
                    ("linear_solves", ss.linear_solves),
                    ("solve_row_ops", ss.solve_row_ops),
                    ("exhausted", ss.exhausted as u64),
                ] {
                    extra.insert(k.to_string(), v);
                }
                let ops = xb.stats.word_ops + ss.transform_word_ops + ss.filter_word_ops;
                if ss.exhausted {
                    (SolverVerdict::BudgetExceeded, ops)
                } else if points.is_empty() {
                    (SolverVerdict::Unsatisfiable, ops)
                } else {
                    (SolverVerdict::Solved(points), ops)
                }
            }
        };
        let cost = SolverCost {
            ops,
            op_unit: "word operations (partial: extraction, transform and filter; per-point solves in solve_row_ops)".into(),
            wall_ns: started.elapsed().as_nanos() as u64,
            peak_bytes: 0,
            degree_reached: Some(xp.macaulay_degree),
            solving_degree: None,
            timed_out: matches!(verdict, SolverVerdict::BudgetExceeded),
            extra,
        };
        (verdict, cost)
    }
}

// ── Fast exhaustive search ─────────────────────────────────────────

/// Bouillaguet et al.'s fast exhaustive search in the libfes-lite form
/// ([`crate::cryptanalysis::mq_fes::gray_incremental_find_all`]): all
/// equations packed one bit each into a word, the points of `{0,1}^n` in
/// Gray-code order, two word XORs per point.  Quadratic systems only —
/// the two-summand descents — with at most 64 equations and 32 unknowns.
pub struct FesF2;

impl SystemSolver for FesF2 {
    fn name(&self) -> &str {
        "fes-f2"
    }

    fn describe(&self) -> String {
        "fast exhaustive search (libfes-lite Gray code): two word XORs per point, quadratic systems only".into()
    }

    fn accepts(&self, shape: &SystemShape) -> bool {
        (1..=32).contains(&shape.n_vars)
            && shape.n_equations <= 64
            && shape.degrees.iter().all(|&d| d <= 2)
    }

    fn solve(
        &self,
        system: &BooleanSystem,
        _params: &Params,
        _budget: Option<Duration>,
    ) -> (SolverVerdict, SolverCost) {
        use crate::cryptanalysis::mq_fes::{gray_incremental_find_all, QuadraticForm};
        let started = Instant::now();
        let n = system.n_vars;
        let forms: Option<Vec<QuadraticForm>> = system
            .equations
            .iter()
            .map(|p| {
                let mut q = QuadraticForm::from_poly(p)?;
                // `from_poly` sizes the form by the polynomial's own
                // variable count; the search needs the system's.
                if q.n != n {
                    q = QuadraticForm::from_anf_row(
                        &crate::cryptanalysis::wdsat_oracle::AnfRow::from_poly(p),
                        n,
                    )?;
                }
                Some(q)
            })
            .collect();
        let setup: u64 = forms
            .as_ref()
            .map(|fs| {
                fs.iter()
                    .map(|f| {
                        f.constant as u64
                            + f.linear.iter().filter(|&&b| b).count() as u64
                            + f.quad.iter().flatten().filter(|&&b| b).count() as u64
                    })
                    .sum()
            })
            .unwrap_or(0);
        let found = forms
            .as_deref()
            .and_then(|fs| gray_incremental_find_all(fs, usize::MAX));
        let mut tests = 0u64;
        let mut extra = BTreeMap::new();
        extra.insert("points".into(), 1u64 << n);
        let (verdict, ops) = match found {
            None => (SolverVerdict::BudgetExceeded, 0),
            Some(points) => {
                let points = verified(points, system, &mut tests);
                // Two XORs per Gray-code step, one step per point, plus
                // one per coefficient scattered into the tables.
                let ops = 2 * (1u64 << n) + setup;
                if points.is_empty() {
                    (SolverVerdict::Unsatisfiable, ops)
                } else {
                    (SolverVerdict::Solved(points), ops)
                }
            }
        };
        extra.insert("verification_tests".into(), tests);
        let cost = SolverCost {
            ops,
            op_unit: "word XORs (Gray-code steps)".into(),
            wall_ns: started.elapsed().as_nanos() as u64,
            peak_bytes: 0,
            degree_reached: None,
            solving_degree: None,
            timed_out: false,
            extra,
        };
        (verdict, cost)
    }
}

/// The same search with the last three or four unknowns fixed per
/// 32-bit lane of a vector register, so one Gray-code walk enumerates 8
/// (AVX2) or 16 (AVX-512) sub-cubes at once
/// ([`crate::cryptanalysis::mq_fes::gray_find_all_wide`]): the vector form
/// of libfes-lite's enumeration.  It is the strongest exhaustive search
/// this host runs for the shape: the lanes wherever the host has the
/// instructions and the system fits them (at most 32 equations, one per
/// lane bit, and enough unknowns for the unrolled walk), the scalar
/// [`FesF2`] otherwise, and the unit it reports says which ran.
pub struct FesWide;

impl SystemSolver for FesWide {
    fn name(&self) -> &str {
        "fes-f2-wide"
    }

    fn describe(&self) -> String {
        "fast exhaustive search over 8 (AVX2) or 16 (AVX-512) sub-cubes per Gray-code step, the first 32 equations in the lanes and the rest as a filter; the scalar search where the lanes do not fit: quadratic systems".into()
    }

    fn accepts(&self, shape: &SystemShape) -> bool {
        if FesF2.accepts(shape) {
            return true;
        }
        // Past the scalar walk's 32 unknowns the lanes still reach: the
        // walk covers only the `n − k` unknowns the lanes do not fix.
        let Some(lanes) = crate::cryptanalysis::mq_fes::wide_lanes() else {
            return false;
        };
        let k = lanes.trailing_zeros() as usize;
        // More than 32 equations: the lanes walk the first 32 and the
        // rest filter the candidates (see `solve`).
        shape.n_vars <= 32 + k && shape.degrees.iter().all(|&d| d <= 2)
    }

    fn solve(
        &self,
        system: &BooleanSystem,
        params: &Params,
        budget: Option<Duration>,
    ) -> (SolverVerdict, SolverCost) {
        use crate::cryptanalysis::mq_fes::{gray_find_all_wide, QuadraticForm};
        let started = Instant::now();
        let n = system.n_vars;
        let forms: Option<Vec<QuadraticForm>> = system
            .equations
            .iter()
            .map(|p| {
                QuadraticForm::from_anf_row(
                    &crate::cryptanalysis::wdsat_oracle::AnfRow::from_poly(p),
                    n,
                )
            })
            .collect();
        // A lane holds 32 equations.  With more, the walk enumerates the
        // roots of the first 32 — a superset of the system's — and every
        // candidate is checked against all the equations below, as
        // libfes does: about `2^{n−32}` spurious candidates per call.
        let found = forms
            .as_deref()
            .and_then(|fs| gray_find_all_wide(&fs[..fs.len().min(32)], usize::MAX));
        let Some((candidates, lanes)) = found else {
            // No lanes on this host, or a system the lanes do not fit:
            // the scalar walk, which reports its own unit.
            return FesF2.solve(system, params, budget);
        };
        let mut tests = 0u64;
        let candidate_count = candidates.len() as u64;
        let points = verified(candidates, system, &mut tests);
        let mut extra = BTreeMap::new();
        extra.insert("points".into(), 1u64 << n);
        extra.insert("lanes".into(), lanes as u64);
        extra.insert("candidates".into(), candidate_count);
        extra.insert("verification_tests".into(), tests);
        let cost = SolverCost {
            // Two vector XORs per Gray-code step, one step per `lanes`
            // points; the per-lane table setup is negligible beside it.
            ops: 2 * ((1u64 << n) / lanes as u64),
            op_unit: format!("vector XORs (Gray-code steps, {lanes} lanes of 32 bits)"),
            wall_ns: started.elapsed().as_nanos() as u64,
            peak_bytes: 0,
            degree_reached: None,
            solving_degree: None,
            timed_out: false,
            extra,
        };
        if points.is_empty() {
            (SolverVerdict::Unsatisfiable, cost)
        } else {
            (SolverVerdict::Solved(points), cost)
        }
    }
}

// ── Buchberger over the boolean ring ───────────────────────────────

/// The repository's boolean-ring Buchberger, with the coprime and
/// chain criteria under the normal selection strategy.
pub struct BuchbergerF2;

impl SystemSolver for BuchbergerF2 {
    fn name(&self) -> &str {
        "buchberger-f2"
    }

    fn describe(&self) -> String {
        "Buchberger over F_2[v]/(v²−v), DegRevLex, normal selection, coprime and chain criteria"
            .into()
    }

    fn accepts(&self, shape: &SystemShape) -> bool {
        shape.n_vars <= 64
    }

    fn solve(
        &self,
        system: &BooleanSystem,
        _params: &Params,
        budget: Option<Duration>,
    ) -> (SolverVerdict, SolverCost) {
        let (gb, st) = groebner_basis_f2_within(system.equations.clone(), system.n_vars, budget);
        let mut extra = BTreeMap::new();
        extra.insert("spolys".into(), st.spolys);
        extra.insert("reduction_steps".into(), st.reduction_steps);
        extra.insert("pairs_coprime_skipped".into(), st.pairs_coprime_skipped);
        extra.insert("pairs_chain_skipped".into(), st.pairs_chain_skipped);
        extra.insert("basis_len".into(), st.basis_len);
        extra.insert("pairs_left".into(), st.pairs_left);
        let cost = SolverCost {
            ops: st.mono_ops,
            op_unit: "monomial operations".into(),
            wall_ns: st.wall_ns,
            peak_bytes: st.peak_bytes(),
            degree_reached: Some(st.max_pair_degree),
            solving_degree: Some(st.solving_degree),
            timed_out: st.timed_out,
            extra,
        };
        if st.timed_out {
            return (SolverVerdict::BudgetExceeded, cost);
        }
        if is_one(&gb) {
            return (SolverVerdict::Unsatisfiable, cost);
        }
        if system.n_vars > ENUMERATION_CAP {
            // The basis is correct but this module extracts solutions by
            // enumeration, which is not affordable here.  Saying so is
            // better than reporting no solutions.
            return (SolverVerdict::BudgetExceeded, cost);
        }
        let solutions = solve_system_f2(&gb, system.n_vars);
        if solutions.is_empty() {
            (SolverVerdict::Unsatisfiable, cost)
        } else {
            (SolverVerdict::Solved(solutions), cost)
        }
    }
}

// ── XL ─────────────────────────────────────────────────────────────

/// XL (Courtois–Klimov–Patarin–Shamir): multiply the system out to a
/// degree, then linearise.  Scales better than Buchberger on the wider
/// boolean systems and worse on the narrow ones, which is the whole
/// reason to be able to switch between them.
pub struct XlF2;

impl SystemSolver for XlF2 {
    fn name(&self) -> &str {
        "xl-f2"
    }

    fn describe(&self) -> String {
        "XL over F_2: multiply to a degree bound, linearise, solve".into()
    }

    fn accepts(&self, shape: &SystemShape) -> bool {
        shape.n_vars <= XL_CAP
    }

    fn solve(
        &self,
        system: &BooleanSystem,
        _params: &Params,
        _budget: Option<Duration>,
    ) -> (SolverVerdict, SolverCost) {
        // The XL implementation has no interrupt hook, so the budget is
        // enforced by `accepts` and by the caller's cell sizing rather
        // than mid-run.  That is stated rather than hidden: a long XL
        // call will run to completion.
        let started = Instant::now();
        let solutions =
            crate::cryptanalysis::pq_xl::boolean_xl_solve(system.equations.clone(), system.n_vars);
        let terms: u64 = system.equations.iter().map(|p| p.terms.len() as u64).sum();
        let cost = SolverCost {
            // XL's work is dominated by the linearised elimination; the
            // term count times the expansion is the honest proxy this
            // implementation can report exactly.
            ops: terms * (system.n_vars as u64).pow(2),
            op_unit: "monomial operations (modelled)".into(),
            wall_ns: started.elapsed().as_nanos() as u64,
            peak_bytes: 0,
            degree_reached: None,
            solving_degree: None,
            timed_out: false,
            extra: BTreeMap::new(),
        };
        if solutions.is_empty() {
            (SolverVerdict::Unsatisfiable, cost)
        } else {
            (SolverVerdict::Solved(solutions), cost)
        }
    }
}

// ── CDCL ───────────────────────────────────────────────────────────

/// Validate a solver's configuration before a timed run. The solver trait
/// cannot return configuration errors, so its own call repeats the check as
/// a fail-fast invariant.
pub fn validate_solver_params(name: &str, params: &Params) -> Result<(), String> {
    if name == "sat-cdcl" {
        sat_xor_encoding(params)?;
    }
    Ok(())
}

fn sat_xor_encoding(params: &Params) -> Result<XorEncoding, String> {
    match params.get("sat_xor_encoding") {
        None | Some("cnf") => Ok(XorEncoding::Cnf),
        Some("native") => Ok(XorEncoding::Native),
        Some(other) => Err(format!(
            "invalid sat_xor_encoding `{other}`; expected cnf or native"
        )),
    }
}

/// The repository's CDCL solver, with one Tseitin auxiliary per
/// monomial of degree at least two. Parity is CNF-expanded by default
/// for historical reproducibility; `sat_xor_encoding=native` opts into
/// the solver's native XOR rows.
pub struct SatCdcl;

impl SystemSolver for SatCdcl {
    fn name(&self) -> &str {
        "sat-cdcl"
    }

    fn describe(&self) -> String {
        "CDCL with Tseitin monomial definitions and CNF parity by default (native XOR opt-in)"
            .into()
    }

    fn parameters(&self) -> &[(&str, &str)] {
        &[
            (
                "sat_conflict_budget",
                "conflicts before the solver gives up (default 200000)",
            ),
            (
                "sat_xor_encoding",
                "cnf (historical default) or native; recorded in cost.extra",
            ),
        ]
    }

    fn accepts(&self, shape: &SystemShape) -> bool {
        shape.n_vars <= 64
    }

    /// One model per call: a first-solution search.
    fn finds_every_solution(&self) -> bool {
        false
    }

    fn solve(
        &self,
        system: &BooleanSystem,
        params: &Params,
        _budget: Option<Duration>,
    ) -> (SolverVerdict, SolverCost) {
        use crate::cryptanalysis::sat::SolveResult;
        let encoding = sat_xor_encoding(params)
            .expect("sat-cdcl configuration must be validated before a timed solve");
        let started = Instant::now();
        let mut enc = crate::cryptanalysis::semaev_sat::encode_boolean_system_with(
            system.n_vars,
            &system.equations,
            &[],
            encoding,
        );
        enc.solver.conflict_budget = params
            .u64_or("sat_conflict_budget", 200_000)
            .unwrap_or(200_000);
        let verdict = if enc.trivially_unsat {
            SolveResult::Unsat
        } else {
            enc.solver.solve()
        };
        let st = &enc.solver.stats;
        let mut extra = BTreeMap::new();
        extra.insert("decisions".into(), st.decisions);
        extra.insert("propagations".into(), st.propagations);
        extra.insert("restarts".into(), st.restarts);
        extra.insert("learnt_clauses".into(), st.learnt_clauses);
        extra.insert("xor_propagations".into(), st.xor_propagations);
        extra.insert(
            "native_xor_encoding".into(),
            u64::from(encoding == XorEncoding::Native),
        );
        extra.insert("native_xor_rows".into(), enc.solver.n_xors() as u64);
        extra.insert(
            "original_clauses".into(),
            enc.solver.n_original_clauses() as u64,
        );
        let cost = SolverCost {
            ops: st.conflicts,
            op_unit: "conflicts".into(),
            wall_ns: started.elapsed().as_nanos() as u64,
            peak_bytes: 0,
            degree_reached: None,
            solving_degree: None,
            timed_out: matches!(verdict, SolveResult::Unknown),
            extra,
        };
        match verdict {
            SolveResult::Sat => (SolverVerdict::Solved(vec![enc.model_assignment()]), cost),
            SolveResult::Unsat => (SolverVerdict::Unsatisfiable, cost),
            SolveResult::Unknown => (SolverVerdict::BudgetExceeded, cost),
        }
    }
}

// ── Exhaustive search, the reference ───────────────────────────────

/// Evaluate the equations at every point of `{0,1}^n`, moving to the
/// next point at the first equation that fails.
///
/// The general-degree reference: it needs nothing of the system but
/// the ability to evaluate it, so it applies where `fes-f2` does not
/// (the degree-six three-summand descents).  Its count is the monomial
/// tests performed, at most `2^n · Σ_i |terms_i|`.
pub struct Exhaustive;

impl SystemSolver for Exhaustive {
    fn name(&self) -> &str {
        "exhaustive"
    }

    fn describe(&self) -> String {
        "evaluate every equation at every point of {0,1}^n — the reference, not a strawman".into()
    }

    fn accepts(&self, shape: &SystemShape) -> bool {
        shape.n_vars <= ENUMERATION_CAP
    }

    fn solve(
        &self,
        system: &BooleanSystem,
        _params: &Params,
        _budget: Option<Duration>,
    ) -> (SolverVerdict, SolverCost) {
        let started = Instant::now();
        let (solutions, ops) = points_satisfying(&system.equations, system.n_vars);
        let cost = SolverCost {
            ops,
            op_unit: "monomial tests".into(),
            wall_ns: started.elapsed().as_nanos() as u64,
            peak_bytes: 0,
            degree_reached: None,
            solving_degree: None,
            timed_out: false,
            extra: BTreeMap::new(),
        };
        if solutions.is_empty() {
            (SolverVerdict::Unsatisfiable, cost)
        } else {
            (SolverVerdict::Solved(solutions), cost)
        }
    }
}

/// Every solver the framework knows, by name.
pub fn solver_registry() -> Vec<Box<dyn SystemSolver>> {
    vec![
        Box::new(F4F2),
        Box::new(BuchbergerF2),
        Box::new(HybridF4 {
            kind: HybridKind::MatrixF4,
        }),
        Box::new(HybridF4 {
            kind: HybridKind::MatrixF5,
        }),
        Box::new(HybridF4 {
            kind: HybridKind::InheritedF4,
        }),
        Box::new(CrossbredF2),
        Box::new(XlF2),
        Box::new(SatCdcl),
        Box::new(FesF2),
        Box::new(FesWide),
        Box::new(Exhaustive),
    ]
}

/// Look one up.
pub fn solver_by_name(name: &str) -> Result<Box<dyn SystemSolver>, String> {
    let registry = solver_registry();
    let known: Vec<String> = registry.iter().map(|s| s.name().to_string()).collect();
    registry
        .into_iter()
        .find(|s| s.name() == name)
        .ok_or_else(|| format!("unknown solver `{name}`; known: {}", known.join(", ")))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::pq_groebner_f2::{F2BoolMono, F2BoolPoly};

    /// `v0 + v1`, `v0·v1 + v1` — solutions are `v0 = v1 = 0` and
    /// `v0 = v1 = 1`, i.e. masks 0 and 3.
    fn fixture() -> BooleanSystem {
        let m = F2BoolMono::from_mask;
        BooleanSystem {
            equations: vec![
                F2BoolPoly::from_monos(vec![m(1), m(2)], 2),
                F2BoolPoly::from_monos(vec![m(3), m(2)], 2),
            ],
            n_vars: 2,
        }
    }

    /// Keep the historical CNF default distinct from an explicitly
    /// selected native-XOR arm, and check both against the same system.
    #[test]
    fn sat_cdcl_parity_modes_are_equivalent_and_reported() {
        let sys = fixture();
        let mut cnf = Params::default();
        cnf.set("sat_xor_encoding", "cnf");
        let mut native = Params::default();
        native.set("sat_xor_encoding", "native");
        let reference: std::collections::BTreeSet<u64> = [0, 3].into_iter().collect();
        for (params, expected_native) in [(Params::default(), false), (cnf, false), (native, true)]
        {
            let (verdict, cost) = SatCdcl.solve(&sys, &params, None);
            let SolverVerdict::Solved(points) = verdict else {
                panic!("selected SAT encoding failed to solve the fixture: {verdict:?}");
            };
            assert!(points.iter().all(|point| reference.contains(point)));
            assert_eq!(
                cost.extra["native_xor_encoding"],
                u64::from(expected_native)
            );
            assert_eq!(cost.extra["native_xor_rows"] > 0, expected_native);
            assert!(cost.extra["original_clauses"] > 0);
        }

        let m = F2BoolMono::from_mask;
        let inconsistent = BooleanSystem {
            equations: vec![
                F2BoolPoly::from_monos(vec![m(1)], 1),
                F2BoolPoly::from_monos(vec![m(1), m(0)], 1),
            ],
            n_vars: 1,
        };
        for mode in ["cnf", "native"] {
            let mut params = Params::default();
            params.set("sat_xor_encoding", mode);
            assert!(matches!(
                SatCdcl.solve(&inconsistent, &params, None).0,
                SolverVerdict::Unsatisfiable
            ));
        }
        let mut invalid = Params::default();
        invalid.set("sat_xor_encoding", "nativ");
        assert!(validate_solver_params("sat-cdcl", &invalid).is_err());
        assert!(std::panic::catch_unwind(|| SatCdcl.solve(&sys, &invalid, None)).is_err());
    }

    /// **Every engine must agree on the answer.**  A framework whose
    /// plug points disagree is not measuring the same problem, and the
    /// column that compares them would be meaningless.
    #[test]
    fn every_solver_finds_the_same_solution_set() {
        let sys = fixture();
        let reference: std::collections::BTreeSet<u64> =
            match Exhaustive.solve(&sys, &Params::default(), None).0 {
                SolverVerdict::Solved(v) => v.into_iter().collect(),
                other => panic!("the reference must solve the fixture, got {other:?}"),
            };
        assert_eq!(reference, [0u64, 3].into_iter().collect());

        for solver in solver_registry() {
            // The CDCL solver returns one model rather than all of
            // them, so it is checked for membership, not equality.
            let (verdict, cost) = solver.solve(&sys, &Params::default(), None);
            match verdict {
                SolverVerdict::Solved(found) => {
                    assert!(
                        !found.is_empty(),
                        "{}: solved with no solutions",
                        solver.name()
                    );
                    for f in &found {
                        assert!(
                            reference.contains(f),
                            "{} returned {f}, which is not a solution",
                            solver.name()
                        );
                    }
                    if solver.name() != "sat-cdcl" {
                        let got: std::collections::BTreeSet<u64> = found.into_iter().collect();
                        assert_eq!(got, reference, "{} missed a solution", solver.name());
                    }
                }
                other => panic!("{} said {other:?} on a satisfiable system", solver.name()),
            }
            assert!(
                !cost.op_unit.is_empty(),
                "{} must name the unit it counts",
                solver.name()
            );
        }
    }

    /// An unsatisfiable system must be reported as unsatisfiable by
    /// every engine, never as a budget failure and never as solved.
    #[test]
    fn every_solver_refutes_an_unsatisfiable_system() {
        let m = F2BoolMono::from_mask;
        // v0 = 0 and v0 = 1 at once.
        let sys = BooleanSystem {
            equations: vec![
                F2BoolPoly::from_monos(vec![m(1)], 1),
                F2BoolPoly::from_monos(vec![m(1), m(0)], 1),
            ],
            n_vars: 1,
        };
        for solver in solver_registry() {
            let (verdict, _) = solver.solve(&sys, &Params::default(), None);
            assert!(
                matches!(verdict, SolverVerdict::Unsatisfiable),
                "{} said {verdict:?} on an unsatisfiable system",
                solver.name()
            );
        }
    }

    /// **With more equations than a lane holds**, the vector search
    /// walks the first 32 and filters with the rest; the answer must be
    /// exactly the scalar search's, which packs up to 64 in a word.
    #[test]
    fn the_wide_search_filters_the_equations_past_a_lane() {
        use rand::{Rng, SeedableRng};
        if crate::cryptanalysis::mq_fes::wide_lanes().is_none() {
            return;
        }
        let mut rng = rand::rngs::StdRng::seed_from_u64(33);
        for trial in 0..12usize {
            let n = 10 + trial % 7;
            let m = 33 + trial * 2;
            let planted: u64 = rng.gen::<u64>() & ((1u64 << n) - 1);
            let mut sys = random_quadratic(n, m, &mut rng);
            // Make `planted` a root so the answer is never trivially empty.
            for e in &mut sys.equations {
                if e.eval(planted) != 0 {
                    *e = e.add(&F2BoolPoly::one(n));
                }
            }
            let shape = sys.shape();
            assert!(FesWide.accepts(&shape) && FesF2.accepts(&shape));
            let (wide, cost) = FesWide.solve(&sys, &Params::default(), None);
            let (scalar, _) = FesF2.solve(&sys, &Params::default(), None);
            let sorted = |v: SolverVerdict| match v {
                SolverVerdict::Solved(mut s) => {
                    s.sort_unstable();
                    s
                }
                other => panic!("trial {trial}: {other:?} on a system with a planted root"),
            };
            let (wide, scalar) = (sorted(wide), sorted(scalar));
            assert!(scalar.contains(&planted));
            assert_eq!(wide, scalar, "trial {trial} (n = {n}, m = {m})");
            assert!(
                cost.op_unit.starts_with("vector XORs"),
                "the lanes ran: {}",
                cost.op_unit
            );
        }
    }

    #[test]
    fn the_registry_resolves_every_name_it_advertises() {
        for solver in solver_registry() {
            let name = solver.name().to_string();
            assert_eq!(solver_by_name(&name).unwrap().name(), name);
        }
        assert!(solver_by_name("f5").is_err());
    }

    fn random_quadratic(n: usize, m: usize, rng: &mut impl rand::Rng) -> BooleanSystem {
        let equations = (0..m)
            .map(|_| {
                let mut monos = Vec::new();
                for i in 0..n {
                    for j in 0..i {
                        if rng.gen_bool(0.5) {
                            monos.push(F2BoolMono::from_mask((1u64 << i) | (1 << j)));
                        }
                    }
                    if rng.gen_bool(0.5) {
                        monos.push(F2BoolMono::from_mask(1u64 << i));
                    }
                }
                if rng.gen_bool(0.5) {
                    monos.push(F2BoolMono::from_mask(0));
                }
                F2BoolPoly::from_monos(monos, n)
            })
            .collect();
        BooleanSystem {
            equations,
            n_vars: n,
        }
    }

    /// Hold every engine that answers to the reference's answer on one
    /// system.  An engine may decline or run out of budget — that is not
    /// a wrong answer — but a verdict it gives must be the right one,
    /// and every engine but CDCL (one model) must return every solution.
    fn agree_with_the_reference(sys: &BooleanSystem, label: &str) -> usize {
        let reference: std::collections::BTreeSet<u64> =
            match Exhaustive.solve(sys, &Params::default(), None).0 {
                SolverVerdict::Solved(v) => v.into_iter().collect(),
                SolverVerdict::Unsatisfiable => Default::default(),
                other => panic!("{label}: the reference must decide, got {other:?}"),
            };
        let mut answered = 0;
        for solver in solver_registry() {
            if !solver.accepts(&sys.shape()) {
                continue;
            }
            let (verdict, cost) =
                solver.solve(sys, &Params::default(), Some(Duration::from_secs(60)));
            match verdict {
                SolverVerdict::Solved(found) => {
                    answered += 1;
                    assert!(
                        !reference.is_empty(),
                        "{label}: {} solved an inconsistent system",
                        solver.name()
                    );
                    let got: std::collections::BTreeSet<u64> = found.into_iter().collect();
                    assert!(
                        got.is_subset(&reference),
                        "{label}: {} returned a non-solution",
                        solver.name()
                    );
                    if solver.name() != "sat-cdcl" {
                        assert_eq!(
                            got,
                            reference,
                            "{label}: {} missed a solution",
                            solver.name()
                        );
                    }
                }
                SolverVerdict::Unsatisfiable => {
                    answered += 1;
                    assert!(
                        reference.is_empty(),
                        "{label}: {} refuted a satisfiable system",
                        solver.name()
                    );
                }
                SolverVerdict::BudgetExceeded => {}
            }
            assert!(!cost.op_unit.is_empty());
        }
        answered
    }

    /// **The new engines against the reference, on random quadratic
    /// systems** of two to eleven unknowns, consistent and not.  (Dense
    /// random systems are far harder for Buchberger than descents of the
    /// same size, which is what bounds the size here.)
    #[test]
    fn every_engine_agrees_on_random_quadratic_systems() {
        use rand::SeedableRng;
        let mut rng = rand::rngs::StdRng::seed_from_u64(20260922);
        for trial in 0..40usize {
            let n = 2 + trial % 10;
            let m = (n + trial % 3).saturating_sub(1).max(1);
            let sys = random_quadratic(n, m, &mut rng);
            let answered =
                agree_with_the_reference(&sys, &format!("trial {trial} (n = {n}, m = {m})"));
            assert!(
                answered >= 5,
                "trial {trial}: only {answered} engines answered"
            );
        }
    }

    /// **And on the systems the framework actually solves**: two- and
    /// three-summand Weil descents of random targets.  The three-summand
    /// one is kept at `n' = 2`: at `n' = 3` its degree-six system cost
    /// the pair-only Buchberger about twenty seconds a target (§14.4).
    #[test]
    fn every_engine_agrees_on_descent_systems() {
        use crate::cryptanalysis::ic_boundary::random_binary_instance;
        use crate::cryptanalysis::pq_descent_symbolic::descend;
        use rand::{Rng, SeedableRng};
        let mut rng = rand::rngs::StdRng::seed_from_u64(7);
        for &(n, np, m, seed) in &[
            (7u32, 4u32, 2u32, 1u64),
            (9, 5, 2, 2),
            (11, 6, 2, 3),
            (7, 2, 3, 4),
        ] {
            let inst = random_binary_instance(n, seed, 1 << 20).unwrap();
            let words: Vec<u64> = (0..np).map(|k| 1u64 << k).collect();
            for t in 0..3 {
                let x_r = rng.gen::<u64>() & ((1u64 << n) - 1);
                let d = descend(&inst.gf, inst.b, x_r, &words, m).unwrap();
                let sys = BooleanSystem {
                    equations: d.equations,
                    n_vars: d.n_vars,
                };
                agree_with_the_reference(&sys, &format!("n = {n}, n' = {np}, m = {m}, target {t}"));
            }
        }
    }

    /// **The fast exhaustive search is exhaustive**, at every size its
    /// Gray-code tables handle, including the small ones where it takes
    /// its unrolling-free path.
    #[test]
    fn fes_finds_exactly_the_solutions_at_every_size() {
        use rand::SeedableRng;
        let mut rng = rand::rngs::StdRng::seed_from_u64(11);
        for n in 1..=18usize {
            for _ in 0..3 {
                let sys = random_quadratic(n, n.saturating_sub(1).max(1), &mut rng);
                let (fes, cost) = FesF2.solve(&sys, &Params::default(), None);
                let (reference, _) = Exhaustive.solve(&sys, &Params::default(), None);
                let as_set = |v: &SolverVerdict| -> std::collections::BTreeSet<u64> {
                    match v {
                        SolverVerdict::Solved(p) => p.iter().copied().collect(),
                        SolverVerdict::Unsatisfiable => Default::default(),
                        other => panic!("n = {n}: undecided {other:?}"),
                    }
                };
                assert_eq!(as_set(&fes), as_set(&reference), "n = {n}");
                assert!(cost.ops >= 2 << n, "n = {n}: two XORs per point");
            }
        }
    }

    /// The exhaustive count is the work performed: never more than the
    /// full model, and less as soon as a point fails early.
    #[test]
    fn the_exhaustive_count_is_the_work_performed() {
        use rand::SeedableRng;
        let mut rng = rand::rngs::StdRng::seed_from_u64(5);
        let sys = random_quadratic(12, 12, &mut rng);
        let model: u64 = sys
            .equations
            .iter()
            .map(|p| p.terms.len() as u64)
            .sum::<u64>()
            << 12;
        let (_, cost) = Exhaustive.solve(&sys, &Params::default(), None);
        assert!(
            cost.ops < model,
            "{} tests against a model of {model}",
            cost.ops
        );
        assert!(
            cost.ops >= sys.equations[0].terms.len() as u64 * (1 << 12),
            "every point tests the first equation"
        );
    }
}
