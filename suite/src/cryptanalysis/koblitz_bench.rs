//! # Measurement harness for Koblitz-curve index-calculus decomposition.
//!
//! The decomposition oracle is the step that decides whether index
//! calculus on subfield curves can ever reach a curve anyone deploys.
//! [`crate::cryptanalysis::koblitz_index_calculus`] ships three of them
//! — exhaustive search, matrix-F4 over the Semaev system, and CDCL SAT
//! over the same system — and they agree on every instance tested.  What
//! was missing is *numbers*: how the instance grows with the field, how
//! the algebra behaves on it, and which of the three wins where.
//!
//! This module produces those numbers reproducibly, so the question can
//! be worked as an optimisation target rather than an opinion.  See
//! `research/notes/ecc2k130/RESEARCH_KOBLITZ_SCALING_TARGET.md` for the pre-registered
//! hypotheses these measurements are meant to settle.
//!
//! ## Two measurements, two reachable ranges
//!
//! **System structure** ([`profile_system`]) needs only the field and
//! the Frobenius-invariant subspace — no curve, no point counting, no
//! materialised factor base.  It therefore runs far past
//! [`crate::cryptanalysis::koblitz_index_calculus::MAX_N`], out to
//! `n = 63`, which is where the interesting scaling lives.  It reports
//! the unknown/equation counts, the degree, the Macaulay rank profile
//! and the **first fall degree**, using the same operational definition
//! as [`crate::cryptanalysis::ffd_harness`] so the subspace-restricted
//! numbers are directly comparable with that harness's full-field ones.
//!
//! **Oracle cost** ([`bench_instance`]) needs a real curve with a
//! prime-order subgroup, so it is capped at `MAX_N`.  It runs all three
//! oracles over the same random targets, checks they agree, and reports
//! median wall-clock per target.
//!
//! ## The cost model the target attacks
//!
//! An `m`-point decomposition chains `m − 1` copies of `S₃` over `m − 2`
//! intermediate points, and those intermediates range over the *whole*
//! field rather than the subspace:
//!
//! ```text
//!     unknowns(n, ℓ, m) = m·ℓ + (m − 2)·n.
//! ```
//!
//! The first term is what the factor base costs; the second is pure
//! bookkeeping, and it dominates.  A useful attack needs `m ≈ n/ℓ`
//! summands, so the chaining term grows like `n²/ℓ` — which is why the
//! solvable instances stop where they do, and why [`n_vars_for`] is the
//! number to drive down.
//!
//! ## What this is not
//!
//! Not a claim that any of this threatens a deployed curve.  The
//! largest instance here is `n = 63` for *structure* and `n ≤ 24` for a
//! full solve; sect163k1 is far away, and the paper's own conclusion is
//! that index calculus stays worse than rho at deployed sizes.  The
//! harness exists to find out *how far* away, with measurements instead
//! of extrapolation.

use std::time::Instant;

use num_bigint::BigUint;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};

use crate::binary_ecc::{BinaryPoint, F2mElement};
use crate::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, first_fall_degree, solving_degree, system_degree, FieldStructure,
    MacaulayProfile, SolverEngine,
};
use crate::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base, enumerate_decompose, groebner_decompose, invariant_subspace_basis,
    order_of_2_mod_n, sat_decompose, KoblitzCurve,
};
use crate::cryptanalysis::pq_groebner_f2::{F2BoolMono, F2BoolPoly};

/// Unknowns in the chained `m`-point decomposition system: `m·ℓ`
/// subspace coordinates plus `(m − 2)·n` for the intermediate points.
///
/// The baseline the scaling target tries to beat.
pub fn n_vars_for(n: u32, ell: u32, m: usize) -> usize {
    m * ell as usize + m.saturating_sub(2) * n as usize
}

/// Largest `m` whose system still fits the 64-variable Boolean-monomial
/// budget, or `None` if even `m = 2` does not.
pub fn max_m_within_budget(n: u32, ell: u32, budget: usize) -> Option<usize> {
    (2..=64).rfind(|&m| n_vars_for(n, ell, m) <= budget)
}

// ── System structure ───────────────────────────────────────────────

/// Structure of one decomposition system: size, degree, and how its
/// Macaulay matrices rank up.
#[derive(Clone, Debug)]
pub struct SystemProfile {
    /// Extension degree.
    pub n: u32,
    /// `ℓ = ord_n(2)`, the invariant subspace dimension.
    pub ell: u32,
    /// Summands.
    pub m: usize,
    /// Boolean unknowns.
    pub n_vars: usize,
    /// Boolean equations (`n` per `S₃` link).
    pub n_eqs: usize,
    /// Total degree of the system: 2 for `m = 2`, 3 once chained.
    pub degree: u32,
    /// First fall degree, by the `ffd_harness` definition: smallest
    /// `D ≥ 2` with `rank < rows` and `rank < cols`.
    pub fall_degree: Option<u32>,
    /// Per-degree Macaulay rank profile.
    pub macaulay: Vec<MacaulayProfile>,
    /// Milliseconds spent profiling.
    pub elapsed_ms: f64,
}

impl SystemProfile {
    /// Equations per unknown.  Below 1 the system is underdetermined
    /// and a refutation has to rule out a large solution space; the
    /// measured refutation blow-ups sit at the low end of this ratio.
    pub fn eq_var_ratio(&self) -> f64 {
        if self.n_vars == 0 {
            0.0
        } else {
            self.n_eqs as f64 / self.n_vars as f64
        }
    }
}

/// **Profile the decomposition system** for extension degree `n`, the
/// `factor_index`-th invariant subspace, and `m` summands.
///
/// The target abscissa is drawn from `x_seed`; `S₃` does not involve the
/// curve parameter `a`, and `b = 1` for every Koblitz curve, so no curve
/// is needed — only the field and the subspace.
///
/// Returns `None` when `n` has no non-trivial invariant subspace, when
/// the system exceeds the 64-variable Boolean budget, or when `n ≥ 64`.
pub fn profile_system(
    n: u32,
    factor_index: usize,
    m: usize,
    d_max: u32,
    x_seed: u64,
) -> Option<SystemProfile> {
    let (irr, basis) = invariant_subspace_basis(n, factor_index)?;
    let st = FieldStructure::new(n, &irr);
    let b = F2mElement::one(n);
    let mut rng = StdRng::seed_from_u64(x_seed);
    let x_r = F2mElement::from_biguint(&BigUint::from(rng.gen::<u64>()), n);

    let start = Instant::now();
    let sys = build_decomposition_system(&basis, &x_r, &b, m, &st)?;
    let degree = sys
        .equations
        .iter()
        .flat_map(|e| e.terms.iter())
        .map(|t| t.mask.count_ones())
        .max()
        .unwrap_or(0);
    let (fall_degree, macaulay) = first_fall_degree(&sys.equations, sys.n_vars, d_max);
    let elapsed_ms = start.elapsed().as_secs_f64() * 1e3;

    Some(SystemProfile {
        n,
        ell: basis.len() as u32,
        m,
        n_vars: sys.n_vars,
        n_eqs: sys.equations.len(),
        degree,
        fall_degree,
        macaulay,
        elapsed_ms,
    })
}

/// First-fall-degree statistics over several target draws.
///
/// The fall degree is a property of the *system*, and the system
/// depends on the target abscissa `x(R)`.  A single draw is therefore a
/// noisy statistic — measured on `K / F_2^9` at `m = 2`, one draw falls
/// at `D = 2` and another shows no fall to `D = 3`.  Anything built on
/// this number has to average.
#[derive(Clone, Debug)]
pub struct FfdSummary {
    /// Extension degree.
    pub n: u32,
    /// Subspace dimension.
    pub ell: u32,
    /// Summands.
    pub m: usize,
    /// Boolean unknowns.
    pub n_vars: usize,
    /// Boolean equations.
    pub n_eqs: usize,
    /// System degree.
    pub degree: u32,
    /// Draws taken.
    pub trials: usize,
    /// Smallest fall degree seen.
    pub fall_min: Option<u32>,
    /// Largest fall degree seen.
    pub fall_max: Option<u32>,
    /// Draws with no fall at or below `d_max`.
    pub no_fall: usize,
    /// Mean rank deficit `rows − rank` at `D = 2`, over the draws.
    pub mean_syzygies_d2: f64,
}

/// Profile `trials` independent target draws and summarise the fall
/// degree across them.
pub fn ffd_summary(
    n: u32,
    factor_index: usize,
    m: usize,
    d_max: u32,
    seed: u64,
    trials: usize,
) -> Option<FfdSummary> {
    let mut falls: Vec<Option<u32>> = Vec::with_capacity(trials);
    let mut syz = Vec::with_capacity(trials);
    let mut first: Option<SystemProfile> = None;
    for t in 0..trials {
        let p = profile_system(n, factor_index, m, d_max, seed.wrapping_add(t as u64))?;
        falls.push(p.fall_degree);
        if let Some(q) = p.macaulay.iter().find(|q| q.degree == 2) {
            syz.push(q.syzygies() as f64);
        }
        if first.is_none() {
            first = Some(p);
        }
    }
    let p = first?;
    let seen: Vec<u32> = falls.iter().flatten().copied().collect();
    Some(FfdSummary {
        n,
        ell: p.ell,
        m,
        n_vars: p.n_vars,
        n_eqs: p.n_eqs,
        degree: p.degree,
        trials,
        fall_min: seen.iter().copied().min(),
        fall_max: seen.iter().copied().max(),
        no_fall: falls.iter().filter(|f| f.is_none()).count(),
        mean_syzygies_d2: if syz.is_empty() {
            0.0
        } else {
            syz.iter().sum::<f64>() / syz.len() as f64
        },
    })
}

/// Summarise the fall degree for every `(n, m)` in the sweep.
pub fn sweep_ffd(
    ns: &[u32],
    ms: &[usize],
    d_max: u32,
    seed: u64,
    trials: usize,
) -> Vec<FfdSummary> {
    let mut out = Vec::new();
    for &n in ns {
        for &m in ms {
            if let Some(s) = ffd_summary(n, 0, m, d_max, seed, trials) {
                out.push(s);
            }
        }
    }
    out
}

/// Markdown table of fall-degree summaries.
pub fn format_ffd_table(rows: &[FfdSummary]) -> String {
    let mut out = String::new();
    out.push_str("| n | ℓ | m | vars | eqs | deg | FFD min | FFD max | no fall | mean syz D=2 |\n");
    out.push_str("|--:|--:|--:|-----:|----:|----:|--------:|--------:|--------:|-------------:|\n");
    for r in rows {
        let f = |v: Option<u32>| v.map(|d| d.to_string()).unwrap_or_else(|| "—".into());
        out.push_str(&format!(
            "| {} | {} | {} | {} | {} | {} | {} | {} | {}/{} | {:.2} |\n",
            r.n,
            r.ell,
            r.m,
            r.n_vars,
            r.n_eqs,
            r.degree,
            f(r.fall_min),
            f(r.fall_max),
            r.no_fall,
            r.trials,
            r.mean_syzygies_d2
        ));
    }
    out
}

/// Profile every `(n, m)` in the sweep, skipping what does not fit.
pub fn sweep_systems(ns: &[u32], ms: &[usize], d_max: u32, x_seed: u64) -> Vec<SystemProfile> {
    let mut out = Vec::new();
    for &n in ns {
        for &m in ms {
            if let Some(p) = profile_system(n, 0, m, d_max, x_seed) {
                out.push(p);
            }
        }
    }
    out
}

// ── Oracle cost ────────────────────────────────────────────────────

/// Timing and verdicts for one oracle over a set of targets.
#[derive(Clone, Debug)]
pub struct OracleRun {
    /// `"search"`, `"matrix-f4"` or `"sat"`.
    pub oracle: &'static str,
    /// Targets that decomposed.
    pub decomposed: usize,
    /// Targets proven not to decompose (an F4 certificate or an UNSAT).
    /// Exhaustive search never *proves* anything beyond its own sweep,
    /// so it reports its negatives here too.
    pub refuted: usize,
    /// Targets where the oracle ran out of budget — neither a
    /// decomposition nor a refutation.
    pub inconclusive: usize,
    /// Median milliseconds per target, over all targets.
    pub median_ms: f64,
    /// Median milliseconds over the targets that *did* decompose.
    ///
    /// Kept separate from [`Self::median_refuted_ms`] because the two
    /// regimes differ by orders of magnitude and averaging them hides
    /// it: finding one root among many is easy, proving there is no
    /// root is not.  A single median over both is a number that
    /// describes neither.
    pub median_found_ms: f64,
    /// Median milliseconds over the targets that did not decompose —
    /// the refutation cost.
    pub median_refuted_ms: f64,
    /// Total milliseconds over all targets.
    pub total_ms: f64,
}

/// One benchmarked instance: all three oracles over the same targets.
#[derive(Clone, Debug)]
pub struct InstanceBench {
    /// Curve parameter.
    pub a: u8,
    /// Extension degree.
    pub n: u32,
    /// Subspace dimension.
    pub ell: u32,
    /// Summands.
    pub m: usize,
    /// Factor-base size.
    pub fb_size: usize,
    /// `π`-orbits, i.e. linear-algebra unknowns.
    pub orbits: usize,
    /// Boolean unknowns in the decomposition system.
    pub n_vars: usize,
    /// Targets tried.
    pub targets: usize,
    /// Per-oracle results.
    pub runs: Vec<OracleRun>,
    /// Targets where the three oracles did not return the same verdict.
    /// **Must be zero**; anything else is a bug, not a measurement.
    pub disagreements: usize,
}

/// Median, or `NaN` when there is nothing to take a median of.
///
/// Deliberately not `0.0`: an empty class means the oracle never hit
/// that case, and reporting it as zero milliseconds would be a
/// measurement claim that is false.  `NaN` serialises to `null`.
fn median(mut xs: Vec<f64>) -> f64 {
    if xs.is_empty() {
        return f64::NAN;
    }
    xs.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let mid = xs.len() / 2;
    if xs.len().is_multiple_of(2) {
        (xs[mid - 1] + xs[mid]) / 2.0
    } else {
        xs[mid]
    }
}

/// **Benchmark all three oracles** on `targets` pseudo-random points of
/// `⟨G⟩`, checking they agree.
///
/// `node_budget` bounds the F4 splitting search, `max_models` the SAT
/// model enumeration, and `macaulay_degree` selects the implied rows
/// handed to the SAT solver (`Some(2)` is the default elsewhere); a `None` from either with its budget spent is
/// counted as inconclusive rather than as a refutation.
///
/// Returns `None` if the curve or the factor base cannot be built.
#[allow(clippy::too_many_arguments)]
pub fn bench_instance(
    a: u8,
    n: u32,
    factor_index: usize,
    m: usize,
    targets: usize,
    seed: u64,
    node_budget: usize,
    max_models: usize,
    macaulay_degree: Option<u32>,
) -> Option<InstanceBench> {
    let kc = KoblitzCurve::new(a, n)?;
    let fb = build_frobenius_factor_base(&kc, factor_index)?;
    let index_of = fb.index_map();
    let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
    let g = kc.generator().clone();
    let n_vars = n_vars_for(n, fb.ell, m);

    let mut rng = StdRng::seed_from_u64(seed);
    let r_u64 = kc
        .subgroup_order
        .to_u64_digits()
        .first()
        .copied()
        .unwrap_or(2)
        .max(2);
    let points: Vec<BinaryPoint> = (0..targets)
        .map(|_| kc.mul(&g, &BigUint::from(rng.gen_range(1..r_u64))))
        .collect();

    // (decomposed, refuted, inconclusive, all_ms, found_ms, refuted_ms)
    type Acc = (usize, usize, usize, Vec<f64>, Vec<f64>, Vec<f64>);
    let mut search: Acc = (0, 0, 0, Vec::new(), Vec::new(), Vec::new());
    let mut f4: Acc = (0, 0, 0, Vec::new(), Vec::new(), Vec::new());
    let mut sat: Acc = (0, 0, 0, Vec::new(), Vec::new(), Vec::new());
    let mut disagreements = 0usize;

    for target in &points {
        let t = Instant::now();
        let by_search = enumerate_decompose(&kc, &fb, &index_of, target, m);
        let ms = t.elapsed().as_secs_f64() * 1e3;
        search.3.push(ms);
        if by_search.is_some() {
            search.0 += 1;
            search.4.push(ms);
        } else {
            search.1 += 1;
            search.5.push(ms);
        }

        let t = Instant::now();
        let (by_f4, f4_stats) = groebner_decompose(
            &kc,
            &fb,
            &index_of,
            &st,
            target,
            m,
            SolverEngine::default(),
            node_budget,
        );
        let ms = t.elapsed().as_secs_f64() * 1e3;
        f4.3.push(ms);
        match (&by_f4, f4_stats.exhausted) {
            (Some(_), _) => {
                f4.0 += 1;
                f4.4.push(ms);
            }
            (None, false) => {
                f4.1 += 1;
                f4.5.push(ms);
            }
            (None, true) => f4.2 += 1,
        }

        let t = Instant::now();
        let (by_sat, sat_stats) = sat_decompose(
            &kc,
            &fb,
            &index_of,
            &st,
            target,
            m,
            max_models,
            macaulay_degree,
        );
        let ms = t.elapsed().as_secs_f64() * 1e3;
        sat.3.push(ms);
        match (&by_sat, sat_stats.refuted) {
            (Some(_), _) => {
                sat.0 += 1;
                sat.4.push(ms);
            }
            (None, true) => {
                sat.1 += 1;
                sat.5.push(ms);
            }
            (None, false) => sat.2 += 1,
        }

        // Agreement gate: a decomposition found by one oracle must be
        // found by all, and every returned decomposition must be real.
        let verdicts = [by_search.is_some(), by_f4.is_some(), by_sat.is_some()];
        if !(verdicts.iter().all(|v| *v) || verdicts.iter().all(|v| !*v)) {
            disagreements += 1;
        }
        for found in [&by_search, &by_f4, &by_sat].into_iter().flatten() {
            let mut acc = BinaryPoint::Infinity;
            for i in found {
                acc = kc.add(&acc, &fb.points[*i]);
            }
            if &acc != target {
                disagreements += 1;
            }
        }
    }

    let pack =
        |name: &'static str, v: (usize, usize, usize, Vec<f64>, Vec<f64>, Vec<f64>)| OracleRun {
            oracle: name,
            decomposed: v.0,
            refuted: v.1,
            inconclusive: v.2,
            median_ms: median(v.3.clone()),
            median_found_ms: median(v.4.clone()),
            median_refuted_ms: median(v.5.clone()),
            total_ms: v.3.iter().sum(),
        };

    Some(InstanceBench {
        a,
        n,
        ell: fb.ell,
        m,
        fb_size: fb.points.len(),
        orbits: fb.unknowns(),
        n_vars,
        targets,
        runs: vec![
            pack("search", search),
            pack("matrix-f4", f4),
            pack("sat", sat),
        ],
        disagreements,
    })
}

// ── Reporting ──────────────────────────────────────────────────────

/// Markdown table of system profiles.
pub fn format_system_table(profiles: &[SystemProfile]) -> String {
    let mut out = String::new();
    out.push_str(
        "| n | ℓ | m | vars | eqs | deg | FFD | D=2 rows×cols (rank) | D=3 rows×cols (rank) |\n",
    );
    out.push_str(
        "|--:|--:|--:|-----:|----:|----:|----:|---------------------:|---------------------:|\n",
    );
    for p in profiles {
        let cell = |d: u32| match p.macaulay.iter().find(|q| q.degree == d) {
            Some(q) => format!("{}×{} ({})", q.rows, q.cols, q.rank),
            None => "—".to_string(),
        };
        out.push_str(&format!(
            "| {} | {} | {} | {} | {} | {} | {} | {} | {} |\n",
            p.n,
            p.ell,
            p.m,
            p.n_vars,
            p.n_eqs,
            p.degree,
            p.fall_degree
                .map(|d| d.to_string())
                .unwrap_or_else(|| "—".into()),
            cell(2),
            cell(3),
        ));
    }
    out
}

/// Markdown table of oracle costs.
pub fn format_oracle_table(benches: &[InstanceBench]) -> String {
    let mut out = String::new();
    out.push_str(
        "| curve | n | ℓ | m | \\|F\\| | vars | oracle | found | refuted | inconc | median ms | med found | med refuted |\n",
    );
    out.push_str(
        "|:------|--:|--:|--:|------:|-----:|:-------|------:|--------:|-------:|----------:|----------:|------------:|\n",
    );
    for b in benches {
        for r in &b.runs {
            out.push_str(&format!(
                "| K_{} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {:.3} | {:.3} | {:.3} |\n",
                b.a,
                b.n,
                b.ell,
                b.m,
                b.fb_size,
                b.n_vars,
                r.oracle,
                r.decomposed,
                r.refuted,
                r.inconclusive,
                r.median_ms,
                r.median_found_ms,
                r.median_refuted_ms
            ));
        }
    }
    out
}

/// Machine-readable dump, for autolab runs that want to diff against a
/// previous baseline rather than read a table.
pub fn to_json(profiles: &[SystemProfile], benches: &[InstanceBench]) -> String {
    let systems: Vec<serde_json::Value> = profiles
        .iter()
        .map(|p| {
            serde_json::json!({
                "n": p.n, "ell": p.ell, "m": p.m,
                "n_vars": p.n_vars, "n_eqs": p.n_eqs, "degree": p.degree,
                "eq_var_ratio": p.eq_var_ratio(),
                "fall_degree": p.fall_degree,
                "macaulay": p.macaulay.iter().map(|q| serde_json::json!({
                    "degree": q.degree, "rows": q.rows, "cols": q.cols,
                    "rank": q.rank, "syzygies": q.syzygies(),
                })).collect::<Vec<_>>(),
                "elapsed_ms": p.elapsed_ms,
            })
        })
        .collect();
    let oracles: Vec<serde_json::Value> = benches
        .iter()
        .map(|b| {
            serde_json::json!({
                "a": b.a, "n": b.n, "ell": b.ell, "m": b.m,
                "fb_size": b.fb_size, "orbits": b.orbits, "n_vars": b.n_vars,
                "targets": b.targets, "disagreements": b.disagreements,
                "runs": b.runs.iter().map(|r| serde_json::json!({
                    "oracle": r.oracle, "decomposed": r.decomposed,
                    "refuted": r.refuted, "inconclusive": r.inconclusive,
                    "median_ms": r.median_ms,
                    "median_found_ms": r.median_found_ms,
                    "median_refuted_ms": r.median_refuted_ms,
                    "total_ms": r.total_ms,
                })).collect::<Vec<_>>(),
            })
        })
        .collect();
    serde_json::json!({ "systems": systems, "oracles": oracles }).to_string()
}

/// The `n` values with a non-trivial Frobenius-invariant subspace of
/// dimension `≤ max_ell`, in range — the ladder every sweep walks.
pub fn subspace_ladder(n_max: u32, max_ell: u32) -> Vec<(u32, u32)> {
    (5..=n_max)
        .step_by(2)
        .filter_map(|n| order_of_2_mod_n(n).map(|l| (n, l)))
        .filter(|(n, l)| *l <= max_ell && *l < *n)
        .collect()
}

// ── Solving degree vs first fall degree ────────────────────────────

/// One `(n, m)` cell of the solving-degree sweep.
///
/// The first fall degree is what the Petit–Quisquater complexity
/// argument is stated in; the solving degree is what the linear algebra
/// actually costs.  `research/notes/index-calculus/RESEARCH_DREG_MEASUREMENT.md` says why the gap
/// between them is the measurement worth having, and
/// `control_solve_mean` is the null object that says whether any of it
/// is structure rather than shape.
#[derive(Clone, Debug)]
pub struct DregSummary {
    /// Extension degree.
    pub n: u32,
    /// Subspace dimension.
    pub ell: u32,
    /// Summands.
    pub m: usize,
    /// Boolean unknowns.
    pub n_vars: usize,
    /// Boolean equations.
    pub n_eqs: usize,
    /// System total degree.
    pub degree: u32,
    /// Target draws taken.
    pub trials: usize,
    /// Mean first fall degree over the draws that fell.
    pub fall_mean: Option<f64>,
    /// Mean degree at which a **non-decomposable** target was refuted.
    ///
    /// This is the number that sets the attack's cost.  The
    /// decomposition probability is tiny, so almost every call in
    /// relation collection is a refutation, and the Macaulay matrix at
    /// this degree is what each of those calls has to build.
    pub refute_mean: Option<f64>,
    /// Largest refutation degree seen.
    pub refute_max: Option<u32>,
    /// Draws refuted at or below `d_max`.
    pub refuted: usize,
    /// Mean degree at which a decomposable target had every variable
    /// pinned.  Reported separately because it is a different event: a
    /// target with two or more decompositions can never be pinned, and
    /// that is a property of the target, not a failure of the algebra.
    pub pin_mean: Option<f64>,
    /// Draws resolved by pinning.
    pub pinned: usize,
    /// Draws that neither refuted nor pinned at or below `d_max`, or
    /// whose Macaulay matrix exceeded the size caps first.
    pub unresolved: usize,
    /// Highest Macaulay degree actually built on any draw.
    ///
    /// The difference between "measured, and the degree is high" and
    /// "could not be measured" lives here.  When this is below `d_max`
    /// on an unresolved cell, the sweep ran out of *matrix*, not out of
    /// degree: [`crate::cryptanalysis::koblitz_groebner::solving_profile`]
    /// returned `None` because the Macaulay matrix exceeded the size
    /// caps, and nothing about the system's solving degree has been
    /// established.
    pub max_degree_built: Option<u32>,
    /// Mean refutation degree of the **shape-matched** control: same
    /// variable count, equation count, total degree and term density,
    /// no Semaev structure.
    ///
    /// Read this together with `Self::control_is_satisfiable`.  With
    /// `n_eqs < n_vars` a random system has `2^(n_vars − n_eqs)`
    /// expected solutions, so it is satisfiable by construction and can
    /// neither refute nor pin — it cannot produce the event being
    /// measured, and a `None` here is uninformative rather than a
    /// finding.  That is why the second control exists.
    pub control_solve_mean: Option<f64>,
    /// Shape-matched control draws that did not resolve.
    pub control_unresolved: usize,
    /// `2^(n_vars − n_eqs)` expected solutions of the shape-matched
    /// control: when this exceeds 1 the control cannot refute.
    pub control_expected_solutions: f64,
    /// Mean refutation degree of the **infeasible** control: same
    /// variables, degree and term density, but enough equations
    /// (`n_vars + 4`) that it has no solution with high probability, so
    /// it refutes and is comparable like for like with the real
    /// systems' refutation degree.
    ///
    /// Shape and feasibility cannot both be matched at once — matching
    /// the equation count is what makes the first control satisfiable.
    /// The two controls bracket the question instead.
    pub control_unsat_mean: Option<f64>,
    /// Infeasible-control draws that did not resolve.
    pub control_unsat_unresolved: usize,
    /// Highest Macaulay degree built on a **shape-matched** control draw.
    ///
    /// The controls need this for the same reason the real systems do:
    /// without it, "did not resolve by `d_max`" and "exceeded the size
    /// caps" are the same output, and only the first of those says
    /// anything.  Omitting it once forced the `n = 5, m = 3` attribution
    /// to be settled by hand-computing the matrix size.
    pub control_shape_max_degree_built: Option<u32>,
    /// Highest Macaulay degree built on an **infeasible** control draw.
    ///
    /// Kept separate from the shape-matched arm rather than folded into
    /// one maximum, because the two arms have different row counts: the
    /// infeasible arm carries `n_vars + 4` equations against the
    /// shape-matched arm's `n_eqs`, so it reaches the row cap at a
    /// *lower* degree.  A shared `max()` would report a degree the
    /// infeasible arm never built — and that arm is precisely the one
    /// whose non-resolution carries the attribution, so the field meant
    /// to prove "not a cap artifact" would have been the field lying
    /// about it.
    pub control_unsat_max_degree_built: Option<u32>,
}

impl DregSummary {
    /// `solve_mean − fall_mean`: how far the degree that costs
    /// anything sits above the degree the complexity claim is stated
    /// in.  The first-fall-degree assumption is the assertion that this
    /// stays bounded as `n` grows.
    pub fn gap(&self) -> Option<f64> {
        Some(self.refute_mean? - self.fall_mean?)
    }
}

/// A random boolean system with a prescribed shape: `n_eqs` equations
/// over `n_vars` variables, each a sum of `terms_per_eq` monomials of
/// degree at most `degree`.
///
/// This is the null object for the sweep.  If the Semaev systems
/// resolve at the same degree as these, then their algebraic structure
/// is buying nothing and the measurement is of the shape alone.
pub fn random_control_system(
    n_vars: usize,
    n_eqs: usize,
    degree: u32,
    terms_per_eq: usize,
    seed: u64,
) -> Vec<F2BoolPoly> {
    let mut rng = StdRng::seed_from_u64(seed);
    (0..n_eqs)
        .map(|_| {
            let monos: Vec<F2BoolMono> = (0..terms_per_eq.max(1))
                .map(|_| {
                    let d = 1 + rng.gen::<u32>() % degree.max(1);
                    let mut mask = 0u64;
                    while mask.count_ones() < d {
                        mask |= 1u64 << (rng.gen::<u32>() % n_vars as u32);
                    }
                    F2BoolMono::from_mask(mask)
                })
                .collect();
            F2BoolPoly::from_monos(monos, n_vars)
        })
        .collect()
}

/// Measure first fall degree and solving degree on the same systems,
/// over `trials` independent target draws, against the matched random
/// control.
/// `with_control` runs the matched random null object as well.  It is
/// the expensive half of the sweep by a wide margin — a random system
/// of this shape does not refute until a high degree, so it pays the
/// full `binom(n_vars, d_max)` Macaulay cost on every draw, while the
/// Semaev systems resolve early and stop.  Turn it off to extend the
/// `n` ladder, on to interpret any single cell.
pub fn dreg_summary(
    n: u32,
    factor_index: usize,
    m: usize,
    d_max: u32,
    trials: usize,
    seed: u64,
    with_control: bool,
) -> Option<DregSummary> {
    let (irr, basis) = invariant_subspace_basis(n, factor_index)?;
    let st = FieldStructure::new(n, &irr);
    let b = F2mElement::one(n);
    let mut rng = StdRng::seed_from_u64(seed);

    let mut falls: Vec<u32> = Vec::new();
    let mut refutes: Vec<u32> = Vec::new();
    let mut pins: Vec<u32> = Vec::new();
    let mut unresolved = 0usize;
    let mut max_degree_built: Option<u32> = None;
    let mut shape: Option<(usize, usize, u32, usize)> = None;

    for _ in 0..trials {
        let x_r = F2mElement::from_biguint(&BigUint::from(rng.gen::<u64>()), n);
        let sys = match build_decomposition_system(&basis, &x_r, &b, m, &st) {
            Some(s) => s,
            None => continue,
        };
        let deg = system_degree(&sys.equations);
        let terms: usize =
            sys.equations.iter().map(|e| e.terms.len()).sum::<usize>() / sys.equations.len().max(1);
        shape = Some((sys.n_vars, sys.equations.len(), deg, terms));

        let (fall, _) = first_fall_degree(&sys.equations, sys.n_vars, d_max);
        if let Some(f) = fall {
            falls.push(f);
        }
        let (d, profs) = solving_degree(&sys.equations, sys.n_vars, d_max);
        if let Some(top) = profs.last().map(|p| p.degree) {
            max_degree_built = Some(max_degree_built.map_or(top, |x: u32| x.max(top)));
        }
        match d {
            Some(d) => {
                // `solving_degree` stops at the first resolving degree,
                // so the last profile is the one that resolved.
                if profs.last().map(|p| p.refuted).unwrap_or(false) {
                    refutes.push(d);
                } else {
                    pins.push(d);
                }
            }
            None => unresolved += 1,
        }
    }

    let (n_vars, n_eqs, degree, terms_per_eq) = shape?;

    // Matched control, same number of draws.  A random system of this
    // shape is overwhelmingly infeasible, so its resolving event is a
    // refutation too, and the two numbers compare like for like.
    let mut control: Vec<u32> = Vec::new();
    let mut control_unresolved = 0usize;
    let mut control_unsat: Vec<u32> = Vec::new();
    let mut control_unsat_unresolved = 0usize;
    let mut control_shape_max_degree_built: Option<u32> = None;
    let mut control_unsat_max_degree_built: Option<u32> = None;
    let note_ctrl = |profs: &[crate::cryptanalysis::koblitz_groebner::SolvingProfile],
                     acc: &mut Option<u32>| {
        if let Some(top) = profs.last().map(|p| p.degree) {
            *acc = Some(acc.map_or(top, |x: u32| x.max(top)));
        }
    };
    for t in 0..(if with_control { trials } else { 0 }) {
        // A fresh control per draw, deterministically derived from the
        // sweep seed so the whole table replays.
        let control_seed = seed
            .wrapping_mul(0x9E37_79B9_7F4A_7C15)
            .wrapping_add(t as u64);
        let polys = random_control_system(n_vars, n_eqs, degree, terms_per_eq, control_seed);
        let (cd, cprofs) = solving_degree(&polys, n_vars, d_max);
        note_ctrl(&cprofs, &mut control_shape_max_degree_built);
        match cd {
            Some(d) => control.push(d),
            None => control_unresolved += 1,
        }

        // Second control: overdetermined, so infeasible with high
        // probability, so it can actually refute.
        let unsat = random_control_system(
            n_vars,
            n_vars + 4,
            degree,
            terms_per_eq,
            control_seed.wrapping_mul(0xA24B_AED4_963E_E407),
        );
        let (ud, uprofs) = solving_degree(&unsat, n_vars, d_max);
        note_ctrl(&uprofs, &mut control_unsat_max_degree_built);
        match ud {
            Some(d) => control_unsat.push(d),
            None => control_unsat_unresolved += 1,
        }
    }

    let mean = |v: &[u32]| {
        if v.is_empty() {
            None
        } else {
            Some(v.iter().map(|&x| x as f64).sum::<f64>() / v.len() as f64)
        }
    };

    Some(DregSummary {
        n,
        ell: basis.len() as u32,
        m,
        n_vars,
        n_eqs,
        degree,
        trials,
        fall_mean: mean(&falls),
        refute_mean: mean(&refutes),
        refute_max: refutes.iter().copied().max(),
        refuted: refutes.len(),
        pin_mean: mean(&pins),
        pinned: pins.len(),
        unresolved,
        max_degree_built,
        control_solve_mean: mean(&control),
        control_unresolved,
        control_expected_solutions: 2f64.powi(n_vars as i32 - n_eqs as i32),
        control_unsat_mean: mean(&control_unsat),
        control_unsat_unresolved,
        control_shape_max_degree_built,
        control_unsat_max_degree_built,
    })
}

/// Render [`DregSummary`] rows as a markdown table.
pub fn format_dreg_table(rows: &[DregSummary]) -> String {
    let mut out = String::from(
        "| n | ℓ | m | vars | eqs | deg | FFD | D_refute | gap | ctrl(shape) | ctrl(unsat) | Dc(shape) | Dc(unsat) | refuted | pinned | unres | D_built |\n\
         |--:|--:|--:|-----:|----:|----:|----:|---------:|----:|------------:|------------:|----------:|----------:|--------:|-------:|------:|--------:|\n",
    );
    let f = |v: Option<f64>| v.map_or("—".to_string(), |x| format!("{x:.2}"));
    // A control that reported no degree is either one that never
    // resolved or one that *could not* resolve because it is
    // satisfiable by construction. Saying which is the whole point.
    let ctrl = |v: Option<f64>, unresolved: usize, satisfiable: bool| match v {
        Some(x) => format!("{x:.2}"),
        None if satisfiable => "n/a(sat)".to_string(),
        None if unresolved > 0 => "unres".to_string(),
        None => "—".to_string(),
    };
    for r in rows {
        out.push_str(&format!(
            "| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {}/{} | {} |\n",
            r.n,
            r.ell,
            r.m,
            r.n_vars,
            r.n_eqs,
            r.degree,
            f(r.fall_mean),
            f(r.refute_mean),
            f(r.gap()),
            ctrl(r.control_solve_mean, r.control_unresolved, r.control_expected_solutions > 1.5),
            ctrl(r.control_unsat_mean, r.control_unsat_unresolved, false),
            r.control_shape_max_degree_built
                .map_or("—".to_string(), |d| d.to_string()),
            r.control_unsat_max_degree_built
                .map_or("—".to_string(), |d| d.to_string()),
            r.refuted,
            r.pinned,
            r.unresolved,
            r.trials,
            r.max_degree_built
                .map_or("—".to_string(), |d| d.to_string()),
        ));
    }
    out
}

// ── Dense vs sparse elimination ────────────────────────────────────

/// Head-to-head measurement of the two elimination paths on one
/// Macaulay matrix.
///
/// The sparse path is an optimisation, so the only question about it is
/// whether it is actually faster — and the honest way to answer that is
/// to time both on the same matrix rather than to argue from the
/// representation.  `max_weight` is reported alongside because fill-in
/// is the failure mode: if elimination densifies the rows, sparse
/// storage buys the early columns and then degrades toward dense
/// behaviour, which shows up as the weight climbing toward `cols`.
#[derive(Clone, Debug)]
pub struct EliminationComparison {
    pub n: u32,
    pub m: usize,
    pub degree: u32,
    pub n_vars: usize,
    pub rows: usize,
    pub cols: usize,
    /// Columns carrying degree-≥2 monomials — the part eliminated
    /// sparsely.
    pub high_cols: usize,
    pub dense_ms: f64,
    pub sparse_ms: f64,
    /// Heaviest row reached during sparse elimination.  Compare against
    /// `cols`: equality means fill-in has won and the rows are dense.
    pub max_weight: usize,
    /// Nonzeros before elimination, as a baseline for `max_weight`.
    pub start_max_weight: usize,
    /// Whether both paths returned the same profile.
    pub agree: bool,
}

impl EliminationComparison {
    /// Sparse time as a fraction of dense; below 1 is a win.
    pub fn ratio(&self) -> f64 {
        if self.sparse_ms == 0.0 {
            f64::INFINITY
        } else {
            self.dense_ms / self.sparse_ms
        }
    }
}

/// Time both elimination paths on the decomposition system for
/// `(n, m)` at one Macaulay degree.
pub fn elimination_comparison(
    n: u32,
    factor_index: usize,
    m: usize,
    degree: u32,
    seed: u64,
) -> Option<EliminationComparison> {
    use crate::cryptanalysis::koblitz_groebner::{
        build_macaulay_sparse, solving_profile, solving_profile_sparse,
    };
    use crate::cryptanalysis::sparse_macaulay::{eliminate_high_columns, low_column_start};

    let (irr, basis) = invariant_subspace_basis(n, factor_index)?;
    let st = FieldStructure::new(n, &irr);
    let b = F2mElement::one(n);
    let mut rng = StdRng::seed_from_u64(seed);
    let x_r = F2mElement::from_biguint(&BigUint::from(rng.gen::<u64>()), n);
    let sys = build_decomposition_system(&basis, &x_r, &b, m, &st)?;

    let (cols, rows) = build_macaulay_sparse(&sys.equations, sys.n_vars, degree)?;
    let high_cols = low_column_start(&cols);
    let start_max_weight = rows.iter().map(|r| r.len()).max().unwrap_or(0);
    let elim = eliminate_high_columns(rows, cols.len(), high_cols);

    let t0 = Instant::now();
    let dense = solving_profile(&sys.equations, sys.n_vars, degree);
    let dense_ms = t0.elapsed().as_secs_f64() * 1e3;

    let t1 = Instant::now();
    let sparse = solving_profile_sparse(&sys.equations, sys.n_vars, degree);
    let sparse_ms = t1.elapsed().as_secs_f64() * 1e3;

    let agree = match (&dense, &sparse) {
        (Some(a), Some(b)) => {
            a.rank == b.rank
                && a.refuted == b.refuted
                && a.vars_determined == b.vars_determined
                && a.resolves() == b.resolves()
        }
        (None, None) => true,
        _ => false,
    };

    Some(EliminationComparison {
        n,
        m,
        degree,
        n_vars: sys.n_vars,
        rows: dense.as_ref().map(|p| p.rows).unwrap_or(0),
        cols: cols.len(),
        high_cols,
        dense_ms,
        sparse_ms,
        max_weight: elim.max_weight,
        start_max_weight,
        agree,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cost_model_matches_the_built_system() {
        // n_vars_for is the number the target drives down, so it had
        // better be the number the builder actually produces.
        for n in [7u32, 9, 15, 21] {
            let (_, basis) = invariant_subspace_basis(n, 0).unwrap();
            for m in [2usize, 3] {
                if let Some(p) = profile_system(n, 0, m, 2, 7) {
                    assert_eq!(
                        p.n_vars,
                        n_vars_for(n, basis.len() as u32, m),
                        "n = {n}, m = {m}"
                    );
                }
            }
        }
    }

    #[test]
    fn profiles_are_deterministic_and_structural() {
        let a = profile_system(9, 0, 2, 3, 42).unwrap();
        let b = profile_system(9, 0, 2, 3, 42).unwrap();
        assert_eq!(a.n_vars, b.n_vars);
        assert_eq!(a.fall_degree, b.fall_degree);
        assert_eq!(
            a.macaulay.iter().map(|p| p.rank).collect::<Vec<_>>(),
            b.macaulay.iter().map(|p| p.rank).collect::<Vec<_>>()
        );
        // K_a / F_2^9: ℓ = 6, so 12 unknowns, 9 equations, quadratic.
        assert_eq!((a.ell, a.n_vars, a.n_eqs, a.degree), (6, 12, 9, 2));
    }

    #[test]
    fn chaining_makes_the_system_cubic_and_much_larger() {
        let two = profile_system(9, 0, 2, 2, 1).unwrap();
        let three = profile_system(9, 0, 3, 2, 1).unwrap();
        assert_eq!(two.degree, 2);
        assert_eq!(three.degree, 3);
        // One intermediate point costs a full n unknowns.
        assert_eq!(three.n_vars - two.n_vars, 6 + 9);
    }

    #[test]
    fn the_budget_is_what_stops_the_sweep() {
        // n = 63, ℓ = 6: m = 2 fits, m = 3 needs 81 > 64 unknowns.
        assert_eq!(n_vars_for(63, 6, 2), 12);
        assert_eq!(n_vars_for(63, 6, 3), 81);
        assert_eq!(max_m_within_budget(63, 6, 64), Some(2));
        assert!(profile_system(63, 0, 3, 2, 1).is_none());
        assert!(profile_system(63, 0, 2, 2, 1).is_some());
    }

    #[test]
    fn the_ladder_is_the_n_with_small_subspaces() {
        let ladder = subspace_ladder(63, 6);
        assert!(ladder.contains(&(7, 3)));
        assert!(ladder.contains(&(15, 4)));
        assert!(ladder.contains(&(31, 5)));
        assert!(ladder.contains(&(63, 6)));
        // ord_11(2) = 10, too big for this cut.
        assert!(!ladder.iter().any(|(n, _)| *n == 11));
    }

    #[test]
    fn all_three_oracles_agree_on_a_benchmarked_instance() {
        let b = bench_instance(0, 9, 0, 2, 6, 0xB0B, 20_000, 64, Some(2)).unwrap();
        assert_eq!(b.disagreements, 0, "oracles disagreed: {b:?}");
        assert_eq!(b.runs.len(), 3);
        for r in &b.runs {
            assert_eq!(
                r.decomposed + r.refuted + r.inconclusive,
                b.targets,
                "{} lost a target",
                r.oracle
            );
        }
        // Every target of K_0/F_2^9 decomposes into 2 factor-base points.
        assert!(b.runs.iter().all(|r| r.decomposed == b.targets));
    }

    #[test]
    fn fall_degree_varies_with_the_target_draw() {
        // The reason the harness averages: one draw is not the system's
        // fall degree, it is one system's fall degree.
        let s = ffd_summary(9, 0, 2, 3, 0x5EED, 16).unwrap();
        assert_eq!(s.trials, 16);
        assert!(
            s.no_fall > 0 || s.fall_min != s.fall_max,
            "expected spread across draws, got {s:?}"
        );
        // …and the summary still describes the same system.
        assert_eq!((s.ell, s.n_vars, s.n_eqs, s.degree), (6, 12, 9, 2));
    }

    #[test]
    fn find_and_refute_costs_are_reported_separately() {
        // The two regimes differ by orders of magnitude, so the harness
        // must not average them into one number.  K_0/F_2^7 refutes
        // every target (its factor base is a single point); K_0/F_2^9
        // decomposes every target.
        let refuting = bench_instance(0, 7, 0, 2, 4, 1, 20_000, 64, Some(2)).unwrap();
        for r in &refuting.runs {
            assert_eq!(r.decomposed, 0);
            assert!(
                r.median_refuted_ms > 0.0,
                "{} has no refute median",
                r.oracle
            );
            assert!(
                r.median_found_ms.is_nan(),
                "{} invented a find median",
                r.oracle
            );
        }
        let finding = bench_instance(0, 9, 0, 2, 4, 1, 20_000, 64, Some(2)).unwrap();
        for r in &finding.runs {
            assert_eq!(r.refuted, 0);
            assert!(r.median_found_ms > 0.0, "{} has no find median", r.oracle);
            assert!(
                r.median_refuted_ms.is_nan(),
                "{} invented a refute median",
                r.oracle
            );
        }
    }

    #[test]
    fn eq_var_ratio_flags_the_underdetermined_systems() {
        // n = 9, m = 3 is the worst measured refutation instance and is
        // the underdetermined one: 18 equations in 27 unknowns.
        let hard = profile_system(9, 0, 3, 2, 1).unwrap();
        assert!(hard.eq_var_ratio() < 1.0, "{}", hard.eq_var_ratio());
        // n = 15, m = 3 has the same variable count but more equations,
        // and refutes ~400x faster.
        let easier = profile_system(15, 0, 3, 2, 1).unwrap();
        assert_eq!(hard.n_vars, easier.n_vars);
        assert!(easier.eq_var_ratio() > 1.0, "{}", easier.eq_var_ratio());
    }

    #[test]
    fn json_round_trips_as_valid_json() {
        let profiles = vec![profile_system(9, 0, 2, 3, 1).unwrap()];
        let benches = vec![bench_instance(0, 9, 0, 2, 2, 1, 20_000, 64, Some(2)).unwrap()];
        let text = to_json(&profiles, &benches);
        let parsed: serde_json::Value = serde_json::from_str(&text).unwrap();
        assert_eq!(parsed["systems"][0]["n_vars"], 12);
        assert_eq!(parsed["oracles"][0]["disagreements"], 0);
    }

    /// The control arms are tracked and reported **separately**.
    ///
    /// Two failures this pins, both found by review on #395 and both
    /// the same class as the ones the module already guards against:
    /// a `control_max_degree_built` that was computed and stored but
    /// never printed, so the sweep still could not tell a control that
    /// exhausted `d_max` from one that hit the size caps; and a single
    /// shared `max()` across both arms, which can report a degree the
    /// infeasible arm never built, because that arm carries
    /// `n_vars + 4` equations and so reaches the row cap at a lower
    /// degree.  The infeasible arm is the one whose non-resolution
    /// carries the attribution, so a field that averages it away is
    /// worse than no field at all.
    #[test]
    fn control_arms_are_reported_separately() {
        // n = 7, m = 2 is six unknowns: cheap enough for a unit test.
        let r = dreg_summary(7, 0, 2, 4, 2, 0x5EED, true).expect("cell builds");

        assert!(
            r.control_shape_max_degree_built.is_some(),
            "the shape-matched arm must record the degree it reached"
        );
        assert!(
            r.control_unsat_max_degree_built.is_some(),
            "so must the infeasible arm, independently"
        );
        assert!(
            r.control_expected_solutions > 0.0,
            "the shape-matched arm's satisfiability must be visible"
        );

        let table = format_dreg_table(std::slice::from_ref(&r));
        for col in ["ctrl(shape)", "ctrl(unsat)", "Dc(shape)", "Dc(unsat)"] {
            assert!(
                table.contains(col),
                "a field that is stored but never printed cannot do its job; \
                 missing {col} in:\n{table}"
            );
        }
    }
}
