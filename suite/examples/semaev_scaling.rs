//! **Does the solver start pruning as the factor base grows?**
//!
//! At `l = 5, 6` it spends almost exactly one conflict per candidate
//! factor-base triple — it walks the space rather than cutting it down,
//! and loses to direct evaluation by ~7× (see `semaev_unsat`).
//!
//! That only matters if it stays true.  Enumeration costs `2^{3l}/3!`
//! and becomes hopeless around `l = 12`; if `conflicts/triple` falls
//! away as `l` grows there is a crossover worth finding, and if it does
//! not, this route does not scale and no amount of solver tuning
//! changes that.  This walks the ladder and reports the ratio.
//!
//! Rejection (unsatisfiable) instances are used throughout: proving
//! unsatisfiability means exhausting the space, so there is no
//! trajectory luck, and rejection is most of an attack's work anyway.
//!
//! Reports the SAT solver against the baseline it has to beat —
//! evaluating the symmetrised `S₄` at every sorted triple — at each
//! rung, so the two scale side by side.
//!
//! ```bash
//! cargo run --release --example semaev_scaling            # to l = 8
//! cargo run --release --example semaev_scaling 60000000 6 # stop at l = 6
//! ```
//!
//! The `l = 8` rung takes about 25 minutes.

use cryptanalysis_suite::binary_ecc::{F2mElement, IrreduciblePoly};
use cryptanalysis_suite::cryptanalysis::binary_semaev_s4::{
    elementary_symmetric_3, symmetrised_s4_eval,
};
use cryptanalysis_suite::cryptanalysis::sat::SolveResult;
use cryptanalysis_suite::cryptanalysis::semaev_sat::{
    encode_semaev_s4_with, S4Options, XorEncoding,
};
use std::time::Instant;

// ── GF(2)[x] on bitmasks, for verifying the moduli ──────────────────
// Bit k is the coefficient of x^k.  Only used to check that each
// tabulated polynomial really is irreducible — trusting a remembered
// table would put the whole ladder on an unverified footing.

fn poly_deg(a: u64) -> i32 {
    63 - a.leading_zeros() as i32
}

fn poly_mulmod(mut a: u64, mut b: u64, f: u64, n: u32) -> u64 {
    let mut r = 0u64;
    while b != 0 {
        if b & 1 == 1 {
            r ^= a;
        }
        b >>= 1;
        a <<= 1;
        if (a >> n) & 1 == 1 {
            a ^= f;
        }
    }
    r
}

fn poly_gcd(mut a: u64, mut b: u64) -> u64 {
    while b != 0 {
        let db = poly_deg(b);
        while a != 0 && poly_deg(a) >= db {
            a ^= b << (poly_deg(a) - db);
        }
        std::mem::swap(&mut a, &mut b);
    }
    a
}

fn prime_factors(mut n: u32) -> Vec<u32> {
    let mut out = Vec::new();
    let mut p = 2;
    while p * p <= n {
        if n.is_multiple_of(p) {
            out.push(p);
            while n.is_multiple_of(p) {
                n /= p;
            }
        }
        p += 1;
    }
    if n > 1 {
        out.push(n);
    }
    out
}

/// Rabin's test: `f` of degree `n` is irreducible over GF(2) iff
/// `x^(2^n) ≡ x (mod f)` and `gcd(x^(2^(n/p)) − x, f) = 1` for every
/// prime `p | n`.
fn is_irreducible(f: u64, n: u32) -> bool {
    let mut t = 2u64; // x
    for _ in 0..n {
        t = poly_mulmod(t, t, f, n);
    }
    if t != 2 {
        return false;
    }
    for p in prime_factors(n) {
        let mut t = 2u64;
        for _ in 0..(n / p) {
            t = poly_mulmod(t, t, f, n);
        }
        if poly_gcd(t ^ 2, f) != 1 {
            return false;
        }
    }
    true
}

fn irr_bits(low: &[u32], n: u32) -> u64 {
    low.iter().fold(1u64 << n, |acc, &t| acc | (1u64 << t))
}

// ── the ladder ──────────────────────────────────────────────────────

/// `(n, l, low_terms)` with `n ≈ 3l`, so the decomposition probability
/// stays near `1/3!` as the factor base grows.
const LADDER: &[(u32, u32, &[u32])] = &[
    (15, 5, &[0, 2, 4, 5]),
    (19, 6, &[0, 1, 2, 5]),
    (21, 7, &[0, 2]),
    (24, 8, &[0, 1, 3, 4]),
];

fn elt(v: u64, l: u32, n: u32) -> F2mElement {
    let bits: Vec<u32> = (0..l).filter(|j| (v >> j) & 1 == 1).collect();
    F2mElement::from_bit_positions(&bits, n)
}

/// Exhaustively decide whether `x_r` decomposes over the factor base.
/// Sorted triples suffice: the symmetrised `f₃` is symmetric.
fn decomposes(x_r: &F2mElement, l: u32, n: u32, irr: &IrreduciblePoly) -> bool {
    let span = 1u64 << l;
    let base: Vec<F2mElement> = (0..span).map(|v| elt(v, l, n)).collect();
    for a in 0..span as usize {
        for b in a..span as usize {
            for c in b..span as usize {
                let (e1, e2, e3) = elementary_symmetric_3(&base[a], &base[b], &base[c], irr);
                if symmetrised_s4_eval(&e1, &e2, &e3, x_r, irr).is_zero() {
                    return true;
                }
            }
        }
    }
    false
}

fn main() {
    let budget: u64 = std::env::args()
        .nth(1)
        .and_then(|a| a.parse().ok())
        .unwrap_or(60_000_000);

    println!("\n  verifying the moduli are irreducible (Rabin):");
    for &(n, _, low) in LADDER {
        let f = irr_bits(low, n);
        let ok = is_irreducible(f, n);
        println!(
            "    n = {n:<3} {:<24} {}",
            format!("{low:?}"),
            if ok {
                "irreducible"
            } else {
                "REDUCIBLE — unusable"
            }
        );
        assert!(ok, "modulus for n = {n} is not irreducible");
    }

    let max_l: u32 = std::env::args()
        .nth(2)
        .and_then(|a| a.parse().ok())
        .unwrap_or(8);
    println!(
        "\n  {:<8} {:>3} {:>10} {:>12} {:>10} {:>12} {:>12} {:>8}",
        "params", "l", "triples", "conflicts", "confl/tri", "SAT reject", "brute force", "ratio"
    );
    for &(n, l, low) in LADDER {
        if l > max_l {
            continue;
        }
        let irr = IrreduciblePoly {
            degree: n,
            low_terms: low.to_vec(),
        };
        let span = 1u64 << l;
        let triples = span * (span + 1) * (span + 2) / 6;

        // Find a target that genuinely does not decompose.  ~5/6 of
        // random targets qualify, so this rarely needs a second try.
        let mut x_r = None;
        let mut seed = 0x9E37_79B9u64;
        for _ in 0..8 {
            seed = seed.wrapping_mul(6364136223846793005).wrapping_add(1);
            let bits: Vec<u32> = (0..n).filter(|j| (seed >> j) & 1 == 1).collect();
            let cand = F2mElement::from_bit_positions(&bits, n);
            if cand.is_zero() {
                continue;
            }
            if !decomposes(&cand, l, n, &irr) {
                x_r = Some(cand);
                break;
            }
        }
        let Some(x_r) = x_r else {
            println!("  n={n:<8} {l:>3}  no undecomposable target found — skipped");
            continue;
        };

        // The baseline: walk every sorted triple and evaluate.
        let t = Instant::now();
        assert!(!decomposes(&x_r, l, n, &irr));
        let brute = t.elapsed().as_secs_f64();

        let b = F2mElement::one(n);
        let mut enc = encode_semaev_s4_with(
            n,
            l,
            &irr,
            &b,
            &x_r,
            S4Options {
                encoding: XorEncoding::Native,
                break_symmetry: true,
            },
        );
        enc.solver.conflict_budget = budget;
        let t = Instant::now();
        let res = enc.solver.solve();
        let secs = t.elapsed().as_secs_f64();
        let conflicts = enc.solver.stats.conflicts;

        match res {
            SolveResult::Unsat => println!(
                "  n={n:<8} {l:>3} {triples:>10} {conflicts:>12} {:>10.2} {:>11.1}s {:>11.2}s {:>7.1}×",
                conflicts as f64 / triples as f64,
                secs,
                brute,
                secs / brute
            ),
            SolveResult::Sat => println!("  n={n:<8} {l:>3}  SAT — target check disagrees!"),
            SolveResult::Unknown => println!(
                "  n={n:<8} {l:>3} {triples:>10} {conflicts:>12} {:>10} {:>11.1}s {:>11.2}s  (budget)",
                "≥", secs, brute
            ),
        }
    }
    println!(
        "\n  A ratio holding at ~1 means the solver walks the whole\n  \
         candidate space.  A ratio falling with l means it prunes.\n"
    );
}
