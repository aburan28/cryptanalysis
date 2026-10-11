//! Prepare a sealed-oracle/blind-bundle Phase-A PDP artifact set.

use clap::{Parser, Subcommand};
use cryptanalysis_suite::cryptanalysis::koblitz_pdp_phase_a::{
    plan_protocol, prepare_protocol, PhaseAProtocol,
};
use cryptanalysis_suite::hash::sha256;
use serde::Serialize;
use serde_json::json;
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::Command as ProcessCommand;

#[derive(Parser, Debug)]
#[command(name = "koblitz-pdp-prepare")]
#[command(about = "Plan or prepare balanced public toy PDP targets; never runs SAT backends")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand, Debug)]
enum Command {
    /// Inspect factor-base geometry and work bounds without running a census.
    Plan {
        #[arg(long)]
        protocol: PathBuf,
    },
    /// Run bounded Phase-A censuses and create separate oracle/blind artifacts.
    Prepare {
        #[arg(long)]
        protocol: PathBuf,
        #[arg(long)]
        output: PathBuf,
        #[arg(long = "cell")]
        cells: Vec<String>,
        /// Mandatory ceiling checked against every selected cell before output exists.
        #[arg(long)]
        max_canonical_triples: u128,
    },
}

fn read_protocol(path: &Path) -> Result<(PhaseAProtocol, Vec<u8>), String> {
    let bytes = fs::read(path).map_err(|error| format!("read {}: {error}", path.display()))?;
    let protocol = serde_json::from_slice(&bytes)
        .map_err(|error| format!("parse {}: {error}", path.display()))?;
    Ok((protocol, bytes))
}

fn pretty_bytes<T: Serialize>(value: &T) -> Result<Vec<u8>, String> {
    let mut bytes = serde_json::to_vec_pretty(value).map_err(|error| error.to_string())?;
    bytes.push(b'\n');
    Ok(bytes)
}

fn write_new(path: &Path, bytes: &[u8]) -> Result<(), String> {
    let mut options = fs::OpenOptions::new();
    options.write(true).create_new(true);
    let mut file = options
        .open(path)
        .map_err(|error| format!("create {}: {error}", path.display()))?;
    file.write_all(bytes)
        .map_err(|error| format!("write {}: {error}", path.display()))
}

fn git_text(root: &Path, arguments: &[&str]) -> Result<String, String> {
    let output = ProcessCommand::new("git")
        .arg("-C")
        .arg(root)
        .args(arguments)
        .output()
        .map_err(|error| format!("run git: {error}"))?;
    if !output.status.success() {
        return Err(format!(
            "git {} failed: {}",
            arguments.join(" "),
            String::from_utf8_lossy(&output.stderr).trim()
        ));
    }
    Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
}

fn implementation_provenance() -> Result<serde_json::Value, String> {
    let binary = std::env::current_exe().map_err(|error| format!("resolve executable: {error}"))?;
    let binary_bytes = fs::read(&binary)
        .map_err(|error| format!("read preparer executable {}: {error}", binary.display()))?;
    let source_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let source_revision = match (
        git_text(&source_root, &["rev-parse", "HEAD"]),
        git_text(
            &source_root,
            &["status", "--porcelain=v1", "--untracked-files=all"],
        ),
    ) {
        (Ok(commit), Ok(porcelain)) => json!({
            "available":true,
            "commit":commit,
            "dirty":!porcelain.is_empty(),
            "porcelain":porcelain.lines().collect::<Vec<_>>(),
        }),
        (commit, status) => json!({
            "available":false,
            "commit_error":commit.err(),
            "status_error":status.err(),
        }),
    };
    Ok(json!({
        "schema":"koblitz_pdp_phase_a_implementation_provenance.v1",
        "preparer_binary_path":binary,
        "preparer_binary_sha256":hex::encode(sha256(&binary_bytes)),
        "build_time_source_root":source_root,
        "source_revision":source_revision,
    }))
}

fn run() -> Result<(), String> {
    let cli = Cli::parse();
    match cli.command {
        Command::Plan { protocol } => {
            let (protocol, _) = read_protocol(&protocol)?;
            let plan = plan_protocol(&protocol)?;
            print!("{}", String::from_utf8(pretty_bytes(&plan)?).unwrap());
        }
        Command::Prepare {
            protocol,
            output,
            cells,
            max_canonical_triples,
        } => {
            if output.exists() {
                return Err(format!("output path must be new: {}", output.display()));
            }
            let (protocol_value, protocol_bytes) = read_protocol(&protocol)?;
            let implementation = implementation_provenance()?;
            // prepare_protocol performs every ceiling and schema check before
            // the first filesystem mutation in this command.
            let artifacts = prepare_protocol(&protocol_value, &cells, max_canonical_triples)?;
            let blind_bytes = pretty_bytes(&artifacts.blind)?;
            let oracle_bytes = pretty_bytes(&artifacts.oracle)?;
            let plan_bytes = pretty_bytes(&artifacts.plan)?;
            fs::create_dir(&output).map_err(|error| format!("create output directory: {error}"))?;
            fs::create_dir(output.join("blind"))
                .map_err(|error| format!("create blind directory: {error}"))?;
            fs::create_dir(output.join("sealed-oracle"))
                .map_err(|error| format!("create sealed-oracle directory: {error}"))?;
            write_new(&output.join("blind/bundle.json"), &blind_bytes)?;
            write_new(
                &output.join("sealed-oracle/oracle-ledger.json"),
                &oracle_bytes,
            )?;
            write_new(&output.join("preparation-plan.json"), &plan_bytes)?;
            let seal = json!({
                "schema":"koblitz_pdp_phase_a_seal.v1",
                "status":"sealed_before_solver_execution",
                "protocol_path":protocol,
                "protocol_sha256":hex::encode(sha256(&protocol_bytes)),
                "blind_bundle_path":"blind/bundle.json",
                "blind_bundle_sha256":hex::encode(sha256(&blind_bytes)),
                "oracle_ledger_path":"sealed-oracle/oracle-ledger.json",
                "oracle_ledger_sha256":hex::encode(sha256(&oracle_bytes)),
                "preparation_plan_path":"preparation-plan.json",
                "preparation_plan_sha256":hex::encode(sha256(&plan_bytes)),
                "selected_cell_ids":artifacts.plan.selected_cell_ids,
                "requested_max_canonical_triples":artifacts.plan.requested_max_canonical_triples,
                "normalized_invocation":std::env::args().collect::<Vec<_>>(),
                "implementation":implementation,
                "solver_access_boundary":"Only the blind directory may be passed to solver processes",
                "execution_status":"not_run"
            });
            write_new(&output.join("seal.json"), &pretty_bytes(&seal)?)?;
            print!("{}", String::from_utf8(pretty_bytes(&seal)?).unwrap());
        }
    }
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("error: {error}");
        std::process::exit(2);
    }
}
