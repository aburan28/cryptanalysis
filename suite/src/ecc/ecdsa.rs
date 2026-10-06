//! ECDSA — Elliptic Curve Digital Signature Algorithm (FIPS 186-4).
//!
//! # Sign
//! Given a private key d, curve order n, and message hash z:
//!   1. Choose a random nonce k ∈ [1, n-1].
//!   2. Compute (x₁, _) = k·G.
//!   3. r = x₁ mod n  (restart if r = 0).
//!   4. s = k⁻¹(z + r·d) mod n  (restart if s = 0).
//!      Output: (r, s).
//!
//! # Verify
//! Given public key Q, signature (r, s), and message hash z:
//!   1. Compute w = s⁻¹ mod n.
//!   2. u₁ = z·w mod n,  u₂ = r·w mod n.
//!   3. (x₁, _) = u₁·G + u₂·Q.
//!   4. Valid iff x₁ mod n = r.

use super::ct::scalar_mul_secret_blinded;
use super::curve::CurveParams;
use super::keys::{EccPrivateKey, EccPublicKey};
use super::point::Point;
use crate::hash::sha256::sha256;
use crate::kdf::hkdf::hmac_sha256;
use crate::utils::{mod_inverse, mod_inverse_prime_ct};
use num_bigint::BigUint;
use num_traits::{One, Zero};
/// An ECDSA signature pair (r, s).
#[derive(Clone, Debug)]
pub struct EcdsaSignature {
    pub r: BigUint,
    pub s: BigUint,
}

/// Sign `message` with `private_key` on `curve`.
///
/// The message is SHA-256 hashed before signing.
pub fn sign(message: &[u8], private_key: &EccPrivateKey, curve: &CurveParams) -> EcdsaSignature {
    sign_hash(&sha256(message), private_key, curve)
}

/// Sign a pre-computed 32-byte hash with `private_key`.
///
/// Nonces are derived deterministically per **RFC 6979** (HMAC-SHA-256
/// DRBG seeded from the private key and the message hash).  This eliminates
/// the catastrophic key-recovery failure mode that occurs when a randomly
/// sampled `k` is repeated, biased, or predictable.  Two signatures over
/// the same `(message, key)` are bit-for-bit identical.
pub fn sign_hash(hash: &[u8], private_key: &EccPrivateKey, curve: &CurveParams) -> EcdsaSignature {
    assert!(
        private_key.curve_name == curve.name
            && private_key.scalar >= BigUint::one()
            && private_key.scalar < curve.n,
        "ECDSA private scalar must be in [1, n) for the selected curve"
    );
    let z = hash_to_scalar(hash, &curve.n);

    let mut drbg = Rfc6979Drbg::new(&private_key.scalar, hash, &curve.n);

    loop {
        let k = drbg.next_k(&curve.n);
        // `scalar_mul_secret_blinded` routes through the curve's
        // projective Renes-Costello-Batina ladder (secp256k1: Alg
        // 7+9 for a=0; P-256: Alg 1+3 for general a) AND adds
        // Coron's scalar blinding: `k' = k + r · n` for a fresh
        // 64-bit random `r` per call.  Since `n · G = O`, `[k']G =
        // [k]G` and the (r, s) output is unchanged — but the bit
        // pattern driving the ladder is re-randomised every call,
        // defeating DPA / template attacks that combine ladder
        // traces across many signatures.  This is the standard
        // post-2020 ECDSA-implementation discipline; see SECURITY.md
        // § "scalar blinding."
        let kg = scalar_mul_secret_blinded(&curve.generator(), &k, curve);

        let x1 = match &kg {
            Point::Affine { x, .. } => x.value.clone(),
            Point::Infinity => continue,
        };

        let r = &x1 % &curve.n;
        if r.is_zero() {
            continue;
        }

        // s = k⁻¹ · (z + r·d) mod n
        let rd = (&r * &private_key.scalar) % &curve.n;
        let z_plus_rd = (&z + &rd) % &curve.n;
        // `k` is the per-message secret nonce.  The curve order `n` is
        // prime for both supported curves, so compute k⁻¹ via Fermat's
        // little theorem (a Montgomery-ladder mod_pow on a public bit
        // length) rather than via the variable-time extended Euclidean
        // algorithm in `mod_inverse`.
        let k_inv = match mod_inverse_prime_ct(&k, &curve.n) {
            Some(v) => v,
            None => continue,
        };
        let s = (&k_inv * &z_plus_rd) % &curve.n;
        if s.is_zero() {
            continue;
        }

        return EcdsaSignature { r, s };
    }
}

// ── RFC 6979 — Deterministic Usage of the DSA and ECDSA ──────────────────────
//
// Implements the HMAC-SHA-256 DRBG as specified in §3.2.
//
//   bits2int(h):     interpret `h` as big-endian, take leftmost 256 bits
//   bits2octets(h):  bits2int(h) mod q, encoded as 32 big-endian bytes
//   int2octets(x):   x encoded as 32 big-endian bytes
//
// Then:
//   V = 0x01 0x01 ... 0x01            (32 bytes)
//   K = 0x00 0x00 ... 0x00            (32 bytes)
//   K = HMAC_K(V || 0x00 || int2octets(d) || bits2octets(h))
//   V = HMAC_K(V)
//   K = HMAC_K(V || 0x01 || int2octets(d) || bits2octets(h))
//   V = HMAC_K(V)
//   loop:
//     T = empty
//     while len(T) < q-len: V = HMAC_K(V); T ||= V
//     k = bits2int(T)
//     if 1 ≤ k < q: yield k
//     else:        K = HMAC_K(V || 0x00); V = HMAC_K(V); continue

struct Rfc6979Drbg {
    k: [u8; 32],
    v: [u8; 32],
    qlen_bits: usize,
    rolen: usize,
}

impl Rfc6979Drbg {
    fn new(private_scalar: &BigUint, hash: &[u8], q: &BigUint) -> Self {
        let qlen_bits = q.bits() as usize;
        let rolen = qlen_bits.div_ceil(8);
        let d_bytes = int2octets(private_scalar, rolen);
        let h_bytes = bits2octets(hash, q, qlen_bits, rolen);

        let mut v = [0x01u8; 32];
        let mut k = [0x00u8; 32];

        // K = HMAC_K(V || 0x00 || d || h)
        let mut buf = Vec::with_capacity(32 + 1 + rolen * 2);
        buf.extend_from_slice(&v);
        buf.push(0x00);
        buf.extend_from_slice(&d_bytes);
        buf.extend_from_slice(&h_bytes);
        k = hmac_sha256(&k, &buf);

        // V = HMAC_K(V)
        v = hmac_sha256(&k, &v);

        // K = HMAC_K(V || 0x01 || d || h)
        buf.clear();
        buf.extend_from_slice(&v);
        buf.push(0x01);
        buf.extend_from_slice(&d_bytes);
        buf.extend_from_slice(&h_bytes);
        k = hmac_sha256(&k, &buf);

        // V = HMAC_K(V)
        v = hmac_sha256(&k, &v);

        Rfc6979Drbg {
            k,
            v,
            qlen_bits,
            rolen,
        }
    }

    fn next_k(&mut self, q: &BigUint) -> BigUint {
        loop {
            // T = HMAC blocks until we cover q-len.
            let mut t = Vec::with_capacity(self.rolen);
            while t.len() < self.rolen {
                self.v = hmac_sha256(&self.k, &self.v);
                t.extend_from_slice(&self.v);
            }
            let t_int = bits2int(&t, self.qlen_bits);
            if !t_int.is_zero() && &t_int < q {
                return t_int;
            }
            // Reseed: K = HMAC_K(V || 0x00); V = HMAC_K(V).
            let mut buf = Vec::with_capacity(33);
            buf.extend_from_slice(&self.v);
            buf.push(0x00);
            self.k = hmac_sha256(&self.k, &buf);
            self.v = hmac_sha256(&self.k, &self.v);
        }
    }
}

fn int2octets(x: &BigUint, rolen: usize) -> Vec<u8> {
    crate::utils::encoding::bigint_to_bytes_be_checked(x, rolen)
        .expect("scalar must fit in curve order length")
}

fn bits2int(h: &[u8], qlen_bits: usize) -> BigUint {
    let mut z = BigUint::from_bytes_be(h);
    let h_bits = h.len() * 8;
    if h_bits > qlen_bits {
        z >>= h_bits - qlen_bits;
    }
    z
}

fn bits2octets(h: &[u8], q: &BigUint, qlen_bits: usize, rolen: usize) -> Vec<u8> {
    let z1 = bits2int(h, qlen_bits);
    let z2 = if &z1 >= q { z1 - q } else { z1 };
    int2octets(&z2, rolen)
}

/// Verify that `sig` is a valid ECDSA signature over `message` for `public_key`.
pub fn verify(
    message: &[u8],
    public_key: &EccPublicKey,
    sig: &EcdsaSignature,
    curve: &CurveParams,
) -> bool {
    verify_hash(&sha256(message), public_key, sig, curve)
}

/// Verify a signature against a pre-computed hash.
pub fn verify_hash(
    hash: &[u8],
    public_key: &EccPublicKey,
    sig: &EcdsaSignature,
    curve: &CurveParams,
) -> bool {
    // Reject out-of-range values immediately.
    if sig.r.is_zero() || sig.r >= curve.n || sig.s.is_zero() || sig.s >= curve.n {
        return false;
    }
    if public_key.curve_name != curve.name || !curve.is_valid_public_point(&public_key.point) {
        return false;
    }

    let z = hash_to_scalar(hash, &curve.n);
    let a = curve.a_fe();

    let w = match mod_inverse(&sig.s, &curve.n) {
        Some(v) => v,
        None => return false,
    };

    let u1 = (&z * &w) % &curve.n;
    let u2 = (&sig.r * &w) % &curve.n;

    let point = curve
        .generator()
        .scalar_mul(&u1, &a)
        .add(&public_key.point.scalar_mul(&u2, &a), &a);

    match point {
        Point::Affine { x, .. } => (&x.value % &curve.n) == sig.r,
        Point::Infinity => false,
    }
}

/// Reduce a hash to a scalar in [0, n) by interpreting it as a big-endian integer.
fn hash_to_scalar(hash: &[u8], n: &BigUint) -> BigUint {
    BigUint::from_bytes_be(hash) % n
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ecc::{curve::CurveParams, keys::EccKeyPair};

    #[test]
    fn sign_and_verify_secp256k1() {
        let curve = CurveParams::secp256k1();
        let kp = EccKeyPair::generate(&curve);
        let msg = b"hello, elliptic curves!";
        let sig = sign(msg, &kp.private, &curve);
        assert!(verify(msg, &kp.public, &sig, &curve));
    }

    #[test]
    fn sign_and_verify_p256() {
        let curve = CurveParams::p256();
        let kp = EccKeyPair::generate(&curve);
        let msg = b"hello, elliptic curves!";
        let sig = sign(msg, &kp.private, &curve);
        assert!(verify(msg, &kp.public, &sig, &curve));
    }

    #[test]
    fn wrong_message_fails() {
        let curve = CurveParams::secp256k1();
        let kp = EccKeyPair::generate(&curve);
        let sig = sign(b"original", &kp.private, &curve);
        assert!(!verify(b"tampered", &kp.public, &sig, &curve));
    }

    #[test]
    fn wrong_key_fails() {
        let curve = CurveParams::secp256k1();
        let kp1 = EccKeyPair::generate(&curve);
        let kp2 = EccKeyPair::generate(&curve);
        let sig = sign(b"message", &kp1.private, &curve);
        assert!(!verify(b"message", &kp2.public, &sig, &curve));
    }

    #[test]
    fn p256_verify_external_signature() {
        // Cross-implementation KAT: signature produced by Python `cryptography`
        // (OpenSSL backend) on P-256 with the given private key and message.
        // Verifies our verification path against an independent implementation.
        let curve = CurveParams::p256();
        let priv_hex = "C9AFA9D845BA75166B5C215767B1D6934E50C3DB36E89B127B8A622B120F6721";
        let d = BigUint::parse_bytes(priv_hex.as_bytes(), 16).unwrap();
        let kp = EccKeyPair::from_private(d, &curve);

        let r = BigUint::parse_bytes(
            b"3f00b2a032fa0274eb2a3ac7a4fda16cbaf44de009166536df839187a0dcdb3d",
            16,
        )
        .unwrap();
        let s = BigUint::parse_bytes(
            b"880fbab6bd8fe10f572454e17ee0bb6cb7a6955aa9b8ee6b0b14b0029b582c1c",
            16,
        )
        .unwrap();
        let sig = EcdsaSignature { r, s };
        assert!(verify(b"attack at dawn", &kp.public, &sig, &curve));
        // Tampered message must fail
        assert!(!verify(b"attack at noon", &kp.public, &sig, &curve));
    }

    #[test]
    fn reject_zero_r_or_s() {
        let curve = CurveParams::p256();
        let kp = EccKeyPair::generate(&curve);
        let zero = EcdsaSignature {
            r: BigUint::from(0u32),
            s: BigUint::from(1u32),
        };
        assert!(!verify(b"msg", &kp.public, &zero, &curve));
        let zero2 = EcdsaSignature {
            r: BigUint::from(1u32),
            s: BigUint::from(0u32),
        };
        assert!(!verify(b"msg", &kp.public, &zero2, &curve));
    }

    #[test]
    fn rfc6979_p256_sample_kat() {
        // RFC 6979 Appendix A.2.5 — P-256 with private key
        //   x = C9AFA9D845BA75166B5C215767B1D6934E50C3DB36E89B127B8A622B120F6721
        // signing the SHA-256 hash of the ASCII string "sample".  Expected
        // values:
        //   k = A6E3C57DD01ABE90086538398355DD4C3B17AA873382B0F24D6129493D8AAD60
        //   r = EFD48B2AACB6A8FD1140DD9CD45E81D69D2C877B56AAF991C34D0EA84EAF3716
        //   s = F7CB1C942D657C41D436C7A1B6E29F65F3E900DBB9AFF4064DC4AB2F843ACDA8
        let curve = CurveParams::p256();
        let d = BigUint::parse_bytes(
            b"C9AFA9D845BA75166B5C215767B1D6934E50C3DB36E89B127B8A622B120F6721",
            16,
        )
        .unwrap();
        let kp = EccKeyPair::from_private(d, &curve);
        let sig = sign(b"sample", &kp.private, &curve);
        assert_eq!(
            format!("{:064x}", sig.r),
            "efd48b2aacb6a8fd1140dd9cd45e81d69d2c877b56aaf991c34d0ea84eaf3716",
        );
        assert_eq!(
            format!("{:064x}", sig.s),
            "f7cb1c942d657c41d436c7a1b6e29f65f3e900dbb9aff4064dc4ab2f843acda8",
        );
        assert!(verify(b"sample", &kp.public, &sig, &curve));
    }

    #[test]
    fn rfc6979_signatures_are_deterministic() {
        // Two signatures over the same (key, message) must be byte-identical.
        let curve = CurveParams::secp256k1();
        let kp = EccKeyPair::generate(&curve);
        let sig1 = sign(b"deterministic", &kp.private, &curve);
        let sig2 = sign(b"deterministic", &kp.private, &curve);
        assert_eq!(sig1.r, sig2.r);
        assert_eq!(sig1.s, sig2.s);
        // But different messages must produce different sigs (overwhelmingly).
        let sig3 = sign(b"different", &kp.private, &curve);
        assert_ne!(sig1.r, sig3.r);
    }

    #[test]
    fn reject_out_of_range_signature() {
        let curve = CurveParams::p256();
        let kp = EccKeyPair::generate(&curve);
        // r = n is out of range
        let bad = EcdsaSignature {
            r: curve.n.clone(),
            s: BigUint::from(1u32),
        };
        assert!(!verify(b"msg", &kp.public, &bad, &curve));
        let bad2 = EcdsaSignature {
            r: BigUint::from(1u32),
            s: curve.n.clone(),
        };
        assert!(!verify(b"msg", &kp.public, &bad2, &curve));
    }

    #[test]
    fn verify_rejects_invalid_public_key() {
        let curve = CurveParams::p256();
        let kp = EccKeyPair::generate(&curve);
        let sig = sign(b"msg", &kp.private, &curve);
        let bad_key = EccPublicKey {
            point: Point::Infinity,
            curve_name: curve.name.to_string(),
        };
        assert!(!verify(b"msg", &bad_key, &sig, &curve));
    }
}
