//! **TEA** — Tiny Encryption Algorithm (Wheeler & Needham, 1994).
//!
//! TEA is one of the smallest published block ciphers: a 64-bit block,
//! 128-bit key, balanced Feistel structure run for 64 rounds (32
//! "cycles") with a magic constant `δ = ⌊2³² / φ⌋ = 0x9E3779B9`.  The
//! original paper fits the C reference on a postcard.
//!
//! ## Round function
//!
//! State is a pair of 32-bit words `(v0, v1)`.  Each cycle accumulates
//! the constant `sum ← sum + δ` and applies the two half-rounds:
//!
//! ```text
//!     v0 ← v0 + (((v1 << 4) + k0) ⊕ (v1 + sum) ⊕ ((v1 >> 5) + k1))
//!     v1 ← v1 + (((v0 << 4) + k2) ⊕ (v0 + sum) ⊕ ((v0 >> 5) + k3))
//! ```
//!
//! Decryption runs the inverse with `sum` initialised to `32·δ` and
//! decremented after each cycle.
//!
//! ## Byte conventions
//!
//! The plaintext block and key are read **big-endian**: `v0 =
//! u32::from_be_bytes(block[0..4])`, `v1 = u32::from_be_bytes(block[4..8])`,
//! `k0 = u32::from_be_bytes(key[0..4])`, etc.  This matches the paper's
//! pseudocode where `v[0]` is the high word.
//!
//! ## Security note
//!
//! TEA has **known weaknesses**: it has equivalent keys (Kelsey, Schneier
//! & Wagner, 1996) — every key has three other keys that encrypt to the
//! same ciphertext, reducing effective key strength to 126 bits — and it
//! was famously used as a hash function in the original Xbox boot ROM,
//! where the equivalent-key property enabled a TEA-as-hash second
//! preimage that broke the chain of trust.  Use [`Xtea`](super::xtea) (or,
//! better, AES/ChaCha20) for new designs.

const DELTA: u32 = 0x9E37_79B9;
const ROUNDS: usize = 32; // 32 cycles = 64 Feistel rounds

/// TEA cipher with a 128-bit key.
#[derive(Clone, Debug)]
pub struct Tea {
    k: [u32; 4],
}

impl Tea {
    /// Construct a TEA cipher from a 16-byte key.
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
        let [k0, k1, k2, k3] = self.k;
        for _ in 0..ROUNDS {
            sum = sum.wrapping_add(DELTA);
            v0 = v0.wrapping_add(
                (v1 << 4).wrapping_add(k0) ^ v1.wrapping_add(sum) ^ (v1 >> 5).wrapping_add(k1),
            );
            v1 = v1.wrapping_add(
                (v0 << 4).wrapping_add(k2) ^ v0.wrapping_add(sum) ^ (v0 >> 5).wrapping_add(k3),
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
        let [k0, k1, k2, k3] = self.k;
        for _ in 0..ROUNDS {
            v1 = v1.wrapping_sub(
                (v0 << 4).wrapping_add(k2) ^ v0.wrapping_add(sum) ^ (v0 >> 5).wrapping_add(k3),
            );
            v0 = v0.wrapping_sub(
                (v1 << 4).wrapping_add(k0) ^ v1.wrapping_add(sum) ^ (v1 >> 5).wrapping_add(k1),
            );
            sum = sum.wrapping_sub(DELTA);
        }
        block[0..4].copy_from_slice(&v0.to_be_bytes());
        block[4..8].copy_from_slice(&v1.to_be_bytes());
    }
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// Reference test vector derived directly from the Wheeler & Needham
    /// 1994 pseudocode (no published vectors exist in the paper itself).
    /// All-zero key, all-zero plaintext.  Independently cross-checked
    /// against a from-scratch Python port of the paper's C source.
    #[test]
    fn tea_zero_key_zero_plaintext() {
        let key = [0u8; 16];
        let mut block = [0u8; 8];
        let c = Tea::new(&key);
        c.encrypt_block(&mut block);
        // sum after 32 cycles with delta = 0x9E3779B9 -> CT derived
        // from the paper's reference C implementation.
        assert_eq!(block, [0x41, 0xea, 0x3a, 0x0a, 0x94, 0xba, 0xa9, 0x40]);
        c.decrypt_block(&mut block);
        assert_eq!(block, [0u8; 8]);
    }

    /// Cross-check vector with a non-trivial key/plaintext pair, also
    /// derived from a Python port of the paper's pseudocode.
    #[test]
    fn tea_known_vector() {
        let key = [
            0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d,
            0x0e, 0x0f,
        ];
        let mut block = [0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde, 0xf0];
        let pt = block;
        let c = Tea::new(&key);
        c.encrypt_block(&mut block);
        assert_eq!(block, [0x33, 0x19, 0xb6, 0x24, 0xc4, 0x6c, 0x3d, 0xe8]);
        c.decrypt_block(&mut block);
        assert_eq!(block, pt);
    }

    /// Random round-trip across a few keys/blocks.
    #[test]
    fn tea_round_trip() {
        for key_byte in [0x00u8, 0x42, 0xff] {
            let key = [key_byte; 16];
            let c = Tea::new(&key);
            for pt_byte in [0x00u8, 0xAA, 0xff] {
                let pt = [pt_byte; 8];
                let mut blk = pt;
                c.encrypt_block(&mut blk);
                if key_byte != 0 || pt_byte != 0 {
                    assert_ne!(blk, pt, "TEA encrypt was identity");
                }
                c.decrypt_block(&mut blk);
                assert_eq!(blk, pt);
            }
        }
    }
}
