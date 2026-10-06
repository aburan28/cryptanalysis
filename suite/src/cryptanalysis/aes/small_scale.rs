//! Small-scale AES (Cid, Murphy, Robshaw — FSE 2005).
//!
//! `SR(n, r, c, e)`: a family of AES-like ciphers parameterised by
//!
//! - `n` — number of rounds,
//! - `r` — number of rows in the state (1, 2, or 4),
//! - `c` — number of columns (1, 2, or 4),
//! - `e` — cell size in bits (4 or 8).
//!
//! `SR(n, 4, 4, 8)` is the standard AES. The interesting downscaled
//! variant for **runnable algebraic cryptanalysis** is
//! `SR(n, 2, 2, 4)`: a 2×2 state of 4-bit cells (16-bit total block),
//! arithmetic in GF(2⁴) with polynomial `x⁴ + x + 1`. The cipher has
//! the same round structure as AES — SubBytes / ShiftRows /
//! MixColumns / AddRoundKey — but a 16-bit state lets exhaustive
//! analysis and polynomial-system tools run in seconds.
//!
//! This module implements `SR(n, 2, 2, 4)` from scratch.
//!
//! ## The 4-bit S-box
//!
//! We use the GF(2⁴) multiplicative inverse (with `0` mapped to `0`)
//! followed by an affine transformation, matching the AES S-box
//! construction pattern at 4-bit scale. The resulting S-box is
//! cryptographically reasonable (differential uniformity 4, max
//! linear bias 4/16 = 1/4) but **not** the same as the AES 8-bit S-box.
//!
//! ## ShiftRows, MixColumns, key schedule
//!
//! - **ShiftRows** on a 2×2 state: row 0 unchanged; row 1 cyclically
//!   shifted left by 1 (i.e. its two cells swap).
//! - **MixColumns** uses the matrix `[[1+x, x], [x, 1+x]]` over
//!   GF(2⁴) — branch number 3 (vs 5 in full AES, since the matrix is
//!   2×2 not 4×4).
//! - **Key schedule** mirrors AES at 4-bit scale: RotWord rotates the
//!   2-cell word, SubWord applies the 4-bit S-box, and the round
//!   constant cycles through `0x1, 0x2, 0x4, 0x8, 0x3, …` (multiplying
//!   by `x` in GF(2⁴) each round).
//!
//! ## Why this is useful
//!
//! Algebraic attacks (Gröbner basis, linearisation, SAT) express the
//! cipher as a polynomial system over GF(2⁴) and attempt to solve
//! the system from a few known plaintext-ciphertext pairs. The
//! systems for full AES have ≈ 8000 variables and equations — far
//! beyond any current solver. For SR(n, 2, 2, 4) with `n = 4` the
//! system has ≈ 100 variables — well within tractable range.

const POLY: u8 = 0b10011; // x⁴ + x + 1 = 0b1_0011, but mod x⁴ uses 0b0011 below

/// Multiply two GF(2⁴) elements (lower 4 bits each).
pub fn gf16_mul(mut a: u8, mut b: u8) -> u8 {
    let mut p = 0u8;
    for _ in 0..4 {
        if b & 1 != 0 {
            p ^= a;
        }
        let hi = a & 0x08 != 0;
        a = (a << 1) & 0x0f;
        if hi {
            a ^= POLY & 0x0f; // = 0011 = x + 1
        }
        b >>= 1;
    }
    p & 0x0f
}

/// Multiplicative inverse in GF(2⁴) by Fermat: `a^14 = a⁻¹`.
pub fn gf16_inv(a: u8) -> u8 {
    if a == 0 {
        return 0;
    }
    let mut result = 1u8;
    let mut base = a;
    let mut exp = 14u8;
    while exp > 0 {
        if exp & 1 == 1 {
            result = gf16_mul(result, base);
        }
        base = gf16_mul(base, base);
        exp >>= 1;
    }
    result
}

/// 4-bit S-box: `S(x) = A · x⁻¹ + b` for an AES-style affine map over
/// GF(2)⁴.
///
/// The affine matrix `A` here is a `4×4` matrix over GF(2) with each
/// row `(1, 1, 1, 0)` cyclically shifted; the additive constant `b`
/// is `0x6`. Pre-computed at module load.
pub const SBOX4: [u8; 16] = compute_sbox4();

const fn compute_sbox4() -> [u8; 16] {
    // Hand-rolled const-fn version of S-box generation. We bake in
    // the inverse table to avoid making `gf16_inv` const.
    //
    // GF(2⁴) inverses with poly x⁴+x+1:
    //   inv[0] = 0
    //   inv[1] = 1
    //   inv[2] = 9
    //   inv[3] = e
    //   inv[4] = d
    //   inv[5] = b
    //   inv[6] = 7
    //   inv[7] = 6
    //   inv[8] = f
    //   inv[9] = 2
    //   inv[a] = c
    //   inv[b] = 5
    //   inv[c] = a
    //   inv[d] = 4
    //   inv[e] = 3
    //   inv[f] = 8
    let inv: [u8; 16] = [0, 1, 9, 0xe, 0xd, 0xb, 7, 6, 0xf, 2, 0xc, 5, 0xa, 4, 3, 8];
    // Affine: row 0 = 1110, row 1 = 0111, row 2 = 1011, row 3 = 1101 (rotations).
    // b = 0b0110 = 6.
    let mut sbox = [0u8; 16];
    let mut i: usize = 0;
    while i < 16 {
        let x = inv[i];
        // Compute A · x in GF(2):
        let b0 = (x ^ (x >> 1) ^ (x >> 2)) & 1;
        let b1 = ((x >> 1) ^ (x >> 2) ^ (x >> 3)) & 1;
        let b2 = (x ^ (x >> 2) ^ (x >> 3)) & 1;
        let b3 = (x ^ (x >> 1) ^ (x >> 3)) & 1;
        let ax = b0 | (b1 << 1) | (b2 << 2) | (b3 << 3);
        sbox[i] = ax ^ 0x6;
        i += 1;
    }
    sbox
}

/// Inverse 4-bit S-box.
pub const INV_SBOX4: [u8; 16] = {
    let mut inv = [0u8; 16];
    let mut i = 0usize;
    while i < 16 {
        inv[SBOX4[i] as usize] = i as u8;
        i += 1;
    }
    inv
};

/// SR(n, 2, 2, 4): the 2×2 4-bit-cell AES variant.
#[derive(Clone)]
pub struct SmallAes {
    pub nr: usize,
    /// Round keys: 4 cells (16 bits) per round, `n + 1` total.
    pub round_keys: Vec<[u8; 4]>,
}

impl SmallAes {
    pub fn new(key: [u8; 4], nr: usize) -> Self {
        // Key schedule: similar to AES, but at 4-bit scale.
        // RCON: 1, 2, 4, 8, 3, 6, 12, 11, ... = x^(i) in GF(2⁴).
        let mut rcon = [0u8; 16];
        rcon[1] = 1;
        for i in 2..16 {
            rcon[i] = gf16_mul(rcon[i - 1], 2);
        }
        let total = nr + 1;
        let mut rk: Vec<[u8; 4]> = Vec::with_capacity(total);
        rk.push(key);
        for r in 1..total {
            let prev = rk[r - 1];
            // RotWord on column 1 (last column): swap the two cells.
            // Treating each round-key as [col0_r0, col0_r1, col1_r0, col1_r1].
            // Take the "last column" = [prev[2], prev[3]].
            // RotWord: swap rows ⇒ [prev[3], prev[2]].
            // SubWord: apply S-box: [S(prev[3]), S(prev[2])].
            let mut t = [SBOX4[prev[3] as usize], SBOX4[prev[2] as usize]];
            // Add RCON to first cell.
            t[0] ^= rcon[r];
            // New column 0 = prev column 0 ⊕ t
            let new_c0 = [prev[0] ^ t[0], prev[1] ^ t[1]];
            // New column 1 = prev column 1 ⊕ new column 0
            let new_c1 = [prev[2] ^ new_c0[0], prev[3] ^ new_c0[1]];
            rk.push([new_c0[0], new_c0[1], new_c1[0], new_c1[1]]);
        }
        SmallAes { nr, round_keys: rk }
    }

    fn add_round_key(state: &mut [u8; 4], rk: &[u8; 4]) {
        for i in 0..4 {
            state[i] ^= rk[i];
        }
    }
    fn sub_bytes(state: &mut [u8; 4]) {
        for s in state.iter_mut() {
            *s = SBOX4[*s as usize];
        }
    }
    fn inv_sub_bytes(state: &mut [u8; 4]) {
        for s in state.iter_mut() {
            *s = INV_SBOX4[*s as usize];
        }
    }
    fn shift_rows(state: &mut [u8; 4]) {
        // State = [col0_r0, col0_r1, col1_r0, col1_r1].
        // Row 0 unchanged. Row 1: swap cells.
        state.swap(1, 3);
    }
    fn inv_shift_rows(state: &mut [u8; 4]) {
        // Self-inverse for 2-column case.
        Self::shift_rows(state);
    }
    fn mix_columns(state: &mut [u8; 4]) {
        // Matrix [[1+x, x], [x, 1+x]] = [[3, 2], [2, 3]] in GF(2⁴) hex.
        for col in 0..2 {
            let a = state[2 * col];
            let b = state[2 * col + 1];
            state[2 * col] = gf16_mul(3, a) ^ gf16_mul(2, b);
            state[2 * col + 1] = gf16_mul(2, a) ^ gf16_mul(3, b);
        }
    }
    fn inv_mix_columns(state: &mut [u8; 4]) {
        // Inverse of [[3, 2], [2, 3]] over GF(2⁴).
        // det = 3*3 - 2*2 = 9 - 4 = 9 ⊕ 4 = 13 in GF(2⁴) wait additive
        // det in GF(2⁴) = 3·3 ⊕ 2·2 = 5 ⊕ 4 = 1. So inverse =
        // [[3, 2], [2, 3]] / 1 — which means the matrix is self-inverse.
        Self::mix_columns(state);
    }

    pub fn encrypt(&self, pt: [u8; 4]) -> [u8; 4] {
        let mut s = pt;
        Self::add_round_key(&mut s, &self.round_keys[0]);
        for r in 1..self.nr {
            Self::sub_bytes(&mut s);
            Self::shift_rows(&mut s);
            Self::mix_columns(&mut s);
            Self::add_round_key(&mut s, &self.round_keys[r]);
        }
        Self::sub_bytes(&mut s);
        Self::shift_rows(&mut s);
        Self::add_round_key(&mut s, &self.round_keys[self.nr]);
        s
    }

    pub fn decrypt(&self, ct: [u8; 4]) -> [u8; 4] {
        let mut s = ct;
        Self::add_round_key(&mut s, &self.round_keys[self.nr]);
        Self::inv_shift_rows(&mut s);
        Self::inv_sub_bytes(&mut s);
        for r in (1..self.nr).rev() {
            Self::add_round_key(&mut s, &self.round_keys[r]);
            Self::inv_mix_columns(&mut s);
            Self::inv_shift_rows(&mut s);
            Self::inv_sub_bytes(&mut s);
        }
        Self::add_round_key(&mut s, &self.round_keys[0]);
        s
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn gf16_inv_round_trips() {
        for a in 1u8..16 {
            assert_eq!(gf16_mul(a, gf16_inv(a)), 1);
        }
    }

    #[test]
    fn sbox4_is_bijective() {
        let mut seen = [false; 16];
        for &v in &SBOX4 {
            assert!(!seen[v as usize], "S-box value {v} appears twice");
            seen[v as usize] = true;
        }
    }

    #[test]
    fn small_aes_round_trips() {
        for &nr in &[1usize, 2, 3, 4, 5, 10] {
            let key = [0xa, 0x5, 0x3, 0xc];
            let cipher = SmallAes::new(key, nr);
            for p in 0u16..256 {
                let pt = [
                    (p & 0xf) as u8,
                    ((p >> 4) & 0xf) as u8,
                    ((p >> 8) & 0xf) as u8,
                    ((p >> 12) & 0xf) as u8,
                ];
                let ct = cipher.encrypt(pt);
                assert_eq!(cipher.decrypt(ct), pt, "round trip failed at nr={nr}");
            }
        }
    }

    /// Brute-force key recovery on `SR(4, 2, 2, 4)`: with 2 known
    /// plaintext-ciphertext pairs, the 16-bit key space is searchable
    /// in milliseconds — confirming that small-scale AES is in fact
    /// useable as an analysis target.
    #[test]
    fn brute_force_key_recovery_works() {
        let key = [0x1, 0xd, 0x4, 0xb];
        let cipher = SmallAes::new(key, 4);
        let pt1 = [0xa, 0x5, 0x3, 0xc];
        let pt2 = [0x0, 0xf, 0x7, 0x1];
        let ct1 = cipher.encrypt(pt1);
        let ct2 = cipher.encrypt(pt2);
        let mut recovered = None;
        for k in 0u32..(1 << 16) {
            let candidate_key = [
                (k & 0xf) as u8,
                ((k >> 4) & 0xf) as u8,
                ((k >> 8) & 0xf) as u8,
                ((k >> 12) & 0xf) as u8,
            ];
            let candidate_cipher = SmallAes::new(candidate_key, 4);
            if candidate_cipher.encrypt(pt1) == ct1 && candidate_cipher.encrypt(pt2) == ct2 {
                recovered = Some(candidate_key);
                break;
            }
        }
        assert_eq!(recovered, Some(key));
    }
}
