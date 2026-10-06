//! Exponential ElGamal — *additive* partially-homomorphic encryption
//! over an elliptic curve.
//!
//! The same scheme used in the Helios voting system and most modern
//! "encrypt your vote, tally homomorphically" protocols.  Unlike
//! multiplicative ElGamal in [`super::elgamal`], this variant
//! encodes the plaintext `m` as the curve point `m·G` rather than as
//! `m` directly; ciphertext addition then composes the encoded
//! plaintexts as `(m_a + m_b)·G`.
//!
//! # Homomorphic property
//!
//! ```text
//! enc(m₁) = (k₁·G,  m₁·G + k₁·Q)
//! enc(m₂) = (k₂·G,  m₂·G + k₂·Q)
//!
//! enc(m₁) ⊞ enc(m₂)
//!   = ((k₁+k₂)·G,  (m₁+m₂)·G + (k₁+k₂)·Q)
//!   = enc(m₁ + m₂)
//! ```
//!
//! …all on the curve.  This is **the** scheme for encrypted vote
//! tally and small-counter aggregation.
//!
//! # Decryption — and why messages must be small
//!
//! Decrypt computes `M = C₂ − d·C₁ = m·G`, then recovers `m` by
//! solving the **elliptic-curve discrete log problem** for that one
//! specific point.  ECDLP is hard in general — that's the whole
//! reason ECC works — so EC-ElGamal decryption is only feasible
//! when `m` is *known to lie in a small range*.  We use baby-step
//! giant-step (BSGS) to recover `m ∈ [0, M_max)` in
//! `O(√M_max)` time and `O(√M_max)` memory.
//!
//! Default `M_max = 2³²`: covers any vote tally with up to 4
//! billion participants, any ledger with sub-cent units up to
//! ~$40 M, any sensor count up to 4 G.  Callers can dial it up to
//! `2⁴⁰` (~1 trillion) at the cost of ~16 MB of BSGS table memory
//! and ~1 s of decrypt time on commodity hardware.  Higher than
//! that means EC-ElGamal is the wrong tool — use Paillier instead.
//!
//! # Use cases
//!
//! - **End-to-end verifiable voting** (Helios, ElectionGuard) — each
//!   vote is `enc(0)` or `enc(1)`; tally is the sum, decrypted by
//!   the election authority.
//! - **Threshold counter aggregation** — federated counters where
//!   each participant contributes an encrypted increment.
//! - **Small-balance private ledgers** where balances fit in 32 bits.

use crate::ecc::curve::CurveParams;
use crate::ecc::point::Point;
use num_bigint::{BigUint, RandBigInt};
use num_traits::Zero;
use rand::rngs::OsRng;
use std::collections::HashMap;

/// EC-ElGamal public key over a chosen curve.
#[derive(Clone, Debug)]
pub struct EcElGamalPublicKey {
    pub curve: CurveParams,
    /// `Q = d·G`, the public point.
    pub q: Point,
}

/// EC-ElGamal private key.
#[derive(Clone, Debug)]
pub struct EcElGamalPrivateKey {
    pub public: EcElGamalPublicKey,
    d: BigUint,
}

impl Drop for EcElGamalPrivateKey {
    fn drop(&mut self) {
        self.d = BigUint::zero();
    }
}

/// EC-ElGamal ciphertext: a pair of curve points.
#[derive(Clone, Debug, PartialEq)]
pub struct EcElGamalCiphertext {
    pub c1: Point,
    pub c2: Point,
}

/// Generate a fresh keypair on the provided curve.
pub fn ec_elgamal_keygen(curve: CurveParams) -> EcElGamalPrivateKey {
    let mut rng = OsRng;
    // d ∈ [1, n) where n is the curve order.
    let n = curve.n.clone();
    let d = loop {
        let candidate = rng.gen_biguint_below(&n);
        if !candidate.is_zero() {
            break candidate;
        }
    };
    let g = curve.generator();
    let bits = curve.order_bits();
    let q = g.scalar_mul_ct(&d, &curve.a_fe(), bits);
    EcElGamalPrivateKey {
        public: EcElGamalPublicKey { curve, q },
        d,
    }
}

/// Encrypt the integer `m` under public key `pk`.
///
/// Panics if `pk` or `m` is invalid. Prefer [`ec_elgamal_encrypt_checked`]
/// when those inputs are untrusted.
pub fn ec_elgamal_encrypt(pk: &EcElGamalPublicKey, m: &BigUint) -> EcElGamalCiphertext {
    ec_elgamal_encrypt_checked(pk, m).expect("invalid EC-ElGamal public key or plaintext")
}

/// Checked EC-ElGamal encryption.
///
/// Plaintexts are accepted only in `[0, n)` to avoid the `m·G` encoding
/// collision where `m` and `m + n` encrypt to the same curve point.
pub fn ec_elgamal_encrypt_checked(
    pk: &EcElGamalPublicKey,
    m: &BigUint,
) -> Result<EcElGamalCiphertext, &'static str> {
    validate_public_key(pk)?;
    if m >= &pk.curve.n {
        return Err("plaintext must be in [0, n)");
    }
    let mut rng = OsRng;
    let n = &pk.curve.n;
    let k = loop {
        let candidate = rng.gen_biguint_below(n);
        if !candidate.is_zero() {
            break candidate;
        }
    };
    let g = pk.curve.generator();
    let bits = pk.curve.order_bits();
    let a = pk.curve.a_fe();
    // C1 = k·G, C2 = m·G + k·Q
    let c1 = g.scalar_mul_ct(&k, &a, bits);
    let m_g = g.scalar_mul(m, &a);
    let k_q = pk.q.scalar_mul_ct(&k, &a, bits);
    let c2 = m_g.add(&k_q, &a);
    Ok(EcElGamalCiphertext { c1, c2 })
}

/// Recover `M = m·G` — the encoded plaintext as a curve point.
///
/// Returns the point but does NOT solve DLP.  Useful for protocols
/// that operate on the encoded plaintext without ever needing the
/// integer (e.g. equality tests via point comparison).
pub fn ec_elgamal_decrypt_point(sk: &EcElGamalPrivateKey, c: &EcElGamalCiphertext) -> Point {
    ec_elgamal_decrypt_point_checked(sk, c).expect("invalid EC-ElGamal ciphertext")
}

/// Checked variant of [`ec_elgamal_decrypt_point`].
pub fn ec_elgamal_decrypt_point_checked(
    sk: &EcElGamalPrivateKey,
    c: &EcElGamalCiphertext,
) -> Result<Point, &'static str> {
    validate_public_key(&sk.public)?;
    validate_ciphertext(&sk.public.curve, c)?;
    let a = sk.public.curve.a_fe();
    let bits = sk.public.curve.order_bits();
    let d_c1 = c.c1.scalar_mul_ct(&sk.d, &a, bits);
    // M = C2 − d·C1 = C2 + (−(d·C1))
    Ok(c.c2.add(&d_c1.neg(), &a))
}

/// Recover the integer plaintext via baby-step giant-step DLP.
///
/// Searches for `m ∈ [0, m_max)` such that `m·G = decrypt_point(c)`.
/// Returns `Err` if no `m` in that range matches — caller must
/// either expand `m_max` or accept that the ciphertext is malformed.
///
/// **Performance.**  Time and memory are both `O(√m_max)`.  At
/// `m_max = 2³²` (the default for [`ec_elgamal_decrypt`]) this is
/// ~65 K table entries (~3 MB) and ~65 K point additions
/// (~milliseconds).  Linear in the table size.
pub fn ec_elgamal_decrypt_bounded(
    sk: &EcElGamalPrivateKey,
    c: &EcElGamalCiphertext,
    m_max: u64,
) -> Result<u64, &'static str> {
    let target = ec_elgamal_decrypt_point_checked(sk, c)?;
    bsgs_solve(&sk.public.curve, &target, m_max)
}

/// Convenience: decrypt with the default `m_max = 2³²`.
pub fn ec_elgamal_decrypt(
    sk: &EcElGamalPrivateKey,
    c: &EcElGamalCiphertext,
) -> Result<u64, &'static str> {
    ec_elgamal_decrypt_bounded(sk, c, 1u64 << 32)
}

/// Solve `m·G = target` for `m ∈ [0, m_max)` via baby-step giant-step.
fn bsgs_solve(curve: &CurveParams, target: &Point, m_max: u64) -> Result<u64, &'static str> {
    if m_max == 0 {
        return Err("m_max must be > 0");
    }
    // Take m_step = ⌈√m_max⌉ as the BSGS step.  Baby steps store
    // {j·G : j = 0..m_step}; giant steps walk target − i·(m_step)·G.
    let m_step = integer_sqrt_ceil(m_max);
    if m_step == 0 {
        return Err("m_max too small");
    }

    let g = curve.generator();
    let a = curve.a_fe();

    // Baby steps: build j → encoded(j·G).
    // We index by the affine x-coordinate (compressed) since
    // Point::Eq isn't implemented here uniformly.
    let mut table: HashMap<Vec<u8>, u64> = HashMap::with_capacity(m_step as usize);
    let mut p = Point::Infinity;
    for j in 0..=m_step {
        let key = point_key(&p);
        table.entry(key).or_insert(j);
        p = p.add(&g, &a);
    }

    // Giant step: P_step = m_step · G; we'll subtract i · P_step.
    let p_step = g.scalar_mul(&BigUint::from(m_step), &a);
    let neg_p_step = p_step.neg();

    let mut current = target.clone();
    for i in 0..=m_step {
        if let Some(&j) = table.get(&point_key(&current)) {
            let m = i.checked_mul(m_step).and_then(|x| x.checked_add(j));
            match m {
                Some(m) if m < m_max => return Ok(m),
                _ => {} // out of range; keep searching
            }
        }
        current = current.add(&neg_p_step, &a);
    }
    Err("plaintext not in [0, m_max); enlarge m_max or check ciphertext")
}

fn integer_sqrt_ceil(n: u64) -> u64 {
    if n <= 1 {
        return n;
    }
    let mut lo = 1u64;
    let mut hi = 1u64 << 32;
    while lo < hi {
        let mid = lo + (hi - lo) / 2;
        if mid >= n / mid && (n.is_multiple_of(mid) || mid > n / mid) {
            hi = mid;
        } else {
            lo = mid + 1;
        }
    }
    lo
}

fn validate_public_key(pk: &EcElGamalPublicKey) -> Result<(), &'static str> {
    if pk.curve.is_valid_public_point(&pk.q) {
        Ok(())
    } else {
        Err("invalid EC-ElGamal public key")
    }
}

fn validate_ciphertext(curve: &CurveParams, c: &EcElGamalCiphertext) -> Result<(), &'static str> {
    if curve.is_valid_public_point(&c.c1) && curve.is_on_curve(&c.c2) {
        Ok(())
    } else {
        Err("ciphertext points are not valid for this curve")
    }
}

/// Canonical byte serialisation of a point — used as a `HashMap` key
/// in BSGS.  Identity gets a distinguished prefix.
fn point_key(p: &Point) -> Vec<u8> {
    match p {
        Point::Infinity => vec![0u8],
        Point::Affine { x, y } => {
            let mut out = Vec::with_capacity(1 + 64);
            out.push(1u8);
            let mut xb = x.value.to_bytes_be();
            let mut yb = y.value.to_bytes_be();
            // Length-prefix to avoid ambiguous concat.
            out.extend_from_slice(&(xb.len() as u32).to_be_bytes());
            out.append(&mut xb);
            out.extend_from_slice(&(yb.len() as u32).to_be_bytes());
            out.append(&mut yb);
            out
        }
    }
}

// ── Homomorphic operations ───────────────────────────────────────────────────

/// **Additive homomorphism**:
/// `dec(ec_elgamal_add(c_a, c_b)) == m_a + m_b`.
pub fn ec_elgamal_add(
    pk: &EcElGamalPublicKey,
    ca: &EcElGamalCiphertext,
    cb: &EcElGamalCiphertext,
) -> EcElGamalCiphertext {
    ec_elgamal_add_checked(pk, ca, cb).expect("invalid EC-ElGamal ciphertext")
}

/// Checked homomorphic ciphertext addition.
pub fn ec_elgamal_add_checked(
    pk: &EcElGamalPublicKey,
    ca: &EcElGamalCiphertext,
    cb: &EcElGamalCiphertext,
) -> Result<EcElGamalCiphertext, &'static str> {
    validate_public_key(pk)?;
    validate_ciphertext(&pk.curve, ca)?;
    validate_ciphertext(&pk.curve, cb)?;
    let a = pk.curve.a_fe();
    Ok(EcElGamalCiphertext {
        c1: ca.c1.add(&cb.c1, &a),
        c2: ca.c2.add(&cb.c2, &a),
    })
}

/// Add a public scalar `m` to an encrypted value.
/// `dec(ec_elgamal_add_plain(c, m)) == m_existing + m`.
pub fn ec_elgamal_add_plain(
    pk: &EcElGamalPublicKey,
    c: &EcElGamalCiphertext,
    m: &BigUint,
) -> EcElGamalCiphertext {
    ec_elgamal_add_plain_checked(pk, c, m).expect("invalid EC-ElGamal ciphertext or plaintext")
}

/// Checked public plaintext addition.
pub fn ec_elgamal_add_plain_checked(
    pk: &EcElGamalPublicKey,
    c: &EcElGamalCiphertext,
    m: &BigUint,
) -> Result<EcElGamalCiphertext, &'static str> {
    validate_public_key(pk)?;
    validate_ciphertext(&pk.curve, c)?;
    if m >= &pk.curve.n {
        return Err("plaintext must be in [0, n)");
    }
    let g = pk.curve.generator();
    let a = pk.curve.a_fe();
    let m_g = g.scalar_mul(m, &a);
    Ok(EcElGamalCiphertext {
        c1: c.c1.clone(),
        c2: c.c2.add(&m_g, &a),
    })
}

/// Scalar multiplication of an encrypted plaintext by a public scalar.
/// `dec(ec_elgamal_mul_scalar(c, k)) == k · m`.
pub fn ec_elgamal_mul_scalar(
    pk: &EcElGamalPublicKey,
    c: &EcElGamalCiphertext,
    k: &BigUint,
) -> EcElGamalCiphertext {
    ec_elgamal_mul_scalar_checked(pk, c, k).expect("invalid EC-ElGamal ciphertext")
}

/// Checked ciphertext scalar multiplication.
pub fn ec_elgamal_mul_scalar_checked(
    pk: &EcElGamalPublicKey,
    c: &EcElGamalCiphertext,
    k: &BigUint,
) -> Result<EcElGamalCiphertext, &'static str> {
    validate_public_key(pk)?;
    validate_ciphertext(&pk.curve, c)?;
    let a = pk.curve.a_fe();
    let bits = pk.curve.order_bits();
    Ok(EcElGamalCiphertext {
        c1: c.c1.scalar_mul_ct(k, &a, bits),
        c2: c.c2.scalar_mul_ct(k, &a, bits),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn keypair() -> EcElGamalPrivateKey {
        ec_elgamal_keygen(CurveParams::p256())
    }

    #[test]
    fn keygen_produces_valid_keypair() {
        let sk = keypair();
        // Q must lie on the curve.
        assert!(sk.public.curve.is_on_curve(&sk.public.q));
        // Q = d·G
        let g = sk.public.curve.generator();
        let a = sk.public.curve.a_fe();
        let q_check = g.scalar_mul(&sk.d, &a);
        assert_eq!(point_key(&sk.public.q), point_key(&q_check));
    }

    #[test]
    #[ignore = "slow: 5 × P-256 affine scalar mul + 5 × BSGS; run with --ignored"]
    fn encrypt_decrypt_roundtrip_small() {
        let sk = keypair();
        for m in [0u64, 1, 7, 1000, 65_535] {
            let c = ec_elgamal_encrypt(&sk.public, &BigUint::from(m));
            let m2 = ec_elgamal_decrypt(&sk, &c).unwrap();
            assert_eq!(m, m2);
        }
    }

    /// Single-roundtrip smoke test (one encrypt, one decrypt) — kept
    /// in the default suite so regressions surface quickly.
    #[test]
    fn encrypt_decrypt_roundtrip_one() {
        let sk = keypair();
        let m = 42u64;
        let c = ec_elgamal_encrypt(&sk.public, &BigUint::from(m));
        let m2 = ec_elgamal_decrypt(&sk, &c).unwrap();
        assert_eq!(m, m2);
    }

    #[test]
    #[ignore = "slow: two P-256 encrypts + two BSGS decrypts; run with --ignored"]
    fn encrypt_is_probabilistic() {
        let sk = keypair();
        let m = BigUint::from(42u32);
        let c1 = ec_elgamal_encrypt(&sk.public, &m);
        let c2 = ec_elgamal_encrypt(&sk.public, &m);
        // Both decrypt to 42 but differ as ciphertexts.
        assert_ne!(point_key(&c1.c1), point_key(&c2.c1));
        assert_eq!(ec_elgamal_decrypt(&sk, &c1).unwrap(), 42);
        assert_eq!(ec_elgamal_decrypt(&sk, &c2).unwrap(), 42);
    }

    /// Headline property: `dec(c_a + c_b) = m_a + m_b`.
    #[test]
    #[ignore = "slow: P-256 affine scalar mul; run with --ignored"]
    fn homomorphic_add_two_ciphertexts() {
        let sk = keypair();
        let ma = 100u64;
        let mb = 200u64;
        let ca = ec_elgamal_encrypt(&sk.public, &BigUint::from(ma));
        let cb = ec_elgamal_encrypt(&sk.public, &BigUint::from(mb));
        let csum = ec_elgamal_add(&sk.public, &ca, &cb);
        assert_eq!(ec_elgamal_decrypt(&sk, &csum).unwrap(), 300);
    }

    /// Add a public plaintext.
    #[test]
    #[ignore = "slow: P-256 affine scalar mul; run with --ignored"]
    fn homomorphic_add_plain() {
        let sk = keypair();
        let m = 1000u64;
        let delta = 23u64;
        let c = ec_elgamal_encrypt(&sk.public, &BigUint::from(m));
        let c2 = ec_elgamal_add_plain(&sk.public, &c, &BigUint::from(delta));
        assert_eq!(ec_elgamal_decrypt(&sk, &c2).unwrap(), 1023);
    }

    /// Scalar multiplication.
    #[test]
    #[ignore = "slow: P-256 affine scalar mul; run with --ignored"]
    fn homomorphic_scalar_multiply() {
        let sk = keypair();
        let m = 6u64;
        let k = 7u64;
        let c = ec_elgamal_encrypt(&sk.public, &BigUint::from(m));
        let ck = ec_elgamal_mul_scalar(&sk.public, &c, &BigUint::from(k));
        assert_eq!(ec_elgamal_decrypt(&sk, &ck).unwrap(), 42);
    }

    /// **Vote tally** — each ballot is enc(0) or enc(1); tally the
    /// sum.  This is the canonical EC-ElGamal use case.
    #[test]
    #[ignore = "slow: 10 P-256 ballots + tally + BSGS decrypt; run with --ignored"]
    fn encrypted_vote_tally() {
        let sk = keypair();
        let pk = &sk.public;
        let ballots: Vec<u32> = vec![1, 0, 1, 1, 0, 1, 1, 0, 1, 1]; // 7 yes, 3 no
        let mut tally = ec_elgamal_encrypt(pk, &BigUint::zero());
        for v in &ballots {
            let c = ec_elgamal_encrypt(pk, &BigUint::from(*v));
            tally = ec_elgamal_add(pk, &tally, &c);
        }
        let result = ec_elgamal_decrypt(&sk, &tally).unwrap();
        assert_eq!(result, 7, "should tally to 7 yes votes");
    }

    /// Larger-range decryption: 2²⁰ ≈ 1 M.  Slower (~250 ms) but
    /// verifies BSGS scales correctly.
    #[test]
    #[ignore = "slow: 1M-entry BSGS table; run with --ignored"]
    fn decrypt_large_message_bounded() {
        let sk = keypair();
        let m = 999_999u64;
        let c = ec_elgamal_encrypt(&sk.public, &BigUint::from(m));
        let m2 = ec_elgamal_decrypt_bounded(&sk, &c, 1_000_000).unwrap();
        assert_eq!(m, m2);
    }

    /// Out-of-range message must fail BSGS — caller is told to expand.
    #[test]
    fn decrypt_out_of_range_fails() {
        let sk = keypair();
        let m = 100_000u64;
        let c = ec_elgamal_encrypt(&sk.public, &BigUint::from(m));
        // Bound = 1000 < m → must fail.
        assert!(ec_elgamal_decrypt_bounded(&sk, &c, 1000).is_err());
    }

    #[test]
    fn decrypt_with_wrong_key_fails() {
        let sk_a = keypair();
        let sk_b = keypair();
        let m = 7u64;
        let c = ec_elgamal_encrypt(&sk_a.public, &BigUint::from(m));
        // Decrypting with the wrong key yields a random point M'·G; the BSGS
        // search will overwhelmingly fail to find a small M' < 2³².
        let result = ec_elgamal_decrypt_bounded(&sk_b, &c, 1 << 16);
        assert!(result.is_err(), "wrong key must not decrypt");
    }

    #[test]
    fn checked_encrypt_rejects_invalid_public_key_and_plaintext_collision() {
        let sk = keypair();
        let mut bad_pk = sk.public.clone();
        bad_pk.q = Point::Infinity;
        assert!(ec_elgamal_encrypt_checked(&bad_pk, &BigUint::from(1u32)).is_err());
        assert!(ec_elgamal_encrypt_checked(&sk.public, &sk.public.curve.n).is_err());
    }

    #[test]
    fn decrypt_rejects_invalid_ciphertext_points() {
        let sk = keypair();
        let bad = EcElGamalCiphertext {
            c1: Point::Infinity,
            c2: sk.public.q.clone(),
        };
        assert!(ec_elgamal_decrypt_bounded(&sk, &bad, 10).is_err());
    }

    #[test]
    fn integer_sqrt_ceil_matches_small_cases() {
        assert_eq!(integer_sqrt_ceil(1), 1);
        assert_eq!(integer_sqrt_ceil(2), 2);
        assert_eq!(integer_sqrt_ceil(4), 2);
        assert_eq!(integer_sqrt_ceil(5), 3);
        assert_eq!(integer_sqrt_ceil(15), 4);
        assert_eq!(integer_sqrt_ceil(16), 4);
    }
}
