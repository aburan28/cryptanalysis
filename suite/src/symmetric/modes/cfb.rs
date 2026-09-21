//! **CFB — Cipher Feedback**.
//!
//! Self-synchronising stream-cipher mode built from a block cipher:
//!
//! ```text
//!     C_i = P_i ⊕ E(C_{i-1}),     C_0 := IV
//! ```
//!
//! `decrypt` uses `E` (not `D`) — only the encryption direction of the
//! underlying cipher is needed.  Supports arbitrary-length plaintext
//! (no padding) because the last block can be truncated.
//!
//! Standard: NIST SP 800-38A §6.3.
//!
//! ## Properties
//! - **No padding**: stream-cipher-like output length = input length.
//! - **Self-synchronising**: a corrupted ciphertext block affects only
//!   the corresponding plaintext block plus the next one (after which
//!   it self-recovers).
//! - **Parallelisable decryption** (each `D` only needs the previous
//!   ciphertext block); encryption is serial.

use super::cipher::BlockCipher;

/// **CFB encrypt** with full-block feedback, arbitrary plaintext length.
pub fn cfb_encrypt<C: BlockCipher<N>, const N: usize>(
    cipher: &C,
    iv: &[u8; N],
    plaintext: &[u8],
) -> Vec<u8> {
    let mut out = Vec::with_capacity(plaintext.len());
    let mut feedback = *iv;
    for chunk in plaintext.chunks(N) {
        let mut keystream = feedback;
        cipher.encrypt_block(&mut keystream);
        let mut block = [0u8; N];
        let n = chunk.len();
        for i in 0..n {
            block[i] = chunk[i] ^ keystream[i];
        }
        out.extend_from_slice(&block[..n]);
        // Feedback = the full N-byte CIPHERTEXT block (zero-extended
        // for the final short chunk, per SP 800-38A §6.3 "CFB-128"
        // configuration).
        feedback.copy_from_slice(&block);
    }
    out
}

/// **CFB decrypt** — uses the cipher's `encrypt` direction.
pub fn cfb_decrypt<C: BlockCipher<N>, const N: usize>(
    cipher: &C,
    iv: &[u8; N],
    ciphertext: &[u8],
) -> Vec<u8> {
    let mut out = Vec::with_capacity(ciphertext.len());
    let mut feedback = *iv;
    for chunk in ciphertext.chunks(N) {
        let mut keystream = feedback;
        cipher.encrypt_block(&mut keystream);
        let n = chunk.len();
        for i in 0..n {
            out.push(chunk[i] ^ keystream[i]);
        }
        // Feedback = the full N-byte CIPHERTEXT block.
        let mut new_fb = [0u8; N];
        new_fb[..n].copy_from_slice(chunk);
        feedback = new_fb;
    }
    out
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::symmetric::aes::AesKey;

    /// Round-trip on a multiple-of-16 message.
    #[test]
    fn cfb_round_trip_aligned() {
        let key = AesKey::new(&[0u8; 16]).unwrap();
        let iv = [1u8; 16];
        let pt = b"sixteen bytes!!!"; // 16 bytes
        let ct = cfb_encrypt::<_, 16>(&key, &iv, pt);
        assert_eq!(ct.len(), pt.len());
        let recovered = cfb_decrypt::<_, 16>(&key, &iv, &ct);
        assert_eq!(recovered, pt);
    }

    /// Round-trip on a non-multiple message (final short block).
    #[test]
    fn cfb_round_trip_unaligned() {
        let key = AesKey::new(&[0u8; 32]).unwrap();
        let iv = [9u8; 16];
        let pt = b"hello, world!";
        let ct = cfb_encrypt::<_, 16>(&key, &iv, pt);
        assert_eq!(ct.len(), pt.len());
        let recovered = cfb_decrypt::<_, 16>(&key, &iv, &ct);
        assert_eq!(recovered, pt);
    }

    /// **NIST SP 800-38A Appendix F.3 AES-128 CFB128 test vector**.
    #[test]
    fn cfb_aes128_nist_vector() {
        // Key: 2b7e1516 28aed2a6 abf71588 09cf4f3c
        // IV:  000102030405060708090a0b0c0d0e0f
        // PT block 1: 6bc1bee2 2e409f96 e93d7e11 7393172a
        // CT block 1: 3b3fd92e b72dad20 333449f8 e83cfb4a
        let key_bytes = [
            0x2b, 0x7e, 0x15, 0x16, 0x28, 0xae, 0xd2, 0xa6, 0xab, 0xf7, 0x15, 0x88, 0x09, 0xcf,
            0x4f, 0x3c,
        ];
        let iv = [
            0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d,
            0x0e, 0x0f,
        ];
        let pt: [u8; 16] = [
            0x6b, 0xc1, 0xbe, 0xe2, 0x2e, 0x40, 0x9f, 0x96, 0xe9, 0x3d, 0x7e, 0x11, 0x73, 0x93,
            0x17, 0x2a,
        ];
        let expected_ct: [u8; 16] = [
            0x3b, 0x3f, 0xd9, 0x2e, 0xb7, 0x2d, 0xad, 0x20, 0x33, 0x34, 0x49, 0xf8, 0xe8, 0x3c,
            0xfb, 0x4a,
        ];
        let key = AesKey::new(&key_bytes).unwrap();
        let ct = cfb_encrypt::<_, 16>(&key, &iv, &pt);
        assert_eq!(&ct[..], &expected_ct[..]);
        let decrypted = cfb_decrypt::<_, 16>(&key, &iv, &ct);
        assert_eq!(&decrypted[..], &pt[..]);
    }

    /// Bit-flip in ciphertext corrupts exactly the targeted plaintext
    /// byte and the entire next block, then self-recovers (the
    /// "self-synchronising" property).
    #[test]
    fn cfb_self_synchronises_after_corruption() {
        let key = AesKey::new(&[0u8; 16]).unwrap();
        let iv = [0u8; 16];
        let pt = vec![0xAAu8; 64];
        let mut ct = cfb_encrypt::<_, 16>(&key, &iv, &pt);
        ct[5] ^= 0xFF; // flip byte 5
        let recovered = cfb_decrypt::<_, 16>(&key, &iv, &ct);
        // Byte 5 in plaintext is corrupted, all of block 2 (bytes 16..32)
        // is corrupted, but blocks 3 onward are correct.
        assert_ne!(recovered[5], pt[5]);
        assert_ne!(&recovered[16..32], &pt[16..32]);
        assert_eq!(&recovered[32..], &pt[32..]);
    }
}
