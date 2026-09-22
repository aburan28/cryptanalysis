//! **IDEA — International Data Encryption Algorithm** (Lai & Massey,
//! 1991).
//!
//! 64-bit block, 128-bit key, 8.5 rounds.  Notable as the symmetric
//! cipher used by **PGP 2.x** in the 1990s and a poster child for
//! "mixing operations from incompatible algebraic groups": every
//! round combines XOR (⊕), addition mod 2^16 (⊞), and multiplication
//! mod the prime 2^16 + 1 (⊙, with the convention `0 ↔ 2^16`).
//!
//! ## Security note
//!
//! IDEA is **not catastrophically broken** but has small weak-key
//! classes (Daemen, Govaerts, Vandewalle 1993; Biham et al. 2012 give
//! a 6-round attack), the patent expired in 2012, and AES has
//! displaced it everywhere.  Kept here for studying the mixed-group
//! design (precursor to PRESENT, FOX/IDEA-NXT) and for legacy PGP
//! interop.
//!
//! ## Algorithm
//!
//! The 128-bit key is split into eight 16-bit words `Z_1…Z_8`.  The
//! schedule then cyclically rotates the *key* by 25 bits and extracts
//! another eight subkeys, repeating until **52 subkeys** are
//! generated (6 per full round × 8 + 4 for the half-round).
//!
//! Each full round on the four-word state `(X_1, X_2, X_3, X_4)`
//! computes:
//!
//! ```text
//!   Y_1 = X_1 ⊙ Z_a       Y_3 = X_3 ⊞ Z_c
//!   Y_2 = X_2 ⊞ Z_b       Y_4 = X_4 ⊙ Z_d
//!   t   = Z_e ⊙ (Y_1 ⊕ Y_3)
//!   u   = Z_f ⊙ (t ⊞ (Y_2 ⊕ Y_4))
//!   v   = t ⊞ u
//!   (X_1', X_2', X_3', X_4') = (Y_1 ⊕ u, Y_3 ⊕ u, Y_2 ⊕ v, Y_4 ⊕ v)
//! ```
//!
//! After 8 such rounds, an output transformation (the "half round")
//! applies four more subkeys without the MA-structure.  The middle
//! two words are swapped inside each round so the final output order
//! matches the input order — see `encrypt_block` for the exact dance.
//!
//! ## References
//!
//! - X. Lai, *On the Design and Security of Block Ciphers*, ETH Diss.
//!   No. 9752 (1992).
//! - **B. Schneier**, *Applied Cryptography*, 2nd ed., §13.9.
//! - RFC 3058 (IDEA in CMS) — informational, with test vectors.

// ── ⊙ : multiplication mod 2^16 + 1 with `0 ↔ 2^16` ─────────────────

/// `a ⊙ b` per IDEA: multiply mod the prime 65537, treating any
/// zero operand as 2^16.  Result is reduced back into the 16-bit
/// range (with 2^16 ↔ 0 again).
#[inline]
fn mul(a: u16, b: u16) -> u16 {
    const P: u32 = 0x10001; // 65537
    let a = a as u32;
    let b = b as u32;
    let prod = if a == 0 {
        // a = 2^16; (2^16 · b) mod (2^16 + 1) = ((2^16 + 1)·b − b) mod p = −b
        P - b
    } else if b == 0 {
        P - a
    } else {
        // r ∈ [1, p−1]; map p back to 0 isn't needed (product can't be p)
        (a * b) % P
    };
    // Map 2^16 back to 0 for storage.
    (prod & 0xffff) as u16
}

/// Multiplicative inverse mod 2^16 + 1 (with the same `0 ↔ 2^16`
/// convention).  Computed via Fermat: `a^(p − 2) mod p` since 65537
/// is prime.
fn mul_inv(a: u16) -> u16 {
    if a <= 1 {
        // 0 (≡ 2^16) and 1 are their own inverses under this convention.
        return a;
    }
    const P: u64 = 0x10001;
    let mut base = a as u64;
    let mut exp: u64 = P - 2; // Fermat: a^(p-2) ≡ a^{-1} (mod p)
    let mut result: u64 = 1;
    while exp > 0 {
        if exp & 1 == 1 {
            result = (result * base) % P;
        }
        base = (base * base) % P;
        exp >>= 1;
    }
    (result & 0xffff) as u16
}

/// Additive inverse mod 2^16.
#[inline]
fn add_inv(a: u16) -> u16 {
    0u16.wrapping_sub(a)
}

// ── Key schedule ────────────────────────────────────────────────────

/// Expand the 128-bit master key into 52 16-bit subkeys.  At each
/// "extraction step" we grab eight subkeys from the key register,
/// then rotate the 128-bit register left by 25 bits and repeat.
fn expand_encryption_key(key: &[u8; 16]) -> [u16; 52] {
    // Hold the 128-bit key as a u128 for easy 25-bit rotation.
    let mut k: u128 = 0;
    for &b in key.iter() {
        k = (k << 8) | (b as u128);
    }
    let mut out = [0u16; 52];
    let mut idx = 0;
    while idx < 52 {
        // Extract up to 8 subkeys from the top of the register.
        let take = (52 - idx).min(8);
        for i in 0..take {
            out[idx + i] = ((k >> (112 - 16 * i)) & 0xffff) as u16;
        }
        idx += take;
        if idx < 52 {
            // Rotate left by 25 bits within 128 bits.
            // u128 is already 128 bits; the shifts saturate exactly.
            k = k.rotate_left(25);
        }
    }
    out
}

/// Derive the 52 decryption subkeys from the encryption subkeys.
/// The structure inverts so neatly that decryption is the *same*
/// algorithm with a permuted schedule:
///
/// - Output transformation subkeys become multiplicative / additive
///   inverses, in reverse order.
/// - The MA-structure subkeys (`Z_e`, `Z_f`) are reused as-is but
///   pulled from the previous round.
fn derive_decryption_keys(enc: &[u16; 52]) -> [u16; 52] {
    let mut dk = [0u16; 52];

    // Decryption round 1: input transform inverts encryption's output
    // transform (no inner swap), MA-subkeys come from encryption round 8.
    dk[0] = mul_inv(enc[48]);
    dk[1] = add_inv(enc[49]);
    dk[2] = add_inv(enc[50]);
    dk[3] = mul_inv(enc[51]);
    dk[4] = enc[46];
    dk[5] = enc[47];

    // Decryption rounds 2..=8: inverses of encryption round (10-r) input
    // transform with the two additive-inverse subkeys swapped (because
    // the per-round x2/x3 implicit swap shifts which subkey acts on
    // which word), MA-subkeys from encryption round (9-r).
    for r in 2..=8 {
        let dst = 6 * (r - 1);
        let enc_input = 6 * (9 - r); // start of input-transform subkeys
        let enc_ma = 6 * (8 - r) + 4; // start of MA subkeys
        dk[dst] = mul_inv(enc[enc_input]);
        dk[dst + 1] = add_inv(enc[enc_input + 2]); // swapped
        dk[dst + 2] = add_inv(enc[enc_input + 1]); // swapped
        dk[dst + 3] = mul_inv(enc[enc_input + 3]);
        dk[dst + 4] = enc[enc_ma];
        dk[dst + 5] = enc[enc_ma + 1];
    }

    // Decryption output transform: inverses of encryption round 1's
    // input transform, no swap.
    dk[48] = mul_inv(enc[0]);
    dk[49] = add_inv(enc[1]);
    dk[50] = add_inv(enc[2]);
    dk[51] = mul_inv(enc[3]);

    dk
}

// ── Core encryption (parameterised over subkey schedule) ────────────

fn idea_crypt(block: &mut [u8; 8], k: &[u16; 52]) {
    let mut x1 = u16::from_be_bytes([block[0], block[1]]);
    let mut x2 = u16::from_be_bytes([block[2], block[3]]);
    let mut x3 = u16::from_be_bytes([block[4], block[5]]);
    let mut x4 = u16::from_be_bytes([block[6], block[7]]);

    for r in 0..8 {
        let off = 6 * r;
        // Round input transform.
        x1 = mul(x1, k[off]);
        x2 = x2.wrapping_add(k[off + 1]);
        x3 = x3.wrapping_add(k[off + 2]);
        x4 = mul(x4, k[off + 3]);

        // MA structure.
        let t = mul(k[off + 4], x1 ^ x3);
        let u = mul(k[off + 5], t.wrapping_add(x2 ^ x4));
        let v = t.wrapping_add(u);

        x1 ^= u;
        let new_x2 = x3 ^ u;
        let new_x3 = x2 ^ v;
        x2 = new_x2;
        x3 = new_x3;
        x4 ^= v;
    }
    // Undo the final round's implicit swap so the output transform
    // sees the natural (Y1⊕u, Y2⊕v, Y3⊕u, Y4⊕v) ordering.
    core::mem::swap(&mut x2, &mut x3);

    // Output transformation (half round).
    let y1 = mul(x1, k[48]);
    let y2 = x2.wrapping_add(k[49]);
    let y3 = x3.wrapping_add(k[50]);
    let y4 = mul(x4, k[51]);

    block[0..2].copy_from_slice(&y1.to_be_bytes());
    block[2..4].copy_from_slice(&y2.to_be_bytes());
    block[4..6].copy_from_slice(&y3.to_be_bytes());
    block[6..8].copy_from_slice(&y4.to_be_bytes());
}

// ── Cipher ──────────────────────────────────────────────────────────

#[derive(Clone, Debug)]
pub struct Idea {
    enc_keys: [u16; 52],
    dec_keys: [u16; 52],
}

impl Idea {
    /// Construct an IDEA cipher from a 128-bit key.
    pub fn new(key: &[u8; 16]) -> Self {
        let enc_keys = expand_encryption_key(key);
        let dec_keys = derive_decryption_keys(&enc_keys);
        Self { enc_keys, dec_keys }
    }

    /// Encrypt a single 64-bit block in place.  Words are big-endian
    /// 16-bit halves of the byte array.
    pub fn encrypt_block(&self, block: &mut [u8; 8]) {
        idea_crypt(block, &self.enc_keys);
    }

    /// Decrypt a single 64-bit block in place.
    pub fn decrypt_block(&self, block: &mut [u8; 8]) {
        idea_crypt(block, &self.dec_keys);
    }
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// **Canonical IDEA test vector** (PGP / Lai-Massey paper, also
    /// in `cryptography`'s historical test suite):
    /// Key = 00010002000300040005000600070008
    /// PT  = 0000000100020003
    /// CT  = 11fbed2b01986de5
    #[test]
    fn idea_canonical_vector() {
        let key: [u8; 16] = [
            0x00, 0x01, 0x00, 0x02, 0x00, 0x03, 0x00, 0x04, 0x00, 0x05, 0x00, 0x06, 0x00, 0x07,
            0x00, 0x08,
        ];
        let pt: [u8; 8] = [0x00, 0x00, 0x00, 0x01, 0x00, 0x02, 0x00, 0x03];
        let expected: [u8; 8] = [0x11, 0xfb, 0xed, 0x2b, 0x01, 0x98, 0x6d, 0xe5];

        let cipher = Idea::new(&key);
        let mut block = pt;
        cipher.encrypt_block(&mut block);
        assert_eq!(block, expected);
        cipher.decrypt_block(&mut block);
        assert_eq!(block, pt);
    }

    /// Round-trip with a non-trivial key/plaintext pair.
    #[test]
    fn idea_round_trip_arbitrary() {
        let key: [u8; 16] = [
            0xde, 0xad, 0xbe, 0xef, 0xfe, 0xed, 0xfa, 0xce, 0xca, 0xfe, 0xba, 0xbe, 0x12, 0x34,
            0x56, 0x78,
        ];
        let pt: [u8; 8] = [0x01, 0x23, 0x45, 0x67, 0x89, 0xab, 0xcd, 0xef];
        let cipher = Idea::new(&key);
        let mut block = pt;
        cipher.encrypt_block(&mut block);
        assert_ne!(block, pt);
        cipher.decrypt_block(&mut block);
        assert_eq!(block, pt);
    }

    /// Multiplication mod 2^16 + 1 with the `0 ↔ 2^16` convention.
    #[test]
    fn idea_mul_inverse() {
        for &x in &[0u16, 1, 2, 3, 0x5555, 0xabcd, 0xffff] {
            let inv = mul_inv(x);
            assert_eq!(mul(x, inv), 1, "x = {:#06x}, inv = {:#06x}", x, inv);
        }
    }

    /// Spec sanity: `mul(0, b) = -b mod (2^16 + 1)`.
    #[test]
    fn idea_mul_zero_means_2_to_16() {
        // 0 stands for 2^16.  2^16 · 1 mod (2^16 + 1) = 2^16, stored as 0.
        assert_eq!(mul(0, 1), 0);
        // 2^16 · 2 mod (2^16 + 1) = 2^17 mod 65537 = 2^17 - 65537 = 65535.
        assert_eq!(mul(0, 2), 0xffff);
    }
}
