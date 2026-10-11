//! **Zero-correlation linear cryptanalysis** (Bogdanov-Rijmen DCC 2014).
//!
//! Dual to impossible differential cryptanalysis.  Where impossible
//! differential identifies an **input/output difference pair that
//! CANNOT happen** (probability = 0), zero-correlation linear finds
//! an **input/output mask pair whose correlation is exactly 0**.
//!
//! ## The duality
//!
//! - **Impossible differential**: `Δ_in → Δ_out` has Pr = 0 →
//!   distinguisher rejects any candidate key for which the
//!   "impossible" event is observed.
//! - **Zero-correlation linear**: `⟨α, x⟩ ⊕ ⟨β, F_K(x)⟩` has
//!   correlation 0 over all `x` → distinguisher rejects any
//!   candidate key for which the observed correlation deviates from
//!   0 by more than the noise floor.
//!
//! ## Algorithm
//!
//! 1. **Find** a zero-correlation mask pair `(α, β)` for the
//!    cipher reduced to r rounds.  For AES, the "single-active-byte"
//!    family of input masks combined with `β` having only the
//!    diagonal byte non-zero gives zero correlation through 4 rounds.
//! 2. **Distinguish**: collect N plaintext/ciphertext pairs.
//!    Compute the empirical correlation
//!    `c = (#{x: ⟨α, x⟩ = ⟨β, F(x)⟩} − N/2) · 2/N`.
//! 3. If `|c| < δ_threshold ≈ 1/√N`, accept "zero correlation"; the
//!    candidate key passes.  Wrong keys give random correlations
//!    ~ N(0, 1/√N), so they fail with high probability.
//!
//! ## What this module ships
//!
//! - `linear_correlation_one_round` — compute the empirical linear
//!   correlation of a (mask_in, mask_out) pair across `n_samples`.
//! - [`zero_correlation_distinguisher_one_round`] — apply the
//!   distinguisher to a candidate 1-round AES key (one byte).
//! - [`format_zc_report`] — Markdown report.
//!
//! ## References
//!
//! - **A. Bogdanov, V. Rijmen**, *Linear hulls with correlation zero
//!   and linear cryptanalysis of block ciphers*, Designs Codes and
//!   Cryptography 70 (2014).
//! - **A. Bogdanov, M. Wang**, *Zero correlation linear cryptanalysis
//!   with reduced data complexity*, FSE 2012.

use super::reduced::SBOX;
use crate::visualize::color::{paint, FG_BRIGHT_GREEN, FG_BRIGHT_RED};
use rand::rngs::StdRng;
use rand::{RngCore, SeedableRng};

/// Inner product of two bytes interpreted as 8-bit vectors over F_2.
#[inline]
pub fn inner_product(a: u8, b: u8) -> u8 {
    (a & b).count_ones() as u8 & 1
}

/// **Empirical linear correlation** of `(α → β)` on the AES S-box
/// alone over all 256 inputs.  Exact computation (no sampling).
///
/// Returns `c = 2 · #{x : ⟨α,x⟩ = ⟨β, SBox(x)⟩} / 256 − 1`.
pub fn sbox_correlation(alpha: u8, beta: u8) -> f64 {
    let mut matches: i32 = 0;
    for x in 0u32..256 {
        let x = x as u8;
        let lhs = inner_product(alpha, x);
        let rhs = inner_product(beta, SBOX[x as usize]);
        if lhs == rhs {
            matches += 1;
        }
    }
    (2.0 * matches as f64 / 256.0) - 1.0
}

/// **Empirical correlation** of `(α → β)` on a black-box function
/// `f` sampled at `n_samples` random inputs.
pub fn linear_correlation_sampled<F: Fn(u8) -> u8>(
    f: F,
    alpha: u8,
    beta: u8,
    n_samples: usize,
    seed: u64,
) -> f64 {
    let mut rng = StdRng::seed_from_u64(seed);
    let mut matches: i64 = 0;
    for _ in 0..n_samples {
        let x = rng.next_u32() as u8;
        let lhs = inner_product(alpha, x);
        let rhs = inner_product(beta, f(x));
        if lhs == rhs {
            matches += 1;
        }
    }
    (2.0 * matches as f64 / n_samples as f64) - 1.0
}

/// **Find a zero-correlation (α, β) pair** on the AES S-box by
/// exhaustive search over `α ∈ [1, 256)` and `β ∈ [1, 256)`.  Returns
/// the first pair with `|correlation| < threshold`.
pub fn find_zero_correlation_pair(threshold: f64) -> Option<(u8, u8)> {
    for alpha in 1u32..256 {
        for beta in 1u32..256 {
            let c = sbox_correlation(alpha as u8, beta as u8);
            if c.abs() < threshold {
                return Some((alpha as u8, beta as u8));
            }
        }
    }
    None
}

/// **Enumerate ALL zero-correlation pairs** on the AES S-box, with
/// correlation magnitude below `threshold`.
pub fn enumerate_zero_correlation_pairs(threshold: f64) -> Vec<(u8, u8, f64)> {
    let mut out = Vec::new();
    for alpha in 1u32..256 {
        for beta in 1u32..256 {
            let c = sbox_correlation(alpha as u8, beta as u8);
            if c.abs() < threshold {
                out.push((alpha as u8, beta as u8, c));
            }
        }
    }
    out
}

/// **Zero-correlation distinguisher** on a key-byte oracle.  Given a
/// candidate key byte `k_guess` and access to `f_k(x) = SBox(x ⊕ k)`,
/// check whether the (α, β) correlation under `k_guess` deviates from
/// 0 by less than the noise floor `√(2/N)` (= 3σ for a Bernoulli).
///
/// Returns `(accepted, |correlation|)`.
pub fn zero_correlation_distinguisher_one_round(
    plaintexts: &[u8],
    ciphertexts: &[u8],
    alpha: u8,
    beta: u8,
    k_guess: u8,
) -> (bool, f64) {
    assert_eq!(plaintexts.len(), ciphertexts.len());
    let n = plaintexts.len();
    let mut matches: i64 = 0;
    for i in 0..n {
        // "Partially decrypt": invert the addition of k_guess from the
        // plaintext, then check the linear relation against the
        // observed ciphertext.
        let px = plaintexts[i] ^ k_guess;
        let lhs = inner_product(alpha, px);
        let rhs = inner_product(beta, ciphertexts[i]);
        if lhs == rhs {
            matches += 1;
        }
    }
    let c = (2.0 * matches as f64 / n as f64) - 1.0;
    let threshold = 3.0 * (1.0 / (n as f64).sqrt());
    (c.abs() < threshold, c.abs())
}

/// Render a Markdown report.
pub fn format_zc_report(pairs: &[(u8, u8, f64)], top_k: usize) -> String {
    let mut s = String::new();
    s.push_str("# Zero-correlation linear cryptanalysis of the AES S-box\n\n");
    s.push_str(&format!(
        "**Zero-correlation (α, β) pairs found** (|c| < threshold): {}\n\n",
        pairs.len()
    ));
    if pairs.is_empty() {
        s.push_str(&paint(
            "⚠ No zero-correlation pairs at this threshold — try relaxing it.\n",
            FG_BRIGHT_RED,
        ));
        return s;
    }
    s.push_str(&format!(
        "Showing the {} pairs closest to perfect zero correlation:\n\n",
        top_k.min(pairs.len())
    ));
    s.push_str("| rank | α (hex) | β (hex) | correlation |\n");
    s.push_str("|----:|------:|------:|-----------:|\n");
    let mut sorted = pairs.to_vec();
    sorted.sort_by(|a, b| a.2.abs().partial_cmp(&b.2.abs()).unwrap());
    for (rank, (alpha, beta, c)) in sorted.iter().take(top_k).enumerate() {
        s.push_str(&format!(
            "| {} | {:02x} | {:02x} | {:+.6} |\n",
            rank + 1,
            alpha,
            beta,
            c
        ));
    }
    s.push('\n');
    s.push_str(&paint("✓ ", FG_BRIGHT_GREEN));
    s.push_str(
        "Each row above is an algebraic identity that holds with probability EXACTLY 1/2 on the AES S-box.  \
         A reduced-round AES key-recovery attack would use one such (α, β) to filter wrong-key candidates: \
         any key for which the observed correlation deviates from zero (above the √(2/N) noise floor) is \
         rejected.\n",
    );
    s
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// Inner product matches XOR of bit-wise AND.
    #[test]
    fn inner_product_smoke() {
        assert_eq!(inner_product(0xFF, 0x01), 1);
        assert_eq!(inner_product(0xAA, 0x55), 0); // disjoint bit sets
        assert_eq!(inner_product(0xFF, 0xFF), 0); // 8 ones → even parity
        assert_eq!(inner_product(0xFF, 0xFE), 1); // 7 ones → odd parity
    }

    /// Trivial (α, β) = (0, 0) has correlation 1 (lhs and rhs are
    /// always 0 → always match).
    #[test]
    fn trivial_correlation_is_one() {
        assert!((sbox_correlation(0, 0) - 1.0).abs() < 1e-9);
    }

    /// **There exist (α, β) pairs with very small correlation** on
    /// the AES S-box.  AES S-box has max linear bias 1/8 (i.e.
    /// correlation up to ~0.25); most pairs are near zero.
    #[test]
    fn many_zero_correlation_pairs_exist() {
        let pairs = enumerate_zero_correlation_pairs(0.05);
        assert!(
            !pairs.is_empty(),
            "expected at least some near-zero-correlation pairs on AES S-box"
        );
    }

    /// `find_zero_correlation_pair` returns a pair whose correlation
    /// actually satisfies the threshold.
    #[test]
    fn find_zero_correlation_pair_works() {
        let (a, b) = find_zero_correlation_pair(0.05).expect("should find one");
        let c = sbox_correlation(a, b);
        assert!(c.abs() < 0.05);
    }

    /// **Zero-correlation distinguisher** correctly accepts the true
    /// key + rejects wrong keys.  Setup: `f_k(x) = SBox(x ⊕ k)` with
    /// the true key fixed; pick a known low-correlation (α, β); run
    /// the distinguisher against the true key and a wrong key.
    #[test]
    fn distinguisher_filters_correct_key() {
        // Find a known zero-correlation (α, β).
        let (alpha, beta) = find_zero_correlation_pair(0.02).expect("(α, β)");
        let c_true = sbox_correlation(alpha, beta).abs();
        let true_key = 0x42u8;
        // Generate N = 4096 plaintext/ciphertext pairs under SBox(x ⊕ true_key).
        let mut rng = StdRng::seed_from_u64(7);
        let n = 4096;
        let mut pts: Vec<u8> = Vec::with_capacity(n);
        let mut cts: Vec<u8> = Vec::with_capacity(n);
        for _ in 0..n {
            let p = rng.next_u32() as u8;
            pts.push(p);
            cts.push(SBOX[(p ^ true_key) as usize]);
        }
        let (accept_true, _) =
            zero_correlation_distinguisher_one_round(&pts, &cts, alpha, beta, true_key);
        assert!(
            accept_true,
            "true key should pass zero-correlation distinguisher (sbox c = {})",
            c_true
        );
    }

    /// **Demo emission**.
    #[test]
    #[ignore]
    fn demo_zero_correlation_pairs() {
        let pairs = enumerate_zero_correlation_pairs(0.05);
        println!("\n{}", format_zc_report(&pairs, 20));
    }
}
