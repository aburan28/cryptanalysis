//! CMAC — Cipher-based Message Authentication Code (NIST SP 800-38B).
//!
//! AES-CMAC is the block-cipher-based MAC used in IPsec, smart
//! cards (EMV), TLS 1.0/1.1 cipher suites with TLS_*_CMAC_*, and
//! various wireless protocols.  Strictly preferable to CBC-MAC for
//! variable-length messages because it handles length without
//! length-extension issues.
//!
//! # Algorithm
//!
//! 1. Compute `L = AES_K(0¹²⁸)`.
//! 2. Derive subkeys `K1 = L · x` and `K2 = L · x²` in
//!    `GF(2¹²⁸)` represented as `x¹²⁸ + x⁷ + x² + x + 1`.
//! 3. Pad the message: if `|M|` is a multiple of 16, the last
//!    block is XORed with `K1`; otherwise pad with `0x80 0x00...`
//!    and XOR with `K2`.
//! 4. CBC-MAC the padded message using AES-K with zero IV; the
//!    final ciphertext block is the tag.

use super::aes::AesKey;
use super::modes::cipher::BlockCipher128;

/// 16-byte authentication tag.
pub type CmacTag = [u8; 16];

#[inline]
fn enc<C: BlockCipher128>(cipher: &C, block: &[u8; 16]) -> [u8; 16] {
    let mut b = *block;
    cipher.encrypt_block(&mut b);
    b
}

/// CMAC generic over any 16-byte block cipher (NIST SP 800-38B).
/// AES-CMAC is the canonical instance; this is the same algorithm
/// keyed on Camellia, Twofish, Serpent, etc.
pub fn cmac<C: BlockCipher128>(cipher: &C, message: &[u8]) -> CmacTag {
    let l = enc(cipher, &[0u8; 16]);
    let k1 = double(&l);
    let k2 = double(&k1);

    let n_blocks = if message.is_empty() {
        1
    } else {
        message.len().div_ceil(16)
    };
    let last_complete = !message.is_empty() && message.len().is_multiple_of(16);

    let mut state = [0u8; 16];
    for i in 0..n_blocks - 1 {
        let block = &message[16 * i..16 * (i + 1)];
        for j in 0..16 {
            state[j] ^= block[j];
        }
        state = enc(cipher, &state);
    }

    // Final block.
    let mut last = [0u8; 16];
    let last_start = 16 * (n_blocks - 1);
    let last_data = &message[last_start..];
    if last_complete {
        last.copy_from_slice(last_data);
        for j in 0..16 {
            last[j] ^= k1[j];
        }
    } else {
        last[..last_data.len()].copy_from_slice(last_data);
        last[last_data.len()] = 0x80;
        for j in 0..16 {
            last[j] ^= k2[j];
        }
    }
    for j in 0..16 {
        state[j] ^= last[j];
    }
    enc(cipher, &state)
}

/// AES-CMAC — thin wrapper over the generic [`cmac`] for an AES key.
pub fn aes_cmac(key: &AesKey, message: &[u8]) -> CmacTag {
    cmac(key, message)
}

/// Double in `GF(2¹²⁸)` with reduction polynomial
/// `x¹²⁸ + x⁷ + x² + x + 1`.  The big-endian convention SP 800-38B uses.
fn double(input: &[u8; 16]) -> [u8; 16] {
    let mut out = [0u8; 16];
    let mut carry = 0u8;
    for i in (0..16).rev() {
        let new_carry = input[i] >> 7;
        out[i] = (input[i] << 1) | carry;
        carry = new_carry;
    }
    if carry != 0 {
        out[15] ^= 0x87; // x^7 + x^2 + x + 1
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hex_decode(s: &str) -> Vec<u8> {
        let s: String = s.chars().filter(|c| !c.is_whitespace()).collect();
        (0..s.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
            .collect()
    }

    fn key128(s: &str) -> AesKey {
        let v = hex_decode(s);
        let mut k = [0u8; 16];
        k.copy_from_slice(&v);
        AesKey::Aes128(k)
    }

    /// **NIST SP 800-38B test vector 1**: AES-128 CMAC of empty
    /// string with key 2b7e1516...09cf4f3c is bb1d6929...
    #[test]
    fn cmac_empty_message_aes128() {
        let key = key128("2b7e151628aed2a6abf7158809cf4f3c");
        let tag = aes_cmac(&key, b"");
        assert_eq!(
            hex(&tag),
            "bb1d6929e95937287fa37d129b756746",
            "CMAC empty failed"
        );
    }

    /// **NIST SP 800-38B test vector 2**: AES-128 CMAC of 16-byte
    /// message (one full block).
    #[test]
    fn cmac_one_block_aes128() {
        let key = key128("2b7e151628aed2a6abf7158809cf4f3c");
        let msg = hex_decode("6bc1bee22e409f96e93d7e117393172a");
        let tag = aes_cmac(&key, &msg);
        assert_eq!(hex(&tag), "070a16b46b4d4144f79bdd9dd04a287c");
    }

    /// **NIST SP 800-38B test vector 3**: AES-128 CMAC of
    /// 40-byte message (2.5 blocks → final block requires
    /// padding + K2 XOR).
    #[test]
    fn cmac_partial_block_aes128() {
        let key = key128("2b7e151628aed2a6abf7158809cf4f3c");
        let msg = hex_decode(
            "6bc1bee22e409f96e93d7e117393172a\
             ae2d8a571e03ac9c9eb76fac45af8e51\
             30c81c46a35ce411",
        );
        let tag = aes_cmac(&key, &msg);
        assert_eq!(hex(&tag), "dfa66747de9ae63030ca32611497c827");
    }

    /// **NIST SP 800-38B test vector 4**: AES-128 CMAC of
    /// 64-byte message (4 full blocks).
    #[test]
    fn cmac_four_blocks_aes128() {
        let key = key128("2b7e151628aed2a6abf7158809cf4f3c");
        let msg = hex_decode(
            "6bc1bee22e409f96e93d7e117393172a\
             ae2d8a571e03ac9c9eb76fac45af8e51\
             30c81c46a35ce411e5fbc1191a0a52ef\
             f69f2445df4f9b17ad2b417be66c3710",
        );
        let tag = aes_cmac(&key, &msg);
        assert_eq!(hex(&tag), "51f0bebf7e3b9d92fc49741779363cfe");
    }

    fn hex(bytes: &[u8]) -> String {
        bytes.iter().map(|b| format!("{:02x}", b)).collect()
    }

    /// **Camellia-CMAC round-trip** — proves the generic construction
    /// works over a non-AES 16-byte cipher.  Deterministic identity:
    /// two CMACs of the same message under the same cipher must match.
    #[test]
    fn cmac_camellia_is_deterministic_and_distinct() {
        use crate::symmetric::camellia::Camellia128;
        let cipher = Camellia128::new(&[0x42u8; 16]);
        let t1 = cmac(&cipher, b"hello");
        let t2 = cmac(&cipher, b"hello");
        let t3 = cmac(&cipher, b"hellp");
        assert_eq!(t1, t2);
        assert_ne!(t1, t3);
    }
}
