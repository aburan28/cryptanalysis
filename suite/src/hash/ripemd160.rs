//! RIPEMD-160.
//!
//! Dobbertin, Bosselaers, Preneel (RIPE 1996).  160-bit hash with
//! two parallel chains (left and right) of 80 rounds each, each
//! built from different round functions and rotation amounts.
//!
//! # Why ship this
//!
//! Bitcoin uses RIPEMD-160 as the outer step of `HASH160 =
//! RIPEMD-160(SHA-256(pubkey))` — the pubkey-to-address
//! transformation for every legacy address (P2PKH, P2SH).  Without
//! it, the library cannot produce a Bitcoin address from a public
//! key and the [`crate::cryptanalysis::signature_corpus`] analyzer
//! cannot compare findings against published Bitcoin addresses.
//!
//! # Test corpus
//!
//! Verified against the test vectors published in the original
//! RIPEMD-160 paper (and reproduced in RFC 2286, RFC 4634):
//!
//! ```text
//! "" → 9c1185a5c5e9fc54612808977ee8f548b2258d31
//! "a" → 0bdc9d2d256b3ee9daae347be6f4dc835a467ffe
//! "abc" → 8eb208f7e05d987a9b044a8e98c6b087f15a0bfc
//! "message digest" → 5d0689ef49d2fae572b881b123a85ffa21595f36
//! ```

// ── Round constants ─────────────────────────────────────────────────

/// Initial hash values (RIPE 1996 §3.2).
pub const RIPEMD160_IV: [u32; 5] = [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0];

/// Left-line constants `K_j`.  Single round-group constant per
/// 16-round block (5 groups × 16 rounds).
const KL: [u32; 5] = [0x00000000, 0x5A827999, 0x6ED9EBA1, 0x8F1BBCDC, 0xA953FD4E];

/// Right-line constants `K'_j`.
const KR: [u32; 5] = [0x50A28BE6, 0x5C4DD124, 0x6D703EF3, 0x7A6D76E9, 0x00000000];

/// Left-line message-word permutation `r_j`.
const RL: [u32; 80] = [
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 7, 4, 13, 1, 10, 6, 15, 3, 12, 0, 9, 5,
    2, 14, 11, 8, 3, 10, 14, 4, 9, 15, 8, 1, 2, 7, 0, 6, 13, 11, 5, 12, 1, 9, 11, 10, 0, 8, 12, 4,
    13, 3, 7, 15, 14, 5, 6, 2, 4, 0, 5, 9, 7, 12, 2, 10, 14, 1, 3, 8, 11, 6, 15, 13,
];

/// Right-line message-word permutation `r'_j`.
const RR: [u32; 80] = [
    5, 14, 7, 0, 9, 2, 11, 4, 13, 6, 15, 8, 1, 10, 3, 12, 6, 11, 3, 7, 0, 13, 5, 10, 14, 15, 8, 12,
    4, 9, 1, 2, 15, 5, 1, 3, 7, 14, 6, 9, 11, 8, 12, 2, 10, 0, 4, 13, 8, 6, 4, 1, 3, 11, 15, 0, 5,
    12, 2, 13, 9, 7, 10, 14, 12, 15, 10, 4, 1, 5, 8, 7, 6, 2, 13, 14, 0, 3, 9, 11,
];

/// Left-line rotation amounts `s_j`.
const SL: [u32; 80] = [
    11, 14, 15, 12, 5, 8, 7, 9, 11, 13, 14, 15, 6, 7, 9, 8, 7, 6, 8, 13, 11, 9, 7, 15, 7, 12, 15,
    9, 11, 7, 13, 12, 11, 13, 6, 7, 14, 9, 13, 15, 14, 8, 13, 6, 5, 12, 7, 5, 11, 12, 14, 15, 14,
    15, 9, 8, 9, 14, 5, 6, 8, 6, 5, 12, 9, 15, 5, 11, 6, 8, 13, 12, 5, 12, 13, 14, 11, 8, 5, 6,
];

/// Right-line rotation amounts `s'_j`.
const SR: [u32; 80] = [
    8, 9, 9, 11, 13, 15, 15, 5, 7, 7, 8, 11, 14, 14, 12, 6, 9, 13, 15, 7, 12, 8, 9, 11, 7, 7, 12,
    7, 6, 15, 13, 11, 9, 7, 15, 11, 8, 6, 6, 14, 12, 13, 5, 14, 13, 13, 7, 5, 15, 5, 8, 11, 14, 14,
    6, 14, 6, 9, 12, 9, 12, 5, 15, 8, 8, 5, 12, 9, 12, 5, 14, 6, 8, 13, 6, 5, 15, 13, 11, 11,
];

/// Round-function selection.  `j ∈ [0, 80)` indexes the round; the
/// **round group** (0-15, 16-31, ..., 64-79) determines which of
/// `f1..f5` is applied — but the **left** and **right** chains use
/// the groups in *opposite* order.  Hence the two `f_*_left` /
/// `f_*_right` dispatchers below.
fn f_left(j: usize, x: u32, y: u32, z: u32) -> u32 {
    match j / 16 {
        0 => x ^ y ^ z,          // f1
        1 => (x & y) | (!x & z), // f2
        2 => (x | !y) ^ z,       // f3
        3 => (x & z) | (y & !z), // f4
        _ => x ^ (y | !z),       // f5
    }
}

fn f_right(j: usize, x: u32, y: u32, z: u32) -> u32 {
    match j / 16 {
        0 => x ^ (y | !z),       // f5
        1 => (x & z) | (y & !z), // f4
        2 => (x | !y) ^ z,       // f3
        3 => (x & y) | (!x & z), // f2
        _ => x ^ y ^ z,          // f1
    }
}

fn k_left(j: usize) -> u32 {
    KL[j / 16]
}
fn k_right(j: usize) -> u32 {
    KR[j / 16]
}

/// Process one 64-byte block, updating `state` in place.
fn compress(state: &mut [u32; 5], block: &[u8; 64]) {
    let mut w = [0u32; 16];
    for i in 0..16 {
        w[i] = u32::from_le_bytes([
            block[4 * i],
            block[4 * i + 1],
            block[4 * i + 2],
            block[4 * i + 3],
        ]);
    }

    let (mut al, mut bl, mut cl, mut dl, mut el) =
        (state[0], state[1], state[2], state[3], state[4]);
    let (mut ar, mut br, mut cr, mut dr, mut er) =
        (state[0], state[1], state[2], state[3], state[4]);

    for j in 0..80 {
        // Left line.
        let t = al
            .wrapping_add(f_left(j, bl, cl, dl))
            .wrapping_add(w[RL[j] as usize])
            .wrapping_add(k_left(j))
            .rotate_left(SL[j])
            .wrapping_add(el);
        al = el;
        el = dl;
        dl = cl.rotate_left(10);
        cl = bl;
        bl = t;

        // Right line.
        let t = ar
            .wrapping_add(f_right(j, br, cr, dr))
            .wrapping_add(w[RR[j] as usize])
            .wrapping_add(k_right(j))
            .rotate_left(SR[j])
            .wrapping_add(er);
        ar = er;
        er = dr;
        dr = cr.rotate_left(10);
        cr = br;
        br = t;
    }

    // Combine.
    let t = state[1].wrapping_add(cl).wrapping_add(dr);
    state[1] = state[2].wrapping_add(dl).wrapping_add(er);
    state[2] = state[3].wrapping_add(el).wrapping_add(ar);
    state[3] = state[4].wrapping_add(al).wrapping_add(br);
    state[4] = state[0].wrapping_add(bl).wrapping_add(cr);
    state[0] = t;
}

/// RIPEMD-160 of an arbitrary-length message.  Returns 20 bytes.
pub fn ripemd160(message: &[u8]) -> [u8; 20] {
    let mut state = RIPEMD160_IV;
    let bit_len = (message.len() as u64).wrapping_mul(8);

    // Pad: 0x80, then zeroes, then 8 bytes of bit-length (LE).
    let mut padded = message.to_vec();
    padded.push(0x80);
    while padded.len() % 64 != 56 {
        padded.push(0);
    }
    padded.extend_from_slice(&bit_len.to_le_bytes());

    for chunk in padded.chunks_exact(64) {
        let mut block = [0u8; 64];
        block.copy_from_slice(chunk);
        compress(&mut state, &block);
    }

    let mut out = [0u8; 20];
    for (i, &word) in state.iter().enumerate() {
        out[4 * i..4 * i + 4].copy_from_slice(&word.to_le_bytes());
    }
    out
}

/// Bitcoin's `HASH160 = RIPEMD-160(SHA-256(input))`.  The
/// canonical pubkey-to-address transformation.
pub fn hash160(input: &[u8]) -> [u8; 20] {
    let sha = crate::hash::sha256::sha256(input);
    ripemd160(&sha)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hex(bytes: &[u8]) -> String {
        bytes.iter().map(|b| format!("{:02x}", b)).collect()
    }

    /// **Original RIPE-1996 paper test vectors** (see RFC 4634
    /// appendix and the canonical RIPEMD-160 reference page).
    #[test]
    fn ripemd160_test_vectors() {
        let cases: &[(&[u8], &str)] = &[
            (b"", "9c1185a5c5e9fc54612808977ee8f548b2258d31"),
            (b"a", "0bdc9d2d256b3ee9daae347be6f4dc835a467ffe"),
            (b"abc", "8eb208f7e05d987a9b044a8e98c6b087f15a0bfc"),
            (
                b"message digest",
                "5d0689ef49d2fae572b881b123a85ffa21595f36",
            ),
            (
                b"abcdefghijklmnopqrstuvwxyz",
                "f71c27109c692c1b56bbdceb5b9d2865b3708dbc",
            ),
        ];
        for (msg, expected) in cases {
            let got = ripemd160(msg);
            assert_eq!(
                hex(&got),
                *expected,
                "RIPEMD-160({:?}) mismatch",
                std::str::from_utf8(msg).unwrap_or("")
            );
        }
    }

    /// Long-message KAT: `"a" × 1,000,000` → `52783243c1697bdb...`.
    /// A standard sanity test for any RIPEMD-160 implementation.
    #[test]
    fn ripemd160_million_a() {
        let msg = vec![b'a'; 1_000_000];
        let got = ripemd160(&msg);
        assert_eq!(hex(&got), "52783243c1697bdbe16d37f97f68f08325dc1528",);
    }

    /// `HASH160` smoke test: a known Bitcoin pubkey → address-hash.
    /// Public key (compressed, hex):
    ///   `02b4632d08485ff1df2db55b9dafd23347d1c47a457072a1e87be26896549a8737`
    /// HASH160 = `93ce48570b55c42c2af816aeaba06cfee1224fae`
    /// (Standard Bitcoin test vector; address `1EHNa6Q4Jz2uvNExL497mE43ikXhwF6kZm`)
    #[test]
    fn hash160_known_bitcoin_pubkey() {
        let pubkey: [u8; 33] = [
            0x02, 0xb4, 0x63, 0x2d, 0x08, 0x48, 0x5f, 0xf1, 0xdf, 0x2d, 0xb5, 0x5b, 0x9d, 0xaf,
            0xd2, 0x33, 0x47, 0xd1, 0xc4, 0x7a, 0x45, 0x70, 0x72, 0xa1, 0xe8, 0x7b, 0xe2, 0x68,
            0x96, 0x54, 0x9a, 0x87, 0x37,
        ];
        let h160 = hash160(&pubkey);
        assert_eq!(hex(&h160), "93ce48570b55c42c2af816aeaba06cfee1224fae");
    }
}
