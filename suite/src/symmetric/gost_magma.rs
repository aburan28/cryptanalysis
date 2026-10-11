//! **GOST Magma** — 64-bit block cipher.  Originally GOST 28147-89
//! (Soviet 1989) with implementation-defined S-boxes; standardised
//! in **GOST R 34.12-2015** with a fixed S-box (the "id-tc26-gost-
//! 28147-param-Z" parameter set from RFC 7836) and the byte/half
//! conventions documented in **RFC 8891**.
//!
//! ## Structure
//!
//! - 32-round Feistel cipher on 64-bit blocks with a 256-bit key.
//! - Round function `g(K, x) = rotl_11(τ(x ⊞ K))` where ⊞ is mod-2^32
//!   addition and τ applies 8 independent 4-bit S-boxes (one per nibble).
//! - Key schedule: split 256-bit key into eight 32-bit subkeys
//!   `K_1..K_8`.  Round keys cycle through:
//!     - rounds 1–8, 9–16, 17–24: `K_1, K_2, …, K_8`
//!     - rounds 25–32: `K_8, K_7, …, K_1`
//!
//! ## Conventions (RFC 8891 / magma-crate)
//!
//! - Key bytes are read MSB-first: `K_1 = u32::from_be_bytes(key[0..4])`,
//!   so the worked example in RFC 8891 §A.2 has `K_1 = 0xffeeddcc`.
//! - The 64-bit block is split into `n2 = bytes[0..4]` (high half) and
//!   `n1 = bytes[4..8]` (low half).  The Feistel round function `g` is
//!   applied to `n1` (the low half), so a Feistel round is
//!   `(n1, n2) ← (n2 ⊕ g(K, n1), n1)`.
//! - The S-box row `π_i` is applied to the *i*-th nibble counted from
//!   the LSB (so `SBOX[0]` processes the low nibble and `SBOX[7]` the
//!   high nibble).
//! - 32 standard Feistel rounds (with swap) are run, then the output
//!   is written as `bytes[0..4] = n2 ‖ bytes[4..8] = n1`.  This is
//!   equivalent to the spec's "31 swap + 1 no-swap" formulation.
//!
//! ## API
//!
//! - [`Magma`]: keyed cipher with `encrypt_block` / `decrypt_block`.
//! - [`encrypt_block`] / [`decrypt_block`]: stateless block ops.

/// **Standardised S-box** from GOST R 34.12-2015 Annex 1 (id-tc26-
/// gost-28147-param-Z, RFC 7836 §B).  `SBOX[i]` is applied to nibble
/// `i` of the 32-bit value (LSB-first).
const SBOX: [[u8; 16]; 8] = [
    [
        0xC, 0x4, 0x6, 0x2, 0xA, 0x5, 0xB, 0x9, 0xE, 0x8, 0xD, 0x7, 0x0, 0x3, 0xF, 0x1,
    ],
    [
        0x6, 0x8, 0x2, 0x3, 0x9, 0xA, 0x5, 0xC, 0x1, 0xE, 0x4, 0x7, 0xB, 0xD, 0x0, 0xF,
    ],
    [
        0xB, 0x3, 0x5, 0x8, 0x2, 0xF, 0xA, 0xD, 0xE, 0x1, 0x7, 0x4, 0xC, 0x9, 0x6, 0x0,
    ],
    [
        0xC, 0x8, 0x2, 0x1, 0xD, 0x4, 0xF, 0x6, 0x7, 0x0, 0xA, 0x5, 0x3, 0xE, 0x9, 0xB,
    ],
    [
        0x7, 0xF, 0x5, 0xA, 0x8, 0x1, 0x6, 0xD, 0x0, 0x9, 0x3, 0xE, 0xB, 0x4, 0x2, 0xC,
    ],
    [
        0x5, 0xD, 0xF, 0x6, 0x9, 0x2, 0xC, 0xA, 0xB, 0x7, 0x8, 0x1, 0x4, 0x3, 0xE, 0x0,
    ],
    [
        0x8, 0xE, 0x2, 0x5, 0x6, 0x9, 0x1, 0xC, 0xF, 0x4, 0xB, 0x0, 0xD, 0xA, 0x3, 0x7,
    ],
    [
        0x1, 0x7, 0xE, 0xD, 0x0, 0x5, 0x8, 0x3, 0x4, 0xF, 0xA, 0x6, 0x9, 0xC, 0xB, 0x2,
    ],
];

#[inline]
fn s_layer(x: u32) -> u32 {
    let mut out: u32 = 0;
    for i in 0..8 {
        let nibble = ((x >> (i * 4)) & 0xF) as usize;
        out |= (SBOX[i][nibble] as u32) << (i * 4);
    }
    out
}

#[inline]
fn rotl11(x: u32) -> u32 {
    x.rotate_left(11)
}

#[inline]
fn g(x: u32, k: u32) -> u32 {
    rotl11(s_layer(x.wrapping_add(k)))
}

#[derive(Clone, Debug)]
pub struct Magma {
    /// 8 32-bit subkeys.  `k[0] = K_1`, `k[7] = K_8`.
    pub k: [u32; 8],
}

impl Magma {
    /// Construct a Magma cipher from a 256-bit (32-byte) master key.
    ///
    /// Per RFC 8891 §A.2: `K_1` is the first 4 bytes of the key,
    /// interpreted big-endian.  So with key
    /// `ffeeddccbbaa9988…fcfdfeff`, `K_1 = 0xffeeddcc` (stored in
    /// `self.k[0]`) and `K_8 = 0xfcfdfeff` (in `self.k[7]`).
    pub fn new(key: &[u8; 32]) -> Self {
        let mut k = [0u32; 8];
        for i in 0..8 {
            k[i] = u32::from_be_bytes([key[i * 4], key[i * 4 + 1], key[i * 4 + 2], key[i * 4 + 3]]);
        }
        Self { k }
    }

    /// Encrypt a single 64-bit block in place.
    pub fn encrypt_block(&self, block: &mut [u8; 8]) {
        // n2 = high half, n1 = low half.  g is applied to n1.
        let mut n2 = u32::from_be_bytes([block[0], block[1], block[2], block[3]]);
        let mut n1 = u32::from_be_bytes([block[4], block[5], block[6], block[7]]);

        // Rounds 1–24: cycle K_1, K_2, …, K_8 three times.
        for round in 0..24 {
            let k = self.k[round % 8];
            let tmp = n2 ^ g(n1, k);
            n2 = n1;
            n1 = tmp;
        }
        // Rounds 25–32: K_8, K_7, …, K_1.
        for round in 0..8 {
            let k = self.k[7 - round];
            let tmp = n2 ^ g(n1, k);
            n2 = n1;
            n1 = tmp;
        }
        // Output: 32 Feistel-with-swap rounds end with the latest XOR
        // in `n1` and the previous value in `n2`.  Writing n2 first
        // is equivalent to the spec's "no swap on round 32".
        block[0..4].copy_from_slice(&n1.to_be_bytes());
        block[4..8].copy_from_slice(&n2.to_be_bytes());
    }

    /// Decrypt a single 64-bit block in place.
    pub fn decrypt_block(&self, block: &mut [u8; 8]) {
        let mut n2 = u32::from_be_bytes([block[0], block[1], block[2], block[3]]);
        let mut n1 = u32::from_be_bytes([block[4], block[5], block[6], block[7]]);

        // Decryption uses the encryption key schedule reversed:
        // K_1, K_2, …, K_8, then K_8, K_7, …, K_1 cycled three times.
        for round in 0..8 {
            let k = self.k[round];
            let tmp = n2 ^ g(n1, k);
            n2 = n1;
            n1 = tmp;
        }
        for round in 0..24 {
            let k = self.k[7 - (round % 8)];
            let tmp = n2 ^ g(n1, k);
            n2 = n1;
            n1 = tmp;
        }

        block[0..4].copy_from_slice(&n1.to_be_bytes());
        block[4..8].copy_from_slice(&n2.to_be_bytes());
    }
}

/// Convenience: encrypt one 64-bit block under `key`.
pub fn encrypt_block(key: &[u8; 32], plaintext: &[u8; 8]) -> [u8; 8] {
    let cipher = Magma::new(key);
    let mut block = *plaintext;
    cipher.encrypt_block(&mut block);
    block
}

/// Convenience: decrypt one 64-bit block under `key`.
pub fn decrypt_block(key: &[u8; 32], ciphertext: &[u8; 8]) -> [u8; 8] {
    let cipher = Magma::new(key);
    let mut block = *ciphertext;
    cipher.decrypt_block(&mut block);
    block
}

#[cfg(test)]
mod tests {
    use super::*;

    /// **Test vector from GOST R 34.12-2015 Annex A.2.1 / RFC 8891 §A.2**:
    /// `Key   = ffeeddccbbaa99887766554433221100 f0f1f2f3f4f5f6f7f8f9fafbfcfdfeff`
    /// `Plain = fedcba9876543210`
    /// `Cipher = 4ee901e5c2d8ca3d`
    #[test]
    fn magma_official_test_vector() {
        let key: [u8; 32] = [
            0xff, 0xee, 0xdd, 0xcc, 0xbb, 0xaa, 0x99, 0x88, 0x77, 0x66, 0x55, 0x44, 0x33, 0x22,
            0x11, 0x00, 0xf0, 0xf1, 0xf2, 0xf3, 0xf4, 0xf5, 0xf6, 0xf7, 0xf8, 0xf9, 0xfa, 0xfb,
            0xfc, 0xfd, 0xfe, 0xff,
        ];
        let plain: [u8; 8] = [0xfe, 0xdc, 0xba, 0x98, 0x76, 0x54, 0x32, 0x10];
        let expected: [u8; 8] = [0x4e, 0xe9, 0x01, 0xe5, 0xc2, 0xd8, 0xca, 0x3d];
        let ct = encrypt_block(&key, &plain);
        assert_eq!(ct, expected);
    }

    /// **Subkey parsing**: K_1 = 0xffeeddcc, K_8 = 0xfcfdfeff per
    /// RFC 8891 §A.2.
    #[test]
    fn magma_subkey_parsing() {
        let key: [u8; 32] = [
            0xff, 0xee, 0xdd, 0xcc, 0xbb, 0xaa, 0x99, 0x88, 0x77, 0x66, 0x55, 0x44, 0x33, 0x22,
            0x11, 0x00, 0xf0, 0xf1, 0xf2, 0xf3, 0xf4, 0xf5, 0xf6, 0xf7, 0xf8, 0xf9, 0xfa, 0xfb,
            0xfc, 0xfd, 0xfe, 0xff,
        ];
        let m = Magma::new(&key);
        assert_eq!(m.k[0], 0xffeeddcc);
        assert_eq!(m.k[1], 0xbbaa9988);
        assert_eq!(m.k[7], 0xfcfdfeff);
    }

    /// **Encrypt → decrypt roundtrip**.
    #[test]
    fn magma_encrypt_decrypt_roundtrip() {
        let key = [0x42u8; 32];
        let plain: [u8; 8] = [1, 2, 3, 4, 5, 6, 7, 8];
        let ct = encrypt_block(&key, &plain);
        let pt = decrypt_block(&key, &ct);
        assert_eq!(pt, plain);
        assert_ne!(ct, plain);
    }

    /// **Decrypt the official test vector** and recover the plaintext.
    #[test]
    fn magma_official_decrypt_roundtrip() {
        let key: [u8; 32] = [
            0xff, 0xee, 0xdd, 0xcc, 0xbb, 0xaa, 0x99, 0x88, 0x77, 0x66, 0x55, 0x44, 0x33, 0x22,
            0x11, 0x00, 0xf0, 0xf1, 0xf2, 0xf3, 0xf4, 0xf5, 0xf6, 0xf7, 0xf8, 0xf9, 0xfa, 0xfb,
            0xfc, 0xfd, 0xfe, 0xff,
        ];
        let ct: [u8; 8] = [0x4e, 0xe9, 0x01, 0xe5, 0xc2, 0xd8, 0xca, 0x3d];
        let plain: [u8; 8] = [0xfe, 0xdc, 0xba, 0x98, 0x76, 0x54, 0x32, 0x10];
        assert_eq!(decrypt_block(&key, &ct), plain);
    }
}
