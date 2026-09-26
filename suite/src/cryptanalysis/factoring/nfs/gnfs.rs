//! **GNFS front end**: base-m polynomial selection, then the shared NFS
//! core.
//!
//! The degree defaults to 3 up to 65 digits, 4 up to 100 and 5 above
//! (the asymptotically optimal `d ≈ (3 ln n / ln ln n)^{1/3}` is 3–4 in
//! this range; degree 4 measured several times slower than 3 at 59
//! digits here).  The leading coefficient is searched over
//! `1..=lead_search`, each candidate is rotated, and the best by
//! [`polysel::score`](super::polysel::score) is kept.  See [`super`] for
//! the algorithm and its limits.

use num_bigint::BigUint;
use serde::Serialize;
use std::time::Instant;

use super::super::arith::{big_mod_u64, decimal_digits, is_probable_prime, perfect_power, secs};
use super::super::ProgressFn;
use super::polysel::{select_base_m, Selection};
use super::{default_bounds, run_core, NfsParams, NfsReport};

/// Options for [`gnfs`].
#[derive(Clone, Debug, Default, Serialize)]
pub struct GnfsParams {
    /// Polynomial degree; `None` chooses from the size of `n`.
    pub degree: Option<usize>,
    /// Leading coefficients `1..=lead_search` tried by the base-m search;
    /// `None`: 40 below 45 digits, 200 from there.
    pub lead_search: Option<u64>,
    /// Rotations `f + (j·x + k)(x − m)`, `|k| ≤ rotation`, `|j| ≤ 2`, tried
    /// per leading coefficient (0 disables); `None`: 64.
    pub rotation: Option<i64>,
    /// Sieve and linear-algebra parameters.
    pub nfs: NfsParams,
}

/// Default GNFS degree for an input of `digits` decimal digits.
pub fn default_degree(digits: usize) -> usize {
    match digits {
        0..=65 => 3,
        66..=100 => 4,
        _ => 5,
    }
}

/// Answer the cases the sieve cannot handle; `true` if the report is final.
pub(crate) fn trivial_cases(report: &mut NfsReport) -> bool {
    let n = report.n.clone();
    if n < BigUint::from(4u32) || is_probable_prime(&n) {
        report.failure = Some("n is < 4 or (probably) prime".into());
        return true;
    }
    for p in super::super::arith::primes_up_to(10_000) {
        if big_mod_u64(&n, p) == 0 {
            report.accept(BigUint::from(p));
            report.found_in_polyselect = true;
            return true;
        }
    }
    if let Some((r, _)) = perfect_power(&n) {
        report.accept(r);
        report.found_in_polyselect = true;
        return true;
    }
    false
}

/// Factor `n` with the general number field sieve.  Returns one verified
/// proper factor (or the reason for failure) and the statistics of every
/// stage.
pub fn gnfs(n: &BigUint, params: &GnfsParams, progress: ProgressFn) -> NfsReport {
    let t0 = Instant::now();
    let mut report = NfsReport::new("gnfs", n);
    if trivial_cases(&mut report) {
        report.total_seconds = secs(t0);
        return report;
    }
    let digits = decimal_digits(n);
    let d = params
        .degree
        .unwrap_or_else(|| default_degree(digits))
        .max(2);
    let (rb, ab, area) = default_bounds(digits);
    let rb = params.nfs.rational_bound.unwrap_or(rb);
    let ab = params.nfs.algebraic_bound.unwrap_or(ab);
    let lead_search = params
        .lead_search
        .unwrap_or(if digits < 45 { 40 } else { 200 });
    let rotation = params.rotation.unwrap_or(64);
    let sel = select_base_m(n, d, lead_search, rotation, area, rb, ab);
    report.polyselect_seconds = secs(t0);
    match sel {
        None => {
            report.failure = Some(format!("no usable degree-{d} base-m polynomial"));
        }
        Some(Selection::Factor(g)) => {
            report.accept(g);
            report.found_in_polyselect = true;
        }
        Some(Selection::Poly(pc)) => {
            run_core(
                &mut report,
                &pc.f,
                &pc.m,
                pc.skew,
                0.35,
                digits,
                &params.nfs,
                progress,
            );
        }
    }
    report.total_seconds = secs(t0);
    report
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn gnfs_factors_30_digit_semiprime() {
        let p: BigUint = "100000000000000003".parse().unwrap();
        let q: BigUint = "1000000000039".parse().unwrap();
        let n = &p * &q;
        let r = gnfs(&n, &GnfsParams::default(), None);
        assert!(r.verified, "{:?}", r.failure);
        assert!(!r.found_in_polyselect);
        assert_eq!(r.factor.as_ref().unwrap(), &q);
        assert_eq!(r.factor.unwrap() * r.cofactor.unwrap(), n);
    }

    #[test]
    fn gnfs_non_monic_polynomial() {
        // Force a leading coefficient search that settles on c_d > 1 for at
        // least some inputs; the parity column must keep |S| even.
        let p: BigUint = "3267000013".parse().unwrap();
        let q: BigUint = "100000000000000000039".parse().unwrap();
        let n = &p * &q;
        let params = GnfsParams {
            lead_search: Some(60),
            ..Default::default()
        };
        let r = gnfs(&n, &params, None);
        assert!(r.verified, "{:?}", r.failure);
        assert_eq!(r.factor.unwrap() * r.cofactor.unwrap(), n);
    }

    #[test]
    fn gnfs_answers_trivial_inputs() {
        let r = gnfs(&BigUint::from(1_000_003u64), &GnfsParams::default(), None);
        assert!(r.factor.is_none());
        let sq = BigUint::from(1_000_003u64) * 1_000_003u64;
        let r = gnfs(&sq, &GnfsParams::default(), None);
        assert!(r.verified && r.found_in_polyselect);
    }
}
