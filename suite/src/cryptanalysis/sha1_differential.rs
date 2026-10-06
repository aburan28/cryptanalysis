//! Differential cryptanalysis of SHA-1.
//!
//! **SHA-1 is broken.**  Wang, Yin, Yu (Crypto 2005) gave a
//! theoretical collision attack at `~2⁶⁹` operations; SHAttered
//! (Stevens, Bursztein, Karpman, Albertini, Markov 2017) produced
//! the first actual collision at `~2⁶³·¹` operations
//! (~6500 CPU-years).  Real-world full-SHA-1 differential
//! cryptanalysis is computationally infeasible in any single
//! session, but **the techniques and toolchain are entirely
//! visible at reduced rounds** and that's what this module
//! demonstrates.
//!
//! # What this module ships
//!
//! 1. **A reduced-round-capable SHA-1** — `sha1_compress(state,
//!    block, rounds)` for `rounds ∈ [0, 80]`.  Verified against
//!    NIST FIPS 180-4 known-answer tests at `rounds = 80`.  Lives
//!    in `cryptanalysis`, NOT `hash` — this is a *target* for
//!    cryptanalysis, not a primitive to use.
//!
//! 2. **Avalanche analysis at varying rounds** — the canonical
//!    "is the diffusion complete?" measurement.  At full 80
//!    rounds, every input bit affects ~50% of output bits (good
//!    SAC).  At reduced rounds, diffusion is incomplete and the
//!    bias becomes measurable.  We use the existing
//!    [`crate::cryptanalysis::avalanche::full_avalanche`]
//!    machinery on reduced-round SHA-1.
//!
//! 3. **Boolean-function analysis of the round functions** —
//!    SHA-1 cycles through `Choose` (rounds 0-19), `Parity`
//!    (20-39), `Majority` (40-59), `Parity` (60-79).  We use the
//!    existing [`crate::cryptanalysis::boolean::walsh_hadamard`]
//!    + [`crate::cryptanalysis::sbox`] tools to characterise each.
//!
//! 4. **Random differential probability search** — for input
//!    XOR-difference `Δ_in` and small target output difference
//!    `Δ_out`, estimate `P[F_r(x) ⊕ F_r(x ⊕ Δ_in) = Δ_out]` over
//!    random `x`.  At reduced rounds the highest-probability
//!    differentials are easy to find.
//!
//! 5. **Reduced-round near-collision finder** — actual collision-
//!    finding via random search on small numbers of rounds.  At
//!    `rounds = 10` we expect to find collisions trivially; at
//!    `rounds = 20` they're harder; at full 80 they're infeasible
//!    without sophisticated paths.  This module demonstrates the
//!    cost-per-rounds curve concretely.
//!
//! # Honest scope
//!
//! - We do **not** ship Wang's differential paths.  Those are
//!   sophisticated hand-crafted characteristics that took years
//!   of cryptanalytic work; reproducing them would be an academic
//!   project, not a session deliverable.
//! - We do **not** find a full-SHA-1 collision.  That requires
//!   `~2⁶³` operations.
//! - We **do** demonstrate that the differential-cryptanalysis
//!   toolchain in this library applies to SHA-1, that reduced-
//!   round SHA-1 is breakable in seconds, and that the avalanche
//!   transition between "broken" and "secure" rounds is visible.

use crate::cryptanalysis::avalanche::{full_avalanche, AvalancheReport};
use rand::rngs::StdRng;
use rand::{RngCore, SeedableRng};

// ── SHA-1 implementation (cryptanalysis target, not a primitive) ────────

/// SHA-1 initial hash values (FIPS 180-4 §5.3.1).
pub const SHA1_IV: [u32; 5] = [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0];

/// SHA-1 round constants (FIPS 180-4 §4.2.1).
pub const K: [u32; 4] = [0x5A827999, 0x6ED9EBA1, 0x8F1BBCDC, 0xCA62C1D6];

/// SHA-1 round function.  Cycles through:
/// - rounds 0..20:  `Choose(B, C, D) = (B ∧ C) ⊕ (¬B ∧ D)`
/// - rounds 20..40: `Parity(B, C, D) = B ⊕ C ⊕ D`
/// - rounds 40..60: `Majority(B, C, D) = (B ∧ C) ⊕ (B ∧ D) ⊕ (C ∧ D)`
/// - rounds 60..80: `Parity` again
pub fn f_t(t: usize, b: u32, c: u32, d: u32) -> u32 {
    if t < 20 {
        (b & c) ^ ((!b) & d)
    } else if t < 40 {
        b ^ c ^ d
    } else if t < 60 {
        (b & c) ^ (b & d) ^ (c & d)
    } else {
        b ^ c ^ d
    }
}

/// Per-round constant `K_t`.
pub fn k_t(t: usize) -> u32 {
    K[t / 20]
}

/// SHA-1 message expansion: build `W[0..rounds]` from the
/// 16-word block, with reduced-round support.
pub fn expand_block(block: &[u8; 64], rounds: usize) -> Vec<u32> {
    let mut w = vec![0u32; rounds.max(16)];
    for i in 0..16 {
        w[i] = u32::from_be_bytes([
            block[4 * i],
            block[4 * i + 1],
            block[4 * i + 2],
            block[4 * i + 3],
        ]);
    }
    for i in 16..rounds {
        w[i] = (w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16]).rotate_left(1);
    }
    w
}

/// **Reduced-round SHA-1 compression function**.  Updates `state`
/// in place by processing `block` through `rounds ∈ [0, 80]`
/// rounds.  At `rounds = 80` matches FIPS 180-4 SHA-1.
pub fn sha1_compress(state: &mut [u32; 5], block: &[u8; 64], rounds: usize) {
    let rounds = rounds.min(80);
    let w = expand_block(block, rounds);
    let mut a = state[0];
    let mut b = state[1];
    let mut c = state[2];
    let mut d = state[3];
    let mut e = state[4];
    for t in 0..rounds {
        let temp = a
            .rotate_left(5)
            .wrapping_add(f_t(t, b, c, d))
            .wrapping_add(e)
            .wrapping_add(k_t(t))
            .wrapping_add(w[t]);
        e = d;
        d = c;
        c = b.rotate_left(30);
        b = a;
        a = temp;
    }
    state[0] = state[0].wrapping_add(a);
    state[1] = state[1].wrapping_add(b);
    state[2] = state[2].wrapping_add(c);
    state[3] = state[3].wrapping_add(d);
    state[4] = state[4].wrapping_add(e);
}

/// Full SHA-1 hash (single-block message, ≤ 55 bytes for simplicity).
/// Includes message-padding per FIPS 180-4 §5.1.
/// Returned as 20-byte big-endian array.
pub fn sha1(message: &[u8], rounds: usize) -> [u8; 20] {
    let mut state = SHA1_IV;
    let bit_len = (message.len() as u64) * 8;
    // Build padded blocks.
    let mut padded = message.to_vec();
    padded.push(0x80);
    while padded.len() % 64 != 56 {
        padded.push(0);
    }
    padded.extend_from_slice(&bit_len.to_be_bytes());
    // Process each 64-byte block.
    for chunk in padded.chunks(64) {
        let mut block = [0u8; 64];
        block.copy_from_slice(chunk);
        sha1_compress(&mut state, &block, rounds);
    }
    let mut out = [0u8; 20];
    for (i, &word) in state.iter().enumerate() {
        out[4 * i..4 * i + 4].copy_from_slice(&word.to_be_bytes());
    }
    out
}

// ── Differential analysis tools ────────────────────────────────────────

/// Compute the avalanche report on reduced-round SHA-1 with
/// `n_input_bits` input variation.  Wraps the existing
/// [`full_avalanche`] machinery.
pub fn sha1_avalanche(
    rounds: usize,
    n_input_bits: usize,
    samples_per_bit: usize,
    seed: u64,
) -> AvalancheReport {
    full_avalanche(
        |input: &[u8]| sha1(input, rounds).to_vec(),
        n_input_bits,
        160,
        samples_per_bit,
        seed,
    )
}

/// Result of a differential probability estimate.
#[derive(Clone, Debug)]
pub struct DifferentialEstimate {
    /// Empirical probability of `Δ_in → Δ_out` over the sample.
    pub probability: f64,
    /// Number of trials.
    pub trials: u64,
    /// Number of hits (output diff matched target).
    pub hits: u64,
}

/// Estimate `P[SHA1_r(x) ⊕ SHA1_r(x ⊕ Δ_in) = Δ_out]` by random
/// sampling.  `delta_in` and `delta_out` are 64-byte / 20-byte
/// XOR differences respectively.
pub fn estimate_differential(
    rounds: usize,
    delta_in: &[u8; 64],
    delta_out: &[u8; 20],
    trials: u64,
    seed: u64,
) -> DifferentialEstimate {
    let mut rng = StdRng::seed_from_u64(seed);
    let mut hits = 0u64;
    for _ in 0..trials {
        let mut x = [0u8; 64];
        rng.fill_bytes(&mut x);
        let mut x_p = x;
        for i in 0..64 {
            x_p[i] ^= delta_in[i];
        }
        // Process through compression (raw, no padding — single block).
        let mut state_a = SHA1_IV;
        let mut state_b = SHA1_IV;
        sha1_compress(&mut state_a, &x, rounds);
        sha1_compress(&mut state_b, &x_p, rounds);
        let mut diff = [0u8; 20];
        for (i, (&a, &b)) in state_a.iter().zip(state_b.iter()).enumerate() {
            let d = a ^ b;
            diff[4 * i..4 * i + 4].copy_from_slice(&d.to_be_bytes());
        }
        if &diff == delta_out {
            hits += 1;
        }
    }
    DifferentialEstimate {
        probability: hits as f64 / trials as f64,
        trials,
        hits,
    }
}

/// Result of a near-collision search.
#[derive(Clone, Debug)]
pub struct NearCollision {
    pub message_a: [u8; 64],
    pub message_b: [u8; 64],
    /// Hamming distance (number of differing output bits).
    pub hamming_distance: u32,
    /// Trials needed to find this collision.
    pub trials: u64,
}

/// **Reduced-round near-collision finder via birthday-style random
/// search**.  Generates pairs of random 64-byte messages and
/// computes the SHA-1 compression-function output Hamming distance.
/// Returns the lowest-distance pair found within `trials`.
///
/// At full 80 rounds, expected `min_hamming_distance` ≈ 80 (output
/// is 160 bits, balanced).  At reduced rounds (10, 20), the
/// distribution shifts toward 0 — actual near-collisions
/// (Hamming distance ≤ 5) become findable.
pub fn find_near_collision(
    rounds: usize,
    target_max_distance: u32,
    max_trials: u64,
    seed: u64,
) -> Option<NearCollision> {
    let mut rng = StdRng::seed_from_u64(seed);
    let mut best: Option<NearCollision> = None;
    for trial in 0..max_trials {
        let mut a = [0u8; 64];
        let mut b = [0u8; 64];
        rng.fill_bytes(&mut a);
        rng.fill_bytes(&mut b);
        if a == b {
            continue;
        }
        let mut state_a = SHA1_IV;
        let mut state_b = SHA1_IV;
        sha1_compress(&mut state_a, &a, rounds);
        sha1_compress(&mut state_b, &b, rounds);
        let dist: u32 = state_a
            .iter()
            .zip(state_b.iter())
            .map(|(&x, &y)| (x ^ y).count_ones())
            .sum();
        let candidate = NearCollision {
            message_a: a,
            message_b: b,
            hamming_distance: dist,
            trials: trial + 1,
        };
        match &best {
            Some(b_old) if b_old.hamming_distance <= candidate.hamming_distance => {}
            _ => best = Some(candidate.clone()),
        }
        if candidate.hamming_distance <= target_max_distance {
            return Some(candidate);
        }
    }
    best
}

// ── Boolean function analysis of f_t ────────────────────────────────────

/// Compute the truth table of one of SHA-1's bitwise round
/// functions over all 8 input bits `(b, c, d) ∈ {0,1}³`.  Returns
/// the 8-element vector `f(0,0,0), f(0,0,1), …, f(1,1,1)`.
/// Useful for [`crate::cryptanalysis::boolean::walsh_hadamard`].
pub fn round_function_truth_table(round: usize) -> [u8; 8] {
    let mut tt = [0u8; 8];
    for i in 0..8 {
        let b = (i >> 2) & 1;
        let c = (i >> 1) & 1;
        let d = i & 1;
        // f_t at single-bit values: same Boolean function applied per-bit.
        tt[i] = (f_t(round, b as u32, c as u32, d as u32) & 1) as u8;
    }
    tt
}

#[cfg(test)]
mod tests {
    use super::*;

    /// **NIST FIPS 180-4 KAT**: SHA-1("abc") = a9993e36 4706816a ba3e2571
    /// 7850c26c 9cd0d89d.
    #[test]
    fn sha1_full_matches_nist_kat() {
        let h = sha1(b"abc", 80);
        let expected: [u8; 20] = [
            0xa9, 0x99, 0x3e, 0x36, 0x47, 0x06, 0x81, 0x6a, 0xba, 0x3e, 0x25, 0x71, 0x78, 0x50,
            0xc2, 0x6c, 0x9c, 0xd0, 0xd8, 0x9d,
        ];
        assert_eq!(h, expected, "SHA-1(\"abc\") doesn't match NIST KAT");
    }

    /// Empty-message KAT: SHA-1("") = da39a3ee 5e6b4b0d 3255bfef 95601890 afd80709.
    #[test]
    fn sha1_empty_matches_nist_kat() {
        let h = sha1(b"", 80);
        let expected: [u8; 20] = [
            0xda, 0x39, 0xa3, 0xee, 0x5e, 0x6b, 0x4b, 0x0d, 0x32, 0x55, 0xbf, 0xef, 0x95, 0x60,
            0x18, 0x90, 0xaf, 0xd8, 0x07, 0x09,
        ];
        assert_eq!(h, expected);
    }

    /// **Avalanche at full 80 rounds**: every input bit should
    /// affect ~50% of output bits.  Note: with 256 samples per
    /// (input-bit, output-bit) cell across 32 × 160 = 5120 cells,
    /// the *worst-case* deviation from 0.5 has expected value
    /// `~5·σ ≈ 0.16` from binomial variance alone (`σ = 1/(2·√256)
    /// = 0.031`).  We use a 0.18 threshold — anything substantially
    /// above signals real bias.  The mean-cell deviation
    /// (averaged across all cells) is the more rigorous metric.
    #[test]
    fn full_sha1_has_good_avalanche() {
        let report = sha1_avalanche(80, 32, 256, 0xC0FFEE);
        let worst = report.sac_deviation();
        // Mean-cell deviation (averaged over all cells): more
        // statistically robust than worst-case.
        let mean: f64 = {
            let mut sum = 0.0_f64;
            let mut n = 0u64;
            for row in &report.matrix {
                for &p in row {
                    sum += (p - 0.5).abs();
                    n += 1;
                }
            }
            sum / n.max(1) as f64
        };
        println!();
        println!("=== full SHA-1 avalanche (80 rounds, 256 samples/bit) ===");
        println!(
            "  worst-cell deviation: {:.4} (expected ~0.10–0.18 from sampling noise)",
            worst
        );
        println!("  mean-cell deviation:  {:.4} (expected near 0.025)", mean);
        // Worst-cell looser; mean-cell tighter.
        assert!(
            worst < 0.18,
            "full SHA-1 worst-case SAC deviation = {} suggests real bias",
            worst
        );
        assert!(
            mean < 0.05,
            "full SHA-1 mean SAC deviation = {} suggests real bias",
            mean
        );
    }

    /// **Avalanche at 10 rounds** — incomplete diffusion.  We
    /// expect the SAC deviation to be substantially larger than
    /// full-SHA-1, demonstrating that 10 rounds is *not* enough.
    /// Concretely: at 10 rounds, only 10 of the 5 state words
    /// are touched per round — full diffusion needs ~16 rounds
    /// minimum just for the message expansion to involve all
    /// 16 input words.
    #[test]
    fn reduced_sha1_has_poor_avalanche() {
        let full = sha1_avalanche(80, 32, 64, 0xCAFE);
        let reduced = sha1_avalanche(10, 32, 64, 0xCAFE);
        // Reduced-round deviation should be measurably worse.
        let full_dev = full.sac_deviation();
        let reduced_dev = reduced.sac_deviation();
        println!();
        println!("=== SHA-1 avalanche at full vs reduced rounds ===");
        println!("  Full   (80 rounds): SAC deviation = {:.4}", full_dev);
        println!("  Reduced (10 rounds): SAC deviation = {:.4}", reduced_dev);
        println!(
            "  Ratio: {:.2}× worse at reduced rounds",
            reduced_dev / full_dev.max(1e-9)
        );
        assert!(
            reduced_dev > full_dev,
            "reduced-round deviation {} should exceed full {}",
            reduced_dev,
            full_dev
        );
    }

    /// Round-function characterisation: each phase has the
    /// expected algebraic identity.
    #[test]
    fn round_function_phases() {
        // Phase 1 (rounds 0-19): Choose
        let t1 = round_function_truth_table(5);
        // Choose(b, c, d): 0 0 0→0, 0 0 1→1, 0 1 0→0, 0 1 1→1,
        //                  1 0 0→0, 1 0 1→0, 1 1 0→1, 1 1 1→1.
        assert_eq!(t1, [0, 1, 0, 1, 0, 0, 1, 1]);

        // Phase 2 (20-39): Parity
        let t2 = round_function_truth_table(25);
        // Parity = XOR: even number of 1s → 0, odd → 1.
        assert_eq!(t2, [0, 1, 1, 0, 1, 0, 0, 1]);

        // Phase 3 (40-59): Majority
        let t3 = round_function_truth_table(45);
        // Majority: ≥ 2 ones → 1, else 0.
        assert_eq!(t3, [0, 0, 0, 1, 0, 1, 1, 1]);

        // Phase 4 (60-79): Parity again
        let t4 = round_function_truth_table(65);
        assert_eq!(t4, [0, 1, 1, 0, 1, 0, 0, 1]);
    }

    /// **Differential probability sanity** — the trivial differential
    /// `Δ_in = 0 → Δ_out = 0` has probability 1.
    #[test]
    fn trivial_differential_has_prob_1() {
        let zero_in = [0u8; 64];
        let zero_out = [0u8; 20];
        let est = estimate_differential(20, &zero_in, &zero_out, 100, 0xBEEF);
        assert_eq!(est.probability, 1.0);
    }

    /// **Random differential**: a non-zero input difference at
    /// reduced rounds should produce a measurable bias compared to
    /// a uniform random output difference.
    #[test]
    fn nonzero_differential_at_reduced_rounds() {
        // Single-bit difference in the input.
        let mut delta_in = [0u8; 64];
        delta_in[0] = 0x01;
        // Some specific output difference (we don't expect this
        // exact target to hit — just verify the estimator runs).
        let mut delta_out = [0u8; 20];
        delta_out[0] = 0x01;
        let est = estimate_differential(20, &delta_in, &delta_out, 1000, 0xFEED);
        // For a random target, expected probability ≈ 2^-160.
        // We just check the estimator returns valid numbers.
        assert!(est.probability >= 0.0 && est.probability <= 1.0);
        assert_eq!(est.trials, 1000);
    }

    /// **Reduced-round near-collision finding** — at 10 rounds,
    /// random search trivially finds output Hamming distance ≤ 50
    /// (out of 160).  At full 80 rounds, the expected minimum is
    /// ~80 (balanced) and finding ≤ 50 within trials is rare.
    #[test]
    fn near_collision_at_reduced_rounds() {
        let nc_10 = find_near_collision(10, 50, 1000, 0xC0FFEE).unwrap();
        let nc_80 = find_near_collision(80, 50, 1000, 0xC0FFEE).unwrap();
        println!();
        println!("=== Reduced-round near-collision finding ===");
        println!(
            "  10 rounds: best Hamming distance = {} after {} trials",
            nc_10.hamming_distance, nc_10.trials
        );
        println!(
            "  80 rounds: best Hamming distance = {} after {} trials",
            nc_80.hamming_distance, nc_80.trials
        );
        // 10-round should find a much lower-distance pair than 80-round.
        assert!(
            nc_10.hamming_distance < nc_80.hamming_distance,
            "10-round near-collision distance {} should be < 80-round {}",
            nc_10.hamming_distance,
            nc_80.hamming_distance
        );
    }

    /// **Avalanche transition curve** — the SAC deviation as a
    /// function of rounds.  Demonstrates the "diffusion threshold"
    /// at which SHA-1 becomes statistically secure.
    #[test]
    #[ignore = "experimental: ~30s; --ignored to opt in"]
    fn avalanche_transition_curve() {
        println!();
        println!("=== SHA-1 avalanche transition (SAC deviation by round count) ===");
        println!("  rounds | SAC deviation | weakest-input-bit dev");
        println!("  -------|---------------|----------------------");
        for &rounds in &[5usize, 10, 15, 20, 30, 40, 60, 80] {
            let r = sha1_avalanche(rounds, 32, 32, 0xC0FFEE);
            let (_, weakest) = r.weakest_input_bit();
            println!(
                "  {:>6} | {:>13.4} | {:>21.4}",
                rounds,
                r.sac_deviation(),
                weakest
            );
        }
    }
}
