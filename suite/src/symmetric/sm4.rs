//! **SM4** — 128-bit block cipher, Chinese national standard
//! GB/T 32907-2016 (formerly SMS4).  ISO/IEC 18033-3:2010
//! Amendment 1.
//!
//! Mandated by Chinese state regulators for commercial encryption.
//! Deployed in TLS via the GM extensions (RFC 8998), and in
//! Chinese smart-card / industrial-IoT protocols.
//!
//! ## Structure
//!
//! - 32-round generalized Feistel: split the 128-bit state into
//!   four 32-bit words, apply a round function `F` to mix them.
//! - Round function `F(X_0, X_1, X_2, X_3, RK) = X_0 ⊕ T(X_1 ⊕ X_2
//!   ⊕ X_3 ⊕ RK)` where `T = L ∘ τ` (linear transform composed
//!   with a 4×8-bit S-box layer).
//! - 128-bit master key expanded to 32 round keys via a similar
//!   key-schedule transform `T'` using `L'` (different rotation
//!   pattern).
//!
//! ## API
//!
//! - [`Sm4`]: keyed cipher with `encrypt_block` / `decrypt_block`.
//! - [`encrypt_block`] / [`decrypt_block`]: stateless block ops.

// ── S-box (256 bytes, specified in GB/T 32907-2016) ───────────────

const SBOX: [u8; 256] = [
    0xd6, 0x90, 0xe9, 0xfe, 0xcc, 0xe1, 0x3d, 0xb7, 0x16, 0xb6, 0x14, 0xc2, 0x28, 0xfb, 0x2c, 0x05,
    0x2b, 0x67, 0x9a, 0x76, 0x2a, 0xbe, 0x04, 0xc3, 0xaa, 0x44, 0x13, 0x26, 0x49, 0x86, 0x06, 0x99,
    0x9c, 0x42, 0x50, 0xf4, 0x91, 0xef, 0x98, 0x7a, 0x33, 0x54, 0x0b, 0x43, 0xed, 0xcf, 0xac, 0x62,
    0xe4, 0xb3, 0x1c, 0xa9, 0xc9, 0x08, 0xe8, 0x95, 0x80, 0xdf, 0x94, 0xfa, 0x75, 0x8f, 0x3f, 0xa6,
    0x47, 0x07, 0xa7, 0xfc, 0xf3, 0x73, 0x17, 0xba, 0x83, 0x59, 0x3c, 0x19, 0xe6, 0x85, 0x4f, 0xa8,
    0x68, 0x6b, 0x81, 0xb2, 0x71, 0x64, 0xda, 0x8b, 0xf8, 0xeb, 0x0f, 0x4b, 0x70, 0x56, 0x9d, 0x35,
    0x1e, 0x24, 0x0e, 0x5e, 0x63, 0x58, 0xd1, 0xa2, 0x25, 0x22, 0x7c, 0x3b, 0x01, 0x21, 0x78, 0x87,
    0xd4, 0x00, 0x46, 0x57, 0x9f, 0xd3, 0x27, 0x52, 0x4c, 0x36, 0x02, 0xe7, 0xa0, 0xc4, 0xc8, 0x9e,
    0xea, 0xbf, 0x8a, 0xd2, 0x40, 0xc7, 0x38, 0xb5, 0xa3, 0xf7, 0xf2, 0xce, 0xf9, 0x61, 0x15, 0xa1,
    0xe0, 0xae, 0x5d, 0xa4, 0x9b, 0x34, 0x1a, 0x55, 0xad, 0x93, 0x32, 0x30, 0xf5, 0x8c, 0xb1, 0xe3,
    0x1d, 0xf6, 0xe2, 0x2e, 0x82, 0x66, 0xca, 0x60, 0xc0, 0x29, 0x23, 0xab, 0x0d, 0x53, 0x4e, 0x6f,
    0xd5, 0xdb, 0x37, 0x45, 0xde, 0xfd, 0x8e, 0x2f, 0x03, 0xff, 0x6a, 0x72, 0x6d, 0x6c, 0x5b, 0x51,
    0x8d, 0x1b, 0xaf, 0x92, 0xbb, 0xdd, 0xbc, 0x7f, 0x11, 0xd9, 0x5c, 0x41, 0x1f, 0x10, 0x5a, 0xd8,
    0x0a, 0xc1, 0x31, 0x88, 0xa5, 0xcd, 0x7b, 0xbd, 0x2d, 0x74, 0xd0, 0x12, 0xb8, 0xe5, 0xb4, 0xb0,
    0x89, 0x69, 0x97, 0x4a, 0x0c, 0x96, 0x77, 0x7e, 0x65, 0xb9, 0xf1, 0x09, 0xc5, 0x6e, 0xc6, 0x84,
    0x18, 0xf0, 0x7d, 0xec, 0x3a, 0xdc, 0x4d, 0x20, 0x79, 0xee, 0x5f, 0x3e, 0xd7, 0xcb, 0x39, 0x48,
];

// ── System parameter FK and round constants CK ────────────────────

const FK: [u32; 4] = [0xa3b1bac6, 0x56aa3350, 0x677d9197, 0xb27022dc];

const CK: [u32; 32] = {
    let mut ck = [0u32; 32];
    let mut i = 0;
    while i < 32 {
        let i4 = i * 4;
        let b0 = ((i4) as u32 * 7) & 0xff;
        let b1 = ((i4 + 1) as u32 * 7) & 0xff;
        let b2 = ((i4 + 2) as u32 * 7) & 0xff;
        let b3 = ((i4 + 3) as u32 * 7) & 0xff;
        ck[i] = (b0 << 24) | (b1 << 16) | (b2 << 8) | b3;
        i += 1;
    }
    ck
};

// ── Helpers ───────────────────────────────────────────────────────

#[inline]
fn rotl(x: u32, n: u32) -> u32 {
    x.rotate_left(n)
}

/// Non-linear byte-wise S-box layer τ.
#[inline]
fn tau(a: u32) -> u32 {
    let b0 = SBOX[((a >> 24) & 0xff) as usize] as u32;
    let b1 = SBOX[((a >> 16) & 0xff) as usize] as u32;
    let b2 = SBOX[((a >> 8) & 0xff) as usize] as u32;
    let b3 = SBOX[(a & 0xff) as usize] as u32;
    (b0 << 24) | (b1 << 16) | (b2 << 8) | b3
}

/// Linear transform L for round function.
#[inline]
fn l(b: u32) -> u32 {
    b ^ rotl(b, 2) ^ rotl(b, 10) ^ rotl(b, 18) ^ rotl(b, 24)
}

/// Linear transform L' for key schedule.
#[inline]
fn l_prime(b: u32) -> u32 {
    b ^ rotl(b, 13) ^ rotl(b, 23)
}

/// T(.) = L(τ(.)).
#[inline]
fn t(x: u32) -> u32 {
    l(tau(x))
}

/// T'(.) = L'(τ(.)).
#[inline]
fn t_prime(x: u32) -> u32 {
    l_prime(tau(x))
}

// ── Key schedule ──────────────────────────────────────────────────

#[derive(Clone, Debug)]
pub struct Sm4 {
    rk: [u32; 32],
}

impl Sm4 {
    /// Construct an SM4 cipher from a 128-bit master key.
    pub fn new(key: &[u8; 16]) -> Self {
        let mk = [
            u32::from_be_bytes([key[0], key[1], key[2], key[3]]),
            u32::from_be_bytes([key[4], key[5], key[6], key[7]]),
            u32::from_be_bytes([key[8], key[9], key[10], key[11]]),
            u32::from_be_bytes([key[12], key[13], key[14], key[15]]),
        ];
        let mut k = [mk[0] ^ FK[0], mk[1] ^ FK[1], mk[2] ^ FK[2], mk[3] ^ FK[3]];
        let mut rk = [0u32; 32];
        for i in 0..32 {
            let new_k = k[0] ^ t_prime(k[1] ^ k[2] ^ k[3] ^ CK[i]);
            rk[i] = new_k;
            k[0] = k[1];
            k[1] = k[2];
            k[2] = k[3];
            k[3] = new_k;
        }
        Self { rk }
    }

    /// Encrypt a single 128-bit block in place.
    pub fn encrypt_block(&self, block: &mut [u8; 16]) {
        let mut x = [
            u32::from_be_bytes([block[0], block[1], block[2], block[3]]),
            u32::from_be_bytes([block[4], block[5], block[6], block[7]]),
            u32::from_be_bytes([block[8], block[9], block[10], block[11]]),
            u32::from_be_bytes([block[12], block[13], block[14], block[15]]),
        ];
        for i in 0..32 {
            let new_x = x[0] ^ t(x[1] ^ x[2] ^ x[3] ^ self.rk[i]);
            x[0] = x[1];
            x[1] = x[2];
            x[2] = x[3];
            x[3] = new_x;
        }
        // Reverse-output transform.
        let out = [x[3], x[2], x[1], x[0]];
        block[0..4].copy_from_slice(&out[0].to_be_bytes());
        block[4..8].copy_from_slice(&out[1].to_be_bytes());
        block[8..12].copy_from_slice(&out[2].to_be_bytes());
        block[12..16].copy_from_slice(&out[3].to_be_bytes());
    }

    /// Decrypt a single 128-bit block in place.  Same as encryption
    /// with round keys reversed.
    pub fn decrypt_block(&self, block: &mut [u8; 16]) {
        let mut x = [
            u32::from_be_bytes([block[0], block[1], block[2], block[3]]),
            u32::from_be_bytes([block[4], block[5], block[6], block[7]]),
            u32::from_be_bytes([block[8], block[9], block[10], block[11]]),
            u32::from_be_bytes([block[12], block[13], block[14], block[15]]),
        ];
        for i in 0..32 {
            let new_x = x[0] ^ t(x[1] ^ x[2] ^ x[3] ^ self.rk[31 - i]);
            x[0] = x[1];
            x[1] = x[2];
            x[2] = x[3];
            x[3] = new_x;
        }
        let out = [x[3], x[2], x[1], x[0]];
        block[0..4].copy_from_slice(&out[0].to_be_bytes());
        block[4..8].copy_from_slice(&out[1].to_be_bytes());
        block[8..12].copy_from_slice(&out[2].to_be_bytes());
        block[12..16].copy_from_slice(&out[3].to_be_bytes());
    }
}

/// Convenience: encrypt a single block with a fresh-key cipher.
pub fn encrypt_block(key: &[u8; 16], plaintext: &[u8; 16]) -> [u8; 16] {
    let cipher = Sm4::new(key);
    let mut block = *plaintext;
    cipher.encrypt_block(&mut block);
    block
}

/// Convenience: decrypt a single block.
pub fn decrypt_block(key: &[u8; 16], ciphertext: &[u8; 16]) -> [u8; 16] {
    let cipher = Sm4::new(key);
    let mut block = *ciphertext;
    cipher.decrypt_block(&mut block);
    block
}

#[cfg(test)]
mod tests {
    use super::*;

    /// **Test vector from GB/T 32907-2016 Appendix A.1**.
    /// Key = 01 23 45 67 89 ab cd ef fe dc ba 98 76 54 32 10
    /// Plain = 01 23 45 67 89 ab cd ef fe dc ba 98 76 54 32 10
    /// Cipher = 68 1e df 34 d2 06 96 5e 86 b3 e9 4f 53 6e 42 46
    #[test]
    fn sm4_official_test_vector() {
        let key: [u8; 16] = [
            0x01, 0x23, 0x45, 0x67, 0x89, 0xab, 0xcd, 0xef, 0xfe, 0xdc, 0xba, 0x98, 0x76, 0x54,
            0x32, 0x10,
        ];
        let plain: [u8; 16] = key;
        let expected: [u8; 16] = [
            0x68, 0x1e, 0xdf, 0x34, 0xd2, 0x06, 0x96, 0x5e, 0x86, 0xb3, 0xe9, 0x4f, 0x53, 0x6e,
            0x42, 0x46,
        ];
        let ct = encrypt_block(&key, &plain);
        assert_eq!(ct, expected);
    }

    /// **Encrypt → decrypt roundtrip**.
    #[test]
    fn sm4_encrypt_decrypt_roundtrip() {
        let key: [u8; 16] = *b"YELLOW SUBMARINE";
        let plain: [u8; 16] = *b"0123456789ABCDEF";
        let ct = encrypt_block(&key, &plain);
        let pt = decrypt_block(&key, &ct);
        assert_eq!(pt, plain);
        assert_ne!(ct, plain);
    }

    /// **1,000,000 encryption rounds** test vector from GB/T 32907-2016
    /// Appendix A.2.  Starting from the same plaintext / key as A.1,
    /// applying SM4 one million times yields:
    /// 59 52 98 c7 c6 fd 27 1f 04 02 f8 04 c3 3d 3f 66.
    #[test]
    fn sm4_million_iterations() {
        let key: [u8; 16] = [
            0x01, 0x23, 0x45, 0x67, 0x89, 0xab, 0xcd, 0xef, 0xfe, 0xdc, 0xba, 0x98, 0x76, 0x54,
            0x32, 0x10,
        ];
        let cipher = Sm4::new(&key);
        let mut block: [u8; 16] = key;
        for _ in 0..1_000_000 {
            cipher.encrypt_block(&mut block);
        }
        let expected: [u8; 16] = [
            0x59, 0x52, 0x98, 0xc7, 0xc6, 0xfd, 0x27, 0x1f, 0x04, 0x02, 0xf8, 0x04, 0xc3, 0x3d,
            0x3f, 0x66,
        ];
        assert_eq!(block, expected);
    }
}
