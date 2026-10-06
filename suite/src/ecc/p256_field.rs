//! Constant-time field arithmetic over P-256's prime field F_p.
//!
//! `p = 2^256 - 2^224 + 2^192 + 2^96 - 1`
//!
//! Mirrors [`crate::ecc::secp256k1_field`]: every value is held in
//! Montgomery form `a·R mod p` where `R = 2^256`, and arithmetic
//! delegates to the constant-time [`crate::ct_bignum::U256`]
//! primitives.  All Montgomery constants are computed at compile time
//! via [`crate::ct_bignum::compute_minv64`] and the `from_montgomery_*`
//! constructors, and are cross-checked against `num-bigint` reference
//! computations in this module's tests.
//!
//! See [`crate::ecc::secp256k1_field`] for the design rationale and a
//! more thorough writeup of the Montgomery-form invariants.

use crate::ct_bignum::{compute_minv64, Uint, U256};
use num_bigint::BigUint;
use subtle::{Choice, ConstantTimeEq};

/// P-256 prime modulus, as little-endian limbs.
///
/// `p = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF`
/// `  = 2^256 - 2^224 + 2^192 + 2^96 - 1`
pub const P: U256 = Uint([
    0xFFFF_FFFF_FFFF_FFFF,
    0x0000_0000_FFFF_FFFF,
    0x0000_0000_0000_0000,
    0xFFFF_FFFF_0000_0001,
]);

/// Montgomery constant `m' = -p^(-1) mod 2^64`.
pub const P_INV_LOW: u64 = compute_minv64(P.0[0]);

/// `R mod p`, where `R = 2^256`.  Equal to "1" in Montgomery form.
pub const R_MOD_P: U256 = Uint([
    0x0000_0000_0000_0001,
    0xFFFF_FFFF_0000_0000,
    0xFFFF_FFFF_FFFF_FFFF,
    0x0000_0000_FFFF_FFFE,
]);

/// `R^2 mod p`.  Used to convert canonical values into Montgomery form
/// via `mont_mul(a, R^2 mod p)`.
pub const R_SQUARED_MOD_P: U256 = Uint([
    0x0000_0000_0000_0003,
    0xFFFF_FFFB_FFFF_FFFF,
    0xFFFF_FFFF_FFFF_FFFE,
    0x0000_0004_FFFF_FFFD,
]);

/// A field element over P-256's prime, stored in Montgomery form.
#[derive(Copy, Clone, Debug)]
pub struct P256FieldElement(U256);

impl P256FieldElement {
    pub const ZERO: P256FieldElement = P256FieldElement(U256::ZERO);
    pub const ONE: P256FieldElement = P256FieldElement(R_MOD_P);

    pub fn from_canonical(a: &U256) -> Self {
        P256FieldElement(U256::mont_mul(a, &R_SQUARED_MOD_P, &P, P_INV_LOW))
    }

    pub fn to_canonical(&self) -> U256 {
        U256::mont_mul(&self.0, &U256::ONE, &P, P_INV_LOW)
    }

    pub fn from_biguint(v: &BigUint) -> Self {
        let p_bu = P.to_biguint();
        let reduced = U256::from_biguint(&(v % &p_bu));
        Self::from_canonical(&reduced)
    }

    pub fn to_biguint(&self) -> BigUint {
        self.to_canonical().to_biguint()
    }

    pub fn to_bytes_be(&self) -> [u8; 32] {
        self.to_canonical().to_bytes_be()
    }

    pub fn from_bytes_be(bytes: &[u8; 32]) -> Self {
        Self::from_canonical(&U256::from_bytes_be(bytes))
    }

    pub fn add(&self, other: &Self) -> Self {
        P256FieldElement(self.0.add_mod(&other.0, &P))
    }

    pub fn sub(&self, other: &Self) -> Self {
        P256FieldElement(self.0.sub_mod(&other.0, &P))
    }

    pub fn mul(&self, other: &Self) -> Self {
        P256FieldElement(U256::mont_mul(&self.0, &other.0, &P, P_INV_LOW))
    }

    pub fn sqr(&self) -> Self {
        P256FieldElement(U256::mont_sqr(&self.0, &P, P_INV_LOW))
    }

    pub fn neg(&self) -> Self {
        P256FieldElement(U256::ZERO.sub_mod(&self.0, &P))
    }

    /// Multiplicative inverse via Fermat: `a^(p-2) mod p`.  Same
    /// cmov-driven Montgomery ladder as
    /// [`crate::ecc::secp256k1_field::SecpFieldElement::inv`], but over
    /// P-256's prime.
    pub fn inv(&self) -> Self {
        // exp = p - 2.  P[0] = 0xFFFF...FFFF, so subtract 2 from the
        // low limb without affecting the higher ones.
        let exp = Uint([P.0[0].wrapping_sub(2), P.0[1], P.0[2], P.0[3]]);
        let mut r0 = P256FieldElement::ONE;
        let mut r1 = *self;
        for i in (0..256).rev() {
            let limb = i / 64;
            let bit_in_limb = i % 64;
            let bit = (exp.0[limb] >> bit_in_limb) & 1;
            let choice = Choice::from(bit as u8);
            let prod = r0.mul(&r1);
            let r0_sq = r0.sqr();
            let r1_sq = r1.sqr();
            r0 = P256FieldElement::cmov(&r0_sq, &prod, choice);
            r1 = P256FieldElement::cmov(&prod, &r1_sq, choice);
        }
        r0
    }

    pub fn ct_eq(&self, other: &Self) -> Choice {
        self.0.ct_eq_full(&other.0)
    }

    pub fn ct_is_zero(&self) -> Choice {
        self.0.ct_is_zero()
    }

    pub fn cmov(a: &Self, b: &Self, choice: Choice) -> Self {
        P256FieldElement(U256::cmov(&a.0, &b.0, choice))
    }

    #[inline]
    pub fn as_montgomery(&self) -> &U256 {
        &self.0
    }

    pub const fn from_montgomery_unchecked(limbs: U256) -> Self {
        P256FieldElement(limbs)
    }
}

impl PartialEq for P256FieldElement {
    fn eq(&self, other: &Self) -> bool {
        bool::from(self.ct_eq(other))
    }
}

impl Eq for P256FieldElement {}

impl ConstantTimeEq for P256FieldElement {
    fn ct_eq(&self, other: &Self) -> Choice {
        self.ct_eq(other)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use num_bigint::BigUint;
    use num_traits::{One, Zero};

    fn p_bu() -> BigUint {
        P.to_biguint()
    }

    fn samples() -> Vec<BigUint> {
        let p = p_bu();
        vec![
            BigUint::zero(),
            BigUint::one(),
            BigUint::from(2u8),
            BigUint::from(0xdeadbeefu64),
            BigUint::from(1u8) << 32,
            BigUint::from(1u8) << 96, // exercises the limb boundary in P-256's prime
            BigUint::from(1u8) << 192,
            &p - 1u8,
            &p - 2u8,
            &p / 2u8,
            (&p / 2u8) + 1u8,
            BigUint::parse_bytes(
                b"DEADBEEFCAFEBABE0123456789ABCDEF112233445566778899AABBCCDDEEFF00",
                16,
            )
            .unwrap(),
            BigUint::parse_bytes(
                b"FEDCBA9876543210FEDCBA9876543210FEDCBA9876543210FEDCBA9876543210",
                16,
            )
            .unwrap(),
        ]
    }

    #[test]
    fn p_constant_matches_curve_params() {
        let want = U256::from_biguint(&crate::ecc::CurveParams::p256().p);
        assert!(bool::from(P.ct_eq_full(&want)));
    }

    #[test]
    fn r_mod_p_constant_is_correct() {
        let r = BigUint::one() << 256;
        let want = U256::from_biguint(&(&r % p_bu()));
        assert!(bool::from(R_MOD_P.ct_eq_full(&want)));
    }

    #[test]
    fn r_squared_constant_is_correct() {
        let r = BigUint::one() << 256;
        let want = U256::from_biguint(&((&r * &r) % p_bu()));
        assert!(bool::from(R_SQUARED_MOD_P.ct_eq_full(&want)));
    }

    #[test]
    fn p_inv_low_consistent_with_compute_minv64() {
        let prod = P.0[0].wrapping_mul(P_INV_LOW);
        assert_eq!(prod.wrapping_add(1), 0);
    }

    #[test]
    fn from_to_canonical_roundtrips() {
        for v in samples() {
            let fe = P256FieldElement::from_biguint(&v);
            assert_eq!(fe.to_biguint(), v);
        }
    }

    #[test]
    fn add_matches_biguint() {
        let p = p_bu();
        for a in samples() {
            for b in samples() {
                let fa = P256FieldElement::from_biguint(&a);
                let fb = P256FieldElement::from_biguint(&b);
                assert_eq!(fa.add(&fb).to_biguint(), (&a + &b) % &p);
            }
        }
    }

    #[test]
    fn sub_matches_biguint() {
        let p = p_bu();
        for a in samples() {
            for b in samples() {
                let fa = P256FieldElement::from_biguint(&a);
                let fb = P256FieldElement::from_biguint(&b);
                let want = (&p + (&a % &p) - (&b % &p)) % &p;
                assert_eq!(fa.sub(&fb).to_biguint(), want);
            }
        }
    }

    #[test]
    fn mul_matches_biguint() {
        let p = p_bu();
        for a in samples() {
            for b in samples() {
                let fa = P256FieldElement::from_biguint(&a);
                let fb = P256FieldElement::from_biguint(&b);
                assert_eq!(fa.mul(&fb).to_biguint(), (&a * &b) % &p);
            }
        }
    }

    #[test]
    fn sqr_matches_mul_self() {
        let p = p_bu();
        for a in samples() {
            let fa = P256FieldElement::from_biguint(&a);
            assert_eq!(fa.sqr().to_biguint(), (&a * &a) % &p);
            assert_eq!(fa.sqr(), fa.mul(&fa));
        }
    }

    #[test]
    fn neg_matches_biguint() {
        let p = p_bu();
        for a in samples() {
            let fa = P256FieldElement::from_biguint(&a);
            let want = (&p - (&a % &p)) % &p;
            assert_eq!(fa.neg().to_biguint(), want);
        }
    }

    #[test]
    fn inv_times_self_is_one() {
        for a in samples() {
            if a.is_zero() {
                continue;
            }
            let fa = P256FieldElement::from_biguint(&a);
            assert_eq!(fa.mul(&fa.inv()).to_biguint(), BigUint::one());
        }
    }
}
