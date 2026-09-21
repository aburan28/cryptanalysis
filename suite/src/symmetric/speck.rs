//! **Speck** — ARX block-cipher family (Beaulieu et al., NSA 2013).
//!
//! Speck is the Add-Rotate-Xor sibling of Simon: where Simon uses a
//! bitwise-AND nonlinear layer, Speck builds its nonlinearity from
//! modular addition.  The two ciphers share the same overall family
//! parameterisation (2n-bit block, mn-bit key) but were tuned for
//! different platforms — Simon for hardware, Speck for software.
//!
//! ## Variants implemented
//!
//! | Name              | Block | Key  | n  | m | T  | α | β |
//! |-------------------|-------|------|----|---|----|---|---|
//! | [`Speck64_128`]   | 64 b  | 128b | 32 | 4 | 27 | 8 | 3 |
//! | [`Speck128_128`]  | 128 b | 128b | 64 | 2 | 32 | 8 | 3 |
//! | [`Speck128_256`]  | 128 b | 256b | 64 | 4 | 34 | 8 | 3 |
//!
//! ## Round function
//!
//! Each round takes a two-word state `(x, y)` and round key `k`:
//!
//! ```text
//!     x ← (ROR(x, α) + y) ⊕ k
//!     y ← ROL(y, β) ⊕ x
//! ```
//!
//! Inverse:
//!
//! ```text
//!     y ← ROR(y ⊕ x, β)
//!     x ← ROL((x ⊕ k) − y, α)
//! ```
//!
//! ## Key schedule
//!
//! The master key is parsed as `(l_{m-2}, …, l_0, k_0)` (high-to-low
//! word).  Round keys `k_0, …, k_{T-1}` are derived by:
//!
//! ```text
//!     l_{i+m-1} = (k_i + ROR(l_i, α)) ⊕ i
//!     k_{i+1}   = ROL(k_i, β) ⊕ l_{i+m-1}
//! ```
//!
//! ## Byte conventions
//!
//! The block and key are byte arrays with lower-indexed words at the
//! lower offsets, each word in **little-endian** order:
//!
//! - Block: `bytes[0..n_bytes] = y` (low word), `bytes[n_bytes..] = x`.
//! - Key:   `bytes[0..n_bytes] = k_0`, then `l_0, l_1, …, l_{m-2}`.
//!
//! With this convention the paper's test vectors map to the byte
//! stream `[0x00, 0x01, …, 0x1f]` etc.
//!
//! ## Security note
//!
//! Speck was designed by NSA and was **rejected** from ISO/IEC 29192-2
//! in 2018 after sustained pushback from the cryptographic community
//! over its design provenance.  No public break is known, but for new
//! designs prefer AES, ChaCha20, or another widely-trusted primitive.
//! This implementation is included for pedagogy and interoperability.

#![allow(non_camel_case_types)]

// ── Round-function building blocks ───────────────────────────────────

#[inline]
fn speck128_enc_round(x: u64, y: u64, k: u64) -> (u64, u64) {
    let nx = x.rotate_right(8).wrapping_add(y) ^ k;
    let ny = y.rotate_left(3) ^ nx;
    (nx, ny)
}

#[inline]
fn speck128_dec_round(x: u64, y: u64, k: u64) -> (u64, u64) {
    let ny = (y ^ x).rotate_right(3);
    let nx = ((x ^ k).wrapping_sub(ny)).rotate_left(8);
    (nx, ny)
}

#[inline]
fn speck64_enc_round(x: u32, y: u32, k: u32) -> (u32, u32) {
    let nx = x.rotate_right(8).wrapping_add(y) ^ k;
    let ny = y.rotate_left(3) ^ nx;
    (nx, ny)
}

#[inline]
fn speck64_dec_round(x: u32, y: u32, k: u32) -> (u32, u32) {
    let ny = (y ^ x).rotate_right(3);
    let nx = ((x ^ k).wrapping_sub(ny)).rotate_left(8);
    (nx, ny)
}

// ── Speck128/128 ─────────────────────────────────────────────────────

const SPECK128_128_ROUNDS: usize = 32;

/// Speck with a 128-bit block and a 128-bit key (32 rounds).
#[derive(Clone, Debug)]
pub struct Speck128_128 {
    round_keys: [u64; SPECK128_128_ROUNDS],
}

impl Speck128_128 {
    pub fn new(key: &[u8; 16]) -> Self {
        let k0 = u64::from_le_bytes(key[0..8].try_into().unwrap());
        let l0 = u64::from_le_bytes(key[8..16].try_into().unwrap());
        let mut rk = [0u64; SPECK128_128_ROUNDS];
        rk[0] = k0;
        let mut l = l0;
        let mut k = k0;
        for i in 0..(SPECK128_128_ROUNDS - 1) {
            let new_l = k.wrapping_add(l.rotate_right(8)) ^ (i as u64);
            let new_k = k.rotate_left(3) ^ new_l;
            l = new_l;
            k = new_k;
            rk[i + 1] = k;
        }
        Self { round_keys: rk }
    }

    pub fn encrypt_block(&self, block: &mut [u8; 16]) {
        let mut y = u64::from_le_bytes(block[0..8].try_into().unwrap());
        let mut x = u64::from_le_bytes(block[8..16].try_into().unwrap());
        for &k in &self.round_keys {
            let (nx, ny) = speck128_enc_round(x, y, k);
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
            let (nx, ny) = speck128_dec_round(x, y, k);
            x = nx;
            y = ny;
        }
        block[0..8].copy_from_slice(&y.to_le_bytes());
        block[8..16].copy_from_slice(&x.to_le_bytes());
    }
}

// ── Speck128/256 ─────────────────────────────────────────────────────

const SPECK128_256_ROUNDS: usize = 34;

/// Speck with a 128-bit block and a 256-bit key (34 rounds).
#[derive(Clone, Debug)]
pub struct Speck128_256 {
    round_keys: [u64; SPECK128_256_ROUNDS],
}

impl Speck128_256 {
    pub fn new(key: &[u8; 32]) -> Self {
        let k0 = u64::from_le_bytes(key[0..8].try_into().unwrap());
        let l0 = u64::from_le_bytes(key[8..16].try_into().unwrap());
        let l1 = u64::from_le_bytes(key[16..24].try_into().unwrap());
        let l2 = u64::from_le_bytes(key[24..32].try_into().unwrap());

        let mut rk = [0u64; SPECK128_256_ROUNDS];
        rk[0] = k0;
        // Sliding window over l_i, l_{i+1}, l_{i+2}; iteration i emits l_{i+3}.
        let mut l = [l0, l1, l2];
        let mut k = k0;
        for i in 0..(SPECK128_256_ROUNDS - 1) {
            let new_l = k.wrapping_add(l[0].rotate_right(8)) ^ (i as u64);
            let new_k = k.rotate_left(3) ^ new_l;
            l = [l[1], l[2], new_l];
            k = new_k;
            rk[i + 1] = k;
        }
        Self { round_keys: rk }
    }

    pub fn encrypt_block(&self, block: &mut [u8; 16]) {
        let mut y = u64::from_le_bytes(block[0..8].try_into().unwrap());
        let mut x = u64::from_le_bytes(block[8..16].try_into().unwrap());
        for &k in &self.round_keys {
            let (nx, ny) = speck128_enc_round(x, y, k);
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
            let (nx, ny) = speck128_dec_round(x, y, k);
            x = nx;
            y = ny;
        }
        block[0..8].copy_from_slice(&y.to_le_bytes());
        block[8..16].copy_from_slice(&x.to_le_bytes());
    }
}

// ── Speck64/128 ──────────────────────────────────────────────────────

const SPECK64_128_ROUNDS: usize = 27;

/// Speck with a 64-bit block and a 128-bit key (27 rounds).
#[derive(Clone, Debug)]
pub struct Speck64_128 {
    round_keys: [u32; SPECK64_128_ROUNDS],
}

impl Speck64_128 {
    pub fn new(key: &[u8; 16]) -> Self {
        let k0 = u32::from_le_bytes(key[0..4].try_into().unwrap());
        let l0 = u32::from_le_bytes(key[4..8].try_into().unwrap());
        let l1 = u32::from_le_bytes(key[8..12].try_into().unwrap());
        let l2 = u32::from_le_bytes(key[12..16].try_into().unwrap());

        let mut rk = [0u32; SPECK64_128_ROUNDS];
        rk[0] = k0;
        let mut l = [l0, l1, l2];
        let mut k = k0;
        for i in 0..(SPECK64_128_ROUNDS - 1) {
            let new_l = k.wrapping_add(l[0].rotate_right(8)) ^ (i as u32);
            let new_k = k.rotate_left(3) ^ new_l;
            l = [l[1], l[2], new_l];
            k = new_k;
            rk[i + 1] = k;
        }
        Self { round_keys: rk }
    }

    pub fn encrypt_block(&self, block: &mut [u8; 8]) {
        let mut y = u32::from_le_bytes(block[0..4].try_into().unwrap());
        let mut x = u32::from_le_bytes(block[4..8].try_into().unwrap());
        for &k in &self.round_keys {
            let (nx, ny) = speck64_enc_round(x, y, k);
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
            let (nx, ny) = speck64_dec_round(x, y, k);
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

    /// Speck128/128 — paper Appendix C test vector:
    /// Key (k_1, k_0) = (0x0f0e0d0c0b0a0908, 0x0706050403020100)
    /// PT  (x,   y  ) = (0x6c61766975716520, 0x7469206564616d20)
    /// CT  (x,   y  ) = (0xa65d985179783265, 0x7860fedf5c570d18)
    #[test]
    fn speck128_128_paper_vector() {
        let key = [
            0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, // k_0 LE = 0x0706050403020100
            0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f, // l_0 LE = 0x0f0e0d0c0b0a0908
        ];
        let mut block = [0u8; 16];
        // y = 0x7469206564616d20, x = 0x6c61766975716520
        block[0..8].copy_from_slice(&0x7469206564616d20u64.to_le_bytes());
        block[8..16].copy_from_slice(&0x6c61766975716520u64.to_le_bytes());

        let c = Speck128_128::new(&key);
        c.encrypt_block(&mut block);

        let mut want = [0u8; 16];
        want[0..8].copy_from_slice(&0x7860fedf5c570d18u64.to_le_bytes());
        want[8..16].copy_from_slice(&0xa65d985179783265u64.to_le_bytes());
        assert_eq!(block, want, "Speck128/128 encrypt mismatch");

        c.decrypt_block(&mut block);
        let mut pt = [0u8; 16];
        pt[0..8].copy_from_slice(&0x7469206564616d20u64.to_le_bytes());
        pt[8..16].copy_from_slice(&0x6c61766975716520u64.to_le_bytes());
        assert_eq!(block, pt, "Speck128/128 decrypt mismatch");
    }

    /// Speck128/256 — paper Appendix C test vector:
    /// Key (l_2, l_1, l_0, k_0) = (0x1f1e1d1c1b1a1918, 0x1716151413121110,
    ///                              0x0f0e0d0c0b0a0908, 0x0706050403020100)
    /// PT  = (0x65736f6874206e49, 0x202e72656e6f6f70)
    /// CT  = (0x4109010405c0f53e, 0x4eeeb48d9c188f43)
    #[test]
    fn speck128_256_paper_vector() {
        let mut key = [0u8; 32];
        for (i, b) in key.iter_mut().enumerate() {
            *b = i as u8;
        }
        let mut block = [0u8; 16];
        block[0..8].copy_from_slice(&0x202e72656e6f6f70u64.to_le_bytes());
        block[8..16].copy_from_slice(&0x65736f6874206e49u64.to_le_bytes());

        let c = Speck128_256::new(&key);
        c.encrypt_block(&mut block);

        let mut want = [0u8; 16];
        want[0..8].copy_from_slice(&0x4eeeb48d9c188f43u64.to_le_bytes());
        want[8..16].copy_from_slice(&0x4109010405c0f53eu64.to_le_bytes());
        assert_eq!(block, want, "Speck128/256 encrypt mismatch");

        c.decrypt_block(&mut block);
        let mut pt = [0u8; 16];
        pt[0..8].copy_from_slice(&0x202e72656e6f6f70u64.to_le_bytes());
        pt[8..16].copy_from_slice(&0x65736f6874206e49u64.to_le_bytes());
        assert_eq!(block, pt, "Speck128/256 decrypt mismatch");
    }

    /// Speck64/128 — paper Appendix C test vector:
    /// Key (l_2, l_1, l_0, k_0) = (0x1b1a1918, 0x13121110, 0x0b0a0908, 0x03020100)
    /// PT  = (0x3b726574, 0x7475432d)
    /// CT  = (0x8c6fa548, 0x454e028b)
    ///
    /// Note: the paper's key uses a `+8` byte-gap pattern between
    /// words, not the contiguous `[0..15]` sequence used by the
    /// 128-bit-block variants.
    #[test]
    fn speck64_128_paper_vector() {
        let key: [u8; 16] = [
            0x00, 0x01, 0x02, 0x03, // k_0  LE = 0x03020100
            0x08, 0x09, 0x0a, 0x0b, // l_0  LE = 0x0b0a0908
            0x10, 0x11, 0x12, 0x13, // l_1  LE = 0x13121110
            0x18, 0x19, 0x1a, 0x1b, // l_2  LE = 0x1b1a1918
        ];
        let mut block = [0u8; 8];
        block[0..4].copy_from_slice(&0x7475432du32.to_le_bytes());
        block[4..8].copy_from_slice(&0x3b726574u32.to_le_bytes());

        let c = Speck64_128::new(&key);
        c.encrypt_block(&mut block);

        let mut want = [0u8; 8];
        want[0..4].copy_from_slice(&0x454e028bu32.to_le_bytes());
        want[4..8].copy_from_slice(&0x8c6fa548u32.to_le_bytes());
        assert_eq!(block, want, "Speck64/128 encrypt mismatch");

        c.decrypt_block(&mut block);
        let mut pt = [0u8; 8];
        pt[0..4].copy_from_slice(&0x7475432du32.to_le_bytes());
        pt[4..8].copy_from_slice(&0x3b726574u32.to_le_bytes());
        assert_eq!(block, pt, "Speck64/128 decrypt mismatch");
    }

    /// Random round-trip across all three variants.
    #[test]
    fn speck_random_round_trips() {
        let key16 = [0x42u8; 16];
        let key32 = [0x77u8; 32];

        let c1 = Speck128_128::new(&key16);
        let mut b1 = [0xAAu8; 16];
        let orig1 = b1;
        c1.encrypt_block(&mut b1);
        assert_ne!(b1, orig1);
        c1.decrypt_block(&mut b1);
        assert_eq!(b1, orig1);

        let c2 = Speck128_256::new(&key32);
        let mut b2 = [0xBBu8; 16];
        let orig2 = b2;
        c2.encrypt_block(&mut b2);
        assert_ne!(b2, orig2);
        c2.decrypt_block(&mut b2);
        assert_eq!(b2, orig2);

        let c3 = Speck64_128::new(&key16);
        let mut b3 = [0xCCu8; 8];
        let orig3 = b3;
        c3.encrypt_block(&mut b3);
        assert_ne!(b3, orig3);
        c3.decrypt_block(&mut b3);
        assert_eq!(b3, orig3);
    }

    /// Zero key + zero plaintext should not be identity (sanity check
    /// for a non-degenerate cipher).
    #[test]
    fn speck_zero_key_not_identity() {
        let c = Speck128_128::new(&[0u8; 16]);
        let mut block = [0u8; 16];
        c.encrypt_block(&mut block);
        assert_ne!(block, [0u8; 16]);
    }
}
