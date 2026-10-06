//! **MPC-in-the-head** proof engine shared by the `sdith`, `mqom` and
//! `faest` modules.
//!
//! # The paradigm (Ishai–Kushilevitz–Ostrovsky–Sahai 2007)
//! To prove knowledge of a witness `w` for some relation, the prover
//! *simulates in their head* an N-party computation on an additive
//! secret-sharing of `w`, commits to every party's view, and is then
//! challenged to open all but one party.  The verifier re-runs the
//! opened parties and checks consistency.  A cheating prover must
//! corrupt at least one party's view and survives only if that party
//! is the hidden one — probability `1/N` per repetition, driven down
//! exponentially with `τ` parallel repetitions.  Fiat–Shamir makes it
//! a signature: the challenges come from hashing the message and the
//! commitments.
//!
//! # What this engine provides
//! Additive sharing over GF(256) (share addition = XOR), so *linear*
//! computation is free: each party applies linear maps to its own
//! share.  The single nonlinear tool is a batched **dot-product check**
//! via a sacrificed random triple (Baum–Nof style): to convince the
//! verifier that `⟨u, v⟩ = t` for shared vectors `u, v` and shared
//! scalar `t`, the parties hold a random shared triple `(a, b, c)`
//! with `c = ⟨a, b⟩`, open the maskings `α = u + a`, `β = v + b`, and
//! broadcast shares of
//!
//! ```text
//! V = t − c + ⟨α, b⟩ + ⟨β, a⟩ − ⟨α, β⟩,
//! ```
//!
//! which telescopes to `(t − ⟨u,v⟩) + (⟨a,b⟩ − c)`: zero exactly when
//! both the statement and the triple are honest.  Each concrete scheme
//! (syndrome decoding, MQ, AES) reduces its nonlinear constraints to
//! one such dot product with verifier-chosen random coefficients `ε`,
//! plus scheme-specific *linear* broadcast checks.
//!
//! # Simplifications vs. the real round-3 schemes
//! Real SDitH/MQOM/FAEST use GGM seed trees (open N−1 seeds with log N
//! hashes), hypercube or VOLE structure, and larger repetition counts.
//! We open seeds individually and use toy `N = 8, τ = 8`
//! (soundness ≈ 2⁻²⁴ plus the 2⁻⁸ algebraic check — demonstration
//! grade).  Educational code: not constant-time.

use crate::hash::sha3::{sha3_256, shake256};
use crate::utils::random::random_bytes;

/// Parties per repetition.
pub const N_PARTIES: usize = 8;
/// Parallel repetitions.
pub const TAU: usize = 8;
/// Seed length in bytes.
pub const SEED_BYTES: usize = 16;

// ── GF(256), AES polynomial ───────────────────────────────────────────────────

pub(crate) fn gf_mul(a: u8, b: u8) -> u8 {
    let (mut a, mut b, mut r) = (a as u16, b as u16, 0u16);
    while b != 0 {
        if b & 1 == 1 {
            r ^= a;
        }
        a <<= 1;
        if a & 0x100 != 0 {
            a ^= 0x11b;
        }
        b >>= 1;
    }
    r as u8
}

pub(crate) fn gf_inv(a: u8) -> u8 {
    let mut result = 1u8;
    let mut base = a;
    let mut e = 254u32;
    while e > 0 {
        if e & 1 == 1 {
            result = gf_mul(result, base);
        }
        base = gf_mul(base, base);
        e >>= 1;
    }
    result
}

pub(crate) fn dot(a: &[u8], b: &[u8]) -> u8 {
    a.iter()
        .zip(b)
        .fold(0u8, |acc, (&x, &y)| acc ^ gf_mul(x, y))
}

fn xor_into(acc: &mut [u8], src: &[u8]) {
    for (a, s) in acc.iter_mut().zip(src) {
        *a ^= s;
    }
}

/// Domain-separated PRG.
fn prg(seed: &[u8], domain: &[u8], len: usize) -> Vec<u8> {
    let mut input = seed.to_vec();
    input.push(0x1f);
    input.extend_from_slice(domain);
    shake256(&input, len)
}

// ── The relation interface ────────────────────────────────────────────────────

/// One party's local computation output.
pub(crate) struct PartyView {
    /// Share of the left dot-product operand `u`.
    pub u: Vec<u8>,
    /// Share of the right dot-product operand `v`.
    pub v: Vec<u8>,
    /// Share of the claimed dot-product value `t`.
    pub t: u8,
    /// Shares of scheme-specific linear checks; each must sum to 0
    /// across parties for an honest witness.
    pub lin: Vec<u8>,
}

/// A relation provable by this engine.  All per-party computation must
/// be *linear* in the witness share (the leader additionally absorbs
/// public constants), with all nonlinearity funnelled into the single
/// `⟨u, v⟩ = t` check under the challenge coefficients `eps`.
pub(crate) trait MpcRelation {
    fn witness_len(&self) -> usize;
    /// Length of the dot-product vectors.
    fn dot_len(&self) -> usize;
    /// Number of challenge coefficients consumed.
    fn eps_len(&self) -> usize;
    /// Length of the linear-check broadcast.
    fn lin_len(&self) -> usize;
    fn party_compute(&self, wshare: &[u8], leader: bool, eps: &[u8]) -> PartyView;
}

// ── Proof structures ──────────────────────────────────────────────────────────

/// The opened data for one repetition.
#[derive(Clone, Debug, PartialEq)]
pub struct RepProof {
    /// Seeds of the N−1 revealed parties, in party order.
    pub seeds: Vec<Vec<u8>>,
    /// Commitment of the hidden party.
    pub hidden_com: [u8; 32],
    /// Last party's witness correction (needed when party N−1 is revealed).
    pub aux_w: Vec<u8>,
    /// Last party's triple correction.
    pub aux_c: u8,
    /// Hidden party's broadcasts: α, β shares, V share, linear shares.
    pub hidden_alpha: Vec<u8>,
    pub hidden_beta: Vec<u8>,
    pub hidden_v: u8,
    pub hidden_lin: Vec<u8>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct MpcithProof {
    /// Commitment-phase hash; the challenge coefficients ε derive from it.
    pub h1: [u8; 32],
    /// Broadcast-phase hash; the hidden party indices derive from it.
    pub h2: [u8; 32],
    pub reps: Vec<RepProof>,
}

// ── Internal per-party state ──────────────────────────────────────────────────

struct Party {
    seed: Vec<u8>,
    wshare: Vec<u8>,
    a: Vec<u8>,
    b: Vec<u8>,
    c: u8,
    com: [u8; 32],
}

/// Derive the parties of one repetition from fresh seeds and the real
/// witness: parties 0..N−2 take PRG shares; party N−1's witness and
/// triple-product shares are corrected so the totals are right, and
/// those corrections are folded into its commitment.
fn setup_parties(rel: &impl MpcRelation, witness: &[u8], rep: usize) -> (Vec<Party>, Vec<u8>, u8) {
    let wlen = rel.witness_len();
    let dlen = rel.dot_len();
    let mut parties = Vec::with_capacity(N_PARTIES);
    let mut w_acc = vec![0u8; wlen];
    let mut a_sum = vec![0u8; dlen];
    let mut b_sum = vec![0u8; dlen];
    let mut c_acc = 0u8;
    for i in 0..N_PARTIES {
        let mut seed = vec![0u8; SEED_BYTES];
        random_bytes(&mut seed);
        let wshare = if i < N_PARTIES - 1 {
            prg(&seed, b"w", wlen)
        } else {
            vec![0u8; wlen]
        };
        let a = prg(&seed, b"a", dlen);
        let b = prg(&seed, b"b", dlen);
        let c = if i < N_PARTIES - 1 {
            prg(&seed, b"c", 1)[0]
        } else {
            0
        };
        xor_into(&mut w_acc, &wshare);
        xor_into(&mut a_sum, &a);
        xor_into(&mut b_sum, &b);
        c_acc ^= c;
        parties.push(Party {
            seed,
            wshare,
            a,
            b,
            c,
            com: [0u8; 32],
        });
    }
    // Corrections for the last party.
    let mut aux_w = witness.to_vec();
    xor_into(&mut aux_w, &w_acc);
    let aux_c = dot(&a_sum, &b_sum) ^ c_acc;
    parties[N_PARTIES - 1].wshare = aux_w.clone();
    parties[N_PARTIES - 1].c = aux_c;
    // Commitments.
    for (i, p) in parties.iter_mut().enumerate() {
        p.com = commit_party(
            rep,
            i,
            &p.seed,
            if i == N_PARTIES - 1 {
                Some((&aux_w, aux_c))
            } else {
                None
            },
        );
    }
    (parties, aux_w, aux_c)
}

fn commit_party(rep: usize, index: usize, seed: &[u8], aux: Option<(&[u8], u8)>) -> [u8; 32] {
    let mut input = vec![rep as u8, index as u8];
    input.extend_from_slice(seed);
    if let Some((w, c)) = aux {
        input.extend_from_slice(w);
        input.push(c);
    }
    sha3_256(&input)
}

/// Recompute a revealed party's derived state from its seed.
fn expand_party(rel: &impl MpcRelation, seed: &[u8], aux: Option<(&[u8], u8)>) -> Party {
    let wlen = rel.witness_len();
    let dlen = rel.dot_len();
    let (wshare, c) = match aux {
        Some((w, c)) => (w.to_vec(), c),
        None => (prg(seed, b"w", wlen), prg(seed, b"c", 1)[0]),
    };
    Party {
        seed: seed.to_vec(),
        wshare,
        a: prg(seed, b"a", dlen),
        b: prg(seed, b"b", dlen),
        c,
        com: [0u8; 32],
    }
}

// ── Prove / verify ────────────────────────────────────────────────────────────

pub(crate) fn mpcith_prove(rel: &impl MpcRelation, witness: &[u8], msg: &[u8]) -> MpcithProof {
    assert_eq!(witness.len(), rel.witness_len());
    // Phase 1: commit to all parties of all repetitions.
    let mut all: Vec<Vec<Party>> = Vec::with_capacity(TAU);
    let mut auxes: Vec<(Vec<u8>, u8)> = Vec::with_capacity(TAU);
    let mut h1_input = msg.to_vec();
    for rep in 0..TAU {
        let (parties, aux_w, aux_c) = setup_parties(rel, witness, rep);
        for p in &parties {
            h1_input.extend_from_slice(&p.com);
        }
        all.push(parties);
        auxes.push((aux_w, aux_c));
    }
    let h1 = sha3_256(&h1_input);

    // Phase 2: challenge coefficients, run the parties, broadcast.
    let mut h2_input = h1.to_vec();
    let mut broadcasts: Vec<Vec<(Vec<u8>, Vec<u8>, u8, Vec<u8>)>> = Vec::with_capacity(TAU);
    for (rep, parties) in all.iter().enumerate() {
        let eps = prg(&h1, &[b'e', rep as u8], rel.eps_len());
        let views: Vec<PartyView> = parties
            .iter()
            .enumerate()
            .map(|(i, p)| rel.party_compute(&p.wshare, i == 0, &eps))
            .collect();
        // Open α = u + a and β = v + b.
        let dlen = rel.dot_len();
        let mut alpha = vec![0u8; dlen];
        let mut beta = vec![0u8; dlen];
        let shares: Vec<(Vec<u8>, Vec<u8>)> = parties
            .iter()
            .zip(&views)
            .map(|(p, view)| {
                let mut ai = view.u.clone();
                xor_into(&mut ai, &p.a);
                let mut bi = view.v.clone();
                xor_into(&mut bi, &p.b);
                xor_into(&mut alpha, &ai);
                xor_into(&mut beta, &bi);
                (ai, bi)
            })
            .collect();
        // V shares.
        let mut rep_bc = Vec::with_capacity(N_PARTIES);
        for (i, (p, view)) in parties.iter().zip(&views).enumerate() {
            let mut v = view.t ^ p.c ^ dot(&alpha, &p.b) ^ dot(&beta, &p.a);
            if i == 0 {
                v ^= dot(&alpha, &beta);
            }
            let (ai, bi) = &shares[i];
            h2_input.extend_from_slice(ai);
            h2_input.extend_from_slice(bi);
            h2_input.push(v);
            h2_input.extend_from_slice(&view.lin);
            rep_bc.push((ai.clone(), bi.clone(), v, view.lin.clone()));
        }
        broadcasts.push(rep_bc);
    }
    let h2 = sha3_256(&h2_input);

    // Phase 3: hide one party per repetition, open the rest.
    let mut reps = Vec::with_capacity(TAU);
    for rep in 0..TAU {
        let hidden = h2[rep] as usize % N_PARTIES;
        let _ = rep;
        let parties = &all[rep];
        let (aux_w, aux_c) = &auxes[rep];
        let (ha, hb, hv, hl) = broadcasts[rep][hidden].clone();
        reps.push(RepProof {
            seeds: (0..N_PARTIES)
                .filter(|&i| i != hidden)
                .map(|i| parties[i].seed.clone())
                .collect(),
            hidden_com: parties[hidden].com,
            aux_w: if hidden != N_PARTIES - 1 {
                aux_w.clone()
            } else {
                Vec::new()
            },
            aux_c: if hidden != N_PARTIES - 1 { *aux_c } else { 0 },
            hidden_alpha: ha,
            hidden_beta: hb,
            hidden_v: hv,
            hidden_lin: hl,
        });
    }
    MpcithProof { h1, h2, reps }
}

pub(crate) fn mpcith_verify(rel: &impl MpcRelation, msg: &[u8], proof: &MpcithProof) -> bool {
    if proof.reps.len() != TAU {
        return false;
    }
    let dlen = rel.dot_len();
    for rep in &proof.reps {
        if rep.seeds.len() != N_PARTIES - 1
            || rep.seeds.iter().any(|s| s.len() != SEED_BYTES)
            || rep.hidden_alpha.len() != dlen
            || rep.hidden_beta.len() != dlen
            || rep.hidden_lin.len() != rel.lin_len()
        {
            return false;
        }
    }

    // The hidden index of each repetition is pinned by h2, and both
    // h1 and h2 are themselves recomputed below from the opened data,
    // so a forger cannot pick them freely.
    let hidden: Vec<usize> = (0..TAU).map(|r| proof.h2[r] as usize % N_PARTIES).collect();
    let wlen = rel.witness_len();

    // Recompute h1 from commitments (hidden party's from the proof).
    let mut h1_input = msg.to_vec();
    for (r, rep) in proof.reps.iter().enumerate() {
        if hidden[r] != N_PARTIES - 1 && rep.aux_w.len() != wlen {
            return false;
        }
        let mut k = 0;
        for i in 0..N_PARTIES {
            if i == hidden[r] {
                h1_input.extend_from_slice(&rep.hidden_com);
            } else {
                let aux = if i == N_PARTIES - 1 {
                    Some((rep.aux_w.as_slice(), rep.aux_c))
                } else {
                    None
                };
                h1_input.extend_from_slice(&commit_party(r, i, &rep.seeds[k], aux));
                k += 1;
            }
        }
    }
    if sha3_256(&h1_input) != proof.h1 {
        return false;
    }

    // Re-run the revealed parties, rebuild broadcasts, recompute h2,
    // and check the two global sums.
    let mut h2_input = proof.h1.to_vec();
    for (r, rep) in proof.reps.iter().enumerate() {
        let eps = prg(&proof.h1, &[b'e', r as u8], rel.eps_len());
        let mut alpha = rep.hidden_alpha.clone();
        let mut beta = rep.hidden_beta.clone();
        let mut opened: Vec<Option<(Party, PartyView, Vec<u8>, Vec<u8>)>> =
            (0..N_PARTIES).map(|_| None).collect();
        let mut k = 0;
        for i in 0..N_PARTIES {
            if i == hidden[r] {
                continue;
            }
            let aux = if i == N_PARTIES - 1 {
                Some((rep.aux_w.as_slice(), rep.aux_c))
            } else {
                None
            };
            let p = expand_party(rel, &rep.seeds[k], aux);
            k += 1;
            let view = rel.party_compute(&p.wshare, i == 0, &eps);
            let mut ai = view.u.clone();
            xor_into(&mut ai, &p.a);
            let mut bi = view.v.clone();
            xor_into(&mut bi, &p.b);
            xor_into(&mut alpha, &ai);
            xor_into(&mut beta, &bi);
            opened[i] = Some((p, view, ai, bi));
        }
        let mut v_total = rep.hidden_v;
        let mut lin_total = rep.hidden_lin.clone();
        for (i, slot) in opened.iter_mut().enumerate() {
            if i == hidden[r] {
                h2_input.extend_from_slice(&rep.hidden_alpha);
                h2_input.extend_from_slice(&rep.hidden_beta);
                h2_input.push(rep.hidden_v);
                h2_input.extend_from_slice(&rep.hidden_lin);
                continue;
            }
            // Filled for every non-hidden party in the loop above; a
            // missing slot would mean the hidden index was inconsistent,
            // so reject rather than panic on adversarial input.
            let Some((p, view, ai, bi)) = slot.take() else {
                return false;
            };
            let mut v = view.t ^ p.c ^ dot(&alpha, &p.b) ^ dot(&beta, &p.a);
            if i == 0 {
                v ^= dot(&alpha, &beta);
            }
            v_total ^= v;
            xor_into(&mut lin_total, &view.lin);
            h2_input.extend_from_slice(&ai);
            h2_input.extend_from_slice(&bi);
            h2_input.push(v);
            h2_input.extend_from_slice(&view.lin);
        }
        if v_total != 0 || lin_total.iter().any(|&x| x != 0) {
            return false;
        }
    }
    sha3_256(&h2_input) == proof.h2
}
