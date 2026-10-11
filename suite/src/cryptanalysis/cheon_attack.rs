//! **Cheon's algorithm** for the discrete logarithm with auxiliary
//! inputs (Cheon, EUROCRYPT 2006; J. Cryptology 23, 2010), `p − 1` case.
//!
//! Threat model (DLPwAI).  The adversary observes `G`, `[α]G` and
//! `[α^d]G` for a *known* divisor `d` of `n − 1`, where `n = ord(G)` is
//! prime.  Such powers leak from every `q`-SDH-style assumption: Boneh–
//! Boyen signatures, broadcast encryption and traitor tracing publish
//! `[α^i]G` for `i ≤ q`, so any `d ≤ q` with `d | n − 1` is usable.
//!
//! Cheon shows that `α` is then recoverable in
//!
//! ```text
//!     O( √((n − 1)/d) + √d )   exponentiations
//! ```
//!
//! instead of the `Ω(√n)` group operations of a generic algorithm.  This
//! matches the generic-group lower bound `Ω(√(n/d))` for the DLPwAI, so
//! the algorithm is optimal for this problem; at `d ≈ √n` the cost is
//! `O(n^{1/4})` exponentiations.
//!
//! ## Why it works
//!
//! `F_n^*` is cyclic of order `n − 1`.  Let `ζ` generate it and let
//! `ζ̂ = ζ^d`, of order `N = (n − 1)/d`.  Write `α = ζ^k` with
//! `k = k₀ + k₁·N`, `0 ≤ k₀ < N`, `0 ≤ k₁ < d`.  Then
//!
//! * `α^d = ζ^{dk} = ζ̂^{k₀}` (the `k₁` part vanishes since `d·N = n−1`),
//!   so a baby-step/giant-step search of size `√N` on the pair
//!   `(G, [α^d]G)` finds `k₀`: baby steps `[ζ̂^i]G`, giant steps
//!   `[ζ̂^{−mj}]·[α^d]G`.
//! * `α·ζ^{−k₀} = ζ^{k₁N} = ζ̌^{k₁}` with `ζ̌ = ζ^N` of order `d`, so a
//!   second search of size `√d` on `(G, [ζ^{−k₀}]·[α]G)` finds `k₁`.
//!
//! Every step is a scalar multiplication of a *fixed* base by a scalar
//! known in `F_n`, which is why the unit is exponentiations; with
//! fixed-base tables (Kozaki–Kutsuma–Matsuo 2007) each costs a handful
//! of group additions.  This module uses plain scalar multiplication and
//! reports the exponentiation count, so the reader can convert.
//!
//! ## What the auxiliary input buys, and what it does not
//!
//! Without `[α^d]G` the algorithm cannot start: the first search needs
//! `α^d` embedded into the small subgroup `⟨ζ̂⟩`, and `[α^d]G` cannot be
//! computed from `G, [α]G` (that is the CDH problem).  Cheon's algorithm
//! is therefore a statement about protocols that leak powers of the
//! secret, not about the ECDLP itself.  See
//! `research/notes/ecdlp-general/RESEARCH_TORSION_AUXILIARY_INPUTS.md` for the measured accounting
//! against Pollard rho.
//!
//! ## History of this module
//!
//! An earlier version of this file performed a plain baby-step/giant-step
//! with `d` baby steps on `(G, [α]G)` and never used the auxiliary input;
//! its cost was `d + (n − 1)/d ≥ 2√n` group operations, i.e. *worse* than
//! rho, while its report quoted Cheon's formula.  The measurement in the
//! research note above (`plain_bsgs_as_in_rust` rows) records that.
//!
//! ## References
//!
//! - **J. H. Cheon**, *Security analysis of the strong Diffie-Hellman
//!   problem*, EUROCRYPT 2006.
//! - **J. H. Cheon**, *Discrete logarithm problems with auxiliary
//!   inputs*, J. Cryptology 23 (2010), 457–476.
//! - **D. R. L. Brown, R. P. Gallant**, *The static Diffie–Hellman
//!   problem*, ePrint 2004/306 (independent discovery of the `p − 1` case).
//! - **S. Kozaki, T. Kutsuma, K. Matsuo**, *Remarks on Cheon's algorithms
//!   for pairing-related problems*, Pairing 2007.

use crate::cryptanalysis::j0_twists::factorise_small;
use crate::ecc::curve::CurveParams;
use crate::ecc::point::Point;
use num_bigint::BigUint;
use num_traits::{One, Zero};
use std::collections::HashMap;

/// Outcome of one Cheon attack run.
#[derive(Clone, Debug)]
pub struct CheonAttackReport {
    /// Subgroup order `n`.
    pub n: BigUint,
    /// Divisor `d` of `n − 1` we exploited (the auxiliary input is `[α^d]G`).
    pub d: BigUint,
    /// Recovered `α` (if found).
    pub recovered_alpha: Option<BigUint>,
    /// Exponentiations spent in the first search (size `√((n−1)/d)`).
    pub step1_exps: u64,
    /// Exponentiations spent in the second search (size `√d`).
    pub step2_exps: u64,
    /// `⌊√n⌋`: the generic reference, in group operations.
    pub naive_cost: u64,
    /// Cheon's predicted cost `√((n−1)/d) + √d`, in exponentiations.
    pub predicted_cost: u64,
    /// Why the attack could not run, if it could not.
    pub error: Option<String>,
    /// Elapsed time in ms (practicality note only; never the metric).
    pub elapsed_ms: u128,
}

fn isqrt(n: &BigUint) -> BigUint {
    if n.is_zero() {
        return BigUint::zero();
    }
    // Newton's method on BigUint.
    let mut x = BigUint::one() << n.bits().div_ceil(2);
    loop {
        let y = (&x + n / &x) >> 1u32;
        if y >= x {
            return x;
        }
        x = y;
    }
}

fn to_u64_sat(n: &BigUint) -> u64 {
    n.to_u64_digits().first().copied().unwrap_or(0)
}

/// Smallest primitive root modulo the prime `n`.
fn primitive_root(n: &BigUint) -> BigUint {
    let n_minus_1 = n - 1u32;
    let factors = factorise_small(&n_minus_1);
    let mut g = BigUint::from(2u32);
    loop {
        if factors
            .iter()
            .all(|(q, _)| g.modpow(&(&n_minus_1 / q), n) != BigUint::one())
        {
            return g;
        }
        g += 1u32;
    }
}

fn point_key(p: &Point) -> Option<(BigUint, BigUint)> {
    match p {
        Point::Infinity => None,
        Point::Affine { x, y } => Some((x.value.clone(), y.value.clone())),
    }
}

/// Find `k ∈ [0, order)` with `target = [gen^k]·base`, where `gen ∈ F_n^*`
/// has multiplicative order `order`.  Baby steps `[gen^i]base`, giant
/// steps `[gen^{−mj}]target`.  Returns `(k, exponentiations)`.
fn bsgs_in_exponent(
    curve: &CurveParams,
    base: &Point,
    target: &Point,
    n: &BigUint,
    gen: &BigUint,
    order: &BigUint,
) -> (Option<BigUint>, u64) {
    let a_fe = curve.a_fe();
    let m = isqrt(order) + 1u32;
    let m_u64 = to_u64_sat(&m);
    let mut exps = 0u64;
    let mut table: HashMap<(BigUint, BigUint), BigUint> = HashMap::new();
    let mut z = BigUint::one();
    for i in 0..m_u64 {
        let pt = base.scalar_mul(&z, &a_fe);
        exps += 1;
        if let Some(key) = point_key(&pt) {
            table.entry(key).or_insert_with(|| BigUint::from(i));
        }
        z = &z * gen % n;
    }
    // gen^{-m}
    let gen_inv = gen.modpow(&(n - 2u32), n);
    let step = gen_inv.modpow(&m, n);
    let mut z = BigUint::one();
    for j in 0..=m_u64 {
        let pt = target.scalar_mul(&z, &a_fe);
        exps += 1;
        if let Some(key) = point_key(&pt) {
            if let Some(i) = table.get(&key) {
                let k = (i + &m * BigUint::from(j)) % order;
                return (Some(k), exps);
            }
        }
        z = &z * &step % n;
    }
    (None, exps)
}

/// **Cheon's `p − 1` algorithm**: given `G`, `[α]G` and `[α^d]G` with
/// `d | n − 1`, recover `α`.
///
/// `d` must divide `n − 1`; otherwise the report carries an `error` and
/// no result.  Cost is `√((n−1)/d) + √d` exponentiations (plus two for
/// the shift and verification), independent of the size of `α`.
pub fn cheon_attack(
    curve: &CurveParams,
    g: &Point,
    alpha_g: &Point,
    alpha_d_g: &Point,
    n: &BigUint,
    d: &BigUint,
) -> CheonAttackReport {
    let t0 = std::time::Instant::now();
    let a_fe = curve.a_fe();
    let n_minus_1 = n - 1u32;
    let naive_cost = to_u64_sat(&isqrt(n));
    let mut report = CheonAttackReport {
        n: n.clone(),
        d: d.clone(),
        recovered_alpha: None,
        step1_exps: 0,
        step2_exps: 0,
        naive_cost,
        predicted_cost: 0,
        error: None,
        elapsed_ms: 0,
    };
    if d.is_zero() || !(&n_minus_1 % d).is_zero() {
        report.error = Some(format!("d = {} does not divide n − 1 = {}", d, n_minus_1));
        report.elapsed_ms = t0.elapsed().as_millis();
        return report;
    }
    let big_n = &n_minus_1 / d; // N = (n−1)/d
    report.predicted_cost = to_u64_sat(&isqrt(&big_n)) + to_u64_sat(&isqrt(d));

    let zeta = primitive_root(n);
    let zeta_hat = zeta.modpow(d, n); // order N

    // Step 1: α^d = ζ̂^{k₀}.
    let (k0, e1) = bsgs_in_exponent(curve, g, alpha_d_g, n, &zeta_hat, &big_n);
    report.step1_exps = e1;
    let k0 = match k0 {
        Some(k) => k,
        None => {
            report.error = Some("step 1 found no match (is [α^d]G genuine?)".into());
            report.elapsed_ms = t0.elapsed().as_millis();
            return report;
        }
    };

    // Step 2: α ζ^{−k₀} = ζ̌^{k₁}, ζ̌ = ζ^N of order d.
    let zeta_inv = zeta.modpow(&(n - 2u32), n);
    let shift = zeta_inv.modpow(&k0, n);
    let shifted = alpha_g.scalar_mul(&shift, &a_fe);
    let zeta_check = zeta.modpow(&big_n, n);
    let (k1, e2) = bsgs_in_exponent(curve, g, &shifted, n, &zeta_check, d);
    report.step2_exps = e2 + 1;
    let k1 = match k1 {
        Some(k) => k,
        None => {
            report.error = Some("step 2 found no match".into());
            report.elapsed_ms = t0.elapsed().as_millis();
            return report;
        }
    };
    let alpha = zeta.modpow(&(&k0 + &k1 * &big_n), n);
    // Verify: [α]G must equal the given [α]G.
    report.step2_exps += 1;
    if &g.scalar_mul(&alpha, &a_fe) == alpha_g {
        report.recovered_alpha = Some(alpha);
    } else {
        report.error = Some("recovered α failed verification".into());
    }
    report.elapsed_ms = t0.elapsed().as_millis();
    report
}

/// Render a Markdown report of Cheon's attack outcome.
pub fn format_visualization(report: &CheonAttackReport) -> String {
    use crate::visualize::color::{paint, FG_BRIGHT_GREEN, FG_BRIGHT_YELLOW};
    let mut s = String::new();
    s.push_str("# Cheon's auxiliary-input attack on DLP (p − 1 case)\n\n");
    s.push_str(&format!(
        "**Subgroup order `n`**: {} ({} bits)\n\n",
        report.n,
        report.n.bits()
    ));
    s.push_str(&format!(
        "**Exploited divisor**: `d = {}` (divides `n − 1`; auxiliary input `[α^d]G`)\n\n",
        report.d
    ));
    s.push_str("## Cost comparison\n\n");
    s.push_str("```\n");
    s.push_str(&format!(
        "  generic √n reference    : {:>10} group operations\n",
        report.naive_cost
    ));
    s.push_str(&format!(
        "  Cheon √((n−1)/d) + √d   : {:>10} exponentiations (predicted)\n",
        report.predicted_cost
    ));
    s.push_str(&format!(
        "  measured (this run)     : {} + {} = {} exponentiations\n\n",
        report.step1_exps,
        report.step2_exps,
        report.step1_exps + report.step2_exps
    ));
    s.push_str(
        "  one exponentiation ≈ 1.5·log₂ n group operations without\n  fixed-base tables; \
         the ratio to the reference is in group operations only\n  after that conversion.\n",
    );
    s.push_str("```\n\n");
    match (&report.recovered_alpha, &report.error) {
        (Some(alpha), _) => s.push_str(&format!(
            "  {} **`α = {}` recovered in {} ms**\n",
            paint("✓", FG_BRIGHT_GREEN),
            alpha,
            report.elapsed_ms
        )),
        (None, Some(err)) => s.push_str(&format!(
            "  {} attack did not complete: {}\n",
            paint("⚠", FG_BRIGHT_YELLOW),
            err
        )),
        (None, None) => s.push_str(&format!(
            "  {} attack did not complete\n",
            paint("⚠", FG_BRIGHT_YELLOW)
        )),
    }
    s
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// Toy curve with order 199; 199 − 1 = 198 = 2 · 3² · 11.
    fn small_curve() -> CurveParams {
        CurveParams {
            name: "cheon-test-199",
            p: BigUint::from(211u32),
            a: BigUint::zero(),
            b: BigUint::from(2u32),
            gx: BigUint::from(4u32),
            gy: BigUint::from(53u32),
            n: BigUint::from(199u32),
            h: 1,
        }
    }

    fn aux_inputs(curve: &CurveParams, alpha: u32, d: u32) -> (Point, Point, Point) {
        let g = curve.generator();
        let a_fe = curve.a_fe();
        let alpha_b = BigUint::from(alpha);
        let alpha_d = alpha_b.modpow(&BigUint::from(d), &curve.n);
        let alpha_g = g.scalar_mul(&alpha_b, &a_fe);
        let alpha_d_g = g.scalar_mul(&alpha_d, &a_fe);
        (g, alpha_g, alpha_d_g)
    }

    /// **Cheon recovers α** from `G, [α]G, [α^d]G` for every divisor of
    /// `n − 1` and several secrets.
    #[test]
    fn cheon_recovers_alpha_for_every_divisor() {
        let curve = small_curve();
        for &d in &[1u32, 2, 3, 6, 9, 11, 18, 22, 33, 66, 99, 198] {
            for &alpha in &[2u32, 5, 73, 100, 197] {
                let (g, ag, adg) = aux_inputs(&curve, alpha, d);
                let report = cheon_attack(&curve, &g, &ag, &adg, &curve.n, &BigUint::from(d));
                assert_eq!(
                    report.recovered_alpha,
                    Some(BigUint::from(alpha)),
                    "d = {d}, alpha = {alpha}: {:?}",
                    report.error
                );
            }
        }
    }

    /// **The auxiliary input is used**: a wrong `[α^d]G` makes step 1 fail
    /// instead of silently recovering α by brute force.
    #[test]
    fn cheon_needs_the_auxiliary_input() {
        let curve = small_curve();
        let (g, ag, _) = aux_inputs(&curve, 73, 11);
        let bogus = g.scalar_mul(&BigUint::from(5u32), &curve.a_fe()); // not [73^11]G
        let report = cheon_attack(&curve, &g, &ag, &bogus, &curve.n, &BigUint::from(11u32));
        assert_ne!(report.recovered_alpha, Some(BigUint::from(73u32)));
    }

    /// **A non-divisor is rejected** with an explanation.
    #[test]
    fn cheon_rejects_non_divisor() {
        let curve = small_curve();
        let (g, ag, adg) = aux_inputs(&curve, 73, 11);
        let report = cheon_attack(&curve, &g, &ag, &adg, &curve.n, &BigUint::from(7u32));
        assert!(report.recovered_alpha.is_none());
        assert!(report.error.is_some());
    }

    /// **Cost scales as √((n−1)/d) + √d**: the measured exponentiation
    /// count stays within a small constant of the prediction.
    #[test]
    fn cheon_cost_tracks_prediction() {
        let curve = small_curve();
        let (g, ag, adg) = aux_inputs(&curve, 73, 11);
        let report = cheon_attack(&curve, &g, &ag, &adg, &curve.n, &BigUint::from(11u32));
        let measured = report.step1_exps + report.step2_exps;
        // predicted √18 + √11 ≈ 4 + 3 = 7; BSGS spends ≤ 2(m+1) per search.
        assert!(measured <= 4 * report.predicted_cost + 8, "{measured}");
        assert!(report.predicted_cost < report.naive_cost);
    }

    /// **Visualization renders** the canonical sections.
    #[test]
    fn cheon_visualization_renders() {
        let report = CheonAttackReport {
            n: BigUint::from(199u32),
            d: BigUint::from(11u32),
            recovered_alpha: Some(BigUint::from(73u32)),
            step1_exps: 9,
            step2_exps: 8,
            naive_cost: 14,
            predicted_cost: 7,
            error: None,
            elapsed_ms: 2,
        };
        let s = format_visualization(&report);
        assert!(s.contains("Cheon"));
        assert!(s.contains("d = 11"));
        assert!(s.contains("exponentiations"));
    }
}
