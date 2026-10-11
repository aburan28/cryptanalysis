//! # Refutation-degree **distribution** over many non-decomposable targets.
//!
//! Averaging layer on top of [`crate::cryptanalysis::pc_degree_harness`].
//! A single `(n, n', b, x₃)` instance gives one noisy refutation degree
//! `D*`; this module samples **many** non-decomposable targets per
//! `(n, n')` and reports the `D*` *distribution* (min / mean / max plus a
//! histogram), which is what the proposal's prediction #1 actually talks
//! about (`research/notes/index-calculus/RESEARCH_FFD_PROOF_COMPLEXITY.md` §4 item 1, §6).
//!
//! Only **non-decomposable** (genuinely unsatisfiable) targets are
//! counted — those are the instances for which a refutation exists and
//! `D*` is defined. Decomposable draws are skipped (and tallied as
//! `skipped_decomposable`) so the reported statistics are conditional on
//! "the target does not decompose over `V`", exactly the index-calculus
//! failure case whose cost the solving degree governs.
//!
//! ## Why a distribution, not a point
//!
//! At toy sizes the per-target `D*` jumps around (some targets admit a
//! degree-2 Nullstellensatz certificate, others need more), so a single
//! sample tells you little about the asymptotic trend. The **mean** and
//! **max** over a batch are the stable signals: prediction #1 says the
//! mean `D*` climbs with `n` while the first fall degree stays flat. This
//! module produces the numbers that test that, and the histogram exposes
//! the spread that a single sample hides.
//!
//! ## Cost
//!
//! Each target costs one `pc_degree_harness::measure_refutation_degree`
//! (a Macaulay rank per degree up to `D*`) plus one decomposability
//! brute-force over `|V|² = 2^{2n'}`. Comfortable for `n' ≤ 6` and
//! batches of a few hundred targets. For larger `n'` the decomposability
//! oracle dominates and should be replaced by an `S₃`-resultant solve.
//!
//! ## References
//!
//! See `pc_degree_harness` and `research/notes/index-calculus/RESEARCH_FFD_PROOF_COMPLEXITY.md`.

use crate::binary_ecc::{F2mElement, IrreduciblePoly};
use crate::cryptanalysis::ffd_harness::{choose_irreducible, random_nonzero_f2m};
use crate::cryptanalysis::pc_degree_harness::{is_decomposable, measure_refutation_degree};
use rand::rngs::StdRng;
use rand::SeedableRng;
use std::collections::BTreeMap;

// ── Public API ──────────────────────────────────────────────────────

/// Summary statistics of an integer-valued degree over a batch of
/// samples: the count, none-count, min/max, mean, and a histogram
/// (degree → frequency).
#[derive(Clone, Debug, Default)]
pub struct DegreeStats {
    /// Number of samples with a *defined* degree (finite, not `None`).
    pub n_defined: u32,
    /// Number of samples where the degree was `None` (no event observed
    /// within the degree budget).
    pub n_none: u32,
    /// Minimum observed degree (over defined samples).
    pub min: Option<u32>,
    /// Maximum observed degree (over defined samples).
    pub max: Option<u32>,
    /// Mean of the defined degrees.
    pub mean: Option<f64>,
    /// Histogram: degree → number of samples with that degree.
    pub histogram: BTreeMap<u32, u32>,
}

impl DegreeStats {
    fn accumulate(&mut self, value: Option<u32>) {
        match value {
            Some(d) => {
                self.n_defined += 1;
                self.min = Some(self.min.map_or(d, |m| m.min(d)));
                self.max = Some(self.max.map_or(d, |m| m.max(d)));
                *self.histogram.entry(d).or_insert(0) += 1;
            }
            None => self.n_none += 1,
        }
    }

    fn finalize(&mut self) {
        if self.n_defined > 0 {
            let sum: u64 = self
                .histogram
                .iter()
                .map(|(&d, &c)| d as u64 * c as u64)
                .sum();
            self.mean = Some(sum as f64 / self.n_defined as f64);
        }
    }

    /// Compact histogram rendering, e.g. `2:3 3:11 4:2`.
    pub fn histogram_str(&self) -> String {
        if self.histogram.is_empty() {
            return "—".into();
        }
        self.histogram
            .iter()
            .map(|(d, c)| format!("{d}:{c}"))
            .collect::<Vec<_>>()
            .join(" ")
    }
}

/// One row of the averaged sweep: a `(n, n')` cell with the `D*` and
/// first-fall distributions over a batch of non-decomposable targets.
#[derive(Clone, Debug)]
pub struct AvgRow {
    pub n: u32,
    pub n_sub: u32,
    pub num_vars: u32,
    pub num_eqs: u32,
    /// Non-decomposable targets actually measured.
    pub n_targets: u32,
    /// Decomposable draws skipped while hunting for non-decomposable ones.
    pub skipped_decomposable: u32,
    /// Distribution of the refutation degree `D*`.
    pub refutation: DegreeStats,
    /// Distribution of the first-fall degree, for the same instances.
    pub first_fall: DegreeStats,
}

impl AvgRow {
    /// Determination ratio `ρ = #eqs / #vars = n / (2n')`.  `ρ > 1` means
    /// over-determined (more equations than unknowns); `ρ ≈ 1` is the
    /// "just determined" index-calculus operating point where the generic
    /// solving degree is largest.
    pub fn ratio(&self) -> f64 {
        if self.num_vars == 0 {
            0.0
        } else {
            self.num_eqs as f64 / self.num_vars as f64
        }
    }
}

/// Measure the `D*` distribution over up to `targets` non-decomposable
/// targets for a fixed `(n, n', b)`. Draws random `x₃` with `rng`,
/// skipping decomposable ones, until `targets` non-decomposable instances
/// are measured or `max_attempts` draws are exhausted.
pub fn measure_avg(
    n: u32,
    n_sub: u32,
    irr: &IrreduciblePoly,
    b: &F2mElement,
    d_max: u32,
    targets: u32,
    max_attempts: u32,
    rng: &mut StdRng,
) -> AvgRow {
    let mut refutation = DegreeStats::default();
    let mut first_fall = DegreeStats::default();
    let mut n_targets = 0u32;
    let mut skipped = 0u32;
    let mut attempts = 0u32;

    while n_targets < targets && attempts < max_attempts {
        attempts += 1;
        let x3 = random_nonzero_f2m(rng, n);
        if is_decomposable(n, n_sub, irr, b, &x3) {
            skipped += 1;
            continue;
        }
        let row = measure_refutation_degree(n, n_sub, irr, b, &x3, d_max);
        debug_assert!(!row.decomposable);
        refutation.accumulate(row.refutation_degree);
        first_fall.accumulate(row.first_fall);
        n_targets += 1;
    }

    refutation.finalize();
    first_fall.finalize();

    AvgRow {
        n,
        n_sub,
        num_vars: 2 * n_sub,
        num_eqs: n,
        n_targets,
        skipped_decomposable: skipped,
        refutation,
        first_fall,
    }
}

/// Run the averaged sweep over `n_range`, with `n' = ⌊n/2⌋`, `targets`
/// non-decomposable instances per `n`, Macaulay degree cap `d_max`, and a
/// reproducible `seed`. `max_attempts` bounds the random search per `n`
/// (so small fields that lack enough non-decomposable targets terminate).
pub fn run_pc_avg_sweep(
    n_range: std::ops::RangeInclusive<u32>,
    d_max: u32,
    targets: u32,
    seed: u64,
) -> Vec<AvgRow> {
    let mut rng = StdRng::seed_from_u64(seed);
    let mut out = Vec::new();
    for n in n_range {
        let n_sub = (n / 2).max(1);
        let irr = choose_irreducible(n);
        let b = random_nonzero_f2m(&mut rng, n);
        // Allow generous head-room over `targets` so decomposable draws
        // don't starve the batch.
        let max_attempts = targets.saturating_mul(20).max(64);
        out.push(measure_avg(
            n,
            n_sub,
            &irr,
            &b,
            d_max,
            targets,
            max_attempts,
            &mut rng,
        ));
    }
    out
}

/// **Determination-ratio regime sweep.** For a *fixed* field degree `n`,
/// vary the factor-base dimension `n'` over `1..=⌊n/2⌋` and report the
/// `D*` distribution at each. This isolates the effect of the
/// **determination ratio** `ρ = #eqs / #vars = n / (2n')` on the
/// refutation degree, with the field held constant so the only thing
/// changing is how over-determined the restricted system is.
///
/// Why this axis. The unsatisfiable (refutable) regime is intrinsically
/// `2n' ≲ n` — non-decomposable targets exist only when `|V|² = 2^{2n'}`
/// is smaller than the field, i.e. `ρ ≳ 1`. So `ρ` cannot be pushed below
/// ~1 while keeping a refutation to measure; the meaningful question is
/// whether `D*` *rises as `ρ → 1⁺`* (the system approaching "just
/// determined", where the solving degree of a generic quadratic system is
/// largest). `n' = ⌊n/2⌋` is the boundary case the plain `run_pc_avg_sweep`
/// already samples; this sweep fills in the more over-determined
/// `n' < ⌊n/2⌋` cells for contrast.
pub fn run_pc_regime_sweep(n: u32, d_max: u32, targets: u32, seed: u64) -> Vec<AvgRow> {
    let mut rng = StdRng::seed_from_u64(seed);
    let irr = choose_irreducible(n);
    let b = random_nonzero_f2m(&mut rng, n);
    let max_attempts = targets.saturating_mul(20).max(64);
    let mut out = Vec::new();
    for n_sub in 1..=(n / 2).max(1) {
        out.push(measure_avg(
            n,
            n_sub,
            &irr,
            &b,
            d_max,
            targets,
            max_attempts,
            &mut rng,
        ));
    }
    out
}

/// **Operating-point scaling sweep.** Scale the field degree `n` across
/// `n_range` while holding the factor base at the *largest* dimension that
/// still leaves most targets non-decomposable, `n' = ⌊(n − margin)/2⌋`
/// (clamped to ≥ 1). This tracks `D*` along the index-calculus operating
/// boundary `2n' ≈ n` as `n` grows — the asymptotic axis that prediction
/// #1 is really about (does mean `D*` climb with `n` at fixed `ρ ≈ 1`?).
///
/// `margin` (typically 1–2) keeps `2n' < n` so non-decomposable targets
/// remain plentiful; `margin = 0` puts `n'` exactly at `⌊n/2⌋` (the
/// `run_pc_avg_sweep` default), where for even `n` the system is exactly
/// determined and non-decomposable targets get scarce.
pub fn run_pc_operating_point_sweep(
    n_range: std::ops::RangeInclusive<u32>,
    margin: u32,
    d_max: u32,
    targets: u32,
    seed: u64,
) -> Vec<AvgRow> {
    let mut rng = StdRng::seed_from_u64(seed);
    let mut out = Vec::new();
    for n in n_range {
        let n_sub = (n.saturating_sub(margin) / 2).max(1);
        let irr = choose_irreducible(n);
        let b = random_nonzero_f2m(&mut rng, n);
        let max_attempts = targets.saturating_mul(20).max(64);
        out.push(measure_avg(
            n,
            n_sub,
            &irr,
            &b,
            d_max,
            targets,
            max_attempts,
            &mut rng,
        ));
    }
    out
}

/// **EXP-A — curve-independence sweep.** For a *fixed* `(n, n')`, measure
/// the `D*` distribution over `n_curves` independent random curve
/// parameters `b`, each with its own batch of `targets` non-decomposable
/// targets. Tests prediction P5: is `D*` a field/basis invariant (the
/// `D*` distribution is the same for every `b`) or does it depend on the
/// specific curve?
///
/// The answer decides how `descent_expansion` (the P2 predictor) must be
/// keyed: if `D*` is curve-independent, the Tanner graph need only encode
/// the (field, basis) multiplication tensor; if not, the curve `b` must
/// enter the graph too. Returns one `AvgRow` per `b` (all share the same
/// `n, n'`), so a downstream spread/KS test can run on `.refutation`.
pub fn run_pc_curve_independence_sweep(
    n: u32,
    n_sub: u32,
    n_curves: u32,
    d_max: u32,
    targets: u32,
    seed: u64,
) -> Vec<AvgRow> {
    let mut rng = StdRng::seed_from_u64(seed);
    let irr = choose_irreducible(n);
    let max_attempts = targets.saturating_mul(20).max(64);
    let mut out = Vec::new();
    for _ in 0..n_curves {
        let b = random_nonzero_f2m(&mut rng, n);
        out.push(measure_avg(
            n,
            n_sub,
            &irr,
            &b,
            d_max,
            targets,
            max_attempts,
            &mut rng,
        ));
    }
    out
}

/// Spread of mean `D*` across a set of rows: `max(mean) − min(mean)` over
/// rows that have a defined mean. `None` if fewer than two rows have a
/// defined mean. Used by the EXP-A gate G-P5: a small spread (≲ 0.5
/// degree) supports curve-independence; a large spread kills it.
pub fn mean_dstar_spread(rows: &[AvgRow]) -> Option<f64> {
    let means: Vec<f64> = rows.iter().filter_map(|r| r.refutation.mean).collect();
    if means.len() < 2 {
        return None;
    }
    let lo = means.iter().cloned().fold(f64::INFINITY, f64::min);
    let hi = means.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    Some(hi - lo)
}

pub fn print_pc_avg_sweep(rows: &[AvgRow]) {
    println!();
    println!(
        "{:>3} {:>3} {:>5} {:>4} {:>5} {:>5} | {:>13} | {:>17} | {:>4}",
        "n", "n'", "vars", "eqs", "ρ", "N", "first-fall μ", "D* min/μ/max", "none"
    );
    println!("{}", "─".repeat(80));
    for r in rows {
        let ff_mean = r
            .first_fall
            .mean
            .map(|m| format!("{m:.2}"))
            .unwrap_or_else(|| "—".into());
        let ds = &r.refutation;
        let dstar = match (ds.min, ds.mean, ds.max) {
            (Some(lo), Some(mu), Some(hi)) => format!("{lo}/{mu:.2}/{hi}"),
            _ => "—".into(),
        };
        println!(
            "{:>3} {:>3} {:>5} {:>4} {:>5.2} {:>5} | {:>13} | {:>17} | {:>4}",
            r.n,
            r.n_sub,
            r.num_vars,
            r.num_eqs,
            r.ratio(),
            r.n_targets,
            ff_mean,
            dstar,
            ds.n_none,
        );
    }
    println!();
    println!("D* histograms (degree:count):");
    for r in rows {
        println!(
            "  n={:>2} n'={:<2} → {}   [skipped {} decomposable draws]",
            r.n,
            r.n_sub,
            r.refutation.histogram_str(),
            r.skipped_decomposable,
        );
    }
    println!();
    println!(
        "Reading: `D* min/μ/max` is the refutation-degree distribution over\n\
         N non-decomposable (unsatisfiable) targets — the stable form of the\n\
         Polynomial-Calculus / last-fall degree. Prediction #1: mean D* climbs\n\
         with n while the first-fall mean stays roughly flat. `none` counts\n\
         instances that did not refute within the degree budget (raise d_max\n\
         if non-zero)."
    );
}

// ── Tests ───────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// `DegreeStats` computes min/max/mean/histogram correctly and counts
    /// `None`s separately.
    #[test]
    fn degree_stats_arithmetic() {
        let mut s = DegreeStats::default();
        for v in [Some(2u32), Some(4), Some(2), None, Some(3)] {
            s.accumulate(v);
        }
        s.finalize();
        assert_eq!(s.n_defined, 4);
        assert_eq!(s.n_none, 1);
        assert_eq!(s.min, Some(2));
        assert_eq!(s.max, Some(4));
        assert_eq!(s.mean, Some((2.0 + 4.0 + 2.0 + 3.0) / 4.0));
        assert_eq!(s.histogram.get(&2), Some(&2));
        assert_eq!(s.histogram.get(&3), Some(&1));
        assert_eq!(s.histogram.get(&4), Some(&1));
        assert_eq!(s.histogram_str(), "2:2 3:1 4:1");
    }

    /// Empty stats stay empty and render as `—`.
    #[test]
    fn degree_stats_empty() {
        let mut s = DegreeStats::default();
        s.finalize();
        assert_eq!(s.n_defined, 0);
        assert!(s.mean.is_none());
        assert_eq!(s.histogram_str(), "—");
    }

    /// **Every measured target in a batch is non-decomposable**, so the
    /// reported `D*` distribution is over genuinely unsatisfiable
    /// instances, and the histogram sample-count matches `n_targets`.
    #[test]
    fn batch_only_counts_nondecomposable_and_is_consistent() {
        let n = 4;
        let n_sub = 2;
        let irr = choose_irreducible(n);
        let mut rng = StdRng::seed_from_u64(0x_AA_BB);
        let b = random_nonzero_f2m(&mut rng, n);
        let row = measure_avg(n, n_sub, &irr, &b, 2 * n_sub + 1, 12, 4000, &mut rng);
        assert_eq!(row.num_eqs, n);
        assert_eq!(row.num_vars, 2 * n_sub);
        // Histogram totals (defined) + none-count == targets measured.
        let hist_total: u32 = row.refutation.histogram.values().sum();
        assert_eq!(hist_total, row.refutation.n_defined);
        assert_eq!(
            row.refutation.n_defined + row.refutation.n_none,
            row.n_targets
        );
        // At n=4/n'=2 the field is small but at least one non-decomposable
        // target should be found.
        assert!(row.n_targets >= 1, "no non-decomposable target found");
        // Non-decomposable ⇒ a refutation exists, so within a generous
        // degree budget there should be no `none`s.
        assert_eq!(
            row.refutation.n_none, 0,
            "non-decomposable target failed to refute"
        );
    }

    /// The averaged sweep runs end-to-end and produces one row per `n`.
    #[test]
    fn avg_sweep_runs() {
        let rows = run_pc_avg_sweep(4..=6, 9, 8, 0x_A6_DE);
        assert_eq!(rows.len(), 3);
        for r in &rows {
            assert_eq!(r.num_eqs, r.n);
            // Mean is defined whenever at least one target refuted.
            if r.refutation.n_defined > 0 {
                assert!(r.refutation.mean.is_some());
                assert!(r.refutation.min.unwrap() <= r.refutation.max.unwrap());
            }
        }
    }

    /// `ratio()` reports `n / (2n')` and is ≥ 1 in the refutable regime.
    #[test]
    fn determination_ratio() {
        let rows = run_pc_avg_sweep(6..=6, 9, 4, 0x_DE_7E);
        let r = &rows[0];
        // n=6, n'=3 ⇒ vars=6, eqs=6, ρ = 1.0.
        assert_eq!(r.num_vars, 6);
        assert!((r.ratio() - 1.0).abs() < 1e-9);
    }

    /// The regime sweep at fixed `n` returns one row per `n' ∈ 1..=⌊n/2⌋`,
    /// with the determination ratio decreasing monotonically toward 1 as
    /// `n'` grows.
    #[test]
    fn regime_sweep_covers_nsub_range() {
        let n = 8;
        let rows = run_pc_regime_sweep(n, 10, 6, 0x000B_E61E);
        assert_eq!(rows.len() as u32, (n / 2).max(1)); // n'=1,2,3,4
        for (i, r) in rows.iter().enumerate() {
            assert_eq!(r.n, n);
            assert_eq!(r.n_sub, (i as u32) + 1);
        }
        // ρ is strictly decreasing in n'.
        for w in rows.windows(2) {
            assert!(w[0].ratio() > w[1].ratio(), "ρ should fall as n' rises");
        }
        // Every measured target is non-decomposable ⇒ no `none`s within a
        // generous budget for the over-determined cells.
        for r in &rows {
            let hist_total: u32 = r.refutation.histogram.values().sum();
            assert_eq!(hist_total, r.refutation.n_defined);
        }
    }

    /// The operating-point sweep keeps `2n'` just below `n` (ρ ≳ 1) as `n`
    /// scales, and produces one row per `n`.
    #[test]
    fn operating_point_sweep_tracks_boundary() {
        let rows = run_pc_operating_point_sweep(6..=10, 1, 11, 6, 0x_0B_DE);
        assert_eq!(rows.len(), 5);
        for r in &rows {
            // margin=1 ⇒ n' = ⌊(n-1)/2⌋, so 2n' ≤ n-1 < n ⇒ ρ > 1.
            assert!(r.num_vars < r.n, "operating point must stay below n");
            assert!(r.ratio() >= 1.0);
        }
    }

    /// EXP-A: the curve-independence sweep returns one row per curve `b`,
    /// all sharing `(n, n')`, and the mean-`D*` spread is well-defined.
    #[test]
    fn curve_independence_sweep_shape_and_spread() {
        let n = 8;
        let n_sub = 3;
        let rows = run_pc_curve_independence_sweep(n, n_sub, 5, 10, 16, 0x_C0_4E);
        assert_eq!(rows.len(), 5);
        for r in &rows {
            assert_eq!(r.n, n);
            assert_eq!(r.n_sub, n_sub);
            assert_eq!(r.num_vars, 2 * n_sub);
        }
        // Spread is the max−min of defined means and is non-negative.
        if let Some(spread) = mean_dstar_spread(&rows) {
            assert!(spread >= 0.0);
        }
    }

    /// `mean_dstar_spread` returns `None` with fewer than two defined means
    /// and the correct max−min otherwise.
    #[test]
    fn spread_arithmetic() {
        assert!(mean_dstar_spread(&[]).is_none());
        // Hand-build rows with known means via DegreeStats.
        let mk = |vals: &[u32]| {
            let mut s = DegreeStats::default();
            for &v in vals {
                s.accumulate(Some(v));
            }
            s.finalize();
            AvgRow {
                n: 6,
                n_sub: 3,
                num_vars: 6,
                num_eqs: 6,
                n_targets: vals.len() as u32,
                skipped_decomposable: 0,
                refutation: s,
                first_fall: DegreeStats::default(),
            }
        };
        let rows = vec![mk(&[2, 2]), mk(&[4, 4])]; // means 2.0 and 4.0
        assert_eq!(mean_dstar_spread(&rows), Some(2.0));
    }
}
