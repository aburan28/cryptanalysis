//! # The boundary this thread measures against.
//!
//! `AGENTS.md` requires a boundary stated *before* optimising: a **floor**
//! derived from a counting argument, and a **reference** equal to the
//! best algorithm that already solves the same problem.  This module
//! computes both, in the repository's unit
//!
//! ```text
//!     S = total operations / √r,            r = the subgroup order,
//! ```
//!
//! which pins Pollard rho at a flat `S ≈ 1.25` and turns "did the
//! isogeny search help" into reading one column.
//!
//! ## The floor: you cannot enumerate the class
//!
//! The floor is **exact**, not estimated.  By Deuring and Waterhouse the
//! isogeny class of an ordinary curve holds `H(Δ)` isomorphism classes,
//! `Δ = t² − 4q`, and for ECC2K-130 that evaluates
//! ([`super::class_number`]) to
//!
//! ```text
//!     H(Δ) = 38 531 015 900 842 054 149  ≈  2^65.06 curves,
//! ```
//!
//! over four endomorphism-ring orders.  The formula is checked against
//! the exhaustive Kloosterman census at every `n` the census reaches, so
//! evaluating it at `n = 131` is an evaluation, not an extrapolation.
//!
//! A *generic* pigeonhole bound is carried alongside as a cross-check —
//! `2(2^n − 1)` curves into at most `4·2^{n/2} + 1` Hasse-admissible
//! traces gives a **mean** class of `2^{n/2 − 1}` — but it is only a
//! statement about the average.  The census makes the difference vivid:
//! at `n = 13` the ECC2K-130 analogue's class has exactly **one**
//! member, because `Δ_13 = −7` exactly.  Means do not bound particular
//! classes, which is why the thread prices the class it actually has.
//!
//! Charging **one operation per curve** — a free screen, which no real
//! screen is — an exhaustive isogeny-class search therefore costs
//!
//! ```text
//!     S_search  =  2^{65.06} / 2^{64.5}  =  1.48,
//! ```
//!
//! against rho's `S ≈ 0.077` on the same group.  The search is **19×
//! worse than the attack it is trying to improve, before it tests its
//! first curve.**  That is the floor, it is derived, and nothing inside
//! the thread can move it.
//!
//! ## The reference: rho on ECC2K-130
//!
//! `E(F_{2^131})` for `y² + xy = x³ + 1` has order `4r` with `r` a
//! 129-bit prime.  Parallel Pollard rho with the negation map and the
//! `131`-power Frobenius walks classes of size `2 · 131 = 262`, so its
//! expected iteration count is `√(π r / (2 · 262))`.
//! [`rho_reference`] computes it; the published figure for the ECC2K-130
//! effort is `≈ 2^60.9` iterations, which is what this reproduces.

use num_bigint::{BigInt, BigUint};
use num_traits::One;

use super::census::IsogenyCensus;

/// `#E(F_{2^131})` for the ECC2K-130 curve `y² + xy = x³ + 1`.
///
/// `2^131 + 1 − s_131`, with `s_k` the Koblitz trace recurrence at
/// `t_1 = −1`.
pub fn ecc2k130_order() -> BigUint {
    let s = super::census::koblitz_trace_recurrence(-1, 131);
    // `s_k` alternates in sign, so do the arithmetic signed and convert
    // once: `|s_131| ≈ 2^66` while `2^131` dwarfs it, so the count is
    // positive either way.
    let order = (BigInt::one() << 131u32) + BigInt::one() - BigInt::from(s);
    order.to_biguint().expect("Hasse keeps #E positive")
}

/// The prime-order subgroup ECC2K-130's discrete logarithm lives in:
/// `#E / 4`.
pub fn ecc2k130_subgroup_order() -> BigUint {
    ecc2k130_order() / BigUint::from(4u32)
}

/// `log2` of a big integer, to double precision.
pub fn log2_big(v: &BigUint) -> f64 {
    let bits = v.bits();
    if bits == 0 {
        return f64::NEG_INFINITY;
    }
    // Take the top 53 bits as a mantissa so the result is accurate
    // regardless of magnitude.
    let shift = bits.saturating_sub(53);
    let top = v >> shift;
    let mantissa: f64 = top.to_string().parse().unwrap_or(f64::NAN);
    mantissa.log2() + shift as f64
}

/// Pollard rho on a group of order `r`, walking equivalence classes of
/// size `automorphisms`.
#[derive(Clone, Copy, Debug)]
pub struct RhoReference {
    /// `log2` of the expected iteration count.
    pub iterations_log2: f64,
    /// `log2 √r`, the unit's denominator.
    pub sqrt_r_log2: f64,
    /// `S = iterations / √r`.
    pub s_unit: f64,
    /// The class size walked (`1` for plain rho, `2n` with negation and
    /// Frobenius on a Koblitz curve over `F_{2^n}`).
    pub automorphisms: u64,
}

/// Expected rho cost: `√(π r / (2 · automorphisms))` iterations.
///
/// `automorphisms = 1` gives the textbook `√(π r / 2)`, i.e. a flat
/// `S = √(π/2) ≈ 1.2533` at every size — the repository's rho row.
pub fn rho_reference(r: &BigUint, automorphisms: u64) -> RhoReference {
    let log2_r = log2_big(r);
    let log2_pi = std::f64::consts::PI.log2();
    let iterations_log2 = 0.5 * (log2_r + log2_pi - 1.0 - (automorphisms as f64).log2());
    let sqrt_r_log2 = 0.5 * log2_r;
    RhoReference {
        iterations_log2,
        sqrt_r_log2,
        s_unit: (iterations_log2 - sqrt_r_log2).exp2(),
        automorphisms,
    }
}

/// `log2` of the pigeonhole lower bound on the mean isogeny class size
/// over `F_{2^n}`: `2(2^n − 1) / (4·2^{n/2} + 1) ≈ 2^{n/2 − 1}`.
pub fn class_size_log2_floor(n: u32) -> f64 {
    let curves = 2.0 * ((2.0f64).powi(n as i32) - 1.0);
    let traces = 4.0 * (2.0f64).powf(n as f64 / 2.0) + 1.0;
    (curves / traces).log2()
}

/// Pigeonhole floor on the class size, as a count (saturating at
/// `f64` precision — at `n = 131` read `class_size_log2_floor` instead).
pub fn class_size_estimate(n: u32) -> f64 {
    class_size_log2_floor(n).exp2()
}

/// The complete boundary row: what an exhaustive isogeny-class search
/// costs, against what rho costs, on the same group and in one unit.
#[derive(Clone, Copy, Debug)]
pub struct SearchBoundary {
    /// Extension degree.
    pub n: u32,
    /// `log2` of the subgroup order.
    pub subgroup_log2: f64,
    /// `log2 H(Δ)` — the **exact** class size, the number of curves an
    /// exhaustive search must touch.
    pub class_log2: f64,
    /// `log2` of the generic pigeonhole mean, carried as a cross-check
    /// on the exact value and never used as the floor.
    pub pigeonhole_log2: f64,
    /// Rho with the curve's automorphisms.
    pub rho: RhoReference,
    /// `S` for the search, charging **one** operation per curve.
    pub search_s: f64,
    /// `search_s / rho.s_unit` — the ratio column.  Above `1` means the
    /// search is worse than the attack it hopes to improve.
    pub ratio_to_rho: f64,
}

/// Build the boundary from an **exact** class size.
pub fn search_boundary(
    n: u32,
    r: &BigUint,
    automorphisms: u64,
    class_size: &BigUint,
) -> SearchBoundary {
    let rho = rho_reference(r, automorphisms);
    let class_log2 = log2_big(class_size);
    let search_s = (class_log2 - rho.sqrt_r_log2).exp2();
    SearchBoundary {
        n,
        subgroup_log2: log2_big(r),
        class_log2,
        pigeonhole_log2: class_size_log2_floor(n),
        rho,
        search_s,
        ratio_to_rho: search_s / rho.s_unit,
    }
}

/// The boundary for ECC2K-130 itself: `n = 131`, `r = #E/4`, rho walking
/// classes of size `2 · 131 = 262`, and the exact class size `H(Δ)`.
pub fn ecc2k130_boundary() -> SearchBoundary {
    search_boundary(
        131,
        &ecc2k130_subgroup_order(),
        2 * 131,
        &super::class_number::ecc2k130_class_size().class_size,
    )
}

/// Measured-versus-predicted class size at a reachable `n`.
///
/// The pigeonhole bound is about the *mean* class; this reports the mean
/// the census actually has and where ECC2K-130's own class sits relative
/// to it, so the `n = 131` extrapolation rests on a measured ratio
/// rather than on an assumption that the class is typical.
#[derive(Clone, Copy, Debug)]
pub struct ClassSizeCalibration {
    pub n: u32,
    /// Pigeonhole floor on the mean.
    pub predicted_mean: f64,
    /// Mean class size the census actually has.
    pub measured_mean: f64,
    /// Size of the ECC2K-130-analogue class.
    pub koblitz_class: usize,
    /// `koblitz_class / measured_mean`.
    pub koblitz_over_mean: f64,
}

/// Calibrate the pigeonhole bound against an exhaustive census.
pub fn calibrate_class_size(census: &IsogenyCensus) -> ClassSizeCalibration {
    let stats = census.stats();
    ClassSizeCalibration {
        n: census.n,
        predicted_mean: class_size_estimate(census.n),
        measured_mean: stats.mean,
        koblitz_class: stats.koblitz_class_size,
        koblitz_over_mean: stats.koblitz_class_size as f64 / stats.mean.max(1.0),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::koblitz_index_calculus::find_irreducible;

    /// Plain rho must sit at the repository's flat `S ≈ 1.25` at every
    /// size — the check that the unit is the same one other threads use.
    #[test]
    fn plain_rho_is_flat_in_s() {
        for bits in [40u32, 80, 129, 200] {
            let r = BigUint::one() << bits;
            let rho = rho_reference(&r, 1);
            assert!(
                (rho.s_unit - (std::f64::consts::PI / 2.0).sqrt()).abs() < 1e-9,
                "bits = {bits}: S = {}",
                rho.s_unit
            );
        }
    }

    /// The ECC2K-130 group must come out with the published shape: a
    /// cofactor of 4, a 129-bit prime-order subgroup, and rho at about
    /// `2^60.9` iterations.
    #[test]
    fn ecc2k130_group_matches_the_challenge() {
        let order = ecc2k130_order();
        assert_eq!(
            &order % BigUint::from(4u32),
            BigUint::from(0u32),
            "cofactor 4 divides the order"
        );
        let r = ecc2k130_subgroup_order();
        // The published ECC2K-130 subgroup order.  Reproducing it from
        // the trace recurrence alone is the check that the group this
        // thread prices is the challenge's group and not a lookalike.
        assert_eq!(
            r.to_string(),
            "680564733841876926932320129493409985129",
            "subgroup order must match the published challenge parameter"
        );
        assert_eq!(r.bits(), 130, "n sits just above 2^129");
        let rho = rho_reference(&r, 2 * 131);
        assert!(
            (rho.iterations_log2 - 60.9).abs() < 0.5,
            "rho ≈ 2^60.9 iterations, got 2^{}",
            rho.iterations_log2
        );
    }

    /// The floor must exceed the reference: enumerating the class is
    /// worse than solving the DLP, before any curve is tested.
    #[test]
    fn exhaustive_search_is_above_the_rho_reference() {
        let b = ecc2k130_boundary();
        assert!(
            b.ratio_to_rho > 10.0,
            "search S = {}, rho S = {}, ratio {}",
            b.search_s,
            b.rho.s_unit,
            b.ratio_to_rho
        );
        assert!(
            (b.class_log2 - 65.06).abs() < 0.02,
            "exact class size is 2^65.06, got 2^{}",
            b.class_log2
        );
        assert!(
            b.class_log2 > b.rho.iterations_log2,
            "touching every curve must cost more than rho: 2^{} vs 2^{}",
            b.class_log2,
            b.rho.iterations_log2
        );
    }

    /// The pigeonhole bound must actually bound the measured mean.
    #[test]
    fn pigeonhole_bound_holds_on_the_census() {
        for n in [7u32, 9, 11] {
            let irr = find_irreducible(n).unwrap();
            let census = IsogenyCensus::build(n, &irr);
            let c = calibrate_class_size(&census);
            assert!(
                c.measured_mean >= c.predicted_mean - 1e-9,
                "n = {n}: measured {} < predicted floor {}",
                c.measured_mean,
                c.predicted_mean
            );
        }
    }
}
