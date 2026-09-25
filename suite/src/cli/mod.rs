//! `crax`: the unified command line of the toolkit.
//!
//! One binary, one subcommand per attack. The generic discrete-logarithm
//! solvers run on the C library in the repository root (64-bit groups,
//! measured constants); everything else runs on this crate's
//! arbitrary-precision attacks. Every command takes the global `--json`
//! flag and then prints exactly one JSON object; every answer a command
//! reports as solved has been verified independently of the solver that
//! produced it.
//!
//! The older binaries (`ca-suite`, `ca-ic`, `ca-curves`) remain as
//! compatible entry points to the same code.

pub mod challenge;
pub mod curve;
pub mod dlog;
pub mod ic;
pub mod output;

use std::process::ExitCode;

use clap::{Parser, Subcommand};

use output::{CmdResult, Out};

const OVERVIEW: &str = "\
Attacks by family:
  discrete logs (generic)   bsgs, rho, kangaroo, grumpy, precomp, glv, pohlig-hellman, cheon, gpu-rho
  index calculus            ic zp
  curves & challenges       curve names, curve info, challenge list|show|solve|rho-job

Every command accepts --json. `crax <command> --help` shows its options.";

/// The top-level parser.
#[derive(Parser, Debug)]
#[command(
    name = "crax",
    version,
    about = "Cryptanalysis toolkit: discrete logarithms, index calculus, factoring, weak curves, \
             symmetric, hash, lattice and post-quantum attacks",
    after_help = OVERVIEW
)]
pub struct Cli {
    /// Print one JSON object instead of text.
    #[arg(long, global = true)]
    pub json: bool,
    #[command(subcommand)]
    pub command: Command,
}

/// Every `crax` subcommand.
#[derive(Subcommand, Debug)]
pub enum Command {
    /// Baby-step giant-step over an interval or the whole group.
    Bsgs(dlog::IntervalArgs),
    /// Pollard rho: r-adding walk, distinguished points, negation map, threads.
    Rho(dlog::RhoArgs),
    /// Pollard kangaroo (van Oorschot-Wiener) over an interval.
    Kangaroo(dlog::IntervalArgs),
    /// Two grumpy giants and a baby (Bernstein-Lange).
    Grumpy(dlog::IntervalArgs),
    /// Discrete logs with a Bernstein-Lange precomputed table.
    Precomp(dlog::PrecompArgs),
    /// Rho folded by the GLV endomorphism of a j = 0 / 1728 curve.
    Glv(dlog::GlvArgs),
    /// Pohlig-Hellman over the factorised group order.
    #[command(visible_aliases = ["ph", "dlog"])]
    PohligHellman(dlog::PohligArgs),
    /// Cheon's attack on the strong Diffie-Hellman problem.
    Cheon(dlog::CheonArgs),
    /// Pollard rho on the GPU kernel (CUDA, or its host emulator).
    GpuRho(dlog::GpuRhoArgs),
    /// Index calculus.
    #[command(subcommand)]
    Ic(IcCmd),
    /// Curve registry and structure.
    #[command(subcommand)]
    Curve(curve::CurveCmd),
    /// The elliptic-curve challenge corpus: list, show, solve.
    Challenge(challenge::ChallengeArgs),
}

/// `crax ic ...`
#[derive(Subcommand, Debug)]
pub enum IcCmd {
    /// Discrete logs in (Z/pZ)^* by the linear sieve (p < 2^63).
    Zp(ic::ZpArgs),
}

/// Run one parsed command.
pub fn run(out: Out, cmd: Command) -> CmdResult {
    use dlog::IntervalSolver;
    match cmd {
        Command::Bsgs(a) => dlog::run_interval(out, IntervalSolver::Bsgs, &a),
        Command::Rho(a) => dlog::run_rho(out, &a),
        Command::Kangaroo(a) => dlog::run_interval(out, IntervalSolver::Kangaroo, &a),
        Command::Grumpy(a) => dlog::run_interval(out, IntervalSolver::Grumpy, &a),
        Command::Precomp(a) => dlog::run_precomp(out, &a),
        Command::Glv(a) => dlog::run_glv(out, &a),
        Command::PohligHellman(a) => dlog::run_pohlig(out, &a),
        Command::Cheon(a) => dlog::run_cheon(out, &a),
        Command::GpuRho(a) => dlog::run_gpu_rho(out, &a),
        Command::Ic(IcCmd::Zp(a)) => ic::run_zp(out, &a),
        Command::Curve(c) => curve::run(out, &c),
        Command::Challenge(a) => challenge::run(out, &a),
    }
}

/// Entry point of the `crax` binary.
pub fn main() -> ExitCode {
    let cli = Cli::parse();
    let out = Out { json: cli.json };
    match run(out, cli.command) {
        Ok(()) => ExitCode::SUCCESS,
        Err(f) => {
            if f.reported {
                eprintln!("error: {}", f.message);
            } else if out.json {
                println!(
                    "{}",
                    serde_json::json!({ "status": "error", "error": f.message })
                );
            } else {
                eprintln!("error: {}", f.message);
            }
            ExitCode::FAILURE
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use clap::CommandFactory;

    #[test]
    fn the_command_tree_is_well_formed() {
        Cli::command().debug_assert();
    }
}
