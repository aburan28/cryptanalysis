//! **Pairs-and-solve against triple enumeration.**
//!
//! Deciding whether a target `x_R` decomposes over the factor base is
//! where an index-calculus run spends its time.  Three ways to do it,
//! measured side by side on the same targets:
//!
//! 1. **triples, general field** — walk all `2^{3l}/3!` sorted triples,
//!    evaluating the symmetrised `S₄` with the crate's `Vec`-backed
//!    `F2mElement`.  This is the baseline the SAT solver was measured
//!    against in `semaev_scaling`.
//! 2. **triples, one-word field** — the same walk with
//!    [`Gf2`](cryptanalysis_suite::cryptanalysis::semaev_decomp::Gf2), which
//!    holds an element of `F_{2ⁿ}`, `n ≤ 63`, in a single `u64`.
//!    Isolates the constant factor from the algorithmic change.
//! 3. **pairs-and-solve** — loop over `2^{2l}/2` *pairs* and solve the
//!    resulting quartic for the third point, keeping only roots inside
//!    the factor-base subspace via `gcd(q, L_V mod q)`.
//!
//! Targets are chosen not to decompose, so every method must exhaust
//! its space: no trajectory luck, and rejection is most of an attack's
//! work anyway.
//!
//! ```bash
//! cargo run --release --example semaev_decomp_bench        # to l = 9
//! cargo run --release --example semaev_decomp_bench 11     # to l = 11
//! ```

use cryptanalysis_suite::binary_ecc::{F2mElement, IrreduciblePoly};
use cryptanalysis_suite::cryptanalysis::binary_semaev_s4::{
    elementary_symmetric_3, symmetrised_s4_eval,
};
use cryptanalysis_suite::cryptanalysis::semaev_decomp::{decompose, eval_f3, Gf2};
use std::time::Instant;

// ── GF(2)[x] on bitmasks, to verify the moduli we pick ──────────────

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

/// Rabin's test.
fn is_irreducible(f: u64, n: u32) -> bool {
    let mut t = 2u64;
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

/// Smallest-weight irreducible polynomial of degree `n`: trinomials
/// first, then pentanomials.  Searched and Rabin-checked rather than
/// remembered, so no rung rests on an unverified table.
fn find_irreducible(n: u32) -> Vec<u32> {
    for k in 1..n {
        let f = (1u64 << n) | (1u64 << k) | 1;
        if is_irreducible(f, n) {
            return vec![0, k];
        }
    }
    for c in 1..n {
        for b in 1..c {
            for a in 1..b {
                let f = (1u64 << n) | (1u64 << c) | (1u64 << b) | (1u64 << a) | 1;
                if is_irreducible(f, n) {
                    return vec![0, a, b, c];
                }
            }
        }
    }
    panic!("no low-weight irreducible of degree {n}");
}

// ── the three methods ───────────────────────────────────────────────

fn elt(v: u64, l: u32, n: u32) -> F2mElement {
    let bits: Vec<u32> = (0..l).filter(|j| (v >> j) & 1 == 1).collect();
    F2mElement::from_bit_positions(&bits, n)
}

/// Method 1: every sorted triple, `Vec`-backed field.
fn triples_general(x_r: &F2mElement, l: u32, n: u32, irr: &IrreduciblePoly) -> bool {
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

/// Method 2: every sorted triple, one-word field.
fn triples_oneword(xr: u64, l: u32, gf: &Gf2) -> bool {
    let span = 1u64 << l;
    for a in 0..span {
        for b in a..span {
            for c in b..span {
                if eval_f3(a, b, c, xr, gf) == 0 {
                    return true;
                }
            }
        }
    }
    false
}

fn main() {
    let max_l: u32 = std::env::args()
        .nth(1)
        .and_then(|a| a.parse().ok())
        .unwrap_or(9);
    // Cut off the two slower methods once they stop being affordable.
    let general_cap: u32 = std::env::args()
        .nth(2)
        .and_then(|a| a.parse().ok())
        .unwrap_or(8);
    // Seconds to spend sampling random targets per rung.
    let sample_budget: f64 = std::env::args()
        .nth(3)
        .and_then(|a| a.parse().ok())
        .unwrap_or(20.0);

    println!("\n  finding and verifying moduli (Rabin):");
    let mut rungs = Vec::new();
    for l in 5..=max_l {
        let n = 3 * l; // n = 3l keeps the decomposition probability at 1/3!
        let low = find_irreducible(n);
        println!("    n = {n:<3} l = {l:<3} {low:?}");
        rungs.push((n, l, low));
    }

    println!("\n  ── deciding one target that does NOT decompose ──────────────────");
    println!(
        "  {:>3} {:>4} {:>14} {:>12} {:>12} {:>12} {:>9}",
        "l", "n", "triples", "triples/gen", "triples/1wd", "pairs+solve", "speedup"
    );

    let mut whole = Vec::new();
    for (n, l, low) in rungs {
        let irr = IrreduciblePoly {
            degree: n,
            low_terms: low.clone(),
        };
        let gf = Gf2::new(&irr);
        let span = 1u64 << l;
        let triples = span * (span + 1) * (span + 2) / 6;

        // A target that genuinely does not decompose — found with the
        // fast method, since at l ≥ 9 the slow ones cannot do the search.
        let mut chosen = None;
        let mut seed = 0x9E37_79B9u64;
        for _ in 0..32 {
            seed = seed.wrapping_mul(6364136223846793005).wrapping_add(1);
            let cand = seed & ((1u64 << n) - 1);
            if cand == 0 {
                continue;
            }
            if decompose(cand, l, &gf).is_none() {
                chosen = Some(cand);
                break;
            }
        }
        let Some(xr) = chosen else {
            println!("  l = {l}: no undecomposable target found — skipped");
            continue;
        };
        let x_r_elt = gf.to_element(xr);

        let gen = if l <= general_cap {
            let t = Instant::now();
            assert!(!triples_general(&x_r_elt, l, n, &irr));
            Some(t.elapsed().as_secs_f64())
        } else {
            None
        };

        let one = if l <= general_cap + 1 {
            let t = Instant::now();
            assert!(!triples_oneword(xr, l, &gf));
            Some(t.elapsed().as_secs_f64())
        } else {
            None
        };

        let t = Instant::now();
        assert!(decompose(xr, l, &gf).is_none());
        let pairs = t.elapsed().as_secs_f64();

        let fmt = |v: Option<f64>| match v {
            Some(s) => format!("{s:.3}s"),
            None => "—".to_string(),
        };
        let speedup = match one {
            Some(s) => format!("{:.1}x", s / pairs),
            None => "—".to_string(),
        };
        println!(
            "  {l:>3} {n:>4} {triples:>14} {:>12} {:>12} {:>12} {speedup:>9}",
            fmt(gen),
            fmt(one),
            format!("{pairs:.3}s"),
        );

        // ── what a relation-collection phase would actually cost ──────
        // Random targets, not the worst case: a target that decomposes
        // exits the pair loop early, and 1 in 3! of them do.
        let start = Instant::now();
        let (mut tried, mut hit) = (0u64, 0u64);
        while start.elapsed().as_secs_f64() < sample_budget && tried < 4000 {
            seed = seed.wrapping_mul(6364136223846793005).wrapping_add(1);
            let cand = seed & ((1u64 << n) - 1);
            if cand == 0 {
                continue;
            }
            if decompose(cand, l, &gf).is_some() {
                hit += 1;
            }
            tried += 1;
        }
        let per_target = start.elapsed().as_secs_f64() / tried as f64;
        let rate = hit as f64 / tried as f64;
        whole.push((n, l, tried, rate, per_target));
    }

    println!("\n  ── what that means for a whole run ─────────────────────────────");
    println!(
        "  {:>3} {:>4} {:>7} {:>10} {:>10} {:>12} {:>13} {:>10}",
        "l", "n", "samples", "decomp %", "1/3! = %", "s/target", "collection", "/ 2^n"
    );
    for (n, l, tried, rate, per_target) in whole {
        // A relation needs 1/rate targets; the linear algebra needs one
        // relation per factor-base element.
        let relations = (1u64 << l) as f64;
        let collection = relations / rate.max(1e-9) * per_target;
        println!(
            "  {l:>3} {n:>4} {tried:>7} {:>9.1}% {:>9.1}% {:>12.2e} {:>13} {:>10.2e}",
            rate * 100.0,
            100.0 / 6.0,
            per_target,
            format!("{:.1e}s", collection),
            collection / (1u64 << n) as f64,
        );
    }
    println!(
        "\n  The last column is the point.  Relation collection costs\n  \
         2^l relations x 3! tries x O(2^2l) per try = Theta(2^n),\n  \
         independent of l: a bigger factor base needs fewer tries but\n  \
         each try costs proportionally more.  Any enumeration oracle,\n  \
         however fast, sits at 2^n -- versus 2^(n/2) for Pollard rho.\n"
    );
}
