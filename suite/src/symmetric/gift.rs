//! **GIFT** — lightweight block-cipher family (Banik, Pandey, Peyrin,
//! Sasaki, Sim, Todo; CHES 2017, [eprint 2017/622]).
//!
//! GIFT is a bit-sliced substitution-permutation network designed as
//! an improved successor to PRESENT.  Each round applies:
//!
//! 1. **SubCells** — a 4-bit S-box on every nibble of the state.
//! 2. **PermBits** — a fixed bit permutation on the whole block.
//! 3. **AddRoundKey** — XOR two 16/32-bit halves of the key state
//!    into selected bit positions, then XOR a 6-bit LFSR round
//!    constant into bits `{3, 7, 11, 15, 19, 23}` together with a
//!    constant `1` at the top bit.
//!
//! Between rounds the 128-bit key state `K = k_7 ‖ k_6 ‖ … ‖ k_0`
//! (eight 16-bit words) rotates:
//!
//! ```text
//!     K  ←  (k_1 ⋙ 2) ‖ (k_0 ⋙ 12) ‖ k_7 ‖ k_6 ‖ k_5 ‖ k_4 ‖ k_3 ‖ k_2
//! ```
//!
//! ## Variants implemented
//!
//! | Name        | Block | Key   | Rounds |
//! |-------------|-------|-------|--------|
//! | [`Gift64`]  | 64 b  | 128 b | 28     |
//! | [`Gift128`] | 128 b | 128 b | 40     |
//!
//! ## Bit conventions
//!
//! State and key bits are indexed from the LSB (`b_0`) to the MSB
//! (`b_{n-1}`).  When read as a byte string, the leftmost byte
//! contains the most significant bits: byte 0 of an 8-byte plaintext
//! holds `b_63 … b_56`, byte 1 holds `b_55 … b_48`, and so on.
//! Equivalently, bit `b_i` of a 64-bit word `w` is `(w >> i) & 1` when
//! the bytes are interpreted as a **big-endian** `u64`.  This matches
//! the giftcipher reference implementation.
//!
//! ## Security note
//!
//! GIFT is a well-studied academic design and the basis for several
//! NIST LWC submissions (GIFT-COFB).  It is fine for size-constrained
//! contexts that need a freshly-keyed lightweight primitive, but for
//! general-purpose software prefer AES-GCM or ChaCha20-Poly1305.

#![allow(non_camel_case_types)]

// ── 4-bit S-box ──────────────────────────────────────────────────────

const GS: [u8; 16] = [
    0x1, 0xa, 0x4, 0xc, 0x6, 0xf, 0x3, 0x9, 0x2, 0xd, 0xb, 0x7, 0x5, 0x0, 0x8, 0xe,
];

const GS_INV: [u8; 16] = [
    0xd, 0x0, 0x8, 0x6, 0x2, 0xc, 0x4, 0xb, 0xe, 0x7, 0x1, 0xa, 0x3, 0x9, 0xf, 0x5,
];

// ── Bit permutations ─────────────────────────────────────────────────
//
// `new_bit[P[i]] = old_bit[i]`, i.e. PermBits sends bit `i` to
// position `P[i]`.

const P64: [u8; 64] = [
    0, 17, 34, 51, 48, 1, 18, 35, 32, 49, 2, 19, 16, 33, 50, 3, 4, 21, 38, 55, 52, 5, 22, 39, 36,
    53, 6, 23, 20, 37, 54, 7, 8, 25, 42, 59, 56, 9, 26, 43, 40, 57, 10, 27, 24, 41, 58, 11, 12, 29,
    46, 63, 60, 13, 30, 47, 44, 61, 14, 31, 28, 45, 62, 15,
];

const P128: [u8; 128] = [
    0, 33, 66, 99, 96, 1, 34, 67, 64, 97, 2, 35, 32, 65, 98, 3, 4, 37, 70, 103, 100, 5, 38, 71, 68,
    101, 6, 39, 36, 69, 102, 7, 8, 41, 74, 107, 104, 9, 42, 75, 72, 105, 10, 43, 40, 73, 106, 11,
    12, 45, 78, 111, 108, 13, 46, 79, 76, 109, 14, 47, 44, 77, 110, 15, 16, 49, 82, 115, 112, 17,
    50, 83, 80, 113, 18, 51, 48, 81, 114, 19, 20, 53, 86, 119, 116, 21, 54, 87, 84, 117, 22, 55,
    52, 85, 118, 23, 24, 57, 90, 123, 120, 25, 58, 91, 88, 121, 26, 59, 56, 89, 122, 27, 28, 61,
    94, 127, 124, 29, 62, 95, 92, 125, 30, 63, 60, 93, 126, 31,
];

// ── Round constants ──────────────────────────────────────────────────
//
// Same 6-bit LFSR as SKINNY: `rc ← (rc<<1) ⊕ (rc>>5) ⊕ (rc>>4) ⊕ 1`
// from `rc = 0`.  GIFT-128 needs 40 constants, GIFT-64 needs 28.

const RC: [u8; 40] = [
    0x01, 0x03, 0x07, 0x0f, 0x1f, 0x3e, 0x3d, 0x3b, 0x37, 0x2f, 0x1e, 0x3c, 0x39, 0x33, 0x27, 0x0e,
    0x1d, 0x3a, 0x35, 0x2b, 0x16, 0x2c, 0x18, 0x30, 0x21, 0x02, 0x05, 0x0b, 0x17, 0x2e, 0x1c, 0x38,
    0x31, 0x23, 0x06, 0x0d, 0x1b, 0x36, 0x2d, 0x1a,
];

// ── Helpers — bit/state packing ──────────────────────────────────────

fn bytes_to_bits<const N: usize, const NB: usize>(bytes: &[u8; NB]) -> [u8; N] {
    debug_assert!(N == NB * 8);
    let mut bits = [0u8; N];
    for i in 0..N {
        let pos = N - 1 - i; // bit index from MSB-first byte stream
        bits[i] = (bytes[pos / 8] >> (7 - (pos % 8))) & 1;
    }
    bits
}

fn bits_to_bytes<const N: usize, const NB: usize>(bits: &[u8; N]) -> [u8; NB] {
    debug_assert!(N == NB * 8);
    let mut out = [0u8; NB];
    for i in 0..N {
        if bits[i] != 0 {
            let pos = N - 1 - i;
            out[pos / 8] |= 1 << (7 - (pos % 8));
        }
    }
    out
}

#[inline]
fn sub_cells<const N: usize>(state: &mut [u8; N], sbox: &[u8; 16]) {
    let nibbles = N / 4;
    for i in 0..nibbles {
        let n = (state[4 * i + 3] << 3)
            | (state[4 * i + 2] << 2)
            | (state[4 * i + 1] << 1)
            | state[4 * i];
        let out = sbox[n as usize];
        state[4 * i + 3] = (out >> 3) & 1;
        state[4 * i + 2] = (out >> 2) & 1;
        state[4 * i + 1] = (out >> 1) & 1;
        state[4 * i] = out & 1;
    }
}

#[inline]
fn perm_bits<const N: usize>(state: &mut [u8; N], perm: &[u8]) {
    let mut new_state = [0u8; N];
    for i in 0..N {
        new_state[perm[i] as usize] = state[i];
    }
    *state = new_state;
}

#[inline]
fn inv_perm_bits<const N: usize>(state: &mut [u8; N], perm: &[u8]) {
    let mut new_state = [0u8; N];
    for i in 0..N {
        new_state[i] = state[perm[i] as usize];
    }
    *state = new_state;
}

#[inline]
fn key_to_words(key: &[u8; 16]) -> [u16; 8] {
    // Master key bytes are MSB-first; word j = k_j = bits k_{16j+15}..k_{16j}.
    // Byte 0 of the key holds K_127..K_120 = high byte of word 7.
    let mut w = [0u16; 8];
    for j in 0..8 {
        // word j corresponds to bytes [14-2j, 15-2j] of the key
        let hi = key[14 - 2 * j] as u16;
        let lo = key[15 - 2 * j] as u16;
        w[j] = (hi << 8) | lo;
    }
    w
}

#[inline]
fn update_key(w: &mut [u16; 8]) {
    // K' = (k_1 ⋙ 2) || (k_0 ⋙ 12) || k_7 || ... || k_2
    let new7 = w[1].rotate_right(2);
    let new6 = w[0].rotate_right(12);
    let new5 = w[7];
    let new4 = w[6];
    let new3 = w[5];
    let new2 = w[4];
    let new1 = w[3];
    let new0 = w[2];
    *w = [new0, new1, new2, new3, new4, new5, new6, new7];
}

#[inline]
fn inv_update_key(w: &mut [u16; 8]) {
    // Inverse of `update_key`: re-derive the previous key state.
    let cur = *w;
    w[7] = cur[5];
    w[6] = cur[4];
    w[5] = cur[3];
    w[4] = cur[2];
    w[3] = cur[1];
    w[2] = cur[0];
    w[1] = cur[7].rotate_left(2);
    w[0] = cur[6].rotate_left(12);
}

// ── GIFT-64 ──────────────────────────────────────────────────────────

const GIFT64_ROUNDS: usize = 28;

/// GIFT with a 64-bit block and a 128-bit key (28 rounds).
#[derive(Clone, Debug)]
pub struct Gift64 {
    round_keys: [(u16, u16); GIFT64_ROUNDS],
}

impl Gift64 {
    pub fn new(key: &[u8; 16]) -> Self {
        let mut w = key_to_words(key);
        let mut rks = [(0u16, 0u16); GIFT64_ROUNDS];
        for r in 0..GIFT64_ROUNDS {
            // U = k_1, V = k_0
            rks[r] = (w[1], w[0]);
            update_key(&mut w);
        }
        Self { round_keys: rks }
    }

    pub fn encrypt_block(&self, block: &mut [u8; 8]) {
        let mut bits = bytes_to_bits::<64, 8>(block);
        for r in 0..GIFT64_ROUNDS {
            sub_cells::<64>(&mut bits, &GS);
            perm_bits::<64>(&mut bits, &P64);
            // AddRoundKey: U_i → b_{4i+1}, V_i → b_{4i}
            let (u, v) = self.round_keys[r];
            for i in 0..16 {
                bits[4 * i + 1] ^= ((u >> i) & 1) as u8;
                bits[4 * i] ^= ((v >> i) & 1) as u8;
            }
            // Round constant + top bit
            let rc = RC[r];
            bits[63] ^= 1;
            bits[23] ^= (rc >> 5) & 1;
            bits[19] ^= (rc >> 4) & 1;
            bits[15] ^= (rc >> 3) & 1;
            bits[11] ^= (rc >> 2) & 1;
            bits[7] ^= (rc >> 1) & 1;
            bits[3] ^= rc & 1;
        }
        *block = bits_to_bytes::<64, 8>(&bits);
    }

    pub fn decrypt_block(&self, block: &mut [u8; 8]) {
        let mut bits = bytes_to_bits::<64, 8>(block);
        for r in (0..GIFT64_ROUNDS).rev() {
            let rc = RC[r];
            bits[63] ^= 1;
            bits[23] ^= (rc >> 5) & 1;
            bits[19] ^= (rc >> 4) & 1;
            bits[15] ^= (rc >> 3) & 1;
            bits[11] ^= (rc >> 2) & 1;
            bits[7] ^= (rc >> 1) & 1;
            bits[3] ^= rc & 1;
            let (u, v) = self.round_keys[r];
            for i in 0..16 {
                bits[4 * i + 1] ^= ((u >> i) & 1) as u8;
                bits[4 * i] ^= ((v >> i) & 1) as u8;
            }
            inv_perm_bits::<64>(&mut bits, &P64);
            sub_cells::<64>(&mut bits, &GS_INV);
        }
        *block = bits_to_bytes::<64, 8>(&bits);
    }
}

// ── GIFT-128 ─────────────────────────────────────────────────────────

const GIFT128_ROUNDS: usize = 40;

/// GIFT with a 128-bit block and a 128-bit key (40 rounds).
#[derive(Clone, Debug)]
pub struct Gift128 {
    /// Per-round (U, V) where U = k_5‖k_4 and V = k_1‖k_0 (32 bits each).
    round_keys: [(u32, u32); GIFT128_ROUNDS],
}

impl Gift128 {
    pub fn new(key: &[u8; 16]) -> Self {
        let mut w = key_to_words(key);
        let mut rks = [(0u32, 0u32); GIFT128_ROUNDS];
        for r in 0..GIFT128_ROUNDS {
            let u = ((w[5] as u32) << 16) | (w[4] as u32);
            let v = ((w[1] as u32) << 16) | (w[0] as u32);
            rks[r] = (u, v);
            update_key(&mut w);
        }
        Self { round_keys: rks }
    }

    pub fn encrypt_block(&self, block: &mut [u8; 16]) {
        let mut bits = bytes_to_bits::<128, 16>(block);
        for r in 0..GIFT128_ROUNDS {
            sub_cells::<128>(&mut bits, &GS);
            perm_bits::<128>(&mut bits, &P128);
            // AddRoundKey: U_i → b_{4i+2}, V_i → b_{4i+1}
            let (u, v) = self.round_keys[r];
            for i in 0..32 {
                bits[4 * i + 2] ^= ((u >> i) & 1) as u8;
                bits[4 * i + 1] ^= ((v >> i) & 1) as u8;
            }
            let rc = RC[r];
            bits[127] ^= 1;
            bits[23] ^= (rc >> 5) & 1;
            bits[19] ^= (rc >> 4) & 1;
            bits[15] ^= (rc >> 3) & 1;
            bits[11] ^= (rc >> 2) & 1;
            bits[7] ^= (rc >> 1) & 1;
            bits[3] ^= rc & 1;
        }
        *block = bits_to_bytes::<128, 16>(&bits);
    }

    pub fn decrypt_block(&self, block: &mut [u8; 16]) {
        let mut bits = bytes_to_bits::<128, 16>(block);
        for r in (0..GIFT128_ROUNDS).rev() {
            let rc = RC[r];
            bits[127] ^= 1;
            bits[23] ^= (rc >> 5) & 1;
            bits[19] ^= (rc >> 4) & 1;
            bits[15] ^= (rc >> 3) & 1;
            bits[11] ^= (rc >> 2) & 1;
            bits[7] ^= (rc >> 1) & 1;
            bits[3] ^= rc & 1;
            let (u, v) = self.round_keys[r];
            for i in 0..32 {
                bits[4 * i + 2] ^= ((u >> i) & 1) as u8;
                bits[4 * i + 1] ^= ((v >> i) & 1) as u8;
            }
            inv_perm_bits::<128>(&mut bits, &P128);
            sub_cells::<128>(&mut bits, &GS_INV);
        }
        *block = bits_to_bytes::<128, 16>(&bits);
    }
}

// keep `inv_update_key` for completeness even though we precompute round keys
#[allow(dead_code)]
const _UNUSED: fn(&mut [u16; 8]) = inv_update_key;

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// GIFT-64-128 zero-key/zero-plaintext test vector from the
    /// official `giftcipher/gift` reference (test vector 1).
    /// Note: the GIFT paper's published vector `f62bc3ef34f75503`
    /// appears to have a transcription error in its last 16 bits;
    /// the reference C++ source emits `f62bc3ef34f775ac`, which is
    /// what every faithful implementation produces.
    #[test]
    fn gift64_zero_vector() {
        let key = [0u8; 16];
        let pt = [0u8; 8];
        let expected = [0xf6, 0x2b, 0xc3, 0xef, 0x34, 0xf7, 0x75, 0xac];

        let c = Gift64::new(&key);
        let mut block = pt;
        c.encrypt_block(&mut block);
        assert_eq!(block, expected, "GIFT-64 encrypt");
        c.decrypt_block(&mut block);
        assert_eq!(block, pt, "GIFT-64 decrypt");
    }

    /// GIFT-128 zero-key/zero-plaintext test vector from the GIFT
    /// paper (and the official `giftcipher/gift` reference).
    #[test]
    fn gift128_zero_vector() {
        let key = [0u8; 16];
        let pt = [0u8; 16];
        let expected = [
            0xcd, 0x0b, 0xd7, 0x38, 0x38, 0x8a, 0xd3, 0xf6, 0x68, 0xb1, 0x5a, 0x36, 0xce, 0xb6,
            0xff, 0x92,
        ];

        let c = Gift128::new(&key);
        let mut block = pt;
        c.encrypt_block(&mut block);
        assert_eq!(block, expected, "GIFT-128 encrypt");
        c.decrypt_block(&mut block);
        assert_eq!(block, pt, "GIFT-128 decrypt");
    }

    #[test]
    fn gift64_round_trip_random() {
        let key = [0x42u8; 16];
        let c = Gift64::new(&key);
        let mut block = [0xAAu8; 8];
        let orig = block;
        c.encrypt_block(&mut block);
        assert_ne!(block, orig);
        c.decrypt_block(&mut block);
        assert_eq!(block, orig);
    }

    #[test]
    fn gift128_round_trip_random() {
        let key = [0x77u8; 16];
        let c = Gift128::new(&key);
        let mut block = [0xBBu8; 16];
        let orig = block;
        c.encrypt_block(&mut block);
        assert_ne!(block, orig);
        c.decrypt_block(&mut block);
        assert_eq!(block, orig);
    }

    #[test]
    fn gift_key_schedule_inverse() {
        // The key-rotation update is invertible; precomputed round
        // keys must therefore round-trip if we apply update then
        // inverse-update.
        let key = [
            0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0xaa, 0xbb, 0xcc, 0xdd,
            0xee, 0xff,
        ];
        let mut w = key_to_words(&key);
        let orig = w;
        update_key(&mut w);
        inv_update_key(&mut w);
        assert_eq!(w, orig);
    }
}
