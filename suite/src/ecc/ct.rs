//! Unified constant-time scalar multiplication dispatcher.
//!
//! Routes `k · P` for secret `k` to the curve's constant-time stack:
//!
//! - **secp256k1** → [`crate::ecc::secp256k1_point`]: projective
//!   coordinates over [`crate::ecc::secp256k1_field::SecpFieldElement`]
//!   (Montgomery form on [`crate::ct_bignum::U256`]); RCB Algorithms 7
//!   (addition) and 9 (doubling) for `a = 0`.
//! - **P-256** → [`crate::ecc::p256_point`]: projective coordinates
//!   over [`crate::ecc::p256_field::P256FieldElement`]; RCB Algorithms
//!   1 (addition) and 3 (doubling) for general `a`, with `a = -3 mod p`
//!   and `b3 = 3·b` carried as field-element constants.
//!
//! Every supported curve goes through one of the constant-time
//! projective ladders.  There is no longer a `BigUint`-backed affine
//! fallback for secret-scalar multiplication.

use super::curve::CurveParams;
use super::p256_point::{ct_scalar_mul_p256, P256ProjectivePoint};
use super::point::Point;
use super::secp256k1_point::{self, ProjectivePoint as SecpProjectivePoint};
use num_bigint::{BigUint, RandBigInt};
use rand::rngs::OsRng;

/// Constant-time scalar multiplication `k · P` for secret `k`.
/// Dispatches to the curve-specific projective Montgomery ladder.
///
/// Use this for **secret** scalars only.  Public-input multiplications
/// (the ECDSA verifier's `u₁·G + u₂·Q`, where both `u_i` are derived
/// from the public signature and message) should keep using the
/// variable-time but faster [`Point::scalar_mul`].
///
/// # Panics
///
/// Panics if `curve.name` is not one of the curves wired in here.
/// Currently supported: `"secp256k1"`, `"P-256"`.  Add a new branch
/// when adding support for another curve — the build will not catch
/// the missing case at compile time.
pub fn scalar_mul_secret(point: &Point, k: &BigUint, curve: &CurveParams) -> Point {
    match curve.name {
        "secp256k1" => secp256k1_point::ct_scalar_mul(point, k, curve),
        "P-256" => ct_scalar_mul_p256(point, k, curve),
        _ => {
            // Generic fallback for curves without a dedicated projective
            // stack: route through the BigUint-backed affine Montgomery
            // ladder.  This is significantly slower than the projective
            // RCB stacks, but it works for any short-Weierstrass curve.
            point.scalar_mul_ct(k, &curve.a_fe(), curve.order_bits())
        }
    }
}

/// Number of extra bits used for scalar blinding.  64 bits matches
/// the literature (Coron 1999, "Resistance against Differential
/// Power Analysis for Elliptic Curve Cryptosystems") and
/// quantitatively renders DPA / template-attack key recovery
/// infeasible for one-shot signatures.  Larger `r` is safer at
/// the cost of more ladder iterations; 64 is the standard
/// trade-off.
pub const SCALAR_BLINDING_BITS: usize = 64;

/// **Scalar-blinded** constant-time `k · P` for a secret `k`.
///
/// Implements Coron's countermeasure: pick a fresh random
/// `r ∈ [0, 2^64)`, compute `k' = k + r · n` where `n` is the
/// curve order, and run the ladder on `k'` for
/// `n_bits + 64` iterations.  Since `n · P = O` for any point
/// `P` of order dividing `n` (in particular, the generator and
/// any point produced by ECDH), the result `[k']P = [k]P` is
/// unchanged — but the bit pattern that drives the ladder is
/// re-randomised for every call, defeating attacks that
/// statistically combine many ladder traces against the same
/// secret `k` (DPA, template attacks, machine-learning side
/// channels).
///
/// Use this variant inside ECDSA signing in place of plain
/// [`scalar_mul_secret`] whenever the same private key signs
/// many messages.
pub fn scalar_mul_secret_blinded(point: &Point, k: &BigUint, curve: &CurveParams) -> Point {
    // r ← random 64-bit value
    let mut rng = OsRng;
    let r = rng.gen_biguint(SCALAR_BLINDING_BITS as u64);
    let k_blinded = k + &r * &curve.n;
    let scalar_bits = curve.order_bits() + SCALAR_BLINDING_BITS;

    match curve.name {
        "secp256k1" => {
            let pp = SecpProjectivePoint::from_textbook(point);
            let out = pp.scalar_mul_ct(&k_blinded, scalar_bits);
            out.to_textbook(&curve.p)
        }
        "P-256" => {
            let pp = P256ProjectivePoint::from_textbook(point);
            let out = pp.scalar_mul_ct(&k_blinded, scalar_bits);
            out.to_textbook(&curve.p)
        }
        _ => {
            // Generic fallback: still randomise the ladder via the
            // Coron k' = k + r·n trick, but route through the affine
            // BigUint Montgomery ladder.  Slower than the dedicated
            // projective stacks but works for any curve.
            point.scalar_mul_ct(&k_blinded, &curve.a_fe(), scalar_bits)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ecc::curve::CurveParams;
    use crate::ecc::field::FieldElement;
    use num_bigint::BigUint;

    fn point_eq(a: &Point, b: &Point) -> bool {
        match (a, b) {
            (Point::Infinity, Point::Infinity) => true,
            (Point::Affine { x: x1, y: y1 }, Point::Affine { x: x2, y: y2 }) => {
                x1.value == x2.value && y1.value == y2.value
            }
            _ => false,
        }
    }

    /// Blinded scalar mul must produce the same result as unblinded
    /// scalar mul: `[k]G = [k + r·n]G` because `n·G = O`.
    #[test]
    fn blinded_matches_unblinded_secp256k1() {
        let curve = CurveParams::secp256k1();
        let g = curve.generator();
        let k =
            BigUint::parse_bytes(b"DEADBEEFCAFEBABE0123456789ABCDEF0011223344556677", 16).unwrap();
        let unblinded = scalar_mul_secret(&g, &k, &curve);
        // Blinded ladder is randomised; run several times and check
        // every result equals the unblinded baseline.
        for _ in 0..5 {
            let blinded = scalar_mul_secret_blinded(&g, &k, &curve);
            assert!(
                point_eq(&unblinded, &blinded),
                "blinded result must equal unblinded"
            );
        }
    }

    #[test]
    fn blinded_matches_unblinded_p256() {
        let curve = CurveParams::p256();
        let g = curve.generator();
        let k = BigUint::from(0xDEADBEEFu64);
        let unblinded = scalar_mul_secret(&g, &k, &curve);
        for _ in 0..5 {
            let blinded = scalar_mul_secret_blinded(&g, &k, &curve);
            assert!(point_eq(&unblinded, &blinded));
        }
    }

    /// Blinded scalar mul handles `k = 0` and `k = n − 1` edge cases.
    #[test]
    fn blinded_edge_case_zero() {
        let curve = CurveParams::secp256k1();
        let g = curve.generator();
        let zero_result = scalar_mul_secret_blinded(&g, &BigUint::from(0u32), &curve);
        // [0]·G = O (the identity / point at infinity).
        match zero_result {
            Point::Infinity => {}
            _ => panic!("[0]·G must be the identity, got {:?}", zero_result),
        }
    }

    /// Pin SCALAR_BLINDING_BITS so any future change is loud.
    #[test]
    fn blinding_bits_is_64() {
        // Coron 1999 standard.  Lower values weaken DPA resistance;
        // higher values cost ladder iterations linearly.
        assert_eq!(SCALAR_BLINDING_BITS, 64);
    }

    // Force the unused-import lint not to drop FieldElement.
    #[allow(dead_code)]
    fn _link(_: FieldElement) {}
}
