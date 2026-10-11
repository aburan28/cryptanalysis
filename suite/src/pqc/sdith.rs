//! **SDitH** — Syndrome Decoding in the Head
//! (Feneuil–Joux–Rivain 2022; NIST additional-signatures round 3).
//!
//! # The idea
//! The oldest hard problem in code-based cryptography: given a random
//! parity-check matrix `H ∈ F^{r×n}` and syndrome `y`, find a
//! **low-weight** vector `e` with `H·e = y` (NP-hard, studied since
//! McEliece 1978).  Classic Stern-protocol signatures from this
//! problem were huge; SDitH replaces Stern's permutation argument with
//! an **MPC-in-the-head** proof (see `pqc::mpcith`), shrinking
//! signatures to ~8 KB at NIST level 1.
//!
//! # The proof
//! The witness is `e` itself, additively shared among the parties.
//! - `H·e = y` is *linear*, so each party broadcasts its share of
//!   `H·eᵢ` (the leader subtracts `y`); the shares must sum to zero.
//! - The binary constraint `eⱼ ∈ {0,1}` is quadratic: `eⱼ² = eⱼ` in
//!   GF(256).  All `n` constraints are batched into a single
//!   dot-product check with verifier randomness `ε`:
//!   `⟨ε∘e, e⟩ = Σⱼ εⱼ·eⱼ` — the right side is linear in `e`, and the
//!   equality holds for all ε iff every `eⱼ` is 0 or 1.
//!
//! # Simplifications
//! Real SDitH additionally proves the exact Hamming weight `wt(e) = w`
//! via polynomial identities (a polynomial `Q` vanishing on the
//! support of `e`) — counting is not GF(256)-linear, so we omit it and
//! prove the *binary-solution* relation `H·e = y, e ∈ {0,1}ⁿ` only
//! (keygen still uses a weight-`w` secret; the syndrome length is
//! chosen so binary solutions are scarce).  Plus the engine-level
//! simplifications listed in `pqc::mpcith`.  Toy parameters, not
//! constant-time; see SECURITY.md.

use super::mpcith::{gf_mul, mpcith_prove, mpcith_verify, MpcRelation, MpcithProof, PartyView};
use crate::hash::sha3::shake256;
use crate::utils::random::random_bytes;

/// Code length.
pub const N_CODE: usize = 32;
/// Number of parity checks (syndrome length).
pub const R: usize = 24;
/// Secret weight used at keygen.
pub const W: usize = 8;

/// Public key: the code and the syndrome of the secret error vector.
#[derive(Clone)]
pub struct SdithPublicKey {
    /// Parity-check matrix, r×n over GF(256).
    pub h: Vec<Vec<u8>>,
    /// Syndrome y = H·e.
    pub y: Vec<u8>,
}

/// Secret key: the low-weight binary error vector.
#[derive(Clone)]
pub struct SdithSecretKey {
    pub e: Vec<u8>,
}

pub type SdithSignature = MpcithProof;

struct SdRelation {
    h: Vec<Vec<u8>>,
    y: Vec<u8>,
}

impl MpcRelation for SdRelation {
    fn witness_len(&self) -> usize {
        N_CODE
    }
    fn dot_len(&self) -> usize {
        N_CODE
    }
    fn eps_len(&self) -> usize {
        N_CODE
    }
    fn lin_len(&self) -> usize {
        R
    }
    fn party_compute(&self, wshare: &[u8], leader: bool, eps: &[u8]) -> PartyView {
        // Dot check ⟨ε∘e, e⟩ = Σ εⱼeⱼ  (batched binarity).
        let u: Vec<u8> = wshare
            .iter()
            .zip(eps)
            .map(|(&e, &x)| gf_mul(e, x))
            .collect();
        let v = wshare.to_vec();
        let t = u.iter().fold(0u8, |acc, &x| acc ^ x); // Σ εⱼeⱼ share (u already ε∘e)
                                                       // Linear check: shares of H·e − y.
        let mut lin: Vec<u8> = self
            .h
            .iter()
            .map(|row| {
                row.iter()
                    .zip(wshare)
                    .fold(0u8, |acc, (&hij, &ej)| acc ^ gf_mul(hij, ej))
            })
            .collect();
        if leader {
            for (l, &yi) in lin.iter_mut().zip(&self.y) {
                *l ^= yi;
            }
        }
        PartyView { u, v, t, lin }
    }
}

pub fn sdith_keygen() -> (SdithPublicKey, SdithSecretKey) {
    // Random parity-check matrix.
    let mut h = vec![vec![0u8; N_CODE]; R];
    for row in h.iter_mut() {
        random_bytes(row);
    }
    // Weight-w binary error vector.
    let mut e = vec![0u8; N_CODE];
    let mut placed = 0;
    while placed < W {
        let mut b = [0u8; 1];
        random_bytes(&mut b);
        let idx = b[0] as usize % N_CODE;
        if e[idx] == 0 {
            e[idx] = 1;
            placed += 1;
        }
    }
    let y: Vec<u8> = h
        .iter()
        .map(|row| {
            row.iter()
                .zip(&e)
                .fold(0u8, |acc, (&hij, &ej)| acc ^ gf_mul(hij, ej))
        })
        .collect();
    (SdithPublicKey { h, y }, SdithSecretKey { e })
}

/// Bind the public key and message into the proven statement.
fn statement(pk: &SdithPublicKey, msg: &[u8]) -> Vec<u8> {
    let mut input = b"SDitH-toy".to_vec();
    for row in &pk.h {
        input.extend_from_slice(row);
    }
    input.extend_from_slice(&pk.y);
    input.extend_from_slice(msg);
    shake256(&input, 32)
}

pub fn sdith_sign(pk: &SdithPublicKey, sk: &SdithSecretKey, msg: &[u8]) -> SdithSignature {
    let rel = SdRelation {
        h: pk.h.clone(),
        y: pk.y.clone(),
    };
    mpcith_prove(&rel, &sk.e, &statement(pk, msg))
}

pub fn sdith_verify(pk: &SdithPublicKey, msg: &[u8], sig: &SdithSignature) -> bool {
    let rel = SdRelation {
        h: pk.h.clone(),
        y: pk.y.clone(),
    };
    mpcith_verify(&rel, &statement(pk, msg), sig)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn keygen_satisfies_relation() {
        let (pk, sk) = sdith_keygen();
        assert_eq!(sk.e.iter().filter(|&&x| x == 1).count(), W);
        assert!(sk.e.iter().all(|&x| x <= 1));
        for (row, &yi) in pk.h.iter().zip(&pk.y) {
            let s = row
                .iter()
                .zip(&sk.e)
                .fold(0u8, |acc, (&h, &e)| acc ^ gf_mul(h, e));
            assert_eq!(s, yi);
        }
    }

    #[test]
    fn sign_verify_roundtrip() {
        let (pk, sk) = sdith_keygen();
        let msg = b"syndrome decoding in the head";
        let sig = sdith_sign(&pk, &sk, msg);
        assert!(sdith_verify(&pk, msg, &sig));
    }

    #[test]
    fn wrong_message_rejected() {
        let (pk, sk) = sdith_keygen();
        let sig = sdith_sign(&pk, &sk, b"one");
        assert!(!sdith_verify(&pk, b"two", &sig));
    }

    #[test]
    fn wrong_key_rejected() {
        let (pk_a, sk_a) = sdith_keygen();
        let (pk_b, _) = sdith_keygen();
        let sig = sdith_sign(&pk_a, &sk_a, b"msg");
        assert!(!sdith_verify(&pk_b, b"msg", &sig));
    }

    #[test]
    fn non_binary_witness_rejected() {
        // A witness solving H·e = y but with a non-binary coordinate
        // must fail the batched binarity check (w.h.p. over ε).
        let (pk, sk) = sdith_keygen();
        // Construct e' = e + delta where delta is in the kernel? Cheap
        // variant: sign with a corrupted witness directly.
        let mut bad = sk.e.clone();
        bad[0] ^= 0x17; // non-binary now
        let rel = SdRelation {
            h: pk.h.clone(),
            y: pk.y.clone(),
        };
        let msg = statement(&pk, b"msg");
        let sig = mpcith_prove(&rel, &bad, &msg);
        assert!(!mpcith_verify(&rel, &msg, &sig));
    }

    #[test]
    fn tampered_proof_rejected() {
        let (pk, sk) = sdith_keygen();
        let msg = b"tamper";
        let mut sig = sdith_sign(&pk, &sk, msg);
        sig.reps[0].hidden_v ^= 1;
        assert!(!sdith_verify(&pk, msg, &sig));
        let mut sig2 = sdith_sign(&pk, &sk, msg);
        sig2.reps[0].seeds[0][0] ^= 1;
        assert!(!sdith_verify(&pk, msg, &sig2));
    }
}
