//! # Buying down the Gröbner solving degree `D*` — lever L3 (hybrid slicing).
//!
//! The FFD program (`research/notes/index-calculus/RESEARCH_FFD_PROOF_COMPLEXITY.md`,
//! `research/notes/index-calculus/RESEARCH_FFD_WORKFLOW.md`) measures `D*`, the degree at which the
//! Macaulay/Gröbner computation on a Weil-descended Semaev system
//! terminates, and establishes two facts we now use *offensively*:
//!
//! - **P6** — over-determination collapses `D*`: at determination ratio
//!   `ρ = #eqs/#vars ≫ 1` the system admits a degree-2 Nullstellensatz
//!   certificate, so `D* = 2`.
//! - **P3-alg** — `D*` decreases with the early Hilbert-function defect
//!   `Δ_low` (slope ≈ −7.6 degrees per unit defect in the critical regime).
//!
//! P6 was recorded as a *nuisance* — the reason the early single-sample
//! harness saw a spuriously flat `D*`. But `ρ` is not fixed by the problem:
//! an attacker can **raise it at will** by guessing `k` of the `N = 2n'`
//! Boolean variables and solving the `2^k` resulting slices. That is the
//! Bettale–Faugère–Perret *hybrid approach*, and this module makes it
//! measurable on descended Semaev systems.
//!
//! ## Why the accounting is exact here
//!
//! Fix a target `x₃` that is **non-decomposable** over the factor base `V`
//! (the common case in index calculus — most relation attempts fail). The
//! descended system `Σ` is then unsatisfiable, and so is *every* one of the
//! `2^k` slices obtained by fixing `k` variables. Hence:
//!
//! - every slice refutes, so `D*` is defined on all of them (no censoring
//!   from "this slice happened to be satisfiable");
//! - the slices **partition** the search space, so the hybrid is not an
//!   approximation — it covers exactly what the direct solve covered;
//! - total work is `Σ_slices cost(D*_slice)`, which sampling estimates as
//!   `2^k · E[cost(D*_slice)]`.
//!
//! So the trade is clean: `2^k` multiplicative slices bought against a
//! (hopefully) collapsing `D*` in each. This module measures both halves
//! and reports the crossover.
//!
//! ## What we expose
//!
//! - [`specialize`] — substitute constants for a chosen set of Boolean
//!   variables and re-index the survivors (an exact affine slice of `Σ`).
//! - [`GuessPattern`] — *which* variables to fix. `OneSide` (all from the
//!   `X₁` half) is index calculus's asymmetric factor-base split;
//!   `Balanced` splits evenly; `Spread` picks uniformly at random.
//! - [`HybridRow`] / [`run_hybrid_sweep`] — the `D*`-vs-`k` curve with a
//!   histogram-exact cost model, so the linear-algebra exponent `ω` can be
//!   varied after the fact ([`HybridRow::log2_total_cost`]).
//!
//! ## Reading the output — and the baseline that actually matters
//!
//! `log2_total_cost(ω) = k + log₂ E[cols(N−k, D*)^ω]` is the log₂ work of
//! the whole hybrid at that `k`; `k = 0` is the direct solve.
//!
//! Beating `k = 0` is **not** the bar. The `k = N` endpoint of this same
//! family is brute-force enumeration of `V × V`, so at toy sizes the cost
//! model will happily report that "guessing more always helps" — it is
//! drifting toward exhaustive search, which is genuinely fastest when
//! `2^N` is small. Any gate keyed only on the `k = 0` comparison measures
//! that artifact and nothing else.
//!
//! So the honest comparison is against [`log2_enumeration_cost`] (`2^N`
//! Semaev evaluations, charged generously at `O(1)` amortised each), and
//! the scaling quantity is [`HybridSweep::collapse_fraction`] — the
//! fraction `c = k/N` at which `D*` reaches the Nullstellensatz floor of 2.
//! Total hybrid work is `2^{cN}·poly`, so the lever is a real speedup only
//! if `c < 1`, and survives to cryptographic size only if `c` does not
//! drift upward with `N`.
//!
//! ## References
//!
//! - L. Bettale, J.-C. Faugère, L. Perret, *Hybrid approach for solving
//!   multivariate systems over finite fields*, J. Math. Cryptol. 2009.
//! - Bardet–Faugère–Salvy, semi-regular complexity (the `cols^ω` model).
//! - `research/notes/index-calculus/RESEARCH_DEGREE_REDUCTION.md` (this thread's charter, ledger R1–R5).

use std::collections::BTreeMap;

use crate::binary_ecc::{F2mElement, IrreduciblePoly};
use crate::cryptanalysis::descent_algebraic::{early_defect, rank_profile, RankRow};
use crate::cryptanalysis::descent_expansion::spearman;
use crate::cryptanalysis::descent_lowgamma::{
    descend_on_subspace, is_decomposable_on_subspace, BasisFamily, FactorSubspace,
};
use crate::cryptanalysis::ffd_harness::{
    monomial_index, num_monomials_upto_degree, quad_monomial_index, F2BoolPoly,
};
use crate::cryptanalysis::pc_degree_harness::refutation_scan;

// ── Affine slicing ──────────────────────────────────────────────────

/// Substitute constants for some Boolean variables and re-index the rest.
///
/// `assign[i] = Some(v)` fixes `x_i := v`; `assign[i] = None` keeps `x_i` as
/// a free variable. The surviving variables are re-indexed in increasing
/// order of their original index, so the result is a system in
/// `num_vars − (#fixed)` variables.
///
/// This is an exact substitution in the Boolean ring `F_2[x]/⟨x_i²−x_i⟩`:
/// a quadratic monomial with one fixed factor becomes linear, one with both
/// fixed becomes a constant. The slices over all `2^k` assignments of a
/// fixed variable set **partition** the solution space of the original
/// system.
pub fn specialize(
    eqs: &[F2BoolPoly],
    num_vars: u32,
    assign: &[Option<bool>],
) -> (Vec<F2BoolPoly>, u32) {
    assert_eq!(
        assign.len(),
        num_vars as usize,
        "assign covers every variable"
    );

    // old index → Some(new index) for survivors, None for fixed.
    let mut remap = vec![None; num_vars as usize];
    let mut new_vars = 0u32;
    for (i, a) in assign.iter().enumerate() {
        if a.is_none() {
            remap[i] = Some(new_vars);
            new_vars += 1;
        }
    }

    let out = eqs
        .iter()
        .map(|eq| {
            let mut f = F2BoolPoly::zero(new_vars);
            if eq.coeffs[0] {
                f.coeffs[0] ^= true;
            }
            // Linear monomials.
            for i in 0..num_vars as usize {
                if !eq.coeffs.get(1 + i).copied().unwrap_or(false) {
                    continue;
                }
                match assign[i] {
                    Some(true) => f.coeffs[0] ^= true,
                    Some(false) => {}
                    None => f.coeffs[1 + remap[i].unwrap() as usize] ^= true,
                }
            }
            // Quadratic monomials x_i·x_j (i < j).
            for i in 0..num_vars {
                for j in (i + 1)..num_vars {
                    let idx = quad_monomial_index(i, j, num_vars);
                    if idx >= eq.coeffs.len() || !eq.coeffs[idx] {
                        continue;
                    }
                    let (ai, aj) = (assign[i as usize], assign[j as usize]);
                    match (ai, aj) {
                        // Both fixed → constant.
                        (Some(vi), Some(vj)) => {
                            if vi && vj {
                                f.coeffs[0] ^= true;
                            }
                        }
                        // One fixed → linear in the survivor (or vanishes).
                        (Some(vi), None) => {
                            if vi {
                                f.coeffs[1 + remap[j as usize].unwrap() as usize] ^= true;
                            }
                        }
                        (None, Some(vj)) => {
                            if vj {
                                f.coeffs[1 + remap[i as usize].unwrap() as usize] ^= true;
                            }
                        }
                        // Both survive → quadratic, re-indexed.
                        (None, None) => {
                            let (a, b) = (remap[i as usize].unwrap(), remap[j as usize].unwrap());
                            f.coeffs[quad_monomial_index(a, b, new_vars)] ^= true;
                        }
                    }
                }
            }
            f
        })
        .collect();

    (out, new_vars)
}

// ── Which variables to guess ────────────────────────────────────────

/// Where in the `[X₁ bits ‖ X₂ bits]` layout the guessed variables come
/// from. The choice is not cosmetic: `OneSide` is the index-calculus
/// *asymmetric factor-base split* (shrink `V` for one summand only), while
/// `Balanced` shrinks both summands symmetrically.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum GuessPattern {
    /// All guessed variables taken from the `X₁` half (low indices first).
    OneSide,
    /// Alternate `X₁`, `X₂`, `X₁`, … so both halves shrink together.
    Balanced,
    /// A uniformly random `k`-subset of all `N` variables.
    Spread,
}

impl GuessPattern {
    pub fn label(&self) -> &'static str {
        match self {
            GuessPattern::OneSide => "one-side",
            GuessPattern::Balanced => "balanced",
            GuessPattern::Spread => "spread",
        }
    }

    /// Pick the `k` variable indices to fix, out of `num_vars` laid out as
    /// `[X₁ bits 0..h ‖ X₂ bits 0..h]` with `h = num_vars/2`.
    fn pick(&self, num_vars: u32, k: u32, rng: &mut dyn FnMut() -> u64) -> Vec<u32> {
        let half = num_vars / 2;
        match self {
            GuessPattern::OneSide => (0..k.min(num_vars)).collect(),
            GuessPattern::Balanced => (0..k.min(num_vars))
                .map(|t| {
                    let side = t % 2;
                    let off = t / 2;
                    if side == 0 {
                        off
                    } else {
                        half + off
                    }
                })
                .filter(|v| *v < num_vars)
                .collect(),
            GuessPattern::Spread => {
                // Partial Fisher–Yates over 0..num_vars.
                let mut pool: Vec<u32> = (0..num_vars).collect();
                for t in 0..k.min(num_vars) as usize {
                    let j = t + (rng() as usize) % (pool.len() - t);
                    pool.swap(t, j);
                }
                let mut v: Vec<u32> = pool[..k.min(num_vars) as usize].to_vec();
                v.sort_unstable();
                v
            }
        }
    }
}

// ── One row of the D*-vs-k curve ────────────────────────────────────

/// Aggregated measurement at one guess count `k`.
#[derive(Clone, Debug)]
pub struct HybridRow {
    /// Number of Boolean variables fixed per slice.
    pub k: u32,
    /// Free variables left in each slice, `N − k`.
    pub vars: u32,
    /// Equations (unchanged by slicing) — the descent gives `n` of them.
    pub eqs: u32,
    /// Determination ratio `#eqs / #vars` of a slice.
    pub rho: f64,
    /// Slices actually measured (targets × slices-per-target).
    pub slices: u32,
    /// Slices that did not refute within `d_max` (censored; excluded from
    /// the statistics below, and a warning sign if nonzero).
    pub censored: u32,
    /// Mean `D*` over the measured slices.
    pub dstar_mean: f64,
    /// Worst `D*` seen — the degree the attacker must actually budget for.
    pub dstar_max: u32,
    /// `D*` histogram (degree → count).
    pub dstar_hist: BTreeMap<u32, u32>,
    /// Mean early Hilbert defect `Δ_low` of a slice (cutoff 3).
    pub delta_low_mean: f64,
    /// Mean operational first-fall degree `d_ff` of a slice.
    pub first_fall_mean: f64,
}

impl HybridRow {
    /// log₂ of the total hybrid work at linear-algebra exponent `ω`:
    ///
    /// ```text
    ///   log2_total = k + log₂ E[ cols(N−k, D*)^ω ]
    /// ```
    ///
    /// computed **exactly** from the `D*` histogram (not from the mean
    /// degree, which would understate the cost by Jensen). `k = 0` is the
    /// direct solve, so a lever pays iff some `k > 0` comes in lower.
    pub fn log2_total_cost(&self, omega: f64) -> f64 {
        let total: u32 = self.dstar_hist.values().sum();
        if total == 0 {
            return f64::NAN;
        }
        let mut expected = 0.0f64;
        for (&d, &count) in &self.dstar_hist {
            let cols = num_monomials_upto_degree(self.vars, d) as f64;
            expected += (count as f64 / total as f64) * cols.powf(omega);
        }
        self.k as f64 + expected.log2()
    }

    /// log₂ of the work in a *single* slice at exponent `ω` (i.e. without
    /// the `2^k` enumeration factor) — the quantity the degree collapse
    /// actually reduces.
    pub fn log2_slice_cost(&self, omega: f64) -> f64 {
        self.log2_total_cost(omega) - self.k as f64
    }
}

/// The full sweep for one `(family, n, n', pattern)` cell.
#[derive(Clone, Debug)]
pub struct HybridSweep {
    pub family: BasisFamily,
    pub pattern: GuessPattern,
    pub n: u32,
    pub n_sub: u32,
    /// `N = 2n'`, the descended variable count before slicing.
    pub full_vars: u32,
    pub targets: u32,
    pub d_max: u32,
    pub rows: Vec<HybridRow>,
}

impl HybridSweep {
    /// log₂ cost of brute-force enumeration of `V × V` at this operating
    /// point — see [`log2_enumeration_cost`]. The baseline any hybrid must
    /// beat to count as a speedup.
    pub fn log2_enumeration(&self) -> f64 {
        log2_enumeration_cost(self.full_vars, self.n)
    }

    /// log₂ margin of the best hybrid over **brute-force enumeration** at
    /// exponent `ω`. Positive means the hybrid genuinely beats the search it
    /// replaces; negative means it does not, and gives the size of the
    /// shortfall in bits.
    pub fn margin_vs_enumeration(&self, omega: f64) -> Option<f64> {
        let best = self
            .rows
            .iter()
            .map(|r| r.log2_total_cost(omega))
            .filter(|c| c.is_finite())
            .fold(f64::INFINITY, f64::min);
        if best.is_finite() {
            Some(self.log2_enumeration() - best)
        } else {
            None
        }
    }

    /// The smallest `k` at which **every sampled slice** has collapsed to the
    /// Nullstellensatz floor `D* = 2`, as a fraction of `N`.
    ///
    /// This is the lever's true scaling quantity. Total hybrid work is
    /// `2^k · poly`, so the hybrid beats `2^N` enumeration only if the
    /// collapse arrives at `k = cN` with `c < 1` — and the *trend* of `c`
    /// with `N` decides whether the lever survives to cryptographic size.
    pub fn collapse_fraction(&self) -> Option<f64> {
        // If the unsliced system is already at the floor there is no degree
        // to reduce, so `c = 0` would be a degenerate reading, not a
        // measurement. Report `None` and let the caller exclude the cell.
        if self.rows.first().map(|r| r.dstar_max <= 2).unwrap_or(false) {
            return None;
        }
        self.rows
            .iter()
            .find(|r| r.censored == 0 && r.dstar_max <= 2)
            .map(|r| r.k as f64 / self.full_vars as f64)
    }

    /// Largest `k` scanned.
    pub fn k_max(&self) -> u32 {
        self.rows.last().map(|r| r.k).unwrap_or(0)
    }

    /// Does the cost curve have an **interior** minimum at exponent `ω`?
    ///
    /// This is the sweep's own honesty check. The `k = N` endpoint of the
    /// hybrid family is exhaustive search, so a cost model evaluated on toy
    /// systems will happily slide the optimum all the way to the largest `k`
    /// available — reporting "guessing always helps" when what it has really
    /// found is that `2^N` is small. If `k* == k_max` the sweep has **not**
    /// located an optimum; it has run off the end of the scan, and any
    /// "saving" it reports is an artifact of where the scan was truncated.
    pub fn optimum_is_interior(&self, omega: f64) -> bool {
        self.best(omega)
            .map(|(k, _)| k < self.k_max())
            .unwrap_or(false)
    }

    /// The `k` minimising total work at exponent `ω`, and its log₂ saving
    /// against the direct solve (`k = 0`). A positive saving means the
    /// hybrid lever pays.
    pub fn best(&self, omega: f64) -> Option<(u32, f64)> {
        let base = self.rows.iter().find(|r| r.k == 0)?.log2_total_cost(omega);
        let best = self
            .rows
            .iter()
            .filter(|r| r.log2_total_cost(omega).is_finite())
            .min_by(|a, b| {
                a.log2_total_cost(omega)
                    .partial_cmp(&b.log2_total_cost(omega))
                    .unwrap()
            })?;
        Some((best.k, base - best.log2_total_cost(omega)))
    }
}

/// log₂ cost of the **brute-force baseline**: enumerate all `2^N` points of
/// `V × V` and evaluate the descended system at each.
///
/// The model is deliberately *generous to brute force* — it charges only
/// `eqs` bit-operations per point, i.e. it assumes Gray-code enumeration
/// amortises the monomial updates to `O(1)` each, and it ignores constant
/// factors entirely. That is the honest way to run the comparison: a lever
/// that only wins against a strawman baseline has not won.
///
/// This baseline matters because it bounds the whole hybrid family. The
/// `k = N` endpoint of hybrid slicing *is* enumeration, so a hybrid that
/// cannot beat `2^N` has bought its degree reduction at full price and is
/// not a speedup over the search it replaced.
pub fn log2_enumeration_cost(full_vars: u32, eqs: u32) -> f64 {
    full_vars as f64 + (eqs.max(1) as f64).log2()
}

/// Run the `D*`-vs-`k` sweep.
///
/// For each of `targets` **non-decomposable** targets `x₃` over the factor
/// base `V` (so the slices are genuinely unsatisfiable and every one
/// refutes), and each `k ∈ 0..=k_max`, sample `slices_per_k` random
/// assignments of the `k` chosen variables and measure the slice's `D*`,
/// `d_ff` and `Δ_low`.
///
/// `k = 0` is measured once per target (there is only one slice).
/// Returns `None` if the subspace family is infeasible at `(n, n')`.
#[allow(clippy::too_many_arguments)]
pub fn run_hybrid_sweep(
    family: BasisFamily,
    pattern: GuessPattern,
    n: u32,
    n_sub: u32,
    irr: &IrreduciblePoly,
    k_max: u32,
    targets: u32,
    slices_per_k: u32,
    d_max: u32,
    seed: u64,
) -> Option<HybridSweep> {
    let full_vars = 2 * n_sub;
    let k_max = k_max.min(full_vars.saturating_sub(2));

    // Two INDEPENDENT streams. `next_target` draws the curve/target pairs;
    // `next_slice` draws the guessed variable sets and their values. Keeping
    // them separate is load-bearing: `GuessPattern::Spread` consumes randomness
    // that `OneSide`/`Balanced` do not, so a single stream would hand each
    // pattern a *different* set of targets and make the pattern comparison
    // meaningless. With the split, every pattern sees the same targets and the
    // `k = 0` row is pattern-independent (asserted in tests).
    let mut t_state = seed | 1;
    let mut next_target = move || {
        t_state ^= t_state >> 12;
        t_state ^= t_state << 25;
        t_state ^= t_state >> 27;
        t_state.wrapping_mul(0x2545F4914F6CDD1D)
    };
    let mut s_state = seed.rotate_left(32) | 1;
    let mut next_slice = move || {
        s_state ^= s_state >> 12;
        s_state ^= s_state << 25;
        s_state ^= s_state >> 27;
        s_state.wrapping_mul(0x2545F4914F6CDD1D)
    };

    // Accumulators, one bucket per k.
    struct Acc {
        slices: u32,
        censored: u32,
        dstar_sum: f64,
        dstar_max: u32,
        hist: BTreeMap<u32, u32>,
        delta_sum: f64,
        ff_sum: f64,
        ff_count: u32,
    }
    let mut acc: Vec<Acc> = (0..=k_max)
        .map(|_| Acc {
            slices: 0,
            censored: 0,
            dstar_sum: 0.0,
            dstar_max: 0,
            hist: BTreeMap::new(),
            delta_sum: 0.0,
            ff_sum: 0.0,
            ff_count: 0,
        })
        .collect();

    let rand_nz = |m: u32, rng: &mut dyn FnMut() -> u64| loop {
        let bits: Vec<u32> = (0..m).filter(|_| (rng() >> 19) & 1 == 1).collect();
        let e = F2mElement::from_bit_positions(&bits, m);
        if !e.is_zero() {
            return e;
        }
    };

    let mut found = 0u32;
    // Bounded search for non-decomposable targets: each draw is roughly a
    // coin flip at the critical operating point, so this terminates fast.
    let mut attempts = 0u32;
    while found < targets && attempts < targets * 64 + 256 {
        attempts += 1;
        let v = match family {
            BasisFamily::Random => {
                FactorSubspace::build(family, n, n_sub, irr, seed ^ (0x9E37 + attempts as u64))?
            }
            _ => FactorSubspace::build(family, n, n_sub, irr, 0)?,
        };
        let b = rand_nz(n, &mut next_target);
        let x3 = rand_nz(n, &mut next_target);
        if is_decomposable_on_subspace(&v, irr, &b, &x3) {
            continue;
        }
        found += 1;

        let eqs = descend_on_subspace(n, &v, irr, &b, &x3);

        for k in 0..=k_max {
            let reps = if k == 0 { 1 } else { slices_per_k };
            for _ in 0..reps {
                let idx = pattern.pick(full_vars, k, &mut next_slice);
                let mut assign: Vec<Option<bool>> = vec![None; full_vars as usize];
                for &i in &idx {
                    assign[i as usize] = Some((next_slice() >> 23) & 1 == 1);
                }
                let (seqs, nv) = specialize(&eqs, full_vars, &assign);
                let a = &mut acc[k as usize];
                a.slices += 1;

                let (ff, dstar, _) = refutation_scan(&seqs, nv, d_max);
                if let Some(f) = ff {
                    a.ff_sum += f as f64;
                    a.ff_count += 1;
                }
                match dstar {
                    Some(d) => {
                        a.dstar_sum += d as f64;
                        a.dstar_max = a.dstar_max.max(d);
                        *a.hist.entry(d).or_insert(0) += 1;
                    }
                    None => a.censored += 1,
                }

                let profile = rank_profile(&seqs, nv, n, 3.min(d_max));
                a.delta_sum += early_defect(&profile, 3);
            }
        }
    }

    if found == 0 {
        return None;
    }

    let rows = (0..=k_max)
        .map(|k| {
            let a = &acc[k as usize];
            let measured = a.slices - a.censored;
            let vars = full_vars - k;
            HybridRow {
                k,
                vars,
                eqs: n,
                rho: n as f64 / vars.max(1) as f64,
                slices: a.slices,
                censored: a.censored,
                dstar_mean: if measured > 0 {
                    a.dstar_sum / measured as f64
                } else {
                    f64::NAN
                },
                dstar_max: a.dstar_max,
                dstar_hist: a.hist.clone(),
                delta_low_mean: if a.slices > 0 {
                    a.delta_sum / a.slices as f64
                } else {
                    f64::NAN
                },
                first_fall_mean: if a.ff_count > 0 {
                    a.ff_sum / a.ff_count as f64
                } else {
                    f64::NAN
                },
            }
        })
        .collect();

    Some(HybridSweep {
        family,
        pattern,
        n,
        n_sub,
        full_vars,
        targets: found,
        d_max,
        rows,
    })
}

// ── Lever L4: degree falls (mutants) ────────────────────────────────
//
// A *syzygy* and a *degree fall* are not the same thing, and the
// distinction decides whether this lever exists at all.
//
// EXP-J (`examples/ffd_syzygy.rs`) found that the descended Semaev system
// carries exactly one excess relation at degree 3, of the form
// `Σ_i ℓ_i · f_i ≡ 0`. That is a **pure syzygy**: the combination vanishes
// identically, so it yields no polynomial. Adding it to the generating set
// adds literally nothing; it only costs the solver one zero reduction,
// which is a constant factor (what F5's criterion avoids), not a degree.
//
// A **degree fall** is the other case: a combination of degree-`D` rows
// whose degree-`D` part cancels but whose remainder is **nonzero**, hence a
// new element of the ideal of degree `≤ D−1`. That *is* worth adding, and
// the reason is not that the solver cannot find it — at degree `D` it
// already has it in its row space — but that once `g` is a generator, the
// rows `x_k · g` become available at degree `D`, and those are degree-`D+1`
// products of the original generators. The Macaulay tower genuinely
// accelerates. This is the mutant mechanism of MutantXL / the degree-fall
// strategy used against HFE.
//
// So `extract_degree_falls` separates the two populations and returns only
// the falls, and only those independent of the generators already present.

/// What the degree-3 top-part cancellation space contains.
#[derive(Clone, Debug)]
pub struct DegreeFallReport {
    /// Macaulay degree scanned (3 — the first degree where a fall can occur
    /// for a quadratic system).
    pub degree: u32,
    /// Degree-`D` rows considered: the products `x_k · f_i`.
    pub rows: usize,
    /// Dimension of the space of combinations whose top-degree part cancels.
    pub cancel_dim: usize,
    /// Cancellations whose remainder is *also* zero — pure syzygies, which
    /// yield nothing. EXP-J's relation lands here.
    pub pure_syzygies: usize,
    /// Cancellations with a nonzero remainder: genuine degree falls.
    pub falls: usize,
    /// The falls that are linearly independent of the original generators —
    /// the only ones worth adding, since a fall already in `span{f_i}` is a
    /// generator the solver has.
    pub new_generators: Vec<F2BoolPoly>,
}

/// Multiply the monomial set of a degree-≤2 Boolean polynomial by `x_k`
/// (multilinearly, `x_k² = x_k`) and XOR-accumulate into a bitset over the
/// degree-≤3 monomial space.
fn cubic_row_bits(f: &F2BoolPoly, num_vars: u32, k: u32, words: usize) -> Vec<u64> {
    let mut acc = vec![0u64; words];
    let push = |mono: &[u32], acc: &mut Vec<u64>| {
        let idx = monomial_index(mono, num_vars, 3);
        acc[idx / 64] ^= 1u64 << (idx % 64);
    };
    let with_k = |mono: &mut Vec<u32>| {
        if let Err(pos) = mono.binary_search(&k) {
            mono.insert(pos, k);
        }
    };
    if f.coeffs[0] {
        let mut m = vec![];
        with_k(&mut m);
        push(&m, &mut acc);
    }
    for i in 0..num_vars {
        if f.coeffs[1 + i as usize] {
            let mut m = vec![i];
            with_k(&mut m);
            push(&m, &mut acc);
        }
    }
    for i in 0..num_vars {
        for j in (i + 1)..num_vars {
            let idx = quad_monomial_index(i, j, num_vars);
            if idx < f.coeffs.len() && f.coeffs[idx] {
                let mut m = vec![i, j];
                with_k(&mut m);
                if m.len() <= 3 {
                    push(&m, &mut acc);
                }
            }
        }
    }
    acc
}

/// Mask a degree-≤3 bitset down to its **cubic** monomials only.
fn cubic_part_only(bits: &[u64], num_vars: u32, words: usize) -> Vec<u64> {
    let low = num_monomials_upto_degree(num_vars, 2) as usize;
    let mut out = vec![0u64; words];
    for idx in low..(num_monomials_upto_degree(num_vars, 3) as usize) {
        if (bits[idx / 64] >> (idx % 64)) & 1 == 1 {
            out[idx / 64] |= 1u64 << (idx % 64);
        }
    }
    out
}

/// Convert a degree-≤3 bitset known to have no cubic monomials back into a
/// [`F2BoolPoly`].
fn bits_to_poly(bits: &[u64], num_vars: u32) -> F2BoolPoly {
    let mut f = F2BoolPoly::zero(num_vars);
    if (bits[0] >> monomial_index(&[], num_vars, 3)) & 1 == 1 {
        f.coeffs[0] ^= true;
    }
    for i in 0..num_vars {
        let idx = monomial_index(&[i], num_vars, 3);
        if (bits[idx / 64] >> (idx % 64)) & 1 == 1 {
            f.coeffs[1 + i as usize] ^= true;
        }
    }
    for i in 0..num_vars {
        for j in (i + 1)..num_vars {
            let idx = monomial_index(&[i, j], num_vars, 3);
            if (bits[idx / 64] >> (idx % 64)) & 1 == 1 {
                f.coeffs[quad_monomial_index(i, j, num_vars)] ^= true;
            }
        }
    }
    f
}

fn lead_bit(v: &[u64]) -> Option<usize> {
    v.iter()
        .enumerate()
        .find(|(_, w)| **w != 0)
        .map(|(i, w)| i * 64 + w.trailing_zeros() as usize)
}

/// Extract the degree-3 falls of a quadratic Boolean system.
///
/// Builds the rows `x_k · f_i`, finds every combination whose **cubic part**
/// cancels (Gaussian elimination with provenance over the cubic monomials
/// only), then evaluates each such combination in full. A zero result is a
/// pure syzygy; a nonzero one is a degree fall of degree ≤ 2. Falls that lie
/// in `span_{F_2}{f_i}` are discarded — they are generators the solver
/// already has — and the rest are returned as `new_generators`.
pub fn extract_degree_falls(eqs: &[F2BoolPoly], num_vars: u32) -> DegreeFallReport {
    let cols3 = num_monomials_upto_degree(num_vars, 3) as usize;
    let words = cols3.div_ceil(64);
    let low_words = (num_monomials_upto_degree(num_vars, 2) as usize).div_ceil(64);

    // Full and cubic-only bit vectors for every row x_k·f_i.
    let mut full: Vec<Vec<u64>> = Vec::with_capacity(eqs.len() * num_vars as usize);
    let mut cubic: Vec<Vec<u64>> = Vec::with_capacity(eqs.len() * num_vars as usize);
    for f in eqs {
        for k in 0..num_vars {
            let bits = cubic_row_bits(f, num_vars, k, words);
            cubic.push(cubic_part_only(&bits, num_vars, words));
            full.push(bits);
        }
    }

    // Null space of the cubic-part map, carrying provenance so we can
    // re-evaluate each cancellation on the full rows.
    struct Pivot {
        vec: Vec<u64>,
        lead: usize,
        combo: Vec<u32>,
    }
    let mut pivots: Vec<Pivot> = Vec::new();
    let mut deps: Vec<Vec<u32>> = Vec::new();
    for (j, col) in cubic.iter().enumerate() {
        let mut vec = col.clone();
        let mut combo = vec![j as u32];
        while let Some(l) = lead_bit(&vec) {
            match pivots.iter().find(|p| p.lead == l) {
                Some(p) => {
                    for w in 0..words {
                        vec[w] ^= p.vec[w];
                    }
                    // Symmetric difference of the provenance sets.
                    let mut merged: Vec<u32> = Vec::new();
                    let (mut a, mut b) = (0usize, 0usize);
                    while a < combo.len() && b < p.combo.len() {
                        match combo[a].cmp(&p.combo[b]) {
                            std::cmp::Ordering::Less => {
                                merged.push(combo[a]);
                                a += 1;
                            }
                            std::cmp::Ordering::Greater => {
                                merged.push(p.combo[b]);
                                b += 1;
                            }
                            std::cmp::Ordering::Equal => {
                                a += 1;
                                b += 1;
                            }
                        }
                    }
                    merged.extend_from_slice(&combo[a..]);
                    merged.extend_from_slice(&p.combo[b..]);
                    combo = merged;
                }
                None => {
                    pivots.push(Pivot {
                        vec: vec.clone(),
                        lead: l,
                        combo: combo.clone(),
                    });
                    break;
                }
            }
        }
        if lead_bit(&vec).is_none() {
            combo.sort_unstable();
            deps.push(combo);
        }
    }

    // Seed the independence basis with the original generators, so a fall
    // that merely reproduces one of them is not counted as new.
    let poly_bits = |f: &F2BoolPoly| -> Vec<u64> {
        let mut v = vec![0u64; low_words.max(1)];
        if f.coeffs[0] {
            v[0] ^= 1;
        }
        for i in 0..num_vars {
            if f.coeffs[1 + i as usize] {
                let idx = monomial_index(&[i], num_vars, 2);
                v[idx / 64] ^= 1u64 << (idx % 64);
            }
        }
        for i in 0..num_vars {
            for j in (i + 1)..num_vars {
                let qi = quad_monomial_index(i, j, num_vars);
                if qi < f.coeffs.len() && f.coeffs[qi] {
                    let idx = monomial_index(&[i, j], num_vars, 2);
                    v[idx / 64] ^= 1u64 << (idx % 64);
                }
            }
        }
        v
    };
    let mut basis: Vec<(usize, Vec<u64>)> = Vec::new();
    let insert = |mut v: Vec<u64>, basis: &mut Vec<(usize, Vec<u64>)>| -> bool {
        loop {
            let Some(l) = lead_bit(&v) else { return false };
            match basis.iter().find(|(bl, _)| *bl == l) {
                Some((_, bv)) => {
                    for w in 0..v.len() {
                        v[w] ^= bv[w];
                    }
                }
                None => {
                    basis.push((l, v));
                    return true;
                }
            }
        }
    };
    for f in eqs {
        insert(poly_bits(f), &mut basis);
    }

    let mut pure = 0usize;
    let mut falls = 0usize;
    let mut new_generators = Vec::new();
    for combo in &deps {
        let mut acc = vec![0u64; words];
        for &c in combo {
            for w in 0..words {
                acc[w] ^= full[c as usize][w];
            }
        }
        if lead_bit(&acc).is_none() {
            pure += 1;
            continue;
        }
        falls += 1;
        let g = bits_to_poly(&acc, num_vars);
        if insert(poly_bits(&g), &mut basis) {
            new_generators.push(g);
        }
    }

    DegreeFallReport {
        degree: 3,
        rows: cubic.len(),
        cancel_dim: deps.len(),
        pure_syzygies: pure,
        falls,
        new_generators,
    }
}

/// log2 cost of a Macaulay elimination at degree `D` on a system of `eqs`
/// quadratics in `vars` Boolean variables:
///
/// ```text
///   rows(D) = eqs · cols(vars, D−2)      (multipliers up to degree D−2)
///   cost    = rows(D) · cols(vars, D)^{ω−1}
/// ```
///
/// Unlike the pure `cols^ω` model used for hybrid slicing, this one keeps
/// the row count explicit — lever L4 *adds* generators, so it pays for a
/// lower degree with a wider matrix, and a model blind to rows would score
/// that trade as free.
pub fn log2_macaulay_cost(vars: u32, eqs: u32, degree: u32, omega: f64) -> f64 {
    let cols = num_monomials_upto_degree(vars, degree) as f64;
    let mult = num_monomials_upto_degree(vars, degree.saturating_sub(2)) as f64;
    let rows = eqs as f64 * mult;
    rows.log2() + (omega - 1.0) * cols.log2()
}

/// Jensen-correct expected log2 cost over a `D*` histogram.
pub fn log2_expected_cost(hist: &BTreeMap<u32, u32>, vars: u32, eqs: u32, omega: f64) -> f64 {
    let total: u32 = hist.values().sum();
    if total == 0 {
        return f64::NAN;
    }
    let mut acc = 0.0f64;
    for (&d, &c) in hist {
        acc += (c as f64 / total as f64) * log2_macaulay_cost(vars, eqs, d, omega).exp2();
    }
    acc.log2()
}

/// Repeatedly extract degree-3 falls and fold them back into the generating
/// set until no new generator appears or `rounds` is exhausted.
///
/// One round is not the whole story: a fall added as a generator creates new
/// products `x_k · g`, which can cancel against each other and produce
/// *further* falls that were degree-4 consequences of the original system.
/// Iterating to saturation is what MutantXL does, and it is cheap here —
/// each round is one degree-3 kernel, strictly less work than the degree-3
/// Macaulay rank the solver performs anyway.
///
/// Returns the saturated system and the per-round count of new generators.
pub fn saturate_with_falls(
    eqs: &[F2BoolPoly],
    num_vars: u32,
    rounds: u32,
) -> (Vec<F2BoolPoly>, Vec<usize>) {
    let mut current = eqs.to_vec();
    let mut per_round = Vec::new();
    for _ in 0..rounds {
        let report = extract_degree_falls(&current, num_vars);
        let added = report.new_generators.len();
        per_round.push(added);
        if added == 0 {
            break;
        }
        current.extend(report.new_generators);
    }
    (current, per_round)
}

/// One matched-target comparison: `D*` before and after adding the degree-3
/// falls to the generating set.
#[derive(Clone, Debug)]
pub struct MutantRow {
    pub n: u32,
    pub n_sub: u32,
    pub full_vars: u32,
    pub targets: u32,
    /// Mean `D*` of the raw descended system.
    pub dstar_base_mean: f64,
    /// `D*` histogram of the raw system (degree → count), for a
    /// Jensen-correct cost expectation.
    pub dstar_base_hist: BTreeMap<u32, u32>,
    /// Mean `D*` after augmenting with the new degree-3 generators.
    pub dstar_aug_mean: f64,
    /// `D*` histogram of the augmented system.
    pub dstar_aug_hist: BTreeMap<u32, u32>,
    /// Targets where augmenting strictly lowered `D*`.
    pub improved: u32,
    /// Targets where augmenting *raised* `D*` (must be 0 — adding ideal
    /// elements cannot make the system harder).
    pub worsened: u32,
    /// Mean dimension of the cubic cancellation space.
    pub cancel_dim_mean: f64,
    /// Mean count of pure syzygies (EXP-J's population).
    pub pure_syzygies_mean: f64,
    /// Mean count of genuine degree falls.
    pub falls_mean: f64,
    /// Mean count of falls that were new generators in the first round.
    pub new_generators_mean: f64,
    /// Mean number of saturation rounds that produced at least one new
    /// generator (1 = a single round exhausted the falls).
    pub productive_rounds_mean: f64,
    /// Mean total generators added across all rounds.
    pub total_added_mean: f64,
    /// Mean equation count of the saturated system (the extra Macaulay rows
    /// the degree reduction is paid for with).
    pub aug_eqs_mean: f64,
    /// log2 of the mean **extraction** cost: every saturation round builds
    /// the degree-3 rows of the system as it stands and takes a kernel, and
    /// that work is what produces the falls. Charging only the cheap
    /// augmented solve would be double-counting the saving — the tower still
    /// had to reach degree 3 to get there.
    pub log2_extraction_cost: f64,
    /// The highest Macaulay degree the augmented route actually touches:
    /// `max(3, D*_aug)`, since extraction itself works at degree 3. This is
    /// the honest single-number comparison against `D*_base`.
    pub working_degree_mean: f64,
}

/// Run the L4 comparison at one operating point over `targets`
/// non-decomposable targets, measuring `D*` on the same target twice — once
/// on the raw system, once on the system augmented with its degree-3 falls.
#[allow(clippy::too_many_arguments)]
pub fn run_mutant_cell(
    family: BasisFamily,
    n: u32,
    n_sub: u32,
    irr: &IrreduciblePoly,
    targets: u32,
    d_max: u32,
    rounds: u32,
    seed: u64,
) -> Option<MutantRow> {
    let full_vars = 2 * n_sub;
    let mut state = seed | 1;
    let mut next = move || {
        state ^= state >> 12;
        state ^= state << 25;
        state ^= state >> 27;
        state.wrapping_mul(0x2545F4914F6CDD1D)
    };
    let rand_nz = |m: u32, rng: &mut dyn FnMut() -> u64| loop {
        let bits: Vec<u32> = (0..m).filter(|_| (rng() >> 19) & 1 == 1).collect();
        let e = F2mElement::from_bit_positions(&bits, m);
        if !e.is_zero() {
            return e;
        }
    };

    let (mut base_sum, mut aug_sum) = (0.0f64, 0.0f64);
    let (mut improved, mut worsened, mut found) = (0u32, 0u32, 0u32);
    let (mut cancel_sum, mut pure_sum, mut fall_sum, mut newgen_sum) = (0.0, 0.0, 0.0, 0.0);
    let (mut rounds_sum, mut added_sum, mut augeqs_sum) = (0.0f64, 0.0f64, 0.0f64);
    let mut base_hist: BTreeMap<u32, u32> = BTreeMap::new();
    let mut aug_hist: BTreeMap<u32, u32> = BTreeMap::new();
    let (mut extract_cost_sum, mut working_sum) = (0.0f64, 0.0f64);

    let mut attempts = 0u32;
    while found < targets && attempts < targets * 64 + 256 {
        attempts += 1;
        let v = match family {
            BasisFamily::Random => {
                FactorSubspace::build(family, n, n_sub, irr, seed ^ (0x9E37 + attempts as u64))?
            }
            _ => FactorSubspace::build(family, n, n_sub, irr, 0)?,
        };
        let b = rand_nz(n, &mut next);
        let x3 = rand_nz(n, &mut next);
        if is_decomposable_on_subspace(&v, irr, &b, &x3) {
            continue;
        }

        let eqs = descend_on_subspace(n, &v, irr, &b, &x3);
        let (_, base, _) = refutation_scan(&eqs, full_vars, d_max);
        let Some(base) = base else { continue };

        let report = extract_degree_falls(&eqs, full_vars);
        let (aug, per_round) = saturate_with_falls(&eqs, full_vars, rounds);
        // Charge every saturation round: round r operates on the system as it
        // stood going in, so its generator count is n + (all falls added so
        // far). Summed in linear space, then logged by the caller.
        let mut eqs_so_far = eqs.len() as u32;
        let mut extract_linear = 0.0f64;
        for added in &per_round {
            extract_linear += log2_macaulay_cost(full_vars, eqs_so_far, 3, 2.807).exp2();
            eqs_so_far += *added as u32;
        }
        let (_, augd, _) = refutation_scan(&aug, full_vars, d_max);
        let Some(augd) = augd else { continue };

        found += 1;
        base_sum += base as f64;
        aug_sum += augd as f64;
        *base_hist.entry(base).or_insert(0) += 1;
        *aug_hist.entry(augd).or_insert(0) += 1;
        if augd < base {
            improved += 1;
        }
        if augd > base {
            worsened += 1;
        }
        cancel_sum += report.cancel_dim as f64;
        pure_sum += report.pure_syzygies as f64;
        fall_sum += report.falls as f64;
        newgen_sum += report.new_generators.len() as f64;
        extract_cost_sum += extract_linear;
        working_sum += augd.max(3) as f64;
        rounds_sum += per_round.iter().filter(|c| **c > 0).count() as f64;
        added_sum += per_round.iter().sum::<usize>() as f64;
        augeqs_sum += aug.len() as f64;
    }

    if found == 0 {
        return None;
    }
    let f = found as f64;
    Some(MutantRow {
        n,
        n_sub,
        full_vars,
        targets: found,
        dstar_base_mean: base_sum / f,
        dstar_base_hist: base_hist,
        dstar_aug_mean: aug_sum / f,
        dstar_aug_hist: aug_hist,
        improved,
        worsened,
        cancel_dim_mean: cancel_sum / f,
        pure_syzygies_mean: pure_sum / f,
        falls_mean: fall_sum / f,
        new_generators_mean: newgen_sum / f,
        productive_rounds_mean: rounds_sum / f,
        total_added_mean: added_sum / f,
        aug_eqs_mean: augeqs_sum / f,
        log2_extraction_cost: (extract_cost_sum / f).log2(),
        working_degree_mean: working_sum / f,
    })
}

// ── R5: composing one-sided guessing with the mutant route ──────────
//
// Iteration 1 killed hybrid slicing on its own (the cost optimum is
// exhaustive search) but left one usable fact: **one-sided** guessing
// reaches the `D* = 2` floor at exactly `k₂ = n'`, i.e. a collapse fraction
// `c = 1/2`, flat across sizes and seeds. Iteration 2 showed lever L4
// lowers the working degree on the hard family.
//
// The composition asks whether the mutant route reaches the floor at
// `c < 1/2`. That threshold is the whole question: total work is
// `2^{cN} · poly`, so `c < 1/2` is strictly better than pure one-sided
// guessing, and it is the only route left to beating the `2^N` enumeration
// baseline that iteration 1 established.
//
// The comparison is **matched per slice**: the same specialised system is
// measured twice, once raw and once saturated with its own degree falls.

/// One `k` of the composed sweep: raw vs mutant `D*` on the same slices.
#[derive(Clone, Debug)]
pub struct ComposedRow {
    pub k: u32,
    pub vars: u32,
    pub slices: u32,
    /// Slices where either route failed to refute within `d_max`.
    pub censored: u32,
    pub raw_dstar_mean: f64,
    pub raw_dstar_max: u32,
    pub mut_dstar_mean: f64,
    pub mut_dstar_max: u32,
    /// `max(3, D*_mut)` averaged — the degree the mutant route actually
    /// touches, since extraction itself works at degree 3 (iteration 2).
    pub mut_working_mean: f64,
    pub new_generators_mean: f64,
    /// Mean equation count of a saturated slice (extra Macaulay rows).
    pub aug_eqs_mean: f64,
    /// log2 of the mean per-slice extraction cost (all saturation rounds).
    pub log2_extraction_cost: f64,
}

impl ComposedRow {
    /// log2 total work of the **raw** guess-only route at this `k`:
    /// `2^k` slices, each a Macaulay solve at its own `D*`.
    pub fn log2_raw_total(&self, eqs: u32, omega: f64) -> f64 {
        self.k as f64 + log2_macaulay_cost(self.vars, eqs, self.raw_dstar_mean.ceil() as u32, omega)
    }

    /// log2 total work of the **composed** route at this `k`: `2^k` slices,
    /// each paying its degree-3 extraction *plus* the augmented solve.
    ///
    /// Charging extraction is the whole point — iteration 2 established that
    /// booking only the cheap augmented solve double-counts the degree the
    /// extraction itself had to climb to.
    pub fn log2_composed_total(&self, omega: f64) -> f64 {
        let solve = log2_macaulay_cost(
            self.vars,
            self.aug_eqs_mean.round().max(1.0) as u32,
            self.mut_dstar_mean.ceil() as u32,
            omega,
        );
        self.k as f64 + (self.log2_extraction_cost.exp2() + solve.exp2()).log2()
    }
}

/// The composed sweep at one operating point.
#[derive(Clone, Debug)]
pub struct ComposedSweep {
    pub family: BasisFamily,
    pub pattern: GuessPattern,
    pub n: u32,
    pub n_sub: u32,
    pub full_vars: u32,
    pub targets: u32,
    pub rounds: u32,
    pub rows: Vec<ComposedRow>,
}

impl ComposedSweep {
    /// Smallest `k/N` at which **every** sampled slice of the raw system is
    /// at the `D* = 2` floor.
    pub fn raw_collapse_fraction(&self) -> Option<f64> {
        self.rows
            .iter()
            .find(|r| r.censored == 0 && r.raw_dstar_max <= 2)
            .map(|r| r.k as f64 / self.full_vars as f64)
    }

    /// Largest `k` scanned.
    pub fn k_max(&self) -> u32 {
        self.rows.last().map(|r| r.k).unwrap_or(0)
    }

    /// Does a route's cost curve have an **interior** minimum?
    ///
    /// Same honesty check as [`HybridSweep::optimum_is_interior`], and it
    /// matters for the same reason: the `k = N` endpoint of either route is
    /// exhaustive search, so at toy sizes a cost model will slide the optimum
    /// to the largest `k` scanned and call that a result. `cost` picks the
    /// route (raw or composed) to check.
    pub fn optimum_is_interior(&self, cost: impl Fn(&ComposedRow) -> f64) -> bool {
        self.rows
            .iter()
            .map(|r| (r.k, cost(r)))
            .filter(|(_, c)| c.is_finite())
            .min_by(|a, b| a.1.partial_cmp(&b.1).unwrap())
            .map(|(k, _)| k < self.k_max())
            .unwrap_or(false)
    }

    /// Same for the mutant-augmented system — the quantity G-R5 tests.
    pub fn mutant_collapse_fraction(&self) -> Option<f64> {
        self.rows
            .iter()
            .find(|r| r.censored == 0 && r.mut_dstar_max <= 2)
            .map(|r| r.k as f64 / self.full_vars as f64)
    }
}

/// Run the composed (guess-then-mutate) sweep.
///
/// For each non-decomposable target and each `k`, take `slices_per_k` random
/// assignments of the `k` guessed variables and measure the resulting
/// slice's `D*` **twice** — raw, and after saturating it with its own
/// degree-3 falls — so the two routes are compared on identical systems.
#[allow(clippy::too_many_arguments)]
pub fn run_composed_sweep(
    family: BasisFamily,
    pattern: GuessPattern,
    n: u32,
    n_sub: u32,
    irr: &IrreduciblePoly,
    k_max: u32,
    targets: u32,
    slices_per_k: u32,
    d_max: u32,
    rounds: u32,
    seed: u64,
) -> Option<ComposedSweep> {
    let full_vars = 2 * n_sub;
    let k_max = k_max.min(full_vars.saturating_sub(2));

    let mut t_state = seed | 1;
    let mut next_target = move || {
        t_state ^= t_state >> 12;
        t_state ^= t_state << 25;
        t_state ^= t_state >> 27;
        t_state.wrapping_mul(0x2545F4914F6CDD1D)
    };
    let mut s_state = seed.rotate_left(32) | 1;
    let mut next_slice = move || {
        s_state ^= s_state >> 12;
        s_state ^= s_state << 25;
        s_state ^= s_state >> 27;
        s_state.wrapping_mul(0x2545F4914F6CDD1D)
    };
    let rand_nz = |m: u32, rng: &mut dyn FnMut() -> u64| loop {
        let bits: Vec<u32> = (0..m).filter(|_| (rng() >> 19) & 1 == 1).collect();
        let e = F2mElement::from_bit_positions(&bits, m);
        if !e.is_zero() {
            return e;
        }
    };

    struct Acc {
        slices: u32,
        censored: u32,
        raw_sum: f64,
        raw_max: u32,
        mut_sum: f64,
        mut_max: u32,
        working_sum: f64,
        newgen_sum: f64,
        extract_linear: f64,
        aug_eqs_sum: f64,
    }
    let mut acc: Vec<Acc> = (0..=k_max)
        .map(|_| Acc {
            slices: 0,
            censored: 0,
            raw_sum: 0.0,
            raw_max: 0,
            mut_sum: 0.0,
            mut_max: 0,
            working_sum: 0.0,
            newgen_sum: 0.0,
            extract_linear: 0.0,
            aug_eqs_sum: 0.0,
        })
        .collect();

    let mut found = 0u32;
    let mut attempts = 0u32;
    while found < targets && attempts < targets * 64 + 256 {
        attempts += 1;
        let v = match family {
            BasisFamily::Random => {
                FactorSubspace::build(family, n, n_sub, irr, seed ^ (0x9E37 + attempts as u64))?
            }
            _ => FactorSubspace::build(family, n, n_sub, irr, 0)?,
        };
        let b = rand_nz(n, &mut next_target);
        let x3 = rand_nz(n, &mut next_target);
        if is_decomposable_on_subspace(&v, irr, &b, &x3) {
            continue;
        }
        found += 1;
        let eqs = descend_on_subspace(n, &v, irr, &b, &x3);

        for k in 0..=k_max {
            let reps = if k == 0 { 1 } else { slices_per_k };
            for _ in 0..reps {
                let idx = pattern.pick(full_vars, k, &mut next_slice);
                let mut assign: Vec<Option<bool>> = vec![None; full_vars as usize];
                for &i in &idx {
                    assign[i as usize] = Some((next_slice() >> 23) & 1 == 1);
                }
                let (slice, nv) = specialize(&eqs, full_vars, &assign);

                let a = &mut acc[k as usize];
                a.slices += 1;

                let (_, raw, _) = refutation_scan(&slice, nv, d_max);
                let (sat, per_round) = saturate_with_falls(&slice, nv, rounds);
                let (_, mutd, _) = refutation_scan(&sat, nv, d_max);

                // Charge every saturation round on the system as it stood
                // going in — the same accounting iteration 2 settled on.
                let mut eqs_so_far = slice.len() as u32;
                let mut extract = 0.0f64;
                for added in &per_round {
                    extract += log2_macaulay_cost(nv, eqs_so_far, 3, 2.807).exp2();
                    eqs_so_far += *added as u32;
                }

                match (raw, mutd) {
                    (Some(r), Some(m)) => {
                        a.raw_sum += r as f64;
                        a.raw_max = a.raw_max.max(r);
                        a.mut_sum += m as f64;
                        a.mut_max = a.mut_max.max(m);
                        a.working_sum += m.max(3) as f64;
                        a.newgen_sum += per_round.iter().sum::<usize>() as f64;
                        a.extract_linear += extract;
                        a.aug_eqs_sum += sat.len() as f64;
                    }
                    _ => a.censored += 1,
                }
            }
        }
    }
    if found == 0 {
        return None;
    }

    let rows = (0..=k_max)
        .map(|k| {
            let a = &acc[k as usize];
            let m = (a.slices - a.censored).max(1) as f64;
            ComposedRow {
                k,
                vars: full_vars - k,
                slices: a.slices,
                censored: a.censored,
                raw_dstar_mean: a.raw_sum / m,
                raw_dstar_max: a.raw_max,
                mut_dstar_mean: a.mut_sum / m,
                mut_dstar_max: a.mut_max,
                mut_working_mean: a.working_sum / m,
                new_generators_mean: a.newgen_sum / m,
                aug_eqs_mean: a.aug_eqs_sum / m,
                log2_extraction_cost: (a.extract_linear / m).log2(),
            }
        })
        .collect();

    Some(ComposedSweep {
        family,
        pattern,
        n,
        n_sub,
        full_vars,
        targets: found,
        rounds,
        rows,
    })
}

// ── R4': is the Δ_low screen fixable by renormalising? ──────────────
//
// Iteration 1 found the `Δ_low` screen reads wrong across systems of
// different shape: under slicing, `D*` falls monotonically while `Δ_low`
// wanders. The obvious diagnosis was units — `Δ_low = Σδ / cols(D_low)` is
// normalised by a monomial count that shrinks with the variable count — and
// the obvious fix a better normaliser. This section tests that diagnosis
// instead of assuming it.
//
// The design separates the two candidate causes by measuring three groups:
//
// | group | what varies | what is held | tests |
// |---|---|---|---|
// | `within-shape` | factor-base family, target | `(vars, eqs)`, `ρ` | the regime the FFD law was fitted in |
// | `rho-varies`   | `k` (slicing) | `eqs` | shape *and* `ρ` both move |
// | `rho-matched`  | `(n, n')` together at `2n'=n` | `ρ ≈ 1` | shape moves, `ρ` does not |
//
// If a renormalisation rescues `rho-varies`, the problem was units. If the
// law holds in `within-shape` and `rho-matched` but fails in `rho-varies`
// for *every* variant, the problem is not units at all — it is that
// over-determination changes the law's sign, and no rescaling fixes a sign
// flip. The prescription would then be "compare at matched `ρ`", which is
// what any lever that changes the variable count (L2) needs to know.

/// Candidate scalar summaries of the low-degree rank defect.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DefectVariant {
    /// `Σδ / cols(cutoff)` — the FFD program's `Δ_low`, as fitted. The
    /// incumbent, and the one iteration 1 found shape-dependent.
    Normalised,
    /// `Σδ` — the raw excess-syzygy count, no normalisation at all.
    Raw,
    /// `Σ δ(D)/r_gen(D)` — defect as a fraction of the *generic* rank.
    /// The leading correction candidate: `r_gen` already encodes both the
    /// variable and the equation count, so the ratio is shape-aware by
    /// construction rather than by a chosen denominator.
    GenericFraction,
    /// `Σδ / #eqs` — per-equation excess.
    PerEquation,
    /// `Σ δ(D)/rows(D)` — the fraction of multiplied rows that are wasted.
    RowFraction,
}

/// Every variant, in report order.
pub const DEFECT_VARIANTS: [DefectVariant; 5] = [
    DefectVariant::Normalised,
    DefectVariant::Raw,
    DefectVariant::GenericFraction,
    DefectVariant::PerEquation,
    DefectVariant::RowFraction,
];

impl DefectVariant {
    pub fn label(&self) -> &'static str {
        match self {
            DefectVariant::Normalised => "normalised",
            DefectVariant::Raw => "raw",
            DefectVariant::GenericFraction => "generic-frac",
            DefectVariant::PerEquation => "per-equation",
            DefectVariant::RowFraction => "row-frac",
        }
    }

    /// Evaluate the variant on a rank profile, summing degrees `≤ cutoff`.
    pub fn value(&self, profile: &[RankRow], cutoff: u32, eqs: u32) -> f64 {
        let rows = profile.iter().filter(|r| r.degree <= cutoff);
        match self {
            DefectVariant::Normalised => {
                let mut sum = 0.0;
                let mut norm = 1.0;
                for r in rows {
                    sum += r.defect as f64;
                    norm = r.cols.max(1) as f64;
                }
                sum / norm
            }
            DefectVariant::Raw => rows.map(|r| r.defect as f64).sum(),
            DefectVariant::GenericFraction => rows
                .map(|r| r.defect as f64 / r.generic_rank.max(1) as f64)
                .sum(),
            DefectVariant::PerEquation => {
                rows.map(|r| r.defect as f64).sum::<f64>() / eqs.max(1) as f64
            }
            DefectVariant::RowFraction => {
                rows.map(|r| r.defect as f64 / r.rows.max(1) as f64).sum()
            }
        }
    }
}

/// One measured instance: every defect variant, plus the `D*` they are
/// supposed to predict.
#[derive(Clone, Debug)]
pub struct DefectCell {
    /// `"within-shape"`, `"rho-varies"` or `"rho-matched"`.
    pub group: &'static str,
    /// Factor-base family, so pooled groups can be aggregated to cell means
    /// the way the FFD program's EXP-G does before correlating.
    pub family: BasisFamily,
    pub vars: u32,
    pub eqs: u32,
    /// `#eqs / #vars` — the determination ratio.
    pub rho: f64,
    pub dstar: u32,
    /// Values parallel to [`DEFECT_VARIANTS`].
    pub defects: Vec<f64>,
}

fn defect_cell(
    group: &'static str,
    family: BasisFamily,
    eqs: &[F2BoolPoly],
    vars: u32,
    n_eqs: u32,
    d_max: u32,
    cutoff: u32,
) -> Option<DefectCell> {
    let (_, dstar, _) = refutation_scan(eqs, vars, d_max);
    let dstar = dstar?;
    let profile = rank_profile(eqs, vars, n_eqs, cutoff.min(d_max));
    Some(DefectCell {
        group,
        family,
        vars,
        eqs: n_eqs,
        rho: n_eqs as f64 / vars.max(1) as f64,
        dstar,
        defects: DEFECT_VARIANTS
            .iter()
            .map(|v| v.value(&profile, cutoff, n_eqs))
            .collect(),
    })
}

/// Collect the `within-shape` and `rho-varies` groups at one operating
/// point: `k = 0` gives the fixed-shape cells (varying only the factor-base
/// family and target), and `k > 0` slices give the cells where both shape
/// and `ρ` move.
#[allow(clippy::too_many_arguments)]
pub fn collect_defect_cells(
    n: u32,
    n_sub: u32,
    irr: &IrreduciblePoly,
    families: &[BasisFamily],
    k_values: &[u32],
    targets: u32,
    d_max: u32,
    cutoff: u32,
    seed: u64,
) -> Vec<DefectCell> {
    let full_vars = 2 * n_sub;
    let mut out = Vec::new();
    let mut state = seed | 1;
    let mut next = move || {
        state ^= state >> 12;
        state ^= state << 25;
        state ^= state >> 27;
        state.wrapping_mul(0x2545F4914F6CDD1D)
    };
    let rand_nz = |m: u32, rng: &mut dyn FnMut() -> u64| loop {
        let bits: Vec<u32> = (0..m).filter(|_| (rng() >> 19) & 1 == 1).collect();
        let e = F2mElement::from_bit_positions(&bits, m);
        if !e.is_zero() {
            return e;
        }
    };

    for &family in families {
        let mut found = 0u32;
        let mut attempts = 0u32;
        while found < targets && attempts < targets * 64 + 256 {
            attempts += 1;
            let Some(v) = (match family {
                BasisFamily::Random => {
                    FactorSubspace::build(family, n, n_sub, irr, seed ^ (0x9E37 + attempts as u64))
                }
                _ => FactorSubspace::build(family, n, n_sub, irr, 0),
            }) else {
                break;
            };
            let b = rand_nz(n, &mut next);
            let x3 = rand_nz(n, &mut next);
            if is_decomposable_on_subspace(&v, irr, &b, &x3) {
                continue;
            }
            found += 1;
            let base = descend_on_subspace(n, &v, irr, &b, &x3);

            if let Some(c) = defect_cell("within-shape", family, &base, full_vars, n, d_max, cutoff)
            {
                out.push(c);
            }
            for &k in k_values {
                if k == 0 || k >= full_vars.saturating_sub(1) {
                    continue;
                }
                let idx = GuessPattern::OneSide.pick(full_vars, k, &mut next);
                let mut assign: Vec<Option<bool>> = vec![None; full_vars as usize];
                for &i in &idx {
                    assign[i as usize] = Some((next() >> 23) & 1 == 1);
                }
                let (slice, nv) = specialize(&base, full_vars, &assign);
                if let Some(c) = defect_cell("rho-varies", family, &slice, nv, n, d_max, cutoff) {
                    out.push(c);
                }
            }
        }
    }
    out
}

/// Collect the `rho-matched` group: vary `(n, n')` together along the
/// critical line `2n' = n`, so the variable count changes while `ρ ≈ 1`
/// stays put. This is the control that separates "shape" from "regime".
pub fn collect_rho_matched_cells(
    points: &[(u32, u32)],
    irrs: &[IrreduciblePoly],
    families: &[BasisFamily],
    targets: u32,
    d_max: u32,
    cutoff: u32,
    seed: u64,
) -> Vec<DefectCell> {
    let mut out = Vec::new();
    for (idx, &(n, n_sub)) in points.iter().enumerate() {
        let Some(irr) = irrs.get(idx) else { continue };
        let cells = collect_defect_cells(
            n,
            n_sub,
            irr,
            families,
            &[],
            targets,
            d_max,
            cutoff,
            seed ^ ((n as u64) << 8),
        );
        out.extend(cells.into_iter().map(|mut c| {
            c.group = "rho-matched";
            c
        }));
    }
    out
}

// ── Per-degree defect profile (EXP-R6) ──────────────────────────────

/// One target's defect measured **at each degree separately**, alongside
/// its `D*`.
///
/// EXP-R4d found `Δ_low` positively correlated with `D*` inside a
/// homogeneous group and explained it by censoring at the cutoff: a target
/// refuting at `D* = 2` never exercises degree 3, so its cutoff-3 defect is
/// ~0. That explanation predicts a *repair* — measure at a cutoff every
/// system must pass through. This row carries the per-degree numbers needed
/// to test that, rather than only the cumulative `Δ_low` the screen uses.
#[derive(Clone, Debug)]
pub struct DefectProfileRow {
    pub full_vars: u32,
    /// `δ(D)/cols(D)` for `D = 2, 3, 4` — the per-degree fractions.
    pub per_degree: [f64; 3],
    /// Cumulative `Δ_low` at cutoffs 2, 3, 4 — the screen's own statistic
    /// evaluated at three cutoffs.
    pub cumulative: [f64; 3],
    pub dstar: u32,
}

/// Names of the six defect readings in [`DefectProfileRow`], in order:
/// three per-degree fractions then three cumulative cutoffs.
pub const PROFILE_READINGS: [&str; 6] = [
    "delta(2)",
    "delta(3)",
    "delta(4)",
    "Delta_low(cut 2)",
    "Delta_low(cut 3)",
    "Delta_low(cut 4)",
];

impl DefectProfileRow {
    /// The six readings as one array, parallel to [`PROFILE_READINGS`].
    pub fn readings(&self) -> [f64; 6] {
        [
            self.per_degree[0],
            self.per_degree[1],
            self.per_degree[2],
            self.cumulative[0],
            self.cumulative[1],
            self.cumulative[2],
        ]
    }
}

/// Measure the per-degree defect profile and `D*` for `targets`
/// non-decomposable targets at one `(family, n, n')` cell.
#[allow(clippy::too_many_arguments)]
pub fn run_defect_profile_cell(
    family: BasisFamily,
    n: u32,
    n_sub: u32,
    irr: &IrreduciblePoly,
    targets: u32,
    d_max: u32,
    seed: u64,
) -> Vec<DefectProfileRow> {
    let full_vars = 2 * n_sub;
    let mut state = seed | 1;
    let mut next = move || {
        state ^= state >> 12;
        state ^= state << 25;
        state ^= state >> 27;
        state.wrapping_mul(0x2545F4914F6CDD1D)
    };
    let rand_nz = |m: u32, rng: &mut dyn FnMut() -> u64| loop {
        let bits: Vec<u32> = (0..m).filter(|_| (rng() >> 19) & 1 == 1).collect();
        let e = F2mElement::from_bit_positions(&bits, m);
        if !e.is_zero() {
            return e;
        }
    };

    let mut out = Vec::new();
    let mut attempts = 0u32;
    while (out.len() as u32) < targets && attempts < targets * 64 + 256 {
        attempts += 1;
        let v = match family {
            BasisFamily::Random => {
                match FactorSubspace::build(
                    family,
                    n,
                    n_sub,
                    irr,
                    seed ^ (0x9E37 + attempts as u64),
                ) {
                    Some(v) => v,
                    None => return out,
                }
            }
            _ => match FactorSubspace::build(family, n, n_sub, irr, 0) {
                Some(v) => v,
                None => return out,
            },
        };
        let b = rand_nz(n, &mut next);
        let x3 = rand_nz(n, &mut next);
        if is_decomposable_on_subspace(&v, irr, &b, &x3) {
            continue;
        }
        let eqs = descend_on_subspace(n, &v, irr, &b, &x3);
        let Some(dstar) = refutation_scan(&eqs, full_vars, d_max).1 else {
            continue;
        };
        let profile = rank_profile(&eqs, full_vars, n, 4.min(d_max));
        let at = |deg: u32| -> f64 {
            profile
                .iter()
                .find(|r| r.degree == deg)
                .map(|r| r.defect as f64 / r.cols.max(1) as f64)
                .unwrap_or(0.0)
        };
        out.push(DefectProfileRow {
            full_vars,
            per_degree: [at(2), at(3), at(4)],
            cumulative: [
                early_defect(&profile, 2),
                early_defect(&profile, 3),
                early_defect(&profile, 4),
            ],
            dstar,
        });
    }
    out
}

// ── Presentation dose-response (EXP-R4d) ────────────────────────────

/// One target measured under three presentations of the **same system at
/// the same variable count**: the raw descended system, the system after a
/// single saturation round, and the fully saturated system.
///
/// The three differ only in how many degree-3 falls have been folded into
/// the generating set, so this is a *dose* axis for lever L4 with nothing
/// cross-shape in it. That matters because R4′ established that `Δ_low`
/// cannot compare instances across shapes; holding `vars` and the target
/// fixed removes that objection entirely, leaving only the question R4
/// actually asked — does the lever act *through* the defect?
#[derive(Clone, Debug)]
pub struct PresentationRow {
    pub full_vars: u32,
    /// Generator counts under the three presentations.
    pub eqs: [u32; 3],
    /// `Δ_low` under raw / one-round / saturated.
    pub defect: [f64; 3],
    /// `D*` under raw / one-round / saturated.
    pub dstar: [u32; 3],
}

/// Labels for the three presentations, in the order they appear in
/// [`PresentationRow`]'s arrays.
pub const PRESENTATIONS: [&str; 3] = ["raw", "one-round", "saturated"];

/// Measure `targets` non-decomposable targets under all three
/// presentations at one `(family, n, n')` cell.
///
/// Returns one row per target for which every presentation refuted within
/// `d_max`; a target that censors under any presentation is dropped
/// entirely rather than contributing a partial row, so the three columns
/// are always the same set of targets.
#[allow(clippy::too_many_arguments)]
pub fn run_presentation_cell(
    family: BasisFamily,
    n: u32,
    n_sub: u32,
    irr: &IrreduciblePoly,
    targets: u32,
    d_max: u32,
    rounds: u32,
    seed: u64,
) -> Vec<PresentationRow> {
    let full_vars = 2 * n_sub;
    let mut state = seed | 1;
    let mut next = move || {
        state ^= state >> 12;
        state ^= state << 25;
        state ^= state >> 27;
        state.wrapping_mul(0x2545F4914F6CDD1D)
    };
    let rand_nz = |m: u32, rng: &mut dyn FnMut() -> u64| loop {
        let bits: Vec<u32> = (0..m).filter(|_| (rng() >> 19) & 1 == 1).collect();
        let e = F2mElement::from_bit_positions(&bits, m);
        if !e.is_zero() {
            return e;
        }
    };

    let mut out = Vec::new();
    let mut attempts = 0u32;
    while (out.len() as u32) < targets && attempts < targets * 64 + 256 {
        attempts += 1;
        let v = match family {
            BasisFamily::Random => {
                match FactorSubspace::build(
                    family,
                    n,
                    n_sub,
                    irr,
                    seed ^ (0x9E37 + attempts as u64),
                ) {
                    Some(v) => v,
                    None => return out,
                }
            }
            _ => match FactorSubspace::build(family, n, n_sub, irr, 0) {
                Some(v) => v,
                None => return out,
            },
        };
        let b = rand_nz(n, &mut next);
        let x3 = rand_nz(n, &mut next);
        if is_decomposable_on_subspace(&v, irr, &b, &x3) {
            continue;
        }
        let raw = descend_on_subspace(n, &v, irr, &b, &x3);
        // One round, then saturation. `saturate_with_falls` with
        // `rounds = 1` is exactly the first round of the full run, so the
        // dose axis is nested by construction.
        let (one, _) = saturate_with_falls(&raw, full_vars, 1);
        let (sat, _) = saturate_with_falls(&raw, full_vars, rounds);

        let mut dstar = [0u32; 3];
        let mut defect = [0.0f64; 3];
        let mut eqs = [0u32; 3];
        let mut ok = true;
        for (i, sys) in [&raw, &one, &sat].into_iter().enumerate() {
            let ne = sys.len() as u32;
            let Some(d) = refutation_scan(sys, full_vars, d_max).1 else {
                ok = false;
                break;
            };
            let profile = rank_profile(sys, full_vars, ne, 3.min(d_max));
            eqs[i] = ne;
            dstar[i] = d;
            defect[i] = early_defect(&profile, 3);
        }
        if !ok {
            continue;
        }
        out.push(PresentationRow {
            full_vars,
            eqs,
            defect,
            dstar,
        });
    }
    out
}

// ── Size-controlled correlation (EXP-R4b) ───────────────────────────

/// One `(block, x, y)` observation for a blocked correlation.
///
/// `block` is the nuisance stratum to hold fixed — for the FFD program's
/// curve that is the operating point `(n, n')`, which fixes the variable
/// count and hence the system's size.
#[derive(Clone, Debug)]
pub struct BlockedObs {
    /// Stratum label. Observations sharing a label are compared only
    /// against each other by the three controlled statistics.
    pub block: String,
    /// Predictor (here: the early Hilbert-function defect `Δ_low`).
    pub x: f64,
    /// Response (here: the measured solving degree `D*`).
    pub y: f64,
}

/// A pooled correlation next to three size-controlled counterparts.
///
/// The point of computing four numbers rather than one is that a pooled
/// correlation across strata of different size cannot distinguish "the
/// predictor tracks the response" from "both track the stratum". The three
/// controlled statistics each remove the stratum in a different way, so
/// agreement between them is evidence the relation is real and disagreement
/// localises which part of the pooled figure was the nuisance variable:
///
/// * `mean_per_block` — correlate inside each stratum, then average. Gives
///   every stratum equal weight regardless of how many cells it holds, and
///   is the most direct reading of "does it hold at fixed size?".
/// * `blocked_rank` — rank within each stratum, rescale to a common mean
///   of 1/2, pool the ranks, correlate once. Uses all cells in a single
///   statistic, so small strata do not dominate. The rescaling is what
///   makes unequal strata rank-comparable: raw 1-based ranks have mean
///   `(n_g+1)/2`, and pooling them would add a between-block term
///   `Σ n_g (μ_g−μ)²` that is a function of the block size this
///   statistic exists to remove.
/// * `fixed_effects` — subtract each stratum's mean from its members and
///   correlate the residuals. Works on raw values rather than ranks, so it
///   is sensitive to magnitude as well as order.
#[derive(Clone, Debug)]
pub struct SizeControl {
    /// Total observations.
    pub n_cells: usize,
    /// Distinct strata.
    pub n_blocks: usize,
    /// Spearman `ρ_s` over all cells at once — the uncontrolled figure.
    pub pooled: Option<f64>,
    /// Mean of the per-stratum Spearman `ρ_s`, over strata where it is
    /// defined.
    pub mean_per_block: Option<f64>,
    /// Pearson `r` of within-stratum ranks, rescaled to mean 1/2 and pooled.
    pub blocked_rank: Option<f64>,
    /// Pearson `r` of within-stratum demeaned residuals.
    pub fixed_effects: Option<f64>,
    /// Per-stratum `(label, cells, ρ_s)`, sorted by label.
    pub per_block: Vec<(String, usize, Option<f64>)>,
}

/// 1-based ranks with ties averaged — the ranking [`spearman`] uses,
/// exposed here because the blocked statistic ranks *within* a stratum.
fn rank_within(v: &[f64]) -> Vec<f64> {
    let n = v.len();
    let mut idx: Vec<usize> = (0..n).collect();
    idx.sort_by(|&a, &b| v[a].partial_cmp(&v[b]).unwrap_or(std::cmp::Ordering::Equal));
    let mut r = vec![0.0; n];
    let mut i = 0;
    while i < n {
        let mut j = i;
        while j + 1 < n && (v[idx[j + 1]] - v[idx[i]]).abs() < 1e-12 {
            j += 1;
        }
        let avg = (i + j) as f64 / 2.0 + 1.0;
        for k in i..=j {
            r[idx[k]] = avg;
        }
        i = j + 1;
    }
    r
}

/// Compute the pooled correlation and its three size-controlled
/// counterparts over `obs`.
///
/// Strata with fewer than 3 observations contribute `None` to
/// `per_block` (and so are skipped by `mean_per_block`) but still
/// contribute their ranks and residuals to the two pooled-controlled
/// statistics, where they are harmless.
pub fn size_control(obs: &[BlockedObs]) -> SizeControl {
    let pooled = spearman(
        &obs.iter().map(|o| o.x).collect::<Vec<_>>(),
        &obs.iter().map(|o| o.y).collect::<Vec<_>>(),
    );
    let mut blocks: BTreeMap<&str, Vec<&BlockedObs>> = BTreeMap::new();
    for o in obs {
        blocks.entry(o.block.as_str()).or_default().push(o);
    }
    let mut per_block = Vec::new();
    let (mut brx, mut bry) = (Vec::new(), Vec::new());
    let (mut fex, mut fey) = (Vec::new(), Vec::new());
    for (label, rows) in &blocks {
        let xs: Vec<f64> = rows.iter().map(|o| o.x).collect();
        let ys: Vec<f64> = rows.iter().map(|o| o.y).collect();
        per_block.push((label.to_string(), rows.len(), spearman(&xs, &ys)));
        // Scale by n_g+1 so every stratum has rank mean 1/2. Without this,
        // unequal blocks inject Σ n_g (μ_g−μ)² into the pooled Pearson —
        // a non-negative function of block size that attenuates a negative
        // within-stratum law.
        let scale = rows.len() as f64 + 1.0;
        brx.extend(rank_within(&xs).into_iter().map(|r| r / scale));
        bry.extend(rank_within(&ys).into_iter().map(|r| r / scale));
        let mx = xs.iter().sum::<f64>() / xs.len() as f64;
        let my = ys.iter().sum::<f64>() / ys.len() as f64;
        fex.extend(xs.iter().map(|a| a - mx));
        fey.extend(ys.iter().map(|b| b - my));
    }
    let defined: Vec<f64> = per_block.iter().filter_map(|(_, _, r)| *r).collect();
    SizeControl {
        n_cells: obs.len(),
        n_blocks: blocks.len(),
        pooled,
        mean_per_block: if defined.is_empty() {
            None
        } else {
            Some(defined.iter().sum::<f64>() / defined.len() as f64)
        },
        blocked_rank: pearson_corr(&brx, &bry),
        fixed_effects: pearson_corr(&fex, &fey),
        per_block,
    }
}

/// Pearson `r`. `None` for fewer than 3 pairs or zero variance on either
/// side — the latter matters here because a stratum where every `D*` is
/// equal contributes an all-zero residual column.
fn pearson_corr(x: &[f64], y: &[f64]) -> Option<f64> {
    let n = x.len();
    if n < 3 || y.len() != n {
        return None;
    }
    let mx = x.iter().sum::<f64>() / n as f64;
    let my = y.iter().sum::<f64>() / n as f64;
    let sxy: f64 = x.iter().zip(y).map(|(a, b)| (a - mx) * (b - my)).sum();
    let sxx: f64 = x.iter().map(|a| (a - mx).powi(2)).sum();
    let syy: f64 = y.iter().map(|b| (b - my).powi(2)).sum();
    if sxx <= 0.0 || syy <= 0.0 {
        return None;
    }
    Some(sxy / (sxx * syy).sqrt())
}

// ── Tests ───────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::ffd_harness::choose_irreducible;

    /// Fixing nothing must return the system unchanged.
    #[test]
    fn specialize_with_no_fixed_vars_is_identity() {
        let n = 6;
        let irr = choose_irreducible(n);
        let v = FactorSubspace::build(BasisFamily::Coordinate, n, 3, &irr, 0).unwrap();
        let b = F2mElement::from_bit_positions(&[0, 2], n);
        let x3 = F2mElement::from_bit_positions(&[1], n);
        let eqs = descend_on_subspace(n, &v, &irr, &b, &x3);

        let assign = vec![None; 6];
        let (out, nv) = specialize(&eqs, 6, &assign);
        assert_eq!(nv, 6);
        assert_eq!(out.len(), eqs.len());
        for (a, e) in out.iter().zip(eqs.iter()) {
            assert_eq!(a.coeffs, e.coeffs);
        }
    }

    /// Substitution must agree with direct evaluation: for every assignment
    /// of the free variables, the sliced system and the original system
    /// (with the fixed values plugged in) must take the same values.
    #[test]
    fn specialize_agrees_with_direct_evaluation() {
        let n = 6;
        let irr = choose_irreducible(n);
        let v = FactorSubspace::build(BasisFamily::Coordinate, n, 3, &irr, 0).unwrap();
        let b = F2mElement::from_bit_positions(&[0, 1], n);
        let x3 = F2mElement::from_bit_positions(&[2], n);
        let eqs = descend_on_subspace(n, &v, &irr, &b, &x3);
        let nvars = 6u32;

        // Fix x0 = 1, x3 = 0.
        let mut assign: Vec<Option<bool>> = vec![None; nvars as usize];
        assign[0] = Some(true);
        assign[3] = Some(false);
        let (sliced, nv) = specialize(&eqs, nvars, &assign);
        assert_eq!(nv, 4);

        // Enumerate all assignments of the 4 free variables.
        for mask in 0u32..(1 << nv) {
            let free: Vec<bool> = (0..nv).map(|i| (mask >> i) & 1 == 1).collect();
            // Lift to the full 6-variable assignment.
            let mut full = vec![false; nvars as usize];
            let mut t = 0usize;
            for i in 0..nvars as usize {
                match assign[i] {
                    Some(val) => full[i] = val,
                    None => {
                        full[i] = free[t];
                        t += 1;
                    }
                }
            }
            for (orig, sl) in eqs.iter().zip(sliced.iter()) {
                assert_eq!(
                    eval_bool(orig, nvars, &full),
                    eval_bool(sl, nv, &free),
                    "slice disagrees at mask {mask}"
                );
            }
        }
    }

    fn eval_bool(f: &F2BoolPoly, nvars: u32, x: &[bool]) -> bool {
        let mut acc = f.coeffs[0];
        for i in 0..nvars as usize {
            if f.coeffs.get(1 + i).copied().unwrap_or(false) && x[i] {
                acc ^= true;
            }
        }
        for i in 0..nvars {
            for j in (i + 1)..nvars {
                let idx = quad_monomial_index(i, j, nvars);
                if idx < f.coeffs.len() && f.coeffs[idx] && x[i as usize] && x[j as usize] {
                    acc ^= true;
                }
            }
        }
        acc
    }

    /// The guess patterns must return `k` distinct in-range indices, and
    /// `OneSide` must stay inside the `X₁` half while `Balanced` must not.
    #[test]
    fn guess_patterns_pick_distinct_in_range_indices() {
        let mut state = 12345u64;
        let mut rng = move || {
            state ^= state >> 12;
            state ^= state << 25;
            state ^= state >> 27;
            state.wrapping_mul(0x2545F4914F6CDD1D)
        };
        let n_vars = 12u32;
        for pat in [
            GuessPattern::OneSide,
            GuessPattern::Balanced,
            GuessPattern::Spread,
        ] {
            for k in 0..=6u32 {
                let idx = pat.pick(n_vars, k, &mut rng);
                assert_eq!(idx.len(), k as usize, "{pat:?} k={k}");
                let mut sorted = idx.clone();
                sorted.sort_unstable();
                sorted.dedup();
                assert_eq!(sorted.len(), k as usize, "{pat:?} k={k} has duplicates");
                assert!(idx.iter().all(|&i| i < n_vars));
            }
        }
        let one = GuessPattern::OneSide.pick(n_vars, 4, &mut rng);
        assert!(one.iter().all(|&i| i < n_vars / 2));
        let bal = GuessPattern::Balanced.pick(n_vars, 4, &mut rng);
        assert!(bal.iter().any(|&i| i >= n_vars / 2));
    }

    /// The cost model must be Jensen-correct: computed from the histogram,
    /// not from the mean degree. A row whose `D*` is split between 2 and 4
    /// must cost strictly more than a row pinned at the mean degree 3.
    #[test]
    fn cost_model_uses_the_histogram_not_the_mean() {
        let mk = |hist: BTreeMap<u32, u32>| HybridRow {
            k: 0,
            vars: 12,
            eqs: 12,
            rho: 1.0,
            slices: 2,
            censored: 0,
            dstar_mean: 3.0,
            dstar_max: 4,
            dstar_hist: hist,
            delta_low_mean: 0.0,
            first_fall_mean: 3.0,
        };
        let split = mk(BTreeMap::from([(2, 1), (4, 1)]));
        let pinned = mk(BTreeMap::from([(3, 2)]));
        assert!(
            split.log2_total_cost(2.807) > pinned.log2_total_cost(2.807),
            "convexity: a spread of degrees must cost more than its mean"
        );
    }

    /// End-to-end smoke test of the sweep at a small operating point: rows
    /// must be produced for every `k`, `ρ` must increase with `k`, and every
    /// slice must refute (all slices of an unsatisfiable system are
    /// unsatisfiable).
    #[test]
    fn hybrid_sweep_runs_and_every_slice_refutes() {
        let n = 8;
        let irr = choose_irreducible(n);
        let sweep = run_hybrid_sweep(
            BasisFamily::Coordinate,
            GuessPattern::Balanced,
            n,
            4,
            &irr,
            3,
            2,
            3,
            6,
            0xC0FFEE,
        )
        .expect("coordinate family is always feasible");

        assert_eq!(sweep.full_vars, 8);
        assert_eq!(sweep.rows.len(), 4);
        for w in sweep.rows.windows(2) {
            assert!(w[1].rho > w[0].rho, "rho must rise with k");
            assert_eq!(w[1].vars + 1, w[0].vars);
        }
        for r in &sweep.rows {
            assert_eq!(
                r.censored, 0,
                "every slice of an unsatisfiable system must refute by d_max"
            );
            assert!(r.dstar_mean >= 2.0);
        }
        assert!(sweep.best(2.807).is_some());
    }

    /// The guess patterns must be compared on the *same* targets: the `k = 0`
    /// row fixes no variables, so it must be bit-identical across patterns.
    /// This fails if the target and slice randomness share one stream.
    #[test]
    fn k0_row_is_pattern_independent() {
        let n = 10;
        let irr = choose_irreducible(n);
        let run = |pat: GuessPattern| {
            run_hybrid_sweep(
                BasisFamily::Coordinate,
                pat,
                n,
                5,
                &irr,
                4,
                3,
                4,
                6,
                0xA11CE,
            )
            .unwrap()
            .rows[0]
                .clone()
        };
        let a = run(GuessPattern::Balanced);
        let b = run(GuessPattern::OneSide);
        let c = run(GuessPattern::Spread);
        assert_eq!(a.dstar_hist, b.dstar_hist, "balanced vs one-side at k=0");
        assert_eq!(a.dstar_hist, c.dstar_hist, "balanced vs spread at k=0");
        assert_eq!(a.dstar_max, c.dstar_max);
    }

    /// The enumeration baseline must dominate the degenerate `k = N` endpoint
    /// of the hybrid family: guessing every variable *is* enumeration, so a
    /// cost model that lets the hybrid beat `2^N` there is mis-specified.
    #[test]
    fn enumeration_baseline_bounds_the_full_guess_endpoint() {
        let (n_vars, eqs) = (14u32, 14u32);
        let base = log2_enumeration_cost(n_vars, eqs);
        // k = N leaves 0 free variables: cols(0, D) = 1, so the slice cost is
        // 1 and the total is exactly 2^N — strictly below the baseline, which
        // also charges `eqs` work per point.
        let full_guess = HybridRow {
            k: n_vars,
            vars: 0,
            eqs,
            rho: f64::INFINITY,
            slices: 1,
            censored: 0,
            dstar_mean: 2.0,
            dstar_max: 2,
            dstar_hist: BTreeMap::from([(2, 1)]),
            delta_low_mean: 0.0,
            first_fall_mean: 2.0,
        };
        assert!(
            full_guess.log2_total_cost(2.807) <= base,
            "baseline must be at least the full-guess endpoint"
        );
        assert!((full_guess.log2_total_cost(2.807) - n_vars as f64).abs() < 1e-9);
    }

    /// `collapse_fraction` must report the first `k` whose slices are all at
    /// the degree-2 floor, normalised by `N`.
    #[test]
    fn collapse_fraction_finds_the_floor() {
        let n = 10;
        let irr = choose_irreducible(n);
        let sweep = run_hybrid_sweep(
            BasisFamily::Coordinate,
            GuessPattern::OneSide,
            n,
            5,
            &irr,
            8,
            3,
            4,
            6,
            0xFEED,
        )
        .unwrap();
        let c = sweep
            .collapse_fraction()
            .expect("floor is reached by k=N-2");
        assert!(
            (0.0..=1.0).contains(&c),
            "collapse fraction out of range: {c}"
        );
        let k = (c * sweep.full_vars as f64).round() as u32;
        assert!(sweep.rows[k as usize].dstar_max <= 2);
        if k > 0 {
            assert!(
                sweep.rows[(k - 1) as usize].dstar_max > 2,
                "collapse_fraction must return the FIRST collapsed k"
            );
        }
    }

    /// The boundary check must actually fire: on a toy system the cost model
    /// slides the optimum to the largest `k` scanned (exhaustive search), and
    /// `optimum_is_interior` must report that rather than let the sweep claim
    /// a saving it did not find.
    #[test]
    fn boundary_optimum_is_reported_as_non_interior() {
        let n = 12;
        let irr = choose_irreducible(n);
        let sweep = run_hybrid_sweep(
            BasisFamily::Coordinate,
            GuessPattern::Balanced,
            n,
            6,
            &irr,
            10,
            2,
            3,
            6,
            0xB0A11,
        )
        .unwrap();
        let (k_star, _) = sweep.best(2.807).unwrap();
        assert_eq!(
            sweep.optimum_is_interior(2.807),
            k_star < sweep.k_max(),
            "interior flag must agree with the optimum's position"
        );
    }

    /// A cell whose unsliced system is already at the degree-2 floor has no
    /// collapse to measure, so `collapse_fraction` must decline to report one
    /// rather than return a degenerate 0.
    #[test]
    fn collapse_fraction_declines_when_already_at_the_floor() {
        // Heavily over-determined: rho = 10/4, so D* = 2 from the start (P6).
        let n = 10;
        let irr = choose_irreducible(n);
        let sweep = run_hybrid_sweep(
            BasisFamily::Coordinate,
            GuessPattern::Balanced,
            n,
            2,
            &irr,
            2,
            2,
            2,
            6,
            0x1234,
        )
        .unwrap();
        assert_eq!(
            sweep.rows[0].dstar_max, 2,
            "expected the P6 floor at rho=2.5"
        );
        assert!(
            sweep.collapse_fraction().is_none(),
            "no collapse to report when k=0 is already at the floor"
        );
    }

    // ── Lever L4: degree falls ──────────────────────────────────────

    /// **The load-bearing correctness test for L4.** Every extracted degree
    /// fall must lie in the ideal, so it must vanish at every common zero of
    /// the system. Checked by brute force on a satisfiable instance: if the
    /// extraction were wrong — a mis-indexed monomial, a botched provenance
    /// XOR — it would manufacture polynomials outside the ideal and this
    /// would catch it.
    #[test]
    fn degree_falls_vanish_on_every_solution() {
        let n = 6;
        let irr = choose_irreducible(n);
        let v = FactorSubspace::build(BasisFamily::Coordinate, n, 3, &irr, 0).unwrap();
        let nvars = 6u32;

        let mut checked_any = false;
        for bb in 1u32..8 {
            for xx in 1u32..8 {
                let b = F2mElement::from_bit_positions(
                    &(0..n).filter(|i| (bb >> i) & 1 == 1).collect::<Vec<_>>(),
                    n,
                );
                let x3 = F2mElement::from_bit_positions(
                    &(0..n).filter(|i| (xx >> i) & 1 == 1).collect::<Vec<_>>(),
                    n,
                );
                if b.is_zero() || x3.is_zero() {
                    continue;
                }
                let eqs = descend_on_subspace(n, &v, &irr, &b, &x3);
                let report = extract_degree_falls(&eqs, nvars);
                if report.new_generators.is_empty() {
                    continue;
                }
                // All common zeros of the original system.
                for mask in 0u32..(1 << nvars) {
                    let x: Vec<bool> = (0..nvars).map(|i| (mask >> i) & 1 == 1).collect();
                    if !eqs.iter().all(|f| !eval_bool(f, nvars, &x)) {
                        continue;
                    }
                    checked_any = true;
                    for g in &report.new_generators {
                        assert!(
                            !eval_bool(g, nvars, &x),
                            "extracted fall does not vanish at a solution of the system"
                        );
                    }
                }
            }
        }
        assert!(
            checked_any,
            "test vacuous: no satisfiable instance with falls was found"
        );
    }

    /// The cancellation space must split exactly into pure syzygies (nothing
    /// gained) and genuine falls (a new lower-degree polynomial). The whole
    /// point of L4 is that these are different populations.
    #[test]
    fn cancellation_space_splits_into_syzygies_and_falls() {
        let n = 10;
        let irr = choose_irreducible(n);
        let v = FactorSubspace::build(BasisFamily::Coordinate, n, 5, &irr, 0).unwrap();
        let b = F2mElement::from_bit_positions(&[0, 3], n);
        let x3 = F2mElement::from_bit_positions(&[1, 4], n);
        let eqs = descend_on_subspace(n, &v, &irr, &b, &x3);
        let r = extract_degree_falls(&eqs, 10);
        assert_eq!(
            r.cancel_dim,
            r.pure_syzygies + r.falls,
            "every cancellation is either a pure syzygy or a fall"
        );
        assert!(r.new_generators.len() <= r.falls);
        assert_eq!(r.rows, eqs.len() * 10);
    }

    /// New generators must be linearly independent of the original equations
    /// and of each other — a "fall" already in the span is a generator the
    /// solver has, and counting it would inflate the lever's apparent value.
    #[test]
    fn new_generators_are_independent_of_the_originals() {
        let n = 10;
        let irr = choose_irreducible(n);
        let v = FactorSubspace::build(BasisFamily::Coordinate, n, 5, &irr, 0).unwrap();
        let b = F2mElement::from_bit_positions(&[2], n);
        let x3 = F2mElement::from_bit_positions(&[0, 1], n);
        let eqs = descend_on_subspace(n, &v, &irr, &b, &x3);
        let r = extract_degree_falls(&eqs, 10);
        // Re-derive independence from scratch: the rank of (eqs ++ new) must
        // be exactly len(eqs-rank) + len(new).
        let rank_of = |set: &[F2BoolPoly]| -> usize {
            let mut basis: Vec<(usize, Vec<u64>)> = Vec::new();
            let mut rank = 0;
            for f in set {
                let mut v: Vec<u64> = vec![0; f.coeffs.len().div_ceil(64)];
                for (i, c) in f.coeffs.iter().enumerate() {
                    if *c {
                        v[i / 64] ^= 1u64 << (i % 64);
                    }
                }
                while let Some(l) = v
                    .iter()
                    .enumerate()
                    .find(|(_, w)| **w != 0)
                    .map(|(i, w)| i * 64 + w.trailing_zeros() as usize)
                {
                    match basis.iter().find(|(bl, _)| *bl == l) {
                        Some((_, bv)) => {
                            for w in 0..v.len() {
                                v[w] ^= bv[w];
                            }
                        }
                        None => {
                            basis.push((l, v.clone()));
                            rank += 1;
                            break;
                        }
                    }
                }
            }
            rank
        };
        let base = rank_of(&eqs);
        let mut both = eqs.clone();
        both.extend(r.new_generators.iter().cloned());
        assert_eq!(
            rank_of(&both),
            base + r.new_generators.len(),
            "new generators must add exactly their own count to the rank"
        );
    }

    /// Adding elements of the ideal can only help: `D*` must never rise.
    /// This is the invariant that makes the L4 measurement trustworthy.
    #[test]
    fn augmenting_with_falls_never_raises_dstar() {
        let n = 10;
        let irr = choose_irreducible(n);
        let cell = run_mutant_cell(BasisFamily::Coordinate, n, 5, &irr, 4, 7, 4, 0x1D0A)
            .expect("coordinate family is feasible");
        assert_eq!(
            cell.worsened, 0,
            "augmenting with ideal elements raised D* — the extraction is unsound"
        );
        assert!(cell.dstar_aug_mean <= cell.dstar_base_mean + 1e-9);
    }

    /// Saturation must terminate: either it runs out of new generators (a
    /// trailing zero round) or it stops at the cap, and it must never shrink
    /// the system.
    #[test]
    fn saturation_terminates_and_only_grows_the_system() {
        let n = 10;
        let irr = choose_irreducible(n);
        let v = FactorSubspace::build(BasisFamily::Coordinate, n, 5, &irr, 0).unwrap();
        let b = F2mElement::from_bit_positions(&[1, 2], n);
        let x3 = F2mElement::from_bit_positions(&[3], n);
        let eqs = descend_on_subspace(n, &v, &irr, &b, &x3);
        let cap = 5;
        let (sat, per_round) = saturate_with_falls(&eqs, 10, cap);
        assert!(sat.len() >= eqs.len());
        assert_eq!(sat.len(), eqs.len() + per_round.iter().sum::<usize>());
        assert!(per_round.len() <= cap as usize);
        if (per_round.len() as u32) < cap {
            assert_eq!(
                *per_round.last().unwrap(),
                0,
                "early stop only when a round yields nothing"
            );
        }
    }

    // ── R5: composition ─────────────────────────────────────────────

    /// On every slice the mutant route sees the *same* system as the raw
    /// route plus extra ideal elements, so its `D*` can never be higher.
    /// This is the invariant that makes the matched comparison meaningful.
    #[test]
    fn composed_mutant_never_above_raw_on_the_same_slices() {
        let n = 10;
        let irr = choose_irreducible(n);
        let sw = run_composed_sweep(
            BasisFamily::Coordinate,
            GuessPattern::OneSide,
            n,
            5,
            &irr,
            5,
            3,
            3,
            7,
            3,
            0xC0DE,
        )
        .unwrap();
        for r in &sw.rows {
            assert!(
                r.mut_dstar_mean <= r.raw_dstar_mean + 1e-9,
                "k={}: mutant D* {} above raw {}",
                r.k,
                r.mut_dstar_mean,
                r.raw_dstar_mean
            );
            assert!(r.mut_dstar_max <= r.raw_dstar_max);
        }
    }

    /// The mutant route can only reach the degree-2 floor at the same `k` or
    /// earlier than the raw route, so its collapse fraction must not exceed
    /// the raw one.
    #[test]
    fn composed_collapse_fraction_is_at_most_the_raw_one() {
        let n = 10;
        let irr = choose_irreducible(n);
        let sw = run_composed_sweep(
            BasisFamily::Random,
            GuessPattern::OneSide,
            n,
            5,
            &irr,
            8,
            3,
            3,
            7,
            3,
            0xFACE,
        )
        .unwrap();
        if let (Some(raw), Some(mutant)) =
            (sw.raw_collapse_fraction(), sw.mutant_collapse_fraction())
        {
            assert!(
                mutant <= raw + 1e-9,
                "mutant collapse {mutant} later than raw {raw}"
            );
        }
    }

    /// The boundary check must fire here too — the `k = N` endpoint of either
    /// route is exhaustive search, and a cost optimum sitting at the largest
    /// `k` scanned is that, not an optimum.
    #[test]
    fn composed_boundary_flag_agrees_with_the_argmin() {
        let n = 10;
        let irr = choose_irreducible(n);
        let sw = run_composed_sweep(
            BasisFamily::Coordinate,
            GuessPattern::OneSide,
            n,
            5,
            &irr,
            6,
            2,
            2,
            7,
            3,
            0x0B0E,
        )
        .unwrap();
        let argmin = sw
            .rows
            .iter()
            .min_by(|a, b| {
                a.log2_composed_total(2.807)
                    .partial_cmp(&b.log2_composed_total(2.807))
                    .unwrap()
            })
            .unwrap()
            .k;
        assert_eq!(
            sw.optimum_is_interior(|r| r.log2_composed_total(2.807)),
            argmin < sw.k_max()
        );
    }

    // ── R4': defect variants ────────────────────────────────────────

    /// Within a fixed shape every variant is a monotone transform of `Σδ`
    /// (the denominators depend only on `(vars, eqs, degree)`, which are
    /// held), so they must *rank* instances identically. This is what makes
    /// the "within-shape" column of EXP-R4′ a property of the defect rather
    /// than of the chosen normaliser — and it is why a renormalisation
    /// cannot rescue a weak within-shape signal.
    #[test]
    fn defect_variants_rank_identically_within_a_fixed_shape() {
        let n = 10;
        let irr = choose_irreducible(n);
        let cells = collect_defect_cells(
            n,
            5,
            &irr,
            &[BasisFamily::Coordinate, BasisFamily::Random],
            &[],
            6,
            7,
            3,
            0x5A17,
        );
        let ws: Vec<&DefectCell> = cells.iter().filter(|c| c.group == "within-shape").collect();
        assert!(ws.len() >= 3, "need a few cells to compare rankings");
        assert!(ws.iter().all(|c| c.vars == ws[0].vars));

        let order = |i: usize| -> Vec<usize> {
            let mut idx: Vec<usize> = (0..ws.len()).collect();
            idx.sort_by(|&a, &b| {
                ws[a].defects[i]
                    .partial_cmp(&ws[b].defects[i])
                    .unwrap()
                    .then(a.cmp(&b))
            });
            idx
        };
        let base = order(0);
        for i in 1..DEFECT_VARIANTS.len() {
            assert_eq!(
                order(i),
                base,
                "{} ranks instances differently from {} at fixed shape",
                DEFECT_VARIANTS[i].label(),
                DEFECT_VARIANTS[0].label()
            );
        }
    }

    /// Every variant is a sum of non-negative terms (`δ ≥ 0` by
    /// construction), so none may go negative.
    #[test]
    fn defect_variant_values_are_non_negative() {
        let n = 10;
        let irr = choose_irreducible(n);
        let cells =
            collect_defect_cells(n, 5, &irr, &[BasisFamily::Random], &[2, 4], 4, 7, 3, 0xD1FF);
        assert!(!cells.is_empty());
        for c in &cells {
            for (i, d) in c.defects.iter().enumerate() {
                assert!(
                    *d >= 0.0 && d.is_finite(),
                    "{} produced {d} at vars={}",
                    DEFECT_VARIANTS[i].label(),
                    c.vars
                );
            }
        }
    }

    /// Group labelling and bookkeeping: `k = 0` cells are the fixed-shape
    /// group at full width, sliced cells are the `ρ`-varying group and are
    /// strictly narrower, and `ρ` must agree with `eqs / vars`.
    #[test]
    fn defect_cells_are_labelled_and_measured_consistently() {
        let n = 12;
        let irr = choose_irreducible(n);
        let cells = collect_defect_cells(
            n,
            6,
            &irr,
            &[BasisFamily::Coordinate],
            &[2, 4],
            3,
            7,
            3,
            0x7A66,
        );
        assert!(cells.iter().any(|c| c.group == "within-shape"));
        assert!(cells.iter().any(|c| c.group == "rho-varies"));
        for c in &cells {
            assert_eq!(c.eqs, n);
            assert!((c.rho - c.eqs as f64 / c.vars as f64).abs() < 1e-9);
            assert!(c.dstar >= 2);
            match c.group {
                "within-shape" => assert_eq!(c.vars, 12),
                "rho-varies" => assert!(c.vars < 12, "a slice must be narrower"),
                other => panic!("unexpected group {other}"),
            }
        }
    }

    /// The load-bearing claim of the whole lever: raising the determination
    /// ratio must not *raise* `D*`. Slicing can only add constraints, so the
    /// worst-case degree must be monotone non-increasing in `k`.
    #[test]
    fn slicing_does_not_raise_the_mean_solving_degree() {
        let n = 10;
        let irr = choose_irreducible(n);
        let sweep = run_hybrid_sweep(
            BasisFamily::Coordinate,
            GuessPattern::Balanced,
            n,
            5,
            &irr,
            4,
            3,
            4,
            6,
            0x5EED,
        )
        .unwrap();
        let first = sweep.rows.first().unwrap().dstar_mean;
        let last = sweep.rows.last().unwrap().dstar_mean;
        assert!(
            last <= first + 1e-9,
            "mean D* rose under slicing: {first} → {last}"
        );
    }

    // ── Per-degree defect profile (EXP-R6) ──────────────────────────

    /// The cumulative readings must be consistent with the per-degree ones
    /// and with each other: `Δ_low` at a higher cutoff sums strictly more
    /// degrees, so a nonzero defect appearing at degree `D` cannot leave
    /// the cutoff-`D` reading below the cutoff-`(D−1)` one once both are
    /// put over the same denominator.
    ///
    /// Pinned because EXP-R6's whole argument is a comparison *across*
    /// cutoffs, and a reading that silently disagreed with its own
    /// per-degree parts would make that comparison meaningless.
    #[test]
    fn defect_profile_readings_are_consistent() {
        let irr = choose_irreducible(10);
        let rows = run_defect_profile_cell(BasisFamily::Coordinate, 10, 5, &irr, 6, 7, 7);
        assert!(!rows.is_empty(), "need measurable targets");
        for r in &rows {
            for (i, v) in r.readings().iter().enumerate() {
                assert!(
                    v.is_finite() && *v >= 0.0,
                    "reading {i} must be a non-negative finite fraction, got {v}"
                );
            }
            // A degree with no defect contributes nothing, so the cutoff-2
            // reading is exactly `δ(2)` — the screen's statistic at its
            // lowest cutoff is a single per-degree fraction, not a sum.
            assert!(
                (r.cumulative[0] - r.per_degree[0]).abs() < 1e-12,
                "cutoff-2 Delta_low should equal delta(2): {} vs {}",
                r.cumulative[0],
                r.per_degree[0]
            );
            assert!(r.dstar >= 2, "D* is at least the Nullstellensatz floor");
            assert_eq!(r.full_vars, 10, "cell reports its own variable count");
        }
    }

    /// A target that refutes at `D* = 2` should carry (near-)zero defect at
    /// degree 2 — the mechanism behind R4e/R6. Asserted as a *tendency* over
    /// a cell rather than per target, because it is a statistical claim
    /// about censoring, not an identity.
    #[test]
    fn refuting_early_means_little_early_defect() {
        let irr = choose_irreducible(14);
        let rows = run_defect_profile_cell(BasisFamily::Coordinate, 14, 7, &irr, 16, 7, 7);
        let easy: Vec<f64> = rows
            .iter()
            .filter(|r| r.dstar == 2)
            .map(|r| r.per_degree[1])
            .collect();
        let hard: Vec<f64> = rows
            .iter()
            .filter(|r| r.dstar > 2)
            .map(|r| r.per_degree[1])
            .collect();
        if easy.is_empty() || hard.is_empty() {
            return; // cell had no contrast; nothing to assert
        }
        let m = |v: &[f64]| v.iter().sum::<f64>() / v.len() as f64;
        assert!(
            m(&easy) < m(&hard),
            "targets refuting at D*=2 should show LESS degree-3 defect than \
             those that do not: {} vs {}",
            m(&easy),
            m(&hard)
        );
    }

    // ── Presentation dose-response (EXP-R4d) ────────────────────────

    /// The mechanical fact EXP-R4d turns on, and the reason `Δ_low` cannot
    /// score a lever's *output*: the cutoff-3 defect **is** the space of
    /// degree-3 falls, and saturation adds precisely those as generators.
    /// So a saturated system has no degree-3 defect left — the lever's
    /// action is to consume the quantity a screen would measure.
    ///
    /// Asserted on a real descended system rather than a constructed one,
    /// because the claim is about what `saturate_with_falls` does to
    /// `early_defect`, not about arithmetic.
    #[test]
    fn saturation_consumes_the_early_defect() {
        let irr = choose_irreducible(10);
        let rows = run_presentation_cell(BasisFamily::Coordinate, 10, 5, &irr, 4, 6, 6, 7);
        assert!(!rows.is_empty(), "need at least one measurable target");
        for r in &rows {
            assert_eq!(
                r.defect[2], 0.0,
                "saturated presentation must have zero cutoff-3 defect, got {}",
                r.defect[2]
            );
            assert!(
                r.eqs[0] < r.eqs[2],
                "saturation must add generators: {} -> {}",
                r.eqs[0],
                r.eqs[2]
            );
        }
        // At least one target must have had something to consume, or the
        // test is vacuous.
        assert!(
            rows.iter().any(|r| r.defect[0] > 0.0),
            "no target had a raw defect — the assertion above proves nothing"
        );
    }

    /// The dose axis is nested: one round is a prefix of full saturation,
    /// so generator counts must be monotone and `D*` must never rise
    /// (adding ideal elements cannot make a system harder).
    #[test]
    fn presentation_dose_axis_is_monotone() {
        let irr = choose_irreducible(10);
        let rows = run_presentation_cell(BasisFamily::Random, 10, 5, &irr, 4, 6, 6, 11);
        assert!(!rows.is_empty());
        for r in &rows {
            assert!(
                r.eqs[0] <= r.eqs[1] && r.eqs[1] <= r.eqs[2],
                "generator counts must be nested: {:?}",
                r.eqs
            );
            assert!(
                r.dstar[0] >= r.dstar[1] && r.dstar[1] >= r.dstar[2],
                "D* must not rise along the dose axis: {:?}",
                r.dstar
            );
        }
    }

    // ── Size-controlled correlation (EXP-R4b) ───────────────────────

    fn obs(rows: &[(&str, f64, f64)]) -> Vec<BlockedObs> {
        rows.iter()
            .map(|&(b, x, y)| BlockedObs {
                block: b.to_string(),
                x,
                y,
            })
            .collect()
    }

    /// The construction EXP-R4b exists to detect: inside every stratum the
    /// predictor is *uncorrelated* with the response, but both rise with the
    /// stratum index. A pooled correlation reads that as a strong positive
    /// relation; all three controlled statistics must report nothing.
    #[test]
    fn pure_size_proxy_is_caught() {
        let mut rows = Vec::new();
        for (b, base) in [("s1", 0.0), ("s2", 100.0), ("s3", 200.0)] {
            // Within a block, y's ranking of x is the permutation
            // (2,4,1,3), whose rank displacements square-sum to 10 — exactly
            // the value that makes Spearman zero at n = 4. So the within-
            // block relation is *nil* by construction, while `base` makes
            // both columns climb together across blocks. That is the size-
            // proxy shape: all of the pooled signal is the stratum.
            for (dx, dy) in [(0.0, 1.0), (1.0, 3.0), (2.0, 0.0), (3.0, 2.0)] {
                rows.push((b, base + dx, base + dy));
            }
        }
        let c = size_control(&obs(&rows));
        assert_eq!(c.n_cells, 12);
        assert_eq!(c.n_blocks, 3);
        let pooled = c.pooled.expect("pooled defined");
        assert!(pooled > 0.85, "pooled must see the stratum trend: {pooled}");
        for (name, v) in [
            ("mean_per_block", c.mean_per_block),
            ("blocked_rank", c.blocked_rank),
            ("fixed_effects", c.fixed_effects),
        ] {
            let v = v.expect("controlled statistic defined");
            assert!(
                v.abs() < 1e-9,
                "{name} must not inherit the stratum trend: {v}"
            );
        }
    }

    /// The converse: a relation that holds identically inside every stratum
    /// must survive all three controls, even when the strata are offset from
    /// each other so the pooled figure is diluted.
    #[test]
    fn within_block_relation_survives_control() {
        let mut rows = Vec::new();
        for (b, off) in [("s1", 0.0), ("s2", 5.0), ("s3", 10.0)] {
            for i in 0..5 {
                let x = i as f64;
                rows.push((b, off + x, off - 2.0 * x));
            }
        }
        let c = size_control(&obs(&rows));
        for (name, v) in [
            ("mean_per_block", c.mean_per_block),
            ("blocked_rank", c.blocked_rank),
            ("fixed_effects", c.fixed_effects),
        ] {
            let v = v.expect("controlled statistic defined");
            assert!(v < -0.99, "{name} must recover the exact relation: {v}");
        }
    }

    /// Raw 1-based ranks have mean `(n_g+1)/2`. Pooling them across
    /// unequal strata injects a between-block term `Σ n_g (μ_g−μ)²` that
    /// is a function of block size — the nuisance this statistic exists
    /// to remove — and that term is non-negative, so it attenuates a
    /// negative within-stratum law. The tests above cannot catch this:
    /// they use equal-sized blocks, where the extra term is zero.
    #[test]
    fn blocked_rank_does_not_mix_unequal_stratum_sizes() {
        // Perfect negative relation, sizes 3 and 9. Unscaled ranks give
        // Pearson ≈ −0.51; after rescaling it must recover −1.
        let mut rows = Vec::new();
        for i in 0..3 {
            rows.push(("small", i as f64, -(i as f64)));
        }
        for i in 0..9 {
            rows.push(("large", i as f64, -(i as f64)));
        }
        let c = size_control(&obs(&rows));
        let br = c.blocked_rank.expect("defined");
        assert!(
            br < -0.99,
            "unequal strata must not attenuate a within-stratum law: {br}"
        );

        // The other direction: within-stratum Spearman is exactly zero
        // at n = 4 (permutation (2,4,1,3), Σd² = 10) and at n = 8
        // (permutation (7,1,5,3,6,4,8,2), Σd² = 84). Unscaled ranks
        // would report a positive blocked_rank from the mean gap alone.
        let rows = obs(&[
            ("n4", 0.0, 1.0),
            ("n4", 1.0, 3.0),
            ("n4", 2.0, 0.0),
            ("n4", 3.0, 2.0),
            ("n8", 0.0, 7.0),
            ("n8", 1.0, 1.0),
            ("n8", 2.0, 5.0),
            ("n8", 3.0, 3.0),
            ("n8", 4.0, 6.0),
            ("n8", 5.0, 4.0),
            ("n8", 6.0, 8.0),
            ("n8", 7.0, 2.0),
        ]);
        let c = size_control(&rows);
        let br = c.blocked_rank.expect("defined");
        assert!(
            br.abs() < 1e-9,
            "unequal zero-within blocks must not inherit a size term: {br}"
        );
    }

    /// Strata are held to equal weight by `mean_per_block` whatever their
    /// size, which is the reason to report it alongside the two pooled
    /// controls rather than instead of them.
    #[test]
    fn per_block_is_reported_and_sorted() {
        let rows = obs(&[
            ("b", 1.0, 1.0),
            ("b", 2.0, 2.0),
            ("b", 3.0, 3.0),
            ("a", 1.0, 3.0),
            ("a", 2.0, 2.0),
            ("a", 3.0, 1.0),
        ]);
        let c = size_control(&rows);
        let labels: Vec<&str> = c.per_block.iter().map(|(l, _, _)| l.as_str()).collect();
        assert_eq!(labels, vec!["a", "b"], "per-block output is sorted");
        assert_eq!(c.per_block[0].2, Some(-1.0));
        assert_eq!(c.per_block[1].2, Some(1.0));
        // They cancel exactly, so the mean is 0 even though each block is
        // perfectly correlated. Averaging correlations is not averaging data.
        let m = c.mean_per_block.expect("defined");
        assert!(m.abs() < 1e-12, "opposing blocks cancel: {m}");
    }

    /// A stratum with no variance in the response contributes no
    /// correlation, and must not be silently scored as zero.
    #[test]
    fn degenerate_block_is_skipped_not_zeroed() {
        let rows = obs(&[
            ("flat", 1.0, 4.0),
            ("flat", 2.0, 4.0),
            ("flat", 3.0, 4.0),
            ("live", 1.0, 3.0),
            ("live", 2.0, 2.0),
            ("live", 3.0, 1.0),
        ]);
        let c = size_control(&rows);
        assert_eq!(c.per_block[0].2, None, "flat block has no rho_s");
        assert_eq!(c.per_block[1].2, Some(-1.0));
        let m = c.mean_per_block.expect("defined from the live block alone");
        assert!(
            (m + 1.0).abs() < 1e-12,
            "a skipped block must not be averaged in as 0: {m}"
        );
    }

    /// The three controlled statistics exist so that **agreement between
    /// them** is the evidence. That only works if they agree when they
    /// should — and the `blocked_rank` bias fixed in `e16b67c` was
    /// invisible to every test here because all of them used equal-sized
    /// blocks, where the bias term is identically zero.
    ///
    /// So: unequal strata (2, 5, 11) carrying the *same* within-stratum
    /// relation, offset from each other so the pooled figure is diluted.
    /// All three controlled statistics must land on it together. A bias
    /// that is a function of block size splits them apart, which is what
    /// should have been read off the `−0.3494 / −0.1189 / −0.3248` triple
    /// rather than published.
    #[test]
    fn controlled_statistics_agree_under_unequal_strata() {
        let mut rows = Vec::new();
        for (label, n, off) in [("a", 2, 0.0), ("b", 5, 40.0), ("c", 11, 80.0)] {
            for i in 0..n {
                let x = i as f64;
                rows.push((label, off + x, off - 3.0 * x));
            }
        }
        let c = size_control(&obs(&rows));
        assert_eq!(c.n_cells, 18);
        assert_eq!(c.n_blocks, 3);
        let vals = [
            ("mean_per_block", c.mean_per_block),
            ("blocked_rank", c.blocked_rank),
            ("fixed_effects", c.fixed_effects),
        ];
        for (name, v) in vals {
            let v = v.expect("defined");
            assert!(
                v < -0.99,
                "{name} must recover the within-stratum law under unequal sizes: {v}"
            );
        }
        let spread = vals
            .iter()
            .filter_map(|(_, v)| *v)
            .fold((f64::MAX, f64::MIN), |(lo, hi), v| (lo.min(v), hi.max(v)));
        assert!(
            spread.1 - spread.0 < 1e-6,
            "the three must agree, not merely all be negative: {spread:?}"
        );
    }

    /// Too few observations to say anything: every statistic reports `None`
    /// rather than a number manufactured from 2 points.
    #[test]
    fn undersized_input_reports_nothing() {
        let c = size_control(&obs(&[("a", 1.0, 2.0), ("a", 2.0, 1.0)]));
        assert_eq!(c.pooled, None);
        assert_eq!(c.mean_per_block, None);
        assert_eq!(c.blocked_rank, None);
        assert_eq!(c.fixed_effects, None);
    }
}
