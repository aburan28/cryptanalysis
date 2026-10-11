//! Cryptographically-secure random number generation.
//!
//! All entropy is sourced from the OS via `getrandom`/`OsRng`:
//!   - Linux/Android: `getrandom(2)` (or `/dev/urandom` fallback)
//!   - macOS/iOS:     `getentropy(2)` / `SecRandomCopyBytes`
//!   - Windows:       `BCryptGenRandom(BCRYPT_USE_SYSTEM_PREFERRED_RNG)`
//!   - WASM/browser:  `crypto.getRandomValues`
//!
//! `OsRng` is a stateless, blocking CSPRNG and is the convention for
//! generating long-term secret material in Rust cryptographic code.  We
//! deliberately avoid `thread_rng` for secret-material paths: while it is
//! cryptographic, having a single, well-known source makes audits simpler
//! and removes any doubt about reseeding semantics.

use num_bigint::{BigUint, RandBigInt};
use num_traits::{One, Zero};
use rand::rngs::OsRng;
use rand::RngCore;

/// Fill `buf` with cryptographically-random bytes from the OS CSPRNG.
///
/// Panics if the OS RNG is unavailable (e.g., no `/dev/urandom` and
/// `getrandom` syscall fails).  This matches the expectations of every
/// other audited Rust crypto crate — a missing CSPRNG is unrecoverable.
pub fn random_bytes(buf: &mut [u8]) {
    OsRng.fill_bytes(buf);
}

/// Generate a random `BigUint` in the range `[1, max)`.
///
/// Uses rejection sampling on top of `OsRng` so the distribution is uniform
/// — no modular bias.  The output is guaranteed non-zero.
pub fn random_scalar_checked(max: &BigUint) -> Option<BigUint> {
    if max <= &BigUint::one() {
        return None;
    }
    let mut rng = OsRng;
    loop {
        let candidate = rng.gen_biguint_below(max);
        if !candidate.is_zero() {
            return Some(candidate);
        }
    }
}

/// Generate a random `BigUint` in the range `[1, max)`.
///
/// Panics for `max <= 1`; use [`random_scalar_checked`] when invalid bounds are
/// possible at runtime.
pub fn random_scalar(max: &BigUint) -> BigUint {
    random_scalar_checked(max).expect("random_scalar requires max > 1")
}

/// Generate `len` cryptographically-random bytes as a `Vec<u8>`.
pub fn random_bytes_vec(len: usize) -> Vec<u8> {
    let mut buf = vec![0u8; len];
    OsRng.fill_bytes(&mut buf);
    buf
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn random_scalar_checked_rejects_empty_ranges() {
        assert!(random_scalar_checked(&BigUint::zero()).is_none());
        assert!(random_scalar_checked(&BigUint::one()).is_none());
    }
}
