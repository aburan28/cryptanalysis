//! # The factor bases, oracles and matrices that ship with the framework.
//!
//! Each of these wraps a component the repository already measures, so
//! a framework run reproduces a ledger row rather than approximating
//! one.  They are also the worked examples: a new plug-in looks like
//! these, and `docs/ic/FRAMEWORK.md` walks through writing one.
//!
//! ## Factor bases
//!
//! | name | regime | what it is |
//! |:--|:--|:--|
//! | `prime-abscissa` | prime | the smallest abscissae carrying a point, one column each |
//! | `binary-subspace` | binary, Koblitz | points whose abscissa lies in an `F_2`-subspace |
//! | `koblitz-orbit` | Koblitz | the same, each signed Frobenius orbit folded onto one column |
//!
//! The column map is the interesting part.  `koblitz-orbit` gives a
//! whole orbit of `2n` points one unknown, which cuts the relations
//! needed by `2n`; setting its `no_fold` parameter gives the control
//! that shows what the fold buys.  That pair is the one place this
//! ledger records an *advance* in the `AGENTS.md` §3 sense rather than
//! engineering, and it is a two-word change in a sweep file.
//!
//! ## Decomposition oracles
//!
//! | name | summands | how |
//! |:--|:--|:--|
//! | `subtract` | 2 | test `R − P ∈ F` for every signed base point; no table |
//! | `mitm` | 2 or 3 | a pair table probed once per target, or once per `R − P` |
//! | `mitm-frobenius` | 2 or 3 | the same on a Frobenius-folded table (Koblitz) |
//!
//! The pair table is where memory buys time, and `mitm`'s
//! `negation_folded` parameter halves the additions that build it.

use std::time::Duration;

use super::stages::{
    BooleanSystem, DecompositionOracle, FactorBaseBuilder, InstanceCtx, Params, SolverCost,
    SolverTotals, SolverVerdict, SystemShape, SystemSolver,
};
use crate::cryptanalysis::ic_boundary::{
    binary_subspace_factor_base, decompose_mitm, decompose_mitm_frobenius, koblitz_factor_base,
    prime_factor_base, BinaryGroup, BinaryInstance, ColumnFold, CountedGroup, FactorBase,
    FrobeniusPairTable, GroupOps, OracleCounters, PairTable, PrimeCurve, PrimeInstance, PrimePoint,
};
use crate::cryptanalysis::koblitz_fast::FastPoint;
use crate::cryptanalysis::koblitz_index_calculus::build_frobenius_factor_base_from_divisor;
use crate::cryptanalysis::pq_descent_symbolic::{descend, max_n_prime, SymbolicDescent};

// ── Factor bases ───────────────────────────────────────────────────

/// The smallest abscissae of a prime-field curve that carry a point,
/// one column each.
pub struct PrimeAbscissaBase<'i> {
    pub instance: &'i PrimeInstance,
}

impl FactorBaseBuilder<PrimeCurve> for PrimeAbscissaBase<'_> {
    fn name(&self) -> &str {
        "prime-abscissa"
    }

    fn describe(&self, params: &Params) -> String {
        format!(
            "the {} smallest abscissae carrying a point, one column each",
            params.get("size").unwrap_or("?")
        )
    }

    fn parameters(&self) -> &[(&str, &str)] {
        &[(
            "size",
            "abscissae in the base; the family optimum is about #E^(1/3)",
        )]
    }

    fn build(
        &self,
        _ctx: &InstanceCtx<PrimeCurve>,
        params: &Params,
        _ops: &mut GroupOps,
    ) -> Result<FactorBase<PrimePoint>, String> {
        let size = params.u64("size")? as usize;
        if size == 0 {
            return Err("factor base size must be positive".into());
        }
        Ok(prime_factor_base(self.instance, size))
    }
}

/// Points of a binary curve whose abscissa lies in an `F_2`-subspace
/// of the field, one column per abscissa.
pub struct BinarySubspaceBase<'i> {
    pub instance: &'i BinaryInstance,
}

impl<'a> FactorBaseBuilder<BinaryGroup<'a>> for BinarySubspaceBase<'_> {
    fn name(&self) -> &str {
        "binary-subspace"
    }

    fn describe(&self, params: &Params) -> String {
        format!(
            "points whose abscissa lies in the {}-dimensional subspace spanned by {{1, z, …}}",
            params.get("dimension").unwrap_or("?")
        )
    }

    fn parameters(&self) -> &[(&str, &str)] {
        &[(
            "dimension",
            "F_2-dimension of the abscissa subspace; about 2^dimension abscissae",
        )]
    }

    fn build(
        &self,
        _ctx: &InstanceCtx<BinaryGroup<'a>>,
        params: &Params,
        _ops: &mut GroupOps,
    ) -> Result<FactorBase<FastPoint>, String> {
        let dim = params.u64("dimension")? as u32;
        if dim == 0 || dim > 30 {
            return Err(format!("subspace dimension {dim} outside 1..=30"));
        }
        let basis: Vec<u64> = (0..dim).map(|k| 1u64 << k).collect();
        Ok(binary_subspace_factor_base(self.instance, &basis))
    }
}

/// A Koblitz base with each signed Frobenius orbit folded onto one
/// column: `2n` points, one unknown.
pub struct KoblitzOrbitBase<'i> {
    pub instance: &'i BinaryInstance,
}

impl<'a> FactorBaseBuilder<BinaryGroup<'a>> for KoblitzOrbitBase<'_> {
    fn name(&self) -> &str {
        "koblitz-orbit"
    }

    fn describe(&self, params: &Params) -> String {
        format!(
            "the Frobenius-invariant subspace spanned by divisor factors {}, {}",
            params.get("divisor").unwrap_or("?"),
            if params.flag("no_fold") {
                "one column per abscissa (the unfolded control)"
            } else {
                "each signed Frobenius orbit folded onto one column"
            }
        )
    }

    fn parameters(&self) -> &[(&str, &str)] {
        &[
            (
                "divisor",
                "comma-separated indices into the factorisation of the Frobenius characteristic \
                 polynomial; the invariant subspace they span becomes the abscissa set. This is \
                 the knob that chooses the base, so sweeping it sweeps factor bases",
            ),
            (
                "no_fold",
                "1 to give every abscissa its own column: the control that shows what the fold buys",
            ),
        ]
    }

    fn build(
        &self,
        _ctx: &InstanceCtx<BinaryGroup<'a>>,
        params: &Params,
        _ops: &mut GroupOps,
    ) -> Result<FactorBase<FastPoint>, String> {
        let kc = self
            .instance
            .koblitz
            .as_ref()
            .ok_or("this instance is not a Koblitz curve, so it has no Frobenius to fold by")?;
        let raw = params
            .get("divisor")
            .ok_or("missing parameter `divisor`; try 0 or 0,1")?;
        let idx: Result<Vec<usize>, String> = raw
            .split([',', ';'])
            .filter(|s| !s.is_empty())
            .map(|s| {
                s.trim()
                    .parse::<usize>()
                    .map_err(|_| format!("divisor index `{s}` is not a number"))
            })
            .collect();
        let idx = idx?;
        if idx.is_empty() {
            return Err("parameter `divisor` selected no factors".into());
        }
        let frob = build_frobenius_factor_base_from_divisor(kc, &idx)
            .ok_or_else(|| format!("no invariant subspace for divisor {idx:?} on this curve"))?;
        let fold = if params.flag("no_fold") {
            ColumnFold::Abscissa
        } else {
            ColumnFold::SignedFrobeniusOrbit
        };
        koblitz_factor_base(
            self.instance,
            &frob,
            fold,
            format!(
                "invariant subspace, divisor {idx:?}, dimension {}",
                frob.ell
            ),
        )
        .ok_or_else(|| "the invariant subspace produced no usable factor base".into())
    }
}

// ── Decomposition oracles ──────────────────────────────────────────

/// Test `R − P ∈ F` for every signed base point: no table, `|F|` group
/// operations a target, and the honest baseline every table oracle is
/// an improvement on.
pub struct SubtractOracle;

impl<G: CountedGroup> DecompositionOracle<G> for SubtractOracle {
    fn name(&self) -> &str {
        "subtract"
    }

    fn summands(&self) -> u32 {
        2
    }

    fn describe(&self, _params: &Params) -> String {
        "for each signed base point P, test whether R − P is in the base".into()
    }

    fn decompose(
        &mut self,
        ctx: &InstanceCtx<G>,
        fb: &FactorBase<G::Elt>,
        ops: &mut GroupOps,
        counters: &mut OracleCounters,
        point: G::Elt,
    ) -> Option<Vec<usize>> {
        for (i, p) in fb.points.iter().enumerate() {
            let rest = ctx.group.add(ops, point, ctx.group.neg(*p));
            counters.lookups += 1;
            let key = ctx.group.key(&rest);
            if let Some(j) = fb.index_of_key(key) {
                return Some(vec![i, j]);
            }
        }
        None
    }
}

/// Meet in the middle over a pair table: memory for time, the lever
/// that makes a two-summand search `O(1)` a target instead of `O(|F|)`.
pub struct MitmOracle {
    m: u32,
    table: Option<PairTable>,
}

impl MitmOracle {
    pub fn new(m: u32) -> Self {
        Self { m, table: None }
    }
}

impl<G: CountedGroup> DecompositionOracle<G> for MitmOracle {
    fn name(&self) -> &str {
        "mitm"
    }

    fn summands(&self) -> u32 {
        self.m
    }

    fn describe(&self, params: &Params) -> String {
        format!(
            "a table of pair sums probed once per target (m = 2) or once per R − P (m = 3), {}",
            if params.flag("negation_folded") {
                "built with the negation fold"
            } else {
                "built in full"
            }
        )
    }

    fn parameters(&self) -> &[(&str, &str)] {
        &[(
            "negation_folded",
            "1 to build only one of each ±pair, halving the table's additions",
        )]
    }

    fn prepare(
        &mut self,
        ctx: &InstanceCtx<G>,
        fb: &FactorBase<G::Elt>,
        params: &Params,
        ops: &mut GroupOps,
    ) -> Result<(), String> {
        let table = if params.flag("negation_folded") {
            PairTable::build_negation_folded(ctx.group, fb)
        } else {
            PairTable::build(ctx.group, fb)
        };
        // The table's construction is part of the pipeline's cost.
        ops.merge(table.build_ops);
        self.table = Some(table);
        Ok(())
    }

    fn decompose(
        &mut self,
        ctx: &InstanceCtx<G>,
        fb: &FactorBase<G::Elt>,
        ops: &mut GroupOps,
        counters: &mut OracleCounters,
        point: G::Elt,
    ) -> Option<Vec<usize>> {
        let table = self.table.as_ref()?;
        decompose_mitm(ctx.group, fb, table, self.m, ops, counters, point)
    }
}

/// Meet in the middle on a table folded by the signed Frobenius: the
/// same probe over a table `2n` times smaller.
pub struct FrobeniusMitmOracle<'i> {
    m: u32,
    instance: &'i BinaryInstance,
    table: Option<FrobeniusPairTable>,
}

impl<'i> FrobeniusMitmOracle<'i> {
    pub fn new(m: u32, instance: &'i BinaryInstance) -> Self {
        Self {
            m,
            instance,
            table: None,
        }
    }
}

impl<'a> DecompositionOracle<BinaryGroup<'a>> for FrobeniusMitmOracle<'_> {
    fn name(&self) -> &str {
        "mitm-frobenius"
    }

    fn summands(&self) -> u32 {
        self.m
    }

    fn describe(&self, _params: &Params) -> String {
        "a pair table folded by the signed Frobenius, one entry per orbit".into()
    }

    fn prepare(
        &mut self,
        _ctx: &InstanceCtx<BinaryGroup<'a>>,
        fb: &FactorBase<FastPoint>,
        _params: &Params,
        ops: &mut GroupOps,
    ) -> Result<(), String> {
        let table = FrobeniusPairTable::build(self.instance, fb)
            .ok_or("this instance has no Koblitz structure to fold by")?;
        ops.merge(table.build_ops);
        self.table = Some(table);
        Ok(())
    }

    fn decompose(
        &mut self,
        ctx: &InstanceCtx<BinaryGroup<'a>>,
        fb: &FactorBase<FastPoint>,
        ops: &mut GroupOps,
        counters: &mut OracleCounters,
        point: FastPoint,
    ) -> Option<Vec<usize>> {
        let table = self.table.as_ref()?;
        decompose_mitm_frobenius(ctx.group, fb, table, self.m, ops, counters, point)
    }
}

// ── The bridge to the solver plug point ────────────────────────────

/// Holds a [`SystemSolver`] and the record of what it cost, so an
/// algebraic oracle can be written without repeating the bookkeeping.
///
/// This is what makes the solver plug point reachable from a whole
/// pipeline: swap `buchberger-f2` for `sat-cdcl` and the change
/// propagates through the relation phase to the recovered key, with
/// every stage still counted.
pub struct SolverHarness {
    pub solver: Box<dyn SystemSolver>,
    pub params: Params,
    pub budget: Option<Duration>,
    last_shape: Option<SystemShape>,
    last_cost: Option<SolverCost>,
    /// Targets whose solver hit its budget.  Counted, never silently
    /// folded into "did not decompose": an oracle that did that would
    /// quietly lower its own hit rate and make the relation phase it
    /// feeds unmeasurable.
    pub budget_exceeded: u64,
}

impl SolverHarness {
    pub fn new(solver: Box<dyn SystemSolver>, params: Params, budget: Option<Duration>) -> Self {
        Self {
            solver,
            params,
            budget,
            last_shape: None,
            last_cost: None,
            budget_exceeded: 0,
        }
    }

    /// Solve one descended system, recording what it cost.
    pub fn solve(&mut self, system: &BooleanSystem) -> SolverVerdict {
        let shape = system.shape();
        self.last_shape = Some(shape.clone());
        if !self.solver.accepts(&shape) {
            self.last_cost = None;
            self.budget_exceeded += 1;
            return SolverVerdict::BudgetExceeded;
        }
        let (verdict, cost) = self.solver.solve(system, &self.params, self.budget);
        self.last_cost = Some(cost);
        if matches!(verdict, SolverVerdict::BudgetExceeded) {
            self.budget_exceeded += 1;
        }
        verdict
    }

    pub fn shape(&self) -> Option<&SystemShape> {
        self.last_shape.as_ref()
    }

    pub fn cost(&self) -> Option<&SolverCost> {
        self.last_cost.as_ref()
    }
}

// ── The algebraic oracle ───────────────────────────────────────────

/// Descend the Semaev polynomial over the base's abscissa subspace and
/// hand the boolean system to the chosen [`SystemSolver`].
///
/// This is the oracle that makes the solver plug point reach the `S`
/// column: swap `buchberger-f2` for `sat-cdcl` and the change
/// propagates through the relation phase to the recovered logarithm,
/// with every stage still counted.  It requires a factor base whose
/// abscissae form an `F_2`-subspace — `binary-subspace` and
/// `koblitz-orbit` both record theirs in `FactorBase::subspace_basis`.
///
/// ## What it charges
///
/// The descent and the solver are engine work, not group operations,
/// and are reported through [`DecompositionOracle::solver_totals`] in
/// the solver's own unit; the runner prices them into `S`.  Lifting a
/// solution back to signed base points costs real group additions,
/// which are charged to `ops` like any other oracle's.
///
/// ## The cap
///
/// The descent is symbolic — the summation polynomial expanded in
/// `F_{2^n}[v]/(v² − v)` term by term — so it builds no table and is
/// capped only by the monomial mask: `m·n' ≤ 64` boolean variables,
/// `n' ≤ 32` at two summands and `n' ≤ 21` at three.  What limits a
/// row above that is the engine, which says so through `accepts`.
pub struct DescentAlgebraicOracle<'i> {
    summands: u32,
    instance: &'i BinaryInstance,
    v_basis: Vec<u64>,
    harness: SolverHarness,
    totals: SolverTotals,
    /// Systems the solver decided satisfiable none of whose solutions
    /// lifted to base points summing to the target.  Expected, not a
    /// defect: a summation polynomial vanishes over the algebraic
    /// closure, so a solution may name abscissae whose points live on
    /// the quadratic twist (`y ∈ F_{2^{2n}}`, never in the base), and
    /// the pair table never sees those.  Reported as
    /// `unliftable_systems` beside `lift_failures` so the hit rate can
    /// be read against what the solver actually found.
    pub unliftable: u64,
}

impl<'i> DescentAlgebraicOracle<'i> {
    pub fn new(
        summands: u32,
        instance: &'i BinaryInstance,
        solver: Box<dyn SystemSolver>,
        solver_params: Params,
        budget: Option<Duration>,
    ) -> Self {
        let totals = SolverTotals {
            solver: solver.name().to_string(),
            ..Default::default()
        };
        Self {
            summands,
            instance,
            v_basis: Vec::new(),
            harness: SolverHarness::new(solver, solver_params, budget),
            totals,
            unliftable: 0,
        }
    }

    pub fn solver_name(&self) -> &str {
        self.harness.solver.name()
    }

    /// The descended system for a target abscissa; its `lift` maps a
    /// solution back to abscissae.  `prepare` must have run.
    fn descend(&self, x_r: u64) -> SymbolicDescent {
        descend(
            &self.instance.gf,
            self.instance.b,
            x_r,
            &self.v_basis,
            self.summands,
        )
        .expect("prepare checked the dimension")
    }
}

fn system_of(sys: &SymbolicDescent) -> BooleanSystem {
    BooleanSystem {
        equations: sys.equations.clone(),
        n_vars: sys.n_vars,
    }
}

impl<'a> DecompositionOracle<BinaryGroup<'a>> for DescentAlgebraicOracle<'_> {
    fn name(&self) -> &str {
        "descent-algebraic"
    }

    fn summands(&self) -> u32 {
        self.summands
    }

    fn describe(&self, _params: &Params) -> String {
        format!(
            "Weil-descend S_{} over the base's abscissa subspace and solve with {}",
            self.summands + 1,
            self.harness.solver.name()
        )
    }

    fn parameters(&self) -> &[(&str, &str)] {
        &[("m", "summands, 2 (descends S3) or 3 (descends S4)")]
    }

    fn prepare(
        &mut self,
        _ctx: &InstanceCtx<BinaryGroup<'a>>,
        fb: &FactorBase<FastPoint>,
        _params: &Params,
        _ops: &mut GroupOps,
    ) -> Result<(), String> {
        if !(2..=3).contains(&self.summands) {
            return Err(format!(
                "descent-algebraic takes m = 2 or 3, got {}",
                self.summands
            ));
        }
        let basis = fb.subspace_basis.as_ref().ok_or(
            "descent-algebraic needs a factor base whose abscissae form an F_2-subspace; \
             use binary-subspace or koblitz-orbit",
        )?;
        let cap = max_n_prime(self.summands);
        if basis.len() as u32 > cap {
            return Err(format!(
                "the descent's monomial mask holds n' ≤ {cap} at m = {}; this base has n' = {}",
                self.summands,
                basis.len()
            ));
        }
        self.v_basis = basis.clone();
        // Every system on one base has the same shape, so descend one
        // abscissa now and let the engine decline the shape here, once,
        // with a reason a sweep can report — rather than target by
        // target, which would run the whole relation phase for nothing.
        let shape = system_of(&self.descend(self.instance.generator.x)).shape();
        if !self.harness.solver.accepts(&shape) {
            return Err(format!(
                "solver `{}` declines a system of {} unknowns and {} equations; \
                 use a smaller base or another engine",
                self.harness.solver.name(),
                shape.n_vars,
                shape.n_equations
            ));
        }
        Ok(())
    }

    fn decompose(
        &mut self,
        ctx: &InstanceCtx<BinaryGroup<'a>>,
        fb: &FactorBase<FastPoint>,
        ops: &mut GroupOps,
        counters: &mut OracleCounters,
        point: FastPoint,
    ) -> Option<Vec<usize>> {
        if self.v_basis.is_empty() {
            return None;
        }
        // Descend, solve, and lift every solution until one sums to R.
        let sys = self.descend(point.x);
        let system = system_of(&sys);
        let shape = system.shape();
        let verdict = self.harness.solve(&system);
        let exceeded = matches!(verdict, SolverVerdict::BudgetExceeded);
        self.totals.absorb(&shape, self.harness.cost(), exceeded);
        let SolverVerdict::Solved(solutions) = verdict else {
            return None;
        };
        for v in solutions {
            let xs = sys.lift(v);
            if let Some(indices) =
                crate::cryptanalysis::ic_boundary::lift_abscissae(ctx.group, fb, ops, &xs, point)
            {
                return Some(indices);
            }
            counters.lift_failures += 1;
        }
        self.unliftable += 1;
        counters.unliftable_systems += 1;
        None
    }

    fn last_system(&self) -> Option<SystemShape> {
        self.totals.shape.clone()
    }

    fn solver_totals(&self) -> Option<SolverTotals> {
        Some(self.totals.clone())
    }
}
