//! **EC-KCDSA** — Korean Certificate-based Digital Signature Algorithm
//! over an elliptic curve (TTAK.KO-12.0011/R3 §6, also standardised
//! in ISO/IEC 14888-3 §6.7).
//!
//! EC-KCDSA is the elliptic-curve specialisation of KCDSA, the Korean
//! national signature scheme.  It is mandatory for Korean public-sector
//! electronic signatures (NPKI) and is the de-facto signature scheme
//! used inside Korean qualified PKI smart-cards.  South Korea
//! instantiates EC-KCDSA over standard SEC/NIST curves (most commonly
//! P-256).
//!
//! ## Curious design choice — inverse-keyed public point
//!
//! Unlike ECDSA or SM2, the public key is
//!
//! ```text
//!     Q = x⁻¹ · G    (private key x, generator G of order n)
//! ```
//!
//! i.e. the inverse of `x` in the scalar field is multiplied by `G`.
//! This means the signer never inverts `x` at sign time — but the
//! verifier never inverts anything either.  Both sign and verify run
//! only one fixed-base and one variable-base scalar multiplication.
//!
//! ## Sign(M, x)
//! 1. `z = H(cert_data || M)` — `cert_data` is application-defined
//!    (typically `H(Q ‖ identity-info)`).
//! 2. `k ← random in [1, n-1]`.
//! 3. `(W_x, _) = k·G`.
//! 4. `r = H(I2OSP(W_x))` — `r` is a hash output, not yet reduced.
//! 5. `e = (r ⊕ z) mod n` — XOR of byte strings, then interpreted as
//!    a big-endian integer reduced mod n.
//! 6. `s = x · (k − e) mod n`.  Restart if `s = 0`.
//! 7. Output `(r, s)`.
//!
//! ## Verify(M, (r, s), Q)
//! 1. Reject if `s ∉ [1, n-1]` or `r` has the wrong length.
//! 2. `z = H(cert_data || M)`.
//! 3. `e = (r ⊕ z) mod n`.
//! 4. `(W'_x, _) = s·Q + e·G`.
//! 5. Accept iff `r == H(I2OSP(W'_x))`.
//!
//! ### Correctness
//!
//! ```text
//!     s·Q + e·G  =  x · (k − e) · x⁻¹ · G  +  e · G
//!                =  (k − e) · G  +  e · G
//!                =  k · G  =  W
//! ```
//! so the verifier reproduces the same `W_x` the signer hashed.

use super::curve::CurveParams;
use super::point::Point;
use crate::hash::sha256::sha256;
use crate::utils::{mod_inverse, random::random_scalar};
use num_bigint::BigUint;
use num_traits::Zero;

/// An EC-KCDSA signature pair.
///
/// `r` is held as the raw hash output (typically 32 bytes for SHA-256)
/// rather than as a `BigUint` because the verifier compares the full
/// hash bit-string to detect tampering.  `s` is an integer mod `n`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EcKcdsaSignature {
    pub r: Vec<u8>,
    pub s: BigUint,
}

/// Hash function used by EC-KCDSA.  The Korean standard parameterises
/// this; we wire SHA-256 because that is the choice mandated by the
/// Korean qualified-PKI profile (CC-EC-KCDSA-SHA256).
fn h(msg: &[u8]) -> Vec<u8> {
    sha256(msg).to_vec()
}

/// Derive the EC-KCDSA public point `Q = x⁻¹ · G` for a private scalar
/// `x ∈ [1, n-1]`.  Returns `None` if `x` is zero or not coprime to
/// `n` (the latter cannot happen when `n` is prime, but we guard for
/// the degenerate case anyway).
pub fn public_key_from_private(x: &BigUint, curve: &CurveParams) -> Option<Point> {
    if x.is_zero() {
        return None;
    }
    let x_inv = mod_inverse(x, &curve.n)?;
    let a = curve.a_fe();
    Some(
        curve
            .generator()
            .scalar_mul_ct(&x_inv, &a, curve.order_bits()),
    )
}

fn z_input(cert_data: &[u8], msg: &[u8]) -> Vec<u8> {
    let mut buf = Vec::with_capacity(cert_data.len() + msg.len());
    buf.extend_from_slice(cert_data);
    buf.extend_from_slice(msg);
    buf
}

fn n_byte_len(curve: &CurveParams) -> usize {
    (curve.n.bits() as usize).div_ceil(8)
}

/// **Sign** `msg` with private key `x` under signer identity
/// `cert_data` (any byte string — the standard prescribes
/// `H(Q ‖ identifying-info)`, but the choice is an application policy).
pub fn sign(
    msg: &[u8],
    x: &BigUint,
    cert_data: &[u8],
    curve: &CurveParams,
) -> Result<EcKcdsaSignature, &'static str> {
    if (x % &curve.n).is_zero() {
        return Err("invalid EC-KCDSA private key");
    }

    let z = h(&z_input(cert_data, msg));
    let nl = n_byte_len(curve);
    let a = curve.a_fe();

    loop {
        let k = random_scalar(&curve.n);
        if k.is_zero() {
            continue;
        }
        let kg = curve.generator().scalar_mul_ct(&k, &a, curve.order_bits());
        let wx = match &kg {
            Point::Affine { x, .. } => x.value.clone(),
            Point::Infinity => continue,
        };
        let wx_bytes = crate::utils::encoding::bigint_to_bytes_be(&wx, nl);
        let r = h(&wx_bytes);
        // e = (r XOR z) mod n.  r and z are both H output length; pad
        // with leading zero bytes if H output is shorter than n_bits.
        let e = xor_reduce_mod_n(&r, &z, &curve.n);
        // s = x·(k − e) mod n
        let k_minus_e = (&k + &curve.n - &e) % &curve.n;
        let s = (x * &k_minus_e) % &curve.n;
        if s.is_zero() {
            continue;
        }
        return Ok(EcKcdsaSignature { r, s });
    }
}

/// **Verify** `(r, s)` against `msg`, signer identity `cert_data`, and
/// public key `q`.  Returns `true` iff the signature is well-formed
/// and reproduces the hash chain.
pub fn verify(
    msg: &[u8],
    sig: &EcKcdsaSignature,
    q: &Point,
    cert_data: &[u8],
    curve: &CurveParams,
) -> bool {
    if !curve.is_valid_public_point(q) {
        return false;
    }

    if sig.s.is_zero() || sig.s >= curve.n {
        return false;
    }
    let z = h(&z_input(cert_data, msg));
    if sig.r.len() != z.len() {
        return false;
    }
    let e = xor_reduce_mod_n(&sig.r, &z, &curve.n);

    let a = curve.a_fe();
    let sq = q.scalar_mul(&sig.s, &a);
    let eg = curve.generator().scalar_mul(&e, &a);
    let w_prime = sq.add(&eg, &a);
    let w_x = match w_prime {
        Point::Affine { x, .. } => x.value,
        Point::Infinity => return false,
    };
    let nl = n_byte_len(curve);
    let wx_bytes = crate::utils::encoding::bigint_to_bytes_be(&w_x, nl);
    let r_prime = h(&wx_bytes);

    // Constant-time tag compare.
    if r_prime.len() != sig.r.len() {
        return false;
    }
    let mut diff = 0u8;
    for i in 0..r_prime.len() {
        diff |= r_prime[i] ^ sig.r[i];
    }
    diff == 0
}

fn xor_reduce_mod_n(a: &[u8], b: &[u8], n: &BigUint) -> BigUint {
    assert_eq!(a.len(), b.len());
    let xored: Vec<u8> = a.iter().zip(b.iter()).map(|(x, y)| x ^ y).collect();
    BigUint::from_bytes_be(&xored) % n
}

#[cfg(test)]
mod tests {
    use super::*;

    /// **Sign / verify roundtrip on P-256** — the most common Korean
    /// PKI deployment.
    #[test]
    fn ec_kcdsa_p256_roundtrip() {
        let curve = CurveParams::p256();
        let x = BigUint::parse_bytes(
            b"C9AFA9D845BA75166B5C215767B1D6934E50C3DB36E89B127B8A622B120F6721",
            16,
        )
        .unwrap();
        let q = public_key_from_private(&x, &curve).expect("key derivation");
        let cert_data = b"signer-info";
        let msg = b"hello, EC-KCDSA";
        let sig = sign(msg, &x, cert_data, &curve).expect("valid signing key");
        assert!(verify(msg, &sig, &q, cert_data, &curve));
    }

    /// **Wrong-message rejection**.
    #[test]
    fn ec_kcdsa_wrong_message_fails() {
        let curve = CurveParams::p256();
        let x = BigUint::from(0xC0FFEEu32);
        let q = public_key_from_private(&x, &curve).unwrap();
        let sig = sign(b"original", &x, b"cert", &curve).expect("valid signing key");
        assert!(!verify(b"tampered", &sig, &q, b"cert", &curve));
    }

    /// **Wrong-cert rejection**: the same message under a different
    /// signer-info hashes differently and must fail verification.
    #[test]
    fn ec_kcdsa_wrong_cert_fails() {
        let curve = CurveParams::p256();
        let x = BigUint::from(0xDEADBEEFu64);
        let q = public_key_from_private(&x, &curve).unwrap();
        let sig = sign(b"msg", &x, b"alice", &curve).expect("valid signing key");
        assert!(!verify(b"msg", &sig, &q, b"bob", &curve));
    }

    /// **Wrong-key rejection**: signature under one key does not
    /// verify under another.
    #[test]
    fn ec_kcdsa_wrong_key_fails() {
        let curve = CurveParams::p256();
        let x1 = BigUint::from(0x11111111u64);
        let x2 = BigUint::from(0x22222222u64);
        let q1 = public_key_from_private(&x1, &curve).unwrap();
        let q2 = public_key_from_private(&x2, &curve).unwrap();
        let sig = sign(b"msg", &x1, b"cert", &curve).expect("valid signing key");
        assert!(verify(b"msg", &sig, &q1, b"cert", &curve));
        assert!(!verify(b"msg", &sig, &q2, b"cert", &curve));
    }

    /// **Sign / verify roundtrip on secp256k1**: same algorithm,
    /// different curve.  Catches any accidental curve-baked-in
    /// assumption.
    #[test]
    fn ec_kcdsa_secp256k1_roundtrip() {
        let curve = CurveParams::secp256k1();
        let x = BigUint::from(0xA5u64);
        let q = public_key_from_private(&x, &curve).unwrap();
        let sig = sign(b"msg", &x, b"cert", &curve).expect("valid signing key");
        assert!(verify(b"msg", &sig, &q, b"cert", &curve));
    }

    #[test]
    fn ec_kcdsa_sign_rejects_zero_private_key() {
        let curve = CurveParams::p256();
        assert_eq!(
            sign(b"msg", &BigUint::zero(), b"cert", &curve),
            Err("invalid EC-KCDSA private key")
        );
    }

    #[test]
    fn ec_kcdsa_sign_rejects_order_multiple_private_key() {
        let curve = CurveParams::p256();
        assert_eq!(
            sign(b"msg", &curve.n, b"cert", &curve),
            Err("invalid EC-KCDSA private key")
        );
    }

    /// **Reject out-of-range s**.
    #[test]
    fn ec_kcdsa_reject_out_of_range_s() {
        let curve = CurveParams::p256();
        let x = BigUint::from(123u32);
        let q = public_key_from_private(&x, &curve).unwrap();
        let bad = EcKcdsaSignature {
            r: vec![0u8; 32],
            s: BigUint::zero(),
        };
        assert!(!verify(b"msg", &bad, &q, b"cert", &curve));
        let bad2 = EcKcdsaSignature {
            r: vec![0u8; 32],
            s: curve.n.clone(),
        };
        assert!(!verify(b"msg", &bad2, &q, b"cert", &curve));
    }

    /// **Verifier checks `r` length**: a mis-sized `r` byte string is
    /// structurally invalid.
    #[test]
    fn ec_kcdsa_reject_wrong_r_length() {
        let curve = CurveParams::p256();
        let x = BigUint::from(42u32);
        let q = public_key_from_private(&x, &curve).unwrap();
        let bad = EcKcdsaSignature {
            r: vec![0u8; 16], // wrong length (SHA-256 is 32)
            s: BigUint::from(1u32),
        };
        assert!(!verify(b"msg", &bad, &q, b"cert", &curve));
    }
}
