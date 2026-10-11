//! **SIV — Synthetic Initialization Vector** AEAD (RFC 5297).
//!
//! Misuse-resistant deterministic AEAD.  Repeating a `(key, nonce, aad)`
//! tuple **does not** leak the plaintext (beyond the fact that the
//! plaintexts are equal): SIV produces the same ciphertext for the
//! same `(key, aad, pt)` triple.
//!
//! ## Key layout
//!
//! Single concatenated key `K = K1 || K2` where `K1` (high half) is
//! the S2V/CMAC key and `K2` (low half) is the CTR key.  RFC 5297
//! defines AES-CMAC-SIV-128 (32-byte K) and AES-CMAC-SIV-256 (64-byte K).
//! We implement the 128-bit-half variant: K is 32 bytes total.
//!
//! ## Algorithm
//!
//! 1. **S2V**: doubling PRF over `(AAD_1, …, AAD_n, plaintext)`.
//!    - `D_0 = AES-CMAC(K1, 0^128)`.
//!    - For each `AAD_i`: `D_i = dbl(D_{i-1}) ⊕ AES-CMAC(K1, AAD_i)`.
//!    - For the plaintext `P`:
//!      - If `|P| ≥ 128 bits`: `T = P xorend dbl(D_n)` then
//!        `V = AES-CMAC(K1, T)`.
//!      - Else: `V = AES-CMAC(K1, dbl(D_n) ⊕ pad(P))` where
//!        `pad(P) = P || 1 || 0…`.
//! 2. **CTR**: clear top bit of byte 8 and byte 12 of `V` to get `Q`,
//!    then CTR-encrypt P under `K2` with counter starting from `Q`.
//! 3. Output `V || ciphertext`.
//!
//! ## References
//!
//! - **RFC 5297** — Synthetic Initialization Vector (SIV) AEAD.
//! - **Rogaway-Shrimpton 2006** — original deterministic AE paper.

use crate::symmetric::aes::AesKey;
use crate::symmetric::cmac::aes_cmac;

/// Double in GF(2^128) — left-shift by 1, XOR with R = 0x...87 if MSB
/// was 1.  Same operation CMAC uses for subkey generation.
fn dbl(input: &[u8; 16]) -> [u8; 16] {
    let mut out = [0u8; 16];
    let mut carry = 0u8;
    for i in (0..16).rev() {
        let new_carry = (input[i] >> 7) & 1;
        out[i] = (input[i] << 1) | carry;
        carry = new_carry;
    }
    if (input[0] >> 7) & 1 == 1 {
        out[15] ^= 0x87;
    }
    out
}

fn xor_blocks(a: &[u8; 16], b: &[u8; 16]) -> [u8; 16] {
    let mut out = [0u8; 16];
    for i in 0..16 {
        out[i] = a[i] ^ b[i];
    }
    out
}

/// **S2V**: the doubling-CMAC PRF.  Inputs: K1 (CMAC key), AAD list,
/// final plaintext.  Output: 128-bit SIV.
fn s2v(k1: &AesKey, aads: &[&[u8]], plaintext: &[u8]) -> [u8; 16] {
    // D_0 = CMAC(K1, 0^128)
    let zero = [0u8; 16];
    let mut d: [u8; 16] = aes_cmac(k1, &zero);
    // Fold in each AAD.
    for aad in aads {
        d = dbl(&d);
        let mac: [u8; 16] = aes_cmac(k1, aad);
        d = xor_blocks(&d, &mac);
    }
    // Final: combine with plaintext.
    if plaintext.len() >= 16 {
        // T = P xorend dbl(D): XOR the trailing 16 bytes with dbl(D).
        let mut t = plaintext.to_vec();
        let n = t.len();
        let d2 = dbl(&d);
        for i in 0..16 {
            t[n - 16 + i] ^= d2[i];
        }
        aes_cmac(k1, &t)
    } else {
        // Pad: P || 1 || 0…, full 16 bytes, then XOR with dbl(D).
        let mut padded = [0u8; 16];
        padded[..plaintext.len()].copy_from_slice(plaintext);
        padded[plaintext.len()] = 0x80;
        let d2 = dbl(&d);
        let mixed = xor_blocks(&d2, &padded);
        aes_cmac(k1, &mixed)
    }
}

/// CTR encrypt `P` under `k2` with initial counter `q`.  Counter is
/// big-endian; increment the full 128-bit value mod 2^128.
fn ctr_encrypt(k2: &AesKey, q: &[u8; 16], plaintext: &[u8]) -> Vec<u8> {
    use crate::symmetric::aes::encrypt_block;
    let mut ctr = *q;
    let mut out = Vec::with_capacity(plaintext.len());
    let mut idx = 0;
    while idx < plaintext.len() {
        let ks = encrypt_block(&ctr, k2);
        let n = 16.min(plaintext.len() - idx);
        for i in 0..n {
            out.push(plaintext[idx + i] ^ ks[i]);
        }
        idx += n;
        // Increment 128-bit big-endian counter.
        for i in (0..16).rev() {
            ctr[i] = ctr[i].wrapping_add(1);
            if ctr[i] != 0 {
                break;
            }
        }
    }
    out
}

/// **SIV encrypt** (AES-CMAC-SIV-128).  `key_full` is the concatenated
/// `K1 || K2` (32 bytes total).  `aads` may be empty; common pattern
/// is `&[&nonce, &header]`.  Returns `V || C` where `V` is the 16-byte
/// synthetic IV / authentication tag.
pub fn siv_encrypt(key_full: &[u8; 32], aads: &[&[u8]], plaintext: &[u8]) -> Vec<u8> {
    let k1 = AesKey::new(&key_full[..16]).unwrap();
    let k2 = AesKey::new(&key_full[16..]).unwrap();
    let v = s2v(&k1, aads, plaintext);
    // Q = V with high bit of byte 8 and byte 12 cleared.
    let mut q = v;
    q[8] &= 0x7F;
    q[12] &= 0x7F;
    let ct = ctr_encrypt(&k2, &q, plaintext);
    let mut out = Vec::with_capacity(16 + ct.len());
    out.extend_from_slice(&v);
    out.extend_from_slice(&ct);
    out
}

/// **SIV decrypt + verify**.  Returns `None` on tag mismatch.
pub fn siv_decrypt(
    key_full: &[u8; 32],
    aads: &[&[u8]],
    ciphertext_with_tag: &[u8],
) -> Option<Vec<u8>> {
    if ciphertext_with_tag.len() < 16 {
        return None;
    }
    let k1 = AesKey::new(&key_full[..16]).unwrap();
    let k2 = AesKey::new(&key_full[16..]).unwrap();
    let mut v = [0u8; 16];
    v.copy_from_slice(&ciphertext_with_tag[..16]);
    let ct = &ciphertext_with_tag[16..];
    let mut q = v;
    q[8] &= 0x7F;
    q[12] &= 0x7F;
    let pt = ctr_encrypt(&k2, &q, ct);
    let v_check = s2v(&k1, aads, &pt);
    let mut diff = 0u8;
    for i in 0..16 {
        diff |= v[i] ^ v_check[i];
    }
    if diff != 0 {
        return None;
    }
    Some(pt)
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// **RFC 5297 Appendix A.1** — Deterministic Authenticated Encryption.
    ///
    /// Key:        fffefdfc fbfaf9f8 f7f6f5f4 f3f2f1f0
    ///             f0f1f2f3 f4f5f6f7 f8f9fafb fcfdfeff
    /// AAD:        10111213 14151617 18191a1b 1c1d1e1f
    ///             20212223 24252627
    /// Plaintext:  11223344 55667788 99aabbcc ddee
    ///
    /// V:          85632d07 c6e8f37f 950acd32 0a2ecc93
    /// CT:         40c02b96 90c4dc04 daef7f6a fe5c
    ///
    /// Output = V || CT.
    #[test]
    fn siv_rfc5297_a1() {
        let mut key = [0u8; 32];
        for i in 0..16 {
            key[i] = 0xFF - i as u8;
            key[16 + i] = 0xF0 + i as u8;
        }
        let aad: [u8; 24] = [
            0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1a, 0x1b, 0x1c, 0x1d,
            0x1e, 0x1f, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27,
        ];
        let pt: [u8; 14] = [
            0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0xaa, 0xbb, 0xcc, 0xdd, 0xee,
        ];
        let expected: [u8; 30] = [
            0x85, 0x63, 0x2d, 0x07, 0xc6, 0xe8, 0xf3, 0x7f, 0x95, 0x0a, 0xcd, 0x32, 0x0a, 0x2e,
            0xcc, 0x93, 0x40, 0xc0, 0x2b, 0x96, 0x90, 0xc4, 0xdc, 0x04, 0xda, 0xef, 0x7f, 0x6a,
            0xfe, 0x5c,
        ];
        let out = siv_encrypt(&key, &[&aad], &pt);
        assert_eq!(&out[..], &expected[..]);
        let recovered = siv_decrypt(&key, &[&aad], &out).unwrap();
        assert_eq!(&recovered[..], &pt[..]);
    }

    /// Round-trip on arbitrary AAD count.
    #[test]
    fn siv_round_trip_multi_aad() {
        let key = [0x42u8; 32];
        let aad1 = b"first associated string";
        let aad2 = b"second";
        let pt = b"this is the plaintext, of any length really";
        let ct = siv_encrypt(&key, &[aad1, aad2], pt);
        let recovered = siv_decrypt(&key, &[aad1, aad2], &ct).unwrap();
        assert_eq!(recovered, pt);
        // Wrong AAD order ⇒ failure.
        assert!(siv_decrypt(&key, &[aad2, aad1], &ct).is_none());
    }

    /// Empty plaintext, empty AAD: degenerate but supported.
    #[test]
    fn siv_empty_inputs() {
        let key = [0u8; 32];
        let ct = siv_encrypt(&key, &[], b"");
        assert_eq!(ct.len(), 16); // just the SIV/tag
        let recovered = siv_decrypt(&key, &[], &ct).unwrap();
        assert!(recovered.is_empty());
    }

    /// **Determinism**: repeating the same (key, aads, pt) gives the
    /// same ciphertext.  This is the misuse-resistance property.
    #[test]
    fn siv_is_deterministic() {
        let key = [7u8; 32];
        let pt = b"deterministic output";
        let ct1 = siv_encrypt(&key, &[b"aad"], pt);
        let ct2 = siv_encrypt(&key, &[b"aad"], pt);
        assert_eq!(ct1, ct2);
    }

    /// Tampered ciphertext fails.
    #[test]
    fn siv_rejects_tampered_ct() {
        let key = [0u8; 32];
        let mut ct = siv_encrypt(&key, &[b"aad"], b"plaintext");
        ct[20] ^= 1;
        assert!(siv_decrypt(&key, &[b"aad"], &ct).is_none());
    }

    /// `dbl` doubles in GF(2^128) — verify on a known value.
    /// dbl(0x00000…01) = 0x00000…02.
    #[test]
    fn dbl_simple_case() {
        let mut x = [0u8; 16];
        x[15] = 1;
        let d = dbl(&x);
        let mut expected = [0u8; 16];
        expected[15] = 2;
        assert_eq!(d, expected);
    }

    /// `dbl(0x80000…0)` triggers the carry → XOR with 0x87 at byte 15.
    #[test]
    fn dbl_with_carry() {
        let mut x = [0u8; 16];
        x[0] = 0x80;
        let d = dbl(&x);
        let mut expected = [0u8; 16];
        expected[15] = 0x87;
        assert_eq!(d, expected);
    }
}
