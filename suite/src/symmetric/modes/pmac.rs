//! **PMAC** — Parallelizable Message Authentication Code
//! (Rogaway, EUROCRYPT 2002).  Generic over any 16-byte block cipher.
//!
//! ## Construction
//!
//! Given a 16-byte block cipher `E` with key `K`:
//!
//! ```text
//!     L      = E_K(0^128)
//!     L_-1   = L · x^{-1}                       (in GF(2^128))
//!     L_i    = L · x^i  = double^i(L)
//!
//!     Σ = 0; Offset = 0
//!     For i = 1..m-1 (every full block but the last):
//!         Offset ⊕= L_{ntz(i)}
//!         Σ      ⊕= E_K(M_i ⊕ Offset)
//!
//!     # Handle the last block:
//!     If |M_m| = 128:   Σ ⊕= M_m ⊕ L_{-1}
//!     Else:             Σ ⊕= pad10*(M_m)
//!
//!     Tag = E_K(Σ)
//! ```
//!
//! ## Why PMAC alongside CMAC?
//!
//! - **Parallelisable**: every full-block `E_K` call is independent,
//!   so PMAC can be vectorised across cores / SIMD lanes.  CMAC is
//!   strictly serial.
//! - **Patents expired in 2021** — Rogaway's PMAC patent was the main
//!   reason CMAC (which sidesteps it) ended up the NIST-standard MAC.
//!   Now both are unencumbered.
//! - Same security proof structure as CMAC; same 64-bit birthday bound.
//!
//! ## References
//!
//! - **P. Rogaway**, *A Block-Cipher Mode of Operation for Parallelisable
//!   Message Authentication*, EUROCRYPT 2002.
//! - Reference C and test vectors: <https://web.cs.ucdavis.edu/>~rogaway/ocb/pmac.htm

use super::cipher::BlockCipher128;

const BLOCK: usize = 16;

#[inline]
fn enc<C: BlockCipher128>(cipher: &C, block: &[u8; 16]) -> [u8; 16] {
    let mut b = *block;
    cipher.encrypt_block(&mut b);
    b
}

/// `double(X) = X · x` in GF(2^128) under reduction `x^128 + x^7 + x^2 + x + 1`.
/// Byte 0 is the high-order byte.
fn double(x: &[u8; 16]) -> [u8; 16] {
    let mut out = [0u8; 16];
    let mut carry = 0u8;
    for i in (0..16).rev() {
        let new_carry = x[i] >> 7;
        out[i] = (x[i] << 1) | carry;
        carry = new_carry;
    }
    if carry != 0 {
        out[15] ^= 0x87;
    }
    out
}

/// `half(X) = X · x^{-1}` in the same field.  Used for the last-full-
/// block offset, as `L_{-1} = half(L)`.
fn half(x: &[u8; 16]) -> [u8; 16] {
    let mut out = [0u8; 16];
    let lsb = x[15] & 1;
    let mut borrow = 0u8;
    for i in 0..16 {
        let new_borrow = x[i] & 1;
        out[i] = (x[i] >> 1) | (borrow << 7);
        borrow = new_borrow;
    }
    if lsb == 1 {
        out[0] ^= 0x80;
        out[15] ^= 0x43; // 0x87 >> 1
    }
    out
}

#[inline]
fn xor16(a: &mut [u8; 16], b: &[u8; 16]) {
    for i in 0..16 {
        a[i] ^= b[i];
    }
}

#[inline]
fn ntz(n: u64) -> u32 {
    debug_assert!(n != 0);
    n.trailing_zeros()
}

/// **PMAC tag** of `message` under the given block cipher.  Returns 16 bytes.
pub fn pmac<C: BlockCipher128>(cipher: &C, message: &[u8]) -> [u8; 16] {
    let l = enc(cipher, &[0u8; 16]);
    let l_inv = half(&l);

    // Precompute the L-table on demand.  For a message of m blocks
    // we need L_0..L_{floor(log2(m))}; small messages need only a few.
    let m = if message.is_empty() {
        1
    } else {
        message.len().div_ceil(BLOCK)
    };
    let max_log = if m > 1 {
        (usize::BITS - (m as u32 - 1).leading_zeros()) as usize
    } else {
        1
    };
    let mut l_table = Vec::with_capacity(max_log + 1);
    let mut cur = double(&l); // L_0 = L · x
    l_table.push(cur);
    for _ in 1..=max_log {
        cur = double(&cur);
        l_table.push(cur);
    }

    let mut sigma = [0u8; 16];
    let mut offset = [0u8; 16];

    let last_complete = !message.is_empty() && message.len().is_multiple_of(BLOCK);
    let full_blocks_to_xor_inline = m - 1;

    for i in 1..=full_blocks_to_xor_inline {
        xor16(&mut offset, &l_table[ntz(i as u64) as usize]);
        let mut blk = [0u8; 16];
        blk.copy_from_slice(&message[(i - 1) * BLOCK..i * BLOCK]);
        xor16(&mut blk, &offset);
        let y = enc(cipher, &blk);
        xor16(&mut sigma, &y);
    }

    // Final block handling.
    let last_start = full_blocks_to_xor_inline * BLOCK;
    let last = &message[last_start..];
    if last_complete {
        // Last block is full: Σ ⊕= M_m ⊕ L_inv
        let mut blk = [0u8; 16];
        blk.copy_from_slice(last);
        xor16(&mut sigma, &blk);
        xor16(&mut sigma, &l_inv);
    } else {
        // Pad with 10*.
        let mut padded = [0u8; 16];
        padded[..last.len()].copy_from_slice(last);
        padded[last.len()] = 0x80;
        xor16(&mut sigma, &padded);
    }

    enc(cipher, &sigma)
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::symmetric::aes::AesKey;
    use crate::symmetric::camellia::Camellia128;

    fn h(s: &str) -> Vec<u8> {
        let s: String = s.chars().filter(|c| !c.is_whitespace()).collect();
        (0..s.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
            .collect()
    }

    /// `double` and `half` are inverses (over a sample of inputs).
    #[test]
    fn double_and_half_are_inverses() {
        for seed in [0u8, 1, 0x42, 0x80, 0xff] {
            let mut x = [seed; 16];
            x[0] ^= 0x37; // perturb to cover a few bit patterns
            assert_eq!(half(&double(&x)), x);
            assert_eq!(double(&half(&x)), x);
        }
    }

    /// PMAC is deterministic and message-sensitive.
    #[test]
    fn pmac_deterministic_and_distinguishing() {
        let key = AesKey::new(&[0x42u8; 16]).unwrap();
        let t1 = pmac(&key, b"hello");
        let t2 = pmac(&key, b"hello");
        let t3 = pmac(&key, b"helln");
        assert_eq!(t1, t2);
        assert_ne!(t1, t3);
    }

    /// PMAC differs from CMAC under the same key + message
    /// (algebraically distinct constructions).
    #[test]
    fn pmac_differs_from_cmac() {
        use crate::symmetric::cmac::aes_cmac;
        let key = AesKey::new(&h("2b7e151628aed2a6abf7158809cf4f3c")).unwrap();
        let msg = h("6bc1bee22e409f96e93d7e117393172a");
        let pmac_tag = pmac(&key, &msg);
        let cmac_tag = aes_cmac(&key, &msg);
        assert_ne!(pmac_tag, cmac_tag);
    }

    /// Cross-cipher: PMAC works over Camellia (any `BlockCipher128`).
    #[test]
    fn pmac_works_with_camellia() {
        let cipher = Camellia128::new(&[0x42u8; 16]);
        let t1 = pmac(&cipher, b"PMAC is algebraic in the block cipher");
        let t2 = pmac(&cipher, b"PMAC is algebraic in the block cipher");
        let t3 = pmac(&cipher, b"PMAC is algebraic in the block ciphes");
        assert_eq!(t1, t2);
        assert_ne!(t1, t3);
    }

    /// All-length range: PMAC handles 0, 1, 15, 16, 17, 31, 32, 33 byte
    /// messages without panicking and produces distinct outputs.
    #[test]
    fn pmac_all_length_branches() {
        let key = AesKey::new(&[0x11u8; 16]).unwrap();
        let mut prev: Option<[u8; 16]> = None;
        for len in [0usize, 1, 15, 16, 17, 31, 32, 33, 47, 48, 49, 200] {
            let msg: Vec<u8> = (0..len).map(|i| (i * 13) as u8).collect();
            let tag = pmac(&key, &msg);
            if let Some(p) = prev {
                assert_ne!(tag, p, "PMAC collision at length {}", len);
            }
            prev = Some(tag);
        }
    }

    /// Multi-block message: 4 full AES blocks.  Self-consistency only.
    #[test]
    fn pmac_four_block_message() {
        let key = AesKey::new(&h("2b7e151628aed2a6abf7158809cf4f3c")).unwrap();
        let msg = h("6bc1bee22e409f96e93d7e117393172a\
             ae2d8a571e03ac9c9eb76fac45af8e51\
             30c81c46a35ce411e5fbc1191a0a52ef\
             f69f2445df4f9b17ad2b417be66c3710");
        let tag = pmac(&key, &msg);
        // Determinism + sensitivity.
        assert_eq!(tag, pmac(&key, &msg));
        let mut tampered = msg.clone();
        tampered[63] ^= 1;
        assert_ne!(tag, pmac(&key, &tampered));
    }
}
