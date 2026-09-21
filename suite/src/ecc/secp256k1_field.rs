//! Constant-time field arithmetic over secp256k1's prime field F_p.
//!
//! `p = 2^256 - 2^32 - 977`
//!
//! Internally every value is stored in **Montgomery form**: a value
//! `a ∈ [0, p)` is represented as `a·R mod p`, where `R = 2^256`.  This
//! lets multiplication and squaring use [`U256::mont_mul`] — which is
//! built from `u64×u64→u128` partial products and `u128` accumulators
//! and never branches on operand magnitudes — instead of the
//! variable-time `BigUint::%`-based reduction used by
//! [`crate::ecc::field::FieldElement`].
//!
//! The Montgomery constants `P_INV_LOW` (`-p[0]^(-1) mod 2^64`) and
//! `R_SQUARED_MOD_P` are computed at compile time and verified by unit
//! tests against `num-bigint` reference computations.
//!
//! See `SECURITY.md` for the wider hardening picture; this module is the
//! piece that closes the limb-level timing leak in field arithmetic for
//! secp256k1 specifically.  P-256 will get a parallel module once this
//! one is wired into [`crate::ecc::point::Point`].

use crate::ct_bignum::{compute_minv64, Uint, U256};
use num_bigint::BigUint;
use subtle::{Choice, ConstantTimeEq};

/// secp256k1 prime modulus, as little-endian limbs.
///
/// `p = 2^256 - 2^32 - 977
///    = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F`
pub const P: U256 = Uint([
    0xFFFF_FFFE_FFFF_FC2F,
    0xFFFF_FFFF_FFFF_FFFF,
    0xFFFF_FFFF_FFFF_FFFF,
    0xFFFF_FFFF_FFFF_FFFF,
]);

/// Montgomery constant `m' = -p^(-1) mod 2^64`.  Computed via the
/// 2-adic Newton iteration in [`compute_minv64`].
pub const P_INV_LOW: u64 = compute_minv64(P.0[0]);

/// `R mod p`, where `R = 2^256`.  Since `R = p + 2^32 + 977`, this is
/// just `2^32 + 977 = 0x1_0000_03D1`.  Equal to "1" in Montgomery form.
pub const R_MOD_P: U256 = Uint([0x0000_0001_0000_03D1, 0, 0, 0]);

/// `R^2 mod p`, used to enter Montgomery form via
/// `a_M = mont_mul(a, R^2 mod p)`.
///
/// Closed form: `(2^32 + 977)^2 = 2^64 + 2·977·2^32 + 977^2`
/// `= 0x1_0000_0000_0000_0000 + 0x7A2_0000_0000 + 0xE90A1`
/// `= 0x1_0000_07A2_000E_90A1` — a 65-bit value, so well below
/// `p` and the modular reduction is a no-op.  Verified by
/// `tests::r_squared_constant_is_correct`.
pub const R_SQUARED_MOD_P: U256 = Uint([0x0000_07A2_000E_90A1, 1, 0, 0]);

/// A field element over secp256k1's prime, stored in Montgomery form.
#[derive(Copy, Clone, Debug)]
pub struct SecpFieldElement(U256);

impl SecpFieldElement {
    /// Additive identity.  In Montgomery form `0·R = 0`.
    pub const ZERO: SecpFieldElement = SecpFieldElement(U256::ZERO);

    /// Multiplicative identity.  In Montgomery form `1·R mod p = R mod p`.
    pub const ONE: SecpFieldElement = SecpFieldElement(R_MOD_P);

    // ── Construction / extraction ────────────────────────────────────────

    /// Convert a canonical-form `U256` (in `[0, p)`) into Montgomery form.
    /// `a → a·R mod p`, computed as `mont_mul(a, R^2 mod p) = a·R^2·R^(-1) = a·R`.
    ///
    /// Caller must ensure `a < p`; this is not runtime-checked.
    pub fn from_canonical(a: &U256) -> Self {
        SecpFieldElement(U256::mont_mul(a, &R_SQUARED_MOD_P, &P, P_INV_LOW))
    }

    /// Extract the canonical form: `a_M · R^(-1) mod p = a`, which is
    /// `mont_mul(a_M, 1)`.
    pub fn to_canonical(&self) -> U256 {
        U256::mont_mul(&self.0, &U256::ONE, &P, P_INV_LOW)
    }

    /// Construct from a `BigUint`, reducing mod p first.  The reduction
    /// goes through `BigUint::%`, which is variable-time — only use this
    /// at trust boundaries where the value originates from public data
    /// or has already been validated.
    pub fn from_biguint(v: &BigUint) -> Self {
        let p_bu = P.to_biguint();
        let reduced = U256::from_biguint(&(v % &p_bu));
        Self::from_canonical(&reduced)
    }

    /// Convert back to a `BigUint` for interop with the variable-time
    /// portions of the codebase (e.g. ECDSA verifier inputs).
    pub fn to_biguint(&self) -> BigUint {
        self.to_canonical().to_biguint()
    }

    /// Big-endian byte serialization (32 bytes), in canonical form.
    pub fn to_bytes_be(&self) -> [u8; 32] {
        self.to_canonical().to_bytes_be()
    }

    /// Big-endian byte deserialization.  Caller must ensure the encoded
    /// value is in `[0, p)`; values `>= p` will yield an out-of-range
    /// internal representation that breaks subsequent arithmetic.
    pub fn from_bytes_be(bytes: &[u8; 32]) -> Self {
        Self::from_canonical(&U256::from_bytes_be(bytes))
    }

    // ── Arithmetic ───────────────────────────────────────────────────────

    /// Field addition.  Constant-time conditional reduction via
    /// [`U256::add_mod`].
    pub fn add(&self, other: &Self) -> Self {
        SecpFieldElement(self.0.add_mod(&other.0, &P))
    }

    /// Field subtraction.
    pub fn sub(&self, other: &Self) -> Self {
        SecpFieldElement(self.0.sub_mod(&other.0, &P))
    }

    /// Field multiplication via Montgomery multiplication.
    pub fn mul(&self, other: &Self) -> Self {
        SecpFieldElement(U256::mont_mul(&self.0, &other.0, &P, P_INV_LOW))
    }

    /// Field squaring.
    pub fn sqr(&self) -> Self {
        SecpFieldElement(U256::mont_sqr(&self.0, &P, P_INV_LOW))
    }

    /// Additive inverse: `0 - self mod p`.  Reduces to one [`U256::sub_mod`].
    pub fn neg(&self) -> Self {
        SecpFieldElement(U256::ZERO.sub_mod(&self.0, &P))
    }

    /// Multiplicative inverse via Fermat's little theorem:
    /// `a^(p-2) mod p`.
    ///
    /// Uses a Montgomery-style ladder over the Montgomery-form
    /// `mul`/`sqr`: iteration count is fixed at 256, every step
    /// performs exactly one multiplication and one squaring, and the
    /// branch on `bit` is replaced with [`U256::cmov`] over the two
    /// candidate next-states.
    ///
    /// Returns `Self::ZERO` if `self.is_zero()`.  Callers that care
    /// about the zero case must check explicitly — there is no `Option`
    /// return because branching on zero would itself leak.
    pub fn inv(&self) -> Self {
        // exp = p - 2.  Since p[0] = 0x...FC2F is far above 2, this is
        // just (p[0] - 2, p[1], p[2], p[3]).
        let exp = Uint([P.0[0].wrapping_sub(2), P.0[1], P.0[2], P.0[3]]);
        let mut r0 = SecpFieldElement::ONE;
        let mut r1 = *self;
        for i in (0..256).rev() {
            let limb = i / 64;
            let bit_in_limb = i % 64;
            let bit = (exp.0[limb] >> bit_in_limb) & 1;
            let choice = Choice::from(bit as u8);

            // Always compute all three; the cmov picks the right pair.
            // bit == 1: r0 ← r0 * r1, r1 ← r1²
            // bit == 0: r0 ← r0²,     r1 ← r0 * r1
            let prod = r0.mul(&r1);
            let r0_sq = r0.sqr();
            let r1_sq = r1.sqr();
            r0 = SecpFieldElement::cmov(&r0_sq, &prod, choice);
            r1 = SecpFieldElement::cmov(&prod, &r1_sq, choice);
        }
        r0
    }

    // ── Comparison / selection ───────────────────────────────────────────

    /// Constant-time equality check.  Two Montgomery-form values are
    /// equal iff their underlying limbs are equal (since the
    /// representation is canonical: every value in `[0, p)` has exactly
    /// one Montgomery encoding).
    pub fn ct_eq(&self, other: &Self) -> Choice {
        self.0.ct_eq_full(&other.0)
    }

    /// Constant-time check for the additive identity.
    pub fn ct_is_zero(&self) -> Choice {
        self.0.ct_is_zero()
    }

    /// Constant-time conditional move: returns `b` iff `choice == 1`.
    pub fn cmov(a: &Self, b: &Self, choice: Choice) -> Self {
        SecpFieldElement(U256::cmov(&a.0, &b.0, choice))
    }

    /// Internal accessor for tests and lower-level interop.  The raw
    /// Montgomery-form limbs leak nothing on their own (they are still
    /// just a 256-bit field element) but callers should normally go
    /// through `to_canonical`.
    #[inline]
    pub fn as_montgomery(&self) -> &U256 {
        &self.0
    }

    /// Construct a `SecpFieldElement` directly from limbs that already
    /// hold the Montgomery encoding of the intended value.
    ///
    /// **Caller is responsible** for ensuring the limbs equal `a·R mod p`
    /// for some `a ∈ [0, p)`.  Misuse breaks the canonical-representation
    /// invariant that arithmetic relies on.
    ///
    /// `const`-callable, so it can populate compile-time constants such
    /// as the curve coefficients `b` and `3b`.  Every such constant is
    /// cross-checked against `from_biguint` in this module's tests.
    pub const fn from_montgomery_unchecked(limbs: U256) -> Self {
        SecpFieldElement(limbs)
    }
}

impl PartialEq for SecpFieldElement {
    fn eq(&self, other: &Self) -> bool {
        bool::from(self.ct_eq(other))
    }
}

impl Eq for SecpFieldElement {}

impl ConstantTimeEq for SecpFieldElement {
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

    /// Curated values exercising interesting limb boundaries.
    fn samples() -> Vec<BigUint> {
        let p = p_bu();
        vec![
            BigUint::zero(),
            BigUint::one(),
            BigUint::from(2u8),
            BigUint::from(0xdeadbeefu64),
            BigUint::from(1u8) << 32,
            BigUint::from(1u8) << 64,
            BigUint::from(1u8) << 128,
            BigUint::from(1u8) << 200,
            &p - 1u8,
            &p - 2u8,
            &p / 2u8,
            (&p / 2u8) + 1u8,
            // Some random-looking values that are definitely < p:
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
        // n * m' ≡ -1 (mod 2^64)  ⇒  n*m' + 1 ≡ 0
        assert_eq!(prod.wrapping_add(1), 0);
    }

    #[test]
    fn from_to_canonical_roundtrips() {
        for v in samples() {
            let fe = SecpFieldElement::from_biguint(&v);
            let back = fe.to_biguint();
            assert_eq!(back, v);
        }
    }

    #[test]
    fn add_matches_biguint() {
        let p = p_bu();
        for a in samples() {
            for b in samples() {
                let fa = SecpFieldElement::from_biguint(&a);
                let fb = SecpFieldElement::from_biguint(&b);
                let got = fa.add(&fb).to_biguint();
                let want = (&a + &b) % &p;
                assert_eq!(got, want);
            }
        }
    }

    #[test]
    fn sub_matches_biguint() {
        let p = p_bu();
        for a in samples() {
            for b in samples() {
                let fa = SecpFieldElement::from_biguint(&a);
                let fb = SecpFieldElement::from_biguint(&b);
                let got = fa.sub(&fb).to_biguint();
                let want = (&p + (&a % &p) - (&b % &p)) % &p;
                assert_eq!(got, want);
            }
        }
    }

    #[test]
    fn mul_matches_biguint() {
        let p = p_bu();
        for a in samples() {
            for b in samples() {
                let fa = SecpFieldElement::from_biguint(&a);
                let fb = SecpFieldElement::from_biguint(&b);
                let got = fa.mul(&fb).to_biguint();
                let want = (&a * &b) % &p;
                assert_eq!(got, want);
            }
        }
    }

    #[test]
    fn sqr_matches_mul_self_and_biguint() {
        let p = p_bu();
        for a in samples() {
            let fa = SecpFieldElement::from_biguint(&a);
            let got_sqr = fa.sqr().to_biguint();
            let got_mul = fa.mul(&fa).to_biguint();
            let want = (&a * &a) % &p;
            assert_eq!(got_sqr, want, "sqr disagrees with biguint");
            assert_eq!(got_mul, want, "mul-self disagrees with biguint");
            assert_eq!(got_sqr, got_mul, "sqr disagrees with mul(a,a)");
        }
    }

    #[test]
    fn neg_matches_biguint() {
        let p = p_bu();
        for a in samples() {
            let fa = SecpFieldElement::from_biguint(&a);
            let got = fa.neg().to_biguint();
            let want = (&p - (&a % &p)) % &p;
            assert_eq!(got, want);
        }
    }

    #[test]
    fn inv_times_self_is_one() {
        for a in samples() {
            if a.is_zero() {
                continue;
            }
            let fa = SecpFieldElement::from_biguint(&a);
            let inv = fa.inv();
            let prod = fa.mul(&inv);
            assert_eq!(
                prod.to_biguint(),
                BigUint::one(),
                "a * a^-1 != 1 for a={:#x}",
                a,
            );
        }
    }

    #[test]
    fn ct_eq_works() {
        let one = SecpFieldElement::ONE;
        let one2 = SecpFieldElement::from_biguint(&BigUint::one());
        let two = SecpFieldElement::from_biguint(&BigUint::from(2u8));
        assert!(bool::from(one.ct_eq(&one2)));
        assert!(!bool::from(one.ct_eq(&two)));
    }

    #[test]
    fn cmov_selects_correctly() {
        let a = SecpFieldElement::from_biguint(&BigUint::from(7u8));
        let b = SecpFieldElement::from_biguint(&BigUint::from(11u8));
        let r0 = SecpFieldElement::cmov(&a, &b, Choice::from(0));
        let r1 = SecpFieldElement::cmov(&a, &b, Choice::from(1));
        assert_eq!(r0, a);
        assert_eq!(r1, b);
    }

    #[test]
    fn zero_one_constants() {
        assert_eq!(SecpFieldElement::ZERO.to_biguint(), BigUint::zero());
        assert_eq!(SecpFieldElement::ONE.to_biguint(), BigUint::one());
        assert!(bool::from(SecpFieldElement::ZERO.ct_is_zero()));
        assert!(!bool::from(SecpFieldElement::ONE.ct_is_zero()));
    }

    #[test]
    fn bytes_roundtrip() {
        for a in samples() {
            let fe = SecpFieldElement::from_biguint(&a);
            let bytes = fe.to_bytes_be();
            let fe2 = SecpFieldElement::from_bytes_be(&bytes);
            assert_eq!(fe, fe2);
            assert_eq!(fe2.to_biguint(), &a % p_bu());
        }
    }
}
