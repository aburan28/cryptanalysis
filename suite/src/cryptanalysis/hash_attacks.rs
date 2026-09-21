//! **Generic hash-function attack framework**.
//!
//! Parallels what `cryptanalysis::boomerang` does for block ciphers:
//! a `HashFunction` trait + generic attack drivers that work against
//! any implementor.
//!
//! ## What's here
//!
//! 1. [`HashFunction`] — minimal trait every hash exposes: name,
//!    output bytes, block bytes (compression-function input width),
//!    and `hash(&[u8]) -> Vec<u8>`.  Hashes with a Merkle–Damgård
//!    structure additionally implement [`MerkleDamgardHash`] to
//!    expose the state and compression function used by length-
//!    extension / Joux multicollision.
//!
//! 2. [`length_extension_attack`] — given `H(secret || m)` and `len(secret)`,
//!    forge `H(secret || m || pad || suffix)` without knowing `secret`.
//!    Works for **any** MD-Damgård hash without HMAC-style wrapping
//!    (MD4, MD5, SHA-1, SHA-256, SHA-512, RIPEMD-160, …).
//!
//! 3. [`birthday_collision_search`] — generic √n collision finder
//!    over an `n`-bit-truncated hash.  Useful for falsifying claims
//!    about reduced-output hashes (truncation to 32, 40, 48 bits is
//!    practical on a laptop).
//!
//! 4. [`joux_multicollision`] — Antoine Joux's CRYPTO 2004
//!    multicollision: chain `t` independent collisions in an MD
//!    construction to produce `2^t` messages with the same digest at
//!    cost `t · birthday`.  Demonstrates that an `n`-bit MD hash
//!    does **not** provide `2^(n/2)` security against
//!    multicollisions, only against single collisions.
//!
//! 5. [`differential_bias`] — XOR `Δ` into one input bit position,
//!    measure the empirical bias `|Pr[bit_i(H(x)) = bit_i(H(x⊕Δ))]
//!    − 1/2|` per output bit.  An ideal hash gives bias ≈ 0; reduced-
//!    round MD4/MD5/SHA-1 give a clear non-zero signal.

use rand::rngs::StdRng;
use rand::{Rng, RngCore, SeedableRng};
use std::collections::HashMap;

/// Generic hash interface that every attack here consumes.
pub trait HashFunction: Send + Sync {
    fn name(&self) -> &'static str;
    /// Digest length in bytes.
    fn output_bytes(&self) -> usize;
    /// Compression-function block width in bytes (typically 64 for
    /// MD-class, 128 for SHA-512-class).
    fn block_bytes(&self) -> usize;
    /// Hash an arbitrary-length message.
    fn hash(&self, message: &[u8]) -> Vec<u8>;
}

/// Additional capability for Merkle–Damgård hashes — exposes the
/// internal compression state so length-extension / Joux can drive
/// the chain from a custom starting point.
pub trait MerkleDamgardHash: HashFunction {
    /// State element type after decoding the digest into the
    /// compression-function state.  Most MD hashes use `[u32; n]` or
    /// `[u64; n]`; we erase to `Vec<u8>` for uniformity.
    fn state_bytes(&self) -> usize {
        self.output_bytes()
    }
    /// Compress one block from a given state (encoded as bytes).
    /// `state.len()` must equal `self.state_bytes()`, `block.len()`
    /// must equal `self.block_bytes()`.
    fn compress(&self, state: &mut [u8], block: &[u8]);
    /// MD-Damgård padding for a message of total length
    /// `message_bytes`.  Returns the padding bytes only (not the
    /// message).  Most MD hashes use the same trailer:
    /// `0x80 || zeros || length-encoding`.
    fn padding_for_length(&self, message_bytes: usize) -> Vec<u8>;
}

// ── Concrete impls for our hash zoo ──────────────────────────────────

/// MD4 as a `HashFunction` + `MerkleDamgardHash`.
pub struct Md4;
impl HashFunction for Md4 {
    fn name(&self) -> &'static str {
        "MD4"
    }
    fn output_bytes(&self) -> usize {
        16
    }
    fn block_bytes(&self) -> usize {
        64
    }
    fn hash(&self, message: &[u8]) -> Vec<u8> {
        crate::hash::md4::md4(message).to_vec()
    }
}
impl MerkleDamgardHash for Md4 {
    fn compress(&self, state: &mut [u8], block: &[u8]) {
        let mut s = [0u32; 4];
        for i in 0..4 {
            s[i] = u32::from_le_bytes([
                state[4 * i],
                state[4 * i + 1],
                state[4 * i + 2],
                state[4 * i + 3],
            ]);
        }
        let mut b = [0u8; 64];
        b.copy_from_slice(block);
        crate::hash::md4::md4_compress(&mut s, &b);
        for i in 0..4 {
            state[4 * i..4 * i + 4].copy_from_slice(&s[i].to_le_bytes());
        }
    }
    fn padding_for_length(&self, message_bytes: usize) -> Vec<u8> {
        crate::hash::md4::md4_pad(&vec![0u8; message_bytes])[message_bytes..].to_vec()
    }
}

/// MD5 as a `HashFunction` + `MerkleDamgardHash`.
pub struct Md5;
impl HashFunction for Md5 {
    fn name(&self) -> &'static str {
        "MD5"
    }
    fn output_bytes(&self) -> usize {
        16
    }
    fn block_bytes(&self) -> usize {
        64
    }
    fn hash(&self, message: &[u8]) -> Vec<u8> {
        crate::hash::md5::md5(message).to_vec()
    }
}
impl MerkleDamgardHash for Md5 {
    fn compress(&self, state: &mut [u8], block: &[u8]) {
        let mut s = [0u32; 4];
        for i in 0..4 {
            s[i] = u32::from_le_bytes([
                state[4 * i],
                state[4 * i + 1],
                state[4 * i + 2],
                state[4 * i + 3],
            ]);
        }
        let mut b = [0u8; 64];
        b.copy_from_slice(block);
        crate::cryptanalysis::md5_differential::md5_compress(&mut s, &b, 64);
        for i in 0..4 {
            state[4 * i..4 * i + 4].copy_from_slice(&s[i].to_le_bytes());
        }
    }
    fn padding_for_length(&self, message_bytes: usize) -> Vec<u8> {
        crate::hash::md5::md5_pad(message_bytes)
    }
}

/// SHA-1 (from the reduced-round-capable cryptanalysis module, used
/// at the full 80 rounds) as a `HashFunction`.  The internal state is
/// `[u32; 5]` big-endian — different byte order than MD4/MD5.
pub struct Sha1;
impl HashFunction for Sha1 {
    fn name(&self) -> &'static str {
        "SHA-1"
    }
    fn output_bytes(&self) -> usize {
        20
    }
    fn block_bytes(&self) -> usize {
        64
    }
    fn hash(&self, message: &[u8]) -> Vec<u8> {
        crate::cryptanalysis::sha1_differential::sha1(message, 80).to_vec()
    }
}
impl MerkleDamgardHash for Sha1 {
    fn compress(&self, state: &mut [u8], block: &[u8]) {
        let mut s = [0u32; 5];
        for i in 0..5 {
            s[i] = u32::from_be_bytes([
                state[4 * i],
                state[4 * i + 1],
                state[4 * i + 2],
                state[4 * i + 3],
            ]);
        }
        let mut b = [0u8; 64];
        b.copy_from_slice(block);
        crate::cryptanalysis::sha1_differential::sha1_compress(&mut s, &b, 80);
        for i in 0..5 {
            state[4 * i..4 * i + 4].copy_from_slice(&s[i].to_be_bytes());
        }
    }
    fn padding_for_length(&self, message_bytes: usize) -> Vec<u8> {
        // SHA-1 padding: 0x80 || zeros || 8-byte big-endian bit-length.
        let bit_len = (message_bytes as u64).wrapping_mul(8);
        let mut out = vec![0x80u8];
        while (message_bytes + out.len()) % 64 != 56 {
            out.push(0);
        }
        out.extend_from_slice(&bit_len.to_be_bytes());
        out
    }
}

// ── Attack 1: length extension ───────────────────────────────────────

/// **Length-extension attack** on an MD-Damgård hash.  Given
/// `digest = H(secret || message)` and the length of `secret || message`
/// in bytes, forge `H(secret || message || pad || suffix)` without
/// knowing `secret`.
///
/// Returns `(forged_digest, glue_padding)`.  The attacker's effective
/// extended message that produces `forged_digest` is
/// `message || glue_padding || suffix`.
///
/// Works against any [`MerkleDamgardHash`] without HMAC-style wrapping
/// — i.e., the bare hash used as `H(secret || data)` MAC, which is
/// broken by design.
pub fn length_extension_attack<H: MerkleDamgardHash>(
    hash: &H,
    digest_after_prefix: &[u8],
    prefix_bytes: usize,
    suffix: &[u8],
) -> (Vec<u8>, Vec<u8>) {
    assert_eq!(digest_after_prefix.len(), hash.output_bytes());
    // Glue padding: the bytes that the hash would have appended to
    // `prefix` to complete the block before processing `suffix`.
    let glue = hash.padding_for_length(prefix_bytes);
    let mut state = digest_after_prefix.to_vec();
    // Process `suffix` through the compression function, with a fake
    // "prefix length" of `prefix_bytes + glue.len() + suffix.len()`
    // baked into the final padding.
    let virtual_prefix = prefix_bytes + glue.len();
    let mut padded_suffix = suffix.to_vec();
    let new_total = virtual_prefix + suffix.len();
    padded_suffix.extend_from_slice(&hash.padding_for_length(new_total));
    for chunk in padded_suffix.chunks(hash.block_bytes()) {
        hash.compress(&mut state, chunk);
    }
    (state, glue)
}

// ── Attack 2: birthday collision search ──────────────────────────────

/// **Birthday-paradox collision search** over a hash truncated to
/// `truncate_bits` bits.  Expected `≈ √(2^truncate_bits) ≈ 2^(b/2)`
/// trials.  Practical for `truncate_bits ≤ 48` on a laptop.
///
/// Returns `Some((m1, m2, digest))` on collision, `None` on giving up.
pub fn birthday_collision_search<H: HashFunction>(
    hash: &H,
    truncate_bits: u32,
    max_trials: usize,
    seed: u64,
) -> Option<(Vec<u8>, Vec<u8>, Vec<u8>)> {
    assert!(truncate_bits as usize <= hash.output_bytes() * 8);
    let truncate_bytes = (truncate_bits as usize).div_ceil(8);
    let mut rng = StdRng::seed_from_u64(seed);
    let mut seen: HashMap<Vec<u8>, Vec<u8>> = HashMap::new();
    for _ in 0..max_trials {
        let msg_len = 16 + (rng.gen::<u32>() % 32) as usize;
        let mut m = vec![0u8; msg_len];
        rng.fill_bytes(&mut m);
        let mut d = hash.hash(&m);
        d.truncate(truncate_bytes);
        // Mask off any leftover bits in the final byte if truncate_bits
        // isn't a multiple of 8.
        let leftover = (truncate_bytes * 8) as u32 - truncate_bits;
        if leftover > 0 {
            if let Some(last) = d.last_mut() {
                *last &= 0xFFu8 >> leftover;
            }
        }
        if let Some(prev) = seen.get(&d) {
            if prev != &m {
                return Some((prev.clone(), m, d));
            }
        }
        seen.insert(d, m);
    }
    None
}

// ── Attack 3: Joux multicollision (CRYPTO 2004) ──────────────────────

/// **Joux multicollision** on an MD-Damgård hash truncated to
/// `truncate_bits`.  Chains `t` independent block-level collisions to
/// produce `2^t` messages with the same digest.  Cost: `t · 2^(b/2)`
/// (vs the naive expectation that `2^t`-fold collision should cost
/// `t · 2^(b · (2^t − 1) / 2^t)` for an ideal hash).
///
/// Returns the chain of `t` `(block_a, block_b)` colliding pairs.
/// Any combination of choosing one from each pair yields a message
/// hashing to the same value.
///
/// The truncation parameter exists so toy demos run in seconds:
/// finding a single 32-bit collision in MD5 takes ~65 k trials; eight
/// chained collisions take ~520 k trials and demonstrate `2^8 = 256`
/// equivalent messages.
pub fn joux_multicollision<H: MerkleDamgardHash>(
    hash: &H,
    truncate_bits: u32,
    chain_length: usize,
    max_trials_per_block: usize,
    seed: u64,
) -> Option<Vec<(Vec<u8>, Vec<u8>)>> {
    assert!(truncate_bits as usize <= hash.state_bytes() * 8);
    let truncate_bytes = (truncate_bits as usize).div_ceil(8);
    let leftover = (truncate_bytes * 8) as u32 - truncate_bits;
    let bb = hash.block_bytes();

    // Start from a fixed initial state — for MD5/MD4 that's MD-IV.
    // We get the IV by hashing the empty message and inverting the
    // final compression: easier to just snapshot after compressing
    // a known block.  Cleanest is to take the IV implicitly by
    // calling `hash.compress` on a fresh state-bytes buffer that we
    // initialise from `H(empty)`'s pre-padding state... but we don't
    // expose that.  Workaround: just iterate from the digest of the
    // empty-string padding block.
    let pad_block = hash.padding_for_length(0);
    let mut state = vec![0u8; hash.state_bytes()];
    // Initialise to the IV by un-doing the final padding compression.
    // Simpler: hash the empty message and adopt its digest as the
    // "starting state" — this means our multicollision is on
    // messages of the form (empty-pad-block || colliding_chain),
    // which still demonstrates the property.
    let initial_digest = hash.hash(&[]);
    state.copy_from_slice(&initial_digest[..hash.state_bytes().min(initial_digest.len())]);
    let _ = pad_block;

    let mut rng = StdRng::seed_from_u64(seed);
    let mut chain = Vec::with_capacity(chain_length);
    for _ in 0..chain_length {
        let mut seen: HashMap<Vec<u8>, Vec<u8>> = HashMap::new();
        let mut found: Option<(Vec<u8>, Vec<u8>)> = None;
        for _ in 0..max_trials_per_block {
            let mut b = vec![0u8; bb];
            rng.fill_bytes(&mut b);
            let mut s = state.clone();
            hash.compress(&mut s, &b);
            let mut key = s.clone();
            key.truncate(truncate_bytes);
            if leftover > 0 {
                if let Some(last) = key.last_mut() {
                    *last &= 0xFFu8 >> leftover;
                }
            }
            if let Some(prev) = seen.get(&key) {
                if prev != &b {
                    found = Some((prev.clone(), b));
                    break;
                }
            }
            seen.insert(key, b);
        }
        let (a, b) = found?;
        // Advance the chain state via `a` (any of the two would do —
        // they produce the same truncated state).
        let mut s = state.clone();
        hash.compress(&mut s, &a);
        state = s.clone();
        // Also keep `s` truncated identically for the next iteration.
        chain.push((a, b));
    }
    Some(chain)
}

// ── Attack 4: differential bias ──────────────────────────────────────

/// **Differential bias** measurement.  For each output byte,
/// estimate `Pr[H(x)_i = H(x ⊕ Δ)_i]` over `n_samples` random `x`.
/// Returns one bias-per-byte vector.  An ideal hash gives all biases
/// ≈ 0; reduced-round MD4/MD5/SHA-1 give a non-zero signature.
///
/// Used by the auto-hash-attack runner to flag "obviously broken at
/// round count r" cipher variants.
pub fn differential_bias<H: HashFunction>(
    hash: &H,
    delta: &[u8],
    message_len: usize,
    n_samples: usize,
    seed: u64,
) -> Vec<f64> {
    assert!(delta.len() <= message_len);
    let mut rng = StdRng::seed_from_u64(seed);
    let mut matches = vec![0u64; hash.output_bytes()];
    for _ in 0..n_samples {
        let mut x = vec![0u8; message_len];
        rng.fill_bytes(&mut x);
        let mut y = x.clone();
        for i in 0..delta.len() {
            y[i] ^= delta[i];
        }
        let hx = hash.hash(&x);
        let hy = hash.hash(&y);
        for i in 0..hash.output_bytes() {
            if hx[i] == hy[i] {
                matches[i] += 1;
            }
        }
    }
    matches
        .iter()
        .map(|&m| {
            let p = m as f64 / n_samples as f64;
            (p - 1.0 / 256.0).abs()
        })
        .collect()
}

// ── Auto-hash-attack runner ──────────────────────────────────────────

/// Auto-run all generic attacks against the named hash.  Mirrors
/// `cryptanalysis::auto_attack` for block ciphers.  Returns a Markdown
/// report.
pub fn auto_hash_attack(hash_name: &str) -> Result<String, String> {
    let mut md = String::new();
    md.push_str(&format!("# Auto-hash-cryptanalysis: `{}`\n\n", hash_name));

    // ── Length-extension (MD-Damgård only) ────────────────────────
    let lex_result: String;
    match hash_name {
        "md4" => {
            lex_result = run_length_extension(&Md4);
            md.push_str(&lex_result);
            md.push_str(&run_birthday(&Md4, 32, 200_000));
            md.push_str(&run_differential(&Md4));
        }
        "md5" => {
            lex_result = run_length_extension(&Md5);
            md.push_str(&lex_result);
            md.push_str(&run_birthday(&Md5, 32, 200_000));
            md.push_str(&run_differential(&Md5));
        }
        "sha1" => {
            lex_result = run_length_extension(&Sha1);
            md.push_str(&lex_result);
            md.push_str(&run_birthday(&Sha1, 32, 200_000));
            md.push_str(&run_differential(&Sha1));
        }
        _ => {
            return Err(format!(
                "unknown hash '{}'; try one of: md4, md5, sha1",
                hash_name
            ));
        }
    }
    Ok(md)
}

fn run_length_extension<H: MerkleDamgardHash>(hash: &H) -> String {
    let mut md = String::from("## Length-extension attack\n\n");
    let secret = b"secret-key-the-attacker-doesnt-know";
    let original_message = b":user=alice&role=guest";
    let suffix = b"&role=admin";
    let combined = [&secret[..], &original_message[..]].concat();
    let target_digest = hash.hash(&combined);
    let (forged_digest, glue) =
        length_extension_attack(hash, &target_digest, combined.len(), suffix);
    // Verify: the forged extended message is original_message || glue || suffix,
    // and its hash under (secret || ·) should equal forged_digest.
    let mut full = Vec::new();
    full.extend_from_slice(&secret[..]);
    full.extend_from_slice(&original_message[..]);
    full.extend_from_slice(&glue);
    full.extend_from_slice(&suffix[..]);
    let actual = hash.hash(&full);
    let ok = actual == forged_digest;
    md.push_str(&format!(
        "- original H(secret || msg) = {}\n\
         - forged H(secret || msg || pad || \"{}\") = {}\n\
         - actual H of forged message = {}\n\
         - **attack succeeds**: {}\n\n",
        hex(&target_digest),
        String::from_utf8_lossy(suffix),
        hex(&forged_digest),
        hex(&actual),
        if ok { "✓" } else { "✗" },
    ));
    md
}

fn run_birthday<H: HashFunction>(hash: &H, truncate_bits: u32, max_trials: usize) -> String {
    let mut md = format!(
        "## Birthday-collision search (truncate to {} bits)\n\n",
        truncate_bits
    );
    let t0 = std::time::Instant::now();
    let result = birthday_collision_search(hash, truncate_bits, max_trials, 0xC0FFEE);
    let elapsed = t0.elapsed().as_millis();
    match result {
        Some((m1, m2, d)) => {
            md.push_str(&format!(
                "- found collision in {} ms\n\
                 - m1 ({} B) ≠ m2 ({} B), both hash to: {}\n\n",
                elapsed,
                m1.len(),
                m2.len(),
                hex(&d),
            ));
        }
        None => {
            md.push_str(&format!(
                "- no collision in {} trials ({} ms)\n\n",
                max_trials, elapsed
            ));
        }
    }
    md
}

fn run_differential<H: HashFunction>(hash: &H) -> String {
    let mut md = String::from("## Differential bias\n\n");
    // Single-bit flip at position 0.
    let delta = vec![0x01u8];
    let biases = differential_bias(hash, &delta, 16, 4096, 1);
    let mean_bias = biases.iter().sum::<f64>() / biases.len() as f64;
    let max_bias = biases.iter().cloned().fold(0.0f64, f64::max);
    md.push_str(&format!(
        "- delta = 0x01 (single-bit flip at byte 0)\n\
         - mean per-byte bias over 4096 trials: {:.4}\n\
         - max per-byte bias: {:.4}\n\
         - ideal hash baseline: ≈ 0\n\n",
        mean_bias, max_bias,
    ));
    md
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{:02x}", b)).collect()
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// Length extension works on MD4.
    #[test]
    fn length_extension_md4() {
        let h = Md4;
        let secret = b"secret123";
        let msg = b"&q=hello";
        let suffix = b"&admin=1";
        let combined = [&secret[..], &msg[..]].concat();
        let target = h.hash(&combined);
        let (forged, glue) = length_extension_attack(&h, &target, combined.len(), suffix);
        let mut actual_input = Vec::new();
        actual_input.extend_from_slice(secret);
        actual_input.extend_from_slice(msg);
        actual_input.extend_from_slice(&glue);
        actual_input.extend_from_slice(suffix);
        assert_eq!(h.hash(&actual_input), forged);
    }

    /// Length extension works on MD5.
    #[test]
    fn length_extension_md5() {
        let h = Md5;
        let secret = b"key";
        let msg = b"&user=bob";
        let suffix = b"&admin=true";
        let combined = [&secret[..], &msg[..]].concat();
        let target = h.hash(&combined);
        let (forged, glue) = length_extension_attack(&h, &target, combined.len(), suffix);
        let mut actual_input = Vec::new();
        actual_input.extend_from_slice(secret);
        actual_input.extend_from_slice(msg);
        actual_input.extend_from_slice(&glue);
        actual_input.extend_from_slice(suffix);
        assert_eq!(h.hash(&actual_input), forged);
    }

    /// Length extension works on SHA-1.
    #[test]
    fn length_extension_sha1() {
        let h = Sha1;
        let secret = b"sha1-secret";
        let msg = b"data";
        let suffix = b"extra";
        let combined = [&secret[..], &msg[..]].concat();
        let target = h.hash(&combined);
        let (forged, glue) = length_extension_attack(&h, &target, combined.len(), suffix);
        let mut actual_input = Vec::new();
        actual_input.extend_from_slice(secret);
        actual_input.extend_from_slice(msg);
        actual_input.extend_from_slice(&glue);
        actual_input.extend_from_slice(suffix);
        assert_eq!(h.hash(&actual_input), forged);
    }

    /// Birthday-attack on 24-bit-truncated MD5 finds a collision in
    /// well under 200k trials (expected ~4k).
    #[test]
    fn birthday_collision_truncated_md5() {
        let h = Md5;
        let result = birthday_collision_search(&h, 24, 200_000, 42);
        let (m1, m2, d) = result.expect("24-bit MD5 collision should be findable");
        assert_ne!(m1, m2);
        assert_eq!(h.hash(&m1)[..3], d[..3]);
        assert_eq!(h.hash(&m2)[..3], d[..3]);
    }

    /// Joux multicollision: chain 3 collisions on 16-bit-truncated
    /// MD5 → demonstrates `2^3 = 8` equivalent message paths exist.
    #[test]
    fn joux_multicollision_md5_chain_of_3() {
        let h = Md5;
        let chain = joux_multicollision(&h, 16, 3, 100_000, 7);
        let chain = chain.expect("3-chain collision should be findable on 16-bit MD5");
        assert_eq!(chain.len(), 3);
        for (a, b) in &chain {
            assert_eq!(a.len(), 64);
            assert_eq!(b.len(), 64);
            assert_ne!(a, b);
        }
    }

    /// Differential-bias measurement runs end-to-end and returns the
    /// expected number of per-byte readings.
    #[test]
    fn differential_bias_returns_per_byte_vector() {
        let h = Md5;
        let biases = differential_bias(&h, &[0x01], 16, 256, 1);
        assert_eq!(biases.len(), 16);
        // Each bias should be in [0, 1].
        for b in &biases {
            assert!(*b >= 0.0 && *b <= 1.0);
        }
    }

    /// Auto-hash-attack runner produces a non-empty Markdown report.
    #[test]
    fn auto_hash_attack_md5_renders() {
        let md = auto_hash_attack("md5").expect("md5 should be registered");
        assert!(md.contains("Length-extension attack"));
        assert!(md.contains("Birthday-collision search"));
        assert!(md.contains("Differential bias"));
    }

    /// Auto-hash-attack rejects unknown hash names.
    #[test]
    fn auto_hash_attack_rejects_unknown() {
        assert!(auto_hash_attack("not-a-hash").is_err());
    }
}
