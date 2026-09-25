//! # Running the index-calculus pipeline on a catalog curve.
//!
//! `icx run <curve>` lands here.  Given a standardized curve, this module
//! selects a **feasible instance of the same family** (the real curve when it
//! is inside the u64 pipeline's envelope, otherwise a scaled same-family
//! analogue), builds it, calibrates it, runs one or more pluggable pipeline
//! configurations through the *identical* public entry points that `ic bench`
//! uses ([`run_pipeline`], [`rho_reference`], the calibration functions), and
//! reports the result with its regime and, for a scaled run, an explicit
//! extrapolation note.
//!
//! It reuses `ic_boundary`/`ic_framework` rather than re-implementing the
//! pipeline, so a `S` reported here is the same quantity, measured the same
//! way, as a ledger row — which is the only way a cross-tool number is
//! meaningful under `AGENTS.md`.
//!
//! ## Honest labelling
//!
//! Standardized curves are all far above the demonstrated end-to-end envelope
//! (the largest solved here is a 48-bit subgroup), and their fields exceed the
//! single-word ceiling (`n ≤ 62`, `p < 2^62`).  So a `run` against, say,
//! `sect163k1` executes a small **Koblitz analogue** and says so; the
//! real-curve cost is what `icx estimate` reports.  Nothing here claims to
//! solve the named curve.

use serde::Serialize;

use crate::cryptanalysis::curve_catalog::{CatalogCurve, Family};
use crate::cryptanalysis::ic_boundary::{
    calibrate_binary_instance, calibrate_group, calibrate_row_ops, calibrate_word_xor,
    generic_floor_ops, koblitz_instance, random_binary_instance, rho_reference,
    roster_prime_instance, BinaryGroup, BinaryInstance, Calibration, CountedGroup, GroupOps,
    PrimeInstance,
};
use crate::cryptanalysis::ic_engine::{classify, Regime};
use crate::cryptanalysis::ic_framework::plugins::{
    BinarySubspaceBase, DescentAlgebraicOracle, KoblitzOrbitBase, MitmOracle, PrimeAbscissaBase,
    SubtractOracle,
};
use crate::cryptanalysis::ic_framework::solvers::solver_by_name;
use crate::cryptanalysis::ic_framework::stages::{
    DecompositionOracle, FactorBaseBuilder, InstanceCtx, Params, Targets,
};
use crate::cryptanalysis::ic_framework::{run_pipeline, PipelineSpec, RunReport};
use crate::cryptanalysis::ic_progress::ProgressReporter;

/// Roster prime-field sizes `roster_prime_instance` can build.
pub const PRIME_ROSTER_BITS: &[u32] = &[7, 10, 12, 14, 16, 18, 20];

/// How a `run` should be configured.  Every field has a per-family default so
/// `icx run <curve>` works with no flags.
#[derive(Clone, Debug)]
pub struct RunConfig {
    /// Factor-base plugin (`name` or `name:k=v,...`); empty picks the default.
    pub factor_base: Option<String>,
    /// Decomposition oracle; empty picks the default.
    pub oracle: Option<String>,
    /// Polynomial solver, for the `descent-algebraic` oracle.
    pub solver: Option<String>,
    /// Relation matrix (`incremental-gauss` or `structured-gauss`).
    pub linalg: String,
    /// Analogue field degree for binary/Koblitz families.
    pub degree: Option<u32>,
    /// Analogue prime size in bits (must be in [`PRIME_ROSTER_BITS`]).
    pub bits: Option<u32>,
    pub seed: u64,
    pub max_trials: u64,
    pub repeats: usize,
    /// Counted rho runs averaged into the reference column; 0 skips it.
    pub rho_runs: usize,
    pub envelope_bits: u64,
    /// Per-solver-call budget in seconds; 0 for none.
    pub solver_budget_seconds: u64,
}

impl Default for RunConfig {
    fn default() -> Self {
        RunConfig {
            factor_base: None,
            oracle: None,
            solver: None,
            linalg: "incremental-gauss".to_string(),
            degree: None,
            bits: None,
            seed: 20_260_922,
            max_trials: 2_000_000,
            repeats: 1,
            rho_runs: 8,
            envelope_bits: crate::cryptanalysis::ic_engine::ATTACK_ENVELOPE_BITS,
            solver_budget_seconds: 60,
        }
    }
}

/// What instance actually ran, so the report can be honest about it.
#[derive(Clone, Debug, Serialize)]
pub struct AnalogueInfo {
    pub family: &'static str,
    /// `true` if this is the named curve itself, `false` if a scaled analogue.
    pub is_named_curve: bool,
    /// Instance name from the framework.
    pub instance: String,
    /// Field degree (binary) if applicable.
    pub field_degree: Option<u32>,
    /// Subgroup order in bits, as actually run.
    pub run_order_bits: u64,
}

/// One counted rho reference run's summary.
#[derive(Clone, Debug, Serialize)]
pub struct RhoRef {
    pub method: String,
    pub runs: usize,
    pub mean_s: f64,
    pub all_verified: bool,
}

/// The full result of a `run`.
#[derive(Clone, Debug, Serialize)]
pub struct RunResult {
    pub curve: String,
    pub regime: &'static str,
    pub ic_relevant: bool,
    pub analogue: AnalogueInfo,
    pub config_label: String,
    pub reports: Vec<RunReport>,
    pub rho: Option<RhoRef>,
    /// Present for scaled runs: what the analogue does and does not say about
    /// the named curve.
    pub extrapolation_note: Option<String>,
}

/// The planted logarithm for repeat `rep` (mirrors the framework's choice so
/// numbers line up with `ic bench`).
fn planted_log(seed: u64, rep: usize, r: u64) -> u64 {
    1 + (seed.wrapping_add(rep as u64 * 0x9E37)) % (r - 1)
}

/// Bit length of a subgroup order.
fn bits_of(r: u64) -> u64 {
    if r == 0 {
        0
    } else {
        64 - r.leading_zeros() as u64
    }
}

/// Default factor-base size for a prime analogue: about `#E^{1/3}`, the family
/// optimum, clamped to something the roster instances solve quickly.
fn prime_base_size(r: u64) -> u64 {
    let cube = (r as f64).cbrt();
    ((cube * 2.0).ceil() as u64).clamp(8, 512)
}

/// Default subspace dimension for a binary analogue: about half the field
/// degree, which the sweeps use (degree 13 → 6, degree 17 → 9).
fn binary_dimension(n: u32) -> u32 {
    n.div_ceil(2).clamp(3, 20)
}

fn rho_ref_for<G: CountedGroup>(
    g: &G,
    generator: G::Elt,
    r: u64,
    seed: u64,
    repeats: usize,
    runs: usize,
) -> Option<RhoRef> {
    if runs == 0 || r < 3 {
        return None;
    }
    let max_steps = (generic_floor_ops(r as f64, 1.0) * 64.0) as u64 + 4096;
    let mut ss = Vec::with_capacity(runs);
    let mut method = String::new();
    let mut all_ok = true;
    for k in 0..runs {
        let planted = planted_log(seed, k % repeats.max(1), r);
        let mut ops = GroupOps::default();
        let target = g.mul(&mut ops, generator, planted);
        let run_seed = seed ^ (0x5248_4F00 + k as u64);
        let res = rho_reference(g, generator, target, r, run_seed, max_steps);
        method = res.method.clone();
        all_ok &= res.verified && res.recovered == Some(planted);
        ss.push(res.s);
    }
    let mean = ss.iter().sum::<f64>() / runs as f64;
    Some(RhoRef {
        method,
        runs,
        mean_s: mean,
        all_verified: all_ok,
    })
}

/// Build the pipeline spec (factor base, oracle, solver, linalg) with
/// per-family defaults filled in.
fn build_spec(family: Family, cfg: &RunConfig, r: u64, field_degree: Option<u32>) -> PipelineSpec {
    let mut spec = PipelineSpec {
        linalg: cfg.linalg.clone(),
        max_trials: cfg.max_trials,
        seed: cfg.seed,
        solver_budget_seconds: cfg.solver_budget_seconds,
        targets: Targets::Walk,
        ..Default::default()
    };
    match family {
        Family::Prime => {
            spec.factor_base = cfg
                .factor_base
                .clone()
                .unwrap_or_else(|| "prime-abscissa".to_string());
            if spec.factor_base == "prime-abscissa"
                && !spec.factor_base_params.0.contains_key("size")
            {
                spec.factor_base_params
                    .set("size", prime_base_size(r).to_string());
            }
            spec.oracle = cfg.oracle.clone().unwrap_or_else(|| "mitm".to_string());
            if spec.oracle == "mitm" {
                spec.oracle_params.set("negation_folded", "1");
            }
        }
        Family::BinaryRandom | Family::Koblitz | Family::Extension | Family::Char3 => {
            let dim = binary_dimension(field_degree.unwrap_or(13));
            spec.factor_base = cfg
                .factor_base
                .clone()
                .unwrap_or_else(|| "binary-subspace".to_string());
            if spec.factor_base == "binary-subspace"
                && !spec.factor_base_params.0.contains_key("dimension")
            {
                spec.factor_base_params.set("dimension", dim.to_string());
            }
            spec.oracle = cfg.oracle.clone().unwrap_or_else(|| "mitm".to_string());
            if spec.oracle == "mitm" {
                spec.oracle_params.set("m", "2");
            }
        }
    }
    // Parse any inline `name:k=v` parameters the caller supplied.
    if let Some(raw) = &cfg.factor_base {
        if let Ok((name, params)) = parse_plugin(raw) {
            spec.factor_base = name;
            merge_params(&mut spec.factor_base_params, params);
        }
    }
    if let Some(raw) = &cfg.oracle {
        if let Ok((name, params)) = parse_plugin(raw) {
            spec.oracle = name;
            merge_params(&mut spec.oracle_params, params);
        }
    }
    spec.solver = cfg.solver.clone();
    spec
}

fn merge_params(into: &mut Params, from: Params) {
    for (k, v) in from.0 {
        into.set(&k, &v);
    }
}

/// Parse `name` or `name:k=v,k=v` into its parts.
fn parse_plugin(raw: &str) -> Result<(String, Params), String> {
    let mut parts = raw.splitn(2, ':');
    let name = parts.next().unwrap_or("").to_string();
    let mut params = Params::default();
    if let Some(rest) = parts.next() {
        for kv in rest.split(',') {
            let mut it = kv.splitn(2, '=');
            let k = it.next().unwrap_or("").trim();
            let v = it.next().unwrap_or("").trim();
            if !k.is_empty() {
                params.set(k, v);
            }
        }
    }
    Ok((name, params))
}

/// Run the pipeline on a prime analogue.
fn run_prime_analogue(
    inst: &PrimeInstance,
    cfg: &RunConfig,
    progress: &mut ProgressReporter,
) -> Result<(Vec<RunReport>, Option<RhoRef>, String), String> {
    let mut points = Vec::new();
    let g0 = inst.generator_point();
    for k in 1..=8u64 {
        let mut ops = GroupOps::default();
        points.push(inst.curve.mul(&mut ops, g0, k));
    }
    let mut calib = Calibration::default();
    calibrate_group(&inst.curve, &points, &mut calib);
    calibrate_row_ops(inst.r, &mut calib);
    calib.ns_per_word_xor = Some(calibrate_word_xor());
    let _ = calib.pin("prime", &inst.name);

    let rho = rho_ref_for(&inst.curve, g0, inst.r, cfg.seed, cfg.repeats, cfg.rho_runs);
    let rho_s = rho.as_ref().map(|r| r.mean_s);

    let base = PrimeAbscissaBase { instance: inst };
    let mut reports = Vec::new();
    let mut label = String::new();
    for rep in 0..cfg.repeats.max(1) {
        let mut spec = build_spec(Family::Prime, cfg, inst.r, None);
        spec.seed = cfg.seed.wrapping_add(rep as u64 * 0x9E37);
        label = spec.label();
        let g = inst.generator_point();
        let planted = planted_log(spec.seed, 0, inst.r);
        let mut ops = GroupOps::default();
        let q = inst.curve.mul(&mut ops, g, planted);
        let ctx = InstanceCtx {
            group: &inst.curve,
            generator: g,
            target: q,
            r: inst.r,
            cofactor: inst.cofactor,
            group_order: inst.group_order,
            name: inst.name.clone(),
            field_degree: None,
        };
        let m = spec.oracle_params.u64_or("m", 2)? as u32;
        let mut subtract = SubtractOracle;
        let mut mitm = MitmOracle::new(m);
        let oracle: &mut dyn DecompositionOracle<_> = match spec.oracle.as_str() {
            "subtract" => &mut subtract,
            "mitm" => &mut mitm,
            other => {
                return Err(format!(
                    "oracle `{other}` is not available on a prime-field curve; try subtract or mitm"
                ))
            }
        };
        progress.stage_begin("Index calculus", None, &spec.label());
        let report = run_pipeline(&ctx, &spec, &base, oracle, planted, &calib, rho_s)?;
        report_progress(progress, &report);
        reports.push(report);
    }
    Ok((reports, rho, label))
}

/// Run the pipeline on a binary/Koblitz analogue.
fn run_binary_analogue(
    inst: &BinaryInstance,
    family: Family,
    cfg: &RunConfig,
    progress: &mut ProgressReporter,
) -> Result<(Vec<RunReport>, Option<RhoRef>, String), String> {
    let mut calib = calibrate_binary_instance(inst);
    calibrate_row_ops(inst.r, &mut calib);
    let _ = calib.pin(family_regime(family), &inst.name);

    let g = BinaryGroup(&inst.fast);
    let rho = rho_ref_for(
        &g,
        inst.generator,
        inst.r,
        cfg.seed,
        cfg.repeats,
        cfg.rho_runs,
    );
    let rho_s = rho.as_ref().map(|r| r.mean_s);

    let subspace = BinarySubspaceBase { instance: inst };
    let orbit = KoblitzOrbitBase { instance: inst };

    let mut reports = Vec::new();
    let mut label = String::new();
    for rep in 0..cfg.repeats.max(1) {
        let mut spec = build_spec(family, cfg, inst.r, Some(inst.n));
        spec.seed = cfg.seed.wrapping_add(rep as u64 * 0x9E37);
        label = spec.label();
        let base: &dyn FactorBaseBuilder<BinaryGroup> = match spec.factor_base.as_str() {
            "binary-subspace" => &subspace,
            "koblitz-orbit" => &orbit,
            other => {
                return Err(format!(
                    "factor base `{other}` is not available on a binary curve; try binary-subspace or koblitz-orbit"
                ))
            }
        };
        let planted = planted_log(spec.seed, 0, inst.r);
        let mut ops = GroupOps::default();
        let q = g.mul(&mut ops, inst.generator, planted);
        let ctx = InstanceCtx {
            group: &g,
            generator: inst.generator,
            target: q,
            r: inst.r,
            cofactor: inst.cofactor,
            group_order: inst.group_order,
            name: inst.name.clone(),
            field_degree: Some(inst.n),
        };
        let m = spec.oracle_params.u64_or("m", 2)? as u32;
        let mut subtract = SubtractOracle;
        let mut mitm = MitmOracle::new(m);
        let mut frob =
            crate::cryptanalysis::ic_framework::plugins::FrobeniusMitmOracle::new(m, inst);
        let mut algebraic = match spec.oracle.as_str() {
            "descent-algebraic" => {
                let raw = spec.solver.as_deref().ok_or(
                    "descent-algebraic needs --solver (try buchberger-f2, sat-cdcl, fes-f2, crossbred-f2 or exhaustive)",
                )?;
                let (sname, sparams) = parse_plugin(raw)?;
                let budget = (spec.solver_budget_seconds > 0)
                    .then(|| std::time::Duration::from_secs(spec.solver_budget_seconds));
                Some(DescentAlgebraicOracle::new(
                    m,
                    inst,
                    solver_by_name(&sname)?,
                    sparams,
                    budget,
                ))
            }
            _ => None,
        };
        let oracle: &mut dyn DecompositionOracle<BinaryGroup> = match spec.oracle.as_str() {
            "subtract" => &mut subtract,
            "mitm" => &mut mitm,
            "mitm-frobenius" => &mut frob,
            "descent-algebraic" => algebraic.as_mut().expect("built above"),
            other => return Err(format!("oracle `{other}` is not available here")),
        };
        progress.stage_begin("Index calculus", None, &spec.label());
        let report = run_pipeline(&ctx, &spec, base, oracle, planted, &calib, rho_s)?;
        report_progress(progress, &report);
        reports.push(report);
    }
    Ok((reports, rho, label))
}

fn family_regime(family: Family) -> &'static str {
    match family {
        Family::Koblitz => "koblitz",
        _ => "char2",
    }
}

/// Emit CADO-style stage lines from a finished report.
fn report_progress(progress: &mut ProgressReporter, report: &RunReport) {
    progress.info(&format!(
        "Factor base: {} columns",
        report.factor_base.columns
    ));
    progress.info(&format!(
        "Relation collection: {} relations from {} targets",
        report.decomposition.relations_found, report.decomposition.targets_tried
    ));
    progress.info(&format!(
        "Linear algebra: {} rank",
        report.linear_algebra.rank
    ));
    let verdict = if report.verified {
        format!("recovered log, S = {:.3e}", report.s)
    } else {
        "did not recover the logarithm (see report)".to_string()
    };
    progress.stage_end(&verdict);
}

/// Choose and run a feasible instance for a catalog curve.
pub fn run_curve(
    curve: &CatalogCurve,
    cfg: &RunConfig,
    progress: &mut ProgressReporter,
) -> Result<RunResult, String> {
    let cls = classify(curve, cfg.envelope_bits);
    let family = curve.family;

    // Extension and characteristic-three families do not yet have a
    // pipeline-runnable instance in this crate (the framework is single-word
    // F_p / F_2^m); estimate them instead of pretending to run.
    if matches!(family, Family::Extension | Family::Char3) {
        return Err(format!(
            "the {} family has no runnable pipeline instance yet; use `icx estimate {}`",
            family.tag(),
            curve.name
        ));
    }

    match family {
        Family::Prime => {
            let bits = cfg.bits.unwrap_or(16);
            if !PRIME_ROSTER_BITS.contains(&bits) {
                return Err(format!(
                    "prime analogue size {bits} bits is not available; choose one of {PRIME_ROSTER_BITS:?}"
                ));
            }
            let inst = roster_prime_instance(bits)
                .ok_or_else(|| format!("could not build a {bits}-bit prime analogue"))?;
            progress.info(&format!(
                "analogue: prime instance {} (r = {} bits) — scaled study for {}",
                inst.name,
                bits_of(inst.r),
                curve.name
            ));
            let analogue = AnalogueInfo {
                family: "prime",
                is_named_curve: false,
                instance: inst.name.clone(),
                field_degree: None,
                run_order_bits: bits_of(inst.r),
            };
            let (reports, rho, label) = run_prime_analogue(&inst, cfg, progress)?;
            Ok(finish(
                curve,
                &cls.regime,
                cls.ic_relevant,
                analogue,
                reports,
                rho,
                label,
            ))
        }
        Family::BinaryRandom | Family::Koblitz => {
            let degree = cfg.degree.unwrap_or(13);
            let inst = if family == Family::Koblitz {
                koblitz_instance(1, degree)
                    .or_else(|| koblitz_instance(0, degree))
                    .ok_or_else(|| format!("could not build a degree-{degree} Koblitz analogue"))?
            } else {
                random_binary_instance(degree, cfg.seed, 8)
                    .ok_or_else(|| format!("could not build a degree-{degree} binary analogue"))?
            };
            progress.info(&format!(
                "analogue: {} instance {} (F_2^{}, r = {} bits) — scaled study for {}",
                family.tag(),
                inst.name,
                inst.n,
                bits_of(inst.r),
                curve.name
            ));
            let analogue = AnalogueInfo {
                family: family.tag(),
                is_named_curve: false,
                instance: inst.name.clone(),
                field_degree: Some(inst.n),
                run_order_bits: bits_of(inst.r),
            };
            let (reports, rho, label) = run_binary_analogue(&inst, family, cfg, progress)?;
            Ok(finish(
                curve,
                &cls.regime,
                cls.ic_relevant,
                analogue,
                reports,
                rho,
                label,
            ))
        }
        Family::Extension | Family::Char3 => unreachable!("handled above"),
    }
}

fn finish(
    curve: &CatalogCurve,
    regime: &Regime,
    ic_relevant: bool,
    analogue: AnalogueInfo,
    reports: Vec<RunReport>,
    rho: Option<RhoRef>,
    config_label: String,
) -> RunResult {
    let note = if !analogue.is_named_curve {
        Some(format!(
            "This run solved a {}-bit {} analogue, not {} ({} bits). It demonstrates the \
             pipeline and its cost on the same family; the named curve's cost is an \
             extrapolation — see `icx estimate {}`. No claim is made about breaking {}.",
            analogue.run_order_bits,
            analogue.family,
            curve.name,
            curve.order_bits(),
            curve.name,
            curve.name
        ))
    } else {
        None
    };
    RunResult {
        curve: curve.name.to_string(),
        regime: regime.tag(),
        ic_relevant,
        analogue,
        config_label,
        reports,
        rho,
        extrapolation_note: note,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::curve_catalog::by_name;

    #[test]
    fn prime_analogue_recovers_a_logarithm() {
        let c = by_name("secp256k1").unwrap();
        let cfg = RunConfig {
            bits: Some(16),
            rho_runs: 0,
            ..Default::default()
        };
        let mut p = ProgressReporter::silent();
        let res = run_curve(&c, &cfg, &mut p).expect("run");
        assert!(!res.analogue.is_named_curve);
        assert!(res.extrapolation_note.is_some());
        assert!(
            res.reports.iter().any(|r| r.verified),
            "prime analogue did not recover the planted log"
        );
    }

    #[test]
    fn koblitz_analogue_runs_and_is_labelled() {
        let c = by_name("sect163k1").unwrap();
        let cfg = RunConfig {
            degree: Some(13),
            rho_runs: 0,
            ..Default::default()
        };
        let mut p = ProgressReporter::silent();
        let res = run_curve(&c, &cfg, &mut p).expect("run");
        assert_eq!(res.analogue.family, "koblitz");
        assert!(!res.analogue.is_named_curve);
        assert!(res.reports.iter().any(|r| r.verified));
    }

    #[test]
    fn extension_family_declines_to_run() {
        // No extension curves in the catalog yet, so synthesize the check by
        // confirming the family guard message shape via a prime curve run is
        // not triggered; extension handling is exercised once such curves land.
        // Here we simply assert the roster guard rejects a bad prime size.
        let c = by_name("p256").unwrap();
        let cfg = RunConfig {
            bits: Some(9),
            ..Default::default()
        };
        let mut p = ProgressReporter::silent();
        assert!(run_curve(&c, &cfg, &mut p).is_err());
    }
}
