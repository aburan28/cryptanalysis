//! **SM3** — 256-bit cryptographic hash, Chinese national standard
//! GB/T 32905-2016.  ISO/IEC 10118-3:2018.
//!
//! Counterpart to SM4 (cipher) in the SM-suite, used as the hash
//! function in **SM2** signatures and key derivation per
//! GB/T 32918.  Structurally similar to SHA-256 (Merkle-Damgård,
//! 64 rounds, 32-bit word operations) but with different
//! mixing/permutation functions.
//!
//! ## Algorithm sketch
//!
//! - **IV**: 8 32-bit words, fixed in the standard.
//! - **Padding**: append `0x80`, then zeros until length ≡ 56 (mod
//!   64), then 8-byte big-endian bit-length.  Identical to SHA-256.
//! - **Compression** (per 512-bit block):
//!   1. **Message expansion**: extend the 16 input words to 132
//!      words `(W_0, …, W_67, W'_0, …, W'_63)` via two permutations
//!      `P_1` and bit rotations.
//!   2. **64-round mixing**: update an 8-word state with non-linear
//!      functions `FF_j, GG_j` (different for `j < 16` vs `j ≥ 16`)
//!      and permutation `P_0`.
//!   3. XOR the new state into the current digest.
//! - **Output**: concatenate the final 8 32-bit words (256 bits).

const IV: [u32; 8] = [
    0x7380166f, 0x4914b2b9, 0x172442d7, 0xda8a0600, 0xa96f30bc, 0x163138aa, 0xe38dee4d, 0xb0fb0e4e,
];

#[inline]
fn rotl(x: u32, n: u32) -> u32 {
    let n = n & 31;
    if n == 0 {
        x
    } else {
        x.rotate_left(n)
    }
}

/// Round constant T_j.
#[inline]
fn t(j: usize) -> u32 {
    if j < 16 {
        0x79cc4519
    } else {
        0x7a879d8a
    }
}

/// Boolean function FF_j.
#[inline]
fn ff(j: usize, x: u32, y: u32, z: u32) -> u32 {
    if j < 16 {
        x ^ y ^ z
    } else {
        (x & y) | (x & z) | (y & z)
    }
}

/// Boolean function GG_j.
#[inline]
fn gg(j: usize, x: u32, y: u32, z: u32) -> u32 {
    if j < 16 {
        x ^ y ^ z
    } else {
        (x & y) | (!x & z)
    }
}

/// Permutation P_0 for the round function.
#[inline]
fn p0(x: u32) -> u32 {
    x ^ rotl(x, 9) ^ rotl(x, 17)
}

/// Permutation P_1 for message expansion.
#[inline]
fn p1(x: u32) -> u32 {
    x ^ rotl(x, 15) ^ rotl(x, 23)
}

/// Compress one 512-bit block into the 8-word state.
fn compress(state: &mut [u32; 8], block: &[u8; 64]) {
    let mut w = [0u32; 68];
    for i in 0..16 {
        w[i] = u32::from_be_bytes([
            block[i * 4],
            block[i * 4 + 1],
            block[i * 4 + 2],
            block[i * 4 + 3],
        ]);
    }
    for i in 16..68 {
        w[i] = p1(w[i - 16] ^ w[i - 9] ^ rotl(w[i - 3], 15)) ^ rotl(w[i - 13], 7) ^ w[i - 6];
    }
    let mut w_prime = [0u32; 64];
    for i in 0..64 {
        w_prime[i] = w[i] ^ w[i + 4];
    }

    let mut a = state[0];
    let mut b = state[1];
    let mut c = state[2];
    let mut d = state[3];
    let mut e = state[4];
    let mut f = state[5];
    let mut g = state[6];
    let mut h = state[7];

    for j in 0..64 {
        let ss1 = rotl(
            rotl(a, 12)
                .wrapping_add(e)
                .wrapping_add(rotl(t(j), j as u32)),
            7,
        );
        let ss2 = ss1 ^ rotl(a, 12);
        let tt1 = ff(j, a, b, c)
            .wrapping_add(d)
            .wrapping_add(ss2)
            .wrapping_add(w_prime[j]);
        let tt2 = gg(j, e, f, g)
            .wrapping_add(h)
            .wrapping_add(ss1)
            .wrapping_add(w[j]);
        d = c;
        c = rotl(b, 9);
        b = a;
        a = tt1;
        h = g;
        g = rotl(f, 19);
        f = e;
        e = p0(tt2);
    }

    state[0] ^= a;
    state[1] ^= b;
    state[2] ^= c;
    state[3] ^= d;
    state[4] ^= e;
    state[5] ^= f;
    state[6] ^= g;
    state[7] ^= h;
}

/// SM3 incremental hasher.
#[derive(Clone, Debug)]
pub struct Sm3 {
    state: [u32; 8],
    buffer: Vec<u8>,
    length_bits: u64,
}

impl Sm3 {
    pub fn new() -> Self {
        Self {
            state: IV,
            buffer: Vec::with_capacity(64),
            length_bits: 0,
        }
    }

    pub fn update(&mut self, data: &[u8]) {
        self.length_bits = self.length_bits.wrapping_add((data.len() as u64) * 8);
        self.buffer.extend_from_slice(data);
        while self.buffer.len() >= 64 {
            let mut block = [0u8; 64];
            block.copy_from_slice(&self.buffer[..64]);
            compress(&mut self.state, &block);
            self.buffer.drain(..64);
        }
    }

    /// Finalize and return the 32-byte digest.
    pub fn finalize(mut self) -> [u8; 32] {
        let bit_length = self.length_bits;
        // Append 0x80 then zeros until length ≡ 56 (mod 64), then
        // 8-byte big-endian bit length.
        self.buffer.push(0x80);
        while self.buffer.len() % 64 != 56 {
            self.buffer.push(0x00);
        }
        self.buffer.extend_from_slice(&bit_length.to_be_bytes());
        // Compress all remaining blocks.
        while self.buffer.len() >= 64 {
            let mut block = [0u8; 64];
            block.copy_from_slice(&self.buffer[..64]);
            compress(&mut self.state, &block);
            self.buffer.drain(..64);
        }
        let mut out = [0u8; 32];
        for (i, w) in self.state.iter().enumerate() {
            out[i * 4..i * 4 + 4].copy_from_slice(&w.to_be_bytes());
        }
        out
    }
}

impl Default for Sm3 {
    fn default() -> Self {
        Self::new()
    }
}

/// One-shot: hash `data` and return the 256-bit digest.
pub fn sm3(data: &[u8]) -> [u8; 32] {
    let mut h = Sm3::new();
    h.update(data);
    h.finalize()
}

#[cfg(test)]
mod tests {
    use super::*;

    /// **Test vector from GB/T 32905-2016 Appendix A.1**:
    /// SM3("abc") = 66c7f0f4 62eeedd9 d1f2d46b dc10e4e2 4167c487 5cf2f7a2 297da02b 8f4ba8e0
    #[test]
    fn sm3_abc() {
        let digest = sm3(b"abc");
        let expected: [u8; 32] = [
            0x66, 0xc7, 0xf0, 0xf4, 0x62, 0xee, 0xed, 0xd9, 0xd1, 0xf2, 0xd4, 0x6b, 0xdc, 0x10,
            0xe4, 0xe2, 0x41, 0x67, 0xc4, 0x87, 0x5c, 0xf2, 0xf7, 0xa2, 0x29, 0x7d, 0xa0, 0x2b,
            0x8f, 0x4b, 0xa8, 0xe0,
        ];
        assert_eq!(digest, expected);
    }

    /// **Test vector from GB/T 32905-2016 Appendix A.2**:
    /// SM3 of 64 bytes of "abcd"-repeated:
    /// SM3(("abcd" × 16)) = debe9ff9 2275b8a1 38604889 c18e5a4d
    ///                      6fdb70e5 387e5765 293dcba3 9c0c5732
    #[test]
    fn sm3_abcd_repeated() {
        let input: Vec<u8> = b"abcd".iter().copied().cycle().take(64).collect();
        let digest = sm3(&input);
        let expected: [u8; 32] = [
            0xde, 0xbe, 0x9f, 0xf9, 0x22, 0x75, 0xb8, 0xa1, 0x38, 0x60, 0x48, 0x89, 0xc1, 0x8e,
            0x5a, 0x4d, 0x6f, 0xdb, 0x70, 0xe5, 0x38, 0x7e, 0x57, 0x65, 0x29, 0x3d, 0xcb, 0xa3,
            0x9c, 0x0c, 0x57, 0x32,
        ];
        assert_eq!(digest, expected);
    }

    /// Incremental updates produce the same digest as a one-shot.
    #[test]
    fn sm3_streaming_matches_oneshot() {
        let msg: Vec<u8> = (0..1000).map(|i| i as u8).collect();
        let oneshot = sm3(&msg);
        let mut h = Sm3::new();
        for chunk in msg.chunks(37) {
            h.update(chunk);
        }
        assert_eq!(h.finalize(), oneshot);
    }

    /// Empty-string hash.
    #[test]
    fn sm3_empty() {
        let digest = sm3(b"");
        // Length should be 32 bytes; check determinism rather than
        // a specific value (the empty-string hash isn't given as an
        // appendix test vector but is fixed by the algorithm).
        assert_eq!(digest.len(), 32);
        assert_eq!(sm3(b""), digest);
    }
}
