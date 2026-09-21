//! Research CLI: read-only curve inspection and bounded known-answer experiments.
#[path = "ic/experiment.rs"]
mod experiment;
#[path = "ic/fixed.rs"]
mod fixed;
#[path = "ic/params.rs"]
mod params;
#[path = "ic/workflow.rs"]
mod workflow;

use clap::{Args, Parser, Subcommand};
use serde_json::{json, Value};
use std::{
    fs::{File, OpenOptions},
    io::{Read, Write},
    path::PathBuf,
    process::ExitCode,
};

#[derive(Parser)]
#[command(
    name = "ic",
    version,
    about = "Curve inspection and synthetic index-calculus research"
)]
#[command(
    long_about = "Inspect named/custom curves, generate reproducible known-answer fixtures, run the toy index-calculus pipeline, compare factor-base candidates, or search for high-yield factor bases. Bare ic runs the default synthetic example. A bare curve name (for example ic ecc2k-130) performs inspection only. The fixed subcommand accepts explicit K_0 parameters and points with full-width coordinates."
)]
struct Cli {
    #[command(subcommand)]
    command: Option<Action>,
    /// Shorthand for inspecting a named curve; use ic list for names.
    #[arg(value_name = "CURVE")]
    profile: Option<String>,
    #[command(flatten)]
    run: experiment::RunArgs,
    /// Print a machine-readable JSON report, without progress text.
    #[arg(long, global = true)]
    json: bool,
    /// Write the JSON report to a new file; existing files are never overwritten.
    #[arg(long, global = true)]
    out: Option<PathBuf>,
}
#[derive(Subcommand)]
enum Action {
    /// List built-in inspection profiles.
    List,
    /// Validate mathematical parameters; never solve an imported target.
    Inspect(InspectArgs),
    /// Run the pipeline on an internally generated known-answer instance.
    Run(experiment::RunArgs),
    /// Generate a reproducible parameter JSON with a random known-answer point.
    Generate(experiment::GenerateArgs),
    /// Compare bounded factor-base candidates using training and holdout fixtures.
    Compare(experiment::CompareArgs),
    /// Search divisor, union and pruned factor bases by exact relation yield, then validate.
    Search(experiment::SearchArgs),
    /// Precompute the factor-base logarithm database once for a curve.
    Logs(experiment::LogsArgs),
    /// Recover a target's logarithm by descent, reusing a saved database.
    Solve(experiment::SolveArgs),
    /// Run or resume a staged select → collect → logs → solve pipeline from a parameter file (or act as a collection worker).
    Workflow(workflow::WorkflowArgs),
    /// Persist and resume index calculus on fixed K_0 parameters through degree 131.
    Fixed(fixed::FixedArgs),
}
#[derive(Args)]
#[group(required = true, multiple = false)]
struct InspectArgs {
    #[arg(long)]
    curve: Option<String>,
    #[arg(long)]
    file: Option<PathBuf>,
}
fn inspect(args: InspectArgs) -> Result<Value, String> {
    if let Some(name) = args.curve {
        let p = params::named(&name)?;
        params::inspect(
            p,
            format!("builtin:{name}; local repository parameter definitions"),
        )
    } else {
        let path = args.file.ok_or("supply --curve or --file")?;
        let (p, hash) = params::load(&path)?;
        params::inspect(p, format!("file BLAKE3:{hash}"))
    }
}
fn execute(cli: &Cli) -> Result<Value, String> {
    if cli.command.is_some() && cli.profile.is_some() {
        return Err("a curve-name shortcut cannot be combined with a subcommand".into());
    }
    if (cli.command.is_some() || cli.profile.is_some()) && cli.run != experiment::RunArgs::default()
    {
        return Err("root-level experiment options apply only to the default run; put run/compare options after their subcommand".into());
    }
    match &cli.command {
        Some(Action::List) => Ok(
            json!({"schema_version":1,"operation":"list","status":"complete","curves":params::NAMES}),
        ),
        Some(Action::Inspect(args)) => inspect(InspectArgs {
            curve: args.curve.clone(),
            file: args.file.clone(),
        }),
        Some(Action::Generate(args)) => experiment::generate(args.clone()),
        Some(Action::Compare(args)) => experiment::compare(args.clone(), cli.json),
        Some(Action::Search(args)) => experiment::search(args.clone(), cli.json),
        Some(Action::Logs(args)) => experiment::logs(args.clone(), cli.json),
        Some(Action::Solve(args)) => experiment::solve(args.clone(), cli.json),
        Some(Action::Workflow(args)) => workflow::run(args.clone(), cli.json),
        Some(Action::Fixed(args)) => fixed::run(args.clone()),
        Some(Action::Run(args)) => experiment::run(args.clone(), cli.json),
        None => {
            if let Some(name) = &cli.profile {
                inspect(InspectArgs {
                    curve: Some(name.clone()),
                    file: None,
                })
            } else {
                experiment::run(cli.run.clone(), cli.json)
            }
        }
    }
}
fn binary_hash() -> Option<String> {
    let mut file = File::open(std::env::current_exe().ok()?).ok()?;
    let mut hasher = blake3::Hasher::new();
    let mut buffer = [0u8; 65536];
    loop {
        let n = file.read(&mut buffer).ok()?;
        if n == 0 {
            break;
        }
        hasher.update(&buffer[..n]);
    }
    Some(hasher.finalize().to_hex().to_string())
}
/// One line for the `linear_algebra` object of a logs report.
fn linear_algebra_summary(la: &Value) -> String {
    let mut line = format!(
        "{} ({} attempts, {:.3}s)",
        la["mode"].as_str().unwrap_or("?"),
        la["attempts"],
        la["seconds"].as_f64().unwrap_or(0.0)
    );
    if let Some(s) = la.get("sparse").filter(|v| !v.is_null()) {
        let f = &s["filter"];
        line.push_str(&format!(
            "; filtered {} rows × {} columns to a core of {} ({} singletons, {} excess rows, {} merged)",
            f["rows_in"], f["columns_in"], s["core_dimension"], f["singletons_removed"],
            f["excess_rows_removed"], f["merged_columns"]
        ));
        if let Some(w) = s.get("wiedemann").filter(|v| !v.is_null()) {
            line.push_str(&format!(
                "; block Wiedemann {}×{}, {} Krylov terms, {} products",
                w["block_m"], w["block_n"], w["sequence_length"], w["products"]
            ));
        }
    }
    line
}

fn display(report: &Value) {
    match report["operation"].as_str() {
        Some("inspect") => {
            println!(
                "Curve: {}\nInspection: {}",
                report["parameters"]["name"].as_str().unwrap_or("?"),
                report["status"].as_str().unwrap_or("?")
            );
            for check in report["checks"].as_array().into_iter().flatten() {
                println!(
                    "  {}: {} — {}",
                    check["name"].as_str().unwrap_or("?"),
                    check["status"].as_str().unwrap_or("?"),
                    check["details"].as_str().unwrap_or("")
                );
            }
            println!("Capabilities: inspection only; imported-target solving is unavailable.");
        }
        Some("run") => {
            println!("Run: {}", report["status"].as_str().unwrap_or("?"));
            if let Some(result) = report.get("result") {
                println!(
                    "Expected: {}; recovered: {}; verified: {}",
                    result["expected"], result["recovered"], result["verified"]
                );
            }
            println!(
                "Counts: {}\nResources: {}",
                report["counts"], report["resources"]
            );
        }
        Some("compare") => {
            println!(
                "Comparison: {}; selected factor: {}",
                report["status"], report["selected_factor_index"]
            );
            for candidate in report["candidates"].as_array().into_iter().flatten() {
                println!(
                    "  factor {}: eligible {}; median process seconds {}",
                    candidate["factor_index"],
                    candidate["eligible"],
                    candidate["median_process_seconds"]
                );
            }
            println!("Scope: {}", report["scope"]);
        }
        Some("search") => {
            println!(
                "Search: {}; {} candidates scored on {} targets{}",
                report["status"],
                report["candidate_count"],
                report["targets"],
                if report["exhaustive_targets"] == true {
                    " (whole subgroup)"
                } else {
                    " (sampled)"
                }
            );
            for (i, c) in report["candidates"]
                .as_array()
                .into_iter()
                .flatten()
                .take(10)
                .enumerate()
            {
                println!(
                    "  #{:<2} {:<22} points {:>5} columns {:>4} coverage {:>6} expected trials {}",
                    i + 1,
                    c["family"].as_str().unwrap_or("?"),
                    c["points"],
                    c["unknowns"],
                    c["coverage"]
                        .as_f64()
                        .map_or("—".to_string(), |v| format!("{v:.3}")),
                    c["expected_trials"]
                        .as_f64()
                        .map_or("∞".to_string(), |v| format!("{v:.1}"))
                );
            }
            for v in report["validation"]["runs"]
                .as_array()
                .into_iter()
                .flatten()
            {
                println!(
                    "  validated #{}: eligible {}; median process seconds {}",
                    v["rank"], v["eligible"], v["median_process_seconds"]
                );
            }
            match report["selected"].get("spec") {
                Some(spec) => println!("Selected: {spec}"),
                None => println!("Selected: none"),
            }
            if let Some(path) = report["spec_out"].as_str() {
                println!("Recipe saved: {path}");
            }
        }
        Some("logs") => {
            println!(
                "Logs: {}; {} columns; {} trials; {} relations",
                report["status"],
                report["counts"]["columns"],
                report["counts"]["trials"],
                report["counts"]["relations"]
            );
            if let Some(la) = report.get("linear_algebra").filter(|v| !v.is_null()) {
                println!("Linear algebra: {}", linear_algebra_summary(la));
            }
            if let Some(path) = report["out"].as_str() {
                println!("Database saved: {path}");
            } else if let Some(reason) = report["reason"].as_str() {
                println!("Reason: {reason}");
            }
        }
        Some("solve") => {
            println!(
                "Solve: {}; database columns {} (re-verified)",
                report["status"], report["database"]["columns"]
            );
            if let Some(result) = report.get("result") {
                println!(
                    "Expected: {}; recovered: {}; verified: {}; descent trials: {}",
                    result["expected"],
                    result["recovered"],
                    result["verified"],
                    report["counts"]["descent_trials"]
                );
            }
        }
        Some("workflow") => {
            println!(
                "Workflow: {}; run {}{}; {}",
                report["status"],
                report["run_number"],
                if report["resumed"] == true {
                    " (resumed)"
                } else {
                    ""
                },
                report["run_directory"].as_str().unwrap_or("?")
            );
            for st in report["stages"].as_array().into_iter().flatten() {
                println!(
                    "  {:<6} {:<8} {}",
                    st["stage"].as_str().unwrap_or("?"),
                    st["status"].as_str().unwrap_or("?"),
                    if st["ran"] == true { "ran" } else { "reused" }
                );
                if let Some(u) = st.get("units").filter(|v| !v.is_null()) {
                    println!(
                        "         units: {} present ({} ran now, {} ignored); {} relations from {} probes",
                        u["present"], u["ran_now"], u["ignored"], st["relations_total"], st["trials_total"]
                    );
                }
                if let Some(la) = st.get("linear_algebra").filter(|v| !v.is_null()) {
                    println!("         linear algebra: {}", linear_algebra_summary(la));
                }
                if let Some(v) = st.get("vs_rho").filter(|v| !v.is_null()) {
                    println!(
                        "         vs rho: descent {:.4}s/target, amortised {:.4}s/target, rho {:.4}s/target ({} of {} rho-verified); charged ratio {:.1}x, amortised {:.2}x; charged crossover {}",
                        v["ic"]["descent_seconds_per_target"].as_f64().unwrap_or(0.0),
                        v["ic"]["amortised_seconds_per_target"].as_f64().unwrap_or(0.0),
                        v["rho"]["seconds_per_target"].as_f64().unwrap_or(0.0),
                        v["rho"]["verified"], v["targets"],
                        v["ratio"]["charged"].as_f64().unwrap_or(0.0),
                        v["ratio"]["amortised"].as_f64().unwrap_or(0.0),
                        v["verdict"]["charged_crossover"]
                    );
                }
            }
            if let Some(sol) = report.get("solutions").filter(|v| !v.is_null()) {
                println!(
                    "Solutions: {} verified of {}",
                    sol["verified"], sol["count"]
                );
            }
            if let Some(f) = report["failure"].as_str() {
                println!("Failure: {f}");
            }
        }
        Some("error") => {
            eprintln!(
                "ic: {}",
                report["message"].as_str().unwrap_or("operation failed")
            );
        }
        Some("list") => {
            for name in params::NAMES {
                println!("{name}");
            }
        }
        _ => println!("{}", serde_json::to_string_pretty(report).unwrap()),
    }
}
fn main() -> ExitCode {
    let cli = Cli::parse();
    if let Some(path) = &cli.out {
        if std::fs::symlink_metadata(path).is_ok() {
            eprintln!("ic: output already exists: {}", path.display());
            return ExitCode::FAILURE;
        }
    }
    let mut report = match execute(&cli) {
        Ok(v) => v,
        Err(message) => {
            json!({"schema_version":1,"operation":"error","status":"error","message":message})
        }
    };
    // Generated parameter documents remain directly importable under their strict schema.
    if report.get("operation").is_some() {
        report["software"] = json!({"version":env!("CARGO_PKG_VERSION"),"os":std::env::consts::OS,
            "arch":std::env::consts::ARCH,"binary_blake3":binary_hash()});
    }
    let success = matches!(
        report["status"].as_str(),
        Some("complete" | "checks_passed" | "stopped")
    ) || report.get("operation").is_none();
    let text = serde_json::to_string_pretty(&report).expect("JSON serializable");
    if let Some(path) = &cli.out {
        let result = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(path)
            .and_then(|mut f| {
                f.write_all(text.as_bytes())?;
                f.write_all(b"\n")?;
                f.sync_all()
            });
        if let Err(error) = result {
            eprintln!("ic: could not create report {}: {error}", path.display());
            return ExitCode::FAILURE;
        }
    }
    if cli.json || report.get("operation").is_none() {
        println!("{text}");
    } else {
        display(&report);
        if let Some(path) = &cli.out {
            println!("Report saved: {}", path.display());
        }
    }
    if success {
        ExitCode::SUCCESS
    } else {
        ExitCode::FAILURE
    }
}
