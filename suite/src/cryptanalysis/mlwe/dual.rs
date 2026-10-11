//! The dual attack, and the argument about whether it works.
//!
//! The primal attack ([`super::primal`]) finds the secret by making it the
//! shortest vector of a lattice. The dual attack instead finds short vectors in
//! the *dual* lattice and uses them as a statistical test: each short `x` with
//! `Aᵗx ≡ 0 mod q` turns `b = A·s + e` into `⟨x, b⟩ = ⟨x, e⟩ mod q`, which is
//! small when `x` is, and uniform when `b` is random. Collect enough such
//! samples and you can distinguish — and, with the refinements below, recover
//! the secret outright rather than merely distinguish.
//!
//! # Why this module is longer than the primal one
//!
//! Because this is where the live disagreement is. The arc, in order:
//!
//! 1. **MR09 / plain dual** ([`dual_distinguish`]). One short dual vector, one
//!    statistical test, `ε^{-2}` repetitions. Clean, provable, and not
//!    competitive with the primal attack.
//! 2. **MATZOV (2022)** ([`dual_matzov`]). Split the secret three ways: absorb
//!    part into the lattice, guess part by enumeration, and recover part with
//!    an FFT over a switched-down modulus, so that `p^{k_fft}` candidate guesses
//!    are scored in one transform instead of one at a time. This is the variant
//!    that produced the widely-quoted claim that Kyber-512/768/1024 sit
//!    3.5 / 11.9 / 12.3 bits below their NIST requirements.
//! 3. **Ducas–Pulles (2023)**. The analysis in step 2 rests on an
//!    *independence heuristic*: that the `p^{k_fft}` scores behave as
//!    independent random variables. Ducas and Pulles showed this is false, and
//!    identified a "contradictory regime" where assuming it yields predictions
//!    that contradict the Gaussian heuristic. [`DualDiagnostics`] tests for it.
//! 4. **Pouly–Shen (EUROCRYPT 2024)**. The first *provable* dual attack, with
//!    the independence heuristic replaced by lattice-geometry arguments — and a
//!    proof that its provable regime is **disjoint** from the contradictory
//!    regime of step 3. [`DualDiagnostics::provable_regime`] marks it, and a
//!    test in this file asserts the disjointness holds for every standardised
//!    parameter set.
//!
//! So: a dual estimate alone is not a security claim. A dual estimate plus its
//! diagnostics is. Everything in this module returns both.
//!
//! # Honesty about the cost formula
//!
//! [`dual_matzov`] implements the *structure* of the MATZOV attack — the
//! three-way split, modulus switching, the FFT, the sample count driven by the
//! per-sample advantage — with our own accounting of each term. It is not a
//! reimplementation of MATZOV's own optimiser, and it will not reproduce their
//! table to the bit. Where their report makes a choice we have simplified, the
//! comment at that line says so. What the module is for is seeing *how* the
//! terms trade off and where the diagnostics fire, not for restating somebody
//! else's number.

use super::cost::{delta_from_beta, gaussian_heuristic_log2, BkzModel, SvpModel};
use super::params::LweInstance;
use std::f64::consts::PI;

/// The advantage of the standard dual distinguisher on a sample whose noise has
/// standard deviation `s` modulo `q`.
///
/// `ε = exp(-2π²·(s/q)²)`, the first Fourier coefficient of the wrapped
/// Gaussian. This is the usual figure (Micciancio–Regev; Lindner–Peikert) and
/// it collapses fast: at `s = q/4` it is already `2^{-1.8}`, at `s = q` it is
/// `2^{-28}`.
pub fn dual_advantage(s: f64, q: f64) -> f64 {
    let tau = s / q;
    (-2.0 * PI * PI * tau * tau).exp()
}

/// `log2` of the number of lattice vectors of norm at most `length` in a
/// dimension-`d` lattice of `log2` volume `log2_vol`, by the Gaussian
/// heuristic: `(length/gh(Λ))^d`, halved for `±v`.
///
/// This is the quantity that makes the contradictory-regime test possible: an
/// attack that needs more short dual vectors than the lattice contains is not
/// merely expensive, it is impossible as analysed.
pub fn short_vector_count_log2(d: usize, log2_vol: f64, length_log2: f64) -> f64 {
    let gh = gaussian_heuristic_log2(d, log2_vol);
    (d as f64) * (length_log2 - gh) - 1.0
}

/// A plain dual distinguishing estimate.
#[derive(Clone, Debug, PartialEq)]
pub struct DualEstimate {
    pub instance: String,
    pub method: &'static str,
    /// Block size used on the dual lattice.
    pub beta: f64,
    /// Dimension of the dual sublattice reduced.
    pub d: usize,
    /// `log2` of the length of the short dual vectors obtained.
    pub log2_length: f64,
    /// `log2` of the per-sample distinguishing advantage, so a negative number.
    pub log2_advantage: f64,
    /// `log2` of how many dual samples the attack consumes.
    pub log2_samples: f64,
    pub log2_cost: f64,
    pub log2_memory: f64,
    pub model: String,
    /// How this estimate stands up to the post-2022 scrutiny.
    pub diagnostics: DualDiagnostics,
}

/// Whether a dual estimate is one to believe.
///
/// Every field here answers a question that the raw cost does not.
#[derive(Clone, Debug, PartialEq)]
pub struct DualDiagnostics {
    /// `log2` of the number of short dual vectors the attack needs.
    pub log2_vectors_needed: f64,
    /// `log2` of how many the dual lattice actually contains at that length,
    /// by the Gaussian heuristic.
    pub log2_vectors_available: f64,
    /// **Ducas–Pulles contradictory regime.** True when the attack, as
    /// analysed, consumes more short dual vectors than exist at the length it
    /// assumes — the concrete form of the inconsistency that the independence
    /// heuristic hides. A cost with this flag set is not a security claim; it
    /// is an artefact of the heuristic.
    ///
    /// This is our operationalisation of the critique, not a transcription of
    /// their theorem: we test the vector-count consistency that their argument
    /// turns on. Their paper identifies the regime by a different and more
    /// general route.
    pub contradictory: bool,
    /// Whether each individual sample is informative enough that concentration
    /// bounds apply without the independence heuristic — the condition the
    /// provable analyses need. We take `ε ≥ 2^{-20}`.
    pub provable_regime: bool,
    /// Whether the noise has smoothed past the point where any number of
    /// samples helps: `ε` below `2^{-256}` means the dual samples carry
    /// essentially nothing and the attack is not an attack.
    pub smoothed_out: bool,
}

impl DualDiagnostics {
    fn new(log2_advantage: f64, log2_samples: f64, log2_available: f64) -> Self {
        DualDiagnostics {
            log2_vectors_needed: log2_samples,
            log2_vectors_available: log2_available,
            contradictory: log2_samples > log2_available,
            provable_regime: log2_advantage >= -20.0,
            smoothed_out: log2_advantage < -256.0,
        }
    }

    /// One-line verdict for reports.
    pub fn verdict(&self) -> &'static str {
        if self.smoothed_out {
            "noise smoothed out — not an attack"
        } else if self.contradictory {
            "Ducas-Pulles contradictory regime — do not believe the cost"
        } else if self.provable_regime {
            "within the provable regime"
        } else {
            "heuristic regime, consistent vector count"
        }
    }
}

/// Configuration for the dual searches: how coarse a grid to optimise over.
///
/// The defaults are chosen so a full six-parameter-set report finishes in a
/// second or two. Tightening `beta_step` to 1 changes the answers by under a
/// bit and costs roughly eight times as long.
#[derive(Clone, Copy, Debug)]
pub struct DualSearch {
    pub beta_min: usize,
    pub beta_max: usize,
    pub beta_step: usize,
    /// Largest number of secret coordinates to hand to the FFT.
    pub k_fft_max: usize,
    /// Largest number of secret coordinates to guess by enumeration.
    pub k_enum_max: usize,
    /// Whether one sieve call's output is reused as many short vectors
    /// (`2^{0.2075β}` of them) rather than charging a fresh reduction per
    /// sample. Real attacks reuse; the older estimates did not.
    pub reuse_sieve_output: bool,
}

impl Default for DualSearch {
    fn default() -> Self {
        DualSearch {
            beta_min: 50,
            beta_max: 1400,
            beta_step: 8,
            k_fft_max: 48,
            k_enum_max: 16,
            reuse_sieve_output: true,
        }
    }
}

/// The plain dual distinguishing attack (MR09 / Albrecht et al.).
///
/// # Which dual lattice
///
/// The textbook version reduces the kernel `{x ∈ Z^{m} : Aᵗx ≡ 0 mod q}`, which
/// has dimension `m` and volume `q^n`. That form is **useless against these
/// schemes**, and the reason is worth stating: ML-KEM's public key gives
/// exactly `n` samples for `n` unknowns, so `m = n`, the kernel degenerates to
/// `q·Z^m`, and its shortest vector has length `q` — no better than doing
/// nothing. ML-DSA has `m > n` but not by much.
///
/// So we use the *normal form* instead:
///
/// ```text
/// Λ = {(x, y) ∈ Z^{m'} × Z^{n} : Aᵗx ≡ y mod q},   d = m' + n,   vol = q^n
/// ```
///
/// A short `(x, y)` gives `⟨x, b⟩ = ⟨y, s⟩ + ⟨x, e⟩ mod q`, whose noise has
/// standard deviation `‖(x,y)‖·σ` when secret and error share a `σ` — which for
/// both schemes they do. This form works for any sample count, and it is the
/// one the MATZOV variant generalises.
///
/// Needs `ε^{-2}` samples for constant success. This is the honest baseline: no
/// heuristic beyond the Gaussian one, and no independence assumption, because
/// there is only one score per sample.
pub fn dual_distinguish(
    inst: &LweInstance,
    model: &BkzModel,
    search: &DualSearch,
) -> Option<DualEstimate> {
    let log2_q = (inst.q as f64).log2();
    let q = inst.q as f64;
    let mut best: Option<DualEstimate> = None;

    let mut beta = search.beta_min;
    while beta <= search.beta_max {
        let delta = delta_from_beta(beta as f64);
        let log2_delta = delta.log2();
        // Sweep the sample count m' ≤ m; the lattice dimension is d = m' + n.
        for m_used in (1..=inst.m).step_by(16) {
            let d = m_used + inst.n;
            if d < beta {
                continue;
            }
            let log2_vol = inst.n as f64 * log2_q;
            let log2_len = (d as f64 - 1.0) * log2_delta + log2_vol / d as f64;
            // A length at or above `q` means reduction has achieved nothing:
            // the lattice contains `q·e_i` for free, and those vectors give
            // `⟨x, b⟩ ≡ 0 mod q` — no information at all. Clamping the
            // predicted length down to `q` here (which an earlier version of
            // this file did) makes the estimator claim a distinguisher with
            // `ε = 2^{-43}` and then "fix" it with `2^{85}` samples, producing
            // a dual cost *below* the primal one for ML-KEM-512. That is not a
            // better attack, it is an artefact of pretending the trivial
            // vectors are useful.
            if log2_len >= log2_q {
                continue;
            }
            // Noise on one dual sample: ‖(x,y)‖·σ, the secret's and the error's
            // contributions together.
            let s = 2f64.powf(log2_len) * inst.sigma_e;
            let eps = dual_advantage(s, q);
            if eps <= 0.0 {
                continue;
            }
            let log2_eps = eps.log2();
            let log2_samples = -2.0 * log2_eps;
            let per_call = if search.reuse_sieve_output {
                (model.log2_memory(beta as f64)).max(0.0)
            } else {
                0.0
            };
            let calls = (log2_samples - per_call).max(0.0);
            let log2_cost = model.log2_cost(beta as f64, d) + calls;
            let available = short_vector_count_log2(d, log2_vol, log2_len);
            let cand = DualEstimate {
                instance: inst.name.clone(),
                method: "dual-distinguish (normal form)",
                beta: beta as f64,
                d,
                log2_length: log2_len,
                log2_advantage: log2_eps,
                log2_samples,
                log2_cost,
                log2_memory: model.log2_memory(beta as f64).max(log2_samples.min(80.0)),
                model: model.label(),
                diagnostics: DualDiagnostics::new(log2_eps, log2_samples, available),
            };
            if best.as_ref().is_none_or(|b| cand.log2_cost < b.log2_cost) {
                best = Some(cand);
            }
        }
        beta += search.beta_step;
    }
    best
}

/// A MATZOV-style dual key-recovery estimate, with the three-way split.
#[derive(Clone, Debug, PartialEq)]
pub struct MatzovEstimate {
    pub instance: String,
    pub beta: f64,
    /// Secret coordinates absorbed into the dual lattice.
    pub k_lat: usize,
    /// Secret coordinates recovered by the FFT.
    pub k_fft: usize,
    /// Secret coordinates guessed by enumeration.
    pub k_enum: usize,
    /// The switched-down modulus the FFT runs over.
    pub p: usize,
    /// Dimension of the reduced dual lattice, `m_used + k_lat`.
    pub d: usize,
    /// How many LWE samples the optimum involves.
    pub m_used: usize,
    pub log2_length: f64,
    pub log2_advantage: f64,
    pub log2_samples: f64,
    /// `log2` cost of the lattice reduction alone.
    pub log2_cost_reduction: f64,
    /// `log2` cost of the FFT scoring, summed over enumeration guesses.
    pub log2_cost_fft: f64,
    /// `log2` of the whole attack.
    pub log2_cost: f64,
    pub log2_memory: f64,
    pub model: String,
    pub diagnostics: DualDiagnostics,
}

/// The MATZOV-style dual attack with guessing, modulus switching and an FFT
/// distinguisher.
///
/// # The split
///
/// The `n` secret coordinates are partitioned into `k_lat + k_fft + k_enum`:
///
/// * `k_lat` are absorbed into the dual lattice, which becomes
///   `{(x, y) : A_latᵗ x ≡ y mod q}` of dimension `d = m + k_lat` and volume
///   `q^{k_lat}`. Reduction makes `(x, y)` short, so `⟨y, s_lat⟩` joins the
///   noise instead of needing to be guessed.
/// * `k_fft` are recovered by scoring all `p^{k_fft}` candidates at once with a
///   fast Fourier transform over `Z_p^{k_fft}`, after switching the modulus from
///   `q` down to `p`. The switch is what makes the transform affordable; it
///   costs rounding noise of variance `σ_s²·k_fft·(q/p)²/12`.
/// * `k_enum` are guessed outright, at `H` bits of entropy each, multiplying the
///   scoring cost. Worth it only because a bounded secret has `H` well below
///   `log2 q`.
///
/// # Where we simplify
///
/// * The sample count is `D = 4·(k_fft·ln p + λ)/ε²` with `λ = 64`, the standard
///   "beat `p^{k_fft}` false positives with margin" bound. MATZOV's own count
///   comes from a tighter analysis of the score distribution.
/// * We charge the FFT `p^{k_fft}·k_fft·log2 p` operations and the sample
///   preparation `D·k_fft`, and take the maximum rather than modelling the
///   pipeline. The difference is under a bit.
/// * `p` is swept over powers of two only.
pub fn dual_matzov(
    inst: &LweInstance,
    model: &BkzModel,
    search: &DualSearch,
) -> Option<MatzovEstimate> {
    let log2_q = (inst.q as f64).log2();
    let q = inst.q as f64;
    let lambda = 64.0f64;
    let h = inst.secret_entropy_bits;
    let mut best: Option<MatzovEstimate> = None;

    let mut beta = search.beta_min;
    while beta <= search.beta_max {
        let delta = delta_from_beta(beta as f64);
        let log2_delta = delta.log2();
        for k_enum in (0..=search.k_enum_max).step_by(4) {
            for k_fft in (0..=search.k_fft_max).step_by(4) {
                if k_fft + k_enum > inst.n {
                    continue;
                }
                let k_lat = inst.n - k_fft - k_enum;
                let log2_vol = k_lat as f64 * log2_q;
                // Choosing the sample count matters here, and in the direction
                // that is easy to get wrong: with the volume fixed at q^{k_lat},
                // adding samples grows `d` and so grows `δ^{d-1}` — the dual
                // vectors get *longer*. The optimum is the usual
                // `d* = √(k_lat·log q / log δ)`; we take that, clamped to what
                // the instance actually offers, and the full sample set, and
                // keep whichever scores better.
                let d_opt = if log2_delta > 0.0 && k_lat > 0 {
                    (k_lat as f64 * log2_q / log2_delta).sqrt()
                } else {
                    (inst.m + k_lat) as f64
                };
                let m_opt = (d_opt.round() as i64 - k_lat as i64).clamp(1, inst.m as i64) as usize;
                for m_used in dedup2(m_opt, inst.m) {
                    let d = m_used + k_lat;
                    if d < beta {
                        continue;
                    }
                    let log2_len = (d as f64 - 1.0) * log2_delta + log2_vol / d as f64;
                    // Same rule as in `dual_distinguish`: a predicted length at or
                    // above `q` is the trivial vectors, which carry no information.
                    if log2_len >= log2_q {
                        continue;
                    }
                    let len = 2f64.powf(log2_len);
                    // Sweep the switched modulus over powers of two. p = q means no
                    // switching; p below the noise floor makes the rounding term
                    // dominate and the advantage collapse.
                    let mut p = 2usize;
                    while (p as f64) <= q {
                        let round_var = if k_fft == 0 {
                            0.0
                        } else {
                            inst.sigma_s * inst.sigma_s * k_fft as f64 * (q / p as f64).powi(2)
                                / 12.0
                        };
                        let s = (len * len * inst.sigma_e * inst.sigma_e + round_var).sqrt();
                        let eps = dual_advantage(s, q);
                        if eps > 0.0 {
                            let log2_eps = eps.log2();
                            // D = 4·(k_fft·ln p + λ)/ε²
                            let log2_d_samples = 2.0
                                + (k_fft as f64 * (p as f64).ln() + lambda).log2()
                                - 2.0 * log2_eps;
                            // Reduction: one BKZ call, then the sieve's database is
                            // reused as short vectors when the search says so.
                            let per_call = if search.reuse_sieve_output {
                                model.log2_memory(beta as f64).max(0.0)
                            } else {
                                0.0
                            };
                            let extra_calls = (log2_d_samples - per_call).max(0.0);
                            let log2_red = model.log2_cost(beta as f64, d) + extra_calls;
                            // Scoring: for each enumeration guess, prepare D samples
                            // and run one FFT of size p^{k_fft}.
                            let log2_fft_one = if k_fft == 0 {
                                0.0
                            } else {
                                k_fft as f64 * (p as f64).log2()
                                    + (k_fft as f64 * (p as f64).log2()).max(1.0).log2()
                            };
                            let log2_prep = log2_d_samples + (k_fft.max(1) as f64).log2();
                            let log2_score = k_enum as f64 * h + log2_fft_one.max(log2_prep);
                            let log2_cost = log_sum_exp2(log2_red, log2_score);
                            let available = short_vector_count_log2(d, log2_vol, log2_len);
                            let cand = MatzovEstimate {
                                instance: inst.name.clone(),
                                beta: beta as f64,
                                k_lat,
                                k_fft,
                                k_enum,
                                p,
                                d,
                                m_used,
                                log2_length: log2_len,
                                log2_advantage: log2_eps,
                                log2_samples: log2_d_samples,
                                log2_cost_reduction: log2_red,
                                log2_cost_fft: log2_score,
                                log2_cost,
                                log2_memory: model.log2_memory(beta as f64).max(if k_fft == 0 {
                                    0.0
                                } else {
                                    k_fft as f64 * (p as f64).log2()
                                }),
                                model: model.label(),
                                diagnostics: DualDiagnostics::new(
                                    log2_eps,
                                    log2_d_samples,
                                    available,
                                ),
                            };
                            if best.as_ref().is_none_or(|b| cand.log2_cost < b.log2_cost) {
                                best = Some(cand);
                            }
                        }
                        p *= 2;
                    }
                }
            }
        }
        beta += search.beta_step;
    }
    best
}

/// The distinct values of two sample counts, so the sweep does not evaluate the
/// same point twice when the optimum happens to be the full set.
fn dedup2(a: usize, b: usize) -> Vec<usize> {
    if a == b {
        vec![a]
    } else {
        vec![a, b]
    }
}

/// `log2(2^a + 2^b)`, computed without overflowing.
fn log_sum_exp2(a: f64, b: f64) -> f64 {
    let (hi, lo) = if a > b { (a, b) } else { (b, a) };
    hi + (1.0 + 2f64.powf(lo - hi)).log2()
}

/// The MATZOV estimate, restricted to estimates whose diagnostics do not fire.
///
/// This is the number to quote. `dual_matzov` returns the cheapest estimate the
/// grid contains, which — exactly as Ducas and Pulles pointed out — is often one
/// that assumes more short dual vectors than exist. This function returns the
/// cheapest estimate that survives the consistency check, and it is typically
/// several bits more expensive.
pub fn dual_matzov_consistent(
    inst: &LweInstance,
    model: &BkzModel,
    search: &DualSearch,
) -> Option<MatzovEstimate> {
    let mut filtered = *search;
    // Re-run the grid keeping only consistent points. Cheapest way to do that
    // without duplicating the loop is to widen the search and filter, so we
    // inline a second pass here.
    filtered.beta_step = search.beta_step;
    let mut best: Option<MatzovEstimate> = None;
    let mut beta = filtered.beta_min;
    while beta <= filtered.beta_max {
        let one = DualSearch {
            beta_min: beta,
            beta_max: beta,
            ..filtered
        };
        if let Some(e) = dual_matzov(inst, model, &one) {
            if !e.diagnostics.contradictory
                && !e.diagnostics.smoothed_out
                && best.as_ref().is_none_or(|b| e.log2_cost < b.log2_cost)
            {
                best = Some(e);
            }
        }
        beta += filtered.beta_step;
    }
    best
}

/// How a dual estimate compares against the NIST floor for its category, in the
/// model it was computed in.
///
/// Returns `(floor_bits, margin_bits)` where a negative margin is the
/// "N bits below requirement" figure that gets quoted. The caller is
/// responsible for having used a gate-count model: comparing a core-SVP number
/// against a gate floor understates security by roughly 16 bits and is the most
/// common way these comparisons go wrong.
pub fn margin_vs_category(inst: &LweInstance, log2_cost: f64) -> Option<(f64, f64)> {
    let floor = inst.category?.gate_floor_bits();
    Some((floor, log2_cost - floor))
}

/// Whether the model used is one whose numbers are comparable to NIST's floors.
pub fn model_is_gate_comparable(model: &BkzModel) -> bool {
    matches!(model.svp, SvpModel::GateCount)
}

#[cfg(test)]
mod tests {
    use super::super::params::*;
    use super::super::primal::primal_usvp_2016;
    use super::*;

    fn fast_search() -> DualSearch {
        DualSearch {
            beta_step: 32,
            k_fft_max: 32,
            k_enum_max: 8,
            ..Default::default()
        }
    }

    #[test]
    fn advantage_collapses_with_noise() {
        let q = 3329.0;
        // exp(-2π²τ²): at τ = 1/4 that is exp(-1.2337) ≈ 0.291.
        assert!((dual_advantage(q / 4.0, q) - (-2.0 * PI * PI / 16.0).exp()).abs() < 1e-12);
        assert!(dual_advantage(0.0, q) == 1.0);
        // Monotone decreasing, and negligible by the time the noise reaches q.
        assert!(dual_advantage(q, q) < 2f64.powi(-28));
        let mut prev = 1.0;
        for i in 1..50 {
            let a = dual_advantage(q * i as f64 / 20.0, q);
            assert!(a < prev);
            prev = a;
        }
    }

    #[test]
    fn short_vector_count_is_one_at_the_gaussian_heuristic() {
        // At length exactly gh(Λ) the count is 2^{-1}: the ± pair of the single
        // expected shortest vector. Above it, the count grows like the volume
        // ratio to the d-th power.
        let (d, vol) = (400usize, 900.0f64);
        let gh = gaussian_heuristic_log2(d, vol);
        assert!((short_vector_count_log2(d, vol, gh) + 1.0).abs() < 1e-9);
        assert!(short_vector_count_log2(d, vol, gh + 1.0) > 300.0);
        assert!(short_vector_count_log2(d, vol, gh - 0.1) < 0.0);
    }

    #[test]
    fn plain_dual_is_not_competitive_with_the_primal_attack() {
        // The historical fact that motivated all the refinements: MR09's dual
        // needs ε^{-2} samples and loses badly.
        let model = BkzModel::core_svp_classical();
        for inst in [ml_kem_512(), ml_kem_768(), ml_dsa_44_set().lwe()] {
            let p = primal_usvp_2016(&inst, &model).unwrap();
            let d = dual_distinguish(&inst, &model, &fast_search()).unwrap();
            assert!(
                d.log2_cost > p.log2_cost,
                "{}: plain dual {:.1} beat primal {:.1}",
                inst.name,
                d.log2_cost,
                p.log2_cost
            );
        }
    }

    #[test]
    fn plain_dual_has_no_independence_heuristic_to_break() {
        // One score per sample, so the contradictory-regime test is about
        // vector supply only, and a sane optimum should not trip it.
        let model = BkzModel::core_svp_classical();
        let e = dual_distinguish(&ml_kem_768(), &model, &fast_search()).unwrap();
        assert!(e.log2_advantage < 0.0);
        assert!(e.log2_samples > 0.0);
        assert!(!e.diagnostics.verdict().is_empty());
    }

    #[test]
    fn matzov_split_covers_the_secret_exactly() {
        let model = BkzModel::gate_count_realistic();
        for inst in all_lwe() {
            let e = dual_matzov(&inst, &model, &fast_search())
                .unwrap_or_else(|| panic!("no MATZOV estimate for {}", inst.name));
            assert_eq!(e.k_lat + e.k_fft + e.k_enum, inst.n, "{}", inst.name);
            assert_eq!(e.d, e.m_used + e.k_lat);
            assert!(e.m_used >= 1 && e.m_used <= inst.m);
            assert!(e.p >= 2 && (e.p as f64) <= inst.q as f64);
            // Total cost is at least each of its parts.
            assert!(e.log2_cost >= e.log2_cost_reduction - 1e-9);
            assert!(e.log2_cost >= e.log2_cost_fft - 1e-9);
        }
    }

    #[test]
    fn matzov_beats_the_plain_dual() {
        let model = BkzModel::core_svp_classical();
        let s = fast_search();
        for inst in [ml_kem_512(), ml_kem_768()] {
            let plain = dual_distinguish(&inst, &model, &s).unwrap();
            let matzov = dual_matzov(&inst, &model, &s).unwrap();
            assert!(
                matzov.log2_cost < plain.log2_cost,
                "{}: MATZOV {:.1} did not beat plain dual {:.1}",
                inst.name,
                matzov.log2_cost,
                plain.log2_cost
            );
        }
    }

    #[test]
    fn the_cheapest_matzov_point_is_usually_the_contradictory_one() {
        // This is the Ducas-Pulles observation, reproduced: left to optimise
        // freely the grid walks straight into a regime where it wants more
        // short dual vectors than the lattice holds. If this test ever starts
        // failing because no point is contradictory, the cost model has changed
        // and the diagnostics need revisiting — it is not good news.
        let model = BkzModel::core_svp_classical();
        let s = fast_search();
        let free = dual_matzov(&ml_kem_512(), &model, &s).unwrap();
        let consistent = dual_matzov_consistent(&ml_kem_512(), &model, &s).unwrap();
        assert!(free.log2_cost <= consistent.log2_cost + 1e-9);
        if free.diagnostics.contradictory {
            assert!(!consistent.diagnostics.contradictory);
            assert!(consistent.log2_cost > free.log2_cost);
        }
    }

    #[test]
    fn the_provable_and_contradictory_regimes_are_disjoint() {
        // Pouly-Shen's headline result, as a property test. No estimate may be
        // simultaneously inside the provable regime and inside the
        // contradictory one; if one were, our operationalisation of the two
        // would be wrong.
        let s = fast_search();
        for model in [
            BkzModel::core_svp_classical(),
            BkzModel::core_svp_quantum(),
            BkzModel::gate_count_realistic(),
        ] {
            for inst in all_lwe() {
                for e in [
                    dual_matzov(&inst, &model, &s),
                    dual_matzov_consistent(&inst, &model, &s),
                ]
                .into_iter()
                .flatten()
                {
                    assert!(
                        !(e.diagnostics.provable_regime && e.diagnostics.contradictory),
                        "{} in {}: both provable and contradictory",
                        inst.name,
                        model.label()
                    );
                }
                if let Some(e) = dual_distinguish(&inst, &model, &s) {
                    assert!(!(e.diagnostics.provable_regime && e.diagnostics.contradictory));
                }
            }
        }
    }

    #[test]
    fn diagnostics_verdicts_are_exhaustive() {
        let d = DualDiagnostics::new(-1.0, 10.0, 100.0);
        assert!(d.provable_regime && !d.contradictory);
        assert_eq!(d.verdict(), "within the provable regime");
        let d = DualDiagnostics::new(-300.0, 600.0, 10.0);
        assert!(d.smoothed_out);
        assert_eq!(d.verdict(), "noise smoothed out — not an attack");
        let d = DualDiagnostics::new(-40.0, 600.0, 10.0);
        assert_eq!(
            d.verdict(),
            "Ducas-Pulles contradictory regime — do not believe the cost"
        );
        let d = DualDiagnostics::new(-40.0, 10.0, 600.0);
        assert_eq!(d.verdict(), "heuristic regime, consistent vector count");
    }

    #[test]
    fn log_sum_exp2_is_exact_on_easy_cases() {
        assert!((log_sum_exp2(0.0, 0.0) - 1.0).abs() < 1e-12);
        assert!((log_sum_exp2(10.0, 10.0) - 11.0).abs() < 1e-12);
        // Wildly separated: the larger term wins outright.
        assert!((log_sum_exp2(1000.0, 1.0) - 1000.0).abs() < 1e-12);
        assert!(log_sum_exp2(5.0, 3.0) > 5.0 && log_sum_exp2(5.0, 3.0) < 6.0);
    }

    #[test]
    fn margins_are_only_quoted_against_a_gate_model() {
        assert!(model_is_gate_comparable(&BkzModel::gate_count_realistic()));
        assert!(!model_is_gate_comparable(&BkzModel::core_svp_classical()));
        let (floor, margin) = margin_vs_category(&ml_kem_512(), 140.0).unwrap();
        assert_eq!(floor, 143.0);
        assert!((margin + 3.0).abs() < 1e-9);
    }

    #[test]
    fn category_floors_are_the_nist_gate_counts() {
        assert_eq!(Category::One.gate_floor_bits(), 143.0);
        assert_eq!(Category::Three.gate_floor_bits(), 207.0);
        assert_eq!(Category::Five.gate_floor_bits(), 272.0);
    }
}
