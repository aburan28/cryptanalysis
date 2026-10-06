//! **PRESENT** — ultra-lightweight SP-network block cipher.
//!
//! Designed by Bogdanov, Knudsen, Leander, Paar, Poschmann, Robshaw,
//! Seurin & Vikkelsoe at CHES 2007 and standardised in **ISO/IEC
//! 29192-2** (lightweight cryptography).  PRESENT targets hardware: a
//! reference RTL implementation fits in ~1570 gate equivalents, making
//! it a poster-child for constrained-device cryptography.
//!
//! ## Structure
//!
//! - 64-bit block, **80-bit** ([`Present80`]) or **128-bit**
//!   ([`Present128`]) key, **31 rounds** plus a post-whitening key
//!   addition.
//! - Each round consists of `addRoundKey` (XOR with a 64-bit subkey),
//!   `sBoxLayer` (16 parallel applications of a fixed 4-bit S-box),
//!   and `pLayer` (a fixed bit permutation on 64 bits).
//! - The bit permutation `P` sends bit `i` to bit `P(i)` where
//!   `P(i) = (16·i) mod 63` for `i ≠ 63`, and `P(63) = 63`.
//!
//! ## Byte conventions
//!
//! The state and key are read **big-endian** as 64- and 80- / 128-bit
//! integers (`bytes[0]` is the most significant byte).  This matches
//! the paper's worked example in Appendix I where key `0xffff…ff` and
//! plaintext `0xffff…ff` are both written in the natural hex order.
//!
//! ## Security note
//!
//! PRESENT has stood up reasonably well against more than a decade of
//! cryptanalysis: the best published attacks on the full 31-round
//! cipher are biclique-style attacks with only marginal advantage over
//! brute force on the 80-bit variant.  However, the 64-bit block makes
//! it unsuitable for encrypting more than a few hundred MiB under one
//! key (Sweet32), and the 80-bit key is well within reach of large
//! brute-force budgets.  PRESENT is meant for resource-constrained
//! tags / sensors, not for general-purpose data protection — prefer
//! AES or ChaCha20 otherwise.

#![allow(non_camel_case_types)]

/// The 4-bit S-box (paper Table 3).
const SBOX: [u8; 16] = [
    0xC, 0x5, 0x6, 0xB, 0x9, 0x0, 0xA, 0xD, 0x3, 0xE, 0xF, 0x8, 0x4, 0x7, 0x1, 0x2,
];

/// Inverse S-box (auto-derived in `sbox_inv`).
const SBOX_INV: [u8; 16] = {
    let mut inv = [0u8; 16];
    let mut i = 0;
    while i < 16 {
        inv[SBOX[i] as usize] = i as u8;
        i += 1;
    }
    inv
};

/// Apply the S-box to all 16 nibbles of a 64-bit state.
#[inline]
fn s_layer(state: u64) -> u64 {
    let mut out = 0u64;
    for i in 0..16 {
        let nibble = ((state >> (4 * i)) & 0xF) as usize;
        out |= (SBOX[nibble] as u64) << (4 * i);
    }
    out
}

/// Apply the inverse S-box to all 16 nibbles of a 64-bit state.
#[inline]
fn s_layer_inv(state: u64) -> u64 {
    let mut out = 0u64;
    for i in 0..16 {
        let nibble = ((state >> (4 * i)) & 0xF) as usize;
        out |= (SBOX_INV[nibble] as u64) << (4 * i);
    }
    out
}

/// `P(i) = (16·i) mod 63` for `i < 63`, `P(63) = 63`.
const fn p_perm(i: u32) -> u32 {
    if i == 63 {
        63
    } else {
        (16 * i) % 63
    }
}

/// Apply the bit permutation `P` to a 64-bit state.
#[inline]
fn p_layer(state: u64) -> u64 {
    let mut out = 0u64;
    let mut i = 0;
    while i < 64 {
        let bit = (state >> i) & 1;
        out |= bit << p_perm(i);
        i += 1;
    }
    out
}

/// Apply the inverse permutation `P⁻¹`.
#[inline]
fn p_layer_inv(state: u64) -> u64 {
    let mut out = 0u64;
    let mut i = 0;
    while i < 64 {
        let bit = (state >> p_perm(i)) & 1;
        out |= bit << i;
        i += 1;
    }
    out
}

const ROUNDS: usize = 31;

// ── PRESENT-80 ───────────────────────────────────────────────────────

/// PRESENT with an 80-bit key (31 rounds).
#[derive(Clone, Debug)]
pub struct Present80 {
    round_keys: [u64; ROUNDS + 1],
}

impl Present80 {
    /// Construct a PRESENT-80 cipher from a 10-byte key.
    ///
    /// The key register is 80 bits; we hold it in a `u128` with the
    /// high 80 bits populated (`key << 48`) so that "left-most 64 bits"
    /// is a simple high-half extract.
    pub fn new(key: &[u8; 10]) -> Self {
        // Load big-endian into a u128 where the key occupies bits 127..48.
        let mut k: u128 = 0;
        for &b in key {
            k = (k << 8) | (b as u128);
        }
        // Now `k` holds the key in the low 80 bits.  Shift up so the
        // 80 valid bits live in bits 127..48 — this makes the spec's
        // 80-bit rotation/operations easier to write as 128-bit ops
        // followed by a mask.
        const MASK80: u128 = (1u128 << 80) - 1;
        k &= MASK80;

        let mut rk = [0u64; ROUNDS + 1];
        // K_1 = leftmost 64 bits of the register
        rk[0] = ((k >> 16) & 0xFFFF_FFFF_FFFF_FFFF) as u64;
        for i in 1..=ROUNDS {
            // Step 1: rotate the 80-bit key register left by 61.
            k = (((k << 61) | (k >> 19)) & MASK80) & MASK80;
            // Step 2: S-box on the top nibble (bits 79..76).
            let top = ((k >> 76) & 0xF) as usize;
            k = (k & !(0xFu128 << 76)) | ((SBOX[top] as u128) << 76);
            // Step 3: XOR the round counter `i` into bits 19..15.
            k ^= (i as u128) << 15;
            // Extract K_{i+1} as the leftmost 64 bits.
            rk[i] = ((k >> 16) & 0xFFFF_FFFF_FFFF_FFFF) as u64;
        }
        Self { round_keys: rk }
    }

    /// Encrypt a single 64-bit block in place.
    pub fn encrypt_block(&self, block: &mut [u8; 8]) {
        let mut state = u64::from_be_bytes(*block);
        for i in 0..ROUNDS {
            state ^= self.round_keys[i];
            state = s_layer(state);
            state = p_layer(state);
        }
        state ^= self.round_keys[ROUNDS];
        block.copy_from_slice(&state.to_be_bytes());
    }

    /// Decrypt a single 64-bit block in place.
    pub fn decrypt_block(&self, block: &mut [u8; 8]) {
        let mut state = u64::from_be_bytes(*block);
        state ^= self.round_keys[ROUNDS];
        for i in (0..ROUNDS).rev() {
            state = p_layer_inv(state);
            state = s_layer_inv(state);
            state ^= self.round_keys[i];
        }
        block.copy_from_slice(&state.to_be_bytes());
    }
}

// ── PRESENT-128 ──────────────────────────────────────────────────────

/// PRESENT with a 128-bit key (31 rounds).
#[derive(Clone, Debug)]
pub struct Present128 {
    round_keys: [u64; ROUNDS + 1],
}

impl Present128 {
    /// Construct a PRESENT-128 cipher from a 16-byte key.
    pub fn new(key: &[u8; 16]) -> Self {
        let mut k: u128 = 0;
        for &b in key {
            k = (k << 8) | (b as u128);
        }

        let mut rk = [0u64; ROUNDS + 1];
        rk[0] = (k >> 64) as u64;
        for i in 1..=ROUNDS {
            // Step 1: rotate the 128-bit key register left by 61.
            k = k.rotate_left(61);
            // Step 2: S-box on the top two nibbles (bits 127..120).
            let top1 = ((k >> 124) & 0xF) as usize;
            let top2 = ((k >> 120) & 0xF) as usize;
            k = (k & !(0xFFu128 << 120))
                | ((SBOX[top1] as u128) << 124)
                | ((SBOX[top2] as u128) << 120);
            // Step 3: XOR the round counter `i` into bits 66..62.
            k ^= (i as u128) << 62;
            rk[i] = (k >> 64) as u64;
        }
        Self { round_keys: rk }
    }

    /// Encrypt a single 64-bit block in place.
    pub fn encrypt_block(&self, block: &mut [u8; 8]) {
        let mut state = u64::from_be_bytes(*block);
        for i in 0..ROUNDS {
            state ^= self.round_keys[i];
            state = s_layer(state);
            state = p_layer(state);
        }
        state ^= self.round_keys[ROUNDS];
        block.copy_from_slice(&state.to_be_bytes());
    }

    /// Decrypt a single 64-bit block in place.
    pub fn decrypt_block(&self, block: &mut [u8; 8]) {
        let mut state = u64::from_be_bytes(*block);
        state ^= self.round_keys[ROUNDS];
        for i in (0..ROUNDS).rev() {
            state = p_layer_inv(state);
            state = s_layer_inv(state);
            state ^= self.round_keys[i];
        }
        block.copy_from_slice(&state.to_be_bytes());
    }
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// PRESENT-80 — Bogdanov et al. CHES 2007, Appendix I.
    /// Key=00…00, PT=00…00 → CT=5579C1387B228445.
    #[test]
    fn present80_zero_zero() {
        let key = [0u8; 10];
        let mut block = [0u8; 8];
        let c = Present80::new(&key);
        c.encrypt_block(&mut block);
        assert_eq!(block, [0x55, 0x79, 0xc1, 0x38, 0x7b, 0x22, 0x84, 0x45]);
        c.decrypt_block(&mut block);
        assert_eq!(block, [0u8; 8]);
    }

    /// PRESENT-80 — paper Appendix I.
    /// Key=FF…FF, PT=FF…FF → CT=3333DCD3213210D2.
    #[test]
    fn present80_ones_ones() {
        let key = [0xFFu8; 10];
        let mut block = [0xFFu8; 8];
        let c = Present80::new(&key);
        c.encrypt_block(&mut block);
        assert_eq!(block, [0x33, 0x33, 0xdc, 0xd3, 0x21, 0x32, 0x10, 0xd2]);
        c.decrypt_block(&mut block);
        assert_eq!(block, [0xFFu8; 8]);
    }

    /// PRESENT-128 — paper Appendix I.
    /// Key=00…00, PT=00…00 → CT=96DB702A2E6900AF.
    #[test]
    fn present128_zero_zero() {
        let key = [0u8; 16];
        let mut block = [0u8; 8];
        let c = Present128::new(&key);
        c.encrypt_block(&mut block);
        assert_eq!(block, [0x96, 0xdb, 0x70, 0x2a, 0x2e, 0x69, 0x00, 0xaf]);
        c.decrypt_block(&mut block);
        assert_eq!(block, [0u8; 8]);
    }

    /// PRESENT-128 — paper Appendix I.
    /// The original task description quoted `13238c710272a5d8` for
    /// `Key=FF…FF / PT=FF…FF`, but cross-checking against the paper's
    /// Appendix I and an independent Python port of the spec shows
    /// that `13238c710272a5d8` is actually the ciphertext for
    /// `Key=FF…FF / PT=00…00`.  The correct `FF/FF` ciphertext
    /// (also derivable from the spec) is `628D9FBD4218E5B4`.  We test
    /// both vectors to nail down the implementation in two independent
    /// places.
    #[test]
    fn present128_ones_zeros_and_ones_ones() {
        let key = [0xFFu8; 16];

        // FF/00
        let c = Present128::new(&key);
        let mut block = [0u8; 8];
        c.encrypt_block(&mut block);
        assert_eq!(block, [0x13, 0x23, 0x8c, 0x71, 0x02, 0x72, 0xa5, 0xd8]);
        c.decrypt_block(&mut block);
        assert_eq!(block, [0u8; 8]);

        // FF/FF
        let mut block = [0xFFu8; 8];
        c.encrypt_block(&mut block);
        assert_eq!(block, [0x62, 0x8d, 0x9f, 0xbd, 0x42, 0x18, 0xe5, 0xb4]);
        c.decrypt_block(&mut block);
        assert_eq!(block, [0xFFu8; 8]);
    }

    /// Round-trip across a sweep of keys and plaintexts.
    #[test]
    fn present_round_trip() {
        let key10 = [0x42u8; 10];
        let key16 = [0x77u8; 16];

        let c80 = Present80::new(&key10);
        let mut blk = [0xAAu8; 8];
        let orig = blk;
        c80.encrypt_block(&mut blk);
        assert_ne!(blk, orig);
        c80.decrypt_block(&mut blk);
        assert_eq!(blk, orig);

        let c128 = Present128::new(&key16);
        let mut blk = [0x5Au8; 8];
        let orig = blk;
        c128.encrypt_block(&mut blk);
        assert_ne!(blk, orig);
        c128.decrypt_block(&mut blk);
        assert_eq!(blk, orig);
    }

    /// Sanity: the P-layer is an involution-free permutation, so
    /// `p_layer_inv(p_layer(x)) == x`.
    #[test]
    fn present_p_layer_round_trip() {
        for x in [0u64, 1, 0xDEAD_BEEF_CAFE_BABE, !0] {
            assert_eq!(p_layer_inv(p_layer(x)), x);
        }
    }
}
