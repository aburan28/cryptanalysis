//! **Twofish** — 128-bit block cipher (Schneier, Kelsey, Whiting, Wagner,
//! Hall, Ferguson; AES finalist, 1998).
//!
//! Twofish is a 16-round Feistel cipher with key-dependent 8×8 S-boxes
//! built from the fixed `q0`/`q1` permutations, an MDS matrix over
//! GF(2^8)/0x169, and a Reed-Solomon code over GF(2^8)/0x14d for
//! deriving the S-vector from the master key.  The round function
//! interleaves the Feistel half-swap with a one-bit rotation and a
//! pseudo-Hadamard transform on the two `g`-function outputs.
//!
//! ## Variants
//!
//! Twofish accepts 128-, 192-, or 256-bit keys.  All variants use the
//! same 16-round structure; the key schedule's `k = keylen / 64`
//! controls how many bytes of the master key feed `q0`/`q1` in the
//! `h`-function and the size of the RS-derived S-vector.
//!
//! ## API
//!
//! [`Twofish::new`] accepts a 16-, 24-, or 32-byte key slice and returns
//! `Err` for any other length, matching the [`super::aes::AesKey`] and
//! [`super::serpent::SerpentKey`] convention used elsewhere in the
//! crate.
//!
//! ## Byte conventions
//!
//! The block and key are little-endian 32-bit words concatenated
//! low-index-first, as specified in §3 of the Twofish paper.  So
//! `Plain = bytes[0..16]` decodes to `(P_0, P_1, P_2, P_3)` with
//! `P_i = u32::from_le_bytes(bytes[4i..4i+4])`.
//!
//! ## Security note
//!
//! Twofish was an AES finalist (selected as one of the five, runner-up
//! to Rijndael).  No public break against the full 16-round cipher is
//! known and it remains widely regarded as secure, but AES has far
//! broader deployment, hardware acceleration, and ongoing analysis.
//! This implementation is included for pedagogy and interoperability.

// ── q0 / q1 permutations (Twofish paper §4.3.5, Table 7) ─────────────

#[rustfmt::skip]
const Q0: [u8; 256] = [
    0xA9, 0x67, 0xB3, 0xE8, 0x04, 0xFD, 0xA3, 0x76, 0x9A, 0x92, 0x80, 0x78, 0xE4, 0xDD, 0xD1, 0x38,
    0x0D, 0xC6, 0x35, 0x98, 0x18, 0xF7, 0xEC, 0x6C, 0x43, 0x75, 0x37, 0x26, 0xFA, 0x13, 0x94, 0x48,
    0xF2, 0xD0, 0x8B, 0x30, 0x84, 0x54, 0xDF, 0x23, 0x19, 0x5B, 0x3D, 0x59, 0xF3, 0xAE, 0xA2, 0x82,
    0x63, 0x01, 0x83, 0x2E, 0xD9, 0x51, 0x9B, 0x7C, 0xA6, 0xEB, 0xA5, 0xBE, 0x16, 0x0C, 0xE3, 0x61,
    0xC0, 0x8C, 0x3A, 0xF5, 0x73, 0x2C, 0x25, 0x0B, 0xBB, 0x4E, 0x89, 0x6B, 0x53, 0x6A, 0xB4, 0xF1,
    0xE1, 0xE6, 0xBD, 0x45, 0xE2, 0xF4, 0xB6, 0x66, 0xCC, 0x95, 0x03, 0x56, 0xD4, 0x1C, 0x1E, 0xD7,
    0xFB, 0xC3, 0x8E, 0xB5, 0xE9, 0xCF, 0xBF, 0xBA, 0xEA, 0x77, 0x39, 0xAF, 0x33, 0xC9, 0x62, 0x71,
    0x81, 0x79, 0x09, 0xAD, 0x24, 0xCD, 0xF9, 0xD8, 0xE5, 0xC5, 0xB9, 0x4D, 0x44, 0x08, 0x86, 0xE7,
    0xA1, 0x1D, 0xAA, 0xED, 0x06, 0x70, 0xB2, 0xD2, 0x41, 0x7B, 0xA0, 0x11, 0x31, 0xC2, 0x27, 0x90,
    0x20, 0xF6, 0x60, 0xFF, 0x96, 0x5C, 0xB1, 0xAB, 0x9E, 0x9C, 0x52, 0x1B, 0x5F, 0x93, 0x0A, 0xEF,
    0x91, 0x85, 0x49, 0xEE, 0x2D, 0x4F, 0x8F, 0x3B, 0x47, 0x87, 0x6D, 0x46, 0xD6, 0x3E, 0x69, 0x64,
    0x2A, 0xCE, 0xCB, 0x2F, 0xFC, 0x97, 0x05, 0x7A, 0xAC, 0x7F, 0xD5, 0x1A, 0x4B, 0x0E, 0xA7, 0x5A,
    0x28, 0x14, 0x3F, 0x29, 0x88, 0x3C, 0x4C, 0x02, 0xB8, 0xDA, 0xB0, 0x17, 0x55, 0x1F, 0x8A, 0x7D,
    0x57, 0xC7, 0x8D, 0x74, 0xB7, 0xC4, 0x9F, 0x72, 0x7E, 0x15, 0x22, 0x12, 0x58, 0x07, 0x99, 0x34,
    0x6E, 0x50, 0xDE, 0x68, 0x65, 0xBC, 0xDB, 0xF8, 0xC8, 0xA8, 0x2B, 0x40, 0xDC, 0xFE, 0x32, 0xA4,
    0xCA, 0x10, 0x21, 0xF0, 0xD3, 0x5D, 0x0F, 0x00, 0x6F, 0x9D, 0x36, 0x42, 0x4A, 0x5E, 0xC1, 0xE0,
];

#[rustfmt::skip]
const Q1: [u8; 256] = [
    0x75, 0xF3, 0xC6, 0xF4, 0xDB, 0x7B, 0xFB, 0xC8, 0x4A, 0xD3, 0xE6, 0x6B, 0x45, 0x7D, 0xE8, 0x4B,
    0xD6, 0x32, 0xD8, 0xFD, 0x37, 0x71, 0xF1, 0xE1, 0x30, 0x0F, 0xF8, 0x1B, 0x87, 0xFA, 0x06, 0x3F,
    0x5E, 0xBA, 0xAE, 0x5B, 0x8A, 0x00, 0xBC, 0x9D, 0x6D, 0xC1, 0xB1, 0x0E, 0x80, 0x5D, 0xD2, 0xD5,
    0xA0, 0x84, 0x07, 0x14, 0xB5, 0x90, 0x2C, 0xA3, 0xB2, 0x73, 0x4C, 0x54, 0x92, 0x74, 0x36, 0x51,
    0x38, 0xB0, 0xBD, 0x5A, 0xFC, 0x60, 0x62, 0x96, 0x6C, 0x42, 0xF7, 0x10, 0x7C, 0x28, 0x27, 0x8C,
    0x13, 0x95, 0x9C, 0xC7, 0x24, 0x46, 0x3B, 0x70, 0xCA, 0xE3, 0x85, 0xCB, 0x11, 0xD0, 0x93, 0xB8,
    0xA6, 0x83, 0x20, 0xFF, 0x9F, 0x77, 0xC3, 0xCC, 0x03, 0x6F, 0x08, 0xBF, 0x40, 0xE7, 0x2B, 0xE2,
    0x79, 0x0C, 0xAA, 0x82, 0x41, 0x3A, 0xEA, 0xB9, 0xE4, 0x9A, 0xA4, 0x97, 0x7E, 0xDA, 0x7A, 0x17,
    0x66, 0x94, 0xA1, 0x1D, 0x3D, 0xF0, 0xDE, 0xB3, 0x0B, 0x72, 0xA7, 0x1C, 0xEF, 0xD1, 0x53, 0x3E,
    0x8F, 0x33, 0x26, 0x5F, 0xEC, 0x76, 0x2A, 0x49, 0x81, 0x88, 0xEE, 0x21, 0xC4, 0x1A, 0xEB, 0xD9,
    0xC5, 0x39, 0x99, 0xCD, 0xAD, 0x31, 0x8B, 0x01, 0x18, 0x23, 0xDD, 0x1F, 0x4E, 0x2D, 0xF9, 0x48,
    0x4F, 0xF2, 0x65, 0x8E, 0x78, 0x5C, 0x58, 0x19, 0x8D, 0xE5, 0x98, 0x57, 0x67, 0x7F, 0x05, 0x64,
    0xAF, 0x63, 0xB6, 0xFE, 0xF5, 0xB7, 0x3C, 0xA5, 0xCE, 0xE9, 0x68, 0x44, 0xE0, 0x4D, 0x43, 0x69,
    0x29, 0x2E, 0xAC, 0x15, 0x59, 0xA8, 0x0A, 0x9E, 0x6E, 0x47, 0xDF, 0x34, 0x35, 0x6A, 0xCF, 0xDC,
    0x22, 0xC9, 0xC0, 0x9B, 0x89, 0xD4, 0xED, 0xAB, 0x12, 0xA2, 0x0D, 0x52, 0xBB, 0x02, 0x2F, 0xA9,
    0xD7, 0x61, 0x1E, 0xB4, 0x50, 0x04, 0xF6, 0xC2, 0x16, 0x25, 0x86, 0x56, 0x55, 0x09, 0xBE, 0x91,
];

// ── GF(2^8) multiplication for MDS and RS layers ─────────────────────

/// Multiply two bytes in GF(2^8) modulo a 9-bit irreducible polynomial
/// `p` (the high bit is its leading 1).  Branchless, but the bit
/// pattern of the operands shapes the runtime constant pool only.
fn gf_mult(a: u8, b: u8, p: u32) -> u8 {
    let p_table = [0u32, p];
    let mut bb = [0u32, b as u32];
    let mut result: u32 = 0;
    let mut a = a;
    for _ in 0..7 {
        result ^= bb[(a & 1) as usize];
        a >>= 1;
        bb[1] = p_table[(bb[1] >> 7) as usize] ^ (bb[1] << 1);
    }
    result ^= bb[(a & 1) as usize];
    (result & 0xFF) as u8
}

/// MDS field: GF(2^8) with primitive polynomial `x^8 + x^6 + x^5 + x^3 + 1`
/// (= `0x169`).  Paper §4.2.
const MDS_POLY: u32 = 0x169;

/// RS field: GF(2^8) with primitive polynomial `x^8 + x^6 + x^3 + x^2 + 1`
/// (= `0x14D`).  Paper §4.3.
const RS_POLY: u32 = 0x14D;

/// Compute one byte of `MDS · [x, 0, 0, 0]` shifted into column `col`
/// of a 32-bit word.  The MDS matrix has only three distinct GF
/// constants: `0x01`, `0x5B`, `0xEF`.
fn mds_column_mult(x: u8, col: usize) -> u32 {
    let x01 = x as u32;
    let x5b = gf_mult(x, 0x5B, MDS_POLY) as u32;
    let xef = gf_mult(x, 0xEF, MDS_POLY) as u32;
    match col {
        0 => x01 | (x5b << 8) | (xef << 16) | (xef << 24),
        1 => xef | (xef << 8) | (x5b << 16) | (x01 << 24),
        2 => x5b | (xef << 8) | (x01 << 16) | (xef << 24),
        3 => x5b | (x01 << 8) | (xef << 16) | (x5b << 24),
        _ => unreachable!(),
    }
}

/// RS matrix (Twofish paper §4.3.7).
const RS: [[u8; 8]; 4] = [
    [0x01, 0xA4, 0x55, 0x87, 0x5A, 0x58, 0xDB, 0x9E],
    [0xA4, 0x56, 0x82, 0xF3, 0x1E, 0xC6, 0x68, 0xE5],
    [0x02, 0xA1, 0xFC, 0xC1, 0x47, 0xAE, 0x3D, 0x19],
    [0xA4, 0x55, 0x87, 0x5A, 0x58, 0xDB, 0x9E, 0x03],
];

// ── h-function ───────────────────────────────────────────────────────

/// The Twofish `h` function applied to a 4-byte input.  `key_len` is
/// the master-key byte length (16, 24, or 32) and `key` is the master
/// key; `offset` selects the Me (`offset = 0`) or Mo (`offset = 1`)
/// half of the key when picking byte slices.  Returns a 32-bit word.
///
/// This matches the layered structure of the reference LibTomCrypt /
/// Go `golang.org/x/crypto/twofish` implementation, which is what the
/// `twofish` PyPI package and Crypto++ both produce identical
/// ciphertexts for.
fn h(input: [u8; 4], key: &[u8], offset: usize) -> u32 {
    let k_words = key.len() / 8;
    let mut y = input;
    if k_words == 4 {
        y[0] = Q1[y[0] as usize] ^ key[4 * (6 + offset)];
        y[1] = Q0[y[1] as usize] ^ key[4 * (6 + offset) + 1];
        y[2] = Q0[y[2] as usize] ^ key[4 * (6 + offset) + 2];
        y[3] = Q1[y[3] as usize] ^ key[4 * (6 + offset) + 3];
    }
    if k_words >= 3 {
        y[0] = Q1[y[0] as usize] ^ key[4 * (4 + offset)];
        y[1] = Q1[y[1] as usize] ^ key[4 * (4 + offset) + 1];
        y[2] = Q0[y[2] as usize] ^ key[4 * (4 + offset) + 2];
        y[3] = Q0[y[3] as usize] ^ key[4 * (4 + offset) + 3];
    }
    // k_words == 2 base layer.
    y[0] =
        Q1[(Q0[(Q0[y[0] as usize] ^ key[4 * (2 + offset)]) as usize] ^ key[4 * offset]) as usize];
    y[1] = Q0[(Q0[(Q1[y[1] as usize] ^ key[4 * (2 + offset) + 1]) as usize] ^ key[4 * offset + 1])
        as usize];
    y[2] = Q1[(Q1[(Q0[y[2] as usize] ^ key[4 * (2 + offset) + 2]) as usize] ^ key[4 * offset + 2])
        as usize];
    y[3] = Q0[(Q1[(Q1[y[3] as usize] ^ key[4 * (2 + offset) + 3]) as usize] ^ key[4 * offset + 3])
        as usize];

    // [y0 y1 y2 y3] = MDS · y
    let mut out = 0u32;
    for (i, &yi) in y.iter().enumerate() {
        out ^= mds_column_mult(yi, i);
    }
    out
}

// ── Twofish cipher ────────────────────────────────────────────────────

/// Twofish block cipher with a 128-, 192-, or 256-bit key.
#[derive(Clone, Debug)]
pub struct Twofish {
    /// 40 expanded 32-bit subkeys: `K_0..K_7` are whitening, then
    /// `K_{8+2r}` and `K_{9+2r}` are the round subkeys for round `r`.
    k: [u32; 40],
    /// Four key-dependent 256-entry S-boxes, each entry already merged
    /// with the corresponding MDS column.  `g(X) = ⊕ s[i][byte_i(X)]`.
    s: [[u32; 256]; 4],
}

impl Twofish {
    /// Build a Twofish cipher from a 16-, 24-, or 32-byte key.  Returns
    /// `Err` for any other length.
    pub fn new(key: &[u8]) -> Result<Self, &'static str> {
        let keylen = key.len();
        if keylen != 16 && keylen != 24 && keylen != 32 {
            return Err("Twofish key must be 16, 24, or 32 bytes");
        }
        let k_words = keylen / 8;

        // ── Derive the S-vector via RS · key chunks ───────────────────
        // `s_vec[4*i + j]` is byte j of the i-th 32-bit S-word.
        let mut s_vec = [0u8; 16];
        for i in 0..k_words {
            for (j, row) in RS.iter().enumerate() {
                let mut acc = 0u8;
                for (col, &rv) in row.iter().enumerate() {
                    acc ^= gf_mult(key[8 * i + col], rv, RS_POLY);
                }
                s_vec[4 * i + j] ^= acc;
            }
        }

        // ── Expand 40 round subkeys ───────────────────────────────────
        let mut k_sched = [0u32; 40];
        for i in 0u8..20 {
            let tmp = [2 * i, 2 * i, 2 * i, 2 * i];
            let a = h(tmp, key, 0);
            let tmp = [2 * i + 1, 2 * i + 1, 2 * i + 1, 2 * i + 1];
            let b = h(tmp, key, 1).rotate_left(8);
            k_sched[2 * i as usize] = a.wrapping_add(b);
            k_sched[2 * i as usize + 1] = a.wrapping_add(b).wrapping_add(b).rotate_left(9);
        }

        // ── Precompute the four key-dependent S-boxes ─────────────────
        let mut s = [[0u32; 256]; 4];
        match k_words {
            2 => {
                for i in 0..256usize {
                    let b = i as u8;
                    s[0][i] = mds_column_mult(
                        Q1[(Q0[(Q0[b as usize] ^ s_vec[0]) as usize] ^ s_vec[4]) as usize],
                        0,
                    );
                    s[1][i] = mds_column_mult(
                        Q0[(Q0[(Q1[b as usize] ^ s_vec[1]) as usize] ^ s_vec[5]) as usize],
                        1,
                    );
                    s[2][i] = mds_column_mult(
                        Q1[(Q1[(Q0[b as usize] ^ s_vec[2]) as usize] ^ s_vec[6]) as usize],
                        2,
                    );
                    s[3][i] = mds_column_mult(
                        Q0[(Q1[(Q1[b as usize] ^ s_vec[3]) as usize] ^ s_vec[7]) as usize],
                        3,
                    );
                }
            }
            3 => {
                for i in 0..256usize {
                    let b = i as u8;
                    s[0][i] = mds_column_mult(
                        Q1[(Q0[(Q0[(Q1[b as usize] ^ s_vec[0]) as usize] ^ s_vec[4]) as usize]
                            ^ s_vec[8]) as usize],
                        0,
                    );
                    s[1][i] = mds_column_mult(
                        Q0[(Q0[(Q1[(Q1[b as usize] ^ s_vec[1]) as usize] ^ s_vec[5]) as usize]
                            ^ s_vec[9]) as usize],
                        1,
                    );
                    s[2][i] = mds_column_mult(
                        Q1[(Q1[(Q0[(Q0[b as usize] ^ s_vec[2]) as usize] ^ s_vec[6]) as usize]
                            ^ s_vec[10]) as usize],
                        2,
                    );
                    s[3][i] = mds_column_mult(
                        Q0[(Q1[(Q1[(Q0[b as usize] ^ s_vec[3]) as usize] ^ s_vec[7]) as usize]
                            ^ s_vec[11]) as usize],
                        3,
                    );
                }
            }
            _ => {
                // k_words == 4
                for i in 0..256usize {
                    let b = i as u8;
                    s[0][i] = mds_column_mult(
                        Q1[(Q0[(Q0[(Q1[(Q1[b as usize] ^ s_vec[0]) as usize] ^ s_vec[4]) as usize]
                            ^ s_vec[8]) as usize]
                            ^ s_vec[12]) as usize],
                        0,
                    );
                    s[1][i] = mds_column_mult(
                        Q0[(Q0[(Q1[(Q1[(Q0[b as usize] ^ s_vec[1]) as usize] ^ s_vec[5]) as usize]
                            ^ s_vec[9]) as usize]
                            ^ s_vec[13]) as usize],
                        1,
                    );
                    s[2][i] = mds_column_mult(
                        Q1[(Q1[(Q0[(Q0[(Q0[b as usize] ^ s_vec[2]) as usize] ^ s_vec[6]) as usize]
                            ^ s_vec[10]) as usize]
                            ^ s_vec[14]) as usize],
                        2,
                    );
                    s[3][i] = mds_column_mult(
                        Q0[(Q1[(Q1[(Q0[(Q1[b as usize] ^ s_vec[3]) as usize] ^ s_vec[7]) as usize]
                            ^ s_vec[11]) as usize]
                            ^ s_vec[15]) as usize],
                        3,
                    );
                }
            }
        }

        Ok(Self { k: k_sched, s })
    }

    /// `g` function: combine the four key-dependent S-box columns into
    /// a 32-bit word (already includes MDS).
    #[inline]
    fn g(&self, x: u32) -> u32 {
        self.s[0][(x & 0xFF) as usize]
            ^ self.s[1][((x >> 8) & 0xFF) as usize]
            ^ self.s[2][((x >> 16) & 0xFF) as usize]
            ^ self.s[3][((x >> 24) & 0xFF) as usize]
    }

    /// Encrypt a single 128-bit block in place.
    pub fn encrypt_block(&self, block: &mut [u8; 16]) {
        let mut a = u32::from_le_bytes(block[0..4].try_into().unwrap()) ^ self.k[0];
        let mut b = u32::from_le_bytes(block[4..8].try_into().unwrap()) ^ self.k[1];
        let mut c = u32::from_le_bytes(block[8..12].try_into().unwrap()) ^ self.k[2];
        let mut d = u32::from_le_bytes(block[12..16].try_into().unwrap()) ^ self.k[3];

        // 16 rounds, unrolled two at a time (matches the reference and
        // avoids redundant swaps).
        for i in 0..8 {
            let k = &self.k[8 + 4 * i..12 + 4 * i];
            let t2 = self.g(b.rotate_left(8));
            let t1 = self.g(a).wrapping_add(t2);
            c = (c ^ t1.wrapping_add(k[0])).rotate_right(1);
            d = d.rotate_left(1) ^ t2.wrapping_add(t1).wrapping_add(k[1]);

            let t2 = self.g(d.rotate_left(8));
            let t1 = self.g(c).wrapping_add(t2);
            a = (a ^ t1.wrapping_add(k[2])).rotate_right(1);
            b = b.rotate_left(1) ^ t2.wrapping_add(t1).wrapping_add(k[3]);
        }

        // Output whitening, with the "undo last swap" baked in:
        // pairs (c, d) and (a, b) trade places at output.
        let ta = c ^ self.k[4];
        let tb = d ^ self.k[5];
        let tc = a ^ self.k[6];
        let td = b ^ self.k[7];
        block[0..4].copy_from_slice(&ta.to_le_bytes());
        block[4..8].copy_from_slice(&tb.to_le_bytes());
        block[8..12].copy_from_slice(&tc.to_le_bytes());
        block[12..16].copy_from_slice(&td.to_le_bytes());
    }

    /// Decrypt a single 128-bit block in place.
    pub fn decrypt_block(&self, block: &mut [u8; 16]) {
        // Reverse output whitening.  Note the half-pair swap is undone
        // by re-binding (ta, tb) → (c, d) and (tc, td) → (a, b).
        let ta = u32::from_le_bytes(block[0..4].try_into().unwrap()) ^ self.k[4];
        let tb = u32::from_le_bytes(block[4..8].try_into().unwrap()) ^ self.k[5];
        let tc = u32::from_le_bytes(block[8..12].try_into().unwrap()) ^ self.k[6];
        let td = u32::from_le_bytes(block[12..16].try_into().unwrap()) ^ self.k[7];

        let mut a = tc;
        let mut b = td;
        let mut c = ta;
        let mut d = tb;

        for i in (0..8).rev() {
            let k = &self.k[8 + 4 * i..12 + 4 * i];
            // Undo the second half-round (operates on (c, d) → (a, b)).
            let t2 = self.g(d.rotate_left(8));
            let t1 = self.g(c).wrapping_add(t2);
            a = a.rotate_left(1) ^ t1.wrapping_add(k[2]);
            b = (b ^ t2.wrapping_add(t1).wrapping_add(k[3])).rotate_right(1);

            // Undo the first half-round.
            let t2 = self.g(b.rotate_left(8));
            let t1 = self.g(a).wrapping_add(t2);
            c = c.rotate_left(1) ^ t1.wrapping_add(k[0]);
            d = (d ^ t2.wrapping_add(t1).wrapping_add(k[1])).rotate_right(1);
        }

        // Reverse input whitening.
        let m0 = a ^ self.k[0];
        let m1 = b ^ self.k[1];
        let m2 = c ^ self.k[2];
        let m3 = d ^ self.k[3];
        block[0..4].copy_from_slice(&m0.to_le_bytes());
        block[4..8].copy_from_slice(&m1.to_le_bytes());
        block[8..12].copy_from_slice(&m2.to_le_bytes());
        block[12..16].copy_from_slice(&m3.to_le_bytes());
    }
}

// ── Tests ─────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// **Twofish paper test vector** (Appendix B.1): zero key, zero plaintext.
    ///   Key    = 00000000000000000000000000000000
    ///   Plain  = 00000000000000000000000000000000
    ///   Cipher = 9F589F5CF6122C32B6BFEC2F2AE8C35A
    #[test]
    fn twofish128_zero_vector() {
        let cipher = Twofish::new(&[0u8; 16]).unwrap();
        let mut block = [0u8; 16];
        cipher.encrypt_block(&mut block);
        let expected: [u8; 16] = [
            0x9F, 0x58, 0x9F, 0x5C, 0xF6, 0x12, 0x2C, 0x32, 0xB6, 0xBF, 0xEC, 0x2F, 0x2A, 0xE8,
            0xC3, 0x5A,
        ];
        assert_eq!(block, expected);
    }

    /// Zero key / zero plaintext for Twofish-192.  Verified against the
    /// reference `twofish` Python package (PyPI).
    #[test]
    fn twofish192_zero_vector() {
        let cipher = Twofish::new(&[0u8; 24]).unwrap();
        let mut block = [0u8; 16];
        cipher.encrypt_block(&mut block);
        let expected: [u8; 16] = [
            0xEF, 0xA7, 0x1F, 0x78, 0x89, 0x65, 0xBD, 0x44, 0x53, 0xF8, 0x60, 0x17, 0x8F, 0xC1,
            0x91, 0x01,
        ];
        assert_eq!(block, expected);
    }

    /// Zero key / zero plaintext for Twofish-256.  Verified against the
    /// reference `twofish` Python package (PyPI).
    #[test]
    fn twofish256_zero_vector() {
        let cipher = Twofish::new(&[0u8; 32]).unwrap();
        let mut block = [0u8; 16];
        cipher.encrypt_block(&mut block);
        let expected: [u8; 16] = [
            0x57, 0xFF, 0x73, 0x9D, 0x4D, 0xC9, 0x2C, 0x1B, 0xD7, 0xFC, 0x01, 0x70, 0x0C, 0xC8,
            0x21, 0x6F,
        ];
        assert_eq!(block, expected);
    }

    /// Non-zero key/plaintext for Twofish-128.  Reference output from
    /// the `twofish` PyPI package.
    #[test]
    fn twofish128_nonzero_vector() {
        let key: [u8; 16] = [
            0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF, 0xFE, 0xDC, 0xBA, 0x98, 0x76, 0x54,
            0x32, 0x10,
        ];
        let plain: [u8; 16] = [
            0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0xAA, 0xBB, 0xCC, 0xDD,
            0xEE, 0xFF,
        ];
        let expected: [u8; 16] = [
            0x56, 0x81, 0x24, 0x26, 0x1C, 0x41, 0x64, 0xDC, 0xB4, 0xDC, 0xBE, 0xEB, 0x44, 0x0C,
            0xF1, 0x9B,
        ];
        let cipher = Twofish::new(&key).unwrap();
        let mut block = plain;
        cipher.encrypt_block(&mut block);
        assert_eq!(block, expected);
        cipher.decrypt_block(&mut block);
        assert_eq!(block, plain);
    }

    /// Non-zero key/plaintext for Twofish-192.
    #[test]
    fn twofish192_nonzero_vector() {
        let key: [u8; 24] = [
            0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF, 0xFE, 0xDC, 0xBA, 0x98, 0x76, 0x54,
            0x32, 0x10, 0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77,
        ];
        let plain: [u8; 16] = [
            0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0xAA, 0xBB, 0xCC, 0xDD,
            0xEE, 0xFF,
        ];
        let expected: [u8; 16] = [
            0x18, 0xF0, 0xB8, 0xE9, 0xC1, 0xE0, 0x0D, 0xF8, 0xA8, 0x29, 0xA3, 0x69, 0x6A, 0xAA,
            0x90, 0x12,
        ];
        let cipher = Twofish::new(&key).unwrap();
        let mut block = plain;
        cipher.encrypt_block(&mut block);
        assert_eq!(block, expected);
        cipher.decrypt_block(&mut block);
        assert_eq!(block, plain);
    }

    /// Non-zero key/plaintext for Twofish-256.
    #[test]
    fn twofish256_nonzero_vector() {
        let key: [u8; 32] = [
            0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF, 0xFE, 0xDC, 0xBA, 0x98, 0x76, 0x54,
            0x32, 0x10, 0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0xAA, 0xBB,
            0xCC, 0xDD, 0xEE, 0xFF,
        ];
        let plain: [u8; 16] = [
            0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0xAA, 0xBB, 0xCC, 0xDD,
            0xEE, 0xFF,
        ];
        let expected: [u8; 16] = [
            0x7C, 0x9C, 0xDE, 0x6D, 0x86, 0xB1, 0xD9, 0xF2, 0x9F, 0xCE, 0xB6, 0x83, 0x0C, 0x45,
            0x12, 0x81,
        ];
        let cipher = Twofish::new(&key).unwrap();
        let mut block = plain;
        cipher.encrypt_block(&mut block);
        assert_eq!(block, expected);
        cipher.decrypt_block(&mut block);
        assert_eq!(block, plain);
    }

    /// Reject malformed key lengths.
    #[test]
    fn twofish_bad_key_lengths() {
        assert!(Twofish::new(&[0u8; 0]).is_err());
        assert!(Twofish::new(&[0u8; 15]).is_err());
        assert!(Twofish::new(&[0u8; 20]).is_err());
        assert!(Twofish::new(&[0u8; 33]).is_err());
    }

    /// Round-trip random data for each key size.
    #[test]
    fn twofish_round_trip() {
        for &keylen in &[16usize, 24, 32] {
            let key: Vec<u8> = (0..keylen as u8)
                .map(|b| b.wrapping_mul(7).wrapping_add(3))
                .collect();
            let cipher = Twofish::new(&key).unwrap();
            let mut block = [0u8; 16];
            for (i, b) in block.iter_mut().enumerate() {
                *b = (i as u8).wrapping_mul(11).wrapping_add(13);
            }
            let orig = block;
            cipher.encrypt_block(&mut block);
            assert_ne!(
                block, orig,
                "ciphertext equals plaintext for keylen={}",
                keylen
            );
            cipher.decrypt_block(&mut block);
            assert_eq!(block, orig, "round-trip mismatch for keylen={}", keylen);
        }
    }
}
