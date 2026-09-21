//! Avalanche / diffusion measurements over arbitrary cipher functions.
//!
//! Black-box tests: pass any `fn(&[u8]) -> Vec<u8>` (your full cipher,
//! a single round, a hash, a PRF) and measure how single-input-bit
//! flips propagate.  Three flavours of measurement, in increasing
//! strength:
//!
//! 1. [`full_avalanche`] returns the `n × m` matrix `A` where
//!    `A[i][j] = Pr[bit_j(F(x)) flips when bit_i(x) flips]`.
//!    A perfect random function has every entry near `0.5`.
//! 2. [`sac_score`] — Strict Avalanche Criterion: `max |A[i][j] − 0.5|`.
//!    Webster–Tavares (1986).  Lower is better; `0` is ideal.
//! 3. [`bit_independence_score`] — Bit Independence Criterion:
//!    pairwise correlation of output-bit flips given a fixed input
//!    bit flip.  Approximated as `max |corr(j, k)|` over output-bit
//!    pairs.

use rand::rngs::StdRng;
use rand::{RngCore, SeedableRng};

/// Per-bit-pair avalanche probabilities.
#[derive(Clone, Debug)]
pub struct AvalancheReport {
    pub n_in: usize,
    pub n_out: usize,
    pub samples_per_bit: usize,
    /// `matrix[i][j]` = empirical Pr[bit_j(F(x)) flips when bit_i(x) flips].
    pub matrix: Vec<Vec<f64>>,
}

impl AvalancheReport {
    /// Worst absolute deviation from 0.5 across the matrix.
    pub fn sac_deviation(&self) -> f64 {
        let mut worst = 0.0f64;
        for row in &self.matrix {
            for &p in row {
                let d = (p - 0.5).abs();
                if d > worst {
                    worst = d;
                }
            }
        }
        worst
    }

    /// Worst-case input bit (the one whose flip diffuses least
    /// uniformly).  Returns `(bit_index, max_deviation_at_that_bit)`.
    pub fn weakest_input_bit(&self) -> (usize, f64) {
        let mut worst_bit = 0;
        let mut worst_dev = 0.0f64;
        for (i, row) in self.matrix.iter().enumerate() {
            let row_worst = row.iter().map(|&p| (p - 0.5).abs()).fold(0.0f64, f64::max);
            if row_worst > worst_dev {
                worst_dev = row_worst;
                worst_bit = i;
            }
        }
        (worst_bit, worst_dev)
    }
}

/// Compute the full avalanche matrix.
///
/// Total cipher calls: `2 · n_in · samples_per_bit`.
///
/// `cipher` must accept exactly `(n_in + 7) / 8` input bytes and
/// produce at least `(n_out + 7) / 8` output bytes.
pub fn full_avalanche<F>(
    cipher: F,
    n_in: usize,
    n_out: usize,
    samples_per_bit: usize,
    seed: u64,
) -> AvalancheReport
where
    F: Fn(&[u8]) -> Vec<u8>,
{
    assert!(n_in > 0 && n_out > 0 && samples_per_bit > 0);

    let in_bytes = n_in.div_ceil(8);
    let mut rng = StdRng::seed_from_u64(seed);
    let mut matrix = vec![vec![0u64; n_out]; n_in];

    for i in 0..n_in {
        for _ in 0..samples_per_bit {
            let mut input = vec![0u8; in_bytes];
            rng.fill_bytes(&mut input);
            // Mask off any bits beyond n_in in the last byte.
            if !n_in.is_multiple_of(8) {
                let keep = (1u8 << (n_in % 8)) - 1;
                input[in_bytes - 1] &= keep;
            }

            let mut flipped = input.clone();
            flipped[i / 8] ^= 1 << (i % 8);

            let y0 = cipher(&input);
            let y1 = cipher(&flipped);
            assert_eq!(
                y0.len(),
                y1.len(),
                "cipher returned mismatched output lengths"
            );

            for j in 0..n_out {
                let b0 = (y0[j / 8] >> (j % 8)) & 1;
                let b1 = (y1[j / 8] >> (j % 8)) & 1;
                if b0 != b1 {
                    matrix[i][j] += 1;
                }
            }
        }
    }

    let denom = samples_per_bit as f64;
    let matrix: Vec<Vec<f64>> = matrix
        .into_iter()
        .map(|row| row.into_iter().map(|c| c as f64 / denom).collect())
        .collect();

    AvalancheReport {
        n_in,
        n_out,
        samples_per_bit,
        matrix,
    }
}

/// SAC score = `max |A[i][j] − 0.5|`.  Convenience wrapper around
/// [`full_avalanche`].
pub fn sac_score<F>(cipher: F, n_in: usize, n_out: usize, samples_per_bit: usize, seed: u64) -> f64
where
    F: Fn(&[u8]) -> Vec<u8>,
{
    full_avalanche(cipher, n_in, n_out, samples_per_bit, seed).sac_deviation()
}

/// BIC score for a single input-bit-flip position.  Returns the max
/// absolute pairwise correlation between output-bit flip indicators.
pub fn bit_independence_score<F>(
    cipher: F,
    n_in: usize,
    n_out: usize,
    flip_input_bit: usize,
    samples: usize,
    seed: u64,
) -> f64
where
    F: Fn(&[u8]) -> Vec<u8>,
{
    assert!(flip_input_bit < n_in);
    if samples < 32 {
        return 1.0;
    }

    let in_bytes = n_in.div_ceil(8);
    let mut rng = StdRng::seed_from_u64(seed);

    let mut v: Vec<Vec<i32>> = Vec::with_capacity(samples);
    for _ in 0..samples {
        let mut input = vec![0u8; in_bytes];
        rng.fill_bytes(&mut input);
        if !n_in.is_multiple_of(8) {
            let keep = (1u8 << (n_in % 8)) - 1;
            input[in_bytes - 1] &= keep;
        }
        let mut flipped = input.clone();
        flipped[flip_input_bit / 8] ^= 1 << (flip_input_bit % 8);
        let y0 = cipher(&input);
        let y1 = cipher(&flipped);
        let mut row = Vec::with_capacity(n_out);
        for j in 0..n_out {
            let b0 = (y0[j / 8] >> (j % 8)) & 1;
            let b1 = (y1[j / 8] >> (j % 8)) & 1;
            row.push((b0 ^ b1) as i32);
        }
        v.push(row);
    }

    let n = samples as f64;
    let means: Vec<f64> = (0..n_out)
        .map(|j| v.iter().map(|row| row[j] as f64).sum::<f64>() / n)
        .collect();
    let vars: Vec<f64> = (0..n_out)
        .map(|j| {
            let m = means[j];
            v.iter().map(|row| (row[j] as f64 - m).powi(2)).sum::<f64>() / n
        })
        .collect();
    let mut max_corr = 0.0f64;
    for j in 0..n_out {
        for k in (j + 1)..n_out {
            if vars[j] < 1e-12 || vars[k] < 1e-12 {
                continue;
            }
            let cov: f64 = v
                .iter()
                .map(|row| (row[j] as f64 - means[j]) * (row[k] as f64 - means[k]))
                .sum::<f64>()
                / n;
            let c = cov / (vars[j] * vars[k]).sqrt();
            if c.abs() > max_corr {
                max_corr = c.abs();
            }
        }
    }
    max_corr
}

#[cfg(test)]
mod tests {
    use super::*;

    /// SHA-256 should look ~random to the SAC test (deviation small).
    #[test]
    fn sha256_passes_sac_loosely() {
        use crate::hash::sha256;
        let cipher = |x: &[u8]| -> Vec<u8> { sha256(x).to_vec() };
        // 64 input bits × 32 samples — finite-sample noise is large
        // (~0.09 / σ), set bound generously.
        let dev = sac_score(cipher, 64, 256, 32, 0xc0ffee);
        assert!(dev <= 0.5, "SAC dev {} too large for SHA-256", dev);
    }

    /// Identity F(x) = x has the worst SAC: avalanche matrix = I,
    /// so deviation from 0.5 is exactly 0.5 everywhere.
    #[test]
    fn identity_function_fails_sac() {
        let cipher = |x: &[u8]| -> Vec<u8> { x.to_vec() };
        let dev = sac_score(cipher, 32, 32, 64, 0xdeadbeef);
        assert!(dev > 0.4, "identity SAC dev {} should be near 0.5", dev);
    }

    #[test]
    fn avalanche_matrix_shape_and_identity() {
        let cipher = |x: &[u8]| -> Vec<u8> { x.to_vec() };
        let r = full_avalanche(cipher, 16, 16, 8, 1);
        assert_eq!(r.matrix.len(), 16);
        assert_eq!(r.matrix[0].len(), 16);
        for i in 0..16 {
            for j in 0..16 {
                if i == j {
                    assert!((r.matrix[i][j] - 1.0).abs() < 1e-9);
                } else {
                    assert!(r.matrix[i][j].abs() < 1e-9);
                }
            }
        }
    }

    #[test]
    fn weakest_bit_for_identity_is_full_deviation() {
        let cipher = |x: &[u8]| -> Vec<u8> { x.to_vec() };
        let r = full_avalanche(cipher, 8, 8, 16, 7);
        let (_bit, dev) = r.weakest_input_bit();
        assert!((dev - 0.5).abs() < 1e-9);
    }
}
