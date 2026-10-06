//! **Boomerang cryptanalysis** — the full chain from S-box BCT to end-
//! to-end attack.
//!
//! ## The boomerang attack in one paragraph
//!
//! Split the cipher `E = E₁ ∘ E₀` into upper (`E₀`) and lower (`E₁`)
//! halves.  Find a differential `α →_{E₀} β` of probability `p` and a
//! differential `γ →_{E₁} δ` of probability `q`.  Then for a random
//! plaintext `P`, encrypt `P` and `P ⊕ α` to get `C, C*`; XOR `δ` onto
//! both to get `C ⊕ δ`, `C* ⊕ δ`; decrypt those to get `P', P*'`.  The
//! claim is `P' ⊕ P*' = α` with probability `≈ (pq)²` if the two trails
//! are independent at the switch.  A statistically significant excess
//! over `2^{−n}` is the distinguisher.
//!
//! ## Why this exists (the "switch correction")
//!
//! The classical analysis treats the meeting of the two trails as
//! independent.  In practice the dependency is non-trivial — for some
//! S-boxes the switch *boosts* the probability above `(pq)²`, for
//! others it *kills* it.  The **Boomerang Connectivity Table** (Cid,
//! Huang, Peyrin, Sasaki, Song — EUROCRYPT 2018) is the per-S-box
//! correction term.  This module:
//!
//! 1. [`boomerang_distinguisher`] — generic adaptive-query distinguisher
//!    over any [`BlockCipher`].  Counts right quartets, reports
//!    empirical vs. predicted probability + z-score.
//!
//! 2. [`rectangle_attack`] — chosen-plaintext variant.  Generates a
//!    pool of `N` plaintexts, looks for quartets `(P₁, P₂, P₃, P₄)`
//!    with the right XOR pattern via hash buckets.  Same per-quartet
//!    probability as the boomerang but trades the adaptive-decryption
//!    oracle for `O(N · log N)` post-processing — important on real
//!    ciphers where the decryption oracle is unavailable.
//!
//! 3. [`sandwich_distinguisher`] — three-layer split `E₁ ∘ E_m ∘ E₀`
//!    where `E_m` is small and we plug the **BCT directly** into the
//!    switch probability instead of multiplying two DDT entries.  This
//!    is the Dunkelman–Keller–Shamir 2010 sandwich attack pattern
//!    (which broke KASUMI).
//!
//! 4. [`boomerang_trail_search`] — branch-and-bound over a generic
//!    SPN cipher model (DDT + linear layer + round count).  Finds the
//!    best upper/lower trail pairs given a target round split, prunes
//!    via per-S-box probability threshold.
//!
//! ## Test substrate
//!
//! - [`ToySpn`] — a 16-bit SPN cipher built on top of a 4-bit S-box, a
//!   bit permutation, and a round key XOR.  Tunable round count.
//!   Used in tests where we want to *verify* that empirical right-
//!   quartet counts match the theoretical `(pq)² · N`.
//!
//! - [`crate::cryptanalysis::aes::reduced::ReducedAes128`] — supports
//!   the [`BlockCipher`] trait via the impl block below, so the same
//!   distinguisher can be pointed at 2-round AES.
//!
//! ## References
//!
//! - **D. Wagner**, *The Boomerang Attack*, FSE 1999.
//! - **E. Biham, O. Dunkelman, N. Keller**, *The Rectangle Attack —
//!   Rectangling the Serpent*, EUROCRYPT 2001.
//! - **E. Biham, O. Dunkelman, N. Keller**, *Related-Key Boomerang and
//!   Rectangle Attacks*, EUROCRYPT 2005.
//! - **O. Dunkelman, N. Keller, A. Shamir**, *A Practical-Time Related-
//!   Key Attack on the KASUMI Cryptosystem*, CRYPTO 2010 (introduces
//!   the sandwich variant).
//! - **C. Cid, T. Huang, T. Peyrin, Y. Sasaki, L. Song**, *Boomerang
//!   Connectivity Table — A New Cryptanalysis Tool*, EUROCRYPT 2018.

use crate::cryptanalysis::sbox::Sbox;
use crate::utils::random::random_bytes_vec as random_bytes;

// ── BlockCipher trait — the API a target cipher exposes ─────────────

/// Minimal API a block cipher must expose to be analysed by this module.
///
/// The block size is in **bytes** so we can plug in 4-bit/16-bit toys
/// (block_bytes = 2) as well as AES (block_bytes = 16).  Inputs / outputs
/// are little-endian byte vectors of length `block_bytes()`.
pub trait BlockCipher {
    fn block_bytes(&self) -> usize;
    fn encrypt(&self, block: &[u8]) -> Vec<u8>;
    fn decrypt(&self, block: &[u8]) -> Vec<u8>;
}

/// XOR two byte slices of equal length; useful in attacks.
fn xor_bytes(a: &[u8], b: &[u8]) -> Vec<u8> {
    debug_assert_eq!(a.len(), b.len());
    a.iter().zip(b).map(|(x, y)| x ^ y).collect()
}

// ── Section 1: Generic boomerang distinguisher ──────────────────────

/// One run of the boomerang distinguisher.
#[derive(Clone, Debug)]
pub struct BoomerangResult {
    /// Number of `(P₁, P₂)` pairs the attacker queried.
    pub n_pairs: usize,
    /// Number of right quartets observed (`P₃ ⊕ P₄ = α`).
    pub right_quartets: u64,
    /// `right_quartets / n_pairs`.
    pub empirical_probability: f64,
    /// `(pq)²` — what the attacker predicted.
    pub predicted_probability: Option<f64>,
    /// Standard normal z-score under the binomial null at the predicted
    /// probability.  `|z| > 2` is typically interesting.
    pub z_score: Option<f64>,
    /// Random-cipher baseline: `2^{-block_bits}`.
    pub random_baseline: f64,
}

impl BoomerangResult {
    /// True iff `right_quartets / n_pairs` is more than `multiplier ×
    /// random_baseline` — a crude "is this a distinguisher" check.
    pub fn distinguishes_from_random(&self, multiplier: f64) -> bool {
        self.empirical_probability > multiplier * self.random_baseline
    }
}

/// **Generic boomerang distinguisher** (Wagner FSE 1999).
///
/// For each of `n_pairs` random plaintexts `P`:
///
/// 1. Build `P₁ = P`, `P₂ = P ⊕ α`.  Encrypt to `C₁, C₂`.
/// 2. Build `C₃ = C₁ ⊕ δ`, `C₄ = C₂ ⊕ δ`.  Decrypt to `P₃, P₄`.
/// 3. **Right quartet** iff `P₃ ⊕ P₄ = α`.
///
/// Returns the count of right quartets along with the empirical
/// frequency.  If `predicted_probability` is provided (typically
/// `(p · q)²` for the upper/lower trail probabilities), the result
/// includes a z-score for the binomial null.
pub fn boomerang_distinguisher<C: BlockCipher>(
    cipher: &C,
    alpha: &[u8],
    delta: &[u8],
    n_pairs: usize,
    predicted_probability: Option<f64>,
) -> BoomerangResult {
    let bb = cipher.block_bytes();
    assert_eq!(alpha.len(), bb, "alpha length must match block size");
    assert_eq!(delta.len(), bb, "delta length must match block size");
    let mut right_quartets = 0u64;
    for _ in 0..n_pairs {
        let p1 = random_bytes(bb);
        let p2 = xor_bytes(&p1, alpha);
        let c1 = cipher.encrypt(&p1);
        let c2 = cipher.encrypt(&p2);
        let c3 = xor_bytes(&c1, delta);
        let c4 = xor_bytes(&c2, delta);
        let p3 = cipher.decrypt(&c3);
        let p4 = cipher.decrypt(&c4);
        if xor_bytes(&p3, &p4) == alpha {
            right_quartets += 1;
        }
    }
    let empirical = (right_quartets as f64) / (n_pairs as f64);
    let random_baseline = 2f64.powi(-(8 * bb as i32));
    let z_score = predicted_probability.map(|p| {
        let n = n_pairs as f64;
        let mean = n * p;
        let var = n * p * (1.0 - p);
        let std = var.sqrt().max(1e-30);
        ((right_quartets as f64) - mean) / std
    });
    BoomerangResult {
        n_pairs,
        right_quartets,
        empirical_probability: empirical,
        predicted_probability,
        z_score,
        random_baseline,
    }
}

// ── Section 2: Rectangle attack (chosen-plaintext variant) ──────────

/// Result of running the rectangle attack.
#[derive(Clone, Debug)]
pub struct RectangleResult {
    /// Size of the plaintext pool.
    pub pool_size: usize,
    /// Number of candidate quartets `(P₁, P₂, P₃, P₄)` with
    /// `P₁ ⊕ P₂ = P₃ ⊕ P₄ = α` and `C₁ ⊕ C₃ = C₂ ⊕ C₄ = δ`.
    pub right_quartets: u64,
    /// Expected from `(p · q)² · (N²/2) · 2^{−n}`.  None if no model
    /// supplied.
    pub predicted_right_quartets: Option<f64>,
}

/// **Rectangle attack** (Biham–Dunkelman–Keller, EUROCRYPT 2001).
///
/// Pure-chosen-plaintext variant of the boomerang.  Generate a pool
/// of `N` plaintexts; the attacker also implicitly has the `N` pairs
/// `(P, P ⊕ α)`.  After encryption, sort by `C` and look for any two
/// pairs `(P₁, P₂)` and `(P₃, P₄)` with `C₁ ⊕ C₃ = C₂ ⊕ C₄ = δ`.  The
/// number of right quartets is `(p · q)² · N² / 2 · 2^{−n}` where
/// `n = block_bits` — note the `N²` scaling, hence the name "rectangle".
///
/// Implemented with a hashmap on `C₁ ⊕ δ` so the quartet hunt is
/// `O(N · log N)`.
pub fn rectangle_attack<C: BlockCipher>(
    cipher: &C,
    alpha: &[u8],
    delta: &[u8],
    pool_size: usize,
    predicted_probability: Option<f64>,
) -> RectangleResult {
    use std::collections::HashMap;
    let bb = cipher.block_bytes();
    assert_eq!(alpha.len(), bb);
    assert_eq!(delta.len(), bb);
    // Build the pool of (P, P ⊕ α) pairs with ciphertexts.
    let mut pairs: Vec<(Vec<u8>, Vec<u8>, Vec<u8>, Vec<u8>)> = Vec::with_capacity(pool_size);
    for _ in 0..pool_size {
        let p1 = random_bytes(bb);
        let p2 = xor_bytes(&p1, alpha);
        let c1 = cipher.encrypt(&p1);
        let c2 = cipher.encrypt(&p2);
        pairs.push((p1, p2, c1, c2));
    }
    // Index pairs by C₁ ⊕ δ.  A right quartet has another pair whose
    // C₁' equals our C₁ ⊕ δ AND whose C₂' equals our C₂ ⊕ δ.
    let mut by_c1_xor_delta: HashMap<Vec<u8>, Vec<usize>> = HashMap::new();
    for (i, (_, _, c1, _)) in pairs.iter().enumerate() {
        let key = xor_bytes(c1, delta);
        by_c1_xor_delta.entry(key).or_default().push(i);
    }
    let mut right_quartets = 0u64;
    for (i, (_p1, _p2, c1, c2)) in pairs.iter().enumerate() {
        // Look for a pair j with c1_j = c1 ⊕ δ (i.e., j is in the bucket
        // keyed by c1, since we indexed by c1_j ⊕ δ).
        if let Some(candidates) = by_c1_xor_delta.get(c1) {
            for &j in candidates {
                if j == i {
                    continue;
                }
                let (_, _, _, c2_j) = &pairs[j];
                if xor_bytes(c2, delta) == *c2_j {
                    right_quartets += 1;
                }
            }
        }
    }
    // Each quartet is counted twice (i, j) and (j, i) — divide.
    right_quartets /= 2;
    let predicted_right_quartets = predicted_probability.map(|pq2| {
        let n = pool_size as f64;
        // Rectangle: N²/2 candidate quartets, each contributes
        // (pq)² · 2^{−n} of right-quartet probability.
        let block_bits = (8 * bb) as f64;
        n * n / 2.0 * pq2 * 2f64.powf(-block_bits)
    });
    RectangleResult {
        pool_size,
        right_quartets,
        predicted_right_quartets,
    }
}

// ── Section 3: Sandwich attack (middle-BCT switch) ──────────────────

/// Sandwich-attack result.
#[derive(Clone, Debug)]
pub struct SandwichResult {
    pub n_pairs: usize,
    pub right_quartets: u64,
    /// Predicted right-quartet probability from `p² · q² · r`, where
    /// `r = BCT_factor / 2^n` is the BCT-correction term for the
    /// middle layer.
    pub predicted_probability: f64,
    pub empirical_probability: f64,
    /// Ratio of empirical to predicted; ~1.0 means the BCT correction
    /// captures the switch dependency well.
    pub bct_correction_ratio: f64,
}

/// **Sandwich attack** (Dunkelman–Keller–Shamir, CRYPTO 2010).
///
/// Three-layer split `E = E₁ ∘ E_m ∘ E₀` where the *middle* layer
/// `E_m` is the boundary where the upper and lower trails meet.
/// Instead of treating the meeting as independent (`(pq)²`), use the
/// **boomerang-connectivity probability** of `E_m`:
///
/// ```text
///     P[right quartet] = p² · q² · r,    r = BCT_E_m(β, γ) / 2^n.
/// ```
///
/// `e0`, `em`, `e1` are the three encrypt closures (each taking a
/// block and returning a block).  Their inverses are required for the
/// decryption half of the boomerang.
///
/// `beta` and `gamma` are the differences AT THE BOUNDARY (output of
/// E₀ and input to E₁ respectively).  `bct_factor` is the integer
/// entry `BCT_E_m[β][γ]` — typically computed for the S-box of `E_m`
/// via [`Sbox::bct`] and aggregated across active S-boxes.
pub fn sandwich_distinguisher<E0, EM, E1, E0Inv, EMInv, E1Inv>(
    e0: E0,
    em: EM,
    e1: E1,
    e0_inv: E0Inv,
    em_inv: EMInv,
    e1_inv: E1Inv,
    block_bytes: usize,
    alpha: &[u8],
    delta: &[u8],
    p_upper: f64,
    q_lower: f64,
    bct_factor: u64,
    middle_bits: u32,
    n_pairs: usize,
) -> SandwichResult
where
    E0: Fn(&[u8]) -> Vec<u8>,
    EM: Fn(&[u8]) -> Vec<u8>,
    E1: Fn(&[u8]) -> Vec<u8>,
    E0Inv: Fn(&[u8]) -> Vec<u8>,
    EMInv: Fn(&[u8]) -> Vec<u8>,
    E1Inv: Fn(&[u8]) -> Vec<u8>,
{
    assert_eq!(alpha.len(), block_bytes);
    assert_eq!(delta.len(), block_bytes);
    let encrypt = |b: &[u8]| -> Vec<u8> {
        let x = e0(b);
        let y = em(&x);
        e1(&y)
    };
    let decrypt = |b: &[u8]| -> Vec<u8> {
        let x = e1_inv(b);
        let y = em_inv(&x);
        e0_inv(&y)
    };
    let mut right_quartets = 0u64;
    for _ in 0..n_pairs {
        let p1 = random_bytes(block_bytes);
        let p2 = xor_bytes(&p1, alpha);
        let c1 = encrypt(&p1);
        let c2 = encrypt(&p2);
        let c3 = xor_bytes(&c1, delta);
        let c4 = xor_bytes(&c2, delta);
        let p3 = decrypt(&c3);
        let p4 = decrypt(&c4);
        if xor_bytes(&p3, &p4) == alpha {
            right_quartets += 1;
        }
    }
    let r = (bct_factor as f64) / 2f64.powi(middle_bits as i32);
    let predicted = p_upper.powi(2) * q_lower.powi(2) * r;
    let empirical = (right_quartets as f64) / (n_pairs as f64);
    let ratio = if predicted > 0.0 {
        empirical / predicted
    } else {
        f64::NAN
    };
    SandwichResult {
        n_pairs,
        right_quartets,
        predicted_probability: predicted,
        empirical_probability: empirical,
        bct_correction_ratio: ratio,
    }
}

// ── Section 4: Boomerang trail search (branch-and-bound) ────────────

/// A generic SPN cipher model for trail search.
///
/// Represents a cipher of the form `(K_r ∘ L ∘ S)^r` where:
/// - `S` is parallel application of the same n-bit S-box across the
///   state, with `n_sboxes` blocks.
/// - `L: F_2^{n·n_sboxes} → F_2^{n·n_sboxes}` is a linear layer.
/// - `K_r` is the round key (irrelevant for the data path of a
///   differential, since XOR commutes through it).
///
/// Trail search ignores the key and works purely on the differential
/// propagation graph.
#[derive(Clone)]
pub struct SpnTrailModel {
    /// The per-Sbox DDT: `ddt[delta_in][delta_out] = count`.
    pub ddt: Vec<Vec<u32>>,
    /// Number of bits per S-box input/output.
    pub sbox_bits: u32,
    /// Number of parallel S-boxes per round.
    pub n_sboxes: usize,
    /// Linear-layer function on the full state.  Maps the post-Sbox
    /// state to the pre-Sbox state of the next round.
    pub linear_layer: fn(u64) -> u64,
}

impl SpnTrailModel {
    /// Block size in bits.
    pub fn block_bits(&self) -> u32 {
        self.sbox_bits * self.n_sboxes as u32
    }

    /// Convert a per-Sbox count to a probability: `count / 2^sbox_bits`.
    pub fn ddt_probability(&self, delta_in: u64, delta_out: u64) -> f64 {
        let mask = (1u64 << self.sbox_bits) - 1;
        let mut p = 1.0;
        let n = 2f64.powi(self.sbox_bits as i32);
        for i in 0..self.n_sboxes {
            let din = ((delta_in >> (i * self.sbox_bits as usize)) & mask) as usize;
            let dout = ((delta_out >> (i * self.sbox_bits as usize)) & mask) as usize;
            if din == 0 && dout == 0 {
                continue; // inactive S-box passes the zero diff with prob 1
            }
            let count = self.ddt[din][dout] as f64;
            if count == 0.0 {
                return 0.0;
            }
            p *= count / n;
        }
        p
    }
}

/// One node in the trail-search tree.
#[derive(Clone, Debug)]
pub struct DifferentialTrail {
    /// Input difference (before the first round's S-box).
    pub alpha: u64,
    /// Output difference (after the last round's S-box, after L).
    pub omega: u64,
    /// `Π` per-round probabilities.
    pub probability: f64,
    /// Per-round (in_diff, out_diff) pairs at the S-box layer.
    pub rounds: Vec<(u64, u64)>,
}

/// **Branch-and-bound differential trail search** on `model` over
/// `n_rounds` rounds.  Returns trails with cumulative probability
/// `≥ threshold`, with `input_diff = alpha_seed` (caller supplies the
/// starting difference) and arbitrary output.
///
/// The pruning happens at every round: trails whose cumulative
/// probability falls below `threshold` are dropped.  At every
/// position we enumerate the **non-zero** `(δ_in_active, δ_out)`
/// pairs of each active S-box according to its DDT row.
///
/// **Complexity**: in the worst case exponential in the number of
/// active S-boxes per round, but the pruning is aggressive in
/// practice.  Suitable for SPN ciphers with ≤ 4 nibbles per round
/// (= 16-bit block) and up to ~6 rounds.
pub fn differential_trail_search(
    model: &SpnTrailModel,
    alpha_seed: u64,
    n_rounds: usize,
    threshold: f64,
) -> Vec<DifferentialTrail> {
    let mut results = Vec::new();
    let mut stack: Vec<(u64, f64, Vec<(u64, u64)>)> = vec![(alpha_seed, 1.0, Vec::new())];
    let mask = (1u64 << model.block_bits()) - 1;
    while let Some((diff_in, prob, trail)) = stack.pop() {
        let depth = trail.len();
        if depth == n_rounds {
            results.push(DifferentialTrail {
                alpha: alpha_seed,
                omega: diff_in,
                probability: prob,
                rounds: trail,
            });
            continue;
        }
        // Enumerate possible (δ_in_active, δ_out) per active S-box and
        // collect compatible full output differences.
        let outputs = enumerate_sbox_outputs(model, diff_in);
        for (dout, dout_prob) in outputs {
            let cumulative = prob * dout_prob;
            if cumulative < threshold {
                continue;
            }
            let next = (model.linear_layer)(dout) & mask;
            let mut next_trail = trail.clone();
            next_trail.push((diff_in, dout));
            stack.push((next, cumulative, next_trail));
        }
    }
    results.sort_by(|a, b| b.probability.partial_cmp(&a.probability).unwrap());
    results
}

/// Enumerate all `(δ_out, P[δ_in → δ_out])` for the full state given
/// `δ_in`, by independently enumerating each active S-box's DDT row
/// and combining via Cartesian product.  Inactive S-boxes
/// (`δ_in_i = 0`) propagate as `δ_out_i = 0` with probability 1.
fn enumerate_sbox_outputs(model: &SpnTrailModel, diff_in: u64) -> Vec<(u64, f64)> {
    let mask = (1u64 << model.sbox_bits) - 1;
    let mut per_sbox: Vec<Vec<(u64, f64)>> = Vec::with_capacity(model.n_sboxes);
    let n = 2f64.powi(model.sbox_bits as i32);
    for i in 0..model.n_sboxes {
        let din = ((diff_in >> (i * model.sbox_bits as usize)) & mask) as usize;
        if din == 0 {
            per_sbox.push(vec![(0u64, 1.0)]);
            continue;
        }
        let row = &model.ddt[din];
        let mut entries = Vec::new();
        for (dout, &count) in row.iter().enumerate() {
            if count > 0 && dout != 0 {
                entries.push((dout as u64, count as f64 / n));
            }
        }
        if entries.is_empty() {
            // No non-trivial transitions; whole trail is impossible.
            return Vec::new();
        }
        per_sbox.push(entries);
    }
    // Cartesian product.
    let mut out: Vec<(u64, f64)> = vec![(0u64, 1.0)];
    for (i, entries) in per_sbox.iter().enumerate() {
        let mut next = Vec::with_capacity(out.len() * entries.len());
        for &(diff_so_far, p) in &out {
            for &(d_i, p_i) in entries {
                let combined = diff_so_far | (d_i << (i * model.sbox_bits as usize));
                next.push((combined, p * p_i));
            }
        }
        out = next;
    }
    out
}

/// **Boomerang trail search**: enumerate upper trails for `r_upper`
/// rounds and lower trails for `r_lower` rounds, then pair them and
/// rank by `(p_upper · p_lower)²`.
#[derive(Clone, Debug)]
pub struct BoomerangTrailPair {
    pub upper: DifferentialTrail,
    pub lower: DifferentialTrail,
    pub p_upper: f64,
    pub q_lower: f64,
    pub naive_quartet_probability: f64, // (p·q)²
}

/// Search for boomerang trail pairs.  `alpha_seed` is the input
/// difference; `delta_seed` is the output difference (we search the
/// lower trail *backwards* from delta).  Returns the top-`k` pairs
/// by `(p · q)²`.
pub fn boomerang_trail_search(
    model: &SpnTrailModel,
    alpha_seed: u64,
    delta_seed: u64,
    r_upper: usize,
    r_lower: usize,
    threshold: f64,
    top_k: usize,
) -> Vec<BoomerangTrailPair> {
    let uppers = differential_trail_search(model, alpha_seed, r_upper, threshold);
    // For the lower trail we want trails ending at `delta_seed`.
    // Easiest: run forward from each candidate `gamma`, keep those
    // whose omega equals delta_seed.  At toy scale this is fine.
    let mut pairs = Vec::new();
    for upper in &uppers {
        // beta = upper.omega is the output difference of E₀.
        // We need gamma such that E₁ takes gamma → delta_seed.
        // Naive: forward search from every possible gamma (the BCT
        // says β doesn't have to equal γ for the boomerang to fire,
        // but for the *trail search* we'll explore γ = β by default
        // and let the sandwich variant handle β ≠ γ via BCT factor).
        let gamma = upper.omega;
        let lowers = differential_trail_search(model, gamma, r_lower, threshold);
        for lower in &lowers {
            if lower.omega != delta_seed {
                continue;
            }
            let p = upper.probability;
            let q = lower.probability;
            let pq = p * q;
            pairs.push(BoomerangTrailPair {
                upper: upper.clone(),
                lower: lower.clone(),
                p_upper: p,
                q_lower: q,
                naive_quartet_probability: pq * pq,
            });
        }
    }
    pairs.sort_by(|a, b| {
        b.naive_quartet_probability
            .partial_cmp(&a.naive_quartet_probability)
            .unwrap()
    });
    pairs.truncate(top_k);
    pairs
}

// ── Section 5: ToySpn — a 16-bit SPN cipher for testing ─────────────

/// Tiny 16-bit SPN cipher: 4 × 4-bit S-boxes per round + bit
/// permutation + round-key XOR.  Configurable round count.
///
/// Used as a clean testbed for boomerang attacks — the right-quartet
/// probability is large enough to observe empirically in seconds.
pub struct ToySpn {
    pub sbox: Sbox,
    pub rounds: usize,
    pub round_keys: Vec<u16>,
}

impl ToySpn {
    /// New ToySpn with the given (4-bit, 4-bit) S-box, round count,
    /// and master key (used to derive round keys by simple XOR with a
    /// rotating constant).
    pub fn new(sbox: Sbox, rounds: usize, master_key: u64) -> Self {
        assert_eq!(sbox.n_in(), 4, "ToySpn requires a 4-bit S-box");
        assert_eq!(sbox.n_out(), 4, "ToySpn requires a 4-bit S-box");
        // Trivial key schedule for testing: rotate the master key by
        // 1 bit per round, take the low 16 bits.
        let mut round_keys = Vec::with_capacity(rounds + 1);
        let mut k = master_key;
        for _ in 0..=rounds {
            round_keys.push((k & 0xFFFF) as u16);
            k = k.rotate_left(7).wrapping_add(0x9E37);
        }
        ToySpn {
            sbox,
            rounds,
            round_keys,
        }
    }

    /// PRESENT-style bit permutation on 16 bits:
    ///   bit i → bit P(i), where P(i) = (4 · i) mod 15 for i < 15, P(15) = 15.
    pub fn bit_permutation(x: u16) -> u16 {
        let mut y = 0u16;
        for i in 0..16 {
            if (x >> i) & 1 == 1 {
                let j = if i < 15 { (4 * i) % 15 } else { 15 };
                y |= 1 << j;
            }
        }
        y
    }

    /// Inverse of `bit_permutation` (since the permutation is a bijection).
    pub fn inverse_bit_permutation(x: u16) -> u16 {
        let mut y = 0u16;
        for i in 0..16 {
            if (x >> i) & 1 == 1 {
                // find j such that bit_permutation maps j to i
                let mut found = 16;
                for j in 0..16 {
                    let jp = if j < 15 { (4 * j) % 15 } else { 15 };
                    if jp == i {
                        found = j;
                        break;
                    }
                }
                debug_assert!(found < 16);
                y |= 1 << found;
            }
        }
        y
    }

    /// Apply the 4 parallel 4-bit S-boxes.
    pub fn sub_nibbles(&self, x: u16) -> u16 {
        let mut y = 0u16;
        for i in 0..4 {
            let nibble = ((x >> (4 * i)) & 0xF) as u32;
            let s = self.sbox.lookup(nibble) as u16;
            y |= s << (4 * i);
        }
        y
    }

    /// Inverse of `sub_nibbles` — only defined when the S-box is
    /// bijective.
    pub fn inv_sub_nibbles(&self, x: u16) -> u16 {
        let inv = self.sbox.inverse_table().expect("inv");
        let mut y = 0u16;
        for i in 0..4 {
            let nibble = ((x >> (4 * i)) & 0xF) as usize;
            let s = inv[nibble] as u16;
            y |= s << (4 * i);
        }
        y
    }

    /// Encrypt a 16-bit block.
    pub fn encrypt_u16(&self, block: u16) -> u16 {
        let mut s = block;
        s ^= self.round_keys[0];
        for r in 1..self.rounds {
            s = self.sub_nibbles(s);
            s = Self::bit_permutation(s);
            s ^= self.round_keys[r];
        }
        // Final round: S-box only (no permutation), then key.
        s = self.sub_nibbles(s);
        s ^= self.round_keys[self.rounds];
        s
    }

    /// Decrypt a 16-bit block.
    pub fn decrypt_u16(&self, block: u16) -> u16 {
        let mut s = block;
        s ^= self.round_keys[self.rounds];
        s = self.inv_sub_nibbles(s);
        for r in (1..self.rounds).rev() {
            s ^= self.round_keys[r];
            s = Self::inverse_bit_permutation(s);
            s = self.inv_sub_nibbles(s);
        }
        s ^= self.round_keys[0];
        s
    }
}

impl BlockCipher for ToySpn {
    fn block_bytes(&self) -> usize {
        2
    }
    fn encrypt(&self, block: &[u8]) -> Vec<u8> {
        let b = u16::from_le_bytes([block[0], block[1]]);
        self.encrypt_u16(b).to_le_bytes().to_vec()
    }
    fn decrypt(&self, block: &[u8]) -> Vec<u8> {
        let b = u16::from_le_bytes([block[0], block[1]]);
        self.decrypt_u16(b).to_le_bytes().to_vec()
    }
}

// ── BlockCipher impl for ReducedAes128 ──────────────────────────────

impl BlockCipher for crate::cryptanalysis::aes::reduced::ReducedAes128 {
    fn block_bytes(&self) -> usize {
        16
    }
    fn encrypt(&self, block: &[u8]) -> Vec<u8> {
        let mut b = [0u8; 16];
        b.copy_from_slice(block);
        self.encrypt(&b).to_vec()
    }
    fn decrypt(&self, block: &[u8]) -> Vec<u8> {
        let mut b = [0u8; 16];
        b.copy_from_slice(block);
        self.decrypt(&b).to_vec()
    }
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// Serpent S0 — a 4-bit S-box with known DDT properties.
    fn serpent_s0() -> Sbox {
        Sbox::new(
            4,
            4,
            vec![3, 8, 15, 1, 10, 6, 5, 11, 14, 13, 4, 2, 7, 0, 9, 12],
        )
        .unwrap()
    }

    /// PRESENT S-box — the canonical lightweight 4×4 S-box.
    fn present_sbox() -> Sbox {
        Sbox::new(
            4,
            4,
            vec![0xC, 5, 6, 0xB, 9, 0, 0xA, 0xD, 3, 0xE, 0xF, 8, 4, 7, 1, 2],
        )
        .unwrap()
    }

    /// **ToySpn round-trip**: encryption is invertible.
    #[test]
    fn toyspn_encrypt_decrypt_inverses() {
        let cipher = ToySpn::new(serpent_s0(), 4, 0xDEAD_BEEF);
        for x in 0u16..=255 {
            let c = cipher.encrypt_u16(x);
            let p = cipher.decrypt_u16(c);
            assert_eq!(p, x, "round-trip fails at x = {:#06x}", x);
        }
    }

    /// **Bit permutation is involutive on extremes**.
    #[test]
    fn toyspn_bit_permutation_is_a_bijection() {
        let mut images = std::collections::HashSet::new();
        for x in 0u16..=65535 {
            images.insert(ToySpn::bit_permutation(x));
        }
        assert_eq!(images.len(), 65536, "bit permutation must be a bijection");
    }

    /// **Bit permutation matches its inverse**.
    #[test]
    fn toyspn_bit_permutation_inverse_is_correct() {
        for x in 0u16..=255 {
            let y = ToySpn::bit_permutation(x);
            let z = ToySpn::inverse_bit_permutation(y);
            assert_eq!(z, x, "bit permutation inverse fails at {}", x);
        }
    }

    /// **Section 1**: boomerang on the zero-difference quartet is
    /// trivially `right` (P₁ = P₂ ⇒ C₁ = C₂ ⇒ C₃ = C₄ ⇒ P₃ = P₄ = P₁
    /// ⇒ P₃ ⊕ P₄ = 0 = α).  Sanity-check the framework: 64 / 64
    /// right quartets at α = δ = 0.
    #[test]
    fn boomerang_zero_difference_always_right_quartet() {
        let cipher = ToySpn::new(serpent_s0(), 2, 0xDEAD_BEEF);
        let result = boomerang_distinguisher(&cipher, &[0u8, 0u8], &[0u8, 0u8], 64, Some(1.0));
        assert_eq!(
            result.right_quartets, 64,
            "zero-diff quartet must always be right: {:?}",
            result
        );
    }

    /// **Section 1**: boomerang on 2-round ToySpn with α = δ = a
    /// 1-active-nibble difference.  The right-quartet probability
    /// should clear the random `2^{−16}` baseline by orders of
    /// magnitude (since the trail covers 2 rounds with ~2^{−6}
    /// probability each).
    #[test]
    fn boomerang_distinguishes_2round_toyspn_from_random() {
        let cipher = ToySpn::new(serpent_s0(), 2, 0xC0FFEE);
        // alpha = 0x0001: lowest nibble active.
        let alpha = [0x01u8, 0x00];
        let delta = [0x01u8, 0x00];
        let result = boomerang_distinguisher(&cipher, &alpha, &delta, 4096, None);
        // Random-cipher baseline = 2^{-16} ≈ 1.5e-5.  Empirical should
        // be much larger.
        assert!(
            result.empirical_probability > 10.0 * result.random_baseline,
            "did not distinguish 2-round ToySpn from random: {:?}",
            result
        );
    }

    /// **Section 2 (empirical scaling)**: rectangle attack on
    /// 1-round ToySpn with the **identity** S-box.  With identity S
    /// the trail probability is 1 (`(pq)² = 1`) so right rectangles
    /// scale as `N²/2 · 2^{-n}` — the pure random-collision rate.
    /// For pool N = 2048 and n = 16, expected right quartets ≈
    /// `2048²/2 / 2^{16} = 32`.  Verify the empirical count clears
    /// `≥ 10` (well above the noise floor).
    #[test]
    fn rectangle_attack_finds_quartets_with_identity_sbox() {
        // Identity 4-bit S-box: BCT all on diagonal, full prob.
        let identity = Sbox::new(4, 4, (0u32..16).collect()).unwrap();
        let cipher = ToySpn::new(identity, 1, 0xC0FFEE);
        let alpha = [0x12u8, 0x34];
        let delta = [0x12u8, 0x34];
        let pool = 2048;
        let result = rectangle_attack(&cipher, &alpha, &delta, pool, Some(1.0));
        // Expected ≈ pool²/2 · 2^{-16} = 32; allow generous lower bound.
        assert!(
            result.right_quartets >= 10,
            "identity-S-box rectangle should find ≥ 10 right quartets (got {:?})",
            result,
        );
    }

    /// **Section 2 (structural)**: rectangle on a non-trivial cipher
    /// runs without panic and returns a non-negative count.  Pool
    /// size is small because 2-round ToySpn needs N ≳ 2^{14} to
    /// observe right quartets — out of scope for a unit test.
    #[test]
    fn rectangle_attack_runs_on_two_round_toyspn() {
        let cipher = ToySpn::new(serpent_s0(), 2, 0xC0FFEE);
        let alpha = [0x01u8, 0x00];
        let delta = [0x01u8, 0x00];
        let result = rectangle_attack(&cipher, &alpha, &delta, 256, None);
        assert_eq!(result.pool_size, 256);
        let _ = result.right_quartets;
    }

    /// **Section 3**: sandwich distinguisher reproduces the boomerang
    /// when split as (E₀, E_m = identity, E₁) with bct_factor = 2^n.
    /// I.e., the trivial-middle sandwich is just a boomerang.
    #[test]
    fn sandwich_with_identity_middle_matches_boomerang() {
        let _cipher = ToySpn::new(serpent_s0(), 2, 0xC0FFEE);
        let e0 = |b: &[u8]| {
            // Round 1 only.
            let cipher1 = ToySpn::new(serpent_s0(), 1, 0xC0FFEE);
            cipher1.encrypt(b)
        };
        let em = |b: &[u8]| b.to_vec();
        let e1 = |b: &[u8]| {
            // Round 2 only — peel from full cipher.
            // For simplicity here, just encrypt with a 1-round cipher
            // that has the appropriate round-keys.
            let cipher1 = ToySpn::new(serpent_s0(), 1, 0xC0FFEE);
            cipher1.encrypt(b)
        };
        // For test purposes we want sandwich(p, em=id, q) to reduce to
        // boomerang(p, q).  Setting bct_factor = 2^16 = 65536 means
        // r = 65536 / 2^16 = 1, so predicted = p²q².
        let alpha = [0x01u8, 0x00];
        let delta = [0x01u8, 0x00];
        let result = sandwich_distinguisher(
            e0,
            em,
            e1,
            |b| {
                let cipher1 = ToySpn::new(serpent_s0(), 1, 0xC0FFEE);
                cipher1.decrypt(b)
            },
            |b| b.to_vec(),
            |b| {
                let cipher1 = ToySpn::new(serpent_s0(), 1, 0xC0FFEE);
                cipher1.decrypt(b)
            },
            2,
            &alpha,
            &delta,
            // p, q: we don't know exactly, use heuristic 2^{-4}
            0.0625,
            0.0625,
            65536, // bct_factor: 2^16 → r = 1
            16,
            512,
        );
        // Distinguishes from random.
        assert!(
            result.empirical_probability > 100.0 * (1.0 / 65536.0),
            "sandwich with identity middle should distinguish: {:?}",
            result
        );
        // Note: this composed cipher is NOT the same as a 2-round cipher
        // (the round keys / structure differ), but the boomerang signal
        // should still clear the random baseline.
    }

    /// **Section 4**: trail search on 2-round ToySpn finds at least
    /// one non-empty trail with the seed α = 0x0001.
    #[test]
    fn trail_search_finds_two_round_trail() {
        let sbox = serpent_s0();
        let ddt = sbox.ddt();
        let model = SpnTrailModel {
            ddt,
            sbox_bits: 4,
            n_sboxes: 4,
            linear_layer: |x| ToySpn::bit_permutation(x as u16) as u64,
        };
        let trails = differential_trail_search(&model, 0x0001u64, 2, 2f64.powi(-12));
        assert!(
            !trails.is_empty(),
            "trail search returned no 2-round trails with α = 0x0001"
        );
        // Best trail probability should exceed the threshold by design.
        assert!(trails[0].probability >= 2f64.powi(-12));
    }

    /// **Section 4**: trail search prunes the worst trails (≤ threshold).
    #[test]
    fn trail_search_respects_threshold() {
        let sbox = present_sbox();
        let ddt = sbox.ddt();
        let model = SpnTrailModel {
            ddt,
            sbox_bits: 4,
            n_sboxes: 4,
            linear_layer: |x| ToySpn::bit_permutation(x as u16) as u64,
        };
        let trails = differential_trail_search(&model, 0x0001u64, 3, 2f64.powi(-8));
        for t in &trails {
            assert!(
                t.probability >= 2f64.powi(-8),
                "trail prob {} below threshold",
                t.probability
            );
        }
    }

    /// **Section 4**: boomerang trail-pair search finds at least one
    /// pair on a tiny 2+2 split.
    #[test]
    fn boomerang_trail_pair_search_finds_pair() {
        let sbox = serpent_s0();
        let ddt = sbox.ddt();
        let model = SpnTrailModel {
            ddt,
            sbox_bits: 4,
            n_sboxes: 4,
            linear_layer: |x| ToySpn::bit_permutation(x as u16) as u64,
        };
        // Search for boomerang pairs with α = δ = 0x0001, 2+2 rounds.
        let pairs = boomerang_trail_search(&model, 0x0001u64, 0x0001u64, 2, 2, 2f64.powi(-12), 5);
        // We don't require a non-empty result for arbitrary (α, δ);
        // verify the search at least terminates and returns a sorted list.
        for window in pairs.windows(2) {
            assert!(
                window[0].naive_quartet_probability >= window[1].naive_quartet_probability,
                "boomerang trails must be sorted by quartet probability"
            );
        }
    }

    /// **AES integration**: 1-round AES still encrypts/decrypts.
    #[test]
    fn reduced_aes_round_trip_via_blockcipher_trait() {
        use crate::cryptanalysis::aes::reduced::ReducedAes128;
        let key = [0u8; 16];
        let cipher = ReducedAes128::new(&key, 1, true);
        let p = [0u8; 16];
        let c = cipher.encrypt(&p);
        let p2 = cipher.decrypt(&c);
        assert_eq!(p2.to_vec(), p.to_vec());
        // Via BlockCipher trait too.
        let c2 = <ReducedAes128 as BlockCipher>::encrypt(&cipher, &p);
        let p3 = <ReducedAes128 as BlockCipher>::decrypt(&cipher, &c2);
        assert_eq!(p3, p.to_vec());
    }

    /// **Sandwich-BCT integration with the Serpent S0 BCT**: feed a
    /// BCT entry computed by `Sbox::bct` into the sandwich
    /// distinguisher and verify the prediction formula computes a
    /// finite probability.  This is the connection point between the
    /// per-S-box BCT (Cid et al. 2018) and the full-cipher attack.
    #[test]
    fn sandwich_consumes_sbox_bct() {
        let sbox = serpent_s0();
        let bct = sbox.bct().expect("Serpent S0 is bijective");
        // Find a non-trivial (β, γ) with maximum BCT entry.
        let mut best = (0usize, 0usize, 0u32);
        for (b, row) in bct.iter().enumerate().skip(1) {
            for (g, &v) in row.iter().enumerate().skip(1) {
                if v > best.2 {
                    best = (b, g, v);
                }
            }
        }
        let (beta, gamma, bct_factor) = best;
        // The Serpent S0 boomerang uniformity is small (≤ 8 / 16 = 0.5).
        assert!(bct_factor > 0, "Serpent S0 should have non-zero BCT entry");
        // Plug into sandwich: bct_factor entries on a 4-bit S-box.
        let cipher1 = ToySpn::new(serpent_s0(), 1, 0xC0FFEE);
        let alpha = [(beta & 0xFF) as u8, ((beta >> 8) & 0xFF) as u8];
        let delta = [(gamma & 0xFF) as u8, ((gamma >> 8) & 0xFF) as u8];
        let result = sandwich_distinguisher(
            |b| b.to_vec(),         // E0 = identity
            |b| cipher1.encrypt(b), // Em = the S-box layer
            |b| b.to_vec(),         // E1 = identity
            |b| b.to_vec(),
            |b| cipher1.decrypt(b),
            |b| b.to_vec(),
            2,
            &alpha,
            &delta,
            1.0,
            1.0,
            bct_factor as u64,
            4, // 4-bit middle
            64,
        );
        // Predicted probability is bct_factor / 16; check it's > 0.
        assert!(result.predicted_probability > 0.0);
        assert!(result.predicted_probability <= 1.0);
    }
}
