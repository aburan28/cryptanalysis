//! **P-256 `b`-coefficient deep statistical profiling.**
//!
//! P-256's `b` constant (FIPS 186-4 §D.1.2.3):
//!
//! ```text
//! b = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
//! ```
//!
//! NIST claims `b` was generated via SHA-1 on a "verifiably random" seed,
//! but the seed-to-b relationship has not been re-verified at high
//! statistical resolution.  The agent's TOP-3 list flags the deep
//! profile of `b mod q` over many primes `q` as an underexplored angle:
//! **if `b` were chosen with malice, residues `b mod q` might exhibit
//! anomalous structure detectable by Kolmogorov-Smirnov goodness-of-fit
//! tests.**
//!
//! # Methodology
//!
//! 1. Sieve primes `q ≤ Q` (we use `Q = 10⁶` for ~78,498 primes; a
//!    serious analysis at `Q = 10⁸` would require ~hours of compute).
//! 2. For each prime `q`, compute `r_q = (b mod q) / q ∈ [0, 1)`.
//! 3. Test the empirical distribution of `{r_q}` against `Uniform[0, 1)`
//!    via the Kolmogorov-Smirnov test.
//! 4. Compute the KS statistic
//!    `D_n = sup_{x ∈ [0,1]} |F_n(x) − x|`
//!    and the corresponding `p`-value via the Kolmogorov distribution.
//! 5. Compare to threshold (typically `p < 0.001` would constitute a
//!    research-grade flag).
//!
//! # Honest expected outcome
//!
//! Under the null hypothesis that `b` is "random" (in the sense that
//! its residues mod various primes are uniform), the KS statistic
//! should be close to its expected value `~1/√n` and the `p`-value
//! should be uniform.  Any significant deviation would be a
//! research-grade finding.
//!
//! Per agent surveys, this test has not been published at the resolution
//! we run it (10⁶ primes).  It's the kind of "obvious" statistical
//! check that's often skipped because it's expected to come up null.
//! Our job: actually do it.

use num_bigint::BigUint;

/// P-256's `b` parameter.
fn p256_b() -> BigUint {
    BigUint::parse_bytes(
        b"5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B",
        16,
    )
    .unwrap()
}

/// Sieve of Eratosthenes returning primes ≤ `bound`.
fn primes_up_to(bound: u64) -> Vec<u64> {
    if bound < 2 {
        return vec![];
    }
    let n = bound as usize;
    let mut sieve = vec![true; n + 1];
    sieve[0] = false;
    sieve[1] = false;
    let mut i = 2;
    while (i * i) <= n {
        if sieve[i] {
            let mut j = i * i;
            while j <= n {
                sieve[j] = false;
                j += i;
            }
        }
        i += 1;
    }
    sieve
        .iter()
        .enumerate()
        .filter_map(|(k, &b)| if b { Some(k as u64) } else { None })
        .collect()
}

/// Compute `(b mod q) / q ∈ [0, 1)` for each prime `q`.  Returns
/// the residue ratios.
pub fn compute_b_residue_ratios(b: &BigUint, primes: &[u64]) -> Vec<f64> {
    primes
        .iter()
        .map(|&q| {
            let r = b % BigUint::from(q);
            // r is small (< q), can convert to u64.
            let r_u64: u64 = r.iter_u64_digits().next().unwrap_or(0);
            r_u64 as f64 / q as f64
        })
        .collect()
}

/// Kolmogorov-Smirnov D-statistic against `Uniform[0, 1)`.
pub fn ks_statistic_uniform(samples: &[f64]) -> f64 {
    let mut sorted: Vec<f64> = samples.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let n = sorted.len() as f64;
    let mut max_d: f64 = 0.0;
    for (i, &x) in sorted.iter().enumerate() {
        let f_n_lower = i as f64 / n;
        let f_n_upper = (i + 1) as f64 / n;
        let d_lower = (f_n_lower - x).abs();
        let d_upper = (f_n_upper - x).abs();
        max_d = max_d.max(d_lower).max(d_upper);
    }
    max_d
}

/// Kolmogorov distribution survival function `Pr[D > d]` for sample
/// size `n`.  Uses the asymptotic formula:
///
/// ```text
/// Pr[√n · D > t] ≈ 2 · Σ_{k=1}^∞ (-1)^{k-1} · exp(-2 k² t²)
/// ```
///
/// For large `n`, this converges fast.  A NaN statistic gives `0`.
pub fn ks_pvalue(d: f64, n: usize) -> f64 {
    let t = (n as f64).sqrt() * d;
    if t == 0.0 {
        return 1.0;
    }
    let mut sum = 0.0f64;
    for k in 1..200 {
        let term = ((-1f64).powi(k - 1)) * (-2.0 * (k as f64).powi(2) * t * t).exp();
        sum += term;
        if term.abs() < 1e-15 {
            break;
        }
    }
    let p = 2.0 * sum;
    // `clamp` alone would keep a NaN; a NaN statistic reads as p = 0.
    if p.is_nan() {
        0.0
    } else {
        p.clamp(0.0, 1.0)
    }
}

/// Run the deep profile: sieve primes, compute `b mod q` ratios,
/// KS-test against uniform.
pub struct BSeedProfileResult {
    pub n_primes: usize,
    pub max_prime: u64,
    pub ks_statistic: f64,
    pub ks_pvalue: f64,
    /// Number of residues in each of 10 deciles: `[0, 0.1), [0.1, 0.2), …`
    /// Should be roughly equal under uniform null.
    pub decile_counts: [u64; 10],
}

pub fn run_b_seed_profile(prime_bound: u64) -> BSeedProfileResult {
    let b = p256_b();
    let primes = primes_up_to(prime_bound);
    // Skip primes 2 and 3 (b mod q for very small q dominates the
    // KS statistic by discreteness; the interesting analysis is at
    // larger primes).
    let primes: Vec<u64> = primes.into_iter().filter(|&p| p >= 5).collect();
    let max_prime = *primes.last().unwrap_or(&0);
    let ratios = compute_b_residue_ratios(&b, &primes);
    let ks = ks_statistic_uniform(&ratios);
    let pval = ks_pvalue(ks, ratios.len());

    let mut decile_counts = [0u64; 10];
    for &r in &ratios {
        let bucket = ((r * 10.0) as usize).min(9);
        decile_counts[bucket] += 1;
    }

    BSeedProfileResult {
        n_primes: primes.len(),
        max_prime,
        ks_statistic: ks,
        ks_pvalue: pval,
        decile_counts,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Sanity: the KS test on uniform samples should give p ≈ uniform.
    #[test]
    fn ks_test_passes_under_null() {
        // 10,000 evenly-spaced points in [0, 1) — very-uniform sample.
        let samples: Vec<f64> = (0..10_000).map(|i| (i as f64 + 0.5) / 10_000.0).collect();
        let d = ks_statistic_uniform(&samples);
        let p = ks_pvalue(d, samples.len());
        assert!(
            d < 0.001,
            "evenly-spaced samples should have tiny D, got {}",
            d
        );
        assert!(
            p > 0.99,
            "p-value should be high for uniform-looking samples, got {}",
            p
        );
    }

    /// Sanity: clearly non-uniform sample should give low p-value.
    #[test]
    fn ks_test_rejects_under_alternative() {
        // Sample biased toward 0: cubic distribution F(x) = x³.
        let samples: Vec<f64> = (1..=1000).map(|i| (i as f64 / 1000.0).powi(3)).collect();
        let d = ks_statistic_uniform(&samples);
        let p = ks_pvalue(d, samples.len());
        assert!(d > 0.1, "skewed samples should have large D, got {}", d);
        assert!(
            p < 0.001,
            "p-value should be tiny for non-uniform samples, got {}",
            p
        );
    }

    /// **The headline experiment**: deep profile of P-256's `b` against
    /// the uniform-mod-q hypothesis.
    #[test]
    fn p256_b_seed_deep_profile() {
        // Use Q = 100,000 for CI speed; a research-grade run would
        // use Q = 10⁶ or 10⁸ (latter requires ~hours of compute).
        let prime_bound = 100_000u64;
        let result = run_b_seed_profile(prime_bound);

        println!();
        println!("=== P-256 `b`-seed Deep Statistical Profile ===");
        println!();
        println!("b = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B");
        println!();
        println!("Prime bound: q ≤ {}", prime_bound);
        println!("Number of primes tested: {}", result.n_primes);
        println!("Largest prime used: {}", result.max_prime);
        println!();
        println!(
            "KS statistic vs Uniform[0, 1):  D = {:.6}",
            result.ks_statistic
        );
        println!(
            "KS p-value:                     p = {:.4}",
            result.ks_pvalue
        );
        println!();
        println!(
            "Decile counts (expected ≈ {}/10 = {} each):",
            result.n_primes,
            result.n_primes / 10
        );
        for k in 0..10 {
            let lo = k as f64 / 10.0;
            let hi = (k + 1) as f64 / 10.0;
            println!("  [{:.1}, {:.1}): {:>6}", lo, hi, result.decile_counts[k]);
        }
        println!();
        if result.ks_pvalue < 0.001 {
            println!("⚠ p-value < 0.001 — POTENTIALLY ANOMALOUS.");
            println!("  Recommend re-running at higher prime_bound for confirmation.");
        } else {
            println!("✓ p-value ≥ 0.001 — `b` residues consistent with uniform.");
            println!("  No structural anomaly in P-256's `b` constant detected.");
        }

        // Sanity: KS statistic is small under null hypothesis.
        // For n = 10K samples, D should be < 0.05 for almost any
        // uniformly-distributed sample.
        assert!(result.ks_statistic < 0.05);
    }
}
