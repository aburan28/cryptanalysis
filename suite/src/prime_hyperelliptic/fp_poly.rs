//! **Polynomial ring `F_p[x]`** — odd-characteristic analogue of
//! [`crate::binary_ecc::poly_f2m::F2mPoly`].
//!
//! Coefficients are stored as plain `BigUint`'s reduced mod `p`.
//! Each polynomial carries `p` so individual operations don't take
//! it as a parameter (unlike the binary version, since prime-field
//! arithmetic is much simpler — no irreducible polynomial to thread).

use num_bigint::BigUint;
use num_traits::{One, Zero};

/// A polynomial `Σ c_i · x^i` with coefficients in `F_p`.
#[derive(Clone, Debug)]
pub struct FpPoly {
    pub p: BigUint,
    /// `coeffs[i]` is the coefficient of `x^i`, reduced mod `p`.
    pub coeffs: Vec<BigUint>,
}

impl FpPoly {
    /// Zero polynomial.
    pub fn zero(p: BigUint) -> Self {
        Self {
            p,
            coeffs: Vec::new(),
        }
    }

    /// Constant `1`.
    pub fn one(p: BigUint) -> Self {
        Self {
            p,
            coeffs: vec![BigUint::one()],
        }
    }

    /// `x`.
    pub fn x(p: BigUint) -> Self {
        Self {
            p,
            coeffs: vec![BigUint::zero(), BigUint::one()],
        }
    }

    /// Constant polynomial `c`.
    pub fn constant(c: BigUint, p: BigUint) -> Self {
        let c = c % &p;
        if c.is_zero() {
            Self::zero(p)
        } else {
            Self { p, coeffs: vec![c] }
        }
    }

    /// Build from coefficient slice (lowest-degree first).
    pub fn from_coeffs(coeffs: Vec<BigUint>, p: BigUint) -> Self {
        let coeffs: Vec<BigUint> = coeffs.into_iter().map(|c| c % &p).collect();
        let mut q = Self { p, coeffs };
        q.trim();
        q
    }

    pub fn trim(&mut self) {
        while let Some(last) = self.coeffs.last() {
            if last.is_zero() {
                self.coeffs.pop();
            } else {
                break;
            }
        }
    }

    pub fn is_zero(&self) -> bool {
        self.coeffs.iter().all(|c| c.is_zero())
    }

    pub fn degree(&self) -> Option<usize> {
        for (i, c) in self.coeffs.iter().enumerate().rev() {
            if !c.is_zero() {
                return Some(i);
            }
        }
        None
    }

    pub fn lead(&self) -> BigUint {
        match self.degree() {
            Some(d) => self.coeffs[d].clone(),
            None => BigUint::zero(),
        }
    }

    pub fn coeff(&self, i: usize) -> BigUint {
        self.coeffs.get(i).cloned().unwrap_or_else(BigUint::zero)
    }

    pub fn add(&self, other: &Self) -> Self {
        debug_assert_eq!(self.p, other.p);
        let n = self.coeffs.len().max(other.coeffs.len());
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push((self.coeff(i) + other.coeff(i)) % &self.p);
        }
        let mut q = Self {
            p: self.p.clone(),
            coeffs: out,
        };
        q.trim();
        q
    }

    pub fn sub(&self, other: &Self) -> Self {
        debug_assert_eq!(self.p, other.p);
        let n = self.coeffs.len().max(other.coeffs.len());
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            let lhs = self.coeff(i);
            let rhs = other.coeff(i);
            let v = (&lhs + &self.p - rhs) % &self.p;
            out.push(v);
        }
        let mut q = Self {
            p: self.p.clone(),
            coeffs: out,
        };
        q.trim();
        q
    }

    pub fn neg(&self) -> Self {
        let coeffs = self
            .coeffs
            .iter()
            .map(|c| {
                if c.is_zero() {
                    BigUint::zero()
                } else {
                    (&self.p - c) % &self.p
                }
            })
            .collect();
        let mut q = Self {
            p: self.p.clone(),
            coeffs,
        };
        q.trim();
        q
    }

    pub fn mul(&self, other: &Self) -> Self {
        if self.is_zero() || other.is_zero() {
            return Self::zero(self.p.clone());
        }
        let d1 = self.degree().unwrap();
        let d2 = other.degree().unwrap();
        let mut out = vec![BigUint::zero(); d1 + d2 + 1];
        for i in 0..=d1 {
            if self.coeffs[i].is_zero() {
                continue;
            }
            for j in 0..=d2 {
                if other.coeffs[j].is_zero() {
                    continue;
                }
                let prod = (&self.coeffs[i] * &other.coeffs[j]) % &self.p;
                out[i + j] = (&out[i + j] + prod) % &self.p;
            }
        }
        let mut q = Self {
            p: self.p.clone(),
            coeffs: out,
        };
        q.trim();
        q
    }

    pub fn scalar_mul(&self, s: &BigUint) -> Self {
        let s = s % &self.p;
        if s.is_zero() {
            return Self::zero(self.p.clone());
        }
        let coeffs = self.coeffs.iter().map(|c| (c * &s) % &self.p).collect();
        Self {
            p: self.p.clone(),
            coeffs,
        }
    }

    /// Divide by leading coefficient.  Panics on zero.
    pub fn monic(&self) -> Self {
        let lead = self.lead();
        assert!(!lead.is_zero(), "monic of zero polynomial");
        let inv = fp_inv(&lead, &self.p).expect("non-zero lead");
        self.scalar_mul(&inv)
    }

    /// Polynomial long division: returns `(q, r)` with
    /// `self = q · divisor + r` and `deg r < deg divisor`.
    pub fn divrem(&self, divisor: &Self) -> (Self, Self) {
        assert!(!divisor.is_zero(), "division by zero polynomial");
        let p = self.p.clone();
        let d_deg = divisor.degree().unwrap();
        let d_lead_inv = fp_inv(&divisor.lead(), &p).expect("non-zero divisor lead");
        let mut r = self.clone();
        let mut q = Self::zero(p.clone());
        while let Some(r_deg) = r.degree() {
            if r_deg < d_deg {
                break;
            }
            let coef = (&r.coeffs[r_deg] * &d_lead_inv) % &p;
            let shift = r_deg - d_deg;
            if q.coeffs.len() <= shift {
                q.coeffs.resize(shift + 1, BigUint::zero());
            }
            q.coeffs[shift] = (&q.coeffs[shift] + &coef) % &p;
            // r -= coef · x^shift · divisor
            let mut sub_coeffs = vec![BigUint::zero(); d_deg + 1 + shift];
            for (i, dc) in divisor.coeffs.iter().enumerate() {
                if dc.is_zero() {
                    continue;
                }
                sub_coeffs[i + shift] = (&coef * dc) % &p;
            }
            let sub = Self {
                p: p.clone(),
                coeffs: sub_coeffs,
            };
            r = r.sub(&sub);
            r.trim();
        }
        q.trim();
        (q, r)
    }

    pub fn rem(&self, divisor: &Self) -> Self {
        self.divrem(divisor).1
    }

    /// Euclidean GCD, returned monic.
    pub fn gcd(&self, other: &Self) -> Self {
        let mut a = self.clone();
        let mut b = other.clone();
        while !b.is_zero() {
            let r = a.divrem(&b).1;
            a = b;
            b = r;
        }
        if a.is_zero() {
            return a;
        }
        a.monic()
    }

    /// Extended GCD: returns `(g, s, t)` with `s·self + t·other = g`,
    /// `g` monic.
    pub fn ext_gcd(&self, other: &Self) -> (Self, Self, Self) {
        let p = self.p.clone();
        let mut old_r = self.clone();
        let mut r = other.clone();
        let mut old_s = Self::one(p.clone());
        let mut s = Self::zero(p.clone());
        let mut old_t = Self::zero(p.clone());
        let mut t = Self::one(p.clone());
        while !r.is_zero() {
            let q = old_r.divrem(&r).0;
            let new_r = old_r.sub(&q.mul(&r));
            old_r = r;
            r = new_r;
            let new_s = old_s.sub(&q.mul(&s));
            old_s = s;
            s = new_s;
            let new_t = old_t.sub(&q.mul(&t));
            old_t = t;
            t = new_t;
        }
        if old_r.is_zero() {
            return (old_r, old_s, old_t);
        }
        let lead_inv = fp_inv(&old_r.lead(), &p).expect("non-zero lead");
        (
            old_r.scalar_mul(&lead_inv),
            old_s.scalar_mul(&lead_inv),
            old_t.scalar_mul(&lead_inv),
        )
    }

    /// Evaluate `self(x_val) ∈ F_p` via Horner's rule.
    pub fn eval(&self, x_val: &BigUint) -> BigUint {
        let mut acc = BigUint::zero();
        for c in self.coeffs.iter().rev() {
            acc = (&acc * x_val + c) % &self.p;
        }
        acc
    }

    /// Equality (canonical after trim).
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

impl PartialEq for FpPoly {
    fn eq(&self, other: &Self) -> bool {
        self.eq_poly(other)
    }
}

impl Eq for FpPoly {}

/// Modular inverse `a^{-1} mod p` via Fermat's little theorem.
/// Returns `None` for `a ≡ 0 (mod p)`.
pub fn fp_inv(a: &BigUint, p: &BigUint) -> Option<BigUint> {
    let a = a % p;
    if a.is_zero() {
        return None;
    }
    let exp = p - BigUint::from(2u32);
    Some(a.modpow(&exp, p))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn p7() -> BigUint {
        BigUint::from(7u32)
    }

    #[test]
    fn divrem_invariant_small_prime() {
        let p = p7();
        let a = FpPoly::from_coeffs(
            vec![
                BigUint::from(3u32),
                BigUint::from(1u32),
                BigUint::from(2u32),
                BigUint::from(1u32),
            ],
            p.clone(),
        );
        let b = FpPoly::from_coeffs(vec![BigUint::from(2u32), BigUint::from(1u32)], p);
        let (q, r) = a.divrem(&b);
        let reconstructed = q.mul(&b).add(&r);
        assert_eq!(reconstructed, a);
        assert!(r.degree().unwrap_or(0) < b.degree().unwrap());
    }

    #[test]
    fn ext_gcd_bezout() {
        let p = p7();
        // a = x² + 1, b = x + 1
        let a = FpPoly::from_coeffs(
            vec![BigUint::from(1u32), BigUint::zero(), BigUint::from(1u32)],
            p.clone(),
        );
        let b = FpPoly::from_coeffs(vec![BigUint::from(1u32), BigUint::from(1u32)], p);
        let (g, s, t) = a.ext_gcd(&b);
        let lhs = s.mul(&a).add(&t.mul(&b));
        assert_eq!(lhs, g);
    }

    #[test]
    fn eval_horner_mod_p() {
        let p = BigUint::from(11u32);
        // p(x) = 2 + 3x + x²; at x = 5: 2 + 15 + 25 = 42, mod 11 = 9.
        let f = FpPoly::from_coeffs(
            vec![
                BigUint::from(2u32),
                BigUint::from(3u32),
                BigUint::from(1u32),
            ],
            p,
        );
        assert_eq!(f.eval(&BigUint::from(5u32)), BigUint::from(9u32));
    }

    #[test]
    fn monic_makes_leading_one() {
        let p = BigUint::from(13u32);
        let f = FpPoly::from_coeffs(vec![BigUint::from(4u32), BigUint::from(7u32)], p.clone());
        let m = f.monic();
        assert_eq!(m.lead(), BigUint::one());
    }

    #[test]
    fn fp_inv_roundtrip() {
        let p = BigUint::from(101u32);
        for a in 1u64..101 {
            let av = BigUint::from(a);
            let inv = fp_inv(&av, &p).unwrap();
            assert_eq!((&av * &inv) % &p, BigUint::one());
        }
    }
}
