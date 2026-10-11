//! Reduced-round AES-128 — the target for the integral and differential
//! attacks in this subtree.
//!
//! Compared to [`crate::symmetric::aes`] (the operational implementation),
//! this module:
//!
//! - exposes the round count `Nr` (1..=10) as a parameter, so the same
//!   code can be 3-round, 4-round, or full 10-round AES;
//! - optionally retains MixColumns in the **last** round, which is
//!   convenient when an attack wants to probe a "raw" round
//!   structure without the FIPS-197 final-round special case;
//! - stores the full round-key schedule and lets attacks read individual
//!   round keys out;
//! - is *not* constant-time. The production AES uses a `subtle`-based
//!   constant-time S-box lookup; here we just index a table, because
//!   the code is for analysis, not for handling secret keys at runtime.
//!
//! The 10-round, `final_mix_columns = false` configuration is the same
//! AES-128 as `crate::symmetric::aes`; a test in this file checks that
//! against the FIPS 197 test vector.

// FIPS 197 forward S-box.
#[rustfmt::skip]
pub(crate) const SBOX: [u8; 256] = [
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
];

#[rustfmt::skip]
pub(crate) const INV_SBOX: [u8; 256] = [
    0x52,0x09,0x6a,0xd5,0x30,0x36,0xa5,0x38,0xbf,0x40,0xa3,0x9e,0x81,0xf3,0xd7,0xfb,
    0x7c,0xe3,0x39,0x82,0x9b,0x2f,0xff,0x87,0x34,0x8e,0x43,0x44,0xc4,0xde,0xe9,0xcb,
    0x54,0x7b,0x94,0x32,0xa6,0xc2,0x23,0x3d,0xee,0x4c,0x95,0x0b,0x42,0xfa,0xc3,0x4e,
    0x08,0x2e,0xa1,0x66,0x28,0xd9,0x24,0xb2,0x76,0x5b,0xa2,0x49,0x6d,0x8b,0xd1,0x25,
    0x72,0xf8,0xf6,0x64,0x86,0x68,0x98,0x16,0xd4,0xa4,0x5c,0xcc,0x5d,0x65,0xb6,0x92,
    0x6c,0x70,0x48,0x50,0xfd,0xed,0xb9,0xda,0x5e,0x15,0x46,0x57,0xa7,0x8d,0x9d,0x84,
    0x90,0xd8,0xab,0x00,0x8c,0xbc,0xd3,0x0a,0xf7,0xe4,0x58,0x05,0xb8,0xb3,0x45,0x06,
    0xd0,0x2c,0x1e,0x8f,0xca,0x3f,0x0f,0x02,0xc1,0xaf,0xbd,0x03,0x01,0x13,0x8a,0x6b,
    0x3a,0x91,0x11,0x41,0x4f,0x67,0xdc,0xea,0x97,0xf2,0xcf,0xce,0xf0,0xb4,0xe6,0x73,
    0x96,0xac,0x74,0x22,0xe7,0xad,0x35,0x85,0xe2,0xf9,0x37,0xe8,0x1c,0x75,0xdf,0x6e,
    0x47,0xf1,0x1a,0x71,0x1d,0x29,0xc5,0x89,0x6f,0xb7,0x62,0x0e,0xaa,0x18,0xbe,0x1b,
    0xfc,0x56,0x3e,0x4b,0xc6,0xd2,0x79,0x20,0x9a,0xdb,0xc0,0xfe,0x78,0xcd,0x5a,0xf4,
    0x1f,0xdd,0xa8,0x33,0x88,0x07,0xc7,0x31,0xb1,0x12,0x10,0x59,0x27,0x80,0xec,0x5f,
    0x60,0x51,0x7f,0xa9,0x19,0xb5,0x4a,0x0d,0x2d,0xe5,0x7a,0x9f,0x93,0xc9,0x9c,0xef,
    0xa0,0xe0,0x3b,0x4d,0xae,0x2a,0xf5,0xb0,0xc8,0xeb,0xbb,0x3c,0x83,0x53,0x99,0x61,
    0x17,0x2b,0x04,0x7e,0xba,0x77,0xd6,0x26,0xe1,0x69,0x14,0x63,0x55,0x21,0x0c,0x7d,
];

const RCON: [u8; 11] = [
    0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36,
];

/// Multiply two bytes as polynomials in GF(2⁸) modulo x⁸+x⁴+x³+x+1.
fn gmul(mut a: u8, mut b: u8) -> u8 {
    let mut p = 0u8;
    for _ in 0..8 {
        if b & 1 != 0 {
            p ^= a;
        }
        let hi = a & 0x80 != 0;
        a <<= 1;
        if hi {
            a ^= 0x1b;
        }
        b >>= 1;
    }
    p
}

/// AES state, indexed `[col][row]`. ShiftRows shifts within a row.
type State = [[u8; 4]; 4];

#[inline]
pub(crate) fn bytes_to_state(b: &[u8; 16]) -> State {
    let mut s = [[0u8; 4]; 4];
    for c in 0..4 {
        for r in 0..4 {
            s[c][r] = b[4 * c + r];
        }
    }
    s
}

#[inline]
pub(crate) fn state_to_bytes(s: &State) -> [u8; 16] {
    let mut b = [0u8; 16];
    for c in 0..4 {
        for r in 0..4 {
            b[4 * c + r] = s[c][r];
        }
    }
    b
}

/// Individual round operations exposed so attacks can run partial rounds.
///
/// `sub_bytes`, `shift_rows`, `mix_columns`, `add_round_key` and their
/// inverses are made available because the integral attack inverts the
/// final round step-by-step, and the differential attack peels a single
/// SubBytes off the ciphertext side.
pub struct RoundOps;

impl RoundOps {
    pub fn sub_bytes(s: &mut State) {
        for c in 0..4 {
            for r in 0..4 {
                s[c][r] = SBOX[s[c][r] as usize];
            }
        }
    }
    pub fn inv_sub_bytes(s: &mut State) {
        for c in 0..4 {
            for r in 0..4 {
                s[c][r] = INV_SBOX[s[c][r] as usize];
            }
        }
    }
    pub fn shift_rows(s: &mut State) {
        // Row r shifts left by r positions.
        let r1 = [s[1][1], s[2][1], s[3][1], s[0][1]];
        let r2 = [s[2][2], s[3][2], s[0][2], s[1][2]];
        let r3 = [s[3][3], s[0][3], s[1][3], s[2][3]];
        for c in 0..4 {
            s[c][1] = r1[c];
            s[c][2] = r2[c];
            s[c][3] = r3[c];
        }
    }
    pub fn inv_shift_rows(s: &mut State) {
        let r1 = [s[3][1], s[0][1], s[1][1], s[2][1]];
        let r2 = [s[2][2], s[3][2], s[0][2], s[1][2]];
        let r3 = [s[1][3], s[2][3], s[3][3], s[0][3]];
        for c in 0..4 {
            s[c][1] = r1[c];
            s[c][2] = r2[c];
            s[c][3] = r3[c];
        }
    }
    pub fn mix_columns(s: &mut State) {
        for c in 0..4 {
            let a = s[c];
            s[c][0] = gmul(2, a[0]) ^ gmul(3, a[1]) ^ a[2] ^ a[3];
            s[c][1] = a[0] ^ gmul(2, a[1]) ^ gmul(3, a[2]) ^ a[3];
            s[c][2] = a[0] ^ a[1] ^ gmul(2, a[2]) ^ gmul(3, a[3]);
            s[c][3] = gmul(3, a[0]) ^ a[1] ^ a[2] ^ gmul(2, a[3]);
        }
    }
    pub fn inv_mix_columns(s: &mut State) {
        for c in 0..4 {
            let a = s[c];
            s[c][0] = gmul(0x0e, a[0]) ^ gmul(0x0b, a[1]) ^ gmul(0x0d, a[2]) ^ gmul(0x09, a[3]);
            s[c][1] = gmul(0x09, a[0]) ^ gmul(0x0e, a[1]) ^ gmul(0x0b, a[2]) ^ gmul(0x0d, a[3]);
            s[c][2] = gmul(0x0d, a[0]) ^ gmul(0x09, a[1]) ^ gmul(0x0e, a[2]) ^ gmul(0x0b, a[3]);
            s[c][3] = gmul(0x0b, a[0]) ^ gmul(0x0d, a[1]) ^ gmul(0x09, a[2]) ^ gmul(0x0e, a[3]);
        }
    }
    pub fn add_round_key(s: &mut State, rk: &[[u8; 4]; 4]) {
        for c in 0..4 {
            for r in 0..4 {
                s[c][r] ^= rk[c][r];
            }
        }
    }
}

/// Reduced-round AES-128.
///
/// `nr` is the number of rounds. `nr = 10` matches the production AES;
/// `nr ∈ {3, 4, 5}` is what the cryptanalysis tests target. `final_mix_columns`
/// controls whether the *last* round retains MixColumns. FIPS 197
/// removes it; some textbook formulations of differential/integral
/// attacks find the no-MC variant slightly easier to reason about, but
/// we default to the FIPS form because the attacks here are written to
/// peel the final no-MC round off cleanly.
#[derive(Clone)]
pub struct ReducedAes128 {
    pub nr: usize,
    pub final_mix_columns: bool,
    /// Full schedule: `4 * (nr + 1)` 32-bit words.
    pub round_keys: Vec<[u8; 4]>,
}

impl ReducedAes128 {
    /// Expand `key` into the schedule for an `nr`-round cipher.
    /// `final_mix_columns = false` matches FIPS 197 for `nr = 10`.
    pub fn new(key: &[u8; 16], nr: usize, final_mix_columns: bool) -> Self {
        assert!((1..=10).contains(&nr), "nr must be in 1..=10");
        let total = 4 * (nr + 1);
        let mut w: Vec<[u8; 4]> = Vec::with_capacity(total);
        for i in 0..4 {
            w.push([key[4 * i], key[4 * i + 1], key[4 * i + 2], key[4 * i + 3]]);
        }
        for i in 4..total {
            let mut temp = w[i - 1];
            if i % 4 == 0 {
                // RotWord
                temp = [temp[1], temp[2], temp[3], temp[0]];
                // SubWord
                for b in temp.iter_mut() {
                    *b = SBOX[*b as usize];
                }
                temp[0] ^= RCON[i / 4];
            }
            let prev = w[i - 4];
            w.push([
                prev[0] ^ temp[0],
                prev[1] ^ temp[1],
                prev[2] ^ temp[2],
                prev[3] ^ temp[3],
            ]);
        }
        Self {
            nr,
            final_mix_columns,
            round_keys: w,
        }
    }

    /// Round key for round `i`, `i ∈ 0..=nr`. Round 0 is the
    /// pre-whitening key.
    pub fn round_key(&self, i: usize) -> [[u8; 4]; 4] {
        let mut rk = [[0u8; 4]; 4];
        for c in 0..4 {
            rk[c] = self.round_keys[4 * i + c];
        }
        rk
    }

    /// Encrypt a single 16-byte block under this reduced cipher.
    pub fn encrypt(&self, block: &[u8; 16]) -> [u8; 16] {
        let mut s = bytes_to_state(block);
        RoundOps::add_round_key(&mut s, &self.round_key(0));
        for round in 1..self.nr {
            RoundOps::sub_bytes(&mut s);
            RoundOps::shift_rows(&mut s);
            RoundOps::mix_columns(&mut s);
            RoundOps::add_round_key(&mut s, &self.round_key(round));
        }
        // Final round.
        RoundOps::sub_bytes(&mut s);
        RoundOps::shift_rows(&mut s);
        if self.final_mix_columns {
            RoundOps::mix_columns(&mut s);
        }
        RoundOps::add_round_key(&mut s, &self.round_key(self.nr));
        state_to_bytes(&s)
    }

    /// Decrypt a single 16-byte block.
    pub fn decrypt(&self, block: &[u8; 16]) -> [u8; 16] {
        let mut s = bytes_to_state(block);
        RoundOps::add_round_key(&mut s, &self.round_key(self.nr));
        if self.final_mix_columns {
            RoundOps::inv_mix_columns(&mut s);
        }
        RoundOps::inv_shift_rows(&mut s);
        RoundOps::inv_sub_bytes(&mut s);
        for round in (1..self.nr).rev() {
            RoundOps::add_round_key(&mut s, &self.round_key(round));
            RoundOps::inv_mix_columns(&mut s);
            RoundOps::inv_shift_rows(&mut s);
            RoundOps::inv_sub_bytes(&mut s);
        }
        RoundOps::add_round_key(&mut s, &self.round_key(0));
        state_to_bytes(&s)
    }

    /// Reverse the key schedule: given round key `i`, recover the
    /// master key. The attacks call this once they have round key `nr`.
    pub fn invert_schedule(round_key_index: usize, round_key: &[[u8; 4]; 4]) -> [u8; 16] {
        // Reconstruct the full 4*(nr+1) word vector. We only need
        // 4 contiguous words to start, so we work backwards from the
        // four words of `round_key`.
        //
        // For an AES-128 schedule, w[i] = w[i-4] XOR f(w[i-1]) where f
        // is RotWord+SubWord+RCON when i%4 == 0, and identity
        // otherwise. Inverting: w[i-4] = w[i] XOR f(w[i-1]).
        let words = round_key_index * 4;
        // Start with our four known words at positions [words..words+4].
        let mut w: Vec<[u8; 4]> = vec![[0; 4]; words + 4];
        w[words..words + 4].copy_from_slice(round_key);
        for i in (4..=(words + 3)).rev() {
            let temp = w[i - 1];
            let mut t = temp;
            if i % 4 == 0 {
                t = [t[1], t[2], t[3], t[0]];
                for b in t.iter_mut() {
                    *b = SBOX[*b as usize];
                }
                t[0] ^= RCON[i / 4];
            }
            // w[i] = w[i-4] XOR t  ⇒  w[i-4] = w[i] XOR t
            let wi = w[i];
            w[i - 4] = [wi[0] ^ t[0], wi[1] ^ t[1], wi[2] ^ t[2], wi[3] ^ t[3]];
        }
        let mut key = [0u8; 16];
        for i in 0..4 {
            key[4 * i..4 * i + 4].copy_from_slice(&w[i]);
        }
        key
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::symmetric::aes::{encrypt_block, AesKey};

    /// FIPS 197 Appendix B vector: matches the operational AES at Nr=10.
    #[test]
    fn matches_production_aes128() {
        let key: [u8; 16] = [
            0x2b, 0x7e, 0x15, 0x16, 0x28, 0xae, 0xd2, 0xa6, 0xab, 0xf7, 0x15, 0x88, 0x09, 0xcf,
            0x4f, 0x3c,
        ];
        let pt: [u8; 16] = [
            0x32, 0x43, 0xf6, 0xa8, 0x88, 0x5a, 0x30, 0x8d, 0x31, 0x31, 0x98, 0xa2, 0xe0, 0x37,
            0x07, 0x34,
        ];
        let expected: [u8; 16] = [
            0x39, 0x25, 0x84, 0x1d, 0x02, 0xdc, 0x09, 0xfb, 0xdc, 0x11, 0x85, 0x97, 0x19, 0x6a,
            0x0b, 0x32,
        ];
        let aes = ReducedAes128::new(&key, 10, false);
        assert_eq!(aes.encrypt(&pt), expected);
        // And matches the production implementation.
        assert_eq!(encrypt_block(&pt, &AesKey::Aes128(key)), expected);
    }

    #[test]
    fn round_trip_at_various_round_counts() {
        let key = [42u8; 16];
        let pt = [7u8; 16];
        for nr in 1..=10 {
            for fmc in [false, true] {
                let aes = ReducedAes128::new(&key, nr, fmc);
                let ct = aes.encrypt(&pt);
                assert_eq!(
                    aes.decrypt(&ct),
                    pt,
                    "round-trip failed at nr={nr}, fmc={fmc}"
                );
            }
        }
    }

    #[test]
    fn key_schedule_inverts() {
        let key: [u8; 16] = [
            0x2b, 0x7e, 0x15, 0x16, 0x28, 0xae, 0xd2, 0xa6, 0xab, 0xf7, 0x15, 0x88, 0x09, 0xcf,
            0x4f, 0x3c,
        ];
        let aes = ReducedAes128::new(&key, 10, false);
        // Recover the master key from each round key in turn.
        for i in 1..=10 {
            let rk = aes.round_key(i);
            let recovered = ReducedAes128::invert_schedule(i, &rk);
            assert_eq!(recovered, key, "schedule inversion failed at round {i}");
        }
    }
}
