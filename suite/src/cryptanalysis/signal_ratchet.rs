//! **Signal Double Ratchet KDF anomaly audit**.
//!
//! Following the same pattern as `cryptanalysis::tls12_kdf` /
//! `cryptanalysis::tls13_kdf`, but for the Signal protocol's
//! double-ratchet key derivation chain (used by Signal, WhatsApp,
//! many other modern messaging apps).  Spec:
//! <https://signal.org/docs/specifications/doubleratchet/>.
//!
//! ## The two KDFs
//!
//! Signal evolves two keys (the "root key" and the "chain key") via
//! two distinct KDFs:
//!
//! ```text
//!     KDF_RK(rk, dh_out) = HKDF-SHA256(salt = rk, ikm = dh_out,
//!                                      info = "WhisperRatchet")[..64]
//!                        → (new_rk, new_chain_key)
//!
//!     KDF_CK(ck) = (HMAC-SHA256(ck, 0x02),  HMAC-SHA256(ck, 0x01))
//!                → (new_chain_key,           message_key)
//! ```
//!
//! - `KDF_RK` runs **once per Diffie-Hellman ratchet** (each new
//!   message direction triggers a fresh DH).  Mixes the previous
//!   root key with the new shared secret.  This is the
//!   **post-compromise-security** step.
//! - `KDF_CK` runs **once per message** within a chain.  Derives the
//!   AEAD message key plus the next chain key.  This is the
//!   **forward-secrecy** step — knowledge of `ck[n]` reveals all
//!   future `ck[n+1], ck[n+2], …` and `mk[n+1], mk[n+2], …` but no
//!   past `ck[i<n]` or `mk[i≤n]` (because HMAC is one-way).
//!
//! ## What this audit probes
//!
//! 1-3 — Standard statistical battery (chi-squared / monobit /
//!       first-byte) on a corpus of message keys.
//! 4   — **Forward-secrecy correlation**: does `mk[n]` correlate
//!       with `mk[n+1]` within the same chain?  HMAC-PRF says no.
//! 5   — **Cross-chain correlation**: do message keys from
//!       independent chains correlate?  Should be uncorrelated.
//! 6   — **Post-compromise-security probe**: simulate an attacker
//!       who knows `rk`.  Run a fresh DH ratchet, check that the
//!       new `(rk', ck')` is uncorrelated with the old `rk`.
//! 7   — **Small-subgroup-confined DH** input (same as the TLS
//!       audits) — the canonical "ECDH peer chose a tiny-order
//!       point" failure mode.
//! 8   — **Within-chain autocorrelation** at lags 1..16 — checks
//!       that successive message keys aren't sliding-correlated.

use crate::cryptanalysis::statistical::{chi_squared_byte_test, monobit_test};
use crate::kdf::hkdf::{hkdf_extract, hmac_sha256};
use crate::visualize::color::{paint, FG_BRIGHT_GREEN, FG_BRIGHT_RED, FG_BRIGHT_YELLOW};

/// **KDF_RK**: root-key ratchet.  Returns `(new_rk, new_chain_key)`.
pub fn kdf_rk(rk: &[u8; 32], dh_out: &[u8]) -> ([u8; 32], [u8; 32]) {
    // HKDF-Extract(salt = rk, ikm = dh_out) gives a single 32-byte
    // PRK; then HKDF-Expand for 64 bytes split into (rk', ck).
    // For correctness against the spec we use Extract then derive
    // 64 output bytes via two HMAC iterations of Expand.
    let prk = hkdf_extract(Some(rk), dh_out);
    // Expand: T(1) = HMAC(prk, info || 0x01), T(2) = HMAC(prk, T(1) || info || 0x02).
    let info = b"WhisperRatchet";
    let mut t1_input = info.to_vec();
    t1_input.push(0x01);
    let t1 = hmac_sha256(&prk, &t1_input);
    let mut t2_input = t1.to_vec();
    t2_input.extend_from_slice(info);
    t2_input.push(0x02);
    let t2 = hmac_sha256(&prk, &t2_input);
    let mut rk_out = [0u8; 32];
    let mut ck_out = [0u8; 32];
    rk_out.copy_from_slice(&t1);
    ck_out.copy_from_slice(&t2);
    (rk_out, ck_out)
}

/// **KDF_CK**: chain-key + message-key derivation.  Returns
/// `(new_ck, message_key)`.
pub fn kdf_ck(ck: &[u8; 32]) -> ([u8; 32], [u8; 32]) {
    let mk = hmac_sha256(ck, &[0x01]);
    let new_ck = hmac_sha256(ck, &[0x02]);
    (new_ck, mk)
}

/// Audit report.
#[derive(Clone, Debug)]
pub struct AnomalyReport {
    pub n_chains: usize,
    pub messages_per_chain: usize,
    pub total_message_keys: usize,
    pub chi_squared_p_value: f64,
    pub monobit_p_value: f64,
    pub first_byte_chi_p_value: f64,
    /// Mean within-chain autocorrelation across lag-1 message keys
    /// (= correlation between `mk[i]` and `mk[i+1]` averaged over
    /// many chains).  Should be ≈ 0 under H₀ (HMAC is a PRF).
    pub mean_lag1_autocorr: f64,
    /// Maximum |Pearson r| at any lag in `1..=16`.  Should be small.
    pub max_autocorr_at_any_lag: f64,
    /// Maximum |Pearson r| between message keys from independent chains.
    pub max_cross_chain_corr: f64,
    /// PCS probe: max |Pearson r| between the OLD root key and the
    /// NEW (rk', ck') after a fresh DH ratchet.  Should be ≈ 0.
    pub pcs_max_correlation: f64,
    /// Small-subgroup-confined DH input: max |z| over output bins.
    pub small_subgroup_max_z: f64,
    /// Avalanche on DH-output bit flip → mean Hamming distance of
    /// resulting (rk', ck').
    pub mean_avalanche_bits: f64,
}

pub fn run_anomaly_audit(n_chains: usize, messages_per_chain: usize, seed: u64) -> AnomalyReport {
    use rand::rngs::StdRng;
    use rand::{RngCore, SeedableRng};
    let mut rng = StdRng::seed_from_u64(seed);

    // ── Build many chains, collect every message key ────────────────
    let mut all_keys: Vec<[u8; 32]> = Vec::with_capacity(n_chains * messages_per_chain);
    let mut chains: Vec<Vec<[u8; 32]>> = Vec::with_capacity(n_chains);
    for _ in 0..n_chains {
        let mut rk = [0u8; 32];
        let mut dh = [0u8; 32];
        rng.fill_bytes(&mut rk);
        rng.fill_bytes(&mut dh);
        let (_, mut ck) = kdf_rk(&rk, &dh);
        let mut chain_keys: Vec<[u8; 32]> = Vec::with_capacity(messages_per_chain);
        for _ in 0..messages_per_chain {
            let (new_ck, mk) = kdf_ck(&ck);
            ck = new_ck;
            all_keys.push(mk);
            chain_keys.push(mk);
        }
        chains.push(chain_keys);
    }

    // ── 1-3. Statistical battery on the concatenated corpus ─────────
    let bytes: Vec<u8> = all_keys.iter().flatten().copied().collect();
    let chi = chi_squared_byte_test(&bytes);
    let mono_dev = monobit_test(&bytes).unwrap_or(0.0);
    let n_bits = bytes.len() as f64 * 8.0;
    let mono_z = 2.0 * n_bits.sqrt() * mono_dev;
    let mono_p = 1.0 - erf(mono_z / std::f64::consts::SQRT_2);
    // First-byte chi-squared.
    let mut first = [0u64; 256];
    for k in &all_keys {
        first[k[0] as usize] += 1;
    }
    let expected = (all_keys.len() as f64) / 256.0;
    let chi_first: f64 = first
        .iter()
        .map(|&c| {
            let d = c as f64 - expected;
            d * d / expected.max(1.0)
        })
        .sum();
    let first_byte_p = chi_p_value(chi_first, 255);

    // ── 4. Within-chain lag-1 autocorrelation ───────────────────────
    let lag1_corrs: Vec<f64> = chains
        .iter()
        .map(|chain| {
            // For each chain, treat byte 0 of each mk as a univariate
            // time series and compute lag-1 autocorrelation.
            let series: Vec<u8> = chain.iter().map(|mk| mk[0]).collect();
            autocorr_at_lag(&series, 1)
        })
        .collect();
    let mean_lag1 = lag1_corrs.iter().sum::<f64>() / lag1_corrs.len().max(1) as f64;

    // Max |autocorr| at any lag 1..16, averaged across chains.
    let mut max_lag = 0.0f64;
    for chain in &chains {
        let series: Vec<u8> = chain.iter().map(|mk| mk[0]).collect();
        for lag in 1..=16usize.min(messages_per_chain.saturating_sub(1)) {
            let r = autocorr_at_lag(&series, lag).abs();
            if r > max_lag {
                max_lag = r;
            }
        }
    }

    // ── 5. Cross-chain correlation ──────────────────────────────────
    let n_pairs = (n_chains / 2).min(256);
    let mut max_cross = 0.0f64;
    for i in 0..n_pairs {
        let j = (i + n_chains / 2).min(n_chains - 1);
        let a: Vec<u8> = chains[i].iter().flatten().copied().collect();
        let b: Vec<u8> = chains[j].iter().flatten().copied().collect();
        let r = pearson_corr_bytes(&a, &b).abs();
        if r > max_cross {
            max_cross = r;
        }
    }

    // ── 6. Post-compromise-security probe ──────────────────────────
    // Attacker knows the OLD root key.  After one fresh DH ratchet,
    // the NEW (rk', ck') should be uncorrelated with the old rk.
    let n_pcs = 256.min(n_chains);
    let mut max_pcs = 0.0f64;
    for _ in 0..n_pcs {
        let mut old_rk = [0u8; 32];
        let mut fresh_dh = [0u8; 32];
        rng.fill_bytes(&mut old_rk);
        rng.fill_bytes(&mut fresh_dh);
        let (new_rk, new_ck) = kdf_rk(&old_rk, &fresh_dh);
        let r1 = pearson_corr_bytes(&old_rk, &new_rk).abs();
        let r2 = pearson_corr_bytes(&old_rk, &new_ck).abs();
        let r = r1.max(r2);
        if r > max_pcs {
            max_pcs = r;
        }
    }

    // ── 7. Small-subgroup-confined DH input ─────────────────────────
    let small_z = small_subgroup_dh_probe(1024);

    // ── 8. Avalanche on DH-bit flip ─────────────────────────────────
    let n_avalanche = 1024.min(n_chains);
    let mut total_flipped = 0u64;
    for _ in 0..n_avalanche {
        let mut rk = [0u8; 32];
        let mut dh = [0u8; 32];
        rng.fill_bytes(&mut rk);
        rng.fill_bytes(&mut dh);
        let (rk1, ck1) = kdf_rk(&rk, &dh);
        let bit = (rng.next_u32() as usize) % (32 * 8);
        dh[bit / 8] ^= 1 << (bit % 8);
        let (rk2, ck2) = kdf_rk(&rk, &dh);
        let mut hd = 0u32;
        for k in 0..32 {
            hd += (rk1[k] ^ rk2[k]).count_ones();
            hd += (ck1[k] ^ ck2[k]).count_ones();
        }
        total_flipped += hd as u64;
    }
    let mean_avalanche_bits = total_flipped as f64 / n_avalanche.max(1) as f64;

    AnomalyReport {
        n_chains,
        messages_per_chain,
        total_message_keys: all_keys.len(),
        chi_squared_p_value: chi.p_value,
        monobit_p_value: mono_p,
        first_byte_chi_p_value: first_byte_p,
        mean_lag1_autocorr: mean_lag1,
        max_autocorr_at_any_lag: max_lag,
        max_cross_chain_corr: max_cross,
        pcs_max_correlation: max_pcs,
        small_subgroup_max_z: small_z,
        mean_avalanche_bits,
    }
}

fn small_subgroup_dh_probe(set_size: usize) -> f64 {
    let rk = [0u8; 32];
    let mut counts: Vec<[u64; 256]> = vec![[0u64; 256]; 64]; // 32-byte rk' + 32-byte ck = 64 bytes per output
    for i in 0..set_size {
        let mut dh = [0u8; 32];
        let i_bytes = (i as u32).to_le_bytes();
        dh[0..4].copy_from_slice(&i_bytes);
        let (rk_out, ck_out) = kdf_rk(&rk, &dh);
        for (pos, &b) in rk_out.iter().chain(ck_out.iter()).enumerate() {
            counts[pos][b as usize] += 1;
        }
    }
    let expected = set_size as f64 / 256.0;
    let std = (expected * (255.0 / 256.0)).sqrt().max(1e-12);
    let mut max_z = 0.0f64;
    for cs in &counts {
        for &c in cs {
            let z = (c as f64 - expected).abs() / std;
            if z > max_z {
                max_z = z;
            }
        }
    }
    max_z
}

fn autocorr_at_lag(series: &[u8], lag: usize) -> f64 {
    if series.len() <= lag {
        return 0.0;
    }
    let a = &series[..series.len() - lag];
    let b = &series[lag..];
    pearson_corr_bytes(a, b)
}

fn pearson_corr_bytes(a: &[u8], b: &[u8]) -> f64 {
    let n = a.len().min(b.len());
    if n < 2 {
        return 0.0;
    }
    let mean_a: f64 = a.iter().map(|&x| x as f64).sum::<f64>() / n as f64;
    let mean_b: f64 = b.iter().map(|&x| x as f64).sum::<f64>() / n as f64;
    let mut num = 0.0;
    let mut sa = 0.0;
    let mut sb = 0.0;
    for i in 0..n {
        let da = a[i] as f64 - mean_a;
        let db = b[i] as f64 - mean_b;
        num += da * db;
        sa += da * da;
        sb += db * db;
    }
    let denom = (sa * sb).sqrt().max(1e-12);
    num / denom
}

fn chi_p_value(chi2: f64, df: usize) -> f64 {
    let df = df as f64;
    let t = ((chi2 / df).powf(1.0 / 3.0) - (1.0 - 2.0 / (9.0 * df))) / ((2.0 / (9.0 * df)).sqrt());
    0.5 * (1.0 - erf(t / std::f64::consts::SQRT_2))
}

fn erf(x: f64) -> f64 {
    let sign = x.signum();
    let x = x.abs();
    let a1 = 0.254829592;
    let a2 = -0.284496736;
    let a3 = 1.421413741;
    let a4 = -1.453152027;
    let a5 = 1.061405429;
    let p = 0.3275911;
    let t = 1.0 / (1.0 + p * x);
    let y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * (-x * x).exp();
    sign * y
}

// ── Visualization ────────────────────────────────────────────────────

pub fn format_anomaly_report(r: &AnomalyReport) -> String {
    let mut s = String::new();
    s.push_str("# Signal Double Ratchet KDF anomaly audit\n\n");
    s.push_str(&format!(
        "**Chains audited**: {}\n\
         **Messages per chain**: {}\n\
         **Total message keys collected**: {}\n\n",
        r.n_chains, r.messages_per_chain, r.total_message_keys,
    ));
    s.push_str("## Tests 1-3 — Statistical battery on message-key corpus\n\n");
    s.push_str(&format!(
        "  chi² (byte uniformity):     p = {:.4}    {}\n",
        r.chi_squared_p_value,
        verdict_p(r.chi_squared_p_value)
    ));
    s.push_str(&format!(
        "  monobit (bit balance):      p = {:.4}    {}\n",
        r.monobit_p_value,
        verdict_p(r.monobit_p_value)
    ));
    s.push_str(&format!(
        "  first-byte chi²:            p = {:.4}    {}\n\n",
        r.first_byte_chi_p_value,
        verdict_p(r.first_byte_chi_p_value)
    ));
    s.push_str("## Test 4 — Within-chain autocorrelation (forward-secrecy probe)\n\n");
    s.push_str(
        "_Hypothesis: HMAC-based ratchet step KDF_CK = (HMAC(ck, 0x02), HMAC(ck, 0x01)) \
         emits successive message keys that are independent random bytes from the \
         attacker's view._\n\n",
    );
    let lag_status = if r.mean_lag1_autocorr.abs() < 0.05 {
        paint("✓ no autocorrelation detected", FG_BRIGHT_GREEN)
    } else {
        paint("⚠ check", FG_BRIGHT_YELLOW)
    };
    s.push_str(&format!(
        "  mean lag-1 |Pearson r|:                  {:.4}    {}\n\
         max |autocorr| over lags 1..16:           {:.4}\n\n",
        r.mean_lag1_autocorr.abs(),
        lag_status,
        r.max_autocorr_at_any_lag,
    ));
    s.push_str("## Test 5 — Cross-chain correlation\n\n");
    let cross_status = if r.max_cross_chain_corr < 0.10 {
        paint("✓ chains uncorrelated", FG_BRIGHT_GREEN)
    } else {
        paint("⚠ check", FG_BRIGHT_YELLOW)
    };
    s.push_str(&format!(
        "  max |Pearson r| between independent chains: {:.4}    {}\n\n",
        r.max_cross_chain_corr, cross_status
    ));
    s.push_str("## Test 6 — Post-compromise-security probe\n\n");
    s.push_str(
        "_Hypothesis: a fresh DH ratchet (KDF_RK(rk_compromised, fresh_dh)) decorrelates \
         from the compromised root key._  Test takes the max |r| over 256 trials of two \
         32-byte correlations each (= 512 |r| values total).  Under H₀ (HKDF is a PRF), \
         max |r| ≈ √(2·ln 512)/√32 ≈ 0.62.\n\n",
    );
    let pcs_status = if r.pcs_max_correlation < 0.70 {
        paint(
            "✓ DH ratchet restores secrecy (within H₀ noise floor ≈ 0.62)",
            FG_BRIGHT_GREEN,
        )
    } else {
        paint("⚠ above H₀ noise floor", FG_BRIGHT_RED)
    };
    s.push_str(&format!(
        "  max |Pearson r| (old_rk, new_rk||new_ck):  {:.4}    {}\n\n",
        r.pcs_max_correlation, pcs_status
    ));
    s.push_str("## Test 7 — Small-subgroup-confined DH input\n\n");
    let sub_status = if r.small_subgroup_max_z < 5.0 {
        paint("✓ HKDF saturates input bias", FG_BRIGHT_GREEN)
    } else if r.small_subgroup_max_z < 8.0 {
        paint("≈ marginal", FG_BRIGHT_YELLOW)
    } else {
        paint("✗ residual bias", FG_BRIGHT_RED)
    };
    s.push_str(&format!(
        "  max |z| over (byte-pos × byte-val) bins: {:.2}σ    {}\n\n",
        r.small_subgroup_max_z, sub_status
    ));
    s.push_str("## Test 8 — Avalanche on DH bit flip\n\n");
    let ideal = 64.0 * 8.0 / 2.0; // 64-byte (rk||ck) output, ideal half flipped
    let aval_status = if (r.mean_avalanche_bits - ideal).abs() < ideal * 0.10 {
        paint("✓ ideal", FG_BRIGHT_GREEN)
    } else if (r.mean_avalanche_bits - ideal).abs() < ideal * 0.25 {
        paint("≈ close", FG_BRIGHT_YELLOW)
    } else {
        paint("✗ off", FG_BRIGHT_RED)
    };
    s.push_str(&format!(
        "  mean flipped output bits: {:.2}  (ideal ≈ {:.0})  {}\n\n",
        r.mean_avalanche_bits, ideal, aval_status
    ));
    s.push_str("---\n\n## Summary\n\n");
    // Thresholds calibrated to the H₀ noise floor of each test
    // (max-of-N statistics with the appropriate sample size).
    let strict = [
        r.chi_squared_p_value < 0.001,
        r.monobit_p_value < 0.001,
        r.first_byte_chi_p_value < 0.001,
        r.mean_lag1_autocorr.abs() > 0.10,
        r.max_cross_chain_corr > 0.30,
        r.pcs_max_correlation > 0.70, // H₀ max-of-512 |r| ≈ 0.62
        r.small_subgroup_max_z > 6.0, // H₀ max-of-16384 |z| ≈ 4.4
        (r.mean_avalanche_bits - ideal).abs() > ideal * 0.25,
    ];
    let count = strict.iter().filter(|&&x| x).count();
    if count == 0 {
        s.push_str(&format!(
            "  {} **No anomalies detected** (strict p < 0.001).  \n\
             The Signal Double Ratchet's KDF chain produces message keys that are \
             statistically indistinguishable from independent uniform random bytes, \
             both within a single chain (forward-secrecy property) and across \
             independent chains (cross-chain isolation).  The DH ratchet (KDF_RK) \
             decorrelates the new root key / chain key from any compromised \
             previous-state input — the post-compromise-security property held empirically.\n",
            paint("✓", FG_BRIGHT_GREEN)
        ));
    } else {
        s.push_str(&format!(
            "  {} **{} test(s) flagged.**  Re-seed and check stability.\n",
            paint("⚠", FG_BRIGHT_YELLOW),
            count
        ));
    }
    s
}

fn verdict_p(p: f64) -> String {
    if p > 0.05 {
        paint("✓ uniform-looking", FG_BRIGHT_GREEN)
    } else if p > 0.001 {
        paint("⚠ borderline", FG_BRIGHT_YELLOW)
    } else {
        paint("✗ significant deviation", FG_BRIGHT_RED)
    }
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// `KDF_CK` is deterministic.
    #[test]
    fn kdf_ck_deterministic() {
        let ck = [0x42u8; 32];
        let (a1, b1) = kdf_ck(&ck);
        let (a2, b2) = kdf_ck(&ck);
        assert_eq!(a1, a2);
        assert_eq!(b1, b2);
    }

    /// `KDF_CK` produces distinct chain key vs message key from the
    /// same input — the 0x01 vs 0x02 domain separation works.
    #[test]
    fn kdf_ck_separates_chain_and_message_keys() {
        let ck = [0x77u8; 32];
        let (new_ck, mk) = kdf_ck(&ck);
        assert_ne!(new_ck, mk);
    }

    /// `KDF_RK` is deterministic + produces distinct root and chain keys.
    #[test]
    fn kdf_rk_deterministic_and_separates() {
        let rk = [0x33u8; 32];
        let dh = [0x88u8; 32];
        let (a1, b1) = kdf_rk(&rk, &dh);
        let (a2, b2) = kdf_rk(&rk, &dh);
        assert_eq!(a1, a2);
        assert_eq!(b1, b2);
        assert_ne!(a1, b1);
    }

    /// **Forward-secrecy property** holds at the function level:
    /// `KDF_CK(ck)` is a one-way step.  Practically this means
    /// recovering `ck` from `(new_ck, mk)` requires inverting HMAC,
    /// which is computationally infeasible.  We can't check
    /// "infeasible" with a unit test, but we CAN check that the
    /// outputs don't trivially leak the input (e.g., XOR with input
    /// is non-zero, output is not equal to input).
    #[test]
    fn kdf_ck_does_not_trivially_leak_input() {
        let ck = [0x01u8; 32];
        let (new_ck, mk) = kdf_ck(&ck);
        // Outputs differ from input.
        assert_ne!(new_ck, ck);
        assert_ne!(mk, ck);
        // Outputs aren't trivial XOR transformations.
        let mut xored = [0u8; 32];
        for i in 0..32 {
            xored[i] = new_ck[i] ^ ck[i];
        }
        // Non-zero XOR (= input ≠ output) — sanity.
        assert!(xored.iter().any(|&b| b != 0));
    }

    /// **HEADLINE TEST**: full audit on 256 chains × 64 messages
    /// each = 16 384 message keys.
    #[test]
    fn anomaly_audit_passes() {
        let r = run_anomaly_audit(256, 64, 42);
        assert!(
            r.chi_squared_p_value > 1e-9,
            "chi²: {}",
            r.chi_squared_p_value
        );
        assert!(r.monobit_p_value > 1e-9, "monobit: {}", r.monobit_p_value);
        assert!(
            r.first_byte_chi_p_value > 1e-9,
            "first-byte: {}",
            r.first_byte_chi_p_value
        );
        assert!(
            r.mean_lag1_autocorr.abs() < 0.10,
            "lag-1 autocorr: {}",
            r.mean_lag1_autocorr
        );
        // PCS: max |r| over 256 random rk-vs-(rk',ck') pairs.  Under
        // H₀ for independent random bytes, max |r| over 256 trials
        // on N=32 is ~ √(2·ln 256)/√32 ≈ 0.42.  We allow 0.6.
        assert!(
            r.pcs_max_correlation < 0.6,
            "PCS correlation: {}",
            r.pcs_max_correlation
        );
        // Avalanche on 512-bit (rk||ck) output, ideal 256.
        assert!(
            (r.mean_avalanche_bits - 256.0).abs() < 256.0 * 0.20,
            "avalanche off: {}",
            r.mean_avalanche_bits
        );
        // Small-subgroup max |z| under H₀ ~ √(2 ln 16384) ≈ 4.4σ.
        assert!(
            r.small_subgroup_max_z < 6.5,
            "subgroup |z|: {}σ",
            r.small_subgroup_max_z
        );
    }

    /// **Demo emission** under `--nocapture`.
    #[test]
    #[ignore]
    fn demo_signal_ratchet_audit() {
        let r = run_anomaly_audit(512, 128, 1337);
        println!("{}", format_anomaly_report(&r));
    }

    /// **Multi-seed stability check** — repeat the audit 5 times.
    #[test]
    #[ignore]
    fn demo_multi_seed_stability_check() {
        println!("\n# Multi-seed stability of Signal Double Ratchet audit\n");
        println!("```");
        println!("  seed       chi²_p    monobit_p   1st-byte_p    lag1_r    pcs_r    sub_z");
        println!("  ────────   ───────   ─────────   ──────────    ──────    ─────    ─────");
        for seed in [1u64, 42, 1337, 2025, 99_999] {
            let r = run_anomaly_audit(256, 64, seed);
            println!(
                "  {:>8}    {:.4}      {:.4}        {:.4}      {:.4}    {:.4}    {:.2}",
                seed,
                r.chi_squared_p_value,
                r.monobit_p_value,
                r.first_byte_chi_p_value,
                r.mean_lag1_autocorr.abs(),
                r.pcs_max_correlation,
                r.small_subgroup_max_z,
            );
        }
        println!("```");
    }
}
