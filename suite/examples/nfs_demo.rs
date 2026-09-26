//! Number field sieve and quadratic sieve demonstrations at sizes too slow
//! for the unit tests.
//!
//! ```text
//! cargo run --release --example nfs_demo              # GNFS 40–55, SNFS 69–78, QS 40–60
//! cargo run --release --example nfs_demo -- gnfs      # one family: gnfs | snfs | qs | auto
//! cargo run --release --example nfs_demo -- all --big # adds GNFS at 60 digits (minutes)
//! cargo run --release --example nfs_demo -- gnfs --threads 4
//! ```
//!
//! Every row is a verified factorisation (`p·q = n` checked by the
//! library); the table shows where the time goes.  All numbers are fixed so
//! runs are comparable.  The semiprimes are products of two random primes
//! of half the size; the SNFS targets are the composite cofactors of
//! `(2^239 + 1)/3` (72 digits), `2^227 − 1` (69 digits) and
//! `(3^163 − 1)/2` (78 digits).

use cryptanalysis_suite::cryptanalysis::factoring::{
    factor, gnfs, qs, snfs, FactorOptions, GnfsParams, NfsReport, QsParams, SnfsInput, SnfsParams,
};
use num_bigint::BigUint;
use std::time::Instant;

/// `(digits, p, q)`.
const SEMIPRIMES: [(usize, &str, &str); 5] = [
    (40, "89680425071963186239", "27578836091457830909"),
    (45, "9452727658721031073001", "94110170590215287940431"),
    (50, "6537542554175184430787693", "8065339880728780970221351"),
    (
        55,
        "707710215016300972897826369",
        "6808621099719900081279941833",
    ),
    (
        60,
        "813254293423893417150294760099",
        "931126142320795990776475955723",
    ),
];

/// `(label, r, e, s, divide out)`: `n = (r^e + s) / small`.
const SNFS_TARGETS: [(&str, u64, u32, i64, u64); 3] = [
    ("(2^239+1)/3", 2, 239, 1, 3),
    ("2^227-1", 2, 227, -1, 1),
    ("(3^163-1)/2", 3, 163, -1, 2),
];

fn semiprime(p: &str, q: &str) -> BigUint {
    p.parse::<BigUint>().expect("p") * q.parse::<BigUint>().expect("q")
}

fn nfs_row(label: &str, r: &NfsReport) {
    println!(
        "| {} | {} | {} | {} | {:.1} | {:.1} | {:.1} | {:.1} | **{:.1}** | {} + {} | {}×{} | {} | {} |",
        r.method,
        label,
        r.digits,
        r.polynomial,
        r.polyselect_seconds,
        r.sieve_seconds,
        r.linalg_seconds,
        r.sqrt_seconds,
        r.total_seconds,
        r.full_relations,
        r.partial_relations,
        r.linalg.dense_rows,
        r.linalg.dense_cols,
        r.dependencies_tried,
        if r.verified {
            format!("{}", r.factor.as_ref().expect("verified"))
        } else {
            format!("FAILED: {}", r.failure.clone().unwrap_or_default())
        }
    );
}

fn nfs_header() {
    println!("| method | n | digits | f(x) | poly s | sieve s | linalg s | sqrt s | total s | full + partial rels | dense matrix | deps | factor |");
    println!("|---|---|---|---|---|---|---|---|---|---|---|---|---|");
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let which = args
        .iter()
        .find(|a| !a.starts_with("--") && a.parse::<usize>().is_err())
        .cloned()
        .unwrap_or_else(|| "all".into());
    let big = args.iter().any(|a| a == "--big");
    let threads = args
        .iter()
        .position(|a| a == "--threads")
        .and_then(|i| args.get(i + 1))
        .and_then(|t| t.parse().ok())
        .unwrap_or(1usize);
    let max_gnfs = if big { 60 } else { 55 };
    let run = |family: &str| which == "all" || which == family;

    if run("gnfs") {
        println!("\n### GNFS (base-m, degree 3, {threads} thread(s))\n");
        nfs_header();
        for &(d, p, q) in SEMIPRIMES.iter().filter(|s| s.0 <= max_gnfs) {
            let n = semiprime(p, q);
            let mut params = GnfsParams::default();
            params.nfs.threads = threads;
            let r = gnfs(&n, &params, None);
            nfs_row(&format!("{d}-digit semiprime"), &r);
        }
    }

    if run("snfs") {
        println!("\n### SNFS ({threads} thread(s))\n");
        nfs_header();
        for &(label, base, e, s, small) in &SNFS_TARGETS {
            let big_n = num_traits::pow(BigUint::from(base), e as usize);
            let full = if s > 0 {
                big_n + s as u64
            } else {
                big_n - s.unsigned_abs()
            };
            let n = full / small;
            let input = SnfsInput::Form {
                r: base,
                e,
                s,
                c: 1,
            };
            let mut params = SnfsParams::default();
            params.nfs.threads = threads;
            let r = snfs(&n, &input, &params, None);
            nfs_row(label, &r);
        }
    }

    if run("qs") {
        println!("\n### SIQS ({threads} thread(s))\n");
        println!("| n digits | factor base | M | polynomials | full + partial rels | dense matrix | sieve s | total s | factor |");
        println!("|---|---|---|---|---|---|---|---|---|");
        for &(d, p, q) in &SEMIPRIMES {
            let n = semiprime(p, q);
            let params = QsParams {
                threads,
                ..Default::default()
            };
            let r = qs(&n, &params, None);
            println!(
                "| {d} | {} | {} | {} | {} + {} | {}×{} | {:.1} | **{:.1}** | {} |",
                r.factor_base_size,
                r.sieve_half_width,
                r.polynomials,
                r.full_relations,
                r.partial_relations,
                r.linalg.dense_rows,
                r.linalg.dense_cols,
                r.sieve_seconds,
                r.total_seconds,
                r.factor
                    .as_ref()
                    .map(|f| f.to_string())
                    .unwrap_or_else(|| format!(
                        "FAILED: {}",
                        r.failure.clone().unwrap_or_default()
                    ))
            );
        }
    }

    if run("auto") {
        println!("\n### Full factorisation ladder\n");
        // 2^3 · 3^2 · 1000003^2 · (a 40-digit semiprime) · (2^61 − 1)
        let (_, p, q) = SEMIPRIMES[0];
        let n = BigUint::from(72u32)
            * BigUint::from(1_000_003u64 * 1_000_003u64)
            * semiprime(p, q)
            * ((BigUint::from(1u32) << 61) - 1u32);
        let t = Instant::now();
        let r = factor(&n, &FactorOptions::default());
        println!(
            "n = {n} ({} digits), {:.2} s, complete = {}, verified = {}",
            n.to_string().len(),
            t.elapsed().as_secs_f64(),
            r.complete,
            r.verified
        );
        for f in &r.factors {
            println!("  {}^{}  via {:?}", f.prime, f.exponent, f.method);
        }
    }
}
