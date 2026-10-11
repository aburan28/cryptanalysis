//! Elliptic Curve Diffie-Hellman (ECDH) key exchange.
//!
//! # Protocol
//! Alice and Bob each hold a private scalar and the corresponding public point:
//!   Alice: d_A, Q_A = d_A·G
//!   Bob:   d_B, Q_B = d_B·G
//!
//! Shared secret:
//!   Alice computes: S = d_A · Q_B = d_A · d_B · G
//!   Bob computes:   S = d_B · Q_A = d_B · d_A · G
//!
//! Both arrive at the same point S; only the x-coordinate is used as the
//! raw shared secret (per RFC 8422 / ANSI X9.63).  Callers should derive a
//! symmetric key from this value using HKDF rather than using it directly.

use super::ct::scalar_mul_secret;
use super::curve::CurveParams;
use super::keys::{EccPrivateKey, EccPublicKey};
use super::point::Point;
use num_bigint::BigUint;
use num_traits::One;

/// Perform ECDH: multiply `our_private` by `their_public`.
/// Returns the x-coordinate of the resulting point as a 32-byte big-endian value,
/// or `None` if the result is the point at infinity (degenerate input).
pub fn ecdh(
    our_private: &EccPrivateKey,
    their_public: &EccPublicKey,
    curve: &CurveParams,
) -> Option<[u8; 32]> {
    if !valid_ecdh_inputs(our_private, their_public, curve) {
        return None;
    }
    // For secp256k1, this routes through `ProjectivePoint::scalar_mul_ct`
    // — Montgomery ladder over Renes-Costello-Batina formulas with
    // limb-level constant-time field arithmetic.  For P-256 it falls
    // back to the affine ladder over the textbook `FieldElement`.
    let shared = scalar_mul_secret(&their_public.point, &our_private.scalar, curve);

    match shared {
        Point::Affine { x, .. } => {
            let bytes = crate::utils::encoding::bigint_to_bytes_be_checked(&x.value, 32)?;
            let mut out = [0u8; 32];
            out.copy_from_slice(&bytes);
            Some(out)
        }
        Point::Infinity => None,
    }
}

/// Raw shared secret as a `BigUint` (x-coordinate of d_A · Q_B).
pub fn ecdh_raw(
    our_private: &EccPrivateKey,
    their_public: &EccPublicKey,
    curve: &CurveParams,
) -> Option<BigUint> {
    if !valid_ecdh_inputs(our_private, their_public, curve) {
        return None;
    }
    match scalar_mul_secret(&their_public.point, &our_private.scalar, curve) {
        Point::Affine { x, .. } => Some(x.value),
        Point::Infinity => None,
    }
}

fn valid_ecdh_inputs(
    our_private: &EccPrivateKey,
    their_public: &EccPublicKey,
    curve: &CurveParams,
) -> bool {
    our_private.curve_name == curve.name
        && their_public.curve_name == curve.name
        && our_private.scalar >= BigUint::one()
        && our_private.scalar < curve.n
        && curve.is_valid_public_point(&their_public.point)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ecc::{curve::CurveParams, keys::EccKeyPair};

    #[test]
    fn shared_secret_matches_secp256k1() {
        let curve = CurveParams::secp256k1();
        let alice = EccKeyPair::generate(&curve);
        let bob = EccKeyPair::generate(&curve);
        let secret_a = ecdh(&alice.private, &bob.public, &curve).unwrap();
        let secret_b = ecdh(&bob.private, &alice.public, &curve).unwrap();
        assert_eq!(secret_a, secret_b, "shared secrets must match");
    }

    #[test]
    fn shared_secret_matches_p256() {
        let curve = CurveParams::p256();
        let alice = EccKeyPair::generate(&curve);
        let bob = EccKeyPair::generate(&curve);
        let secret_a = ecdh(&alice.private, &bob.public, &curve).unwrap();
        let secret_b = ecdh(&bob.private, &alice.public, &curve).unwrap();
        assert_eq!(secret_a, secret_b, "P-256 shared secrets must match");
    }

    #[test]
    fn ecdh_p256_known_answer() {
        // Cross-checked against Python `cryptography`:
        //   priv_a = 1, priv_b = 2; the shared secret is x-coordinate of 2G
        //   = 7cf27b188d034f7e8a52380304b51ac3c08969e277f21b35a60b48fc47669978
        let curve = CurveParams::p256();
        let alice = EccKeyPair::from_private(BigUint::from(1u32), &curve);
        let bob = EccKeyPair::from_private(BigUint::from(2u32), &curve);

        let secret_ab = ecdh(&alice.private, &bob.public, &curve).unwrap();
        let secret_ba = ecdh(&bob.private, &alice.public, &curve).unwrap();
        assert_eq!(secret_ab, secret_ba);
        assert_eq!(
            hex::encode(secret_ab),
            "7cf27b188d034f7e8a52380304b51ac3c08969e277f21b35a60b48fc47669978",
        );
    }

    #[test]
    fn rejects_invalid_peer_public_key() {
        let curve = CurveParams::p256();
        let alice = EccKeyPair::from_private(BigUint::from(1u32), &curve);
        let bad = EccPublicKey {
            point: Point::Infinity,
            curve_name: curve.name.to_string(),
        };
        assert!(ecdh(&alice.private, &bad, &curve).is_none());
        assert!(ecdh_raw(&alice.private, &bad, &curve).is_none());
    }
}
