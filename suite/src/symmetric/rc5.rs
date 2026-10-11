//! **RC5** — Rivest Cipher 5 (Ron Rivest, 1994).
//!
//! Variable-parameter ARX block cipher.  The "size triplet"
//! `(word_bits, rounds, key_bytes)` is part of the algorithm name:
//! we implement the canonical **RC5-32/12/16** (32-bit words, 12
//! rounds, 16-byte key, **64-bit block**).
//!
//! ## Algorithm
//!
//! Key expansion produces `2*(rounds + 1) = 26` 32-bit subkeys
//! `S[0..26]` from the user key, via a mixing schedule using the
//! magic constants `P32 = 0xB7E15163` and `Q32 = 0x9E3779B9`.
//!
//! Encryption (after split into `A, B`):
//!
//! ```text
//!     A = A + S[0]
//!     B = B + S[1]
//!     for i = 1..=rounds:
//!         A = ((A ⊕ B) <<<_B) + S[2i]
//!         B = ((B ⊕ A) <<<_A) + S[2i+1]
//! ```
//!
//! `<<<_n` denotes left-rotation by `n mod word_bits` bits — the
//! data-dependent rotation that's RC5's signature feature.
//!
//! ## Status
//!
//! RC5 was the subject of the RSA Labs RC5 cryptanalysis contest;
//! reduced-round variants fall to differential and linear
//! cryptanalysis (Biryukov-Kushilevitz 1998, Kaliski-Yin 1995).
//! Full RC5-32/12/16 is still considered secure but **deprecated
//! in favour of AES** for new designs.  Patents have expired (US
//! 5,724,428 expired 2015).
//!
//! ## References
//!
//! - **R. Rivest**, *The RC5 Encryption Algorithm*, FSE 1994.
//! - **B. Kaliski, Y. L. Yin**, *On Differential and Linear
//!   Cryptanalysis of the RC5 Encryption Algorithm*, CRYPTO 1995.

const W: usize = 32; // word bits
const R: usize = 12; // rounds
const B: usize = 16; // key bytes
const T: usize = 2 * (R + 1); // 26 subkeys
const C: usize = B / 4; // 4 u32 words in the user key

/// RC5 "magic" constants — odd integers nearest to `e − 2` and
/// `φ − 1` scaled to fit in a 32-bit word.  Defined in the RC5 paper.
const P32: u32 = 0xB7E15163;
const Q32: u32 = 0x9E3779B9;

/// RC5-32/12/16 context with the round-key array pre-expanded.
pub struct Rc5 {
    s: [u32; T],
}

impl Rc5 {
    /// New RC5 with the given 16-byte key.  Runs the standard RC5
    /// key schedule.
    pub fn new(key: &[u8; 16]) -> Self {
        // Step 1: load key into `L` (4 u32 words, little-endian).
        let mut l = [0u32; C];
        for i in 0..B {
            l[i / 4] |= (key[i] as u32) << (8 * (i % 4));
        }
        // Step 2: initialise `S` with P32 + i·Q32.
        let mut s = [0u32; T];
        s[0] = P32;
        for i in 1..T {
            s[i] = s[i - 1].wrapping_add(Q32);
        }
        // Step 3: 3·max(T, C) = 78 mixing rounds.
        let mut a: u32 = 0;
        let mut b: u32 = 0;
        let mut i = 0usize;
        let mut j = 0usize;
        let mix_iters = 3 * T.max(C);
        for _ in 0..mix_iters {
            s[i] = s[i].wrapping_add(a).wrapping_add(b).rotate_left(3);
            a = s[i];
            let shift = (a.wrapping_add(b)) & ((W as u32) - 1);
            l[j] = l[j].wrapping_add(a).wrapping_add(b).rotate_left(shift);
            b = l[j];
            i = (i + 1) % T;
            j = (j + 1) % C;
        }
        Rc5 { s }
    }

    /// Encrypt one 8-byte block in place.
    pub fn encrypt_block(&self, block: &mut [u8; 8]) {
        let mut a = u32::from_le_bytes([block[0], block[1], block[2], block[3]]);
        let mut b = u32::from_le_bytes([block[4], block[5], block[6], block[7]]);
        a = a.wrapping_add(self.s[0]);
        b = b.wrapping_add(self.s[1]);
        for i in 1..=R {
            a = (a ^ b)
                .rotate_left(b & ((W as u32) - 1))
                .wrapping_add(self.s[2 * i]);
            b = (b ^ a)
                .rotate_left(a & ((W as u32) - 1))
                .wrapping_add(self.s[2 * i + 1]);
        }
        block[0..4].copy_from_slice(&a.to_le_bytes());
        block[4..8].copy_from_slice(&b.to_le_bytes());
    }

    /// Decrypt one 8-byte block in place.
    pub fn decrypt_block(&self, block: &mut [u8; 8]) {
        let mut a = u32::from_le_bytes([block[0], block[1], block[2], block[3]]);
        let mut b = u32::from_le_bytes([block[4], block[5], block[6], block[7]]);
        for i in (1..=R).rev() {
            b = b
                .wrapping_sub(self.s[2 * i + 1])
                .rotate_right(a & ((W as u32) - 1))
                ^ a;
            a = a
                .wrapping_sub(self.s[2 * i])
                .rotate_right(b & ((W as u32) - 1))
                ^ b;
        }
        b = b.wrapping_sub(self.s[1]);
        a = a.wrapping_sub(self.s[0]);
        block[0..4].copy_from_slice(&a.to_le_bytes());
        block[4..8].copy_from_slice(&b.to_le_bytes());
    }
}

/// Free-function RC5 encrypt.
pub fn encrypt_block(key: &[u8; 16], block: &[u8; 8]) -> [u8; 8] {
    let rc = Rc5::new(key);
    let mut out = *block;
    rc.encrypt_block(&mut out);
    out
}

/// Free-function RC5 decrypt.
pub fn decrypt_block(key: &[u8; 16], block: &[u8; 8]) -> [u8; 8] {
    let rc = Rc5::new(key);
    let mut out = *block;
    rc.decrypt_block(&mut out);
    out
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

    /// **Rivest 1994 test vector** for RC5-32/12/16:
    /// Key = 91 5F 46 19 BE 41 B2 51 63 55 A5 01 10 A9 CE 91
    /// PT  = 21 A5 DB EE 15 4B 8F 6D
    /// CT  = F7 C0 13 AC 5B 2B 89 52
    #[test]
    fn rc5_rivest_vector_1() {
        let mut key = [0u8; 16];
        key.copy_from_slice(&h("915F4619BE41B2516355A50110A9CE91"));
        let mut pt = [0u8; 8];
        pt.copy_from_slice(&h("21A5DBEE154B8F6D"));
        let expected = h("F7C013AC5B2B8952");
        let ct = encrypt_block(&key, &pt);
        assert_eq!(&ct[..], &expected[..]);
        let recovered = decrypt_block(&key, &ct);
        assert_eq!(&recovered[..], &pt[..]);
    }

    /// **Rivest 1994 vector #2**:
    /// Key = 78 33 48 E7 5A EB 0F 2F D7 B1 69 BB 8D C1 67 87
    /// PT  = F7 C0 13 AC 5B 2B 89 52
    /// CT  = 2F 42 B3 B7 03 69 FC 92
    #[test]
    fn rc5_rivest_vector_2() {
        let mut key = [0u8; 16];
        key.copy_from_slice(&h("783348E75AEB0F2FD7B169BB8DC16787"));
        let mut pt = [0u8; 8];
        pt.copy_from_slice(&h("F7C013AC5B2B8952"));
        let expected = h("2F42B3B70369FC92");
        let ct = encrypt_block(&key, &pt);
        assert_eq!(&ct[..], &expected[..]);
        let recovered = decrypt_block(&key, &ct);
        assert_eq!(&recovered[..], &pt[..]);
    }

    /// **Round-trip** on arbitrary plaintext.
    #[test]
    fn rc5_round_trip() {
        let key = [0xAAu8; 16];
        for v in 0u64..1024 {
            let pt = v.to_le_bytes();
            let ct = encrypt_block(&key, &pt);
            let recovered = decrypt_block(&key, &ct);
            assert_eq!(recovered, pt);
        }
    }

    /// `Rc5` struct version matches the free-function version.
    #[test]
    fn rc5_struct_matches_free_function() {
        let key = [0x42u8; 16];
        let pt = [0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF];
        let ct_free = encrypt_block(&key, &pt);
        let rc = Rc5::new(&key);
        let mut block = pt;
        rc.encrypt_block(&mut block);
        assert_eq!(block, ct_free);
        rc.decrypt_block(&mut block);
        assert_eq!(block, pt);
    }
}
