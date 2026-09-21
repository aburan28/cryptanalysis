//! # Algebraic discriminator for `D*` — Hilbert-function / rank-profile defect.
//!
//! Workflow iterations 3–4 refuted every *incidence-graph* predictor of the
//! refutation degree `D*` (spectral expansion varies the wrong way;
//! treewidth is constant because the descended primal graph is the complete
//! graph). The lesson: the structure that makes a *subfield* factor base
//! easier (lower `D*`) lives in the **algebra of the coefficients**, not in
//! the variable-incidence graph. This module looks where the structure
//! actually is.
//!
//! ## The invariant
//!
//! For the `V`-substituted descended system `Σ`, build the Macaulay matrix
//! at each degree `D` and compare its rank `r(D)` to the **generic**
//! (semi-regular) prediction `r_gen(D)` for a system of the same shape
//! (`#eqs` quadratics in `#vars` Boolean variables). The **rank defect**
//!
//! ```text
//!   δ(D) = r_gen(D) − r(D)   ≥ 0
//! ```
//!
//! counts the **excess low-degree syzygies** the ideal carries beyond a
//! generic system — i.e. how far the Hilbert function falls below the
//! generic Hilbert series at degree `D`. A multiplicatively-closed factor
//! base (a subfield) injects many such relations early, so the hypothesis
//! (**prediction P3-alg**) is:
//!
//! > the structured / easy (low-`D*`) systems carry a **larger early rank
//! > defect** `δ(D)` at small `D` than generic/random systems — and that
//! > early defect is what predicts the lower `D*`.
//!
//! Unlike spectral γ and treewidth, `δ(D)` is computed from the *actual
//! coefficients* of the substituted system (via the same bit-packed
//! Macaulay rank the rest of the program uses), so it can see algebraic
//! structure a graph invariant cannot.
//!
//! ## What we expose
//!
//! - [`rank_profile`] — `(D, rows, cols, rank, generic_rank, defect)` per
//!   degree for an arbitrary `F_2`-quadratic system.
//! - [`early_defect`] — the cumulative defect `Σ_{D≤d} δ(D)` up to a cutoff,
//!   the scalar summary used for correlation against `D*`.
//!
//! ## References
//!
//! - Bardet–Faugère–Salvy, *complexity of Gröbner bases of semi-regular
//!   systems* (the generic Hilbert-series baseline `r_gen`).
//! - `research/notes/index-calculus/RESEARCH_FFD_WORKFLOW.md` iterations 3–4 (the graph-invariant
//!   refutations that motivate going algebraic).

use crate::cryptanalysis::ffd_harness::{
    build_macaulay_rows, f2_rank, generic_rank_prediction, num_monomials_upto_degree, F2BoolPoly,
};

/// One degree-`D` row of the Macaulay rank profile.
#[derive(Clone, Debug)]
pub struct RankRow {
    pub degree: u32,
    pub rows: u64,
    pub cols: u64,
    pub rank: u64,
    /// Generic (semi-regular) rank prediction for a system of the same shape.
    pub generic_rank: u64,
    /// `generic_rank − rank`, clamped at 0: the excess low-degree syzygies
    /// (how far below generic the Hilbert function sits at this degree).
    pub defect: u64,
}

/// Macaulay rank profile of an `F_2`-quadratic system `eqs` in `num_vars`
/// Boolean variables, over degrees `2..=d_max`. The `defect` column is the
/// algebraic discriminator.
pub fn rank_profile(eqs: &[F2BoolPoly], num_vars: u32, num_eqs: u32, d_max: u32) -> Vec<RankRow> {
    let mut out = Vec::new();
    for d in 2..=d_max {
        let (rows, cols, rows_constructed) = build_macaulay_rows(eqs, num_vars, d);
        let cols_u64 = cols as u64;
        let rank = if rows.is_empty() {
            0
        } else {
            let mut for_rank = rows;
            f2_rank(&mut for_rank, cols) as u64
        };
        let generic_rank = generic_rank_prediction(num_eqs as u64, num_vars, d, cols_u64);
        let defect = generic_rank.saturating_sub(rank);
        out.push(RankRow {
            degree: d,
            rows: rows_constructed,
            cols: cols_u64,
            rank,
            generic_rank,
            defect,
        });
    }
    out
}

/// Cumulative rank defect over degrees `≤ cutoff`: `Σ_{D≤cutoff} δ(D)`.
/// The scalar "how non-generic at low degree" summary correlated against
/// `D*`. Normalized by the column count at `cutoff` so it is comparable
/// across systems of slightly different size.
pub fn early_defect(profile: &[RankRow], cutoff: u32) -> f64 {
    let mut sum = 0.0;
    let mut norm = 1.0;
    for r in profile {
        if r.degree <= cutoff {
            sum += r.defect as f64;
            norm = r.cols.max(1) as f64; // last (largest) col count ≤ cutoff
        }
    }
    sum / norm
}

/// Total (un-normalized) rank defect over the whole profile.
pub fn total_defect(profile: &[RankRow]) -> u64 {
    profile.iter().map(|r| r.defect).sum()
}

/// Raw normalized-defect / cols helper for a single degree (diagnostic).
pub fn defect_fraction_at(profile: &[RankRow], degree: u32) -> Option<f64> {
    profile
        .iter()
        .find(|r| r.degree == degree)
        .map(|r| r.defect as f64 / r.cols.max(1) as f64)
}

/// Sanity: number of degree-≤`d` monomials, re-exported for callers wiring
/// the profile into a sweep (keeps the dependency surface in one place).
pub fn monomials_upto(v: u32, d: u32) -> u64 {
    num_monomials_upto_degree(v, d)
}

// ── Tests ───────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::binary_ecc::F2mElement;
    use crate::cryptanalysis::descent_expansion::enumerate_irreducibles;
    use crate::cryptanalysis::descent_lowgamma::{
        descend_on_subspace, BasisFamily, FactorSubspace,
    };

    /// The defect is non-negative and the profile spans the requested
    /// degrees.
    #[test]
    fn profile_shape_and_nonneg_defect() {
        let n = 6;
        let n_sub = 3;
        let irr = enumerate_irreducibles(n, 1).into_iter().next().unwrap();
        let v = FactorSubspace::build(BasisFamily::Coordinate, n, n_sub, &irr, 0).unwrap();
        let b = F2mElement::from_bit_positions(&[0, 2], n);
        let x3 = F2mElement::from_bit_positions(&[1], n);
        let eqs = descend_on_subspace(n, &v, &irr, &b, &x3);
        let nv = 2 * n_sub;
        let prof = rank_profile(&eqs, nv, n, 2 * n_sub + 1);
        assert_eq!(prof.first().unwrap().degree, 2);
        for r in &prof {
            assert!(r.rank <= r.cols);
            // defect = max(0, generic - rank); always ≥ 0 by construction.
            assert_eq!(r.defect, r.generic_rank.saturating_sub(r.rank));
        }
    }

    /// `early_defect` and `total_defect` agree with hand computation on a
    /// tiny synthetic profile.
    #[test]
    fn defect_aggregation() {
        let prof = vec![
            RankRow {
                degree: 2,
                rows: 6,
                cols: 20,
                rank: 6,
                generic_rank: 6,
                defect: 0,
            },
            RankRow {
                degree: 3,
                rows: 60,
                cols: 56,
                rank: 50,
                generic_rank: 55,
                defect: 5,
            },
            RankRow {
                degree: 4,
                rows: 200,
                cols: 120,
                rank: 118,
                generic_rank: 120,
                defect: 2,
            },
        ];
        assert_eq!(total_defect(&prof), 7);
        // early_defect(cutoff=3) = (0+5)/cols_at_deg_3 = 5/56.
        let e = early_defect(&prof, 3);
        assert!((e - 5.0 / 56.0).abs() < 1e-12, "got {e}");
    }

    /// **The algebraic discriminator, first measurement (prediction P3-alg).**
    /// At the operating point `2n'=n`, the subfield factor base — which has
    /// the lowest `D*` — should carry a **larger** early rank defect than a
    /// random factor base, because its multiplicative closure injects extra
    /// low-degree syzygies. This is the test that the *coefficient* algebra,
    /// not the incidence graph, is where `D*` is decided. Averaged over a
    /// few targets for stability.
    #[test]
    fn subfield_has_larger_early_defect_than_random() {
        let n = 8;
        let n_sub = 4; // 2n' = n; F_16 subfield exists (4 | 8)
        let irr = enumerate_irreducibles(n, 1).into_iter().next().unwrap();
        let cutoff = 3;
        let d_max = 2 * n_sub; // enough to see the early profile

        let mean_early = |fam: BasisFamily, seed_off: u64| -> f64 {
            let mut acc = 0.0;
            let mut cnt = 0.0;
            for t in 0..6u64 {
                let v = match fam {
                    BasisFamily::Random => {
                        FactorSubspace::build(fam, n, n_sub, &irr, 0x500 + seed_off + t)
                    }
                    _ => FactorSubspace::build(fam, n, n_sub, &irr, 0),
                }
                .unwrap();
                // Deterministic-ish (b, x3) from t.
                let b = F2mElement::from_bit_positions(
                    &(0..n)
                        .filter(|k| ((t.wrapping_mul(2654435761) >> k) & 1) == 1)
                        .collect::<Vec<_>>(),
                    n,
                );
                let x3 = F2mElement::from_bit_positions(
                    &(0..n)
                        .filter(|k| (((t.wrapping_mul(40503) + 7) >> k) & 1) == 1)
                        .collect::<Vec<_>>(),
                    n,
                );
                if b.is_zero() || x3.is_zero() {
                    continue;
                }
                let eqs = descend_on_subspace(n, &v, &irr, &b, &x3);
                let prof = rank_profile(&eqs, 2 * n_sub, n, d_max);
                acc += early_defect(&prof, cutoff);
                cnt += 1.0;
            }
            if cnt > 0.0 {
                acc / cnt
            } else {
                0.0
            }
        };

        let sub = mean_early(BasisFamily::Subfield, 0);
        let rnd = mean_early(BasisFamily::Random, 0);
        // The discriminating claim: the easy (low-D*) subfield carries a
        // STRICTLY larger early rank defect than the hard random factor base
        // — the algebraic structure (multiplicative closure) shows up as
        // excess low-degree syzygies. This is the positive signal that the
        // *coefficient* algebra, unlike spectral γ / treewidth, predicts D*.
        assert!(
            sub > rnd,
            "subfield early defect {sub:.5} should EXCEED random {rnd:.5} (algebraic structure at low degree)"
        );
    }
}
