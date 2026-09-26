//! Index of the elliptic-curve challenge corpus.
//!
//! `list` reads `catalog.json`. `show` prints one rich record. `rho-job`
//! writes a collaborative Pollard-rho job for a prime-field curve. The
//! discrete log is not copied into the job.

use std::path::PathBuf;
use std::process::ExitCode;

use clap::{Parser, Subcommand};
use cryptanalysis_suite::ecc::challenges::{
    load_record, prime_field_challenge, Catalog, CatalogEntry,
};

#[derive(Parser, Debug)]
#[command(name = "ca-curves")]
#[command(about = "List and export elliptic-curve challenges")]
struct Cli {
    /// Directory that contains catalog.json, curves/, and inspect/.
    #[arg(long, default_value = concat!(env!("CARGO_MANIFEST_DIR"), "/../challenges/ecc"))]
    corpus: PathBuf,
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand, Debug)]
enum Command {
    /// Print the catalog, optionally filtered.
    List {
        #[arg(long)]
        family: Option<String>,
        #[arg(long)]
        tag: Option<String>,
        /// `check` or `open`.
        #[arg(long)]
        tier: Option<String>,
        #[arg(long)]
        min_bits: Option<u64>,
        #[arg(long)]
        max_bits: Option<u64>,
        #[arg(long)]
        json: bool,
    },
    /// Print one curve record.
    Show { id: String },
    /// Emit a Pollard-rho job for a prime-field short-Weierstrass challenge.
    RhoJob {
        id: String,
        #[arg(long, default_value_t = 1)]
        seed: u64,
    },
}

fn main() -> ExitCode {
    let cli = Cli::parse();
    let result = match cli.command {
        Command::List {
            family,
            tag,
            tier,
            min_bits,
            max_bits,
            json,
        } => list(
            &cli.corpus,
            family.as_deref(),
            tag.as_deref(),
            tier.as_deref(),
            min_bits,
            max_bits,
            json,
        ),
        Command::Show { id } => show(&cli.corpus, &id),
        Command::RhoJob { id, seed } => rho_job(&cli.corpus, &id, seed),
    };
    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(message) => {
            eprintln!("ca-curves: {message}");
            ExitCode::FAILURE
        }
    }
}

fn list(
    root: &std::path::Path,
    family: Option<&str>,
    tag: Option<&str>,
    tier: Option<&str>,
    min_bits: Option<u64>,
    max_bits: Option<u64>,
    json: bool,
) -> Result<(), String> {
    let catalog = Catalog::load(root)?;
    let rows: Vec<&CatalogEntry> = catalog
        .curves
        .iter()
        .filter(|c| family.is_none_or(|f| c.family == f))
        .filter(|c| tier.is_none_or(|t| c.tier == t))
        .filter(|c| min_bits.is_none_or(|n| c.cardinality_bits >= n))
        .filter(|c| max_bits.is_none_or(|n| c.cardinality_bits <= n))
        .filter(|c| tag.is_none_or(|t| c.tags.iter().any(|tag| tag == t)))
        .collect();
    if json {
        let value: Vec<_> = rows
            .iter()
            .map(|c| {
                serde_json::json!({
                    "id": c.id,
                    "family": c.family,
                    "tier": c.tier,
                    "cardinality_bits": c.cardinality_bits,
                    "field_type": c.field_type,
                    "degree": c.degree,
                    "degree_kind": c.degree_kind,
                    "tags": c.tags,
                    "inspect": c.inspect,
                })
            })
            .collect();
        println!("{}", serde_json::to_string_pretty(&value).expect("json"));
        return Ok(());
    }
    println!(
        "{} curves, bits {}..{}, showing {}",
        catalog.curve_count,
        catalog.cardinality_bits_min,
        catalog.cardinality_bits_max,
        rows.len()
    );
    for curve in rows {
        println!(
            "{:<40} {:>4} bits  {:<24} {}",
            curve.id, curve.cardinality_bits, curve.family, curve.tier
        );
    }
    Ok(())
}

fn show(root: &std::path::Path, id: &str) -> Result<(), String> {
    let record = load_record(root, id)?;
    println!("{}", serde_json::to_string_pretty(&record).expect("json"));
    Ok(())
}

fn rho_job(root: &std::path::Path, id: &str, seed: u64) -> Result<(), String> {
    let record = load_record(root, id)?;
    let curve = prime_field_challenge(&record)?;
    let job = curve.rho_job(seed)?;
    println!("{}", job.to_json());
    Ok(())
}
