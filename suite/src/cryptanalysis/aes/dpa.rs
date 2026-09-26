//! **DPA / CPA — Differential / Correlation Power Analysis** on AES
//! (Kocher-Jaffe-Jun CRYPTO 1999; Brier-Clavier-Olivier CHES 2004).
//!
//! Threat model: the attacker can measure the **power consumption**
//! of a device while it encrypts known plaintexts.  Power draw is
//! data-dependent — CMOS gates dissipate energy proportional to the
//! number of bit transitions per clock.  At the AES S-box output,
//! this is well-approximated by the **Hamming weight** of the value:
//!
//! ```text
//!     power(t) ≈ α · HW(SBox(P_byte ⊕ K_byte)) + noise(t)
//! ```
//!
//! With enough traces, the correlation between *predicted* power
//! (under each key-byte guess) and *actual* power peaks at the
//! correct key byte.
//!
//! ## Algorithm (CPA — Correlation Power Analysis)
//!
//! For each candidate byte `k ∈ [0, 256)`:
//!
//! 1. For each trace `i`, predict `H_i(k) = HW(SBox(P_i ⊕ k))`.
//! 2. Compute Pearson correlation `ρ(H(k), measured_power)` over `i`.
//! 3. The correct `k` gives the maximum |ρ|.
//!
//! Expected success: with `N = O(σ²_noise · 100)` traces (around
//! 100-1000 for clean models, more for noisy ones), the correct key
//! byte is reliably the top peak.
//!
//! ## Why this works on our library
//!
//! Our `src/symmetric/aes.rs` uses lookup-table S-boxes.  A real
//! implementation of CPA would measure side-channel emanations from
//! a hardware AES chip; here we **simulate** the power model
//! (Hamming weight of the S-box output) directly.  This is the
//! standard pedagogical setup for DPA / CPA — the actual measurement
//! step is hardware-specific.
//!
//! ## References
//!
//! - **P. Kocher, J. Jaffe, B. Jun**, *Differential Power Analysis*,
//!   CRYPTO 1999.
//! - **E. Brier, C. Clavier, F. Olivier**, *Correlation Power
//!   Analysis with a Leakage Model*, CHES 2004.

use super::reduced::SBOX;
use crate::visualize::color::{paint, FG_BRIGHT_GREEN, FG_BRIGHT_RED};
use rand::rngs::StdRng;
use rand::{RngCore, SeedableRng};

/// Hamming weight of a byte.
#[inline]
pub fn hw(b: u8) -> u32 {
    b.count_ones()
}

/// **Simulate one power trace** for an AES encryption — return a
/// single scalar = Hamming weight of the S-box output at byte
/// position `byte_pos` in round 1, **plus Gaussian noise**.
///
/// Real measurements would be a time-series; for the algebraic-level
/// CPA we collapse to a single sample at the leakage point.
pub fn simulate_trace_byte(
    plaintext: &[u8; 16],
    true_key: &[u8; 16],
    byte_pos: usize,
    noise_sigma: f64,
    rng: &mut impl RngCore,
) -> f64 {
    let p = plaintext[byte_pos];
    let k = true_key[byte_pos];
    let sb = SBOX[(p ^ k) as usize];
    let signal = hw(sb) as f64;
    // Gaussian noise via Box-Muller.
    let u1: f64 = (rng.next_u32() as f64 + 1.0) / (u32::MAX as f64 + 2.0);
    let u2: f64 = (rng.next_u32() as f64 + 1.0) / (u32::MAX as f64 + 2.0);
    let g = (-2.0 * u1.ln()).sqrt() * (2.0 * std::f64::consts::PI * u2).cos();
    signal + noise_sigma * g
}

/// **CPA attack** on one byte of K_R0.  Returns
/// `(recovered_byte, correlation_per_guess[256])`.  The correct byte
/// is `argmax|correlation_per_guess|`.
pub fn cpa_recover_byte(
    plaintexts: &[[u8; 16]],
    traces: &[f64],
    byte_pos: usize,
) -> (u8, [f64; 256]) {
    assert_eq!(plaintexts.len(), traces.len());
    let n = traces.len() as f64;
    let mean_trace: f64 = traces.iter().sum::<f64>() / n;
    let var_trace: f64 = traces
        .iter()
        .map(|&t| (t - mean_trace).powi(2))
        .sum::<f64>();
    let mut corrs = [0.0f64; 256];
    for k_guess in 0u32..256 {
        let k = k_guess as u8;
        let predicted: Vec<f64> = plaintexts
            .iter()
            .map(|p| hw(SBOX[(p[byte_pos] ^ k) as usize]) as f64)
            .collect();
        let mean_pred: f64 = predicted.iter().sum::<f64>() / n;
        let var_pred: f64 = predicted
            .iter()
            .map(|&v| (v - mean_pred).powi(2))
            .sum::<f64>();
        let cov: f64 = predicted
            .iter()
            .zip(traces.iter())
            .map(|(&p, &t)| (p - mean_pred) * (t - mean_trace))
            .sum::<f64>();
        let denom = (var_pred * var_trace).sqrt().max(1e-12);
        corrs[k_guess as usize] = cov / denom;
    }
    let recovered = corrs
        .iter()
        .enumerate()
        .max_by(|(_, a), (_, b)| a.abs().partial_cmp(&b.abs()).unwrap())
        .map(|(i, _)| i as u8)
        .unwrap();
    (recovered, corrs)
}

/// **Full CPA attack on all 16 key bytes** of K_R0.  Returns the
/// recovered key + a per-byte report.
pub fn cpa_attack_full_key(
    plaintexts: &[[u8; 16]],
    traces_per_byte: &[Vec<f64>; 16],
    true_key: &[u8; 16],
) -> ([u8; 16], CpaReport) {
    let mut recovered = [0u8; 16];
    let mut per_byte_top_corr = [0.0f64; 16];
    let mut per_byte_rank_of_correct = [0usize; 16];
    let mut bytes_correct = 0;
    for byte_pos in 0..16 {
        let (byte, corrs) = cpa_recover_byte(plaintexts, &traces_per_byte[byte_pos], byte_pos);
        recovered[byte_pos] = byte;
        per_byte_top_corr[byte_pos] = corrs[byte as usize].abs();
        // Rank of correct key byte by |corr|.
        let mut sorted_indices: Vec<usize> = (0..256).collect();
        sorted_indices.sort_by(|&a, &b| corrs[b].abs().partial_cmp(&corrs[a].abs()).unwrap());
        let true_byte = true_key[byte_pos];
        let rank = sorted_indices
            .iter()
            .position(|&idx| idx as u8 == true_byte)
            .unwrap_or(255);
        per_byte_rank_of_correct[byte_pos] = rank;
        if byte == true_key[byte_pos] {
            bytes_correct += 1;
        }
    }
    let report = CpaReport {
        n_traces: plaintexts.len(),
        bytes_correct,
        per_byte_top_corr,
        per_byte_rank_of_correct,
    };
    (recovered, report)
}

#[derive(Clone, Debug)]
pub struct CpaReport {
    pub n_traces: usize,
    pub bytes_correct: usize,
    pub per_byte_top_corr: [f64; 16],
    pub per_byte_rank_of_correct: [usize; 16],
}

/// **Generate a synthetic trace set** for a CPA attack.  Returns
/// (`plaintexts`, `traces_per_byte`).  Each `traces_per_byte[i]`
/// holds the leakage at byte position `i` in round 1.
pub fn generate_traces(
    n_traces: usize,
    true_key: &[u8; 16],
    noise_sigma: f64,
    seed: u64,
) -> (Vec<[u8; 16]>, [Vec<f64>; 16]) {
    let mut rng = StdRng::seed_from_u64(seed);
    let mut plaintexts = Vec::with_capacity(n_traces);
    let mut traces: [Vec<f64>; 16] = Default::default();
    for v in traces.iter_mut() {
        *v = Vec::with_capacity(n_traces);
    }
    for _ in 0..n_traces {
        let mut p = [0u8; 16];
        rng.fill_bytes(&mut p);
        plaintexts.push(p);
        for byte in 0..16 {
            let t = simulate_trace_byte(&p, true_key, byte, noise_sigma, &mut rng);
            traces[byte].push(t);
        }
    }
    (plaintexts, traces)
}

/// Render a Markdown report of the CPA outcome.
pub fn format_cpa_report(report: &CpaReport, recovered: &[u8; 16], true_key: &[u8; 16]) -> String {
    let mut s = String::new();
    s.push_str("# CPA / Correlation Power Analysis on AES-128 K_R0\n\n");
    s.push_str(&format!("**Traces used**: {}\n\n", report.n_traces));
    s.push_str(&format!(
        "**Bytes correctly recovered**: {}/16  {}\n\n",
        report.bytes_correct,
        if report.bytes_correct == 16 {
            paint("✓ FULL KEY RECOVERED", FG_BRIGHT_GREEN)
        } else if report.bytes_correct >= 12 {
            paint(
                "≈ mostly recovered",
                crate::visualize::color::FG_BRIGHT_YELLOW,
            )
        } else {
            paint("✗ attack fails at this noise level", FG_BRIGHT_RED)
        }
    ));
    s.push_str("## Per-byte breakdown\n\n");
    s.push_str("| byte | true | recovered | |ρ| at peak | rank of true |\n");
    s.push_str("|----:|----:|---------:|----------:|------------:|\n");
    for i in 0..16 {
        let ok = recovered[i] == true_key[i];
        s.push_str(&format!(
            "| {} | {:02x} | {:02x}{} | {:.4} | {} |\n",
            i,
            true_key[i],
            recovered[i],
            if ok { " ✓" } else { " ✗" },
            report.per_byte_top_corr[i],
            report.per_byte_rank_of_correct[i] + 1,
        ));
    }
    s.push('\n');
    s
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// `hw` matches `count_ones`.
    #[test]
    fn hamming_weight_smoke() {
        assert_eq!(hw(0x00), 0);
        assert_eq!(hw(0xFF), 8);
        assert_eq!(hw(0xAA), 4);
    }

    /// **Noise-free CPA** recovers one byte with ~50 traces.
    #[test]
    fn cpa_recovers_byte_no_noise() {
        let key = [0x42u8; 16];
        let (pts, traces) = generate_traces(200, &key, 0.0, 7);
        let (recovered, _) = cpa_recover_byte(&pts, &traces[5], 5);
        assert_eq!(recovered, key[5]);
    }

    /// **Noisy CPA** — at σ = 1.0 (moderate noise), 500 traces should
    /// still reliably recover the correct byte.
    #[test]
    fn cpa_recovers_byte_with_noise() {
        let key = [0xABu8; 16];
        let (pts, traces) = generate_traces(500, &key, 1.0, 42);
        let (recovered, _) = cpa_recover_byte(&pts, &traces[0], 0);
        assert_eq!(recovered, key[0]);
    }

    /// **Full-key recovery** with low noise, ~256 traces.
    #[test]
    fn cpa_recovers_full_key_no_noise() {
        let mut key = [0u8; 16];
        for i in 0..16 {
            key[i] = i as u8 * 17;
        }
        let (pts, traces) = generate_traces(256, &key, 0.0, 1337);
        let (recovered, report) = cpa_attack_full_key(&pts, &traces, &key);
        assert_eq!(recovered, key);
        assert_eq!(report.bytes_correct, 16);
    }

    /// **Trace-count threshold**: with too few traces, the attack
    /// fails some bytes.  Demonstrates the data-noise tradeoff.
    #[test]
    fn cpa_fails_with_too_few_noisy_traces() {
        let key = [0xC0u8; 16];
        // Just 32 traces with σ = 2.0 — likely to mis-rank some bytes.
        let (pts, traces) = generate_traces(32, &key, 2.0, 99);
        let (_, report) = cpa_attack_full_key(&pts, &traces, &key);
        // We don't insist on all-failure (the attack is probabilistic);
        // we just verify the bytes_correct count is < 16.
        assert!(report.bytes_correct < 16);
    }

    /// **Demo emission**.
    #[test]
    #[ignore]
    fn demo_cpa_attack() {
        let key = [
            0x2b, 0x7e, 0x15, 0x16, 0x28, 0xae, 0xd2, 0xa6, 0xab, 0xf7, 0x15, 0x88, 0x09, 0xcf,
            0x4f, 0x3c,
        ];
        let (pts, traces) = generate_traces(512, &key, 1.0, 1337);
        let (recovered, report) = cpa_attack_full_key(&pts, &traces, &key);
        println!("\n{}", format_cpa_report(&report, &recovered, &key));
    }
}
