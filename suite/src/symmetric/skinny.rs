//! **SKINNY** — lightweight tweakable block cipher family (Beierle
//! et al., CRYPTO 2016, [eprint 2016/660]).
//!
//! SKINNY is a substitution-permutation network on a 4×4 array of
//! `s`-bit cells (`s = 4` or `s = 8`).  Each round applies five layers:
//!
//! 1. **SubCells**  — independent S-box on every cell.
//! 2. **AddConstants** — XOR a 6-bit LFSR-generated round constant
//!    into cells `(0,0)`, `(1,0)` and the fixed value `0x2` into
//!    cell `(2,0)`.
//! 3. **AddRoundTweakey** — XOR the first two rows of every active
//!    tweakey word into the top two rows of the state.
//! 4. **ShiftRows** — rotate row `i` to the right by `i` cells.
//! 5. **MixColumns** — multiply each column by a sparse binary matrix
//!
//!    ```text
//!        M = ⎡1 0 1 1⎤    →   (a,b,c,d) ↦ (a⊕c⊕d, a, b⊕c, a⊕c)
//!            ⎢1 0 0 0⎥
//!            ⎢0 1 1 0⎥
//!            ⎣1 0 1 0⎦
//!    ```
//!
//! The "tweakey" word(s) are permuted by a fixed cell permutation
//! between rounds; in the `TKz` variant the second and third tweakey
//! words are also updated by 4- or 8-bit LFSRs.
//!
//! ## Variants implemented
//!
//! | Name              | Block | Tweakey | Rounds | Cell |
//! |-------------------|-------|---------|--------|------|
//! | [`Skinny64_128`]  | 64 b  | 128 b   | 36     | 4 b  |
//! | [`Skinny128_128`] | 128 b | 128 b   | 40     | 8 b  |
//!
//! For this implementation we follow the paper's "key-only" usage:
//! the supplied 128-bit input is treated as the full tweakey, so
//! `Skinny128_128` is TK1 (`z = 1`) and `Skinny64_128` is TK2
//! (`z = 2`) with no separate tweak parameter.
//!
//! ## Byte / cell conventions
//!
//! State and tweakey are loaded **row-wise**: byte 0 carries cells
//! `(0,0)` (high nibble) and `(0,1)` (low nibble) for the nibble
//! variant, or cell `(0,0)` for the byte variant; byte 1 carries
//! `(0,2)`/`(0,3)` or `(0,1)`, etc.  This is the convention from the
//! paper's Appendix B test vectors and the reference C code by
//! `rweather/skinny-c`.
//!
//! ## Security note
//!
//! SKINNY is a peer-reviewed academic design with substantial public
//! analysis; no practical break is known for the recommended round
//! counts.  Its primary use cases are constrained-hardware,
//! authenticated encryption (SKINNY-AEAD/Hash, NIST LWC finalist
//! Romulus) and as a building block for tweakable modes.  Prefer
//! AES-GCM or ChaCha20-Poly1305 for general-purpose software.

#![allow(non_camel_case_types)]

// ── 4-bit S-box (S4) and inverse ─────────────────────────────────────

const S4: [u8; 16] = [
    0xc, 0x6, 0x9, 0x0, 0x1, 0xa, 0x2, 0xb, 0x3, 0x8, 0x5, 0xd, 0x4, 0xe, 0x7, 0xf,
];
const S4_INV: [u8; 16] = [
    0x3, 0x4, 0x6, 0x8, 0xc, 0xa, 0x1, 0xe, 0x9, 0x2, 0x5, 0x7, 0x0, 0xb, 0xd, 0xf,
];

// ── 8-bit S-box (S8) and inverse — paper Appendix A ──────────────────

const S8: [u8; 256] = [
    0x65, 0x4c, 0x6a, 0x42, 0x4b, 0x63, 0x43, 0x6b, 0x55, 0x75, 0x5a, 0x7a, 0x53, 0x73, 0x5b, 0x7b,
    0x35, 0x8c, 0x3a, 0x81, 0x89, 0x33, 0x80, 0x3b, 0x95, 0x25, 0x98, 0x2a, 0x90, 0x23, 0x99, 0x2b,
    0xe5, 0xcc, 0xe8, 0xc1, 0xc9, 0xe0, 0xc0, 0xe9, 0xd5, 0xf5, 0xd8, 0xf8, 0xd0, 0xf0, 0xd9, 0xf9,
    0xa5, 0x1c, 0xa8, 0x12, 0x1b, 0xa0, 0x13, 0xa9, 0x05, 0xb5, 0x0a, 0xb8, 0x03, 0xb0, 0x0b, 0xb9,
    0x32, 0x88, 0x3c, 0x85, 0x8d, 0x34, 0x84, 0x3d, 0x91, 0x22, 0x9c, 0x2c, 0x94, 0x24, 0x9d, 0x2d,
    0x62, 0x4a, 0x6c, 0x45, 0x4d, 0x64, 0x44, 0x6d, 0x52, 0x72, 0x5c, 0x7c, 0x54, 0x74, 0x5d, 0x7d,
    0xa1, 0x1a, 0xac, 0x15, 0x1d, 0xa4, 0x14, 0xad, 0x02, 0xb1, 0x0c, 0xbc, 0x04, 0xb4, 0x0d, 0xbd,
    0xe1, 0xc8, 0xec, 0xc5, 0xcd, 0xe4, 0xc4, 0xed, 0xd1, 0xf1, 0xdc, 0xfc, 0xd4, 0xf4, 0xdd, 0xfd,
    0x36, 0x8e, 0x38, 0x82, 0x8b, 0x30, 0x83, 0x39, 0x96, 0x26, 0x9a, 0x28, 0x93, 0x20, 0x9b, 0x29,
    0x66, 0x4e, 0x68, 0x41, 0x49, 0x60, 0x40, 0x69, 0x56, 0x76, 0x58, 0x78, 0x50, 0x70, 0x59, 0x79,
    0xa6, 0x1e, 0xaa, 0x11, 0x19, 0xa3, 0x10, 0xab, 0x06, 0xb6, 0x08, 0xba, 0x00, 0xb3, 0x09, 0xbb,
    0xe6, 0xce, 0xea, 0xc2, 0xcb, 0xe3, 0xc3, 0xeb, 0xd6, 0xf6, 0xda, 0xfa, 0xd3, 0xf3, 0xdb, 0xfb,
    0x31, 0x8a, 0x3e, 0x86, 0x8f, 0x37, 0x87, 0x3f, 0x92, 0x21, 0x9e, 0x2e, 0x97, 0x27, 0x9f, 0x2f,
    0x61, 0x48, 0x6e, 0x46, 0x4f, 0x67, 0x47, 0x6f, 0x51, 0x71, 0x5e, 0x7e, 0x57, 0x77, 0x5f, 0x7f,
    0xa2, 0x18, 0xae, 0x16, 0x1f, 0xa7, 0x17, 0xaf, 0x01, 0xb2, 0x0e, 0xbe, 0x07, 0xb7, 0x0f, 0xbf,
    0xe2, 0xca, 0xee, 0xc6, 0xcf, 0xe7, 0xc7, 0xef, 0xd2, 0xf2, 0xde, 0xfe, 0xd7, 0xf7, 0xdf, 0xff,
];

const S8_INV: [u8; 256] = [
    0xac, 0xe8, 0x68, 0x3c, 0x6c, 0x38, 0xa8, 0xec, 0xaa, 0xae, 0x3a, 0x3e, 0x6a, 0x6e, 0xea, 0xee,
    0xa6, 0xa3, 0x33, 0x36, 0x66, 0x63, 0xe3, 0xe6, 0xe1, 0xa4, 0x61, 0x34, 0x31, 0x64, 0xa1, 0xe4,
    0x8d, 0xc9, 0x49, 0x1d, 0x4d, 0x19, 0x89, 0xcd, 0x8b, 0x8f, 0x1b, 0x1f, 0x4b, 0x4f, 0xcb, 0xcf,
    0x85, 0xc0, 0x40, 0x15, 0x45, 0x10, 0x80, 0xc5, 0x82, 0x87, 0x12, 0x17, 0x42, 0x47, 0xc2, 0xc7,
    0x96, 0x93, 0x03, 0x06, 0x56, 0x53, 0xd3, 0xd6, 0xd1, 0x94, 0x51, 0x04, 0x01, 0x54, 0x91, 0xd4,
    0x9c, 0xd8, 0x58, 0x0c, 0x5c, 0x08, 0x98, 0xdc, 0x9a, 0x9e, 0x0a, 0x0e, 0x5a, 0x5e, 0xda, 0xde,
    0x95, 0xd0, 0x50, 0x05, 0x55, 0x00, 0x90, 0xd5, 0x92, 0x97, 0x02, 0x07, 0x52, 0x57, 0xd2, 0xd7,
    0x9d, 0xd9, 0x59, 0x0d, 0x5d, 0x09, 0x99, 0xdd, 0x9b, 0x9f, 0x0b, 0x0f, 0x5b, 0x5f, 0xdb, 0xdf,
    0x16, 0x13, 0x83, 0x86, 0x46, 0x43, 0xc3, 0xc6, 0x41, 0x14, 0xc1, 0x84, 0x11, 0x44, 0x81, 0xc4,
    0x1c, 0x48, 0xc8, 0x8c, 0x4c, 0x18, 0x88, 0xcc, 0x1a, 0x1e, 0x8a, 0x8e, 0x4a, 0x4e, 0xca, 0xce,
    0x35, 0x60, 0xe0, 0xa5, 0x65, 0x30, 0xa0, 0xe5, 0x32, 0x37, 0xa2, 0xa7, 0x62, 0x67, 0xe2, 0xe7,
    0x3d, 0x69, 0xe9, 0xad, 0x6d, 0x39, 0xa9, 0xed, 0x3b, 0x3f, 0xab, 0xaf, 0x6b, 0x6f, 0xeb, 0xef,
    0x26, 0x23, 0xb3, 0xb6, 0x76, 0x73, 0xf3, 0xf6, 0x71, 0x24, 0xf1, 0xb4, 0x21, 0x74, 0xb1, 0xf4,
    0x2c, 0x78, 0xf8, 0xbc, 0x7c, 0x28, 0xb8, 0xfc, 0x2a, 0x2e, 0xba, 0xbe, 0x7a, 0x7e, 0xfa, 0xfe,
    0x25, 0x70, 0xf0, 0xb5, 0x75, 0x20, 0xb0, 0xf5, 0x22, 0x27, 0xb2, 0xb7, 0x72, 0x77, 0xf2, 0xf7,
    0x2d, 0x79, 0xf9, 0xbd, 0x7d, 0x29, 0xb9, 0xfd, 0x2b, 0x2f, 0xbb, 0xbf, 0x7b, 0x7f, 0xfb, 0xff,
];

// ── Tweakey cell permutation P_T ─────────────────────────────────────

const P_T: [usize; 16] = [9, 15, 8, 13, 10, 14, 12, 11, 0, 1, 2, 3, 4, 5, 6, 7];

// ── 6-bit LFSR for round constants ───────────────────────────────────
//
//      rc ← ((rc << 1) ⊕ (rc>>5) ⊕ (rc>>4) ⊕ 1) & 0x3F
//
// starting from `rc = 0`.  Output sequence is `1, 3, 7, 0xF, …`.

#[inline]
fn next_rc(rc: u8) -> u8 {
    ((rc << 1) ^ ((rc >> 5) & 1) ^ ((rc >> 4) & 1) ^ 1) & 0x3F
}

// ── 4-bit cell LFSRs for tweakey update ──────────────────────────────
//
// LFSR2 (TK2):  (x3 x2 x1 x0) → (x2 x1 x0 x3⊕x2)
//
// LFSR3 (TK3) is unused here but defined for completeness in comments.

#[inline]
fn lfsr2_4(x: u8) -> u8 {
    let top = (x >> 3) & 1;
    let next = (x >> 2) & 1;
    ((x << 1) & 0xF) | (top ^ next)
}

// ── Common 16-cell state helpers ─────────────────────────────────────
//
// We work on 16-cell arrays for both variants and let the caller
// pack/unpack against the original byte buffer.

#[inline]
fn shift_rows(state: &mut [u8; 16]) {
    // row i rotated right by i cells: new[row, col] = old[row, (col - row) mod 4]
    let s = *state;
    // row 0 unchanged
    state[4] = s[7];
    state[5] = s[4];
    state[6] = s[5];
    state[7] = s[6];
    state[8] = s[10];
    state[9] = s[11];
    state[10] = s[8];
    state[11] = s[9];
    state[12] = s[13];
    state[13] = s[14];
    state[14] = s[15];
    state[15] = s[12];
}

#[inline]
fn inv_shift_rows(state: &mut [u8; 16]) {
    let s = *state;
    state[4] = s[5];
    state[5] = s[6];
    state[6] = s[7];
    state[7] = s[4];
    state[8] = s[10];
    state[9] = s[11];
    state[10] = s[8];
    state[11] = s[9];
    state[12] = s[15];
    state[13] = s[12];
    state[14] = s[13];
    state[15] = s[14];
}

#[inline]
fn mix_columns(state: &mut [u8; 16]) {
    for col in 0..4 {
        let a = state[col];
        let b = state[4 + col];
        let c = state[8 + col];
        let d = state[12 + col];
        state[col] = a ^ c ^ d;
        state[4 + col] = a;
        state[8 + col] = b ^ c;
        state[12 + col] = a ^ c;
    }
}

#[inline]
fn inv_mix_columns(state: &mut [u8; 16]) {
    // Inverse of M:
    //
    // Given (a',b',c',d') = (a⊕c⊕d, a, b⊕c, a⊕c) we solve
    //
    //     a = b'
    //     c = b' ⊕ d'
    //     b = c' ⊕ b' ⊕ d'
    //     d = a' ⊕ d'
    for col in 0..4 {
        let ap = state[col];
        let bp = state[4 + col];
        let cp = state[8 + col];
        let dp = state[12 + col];
        state[col] = bp;
        state[4 + col] = cp ^ bp ^ dp;
        state[8 + col] = bp ^ dp;
        state[12 + col] = ap ^ dp;
    }
}

// ── 4-bit cell pack/unpack ───────────────────────────────────────────

fn bytes_to_nibbles(bytes: &[u8; 8]) -> [u8; 16] {
    let mut s = [0u8; 16];
    for i in 0..8 {
        s[2 * i] = bytes[i] >> 4;
        s[2 * i + 1] = bytes[i] & 0xF;
    }
    s
}

fn nibbles_to_bytes(s: &[u8; 16]) -> [u8; 8] {
    let mut out = [0u8; 8];
    for i in 0..8 {
        out[i] = (s[2 * i] << 4) | (s[2 * i + 1] & 0xF);
    }
    out
}

// ── Skinny64/128 ─────────────────────────────────────────────────────

const SKINNY64_128_ROUNDS: usize = 36;

/// SKINNY with a 64-bit block and a 128-bit tweakey (TK2, 36 rounds).
#[derive(Clone, Debug)]
pub struct Skinny64_128 {
    tk1: [u8; 16],
    tk2: [u8; 16],
}

impl Skinny64_128 {
    /// Build the cipher from a 16-byte tweakey, parsed as TK1 ‖ TK2
    /// (each 8 bytes / 16 nibbles, row-wise).
    pub fn new(tweakey: &[u8; 16]) -> Self {
        let tk1_bytes: [u8; 8] = tweakey[0..8].try_into().unwrap();
        let tk2_bytes: [u8; 8] = tweakey[8..16].try_into().unwrap();
        Self {
            tk1: bytes_to_nibbles(&tk1_bytes),
            tk2: bytes_to_nibbles(&tk2_bytes),
        }
    }

    pub fn encrypt_block(&self, block: &mut [u8; 8]) {
        let mut state = bytes_to_nibbles(block);
        let mut tk1 = self.tk1;
        let mut tk2 = self.tk2;
        let mut rc: u8 = 0;
        for _ in 0..SKINNY64_128_ROUNDS {
            // SubCells
            for c in state.iter_mut() {
                *c = S4[*c as usize];
            }
            // AddConstants
            rc = next_rc(rc);
            state[0] ^= rc & 0xF;
            state[4] ^= (rc >> 4) & 0x3;
            state[8] ^= 0x2;
            // AddRoundTweakey (first two rows)
            for i in 0..8 {
                state[i] ^= tk1[i] ^ tk2[i];
            }
            // Update tweakey: permute, then LFSR2 on first 2 rows of TK2.
            tk1 = permute_tk(&tk1);
            tk2 = permute_tk(&tk2);
            for i in 0..8 {
                tk2[i] = lfsr2_4(tk2[i]);
            }
            // ShiftRows + MixColumns
            shift_rows(&mut state);
            mix_columns(&mut state);
        }
        *block = nibbles_to_bytes(&state);
    }

    pub fn decrypt_block(&self, block: &mut [u8; 8]) {
        // Precompute the per-round tweakey contributions.
        let mut tk_rounds = [[0u8; 8]; SKINNY64_128_ROUNDS];
        let mut tk1 = self.tk1;
        let mut tk2 = self.tk2;
        for r in 0..SKINNY64_128_ROUNDS {
            for i in 0..8 {
                tk_rounds[r][i] = tk1[i] ^ tk2[i];
            }
            tk1 = permute_tk(&tk1);
            tk2 = permute_tk(&tk2);
            for i in 0..8 {
                tk2[i] = lfsr2_4(tk2[i]);
            }
        }
        // Precompute round constants.
        let mut rcs = [0u8; SKINNY64_128_ROUNDS];
        let mut rc: u8 = 0;
        for r in rcs.iter_mut() {
            rc = next_rc(rc);
            *r = rc;
        }
        let mut state = bytes_to_nibbles(block);
        for r in (0..SKINNY64_128_ROUNDS).rev() {
            inv_mix_columns(&mut state);
            inv_shift_rows(&mut state);
            for i in 0..8 {
                state[i] ^= tk_rounds[r][i];
            }
            let rc = rcs[r];
            state[0] ^= rc & 0xF;
            state[4] ^= (rc >> 4) & 0x3;
            state[8] ^= 0x2;
            for c in state.iter_mut() {
                *c = S4_INV[*c as usize];
            }
        }
        *block = nibbles_to_bytes(&state);
    }
}

// ── Skinny128/128 ────────────────────────────────────────────────────

const SKINNY128_128_ROUNDS: usize = 40;

/// SKINNY with a 128-bit block and a 128-bit tweakey (TK1, 40 rounds).
#[derive(Clone, Debug)]
pub struct Skinny128_128 {
    tk1: [u8; 16],
}

impl Skinny128_128 {
    /// Build the cipher from a 16-byte tweakey (treated as TK1).
    pub fn new(tweakey: &[u8; 16]) -> Self {
        Self { tk1: *tweakey }
    }

    pub fn encrypt_block(&self, block: &mut [u8; 16]) {
        let mut state = *block;
        let mut tk1 = self.tk1;
        let mut rc: u8 = 0;
        for _ in 0..SKINNY128_128_ROUNDS {
            for c in state.iter_mut() {
                *c = S8[*c as usize];
            }
            rc = next_rc(rc);
            state[0] ^= rc & 0xF;
            state[4] ^= (rc >> 4) & 0x3;
            state[8] ^= 0x2;
            for i in 0..8 {
                state[i] ^= tk1[i];
            }
            tk1 = permute_tk(&tk1);
            shift_rows(&mut state);
            mix_columns(&mut state);
        }
        *block = state;
    }

    pub fn decrypt_block(&self, block: &mut [u8; 16]) {
        let mut tk_rounds = [[0u8; 8]; SKINNY128_128_ROUNDS];
        let mut tk1 = self.tk1;
        for r in 0..SKINNY128_128_ROUNDS {
            tk_rounds[r][..8].copy_from_slice(&tk1[..8]);
            tk1 = permute_tk(&tk1);
        }
        let mut rcs = [0u8; SKINNY128_128_ROUNDS];
        let mut rc: u8 = 0;
        for r in rcs.iter_mut() {
            rc = next_rc(rc);
            *r = rc;
        }
        let mut state = *block;
        for r in (0..SKINNY128_128_ROUNDS).rev() {
            inv_mix_columns(&mut state);
            inv_shift_rows(&mut state);
            for i in 0..8 {
                state[i] ^= tk_rounds[r][i];
            }
            let rc = rcs[r];
            state[0] ^= rc & 0xF;
            state[4] ^= (rc >> 4) & 0x3;
            state[8] ^= 0x2;
            for c in state.iter_mut() {
                *c = S8_INV[*c as usize];
            }
        }
        *block = state;
    }
}

// ── Tweakey permutation helper ───────────────────────────────────────

#[inline]
fn permute_tk(tk: &[u8; 16]) -> [u8; 16] {
    let mut out = [0u8; 16];
    for i in 0..16 {
        out[i] = tk[P_T[i]];
    }
    out
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// SKINNY-64/128 paper test vector (Appendix B):
    ///
    /// - tweakey  = `9eb93640d088da63 76a39d1c8bea71e1`
    /// - plaintext  = `cf16cfe8fd0f98aa`
    /// - ciphertext = `6ceda1f43de92b9e`
    #[test]
    fn skinny64_128_paper_vector() {
        let tweakey = [
            0x9e, 0xb9, 0x36, 0x40, 0xd0, 0x88, 0xda, 0x63, 0x76, 0xa3, 0x9d, 0x1c, 0x8b, 0xea,
            0x71, 0xe1,
        ];
        let pt = [0xcf, 0x16, 0xcf, 0xe8, 0xfd, 0x0f, 0x98, 0xaa];
        let expected = [0x6c, 0xed, 0xa1, 0xf4, 0x3d, 0xe9, 0x2b, 0x9e];

        let c = Skinny64_128::new(&tweakey);
        let mut block = pt;
        c.encrypt_block(&mut block);
        assert_eq!(block, expected, "Skinny-64/128 encrypt");
        c.decrypt_block(&mut block);
        assert_eq!(block, pt, "Skinny-64/128 decrypt");
    }

    /// SKINNY-128/128 paper test vector (Appendix B):
    ///
    /// - tweakey  = `4f55cfb0520cac52 fd92c15f37073e93`
    /// - plaintext  = `f20adb0eb08b648a 3b2eeed1f0adda14`
    /// - ciphertext = `22ff30d498ea62d7 e45b476e33675b74`
    #[test]
    fn skinny128_128_paper_vector() {
        let tweakey = [
            0x4f, 0x55, 0xcf, 0xb0, 0x52, 0x0c, 0xac, 0x52, 0xfd, 0x92, 0xc1, 0x5f, 0x37, 0x07,
            0x3e, 0x93,
        ];
        let pt = [
            0xf2, 0x0a, 0xdb, 0x0e, 0xb0, 0x8b, 0x64, 0x8a, 0x3b, 0x2e, 0xee, 0xd1, 0xf0, 0xad,
            0xda, 0x14,
        ];
        let expected = [
            0x22, 0xff, 0x30, 0xd4, 0x98, 0xea, 0x62, 0xd7, 0xe4, 0x5b, 0x47, 0x6e, 0x33, 0x67,
            0x5b, 0x74,
        ];

        let c = Skinny128_128::new(&tweakey);
        let mut block = pt;
        c.encrypt_block(&mut block);
        assert_eq!(block, expected, "Skinny-128/128 encrypt");
        c.decrypt_block(&mut block);
        assert_eq!(block, pt, "Skinny-128/128 decrypt");
    }

    /// SKINNY-64-64 (32-round, TK1-only) paper test vector — packed
    /// into the 64/128 API with a duplicated key so that TK2 cancels
    /// itself in pairs of rounds isn't possible, but we can still
    /// sanity-check the 64-bit code path on a second independent input.
    #[test]
    fn skinny64_128_round_trip_random() {
        let tweakey = [0x42u8; 16];
        let c = Skinny64_128::new(&tweakey);
        let mut block = [0xAAu8; 8];
        let orig = block;
        c.encrypt_block(&mut block);
        assert_ne!(block, orig, "Skinny-64/128 not identity");
        c.decrypt_block(&mut block);
        assert_eq!(block, orig, "Skinny-64/128 round trip");
    }

    #[test]
    fn skinny128_128_round_trip_random() {
        let tweakey = [0x77u8; 16];
        let c = Skinny128_128::new(&tweakey);
        let mut block = [0xBBu8; 16];
        let orig = block;
        c.encrypt_block(&mut block);
        assert_ne!(block, orig, "Skinny-128/128 not identity");
        c.decrypt_block(&mut block);
        assert_eq!(block, orig, "Skinny-128/128 round trip");
    }

    #[test]
    fn skinny_zero_key_not_identity() {
        let c = Skinny128_128::new(&[0u8; 16]);
        let mut block = [0u8; 16];
        c.encrypt_block(&mut block);
        assert_ne!(block, [0u8; 16]);
    }
}
