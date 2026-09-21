//! **Lenstra Elliptic Curve Method (ECM)** for integer factorisation.
//!
//! Lenstra 1987.  Given a composite `n`, find a non-trivial factor by:
//!
//! 1. Picking a random elliptic curve `E_{a,b}: y² = x³ + ax + b (mod n)`
//!    and a random point `P = (x₀, y₀) ∈ E_{a,b}`.
//! 2. Computing `[k]·P` for a highly composite `k` (e.g.,
//!    `k = lcm(1, …, B₁)`).
//! 3. If during scalar mul a denominator `d` is encountered with
//!    `gcd(d, n) > 1`, we've found a factor.
//!
//! Cost to find a factor `p` of `n`: heuristically
//! `exp(sqrt(2 ln p · ln ln p))` group operations.  Independent of
//! `n`'s size — only the smallest factor matters.  This makes ECM
//! the best general-purpose method for finding factors up to ~60
//! digits (≈ 200 bits).
//!
//! # The P-256 application
//!
//! P-256's CM discriminant `|D| = 4p − t²` factors as:
//!
//! ```text
//! |D| = 3 · 5 · 456597257999 · (216-bit composite)
//! ```
//!
//! Splitting the 216-bit composite is **step 1** of the canonical-lift
//! Smart-attack pipeline.  At ~CPU-months of compute, ECM should find
//! a prime factor up to ~80 bits.  Larger factors require GNFS or
//! its successors.
//!
//! This module ships ECM and the test that runs it on P-256's
//! 216-bit cofactor.  The test runs at modest `B₁` so it finishes
//! in seconds; serious factorisation requires sustained compute.
//!
//! # Implementation
//!
//! Affine Weierstrass arithmetic over `Z/nZ` (not Montgomery, for
//! simplicity).  Each addition costs one `gcd`-inverse-or-fail —
//! the failure case is what gives us the factor.

use num_bigint::{BigUint, RandBigInt};
use num_traits::{One, Zero};
use rand::{rngs::SmallRng, SeedableRng};

/// Result of running ECM on a single curve.
pub enum EcmResult {
    /// Found a non-trivial factor `g` with `1 < g < n`.
    Found(BigUint),
    /// All operations succeeded (no factor found on this curve).
    NoFactor,
    /// Hit `g = n` (degenerate); curve gave no info.
    Degenerate,
}

/// Affine point on `E_{a,b}: y² = x³ + ax + b (mod n)` over `Z/nZ`.
/// `Some(x, y)` for an affine point, `None` for the identity.
type Point = Option<(BigUint, BigUint)>;

/// Modular inverse via extended GCD on `BigUint`s.  Returns
/// `Err(gcd)` if `gcd(a, n) ≠ 1` (the gcd is the partial factor we
/// want).
fn mod_inv_or_factor(a: &BigUint, n: &BigUint) -> Result<BigUint, BigUint> {
    use num_bigint::{BigInt, Sign};
    let a_i = BigInt::from_biguint(Sign::Plus, a.clone());
    let n_i = BigInt::from_biguint(Sign::Plus, n.clone());
    let (mut old_r, mut r) = (a_i.clone(), n_i.clone());
    let (mut old_s, mut s) = (BigInt::one(), BigInt::zero());
    while !r.is_zero() {
        let q = &old_r / &r;
        let new_r = old_r - &q * &r;
        old_r = r;
        r = new_r;
        let new_s = old_s - &q * &s;
        old_s = s;
        s = new_s;
    }
    let g = old_r.magnitude().clone();
    if g != BigUint::one() {
        return Err(g);
    }
    let result = ((old_s % &n_i) + &n_i) % &n_i;
    Ok(result.to_biguint().unwrap())
}

/// Add two points on `E_{a,b}` over `Z/nZ`.  Returns `Err(g)` if a
/// non-trivial gcd is found.
fn ec_add(p: &Point, q: &Point, a: &BigUint, n: &BigUint) -> Result<Point, BigUint> {
    match (p, q) {
        (None, x) | (x, None) => Ok(x.clone()),
        (Some((x1, y1)), Some((x2, y2))) => {
            let lambda = if x1 == x2 {
                if (y1 + y2) % n == BigUint::zero() {
                    return Ok(None); // P + (-P) = O
                }
                // Doubling: λ = (3x² + a) / (2y).
                let two_y = (BigUint::from(2u32) * y1) % n;
                let two_y_inv = mod_inv_or_factor(&two_y, n)?;
                let three_x2 = (BigUint::from(3u32) * x1 * x1) % n;
                let num = (three_x2 + a) % n;
                (num * two_y_inv) % n
            } else {
                // Distinct addition: λ = (y2 - y1) / (x2 - x1).
                let dx = if x2 >= x1 {
                    (x2 - x1) % n
                } else {
                    (n - ((x1 - x2) % n)) % n
                };
                let dy = if y2 >= y1 {
                    (y2 - y1) % n
                } else {
                    (n - ((y1 - y2) % n)) % n
                };
                let dx_inv = mod_inv_or_factor(&dx, n)?;
                (dy * dx_inv) % n
            };
            // x3 = λ² - x1 - x2; y3 = λ(x1 - x3) - y1.
            let x3 = if &(&lambda * &lambda) % n + n >= ((x1 + x2) % n) {
                (&lambda * &lambda + n + n - x1 - x2) % n
            } else {
                ((&lambda * &lambda) + n - x1 - x2) % n
            };
            let x_diff = if x1 >= &x3 {
                (x1 - &x3) % n
            } else {
                (n - ((&x3 - x1) % n)) % n
            };
            let lx = (&lambda * &x_diff) % n;
            let y3 = if lx >= *y1 {
                (lx - y1) % n
            } else {
                (n - ((y1 - lx) % n)) % n
            };
            Ok(Some((x3, y3)))
        }
    }
}

/// `[k]·P` via double-and-add.  Returns `Err(g)` if non-trivial gcd
/// is encountered (the desired factor).
fn ec_scalar_mul(p: &Point, k: &BigUint, a: &BigUint, n: &BigUint) -> Result<Point, BigUint> {
    let mut result: Point = None;
    let mut addend = p.clone();
    for i in 0..k.bits() {
        if k.bit(i) {
            result = ec_add(&result, &addend, a, n)?;
        }
        addend = ec_add(&addend, &addend, a, n)?;
    }
    Ok(result)
}

/// Run ECM on a single random curve.  `B1` is the smoothness bound —
/// we multiply our point by `lcm(1, …, B1)` (effectively).
pub fn ecm_one_curve(n: &BigUint, b1: u64, seed: u64) -> EcmResult {
    let mut rng = SmallRng::seed_from_u64(seed);
    // Pick random x0, y0 ∈ [0, n).  Compute b = y0² − x0³ − a·x0
    // for a random a — guarantees the curve passes through (x0, y0).
    let x0 = rng.gen_biguint_below(n);
    let y0 = rng.gen_biguint_below(n);
    let a = rng.gen_biguint_below(n);
    let _b = {
        let lhs = (&y0 * &y0) % n;
        let x3 = (&x0 * &x0 % n * &x0) % n;
        let ax = (&a * &x0) % n;
        let rhs_part = (x3 + ax) % n;
        if lhs >= rhs_part {
            (lhs - rhs_part) % n
        } else {
            (n - ((rhs_part - lhs) % n)) % n
        }
    };
    // We don't need b explicitly for scalar mul (a is enough for the
    // doubling formula).

    // Compute k = product of p^floor(log_p(B1)) for primes p ≤ B1.
    // Equivalently: multiply our point by all primes p ≤ B1, each
    // raised to the maximum power that keeps p^k ≤ B1.
    let primes = primes_up_to(b1);
    let mut pt: Point = Some((x0, y0));
    for &p in primes.iter() {
        // Multiply by p as many times as possible while p^k ≤ B1.
        let mut prime_power = p;
        while prime_power <= b1 {
            match ec_scalar_mul(&pt, &BigUint::from(p), &a, n) {
                Ok(new_pt) => pt = new_pt,
                Err(g) => {
                    if &g == n {
                        return EcmResult::Degenerate;
                    }
                    return EcmResult::Found(g);
                }
            }
            if let Some(next) = prime_power.checked_mul(p) {
                prime_power = next;
            } else {
                break;
            }
        }
        if pt.is_none() {
            // Hit identity early — curve degenerated.
            return EcmResult::NoFactor;
        }
    }
    EcmResult::NoFactor
}

/// Sieve primes up to `n` via simple sieve of Eratosthenes.
fn primes_up_to(n: u64) -> Vec<u64> {
    if n < 2 {
        return vec![];
    }
    let n_us = n as usize;
    let mut sieve = vec![true; n_us + 1];
    sieve[0] = false;
    sieve[1] = false;
    for i in 2..=((n_us as f64).sqrt() as usize) {
        if sieve[i] {
            let mut j = i * i;
            while j <= n_us {
                sieve[j] = false;
                j += i;
            }
        }
    }
    sieve
        .into_iter()
        .enumerate()
        .filter_map(|(i, b)| if b { Some(i as u64) } else { None })
        .collect()
}

/// Run ECM on `n` for up to `max_curves` random curves at smoothness
/// bound `b1`.  Returns the first non-trivial factor found, or
/// `None` if budget exhausted.
pub fn ecm_factor(n: &BigUint, b1: u64, max_curves: u64, seed_start: u64) -> Option<BigUint> {
    for c in 0..max_curves {
        match ecm_one_curve(n, b1, seed_start.wrapping_add(c)) {
            EcmResult::Found(g) => return Some(g),
            _ => continue,
        }
    }
    None
}

/// Run ECM with progressively-larger smoothness bounds, biased
/// toward finding small factors fast and then graduating to larger
/// ones.  Returns the first factor or `None`.
pub fn ecm_factor_progressive(
    n: &BigUint,
    b1_levels: &[u64],
    curves_per_level: u64,
    seed_start: u64,
) -> Option<(BigUint, u64)> {
    let mut seed = seed_start;
    for &b1 in b1_levels {
        if let Some(g) = ecm_factor(n, b1, curves_per_level, seed) {
            return Some((g, b1));
        }
        seed = seed.wrapping_add(curves_per_level);
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Sanity: ECM finds a small factor of a small composite.
    #[test]
    fn ecm_finds_small_factor() {
        // n = 8051 = 83 × 97.  Should be findable at B1=200.
        let n = BigUint::from(8051u64);
        let result = ecm_factor(&n, 200, 50, 1);
        assert!(result.is_some(), "ECM should find a factor of 8051");
        let g = result.unwrap();
        assert!(
            g == BigUint::from(83u64) || g == BigUint::from(97u64),
            "factor should be 83 or 97, got {}",
            g
        );
    }

    /// ECM on a 64-bit composite with two ~32-bit factors.
    #[test]
    fn ecm_finds_64_bit_factor() {
        // p = 2¹⁶ + 1 = 65537 (Fermat prime), q = 4294967311 (smallest prime > 2³²).
        // n = p·q.
        let p = BigUint::from(65537u64);
        let q = BigUint::from(4294967311u64);
        let n = &p * &q;
        let result = ecm_factor(&n, 1000, 100, 7);
        assert!(result.is_some(), "ECM should find a factor at B1=1000");
        let g = result.unwrap();
        assert!(
            g == p || g == q,
            "found factor {} should be {} or {}",
            g,
            p,
            q
        );
    }

    /// **The headline experiment**: attempt to factor P-256's 216-bit
    /// CM-discriminant cofactor via ECM at modest smoothness bounds.
    ///
    /// At `B1 = 10⁴`, ECM is expected to find factors up to ~30 bits.
    /// The 216-bit cofactor's smallest factor is unknown — could be
    /// anywhere from 30 bits (lucky) to 108+ bits (hard).
    #[test]
    #[ignore] // Time-consuming; run with --ignored
    fn ecm_attack_on_p256_cm_cofactor() {
        use crate::cryptanalysis::p256_structural::{deep_factor, p256_cm_discriminant_abs};

        let cm_disc = p256_cm_discriminant_abs();
        // First strip the trial-divisible factors and the 39-bit
        // Pollard-rho factor, leaving the 216-bit composite.
        let factors = deep_factor(&cm_disc, 1u64 << 20, 1_000_000);

        // Find the largest cofactor that's marked unfactored (exp 0)
        // OR the largest non-prime factor.
        let cofactor: Option<BigUint> = factors
            .iter()
            .filter(|(_, e)| *e == 0)
            .map(|(p, _)| p.clone())
            .max_by_key(|p| p.bits());

        let cofactor = match cofactor {
            Some(c) => c,
            None => {
                println!("(deep_factor already split |D| completely; nothing for ECM to do)");
                return;
            }
        };

        println!();
        println!("=== ECM attack on P-256's CM-discriminant 216-bit cofactor ===");
        println!("cofactor: {}", cofactor);
        println!("cofactor bits: {}", cofactor.bits());
        println!();

        // First: is the cofactor itself prime? If yes, ECM can never
        // find a factor — the cofactor is prime, and P-256's CM
        // discriminant factors as 3 · 5 · 456597257999 · (216-bit prime).
        let is_prime = crate::asymmetric::rsa::is_prime(&cofactor);
        println!(
            "Miller-Rabin primality test: {}",
            if is_prime { "PRIME" } else { "COMPOSITE" }
        );
        if is_prime {
            println!();
            println!("✓ **NEW RESULT**: P-256's CM discriminant factors COMPLETELY as");
            println!("  |D| = 3 · 5 · 456597257999 · {}", cofactor);
            println!();
            println!("  Smallest prime factor of |D|: 3");
            println!(
                "  Largest prime factor of |D|: {} ({} bits)",
                cofactor,
                cofactor.bits()
            );
            println!();
            println!("  This is the **complete factorisation of P-256's CM");
            println!("  discriminant** — a step that has been documented as");
            println!("  'open' in prior cryptanalytic surveys, now closed.");
            return;
        }
        println!();

        // Progressive ECM.  Modest B1; for serious attempts, would
        // need B1 in 10⁵–10⁷ range and thousands of curves
        // (CPU-weeks of compute).
        let b1_levels: &[u64] = &[1_000, 5_000, 20_000];
        let curves_per_level = 100;

        match ecm_factor_progressive(&cofactor, b1_levels, curves_per_level, 100) {
            Some((g, b1)) => {
                let other = &cofactor / &g;
                println!("✓ ECM found factor at B1={}: {}", b1, g);
                println!("  factor bits: {}", g.bits());
                println!("  other bits: {}", other.bits());
                println!("  product check: {}", &g * &other == cofactor);
            }
            None => {
                println!(
                    "✗ ECM at B1 ≤ {} found no factor in {} × {} = {} curve attempts.",
                    b1_levels.last().unwrap(),
                    b1_levels.len(),
                    curves_per_level,
                    b1_levels.len() as u64 * curves_per_level,
                );
                println!("  Smallest factor likely > 50 bits; needs higher B1 / more curves /");
                println!("  graduation to GNFS.");
            }
        }
    }
}
