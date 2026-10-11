//! SHA-512 and SHA-384 (FIPS 180-4 §6.4-6.5).
//!
//! Same Merkle-Damgård structure as SHA-256 but with 64-bit words,
//! 80 rounds, and different rotation amounts.  SHA-384 is just
//! SHA-512 with a different IV and output truncated to 48 bytes.
//!
//! **Why ship this**: Ed25519 uses SHA-512 internally (per RFC
//! 8032).  Without it, the deferred Ed25519 implementation has no
//! foundation.

#[inline]
fn ch(e: u64, f: u64, g: u64) -> u64 {
    (e & f) ^ (!e & g)
}
#[inline]
fn maj(a: u64, b: u64, c: u64) -> u64 {
    (a & b) ^ (a & c) ^ (b & c)
}
#[inline]
fn big_sigma0(x: u64) -> u64 {
    x.rotate_right(28) ^ x.rotate_right(34) ^ x.rotate_right(39)
}
#[inline]
fn big_sigma1(x: u64) -> u64 {
    x.rotate_right(14) ^ x.rotate_right(18) ^ x.rotate_right(41)
}
#[inline]
fn small_sigma0(x: u64) -> u64 {
    x.rotate_right(1) ^ x.rotate_right(8) ^ (x >> 7)
}
#[inline]
fn small_sigma1(x: u64) -> u64 {
    x.rotate_right(19) ^ x.rotate_right(61) ^ (x >> 6)
}

/// FIPS 180-4 §4.2.3 — first 64 bits of fractional parts of cube
/// roots of the first 80 primes.
const K: [u64; 80] = [
    0x428a2f98d728ae22,
    0x7137449123ef65cd,
    0xb5c0fbcfec4d3b2f,
    0xe9b5dba58189dbbc,
    0x3956c25bf348b538,
    0x59f111f1b605d019,
    0x923f82a4af194f9b,
    0xab1c5ed5da6d8118,
    0xd807aa98a3030242,
    0x12835b0145706fbe,
    0x243185be4ee4b28c,
    0x550c7dc3d5ffb4e2,
    0x72be5d74f27b896f,
    0x80deb1fe3b1696b1,
    0x9bdc06a725c71235,
    0xc19bf174cf692694,
    0xe49b69c19ef14ad2,
    0xefbe4786384f25e3,
    0x0fc19dc68b8cd5b5,
    0x240ca1cc77ac9c65,
    0x2de92c6f592b0275,
    0x4a7484aa6ea6e483,
    0x5cb0a9dcbd41fbd4,
    0x76f988da831153b5,
    0x983e5152ee66dfab,
    0xa831c66d2db43210,
    0xb00327c898fb213f,
    0xbf597fc7beef0ee4,
    0xc6e00bf33da88fc2,
    0xd5a79147930aa725,
    0x06ca6351e003826f,
    0x142929670a0e6e70,
    0x27b70a8546d22ffc,
    0x2e1b21385c26c926,
    0x4d2c6dfc5ac42aed,
    0x53380d139d95b3df,
    0x650a73548baf63de,
    0x766a0abb3c77b2a8,
    0x81c2c92e47edaee6,
    0x92722c851482353b,
    0xa2bfe8a14cf10364,
    0xa81a664bbc423001,
    0xc24b8b70d0f89791,
    0xc76c51a30654be30,
    0xd192e819d6ef5218,
    0xd69906245565a910,
    0xf40e35855771202a,
    0x106aa07032bbd1b8,
    0x19a4c116b8d2d0c8,
    0x1e376c085141ab53,
    0x2748774cdf8eeb99,
    0x34b0bcb5e19b48a8,
    0x391c0cb3c5c95a63,
    0x4ed8aa4ae3418acb,
    0x5b9cca4f7763e373,
    0x682e6ff3d6b2b8a3,
    0x748f82ee5defb2fc,
    0x78a5636f43172f60,
    0x84c87814a1f0ab72,
    0x8cc702081a6439ec,
    0x90befffa23631e28,
    0xa4506cebde82bde9,
    0xbef9a3f7b2c67915,
    0xc67178f2e372532b,
    0xca273eceea26619c,
    0xd186b8c721c0c207,
    0xeada7dd6cde0eb1e,
    0xf57d4f7fee6ed178,
    0x06f067aa72176fba,
    0x0a637dc5a2c898a6,
    0x113f9804bef90dae,
    0x1b710b35131c471b,
    0x28db77f523047d84,
    0x32caab7b40c72493,
    0x3c9ebe0a15c9bebc,
    0x431d67c49c100d4c,
    0x4cc5d4becb3e42b6,
    0x597f299cfc657e2a,
    0x5fcb6fab3ad6faec,
    0x6c44198c4a475817,
];

/// SHA-512 IV (FIPS 180-4 §5.3.5).
const IV_512: [u64; 8] = [
    0x6a09e667f3bcc908,
    0xbb67ae8584caa73b,
    0x3c6ef372fe94f82b,
    0xa54ff53a5f1d36f1,
    0x510e527fade682d1,
    0x9b05688c2b3e6c1f,
    0x1f83d9abfb41bd6b,
    0x5be0cd19137e2179,
];

/// SHA-384 IV (FIPS 180-4 §5.3.4).
const IV_384: [u64; 8] = [
    0xcbbb9d5dc1059ed8,
    0x629a292a367cd507,
    0x9159015a3070dd17,
    0x152fecd8f70e5939,
    0x67332667ffc00b31,
    0x8eb44a8768581511,
    0xdb0c2e0d64f98fa7,
    0x47b5481dbefa4fa4,
];

fn compress(state: &mut [u64; 8], block: &[u8; 128]) {
    let mut w = [0u64; 80];
    for i in 0..16 {
        w[i] = u64::from_be_bytes(block[8 * i..8 * i + 8].try_into().unwrap());
    }
    for t in 16..80 {
        w[t] = small_sigma1(w[t - 2])
            .wrapping_add(w[t - 7])
            .wrapping_add(small_sigma0(w[t - 15]))
            .wrapping_add(w[t - 16]);
    }
    let (mut a, mut b, mut c, mut d, mut e, mut f, mut g, mut h) = (
        state[0], state[1], state[2], state[3], state[4], state[5], state[6], state[7],
    );
    for t in 0..80 {
        let t1 = h
            .wrapping_add(big_sigma1(e))
            .wrapping_add(ch(e, f, g))
            .wrapping_add(K[t])
            .wrapping_add(w[t]);
        let t2 = big_sigma0(a).wrapping_add(maj(a, b, c));
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

fn pad_and_compress(message: &[u8], iv: [u64; 8]) -> [u64; 8] {
    let mut state = iv;
    // SHA-512 uses 128-bit length; we embed in low 64 bits (top is
    // ~0 for any reasonable message length on a 64-bit system).
    let bit_len = (message.len() as u128) * 8;
    let mut padded = message.to_vec();
    padded.push(0x80);
    while padded.len() % 128 != 112 {
        padded.push(0);
    }
    padded.extend_from_slice(&bit_len.to_be_bytes());
    for chunk in padded.chunks_exact(128) {
        let mut block = [0u8; 128];
        block.copy_from_slice(chunk);
        compress(&mut state, &block);
    }
    state
}

/// SHA-512 of `message`.  Returns 64 bytes.
pub fn sha512(message: &[u8]) -> [u8; 64] {
    let state = pad_and_compress(message, IV_512);
    let mut out = [0u8; 64];
    for (i, &word) in state.iter().enumerate() {
        out[8 * i..8 * i + 8].copy_from_slice(&word.to_be_bytes());
    }
    out
}

/// SHA-384 of `message`.  Returns 48 bytes (truncated SHA-512 with
/// distinct IV).
pub fn sha384(message: &[u8]) -> [u8; 48] {
    let state = pad_and_compress(message, IV_384);
    let mut out = [0u8; 48];
    for (i, &word) in state.iter().take(6).enumerate() {
        out[8 * i..8 * i + 8].copy_from_slice(&word.to_be_bytes());
    }
    out
}

// ── SHA-512/t truncated variants (FIPS 180-4 §6.6) ───────────────────────────
//
// SHA-512/224 and SHA-512/256 are SHA-512 with output truncated to 224/256
// bits and distinct IVs.  Per FIPS 180-4 §5.3.6, each generation IV is
// computed by running SHA-512 over the literal ASCII `"SHA-512/t"` with
// the standard IV XORed against `0xa5a5_a5a5_a5a5_a5a5`.  The hard-coded
// constants below are the published outputs of that derivation.

/// SHA-512/224 IV (FIPS 180-4 §5.3.6.1).
const IV_512_224: [u64; 8] = [
    0x8c3d37c819544da2,
    0x73e1996689dcd4d6,
    0x1dfab7ae32ff9c82,
    0x679dd514582f9fcf,
    0x0f6d2b697bd44da8,
    0x77e36f7304c48942,
    0x3f9d85a86a1d36c8,
    0x1112e6ad91d692a1,
];

/// SHA-512/256 IV (FIPS 180-4 §5.3.6.2).
const IV_512_256: [u64; 8] = [
    0x22312194fc2bf72c,
    0x9f555fa3c84c64c2,
    0x2393b86b6f53b151,
    0x963877195940eabd,
    0x96283ee2a88effe3,
    0xbe5e1e2553863992,
    0x2b0199fc2c85b8aa,
    0x0eb72ddc81c52ca2,
];

/// SHA-512/224 of `message`.  Returns 28 bytes (truncated SHA-512 with
/// the §5.3.6.1 IV).
pub fn sha512_224(message: &[u8]) -> [u8; 28] {
    let state = pad_and_compress(message, IV_512_224);
    let mut out = [0u8; 28];
    // First 3.5 64-bit words = 28 bytes: full words 0..3, then high 4
    // bytes of word 3 — but easier to lay down 4 full words and truncate.
    let mut full = [0u8; 32];
    for (i, &word) in state.iter().take(4).enumerate() {
        full[8 * i..8 * i + 8].copy_from_slice(&word.to_be_bytes());
    }
    out.copy_from_slice(&full[..28]);
    out
}

/// SHA-512/256 of `message`.  Returns 32 bytes (truncated SHA-512 with
/// the §5.3.6.2 IV).
pub fn sha512_256(message: &[u8]) -> [u8; 32] {
    let state = pad_and_compress(message, IV_512_256);
    let mut out = [0u8; 32];
    for (i, &word) in state.iter().take(4).enumerate() {
        out[8 * i..8 * i + 8].copy_from_slice(&word.to_be_bytes());
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hex(bytes: &[u8]) -> String {
        bytes.iter().map(|b| format!("{:02x}", b)).collect()
    }

    /// FIPS 180-4 KAT for SHA-512("").
    #[test]
    fn sha512_empty() {
        let h = sha512(b"");
        assert_eq!(
            hex(&h),
            "cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce\
             47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e",
        );
    }

    /// FIPS 180-4 KAT for SHA-512("abc").
    #[test]
    fn sha512_abc() {
        let h = sha512(b"abc");
        assert_eq!(
            hex(&h),
            "ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a\
             2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f",
        );
    }

    /// FIPS 180-4 KAT for SHA-512 of two-block message.
    #[test]
    fn sha512_two_block() {
        let msg = b"abcdefghbcdefghicdefghijdefghijkefghijklfghijklmghijklmn\
                    hijklmnoijklmnopjklmnopqklmnopqrlmnopqrsmnopqrstnopqrstu";
        let h = sha512(msg);
        assert_eq!(
            hex(&h),
            "8e959b75dae313da8cf4f72814fc143f8f7779c6eb9f7fa17299aeadb6889018\
             501d289e4900f7e4331b99dec4b5433ac7d329eeb6dd26545e96e55b874be909",
        );
    }

    /// FIPS 180-4 KAT for SHA-384("abc").
    #[test]
    fn sha384_abc() {
        let h = sha384(b"abc");
        assert_eq!(
            hex(&h),
            "cb00753f45a35e8bb5a03d699ac65007272c32ab0eded1631a8b605a43ff5bed\
             8086072ba1e7cc2358baeca134c825a7",
        );
    }

    /// FIPS 180-4 KAT for SHA-384("").
    #[test]
    fn sha384_empty() {
        let h = sha384(b"");
        assert_eq!(
            hex(&h),
            "38b060a751ac96384cd9327eb1b1e36a21fdb71114be07434c0cc7bf63f6e1da\
             274edebfe76f65fbd51ad2f14898b95b",
        );
    }

    // ── SHA-512/224 and SHA-512/256 KATs (FIPS 180-4 §6.6) ───────────────────

    #[test]
    fn sha512_224_empty() {
        let h = sha512_224(b"");
        assert_eq!(
            hex(&h),
            "6ed0dd02806fa89e25de060c19d3ac86cabb87d6a0ddd05c333b84f4",
        );
    }

    #[test]
    fn sha512_224_abc() {
        let h = sha512_224(b"abc");
        assert_eq!(
            hex(&h),
            "4634270f707b6a54daae7530460842e20e37ed265ceee9a43e8924aa",
        );
    }

    #[test]
    fn sha512_256_empty() {
        let h = sha512_256(b"");
        assert_eq!(
            hex(&h),
            "c672b8d1ef56ed28ab87c3622c5114069bdd3ad7b8f9737498d0c01ecef0967a",
        );
    }

    #[test]
    fn sha512_256_abc() {
        let h = sha512_256(b"abc");
        assert_eq!(
            hex(&h),
            "53048e2681941ef99b2e29b76b4c7dabe4c2d0c634fc6d46e0e2f13107e7af23",
        );
    }
}
