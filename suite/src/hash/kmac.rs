//! KMAC128 / KMAC256 — Keccak-based MAC (NIST SP 800-185 §4).
//!
//! KMAC is a MAC built on cSHAKE with function-name `N = "KMAC"`:
//!
//! ```text
//!   KMAC128(K, X, L, S) = cSHAKE128(newX, L, "KMAC", S)
//!     where newX = bytepad(encode_string(K), 168) || X || right_encode(L)
//! ```
//!
//! and analogously for KMAC256 (rate 136).  `L` is the **bit-length** of
//! the requested output — encoded into the message so that a tag truncated
//! to a different length is provably a different MAC (no length-extension,
//! no length-prefix forgery).
//!
//! # Security
//! - Output length is variable (XOF-mode): pass `out_len` in bytes; we
//!   encode `L = out_len * 8` internally.
//! - To verify, recompute and compare in constant time.  KMAC tags are
//!   not customarily compared via subtle here because the API returns a
//!   `Vec<u8>` of arbitrary length; callers should use [`subtle::ConstantTimeEq`]
//!   or a wrapper of their own.

use super::cshake::{bytepad, cshake128, cshake256, encode_string, right_encode};

/// KMAC128.  `key` is the MAC key, `data` the message, `custom_str` an
/// optional domain-separation string (pass `b""` if unused), `out_len`
/// the desired tag length in bytes.
pub fn kmac128(key: &[u8], data: &[u8], custom_str: &[u8], out_len: usize) -> Vec<u8> {
    // newX = bytepad(encode_string(K), 168) || X || right_encode(L)
    // L is in BITS per SP 800-185 §4.3.
    let mut new_x = bytepad(&encode_string(key), 168);
    new_x.extend_from_slice(data);
    new_x.extend_from_slice(&right_encode((out_len as u64) * 8));
    cshake128(&new_x, b"KMAC", custom_str, out_len)
}

/// KMAC256.  Same shape as [`kmac128`] but uses rate 136.
pub fn kmac256(key: &[u8], data: &[u8], custom_str: &[u8], out_len: usize) -> Vec<u8> {
    let mut new_x = bytepad(&encode_string(key), 136);
    new_x.extend_from_slice(data);
    new_x.extend_from_slice(&right_encode((out_len as u64) * 8));
    cshake256(&new_x, b"KMAC", custom_str, out_len)
}

/// KMACXOF128 — XOF variant.  Identical to KMAC128 except `L = 0` is
/// encoded into the message, signalling "arbitrary-length output".
/// The actual extracted length is `out_len`.
pub fn kmacxof128(key: &[u8], data: &[u8], custom_str: &[u8], out_len: usize) -> Vec<u8> {
    let mut new_x = bytepad(&encode_string(key), 168);
    new_x.extend_from_slice(data);
    new_x.extend_from_slice(&right_encode(0));
    cshake128(&new_x, b"KMAC", custom_str, out_len)
}

/// KMACXOF256 — XOF variant of KMAC256 (analogous to [`kmacxof128`]).
pub fn kmacxof256(key: &[u8], data: &[u8], custom_str: &[u8], out_len: usize) -> Vec<u8> {
    let mut new_x = bytepad(&encode_string(key), 136);
    new_x.extend_from_slice(data);
    new_x.extend_from_slice(&right_encode(0));
    cshake256(&new_x, b"KMAC", custom_str, out_len)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn h(s: &str) -> Vec<u8> {
        hex::decode(s.chars().filter(|c| !c.is_whitespace()).collect::<String>()).unwrap()
    }

    fn key_sp800_185() -> Vec<u8> {
        // SP 800-185 §A.4 fixed key: 0x40..0x5f (32 bytes).
        (0x40u8..=0x5f).collect()
    }

    // ── KMAC128 NIST SP 800-185 Annex A.4 ────────────────────────────────────

    /// Sample #1: data = 00 01 02 03, S = "", L = 256 bits.
    #[test]
    fn kmac128_sample_1() {
        let data = h("00010203");
        let expected = h("e5780b0d3ea6f7d3a429c5706aa43a00\
             fadbd7d49628839e3187243f456ee14e");
        assert_eq!(kmac128(&key_sp800_185(), &data, b"", 32), expected);
    }

    /// Sample #2: data = 00 01 02 03, S = "My Tagged Application", L = 256.
    #[test]
    fn kmac128_sample_2() {
        let data = h("00010203");
        let s = b"My Tagged Application";
        let expected = h("3b1fba963cd8b0b59e8c1a6d71888b71\
             43651af8ba0a7070c0979e2811324aa5");
        assert_eq!(kmac128(&key_sp800_185(), &data, s, 32), expected);
    }

    /// Sample #3: data = 0..199, S = "My Tagged Application", L = 256.
    #[test]
    fn kmac128_sample_3() {
        let data: Vec<u8> = (0u8..=199).collect();
        let s = b"My Tagged Application";
        let expected = h("1f5b4e6cca02209e0dcb5ca635b89a15\
             e271ecc760071dfd805faa38f9729230");
        assert_eq!(kmac128(&key_sp800_185(), &data, s, 32), expected);
    }

    // ── KMAC256 NIST SP 800-185 Annex A.5 ────────────────────────────────────

    /// Sample #4: data = 00 01 02 03, S = "My Tagged Application", L = 512.
    #[test]
    fn kmac256_sample_4() {
        let data = h("00010203");
        let s = b"My Tagged Application";
        let expected = h("20c570c31346f703c9ac36c61c03cb64\
             c3970d0cfc787e9b79599d273a68d2f7\
             f69d4cc3de9d104a351689f27cf6f595\
             1f0103f33f4f24871024d9c27773a8dd");
        assert_eq!(kmac256(&key_sp800_185(), &data, s, 64), expected);
    }

    /// Sample #5: data = 0..199, S = "", L = 512.
    #[test]
    fn kmac256_sample_5() {
        let data: Vec<u8> = (0u8..=199).collect();
        let expected = h("75358cf39e41494e949707927cee0af2\
             0a3ff553904c86b08f21cc414bcfd691\
             589d27cf5e15369cbbff8b9a4c2eb178\
             00855d0235ff635da82533ec6b759b69");
        assert_eq!(kmac256(&key_sp800_185(), &data, b"", 64), expected);
    }

    /// Sample #6: data = 0..199, S = "My Tagged Application", L = 512.
    #[test]
    fn kmac256_sample_6() {
        let data: Vec<u8> = (0u8..=199).collect();
        let s = b"My Tagged Application";
        let expected = h("b58618f71f92e1d56c1b8c55ddd7cd18\
             8b97b4ca4d99831eb2699a837da2e4d9\
             70fbacfde50033aea585f1a2708510c3\
             2d07880801bd182898fe476876fc8965");
        assert_eq!(kmac256(&key_sp800_185(), &data, s, 64), expected);
    }

    // ── KMACXOF NIST SP 800-185 §A.4/A.5 (L=0 sentinel) ──────────────────────

    /// KMACXOF128 Sample #4 (Annex A.4): data = 00 01 02 03, S = "", 256 bits.
    #[test]
    fn kmacxof128_sample_4() {
        let data = h("00010203");
        let expected = h("cd83740bbd92ccc8cf032b1481a0f4460e7ca9dd12b08a0c4031178bacd6ec35");
        assert_eq!(kmacxof128(&key_sp800_185(), &data, b"", 32), expected);
    }

    /// KMACXOF256 Sample #6 (Annex A.5.6): data = 0..199, S = "My Tagged Application", 512 bits.
    #[test]
    fn kmacxof256_sample_6() {
        let data: Vec<u8> = (0u8..=199).collect();
        let s = b"My Tagged Application";
        let expected = h("d5be731c954ed7732846bb59dbe3a8e3\
             0f83e77a4bff4459f2f1c2b4ecebb8ce\
             67ba01c62e8ab8578d2d499bd1bb2767\
             68781190020a306a97de281dcc30305d");
        assert_eq!(kmacxof256(&key_sp800_185(), &data, s, 64), expected);
    }
}
