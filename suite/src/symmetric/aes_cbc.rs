//! AES-CBC mode + PKCS#7 padding + Vaudenay 2002 padding-oracle attack.
//!
//! CBC was the workhorse mode of TLS 1.0-1.2 and is still the
//! default mode of many at-rest encryption stacks (Java, .NET,
//! plenty of "encrypt-this-file" CLI tools).  It's deeply broken
//! when used with PKCS#7 padding and an attacker can observe
//! valid-vs-invalid padding — Vaudenay (Eurocrypt 2002,
//! "Security Flaws Induced by CBC Padding") gives a complete
//! plaintext-recovery attack.  This module ships both:
//!
//! 1. **AES-CBC encrypt/decrypt** with PKCS#7 padding.
//! 2. **The padding-oracle attack** — given an oracle that
//!    answers "is this ciphertext's plaintext correctly padded?",
//!    recover the plaintext byte by byte from any ciphertext.
//!
//! # Why ship the attack
//!
//! Pedagogically: it's the canonical "secure primitive used wrong
//! at the protocol layer" demonstration.  Lucky-13 (Al Fardan-
//! Paterson 2013) and POODLE (Möller-Duong-Kotowicz 2014) are
//! production-class refinements; this is the original.
//!
//! Defensively: the attack exists; *every* CBC + PKCS#7 deployment
//! that responds differently to padding errors versus other
//! errors is breakable in `O(plaintext_bytes · 256)` oracle
//! queries.  Modern guidance is "use AES-GCM, never CBC" — this
//! module shows why.

use super::aes::{decrypt_block, encrypt_block, AesKey};

// ── AES-CBC encrypt / decrypt with PKCS#7 padding ─────────────────────

/// Append PKCS#7 padding so the result is a multiple of 16 bytes.
/// Always adds at least one byte: if the message is already a
/// multiple of 16, a full 16-byte block of `0x10` is appended.
pub fn pkcs7_pad(data: &[u8], block_size: usize) -> Vec<u8> {
    let pad_len = block_size - (data.len() % block_size);
    let mut out = Vec::with_capacity(data.len() + pad_len);
    out.extend_from_slice(data);
    out.extend(std::iter::repeat_n(pad_len as u8, pad_len));
    out
}

/// Strip PKCS#7 padding; verify the padding is well-formed and
/// reject if not.  Returns `None` on bad padding (this is
/// EXACTLY the boolean an attacker exploits — but a clean
/// implementation that uses *only* AEAD modes would never expose
/// this distinguisher).
pub fn pkcs7_unpad(data: &[u8], block_size: usize) -> Option<Vec<u8>> {
    if data.is_empty() || !data.len().is_multiple_of(block_size) {
        return None;
    }
    let pad_len = *data.last()? as usize;
    if pad_len == 0 || pad_len > block_size {
        return None;
    }
    let n = data.len();
    if data.len() < pad_len {
        return None;
    }
    for &b in &data[n - pad_len..] {
        if b as usize != pad_len {
            return None;
        }
    }
    Some(data[..n - pad_len].to_vec())
}

/// AES-CBC encryption with PKCS#7 padding.  Returns IV ‖ ciphertext.
pub fn aes_cbc_encrypt(plaintext: &[u8], key: &AesKey, iv: &[u8; 16]) -> Vec<u8> {
    let padded = pkcs7_pad(plaintext, 16);
    let mut out = Vec::with_capacity(16 + padded.len());
    out.extend_from_slice(iv);
    let mut prev = *iv;
    for chunk in padded.chunks_exact(16) {
        let mut block = [0u8; 16];
        for i in 0..16 {
            block[i] = chunk[i] ^ prev[i];
        }
        let ct = encrypt_block(&block, key);
        out.extend_from_slice(&ct);
        prev = ct;
    }
    out
}

/// AES-CBC decryption with PKCS#7 padding verification.  Input
/// is `iv ‖ ciphertext`.  Returns `None` if the padding is malformed.
pub fn aes_cbc_decrypt(input: &[u8], key: &AesKey) -> Option<Vec<u8>> {
    if input.len() < 32 || !(input.len() - 16).is_multiple_of(16) {
        return None;
    }
    let iv = &input[..16];
    let mut prev: [u8; 16] = iv.try_into().ok()?;
    let mut padded = Vec::with_capacity(input.len() - 16);
    for chunk in input[16..].chunks_exact(16) {
        let mut ct_block = [0u8; 16];
        ct_block.copy_from_slice(chunk);
        let pt = decrypt_block(&ct_block, key);
        let mut plain = [0u8; 16];
        for i in 0..16 {
            plain[i] = pt[i] ^ prev[i];
        }
        padded.extend_from_slice(&plain);
        prev = ct_block;
    }
    pkcs7_unpad(&padded, 16)
}

// ── Vaudenay 2002 padding-oracle attack ────────────────────────────────
//
// Attack model: the attacker has access to a function
//
//     oracle: &[u8] → bool
//
// that returns `true` iff the ciphertext (input concatenated as
// IV‖CT) decrypts under the unknown key with valid PKCS#7
// padding, and `false` otherwise.  No other information leaks.
//
// Goal: given a target ciphertext `IV ‖ C_1 ‖ C_2 ‖ ... ‖ C_n`,
// recover the plaintext.
//
// Algorithm (from Vaudenay 2002, simplified):
//
//   For each block C_i (i = 1..n) we recover the intermediate
//   value `D = AES_dec(C_i)`, the per-block decrypt-before-XOR
//   state.  Once we have `D`, the plaintext block is `D ⊕ C_{i-1}`
//   (where `C_0 = IV`).
//
//   To recover `D` we craft a chosen-prefix `C'` and submit
//   `C' ‖ C_i` to the oracle.  Vary the last byte of `C'` from
//   0 to 255; exactly one (or two — see below) values produce
//   valid padding.  When valid, we know `D[15] ⊕ C'[15] = 0x01`,
//   giving `D[15] = C'[15] ⊕ 0x01`.  Then move to `D[14]` by
//   adjusting `C'[15]` so the trailing byte decrypts to `0x02`,
//   varying `C'[14]`, and so on.

/// One block's worth of recovered intermediate state `D = AES_dec(C)`.
fn recover_intermediate<F: Fn(&[u8]) -> bool>(c_block: &[u8; 16], oracle: &F) -> [u8; 16] {
    let mut intermediate = [0u8; 16];
    // Recover bytes 15, 14, ..., 0 (right to left).
    for byte_idx in (0..16usize).rev() {
        let target_pad = (16 - byte_idx) as u8;
        // Build the prefix C' that, with our knowledge so far,
        // would force the trailing bytes to decrypt to target_pad.
        let mut prefix = [0u8; 16];
        for i in (byte_idx + 1)..16 {
            prefix[i] = intermediate[i] ^ target_pad;
        }
        // Try every candidate value for prefix[byte_idx].
        let mut found = None;
        for cand in 0u16..=255 {
            prefix[byte_idx] = cand as u8;
            let mut probe = Vec::with_capacity(32);
            probe.extend_from_slice(&prefix);
            probe.extend_from_slice(c_block);
            if oracle(&probe) {
                // Edge case: at byte_idx == 15, the value 0x01 may
                // also produce valid padding because the original
                // last byte's natural value happens to be 0x01.
                // Disambiguate by perturbing prefix[14] and re-checking.
                if byte_idx == 15 {
                    let mut probe2 = probe.clone();
                    probe2[14] ^= 0x01;
                    if !oracle(&probe2) {
                        // The valid-padding hit was a "lucky 0x01"
                        // that depended on prefix[14]; skip.
                        continue;
                    }
                }
                found = Some(cand as u8);
                break;
            }
        }
        let cand = found.expect("no candidate produced valid padding — oracle is broken");
        intermediate[byte_idx] = cand ^ target_pad;
    }
    intermediate
}

/// **Vaudenay 2002 padding-oracle attack**.  Recover the plaintext
/// of `iv ‖ ct` block-by-block using only the supplied oracle.
///
/// Returns the recovered plaintext (with PKCS#7 padding *not*
/// stripped — the attack reveals raw plaintext including padding).
/// Cost: ≤ 256 oracle queries per byte × 16 bytes per block × N blocks.
pub fn padding_oracle_attack<F>(iv: &[u8; 16], ct: &[u8], oracle: F) -> Vec<u8>
where
    F: Fn(&[u8]) -> bool,
{
    assert_eq!(
        ct.len() % 16,
        0,
        "ciphertext must be a whole number of blocks"
    );
    let mut plaintext = Vec::with_capacity(ct.len());
    let mut prev_ct: [u8; 16] = *iv;
    for chunk in ct.chunks_exact(16) {
        let mut c_block = [0u8; 16];
        c_block.copy_from_slice(chunk);
        let d = recover_intermediate(&c_block, &oracle);
        let mut pt_block = [0u8; 16];
        for i in 0..16 {
            pt_block[i] = d[i] ^ prev_ct[i];
        }
        plaintext.extend_from_slice(&pt_block);
        prev_ct = c_block;
    }
    plaintext
}

#[cfg(test)]
mod tests {
    use super::*;

    /// PKCS#7 round-trip: pad, unpad, recover original.
    #[test]
    fn pkcs7_roundtrip() {
        let cases: &[&[u8]] = &[
            b"",
            b"a",
            b"hello",
            b"0123456789ABCDE",                 // 15 bytes — pad with 1 byte 0x01
            b"0123456789ABCDEF",                // 16 bytes — pad with full block of 0x10
            b"0123456789ABCDEF0123456789ABCDE", // 31 bytes
        ];
        for &m in cases {
            let padded = pkcs7_pad(m, 16);
            assert_eq!(padded.len() % 16, 0);
            let unpadded = pkcs7_unpad(&padded, 16).unwrap();
            assert_eq!(unpadded, m);
        }
    }

    /// Bad padding rejected.
    #[test]
    fn pkcs7_rejects_bad_padding() {
        // Wrong byte at end.
        let mut bad = pkcs7_pad(b"hello", 16);
        bad[15] = 0xFF; // should be 11 (0x0B), not 0xFF
        assert!(pkcs7_unpad(&bad, 16).is_none());
        // Inconsistent padding bytes.
        let mut bad2 = pkcs7_pad(b"hello", 16);
        bad2[14] = 0x05; // padding bytes should all be 0x0B
        assert!(pkcs7_unpad(&bad2, 16).is_none());
    }

    /// AES-CBC encrypt/decrypt round-trip.
    #[test]
    fn aes_cbc_roundtrip() {
        let key = AesKey::Aes128([0x0Fu8; 16]);
        let iv = [0x42u8; 16];
        for msg_len in &[0usize, 1, 15, 16, 17, 31, 32, 33, 100, 256] {
            let plaintext: Vec<u8> = (0..*msg_len).map(|i| (i & 0xFF) as u8).collect();
            let ct = aes_cbc_encrypt(&plaintext, &key, &iv);
            let recovered = aes_cbc_decrypt(&ct, &key).unwrap();
            assert_eq!(plaintext, recovered, "round-trip failed at len {}", msg_len);
        }
    }

    /// AES-CBC decryption rejects bad padding.
    #[test]
    fn aes_cbc_rejects_bad_padding() {
        let key = AesKey::Aes128([1u8; 16]);
        let iv = [2u8; 16];
        let ct = aes_cbc_encrypt(b"hello world", &key, &iv);
        // Flip a bit in the last ciphertext block — overwhelmingly
        // produces malformed padding.
        let mut tampered = ct.clone();
        let last = tampered.len() - 1;
        tampered[last] ^= 0xFF;
        // Most random tampering ⇒ bad padding ⇒ None.  A few
        // values would happen to produce valid-looking padding;
        // 0xFF specifically should be safe (very unlikely to
        // produce 0x01..0x10 trailing byte).
        let result = aes_cbc_decrypt(&tampered, &key);
        if let Some(r) = result {
            // If by chance the random ⊕ produces valid PKCS#7
            // padding, the recovered message must NOT equal
            // "hello world" (it'd be garbage).
            assert_ne!(r, b"hello world".to_vec());
        }
    }

    /// **The headline attack**: padding-oracle plaintext recovery.
    /// We construct an oracle around our own decryption, simulate
    /// the attacker (who has only the public oracle), and verify
    /// the attack recovers the correct plaintext.
    #[test]
    fn padding_oracle_recovers_plaintext() {
        let key = AesKey::Aes128([0x2Bu8; 16]);
        let iv = [0xA5u8; 16];
        let secret: &[u8] = b"the password is hunter2";
        let full_ct = aes_cbc_encrypt(secret, &key, &iv);

        // The oracle: given iv‖ct, return true iff the padding is valid.
        let oracle = |probe: &[u8]| -> bool {
            // Pretend our oracle gives only the boolean valid/invalid.
            aes_cbc_decrypt(probe, &key).is_some()
        };

        // The attacker has only the oracle and the ciphertext (not the key).
        let iv_ref: &[u8; 16] = full_ct[..16].try_into().unwrap();
        let ct_ref = &full_ct[16..];
        let recovered_padded = padding_oracle_attack(iv_ref, ct_ref, oracle);
        // Strip PKCS#7 padding from the recovered (raw) plaintext.
        let recovered = pkcs7_unpad(&recovered_padded, 16).unwrap();
        assert_eq!(recovered, secret);
    }

    /// Padding-oracle attack on a multi-block plaintext.
    #[test]
    fn padding_oracle_recovers_multiblock_plaintext() {
        let key = AesKey::Aes128([0xDEu8; 16]);
        let iv = [0xADu8; 16];
        let secret: &[u8] = b"this plaintext spans multiple AES blocks for the test.";
        let full_ct = aes_cbc_encrypt(secret, &key, &iv);
        let oracle = |probe: &[u8]| -> bool { aes_cbc_decrypt(probe, &key).is_some() };
        let iv_ref: &[u8; 16] = full_ct[..16].try_into().unwrap();
        let ct_ref = &full_ct[16..];
        let recovered_padded = padding_oracle_attack(iv_ref, ct_ref, oracle);
        let recovered = pkcs7_unpad(&recovered_padded, 16).unwrap();
        assert_eq!(recovered, secret);
    }
}
