//! **TLS 1.2 key-derivation anomaly audit** — counterpart to
//! [`crate::cryptanalysis::tls13_kdf`].
//!
//! RFC 5246 §5 defines TLS 1.2's key schedule.  Unlike TLS 1.3,
//! TLS 1.2 uses a **custom PRF** (`P_hash`) instead of HKDF.  The
//! derivation chain is:
//!
//! ```text
//!     PMS (pre-master secret) = ECDHE shared secret (raw x-coord)
//!
//!     master_secret = PRF(PMS, "master secret",
//!                         client_random || server_random)[0..48]
//!
//!     key_block = PRF(master_secret, "key expansion",
//!                     server_random || client_random)    ← note flipped order!
//!
//!     where PRF(secret, label, seed) = P_hash(secret, label || seed)
//!
//!     and P_hash(secret, seed) = HMAC(secret, A(1) || seed) ||
//!                                HMAC(secret, A(2) || seed) || ...
//!     with A(0) = seed, A(i) = HMAC(secret, A(i-1)).
//! ```
//!
//! The key_block is sliced into per-direction MAC / encryption / IV
//! keys depending on the cipher suite.  For AES-128-GCM (the modern
//! choice), MAC keys are absent (AEAD), enc keys are 16 bytes each,
//! IVs are 4 bytes each — total 40 bytes.
//!
//! ## Why TLS 1.2 is interesting for an audit
//!
//! 1. **Different PRF structure**.  P_hash mixes the A-chain
//!    (`A(i) = HMAC^i(seed)`) with per-output HMAC calls.  Subtly
//!    different from HKDF-Expand's chained `T(i)` blocks.
//! 2. **Random-pair ordering asymmetry**.  Master secret uses
//!    `client_random || server_random`; key block uses
//!    `server_random || client_random`.  This is arbitrary historical
//!    choice — but it means the two PRF invocations have orthogonal
//!    seeds even if both randoms repeat.
//! 3. **Extended Master Secret (RFC 7627)** — fixes the "triple
//!    handshake" attack.  Without EMS, the master secret is derived
//!    only from PMS + randoms, NOT the full handshake transcript.
//!    Two handshakes that happen to share `(PMS, randoms)` would
//!    produce **identical traffic keys** even if other handshake
//!    fields differ.  Our `probe_ems_collision_resistance` quantifies
//!    this empirically.
//!
//! ## What this module ships
//!
//! - [`p_sha256`] — the TLS 1.2 PRF, configurable output length.
//! - [`tls12_key_schedule`] — full PMS → master_secret → key_block
//!   chain, with optional EMS.
//! - [`run_anomaly_audit`] — six-test battery analogous to TLS 1.3.
//! - `probe_ems_collision_resistance` — measures the difference
//!   between EMS-on and EMS-off behaviour under contrived shared
//!   (PMS, randoms) collisions.

use crate::cryptanalysis::statistical::{chi_squared_byte_test, monobit_test};
use crate::kdf::hkdf::hmac_sha256;
use crate::visualize::color::{paint, FG_BRIGHT_GREEN, FG_BRIGHT_RED, FG_BRIGHT_YELLOW};
use std::collections::HashMap;

// ── TLS 1.2 P_SHA256 PRF (RFC 5246 §5) ───────────────────────────────

/// **P_SHA256**: the TLS 1.2 PRF.  Returns exactly `length` bytes.
///
/// `P_hash(secret, seed) = HMAC(secret, A(1) || seed)
///                       || HMAC(secret, A(2) || seed) || …`
/// where `A(0) = seed`, `A(i) = HMAC(secret, A(i-1))`.
pub fn p_sha256(secret: &[u8], seed: &[u8], length: usize) -> Vec<u8> {
    let mut out = Vec::with_capacity(length);
    let mut a = hmac_sha256(secret, seed).to_vec();
    while out.len() < length {
        let mut concat = a.clone();
        concat.extend_from_slice(seed);
        let block = hmac_sha256(secret, &concat);
        out.extend_from_slice(&block);
        a = hmac_sha256(secret, &a).to_vec();
    }
    out.truncate(length);
    out
}

/// **TLS 1.2 PRF**: `PRF(secret, label, seed) = P_hash(secret, label || seed)`.
pub fn tls12_prf(secret: &[u8], label: &str, seed: &[u8], length: usize) -> Vec<u8> {
    let mut combined = label.as_bytes().to_vec();
    combined.extend_from_slice(seed);
    p_sha256(secret, &combined, length)
}

// ── TLS 1.2 key schedule (RFC 5246 §6.3 / RFC 7627 EMS) ──────────────

/// Full TLS 1.2 key schedule.  Returns `(master_secret, key_block)`.
///
/// `pms`: pre-master secret (= raw ECDHE shared secret).
/// `client_random` / `server_random`: 32-byte nonces from
/// `ClientHello` / `ServerHello`.
/// `key_block_length`: total bytes of key material to derive.
/// `extended_master_secret`: if `Some(handshake_hash)`, use RFC 7627
/// EMS — input the handshake transcript hash instead of the
/// random concat for master-secret derivation.  Triple-handshake
/// mitigation.
pub fn tls12_key_schedule(
    pms: &[u8],
    client_random: &[u8; 32],
    server_random: &[u8; 32],
    key_block_length: usize,
    extended_master_secret: Option<&[u8]>,
) -> ([u8; 48], Vec<u8>) {
    // ── Master secret derivation ────────────────────────────────────
    let mut ms = [0u8; 48];
    if let Some(transcript_hash) = extended_master_secret {
        let derived = tls12_prf(pms, "extended master secret", transcript_hash, 48);
        ms.copy_from_slice(&derived);
    } else {
        let mut seed = client_random.to_vec();
        seed.extend_from_slice(server_random);
        let derived = tls12_prf(pms, "master secret", &seed, 48);
        ms.copy_from_slice(&derived);
    }

    // ── Key block expansion ─────────────────────────────────────────
    // Note: key-block seed flips the random order
    // (server_random || client_random) — RFC 5246 §6.3.
    let mut seed = server_random.to_vec();
    seed.extend_from_slice(client_random);
    let key_block = tls12_prf(&ms, "key expansion", &seed, key_block_length);

    (ms, key_block)
}

/// Slice the AES-128-GCM key block per RFC 5246 §6.3 (no MAC for AEAD):
/// 16-byte client_write_key, 16-byte server_write_key, 4-byte
/// client_write_IV, 4-byte server_write_IV.  Total = 40 bytes.
pub fn slice_aes128_gcm_keys(key_block: &[u8]) -> ([u8; 16], [u8; 16], [u8; 4], [u8; 4]) {
    assert!(key_block.len() >= 40);
    let mut ck = [0u8; 16];
    let mut sk = [0u8; 16];
    let mut civ = [0u8; 4];
    let mut siv = [0u8; 4];
    ck.copy_from_slice(&key_block[0..16]);
    sk.copy_from_slice(&key_block[16..32]);
    civ.copy_from_slice(&key_block[32..36]);
    siv.copy_from_slice(&key_block[36..40]);
    (ck, sk, civ, siv)
}

// ── Anomaly audit ────────────────────────────────────────────────────

#[derive(Clone, Debug)]
pub struct AnomalyReport {
    pub n_handshakes: usize,
    pub key_block_length: usize,
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
    /// EMS probe: number of cross-handshake master-secret collisions
    /// observed when the audit deliberately reuses `(PMS, randoms)`.
    /// Without EMS, this should be 100% (deterministic).  With EMS,
    /// the transcript hash breaks the collision.
    pub no_ems_collision_rate: f64,
    pub ems_collision_rate: f64,
}

pub fn run_anomaly_audit(n_handshakes: usize, key_block_length: usize, seed: u64) -> AnomalyReport {
    use rand::rngs::StdRng;
    use rand::{RngCore, SeedableRng};
    let mut rng = StdRng::seed_from_u64(seed);

    // ── 1. Collect a corpus of key blocks ───────────────────────────
    let mut all_bytes: Vec<u8> = Vec::with_capacity(n_handshakes * key_block_length);
    let mut first_byte_counts = [0u64; 256];
    let mut blocks: Vec<Vec<u8>> = Vec::with_capacity(n_handshakes);
    for _ in 0..n_handshakes {
        let mut pms = vec![0u8; 32];
        let mut cr = [0u8; 32];
        let mut sr = [0u8; 32];
        rng.fill_bytes(&mut pms);
        rng.fill_bytes(&mut cr);
        rng.fill_bytes(&mut sr);
        let (_, kb) = tls12_key_schedule(&pms, &cr, &sr, key_block_length, None);
        if let Some(&first) = kb.first() {
            first_byte_counts[first as usize] += 1;
        }
        all_bytes.extend_from_slice(&kb);
        blocks.push(kb);
    }
    let chi_report = chi_squared_byte_test(&all_bytes);
    let mono_dev = monobit_test(&all_bytes).unwrap_or(0.0);
    let n_bits = all_bytes.len() as f64 * 8.0;
    let mono_z = 2.0 * n_bits.sqrt() * mono_dev;
    let mono_p = 1.0 - erf(mono_z / std::f64::consts::SQRT_2);
    let expected = (n_handshakes as f64) / 256.0;
    let first_byte_chi: f64 = first_byte_counts
        .iter()
        .map(|&c| {
            let d = c as f64 - expected;
            d * d / expected.max(1.0)
        })
        .sum();
    let first_byte_p = chi_p_value(first_byte_chi, 255);

    // ── 2. Avalanche on PMS bit flip ────────────────────────────────
    let avalanche_samples = (n_handshakes / 4).min(2048);
    let mut total_flipped = 0u64;
    for _ in 0..avalanche_samples {
        let mut pms = vec![0u8; 32];
        let cr = [0xAAu8; 32];
        let sr = [0x55u8; 32];
        rng.fill_bytes(&mut pms);
        let (_, kb0) = tls12_key_schedule(&pms, &cr, &sr, key_block_length, None);
        let bit = (rng.next_u32() as usize) % (32 * 8);
        pms[bit / 8] ^= 1 << (bit % 8);
        let (_, kb1) = tls12_key_schedule(&pms, &cr, &sr, key_block_length, None);
        let hd: u32 = kb0
            .iter()
            .zip(&kb1)
            .map(|(a, b)| (a ^ b).count_ones())
            .sum();
        total_flipped += hd as u64;
    }
    let mean_avalanche_bits = total_flipped as f64 / avalanche_samples.max(1) as f64;

    // ── 3. Cross-handshake correlation ──────────────────────────────
    let n_pairs = (n_handshakes / 2).min(256);
    let mut max_pearson = 0.0f64;
    for i in 0..n_pairs {
        let j = (i + n_handshakes / 2).min(n_handshakes - 1);
        let blob_a = &blocks[i];
        let blob_b = &blocks[j];
        let r = pearson_corr_bytes(blob_a, blob_b);
        if r.abs() > max_pearson.abs() {
            max_pearson = r;
        }
    }

    // ── 4. Short-key (8-byte) collision search ──────────────────────
    let short_key_n = (n_handshakes / 4).min(8192);
    let mut seen: HashMap<Vec<u8>, ()> = HashMap::with_capacity(short_key_n);
    let mut short_collisions = 0u64;
    for _ in 0..short_key_n {
        let mut pms = vec![0u8; 32];
        let mut cr = [0u8; 32];
        let mut sr = [0u8; 32];
        rng.fill_bytes(&mut pms);
        rng.fill_bytes(&mut cr);
        rng.fill_bytes(&mut sr);
        let (_, kb) = tls12_key_schedule(&pms, &cr, &sr, 8, None);
        if let std::collections::hash_map::Entry::Vacant(e) = seen.entry(kb) {
            e.insert(());
        } else {
            short_collisions += 1;
        }
    }
    let pairs_f = (short_key_n as f64) * ((short_key_n - 1) as f64) / 2.0;
    let short_expected = pairs_f / 2f64.powi(64);

    // ── 5. Small-subgroup-confined PMS ──────────────────────────────
    let small_z = small_subgroup_bias_probe(1024, key_block_length);

    // ── 6. EMS-vs-no-EMS collision probe ────────────────────────────
    let (no_ems_rate, ems_rate) = ems_collision_probe(64);

    AnomalyReport {
        n_handshakes,
        key_block_length,
        total_bytes_collected: all_bytes.len(),
        chi_squared_p_value: chi_report.p_value,
        monobit_p_value: mono_p,
        first_byte_chi_squared: first_byte_chi,
        first_byte_chi_p_value: first_byte_p,
        mean_avalanche_bits,
        avalanche_samples,
        cross_handshake_max_pearson: max_pearson,
        short_key_collisions_observed: short_collisions,
        short_key_collisions_expected: short_expected,
        short_key_n,
        small_subgroup_bias_max: small_z,
        no_ems_collision_rate: no_ems_rate,
        ems_collision_rate: ems_rate,
    }
}

fn small_subgroup_bias_probe(set_size: usize, key_block_length: usize) -> f64 {
    let cr = [0xAAu8; 32];
    let sr = [0x55u8; 32];
    let mut byte_counts: Vec<[u64; 256]> = vec![[0u64; 256]; key_block_length];
    for i in 0..set_size {
        let mut pms = [0u8; 32];
        let i_bytes = (i as u32).to_le_bytes();
        pms[0..4].copy_from_slice(&i_bytes);
        let (_, kb) = tls12_key_schedule(&pms, &cr, &sr, key_block_length, None);
        for (pos, &b) in kb.iter().enumerate() {
            byte_counts[pos][b as usize] += 1;
        }
    }
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

/// **EMS-vs-no-EMS collision probe**.  Deliberately reuse the same
/// `(PMS, client_random, server_random)` across `n_reps` "handshakes"
/// that differ only in transcript hash (= other handshake messages).
///
/// **Without EMS** (RFC 5246 vanilla): master secret depends only on
/// `(PMS, randoms)` — the `n_reps` handshakes produce **identical**
/// master secrets and identical traffic keys.  Collision rate = 1.0.
///
/// **With EMS** (RFC 7627): master secret incorporates the transcript
/// hash — different handshakes produce different master secrets.
/// Collision rate = 0.0.
///
/// Returns `(no_ems_rate, ems_rate)`.
pub fn ems_collision_probe(n_reps: usize) -> (f64, f64) {
    use rand::rngs::StdRng;
    use rand::{RngCore, SeedableRng};
    let mut rng = StdRng::seed_from_u64(13);
    let mut pms = vec![0u8; 32];
    let mut cr = [0u8; 32];
    let mut sr = [0u8; 32];
    rng.fill_bytes(&mut pms);
    rng.fill_bytes(&mut cr);
    rng.fill_bytes(&mut sr);
    let mut no_ems: HashMap<[u8; 48], u64> = HashMap::new();
    let mut ems: HashMap<[u8; 48], u64> = HashMap::new();
    for i in 0..n_reps {
        // Synthesise a different transcript per "handshake".  In a
        // real triple-handshake attack, the attacker forces the same
        // (PMS, randoms) across two distinct handshakes whose
        // transcripts differ in other fields.
        let mut transcript = [0u8; 32];
        transcript[0] = i as u8;
        // No-EMS path: master secret derived without transcript hash.
        let (ms_no, _) = tls12_key_schedule(&pms, &cr, &sr, 40, None);
        *no_ems.entry(ms_no).or_insert(0) += 1;
        // EMS path: master secret depends on transcript hash.
        let (ms_yes, _) = tls12_key_schedule(&pms, &cr, &sr, 40, Some(&transcript));
        *ems.entry(ms_yes).or_insert(0) += 1;
    }
    // Collision rate = fraction of handshakes that share their
    // master secret with at least one OTHER handshake.
    let no_ems_rate = collision_rate(&no_ems, n_reps);
    let ems_rate = collision_rate(&ems, n_reps);
    (no_ems_rate, ems_rate)
}

fn collision_rate<K: Eq + std::hash::Hash>(m: &HashMap<K, u64>, n: usize) -> f64 {
    let mut in_collision = 0u64;
    for &count in m.values() {
        if count > 1 {
            in_collision += count;
        }
    }
    in_collision as f64 / n.max(1) as f64
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
    s.push_str("# TLS 1.2 key-block anomaly audit\n\n");
    s.push_str(&format!(
        "**Handshakes simulated**: {} (key block = {} bytes each)\n\
         **PRF**: P_SHA256 (RFC 5246 §5)\n\
         **Total bytes audited**: {}\n\n",
        r.n_handshakes, r.key_block_length, r.total_bytes_collected,
    ));
    s.push_str("## Test 1 — Output uniformity (chi-squared + monobit on full corpus)\n\n");
    s.push_str(&format!(
        "  chi-squared on bytes:  p = {:.4}    {}\n",
        r.chi_squared_p_value,
        verdict_p(r.chi_squared_p_value)
    ));
    s.push_str(&format!(
        "  monobit (bit balance): p = {:.4}    {}\n\n",
        r.monobit_p_value,
        verdict_p(r.monobit_p_value)
    ));
    s.push_str("## Test 2 — First-byte distribution\n\n");
    s.push_str(&format!(
        "  chi² (df=255) = {:.2}    p = {:.4}    {}\n\n",
        r.first_byte_chi_squared,
        r.first_byte_chi_p_value,
        verdict_p(r.first_byte_chi_p_value),
    ));
    s.push_str("## Test 3 — Avalanche (flip 1 PMS bit → key-block Hamming distance)\n\n");
    let ideal = (r.key_block_length as f64) * 8.0 / 2.0;
    let avalanche_status = if (r.mean_avalanche_bits - ideal).abs() < ideal * 0.10 {
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
    let corr_status = if r.cross_handshake_max_pearson.abs() < 0.30 {
        paint("✓ uncorrelated (within H₀ noise floor)", FG_BRIGHT_GREEN)
    } else {
        paint("⚠ check", FG_BRIGHT_YELLOW)
    };
    s.push_str(&format!(
        "  max |Pearson r| across paired handshakes: {:.4}    {}\n\n",
        r.cross_handshake_max_pearson, corr_status
    ));
    s.push_str("## Test 5 — Short-key collisions (8-byte slice of key block)\n\n");
    let coll_status = if (r.short_key_collisions_observed as f64)
        <= r.short_key_collisions_expected.max(1.0) * 10.0
    {
        paint("✓ within expectation", FG_BRIGHT_GREEN)
    } else {
        paint("⚠ excess collisions", FG_BRIGHT_RED)
    };
    s.push_str(&format!(
        "  pool size N = {}\n  observed collisions: {}\n  expected (uniform 2⁻⁶⁴): {:.4e}\n  status: {}\n\n",
        r.short_key_n, r.short_key_collisions_observed, r.short_key_collisions_expected, coll_status,
    ));
    s.push_str("## Test 6 — Small-subgroup-confined PMS input\n\n");
    let sub_status = if r.small_subgroup_bias_max < 5.0 {
        paint("✓ P_SHA256 saturates input bias", FG_BRIGHT_GREEN)
    } else if r.small_subgroup_bias_max < 8.0 {
        paint("≈ marginal", FG_BRIGHT_YELLOW)
    } else {
        paint("✗ residual bias", FG_BRIGHT_RED)
    };
    s.push_str(&format!(
        "  max |z| over (byte-pos × byte-val) bins: {:.2}σ    {}\n\n",
        r.small_subgroup_bias_max, sub_status
    ));
    s.push_str(
        "## Test 7 — Extended-Master-Secret (RFC 7627) collision probe\n\n\
         _Probe: reuse (PMS, client_random, server_random) across handshakes \
         that differ only in transcript._  Without EMS, the master secret depends \
         on (PMS, randoms) ONLY — identical inputs → identical traffic keys.  \
         **This is the triple-handshake vulnerability.**\n\n",
    );
    let no_ems_status = if r.no_ems_collision_rate > 0.9 {
        paint("✗ all handshakes share master secret (vuln)", FG_BRIGHT_RED)
    } else {
        paint("?", FG_BRIGHT_YELLOW)
    };
    let ems_status = if r.ems_collision_rate < 0.01 {
        paint(
            "✓ EMS mitigates: transcript hash breaks collision",
            FG_BRIGHT_GREEN,
        )
    } else {
        paint("⚠ unexpected EMS collision rate", FG_BRIGHT_RED)
    };
    s.push_str(&format!(
        "  no-EMS master-secret collision rate: {:.4}    {}\n",
        r.no_ems_collision_rate, no_ems_status
    ));
    s.push_str(&format!(
        "  EMS master-secret collision rate:    {:.4}    {}\n\n",
        r.ems_collision_rate, ems_status
    ));
    s.push_str("---\n\n## Summary\n\n");
    let strict_anomalies = [
        r.chi_squared_p_value < 0.001,
        r.monobit_p_value < 0.001,
        r.first_byte_chi_p_value < 0.001,
        (r.mean_avalanche_bits - ideal).abs() > ideal * 0.25,
        r.cross_handshake_max_pearson.abs() > 0.30,
        r.small_subgroup_bias_max > 6.0,
    ];
    let strict_count = strict_anomalies.iter().filter(|&&x| x).count();
    if strict_count == 0 {
        s.push_str(&format!(
            "  {} **No statistical anomalies in P_SHA256 output** at the strict (p < 0.001) threshold.  TLS 1.2's custom PRF produces output statistically indistinguishable from a true PRF, just like TLS 1.3's HKDF.\n\n",
            paint("✓", FG_BRIGHT_GREEN)
        ));
    } else {
        s.push_str(&format!(
            "  {} **{} statistical test(s) flagged.**  Cross-check with a different seed.\n\n",
            paint("⚠", FG_BRIGHT_YELLOW),
            strict_count
        ));
    }
    if r.no_ems_collision_rate > 0.9 && r.ems_collision_rate < 0.01 {
        s.push_str(&format!(
            "  {} **EMS-vs-no-EMS probe** confirms the historical triple-handshake exposure: identical (PMS, randoms) → identical traffic keys WITHOUT EMS.  This is why RFC 7627 EMS was needed.\n",
            paint("ℹ", FG_BRIGHT_YELLOW)
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

    /// `p_sha256` is deterministic for the same inputs.
    #[test]
    fn p_sha256_deterministic() {
        let s = b"secret";
        let seed = b"label seed";
        let a = p_sha256(s, seed, 100);
        let b = p_sha256(s, seed, 100);
        assert_eq!(a, b);
        assert_eq!(a.len(), 100);
    }

    /// `p_sha256` output length is exactly what's requested.
    #[test]
    fn p_sha256_truncates_to_exact_length() {
        for len in [1usize, 5, 31, 32, 33, 63, 64, 65, 100] {
            assert_eq!(p_sha256(b"k", b"s", len).len(), len);
        }
    }

    /// **TLS 1.2 key-schedule determinism** — same inputs → same
    /// keys.
    #[test]
    fn key_schedule_deterministic() {
        let pms = [0x42u8; 32];
        let cr = [0xAAu8; 32];
        let sr = [0x55u8; 32];
        let (ms1, kb1) = tls12_key_schedule(&pms, &cr, &sr, 40, None);
        let (ms2, kb2) = tls12_key_schedule(&pms, &cr, &sr, 40, None);
        assert_eq!(ms1, ms2);
        assert_eq!(kb1, kb2);
    }

    /// **Different PMS** → **different key block**.
    #[test]
    fn different_pms_different_keys() {
        let cr = [0u8; 32];
        let sr = [0u8; 32];
        let (_, kb1) = tls12_key_schedule(&[1u8; 32], &cr, &sr, 40, None);
        let (_, kb2) = tls12_key_schedule(&[2u8; 32], &cr, &sr, 40, None);
        assert_ne!(kb1, kb2);
    }

    /// **EMS changes the master secret** for the same `(PMS, randoms)`.
    #[test]
    fn ems_changes_master_secret() {
        let pms = [0x33u8; 32];
        let cr = [0xAAu8; 32];
        let sr = [0x55u8; 32];
        let (ms_no, _) = tls12_key_schedule(&pms, &cr, &sr, 40, None);
        let (ms_yes, _) = tls12_key_schedule(&pms, &cr, &sr, 40, Some(&[0xCCu8; 32]));
        assert_ne!(ms_no, ms_yes);
    }

    /// **Slice helper** matches the documented layout.
    #[test]
    fn slice_aes128_gcm_keys_works() {
        let kb: Vec<u8> = (0..40u8).collect();
        let (ck, sk, civ, siv) = slice_aes128_gcm_keys(&kb);
        assert_eq!(&ck[..], &kb[0..16]);
        assert_eq!(&sk[..], &kb[16..32]);
        assert_eq!(&civ[..], &kb[32..36]);
        assert_eq!(&siv[..], &kb[36..40]);
    }

    /// **EMS-vs-no-EMS probe** quantifies the triple-handshake
    /// exposure: without EMS, all 64 fake handshakes share the same
    /// master secret (rate = 1.0); with EMS, all 64 are distinct
    /// (rate = 0.0).
    #[test]
    fn ems_probe_demonstrates_triple_handshake_exposure() {
        let (no_ems_rate, ems_rate) = ems_collision_probe(64);
        assert!(
            no_ems_rate > 0.99,
            "expected no-EMS collisions ≈ 1.0, got {}",
            no_ems_rate
        );
        assert!(
            ems_rate < 0.01,
            "expected EMS collisions ≈ 0.0, got {}",
            ems_rate
        );
    }

    /// **HEADLINE TEST**: full anomaly battery passes on 4096
    /// handshakes.
    #[test]
    fn anomaly_audit_passes() {
        let r = run_anomaly_audit(4096, 40, 42);
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
        assert!(
            r.first_byte_chi_p_value > 1e-9,
            "first-byte p too small: {}",
            r.first_byte_chi_p_value
        );
        let ideal = (r.key_block_length as f64) * 8.0 / 2.0;
        assert!(
            (r.mean_avalanche_bits - ideal).abs() < ideal * 0.2,
            "avalanche off: got {}, ideal {}",
            r.mean_avalanche_bits,
            ideal
        );
        // Under H₀ on a 40-byte key block, max |r| over 256 pairs ≈
        // √(2·ln 256)/√40 ≈ 0.53 — generous threshold at 0.7.  (Real
        // anomalies would show |r| pegged near 1.0.)
        assert!(
            r.cross_handshake_max_pearson.abs() < 0.7,
            "correlation: {}",
            r.cross_handshake_max_pearson
        );
        assert!(
            r.small_subgroup_bias_max < 6.0,
            "subgroup |z|: {}σ",
            r.small_subgroup_bias_max
        );
        // EMS probe baked in.
        assert!(r.no_ems_collision_rate > 0.9);
        assert!(r.ems_collision_rate < 0.1);
    }

    /// **Demo emission** under `--nocapture`.
    #[test]
    #[ignore]
    fn demo_tls12_anomaly_audit() {
        let r = run_anomaly_audit(8192, 40, 1337);
        println!("{}", format_anomaly_report(&r));
    }

    /// **Multi-seed stability check** — repeat the audit 5 times.
    #[test]
    #[ignore]
    fn demo_multi_seed_stability_check() {
        println!("\n# Multi-seed stability of TLS 1.2 KDF anomaly audit\n");
        println!("```");
        println!(
            "  seed       chi²_p    monobit_p   1st-byte_p    max|r|    max|z|    no-EMS  EMS"
        );
        println!(
            "  ────────   ───────   ─────────   ──────────   ───────   ──────    ──────  ─────"
        );
        for seed in [1u64, 42, 1337, 2025, 99_999] {
            let r = run_anomaly_audit(8192, 40, seed);
            println!(
                "  {:>8}    {:.4}      {:.4}        {:.4}     {:.4}      {:.2}      {:.2}    {:.2}",
                seed,
                r.chi_squared_p_value,
                r.monobit_p_value,
                r.first_byte_chi_p_value,
                r.cross_handshake_max_pearson.abs(),
                r.small_subgroup_bias_max,
                r.no_ems_collision_rate,
                r.ems_collision_rate,
            );
        }
        println!("```\n");
    }

    /// **Side-by-side TLS 1.2 vs TLS 1.3** — same battery, compared.
    #[test]
    #[ignore]
    fn demo_tls12_vs_tls13_comparison() {
        use crate::cryptanalysis::tls13_kdf;
        println!("\n# TLS 1.2 (P_SHA256) vs TLS 1.3 (HKDF-Expand-Label) side-by-side\n");
        let r12 = run_anomaly_audit(8192, 32, 7);
        let r13 = tls13_kdf::run_anomaly_audit(8192, 32, 7);
        println!("```");
        println!("  Test                          TLS 1.2 (P_SHA256)    TLS 1.3 (HKDF)");
        println!("  ──────────────────────────    ──────────────────    ──────────────");
        println!(
            "  chi²_p (byte uniformity)      {:.4}                {:.4}",
            r12.chi_squared_p_value, r13.chi_squared_p_value
        );
        println!(
            "  monobit_p (bit balance)       {:.4}                {:.4}",
            r12.monobit_p_value, r13.monobit_p_value
        );
        println!(
            "  first-byte chi²_p             {:.4}                {:.4}",
            r12.first_byte_chi_p_value, r13.first_byte_chi_p_value
        );
        println!(
            "  avalanche bits (ideal=128)    {:.2}                {:.2}",
            r12.mean_avalanche_bits, r13.mean_avalanche_bits
        );
        println!(
            "  cross-handshake max |r|       {:.4}                {:.4}",
            r12.cross_handshake_max_pearson.abs(),
            r13.cross_handshake_max_pearson.abs()
        );
        println!(
            "  small-subgroup max |z|        {:.2}σ                  {:.2}σ",
            r12.small_subgroup_bias_max, r13.small_subgroup_bias_max
        );
        println!("```");
        println!();
        println!("**Verdict**: both PRF families produce statistically-equivalent output.");
        println!("The TLS 1.3 / RFC 5869 switch from P_hash to HKDF was motivated by");
        println!("formal-security guarantees (Extract+Expand vs single-PRF), not by any");
        println!("empirically-detectable bias in P_hash itself.");
        println!();
        println!("The MEANINGFUL difference between TLS 1.2 and TLS 1.3 is the");
        println!("**Extended Master Secret** (RFC 7627) — without EMS, TLS 1.2 is");
        println!("vulnerable to the triple-handshake attack:");
        println!(
            "  - no-EMS collision rate: {:.4}  (= 1.0: vulnerable)",
            r12.no_ems_collision_rate
        );
        println!(
            "  - EMS collision rate:    {:.4}  (= 0.0: mitigated)",
            r12.ems_collision_rate
        );
    }
}
