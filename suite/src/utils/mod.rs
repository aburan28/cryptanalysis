//! Shared utilities: randomness, encoding, and modular arithmetic helpers.

pub mod encoding;
pub mod random;

pub use encoding::*;
pub use random::*;

use num_bigint::{BigInt, BigUint, Sign};
use num_traits::{One, ToPrimitive, Zero};

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
///
/// The inverse returned is the representative in `[0, m)`, and `a` may
/// be any size.  When `2 ≤ m < 2⁶⁴` the recurrence runs on machine
/// words (`mod_inverse_u64`) rather than on heap-allocated `BigInt`s:
/// the inverse is unique, so the answer is the same, and the
/// cryptanalysis walks that invert once per group operation over a
/// word-sized field otherwise spend half their time allocating here.
/// `m = 0` and `m = 1` keep the big-integer path and its behaviour.
///
/// Variable-time on either path: the number of division steps depends
/// on `a`.  Use [`mod_inverse_prime_ct`] for a secret `a` mod a prime.
pub fn mod_inverse(a: &BigUint, m: &BigUint) -> Option<BigUint> {
    if a.is_zero() {
        return None;
    }
    if let Some(m_word) = m.to_u64().filter(|&m_word| m_word >= 2) {
        // Only the residue of `a` matters; reduce a wide `a` once in
        // big-integer arithmetic, which leaves a value below `m`.
        let a_word = match a.to_u64() {
            Some(a_word) => a_word % m_word,
            None => (a % m).to_u64().expect("a mod m is below a one-word m"),
        };
        return mod_inverse_u64(a_word, m_word).map(BigUint::from);
    }
    mod_inverse_bigint(a, m)
}

/// The extended Euclidean algorithm on `BigInt`s: [`mod_inverse`] for
/// a nonzero `a` and a modulus that does not fit the word path.  Kept
/// whole, rather than folded into the caller, so the tests can hold the
/// word path to it on every input.
fn mod_inverse_bigint(a: &BigUint, m: &BigUint) -> Option<BigUint> {
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

/// Modular inverse of a word modulo a word, by the extended Euclidean
/// algorithm: `Some(x)` with `a·x ≡ 1 (mod m)` and `x ∈ [0, m)`, or
/// `None` when `gcd(a, m) ≠ 1` (in particular when `a ≡ 0`).  `a` may
/// exceed `m`.  Requires `m ≥ 2`: [`mod_inverse`] routes smaller moduli
/// to the big-integer path, whose conventions for them are its own.
///
/// Starting from `m = 0·a + 1·m` and `a = 1·a + 0·m`, the Bézout
/// coefficient of `a` alternates in sign from one remainder to the next
/// and its magnitude never exceeds `m`.  So the recurrence
/// `t_{k+1} = t_{k−1} − q_k·t_k` is run on magnitudes, where it only
/// adds, with the sign read off the parity of the step count at the end.
/// Every quotient is then one hardware 64-bit division; the `i128` form
/// of the same loop pays a software 128-bit divide for each.
///
/// Variable-time, like [`mod_inverse`].
pub(crate) fn mod_inverse_u64(a: u64, m: u64) -> Option<u64> {
    debug_assert!(m >= 2, "mod_inverse_u64 needs a modulus of at least 2");
    // (r0, r1) are consecutive remainders and (s0, s1) the magnitudes of
    // their coefficients of `a`; `odd` is the parity of the steps taken,
    // which is the sign of the coefficient in s0 (positive when odd).
    let (mut r0, mut r1) = (m, a % m);
    let (mut s0, mut s1) = (0u64, 1u64);
    let mut odd = false;
    while r1 != 0 {
        let q = r0 / r1;
        (r0, r1) = (r1, r0 % r1);
        // |t_{k+1}| = |t_{k−1}| + q·|t_k| ≤ m / gcd: no overflow.
        (s0, s1) = (s1, s0 + q * s1);
        odd = !odd;
    }
    if r0 != 1 {
        return None;
    }
    // gcd = 1 forces at least one step, so s0 ≥ 1, and s0 < s1 = m.
    Some(if odd { s0 } else { m - s0 })
}

#[cfg(test)]
mod tests {
    use super::*;
    use num_bigint::RandBigInt;
    use num_integer::Integer;
    use rand::rngs::StdRng;
    use rand::{Rng, SeedableRng};

    /// What the word path must return: the big-integer recurrence, which
    /// was `mod_inverse` for every modulus before the word path existed,
    /// with its `a = 0` guard.
    fn reference(a: &BigUint, m: &BigUint) -> Option<BigUint> {
        if a.is_zero() {
            None
        } else {
            mod_inverse_bigint(a, m)
        }
    }

    fn check(a: &BigUint, m: &BigUint) {
        let got = mod_inverse(a, m);
        assert_eq!(got, reference(a, m), "a = {a}, m = {m}");
        if let Some(x) = &got {
            assert!(x < m);
            assert!(((a * x) % m).is_one());
        }
    }

    /// Moduli at the edges of the word path: the smallest, even and
    /// composite ones, powers of two, and the largest word values.
    const EDGE_MODULI: [u64; 14] = [
        2,
        3,
        4,
        6,
        12,
        1 << 31,
        (1 << 32) - 5,
        1 << 32,
        (1 << 32) + 15,
        33_750_391,
        1 << 63,
        u64::MAX - 58, // 2⁶⁴ − 59, the largest prime below 2⁶⁴
        u64::MAX - 1,
        u64::MAX, // 3·5·17·257·641·65537·6700417
    ];

    #[test]
    fn mod_inverse_word_path_matches_bigint_path_at_the_edges() {
        for &m in &EDGE_MODULI {
            let m_big = BigUint::from(m);
            let mut values = vec![0, 1, 2, 3, m / 2, m - 2, m - 1, m, u64::MAX, u64::MAX - 1];
            values.extend(m.checked_add(1));
            values.extend(m.checked_mul(2));
            values.extend(m.checked_mul(3).and_then(|v| v.checked_add(1)));
            for a in values {
                check(&BigUint::from(a), &m_big);
            }
            // `a` wider than a word, including exact multiples of `m`.
            let wide = BigUint::one() << 64u32;
            check(&wide, &m_big);
            check(&(&wide + 1u32), &m_big);
            check(&(&m_big << 70u32), &m_big);
            check(&((&m_big << 70u32) + 1u32), &m_big);
            check(&((&m_big << 70u32) + &m_big - 1u32), &m_big);
        }
    }

    #[test]
    fn mod_inverse_word_path_matches_bigint_path_on_random_inputs() {
        let mut rng = StdRng::seed_from_u64(0x6d6f_6469_6e76);
        for bits in 2..=64u32 {
            for _ in 0..200 {
                // A modulus of exactly `bits` bits, odd or even.
                let top = 1u64 << (bits - 1);
                let m = top | (rng.gen::<u64>() & (top - 1));
                let m_big = BigUint::from(m);
                check(&BigUint::from(rng.gen_range(0..m)), &m_big);
                check(&BigUint::from(rng.gen::<u64>()), &m_big);
                check(&rng.gen_biguint(64 + u64::from(bits)), &m_big);
                // Shared factors: a multiple of a factor of `m`'s.
                let g = m.gcd(&rng.gen_range(1..=m));
                check(&BigUint::from(g * rng.gen_range(1..=m / g)), &m_big);
                // The word routine itself, on an unreduced word `a`.
                let a = rng.gen::<u64>();
                assert_eq!(
                    mod_inverse_u64(a, m).map(BigUint::from),
                    reference(&BigUint::from(a), &m_big),
                    "a = {a}, m = {m}"
                );
            }
        }
    }

    /// `m = 0` and `m = 1` stay on the big-integer path, with its
    /// conventions: `a = 0` has no inverse modulo anything, every other
    /// `a` has the inverse `0` modulo 1, and modulo 0 only `a = 1` passes
    /// the gcd test (and then divides by zero, pinned below).
    #[test]
    fn mod_inverse_small_moduli_keep_their_behaviour() {
        let zero = BigUint::zero();
        let one = BigUint::one();
        assert_eq!(mod_inverse(&zero, &one), None);
        assert_eq!(mod_inverse(&zero, &zero), None);
        for a in [1u64, 2, 7, u64::MAX] {
            assert_eq!(mod_inverse(&BigUint::from(a), &one), Some(BigUint::zero()));
        }
        let wide = BigUint::one() << 80u32;
        assert_eq!(mod_inverse(&wide, &one), Some(BigUint::zero()));
        for a in [2u64, 7, u64::MAX] {
            assert_eq!(mod_inverse(&BigUint::from(a), &zero), None);
        }
        assert_eq!(mod_inverse(&wide, &zero), None);
    }

    #[test]
    #[should_panic]
    fn mod_inverse_of_one_mod_zero_still_divides_by_zero() {
        let _ = mod_inverse(&BigUint::one(), &BigUint::zero());
    }

    /// Above a word the big-integer path is the only one; check that its
    /// answers are still inverses in `[0, m)` next to the word path's.
    #[test]
    fn mod_inverse_wide_moduli_return_normalised_inverses() {
        let mut rng = StdRng::seed_from_u64(0x7769_6465);
        for bits in [65u64, 96, 128, 255] {
            for _ in 0..50 {
                let m = rng.gen_biguint(bits) | (BigUint::one() << (bits - 1));
                check(&rng.gen_biguint(bits + 7), &m);
                check(&(&m + 1u32), &m);
                check(&(&m * 3u32), &m);
            }
        }
    }

    /// Consecutive Fibonacci numbers take the most division steps for
    /// their size, every quotient 1, and drive the coefficient magnitudes
    /// up to the modulus: the widest intermediate values the word
    /// recurrence adds, up to `F₉₃ < 2⁶⁴`.
    #[test]
    fn mod_inverse_word_path_on_fibonacci_pairs() {
        let (mut f0, mut f1) = (1u64, 2u64);
        while let Some(f2) = f0.checked_add(f1) {
            for (a, m) in [(f0, f1), (f1, f2), (f0, f2), (f2 - 1, f2), (f1, u64::MAX)] {
                check(&BigUint::from(a), &BigUint::from(m));
                check(&BigUint::from(m - a), &BigUint::from(m));
            }
            (f0, f1) = (f1, f2);
        }
    }
}
