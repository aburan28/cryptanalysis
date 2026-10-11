//! Elliptic curve point arithmetic over short Weierstrass curves: y² = x³ + ax + b (mod p).
//!
//! # Point addition
//! For P ≠ Q and P ≠ -Q:
//!   λ = (y₂ - y₁) / (x₂ - x₁)
//!   x₃ = λ² - x₁ - x₂
//!   y₃ = λ(x₁ - x₃) - y₁
//!
//! # Point doubling (P = Q)
//!   λ = (3x² + a) / (2y)
//!   x₃ = λ² - 2x
//!   y₃ = λ(x - x₃) - y
//!
//! # Scalar multiplication
//! Uses the double-and-add algorithm: scan bits of k from LSB to MSB,
//! doubling the accumulator each step and adding P when the bit is 1.
//! This is O(log k) point operations.

use super::field::FieldElement;
use num_bigint::BigUint;
use num_traits::{One, Zero};

/// A point on a Weierstrass curve, either the identity (point at infinity)
/// or an affine coordinate pair.
#[derive(Clone, Debug, PartialEq)]
pub enum Point {
    Infinity,
    Affine { x: FieldElement, y: FieldElement },
}

impl Point {
    /// Add two curve points. `a` is the curve coefficient from y²=x³+ax+b.
    pub fn add(&self, other: &Point, a: &FieldElement) -> Point {
        match (self, other) {
            (Point::Infinity, p) | (p, Point::Infinity) => p.clone(),
            (Point::Affine { x: x1, y: y1 }, Point::Affine { x: x2, y: y2 }) => {
                if x1 == x2 {
                    if y1 == y2 {
                        // Same point → double
                        return self.double(a);
                    } else {
                        // P + (-P) = ∞
                        return Point::Infinity;
                    }
                }
                // λ = (y2 - y1) / (x2 - x1)
                let lambda = y2.sub(y1).mul(&x2.sub(x1).inv().unwrap());
                let x3 = lambda.mul(&lambda).sub(x1).sub(x2);
                let y3 = lambda.mul(&x1.sub(&x3)).sub(y1);
                Point::Affine { x: x3, y: y3 }
            }
        }
    }

    /// Double a point: 2P.
    pub fn double(&self, a: &FieldElement) -> Point {
        match self {
            Point::Infinity => Point::Infinity,
            Point::Affine { x, y } => {
                if y.is_zero() {
                    return Point::Infinity;
                }
                let p = x.modulus.clone();
                let three = FieldElement::new(BigUint::from(3u32), p.clone());
                let two = FieldElement::new(BigUint::from(2u32), p);

                // λ = (3x² + a) / (2y)
                let numerator = three.mul(&x.mul(x)).add(a);
                let denominator = two.mul(y);
                let lambda = numerator.mul(&denominator.inv().unwrap());

                let x3 = lambda.mul(&lambda).sub(&two.mul(x));
                let y3 = lambda.mul(&x.sub(&x3)).sub(y);
                Point::Affine { x: x3, y: y3 }
            }
        }
    }

    /// Scalar multiplication kP using the double-and-add algorithm.
    ///
    /// Security note: this implementation is NOT constant-time and is
    /// vulnerable to timing side-channels.  Use [`Point::scalar_mul_ct`]
    /// for secret scalars.  This variable-time variant is appropriate
    /// only for public-input scalar multiplications, e.g. the verifier's
    /// `u1·G + u2·Q` in ECDSA verification.
    pub fn scalar_mul(&self, k: &BigUint, a: &FieldElement) -> Point {
        let mut result = Point::Infinity;
        let mut addend = self.clone();
        let mut k = k.clone();
        let one = BigUint::one();

        while !k.is_zero() {
            if &k & &one == one {
                result = result.add(&addend, a);
            }
            addend = addend.double(a);
            k >>= 1;
        }
        result
    }

    /// Scalar multiplication kP using the Montgomery ladder, processing
    /// `scalar_bits` bits MSB-first.  Every iteration performs exactly
    /// one point addition and one point doubling, regardless of the bit
    /// value, so the *operation count* no longer depends on the
    /// scalar's bit pattern.  Iteration count is fixed at `scalar_bits`,
    /// so the runtime no longer scales with the position of the
    /// most-significant set bit.
    ///
    /// Security caveats (read carefully):
    ///
    /// - The branch that re-binds `(r0, r1)` after each step is a
    ///   plain Rust `if`.  The two branches assign the same set of
    ///   precomputed values in different orders, but the compiler is
    ///   free to emit a conditional jump.  This still closes the
    ///   coarse-grained "count operations to count set bits" leak that
    ///   double-and-add has.
    /// - The underlying field arithmetic uses `num-bigint`, which is
    ///   *not* constant-time at the limb level.  An attacker with
    ///   fine-grained timing access can still extract information from
    ///   individual `FieldElement::mul` / `inv` operations.  Fixing
    ///   that requires replacing `num-bigint` with a fixed-width,
    ///   constant-time bignum (out of scope for this change).
    ///
    /// In other words: this is a real improvement over double-and-add,
    /// but it does not make ECC operations side-channel safe.  See
    /// `SECURITY.md` for the full picture.
    pub fn scalar_mul_ct(&self, k: &BigUint, a: &FieldElement, scalar_bits: usize) -> Point {
        let mut r0 = Point::Infinity;
        let mut r1 = self.clone();

        for i in (0..scalar_bits).rev() {
            let bit = k.bit(i as u64);

            // Always compute all three potential next states so the
            // operation count is independent of `bit`.
            let sum = r0.add(&r1, a);
            let r0_dbl = r0.double(a);
            let r1_dbl = r1.double(a);

            // Re-bind (r0, r1) according to the current bit.  Both
            // arms assign exactly two values; the work is the same.
            if bit {
                r0 = sum;
                r1 = r1_dbl;
            } else {
                r0 = r0_dbl;
                r1 = sum;
            }
        }
        r0
    }

    /// Negate a point: -P = (x, -y mod p).
    pub fn neg(&self) -> Point {
        match self {
            Point::Infinity => Point::Infinity,
            Point::Affine { x, y } => Point::Affine {
                x: x.clone(),
                y: y.neg(),
            },
        }
    }

    /// Return the x-coordinate as a `BigUint`, or `None` for the point at infinity.
    pub fn x_coord(&self) -> Option<&BigUint> {
        match self {
            Point::Affine { x, .. } => Some(&x.value),
            Point::Infinity => None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Small curve for testing: y² = x³ + 2x + 3 mod 97
    /// Generator G = (3, 6), order 5.
    fn field(v: u64) -> FieldElement {
        FieldElement::new(BigUint::from(v), BigUint::from(97u64))
    }

    fn g() -> Point {
        Point::Affine {
            x: field(3),
            y: field(6),
        }
    }

    fn a() -> FieldElement {
        field(2)
    }

    #[test]
    fn double_then_add() {
        // 2G + G = 3G; verify the result is still a finite point
        let g = g();
        let g2 = g.double(&a());
        let g3 = g2.add(&g, &a());
        assert!(matches!(g3, Point::Affine { .. }));
    }

    #[test]
    fn scalar_mul_zero() {
        let g = g();
        let result = g.scalar_mul(&BigUint::zero(), &a());
        assert_eq!(result, Point::Infinity);
    }

    #[test]
    fn scalar_mul_one() {
        let g = g();
        let result = g.scalar_mul(&BigUint::one(), &a());
        assert_eq!(result, g);
    }

    #[test]
    fn ladder_matches_double_and_add() {
        let g = g();
        let a = a();
        // Try every scalar in [0, 5] (curve order) and verify ladder == double-and-add.
        for k in 0u64..=5 {
            let k_bu = BigUint::from(k);
            let v = g.scalar_mul(&k_bu, &a);
            let ct = g.scalar_mul_ct(&k_bu, &a, 4);
            assert_eq!(v, ct, "mismatch at k={}", k);
        }
    }

    #[test]
    fn ladder_matches_double_and_add_p256() {
        use super::super::curve::CurveParams;
        let curve = CurveParams::p256();
        let g = curve.generator();
        let a = curve.a_fe();
        // A handful of arbitrary scalars: the ladder must agree with double-and-add.
        for k_hex in [
            "1",
            "2",
            "deadbeef",
            "ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc63254f",
        ] {
            let k = BigUint::parse_bytes(k_hex.as_bytes(), 16).unwrap();
            let v = g.scalar_mul(&k, &a);
            let ct = g.scalar_mul_ct(&k, &a, 256);
            assert_eq!(v, ct, "mismatch at k={}", k_hex);
        }
    }

    #[test]
    fn neg_point() {
        let g = g();
        let neg_g = g.neg();
        // P + (-P) = ∞
        let sum = g.add(&neg_g, &a());
        assert_eq!(sum, Point::Infinity);
    }
}
