//! **FEAL-8** — Fast data Encipherment ALgorithm, 8-round variant.
//!
//! Designed by **Akihiro Shimizu and Shoji Miyaguchi** at NTT in 1987
//! as a software-friendly DES alternative.  FEAL replaced DES's bit
//! permutations and table-lookup S-boxes with simple byte rotations
//! and additions, so it runs fast on 8-bit microcontrollers; in
//! exchange, the diffusion is weak and the cipher fell to differential
//! and linear cryptanalysis almost immediately.
//!
//! ## Security note
//!
//! **FEAL is comprehensively broken** — included here strictly as a
//! historical and pedagogical artefact, *not* for any real use:
//!
//! - FEAL-4 was broken by Bert den Boer in 1988 with 100–10000
//!   chosen plaintexts.
//! - FEAL-8, the variant implemented here, fell to Murphy (1990) and
//!   was definitively broken by Biham & Shamir's differential
//!   cryptanalysis (1991) with 1280 chosen plaintexts.
//! - Matsui used FEAL-8 as the introductory example for **linear
//!   cryptanalysis** (1992), recovering the key with 2^15 known
//!   plaintexts — i.e. trivially.
//!
//! Even FEAL-N (any N) succumbs to linear cryptanalysis well below
//! brute force, so the design has no surviving variant.
//!
//! ## Structure
//!
//! 64-bit block, 64-bit key, 8-round Feistel.
//!
//! - Pre-whitening of the 64-bit input with 64 bits of subkey
//!   (`(K_8, K_9, K_{10}, K_{11})`).
//! - XOR the right half with the left.
//! - 8 Feistel rounds with the round function `f(R, K_i)`.
//! - Swap the halves back, XOR the right half with the left.
//! - Post-whitening of the 64-bit output with another 64 bits of
//!   subkey (`(K_{12}, …, K_{15})`).
//!
//! ## Round function `f`
//!
//! `f` takes a 32-bit data word `a = (a0 a1 a2 a3)` (bytes MSB-first)
//! and a 16-bit round key `β = (β0 β1)`:
//!
//! ```text
//!     f1 = S1( a0 ⊕ a1 ⊕ β0 ,  a2 ⊕ a3 ⊕ β1 )
//!     f2 = S0( a2 ⊕ a3 ⊕ β1 ,  f1 )
//!     f0 = S0( a0 ,  f1 )
//!     f3 = S1( a3 ,  f2 )
//!     f  = (f0 f1 f2 f3)
//! ```
//!
//! where the S-boxes are byte rotations of a sum:
//!
//! ```text
//!     S0(x, y) = ROL_2( (x + y    ) mod 256 )
//!     S1(x, y) = ROL_2( (x + y + 1) mod 256 )
//! ```
//!
//! ## Key schedule
//!
//! The 64-bit key splits into `K_L = key[0..4]` and `K_R = key[4..8]`
//! (big-endian).  The schedule keeps running state `(A, B, D)` initialised
//! to `(K_L, K_R, 0)` and at each step `r = 0..8` computes
//!
//! ```text
//!     fK_in_A = A
//!     fK_in_B = B ⊕ D
//!     new = fK(fK_in_A, fK_in_B)
//!     output high16(new), low16(new)   ; two new 16-bit subkeys
//!     D, A, B  ←  A, B, new            ; rotate state
//! ```
//!
//! producing 16 subkeys `K_0..K_15`: the first 8 are the round keys,
//! the last 8 are paired into the four 32-bit whitening words.
//!
//! `fK` is the keyless variant of the round function:
//!
//! ```text
//!     fk1 = S1( a0 ⊕ a1 ,  a2 ⊕ a3 ⊕ b0 )
//!     fk2 = S0( a2 ⊕ a3 ,  fk1 ⊕ b1 )
//!     fk0 = S0( a0 ,  fk1 ⊕ b2 )
//!     fk3 = S1( a3 ,  fk2 ⊕ b3 )
//! ```
//!
//! ## References
//!
//! - S. Miyaguchi, *The FEAL Cipher Family*, CRYPTO 1990.
//! - B. Schneier, *Applied Cryptography*, 2nd ed., §13.5.
//! - Biham, Shamir, *Differential Cryptanalysis of FEAL and N-Hash*,
//!   EUROCRYPT 1991.

// ── S-boxes ──────────────────────────────────────────────────────────

/// `S_0(a, b) = ROL2(a + b mod 256)`.
#[inline]
fn s0(a: u8, b: u8) -> u8 {
    a.wrapping_add(b).rotate_left(2)
}

/// `S_1(a, b) = ROL2(a + b + 1 mod 256)`.
#[inline]
fn s1(a: u8, b: u8) -> u8 {
    a.wrapping_add(b).wrapping_add(1).rotate_left(2)
}

// ── Round / key-schedule functions ───────────────────────────────────

/// FEAL round function `f(α, β)`.  `α` is a 32-bit data word and `β`
/// a 16-bit round key.  Bytes are MSB-first.
#[inline]
fn f(alpha: u32, beta: u16) -> u32 {
    let a0 = (alpha >> 24) as u8;
    let a1 = (alpha >> 16) as u8;
    let a2 = (alpha >> 8) as u8;
    let a3 = alpha as u8;
    let b0 = (beta >> 8) as u8;
    let b1 = beta as u8;

    let t1 = a0 ^ a1 ^ b0;
    let t2 = a2 ^ a3 ^ b1;
    let f1 = s1(t1, t2);
    let f2 = s0(t2, f1);
    let f0 = s0(a0, f1);
    let f3 = s1(a3, f2);

    ((f0 as u32) << 24) | ((f1 as u32) << 16) | ((f2 as u32) << 8) | (f3 as u32)
}

/// Keyless variant `fK(α, β)` used by the key schedule.
#[inline]
fn fk(alpha: u32, beta: u32) -> u32 {
    let a0 = (alpha >> 24) as u8;
    let a1 = (alpha >> 16) as u8;
    let a2 = (alpha >> 8) as u8;
    let a3 = alpha as u8;
    let b0 = (beta >> 24) as u8;
    let b1 = (beta >> 16) as u8;
    let b2 = (beta >> 8) as u8;
    let b3 = beta as u8;

    let t1 = a0 ^ a1;
    let t2 = a2 ^ a3;
    let fk1 = s1(t1, t2 ^ b0);
    let fk2 = s0(t2, fk1 ^ b1);
    let fk0 = s0(a0, fk1 ^ b2);
    let fk3 = s1(a3, fk2 ^ b3);

    ((fk0 as u32) << 24) | ((fk1 as u32) << 16) | ((fk2 as u32) << 8) | (fk3 as u32)
}

// ── Key schedule ─────────────────────────────────────────────────────

/// Compute the 16 sixteen-bit FEAL subkeys.
fn key_schedule(key: &[u8; 8]) -> [u16; 16] {
    let kl = u32::from_be_bytes([key[0], key[1], key[2], key[3]]);
    let kr = u32::from_be_bytes([key[4], key[5], key[6], key[7]]);

    let mut d: u32 = 0;
    let mut a: u32 = kl;
    let mut b: u32 = kr;

    let mut sk = [0u16; 16];
    for r in 0..8 {
        let out = fk(a, b ^ d);
        sk[2 * r] = (out >> 16) as u16;
        sk[2 * r + 1] = out as u16;
        // Rotate state: (D, A, B) ← (A, B, out)
        d = a;
        a = b;
        b = out;
    }
    sk
}

// ── FEAL-8 cipher ────────────────────────────────────────────────────

/// FEAL-8 keyed cipher.  64-bit block, 64-bit key, 8 Feistel rounds.
#[derive(Clone, Debug)]
pub struct Feal8 {
    subkeys: [u16; 16],
}

impl Feal8 {
    pub fn new(key: &[u8; 8]) -> Self {
        Self {
            subkeys: key_schedule(key),
        }
    }

    /// Encrypt one 64-bit block in place.
    pub fn encrypt_block(&self, block: &mut [u8; 8]) {
        let mut l = u32::from_be_bytes([block[0], block[1], block[2], block[3]]);
        let mut r = u32::from_be_bytes([block[4], block[5], block[6], block[7]]);

        // Pre-whitening (K8 K9 K10 K11).
        let w_pre_l = ((self.subkeys[8] as u32) << 16) | (self.subkeys[9] as u32);
        let w_pre_r = ((self.subkeys[10] as u32) << 16) | (self.subkeys[11] as u32);
        l ^= w_pre_l;
        r ^= w_pre_r;

        // XOR right with left.
        r ^= l;

        // 8 Feistel rounds: (L, R) ← (R, L ⊕ f(R, K_i)).
        for i in 0..8 {
            let new_r = l ^ f(r, self.subkeys[i]);
            l = r;
            r = new_r;
        }

        // FEAL omits the last swap, so the output halves are (R, L) in
        // the spec's notation — i.e. swap our local (l, r) back.
        std::mem::swap(&mut l, &mut r);

        // XOR right with left (post-mix).
        r ^= l;

        // Post-whitening (K12 K13 K14 K15).
        let w_post_l = ((self.subkeys[12] as u32) << 16) | (self.subkeys[13] as u32);
        let w_post_r = ((self.subkeys[14] as u32) << 16) | (self.subkeys[15] as u32);
        l ^= w_post_l;
        r ^= w_post_r;

        block[0..4].copy_from_slice(&l.to_be_bytes());
        block[4..8].copy_from_slice(&r.to_be_bytes());
    }

    /// Decrypt one 64-bit block in place.
    pub fn decrypt_block(&self, block: &mut [u8; 8]) {
        let mut l = u32::from_be_bytes([block[0], block[1], block[2], block[3]]);
        let mut r = u32::from_be_bytes([block[4], block[5], block[6], block[7]]);

        // Undo post-whitening.
        let w_post_l = ((self.subkeys[12] as u32) << 16) | (self.subkeys[13] as u32);
        let w_post_r = ((self.subkeys[14] as u32) << 16) | (self.subkeys[15] as u32);
        l ^= w_post_l;
        r ^= w_post_r;

        // Undo XOR right-with-left.
        r ^= l;

        // Undo the "no last swap" by swapping back.
        std::mem::swap(&mut l, &mut r);

        // Reverse the 8 Feistel rounds.
        for i in (0..8).rev() {
            // Forward: l_new = r_old, r_new = l_old ⊕ f(r_old, K_i)
            // Reverse: r_old = l_new, l_old = r_new ⊕ f(r_old, K_i) = r_new ⊕ f(l_new, K_i)
            let prev_l = r ^ f(l, self.subkeys[i]);
            r = l;
            l = prev_l;
        }

        // Undo initial XOR right-with-left.
        r ^= l;

        // Undo pre-whitening.
        let w_pre_l = ((self.subkeys[8] as u32) << 16) | (self.subkeys[9] as u32);
        let w_pre_r = ((self.subkeys[10] as u32) << 16) | (self.subkeys[11] as u32);
        l ^= w_pre_l;
        r ^= w_pre_r;

        block[0..4].copy_from_slice(&l.to_be_bytes());
        block[4..8].copy_from_slice(&r.to_be_bytes());
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

    /// Round-trip on a handful of arbitrary blocks.
    #[test]
    fn feal8_round_trip() {
        let key = *b"abcdefgh";
        let c = Feal8::new(&key);
        for seed in 0u8..32 {
            let mut block = [seed; 8];
            for (i, b) in block.iter_mut().enumerate() {
                *b = b.wrapping_mul(31).wrapping_add(i as u8);
            }
            let orig = block;
            c.encrypt_block(&mut block);
            assert_ne!(block, orig);
            c.decrypt_block(&mut block);
            assert_eq!(block, orig, "round-trip failed for seed {}", seed);
        }
    }

    /// FEAL-8 test vector from the Cryptol formal-verification
    /// implementation in <https://github.com/septract/saw-ai/blob/main/experiments/feal/feal8.cry>
    /// (which derives the spec directly from Miyaguchi 1990):
    ///
    /// Key = 0123456789abcdef, PT = 0000000000000000,
    /// CT  = ceef2c86f2490752.
    ///
    /// The subkeys this implementation should produce are
    /// `[df3b, ca36, f17c, 1aec, 45a5, b9c7, 26eb, ad25,
    ///   8b2a, ecb7, ac50, 9d4c, 22cd, 479b, a8d5, 0cb5]`.
    ///
    /// Note: several online tutorials cite "cee43e51ebdc6c46" for the
    /// same input — that value belongs to a different FEAL variant
    /// (likely FEAL-NX or a byte-ordering twist).  The Cryptol value
    /// is the one consistent with the Miyaguchi 1990 paper.
    #[test]
    fn feal8_known_vector() {
        let mut key = [0u8; 8];
        key.copy_from_slice(&h("0123456789abcdef"));
        let mut block = [0u8; 8];
        let expected = h("ceef2c86f2490752");

        let c = Feal8::new(&key);
        c.encrypt_block(&mut block);
        assert_eq!(&block[..], &expected[..], "FEAL-8 encrypt mismatch");

        c.decrypt_block(&mut block);
        assert_eq!(block, [0u8; 8], "FEAL-8 decrypt mismatch");
    }

    /// Verify the key-schedule output against the Cryptol reference
    /// subkeys for `key = 0123456789abcdef`.
    #[test]
    fn feal8_key_schedule_reference() {
        let mut key = [0u8; 8];
        key.copy_from_slice(&h("0123456789abcdef"));
        let sk = super::key_schedule(&key);
        let expected: [u16; 16] = [
            0xdf3b, 0xca36, 0xf17c, 0x1aec, 0x45a5, 0xb9c7, 0x26eb, 0xad25, 0x8b2a, 0xecb7, 0xac50,
            0x9d4c, 0x22cd, 0x479b, 0xa8d5, 0x0cb5,
        ];
        assert_eq!(sk, expected);
    }
}
