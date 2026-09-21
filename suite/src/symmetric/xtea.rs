//! **XTEA** — eXtended TEA (Needham & Wheeler, 1997).
//!
//! XTEA is a retrofit of [TEA](super::tea) that repairs the equivalent-
//! key weakness and reorders operations so that the key schedule mixes
//! all four subkeys more thoroughly.  It keeps the 64-bit block,
//! 128-bit key, and the magic constant `δ = 0x9E3779B9`, and like TEA
//! the standard parameterisation runs 32 cycles (64 Feistel rounds).
//!
//! ## Round function
//!
//! State `(v0, v1)`.  Each cycle:
//!
//! ```text
//!     v0 ← v0 + ((((v1 << 4) ⊕ (v1 >> 5)) + v1) ⊕ (sum + k[sum & 3]))
//!     sum ← sum + δ
//!     v1 ← v1 + ((((v0 << 4) ⊕ (v0 >> 5)) + v0) ⊕ (sum + k[(sum >> 11) & 3]))
//! ```
//!
//! The inverse is the straightforward reversal with `sum` starting at
//! `32·δ` and decrementing after each cycle.
//!
//! ## Byte conventions
//!
//! Block and key are read **big-endian**, matching the typical XTEA
//! reference C code where `v[0]` and `k[0]` are the high words.
//!
//! ## Security note
//!
//! XTEA has known related-key and impossible-differential attacks on
//! reduced-round variants, but no practical break of full 32-cycle
//! XTEA is publicly known.  Its 64-bit block is the bigger problem in
//! 2024: it makes XTEA unsuitable for encrypting more than a few GiB
//! under one key (the Sweet32 boundary).  Use AES-128 or ChaCha20 for
//! new designs; this implementation is included for interoperability
//! with legacy systems (e.g. embedded firmware, classic game consoles).

const DELTA: u32 = 0x9E37_79B9;
const ROUNDS: usize = 32; // 32 cycles = 64 Feistel rounds (standard XTEA)

/// XTEA cipher with a 128-bit key.
#[derive(Clone, Debug)]
pub struct Xtea {
    k: [u32; 4],
}

impl Xtea {
    /// Construct an XTEA cipher from a 16-byte key.
    pub fn new(key: &[u8; 16]) -> Self {
        Self {
            k: [
                u32::from_be_bytes(key[0..4].try_into().unwrap()),
                u32::from_be_bytes(key[4..8].try_into().unwrap()),
                u32::from_be_bytes(key[8..12].try_into().unwrap()),
                u32::from_be_bytes(key[12..16].try_into().unwrap()),
            ],
        }
    }

    /// Encrypt a single 64-bit block in place.
    pub fn encrypt_block(&self, block: &mut [u8; 8]) {
        let mut v0 = u32::from_be_bytes(block[0..4].try_into().unwrap());
        let mut v1 = u32::from_be_bytes(block[4..8].try_into().unwrap());
        let mut sum: u32 = 0;
        for _ in 0..ROUNDS {
            v0 = v0.wrapping_add(
                (((v1 << 4) ^ (v1 >> 5)).wrapping_add(v1))
                    ^ sum.wrapping_add(self.k[(sum & 3) as usize]),
            );
            sum = sum.wrapping_add(DELTA);
            v1 = v1.wrapping_add(
                (((v0 << 4) ^ (v0 >> 5)).wrapping_add(v0))
                    ^ sum.wrapping_add(self.k[((sum >> 11) & 3) as usize]),
            );
        }
        block[0..4].copy_from_slice(&v0.to_be_bytes());
        block[4..8].copy_from_slice(&v1.to_be_bytes());
    }

    /// Decrypt a single 64-bit block in place.
    pub fn decrypt_block(&self, block: &mut [u8; 8]) {
        let mut v0 = u32::from_be_bytes(block[0..4].try_into().unwrap());
        let mut v1 = u32::from_be_bytes(block[4..8].try_into().unwrap());
        let mut sum: u32 = DELTA.wrapping_mul(ROUNDS as u32);
        for _ in 0..ROUNDS {
            v1 = v1.wrapping_sub(
                (((v0 << 4) ^ (v0 >> 5)).wrapping_add(v0))
                    ^ sum.wrapping_add(self.k[((sum >> 11) & 3) as usize]),
            );
            sum = sum.wrapping_sub(DELTA);
            v0 = v0.wrapping_sub(
                (((v1 << 4) ^ (v1 >> 5)).wrapping_add(v1))
                    ^ sum.wrapping_add(self.k[(sum & 3) as usize]),
            );
        }
        block[0..4].copy_from_slice(&v0.to_be_bytes());
        block[4..8].copy_from_slice(&v1.to_be_bytes());
    }
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// All-zero key + all-zero plaintext.  CT derived from a Python
    /// port of the Needham & Wheeler 1997 reference C source.
    #[test]
    fn xtea_zero_key_zero_plaintext() {
        let key = [0u8; 16];
        let mut block = [0u8; 8];
        let c = Xtea::new(&key);
        c.encrypt_block(&mut block);
        assert_eq!(block, [0xde, 0xe9, 0xd4, 0xd8, 0xf7, 0x13, 0x1e, 0xd9]);
        c.decrypt_block(&mut block);
        assert_eq!(block, [0u8; 8]);
    }

    /// Known-vector cross-check with a non-trivial key/plaintext pair,
    /// also derived from a from-scratch Python port of the paper.
    /// Key  = 00 01 02 … 0f
    /// PT   = "ABCDEFGH" (0x4142434445464748)
    #[test]
    fn xtea_known_vector() {
        let key = [
            0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d,
            0x0e, 0x0f,
        ];
        let pt = [0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48];
        let mut block = pt;
        let c = Xtea::new(&key);
        c.encrypt_block(&mut block);
        assert_eq!(block, [0x49, 0x7d, 0xf3, 0xd0, 0x72, 0x61, 0x2c, 0xb5]);
        c.decrypt_block(&mut block);
        assert_eq!(block, pt);
    }

    /// Round-trip across a sweep of keys and plaintexts.
    #[test]
    fn xtea_round_trip() {
        for key_byte in [0x00u8, 0x55, 0xaa, 0xff] {
            let key = [key_byte; 16];
            let c = Xtea::new(&key);
            for pt_byte in [0x00u8, 0xa5, 0xff] {
                let pt = [pt_byte; 8];
                let mut blk = pt;
                c.encrypt_block(&mut blk);
                if key_byte != 0 || pt_byte != 0 {
                    assert_ne!(blk, pt);
                }
                c.decrypt_block(&mut blk);
                assert_eq!(blk, pt);
            }
        }
    }

    /// XTEA must differ from TEA: with all-zero key + plaintext, the
    /// two ciphers produce different ciphertexts.  Sanity check that
    /// we did not accidentally implement TEA.
    #[test]
    fn xtea_differs_from_tea() {
        let key = [0u8; 16];
        let mut block = [0u8; 8];
        Xtea::new(&key).encrypt_block(&mut block);
        // TEA's zero/zero output is 0x41ea3a0a94baa940 — must differ.
        assert_ne!(block, [0x41, 0xea, 0x3a, 0x0a, 0x94, 0xba, 0xa9, 0x40]);
    }
}
