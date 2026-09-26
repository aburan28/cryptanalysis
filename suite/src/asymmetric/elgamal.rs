//! ElGamal — multiplicative partially-homomorphic encryption over `Z_p*`.
//!
//! Taher ElGamal, "A public-key cryptosystem and a signature scheme
//! based on discrete logarithms," CRYPTO 1984.
//!
//! Security reduces to the Decisional Diffie-Hellman (DDH) assumption
//! in the prime-order subgroup `G_q ⊆ Z_p*`.  We use a hardcoded
//! standardised group from RFC 3526 (the 2048-bit MODP group, "Group
//! 14") — the same prime that TLS, IPsec, and SSH use as a fallback
//! DH group.  Hardcoding avoids the substantial cost of generating
//! a fresh safe prime per keypair (~30 s at 2048 bits) and matches
//! how real systems deploy DH-style cryptography: standard groups
//! are vetted, fresh primes are not.
//!
//! # Homomorphic property
//!
//! ElGamal is **multiplicatively** homomorphic:
//!
//! ```text
//! enc(m₁) = (g^k₁, m₁ · h^k₁)
//! enc(m₂) = (g^k₂, m₂ · h^k₂)
//!
//! enc(m₁) ⊙ enc(m₂)
//!   = (g^(k₁+k₂),  m₁·m₂ · h^(k₁+k₂))
//!   = enc(m₁ · m₂ mod p)
//! ```
//!
//! This is the dual of [Paillier](super::paillier) (which is
//! additive).  Use ElGamal when your protocol naturally combines
//! values multiplicatively — geometric means, threshold-product
//! protocols, RSA-style "blind signatures by composition."
//!
//! # Why hardcode RFC 3526 Group 14?
//!
//! ElGamal's security depends on DDH being hard in the chosen
//! group.  Hardness in turn requires:
//!
//! 1. The order `q` of the generator's subgroup is a large prime.
//! 2. `p − 1 = 2 q · k` for *some* small `k` (1 for safe primes,
//!    larger for "DSA-like" primes).
//! 3. The chosen `g` actually generates a prime-order subgroup of
//!    size `q` — not the whole `Z_p*`, which has order `p − 1` and
//!    contains the −1 subgroup that leaks one bit per ciphertext
//!    via Legendre symbols.
//!
//! Rolling your own primes safely takes care.  RFC 3526 Group 14
//! gives us all three properties for free, with `p` a 2048-bit safe
//! prime (`q = (p − 1) / 2` also prime), `g = 2`, and Pohlig-Hellman
//! resistance proven by the safe-prime structure.
//!
//! # Limitations
//!
//! - **Plaintext space** is `(0, p)` — message must be a non-zero
//!   integer mod `p`.  In practice, embed your data as an element
//!   of `G_q` (the order-`q` subgroup), e.g. via squaring:
//!   `m̃ = m² mod p` is always in `G_q`.  We don't enforce this in
//!   `encrypt` because the multiplicative homomorphism is preserved
//!   regardless; it's the caller's responsibility to ensure the
//!   plaintext encoding lies in the right subgroup if their protocol
//!   needs it.
//! - **No standardised AEAD construction.**  ElGamal is malleable
//!   by design (multiplying ciphertexts multiplies plaintexts).
//!   Do not use as encryption-with-integrity.
//! - **Decryption is variable-time.**  The `c₁^x` exponentiation
//!   uses `mod_pow`, which is not constant-time.  Same posture as
//!   Paillier — HE schemes generally don't have CT decryption.
//! - **Refuses small groups.**  Hardcoded to RFC 3526 Group 14
//!   (2048-bit `p`, ≥112-bit security per NIST SP 800-57); no
//!   smaller-group constructor is exposed.

use crate::utils::{mod_inverse, mod_pow};
use num_bigint::{BigUint, RandBigInt};
use num_integer::Integer;
use num_traits::One;
use rand::rngs::OsRng;

/// RFC 3526 Group 14 prime `p` — 2048-bit safe prime.
///
/// `p = 2^2048 − 2^1984 − 1 + 2^64 · ⌊2^1918 · π + 124476⌋`
///
/// `q = (p − 1) / 2` is also prime (Sophie Germain pair).  `g = 2`
/// generates the order-`q` subgroup of `Z_p*`.
const RFC3526_GROUP_14_HEX: &str = "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA051015728E5A8AACAA68FFFFFFFFFFFFFFFF";

/// Public parameters of the standardised ElGamal group.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ElGamalGroup {
    pub p: BigUint,
    pub q: BigUint,
    pub g: BigUint,
}

impl ElGamalGroup {
    /// RFC 3526 Group 14 — the canonical 2048-bit MODP group.
    pub fn rfc3526_group_14() -> Self {
        let p = BigUint::parse_bytes(RFC3526_GROUP_14_HEX.as_bytes(), 16).expect("valid hex");
        let q = (&p - BigUint::one()) >> 1;
        Self {
            p,
            q,
            g: BigUint::from(2u32),
        }
    }
}

/// ElGamal public key: the group plus `h = g^x mod p`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ElGamalPublicKey {
    pub group: ElGamalGroup,
    pub h: BigUint,
}

/// ElGamal private key: discrete log `x` such that `h = g^x mod p`.
#[derive(Clone, Debug)]
pub struct ElGamalPrivateKey {
    pub public: ElGamalPublicKey,
    x: BigUint,
}

impl Drop for ElGamalPrivateKey {
    fn drop(&mut self) {
        self.x = BigUint::from(0u32);
    }
}

/// ElGamal ciphertext: pair `(c₁, c₂)` over `Z_p`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ElGamalCiphertext {
    pub c1: BigUint,
    pub c2: BigUint,
}

/// Generate an ElGamal keypair in RFC 3526 Group 14.
///
/// Picks `x ∈ [1, q)` uniformly and computes `h = g^x mod p`.
pub fn elgamal_keygen() -> ElGamalPrivateKey {
    let group = ElGamalGroup::rfc3526_group_14();
    let mut rng = OsRng;
    let x = rng.gen_biguint_below(&group.q);
    let x = if x.is_zero_choice() {
        BigUint::one()
    } else {
        x
    };
    let h = mod_pow(&group.g, &x, &group.p);
    ElGamalPrivateKey {
        public: ElGamalPublicKey { group, h },
        x,
    }
}

/// Tiny helper since `BigUint` doesn't have a stable `is_zero` const.
trait BigUintZeroExt {
    fn is_zero_choice(&self) -> bool;
}
impl BigUintZeroExt for BigUint {
    fn is_zero_choice(&self) -> bool {
        self == &BigUint::from(0u32)
    }
}

/// Encrypt `m ∈ (0, p)` under public key `pk`.  Probabilistic —
/// every call samples a fresh `k`.
pub fn elgamal_encrypt(
    pk: &ElGamalPublicKey,
    m: &BigUint,
) -> Result<ElGamalCiphertext, &'static str> {
    if m == &BigUint::from(0u32) || m >= &pk.group.p {
        return Err("plaintext must lie in (0, p)");
    }
    let mut rng = OsRng;
    let k = loop {
        let candidate = rng.gen_biguint_below(&pk.group.q);
        if !candidate.is_zero_choice() {
            break candidate;
        }
    };
    let c1 = mod_pow(&pk.group.g, &k, &pk.group.p);
    let h_k = mod_pow(&pk.h, &k, &pk.group.p);
    let c2 = (m * &h_k) % &pk.group.p;
    Ok(ElGamalCiphertext { c1, c2 })
}

/// Decrypt under private key `sk`.  Returns `m ∈ (0, p)`.
pub fn elgamal_decrypt(
    sk: &ElGamalPrivateKey,
    c: &ElGamalCiphertext,
) -> Result<BigUint, &'static str> {
    let p = &sk.public.group.p;
    if &c.c1 >= p || &c.c2 >= p {
        return Err("ciphertext components must be in [0, p)");
    }
    // m = c₂ · (c₁^x)^(-1) mod p
    let s = mod_pow(&c.c1, &sk.x, p);
    let s_inv = mod_inverse(&s, p).ok_or("c1^x had no inverse mod p")?;
    Ok((&c.c2 * &s_inv) % p)
}

// ── Homomorphic operations ───────────────────────────────────────────────────

/// **Multiplicative homomorphism**:
/// `dec(elgamal_mul(c_a, c_b)) == m_a · m_b mod p`.
pub fn elgamal_mul(
    pk: &ElGamalPublicKey,
    ca: &ElGamalCiphertext,
    cb: &ElGamalCiphertext,
) -> ElGamalCiphertext {
    let p = &pk.group.p;
    ElGamalCiphertext {
        c1: (&ca.c1 * &cb.c1) % p,
        c2: (&ca.c2 * &cb.c2) % p,
    }
}

/// **Plaintext multiplication** by a public scalar `k`:
/// `dec(elgamal_mul_plain(c, k)) == k · m mod p`.
///
/// Implementation: `(c₁, c₂) ↦ (c₁, k · c₂)`.  This makes the
/// ciphertext deterministic-rerandomisation-equivalent — re-randomise
/// afterwards if anonymity matters.
pub fn elgamal_mul_plain(
    pk: &ElGamalPublicKey,
    c: &ElGamalCiphertext,
    k: &BigUint,
) -> Result<ElGamalCiphertext, &'static str> {
    if k == &BigUint::from(0u32) || k >= &pk.group.p {
        return Err("scalar must lie in (0, p)");
    }
    Ok(ElGamalCiphertext {
        c1: c.c1.clone(),
        c2: (k * &c.c2) % &pk.group.p,
    })
}

/// **Plaintext exponentiation** by a public exponent `k`:
/// `dec(elgamal_pow(c, k)) == m^k mod p`.
///
/// Implementation: `(c₁^k, c₂^k)`.
pub fn elgamal_pow(pk: &ElGamalPublicKey, c: &ElGamalCiphertext, k: &BigUint) -> ElGamalCiphertext {
    let p = &pk.group.p;
    ElGamalCiphertext {
        c1: mod_pow(&c.c1, k, p),
        c2: mod_pow(&c.c2, k, p),
    }
}

/// Re-randomise a ciphertext without changing its plaintext.
///
/// Multiplies by `(g^k', h^k')` for fresh `k'`.
pub fn elgamal_rerandomise(pk: &ElGamalPublicKey, c: &ElGamalCiphertext) -> ElGamalCiphertext {
    let p = &pk.group.p;
    let mut rng = OsRng;
    let k = rng.gen_biguint_below(&pk.group.q);
    let g_k = mod_pow(&pk.group.g, &k, p);
    let h_k = mod_pow(&pk.h, &k, p);
    ElGamalCiphertext {
        c1: (&c.c1 * &g_k) % p,
        c2: (&c.c2 * &h_k) % p,
    }
}

// `Integer::gcd` is available via the `num_integer` import in the
// dependency graph; we don't currently use it here but keep the
// import path live by silencing dead-code lints if the compiler ever
// folds it out.
#[allow(dead_code)]
fn _gcd_link(a: &BigUint, b: &BigUint) -> BigUint {
    a.gcd(b)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn keypair() -> ElGamalPrivateKey {
        elgamal_keygen()
    }

    #[test]
    fn rfc3526_group_14_is_2048_bit_safe_prime() {
        let group = ElGamalGroup::rfc3526_group_14();
        assert_eq!(group.p.bits(), 2048);
        // q = (p - 1) / 2 should be one bit shorter.
        assert_eq!(group.q.bits(), 2047);
        // p = 2q + 1.
        assert_eq!(&group.q * BigUint::from(2u32) + BigUint::one(), group.p);
        // g = 2.
        assert_eq!(group.g, BigUint::from(2u32));
    }

    #[test]
    fn keygen_produces_consistent_keypair() {
        let sk = keypair();
        // h = g^x mod p
        let h_check = mod_pow(&sk.public.group.g, &sk.x, &sk.public.group.p);
        assert_eq!(sk.public.h, h_check);
    }

    #[test]
    fn encrypt_decrypt_roundtrip() {
        let sk = keypair();
        let m = BigUint::from(0xdead_beef_u64);
        let c = elgamal_encrypt(&sk.public, &m).unwrap();
        let m2 = elgamal_decrypt(&sk, &c).unwrap();
        assert_eq!(m, m2);
    }

    #[test]
    fn encrypt_rejects_zero_and_oversize() {
        let sk = keypair();
        assert!(elgamal_encrypt(&sk.public, &BigUint::from(0u32)).is_err());
        assert!(elgamal_encrypt(&sk.public, &sk.public.group.p).is_err());
    }

    /// Two encryptions of the same plaintext must differ.
    #[test]
    fn encrypt_is_probabilistic() {
        let sk = keypair();
        let m = BigUint::from(424242u64);
        let c1 = elgamal_encrypt(&sk.public, &m).unwrap();
        let c2 = elgamal_encrypt(&sk.public, &m).unwrap();
        assert_ne!(c1, c2);
        assert_eq!(elgamal_decrypt(&sk, &c1).unwrap(), m);
        assert_eq!(elgamal_decrypt(&sk, &c2).unwrap(), m);
    }

    /// Headline property: `dec(c_a · c_b) = m_a · m_b mod p`.
    #[test]
    fn homomorphic_multiply_two_ciphertexts() {
        let sk = keypair();
        let ma = BigUint::from(7u32);
        let mb = BigUint::from(11u32);
        let ca = elgamal_encrypt(&sk.public, &ma).unwrap();
        let cb = elgamal_encrypt(&sk.public, &mb).unwrap();
        let cmul = elgamal_mul(&sk.public, &ca, &cb);
        let m = elgamal_decrypt(&sk, &cmul).unwrap();
        assert_eq!(m, BigUint::from(77u32), "7 × 11 = 77");
    }

    /// Plaintext multiplication by a public constant.
    #[test]
    fn homomorphic_multiply_by_plain() {
        let sk = keypair();
        let m = BigUint::from(13u32);
        let k = BigUint::from(5u32);
        let c = elgamal_encrypt(&sk.public, &m).unwrap();
        let c2 = elgamal_mul_plain(&sk.public, &c, &k).unwrap();
        let result = elgamal_decrypt(&sk, &c2).unwrap();
        assert_eq!(result, BigUint::from(65u32), "13 × 5 = 65");
    }

    /// `enc(m)^k = enc(m^k)`.
    #[test]
    fn homomorphic_exponentiate() {
        let sk = keypair();
        let m = BigUint::from(3u32);
        let k = BigUint::from(7u32);
        let c = elgamal_encrypt(&sk.public, &m).unwrap();
        let c_k = elgamal_pow(&sk.public, &c, &k);
        let result = elgamal_decrypt(&sk, &c_k).unwrap();
        assert_eq!(result, BigUint::from(2187u32), "3^7 = 2187");
    }

    /// Chained product: enc(2) × enc(3) × enc(5) × enc(7) = enc(210).
    #[test]
    fn homomorphic_chained_product() {
        let sk = keypair();
        let pk = &sk.public;
        let mut acc = elgamal_encrypt(pk, &BigUint::one()).unwrap();
        for v in [2u32, 3, 5, 7] {
            let c_v = elgamal_encrypt(pk, &BigUint::from(v)).unwrap();
            acc = elgamal_mul(pk, &acc, &c_v);
        }
        let result = elgamal_decrypt(&sk, &acc).unwrap();
        assert_eq!(result, BigUint::from(210u32));
    }

    #[test]
    fn rerandomise_preserves_plaintext() {
        let sk = keypair();
        let m = BigUint::from(0x1234_5678_u64);
        let c1 = elgamal_encrypt(&sk.public, &m).unwrap();
        let c2 = elgamal_rerandomise(&sk.public, &c1);
        assert_ne!(c1, c2);
        assert_eq!(elgamal_decrypt(&sk, &c2).unwrap(), m);
    }

    /// Decryption under wrong key must NOT recover the plaintext.
    #[test]
    fn decrypt_with_wrong_key_fails() {
        let sk_a = keypair();
        let sk_b = keypair();
        let m = BigUint::from(42u32);
        let c = elgamal_encrypt(&sk_a.public, &m).unwrap();
        let m_wrong = elgamal_decrypt(&sk_b, &c).unwrap();
        assert_ne!(m_wrong, m, "wrong key must not decrypt");
    }
}
