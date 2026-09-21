//! Threefish — tweakable block cipher used as the round function of the
//! Skein hash family.  Designed by Ferguson, Lucas, Schneier, Whiting,
//! Bellare, Kohno, Callas, and Walker (2008) for the SHA-3 competition.
//!
//! Threefish is a pure ARX (Add-Rotate-XOR) cipher: every round consists
//! of modular additions, fixed-distance bit rotations, and XORs.  No
//! S-boxes, no field arithmetic, no lookup tables — which makes
//! cache-timing attacks structurally impossible at the algorithm level.
//!
//! # Variants
//! The spec defines three block sizes:
//!
//! | Variant       | Block / key | Words `N_w` | Rounds `N_r` |
//! |---------------|-------------|-------------|--------------|
//! | Threefish-256 | 32 bytes    | 4           | 72           |
//! | Threefish-512 | 64 bytes    | 8           | 72           |
//! | Threefish-1024| 128 bytes   | 16          | 80           |
//!
//! Each variant takes a 16-byte (2-word) tweak.  All three sizes are
//! implemented here as parallel `Threefish{256,512,1024}` types — the
//! algorithm is identical apart from the `N_w`-specific permutation
//! (`PI`) and rotation (`R`) tables, which are taken verbatim from
//! Skein 1.3 §3.3 Table 4.
//!
//! # Side-channel posture
//!
//! Pure ARX, no tables, no operand-dependent branches.  The full set
//! of rotations is fixed at compile time.  The only memory accesses
//! are sequential reads of the key and tweak words and contiguous
//! writes back to the state — neither leaks anything about secret
//! data via cache lines or branch predictors.  This is the same
//! reason Threefish (and ChaCha20) are recommended over AES on
//! platforms without AES-NI.
//!
//! # Caveats
//!
//! - **KAT-verified for all three sizes.**  All three variants
//!   (256 / 512 / 1024-bit block) are cross-checked against the
//!   all-zero key/tweak/plaintext vectors produced by the Skein 1.3
//!   reference implementation, independently corroborated by the
//!   RustCrypto `threefish` crate (which sources from Crypto++'s
//!   `TestVectors/threefish.txt`).  See `kat_threefish{256,512,1024}_zero`
//!   in the test module for exact bytes and provenance.
//! - Threefish on its own is a block cipher, not an authenticated
//!   construction.  The Skein hash builds a MAC (Skein-MAC) and a
//!   stream cipher (Skein-Counter) on top; we don't include those
//!   here.

// ── Common helpers (shared across Threefish-256/-512/-1024) ──────────────────

/// Skein 1.3 §3.3 key-extension constant `C₂₄₀`.  Mixed into the
/// extra key word `k_{N_w}` so that an all-zero key cannot collapse
/// the subkey schedule.
const C240: u64 = 0x1BD1_1BDA_A9FC_1A22;

/// MIX function: `(y₀, y₁) = (x₀ + x₁, ROL(x₁, R) ⊕ (x₀ + x₁))`.
///
/// The forward direction is `(x0, x1) → (x0+x1, (x1<<<R) XOR (x0+x1))`.
/// Inverse: `(y0, y1) → (y0 - ((y1 XOR y0) >>> R), (y1 XOR y0) >>> R)`.
#[inline(always)]
fn mix(x0: u64, x1: u64, r: u32) -> (u64, u64) {
    let y0 = x0.wrapping_add(x1);
    let y1 = x1.rotate_left(r) ^ y0;
    (y0, y1)
}

#[inline(always)]
fn mix_inv(y0: u64, y1: u64, r: u32) -> (u64, u64) {
    let x1 = (y1 ^ y0).rotate_right(r);
    let x0 = y0.wrapping_sub(x1);
    (x0, x1)
}

// ── Threefish-512 ────────────────────────────────────────────────────────────
//
// 64-byte block, 64-byte key, 16-byte tweak, 72 rounds.
// Subkey injection every 4 rounds gives N_r/4 + 1 = 19 subkeys.

/// Permutation table π_e for Threefish-512.  After the per-pair MIX,
/// `state[i]` is replaced by `state[PI_512[i]]`.  Skein 1.3 §3.3 Table 3.
const PI_512: [usize; 8] = [2, 1, 4, 7, 6, 5, 0, 3];

/// Rotation constants for Threefish-512.  `R_512[d mod 8][j]` is the
/// rotation amount for the `j`-th pair in round `d`.  Skein 1.3 §3.3
/// Table 4 (left column).
#[rustfmt::skip]
const R_512: [[u32; 4]; 8] = [
    [46, 36, 19, 37],
    [33, 27, 14, 42],
    [17, 49, 36, 39],
    [44,  9, 54, 56],
    [39, 30, 34, 24],
    [13, 50, 10, 17],
    [25, 29, 39, 43],
    [ 8, 35, 56, 22],
];

/// Threefish-512 expanded key (key + tweak preprocessed into the
/// extension words).  Holding this struct avoids recomputing `k_8` and
/// `t_2` on every block; in practice we encrypt many blocks under the
/// same (key, tweak) pair.
#[derive(Clone)]
pub struct Threefish512 {
    /// `k[0..8]` are the original key words; `k[8] = C240 ⊕ k₀ ⊕ … ⊕ k₇`.
    k: [u64; 9],
    /// `t[0..2]` are the original tweak words; `t[2] = t₀ ⊕ t₁`.
    t: [u64; 3],
}

impl Drop for Threefish512 {
    fn drop(&mut self) {
        for w in self.k.iter_mut() {
            *w = 0;
        }
        for w in self.t.iter_mut() {
            *w = 0;
        }
    }
}

impl Threefish512 {
    /// Build an expanded Threefish-512 key.  `key` is the 64-byte
    /// master key; `tweak` is the 16-byte tweak (in 2 little-endian
    /// `u64` words).
    pub fn new(key: &[u8; 64], tweak: &[u8; 16]) -> Self {
        let mut k = [0u64; 9];
        for i in 0..8 {
            k[i] = u64::from_le_bytes(key[i * 8..i * 8 + 8].try_into().unwrap());
        }
        // Skein 1.3 §3.3.2 (1):  k_{N_w} = C240 ⊕ k_0 ⊕ … ⊕ k_{N_w−1}.
        k[8] = C240 ^ k[0] ^ k[1] ^ k[2] ^ k[3] ^ k[4] ^ k[5] ^ k[6] ^ k[7];

        let mut t = [0u64; 3];
        t[0] = u64::from_le_bytes(tweak[0..8].try_into().unwrap());
        t[1] = u64::from_le_bytes(tweak[8..16].try_into().unwrap());
        // Skein 1.3 §3.3.2 (2):  t_2 = t_0 ⊕ t_1.
        t[2] = t[0] ^ t[1];

        Threefish512 { k, t }
    }

    /// Compute subkey `s_d` for `d ∈ 0..=18` (= N_r/4).  Three of the
    /// eight words mix in the tweak; the last also mixes in `d`.
    fn subkey(&self, d: usize, out: &mut [u64; 8]) {
        // s_d[i] = k[(d + i) mod 9]   for i in 0..=4
        // s_d[5] = k[(d + 5) mod 9] + t[d mod 3]
        // s_d[6] = k[(d + 6) mod 9] + t[(d + 1) mod 3]
        // s_d[7] = k[(d + 7) mod 9] + d
        // (additions are mod 2^64).
        for i in 0..5 {
            out[i] = self.k[(d + i) % 9];
        }
        out[5] = self.k[(d + 5) % 9].wrapping_add(self.t[d % 3]);
        out[6] = self.k[(d + 6) % 9].wrapping_add(self.t[(d + 1) % 3]);
        out[7] = self.k[(d + 7) % 9].wrapping_add(d as u64);
    }

    /// Encrypt one 64-byte block in place via fixed-shape ARX rounds.
    pub fn encrypt(&self, block: &mut [u8; 64]) {
        let mut v = [0u64; 8];
        for i in 0..8 {
            v[i] = u64::from_le_bytes(block[i * 8..i * 8 + 8].try_into().unwrap());
        }

        let mut sk = [0u64; 8];

        // 72 rounds, with subkey injection every 4 rounds (so 18
        // injections during the loop) plus a final injection after
        // the last round (s_{N_r/4} = s_18).
        for d in 0..72 {
            // Subkey injection.
            if d % 4 == 0 {
                self.subkey(d / 4, &mut sk);
                for i in 0..8 {
                    v[i] = v[i].wrapping_add(sk[i]);
                }
            }

            // MIX on each of the 4 word pairs, with rotation row
            // selected by d mod 8.
            let r = &R_512[d % 8];
            let (a, b) = mix(v[0], v[1], r[0]);
            v[0] = a;
            v[1] = b;
            let (a, b) = mix(v[2], v[3], r[1]);
            v[2] = a;
            v[3] = b;
            let (a, b) = mix(v[4], v[5], r[2]);
            v[4] = a;
            v[5] = b;
            let (a, b) = mix(v[6], v[7], r[3]);
            v[6] = a;
            v[7] = b;

            // Permute words: new[i] = old[PI[i]].
            let prev = v;
            for i in 0..8 {
                v[i] = prev[PI_512[i]];
            }
        }

        // Final subkey injection (s_{N_r/4} = s_18).
        self.subkey(18, &mut sk);
        for i in 0..8 {
            v[i] = v[i].wrapping_add(sk[i]);
        }

        for i in 0..8 {
            block[i * 8..i * 8 + 8].copy_from_slice(&v[i].to_le_bytes());
        }
    }

    /// Decrypt one 64-byte block in place.  Reverses the encryption
    /// step-for-step: undo the final injection, then for each round
    /// run the inverse permutation, inverse MIX, and (every 4 rounds)
    /// subtract the subkey.
    pub fn decrypt(&self, block: &mut [u8; 64]) {
        let mut v = [0u64; 8];
        for i in 0..8 {
            v[i] = u64::from_le_bytes(block[i * 8..i * 8 + 8].try_into().unwrap());
        }

        let mut sk = [0u64; 8];

        // Undo the post-loop subkey injection.
        self.subkey(18, &mut sk);
        for i in 0..8 {
            v[i] = v[i].wrapping_sub(sk[i]);
        }

        // Inverse permutation: pi_d such that pi_e ∘ pi_d = id.
        // For PI_512 = [2,1,4,7,6,5,0,3], the inverse is [6,1,0,7,2,5,4,3].
        const PI_512_INV: [usize; 8] = [6, 1, 0, 7, 2, 5, 4, 3];

        for d in (0..72).rev() {
            // Undo word permutation.
            let prev = v;
            for i in 0..8 {
                v[i] = prev[PI_512_INV[i]];
            }

            // Undo MIX on each pair.
            let r = &R_512[d % 8];
            let (a, b) = mix_inv(v[0], v[1], r[0]);
            v[0] = a;
            v[1] = b;
            let (a, b) = mix_inv(v[2], v[3], r[1]);
            v[2] = a;
            v[3] = b;
            let (a, b) = mix_inv(v[4], v[5], r[2]);
            v[4] = a;
            v[5] = b;
            let (a, b) = mix_inv(v[6], v[7], r[3]);
            v[6] = a;
            v[7] = b;

            if d % 4 == 0 {
                self.subkey(d / 4, &mut sk);
                for i in 0..8 {
                    v[i] = v[i].wrapping_sub(sk[i]);
                }
            }
        }

        for i in 0..8 {
            block[i * 8..i * 8 + 8].copy_from_slice(&v[i].to_le_bytes());
        }
    }
}

// ── Threefish-256 ────────────────────────────────────────────────────────────

const PI_256: [usize; 4] = [0, 3, 2, 1];

#[rustfmt::skip]
const R_256: [[u32; 2]; 8] = [
    [14, 16],
    [52, 57],
    [23, 40],
    [ 5, 37],
    [25, 33],
    [46, 12],
    [58, 22],
    [32, 32],
];

#[derive(Clone)]
pub struct Threefish256 {
    k: [u64; 5],
    t: [u64; 3],
}

impl Drop for Threefish256 {
    fn drop(&mut self) {
        for w in self.k.iter_mut() {
            *w = 0;
        }
        for w in self.t.iter_mut() {
            *w = 0;
        }
    }
}

impl Threefish256 {
    pub fn new(key: &[u8; 32], tweak: &[u8; 16]) -> Self {
        let mut k = [0u64; 5];
        for i in 0..4 {
            k[i] = u64::from_le_bytes(key[i * 8..i * 8 + 8].try_into().unwrap());
        }
        k[4] = C240 ^ k[0] ^ k[1] ^ k[2] ^ k[3];
        let mut t = [0u64; 3];
        t[0] = u64::from_le_bytes(tweak[0..8].try_into().unwrap());
        t[1] = u64::from_le_bytes(tweak[8..16].try_into().unwrap());
        t[2] = t[0] ^ t[1];
        Threefish256 { k, t }
    }

    fn subkey(&self, d: usize, out: &mut [u64; 4]) {
        // For Threefish-256: 4 words.  Subkey layout (Skein 1.3 §3.3.2):
        //   s_d[0] = k[d mod 5]
        //   s_d[1] = k[(d + 1) mod 5] + t[d mod 3]
        //   s_d[2] = k[(d + 2) mod 5] + t[(d + 1) mod 3]
        //   s_d[3] = k[(d + 3) mod 5] + d
        out[0] = self.k[d % 5];
        out[1] = self.k[(d + 1) % 5].wrapping_add(self.t[d % 3]);
        out[2] = self.k[(d + 2) % 5].wrapping_add(self.t[(d + 1) % 3]);
        out[3] = self.k[(d + 3) % 5].wrapping_add(d as u64);
    }

    pub fn encrypt(&self, block: &mut [u8; 32]) {
        let mut v = [0u64; 4];
        for i in 0..4 {
            v[i] = u64::from_le_bytes(block[i * 8..i * 8 + 8].try_into().unwrap());
        }
        let mut sk = [0u64; 4];

        for d in 0..72 {
            if d % 4 == 0 {
                self.subkey(d / 4, &mut sk);
                for i in 0..4 {
                    v[i] = v[i].wrapping_add(sk[i]);
                }
            }
            let r = &R_256[d % 8];
            let (a, b) = mix(v[0], v[1], r[0]);
            v[0] = a;
            v[1] = b;
            let (a, b) = mix(v[2], v[3], r[1]);
            v[2] = a;
            v[3] = b;

            let prev = v;
            for i in 0..4 {
                v[i] = prev[PI_256[i]];
            }
        }
        self.subkey(18, &mut sk);
        for i in 0..4 {
            v[i] = v[i].wrapping_add(sk[i]);
        }
        for i in 0..4 {
            block[i * 8..i * 8 + 8].copy_from_slice(&v[i].to_le_bytes());
        }
    }

    pub fn decrypt(&self, block: &mut [u8; 32]) {
        let mut v = [0u64; 4];
        for i in 0..4 {
            v[i] = u64::from_le_bytes(block[i * 8..i * 8 + 8].try_into().unwrap());
        }
        let mut sk = [0u64; 4];

        self.subkey(18, &mut sk);
        for i in 0..4 {
            v[i] = v[i].wrapping_sub(sk[i]);
        }

        // Inverse of [0,3,2,1] is [0,3,2,1] (it's an involution).
        const PI_256_INV: [usize; 4] = [0, 3, 2, 1];

        for d in (0..72).rev() {
            let prev = v;
            for i in 0..4 {
                v[i] = prev[PI_256_INV[i]];
            }
            let r = &R_256[d % 8];
            let (a, b) = mix_inv(v[0], v[1], r[0]);
            v[0] = a;
            v[1] = b;
            let (a, b) = mix_inv(v[2], v[3], r[1]);
            v[2] = a;
            v[3] = b;

            if d % 4 == 0 {
                self.subkey(d / 4, &mut sk);
                for i in 0..4 {
                    v[i] = v[i].wrapping_sub(sk[i]);
                }
            }
        }

        for i in 0..4 {
            block[i * 8..i * 8 + 8].copy_from_slice(&v[i].to_le_bytes());
        }
    }
}

// ── Threefish-1024 ───────────────────────────────────────────────────────────
//
// 128-byte block, 80 rounds (vs. 72 for the smaller variants).

const PI_1024: [usize; 16] = [0, 9, 2, 13, 6, 11, 4, 15, 10, 7, 12, 3, 14, 5, 8, 1];

#[rustfmt::skip]
const R_1024: [[u32; 8]; 8] = [
    [24, 13,  8, 47,  8, 17, 22, 37],
    [38, 19, 10, 55, 49, 18, 23, 52],
    [33,  4, 51, 13, 34, 41, 59, 17],
    [ 5, 20, 48, 41, 47, 28, 16, 25],
    [41,  9, 37, 31, 12, 47, 44, 30],
    [16, 34, 56, 51,  4, 53, 42, 41],
    [31, 44, 47, 46, 19, 42, 44, 25],
    [ 9, 48, 35, 52, 23, 31, 37, 20],
];

#[derive(Clone)]
pub struct Threefish1024 {
    k: [u64; 17],
    t: [u64; 3],
}

impl Drop for Threefish1024 {
    fn drop(&mut self) {
        for w in self.k.iter_mut() {
            *w = 0;
        }
        for w in self.t.iter_mut() {
            *w = 0;
        }
    }
}

impl Threefish1024 {
    pub fn new(key: &[u8; 128], tweak: &[u8; 16]) -> Self {
        let mut k = [0u64; 17];
        for i in 0..16 {
            k[i] = u64::from_le_bytes(key[i * 8..i * 8 + 8].try_into().unwrap());
        }
        k[16] = C240
            ^ k[0]
            ^ k[1]
            ^ k[2]
            ^ k[3]
            ^ k[4]
            ^ k[5]
            ^ k[6]
            ^ k[7]
            ^ k[8]
            ^ k[9]
            ^ k[10]
            ^ k[11]
            ^ k[12]
            ^ k[13]
            ^ k[14]
            ^ k[15];
        let mut t = [0u64; 3];
        t[0] = u64::from_le_bytes(tweak[0..8].try_into().unwrap());
        t[1] = u64::from_le_bytes(tweak[8..16].try_into().unwrap());
        t[2] = t[0] ^ t[1];
        Threefish1024 { k, t }
    }

    fn subkey(&self, d: usize, out: &mut [u64; 16]) {
        // 16-word subkey: tweak mixes into positions N_w-3, N_w-2, N_w-1
        // (= 13, 14, 15) and `d` into the last.
        for i in 0..13 {
            out[i] = self.k[(d + i) % 17];
        }
        out[13] = self.k[(d + 13) % 17].wrapping_add(self.t[d % 3]);
        out[14] = self.k[(d + 14) % 17].wrapping_add(self.t[(d + 1) % 3]);
        out[15] = self.k[(d + 15) % 17].wrapping_add(d as u64);
    }

    pub fn encrypt(&self, block: &mut [u8; 128]) {
        let mut v = [0u64; 16];
        for i in 0..16 {
            v[i] = u64::from_le_bytes(block[i * 8..i * 8 + 8].try_into().unwrap());
        }
        let mut sk = [0u64; 16];

        for d in 0..80 {
            if d % 4 == 0 {
                self.subkey(d / 4, &mut sk);
                for i in 0..16 {
                    v[i] = v[i].wrapping_add(sk[i]);
                }
            }
            let r = &R_1024[d % 8];
            for j in 0..8 {
                let (a, b) = mix(v[2 * j], v[2 * j + 1], r[j]);
                v[2 * j] = a;
                v[2 * j + 1] = b;
            }
            let prev = v;
            for i in 0..16 {
                v[i] = prev[PI_1024[i]];
            }
        }
        self.subkey(20, &mut sk);
        for i in 0..16 {
            v[i] = v[i].wrapping_add(sk[i]);
        }
        for i in 0..16 {
            block[i * 8..i * 8 + 8].copy_from_slice(&v[i].to_le_bytes());
        }
    }

    pub fn decrypt(&self, block: &mut [u8; 128]) {
        let mut v = [0u64; 16];
        for i in 0..16 {
            v[i] = u64::from_le_bytes(block[i * 8..i * 8 + 8].try_into().unwrap());
        }
        let mut sk = [0u64; 16];

        self.subkey(20, &mut sk);
        for i in 0..16 {
            v[i] = v[i].wrapping_sub(sk[i]);
        }

        // Inverse of PI_1024 = [0, 9, 2, 13, 6, 11, 4, 15, 10, 7, 12, 3, 14, 5, 8, 1].
        // i.e. PI_INV[PI[i]] = i.
        let pi_inv: [usize; 16] = {
            let mut inv = [0usize; 16];
            let mut i = 0;
            while i < 16 {
                inv[PI_1024[i]] = i;
                i += 1;
            }
            inv
        };

        for d in (0..80).rev() {
            let prev = v;
            for i in 0..16 {
                v[i] = prev[pi_inv[i]];
            }
            let r = &R_1024[d % 8];
            for j in 0..8 {
                let (a, b) = mix_inv(v[2 * j], v[2 * j + 1], r[j]);
                v[2 * j] = a;
                v[2 * j + 1] = b;
            }
            if d % 4 == 0 {
                self.subkey(d / 4, &mut sk);
                for i in 0..16 {
                    v[i] = v[i].wrapping_sub(sk[i]);
                }
            }
        }

        for i in 0..16 {
            block[i * 8..i * 8 + 8].copy_from_slice(&v[i].to_le_bytes());
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── MIX inverse property ─────────────────────────────────────────

    #[test]
    fn mix_inverts() {
        for r in [1u32, 14, 32, 47, 63] {
            let cases = [
                (0u64, 0u64),
                (1, 0),
                (0, 1),
                (u64::MAX, 0),
                (0xdeadbeefcafebabe, 0x1234567890abcdef),
            ];
            for (x0, x1) in cases {
                let (y0, y1) = mix(x0, x1, r);
                let (x0p, x1p) = mix_inv(y0, y1, r);
                assert_eq!((x0p, x1p), (x0, x1), "mix_inv failed for r={r}");
            }
        }
    }

    // ── Threefish-512 round-trip and properties ──────────────────────

    #[test]
    fn threefish512_round_trip_zero() {
        let key = [0u8; 64];
        let tweak = [0u8; 16];
        let pt = [0u8; 64];
        let cipher = Threefish512::new(&key, &tweak);
        let mut block = pt;
        cipher.encrypt(&mut block);
        assert_ne!(
            block, pt,
            "zero key/tweak/plaintext must not be a fixed point"
        );
        cipher.decrypt(&mut block);
        assert_eq!(block, pt);
    }

    #[test]
    fn threefish512_round_trip_random() {
        let mut s = 0xdeadbeef_12345678u64;
        for _ in 0..16 {
            let mut key = [0u8; 64];
            let mut tweak = [0u8; 16];
            let mut pt = [0u8; 64];
            for buf in [&mut key[..], &mut tweak[..], &mut pt[..]] {
                for b in buf.iter_mut() {
                    s = s
                        .wrapping_mul(6364136223846793005)
                        .wrapping_add(1442695040888963407);
                    *b = (s >> 56) as u8;
                }
            }
            let cipher = Threefish512::new(&key, &tweak);
            let mut block = pt;
            cipher.encrypt(&mut block);
            cipher.decrypt(&mut block);
            assert_eq!(block, pt);
        }
    }

    #[test]
    fn threefish512_distinct_tweaks_diverge() {
        let key = [0x42u8; 64];
        let pt = [0x33u8; 64];

        let t1 = [0u8; 16];
        let mut t2 = [0u8; 16];
        t2[0] = 1;

        let c1 = {
            let cipher = Threefish512::new(&key, &t1);
            let mut b = pt;
            cipher.encrypt(&mut b);
            b
        };
        let c2 = {
            let cipher = Threefish512::new(&key, &t2);
            let mut b = pt;
            cipher.encrypt(&mut b);
            b
        };
        assert_ne!(c1, c2, "single-bit tweak change must change ciphertext");

        // Tweak avalanche: ≥ 200 of 512 bits should differ.
        let differing: usize = c1
            .iter()
            .zip(c2.iter())
            .map(|(a, b)| (a ^ b).count_ones() as usize)
            .sum();
        assert!(
            differing >= 200,
            "weak avalanche on tweak: {} bits",
            differing
        );
    }

    #[test]
    fn threefish512_distinct_keys_diverge() {
        let pt = [0u8; 64];
        let tweak = [0u8; 16];
        let k1 = [0u8; 64];
        let mut k2 = [0u8; 64];
        k2[0] = 1;
        let c1 = {
            let mut b = pt;
            Threefish512::new(&k1, &tweak).encrypt(&mut b);
            b
        };
        let c2 = {
            let mut b = pt;
            Threefish512::new(&k2, &tweak).encrypt(&mut b);
            b
        };
        assert_ne!(c1, c2);
    }

    // ── Threefish-256 round-trip ─────────────────────────────────────

    #[test]
    fn threefish256_round_trip_zero() {
        let cipher = Threefish256::new(&[0u8; 32], &[0u8; 16]);
        let pt = [0u8; 32];
        let mut block = pt;
        cipher.encrypt(&mut block);
        assert_ne!(block, pt);
        cipher.decrypt(&mut block);
        assert_eq!(block, pt);
    }

    #[test]
    fn threefish256_round_trip_random() {
        let mut s = 0xfeedfaceu64;
        for _ in 0..16 {
            let mut key = [0u8; 32];
            let mut tweak = [0u8; 16];
            let mut pt = [0u8; 32];
            for buf in [&mut key[..], &mut tweak[..], &mut pt[..]] {
                for b in buf.iter_mut() {
                    s = s
                        .wrapping_mul(6364136223846793005)
                        .wrapping_add(1442695040888963407);
                    *b = (s >> 56) as u8;
                }
            }
            let cipher = Threefish256::new(&key, &tweak);
            let mut block = pt;
            cipher.encrypt(&mut block);
            cipher.decrypt(&mut block);
            assert_eq!(block, pt);
        }
    }

    // ── Threefish-1024 round-trip ────────────────────────────────────

    #[test]
    fn threefish1024_round_trip_zero() {
        let cipher = Threefish1024::new(&[0u8; 128], &[0u8; 16]);
        let pt = [0u8; 128];
        let mut block = pt;
        cipher.encrypt(&mut block);
        assert_ne!(block, pt);
        cipher.decrypt(&mut block);
        assert_eq!(block, pt);
    }

    #[test]
    fn threefish1024_round_trip_random() {
        let mut s = 0xa5a5a5a5_5a5a5a5au64;
        for _ in 0..8 {
            let mut key = [0u8; 128];
            let mut tweak = [0u8; 16];
            let mut pt = [0u8; 128];
            for buf in [&mut key[..], &mut tweak[..], &mut pt[..]] {
                for b in buf.iter_mut() {
                    s = s
                        .wrapping_mul(6364136223846793005)
                        .wrapping_add(1442695040888963407);
                    *b = (s >> 56) as u8;
                }
            }
            let cipher = Threefish1024::new(&key, &tweak);
            let mut block = pt;
            cipher.encrypt(&mut block);
            cipher.decrypt(&mut block);
            assert_eq!(block, pt);
        }
    }

    // ── Published KAT vectors ───────────────────────────────────────────
    //
    // Threefish has no separately-published KAT file in the Skein 1.3
    // submission package — the submission's Appendix C contains Skein-
    // hash test vectors only.  The vectors below are produced by the
    // Skein 1.3 reference implementation (NIST/CD/Reference_Implementation
    // in skein.zip from schneier.com) calling the Threefish-N
    // Encrypt_Block primitive directly with all-zero key, tweak, and
    // plaintext.  They are independently cross-checked against the
    // RustCrypto `threefish` crate's tests, which in turn cite Crypto++'s
    // TestVectors/threefish.txt — these are the de-facto canonical
    // Threefish KATs.
    //
    // Byte order: words are little-endian u64 (Skein convention), so
    // `ciphertext[0..8]` is the LE byte serialisation of the first
    // state word, `ciphertext[8..16]` is the second, etc.

    fn hex_to_vec(s: &str) -> Vec<u8> {
        hex::decode(s).expect("valid hex literal")
    }

    #[test]
    fn kat_threefish256_zero() {
        let key = [0u8; 32];
        let tweak = [0u8; 16];
        let mut block = [0u8; 32];
        let cipher = Threefish256::new(&key, &tweak);
        cipher.encrypt(&mut block);
        let expect = hex_to_vec("84da2a1f8beaee947066ae3e3103f1ad536db1f4a1192495116b9f3ce6133fd8");
        assert_eq!(&block[..], &expect[..], "Threefish-256 KAT mismatch");
        cipher.decrypt(&mut block);
        assert_eq!(block, [0u8; 32]);
    }

    #[test]
    fn kat_threefish512_zero() {
        let key = [0u8; 64];
        let tweak = [0u8; 16];
        let mut block = [0u8; 64];
        let cipher = Threefish512::new(&key, &tweak);
        cipher.encrypt(&mut block);
        let expect = hex_to_vec(
            "b1a2bbc6ef6025bc40eb3822161f36e375d1bb0aee3186fbd19e47c5d479947b\
             7bc2f8586e35f0cff7e7f03084b0b7b1f1ab3961a580a3e97eb41ea14a6d7bbe",
        );
        assert_eq!(&block[..], &expect[..], "Threefish-512 KAT mismatch");
        cipher.decrypt(&mut block);
        assert_eq!(block, [0u8; 64]);
    }

    #[test]
    fn kat_threefish1024_zero() {
        let key = [0u8; 128];
        let tweak = [0u8; 16];
        let mut block = [0u8; 128];
        let cipher = Threefish1024::new(&key, &tweak);
        cipher.encrypt(&mut block);
        let expect = hex_to_vec(
            "f05c3d0a3d05b304f785ddc7d1e036015c8aa76e2f217b06c6e1544c0bc1a90d\
             f0accb9473c24e0fd54fea68057f43329cb454761d6df5cf7b2e9b3614fbd5a2\
             0b2e4760b40603540d82eabc5482c171c832afbe68406bc39500367a592943fa\
             9a5b4a43286ca3c4cf46104b443143d560a4b230488311df4feef7e1dfe8391e",
        );
        assert_eq!(&block[..], &expect[..], "Threefish-1024 KAT mismatch");
        cipher.decrypt(&mut block);
        assert_eq!(block, [0u8; 128]);
    }

    #[test]
    fn pi_1024_inverse_is_correct() {
        // Self-check the manually-derived inverse: PI_INV[PI[i]] = i.
        let mut inv = [0usize; 16];
        for i in 0..16 {
            inv[PI_1024[i]] = i;
        }
        for i in 0..16 {
            assert_eq!(PI_1024[inv[i]], i);
        }
    }
}
