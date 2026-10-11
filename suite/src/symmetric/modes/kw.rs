//! **KW — Key Wrap** (RFC 3394 / NIST SP 800-38F).
//!
//! Deterministic AES-based key wrapping for cryptographic keys.
//! Does *not* require an IV (because the input is high-entropy key
//! material), uses a 64-bit integrity check value, and wraps `n`
//! 64-bit blocks into `n+1` blocks of ciphertext.
//!
//! ## Algorithm
//!
//! Let `P = P_1 || P_2 || … || P_n` be the input (each `P_i` is 64
//! bits).  Set `A = 0xA6A6A6A6A6A6A6A6` (the default IV) and
//! `R_i = P_i`.  Then for `j = 0..5`, for `i = 1..=n`:
//!
//! ```text
//!     B = E_K(A || R_i)
//!     A = B[0..8] ⊕ ((n · j) + i)  (big-endian XOR)
//!     R_i = B[8..16]
//! ```
//!
//! Output `C = A || R_1 || … || R_n` — `(n+1) · 8 = 8 · (n+1)` bytes.
//! Unwrapping inverts and checks that the recovered `A == 0xA6…A6`.
//!
//! Standards: RFC 3394, NIST SP 800-38F §6.2.

use super::cipher::BlockCipher;

const DEFAULT_IV: [u8; 8] = [0xA6; 8];

/// **KW wrap** an `n × 8`-byte plaintext.  Returns `(n + 1) × 8` bytes.
/// Returns `None` if `plaintext.len() < 16` or not a multiple of 8.
pub fn kw_wrap<C: BlockCipher<16>>(cipher: &C, plaintext: &[u8]) -> Option<Vec<u8>> {
    if plaintext.len() < 16 || !plaintext.len().is_multiple_of(8) {
        return None;
    }
    let n = plaintext.len() / 8;
    let mut a = DEFAULT_IV;
    let mut r: Vec<[u8; 8]> = (0..n)
        .map(|i| {
            let mut b = [0u8; 8];
            b.copy_from_slice(&plaintext[i * 8..(i + 1) * 8]);
            b
        })
        .collect();
    for j in 0..6 {
        for i in 1..=n {
            let mut block = [0u8; 16];
            block[0..8].copy_from_slice(&a);
            block[8..16].copy_from_slice(&r[i - 1]);
            cipher.encrypt_block(&mut block);
            // A = MSB(64, B) ⊕ t where t = (n · j) + i.
            let t = (n as u64) * (j as u64) + (i as u64);
            let t_bytes = t.to_be_bytes();
            let mut new_a = [0u8; 8];
            for k in 0..8 {
                new_a[k] = block[k] ^ t_bytes[k];
            }
            a = new_a;
            r[i - 1].copy_from_slice(&block[8..16]);
        }
    }
    let mut out = Vec::with_capacity(8 * (n + 1));
    out.extend_from_slice(&a);
    for ri in &r {
        out.extend_from_slice(ri);
    }
    Some(out)
}

/// **KW unwrap**.  Returns the plaintext if the recovered IV matches
/// `0xA6A6…A6`, else `None`.
pub fn kw_unwrap<C: BlockCipher<16>>(cipher: &C, ciphertext: &[u8]) -> Option<Vec<u8>> {
    if ciphertext.len() < 24 || !ciphertext.len().is_multiple_of(8) {
        return None;
    }
    let n = ciphertext.len() / 8 - 1;
    let mut a = [0u8; 8];
    a.copy_from_slice(&ciphertext[0..8]);
    let mut r: Vec<[u8; 8]> = (0..n)
        .map(|i| {
            let mut b = [0u8; 8];
            b.copy_from_slice(&ciphertext[(i + 1) * 8..(i + 2) * 8]);
            b
        })
        .collect();
    for j in (0..6).rev() {
        for i in (1..=n).rev() {
            let t = (n as u64) * (j as u64) + (i as u64);
            let t_bytes = t.to_be_bytes();
            let mut block = [0u8; 16];
            for k in 0..8 {
                block[k] = a[k] ^ t_bytes[k];
            }
            block[8..16].copy_from_slice(&r[i - 1]);
            cipher.decrypt_block(&mut block);
            a.copy_from_slice(&block[0..8]);
            r[i - 1].copy_from_slice(&block[8..16]);
        }
    }
    // Constant-time-ish IV check.
    let mut diff = 0u8;
    for k in 0..8 {
        diff |= a[k] ^ DEFAULT_IV[k];
    }
    if diff != 0 {
        return None;
    }
    let mut out = Vec::with_capacity(8 * n);
    for ri in &r {
        out.extend_from_slice(ri);
    }
    Some(out)
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::symmetric::aes::AesKey;

    /// **RFC 3394 §4.1 test vector** — 128-bit KEK wrapping 128-bit key.
    /// KEK:         000102030405060708090A0B0C0D0E0F
    /// KeyData:     00112233445566778899AABBCCDDEEFF
    /// Ciphertext:  1FA68B0A8112B447 AEF34BD8FB5A7B82 9D3E862371D2CFE5
    #[test]
    fn kw_rfc3394_4_1() {
        let kek = AesKey::new(&[
            0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D,
            0x0E, 0x0F,
        ])
        .unwrap();
        let key_data: [u8; 16] = [
            0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0xAA, 0xBB, 0xCC, 0xDD,
            0xEE, 0xFF,
        ];
        let expected: [u8; 24] = [
            0x1F, 0xA6, 0x8B, 0x0A, 0x81, 0x12, 0xB4, 0x47, 0xAE, 0xF3, 0x4B, 0xD8, 0xFB, 0x5A,
            0x7B, 0x82, 0x9D, 0x3E, 0x86, 0x23, 0x71, 0xD2, 0xCF, 0xE5,
        ];
        let wrapped = kw_wrap(&kek, &key_data).unwrap();
        assert_eq!(&wrapped[..], &expected[..]);
        let unwrapped = kw_unwrap(&kek, &wrapped).unwrap();
        assert_eq!(&unwrapped[..], &key_data[..]);
    }

    /// **RFC 3394 §4.6 test vector** — 256-bit KEK wrapping 256-bit key.
    /// KEK:    000102030405060708090A0B0C0D0E0F101112131415161718191A1B1C1D1E1F
    /// Key:    00112233445566778899AABBCCDDEEFF000102030405060708090A0B0C0D0E0F
    /// CT:     28C9F404C4B810F4 CBCCB35CFB87F826 3F5786E2D80ED326 CBC7F0E71A99F43B FB988B9B7A02DD21
    #[test]
    fn kw_rfc3394_4_6() {
        let mut kek_bytes = [0u8; 32];
        for i in 0..32 {
            kek_bytes[i] = i as u8;
        }
        let kek = AesKey::new(&kek_bytes).unwrap();
        let key_data: [u8; 32] = [
            0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0xAA, 0xBB, 0xCC, 0xDD,
            0xEE, 0xFF, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B,
            0x0C, 0x0D, 0x0E, 0x0F,
        ];
        let expected: [u8; 40] = [
            0x28, 0xC9, 0xF4, 0x04, 0xC4, 0xB8, 0x10, 0xF4, 0xCB, 0xCC, 0xB3, 0x5C, 0xFB, 0x87,
            0xF8, 0x26, 0x3F, 0x57, 0x86, 0xE2, 0xD8, 0x0E, 0xD3, 0x26, 0xCB, 0xC7, 0xF0, 0xE7,
            0x1A, 0x99, 0xF4, 0x3B, 0xFB, 0x98, 0x8B, 0x9B, 0x7A, 0x02, 0xDD, 0x21,
        ];
        let wrapped = kw_wrap(&kek, &key_data).unwrap();
        assert_eq!(&wrapped[..], &expected[..]);
        let unwrapped = kw_unwrap(&kek, &wrapped).unwrap();
        assert_eq!(&unwrapped[..], &key_data[..]);
    }

    /// Corrupted ciphertext fails to unwrap.
    #[test]
    fn kw_rejects_tampered_ciphertext() {
        let kek = AesKey::new(&[0u8; 16]).unwrap();
        let key_data = [0xAAu8; 16];
        let mut wrapped = kw_wrap(&kek, &key_data).unwrap();
        wrapped[5] ^= 1;
        assert!(kw_unwrap(&kek, &wrapped).is_none());
    }

    /// Wrong length rejected.
    #[test]
    fn kw_rejects_bad_lengths() {
        let kek = AesKey::new(&[0u8; 16]).unwrap();
        assert!(kw_wrap(&kek, &[0u8; 7]).is_none()); // not multiple of 8
        assert!(kw_wrap(&kek, &[0u8; 8]).is_none()); // < 16 bytes
        assert!(kw_unwrap(&kek, &[0u8; 8]).is_none()); // < 24 bytes
    }
}
