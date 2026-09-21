//! **AEGIS** authenticated encryption — AEGIS-128L and AEGIS-256.
//!
//! AEGIS (Wu & Preneel, 2014) was a finalist in the CAESAR competition
//! and is standardised by IETF as the high-throughput AEAD primitive
//! built from the AES round function.  It maintains a large internal
//! state (8 × 128 bits for AEGIS-128L, 6 × 128 bits for AEGIS-256) and
//! advances it by applying single-round AES transformations between
//! state words.  On platforms with hardware AES acceleration (AES-NI,
//! ARMv8 crypto extensions) AEGIS reaches several gigabytes per second
//! per core — substantially faster than AES-GCM at the same key length.
//!
//! ## Security note
//!
//! AEGIS has received extensive analysis since 2013 and no attacks
//! significantly better than generic bounds are known.  As with any
//! nonce-based AEAD, reusing a (key, nonce) pair is catastrophic.  This
//! implementation evaluates the AES S-box via constant-time table scan
//! to avoid cache-timing leaks; it is not optimised for throughput.
//!
//! ## Round function
//!
//! AEGIS uses `AESRound(s, k) = MixColumns(ShiftRows(SubBytes(s))) ⊕ k`
//! (one AES round with the XOR-in-key fused after MixColumns; no
//! AddRoundKey at the start).  Implemented locally so the module is
//! self-contained.

use subtle::ConstantTimeEq;

// ── AES round (single round, no key schedule) ───────────────────────────────

#[rustfmt::skip]
const SBOX: [u8; 256] = [
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
];

/// Branchless GF(2⁸) multiply (same shape as `aes.rs::gmul`).
#[inline]
fn gmul(mut a: u8, mut b: u8) -> u8 {
    let mut p = 0u8;
    for _ in 0..8 {
        let bit_mask = 0u8.wrapping_sub(b & 1);
        p ^= a & bit_mask;
        let hi_mask = 0u8.wrapping_sub(a >> 7);
        a = (a << 1) ^ (0x1b & hi_mask);
        b >>= 1;
    }
    p
}

/// Constant-time S-box: scan the whole table on every lookup.
#[inline]
fn sbox_ct(x: u8) -> u8 {
    use subtle::{ConditionallySelectable, ConstantTimeEq};
    let mut result: u8 = 0;
    for i in 0u16..256 {
        let choice = (i as u8).ct_eq(&x);
        result = u8::conditional_select(&result, &SBOX[i as usize], choice);
    }
    result
}

/// Single-round AES transform fused with key XOR:
///   `aes_round(state, key) = MixColumns(ShiftRows(SubBytes(state))) ⊕ key`.
///
/// The 16-byte block is laid out column-major (AES "state" convention):
/// `b[r + 4*c]` is row `r`, column `c`.  ShiftRows shifts row `r` left
/// by `r` positions; MixColumns multiplies each column by the fixed
/// MDS matrix over GF(2⁸).
#[inline]
fn aes_round(state: &[u8; 16], key: &[u8; 16]) -> [u8; 16] {
    // SubBytes.
    let mut s = [0u8; 16];
    for i in 0..16 {
        s[i] = sbox_ct(state[i]);
    }
    // ShiftRows (rows interleaved every 4 bytes; row r is bytes [r, r+4, r+8, r+12]).
    let r0 = [s[0], s[4], s[8], s[12]];
    let r1 = [s[5], s[9], s[13], s[1]];
    let r2 = [s[10], s[14], s[2], s[6]];
    let r3 = [s[15], s[3], s[7], s[11]];
    // MixColumns column-by-column, XOR with key, write out column-major.
    let mut out = [0u8; 16];
    for c in 0..4 {
        let a0 = r0[c];
        let a1 = r1[c];
        let a2 = r2[c];
        let a3 = r3[c];
        out[4 * c] = gmul(0x02, a0) ^ gmul(0x03, a1) ^ a2 ^ a3 ^ key[4 * c];
        out[4 * c + 1] = a0 ^ gmul(0x02, a1) ^ gmul(0x03, a2) ^ a3 ^ key[4 * c + 1];
        out[4 * c + 2] = a0 ^ a1 ^ gmul(0x02, a2) ^ gmul(0x03, a3) ^ key[4 * c + 2];
        out[4 * c + 3] = gmul(0x03, a0) ^ a1 ^ a2 ^ gmul(0x02, a3) ^ key[4 * c + 3];
    }
    out
}

#[inline]
fn xor128(a: &[u8; 16], b: &[u8; 16]) -> [u8; 16] {
    let mut r = [0u8; 16];
    for i in 0..16 {
        r[i] = a[i] ^ b[i];
    }
    r
}

#[inline]
fn and128(a: &[u8; 16], b: &[u8; 16]) -> [u8; 16] {
    let mut r = [0u8; 16];
    for i in 0..16 {
        r[i] = a[i] & b[i];
    }
    r
}

// AEGIS round constants (little-endian byte order as used in the spec).
const C0: [u8; 16] = [
    0x00, 0x01, 0x01, 0x02, 0x03, 0x05, 0x08, 0x0d, 0x15, 0x22, 0x37, 0x59, 0x90, 0xe9, 0x79, 0x62,
];
const C1: [u8; 16] = [
    0xdb, 0x3d, 0x18, 0x55, 0x6d, 0xc2, 0x2f, 0xf1, 0x20, 0x11, 0x31, 0x42, 0x73, 0xb5, 0x28, 0xdd,
];

// ── AEGIS-128L ──────────────────────────────────────────────────────────────

type State128L = [[u8; 16]; 8];

#[inline]
fn update_128l(s: &mut State128L, m0: &[u8; 16], m1: &[u8; 16]) {
    let s7_new = aes_round(&s[6], &s[7]);
    let s6_new = aes_round(&s[5], &s[6]);
    let s5_new = aes_round(&s[4], &s[5]);
    let s4_new = aes_round(&s[3], &xor128(&s[4], m1));
    let s3_new = aes_round(&s[2], &s[3]);
    let s2_new = aes_round(&s[1], &s[2]);
    let s1_new = aes_round(&s[0], &s[1]);
    let s0_new = aes_round(&s[7], &xor128(&s[0], m0));
    s[0] = s0_new;
    s[1] = s1_new;
    s[2] = s2_new;
    s[3] = s3_new;
    s[4] = s4_new;
    s[5] = s5_new;
    s[6] = s6_new;
    s[7] = s7_new;
}

fn init_128l(key: &[u8; 16], nonce: &[u8; 16]) -> State128L {
    let kn = xor128(key, nonce);
    let k_c0 = xor128(key, &C0);
    let k_c1 = xor128(key, &C1);
    let mut s: State128L = [kn, C1, C0, C1, kn, k_c0, k_c1, k_c0];
    for _ in 0..10 {
        update_128l(&mut s, nonce, key);
    }
    s
}

/// Derive the 16-byte keystream block for one update step:
/// `S1 ⊕ S6 ⊕ (S2 AND S3)` for lane 0 and `S2 ⊕ S5 ⊕ (S6 AND S7)` for lane 1.
#[inline]
fn keystream_128l(s: &State128L) -> ([u8; 16], [u8; 16]) {
    let z0 = xor128(&xor128(&s[1], &s[6]), &and128(&s[2], &s[3]));
    let z1 = xor128(&xor128(&s[2], &s[5]), &and128(&s[6], &s[7]));
    (z0, z1)
}

fn absorb_aad_128l(s: &mut State128L, aad: &[u8]) {
    let mut chunks = aad.chunks_exact(32);
    for blk in &mut chunks {
        let m0: [u8; 16] = blk[0..16].try_into().unwrap();
        let m1: [u8; 16] = blk[16..32].try_into().unwrap();
        update_128l(s, &m0, &m1);
    }
    let rem = chunks.remainder();
    if !rem.is_empty() {
        let mut pad = [0u8; 32];
        pad[..rem.len()].copy_from_slice(rem);
        let m0: [u8; 16] = pad[0..16].try_into().unwrap();
        let m1: [u8; 16] = pad[16..32].try_into().unwrap();
        update_128l(s, &m0, &m1);
    }
}

fn encrypt_stream_128l(s: &mut State128L, pt: &[u8], out: &mut Vec<u8>) {
    let mut chunks = pt.chunks_exact(32);
    for blk in &mut chunks {
        let m0: [u8; 16] = blk[0..16].try_into().unwrap();
        let m1: [u8; 16] = blk[16..32].try_into().unwrap();
        let (z0, z1) = keystream_128l(s);
        out.extend_from_slice(&xor128(&m0, &z0));
        out.extend_from_slice(&xor128(&m1, &z1));
        update_128l(s, &m0, &m1);
    }
    let rem = chunks.remainder();
    if !rem.is_empty() {
        let mut pad = [0u8; 32];
        pad[..rem.len()].copy_from_slice(rem);
        let m0: [u8; 16] = pad[0..16].try_into().unwrap();
        let m1: [u8; 16] = pad[16..32].try_into().unwrap();
        let (z0, z1) = keystream_128l(s);
        let mut block = [0u8; 32];
        block[0..16].copy_from_slice(&xor128(&m0, &z0));
        block[16..32].copy_from_slice(&xor128(&m1, &z1));
        out.extend_from_slice(&block[..rem.len()]);
        update_128l(s, &m0, &m1);
    }
}

fn decrypt_stream_128l(s: &mut State128L, ct: &[u8], out: &mut Vec<u8>) {
    let mut chunks = ct.chunks_exact(32);
    for blk in &mut chunks {
        let c0: [u8; 16] = blk[0..16].try_into().unwrap();
        let c1: [u8; 16] = blk[16..32].try_into().unwrap();
        let (z0, z1) = keystream_128l(s);
        let m0 = xor128(&c0, &z0);
        let m1 = xor128(&c1, &z1);
        out.extend_from_slice(&m0);
        out.extend_from_slice(&m1);
        update_128l(s, &m0, &m1);
    }
    let rem = chunks.remainder();
    if !rem.is_empty() {
        // Pad ciphertext with zeros, decrypt, then zero the tail of the
        // recovered plaintext before re-absorbing (spec §2.6.3).
        let mut padded_c = [0u8; 32];
        padded_c[..rem.len()].copy_from_slice(rem);
        let c0: [u8; 16] = padded_c[0..16].try_into().unwrap();
        let c1: [u8; 16] = padded_c[16..32].try_into().unwrap();
        let (z0, z1) = keystream_128l(s);
        let mut m_full = [0u8; 32];
        m_full[0..16].copy_from_slice(&xor128(&c0, &z0));
        m_full[16..32].copy_from_slice(&xor128(&c1, &z1));
        out.extend_from_slice(&m_full[..rem.len()]);
        // Zero the bytes beyond the message length, then update with the
        // sanitised plaintext block.
        for i in rem.len()..32 {
            m_full[i] = 0;
        }
        let m0: [u8; 16] = m_full[0..16].try_into().unwrap();
        let m1: [u8; 16] = m_full[16..32].try_into().unwrap();
        update_128l(s, &m0, &m1);
    }
}

fn finalize_128l(s: &mut State128L, ad_len_bits: u64, msg_len_bits: u64) -> [u8; 16] {
    let mut tmp = [0u8; 16];
    tmp[0..8].copy_from_slice(&ad_len_bits.to_le_bytes());
    tmp[8..16].copy_from_slice(&msg_len_bits.to_le_bytes());
    let t = xor128(&tmp, &s[2]);
    for _ in 0..7 {
        update_128l(s, &t, &t);
    }
    let mut tag = s[0];
    for i in 1..7 {
        tag = xor128(&tag, &s[i]);
    }
    tag
}

/// **AEGIS-128L encrypt** — 128-bit key, 128-bit nonce, 16-byte tag.
/// Returns `ciphertext || tag`.
pub fn aegis128l_encrypt(
    key: &[u8; 16],
    nonce: &[u8; 16],
    aad: &[u8],
    plaintext: &[u8],
) -> Vec<u8> {
    let mut s = init_128l(key, nonce);
    absorb_aad_128l(&mut s, aad);
    let mut out = Vec::with_capacity(plaintext.len() + 16);
    encrypt_stream_128l(&mut s, plaintext, &mut out);
    let tag = finalize_128l(&mut s, (aad.len() as u64) * 8, (plaintext.len() as u64) * 8);
    out.extend_from_slice(&tag);
    out
}

/// **AEGIS-128L decrypt + verify**.  Returns `Some(plaintext)` iff the tag
/// matches.
pub fn aegis128l_decrypt(
    key: &[u8; 16],
    nonce: &[u8; 16],
    aad: &[u8],
    ciphertext_with_tag: &[u8],
) -> Option<Vec<u8>> {
    if ciphertext_with_tag.len() < 16 {
        return None;
    }
    let (ct, tag_bytes) = ciphertext_with_tag.split_at(ciphertext_with_tag.len() - 16);
    let mut s = init_128l(key, nonce);
    absorb_aad_128l(&mut s, aad);
    let mut out = Vec::with_capacity(ct.len());
    decrypt_stream_128l(&mut s, ct, &mut out);
    let expected = finalize_128l(&mut s, (aad.len() as u64) * 8, (ct.len() as u64) * 8);
    if expected.ct_eq(tag_bytes).unwrap_u8() != 1 {
        return None;
    }
    Some(out)
}

// ── AEGIS-256 ───────────────────────────────────────────────────────────────

type State256 = [[u8; 16]; 6];

#[inline]
fn update_256(s: &mut State256, m: &[u8; 16]) {
    let s5_new = aes_round(&s[4], &s[5]);
    let s4_new = aes_round(&s[3], &s[4]);
    let s3_new = aes_round(&s[2], &s[3]);
    let s2_new = aes_round(&s[1], &s[2]);
    let s1_new = aes_round(&s[0], &s[1]);
    let s0_new = aes_round(&s[5], &xor128(&s[0], m));
    s[0] = s0_new;
    s[1] = s1_new;
    s[2] = s2_new;
    s[3] = s3_new;
    s[4] = s4_new;
    s[5] = s5_new;
}

fn init_256(key: &[u8; 32], nonce: &[u8; 32]) -> State256 {
    let k0: [u8; 16] = key[0..16].try_into().unwrap();
    let k1: [u8; 16] = key[16..32].try_into().unwrap();
    let n0: [u8; 16] = nonce[0..16].try_into().unwrap();
    let n1: [u8; 16] = nonce[16..32].try_into().unwrap();
    let k0n0 = xor128(&k0, &n0);
    let k1n1 = xor128(&k1, &n1);
    let mut s: State256 = [k0n0, k1n1, C1, C0, xor128(&k0, &C0), xor128(&k1, &C1)];
    for _ in 0..4 {
        update_256(&mut s, &k0);
        update_256(&mut s, &k1);
        update_256(&mut s, &k0n0);
        update_256(&mut s, &k1n1);
    }
    s
}

/// Keystream block for AEGIS-256: `S1 ⊕ S4 ⊕ S5 ⊕ (S2 AND S3)`.
#[inline]
fn keystream_256(s: &State256) -> [u8; 16] {
    let a = xor128(&s[1], &s[4]);
    let b = xor128(&a, &s[5]);
    xor128(&b, &and128(&s[2], &s[3]))
}

fn absorb_aad_256(s: &mut State256, aad: &[u8]) {
    let mut chunks = aad.chunks_exact(16);
    for blk in &mut chunks {
        let m: [u8; 16] = blk.try_into().unwrap();
        update_256(s, &m);
    }
    let rem = chunks.remainder();
    if !rem.is_empty() {
        let mut pad = [0u8; 16];
        pad[..rem.len()].copy_from_slice(rem);
        update_256(s, &pad);
    }
}

fn encrypt_stream_256(s: &mut State256, pt: &[u8], out: &mut Vec<u8>) {
    let mut chunks = pt.chunks_exact(16);
    for blk in &mut chunks {
        let m: [u8; 16] = blk.try_into().unwrap();
        let z = keystream_256(s);
        out.extend_from_slice(&xor128(&m, &z));
        update_256(s, &m);
    }
    let rem = chunks.remainder();
    if !rem.is_empty() {
        let mut pad = [0u8; 16];
        pad[..rem.len()].copy_from_slice(rem);
        let z = keystream_256(s);
        let c = xor128(&pad, &z);
        out.extend_from_slice(&c[..rem.len()]);
        update_256(s, &pad);
    }
}

fn decrypt_stream_256(s: &mut State256, ct: &[u8], out: &mut Vec<u8>) {
    let mut chunks = ct.chunks_exact(16);
    for blk in &mut chunks {
        let c: [u8; 16] = blk.try_into().unwrap();
        let z = keystream_256(s);
        let m = xor128(&c, &z);
        out.extend_from_slice(&m);
        update_256(s, &m);
    }
    let rem = chunks.remainder();
    if !rem.is_empty() {
        let mut padded_c = [0u8; 16];
        padded_c[..rem.len()].copy_from_slice(rem);
        let z = keystream_256(s);
        let mut m_full = xor128(&padded_c, &z);
        out.extend_from_slice(&m_full[..rem.len()]);
        for i in rem.len()..16 {
            m_full[i] = 0;
        }
        update_256(s, &m_full);
    }
}

fn finalize_256(s: &mut State256, ad_len_bits: u64, msg_len_bits: u64) -> [u8; 16] {
    let mut tmp = [0u8; 16];
    tmp[0..8].copy_from_slice(&ad_len_bits.to_le_bytes());
    tmp[8..16].copy_from_slice(&msg_len_bits.to_le_bytes());
    let t = xor128(&tmp, &s[3]);
    for _ in 0..7 {
        update_256(s, &t);
    }
    let mut tag = s[0];
    for i in 1..6 {
        tag = xor128(&tag, &s[i]);
    }
    tag
}

/// **AEGIS-256 encrypt** — 256-bit key, 256-bit nonce, 16-byte tag.
/// Returns `ciphertext || tag`.
pub fn aegis256_encrypt(key: &[u8; 32], nonce: &[u8; 32], aad: &[u8], plaintext: &[u8]) -> Vec<u8> {
    let mut s = init_256(key, nonce);
    absorb_aad_256(&mut s, aad);
    let mut out = Vec::with_capacity(plaintext.len() + 16);
    encrypt_stream_256(&mut s, plaintext, &mut out);
    let tag = finalize_256(&mut s, (aad.len() as u64) * 8, (plaintext.len() as u64) * 8);
    out.extend_from_slice(&tag);
    out
}

/// **AEGIS-256 decrypt + verify**.
pub fn aegis256_decrypt(
    key: &[u8; 32],
    nonce: &[u8; 32],
    aad: &[u8],
    ciphertext_with_tag: &[u8],
) -> Option<Vec<u8>> {
    if ciphertext_with_tag.len() < 16 {
        return None;
    }
    let (ct, tag_bytes) = ciphertext_with_tag.split_at(ciphertext_with_tag.len() - 16);
    let mut s = init_256(key, nonce);
    absorb_aad_256(&mut s, aad);
    let mut out = Vec::with_capacity(ct.len());
    decrypt_stream_256(&mut s, ct, &mut out);
    let expected = finalize_256(&mut s, (aad.len() as u64) * 8, (ct.len() as u64) * 8);
    if expected.ct_eq(tag_bytes).unwrap_u8() != 1 {
        return None;
    }
    Some(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn h(s: &str) -> Vec<u8> {
        hex::decode(s).unwrap()
    }

    fn k16(s: &str) -> [u8; 16] {
        h(s).try_into().unwrap()
    }

    fn k32(s: &str) -> [u8; 32] {
        h(s).try_into().unwrap()
    }

    // ── AEGIS-128L KATs ────────────────────────────────────────────────────

    /// IETF AEGIS draft test vector: `KEY=10 01 00…`, `NONCE=10 00 02 00…`,
    /// 16-byte zero plaintext, no AAD.
    #[test]
    fn aegis128l_spec_vector() {
        let key = k16("10010000000000000000000000000000");
        let nonce = k16("10000200000000000000000000000000");
        let pt = h("00000000000000000000000000000000");
        let ct = aegis128l_encrypt(&key, &nonce, b"", &pt);
        assert_eq!(
            ct,
            h("c1c0e58bd913006feba00f4b3cc3594eabe0ece80c24868a226a35d16bdae37a")
        );
        let pt2 = aegis128l_decrypt(&key, &nonce, b"", &ct).expect("tag verifies");
        assert_eq!(pt2, pt);
    }

    /// pyaegis cross-check: empty AAD and empty plaintext.
    #[test]
    fn aegis128l_empty() {
        let key = k16("000102030405060708090a0b0c0d0e0f");
        let nonce = k16("000102030405060708090a0b0c0d0e0f");
        let ct = aegis128l_encrypt(&key, &nonce, b"", b"");
        assert_eq!(ct, h("c3f43996b947d95391c1e453e9a7b8f3"));
        assert!(aegis128l_decrypt(&key, &nonce, b"", &ct)
            .unwrap()
            .is_empty());
    }

    /// pyaegis cross-check: 16-byte AAD + 32-byte plaintext (two state blocks).
    #[test]
    fn aegis128l_aad_and_multi_block() {
        let key = k16("000102030405060708090a0b0c0d0e0f");
        let nonce = k16("000102030405060708090a0b0c0d0e0f");
        let aad = h("000102030405060708090a0b0c0d0e0f");
        let pt = h("101112131415161718191a1b1c1d1e1f202122232425262728292a2b2c2d2e2f");
        let ct = aegis128l_encrypt(&key, &nonce, &aad, &pt);
        assert_eq!(
            ct,
            h(
                "1d5b2ecb7f8c45dbe9b67a923e70500b37566ee1d458687249617258a6bb22eb\
               41881e8230c745b2345fac5155faa240"
            )
        );
        let pt2 = aegis128l_decrypt(&key, &nonce, &aad, &ct).expect("tag verifies");
        assert_eq!(pt2, pt);
    }

    /// pyaegis cross-check: 7-byte plaintext (sub-block) with empty AAD.
    #[test]
    fn aegis128l_partial_block() {
        let key = k16("000102030405060708090a0b0c0d0e0f");
        let nonce = k16("000102030405060708090a0b0c0d0e0f");
        let ct = aegis128l_encrypt(&key, &nonce, b"", b"7 bytes");
        assert_eq!(ct, h("782fcf4f48e5615cc952389f3273bec14936b969a029d0"));
        let pt = aegis128l_decrypt(&key, &nonce, b"", &ct).unwrap();
        assert_eq!(pt, b"7 bytes");
    }

    // ── AEGIS-256 KATs ─────────────────────────────────────────────────────

    /// pyaegis cross-check: empty AAD and empty plaintext.
    #[test]
    fn aegis256_empty() {
        let key = k32("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f");
        let nonce = k32("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f");
        let ct = aegis256_encrypt(&key, &nonce, b"", b"");
        assert_eq!(ct, h("cdbc212011c11a3650b2cd3e6c8b0282"));
        assert!(aegis256_decrypt(&key, &nonce, b"", &ct).unwrap().is_empty());
    }

    /// pyaegis cross-check: 16-byte AAD + 32-byte plaintext (two state blocks).
    #[test]
    fn aegis256_aad_and_multi_block() {
        let key = k32("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f");
        let nonce = k32("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f");
        let aad = h("000102030405060708090a0b0c0d0e0f");
        let pt = h("101112131415161718191a1b1c1d1e1f202122232425262728292a2b2c2d2e2f");
        let ct = aegis256_encrypt(&key, &nonce, &aad, &pt);
        assert_eq!(
            ct,
            h(
                "3af6da22c6231f0bd4740df43a5668166287a3eaa983aa83021530922aa33efd\
               b16be5c34b6032881e50325c28ed34de"
            )
        );
        let pt2 = aegis256_decrypt(&key, &nonce, &aad, &ct).expect("tag verifies");
        assert_eq!(pt2, pt);
    }

    /// pyaegis cross-check: longer ASCII plaintext + AAD.
    #[test]
    fn aegis256_longer_message() {
        let key = k32("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f");
        let nonce = k32("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f");
        let pt = b"Hello, AEGIS-256! This is a longer test.";
        let ct = aegis256_encrypt(&key, &nonce, b"associated", pt);
        assert_eq!(
            ct,
            h(
                "6282a45dbd1a295d892a5ebc0b79433f3407d6a738aed16bf5f95afa6c824033\
               f74b0d77adc2c7848dc1d35a9fe6dba0888445b2bea6eaf3"
            )
        );
        let recovered = aegis256_decrypt(&key, &nonce, b"associated", &ct).unwrap();
        assert_eq!(recovered, pt);
    }

    // ── Round-trip & negative tests ────────────────────────────────────────

    #[test]
    fn aegis128l_roundtrip_random_lengths() {
        let key = [0x42u8; 16];
        let nonce = [0x07u8; 16];
        for len in [0usize, 1, 15, 16, 17, 31, 32, 33, 63, 64, 65, 200] {
            let pt: Vec<u8> = (0..len).map(|i| (i as u8).wrapping_mul(31)).collect();
            let aad: Vec<u8> = (0..(len % 23))
                .map(|i| (i as u8).wrapping_mul(17))
                .collect();
            let ct = aegis128l_encrypt(&key, &nonce, &aad, &pt);
            assert_eq!(ct.len(), pt.len() + 16);
            let dec = aegis128l_decrypt(&key, &nonce, &aad, &ct).expect("roundtrip");
            assert_eq!(dec, pt, "len={}", len);
        }
    }

    #[test]
    fn aegis256_roundtrip_random_lengths() {
        let key = [0x42u8; 32];
        let nonce = [0x07u8; 32];
        for len in [0usize, 1, 15, 16, 17, 31, 32, 33, 63, 64, 65, 200] {
            let pt: Vec<u8> = (0..len).map(|i| (i as u8).wrapping_mul(31)).collect();
            let aad: Vec<u8> = (0..(len % 23))
                .map(|i| (i as u8).wrapping_mul(17))
                .collect();
            let ct = aegis256_encrypt(&key, &nonce, &aad, &pt);
            assert_eq!(ct.len(), pt.len() + 16);
            let dec = aegis256_decrypt(&key, &nonce, &aad, &ct).expect("roundtrip");
            assert_eq!(dec, pt, "len={}", len);
        }
    }

    #[test]
    fn aegis128l_tamper_fails() {
        let key = [0x42u8; 16];
        let nonce = [0u8; 16];
        let ct = aegis128l_encrypt(&key, &nonce, b"aad", b"secret payload");
        // CT tamper.
        let mut t = ct.clone();
        t[0] ^= 1;
        assert!(aegis128l_decrypt(&key, &nonce, b"aad", &t).is_none());
        // Tag tamper.
        let mut t = ct.clone();
        let last = t.len() - 1;
        t[last] ^= 1;
        assert!(aegis128l_decrypt(&key, &nonce, b"aad", &t).is_none());
        // AAD tamper.
        assert!(aegis128l_decrypt(&key, &nonce, b"AAD", &ct).is_none());
    }

    #[test]
    fn aegis256_tamper_fails() {
        let key = [0x42u8; 32];
        let nonce = [0u8; 32];
        let ct = aegis256_encrypt(&key, &nonce, b"aad", b"secret payload");
        let mut t = ct.clone();
        t[0] ^= 1;
        assert!(aegis256_decrypt(&key, &nonce, b"aad", &t).is_none());
        let mut t = ct.clone();
        let last = t.len() - 1;
        t[last] ^= 1;
        assert!(aegis256_decrypt(&key, &nonce, b"aad", &t).is_none());
        assert!(aegis256_decrypt(&key, &nonce, b"AAD", &ct).is_none());
    }

    #[test]
    fn aegis_short_input_fails() {
        assert!(aegis128l_decrypt(&[0u8; 16], &[0u8; 16], b"", &[0u8; 8]).is_none());
        assert!(aegis256_decrypt(&[0u8; 32], &[0u8; 32], b"", &[0u8; 8]).is_none());
    }
}
