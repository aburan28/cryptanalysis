//! **MQOM** — MQ on my Mind
//! (Feneuil–Rivain 2023; NIST additional-signatures round 3).
//!
//! # The idea
//! MQOM proves knowledge of a solution `x` to a **multivariate
//! quadratic** system — the same MQ problem UOV/MAYO hide a trapdoor
//! inside, but here used *directly*, with **no trapdoor**.  The public
//! key is a random MQ map `P: F_q^n → F_q^m`,
//!
//! ```text
//! P_k(x) = xᵀ·A_k·x + b_kᵀ·x,      k = 1..m,
//! ```
//!
//! and a target `y = P(x)`.  Because there is no structure to protect,
//! MQOM has the *smallest keys* of any signature here (a few dozen
//! bytes — the map is regenerated from a seed) at the cost of a larger
//! signature.  Security rests only on the average-case hardness of
//! random MQ.
//!
//! # The proof (MPC-in-the-head)
//! The witness is `x`, additively shared.  Each equation
//! `xᵀA_k x + b_kᵀx = y_k` is quadratic; the parties compute a share
//! of the *linear* part `b_kᵀx` locally, and the quadratic part
//! `xᵀA_k x` is verified with the sacrificed-triple dot-product check
//! (`pqc::mpcith`): batching the `m` equations under verifier
//! randomness `ε` gives one check `⟨u, v⟩ = t` with
//! `u = (Σ_k ε_k A_k)·x`, `v = x`, and
//! `t = Σ_k ε_k y_k − Σ_k ε_k b_kᵀx`.  Both `u` (a shared linear image
//! of `x`) and `t` (linear in `x`) are computable from the shares, so
//! the whole nonlinear content collapses into the single dot product.
//!
//! # Simplifications
//! We batch the `m` quadratic constraints into one dot-product check
//! rather than proving each `xᵀA_k x` separately; this is exactly the
//! standard random-linear-combination soundness amplification (a
//! cheating `x` survives with probability `1/q` over ε, i.e. 2⁻⁸ here),
//! layered on the engine's `1/N^τ`.  Plus the engine simplifications in
//! `pqc::mpcith`.  Toy parameters `q = 256, n = 24, m = 24`; not
//! constant-time; see SECURITY.md.

use super::mpcith::{gf_mul, mpcith_prove, mpcith_verify, MpcRelation, MpcithProof, PartyView};
use crate::hash::sha3::shake256;
use crate::utils::random::random_bytes;

/// Number of variables.
pub const N_VARS: usize = 24;
/// Number of quadratic equations.
pub const M_EQ: usize = 24;

/// Public key: a random MQ map (quadratic matrices `A_k`, linear parts
/// `b_k`) and its value `y` at the secret `x`.
#[derive(Clone)]
pub struct MqomPublicKey {
    pub a: Vec<Vec<Vec<u8>>>, // m × n × n
    pub b: Vec<Vec<u8>>,      // m × n
    pub y: Vec<u8>,           // m
}

#[derive(Clone)]
pub struct MqomSecretKey {
    pub x: Vec<u8>,
}

pub type MqomSignature = MpcithProof;

/// Evaluate the MQ map at `x`.
fn eval_mq(a: &[Vec<Vec<u8>>], b: &[Vec<u8>], x: &[u8]) -> Vec<u8> {
    (0..a.len())
        .map(|k| {
            let mut acc = 0u8;
            for i in 0..N_VARS {
                if x[i] == 0 {
                    continue;
                }
                let mut inner = 0u8;
                for j in 0..N_VARS {
                    if a[k][i][j] != 0 {
                        inner ^= gf_mul(a[k][i][j], x[j]);
                    }
                }
                acc ^= gf_mul(x[i], inner);
            }
            for j in 0..N_VARS {
                acc ^= gf_mul(b[k][j], x[j]);
            }
            acc
        })
        .collect()
}

struct MqRelation {
    a: Vec<Vec<Vec<u8>>>,
    b: Vec<Vec<u8>>,
    y: Vec<u8>,
}

impl MpcRelation for MqRelation {
    fn witness_len(&self) -> usize {
        N_VARS
    }
    fn dot_len(&self) -> usize {
        N_VARS
    }
    fn eps_len(&self) -> usize {
        M_EQ
    }
    fn lin_len(&self) -> usize {
        0
    }
    fn party_compute(&self, wshare: &[u8], leader: bool, eps: &[u8]) -> PartyView {
        // Combined quadratic matrix M_ε = Σ_k ε_k A_k, then u = M_ε·x.
        let mut u = vec![0u8; N_VARS];
        for i in 0..N_VARS {
            let mut acc = 0u8;
            for j in 0..N_VARS {
                let mut mij = 0u8;
                for k in 0..M_EQ {
                    if self.a[k][i][j] != 0 && eps[k] != 0 {
                        mij ^= gf_mul(eps[k], self.a[k][i][j]);
                    }
                }
                if mij != 0 {
                    acc ^= gf_mul(mij, wshare[j]);
                }
            }
            u[i] = acc;
        }
        let v = wshare.to_vec();
        // t = Σ_k ε_k y_k (leader only) − Σ_k ε_k (b_kᵀ x).
        let mut t = 0u8;
        for k in 0..M_EQ {
            if eps[k] == 0 {
                continue;
            }
            let bx = self.b[k]
                .iter()
                .zip(wshare)
                .fold(0u8, |acc, (&bj, &xj)| acc ^ gf_mul(bj, xj));
            t ^= gf_mul(eps[k], bx);
        }
        if leader {
            for k in 0..M_EQ {
                t ^= gf_mul(eps[k], self.y[k]);
            }
        }
        PartyView {
            u,
            v,
            t,
            lin: Vec::new(),
        }
    }
}

pub fn mqom_keygen() -> (MqomPublicKey, MqomSecretKey) {
    // Secret solution, then a random map, then y = P(x) — so a solution
    // is guaranteed to exist (the standard MQ-signature keygen).
    let mut x = vec![0u8; N_VARS];
    random_bytes(&mut x);
    let mut a = vec![vec![vec![0u8; N_VARS]; N_VARS]; M_EQ];
    let mut b = vec![vec![0u8; N_VARS]; M_EQ];
    for k in 0..M_EQ {
        for i in 0..N_VARS {
            random_bytes(&mut a[k][i]);
        }
        random_bytes(&mut b[k]);
    }
    let y = eval_mq(&a, &b, &x);
    (MqomPublicKey { a, b, y }, MqomSecretKey { x })
}

fn statement(pk: &MqomPublicKey, msg: &[u8]) -> Vec<u8> {
    let mut input = b"MQOM-toy".to_vec();
    for mat in &pk.a {
        for row in mat {
            input.extend_from_slice(row);
        }
    }
    for row in &pk.b {
        input.extend_from_slice(row);
    }
    input.extend_from_slice(&pk.y);
    input.extend_from_slice(msg);
    shake256(&input, 32)
}

pub fn mqom_sign(pk: &MqomPublicKey, sk: &MqomSecretKey, msg: &[u8]) -> MqomSignature {
    let rel = MqRelation {
        a: pk.a.clone(),
        b: pk.b.clone(),
        y: pk.y.clone(),
    };
    mpcith_prove(&rel, &sk.x, &statement(pk, msg))
}

pub fn mqom_verify(pk: &MqomPublicKey, msg: &[u8], sig: &MqomSignature) -> bool {
    let rel = MqRelation {
        a: pk.a.clone(),
        b: pk.b.clone(),
        y: pk.y.clone(),
    };
    mpcith_verify(&rel, &statement(pk, msg), sig)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn keygen_solution_is_valid() {
        let (pk, sk) = mqom_keygen();
        assert_eq!(eval_mq(&pk.a, &pk.b, &sk.x), pk.y);
    }

    #[test]
    fn sign_verify_roundtrip() {
        let (pk, sk) = mqom_keygen();
        let msg = b"MQ on my mind";
        let sig = mqom_sign(&pk, &sk, msg);
        assert!(mqom_verify(&pk, msg, &sig));
    }

    #[test]
    fn wrong_message_rejected() {
        let (pk, sk) = mqom_keygen();
        let sig = mqom_sign(&pk, &sk, b"one");
        assert!(!mqom_verify(&pk, b"two", &sig));
    }

    #[test]
    fn wrong_key_rejected() {
        let (pk_a, sk_a) = mqom_keygen();
        let (pk_b, _) = mqom_keygen();
        let sig = mqom_sign(&pk_a, &sk_a, b"msg");
        assert!(!mqom_verify(&pk_b, b"msg", &sig));
    }

    #[test]
    fn wrong_witness_rejected() {
        // An x' that does not solve the MQ system must fail the quadratic
        // dot-product check with overwhelming probability over ε.
        let (pk, sk) = mqom_keygen();
        let mut bad = sk.x.clone();
        bad[0] ^= 0x9e;
        let rel = MqRelation {
            a: pk.a.clone(),
            b: pk.b.clone(),
            y: pk.y.clone(),
        };
        let msg = statement(&pk, b"msg");
        let sig = mpcith_prove(&rel, &bad, &msg);
        assert!(!mpcith_verify(&rel, &msg, &sig));
    }

    #[test]
    fn tampered_proof_rejected() {
        let (pk, sk) = mqom_keygen();
        let msg = b"tamper";
        let mut sig = mqom_sign(&pk, &sk, msg);
        sig.reps[1].hidden_v ^= 0x40;
        assert!(!mqom_verify(&pk, msg, &sig));
    }
}
