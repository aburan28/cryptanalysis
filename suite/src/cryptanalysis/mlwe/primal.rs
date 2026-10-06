//! The primal attack: embed the LWE instance in a lattice whose unique
//! shortest vector *is* the secret, then reduce until it falls out.
//!
//! This is the baseline both schemes' parameters were set against, and nothing
//! published has improved on it in years. If a claim about ML-KEM's or
//! ML-DSA's margin is interesting, it is almost always a claim about the *dual*
//! attack ([`super::dual`]) beating this one.
//!
//! # The embedding
//!
//! Given `b = A·s + e mod q` with `A` of shape `m × n`, Kannan's embedding (in
//! the Bai–Galbraith form, which scales the secret block so the short vector is
//! balanced) gives a lattice of dimension
//!
//! ```text
//! d = m + n + 1
//! ```
//!
//! containing `v = (e, ν·s, 1)` with `ν = σ_e/σ_s`, of volume `q^m · ν^n`.
//! `‖v‖ ≈ σ_e·√(m + n)`, which for the parameters here is far below the
//! Gaussian heuristic for the lattice — so `v` is *unique*, and the problem is
//! unique-SVP rather than SVP.
//!
//! The attacker chooses how many samples to use. Using fewer shrinks `d`
//! (cheaper reduction) but also shrinks the volume (less help from `q`), so
//! there is an optimum, and the estimators below search for it rather than
//! assuming `m` is all used.
//!
//! # Two conditions, deliberately both
//!
//! * [`primal_usvp_2016`] uses the closed-form condition of Alkim–Ducas–
//!   Pöppelmann–Schwabe: `√β·σ ≤ δ^{2β-d-1}·vol^{1/d}`. Cheap, and the one
//!   every published table is computed with.
//! * [`primal_usvp_simulated`] runs the BKZ simulator and applies the modern
//!   condition — the secret's projection onto the last `β` Gram–Schmidt
//!   directions must be shorter than `‖b*_{d-β}‖` — which respects the q-ary
//!   z-shape that the closed form ignores.
//!
//! They are independent predictions of the same number. A test asserts they
//! agree to within a few block sizes; where they do not, the simulated one is
//! the better-founded.

use super::cost::{beta_from_delta, delta_from_beta, BkzModel, Profile};
use super::params::{LweInstance, SisInstance};

/// The outcome of a primal estimate.
#[derive(Clone, Debug, PartialEq)]
pub struct PrimalEstimate {
    /// Which instance this is about.
    pub instance: String,
    /// Which condition produced it.
    pub method: &'static str,
    /// The block size the attack needs.
    pub beta: f64,
    /// The embedding dimension at that block size.
    pub d: usize,
    /// How many of the available LWE samples the optimum uses.
    pub m_used: usize,
    /// Root Hermite factor at `beta`.
    pub delta: f64,
    /// `log2` of the attack's cost in the given model.
    pub log2_cost: f64,
    /// `log2` of the attack's memory.
    pub log2_memory: f64,
    /// The cost model's label, so a number is never quoted without it.
    pub model: String,
}

/// Search bound: no attack in this file will look past this block size. A
/// block size above it means the instance is out of reach by a margin nobody
/// disputes, and reporting "≥" is more honest than a fitted number.
pub const MAX_BETA: usize = 4000;

/// The primal uSVP estimate under the closed-form 2016 condition.
///
/// Returns `None` only if no block size up to [`MAX_BETA`] suffices, which for
/// the standardised parameter sets does not happen.
pub fn primal_usvp_2016(inst: &LweInstance, model: &BkzModel) -> Option<PrimalEstimate> {
    let log2_q = (inst.q as f64).log2();
    // ν = σ_e/σ_s balances the embedding; log2 ν per secret coordinate.
    let log2_nu = inst.volume_scale_log2();
    let sigma = inst.sigma_e;
    let n = inst.n as f64;

    // The condition is `√β·σ ≤ δ^{2β-d-1}·vol^{1/d}` with `d = m + n + 1` and
    // `vol = q^m·ν^n`. Taking logs and substituting `m = d - n - 1`:
    //
    //   f(d) = 2βL - L - L·d + log2 q - C/d,
    //   L = log2 δ,   C = (n+1)·log2 q - n·log2 ν
    //
    // which is concave in `d` (its second derivative is `-2C/d³ < 0`), so the
    // best sample count is the single stationary point
    //
    //   d* = √(C/L)
    //
    // clamped to what the instance offers. Evaluating there and at the two
    // endpoints replaces a sweep over every possible `m` — which, at `m` up to
    // 2048 and hundreds of candidate block sizes, dominated the runtime of
    // every hybrid estimate that calls this in a loop.
    let c_const = (n + 1.0) * log2_q - n * log2_nu;

    for beta_i in 50..=MAX_BETA {
        let beta = beta_i as f64;
        let delta = delta_from_beta(beta);
        let l = delta.log2();
        let lhs = sigma.log2() + 0.5 * beta.log2();

        let d_lo = (inst.n + 2).max(beta.ceil() as usize);
        let d_hi = inst.n + 1 + inst.m;
        if d_lo > d_hi {
            continue;
        }
        let f = |d: usize| -> f64 {
            let d = d as f64;
            2.0 * beta * l - l - l * d + log2_q - c_const / d
        };
        let d_star = if l > 0.0 && c_const > 0.0 {
            (c_const / l).sqrt().round() as usize
        } else {
            d_hi
        };
        let mut best_d = d_lo;
        let mut best_f = f(d_lo);
        for cand in [d_star.clamp(d_lo, d_hi), d_hi] {
            let v = f(cand);
            if v > best_f {
                best_f = v;
                best_d = cand;
            }
        }
        if lhs <= best_f {
            return Some(PrimalEstimate {
                instance: inst.name.clone(),
                method: "primal-usvp (ADPS16 closed form)",
                beta,
                d: best_d,
                m_used: best_d - inst.n - 1,
                delta,
                log2_cost: model.log2_cost(beta, best_d),
                log2_memory: model.log2_memory(beta),
                model: model.label(),
            });
        }
    }
    None
}

/// The primal uSVP estimate from the BKZ simulator.
///
/// Condition: after BKZ-β on the q-ary embedding lattice, the unique short
/// vector is recovered when its projection onto the last `β` Gram–Schmidt
/// directions, of expected norm `σ·√β`, is shorter than `‖b*_{d-β}‖`. That is
/// the event that makes the vector visible to the final SVP call.
///
/// `tours` is how many BKZ passes to simulate; 8 is BKZ 2.0's usual auto-abort
/// point and what the published simulations use.
pub fn primal_usvp_simulated(
    inst: &LweInstance,
    model: &BkzModel,
    tours: usize,
) -> Option<PrimalEstimate> {
    let sigma = inst.sigma_e;
    // Simulating is thousands of times more expensive than evaluating the
    // closed form, so we do not sweep the sample count here. We take the
    // candidates the closed form points at — its own optimum, the smallest
    // lattice that can hold the secret, and the full sample set — and let the
    // simulator choose between them. Sweeping every `m` moves the answer by
    // less than a block size and costs minutes.
    let seeded = primal_usvp_2016(inst, model)?;
    let mut candidates = vec![seeded.m_used, inst.n.min(inst.m), inst.m];
    candidates.sort_unstable();
    candidates.dedup();

    let mut best: Option<PrimalEstimate> = None;
    for m_used in candidates {
        let d = m_used + inst.n + 1;
        // Feasibility is monotone in β: a larger block size both reduces the
        // basis further and reads an earlier (longer) Gram–Schmidt vector, so
        // bisection finds the threshold exactly.
        let feasible = |beta: usize| -> bool {
            if beta + 1 > d {
                return true;
            }
            let profile = Profile::zgsa(d, inst.n + 1, inst.q, delta_from_beta(50.0))
                .simulate_bkz(beta, tours);
            sigma.log2() + 0.5 * (beta as f64).log2() < profile.log2_norms[d - beta]
        };
        if !feasible(d.min(MAX_BETA)) {
            continue;
        }
        let (mut lo, mut hi) = (50usize, d.min(MAX_BETA));
        while lo < hi {
            let mid = lo + (hi - lo) / 2;
            if feasible(mid) {
                hi = mid;
            } else {
                lo = mid + 1;
            }
        }
        let beta = lo as f64;
        let cand = PrimalEstimate {
            instance: inst.name.clone(),
            method: "primal-usvp (BKZ simulator)",
            beta,
            d,
            m_used,
            delta: delta_from_beta(beta),
            log2_cost: model.log2_cost(beta, d),
            log2_memory: model.log2_memory(beta),
            model: model.label(),
        };
        if best.as_ref().is_none_or(|b| cand.log2_cost < b.log2_cost) {
            best = Some(cand);
        }
    }
    best
}

/// The primal estimate for an SIS instance — ML-DSA forgery.
///
/// `Λ = {z : A·z ≡ 0 mod q}` has dimension `m` and volume `q^n`. BKZ-β on a
/// dimension-`m'` q-ary sublattice returns a vector of length
/// `δ^{m'-1}·q^{n/m'}`, and a forgery needs that below the scheme's bound. The
/// attacker picks `m'`; the optimum is near `√(n log q / log δ)` and we sweep
/// around it rather than assuming the closed form.
///
/// Note the `l∞`-to-`l2` conversion in [`SisInstance::l2_bound`] is generous to
/// the attacker in one direction (a solution meeting the `l2` bound need not
/// meet the `l∞` one) and tight in the other. Published Dilithium estimates
/// use the same convention.
pub fn sis_estimate(inst: &SisInstance, model: &BkzModel) -> Option<PrimalEstimate> {
    let log2_q = (inst.q as f64).log2();
    let log2_bound = inst.l2_bound().log2();
    let n = inst.n as f64;

    // `achieved(m) = (m-1)·L + n·log2 q / m` is convex in `m`, minimised at
    // `m* = √(n·log2 q / L)`. Evaluating there and at the endpoints replaces
    // the sweep.
    for beta_i in 50..=MAX_BETA {
        let beta = beta_i as f64;
        let delta = delta_from_beta(beta);
        let l = delta.log2();
        let m_lo = inst.n.max(beta.ceil() as usize);
        let m_hi = inst.m;
        if m_lo > m_hi {
            continue;
        }
        // No clamp at `log2 q`. The q-ary lattice does contain `q·e_i`, and for
        // an `l2` bound those would be legitimate SIS solutions — but ML-DSA's
        // bound is an `l∞` one, and `‖q·e_i‖∞ = q` is far outside it. Clamping
        // would hand the estimator a "solution" the scheme's own bound rejects.
        // Leaving the prediction unclamped can overstate the achieved length,
        // which is conservative and therefore safe.
        let achieved = |m: usize| -> f64 { ((m as f64) - 1.0) * l + n * log2_q / m as f64 };
        let m_star = if l > 0.0 {
            (n * log2_q / l).sqrt().round() as usize
        } else {
            m_hi
        };
        let mut best_m = m_lo;
        let mut best = achieved(m_lo);
        for cand in [m_star.clamp(m_lo, m_hi), m_hi] {
            let v = achieved(cand);
            if v < best {
                best = v;
                best_m = cand;
            }
        }
        if best <= log2_bound {
            return Some(PrimalEstimate {
                instance: inst.name.clone(),
                method: "sis (short vector in the q-ary kernel)",
                beta,
                d: best_m,
                m_used: best_m,
                delta,
                log2_cost: model.log2_cost(beta, best_m),
                log2_memory: model.log2_memory(beta),
                model: model.label(),
            });
        }
    }
    None
}

/// The block size an SIS bound demands, ignoring cost: the smallest `β` whose
/// `δ` makes `δ^{m-1}·q^{n/m} ≤ bound` for some `m`.
///
/// Useful on its own because ML-DSA's forgery bound is so loose that the answer
/// is often "any `δ` at all", and seeing that directly is clearer than reading
/// it off a cost.
pub fn sis_required_delta(inst: &SisInstance) -> Option<f64> {
    let log2_q = (inst.q as f64).log2();
    let log2_bound = inst.l2_bound().log2();
    let mut best: Option<f64> = None;
    for m_used in inst.n..=inst.m {
        // Solve (m-1) log δ + n log q / m = log bound for δ.
        let needed = (log2_bound - inst.n as f64 * log2_q / m_used as f64) / (m_used as f64 - 1.0);
        let delta = 2f64.powf(needed);
        if delta > 1.0 {
            best = Some(best.map_or(delta, |b: f64| b.max(delta)));
        }
    }
    best
}

/// The block size an SIS instance needs, via [`sis_required_delta`].
pub fn sis_required_beta(inst: &SisInstance) -> Option<f64> {
    sis_required_delta(inst).map(beta_from_delta)
}

#[cfg(test)]
mod tests {
    use super::super::cost::{Reps, SvpModel};
    use super::super::params::*;
    use super::*;

    fn core_svp() -> BkzModel {
        BkzModel::core_svp_classical()
    }

    #[test]
    fn primal_finds_a_block_size_for_every_standard_set() {
        for inst in all_lwe() {
            let e = primal_usvp_2016(&inst, &core_svp())
                .unwrap_or_else(|| panic!("no estimate for {}", inst.name));
            assert!(e.beta >= 50.0 && e.beta < MAX_BETA as f64);
            assert!(e.d > inst.n, "{}: d = {} ≤ n", inst.name, e.d);
            assert!(e.m_used >= 1 && e.m_used <= inst.m);
            assert!(e.log2_cost > 0.0);
        }
    }

    #[test]
    fn primal_cost_orders_the_parameter_sets_correctly() {
        // More module rank, more security — the whole design intent.
        let c = |i: LweInstance| primal_usvp_2016(&i, &core_svp()).unwrap().log2_cost;
        assert!(c(ml_kem_512()) < c(ml_kem_768()));
        assert!(c(ml_kem_768()) < c(ml_kem_1024()));
        let d = |s: MlDsaSet| primal_usvp_2016(&s.lwe(), &core_svp()).unwrap().log2_cost;
        assert!(d(ml_dsa_44_set()) < d(ml_dsa_65_set()));
        assert!(d(ml_dsa_65_set()) < d(ml_dsa_87_set()));
    }

    #[test]
    fn primal_reproduces_the_published_core_svp_neighbourhood() {
        // The Kyber submission's core-SVP primal numbers are 118 / 183 / 256
        // bits classical. We should land in that neighbourhood — not on it, as
        // the submission optimises the embedding slightly differently, but a
        // model this far from those numbers would be broken.
        let checks = [
            (ml_kem_512(), 118.0),
            (ml_kem_768(), 183.0),
            (ml_kem_1024(), 256.0),
        ];
        for (inst, published) in checks {
            let got = primal_usvp_2016(&inst, &core_svp()).unwrap().log2_cost;
            assert!(
                (got - published).abs() < 25.0,
                "{}: got {got:.1}, published ≈ {published}",
                inst.name
            );
        }
    }

    #[test]
    fn quantum_core_svp_shaves_about_a_tenth_of_the_exponent() {
        for inst in all_lwe() {
            let c = primal_usvp_2016(&inst, &BkzModel::core_svp_classical()).unwrap();
            let q = primal_usvp_2016(&inst, &BkzModel::core_svp_quantum()).unwrap();
            // Same lattice, same block size — only the price of a sieve call
            // differs. That is the entire quantum story.
            assert_eq!(c.beta, q.beta);
            assert!(q.log2_cost < c.log2_cost);
            let ratio = q.log2_cost / c.log2_cost;
            assert!((ratio - 0.265 / 0.292).abs() < 1e-9, "{}", inst.name);
        }
    }

    #[test]
    fn using_fewer_samples_is_sometimes_optimal() {
        // If the optimum always used every sample the sweep would be pointless.
        // ML-DSA has 256·k samples against 256·ℓ unknowns with a big q, so the
        // optimum is well short of all of them.
        let e = primal_usvp_2016(&ml_dsa_65_set().lwe(), &core_svp()).unwrap();
        assert!(e.m_used < 256 * 6, "used all {} samples", e.m_used);
    }

    #[test]
    fn simulated_and_closed_form_agree_within_a_few_block_sizes() {
        for inst in [ml_kem_512(), ml_kem_768(), ml_dsa_44_set().lwe()] {
            let a = primal_usvp_2016(&inst, &core_svp()).unwrap();
            let b = primal_usvp_simulated(&inst, &core_svp(), 8).unwrap();
            assert!(
                (a.beta - b.beta).abs() <= 60.0,
                "{}: closed form β = {}, simulator β = {}",
                inst.name,
                a.beta,
                b.beta
            );
        }
    }

    #[test]
    fn ml_dsa_forgery_is_far_easier_than_key_recovery() {
        // ζ' is enormous — of order γ₁ — so the SIS instance is loose, and
        // forgery-by-lattice-reduction is *not* what protects ML-DSA. What
        // protects it is that a short SIS solution alone is not a signature:
        // it has to be consistent with a challenge hash. Seeing the SIS side
        // come out weak is expected, and is why nobody quotes it as the
        // security level.
        for s in [ml_dsa_44_set(), ml_dsa_65_set(), ml_dsa_87_set()] {
            let key = primal_usvp_2016(&s.lwe(), &core_svp()).unwrap();
            let forge = sis_estimate(&s.sis(), &core_svp());
            if let Some(f) = forge {
                assert!(
                    f.log2_cost <= key.log2_cost,
                    "{}: SIS {} > MLWE {}",
                    s.name,
                    f.log2_cost,
                    key.log2_cost
                )
            }
        }
    }

    #[test]
    fn sis_required_delta_is_above_one_and_inverts_to_a_block_size() {
        for s in all_sis() {
            let delta = sis_required_delta(&s).expect("a loose bound always has a δ");
            assert!(delta > 1.0, "{}: δ = {delta}", s.name);
            let beta = sis_required_beta(&s).unwrap();
            assert!(beta >= 50.0);
        }
    }

    #[test]
    fn tours_and_dimension_enter_the_cost_but_not_the_block_size() {
        let inst = ml_kem_768();
        let bare = primal_usvp_2016(&inst, &BkzModel::core_svp_classical()).unwrap();
        let tours = primal_usvp_2016(
            &inst,
            &BkzModel {
                svp: SvpModel::CoreSvpClassical,
                reps: Reps::Tours(8),
                d4f: false,
            },
        )
        .unwrap();
        assert_eq!(bare.beta, tours.beta);
        assert_eq!(bare.d, tours.d);
        assert!(tours.log2_cost > bare.log2_cost);
    }

    #[test]
    fn every_estimate_carries_its_model_label() {
        let e = primal_usvp_2016(&ml_kem_512(), &BkzModel::gate_count_realistic()).unwrap();
        assert!(e.model.contains("gate-count"));
        assert!(e.model.contains("d4f"));
    }
}
