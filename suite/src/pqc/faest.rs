//! **FAEST** — signatures from AES in the head
//! (Baum–Braun–Delpech–Dobraunig–Kales–Orlt–Radi–Zaverucha 2022; NIST
//! additional-signatures round 3).
//!
//! # The idea — the most conservative assumption available
//! Every other signature here needs a *new* hardness assumption
//! (lattices, codes, isogenies, MQ).  FAEST needs only that **AES is a
//! one-way function**: the public key is `(x, y)` with `y = AES_k(x)`
//! for a secret key `k`, and a signature proves knowledge of `k`
//! without revealing it.  If AES is secure — which we bet on for all
//! symmetric crypto anyway — FAEST is secure.  No number theory, no new
//! assumption.
//!
//! # The proof (MPC-in-the-head)
//! Prove knowledge of an AES key mapping a public plaintext to a public
//! ciphertext.  AES is linear over GF(2) *except* for the 16 S-boxes
//! per round, and every S-box is the field inversion `y = x⁻¹` in
//! GF(256) (with 0 ↦ 0), which is captured by the single algebraic
//! relation
//!
//! ```text
//! x · y = 1        (for x ≠ 0).
//! ```
//!
//! The witness is the key together with every S-box **output** along
//! the AES computation (the "extended witness").  Given those, the
//! entire cipher is a *linear* function of the witness, so each party
//! recomputes it locally; the only thing to prove is that each
//! (input, output) S-box pair multiplies to 1.  All S-box relations are
//! batched under verifier randomness `ε` into one sacrificed-triple
//! dot-product check (`pqc::mpcith`): `⟨ε∘s_in, s_out⟩ = Σ_j ε_j`.
//!
//! # Educational rendition
//! Real FAEST proves the full AES-128 circuit (10 rounds, 160 S-boxes,
//! ~1.6 KB extended witness) via VOLE-in-the-head.  Proving a genuine
//! AES round would drag the whole key schedule and MixColumns into the
//! linear layer; to keep this module about the *FAEST technique* rather
//! than an AES reimplementation, we prove the essential S-box core: a
//! **one-round substitution–permutation** one-way function
//!
//! ```text
//! F_k(x) = L( SBOX( x ⊕ k ) ) ⊕ k,
//! ```
//!
//! with `L` a fixed public invertible GF(256)-linear map over the
//! 16-byte state and `SBOX` the AES inversion S-box.  The witness is
//! `(k, s_out)` where `s_out[j] = (x[j] ⊕ k[j])⁻¹`; the SP structure,
//! the extended witness, and the batched `x·y = 1` proof are exactly as
//! in FAEST.  Plus the engine simplifications in `pqc::mpcith`.  Toy,
//! not constant-time; see SECURITY.md.

use super::mpcith::{
    gf_inv, gf_mul, mpcith_prove, mpcith_verify, MpcRelation, MpcithProof, PartyView,
};
use crate::hash::sha3::shake256;
use crate::utils::random::random_bytes;

/// State size in bytes (as AES).
pub const BLOCK: usize = 16;
/// Extended witness = key ‖ S-box outputs.
pub const WITNESS_LEN: usize = 2 * BLOCK;

/// Public key: plaintext, ciphertext, and the public linear layer.
#[derive(Clone)]
pub struct FaestPublicKey {
    pub x: Vec<u8>,        // plaintext (BLOCK bytes)
    pub y: Vec<u8>,        // ciphertext = F_k(x)
    pub lin: Vec<Vec<u8>>, // BLOCK×BLOCK invertible GF(256) matrix L
}

#[derive(Clone)]
pub struct FaestSecretKey {
    pub k: Vec<u8>,
}

pub type FaestSignature = MpcithProof;

/// The AES inversion S-box relation, applied byte-wise: 0 ↦ 0.
fn sbox(a: u8) -> u8 {
    if a == 0 {
        0
    } else {
        gf_inv(a)
    }
}

fn apply_linear(lin: &[Vec<u8>], v: &[u8]) -> Vec<u8> {
    (0..BLOCK)
        .map(|i| {
            lin[i]
                .iter()
                .zip(v)
                .fold(0u8, |acc, (&lij, &vj)| acc ^ gf_mul(lij, vj))
        })
        .collect()
}

/// F_k(x) = L(SBOX(x ⊕ k)) ⊕ k.
fn one_way(pk_lin: &[Vec<u8>], x: &[u8], k: &[u8]) -> Vec<u8> {
    let s: Vec<u8> = (0..BLOCK).map(|j| sbox(x[j] ^ k[j])).collect();
    let l = apply_linear(pk_lin, &s);
    (0..BLOCK).map(|j| l[j] ^ k[j]).collect()
}

/// Random invertible GF(256) matrix and (unused) — we only need forward.
fn random_invertible_linear() -> Vec<Vec<u8>> {
    loop {
        let mut m = vec![vec![0u8; BLOCK]; BLOCK];
        for row in m.iter_mut() {
            random_bytes(row);
        }
        if gf_matrix_invertible(&m) {
            return m;
        }
    }
}

fn gf_matrix_invertible(a: &[Vec<u8>]) -> bool {
    let n = a.len();
    let mut m: Vec<Vec<u8>> = a.to_vec();
    for col in 0..n {
        let Some(pivot) = (col..n).find(|&r| m[r][col] != 0) else {
            return false;
        };
        m.swap(col, pivot);
        let inv = gf_inv(m[col][col]);
        for j in 0..n {
            m[col][j] = gf_mul(m[col][j], inv);
        }
        for r in 0..n {
            if r != col && m[r][col] != 0 {
                let f = m[r][col];
                for j in 0..n {
                    m[r][j] ^= gf_mul(f, m[col][j]);
                }
            }
        }
    }
    true
}

struct AesRelation {
    x: Vec<u8>,
    y: Vec<u8>,
    lin: Vec<Vec<u8>>,
}

impl MpcRelation for AesRelation {
    fn witness_len(&self) -> usize {
        WITNESS_LEN
    }
    fn dot_len(&self) -> usize {
        BLOCK
    }
    fn eps_len(&self) -> usize {
        BLOCK
    }
    fn lin_len(&self) -> usize {
        BLOCK
    }
    fn party_compute(&self, wshare: &[u8], leader: bool, eps: &[u8]) -> PartyView {
        // Witness = k ‖ s_out.  S-box inputs are s_in[j] = x[j] ⊕ k[j];
        // x is public, so only the leader adds it.
        let k = &wshare[..BLOCK];
        let s_out = &wshare[BLOCK..];
        let mut s_in = k.to_vec();
        if leader {
            for j in 0..BLOCK {
                s_in[j] ^= self.x[j];
            }
        }
        // Dot check: ⟨ε ∘ s_in, s_out⟩ = Σ_j ε_j   (each s_in·s_out = 1).
        let u: Vec<u8> = (0..BLOCK).map(|j| gf_mul(eps[j], s_in[j])).collect();
        let v = s_out.to_vec();
        // Target Σ_j ε_j·1 is a public constant → leader's share only.
        let t = if leader {
            eps.iter().fold(0u8, |a, &e| a ^ e)
        } else {
            0
        };

        // Linear check: reconstructed ciphertext must equal y.
        // L(s_out) ⊕ k, compared to y (public → leader subtracts).
        let l = apply_linear(&self.lin, s_out);
        let mut lin: Vec<u8> = (0..BLOCK).map(|j| l[j] ^ k[j]).collect();
        if leader {
            for j in 0..BLOCK {
                lin[j] ^= self.y[j];
            }
        }
        PartyView { u, v, t, lin }
    }
}

pub fn faest_keygen() -> (FaestPublicKey, FaestSecretKey) {
    let mut k = vec![0u8; BLOCK];
    let mut x = vec![0u8; BLOCK];
    random_bytes(&mut k);
    random_bytes(&mut x);
    // Avoid zero S-box inputs so the x·y = 1 relation is exact for every
    // byte (0⁻¹ = 0 breaks it); resample plaintext bytes that collide.
    for j in 0..BLOCK {
        while x[j] ^ k[j] == 0 {
            let mut b = [0u8; 1];
            random_bytes(&mut b);
            x[j] = b[0];
        }
    }
    let lin = random_invertible_linear();
    let y = one_way(&lin, &x, &k);
    (FaestPublicKey { x, y, lin }, FaestSecretKey { k })
}

/// Build the extended witness `k ‖ s_out` for the secret key.
fn extended_witness(pk: &FaestPublicKey, sk: &FaestSecretKey) -> Vec<u8> {
    let mut w = sk.k.clone();
    for j in 0..BLOCK {
        w.push(sbox(pk.x[j] ^ sk.k[j]));
    }
    w
}

fn statement(pk: &FaestPublicKey, msg: &[u8]) -> Vec<u8> {
    let mut input = b"FAEST-toy".to_vec();
    input.extend_from_slice(&pk.x);
    input.extend_from_slice(&pk.y);
    for row in &pk.lin {
        input.extend_from_slice(row);
    }
    input.extend_from_slice(msg);
    shake256(&input, 32)
}

pub fn faest_sign(pk: &FaestPublicKey, sk: &FaestSecretKey, msg: &[u8]) -> FaestSignature {
    let rel = AesRelation {
        x: pk.x.clone(),
        y: pk.y.clone(),
        lin: pk.lin.clone(),
    };
    mpcith_prove(&rel, &extended_witness(pk, sk), &statement(pk, msg))
}

pub fn faest_verify(pk: &FaestPublicKey, msg: &[u8], sig: &FaestSignature) -> bool {
    let rel = AesRelation {
        x: pk.x.clone(),
        y: pk.y.clone(),
        lin: pk.lin.clone(),
    };
    mpcith_verify(&rel, &statement(pk, msg), sig)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn keygen_one_way_consistent() {
        let (pk, sk) = faest_keygen();
        assert_eq!(one_way(&pk.lin, &pk.x, &sk.k), pk.y);
        // Every S-box input is nonzero, so x·y = 1 holds exactly.
        for j in 0..BLOCK {
            let s_in = pk.x[j] ^ sk.k[j];
            assert_ne!(s_in, 0);
            assert_eq!(gf_mul(s_in, sbox(s_in)), 1);
        }
    }

    #[test]
    fn sign_verify_roundtrip() {
        let (pk, sk) = faest_keygen();
        let msg = b"AES in the head";
        let sig = faest_sign(&pk, &sk, msg);
        assert!(faest_verify(&pk, msg, &sig));
    }

    #[test]
    fn wrong_message_rejected() {
        let (pk, sk) = faest_keygen();
        let sig = faest_sign(&pk, &sk, b"one");
        assert!(!faest_verify(&pk, b"two", &sig));
    }

    #[test]
    fn wrong_key_rejected() {
        let (pk_a, sk_a) = faest_keygen();
        let (pk_b, _) = faest_keygen();
        let sig = faest_sign(&pk_a, &sk_a, b"msg");
        assert!(!faest_verify(&pk_b, b"msg", &sig));
    }

    #[test]
    fn forged_witness_rejected() {
        // Witness with a wrong key byte: the linear ciphertext check
        // fails (and/or the S-box relation), so the proof is rejected.
        let (pk, sk) = faest_keygen();
        let mut bad = sk.clone();
        bad.k[0] ^= 0x3c;
        let rel = AesRelation {
            x: pk.x.clone(),
            y: pk.y.clone(),
            lin: pk.lin.clone(),
        };
        let msg = statement(&pk, b"msg");
        // Extended witness recomputed from the *bad* key so the S-box
        // relation still holds internally, but the ciphertext ≠ y.
        let mut w = bad.k.clone();
        for j in 0..BLOCK {
            w.push(sbox(pk.x[j] ^ bad.k[j]));
        }
        let sig = mpcith_prove(&rel, &w, &msg);
        assert!(!mpcith_verify(&rel, &msg, &sig));
    }

    #[test]
    fn tampered_proof_rejected() {
        let (pk, sk) = faest_keygen();
        let msg = b"tamper";
        let mut sig = faest_sign(&pk, &sk, msg);
        sig.reps[2].hidden_lin[0] ^= 1;
        assert!(!faest_verify(&pk, msg, &sig));
    }
}
