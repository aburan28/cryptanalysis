//! **SQUARE** — Daemen, Knudsen, Rijmen (FSE 1997).
//!
//! 128-bit block, 128-bit key, 8 rounds.  The direct *precursor* to
//! Rijndael / AES: same designers, same overall round structure
//! (NL-byte-substitution + linear diffusion + AddRoundKey), but with
//! the diffusion arranged differently (a transpose between successive
//! rounds rather than ShiftRows).
//!
//! ## Security status
//!
//! - The **Square attack** (introduced in the original 1997 paper to
//!   break a 6-round variant of SQUARE) is the same dedicated
//!   distinguisher that recovers reduced-round AES (a.k.a. the
//!   *integral attack*).  No practical attack on the full 8 rounds is
//!   known, but the cipher is **superseded** by AES and shipped here
//!   purely for historical and pedagogical interest.
//!
//! ## Algorithm
//!
//! State is a 4 × 4 byte matrix (column-major: byte at row *i*,
//! column *j* lives at position `4*j + i` in the byte stream).  Per
//! round:
//!
//! 1. **γ (gamma)** — non-linear: byte-by-byte S-box `Se` (built from
//!    inversion in GF(2^8) and an affine map; tabulated below).
//! 2. **θ (theta)** — linear diffusion: each row is multiplied by an
//!    MDS matrix with circulant `[2,1,1,3]` in GF(2^8) modulo
//!    `x^8 + x^7 + x^6 + x^5 + x^4 + x^2 + 1` (root `0x1F5`).
//! 3. **π (pi)** — transposition: `b[i][j] = a[j][i]`.
//! 4. **σ (sigma)** — XOR with the round subkey.
//!
//! The cipher is `σ(k_0) ; (γ θ π σ(k_i))_{i=1..7} ; (γ π σ(k_8))`,
//! i.e. the last round skips θ (mirroring AES's "no MixColumns in the
//! final round").
//!
//! ## Test vector (libmcrypt / ESAT-KU Leuven reference C
//! implementation, `sqtest.c`)
//!
//! ```text
//! Key       = 000102030405060708090a0b0c0d0e0f
//! Plaintext = 000102030405060708090a0b0c0d0e0f
//! Ciphertext= 7c3491d94994e70f0ec2e7a5ccb5a14f
//! ```
//!
//! ## References
//!
//! - **Daemen, Knudsen, Rijmen**, *The Block Cipher Square*, FSE 1997.
//! - **V. Rijmen** / **R. De Moliner** reference C implementation.

const ROUNDS: usize = 8;

/// Reduction polynomial for GF(2^8) used by SQUARE:
/// `x^8 + x^7 + x^6 + x^5 + x^4 + x^2 + 1` = 0x1F5.  Note this is
/// *different* from AES's 0x11B; SQUARE picked a polynomial with
/// better diffusion properties in its MDS matrix.
const ROOT: u16 = 0x1F5;

// ── SQUARE S-box (Se) ─────────────────────────────────────────────────
//
// From the libmcrypt / ESAT-KU Leuven reference `square.tab`.

#[rustfmt::skip]
const SE: [u8; 256] = [
    0xb1, 0xce, 0xc3, 0x95, 0x5a, 0xad, 0xe7, 0x02, 0x4d, 0x44, 0xfb, 0x91, 0x0c, 0x87, 0xa1, 0x50,
    0xcb, 0x67, 0x54, 0xdd, 0x46, 0x8f, 0xe1, 0x4e, 0xf0, 0xfd, 0xfc, 0xeb, 0xf9, 0xc4, 0x1a, 0x6e,
    0x5e, 0xf5, 0xcc, 0x8d, 0x1c, 0x56, 0x43, 0xfe, 0x07, 0x61, 0xf8, 0x75, 0x59, 0xff, 0x03, 0x22,
    0x8a, 0xd1, 0x13, 0xee, 0x88, 0x00, 0x0e, 0x34, 0x15, 0x80, 0x94, 0xe3, 0xed, 0xb5, 0x53, 0x23,
    0x4b, 0x47, 0x17, 0xa7, 0x90, 0x35, 0xab, 0xd8, 0xb8, 0xdf, 0x4f, 0x57, 0x9a, 0x92, 0xdb, 0x1b,
    0x3c, 0xc8, 0x99, 0x04, 0x8e, 0xe0, 0xd7, 0x7d, 0x85, 0xbb, 0x40, 0x2c, 0x3a, 0x45, 0xf1, 0x42,
    0x65, 0x20, 0x41, 0x18, 0x72, 0x25, 0x93, 0x70, 0x36, 0x05, 0xf2, 0x0b, 0xa3, 0x79, 0xec, 0x08,
    0x27, 0x31, 0x32, 0xb6, 0x7c, 0xb0, 0x0a, 0x73, 0x5b, 0x7b, 0xb7, 0x81, 0xd2, 0x0d, 0x6a, 0x26,
    0x9e, 0x58, 0x9c, 0x83, 0x74, 0xb3, 0xac, 0x30, 0x7a, 0x69, 0x77, 0x0f, 0xae, 0x21, 0xde, 0xd0,
    0x2e, 0x97, 0x10, 0xa4, 0x98, 0xa8, 0xd4, 0x68, 0x2d, 0x62, 0x29, 0x6d, 0x16, 0x49, 0x76, 0xc7,
    0xe8, 0xc1, 0x96, 0x37, 0xe5, 0xca, 0xf4, 0xe9, 0x63, 0x12, 0xc2, 0xa6, 0x14, 0xbc, 0xd3, 0x28,
    0xaf, 0x2f, 0xe6, 0x24, 0x52, 0xc6, 0xa0, 0x09, 0xbd, 0x8c, 0xcf, 0x5d, 0x11, 0x5f, 0x01, 0xc5,
    0x9f, 0x3d, 0xa2, 0x9b, 0xc9, 0x3b, 0xbe, 0x51, 0x19, 0x1f, 0x3f, 0x5c, 0xb2, 0xef, 0x4a, 0xcd,
    0xbf, 0xba, 0x6f, 0x64, 0xd9, 0xf3, 0x3e, 0xb4, 0xaa, 0xdc, 0xd5, 0x06, 0xc0, 0x7e, 0xf6, 0x66,
    0x6c, 0x84, 0x71, 0x38, 0xb9, 0x1d, 0x7f, 0x9d, 0x48, 0x8b, 0x2a, 0xda, 0xa5, 0x33, 0x82, 0x39,
    0xd6, 0x78, 0x86, 0xfa, 0xe4, 0x2b, 0xa9, 0x1e, 0x89, 0x60, 0x6b, 0xea, 0x55, 0x4c, 0xf7, 0xe2,
];

#[rustfmt::skip]
const SD: [u8; 256] = [
    0x35, 0xbe, 0x07, 0x2e, 0x53, 0x69, 0xdb, 0x28, 0x6f, 0xb7, 0x76, 0x6b, 0x0c, 0x7d, 0x36, 0x8b,
    0x92, 0xbc, 0xa9, 0x32, 0xac, 0x38, 0x9c, 0x42, 0x63, 0xc8, 0x1e, 0x4f, 0x24, 0xe5, 0xf7, 0xc9,
    0x61, 0x8d, 0x2f, 0x3f, 0xb3, 0x65, 0x7f, 0x70, 0xaf, 0x9a, 0xea, 0xf5, 0x5b, 0x98, 0x90, 0xb1,
    0x87, 0x71, 0x72, 0xed, 0x37, 0x45, 0x68, 0xa3, 0xe3, 0xef, 0x5c, 0xc5, 0x50, 0xc1, 0xd6, 0xca,
    0x5a, 0x62, 0x5f, 0x26, 0x09, 0x5d, 0x14, 0x41, 0xe8, 0x9d, 0xce, 0x40, 0xfd, 0x08, 0x17, 0x4a,
    0x0f, 0xc7, 0xb4, 0x3e, 0x12, 0xfc, 0x25, 0x4b, 0x81, 0x2c, 0x04, 0x78, 0xcb, 0xbb, 0x20, 0xbd,
    0xf9, 0x29, 0x99, 0xa8, 0xd3, 0x60, 0xdf, 0x11, 0x97, 0x89, 0x7e, 0xfa, 0xe0, 0x9b, 0x1f, 0xd2,
    0x67, 0xe2, 0x64, 0x77, 0x84, 0x2b, 0x9e, 0x8a, 0xf1, 0x6d, 0x88, 0x79, 0x74, 0x57, 0xdd, 0xe6,
    0x39, 0x7b, 0xee, 0x83, 0xe1, 0x58, 0xf2, 0x0d, 0x34, 0xf8, 0x30, 0xe9, 0xb9, 0x23, 0x54, 0x15,
    0x44, 0x0b, 0x4d, 0x66, 0x3a, 0x03, 0xa2, 0x91, 0x94, 0x52, 0x4c, 0xc3, 0x82, 0xe7, 0x80, 0xc0,
    0xb6, 0x0e, 0xc2, 0x6c, 0x93, 0xec, 0xab, 0x43, 0x95, 0xf6, 0xd8, 0x46, 0x86, 0x05, 0x8c, 0xb0,
    0x75, 0x00, 0xcc, 0x85, 0xd7, 0x3d, 0x73, 0x7a, 0x48, 0xe4, 0xd1, 0x59, 0xad, 0xb8, 0xc6, 0xd0,
    0xdc, 0xa1, 0xaa, 0x02, 0x1d, 0xbf, 0xb5, 0x9f, 0x51, 0xc4, 0xa5, 0x10, 0x22, 0xcf, 0x01, 0xba,
    0x8f, 0x31, 0x7c, 0xae, 0x96, 0xda, 0xf0, 0x56, 0x47, 0xd4, 0xeb, 0x4e, 0xd9, 0x13, 0x8e, 0x49,
    0x55, 0x16, 0xff, 0x3b, 0xf4, 0xa4, 0xb2, 0x06, 0xa0, 0xa7, 0xfb, 0x1b, 0x6e, 0x3c, 0x33, 0xcd,
    0x18, 0x5e, 0x6a, 0xd5, 0xa6, 0x21, 0xde, 0xfe, 0x2a, 0x1c, 0xf3, 0x0a, 0x1a, 0x19, 0x27, 0x2d,
];

// ── GF(2^8) multiplication for the diffusion matrix θ ────────────────

/// Multiply two bytes in `GF(2^8)` with reduction polynomial 0x1F5.
fn gmul(a: u8, b: u8) -> u8 {
    let mut p: u16 = 0;
    let mut a: u16 = a as u16;
    let mut b: u8 = b;
    for _ in 0..8 {
        if b & 1 != 0 {
            p ^= a;
        }
        b >>= 1;
        a <<= 1;
        if a & 0x100 != 0 {
            a ^= ROOT;
        }
    }
    p as u8
}

/// Generate the 8 `offset[]` round constants used by the key schedule:
/// `offset[0] = 1`, `offset[i] = 2 · offset[i-1]` in `GF(2^8)`.  Each
/// constant is a single byte; in the C reference it's XORed into a
/// 32-bit word, so it affects only the low byte (LSB-end) of that word.
fn offsets() -> [u32; ROUNDS] {
    let mut out = [0u32; ROUNDS];
    let mut o: u8 = 1;
    out[0] = o as u32;
    for i in 1..ROUNDS {
        o = gmul(2, o);
        out[i] = o as u32;
    }
    out
}

// ── Round transformations (γ θ π) ────────────────────────────────────
//
// We work on a 16-byte state laid out column-major: state[4*j + i]
// is the byte at row i, column j.  This matches the byte order of
// the libmcrypt reference's `text[]` words.

#[inline]
fn gamma(state: &mut [u8; 16], sbox: &[u8; 256]) {
    for b in state.iter_mut() {
        *b = sbox[*b as usize];
    }
}

/// π (pi): transposition `b[i][j] = a[j][i]` of the 4 × 4 byte matrix.
#[inline]
fn pi(state: &mut [u8; 16]) {
    let mut new = [0u8; 16];
    for i in 0..4 {
        for j in 0..4 {
            // (row, col) = (i, j) → byte index 4*j + i (column-major).
            new[4 * i + j] = state[4 * j + i];
        }
    }
    *state = new;
}

/// θ (theta): MixColumns — each column (4 contiguous bytes
/// `state[4c..4c+4]`) is left-multiplied by the SQUARE MDS matrix
///
/// ```text
///   ⎛ 2 3 1 1 ⎞
///   ⎜ 1 2 3 1 ⎟
///   ⎜ 1 1 2 3 ⎟
///   ⎝ 3 1 1 2 ⎠
/// ```
///
/// over `GF(2^8)` with reduction polynomial `0x1F5`.
#[inline]
fn theta(state: &mut [u8; 16]) {
    let mut new = [0u8; 16];
    for c in 0..4 {
        let a = state[4 * c];
        let b = state[4 * c + 1];
        let cc = state[4 * c + 2];
        let d = state[4 * c + 3];
        new[4 * c] = gmul(2, a) ^ gmul(3, b) ^ gmul(1, cc) ^ gmul(1, d);
        new[4 * c + 1] = gmul(1, a) ^ gmul(2, b) ^ gmul(3, cc) ^ gmul(1, d);
        new[4 * c + 2] = gmul(1, a) ^ gmul(1, b) ^ gmul(2, cc) ^ gmul(3, d);
        new[4 * c + 3] = gmul(3, a) ^ gmul(1, b) ^ gmul(1, cc) ^ gmul(2, d);
    }
    *state = new;
}

/// θ⁻¹: multiply each column by the inverse MDS matrix.  The MDS
/// matrix's inverse in `GF(2^8)` with reduction `0x1F5` has the *same*
/// integer coefficients as AES's MixColumns⁻¹ (the polynomial is
/// different but the matrix invariants coincide):
/// first column = `[0x0E, 0x09, 0x0D, 0x0B]`.
#[inline]
fn theta_inv(state: &mut [u8; 16]) {
    let mut new = [0u8; 16];
    for c in 0..4 {
        let a = state[4 * c];
        let b = state[4 * c + 1];
        let cc = state[4 * c + 2];
        let d = state[4 * c + 3];
        new[4 * c] = gmul(0x0E, a) ^ gmul(0x0B, b) ^ gmul(0x0D, cc) ^ gmul(0x09, d);
        new[4 * c + 1] = gmul(0x09, a) ^ gmul(0x0E, b) ^ gmul(0x0B, cc) ^ gmul(0x0D, d);
        new[4 * c + 2] = gmul(0x0D, a) ^ gmul(0x09, b) ^ gmul(0x0E, cc) ^ gmul(0x0B, d);
        new[4 * c + 3] = gmul(0x0B, a) ^ gmul(0x0D, b) ^ gmul(0x09, cc) ^ gmul(0x0E, d);
    }
    *state = new;
}

// ── Key schedule ──────────────────────────────────────────────────────
//
// From the reference C `squareGenerateRoundKeys`.  RoundKey[0] = input
// key.  Each subsequent round key is derived from the previous by a
// rotating XOR + offset constant, then the *previous* round key is
// passed through the θ-style transform to become the actual encryption
// subkey.  Decryption subkeys are the same set but in reverse order
// with θ⁻¹ applied to all but the first and last.

fn key_schedule(key: &[u8; 16]) -> [[u8; 16]; ROUNDS + 1] {
    let offsets = offsets();
    let mut ke: [[u8; 16]; ROUNDS + 1] = [[0u8; 16]; ROUNDS + 1];
    ke[0].copy_from_slice(key);

    for t in 1..=ROUNDS {
        // Treat each round-key as 4 column-words (32 bits, little-endian).
        let prev = ke[t - 1];
        let w0 = u32::from_le_bytes([prev[0], prev[1], prev[2], prev[3]]);
        let w1 = u32::from_le_bytes([prev[4], prev[5], prev[6], prev[7]]);
        let w2 = u32::from_le_bytes([prev[8], prev[9], prev[10], prev[11]]);
        let w3 = u32::from_le_bytes([prev[12], prev[13], prev[14], prev[15]]);
        // Reference: `PSI_ROTL(rk[3], 8)` — on a little-endian view of
        // bytes-in-words, this rotates the column "up" by one row.
        let new_w0 = w0 ^ w3.rotate_right(8) ^ offsets[t - 1];
        let new_w1 = w1 ^ new_w0;
        let new_w2 = w2 ^ new_w1;
        let new_w3 = w3 ^ new_w2;

        let mut next = [0u8; 16];
        next[0..4].copy_from_slice(&new_w0.to_le_bytes());
        next[4..8].copy_from_slice(&new_w1.to_le_bytes());
        next[8..12].copy_from_slice(&new_w2.to_le_bytes());
        next[12..16].copy_from_slice(&new_w3.to_le_bytes());
        ke[t] = next;

        // Apply θ to ke[t-1] in place: it becomes the actual subkey
        // for round t-1.  ke[ROUNDS] is NOT θ-applied (the loop body
        // applies θ to ke[t-1], so ke[ROUNDS] never gets transformed).
        let mut prev_mut = ke[t - 1];
        theta(&mut prev_mut);
        ke[t - 1] = prev_mut;
    }
    ke
}

// ── Cipher ───────────────────────────────────────────────────────────

#[derive(Clone, Debug)]
pub struct Square {
    ke: [[u8; 16]; ROUNDS + 1],
}

impl Square {
    /// Construct a SQUARE cipher from a 128-bit key.
    pub fn new(key: &[u8; 16]) -> Self {
        Self {
            ke: key_schedule(key),
        }
    }

    /// Encrypt one 128-bit block in place.
    ///
    /// Structure: σ(k0) ; (γ π θ σ(k_r))_{r=1..7} ; (γ π σ(k_8)).
    pub fn encrypt_block(&self, block: &mut [u8; 16]) {
        for i in 0..16 {
            block[i] ^= self.ke[0][i];
        }
        for r in 1..ROUNDS {
            gamma(block, &SE);
            pi(block);
            theta(block);
            for i in 0..16 {
                block[i] ^= self.ke[r][i];
            }
        }
        // Final round: γ π σ (no θ).
        gamma(block, &SE);
        pi(block);
        for i in 0..16 {
            block[i] ^= self.ke[ROUNDS][i];
        }
    }

    /// Decrypt one 128-bit block in place.
    ///
    /// Literal inverse of encrypt: reverse the order of operations and
    /// substitute each by its inverse.  Since π is a transposition,
    /// π⁻¹ = π.
    pub fn decrypt_block(&self, block: &mut [u8; 16]) {
        // Undo the final round (γ π σ).
        for i in 0..16 {
            block[i] ^= self.ke[ROUNDS][i];
        }
        pi(block);
        gamma(block, &SD);

        // Undo full rounds R-1 down to 1: each was (γ π θ σ).
        for r in (1..ROUNDS).rev() {
            for i in 0..16 {
                block[i] ^= self.ke[r][i];
            }
            theta_inv(block);
            pi(block);
            gamma(block, &SD);
        }

        // Undo the initial σ(k_0).
        for i in 0..16 {
            block[i] ^= self.ke[0][i];
        }
    }
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// **libmcrypt / ESAT-KU Leuven `sqtest.c` reference vector**:
    /// `Key = PT = 000102030405060708090a0b0c0d0e0f`,
    /// `CT  = 7c3491d94994e70f0ec2e7a5ccb5a14f`.
    #[test]
    fn square_libmcrypt_reference() {
        let key: [u8; 16] = [
            0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d,
            0x0e, 0x0f,
        ];
        let mut block: [u8; 16] = key;
        let expected: [u8; 16] = [
            0x7c, 0x34, 0x91, 0xd9, 0x49, 0x94, 0xe7, 0x0f, 0x0e, 0xc2, 0xe7, 0xa5, 0xcc, 0xb5,
            0xa1, 0x4f,
        ];
        let c = Square::new(&key);
        c.encrypt_block(&mut block);
        assert_eq!(block, expected);
    }

    /// Decryption recovers the plaintext.
    #[test]
    fn square_libmcrypt_decrypt() {
        let key: [u8; 16] = [
            0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d,
            0x0e, 0x0f,
        ];
        let mut block: [u8; 16] = [
            0x7c, 0x34, 0x91, 0xd9, 0x49, 0x94, 0xe7, 0x0f, 0x0e, 0xc2, 0xe7, 0xa5, 0xcc, 0xb5,
            0xa1, 0x4f,
        ];
        let c = Square::new(&key);
        c.decrypt_block(&mut block);
        assert_eq!(block, key);
    }

    /// Encrypt → decrypt round-trip across several inputs.
    #[test]
    fn square_round_trip() {
        let key = [0xA5u8; 16];
        let c = Square::new(&key);
        for v in 0u8..32 {
            let mut p = [0u8; 16];
            p[0] = v;
            p[15] = v.wrapping_mul(7);
            let saved = p;
            c.encrypt_block(&mut p);
            c.decrypt_block(&mut p);
            assert_eq!(p, saved, "round-trip failed at v={v}");
        }
    }

    /// S-boxes Se and Sd are mutual inverses.
    #[test]
    fn square_sbox_inverse() {
        for x in 0u16..=255 {
            assert_eq!(SD[SE[x as usize] as usize] as u16, x);
            assert_eq!(SE[SD[x as usize] as usize] as u16, x);
        }
    }
}
