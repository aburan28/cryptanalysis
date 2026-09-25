//! `ic corpus`: write a benchmark corpus of Weil-descended Semaev `S₄`
//! instances (Magma, DIMACS with XOR rows, plain CNF, ANF, INFO) with
//! certified labels — see [`cryptanalysis_suite::cryptanalysis::ic_corpus`].
//!
//!     ic corpus --degree 19 --dimension 6 --sat 5 --unsat 5 --dir corpus/n19l6

use clap::Args;
use cryptanalysis_suite::cryptanalysis::ic_corpus::{generate, write_corpus, CorpusConfig};
use serde_json::{json, Value};
use std::path::PathBuf;

#[derive(Args, Clone, Debug)]
pub struct CorpusArgs {
    /// Field degree n.
    #[arg(long, value_parser = clap::value_parser!(u32).range(3..=62))]
    pub degree: u32,
    /// Factor-base subspace dimension l.
    #[arg(long, value_parser = clap::value_parser!(u32).range(1..=20))]
    pub dimension: u32,
    /// Koblitz coefficient a (0 or 1); b is 1.
    #[arg(long, default_value_t = 1, value_parser = clap::value_parser!(u8).range(0..=1))]
    pub curve_a: u8,
    #[arg(long, default_value_t = 1)]
    pub seed: u64,
    /// Instances with a planted decomposition.
    #[arg(long, default_value_t = 5)]
    pub sat: usize,
    /// Instances certified to have none.
    #[arg(long, default_value_t = 5)]
    pub unsat: usize,
    /// Name prefix (default `n{degree}l{dimension}`).
    #[arg(long, default_value = "")]
    pub prefix: String,
    /// Directory to write the files into; existing files are never
    /// overwritten.  Without it the report carries the sizes only.
    #[arg(long)]
    pub dir: Option<PathBuf>,
    /// Skip the Tseitin-expanded plain CNF, the largest of the formats.
    #[arg(long)]
    pub no_cnf: bool,
}

pub fn run(args: CorpusArgs) -> Result<Value, String> {
    if args.dimension >= args.degree {
        return Err("the subspace dimension must be smaller than the degree".into());
    }
    let cfg = CorpusConfig {
        n: args.degree,
        l: args.dimension,
        a: args.curve_a,
        seed: args.seed,
        satisfiable: args.sat,
        unsatisfiable: args.unsat,
        prefix: args.prefix,
        include_cnf: !args.no_cnf,
    };
    let entries = generate(&cfg)?;
    let written = match &args.dir {
        Some(dir) => write_corpus(&entries, dir, cfg.include_cnf)
            .map_err(|e| format!("could not write the corpus into {}: {e}", dir.display()))?,
        None => Vec::new(),
    };
    let instances: Vec<Value> = entries
        .iter()
        .map(|e| {
            json!({
                "name": e.name,
                "x_r": e.x_r,
                "satisfiable": e.satisfiable,
                "planted": e.planted,
                "planted_true_sat_variables": e.planted_true_variables,
                "dimacs_xor": e.stats_xor,
                "dimacs_cnf": e.stats_cnf,
                "anf": {"equations": e.anf_equations, "monomials": e.anf_monomials},
                "label_checked_by_own_solver": e.checked,
                "blake3": {
                    "dimacs_xor": blake3::hash(e.dimacs_xor.as_bytes()).to_hex().to_string(),
                    "dimacs_cnf": blake3::hash(e.dimacs_cnf.as_bytes()).to_hex().to_string(),
                    "anf": blake3::hash(e.anf.as_bytes()).to_hex().to_string(),
                    "magma": blake3::hash(e.magma.as_bytes()).to_hex().to_string(),
                },
            })
        })
        .collect();
    Ok(json!({
        "schema_version": 1,
        "operation": "corpus",
        "status": "complete",
        "config": cfg,
        "instances": instances,
        "written": written.iter().map(|p| p.display().to_string()).collect::<Vec<_>>(),
        "formats": {
            "INFO<name>": "curve, modulus, target abscissa, certified label, planted witness and its SAT assignment, encoding sizes",
            "<name>.dimacs": "DIMACS CNF with native parity rows as `x` lines (CryptoMiniSat / WDSat convention)",
            "<name>.cnf": "the same system with every parity row Tseitin-expanded to clauses",
            "<name>.anf": "one GF(2) polynomial per line in the shared variable naming",
            "<name>.magma": "the system as a Magma script computing its Groebner basis",
        },
    }))
}
