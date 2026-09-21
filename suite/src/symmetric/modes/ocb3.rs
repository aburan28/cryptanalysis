//! **OCB3** — Offset Codebook Mode v3 (RFC 7253).
//!
//! Single-pass, parallelisable AEAD with a clean security proof and
//! strong empirical performance.  Was patent-encumbered for many
//! years; the patents have all expired and OCB3 is now standardised
//! in RFC 7253.
//!
//! ## Construction
//!
//! Given AES key `K`:
//!
//! ```text
//!     L_* = E_K(0^128)
//!     L_$ = double(L_*)
//!     L_0 = double(L_$)
//!     L_i = double(L_{i-1})    for i ≥ 1
//! ```
//!
//! where `double(X)` in GF(2^128) with reduction `x^128 + x^7 + x^2 + x + 1`.
//!
//! Nonce processing (we restrict to a 12-byte nonce and 16-byte tag —
//! the simplest profile per RFC 7253 §4.2):
//!
//! ```text
//!     Nonce = 00 || 00 || 00 || 01 || N₁..N₁₂     (16 bytes)
//!     top    = Nonce with bottom 6 bits cleared
//!     bottom = bottom 6 bits of Nonce[15]
//!     Ktop = E_K(top)
//!     Stretch = Ktop || (Ktop[0..8] ⊕ Ktop[1..9])     (24 bytes)
//!     Offset_0 = Stretch[bottom .. bottom + 128]      (bit-aligned)
//! ```
//!
//! Encrypt:
//!
//! ```text
//!     Offset = Offset_0
//!     Checksum = 0
//!     for i = 1..m (full plaintext blocks):
//!         Offset = Offset ⊕ L_{ntz(i)}
//!         C_i    = E_K(P_i ⊕ Offset) ⊕ Offset
//!         Checksum ⊕= P_i
//!     if P_* (partial last block):
//!         Offset_*  = Offset ⊕ L_*
//!         Pad        = E_K(Offset_*)
//!         C_*        = P_* ⊕ Pad[..|P_*|]
//!         Checksum  ⊕= (P_* || 1 || 0…)
//!     Auth   = HASH_K(A)      (similar offset chain, see HASH)
//!     Tag    = E_K(Checksum ⊕ Offset ⊕ L_$) ⊕ Auth
//! ```
//!
//! ## References
//!
//! - **T. Krovetz, P. Rogaway**, *The Software Performance of
//!   Authenticated-Encryption Modes*, FSE 2011.
//! - **RFC 7253** — The OCB Authenticated-Encryption Algorithm.

use crate::symmetric::aes::{decrypt_block, encrypt_block, AesKey};

const BLOCK: usize = 16;

/// `double(X)` in GF(2^128) with reduction `x^128 + x^7 + x^2 + x + 1`.
/// Big-endian byte convention (same as CMAC's `dbl`).
fn double(x: &[u8; 16]) -> [u8; 16] {
    let mut out = [0u8; 16];
    let mut carry = 0u8;
    for i in (0..16).rev() {
        let new_carry = x[i] >> 7;
        out[i] = (x[i] << 1) | carry;
        carry = new_carry;
    }
    if (x[0] >> 7) & 1 == 1 {
        out[15] ^= 0x87;
    }
    out
}

fn xor16(a: &[u8; 16], b: &[u8; 16]) -> [u8; 16] {
    let mut out = [0u8; 16];
    for i in 0..16 {
        out[i] = a[i] ^ b[i];
    }
    out
}

fn xor16_in_place(a: &mut [u8; 16], b: &[u8; 16]) {
    for i in 0..16 {
        a[i] ^= b[i];
    }
}

/// Compute `Stretch[bottom .. bottom + 128]` as a 16-byte bit-aligned
/// slice of the 24-byte `stretch` buffer.  Bits are big-endian
/// (bit 0 of `stretch` is the MSB of `stretch[0]`).
fn bit_slice(stretch: &[u8; 24], bottom: u32) -> [u8; 16] {
    let mut out = [0u8; 16];
    let byte_off = (bottom / 8) as usize;
    let bit_off = bottom % 8;
    if bit_off == 0 {
        out.copy_from_slice(&stretch[byte_off..byte_off + 16]);
    } else {
        for i in 0..16 {
            let hi = stretch[byte_off + i];
            let lo = stretch[byte_off + i + 1];
            out[i] = (hi << bit_off) | (lo >> (8 - bit_off));
        }
    }
    out
}

/// Precompute `(L_*, L_$, L_0, L_1, …, L_max)` for up to `2^max_log`
/// blocks total.
fn compute_l_table(key: &AesKey, max_log: usize) -> (Vec<[u8; 16]>, [u8; 16], [u8; 16]) {
    let l_star = encrypt_block(&[0u8; 16], key);
    let l_dollar = double(&l_star);
    let mut l_table = Vec::with_capacity(max_log + 1);
    let mut cur = double(&l_dollar);
    l_table.push(cur);
    for _ in 1..=max_log {
        cur = double(&cur);
        l_table.push(cur);
    }
    (l_table, l_star, l_dollar)
}

/// Number of trailing zero bits in `n`.  `ntz(0)` is undefined per
/// RFC 7253; we only call this for `n ≥ 1`.
fn ntz(n: u64) -> u32 {
    debug_assert!(n != 0);
    n.trailing_zeros()
}

fn l_table_max_log(data_len: usize, aad_len: usize) -> usize {
    let blocks = data_len / BLOCK + aad_len / BLOCK + 2;
    let ceil_logish = usize::BITS as usize - blocks.max(1).leading_zeros() as usize;
    ceil_logish + 4
}

fn nonce_to_offset0(key: &AesKey, nonce: &[u8; 12]) -> [u8; 16] {
    // Nonce: 00 || 00 || 00 || 01 || N12.
    let mut full_nonce = [0u8; 16];
    full_nonce[3] = 0x01;
    full_nonce[4..16].copy_from_slice(nonce);
    let bottom = (full_nonce[15] & 0x3F) as u32;
    let mut top = full_nonce;
    top[15] &= 0xC0;
    let ktop = encrypt_block(&top, key);
    let mut stretch = [0u8; 24];
    stretch[0..16].copy_from_slice(&ktop);
    for i in 0..8 {
        stretch[16 + i] = ktop[i] ^ ktop[i + 1];
    }
    bit_slice(&stretch, bottom)
}

/// **HASH(A)** — POLY1305-style accumulator over the AAD using the
/// L-offset chain.  Returns the 128-bit Auth value.
fn hash_aad(key: &AesKey, aad: &[u8], l_table: &[[u8; 16]], l_star: &[u8; 16]) -> [u8; 16] {
    let m = aad.len() / BLOCK;
    let rem = aad.len() % BLOCK;
    let mut sum = [0u8; 16];
    let mut offset = [0u8; 16];
    for i in 1..=m {
        xor16_in_place(&mut offset, &l_table[ntz(i as u64) as usize]);
        let mut blk = [0u8; 16];
        blk.copy_from_slice(&aad[(i - 1) * BLOCK..i * BLOCK]);
        let inp = xor16(&blk, &offset);
        let enc = encrypt_block(&inp, key);
        xor16_in_place(&mut sum, &enc);
    }
    if rem > 0 {
        xor16_in_place(&mut offset, l_star);
        let mut pad = [0u8; 16];
        pad[..rem].copy_from_slice(&aad[m * BLOCK..]);
        pad[rem] = 0x80;
        let inp = xor16(&pad, &offset);
        let enc = encrypt_block(&inp, key);
        xor16_in_place(&mut sum, &enc);
    }
    sum
}

/// **OCB3 encrypt** with 12-byte nonce, 16-byte tag.  Returns
/// `ciphertext || tag`.
pub fn ocb3_encrypt(key: &AesKey, nonce: &[u8; 12], aad: &[u8], plaintext: &[u8]) -> Vec<u8> {
    let max_log = l_table_max_log(plaintext.len(), aad.len());
    let (l_table, l_star, l_dollar) = compute_l_table(key, max_log.max(1));
    let mut offset = nonce_to_offset0(key, nonce);
    let mut checksum = [0u8; 16];
    let mut ct = Vec::with_capacity(plaintext.len() + 16);
    let m = plaintext.len() / BLOCK;
    let rem = plaintext.len() % BLOCK;
    for i in 1..=m {
        xor16_in_place(&mut offset, &l_table[ntz(i as u64) as usize]);
        let mut p_i = [0u8; 16];
        p_i.copy_from_slice(&plaintext[(i - 1) * BLOCK..i * BLOCK]);
        let inp = xor16(&p_i, &offset);
        let enc = encrypt_block(&inp, key);
        let c_i = xor16(&enc, &offset);
        ct.extend_from_slice(&c_i);
        xor16_in_place(&mut checksum, &p_i);
    }
    if rem > 0 {
        let offset_star = xor16(&offset, &l_star);
        let pad = encrypt_block(&offset_star, key);
        let p_star = &plaintext[m * BLOCK..];
        let mut c_star = vec![0u8; rem];
        for i in 0..rem {
            c_star[i] = p_star[i] ^ pad[i];
        }
        ct.extend_from_slice(&c_star);
        let mut checksum_input = [0u8; 16];
        checksum_input[..rem].copy_from_slice(p_star);
        checksum_input[rem] = 0x80;
        xor16_in_place(&mut checksum, &checksum_input);
    }
    let auth = hash_aad(key, aad, &l_table, &l_star);
    let tag_input = xor16(&xor16(&checksum, &offset), &l_dollar);
    let tag_enc = encrypt_block(&tag_input, key);
    let tag = xor16(&tag_enc, &auth);
    ct.extend_from_slice(&tag);
    ct
}

/// **OCB3 decrypt + verify** with 12-byte nonce, 16-byte tag.
pub fn ocb3_decrypt(
    key: &AesKey,
    nonce: &[u8; 12],
    aad: &[u8],
    ciphertext_with_tag: &[u8],
) -> Option<Vec<u8>> {
    if ciphertext_with_tag.len() < 16 {
        return None;
    }
    let ct_len = ciphertext_with_tag.len() - 16;
    let ct = &ciphertext_with_tag[..ct_len];
    let mut recv_tag = [0u8; 16];
    recv_tag.copy_from_slice(&ciphertext_with_tag[ct_len..]);
    let max_log = l_table_max_log(ct_len, aad.len());
    let (l_table, l_star, l_dollar) = compute_l_table(key, max_log.max(1));
    let mut offset = nonce_to_offset0(key, nonce);
    let mut checksum = [0u8; 16];
    let mut pt = Vec::with_capacity(ct_len);
    let m = ct_len / BLOCK;
    let rem = ct_len % BLOCK;
    for i in 1..=m {
        xor16_in_place(&mut offset, &l_table[ntz(i as u64) as usize]);
        let mut c_i = [0u8; 16];
        c_i.copy_from_slice(&ct[(i - 1) * BLOCK..i * BLOCK]);
        let inp = xor16(&c_i, &offset);
        let dec = decrypt_block(&inp, key);
        let p_i = xor16(&dec, &offset);
        pt.extend_from_slice(&p_i);
        xor16_in_place(&mut checksum, &p_i);
    }
    if rem > 0 {
        let offset_star = xor16(&offset, &l_star);
        let pad = encrypt_block(&offset_star, key);
        let c_star = &ct[m * BLOCK..];
        let mut p_star = vec![0u8; rem];
        for i in 0..rem {
            p_star[i] = c_star[i] ^ pad[i];
        }
        pt.extend_from_slice(&p_star);
        let mut checksum_input = [0u8; 16];
        checksum_input[..rem].copy_from_slice(&p_star);
        checksum_input[rem] = 0x80;
        xor16_in_place(&mut checksum, &checksum_input);
    }
    let auth = hash_aad(key, aad, &l_table, &l_star);
    let tag_input = xor16(&xor16(&checksum, &offset), &l_dollar);
    let tag_enc = encrypt_block(&tag_input, key);
    let expected_tag = xor16(&tag_enc, &auth);
    let mut diff = 0u8;
    for i in 0..16 {
        diff |= expected_tag[i] ^ recv_tag[i];
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

    fn h(s: &str) -> Vec<u8> {
        let s: String = s.chars().filter(|c| !c.is_whitespace()).collect();
        (0..s.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
            .collect()
    }

    /// **RFC 7253 Appendix A** test vector — empty plaintext, empty AAD.
    /// Key:    000102030405060708090A0B0C0D0E0F
    /// Nonce:  BBAA99887766554433221100
    /// Tag:    785407BFFFC8AD9EDCC5520AC9111EE6
    #[test]
    fn ocb3_rfc7253_empty() {
        let key = AesKey::new(&h("000102030405060708090A0B0C0D0E0F")).unwrap();
        let nonce_v = h("BBAA99887766554433221100");
        let mut nonce = [0u8; 12];
        nonce.copy_from_slice(&nonce_v);
        let expected = h("785407BFFFC8AD9EDCC5520AC9111EE6");
        let out = ocb3_encrypt(&key, &nonce, b"", b"");
        assert_eq!(out, expected);
        let recovered = ocb3_decrypt(&key, &nonce, b"", &out).unwrap();
        assert!(recovered.is_empty());
    }

    /// Round-trip with arbitrary plaintext and AAD.
    #[test]
    fn ocb3_round_trip() {
        let key = AesKey::new(&[0x42u8; 16]).unwrap();
        let nonce = [0x99u8; 12];
        let aad = b"associated data, possibly long, here it's about this long";
        let pt = b"plaintext goes here and may span multiple AES blocks";
        let ct = ocb3_encrypt(&key, &nonce, aad, pt);
        let recovered = ocb3_decrypt(&key, &nonce, aad, &ct).unwrap();
        assert_eq!(recovered, pt);
    }

    /// Tampered ciphertext fails verification.
    #[test]
    fn ocb3_rejects_tampered_ct() {
        let key = AesKey::new(&[0u8; 16]).unwrap();
        let nonce = [1u8; 12];
        let mut ct = ocb3_encrypt(&key, &nonce, b"", b"plaintext");
        ct[3] ^= 1;
        assert!(ocb3_decrypt(&key, &nonce, b"", &ct).is_none());
    }

    /// Tampered tag fails verification.
    #[test]
    fn ocb3_rejects_tampered_tag() {
        let key = AesKey::new(&[2u8; 16]).unwrap();
        let nonce = [3u8; 12];
        let mut ct = ocb3_encrypt(&key, &nonce, b"", b"pt");
        let len = ct.len();
        ct[len - 1] ^= 1;
        assert!(ocb3_decrypt(&key, &nonce, b"", &ct).is_none());
    }

    /// Multiple-AES-block plaintext stress-tests the L-table chain.
    #[test]
    fn ocb3_many_blocks() {
        let key = AesKey::new(&[5u8; 16]).unwrap();
        let nonce = [0u8; 12];
        let pt: Vec<u8> = (0..16 * 17).map(|i| i as u8).collect(); // 17 full blocks
        let ct = ocb3_encrypt(&key, &nonce, b"", &pt);
        let recovered = ocb3_decrypt(&key, &nonce, b"", &ct).unwrap();
        assert_eq!(recovered, pt);
    }

    #[test]
    fn ocb3_l_table_sizing_uses_integer_math() {
        assert!(l_table_max_log(0, 0) >= 1);
        assert!(l_table_max_log(16 * 17, 0) >= ntz(17) as usize);
    }

    /// Partial last block (forces L_* / 0x80-pad branch).
    #[test]
    fn ocb3_partial_last_block() {
        let key = AesKey::new(&[7u8; 16]).unwrap();
        let nonce = [0u8; 12];
        for len in [1usize, 5, 15, 17, 31, 33, 47] {
            let pt: Vec<u8> = (0..len).map(|i| (i * 7) as u8).collect();
            let ct = ocb3_encrypt(&key, &nonce, b"aad", &pt);
            let recovered = ocb3_decrypt(&key, &nonce, b"aad", &ct).unwrap();
            assert_eq!(recovered, pt, "fail at len={}", len);
        }
    }
}
