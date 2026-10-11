//! **RC6** — Rivest et al. (1998), AES competition finalist.
//!
//! RC6 generalises [`super::rc5`] from a two-register Feistel-like ARX
//! cipher to a four-register one, doubling the block size to 128 bits
//! and adding a quadratic mixing function `f(x) = x·(2x+1) mod 2^w`
//! whose top bits (after rotation) drive the data-dependent rotations
//! that are RC6's signature.  The "size triplet" is **RC6-32/20/b**:
//! 32-bit words, 20 rounds, key size `b` ∈ {16, 24, 32} bytes
//! (i.e. 128, 192 or 256 bits — the three sizes the AES submission was
//! specified for).
//!
//! ## Algorithm
//!
//! Key expansion produces `t = 2·r + 4 = 44` 32-bit subkeys
//! `S[0..44]` from the user key, via the same mixing schedule as RC5
//! with constants `P32 = 0xB7E15163` and `Q32 = 0x9E3779B9` and
//! `3·max(t, c)` mixing iterations.
//!
//! Encryption on the four-register state `(A, B, C, D)` (each word
//! loaded little-endian):
//!
//! ```text
//!     B = B + S[0]
//!     D = D + S[1]
//!     for i = 1..=r:
//!         t = ((B · (2B + 1)) <<<  5)
//!         u = ((D · (2D + 1)) <<<  5)
//!         A = ((A ⊕ t) <<< u) + S[2i]
//!         C = ((C ⊕ u) <<< t) + S[2i+1]
//!         (A, B, C, D) = (B, C, D, A)
//!     A = A + S[2r+2]
//!     C = C + S[2r+3]
//! ```
//!
//! The fixed `<<< 5` rotation on `t, u` is `lg w` (= `log2(32)`).  The
//! variable rotation amount is taken mod `w`, i.e. only the low 5 bits
//! of the rotating word are used.
//!
//! ## Status
//!
//! Patents (Rivest et al., RSA Security) have expired.  No practical
//! break on the full 20-round cipher is known, but as with all the
//! AES-runner-up designs, **prefer AES-128/256 for new work**.
//!
//! ## References
//!
//! - **R. Rivest, M. Robshaw, R. Sidney, Y. L. Yin**,
//!   *The RC6 Block Cipher* (v1.1), 20 August 1998.  Submitted to
//!   NIST's AES competition.  Test vectors in Appendix B.

// ── Parameters ───────────────────────────────────────────────────────

/// Word size in bits.
const W: u32 = 32;
/// Rotation amount for `t, u` — `lg w` where `w = 32`.
const LG_W: u32 = 5;
/// Number of rounds (RC6-32/20/b).
const R: usize = 20;
/// Number of round-key words: `2·r + 4 = 44` (indices `S[0..2r+3]`).
const T_WORDS: usize = 2 * R + 4;

/// RC6 "magic" constants — derived from `e` and `φ` (golden ratio),
/// identical to RC5's `P32`/`Q32`.
const P32: u32 = 0xB7E15163;
const Q32: u32 = 0x9E3779B9;

/// RC6-32/20/b context with the round-key array pre-expanded.
#[derive(Clone, Debug)]
pub struct Rc6 {
    s: [u32; T_WORDS],
}

impl Rc6 {
    /// New RC6 context from a 16, 24, or 32 byte key.  Runs the
    /// standard RC6 key schedule (identical mixing loop to RC5 but
    /// producing `2·(r+1) + 4` subkeys).
    pub fn new(key: &[u8]) -> Result<Self, &'static str> {
        if !matches!(key.len(), 16 | 24 | 32) {
            return Err("RC6 key must be 16, 24, or 32 bytes (128/192/256-bit)");
        }
        // c = number of 32-bit words in the user key; spec also handles
        // b = 0 with c = 1, but we reject that above.
        let c = key.len() / 4;

        // Step 1: load key into `L[0..c]` little-endian.
        let mut l = [0u32; 8]; // max c = 8 (256-bit key)
        for i in 0..key.len() {
            l[i / 4] |= (key[i] as u32) << (8 * (i % 4));
        }

        // Step 2: initialise `S` with P32 + i·Q32.
        let mut s = [0u32; T_WORDS];
        s[0] = P32;
        for i in 1..T_WORDS {
            s[i] = s[i - 1].wrapping_add(Q32);
        }

        // Step 3: 3·max(T_WORDS, c) mixing iterations.
        let mut a: u32 = 0;
        let mut b: u32 = 0;
        let mut ii = 0usize;
        let mut jj = 0usize;
        let mix_iters = 3 * T_WORDS.max(c);
        for _ in 0..mix_iters {
            s[ii] = s[ii].wrapping_add(a).wrapping_add(b).rotate_left(3);
            a = s[ii];
            let shift = a.wrapping_add(b) & (W - 1);
            l[jj] = l[jj].wrapping_add(a).wrapping_add(b).rotate_left(shift);
            b = l[jj];
            ii = (ii + 1) % T_WORDS;
            jj = (jj + 1) % c;
        }
        Ok(Rc6 { s })
    }

    /// Encrypt one 16-byte block in place.
    pub fn encrypt_block(&self, block: &mut [u8; 16]) {
        let mut a = u32::from_le_bytes(block[0..4].try_into().unwrap());
        let mut b = u32::from_le_bytes(block[4..8].try_into().unwrap());
        let mut c = u32::from_le_bytes(block[8..12].try_into().unwrap());
        let mut d = u32::from_le_bytes(block[12..16].try_into().unwrap());

        b = b.wrapping_add(self.s[0]);
        d = d.wrapping_add(self.s[1]);
        for i in 1..=R {
            // f(x) = x·(2x+1) mod 2^32, then <<< lg w.  The quadratic
            // is the source of RC6's confusion: it spreads any single-
            // bit difference in `B` (resp. `D`) over all higher bit
            // positions before driving the data-dependent rotation.
            let t = b
                .wrapping_mul(b.wrapping_mul(2).wrapping_add(1))
                .rotate_left(LG_W);
            let u = d
                .wrapping_mul(d.wrapping_mul(2).wrapping_add(1))
                .rotate_left(LG_W);
            a = (a ^ t).rotate_left(u & (W - 1)).wrapping_add(self.s[2 * i]);
            c = (c ^ u)
                .rotate_left(t & (W - 1))
                .wrapping_add(self.s[2 * i + 1]);
            // (A, B, C, D) ← (B, C, D, A)
            let na = b;
            let nb = c;
            let nc = d;
            let nd = a;
            a = na;
            b = nb;
            c = nc;
            d = nd;
        }
        a = a.wrapping_add(self.s[2 * R + 2]);
        c = c.wrapping_add(self.s[2 * R + 3]);

        block[0..4].copy_from_slice(&a.to_le_bytes());
        block[4..8].copy_from_slice(&b.to_le_bytes());
        block[8..12].copy_from_slice(&c.to_le_bytes());
        block[12..16].copy_from_slice(&d.to_le_bytes());
    }

    /// Decrypt one 16-byte block in place.  Inverse of `encrypt_block`.
    pub fn decrypt_block(&self, block: &mut [u8; 16]) {
        let mut a = u32::from_le_bytes(block[0..4].try_into().unwrap());
        let mut b = u32::from_le_bytes(block[4..8].try_into().unwrap());
        let mut c = u32::from_le_bytes(block[8..12].try_into().unwrap());
        let mut d = u32::from_le_bytes(block[12..16].try_into().unwrap());

        c = c.wrapping_sub(self.s[2 * R + 3]);
        a = a.wrapping_sub(self.s[2 * R + 2]);
        for i in (1..=R).rev() {
            // Undo the rotate-by-1: (B, C, D, A) ← (A, B, C, D)
            let na = d;
            let nb = a;
            let nc = b;
            let nd = c;
            a = na;
            b = nb;
            c = nc;
            d = nd;
            let t = b
                .wrapping_mul(b.wrapping_mul(2).wrapping_add(1))
                .rotate_left(LG_W);
            let u = d
                .wrapping_mul(d.wrapping_mul(2).wrapping_add(1))
                .rotate_left(LG_W);
            c = c.wrapping_sub(self.s[2 * i + 1]).rotate_right(t & (W - 1)) ^ u;
            a = a.wrapping_sub(self.s[2 * i]).rotate_right(u & (W - 1)) ^ t;
        }
        d = d.wrapping_sub(self.s[1]);
        b = b.wrapping_sub(self.s[0]);

        block[0..4].copy_from_slice(&a.to_le_bytes());
        block[4..8].copy_from_slice(&b.to_le_bytes());
        block[8..12].copy_from_slice(&c.to_le_bytes());
        block[12..16].copy_from_slice(&d.to_le_bytes());
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

    fn hex16(s: &str) -> [u8; 16] {
        let v = h(s);
        let mut a = [0u8; 16];
        a.copy_from_slice(&v);
        a
    }

    /// **Rivest et al. 1998, RC6 paper Appendix B vector 1**:
    /// 128-bit zero key, 128-bit zero plaintext.
    #[test]
    fn rc6_paper_vector_128_zero() {
        let key = [0u8; 16];
        let cipher = Rc6::new(&key).unwrap();
        let mut block = [0u8; 16];
        cipher.encrypt_block(&mut block);
        assert_eq!(block, hex16("8fc3a53656b1f778c129df4e9848a41e"));
        cipher.decrypt_block(&mut block);
        assert_eq!(block, [0u8; 16]);
    }

    /// **Rivest et al. 1998, RC6 paper Appendix B vector 2**:
    /// 128-bit key, structured plaintext.
    #[test]
    fn rc6_paper_vector_128_structured() {
        // PT  = 02132435465768798a9bacbdcedfe0f1
        // Key = 0123456789abcdef0112233445566778
        // CT  = 524e192f4715c6231f51f6367ea43f18
        let key = hex16("0123456789abcdef0112233445566778");
        let mut block = hex16("02132435465768798a9bacbdcedfe0f1");
        let pt = block;
        let cipher = Rc6::new(&key).unwrap();
        cipher.encrypt_block(&mut block);
        assert_eq!(block, hex16("524e192f4715c6231f51f6367ea43f18"));
        cipher.decrypt_block(&mut block);
        assert_eq!(block, pt);
    }

    /// **Rivest et al. 1998, RC6 paper Appendix B vector 3** (192-bit key):
    /// Key = 0123456789abcdef0112233445566778 899aabbccddeeff0
    /// PT  = 02132435465768798a9bacbdcedfe0f1
    /// CT  = 688329d019e505041e52e92af95291d4
    #[test]
    fn rc6_paper_vector_192() {
        let key = h("0123456789abcdef0112233445566778 899aabbccddeeff0");
        let mut block = hex16("02132435465768798a9bacbdcedfe0f1");
        let pt = block;
        let cipher = Rc6::new(&key).unwrap();
        cipher.encrypt_block(&mut block);
        assert_eq!(block, hex16("688329d019e505041e52e92af95291d4"));
        cipher.decrypt_block(&mut block);
        assert_eq!(block, pt);
    }

    /// **Rivest et al. 1998, RC6 paper Appendix B vector 4** (256-bit key):
    /// Key = 0123456789abcdef0112233445566778 899aabbccddeeff01032547698badcfe
    /// PT  = 02132435465768798a9bacbdcedfe0f1
    /// CT  = c8241816f0d7e48920ad16a1674e5d48
    #[test]
    fn rc6_paper_vector_256() {
        let key = h("0123456789abcdef0112233445566778 899aabbccddeeff01032547698badcfe");
        let mut block = hex16("02132435465768798a9bacbdcedfe0f1");
        let pt = block;
        let cipher = Rc6::new(&key).unwrap();
        cipher.encrypt_block(&mut block);
        assert_eq!(block, hex16("c8241816f0d7e48920ad16a1674e5d48"));
        cipher.decrypt_block(&mut block);
        assert_eq!(block, pt);
    }

    /// **Round-trip** across many random keys/plaintexts at every
    /// supported key size — guards against off-by-one mistakes in the
    /// rotation rule of the inverse round.
    #[test]
    fn rc6_round_trip() {
        let mut seed: u64 = 0xdead_beef_cafe_babe;
        for &klen in &[16usize, 24, 32] {
            for _ in 0..16 {
                let mut key = vec![0u8; klen];
                let mut pt = [0u8; 16];
                for b in key.iter_mut() {
                    seed = seed
                        .wrapping_mul(6364136223846793005)
                        .wrapping_add(1442695040888963407);
                    *b = (seed >> 56) as u8;
                }
                for b in pt.iter_mut() {
                    seed = seed
                        .wrapping_mul(6364136223846793005)
                        .wrapping_add(1442695040888963407);
                    *b = (seed >> 56) as u8;
                }
                let cipher = Rc6::new(&key).unwrap();
                let mut block = pt;
                cipher.encrypt_block(&mut block);
                assert_ne!(block, pt, "zero output cycle");
                cipher.decrypt_block(&mut block);
                assert_eq!(block, pt);
            }
        }
    }

    /// Invalid key lengths are rejected.
    #[test]
    fn rc6_rejects_bad_key_length() {
        assert!(Rc6::new(&[0u8; 0]).is_err());
        assert!(Rc6::new(&[0u8; 8]).is_err());
        assert!(Rc6::new(&[0u8; 15]).is_err());
        assert!(Rc6::new(&[0u8; 20]).is_err());
        assert!(Rc6::new(&[0u8; 33]).is_err());
        assert!(Rc6::new(&[0u8; 16]).is_ok());
        assert!(Rc6::new(&[0u8; 24]).is_ok());
        assert!(Rc6::new(&[0u8; 32]).is_ok());
    }

    /// Single-bit avalanche sanity: a one-bit change in plaintext
    /// should flip roughly half the ciphertext bits.
    #[test]
    fn rc6_avalanche() {
        let key = [0x55u8; 16];
        let cipher = Rc6::new(&key).unwrap();
        let mut b1 = [0u8; 16];
        let mut b2 = [0u8; 16];
        b2[0] = 1;
        cipher.encrypt_block(&mut b1);
        cipher.encrypt_block(&mut b2);
        let differing: u32 = b1
            .iter()
            .zip(b2.iter())
            .map(|(a, b)| (a ^ b).count_ones())
            .sum();
        assert!(differing >= 40, "weak avalanche: {} bits", differing);
    }
}
