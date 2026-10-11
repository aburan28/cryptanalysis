//! **Kuznyechik** — 128-bit block cipher, GOST R 34.12-2015 part 2.
//! Russian national standard, replacing the deprecated 64-bit
//! Magma for modern applications.  "Кузнечик" = grasshopper.
//!
//! ## Structure
//!
//! - 128-bit block, 256-bit key, **9 rounds** + final key XOR.
//! - Round = `X[K_i] ∘ L ∘ S`:
//!   - `S`: 16-parallel 8-bit S-box (`pi`).
//!   - `L`: linear transform over `F_{2^8} = F_2[x]/(x^8 + x^7 +
//!     x^6 + x + 1)`.  Mixes all 16 bytes via 16 iterations of a
//!     linear-feedback shift register (LFSR).
//!   - `X[K_i]`: XOR with round key.
//! - Key schedule: 10 round keys via the same `L S` round
//!   structure applied to the 256-bit key in two 128-bit halves
//!   over 8 Feistel-like steps.

// ── S-box π (256 bytes, fixed in standard) ────────────────────────

const PI: [u8; 256] = [
    0xfc, 0xee, 0xdd, 0x11, 0xcf, 0x6e, 0x31, 0x16, 0xfb, 0xc4, 0xfa, 0xda, 0x23, 0xc5, 0x04, 0x4d,
    0xe9, 0x77, 0xf0, 0xdb, 0x93, 0x2e, 0x99, 0xba, 0x17, 0x36, 0xf1, 0xbb, 0x14, 0xcd, 0x5f, 0xc1,
    0xf9, 0x18, 0x65, 0x5a, 0xe2, 0x5c, 0xef, 0x21, 0x81, 0x1c, 0x3c, 0x42, 0x8b, 0x01, 0x8e, 0x4f,
    0x05, 0x84, 0x02, 0xae, 0xe3, 0x6a, 0x8f, 0xa0, 0x06, 0x0b, 0xed, 0x98, 0x7f, 0xd4, 0xd3, 0x1f,
    0xeb, 0x34, 0x2c, 0x51, 0xea, 0xc8, 0x48, 0xab, 0xf2, 0x2a, 0x68, 0xa2, 0xfd, 0x3a, 0xce, 0xcc,
    0xb5, 0x70, 0x0e, 0x56, 0x08, 0x0c, 0x76, 0x12, 0xbf, 0x72, 0x13, 0x47, 0x9c, 0xb7, 0x5d, 0x87,
    0x15, 0xa1, 0x96, 0x29, 0x10, 0x7b, 0x9a, 0xc7, 0xf3, 0x91, 0x78, 0x6f, 0x9d, 0x9e, 0xb2, 0xb1,
    0x32, 0x75, 0x19, 0x3d, 0xff, 0x35, 0x8a, 0x7e, 0x6d, 0x54, 0xc6, 0x80, 0xc3, 0xbd, 0x0d, 0x57,
    0xdf, 0xf5, 0x24, 0xa9, 0x3e, 0xa8, 0x43, 0xc9, 0xd7, 0x79, 0xd6, 0xf6, 0x7c, 0x22, 0xb9, 0x03,
    0xe0, 0x0f, 0xec, 0xde, 0x7a, 0x94, 0xb0, 0xbc, 0xdc, 0xe8, 0x28, 0x50, 0x4e, 0x33, 0x0a, 0x4a,
    0xa7, 0x97, 0x60, 0x73, 0x1e, 0x00, 0x62, 0x44, 0x1a, 0xb8, 0x38, 0x82, 0x64, 0x9f, 0x26, 0x41,
    0xad, 0x45, 0x46, 0x92, 0x27, 0x5e, 0x55, 0x2f, 0x8c, 0xa3, 0xa5, 0x7d, 0x69, 0xd5, 0x95, 0x3b,
    0x07, 0x58, 0xb3, 0x40, 0x86, 0xac, 0x1d, 0xf7, 0x30, 0x37, 0x6b, 0xe4, 0x88, 0xd9, 0xe7, 0x89,
    0xe1, 0x1b, 0x83, 0x49, 0x4c, 0x3f, 0xf8, 0xfe, 0x8d, 0x53, 0xaa, 0x90, 0xca, 0xd8, 0x85, 0x61,
    0x20, 0x71, 0x67, 0xa4, 0x2d, 0x2b, 0x09, 0x5b, 0xcb, 0x9b, 0x25, 0xd0, 0xbe, 0xe5, 0x6c, 0x52,
    0x59, 0xa6, 0x74, 0xd2, 0xe6, 0xf4, 0xb4, 0xc0, 0xd1, 0x66, 0xaf, 0xc2, 0x39, 0x4b, 0x63, 0xb6,
];

const PI_INV: [u8; 256] = {
    let mut inv = [0u8; 256];
    let mut i = 0;
    while i < 256 {
        inv[PI[i] as usize] = i as u8;
        i += 1;
    }
    inv
};

/// L-transform coefficients (`l_15..l_0` in standard's notation).
const L_COEFFS: [u8; 16] = [
    0x94, 0x20, 0x85, 0x10, 0xC2, 0xC0, 0x01, 0xFB, 0x01, 0xC0, 0xC2, 0x10, 0x85, 0x20, 0x94, 0x01,
];

// ── F_{2^8} arithmetic (irreducible polynomial x^8 + x^7 + x^6 + x + 1 = 0x1C3) ──

#[inline]
fn gmul(mut a: u8, mut b: u8) -> u8 {
    let mut p: u8 = 0;
    for _ in 0..8 {
        if b & 1 == 1 {
            p ^= a;
        }
        let hi = a & 0x80;
        a <<= 1;
        if hi != 0 {
            a ^= 0xC3;
        }
        b >>= 1;
    }
    p
}

// ── Block-level transforms S, L, R ────────────────────────────────

/// `S`: byte-wise S-box layer.
#[inline]
fn s(block: &mut [u8; 16]) {
    for b in block.iter_mut() {
        *b = PI[*b as usize];
    }
}

#[inline]
fn s_inv(block: &mut [u8; 16]) {
    for b in block.iter_mut() {
        *b = PI_INV[*b as usize];
    }
}

/// `R`: single LFSR step.  Compute `s = ⊕ l_i · a_{15-i}`, then
/// shift right (`a_15` drops off, new bytes inserted on the left).
#[inline]
fn r(block: &mut [u8; 16]) {
    let mut s_val: u8 = 0;
    for i in 0..16 {
        s_val ^= gmul(L_COEFFS[i], block[i]);
    }
    block.rotate_right(1);
    block[0] = s_val;
}

/// `R_inv`: inverse LFSR step.
#[inline]
fn r_inv(block: &mut [u8; 16]) {
    let saved = block[0];
    block.rotate_left(1);
    // After rotate-left, byte 15 contains the saved leading byte.
    block[15] = saved;
    // Now block[15] should equal `⊕ l_i · block[(15 - i + 1) mod 16]` from the original.
    // Recover what byte 15 was before R; specifically, original_byte_15
    // satisfies: saved = ⊕ l_i · original_block[i].
    // So original_block[0] = saved ⊕ ⊕_{i≠0} l_i · block_after_R[i+1 mod 16]
    // — but it's easier just to compute the inverse from the formula.
    //
    // Simpler approach: brute-force the leading byte by solving the
    // LFSR equation.  After R: new_block[0] = ⊕ l_i · old_block[i].
    //                             new_block[i+1] = old_block[i] for i in 0..15.
    // To invert: old_block[i] = new_block[i+1] for i in 0..15,
    //            and old_block[15] = solved from the equation.
    //
    // We've already done the rotate; saved is what was new_block[0].
    // We now need block[15] = old_block[15] = saved ⊕ ⊕_{i<15} l_i · old_block[i]
    //                       = saved ⊕ ⊕_{i<15} l_i · block[i+1]  (after our rotation).
    // But l_15 multiplies old_block[15]; l_15 = 0x94.
    // So saved = ⊕ l_i · old_block[i] = ⊕_{i<15} l_i · block_after_rotate[i+1]
    //          ... actually let me redo.

    // Reset (rotate back) and do the math cleanly.
    let saved2 = block[15];
    block.rotate_right(1);
    block[0] = saved;
    // Now block matches the state right after R.
    // R produced: post[0] = ⊕ l_i · pre[i], post[i+1] = pre[i].
    // So pre[i] = post[i+1] for i in 0..15.
    // pre[15] = (post[0] - ⊕_{i<15} l_i · pre[i]) / l_15
    //        = (post[0] ⊕ ⊕_{i<15} l_i · post[i+1]) / l_15.
    // In F_{2^8}, division = multiplication by inverse, but l_15 = 0x94.
    // We need l_15^{-1} in this field.
    let l15_inv = inv_gf256(L_COEFFS[15]);
    let mut acc: u8 = block[0];
    for i in 0..15 {
        acc ^= gmul(L_COEFFS[i], block[i + 1]);
    }
    let pre_15 = gmul(acc, l15_inv);
    // Build the pre-R state.
    for i in 0..15 {
        block[i] = block[i + 1];
    }
    block[15] = pre_15;
    let _ = saved2;
}

/// Compute `a^{-1}` in `F_{2^8}` (with irreducible poly 0x1C3) by
/// Fermat: `a^{254}` (since `|F^*| = 255`).
fn inv_gf256(a: u8) -> u8 {
    if a == 0 {
        return 0;
    }
    // 254 = 11111110_2 = sum of 2^i for i ∈ {1, 2, 3, 4, 5, 6, 7}
    let mut base = gmul(a, a); // a^2
    let mut result = base;
    base = gmul(base, base);
    result = gmul(result, base); // a^2 * a^4 = a^6
    base = gmul(base, base);
    result = gmul(result, base); // a^6 * a^8 = a^14
    base = gmul(base, base);
    result = gmul(result, base); // a^14 * a^16 = a^30
    base = gmul(base, base);
    result = gmul(result, base); // * a^32 = a^62
    base = gmul(base, base);
    result = gmul(result, base); // * a^64 = a^126
    base = gmul(base, base);
    gmul(result, base) // * a^128 = a^254 = a^{-1}
}

/// `L`: apply `R` sixteen times.
#[inline]
fn l_transform(block: &mut [u8; 16]) {
    for _ in 0..16 {
        r(block);
    }
}

#[inline]
fn l_inv(block: &mut [u8; 16]) {
    for _ in 0..16 {
        r_inv(block);
    }
}

#[inline]
fn x_xor(block: &mut [u8; 16], key: &[u8; 16]) {
    for i in 0..16 {
        block[i] ^= key[i];
    }
}

// ── Key schedule ──────────────────────────────────────────────────

fn round_constants() -> [[u8; 16]; 32] {
    let mut cs = [[0u8; 16]; 32];
    for i in 0..32 {
        // C_i has its last byte = i+1, then L applied.
        let mut c = [0u8; 16];
        c[15] = (i + 1) as u8;
        l_transform(&mut c);
        cs[i] = c;
    }
    cs
}

#[derive(Clone, Debug)]
pub struct Kuznyechik {
    round_keys: [[u8; 16]; 10],
}

impl Kuznyechik {
    pub fn new(key: &[u8; 32]) -> Self {
        let mut k1 = [0u8; 16];
        let mut k2 = [0u8; 16];
        k1.copy_from_slice(&key[0..16]);
        k2.copy_from_slice(&key[16..32]);
        let cs = round_constants();
        let mut rks = [[0u8; 16]; 10];
        rks[0] = k1;
        rks[1] = k2;
        for i in 0..4 {
            // 8 Feistel-like rounds per (K1, K2) update.
            for j in 0..8 {
                let mut tmp = k1;
                x_xor(&mut tmp, &cs[8 * i + j]);
                s(&mut tmp);
                l_transform(&mut tmp);
                // Result XORed with K2 gives new K1; old K1 becomes new K2.
                for b in 0..16 {
                    tmp[b] ^= k2[b];
                }
                k2 = k1;
                k1 = tmp;
            }
            rks[2 + 2 * i] = k1;
            rks[2 + 2 * i + 1] = k2;
        }
        Self { round_keys: rks }
    }

    pub fn encrypt_block(&self, block: &mut [u8; 16]) {
        for i in 0..9 {
            x_xor(block, &self.round_keys[i]);
            s(block);
            l_transform(block);
        }
        x_xor(block, &self.round_keys[9]);
    }

    pub fn decrypt_block(&self, block: &mut [u8; 16]) {
        x_xor(block, &self.round_keys[9]);
        for i in (0..9).rev() {
            l_inv(block);
            s_inv(block);
            x_xor(block, &self.round_keys[i]);
        }
    }
}

pub fn encrypt_block(key: &[u8; 32], plain: &[u8; 16]) -> [u8; 16] {
    let c = Kuznyechik::new(key);
    let mut b = *plain;
    c.encrypt_block(&mut b);
    b
}

pub fn decrypt_block(key: &[u8; 32], ct: &[u8; 16]) -> [u8; 16] {
    let c = Kuznyechik::new(key);
    let mut b = *ct;
    c.decrypt_block(&mut b);
    b
}

#[cfg(test)]
mod tests {
    use super::*;

    /// **Test vector from GOST R 34.12-2015 Annex A.1**:
    /// Key   = 8899aabbccddeeff0011223344556677fedcba98765432100123456789abcdef
    /// Plain = 1122334455667700ffeeddccbbaa9988
    /// Cipher = 7f679d90bebc24305a468d42b9d4edcd
    #[test]
    fn kuznyechik_official_test_vector() {
        let key: [u8; 32] = [
            0x88, 0x99, 0xaa, 0xbb, 0xcc, 0xdd, 0xee, 0xff, 0x00, 0x11, 0x22, 0x33, 0x44, 0x55,
            0x66, 0x77, 0xfe, 0xdc, 0xba, 0x98, 0x76, 0x54, 0x32, 0x10, 0x01, 0x23, 0x45, 0x67,
            0x89, 0xab, 0xcd, 0xef,
        ];
        let plain: [u8; 16] = [
            0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x00, 0xff, 0xee, 0xdd, 0xcc, 0xbb, 0xaa,
            0x99, 0x88,
        ];
        let expected: [u8; 16] = [
            0x7f, 0x67, 0x9d, 0x90, 0xbe, 0xbc, 0x24, 0x30, 0x5a, 0x46, 0x8d, 0x42, 0xb9, 0xd4,
            0xed, 0xcd,
        ];
        let ct = encrypt_block(&key, &plain);
        assert_eq!(ct, expected);
    }

    /// **Encrypt → decrypt roundtrip**.
    #[test]
    fn kuznyechik_encrypt_decrypt_roundtrip() {
        let key = [0x42u8; 32];
        let plain: [u8; 16] = *b"0123456789ABCDEF";
        let ct = encrypt_block(&key, &plain);
        let pt = decrypt_block(&key, &ct);
        assert_eq!(pt, plain);
        assert_ne!(ct, plain);
    }

    /// S-box inverse roundtrip.
    #[test]
    fn pi_inverse_is_correct() {
        for i in 0..256u32 {
            assert_eq!(PI_INV[PI[i as usize] as usize], i as u8);
        }
    }

    /// L-transform inverse roundtrip.
    #[test]
    fn l_inverse_recovers_input() {
        let mut block = *b"0123456789ABCDEF";
        let original = block;
        l_transform(&mut block);
        assert_ne!(block, original);
        l_inv(&mut block);
        assert_eq!(block, original);
    }
}
