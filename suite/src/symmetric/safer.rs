//! **SAFER-K-64** — *Secure And Fast Encryption Routine*, key length 64.
//!
//! Designed by **James L. Massey** at ETH Zürich in 1993.  64-bit block,
//! 64-bit key, byte-oriented substitution-permutation network.  Default
//! 6 rounds; the spec supports 6–10.  SAFER predates and influenced
//! Rijndael / AES, but the *K*-variant was found to have a weak key
//! schedule (Knudsen 1995) and was superseded by SAFER-SK and later
//! SAFER+.
//!
//! ## Security status
//!
//! - **Knudsen** (1995) showed key-schedule weaknesses in SAFER-K
//!   leading to related-key distinguishers and inspired the "SK"
//!   (strengthened key-schedule) family.
//! - **SAFER+** (1998) was an AES candidate; selected as the Bluetooth
//!   E0/E21/E22 building block (also broken in that context).
//! - Plain SAFER-K-64 is **historical** — shipped here for spec/interop
//!   study, not for production.
//!
//! ## Algorithm sketch
//!
//! - 8-byte state `(a, b, c, d, e, f, g, h)`.
//! - Per round:
//!     1. **Mixed XOR / add** with round key 1 (XOR on bytes 0,3,4,7;
//!        modular add on bytes 1,2,5,6).
//!     2. **Nonlinear layer**: bytes 0,3,4,7 → `EXP` then add round-key-2
//!        byte; bytes 1,2,5,6 → `LOG` then XOR round-key-2 byte.
//!     3. **3-level pseudo-Hadamard transform (PHT)** mixing all 8
//!        bytes, with a fixed byte permutation between levels.
//! - After the last round one more "mixed XOR / add" with the final
//!   half-key is applied (no nonlinear layer / PHT).
//!
//! `EXP[x] = 45^x mod 257` (with `45^128 ≡ 256` mapped to byte 0) and
//! `LOG[x]` is its inverse.  Note `EXP` and `LOG` are not strictly
//! mutual inverses on byte 0/1 — `EXP[0] = 1`, `LOG[1] = 0`, etc., per
//! Massey's tables.
//!
//! ## Test vector (Massey/De Moliner C reference, libtomcrypt
//! `safer_k64_test`, 6 rounds)
//!
//! ```text
//! Key       = 08 07 06 05 04 03 02 01
//! Plaintext = 01 02 03 04 05 06 07 08
//! Ciphertext= c8 f2 9c dd 87 78 3e d9
//! ```
//!
//! ## References
//!
//! - **J. L. Massey**, *SAFER K-64: A Byte-Oriented Block-Ciphering
//!   Algorithm*, FSE 1993.
//! - **R. De Moliner**, ETH Zürich reference C implementation (1995).

const SAFER_BLOCK_LEN: usize = 8;
const DEFAULT_ROUNDS: usize = 6;
/// Maximum rounds the spec permits (the strengthened variants go up to
/// 13, but plain SAFER-K-64 caps at 10).
pub const MAX_ROUNDS: usize = 10;

// ── EXP / LOG tables (Massey, FSE 1993) ──────────────────────────────
//
// EXP[x] = 45^x mod 257, with the value 256 represented as byte 0.

#[rustfmt::skip]
const EXP_TAB: [u8; 256] = [
      1,  45, 226, 147, 190,  69,  21, 174, 120,   3, 135, 164, 184,  56, 207,  63,
      8, 103,   9, 148, 235,  38, 168, 107, 189,  24,  52,  27, 187, 191, 114, 247,
     64,  53,  72, 156,  81,  47,  59,  85, 227, 192, 159, 216, 211, 243, 141, 177,
    255, 167,  62, 220, 134, 119, 215, 166,  17, 251, 244, 186, 146, 145, 100, 131,
    241,  51, 239, 218,  44, 181, 178,  43, 136, 209, 153, 203, 140, 132,  29,  20,
    129, 151, 113, 202,  95, 163, 139,  87,  60, 130, 196,  82,  92,  28, 232, 160,
      4, 180, 133,  74, 246,  19,  84, 182, 223,  12,  26, 142, 222, 224,  57, 252,
     32, 155,  36,  78, 169, 152, 158, 171, 242,  96, 208, 108, 234, 250, 199, 217,
      0, 212,  31, 110,  67, 188, 236,  83, 137, 254, 122,  93,  73, 201,  50, 194,
    249, 154, 248, 109,  22, 219,  89, 150,  68, 233, 205, 230,  70,  66, 143,  10,
    193, 204, 185, 101, 176, 210, 198, 172,  30,  65,  98,  41,  46,  14, 116,  80,
      2,  90, 195,  37, 123, 138,  42,  91, 240,   6,  13,  71, 111, 112, 157, 126,
     16, 206,  18,  39, 213,  76,  79, 214, 121,  48, 104,  54, 117, 125, 228, 237,
    128, 106, 144,  55, 162,  94, 118, 170, 197, 127,  61, 175, 165, 229,  25,  97,
    253,  77, 124, 183,  11, 238, 173,  75,  34, 245, 231, 115,  35,  33, 200,   5,
    225, 102, 221, 179,  88, 105,  99,  86,  15, 161,  49, 149,  23,   7,  58,  40,
];

#[rustfmt::skip]
const LOG_TAB: [u8; 256] = [
    128,   0, 176,   9,  96, 239, 185, 253,  16,  18, 159, 228, 105, 186, 173, 248,
    192,  56, 194, 101,  79,   6, 148, 252,  25, 222, 106,  27,  93,  78, 168, 130,
    112, 237, 232, 236, 114, 179,  21, 195, 255, 171, 182,  71,  68,   1, 172,  37,
    201, 250, 142,  65,  26,  33, 203, 211,  13, 110, 254,  38,  88, 218,  50,  15,
     32, 169, 157, 132, 152,   5, 156, 187,  34, 140,  99, 231, 197, 225, 115, 198,
    175,  36,  91, 135, 102,  39, 247,  87, 244, 150, 177, 183,  92, 139, 213,  84,
    121, 223, 170, 246,  62, 163, 241,  17, 202, 245, 209,  23, 123, 147, 131, 188,
    189,  82,  30, 235, 174, 204, 214,  53,   8, 200, 138, 180, 226, 205, 191, 217,
    208,  80,  89,  63,  77,  98,  52,  10,  72, 136, 181,  86,  76,  46, 107, 158,
    210,  61,  60,   3,  19, 251, 151,  81, 117,  74, 145, 113,  35, 190, 118,  42,
     95, 249, 212,  85,  11, 220,  55,  49,  22, 116, 215, 119, 167, 230,   7, 219,
    164,  47,  70, 243,  97,  69, 103, 227,  12, 162,  59,  28, 133,  24,   4,  29,
     41, 160, 143, 178,  90, 216, 166, 126, 238, 141,  83,  75, 161, 154, 193,  14,
    122,  73, 165,  44, 129, 196, 199,  54,  43, 127,  67, 149,  51, 242, 108, 104,
    109, 240,   2,  40, 206, 221, 155, 234,  94, 153, 124,  20, 134, 207, 229,  66,
    184,  64, 120,  45,  58, 233, 100,  31, 146, 144, 125,  57, 111, 224, 137,  48,
];

#[inline]
fn rol8(x: u8, n: u32) -> u8 {
    x.rotate_left(n)
}

#[inline]
fn pht(x: &mut u8, y: &mut u8) {
    *y = y.wrapping_add(*x);
    *x = x.wrapping_add(*y);
}

#[inline]
fn ipht(x: &mut u8, y: &mut u8) {
    *x = x.wrapping_sub(*y);
    *y = y.wrapping_sub(*x);
}

// ── Key schedule (SAFER-K-64, non-strengthened) ──────────────────────
//
// The key buffer layout matches the De Moliner reference: the first
// byte stores `nof_rounds`, then 2 × nof_rounds round keys of 8 bytes
// each.  For K-64 (not "strengthened"), both userkey halves are the
// same 64-bit input key.

fn expand_userkey(user_key: &[u8; 8], nof_rounds: usize) -> Vec<u8> {
    assert!((1..=MAX_ROUNDS).contains(&nof_rounds));
    let mut key = Vec::with_capacity(1 + 16 * nof_rounds);
    key.push(nof_rounds as u8);

    // Two parallel key registers KA and KB, each 9 bytes (the 9th byte
    // is a running XOR parity over the other 8).  For K-64 both are
    // initialised from the same 64-bit user key, but KA is pre-rotated
    // left by 5 bits.
    let mut ka = [0u8; SAFER_BLOCK_LEN + 1];
    let mut kb = [0u8; SAFER_BLOCK_LEN + 1];
    for j in 0..SAFER_BLOCK_LEN {
        ka[j] = rol8(user_key[j], 5);
        ka[SAFER_BLOCK_LEN] ^= ka[j];
        kb[j] = user_key[j];
        kb[SAFER_BLOCK_LEN] ^= kb[j];
        key.push(user_key[j]); // K_1 = user key
    }

    for i in 1..=nof_rounds {
        for j in 0..(SAFER_BLOCK_LEN + 1) {
            ka[j] = rol8(ka[j], 6);
            kb[j] = rol8(kb[j], 6);
        }
        // K_{2i} (8 bytes, K-variant non-strengthened: no `ka[k]` rotation,
        // just `ka[j] + EXP[EXP[(18i + j + 1) mod 256]]`).
        for j in 0..SAFER_BLOCK_LEN {
            let bias_idx = (18 * i + j + 1) & 0xFF;
            let bias = EXP_TAB[EXP_TAB[bias_idx] as usize];
            key.push(ka[j].wrapping_add(bias));
        }
        // K_{2i+1} (8 bytes).
        for j in 0..SAFER_BLOCK_LEN {
            let bias_idx = (18 * i + j + 10) & 0xFF;
            let bias = EXP_TAB[EXP_TAB[bias_idx] as usize];
            key.push(kb[j].wrapping_add(bias));
        }
    }

    key
}

// ── Cipher struct ────────────────────────────────────────────────────

#[derive(Clone, Debug)]
pub struct SaferK64 {
    /// Expanded key: 1 + 16·rounds bytes (the leading byte stores
    /// `nof_rounds`).
    key: Vec<u8>,
    rounds: usize,
}

impl SaferK64 {
    /// Construct SAFER-K-64 with the default 6 rounds (Massey's
    /// original recommendation).
    pub fn new(key: &[u8; 8]) -> Self {
        Self::with_rounds(key, DEFAULT_ROUNDS)
    }

    /// Construct SAFER-K-64 with an explicit round count in `6..=10`.
    pub fn with_rounds(key: &[u8; 8], rounds: usize) -> Self {
        assert!(
            (6..=MAX_ROUNDS).contains(&rounds),
            "SAFER-K-64 supports 6..=10 rounds, got {rounds}"
        );
        Self {
            key: expand_userkey(key, rounds),
            rounds,
        }
    }

    /// Encrypt one 64-bit block in place.
    pub fn encrypt_block(&self, block: &mut [u8; 8]) {
        let (mut a, mut b, mut c, mut d) = (block[0], block[1], block[2], block[3]);
        let (mut e, mut f, mut g, mut h) = (block[4], block[5], block[6], block[7]);

        // Walk a moving pointer through `self.key`.  Skip the first byte
        // (which stores the round count) by starting at index 0 and
        // pre-incrementing on each fetch — mirroring the C reference's
        // `*++key` idiom.
        let mut ki: usize = 0;
        for _ in 0..self.rounds {
            // Mixed XOR / add with round key 1.
            ki += 1;
            a ^= self.key[ki];
            ki += 1;
            b = b.wrapping_add(self.key[ki]);
            ki += 1;
            c = c.wrapping_add(self.key[ki]);
            ki += 1;
            d ^= self.key[ki];
            ki += 1;
            e ^= self.key[ki];
            ki += 1;
            f = f.wrapping_add(self.key[ki]);
            ki += 1;
            g = g.wrapping_add(self.key[ki]);
            ki += 1;
            h ^= self.key[ki];

            // Nonlinear layer with round key 2.
            ki += 1;
            a = EXP_TAB[a as usize].wrapping_add(self.key[ki]);
            ki += 1;
            b = LOG_TAB[b as usize] ^ self.key[ki];
            ki += 1;
            c = LOG_TAB[c as usize] ^ self.key[ki];
            ki += 1;
            d = EXP_TAB[d as usize].wrapping_add(self.key[ki]);
            ki += 1;
            e = EXP_TAB[e as usize].wrapping_add(self.key[ki]);
            ki += 1;
            f = LOG_TAB[f as usize] ^ self.key[ki];
            ki += 1;
            g = LOG_TAB[g as usize] ^ self.key[ki];
            ki += 1;
            h = EXP_TAB[h as usize].wrapping_add(self.key[ki]);

            // 3 levels of PHT with a fixed permutation between levels.
            pht(&mut a, &mut b);
            pht(&mut c, &mut d);
            pht(&mut e, &mut f);
            pht(&mut g, &mut h);
            pht(&mut a, &mut c);
            pht(&mut e, &mut g);
            pht(&mut b, &mut d);
            pht(&mut f, &mut h);
            pht(&mut a, &mut e);
            pht(&mut b, &mut f);
            pht(&mut c, &mut g);
            pht(&mut d, &mut h);
            // Byte permutation: (b,c,d,e,f,g) → (e,c→b stays, …).  C
            // expansion: `t=b; b=e; e=c; c=t; t=d; d=f; f=g; g=t;`.
            let t = b;
            b = e;
            e = c;
            c = t;
            let t = d;
            d = f;
            f = g;
            g = t;
        }

        // Final output transformation: just the "mixed XOR / add" with
        // the trailing half-key, no nonlinear layer / PHT.
        ki += 1;
        a ^= self.key[ki];
        ki += 1;
        b = b.wrapping_add(self.key[ki]);
        ki += 1;
        c = c.wrapping_add(self.key[ki]);
        ki += 1;
        d ^= self.key[ki];
        ki += 1;
        e ^= self.key[ki];
        ki += 1;
        f = f.wrapping_add(self.key[ki]);
        ki += 1;
        g = g.wrapping_add(self.key[ki]);
        ki += 1;
        h ^= self.key[ki];

        block[0] = a;
        block[1] = b;
        block[2] = c;
        block[3] = d;
        block[4] = e;
        block[5] = f;
        block[6] = g;
        block[7] = h;
    }

    /// Decrypt one 64-bit block in place.
    pub fn decrypt_block(&self, block: &mut [u8; 8]) {
        let (mut a, mut b, mut c, mut d) = (block[0], block[1], block[2], block[3]);
        let (mut e, mut f, mut g, mut h) = (block[4], block[5], block[6], block[7]);

        // Position the key pointer at the very last byte (`h ^= *key`
        // in the C reference, then pre-decrement on each subsequent
        // fetch).
        let mut ki = SAFER_BLOCK_LEN * (1 + 2 * self.rounds);
        h ^= self.key[ki];
        ki -= 1;
        g = g.wrapping_sub(self.key[ki]);
        ki -= 1;
        f = f.wrapping_sub(self.key[ki]);
        ki -= 1;
        e ^= self.key[ki];
        ki -= 1;
        d ^= self.key[ki];
        ki -= 1;
        c = c.wrapping_sub(self.key[ki]);
        ki -= 1;
        b = b.wrapping_sub(self.key[ki]);
        ki -= 1;
        a ^= self.key[ki];

        for _ in 0..self.rounds {
            // Inverse byte permutation:
            // `t=e; e=b; b=c; c=t; t=f; f=d; d=g; g=t;`.
            let t = e;
            e = b;
            b = c;
            c = t;
            let t = f;
            f = d;
            d = g;
            g = t;
            ipht(&mut a, &mut e);
            ipht(&mut b, &mut f);
            ipht(&mut c, &mut g);
            ipht(&mut d, &mut h);
            ipht(&mut a, &mut c);
            ipht(&mut e, &mut g);
            ipht(&mut b, &mut d);
            ipht(&mut f, &mut h);
            ipht(&mut a, &mut b);
            ipht(&mut c, &mut d);
            ipht(&mut e, &mut f);
            ipht(&mut g, &mut h);

            ki -= 1;
            h = h.wrapping_sub(self.key[ki]);
            ki -= 1;
            g ^= self.key[ki];
            ki -= 1;
            f ^= self.key[ki];
            ki -= 1;
            e = e.wrapping_sub(self.key[ki]);
            ki -= 1;
            d = d.wrapping_sub(self.key[ki]);
            ki -= 1;
            c ^= self.key[ki];
            ki -= 1;
            b ^= self.key[ki];
            ki -= 1;
            a = a.wrapping_sub(self.key[ki]);

            ki -= 1;
            h = LOG_TAB[h as usize] ^ self.key[ki];
            ki -= 1;
            g = EXP_TAB[g as usize].wrapping_sub(self.key[ki]);
            ki -= 1;
            f = EXP_TAB[f as usize].wrapping_sub(self.key[ki]);
            ki -= 1;
            e = LOG_TAB[e as usize] ^ self.key[ki];
            ki -= 1;
            d = LOG_TAB[d as usize] ^ self.key[ki];
            ki -= 1;
            c = EXP_TAB[c as usize].wrapping_sub(self.key[ki]);
            ki -= 1;
            b = EXP_TAB[b as usize].wrapping_sub(self.key[ki]);
            ki -= 1;
            a = LOG_TAB[a as usize] ^ self.key[ki];
        }

        block[0] = a;
        block[1] = b;
        block[2] = c;
        block[3] = d;
        block[4] = e;
        block[5] = f;
        block[6] = g;
        block[7] = h;
    }
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// **libtomcrypt `safer_k64_test` reference vector** (6 rounds):
    /// Key = {8,7,6,5,4,3,2,1}, PT = {1,2,3,4,5,6,7,8}, CT =
    /// {200,242,156,221,135,120,62,217}.  Cross-checked against the
    /// De Moliner ETH reference C implementation.
    #[test]
    fn safer_k64_libtom_vector() {
        let key: [u8; 8] = [8, 7, 6, 5, 4, 3, 2, 1];
        let mut block: [u8; 8] = [1, 2, 3, 4, 5, 6, 7, 8];
        let expected: [u8; 8] = [200, 242, 156, 221, 135, 120, 62, 217];
        let c = SaferK64::new(&key);
        c.encrypt_block(&mut block);
        assert_eq!(block, expected);
    }

    /// Decryption recovers the plaintext.
    #[test]
    fn safer_k64_libtom_decrypt() {
        let key: [u8; 8] = [8, 7, 6, 5, 4, 3, 2, 1];
        let plain: [u8; 8] = [1, 2, 3, 4, 5, 6, 7, 8];
        let mut block: [u8; 8] = [200, 242, 156, 221, 135, 120, 62, 217];
        let c = SaferK64::new(&key);
        c.decrypt_block(&mut block);
        assert_eq!(block, plain);
    }

    /// Encrypt → decrypt round-trip with several round counts.
    #[test]
    fn safer_k64_round_trip_varied_rounds() {
        let key: [u8; 8] = [0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0];
        for r in 6..=10 {
            let c = SaferK64::with_rounds(&key, r);
            for v in 0u64..16 {
                let p = v.wrapping_mul(0x0101_0101_0101_0101).to_be_bytes();
                let mut b = p;
                c.encrypt_block(&mut b);
                c.decrypt_block(&mut b);
                assert_eq!(b, p, "round trip failed for r={r} v={v}");
            }
        }
    }

    /// EXP / LOG tables are mutual inverses except at the "256 → 0"
    /// boundary (Massey's convention: `45^128 ≡ 256 (mod 257)`, stored
    /// as 0).
    #[test]
    fn safer_exp_log_inverse() {
        // `EXP[LOG[x]]` round-trips for all x except the special 0/128
        // wrap, but at minimum it matches for the non-degenerate cases.
        // Sanity-check a non-zero sample.
        for x in 1u16..=255 {
            let l = LOG_TAB[x as usize];
            let e = EXP_TAB[l as usize];
            assert_eq!(e as u16, x, "LOG/EXP mismatch at x={x}");
        }
    }
}
