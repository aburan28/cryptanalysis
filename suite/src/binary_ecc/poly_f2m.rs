//! **Polynomial ring `F_{2^m}[x]`** — built on top of [`crate::binary_ecc::f2m`].
//!
//! Coefficients are [`F2mElement`]s; the polynomial itself is a `Vec`
//! of coefficients where `coeffs[i]` is the coefficient of `x^i`.
//! The polynomial carries the field parameter `m` and a reference to
//! an [`IrreduciblePoly`] is threaded through every operation that
//! needs to do field arithmetic (multiplication, inversion, GCD).
//!
//! This module is the foundation for the **hyperelliptic curve**
//! arithmetic in [`crate::binary_ecc::hyperelliptic`], which in turn
//! supports the GHS Weil-descent attack in
//! [`crate::cryptanalysis::ghs_descent`] used by Teske's elliptic-
//! curve trapdoor system.
//!
//! ## What you get
//!
//! - [`F2mPoly`] — polynomial type with `add`, `sub` (= `add` in char 2),
//!   `mul`, `divrem`, `gcd`, `ext_gcd` (Bézout coefficients),
//!   `eval`, `is_zero`, `degree`, `lead`, `monic`.
//! - Scalar multiplication by a field element, by `x^k`, and
//!   evaluation at points in `F_{2^m}`.
//! - Conversion to/from coefficient vectors for serialisation.
//!
//! ## Honest scope
//!
//! - Variable-time.  Same caveat as the rest of `binary_ecc`: this
//!   is for *cryptanalysis* (constructing weak instances, executing
//!   the attack), not for deployment.
//! - Schoolbook multiplication.  For the polynomial degrees we deal
//!   with (genus ≤ ~10, so deg ≤ ~20), this is plenty.  Karatsuba
//!   could be added if needed.

use super::f2m::{F2mElement, IrreduciblePoly};

/// A polynomial `Σ c_i · x^i` with coefficients in `F_{2^m}`.
///
/// `coeffs[i]` is the coefficient of `x^i`.  The representation is
/// **not** normalized eagerly — `degree()` walks down skipping zero
/// trailing coefficients.  Use [`F2mPoly::trim`] to drop them in place.
#[derive(Clone, Debug)]
pub struct F2mPoly {
    pub m: u32,
    pub coeffs: Vec<F2mElement>,
}

impl F2mPoly {
    /// The zero polynomial.
    pub fn zero(m: u32) -> Self {
        Self {
            m,
            coeffs: Vec::new(),
        }
    }

    /// The constant `1`.
    pub fn one(m: u32) -> Self {
        Self {
            m,
            coeffs: vec![F2mElement::one(m)],
        }
    }

    /// `x`.
    pub fn x(m: u32) -> Self {
        Self {
            m,
            coeffs: vec![F2mElement::zero(m), F2mElement::one(m)],
        }
    }

    /// The monomial `c · x^k`.
    pub fn monomial(c: F2mElement, k: usize) -> Self {
        if c.is_zero() {
            return Self::zero(c.m_value());
        }
        let m = c.m_value();
        let mut coeffs = vec![F2mElement::zero(m); k];
        coeffs.push(c);
        Self { m, coeffs }
    }

    /// Build from a coefficient slice (lowest-degree first).
    pub fn from_coeffs(coeffs: Vec<F2mElement>, m: u32) -> Self {
        let mut p = Self { m, coeffs };
        p.trim();
        p
    }

    /// Build a constant polynomial.
    pub fn constant(c: F2mElement) -> Self {
        if c.is_zero() {
            Self::zero(c.m_value())
        } else {
            Self {
                m: c.m_value(),
                coeffs: vec![c],
            }
        }
    }

    /// Strip trailing zero coefficients.
    pub fn trim(&mut self) {
        while let Some(last) = self.coeffs.last() {
            if last.is_zero() {
                self.coeffs.pop();
            } else {
                break;
            }
        }
    }

    /// `true` iff the polynomial is identically zero.
    pub fn is_zero(&self) -> bool {
        self.coeffs.iter().all(|c| c.is_zero())
    }

    /// Degree.  Returns `None` for the zero polynomial.
    pub fn degree(&self) -> Option<usize> {
        for (i, c) in self.coeffs.iter().enumerate().rev() {
            if !c.is_zero() {
                return Some(i);
            }
        }
        None
    }

    /// Leading coefficient.  Returns the zero element when the
    /// polynomial is zero (caller must check `is_zero` first if it
    /// needs to distinguish).
    pub fn lead(&self) -> F2mElement {
        match self.degree() {
            Some(d) => self.coeffs[d].clone(),
            None => F2mElement::zero(self.m),
        }
    }

    /// Coefficient of `x^i`; out-of-range returns zero.
    pub fn coeff(&self, i: usize) -> F2mElement {
        self.coeffs
            .get(i)
            .cloned()
            .unwrap_or_else(|| F2mElement::zero(self.m))
    }

    /// `self + other`.  In `F_{2^m}` this is XOR coefficient-wise.
    pub fn add(&self, other: &Self) -> Self {
        debug_assert_eq!(self.m, other.m);
        let n = self.coeffs.len().max(other.coeffs.len());
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push(self.coeff(i).add(&other.coeff(i)));
        }
        let mut p = Self {
            m: self.m,
            coeffs: out,
        };
        p.trim();
        p
    }

    /// `self - other`.  Char 2 ⇒ same as `add`.
    pub fn sub(&self, other: &Self) -> Self {
        self.add(other)
    }

    /// Negation.  Char 2 ⇒ identity.
    pub fn neg(&self) -> Self {
        self.clone()
    }

    /// `self · other` (schoolbook).
    pub fn mul(&self, other: &Self, irr: &IrreduciblePoly) -> Self {
        if self.is_zero() || other.is_zero() {
            return Self::zero(self.m);
        }
        let d1 = self.degree().unwrap();
        let d2 = other.degree().unwrap();
        let mut out = vec![F2mElement::zero(self.m); d1 + d2 + 1];
        for i in 0..=d1 {
            let ci = &self.coeffs[i];
            if ci.is_zero() {
                continue;
            }
            for j in 0..=d2 {
                let cj = &other.coeffs[j];
                if cj.is_zero() {
                    continue;
                }
                let prod = ci.mul(cj, irr);
                out[i + j] = out[i + j].add(&prod);
            }
        }
        let mut p = Self {
            m: self.m,
            coeffs: out,
        };
        p.trim();
        p
    }

    /// Multiply every coefficient by a scalar `s ∈ F_{2^m}`.
    pub fn scalar_mul(&self, s: &F2mElement, irr: &IrreduciblePoly) -> Self {
        if s.is_zero() {
            return Self::zero(self.m);
        }
        let coeffs = self.coeffs.iter().map(|c| c.mul(s, irr)).collect();
        let mut p = Self { m: self.m, coeffs };
        p.trim();
        p
    }

    /// `self · x^k` — shift up.
    pub fn shift(&self, k: usize) -> Self {
        if self.is_zero() {
            return Self::zero(self.m);
        }
        let mut coeffs = vec![F2mElement::zero(self.m); k];
        coeffs.extend_from_slice(&self.coeffs);
        Self { m: self.m, coeffs }
    }

    /// Divide by `x^k` — shift down.  Truncates (drops) the lower
    /// `k` coefficients.  Returns the quotient polynomial; the
    /// remainder is silently discarded.  Caller must ensure the
    /// quotient is exact when that matters.
    pub fn shift_down(&self, k: usize) -> Self {
        if k >= self.coeffs.len() {
            return Self::zero(self.m);
        }
        let coeffs = self.coeffs[k..].to_vec();
        let mut p = Self { m: self.m, coeffs };
        p.trim();
        p
    }

    /// Polynomial long division: returns `(q, r)` with
    /// `self = q · divisor + r` and `deg r < deg divisor`.
    /// Panics if `divisor` is zero.
    pub fn divrem(&self, divisor: &Self, irr: &IrreduciblePoly) -> (Self, Self) {
        assert!(!divisor.is_zero(), "division by zero polynomial");
        let m = self.m;
        let mut r = self.clone();
        let mut q = Self::zero(m);
        let d_deg = divisor.degree().unwrap();
        let d_lead_inv = divisor.lead().flt_inverse(irr).expect("non-zero lead");
        while let Some(r_deg) = r.degree() {
            if r_deg < d_deg {
                break;
            }
            // Compute the coefficient and degree of the next term of q.
            let coef = r.coeffs[r_deg].mul(&d_lead_inv, irr);
            let shift = r_deg - d_deg;
            // q += coef · x^shift
            if q.coeffs.len() <= shift {
                q.coeffs.resize(shift + 1, F2mElement::zero(m));
            }
            q.coeffs[shift] = q.coeffs[shift].add(&coef);
            // r -= (coef · x^shift) · divisor
            let term = Self::monomial(coef, shift);
            let sub = term.mul(divisor, irr);
            r = r.add(&sub);
            r.trim();
        }
        q.trim();
        (q, r)
    }

    /// Euclidean GCD.  Returns a *monic* GCD.
    pub fn gcd(&self, other: &Self, irr: &IrreduciblePoly) -> Self {
        let mut a = self.clone();
        let mut b = other.clone();
        while !b.is_zero() {
            let (_q, r) = a.divrem(&b, irr);
            a = b;
            b = r;
        }
        // Normalize to monic.
        if a.is_zero() {
            return a;
        }
        let lead_inv = a.lead().flt_inverse(irr).expect("non-zero lead");
        a.scalar_mul(&lead_inv, irr)
    }

    /// Extended Euclidean: returns `(g, s, t)` with `s·self + t·other = g`,
    /// `g` monic.
    pub fn ext_gcd(&self, other: &Self, irr: &IrreduciblePoly) -> (Self, Self, Self) {
        let m = self.m;
        let mut old_r = self.clone();
        let mut r = other.clone();
        let mut old_s = Self::one(m);
        let mut s = Self::zero(m);
        let mut old_t = Self::zero(m);
        let mut t = Self::one(m);
        while !r.is_zero() {
            let (q, _) = old_r.divrem(&r, irr);
            let new_r = old_r.add(&q.mul(&r, irr)); // old_r - q·r  (char 2)
            old_r = r;
            r = new_r;
            let new_s = old_s.add(&q.mul(&s, irr));
            old_s = s;
            s = new_s;
            let new_t = old_t.add(&q.mul(&t, irr));
            old_t = t;
            t = new_t;
        }
        // Normalize `old_r` to monic, scale `old_s` and `old_t` to match.
        if old_r.is_zero() {
            return (old_r, old_s, old_t);
        }
        let lead_inv = old_r.lead().flt_inverse(irr).expect("non-zero lead");
        (
            old_r.scalar_mul(&lead_inv, irr),
            old_s.scalar_mul(&lead_inv, irr),
            old_t.scalar_mul(&lead_inv, irr),
        )
    }

    /// Evaluate `self(x_val)`.
    pub fn eval(&self, x_val: &F2mElement, irr: &IrreduciblePoly) -> F2mElement {
        // Horner's rule.
        let mut acc = F2mElement::zero(self.m);
        for c in self.coeffs.iter().rev() {
            acc = acc.mul(x_val, irr).add(c);
        }
        acc
    }

    /// Make `self` monic (divide by leading coefficient).  Panics on
    /// zero polynomial.
    pub fn monic(&self, irr: &IrreduciblePoly) -> Self {
        let lead = self.lead();
        assert!(!lead.is_zero(), "monic of zero polynomial");
        let inv = lead.flt_inverse(irr).unwrap();
        self.scalar_mul(&inv, irr)
    }

    /// `self mod divisor`.
    pub fn rem(&self, divisor: &Self, irr: &IrreduciblePoly) -> Self {
        self.divrem(divisor, irr).1
    }

    /// Compute `self² (mod m)` — squaring in `F_{2^m}[x] / (m)`.
    pub fn square_mod(&self, modulus: &Self, irr: &IrreduciblePoly) -> Self {
        let sq = self.mul(self, irr);
        sq.rem(modulus, irr)
    }

    /// Equality (after trimming).
    pub fn eq_poly(&self, other: &Self) -> bool {
        let d1 = self.degree();
        let d2 = other.degree();
        if d1 != d2 {
            return false;
        }
        match d1 {
            None => true,
            Some(d) => (0..=d).all(|i| self.coeff(i) == other.coeff(i)),
        }
    }
}

impl PartialEq for F2mPoly {
    fn eq(&self, other: &Self) -> bool {
        self.eq_poly(other)
    }
}

impl Eq for F2mPoly {}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::binary_ecc::f2m::{F2mElement, IrreduciblePoly};

    fn f4_irr() -> IrreduciblePoly {
        // x² + x + 1 over F_2.
        IrreduciblePoly {
            degree: 2,
            low_terms: vec![0, 1],
        }
    }

    #[test]
    fn add_is_xor() {
        let irr = f4_irr();
        let _ = irr;
        let m = 2;
        let p = F2mPoly::from_coeffs(
            vec![F2mElement::one(m), F2mElement::zero(m), F2mElement::one(m)],
            m,
        );
        let q = F2mPoly::from_coeffs(
            vec![F2mElement::zero(m), F2mElement::one(m), F2mElement::one(m)],
            m,
        );
        let s = p.add(&q);
        // (1 + x²) + (x + x²) = 1 + x
        assert_eq!(s.degree(), Some(1));
        assert_eq!(s.coeff(0), F2mElement::one(m));
        assert_eq!(s.coeff(1), F2mElement::one(m));
    }

    #[test]
    fn mul_degree_adds() {
        let irr = f4_irr();
        let m = 2;
        let p = F2mPoly::from_coeffs(vec![F2mElement::one(m), F2mElement::one(m)], m);
        let q = F2mPoly::from_coeffs(vec![F2mElement::one(m), F2mElement::one(m)], m);
        let pq = p.mul(&q, &irr);
        // (1+x)(1+x) = 1 + x² over char 2.
        assert_eq!(pq.degree(), Some(2));
        assert_eq!(pq.coeff(0), F2mElement::one(m));
        assert_eq!(pq.coeff(1), F2mElement::zero(m));
        assert_eq!(pq.coeff(2), F2mElement::one(m));
    }

    #[test]
    fn divrem_self_is_one_zero() {
        let irr = IrreduciblePoly::deg_8();
        let m = 8;
        let p = F2mPoly::from_coeffs(
            vec![
                F2mElement::one(m),
                F2mElement::zero(m),
                F2mElement::one(m),
                F2mElement::one(m),
            ],
            m,
        );
        let (q, r) = p.divrem(&p, &irr);
        assert!(r.is_zero());
        assert_eq!(q.degree(), Some(0));
        assert_eq!(q.coeff(0), F2mElement::one(m));
    }

    #[test]
    fn divrem_invariant() {
        // self = q·divisor + r,  deg r < deg divisor.
        let irr = IrreduciblePoly::deg_8();
        let m = 8;
        let a = F2mPoly::from_coeffs(
            vec![
                F2mElement::from_biguint(&num_bigint::BigUint::from(0x17u32), m),
                F2mElement::from_biguint(&num_bigint::BigUint::from(0x09u32), m),
                F2mElement::from_biguint(&num_bigint::BigUint::from(0x05u32), m),
                F2mElement::from_biguint(&num_bigint::BigUint::from(0x01u32), m),
            ],
            m,
        );
        let b = F2mPoly::from_coeffs(
            vec![
                F2mElement::from_biguint(&num_bigint::BigUint::from(0x03u32), m),
                F2mElement::from_biguint(&num_bigint::BigUint::from(0x02u32), m),
            ],
            m,
        );
        let (q, r) = a.divrem(&b, &irr);
        let reconstructed = q.mul(&b, &irr).add(&r);
        assert_eq!(reconstructed, a);
        assert!(r.degree().unwrap_or(0) < b.degree().unwrap());
    }

    #[test]
    fn gcd_monic() {
        let irr = IrreduciblePoly::deg_8();
        let m = 8;
        let x = F2mPoly::x(m);
        let one = F2mPoly::one(m);
        // a = (x+1)(x²+1) ,  b = (x+1)(x+α)
        let x_plus_1 = x.add(&one);
        let x_sq_plus_1 = x.mul(&x, &irr).add(&one);
        let a = x_plus_1.mul(&x_sq_plus_1, &irr);
        let alpha = F2mElement::from_biguint(&num_bigint::BigUint::from(0x05u32), m);
        let x_plus_alpha = F2mPoly::from_coeffs(vec![alpha.clone(), F2mElement::one(m)], m);
        let b = x_plus_1.mul(&x_plus_alpha, &irr);
        let g = a.gcd(&b, &irr);
        // Should contain (x+1).  Check that g(1) = 0 — i.e., 1 is a root.
        let one_elt = F2mElement::one(m);
        assert!(g.eval(&one_elt, &irr).is_zero());
        // And monic.
        assert_eq!(g.lead(), F2mElement::one(m));
    }

    #[test]
    fn ext_gcd_bezout() {
        let irr = IrreduciblePoly::deg_8();
        let m = 8;
        let x = F2mPoly::x(m);
        let one = F2mPoly::one(m);
        let a = x.mul(&x, &irr).add(&one); // x² + 1
        let b = x.add(&one); // x + 1
        let (g, s, t) = a.ext_gcd(&b, &irr);
        // s·a + t·b should equal g.
        let lhs = s.mul(&a, &irr).add(&t.mul(&b, &irr));
        assert_eq!(lhs, g);
    }

    #[test]
    fn eval_horner() {
        let irr = IrreduciblePoly::deg_8();
        let m = 8;
        // p(x) = 1 + x + x²
        let p = F2mPoly::from_coeffs(
            vec![F2mElement::one(m), F2mElement::one(m), F2mElement::one(m)],
            m,
        );
        let alpha = F2mElement::from_biguint(&num_bigint::BigUint::from(0x05u32), m);
        let v = p.eval(&alpha, &irr);
        // Expected: 1 + α + α².
        let manual = F2mElement::one(m).add(&alpha).add(&alpha.square(&irr));
        assert_eq!(v, manual);
    }
}
