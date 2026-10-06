//! **Skipjack** — NSA's "Clipper" cipher (1993, declassified 1998).
//!
//! 64-bit block, 80-bit key, 32 rounds.  Designed by the NSA in the
//! mid-1980s, deployed in the **Clipper** chip and the **Fortezza**
//! PCMCIA card as part of the U.S. government's key-escrow programme.
//! The algorithm was classified until **24 June 1998**, when NIST
//! published the specification together with the companion KEA key
//! exchange ("SKIPJACK and KEA Algorithm Specifications", v2.0).
//!
//! ## Security note
//!
//! **Skipjack is a historical / pedagogical cipher** — it is not
//! recommended for any new design.  The 80-bit key is below modern
//! brute-force margins (NIST itself withdrew support in 2010); Biham,
//! Biryukov & Shamir gave an impossible-differential attack on a
//! 31-round variant within months of declassification, and the cipher
//! was politically tainted from birth by the Clipper escrow proposal.
//! It survives here purely so that students can read the round
//! structure and reproduce the NIST test vector.
//!
//! ## Structure
//!
//! Skipjack operates on a 64-bit word split into four 16-bit words
//! `w1, w2, w3, w4` (high-to-low, MSB-first).  Eight "Rule A" rounds
//! and eight "Rule B" rounds alternate:
//!
//! ```text
//!     Rule A (counter k):                 Rule B (counter k):
//!         w1' = G_k(w1) ⊕ w4 ⊕ k             w1' = w4
//!         w2' = G_k(w1)                      w2' = G_k(w1)
//!         w3' = w2                           w3' = w1 ⊕ w2 ⊕ k
//!         w4' = w3                           w4' = w3
//! ```
//!
//! The full schedule is `A^8, B^8, A^8, B^8` with the counter `k`
//! running from 1 through 32.  Decryption uses the inverses `A^{-1}`
//! and `B^{-1}` in the order `B^{-1}^8, A^{-1}^8, B^{-1}^8, A^{-1}^8`
//! with `k` running from 32 down to 1.
//!
//! `G_k` is a 4-round Feistel permutation on a 16-bit word with the
//! 8-bit "F-table" S-box.  The four bytes of the round key for `G_k`
//! are `cv[(4k-4) mod 10], …, cv[(4k-1) mod 10]` where `cv` is the
//! 10-byte master key (NIST spec uses 1-indexed `cv[1..10]`; we are
//! 0-indexed here).
//!
//! ## References
//!
//! - NIST, *SKIPJACK and KEA Algorithm Specifications*, v2.0, 29 May
//!   1998 (the official declassified document).
//! - Biham, Biryukov, Shamir, *Cryptanalysis of Skipjack Reduced to 31
//!   Rounds Using Impossible Differentials*, EUROCRYPT 1999.

// ── F-table (NIST spec §3.1) ─────────────────────────────────────────

/// The Skipjack F-table: a fixed 8→8 bijection used in `G_k`.
#[rustfmt::skip]
const F: [u8; 256] = [
    0xa3, 0xd7, 0x09, 0x83, 0xf8, 0x48, 0xf6, 0xf4, 0xb3, 0x21, 0x15, 0x78, 0x99, 0xb1, 0xaf, 0xf9,
    0xe7, 0x2d, 0x4d, 0x8a, 0xce, 0x4c, 0xca, 0x2e, 0x52, 0x95, 0xd9, 0x1e, 0x4e, 0x38, 0x44, 0x28,
    0x0a, 0xdf, 0x02, 0xa0, 0x17, 0xf1, 0x60, 0x68, 0x12, 0xb7, 0x7a, 0xc3, 0xe9, 0xfa, 0x3d, 0x53,
    0x96, 0x84, 0x6b, 0xba, 0xf2, 0x63, 0x9a, 0x19, 0x7c, 0xae, 0xe5, 0xf5, 0xf7, 0x16, 0x6a, 0xa2,
    0x39, 0xb6, 0x7b, 0x0f, 0xc1, 0x93, 0x81, 0x1b, 0xee, 0xb4, 0x1a, 0xea, 0xd0, 0x91, 0x2f, 0xb8,
    0x55, 0xb9, 0xda, 0x85, 0x3f, 0x41, 0xbf, 0xe0, 0x5a, 0x58, 0x80, 0x5f, 0x66, 0x0b, 0xd8, 0x90,
    0x35, 0xd5, 0xc0, 0xa7, 0x33, 0x06, 0x65, 0x69, 0x45, 0x00, 0x94, 0x56, 0x6d, 0x98, 0x9b, 0x76,
    0x97, 0xfc, 0xb2, 0xc2, 0xb0, 0xfe, 0xdb, 0x20, 0xe1, 0xeb, 0xd6, 0xe4, 0xdd, 0x47, 0x4a, 0x1d,
    0x42, 0xed, 0x9e, 0x6e, 0x49, 0x3c, 0xcd, 0x43, 0x27, 0xd2, 0x07, 0xd4, 0xde, 0xc7, 0x67, 0x18,
    0x89, 0xcb, 0x30, 0x1f, 0x8d, 0xc6, 0x8f, 0xaa, 0xc8, 0x74, 0xdc, 0xc9, 0x5d, 0x5c, 0x31, 0xa4,
    0x70, 0x88, 0x61, 0x2c, 0x9f, 0x0d, 0x2b, 0x87, 0x50, 0x82, 0x54, 0x64, 0x26, 0x7d, 0x03, 0x40,
    0x34, 0x4b, 0x1c, 0x73, 0xd1, 0xc4, 0xfd, 0x3b, 0xcc, 0xfb, 0x7f, 0xab, 0xe6, 0x3e, 0x5b, 0xa5,
    0xad, 0x04, 0x23, 0x9c, 0x14, 0x51, 0x22, 0xf0, 0x29, 0x79, 0x71, 0x7e, 0xff, 0x8c, 0x0e, 0xe2,
    0x0c, 0xef, 0xbc, 0x72, 0x75, 0x6f, 0x37, 0xa1, 0xec, 0xd3, 0x8e, 0x62, 0x8b, 0x86, 0x10, 0xe8,
    0x08, 0x77, 0x11, 0xbe, 0x92, 0x4f, 0x24, 0xc5, 0x32, 0x36, 0x9d, 0xcf, 0xf3, 0xa6, 0xbb, 0xac,
    0x5e, 0x6c, 0xa9, 0x13, 0x57, 0x25, 0xb5, 0xe3, 0xbd, 0xa8, 0x3a, 0x01, 0x05, 0x59, 0x2a, 0x46,
];

// ── G permutation ────────────────────────────────────────────────────

/// 4-round Feistel `G_k`.  `k` is the 1-indexed round counter; the four
/// cryptovariable bytes come from `cv[(4·(k-1)) mod 10 ..]`.
#[inline]
fn g(cv: &[u8; 10], k: usize, w: u16) -> u16 {
    let base = 4 * (k - 1);
    let g1 = (w >> 8) as u8;
    let g2 = (w & 0xFF) as u8;
    let g3 = F[(g2 ^ cv[base % 10]) as usize] ^ g1;
    let g4 = F[(g3 ^ cv[(base + 1) % 10]) as usize] ^ g2;
    let g5 = F[(g4 ^ cv[(base + 2) % 10]) as usize] ^ g3;
    let g6 = F[(g5 ^ cv[(base + 3) % 10]) as usize] ^ g4;
    ((g5 as u16) << 8) | (g6 as u16)
}

/// Inverse of `G_k`.  Undo the 4-round Feistel by reversing the steps:
/// from `(g5, g6)` recover `g4, g3, g2, g1`.
#[inline]
fn g_inv(cv: &[u8; 10], k: usize, w: u16) -> u16 {
    let base = 4 * (k - 1);
    let g5 = (w >> 8) as u8;
    let g6 = (w & 0xFF) as u8;
    // From g6 = F[g5 ⊕ cv[base+3]] ⊕ g4 →
    let g4 = F[(g5 ^ cv[(base + 3) % 10]) as usize] ^ g6;
    // From g5 = F[g4 ⊕ cv[base+2]] ⊕ g3 →
    let g3 = F[(g4 ^ cv[(base + 2) % 10]) as usize] ^ g5;
    // From g4 = F[g3 ⊕ cv[base+1]] ⊕ g2 →
    let g2 = F[(g3 ^ cv[(base + 1) % 10]) as usize] ^ g4;
    // From g3 = F[g2 ⊕ cv[base+0]] ⊕ g1 →
    let g1 = F[(g2 ^ cv[base % 10]) as usize] ^ g3;
    ((g1 as u16) << 8) | (g2 as u16)
}

// ── Rule A / Rule B (NIST spec §3) ───────────────────────────────────

/// Rule A round (encryption).
#[inline]
fn rule_a(cv: &[u8; 10], k: usize, w: [u16; 4]) -> [u16; 4] {
    let gw = g(cv, k, w[0]);
    [gw ^ w[3] ^ (k as u16), gw, w[1], w[2]]
}

/// Rule B round (encryption).
#[inline]
fn rule_b(cv: &[u8; 10], k: usize, w: [u16; 4]) -> [u16; 4] {
    let gw = g(cv, k, w[0]);
    [w[3], gw, w[0] ^ w[1] ^ (k as u16), w[2]]
}

/// Inverse of Rule A.  Given output `w'` and counter `k`, recover input.
///
/// From Rule A: `w1' = G(w1) ⊕ w4 ⊕ k`, `w2' = G(w1)`, `w3' = w2`,
/// `w4' = w3`.  So `w1 = G^{-1}(w2')`, `w2 = w3'`, `w3 = w4'`,
/// `w4 = w1' ⊕ w2' ⊕ k`.
#[inline]
fn rule_a_inv(cv: &[u8; 10], k: usize, w: [u16; 4]) -> [u16; 4] {
    let w1 = g_inv(cv, k, w[1]);
    [w1, w[2], w[3], w[0] ^ w[1] ^ (k as u16)]
}

/// Inverse of Rule B.  Given output `w'`:
/// From Rule B: `w1' = w4`, `w2' = G(w1)`, `w3' = w1 ⊕ w2 ⊕ k`,
/// `w4' = w3`.  So `w1 = G^{-1}(w2')`, `w2 = w1 ⊕ w3' ⊕ k`,
/// `w3 = w4'`, `w4 = w1'`.
#[inline]
fn rule_b_inv(cv: &[u8; 10], k: usize, w: [u16; 4]) -> [u16; 4] {
    let w1 = g_inv(cv, k, w[1]);
    [w1, w1 ^ w[2] ^ (k as u16), w[3], w[0]]
}

// ── Byte/word conversion ─────────────────────────────────────────────

#[inline]
fn bytes_to_words(b: &[u8; 8]) -> [u16; 4] {
    [
        ((b[0] as u16) << 8) | b[1] as u16,
        ((b[2] as u16) << 8) | b[3] as u16,
        ((b[4] as u16) << 8) | b[5] as u16,
        ((b[6] as u16) << 8) | b[7] as u16,
    ]
}

#[inline]
fn words_to_bytes(w: [u16; 4]) -> [u8; 8] {
    [
        (w[0] >> 8) as u8,
        (w[0] & 0xFF) as u8,
        (w[1] >> 8) as u8,
        (w[1] & 0xFF) as u8,
        (w[2] >> 8) as u8,
        (w[2] & 0xFF) as u8,
        (w[3] >> 8) as u8,
        (w[3] & 0xFF) as u8,
    ]
}

// ── Public API ───────────────────────────────────────────────────────

/// A Skipjack instance keyed with a 10-byte (80-bit) cryptovariable.
#[derive(Clone, Debug)]
pub struct Skipjack {
    cv: [u8; 10],
}

impl Skipjack {
    pub fn new(key: &[u8; 10]) -> Self {
        Self { cv: *key }
    }

    /// Encrypt one 64-bit block in place.  The 32 rounds run as
    /// `A^8 (k=1..8), B^8 (k=9..16), A^8 (k=17..24), B^8 (k=25..32)`.
    pub fn encrypt_block(&self, block: &mut [u8; 8]) {
        let mut w = bytes_to_words(block);
        for k in 1..=8 {
            w = rule_a(&self.cv, k, w);
        }
        for k in 9..=16 {
            w = rule_b(&self.cv, k, w);
        }
        for k in 17..=24 {
            w = rule_a(&self.cv, k, w);
        }
        for k in 25..=32 {
            w = rule_b(&self.cv, k, w);
        }
        *block = words_to_bytes(w);
    }

    /// Decrypt one 64-bit block in place.
    pub fn decrypt_block(&self, block: &mut [u8; 8]) {
        let mut w = bytes_to_words(block);
        for k in (25..=32).rev() {
            w = rule_b_inv(&self.cv, k, w);
        }
        for k in (17..=24).rev() {
            w = rule_a_inv(&self.cv, k, w);
        }
        for k in (9..=16).rev() {
            w = rule_b_inv(&self.cv, k, w);
        }
        for k in (1..=8).rev() {
            w = rule_a_inv(&self.cv, k, w);
        }
        *block = words_to_bytes(w);
    }
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

    /// **NIST declassified spec test vector** (SKIPJACK & KEA v2.0,
    /// Appendix):
    ///
    /// Key (cv) = 00 99 88 77 66 55 44 33 22 11
    /// PT       = 33 22 11 00 DD CC BB AA
    /// CT       = 25 87 CA E2 7A 12 D3 00
    #[test]
    fn skipjack_nist_appendix_vector() {
        let mut key = [0u8; 10];
        key.copy_from_slice(&h("00998877665544332211"));
        let mut block = [0u8; 8];
        block.copy_from_slice(&h("33221100ddccbbaa"));
        let expected = h("2587cae27a12d300");

        let c = Skipjack::new(&key);
        c.encrypt_block(&mut block);
        assert_eq!(&block[..], &expected[..], "Skipjack encrypt mismatch");

        c.decrypt_block(&mut block);
        let pt = h("33221100ddccbbaa");
        assert_eq!(&block[..], &pt[..], "Skipjack decrypt mismatch");
    }

    /// Round-trip on a handful of arbitrary blocks.
    #[test]
    fn skipjack_round_trip() {
        let key = [0x42u8; 10];
        let c = Skipjack::new(&key);
        for seed in 0u8..32 {
            let mut block = [seed; 8];
            for (i, b) in block.iter_mut().enumerate() {
                *b = b.wrapping_mul(31).wrapping_add(i as u8);
            }
            let orig = block;
            c.encrypt_block(&mut block);
            assert_ne!(block, orig, "encrypt-of-orig should not be identity");
            c.decrypt_block(&mut block);
            assert_eq!(block, orig, "round-trip failed for seed {}", seed);
        }
    }

    /// Test inverses round-trip across many keys.
    #[test]
    fn skipjack_round_trip_many_keys() {
        for key_seed in 0u8..16 {
            let key = [
                key_seed,
                key_seed.wrapping_add(1),
                key_seed.wrapping_add(2),
                key_seed.wrapping_add(3),
                key_seed.wrapping_add(4),
                key_seed.wrapping_add(5),
                key_seed.wrapping_add(6),
                key_seed.wrapping_add(7),
                key_seed.wrapping_add(8),
                key_seed.wrapping_add(9),
            ];
            let c = Skipjack::new(&key);
            for blk_seed in 0u8..8 {
                let block_orig: [u8; 8] = [
                    blk_seed,
                    blk_seed.wrapping_mul(3),
                    blk_seed.wrapping_mul(5),
                    blk_seed.wrapping_mul(7),
                    blk_seed.wrapping_mul(11),
                    blk_seed.wrapping_mul(13),
                    blk_seed.wrapping_mul(17),
                    blk_seed.wrapping_mul(19),
                ];
                let mut block = block_orig;
                c.encrypt_block(&mut block);
                c.decrypt_block(&mut block);
                assert_eq!(
                    block, block_orig,
                    "round-trip failed at key_seed={}, blk_seed={}",
                    key_seed, blk_seed
                );
            }
        }
    }
}
