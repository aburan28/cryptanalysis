//! Statistical distinguishers for cipher / hash output.
//!
//! These are the classic NIST-style randomness tests, scoped to the
//! cryptanalysis use-case: given a candidate cipher / hash / PRF, run
//! it on many varying inputs, concatenate the outputs into a bit
//! stream, and check whether the stream is statistically
//! distinguishable from uniform.  A failed test is strong evidence
//! the primitive is broken; a passed test is weak evidence it is
//! sound (lots of broken designs pass these).
//!
//! Three tests covered:
//!
//! 1. [`monobit_test`] — Frequency (monobit): equal counts of 0s and
//!    1s.  Fails any cipher with a constant or near-constant output
//!    bit.
//! 2. [`runs_test`] — Runs: number of runs of consecutive equal bits.
//!    Fails ciphers whose output bits are positively or negatively
//!    autocorrelated.
//! 3. [`chi_squared_byte_test`] — chi-squared over the byte
//!    distribution.  Fails ciphers with biased byte frequencies.
//!
//! All three return a small report struct including the p-value
//! (where well-defined) and a pass/fail decision at significance
//! level α = 0.01.

/// Report from [`chi_squared_byte_test`].
#[derive(Clone, Debug)]
pub struct ChiSquaredReport {
    /// Number of bytes scanned.
    pub n: usize,
    /// chi² statistic (sum over 256 bins of `(obs − exp)² / exp`).
    pub statistic: f64,
    /// Approximate p-value for chi² distribution with 255 dof.
    pub p_value: f64,
    /// Reject H₀ at α = 0.01?  `true` means biased.
    pub rejected: bool,
}

/// Monobit frequency test on a byte stream.
///
/// Bits are scanned LSB-first within each byte.  Returns the absolute
/// fractional deviation `|0.5 − ones/n|` where `n = 8 · stream.len()`.
/// Returns `None` if the stream is too short to be meaningful (< 100 bytes).
pub fn monobit_test(stream: &[u8]) -> Option<f64> {
    if stream.len() < 100 {
        return None;
    }
    let mut ones: u64 = 0;
    for &b in stream {
        ones += b.count_ones() as u64;
    }
    let n = (stream.len() * 8) as f64;
    Some(((ones as f64 / n) - 0.5).abs())
}

/// NIST-style runs test (cf. NIST SP 800-22 §2.3).
///
/// Counts the number of runs (maximal blocks of consecutive equal bits)
/// in the stream and returns `|V_n − 2nπ(1−π)| / (2 √(2n) π (1 − π))`,
/// the test statistic's standardised absolute value.  A passing
/// stream has this < ~2.58 (α = 0.01, two-sided).  Returns `None`
/// if the prerequisite monobit test is failed (i.e. proportion of
/// ones deviates by more than `2 / √n`).
pub fn runs_test(stream: &[u8]) -> Option<f64> {
    if stream.len() < 100 {
        return None;
    }
    let n_bits = stream.len() * 8;
    let n = n_bits as f64;
    let mut ones: u64 = 0;
    for &b in stream {
        ones += b.count_ones() as u64;
    }
    let pi = ones as f64 / n;
    if (pi - 0.5).abs() >= 2.0 / n.sqrt() {
        // Prerequisite monobit failure — runs test is meaningless.
        return None;
    }

    let mut runs: u64 = 1;
    let mut prev = (stream[0]) & 1;
    for k in 1..n_bits {
        let cur = (stream[k / 8] >> (k % 8)) & 1;
        if cur != prev {
            runs += 1;
        }
        prev = cur;
    }

    let v = runs as f64;
    let expected = 2.0 * n * pi * (1.0 - pi);
    let stddev = 2.0 * (2.0 * n).sqrt() * pi * (1.0 - pi);
    Some((v - expected).abs() / stddev)
}

/// chi² test over the byte distribution.  H₀: bytes are uniform on
/// `[0, 256)`.
///
/// Statistic `Σ (obs[b] − n/256)² / (n/256)` follows χ²(255) under H₀.
/// We compare against the χ²(255) 99% critical value (≈ 310.46) to
/// produce a binary pass/fail.  The reported `p_value` is approximate
/// — we use a Wilson–Hilferty normal approximation rather than the
/// exact χ² CDF (no `statrs` dependency).
pub fn chi_squared_byte_test(stream: &[u8]) -> ChiSquaredReport {
    let n = stream.len();
    let mut bins = [0u64; 256];
    for &b in stream {
        bins[b as usize] += 1;
    }
    let exp = n as f64 / 256.0;
    let stat: f64 = bins
        .iter()
        .map(|&c| {
            let d = c as f64 - exp;
            d * d / exp.max(1e-12)
        })
        .sum();

    // Wilson–Hilferty: X ~ χ²(k) ⇒ ((X/k)^(1/3) − (1 − 2/(9k))) /
    // sqrt(2/(9k)) ≈ N(0, 1).
    let k = 255.0f64;
    let z = ((stat / k).cbrt() - (1.0 - 2.0 / (9.0 * k))) / (2.0 / (9.0 * k)).sqrt();
    let p_value = 1.0 - normal_cdf(z);

    // 99% critical value of χ²(255) ≈ 310.46.
    let rejected = stat > 310.46;

    ChiSquaredReport {
        n,
        statistic: stat,
        p_value,
        rejected,
    }
}

/// Standard-normal CDF via the Abramowitz–Stegun 26.2.17 formula.
/// Max error ≈ 7.5e-8 — fine for "is this distinguishable from
/// random?" purposes.
fn normal_cdf(z: f64) -> f64 {
    let a1 = 0.254829592;
    let a2 = -0.284496736;
    let a3 = 1.421413741;
    let a4 = -1.453152027;
    let a5 = 1.061405429;
    let p = 0.3275911;
    let sign = if z < 0.0 { -1.0 } else { 1.0 };
    let z = z.abs() / std::f64::consts::SQRT_2;
    let t = 1.0 / (1.0 + p * z);
    let y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * (-z * z).exp();
    0.5 * (1.0 + sign * y)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hash::sha256;

    /// SHA-256 over varying inputs should produce a stream that
    /// passes all three tests.
    fn sha_stream(n_blocks: usize) -> Vec<u8> {
        let mut out = Vec::with_capacity(n_blocks * 32);
        for i in 0..n_blocks {
            let h = sha256(&i.to_le_bytes());
            out.extend_from_slice(&h);
        }
        out
    }

    #[test]
    fn sha256_passes_monobit() {
        let s = sha_stream(2_000); // 64 KiB
        let d = monobit_test(&s).expect("stream long enough");
        // Expected stddev for n = 64 K bits is 1 / (2 √n) ≈ 0.002.
        // Real SHA-256 typically lands well under 0.01.
        assert!(d < 0.01, "SHA-256 monobit deviation {} too large", d);
    }

    #[test]
    fn all_zeros_fails_monobit() {
        let s = vec![0u8; 1024];
        let d = monobit_test(&s).expect("long enough");
        assert!(d > 0.49, "all-zeros monobit dev should be ~0.5, got {}", d);
    }

    #[test]
    fn sha256_passes_chi_squared() {
        let s = sha_stream(2_000);
        let r = chi_squared_byte_test(&s);
        assert!(
            !r.rejected,
            "SHA-256 chi² rejected at α=0.01: stat = {}",
            r.statistic
        );
    }

    #[test]
    fn biased_stream_fails_chi_squared() {
        // 90% of the bytes are 0x00; the rest are uniform.  Should be
        // overwhelmingly rejected.
        let mut s = vec![0u8; 9_000];
        s.extend((0..1_000u32).map(|i| (i & 0xff) as u8));
        let r = chi_squared_byte_test(&s);
        assert!(
            r.rejected,
            "biased stream NOT rejected; stat = {}",
            r.statistic
        );
    }

    #[test]
    fn alternating_bits_fails_runs_test() {
        // Stream `0101...` has the maximum possible number of runs;
        // far from `2nπ(1−π)`.
        let s = vec![0xaau8; 1024];
        let stat = runs_test(&s).expect("monobit prerequisite holds");
        // Far in the tail; stat ≈ |n/2 − 0| / small denom.
        assert!(stat > 5.0, "alternating-bit runs stat {} too small", stat);
    }

    #[test]
    fn sha256_passes_runs_test() {
        let s = sha_stream(2_000);
        let stat = runs_test(&s).expect("monobit passes");
        // Two-sided 99% threshold ≈ 2.58.  Allow some headroom.
        assert!(stat < 4.0, "SHA-256 runs stat {} unexpectedly large", stat);
    }
}
