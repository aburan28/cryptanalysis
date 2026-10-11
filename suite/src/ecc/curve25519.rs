//! Curve25519 field arithmetic over `F_p` where `p = 2²⁵⁵ − 19`.
//!
//! Bernstein 2006.  The prime is a Mersenne-form prime that admits
//! fast modular reduction without conditional branches.  This is
//! the field underlying both X25519 (key agreement) and Ed25519
//! (signatures).
//!
//! # Representation choice
//!
//! Production implementations use radix-2⁵¹ (5 limbs) or
//! radix-2²⁵.⁵ (10 limbs of 26+25 bits) for fast unsaturated
//! arithmetic.  This module uses **`BigUint` over a fixed
//! `p = 2²⁵⁵ − 19` constant** for clarity over speed — same
//! pattern as the rest of the library's `field.rs`.  Verified
//! against RFC 7748 / RFC 8032 KATs at the higher level.
//!
//! Constant-time properties are inherited from `BigUint`'s
//! arithmetic operations (which are *not* constant-time at the
//! limb level).  For production use, the existing P-256 /
//! secp256k1 backends in this library use a constant-time U256;
//! a similar treatment for Curve25519 is in `docs/DEFERRED.md` item
//! "constant-time Curve25519 backend".

use num_bigint::BigUint;
use num_traits::{One, Zero};

/// Curve25519's field prime: `p = 2²⁵⁵ − 19`.
pub fn p() -> BigUint {
    (BigUint::one() << 255) - BigUint::from(19u32)
}

/// Reduce `x mod p`.
pub fn fe_reduce(x: &BigUint) -> BigUint {
    let pp = p();
    if x < &pp {
        x.clone()
    } else {
        x % &pp
    }
}

/// `(a + b) mod p`.
pub fn fe_add(a: &BigUint, b: &BigUint) -> BigUint {
    fe_reduce(&(a + b))
}

/// `(a − b) mod p`.
pub fn fe_sub(a: &BigUint, b: &BigUint) -> BigUint {
    let pp = p();
    if a >= b {
        (a - b) % &pp
    } else {
        &pp - ((b - a) % &pp)
    }
}

/// `(a · b) mod p`.
pub fn fe_mul(a: &BigUint, b: &BigUint) -> BigUint {
    fe_reduce(&(a * b))
}

/// `a² mod p`.
pub fn fe_sq(a: &BigUint) -> BigUint {
    fe_mul(a, a)
}

/// `a⁻¹ mod p` via Fermat's little theorem: `a^(p-2) mod p`.
/// Constant-time-suitable iff `BigUint::modpow` is, which it
/// isn't strictly — but for educational use this is fine.
pub fn fe_inv(a: &BigUint) -> BigUint {
    let pp = p();
    let exp = &pp - BigUint::from(2u32);
    a.modpow(&exp, &pp)
}

/// `a^((p−5)/8) mod p` — used by Ed25519 for the square-root
/// shortcut on Curve25519 (since `p ≡ 5 (mod 8)`).
pub fn fe_pow_p58(a: &BigUint) -> BigUint {
    let pp = p();
    // (p − 5) / 8 = 2²⁵² − 3.
    let exp = (&pp - BigUint::from(5u32)) / BigUint::from(8u32);
    a.modpow(&exp, &pp)
}

/// Square root of `a` in `F_p`.  Returns `Some(s)` iff `s² = a`.
/// Uses the `p ≡ 5 (mod 8)` shortcut: candidate is
/// `a^((p+3)/8)`; if `cand² = a`, return cand; if `cand² = -a`,
/// multiply by `2^((p-1)/4) = i` (a square root of -1) and check;
/// else fail.
pub fn fe_sqrt(a: &BigUint) -> Option<BigUint> {
    let pp = p();
    if a.is_zero() {
        return Some(BigUint::zero());
    }
    // candidate = a^((p+3)/8)
    let exp = (&pp + BigUint::from(3u32)) / BigUint::from(8u32);
    let cand = a.modpow(&exp, &pp);
    let sq = fe_sq(&cand);
    if sq == *a {
        return Some(cand);
    }
    // Try cand * sqrt(-1).  sqrt_m1 = 2^((p-1)/4) mod p.
    let sqrt_m1_exp = (&pp - BigUint::one()) / BigUint::from(4u32);
    let sqrt_m1 = BigUint::from(2u32).modpow(&sqrt_m1_exp, &pp);
    let cand2 = fe_mul(&cand, &sqrt_m1);
    if fe_sq(&cand2) == *a {
        return Some(cand2);
    }
    None
}

/// Encode a field element as 32 little-endian bytes.
pub fn fe_to_bytes(a: &BigUint) -> [u8; 32] {
    let mut out = [0u8; 32];
    let bytes = a.to_bytes_le();
    let n = bytes.len().min(32);
    out[..n].copy_from_slice(&bytes[..n]);
    out
}

/// Decode 32 little-endian bytes to a field element modulo `p`.
///
/// RFC 7748 requires X25519 implementations to accept non-canonical
/// u-coordinate encodings and process them as if reduced modulo `p`,
/// so this helper intentionally performs that reduction. Protocols
/// with stricter encoding rules (for example Ed25519 point decoding)
/// must use [`fe_from_bytes_canonical`] instead.
pub fn fe_from_bytes(bytes: &[u8; 32]) -> BigUint {
    fe_reduce(&BigUint::from_bytes_le(bytes))
}

/// Decode a canonical 32-byte little-endian field-element encoding.
///
/// Returns `None` when the integer is not already in `[0, p)`. This is
/// the right boundary for Ed25519 point encodings, which must reject
/// non-canonical field elements rather than silently reducing them.
pub fn fe_from_bytes_canonical(bytes: &[u8; 32]) -> Option<BigUint> {
    let value = BigUint::from_bytes_le(bytes);
    if value < p() {
        Some(value)
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// `p = 2²⁵⁵ − 19` has 255 bits and the right value.
    #[test]
    fn prime_p() {
        let pp = p();
        assert_eq!(pp.bits(), 255);
        assert_eq!(&pp + BigUint::from(19u32), BigUint::one() << 255);
    }

    /// Field round-trip via byte encoding.
    #[test]
    fn byte_roundtrip() {
        for v in [0u32, 1, 2, 100, 0xFFFFFFFF] {
            let f = BigUint::from(v);
            let bytes = fe_to_bytes(&f);
            let recovered = fe_from_bytes(&bytes);
            assert_eq!(f, recovered);
        }
    }

    #[test]
    fn canonical_decoder_rejects_p_and_above() {
        let pp = p();
        let canonical = fe_to_bytes(&(pp.clone() - BigUint::one()));
        assert_eq!(
            fe_from_bytes_canonical(&canonical),
            Some(pp.clone() - BigUint::one())
        );

        let p_bytes = fe_to_bytes(&pp);
        assert_eq!(fe_from_bytes_canonical(&p_bytes), None);

        let reduced = fe_from_bytes(&p_bytes);
        assert_eq!(
            reduced,
            BigUint::zero(),
            "X25519-style decoder still reduces non-canonical inputs mod p"
        );
    }

    /// `a · a⁻¹ ≡ 1 (mod p)`.
    #[test]
    fn inverse_correctness() {
        for v in [2u32, 3, 5, 7, 100, 12345] {
            let a = BigUint::from(v);
            let a_inv = fe_inv(&a);
            assert_eq!(fe_mul(&a, &a_inv), BigUint::one());
        }
    }

    /// `sqrt(a²) = ±a`.
    #[test]
    fn sqrt_correctness() {
        for v in [1u32, 2, 3, 5, 100, 12345] {
            let a = BigUint::from(v);
            let a_sq = fe_sq(&a);
            let s = fe_sqrt(&a_sq).expect("a² is always a QR");
            // s ≡ ±a (mod p)
            assert!(s == a || s == fe_sub(&BigUint::zero(), &a));
        }
    }
}
