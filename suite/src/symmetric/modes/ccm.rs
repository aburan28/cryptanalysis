//! **CCM — Counter with CBC-MAC** AEAD mode.
//!
//! Standards: NIST SP 800-38C, RFC 3610 (the original WiFi WEP-fix
//! profile).  CCM combines CTR encryption with a CBC-MAC tag in a
//! "MAC-then-encrypt-the-MAC" construction.
//!
//! ## Algorithm sketch
//!
//! Parameters: `L` ∈ {2..8} (length-field bytes), `M` ∈ {4, 6, 8, 10,
//! 12, 14, 16} (tag bytes), `nonce_len = 15 − L`.
//!
//! 1. **Format `B_0`**: `flags || nonce || plaintext_len` where
//!    `flags = (aad?<<6) | ((M-2)/2)<<3 | (L-1)`.
//! 2. **CBC-MAC chain**: `B_0`, then a length-prefixed AAD chunk,
//!    then the plaintext, each zero-padded to a multiple of 16.
//!    Tag `T = first M bytes of the final CBC-MAC state`.
//! 3. **CTR encrypt** the plaintext with counter blocks
//!    `A_i = (L−1) || nonce || i` for `i = 1, 2, …`.
//! 4. **Authenticated tag**: `U = T ⊕ first M bytes of E(A_0)`.
//!
//! Output: `ciphertext || U`.  Decryption reverses with constant-time
//! tag comparison.
//!
//! ## Implementation notes
//!
//! We hard-code `L = 4` (4-byte length field ⇒ 11-byte nonces, max
//! plaintext `2^32 − 1` bytes) for simplicity.  This matches the
//! common SP 800-38C profile for 96-bit nonces.

use super::cipher::BlockCipher;

const L: usize = 4; // length field bytes
const NONCE_LEN: usize = 15 - L; // 11 bytes

/// Tag length: must be one of `{4, 6, 8, 10, 12, 14, 16}`.  Returned
/// by [`ccm_encrypt`]; required by [`ccm_decrypt`].
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CcmTagLen {
    Bytes4 = 4,
    Bytes8 = 8,
    Bytes12 = 12,
    Bytes16 = 16,
}

fn format_b0(tag_len: usize, nonce: &[u8; NONCE_LEN], pt_len: usize, has_aad: bool) -> [u8; 16] {
    let mut b0 = [0u8; 16];
    let flags = ((has_aad as u8) << 6) | (((tag_len as u8 - 2) / 2) << 3) | ((L as u8) - 1);
    b0[0] = flags;
    b0[1..1 + NONCE_LEN].copy_from_slice(nonce);
    // Plaintext length, big-endian, in the trailing L bytes.
    let pt_len_bytes = (pt_len as u32).to_be_bytes();
    b0[12..16].copy_from_slice(&pt_len_bytes);
    b0
}

pub fn ccm_plaintext_len_supported(len: usize) -> bool {
    len <= u32::MAX as usize
}

fn format_aad(aad: &[u8]) -> Vec<u8> {
    // Length-prefix encoding per SP 800-38C §A.2.2.
    let mut out = Vec::new();
    let len = aad.len();
    if len == 0 {
        return out;
    }
    if len < 0xFF00 {
        out.push((len >> 8) as u8);
        out.push((len & 0xFF) as u8);
    } else if (len as u64) < (1u64 << 32) {
        out.push(0xFF);
        out.push(0xFE);
        out.extend_from_slice(&(len as u32).to_be_bytes());
    } else {
        out.push(0xFF);
        out.push(0xFF);
        out.extend_from_slice(&(len as u64).to_be_bytes());
    }
    out.extend_from_slice(aad);
    // Zero-pad to 16-byte boundary.
    while out.len() % 16 != 0 {
        out.push(0);
    }
    out
}

fn cbc_mac<C: BlockCipher<16>>(cipher: &C, blocks: &[u8]) -> [u8; 16] {
    debug_assert_eq!(blocks.len() % 16, 0);
    let mut x = [0u8; 16];
    for chunk in blocks.chunks(16) {
        for i in 0..16 {
            x[i] ^= chunk[i];
        }
        cipher.encrypt_block(&mut x);
    }
    x
}

fn ctr_block(counter: u32, nonce: &[u8; NONCE_LEN]) -> [u8; 16] {
    let mut blk = [0u8; 16];
    blk[0] = (L as u8) - 1;
    blk[1..1 + NONCE_LEN].copy_from_slice(nonce);
    blk[12..16].copy_from_slice(&counter.to_be_bytes());
    blk
}

/// **CCM encrypt**.  Returns `ciphertext || tag` (tag_len bytes).
///
/// `nonce` must be 11 bytes (= 15 − L with our chosen L = 4).
/// `aad` may be empty.  `plaintext` may be empty.
pub fn ccm_encrypt<C: BlockCipher<16>>(
    cipher: &C,
    nonce: &[u8; NONCE_LEN],
    aad: &[u8],
    plaintext: &[u8],
    tag_len: CcmTagLen,
) -> Vec<u8> {
    ccm_encrypt_checked(cipher, nonce, aad, plaintext, tag_len)
        .expect("CCM plaintext too long for L=4 length field")
}

/// Checked CCM encrypt that rejects plaintext lengths not encodable with L=4.
pub fn ccm_encrypt_checked<C: BlockCipher<16>>(
    cipher: &C,
    nonce: &[u8; NONCE_LEN],
    aad: &[u8],
    plaintext: &[u8],
    tag_len: CcmTagLen,
) -> Result<Vec<u8>, &'static str> {
    if !ccm_plaintext_len_supported(plaintext.len()) {
        return Err("CCM plaintext too long for L=4");
    }
    let m = tag_len as usize;
    // ── 1) CBC-MAC chain ──────────────────────────────────────────────
    let mut chain = Vec::new();
    chain.extend_from_slice(&format_b0(m, nonce, plaintext.len(), !aad.is_empty()));
    chain.extend_from_slice(&format_aad(aad));
    chain.extend_from_slice(plaintext);
    while chain.len() % 16 != 0 {
        chain.push(0);
    }
    let t = cbc_mac(cipher, &chain);
    // ── 2) CTR encrypt: keystream from A_1, A_2, … ────────────────────
    let mut ct = Vec::with_capacity(plaintext.len() + m);
    let mut counter: u32 = 1;
    let mut idx = 0;
    while idx < plaintext.len() {
        let mut ks = ctr_block(counter, nonce);
        cipher.encrypt_block(&mut ks);
        let n = 16.min(plaintext.len() - idx);
        for i in 0..n {
            ct.push(plaintext[idx + i] ^ ks[i]);
        }
        idx += n;
        counter = counter.wrapping_add(1);
    }
    // ── 3) Authenticated tag: T ⊕ first M bytes of E(A_0) ────────────
    let mut s0 = ctr_block(0, nonce);
    cipher.encrypt_block(&mut s0);
    for i in 0..m {
        ct.push(t[i] ^ s0[i]);
    }
    Ok(ct)
}

/// **CCM decrypt + verify**.  Returns `None` on tag mismatch (the
/// standard CCM failure response).
pub fn ccm_decrypt<C: BlockCipher<16>>(
    cipher: &C,
    nonce: &[u8; NONCE_LEN],
    aad: &[u8],
    ciphertext_with_tag: &[u8],
    tag_len: CcmTagLen,
) -> Option<Vec<u8>> {
    let m = tag_len as usize;
    if ciphertext_with_tag.len() < m {
        return None;
    }
    let ct_len = ciphertext_with_tag.len() - m;
    if !ccm_plaintext_len_supported(ct_len) {
        return None;
    }
    let ct = &ciphertext_with_tag[..ct_len];
    let recv_u = &ciphertext_with_tag[ct_len..];

    // ── 1) CTR-decrypt to recover plaintext ───────────────────────────
    let mut pt = Vec::with_capacity(ct_len);
    let mut counter: u32 = 1;
    let mut idx = 0;
    while idx < ct_len {
        let mut ks = ctr_block(counter, nonce);
        cipher.encrypt_block(&mut ks);
        let n = 16.min(ct_len - idx);
        for i in 0..n {
            pt.push(ct[idx + i] ^ ks[i]);
        }
        idx += n;
        counter = counter.wrapping_add(1);
    }

    // ── 2) Recompute CBC-MAC tag T over recovered plaintext ──────────
    let mut chain = Vec::new();
    chain.extend_from_slice(&format_b0(m, nonce, ct_len, !aad.is_empty()));
    chain.extend_from_slice(&format_aad(aad));
    chain.extend_from_slice(&pt);
    while chain.len() % 16 != 0 {
        chain.push(0);
    }
    let t_computed = cbc_mac(cipher, &chain);

    // ── 3) Verify: T_computed ⊕ S_0 == recv_u (constant-time-ish) ────
    let mut s0 = ctr_block(0, nonce);
    cipher.encrypt_block(&mut s0);
    let mut diff = 0u8;
    for i in 0..m {
        diff |= (t_computed[i] ^ s0[i]) ^ recv_u[i];
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
    use crate::symmetric::aes::AesKey;

    /// Round-trip basic test.
    #[test]
    fn ccm_round_trip() {
        let key = AesKey::new(&[0u8; 16]).unwrap();
        let nonce = [0x42u8; NONCE_LEN];
        let aad = b"associated data";
        let pt = b"plaintext goes here";
        let ct = ccm_encrypt(&key, &nonce, aad, pt, CcmTagLen::Bytes16);
        assert_eq!(ct.len(), pt.len() + 16);
        let recovered =
            ccm_decrypt(&key, &nonce, aad, &ct, CcmTagLen::Bytes16).expect("CCM should verify");
        assert_eq!(recovered, pt);
    }

    /// Tampered ciphertext fails verification.
    #[test]
    fn ccm_rejects_tampered_ciphertext() {
        let key = AesKey::new(&[1u8; 16]).unwrap();
        let nonce = [0u8; NONCE_LEN];
        let pt = b"secret";
        let mut ct = ccm_encrypt(&key, &nonce, b"", pt, CcmTagLen::Bytes8);
        ct[0] ^= 1;
        assert!(ccm_decrypt(&key, &nonce, b"", &ct, CcmTagLen::Bytes8).is_none());
    }

    /// Tampered AAD fails verification.
    #[test]
    fn ccm_rejects_tampered_aad() {
        let key = AesKey::new(&[2u8; 16]).unwrap();
        let nonce = [3u8; NONCE_LEN];
        let pt = b"data";
        let ct = ccm_encrypt(&key, &nonce, b"aad", pt, CcmTagLen::Bytes12);
        assert!(ccm_decrypt(&key, &nonce, b"AAD", &ct, CcmTagLen::Bytes12).is_none());
    }

    /// Empty plaintext + empty AAD: tag-only AEAD.
    #[test]
    fn ccm_empty_pt_empty_aad() {
        let key = AesKey::new(&[0u8; 16]).unwrap();
        let nonce = [0u8; NONCE_LEN];
        let ct = ccm_encrypt(&key, &nonce, b"", b"", CcmTagLen::Bytes16);
        assert_eq!(ct.len(), 16);
        let recovered = ccm_decrypt(&key, &nonce, b"", &ct, CcmTagLen::Bytes16).unwrap();
        assert!(recovered.is_empty());
    }

    /// AAD-only authentication (no plaintext).
    #[test]
    fn ccm_aad_only_works() {
        let key = AesKey::new(&[7u8; 16]).unwrap();
        let nonce = [9u8; NONCE_LEN];
        let aad = b"only the AAD is authenticated";
        let ct = ccm_encrypt(&key, &nonce, aad, b"", CcmTagLen::Bytes16);
        let _ = ccm_decrypt(&key, &nonce, aad, &ct, CcmTagLen::Bytes16).unwrap();
        // Wrong AAD must fail.
        assert!(ccm_decrypt(&key, &nonce, b"different", &ct, CcmTagLen::Bytes16).is_none());
    }

    /// Different tag lengths give different ciphertext lengths.
    #[test]
    fn ccm_tag_lengths() {
        let key = AesKey::new(&[5u8; 16]).unwrap();
        let nonce = [0u8; NONCE_LEN];
        let pt = b"hi";
        for tag in [
            CcmTagLen::Bytes4,
            CcmTagLen::Bytes8,
            CcmTagLen::Bytes12,
            CcmTagLen::Bytes16,
        ] {
            let ct = ccm_encrypt(&key, &nonce, b"", pt, tag);
            assert_eq!(ct.len(), pt.len() + tag as usize);
            assert_eq!(
                ccm_decrypt(&key, &nonce, b"", &ct, tag).unwrap(),
                pt.to_vec()
            );
        }
    }

    #[test]
    fn ccm_rejects_unencodable_lengths_without_allocating() {
        assert!(ccm_plaintext_len_supported(u32::MAX as usize));
        assert!(!ccm_plaintext_len_supported(u32::MAX as usize + 1));
    }
}
