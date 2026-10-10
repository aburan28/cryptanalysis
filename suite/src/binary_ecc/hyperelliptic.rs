//! **Hyperelliptic curves** `C: y² + h(x)·y = f(x)` over `F_{2^m}`
//! with Jacobian arithmetic in **Mumford representation** via
//! **Cantor's algorithm** (characteristic-2 variant).
//!
//! ## Background
//!
//! A hyperelliptic curve of genus `g` over `F_q` is a non-singular
//! projective curve birational to an affine model
//! ```text
//!     C : y² + h(x)·y = f(x)
//! ```
//! with `deg f ≤ 2g + 1` and `deg h ≤ g`.  In characteristic 2 the
//! `h(x)` term is mandatory (otherwise `C` is singular).
//!
//! The Jacobian variety `Jac(C)` is a `g`-dimensional abelian group;
//! over `F_q` its rational points form a finite abelian group whose
//! order lies in the **Weil interval** `(√q − 1)^{2g} ≤ #Jac(C)(F_q) ≤
//! (√q + 1)^{2g}`.  This is the target of HCDLP (hyperelliptic discrete-
//! log) attacks and the *codomain* of the GHS Weil-descent homomorphism
//! from `E(F_{q^n})`.
//!
//! ## Mumford representation
//!
//! Every reduced divisor class in `Jac(C)(F_q)` has a **unique** pair
//! of polynomials `(u(x), v(x))` over `F_q` with:
//! - `u` monic,
//! - `deg v < deg u ≤ g`,
//! - `u  |  v² + h·v + f`  (mod 2; `−` becomes `+` in char 2).
//!
//! Geometrically `u(x) = ∏(x − x_i)` for the affine `x`-coordinates of
//! the divisor's support (with multiplicity), and `y = v(x)` interpolates
//! the `y`-coordinates of those points.  The identity is `(1, 0)`
//! (the empty divisor).
//!
//! ## Cantor's algorithm (Koblitz '89, Cantor '87, char-2 form)
//!
//! To add `D_1 = (u_1, v_1)` and `D_2 = (u_2, v_2)`:
//!
//! **Composition.**  Let `d_1 = gcd(u_1, u_2) = e_1·u_1 + e_2·u_2`
//! (extended Euclidean).  Let `d = gcd(d_1, v_1 + v_2 + h) =
//! c_1·d_1 + c_2·(v_1 + v_2 + h)`.  Let `s_1 = c_1·e_1`, `s_2 = c_1·e_2`,
//! `s_3 = c_2`.  Then
//! ```text
//!     u'  = u_1 · u_2 / d²
//!     v'  = (s_1·u_1·v_2 + s_2·u_2·v_1 + s_3·(v_1·v_2 + f)) / d  (mod u')
//! ```
//!
//! **Reduction** (apply while `deg u' > g`):
//! ```text
//!     u'' = monic((f + h·v' + v'²) / u')      // exact division
//!     v'' = (h + v') mod u''                  // char-2 sign collapse
//! ```
//! When `deg u' ≤ g`, the pair `(u', v')` is the reduced sum.
//!
//! ## What this module provides
//!
//! - [`HyperellipticCurve`] — checked odd-degree, one-rational-infinity
//!   models `(h, f, g)` over `F_{2^m}` (`deg f = 2g + 1`).
//! - [`MumfordDivisor`] — `(u, v)` with the invariants enforced on
//!   construction, plus `is_reduced`, `eq` (canonical), `is_identity`.
//! - Group law: [`MumfordDivisor::add`], [`MumfordDivisor::neg`],
//!   [`MumfordDivisor::double`], [`MumfordDivisor::scalar_mul`].
//! - Point-to-divisor conversion: [`MumfordDivisor::from_point`]
//!   (the standard embedding `P ↦ [P] − [∞]`, including ramified points).
//! - **BSGS** discrete-log solver: [`hcdlp_bsgs`] — for toy-sized
//!   Jacobians (genus ≤ ~3, base field ≤ ~F_{2^8}).
//! - **Pollard-ρ** discrete-log solver: [`hcdlp_pollard_rho`] —
//!   exponential in `√#Jac(C)`, works at slightly larger sizes.
//!
//! ## Honest scope
//!
//! - **Toy sizes only.**  These routines are correct but unoptimised.
//!   `add` allocates polynomial vectors; `scalar_mul` uses left-to-
//!   right double-and-add without windowing.  Realistic ECC-trapdoor
//!   parameters (`N ≈ 160`, `g ≈ 30`) would need a much faster
//!   Jacobian implementation and index-calculus HCDLP — out of scope
//!   for this educational reference.  The end-to-end test runs at
//!   `N ∈ {6, 8, 10, 12}` where brute-force ECDLP can verify the
//!   trapdoor's answer.
//! - **One rational point at infinity.**  The checked constructor in this
//!   module deliberately supports the odd-degree model `deg f = 2g + 1`.
//!   Even-degree models, including their different infinity bookkeeping,
//!   need a separate implementation.

use super::f2m::{F2mElement, IrreduciblePoly};
use super::poly_f2m::F2mPoly;
use num_bigint::BigUint;
use num_traits::{One, Zero};
use std::fmt;

/// Largest binary extension degree accepted by the checked constructor.
///
/// This is a validation/resource boundary, not a mathematical claim.  It is
/// aligned with the catalog cover checker and comfortably includes all binary
/// fields currently represented in this crate.
pub const MAX_CHECKED_FIELD_DEGREE: u32 = 4096;

/// Validation and arithmetic failures for the checked characteristic-two
/// hyperelliptic API.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum HyperellipticError {
    ZeroFieldDegree,
    FieldDegreeTooLarge {
        degree: u32,
        maximum: u32,
    },
    FieldDegreeMismatch {
        curve_degree: u32,
        modulus_degree: u32,
    },
    InvalidModulusTerm {
        term: u32,
        degree: u32,
    },
    DuplicateModulusTerm {
        term: u32,
    },
    ReducibleModulus,
    ZeroGenus,
    GenusDegreeOverflow {
        genus: u32,
    },
    PolynomialFieldMismatch {
        polynomial: &'static str,
        expected: u32,
        actual: u32,
    },
    CoefficientFieldMismatch {
        polynomial: &'static str,
        coefficient: usize,
        expected: u32,
        actual: u32,
    },
    NonCanonicalPolynomial {
        polynomial: &'static str,
    },
    ZeroHPolynomial,
    ZeroFPolynomial,
    UnsupportedInfinityConfiguration {
        expected_f_degree: usize,
        actual_f_degree: Option<usize>,
    },
    HDegreeTooLarge {
        maximum: usize,
        actual: usize,
    },
    SingularAffineModel,
    CoordinateFieldMismatch {
        coordinate: &'static str,
        expected: u32,
        actual: u32,
    },
    PointNotOnCurve,
    ZeroDivisorPolynomial,
    NonMonicDivisorPolynomial,
    DivisorDegreeTooLarge {
        maximum: usize,
        actual: usize,
    },
    DivisorVNotReduced {
        u_degree: usize,
        v_degree: usize,
    },
    DivisorEquationNotDivisible,
    NonExactCompositionUDivision,
    NonExactCompositionVDivision,
    NonExactReductionDivision,
    ZeroReductionPolynomial,
}

impl fmt::Display for HyperellipticError {
    fn fmt(&self, out: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::ZeroFieldDegree => write!(out, "binary field degree must be positive"),
            Self::FieldDegreeTooLarge { degree, maximum } => write!(
                out,
                "binary field degree {degree} exceeds checked limit {maximum}"
            ),
            Self::FieldDegreeMismatch {
                curve_degree,
                modulus_degree,
            } => write!(
                out,
                "curve field degree {curve_degree} does not match modulus degree {modulus_degree}"
            ),
            Self::InvalidModulusTerm { term, degree } => write!(
                out,
                "modulus term {term} is not below its leading degree {degree}"
            ),
            Self::DuplicateModulusTerm { term } => {
                write!(out, "modulus term {term} occurs more than once")
            }
            Self::ReducibleModulus => write!(out, "binary field modulus is reducible"),
            Self::ZeroGenus => write!(out, "hyperelliptic genus must be positive"),
            Self::GenusDegreeOverflow { genus } => {
                write!(out, "degree 2g+1 overflows for genus {genus}")
            }
            Self::PolynomialFieldMismatch {
                polynomial,
                expected,
                actual,
            } => write!(
                out,
                "polynomial {polynomial} declares F_(2^{actual}), expected F_(2^{expected})"
            ),
            Self::CoefficientFieldMismatch {
                polynomial,
                coefficient,
                expected,
                actual,
            } => write!(
                out,
                "coefficient {coefficient} of {polynomial} is in F_(2^{actual}), expected F_(2^{expected})"
            ),
            Self::NonCanonicalPolynomial { polynomial } => write!(
                out,
                "polynomial {polynomial} has a noncanonical trailing zero coefficient"
            ),
            Self::ZeroHPolynomial => write!(
                out,
                "h = 0 gives an inseparable quadratic function-field model"
            ),
            Self::ZeroFPolynomial => write!(out, "f must be non-zero"),
            Self::UnsupportedInfinityConfiguration {
                expected_f_degree,
                actual_f_degree,
            } => write!(
                out,
                "checked one-infinity model requires deg f = {expected_f_degree}, got {actual_f_degree:?}"
            ),
            Self::HDegreeTooLarge { maximum, actual } => {
                write!(out, "deg h = {actual} exceeds genus {maximum}")
            }
            Self::SingularAffineModel => write!(out, "affine curve model is singular"),
            Self::CoordinateFieldMismatch {
                coordinate,
                expected,
                actual,
            } => write!(
                out,
                "point coordinate {coordinate} is in F_(2^{actual}), expected F_(2^{expected})"
            ),
            Self::PointNotOnCurve => write!(out, "affine point is not on the curve"),
            Self::ZeroDivisorPolynomial => write!(out, "Mumford u polynomial must be non-zero"),
            Self::NonMonicDivisorPolynomial => write!(out, "Mumford u polynomial must be monic"),
            Self::DivisorDegreeTooLarge { maximum, actual } => write!(
                out,
                "Mumford u degree {actual} exceeds genus {maximum}"
            ),
            Self::DivisorVNotReduced { u_degree, v_degree } => write!(
                out,
                "Mumford v degree {v_degree} is not below u degree {u_degree}"
            ),
            Self::DivisorEquationNotDivisible => {
                write!(out, "Mumford u does not divide v^2 + h*v + f")
            }
            Self::NonExactCompositionUDivision => {
                write!(out, "Cantor composition u division is not exact")
            }
            Self::NonExactCompositionVDivision => {
                write!(out, "Cantor composition v division is not exact")
            }
            Self::NonExactReductionDivision => {
                write!(out, "Cantor reduction division is not exact")
            }
            Self::ZeroReductionPolynomial => {
                write!(out, "Cantor reduction produced the zero u polynomial")
            }
        }
    }
}

impl std::error::Error for HyperellipticError {}

fn bit_rem(mut value: BigUint, modulus: &BigUint) -> BigUint {
    while !value.is_zero() && value.bits() >= modulus.bits() {
        let shift = (value.bits() - modulus.bits()) as usize;
        value ^= modulus << shift;
    }
    value
}

fn bit_gcd(mut left: BigUint, mut right: BigUint) -> BigUint {
    while !right.is_zero() {
        let remainder = bit_rem(left, &right);
        left = right;
        right = remainder;
    }
    left
}

fn modulus_bits(irr: &IrreduciblePoly) -> BigUint {
    let mut modulus = BigUint::one() << irr.degree as usize;
    for &term in &irr.low_terms {
        modulus ^= BigUint::one() << term as usize;
    }
    modulus
}

fn modulus_is_irreducible(irr: &IrreduciblePoly) -> bool {
    // Every monic linear polynomial is irreducible.  Handling this explicitly
    // also avoids representing the polynomial `z` as an F_2 field element.
    if irr.degree == 1 {
        return true;
    }
    let modulus = modulus_bits(irr);
    if (&modulus & BigUint::one()).is_zero() {
        return false;
    }

    // Rabin's criterion: z^(2^m)=z modulo q, and for every prime l|m,
    // gcd(z^(2^(m/l))-z, q)=1.
    let m = irr.degree;
    let mut remaining = m;
    let mut prime = 2u32;
    let mut checkpoints = Vec::new();
    while prime <= remaining / prime {
        if remaining.is_multiple_of(prime) {
            checkpoints.push(m / prime);
            while remaining.is_multiple_of(prime) {
                remaining /= prime;
            }
        }
        prime += 1;
    }
    if remaining > 1 {
        checkpoints.push(m / remaining);
    }

    let z = bit_rem(BigUint::from(2u32), &modulus);
    let mut power = F2mElement::from_biguint(&z, m);
    for exponent in 1..=m {
        power = power.square(irr);
        if checkpoints.contains(&exponent)
            && bit_gcd(power.to_biguint() ^ &z, modulus.clone()) != BigUint::one()
        {
            return false;
        }
    }
    power.to_biguint() == z
}

fn formal_derivative(poly: &F2mPoly) -> F2mPoly {
    let mut coefficients = vec![F2mElement::zero(poly.m); poly.coeffs.len().saturating_sub(1)];
    for degree in (1..poly.coeffs.len()).step_by(2) {
        coefficients[degree - 1] = poly.coeffs[degree].clone();
    }
    F2mPoly::from_coeffs(coefficients, poly.m)
}

/// `C : y² + h(x)·y = f(x)` over `F_{2^m}` with `m`'s irreducible
/// polynomial provided.  Stores genus and both defining polynomials.
#[derive(Clone, Debug)]
pub struct HyperellipticCurve {
    /// Field width — `C` is defined over `F_{2^m}`.
    pub m: u32,
    /// Reduction polynomial of `F_{2^m}`.
    pub irr: IrreduciblePoly,
    /// `h(x)` with `deg h ≤ g`.
    pub h: F2mPoly,
    /// `f(x)` with `deg f ≤ 2g + 1`.
    pub f: F2mPoly,
    /// Genus.
    pub genus: u32,
}

impl HyperellipticCurve {
    /// Construct a checked odd-degree characteristic-two model.
    ///
    /// This compatibility wrapper panics on invalid input.  Parsers and other
    /// callers handling public input should use [`Self::try_new`].
    pub fn new(m: u32, irr: IrreduciblePoly, h: F2mPoly, f: F2mPoly, genus: u32) -> Self {
        Self::try_new(m, irr, h, f, genus).expect("invalid characteristic-two hyperelliptic curve")
    }

    /// Construct a separable, smooth odd-degree model with one rational point
    /// at infinity.
    ///
    /// The supported equation is `y^2 + h(x)y = f(x)` over a validated
    /// polynomial-basis field, with `deg f = 2g+1` and `deg h <= g`.
    /// Smoothness on the affine chart is checked by the characteristic-two
    /// criterion
    /// `gcd(h, f'^2 + f h'^2) = 1`.  Exact odd degree supplies the single
    /// smooth rational point at infinity and fixes the declared genus.
    pub fn try_new(
        m: u32,
        irr: IrreduciblePoly,
        h: F2mPoly,
        f: F2mPoly,
        genus: u32,
    ) -> Result<Self, HyperellipticError> {
        let curve = Self {
            m,
            irr,
            h,
            f,
            genus,
        };
        curve.validate()?;
        Ok(curve)
    }

    fn validate_polynomial(
        &self,
        name: &'static str,
        polynomial: &F2mPoly,
    ) -> Result<(), HyperellipticError> {
        if polynomial.m != self.m {
            return Err(HyperellipticError::PolynomialFieldMismatch {
                polynomial: name,
                expected: self.m,
                actual: polynomial.m,
            });
        }
        for (coefficient, value) in polynomial.coeffs.iter().enumerate() {
            if value.m_value() != self.m {
                return Err(HyperellipticError::CoefficientFieldMismatch {
                    polynomial: name,
                    coefficient,
                    expected: self.m,
                    actual: value.m_value(),
                });
            }
        }
        if polynomial.coeffs.last().is_some_and(F2mElement::is_zero) {
            return Err(HyperellipticError::NonCanonicalPolynomial { polynomial: name });
        }
        Ok(())
    }

    /// Revalidate the field, model degrees, separability and smoothness.
    ///
    /// The fields remain public for source compatibility, so checked public
    /// arithmetic calls this method before consuming a curve that may have
    /// been mutated after construction.
    pub fn validate(&self) -> Result<(), HyperellipticError> {
        if self.m == 0 {
            return Err(HyperellipticError::ZeroFieldDegree);
        }
        if self.m > MAX_CHECKED_FIELD_DEGREE {
            return Err(HyperellipticError::FieldDegreeTooLarge {
                degree: self.m,
                maximum: MAX_CHECKED_FIELD_DEGREE,
            });
        }
        if self.irr.degree != self.m {
            return Err(HyperellipticError::FieldDegreeMismatch {
                curve_degree: self.m,
                modulus_degree: self.irr.degree,
            });
        }
        let mut terms = self.irr.low_terms.clone();
        for &term in &terms {
            if term >= self.m {
                return Err(HyperellipticError::InvalidModulusTerm {
                    term,
                    degree: self.m,
                });
            }
        }
        terms.sort_unstable();
        for pair in terms.windows(2) {
            if pair[0] == pair[1] {
                return Err(HyperellipticError::DuplicateModulusTerm { term: pair[0] });
            }
        }
        if !modulus_is_irreducible(&self.irr) {
            return Err(HyperellipticError::ReducibleModulus);
        }
        if self.genus == 0 {
            return Err(HyperellipticError::ZeroGenus);
        }
        let genus = self.genus as usize;
        let expected_f_degree = genus
            .checked_mul(2)
            .and_then(|degree| degree.checked_add(1))
            .ok_or(HyperellipticError::GenusDegreeOverflow { genus: self.genus })?;
        self.validate_polynomial("h", &self.h)?;
        self.validate_polynomial("f", &self.f)?;
        if self.h.is_zero() {
            return Err(HyperellipticError::ZeroHPolynomial);
        }
        if self.f.is_zero() {
            return Err(HyperellipticError::ZeroFPolynomial);
        }
        if self.f.degree() != Some(expected_f_degree) {
            return Err(HyperellipticError::UnsupportedInfinityConfiguration {
                expected_f_degree,
                actual_f_degree: self.f.degree(),
            });
        }
        if let Some(actual) = self.h.degree().filter(|&degree| degree > genus) {
            return Err(HyperellipticError::HDegreeTooLarge {
                maximum: genus,
                actual,
            });
        }

        // For F(x,y)=y^2+h(x)y+f(x), a finite singular point must have
        // h=0 and h' y+f'=0.  Squaring the latter and using y^2=f gives
        // f'^2+f h'^2=0.  Conversely Frobenius is injective over the
        // algebraic closure, so this gcd criterion is exact.
        let f_derivative = formal_derivative(&self.f);
        let h_derivative = formal_derivative(&self.h);
        let singularity_polynomial = f_derivative.mul(&f_derivative, &self.irr).add(
            &self
                .f
                .mul(&h_derivative.mul(&h_derivative, &self.irr), &self.irr),
        );
        let singularity_gcd = self.h.gcd(&singularity_polynomial, &self.irr);
        if singularity_gcd.degree() != Some(0) {
            return Err(HyperellipticError::SingularAffineModel);
        }
        Ok(())
    }

    /// `true` iff `(x, y)` satisfies `y² + h(x)·y = f(x)`.
    pub fn is_on_curve(&self, x: &F2mElement, y: &F2mElement) -> bool {
        self.try_is_on_curve(x, y).unwrap_or(false)
    }

    /// Checked affine-point membership test.
    pub fn try_is_on_curve(
        &self,
        x: &F2mElement,
        y: &F2mElement,
    ) -> Result<bool, HyperellipticError> {
        self.validate()?;
        if x.m_value() != self.m {
            return Err(HyperellipticError::CoordinateFieldMismatch {
                coordinate: "x",
                expected: self.m,
                actual: x.m_value(),
            });
        }
        if y.m_value() != self.m {
            return Err(HyperellipticError::CoordinateFieldMismatch {
                coordinate: "y",
                expected: self.m,
                actual: y.m_value(),
            });
        }
        let lhs = y
            .square(&self.irr)
            .add(&self.h.eval(x, &self.irr).mul(y, &self.irr));
        let rhs = self.f.eval(x, &self.irr);
        Ok(lhs == rhs)
    }
}

/// A reduced Mumford divisor `(u, v)` on a [`HyperellipticCurve`].
/// The curve reference is *not* stored — the polynomials carry the
/// field width and the caller threads the curve in for arithmetic
/// (this avoids lifetime annotations on every divisor).
#[derive(Clone, Debug)]
pub struct MumfordDivisor {
    /// Monic, `deg u ≤ g`.
    pub u: F2mPoly,
    /// `deg v < deg u`, satisfies `u | v² + h·v + f`.
    pub v: F2mPoly,
}

impl PartialEq for MumfordDivisor {
    fn eq(&self, other: &Self) -> bool {
        self.u == other.u && self.v == other.v
    }
}

impl Eq for MumfordDivisor {}

impl MumfordDivisor {
    /// Identity element `(1, 0)` of `Jac(C)(F_q)`.
    pub fn identity(m: u32) -> Self {
        Self {
            u: F2mPoly::one(m),
            v: F2mPoly::zero(m),
        }
    }

    /// Construct and validate a canonical reduced Mumford pair.
    pub fn try_new(
        curve: &HyperellipticCurve,
        u: F2mPoly,
        v: F2mPoly,
    ) -> Result<Self, HyperellipticError> {
        curve.validate()?;
        let divisor = Self { u, v };
        divisor.validate_on_valid_curve(curve)?;
        Ok(divisor)
    }

    /// Embed an affine point `P = (x_0, y_0)` on `C` into `Jac(C)` as
    /// the class of `[P] − [∞]`.
    ///
    /// This compatibility wrapper returns `None` for invalid public input.
    /// Use [`Self::try_from_point`] to retain the structured error.  Ramified
    /// points with `h(x_0)=0` are accepted: their pair `(x+x_0, y_0)` is a
    /// valid reduced divisor (and is fixed by negation).
    pub fn from_point(
        curve: &HyperellipticCurve,
        x0: &F2mElement,
        y0: &F2mElement,
    ) -> Option<Self> {
        Self::try_from_point(curve, x0, y0).ok()
    }

    /// Checked affine-point embedding `P -> [P]-[infinity]`.
    pub fn try_from_point(
        curve: &HyperellipticCurve,
        x0: &F2mElement,
        y0: &F2mElement,
    ) -> Result<Self, HyperellipticError> {
        curve.validate()?;
        if x0.m_value() != curve.m {
            return Err(HyperellipticError::CoordinateFieldMismatch {
                coordinate: "x",
                expected: curve.m,
                actual: x0.m_value(),
            });
        }
        if y0.m_value() != curve.m {
            return Err(HyperellipticError::CoordinateFieldMismatch {
                coordinate: "y",
                expected: curve.m,
                actual: y0.m_value(),
            });
        }
        let lhs = y0
            .square(&curve.irr)
            .add(&curve.h.eval(x0, &curve.irr).mul(y0, &curve.irr));
        if lhs != curve.f.eval(x0, &curve.irr) {
            return Err(HyperellipticError::PointNotOnCurve);
        }
        // u(x) = x + x₀  (char 2; "x − x₀" = "x + x₀").
        let u = F2mPoly::from_coeffs(vec![x0.clone(), F2mElement::one(curve.m)], curve.m);
        // v(x) = y₀ (constant).
        let v = F2mPoly::constant(y0.clone());
        let divisor = Self { u, v };
        divisor.validate_on_valid_curve(curve)?;
        Ok(divisor)
    }

    /// `true` iff `(u, v)` already satisfies the reduced-divisor
    /// invariants: `u` monic, `deg v < deg u ≤ g`, `u | v² + h·v + f`.
    /// This is the boolean compatibility form of [`Self::validate`].
    pub fn is_reduced(&self, curve: &HyperellipticCurve) -> bool {
        self.validate(curve).is_ok()
    }

    /// Validate this pair as the canonical reduced representative of a
    /// divisor class on `curve`.
    pub fn validate(&self, curve: &HyperellipticCurve) -> Result<(), HyperellipticError> {
        curve.validate()?;
        self.validate_on_valid_curve(curve)
    }

    /// Validate both canonical representatives and compare their divisor
    /// classes.  Reduced Mumford representatives are unique in the supported
    /// one-infinity model, so coefficient equality is class equality.
    pub fn try_eq(
        &self,
        other: &Self,
        curve: &HyperellipticCurve,
    ) -> Result<bool, HyperellipticError> {
        curve.validate()?;
        self.validate_on_valid_curve(curve)?;
        other.validate_on_valid_curve(curve)?;
        Ok(self == other)
    }

    fn validate_on_valid_curve(
        &self,
        curve: &HyperellipticCurve,
    ) -> Result<(), HyperellipticError> {
        curve.validate_polynomial("u", &self.u)?;
        curve.validate_polynomial("v", &self.v)?;
        if self.u.is_zero() {
            return Err(HyperellipticError::ZeroDivisorPolynomial);
        }
        if self.u.lead() != F2mElement::one(curve.m) {
            return Err(HyperellipticError::NonMonicDivisorPolynomial);
        }
        let du = self.u.degree().unwrap();
        if du > curve.genus as usize {
            return Err(HyperellipticError::DivisorDegreeTooLarge {
                maximum: curve.genus as usize,
                actual: du,
            });
        }
        if let Some(dv) = self.v.degree().filter(|&degree| degree >= du) {
            return Err(HyperellipticError::DivisorVNotReduced {
                u_degree: du,
                v_degree: dv,
            });
        }
        // u | v² + h·v + f
        let vsq = self.v.mul(&self.v, &curve.irr);
        let hv = curve.h.mul(&self.v, &curve.irr);
        let target = vsq.add(&hv).add(&curve.f);
        let (_q, r) = target.divrem(&self.u, &curve.irr);
        if !r.is_zero() {
            return Err(HyperellipticError::DivisorEquationNotDivisible);
        }
        Ok(())
    }

    /// `D + (0)`  ≡  `D` — the additive identity check.
    pub fn is_identity(&self) -> bool {
        self.u == F2mPoly::one(self.u.m) && self.v.is_zero()
    }

    /// **Negation**: `−(u, v) = (u, (h + v) mod u)`.
    ///
    /// On the underlying curve this maps `(x_i, y_i)` to
    /// `(x_i, y_i + h(x_i))` — the "other" root of the quadratic.
    pub fn neg(&self, curve: &HyperellipticCurve) -> Self {
        self.try_neg(curve)
            .expect("invalid divisor or curve in Mumford negation")
    }

    /// Checked negation.
    pub fn try_neg(&self, curve: &HyperellipticCurve) -> Result<Self, HyperellipticError> {
        curve.validate()?;
        self.try_neg_on_valid_curve(curve)
    }

    fn try_neg_on_valid_curve(
        &self,
        curve: &HyperellipticCurve,
    ) -> Result<Self, HyperellipticError> {
        self.validate_on_valid_curve(curve)?;
        let h_plus_v = curve.h.add(&self.v);
        let v_new = h_plus_v.rem(&self.u, &curve.irr);
        let result = Self {
            u: self.u.clone(),
            v: v_new,
        };
        result.validate_on_valid_curve(curve)?;
        Ok(result)
    }

    /// **Cantor composition**: produce a (possibly unreduced) divisor
    /// representing `self + other`.  Result has `deg u ≤ 2g`; callers
    /// should follow with `try_reduce` to bring it back to `deg u ≤ g`.
    fn try_cantor_compose(
        &self,
        other: &Self,
        curve: &HyperellipticCurve,
    ) -> Result<Self, HyperellipticError> {
        let irr = &curve.irr;
        // Step 1: d1 = gcd(u1, u2) = e1·u1 + e2·u2
        let (d1, e1, e2) = self.u.ext_gcd(&other.u, irr);
        // Step 2: d = gcd(d1, v1 + v2 + h) = c1·d1 + c2·(v1+v2+h)
        let v_sum = self.v.add(&other.v).add(&curve.h);
        let (d, c1, c2) = d1.ext_gcd(&v_sum, irr);
        // Step 3: combine — s1 = c1·e1, s2 = c1·e2, s3 = c2
        let s1 = c1.mul(&e1, irr);
        let s2 = c1.mul(&e2, irr);
        let s3 = c2.clone();
        // Step 4: u' = u1·u2 / d²
        let u_prod = self.u.mul(&other.u, irr);
        let d_sq = d.mul(&d, irr);
        let (u_prime, u_rem) = u_prod.divrem(&d_sq, irr);
        if !u_rem.is_zero() {
            return Err(HyperellipticError::NonExactCompositionUDivision);
        }
        // Step 5: v' = (s1·u1·v2 + s2·u2·v1 + s3·(v1·v2 + f)) / d  (mod u')
        let term1 = s1.mul(&self.u, irr).mul(&other.v, irr);
        let term2 = s2.mul(&other.u, irr).mul(&self.v, irr);
        let v1v2 = self.v.mul(&other.v, irr);
        let term3 = s3.mul(&v1v2.add(&curve.f), irr);
        let v_num = term1.add(&term2).add(&term3);
        let (v_div, v_div_rem) = v_num.divrem(&d, irr);
        if !v_div_rem.is_zero() {
            return Err(HyperellipticError::NonExactCompositionVDivision);
        }
        let v_prime = v_div.rem(&u_prime, irr);
        Ok(Self {
            u: u_prime,
            v: v_prime,
        })
    }

    /// **Cantor reduction**: bring `(u, v)` with `deg u > g` back to
    /// `deg u ≤ g` by repeated application of the standard reduction
    /// step.  Idempotent on already-reduced divisors.
    fn try_reduce(&self, curve: &HyperellipticCurve) -> Result<Self, HyperellipticError> {
        let irr = &curve.irr;
        let g = curve.genus as usize;
        let mut u = self.u.clone();
        let mut v = self.v.clone();
        while u.degree().map(|d| d > g).unwrap_or(false) {
            // u_new = (f + h·v + v²) / u
            let vsq = v.mul(&v, irr);
            let hv = curve.h.mul(&v, irr);
            let num = curve.f.add(&hv).add(&vsq);
            let (u_new_raw, rem) = num.divrem(&u, irr);
            if !rem.is_zero() {
                return Err(HyperellipticError::NonExactReductionDivision);
            }
            if u_new_raw.is_zero() {
                return Err(HyperellipticError::ZeroReductionPolynomial);
            }
            // Make u_new monic.
            let u_new = u_new_raw.monic(irr);
            // v_new = (h + v) mod u_new
            let v_new = curve.h.add(&v).rem(&u_new, irr);
            u = u_new;
            v = v_new;
        }
        // Final monic-normalisation just in case the loop exited
        // with a non-monic u (it shouldn't, but be safe).
        if !u.is_zero() && u.lead() != F2mElement::one(u.m) {
            u = u.monic(irr);
        }
        Ok(Self { u, v })
    }

    /// **Group addition** in `Jac(C)(F_q)`.
    pub fn add(&self, other: &Self, curve: &HyperellipticCurve) -> Self {
        self.try_add(other, curve)
            .expect("invalid divisor or curve in Cantor addition")
    }

    /// Checked group addition in `Jac(C)(F_q)`.
    pub fn try_add(
        &self,
        other: &Self,
        curve: &HyperellipticCurve,
    ) -> Result<Self, HyperellipticError> {
        curve.validate()?;
        self.try_add_on_valid_curve(other, curve)
    }

    fn try_add_on_valid_curve(
        &self,
        other: &Self,
        curve: &HyperellipticCurve,
    ) -> Result<Self, HyperellipticError> {
        self.validate_on_valid_curve(curve)?;
        other.validate_on_valid_curve(curve)?;
        // Short-circuit identity.
        if self.is_identity() {
            return Ok(other.clone());
        }
        if other.is_identity() {
            return Ok(self.clone());
        }
        let composed = self.try_cantor_compose(other, curve)?;
        let result = composed.try_reduce(curve)?;
        result.validate_on_valid_curve(curve)?;
        Ok(result)
    }

    /// **Doubling** — `2·self`.  Cantor's algorithm handles the
    /// `u_1 = u_2` case correctly through `gcd`, so we just call
    /// `add` with `self` on both sides; a specialised doubling
    /// formula could be added for speed.
    pub fn double(&self, curve: &HyperellipticCurve) -> Self {
        self.try_double(curve)
            .expect("invalid divisor or curve in Cantor doubling")
    }

    /// Checked doubling.
    pub fn try_double(&self, curve: &HyperellipticCurve) -> Result<Self, HyperellipticError> {
        curve.validate()?;
        self.try_add_on_valid_curve(self, curve)
    }

    /// **Scalar multiplication** `[k]·self` via left-to-right
    /// double-and-add.
    pub fn scalar_mul(&self, k: &BigUint, curve: &HyperellipticCurve) -> Self {
        self.try_scalar_mul(k, curve)
            .expect("invalid divisor or curve in scalar multiplication")
    }

    /// Checked scalar multiplication via left-to-right double-and-add.
    pub fn try_scalar_mul(
        &self,
        k: &BigUint,
        curve: &HyperellipticCurve,
    ) -> Result<Self, HyperellipticError> {
        curve.validate()?;
        self.validate_on_valid_curve(curve)?;
        if k.is_zero() {
            return Ok(Self::identity(curve.m));
        }
        let bits = k.bits();
        let mut result = Self::identity(curve.m);
        for i in (0..bits).rev() {
            result = result.try_add_on_valid_curve(&result, curve)?;
            if k.bit(i) {
                result = result.try_add_on_valid_curve(self, curve)?;
            }
        }
        Ok(result)
    }
}

// ── HCDLP solvers ────────────────────────────────────────────────────

/// **Baby-step / Giant-step** for `Q = [k]·P` on `Jac(C)`.  Returns
/// `Some(k)` with `0 ≤ k < bound` if a solution exists, else `None`.
///
/// Memory `O(√bound)`; time `O(√bound · log bound)`.  Good for toy
/// Jacobians with `#Jac(C)(F_q) ≤ 2^{30}` or so.
pub fn hcdlp_bsgs(
    p: &MumfordDivisor,
    q: &MumfordDivisor,
    bound: &BigUint,
    curve: &HyperellipticCurve,
) -> Option<BigUint> {
    use std::collections::HashMap;
    // m = ceil(sqrt(bound))
    let sqrt_b = bound.sqrt() + BigUint::one();
    let m = sqrt_b;
    // Baby steps: { (i, i·P) : 0 ≤ i < m }
    let mut table: HashMap<(Vec<u8>, Vec<u8>), BigUint> = HashMap::new();
    let mut acc = MumfordDivisor::identity(curve.m);
    let mut i = BigUint::zero();
    while i < m {
        let key = divisor_key(&acc);
        table.entry(key).or_insert_with(|| i.clone());
        acc = acc.add(p, curve);
        i += BigUint::one();
    }
    // Giant step factor: γ = [m]·P.  Walk Q, Q − γ, Q − 2γ, …, look up.
    let gamma = p.scalar_mul(&m, curve);
    let neg_gamma = gamma.neg(curve);
    let mut gq = q.clone();
    let mut j = BigUint::zero();
    while j < m {
        let key = divisor_key(&gq);
        if let Some(i_val) = table.get(&key) {
            // k = j·m + i  (mod #Jac); we don't know #Jac here, so
            // return the lift in [0, bound).
            let k = &j * &m + i_val;
            if &k < bound {
                return Some(k);
            }
        }
        gq = gq.add(&neg_gamma, curve);
        j += BigUint::one();
    }
    None
}

fn divisor_key(d: &MumfordDivisor) -> (Vec<u8>, Vec<u8>) {
    let serialize = |p: &F2mPoly| -> Vec<u8> {
        let mut out = Vec::new();
        for c in &p.coeffs {
            let bytes = c.to_biguint().to_bytes_be();
            out.push(bytes.len() as u8);
            out.extend(bytes);
        }
        out
    };
    (serialize(&d.u), serialize(&d.v))
}

/// **Pollard's ρ** on `Jac(C)(F_q)`.  Three-partition deterministic
/// walk; halts when a collision is found.  Requires the group order
/// `n` (or a multiple of it) to extract the discrete log.
///
/// Same caveat as the elliptic version: `O(√n)` time, exponential
/// in the genus.
pub fn hcdlp_pollard_rho(
    p: &MumfordDivisor,
    q: &MumfordDivisor,
    order: &BigUint,
    curve: &HyperellipticCurve,
) -> Option<BigUint> {
    use crate::utils::mod_inverse;
    // Three-partition walker.
    let partition = |d: &MumfordDivisor| -> usize {
        // Hash-based partition: take the trailing byte of u's
        // constant coefficient mod 3.
        let c0 = d.u.coeff(0).to_biguint();
        let b = c0.to_bytes_be().last().copied().unwrap_or(0);
        (b as usize) % 3
    };
    let step =
        |d: &MumfordDivisor, a: &BigUint, b: &BigUint| -> (MumfordDivisor, BigUint, BigUint) {
            match partition(d) {
                0 => (d.add(p, curve), (a + 1u32) % order, b.clone()),
                1 => (d.double(curve), (a * 2u32) % order, (b * 2u32) % order),
                _ => (d.add(q, curve), a.clone(), (b + 1u32) % order),
            }
        };
    let mut x = MumfordDivisor::identity(curve.m);
    let mut a = BigUint::zero();
    let mut b = BigUint::zero();
    let mut xt = x.clone();
    let mut at = a.clone();
    let mut bt = b.clone();
    let max_steps: u64 = 1 << 24;
    for _ in 0..max_steps {
        let (nx, na, nb) = step(&x, &a, &b);
        x = nx;
        a = na;
        b = nb;
        let (nx, na, nb) = step(&xt, &at, &bt);
        let (nx, na, nb) = step(&nx, &na, &nb);
        xt = nx;
        at = na;
        bt = nb;
        if x == xt {
            // a + b·k ≡ at + bt·k  ⇒  k ≡ (a − at)/(bt − b)  (mod order).
            let num = if a >= at { &a - &at } else { order + &a - &at };
            let den = if bt >= b { &bt - &b } else { order + &bt - &b };
            if den.is_zero() {
                return None; // bad walk; caller should retry
            }
            let den_inv = mod_inverse(&den, order)?;
            let k = (&num * &den_inv) % order;
            // Verify.
            if p.scalar_mul(&k, curve) == *q {
                return Some(k);
            }
            return None;
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::binary_ecc::f2m::IrreduciblePoly;
    use std::collections::HashSet;

    fn f8(value: u32) -> F2mElement {
        F2mElement::from_biguint(&BigUint::from(value), 3)
    }

    /// The checker’s explicit binary cubic pullback for
    /// E: y²+xy=x³+x²+3 over F8[z]/(z³+z+1):
    ///
    /// H: v²+u²v=u⁷+u⁴+7u,  (x,y)=(u³,u v+7).
    fn binary_cubic_cover_f8() -> HyperellipticCurve {
        let m = 3;
        let irr = IrreduciblePoly {
            degree: m,
            low_terms: vec![0, 1],
        };
        let h = F2mPoly::monomial(F2mElement::one(m), 2);
        let mut f_coefficients = vec![F2mElement::zero(m); 8];
        f_coefficients[1] = f8(7); // d=sqrt(3), since 7²=3 in this basis.
        f_coefficients[4] = F2mElement::one(m);
        f_coefficients[7] = F2mElement::one(m);
        HyperellipticCurve::try_new(m, irr, h, F2mPoly::from_coeffs(f_coefficients, m), 3).unwrap()
    }

    fn coefficients_from_code(
        mut code: usize,
        length: usize,
        elements: &[F2mElement],
    ) -> Vec<F2mElement> {
        let radix = elements.len();
        (0..length)
            .map(|_| {
                let coefficient = elements[code % radix].clone();
                code /= radix;
                coefficient
            })
            .collect()
    }

    fn all_reduced_f8_divisors(curve: &HyperellipticCurve) -> Vec<MumfordDivisor> {
        curve.validate().unwrap();
        let elements: Vec<_> = (0..8).map(f8).collect();
        let mut divisors = vec![MumfordDivisor::identity(curve.m)];
        for u_degree in 1..=curve.genus as usize {
            let coefficient_vectors = elements.len().pow(u_degree as u32);
            for u_code in 0..coefficient_vectors {
                let mut u_coefficients = coefficients_from_code(u_code, u_degree, &elements);
                u_coefficients.push(F2mElement::one(curve.m));
                let u = F2mPoly::from_coeffs(u_coefficients, curve.m);
                for v_code in 0..coefficient_vectors {
                    let v = F2mPoly::from_coeffs(
                        coefficients_from_code(v_code, u_degree, &elements),
                        curve.m,
                    );
                    let divisor = MumfordDivisor { u: u.clone(), v };
                    if divisor.validate_on_valid_curve(curve).is_ok() {
                        divisors.push(divisor);
                    }
                }
            }
        }
        divisors
    }

    fn add_prevalidated(
        left: &MumfordDivisor,
        right: &MumfordDivisor,
        curve: &HyperellipticCurve,
    ) -> MumfordDivisor {
        if left.is_identity() {
            return right.clone();
        }
        if right.is_identity() {
            return left.clone();
        }
        left.try_cantor_compose(right, curve)
            .unwrap()
            .try_reduce(curve)
            .unwrap()
    }

    /// Genus-1 hyperelliptic curve over F_{2^8} — i.e., an elliptic
    /// curve in disguise, useful for sanity-checking the Jacobian
    /// arithmetic against the known elliptic group law.
    fn g1_curve_f16() -> HyperellipticCurve {
        let irr = IrreduciblePoly::deg_8();
        let m = 8;
        // C: y² + (x+1)·y = x³ + x + 1   (toy)
        let h = F2mPoly::from_coeffs(vec![F2mElement::one(m), F2mElement::one(m)], m);
        let mut f_coeffs = vec![F2mElement::zero(m); 4];
        f_coeffs[0] = F2mElement::one(m);
        f_coeffs[1] = F2mElement::one(m);
        f_coeffs[3] = F2mElement::one(m);
        let f = F2mPoly::from_coeffs(f_coeffs, m);
        HyperellipticCurve::new(m, irr, h, f, 1)
    }

    #[test]
    fn identity_is_identity() {
        let curve = g1_curve_f16();
        let id = MumfordDivisor::identity(curve.m);
        assert!(id.is_identity());
        // Identity + identity = identity.
        let sum = id.add(&id, &curve);
        assert!(sum.is_identity());
    }

    #[test]
    fn neg_then_add_is_identity() {
        let curve = g1_curve_f16();
        // Find an affine point on the curve by trial.
        let m = curve.m;
        let mut found = None;
        for xi in 1u64..256 {
            let x = F2mElement::from_biguint(&BigUint::from(xi), m);
            // y² + h(x)·y = f(x)  →  y² + h(x)·y + f(x) = 0
            for yi in 0u64..256 {
                let y = F2mElement::from_biguint(&BigUint::from(yi), m);
                if curve.is_on_curve(&x, &y) {
                    let h_at_x = curve.h.eval(&x, &curve.irr);
                    if !h_at_x.is_zero() {
                        found = Some((x.clone(), y.clone()));
                        break;
                    }
                }
            }
            if found.is_some() {
                break;
            }
        }
        let (x0, y0) = found.expect("a generic point exists");
        let d = MumfordDivisor::from_point(&curve, &x0, &y0).unwrap();
        let neg_d = d.neg(&curve);
        let sum = d.add(&neg_d, &curve);
        assert!(sum.is_identity(), "D + (-D) should be identity");
    }

    #[test]
    fn double_equals_self_add() {
        let curve = g1_curve_f16();
        let m = curve.m;
        // Find two generic points P, Q with x_P ≠ x_Q.
        let mut points = Vec::new();
        'outer: for xi in 1u64..256 {
            let x = F2mElement::from_biguint(&BigUint::from(xi), m);
            for yi in 0u64..256 {
                let y = F2mElement::from_biguint(&BigUint::from(yi), m);
                if curve.is_on_curve(&x, &y) {
                    let h_at_x = curve.h.eval(&x, &curve.irr);
                    if !h_at_x.is_zero() {
                        points.push((x.clone(), y.clone()));
                        if points.len() >= 4 {
                            break 'outer;
                        }
                        break;
                    }
                }
            }
        }
        assert!(points.len() >= 2);
        let p = MumfordDivisor::from_point(&curve, &points[0].0, &points[0].1).unwrap();
        let pp_dbl = p.double(&curve);
        let pp_add = p.add(&p, &curve);
        assert_eq!(pp_dbl, pp_add);
    }

    #[test]
    fn scalar_mul_distributes_over_zero() {
        let curve = g1_curve_f16();
        let m = curve.m;
        // Any point ⋅ 0 = identity.
        let x = F2mElement::from_biguint(&BigUint::from(5u32), m);
        // Find a y for this x (or skip).
        let mut p = None;
        for yi in 0u64..256 {
            let y = F2mElement::from_biguint(&BigUint::from(yi), m);
            if curve.is_on_curve(&x, &y) {
                let h_at_x = curve.h.eval(&x, &curve.irr);
                if !h_at_x.is_zero() {
                    p = MumfordDivisor::from_point(&curve, &x, &y);
                    break;
                }
            }
        }
        if let Some(p) = p {
            let zero_p = p.scalar_mul(&BigUint::zero(), &curve);
            assert!(zero_p.is_identity());
            let one_p = p.scalar_mul(&BigUint::one(), &curve);
            assert_eq!(one_p, p);
        }
    }

    #[test]
    fn bsgs_finds_small_dlp() {
        let curve = g1_curve_f16();
        let m = curve.m;
        // Find any generic point.
        let mut p = None;
        'outer: for xi in 1u64..256 {
            let x = F2mElement::from_biguint(&BigUint::from(xi), m);
            for yi in 0u64..256 {
                let y = F2mElement::from_biguint(&BigUint::from(yi), m);
                if curve.is_on_curve(&x, &y) {
                    let h_at_x = curve.h.eval(&x, &curve.irr);
                    if !h_at_x.is_zero() {
                        p = MumfordDivisor::from_point(&curve, &x, &y);
                        break 'outer;
                    }
                }
            }
        }
        let p = p.unwrap();
        let k_true = BigUint::from(13u32);
        let q = p.scalar_mul(&k_true, &curve);
        let recovered = hcdlp_bsgs(&p, &q, &BigUint::from(2000u32), &curve);
        assert_eq!(recovered, Some(k_true));
    }

    #[test]
    fn checked_curve_constructor_binds_field_degree_and_smoothness_errors() {
        let curve = binary_cubic_cover_f8();
        assert_eq!(curve.f.degree(), Some(7));
        assert_eq!(curve.h.degree(), Some(2));
        curve.validate().unwrap();

        let reducible = IrreduciblePoly {
            degree: 3,
            low_terms: vec![0, 1, 2], // z³+z²+z+1=(z+1)³
        };
        assert!(matches!(
            HyperellipticCurve::try_new(3, reducible, curve.h.clone(), curve.f.clone(), 3,),
            Err(HyperellipticError::ReducibleModulus)
        ));

        let mut wrong_degree = curve.clone();
        wrong_degree.irr.degree = 4;
        assert!(matches!(
            wrong_degree.validate(),
            Err(HyperellipticError::FieldDegreeMismatch { .. })
        ));

        let mut duplicate_term = curve.clone();
        duplicate_term.irr.low_terms.push(1);
        assert_eq!(
            duplicate_term.validate(),
            Err(HyperellipticError::DuplicateModulusTerm { term: 1 })
        );

        let mut bad_coefficient_field = curve.clone();
        bad_coefficient_field.h.coeffs[0] = F2mElement::one(2);
        assert!(matches!(
            bad_coefficient_field.validate(),
            Err(HyperellipticError::CoefficientFieldMismatch {
                polynomial: "h",
                coefficient: 0,
                ..
            })
        ));

        let mut even_degree = curve.clone();
        even_degree.f.coeffs.truncate(5);
        assert!(matches!(
            even_degree.validate(),
            Err(HyperellipticError::UnsupportedInfinityConfiguration { .. })
        ));

        let mut h_too_large = curve.clone();
        h_too_large.h = F2mPoly::monomial(F2mElement::one(3), 4);
        assert_eq!(
            h_too_large.validate(),
            Err(HyperellipticError::HDegreeTooLarge {
                maximum: 3,
                actual: 4,
            })
        );

        // Removing the non-zero linear term makes (0,0) singular:
        // h(0)=f(0)=f'(0)=0.
        let mut singular = curve.clone();
        singular.f.coeffs[1] = F2mElement::zero(3);
        assert_eq!(
            singular.validate(),
            Err(HyperellipticError::SingularAffineModel)
        );
    }

    #[test]
    fn explicit_f8_cubic_cover_map_holds_on_every_affine_pair() {
        let curve = binary_cubic_cover_f8();
        let irr = &curve.irr;
        let a = F2mElement::one(3);
        let b = f8(3);
        let d = f8(7);
        assert_eq!(d.square(irr), b);

        let mut cover_points = 0usize;
        for u_value in 0..8 {
            let u = f8(u_value);
            for v_value in 0..8 {
                let v = f8(v_value);
                if !curve.is_on_curve(&u, &v) {
                    continue;
                }
                cover_points += 1;
                let u2 = u.square(irr);
                let x = u2.mul(&u, irr);
                let y = u.mul(&v, irr).add(&d);
                let lhs = y.square(irr).add(&x.mul(&y, irr));
                let x2 = x.square(irr);
                let rhs = x2.mul(&x, irr).add(&a.mul(&x2, irr)).add(&b);
                assert_eq!(lhs, rhs, "cover map failed at u={u_value}, v={v_value}");
            }
        }
        // Frozen direct enumeration over the declared F8 basis.  Infinity is
        // the additional unique rational point of the smooth odd-degree model.
        assert_eq!(cover_points, 5);
    }

    #[test]
    fn ramified_origin_has_a_valid_mumford_pair_and_order_two() {
        let curve = binary_cubic_cover_f8();
        let zero = F2mElement::zero(curve.m);
        assert!(curve.is_on_curve(&zero, &zero));
        assert!(curve.h.eval(&zero, &curve.irr).is_zero());

        let ramified = MumfordDivisor::try_from_point(&curve, &zero, &zero).unwrap();
        assert_eq!(ramified.u, F2mPoly::x(curve.m));
        assert!(ramified.v.is_zero());
        assert_eq!(ramified.try_neg(&curve).unwrap(), ramified);
        assert!(ramified.try_double(&curve).unwrap().is_identity());
        assert!(ramified
            .try_scalar_mul(&BigUint::from(2u32), &curve)
            .unwrap()
            .is_identity());
        assert_eq!(
            ramified
                .try_scalar_mul(&BigUint::from(3u32), &curve)
                .unwrap(),
            ramified
        );
    }

    #[test]
    fn checked_divisor_api_rejects_malformed_public_pairs_without_debug_asserts() {
        let curve = binary_cubic_cover_f8();
        let zero = F2mElement::zero(curve.m);
        let ramified = MumfordDivisor::try_from_point(&curve, &zero, &zero).unwrap();
        assert!(ramified.try_eq(&ramified.clone(), &curve).unwrap());

        let zero_u = MumfordDivisor {
            u: F2mPoly::zero(curve.m),
            v: F2mPoly::zero(curve.m),
        };
        assert_eq!(
            zero_u.try_add(&ramified, &curve),
            Err(HyperellipticError::ZeroDivisorPolynomial)
        );
        assert_eq!(
            zero_u.try_eq(&ramified, &curve),
            Err(HyperellipticError::ZeroDivisorPolynomial)
        );

        let non_monic = MumfordDivisor {
            u: F2mPoly::constant(f8(2)),
            v: F2mPoly::zero(curve.m),
        };
        assert_eq!(
            non_monic.validate(&curve),
            Err(HyperellipticError::NonMonicDivisorPolynomial)
        );

        let trailing_zero = MumfordDivisor {
            u: F2mPoly {
                m: curve.m,
                coeffs: vec![F2mElement::one(curve.m), F2mElement::zero(curve.m)],
            },
            v: F2mPoly::zero(curve.m),
        };
        assert_eq!(
            trailing_zero.validate(&curve),
            Err(HyperellipticError::NonCanonicalPolynomial { polynomial: "u" })
        );

        let wrong_field = MumfordDivisor {
            u: F2mPoly::one(2),
            v: F2mPoly::zero(2),
        };
        assert!(matches!(
            wrong_field.try_add(&ramified, &curve),
            Err(HyperellipticError::PolynomialFieldMismatch {
                polynomial: "u",
                ..
            })
        ));

        // The private reduction primitive now reports its formerly
        // debug-only exact-division failure.  Public checked addition rejects
        // malformed inputs before reaching this path.
        let invalid_unreduced = MumfordDivisor {
            u: F2mPoly::monomial(F2mElement::one(curve.m), 4),
            v: F2mPoly::zero(curve.m),
        };
        assert_eq!(
            invalid_unreduced.try_reduce(&curve),
            Err(HyperellipticError::NonExactReductionDivision)
        );

        let wrong_width = F2mElement::zero(2);
        assert!(matches!(
            MumfordDivisor::try_from_point(&curve, &wrong_width, &wrong_width),
            Err(HyperellipticError::CoordinateFieldMismatch { .. })
        ));
        assert_eq!(
            MumfordDivisor::try_from_point(&curve, &F2mElement::one(3), &zero),
            Err(HyperellipticError::PointNotOnCurve)
        );
    }

    #[test]
    fn exhaustive_f8_reduced_domain_has_closure_inverses_and_scalar_consistency() {
        let curve = binary_cubic_cover_f8();
        let divisors = all_reduced_f8_divisors(&curve);
        let keys: HashSet<_> = divisors.iter().map(divisor_key).collect();
        assert_eq!(
            keys.len(),
            divisors.len(),
            "Mumford representatives must be unique"
        );
        assert_eq!(divisors.len(), 486, "frozen exhaustive F8 Jacobian order");

        for divisor in &divisors {
            divisor.validate_on_valid_curve(&curve).unwrap();
            let inverse = divisor.try_neg_on_valid_curve(&curve).unwrap();
            assert!(keys.contains(&divisor_key(&inverse)));
            assert!(divisor
                .try_add_on_valid_curve(&inverse, &curve)
                .unwrap()
                .is_identity());
            assert_eq!(
                divisor
                    .try_scalar_mul(&BigUint::from(2u32), &curve)
                    .unwrap(),
                divisor.try_add_on_valid_curve(divisor, &curve).unwrap()
            );
        }

        // Exhaust every unordered pair of canonical reduced representatives.
        // This checks the shared-support and cancellation branches encountered
        // in the complete small domain, not only point divisors.  The dedicated
        // shared-support test below checks both operand orders.
        for (left_index, left) in divisors.iter().enumerate() {
            for right in divisors.iter().skip(left_index) {
                let sum = add_prevalidated(left, right, &curve);
                assert!(keys.contains(&divisor_key(&sum)));
            }
        }
    }

    #[test]
    fn nontrivial_shared_support_divisors_cover_both_cantor_gcd_branches() {
        let curve = binary_cubic_cover_f8();
        let divisors = all_reduced_f8_divisors(&curve);
        let mut retained_shared_support = None;
        let mut cancelled_shared_support = None;

        'pairs: for (left_index, left) in divisors.iter().enumerate() {
            if left.u.degree().unwrap_or(0) < 2 {
                continue;
            }
            for right in divisors.iter().skip(left_index + 1) {
                if right.u.degree().unwrap_or(0) < 2 {
                    continue;
                }
                let shared = left.u.gcd(&right.u, &curve.irr);
                if shared.degree() != Some(1) {
                    continue;
                }
                let cancellation = shared.gcd(&left.v.add(&right.v).add(&curve.h), &curve.irr);
                match cancellation.degree() {
                    Some(0) if retained_shared_support.is_none() => {
                        retained_shared_support = Some((left.clone(), right.clone()));
                    }
                    Some(1) if cancelled_shared_support.is_none() => {
                        cancelled_shared_support = Some((left.clone(), right.clone()));
                    }
                    _ => {}
                }
                if retained_shared_support.is_some() && cancelled_shared_support.is_some() {
                    break 'pairs;
                }
            }
        }

        for (left, right) in [
            retained_shared_support.expect("a retained shared-support pair"),
            cancelled_shared_support.expect("a cancelling shared-support pair"),
        ] {
            assert_ne!(left, right);
            let sum = left.try_add(&right, &curve).unwrap();
            assert!(sum.is_reduced(&curve));
            assert_eq!(sum, right.try_add(&left, &curve).unwrap());
            assert_eq!(
                sum.try_add(&right.try_neg(&curve).unwrap(), &curve)
                    .unwrap(),
                left
            );
        }
    }
}
