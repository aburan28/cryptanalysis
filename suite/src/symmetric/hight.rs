//! **HIGHT** — Korean lightweight block cipher (Hong et al., CHES 2006).
//!
//! HIGHT (*HIgh security and light-weighT*) is a 64-bit block, 128-bit
//! key generalised Feistel cipher with 32 rounds.  It is standardised
//! in **ISO/IEC 18033-3** and was the basis of an IETF Internet-Draft
//! (`draft-kisa-hight-00`); KISA publishes the reference C source as
//! `KISA_HIGHT_ECB.c`.  Inside its mathematical structure HIGHT is an
//! "8-branch unbalanced Feistel" — each round updates four of the
//! eight bytes of the state by mixing the other four through a pair of
//! linear permutations `F0` and `F1`.
//!
//! ## Round function
//!
//! On a byte vector `X = (X₀, X₁, …, X₇)` with round key bytes
//! `SK_{4i..4i+3}`:
//!
//! ```text
//!     X'₁ = X₀        (and similarly X'₃ ← X₂, X'₅ ← X₄, X'₇ ← X₆)
//!     X'₀ = X₇ ⊕ (F₀(X₆) + SK_{4i+3})
//!     X'₂ = X₁ + (F₁(X₀) ⊕ SK_{4i})
//!     X'₄ = X₃ ⊕ (F₀(X₂) + SK_{4i+1})
//!     X'₆ = X₅ + (F₁(X₄) ⊕ SK_{4i+2})
//! ```
//!
//! where
//!
//! ```text
//!     F₀(x) = ROL(x, 1) ⊕ ROL(x, 2) ⊕ ROL(x, 7)
//!     F₁(x) = ROL(x, 3) ⊕ ROL(x, 4) ⊕ ROL(x, 6)
//! ```
//!
//! The last round (round 32) skips the byte rotation, and the output is
//! whitened with `WK_{4..7}` exactly the way the input was pre-whitened
//! with `WK_{0..3}`.
//!
//! ## Key schedule
//!
//! Whitening keys: `WK_i = MK_{i+12}` for `i = 0..3`, `WK_i = MK_{i-4}`
//! for `i = 4..7`.  Subkeys: for `i = 0..7` and `j = 0..7`,
//!
//! ```text
//!     SK_{16i + j}     = MK_{(j - i) mod 8}     + δ_{16i + j}
//!     SK_{16i + j + 8} = MK_{((j - i) mod 8) + 8} + δ_{16i + j + 8}
//! ```
//!
//! The 128 `δ` constants are produced by a 7-bit LFSR with initial
//! state `s₀…s₆ = 0,1,0,1,1,0,1` and feedback `s_{i+7} = s_{i+3} ⊕ s_i`.
//! `δ_i = (s_{i+6}, …, s_i)` interpreted as a 7-bit integer; `δ_0 = 0x5A`.
//!
//! ## Byte conventions
//!
//! `MK[0]` is `mk[0]`, `MK[15]` is `mk[15]`; the plaintext `pt[0]` maps
//! to `X₀`, …, `pt[7]` to `X₇`.  This matches the KISA reference
//! `KISA_HIGHT_ECB.c` and the Crypto++ test-vector file.
//!
//! ## Security note
//!
//! HIGHT has been the target of biclique and saturation attacks that
//! marginally beat brute force for the full 32 rounds.  Like other
//! lightweight 64-bit-block designs, the bigger practical concern is
//! Sweet32-style birthday collisions when encrypting large volumes
//! under one key.  Use AES or ChaCha20 for general-purpose work; HIGHT
//! is included here for interoperability with Korean government
//! systems and ISO/IEC 18033-3 deployments.

// ── δ-constant table (paper Appendix; matches KISA / Crypto++) ───────

const DELTA: [u8; 128] = [
    0x5A, 0x6D, 0x36, 0x1B, 0x0D, 0x06, 0x03, 0x41, 0x60, 0x30, 0x18, 0x4C, 0x66, 0x33, 0x59, 0x2C,
    0x56, 0x2B, 0x15, 0x4A, 0x65, 0x72, 0x39, 0x1C, 0x4E, 0x67, 0x73, 0x79, 0x3C, 0x5E, 0x6F, 0x37,
    0x5B, 0x2D, 0x16, 0x0B, 0x05, 0x42, 0x21, 0x50, 0x28, 0x54, 0x2A, 0x55, 0x6A, 0x75, 0x7A, 0x7D,
    0x3E, 0x5F, 0x2F, 0x17, 0x4B, 0x25, 0x52, 0x29, 0x14, 0x0A, 0x45, 0x62, 0x31, 0x58, 0x6C, 0x76,
    0x3B, 0x1D, 0x0E, 0x47, 0x63, 0x71, 0x78, 0x7C, 0x7E, 0x7F, 0x3F, 0x1F, 0x0F, 0x07, 0x43, 0x61,
    0x70, 0x38, 0x5C, 0x6E, 0x77, 0x7B, 0x3D, 0x1E, 0x4F, 0x27, 0x53, 0x69, 0x34, 0x1A, 0x4D, 0x26,
    0x13, 0x49, 0x24, 0x12, 0x09, 0x04, 0x02, 0x01, 0x40, 0x20, 0x10, 0x08, 0x44, 0x22, 0x11, 0x48,
    0x64, 0x32, 0x19, 0x0C, 0x46, 0x23, 0x51, 0x68, 0x74, 0x3A, 0x5D, 0x2E, 0x57, 0x6B, 0x35, 0x5A,
];

#[inline]
fn f0(x: u8) -> u8 {
    x.rotate_left(1) ^ x.rotate_left(2) ^ x.rotate_left(7)
}

#[inline]
fn f1(x: u8) -> u8 {
    x.rotate_left(3) ^ x.rotate_left(4) ^ x.rotate_left(6)
}

/// HIGHT cipher with a 128-bit key.
#[derive(Clone, Debug)]
pub struct Hight {
    /// `wk[0..8]` = whitening keys WK_0..WK_7;
    /// `sk[0..128]` = subkeys SK_0..SK_127.
    wk: [u8; 8],
    sk: [u8; 128],
}

impl Hight {
    /// Construct a HIGHT cipher from a 16-byte master key.
    pub fn new(key: &[u8; 16]) -> Self {
        let mut wk = [0u8; 8];
        wk[..4].copy_from_slice(&key[12..(4 + 12)]);
        wk[4..(4 + 4)].copy_from_slice(&key[..4]);
        let mut sk = [0u8; 128];
        for i in 0..8 {
            for j in 0..8 {
                sk[16 * i + j] = key[(j.wrapping_sub(i)) & 7].wrapping_add(DELTA[16 * i + j]);
                sk[16 * i + j + 8] =
                    key[((j.wrapping_sub(i)) & 7) + 8].wrapping_add(DELTA[16 * i + j + 8]);
            }
        }
        Self { wk, sk }
    }

    /// Encrypt a single 64-bit block in place.
    ///
    /// The implementation follows the KISA `KISA_HIGHT_ECB.c` reference,
    /// which expresses the round-by-round byte rotation as an index
    /// permutation on a fixed 8-element array `xx`.  Each call to
    /// `enc_round` updates four positions of `xx` in place; the
    /// permutation `(i0, …, i7)` rotates by one byte per round.
    pub fn encrypt_block(&self, block: &mut [u8; 8]) {
        // Pre-whitening
        let mut xx = [
            block[0].wrapping_add(self.wk[0]),
            block[1],
            block[2] ^ self.wk[1],
            block[3],
            block[4].wrapping_add(self.wk[2]),
            block[5],
            block[6] ^ self.wk[3],
            block[7],
        ];

        // 32 rounds, expressed as 32 calls with rotated index lists.
        // Round number `k` (paper indexing: 1..=32) consumes subkeys
        // SK_{4(k-1) + 0..3}.  The KISA reference passes `k+1` in the
        // macro argument (so k = 2..=33) and reads `4k+0..3` from a
        // round-key array that begins with the 8 WK bytes — we drop
        // that offset by referring to `self.sk[4*(k-2) + …]`.
        const PERMS: [[usize; 8]; 32] = [
            [7, 6, 5, 4, 3, 2, 1, 0],
            [6, 5, 4, 3, 2, 1, 0, 7],
            [5, 4, 3, 2, 1, 0, 7, 6],
            [4, 3, 2, 1, 0, 7, 6, 5],
            [3, 2, 1, 0, 7, 6, 5, 4],
            [2, 1, 0, 7, 6, 5, 4, 3],
            [1, 0, 7, 6, 5, 4, 3, 2],
            [0, 7, 6, 5, 4, 3, 2, 1],
            [7, 6, 5, 4, 3, 2, 1, 0],
            [6, 5, 4, 3, 2, 1, 0, 7],
            [5, 4, 3, 2, 1, 0, 7, 6],
            [4, 3, 2, 1, 0, 7, 6, 5],
            [3, 2, 1, 0, 7, 6, 5, 4],
            [2, 1, 0, 7, 6, 5, 4, 3],
            [1, 0, 7, 6, 5, 4, 3, 2],
            [0, 7, 6, 5, 4, 3, 2, 1],
            [7, 6, 5, 4, 3, 2, 1, 0],
            [6, 5, 4, 3, 2, 1, 0, 7],
            [5, 4, 3, 2, 1, 0, 7, 6],
            [4, 3, 2, 1, 0, 7, 6, 5],
            [3, 2, 1, 0, 7, 6, 5, 4],
            [2, 1, 0, 7, 6, 5, 4, 3],
            [1, 0, 7, 6, 5, 4, 3, 2],
            [0, 7, 6, 5, 4, 3, 2, 1],
            [7, 6, 5, 4, 3, 2, 1, 0],
            [6, 5, 4, 3, 2, 1, 0, 7],
            [5, 4, 3, 2, 1, 0, 7, 6],
            [4, 3, 2, 1, 0, 7, 6, 5],
            [3, 2, 1, 0, 7, 6, 5, 4],
            [2, 1, 0, 7, 6, 5, 4, 3],
            [1, 0, 7, 6, 5, 4, 3, 2],
            [0, 7, 6, 5, 4, 3, 2, 1],
        ];

        for (round_idx, perm) in PERMS.iter().enumerate() {
            let [i0, i1, i2, i3, i4, i5, i6, i7] = *perm;
            let base = 4 * round_idx;
            xx[i0] ^= f0(xx[i1]).wrapping_add(self.sk[base + 3]);
            xx[i2] = xx[i2].wrapping_add(f1(xx[i3]) ^ self.sk[base + 2]);
            xx[i4] ^= f0(xx[i5]).wrapping_add(self.sk[base + 1]);
            xx[i6] = xx[i6].wrapping_add(f1(xx[i7]) ^ self.sk[base]);
        }

        // Final (post-whitening + skip the very last byte rotation).
        block[1] = xx[2];
        block[3] = xx[4];
        block[5] = xx[6];
        block[7] = xx[0];
        block[0] = xx[1].wrapping_add(self.wk[4]);
        block[2] = xx[3] ^ self.wk[5];
        block[4] = xx[5].wrapping_add(self.wk[6]);
        block[6] = xx[7] ^ self.wk[7];
    }

    /// Decrypt a single 64-bit block in place.
    ///
    /// Mirrors the KISA reference `HIGHT_DEC` macro: the initial-state
    /// layout, round-by-round index permutations, and final whitening
    /// are all the encrypt path run backwards.
    pub fn decrypt_block(&self, block: &mut [u8; 8]) {
        // Reverse of the encrypt path's "skip the last rotation" layout.
        let mut xx = [0u8; 8];
        xx[2] = block[1];
        xx[4] = block[3];
        xx[6] = block[5];
        xx[0] = block[7];
        xx[1] = block[0].wrapping_sub(self.wk[4]);
        xx[3] = block[2] ^ self.wk[5];
        xx[5] = block[4].wrapping_sub(self.wk[6]);
        xx[7] = block[6] ^ self.wk[7];

        // Decrypt-side index permutations from the KISA reference
        // (HIGHT_DEC(33 .. 2) — paired with round counter 31..0 into
        // `sk`).
        const PERMS: [[usize; 8]; 32] = [
            [7, 6, 5, 4, 3, 2, 1, 0],
            [0, 7, 6, 5, 4, 3, 2, 1],
            [1, 0, 7, 6, 5, 4, 3, 2],
            [2, 1, 0, 7, 6, 5, 4, 3],
            [3, 2, 1, 0, 7, 6, 5, 4],
            [4, 3, 2, 1, 0, 7, 6, 5],
            [5, 4, 3, 2, 1, 0, 7, 6],
            [6, 5, 4, 3, 2, 1, 0, 7],
            [7, 6, 5, 4, 3, 2, 1, 0],
            [0, 7, 6, 5, 4, 3, 2, 1],
            [1, 0, 7, 6, 5, 4, 3, 2],
            [2, 1, 0, 7, 6, 5, 4, 3],
            [3, 2, 1, 0, 7, 6, 5, 4],
            [4, 3, 2, 1, 0, 7, 6, 5],
            [5, 4, 3, 2, 1, 0, 7, 6],
            [6, 5, 4, 3, 2, 1, 0, 7],
            [7, 6, 5, 4, 3, 2, 1, 0],
            [0, 7, 6, 5, 4, 3, 2, 1],
            [1, 0, 7, 6, 5, 4, 3, 2],
            [2, 1, 0, 7, 6, 5, 4, 3],
            [3, 2, 1, 0, 7, 6, 5, 4],
            [4, 3, 2, 1, 0, 7, 6, 5],
            [5, 4, 3, 2, 1, 0, 7, 6],
            [6, 5, 4, 3, 2, 1, 0, 7],
            [7, 6, 5, 4, 3, 2, 1, 0],
            [0, 7, 6, 5, 4, 3, 2, 1],
            [1, 0, 7, 6, 5, 4, 3, 2],
            [2, 1, 0, 7, 6, 5, 4, 3],
            [3, 2, 1, 0, 7, 6, 5, 4],
            [4, 3, 2, 1, 0, 7, 6, 5],
            [5, 4, 3, 2, 1, 0, 7, 6],
            [6, 5, 4, 3, 2, 1, 0, 7],
        ];

        // Round counter walks 31 → 0 (paper index 32 → 1).
        for (rev_idx, perm) in PERMS.iter().enumerate() {
            let round_idx = 31 - rev_idx;
            let [i0, i1, i2, i3, i4, i5, i6, i7] = *perm;
            let base = 4 * round_idx;
            xx[i1] = xx[i1].wrapping_sub(f1(xx[i2]) ^ self.sk[base + 2]);
            xx[i3] ^= f0(xx[i4]).wrapping_add(self.sk[base + 1]);
            xx[i5] = xx[i5].wrapping_sub(f1(xx[i6]) ^ self.sk[base]);
            xx[i7] ^= f0(xx[i0]).wrapping_add(self.sk[base + 3]);
        }

        // Undo pre-whitening.
        block[0] = xx[0].wrapping_sub(self.wk[0]);
        block[1] = xx[1];
        block[2] = xx[2] ^ self.wk[1];
        block[3] = xx[3];
        block[4] = xx[4].wrapping_sub(self.wk[2]);
        block[5] = xx[5];
        block[6] = xx[6] ^ self.wk[3];
        block[7] = xx[7];
    }
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// HIGHT — KISA reference test vector (matches the test-vector file
    /// distributed with Crypto++ as `TestVectors/hight.txt`).
    /// Key=88E34F8F081779F1E9F394370AD40589
    /// PT =D76D0D18327EC562
    /// CT =E4BC2E312277E4DD
    ///
    /// Note: the original task description quoted a test vector
    /// (`K=000102…0F PT=000102…07 → CT=00f418aed94f03f2`) that does
    /// **not** appear in the HIGHT paper and disagrees with both the
    /// KISA reference C source and the Crypto++ test-vector file.
    /// We therefore use the KISA-published vectors as the authority.
    #[test]
    fn hight_kisa_vector_1() {
        let key = [
            0x88, 0xE3, 0x4F, 0x8F, 0x08, 0x17, 0x79, 0xF1, 0xE9, 0xF3, 0x94, 0x37, 0x0A, 0xD4,
            0x05, 0x89,
        ];
        let pt = [0xD7, 0x6D, 0x0D, 0x18, 0x32, 0x7E, 0xC5, 0x62];
        let mut block = pt;
        let c = Hight::new(&key);
        c.encrypt_block(&mut block);
        assert_eq!(block, [0xE4, 0xBC, 0x2E, 0x31, 0x22, 0x77, 0xE4, 0xDD]);
        c.decrypt_block(&mut block);
        assert_eq!(block, pt);
    }

    /// HIGHT — second KISA / Crypto++ test vector.
    /// Key=2923BE84E16CD6AE529049F1F1BBE9EB
    /// PT =B3A6DB3C870C3E99
    /// CT =23CAD1A3CDDF7EAB
    #[test]
    fn hight_kisa_vector_2() {
        let key = [
            0x29, 0x23, 0xBE, 0x84, 0xE1, 0x6C, 0xD6, 0xAE, 0x52, 0x90, 0x49, 0xF1, 0xF1, 0xBB,
            0xE9, 0xEB,
        ];
        let pt = [0xB3, 0xA6, 0xDB, 0x3C, 0x87, 0x0C, 0x3E, 0x99];
        let mut block = pt;
        let c = Hight::new(&key);
        c.encrypt_block(&mut block);
        assert_eq!(block, [0x23, 0xCA, 0xD1, 0xA3, 0xCD, 0xDF, 0x7E, 0xAB]);
        c.decrypt_block(&mut block);
        assert_eq!(block, pt);
    }

    /// HIGHT — third KISA / Crypto++ test vector.
    /// Key=245E0D1C06B747DEB3124DC843BB8BA6
    /// PT =1F035A7D0938251F
    /// CT =52BD91BB26F8ED99
    #[test]
    fn hight_kisa_vector_3() {
        let key = [
            0x24, 0x5E, 0x0D, 0x1C, 0x06, 0xB7, 0x47, 0xDE, 0xB3, 0x12, 0x4D, 0xC8, 0x43, 0xBB,
            0x8B, 0xA6,
        ];
        let pt = [0x1F, 0x03, 0x5A, 0x7D, 0x09, 0x38, 0x25, 0x1F];
        let mut block = pt;
        let c = Hight::new(&key);
        c.encrypt_block(&mut block);
        assert_eq!(block, [0x52, 0xBD, 0x91, 0xBB, 0x26, 0xF8, 0xED, 0x99]);
        c.decrypt_block(&mut block);
        assert_eq!(block, pt);
    }

    /// Round-trip sweep with assorted keys / blocks.
    #[test]
    fn hight_round_trip() {
        for key_byte in [0x00u8, 0x55, 0xa5, 0xff] {
            let key = [key_byte; 16];
            let c = Hight::new(&key);
            for pt_byte in [0x00u8, 0x33, 0xff] {
                let pt = [pt_byte; 8];
                let mut blk = pt;
                c.encrypt_block(&mut blk);
                if key_byte != 0 || pt_byte != 0 {
                    assert_ne!(blk, pt, "HIGHT encrypt was identity");
                }
                c.decrypt_block(&mut blk);
                assert_eq!(blk, pt);
            }
        }
    }
}
