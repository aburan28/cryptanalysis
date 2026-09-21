//! **EAX** — Bellare-Rogaway-Wagner AEAD (2004).
//!
//! Two-pass AEAD built from a block cipher's CMAC and CTR modes.
//! Provably secure, patent-free, and slightly simpler than CCM
//! (no length-pre-declaration constraint).  Not standardised by NIST
//! but widely deployed in ANSI C12.22, ISO/IEC 19772, and several
//! IoT protocols.
//!
//! ## Algorithm
//!
//! Three CMACs each prefixed by a 1-byte domain separator block
//! (`[i]^128`, i.e. a 16-byte block with `i` in the last byte):
//!
//! ```text
//!     N' = CMAC_K([0]^128 || N)
//!     H' = CMAC_K([1]^128 || H)
//!     C  = CTR_K(P, starting counter = N')
//!     T'' = CMAC_K([2]^128 || C)
//!     Tag = (N' ⊕ H' ⊕ T'') truncated to tag_len
//!     Output = C || Tag
//! ```
//!
//! ## Properties
//!
//! - **Two-pass over the plaintext** (one for CTR, one for the
//!   CMAC over the ciphertext).
//! - **Arbitrary nonce length** (no fixed 96-bit constraint like GCM).
//! - **Single-key**: only one AES key needed, in contrast to SIV's
//!   K1 || K2 split.
//!
//! ## References
//!
//! - **M. Bellare, P. Rogaway, D. Wagner**, *The EAX Mode of Operation*,
//!   FSE 2004.

use super::cipher::BlockCipher128;
use crate::symmetric::cmac::cmac;

/// OMAC^t_K(X): CMAC of `[t]^128 || X` (16 zero bytes + the byte `t`
/// in position 15, then `X` concatenated).
fn omac_t<C: BlockCipher128>(cipher: &C, t: u8, x: &[u8]) -> [u8; 16] {
    let mut buf = Vec::with_capacity(16 + x.len());
    let mut prefix = [0u8; 16];
    prefix[15] = t;
    buf.extend_from_slice(&prefix);
    buf.extend_from_slice(x);
    cmac(cipher, &buf)
}

/// CTR with a 16-byte initial counter (incremented big-endian).
fn ctr<C: BlockCipher128>(cipher: &C, init_counter: &[u8; 16], data: &[u8]) -> Vec<u8> {
    let mut counter = *init_counter;
    let mut out = Vec::with_capacity(data.len());
    let mut idx = 0;
    while idx < data.len() {
        let mut ks = counter;
        cipher.encrypt_block(&mut ks);
        let n = 16.min(data.len() - idx);
        for i in 0..n {
            out.push(data[idx + i] ^ ks[i]);
        }
        idx += n;
        // Increment 128-bit counter, big-endian.
        for i in (0..16).rev() {
            counter[i] = counter[i].wrapping_add(1);
            if counter[i] != 0 {
                break;
            }
        }
    }
    out
}

/// **EAX encrypt** — generic over any 16-byte block cipher.  Returns
/// `ciphertext || tag` where `tag_len ≤ 16`.  Arbitrary `nonce` length
/// is allowed (≥ 1 byte recommended); `header` (associated data) and
/// `plaintext` may be empty.
pub fn eax_encrypt<C: BlockCipher128>(
    cipher: &C,
    nonce: &[u8],
    header: &[u8],
    plaintext: &[u8],
    tag_len: usize,
) -> Vec<u8> {
    assert!(tag_len > 0 && tag_len <= 16, "tag_len must be in 1..=16");
    let n_prime = omac_t(cipher, 0, nonce);
    let h_prime = omac_t(cipher, 1, header);
    let ct = ctr(cipher, &n_prime, plaintext);
    let c_prime = omac_t(cipher, 2, &ct);
    let mut tag = [0u8; 16];
    for i in 0..16 {
        tag[i] = n_prime[i] ^ h_prime[i] ^ c_prime[i];
    }
    let mut out = Vec::with_capacity(ct.len() + tag_len);
    out.extend_from_slice(&ct);
    out.extend_from_slice(&tag[..tag_len]);
    out
}

/// **EAX decrypt + verify**.  Generic over any 16-byte block cipher.
/// Returns `None` on tag mismatch.
pub fn eax_decrypt<C: BlockCipher128>(
    cipher: &C,
    nonce: &[u8],
    header: &[u8],
    ciphertext_with_tag: &[u8],
    tag_len: usize,
) -> Option<Vec<u8>> {
    assert!(tag_len > 0 && tag_len <= 16);
    if ciphertext_with_tag.len() < tag_len {
        return None;
    }
    let ct_len = ciphertext_with_tag.len() - tag_len;
    let ct = &ciphertext_with_tag[..ct_len];
    let recv_tag = &ciphertext_with_tag[ct_len..];
    let n_prime = omac_t(cipher, 0, nonce);
    let h_prime = omac_t(cipher, 1, header);
    let c_prime = omac_t(cipher, 2, ct);
    let mut tag = [0u8; 16];
    for i in 0..16 {
        tag[i] = n_prime[i] ^ h_prime[i] ^ c_prime[i];
    }
    let mut diff = 0u8;
    for i in 0..tag_len {
        diff |= tag[i] ^ recv_tag[i];
    }
    if diff != 0 {
        return None;
    }
    Some(ctr(cipher, &n_prime, ct))
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::symmetric::aes::AesKey;
    use crate::symmetric::camellia::Camellia128;

    fn h(s: &str) -> Vec<u8> {
        let s: String = s.chars().filter(|c| !c.is_whitespace()).collect();
        (0..s.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
            .collect()
    }

    /// **EAX paper test vector #1** (Bellare-Rogaway-Wagner 2004).
    ///
    /// KEY:    233952DEE4D5ED5F9B9C6D6FF80FF478
    /// NONCE:  62EC67F9C3A4A407FCB2A8C49031A8B3
    /// HEADER: 6BFB914FD07EAE6B
    /// MSG:    (empty)
    /// CIPHER: E037830E8389F27B025A2D6527E79D01  (= tag only)
    #[test]
    fn eax_vector_1() {
        let key = AesKey::new(&h("233952DEE4D5ED5F9B9C6D6FF80FF478")).unwrap();
        let nonce = h("62EC67F9C3A4A407FCB2A8C49031A8B3");
        let header = h("6BFB914FD07EAE6B");
        let pt: Vec<u8> = Vec::new();
        let expected = h("E037830E8389F27B025A2D6527E79D01");
        let out = eax_encrypt(&key, &nonce, &header, &pt, 16);
        assert_eq!(out, expected);
        let recovered = eax_decrypt(&key, &nonce, &header, &out, 16).unwrap();
        assert!(recovered.is_empty());
    }

    /// **EAX paper test vector #2**.
    /// KEY:    91945D3F4DCBEE0BF45EF52255F095A4
    /// NONCE:  BECAF043B0A23D843194BA972C66DEBD
    /// HEADER: FA3BFD4806EB53FA
    /// MSG:    F7FB
    /// CIPHER: 19DD5C4C9331049D 0BDAB0277408F67967E5
    #[test]
    fn eax_vector_2() {
        let key = AesKey::new(&h("91945D3F4DCBEE0BF45EF52255F095A4")).unwrap();
        let nonce = h("BECAF043B0A23D843194BA972C66DEBD");
        let header = h("FA3BFD4806EB53FA");
        let pt = h("F7FB");
        let expected = h("19DD 5C4C9331049D 0BDAB0277408F67967E5");
        let out = eax_encrypt(&key, &nonce, &header, &pt, 16);
        assert_eq!(out, expected);
        let recovered = eax_decrypt(&key, &nonce, &header, &out, 16).unwrap();
        assert_eq!(recovered, pt);
    }

    /// **EAX paper test vector #4** — longer plaintext.
    /// KEY:    8395FCF1E95BEBD697BD010BC766AAC3
    /// NONCE:  22E7ADD93CFC6393C57EC0B3C17D6B44
    /// HEADER: 126735FCC320D25A
    /// MSG:    CA40D7446E545FFAED3BD12A740A659FFBBB3CEAB7
    /// CIPHER: CB8920F87A6C75CFF39627B56E3ED197C552D295A7 CFC46AFC253B4652B1AF3795B124AB6E
    #[test]
    fn eax_vector_4() {
        let key = AesKey::new(&h("8395FCF1E95BEBD697BD010BC766AAC3")).unwrap();
        let nonce = h("22E7ADD93CFC6393C57EC0B3C17D6B44");
        let header = h("126735FCC320D25A");
        let pt = h("CA40D7446E545FFAED3BD12A740A659FFBBB3CEAB7");
        let expected = h("CB8920F87A6C75CFF39627B56E3ED197C552D295A7 \
             CFC46AFC253B4652B1AF3795B124AB6E");
        let out = eax_encrypt(&key, &nonce, &header, &pt, 16);
        assert_eq!(out, expected);
        let recovered = eax_decrypt(&key, &nonce, &header, &out, 16).unwrap();
        assert_eq!(recovered, pt);
    }

    /// Tampered ciphertext fails verification.
    #[test]
    fn eax_rejects_tampered_ct() {
        let key = AesKey::new(&[0u8; 16]).unwrap();
        let nonce = b"unique nonce";
        let mut ct = eax_encrypt(&key, nonce, b"aad", b"plaintext", 16);
        ct[3] ^= 1;
        assert!(eax_decrypt(&key, nonce, b"aad", &ct, 16).is_none());
    }

    /// Tampered tag fails verification.
    #[test]
    fn eax_rejects_tampered_tag() {
        let key = AesKey::new(&[1u8; 16]).unwrap();
        let nonce = b"n";
        let mut ct = eax_encrypt(&key, nonce, b"", b"hi", 12);
        let len = ct.len();
        ct[len - 1] ^= 1;
        assert!(eax_decrypt(&key, nonce, b"", &ct, 12).is_none());
    }

    /// Truncated tags work end-to-end.
    #[test]
    fn eax_truncated_tags() {
        let key = AesKey::new(&[7u8; 32]).unwrap();
        let nonce = b"abc";
        let pt = b"hello world";
        for tag_len in [4, 8, 12, 16] {
            let ct = eax_encrypt(&key, nonce, b"aad", pt, tag_len);
            assert_eq!(ct.len(), pt.len() + tag_len);
            let recovered = eax_decrypt(&key, nonce, b"aad", &ct, tag_len).unwrap();
            assert_eq!(recovered, pt);
        }
    }

    /// **EAX over Camellia** — round-trip + tamper.  Proves the
    /// construction is algebraic in the block cipher.
    #[test]
    fn eax_camellia_round_trip_and_tamper() {
        let cipher = Camellia128::new(&[0x42u8; 16]);
        let nonce = b"camellia-eax-nonce";
        let aad = b"associated data";
        let pt = b"non-AES EAX works fine".to_vec();

        let ct = eax_encrypt(&cipher, nonce, aad, &pt, 16);
        let recovered = eax_decrypt(&cipher, nonce, aad, &ct, 16).expect("decrypt");
        assert_eq!(recovered, pt);

        // Tag tamper → reject.
        let mut tampered = ct.clone();
        let last = tampered.len() - 1;
        tampered[last] ^= 1;
        assert!(eax_decrypt(&cipher, nonce, aad, &tampered, 16).is_none());

        // AAD tamper → reject.
        assert!(eax_decrypt(&cipher, nonce, b"other-aad", &ct, 16).is_none());
    }
}
