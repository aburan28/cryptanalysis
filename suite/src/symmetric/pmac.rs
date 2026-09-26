//! **PMAC** — Parallelizable Message Authentication Code
//! (Rogaway 2002; the corrected PMAC1 from Rogaway 2005).
//!
//! PMAC is a CMAC alternative that's:
//! - **Parallelizable**: each block can be enciphered independently
//!   (CMAC is strictly serial).
//! - **Patent-free** since 2021 (Rogaway's patents expired).
//! - **Provably secure** with a clean tight bound, same standard
//!   PRF assumption as CMAC.
//!
//! ## Algorithm (PMAC1 over a 16-byte block cipher)
//!
//! ```text
//!     L      = E_K(0^128)
//!     L_i    = (x^{i+1} mod p) · L   for i ≥ 0   ; L_0 = 2·L, L_{i+1} = 2·L_i
//!     L_∞    = (x^{-1} mod p) · L
//!
//!     Partition M into M_1, …, M_m  (each n=128 bits except possibly M_m).
//!     If |M_m| = 128: Σ = M_m
//!     Else:           Σ = M_m || 10^{127 - |M_m|}
//!
//!     S = 0
//!     For i = 1 to m-1:
//!         S ⊕= E_K(M_i ⊕ L_{ntz(i)})
//!
//!     Tag = E_K( S ⊕ Σ ⊕ (L_∞ if |M_m|=128 else 0) )
//! ```
//!
//! where `ntz(i)` is the number of trailing zero bits of `i`.  The
//! empty-message case is treated as a single partial "block" of zero
//! length: `Σ = 0x80 00 … 00`, `S = 0`, `Tag = E_K(Σ)`.
//!
//! ## References
//!
//! - **P. Rogaway**, *Efficient Instantiations of Tweakable
//!   Blockciphers and Refinements to Modes OCB and PMAC*,
//!   ASIACRYPT 2004.
//! - libtomcrypt's `pmac_test.c` for the canonical AES-128 KAT.

use super::modes::cipher::BlockCipher128;

/// 16-byte authentication tag.
pub type PmacTag = [u8; 16];

const BLOCK: usize = 16;

/// `double(X)` in GF(2^128) with reduction `x^128 + x^7 + x^2 + x + 1`.
fn double(x: &[u8; 16]) -> [u8; 16] {
    let mut out = [0u8; 16];
    let mut carry = 0u8;
    for i in (0..16).rev() {
        let new_carry = x[i] >> 7;
        out[i] = (x[i] << 1) | carry;
        carry = new_carry;
    }
    if (x[0] >> 7) & 1 == 1 {
        out[15] ^= 0x87;
    }
    out
}

/// `divX(X)` — inverse of `double` in GF(2^128).  Right-shift by 1
/// with the polynomial reduction bit on the way in.
fn div_x(x: &[u8; 16]) -> [u8; 16] {
    // If the LSB is set, the original value was double(x') XOR 0x87 (the
    // polynomial reduction); after shifting right we OR back the top bit.
    let lsb = x[15] & 1;
    let mut v = *x;
    if lsb == 1 {
        v[15] ^= 0x87;
    }
    let mut out = [0u8; 16];
    let mut carry = 0u8;
    for i in 0..16 {
        let new_carry = v[i] & 1;
        out[i] = (v[i] >> 1) | (carry << 7);
        carry = new_carry;
    }
    if lsb == 1 {
        out[0] |= 0x80;
    }
    out
}

#[inline]
fn ntz(i: usize) -> usize {
    debug_assert!(i > 0);
    i.trailing_zeros() as usize
}

fn xor16_in_place(a: &mut [u8; 16], b: &[u8; 16]) {
    for i in 0..16 {
        a[i] ^= b[i];
    }
}

#[inline]
fn enc<C: BlockCipher128>(cipher: &C, block: &[u8; 16]) -> [u8; 16] {
    let mut b = *block;
    cipher.encrypt_block(&mut b);
    b
}

/// **PMAC1** generic over any 16-byte block cipher.
///
/// Tag length is fixed at 16 bytes; truncation is the caller's choice.
pub fn pmac<C: BlockCipher128>(cipher: &C, message: &[u8]) -> PmacTag {
    let l = enc(cipher, &[0u8; 16]);
    let l_inf = div_x(&l);

    // Precompute L_i = 2^i · L (Black-Rogaway 2002): L_0 = L, L_1 = 2L, L_2 = 4L, …
    let m_full = message.len() / BLOCK;
    let last_is_partial = message.is_empty() || !message.len().is_multiple_of(BLOCK);
    let needed_ntz = if m_full == 0 {
        0
    } else {
        usize::BITS as usize - m_full.leading_zeros() as usize
    };
    let mut l_table = Vec::with_capacity(needed_ntz + 1);
    let mut cur = l;
    l_table.push(cur); // L_0 = L
    for _ in 0..needed_ntz {
        cur = double(&cur);
        l_table.push(cur);
    }

    // Process the first (m_full - last_full_count) blocks where last_full_count
    // is 1 if the last block is a full block (no partial tail), else 0.
    // I.e., the loop covers blocks 1..=m_full when there's a partial tail, or
    // 1..(m_full - 1) when the last block is full.
    let loop_end = if last_is_partial { m_full } else { m_full - 1 };

    let mut offset = [0u8; 16];
    let mut s = [0u8; 16];
    for i in 1..=loop_end {
        xor16_in_place(&mut offset, &l_table[ntz(i)]);
        let mut blk = [0u8; 16];
        blk.copy_from_slice(&message[(i - 1) * BLOCK..i * BLOCK]);
        for j in 0..16 {
            blk[j] ^= offset[j];
        }
        let enc_blk = enc(cipher, &blk);
        xor16_in_place(&mut s, &enc_blk);
    }

    // Build Σ (sigma): the (possibly padded) last block, then combine.
    let mut sigma = [0u8; 16];
    if last_is_partial {
        // Pad M_m with 10*.
        let tail = &message[m_full * BLOCK..];
        sigma[..tail.len()].copy_from_slice(tail);
        sigma[tail.len()] = 0x80;
        // Tag input: S ⊕ Σ  (no L_∞ XOR).
        for j in 0..16 {
            sigma[j] ^= s[j];
        }
    } else {
        // Full last block: Σ = M_m, XOR with S and L_∞.
        sigma.copy_from_slice(&message[(m_full - 1) * BLOCK..m_full * BLOCK]);
        for j in 0..16 {
            sigma[j] ^= s[j] ^ l_inf[j];
        }
    }
    enc(cipher, &sigma)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::symmetric::aes::AesKey;

    fn h(s: &str) -> Vec<u8> {
        let s: String = s.chars().filter(|c| !c.is_whitespace()).collect();
        (0..s.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
            .collect()
    }

    /// **PMAC-AES-128 / empty message** — libtomcrypt KAT.
    /// Key:    000102030405060708090A0B0C0D0E0F
    /// Msg:    (empty)
    /// Tag:    4399572CD6EA5341B8D35876A7098AF7
    #[test]
    fn pmac_aes128_empty() {
        let key = AesKey::new(&h("000102030405060708090A0B0C0D0E0F")).unwrap();
        let tag = pmac(&key, b"");
        assert_eq!(&tag[..], &h("4399572CD6EA5341B8D35876A7098AF7")[..]);
    }

    /// **PMAC-AES-128 / 3-byte message** — libtomcrypt KAT.
    /// Key:    000102030405060708090A0B0C0D0E0F
    /// Msg:    000102
    /// Tag:    256BA5193C1B991B4DF0C51F388A9E27
    #[test]
    fn pmac_aes128_three_bytes() {
        let key = AesKey::new(&h("000102030405060708090A0B0C0D0E0F")).unwrap();
        let tag = pmac(&key, &h("000102"));
        assert_eq!(&tag[..], &h("256BA5193C1B991B4DF0C51F388A9E27")[..]);
    }

    /// **PMAC-AES-128 / 16-byte message** — libtomcrypt KAT.
    /// Key:    000102030405060708090A0B0C0D0E0F
    /// Msg:    000102030405060708090A0B0C0D0E0F
    /// Tag:    EBBD822FA458DAF6DFDAD7C27DA76338
    #[test]
    fn pmac_aes128_one_full_block() {
        let key = AesKey::new(&h("000102030405060708090A0B0C0D0E0F")).unwrap();
        let tag = pmac(&key, &h("000102030405060708090A0B0C0D0E0F"));
        assert_eq!(&tag[..], &h("EBBD822FA458DAF6DFDAD7C27DA76338")[..]);
    }

    /// **PMAC-AES-128 / 20-byte message** — libtomcrypt KAT.
    /// Key:    000102030405060708090A0B0C0D0E0F
    /// Msg:    000102030405060708090A0B0C0D0E0F10111213
    /// Tag:    0412CA150BBF79058D8C75A58C993F55
    #[test]
    fn pmac_aes128_partial_tail() {
        let key = AesKey::new(&h("000102030405060708090A0B0C0D0E0F")).unwrap();
        let tag = pmac(&key, &h("000102030405060708090A0B0C0D0E0F10111213"));
        assert_eq!(&tag[..], &h("0412CA150BBF79058D8C75A58C993F55")[..]);
    }

    /// PMAC is deterministic and differs across messages.
    #[test]
    fn pmac_camellia_deterministic_and_distinct() {
        use crate::symmetric::camellia::Camellia128;
        let cipher = Camellia128::new(&[0x42u8; 16]);
        let t1 = pmac(&cipher, b"hello");
        let t2 = pmac(&cipher, b"hello");
        let t3 = pmac(&cipher, b"hello world");
        assert_eq!(t1, t2);
        assert_ne!(t1, t3);
    }

    /// Self-consistency: `div_x(double(x)) == x`.
    #[test]
    fn double_div_x_inverse() {
        let x = [
            0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF, 0xFE, 0xDC, 0xBA, 0x98, 0x76, 0x54,
            0x32, 0x10,
        ];
        assert_eq!(div_x(&double(&x)), x);
        // Also for an input where the high bit is set (triggers reduction).
        let x = [0xFF; 16];
        assert_eq!(div_x(&double(&x)), x);
    }
}
