//! Constant-time projective-coordinate point arithmetic over secp256k1.
//!
//! # Why a separate point type?
//!
//! [`crate::ecc::point::Point`] is the textbook affine-coordinate
//! implementation that backs both secp256k1 and P-256.  Every addition
//! and doubling there computes a modular inverse to normalize the
//! output, which (a) is expensive and (b) — more importantly here —
//! routes through a variable-time field inverse and therefore through
//! `num-bigint` arithmetic that leaks operand magnitudes at the limb
//! level.
//!
//! This module sidesteps both problems for secp256k1 specifically:
//!
//! - **Homogeneous projective coordinates** `(X, Y, Z)` represent the
//!   affine point `(X/Z, Y/Z)`.  The identity is `(0, 1, 0)`.  No
//!   inverses are needed inside the addition or doubling chain — only
//!   one final inverse to convert back to affine.
//! - **Renes–Costello–Batina (2015) complete formulas** for the
//!   `y² = x³ + b` family work uniformly for all input combinations,
//!   including doublings, the identity, and `P + (-P)`.  No branches
//!   on input values are needed, so the formula is a fixed sequence
//!   of [`SecpFieldElement`] adds, subs, and muls — every one of which
//!   is constant-time.
//! - **Field arithmetic via [`SecpFieldElement`]** delegates to the
//!   Montgomery-form `mont_mul` over [`U256`], which is built from
//!   `u64×u64→u128` partial products and `u128` accumulators with
//!   no operand-dependent branching.
//!
//! The Montgomery ladder over this point type therefore has uniform
//! work per scalar bit at every layer of the stack — addition,
//! doubling, multiplication, reduction.  See `SECURITY.md` for the
//! wider hardening picture.
//!
//! # Reference
//!
//! Joost Renes, Craig Costello, Lejla Batina, *Complete addition
//! formulas for prime order elliptic curves*, EUROCRYPT 2016.  The
//! algorithms here are **Algorithm 7** (addition) and **Algorithm 9**
//! (doubling) for the special case `a = 0`, which secp256k1 satisfies.

use super::curve::CurveParams;
use super::field::FieldElement;
use super::point::Point;
use super::secp256k1_field::SecpFieldElement;
use crate::ct_bignum::{Uint, U256};
use num_bigint::BigUint;
use subtle::Choice;

/// Curve coefficient `b = 7` in Montgomery form.
///
/// `7·R mod p = 7·(2^32 + 977) = 0x7_0000_1AB7`.  Verified by
/// `tests::b_constant_is_correct`.
pub const B_FE: SecpFieldElement =
    SecpFieldElement::from_montgomery_unchecked(Uint([0x0000_0007_0000_1AB7, 0, 0, 0]));

/// Precomputed `3·b = 21` in Montgomery form, as it appears in the RCB
/// formulas.
///
/// `21·R mod p = 21·(2^32 + 977) = 0x15_0000_5025`.  Verified by
/// `tests::b3_constant_is_correct`.
pub const B3_FE: SecpFieldElement =
    SecpFieldElement::from_montgomery_unchecked(Uint([0x0000_0015_0000_5025, 0, 0, 0]));

/// A projective-coordinate point on secp256k1.  The triple
/// `(X, Y, Z)` encodes the affine point `(X/Z, Y/Z)`; the identity
/// is `(0, 1, 0)`.
#[derive(Copy, Clone, Debug)]
pub struct ProjectivePoint {
    pub x: SecpFieldElement,
    pub y: SecpFieldElement,
    pub z: SecpFieldElement,
}

impl ProjectivePoint {
    /// The point at infinity (curve identity), `(0, 1, 0)`.
    pub const IDENTITY: ProjectivePoint = ProjectivePoint {
        x: SecpFieldElement::ZERO,
        y: SecpFieldElement::ONE,
        z: SecpFieldElement::ZERO,
    };

    /// Build a projective point from canonical affine coordinates
    /// `(x, y) ∈ [0, p)²`.  The `Z` coordinate is set to 1.  Caller
    /// must ensure the point lies on the curve; this is not checked.
    pub fn from_affine(x: &U256, y: &U256) -> Self {
        ProjectivePoint {
            x: SecpFieldElement::from_canonical(x),
            y: SecpFieldElement::from_canonical(y),
            z: SecpFieldElement::ONE,
        }
    }

    /// Convert back to canonical affine coordinates.  Returns `None`
    /// for the point at infinity (`Z == 0`).
    ///
    /// Performs one field inverse — variable-time inside, but the
    /// inverse routine is implemented via the constant-time Fermat
    /// ladder over Montgomery-form arithmetic.  Acceptable as a final
    /// step of scalar multiplication, where the result is no longer
    /// dependent on per-bit secrets.
    pub fn to_affine(&self) -> Option<(U256, U256)> {
        if bool::from(self.z.ct_is_zero()) {
            return None;
        }
        let z_inv = self.z.inv();
        let x = self.x.mul(&z_inv).to_canonical();
        let y = self.y.mul(&z_inv).to_canonical();
        Some((x, y))
    }

    /// Constant-time check for the point at infinity.
    pub fn is_identity(&self) -> Choice {
        self.z.ct_is_zero()
    }

    /// Constant-time conditional move: returns `b` iff `choice == 1`.
    pub fn cmov(a: &Self, b: &Self, choice: Choice) -> Self {
        ProjectivePoint {
            x: SecpFieldElement::cmov(&a.x, &b.x, choice),
            y: SecpFieldElement::cmov(&a.y, &b.y, choice),
            z: SecpFieldElement::cmov(&a.z, &b.z, choice),
        }
    }

    /// Renes–Costello–Batina **Algorithm 7**: complete addition for
    /// short-Weierstrass curves with `a = 0`.  Works uniformly for all
    /// input combinations — different points, doublings, identity on
    /// either side, and `P + (-P)` — without branching on operand values.
    ///
    /// 12 multiplications + 2 multiplications by `b3` + 22 add/subs.
    pub fn add(&self, other: &Self) -> Self {
        let (x1, y1, z1) = (&self.x, &self.y, &self.z);
        let (x2, y2, z2) = (&other.x, &other.y, &other.z);

        let mut t0 = x1.mul(x2); // 1.  t0 = X1*X2
        let mut t1 = y1.mul(y2); // 2.  t1 = Y1*Y2
        let mut t2 = z1.mul(z2); // 3.  t2 = Z1*Z2
        let mut t3 = x1.add(y1); // 4.  t3 = X1+Y1
        let mut t4 = x2.add(y2); // 5.  t4 = X2+Y2
        t3 = t3.mul(&t4); // 6.  t3 = t3*t4
        t4 = t0.add(&t1); // 7.  t4 = t0+t1
        t3 = t3.sub(&t4); // 8.  t3 = t3-t4
        t4 = y1.add(z1); // 9.  t4 = Y1+Z1
        let mut x3 = y2.add(z2); // 10. X3 = Y2+Z2
        t4 = t4.mul(&x3); // 11. t4 = t4*X3
        x3 = t1.add(&t2); // 12. X3 = t1+t2
        t4 = t4.sub(&x3); // 13. t4 = t4-X3
        x3 = x1.add(z1); // 14. X3 = X1+Z1
        let mut y3 = x2.add(z2); // 15. Y3 = X2+Z2
        x3 = x3.mul(&y3); // 16. X3 = X3*Y3
        y3 = t0.add(&t2); // 17. Y3 = t0+t2
        y3 = x3.sub(&y3); // 18. Y3 = X3-Y3
        x3 = t0.add(&t0); // 19. X3 = t0+t0
        t0 = x3.add(&t0); // 20. t0 = X3+t0
        t2 = B3_FE.mul(&t2); // 21. t2 = b3*t2
        let mut z3 = t1.add(&t2); // 22. Z3 = t1+t2
        t1 = t1.sub(&t2); // 23. t1 = t1-t2
        y3 = B3_FE.mul(&y3); // 24. Y3 = b3*Y3
        x3 = t4.mul(&y3); // 25. X3 = t4*Y3
        t2 = t3.mul(&t1); // 26. t2 = t3*t1
        x3 = t2.sub(&x3); // 27. X3 = t2-X3
        y3 = y3.mul(&t0); // 28. Y3 = Y3*t0
        t1 = t1.mul(&z3); // 29. t1 = t1*Z3
        y3 = t1.add(&y3); // 30. Y3 = t1+Y3
        t0 = t0.mul(&t3); // 31. t0 = t0*t3
        z3 = z3.mul(&t4); // 32. Z3 = Z3*t4
        z3 = z3.add(&t0); // 33. Z3 = Z3+t0

        ProjectivePoint {
            x: x3,
            y: y3,
            z: z3,
        }
    }

    /// Renes–Costello–Batina **Algorithm 9**: complete doubling for
    /// short-Weierstrass curves with `a = 0`.  6 multiplications +
    /// 2 multiplications by `b3` + 9 add/subs.  Faster than calling
    /// `add(self, self)` because the formula exploits the equality.
    pub fn double(&self) -> Self {
        let (x, y, z) = (&self.x, &self.y, &self.z);

        let mut t0 = y.mul(y); // 1.  t0 = Y*Y
        let mut z3 = t0.add(&t0); // 2.  Z3 = t0+t0
        z3 = z3.add(&z3); // 3.  Z3 = Z3+Z3
        z3 = z3.add(&z3); // 4.  Z3 = Z3+Z3
        let mut t1 = y.mul(z); // 5.  t1 = Y*Z
        let mut t2 = z.mul(z); // 6.  t2 = Z*Z
        t2 = B3_FE.mul(&t2); // 7.  t2 = b3*t2
        let mut x3 = t2.mul(&z3); // 8.  X3 = t2*Z3
        let mut y3 = t0.add(&t2); // 9.  Y3 = t0+t2
        z3 = t1.mul(&z3); // 10. Z3 = t1*Z3
        t1 = t2.add(&t2); // 11. t1 = t2+t2
        t2 = t1.add(&t2); // 12. t2 = t1+t2
        t0 = t0.sub(&t2); // 13. t0 = t0-t2
        y3 = t0.mul(&y3); // 14. Y3 = t0*Y3
        y3 = x3.add(&y3); // 15. Y3 = X3+Y3
        t1 = x.mul(y); // 16. t1 = X*Y
        x3 = t0.mul(&t1); // 17. X3 = t0*t1
        x3 = x3.add(&x3); // 18. X3 = X3+X3

        ProjectivePoint {
            x: x3,
            y: y3,
            z: z3,
        }
    }

    /// Negate a point: `-(X, Y, Z) = (X, -Y, Z)`.
    pub fn neg(&self) -> Self {
        ProjectivePoint {
            x: self.x,
            y: self.y.neg(),
            z: self.z,
        }
    }

    /// Construct a `ProjectivePoint` from a textbook affine `Point`,
    /// converting the field elements via the canonical bignum
    /// representation.  The point at infinity maps to
    /// [`ProjectivePoint::IDENTITY`].
    pub fn from_textbook(p: &Point) -> Self {
        match p {
            Point::Infinity => ProjectivePoint::IDENTITY,
            Point::Affine { x, y } => ProjectivePoint::from_affine(
                &U256::from_biguint(&x.value),
                &U256::from_biguint(&y.value),
            ),
        }
    }

    /// Convert back to a textbook affine `Point` over the given prime
    /// modulus.  Returns [`Point::Infinity`] when `Z == 0`.
    pub fn to_textbook(&self, p: &BigUint) -> Point {
        match self.to_affine() {
            None => Point::Infinity,
            Some((x_u, y_u)) => Point::Affine {
                x: FieldElement::new(x_u.to_biguint(), p.clone()),
                y: FieldElement::new(y_u.to_biguint(), p.clone()),
            },
        }
    }

    /// Scalar multiplication via the Montgomery ladder, processing
    /// `scalar_bits` bits MSB-first.
    ///
    /// Every iteration performs **exactly one** addition and one
    /// doubling, regardless of the bit value.  The bit-driven branch
    /// is replaced with [`ProjectivePoint::cmov`] over the two
    /// candidate next-states, so on the Rust source level there is no
    /// `if`/`else` keyed on a secret bit.
    ///
    /// Caller specifies `scalar_bits` so the iteration count is fixed
    /// regardless of the position of the most-significant set bit of
    /// `k`.  For secp256k1 secrets this should be the curve order's
    /// bit length (256), not `k.bits()`.
    pub fn scalar_mul_ct(&self, k: &BigUint, scalar_bits: usize) -> Self {
        let mut r0 = ProjectivePoint::IDENTITY;
        let mut r1 = *self;
        for i in (0..scalar_bits).rev() {
            let bit = Choice::from(k.bit(i as u64) as u8);

            // Compute every candidate next-state up front; cmov picks.
            let sum = r0.add(&r1);
            let r0_dbl = r0.double();
            let r1_dbl = r1.double();
            // bit == 1: r0 ← sum,    r1 ← r1_dbl
            // bit == 0: r0 ← r0_dbl, r1 ← sum
            r0 = ProjectivePoint::cmov(&r0_dbl, &sum, bit);
            r1 = ProjectivePoint::cmov(&sum, &r1_dbl, bit);
        }
        r0
    }
}

/// Drop-in constant-time scalar multiplication for **secp256k1 only**:
/// converts `point` into projective form, runs the
/// [`ProjectivePoint::scalar_mul_ct`] Montgomery ladder over the
/// Renes–Costello–Batina formulas, and returns the result as a
/// textbook [`Point`] for compatibility with the existing ECDH /
/// ECDSA code paths.
///
/// Falls back to the textbook affine [`Point::scalar_mul_ct`] for any
/// other curve, since the projective formulas in this module assume
/// `a = 0` (which only secp256k1 satisfies among the curves the crate
/// supports).
///
/// Use this for **secret** scalars only.  Public-input scalar
/// multiplications (the ECDSA verifier's `u₁·G + u₂·Q`) should keep
/// using the variable-time but faster [`Point::scalar_mul`].
pub fn ct_scalar_mul(point: &Point, k: &BigUint, curve: &CurveParams) -> Point {
    if curve.name == "secp256k1" {
        let pp = ProjectivePoint::from_textbook(point);
        let out = pp.scalar_mul_ct(k, curve.order_bits());
        out.to_textbook(&curve.p)
    } else {
        // Other curves (P-256) fall back to the affine ladder.  The
        // affine ladder still has the operation-count uniformity
        // property; what it lacks is the limb-level constant-time
        // field arithmetic that this module's projective ladder gets
        // from `SecpFieldElement`.
        point.scalar_mul_ct(k, &curve.a_fe(), curve.order_bits())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ecc::curve::CurveParams;
    use crate::ecc::field::FieldElement;
    use crate::ecc::point::Point;
    use num_bigint::BigUint;
    use num_traits::Zero;

    fn secp() -> CurveParams {
        CurveParams::secp256k1()
    }

    /// Convert a textbook `Point` to a `ProjectivePoint` for cross-checking.
    fn proj_from_textbook(p: &Point) -> ProjectivePoint {
        match p {
            Point::Infinity => ProjectivePoint::IDENTITY,
            Point::Affine { x, y } => {
                let xu = U256::from_biguint(&x.value);
                let yu = U256::from_biguint(&y.value);
                ProjectivePoint::from_affine(&xu, &yu)
            }
        }
    }

    /// Compare a `ProjectivePoint` to a textbook `Point` by mapping the
    /// projective one back to affine and comparing canonical coordinates.
    fn proj_eq_textbook(pp: &ProjectivePoint, p: &Point) -> bool {
        match (pp.to_affine(), p) {
            (None, Point::Infinity) => true,
            (Some((x, y)), Point::Affine { x: xf, y: yf }) => {
                x.to_biguint() == xf.value && y.to_biguint() == yf.value
            }
            _ => false,
        }
    }

    #[test]
    fn b_constant_is_correct() {
        let want = SecpFieldElement::from_biguint(&BigUint::from(7u8));
        assert_eq!(B_FE, want);
    }

    #[test]
    fn b3_constant_is_correct() {
        let want = SecpFieldElement::from_biguint(&BigUint::from(21u8));
        assert_eq!(B3_FE, want);
    }

    #[test]
    fn identity_to_affine_is_none() {
        assert!(ProjectivePoint::IDENTITY.to_affine().is_none());
        assert!(bool::from(ProjectivePoint::IDENTITY.is_identity()));
    }

    #[test]
    fn from_affine_roundtrips() {
        let g = secp().generator();
        let (gx_bu, gy_bu) = match &g {
            Point::Affine { x, y } => (x.value.clone(), y.value.clone()),
            Point::Infinity => panic!("generator is not infinity"),
        };
        let pp =
            ProjectivePoint::from_affine(&U256::from_biguint(&gx_bu), &U256::from_biguint(&gy_bu));
        let (x_back, y_back) = pp.to_affine().unwrap();
        assert_eq!(x_back.to_biguint(), gx_bu);
        assert_eq!(y_back.to_biguint(), gy_bu);
    }

    #[test]
    fn add_matches_textbook_for_distinct_points() {
        let curve = secp();
        let g = curve.generator();
        let a = curve.a_fe();
        let g2 = g.double(&a);
        let g3_textbook = g.add(&g2, &a);

        let pg = proj_from_textbook(&g);
        let pg2 = proj_from_textbook(&g2);
        let pg3 = pg.add(&pg2);

        assert!(proj_eq_textbook(&pg3, &g3_textbook));
    }

    #[test]
    fn add_matches_textbook_for_doubling_via_add() {
        let curve = secp();
        let g = curve.generator();
        let a = curve.a_fe();
        let g2_textbook = g.double(&a);

        let pg = proj_from_textbook(&g);
        let pg_plus_pg = pg.add(&pg);

        assert!(proj_eq_textbook(&pg_plus_pg, &g2_textbook));
    }

    #[test]
    fn double_matches_textbook() {
        let curve = secp();
        let g = curve.generator();
        let a = curve.a_fe();
        let g2_textbook = g.double(&a);

        let pg = proj_from_textbook(&g);
        let pg2 = pg.double();

        assert!(proj_eq_textbook(&pg2, &g2_textbook));
    }

    #[test]
    fn add_with_identity_is_identity_law() {
        let g = secp().generator();
        let pg = proj_from_textbook(&g);
        let lhs = pg.add(&ProjectivePoint::IDENTITY);
        let rhs = ProjectivePoint::IDENTITY.add(&pg);
        assert!(proj_eq_textbook(&lhs, &g));
        assert!(proj_eq_textbook(&rhs, &g));
    }

    #[test]
    fn add_with_neg_yields_identity() {
        let g = secp().generator();
        let pg = proj_from_textbook(&g);
        let neg_pg = pg.neg();
        let sum = pg.add(&neg_pg);
        assert!(bool::from(sum.is_identity()));
    }

    #[test]
    fn scalar_mul_ct_matches_textbook_small_scalars() {
        let curve = secp();
        let g = curve.generator();
        let a_fe = curve.a_fe();
        let pg = proj_from_textbook(&g);
        for k in 0u64..=10 {
            let k_bu = BigUint::from(k);
            let want = g.scalar_mul_ct(&k_bu, &a_fe, 4);
            let got = pg.scalar_mul_ct(&k_bu, 4);
            assert!(proj_eq_textbook(&got, &want), "mismatch at k={}", k);
        }
    }

    #[test]
    fn scalar_mul_ct_matches_textbook_full_size_scalars() {
        let curve = secp();
        let g = curve.generator();
        let a_fe = curve.a_fe();
        let pg = proj_from_textbook(&g);
        let bits = curve.order_bits();
        for k_hex in [
            "1",
            "2",
            "deadbeef",
            // Just under the curve order
            "fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364140",
            // Random 256-bit value (fits in scalar range)
            "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        ] {
            let k = BigUint::parse_bytes(k_hex.as_bytes(), 16).unwrap();
            let want = g.scalar_mul_ct(&k, &a_fe, bits);
            let got = pg.scalar_mul_ct(&k, bits);
            assert!(proj_eq_textbook(&got, &want), "mismatch at k={}", k_hex);
        }
    }

    #[test]
    fn cmov_selects_correctly() {
        let g = secp().generator();
        let pg = proj_from_textbook(&g);
        let id = ProjectivePoint::IDENTITY;

        let r0 = ProjectivePoint::cmov(&pg, &id, Choice::from(0));
        let r1 = ProjectivePoint::cmov(&pg, &id, Choice::from(1));

        assert!(proj_eq_textbook(&r0, &g));
        assert!(bool::from(r1.is_identity()));
    }

    /// Sanity: scalar mul by curve order should yield identity.
    #[test]
    fn scalar_mul_by_order_is_identity() {
        let curve = secp();
        let g = curve.generator();
        let pg = proj_from_textbook(&g);
        let n = curve.n.clone();
        let bits = curve.order_bits();
        let result = pg.scalar_mul_ct(&n, bits);
        assert!(bool::from(result.is_identity()));
        // (Defeat unused-import warning for FieldElement if reached here.)
        let _ = FieldElement::zero(BigUint::from(7u8));
    }

    /// Sanity: doubling identity stays identity.
    #[test]
    fn double_identity_is_identity() {
        let r = ProjectivePoint::IDENTITY.double();
        assert!(bool::from(r.is_identity()));
        // Suppress `Zero`-import warning if test set narrows.
        let _ = BigUint::zero();
    }
}
