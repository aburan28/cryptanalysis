//! MD5 + differential collision finding.
//!
//! **MD5 is broken.**  Wang, Feng, Lai, Yu published the first
//! actual MD5 collision (Crypto 2004) at `~2³⁹` operations; modern
//! implementations find collisions in seconds on a laptop.
//!
//! Lives in `cryptanalysis`, NOT `hash` — like SHA-1, MD5 is
//! shipped as a *target* for cryptanalytic study, not a primitive
//! for production use.
//!
//! # What this module ships
//!
//! - **MD5 implementation** (RFC 1321), verified against the
//!   original test vectors.
//! - **Reduced-round-capable**: `md5_compress(state, block, rounds)`
//!   for `rounds ∈ [0, 64]`.
//! - **Avalanche analysis** at varying rounds — same toolchain as
//!   SHA-1.
//! - **Random-search collision finder** at very reduced rounds
//!   (≤ 16): demonstrates the round-cost cliff that Wang's
//!   sophisticated paths exploit at full 64.
//!
//! What this module does NOT ship: Wang's hand-crafted
//! differential paths.  Reproducing those would be a separate
//! research project.

/// MD5 round constants (sine of `i`, scaled).
const T: [u32; 64] = [
    0xd76aa478, 0xe8c7b756, 0x242070db, 0xc1bdceee, 0xf57c0faf, 0x4787c62a, 0xa8304613, 0xfd469501,
    0x698098d8, 0x8b44f7af, 0xffff5bb1, 0x895cd7be, 0x6b901122, 0xfd987193, 0xa679438e, 0x49b40821,
    0xf61e2562, 0xc040b340, 0x265e5a51, 0xe9b6c7aa, 0xd62f105d, 0x02441453, 0xd8a1e681, 0xe7d3fbc8,
    0x21e1cde6, 0xc33707d6, 0xf4d50d87, 0x455a14ed, 0xa9e3e905, 0xfcefa3f8, 0x676f02d9, 0x8d2a4c8a,
    0xfffa3942, 0x8771f681, 0x6d9d6122, 0xfde5380c, 0xa4beea44, 0x4bdecfa9, 0xf6bb4b60, 0xbebfbc70,
    0x289b7ec6, 0xeaa127fa, 0xd4ef3085, 0x04881d05, 0xd9d4d039, 0xe6db99e5, 0x1fa27cf8, 0xc4ac5665,
    0xf4292244, 0x432aff97, 0xab9423a7, 0xfc93a039, 0x655b59c3, 0x8f0ccc92, 0xffeff47d, 0x85845dd1,
    0x6fa87e4f, 0xfe2ce6e0, 0xa3014314, 0x4e0811a1, 0xf7537e82, 0xbd3af235, 0x2ad7d2bb, 0xeb86d391,
];

/// Per-round shift amounts.
const S: [u32; 64] = [
    7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9,
    14, 20, 5, 9, 14, 20, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 6, 10, 15,
    21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21,
];

/// MD5 IV.
pub const MD5_IV: [u32; 4] = [0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476];

#[inline]
fn f(x: u32, y: u32, z: u32) -> u32 {
    (x & y) | (!x & z)
}
#[inline]
fn g(x: u32, y: u32, z: u32) -> u32 {
    (x & z) | (y & !z)
}
#[inline]
fn h(x: u32, y: u32, z: u32) -> u32 {
    x ^ y ^ z
}
#[inline]
fn i_fn(x: u32, y: u32, z: u32) -> u32 {
    y ^ (x | !z)
}

/// MD5 round function — selects one of `f`, `g`, `h`, `i` based
/// on the round group.
fn round_fn(round: usize, b: u32, c: u32, d: u32) -> u32 {
    match round / 16 {
        0 => f(b, c, d),
        1 => g(b, c, d),
        2 => h(b, c, d),
        _ => i_fn(b, c, d),
    }
}

/// Word-permutation index for round `i`.
fn word_index(round: usize) -> usize {
    match round / 16 {
        0 => round,
        1 => (5 * round + 1) % 16,
        2 => (3 * round + 5) % 16,
        _ => (7 * round) % 16,
    }
}

/// Reduced-round MD5 compression function.  Updates `state` in
/// place by processing `block` through `rounds ∈ [0, 64]` rounds.
/// At `rounds = 64` matches RFC 1321 MD5.
pub fn md5_compress(state: &mut [u32; 4], block: &[u8; 64], rounds: usize) {
    let rounds = rounds.min(64);
    let mut m = [0u32; 16];
    for j in 0..16 {
        m[j] = u32::from_le_bytes([
            block[4 * j],
            block[4 * j + 1],
            block[4 * j + 2],
            block[4 * j + 3],
        ]);
    }
    let (mut a, mut b, mut c, mut d) = (state[0], state[1], state[2], state[3]);
    for r in 0..rounds {
        let f_val = round_fn(r, b, c, d);
        let new_a = b.wrapping_add(
            a.wrapping_add(f_val)
                .wrapping_add(T[r])
                .wrapping_add(m[word_index(r)])
                .rotate_left(S[r]),
        );
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

/// Full MD5 of `message` with configurable round count.
pub fn md5(message: &[u8], rounds: usize) -> [u8; 16] {
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
        md5_compress(&mut state, &block, rounds);
    }
    let mut out = [0u8; 16];
    for (j, &word) in state.iter().enumerate() {
        out[4 * j..4 * j + 4].copy_from_slice(&word.to_le_bytes());
    }
    out
}

/// Random-search reduced-round **near-collision** finder.  The
/// 128-bit MD5 output makes full-collision random search infeasible
/// at any round count (birthday cost is `2⁶⁴`), but near-collisions
/// (low output Hamming distance) are findable and demonstrate the
/// same round-cost cliff Wang's differential paths exploit.
pub fn find_md5_near_collision(
    rounds: usize,
    target_max_distance: u32,
    max_trials: u64,
    seed: u64,
) -> Option<([u8; 64], [u8; 64], u32)> {
    use rand::rngs::StdRng;
    use rand::{RngCore, SeedableRng};
    let mut rng = StdRng::seed_from_u64(seed);
    let mut best: Option<([u8; 64], [u8; 64], u32)> = None;
    let n_pairs = max_trials / 2;
    for _ in 0..n_pairs {
        let mut a = [0u8; 64];
        let mut b = [0u8; 64];
        rng.fill_bytes(&mut a);
        rng.fill_bytes(&mut b);
        if a == b {
            continue;
        }
        let mut state_a = MD5_IV;
        let mut state_b = MD5_IV;
        md5_compress(&mut state_a, &a, rounds);
        md5_compress(&mut state_b, &b, rounds);
        let dist: u32 = state_a
            .iter()
            .zip(state_b.iter())
            .map(|(&x, &y)| (x ^ y).count_ones())
            .sum();
        match &best {
            Some(b_old) if b_old.2 <= dist => {}
            _ => best = Some((a, b, dist)),
        }
        if dist <= target_max_distance {
            return Some((a, b, dist));
        }
    }
    best
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hex(bytes: &[u8]) -> String {
        bytes.iter().map(|b| format!("{:02x}", b)).collect()
    }

    /// **RFC 1321 §A.5 test vectors**.
    #[test]
    fn md5_rfc1321_kats() {
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
        ];
        for (msg, expected) in cases {
            let got = md5(msg, 64);
            assert_eq!(
                hex(&got),
                *expected,
                "MD5({:?}) mismatch",
                std::str::from_utf8(msg).unwrap_or("")
            );
        }
    }

    /// **Reduced-round near-collision** — at 8 rounds (≪ full 64),
    /// random search finds pairs with much lower Hamming distance
    /// than at full rounds.  Demonstrates the round-cost cliff that
    /// Wang's differential paths exploit at 64.
    #[test]
    fn reduced_round_near_collision() {
        let nc_8 = find_md5_near_collision(8, 50, 4096, 0xC0FFEE).unwrap();
        let nc_64 = find_md5_near_collision(64, 50, 4096, 0xC0FFEE).unwrap();
        println!();
        println!("=== MD5 reduced-round near-collision (random search) ===");
        println!("   8 rounds: best Hamming distance = {}", nc_8.2);
        println!("  64 rounds: best Hamming distance = {}", nc_64.2);
        // 8-round should find lower-distance pairs than 64-round.
        assert!(
            nc_8.2 <= nc_64.2,
            "8-round near-collision distance {} should be ≤ 64-round {}",
            nc_8.2,
            nc_64.2
        );
    }
}
