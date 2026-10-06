//! Constant-time projective-coordinate point arithmetic over P-256.
//!
//! Mirrors [`crate::ecc::secp256k1_point`], but specialised for
//! P-256's curve parameters (`a = -3 mod p`, generic `b`).  Where
//! secp256k1 used the Renes–Costello–Batina algorithms specialised to
//! `a = 0` (Algorithms 7 + 9), this module uses the general-`a`
//! complete formulas (**Algorithm 1** for addition, **Algorithm 3**
//! for doubling) with `a` and `b3 = 3b` carried as
//! [`P256FieldElement`] constants.  Algorithm 1 has 12 multiplications
//! + 3 multiplications by `a` + 2 multiplications by `b3` per
//!   addition; Algorithm 3 has 8 + 3·a + 2·b3 per doubling.  Both
//!   formulas are *complete* — they work uniformly for distinct points,
//!   doublings, the identity on either side, and `P + (-P)`, with no
//!   branches on input values.
//!
//! The Montgomery ladder over this point type replaces the bit-driven
//! `if` with [`P256FieldElement::cmov`] over candidate next-states,
//! matching the constant-time profile of the secp256k1 ladder.

use super::curve::CurveParams;
use super::field::FieldElement;
use super::p256_field::P256FieldElement;
use super::point::Point;
use crate::ct_bignum::{Uint, U256};
use num_bigint::BigUint;
use subtle::Choice;

/// Curve coefficient `a = -3 mod p` in Montgomery form.
///
/// `(p - 3)·R mod p` — verified by `tests::a_constant_is_correct`.
pub const A_FE: P256FieldElement = P256FieldElement::from_montgomery_unchecked(Uint([
    0xFFFF_FFFF_FFFF_FFFC,
    0x0000_0003_FFFF_FFFF,
    0x0000_0000_0000_0000,
    0xFFFF_FFFC_0000_0004,
]));

/// Curve coefficient `b` (from y² = x³ + ax + b) in Montgomery form.
/// `b·R mod p`.  Verified by `tests::b_constant_is_correct`.
pub const B_FE: P256FieldElement = P256FieldElement::from_montgomery_unchecked(Uint([
    0xD89C_DF62_29C4_BDDF,
    0xACF0_05CD_7884_3090,
    0xE5A2_20AB_F721_2ED6,
    0xDC30_061D_0487_4834,
]));

/// `3·b` in Montgomery form, as it appears in the RCB formulas.
/// Verified by `tests::b3_constant_is_correct`.
pub const B3_FE: P256FieldElement = P256FieldElement::from_montgomery_unchecked(Uint([
    0x89D6_9E26_7D4E_399F,
    0x06D0_1166_698C_91B2,
    0xB0E6_6203_E563_8C84,
    0x9490_1259_0D95_D89C,
]));

/// A projective-coordinate point on P-256.  Encoding identical to
/// [`crate::ecc::secp256k1_point::ProjectivePoint`] — the identity is
/// `(0, 1, 0)`.
#[derive(Copy, Clone, Debug)]
pub struct P256ProjectivePoint {
    pub x: P256FieldElement,
    pub y: P256FieldElement,
    pub z: P256FieldElement,
}

impl P256ProjectivePoint {
    pub const IDENTITY: P256ProjectivePoint = P256ProjectivePoint {
        x: P256FieldElement::ZERO,
        y: P256FieldElement::ONE,
        z: P256FieldElement::ZERO,
    };

    pub fn from_affine(x: &U256, y: &U256) -> Self {
        P256ProjectivePoint {
            x: P256FieldElement::from_canonical(x),
            y: P256FieldElement::from_canonical(y),
            z: P256FieldElement::ONE,
        }
    }

    pub fn to_affine(&self) -> Option<(U256, U256)> {
        if bool::from(self.z.ct_is_zero()) {
            return None;
        }
        let z_inv = self.z.inv();
        let x = self.x.mul(&z_inv).to_canonical();
        let y = self.y.mul(&z_inv).to_canonical();
        Some((x, y))
    }

    pub fn is_identity(&self) -> Choice {
        self.z.ct_is_zero()
    }

    pub fn cmov(a: &Self, b: &Self, choice: Choice) -> Self {
        P256ProjectivePoint {
            x: P256FieldElement::cmov(&a.x, &b.x, choice),
            y: P256FieldElement::cmov(&a.y, &b.y, choice),
            z: P256FieldElement::cmov(&a.z, &b.z, choice),
        }
    }

    pub fn from_textbook(p: &Point) -> Self {
        match p {
            Point::Infinity => P256ProjectivePoint::IDENTITY,
            Point::Affine { x, y } => P256ProjectivePoint::from_affine(
                &U256::from_biguint(&x.value),
                &U256::from_biguint(&y.value),
            ),
        }
    }

    pub fn to_textbook(&self, p: &BigUint) -> Point {
        match self.to_affine() {
            None => Point::Infinity,
            Some((x_u, y_u)) => Point::Affine {
                x: FieldElement::new(x_u.to_biguint(), p.clone()),
                y: FieldElement::new(y_u.to_biguint(), p.clone()),
            },
        }
    }

    /// Renes–Costello–Batina **Algorithm 1**: complete addition for
    /// arbitrary short Weierstrass curves.  17 multiplications total
    /// (12 generic + 3·a + 2·b3) and 22 add/subs.
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
        t4 = x1.add(z1); // 9.  t4 = X1+Z1
        let mut t5 = x2.add(z2); // 10. t5 = X2+Z2
        t4 = t4.mul(&t5); // 11. t4 = t4*t5
        t5 = t0.add(&t2); // 12. t5 = t0+t2
        t4 = t4.sub(&t5); // 13. t4 = t4-t5
        t5 = y1.add(z1); // 14. t5 = Y1+Z1
        let mut x3 = y2.add(z2); // 15. X3 = Y2+Z2
        t5 = t5.mul(&x3); // 16. t5 = t5*X3
        x3 = t1.add(&t2); // 17. X3 = t1+t2
        t5 = t5.sub(&x3); // 18. t5 = t5-X3
        let mut z3 = A_FE.mul(&t4); // 19. Z3 = a*t4
        x3 = B3_FE.mul(&t2); // 20. X3 = b3*t2
        z3 = x3.add(&z3); // 21. Z3 = X3+Z3
        x3 = t1.sub(&z3); // 22. X3 = t1-Z3
        z3 = t1.add(&z3); // 23. Z3 = t1+Z3
        let mut y3 = x3.mul(&z3); // 24. Y3 = X3*Z3
        t1 = t0.add(&t0); // 25. t1 = t0+t0
        t1 = t1.add(&t0); // 26. t1 = t1+t0
        t2 = A_FE.mul(&t2); // 27. t2 = a*t2
        t4 = B3_FE.mul(&t4); // 28. t4 = b3*t4
        t1 = t1.add(&t2); // 29. t1 = t1+t2
        t2 = t0.sub(&t2); // 30. t2 = t0-t2
        t2 = A_FE.mul(&t2); // 31. t2 = a*t2
        t4 = t4.add(&t2); // 32. t4 = t4+t2
        t0 = t1.mul(&t4); // 33. t0 = t1*t4
        y3 = y3.add(&t0); // 34. Y3 = Y3+t0
        t0 = t5.mul(&t4); // 35. t0 = t5*t4
        x3 = t3.mul(&x3); // 36. X3 = t3*X3
        x3 = x3.sub(&t0); // 37. X3 = X3-t0
        t0 = t3.mul(&t1); // 38. t0 = t3*t1
        z3 = t5.mul(&z3); // 39. Z3 = t5*Z3
        z3 = z3.add(&t0); // 40. Z3 = Z3+t0

        P256ProjectivePoint {
            x: x3,
            y: y3,
            z: z3,
        }
    }

    /// Renes–Costello–Batina **Algorithm 3**: complete doubling for
    /// arbitrary short Weierstrass curves.  13 multiplications total
    /// (8 generic + 3·a + 2·b3) and 14 add/subs.
    pub fn double(&self) -> Self {
        let (x, y, z) = (&self.x, &self.y, &self.z);

        let mut t0 = x.mul(x); // 1.  t0 = X*X
        let t1 = y.mul(y); // 2.  t1 = Y*Y
        let mut t2 = z.mul(z); // 3.  t2 = Z*Z
        let mut t3 = x.mul(y); // 4.  t3 = X*Y
        t3 = t3.add(&t3); // 5.  t3 = t3+t3
        let mut z3 = x.mul(z); // 6.  Z3 = X*Z
        z3 = z3.add(&z3); // 7.  Z3 = Z3+Z3
        let mut x3 = A_FE.mul(&z3); // 8.  X3 = a*Z3
        let mut y3 = B3_FE.mul(&t2); // 9.  Y3 = b3*t2
        y3 = x3.add(&y3); // 10. Y3 = X3+Y3
        x3 = t1.sub(&y3); // 11. X3 = t1-Y3
        y3 = t1.add(&y3); // 12. Y3 = t1+Y3
        y3 = x3.mul(&y3); // 13. Y3 = X3*Y3
        x3 = t3.mul(&x3); // 14. X3 = t3*X3
        z3 = B3_FE.mul(&z3); // 15. Z3 = b3*Z3
        t2 = A_FE.mul(&t2); // 16. t2 = a*t2
        t3 = t0.sub(&t2); // 17. t3 = t0-t2
        t3 = A_FE.mul(&t3); // 18. t3 = a*t3
        t3 = t3.add(&z3); // 19. t3 = t3+Z3
        z3 = t0.add(&t0); // 20. Z3 = t0+t0
        t0 = z3.add(&t0); // 21. t0 = Z3+t0
        t0 = t0.add(&t2); // 22. t0 = t0+t2
        t0 = t0.mul(&t3); // 23. t0 = t0*t3
        y3 = y3.add(&t0); // 24. Y3 = Y3+t0
        t2 = y.mul(z); // 25. t2 = Y*Z
        t2 = t2.add(&t2); // 26. t2 = t2+t2
        t0 = t2.mul(&t3); // 27. t0 = t2*t3
        x3 = x3.sub(&t0); // 28. X3 = X3-t0
        z3 = t2.mul(&t1); // 29. Z3 = t2*t1
        z3 = z3.add(&z3); // 30. Z3 = Z3+Z3
        z3 = z3.add(&z3); // 31. Z3 = Z3+Z3

        P256ProjectivePoint {
            x: x3,
            y: y3,
            z: z3,
        }
    }

    pub fn neg(&self) -> Self {
        P256ProjectivePoint {
            x: self.x,
            y: self.y.neg(),
            z: self.z,
        }
    }

    /// Constant-time scalar multiplication via the Montgomery ladder.
    /// Same shape as
    /// [`crate::ecc::secp256k1_point::ProjectivePoint::scalar_mul_ct`]:
    /// uniform per-bit work (one add + one double), cmov-driven
    /// re-binding, fixed iteration count.
    pub fn scalar_mul_ct(&self, k: &BigUint, scalar_bits: usize) -> Self {
        let mut r0 = P256ProjectivePoint::IDENTITY;
        let mut r1 = *self;
        for i in (0..scalar_bits).rev() {
            let bit = Choice::from(k.bit(i as u64) as u8);
            let sum = r0.add(&r1);
            let r0_dbl = r0.double();
            let r1_dbl = r1.double();
            r0 = P256ProjectivePoint::cmov(&r0_dbl, &sum, bit);
            r1 = P256ProjectivePoint::cmov(&sum, &r1_dbl, bit);
        }
        r0
    }
}

/// Drop-in CT scalar multiplication for **P-256** that returns a
/// textbook [`Point`].  Companion to
/// [`crate::ecc::secp256k1_point::ct_scalar_mul`]; the unified
/// dispatcher in [`crate::ecc::ct`] picks the right one based on
/// `curve.name`.
pub fn ct_scalar_mul_p256(point: &Point, k: &BigUint, curve: &CurveParams) -> Point {
    let pp = P256ProjectivePoint::from_textbook(point);
    let out = pp.scalar_mul_ct(k, curve.order_bits());
    out.to_textbook(&curve.p)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ecc::curve::CurveParams;
    use crate::ecc::point::Point;
    use num_bigint::BigUint;

    fn p256() -> CurveParams {
        CurveParams::p256()
    }

    fn proj_eq_textbook(pp: &P256ProjectivePoint, p: &Point) -> bool {
        match (pp.to_affine(), p) {
            (None, Point::Infinity) => true,
            (Some((x, y)), Point::Affine { x: xf, y: yf }) => {
                x.to_biguint() == xf.value && y.to_biguint() == yf.value
            }
            _ => false,
        }
    }

    #[test]
    fn a_constant_is_correct() {
        // -3 mod p == p - 3
        let p_minus_3 = &p256().p - 3u8;
        let want = P256FieldElement::from_biguint(&p_minus_3);
        assert_eq!(A_FE, want);
    }

    #[test]
    fn b_constant_is_correct() {
        let want = P256FieldElement::from_biguint(&p256().b);
        assert_eq!(B_FE, want);
    }

    #[test]
    fn b3_constant_is_correct() {
        let want = P256FieldElement::from_biguint(&((&p256().b * 3u8) % &p256().p));
        assert_eq!(B3_FE, want);
    }

    #[test]
    fn from_affine_roundtrips() {
        let g = p256().generator();
        let (gx, gy) = match &g {
            Point::Affine { x, y } => (x.value.clone(), y.value.clone()),
            Point::Infinity => panic!(),
        };
        let pp =
            P256ProjectivePoint::from_affine(&U256::from_biguint(&gx), &U256::from_biguint(&gy));
        let (xb, yb) = pp.to_affine().unwrap();
        assert_eq!(xb.to_biguint(), gx);
        assert_eq!(yb.to_biguint(), gy);
    }

    #[test]
    fn add_matches_textbook_for_distinct_points() {
        let curve = p256();
        let g = curve.generator();
        let a = curve.a_fe();
        let g2 = g.double(&a);
        let g3 = g.add(&g2, &a);

        let pg = P256ProjectivePoint::from_textbook(&g);
        let pg2 = P256ProjectivePoint::from_textbook(&g2);
        assert!(proj_eq_textbook(&pg.add(&pg2), &g3));
    }

    #[test]
    fn add_matches_textbook_for_doubling_via_add() {
        let curve = p256();
        let g = curve.generator();
        let a = curve.a_fe();
        let g2 = g.double(&a);

        let pg = P256ProjectivePoint::from_textbook(&g);
        assert!(proj_eq_textbook(&pg.add(&pg), &g2));
    }

    #[test]
    fn double_matches_textbook() {
        let curve = p256();
        let g = curve.generator();
        let a = curve.a_fe();
        let g2 = g.double(&a);

        let pg = P256ProjectivePoint::from_textbook(&g);
        assert!(proj_eq_textbook(&pg.double(), &g2));
    }

    #[test]
    fn add_with_identity_law() {
        let g = p256().generator();
        let pg = P256ProjectivePoint::from_textbook(&g);
        assert!(proj_eq_textbook(
            &pg.add(&P256ProjectivePoint::IDENTITY),
            &g
        ));
        assert!(proj_eq_textbook(
            &P256ProjectivePoint::IDENTITY.add(&pg),
            &g
        ));
    }

    #[test]
    fn add_with_neg_yields_identity() {
        let g = p256().generator();
        let pg = P256ProjectivePoint::from_textbook(&g);
        let sum = pg.add(&pg.neg());
        assert!(bool::from(sum.is_identity()));
    }

    #[test]
    fn scalar_mul_ct_matches_textbook_full_size_scalars() {
        let curve = p256();
        let g = curve.generator();
        let a_fe = curve.a_fe();
        let pg = P256ProjectivePoint::from_textbook(&g);
        let bits = curve.order_bits();
        for k_hex in [
            "1",
            "2",
            "deadbeef",
            "ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632550",
            "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        ] {
            let k = BigUint::parse_bytes(k_hex.as_bytes(), 16).unwrap();
            let want = g.scalar_mul_ct(&k, &a_fe, bits);
            let got = pg.scalar_mul_ct(&k, bits);
            assert!(proj_eq_textbook(&got, &want), "mismatch at k={}", k_hex);
        }
    }

    #[test]
    fn scalar_mul_by_order_is_identity() {
        let curve = p256();
        let g = curve.generator();
        let pg = P256ProjectivePoint::from_textbook(&g);
        let result = pg.scalar_mul_ct(&curve.n, curve.order_bits());
        assert!(bool::from(result.is_identity()));
    }

    #[test]
    fn external_kat_matches_via_projective() {
        // Derive Q = d·G for the P-256 KAT private key used in
        // ecdsa.rs / ecdh.rs cross-checks.  Then verify the
        // projective ladder lands on the same (x, y) as the
        // textbook ladder.
        let curve = p256();
        let g = curve.generator();
        let a_fe = curve.a_fe();
        let d_hex = "C9AFA9D845BA75166B5C215767B1D6934E50C3DB36E89B127B8A622B120F6721";
        let d = BigUint::parse_bytes(d_hex.as_bytes(), 16).unwrap();
        let want = g.scalar_mul_ct(&d, &a_fe, curve.order_bits());

        let pg = P256ProjectivePoint::from_textbook(&g);
        let got = pg.scalar_mul_ct(&d, curve.order_bits());
        assert!(proj_eq_textbook(&got, &want));
    }
}
