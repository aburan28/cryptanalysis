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
//! `crax ic`, `crax icx` and the suite's cipher, hash, lattice, isogeny and
//! collaborative-rho commands are the research command lines in
//! [`tools`], handed their arguments unchanged: they keep their own flags
//! and report formats. The older binaries (`ca-ic`, `ca-icx`, `ca-suite`,
//! `ca-curves`) remain as compatible entry points to the same code.

pub mod challenge;
pub mod curve;
pub mod dlog;
pub mod ic;
pub mod output;
pub mod tools;

use std::ffi::OsString;
use std::process::ExitCode;

use clap::{CommandFactory, FromArgMatches, Parser, Subcommand};

use output::{CmdResult, Out};

const OVERVIEW: &str = "\
Attacks by family:
  discrete logs (generic)   bsgs, rho, kangaroo, grumpy, precomp, glv, pohlig-hellman, cheon, gpu-rho
  index calculus            ic (zp, prime, run, compare, fixed, workflow, boundary, bench, rho, ...), icx
  symmetric & hash          list-ciphers, auto, boomerang, rectangle, sbox, aes-related-key, hash-auto, length-extension
  lattice & post-quantum    mlwe
  isogenies                 isogeny
  distributed rho           rho-collab
  demos & research bench    visual-all, aes-visual-demo, bench, ec-challenges
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
    /// Curve registry and structure.
    #[command(subcommand)]
    Curve(curve::CurveCmd),
    /// The elliptic-curve challenge corpus: list, show, solve.
    Challenge(challenge::ChallengeArgs),
}

/// `crax ic zp`, parsed by `crax` itself so that it prints like the other
/// generic solvers.
#[derive(Parser, Debug)]
#[command(name = "crax ic zp", about = "Discrete logs in (Z/pZ)^* by the linear sieve (p < 2^63)")]
struct IcZpCli {
    /// Print one JSON object instead of text.
    #[arg(long)]
    json: bool,
    #[command(flatten)]
    args: ic::ZpArgs,
}

/// Which research command line a subcommand belongs to.
enum Tool {
    Ic,
    Icx,
    Suite,
}

/// The suite subcommands `crax` hands to [`tools::suite`].
fn suite_commands() -> Vec<String> {
    tools::suite::Cli::command()
        .get_subcommands()
        .map(|c| c.get_name().to_string())
        .collect()
}

fn tool_for(sub: &str) -> Option<Tool> {
    match sub {
        "ic" => Some(Tool::Ic),
        "icx" => Some(Tool::Icx),
        s if suite_commands().iter().any(|c| c == s) => Some(Tool::Suite),
        _ => None,
    }
}

/// The full command tree, for `--help`: `crax`'s own subcommands plus the
/// research command lines, grafted in under their `crax` names.
pub fn command() -> clap::Command {
    // crax's own subcommands first, in declaration order; the research
    // command lines after them.
    let mut cmd = Cli::command();
    let own: Vec<String> = cmd.get_subcommands().map(|c| c.get_name().to_string()).collect();
    for (i, name) in own.iter().enumerate() {
        cmd = cmd.mut_subcommand(name, |c| c.display_order(i));
    }
    let mut cmd = cmd
        .subcommand(
            tools::ic::Cli::command()
                .name("ic")
                .about("Index calculus: prime-field curves by type, Koblitz curves, fixed K_0 runs, boundary pricing, (Z/pZ)^* (`ic zp`)"),
        )
        .subcommand(
            tools::icx::Cli::command()
                .name("icx")
                .about("Index calculus across every standardized curve: catalog, estimate, run"),
        );
    for sub in tools::suite::Cli::command().get_subcommands() {
        cmd = cmd.subcommand(sub.clone());
    }
    let n = own.len();
    for (i, name) in ["ic", "icx"].iter().enumerate() {
        cmd = cmd.mut_subcommand(name, |c| c.display_order(n + i));
    }
    for (i, name) in suite_commands().iter().enumerate() {
        cmd = cmd.mut_subcommand(name, |c| c.display_order(n + 2 + i));
    }
    cmd
}

/// Die quietly on a closed pipe (`crax ... | head`) as command-line tools
/// do, instead of panicking in `println!`.
pub fn default_sigpipe() {
    #[cfg(unix)]
    // SAFETY: restoring the default disposition of one signal before any
    // thread is started; no handler runs Rust code.
    unsafe {
        libc::signal(libc::SIGPIPE, libc::SIG_DFL);
    }
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
        Command::Curve(c) => curve::run(out, &c),
        Command::Challenge(a) => challenge::run(out, &a),
    }
}

/// Entry point of the `crax` binary.
pub fn main() -> ExitCode {
    default_sigpipe();
    main_from(std::env::args_os())
}

/// Run `crax` on `args` (the first item is the program name).
pub fn main_from<I, T>(args: I) -> ExitCode
where
    I: IntoIterator<Item = T>,
    T: Into<OsString> + Clone,
{
    let args: Vec<OsString> = args.into_iter().map(Into::into).collect();
    // A leading --json belongs to crax; the research tools take theirs after
    // the subcommand, so move it there.
    let lead_json = args.get(1).is_some_and(|a| a == "--json");
    let rest: Vec<OsString> = args.iter().skip(if lead_json { 2 } else { 1 }).cloned().collect();
    let sub = rest.first().and_then(|a| a.to_str()).unwrap_or("");
    if let Some(tool) = tool_for(sub) {
        let is_zp = matches!(tool, Tool::Ic) && rest.get(1).is_some_and(|a| a == "zp");
        if !is_zp {
            let mut argv: Vec<OsString> = vec![format!("crax {sub}").into()];
            argv.extend(rest[1..].iter().cloned());
            if lead_json && !matches!(tool, Tool::Suite) {
                argv.push("--json".into());
            }
            return match tool {
                Tool::Ic => tools::ic::run_from(argv),
                Tool::Icx => tools::icx::run_from(argv),
                Tool::Suite => {
                    let mut argv = argv;
                    argv[0] = "crax".into();
                    argv.insert(1, sub.into());
                    tools::suite::run_from(argv)
                }
            };
        }
        let mut argv: Vec<OsString> = vec!["crax ic zp".into()];
        argv.extend(rest[2..].iter().cloned());
        if lead_json {
            argv.push("--json".into());
        }
        let z = IcZpCli::parse_from(argv);
        return finish(Out { json: z.json }, ic::run_zp(Out { json: z.json }, &z.args));
    }
    let matches = command().get_matches_from(&args);
    let cli = match Cli::from_arg_matches(&matches) {
        Ok(c) => c,
        Err(e) => e.exit(),
    };
    let out = Out { json: cli.json };
    finish(out, run(out, cli.command))
}

fn finish(out: Out, r: CmdResult) -> ExitCode {
    match r {
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
        command().debug_assert();
        IcZpCli::command().debug_assert();
    }

    #[test]
    fn research_tools_are_routed_by_name() {
        assert!(matches!(tool_for("ic"), Some(Tool::Ic)));
        assert!(matches!(tool_for("icx"), Some(Tool::Icx)));
        for s in ["auto", "mlwe", "rho-collab", "isogeny", "list-ciphers"] {
            assert!(matches!(tool_for(s), Some(Tool::Suite)), "{s}");
        }
        assert!(tool_for("rho").is_none());
        // No crax subcommand shadows a research tool's.
        let own: Vec<String> = Cli::command()
            .get_subcommands()
            .map(|c| c.get_name().to_string())
            .collect();
        for s in suite_commands() {
            assert!(!own.contains(&s), "{s} is both a crax and a suite command");
        }
    }
}
