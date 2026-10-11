//! Elliptic curve parameter sets.
//!
//! A `CurveParams` bundles the Weierstrass curve coefficients (a, b),
//! the field prime p, the generator point G, the group order n, and the
//! cofactor h.  All arithmetic is performed using `FieldElement` (for
//! field operations) or plain `BigUint` (for scalar operations mod n).

use super::field::FieldElement;
use super::point::Point;
use num_bigint::BigUint;

/// Parameters for a short Weierstrass curve y² ≡ x³ + ax + b (mod p).
#[derive(Clone, Debug)]
pub struct CurveParams {
    /// Human-readable name
    pub name: &'static str,
    /// Field prime
    pub p: BigUint,
    /// Curve coefficient a
    pub a: BigUint,
    /// Curve coefficient b
    pub b: BigUint,
    /// Generator x-coordinate
    pub gx: BigUint,
    /// Generator y-coordinate
    pub gy: BigUint,
    /// Group order (number of points on the curve)
    pub n: BigUint,
    /// Cofactor (usually 1 for NIST/secp curves)
    pub h: u32,
}

impl CurveParams {
    // ── Convenience constructors ──────────────────────────────────────────────

    /// secp256k1 — the curve used by Bitcoin and Ethereum.
    ///
    /// y² = x³ + 7 (mod p), a=0, b=7.
    /// Defined in SEC 2, section 2.4.1.
    pub fn secp256k1() -> Self {
        CurveParams {
            name: "secp256k1",
            p: BigUint::parse_bytes(
                b"FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F",
                16,
            )
            .unwrap(),
            a: BigUint::from(0u32),
            b: BigUint::from(7u32),
            gx: BigUint::parse_bytes(
                b"79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798",
                16,
            )
            .unwrap(),
            gy: BigUint::parse_bytes(
                b"483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8",
                16,
            )
            .unwrap(),
            n: BigUint::parse_bytes(
                b"FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141",
                16,
            )
            .unwrap(),
            h: 1,
        }
    }

    /// **GOST R 34.10-2012 §A.2.1 example curve** (256-bit).  This is
    /// the demonstration curve used in the standard's worked example
    /// (Appendix A.2.1); it is *not* one of the operationally
    /// standardised parameter sets (CryptoPro-A/B/C, paramSetA/B), but
    /// it is what every published GOST 34.10-2012 test vector at the
    /// 256-bit level is computed against.
    pub fn gost_3410_2012_256_test() -> Self {
        CurveParams {
            name: "GOST-3410-2012-256-test",
            p: BigUint::parse_bytes(
                b"8000000000000000000000000000000000000000000000000000000000000431",
                16,
            )
            .unwrap(),
            a: BigUint::from(7u32),
            b: BigUint::parse_bytes(
                b"5FBFF498AA938CE739B8E022FBAFEF40563F6E6A3472FC2A514C0CE9DAE23B7E",
                16,
            )
            .unwrap(),
            gx: BigUint::from(2u32),
            gy: BigUint::parse_bytes(
                b"08E2A8A0E65147D4BD6316030E16D19C85C97F0A9CA267122B96ABBCEA7E8FC8",
                16,
            )
            .unwrap(),
            n: BigUint::parse_bytes(
                b"8000000000000000000000000000000150FE8A1892976154C59CFC193ACCF5B3",
                16,
            )
            .unwrap(),
            h: 1,
        }
    }

    /// **GOST R 34.10-2012 §A.2.2 example curve** (512-bit).  The
    /// demonstration curve used in the standard's 512-bit worked
    /// example (Appendix A.2.2).
    pub fn gost_3410_2012_512_test() -> Self {
        CurveParams {
            name: "GOST-3410-2012-512-test",
            p: BigUint::parse_bytes(
                b"4531ACD1FE0023C7550D267B6B2FEE80922B14B2FFB90F04D4EB7C09B5D2D15DF1D852741AF4704A0458047E80E4546D35B8336FAC224DD81664BBF528BE6373",
                16,
            ).unwrap(),
            a: BigUint::from(7u32),
            b: BigUint::parse_bytes(
                b"1CFF0806A31116DA29D8CFA54E57EB748BC5F377E49400FDD788B649ECA1AC4361834013B2AD7322480A89CA58E0CF74BC9E540C2ADD6897FAD0A3084F302ADC",
                16,
            ).unwrap(),
            gx: BigUint::parse_bytes(
                b"24D19CC64572EE30F396BF6EBBFD7A6C5213B3B3D7057CC825F91093A68CD762FD60611262CD838DC6B60AA7EEE804E28BC849977FAC33B4B530F1B120248A9A",
                16,
            ).unwrap(),
            gy: BigUint::parse_bytes(
                b"2BB312A43BD2CE6E0D020613C857ACDDCFBF061E91E5F2C3F32447C259F39B2C83AB156D77F1496BF7EB3351E1EE4E43DC1A18B91B24640B6DBB92CB1ADD371E",
                16,
            ).unwrap(),
            n: BigUint::parse_bytes(
                b"4531ACD1FE0023C7550D267B6B2FEE80922B14B2FFB90F04D4EB7C09B5D2D15DA82F2D7ECB1DBAC719905C5EECC423F1D86E25EDBE23C595D644AAF187E6E6DF",
                16,
            ).unwrap(),
            h: 1,
        }
    }

    /// **SM2 curve** — the standardised 256-bit prime-field curve in
    /// GB/T 32918 (Chinese national standard).  Sometimes called
    /// `sm2p256v1`.  Used for SM2 digital signature, public-key
    /// encryption, and key agreement.
    ///
    /// y² = x³ + ax + b (mod p) with a = p - 3 (so the curve has the
    /// Weierstrass form `y² = x³ - 3x + b` over F_p).
    pub fn sm2() -> Self {
        CurveParams {
            name: "SM2",
            p: BigUint::parse_bytes(
                b"FFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF00000000FFFFFFFFFFFFFFFF",
                16,
            )
            .unwrap(),
            a: BigUint::parse_bytes(
                b"FFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF00000000FFFFFFFFFFFFFFFC",
                16,
            )
            .unwrap(),
            b: BigUint::parse_bytes(
                b"28E9FA9E9D9F5E344D5A9E4BCF6509A7F39789F515AB8F92DDBCBD414D940E93",
                16,
            )
            .unwrap(),
            gx: BigUint::parse_bytes(
                b"32C4AE2C1F1981195F9904466A39C9948FE30BBFF2660BE1715A4589334C74C7",
                16,
            )
            .unwrap(),
            gy: BigUint::parse_bytes(
                b"BC3736A2F4F6779C59BDCEE36B692153D0A9877CC62A474002DF32E52139F0A0",
                16,
            )
            .unwrap(),
            n: BigUint::parse_bytes(
                b"FFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFF7203DF6B21C6052B53BBF40939D54123",
                16,
            )
            .unwrap(),
            h: 1,
        }
    }

    /// NIST P-256 (secp256r1) — widely used in TLS and FIDO2.
    ///
    /// y² = x³ - 3x + b (mod p), a = p - 3.
    pub fn p256() -> Self {
        CurveParams {
            name: "P-256",
            p: BigUint::parse_bytes(
                b"ffffffff00000001000000000000000000000000ffffffffffffffffffffffff",
                16,
            )
            .unwrap(),
            a: BigUint::parse_bytes(
                b"ffffffff00000001000000000000000000000000fffffffffffffffffffffffc",
                16,
            )
            .unwrap(),
            b: BigUint::parse_bytes(
                b"5ac635d8aa3a93e7b3ebbd55769886bc651d06b0cc53b0f63bce3c3e27d2604b",
                16,
            )
            .unwrap(),
            gx: BigUint::parse_bytes(
                b"6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296",
                16,
            )
            .unwrap(),
            gy: BigUint::parse_bytes(
                b"4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5",
                16,
            )
            .unwrap(),
            n: BigUint::parse_bytes(
                b"ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551",
                16,
            )
            .unwrap(),
            h: 1,
        }
    }

    // (secp192k1 and secp224k1 are in curve_zoo.rs; we delegate to those.)

    // ── Helpers ───────────────────────────────────────────────────────────────

    /// Wrap a raw value as a `FieldElement` over this curve's prime field.
    pub fn fe(&self, v: BigUint) -> FieldElement {
        FieldElement::new(v, self.p.clone())
    }

    /// Return the curve's `a` coefficient as a `FieldElement`.
    pub fn a_fe(&self) -> FieldElement {
        self.fe(self.a.clone())
    }

    /// Bit length of the group order `n`.  Used to pick a fixed
    /// iteration count for the constant-time scalar-multiplication
    /// ladder so the runtime does not depend on the position of the
    /// scalar's most-significant set bit.
    pub fn order_bits(&self) -> usize {
        self.n.bits() as usize
    }

    /// Return the generator point G.
    pub fn generator(&self) -> Point {
        Point::Affine {
            x: self.fe(self.gx.clone()),
            y: self.fe(self.gy.clone()),
        }
    }

    /// Check whether a point satisfies the curve equation y² ≡ x³ + ax + b (mod p).
    pub fn is_on_curve(&self, point: &Point) -> bool {
        match point {
            Point::Infinity => true,
            Point::Affine { x, y } => {
                let lhs = y.mul(y); // y²
                let a = self.a_fe();
                let rhs = x
                    .mul(&x.mul(x)) // x³
                    .add(&a.mul(x)) // + ax
                    .add(&self.fe(self.b.clone())); // + b
                lhs == rhs
            }
        }
    }

    /// Validate an externally supplied public point for this curve.
    ///
    /// Infinity is never a valid public key.  Affine coordinates must satisfy
    /// the curve equation and lie in the subgroup generated by `G`.
    pub fn is_valid_public_point(&self, point: &Point) -> bool {
        if matches!(point, Point::Infinity) || !self.is_on_curve(point) {
            return false;
        }

        // Cofactor-one curves get the same subgroup check; it is cheap compared
        // with accepting invalid-curve or small-subgroup public inputs.
        matches!(point.scalar_mul(&self.n, &self.a_fe()), Point::Infinity)
    }
}
