//! **Simon** — bitwise-AND block-cipher family (Beaulieu et al., NSA 2013).
//!
//! Simon is the AND-Rotate-Xor sibling of [Speck](super::speck): a
//! balanced Feistel cipher whose nonlinearity comes from a bitwise AND
//! between two cyclic rotations of the round state.  It was tuned for
//! small hardware footprint, the way Speck was tuned for software.
//!
//! ## Variants implemented
//!
//! | Name             | Block | Key  | n  | m | T  | z-seq |
//! |------------------|-------|------|----|---|----|-------|
//! | [`Simon64_128`]  | 64 b  | 128b | 32 | 4 | 44 | z_3   |
//! | [`Simon128_128`] | 128 b | 128b | 64 | 2 | 68 | z_2   |
//! | [`Simon128_256`] | 128 b | 256b | 64 | 4 | 72 | z_4   |
//!
//! ## Round function
//!
//! On a two-word state `(x, y)` with round key `k`:
//!
//! ```text
//!     f(x) = (ROL(x, 1) ∧ ROL(x, 8)) ⊕ ROL(x, 2)
//!     (x', y') = (y ⊕ f(x) ⊕ k, x)
//! ```
//!
//! The inverse is `(x', y') = (y, x ⊕ f(y) ⊕ k)`.
//!
//! ## Key schedule
//!
//! The master key supplies the first `m` round keys `k_0, …, k_{m-1}`.
//! Successive round keys are produced by combining a fixed constant
//! `c = 2^n − 4` with a bit of one of five 62-bit `z_j` sequences
//! (cycled by index `i mod 62`) and a function of earlier round keys:
//!
//! ```text
//!     m = 2: k_{i+2} = c ⊕ z_j(i) ⊕ k_i ⊕ (I ⊕ S^{-1}) S^{-3} k_{i+1}
//!     m = 3: k_{i+3} = c ⊕ z_j(i) ⊕ k_i ⊕ (I ⊕ S^{-1}) S^{-3} k_{i+2}
//!     m = 4: k_{i+4} = c ⊕ z_j(i) ⊕ k_i ⊕ (I ⊕ S^{-1}) (S^{-3} k_{i+3} ⊕ k_{i+1})
//! ```
//!
//! where `S^{-j}` is right-rotation by `j` and `I` is the identity, so
//! `(I ⊕ S^{-1}) v = v ⊕ ROR(v, 1)`.
//!
//! ## Byte conventions
//!
//! Same as Speck (see [`super::speck`]): the byte array holds words
//! low-to-high, each word little-endian.
//!
//! - Block: `bytes[0..n_bytes] = y` (low word), `bytes[n_bytes..] = x`.
//! - Key:   `bytes[0..n_bytes] = k_0, …, bytes[(m-1)·n_bytes..] = k_{m-1}`.
//!
//! ## Security note
//!
//! Like Speck, Simon was withdrawn from ISO/IEC 29192-2 in 2018.  No
//! public break is known, but for new designs prefer a primitive with
//! broader public confidence.  This implementation is included for
//! pedagogy and interoperability.

#![allow(non_camel_case_types)]

/// The five 62-bit `z_j` constants from the Simon paper, packed so that
/// bit `i` of `Z_SIMON[j]` is `z_j(i)`.
///
/// Extract via `(Z_SIMON[j] >> (i % 62)) & 1`.
const Z_SIMON: [u64; 5] = [
    0x19C3522FB386A45F, // z_0
    0x2D0C9F715A193F71, // z_1
    0x3369F885192C0EF5, // z_2
    0x3C2CE51207A635DB, // z_3
    0x3DC94C3A046D678B, // z_4
];

// ── Round-function building blocks ───────────────────────────────────

#[inline]
fn simon128_enc_round(x: u64, y: u64, k: u64) -> (u64, u64) {
    let f = (x.rotate_left(1) & x.rotate_left(8)) ^ x.rotate_left(2);
    (y ^ f ^ k, x)
}

#[inline]
fn simon128_dec_round(x: u64, y: u64, k: u64) -> (u64, u64) {
    // Inverse: swap halves and reapply f to the new low word.
    let f = (y.rotate_left(1) & y.rotate_left(8)) ^ y.rotate_left(2);
    (y, x ^ f ^ k)
}

#[inline]
fn simon64_enc_round(x: u32, y: u32, k: u32) -> (u32, u32) {
    let f = (x.rotate_left(1) & x.rotate_left(8)) ^ x.rotate_left(2);
    (y ^ f ^ k, x)
}

#[inline]
fn simon64_dec_round(x: u32, y: u32, k: u32) -> (u32, u32) {
    let f = (y.rotate_left(1) & y.rotate_left(8)) ^ y.rotate_left(2);
    (y, x ^ f ^ k)
}

// ── Simon128/128 ─────────────────────────────────────────────────────

const SIMON128_128_ROUNDS: usize = 68;

/// Simon with a 128-bit block and a 128-bit key (68 rounds, `z_2`).
#[derive(Clone, Debug)]
pub struct Simon128_128 {
    round_keys: [u64; SIMON128_128_ROUNDS],
}

impl Simon128_128 {
    pub fn new(key: &[u8; 16]) -> Self {
        let k0 = u64::from_le_bytes(key[0..8].try_into().unwrap());
        let k1 = u64::from_le_bytes(key[8..16].try_into().unwrap());
        let z = Z_SIMON[2];
        let c: u64 = !3u64;

        let mut rk = [0u64; SIMON128_128_ROUNDS];
        rk[0] = k0;
        rk[1] = k1;
        for i in 0..(SIMON128_128_ROUNDS - 2) {
            let mut t = rk[i + 1].rotate_right(3);
            t ^= t.rotate_right(1);
            rk[i + 2] = c ^ ((z >> (i % 62)) & 1) ^ rk[i] ^ t;
        }
        Self { round_keys: rk }
    }

    pub fn encrypt_block(&self, block: &mut [u8; 16]) {
        let mut y = u64::from_le_bytes(block[0..8].try_into().unwrap());
        let mut x = u64::from_le_bytes(block[8..16].try_into().unwrap());
        for &k in &self.round_keys {
            let (nx, ny) = simon128_enc_round(x, y, k);
            x = nx;
            y = ny;
        }
        block[0..8].copy_from_slice(&y.to_le_bytes());
        block[8..16].copy_from_slice(&x.to_le_bytes());
    }

    pub fn decrypt_block(&self, block: &mut [u8; 16]) {
        let mut y = u64::from_le_bytes(block[0..8].try_into().unwrap());
        let mut x = u64::from_le_bytes(block[8..16].try_into().unwrap());
        for &k in self.round_keys.iter().rev() {
            let (nx, ny) = simon128_dec_round(x, y, k);
            x = nx;
            y = ny;
        }
        block[0..8].copy_from_slice(&y.to_le_bytes());
        block[8..16].copy_from_slice(&x.to_le_bytes());
    }
}

// ── Simon128/256 ─────────────────────────────────────────────────────

const SIMON128_256_ROUNDS: usize = 72;

/// Simon with a 128-bit block and a 256-bit key (72 rounds, `z_4`).
#[derive(Clone, Debug)]
pub struct Simon128_256 {
    round_keys: [u64; SIMON128_256_ROUNDS],
}

impl Simon128_256 {
    pub fn new(key: &[u8; 32]) -> Self {
        let k0 = u64::from_le_bytes(key[0..8].try_into().unwrap());
        let k1 = u64::from_le_bytes(key[8..16].try_into().unwrap());
        let k2 = u64::from_le_bytes(key[16..24].try_into().unwrap());
        let k3 = u64::from_le_bytes(key[24..32].try_into().unwrap());
        let z = Z_SIMON[4];
        let c: u64 = !3u64;

        let mut rk = [0u64; SIMON128_256_ROUNDS];
        rk[0] = k0;
        rk[1] = k1;
        rk[2] = k2;
        rk[3] = k3;
        for i in 0..(SIMON128_256_ROUNDS - 4) {
            let mut t = rk[i + 3].rotate_right(3) ^ rk[i + 1];
            t ^= t.rotate_right(1);
            rk[i + 4] = c ^ ((z >> (i % 62)) & 1) ^ rk[i] ^ t;
        }
        Self { round_keys: rk }
    }

    pub fn encrypt_block(&self, block: &mut [u8; 16]) {
        let mut y = u64::from_le_bytes(block[0..8].try_into().unwrap());
        let mut x = u64::from_le_bytes(block[8..16].try_into().unwrap());
        for &k in &self.round_keys {
            let (nx, ny) = simon128_enc_round(x, y, k);
            x = nx;
            y = ny;
        }
        block[0..8].copy_from_slice(&y.to_le_bytes());
        block[8..16].copy_from_slice(&x.to_le_bytes());
    }

    pub fn decrypt_block(&self, block: &mut [u8; 16]) {
        let mut y = u64::from_le_bytes(block[0..8].try_into().unwrap());
        let mut x = u64::from_le_bytes(block[8..16].try_into().unwrap());
        for &k in self.round_keys.iter().rev() {
            let (nx, ny) = simon128_dec_round(x, y, k);
            x = nx;
            y = ny;
        }
        block[0..8].copy_from_slice(&y.to_le_bytes());
        block[8..16].copy_from_slice(&x.to_le_bytes());
    }
}

// ── Simon64/128 ──────────────────────────────────────────────────────

const SIMON64_128_ROUNDS: usize = 44;

/// Simon with a 64-bit block and a 128-bit key (44 rounds, `z_3`).
#[derive(Clone, Debug)]
pub struct Simon64_128 {
    round_keys: [u32; SIMON64_128_ROUNDS],
}

impl Simon64_128 {
    pub fn new(key: &[u8; 16]) -> Self {
        let k0 = u32::from_le_bytes(key[0..4].try_into().unwrap());
        let k1 = u32::from_le_bytes(key[4..8].try_into().unwrap());
        let k2 = u32::from_le_bytes(key[8..12].try_into().unwrap());
        let k3 = u32::from_le_bytes(key[12..16].try_into().unwrap());
        let z = Z_SIMON[3];
        let c: u32 = !3u32;

        let mut rk = [0u32; SIMON64_128_ROUNDS];
        rk[0] = k0;
        rk[1] = k1;
        rk[2] = k2;
        rk[3] = k3;
        for i in 0..(SIMON64_128_ROUNDS - 4) {
            let mut t = rk[i + 3].rotate_right(3) ^ rk[i + 1];
            t ^= t.rotate_right(1);
            rk[i + 4] = c ^ (((z >> (i % 62)) & 1) as u32) ^ rk[i] ^ t;
        }
        Self { round_keys: rk }
    }

    pub fn encrypt_block(&self, block: &mut [u8; 8]) {
        let mut y = u32::from_le_bytes(block[0..4].try_into().unwrap());
        let mut x = u32::from_le_bytes(block[4..8].try_into().unwrap());
        for &k in &self.round_keys {
            let (nx, ny) = simon64_enc_round(x, y, k);
            x = nx;
            y = ny;
        }
        block[0..4].copy_from_slice(&y.to_le_bytes());
        block[4..8].copy_from_slice(&x.to_le_bytes());
    }

    pub fn decrypt_block(&self, block: &mut [u8; 8]) {
        let mut y = u32::from_le_bytes(block[0..4].try_into().unwrap());
        let mut x = u32::from_le_bytes(block[4..8].try_into().unwrap());
        for &k in self.round_keys.iter().rev() {
            let (nx, ny) = simon64_dec_round(x, y, k);
            x = nx;
            y = ny;
        }
        block[0..4].copy_from_slice(&y.to_le_bytes());
        block[4..8].copy_from_slice(&x.to_le_bytes());
    }
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// Simon128/128 — paper Appendix C test vector:
    /// Key (k_1, k_0) = (0x0f0e0d0c0b0a0908, 0x0706050403020100)
    /// PT  (x,   y  ) = (0x6373656420737265, 0x6c6c657661727420)
    /// CT  (x,   y  ) = (0x49681b1e1e54fe3f, 0x65aa832af84e0bbc)
    ///
    /// Block bytes (LE-y || LE-x) spell " travellers desc" — the
    /// paper's ASCII pun "the travellers desc[ended]".
    #[test]
    fn simon128_128_paper_vector() {
        let mut key = [0u8; 16];
        for (i, b) in key.iter_mut().enumerate() {
            *b = i as u8;
        }
        let mut block = [0u8; 16];
        block[0..8].copy_from_slice(&0x6c6c657661727420u64.to_le_bytes());
        block[8..16].copy_from_slice(&0x6373656420737265u64.to_le_bytes());

        let c = Simon128_128::new(&key);
        c.encrypt_block(&mut block);

        let mut want = [0u8; 16];
        want[0..8].copy_from_slice(&0x65aa832af84e0bbcu64.to_le_bytes());
        want[8..16].copy_from_slice(&0x49681b1e1e54fe3fu64.to_le_bytes());
        assert_eq!(block, want, "Simon128/128 encrypt mismatch");

        c.decrypt_block(&mut block);
        let mut pt = [0u8; 16];
        pt[0..8].copy_from_slice(&0x6c6c657661727420u64.to_le_bytes());
        pt[8..16].copy_from_slice(&0x6373656420737265u64.to_le_bytes());
        assert_eq!(block, pt, "Simon128/128 decrypt mismatch");
    }

    /// Simon128/256 — paper Appendix C test vector:
    /// Key (k_3, k_2, k_1, k_0) = (0x1f1e1d1c1b1a1918, 0x1716151413121110,
    ///                              0x0f0e0d0c0b0a0908, 0x0706050403020100)
    /// PT  = (0x74206e69206d6f6f, 0x6d69732061207369)
    /// CT  = (0x8d2b5579afc8a3a0, 0x3bf72a87efe7b868)
    #[test]
    fn simon128_256_paper_vector() {
        let mut key = [0u8; 32];
        for (i, b) in key.iter_mut().enumerate() {
            *b = i as u8;
        }
        let mut block = [0u8; 16];
        block[0..8].copy_from_slice(&0x6d69732061207369u64.to_le_bytes());
        block[8..16].copy_from_slice(&0x74206e69206d6f6fu64.to_le_bytes());

        let c = Simon128_256::new(&key);
        c.encrypt_block(&mut block);

        let mut want = [0u8; 16];
        want[0..8].copy_from_slice(&0x3bf72a87efe7b868u64.to_le_bytes());
        want[8..16].copy_from_slice(&0x8d2b5579afc8a3a0u64.to_le_bytes());
        assert_eq!(block, want, "Simon128/256 encrypt mismatch");

        c.decrypt_block(&mut block);
        let mut pt = [0u8; 16];
        pt[0..8].copy_from_slice(&0x6d69732061207369u64.to_le_bytes());
        pt[8..16].copy_from_slice(&0x74206e69206d6f6fu64.to_le_bytes());
        assert_eq!(block, pt, "Simon128/256 decrypt mismatch");
    }

    /// Simon64/128 — paper Appendix C test vector:
    /// Key (k_3, k_2, k_1, k_0) = (0x1b1a1918, 0x13121110, 0x0b0a0908, 0x03020100)
    /// PT  = (0x656b696c, 0x20646e75)
    /// CT  = (0x44c8fc20, 0xb9dfa07a)
    ///
    /// Note: like Speck64/128, the paper's key bytes use a `+8` gap
    /// pattern between words.
    #[test]
    fn simon64_128_paper_vector() {
        let key: [u8; 16] = [
            0x00, 0x01, 0x02, 0x03, // k_0  LE = 0x03020100
            0x08, 0x09, 0x0a, 0x0b, // k_1  LE = 0x0b0a0908
            0x10, 0x11, 0x12, 0x13, // k_2  LE = 0x13121110
            0x18, 0x19, 0x1a, 0x1b, // k_3  LE = 0x1b1a1918
        ];
        let mut block = [0u8; 8];
        block[0..4].copy_from_slice(&0x20646e75u32.to_le_bytes());
        block[4..8].copy_from_slice(&0x656b696cu32.to_le_bytes());

        let c = Simon64_128::new(&key);
        c.encrypt_block(&mut block);

        let mut want = [0u8; 8];
        want[0..4].copy_from_slice(&0xb9dfa07au32.to_le_bytes());
        want[4..8].copy_from_slice(&0x44c8fc20u32.to_le_bytes());
        assert_eq!(block, want, "Simon64/128 encrypt mismatch");

        c.decrypt_block(&mut block);
        let mut pt = [0u8; 8];
        pt[0..4].copy_from_slice(&0x20646e75u32.to_le_bytes());
        pt[4..8].copy_from_slice(&0x656b696cu32.to_le_bytes());
        assert_eq!(block, pt, "Simon64/128 decrypt mismatch");
    }

    /// Random round-trips across all three variants.
    #[test]
    fn simon_random_round_trips() {
        let key16 = [0x42u8; 16];
        let key32 = [0x77u8; 32];

        let c1 = Simon128_128::new(&key16);
        let mut b1 = [0xAAu8; 16];
        let orig1 = b1;
        c1.encrypt_block(&mut b1);
        assert_ne!(b1, orig1);
        c1.decrypt_block(&mut b1);
        assert_eq!(b1, orig1);

        let c2 = Simon128_256::new(&key32);
        let mut b2 = [0xBBu8; 16];
        let orig2 = b2;
        c2.encrypt_block(&mut b2);
        assert_ne!(b2, orig2);
        c2.decrypt_block(&mut b2);
        assert_eq!(b2, orig2);

        let c3 = Simon64_128::new(&key16);
        let mut b3 = [0xCCu8; 8];
        let orig3 = b3;
        c3.encrypt_block(&mut b3);
        assert_ne!(b3, orig3);
        c3.decrypt_block(&mut b3);
        assert_eq!(b3, orig3);
    }
}
