//! Paillier — partially homomorphic public-key encryption (additive).
//!
//! Pascal Paillier, "Public-Key Cryptosystems Based on Composite
//! Degree Residuosity Classes," EUROCRYPT 1999.
//!
//! Paillier is a probabilistic public-key scheme over `Z_{n²}` whose
//! security reduces to the Decisional Composite Residuosity
//! Assumption (DCRA), which in turn relies on the hardness of
//! factoring `n = p · q` (the same hardness assumption as RSA).
//!
//! # Why additive HE matters
//!
//! Paillier supports two homomorphic operations:
//!
//! - **Ciphertext addition.**  `enc(m₁) · enc(m₂) mod n²  =  enc(m₁ + m₂ mod n)`.
//!   Multiplying ciphertexts adds the plaintexts.
//! - **Scalar multiplication by a public constant.**
//!   `enc(m)^k mod n²  =  enc(k · m mod n)`.
//!   Raising a ciphertext to a known power multiplies the plaintext.
//!
//! From those two, you build:
//!
//! - **Encrypted aggregation** — sum encrypted balances / votes /
//!   sensor readings without ever decrypting individual contributions.
//! - **Sealed-bid auctions** — combine encrypted bids without
//!   learning losers' values.
//! - **Federated-learning gradient aggregation** — aggregate
//!   encrypted model updates from N clients in a single ciphertext
//!   the server can decrypt only if every client participated.
//! - **Threshold tally with verifiable end-state** — the recipient
//!   sees only the sum, never any individual ciphertext's plaintext.
//!
//! Paillier does **not** support ciphertext × ciphertext
//! multiplication (that would be fully homomorphic encryption).
//! Anyone needing arbitrary computation on ciphertexts should reach
//! for an audited FHE library — see [Module-level scope note] below.
//!
//! # Module-level scope note
//!
//! This crate implements **only Paillier** from the homomorphic-
//! encryption family.  Fully homomorphic schemes (BFV, CKKS, TFHE)
//! are deliberately out of scope — each is 10–25× the implementation
//! cost (NTT-based ring-LWE, modulus switching, bootstrapping,
//! noise-budget tracking) and requires a level of testing that an
//! educational from-scratch library cannot deliver responsibly.
//! For FHE, use [Microsoft SEAL](https://github.com/microsoft/SEAL)
//! or [OpenFHE](https://www.openfhe.org/) — both audited, both with
//! published security parameters from HomomorphicEncryption.org.
//!
//! # Security properties
//!
//! - **IND-CPA secure under DCRA** — provided every encryption uses a
//!   fresh random `r ∈ Z_n*`.  Reusing `r` across two encryptions
//!   leaks `m₁ ⊕ m₂` (and is a bug as severe as ECDSA k-reuse).
//! - **Malleable by design.**  Multiplying two ciphertexts adds the
//!   plaintexts — that's the entire point.  Do not use Paillier as
//!   "encryption with integrity"; if you need that, run the
//!   ciphertext through a separate authenticated channel or wrap it
//!   with a non-malleable transformation (Cramer–Shoup style).
//! - **Not constant-time.**  Decryption uses `λ`-exponentiation in
//!   `Z_{n²}` via `mod_pow`, which is variable-time.  HE schemes
//!   broadly do not have constant-time decryption — the secret-
//!   dependent reductions are too expensive to mask.  Mitigation:
//!   only decrypt on a server that an attacker cannot time.
//! - **Refuses small `n`.**  Minimum modulus size is 2048 bits
//!   (NIST 2030+ recommendation for factoring-based schemes).

use crate::asymmetric::rsa::random_prime;
use crate::utils::{mod_inverse, mod_pow};
use num_bigint::{BigUint, RandBigInt};
use num_integer::Integer;
use num_traits::{One, Zero};
use rand::rngs::OsRng;

/// Public key.  Holds the modulus `n` (and `n²` precomputed) and the
/// generator `g`.  We use the canonical simplification `g = n + 1`
/// from Paillier §6 — this lets `g^m mod n²` collapse to
/// `(1 + m·n) mod n²` and makes encryption a single multiplication
/// plus one `r^n mod n²` exponentiation rather than two
/// exponentiations.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PaillierPublicKey {
    pub n: BigUint,
    pub n_squared: BigUint,
    pub g: BigUint,
}

/// Private key.  Holds `λ = lcm(p − 1, q − 1)` and the precomputed
/// `μ = (L(g^λ mod n²))⁻¹ mod n` where `L(u) = (u − 1) / n`.  The
/// public key is bundled inside so a `&PrivateKey` is sufficient for
/// every operation, including the homomorphic ones.
#[derive(Clone, Debug)]
pub struct PaillierPrivateKey {
    pub public: PaillierPublicKey,
    pub lambda: BigUint,
    pub mu: BigUint,
    /// Stored only so [`Drop`] can scrub them.  Not used after keygen
    /// because we hold `λ` directly.
    p: BigUint,
    q: BigUint,
}

impl Drop for PaillierPrivateKey {
    fn drop(&mut self) {
        self.lambda = BigUint::zero();
        self.mu = BigUint::zero();
        self.p = BigUint::zero();
        self.q = BigUint::zero();
    }
}

/// Generate a fresh Paillier keypair with `bits`-bit modulus.
///
/// `bits` must be ≥ 2048 and even.  Each prime is `bits / 2` bits.
/// Average runtime ≈ 2× RSA keygen at the same modulus size.
pub fn paillier_keygen(bits: u64) -> Result<PaillierPrivateKey, &'static str> {
    if bits < 2048 {
        return Err("Paillier modulus must be ≥ 2048 bits (NIST 2030+ recommendation)");
    }
    if !bits.is_multiple_of(2) {
        return Err("modulus bit-size must be even");
    }
    let half = bits / 2;

    loop {
        let p = random_prime(half);
        let q = random_prime(half);
        if p == q {
            continue;
        }

        let n = &p * &q;

        // gcd(n, (p-1)(q-1)) = 1 is required for the scheme to work.
        // For RSA-style primes (both > 2, p ≠ q) this always holds, but
        // we check defensively in case `random_prime` ever returns
        // something pathological.
        let p1 = &p - BigUint::one();
        let q1 = &q - BigUint::one();
        let phi = &p1 * &q1;
        if n.gcd(&phi) != BigUint::one() {
            continue;
        }

        let lambda = p1.lcm(&q1);
        let n_squared = &n * &n;

        // Canonical simplification: g = n + 1.
        // Then g^x mod n² = 1 + x·n mod n² (binomial expansion;
        // higher powers of n vanish modulo n²).
        let g = &n + BigUint::one();

        // μ = (L(g^λ mod n²))⁻¹ mod n
        // With g = n+1: g^λ ≡ 1 + λ·n (mod n²), so L(g^λ mod n²) = λ mod n,
        // and μ = λ⁻¹ mod n.
        let mu = match mod_inverse(&lambda, &n) {
            Some(v) => v,
            None => continue, // can't happen for our `g`, but keep it total
        };

        return Ok(PaillierPrivateKey {
            public: PaillierPublicKey { n, n_squared, g },
            lambda,
            mu,
            p,
            q,
        });
    }
}

/// Sample `r ∈ Z_n*` uniformly at random.  Used as the encryption
/// nonce.  Rejection-samples until `gcd(r, n) = 1` (a one-in-billions
/// rejection rate for cryptographic-size `n`).
fn sample_r(n: &BigUint) -> BigUint {
    let mut rng = OsRng;
    loop {
        let r = rng.gen_biguint_below(n);
        if r > BigUint::one() && r.gcd(n).is_one() {
            return r;
        }
    }
}

/// Encrypt a message `m ∈ [0, n)` under public key `pk`.
///
/// Returns a fresh ciphertext `c = g^m · r^n mod n²` where `r` is a
/// freshly-sampled `r ∈ Z_n*`.  Calling encrypt twice on the same
/// `m` yields two distinct ciphertexts (Paillier is probabilistic).
pub fn paillier_encrypt(pk: &PaillierPublicKey, m: &BigUint) -> Result<BigUint, &'static str> {
    if m >= &pk.n {
        return Err("plaintext must be in [0, n)");
    }
    let r = sample_r(&pk.n);
    Ok(paillier_encrypt_with_randomness(pk, m, &r))
}

/// Encrypt with caller-supplied randomness — exposed only for
/// testing / re-randomisation patterns.  **Never reuse `r` across
/// two encryptions**: doing so leaks `m₁ - m₂ mod n` instantly.
pub fn paillier_encrypt_with_randomness(
    pk: &PaillierPublicKey,
    m: &BigUint,
    r: &BigUint,
) -> BigUint {
    // c = g^m · r^n mod n²
    // With g = n+1: g^m mod n² = 1 + m·n mod n² — no exponentiation needed.
    let g_m = (BigUint::one() + m * &pk.n) % &pk.n_squared;
    let r_n = mod_pow(r, &pk.n, &pk.n_squared);
    (g_m * r_n) % &pk.n_squared
}

/// Decrypt ciphertext `c` under private key `sk`.  Returns the
/// plaintext `m ∈ [0, n)`.
pub fn paillier_decrypt(sk: &PaillierPrivateKey, c: &BigUint) -> Result<BigUint, &'static str> {
    if c >= &sk.public.n_squared {
        return Err("ciphertext must be in [0, n²)");
    }
    // m = L(c^λ mod n²) · μ mod n,   where L(u) = (u - 1) / n.
    let c_lambda = mod_pow(c, &sk.lambda, &sk.public.n_squared);
    let l_value = (&c_lambda - BigUint::one()) / &sk.public.n;
    let m = (l_value * &sk.mu) % &sk.public.n;
    Ok(m)
}

// ── Homomorphic operations ───────────────────────────────────────────────────

/// **Homomorphic addition of two ciphertexts.**
///
/// `paillier_add(pk, enc(m₁), enc(m₂))` returns a ciphertext that
/// decrypts to `(m₁ + m₂) mod n`.  Implementation:
/// `c₁ · c₂ mod n²`.
///
/// The result is a valid Paillier ciphertext with effective
/// randomness `r₁ · r₂ mod n` — still uniform in `Z_n*`, so adding
/// preserves IND-CPA freshness.
pub fn paillier_add(pk: &PaillierPublicKey, c1: &BigUint, c2: &BigUint) -> BigUint {
    (c1 * c2) % &pk.n_squared
}

/// **Homomorphic addition of a public plaintext to a ciphertext.**
///
/// `paillier_add_plain(pk, enc(m₁), m₂)` returns `enc(m₁ + m₂ mod n)`.
/// Implementation: `c · g^m₂ mod n² = c · (1 + m₂ · n) mod n²`.
pub fn paillier_add_plain(pk: &PaillierPublicKey, c: &BigUint, m: &BigUint) -> BigUint {
    let g_m = (BigUint::one() + m * &pk.n) % &pk.n_squared;
    (c * g_m) % &pk.n_squared
}

/// **Homomorphic scalar multiplication by a public constant.**
///
/// `paillier_mul_scalar(pk, enc(m), k)` returns `enc(k · m mod n)`.
/// Implementation: `c^k mod n²`.
pub fn paillier_mul_scalar(pk: &PaillierPublicKey, c: &BigUint, k: &BigUint) -> BigUint {
    mod_pow(c, k, &pk.n_squared)
}

/// **Re-randomise a ciphertext** without changing its plaintext.
///
/// Multiplies by a fresh `r^n mod n²`.  Useful when you need to
/// hand a ciphertext to a third party who must not be able to link
/// it to the original (e.g. anonymous voting tally).
pub fn paillier_rerandomise(pk: &PaillierPublicKey, c: &BigUint) -> BigUint {
    let r = sample_r(&pk.n);
    let r_n = mod_pow(&r, &pk.n, &pk.n_squared);
    (c * r_n) % &pk.n_squared
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Use a small but non-trivial modulus for fast tests, then a
    /// production-size keypair for one end-to-end smoke test.
    fn test_keypair() -> PaillierPrivateKey {
        // 2048 bits is the minimum the keygen will accept.
        paillier_keygen(2048).unwrap()
    }

    #[test]
    fn keygen_rejects_small_modulus() {
        assert!(paillier_keygen(1024).is_err());
        assert!(paillier_keygen(2047).is_err()); // odd
    }

    #[test]
    fn keygen_2048_produces_valid_keypair() {
        let sk = paillier_keygen(2048).unwrap();
        // n should be ~2048 bits.
        let bits = sk.public.n.bits();
        assert!((2047..=2048).contains(&bits), "modulus has {} bits", bits);
        // If n is 2047 bits, n² can be 4093 bits; if n is 2048 bits, n² can
        // be 4095-4096 bits. All are valid for two 1024-bit primes.
        assert!(sk.public.n_squared.bits() >= 4093);
        // g = n + 1
        assert_eq!(sk.public.g, &sk.public.n + BigUint::one());
    }

    #[test]
    fn encrypt_decrypt_roundtrip() {
        let sk = test_keypair();
        let m = BigUint::from(424242u64);
        let c = paillier_encrypt(&sk.public, &m).unwrap();
        let m2 = paillier_decrypt(&sk, &c).unwrap();
        assert_eq!(m, m2);
    }

    #[test]
    fn encrypt_decrypt_zero() {
        let sk = test_keypair();
        let m = BigUint::zero();
        let c = paillier_encrypt(&sk.public, &m).unwrap();
        let m2 = paillier_decrypt(&sk, &c).unwrap();
        assert_eq!(m, m2);
    }

    #[test]
    fn encrypt_rejects_oversize_plaintext() {
        let sk = test_keypair();
        // m = n is out of range.
        assert!(paillier_encrypt(&sk.public, &sk.public.n).is_err());
    }

    /// Two encryptions of the same plaintext must produce different
    /// ciphertexts (semantic security smoke test).
    #[test]
    fn encrypt_is_probabilistic() {
        let sk = test_keypair();
        let m = BigUint::from(0x1234_5678u64);
        let c1 = paillier_encrypt(&sk.public, &m).unwrap();
        let c2 = paillier_encrypt(&sk.public, &m).unwrap();
        assert_ne!(c1, c2, "Paillier must be probabilistic");
        // But both must decrypt to the same m.
        assert_eq!(paillier_decrypt(&sk, &c1).unwrap(), m);
        assert_eq!(paillier_decrypt(&sk, &c2).unwrap(), m);
    }

    /// **Homomorphic addition** — the headline property.
    /// `dec(enc(m₁) · enc(m₂)) = m₁ + m₂ mod n`.
    #[test]
    fn homomorphic_add_two_ciphertexts() {
        let sk = test_keypair();
        let m1 = BigUint::from(100u64);
        let m2 = BigUint::from(250u64);
        let c1 = paillier_encrypt(&sk.public, &m1).unwrap();
        let c2 = paillier_encrypt(&sk.public, &m2).unwrap();
        let c_sum = paillier_add(&sk.public, &c1, &c2);
        let m_sum = paillier_decrypt(&sk, &c_sum).unwrap();
        assert_eq!(m_sum, BigUint::from(350u64));
    }

    /// Adding a public plaintext to a ciphertext.
    #[test]
    fn homomorphic_add_plain() {
        let sk = test_keypair();
        let m = BigUint::from(1000u64);
        let delta = BigUint::from(7u64);
        let c = paillier_encrypt(&sk.public, &m).unwrap();
        let c2 = paillier_add_plain(&sk.public, &c, &delta);
        let m2 = paillier_decrypt(&sk, &c2).unwrap();
        assert_eq!(m2, BigUint::from(1007u64));
    }

    /// Scalar multiplication.
    #[test]
    fn homomorphic_scalar_multiply() {
        let sk = test_keypair();
        let m = BigUint::from(13u64);
        let k = BigUint::from(7u64);
        let c = paillier_encrypt(&sk.public, &m).unwrap();
        let c_k = paillier_mul_scalar(&sk.public, &c, &k);
        let m_k = paillier_decrypt(&sk, &c_k).unwrap();
        assert_eq!(m_k, BigUint::from(91u64), "13 × 7 = 91");
    }

    /// **Encrypted aggregation**: Σ_{i=1..10} enc(i) → enc(55).
    /// This is the canonical "private sum" use case — federated
    /// balance tally, sealed-bid bid total, etc.
    #[test]
    fn encrypted_aggregation_of_ten_values() {
        let sk = test_keypair();
        let pk = &sk.public;

        // Start with enc(0).
        let mut acc = paillier_encrypt(pk, &BigUint::zero()).unwrap();
        for i in 1u64..=10 {
            let c_i = paillier_encrypt(pk, &BigUint::from(i)).unwrap();
            acc = paillier_add(pk, &acc, &c_i);
        }

        let total = paillier_decrypt(&sk, &acc).unwrap();
        assert_eq!(total, BigUint::from(55u64), "1+2+...+10 = 55");
    }

    /// Re-randomisation preserves plaintext but changes the ciphertext.
    #[test]
    fn rerandomise_preserves_plaintext() {
        let sk = test_keypair();
        let m = BigUint::from(0xdead_beefu64);
        let c1 = paillier_encrypt(&sk.public, &m).unwrap();
        let c2 = paillier_rerandomise(&sk.public, &c1);
        assert_ne!(c1, c2, "rerandomisation must change ciphertext");
        assert_eq!(paillier_decrypt(&sk, &c2).unwrap(), m);
    }

    /// Edge case: m near n - 1 (largest representable plaintext).
    #[test]
    fn encrypt_decrypt_max_plaintext() {
        let sk = test_keypair();
        let m = &sk.public.n - BigUint::one();
        let c = paillier_encrypt(&sk.public, &m).unwrap();
        assert_eq!(paillier_decrypt(&sk, &c).unwrap(), m);
    }

    /// Wrap-around: enc(n - 1) + enc(2) ≡ enc(1) mod n.
    #[test]
    fn homomorphic_add_wraps_at_modulus() {
        let sk = test_keypair();
        let m1 = &sk.public.n - BigUint::one();
        let m2 = BigUint::from(2u64);
        let c1 = paillier_encrypt(&sk.public, &m1).unwrap();
        let c2 = paillier_encrypt(&sk.public, &m2).unwrap();
        let c_sum = paillier_add(&sk.public, &c1, &c2);
        let m_sum = paillier_decrypt(&sk, &c_sum).unwrap();
        assert_eq!(m_sum, BigUint::one(), "(n-1) + 2 ≡ 1 (mod n)");
    }

    /// The "encrypt with the wrong public key" sanity: decrypting
    /// under the wrong sk must NOT produce the original plaintext
    /// (with overwhelming probability).
    #[test]
    fn decrypt_with_wrong_key_fails() {
        let sk_a = test_keypair();
        let sk_b = test_keypair();
        // Pick m small enough that it lies in both moduli.
        let m = BigUint::from(42u64);
        let c = paillier_encrypt(&sk_a.public, &m).unwrap();
        // Decrypting under sk_b only works if c happens to be in [0, n_b²),
        // which it usually isn't — but if it is, the result is garbage.
        if c < sk_b.public.n_squared {
            let m_wrong = paillier_decrypt(&sk_b, &c).unwrap();
            assert_ne!(m_wrong, m);
        }
    }
}
