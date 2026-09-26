//! **TLS 1.3 key-derivation anomaly audit**.
//!
//! RFC 8446 §7.1 defines the TLS 1.3 key schedule.  After ECDHE
//! produces a shared secret `Z`, the entire traffic-key family is
//! derived through chained HKDF calls — TLS deliberately never uses
//! `Z` directly.
//!
//! ```text
//!     0  ──► HKDF-Extract(salt=0, IKM=PSK or zeros) ─► Early Secret
//!                                                          │
//!                                                          ▼
//!                                            Derive-Secret(es, "derived", "")
//!                                                          │
//!     DHE ──► HKDF-Extract(salt=above, IKM=DHE)            │
//!                                ▼                          │
//!                          Handshake Secret ◄───────────────┘
//!                                ▼
//!                  Derive-Secret(hs, "c hs traffic", H(ClientHello||ServerHello))
//!                                ▼
//!                  HKDF-Expand-Label(secret, "key", "", key_length)
//!                                ▼
//!                          traffic_key  (the AEAD key the record layer uses)
//! ```
//!
//! ## What this module does
//!
//! Implements a simplified but RFC-faithful TLS 1.3 key schedule, runs
//! the resulting traffic keys through statistical-anomaly tests, and
//! probes for the specific failure modes one might worry about:
//!
//! 1. **Output distribution uniformity** — chi-squared, monobit, byte
//!    frequency over a corpus of derived keys.
//! 2. **First-byte bias** (the RC4-style failure mode).  HKDF should
//!    saturate this; verify empirically.
//! 3. **Avalanche** — flip one bit of the ECDHE shared secret; measure
//!    Hamming distance of the resulting traffic key.  Ideal: ~ half
//!    the output bits flip regardless of where in the input the flip
//!    landed.
//! 4. **Cross-handshake correlation** — do different (key_a, key_b)
//!    derived from independent ECDHE handshakes correlate?  Ideal: 0.
//! 5. **Short-key collision** — request `key_length = 8` instead of 32;
//!    do we hit collisions earlier than the √(2^64) ≈ 4·10⁹ birthday
//!    bound?
//! 6. **Small-subgroup-confined input** — feed HKDF a `Z` from a
//!    deliberately-confined ECDHE (small-order point); does the
//!    derived key still look uniform, or does HKDF leak the input
//!    structure?
//!
//! ## What this module does NOT do
//!
//! - Full TLS 1.3 transcript / handshake — we only model the
//!   DHE → traffic-key path, holding the PSK and transcript-hash
//!   inputs constant.
//! - Side-channel analysis of HKDF — the bias measurements here are
//!   black-box statistical tests, not side-channel attacks.

use crate::cryptanalysis::statistical::{chi_squared_byte_test, monobit_test};
use crate::kdf::hkdf::{hkdf_expand, hkdf_extract};
use crate::visualize::color::{paint, FG_BRIGHT_GREEN, FG_BRIGHT_RED, FG_BRIGHT_YELLOW};
use std::collections::HashMap;

// ── TLS 1.3 HKDF-Expand-Label (RFC 8446 §7.1) ────────────────────────

/// Build the `HkdfLabel` struct from RFC 8446 §7.1.
///
/// ```text
///     struct {
///         uint16 length = Length;
///         opaque label<7..255> = "tls13 " + Label;
///         opaque context<0..255> = Context;
///     } HkdfLabel;
/// ```
fn hkdf_label(length: u16, label: &str, context: &[u8]) -> Vec<u8> {
    let full_label = format!("tls13 {}", label);
    let mut out = Vec::new();
    out.extend_from_slice(&length.to_be_bytes());
    out.push(full_label.len() as u8);
    out.extend_from_slice(full_label.as_bytes());
    out.push(context.len() as u8);
    out.extend_from_slice(context);
    out
}

/// **HKDF-Expand-Label** as defined in RFC 8446 §7.1.
pub fn hkdf_expand_label(secret: &[u8], label: &str, context: &[u8], length: usize) -> Vec<u8> {
    let info = hkdf_label(length as u16, label, context);
    let mut prk = [0u8; 32];
    prk.copy_from_slice(secret);
    hkdf_expand(&prk, &info, length)
}

/// **Derive-Secret** from RFC 8446 §7.1 — convenience wrapper that
/// uses a transcript-hash as context.
pub fn derive_secret(secret: &[u8], label: &str, transcript_hash: &[u8]) -> [u8; 32] {
    let v = hkdf_expand_label(secret, label, transcript_hash, 32);
    let mut out = [0u8; 32];
    out.copy_from_slice(&v);
    out
}

/// **Full TLS 1.3 key schedule** simplified to the DHE → traffic-key path.
/// Returns `(client_handshake_traffic_secret, server_handshake_traffic_secret,
/// client_application_traffic_key, server_application_traffic_key)`.
///
/// `dhe_secret`: the raw ECDHE shared secret (x-coordinate or fixed
/// representation).
/// `transcript_hash`: a 32-byte SHA-256 transcript hash standing in
/// for `H(ClientHello || ServerHello || ...)`.
/// `key_length`: bytes of the final traffic keys (16 for AES-128-GCM,
/// 32 for AES-256-GCM / ChaCha20-Poly1305).
pub fn tls13_key_schedule(
    dhe_secret: &[u8],
    transcript_hash: &[u8],
    key_length: usize,
) -> (Vec<u8>, Vec<u8>, Vec<u8>, Vec<u8>) {
    // Early secret (no PSK case → use 32 zero bytes for both salt and IKM).
    let zeros = [0u8; 32];
    let early_secret = hkdf_extract(Some(&zeros), &zeros);
    // Derive-Secret(es, "derived", "")
    let empty_hash = crate::hash::sha256::sha256(b"");
    let derived_for_hs = derive_secret(&early_secret, "derived", &empty_hash);
    // Handshake secret = HKDF-Extract(salt=derived, IKM=DHE).
    let handshake_secret = hkdf_extract(Some(&derived_for_hs), dhe_secret);
    let chts = derive_secret(&handshake_secret, "c hs traffic", transcript_hash);
    let shts = derive_secret(&handshake_secret, "s hs traffic", transcript_hash);
    let derived_for_master = derive_secret(&handshake_secret, "derived", &empty_hash);
    let master_secret = hkdf_extract(Some(&derived_for_master), &zeros);
    let cats = derive_secret(&master_secret, "c ap traffic", transcript_hash);
    let sats = derive_secret(&master_secret, "s ap traffic", transcript_hash);
    // Final traffic keys (the AEAD keys the record layer uses).
    let client_key = hkdf_expand_label(&cats, "key", b"", key_length);
    let server_key = hkdf_expand_label(&sats, "key", b"", key_length);
    (chts.to_vec(), shts.to_vec(), client_key, server_key)
}

// ── Anomaly tests ────────────────────────────────────────────────────

/// Results of one anomaly-audit run.
#[derive(Clone, Debug)]
pub struct AnomalyReport {
    pub n_handshakes: usize,
    pub key_length: usize,
    pub total_bytes_collected: usize,
    pub chi_squared_p_value: f64,
    pub monobit_p_value: f64,
    pub first_byte_chi_squared: f64,
    pub first_byte_chi_p_value: f64,
    pub mean_avalanche_bits: f64,
    pub avalanche_samples: usize,
    pub cross_handshake_max_pearson: f64,
    pub short_key_collisions_observed: u64,
    pub short_key_collisions_expected: f64,
    pub short_key_n: usize,
    pub small_subgroup_bias_max: f64,
}

/// **Run the full anomaly battery**.  Returns a structured report.
pub fn run_anomaly_audit(n_handshakes: usize, key_length: usize, seed: u64) -> AnomalyReport {
    use rand::rngs::StdRng;
    use rand::{RngCore, SeedableRng};
    let mut rng = StdRng::seed_from_u64(seed);
    let transcript_hash = [0xAAu8; 32];
    // ── 1. Collect a large corpus of derived keys ───────────────────
    let mut all_bytes: Vec<u8> = Vec::with_capacity(n_handshakes * key_length);
    let mut first_byte_counts = [0u64; 256];
    let mut keys: Vec<Vec<u8>> = Vec::with_capacity(n_handshakes);
    for _ in 0..n_handshakes {
        let mut dhe = vec![0u8; 32];
        rng.fill_bytes(&mut dhe);
        let (_, _, ck, _) = tls13_key_schedule(&dhe, &transcript_hash, key_length);
        if let Some(&first) = ck.first() {
            first_byte_counts[first as usize] += 1;
        }
        all_bytes.extend_from_slice(&ck);
        keys.push(ck);
    }
    // Chi-squared + monobit over the whole corpus.
    let chi_report = chi_squared_byte_test(&all_bytes);
    // monobit_test returns the *absolute deviation* `|0.5 - ones/n|`,
    // NOT a p-value.  Convert: z = 2·√n · deviation, then two-sided
    // normal-tail p = 2·(1 − Φ(|z|)).
    let mono_dev = monobit_test(&all_bytes).unwrap_or(0.0);
    let n_bits = all_bytes.len() as f64 * 8.0;
    let mono_z = 2.0 * n_bits.sqrt() * mono_dev;
    let mono_p = 1.0 - erf(mono_z / std::f64::consts::SQRT_2);
    // First-byte chi-squared.
    let expected = (n_handshakes as f64) / 256.0;
    let first_byte_chi: f64 = first_byte_counts
        .iter()
        .map(|&c| {
            let d = c as f64 - expected;
            d * d / expected.max(1.0)
        })
        .sum();
    let first_byte_p = chi_p_value(first_byte_chi, 255);

    // ── 2. Avalanche test ───────────────────────────────────────────
    let avalanche_samples = (n_handshakes / 4).min(2048);
    let mut total_flipped_bits = 0u64;
    for _ in 0..avalanche_samples {
        let mut dhe = vec![0u8; 32];
        rng.fill_bytes(&mut dhe);
        let (_, _, k0, _) = tls13_key_schedule(&dhe, &transcript_hash, key_length);
        // Flip one random bit of the DHE secret.
        let bit = (rng.next_u32() as usize) % (32 * 8);
        dhe[bit / 8] ^= 1 << (bit % 8);
        let (_, _, k1, _) = tls13_key_schedule(&dhe, &transcript_hash, key_length);
        let hd: u32 = k0.iter().zip(&k1).map(|(a, b)| (a ^ b).count_ones()).sum();
        total_flipped_bits += hd as u64;
    }
    let mean_avalanche_bits = total_flipped_bits as f64 / avalanche_samples.max(1) as f64;

    // ── 3. Cross-handshake correlation ──────────────────────────────
    // For each pair, derive a long (256-byte) blob via
    // HKDF-Expand-Label so the Pearson statistic isn't dominated by
    // small-N variance.  Random independent keys at N = 256 give
    // |r| ≈ 1/√256 ≈ 0.06 under H0; the threshold below should leave
    // room for that natural noise floor.
    let n_pairs = (n_handshakes / 2).min(256);
    let mut sum_abs_pearson = 0.0f64;
    let mut max_pearson = 0.0f64;
    for i in 0..n_pairs {
        let j = (i + n_handshakes / 2).min(n_handshakes - 1);
        // Re-derive 256-byte blobs from each handshake's master secret
        // by reusing its first 32 bytes as the PRK.
        let blob_a = hkdf_expand_label(&keys[i][..keys[i].len().min(32)], "blob", b"", 256);
        let blob_b = hkdf_expand_label(&keys[j][..keys[j].len().min(32)], "blob", b"", 256);
        let r = pearson_corr_bytes(&blob_a, &blob_b);
        sum_abs_pearson += r.abs();
        if r.abs() > max_pearson.abs() {
            max_pearson = r;
        }
    }
    let mean_abs_pearson = sum_abs_pearson / n_pairs.max(1) as f64;
    let _ = mean_abs_pearson;

    // ── 4. Short-key collision search ───────────────────────────────
    let short_key_n = (n_handshakes / 4).min(8192);
    let short_key_collisions = short_key_collision_count(&mut rng, short_key_n, &transcript_hash);
    // Expected collisions under uniform distribution: C(N, 2) · 2^{-64}.
    let pairs = (short_key_n as f64) * ((short_key_n - 1) as f64) / 2.0;
    let short_key_expected = pairs / 2f64.powi(64);

    // ── 5. Small-subgroup-confined input ────────────────────────────
    // 1024 distinct *structured* inputs (single-byte-varying DHEs).
    // 1024 derived keys across 256 byte-bins gives expected count 4
    // per bin — enough for the chi² to be informative without
    // discretization dominating.
    let small_bias = small_subgroup_bias_probe(1024, &transcript_hash, key_length);

    AnomalyReport {
        n_handshakes,
        key_length,
        total_bytes_collected: all_bytes.len(),
        chi_squared_p_value: chi_report.p_value,
        monobit_p_value: mono_p,
        first_byte_chi_squared: first_byte_chi,
        first_byte_chi_p_value: first_byte_p,
        mean_avalanche_bits,
        avalanche_samples,
        cross_handshake_max_pearson: max_pearson,
        short_key_collisions_observed: short_key_collisions,
        short_key_collisions_expected: short_key_expected,
        short_key_n,
        small_subgroup_bias_max: small_bias,
    }
}

/// Search for collisions when traffic key length = 8 bytes (= 64 bits).
fn short_key_collision_count(
    rng: &mut impl rand::RngCore,
    n: usize,
    transcript_hash: &[u8; 32],
) -> u64 {
    let mut seen: HashMap<Vec<u8>, ()> = HashMap::with_capacity(n);
    let mut collisions = 0u64;
    for _ in 0..n {
        let mut dhe = vec![0u8; 32];
        rng.fill_bytes(&mut dhe);
        let (_, _, k, _) = tls13_key_schedule(&dhe, transcript_hash, 8);
        if let std::collections::hash_map::Entry::Vacant(e) = seen.entry(k) {
            e.insert(());
        } else {
            collisions += 1;
        }
    }
    collisions
}

/// Probe what happens when the ECDHE shared secret is confined to a
/// tiny set.  In a real implementation this can happen if the peer
/// chose a small-subgroup point.  Measures max per-byte bias of the
/// derived key averaged across the confined input set.
fn small_subgroup_bias_probe(
    set_size: usize,
    transcript_hash: &[u8; 32],
    key_length: usize,
) -> f64 {
    // Synthesize `set_size` deliberately structured DHE inputs (each
    // a 32-byte buffer of `(i, i, …, i)` — minimal entropy).  Derive
    // keys; measure how much the output bytes deviate from uniform.
    // Statistic: max chi²-normalized bias over (byte-position × byte-value)
    // bins.  Under H0 ("HKDF saturates input bias"), the bias matches
    // what you'd get from `set_size` truly random uniform bytes per
    // bin — bounded by the binomial fluctuation.
    let mut byte_counts: Vec<[u64; 256]> = vec![[0u64; 256]; key_length];
    for i in 0..set_size {
        let mut dhe = [0u8; 32];
        // Make the input structured but DISTINCT: low 4 bytes carry
        // the index `i` (32 bits of variation), other 28 bytes fixed.
        // This is the "small-subgroup" model: low-entropy DHE source.
        let i_bytes = (i as u32).to_le_bytes();
        dhe[0..4].copy_from_slice(&i_bytes);
        let (_, _, k, _) = tls13_key_schedule(&dhe, transcript_hash, key_length);
        for (pos, &b) in k.iter().enumerate() {
            byte_counts[pos][b as usize] += 1;
        }
    }
    // Under H0: count ~ Binomial(set_size, 1/256), so std ≈
    // √(set_size · (255/256²)) ≈ √(set_size/256).
    // We report max |z| across all bins.
    let expected = set_size as f64 / 256.0;
    let std = (expected * (255.0 / 256.0)).sqrt().max(1e-12);
    let mut max_z = 0.0f64;
    for counts in &byte_counts {
        for &c in counts {
            let z = (c as f64 - expected).abs() / std;
            if z > max_z {
                max_z = z;
            }
        }
    }
    max_z
}

fn pearson_corr_bytes(a: &[u8], b: &[u8]) -> f64 {
    let n = a.len().min(b.len());
    if n == 0 {
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

/// Crude chi-squared survival-function approximation for `df` degrees
/// of freedom.  Wilson-Hilferty transform.
fn chi_p_value(chi2: f64, df: usize) -> f64 {
    let df = df as f64;
    let t = ((chi2 / df).powf(1.0 / 3.0) - (1.0 - 2.0 / (9.0 * df))) / ((2.0 / (9.0 * df)).sqrt());
    // Convert one-sided z to upper-tail probability.
    0.5 * (1.0 - erf(t / std::f64::consts::SQRT_2))
}

/// Abramowitz–Stegun 7.1.26 approximation to `erf`.
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
    s.push_str("# TLS 1.3 traffic-key anomaly audit\n\n");
    s.push_str(&format!(
        "**Handshakes simulated**: {} (key length = {} bytes each)\n\
         **Total bytes audited**: {}\n\n",
        r.n_handshakes, r.key_length, r.total_bytes_collected,
    ));
    s.push_str("## Test 1 — Output uniformity (chi-squared + monobit on full corpus)\n\n");
    let verdict_chi = verdict_p(r.chi_squared_p_value);
    let verdict_mono = verdict_p(r.monobit_p_value);
    s.push_str(&format!(
        "  chi-squared on bytes:  p = {:.4}    {}\n",
        r.chi_squared_p_value, verdict_chi
    ));
    s.push_str(&format!(
        "  monobit (bit balance): p = {:.4}    {}\n\n",
        r.monobit_p_value, verdict_mono
    ));
    s.push_str("## Test 2 — First-byte distribution (the RC4-style failure mode)\n\n");
    let verdict_fb = verdict_p(r.first_byte_chi_p_value);
    s.push_str(&format!(
        "  chi² (df=255) = {:.2}    p = {:.4}    {}\n\n",
        r.first_byte_chi_squared, r.first_byte_chi_p_value, verdict_fb,
    ));
    s.push_str("## Test 3 — Avalanche (flip 1 input bit → output Hamming distance)\n\n");
    let ideal = (r.key_length as f64 * 8.0) / 2.0;
    let avalanche_status = if (r.mean_avalanche_bits - ideal).abs() < ideal * 0.1 {
        paint("✓ ideal", FG_BRIGHT_GREEN)
    } else if (r.mean_avalanche_bits - ideal).abs() < ideal * 0.25 {
        paint("≈ close", FG_BRIGHT_YELLOW)
    } else {
        paint("✗ off", FG_BRIGHT_RED)
    };
    s.push_str(&format!(
        "  mean flipped output bits: {:.2}  (ideal ≈ {:.1})  {}\n",
        r.mean_avalanche_bits, ideal, avalanche_status
    ));
    s.push_str(&format!("  samples: {}\n\n", r.avalanche_samples));
    s.push_str("## Test 4 — Cross-handshake correlation\n\n");
    // Under H₀ (independent 256-byte derivatives), max |r| over 256
    // pairs is approximately √(2·ln 256)/√256 ≈ 0.21.  Threshold of
    // 0.30 leaves room for the natural noise floor.
    let corr_status = if r.cross_handshake_max_pearson.abs() < 0.30 {
        paint(
            "✓ uncorrelated (within H₀ noise floor ≈ 0.21)",
            FG_BRIGHT_GREEN,
        )
    } else {
        paint("⚠ check", FG_BRIGHT_YELLOW)
    };
    s.push_str(&format!(
        "  max |Pearson r| across paired handshakes: {:.4}    {}\n\n",
        r.cross_handshake_max_pearson, corr_status
    ));
    s.push_str("## Test 5 — Short-key collisions (8-byte keys)\n\n");
    s.push_str(&format!(
        "  pool size N = {}\n  observed collisions: {}\n  expected (uniform 2⁻⁶⁴): {:.4e}\n  status: {}\n\n",
        r.short_key_n,
        r.short_key_collisions_observed,
        r.short_key_collisions_expected,
        if (r.short_key_collisions_observed as f64) <= r.short_key_collisions_expected.max(1.0) * 10.0 {
            paint("✓ within expectation", FG_BRIGHT_GREEN)
        } else {
            paint("⚠ excess collisions", FG_BRIGHT_RED)
        }
    ));
    s.push_str("## Test 6 — Small-subgroup-confined ECDHE input\n\n");
    // Under H0, max |z| over (key_length × 256) bins follows roughly
    // Gumbel.  For 32 × 256 = 8192 bins, the expected max |z| is
    // about Φ⁻¹(1 - 1/(2·8192)) ≈ 4.3, with rare excursions to ~5.
    // So anything below ~5 is consistent with random.
    let sub_status = if r.small_subgroup_bias_max < 5.0 {
        paint("✓ HKDF saturates input bias", FG_BRIGHT_GREEN)
    } else if r.small_subgroup_bias_max < 8.0 {
        paint("≈ marginal — at noise-floor edge", FG_BRIGHT_YELLOW)
    } else {
        paint("✗ residual bias from structured input", FG_BRIGHT_RED)
    };
    s.push_str(&format!(
        "  max |z| over (byte-pos × byte-val) bins: {:.2}σ    {}\n  (under H₀ for 32 × 256 bins, expected max ≈ 4.3σ; >5σ flags non-uniformity)\n\n",
        r.small_subgroup_bias_max, sub_status
    ));
    s.push_str("---\n\n## Summary\n\n");
    // A "real" anomaly = p ≪ 0.05 (we use 0.001 as the strict
    // threshold; weaker flags at p < 0.05 are expected from the
    // multiple-testing problem across 6 tests).
    let anomalies = [
        r.chi_squared_p_value < 0.001,
        r.monobit_p_value < 0.001,
        r.first_byte_chi_p_value < 0.001,
        (r.mean_avalanche_bits - ideal).abs() > ideal * 0.25,
        r.cross_handshake_max_pearson.abs() > 0.30,
        r.small_subgroup_bias_max > 6.0,
    ];
    let count = anomalies.iter().filter(|&&x| x).count();
    if count == 0 {
        s.push_str(&format!(
            "  {} **No anomalies detected** at the strict (p < 0.001) threshold.\n\n\
             TLS 1.3's HKDF Extract+Expand chain produces traffic keys statistically \
             indistinguishable from a true PRF.  Per-test 'borderline' flags at \
             p < 0.05 are expected from multiple-testing variance and disappear \
             when the audit is re-seeded.  Run `demo_multi_seed_stability_check` \
             to confirm.\n",
            paint("✓", FG_BRIGHT_GREEN)
        ));
    } else {
        s.push_str(&format!(
            "  {} **{} test(s) flagged.**  Re-run with a different seed; if the same \
             column trips again, it's a real anomaly.  Otherwise it's multiple-testing noise.\n",
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

    /// HKDF-Expand-Label produces deterministic output.
    #[test]
    fn hkdf_expand_label_deterministic() {
        let secret = [0u8; 32];
        let a = hkdf_expand_label(&secret, "key", b"", 16);
        let b = hkdf_expand_label(&secret, "key", b"", 16);
        assert_eq!(a, b);
        assert_eq!(a.len(), 16);
    }

    /// Different labels → different keys.
    #[test]
    fn hkdf_expand_label_separates_labels() {
        let secret = [1u8; 32];
        let a = hkdf_expand_label(&secret, "key", b"", 16);
        let b = hkdf_expand_label(&secret, "iv", b"", 16);
        assert_ne!(a, b);
    }

    /// **Full key-schedule round-trip**: same DHE + same transcript →
    /// same 4 traffic keys.  Different DHE → different keys.
    #[test]
    fn key_schedule_is_deterministic() {
        let dhe = [0x42u8; 32];
        let th = [0xAAu8; 32];
        let (a1, b1, c1, d1) = tls13_key_schedule(&dhe, &th, 32);
        let (a2, b2, c2, d2) = tls13_key_schedule(&dhe, &th, 32);
        assert_eq!(a1, a2);
        assert_eq!(b1, b2);
        assert_eq!(c1, c2);
        assert_eq!(d1, d2);
    }

    #[test]
    fn key_schedule_different_dhe_different_keys() {
        let th = [0xAAu8; 32];
        let (_, _, c1, _) = tls13_key_schedule(&[0x42u8; 32], &th, 32);
        let (_, _, c2, _) = tls13_key_schedule(&[0x43u8; 32], &th, 32);
        assert_ne!(c1, c2);
    }

    /// **HEADLINE TEST**: run the full anomaly battery on 4096
    /// handshakes.  Verify all 6 tests pass (no anomalies found).
    #[test]
    fn anomaly_audit_passes() {
        let r = run_anomaly_audit(4096, 32, 42);
        // Uniformity p-values should not be ridiculously small.
        assert!(
            r.chi_squared_p_value > 1e-9,
            "chi² p too small: {}",
            r.chi_squared_p_value
        );
        assert!(
            r.monobit_p_value > 1e-9,
            "monobit p too small: {}",
            r.monobit_p_value
        );
        // First-byte chi² p > tiny threshold.
        assert!(
            r.first_byte_chi_p_value > 1e-9,
            "first-byte chi² p too small: {}",
            r.first_byte_chi_p_value
        );
        // Avalanche close to half output bits.
        let ideal = (r.key_length as f64) * 8.0 / 2.0;
        assert!(
            (r.mean_avalanche_bits - ideal).abs() < ideal * 0.2,
            "avalanche off: got {}, ideal {}",
            r.mean_avalanche_bits,
            ideal
        );
        // No cross-handshake correlation.
        assert!(
            r.cross_handshake_max_pearson.abs() < 0.25,
            "unexpected cross-handshake correlation: {}",
            r.cross_handshake_max_pearson
        );
        // Small-subgroup max |z| over 32·256 = 8192 bins under H0
        // follows roughly Gumbel(√(2·ln 8192) ≈ 4.24σ).  We allow
        // up to 6σ as a generous noise margin; anything past that
        // would indicate a real residual bias from the structured
        // input.
        assert!(
            r.small_subgroup_bias_max < 6.0,
            "subgroup max |z| exceeds 6σ Gumbel limit: {}",
            r.small_subgroup_bias_max
        );
    }

    /// **Demo emission**: print the full report under `--nocapture`.
    #[test]
    #[ignore]
    fn demo_tls13_anomaly_audit() {
        let r = run_anomaly_audit(8192, 32, 1337);
        println!("{}", format_anomaly_report(&r));
    }

    /// **Multi-seed stability check** — repeat the audit at 5 different
    /// RNG seeds.  If any individual test fails consistently across
    /// seeds → real anomaly.  If failures rotate (different test fails
    /// at different seeds) → false-positive at the chosen threshold.
    #[test]
    #[ignore]
    fn demo_multi_seed_stability_check() {
        println!("\n# Multi-seed stability of TLS 1.3 KDF anomaly audit\n");
        println!("Each row is one independent audit run.  An anomaly is *real* iff");
        println!("the same column shows p ≪ 0.05 across most/all rows.\n");
        println!("```");
        println!("  seed       chi²_p    monobit_p   1st-byte_p    max|r|    max|z|");
        println!("  ────────   ───────   ─────────   ──────────   ───────   ──────");
        for seed in [1u64, 42, 1337, 2025, 99_999] {
            let r = run_anomaly_audit(8192, 32, seed);
            println!(
                "  {:>8}    {:.4}      {:.4}        {:.4}     {:.4}      {:.2}",
                seed,
                r.chi_squared_p_value,
                r.monobit_p_value,
                r.first_byte_chi_p_value,
                r.cross_handshake_max_pearson.abs(),
                r.small_subgroup_bias_max,
            );
        }
        println!("```\n");
        println!("Under the null hypothesis (HKDF is a PRF), each p-value column should be");
        println!("approximately uniform on [0, 1]; flags below p < 0.05 should occur ~1 in 20");
        println!("rows by chance, not in every row.");
    }
}
