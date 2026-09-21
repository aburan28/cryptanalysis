//! **AES-GCM-SIV** — nonce-misuse-resistant AEAD (RFC 8452).
//!
//! Differs from GCM in three ways:
//!
//! 1. **POLYVAL** instead of GHASH.  POLYVAL is the "natural"
//!    little-endian polynomial-hash variant; algebraically isomorphic
//!    to GHASH but free of GHASH's awkward bit-reversal.
//! 2. **Per-nonce key derivation**: each (master_key, nonce) pair
//!    derives a fresh `(record_auth_key, record_enc_key)` so a nonce
//!    repeat does not catastrophically destroy authenticity (the way
//!    it does for GCM, where the auth key `H = E_K(0)` is fixed and a
//!    nonce repeat lets an attacker recover `H`).
//! 3. **The tag IS the initial counter** (with the top bit set after
//!    XOR with the nonce, and bit 31 of the high half cleared) — so
//!    decryption can recompute and compare the tag with no separate
//!    GMAC step.
//!
//! ## Algorithm
//!
//! Given master key `K` (16 or 32 bytes) and 12-byte nonce `N`:
//!
//! ```text
//!     # Derive subkeys via AES_K on counter blocks (i || N)_le.
//!     # First-8-byte extracts of each block, concatenated:
//!     H = (AES_K(0||N))[0..8] || (AES_K(1||N))[0..8]            -- 16 bytes, auth key
//!     K_e = (AES_K(2||N))[0..8] || (AES_K(3||N))[0..8]
//!           [|| (AES_K(4||N))[0..8] || (AES_K(5||N))[0..8]]      -- 16 or 32 bytes
//!
//!     # Length block: (|AAD|_bits || |PT|_bits) as 8-byte LE each.
//!     LB = u64_le(|AAD|*8) || u64_le(|PT|*8)
//!
//!     # POLYVAL over pad(AAD) || pad(PT) || LB.
//!     S_s = POLYVAL_H(AAD || zeros... || PT || zeros... || LB)
//!     S_s[0..12] ⊕= N
//!     S_s[15] &= 0x7F
//!     Tag = AES_K_e(S_s)
//!
//!     # CTR with initial counter = Tag (top bit set).
//!     ctr0 = Tag; ctr0[15] |= 0x80
//!     C = CTR_{K_e}(P, ctr0)
//!     Output = C || Tag
//! ```
//!
//! ## References
//!
//! - **RFC 8452** — AES-GCM-SIV.
//! - **Gueron-Lindell**, *GCM-SIV: Full Nonce Misuse-Resistant
//!   Authenticated Encryption at Under One Cycle per Byte*, CCS 2015.

use super::cipher::BlockCipher128;
use crate::symmetric::aes::AesKey;

#[inline]
fn enc<C: BlockCipher128>(cipher: &C, block: &[u8; 16]) -> [u8; 16] {
    let mut b = *block;
    cipher.encrypt_block(&mut b);
    b
}

// ── POLYVAL ──────────────────────────────────────────────────────────
//
// POLYVAL operates on 16-byte blocks viewed as elements of GF(2^128)
// under reduction polynomial `x^128 + x^127 + x^126 + x^121 + 1`,
// little-endian byte order (byte 0 = least-significant byte).
//
// Two-block POLYVAL is: POLYVAL_H(X1, X2) = (X1 * H + X2) * H,
// folding via Horner's rule.

/// Multiply by `x` in POLYVAL's GF(2^128) with on-the-fly reduction.
///
/// Left-shift the u128 by 1; if the high bit (bit 127) was set, XOR
/// with the reduction constant `byte 0 = 0x01, byte 15 = 0xC2`
/// (equivalent: bits 0, 121, 126, 127 set in the u128).
///
/// `multX_POLYVAL` per RFC 8452 §3.
fn multx_polyval(x: u128) -> u128 {
    let msb = (x >> 127) & 1;
    let shifted = x << 1;
    let c = 1u128 | (1u128 << 121) | (1u128 << 126) | (1u128 << 127);
    shifted ^ (c & 0u128.wrapping_sub(msb))
}

/// Multiply by `x^(-1)` (inverse of `multx_polyval`).
///
/// Right-shift the u128 by 1; if bit 0 was set, the original input
/// had bit 127 set (the multX path that XOR'd in the constant), so
/// we XOR with the constant *before* shifting and then OR back bit 127.
fn divx_polyval(x: u128) -> u128 {
    let bit = x & 1;
    let mask = 0u128.wrapping_sub(bit);
    let c = 1u128 | (1u128 << 121) | (1u128 << 126) | (1u128 << 127);
    ((x ^ (c & mask)) >> 1) | ((1u128 << 127) & mask)
}

/// **POLYVAL's dot product** in GF(2^128):  `dot(a, b) = a · b · x^(-128)`
/// modulo the reduction polynomial `x^128 + x^127 + x^126 + x^121 + 1`.
///
/// This is POLYVAL's actual multiplication (RFC 8452 §3 calls it
/// `dot`, equivalent to multiplying in GHASH's representation under
/// a different reduction polynomial then applying a single
/// `multX` to compensate for the bit-ordering offset).
///
/// Implementation: compute the raw 256-bit polynomial product `a · b`
/// by Horner over bits of `b`, accumulating `a · x^i` for each set
/// bit `i`; then apply `multX^(-1)` 128 times to absorb the
/// `x^(-128)` factor.  Equivalent formulations interleave the divX
/// into the main loop for a single pass; this two-pass version is
/// clearer.
pub fn polyval_mul(a: &[u8; 16], b: &[u8; 16]) -> [u8; 16] {
    let mut a_u = u128::from_le_bytes(*a);
    let b_u = u128::from_le_bytes(*b);
    // Pass 1: compute `a · b` (mod R) using multX after each bit.
    let mut result: u128 = 0;
    for i in 0..128 {
        let mask = 0u128.wrapping_sub((b_u >> i) & 1);
        result ^= a_u & mask;
        a_u = multx_polyval(a_u);
    }
    // Pass 2: apply x^(-128) — divide by x 128 times.
    for _ in 0..128 {
        result = divx_polyval(result);
    }
    let lo64 = result as u64;
    let hi64 = (result >> 64) as u64;
    let mut out = [0u8; 16];
    out[0..8].copy_from_slice(&lo64.to_le_bytes());
    out[8..16].copy_from_slice(&hi64.to_le_bytes());
    out
}

/// **POLYVAL hash**.  Folds 16-byte `blocks` into a single 16-byte
/// digest under key `H`.  `data` must be a multiple of 16 bytes (the
/// caller pads as required by RFC 8452).
pub fn polyval(h: &[u8; 16], data: &[u8]) -> [u8; 16] {
    assert_eq!(
        data.len() % 16,
        0,
        "POLYVAL input must be padded to 16-byte blocks"
    );
    let mut s = [0u8; 16];
    for chunk in data.chunks(16) {
        let mut blk = [0u8; 16];
        blk.copy_from_slice(chunk);
        // S = (S ⊕ X) * H
        for i in 0..16 {
            s[i] ^= blk[i];
        }
        s = polyval_mul(&s, h);
    }
    s
}

// ── Key derivation per RFC 8452 §4 ───────────────────────────────────

/// Generic key derivation.  Returns `(auth_key, enc_key_bytes)`.
/// `enc_key_len` is 16 or 32 per RFC 8452.
fn derive_key_bytes<C: BlockCipher128>(
    master: &C,
    nonce: &[u8; 12],
    enc_key_len: usize,
) -> ([u8; 16], Vec<u8>) {
    assert!(enc_key_len == 16 || enc_key_len == 32);
    let mut auth = [0u8; 16];
    let mut enc_buf = vec![0u8; enc_key_len];
    let n_blocks_enc = enc_key_len / 8;
    // Auth blocks: indices 0, 1.
    for i in 0..2u32 {
        let mut blk = [0u8; 16];
        blk[0..4].copy_from_slice(&i.to_le_bytes());
        blk[4..16].copy_from_slice(nonce);
        let e = enc(master, &blk);
        auth[(i as usize) * 8..(i as usize + 1) * 8].copy_from_slice(&e[0..8]);
    }
    // Enc-key blocks: indices 2, 3 (and 4, 5 if 32-byte master).
    for i in 0..n_blocks_enc {
        let mut blk = [0u8; 16];
        blk[0..4].copy_from_slice(&((i as u32) + 2).to_le_bytes());
        blk[4..16].copy_from_slice(nonce);
        let e = enc(master, &blk);
        enc_buf[i * 8..(i + 1) * 8].copy_from_slice(&e[0..8]);
    }
    (auth, enc_buf)
}

// ── GCM-SIV encrypt / decrypt ────────────────────────────────────────

fn pad16(data: &[u8]) -> Vec<u8> {
    let mut v = data.to_vec();
    while !v.len().is_multiple_of(16) {
        v.push(0);
    }
    v
}

fn length_block(aad_len: usize, pt_len: usize) -> [u8; 16] {
    let mut lb = [0u8; 16];
    let aad_bits = (aad_len as u64) * 8;
    let pt_bits = (pt_len as u64) * 8;
    lb[0..8].copy_from_slice(&aad_bits.to_le_bytes());
    lb[8..16].copy_from_slice(&pt_bits.to_le_bytes());
    lb
}

fn ctr_encrypt<C: BlockCipher128>(cipher: &C, init_ctr: &[u8; 16], data: &[u8]) -> Vec<u8> {
    let mut ctr = *init_ctr;
    let mut out = Vec::with_capacity(data.len());
    let mut idx = 0;
    while idx < data.len() {
        let ks = enc(cipher, &ctr);
        let n = 16.min(data.len() - idx);
        for i in 0..n {
            out.push(data[idx + i] ^ ks[i]);
        }
        idx += n;
        // Increment LITTLE-ENDIAN 32-bit counter in bytes 0..4 of ctr.
        let mut c = u32::from_le_bytes([ctr[0], ctr[1], ctr[2], ctr[3]]);
        c = c.wrapping_add(1);
        ctr[0..4].copy_from_slice(&c.to_le_bytes());
    }
    out
}

/// **GCM-SIV encrypt** (RFC 8452), generic over any 16-byte block cipher.
///
/// `master` is the master cipher (16- or 32-byte key per RFC 8452).
/// `enc_key_len` is the master's key length in bytes (16 or 32).
/// `new_cipher` is a factory that builds a fresh `C` instance from the
/// derived enc-key bytes.
///
/// The standard AES-typed entry points [`gcm_siv_encrypt`] /
/// [`gcm_siv_decrypt`] are thin wrappers over this.
pub fn gcm_siv_encrypt_with<M, C, F>(
    master: &M,
    enc_key_len: usize,
    nonce: &[u8; 12],
    aad: &[u8],
    plaintext: &[u8],
    new_cipher: F,
) -> Vec<u8>
where
    M: BlockCipher128,
    C: BlockCipher128,
    F: Fn(&[u8]) -> C,
{
    let (auth_key, enc_key_bytes) = derive_key_bytes(master, nonce, enc_key_len);
    let enc_cipher = new_cipher(&enc_key_bytes);
    let mut polyval_input = Vec::new();
    polyval_input.extend_from_slice(&pad16(aad));
    polyval_input.extend_from_slice(&pad16(plaintext));
    polyval_input.extend_from_slice(&length_block(aad.len(), plaintext.len()));
    let mut s_s = polyval(&auth_key, &polyval_input);
    for i in 0..12 {
        s_s[i] ^= nonce[i];
    }
    s_s[15] &= 0x7F;
    let tag = enc(&enc_cipher, &s_s);
    let mut ctr0 = tag;
    ctr0[15] |= 0x80;
    let ct = ctr_encrypt(&enc_cipher, &ctr0, plaintext);
    let mut out = Vec::with_capacity(ct.len() + 16);
    out.extend_from_slice(&ct);
    out.extend_from_slice(&tag);
    out
}

/// **GCM-SIV decrypt + verify**, generic over any 16-byte block cipher.
pub fn gcm_siv_decrypt_with<M, C, F>(
    master: &M,
    enc_key_len: usize,
    nonce: &[u8; 12],
    aad: &[u8],
    ciphertext_with_tag: &[u8],
    new_cipher: F,
) -> Option<Vec<u8>>
where
    M: BlockCipher128,
    C: BlockCipher128,
    F: Fn(&[u8]) -> C,
{
    if ciphertext_with_tag.len() < 16 {
        return None;
    }
    let ct_len = ciphertext_with_tag.len() - 16;
    let ct = &ciphertext_with_tag[..ct_len];
    let mut recv_tag = [0u8; 16];
    recv_tag.copy_from_slice(&ciphertext_with_tag[ct_len..]);
    let (auth_key, enc_key_bytes) = derive_key_bytes(master, nonce, enc_key_len);
    let enc_cipher = new_cipher(&enc_key_bytes);
    let mut ctr0 = recv_tag;
    ctr0[15] |= 0x80;
    let pt = ctr_encrypt(&enc_cipher, &ctr0, ct);
    let mut polyval_input = Vec::new();
    polyval_input.extend_from_slice(&pad16(aad));
    polyval_input.extend_from_slice(&pad16(&pt));
    polyval_input.extend_from_slice(&length_block(aad.len(), pt.len()));
    let mut s_s = polyval(&auth_key, &polyval_input);
    for i in 0..12 {
        s_s[i] ^= nonce[i];
    }
    s_s[15] &= 0x7F;
    let expected_tag = enc(&enc_cipher, &s_s);
    let mut diff = 0u8;
    for i in 0..16 {
        diff |= expected_tag[i] ^ recv_tag[i];
    }
    if diff != 0 {
        return None;
    }
    Some(pt)
}

/// **AES-GCM-SIV encrypt** (RFC 8452).  Returns `ciphertext || 16-byte tag`.
/// Thin wrapper over the generic [`gcm_siv_encrypt_with`].
pub fn gcm_siv_encrypt(master: &AesKey, nonce: &[u8; 12], aad: &[u8], plaintext: &[u8]) -> Vec<u8> {
    let kl = master.key_len();
    gcm_siv_encrypt_with(master, kl, nonce, aad, plaintext, |bytes| {
        AesKey::new(bytes).expect("derived AES key bytes")
    })
}

/// **AES-GCM-SIV decrypt + verify**.  Thin wrapper over
/// [`gcm_siv_decrypt_with`].
pub fn gcm_siv_decrypt(
    master: &AesKey,
    nonce: &[u8; 12],
    aad: &[u8],
    ciphertext_with_tag: &[u8],
) -> Option<Vec<u8>> {
    let kl = master.key_len();
    gcm_siv_decrypt_with(master, kl, nonce, aad, ciphertext_with_tag, |bytes| {
        AesKey::new(bytes).expect("derived AES key bytes")
    })
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn h(s: &str) -> Vec<u8> {
        let s: String = s.chars().filter(|c| !c.is_whitespace()).collect();
        (0..s.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
            .collect()
    }

    /// POLYVAL self-consistency: H * 0 = 0.
    #[test]
    fn polyval_zero() {
        let h = [0u8; 16];
        let zero = [0u8; 16];
        assert_eq!(polyval_mul(&h, &zero), [0u8; 16]);
    }

    /// **Published POLYVAL test vector** (Gueron-Langley-Lindell 2017
    /// "AES-GCM-SIV: Specification and Analysis"):
    ///
    ///     H  = 25629347589242761d31f826ba4b757b
    ///     X1 = 4f4f95668c83dfb6401762bb2d01a262
    ///     X2 = d1a24ddd2721d006bbe45f20d3c9f362
    ///     POLYVAL(H, X1 || X2) = f7a3b47b846119fae5b7866cf5e5b77e
    ///
    /// All hex strings are byte-by-byte (byte 0 is the leftmost pair
    /// of hex digits), consistent with the LE byte order POLYVAL uses
    /// natively.
    #[test]
    fn polyval_published_vector() {
        let h_bytes = h("25629347589242761d31f826ba4b757b");
        let mut h_arr = [0u8; 16];
        h_arr.copy_from_slice(&h_bytes);
        let x = h("4f4f95668c83dfb6401762bb2d01a262 \
             d1a24ddd2721d006bbe45f20d3c9f362");
        let expected = h("f7a3b47b846119fae5b7866cf5e5b77e");
        let result = polyval(&h_arr, &x);
        // Debug aid: print both representations so any divergence is
        // visible in test output.
        eprintln!("polyval got:      {}", to_hex(&result));
        eprintln!("polyval expected: {}", to_hex(&expected));
        assert_eq!(&result[..], &expected[..]);
    }

    fn to_hex(bytes: &[u8]) -> String {
        bytes.iter().map(|b| format!("{:02x}", b)).collect()
    }

    /// POLYVAL multiplication is commutative.
    #[test]
    fn polyval_commutative() {
        let a = [
            0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E,
            0x0F, 0x10,
        ];
        let b = [
            0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E,
            0x1F, 0x20,
        ];
        assert_eq!(polyval_mul(&a, &b), polyval_mul(&b, &a));
    }

    /// Round-trip with empty AAD and short plaintext.
    #[test]
    fn gcm_siv_round_trip_short() {
        let key = AesKey::new(&[0u8; 16]).unwrap();
        let nonce = [0u8; 12];
        let pt = b"hello GCM-SIV";
        let ct = gcm_siv_encrypt(&key, &nonce, b"", pt);
        assert_eq!(ct.len(), pt.len() + 16);
        let recovered = gcm_siv_decrypt(&key, &nonce, b"", &ct).unwrap();
        assert_eq!(recovered, pt);
    }

    /// Round-trip with AAD.
    #[test]
    fn gcm_siv_round_trip_with_aad() {
        let key = AesKey::new(&[7u8; 32]).unwrap();
        let nonce = [9u8; 12];
        let aad = b"associated data";
        let pt = b"plaintext content of arbitrary length";
        let ct = gcm_siv_encrypt(&key, &nonce, aad, pt);
        let recovered = gcm_siv_decrypt(&key, &nonce, aad, &ct).unwrap();
        assert_eq!(recovered, pt);
    }

    /// Tampered ciphertext fails.
    #[test]
    fn gcm_siv_rejects_tampered_ct() {
        let key = AesKey::new(&[0u8; 16]).unwrap();
        let nonce = [0u8; 12];
        let mut ct = gcm_siv_encrypt(&key, &nonce, b"", b"plaintext");
        ct[2] ^= 1;
        assert!(gcm_siv_decrypt(&key, &nonce, b"", &ct).is_none());
    }

    /// Tampered AAD fails.
    #[test]
    fn gcm_siv_rejects_tampered_aad() {
        let key = AesKey::new(&[1u8; 16]).unwrap();
        let nonce = [2u8; 12];
        let ct = gcm_siv_encrypt(&key, &nonce, b"aad", b"pt");
        assert!(gcm_siv_decrypt(&key, &nonce, b"AAD", &ct).is_none());
    }

    /// **Misuse resistance**: repeating the (key, nonce, aad, pt) tuple
    /// yields the same ciphertext.  Repeating (key, nonce) with
    /// *different* plaintexts does NOT leak the plaintext beyond
    /// equality (a property of all SIV-class AEADs).
    #[test]
    fn gcm_siv_deterministic() {
        let key = AesKey::new(&[5u8; 16]).unwrap();
        let nonce = [3u8; 12];
        let ct1 = gcm_siv_encrypt(&key, &nonce, b"a", b"plaintext");
        let ct2 = gcm_siv_encrypt(&key, &nonce, b"a", b"plaintext");
        assert_eq!(ct1, ct2);
    }

    /// **RFC 8452 Appendix C.1 first AES-128 vector**.
    ///
    /// Plaintext: (empty)
    /// AAD:       (empty)
    /// Key:       01000000000000000000000000000000
    /// Nonce:     030000000000000000000000
    /// Result:    dc20e2d83f25705bb49e439eca56de25
    #[test]
    fn gcm_siv_rfc8452_c1_empty_aes128() {
        let key = AesKey::new(&h("01000000000000000000000000000000")).unwrap();
        let nonce_v = h("030000000000000000000000");
        let mut nonce = [0u8; 12];
        nonce.copy_from_slice(&nonce_v);
        let expected = h("dc20e2d83f25705bb49e439eca56de25");
        let out = gcm_siv_encrypt(&key, &nonce, b"", b"");
        assert_eq!(out, expected);
        // Round-trip.
        let recovered = gcm_siv_decrypt(&key, &nonce, b"", &out).unwrap();
        assert!(recovered.is_empty());
    }

    /// **RFC 8452 Appendix C.1 vector 2** — 8-byte plaintext, empty AAD.
    ///
    /// Plaintext: 0100000000000000
    /// Key:       01000000000000000000000000000000
    /// Nonce:     030000000000000000000000
    /// Result:    b5d839330ac7b786 578782fff6013b815b287c22493a364c
    #[test]
    fn gcm_siv_rfc8452_c1_8byte_aes128() {
        let key = AesKey::new(&h("01000000000000000000000000000000")).unwrap();
        let nonce_v = h("030000000000000000000000");
        let mut nonce = [0u8; 12];
        nonce.copy_from_slice(&nonce_v);
        let pt = h("0100000000000000");
        let expected = h("b5d839330ac7b786 578782fff6013b815b287c22493a364c");
        let out = gcm_siv_encrypt(&key, &nonce, b"", &pt);
        assert_eq!(out, expected);
        let recovered = gcm_siv_decrypt(&key, &nonce, b"", &out).unwrap();
        assert_eq!(recovered, pt);
    }

    /// **Camellia-GCM-SIV** round-trip + tamper.  No standardised
    /// test vectors exist (RFC 8452 is AES-only), so we verify
    /// encrypt → decrypt → match plus tag-tamper rejection.
    #[test]
    fn gcm_siv_camellia_round_trip() {
        use crate::symmetric::camellia::Camellia128;
        let master = Camellia128::new(&[0x42u8; 16]);
        let nonce = [0x99u8; 12];
        let aad = b"non-AES GCM-SIV";
        let pt = b"GCM-SIV is algebraic in the block cipher.".to_vec();

        let ct = gcm_siv_encrypt_with(&master, 16, &nonce, aad, &pt, |bytes| {
            let mut k = [0u8; 16];
            k.copy_from_slice(bytes);
            Camellia128::new(&k)
        });
        let recovered = gcm_siv_decrypt_with(&master, 16, &nonce, aad, &ct, |bytes| {
            let mut k = [0u8; 16];
            k.copy_from_slice(bytes);
            Camellia128::new(&k)
        })
        .expect("decrypt");
        assert_eq!(recovered, pt);

        // Tag tamper → reject.
        let mut tampered = ct.clone();
        let last = tampered.len() - 1;
        tampered[last] ^= 1;
        let rejected = gcm_siv_decrypt_with(&master, 16, &nonce, aad, &tampered, |bytes| {
            let mut k = [0u8; 16];
            k.copy_from_slice(bytes);
            Camellia128::new(&k)
        });
        assert!(rejected.is_none());
    }
}
