//! # `icx` — index calculus across every standardized curve.
//!
//! One command that accepts any standardized elliptic curve by name and, per
//! `docs/ic/ENGINE_AUDIT_AND_DESIGN.md`:
//!
//! - `icx list` — enumerate the catalog (filter by `--family`);
//! - `icx inspect <curve>` — verify the curve's parameters;
//! - `icx estimate <curve>` — the generic-attack cost and the honest IC
//!   picture for this size, with heuristics named;
//! - `icx <curve>` — shorthand for `inspect`.
//!
//! `icx run` (execute the pipeline on an in-envelope curve or a same-family
//! analogue) is layered on top of this in the same crate and lands with the
//! solver wiring; this binary is the catalog-and-estimate front door and never
//! claims to solve what it has not.
//!
//! Every subcommand supports `--json` for a machine-readable report carrying a
//! provenance block (binary hash, git commit, host, dispatched field backend).

use std::process::ExitCode;

use clap::{Args, Parser, Subcommand};
use serde_json::{json, Value};

use crate::cryptanalysis::curve_catalog::{self, CatalogCurve, Family};
use crate::cryptanalysis::ic_engine;

#[derive(Parser)]
#[command(
    name = "icx",
    version,
    about = "Index calculus across every standardized elliptic curve",
    long_about = "Inspect, estimate and (where feasible) run index calculus on \
                  any standardized curve — prime, binary, Koblitz, extension \
                  field, or characteristic three — selected by name. See \
                  `icx list` for the catalog and \
                  docs/ic/ENGINE_AUDIT_AND_DESIGN.md for the honest scope."
)]
pub struct Cli {
    #[command(subcommand)]
    command: Option<Action>,
    /// Shorthand: inspect this curve. Use `icx list` for names.
    #[arg(value_name = "CURVE")]
    curve: Option<String>,
    /// Emit a machine-readable JSON report.
    #[arg(long, global = true)]
    json: bool,
}

#[derive(Subcommand)]
enum Action {
    /// List catalog curves, optionally filtered by field family.
    List(ListArgs),
    /// Verify a curve's parameters (generator on curve, n·G = O, Hasse).
    Inspect(CurveArg),
    /// Report the generic-attack cost and the IC picture for this curve.
    Estimate(EstimateArgs),
    /// Run the index-calculus pipeline on the curve (or a same-family analogue).
    Run(RunArgs),
    /// Solve a quadratic Boolean system with the FES kernel (CPU or GPU worker).
    Fes(FesArgs),
}

#[derive(Args)]
struct FesArgs {
    /// Variables in the generated quadratic system.
    #[arg(long, default_value_t = 18)]
    n: usize,
    /// Equations in the generated quadratic system.
    #[arg(long, default_value_t = 20)]
    m: usize,
    #[arg(long, default_value_t = 1)]
    seed: u64,
    /// Backend: `cpu` (in-process), `gpu` (an external CUDA/Metal/host worker),
    /// or `auto` (a discovered worker if present, else cpu).
    #[arg(long, default_value = "auto")]
    backend: String,
    /// Explicit worker executable (overrides discovery); it must speak the
    /// gpu/fes file contract.
    #[arg(long)]
    worker: Option<String>,
}

#[derive(Args)]
struct RunArgs {
    /// Curve name or alias.
    curve: String,
    /// Factor base plugin: `name` or `name:k=v,...` (default per family).
    #[arg(long)]
    factor_base: Option<String>,
    /// Decomposition oracle (subtract | mitm | mitm-frobenius | descent-algebraic).
    #[arg(long)]
    oracle: Option<String>,
    /// Polynomial solver for descent-algebraic (f4-f2 | matrix-f5 | xl-f2 |
    /// crossbred-f2 | fes-f2 | fes-f2-wide | sat-cdcl | buchberger-f2 | exhaustive).
    #[arg(long)]
    solver: Option<String>,
    /// Relation matrix (incremental-gauss | structured-gauss).
    #[arg(long, default_value = "incremental-gauss")]
    linalg: String,
    /// Analogue field degree for binary/Koblitz families.
    #[arg(long)]
    degree: Option<u32>,
    /// Analogue prime size in bits (7|10|12|14|16|18|20).
    #[arg(long)]
    bits: Option<u32>,
    #[arg(long, default_value_t = 20_260_922)]
    seed: u64,
    #[arg(long, default_value_t = 2_000_000)]
    max_trials: u64,
    #[arg(long, default_value_t = 1)]
    repeats: usize,
    /// Counted Pollard-rho reference runs to average (0 to skip).
    #[arg(long, default_value_t = 8)]
    rho_runs: usize,
    /// End-to-end envelope in subgroup-order bits.
    #[arg(long, default_value_t = ic_engine::ATTACK_ENVELOPE_BITS)]
    envelope: u64,
    /// Per-solver-call budget in seconds (0 for none).
    #[arg(long, default_value_t = 60)]
    solver_budget_seconds: u64,
}

#[derive(Args)]
struct ListArgs {
    /// Restrict to one family: prime | binary | koblitz | extension | char3.
    #[arg(long)]
    family: Option<String>,
}

#[derive(Args)]
struct CurveArg {
    /// Curve name or alias.
    curve: String,
}

#[derive(Args)]
struct EstimateArgs {
    /// Curve name or alias.
    curve: String,
    /// End-to-end envelope in subgroup-order bits (default: demonstrated max).
    #[arg(long, default_value_t = ic_engine::ATTACK_ENVELOPE_BITS)]
    envelope: u64,
}

fn provenance() -> Value {
    json!({
        "version": env!("CARGO_PKG_VERSION"),
        "os": std::env::consts::OS,
        "arch": std::env::consts::ARCH,
        "field_backend": field_backend_label(),
    })
}

/// Which carry-less-multiply backend this build will use at runtime, for the
/// provenance block. (The dispatch itself lands with the field-backend work;
/// this reports what the host supports.)
fn field_backend_label() -> &'static str {
    #[cfg(target_arch = "x86_64")]
    {
        if std::arch::is_x86_feature_detected!("vpclmulqdq") {
            "x86_64:vpclmulqdq"
        } else if std::arch::is_x86_feature_detected!("pclmulqdq") {
            "x86_64:pclmulqdq"
        } else {
            "x86_64:portable"
        }
    }
    #[cfg(target_arch = "aarch64")]
    {
        if std::arch::is_aarch64_feature_detected!("aes") {
            "aarch64:pmull"
        } else {
            "aarch64:portable"
        }
    }
    #[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
    {
        "portable"
    }
}

fn family_of(curve: &CatalogCurve) -> &'static str {
    curve.family.tag()
}

fn list(args: &ListArgs) -> Result<Value, String> {
    let filter = match &args.family {
        Some(f) => Some(Family::parse(f).ok_or_else(|| {
            format!("unknown family '{f}'; use prime|binary|koblitz|extension|char3")
        })?),
        None => None,
    };
    let mut rows = Vec::new();
    for c in curve_catalog::all() {
        if let Some(f) = filter {
            if c.family != f {
                continue;
            }
        }
        let field = c.field();
        let est = ic_engine::estimate(&c, ic_engine::ATTACK_ENVELOPE_BITS);
        rows.push(json!({
            "name": c.name,
            "aliases": c.aliases,
            "family": family_of(&c),
            "standard": c.standard,
            "field": field.label,
            "field_bits": field.bits,
            "order_bits": c.order_bits(),
            "rho_security_bits": round1(c.rho_security_bits()),
            "ic_relevant": est.ic_relevant,
            "regime": est.regime.tag(),
        }));
    }
    Ok(json!({
        "schema_version": 1,
        "operation": "list",
        "status": "complete",
        "count": rows.len(),
        "curves": rows,
    }))
}

fn inspect(name: &str) -> Result<Value, String> {
    let c = curve_catalog::by_name(name)
        .ok_or_else(|| format!("unknown curve '{name}'; try `icx list`"))?;
    let field = c.field();
    let checks = c.verify();
    let all_passed = checks.iter().all(|k| k.passed);
    let checks_json: Vec<Value> = checks
        .iter()
        .map(|k| json!({"name": k.name, "status": if k.passed {"pass"} else {"fail"}, "detail": k.detail}))
        .collect();
    Ok(json!({
        "schema_version": 1,
        "operation": "inspect",
        "status": if all_passed {"checks_passed"} else {"checks_failed"},
        "curve": {
            "name": c.name,
            "aliases": c.aliases,
            "family": family_of(&c),
            "standard": c.standard,
            "field": {"kind": field.kind, "label": field.label, "bits": field.bits},
            "order_bits": c.order_bits(),
            "subgroup_order": c.subgroup_order().to_string(),
            "cofactor": c.cofactor().to_string(),
            "group_order": c.group_order().to_string(),
            "rho_security_bits": round1(c.rho_security_bits()),
        },
        "checks": checks_json,
        "verified": all_passed,
    }))
}

fn estimate(args: &EstimateArgs) -> Result<Value, String> {
    let c = curve_catalog::by_name(&args.curve)
        .ok_or_else(|| format!("unknown curve '{}'; try `icx list`", args.curve))?;
    let est = ic_engine::estimate(&c, args.envelope);
    Ok(json!({
        "schema_version": 1,
        "operation": "estimate",
        "status": "complete",
        "curve": est.curve,
        "family": est.family,
        "field": est.field_label,
        "field_bits": est.field_bits,
        "order_bits": est.order_bits,
        "generic_attack": {
            "algorithm": "pollard-rho",
            "log2_operations": round2(est.rho_log2_ops),
            "security_bits": round1(est.rho_security_bits),
        },
        "index_calculus": {
            "relevant": est.ic_relevant,
            "regime": est.regime.tag(),
        },
        "notes": est.notes,
    }))
}

fn round1(x: f64) -> f64 {
    (x * 10.0).round() / 10.0
}
fn round2(x: f64) -> f64 {
    (x * 100.0).round() / 100.0
}

fn display(report: &Value) {
    match report["operation"].as_str() {
        Some("list") => {
            println!(
                "{:<22} {:<10} {:<9} {:>10} {:>9}  regime",
                "curve", "family", "field", "order_bits", "rho_bits"
            );
            for c in report["curves"].as_array().into_iter().flatten() {
                println!(
                    "{:<22} {:<10} {:<9} {:>10} {:>9}  {}",
                    c["name"].as_str().unwrap_or("?"),
                    c["family"].as_str().unwrap_or("?"),
                    c["field"].as_str().unwrap_or("?"),
                    c["order_bits"].as_u64().unwrap_or(0),
                    format!("{:.1}", c["rho_security_bits"].as_f64().unwrap_or(0.0)),
                    c["regime"].as_str().unwrap_or("?"),
                );
            }
            println!("\n{} curves.", report["count"]);
        }
        Some("inspect") => {
            let cu = &report["curve"];
            println!(
                "Curve: {} [{}]",
                cu["name"].as_str().unwrap_or("?"),
                cu["family"].as_str().unwrap_or("?")
            );
            println!("Standard: {}", cu["standard"].as_str().unwrap_or("?"));
            println!(
                "Field: {} ({} bits); subgroup order {} bits; cofactor {}",
                cu["field"]["label"].as_str().unwrap_or("?"),
                cu["field"]["bits"],
                cu["order_bits"],
                cu["cofactor"].as_str().unwrap_or("?"),
            );
            println!("Generic (rho) security: {} bits", cu["rho_security_bits"]);
            for k in report["checks"].as_array().into_iter().flatten() {
                println!(
                    "  {:<22} {:<5} {}",
                    k["name"].as_str().unwrap_or("?"),
                    k["status"].as_str().unwrap_or("?"),
                    k["detail"].as_str().unwrap_or("")
                );
            }
            println!(
                "Verified: {}",
                if report["verified"] == true {
                    "yes"
                } else {
                    "NO"
                }
            );
        }
        Some("estimate") => {
            println!(
                "Curve: {} [{}]  field {} ({} bits)  order {} bits",
                report["curve"].as_str().unwrap_or("?"),
                report["family"].as_str().unwrap_or("?"),
                report["field"].as_str().unwrap_or("?"),
                report["field_bits"],
                report["order_bits"],
            );
            let ga = &report["generic_attack"];
            println!(
                "Generic attack (rho): ~2^{} operations, {} security bits",
                ga["log2_operations"], ga["security_bits"]
            );
            println!(
                "Index calculus: relevant={}  regime={}",
                report["index_calculus"]["relevant"],
                report["index_calculus"]["regime"].as_str().unwrap_or("?"),
            );
            for n in report["notes"].as_array().into_iter().flatten() {
                println!("  - {}", n.as_str().unwrap_or(""));
            }
        }
        Some("run") => {
            let r = &report["result"];
            let an = &r["analogue"];
            println!(
                "Run: {} [{}]  regime={}  ic_relevant={}",
                r["curve"].as_str().unwrap_or("?"),
                an["family"].as_str().unwrap_or("?"),
                r["regime"].as_str().unwrap_or("?"),
                r["ic_relevant"],
            );
            println!(
                "Instance run: {} (order {} bits){}",
                an["instance"].as_str().unwrap_or("?"),
                an["run_order_bits"],
                if an["is_named_curve"] == true {
                    " — the named curve"
                } else {
                    " — scaled analogue"
                },
            );
            println!("Config: {}", r["config_label"].as_str().unwrap_or("?"));
            for (i, rep) in r["reports"].as_array().into_iter().flatten().enumerate() {
                let s = rep["s"].as_f64().unwrap_or(0.0);
                let sr = rep.get("s_over_rho").and_then(|v| v.as_f64());
                println!(
                    "  config {}: verified={}  S={:.3e}{}",
                    i + 1,
                    rep["verified"],
                    s,
                    sr.map(|x| format!("  ({x:.2}x rho)")).unwrap_or_default(),
                );
            }
            if let Some(rho) = r.get("rho").filter(|v| !v.is_null()) {
                println!(
                    "Rho reference: {} runs, mean S={:.3e}, all verified={}",
                    rho["runs"],
                    rho["mean_s"].as_f64().unwrap_or(0.0),
                    rho["all_verified"],
                );
            }
            if let Some(note) = r["extrapolation_note"].as_str() {
                println!("\nScope: {note}");
            }
        }
        Some("fes") => {
            let sy = &report["system"];
            println!(
                "FES: {}-var, {}-eq quadratic system (seed {})",
                sy["n"], sy["m"], sy["seed"]
            );
            println!("Backend: {}", report["backend"].as_str().unwrap_or("?"));
            println!(
                "Solutions: {} verified of {} proposed",
                report["verified"], report["proposed"]
            );
            println!(
                "Planted solution {}: {}",
                report["planted"],
                if report["planted_found"] == true {
                    "found"
                } else {
                    "NOT found"
                }
            );
        }
        Some("error") => {
            eprintln!("icx: {}", report["message"].as_str().unwrap_or("failed"));
        }
        _ => {
            println!("{}", serde_json::to_string_pretty(report).unwrap());
        }
    }
}

fn run_cmd(args: &RunArgs, json: bool) -> Result<Value, String> {
    use crate::cryptanalysis::ic_progress::ProgressReporter;
    use crate::cryptanalysis::ic_run::{run_curve, RunConfig};

    let curve = curve_catalog::by_name(&args.curve)
        .ok_or_else(|| format!("unknown curve '{}'; try `icx list`", args.curve))?;
    let cfg = RunConfig {
        factor_base: args.factor_base.clone(),
        oracle: args.oracle.clone(),
        solver: args.solver.clone(),
        linalg: args.linalg.clone(),
        degree: args.degree,
        bits: args.bits,
        seed: args.seed,
        max_trials: args.max_trials,
        repeats: args.repeats,
        rho_runs: args.rho_runs,
        envelope_bits: args.envelope,
        solver_budget_seconds: args.solver_budget_seconds,
    };
    // In JSON mode the progress log would interleave with the document, so
    // silence it; in human mode it streams the CADO-style stage lines to stderr.
    let mut progress = ProgressReporter::new(false, json);
    let result = run_curve(&curve, &cfg, &mut progress)?;
    let verified_any = result.reports.iter().any(|r| r.verified);
    if !json {
        progress.summary(&format!(
            "{} — {} of {} configuration(s) verified",
            result.curve,
            result.reports.iter().filter(|r| r.verified).count(),
            result.reports.len()
        ));
    }
    Ok(json!({
        "schema_version": 1,
        "operation": "run",
        "status": if verified_any { "complete" } else { "incomplete" },
        "verified": verified_any,
        "result": serde_json::to_value(&result).map_err(|e| e.to_string())?,
    }))
}

fn fes_cmd(args: &FesArgs) -> Result<Value, String> {
    use crate::cryptanalysis::fes_gpu::{self, FesBackend};

    let (sys, planted) = fes_gpu::random_system(args.n, args.m, args.seed);
    let backend = match (args.worker.as_deref(), args.backend.as_str()) {
        (Some(path), _) => FesBackend::Worker(std::path::PathBuf::from(path)),
        (None, "cpu") => FesBackend::Cpu,
        (None, "auto") => FesBackend::Auto,
        (None, "gpu") => match fes_gpu::discover_worker() {
            Some(w) => FesBackend::Worker(w),
            None => {
                return Err(
                    "no FES worker found; build one with `make -C gpu/fes host-worker` \
                            (or cuda / metal-worker) or set ICX_FES_WORKER, or use --backend cpu"
                        .into(),
                )
            }
        },
        (None, other) => return Err(format!("unknown backend '{other}'; use cpu|gpu|auto")),
    };
    let res = fes_gpu::solve(&sys, &backend)?;
    let planted_found = res.solutions.contains(&planted);
    Ok(json!({
        "schema_version": 1,
        "operation": "fes",
        "status": "complete",
        "system": {"n": args.n, "m": args.m, "seed": args.seed},
        "backend": res.backend,
        "proposed": res.proposed,
        "verified": res.verified,
        "solutions": res.solutions.len(),
        "planted": planted,
        "planted_found": planted_found,
    }))
}

fn execute(cli: &Cli) -> Result<Value, String> {
    match &cli.command {
        Some(Action::List(a)) => list(a),
        Some(Action::Inspect(a)) => inspect(&a.curve),
        Some(Action::Estimate(a)) => estimate(a),
        Some(Action::Run(a)) => run_cmd(a, cli.json),
        Some(Action::Fes(a)) => fes_cmd(a),
        None => {
            let name = cli
                .curve
                .as_deref()
                .ok_or("supply a curve name or a subcommand; see `icx --help`")?;
            inspect(name)
        }
    }
}

/// Run the `ca-icx` command line on `args` (the first item is the program
/// name, as in `std::env::args_os`).
pub fn run_from<I, T>(args: I) -> ExitCode
where
    I: IntoIterator<Item = T>,
    T: Into<std::ffi::OsString> + Clone,
{
    let cli = Cli::parse_from(args);
    let mut report = match execute(&cli) {
        Ok(v) => v,
        Err(message) => json!({
            "schema_version": 1, "operation": "error", "status": "error", "message": message
        }),
    };
    if report.get("operation").is_some() {
        report["software"] = provenance();
    }
    let ok = matches!(
        report["status"].as_str(),
        Some("complete" | "checks_passed")
    );
    if cli.json {
        println!("{}", serde_json::to_string_pretty(&report).unwrap());
    } else {
        display(&report);
    }
    if ok {
        ExitCode::SUCCESS
    } else {
        ExitCode::FAILURE
    }
}
