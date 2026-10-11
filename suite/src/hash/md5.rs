//! **MD5** — Message Digest 5 (RFC 1321, 1992).
//!
//! 128-bit output, four 16-step rounds.  Wang-Feng-Lai-Yu (Crypto
//! 2004) found a practical collision in 2⁻³⁹ ops; modern collision
//! finders complete in seconds.  Use only as a study target —
//! `cryptanalysis::md5_differential` carries the analysis tooling.
//!
//! ## Algorithm
//!
//! Same Merkle–Damgård structure as MD4 with a fourth round
//! function `I(x, y, z) = y ⊕ (x ∨ ¬z)`, distinct word-index
//! permutations per round, and the 64 sine-table constants
//! `T[i] = floor(2³² · |sin(i+1)|)`.
//!
//! This module re-exports the MD5 primitive at the *hash* level.
//! The full-round (rounds=64) implementation lives here and shadows
//! the reduced-round variant in `cryptanalysis::md5_differential`
//! used for round-cost studies.

use crate::cryptanalysis::md5_differential::{md5_compress, MD5_IV};

/// **MD5 hash** of an arbitrary-length message — RFC 1321.  Always
/// runs the full 64-round compression.  Returns 16 bytes.
pub fn md5(message: &[u8]) -> [u8; 16] {
    let mut state = MD5_IV;
    let bit_len = (message.len() as u64).wrapping_mul(8);
    let mut padded = message.to_vec();
    padded.push(0x80);
    while padded.len() % 64 != 56 {
        padded.push(0);
    }
    padded.extend_from_slice(&bit_len.to_le_bytes());
    for chunk in padded.chunks_exact(64) {
        let mut block = [0u8; 64];
        block.copy_from_slice(chunk);
        md5_compress(&mut state, &block, 64);
    }
    let mut out = [0u8; 16];
    for (j, &word) in state.iter().enumerate() {
        out[4 * j..4 * j + 4].copy_from_slice(&word.to_le_bytes());
    }
    out
}

/// Apply MD-Damgård padding (RFC 1321 §3.1).  Useful when running an
/// **length-extension attack** that needs to recreate the padded
/// preimage of an absorbed prefix.
pub fn md5_pad(message_len: usize) -> Vec<u8> {
    let bit_len = (message_len as u64).wrapping_mul(8);
    let mut out = Vec::new();
    out.push(0x80);
    while (message_len + out.len()) % 64 != 56 {
        out.push(0);
    }
    out.extend_from_slice(&bit_len.to_le_bytes());
    out
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn hex(bytes: &[u8]) -> String {
        bytes.iter().map(|b| format!("{:02x}", b)).collect()
    }

    /// **RFC 1321 Appendix A.5 test vectors**.
    #[test]
    fn md5_rfc1321_test_vectors() {
        let cases: &[(&[u8], &str)] = &[
            (b"", "d41d8cd98f00b204e9800998ecf8427e"),
            (b"a", "0cc175b9c0f1b6a831c399e269772661"),
            (b"abc", "900150983cd24fb0d6963f7d28e17f72"),
            (b"message digest", "f96b697d7cb7938d525a2f31aaf161d0"),
            (
                b"abcdefghijklmnopqrstuvwxyz",
                "c3fcd3d76192e4007dfb496cca67e13b",
            ),
            (
                b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
                "d174ab98d277d9f5a5611c2c9f419d9f",
            ),
            (
                b"12345678901234567890123456789012345678901234567890123456789012345678901234567890",
                "57edf4a22be3c955ac49da2e2107b67a",
            ),
        ];
        for (msg, want) in cases {
            let got = md5(msg);
            assert_eq!(hex(&got), *want, "mismatch on {:?}", msg);
        }
    }

    /// Padding length matches the standard.
    #[test]
    fn md5_pad_lengths() {
        // For a 0-byte message: pad = 0x80 + 55 zeros + 8 bytes len = 64.
        assert_eq!(md5_pad(0).len(), 64);
        // For a 55-byte message: pad = 0x80 + 0 zeros + 8 bytes len = 9.
        assert_eq!(md5_pad(55).len(), 9);
        // For a 56-byte message: pad = 0x80 + 63 zeros + 8 bytes len = 72.
        assert_eq!(md5_pad(56).len(), 72);
        // Padded result is always a multiple of 64.
        for len in 0..200 {
            assert_eq!((len + md5_pad(len).len()) % 64, 0);
        }
    }
}
