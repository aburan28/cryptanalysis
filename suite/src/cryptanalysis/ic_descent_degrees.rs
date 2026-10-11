//! # The degree a Weil-descent system actually reaches.
//!
//! Petit and Quisquater's Table 2 (*On Polynomial Systems Arising from
//! a Weil Descent*, ASIACRYPT 2012, p. 461) reports, for a handful of
//! `(curve family, n, n', m)` cells, the **average maximal degree
//! reached** in a Gröbner-basis computation, the average time and the
//! peak memory.  Its point is not the timings: it is that in every cell
//! the degree reached came out *below* the first-fall-degree bound,
//! because Semaev's polynomials are sparse and the bound is derived for
//! a generic system.  The bound used here is the semi-regular degree
//! of a boolean system with the same equation degrees, which plays the
//! same role: it is what a system with no exploitable structure would
//! reach.
//!
//! This module measures the same three quantities on the descent
//! systems this repository builds, so that the phenomenon can be
//! checked here rather than cited.
//!
//! ## What is and is not being reproduced
//!
//! **Not reproduced**: Petit–Quisquater's *numbers*.  Their Table 2
//! solves a symmetrised system in `mt + 1 = m² + 1` variables — five at
//! `m = 2`, ten at `m = 3` — obtained from the block structure of
//! Section 4 of that paper.  The symbolic descent
//! ([`pq_descent_symbolic`](crate::cryptanalysis::pq_descent_symbolic))
//! builds the plain descent, `m·n'` boolean variables with no
//! symmetrisation, so at `(n, n', m) = (11, 6, 2)` this module solves a
//! 12-variable system where they solve a 5-variable one.  The degrees
//! are therefore not comparable row by row and are not presented as
//! though they were.
//!
//! **Reproduced**: the *shape* of the measurement and the comparison
//! that gives it meaning — a derived degree bound in one column, the
//! degree actually reached beside it, and their ratio.
//!
//! ## What the columns mean
//!
//! | column | meaning |
//! |:--|:--|
//! | `family` | `K` for the Koblitz curve `y² + xy = x³ + a x² + 1`, `R` for a random binary curve of the same degree |
//! | `n` | the field degree: the system is over `F_{2^n}` and descends to `n` equations |
//! | `n'` | the `F_2`-dimension of the subspace `V ⊂ F_{2^n}` the summands are drawn from |
//! | `m` | summands: `m = 2` descends `S₃`, `m = 3` descends `S₄` |
//! | `vars` | `m · n'`, the boolean unknowns |
//! | `D_av` | mean over targets of the **solving degree**: the highest degree at which the run produced a new basis element |
//! | `D_max` | the largest solving degree over the targets |
//! | `D_pair` | mean highest degree of a pair *processed*, which Buchberger's strategy pushes above the solving degree |
//! | `D_sr` | the semi-regular degree of a system with the same equation degrees — the derived bound `D_av` is measured against |
//! | `ops` | monomial operations, the metric |
//! | `enumerate` | the reference in the same unit: evaluating every equation at every point of the subspace |
//! | `ops/enum` | above one means the Gröbner basis costs more than enumerating |
//! | `ms` | wall time, the practicality note |
//! | `KiB` | the engine's own peak footprint: monomials held × 8 bytes |
//!
//! ## This is a stage diagnostic
//!
//! `AGENTS.md` §2 is explicit that a number pricing one phase is never a
//! speed.  Everything here prices **one decomposition oracle call** on
//! one target.  It says nothing on its own about whether index calculus
//! beats rho; the whole-pipeline unit `S` and its boundaries live in
//! `ic_boundary` and the ledger note.  No row of this table may be
//! quoted as a speedup.

use serde::Serialize;

use crate::binary_ecc::{BinaryCurve, BinaryPoint};
use crate::cryptanalysis::ic_boundary::{koblitz_instance, random_binary_instance, BinaryInstance};
use crate::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;
use crate::cryptanalysis::pq_descent_symbolic::descend;
use crate::cryptanalysis::pq_groebner_f2::{groebner_basis_f2_within, GbStats};
use num_bigint::BigUint;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};

/// The caps the descent's truth-table construction imposed: it
/// enumerated `2^{m·n'}` inputs to build the algebraic normal form.
/// Kept as the record of where the §14 table stopped and why; the
/// symbolic descent this module now uses is capped only by the
/// monomial mask, see [`max_n_prime`].
pub const TRUTH_TABLE_MAX_N_PRIME_M2: u32 = 8;
pub const TRUTH_TABLE_MAX_N_PRIME_M3: u32 = 5;

/// The largest subspace dimension this module will descend at `m`
/// summands: `⌊64 / m⌋`, the monomial mask's width, since the descent
/// is symbolic and builds no table.
pub fn max_n_prime(m: u32) -> u32 {
    crate::cryptanalysis::pq_descent_symbolic::max_n_prime(m)
}

/// One Gröbner run on one target.
#[derive(Clone, Copy, Debug, Serialize)]
pub struct TargetRun {
    pub stats: GbStats,
    /// Whether the basis is `{1}`: the system is inconsistent, so this
    /// target has no decomposition over `V`.
    pub inconsistent: bool,
}

/// One `(family, n, n', m)` cell, over every target drawn for it.
#[derive(Clone, Debug, Serialize)]
pub struct DescentCell {
    pub family: String,
    pub curve: String,
    pub n: u32,
    pub n_prime: u32,
    pub summands: u32,
    pub n_vars: usize,
    pub equations: usize,
    pub targets: usize,
    /// Targets whose system was inconsistent — no decomposition in `V`.
    pub inconsistent: usize,
    /// Targets whose run hit the budget.  Any degree or cost on a row
    /// with these is a lower bound and a statement about the engine.
    pub timed_out: usize,
    /// Mean and max over targets of the **solving degree**: the
    /// highest degree at which the run produced a new basis element.
    /// This is the column the bound is for.
    pub d_av: f64,
    pub d_max: u32,
    /// The same for the highest degree of a pair *processed*, which
    /// Buchberger's strategy pushes above the solving degree; it is a
    /// property of the pair selection, not of the system.
    pub d_pair_av: f64,
    pub d_pair_max: u32,
    /// The same for the highest degree of any intermediate polynomial,
    /// which a reduction can push above the pair degree.
    pub d_poly_av: f64,
    pub d_poly_max: u32,
    /// The derived bound: the semi-regular degree of a boolean system
    /// with the same equation degrees, over the targets drawn.
    pub d_semireg_min: Option<u32>,
    pub d_semireg_max: Option<u32>,
    pub d_semireg_unbounded: usize,
    /// `d_av / d_semireg_min`: below one is Petit–Quisquater's phenomenon.
    pub d_av_over_semireg: Option<f64>,
    /// The metric: monomial operations per target.
    pub mono_ops_mean: f64,
    pub mono_ops_max: u64,
    /// **The reference**, in the same unit: what it costs to solve the
    /// same problem by evaluating every equation at every point of the
    /// subspace, `2^vars · Σ_i |terms_i|` monomial tests.  `AGENTS.md`
    /// §1 asks a method to be priced against the best algorithm that
    /// already solves the problem, and at these sizes that is
    /// exhaustive search.
    pub brute_force_ops: f64,
    /// `mono_ops_mean / brute_force_ops`.  Above one means the Gröbner
    /// basis costs more than enumerating the subspace.
    pub ops_over_brute_force: f64,
    pub spolys_mean: f64,
    pub basis_len_mean: f64,
    /// The practicality note, never the metric.
    pub ms_mean: f64,
    pub ms_max: f64,
    /// The engine's own peak footprint, monomials held × 8 bytes.
    pub peak_kib_max: f64,
    pub per_target: Vec<TargetRun>,
}

fn mean(xs: impl Iterator<Item = f64>) -> f64 {
    let v: Vec<f64> = xs.collect();
    if v.is_empty() {
        f64::NAN
    } else {
        v.iter().sum::<f64>() / v.len() as f64
    }
}

/// Build the `BinaryCurve` an instance describes.  Public because the
/// framework's algebraic oracle descends over the same curve.
pub fn curve_of(inst: &BinaryInstance) -> Option<BinaryCurve> {
    let irreducible = find_irreducible_sparse(inst.n)?;
    Some(BinaryCurve {
        m: inst.n,
        irreducible,
        a: inst.gf.to_element(inst.a),
        b: inst.gf.to_element(inst.b),
        generator: BinaryPoint::Infinity,
        order: BigUint::from(inst.r),
        cofactor: BigUint::from(inst.cofactor),
    })
}

/// `{1, z, …, z^{n'-1}}`, the standard low-degree subspace of
/// `F_{2^n}`, as words.  It is the subspace Gaudry's and Diem's factor
/// bases use and the one the descent is cheapest on; a random subspace
/// would change the constants but not the shape.
fn standard_basis(n_prime: u32) -> Vec<u64> {
    (0..n_prime).map(|k| 1u64 << k).collect()
}

/// The `K` or `R` instance at degree `n`.
pub fn instance_for(family: &str, n: u32, seed: u64) -> Option<BinaryInstance> {
    match family {
        // Petit–Quisquater use `y² + xy = x³ + x² + 1`, which is `K_1`.
        "K" => koblitz_instance(1, n).or_else(|| koblitz_instance(0, n)),
        "R" => random_binary_instance(n, seed, 1 << 20),
        _ => None,
    }
}

/// Measure one cell: descend `targets` random targets and run the
/// boolean Gröbner basis on each.
pub fn price_descent_cell(
    family: &str,
    n: u32,
    n_prime: u32,
    summands: u32,
    targets: usize,
    seed: u64,
    budget: Option<std::time::Duration>,
) -> Option<DescentCell> {
    if n_prime == 0 || n_prime > max_n_prime(summands) {
        return None;
    }
    let inst = instance_for(family, n, seed)?;
    let v_basis = standard_basis(n_prime);
    let mut rng = StdRng::seed_from_u64(seed ^ ((n as u64) << 32) ^ ((summands as u64) << 16));

    let mut runs: Vec<TargetRun> = Vec::with_capacity(targets);
    let mut bounds: Vec<Option<u32>> = Vec::new();
    let mut brute: Vec<f64> = Vec::new();
    let mut n_vars = 0usize;
    let mut equations = 0usize;

    for _ in 0..targets {
        // A target abscissa drawn uniformly from the field.  The same
        // draw the truth-table rounds made, so a cell re-run here is
        // the same targets.
        let x_r = rng.gen::<u64>() & inst.gf.mask;
        let sys = descend(&inst.gf, inst.b, x_r, &v_basis, summands).ok()?;
        let (eqs, vars) = (sys.equations, sys.n_vars);
        n_vars = vars;
        equations = eqs.len();
        // The derived bound, on the same equations the run will solve.
        bounds.push(semi_regular_degree_of(&eqs, vars));
        // The reference: evaluate every equation at every point of the
        // subspace.  One monomial test per term per point.
        let terms: usize = eqs.iter().map(|p| p.terms.len()).sum();
        brute.push((terms as f64) * 2f64.powi(vars as i32));
        let (gb, stats) = groebner_basis_f2_within(eqs, vars, budget);
        let inconsistent = gb.len() == 1 && gb[0].terms.len() == 1 && gb[0].terms[0].degree() == 0;
        runs.push(TargetRun {
            stats,
            inconsistent,
        });
    }

    let seen: Vec<u32> = bounds.iter().filter_map(|f| *f).collect();
    let d_semireg_min = seen.iter().copied().min();
    let d_av = mean(runs.iter().map(|r| r.stats.solving_degree as f64));
    let ops_mean = mean(runs.iter().map(|r| r.stats.mono_ops as f64));
    let brute_mean = mean(brute.iter().copied());
    Some(DescentCell {
        family: family.into(),
        curve: inst.name.clone(),
        n,
        n_prime,
        summands,
        n_vars,
        equations,
        targets,
        inconsistent: runs.iter().filter(|r| r.inconsistent).count(),
        timed_out: runs.iter().filter(|r| r.stats.timed_out).count(),
        d_av,
        d_max: runs
            .iter()
            .map(|r| r.stats.solving_degree)
            .max()
            .unwrap_or(0),
        d_pair_av: mean(runs.iter().map(|r| r.stats.max_pair_degree as f64)),
        d_pair_max: runs
            .iter()
            .map(|r| r.stats.max_pair_degree)
            .max()
            .unwrap_or(0),
        d_poly_av: mean(runs.iter().map(|r| r.stats.max_poly_degree as f64)),
        d_poly_max: runs
            .iter()
            .map(|r| r.stats.max_poly_degree)
            .max()
            .unwrap_or(0),
        d_semireg_min,
        d_semireg_max: seen.iter().copied().max(),
        d_semireg_unbounded: bounds.iter().filter(|f| f.is_none()).count(),
        d_av_over_semireg: d_semireg_min.map(|f| d_av / f as f64),
        mono_ops_mean: ops_mean,
        brute_force_ops: brute_mean,
        ops_over_brute_force: ops_mean / brute_mean,
        mono_ops_max: runs.iter().map(|r| r.stats.mono_ops).max().unwrap_or(0),
        spolys_mean: mean(runs.iter().map(|r| r.stats.spolys as f64)),
        basis_len_mean: mean(runs.iter().map(|r| r.stats.basis_len as f64)),
        ms_mean: mean(runs.iter().map(|r| r.stats.wall_ns as f64 / 1e6)),
        ms_max: runs
            .iter()
            .map(|r| r.stats.wall_ns as f64 / 1e6)
            .fold(0.0, f64::max),
        peak_kib_max: runs
            .iter()
            .map(|r| r.stats.peak_bytes() as f64 / 1024.0)
            .fold(0.0, f64::max),
        per_target: runs,
    })
}

/// **The derived boundary: the semi-regular degree of a boolean system.**
///
/// For a semi-regular sequence of equations of degrees `d_1, …, d_k` in
/// `v` boolean variables — that is, one behaving as generically as the
/// field equations `v_i² = v_i` allow — the Hilbert series of the
/// quotient is
///
/// ```text
///     H(t) = (1 + t)^v / Π_i (1 + t^{d_i})
/// ```
///
/// and the degree of regularity is the index of its first non-positive
/// coefficient (Bardet–Faugère–Salvy).  A Gröbner computation on a
/// semi-regular system reaches that degree; one on a system with extra
/// structure falls earlier.  That gap is the whole subject of
/// Petit–Quisquater's Table 2, so this is the column their `D_av` is
/// worth reporting against.
///
/// Returns `None` when the series stays positive out to degree `v`,
/// which is the boolean ring's own ceiling.
pub fn semi_regular_degree(n_vars: usize, degrees: &[u32]) -> Option<u32> {
    if n_vars == 0 || n_vars > 512 {
        return None;
    }
    let top = n_vars + 1;
    // Numerator (1 + t)^v by Pascal's triangle, truncated at t^top.
    let mut num = vec![0i128; top + 1];
    num[0] = 1;
    for _ in 0..n_vars {
        for k in (1..=top).rev() {
            num[k] += num[k - 1];
        }
    }
    // Denominator Π (1 + t^{d_i}), truncated likewise.
    let mut den = vec![0i128; top + 1];
    den[0] = 1;
    for &d in degrees {
        if d == 0 || d as usize > top {
            continue;
        }
        for k in (d as usize..=top).rev() {
            den[k] += den[k - d as usize];
        }
    }
    // Long division: num = den · quot, with den[0] = 1.
    let mut quot = vec![0i128; top + 1];
    for k in 0..=top {
        let mut acc = num[k];
        for j in 1..=k {
            acc -= den[j] * quot[k - j];
        }
        quot[k] = acc;
        if k >= 1 && quot[k] <= 0 {
            return Some(k as u32);
        }
    }
    None
}

/// The derived boundary for one descent system, from the degrees its
/// equations actually have.
fn semi_regular_degree_of(
    eqs: &[crate::cryptanalysis::pq_groebner_f2::F2BoolPoly],
    n_vars: usize,
) -> Option<u32> {
    let degrees: Vec<u32> = eqs
        .iter()
        .filter_map(|p| p.terms.iter().map(|t| t.degree()).max())
        .filter(|d| *d > 0)
        .collect();
    semi_regular_degree(n_vars, &degrees)
}

// ── Any engine, several at once: the matched stage suite ───────────

/// One engine's answer to one target in one repetition.
#[derive(Clone, Debug, Serialize)]
pub struct EngineRun {
    /// `solved`, `unsatisfiable`, `budget` or `declined`.
    pub verdict: String,
    /// The solutions returned, sorted.
    pub solutions: Vec<u64>,
    pub ops: u64,
    pub wall_ns: u64,
    pub degree_reached: Option<u32>,
    pub solving_degree: Option<u32>,
    pub peak_bytes: u64,
    pub extra: std::collections::BTreeMap<String, u64>,
    /// The unit `ops` counts, as the engine named it; carried on the
    /// summary rather than repeated on every run.
    #[serde(skip)]
    pub op_unit: String,
}

/// One target of a cell: the system's fingerprint and every engine's
/// runs on it, repetition by repetition.
#[derive(Clone, Debug, Serialize)]
pub struct EngineTarget {
    pub x_r: u64,
    /// blake3 over the canonical system (variable count, then each
    /// equation's term masks in ascending order), so a later run can
    /// prove it solved the same inputs.
    pub system_blake3: String,
    pub terms: u64,
    pub semi_regular_degree: Option<u32>,
    /// Engine name → its runs on this target in repetition order.  An
    /// engine that exhausted the budget has one run here, not `repeats`.
    pub runs: std::collections::BTreeMap<String, Vec<EngineRun>>,
}

/// One engine over one cell.
#[derive(Clone, Debug, Serialize)]
pub struct EngineSummary {
    pub engine: String,
    pub op_unit: String,
    /// `complete enumeration` or `first solution`: the accounting
    /// contract keeps the two on separate leaderboards.
    pub workload: String,
    pub declined: bool,
    /// Targets decided (solved or refuted) in every repetition.
    pub decided: usize,
    /// Targets with a budget verdict in some repetition.
    pub over_budget: usize,
    /// Every decided answer equals the reference engine's (CDCL: its
    /// one model is a reference solution).
    pub agrees_with_reference: bool,
    /// Mean and max over decided targets of the solving degree (highest
    /// degree that produced a new element) and of the highest degree
    /// processed, where the engine reports them.
    pub d_learn_mean: Option<f64>,
    pub d_learn_max: Option<u32>,
    pub d_reach_mean: Option<f64>,
    pub d_reach_max: Option<u32>,
    /// Means over targets of the per-target median over repetitions.
    pub ops_mean: f64,
    pub ms_mean: f64,
    pub ms_max: f64,
    pub peak_kib_max: f64,
    /// Summed median wall over the targets both decided, this engine over
    /// the reference.  A wall-time ratio: `measured`, host-dependent.
    pub wall_over_reference: Option<f64>,
}

#[derive(Clone, Debug, Serialize)]
pub struct EngineCell {
    pub family: String,
    pub curve: String,
    pub n: u32,
    pub n_prime: u32,
    pub summands: u32,
    pub n_vars: usize,
    pub equations: usize,
    pub targets: usize,
    pub repeats: usize,
    pub reference_engine: String,
    pub d_semireg_min: Option<u32>,
    pub d_semireg_max: Option<u32>,
    /// blake3 over every target's index and reference solution set: two
    /// runs that decided the cell identically have the same digest.
    pub verdict_digest: String,
    pub engines: Vec<EngineSummary>,
    pub per_target: Vec<EngineTarget>,
}

fn system_blake3(
    eqs: &[crate::cryptanalysis::pq_groebner_f2::F2BoolPoly],
    n_vars: usize,
) -> String {
    let mut h = blake3::Hasher::new();
    h.update(&(n_vars as u64).to_le_bytes());
    h.update(&(eqs.len() as u64).to_le_bytes());
    for e in eqs {
        let mut masks: Vec<u64> = e.terms.iter().map(|t| t.mask).collect();
        masks.sort_unstable();
        h.update(&(masks.len() as u64).to_le_bytes());
        for m in masks {
            h.update(&m.to_le_bytes());
        }
    }
    h.finalize().to_hex().to_string()
}

fn median(mut xs: Vec<f64>) -> f64 {
    if xs.is_empty() {
        return f64::NAN;
    }
    xs.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let k = xs.len();
    if k % 2 == 1 {
        xs[k / 2]
    } else {
        0.5 * (xs[k / 2 - 1] + xs[k / 2])
    }
}

/// **Price several engines on one cell, paired.**  The targets are the
/// ones [`price_descent_cell`] draws for the same `(family, n, n', m,
/// seed)`, so the cell is the frozen §14/§16 cell; every engine solves
/// every target `repeats` times, interleaved per target with the engine
/// order rotated each repetition, so host drift falls on all of them
/// alike.  The reference engine — the strongest exhaustive search listed
/// that applies (`fes-f2-wide`, then `fes-f2`, then `exhaustive`), else
/// the first listed engine that enumerates every solution — sets the
/// answers every other engine is checked against.
pub fn price_engine_cell(
    engines: &[(
        String,
        Box<dyn crate::cryptanalysis::ic_framework::stages::SystemSolver>,
        crate::cryptanalysis::ic_framework::stages::Params,
    )],
    family: &str,
    n: u32,
    n_prime: u32,
    summands: u32,
    targets: usize,
    seed: u64,
    budget: Option<std::time::Duration>,
    repeats: usize,
) -> Option<EngineCell> {
    use crate::cryptanalysis::ic_framework::stages::{BooleanSystem, SolverVerdict};
    if n_prime == 0 || n_prime > max_n_prime(summands) || engines.is_empty() {
        return None;
    }
    let inst = instance_for(family, n, seed)?;
    let v_basis = standard_basis(n_prime);
    let mut rng = StdRng::seed_from_u64(seed ^ ((n as u64) << 32) ^ ((summands as u64) << 16));
    let repeats = repeats.max(1);
    let mut per_target: Vec<EngineTarget> = Vec::with_capacity(targets);
    let (mut n_vars, mut equations) = (0usize, 0usize);
    let mut shape = None;
    for _ in 0..targets {
        let x_r = rng.gen::<u64>() & inst.gf.mask;
        let d = descend(&inst.gf, inst.b, x_r, &v_basis, summands).ok()?;
        let system = BooleanSystem {
            equations: d.equations,
            n_vars: d.n_vars,
        };
        let sh = system.shape();
        n_vars = system.n_vars;
        equations = system.equations.len();
        let mut runs: std::collections::BTreeMap<String, Vec<EngineRun>> = Default::default();
        for rep in 0..repeats {
            for k in 0..engines.len() {
                let (name, solver, params) = &engines[(k + rep) % engines.len()];
                // A call that exhausted its budget is not repeated on the
                // same target: its verdict is already "at least the
                // budget", and repeating it would spend the budget again
                // to learn nothing.  Such a target has one run, not
                // `repeats`, and every count on it is a lower bound.
                if runs
                    .get(name)
                    .is_some_and(|rs| rs.iter().any(|r| r.verdict == "budget"))
                {
                    continue;
                }
                let run = if !solver.accepts(&sh) {
                    EngineRun {
                        verdict: "declined".into(),
                        solutions: Vec::new(),
                        ops: 0,
                        wall_ns: 0,
                        degree_reached: None,
                        solving_degree: None,
                        peak_bytes: 0,
                        extra: Default::default(),
                        op_unit: String::new(),
                    }
                } else {
                    let (verdict, cost) = solver.solve(&system, params, budget);
                    let (verdict, mut solutions) = match verdict {
                        SolverVerdict::Solved(s) => ("solved", s),
                        SolverVerdict::Unsatisfiable => ("unsatisfiable", Vec::new()),
                        SolverVerdict::BudgetExceeded => ("budget", Vec::new()),
                    };
                    solutions.sort_unstable();
                    EngineRun {
                        verdict: verdict.into(),
                        solutions,
                        ops: cost.ops,
                        wall_ns: cost.wall_ns,
                        degree_reached: cost.degree_reached,
                        solving_degree: cost.solving_degree,
                        peak_bytes: cost.peak_bytes,
                        extra: cost.extra,
                        op_unit: cost.op_unit,
                    }
                };
                runs.entry(name.clone()).or_default().push(run);
            }
        }
        per_target.push(EngineTarget {
            x_r,
            system_blake3: system_blake3(&system.equations, system.n_vars),
            terms: system.equations.iter().map(|p| p.terms.len() as u64).sum(),
            semi_regular_degree: sh.semi_regular_degree,
            runs,
        });
        shape = Some(sh);
    }
    let shape = shape?;

    // The reference: the strongest exhaustive search that applies, else
    // the first listed engine that enumerates every solution — a
    // first-solution engine cannot say what the full answer is.
    let applies = |name: &str| {
        engines
            .iter()
            .any(|(n, s, _)| n == name && s.accepts(&shape))
    };
    let reference = ["fes-f2-wide", "fes-f2", "exhaustive"]
        .into_iter()
        .find(|r| applies(r))
        .map(str::to_string)
        .or_else(|| {
            engines
                .iter()
                .find(|(_, s, _)| s.finds_every_solution() && s.accepts(&shape))
                .map(|(n, _, _)| n.clone())
        })
        .unwrap_or_else(|| engines[0].0.clone());
    let decided = |r: &EngineRun| r.verdict == "solved" || r.verdict == "unsatisfiable";
    let reference_answer = |t: &EngineTarget| -> Option<Vec<u64>> {
        let runs = &t.runs[&reference];
        runs.iter().all(decided).then(|| runs[0].solutions.clone())
    };

    let mut digest = blake3::Hasher::new();
    for (i, t) in per_target.iter().enumerate() {
        digest.update(&(i as u64).to_le_bytes());
        match reference_answer(t) {
            Some(sols) => {
                digest.update(&(sols.len() as u64).to_le_bytes());
                for s in sols {
                    digest.update(&s.to_le_bytes());
                }
            }
            None => {
                digest.update(b"undecided");
            }
        }
    }

    let mut summaries = Vec::new();
    for (name, solver, _) in engines {
        let declined = !solver.accepts(&shape);
        let every = solver.finds_every_solution();
        let op_unit = per_target
            .iter()
            .flat_map(|t| t.runs[name].iter())
            .map(|r| r.op_unit.as_str())
            .find(|u| !u.is_empty())
            .unwrap_or("")
            .to_string();
        let mut ok = true;
        let (mut n_decided, mut n_budget) = (0usize, 0usize);
        let (mut learn, mut reach): (Vec<u32>, Vec<u32>) = (Vec::new(), Vec::new());
        let (mut ops, mut ms, mut peak) = (Vec::new(), Vec::new(), 0f64);
        let (mut mine_sum, mut ref_sum) = (0f64, 0f64);
        for t in &per_target {
            let runs = &t.runs[name];
            if runs.iter().any(|r| r.verdict == "budget") {
                n_budget += 1;
            }
            ops.push(median(runs.iter().map(|r| r.ops as f64).collect()));
            let my_ms = median(runs.iter().map(|r| r.wall_ns as f64 / 1e6).collect());
            ms.push(my_ms);
            peak = runs
                .iter()
                .map(|r| r.peak_bytes as f64 / 1024.0)
                .fold(peak, f64::max);
            if declined || !runs.iter().all(decided) {
                continue;
            }
            n_decided += 1;
            if let Some(d) = runs[0].solving_degree {
                learn.push(d);
            }
            if let Some(d) = runs[0].degree_reached {
                reach.push(d);
            }
            if let Some(expect) = reference_answer(t) {
                for r in runs {
                    // A first-solution engine is checked for membership:
                    // its answer must be one of the reference's, and it
                    // may report no solution only where there is none.
                    let fine = if every {
                        r.solutions == expect
                    } else {
                        r.solutions.iter().all(|s| expect.contains(s))
                            && r.solutions.is_empty() == expect.is_empty()
                    };
                    ok &= fine;
                }
                let ref_ms = median(
                    t.runs[&reference]
                        .iter()
                        .map(|r| r.wall_ns as f64 / 1e6)
                        .collect(),
                );
                mine_sum += my_ms;
                ref_sum += ref_ms;
            }
        }
        let mean_u =
            |v: &[u32]| (!v.is_empty()).then(|| v.iter().sum::<u32>() as f64 / v.len() as f64);
        summaries.push(EngineSummary {
            engine: name.clone(),
            op_unit,
            workload: if every {
                "complete enumeration"
            } else {
                "first solution"
            }
            .into(),
            declined,
            decided: n_decided,
            over_budget: n_budget,
            agrees_with_reference: ok,
            d_learn_mean: mean_u(&learn),
            d_learn_max: learn.iter().copied().max(),
            d_reach_mean: mean_u(&reach),
            d_reach_max: reach.iter().copied().max(),
            ops_mean: mean(ops.into_iter()),
            ms_mean: mean(ms.iter().copied()),
            ms_max: ms.iter().copied().fold(0.0, f64::max),
            peak_kib_max: peak,
            wall_over_reference: (ref_sum > 0.0 && n_decided > 0).then(|| mine_sum / ref_sum),
        });
    }

    let bounds: Vec<u32> = per_target
        .iter()
        .filter_map(|t| t.semi_regular_degree)
        .collect();
    Some(EngineCell {
        family: family.into(),
        curve: inst.name.clone(),
        n,
        n_prime,
        summands,
        n_vars,
        equations,
        targets,
        repeats,
        reference_engine: reference,
        d_semireg_min: bounds.iter().copied().min(),
        d_semireg_max: bounds.iter().copied().max(),
        verdict_digest: digest.finalize().to_hex().to_string(),
        engines: summaries,
        per_target,
    })
}

fn short_unit(unit: &str) -> &'static str {
    if unit.starts_with("word XORs") {
        "wx"
    } else if unit.starts_with("word operations") {
        "wo"
    } else if unit.starts_with("monomial operations") {
        "mo"
    } else if unit.starts_with("monomial tests") {
        "mt"
    } else if unit.starts_with("conflicts") {
        "cf"
    } else {
        "?"
    }
}

/// The engine table: one row per cell and engine.
pub fn format_engine_markdown(cells: &[EngineCell]) -> String {
    let mut out = String::new();
    out.push_str("| E | n | n' | m | vars | engine | finds | decided | over budget | D_learn | D_reach | D_sr | ops | ms | wall / reference | agrees |\n");
    out.push_str("|:--|--:|--:|--:|--:|:--|:--|--:|--:|--:|--:|:--|--:|--:|--:|:--|\n");
    for c in cells {
        let bound = match (c.d_semireg_min, c.d_semireg_max) {
            (Some(a), Some(b)) if a == b => format!("{a}"),
            (Some(a), Some(b)) => format!("{a}–{b}"),
            _ => "—".into(),
        };
        for e in &c.engines {
            if e.declined {
                out.push_str(&format!(
                    "| {} | {} | {} | {} | {} | {} | | declined | | | | {} | | | | |\n",
                    c.family, c.n, c.n_prime, c.summands, c.n_vars, e.engine, bound
                ));
                continue;
            }
            let deg = |m: Option<f64>| m.map(|v| format!("{v:.1}")).unwrap_or_else(|| "—".into());
            let reference = if e.engine == c.reference_engine {
                "ref".to_string()
            } else {
                e.wall_over_reference
                    .map(|r| format!("{r:.1}×"))
                    .unwrap_or_else(|| "—".into())
            };
            // Agreement over nothing decided is vacuous, so it is not shown.
            let agrees = match (e.decided, e.agrees_with_reference) {
                (0, _) => "—",
                (_, true) => "yes",
                (_, false) => "NO",
            };
            out.push_str(&format!(
                "| {} | {} | {} | {} | {} | {} | {} | {}/{} | {} | {} | {} | {} | {:.3e} {} | {:.1} | {} | {} |\n",
                c.family,
                c.n,
                c.n_prime,
                c.summands,
                c.n_vars,
                e.engine,
                if e.workload == "first solution" { "first" } else { "all" },
                e.decided,
                c.targets,
                e.over_budget,
                deg(e.d_learn_mean),
                deg(e.d_reach_mean),
                bound,
                e.ops_mean,
                short_unit(&e.op_unit),
                e.ms_mean,
                reference,
                agrees
            ));
        }
    }
    out
}

/// The table, in the shape of Petit–Quisquater's Table 2.
pub fn format_markdown(cells: &[DescentCell]) -> String {
    let mut out = String::new();
    out.push_str("| E | n | n' | m | vars | eqs | D_av | D_pair | D_sr | D_av/D_sr | ops | enumerate | ops/enum | ms | KiB | no decomp |\n");
    out.push_str("|:--|--:|--:|--:|--:|--:|--:|--:|:--|--:|--:|--:|--:|--:|--:|--:|\n");
    for c in cells {
        let bound = match (c.d_semireg_min, c.d_semireg_max) {
            (Some(a), Some(b)) if a == b => format!("{a}"),
            (Some(a), Some(b)) => format!("{a}–{b}"),
            _ => "—".into(),
        };
        let ratio = match c.d_av_over_semireg {
            Some(r) => format!("{r:.2}"),
            None => "—".into(),
        };
        out.push_str(&format!(
            "| {} | {} | {} | {} | {} | {} | {:.1} | {:.1} | {} | {} | {:.3e} | {:.3e} | {:.1}x | {:.1} | {:.0} | {}/{} |\n",
            c.family,
            c.n,
            c.n_prime,
            c.summands,
            c.n_vars,
            c.equations,
            c.d_av,
            c.d_pair_av,
            bound,
            ratio,
            c.mono_ops_mean,
            c.brute_force_ops,
            c.ops_over_brute_force,
            c.ms_mean,
            c.peak_kib_max,
            c.inconsistent,
            c.targets,
        ));
        if c.timed_out > 0 {
            out.push_str(&format!(
                "| ^ | | | | | | \u{2014} | \u{2014} | \u{2014} | \u{2014} | \u{2014} | \u{2014} | \u{2014} | \u{2014} | \u{2014} | {} of {} runs hit the budget: every figure on this row is a lower bound |\n",
                c.timed_out, c.targets
            ));
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The instrumentation must report a degree that the run could
    /// actually have reached, a basis it actually returned, and a cost
    /// that grows with the work done.
    #[test]
    fn a_descent_cell_reports_a_degree_and_a_cost() {
        let cell =
            price_descent_cell("K", 11, 4, 2, 3, 7, None).expect("K_1 over GF(2^11) at n'=4");
        assert_eq!(cell.n_vars, 8, "two summands over a 4-dimensional subspace");
        assert_eq!(cell.equations, 11, "one equation per field coordinate");
        assert_eq!(cell.per_target.len(), 3);
        assert!(cell.d_av >= 1.0, "a processed pair has degree at least one");
        assert!(
            cell.d_max as f64 >= cell.d_av,
            "the max cannot be below the mean"
        );
        assert!(
            cell.d_poly_max >= cell.d_max,
            "an intermediate polynomial is at least as high as the pair degree"
        );
        assert!(cell.mono_ops_mean > 0.0, "the run touched monomials");
        assert!(cell.peak_kib_max > 0.0, "the run held a basis");
    }

    /// Both families must be constructible at the same degree, so the
    /// `K` against `R` comparison the table draws is on matched sizes.
    #[test]
    fn both_curve_families_descend_at_the_same_degree() {
        for family in ["K", "R"] {
            let cell = price_descent_cell(family, 11, 3, 2, 2, 11, None)
                .unwrap_or_else(|| panic!("{family} at n = 11"));
            assert_eq!(cell.equations, 11);
            assert_eq!(cell.n_vars, 6);
            assert_eq!(cell.family, family);
        }
    }

    /// **The pruning must not lose a solution.**  The chain criterion
    /// skips S-polynomials on the argument that they cannot contribute;
    /// that argument is standard, but it is being applied here to the
    /// systems this table measures, so it is checked on them: the
    /// variety of the Gröbner basis must equal the variety of the
    /// original equations, computed by enumerating every point of the
    /// subspace.  A criterion that dropped a needed pair would show up
    /// as a basis with solutions the system does not have, or the
    /// reverse.
    #[test]
    fn the_pruned_basis_has_exactly_the_solutions_the_system_has() {
        use crate::cryptanalysis::pq_groebner_f2::{groebner_basis_f2_stats, solve_system_f2};

        let inst = instance_for("K", 11, 5).expect("K_1 over GF(2^11)");
        let v_basis = standard_basis(5);
        let mut rng = StdRng::seed_from_u64(20260922);
        let mut consistent = 0;
        for _ in 0..6 {
            let x_r = rng.gen::<u64>() & inst.gf.mask;
            let sys = descend(&inst.gf, inst.b, x_r, &v_basis, 2).unwrap();
            let (gb, _) = groebner_basis_f2_stats(sys.equations.clone(), sys.n_vars);
            let from_basis: std::collections::HashSet<u64> =
                solve_system_f2(&gb, sys.n_vars).into_iter().collect();
            // Every point of the subspace, checked against the original
            // equations rather than the basis.
            let direct: std::collections::HashSet<u64> = (0..1u64 << sys.n_vars)
                .filter(|v| sys.equations.iter().all(|e| e.eval(*v) == 0))
                .collect();
            assert_eq!(from_basis, direct, "the pruned basis changed the variety");
            if !direct.is_empty() {
                consistent += 1;
            }
        }
        assert!(
            consistent > 0,
            "every target was inconsistent; the fixture proves only that {{1}} has no roots"
        );
    }

    /// The series is short enough to divide by hand, so it is:
    /// `(1+t)^4 / (1+t²)² = 1 + 4t + 4t² − 4t³ + …`, whose first
    /// non-positive coefficient sits at degree three.
    #[test]
    fn the_semi_regular_degree_is_the_first_non_positive_coefficient() {
        assert_eq!(semi_regular_degree(4, &[2, 2]), Some(3));
        // More equations at the same variable count fall earlier, and
        // the degree never exceeds the boolean ring's own ceiling.
        let square = semi_regular_degree(16, &[2; 16]).unwrap();
        let over = semi_regular_degree(16, &[2; 32]).unwrap();
        assert!(over < square, "{over} should fall before {square}");
        assert!(
            square <= 16,
            "a boolean monomial cannot exceed the variable count"
        );
        // Degree-1 equations are linear: they cut the ring down at once.
        assert_eq!(semi_regular_degree(8, &[1; 8]), Some(1));
    }

    /// The descent is symbolic, so the only cap is the monomial mask;
    /// a cell past the old truth-table cap now runs, and one past the
    /// mask declines rather than panic.
    #[test]
    fn the_subspace_dimension_cap_is_the_monomial_mask() {
        assert_eq!(max_n_prime(2), 32);
        assert_eq!(max_n_prime(3), 21);
        assert!(price_descent_cell("K", 17, 33, 2, 1, 3, None).is_none());
        assert!(price_descent_cell("K", 17, 22, 3, 1, 3, None).is_none());
        // Past the truth table's `n' = 8`: the system is built and the
        // engine runs on it, under a budget so the test stays short.
        let cell = price_descent_cell("K", 17, 9, 2, 1, 3, Some(std::time::Duration::from_secs(3)))
            .expect("a cell past the old cap");
        assert_eq!(cell.n_vars, 18);
        assert_eq!(cell.equations, 17);
        // The bound is derived from the shape, so the cell must carry
        // exactly what the series gives for seventeen quadratics in
        // eighteen unknowns.
        assert_eq!(cell.d_semireg_min, semi_regular_degree(18, &[2; 17]));
    }

    /// **The paired cell solves the frozen table's targets, and checks
    /// every engine against the reference.**  Same draw as
    /// [`price_descent_cell`], the reference is the fast exhaustive
    /// search on a quadratic cell, a first-solution engine is checked
    /// for membership rather than equality, and the digest of the
    /// reference answers is a function of the inputs alone, so two runs
    /// of one cell agree on it.
    #[test]
    fn a_paired_engine_cell_is_the_frozen_cell_checked_against_its_reference() {
        use crate::cryptanalysis::ic_framework::solvers::solver_by_name;
        use crate::cryptanalysis::ic_framework::stages::Params;
        let engines = |names: &[&str]| -> Vec<_> {
            names
                .iter()
                .map(|n| (n.to_string(), solver_by_name(n).unwrap(), Params::default()))
                .collect()
        };
        let list = engines(&["f4-f2", "buchberger-f2", "sat-cdcl", "fes-f2", "exhaustive"]);
        let cell = price_engine_cell(&list, "K", 11, 5, 2, 4, 7, None, 2).expect("K at n = 11");
        let frozen = price_descent_cell("K", 11, 5, 2, 4, 7, None).unwrap();
        assert_eq!(
            cell.reference_engine, "fes-f2",
            "the quadratic cell's reference"
        );
        assert_eq!(cell.n_vars, frozen.n_vars);
        for (t, run) in cell.per_target.iter().zip(&frozen.per_target) {
            // The same target: the Buchberger engine inside the paired
            // cell does exactly the work the frozen cell recorded.
            assert_eq!(t.runs["buchberger-f2"][0].ops, run.stats.mono_ops);
            assert_eq!(t.runs["f4-f2"].len(), 2, "every repetition is kept");
        }
        for e in &cell.engines {
            assert!(e.agrees_with_reference, "{} disagrees", e.engine);
            assert_eq!(e.decided, 4, "{} left a target undecided", e.engine);
        }
        let cdcl = cell
            .engines
            .iter()
            .find(|e| e.engine == "sat-cdcl")
            .unwrap();
        assert_eq!(cdcl.workload, "first solution");
        // The reference order does not depend on the listed order, and the
        // digest depends on the inputs and answers only.
        let reordered = engines(&["exhaustive", "f4-f2", "fes-f2"]);
        let again = price_engine_cell(&reordered, "K", 11, 5, 2, 4, 7, None, 1).unwrap();
        assert_eq!(again.reference_engine, "fes-f2");
        assert_eq!(again.verdict_digest, cell.verdict_digest);
        assert_eq!(
            again
                .per_target
                .iter()
                .map(|t| &t.system_blake3)
                .collect::<Vec<_>>(),
            cell.per_target
                .iter()
                .map(|t| &t.system_blake3)
                .collect::<Vec<_>>()
        );
        // A cubic cell has no quadratic reference, so the general one is used.
        let cubic = price_engine_cell(&reordered, "K", 7, 2, 3, 2, 7, None, 1).unwrap();
        assert_eq!(cubic.reference_engine, "exhaustive");
        assert!(
            cubic
                .engines
                .iter()
                .find(|e| e.engine == "fes-f2")
                .unwrap()
                .declined
        );
    }
}
