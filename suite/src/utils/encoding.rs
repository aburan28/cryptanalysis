//! Byte/hex/BigUint encoding utilities.

use num_bigint::BigUint;

/// Encode bytes as lowercase hex string.
pub fn to_hex(bytes: &[u8]) -> String {
    hex::encode(bytes)
}

/// Decode a hex string into bytes, returning an error on bad input.
pub fn from_hex(s: &str) -> Result<Vec<u8>, hex::FromHexError> {
    hex::decode(s)
}

/// Encode a `BigUint` as a fixed-width big-endian byte array.
/// Pads with leading zeros if the value is shorter than `len`.
///
/// This legacy helper keeps the historical truncating behavior. New fixed-width
/// public encoders should prefer [`bigint_to_bytes_be_checked`] so oversized
/// values are rejected instead of silently losing high-order bytes.
pub fn bigint_to_bytes_be(n: &BigUint, len: usize) -> Vec<u8> {
    let raw = n.to_bytes_be();
    if raw.len() >= len {
        raw[raw.len() - len..].to_vec()
    } else {
        let mut out = vec![0u8; len];
        out[len - raw.len()..].copy_from_slice(&raw);
        out
    }
}

/// Encode a `BigUint` as exactly `len` big-endian bytes, rejecting overflow.
///
/// Leading zero padding is added when needed. If the integer needs more than
/// `len` bytes, `None` is returned rather than silently truncating.
pub fn bigint_to_bytes_be_checked(n: &BigUint, len: usize) -> Option<Vec<u8>> {
    let raw = n.to_bytes_be();
    if raw.len() > len {
        None
    } else {
        let mut out = vec![0u8; len];
        out[len - raw.len()..].copy_from_slice(&raw);
        Some(out)
    }
}

/// Decode a big-endian byte slice into a `BigUint`.
pub fn bytes_be_to_bigint(bytes: &[u8]) -> BigUint {
    BigUint::from_bytes_be(bytes)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn checked_bigint_encoder_rejects_overflow() {
        let n = BigUint::from(0x0100u32);
        assert_eq!(bigint_to_bytes_be_checked(&n, 2).unwrap(), vec![0x01, 0x00]);
        assert!(bigint_to_bytes_be_checked(&n, 1).is_none());
    }
}
