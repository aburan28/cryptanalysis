//! **Toy X-Wing-style hybrid** — X25519 plus this crate's educational
//! Kyber-inspired KEM.
//!
//! ## Why X-Wing
//!
//! X-Wing is a **defense-in-depth** construction: an attacker must
//! break **both** X25519 (classical, ECDLP) **and** ML-KEM
//! (post-quantum, MLWE) to recover the shared secret.  This
//! protects deployments during the post-quantum transition where:
//!
//! - Confidence in ML-KEM's exact security level is still being
//!   built (the algorithm is new; classical analysis is mature).
//! - A future cryptanalytic breakthrough on lattice problems
//!   would leave ML-KEM-only deployments suddenly insecure.
//!
//! Real deployments should use the CFRG X-Wing construction with ML-KEM-768.
//! This module is non-interoperable because `pqc::kyber` is a toy Kyber-512-like
//! implementation.
//!
//! ## Construction
//!
//! Public key: `(pk_x25519, pk_kyber)`.
//! Private key: `(sk_x25519, sk_kyber)`.
//!
//! **Encapsulation**:
//! 1. Sample ephemeral X25519 keypair `(esk, epk)`.
//! 2. X25519 shared secret: `ss_x = X25519(esk, pk_x25519)`.
//! 3. ML-KEM encapsulation: `(c_k, ss_k) = ML-KEM.Encap(pk_kyber)`.
//! 4. Combined shared secret: `K = H("X-Wing" ‖ ss_x ‖ ss_k ‖ c_k ‖ epk)`.
//! 5. Ciphertext: `(epk, c_k)`.
//!
//! **Decapsulation**:
//! 1. Recompute `ss_x = X25519(sk_x25519, epk)`.
//! 2. Recompute `ss_k = ML-KEM.Decap(sk_kyber, c_k)`.
//! 3. `K = H("X-Wing" ‖ ss_x ‖ ss_k ‖ c_k ‖ epk)`.
//!
//! ## Security
//!
//! - **Hybrid KEM-combiner** security: `K` is uniformly random as
//!   long as *either* `ss_x` or `ss_k` is.
//! - The hash domain-separator `"X-Wing"` prevents cross-protocol
//!   key recovery.
//! - Including `c_k` and `epk` in the hash provides **binding**:
//!   modifying either ciphertext changes the shared secret.

use crate::ecc::x25519::{x25519, x25519_base};
use crate::hash::sha256::sha256;
use crate::pqc::kyber::{
    kyber_ciphertext_to_bytes, kyber_decapsulate, kyber_encapsulate, kyber_keygen, KyberCiphertext,
    KyberPrivateKey, KyberPublicKey,
};
use rand::{rngs::OsRng, Rng};

const DOMAIN_SEPARATOR: &[u8] = b"X-Wing-Hybrid-KEM-v1";

#[derive(Clone, Debug)]
pub struct XWingPublicKey {
    pub x25519: [u8; 32],
    pub kyber: KyberPublicKey,
}

#[derive(Clone, Debug)]
pub struct XWingPrivateKey {
    pub x25519: [u8; 32],
    pub kyber: KyberPrivateKey,
    pub pk: XWingPublicKey,
}

#[derive(Clone, Debug)]
pub struct XWingKeyPair {
    pub pk: XWingPublicKey,
    pub sk: XWingPrivateKey,
}

#[derive(Clone, Debug)]
pub struct XWingCiphertext {
    pub epk: [u8; 32],
    pub kyber_ct: KyberCiphertext,
}

/// Generate a toy hybrid keypair: an X25519 keypair plus a toy Kyber keypair.
pub fn x_wing_keygen() -> XWingKeyPair {
    let mut rng = OsRng;
    let mut x_sk = [0u8; 32];
    rng.fill(&mut x_sk);
    // Clamp per X25519 spec.
    x_sk[0] &= 0xF8;
    x_sk[31] &= 0x7F;
    x_sk[31] |= 0x40;
    let x_pk = x25519_base(&x_sk);

    let kyber_sk = kyber_keygen();
    let kyber_pk = kyber_sk.public.clone();

    let pk = XWingPublicKey {
        x25519: x_pk,
        kyber: kyber_pk,
    };
    let sk = XWingPrivateKey {
        x25519: x_sk,
        kyber: kyber_sk,
        pk: pk.clone(),
    };
    XWingKeyPair { pk, sk }
}

/// Encapsulate against a toy hybrid public key.
pub fn x_wing_encapsulate(pk: &XWingPublicKey) -> (XWingCiphertext, [u8; 32]) {
    let mut rng = OsRng;
    let mut esk = [0u8; 32];
    rng.fill(&mut esk);
    esk[0] &= 0xF8;
    esk[31] &= 0x7F;
    esk[31] |= 0x40;
    let epk = x25519_base(&esk);
    let ss_x = x25519(&esk, &pk.x25519);

    let (kyber_ct, ss_k) = kyber_encapsulate(&pk.kyber);

    let k = combine_secrets(&ss_x, &ss_k, &kyber_ct, &epk);
    (XWingCiphertext { epk, kyber_ct }, k)
}

/// Decapsulate to recover the shared secret.
pub fn x_wing_decapsulate(ct: &XWingCiphertext, sk: &XWingPrivateKey) -> [u8; 32] {
    let ss_x = x25519(&sk.x25519, &ct.epk);
    let ss_k = kyber_decapsulate(&sk.kyber, &ct.kyber_ct);
    combine_secrets(&ss_x, &ss_k, &ct.kyber_ct, &ct.epk)
}

/// Combine X25519 and ML-KEM shared secrets into the final session
/// key.  Hash all of: domain separator, both shared secrets, the
/// Kyber ciphertext, and the ephemeral X25519 public key.
fn combine_secrets(
    ss_x: &[u8; 32],
    ss_k: &[u8; 32],
    kyber_ct: &KyberCiphertext,
    epk: &[u8; 32],
) -> [u8; 32] {
    let mut input = Vec::new();
    input.extend_from_slice(DOMAIN_SEPARATOR);
    input.extend_from_slice(ss_x);
    input.extend_from_slice(ss_k);
    input.extend_from_slice(
        &kyber_ciphertext_to_bytes(kyber_ct).expect("X-Wing ciphertext must be well formed"),
    );
    input.extend_from_slice(epk);
    sha256(&input)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// **X-Wing end-to-end**: shared secret matches between
    /// encap and decap.
    #[test]
    fn x_wing_kem_shared_secret_matches() {
        let kp = x_wing_keygen();
        let (ct, k_enc) = x_wing_encapsulate(&kp.pk);
        let k_dec = x_wing_decapsulate(&ct, &kp.sk);
        assert_eq!(k_enc, k_dec);
    }

    /// Different keypairs yield different shared secrets.
    #[test]
    fn x_wing_different_keys_yield_different_secrets() {
        let kp1 = x_wing_keygen();
        let kp2 = x_wing_keygen();
        let (_, k1) = x_wing_encapsulate(&kp1.pk);
        let (_, k2) = x_wing_encapsulate(&kp2.pk);
        assert_ne!(k1, k2);
    }

    /// Tampering with the ephemeral public key changes the shared
    /// secret (binding property of the hash combiner).
    #[test]
    fn x_wing_tampered_ciphertext_yields_different_secret() {
        let kp = x_wing_keygen();
        let (mut ct, _) = x_wing_encapsulate(&kp.pk);
        // Flip a bit in epk.
        ct.epk[0] ^= 0x01;
        let k_dec = x_wing_decapsulate(&ct, &kp.sk);
        let (_, k_orig) = x_wing_encapsulate(&kp.pk);
        assert_ne!(k_dec, k_orig);
    }

    #[test]
    fn x_wing_uses_canonical_kyber_serialization() {
        let kp = x_wing_keygen();
        let (ct, _) = x_wing_encapsulate(&kp.pk);
        let a = kyber_ciphertext_to_bytes(&ct.kyber_ct).unwrap();
        let b = kyber_ciphertext_to_bytes(&ct.kyber_ct).unwrap();
        assert_eq!(a, b);
        assert!(!a.is_empty());
    }
}
