//! Shared utilities: randomness, encoding, and modular arithmetic helpers.

pub mod encoding;
pub mod random;

pub use encoding::*;
pub use random::*;

use num_bigint::{BigInt, BigUint, Sign};
use num_traits::{One, Zero};

/// Modular exponentiation: `base^exp mod modulus` using square-and-multiply.
/// Works for any size integers; does NOT require `modulus` to be prime.
///
/// Variable-time.  The number of iterations depends on the position of
/// the most-significant set bit of `exp`, and the multiplication is
/// performed conditionally on each bit.  Use [`mod_pow_ct`] when `exp`
/// is a secret value.
pub fn mod_pow(base: &BigUint, exp: &BigUint, modulus: &BigUint) -> BigUint {
    let mut result = BigUint::one();
    let mut b = base % modulus;
    let mut e = exp.clone();
    let zero = BigUint::zero();
    let one = BigUint::one();

    while e > zero {
        if &e & &one == one {
            result = (&result * &b) % modulus;
        }
        b = (&b * &b) % modulus;
        e >>= 1;
    }
    result
}

/// Modular exponentiation via the **Montgomery ladder**.  Processes a
/// fixed number of bits (`exp_bits`) MSB-first; every iteration performs
/// exactly one modular multiplication and one modular squaring,
/// regardless of the bit value.  This closes the coarse-grained
/// "operation count reveals Hamming weight of the exponent" leak that
/// plain square-and-multiply has.
///
/// **Caveats:**
///
/// - The branch that re-binds `(r0, r1)` after each step is a plain
///   Rust `if`.  Both arms assign exactly two values; the algorithmic
///   work is identical.  A sufficiently aggressive compiler may emit a
///   data-dependent jump here, so this is not a hardware-level
///   constant-time guarantee.
/// - The underlying `BigUint` multiplication and modular reduction are
///   *not* constant-time.  Operand magnitudes affect runtime at the
///   limb level, leaking information that a fine-grained timing
///   adversary can exploit.  Truly constant-time exponentiation
///   requires fixed-width, constant-time bignum arithmetic
///   (e.g. `crypto-bigint`'s `BoxedUint` with Montgomery form).
///
/// Pass `exp_bits = modulus.bits()` for RSA private-key operations:
/// the exponent `d` is bounded by the modulus, and using `n.bits()`
/// keeps the iteration count uniform across keys with the same
/// modulus size.
pub fn mod_pow_ct(base: &BigUint, exp: &BigUint, modulus: &BigUint, exp_bits: usize) -> BigUint {
    let mut r0 = BigUint::one();
    let mut r1 = base % modulus;

    for i in (0..exp_bits).rev() {
        let bit = exp.bit(i as u64);

        let prod = (&r0 * &r1) % modulus;
        let r0_sq = (&r0 * &r0) % modulus;
        let r1_sq = (&r1 * &r1) % modulus;

        if bit {
            r0 = prod;
            r1 = r1_sq;
        } else {
            r0 = r0_sq;
            r1 = prod;
        }
    }
    r0
}

/// Modular inverse for a **prime** modulus, via Fermat's little theorem:
/// for prime `p` and `a` coprime to `p`, `a^(p-2) ≡ a⁻¹ (mod p)`.
///
/// Uses [`mod_pow_ct`] under the hood, so it inherits the same
/// "operation count is uniform per bit" property — and the same
/// caveats about underlying limb arithmetic not being constant-time.
///
/// Returns `None` when `a` is zero (mod `p`); otherwise returns the
/// inverse.  The caller is responsible for ensuring `p` is actually
/// prime; passing a composite modulus produces meaningless output.
pub fn mod_inverse_prime_ct(a: &BigUint, p: &BigUint) -> Option<BigUint> {
    if (a % p).is_zero() {
        return None;
    }
    let two = BigUint::from(2u32);
    if p < &two {
        return None;
    }
    let exp = p - &two;
    Some(mod_pow_ct(a, &exp, p, p.bits() as usize))
}

/// Modular inverse via the extended Euclidean algorithm.
/// Returns `Some(x)` such that `a * x ≡ 1 (mod m)`, or `None` if no inverse exists.
/// Works whether or not `m` is prime (unlike Fermat's little theorem).
pub fn mod_inverse(a: &BigUint, m: &BigUint) -> Option<BigUint> {
    if a.is_zero() {
        return None;
    }
    let a_i = BigInt::from_biguint(Sign::Plus, a.clone());
    let m_i = BigInt::from_biguint(Sign::Plus, m.clone());

    let (mut old_r, mut r) = (a_i.clone(), m_i.clone());
    let (mut old_s, mut s) = (BigInt::one(), BigInt::zero());

    while !r.is_zero() {
        let q = &old_r / &r;
        let tmp = old_r - &q * &r;
        old_r = r;
        r = tmp;
        let tmp = old_s - q * &s;
        old_s = s;
        s = tmp;
    }

    // gcd must be 1 for the inverse to exist
    if old_r != BigInt::one() && old_r != BigInt::from(-1i32) {
        return None;
    }

    let result = ((old_s % &m_i) + &m_i) % &m_i;
    result.to_biguint()
}
