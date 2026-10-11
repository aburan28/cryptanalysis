//! SHA-256 implemented from scratch per FIPS 180-4.
//!
//! # Algorithm outline
//! 1. Pre-process: pad the message to a multiple of 512 bits.
//! 2. Parse into 512-bit blocks.
//! 3. For each block, expand the 16-word message schedule to 64 words,
//!    then run the 64-round compression function against eight 32-bit
//!    working variables (a–h), mixing in round constants K[0..63].
//! 4. Add the compressed block into the running hash value.
//! 5. Concatenate the final eight 32-bit words as big-endian bytes.

/// The eight initial hash values — first 32 bits of the fractional parts
/// of the square roots of the first 8 primes.
const H0: [u32; 8] = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
];

/// The 64 round constants — first 32 bits of the fractional parts of the
/// cube roots of the first 64 primes.
const K: [u32; 64] = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

// ── Bitwise operations ───────────────────────────────────────────────────────

#[inline]
fn rotr32(x: u32, n: u32) -> u32 {
    x.rotate_right(n)
}
#[inline]
fn ch(e: u32, f: u32, g: u32) -> u32 {
    (e & f) ^ (!e & g)
}
#[inline]
fn maj(a: u32, b: u32, c: u32) -> u32 {
    (a & b) ^ (a & c) ^ (b & c)
}
#[inline]
fn sigma0(a: u32) -> u32 {
    rotr32(a, 2) ^ rotr32(a, 13) ^ rotr32(a, 22)
}
#[inline]
fn sigma1(e: u32) -> u32 {
    rotr32(e, 6) ^ rotr32(e, 11) ^ rotr32(e, 25)
}
#[inline]
fn gamma0(x: u32) -> u32 {
    rotr32(x, 7) ^ rotr32(x, 18) ^ (x >> 3)
}
#[inline]
fn gamma1(x: u32) -> u32 {
    rotr32(x, 17) ^ rotr32(x, 19) ^ (x >> 10)
}

// ── Padding ──────────────────────────────────────────────────────────────────

/// Pad a message to a multiple of 64 bytes (512 bits):
///   append bit '1', then zeros, then the 64-bit big-endian message length.
fn pad(msg: &[u8]) -> Vec<u8> {
    let bit_len = (msg.len() as u64).wrapping_mul(8);
    let mut out = msg.to_vec();
    out.push(0x80);
    while out.len() % 64 != 56 {
        out.push(0x00);
    }
    out.extend_from_slice(&bit_len.to_be_bytes());
    out
}

// ── Compression ──────────────────────────────────────────────────────────────

fn compress(state: &mut [u32; 8], block: &[u8]) {
    // Build the 64-word message schedule W from the 16 input words.
    let mut w = [0u32; 64];
    for i in 0..16 {
        w[i] = u32::from_be_bytes(block[i * 4..i * 4 + 4].try_into().unwrap());
    }
    for i in 16..64 {
        w[i] = gamma1(w[i - 2])
            .wrapping_add(w[i - 7])
            .wrapping_add(gamma0(w[i - 15]))
            .wrapping_add(w[i - 16]);
    }

    let mut a = state[0];
    let mut b = state[1];
    let mut c = state[2];
    let mut d = state[3];
    let mut e = state[4];
    let mut f = state[5];
    let mut g = state[6];
    let mut h = state[7];

    for i in 0..64 {
        let t1 = h
            .wrapping_add(sigma1(e))
            .wrapping_add(ch(e, f, g))
            .wrapping_add(K[i])
            .wrapping_add(w[i]);
        let t2 = sigma0(a).wrapping_add(maj(a, b, c));
        h = g;
        g = f;
        f = e;
        e = d.wrapping_add(t1);
        d = c;
        c = b;
        b = a;
        a = t1.wrapping_add(t2);
    }

    state[0] = state[0].wrapping_add(a);
    state[1] = state[1].wrapping_add(b);
    state[2] = state[2].wrapping_add(c);
    state[3] = state[3].wrapping_add(d);
    state[4] = state[4].wrapping_add(e);
    state[5] = state[5].wrapping_add(f);
    state[6] = state[6].wrapping_add(g);
    state[7] = state[7].wrapping_add(h);
}

// ── Public API ───────────────────────────────────────────────────────────────

/// Compute SHA-256 of `data`, returning a 32-byte digest.
pub fn sha256(data: &[u8]) -> [u8; 32] {
    let padded = pad(data);
    let mut state = H0;

    for block in padded.chunks_exact(64) {
        compress(&mut state, block);
    }

    let mut out = [0u8; 32];
    for (i, word) in state.iter().enumerate() {
        out[i * 4..i * 4 + 4].copy_from_slice(&word.to_be_bytes());
    }
    out
}
