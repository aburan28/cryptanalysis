//! **ARIA** — 128-bit block cipher, Korean national standard
//! (KS X 1213, 2004), specified in **RFC 5794** (2010).  Designed by
//! a team of Korean cryptographers led by D. Kwon at NSRI.
//!
//! ## Structure
//!
//! - 128-bit block, 128/192/256-bit keys, **12/14/16 rounds**
//!   respectively.
//! - SPN with two distinct S-box layers `SL_1` (S-boxes `S1, S2,
//!   S1^{-1}, S2^{-1}` × 4) and `SL_2` (`S1^{-1}, S2^{-1}, S1, S2`
//!   × 4) used in alternating rounds.
//! - Diffusion layer `A` is an involutory 16×16 binary matrix (each
//!   output byte is the XOR of seven input bytes).
//! - Final round skips `A`, applies `SL_2`, then XORs two round keys
//!   (`ek_{R}` and `ek_{R+1}`).
//!
//! ## Key schedule
//!
//! Master key is padded to 256 bits (left-aligned), then split as
//! `KL || KR` of 128 bits each.  A 3-round 256-bit Feistel-like
//! routine using round constants `CK1, CK2, CK3` (chosen from the
//! binary expansion of `1/π`) produces four intermediate words
//! `W0, W1, W2, W3`.  Encryption round keys `ek_i` are derived as
//! XORs of cyclic rotations of `W_j` words; decryption keys are
//! obtained from `ek_i` via the diffusion layer `A`.
//!
//! ## References
//!
//! - **RFC 5794** — A Description of the ARIA Encryption Algorithm.
//! - **D. Kwon et al.**, "New Block Cipher: ARIA", ICISC 2003.

// ── S-boxes ──────────────────────────────────────────────────────────

/// S-box `S1` (= AES S-box).
const S1: [u8; 256] = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16,
];

/// S-box `S2`.
const S2: [u8; 256] = [
    0xe2, 0x4e, 0x54, 0xfc, 0x94, 0xc2, 0x4a, 0xcc, 0x62, 0x0d, 0x6a, 0x46, 0x3c, 0x4d, 0x8b, 0xd1,
    0x5e, 0xfa, 0x64, 0xcb, 0xb4, 0x97, 0xbe, 0x2b, 0xbc, 0x77, 0x2e, 0x03, 0xd3, 0x19, 0x59, 0xc1,
    0x1d, 0x06, 0x41, 0x6b, 0x55, 0xf0, 0x99, 0x69, 0xea, 0x9c, 0x18, 0xae, 0x63, 0xdf, 0xe7, 0xbb,
    0x00, 0x73, 0x66, 0xfb, 0x96, 0x4c, 0x85, 0xe4, 0x3a, 0x09, 0x45, 0xaa, 0x0f, 0xee, 0x10, 0xeb,
    0x2d, 0x7f, 0xf4, 0x29, 0xac, 0xcf, 0xad, 0x91, 0x8d, 0x78, 0xc8, 0x95, 0xf9, 0x2f, 0xce, 0xcd,
    0x08, 0x7a, 0x88, 0x38, 0x5c, 0x83, 0x2a, 0x28, 0x47, 0xdb, 0xb8, 0xc7, 0x93, 0xa4, 0x12, 0x53,
    0xff, 0x87, 0x0e, 0x31, 0x36, 0x21, 0x58, 0x48, 0x01, 0x8e, 0x37, 0x74, 0x32, 0xca, 0xe9, 0xb1,
    0xb7, 0xab, 0x0c, 0xd7, 0xc4, 0x56, 0x42, 0x26, 0x07, 0x98, 0x60, 0xd9, 0xb6, 0xb9, 0x11, 0x40,
    0xec, 0x20, 0x8c, 0xbd, 0xa0, 0xc9, 0x84, 0x04, 0x49, 0x23, 0xf1, 0x4f, 0x50, 0x1f, 0x13, 0xdc,
    0xd8, 0xc0, 0x9e, 0x57, 0xe3, 0xc3, 0x7b, 0x65, 0x3b, 0x02, 0x8f, 0x3e, 0xe8, 0x25, 0x92, 0xe5,
    0x15, 0xdd, 0xfd, 0x17, 0xa9, 0xbf, 0xd4, 0x9a, 0x7e, 0xc5, 0x39, 0x67, 0xfe, 0x76, 0x9d, 0x43,
    0xa7, 0xe1, 0xd0, 0xf5, 0x68, 0xf2, 0x1b, 0x34, 0x70, 0x05, 0xa3, 0x8a, 0xd5, 0x79, 0x86, 0xa8,
    0x30, 0xc6, 0x51, 0x4b, 0x1e, 0xa6, 0x27, 0xf6, 0x35, 0xd2, 0x6e, 0x24, 0x16, 0x82, 0x5f, 0xda,
    0xe6, 0x75, 0xa2, 0xef, 0x2c, 0xb2, 0x1c, 0x9f, 0x5d, 0x6f, 0x80, 0x0a, 0x72, 0x44, 0x9b, 0x6c,
    0x90, 0x0b, 0x5b, 0x33, 0x7d, 0x5a, 0x52, 0xf3, 0x61, 0xa1, 0xf7, 0xb0, 0xd6, 0x3f, 0x7c, 0x6d,
    0xed, 0x14, 0xe0, 0xa5, 0x3d, 0x22, 0xb3, 0xf8, 0x89, 0xde, 0x71, 0x1a, 0xaf, 0xba, 0xb5, 0x81,
];

const S1_INV: [u8; 256] = {
    let mut inv = [0u8; 256];
    let mut i = 0;
    while i < 256 {
        inv[S1[i] as usize] = i as u8;
        i += 1;
    }
    inv
};

const S2_INV: [u8; 256] = {
    let mut inv = [0u8; 256];
    let mut i = 0;
    while i < 256 {
        inv[S2[i] as usize] = i as u8;
        i += 1;
    }
    inv
};

// ── Substitution layers SL_1 and SL_2 ────────────────────────────────

/// Odd-round substitution layer: `SL_1 = (S1, S2, S1^{-1}, S2^{-1}) × 4`.
#[inline]
fn sl1(block: &mut [u8; 16]) {
    for i in 0..4 {
        let base = i * 4;
        block[base] = S1[block[base] as usize];
        block[base + 1] = S2[block[base + 1] as usize];
        block[base + 2] = S1_INV[block[base + 2] as usize];
        block[base + 3] = S2_INV[block[base + 3] as usize];
    }
}

/// Even-round substitution layer: `SL_2 = (S1^{-1}, S2^{-1}, S1, S2) × 4`.
#[inline]
fn sl2(block: &mut [u8; 16]) {
    for i in 0..4 {
        let base = i * 4;
        block[base] = S1_INV[block[base] as usize];
        block[base + 1] = S2_INV[block[base + 1] as usize];
        block[base + 2] = S1[block[base + 2] as usize];
        block[base + 3] = S2[block[base + 3] as usize];
    }
}

// ── Diffusion layer A (RFC 5794 §2.4.3) ──────────────────────────────

/// Involutory 16-byte diffusion: each output byte is the XOR of seven
/// input bytes.  Matrix indices follow RFC 5794 §2.4.3.
#[inline]
fn diffusion(b: &mut [u8; 16]) {
    let x = *b;
    b[0] = x[3] ^ x[4] ^ x[6] ^ x[8] ^ x[9] ^ x[13] ^ x[14];
    b[1] = x[2] ^ x[5] ^ x[7] ^ x[8] ^ x[9] ^ x[12] ^ x[15];
    b[2] = x[1] ^ x[4] ^ x[6] ^ x[10] ^ x[11] ^ x[12] ^ x[15];
    b[3] = x[0] ^ x[5] ^ x[7] ^ x[10] ^ x[11] ^ x[13] ^ x[14];
    b[4] = x[0] ^ x[2] ^ x[5] ^ x[8] ^ x[11] ^ x[14] ^ x[15];
    b[5] = x[1] ^ x[3] ^ x[4] ^ x[9] ^ x[10] ^ x[14] ^ x[15];
    b[6] = x[0] ^ x[2] ^ x[7] ^ x[9] ^ x[10] ^ x[12] ^ x[13];
    b[7] = x[1] ^ x[3] ^ x[6] ^ x[8] ^ x[11] ^ x[12] ^ x[13];
    b[8] = x[0] ^ x[1] ^ x[4] ^ x[7] ^ x[10] ^ x[13] ^ x[15];
    b[9] = x[0] ^ x[1] ^ x[5] ^ x[6] ^ x[11] ^ x[12] ^ x[14];
    b[10] = x[2] ^ x[3] ^ x[5] ^ x[6] ^ x[8] ^ x[13] ^ x[15];
    b[11] = x[2] ^ x[3] ^ x[4] ^ x[7] ^ x[9] ^ x[12] ^ x[14];
    b[12] = x[1] ^ x[2] ^ x[6] ^ x[7] ^ x[9] ^ x[11] ^ x[12];
    b[13] = x[0] ^ x[3] ^ x[6] ^ x[7] ^ x[8] ^ x[10] ^ x[13];
    b[14] = x[0] ^ x[3] ^ x[4] ^ x[5] ^ x[9] ^ x[11] ^ x[14];
    b[15] = x[1] ^ x[2] ^ x[4] ^ x[5] ^ x[8] ^ x[10] ^ x[15];
}

// ── Key schedule helpers ─────────────────────────────────────────────

/// Round constants (binary expansion of `1/π`), RFC 5794 §2.2.
const CK: [[u8; 16]; 3] = [
    [
        0x51, 0x7c, 0xc1, 0xb7, 0x27, 0x22, 0x0a, 0x94, 0xfe, 0x13, 0xab, 0xe8, 0xfa, 0x9a, 0x6e,
        0xe0,
    ],
    [
        0x6d, 0xb1, 0x4a, 0xcc, 0x9e, 0x21, 0xc8, 0x20, 0xff, 0x28, 0xb1, 0xd5, 0xef, 0x5d, 0xe2,
        0xb0,
    ],
    [
        0xdb, 0x92, 0x37, 0x1d, 0x21, 0x26, 0xe9, 0x70, 0x03, 0x24, 0x97, 0x75, 0x04, 0xe8, 0xc9,
        0x0e,
    ],
];

#[inline]
fn xor16(a: &mut [u8; 16], b: &[u8; 16]) {
    for i in 0..16 {
        a[i] ^= b[i];
    }
}

#[inline]
fn xor16_3(a: &[u8; 16], b: &[u8; 16]) -> [u8; 16] {
    let mut r = [0u8; 16];
    for i in 0..16 {
        r[i] = a[i] ^ b[i];
    }
    r
}

/// Odd round function `FO(D, RK) = A ∘ SL_1 (D ⊕ RK)`.
#[inline]
fn fo(d: &[u8; 16], rk: &[u8; 16]) -> [u8; 16] {
    let mut x = xor16_3(d, rk);
    sl1(&mut x);
    diffusion(&mut x);
    x
}

/// Even round function `FE(D, RK) = A ∘ SL_2 (D ⊕ RK)`.
#[inline]
fn fe(d: &[u8; 16], rk: &[u8; 16]) -> [u8; 16] {
    let mut x = xor16_3(d, rk);
    sl2(&mut x);
    diffusion(&mut x);
    x
}

/// Left circular rotation of a 128-bit value by `n` bits
/// (`0 < n < 128`), treating the 16-byte array as big-endian.
fn rotl128(b: &[u8; 16], n: usize) -> [u8; 16] {
    let n = n % 128;
    let byte_shift = n / 8;
    let bit_shift = n % 8;
    let mut tmp = [0u8; 16];
    for i in 0..16 {
        tmp[i] = b[(i + byte_shift) % 16];
    }
    if bit_shift == 0 {
        return tmp;
    }
    let mut out = [0u8; 16];
    for i in 0..16 {
        let hi = (tmp[i] as u16) << bit_shift;
        let lo = (tmp[(i + 1) % 16] as u16) >> (8 - bit_shift);
        out[i] = ((hi | lo) & 0xff) as u8;
    }
    out
}

#[inline]
fn rotr128(b: &[u8; 16], n: usize) -> [u8; 16] {
    rotl128(b, 128 - (n % 128))
}

// ── Key schedule core ────────────────────────────────────────────────

/// Compute the four 128-bit words `W0, W1, W2, W3` and `R` (number of
/// rounds) for a key of length 16, 24, or 32 bytes.
fn key_words(key: &[u8]) -> ([[u8; 16]; 4], usize) {
    let (rounds, ck_idx) = match key.len() {
        16 => (12, [0usize, 1, 2]),
        24 => (14, [1, 2, 0]),
        32 => (16, [2, 0, 1]),
        _ => panic!("ARIA: unsupported key length"),
    };
    let mut kl = [0u8; 16];
    let mut kr = [0u8; 16];
    kl.copy_from_slice(&key[..16]);
    if key.len() > 16 {
        let n = key.len() - 16;
        kr[..n].copy_from_slice(&key[16..]);
        // Remaining bytes of kr are already zero.
    }

    let w0 = kl;
    // W1 = FO(W0, CK1) ⊕ KR
    let t = fo(&w0, &CK[ck_idx[0]]);
    let w1 = xor16_3(&t, &kr);
    // W2 = FE(W1, CK2) ⊕ W0
    let t = fe(&w1, &CK[ck_idx[1]]);
    let w2 = xor16_3(&t, &w0);
    // W3 = FO(W2, CK3) ⊕ W1
    let t = fo(&w2, &CK[ck_idx[2]]);
    let w3 = xor16_3(&t, &w1);

    ([w0, w1, w2, w3], rounds)
}

/// Generate encryption round keys (`R + 1` keys) per RFC 5794 §2.2.
fn expand_enc(key: &[u8]) -> (Vec<[u8; 16]>, usize) {
    let (w, rounds) = key_words(key);
    let mut ek = Vec::with_capacity(rounds + 1);
    // ek1 = W0 ^ ROTR(W1, 19)
    ek.push(xor16_3(&w[0], &rotr128(&w[1], 19)));
    ek.push(xor16_3(&w[1], &rotr128(&w[2], 19)));
    ek.push(xor16_3(&w[2], &rotr128(&w[3], 19)));
    ek.push(xor16_3(&rotr128(&w[0], 19), &w[3]));

    ek.push(xor16_3(&w[0], &rotr128(&w[1], 31)));
    ek.push(xor16_3(&w[1], &rotr128(&w[2], 31)));
    ek.push(xor16_3(&w[2], &rotr128(&w[3], 31)));
    ek.push(xor16_3(&rotr128(&w[0], 31), &w[3]));

    ek.push(xor16_3(&w[0], &rotl128(&w[1], 61)));
    ek.push(xor16_3(&w[1], &rotl128(&w[2], 61)));
    ek.push(xor16_3(&w[2], &rotl128(&w[3], 61)));
    ek.push(xor16_3(&rotl128(&w[0], 61), &w[3]));

    ek.push(xor16_3(&w[0], &rotl128(&w[1], 31)));
    if rounds >= 14 {
        ek.push(xor16_3(&w[1], &rotl128(&w[2], 31)));
        ek.push(xor16_3(&w[2], &rotl128(&w[3], 31)));
    }
    if rounds >= 16 {
        ek.push(xor16_3(&rotl128(&w[0], 31), &w[3]));
        ek.push(xor16_3(&w[0], &rotl128(&w[1], 19)));
    }
    (ek, rounds)
}

/// Generate decryption round keys.  Per RFC 5794 §2.2 the decryption
/// keys are the reversed encryption keys, with the diffusion layer `A`
/// applied to all but the first and last.
fn expand_dec(key: &[u8]) -> (Vec<[u8; 16]>, usize) {
    let (ek, rounds) = expand_enc(key);
    let mut dk: Vec<[u8; 16]> = Vec::with_capacity(rounds + 1);
    dk.push(ek[rounds]);
    for i in 1..rounds {
        let mut t = ek[rounds - i];
        diffusion(&mut t);
        dk.push(t);
    }
    dk.push(ek[0]);
    (dk, rounds)
}

// ── Core encrypt / decrypt ───────────────────────────────────────────

fn encrypt_with_keys(block: &mut [u8; 16], rk: &[[u8; 16]], rounds: usize) {
    let mut state = *block;
    // Rounds 1..R-1: full odd/even rounds.
    for i in 0..(rounds - 1) {
        state = if i % 2 == 0 {
            fo(&state, &rk[i])
        } else {
            fe(&state, &rk[i])
        };
    }
    // Final round R: SL_2 applied to (state XOR ek_R), then XOR ek_{R+1}.
    let mut x = xor16_3(&state, &rk[rounds - 1]);
    sl2(&mut x);
    xor16(&mut x, &rk[rounds]);
    *block = x;
}

// ── Public structs ───────────────────────────────────────────────────

#[derive(Clone, Debug)]
pub struct Aria128 {
    ek: Vec<[u8; 16]>,
    dk: Vec<[u8; 16]>,
    rounds: usize,
}

impl Aria128 {
    pub fn new(key: &[u8; 16]) -> Self {
        let (ek, rounds) = expand_enc(key);
        let (dk, _) = expand_dec(key);
        Self { ek, dk, rounds }
    }
    pub fn encrypt_block(&self, block: &mut [u8; 16]) {
        encrypt_with_keys(block, &self.ek, self.rounds);
    }
    pub fn decrypt_block(&self, block: &mut [u8; 16]) {
        encrypt_with_keys(block, &self.dk, self.rounds);
    }
}

#[derive(Clone, Debug)]
pub struct Aria192 {
    ek: Vec<[u8; 16]>,
    dk: Vec<[u8; 16]>,
    rounds: usize,
}

impl Aria192 {
    pub fn new(key: &[u8; 24]) -> Self {
        let (ek, rounds) = expand_enc(key);
        let (dk, _) = expand_dec(key);
        Self { ek, dk, rounds }
    }
    pub fn encrypt_block(&self, block: &mut [u8; 16]) {
        encrypt_with_keys(block, &self.ek, self.rounds);
    }
    pub fn decrypt_block(&self, block: &mut [u8; 16]) {
        encrypt_with_keys(block, &self.dk, self.rounds);
    }
}

#[derive(Clone, Debug)]
pub struct Aria256 {
    ek: Vec<[u8; 16]>,
    dk: Vec<[u8; 16]>,
    rounds: usize,
}

impl Aria256 {
    pub fn new(key: &[u8; 32]) -> Self {
        let (ek, rounds) = expand_enc(key);
        let (dk, _) = expand_dec(key);
        Self { ek, dk, rounds }
    }
    pub fn encrypt_block(&self, block: &mut [u8; 16]) {
        encrypt_with_keys(block, &self.ek, self.rounds);
    }
    pub fn decrypt_block(&self, block: &mut [u8; 16]) {
        encrypt_with_keys(block, &self.dk, self.rounds);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hex_to_16(s: &str) -> [u8; 16] {
        let mut out = [0u8; 16];
        for i in 0..16 {
            out[i] = u8::from_str_radix(&s[2 * i..2 * i + 2], 16).unwrap();
        }
        out
    }
    fn hex_to_24(s: &str) -> [u8; 24] {
        let mut out = [0u8; 24];
        for i in 0..24 {
            out[i] = u8::from_str_radix(&s[2 * i..2 * i + 2], 16).unwrap();
        }
        out
    }
    fn hex_to_32(s: &str) -> [u8; 32] {
        let mut out = [0u8; 32];
        for i in 0..32 {
            out[i] = u8::from_str_radix(&s[2 * i..2 * i + 2], 16).unwrap();
        }
        out
    }

    /// **RFC 5794 Appendix — 128-bit key**.
    #[test]
    fn aria128_rfc_vector() {
        let key = hex_to_16("000102030405060708090a0b0c0d0e0f");
        let pt = hex_to_16("00112233445566778899aabbccddeeff");
        let expected = hex_to_16("d718fbd6ab644c739da95f3be6451778");
        let c = Aria128::new(&key);
        let mut b = pt;
        c.encrypt_block(&mut b);
        assert_eq!(b, expected);
        c.decrypt_block(&mut b);
        assert_eq!(b, pt);
    }

    /// **RFC 5794 Appendix — 192-bit key**.
    #[test]
    fn aria192_rfc_vector() {
        let key = hex_to_24("000102030405060708090a0b0c0d0e0f1011121314151617");
        let pt = hex_to_16("00112233445566778899aabbccddeeff");
        let expected = hex_to_16("26449c1805dbe7aa25a468ce263a9e79");
        let c = Aria192::new(&key);
        let mut b = pt;
        c.encrypt_block(&mut b);
        assert_eq!(b, expected);
        c.decrypt_block(&mut b);
        assert_eq!(b, pt);
    }

    /// **RFC 5794 Appendix — 256-bit key**.
    #[test]
    fn aria256_rfc_vector() {
        let key = hex_to_32("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f");
        let pt = hex_to_16("00112233445566778899aabbccddeeff");
        let expected = hex_to_16("f92bd7c79fb72e2f2b8f80c1972d24fc");
        let c = Aria256::new(&key);
        let mut b = pt;
        c.encrypt_block(&mut b);
        assert_eq!(b, expected);
        c.decrypt_block(&mut b);
        assert_eq!(b, pt);
    }

    /// **Diffusion involution**: `A(A(x)) = x`.
    #[test]
    fn diffusion_involution() {
        let mut x = *b"0123456789ABCDEF";
        let orig = x;
        diffusion(&mut x);
        assert_ne!(x, orig);
        diffusion(&mut x);
        assert_eq!(x, orig);
    }

    /// **Round-trip with arbitrary key/block**.
    #[test]
    fn aria128_roundtrip() {
        let key = [0x42u8; 16];
        let pt = [0x37u8; 16];
        let c = Aria128::new(&key);
        let mut b = pt;
        c.encrypt_block(&mut b);
        assert_ne!(b, pt);
        c.decrypt_block(&mut b);
        assert_eq!(b, pt);
    }
}
