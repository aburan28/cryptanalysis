//! **CTR** — Counter Mode (NIST SP 800-38A §6.5), generic over any
//! 16-byte block cipher.
//!
//! ## Construction
//!
//! ```text
//!     for i = 0..n_blocks:
//!         keystream_i = E_K(counter_i)
//!         ciphertext_i = plaintext_i ⊕ keystream_i
//!         counter_{i+1} = counter_i + 1   (big-endian increment)
//! ```
//!
//! CTR turns a block cipher into a stream cipher.  Encryption and
//! decryption are identical: the keystream is data-independent.  The
//! caller chooses the initial counter block (typically `nonce || 0` or
//! `nonce || 1` per RFC 3686 §4) and is responsible for ensuring no
//! counter overlap across messages.
//!
//! ## Why generic
//!
//! CTR is a foundational building block — GCM, GCM-SIV, EAX, OCB3,
//! CCM, AES-CMAC's underpinnings all rely on CTR (or CTR-like
//! constructions) over their respective ciphers.  This module exposes
//! it directly so any 16-byte block cipher (AES, Camellia, Twofish,
//! Serpent, ARIA, Kuznyechik, SM4, etc.) can act as a stream cipher.
//!
//! For AES specifically, the in-place [`crate::symmetric::aes::aes_ctr`]
//! is still available with the RFC 3686 nonce profile (12-byte nonce +
//! 4-byte big-endian counter starting at 1).

use super::cipher::BlockCipher128;

/// Apply CTR keystream to `data`, treating the 16-byte block as a
/// big-endian counter.  Encryption and decryption are the same call.
pub fn ctr_apply<C: BlockCipher128>(
    cipher: &C,
    initial_counter: &[u8; 16],
    data: &[u8],
) -> Vec<u8> {
    let mut out = data.to_vec();
    let mut counter = *initial_counter;
    for chunk in out.chunks_mut(16) {
        let mut ks = counter;
        cipher.encrypt_block(&mut ks);
        for (b, k) in chunk.iter_mut().zip(ks.iter()) {
            *b ^= k;
        }
        // Big-endian increment of the full 16-byte counter.
        for byte in counter.iter_mut().rev() {
            *byte = byte.wrapping_add(1);
            if *byte != 0 {
                break;
            }
        }
    }
    out
}

/// RFC 3686-style CTR: 12-byte nonce || 4-byte big-endian counter.
/// Counter starts at 1 (per RFC 3686 §4).  This is the layout used by
/// AES-CTR throughout the project.
pub fn ctr_rfc3686<C: BlockCipher128>(cipher: &C, nonce: &[u8; 12], data: &[u8]) -> Vec<u8> {
    let mut init = [0u8; 16];
    init[..12].copy_from_slice(nonce);
    init[12..].copy_from_slice(&1u32.to_be_bytes());
    ctr_apply(cipher, &init, data)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::symmetric::aes::{aes_ctr, AesKey};
    use crate::symmetric::camellia::Camellia128;
    use crate::symmetric::serpent::SerpentKey;

    /// **Generic CTR over AES** matches the dedicated `aes_ctr` in
    /// the existing AES module bit-for-bit — proves the generic
    /// implementation is a clean drop-in.
    #[test]
    fn ctr_aes_matches_dedicated_aes_ctr() {
        let key_bytes = [0x42u8; 32];
        let key = AesKey::new(&key_bytes).unwrap();
        let nonce = [0x77u8; 12];
        let pt: Vec<u8> = (0..200).map(|i| i as u8).collect();

        let want = aes_ctr(&pt, &key, &nonce);
        let got = ctr_rfc3686(&key, &nonce, &pt);
        assert_eq!(got, want);
    }

    /// CTR is its own inverse — encrypt twice → plaintext.
    #[test]
    fn ctr_self_inverse_camellia() {
        let cipher = Camellia128::new(&[0x55u8; 16]);
        let nonce_counter = [0x11u8; 16];
        let pt = b"CTR over Camellia is a stream cipher.".to_vec();
        let ct = ctr_apply(&cipher, &nonce_counter, &pt);
        assert_ne!(ct, pt);
        let pt2 = ctr_apply(&cipher, &nonce_counter, &ct);
        assert_eq!(pt2, pt);
    }

    /// Partial last block (length not a multiple of 16) — common in
    /// stream-cipher usage and the most-tested edge case.
    #[test]
    fn ctr_handles_partial_blocks_serpent() {
        let cipher = SerpentKey::new(&[0u8; 16]).unwrap();
        let nonce_counter = [0u8; 16];
        for len in [0usize, 1, 15, 17, 31, 33, 1023] {
            let pt: Vec<u8> = (0..len).map(|i| (i * 13) as u8).collect();
            let ct = ctr_apply(&cipher, &nonce_counter, &pt);
            assert_eq!(ct.len(), len);
            assert_eq!(ctr_apply(&cipher, &nonce_counter, &ct), pt, "len={}", len);
        }
    }
}
