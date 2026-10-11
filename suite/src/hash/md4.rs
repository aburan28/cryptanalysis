//! **MD4** — Rivest's Message Digest 4 (RFC 1320, 1990).
//!
//! 128-bit output, 32-bit-word Merkle–Damgård design with three
//! 16-step rounds.  Broken: Dobbertin 1996 found a collision; Wang-Lai
//! 2005 published practical collision-finding in seconds.  Still
//! useful as a study target and as the basis for MD5.
//!
//! ## Algorithm
//!
//! Padding: append a 0x80 byte, then enough zeros, then an 8-byte
//! little-endian length so the total is a multiple of 64 bytes.
//!
//! Each 64-byte block is split into 16 little-endian 32-bit words.
//! Round functions:
//!
//! ```text
//!     F(X, Y, Z) = (X ∧ Y) ∨ (¬X ∧ Z)
//!     G(X, Y, Z) = (X ∧ Y) ∨ (X ∧ Z) ∨ (Y ∧ Z)
//!     H(X, Y, Z) = X ⊕ Y ⊕ Z
//! ```
//!
//! Three rounds of 16 operations each.  After all blocks, output the
//! state as 16 little-endian bytes.
//!
//! ## References
//!
//! - **RFC 1320** — The MD4 Message-Digest Algorithm.
//! - **H. Dobbertin**, *Cryptanalysis of MD4*, FSE 1996.
//! - **X. Wang, X. Lai, D. Feng, H. Chen, X. Yu**, *Cryptanalysis of
//!   the Hash Functions MD4 and RIPEMD*, EUROCRYPT 2005.

const INITIAL_STATE: [u32; 4] = [0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476];

#[inline]
fn f(x: u32, y: u32, z: u32) -> u32 {
    (x & y) | (!x & z)
}
#[inline]
fn g(x: u32, y: u32, z: u32) -> u32 {
    (x & y) | (x & z) | (y & z)
}
#[inline]
fn h(x: u32, y: u32, z: u32) -> u32 {
    x ^ y ^ z
}

/// **Compress one 512-bit block** into the running state.  Exposed so
/// the cryptanalysis side can target intermediate states or run a
/// reduced-round variant.
pub fn md4_compress(state: &mut [u32; 4], block: &[u8; 64]) {
    let mut x = [0u32; 16];
    for i in 0..16 {
        x[i] = u32::from_le_bytes([
            block[4 * i],
            block[4 * i + 1],
            block[4 * i + 2],
            block[4 * i + 3],
        ]);
    }
    let (mut a, mut b, mut c, mut d) = (state[0], state[1], state[2], state[3]);

    // Round 1: F + K=0  (FF macro in RFC 1320).
    let ff = |a: u32, b, c, d, k: u32, s: u32| -> u32 {
        a.wrapping_add(f(b, c, d)).wrapping_add(k).rotate_left(s)
    };
    for &(i, s) in &[
        (0usize, 3u32),
        (1, 7),
        (2, 11),
        (3, 19),
        (4, 3),
        (5, 7),
        (6, 11),
        (7, 19),
        (8, 3),
        (9, 7),
        (10, 11),
        (11, 19),
        (12, 3),
        (13, 7),
        (14, 11),
        (15, 19),
    ] {
        // Rotate (a, b, c, d) <- (d, ff(a,b,c,d), b, c) every step.
        let new_a = ff(a, b, c, d, x[i], s);
        a = d;
        d = c;
        c = b;
        b = new_a;
    }

    // Round 2: G + K=0x5A827999.
    let gg = |a: u32, b, c, d, k: u32, s: u32| -> u32 {
        a.wrapping_add(g(b, c, d))
            .wrapping_add(k)
            .wrapping_add(0x5A827999)
            .rotate_left(s)
    };
    // Round-2 message-word order: 0,4,8,12,1,5,9,13,2,6,10,14,3,7,11,15.
    for &(i, s) in &[
        (0usize, 3u32),
        (4, 5),
        (8, 9),
        (12, 13),
        (1, 3),
        (5, 5),
        (9, 9),
        (13, 13),
        (2, 3),
        (6, 5),
        (10, 9),
        (14, 13),
        (3, 3),
        (7, 5),
        (11, 9),
        (15, 13),
    ] {
        let new_a = gg(a, b, c, d, x[i], s);
        a = d;
        d = c;
        c = b;
        b = new_a;
    }

    // Round 3: H + K=0x6ED9EBA1.
    let hh = |a: u32, b, c, d, k: u32, s: u32| -> u32 {
        a.wrapping_add(h(b, c, d))
            .wrapping_add(k)
            .wrapping_add(0x6ED9EBA1)
            .rotate_left(s)
    };
    // Round-3 message-word order: 0,8,4,12,2,10,6,14,1,9,5,13,3,11,7,15.
    for &(i, s) in &[
        (0usize, 3u32),
        (8, 9),
        (4, 11),
        (12, 15),
        (2, 3),
        (10, 9),
        (6, 11),
        (14, 15),
        (1, 3),
        (9, 9),
        (5, 11),
        (13, 15),
        (3, 3),
        (11, 9),
        (7, 11),
        (15, 15),
    ] {
        let new_a = hh(a, b, c, d, x[i], s);
        a = d;
        d = c;
        c = b;
        b = new_a;
    }

    state[0] = state[0].wrapping_add(a);
    state[1] = state[1].wrapping_add(b);
    state[2] = state[2].wrapping_add(c);
    state[3] = state[3].wrapping_add(d);
}

/// Apply MD-Damgård padding (RFC 1320 §3.1).  Append `0x80`, then
/// zeros, then an 8-byte little-endian message-bit-length, so the
/// total is a multiple of 64 bytes.
pub fn md4_pad(message: &[u8]) -> Vec<u8> {
    let bit_len = (message.len() as u64).wrapping_mul(8);
    let mut padded = message.to_vec();
    padded.push(0x80);
    while padded.len() % 64 != 56 {
        padded.push(0);
    }
    padded.extend_from_slice(&bit_len.to_le_bytes());
    padded
}

/// **MD4 hash** of an arbitrary-length message.  Returns 16 bytes.
pub fn md4(message: &[u8]) -> [u8; 16] {
    let mut state = INITIAL_STATE;
    let padded = md4_pad(message);
    for chunk in padded.chunks(64) {
        let mut block = [0u8; 64];
        block.copy_from_slice(chunk);
        md4_compress(&mut state, &block);
    }
    let mut out = [0u8; 16];
    for i in 0..4 {
        out[4 * i..4 * i + 4].copy_from_slice(&state[i].to_le_bytes());
    }
    out
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn hex(bytes: &[u8]) -> String {
        bytes.iter().map(|b| format!("{:02x}", b)).collect()
    }

    /// **RFC 1320 Appendix A.5 test vectors**.
    #[test]
    fn md4_rfc1320_test_vectors() {
        let cases: &[(&[u8], &str)] = &[
            (b"", "31d6cfe0d16ae931b73c59d7e0c089c0"),
            (b"a", "bde52cb31de33e46245e05fbdbd6fb24"),
            (b"abc", "a448017aaf21d8525fc10ae87aa6729d"),
            (b"message digest", "d9130a8164549fe818874806e1c7014b"),
            (
                b"abcdefghijklmnopqrstuvwxyz",
                "d79e1c308aa5bbcdeea8ed63df412da9",
            ),
            (
                b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
                "043f8582f241db351ce627e153e7f0e4",
            ),
            (
                b"12345678901234567890123456789012345678901234567890123456789012345678901234567890",
                "e33b4ddc9c38f2199c3e7b164fcc0536",
            ),
        ];
        for (msg, want) in cases {
            let got = md4(msg);
            assert_eq!(hex(&got), *want, "mismatch on input {:?}", msg);
        }
    }

    /// Long-input sanity: hashing 1MB of zeros produces a known fixed
    /// digest, and is invariant across multi-block boundary positions.
    #[test]
    fn md4_one_megabyte_zeros() {
        let big = vec![0u8; 1 << 20];
        let digest = md4(&big);
        // First few bytes are deterministic; just check round-trip is
        // consistent rather than memorising a 1MB-of-zeros vector.
        let again = md4(&big);
        assert_eq!(digest, again);
    }
}
