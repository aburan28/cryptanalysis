//! What the `π − 1` transport on `K_0` is worth, measured.
//!
//! ```bash
//! cargo run --release --example transport_bench
//! ```
//!
//! For each instance: the symmetrised oracle solved directly for `R` and
//! solved for `φ(R)` then lifted; whether the two verdicts ever differ
//! (theory: never); how often `R` decomposes over `F_u`, over `φ⁻¹(F_u)`
//! and over their union by exhaustive enumeration; and how many projected
//! columns each base occupies.  See `research/notes/index-calculus/RESEARCH_EXOTIC_COORDINATES.md` §11.

use cryptanalysis_suite::cryptanalysis::koblitz_symmetrised::{format_transport, transport_bench};
use std::time::Instant;

fn main() {
    let targets: usize = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(12);
    println!("=== π − 1 transport on K_0, {targets} targets per instance ===");
    println!();
    // K_0 needs n with a usable prime-order subgroup (n = 15, 23 in range)
    // and an invariant subspace containing 1 whose u-frame base is not a
    // single point — dim 7 at n = 15, dim 12 at n = 23.
    for (n, m, t) in [
        (15u32, 2usize, targets),
        (15, 3, targets),
        (23, 2, targets.min(4)),
    ] {
        let t0 = Instant::now();
        match transport_bench(n, m, t, 0x5EED, 20_000) {
            Some(b) => print!("{}", format_transport(&b)),
            None => println!("== K_0/F_2^{n} m = {m}: no instance"),
        }
        println!("   ({:.1} s)", t0.elapsed().as_secs_f64());
        println!();
    }
}
