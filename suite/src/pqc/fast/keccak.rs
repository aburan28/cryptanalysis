//! Keccak-f1600 and a streaming sponge, for the post-quantum schemes.
//!
//! `hash::sha3` is the readable implementation and stays the reference; this is
//! the same permutation written for speed, plus the streaming interface the
//! lattice schemes need.
//!
//! Two things matter here beyond the permutation itself:
//!
//! * **Squeezing is incremental.** ML-KEM's matrix expansion rejection-samples
//!   from SHAKE128 and cannot know in advance how many bytes it will consume.
//!   A one-shot XOF forces the caller to restart the whole sponge with a longer
//!   output request when the buffer runs out, which repeats every permutation
//!   already done. `squeeze_blocks` continues the same state instead.
//! * **Nothing allocates.** Absorbing borrows the input and writes straight
//!   into the lane array; squeezing writes into a caller-owned buffer. The
//!   schemes call this tens of times per operation with inputs of 32 to 64
//!   bytes, where a heap allocation costs more than the permutation.
//!
//! The permutation is validated against `hash::sha3` on random inputs, and the
//! sponge against the NIST SHA-3 and SHAKE known-answer tests, in the tests at
//! the bottom of this file.

/// Round constants for the ι step (24 rounds of Keccak-f[1600]).
const RC: [u64; 24] = [
    0x0000_0000_0000_0001,
    0x0000_0000_0000_8082,
    0x8000_0000_0000_808a,
    0x8000_0000_8000_8000,
    0x0000_0000_0000_808b,
    0x0000_0000_8000_0001,
    0x8000_0000_8000_8081,
    0x8000_0000_0000_8009,
    0x0000_0000_0000_008a,
    0x0000_0000_0000_0088,
    0x0000_0000_8000_8009,
    0x0000_0000_8000_000a,
    0x0000_0000_8000_808b,
    0x8000_0000_0000_008b,
    0x8000_0000_0000_8089,
    0x8000_0000_0000_8003,
    0x8000_0000_0000_8002,
    0x8000_0000_0000_0080,
    0x0000_0000_0000_800a,
    0x8000_0000_8000_000a,
    0x8000_0000_8000_8081,
    0x8000_0000_0000_8080,
    0x0000_0000_8000_0001,
    0x8000_0000_8000_8008,
];

/// Keccak-f1600, in place.
///
/// The lanes are held in named locals rather than indexed out of the array, so
/// every rotation amount is a constant and the ρ/π permutation is register
/// renaming rather than a scratch array and a modulo. That is the whole
/// difference from the readable version in `hash::sha3`.
pub fn keccak_f1600(state: &mut [u64; 25]) {
    let mut a00 = state[0];
    let mut a01 = state[1];
    let mut a02 = state[2];
    let mut a03 = state[3];
    let mut a04 = state[4];
    let mut a05 = state[5];
    let mut a06 = state[6];
    let mut a07 = state[7];
    let mut a08 = state[8];
    let mut a09 = state[9];
    let mut a10 = state[10];
    let mut a11 = state[11];
    let mut a12 = state[12];
    let mut a13 = state[13];
    let mut a14 = state[14];
    let mut a15 = state[15];
    let mut a16 = state[16];
    let mut a17 = state[17];
    let mut a18 = state[18];
    let mut a19 = state[19];
    let mut a20 = state[20];
    let mut a21 = state[21];
    let mut a22 = state[22];
    let mut a23 = state[23];
    let mut a24 = state[24];

    for &rc in RC.iter() {
        // θ
        let c0 = a00 ^ a05 ^ a10 ^ a15 ^ a20;
        let c1 = a01 ^ a06 ^ a11 ^ a16 ^ a21;
        let c2 = a02 ^ a07 ^ a12 ^ a17 ^ a22;
        let c3 = a03 ^ a08 ^ a13 ^ a18 ^ a23;
        let c4 = a04 ^ a09 ^ a14 ^ a19 ^ a24;

        let d0 = c4 ^ c1.rotate_left(1);
        let d1 = c0 ^ c2.rotate_left(1);
        let d2 = c1 ^ c3.rotate_left(1);
        let d3 = c2 ^ c4.rotate_left(1);
        let d4 = c3 ^ c0.rotate_left(1);

        a00 ^= d0;
        a05 ^= d0;
        a10 ^= d0;
        a15 ^= d0;
        a20 ^= d0;
        a01 ^= d1;
        a06 ^= d1;
        a11 ^= d1;
        a16 ^= d1;
        a21 ^= d1;
        a02 ^= d2;
        a07 ^= d2;
        a12 ^= d2;
        a17 ^= d2;
        a22 ^= d2;
        a03 ^= d3;
        a08 ^= d3;
        a13 ^= d3;
        a18 ^= d3;
        a23 ^= d3;
        a04 ^= d4;
        a09 ^= d4;
        a14 ^= d4;
        a19 ^= d4;
        a24 ^= d4;

        // ρ and π together: b[π(i)] = rot(a[i], ρ(i)), all constants.
        let b00 = a00;
        let b01 = a06.rotate_left(44);
        let b02 = a12.rotate_left(43);
        let b03 = a18.rotate_left(21);
        let b04 = a24.rotate_left(14);
        let b05 = a03.rotate_left(28);
        let b06 = a09.rotate_left(20);
        let b07 = a10.rotate_left(3);
        let b08 = a16.rotate_left(45);
        let b09 = a22.rotate_left(61);
        let b10 = a01.rotate_left(1);
        let b11 = a07.rotate_left(6);
        let b12 = a13.rotate_left(25);
        let b13 = a19.rotate_left(8);
        let b14 = a20.rotate_left(18);
        let b15 = a04.rotate_left(27);
        let b16 = a05.rotate_left(36);
        let b17 = a11.rotate_left(10);
        let b18 = a17.rotate_left(15);
        let b19 = a23.rotate_left(56);
        let b20 = a02.rotate_left(62);
        let b21 = a08.rotate_left(55);
        let b22 = a14.rotate_left(39);
        let b23 = a15.rotate_left(41);
        let b24 = a21.rotate_left(2);

        // χ
        a00 = b00 ^ (!b01 & b02);
        a01 = b01 ^ (!b02 & b03);
        a02 = b02 ^ (!b03 & b04);
        a03 = b03 ^ (!b04 & b00);
        a04 = b04 ^ (!b00 & b01);
        a05 = b05 ^ (!b06 & b07);
        a06 = b06 ^ (!b07 & b08);
        a07 = b07 ^ (!b08 & b09);
        a08 = b08 ^ (!b09 & b05);
        a09 = b09 ^ (!b05 & b06);
        a10 = b10 ^ (!b11 & b12);
        a11 = b11 ^ (!b12 & b13);
        a12 = b12 ^ (!b13 & b14);
        a13 = b13 ^ (!b14 & b10);
        a14 = b14 ^ (!b10 & b11);
        a15 = b15 ^ (!b16 & b17);
        a16 = b16 ^ (!b17 & b18);
        a17 = b17 ^ (!b18 & b19);
        a18 = b18 ^ (!b19 & b15);
        a19 = b19 ^ (!b15 & b16);
        a20 = b20 ^ (!b21 & b22);
        a21 = b21 ^ (!b22 & b23);
        a22 = b22 ^ (!b23 & b24);
        a23 = b23 ^ (!b24 & b20);
        a24 = b24 ^ (!b20 & b21);

        // ι
        a00 ^= rc;
    }

    state[0] = a00;
    state[1] = a01;
    state[2] = a02;
    state[3] = a03;
    state[4] = a04;
    state[5] = a05;
    state[6] = a06;
    state[7] = a07;
    state[8] = a08;
    state[9] = a09;
    state[10] = a10;
    state[11] = a11;
    state[12] = a12;
    state[13] = a13;
    state[14] = a14;
    state[15] = a15;
    state[16] = a16;
    state[17] = a17;
    state[18] = a18;
    state[19] = a19;
    state[20] = a20;
    state[21] = a21;
    state[22] = a22;
    state[23] = a23;
    state[24] = a24;
}

/// Rate in bytes of SHAKE128 (and SHA3-128-equivalent security level).
pub const SHAKE128_RATE: usize = 168;
/// Rate in bytes of SHAKE256, SHA3-256 and SHA3-512's sponge.
pub const SHAKE256_RATE: usize = 136;
/// Rate in bytes of SHA3-256.
pub const SHA3_256_RATE: usize = 136;
/// Rate in bytes of SHA3-512.
pub const SHA3_512_RATE: usize = 72;

/// A Keccak sponge that can be absorbed into and squeezed from in pieces.
///
/// `RATE` is the block size in bytes. The state is 200 bytes; the capacity is
/// whatever the rate leaves.
#[derive(Clone)]
pub struct Sponge<const RATE: usize> {
    s: [u64; 25],
    /// Bytes buffered into the current block: an absorb offset before
    /// `finalize`, a squeeze offset after it.
    pos: usize,
}

impl<const RATE: usize> Default for Sponge<RATE> {
    fn default() -> Self {
        Self::new()
    }
}

impl<const RATE: usize> Sponge<RATE> {
    pub fn new() -> Self {
        Sponge {
            s: [0u64; 25],
            pos: 0,
        }
    }

    /// XOR one byte into the state at byte offset `i`.
    #[inline(always)]
    fn xor_byte(&mut self, i: usize, b: u8) {
        self.s[i / 8] ^= (b as u64) << (8 * (i % 8));
    }

    /// Absorb `data`, which may be any length and may be called repeatedly.
    pub fn absorb(&mut self, data: &[u8]) {
        let mut off = 0;
        // Finish a partially filled block one byte at a time; whole blocks
        // below go eight bytes at a time.
        while off < data.len() && !self.pos.is_multiple_of(8) {
            self.xor_byte(self.pos, data[off]);
            self.pos += 1;
            off += 1;
            if self.pos == RATE {
                keccak_f1600(&mut self.s);
                self.pos = 0;
            }
        }
        while off < data.len() {
            let room = RATE - self.pos;
            let take = room.min(data.len() - off);
            let chunk = &data[off..off + take];
            let base = self.pos / 8;
            let whole = take / 8;
            for i in 0..whole {
                let mut w = [0u8; 8];
                w.copy_from_slice(&chunk[8 * i..8 * i + 8]);
                self.s[base + i] ^= u64::from_le_bytes(w);
            }
            for i in 8 * whole..take {
                self.xor_byte(self.pos + i, chunk[i]);
            }
            self.pos += take;
            off += take;
            if self.pos == RATE {
                keccak_f1600(&mut self.s);
                self.pos = 0;
            }
        }
    }

    /// Apply the padding for domain-separation byte `suffix` (0x1f for SHAKE,
    /// 0x06 for SHA-3) and switch the sponge to squeezing.
    pub fn finalize(&mut self, suffix: u8) {
        self.xor_byte(self.pos, suffix);
        self.xor_byte(RATE - 1, 0x80);
        keccak_f1600(&mut self.s);
        self.pos = 0;
    }

    /// Squeeze `out.len()` bytes, continuing the stream across calls.
    ///
    /// Whole lanes are written eight bytes at a time; only the ragged ends of a
    /// request go byte by byte.  The rejection samplers squeeze a whole block
    /// at a time, so in practice this is the lane path throughout.
    pub fn squeeze(&mut self, out: &mut [u8]) {
        let mut off = 0;
        while off < out.len() {
            if self.pos == RATE {
                keccak_f1600(&mut self.s);
                self.pos = 0;
            }
            let take = (RATE - self.pos).min(out.len() - off);
            let mut i = 0;
            // Ragged head: up to seven bytes to reach a lane boundary.
            while i < take && !(self.pos + i).is_multiple_of(8) {
                let j = self.pos + i;
                out[off + i] = (self.s[j / 8] >> (8 * (j % 8))) as u8;
                i += 1;
            }
            while i + 8 <= take {
                let j = self.pos + i;
                out[off + i..off + i + 8].copy_from_slice(&self.s[j / 8].to_le_bytes());
                i += 8;
            }
            while i < take {
                let j = self.pos + i;
                out[off + i] = (self.s[j / 8] >> (8 * (j % 8))) as u8;
                i += 1;
            }
            self.pos += take;
            off += take;
        }
    }

    /// Squeeze exactly `n` whole blocks. Cheaper than `squeeze` when the caller
    /// works a block at a time, which the rejection samplers do.
    pub fn squeeze_blocks(&mut self, out: &mut [u8], n: usize) {
        debug_assert!(out.len() >= n * RATE);
        debug_assert_eq!(self.pos % RATE, 0);
        for blk in 0..n {
            if self.pos == RATE || (blk > 0) {
                keccak_f1600(&mut self.s);
            }
            self.pos = 0;
            for j in 0..RATE {
                out[blk * RATE + j] = (self.s[j / 8] >> (8 * (j % 8))) as u8;
            }
        }
        self.pos = RATE;
    }
}

// ── one-shot helpers ─────────────────────────────────────────────────────────

/// SHAKE128 with the output length known up front.
pub fn shake128_into(out: &mut [u8], input: &[u8]) {
    let mut s = Sponge::<SHAKE128_RATE>::new();
    s.absorb(input);
    s.finalize(0x1f);
    s.squeeze(out);
}

/// SHAKE256 with the output length known up front.
pub fn shake256_into(out: &mut [u8], input: &[u8]) {
    let mut s = Sponge::<SHAKE256_RATE>::new();
    s.absorb(input);
    s.finalize(0x1f);
    s.squeeze(out);
}

/// SHAKE256 over the concatenation of two pieces, without joining them first.
pub fn shake256_2_into(out: &mut [u8], a: &[u8], b: &[u8]) {
    let mut s = Sponge::<SHAKE256_RATE>::new();
    s.absorb(a);
    s.absorb(b);
    s.finalize(0x1f);
    s.squeeze(out);
}

/// SHA3-256.
pub fn sha3_256(input: &[u8]) -> [u8; 32] {
    let mut s = Sponge::<SHA3_256_RATE>::new();
    s.absorb(input);
    s.finalize(0x06);
    let mut out = [0u8; 32];
    s.squeeze(&mut out);
    out
}

/// SHA3-512 over the concatenation of two pieces.
pub fn sha3_512_2(a: &[u8], b: &[u8]) -> [u8; 64] {
    let mut s = Sponge::<SHA3_512_RATE>::new();
    s.absorb(a);
    s.absorb(b);
    s.finalize(0x06);
    let mut out = [0u8; 64];
    s.squeeze(&mut out);
    out
}

/// SHA3-512.
pub fn sha3_512(input: &[u8]) -> [u8; 64] {
    sha3_512_2(input, &[])
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hash::sha3 as slow;

    /// The permutation itself, against the readable implementation, from
    /// states with no structure for a bug to hide behind.
    #[test]
    fn permutation_matches_the_reference() {
        let mut x = 0x1234_5678_9abc_def0u64;
        for _ in 0..64 {
            let mut a = [0u64; 25];
            for lane in a.iter_mut() {
                // xorshift64: any cheap full-period generator will do here.
                x ^= x << 13;
                x ^= x >> 7;
                x ^= x << 17;
                *lane = x;
            }
            let mut b = a;
            keccak_f1600(&mut a);
            slow::keccak_f(&mut b);
            assert_eq!(a, b);
        }
    }

    #[test]
    fn sha3_matches_the_reference_at_every_length_across_a_block() {
        // 0..300 bytes covers empty, short, exactly one block, and the
        // boundary where padding needs a second permutation, for both rates.
        let msg: Vec<u8> = (0..300u32).map(|i| (i * 7 + 1) as u8).collect();
        for len in 0..msg.len() {
            assert_eq!(
                sha3_256(&msg[..len]).to_vec(),
                slow::sha3_256(&msg[..len]),
                "sha3-256 length {len}"
            );
            assert_eq!(
                sha3_512(&msg[..len]).to_vec(),
                slow::sha3_512(&msg[..len]),
                "sha3-512 length {len}"
            );
        }
    }

    #[test]
    fn shake_matches_the_reference_at_every_length_across_a_block() {
        let msg: Vec<u8> = (0..200u32).map(|i| (i * 13 + 5) as u8).collect();
        for len in [0usize, 1, 31, 32, 135, 136, 137, 167, 168, 169, 199] {
            for outlen in [1usize, 32, 135, 136, 168, 169, 504, 600] {
                let mut got = vec![0u8; outlen];
                shake128_into(&mut got, &msg[..len]);
                assert_eq!(
                    got,
                    slow::shake128(&msg[..len], outlen),
                    "shake128 {len}->{outlen}"
                );

                let mut got = vec![0u8; outlen];
                shake256_into(&mut got, &msg[..len]);
                assert_eq!(
                    got,
                    slow::shake256(&msg[..len], outlen),
                    "shake256 {len}->{outlen}"
                );
            }
        }
    }

    /// The property the one-shot XOF could not offer: squeezing in pieces has
    /// to give the same stream as squeezing all at once. ML-KEM's matrix
    /// expansion depends on this and was re-running the sponge without it.
    #[test]
    fn incremental_squeezing_continues_the_stream() {
        let seed = [9u8; 34];
        let mut whole = [0u8; 168 * 4];
        shake128_into(&mut whole, &seed);

        let mut s = Sponge::<SHAKE128_RATE>::new();
        s.absorb(&seed);
        s.finalize(0x1f);
        let mut piece = [0u8; 168 * 4];
        // Deliberately ragged: 1, 2, 3, ... bytes at a time across block ends.
        let mut off = 0;
        let mut n = 1;
        while off < piece.len() {
            let take = n.min(piece.len() - off);
            s.squeeze(&mut piece[off..off + take]);
            off += take;
            n += 1;
        }
        assert_eq!(whole, piece);
    }

    #[test]
    fn squeeze_blocks_agrees_with_squeeze() {
        let seed = [4u8; 34];
        let mut a = [0u8; 168 * 3];
        shake128_into(&mut a, &seed);

        let mut s = Sponge::<SHAKE128_RATE>::new();
        s.absorb(&seed);
        s.finalize(0x1f);
        let mut b = [0u8; 168 * 3];
        s.squeeze_blocks(&mut b, 3);
        assert_eq!(a, b);
    }

    #[test]
    fn absorbing_in_pieces_matches_absorbing_at_once() {
        let msg: Vec<u8> = (0..500u32).map(|i| (i * 3 + 2) as u8).collect();
        let mut whole = [0u8; 64];
        shake256_into(&mut whole, &msg);

        for split in [0usize, 1, 7, 8, 9, 135, 136, 137, 271, 499] {
            let mut s = Sponge::<SHAKE256_RATE>::new();
            s.absorb(&msg[..split]);
            s.absorb(&msg[split..]);
            s.finalize(0x1f);
            let mut got = [0u8; 64];
            s.squeeze(&mut got);
            assert_eq!(whole, got, "split at {split}");
        }
    }

    #[test]
    fn two_part_helpers_match_the_concatenation() {
        let a = [1u8; 40];
        let b = [2u8; 90];
        let mut joined = a.to_vec();
        joined.extend_from_slice(&b);

        assert_eq!(sha3_512_2(&a, &b).to_vec(), slow::sha3_512(&joined));

        let mut got = [0u8; 64];
        shake256_2_into(&mut got, &a, &b);
        assert_eq!(got.to_vec(), slow::shake256(&joined, 64));
    }
}
