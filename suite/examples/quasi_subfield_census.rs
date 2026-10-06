//! Exhaustive census of quasi-subfield polynomials over `F_{2^n}`.
//!
//! Huang–Kosters–Petit–Yeo–Yun (J. Math. Cryptol. 2020) leave open
//! whether quasi-subfield polynomials exist with `deg λ` small enough to
//! beat generic algorithms, and single out whether the `n mod n0` term
//! in their Lemma 4.1 bound is needed.  This enumerates every monic
//! 2-linearised candidate at small `(n, n0)` and reports what splits.
//!
//! ```bash
//! cargo run --release --example quasi_subfield_census
//! ```

use cryptanalysis_suite::cryptanalysis::quasi_subfield::{census, format_census, max_j};

fn main() {
    println!("=== Quasi-subfield polynomial census over F_2^n ===");
    println!("A candidate is L(X) = X^(2^n0) + sum_{{i<=j_max}} c_i X^(2^i);");
    println!("it counts when it splits completely, i.e. kernel dim = n0.");
    println!("'expected' is the first-moment count 2^(bits - n0^2).");
    println!();
    let mut rows = 0;
    for n in 2u32..=17 {
        for n0 in 1u32..n {
            let Some(j_max) = max_j(n, n0) else { continue };
            let bits = (j_max + 1) * n;
            if bits > 26 {
                continue;
            }
            match census(n, n0, 3) {
                Some(c) => {
                    println!("{}", format_census(&c));
                    if let Some(w) = c.witnesses.first() {
                        if !w.is_subfield() {
                            println!(
                                "        smallest-j witness: lambda = {:?}  (j = {:?}, non-subfield)",
                                w.lambda, w.j
                            );
                        }
                    }
                    rows += 1;
                }
                None => continue,
            }
        }
    }
    println!();
    println!("{rows} cells enumerated exhaustively.");
}
