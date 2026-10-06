//! **GOST R 34.10-2012** — Russian elliptic-curve digital signature
//! standard (GOST 34.10-2012).
//!
//! Replaces GOST R 34.10-2001 with a refreshed parameter set and adds
//! a 512-bit variant alongside the original 256-bit variant.  The
//! signing/verification algorithm is otherwise identical to its
//! predecessor.
//!
//! ## Algorithm
//!
//! Both variants operate on a short-Weierstrass prime-field curve
//! `E: y² = x³ + ax + b (mod p)` with prime order `q` (subgroup order).
//! The 256-bit variant uses Streebog-256 to hash the message; the
//! 512-bit variant uses Streebog-512.
//!
//! ### Sign
//! Given private key `d ∈ [1, q-1]`, message `M`, and the appropriate
//! Streebog digest function:
//!
//! 1. `h = Streebog(M)`; `α = int(h)` (big-endian).
//! 2. `e = α mod q`; if `e = 0`, set `e = 1`.
//! 3. Choose random `k ∈ [1, q-1]`.
//! 4. `(x_C, y_C) = k·P`.
//! 5. `r = x_C mod q`; restart if `r = 0`.
//! 6. `s = (r·d + k·e) mod q`; restart if `s = 0`.
//! 7. Output `(r, s)`.
//!
//! ### Verify
//! Given public key `Q = d·P`, signature `(r, s)`, message `M`:
//!
//! 1. Reject if `r, s ∉ [1, q-1]`.
//! 2. `h = Streebog(M)`; `e = int(h) mod q`; if `e = 0`, set `e = 1`.
//! 3. `v = e⁻¹ mod q`.
//! 4. `z₁ = s·v mod q`, `z₂ = (q − r)·v mod q`.
//! 5. `(x_C, _) = z₁·P + z₂·Q`.
//! 6. Accept iff `x_C mod q == r`.
//!
//! ## Differences from ECDSA
//!
//! The signing equation in GOST 34.10 is `s = r·d + k·e` (vs ECDSA's
//! `s = k⁻¹(z + r·d)`).  This avoids the modular inverse at signing
//! time — only the verifier inverts `e`.  As a consequence, signing
//! does not fail when `k` is congruent to an awkward value mod `q`;
//! it only restarts when `r = 0` or `s = 0`, both of which are
//! negligibly probable.

use super::curve::CurveParams;
use super::point::Point;
use crate::hash::streebog::{streebog_256, streebog_512};
use crate::utils::{mod_inverse, random::random_scalar};
use num_bigint::BigUint;
use num_traits::{One, Zero};

/// A GOST 34.10-2012 signature pair `(r, s)`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct GostSignature {
    pub r: BigUint,
    pub s: BigUint,
}

/// Width of the digest variant — 256 or 512 bits.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DigestBits {
    B256,
    B512,
}

fn hash_message(msg: &[u8], width: DigestBits) -> Vec<u8> {
    match width {
        DigestBits::B256 => streebog_256(msg).to_vec(),
        DigestBits::B512 => streebog_512(msg).to_vec(),
    }
}

/// Compute the "α mod q, replace 0 with 1" reduction step from §6 of
/// GOST R 34.10-2012.  Exposed so callers that want to sign a
/// pre-computed digest can match the standard's mapping exactly.
pub fn reduce_digest(hash: &[u8], q: &BigUint) -> BigUint {
    // GOST §6.1: α = int(h) read big-endian.  Note: the standard
    // describes h as the bit-reversed Streebog output ("the integer
    // whose binary expansion coincides with α"), but in the worked
    // example the digest is treated as a plain big-endian integer.
    // We follow the example convention.
    let alpha = BigUint::from_bytes_be(hash);
    let mut e = alpha % q;
    if e.is_zero() {
        e = BigUint::one();
    }
    e
}

/// **Sign** a pre-computed hash with a *fixed* nonce `k`.  Exists
/// purely for test-vector reproduction — production code must call
/// [`sign_hash`] (random `k`) or wrap a deterministic-RFC-6979-style
/// derivation around it.
pub fn sign_hash_with_k(
    hash: &[u8],
    d: &BigUint,
    k: &BigUint,
    curve: &CurveParams,
) -> Option<GostSignature> {
    if d.is_zero() || d >= &curve.n || k.is_zero() || k >= &curve.n {
        return None;
    }
    let e = reduce_digest(hash, &curve.n);
    let a = curve.a_fe();
    let kg = curve.generator().scalar_mul_ct(k, &a, curve.order_bits());
    let x_c = match &kg {
        Point::Affine { x, .. } => x.value.clone(),
        Point::Infinity => return None,
    };
    let r = &x_c % &curve.n;
    if r.is_zero() {
        return None;
    }
    let s = (&r * d + k * &e) % &curve.n;
    if s.is_zero() {
        return None;
    }
    Some(GostSignature { r, s })
}

/// **Sign** a pre-computed `hash` with private key `d`, using a fresh
/// random nonce `k ∈ [1, q-1]` on each call.
pub fn sign_hash(hash: &[u8], d: &BigUint, curve: &CurveParams) -> GostSignature {
    loop {
        let k = random_scalar(&curve.n);
        if k.is_zero() {
            continue;
        }
        if let Some(sig) = sign_hash_with_k(hash, d, &k, curve) {
            return sig;
        }
    }
}

/// **Sign** `msg` with private key `d`, hashing the message with the
/// digest variant tied to `curve`'s natural width.  The 256-bit GOST
/// test curves use Streebog-256; the 512-bit ones use Streebog-512.
pub fn sign(msg: &[u8], d: &BigUint, curve: &CurveParams, width: DigestBits) -> GostSignature {
    let h = hash_message(msg, width);
    sign_hash(&h, d, curve)
}

/// **Verify** that `sig` is a valid GOST 34.10-2012 signature for the
/// pre-computed hash `hash` under public key `pa`.
pub fn verify_hash(hash: &[u8], sig: &GostSignature, pa: &Point, curve: &CurveParams) -> bool {
    if !curve.is_valid_public_point(pa) {
        return false;
    }

    if sig.r.is_zero() || sig.r >= curve.n || sig.s.is_zero() || sig.s >= curve.n {
        return false;
    }
    if !curve.is_valid_public_point(pa) {
        return false;
    }
    let e = reduce_digest(hash, &curve.n);
    let a = curve.a_fe();

    let v = match mod_inverse(&e, &curve.n) {
        Some(v) => v,
        None => return false,
    };
    let z1 = (&sig.s * &v) % &curve.n;
    // z2 = (-r · v) mod q  ≡  (q − r·v mod q) mod q
    let rv = (&sig.r * &v) % &curve.n;
    let z2 = (&curve.n - &rv) % &curve.n;

    let z1g = curve.generator().scalar_mul(&z1, &a);
    let z2q = pa.scalar_mul(&z2, &a);
    let sum = z1g.add(&z2q, &a);
    let x_c = match sum {
        Point::Affine { x, .. } => x.value,
        Point::Infinity => return false,
    };
    (&x_c % &curve.n) == sig.r
}

/// **Verify** that `sig` is a valid signature over `msg` under
/// public key `pa`.
pub fn verify(
    msg: &[u8],
    sig: &GostSignature,
    pa: &Point,
    curve: &CurveParams,
    width: DigestBits,
) -> bool {
    let h = hash_message(msg, width);
    verify_hash(&h, sig, pa, curve)
}

/// Derive the public point `Q = d·P` for the given private scalar.
pub fn public_key_from_private(d: &BigUint, curve: &CurveParams) -> Point {
    let a = curve.a_fe();
    curve.generator().scalar_mul_ct(d, &a, curve.order_bits())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn curve_256_test() -> CurveParams {
        CurveParams::gost_3410_2012_256_test()
    }

    fn curve_512_test() -> CurveParams {
        CurveParams::gost_3410_2012_512_test()
    }

    /// **256-bit §A.2.1 — public-key derivation** matches the spec.
    #[test]
    fn gost_256_public_key_vector() {
        let curve = curve_256_test();
        let d = BigUint::parse_bytes(
            b"7A929ADE789BB9BE10ED359DD39A72C11B60961F49397EEE1D19CE9891EC3B28",
            16,
        )
        .unwrap();
        let pa = public_key_from_private(&d, &curve);
        let (xa, ya) = match pa {
            Point::Affine { x, y } => (x.value, y.value),
            _ => panic!("PA should not be infinity"),
        };
        assert_eq!(
            xa,
            BigUint::parse_bytes(
                b"7F2B49E270DB6D90D8595BEC458B50C58585BA1D4E9B788F6689DBD8E56FD80B",
                16,
            )
            .unwrap(),
        );
        assert_eq!(
            ya,
            BigUint::parse_bytes(
                b"26F1B489D6701DD185C8413A977B3CBBAF64D1C593D26627DFFB101A87FF77DA",
                16,
            )
            .unwrap(),
        );
    }

    /// **256-bit §A.2.1 — full deterministic signature** matches.  This
    /// is the standard's worked example with the explicit nonce `k`.
    #[test]
    fn gost_256_signature_vector() {
        let curve = curve_256_test();
        let d = BigUint::parse_bytes(
            b"7A929ADE789BB9BE10ED359DD39A72C11B60961F49397EEE1D19CE9891EC3B28",
            16,
        )
        .unwrap();
        let k = BigUint::parse_bytes(
            b"77105C9B20BCD3122823C8CF6FCC7B956DE33814E95B7FE64FED924594DCEAB3",
            16,
        )
        .unwrap();
        let alpha = hex_bytes("2DFBC1B372D89A1188C09C52E0EEC61FCE52032AB1022E8E67ECE6672B043EE5");
        let sig = sign_hash_with_k(&alpha, &d, &k, &curve).expect("nonce is fine");
        assert_eq!(
            sig.r,
            BigUint::parse_bytes(
                b"41AA28D2F1AB148280CD9ED56FEDA41974053554A42767B83AD043FD39DC0493",
                16,
            )
            .unwrap(),
            "r mismatch",
        );
        assert_eq!(
            sig.s,
            BigUint::parse_bytes(
                b"1456C64BA4642A1653C235A98A60249BCD6D3F746B631DF928014F6C5BF9C40",
                16,
            )
            .unwrap(),
            "s mismatch",
        );
    }

    /// **256-bit — sign / verify roundtrip** with random `k`.
    #[test]
    fn gost_256_sign_verify_roundtrip() {
        let curve = curve_256_test();
        let d = BigUint::parse_bytes(
            b"7A929ADE789BB9BE10ED359DD39A72C11B60961F49397EEE1D19CE9891EC3B28",
            16,
        )
        .unwrap();
        let pa = public_key_from_private(&d, &curve);
        let msg = b"GOST 34.10-2012 message";
        let sig = sign(msg, &d, &curve, DigestBits::B256);
        assert!(verify(msg, &sig, &pa, &curve, DigestBits::B256));
    }

    /// **256-bit — sign-with-k verifies** under the spec's verify
    /// algorithm.  This composes the deterministic signer with our
    /// verifier (same digest input).
    #[test]
    fn gost_256_signature_verifies() {
        let curve = curve_256_test();
        let d = BigUint::parse_bytes(
            b"7A929ADE789BB9BE10ED359DD39A72C11B60961F49397EEE1D19CE9891EC3B28",
            16,
        )
        .unwrap();
        let pa = public_key_from_private(&d, &curve);
        let k = BigUint::parse_bytes(
            b"77105C9B20BCD3122823C8CF6FCC7B956DE33814E95B7FE64FED924594DCEAB3",
            16,
        )
        .unwrap();
        let alpha = hex_bytes("2DFBC1B372D89A1188C09C52E0EEC61FCE52032AB1022E8E67ECE6672B043EE5");
        let sig = sign_hash_with_k(&alpha, &d, &k, &curve).unwrap();
        assert!(verify_hash(&alpha, &sig, &pa, &curve));
    }

    /// **256-bit — wrong-message rejection**.
    #[test]
    fn gost_256_wrong_message_fails() {
        let curve = curve_256_test();
        let d = BigUint::parse_bytes(
            b"7A929ADE789BB9BE10ED359DD39A72C11B60961F49397EEE1D19CE9891EC3B28",
            16,
        )
        .unwrap();
        let pa = public_key_from_private(&d, &curve);
        let sig = sign(b"original", &d, &curve, DigestBits::B256);
        assert!(!verify(b"tampered", &sig, &pa, &curve, DigestBits::B256));
    }

    /// **512-bit — sign / verify roundtrip**.
    #[test]
    fn gost_512_sign_verify_roundtrip() {
        let curve = curve_512_test();
        let d = BigUint::parse_bytes(
            b"0BA6048AADAE241BA40936D47756D7C93091A0E8514669700EE7508E508B102072E8123B2200A0563322DAD2827E2714A2636B7BFD18AADFC62967821FA18DD4",
            16,
        ).unwrap();
        let pa = public_key_from_private(&d, &curve);
        let msg = b"GOST 34.10-2012 512-bit roundtrip";
        let sig = sign(msg, &d, &curve, DigestBits::B512);
        assert!(verify(msg, &sig, &pa, &curve, DigestBits::B512));
    }

    /// **512-bit — wrong-key rejection**.
    #[test]
    fn gost_512_wrong_key_fails() {
        let curve = curve_512_test();
        let d1 = BigUint::parse_bytes(
            b"0BA6048AADAE241BA40936D47756D7C93091A0E8514669700EE7508E508B102072E8123B2200A0563322DAD2827E2714A2636B7BFD18AADFC62967821FA18DD4",
            16,
        ).unwrap();
        let d2 = BigUint::parse_bytes(
            b"1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF",
            16,
        ).unwrap();
        let pa1 = public_key_from_private(&d1, &curve);
        let pa2 = public_key_from_private(&d2, &curve);
        let sig = sign(b"hello", &d1, &curve, DigestBits::B512);
        assert!(!verify(b"hello", &sig, &pa2, &curve, DigestBits::B512));
        // Verifying with the right key still works.
        assert!(verify(b"hello", &sig, &pa1, &curve, DigestBits::B512));
    }

    /// **Reject out-of-range signatures**.
    #[test]
    fn gost_reject_out_of_range() {
        let curve = curve_256_test();
        let d = BigUint::parse_bytes(
            b"7A929ADE789BB9BE10ED359DD39A72C11B60961F49397EEE1D19CE9891EC3B28",
            16,
        )
        .unwrap();
        let pa = public_key_from_private(&d, &curve);
        let bad_r = GostSignature {
            r: BigUint::zero(),
            s: BigUint::one(),
        };
        assert!(!verify_hash(b"msg", &bad_r, &pa, &curve));
        let bad_s = GostSignature {
            r: BigUint::one(),
            s: curve.n.clone(),
        };
        assert!(!verify_hash(b"msg", &bad_s, &pa, &curve));
    }

    #[test]
    fn gost_rejects_invalid_public_key() {
        let curve = curve_256_test();
        let sig = GostSignature {
            r: BigUint::one(),
            s: BigUint::one(),
        };
        assert!(!verify_hash(b"msg", &sig, &Point::Infinity, &curve));
    }

    fn hex_bytes(s: &str) -> Vec<u8> {
        (0..s.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
            .collect()
    }
}
