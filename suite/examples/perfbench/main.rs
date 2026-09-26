//! `perfbench` — the repository-wide performance index.
//!
//! ```bash
//! cargo run --release --example perfbench -- list
//! cargo run --release --example perfbench -- run --filter gf2_la/
//! python3 scripts/perf/perfindex.py --help   # baseline vs candidate index
//! ```
//!
//! Every kernel runs a fixed, seeded input through an existing public entry
//! point and returns a fingerprint of the result, so the same harness built
//! against an older revision measures that revision's code on identical
//! work.  The formula that turns the per-kernel timings into one number is
//! in `docs/perf/PERFORMANCE_INDEX.md`.  These are engineering (stage)
//! measurements in the sense of `AGENTS.md` §3 and §8: a kernel speedup
//! changes the time per counted operation, not the operation count, and is
//! never an end-to-end method speedup on its own.

mod harness;

mod bool_gb;
mod dlp;
mod field_ec;
mod fp_gb;
mod gf2_la;
mod pdp;
mod relation;
mod sat;

fn registry() -> Vec<harness::Kernel> {
    let mut kernels = Vec::new();
    gf2_la::register(&mut kernels);
    bool_gb::register(&mut kernels);
    fp_gb::register(&mut kernels);
    sat::register(&mut kernels);
    pdp::register(&mut kernels);
    field_ec::register(&mut kernels);
    relation::register(&mut kernels);
    dlp::register(&mut kernels);
    kernels
}

fn main() {
    harness::main(registry());
}
