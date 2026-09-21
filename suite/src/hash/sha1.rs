//! **SHA-1** — Secure Hash Algorithm 1 (FIPS 180-4 §6.1, RFC 3174).
//!
//! 160-bit output, 80-round Merkle-Damgård on 32-bit words, big-endian
//! byte order.  **Broken**: Stevens-Bursztein-Karpman-Albertini-Markov
//! (SHAttered, 2017) produced the first public collision — two distinct
//! PDFs hashing to the same value — at a cost of ~2⁶³·¹ SHA-1 evaluations.
//! Leurent-Peyrin (2020) followed with a chosen-prefix collision.  Shipped
//! here only for legacy interop (Git object IDs, old TLS certs) and as a
//! study target for cryptanalysis; do not use for new security work.
//!
//! ## Algorithm
//!
//! Padding matches SHA-256 (append `0x80`, zero pad, 64-bit big-endian
//! length).  Each 512-bit block expands to 80 32-bit words via the
//! schedule `W[t] = ROTL¹(W[t-3] ⊕ W[t-8] ⊕ W[t-14] ⊕ W[t-16])`
//! (the extra rotation is the lesson SHA-0 → SHA-1 baked in to fix
//! collision resistance — and still wasn't enough).  Four 20-round
//! sections use round functions `Ch`, `Parity`, `Maj`, `Parity` with
//! constants `K = 5a827999, 6ed9eba1, 8f1bbcdc, ca62c1d6` (square roots
//! of 2, 3, 5, 10 scaled by 2³⁰).

/// SHA-1 initial hash values (FIPS 180-4 §5.3.1).
const H0: [u32; 5] = [0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476, 0xc3d2e1f0];

// ── Round functions ──────────────────────────────────────────────────────────

#[inline]
fn ch(x: u32, y: u32, z: u32) -> u32 {
    (x & y) ^ (!x & z)
}
#[inline]
fn parity(x: u32, y: u32, z: u32) -> u32 {
    x ^ y ^ z
}
#[inline]
fn maj(x: u32, y: u32, z: u32) -> u32 {
    (x & y) ^ (x & z) ^ (y & z)
}

// ── Padding ──────────────────────────────────────────────────────────────────

/// Pad to a multiple of 64 bytes: append `0x80`, zeros, then the 64-bit
/// big-endian message length in bits.
fn sha1_pad(msg: &[u8]) -> Vec<u8> {
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

fn sha1_compress(state: &mut [u32; 5], block: &[u8]) {
    let mut w = [0u32; 80];
    for i in 0..16 {
        w[i] = u32::from_be_bytes(block[i * 4..i * 4 + 4].try_into().unwrap());
    }
    for t in 16..80 {
        w[t] = (w[t - 3] ^ w[t - 8] ^ w[t - 14] ^ w[t - 16]).rotate_left(1);
    }

    let mut a = state[0];
    let mut b = state[1];
    let mut c = state[2];
    let mut d = state[3];
    let mut e = state[4];

    for t in 0..80 {
        let (f, k) = match t {
            0..=19 => (ch(b, c, d), 0x5a827999),
            20..=39 => (parity(b, c, d), 0x6ed9eba1),
            40..=59 => (maj(b, c, d), 0x8f1bbcdc),
            _ => (parity(b, c, d), 0xca62c1d6),
        };
        let temp = a
            .rotate_left(5)
            .wrapping_add(f)
            .wrapping_add(e)
            .wrapping_add(k)
            .wrapping_add(w[t]);
        e = d;
        d = c;
        c = b.rotate_left(30);
        b = a;
        a = temp;
    }

    state[0] = state[0].wrapping_add(a);
    state[1] = state[1].wrapping_add(b);
    state[2] = state[2].wrapping_add(c);
    state[3] = state[3].wrapping_add(d);
    state[4] = state[4].wrapping_add(e);
}

// ── Public API ───────────────────────────────────────────────────────────────

/// Compute SHA-1 of `data`, returning a 20-byte digest.
pub fn sha1(data: &[u8]) -> [u8; 20] {
    let padded = sha1_pad(data);
    let mut state = H0;
    for block in padded.chunks_exact(64) {
        sha1_compress(&mut state, block);
    }
    let mut out = [0u8; 20];
    for (i, word) in state.iter().enumerate() {
        out[i * 4..i * 4 + 4].copy_from_slice(&word.to_be_bytes());
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn h(hex_str: &str) -> Vec<u8> {
        hex::decode(hex_str).unwrap()
    }

    // ── SHA-1 known-answer tests (FIPS 180-4 / RFC 3174) ─────────────────────

    #[test]
    fn sha1_empty() {
        assert_eq!(
            sha1(b"").as_slice(),
            h("da39a3ee5e6b4b0d3255bfef95601890afd80709").as_slice(),
        );
    }

    #[test]
    fn sha1_abc() {
        // FIPS 180-4 §A.1
        assert_eq!(
            sha1(b"abc").as_slice(),
            h("a9993e364706816aba3e25717850c26c9cd0d89d").as_slice(),
        );
    }

    #[test]
    fn sha1_fips180_56byte() {
        // FIPS 180-4 §A.2 — spans two blocks
        let msg = b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq";
        assert_eq!(
            sha1(msg).as_slice(),
            h("84983e441c3bd26ebaae4aa1f95129e5e54670f1").as_slice(),
        );
    }

    #[test]
    fn sha1_million_a() {
        // FIPS 180-4 §A.3 — 1,000,000 'a' characters
        let msg = vec![b'a'; 1_000_000];
        assert_eq!(
            sha1(&msg).as_slice(),
            h("34aa973cd4c4daa4f61eeb2bdbad27316534016f").as_slice(),
        );
    }
}
