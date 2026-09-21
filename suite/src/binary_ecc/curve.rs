//! **Binary elliptic curves**: `y² + xy = x³ + a·x² + b` over
//! `F_{2^m}`.
//!
//! This is the standard Weierstrass form for characteristic-2
//! fields used by NIST B-163, B-233, B-283, B-409, B-571 (SEC 2,
//! FIPS 186-4 Appendix D.1.3).
//!
//! ## Group law (Putranto et al. §3)
//!
//! For affine points `P₁ = (x₁, y₁)`, `P₂ = (x₂, y₂)`:
//!
//! **Negation**: `−P₁ = (x₁, y₁ + x₁)`.
//!
//! **Point Addition (P₁ ≠ ±P₂)**:
//! ```text
//! λ  = (y₁ + y₂) / (x₁ + x₂)
//! x₃ = λ² + λ + x₁ + x₂ + a
//! y₃ = λ·(x₁ + x₃) + x₃ + y₁
//! ```
//!
//! **Point Doubling (P₁ ≠ −P₁)**:
//! ```text
//! λ  = x₁ + y₁/x₁
//! x₃ = λ² + λ + a
//! y₃ = x₁² + (λ + 1)·x₃
//! ```
//!
//! ## ECPM
//!
//! Scalar multiplication `[k]·P` via left-to-right double-and-add.
//! In the paper, this is the operation whose **quantum-circuit
//! resource estimation** is the main contribution; we provide the
//! **classical reference** here.

use super::f2m::{F2mElement, IrreduciblePoly};
use num_bigint::BigUint;
use num_traits::{One, Zero};

/// A binary elliptic curve over `F_{2^m}`.
#[derive(Clone, Debug)]
pub struct BinaryCurve {
    pub m: u32,
    pub irreducible: IrreduciblePoly,
    /// Coefficient `a` of `y² + xy = x³ + a·x² + b`.
    pub a: F2mElement,
    /// Coefficient `b` of the curve equation.
    pub b: F2mElement,
    /// A base point of large prime order (the generator).
    pub generator: BinaryPoint,
    /// Order of the generator (a prime number, as `BigUint`).
    pub order: BigUint,
    /// Cofactor of the curve (`h = #E / n`).
    pub cofactor: BigUint,
}

/// An affine point on a binary elliptic curve, or the point at
/// infinity (`O`).
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum BinaryPoint {
    Infinity,
    Affine { x: F2mElement, y: F2mElement },
}

impl BinaryCurve {
    /// **Low-security historical binary curves** from SECG and IKE/Oakley.
    ///
    /// Includes the 56-bit, 64-bit, and pre-NIST IKE EC2N groups used in
    /// WTLS/WAP and IPsec-era interoperability.  These are retained for
    /// catalog/audit coverage and attack demos only.
    pub fn legacy_low_security_family() -> Vec<(&'static str, Self)> {
        vec![
            ("sect113r1", Self::sect113r1()),
            ("sect113r2", Self::sect113r2()),
            ("sect131r1", Self::sect131r1()),
            ("sect131r2", Self::sect131r2()),
            ("ike-oakley-group3", Self::ike_oakley_group3()),
            ("sect163k1", Self::sect163k1()),
            ("sect163r1", Self::sect163r1()),
            ("sect163r2", Self::sect163r2()),
        ]
    }

    /// **sect113 family** from SEC 2 / SECG, WTLS/WAP-era 56-bit curves.
    pub fn sect113_family() -> Vec<(&'static str, Self)> {
        vec![
            ("sect113r1", Self::sect113r1()),
            ("sect113r2", Self::sect113r2()),
        ]
    }

    /// **sect131 family** from SEC 2 / SECG, WTLS/WAP-era 64-bit curves.
    pub fn sect131_family() -> Vec<(&'static str, Self)> {
        vec![
            ("sect131r1", Self::sect131r1()),
            ("sect131r2", Self::sect131r2()),
        ]
    }

    /// **sect163 family** from SEC 2 / NIST, historically deployed at
    /// roughly 80-bit generic ECDLP security.
    ///
    /// These binary-field curves are retained for legacy audits,
    /// cryptanalytic demonstrations, and regression tests. They are not
    /// suitable for new production systems.
    pub fn sect163_family() -> Vec<(&'static str, Self)> {
        vec![
            ("sect163k1", Self::sect163k1()),
            ("sect163r1", Self::sect163r1()),
            ("sect163r2", Self::sect163r2()),
        ]
    }

    /// **sect113r1** (SEC 2 v1 §3.2.1).
    ///
    /// Binary random curve over `F_{2^113}` with reduction polynomial
    /// `z¹¹³ + z⁹ + 1`; roughly 56-bit generic ECDLP security.
    pub fn sect113r1() -> Self {
        let m = 113;
        let irr = IrreduciblePoly::deg_113();
        let a = F2mElement::from_hex("003088250CA6E7C7FE649CE85820F7", m);
        let b = F2mElement::from_hex("00E8BEE4D3E2260744188BE0E9C723", m);
        let gx = F2mElement::from_hex("009D73616F35F4AB1407D73562C10F", m);
        let gy = F2mElement::from_hex("00A52830277958EE84D1315ED31886", m);
        let order = BigUint::parse_bytes(b"0100000000000000D9CCEC8A39E56F", 16).unwrap();
        Self {
            m,
            irreducible: irr,
            a,
            b,
            generator: BinaryPoint::Affine { x: gx, y: gy },
            order,
            cofactor: BigUint::from(2u32),
        }
    }

    /// **sect113r2** (SEC 2 v1 §3.2.2).
    ///
    /// Binary random curve over `F_{2^113}` with reduction polynomial
    /// `z¹¹³ + z⁹ + 1`; roughly 56-bit generic ECDLP security.
    pub fn sect113r2() -> Self {
        let m = 113;
        let irr = IrreduciblePoly::deg_113();
        let a = F2mElement::from_hex("00689918DBEC7E5A0DD6DFC0AA55C7", m);
        let b = F2mElement::from_hex("0095E9A9EC9B297BD4BF36E059184F", m);
        let gx = F2mElement::from_hex("01A57A6A7B26CA5EF52FCDB8164797", m);
        let gy = F2mElement::from_hex("00B3ADC94ED1FE674C06E695BABA1D", m);
        let order = BigUint::parse_bytes(b"010000000000000108789B2496AF93", 16).unwrap();
        Self {
            m,
            irreducible: irr,
            a,
            b,
            generator: BinaryPoint::Affine { x: gx, y: gy },
            order,
            cofactor: BigUint::from(2u32),
        }
    }

    /// **sect131r1** (SEC 2 v1 §3.3.1).
    ///
    /// Binary random curve over `F_{2^131}` with reduction polynomial
    /// `z¹³¹ + z⁸ + z³ + z² + 1`; roughly 64-bit generic ECDLP security.
    pub fn sect131r1() -> Self {
        let m = 131;
        let irr = IrreduciblePoly::deg_131();
        let a = F2mElement::from_hex("07A11B09A76B562144418FF3FF8C2570B8", m);
        let b = F2mElement::from_hex("0217C05610884B63B9C6C7291678F9D341", m);
        let gx = F2mElement::from_hex("0081BAF91FDF9833C40F9C181343638399", m);
        let gy = F2mElement::from_hex("078C6E7EA38C001F73C8134B1B4EF9E150", m);
        let order = BigUint::parse_bytes(b"0400000000000000023123953A9464B54D", 16).unwrap();
        Self {
            m,
            irreducible: irr,
            a,
            b,
            generator: BinaryPoint::Affine { x: gx, y: gy },
            order,
            cofactor: BigUint::from(2u32),
        }
    }

    /// **sect131r2** (SEC 2 v1 §3.3.2).
    ///
    /// Binary random curve over `F_{2^131}` with reduction polynomial
    /// `z¹³¹ + z⁸ + z³ + z² + 1`; roughly 64-bit generic ECDLP security.
    pub fn sect131r2() -> Self {
        let m = 131;
        let irr = IrreduciblePoly::deg_131();
        let a = F2mElement::from_hex("03E5A88919D7CAFCBF415F07C2176573B2", m);
        let b = F2mElement::from_hex("04B8266A46C55657AC734CE38F018F2192", m);
        let gx = F2mElement::from_hex("0356DCD8F2F95031AD652D23951BB366A8", m);
        let gy = F2mElement::from_hex("0648F06D867940A5366D9E265DE9EB240F", m);
        let order = BigUint::parse_bytes(b"0400000000000000016954A233049BA98F", 16).unwrap();
        Self {
            m,
            irreducible: irr,
            a,
            b,
            generator: BinaryPoint::Affine { x: gx, y: gy },
            order,
            cofactor: BigUint::from(2u32),
        }
    }

    /// **IKE/Oakley Group 3** (RFC 2409 §6.3), EC2N over `GF(2^155)`.
    ///
    /// RFC 2409 publishes the generator by x-coordinate (`0x7b`) and
    /// permits either of the two y-coordinates satisfying the curve
    /// equation.  We use `y = 0x1c8`, one valid solution under the
    /// polynomial basis `z¹⁵⁵ + z⁶² + 1`, so the group is usable by the
    /// existing affine arithmetic while preserving the RFC generator x.
    pub fn ike_oakley_group3() -> Self {
        let m = 155;
        let irr = IrreduciblePoly::deg_155_oakley_group3();
        let a = F2mElement::zero(m);
        let b = F2mElement::from_hex("07338F", m);
        let gx = F2mElement::from_hex("7B", m);
        let gy = F2mElement::from_hex("01C8", m);
        let order = BigUint::parse_bytes(b"0800000000000000000057DB5698537193AEF944", 16).unwrap();
        Self {
            m,
            irreducible: irr,
            a,
            b,
            generator: BinaryPoint::Affine { x: gx, y: gy },
            order,
            // RFC 2409 gives a group order, not a separate prime-subgroup
            // order and cofactor pair.
            cofactor: BigUint::one(),
        }
    }

    /// **NIST sect163k1** (Koblitz curve over `F_{2^163}`).
    ///
    /// Curve equation: `y² + xy = x³ + x² + 1` (a = 1, b = 1).
    /// Reduction polynomial: `z¹⁶³ + z⁷ + z⁶ + z³ + 1`.
    /// Per FIPS 186-4 Appendix D.1.3 (and SEC 2 v2.0 §3.1).
    pub fn sect163k1() -> Self {
        let m = 163;
        let irr = IrreduciblePoly::deg_163();
        let a = F2mElement::one(m); // a = 1
        let b = F2mElement::one(m); // b = 1
                                    // Generator coordinates from SEC 2.
        let gx = F2mElement::from_hex("02fe13c0537bbc11acaa07d793de4e6d5e5c94eee8", m);
        let gy = F2mElement::from_hex("0289070fb05d38ff58321f2e800536d538ccdaa3d9", m);
        // Order n (SEC 2): 4000000000000000000020108A2E0CC0D99F8A5EF
        let order = BigUint::parse_bytes(b"4000000000000000000020108A2E0CC0D99F8A5EF", 16).unwrap();
        Self {
            m,
            irreducible: irr,
            a,
            b,
            generator: BinaryPoint::Affine { x: gx, y: gy },
            order,
            cofactor: BigUint::from(2u32),
        }
    }

    /// **sect163r1** (SEC 2 v2 §3.1.2).
    ///
    /// Older random binary curve over `F_{2^163}`. Legacy/insecure by
    /// modern standards; included so binary-curve attack tooling can
    /// cover historical Internet-standard parameters.
    pub fn sect163r1() -> Self {
        let m = 163;
        let irr = IrreduciblePoly::deg_163();
        let a = F2mElement::from_hex("07B6882CAAEFA84F9554FF8428BD88E246D2782AE2", m);
        let b = F2mElement::from_hex("0713612DCDDCB40AAB946BDA29CA91F73AF958AFD9", m);
        let gx = F2mElement::from_hex("0369979697AB43897789566789567F787A7876A654", m);
        let gy = F2mElement::from_hex("00435EDB42EFAFB2989D51FEFCE3C80988F41FF883", m);
        let order =
            BigUint::parse_bytes(b"03FFFFFFFFFFFFFFFFFFFF48AAB689C29CA710279B", 16).unwrap();
        Self {
            m,
            irreducible: irr,
            a,
            b,
            generator: BinaryPoint::Affine { x: gx, y: gy },
            order,
            cofactor: BigUint::from(2u32),
        }
    }

    /// **NIST B-163 / sect163r2** (FIPS 186-4 §D.1.3, SEC 2 v2 §3.1.3).
    ///
    /// Random binary curve over `F_{2^163}`, roughly 80-bit generic ECDLP
    /// security. Present only for historical/audit and attack-demo use.
    pub fn sect163r2() -> Self {
        let m = 163;
        let irr = IrreduciblePoly::deg_163();
        let a = F2mElement::one(m);
        let b = F2mElement::from_hex("020A601907B8C953CA1481EB10512F78744A3205FD", m);
        let gx = F2mElement::from_hex("03F0EBA16286A2D57EA0991168D4994637E8343E36", m);
        let gy = F2mElement::from_hex("00D51FBC6C71A0094FA2CDD545B11C5C0C797324F1", m);
        let order =
            BigUint::parse_bytes(b"040000000000000000000292FE77E70C12A4234C33", 16).unwrap();
        Self {
            m,
            irreducible: irr,
            a,
            b,
            generator: BinaryPoint::Affine { x: gx, y: gy },
            order,
            cofactor: BigUint::from(2u32),
        }
    }

    /// Tiny test curve over `F_{2^8}` with `a = 1, b = 1`.  Used
    /// for unit-testing without depending on the full sect163k1
    /// parameters.
    pub fn test_curve_f256() -> Self {
        let m = 8;
        let irr = IrreduciblePoly::deg_8();
        let a = F2mElement::one(m);
        let b = F2mElement::one(m);
        // Pick a generator by trial (we'll find one valid point).
        let _gx = F2mElement::from_bit_positions(&[1], m); // x = z
                                                           // Find y satisfying y² + zy = z³ + z² + 1 ...
                                                           // Just brute-force search for a valid point.
        let (gen, ord) = find_any_generator(m, &irr, &a, &b);
        Self {
            m,
            irreducible: irr,
            a,
            b,
            generator: gen,
            order: ord,
            cofactor: BigUint::one(),
            // Note: cofactor unknown precisely without full point
            // counting; for the test curve it's fine.
        }
    }

    /// Verify a point satisfies the curve equation.
    pub fn is_on_curve(&self, p: &BinaryPoint) -> bool {
        match p {
            BinaryPoint::Infinity => true,
            BinaryPoint::Affine { x, y } => {
                // y² + xy = x³ + a·x² + b
                let y_sq = y.square(&self.irreducible);
                let xy = x.mul(y, &self.irreducible);
                let lhs = y_sq.add(&xy);
                let x_sq = x.square(&self.irreducible);
                let x_cu = x_sq.mul(x, &self.irreducible);
                let ax_sq = self.a.mul(&x_sq, &self.irreducible);
                let rhs = x_cu.add(&ax_sq).add(&self.b);
                lhs == rhs
            }
        }
    }
}

/// Negation: `−(x, y) = (x, y + x)`.
pub fn point_neg(p: &BinaryPoint) -> BinaryPoint {
    match p {
        BinaryPoint::Infinity => BinaryPoint::Infinity,
        BinaryPoint::Affine { x, y } => BinaryPoint::Affine {
            x: x.clone(),
            y: y.add(x),
        },
    }
}

/// **Point Addition** on a binary curve (Putranto et al. §3, formula
/// reproduced in the module header).
///
/// Cases:
/// - One operand is `O` → return the other.
/// - `P₁ = P₂` → defer to [`point_double`].
/// - `P₁ = −P₂` → return `O`.
/// - Otherwise: λ = (y₁+y₂)/(x₁+x₂), x₃ = λ² + λ + x₁ + x₂ + a,
///   y₃ = λ(x₁+x₃) + x₃ + y₁.
pub fn point_add(curve: &BinaryCurve, p1: &BinaryPoint, p2: &BinaryPoint) -> BinaryPoint {
    match (p1, p2) {
        (BinaryPoint::Infinity, q) | (q, BinaryPoint::Infinity) => q.clone(),
        (BinaryPoint::Affine { x: x1, y: y1 }, BinaryPoint::Affine { x: x2, y: y2 }) => {
            if x1 == x2 {
                // x₁ = x₂.  Either P + P (double) or P + (-P) = O.
                if y1.add(y2) == *x1 {
                    // y₂ = y₁ + x₁ ⇒ P₂ = -P₁.
                    return BinaryPoint::Infinity;
                }
                return point_double(curve, p1);
            }
            let irr = &curve.irreducible;
            let num = y1.add(y2);
            let den = x1.add(x2);
            let lambda = num.mul(&den.flt_inverse(irr).expect("non-zero"), irr);
            let lambda_sq = lambda.square(irr);
            // x₃ = λ² + λ + x₁ + x₂ + a
            let x3 = lambda_sq.add(&lambda).add(x1).add(x2).add(&curve.a);
            // y₃ = λ·(x₁ + x₃) + x₃ + y₁
            let y3 = lambda.mul(&x1.add(&x3), irr).add(&x3).add(y1);
            BinaryPoint::Affine { x: x3, y: y3 }
        }
    }
}

/// **Point Doubling** on a binary curve.
///
/// `[2]·(x₁, y₁)`:
/// - If `x₁ = 0` → result is `O`.
/// - Otherwise: λ = x₁ + y₁/x₁, x₃ = λ² + λ + a, y₃ = x₁² + (λ + 1)·x₃.
pub fn point_double(curve: &BinaryCurve, p: &BinaryPoint) -> BinaryPoint {
    match p {
        BinaryPoint::Infinity => BinaryPoint::Infinity,
        BinaryPoint::Affine { x: x1, y: y1 } => {
            let irr = &curve.irreducible;
            if x1.is_zero() {
                return BinaryPoint::Infinity;
            }
            let x1_inv = x1.flt_inverse(irr).expect("non-zero x₁");
            // λ = x₁ + y₁/x₁
            let lambda = x1.add(&y1.mul(&x1_inv, irr));
            let lambda_sq = lambda.square(irr);
            let x3 = lambda_sq.add(&lambda).add(&curve.a);
            // y₃ = x₁² + (λ + 1)·x₃
            let lambda_plus_one = lambda.add(&F2mElement::one(curve.m));
            let y3 = x1.square(irr).add(&lambda_plus_one.mul(&x3, irr));
            BinaryPoint::Affine { x: x3, y: y3 }
        }
    }
}

/// **ECPM**: scalar multiplication `[k]·P` via left-to-right
/// double-and-add.  This is the operation analysed in Putranto
/// et al. for quantum-resource estimation; classical version here
/// for verification.
pub fn scalar_mul(curve: &BinaryCurve, p: &BinaryPoint, k: &BigUint) -> BinaryPoint {
    if k.is_zero() {
        return BinaryPoint::Infinity;
    }
    let bits = k.bits();
    let mut result = BinaryPoint::Infinity;
    for i in (0..bits).rev() {
        result = point_double(curve, &result);
        if k.bit(i) {
            result = point_add(curve, &result, p);
        }
    }
    result
}

/// Brute-force search for any valid point and its order, on a tiny
/// test curve.  Only feasible for `m ≤ 16`.
fn find_any_generator(
    m: u32,
    irr: &IrreduciblePoly,
    a: &F2mElement,
    b: &F2mElement,
) -> (BinaryPoint, BigUint) {
    let curve_for_check = BinaryCurve {
        m,
        irreducible: irr.clone(),
        a: a.clone(),
        b: b.clone(),
        generator: BinaryPoint::Infinity,
        order: BigUint::one(),
        cofactor: BigUint::one(),
    };
    for xi in 1..(1u64 << m) {
        let x = F2mElement::from_biguint(&BigUint::from(xi), m);
        // Find y satisfying y² + xy = x³ + ax² + b.
        // Brute force: try every possible y.
        for yi in 1..(1u64 << m) {
            let y = F2mElement::from_biguint(&BigUint::from(yi), m);
            let pt = BinaryPoint::Affine { x: x.clone(), y };
            if curve_for_check.is_on_curve(&pt) {
                // Determine order by repeated doubling.
                let ord = point_order(&curve_for_check, &pt);
                if ord >= BigUint::from(2u32) {
                    return (pt, ord);
                }
            }
        }
    }
    (BinaryPoint::Infinity, BigUint::one())
}

fn point_order(curve: &BinaryCurve, p: &BinaryPoint) -> BigUint {
    let mut k = BigUint::one();
    let mut acc = p.clone();
    while k < BigUint::from(1u32 << 10) {
        acc = point_add(curve, &acc, p);
        k += 1u32;
        if matches!(acc, BinaryPoint::Infinity) {
            return k;
        }
    }
    // Couldn't find order in budget; return placeholder.
    k
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Historical binary-curve generators are on their curves.
    #[test]
    fn legacy_binary_generators_are_on_curve() {
        for (name, curve) in BinaryCurve::legacy_low_security_family() {
            assert!(
                curve.is_on_curve(&curve.generator),
                "generator off curve for {}",
                name
            );
        }
    }

    #[test]
    fn low_security_binary_base_points_match_published_constants() {
        let cases = [
            (
                "sect113r1",
                BinaryCurve::sect113r1(),
                "009D73616F35F4AB1407D73562C10F",
                "00A52830277958EE84D1315ED31886",
            ),
            (
                "sect113r2",
                BinaryCurve::sect113r2(),
                "01A57A6A7B26CA5EF52FCDB8164797",
                "00B3ADC94ED1FE674C06E695BABA1D",
            ),
            (
                "sect131r1",
                BinaryCurve::sect131r1(),
                "0081BAF91FDF9833C40F9C181343638399",
                "078C6E7EA38C001F73C8134B1B4EF9E150",
            ),
            (
                "sect131r2",
                BinaryCurve::sect131r2(),
                "0356DCD8F2F95031AD652D23951BB366A8",
                "0648F06D867940A5366D9E265DE9EB240F",
            ),
            (
                "ike-oakley-group3",
                BinaryCurve::ike_oakley_group3(),
                "7B",
                "01C8",
            ),
        ];
        for (name, curve, gx, gy) in cases {
            let (x, y) = match curve.generator {
                BinaryPoint::Affine { x, y } => (x, y),
                BinaryPoint::Infinity => panic!("{} generator is infinity", name),
            };
            assert_eq!(
                x,
                F2mElement::from_hex(gx, curve.m),
                "Gx mismatch for {}",
                name
            );
            assert_eq!(
                y,
                F2mElement::from_hex(gy, curve.m),
                "Gy mismatch for {}",
                name
            );
        }
    }

    #[test]
    fn low_security_binary_catalog_security_categories() {
        for (name, curve) in BinaryCurve::sect113_family() {
            assert_eq!(curve.m, 113, "{} should be over F_2^113", name);
            assert_eq!(curve.order.bits() / 2, 56, "{} should be ~56-bit", name);
            assert_eq!(curve.cofactor, BigUint::from(2u32), "{} cofactor", name);
        }
        for (name, curve) in BinaryCurve::sect131_family() {
            assert_eq!(curve.m, 131, "{} should be over F_2^131", name);
            assert!(
                (64..=65).contains(&(curve.order.bits() / 2)),
                "{} should be ~64-bit",
                name
            );
            assert_eq!(curve.cofactor, BigUint::from(2u32), "{} cofactor", name);
        }

        let oakley = BinaryCurve::ike_oakley_group3();
        assert_eq!(oakley.m, 155);
        assert_eq!(oakley.irreducible.low_terms, vec![0, 62]);
        assert!(
            (76..=78).contains(&(oakley.order.bits() / 2)),
            "Oakley Group 3 should be roughly 76-bit"
        );
    }

    /// Adding `P + (-P) = O`.
    #[test]
    fn point_plus_neg_is_infinity() {
        let curve = BinaryCurve::sect163k1();
        let neg_g = point_neg(&curve.generator);
        let sum = point_add(&curve, &curve.generator, &neg_g);
        assert!(matches!(sum, BinaryPoint::Infinity));
    }

    /// `2P` via doubling equals `P + P` via addition.
    #[test]
    fn double_equals_self_add() {
        let curve = BinaryCurve::sect163k1();
        let g = curve.generator.clone();
        let g2_dbl = point_double(&curve, &g);
        let g2_add = point_add(&curve, &g, &g);
        assert_eq!(g2_dbl, g2_add);
    }

    /// `2P` is on the curve.
    #[test]
    fn double_stays_on_curve() {
        let curve = BinaryCurve::sect163k1();
        let g2 = point_double(&curve, &curve.generator);
        assert!(curve.is_on_curve(&g2));
    }

    /// Scalar multiplication: `[1]·G = G`, `[2]·G = 2G`, etc.
    #[test]
    fn scalar_mul_small_consistency() {
        let curve = BinaryCurve::sect163k1();
        let g = curve.generator.clone();
        let g1 = scalar_mul(&curve, &g, &BigUint::one());
        assert_eq!(g1, g);
        let g2_sm = scalar_mul(&curve, &g, &BigUint::from(2u32));
        let g2_dbl = point_double(&curve, &g);
        assert_eq!(g2_sm, g2_dbl);
        let g3_sm = scalar_mul(&curve, &g, &BigUint::from(3u32));
        let g3_add = point_add(&curve, &g2_dbl, &g);
        assert_eq!(g3_sm, g3_add);
    }

    /// `[5]G = 2·(2G) + G` via mixed PA/PD.  Demonstrates ECPM
    /// matches a hand-computed sequence.
    #[test]
    fn scalar_mul_matches_handcomputed() {
        let curve = BinaryCurve::sect163k1();
        let g = curve.generator.clone();
        let g2 = point_double(&curve, &g);
        let g4 = point_double(&curve, &g2);
        let g5 = point_add(&curve, &g4, &g);
        let g5_sm = scalar_mul(&curve, &g, &BigUint::from(5u32));
        assert_eq!(g5, g5_sm);
    }

    #[test]
    fn sect163_base_points_match_sec2_constants() {
        let cases = [
            (
                "sect163k1",
                BinaryCurve::sect163k1(),
                "02fe13c0537bbc11acaa07d793de4e6d5e5c94eee8",
                "0289070fb05d38ff58321f2e800536d538ccdaa3d9",
            ),
            (
                "sect163r1",
                BinaryCurve::sect163r1(),
                "0369979697AB43897789566789567F787A7876A654",
                "00435EDB42EFAFB2989D51FEFCE3C80988F41FF883",
            ),
            (
                "sect163r2",
                BinaryCurve::sect163r2(),
                "03F0EBA16286A2D57EA0991168D4994637E8343E36",
                "00D51FBC6C71A0094FA2CDD545B11C5C0C797324F1",
            ),
        ];
        for (name, curve, gx, gy) in cases {
            let (x, y) = match curve.generator {
                BinaryPoint::Affine { x, y } => (x, y),
                BinaryPoint::Infinity => panic!("{} generator is infinity", name),
            };
            assert_eq!(
                x,
                F2mElement::from_hex(gx, curve.m),
                "Gx mismatch for {}",
                name
            );
            assert_eq!(
                y,
                F2mElement::from_hex(gy, curve.m),
                "Gy mismatch for {}",
                name
            );
        }
    }

    #[test]
    fn sect163_nominal_security_category_is_80_bit() {
        for (name, curve) in BinaryCurve::sect163_family() {
            assert_eq!(curve.m, 163, "{} should be over F_2^163", name);
            assert_eq!(
                curve.order.bits() / 2,
                81,
                "{} has expected ~80-bit order",
                name
            );
            assert_eq!(curve.cofactor, BigUint::from(2u32), "{} cofactor", name);
        }
    }

    #[test]
    fn sect163_order_times_generator_is_identity() {
        for (name, curve) in BinaryCurve::sect163_family() {
            let n_g = scalar_mul(&curve, &curve.generator, &curve.order);
            assert!(
                matches!(n_g, BinaryPoint::Infinity),
                "n*G should be infinity for {}",
                name
            );
        }
    }

    #[test]
    fn low_security_order_times_generator_is_identity() {
        for (name, curve) in [
            ("sect113r1", BinaryCurve::sect113r1()),
            ("sect113r2", BinaryCurve::sect113r2()),
            ("sect131r1", BinaryCurve::sect131r1()),
            ("sect131r2", BinaryCurve::sect131r2()),
            ("ike-oakley-group3", BinaryCurve::ike_oakley_group3()),
        ] {
            let n_g = scalar_mul(&curve, &curve.generator, &curve.order);
            assert!(
                matches!(n_g, BinaryPoint::Infinity),
                "n*G should be infinity for {}",
                name
            );
        }
    }

    /// `[n]·G = O` where `n` is the generator's order.  This is
    /// the critical Lagrange-theorem test that distinguishes a
    /// real elliptic-curve implementation from one with subtle
    /// bugs.  Expensive (~thousands of point ops at sect163k1
    /// scale); ignored by default but can be run via --ignored.
    #[test]
    #[ignore]
    fn scalar_mul_by_order_is_identity() {
        let curve = BinaryCurve::sect163k1();
        let n_g = scalar_mul(&curve, &curve.generator, &curve.order);
        assert!(matches!(n_g, BinaryPoint::Infinity));
    }
}
