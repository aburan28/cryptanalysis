//! `ca-icx` — index calculus across every standardized curve; the same command line is `crax icx`.
//! See [`cryptanalysis_suite::cli::tools::icx`].

fn main() -> std::process::ExitCode {
    cryptanalysis_suite::cli::default_sigpipe();
    cryptanalysis_suite::cli::tools::icx::run_from(std::env::args_os())
}
