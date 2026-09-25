//! `ca-ic` — curve inspection and bounded known-answer index-calculus experiments; the same command line is `crax ic`.
//! See [`cryptanalysis_suite::cli::tools::ic`].

fn main() -> std::process::ExitCode {
    cryptanalysis_suite::cli::default_sigpipe();
    cryptanalysis_suite::cli::tools::ic::run_from(std::env::args_os())
}
