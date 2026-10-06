//! **Cache-timing attack on T-table AES** (Bernstein 2005 / Osvik-
//! Shamir-Tromer CT-RSA 2006).
//!
//! Threat model: the attacker observes the encryption time of an
//! AES implementation that uses **T-tables** (precomputed 1024-byte
//! lookup tables combining S-box + MixColumns).  Each round-1 lookup
//! accesses `T[plaintext_byte ⊕ key_byte]`; the **cache line** hit
//! depends on the high bits of that XOR.  If multiple round-1 lookups
//! happen to map to the same cache line, the average encryption is
//! faster (= cache hits).
//!
//! ## Bernstein's model
//!
//! T-tables are typically 1024 bytes = 16 cache lines of 64 bytes
//! each.  Each line holds 16 entries (each entry = 4 bytes = one
//! 32-bit column of the round output).  The cache line accessed for
//! input byte `x` is `x >> 4` (the high nibble).
//!
//! When the attacker varies plaintext byte `i` and the key byte at
//! position `i` is fixed, the cache footprint depends on the
//! distribution of `(p_i ⊕ k_i) >> 4`.  By observing timing
//! variance vs the *uniform* baseline, the attacker recovers the
//! **high nibble** of each key byte.
//!
//! Then a second pass (varying byte j ≠ i and measuring conditioned
//! on byte i) recovers the low nibble.
//!
//! ## Simplification in this module
//!
//! We model the timing as a deterministic function of the cache-line
//! access pattern: each encryption's timing = number of UNIQUE cache
//! lines accessed across the 16 round-1 T-table lookups, plus noise.
//! This is the same dependency Bernstein exploits — the difference
//! between best-case (all 16 lookups in the same line) and worst
//! case (all 16 in different lines) translates to a measurable
//! timing delta.
//!
//! ## What this module ships
//!
//! - [`simulate_encryption_timing`] — model the cache-timing leak.
//! - [`bernstein_attack_high_nibble`] — recover the high nibble of
//!   each key byte from N timed encryptions.
//! - [`format_cache_attack_report`] — Markdown report.

use crate::visualize::color::{paint, FG_BRIGHT_GREEN, FG_BRIGHT_RED, FG_BRIGHT_YELLOW};
use rand::rngs::StdRng;
use rand::{RngCore, SeedableRng};

/// **Simulate the cache-timing of one AES-128 encryption** under our
/// T-table model.  Timing = sum over all 16 lookups of the per-lookup
/// "miss penalty": the lookup is a MISS (slow) if it accesses a cache
/// line not yet warm (= newly fetched), HIT (fast) if the line is
/// already cached from a previous lookup in this encryption.
///
/// This model corresponds to a cold-cache assumption at the start of
/// each encryption (which Bernstein's attack achieves with a
/// preceding `prime` step).
pub fn simulate_encryption_timing(
    plaintext: &[u8; 16],
    key: &[u8; 16],
    noise_sigma: f64,
    rng: &mut impl RngCore,
) -> f64 {
    let mut lines_warm = [false; 16];
    let mut total_miss_penalty = 0.0f64;
    for i in 0..16 {
        let line = ((plaintext[i] ^ key[i]) >> 4) as usize;
        if !lines_warm[line] {
            total_miss_penalty += 1.0;
            lines_warm[line] = true;
        }
    }
    let u1: f64 = (rng.next_u32() as f64 + 1.0) / (u32::MAX as f64 + 2.0);
    let u2: f64 = (rng.next_u32() as f64 + 1.0) / (u32::MAX as f64 + 2.0);
    let g = (-2.0 * u1.ln()).sqrt() * (2.0 * std::f64::consts::PI * u2).cos();
    total_miss_penalty + noise_sigma * g
}

/// **Simpler per-byte timing model** for the bernstein attack
/// pedagogical demonstration: at byte position `i`, the encryption
/// MEASURED time is the indicator (1 / 0) of whether the lookup
/// at byte `i` hit the FIRST cache line.  Achievable in practice
/// via an instrumented test setup that isolates one round-1 lookup.
///
/// Under this model, the attacker conditioning on `plaintext[i] >> 4`
/// observes the deterministic effect of `(plaintext[i] >> 4) ⊕
/// (key[i] >> 4) == 0` — i.e., the MIN-time bucket reveals
/// `key[i] >> 4` directly.
pub fn simulate_single_byte_timing(
    plaintext: &[u8; 16],
    key: &[u8; 16],
    byte_pos: usize,
    noise_sigma: f64,
    rng: &mut impl RngCore,
) -> f64 {
    let line = ((plaintext[byte_pos] ^ key[byte_pos]) >> 4) as usize;
    // Time = 1 if line == 0 (first cache line — "fast warm path"), else 0.
    let base = if line == 0 { 0.0 } else { 1.0 };
    let u1: f64 = (rng.next_u32() as f64 + 1.0) / (u32::MAX as f64 + 2.0);
    let u2: f64 = (rng.next_u32() as f64 + 1.0) / (u32::MAX as f64 + 2.0);
    let g = (-2.0 * u1.ln()).sqrt() * (2.0 * std::f64::consts::PI * u2).cos();
    base + noise_sigma * g
}

/// **Bernstein's high-nibble recovery attack**.  For each byte
/// position `i`, partition the timed encryptions by `plaintext[i] >> 4`
/// (the high nibble of the plaintext byte at position `i`) and look at
/// the conditional mean timing.  The minimum-mean bucket's high
/// nibble XORed with the partition value reveals the key byte's high
/// nibble.
///
/// Returns an array of 16 recovered high nibbles (each in `[0, 16)`).
pub fn bernstein_attack_high_nibble(plaintexts: &[[u8; 16]], timings: &[f64]) -> [u8; 16] {
    let mut out = [0u8; 16];
    let n = timings.len();
    assert_eq!(plaintexts.len(), n);
    for byte_pos in 0..16 {
        // For each plaintext high-nibble value v ∈ [0, 16), accumulate
        // mean(timing | plaintext_byte_high_nibble == v).
        let mut means = [0.0f64; 16];
        let mut counts = [0u64; 16];
        for i in 0..n {
            let v = (plaintexts[i][byte_pos] >> 4) as usize;
            means[v] += timings[i];
            counts[v] += 1;
        }
        for v in 0..16 {
            if counts[v] > 0 {
                means[v] /= counts[v] as f64;
            }
        }
        // The MINIMUM-mean bucket corresponds to the highest hit-rate
        // pattern — which Bernstein's analysis shows is where the
        // plaintext high nibble XOR key high nibble = some fixed value
        // (call it the "min-line" value).  Since the attacker
        // benchmarks against a reference run with key = 0, the
        // recovered byte is the bucket index XOR the reference's
        // min-line value.
        //
        // For the simplified pedagogical attack here, the reference
        // assumption is that the MIN bucket corresponds to plaintext
        // high nibble = (some baseline 0) ⊕ key_high_nibble.  We pick
        // the min-mean bucket and reveal its high nibble as the key
        // high nibble.
        let min_v = (0..16usize)
            .min_by(|&a, &b| means[a].partial_cmp(&means[b]).unwrap())
            .unwrap();
        out[byte_pos] = min_v as u8;
    }
    out
}

/// Convenience: simulate a Bernstein-style attack end-to-end using
/// the per-byte timing model (`simulate_single_byte_timing`).  For
/// each byte position we collect `n_traces` timings; the bucket of
/// plaintext-high-nibble values with the minimum mean reveals the
/// key high nibble at that position.
///
/// (The full-encryption model in `simulate_encryption_timing` is
/// what Bernstein's actual attack uses, but recovering high nibbles
/// from joint 16-byte timings requires the much more elaborate
/// reference-distribution alignment.  We use the per-byte model here
/// to keep the educational demonstration tight.)
pub fn run_bernstein_attack(
    true_key: &[u8; 16],
    n_traces: usize,
    noise_sigma: f64,
    seed: u64,
) -> ([u8; 16], CacheAttackReport) {
    let mut rng = StdRng::seed_from_u64(seed);
    let mut recovered_high = [0u8; 16];
    let mut per_byte_correct = [false; 16];
    let mut bytes_correct = 0;
    for byte_pos in 0..16 {
        let mut plaintexts = Vec::with_capacity(n_traces);
        let mut timings = Vec::with_capacity(n_traces);
        for _ in 0..n_traces {
            let mut p = [0u8; 16];
            rng.fill_bytes(&mut p);
            let t = simulate_single_byte_timing(&p, true_key, byte_pos, noise_sigma, &mut rng);
            plaintexts.push(p);
            timings.push(t);
        }
        // Find the high-nibble bucket with the MINIMUM mean timing
        // (= fastest = warm-cache-line hit = plaintext_high ⊕ key_high == 0).
        let mut means = [0.0f64; 16];
        let mut counts = [0u64; 16];
        for i in 0..n_traces {
            let v = (plaintexts[i][byte_pos] >> 4) as usize;
            means[v] += timings[i];
            counts[v] += 1;
        }
        for v in 0..16 {
            if counts[v] > 0 {
                means[v] /= counts[v] as f64;
            }
        }
        let min_v = (0..16usize)
            .min_by(|&a, &b| means[a].partial_cmp(&means[b]).unwrap())
            .unwrap();
        recovered_high[byte_pos] = min_v as u8;
        if recovered_high[byte_pos] == (true_key[byte_pos] >> 4) {
            per_byte_correct[byte_pos] = true;
            bytes_correct += 1;
        }
    }
    let report = CacheAttackReport {
        n_traces,
        noise_sigma,
        bytes_correct,
        per_byte_correct,
    };
    (recovered_high, report)
}

#[derive(Clone, Debug)]
pub struct CacheAttackReport {
    pub n_traces: usize,
    pub noise_sigma: f64,
    pub bytes_correct: usize,
    pub per_byte_correct: [bool; 16],
}

pub fn format_cache_attack_report(
    recovered_high: &[u8; 16],
    report: &CacheAttackReport,
    true_key: &[u8; 16],
) -> String {
    let mut s = String::new();
    s.push_str("# Cache-timing attack on T-table AES (Bernstein 2005)\n\n");
    s.push_str(&format!(
        "**Traces**: {}  **Noise σ**: {:.2}\n\n",
        report.n_traces, report.noise_sigma
    ));
    s.push_str(&format!(
        "**Key-byte high nibbles correctly recovered**: {}/16  {}\n\n",
        report.bytes_correct,
        if report.bytes_correct == 16 {
            paint("✓ all high nibbles recovered", FG_BRIGHT_GREEN)
        } else if report.bytes_correct >= 12 {
            paint("≈ mostly recovered", FG_BRIGHT_YELLOW)
        } else {
            paint(
                "✗ attack fails at this noise level / trace count",
                FG_BRIGHT_RED,
            )
        }
    ));
    s.push_str("## Per-byte breakdown\n\n");
    s.push_str("| byte | true high | recovered high | ok? |\n");
    s.push_str("|----:|---------:|--------------:|:---:|\n");
    for i in 0..16 {
        s.push_str(&format!(
            "| {} | {:x} | {:x} | {} |\n",
            i,
            true_key[i] >> 4,
            recovered_high[i],
            if report.per_byte_correct[i] {
                "✓"
            } else {
                "✗"
            },
        ));
    }
    s.push('\n');
    s.push_str(
        "**Note**: this is the *high-nibble* recovery step (4 bits per byte = 64 bits of \
         key entropy cut).  The full Bernstein attack runs a second pass to recover the \
         low nibble — combined with a brute-force search over the remaining 2⁶⁴ candidates \
         it's a polynomial-time break.\n",
    );
    s
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// **Cache-line collision count**: identical key bytes → all 16
    /// round-1 lookups hit the same line iff plaintext bytes also
    /// match.  With all-zero key, varying plaintext bytes, lines
    /// accessed = number of distinct plaintext-high-nibbles.
    #[test]
    fn timing_reflects_cache_line_collisions() {
        use rand::SeedableRng;
        let mut rng = StdRng::seed_from_u64(0);
        let key = [0u8; 16];
        // Plaintext with all high nibbles = 0 → all lookups hit line 0.
        let mut p1 = [0u8; 16];
        for i in 0..16 {
            p1[i] = i as u8; // low nibbles vary but high nibble = 0
        }
        let t1 = simulate_encryption_timing(&p1, &key, 0.0, &mut rng);
        assert_eq!(t1 as u32, 1);
        // Plaintext with 16 distinct high nibbles → 16 distinct lines.
        let mut p2 = [0u8; 16];
        for i in 0..16 {
            p2[i] = (i as u8) << 4;
        }
        let t2 = simulate_encryption_timing(&p2, &key, 0.0, &mut rng);
        assert_eq!(t2 as u32, 16);
    }

    /// **Noise-free Bernstein attack** with 4 096 traces recovers
    /// all 16 high nibbles.
    #[test]
    fn bernstein_recovers_high_nibbles_no_noise() {
        let key = [0x42u8; 16];
        let (_, report) = run_bernstein_attack(&key, 4096, 0.0, 7);
        assert_eq!(report.bytes_correct, 16);
    }

    /// **Bernstein attack with moderate noise** at σ = 0.5 with 16 k
    /// traces — still reliably recovers all high nibbles.
    #[test]
    fn bernstein_recovers_with_noise() {
        let key = [
            0x2b, 0x7e, 0x15, 0x16, 0x28, 0xae, 0xd2, 0xa6, 0xab, 0xf7, 0x15, 0x88, 0x09, 0xcf,
            0x4f, 0x3c,
        ];
        let (_, report) = run_bernstein_attack(&key, 16384, 0.5, 1337);
        assert!(
            report.bytes_correct >= 14,
            "expected ≥ 14/16 high nibbles, got {}",
            report.bytes_correct
        );
    }

    /// **Demo emission**.
    #[test]
    #[ignore]
    fn demo_bernstein_cache_attack() {
        let key = [
            0x2b, 0x7e, 0x15, 0x16, 0x28, 0xae, 0xd2, 0xa6, 0xab, 0xf7, 0x15, 0x88, 0x09, 0xcf,
            0x4f, 0x3c,
        ];
        let (rec, report) = run_bernstein_attack(&key, 16384, 0.5, 1337);
        println!("\n{}", format_cache_attack_report(&rec, &report, &key));
    }
}
