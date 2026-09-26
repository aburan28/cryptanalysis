//! `crax` — the unified command line: one subcommand per attack.
//! See [`cryptanalysis_suite::cli`].

fn main() -> std::process::ExitCode {
    cryptanalysis_suite::cli::main()
}
