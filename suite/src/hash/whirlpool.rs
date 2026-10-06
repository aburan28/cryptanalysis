//! **Whirlpool** — 512-bit hash by Barreto & Rijmen (2000), revised
//! 2003.  ISO/IEC 10118-3:2018 standard, also adopted by NESSIE.
//! Uses an AES-like dedicated block cipher *W* in Miyaguchi–Preneel
//! mode: each 512-bit message block is encrypted under the running
//! hash as the key, and the result is XORed with both the hash and
//! the block.
//!
//! ## Structure
//!
//! - Block size: 512 bits, viewed as an 8×8 byte matrix (row-major).
//! - 10 rounds of SubBytes → ShiftColumns → MixRows → AddRoundKey.
//! - Round constants `RC[r]` placed in row 0 of the key schedule.
//! - GF(2^8) arithmetic with reduction polynomial `x^8 + x^4 + x^3
//!   + x^2 + 1` (= `0x11D`).
//! - Padding: append `0x80`, zeros, then a 256-bit big-endian length.
//!
//! This implements the **revised (2003)** Whirlpool, which differs
//! from the 2000 original in the MixRows matrix and from the 2001
//! "Whirlpool-T" intermediate version in the S-box construction.

// ── S-box generated from the mini-box recursion ───────────────────

const S: [u8; 256] = [
    0x18, 0x23, 0xc6, 0xe8, 0x87, 0xb8, 0x01, 0x4f, 0x36, 0xa6, 0xd2, 0xf5, 0x79, 0x6f, 0x91, 0x52,
    0x60, 0xbc, 0x9b, 0x8e, 0xa3, 0x0c, 0x7b, 0x35, 0x1d, 0xe0, 0xd7, 0xc2, 0x2e, 0x4b, 0xfe, 0x57,
    0x15, 0x77, 0x37, 0xe5, 0x9f, 0xf0, 0x4a, 0xda, 0x58, 0xc9, 0x29, 0x0a, 0xb1, 0xa0, 0x6b, 0x85,
    0xbd, 0x5d, 0x10, 0xf4, 0xcb, 0x3e, 0x05, 0x67, 0xe4, 0x27, 0x41, 0x8b, 0xa7, 0x7d, 0x95, 0xd8,
    0xfb, 0xee, 0x7c, 0x66, 0xdd, 0x17, 0x47, 0x9e, 0xca, 0x2d, 0xbf, 0x07, 0xad, 0x5a, 0x83, 0x33,
    0x63, 0x02, 0xaa, 0x71, 0xc8, 0x19, 0x49, 0xd9, 0xf2, 0xe3, 0x5b, 0x88, 0x9a, 0x26, 0x32, 0xb0,
    0xe9, 0x0f, 0xd5, 0x80, 0xbe, 0xcd, 0x34, 0x48, 0xff, 0x7a, 0x90, 0x5f, 0x20, 0x68, 0x1a, 0xae,
    0xb4, 0x54, 0x93, 0x22, 0x64, 0xf1, 0x73, 0x12, 0x40, 0x08, 0xc3, 0xec, 0xdb, 0xa1, 0x8d, 0x3d,
    0x97, 0x00, 0xcf, 0x2b, 0x76, 0x82, 0xd6, 0x1b, 0xb5, 0xaf, 0x6a, 0x50, 0x45, 0xf3, 0x30, 0xef,
    0x3f, 0x55, 0xa2, 0xea, 0x65, 0xba, 0x2f, 0xc0, 0xde, 0x1c, 0xfd, 0x4d, 0x92, 0x75, 0x06, 0x8a,
    0xb2, 0xe6, 0x0e, 0x1f, 0x62, 0xd4, 0xa8, 0x96, 0xf9, 0xc5, 0x25, 0x59, 0x84, 0x72, 0x39, 0x4c,
    0x5e, 0x78, 0x38, 0x8c, 0xd1, 0xa5, 0xe2, 0x61, 0xb3, 0x21, 0x9c, 0x1e, 0x43, 0xc7, 0xfc, 0x04,
    0x51, 0x99, 0x6d, 0x0d, 0xfa, 0xdf, 0x7e, 0x24, 0x3b, 0xab, 0xce, 0x11, 0x8f, 0x4e, 0xb7, 0xeb,
    0x3c, 0x81, 0x94, 0xf7, 0xb9, 0x13, 0x2c, 0xd3, 0xe7, 0x6e, 0xc4, 0x03, 0x56, 0x44, 0x7f, 0xa9,
    0x2a, 0xbb, 0xc1, 0x53, 0xdc, 0x0b, 0x9d, 0x6c, 0x31, 0x74, 0xf6, 0x46, 0xac, 0x89, 0x14, 0xe1,
    0x16, 0x3a, 0x69, 0x09, 0x70, 0xb6, 0xd0, 0xed, 0xcc, 0x42, 0x98, 0xa4, 0x28, 0x5c, 0xf8, 0x86,
];

/// Round constants: `RC[r]` is an 8×8 matrix whose row 0 is bytes
/// `S[8(r-1)..8r]` and whose other rows are zero.  Only row 0 is
/// stored; the other rows are implicit.
const RC: [[u8; 8]; 10] = [
    [0x18, 0x23, 0xc6, 0xe8, 0x87, 0xb8, 0x01, 0x4f],
    [0x36, 0xa6, 0xd2, 0xf5, 0x79, 0x6f, 0x91, 0x52],
    [0x60, 0xbc, 0x9b, 0x8e, 0xa3, 0x0c, 0x7b, 0x35],
    [0x1d, 0xe0, 0xd7, 0xc2, 0x2e, 0x4b, 0xfe, 0x57],
    [0x15, 0x77, 0x37, 0xe5, 0x9f, 0xf0, 0x4a, 0xda],
    [0x58, 0xc9, 0x29, 0x0a, 0xb1, 0xa0, 0x6b, 0x85],
    [0xbd, 0x5d, 0x10, 0xf4, 0xcb, 0x3e, 0x05, 0x67],
    [0xe4, 0x27, 0x41, 0x8b, 0xa7, 0x7d, 0x95, 0xd8],
    [0xfb, 0xee, 0x7c, 0x66, 0xdd, 0x17, 0x47, 0x9e],
    [0xca, 0x2d, 0xbf, 0x07, 0xad, 0x5a, 0x83, 0x33],
];

// ── GF(2^8) multiplication with reduction polynomial 0x11D ────────

#[inline]
fn gmul(a: u8, b: u8) -> u8 {
    let mut x = a;
    let mut y = b;
    let mut r: u8 = 0;
    for _ in 0..8 {
        if y & 1 != 0 {
            r ^= x;
        }
        let hi = x & 0x80;
        x <<= 1;
        if hi != 0 {
            x ^= 0x1D; // reduction: x^8 ≡ x^4 + x^3 + x^2 + 1.
        }
        y >>= 1;
    }
    r
}

// ── W round (operates on an 8×8 byte matrix, row-major) ──────────

/// Apply SubBytes ∘ ShiftColumns ∘ MixRows; result stored in `out`.
/// Column j shifts down by j positions: `out[i][j] = state[(i-j) mod 8][j]`,
/// then each row is multiplied by the circulant `[1, 1, 4, 1, 8, 5, 2, 9]`.
fn theta(state: &[u8; 64], out: &mut [u8; 64]) {
    // The MixRows row vector (in GF(2^8)) for Whirlpool 2003.
    const C: [u8; 8] = [0x01, 0x01, 0x04, 0x01, 0x08, 0x05, 0x02, 0x09];
    let mut shifted = [0u8; 64];
    for i in 0..8 {
        for j in 0..8 {
            // SubBytes baked in: pull from state[(i-j) mod 8][j] then S-box it.
            let src = state[((i + 8 - j) % 8) * 8 + j];
            shifted[i * 8 + j] = S[src as usize];
        }
    }
    // MixRows: out[i][j] = ⊕_k C[(j-k) mod 8] · shifted[i][k].
    for i in 0..8 {
        for j in 0..8 {
            let mut v: u8 = 0;
            for k in 0..8 {
                v ^= gmul(C[(j + 8 - k) % 8], shifted[i * 8 + k]);
            }
            out[i * 8 + j] = v;
        }
    }
}

#[inline]
fn xor_block(out: &mut [u8; 64], a: &[u8; 64]) {
    for i in 0..64 {
        out[i] ^= a[i];
    }
}

/// Block cipher *W* keyed by `key`, encrypting `block`.  Returns
/// `W_K(block)` in the convention used by Miyaguchi–Preneel.
fn w_cipher(key: &[u8; 64], block: &[u8; 64]) -> [u8; 64] {
    let mut k = *key;
    let mut state = *block;
    xor_block(&mut state, &k);

    for r in 0..10 {
        // Key schedule: K_{r+1} = theta(K_r) ⊕ RC_{r+1} (only in row 0).
        let mut nk = [0u8; 64];
        theta(&k, &mut nk);
        for j in 0..8 {
            nk[j] ^= RC[r][j];
        }
        k = nk;
        // State: theta(state) ⊕ K_{r+1}.
        let mut ns = [0u8; 64];
        theta(&state, &mut ns);
        xor_block(&mut ns, &k);
        state = ns;
    }
    state
}

// ── Whirlpool driver ──────────────────────────────────────────────

#[derive(Clone, Debug)]
pub struct Whirlpool {
    h: [u8; 64],
    buffer: Vec<u8>,
    bit_len: u128, // Whirlpool uses a 256-bit length, but 128 bits is plenty here.
}

impl Default for Whirlpool {
    fn default() -> Self {
        Self::new()
    }
}

impl Whirlpool {
    pub fn new() -> Self {
        Self {
            h: [0u8; 64],
            buffer: Vec::with_capacity(64),
            bit_len: 0,
        }
    }

    pub fn update(&mut self, data: &[u8]) {
        self.bit_len = self.bit_len.wrapping_add((data.len() as u128) * 8);
        self.buffer.extend_from_slice(data);
        while self.buffer.len() >= 64 {
            let mut m = [0u8; 64];
            m.copy_from_slice(&self.buffer[..64]);
            self.compress(&m);
            self.buffer.drain(..64);
        }
    }

    /// Miyaguchi–Preneel: `h' = W_h(m) ⊕ h ⊕ m`.
    fn compress(&mut self, m: &[u8; 64]) {
        let c = w_cipher(&self.h, m);
        for i in 0..64 {
            self.h[i] ^= c[i] ^ m[i];
        }
    }

    pub fn finalize(mut self) -> [u8; 64] {
        let bit_len = self.bit_len;
        // Padding: append 0x80, zeros, then 32-byte big-endian bit length.
        let mut padded = std::mem::take(&mut self.buffer);
        padded.push(0x80);
        while padded.len() % 64 != 32 {
            padded.push(0x00);
        }
        // 256-bit big-endian length.  Top 16 bytes are zero (we use u128).
        padded.extend_from_slice(&[0u8; 16]);
        padded.extend_from_slice(&bit_len.to_be_bytes());

        for chunk in padded.chunks_exact(64) {
            let mut m = [0u8; 64];
            m.copy_from_slice(chunk);
            self.compress(&m);
        }
        self.h
    }
}

/// One-shot Whirlpool: returns a 64-byte digest.
pub fn whirlpool(data: &[u8]) -> [u8; 64] {
    let mut h = Whirlpool::new();
    h.update(data);
    h.finalize()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hx(s: &str) -> Vec<u8> {
        hex::decode(s).unwrap()
    }

    /// ISO/IEC 10118-3 / NESSIE published vectors for Whirlpool (2003).
    #[test]
    fn whirlpool_empty() {
        assert_eq!(
            whirlpool(b"").as_slice(),
            hx(
                "19fa61d75522a4669b44e39c1d2e1726c530232130d407f89afee0964997f7a7\
                3e83be698b288febcf88e3e03c4f0757ea8964e59b63d93708b138cc42a66eb3"
            )
            .as_slice(),
        );
    }

    #[test]
    fn whirlpool_a() {
        assert_eq!(
            whirlpool(b"a").as_slice(),
            hx(
                "8aca2602792aec6f11a67206531fb7d7f0dff59413145e6973c45001d0087b42\
                d11bc645413aeff63a42391a39145a591a92200d560195e53b478584fdae231a"
            )
            .as_slice(),
        );
    }

    #[test]
    fn whirlpool_abc() {
        assert_eq!(
            whirlpool(b"abc").as_slice(),
            hx(
                "4e2448a4c6f486bb16b6562c73b4020bf3043e3a731bce721ae1b303d97e6d4c\
                7181eebdb6c57e277d0e34957114cbd6c797fc9d95d8b582d225292076d4eef5"
            )
            .as_slice(),
        );
    }

    /// 43-byte message — spans into a second block due to padding.
    #[test]
    fn whirlpool_quick_fox() {
        // Verified against `openssl dgst -provider legacy -whirlpool`.
        assert_eq!(
            whirlpool(b"The quick brown fox jumps over the lazy dog").as_slice(),
            hx(
                "b97de512e91e3828b40d2b0fdce9ceb3c4a71f9bea8d88e75c4fa854df36725f\
                d2b52eb6544edcacd6f8beddfea403cb55ae31f03ad62a5ef54e42ee82c3fb35"
            )
            .as_slice(),
        );
    }

    /// Incremental hashing matches one-shot.
    #[test]
    fn whirlpool_incremental_matches_oneshot() {
        let msg = b"the quick brown fox jumps over the lazy dog";
        let oneshot = whirlpool(msg);
        let mut h = Whirlpool::new();
        for chunk in msg.chunks(7) {
            h.update(chunk);
        }
        assert_eq!(oneshot, h.finalize());
    }

    /// Block-boundary case: input exactly one block.
    #[test]
    fn whirlpool_64_byte_input() {
        let msg = [0x42u8; 64];
        let d = whirlpool(&msg);
        // Determinism / non-zero output sanity check.
        assert!(d.iter().any(|&b| b != 0));
        assert_eq!(d, whirlpool(&msg));
    }

    /// Avalanche: a one-bit change in input changes many output bits.
    #[test]
    fn whirlpool_avalanche() {
        let d1 = whirlpool(b"hello world");
        let d2 = whirlpool(b"hello worle");
        let differing = d1.iter().zip(&d2).filter(|(a, b)| a != b).count();
        assert!(differing >= 40, "avalanche too weak: {differing} bytes");
    }
}
