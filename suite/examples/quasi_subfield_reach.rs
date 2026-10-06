//! How far quasi-subfield polynomials reach over `F_{2^n}`.
//!
//! The exhaustive census (`quasi_subfield_census`) shows that over
//! `F_{2^n}` every quasi-subfield polynomial is accounted for by a
//! Frobenius-stable subspace, i.e. by a divisor of `t^n − 1` carrying
//! the required gap.  Testing divisors costs `2^{j_max+1}` trial
//! divisions instead of the census's `2^{(j_max+1)·n}` rank
//! computations, so this reaches field sizes of cryptographic interest.
//!
//! ```bash
//! cargo run --release --example quasi_subfield_reach
//! ```

use cryptanalysis_suite::cryptanalysis::quasi_subfield::{max_j, stable_candidates};

fn ord2(n: u32) -> u32 {
    let mut x = 1u64;
    for k in 1..=n {
        x = (x * 2) % n as u64;
        if x == 1 {
            return k;
        }
    }
    0
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let hi: u32 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(200);

    println!("=== Quasi-subfield reach over F_2^n, via divisors of t^n - 1 ===");
    println!("A cell is a hit when some divisor g of t^n - 1 of degree n0 has");
    println!("its second-highest term below n0^2/n.  Subfield hits (n0 | n) are");
    println!("marked, since those are the known, trivial case.");
    println!();

    let mut hits = 0usize;
    let mut nontrivial = 0usize;
    let mut prime_nontrivial: Vec<(u32, u32, u32)> = Vec::new();

    for n in (3u32..=hi).step_by(2) {
        let d = ord2(n);
        let mut row: Vec<String> = Vec::new();
        for n0 in 2..n {
            let Some(jm) = max_j(n, n0) else { continue };
            if jm >= 22 {
                continue;
            }
            let Some(cands) = stable_candidates(n, n0) else {
                continue;
            };
            let Some(best) = cands.first() else { continue };
            if (best.j as f64) >= (n0 as f64) * (n0 as f64) / (n as f64) {
                continue;
            }
            hits += 1;
            let sub = n % n0 == 0;
            if !sub {
                nontrivial += 1;
                if is_prime(n) {
                    prime_nontrivial.push((n, n0, best.j));
                }
            }
            row.push(format!(
                "n0={n0}(j={}{})",
                best.j,
                if sub { ",subfield" } else { "" }
            ));
        }
        if !row.is_empty() {
            println!("n={n:<4} ord_n(2)={d:<4} {}", row.join(" "));
        }
    }

    println!();
    println!("{hits} hits, of which {nontrivial} are not the subfield case.");
    println!();
    println!("Non-subfield hits at PRIME n (the Koblitz setting):");
    println!("  (g printed for the most useful cells, ratio n0/n < 0.2)");
    if prime_nontrivial.is_empty() {
        println!("  none in the range scanned.");
    } else {
        for (n, n0, j) in &prime_nontrivial {
            let ratio = (*n0 as f64) / (*n as f64);
            println!(
                "  n={n:<4} n0={n0:<4} j={j:<3} n0/n={ratio:.3}  ord_n(2)={}",
                ord2(*n)
            );
            if ratio < 0.2 {
                if let Some(cs) = stable_candidates(*n, *n0) {
                    for c in cs.iter().take(3) {
                        println!("        g = {:b}  (deg lambda = 2^{})", c.g, c.j);
                    }
                }
            }
        }
    }
}

fn is_prime(n: u32) -> bool {
    if n < 2 {
        return false;
    }
    let mut d = 2;
    while d * d <= n {
        if n.is_multiple_of(d) {
            return false;
        }
        d += 1;
    }
    true
}
