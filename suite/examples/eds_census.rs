//! EDS-Residue **bias census** — step 1 of the research program in
//! `research/notes/cm-isogeny/RESEARCH_EDS_RESIDUE.md`.
//!
//! ```bash
//! cargo run --release --example eds_census
//! ```
//!
//! Sweeps thousands of curves `y²=x³+ax+b` over several primes `p ≡ 3 mod 4`
//! and aggregates the apparition-block quadratic-residue bias of the
//! associated elliptic divisibility sequence, broken down by the multiplier
//! characters `(χ(A), χ(B))`.  The question: is the residue bias generic
//! noise, or curve-structured?

use cryptanalysis_suite::cryptanalysis::eds_residue::{census, format_census};
use std::time::Instant;

fn main() {
    println!("\n=== EDS-Residue bias census ===\n");
    // (p, a_max, b_max, min_order, cap, label).
    let runs = [
        (4099u64, 40u64, 40u64, 80u64, 5_000usize, "≡3 mod 4"),
        (10_007, 40, 40, 200, 11_000, "≡3 mod 4"),
        (100_003, 28, 28, 2_000, 101_000, "≡3 mod 4"),
        (4093, 40, 40, 80, 5_000, "≡1 mod 4"),
        (10_009, 40, 40, 200, 11_000, "≡1 mod 4"),
    ];
    for (p, am, bm, mo, cap, label) in runs {
        println!("# p = {} ({}):", p, label);
        let t = Instant::now();
        let (s, recs) = census(p, am, bm, mo, cap);
        println!("{}", format_census(&s));
        // Top-5 most-biased curves for inspection.
        let mut top = recs.clone();
        top.sort_by(|x, y| y.bias.abs().partial_cmp(&x.bias.abs()).unwrap());
        print!("  top |bias|:");
        for r in top.iter().take(5) {
            print!(
                " (a={},b={},ord={},χA={:+},χB={:+},bias={:+.3})",
                r.a, r.b, r.order, r.chi_a, r.chi_b, r.bias
            );
        }
        println!("\n  [{:.2}s]\n", t.elapsed().as_secs_f64());
    }
}
