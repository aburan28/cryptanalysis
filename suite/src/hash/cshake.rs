//! cSHAKE128 / cSHAKE256 — customizable SHAKE (NIST SP 800-185 §3).
//!
//! cSHAKE is SHAKE prefixed by a domain-separation header carrying a
//! function-name `N` and a customization string `S`:
//!
//! ```text
//!   cSHAKE(X, L, N, S) = KECCAK[c]( bytepad(encode_string(N) ||
//!                                           encode_string(S), rate)
//!                                   || X || 00 , L )
//! ```
//!
//! with domain-separation suffix `0x04` instead of SHAKE's `0x1f`.
//! When both `N` and `S` are empty cSHAKE collapses to plain SHAKE —
//! we take the fast-path and call into [`super::sha3::shake128`] /
//! [`super::sha3::shake256`] directly.
//!
//! # Why care
//! cSHAKE is the building block under KMAC, ParallelHash, TupleHash,
//! and (informally) under STARKs' "fiat-shamir" transcripts.  Getting
//! the bytepad / encode_string framing right *once* lets every higher-
//! level primitive reuse it.

use super::sha3::{keccak_f, shake128, shake256};

// ── SP 800-185 §2.3 encoding helpers ─────────────────────────────────────────

/// `left_encode(x)`: NIST SP 800-185 §2.3.1.  Encodes integer `x` as
/// `n || x_be` where `n` is a one-byte length prefix and `x_be` is the
/// big-endian byte representation of `x` (with leading-zero suppression,
/// except that `x = 0` is encoded as `01 00`).
pub fn left_encode(x: u64) -> Vec<u8> {
    let mut bytes = x.to_be_bytes().to_vec();
    // Strip leading zeros, but keep at least one byte.
    while bytes.len() > 1 && bytes[0] == 0 {
        bytes.remove(0);
    }
    let n = bytes.len() as u8;
    let mut out = Vec::with_capacity(1 + bytes.len());
    out.push(n);
    out.extend_from_slice(&bytes);
    out
}

/// `right_encode(x)`: NIST SP 800-185 §2.3.1.  Same as `left_encode`
/// but with the length byte at the end.  Used by KMAC for the
/// trailing output-length field.
pub fn right_encode(x: u64) -> Vec<u8> {
    let mut bytes = x.to_be_bytes().to_vec();
    while bytes.len() > 1 && bytes[0] == 0 {
        bytes.remove(0);
    }
    let n = bytes.len() as u8;
    let mut out = bytes;
    out.push(n);
    out
}

/// `encode_string(S)`: §2.3.2.  `left_encode(|S| in bits) || S`.
pub fn encode_string(s: &[u8]) -> Vec<u8> {
    let mut out = left_encode((s.len() as u64) * 8);
    out.extend_from_slice(s);
    out
}

/// `bytepad(X, w)`: §2.3.3.  Prepends `left_encode(w)`, then pads with
/// zero bytes to a multiple of `w`.
pub fn bytepad(x: &[u8], w: usize) -> Vec<u8> {
    let mut out = left_encode(w as u64);
    out.extend_from_slice(x);
    while !out.len().is_multiple_of(w) {
        out.push(0);
    }
    out
}

// ── cSHAKE sponge (custom domain byte 0x04) ──────────────────────────────────

/// Keccak sponge with cSHAKE domain-separation suffix `0x04`.  Mirrors
/// the private sponge in `sha3.rs`; duplicated here so we can swap the
/// suffix without touching that module.
fn cshake_sponge(msg: &[u8], rate: usize, output_len: usize) -> Vec<u8> {
    let mut state = [0u64; 25];

    let mut padded = msg.to_vec();
    padded.push(0x04); // cSHAKE domain suffix
    while !padded.len().is_multiple_of(rate) {
        padded.push(0x00);
    }
    *padded.last_mut().unwrap() |= 0x80;

    for block in padded.chunks(rate) {
        for (i, chunk) in block.chunks(8).enumerate() {
            let mut word = [0u8; 8];
            word[..chunk.len()].copy_from_slice(chunk);
            state[i] ^= u64::from_le_bytes(word);
        }
        keccak_f(&mut state);
    }

    let mut out = Vec::with_capacity(output_len);
    while out.len() < output_len {
        for i in 0..(rate / 8) {
            out.extend_from_slice(&state[i].to_le_bytes());
            if out.len() >= output_len {
                break;
            }
        }
        if out.len() < output_len {
            keccak_f(&mut state);
        }
    }
    out.truncate(output_len);
    out
}

/// Build the cSHAKE prefix `bytepad(encode_string(N) || encode_string(S), rate)`
/// and append the user message.
fn cshake_input(data: &[u8], function_name: &[u8], custom_str: &[u8], rate: usize) -> Vec<u8> {
    let mut ns = encode_string(function_name);
    ns.extend_from_slice(&encode_string(custom_str));
    let mut input = bytepad(&ns, rate);
    input.extend_from_slice(data);
    input
}

// ── Public API ───────────────────────────────────────────────────────────────

/// cSHAKE128.  Rate = 168 bytes.  When both `function_name` and
/// `custom_str` are empty, delegates to plain SHAKE128 per §3.3.
pub fn cshake128(data: &[u8], function_name: &[u8], custom_str: &[u8], out_len: usize) -> Vec<u8> {
    if function_name.is_empty() && custom_str.is_empty() {
        return shake128(data, out_len);
    }
    let input = cshake_input(data, function_name, custom_str, 168);
    cshake_sponge(&input, 168, out_len)
}

/// cSHAKE256.  Rate = 136 bytes.  Same empty-input fast-path as cSHAKE128.
pub fn cshake256(data: &[u8], function_name: &[u8], custom_str: &[u8], out_len: usize) -> Vec<u8> {
    if function_name.is_empty() && custom_str.is_empty() {
        return shake256(data, out_len);
    }
    let input = cshake_input(data, function_name, custom_str, 136);
    cshake_sponge(&input, 136, out_len)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn h(s: &str) -> Vec<u8> {
        hex::decode(s.chars().filter(|c| !c.is_whitespace()).collect::<String>()).unwrap()
    }

    // ── Encoding sanity checks ───────────────────────────────────────────────

    #[test]
    fn left_encode_examples() {
        // SP 800-185 §2.3.1 worked examples.
        assert_eq!(left_encode(0), vec![0x01, 0x00]);
        assert_eq!(left_encode(128), vec![0x01, 0x80]);
        assert_eq!(left_encode(65536), vec![0x03, 0x01, 0x00, 0x00]);
    }

    #[test]
    fn right_encode_examples() {
        assert_eq!(right_encode(0), vec![0x00, 0x01]);
        assert_eq!(right_encode(128), vec![0x80, 0x01]);
    }

    #[test]
    fn empty_inputs_collapse_to_shake() {
        // §3.3: with N=S=∅, cSHAKE === SHAKE.
        let x = b"abc";
        assert_eq!(cshake128(x, b"", b"", 32), shake128(x, 32));
        assert_eq!(cshake256(x, b"", b"", 32), shake256(x, 32));
    }

    // ── cSHAKE128 NIST SP 800-185 Annex A samples ────────────────────────────

    /// Sample #1: data = 00 01 02 03, N = "", S = "Email Signature".
    #[test]
    fn cshake128_sample_1() {
        let data = h("00010203");
        let s = b"Email Signature";
        let expected = h("c1c36925b6409a04f1b504fcbca9d82b\
             4017277cb5ed2b2065fc1d3814d5aaf5");
        assert_eq!(cshake128(&data, b"", s, 32), expected);
    }

    /// Sample #2: data = 0..199, N = "", S = "Email Signature".
    #[test]
    fn cshake128_sample_2() {
        let data: Vec<u8> = (0u8..=199).collect();
        let s = b"Email Signature";
        let expected = h("c5221d50e4f822d96a2e8881a961420f\
             294b7b24fe3d2094baed2c6524cc166b");
        assert_eq!(cshake128(&data, b"", s, 32), expected);
    }

    // ── cSHAKE256 NIST SP 800-185 Annex A samples ────────────────────────────

    /// Sample #3: data = 00 01 02 03, N = "", S = "Email Signature", 64 bytes out.
    #[test]
    fn cshake256_sample_3() {
        let data = h("00010203");
        let s = b"Email Signature";
        let expected = h("d008828e2b80ac9d2218ffee1d070c48\
             b8e4c87bff32c9699d5b6896eee0edd1\
             64020e2be0560858d9c00c037e34a969\
             37c561a74c412bb4c746469527281c8c");
        assert_eq!(cshake256(&data, b"", s, 64), expected);
    }

    /// Sample #4: data = 0..199, N = "", S = "Email Signature", 64 bytes out.
    #[test]
    fn cshake256_sample_4() {
        let data: Vec<u8> = (0u8..=199).collect();
        let s = b"Email Signature";
        let expected = h("07dc27b11e51fbac75bc7b3c1d983e8b\
             4b85fb1defaf218912ac86430273091727f42b17ed1df63e\
             8ec118f04b23633c1dfb1574c8fb55cb45da8e25afb092bb");
        // Above hex is wrapped; recompute clean.
        let expected_clean = h("07dc27b11e51fbac75bc7b3c1d983e8b\
             4b85fb1defaf218912ac86430273091727f42b17ed1df63e\
             8ec118f04b23633c1dfb1574c8fb55cb45da8e25afb092bb");
        assert_eq!(expected, expected_clean);
        assert_eq!(cshake256(&data, b"", s, 64), expected);
    }
}
