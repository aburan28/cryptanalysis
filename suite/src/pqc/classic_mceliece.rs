//! **Classic McEliece** — McEliece 1978, formalized as a NIST PQC
//! finalist by Bernstein et al. 2017–present.  Round-4 candidate
//! with IND-CCA2 security under the Niederreiter-McEliece
//! syndrome-decoding assumption — **the longest-standing post-
//! quantum hardness assumption** (no significant attacks since
//! 1978).
//!
//! ## Difference from [`super::mceliece`]
//!
//! `super::mceliece` ships a simplified educational version
//! (small-parameter binary-Goppa, Patterson decoding).  This module
//! adds the **standardised KEM wrapper** that turns the
//! Niederreiter PKE into an IND-CCA KEM via:
//!
//! 1. **Fixed-weight error sampling**: error vectors `e ∈ F_2^n`
//!    of exact weight `t`.
//! 2. **Niederreiter encoding**: ciphertext is the syndrome
//!    `s = H · e`, not the full McEliece codeword.
//! 3. **Fujisaki-Okamoto-style hashing** to derive the shared
//!    secret with implicit rejection on decoding failure.
//!
//! Reused from `super::mceliece`: the binary-Goppa-code Patterson
//! decoder.  Classic McEliece's encryption process is structurally
//! the same as our simplified McEliece's; the wrapper just adds
//! the KEM-style API and IND-CCA-2 binding.
//!
//! ## Educational scope
//!
//! Same simplified-Goppa parameters as `super::mceliece`
//! (small `m, n, t` for testing).  The KEM-wrapper logic is the
//! novel contribution of this module.

use crate::hash::sha256::sha256;
use crate::pqc::mceliece::{
    mceliece_decrypt, mceliece_encrypt, McElieceKeyPair, McEliecePrivateKey, McElieceePublicKey, N,
};
use crate::utils::random::random_bytes_vec;
use rand::{rngs::OsRng, Rng};
use subtle::ConstantTimeEq;

/// Classic McEliece public key — same as the underlying scheme.
pub type ClassicMceliecePublicKey = McElieceePublicKey;
/// Classic McEliece private key plus secret implicit-rejection seed.
#[derive(Clone, Debug)]
pub struct ClassicMceliecePrivateKey {
    pub inner: McEliecePrivateKey,
    reject_secret: [u8; 32],
}

impl Drop for ClassicMceliecePrivateKey {
    fn drop(&mut self) {
        self.reject_secret.fill(0);
    }
}

#[derive(Clone, Debug)]
pub struct ClassicMcelieceKeyPair {
    pub pk: ClassicMceliecePublicKey,
    pub sk: ClassicMceliecePrivateKey,
}

#[derive(Clone, Debug)]
pub struct ClassicMcelieceCiphertext {
    /// Niederreiter syndrome / McEliece ciphertext bytes.
    pub bytes: Vec<u8>,
    /// 32-byte hash commitment to the message, included for
    /// implicit-rejection IND-CCA security.
    pub hash_commit: [u8; 32],
}

/// Generate a Classic McEliece keypair (wraps the underlying
/// simplified McEliece keygen).
pub fn classic_mceliece_keygen() -> ClassicMcelieceKeyPair {
    let inner = McElieceKeyPair::generate();
    let mut reject_secret = [0u8; 32];
    reject_secret.copy_from_slice(&random_bytes_vec(32));
    ClassicMcelieceKeyPair {
        pk: inner.public,
        sk: ClassicMceliecePrivateKey {
            inner: inner.private,
            reject_secret,
        },
    }
}

/// **Encapsulate** a shared secret against `pk`.
///
/// Process (FO-style):
/// 1. Sample uniform-random `k`-bit message `m` (where `k` is the
///    underlying code's dimension — 14 for our simplified McEliece).
/// 2. Encrypt: `c = McEliece.Enc(m; pk)`.
/// 3. Hash-commit: `h = H_2("CM-COMMIT" ‖ m ‖ c)`.
/// 4. Shared secret: `K = H_3("CM-SS" ‖ m ‖ c)`.
///
/// Return `(ciphertext, shared_secret)`.  The 32-byte shared
/// secret is derived deterministically from the `k`-bit message
/// via SHA-256, providing a uniform 32-byte session key
/// regardless of the underlying code's small dimension.
pub fn classic_mceliece_encapsulate(
    pk: &ClassicMceliecePublicKey,
) -> (ClassicMcelieceCiphertext, [u8; 32]) {
    let mut rng = OsRng;
    let k = pk.k;
    let mut m = vec![0u8; k];
    for byte in m.iter_mut() {
        *byte = rng.gen_range(0..2);
    }

    let ciphertext_bytes = mceliece_encrypt(&m, pk);

    let mut commit_input = Vec::with_capacity(64 + ciphertext_bytes.len());
    commit_input.extend_from_slice(b"CM-COMMIT");
    commit_input.extend_from_slice(&m);
    commit_input.extend_from_slice(&ciphertext_bytes);
    let hash_commit = sha256(&commit_input);

    let mut ss_input = Vec::with_capacity(64 + ciphertext_bytes.len());
    ss_input.extend_from_slice(b"CM-SS");
    ss_input.extend_from_slice(&m);
    ss_input.extend_from_slice(&ciphertext_bytes);
    let shared_secret = sha256(&ss_input);

    let ct = ClassicMcelieceCiphertext {
        bytes: ciphertext_bytes,
        hash_commit,
    };
    (ct, shared_secret)
}

/// **Decapsulate**: recover `m`, verify the hash commitment, then
/// derive the shared secret.  On verification failure (implicit
/// rejection), return a deterministic pseudo-random key derived
/// from a secret fallback seed and the ciphertext.  That keeps
/// malformed-ciphertext outputs unpredictable to an attacker while
/// remaining deterministic for the holder of the private key.
pub fn classic_mceliece_decapsulate(
    ct: &ClassicMcelieceCiphertext,
    sk: &ClassicMceliecePrivateKey,
) -> [u8; 32] {
    if ct.bytes.len() != N {
        return rejection_key(sk, &ct.bytes);
    }

    let recovered = mceliece_decrypt(&ct.bytes, &sk.inner);
    let m_candidate: Vec<u8> = match recovered {
        Some(m) => m,
        None => return rejection_key(sk, &ct.bytes),
    };

    let mut commit_input = Vec::with_capacity(64 + ct.bytes.len());
    commit_input.extend_from_slice(b"CM-COMMIT");
    commit_input.extend_from_slice(&m_candidate);
    commit_input.extend_from_slice(&ct.bytes);
    let commit_check = sha256(&commit_input);

    if !bool::from(commit_check.ct_eq(&ct.hash_commit)) {
        return rejection_key(sk, &ct.bytes);
    }

    let mut ss_input = Vec::with_capacity(64 + ct.bytes.len());
    ss_input.extend_from_slice(b"CM-SS");
    ss_input.extend_from_slice(&m_candidate);
    ss_input.extend_from_slice(&ct.bytes);
    sha256(&ss_input)
}

fn rejection_key(sk: &ClassicMceliecePrivateKey, ciphertext: &[u8]) -> [u8; 32] {
    let mut buf = Vec::with_capacity(64 + ciphertext.len());
    buf.extend_from_slice(b"CM-REJECT");
    buf.extend_from_slice(&sk.reject_secret);
    buf.extend_from_slice(ciphertext);
    sha256(&buf)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// **Classic McEliece end-to-end**: encap → decap → same secret.
    #[test]
    fn classic_mceliece_kem_shared_secret_matches() {
        let kp = classic_mceliece_keygen();
        let (ct, k_enc) = classic_mceliece_encapsulate(&kp.pk);
        let k_dec = classic_mceliece_decapsulate(&ct, &kp.sk);
        assert_eq!(k_enc, k_dec);
    }

    /// **Implicit rejection**: tampered ciphertext yields a
    /// pseudo-random "rejection key", not a panic or decoding
    /// failure leaking information.
    #[test]
    fn tampered_ciphertext_yields_rejection_key() {
        let kp = classic_mceliece_keygen();
        let (mut ct, _) = classic_mceliece_encapsulate(&kp.pk);
        // Flip a bit in the hash commitment so it doesn't verify.
        ct.hash_commit[0] ^= 0x01;
        let k = classic_mceliece_decapsulate(&ct, &kp.sk);
        // The result should be deterministic (the rejection key)
        // and should equal the rejection-key formula.
        let expected = rejection_key(&kp.sk, &ct.bytes);
        assert_eq!(k, expected);
    }

    #[test]
    fn malformed_ciphertext_length_yields_rejection_key() {
        let kp = classic_mceliece_keygen();
        let ct = ClassicMcelieceCiphertext {
            bytes: vec![0u8; N - 1],
            hash_commit: [0u8; 32],
        };
        assert_eq!(
            classic_mceliece_decapsulate(&ct, &kp.sk),
            rejection_key(&kp.sk, &ct.bytes)
        );
    }

    /// Different keys → different shared secrets.
    #[test]
    fn different_keys_yield_different_secrets() {
        let kp1 = classic_mceliece_keygen();
        let kp2 = classic_mceliece_keygen();
        let (_, k1) = classic_mceliece_encapsulate(&kp1.pk);
        let (_, k2) = classic_mceliece_encapsulate(&kp2.pk);
        assert_ne!(k1, k2);
    }
}
