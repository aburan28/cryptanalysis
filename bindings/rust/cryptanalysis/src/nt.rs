//! Number-theory helpers exported by the library.

use cryptanalysis_sys as sys;

/// Deterministic primality test for 64-bit integers.
///
/// ```
/// assert!(cryptanalysis::is_prime(1_000_003));
/// assert!(!cryptanalysis::is_prime(1_000_002));
/// ```
pub fn is_prime(n: u64) -> bool {
    // SAFETY: pure function of its argument.
    unsafe { sys::ca_ffi_is_prime(n) != 0 }
}

/// The smallest prime strictly greater than `n`.
///
/// ```
/// assert_eq!(cryptanalysis::next_prime(1_000_003), 1_000_033);
/// ```
pub fn next_prime(n: u64) -> u64 {
    // SAFETY: pure function of its argument.
    unsafe { sys::ca_ffi_next_prime(n) }
}

/// The smallest primitive root modulo the prime `p`.
///
/// ```
/// assert_eq!(cryptanalysis::primitive_root(1_000_003), 2);
/// ```
pub fn primitive_root(p: u64) -> u64 {
    // SAFETY: pure function of its argument.
    unsafe { sys::ca_ffi_primitive_root(p) }
}

/// `b^e mod m`.
///
/// ```
/// assert_eq!(cryptanalysis::powmod(2, 10, 1000), 24);
/// ```
pub fn powmod(b: u64, e: u64, m: u64) -> u64 {
    // SAFETY: pure function of its arguments.
    unsafe { sys::ca_ffi_powmod(b, e, m) }
}

/// `a^-1 mod m`, or 0 when `gcd(a, m) != 1`.
///
/// ```
/// let inv = cryptanalysis::invmod(3, 1_000_003);
/// assert_eq!(cryptanalysis::powmod(3, 1, 1_000_003) * inv % 1_000_003, 1);
/// ```
pub fn invmod(a: u64, m: u64) -> u64 {
    // SAFETY: pure function of its arguments.
    unsafe { sys::ca_ffi_invmod(a, m) }
}

/// Factor `n` into `(prime, exponent)` pairs in increasing prime order.
///
/// Returns an empty vector for `n <= 1`.
///
/// ```
/// assert_eq!(cryptanalysis::factorize(1_000_002), vec![(2, 1), (3, 1), (166_667, 1)]);
/// ```
pub fn factorize(n: u64) -> Vec<(u64, u32)> {
    // A 64-bit integer has at most 15 distinct prime factors.
    const CAP: usize = 16;
    let mut primes = [0u64; CAP];
    let mut exps = [0u32; CAP];
    // SAFETY: both buffers hold CAP entries and CAP is passed as the cap.
    let count =
        unsafe { sys::ca_ffi_factorize(n, primes.as_mut_ptr(), exps.as_mut_ptr(), CAP as u32) }
            as usize;
    primes
        .iter()
        .zip(exps.iter())
        .take(count.min(CAP))
        .map(|(&p, &e)| (p, e))
        .collect()
}
