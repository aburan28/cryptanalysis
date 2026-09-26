//! What do the curve-independent summation polynomials cost to build?
//!
//! `semaev_leading_form::semaev(m)` returns S_{m+1} fully symbolically over
//! F_2[a6] -- it takes no curve parameters, so one build serves every curve in
//! the binary Koblitz family, with specialising a6 as the per-curve step.
//! Whether that is worth caching depends entirely on what it costs, which is
//! what this prints. Run each m under a timeout: the resultants grow fast.
use cryptanalysis_suite::cryptanalysis::semaev_leading_form::{semaev, NVARS};
use std::hint::black_box;
use std::time::Instant;

fn main() {
    let a: Vec<usize> = std::env::args()
        .skip(1)
        .filter_map(|x| x.parse().ok())
        .collect();
    let ms: Vec<usize> = if a.is_empty() { vec![2, 3] } else { a };
    println!(
        "{:>3} {:>6} {:>14} {:>12} {:>13} {:>13}   (NVARS={})",
        "m", "S_m+1", "build", "terms", "json payload", "stored ~2x", NVARS
    );
    for m in ms {
        if !(2..=5).contains(&m) {
            println!("{m:>3}   unsupported (semaev covers m in 2..=5)");
            continue;
        }
        let start = Instant::now();
        let p = black_box(semaev(m));
        let ns = start.elapsed().as_nanos();
        // What the artifact would weigh in the cache. `AlgebraCache` encodes
        // with serde_json and then wraps the payload as an escaped JSON string
        // inside the envelope, so the stored form is about twice the payload.
        let payload: usize = p
            .terms
            .iter()
            .map(|t| 2 + t.iter().map(|e| e.to_string().len() + 1).sum::<usize>())
            .sum::<usize>()
            + 2;
        // What the exponents actually look like decides the packing: a byte
        // per variable is the safe default, but if they are small and most
        // slots are unused, a tighter encoding buys headroom under the cap.
        let mut max_exp = 0u8;
        let mut used = [false; NVARS];
        for t in &p.terms {
            for (i, &e) in t.iter().enumerate() {
                if e > max_exp {
                    max_exp = e;
                }
                if e != 0 {
                    used[i] = true;
                }
            }
        }
        let live: Vec<usize> = (0..NVARS).filter(|&i| used[i]).collect();
        println!(
            "      max exponent {max_exp}, live slots {:?} of {NVARS}  \
             -> raw {:.2} MB at 1 byte/var, {:.2} MB over live slots only",
            live,
            p.terms.len() as f64 * NVARS as f64 / 1e6,
            p.terms.len() as f64 * live.len() as f64 / 1e6,
        );
        println!(
            "{:>3} {:>6} {:>11.2} ms {:>12} {:>10.2} MB {:>10.2} MB",
            m,
            format!("S_{}", m + 1),
            ns as f64 / 1e6,
            p.terms.len(),
            payload as f64 / 1e6,
            payload as f64 * 2.0 / 1e6,
        );
    }
}
