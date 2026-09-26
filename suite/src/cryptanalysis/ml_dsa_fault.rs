//! Fault attacks on ML-DSA: what happens when the masking vector is not fresh.
//!
//! [`crate::cryptanalysis::ml_dsa_leakage`] recovers `s1` by watching `y` leak a
//! bit at a time. This module takes the shorter route: make `y` *wrong*.
//!
//! The rejection loop is a uniquely attractive fault target. It runs several
//! times per signature, it draws fresh randomness each time, and the value it
//! draws is the only thing protecting the secret. Three faults, each fully
//! implemented against the library's real ML-DSA-65 signer:
//!
//! | fault | effect | signatures needed |
//! |---|---|---|
//! | [`zeroed_nonce_attack`] | `y = 0` | 1 |
//! | [`nonce_reuse_attack`] | the same `y` on two messages | 2 |
//! | [`partial_zero_attack`] | one polynomial of `y` is zeroed | 1 per component |
//!
//! All three end the same way: solve a linear system over `Z_q`, recover `s1`,
//! and forge a signature that the library's own verifier accepts.
//!
//! # Hedging does not help
//!
//! It is worth being explicit, because it is a common misconception. ML-DSA's
//! hedged mode mixes 32 fresh random bytes into `ρ''` so that a bad RNG cannot
//! produce a repeated `y`. That defends against *randomness failure*. It does
//! nothing here, because these faults act on `y` after it is derived — and it
//! does nothing against the side channels in the sibling module either, because
//! a probe does not care where the value came from. The published
//! ~300-trace key recovery works in hedged mode, and the correction-fault
//! attacks of eprint 2024/138 work against randomized and hedged Dilithium
//! alike.
//!
//! # References
//!
//! * Bruinderink and Pessl, *Differential fault attacks on deterministic
//!   lattice signatures*, TCHES 2018 — the nonce-reuse route.
//! * Ravi, Jhanwar, Howe, Chattopadhyay, Bhasin, *Exploiting determinism in
//!   lattice-based signatures*, AsiaCCS 2019.
//! * Correction fault attacks on randomized and hedged Dilithium,
//!   eprint 2024/138.

use crate::cryptanalysis::ml_dsa_leakage::{
    centre, forge_and_verify, negacyclic_row, solve_mod_q, Q,
};
use crate::pqc::ml_dsa::{
    ml_dsa_65_keygen, ml_dsa_65_secret_vectors, ml_dsa_65_sign_with_forced_nonce,
    ml_dsa_65_signature_parts, ml_dsa_65_verify, MlDsaPublicKey, ML_DSA_65_GAMMA1, ML_DSA_65_L,
};
use rand::rngs::SmallRng;
use rand::{Rng, SeedableRng};

/// Polynomial degree.
pub const N: usize = 256;

/// What a fault attack achieved.
#[derive(Clone, Debug, PartialEq)]
pub struct FaultReport {
    pub fault: &'static str,
    /// Faulty signatures the attacker needed.
    pub signatures: u32,
    /// Signing attempts made, including ones the faulted nonce failed.
    pub attempts: u32,
    /// Coefficients of `s1`, i.e. `256·ℓ`.
    pub coefficients: usize,
    /// How many were recovered correctly.
    pub correct: usize,
    /// Whether a forgery built from the recovered `s1` verified.
    pub forged: bool,
}

impl FaultReport {
    pub fn succeeded(&self) -> bool {
        self.correct == self.coefficients && self.forged
    }
}

/// A masking vector of the right shape, drawn uniformly from `(-γ₁, γ₁]`.
///
/// Used as the *repeated* value in the nonce-reuse attack: the fault does not
/// change what `y` looks like, only that it comes round again.
pub fn random_mask(seed: u64) -> Vec<Vec<i32>> {
    let mut rng = SmallRng::seed_from_u64(seed);
    (0..ML_DSA_65_L)
        .map(|_| {
            (0..N)
                .map(|_| rng.gen_range(-ML_DSA_65_GAMMA1 + 1..=ML_DSA_65_GAMMA1))
                .collect()
        })
        .collect()
}

/// A masking vector that is entirely zero.
pub fn zero_mask() -> Vec<Vec<i32>> {
    vec![vec![0i32; N]; ML_DSA_65_L]
}

/// Solve `(c·x)[j] = rhs[j]` for all `j` — one component of `s1` from one
/// polynomial equation.
///
/// Returns `None` when the negacyclic matrix of `c` is singular mod `q`, which
/// happens when `c` has a zero in its NTT. The caller retries with another
/// signature.
fn solve_component(c: &[i32], rhs: &[i64]) -> Option<Vec<i32>> {
    let rows: Vec<(Vec<i64>, i64)> = (0..N)
        .map(|j| (negacyclic_row(c, j), rhs[j].rem_euclid(Q)))
        .collect();
    let sol = solve_mod_q(&rows, N)?;
    Some(sol.iter().map(|&v| centre(v) as i32).collect())
}

/// **Fault: the mask is zeroed.** `z = y + c·s1` becomes `z = c·s1`, and one
/// signature is the whole secret.
///
/// This is the cheapest fault there is, and it is not far-fetched: a cleared
/// randomness buffer, a skipped `ExpandMask` call, a reset that lands between
/// the draw and the use. Note that a zeroed mask sails through every rejection
/// check — `‖c·s1‖∞ ≤ τ·η = 196`, far inside `γ₁ - β` — so the device happily
/// emits the signature.
pub fn zeroed_nonce_attack(seed: u64) -> Option<FaultReport> {
    let mut kseed = [0u8; 32];
    kseed[..8].copy_from_slice(&seed.to_le_bytes());
    let (pk, sk) = ml_dsa_65_keygen(&kseed);
    let (true_s1, _) = ml_dsa_65_secret_vectors(&sk);

    let mut attempts = 0u32;
    let mut recovered: Option<Vec<Vec<i32>>> = None;
    for t in 0..16u32 {
        attempts += 1;
        let msg = format!("faulted message {t}");
        let Some((sig, _)) =
            ml_dsa_65_sign_with_forced_nonce(&sk, msg.as_bytes(), &[t as u8; 32], &zero_mask())
        else {
            continue;
        };
        let (c, z) = ml_dsa_65_signature_parts(&sig)?;
        let mut s1 = Vec::with_capacity(ML_DSA_65_L);
        let mut ok = true;
        for zi in z.iter() {
            let rhs: Vec<i64> = zi.iter().map(|&v| v as i64).collect();
            match solve_component(&c, &rhs) {
                Some(x) => s1.push(x),
                None => {
                    ok = false;
                    break;
                }
            }
        }
        if ok {
            recovered = Some(s1);
            break;
        }
    }
    let s1 = recovered?;
    Some(score(
        "zeroed nonce (y = 0)",
        1,
        attempts,
        &pk,
        &true_s1,
        &s1,
    ))
}

/// **Fault: the same mask twice.** Two signatures under the same `y` give
/// `z - z' = (c - c')·s1`, and `s1` follows by one linear solve.
///
/// The mask itself never has to be known — only that it repeated. That makes
/// this the fault to worry about in practice: a stuck RNG, a replayed context,
/// a virtual machine rolled back to a snapshot between signatures.
pub fn nonce_reuse_attack(seed: u64) -> Option<FaultReport> {
    let mut kseed = [0u8; 32];
    kseed[..8].copy_from_slice(&seed.to_le_bytes());
    let (pk, sk) = ml_dsa_65_keygen(&kseed);
    let (true_s1, _) = ml_dsa_65_secret_vectors(&sk);

    // A frozen mask is not automatically a *usable* frozen mask. `‖z‖∞` must
    // stay under `γ₁ - β`, and a `y` with any coefficient within `β` of the
    // edge fails that for essentially every message — about 60% of uniform
    // masks are unusable this way. An honest signer redraws and moves on; a
    // frozen one is stuck. So the attacker waits for a fault that freezes a
    // workable value, which is what the outer loop models.
    let mut collected: Vec<(Vec<i32>, Vec<Vec<i32>>)> = Vec::new();
    let mut attempts = 0u32;
    'outer: for trial in 0..64u64 {
        let y = random_mask(seed ^ 0xDEAD_BEEF ^ (trial << 8));
        collected.clear();
        for t in 0..32u32 {
            attempts += 1;
            let msg = format!("reused-nonce message {trial}-{t}");
            let Some((sig, _)) =
                ml_dsa_65_sign_with_forced_nonce(&sk, msg.as_bytes(), &[0u8; 32], &y)
            else {
                continue;
            };
            if !ml_dsa_65_verify(&pk, msg.as_bytes(), &sig) {
                continue;
            }
            let (c, z) = ml_dsa_65_signature_parts(&sig)?;
            collected.push((c, z));
            if collected.len() >= 2 {
                break 'outer;
            }
        }
    }
    if collected.len() < 2 {
        return None;
    }
    let (c0, z0) = &collected[0];
    let (c1, z1) = &collected[1];
    let dc: Vec<i32> = c0.iter().zip(c1).map(|(&a, &b)| a - b).collect();
    let mut s1 = Vec::with_capacity(ML_DSA_65_L);
    for i in 0..ML_DSA_65_L {
        let rhs: Vec<i64> = z0[i]
            .iter()
            .zip(&z1[i])
            .map(|(&a, &b)| (a as i64 - b as i64).rem_euclid(Q))
            .collect();
        s1.push(solve_component(&dc, &rhs)?);
    }
    Some(score(
        "nonce reuse (same y, two messages)",
        2,
        attempts,
        &pk,
        &true_s1,
        &s1,
    ))
}

/// **Fault: one polynomial of the mask is zeroed.** Recovers one component of
/// `s1` per faulted signature.
///
/// The partial version is the realistic one when the fault is a single skipped
/// `ExpandMask` iteration rather than a wholesale clear. It also shows the
/// attack degrades gracefully: `ℓ` faults instead of one, still no lattice.
pub fn partial_zero_attack(seed: u64) -> Option<FaultReport> {
    let mut kseed = [0u8; 32];
    kseed[..8].copy_from_slice(&seed.to_le_bytes());
    let (pk, sk) = ml_dsa_65_keygen(&kseed);
    let (true_s1, _) = ml_dsa_65_secret_vectors(&sk);

    let mut s1: Vec<Option<Vec<i32>>> = vec![None; ML_DSA_65_L];
    let mut attempts = 0u32;
    let mut signatures = 0u32;
    for target in 0..ML_DSA_65_L {
        for t in 0..64u32 {
            attempts += 1;
            // Only polynomial `target` is zeroed; the rest are honest-looking.
            let mut y = random_mask(seed ^ (t as u64) ^ ((target as u64) << 32));
            y[target] = vec![0i32; N];
            let msg = format!("partially faulted {target}-{t}");
            let Some((sig, _)) =
                ml_dsa_65_sign_with_forced_nonce(&sk, msg.as_bytes(), &[0u8; 32], &y)
            else {
                continue;
            };
            signatures += 1;
            let (c, z) = ml_dsa_65_signature_parts(&sig)?;
            // z[target] = 0 + c·s1[target].
            let rhs: Vec<i64> = z[target].iter().map(|&v| v as i64).collect();
            if let Some(x) = solve_component(&c, &rhs) {
                s1[target] = Some(x);
                break;
            }
        }
        s1[target].as_ref()?;
    }
    let s1: Vec<Vec<i32>> = s1.into_iter().map(|x| x.unwrap()).collect();
    Some(score(
        "partial zeroed nonce (one polynomial of y)",
        signatures,
        attempts,
        &pk,
        &true_s1,
        &s1,
    ))
}

fn score(
    fault: &'static str,
    signatures: u32,
    attempts: u32,
    pk: &MlDsaPublicKey,
    truth: &[Vec<i32>],
    got: &[Vec<i32>],
) -> FaultReport {
    let correct = truth
        .iter()
        .zip(got)
        .map(|(t, r)| t.iter().zip(r).filter(|(a, b)| a == b).count())
        .sum();
    FaultReport {
        fault,
        signatures,
        attempts,
        coefficients: ML_DSA_65_L * N,
        correct,
        forged: forge_and_verify(pk, got, b"forged after a fault"),
    }
}

/// Run all three faults, for the CLI and for the report.
pub fn run_all(seed: u64) -> Vec<FaultReport> {
    [
        zeroed_nonce_attack(seed),
        nonce_reuse_attack(seed),
        partial_zero_attack(seed),
    ]
    .into_iter()
    .flatten()
    .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_zeroed_nonce_gives_up_the_whole_key_in_one_signature() {
        let r = zeroed_nonce_attack(1).expect("the faulted signature was produced");
        assert_eq!(r.correct, r.coefficients, "{r:?}");
        assert!(r.forged, "{r:?}");
        assert_eq!(r.signatures, 1);
    }

    #[test]
    fn a_zeroed_nonce_still_passes_every_rejection_check() {
        // The fault is not caught by the scheme, which is the uncomfortable
        // part: ‖c·s1‖∞ ≤ τ·η = 196, far inside γ₁ - β, so the device signs.
        let (pk, sk) = ml_dsa_65_keygen(&[3u8; 32]);
        let (sig, trace) =
            ml_dsa_65_sign_with_forced_nonce(&sk, b"zeroed", &[0u8; 32], &zero_mask())
                .expect("a zero mask clears the rejection checks");
        assert!(ml_dsa_65_verify(&pk, b"zeroed", &sig));
        assert_eq!(trace.attempts, 1);
        assert!(trace.y.iter().all(|p| p.iter().all(|&c| c == 0)));
        // …and z is then exactly c·s1.
        let (_, s1_check) = (0, ml_dsa_65_secret_vectors(&sk).0);
        let (c, z) = ml_dsa_65_signature_parts(&sig).unwrap();
        for i in 0..ML_DSA_65_L {
            let expect = crate::cryptanalysis::ml_dsa_leakage::negacyclic_mul(
                &c,
                &s1_check[i].iter().map(|&v| v as i64).collect::<Vec<_>>(),
            );
            for j in 0..N {
                assert_eq!(
                    (z[i][j] as i64).rem_euclid(Q),
                    expect[j],
                    "component {i}, coefficient {j}"
                );
            }
        }
    }

    #[test]
    fn nonce_reuse_gives_up_the_key_from_two_signatures() {
        let r = nonce_reuse_attack(2).expect("two faulted signatures landed");
        assert!(r.succeeded(), "{r:?}");
        assert_eq!(r.signatures, 2);
        // The faulted nonce must clear the rejection checks to produce a
        // signature at all, so more attempts than signatures is expected.
        assert!(r.attempts >= r.signatures);
    }

    #[test]
    fn partial_zeroing_recovers_one_component_per_fault() {
        let r = partial_zero_attack(4).expect("the partial faults landed");
        assert!(r.succeeded(), "{r:?}");
        assert!(r.signatures >= ML_DSA_65_L as u32);
    }

    #[test]
    fn all_three_faults_succeed_and_report_themselves() {
        let rs = run_all(8);
        assert_eq!(rs.len(), 3);
        for r in &rs {
            assert!(r.succeeded(), "{r:?}");
            assert!(!r.fault.is_empty());
            assert_eq!(r.coefficients, ML_DSA_65_L * N);
        }
        // The zeroed nonce is the cheapest; reuse needs one more signature.
        assert!(rs[0].signatures <= rs[1].signatures);
    }

    #[test]
    fn a_forced_nonce_that_fails_the_checks_produces_nothing() {
        // Faithfulness of the fault model: a faulted device that hits a
        // rejection emits no signature rather than silently retrying with a
        // fresh mask, which would defeat the whole attack.
        let (_, sk) = ml_dsa_65_keygen(&[5u8; 32]);
        // A mask pinned at the very top of the range makes ‖z‖∞ ≥ γ₁ - β
        // essentially always, so signing must decline.
        let y = vec![vec![ML_DSA_65_GAMMA1; N]; ML_DSA_65_L];
        assert!(ml_dsa_65_sign_with_forced_nonce(&sk, b"too big", &[0u8; 32], &y).is_none());
    }

    #[test]
    fn solve_component_inverts_multiplication_by_c() {
        let (_, sk) = ml_dsa_65_keygen(&[6u8; 32]);
        let (s1, _) = ml_dsa_65_secret_vectors(&sk);
        let (sig, _) =
            ml_dsa_65_sign_with_forced_nonce(&sk, b"invert me", &[0u8; 32], &zero_mask()).unwrap();
        let (c, z) = ml_dsa_65_signature_parts(&sig).unwrap();
        for i in 0..ML_DSA_65_L {
            let rhs: Vec<i64> = z[i].iter().map(|&v| v as i64).collect();
            assert_eq!(
                solve_component(&c, &rhs),
                Some(s1[i].clone()),
                "component {i}"
            );
        }
    }

    #[test]
    fn random_masks_stay_inside_the_gamma1_range() {
        let y = random_mask(99);
        assert_eq!(y.len(), ML_DSA_65_L);
        for p in &y {
            assert_eq!(p.len(), N);
            for &c in p {
                assert!(c > -ML_DSA_65_GAMMA1 && c <= ML_DSA_65_GAMMA1);
            }
        }
    }

    #[test]
    fn faults_are_stable_across_keys() {
        for seed in [10u64, 21, 33] {
            assert!(
                zeroed_nonce_attack(seed).unwrap().succeeded(),
                "seed {seed}"
            );
        }
    }
}
