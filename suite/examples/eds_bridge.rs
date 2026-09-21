//! EDS-Residue **F_p ↔ Z bridge** — Silverman–Stephens archimedean signs vs
//! the arithmetic F_p χ-period.  Item 4 of `research/notes/cm-isogeny/RESEARCH_EDS_RESIDUE.md` §5.
//!
//! ```bash
//! cargo run --release --example eds_bridge
//! ```
//!
//! Computes the integer EDS of curve 37a / point (0,0) (OEIS A006769), shows
//! its sign sequence is archimedean-aperiodic, then reduces it mod several p
//! to show the F_p χ-period is a *different*, arithmetic quantity (r or 2r,
//! set by the multiplier characters), not a reduction of the real sign.

use cryptanalysis_suite::cryptanalysis::eds_residue::{
    eds_integer, reduce_and_analyze, sign_period, signs,
};

fn main() {
    println!("\n=== EDS-Residue F_p ↔ Z bridge (curve 37a, P=(0,0)) ===\n");

    let w = eds_integer(1, -1, 1, 220);
    let s = signs(&w);
    print!("integer EDS (A006769) signs, n=1..40:  ");
    for &sgn in s.iter().take(41).skip(1) {
        print!(
            "{}",
            if sgn > 0 {
                '+'
            } else if sgn < 0 {
                '-'
            } else {
                '0'
            }
        );
    }
    println!();
    match sign_period(&s, 1, 80) {
        Some(p) => println!("  archimedean sign period: {} (periodic)", p),
        None => println!(
            "  archimedean sign period: NONE up to 80 — aperiodic (irrational\n  \
             rotation number; Silverman–Stephens).\n"
        ),
    }

    println!("Reductions mod p — the F_p χ-period is arithmetic (r or 2r):");
    println!("   p  | ord(P mod p) | χ(A) χ(B) | χ-period");
    println!("  ----+--------------+-----------+----------");
    for p in [7u64, 11, 13, 17, 19, 23, 29, 31, 41, 43] {
        if let Some(br) = reduce_and_analyze(&w, p) {
            let j = br.chi_period / br.order.max(1);
            println!(
                "  {:>3} | {:>12} |  {:+} {:+}   | {}·r = {}",
                p, br.order, br.chi_a, br.chi_b, j, br.chi_period
            );
        }
    }
    println!(
        "\nThe real sign sequence is one fixed aperiodic object; the mod-p\n\
         χ-period jumps around with p (and is r vs 2r per the §3 multiplier\n\
         law). The two are orthogonal — the F_p χ-period is NOT the reduction\n\
         of the archimedean period.\n"
    );
}
