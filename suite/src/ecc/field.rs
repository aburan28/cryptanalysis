//! Finite field arithmetic over F_p (prime field).
//!
//! Every `FieldElement` stores its value reduced mod p and carries p along.
//! The modulus p must be prime for `inv()` to work correctly (Fermat's
//! little theorem: a^(p-2) ≡ a^(-1) mod p).

use crate::utils::mod_pow_ct;
use num_bigint::BigUint;
use num_traits::{One, Zero};
use std::fmt;

#[derive(Clone, Debug)]
pub struct FieldElement {
    /// Value in [0, p)
    pub value: BigUint,
    /// The field prime p
    pub modulus: BigUint,
}

impl FieldElement {
    /// Construct a new field element, reducing `value` mod `modulus`.
    pub fn new(value: BigUint, modulus: BigUint) -> Self {
        let value = value % &modulus;
        FieldElement { value, modulus }
    }

    pub fn zero(modulus: BigUint) -> Self {
        FieldElement {
            value: BigUint::zero(),
            modulus,
        }
    }

    pub fn one(modulus: BigUint) -> Self {
        FieldElement {
            value: BigUint::one(),
            modulus,
        }
    }

    pub fn is_zero(&self) -> bool {
        self.value.is_zero()
    }

    // ── Arithmetic ────────────────────────────────────────────────────────────

    pub fn add(&self, rhs: &Self) -> Self {
        Self::new(&self.value + &rhs.value, self.modulus.clone())
    }

    pub fn sub(&self, rhs: &Self) -> Self {
        // Always compute (a + p - b) mod p instead of branching on
        // (a >= b).  Algebraically the same as (a - b) mod p, but
        // without the data-dependent comparison that the branch-and-
        // negate variant uses.  The underlying `BigUint` add/sub still
        // leak via limb count — see SECURITY.md.
        let v = (&self.value + &self.modulus - &rhs.value) % &self.modulus;
        FieldElement {
            value: v,
            modulus: self.modulus.clone(),
        }
    }

    pub fn mul(&self, rhs: &Self) -> Self {
        Self::new(&self.value * &rhs.value, self.modulus.clone())
    }

    /// Additive inverse: -a mod p.  Always computes (p - a) mod p
    /// instead of branching on `a == 0`.  For `a = 0` the result is
    /// `p mod p = 0`; for `a != 0` it is `p - a` (unreduced, since
    /// `0 < p - a < p`).
    pub fn neg(&self) -> Self {
        let v = (&self.modulus - &self.value) % &self.modulus;
        FieldElement {
            value: v,
            modulus: self.modulus.clone(),
        }
    }

    /// Modular exponentiation via the Montgomery-ladder
    /// [`mod_pow_ct`].  Iteration count is fixed at `modulus.bits()`,
    /// and every step performs one multiplication and one squaring
    /// regardless of the bit value.  Caveat: the underlying
    /// `BigUint` arithmetic is still not constant-time at the limb
    /// level — see SECURITY.md.
    pub fn pow(&self, exp: &BigUint) -> Self {
        let bits = self.modulus.bits() as usize;
        let value = mod_pow_ct(&self.value, exp, &self.modulus, bits);
        FieldElement {
            value,
            modulus: self.modulus.clone(),
        }
    }

    /// Multiplicative inverse via Fermat's little theorem: a^(p-2) mod p.
    /// Returns `None` if `self` is zero.  Uses the laddered `pow`.
    pub fn inv(&self) -> Option<Self> {
        if self.is_zero() {
            return None;
        }
        let exp = &self.modulus - BigUint::from(2u32);
        Some(self.pow(&exp))
    }
}

impl PartialEq for FieldElement {
    fn eq(&self, other: &Self) -> bool {
        self.value == other.value
    }
}

impl fmt::Display for FieldElement {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.value)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fe(v: u64, p: u64) -> FieldElement {
        FieldElement::new(BigUint::from(v), BigUint::from(p))
    }

    #[test]
    fn add_mod() {
        // In F_7: 5 + 4 = 9 ≡ 2
        assert_eq!(fe(5, 7).add(&fe(4, 7)), fe(2, 7));
    }

    #[test]
    fn sub_wrap() {
        // In F_7: 2 - 5 = -3 ≡ 4
        assert_eq!(fe(2, 7).sub(&fe(5, 7)), fe(4, 7));
    }

    #[test]
    fn mul_mod() {
        // In F_7: 3 * 5 = 15 ≡ 1
        assert_eq!(fe(3, 7).mul(&fe(5, 7)), fe(1, 7));
    }

    #[test]
    fn inv_fermat() {
        // In F_7: 3^(-1) = 5 because 3*5=15≡1 mod 7
        let inv = fe(3, 7).inv().unwrap();
        assert_eq!(inv, fe(5, 7));
    }

    #[test]
    fn pow_identity() {
        // In F_7: 2^6 ≡ 1 (Fermat's little theorem)
        let r = fe(2, 7).pow(&BigUint::from(6u32));
        assert_eq!(r, fe(1, 7));
    }
}
