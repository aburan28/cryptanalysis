//! BLAKE2s implemented from scratch per RFC 7693.
//!
//! BLAKE2s is the 32-bit-word sibling of BLAKE2b — same HAIFA structure
//! and ARX permutation, but tuned for 8- to 32-bit platforms. It
//! produces 1..=32 byte digests, processes 64-byte blocks across 10
//! rounds, and supports a 0..=32 byte key for use as a keyed PRF / MAC.
//!
//! Differences from BLAKE2b (besides word size): 10 rounds instead of
//! 12, rotation amounts of 16/12/8/7, and a 64-bit byte counter (vs
//! 128-bit).

const IV: [u32; 8] = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
];

/// RFC 7693 §2.7 — same permutation table as BLAKE2b but only the
/// first 10 rows are used.
const SIGMA: [[usize; 16]; 10] = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
    [14, 10, 4, 8, 9, 15, 13, 6, 1, 12, 0, 2, 11, 7, 5, 3],
    [11, 8, 12, 0, 5, 2, 15, 13, 10, 14, 3, 6, 7, 1, 9, 4],
    [7, 9, 3, 1, 13, 12, 11, 14, 2, 6, 5, 10, 4, 0, 15, 8],
    [9, 0, 5, 7, 2, 4, 10, 15, 14, 1, 11, 12, 6, 8, 3, 13],
    [2, 12, 6, 10, 0, 11, 8, 3, 4, 13, 7, 5, 15, 14, 1, 9],
    [12, 5, 1, 15, 14, 13, 4, 10, 0, 7, 6, 3, 9, 2, 8, 11],
    [13, 11, 7, 14, 12, 1, 3, 9, 5, 0, 15, 4, 8, 6, 2, 10],
    [6, 15, 14, 9, 11, 3, 0, 8, 12, 2, 13, 7, 1, 4, 10, 5],
    [10, 2, 8, 4, 7, 6, 1, 5, 15, 11, 9, 14, 3, 12, 13, 0],
];

const BLOCK_BYTES: usize = 64;
const ROUNDS: usize = 10;

/// The G mixing function (RFC 7693 §3.1) — rotation amounts 16/12/8/7.
#[inline]
fn g(v: &mut [u32; 16], a: usize, b: usize, c: usize, d: usize, x: u32, y: u32) {
    v[a] = v[a].wrapping_add(v[b]).wrapping_add(x);
    v[d] = (v[d] ^ v[a]).rotate_right(16);
    v[c] = v[c].wrapping_add(v[d]);
    v[b] = (v[b] ^ v[c]).rotate_right(12);
    v[a] = v[a].wrapping_add(v[b]).wrapping_add(y);
    v[d] = (v[d] ^ v[a]).rotate_right(8);
    v[c] = v[c].wrapping_add(v[d]);
    v[b] = (v[b] ^ v[c]).rotate_right(7);
}

fn compress(h: &mut [u32; 8], block: &[u8; BLOCK_BYTES], t: u64, last: bool) {
    let mut m = [0u32; 16];
    for i in 0..16 {
        m[i] = u32::from_le_bytes(block[4 * i..4 * i + 4].try_into().unwrap());
    }

    let mut v = [0u32; 16];
    v[..8].copy_from_slice(h);
    v[8..].copy_from_slice(&IV);
    v[12] ^= t as u32;
    v[13] ^= (t >> 32) as u32;
    if last {
        v[14] ^= !0u32;
    }

    for i in 0..ROUNDS {
        let s = &SIGMA[i];
        g(&mut v, 0, 4, 8, 12, m[s[0]], m[s[1]]);
        g(&mut v, 1, 5, 9, 13, m[s[2]], m[s[3]]);
        g(&mut v, 2, 6, 10, 14, m[s[4]], m[s[5]]);
        g(&mut v, 3, 7, 11, 15, m[s[6]], m[s[7]]);
        g(&mut v, 0, 5, 10, 15, m[s[8]], m[s[9]]);
        g(&mut v, 1, 6, 11, 12, m[s[10]], m[s[11]]);
        g(&mut v, 2, 7, 8, 13, m[s[12]], m[s[13]]);
        g(&mut v, 3, 4, 9, 14, m[s[14]], m[s[15]]);
    }

    for i in 0..8 {
        h[i] ^= v[i] ^ v[i + 8];
    }
}

fn blake2s_core(key: &[u8], data: &[u8], out_len: usize) -> Vec<u8> {
    assert!(
        (1..=32).contains(&out_len),
        "BLAKE2s output length must be 1..=32"
    );
    assert!(key.len() <= 32, "BLAKE2s key length must be 0..=32");

    let mut h = IV;
    h[0] ^= 0x0101_0000 ^ ((key.len() as u32) << 8) ^ (out_len as u32);

    // Padded key block (when present) counts as 64 bytes in `t`.
    let mut buf: Vec<u8> = Vec::with_capacity(data.len() + BLOCK_BYTES);
    if !key.is_empty() {
        let mut kb = [0u8; BLOCK_BYTES];
        kb[..key.len()].copy_from_slice(key);
        buf.extend_from_slice(&kb);
    }
    buf.extend_from_slice(data);

    // Empty unkeyed input still hashes one all-zero block with t = 0.
    if buf.is_empty() {
        compress(&mut h, &[0u8; BLOCK_BYTES], 0, true);
    } else {
        let total = buf.len();
        let mut offset = 0;
        let mut block = [0u8; BLOCK_BYTES];

        while total - offset > BLOCK_BYTES {
            block.copy_from_slice(&buf[offset..offset + BLOCK_BYTES]);
            offset += BLOCK_BYTES;
            compress(&mut h, &block, offset as u64, false);
        }

        let remaining = total - offset;
        block.fill(0);
        block[..remaining].copy_from_slice(&buf[offset..]);
        compress(&mut h, &block, total as u64, true);
    }

    let mut out = vec![0u8; out_len];
    let mut tmp = [0u8; 32];
    for (i, &word) in h.iter().enumerate() {
        tmp[4 * i..4 * i + 4].copy_from_slice(&word.to_le_bytes());
    }
    out.copy_from_slice(&tmp[..out_len]);
    out
}

/// Unkeyed BLAKE2s. `out_len` must be in 1..=32.
pub fn blake2s(data: &[u8], out_len: usize) -> Vec<u8> {
    blake2s_core(&[], data, out_len)
}

/// Keyed BLAKE2s (PRF / MAC). `key` may be 0..=32 bytes; `out_len` 1..=32.
pub fn blake2s_keyed(key: &[u8], data: &[u8], out_len: usize) -> Vec<u8> {
    blake2s_core(key, data, out_len)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hex(bytes: &[u8]) -> String {
        bytes.iter().map(|b| format!("{:02x}", b)).collect()
    }

    /// RFC 7693 Appendix A — BLAKE2s-256("abc").
    #[test]
    fn rfc7693_abc() {
        assert_eq!(
            hex(&blake2s(b"abc", 32)),
            "508c5e8c327c14e2e1a72ba34eeb452f37458b209ed63a294d999b4c86675982",
        );
    }

    /// Empty input — verified with Python's `hashlib.blake2s`.
    #[test]
    fn empty() {
        assert_eq!(
            hex(&blake2s(b"", 32)),
            "69217a3079908094e11121d042354a7c1f55b6482ca1a51e1b250dfd1ed0eef9",
        );
    }

    /// Keyed BLAKE2s — verified with Python's `hashlib.blake2s(..., key=...)`.
    #[test]
    fn keyed_abc_mykey() {
        assert_eq!(
            hex(&blake2s_keyed(b"mykey", b"abc", 32)),
            "9f1d7066decc863caa49c7698eb5f583be311ef9496591d067af4fe8240d9142",
        );
    }

    /// Quick-fox sanity check.
    #[test]
    fn quickfox() {
        assert_eq!(
            hex(&blake2s(b"The quick brown fox jumps over the lazy dog", 32)),
            "606beeec743ccbeff6cbcdf5d5302aa855c256c29b88c8ed331ea1a6bf3c8812",
        );
    }

    /// Block boundary: exactly one 64-byte block.
    #[test]
    fn block_boundary_64() {
        assert_eq!(
            hex(&blake2s(&[b'A'; 64], 32)),
            "f85b88e0ac55872416d202c5f4881e7dbc9c7270542ef75074ff9b0a610b5a0e",
        );
    }

    /// One past the boundary forces a second compression call.
    #[test]
    fn block_boundary_65() {
        assert_eq!(
            hex(&blake2s(&[b'A'; 65], 32)),
            "65bba861969fcb5f1d8ec69e1dbd3e891f546b02203ce73b27958b9589a6789d",
        );
    }

    /// Short output length still hashes correctly.
    #[test]
    fn truncated_output_16() {
        assert_eq!(
            hex(&blake2s(b"abc", 16)),
            "aa4938119b1dc7b87cbad0ffd200d0ae",
        );
    }
}
