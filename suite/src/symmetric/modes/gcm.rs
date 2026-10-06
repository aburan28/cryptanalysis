//! **GCM** — Galois/Counter Mode AEAD, generic over any 16-byte block
//! cipher (NIST SP 800-38D).
//!
//! ## Construction
//!
//! ```text
//!     H = E_K(0^128)                       (GHASH key)
//!     J0 = nonce ‖ 0x00000001              (96-bit nonce profile)
//!     C  = CTR_{E_K}(plaintext, start=2)   (counter 1 reserved for tag)
//!     T  = GHASH(H, AAD, C) ⊕ E_K(J0)
//!     Output = C ‖ T
//! ```
//!
//! GHASH is multiplication in `GF(2^128)` with the GCM polynomial
//! `x^128 + x^7 + x^2 + x + 1`, using the "bit-reflected" byte order.
//!
//! ## Nonce profile
//!
//! Only the 12-byte (96-bit) nonce variant is supported.  The
//! general-nonce profile (where nonces of other lengths are hashed
//! into J0 via GHASH) is intentionally omitted — it's rarely used
//! and creates extra footguns around nonce reuse.
//!
//! ## Why generic
//!
//! GCM was originally specified for AES, but the construction is
//! algebraic in the block cipher — *any* 16-byte block cipher with
//! ≥128-bit security can be plugged in.  Camellia-GCM, Aria-GCM,
//! Twofish-GCM are all well-defined and produce valid AEAD; this
//! module makes those one-liners.
//!
//! AES-GCM is the standardised profile and the one with NIST test
//! vectors — see [`crate::symmetric::aes::aes_gcm_encrypt`] for the
//! AES-typed convenience wrapper that exercises this generic code.

use super::cipher::BlockCipher128;
use subtle::ConstantTimeEq;

/// GF(2^128) multiplication with the GCM polynomial (bit-reflected).
fn gcm_mult(x: &[u8; 16], y: &[u8; 16]) -> [u8; 16] {
    let mut z = [0u8; 16];
    let mut v = *y;
    for i in 0..16 {
        for bit in (0..8).rev() {
            if (x[i] >> bit) & 1 == 1 {
                for j in 0..16 {
                    z[j] ^= v[j];
                }
            }
            let lsb = v[15] & 1;
            for j in (1..16).rev() {
                v[j] = (v[j] >> 1) | (v[j - 1] << 7);
            }
            v[0] >>= 1;
            if lsb == 1 {
                v[0] ^= 0xe1;
            }
        }
    }
    z
}

fn pad_to_block(data: &[u8]) -> Vec<u8> {
    let mut v = data.to_vec();
    let rem = v.len() % 16;
    if rem != 0 {
        v.resize(v.len() + (16 - rem), 0);
    }
    v
}

fn xor_into(dst: &mut [u8; 16], src: &[u8]) {
    for (a, b) in dst.iter_mut().zip(src.iter()) {
        *a ^= b;
    }
}

/// GHASH(H, A, C): authenticate AAD and ciphertext into a 16-byte tag.
fn ghash(h: &[u8; 16], aad: &[u8], ciphertext: &[u8]) -> [u8; 16] {
    let mut y = [0u8; 16];
    for block in pad_to_block(aad).chunks(16) {
        xor_into(&mut y, block);
        y = gcm_mult(&y, h);
    }
    for block in pad_to_block(ciphertext).chunks(16) {
        xor_into(&mut y, block);
        y = gcm_mult(&y, h);
    }
    let mut len_block = [0u8; 16];
    len_block[..8].copy_from_slice(&((aad.len() as u64 * 8).to_be_bytes()));
    len_block[8..].copy_from_slice(&((ciphertext.len() as u64 * 8).to_be_bytes()));
    xor_into(&mut y, &len_block);
    gcm_mult(&y, h)
}

/// Generic CTR over a 16-byte block cipher, starting at the given counter.
fn ctr_from<C: BlockCipher128>(cipher: &C, nonce: &[u8; 12], start: u32, data: &[u8]) -> Vec<u8> {
    let mut out = data.to_vec();
    let mut ctr = start;
    for chunk in out.chunks_mut(16) {
        let mut block = [0u8; 16];
        block[..12].copy_from_slice(nonce);
        block[12..].copy_from_slice(&ctr.to_be_bytes());
        cipher.encrypt_block(&mut block);
        for (b, k) in chunk.iter_mut().zip(block.iter()) {
            *b ^= k;
        }
        ctr = ctr.wrapping_add(1);
    }
    out
}

fn hash_key<C: BlockCipher128>(cipher: &C) -> [u8; 16] {
    let mut h = [0u8; 16];
    cipher.encrypt_block(&mut h);
    h
}

fn encrypt_j0<C: BlockCipher128>(cipher: &C, nonce: &[u8; 12]) -> [u8; 16] {
    let mut j0 = [0u8; 16];
    j0[..12].copy_from_slice(nonce);
    j0[15] = 1;
    cipher.encrypt_block(&mut j0);
    j0
}

/// **GCM encrypt** with a 12-byte nonce.  Returns `ciphertext || 16-byte tag`.
pub fn gcm_encrypt<C: BlockCipher128>(
    cipher: &C,
    nonce: &[u8; 12],
    aad: &[u8],
    plaintext: &[u8],
) -> Vec<u8> {
    let h = hash_key(cipher);
    let ct = ctr_from(cipher, nonce, 2, plaintext);
    let mut tag = ghash(&h, aad, &ct);
    let j0 = encrypt_j0(cipher, nonce);
    for (t, j) in tag.iter_mut().zip(j0.iter()) {
        *t ^= j;
    }
    let mut out = ct;
    out.extend_from_slice(&tag);
    out
}

/// **GCM decrypt**.  Returns the plaintext on tag match; `None` otherwise.
/// Tag comparison is constant-time.
pub fn gcm_decrypt<C: BlockCipher128>(
    cipher: &C,
    nonce: &[u8; 12],
    aad: &[u8],
    ciphertext_and_tag: &[u8],
) -> Option<Vec<u8>> {
    if ciphertext_and_tag.len() < 16 {
        return None;
    }
    let (ct, tag_bytes) = ciphertext_and_tag.split_at(ciphertext_and_tag.len() - 16);
    let h = hash_key(cipher);
    let mut expected = ghash(&h, aad, ct);
    let j0 = encrypt_j0(cipher, nonce);
    for (t, j) in expected.iter_mut().zip(j0.iter()) {
        *t ^= j;
    }
    if expected.ct_eq(tag_bytes).unwrap_u8() != 1 {
        return None;
    }
    Some(ctr_from(cipher, nonce, 2, ct))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::symmetric::aes::AesKey;
    use crate::symmetric::camellia::Camellia128;
    use crate::symmetric::twofish::Twofish;

    /// **NIST AES-GCM test case 3** (SP 800-38D Annex B).  Verifies
    /// the generic implementation against the canonical AES-GCM
    /// vector, proving that AES-GCM emerges naturally from the
    /// generic construction.
    #[test]
    fn nist_aes_gcm_case_3() {
        let key = AesKey::Aes128(
            hex::decode("feffe9928665731c6d6a8f9467308308")
                .unwrap()
                .try_into()
                .unwrap(),
        );
        let nonce: [u8; 12] = hex::decode("cafebabefacedbaddecaf888")
            .unwrap()
            .try_into()
            .unwrap();
        let pt = hex::decode(
            "d9313225f88406e5a55909c5aff5269a86a7a9531534f7da2e4c303d8a318a72\
             1c3c0c95956809532fcf0e2449a6b525b16aedf5aa0de657ba637b391aafd255",
        )
        .unwrap();
        let expected_ct = hex::decode(
            "42831ec2217774244b7221b784d0d49ce3aa212f2c02a4e035c17e2329aca12e\
             21d514b25466931c7d8f6a5aac84aa051ba30b396a0aac973d58e091473f5985",
        )
        .unwrap();
        let expected_tag = hex::decode("4d5c2af327cd64a62cf35abd2ba6fab4").unwrap();

        let out = gcm_encrypt(&key, &nonce, &[], &pt);
        let (ct, tag) = out.split_at(out.len() - 16);
        assert_eq!(ct, &expected_ct[..]);
        assert_eq!(tag, &expected_tag[..]);

        let pt2 = gcm_decrypt(&key, &nonce, &[], &out).expect("decrypt");
        assert_eq!(pt2, pt);
    }

    /// **Camellia-GCM round-trip** — proving the construction works
    /// over a non-AES 16-byte cipher.  No standardised test vectors
    /// exist for Camellia-GCM (RFC 6367 defines TLS suites but not
    /// raw test vectors), so we verify encrypt-then-decrypt
    /// consistency plus tamper detection.
    #[test]
    fn camellia_gcm_round_trip_and_tamper() {
        let cipher = Camellia128::new(&[0x42u8; 16]);
        let nonce = [0x11u8; 12];
        let aad = b"non-aes AEAD";
        let pt = b"GCM is algebraic in the block cipher.".to_vec();

        let ct = gcm_encrypt(&cipher, &nonce, aad, &pt);
        assert_ne!(&ct[..pt.len()], &pt[..]);
        let recovered = gcm_decrypt(&cipher, &nonce, aad, &ct).expect("decrypt");
        assert_eq!(recovered, pt);

        // Flip one ciphertext byte → tag fails.
        let mut tampered = ct.clone();
        tampered[0] ^= 1;
        assert!(gcm_decrypt(&cipher, &nonce, aad, &tampered).is_none());

        // Flip one tag byte → fails.
        let mut tampered = ct.clone();
        let last = tampered.len() - 1;
        tampered[last] ^= 1;
        assert!(gcm_decrypt(&cipher, &nonce, aad, &tampered).is_none());

        // Different AAD → fails.
        assert!(gcm_decrypt(&cipher, &nonce, b"other-aad", &ct).is_none());
    }

    /// **Twofish-GCM round-trip** — same proof for another 16-byte cipher.
    #[test]
    fn twofish_gcm_round_trip() {
        let cipher = Twofish::new(&[0x77u8; 32]).expect("256-bit key");
        let nonce = [0x33u8; 12];
        let aad = b"";
        let pt = b"Twofish + GCM is a perfectly valid AEAD.".to_vec();

        let ct = gcm_encrypt(&cipher, &nonce, aad, &pt);
        let pt2 = gcm_decrypt(&cipher, &nonce, aad, &ct).expect("decrypt");
        assert_eq!(pt2, pt);
    }

    /// Empty plaintext / empty AAD case — pure authenticator.
    #[test]
    fn gcm_empty_pt_empty_aad() {
        let key = AesKey::Aes128([0u8; 16]);
        let nonce = [0u8; 12];
        let out = gcm_encrypt(&key, &nonce, &[], &[]);
        assert_eq!(out.len(), 16); // just the tag
        let pt = gcm_decrypt(&key, &nonce, &[], &out).expect("decrypt");
        assert!(pt.is_empty());
    }
}
