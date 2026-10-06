//! # The stages of an index-calculus pipeline, as plug points.
//!
//! An elliptic-curve index-calculus attack is the same five stages
//! whatever the variant, and each stage has one job with a stable
//! interface.  This module states those interfaces as traits so that a
//! variant is a *choice at each stage* rather than a fork of the whole
//! pipeline.
//!
//! ```text
//!   instance ──► factor base ──► targets ──► decomposition ──► relations ──► logarithm
//!                    │              │             │                │
//!            FactorBaseBuilder  TargetSource  DecompositionOracle  RelationSolver
//!                                                   │
//!                                             SystemSolver
//!                                        (algebraic oracles only)
//! ```
//!
//! ## What each stage owes the pipeline
//!
//! Every stage is handed a `&mut GroupOps` and must charge **every**
//! group operation it performs to it.  That is not a formality: the
//! whole point of the framework is that the end-to-end cost is the sum
//! of the stages, so a stage that does uncounted work makes the total a
//! fiction.  Engine-native work that is not a group operation — square
//! roots, table lookups, SAT conflicts, monomial operations — is
//! charged to the stage's own counters and converted once, at the end,
//! by the calibration.  See `docs/ic/FRAMEWORK.md` for the accounting
//! contract in full.
//!
//! ## Why the traits are generic over the group
//!
//! A prime-field curve, a random binary curve and a Koblitz curve differ
//! in their arithmetic and in what symmetries the factor base can fold,
//! but not in the shape of the pipeline.  [`CountedGroup`] is the
//! repository's existing abstraction for "a group whose every operation
//! is counted", so the stages are generic over it and a plug-in written
//! once runs on any regime whose group implements it.

use std::collections::BTreeMap;
use std::time::Duration;

use serde::Serialize;

use crate::cryptanalysis::ic_boundary::{
    CountedGroup, FactorBase, GroupOps, OracleCounters, RowStatus,
};
use crate::cryptanalysis::pq_groebner_f2::F2BoolPoly;

/// Free-form parameters a plug-in reads its configuration from.
///
/// Deliberately untyped: a factor-base builder wants a size, a subspace
/// dimension or a fold, and the framework should not need editing to
/// let a new plug-in take a parameter it invented.  A plug-in validates
/// what it reads and returns a clear error when a parameter is missing
/// or absurd, rather than defaulting silently.
#[derive(Clone, Debug, Default, Serialize)]
pub struct Params(pub BTreeMap<String, String>);

impl Params {
    pub fn get(&self, key: &str) -> Option<&str> {
        self.0.get(key).map(|s| s.as_str())
    }

    /// A required integer parameter.
    pub fn u64(&self, key: &str) -> Result<u64, String> {
        let raw = self
            .get(key)
            .ok_or_else(|| format!("missing parameter `{key}`"))?;
        raw.parse()
            .map_err(|_| format!("parameter `{key}` is not a number: `{raw}`"))
    }

    /// An optional integer parameter with a default.
    pub fn u64_or(&self, key: &str, default: u64) -> Result<u64, String> {
        match self.get(key) {
            None => Ok(default),
            Some(raw) => raw
                .parse()
                .map_err(|_| format!("parameter `{key}` is not a number: `{raw}`")),
        }
    }

    /// An optional flag; absent is `false`.
    pub fn flag(&self, key: &str) -> bool {
        matches!(self.get(key), Some("1" | "true" | "yes"))
    }

    pub fn set(&mut self, key: &str, value: impl Into<String>) -> &mut Self {
        self.0.insert(key.into(), value.into());
        self
    }
}

/// Everything a stage may need to know about the instance it is
/// running on, and nothing it may not.
///
/// In particular there is **no field for the secret**.  A stage that
/// could read `k` could fake a relation, and a pipeline that can fake a
/// relation measures nothing.  The runner holds the planted logarithm
/// and uses it once, to verify the recovered answer.
pub struct InstanceCtx<'a, G: CountedGroup> {
    pub group: &'a G,
    pub generator: G::Elt,
    /// `Q = [k]G`, the point whose logarithm the pipeline must recover.
    pub target: G::Elt,
    /// The prime order of the subgroup the logarithm lives in.
    pub r: u64,
    /// `#E / r`.
    pub cofactor: u64,
    /// `#E`, the order of the whole curve group.
    pub group_order: u64,
    /// A name for the instance, used in reports.
    pub name: String,
    /// The field degree for binary regimes, `None` for prime fields.
    pub field_degree: Option<u32>,
}

/// **Stage 1 — the factor base.**
///
/// Chooses the subset `F ⊂ E` that relations are written over, and the
/// column map that says which unknown each point contributes to.  The
/// column map is what lets a base fold by negation (`P` and `−P` share
/// a column with opposite signs) or by the Frobenius (a whole orbit
/// shares one), which is why it is the builder's job and not the
/// runner's.
///
/// The build cost belongs to the pipeline's total, so charge it to
/// `ops` and to `FactorBase::cost`.
pub trait FactorBaseBuilder<G: CountedGroup> {
    fn name(&self) -> &str;

    /// One line on what this base is and what it costs, for the report.
    fn describe(&self, params: &Params) -> String;

    /// The parameters this builder reads, with a word on each, so that
    /// `ic bench --list` can tell a user what to pass.
    fn parameters(&self) -> &[(&str, &str)] {
        &[]
    }

    fn build(
        &self,
        ctx: &InstanceCtx<G>,
        params: &Params,
        ops: &mut GroupOps,
    ) -> Result<FactorBase<G::Elt>, String>;
}

/// The shape of an algebraic system, for the report's degree columns.
#[derive(Clone, Debug, Default, Serialize)]
pub struct SystemShape {
    pub n_vars: usize,
    pub n_equations: usize,
    /// The degree of each equation, in the variables the solver sees.
    pub degrees: Vec<u32>,
    /// The semi-regular degree of a system with these degrees: what a
    /// system with no exploitable structure would reach.
    pub semi_regular_degree: Option<u32>,
}

/// **Stage 3 — the point decomposition problem.**
///
/// Given a target point `R`, find `m` factor-base points summing to it,
/// returned as indices into `fb.points`.  `None` means this `R` does
/// not decompose over this base, which is the common case and must be
/// cheap.
///
/// An oracle that works by solving an algebraic system reports the
/// system it built through [`DecompositionOracle::last_system`], so the
/// degree columns of the report are filled from the real system rather
/// than from a model of it.
pub trait DecompositionOracle<G: CountedGroup> {
    fn name(&self) -> &str;

    /// How many factor-base points a relation from this oracle has.
    fn summands(&self) -> u32;

    fn describe(&self, params: &Params) -> String;

    fn parameters(&self) -> &[(&str, &str)] {
        &[]
    }

    /// Prepare for a run: build whatever table or precomputation the
    /// oracle needs, charging it to `ops`.  Called once per run, after
    /// the factor base exists.
    fn prepare(
        &mut self,
        _ctx: &InstanceCtx<G>,
        _fb: &FactorBase<G::Elt>,
        _params: &Params,
        _ops: &mut GroupOps,
    ) -> Result<(), String> {
        Ok(())
    }

    /// Decompose `point`, or decide it does not decompose.
    fn decompose(
        &mut self,
        ctx: &InstanceCtx<G>,
        fb: &FactorBase<G::Elt>,
        ops: &mut GroupOps,
        counters: &mut OracleCounters,
        point: G::Elt,
    ) -> Option<Vec<usize>>;

    /// The algebraic system the last [`decompose`] built, when it built
    /// one.  Table oracles return `None` and their degree columns stay
    /// empty, which is correct: they solve no system.
    ///
    /// [`decompose`]: DecompositionOracle::decompose
    fn last_system(&self) -> Option<SystemShape> {
        None
    }

    /// Everything the oracle's [`SystemSolver`] cost over the run so
    /// far, when it uses one.  The runner prices this into `S` and
    /// fills the report's degree columns from it.  Table oracles return
    /// `None`.
    fn solver_totals(&self) -> Option<SolverTotals> {
        None
    }
}

/// Totals an algebraic oracle accumulates over its solver calls.
#[derive(Clone, Debug, Default, Serialize)]
pub struct SolverTotals {
    pub solver: String,
    pub calls: u64,
    pub ops: u64,
    pub op_unit: String,
    pub wall_ns: u64,
    pub peak_bytes: u64,
    /// Calls that ran out of budget, counted apart from refutations.
    pub budget_exceeded: u64,
    pub solving_degree_sum: u64,
    pub solving_degree_max: u32,
    pub calls_with_a_degree: u64,
    /// The shape of the last system, which is the shape of every system
    /// on one base: the descent's variable and equation counts do not
    /// depend on the target.
    pub shape: Option<SystemShape>,
    pub extra: BTreeMap<String, u64>,
}

impl SolverTotals {
    pub fn absorb(
        &mut self,
        shape: &SystemShape,
        cost: Option<&SolverCost>,
        budget_exceeded: bool,
    ) {
        self.calls += 1;
        self.shape = Some(shape.clone());
        self.budget_exceeded += u64::from(budget_exceeded);
        let Some(c) = cost else { return };
        self.ops += c.ops;
        if self.op_unit.is_empty() {
            self.op_unit = c.op_unit.clone();
        }
        self.wall_ns += c.wall_ns;
        self.peak_bytes = self.peak_bytes.max(c.peak_bytes);
        if let Some(d) = c.solving_degree {
            self.solving_degree_sum += d as u64;
            self.solving_degree_max = self.solving_degree_max.max(d);
            self.calls_with_a_degree += 1;
        }
        for (k, v) in &c.extra {
            *self.extra.entry(k.clone()).or_insert(0) += v;
        }
    }

    pub fn solving_degree_mean(&self) -> Option<f64> {
        (self.calls_with_a_degree > 0)
            .then(|| self.solving_degree_sum as f64 / self.calls_with_a_degree as f64)
    }

    pub fn semi_regular_degree(&self) -> Option<u32> {
        self.shape.as_ref()?.semi_regular_degree
    }

    /// Mean solving degree over the semi-regular degree: below one is
    /// the structure the solver exploited.
    pub fn degree_over_bound(&self) -> Option<f64> {
        Some(self.solving_degree_mean()? / self.semi_regular_degree()? as f64)
    }
}

/// A boolean polynomial system, the common currency between an
/// algebraic decomposition oracle and a solver.
///
/// `F_2` and the boolean quotient `v² = v` are the setting every
/// Weil-descended Semaev system lands in, so a solver that speaks this
/// speaks to all of them.  A solver over a larger field adapts at its
/// own boundary.
#[derive(Clone, Debug)]
pub struct BooleanSystem {
    pub equations: Vec<F2BoolPoly>,
    pub n_vars: usize,
}

impl BooleanSystem {
    pub fn shape(&self) -> SystemShape {
        let degrees: Vec<u32> = self
            .equations
            .iter()
            .filter_map(|p| p.terms.iter().map(|t| t.degree()).max())
            .collect();
        SystemShape {
            n_vars: self.n_vars,
            n_equations: self.equations.len(),
            semi_regular_degree: crate::cryptanalysis::ic_descent_degrees::semi_regular_degree(
                self.n_vars,
                &degrees
                    .iter()
                    .copied()
                    .filter(|d| *d > 0)
                    .collect::<Vec<_>>(),
            ),
            degrees,
        }
    }
}

/// What a solver concluded.
#[derive(Clone, Debug, Serialize)]
pub enum SolverVerdict {
    /// Solutions found, as bitmasks over the system's variables.
    Solved(Vec<u64>),
    /// The system is inconsistent: this target does not decompose.
    Unsatisfiable,
    /// The budget ran out.  **Not** the same as unsatisfiable, and a
    /// pipeline must not treat it as one: an oracle that reports a
    /// timeout as "no decomposition" silently lowers its own hit rate
    /// and the relation phase it feeds becomes unmeasurable.
    BudgetExceeded,
}

/// What a solver call cost, in the engine's own units plus the ones
/// every engine can report.
#[derive(Clone, Debug, Default, Serialize)]
pub struct SolverCost {
    /// The engine's native operation count.
    pub ops: u64,
    /// What one `ops` is: `monomial operations`, `conflicts`,
    /// `field multiplications`, `word XORs`.  Carried so the
    /// calibration can convert it and so two engines are never added
    /// together in the wrong unit.
    pub op_unit: String,
    pub wall_ns: u64,
    /// The engine's own peak footprint in bytes, where it can report
    /// one; an operating-system sample is not required.
    pub peak_bytes: u64,
    /// The highest degree the computation reached.
    pub degree_reached: Option<u32>,
    /// The highest degree at which it learned something new — the
    /// solving degree, and the one to compare against a degree bound.
    pub solving_degree: Option<u32>,
    pub timed_out: bool,
    /// Anything else the engine counts and wants in the report.
    pub extra: BTreeMap<String, u64>,
}

/// **Stage 3b — the polynomial system solver.**
///
/// This is the plug point for F4, F5, XL, a SAT solver, exhaustive
/// search, or anything else that decides a boolean system.  It is
/// deliberately independent of the curve: a solver knows nothing about
/// elliptic curves, and an implementer does not have to.
///
/// A solver **must** respect `budget` and report `BudgetExceeded`
/// rather than running on, and **must not** return `Unsatisfiable`
/// unless it has decided the system.
pub trait SystemSolver: Send + Sync {
    fn name(&self) -> &str;

    fn describe(&self) -> String;

    fn parameters(&self) -> &[(&str, &str)] {
        &[]
    }

    /// Whether this solver can decide a system of this shape at all.
    /// A solver that would blow up is better declining than timing out
    /// on every target of a sweep.
    fn accepts(&self, shape: &SystemShape) -> bool {
        let _ = shape;
        true
    }

    /// Whether `Solved` carries **every** solution (a complete
    /// enumeration) or only one (a first-solution search, as a CDCL
    /// solver returns).  The two are different workloads and are never
    /// ranked against each other: the accounting contract keeps them
    /// on separate leaderboards, and a comparison checks a first-solution
    /// engine only for membership in the reference's solution set.
    fn finds_every_solution(&self) -> bool {
        true
    }

    fn solve(
        &self,
        system: &BooleanSystem,
        params: &Params,
        budget: Option<Duration>,
    ) -> (SolverVerdict, SolverCost);
}

/// **Stage 4 — the relation matrix.**
///
/// Accumulates relations and decides when the target's logarithm is
/// determined.  Kept behind a trait because the choice between a dense
/// incremental elimination, a structured Gaussian elimination and a
/// Wiedemann or Lanczos method is one of the real levers of an
/// index-calculus attack, and it is the one most often left unpriced.
pub trait RelationSolver {
    fn name(&self) -> &str;

    fn describe(&self) -> String;

    /// Add a relation row over `Z/rZ` with right-hand side `rhs`.
    fn add_row(&mut self, row: Vec<u64>, rhs: u64) -> RowStatus;

    /// The value of the target's column, once it is determined.
    fn pinned(&self, col: usize) -> Option<u64>;

    fn rank(&self) -> usize;

    /// Rows that added nothing to the rank.
    fn dependent(&self) -> u64;

    /// The work done, in whatever the method counts; `row_ops` for an
    /// elimination, matrix-vector products for an iterative method.
    fn work(&self) -> (u64, &'static str);
}

/// **Stage 2 — where trial points come from.**
///
/// Kept as a small enum rather than a trait: there are two designs that
/// matter, the repository has measured both, and the difference between
/// them is a documented result (§10.2 and §11.1 of the ledger note)
/// rather than an extension point.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize)]
pub enum Targets {
    /// A fresh `[a]G + [b]Q` per trial: two scalar multiplications.
    #[default]
    Random,
    /// An r-adding walk: one group addition per trial, with the guard
    /// that no target is presented twice.
    Walk,
}

impl Targets {
    pub fn name(self) -> &'static str {
        match self {
            Targets::Random => "random",
            Targets::Walk => "walk",
        }
    }

    pub fn parse(s: &str) -> Result<Self, String> {
        match s {
            "random" => Ok(Targets::Random),
            "walk" => Ok(Targets::Walk),
            other => Err(format!(
                "unknown target source `{other}`; try random or walk"
            )),
        }
    }
}
