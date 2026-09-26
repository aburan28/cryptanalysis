//! **DES — Data Encryption Standard** (FIPS PUB 46, 1977).
//!
//! 64-bit block, 56-bit effective key (8 bytes; the high bit of each
//! key byte is a parity check that DES ignores), 16-round Feistel
//! network.  Designed by IBM and the NSA, standardised by NIST,
//! **broken** since EFF's 1998 Deep Crack hardware (full key
//! recovery in < 56 hours).
//!
//! Shipping it here for:
//!
//! - Studying the Feistel structure and S-box design.
//! - Acting as the building block for **3DES** (`des3.rs`), which is
//!   still in legacy use (banking, PKCS#12).
//!
//! ## Algorithm
//!
//! 1. **Initial Permutation (IP)** of the 64-bit input.
//! 2. Split into `L_0 || R_0` (32 bits each).
//! 3. For 16 rounds: `L_{i+1} = R_i`, `R_{i+1} = L_i ⊕ f(R_i, K_i)`.
//! 4. **Final Permutation (IP⁻¹)** of `R_{16} || L_{16}` (note the
//!    swap — the "swap-back" at the end of the last round is omitted
//!    in DES, so we feed (R, L) into IP⁻¹).
//!
//! `f(R, K)` = `P(S-box(E(R) ⊕ K))` where:
//! - `E` expands 32 → 48 bits.
//! - The XOR with the 48-bit round key feeds 6-bit groups into
//!   8 different S-boxes, each producing 4 bits (48 → 32).
//! - `P` permutes the 32-bit output.
//!
//! ## References
//!
//! - **FIPS PUB 46-3** (latest DES spec, withdrawn in 2005).
//! - **Stinson**, *Cryptography: Theory and Practice*, §3.6.
//! - **B. Schneier**, *Applied Cryptography*, 2nd ed., §12.

// ── Tables (FIPS PUB 46-3 Appendix) ──────────────────────────────────

/// Initial permutation: bit `i` of the output gets bit `IP[i]` of the
/// input.  1-indexed in FIPS, 0-indexed here (subtract 1).
const IP: [u8; 64] = [
    58, 50, 42, 34, 26, 18, 10, 2, 60, 52, 44, 36, 28, 20, 12, 4, 62, 54, 46, 38, 30, 22, 14, 6,
    64, 56, 48, 40, 32, 24, 16, 8, 57, 49, 41, 33, 25, 17, 9, 1, 59, 51, 43, 35, 27, 19, 11, 3, 61,
    53, 45, 37, 29, 21, 13, 5, 63, 55, 47, 39, 31, 23, 15, 7,
];

/// Final permutation = inverse of `IP`.
const IP_INV: [u8; 64] = [
    40, 8, 48, 16, 56, 24, 64, 32, 39, 7, 47, 15, 55, 23, 63, 31, 38, 6, 46, 14, 54, 22, 62, 30,
    37, 5, 45, 13, 53, 21, 61, 29, 36, 4, 44, 12, 52, 20, 60, 28, 35, 3, 43, 11, 51, 19, 59, 27,
    34, 2, 42, 10, 50, 18, 58, 26, 33, 1, 41, 9, 49, 17, 57, 25,
];

/// Expansion E: 32 → 48 bits.
const E: [u8; 48] = [
    32, 1, 2, 3, 4, 5, 4, 5, 6, 7, 8, 9, 8, 9, 10, 11, 12, 13, 12, 13, 14, 15, 16, 17, 16, 17, 18,
    19, 20, 21, 20, 21, 22, 23, 24, 25, 24, 25, 26, 27, 28, 29, 28, 29, 30, 31, 32, 1,
];

/// Permutation P: 32-bit permutation applied after the S-boxes.
const P: [u8; 32] = [
    16, 7, 20, 21, 29, 12, 28, 17, 1, 15, 23, 26, 5, 18, 31, 10, 2, 8, 24, 14, 32, 27, 3, 9, 19,
    13, 30, 6, 22, 11, 4, 25,
];

/// Permuted Choice 1: 64 → 56 bits (drops 8 parity bits, permutes).
const PC1: [u8; 56] = [
    57, 49, 41, 33, 25, 17, 9, 1, 58, 50, 42, 34, 26, 18, 10, 2, 59, 51, 43, 35, 27, 19, 11, 3, 60,
    52, 44, 36, 63, 55, 47, 39, 31, 23, 15, 7, 62, 54, 46, 38, 30, 22, 14, 6, 61, 53, 45, 37, 29,
    21, 13, 5, 28, 20, 12, 4,
];

/// Permuted Choice 2: 56 → 48 bits.  Selects 48 bits of the CD
/// register to form the round key.
const PC2: [u8; 48] = [
    14, 17, 11, 24, 1, 5, 3, 28, 15, 6, 21, 10, 23, 19, 12, 4, 26, 8, 16, 7, 27, 20, 13, 2, 41, 52,
    31, 37, 47, 55, 30, 40, 51, 45, 33, 48, 44, 49, 39, 56, 34, 53, 46, 42, 50, 36, 29, 32,
];

/// Per-round left-rotation amount for the CD halves.
const SHIFTS: [u8; 16] = [1, 1, 2, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 1];

/// The 8 DES S-boxes.  Each maps a 6-bit input `b1 b2 b3 b4 b5 b6` to
/// 4 bits via `SBOX[i][row][col]` where `row = (b1 << 1) | b6` and
/// `col = (b2 << 3) | (b3 << 2) | (b4 << 1) | b5`.
#[rustfmt::skip]
const SBOX: [[[u8; 16]; 4]; 8] = [
    // S1
    [[14, 4, 13, 1, 2, 15, 11, 8, 3, 10, 6, 12, 5, 9, 0, 7],
     [0, 15, 7, 4, 14, 2, 13, 1, 10, 6, 12, 11, 9, 5, 3, 8],
     [4, 1, 14, 8, 13, 6, 2, 11, 15, 12, 9, 7, 3, 10, 5, 0],
     [15, 12, 8, 2, 4, 9, 1, 7, 5, 11, 3, 14, 10, 0, 6, 13]],
    // S2
    [[15, 1, 8, 14, 6, 11, 3, 4, 9, 7, 2, 13, 12, 0, 5, 10],
     [3, 13, 4, 7, 15, 2, 8, 14, 12, 0, 1, 10, 6, 9, 11, 5],
     [0, 14, 7, 11, 10, 4, 13, 1, 5, 8, 12, 6, 9, 3, 2, 15],
     [13, 8, 10, 1, 3, 15, 4, 2, 11, 6, 7, 12, 0, 5, 14, 9]],
    // S3
    [[10, 0, 9, 14, 6, 3, 15, 5, 1, 13, 12, 7, 11, 4, 2, 8],
     [13, 7, 0, 9, 3, 4, 6, 10, 2, 8, 5, 14, 12, 11, 15, 1],
     [13, 6, 4, 9, 8, 15, 3, 0, 11, 1, 2, 12, 5, 10, 14, 7],
     [1, 10, 13, 0, 6, 9, 8, 7, 4, 15, 14, 3, 11, 5, 2, 12]],
    // S4
    [[7, 13, 14, 3, 0, 6, 9, 10, 1, 2, 8, 5, 11, 12, 4, 15],
     [13, 8, 11, 5, 6, 15, 0, 3, 4, 7, 2, 12, 1, 10, 14, 9],
     [10, 6, 9, 0, 12, 11, 7, 13, 15, 1, 3, 14, 5, 2, 8, 4],
     [3, 15, 0, 6, 10, 1, 13, 8, 9, 4, 5, 11, 12, 7, 2, 14]],
    // S5
    [[2, 12, 4, 1, 7, 10, 11, 6, 8, 5, 3, 15, 13, 0, 14, 9],
     [14, 11, 2, 12, 4, 7, 13, 1, 5, 0, 15, 10, 3, 9, 8, 6],
     [4, 2, 1, 11, 10, 13, 7, 8, 15, 9, 12, 5, 6, 3, 0, 14],
     [11, 8, 12, 7, 1, 14, 2, 13, 6, 15, 0, 9, 10, 4, 5, 3]],
    // S6
    [[12, 1, 10, 15, 9, 2, 6, 8, 0, 13, 3, 4, 14, 7, 5, 11],
     [10, 15, 4, 2, 7, 12, 9, 5, 6, 1, 13, 14, 0, 11, 3, 8],
     [9, 14, 15, 5, 2, 8, 12, 3, 7, 0, 4, 10, 1, 13, 11, 6],
     [4, 3, 2, 12, 9, 5, 15, 10, 11, 14, 1, 7, 6, 0, 8, 13]],
    // S7
    [[4, 11, 2, 14, 15, 0, 8, 13, 3, 12, 9, 7, 5, 10, 6, 1],
     [13, 0, 11, 7, 4, 9, 1, 10, 14, 3, 5, 12, 2, 15, 8, 6],
     [1, 4, 11, 13, 12, 3, 7, 14, 10, 15, 6, 8, 0, 5, 9, 2],
     [6, 11, 13, 8, 1, 4, 10, 7, 9, 5, 0, 15, 14, 2, 3, 12]],
    // S8
    [[13, 2, 8, 4, 6, 15, 11, 1, 10, 9, 3, 14, 5, 0, 12, 7],
     [1, 15, 13, 8, 10, 3, 7, 4, 12, 5, 6, 11, 0, 14, 9, 2],
     [7, 11, 4, 1, 9, 12, 14, 2, 0, 6, 10, 13, 15, 3, 5, 8],
     [2, 1, 14, 7, 4, 10, 8, 13, 15, 12, 9, 0, 3, 5, 6, 11]],
];

// ── Bit-permutation helper ───────────────────────────────────────────

/// Apply a 1-indexed permutation table to a bit-string of length
/// `input_bits`.  Returns the permuted bit-string of length
/// `table.len()`.  Bits are MSB-first.
fn permute(input: u64, input_bits: u8, table: &[u8]) -> u64 {
    let mut out: u64 = 0;
    for (i, &src) in table.iter().enumerate() {
        let bit = (input >> (input_bits - src)) & 1;
        out |= bit << (table.len() - 1 - i);
    }
    out
}

fn block_to_u64(block: &[u8; 8]) -> u64 {
    let mut v: u64 = 0;
    for i in 0..8 {
        v = (v << 8) | (block[i] as u64);
    }
    v
}

fn u64_to_block(v: u64) -> [u8; 8] {
    let mut out = [0u8; 8];
    for i in 0..8 {
        out[i] = ((v >> (56 - 8 * i)) & 0xFF) as u8;
    }
    out
}

// ── Key schedule ─────────────────────────────────────────────────────

/// Expand the 64-bit DES key into 16 × 48-bit round keys.
pub fn key_schedule(key: &[u8; 8]) -> [u64; 16] {
    let key_u64 = block_to_u64(key);
    let cd = permute(key_u64, 64, &PC1); // 56 bits
    let mut c: u64 = (cd >> 28) & 0x0FFF_FFFF;
    let mut d: u64 = cd & 0x0FFF_FFFF;
    let mut round_keys = [0u64; 16];
    for r in 0..16 {
        let shift = SHIFTS[r];
        c = ((c << shift) | (c >> (28 - shift))) & 0x0FFF_FFFF;
        d = ((d << shift) | (d >> (28 - shift))) & 0x0FFF_FFFF;
        let cd_r = (c << 28) | d; // 56 bits
        round_keys[r] = permute(cd_r, 56, &PC2);
    }
    round_keys
}

// ── Feistel f function ───────────────────────────────────────────────

/// `f(R, K)` — the DES round function.  `R` is 32 bits, `K` is 48
/// bits; returns 32 bits.
fn feistel_f(r: u32, k: u64) -> u32 {
    let er = permute(r as u64, 32, &E); // 48 bits
    let x = er ^ k;
    let mut out: u32 = 0;
    for i in 0..8 {
        let six = ((x >> (42 - 6 * i)) & 0x3F) as u8;
        let row = ((six & 0b100000) >> 4) | (six & 1);
        let col = (six >> 1) & 0x0F;
        let s = SBOX[i][row as usize][col as usize] as u32;
        out |= s << (28 - 4 * i);
    }
    permute(out as u64, 32, &P) as u32
}

// ── Encryption / decryption ──────────────────────────────────────────

/// Encrypt one 64-bit block.
pub fn encrypt_block(key: &[u8; 8], block: &[u8; 8]) -> [u8; 8] {
    let rks = key_schedule(key);
    let mut x = permute(block_to_u64(block), 64, &IP);
    let mut l = (x >> 32) as u32;
    let mut r = (x & 0xFFFF_FFFF) as u32;
    for i in 0..16 {
        let new_r = l ^ feistel_f(r, rks[i]);
        l = r;
        r = new_r;
    }
    // No final swap-back: combine as (R, L) and apply IP^-1.
    x = ((r as u64) << 32) | (l as u64);
    u64_to_block(permute(x, 64, &IP_INV))
}

/// Decrypt one 64-bit block (round keys reversed).
pub fn decrypt_block(key: &[u8; 8], block: &[u8; 8]) -> [u8; 8] {
    let rks = key_schedule(key);
    let mut x = permute(block_to_u64(block), 64, &IP);
    let mut l = (x >> 32) as u32;
    let mut r = (x & 0xFFFF_FFFF) as u32;
    for i in (0..16).rev() {
        let new_r = l ^ feistel_f(r, rks[i]);
        l = r;
        r = new_r;
    }
    x = ((r as u64) << 32) | (l as u64);
    u64_to_block(permute(x, 64, &IP_INV))
}

/// A DES instance pre-loaded with the round keys.  Use when
/// encrypting many blocks under the same key — avoids re-running the
/// key schedule per call.
pub struct Des {
    pub round_keys: [u64; 16],
}

impl Des {
    pub fn new(key: &[u8; 8]) -> Self {
        Des {
            round_keys: key_schedule(key),
        }
    }
    pub fn encrypt_block(&self, block: &mut [u8; 8]) {
        let mut x = permute(block_to_u64(block), 64, &IP);
        let mut l = (x >> 32) as u32;
        let mut r = (x & 0xFFFF_FFFF) as u32;
        for i in 0..16 {
            let new_r = l ^ feistel_f(r, self.round_keys[i]);
            l = r;
            r = new_r;
        }
        x = ((r as u64) << 32) | (l as u64);
        *block = u64_to_block(permute(x, 64, &IP_INV));
    }
    pub fn decrypt_block(&self, block: &mut [u8; 8]) {
        let mut x = permute(block_to_u64(block), 64, &IP);
        let mut l = (x >> 32) as u32;
        let mut r = (x & 0xFFFF_FFFF) as u32;
        for i in (0..16).rev() {
            let new_r = l ^ feistel_f(r, self.round_keys[i]);
            l = r;
            r = new_r;
        }
        x = ((r as u64) << 32) | (l as u64);
        *block = u64_to_block(permute(x, 64, &IP_INV));
    }
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn h(s: &str) -> Vec<u8> {
        let s: String = s.chars().filter(|c| !c.is_whitespace()).collect();
        (0..s.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
            .collect()
    }

    /// **FIPS PUB 81 example** (often cited as the canonical DES test
    /// vector): Key=0123456789ABCDEF, PT=0123456789ABCDEF, CT=56CC09E7CFDC4CEF.
    #[test]
    fn des_fips81_canonical() {
        let mut k = [0u8; 8];
        k.copy_from_slice(&h("0123456789ABCDEF"));
        let mut p = [0u8; 8];
        p.copy_from_slice(&h("0123456789ABCDEF"));
        let expected = h("56CC09E7CFDC4CEF");
        let ct = encrypt_block(&k, &p);
        assert_eq!(&ct[..], &expected[..]);
        let pt = decrypt_block(&k, &ct);
        assert_eq!(&pt[..], &p[..]);
    }

    /// **NIST SP 800-17 single-block example** (also widely cited):
    /// Key = 752878397493CB70, PT = 1122334455667788, CT = B5219EE81AA7499D.
    #[test]
    fn des_nist_800_17() {
        let mut k = [0u8; 8];
        k.copy_from_slice(&h("752878397493CB70"));
        let mut p = [0u8; 8];
        p.copy_from_slice(&h("1122334455667788"));
        let expected = h("B5219EE81AA7499D");
        let ct = encrypt_block(&k, &p);
        assert_eq!(&ct[..], &expected[..]);
        let pt = decrypt_block(&k, &ct);
        assert_eq!(&pt[..], &p[..]);
    }

    /// **All-zeros key, all-zeros plaintext** (Schneier *Applied
    /// Cryptography* 2e p.270): CT = 8CA64DE9C1B123A7.
    #[test]
    fn des_all_zeros() {
        let k = [0u8; 8];
        let p = [0u8; 8];
        let expected = h("8CA64DE9C1B123A7");
        let ct = encrypt_block(&k, &p);
        assert_eq!(&ct[..], &expected[..]);
    }

    /// Encrypt/decrypt round-trip.
    #[test]
    fn des_round_trip_arbitrary() {
        let k = [0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0];
        for v in 0u64..256 {
            let p = u64_to_block(v.wrapping_mul(0x0101_0101_0101_0101));
            let ct = encrypt_block(&k, &p);
            let pt = decrypt_block(&k, &ct);
            assert_eq!(pt, p);
        }
    }

    /// `Des` struct version matches the free-function version.
    #[test]
    fn des_struct_matches_free_function() {
        let k = [0x42u8; 8];
        let p = [0xABu8; 8];
        let free_ct = encrypt_block(&k, &p);
        let des = Des::new(&k);
        let mut block = p;
        des.encrypt_block(&mut block);
        assert_eq!(block, free_ct);
        des.decrypt_block(&mut block);
        assert_eq!(block, p);
    }
}
