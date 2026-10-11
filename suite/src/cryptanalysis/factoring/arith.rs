//! Number-theoretic helpers shared by every factoring method.
//!
//! - [`is_probable_prime`] — the **Baillie–PSW** test: a strong
//!   Fermat test to base 2 followed by a strong Lucas test with
//!   Selfridge's parameters (method A).  No composite is known to pass
//!   it, it is deterministic (the same answer on every run, unlike the
//!   random-witness Miller–Rabin in [`crate::asymmetric::rsa::is_prime`]),
//!   and it has been verified to have no counterexample below `2⁶⁴`
//!   (Feitsma–Galway).  Above `2⁶⁴` it is a *probable*-prime test, and
//!   the factoring reports say so.
//! - [`perfect_power`] — detect `n = rᵏ`, `k ≥ 2`.
//! - `u64` modular arithmetic ([`mul_mod`], [`pow_mod`], [`inv_mod`],
//!   [`sqrt_mod`] — Tonelli–Shanks) used by the sieves, where every
//!   factor-base prime fits in 32 bits so products fit in 64.
//! - [`primes_up_to`] re-exports the Eratosthenes sieve from
//!   [`crate::cryptanalysis::ecm`].
//!
//! References: R. Baillie and S. Wagstaff, *Lucas pseudoprimes*, Math.
//! Comp. 35 (1980); C. Pomerance, J. Selfridge and S. Wagstaff, *The
//! pseudoprimes to 25·10⁹*, Math. Comp. 35 (1980).

use num_bigint::{BigInt, BigUint, Sign};
use num_integer::Integer;
use num_traits::{One, Signed, ToPrimitive, Zero};

pub use crate::cryptanalysis::ecm::primes_up_to;

/// Small primes used for quick trial division before the BPSW test.
const SMALL_PRIMES: [u64; 25] = [
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97,
];

/// `a · b mod m` without overflow.
#[inline]
pub fn mul_mod(a: u64, b: u64, m: u64) -> u64 {
    ((a as u128 * b as u128) % m as u128) as u64
}

/// `base^exp mod m` by square-and-multiply.
pub fn pow_mod(mut base: u64, mut exp: u64, m: u64) -> u64 {
    if m == 1 {
        return 0;
    }
    let mut r = 1u64;
    base %= m;
    while exp > 0 {
        if exp & 1 == 1 {
            r = mul_mod(r, base, m);
        }
        base = mul_mod(base, base, m);
        exp >>= 1;
    }
    r
}

/// Inverse of `a` modulo `m`, or `None` when `gcd(a, m) ≠ 1`.
pub fn inv_mod(a: u64, m: u64) -> Option<u64> {
    let (mut old_r, mut r) = (a as i128 % m as i128, m as i128);
    let (mut old_s, mut s) = (1i128, 0i128);
    while r != 0 {
        let q = old_r / r;
        (old_r, r) = (r, old_r - q * r);
        (old_s, s) = (s, old_s - q * s);
    }
    if old_r != 1 {
        return None;
    }
    Some(old_s.rem_euclid(m as i128) as u64)
}

/// Legendre symbol `(a / p)` for an odd prime `p`: `1`, `p − 1` (i.e. −1)
/// or `0`, returned as the Euler criterion value.
#[inline]
pub fn legendre(a: u64, p: u64) -> u64 {
    pow_mod(a % p, (p - 1) / 2, p)
}

/// Jacobi symbol `(a / n)` for odd `n`, by the binary reciprocity
/// algorithm (no multiplications; much cheaper than Euler's criterion).
pub fn jacobi_u64(a: u64, n: u64) -> i32 {
    debug_assert!(n % 2 == 1);
    let (mut a, mut n) = (a % n, n);
    let mut t = 1;
    while a != 0 {
        let z = a.trailing_zeros();
        a >>= z;
        if z % 2 == 1 && (n % 8 == 3 || n % 8 == 5) {
            t = -t;
        }
        if a % 4 == 3 && n % 4 == 3 {
            t = -t;
        }
        (a, n) = (n % a, a);
    }
    if n == 1 {
        t
    } else {
        0
    }
}

/// Square root of `a` modulo an odd prime `p` (Tonelli–Shanks), or `None`
/// when `a` is a non-residue.  For `p = 2` returns `a mod 2`.
pub fn sqrt_mod(a: u64, p: u64) -> Option<u64> {
    let a = a % p;
    if p == 2 || a == 0 {
        return Some(a);
    }
    if legendre(a, p) != 1 {
        return None;
    }
    if p % 4 == 3 {
        return Some(pow_mod(a, p.div_ceil(4), p));
    }
    // p − 1 = q · 2^s with q odd.
    let mut q = p - 1;
    let mut s = 0u32;
    while q.is_multiple_of(2) {
        q /= 2;
        s += 1;
    }
    let mut z = 2u64;
    while legendre(z, p) != p - 1 {
        z += 1;
    }
    let mut m = s;
    let mut c = pow_mod(z, q, p);
    let mut t = pow_mod(a, q, p);
    let mut r = pow_mod(a, q.div_ceil(2), p);
    while t != 1 {
        let mut i = 0u32;
        let mut t2 = t;
        while t2 != 1 {
            t2 = mul_mod(t2, t2, p);
            i += 1;
        }
        let b = pow_mod(c, 1u64 << (m - i - 1), p);
        m = i;
        c = mul_mod(b, b, p);
        t = mul_mod(t, c, p);
        r = mul_mod(r, b, p);
    }
    Some(r)
}

/// `gcd` on signed 64-bit integers (non-negative result).
#[inline]
pub fn gcd_i64(a: i64, b: i64) -> u64 {
    let (mut a, mut b) = (a.unsigned_abs(), b.unsigned_abs());
    while b != 0 {
        (a, b) = (b, a % b);
    }
    a
}

/// `x mod p` for a big integer and a word-size modulus.
#[inline]
pub fn big_mod_u64(x: &BigUint, p: u64) -> u64 {
    (x % p).to_u64().unwrap_or(0)
}

/// `x mod p` for a signed big integer, in `[0, p)`.
#[inline]
pub fn bigint_mod_u64(x: &BigInt, p: u64) -> u64 {
    let r = big_mod_u64(x.magnitude(), p);
    if x.sign() == Sign::Minus && r != 0 {
        p - r
    } else {
        r
    }
}

/// Reduce a signed big integer into `[0, n)`.
pub fn bigint_mod(x: &BigInt, n: &BigUint) -> BigUint {
    let r = x.magnitude() % n;
    if x.sign() == Sign::Minus && !r.is_zero() {
        n - r
    } else {
        r
    }
}

/// Jacobi symbol `(a / n)` for odd positive `n`.
pub fn jacobi(a: &BigInt, n: &BigUint) -> i32 {
    debug_assert!(n.is_odd());
    let mut a = bigint_mod(a, n);
    let mut n = n.clone();
    let mut result = 1;
    while !a.is_zero() {
        let tz = a.trailing_zeros().unwrap_or(0);
        if tz > 0 {
            a >>= tz;
            let n8 = (&n % 8u32).to_u32().unwrap_or(0);
            if tz % 2 == 1 && (n8 == 3 || n8 == 5) {
                result = -result;
            }
        }
        std::mem::swap(&mut a, &mut n);
        if (&a % 4u32) == BigUint::from(3u32) && (&n % 4u32) == BigUint::from(3u32) {
            result = -result;
        }
        a %= &n;
    }
    if n.is_one() {
        result
    } else {
        0
    }
}

/// Strong probable-prime (Miller–Rabin) test to one base.
fn strong_probable_prime(n: &BigUint, base: &BigUint) -> bool {
    let one = BigUint::one();
    let nm1 = n - &one;
    let s = nm1.trailing_zeros().unwrap_or(0);
    let d = &nm1 >> s;
    let mut x = base.modpow(&d, n);
    if x.is_one() || x == nm1 {
        return true;
    }
    for _ in 1..s {
        x = &x * &x % n;
        if x == nm1 {
            return true;
        }
        if x.is_one() {
            return false;
        }
    }
    false
}

/// Halve `x` modulo odd `n` (`x / 2 mod n`).
fn half_mod(x: BigUint, n: &BigUint) -> BigUint {
    if x.is_even() {
        x >> 1
    } else {
        (x + n) >> 1
    }
}

/// Strong Lucas probable-prime test with Selfridge parameters: `D` is the
/// first of `5, −7, 9, −11, …` with `(D / n) = −1`, `P = 1`,
/// `Q = (1 − D) / 4`.  `n` must be odd, > 2 and not a perfect square.
fn strong_lucas_probable_prime(n: &BigUint) -> bool {
    let mut d_val: i64 = 5;
    loop {
        let j = jacobi(&BigInt::from(d_val), n);
        if j == -1 {
            break;
        }
        if j == 0 && BigUint::from(d_val.unsigned_abs()) != *n {
            return false;
        }
        d_val = if d_val > 0 { -(d_val + 2) } else { -d_val + 2 };
        if d_val.abs() > 1_000_000 {
            // Only a perfect square can defeat the search; the caller
            // excludes those, so this is unreachable in practice.
            return false;
        }
    }
    let d_big = bigint_mod(&BigInt::from(d_val), n);
    let q_big = bigint_mod(&BigInt::from((1 - d_val) / 4), n);
    // n + 1 = k · 2^s with k odd.
    let np1 = n + 1u32;
    let s = np1.trailing_zeros().unwrap_or(0);
    let k = &np1 >> s;

    // Binary Lucas chain with P = 1: U_1 = 1, V_1 = 1.
    let mut u = BigUint::one();
    let mut v = BigUint::one();
    let mut qk = q_big.clone();
    let bits = k.bits();
    for i in (0..bits - 1).rev() {
        // Doubling: U_2j = U_j V_j, V_2j = V_j² − 2 Q^j.
        u = &u * &v % n;
        let two_qk = (&qk << 1) % n;
        v = (&v * &v + n - two_qk) % n;
        qk = &qk * &qk % n;
        if k.bit(i) {
            // Increment: U_{j+1} = (P U + V)/2, V_{j+1} = (D U + P V)/2.
            let nu = half_mod((&u + &v) % n, n);
            let nv = half_mod((&d_big * &u + &v) % n, n);
            u = nu;
            v = nv;
            qk = &qk * &q_big % n;
        }
    }
    if u.is_zero() || v.is_zero() {
        return true;
    }
    for _ in 1..s {
        let two_qk = (&qk << 1) % n;
        v = (&v * &v + n - two_qk) % n;
        if v.is_zero() {
            return true;
        }
        qk = &qk * &qk % n;
    }
    false
}

/// Baillie–PSW probable-prime test.  Exact (proven) for `n < 2⁶⁴`.
pub fn is_probable_prime(n: &BigUint) -> bool {
    if n < &BigUint::from(2u32) {
        return false;
    }
    for &p in &SMALL_PRIMES {
        if n == &BigUint::from(p) {
            return true;
        }
        if big_mod_u64(n, p) == 0 {
            return false;
        }
    }
    if n < &BigUint::from(97u32 * 97) {
        return true;
    }
    if !strong_probable_prime(n, &BigUint::from(2u32)) {
        return false;
    }
    let r = n.sqrt();
    if &(&r * &r) == n {
        return false;
    }
    strong_lucas_probable_prime(n)
}

/// `is_probable_prime` for a machine word.
pub fn is_prime_u64(n: u64) -> bool {
    is_probable_prime(&BigUint::from(n))
}

/// If `n = rᵏ` for some `k ≥ 2`, return `(r, k)` with the **largest** such
/// `k` (so `r` is not itself a perfect power).  `None` for `n < 4` or
/// when `n` is not a perfect power.
pub fn perfect_power(n: &BigUint) -> Option<(BigUint, u32)> {
    if n < &BigUint::from(4u32) {
        return None;
    }
    let max_k = n.bits() as u32;
    let mut best: Option<(BigUint, u32)> = None;
    for k in 2..=max_k {
        let r = n.nth_root(k);
        if r < BigUint::from(2u32) {
            break;
        }
        if &num_traits::pow(r.clone(), k as usize) == n {
            best = Some((r, k));
        }
    }
    best
}

/// Integer `k`-th root if exact.
pub fn exact_root(n: &BigUint, k: u32) -> Option<BigUint> {
    let r = n.nth_root(k);
    if num_traits::pow(r.clone(), k as usize) == *n {
        Some(r)
    } else {
        None
    }
}

/// Integer square root and whether it is exact.
pub fn isqrt_exact(n: &BigUint) -> (BigUint, bool) {
    let r = n.sqrt();
    let exact = &r * &r == *n;
    (r, exact)
}

/// Extended Euclid on big signed integers: returns `(g, x, y)` with
/// `a·x + b·y = g = gcd(a, b) ≥ 0`.
pub fn ext_gcd(a: &BigInt, b: &BigInt) -> (BigInt, BigInt, BigInt) {
    let (mut old_r, mut r) = (a.clone(), b.clone());
    let (mut old_s, mut s) = (BigInt::one(), BigInt::zero());
    let (mut old_t, mut t) = (BigInt::zero(), BigInt::one());
    while !r.is_zero() {
        let q = old_r.div_floor(&r);
        let nr = &old_r - &q * &r;
        old_r = std::mem::replace(&mut r, nr);
        let ns = &old_s - &q * &s;
        old_s = std::mem::replace(&mut s, ns);
        let nt = &old_t - &q * &t;
        old_t = std::mem::replace(&mut t, nt);
    }
    if old_r.is_negative() {
        (-old_r, -old_s, -old_t)
    } else {
        (old_r, old_s, old_t)
    }
}

/// Number of decimal digits of `n` (`n = 0` has one digit).
pub fn decimal_digits(n: &BigUint) -> usize {
    n.to_str_radix(10).len()
}

/// Wall-clock seconds since `t`.
#[inline]
pub(crate) fn secs(t: std::time::Instant) -> f64 {
    t.elapsed().as_secs_f64()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bpsw_agrees_with_sieve_below_100000() {
        let primes = primes_up_to(100_000);
        let mut is_p = vec![false; 100_001];
        for &p in &primes {
            is_p[p as usize] = true;
        }
        for n in 0..=100_000u64 {
            assert_eq!(is_prime_u64(n), is_p[n as usize], "n = {n}");
        }
    }

    #[test]
    fn bpsw_rejects_pseudoprimes() {
        // Strong pseudoprimes to base 2, Carmichael numbers and a strong
        // Lucas pseudoprime: each fools one half of the test, none both.
        for c in [
            2047u64,
            3277,
            4033,
            4681,
            8321,
            561,
            1105,
            1729,
            5459,
            5777,
            10877,
            3215031751,
            3825123056546413051,
        ] {
            assert!(!is_prime_u64(c), "{c} is composite");
        }
        let m127 = (BigUint::one() << 127) - 1u32;
        assert!(is_probable_prime(&m127));
        let m128 = (BigUint::one() << 128) - 1u32;
        assert!(!is_probable_prime(&m128));
    }

    #[test]
    fn sqrt_mod_roundtrip() {
        for &p in &[3u64, 5, 13, 17, 97, 65537, 1_000_000_007, 4_294_967_291] {
            for a in 1..50u64 {
                if let Some(r) = sqrt_mod(a, p) {
                    assert_eq!(mul_mod(r, r, p), a % p);
                }
            }
        }
    }

    #[test]
    fn jacobi_u64_matches_euler() {
        for &p in &[3u64, 5, 7, 1_000_003, 4_294_967_291] {
            for a in 0..200u64 {
                let e = legendre(a, p);
                let want = if e == 0 {
                    0
                } else if e == 1 {
                    1
                } else {
                    -1
                };
                assert_eq!(jacobi_u64(a, p), want, "({a}/{p})");
            }
        }
    }

    #[test]
    fn perfect_powers() {
        let n = num_traits::pow(BigUint::from(12345u32), 6);
        assert_eq!(perfect_power(&n), Some((BigUint::from(12345u32), 6)));
        assert_eq!(perfect_power(&BigUint::from(1000001u32)), None);
        assert_eq!(
            perfect_power(&BigUint::from(1024u32)),
            Some((BigUint::from(2u32), 10))
        );
    }

    #[test]
    fn jacobi_matches_euler() {
        let p = BigUint::from(1_000_003u64);
        for a in -30i64..30 {
            let j = jacobi(&BigInt::from(a), &p);
            let e = legendre(a.rem_euclid(1_000_003) as u64, 1_000_003);
            let want = if e == 0 {
                0
            } else if e == 1 {
                1
            } else {
                -1
            };
            assert_eq!(j, want, "a = {a}");
        }
    }
}
