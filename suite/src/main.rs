//! `ca-suite` — the attack suite (ciphers, hashes, ML-KEM/ML-DSA, collaborative rho, isogenies); the same command line is `crax <command>`.
//! See [`cryptanalysis_suite::cli::tools::suite`].

fn main() -> std::process::ExitCode {
    cryptanalysis_suite::cli::default_sigpipe();
    cryptanalysis_suite::cli::tools::suite::run_from(std::env::args_os())
}
