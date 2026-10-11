//! Research CLI: read-only curve inspection and bounded known-answer experiments.
mod bench;
mod boundary;
mod budget;
mod corpus;
mod descent;
mod experiment;
mod fixed;
mod params;
mod prime;
mod rho;
mod workflow;

use clap::{Args, Parser, Subcommand};
use serde_json::{json, Value};
use std::{
    fs::{File, OpenOptions},
    io::{Read, Write},
    path::PathBuf,
    process::ExitCode,
    sync::OnceLock,
};

#[derive(Parser)]
#[command(
    name = "ic",
    version,
    about = "Curve inspection and synthetic index-calculus research"
)]
#[command(
    long_about = "Inspect named/custom curves, generate reproducible known-answer fixtures, run the toy index-calculus pipeline, compare factor-base candidates, or search for high-yield factor bases. Bare ic runs the default synthetic example. A bare curve name (for example ic ecc2k-130 or ic p224) performs inspection only. The fixed subcommand accepts explicit K_0 parameters and points with full-width coordinates. The prime subcommand runs prime-field index calculus by curve type (generic, as P-192/P-224; j0, as secp256k1) on a scaled-down curve of that type."
)]
pub struct Cli {
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
    /// Charge index calculus against rho analytically: what one decomposition may cost.
    Budget(budget::BudgetArgs),
    /// Prime-field index calculus by curve type (generic P-curves, j0 Koblitz such as secp256k1): a named curve's structure, then a verified run on a scaled-down curve of that type against rho.
    Prime(prime::PrimeArgs),
    /// Price every index-calculus variant of the prime, generic-binary and Koblitz regimes in one unit against the generic floor and a counted Pollard rho, with fitted exponents.
    Boundary(boundary::BoundaryArgs),
    /// Write a benchmark corpus of Weil-descended Semaev S4 instances (Magma, DIMACS+XOR, CNF, ANF) with certified labels and planted witnesses.
    Corpus(corpus::CorpusArgs),
    /// Measure the degree a Weil-descent system actually reaches, against the degree a semi-regular system of the same shape would, with the operation count, wall time and peak footprint beside it.
    Descent(descent::DescentArgs),
    /// Run index-calculus configurations end to end and compare them: plug a factor base, a target source, a decomposition oracle, a polynomial solver and a relation matrix together, and see every stage's cost in one unit.
    Bench(bench::BenchArgs),
    /// Price every decomposition oracle on R and on R − P + Q pairwise: does a solver charge the same for a swapped target?
    Swap(boundary::SwapArgs),
    /// Run the counted Pollard-rho references paired (the frozen plain walk, the tuned walk, the negation-map walk that is the matched reference), or re-price a frozen boundary or bench report against the matched one.
    Rho(rho::RhoArgs),
    /// Discrete logs in (Z/pZ)^* by the C library's linear sieve (p < 2^63), verified.
    Zp(crate::cli::ic::ZpArgs),
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
        Some(Action::Budget(args)) => budget::run(args.clone(), cli.json),
        Some(Action::Prime(args)) => prime::run(args.clone(), cli.json),
        Some(Action::Boundary(args)) => boundary::run(args.clone(), cli.json),
        Some(Action::Corpus(args)) => corpus::run(args.clone()),
        Some(Action::Descent(args)) => descent::run(args.clone(), cli.json),
        Some(Action::Bench(args)) => bench::run(args.clone(), cli.json),
        Some(Action::Swap(args)) => boundary::swap(args.clone(), cli.json),
        Some(Action::Rho(args)) => rho::run(args.clone(), cli.json),
        Some(Action::Zp(args)) => crate::cli::ic::solve_zp(args)
            .and_then(|r| serde_json::to_value(r).map_err(|e| e.to_string())),
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
/// Provenance, captured **at start-up** and cached.
///
/// Both of these used to be read when the report was assembled, which on a
/// run of any length is the wrong moment: a rebuild during the run replaces
/// the executable, so `current_exe` no longer opens (the hash came out
/// `null`), and a commit made during the run is the one `git rev-parse`
/// answers with — so a report could name a commit whose code never ran.
/// Reading both before any work makes the pair describe the binary that
/// produced the numbers.
static BINARY_HASH: OnceLock<Option<String>> = OnceLock::new();
static GIT_COMMIT: OnceLock<Option<String>> = OnceLock::new();

/// Hash of the executable that is producing this report.
pub fn binary_hash() -> Option<String> {
    BINARY_HASH.get_or_init(compute_binary_hash).clone()
}

/// The working tree's commit when this process started.
pub fn git_commit() -> Option<String> {
    GIT_COMMIT.get_or_init(compute_git_commit).clone()
}

fn compute_git_commit() -> Option<String> {
    let out = std::process::Command::new("git")
        .args(["rev-parse", "HEAD"])
        .output()
        .ok()?;
    out.status
        .success()
        .then(|| String::from_utf8_lossy(&out.stdout).trim().to_string())
}

fn compute_binary_hash() -> Option<String> {
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

/// The `prime` summary: either solver's result, then the rho comparison.
fn display_prime(report: &Value) {
    let f = |v: &Value| v.as_f64().unwrap_or(f64::NAN);
    println!(
        "Prime-field index calculus ({}): {}",
        report["solver"].as_str().unwrap_or("?"),
        report["status"].as_str().unwrap_or("?")
    );
    println!(
        "Expected: {}; recovered: {}; verified: {}",
        report["result"]["expected"], report["result"]["recovered"], report["result"]["verified"]
    );
    if report["solver"] == "semaev" {
        let ic = &report["index_calculus"];
        let rho = &report["rho"];
        println!(
            "Index calculus ({}, {} factor-base {}): verified {} in {:.4}s over {} attempt(s)",
            ic["solver"]["method"].as_str().unwrap_or("?"),
            ic["factor_base"],
            ic["factor_base_unit"].as_str().unwrap_or("?"),
            ic["solver"]["verified"],
            f(&ic["solver"]["seconds"]),
            ic["solver"]["attempts"]
        );
        println!(
            "Pollard rho (plain walk): verified {} in {:.5}s; expected {:.0} steps, {:.0} with the |Aut| = {} fold",
            rho["solver"]["verified"],
            f(&rho["solver"]["seconds"]),
            f(&rho["expected_steps"]),
            f(&rho["expected_steps_folded"]),
            rho["automorphism_order"]
        );
        match report["vs_rho"]["rho_seconds_over_ic_seconds"].as_f64() {
            Some(r) if r > 0.0 && r < 1.0 => println!(
                "vs rho: rho/IC time {r:.4} — index calculus is {:.0}x slower",
                1.0 / r
            ),
            Some(r) => println!("vs rho: rho/IC time {r:.4}"),
            None => println!("vs rho: not measured"),
        }
        return;
    }
    let fb = &report["factor_base"];
    let logs = &report["logs"];
    let des = &report["descent"];
    println!(
        "Factor base: {} orbits ({} certified, sized {}) of |Aut| = {} points; {} relations from {} probes",
        fb["orbits"],
        fb["certified_orbits"],
        fb["sizing"].as_str().unwrap_or("?"),
        fb["automorphism_order"],
        logs["relations"],
        logs["trials"]
    );
    if logs["collection"] == "large_primes" {
        println!(
            "Large primes: {} relations from two probes meeting on one of {} large primes, {} with both summands in the base; {} large-prime logarithms known",
            logs["combined_relations"],
            logs["distinct_large_primes"],
            logs["full_relations"],
            logs["known_large_primes"]
        );
    }
    println!(
        "Logarithm precompute: {:.3e} group operations in {:.3}s",
        f(&logs["oracle_ops"]) + f(&logs["probe_ops"]),
        f(&logs["seconds"])
    );
    println!(
        "Descent: {}/{} verified, {} through a large prime, {} large primes learnt for the targets after; mean {:.0} group operations per target",
        des["verified"],
        des["per_target"].as_array().map_or(0, Vec::len),
        des["through_large_primes"],
        des["learned_large_primes"],
        f(&des["mean_ops"])
    );
    let rho = &report["rho"];
    if rho.is_null() {
        println!("Rho: skipped");
        return;
    }
    println!(
        "Rho (unfolded, {} batched walks): {} verified; mean {:.0} steps + {:.0} setup (expected {:.0} steps; folded expectation {:.0})",
        rho["walks"],
        rho["verified"],
        f(&rho["mean_steps"]),
        f(&rho["mean_setup_ops"]),
        f(&rho["expected_steps"]),
        f(&rho["expected_steps_folded"])
    );
    let v = &report["vs_rho"];
    println!(
        "vs rho (rho/IC, group operations): charged {:.3}, against the folded expectation {:.3}; amortised {:.4}; whole process {:.4}",
        f(&v["charged"]["ratio"]),
        f(&v["charged"]["ratio_vs_folded_expectation"]),
        f(&v["amortised"]["ratio"]),
        f(&v["whole_process"]["ratio"])
    );
    let b = &v["whole_process_vs_batch_rho"];
    println!(
        "vs batch rho (Kuhn-Struik expectation, distinguished points shared by the targets): whole process {:.3}, {:.3} against the folded walk",
        f(&b["ratio"]),
        f(&b["ratio_folded"])
    );
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
        Some("budget") => {
            println!(
                "Budget: {}; Frobenius orbit quotient {}",
                report["status"].as_str().unwrap_or("?"),
                if report["frobenius_orbit_quotient_credited"].as_bool() == Some(true) {
                    "credited"
                } else {
                    "not credited"
                }
            );
            for degree in report["degrees"].as_array().into_iter().flatten() {
                println!(
                    "  n = {}: rho 2^{:.1}; smallest arity with a budget: {}",
                    degree["degree"],
                    degree["log2_rho"].as_f64().unwrap_or(f64::NAN),
                    degree["minimum_viable_arity"]
                );
                for cell in degree["cells"].as_array().into_iter().flatten() {
                    let budget = cell["log2_budget"].as_f64();
                    let deficit = cell["log2_anf_deficit"].as_f64();
                    println!(
                        "    m = {} l = {}: budget {}; system 2^{:.1} monomials, degree {} ({}); {}",
                        cell["summands"],
                        cell["dimension"],
                        match budget {
                            Some(b) => format!("2^{b:.1}"),
                            None => "none — linear algebra alone exceeds rho".into(),
                        },
                        cell["log2_anf_monomials"].as_f64().unwrap_or(f64::NAN),
                        cell["boolean_degree"],
                        match deficit {
                            Some(d) if d > 0.0 =>
                                format!("{d:.1} bits too large to build inside the budget"),
                            Some(_) => "fits inside the budget".into(),
                            None => "not reached".into(),
                        },
                        if cell["viable"].as_bool() == Some(true) {
                            "worth attempting"
                        } else if cell["free_oracle_loses"].as_bool() == Some(true) {
                            "loses to rho even with a free decomposition oracle"
                        } else {
                            "blocked by the size of the system, whatever solves it"
                        }
                    );
                }
            }
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
        Some("prime") => display_prime(report),
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
        Some("boundary") => {
            println!(
                "Boundary ledger: {}; {} instances, all verified: {}; {:.1} s",
                report["status"],
                report["ledger"]["instances"]
                    .as_array()
                    .map_or(0, |a| a.len()),
                report["all_verified"],
                report["elapsed_seconds"].as_f64().unwrap_or(0.0)
            );
            println!("Unit: {}", report["ledger"]["unit"].as_str().unwrap_or("?"));
            println!();
            println!("{}", report["markdown"].as_str().unwrap_or(""));
            if let Some(o) = report.get("oracle_pricing").filter(|v| !v.is_null()) {
                println!(
                    "Oracle pricing: {} cells, all oracles agree: {}",
                    o["cells"].as_array().map_or(0, |a| a.len()),
                    o["all_agree"]
                );
                println!("{}", o["markdown"].as_str().unwrap_or(""));
            }
        }
        Some("corpus") => {
            println!(
                "Corpus: {} instances (n = {}, l = {}); {} files written",
                report["instances"].as_array().map_or(0, |a| a.len()),
                report["config"]["n"],
                report["config"]["l"],
                report["written"].as_array().map_or(0, |a| a.len())
            );
            for inst in report["instances"].as_array().into_iter().flatten() {
                println!(
                    "  {:<16} sat={:<5} xor: {} vars {} clauses {} rows; cnf: {} vars {} clauses; anf: {} eqs",
                    inst["name"].as_str().unwrap_or("?"),
                    inst["satisfiable"],
                    inst["dimacs_xor"]["variables"],
                    inst["dimacs_xor"]["clauses"],
                    inst["dimacs_xor"]["xor_rows"],
                    inst["dimacs_cnf"]["variables"],
                    inst["dimacs_cnf"]["clauses"],
                    inst["anf"]["equations"]
                );
            }
        }
        Some("rho") => {
            println!(
                "Rho references: {}; {} instances, all verified: {}",
                report["status"],
                report["instances"].as_array().map_or(0, |a| a.len()),
                report["all_verified"]
            );
        }
        Some("rho-batch") => {
            println!(
                "Batch rho: {}; {} curves, all verified: {}",
                report["status"],
                report["curves"].as_array().map_or(0, |a| a.len()),
                report["all_verified"]
            );
        }
        Some("rho-reprice") => {
            println!(
                "Re-priced {}: {}; the frozen walk reproduced on every recorded seed: {}",
                report["source"].as_str().unwrap_or("?"),
                report["status"],
                report["identity"]["all_reproduced"]
            );
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
/// Run the `ca-ic` command line on `args` (the first item is the program
/// name, as in `std::env::args_os`).
pub fn run_from<I, T>(args: I) -> ExitCode
where
    I: IntoIterator<Item = T>,
    T: Into<std::ffi::OsString> + Clone,
{
    let cli = Cli::parse_from(args);
    // Before any work: the binary that is about to run, and the commit it
    // was built from.  See `BINARY_HASH`.
    let _ = binary_hash();
    let _ = git_commit();
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
