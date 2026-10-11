//! Hybrid attacks: trade lattice dimension against guessing.
//!
//! Both schemes' secrets are *small* — ML-KEM's coordinates come from `CBD(η)`
//! on `[-η, η]`, ML-DSA's from the uniform distribution on the same range — so a
//! secret coordinate carries between 1.5 and 3.2 bits rather than the `log2 q`
//! (11.7 or 23) bits an unstructured one would. Guessing a coordinate is
//! therefore cheap, and every coordinate guessed shrinks the lattice.
//!
//! # What this module concludes, up front
//!
//! **Hybrid primal attacks do not beat the plain primal attack at these
//! parameter sets.** Every estimator here returns `g = 0`, or something more
//! expensive. That is a result, not a bug, and it took getting the accounting
//! right to see it:
//!
//! * Under the **uSVP** success condition ([`hybrid_guess_values`],
//!   [`hybrid_guess_zeros`], [`hybrid_meet_in_the_middle`]) the reduction is
//!   paid once *per guess*, so the exponents add. A coordinate costs `H` bits
//!   and buys about `0.29` bits of block size. `H` is never below 1.4. So the
//!   optimum is to guess nothing.
//! * Under the **Babai decoding** condition ([`hybrid_primal_bdd`]) the
//!   reduction is paid once in total, which is the amortisation the hybrid
//!   attack exists for — but the condition is far stronger (*every*
//!   Gram–Schmidt norm must exceed `2σ`, not just the first), so the block size
//!   it demands more than eats the saving.
//!
//! The published 2–15 bit improvements over the round-3 estimates are on the
//! **dual** side, not here: they come from the enumeration block of the
//! MATZOV-style attack, where the short dual vectors are reused across guesses
//! for free. [`hybrid_dual`] reports that, and it is the line to look at.
//!
//! # The mistake this module is arranged to avoid
//!
//! Pairing one attack's cost model with another's success condition. Charging
//! `2^{gH} + T_primal(n-g)` — reduce once — while requiring only the uSVP
//! condition produces an apparent 30–55 bit hybrid win on ML-KEM, which is not
//! real. Wunderer's *Revisiting the hybrid attack* is an entire paper about
//! versions of this error. Each estimator below names the condition it uses.
//!
//! # References
//!
//! * Howgrave-Graham, *A hybrid lattice-reduction and meet-in-the-middle attack
//!   against NTRU*, CRYPTO 2007.
//! * Wunderer, *Revisiting the hybrid attack*, 2016.
//! * Albrecht, Curtis, Deo, Davidson, Player, Postlethwaite, Virdia, Wunderer,
//!   *Estimate all the {LWE, NTRU} schemes!*, SCN 2018.

use super::cost::{delta_from_beta, BkzModel};
use super::dual::{dual_matzov, dual_matzov_consistent, DualSearch};
use super::params::LweInstance;
use super::primal::{primal_usvp_2016, MAX_BETA};

/// The outcome of a hybrid estimate.
#[derive(Clone, Debug, PartialEq)]
pub struct HybridEstimate {
    pub instance: String,
    pub method: &'static str,
    /// How many secret coordinates are guessed rather than reduced.
    pub guessed: usize,
    /// `log2` of the guessing work (including any repetition factor).
    pub log2_guess_cost: f64,
    /// `log2` of the lattice work on the shrunken instance.
    pub log2_lattice_cost: f64,
    /// Total, `log2`.
    pub log2_cost: f64,
    pub log2_memory: f64,
    /// Block size the shrunken instance needs.
    pub beta: f64,
    pub model: String,
}

/// The probability that one coordinate of `CBD(η)` is zero: `C(2η, η)/4^η`.
pub fn cbd_zero_probability(eta: usize) -> f64 {
    let two_eta = 2 * eta;
    let mut c: f64 = 1.0;
    for i in 0..eta {
        c = c * (two_eta - i) as f64 / (i as f64 + 1.0);
    }
    c / 4f64.powi(eta as i32)
}

/// The probability that one coordinate is zero, inferred from the instance.
///
/// For a uniform secret on `[-η, η]` this is `1/(2η+1)`; for `CBD(η)` it is
/// [`cbd_zero_probability`]. We tell them apart by comparing the recorded
/// entropy against the uniform entropy: `CBD` is strictly below it.
fn zero_probability(inst: &LweInstance) -> Option<f64> {
    let support = inst.secret_support?;
    let eta = inst.secret_bound? as usize;
    let uniform_h = (support as f64).log2();
    if (inst.secret_entropy_bits - uniform_h).abs() < 1e-9 {
        Some(1.0 / support as f64)
    } else {
        Some(cbd_zero_probability(eta))
    }
}

/// Drop `g` coordinates from the secret: the same instance with `n - g`
/// unknowns and the same sample count.
fn shrink(inst: &LweInstance, g: usize) -> LweInstance {
    let mut out = inst.clone();
    out.n = inst.n.saturating_sub(g);
    out.name = format!("{} [{} guessed]", inst.name, g);
    out
}

/// Hybrid primal with outright value guessing, under the uSVP condition.
///
/// Sweep `g`, guess those coordinates at `H` bits each, and solve the remaining
/// `n - g` by the primal uSVP attack.
///
/// # Why the costs multiply
///
/// Each guess yields a *different* uSVP instance — the same lattice, but a
/// different embedded target — and solving uSVP means running the reduction
/// through to its final SVP call. So the reduction is paid once per guess and
/// the total is `2^{gH} · T_primal(n-g)`, an addition of exponents.
///
/// It is tempting to charge `2^{gH} + T_primal(n-g)` instead, on the grounds
/// that the lattice depends only on `A` and can be reduced once. That is the
/// right accounting for a *different* attack — reduce once, then decode each
/// guess by nearest-plane — and it is what [`hybrid_primal_bdd`] implements.
/// But that attack succeeds under the Babai decoding condition, not the uSVP
/// condition, and pairing one attack's cost with the other's success condition
/// is how a hybrid estimate ends up claiming tens of bits it has not earned.
/// Ask which condition a cost belongs to before believing it; Wunderer's
/// *Revisiting the hybrid attack* is an entire paper about this mistake.
///
/// With exponents added, guessing never pays at these parameter sets: a
/// coordinate costs `H ≈ 1.5–3.2` bits and buys about `0.29` bits of block
/// size. The sweep therefore returns `g = 0`, and that is the correct answer
/// for this attack, not a failure of the sweep.
pub fn hybrid_guess_values(
    inst: &LweInstance,
    model: &BkzModel,
    max_guess: usize,
) -> Option<HybridEstimate> {
    sweep_usvp(
        inst,
        model,
        max_guess,
        "hybrid-primal (guess values, uSVP)",
        inst.secret_entropy_bits,
    )
}

/// Hybrid primal, guessing that `g` coordinates are zero.
///
/// Cheaper per coordinate than guessing a value whenever the distribution is
/// concentrated at zero, which `CBD(η)` is: `-log2 P(0)` is 1.42 bits for
/// `CBD(2)` against 2.03 bits of entropy. The `1/P(0)^g` factor is a repetition
/// count rather than a search space, but it multiplies the lattice work either
/// way, so the accounting is the same as [`hybrid_guess_values`].
pub fn hybrid_guess_zeros(
    inst: &LweInstance,
    model: &BkzModel,
    max_guess: usize,
) -> Option<HybridEstimate> {
    let p0 = zero_probability(inst)?;
    if p0 <= 0.0 {
        return None;
    }
    sweep_usvp(
        inst,
        model,
        max_guess,
        "hybrid-primal (guess zeros, uSVP)",
        -p0.log2(),
    )
}

/// Hybrid primal with a meet-in-the-middle on the guessed block.
///
/// Halves the guessing exponent to `gH/2` and charges the same in memory.
///
/// **Caveat, stated because the number is otherwise misleading.** The MitM step
/// needs the two halves' contributions to collide *exactly* in some hash of the
/// residual vector, and LWE noise blurs that hash. Howgrave-Graham's original
/// attack handles the blur with a near-collision search whose cost is not
/// captured by halving the exponent. So this is an *optimistic bound* on what
/// meet-in-the-middle can buy, not a costing of a concrete algorithm. Read it
/// as "guessing cannot help more than this".
pub fn hybrid_meet_in_the_middle(
    inst: &LweInstance,
    model: &BkzModel,
    max_guess: usize,
) -> Option<HybridEstimate> {
    let mut e = sweep_usvp(
        inst,
        model,
        max_guess,
        "hybrid-primal (MitM bound, uSVP)",
        inst.secret_entropy_bits / 2.0,
    )?;
    e.log2_memory = e.log2_memory.max(e.log2_guess_cost);
    Some(e)
}

/// The shared sweep for the uSVP-condition hybrids: `bits_per` bits of guessing
/// per coordinate, multiplied into the lattice cost.
fn sweep_usvp(
    inst: &LweInstance,
    model: &BkzModel,
    max_guess: usize,
    method: &'static str,
    bits_per: f64,
) -> Option<HybridEstimate> {
    let mut best: Option<HybridEstimate> = None;
    let step = (max_guess / 64).max(1);
    for g in (0..=max_guess.min(inst.n.saturating_sub(1))).step_by(step) {
        let sub = shrink(inst, g);
        let Some(p) = primal_usvp_2016(&sub, model) else {
            continue;
        };
        let guess = g as f64 * bits_per;
        let cand = HybridEstimate {
            instance: inst.name.clone(),
            method,
            guessed: g,
            log2_guess_cost: guess,
            log2_lattice_cost: p.log2_cost,
            log2_cost: guess + p.log2_cost,
            log2_memory: p.log2_memory,
            beta: p.beta,
            model: model.label(),
        };
        if best.as_ref().is_none_or(|b| cand.log2_cost < b.log2_cost) {
            best = Some(cand);
        }
    }
    best
}

/// The hybrid attack that actually pays: reduce once, decode every guess.
///
/// This is Howgrave-Graham's attack, and its success condition is *not* uSVP.
///
/// # The condition
///
/// Take `m` samples and work in the q-ary lattice
/// `Λ = {A·s mod q} + q·Z^m`, of dimension `m` and volume `q^{m-n'}` where
/// `n' = n - g` is what is left after guessing. The target `b = A·s + e` sits at
/// distance `‖e‖ ≈ σ√m` from it. Once the basis is BKZ-β-reduced, Babai's
/// nearest-plane algorithm recovers the lattice point when the error is inside
/// the fundamental parallelepiped, i.e. when
///
/// ```text
/// σ ≤ ‖b*_i‖ / 2   for every i,
/// ```
///
/// which the *last* Gram–Schmidt vector decides. Under the GSA that is
///
/// ```text
/// (1-m)·log2 δ + (m - n')·log2 q / m  ≥  log2 2σ,
/// ```
///
/// and the attacker picks `m` to maximise the left-hand side — a concave
/// function with its optimum at `m* = √(n'·log2 q / log2 δ)`.
///
/// # Why this one wins
///
/// The reduction is paid **once**, because the lattice depends only on `A` and
/// not on the guess. Each guess then costs a nearest-plane pass, `O(m²)`
/// operations. So the costs *add* rather than multiply:
///
/// ```text
/// T = T_bkz(β, m) + 2^{gH}·m²
/// ```
///
/// and the optimum sits where the two terms are comparable. That is where the
/// published 2–15 bit improvements over the round-3 estimates come from.
///
/// # What it costs in honesty
///
/// The Babai condition is far more demanding than uSVP's, so `β` here is larger
/// than [`hybrid_guess_values`] would need for the same `g`. The trade is a
/// harder lattice problem against a cheaper per-guess step, and whether it comes
/// out ahead is exactly what the sweep decides rather than assumes.
pub fn hybrid_primal_bdd(
    inst: &LweInstance,
    model: &BkzModel,
    max_guess: usize,
) -> Option<HybridEstimate> {
    let log2_q = (inst.q as f64).log2();
    let h = inst.secret_entropy_bits;
    let target = (2.0 * inst.sigma_e).log2();
    let mut best: Option<HybridEstimate> = None;
    let step = (max_guess / 64).max(1);

    for g in (0..=max_guess.min(inst.n.saturating_sub(1))).step_by(step) {
        let n_prime = (inst.n - g) as f64;
        for beta_i in (50..=MAX_BETA).step_by(2) {
            let beta = beta_i as f64;
            let l = delta_from_beta(beta).log2();
            let tail = |m: usize| -> f64 {
                let m = m as f64;
                (1.0 - m) * l + (m - n_prime) * log2_q / m
            };
            let m_star = if l > 0.0 {
                (n_prime * log2_q / l).sqrt().round() as usize
            } else {
                inst.m
            };
            let m_lo = ((inst.n - g) + 1).max(beta_i);
            if m_lo > inst.m {
                break;
            }
            let mut best_m = m_lo;
            let mut best_tail = tail(m_lo);
            for cand in [m_star.clamp(m_lo, inst.m), inst.m] {
                let v = tail(cand);
                if v > best_tail {
                    best_tail = v;
                    best_m = cand;
                }
            }
            if best_tail < target {
                continue;
            }
            // Reduce once, then one nearest-plane pass per guess.
            let reduce = model.log2_cost(beta, best_m);
            let decode = g as f64 * h + 2.0 * (best_m as f64).log2();
            let cand = HybridEstimate {
                instance: inst.name.clone(),
                method: "hybrid-primal-bdd (reduce once, decode per guess)",
                guessed: g,
                log2_guess_cost: decode,
                log2_lattice_cost: reduce,
                log2_cost: log_add2(reduce, decode),
                log2_memory: model.log2_memory(beta),
                beta,
                model: model.label(),
            };
            if best.as_ref().is_none_or(|b| cand.log2_cost < b.log2_cost) {
                best = Some(cand);
            }
            break;
        }
    }
    best
}

/// The hybrid *dual* attack: guessing composed with the MATZOV-style dual.
///
/// The MATZOV estimator already has an enumeration block (`k_enum`), so the
/// hybrid dual is that estimator with the guessing budget widened. This wrapper
/// exists to report it as its own line, and to do the comparison that matters:
/// the cheapest point the grid finds versus the cheapest point whose
/// diagnostics do not fire.
pub fn hybrid_dual(
    inst: &LweInstance,
    model: &BkzModel,
    search: &DualSearch,
) -> Option<(HybridEstimate, HybridEstimate)> {
    let wide = DualSearch {
        k_enum_max: search.k_enum_max.max(64),
        ..*search
    };
    let free = dual_matzov(inst, model, &wide)?;
    let consistent = dual_matzov_consistent(inst, model, &wide)?;
    let to_hybrid = |e: &super::dual::MatzovEstimate, method: &'static str| HybridEstimate {
        instance: inst.name.clone(),
        method,
        guessed: e.k_enum + e.k_fft,
        log2_guess_cost: e.log2_cost_fft,
        log2_lattice_cost: e.log2_cost_reduction,
        log2_cost: e.log2_cost,
        log2_memory: e.log2_memory,
        beta: e.beta,
        model: e.model.clone(),
    };
    Some((
        to_hybrid(&free, "hybrid-dual (cheapest grid point)"),
        to_hybrid(&consistent, "hybrid-dual (consistent only)"),
    ))
}

/// `log2(2^a + 2^b)`.
fn log_add2(a: f64, b: f64) -> f64 {
    let (hi, lo) = if a > b { (a, b) } else { (b, a) };
    hi + (1.0 + 2f64.powf(lo - hi)).log2()
}

/// The cheapest hybrid across all three guessing strategies.
pub fn best_hybrid(
    inst: &LweInstance,
    model: &BkzModel,
    max_guess: usize,
) -> Option<HybridEstimate> {
    [
        hybrid_guess_values(inst, model, max_guess),
        hybrid_guess_zeros(inst, model, max_guess),
        hybrid_meet_in_the_middle(inst, model, max_guess),
        hybrid_primal_bdd(inst, model, max_guess),
    ]
    .into_iter()
    .flatten()
    .min_by(|a, b| a.log2_cost.total_cmp(&b.log2_cost))
}

#[cfg(test)]
mod tests {
    use super::super::params::*;
    use super::*;

    #[test]
    fn cbd_zero_probability_matches_the_definition() {
        // CBD(1): (1/4, 1/2, 1/4) → P(0) = 1/2.
        assert!((cbd_zero_probability(1) - 0.5).abs() < 1e-12);
        // CBD(2): C(4,2)/16 = 6/16 = 0.375.
        assert!((cbd_zero_probability(2) - 0.375).abs() < 1e-12);
        // CBD(3): C(6,3)/64 = 20/64 = 0.3125.
        assert!((cbd_zero_probability(3) - 0.3125).abs() < 1e-12);
        // Always above the uniform 1/(2η+1), which is the whole point.
        for eta in 1..=6 {
            assert!(cbd_zero_probability(eta) > 1.0 / (2 * eta + 1) as f64);
        }
    }

    #[test]
    fn zero_probability_distinguishes_cbd_from_uniform() {
        // ML-KEM is CBD; ML-DSA is uniform.
        let kem = zero_probability(&ml_kem_768()).unwrap();
        assert!((kem - cbd_zero_probability(2)).abs() < 1e-12);
        let dsa = zero_probability(&ml_dsa_44_set().lwe()).unwrap();
        assert!((dsa - 1.0 / 5.0).abs() < 1e-12);
    }

    #[test]
    fn guessing_zeros_beats_guessing_values_for_cbd_secrets() {
        // -log2 P(0) < H for a concentrated distribution, so per coordinate the
        // zero guess is cheaper. Whether that wins overall depends on how much
        // the lattice shrinks, which is what the estimators decide.
        for eta in [2usize, 3] {
            let p0_bits = -cbd_zero_probability(eta).log2();
            let uniform_bits = ((2 * eta + 1) as f64).log2();
            assert!(p0_bits < uniform_bits, "η = {eta}");
        }
    }

    #[test]
    fn the_usvp_hybrids_reduce_to_the_plain_primal_attack() {
        // g = 0 is in every sweep, so the minimum is over a set containing the
        // plain attack — and with the exponents added rather than combined, the
        // plain attack *is* the minimum. Both halves matter: the estimate must
        // not come out worse (that would mean g = 0 was skipped) and must not
        // come out better (that would mean guessing was charged too little).
        let model = BkzModel::core_svp_classical();
        for inst in all_lwe() {
            let plain = super::super::primal::primal_usvp_2016(&inst, &model)
                .unwrap()
                .log2_cost;
            for f in [
                hybrid_guess_values as fn(&LweInstance, &BkzModel, usize) -> Option<HybridEstimate>,
                hybrid_guess_zeros,
                hybrid_meet_in_the_middle,
            ] {
                let h = f(&inst, &model, 512).unwrap();
                assert_eq!(
                    h.guessed, 0,
                    "{} {}: guessed {}",
                    inst.name, h.method, h.guessed
                );
                assert!(
                    (h.log2_cost - plain).abs() < 1e-9,
                    "{} {}: hybrid {:.2} vs plain {:.2}",
                    inst.name,
                    h.method,
                    h.log2_cost,
                    plain
                );
            }
        }
    }

    #[test]
    fn guessing_a_coordinate_costs_more_than_it_buys() {
        // The arithmetic behind the conclusion above, made explicit. Dropping
        // one secret coordinate lowers the required block size by about one,
        // worth 0.292 bits in the core-SVP model — against at least 1.4 bits to
        // guess it.
        let model = BkzModel::core_svp_classical();
        for inst in all_lwe() {
            let full = super::super::primal::primal_usvp_2016(&inst, &model).unwrap();
            let mut one_less = inst.clone();
            one_less.n -= 8;
            let less = super::super::primal::primal_usvp_2016(&one_less, &model).unwrap();
            let beta_saved_per_coordinate = (full.beta - less.beta) / 8.0;
            assert!(
                beta_saved_per_coordinate > 0.0 && beta_saved_per_coordinate < 2.0,
                "{}: {beta_saved_per_coordinate} block sizes per coordinate",
                inst.name
            );
            let bits_bought = 0.292 * beta_saved_per_coordinate;
            let bits_spent = zero_probability(&inst).map(|p| -p.log2()).unwrap();
            assert!(
                bits_spent > bits_bought,
                "{}: guessing a zero costs {bits_spent:.2} and buys {bits_bought:.2}",
                inst.name
            );
        }
    }

    #[test]
    fn the_bdd_hybrid_is_a_real_estimate_even_though_it_loses() {
        // It must produce a finite, self-consistent answer for every set. That
        // it comes out above the primal attack is the Babai condition's fault,
        // not the estimator's, and the module doc says so.
        let model = BkzModel::core_svp_classical();
        for inst in all_lwe() {
            let e = hybrid_primal_bdd(&inst, &model, 512)
                .unwrap_or_else(|| panic!("no BDD estimate for {}", inst.name));
            assert!(e.log2_cost.is_finite() && e.log2_cost > 0.0);
            assert!(e.beta >= 50.0);
            assert!(e.guessed > 0, "{}: BDD chose to guess nothing", inst.name);
            // Costs add here, so the total is between the larger part and
            // twice it.
            let larger = e.log2_guess_cost.max(e.log2_lattice_cost);
            assert!(e.log2_cost >= larger - 1e-9);
            assert!(e.log2_cost <= larger + 1.0 + 1e-9);
        }
    }

    #[test]
    fn mitm_is_at_most_as_expensive_as_value_guessing() {
        let model = BkzModel::core_svp_classical();
        for inst in [ml_kem_512(), ml_dsa_65_set().lwe()] {
            let v = hybrid_guess_values(&inst, &model, 512).unwrap();
            let m = hybrid_meet_in_the_middle(&inst, &model, 512).unwrap();
            assert!(m.log2_cost <= v.log2_cost + 1e-9);
            // …and it pays for it in memory.
            assert!(m.log2_memory >= m.log2_guess_cost - 1e-9);
        }
    }

    #[test]
    fn hybrid_dual_reports_both_the_free_and_the_consistent_point() {
        let model = BkzModel::gate_count_realistic();
        let s = DualSearch {
            beta_step: 64,
            k_fft_max: 16,
            k_enum_max: 8,
            ..Default::default()
        };
        let (free, consistent) = hybrid_dual(&ml_kem_512(), &model, &s).unwrap();
        assert!(free.log2_cost <= consistent.log2_cost + 1e-9);
        assert!(free.method.contains("cheapest"));
        assert!(consistent.method.contains("consistent"));
    }

    #[test]
    fn shrink_keeps_everything_but_the_dimension() {
        let a = ml_kem_768();
        let b = shrink(&a, 100);
        assert_eq!(b.n, a.n - 100);
        assert_eq!(b.m, a.m);
        assert_eq!(b.q, a.q);
        assert_eq!(b.sigma_s, a.sigma_s);
        assert!(b.name.contains("100 guessed"));
    }

    #[test]
    fn log_add2_behaves() {
        assert!((log_add2(0.0, 0.0) - 1.0).abs() < 1e-12);
        assert!((log_add2(100.0, 0.0) - 100.0).abs() < 1e-9);
    }
}
