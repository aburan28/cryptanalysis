//! BLAKE3 — a fast, parallel, secure hash function.
//!
//! BLAKE3 builds on BLAKE2 with a Merkle tree structure that enables
//! unlimited parallelism and incremental/streaming verification. Its
//! internal compression function mixes 16 32-bit words using the
//! "G" mixing function (ARX: Add, Rotate, XOR).
//!
//! Rather than re-implementing the full Merkle-tree machinery here (which
//! would obscure the learning goal), we delegate to the `blake3` crate —
//! the reference implementation maintained by the BLAKE3 authors.
//!
//! See <https://github.com/BLAKE3-team/BLAKE3-specs/blob/master/blake3.pdf>
//! for the full specification.

/// Compute BLAKE3 of `data`, returning a 32-byte digest.
pub fn blake3_hash(data: &[u8]) -> [u8; 32] {
    *blake3::hash(data).as_bytes()
}

/// Compute a BLAKE3 keyed hash (MAC). `key` must be exactly 32 bytes.
pub fn blake3_keyed(key: &[u8; 32], data: &[u8]) -> [u8; 32] {
    *blake3::keyed_hash(key, data).as_bytes()
}

/// Derive a key using BLAKE3's key-derivation mode.
///
/// `context` is a globally unique, hard-coded application string.
/// `material` is the key/secret input.
pub fn blake3_derive_key(context: &str, material: &[u8]) -> [u8; 32] {
    blake3::derive_key(context, material)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_hash() {
        let h = blake3_hash(b"");
        assert_eq!(h.len(), 32);
        // Known answer: BLAKE3("") from the spec
        let expected =
            hex::decode("af1349b9f5f9a1a6a0404dea36dcc9499bcb25c9adc112b7cc9a93cae41f3262")
                .unwrap();
        assert_eq!(&h, expected.as_slice());
    }
}
