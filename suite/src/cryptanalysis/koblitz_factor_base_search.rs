//! # Algorithmic search for high-yield Frobenius-invariant factor bases.
//!
//! The Koblitz index calculus in
//! [`crate::cryptanalysis::koblitz_index_calculus`] needs, per relation
//! column, roughly one target that decomposes over the factor base.  The
//! end-to-end cost is therefore governed by two numbers of the base
//! `F`, neither of which is its size:
//!
//! - **coverage** `p_m(F)`: the fraction of nonzero points of the
//!   prime-order subgroup `⟨G⟩` that are sums of exactly `m` points of
//!   `F` — the probability that a random relation trial succeeds;
//! - **unknowns** `U(F)`: the number of relation columns, i.e. signed
//!   Frobenius orbits, optionally merged by their cofactor projection.
//!
//! The expected number of trials to collect a determining system is
//! `≈ (U + 1 + extra) / p_m`, and that ratio is what this module
//! minimises.  It does so **exactly**, not by proxy: a pair-sum table of
//! `F` ([`PairSumTable`]) lets every witness `R = P_{i_1} + … + P_{i_m}`
//! of every target be enumerated, over all of `⟨G⟩` when the subgroup is
//! small enough and over a fixed seeded sample otherwise.  Cofactor
//! classes are handled implicitly — a sum lands in `⟨G⟩` or it does not.
//!
//! Three families of candidates are searched:
//!
//! 1. the **divisor lattice** — every product of irreducible factors of
//!    `x^n − 1` within a dimension window, which is the complete list of
//!    Frobenius-stable linear subspaces (see
//!    `available_subspace_dimensions`);
//! 2. **Frobenius unions** of random small seed spaces, the nonlinear
//!    invariant sets that exist even where the linear ones do not;
//! 3. optionally the **2-torsion saturation** of either.
//!
//! Every candidate can then be **pruned**: signed orbits are removed
//! greedily while the removal lowers `(U + 1 + extra) / p_m`, i.e. while
//! the orbit costs more as an unknown than it contributes as a summand.
//! The witness list makes each step a count rather than a re-search.
//!
//! The result is a [`FactorBaseSpec`] — a small, serialisable recipe
//! that re-materialises the exact base — so the `ic` tool can run the
//! full pipeline on it and validate the choice on fresh targets.  What
//! the census measures is coverage and column count; solving cost per
//! trial is a separate axis that depends on the oracle, and the report
//! carries the standard proxies (`|F|^{m−1}` enumeration work, SAT
//! variable count) alongside so a caller can trade them off.
//!
//! **That separation costs an order of magnitude when it is left to the
//! caller.**  A trial is paid whether or not it succeeds, so collection
//! spends `(U + 1)/p_m · E[solver cost per target]`, and the second
//! factor is the one that varies: coverage saturates at 100% as the
//! subspace grows while the Gröbner oracle's system has `m·ℓ` unknowns
//! and does not.  Measured on `K_1/2^15`, `m = 2`, over 72 complete and
//! verified discrete logarithms: the base this module's `T` selects costs
//! `22.41×` the one [`SearchOptions::solve_cost_targets`] selects, and the
//! rank correlation between `T` and measured cost across the six bases is
//! `ρ = −0.83`.  See `research/notes/index-calculus/RESEARCH_FACTOR_BASE_SOLVE_COST.md` §6, and
//! `examples/groebner_base_sweep.rs` for the sweep that scores the second
//! factor directly.
//!
//! Only a linear-subspace candidate can be scored that way — the Weil
//! restriction is written over the subspace basis, so a base that is a
//! *subset* of its span is carried by the SAT domain trie instead and is
//! left unmeasured rather than priced on the span.  Free and unmeasured:
//! `ker g(σ) ⊆ ker Tr` exactly when `(x+1) ∤ g`, which doubles the yield
//! (`research/notes/ecc2k130/RESEARCH_ECC2K130_DECOMPOSITION.md` §3.1) for the price of a
//! divisibility test.

use std::collections::{BTreeMap, HashMap, HashSet};

use num_bigint::BigUint;
use num_traits::{ToPrimitive, Zero};
use rand::{rngs::StdRng, Rng, SeedableRng};
use serde::{Deserialize, Serialize};

use crate::binary_ecc::{BinaryPoint, F2mElement};

use super::koblitz_groebner::{f4_thread_word_ops, FieldStructure, SolverEngine};
use super::koblitz_index_calculus::{
    build_frobenius_factor_base, build_frobenius_factor_base_from_divisor,
    build_frobenius_union_factor_base, build_subgroup_orbit_factor_base, groebner_decompose,
    invariant_factors, projected_signed_orbit_count, restrict_factor_base_to_orbits,
    saturate_factor_base_two_torsion, span_f2, top_factor_indices, FactorBaseDomain,
    FrobeniusFactorBase, KoblitzCurve, PairSumTable,
};

// ── Specifications ─────────────────────────────────────────────────

/// A reproducible recipe for a Frobenius-invariant factor base.
///
/// Serialises to a small JSON document, e.g.
/// `{"kind":"divisor","indices":[0,2]}` or
/// `{"kind":"pruned","parent":{…},"retained_abscissa_orbits":[…]}`,
/// and re-materialises the identical base on the same curve.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum FactorBaseSpec {
    /// The legacy single-factor family: the `index`-th degree-`ord_n(2)`
    /// irreducible factor of `x^n − 1` (`ic run --factor-index`).
    Factor { index: usize },
    /// A product of irreducible factors of `x^n − 1`, by index into
    /// `all_factors_of_x_n_minus_1` (`x + 1` first).
    Divisor { indices: Vec<usize> },
    /// The union of all Frobenius translates of the span of the given
    /// seed elements (polynomial-basis bitmasks).
    FrobeniusUnion { seed_masks: Vec<u64> },
    /// The parent base closed under translation by the rational
    /// 2-torsion point `(0, 1)`.
    TwoTorsionSaturated { parent: Box<FactorBaseSpec> },
    /// Frobenius orbits of abscissae drawn pseudo-randomly from `seed`,
    /// keeping only points of the prime-order subgroup.
    ///
    /// Every other family here is linear: a subspace, a union of
    /// Frobenius translates of one, or a subset of those.  That
    /// structure is what the algebraic oracles need — Semaev's
    /// polynomials and the Weil descent are written over a subspace —
    /// but the pair-table oracle needs no structure at all, and the
    /// structure costs witnesses: a sum of three points of a subspace
    /// union lands on a given target far less often than three random
    /// points would.  Restricting to the subgroup removes the rest of
    /// the deficit, because a sum of subgroup points cannot leave the
    /// subgroup the targets live in.
    ///
    /// Membership is tested by `[r]P = O`, which needs no logarithm, so
    /// this reveals nothing about the points it selects.
    SubgroupOrbits {
        /// Seed of the abscissa sampler; the recipe is reproducible.
        seed: u64,
        /// Sampling stops once the base has at least this many points.
        points: usize,
    },
    /// The parent base restricted to the signed Frobenius orbits whose
    /// canonical (smallest) abscissa is listed.
    Pruned {
        parent: Box<FactorBaseSpec>,
        retained_abscissa_orbits: Vec<u64>,
    },
}

impl FactorBaseSpec {
    /// Short family label for reports.
    pub fn family(&self) -> &'static str {
        match self {
            Self::Factor { .. } => "factor",
            Self::Divisor { .. } => "divisor",
            Self::FrobeniusUnion { .. } => "frobenius_union",
            Self::SubgroupOrbits { .. } => "subgroup_orbits",
            Self::TwoTorsionSaturated { .. } => "two_torsion_saturated",
            Self::Pruned { .. } => "pruned",
        }
    }

    /// The innermost constructor of a pruned or saturated spec.
    pub fn root(&self) -> &FactorBaseSpec {
        match self {
            Self::TwoTorsionSaturated { parent } | Self::Pruned { parent, .. } => parent.root(),
            other => other,
        }
    }

    /// Build the base this spec names on `kc`, or explain why not.
    pub fn materialize(&self, kc: &KoblitzCurve) -> Result<FrobeniusFactorBase, String> {
        match self {
            Self::Factor { index } => build_frobenius_factor_base(kc, *index).ok_or_else(|| {
                format!(
                    "no top-degree invariant factor with index {index} on {}",
                    kc.label()
                )
            }),
            Self::Divisor { indices } => {
                let factors = invariant_factors(kc);
                let mut sorted = indices.clone();
                sorted.sort_unstable();
                sorted.dedup();
                if sorted.len() != indices.len() {
                    return Err("divisor indices must be distinct".into());
                }
                if sorted.iter().any(|&i| i >= factors.len()) {
                    return Err(format!(
                        "divisor index out of range: x^{} − 1 has {} irreducible factors over GF(2^{})",
                        kc.extension_degree(),
                        factors.len(),
                        kc.k
                    ));
                }
                build_frobenius_factor_base_from_divisor(kc, &sorted)
                    .ok_or_else(|| "divisor does not define a proper invariant subspace".into())
            }
            Self::FrobeniusUnion { seed_masks } => {
                if seed_masks.is_empty() || seed_masks.len() > 12 {
                    return Err("union seeds must number 1..=12".into());
                }
                if kc.n < 64 && seed_masks.iter().any(|&m| m >= 1u64 << kc.n) {
                    return Err("union seed mask exceeds the field width".into());
                }
                let basis: Vec<F2mElement> = seed_masks
                    .iter()
                    .map(|&m| F2mElement::from_biguint(&BigUint::from(m), kc.n))
                    .collect();
                build_frobenius_union_factor_base(kc, &basis)
                    .ok_or_else(|| "seed masks are linearly dependent or unusable".into())
            }
            Self::SubgroupOrbits { seed, points } => {
                build_subgroup_orbit_factor_base(kc, *seed, *points)
            }
            Self::TwoTorsionSaturated { parent } => {
                let inner = parent.materialize(kc)?;
                saturate_factor_base_two_torsion(kc, &inner)
                    .ok_or_else(|| "2-torsion saturation needs an even cofactor".into())
            }
            Self::Pruned {
                parent,
                retained_abscissa_orbits,
            } => {
                let inner = parent.materialize(kc)?;
                let reps = inner.signed_orbit_abscissa_representatives();
                let by_rep: HashMap<u64, usize> = reps
                    .iter()
                    .enumerate()
                    .filter_map(|(o, x)| x.to_u64().map(|x| (x, o)))
                    .collect();
                let mut keep = Vec::with_capacity(retained_abscissa_orbits.len());
                for x in retained_abscissa_orbits {
                    let o = by_rep.get(x).ok_or_else(|| {
                        format!(
                            "abscissa {x} is not a signed-orbit representative of the parent base"
                        )
                    })?;
                    keep.push(*o);
                }
                keep.sort_unstable();
                keep.dedup();
                restrict_factor_base_to_orbits(kc, &inner, &keep)
                    .ok_or_else(|| "orbit restriction produced no base".into())
            }
        }
    }
}

/// Human-readable domain label.
pub fn domain_label(domain: &FactorBaseDomain) -> String {
    match domain {
        FactorBaseDomain::LinearSubspace => "linear_subspace".into(),
        FactorBaseDomain::SubspaceSubset { retained_orbits } => {
            format!("subspace_subset({retained_orbits} orbits)")
        }
        FactorBaseDomain::FrobeniusUnion { seed_dimension } => {
            format!("frobenius_union(seed dim {seed_dimension})")
        }
        FactorBaseDomain::ExplicitFrobeniusOrbits { representatives } => {
            format!("explicit_orbits({representatives})")
        }
        FactorBaseDomain::TwoTorsionSaturation => "two_torsion_saturation".into(),
    }
}

// ── Targets ────────────────────────────────────────────────────────

/// The subgroup points a census is evaluated on: all of `⟨G⟩ \ {O}`
/// when it is small enough, otherwise a seeded sample without
/// replacement.  Every candidate in one search sees the same set.
#[derive(Clone, Debug)]
pub struct TargetSet {
    pub points: Vec<BinaryPoint>,
    pub scalars: Vec<u64>,
    pub exhaustive: bool,
}

impl TargetSet {
    /// Exhaustive when `r − 1 ≤ exhaustive_cap`, else `sample` targets.
    pub fn new(kc: &KoblitzCurve, sample: usize, exhaustive_cap: u64, seed: u64) -> Self {
        let r = kc.subgroup_order.to_u64().unwrap_or(u64::MAX);
        let g = kc.generator();
        let (scalars, exhaustive) = if r - 1 <= exhaustive_cap {
            ((1..r).collect::<Vec<_>>(), true)
        } else {
            let mut rng = StdRng::seed_from_u64(seed ^ 0x5441_5247_4554_5300);
            let mut seen = HashSet::new();
            let mut out = Vec::with_capacity(sample);
            while out.len() < sample.min((r - 1) as usize) {
                let k = rng.gen_range(1..r);
                if seen.insert(k) {
                    out.push(k);
                }
            }
            (out, false)
        };
        let points = scalars
            .iter()
            .map(|&k| kc.mul(g, &BigUint::from(k)))
            .collect();
        Self {
            points,
            scalars,
            exhaustive,
        }
    }

    pub fn len(&self) -> usize {
        self.points.len()
    }

    pub fn is_empty(&self) -> bool {
        self.points.is_empty()
    }
}

// ── Exact yield census ─────────────────────────────────────────────

/// One decomposition of one target, recorded by the signed orbits it
/// uses (sorted, deduplicated) — all the pruning step needs.
#[derive(Clone, Debug)]
pub struct Witness {
    pub target: u32,
    pub orbits: Vec<u32>,
}

/// Enumerate every sorted `m`-summand witness of every target.
pub fn witness_list(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    table: &PairSumTable,
    targets: &TargetSet,
    m: usize,
) -> Vec<Witness> {
    let mut out = Vec::new();
    for (t, target) in targets.points.iter().enumerate() {
        table.witnesses(kc, fb, target, m, &mut |idxs| {
            let mut orbits: Vec<u32> = idxs
                .iter()
                .map(|&i| fb.signed_orbit_of[i].0 as u32)
                .collect();
            orbits.sort_unstable();
            orbits.dedup();
            out.push(Witness {
                target: t as u32,
                orbits,
            });
            true
        });
    }
    out
}

/// Exact relation-yield statistics of a factor base on a target set.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct YieldCensus {
    /// Summands per decomposition.
    pub m: usize,
    /// Targets evaluated.
    pub targets: usize,
    /// Whether the targets are all of `⟨G⟩ \ {O}`.
    pub exhaustive: bool,
    /// Targets with at least one witness.
    pub covered: usize,
    /// `covered / targets` — the per-trial relation probability.
    pub coverage: f64,
    /// Witnesses over all targets (sorted tuples, multiplicity kept).
    pub witnesses: usize,
    /// `witnesses / targets`.
    pub mean_witnesses: f64,
    /// Witnesses touching each signed orbit.
    pub orbit_witnesses: Vec<usize>,
    /// Relation columns the pipeline will solve for.
    pub unknowns: usize,
    /// Surplus relations assumed for rank.
    pub extra_relations: usize,
    /// `(unknowns + 1 + extra) / coverage`; infinite when nothing
    /// decomposes.  The number this module minimises.
    pub expected_trials: f64,
    /// Wall time of the census, table included.
    pub census_ms: f64,
}

/// Expected trials to collect `unknowns + 1 + extra` relations.
pub fn expected_trials(unknowns: usize, extra: usize, covered: usize, targets: usize) -> f64 {
    if covered == 0 || targets == 0 {
        f64::INFINITY
    } else {
        (unknowns + 1 + extra) as f64 * targets as f64 / covered as f64
    }
}

/// Summarise a witness list.
pub fn census_from_witnesses(
    witnesses: &[Witness],
    targets: &TargetSet,
    m: usize,
    signed_orbits: usize,
    unknowns: usize,
    extra_relations: usize,
    census_ms: f64,
) -> YieldCensus {
    let mut covered_set = vec![false; targets.len()];
    let mut orbit_witnesses = vec![0usize; signed_orbits];
    for w in witnesses {
        covered_set[w.target as usize] = true;
        for &o in &w.orbits {
            orbit_witnesses[o as usize] += 1;
        }
    }
    let covered = covered_set.iter().filter(|&&c| c).count();
    YieldCensus {
        m,
        targets: targets.len(),
        exhaustive: targets.exhaustive,
        covered,
        coverage: if targets.is_empty() {
            0.0
        } else {
            covered as f64 / targets.len() as f64
        },
        witnesses: witnesses.len(),
        mean_witnesses: if targets.is_empty() {
            0.0
        } else {
            witnesses.len() as f64 / targets.len() as f64
        },
        orbit_witnesses,
        unknowns,
        extra_relations,
        expected_trials: expected_trials(unknowns, extra_relations, covered, targets.len()),
        census_ms,
    }
}

// ── Greedy orbit pruning ───────────────────────────────────────────

/// One accepted pruning step.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PruneStep {
    /// Signed orbit removed (index in the parent base).
    pub removed_orbit: usize,
    /// Its canonical abscissa.
    pub removed_abscissa: u64,
    pub covered_before: usize,
    pub covered_after: usize,
    pub unknowns_after: usize,
    pub expected_trials_after: f64,
}

/// Greedily drop signed orbits while doing so lowers the expected trial
/// count.  Returns the retained orbit indices and the accepted steps.
///
/// The score of a base with `U` columns covering `c` of `T` targets is
/// `(U + 1 + extra)·T / c`.  Dropping orbit `o` loses exactly the
/// targets all of whose witnesses use `o`; that is a count over the
/// witness list, so each step is `O(U · |witnesses|)` and exact.
pub fn greedy_prune(
    fb: &FrobeniusFactorBase,
    witnesses: &[Witness],
    targets: usize,
    extra_relations: usize,
    min_orbits: usize,
) -> (Vec<usize>, Vec<PruneStep>) {
    let reps = fb.signed_orbit_abscissa_representatives();
    let mut retained: Vec<bool> = vec![true; fb.signed_orbits.len()];
    let mut alive: Vec<bool> = vec![true; witnesses.len()];
    let mut steps = Vec::new();
    let covered_by = |alive: &[bool], skip: Option<usize>| -> usize {
        let mut seen = vec![false; targets];
        for (w, witness) in witnesses.iter().enumerate() {
            if !alive[w] {
                continue;
            }
            if let Some(o) = skip {
                if witness.orbits.iter().any(|&x| x as usize == o) {
                    continue;
                }
            }
            seen[witness.target as usize] = true;
        }
        seen.iter().filter(|&&c| c).count()
    };
    let mut unknowns = fb.signed_orbits.len();
    let mut covered = covered_by(&alive, None);
    let mut score = expected_trials(unknowns, extra_relations, covered, targets);
    while unknowns > min_orbits.max(1) {
        let mut best: Option<(usize, usize, f64)> = None;
        for o in 0..fb.signed_orbits.len() {
            if !retained[o] {
                continue;
            }
            let c = covered_by(&alive, Some(o));
            if c == 0 {
                continue;
            }
            let s = expected_trials(unknowns - 1, extra_relations, c, targets);
            if s < score * (1.0 - 1e-12) && best.is_none_or(|(_, _, bs)| s < bs) {
                best = Some((o, c, s));
            }
        }
        let Some((o, c, s)) = best else { break };
        retained[o] = false;
        for (w, witness) in witnesses.iter().enumerate() {
            if alive[w] && witness.orbits.iter().any(|&x| x as usize == o) {
                alive[w] = false;
            }
        }
        steps.push(PruneStep {
            removed_orbit: o,
            removed_abscissa: reps[o].to_u64().unwrap_or(u64::MAX),
            covered_before: covered,
            covered_after: c,
            unknowns_after: unknowns - 1,
            expected_trials_after: s,
        });
        unknowns -= 1;
        covered = c;
        score = s;
    }
    let keep: Vec<usize> = (0..fb.signed_orbits.len())
        .filter(|&o| retained[o])
        .collect();
    (keep, steps)
}

// ── Search ─────────────────────────────────────────────────────────

/// Candidate families.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Family {
    /// Single degree-`ord_n(2)` factors (the legacy `factor_index`).
    Factor,
    /// Every divisor of `x^n − 1` in the dimension window.
    Divisor,
    /// Frobenius unions of random seed spaces.
    Union,
    /// Frobenius orbits sampled from the prime-order subgroup.  Carries
    /// no linear structure, so only the pair-table oracle can use it —
    /// and it is the family that decomposes targets most often.
    Subgroup,
}

/// Search controls.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SearchOptions {
    /// Summands per decomposition (2, 3 or 4).
    pub m: usize,
    /// Smallest subspace dimension considered for divisors.
    pub min_dimension: u32,
    /// Largest subspace dimension considered for divisors.
    pub max_dimension: u32,
    /// Skip any candidate with more abscissae than this (materialisation
    /// and `|F|²` pair-table guard).
    pub max_abscissae: usize,
    pub families: Vec<Family>,
    /// Seed-space dimensions for the union family, inclusive.
    pub union_seed_dimensions: (u32, u32),
    /// Random seed spaces per dimension (the standard basis is always
    /// included as well).
    pub union_samples: usize,
    /// Sampled targets when the subgroup is too large to enumerate.
    pub sample_targets: usize,
    /// Enumerate all of `⟨G⟩ \ {O}` when `r − 1` is at most this.
    pub exhaustive_cap: u64,
    /// Surplus relations assumed when scoring.
    pub extra_relations: usize,
    /// Greedily prune orbits of every candidate.
    pub prune: bool,
    /// Also try the 2-torsion saturation of every candidate.
    pub saturate: bool,
    /// Count columns after cofactor projection (as the pipeline does
    /// with `collapse_projected_orbits`) rather than raw signed orbits.
    pub projected_columns: bool,
    /// Seed for target sampling and union seeds.
    pub seed: u64,
    /// Measure the algebraic solver on this many of the census targets
    /// per candidate, and rank by the resulting
    /// [`Candidate::expected_stage_ops`] instead of by expected trials.
    ///
    /// `None` keeps the historical trials-only ranking, so every earlier
    /// measurement means what it did.  A trial is paid whether or not it
    /// succeeds and the Gröbner system carries `m·ℓ` unknowns, so the
    /// two orders can differ by an order of magnitude — see
    /// `research/notes/index-calculus/RESEARCH_FACTOR_BASE_SOLVE_COST.md`.
    ///
    /// Only linear-subspace candidates can be priced: the summation
    /// polynomial is Weil-restricted over the subspace basis, so a base
    /// that is a subset of that span (pruned, saturated, union, orbit)
    /// is left unmeasured and ranked below the measured ones.  Pair it
    /// with `prune: false`, `saturate: false` and the divisor or factor
    /// family to score every candidate the same way.  Nothing is measured
    /// at all while `IC_REDUCTION_CACHE` is set, since a replayed
    /// reduction returns without running F4 and so reports as free.
    pub solve_cost_targets: Option<usize>,
}

impl Default for SearchOptions {
    fn default() -> Self {
        Self {
            m: 2,
            min_dimension: 3,
            max_dimension: 10,
            max_abscissae: 2048,
            families: vec![
                Family::Factor,
                Family::Divisor,
                Family::Union,
                Family::Subgroup,
            ],
            union_seed_dimensions: (2, 5),
            union_samples: 3,
            sample_targets: 1024,
            exhaustive_cap: 4096,
            extra_relations: 2,
            prune: true,
            saturate: true,
            projected_columns: true,
            seed: 0x4641_4354_4f52_4241, // "FACTORBA"
            solve_cost_targets: None,
        }
    }
}

/// A scored candidate.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Candidate {
    pub spec: FactorBaseSpec,
    pub family: String,
    pub domain: String,
    /// Ambient coordinate dimension (`ℓ`, or `n` for nonlinear sets).
    pub dimension: u32,
    pub abscissae: usize,
    pub points: usize,
    pub signed_orbits: usize,
    pub projected_columns: usize,
    /// Columns used for scoring.
    pub unknowns: usize,
    pub cofactor_admissible: bool,
    pub census: Option<YieldCensus>,
    /// `|F|^{m−1}` — enumeration group operations per trial.
    pub enumeration_ops_per_trial: f64,
    /// `|F|^{m−2}` — pair-table lookups per trial.
    pub pair_table_lookups_per_trial: f64,
    /// `m·dim + (m − 2)·n` — Boolean unknowns of the algebraic system.
    pub sat_variables: usize,
    /// Whether the abscissa subspace lies inside `ker Tr`, which doubles
    /// the yield (`research/notes/ecc2k130/RESEARCH_ECC2K130_DECOMPOSITION.md` §3.1).  Decided
    /// by a divisibility, not by solving: `ker g(σ) ⊆ ker Tr` exactly
    /// when `(x+1) ∤ g`, and equivalently every abscissa has trace zero.
    pub trace_zero: bool,
    /// Mean 64-bit word XORs the Gröbner oracle spent per target, over
    /// `solve_cost_targets` targets, decomposing and refuted alike.
    /// `None` when the measurement was not asked for.
    pub measured_ops_per_target: Option<f64>,
    /// `expected_trials × measured_ops_per_target` — the word XORs the
    /// decomposition stage is expected to spend collecting one
    /// determining system over this base.
    pub expected_stage_ops: Option<f64>,
    /// Why the solve cost was not measured, when it was asked for.
    /// A base whose points are a *subset* of the space its Weil
    /// restriction is written over cannot be priced this way — see
    /// `measure_solve_cost`.
    pub solve_cost_skipped: Option<String>,
    pub build_ms: f64,
    pub prune_steps: Vec<PruneStep>,
    /// Why the candidate was not scored, if it was not.
    pub skipped: Option<String>,
}

impl Candidate {
    /// Expected trials, infinite when unscored or uncovered.
    pub fn expected_trials(&self) -> f64 {
        self.census
            .as_ref()
            .map_or(f64::INFINITY, |c| c.expected_trials)
    }

    /// The quantity to minimise: measured stage cost where it was
    /// measured, expected trials otherwise.
    pub fn score(&self) -> f64 {
        self.expected_stage_ops
            .unwrap_or_else(|| self.expected_trials())
    }
}

/// The full search result, candidates ranked best first.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SearchReport {
    pub n: u32,
    pub a: u8,
    pub subgroup_order: String,
    pub cofactor: String,
    pub options: SearchOptions,
    pub targets: usize,
    pub exhaustive_targets: bool,
    pub candidates: Vec<Candidate>,
    pub elapsed_ms: f64,
}

impl SearchReport {
    /// Best candidate in rank order, if any decomposes anything.
    ///
    /// Scored by whichever objective [`SearchOptions::solve_cost_targets`]
    /// selected, so this is the measured-cheapest base when the solve
    /// cost was measured and the fewest-trials base when it was not.
    pub fn best(&self) -> Option<&Candidate> {
        self.candidates.iter().find(|c| c.score().is_finite())
    }
}

/// Rank measured candidates first, each group ascending by
/// [`Candidate::score`], then by the free tie-breaks.
///
/// The two scores are in different units — word XORs against trials — so
/// they are never compared to each other.  When `solve_cost_targets` was
/// not asked for, nothing is measured, every candidate is in the second
/// group and the order is exactly the historical one.  When it was, the
/// candidates the Gröbner oracle could actually be priced on
/// (`measure_solve_cost` declines the rest) rank above the ones it
/// could not, which would otherwise win on a trials count of `8` against
/// a word-XOR count of `10^6`.
///
/// A trace-zero base breaks a tie because it yields twice for nothing
/// (`research/notes/ecc2k130/RESEARCH_ECC2K130_DECOMPOSITION.md` §3.1); the remaining ties go to
/// the smaller base, which is the cheaper one to materialise and to
/// solve over.
pub fn rank_candidates(candidates: &mut [Candidate]) {
    candidates.sort_by(|x, y| {
        x.expected_stage_ops
            .is_none()
            .cmp(&y.expected_stage_ops.is_none())
            .then_with(|| x.score().total_cmp(&y.score()))
            .then(y.trace_zero.cmp(&x.trace_zero))
            .then(x.points.cmp(&y.points))
            .then(x.unknowns.cmp(&y.unknowns))
    });
}

fn unscored(spec: FactorBaseSpec, reason: String, m: usize, n: u32) -> Candidate {
    Candidate {
        family: spec.family().into(),
        spec,
        domain: String::new(),
        dimension: 0,
        abscissae: 0,
        points: 0,
        signed_orbits: 0,
        projected_columns: 0,
        unknowns: 0,
        cofactor_admissible: false,
        census: None,
        enumeration_ops_per_trial: 0.0,
        pair_table_lookups_per_trial: 0.0,
        sat_variables: m.saturating_sub(2) * n as usize,
        trace_zero: false,
        measured_ops_per_target: None,
        expected_stage_ops: None,
        solve_cost_skipped: None,
        build_ms: 0.0,
        prune_steps: Vec::new(),
        skipped: Some(reason),
    }
}

/// Score one spec on a target set.  With `prune` set, a pruned variant
/// is appended when the greedy pass removes at least one orbit.
pub fn evaluate_spec(
    kc: &KoblitzCurve,
    spec: &FactorBaseSpec,
    targets: &TargetSet,
    opts: &SearchOptions,
    prune: bool,
) -> Vec<Candidate> {
    let build_start = std::time::Instant::now();
    let fb = match spec.materialize(kc) {
        Ok(fb) => fb,
        Err(reason) => return vec![unscored(spec.clone(), reason, opts.m, kc.n)],
    };
    let build_ms = build_start.elapsed().as_secs_f64() * 1000.0;
    if fb.subspace.len() > opts.max_abscissae {
        return vec![unscored(
            spec.clone(),
            format!(
                "{} abscissae exceed the cap {}",
                fb.subspace.len(),
                opts.max_abscissae
            ),
            opts.m,
            kc.n,
        )];
    }
    let mut out = Vec::new();
    let (candidate, witnesses) =
        score_base(kc, spec.clone(), &fb, targets, opts, build_ms, Vec::new());
    let base_score = candidate.expected_trials();
    out.push(candidate);
    if prune && base_score.is_finite() {
        let (keep, steps) = greedy_prune(&fb, &witnesses, targets.len(), opts.extra_relations, 1);
        if !steps.is_empty() && keep.len() < fb.signed_orbits.len() {
            let reps = fb.signed_orbit_abscissa_representatives();
            let pruned_spec = FactorBaseSpec::Pruned {
                parent: Box::new(spec.clone()),
                retained_abscissa_orbits: keep
                    .iter()
                    .map(|&o| reps[o].to_u64().unwrap_or(u64::MAX))
                    .collect(),
            };
            let pruned_start = std::time::Instant::now();
            match pruned_spec.materialize(kc) {
                Ok(pruned_fb) => {
                    let ms = pruned_start.elapsed().as_secs_f64() * 1000.0;
                    let (c, _) = score_base(kc, pruned_spec, &pruned_fb, targets, opts, ms, steps);
                    out.push(c);
                }
                Err(reason) => out.push(unscored(pruned_spec, reason, opts.m, kc.n)),
            }
        }
    }
    out
}

fn score_base(
    kc: &KoblitzCurve,
    spec: FactorBaseSpec,
    fb: &FrobeniusFactorBase,
    targets: &TargetSet,
    opts: &SearchOptions,
    build_ms: f64,
    prune_steps: Vec<PruneStep>,
) -> (Candidate, Vec<Witness>) {
    let projected = projected_signed_orbit_count(kc, fb);
    let unknowns = if opts.projected_columns {
        projected
    } else {
        fb.signed_orbits.len()
    };
    let points = fb.points.len() as f64;
    let mut candidate = Candidate {
        family: spec.family().into(),
        spec,
        domain: domain_label(&fb.domain),
        dimension: fb.ell,
        abscissae: fb.subspace.len(),
        points: fb.points.len(),
        signed_orbits: fb.signed_orbits.len(),
        projected_columns: projected,
        unknowns,
        cofactor_admissible: false,
        census: None,
        enumeration_ops_per_trial: points.powi(opts.m as i32 - 1),
        pair_table_lookups_per_trial: points.powi(opts.m as i32 - 2),
        sat_variables: opts.m * fb.ell as usize + opts.m.saturating_sub(2) * kc.n as usize,
        trace_zero: subspace_is_trace_zero(kc, fb),
        measured_ops_per_target: None,
        expected_stage_ops: None,
        solve_cost_skipped: None,
        build_ms,
        prune_steps,
        skipped: None,
    };
    let census_start = std::time::Instant::now();
    let Some(table) = PairSumTable::build(kc, fb) else {
        candidate.skipped = Some("field too wide for the pair table".into());
        return (candidate, Vec::new());
    };
    let witnesses = witness_list(kc, fb, &table, targets, opts.m);
    let census_ms = census_start.elapsed().as_secs_f64() * 1000.0;
    // A witness proves admissibility outright; only an empty census
    // pays for the cofactor-class walk, which then tells "impossible"
    // from "unlucky sample".
    let admissible = !witnesses.is_empty() || fb.m_can_decompose(kc, opts.m);
    candidate.cofactor_admissible = admissible;
    if !admissible {
        candidate.skipped = Some(format!(
            "cofactor classes cannot cancel with {} summands",
            opts.m
        ));
    }
    candidate.census = Some(census_from_witnesses(
        &witnesses,
        targets,
        opts.m,
        fb.signed_orbits.len(),
        unknowns,
        opts.extra_relations,
        census_ms,
    ));
    if let Some(sample) = opts.solve_cost_targets {
        measure_solve_cost(kc, fb, targets, opts, sample, &mut candidate);
    }
    (candidate, witnesses)
}

/// Does every abscissa of the base have trace zero?
///
/// For an invariant subspace this is the divisibility test `(x+1) ∤ g`,
/// but the base may be a union or a pruned set, so it is computed
/// directly on the abscissae and holds for every family.
fn subspace_is_trace_zero(kc: &KoblitzCurve, fb: &FrobeniusFactorBase) -> bool {
    fb.subspace.iter().all(|x| {
        let mut acc = x.clone();
        let mut cur = x.clone();
        for _ in 1..kc.n {
            cur = cur.square(&kc.curve.irreducible);
            acc = acc.add(&cur);
        }
        acc.is_zero()
    })
}

/// Run the algebraic oracle on the first `sample` census targets and
/// record what it cost.
///
/// This is the second factor of the collection cost, the one the census
/// does not see: coverage saturates as the subspace grows, while the
/// Weil-restricted system carries `m·ℓ` unknowns and does not.  Both
/// outcomes are charged — a refuted target costs a full search and is
/// the common case — so the mean is over every target tried, not over
/// the ones that decomposed.
///
/// **Only a [`FactorBaseDomain::LinearSubspace`] base can be priced this
/// way.**  The summation polynomial is Weil-restricted over
/// `fb.subspace_basis`, so the system's solutions are the whole space
/// that basis spans.  For every other domain — a pruned
/// `SubspaceSubset`, a `TwoTorsionSaturation`, a `FrobeniusUnion`, an
/// `ExplicitFrobeniusOrbits` set — the base is a *subset* of that span,
/// carried by the SAT domain trie rather than by the linear algebra, and
/// [`groebner_decompose`] falls back to enumerating the whole span and
/// rejecting non-members.  The number that comes back is then the span's
/// solving cost and not the base's, and it costs orders of magnitude
/// more to obtain: at `K_1/2^15`, `m = 2` a divisor-only sweep of the
/// linear candidates takes `0.3 s` where the same sweep with pruning and
/// saturation on does not finish in ten minutes.  Those candidates are
/// left unmeasured, with the reason recorded in
/// [`Candidate::solve_cost_skipped`], and [`rank_candidates`] sorts them
/// below every measured one rather than letting their trials count
/// compete with a word-XOR count.
fn measure_solve_cost(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    targets: &TargetSet,
    opts: &SearchOptions,
    sample: usize,
    candidate: &mut Candidate,
) {
    if fb.domain != FactorBaseDomain::LinearSubspace {
        candidate.solve_cost_skipped = Some(format!(
            "{} is a subset of the space its Weil restriction is written over; \
             the Gröbner oracle prices the span, not the base",
            domain_label(&fb.domain)
        ));
        return;
    }
    // A memo hit returns a reduction without computing it, so the counter
    // diff below would report replayed work as free.
    if super::algebra_cache::enabled(super::algebra_cache::Layer::ExactReduction) {
        candidate.solve_cost_skipped =
            Some("IC_REDUCTION_CACHE replays reductions, so nothing here can be timed".into());
        return;
    }
    let trials = sample.min(targets.points.len());
    if trials == 0 {
        candidate.solve_cost_skipped = Some("no census targets".into());
        return;
    }
    if !candidate.cofactor_admissible {
        candidate.solve_cost_skipped = Some("cofactor classes cannot cancel".into());
        return;
    }
    let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
    let index_of = fb.index_map();
    // This thread's own reductions only: the decompositions below run here,
    // and solving elsewhere in the process must not be charged to them.
    let before = f4_thread_word_ops();
    for target in targets.points.iter().take(trials) {
        let _ = groebner_decompose(
            kc,
            fb,
            &index_of,
            &st,
            target,
            opts.m,
            SolverEngine::default(),
            20_000,
        );
    }
    let ops = f4_thread_word_ops().saturating_sub(before) as f64 / trials as f64;
    candidate.measured_ops_per_target = Some(ops);
    // Cost per target is only half of it: without a trial count there is
    // nothing to multiply, and a base that decomposes nothing is not made
    // attractive by being cheap to fail on.
    let expected = candidate.expected_trials();
    if expected.is_finite() {
        candidate.expected_stage_ops = Some(expected * ops);
    } else {
        candidate.solve_cost_skipped =
            Some("no census target decomposes, so there is no trial count to price".into());
    }
}

/// Enumerate the specs a search would try, without scoring them.
pub fn candidate_specs(kc: &KoblitzCurve, opts: &SearchOptions) -> Vec<FactorBaseSpec> {
    let mut specs: Vec<FactorBaseSpec> = Vec::new();
    let mut seen: HashSet<String> = HashSet::new();
    fn push_unique(
        specs: &mut Vec<FactorBaseSpec>,
        seen: &mut HashSet<String>,
        spec: FactorBaseSpec,
    ) {
        let key = serde_json::to_string(&spec).unwrap_or_default();
        if seen.insert(key) {
            specs.push(spec);
        }
    }
    let mut push = |spec: FactorBaseSpec| push_unique(&mut specs, &mut seen, spec);
    if opts.families.contains(&Family::Factor) {
        let count = top_factor_indices(kc).len();
        for index in 0..count {
            push(FactorBaseSpec::Factor { index });
        }
    }
    if opts.families.contains(&Family::Divisor) {
        let factors = invariant_factors(kc);
        if !factors.is_empty() && factors.len() <= 20 {
            // F_2-dimension of each factor's invariant subspace.
            let degrees: Vec<u32> = factors
                .iter()
                .map(|f| kc.k * f.degree().unwrap_or(0) as u32)
                .collect();
            for mask in 1usize..(1usize << factors.len()) {
                let indices: Vec<usize> = (0..factors.len())
                    .filter(|i| (mask >> i) & 1 == 1)
                    .collect();
                let dim: u32 = indices.iter().map(|&i| degrees[i]).sum();
                if dim < opts.min_dimension || dim > opts.max_dimension || dim >= kc.n {
                    continue;
                }
                if (1usize << dim) > opts.max_abscissae {
                    continue;
                }
                push(FactorBaseSpec::Divisor { indices });
            }
        }
    }
    if opts.families.contains(&Family::Union) && kc.n < 64 {
        let mut rng = StdRng::seed_from_u64(opts.seed ^ 0x554e_494f_4e53_4545);
        let (lo, hi) = opts.union_seed_dimensions;
        for dim in lo.max(1)..=hi.min(12) {
            // Standard basis first, then random seeds.
            let mut seeds: Vec<Vec<u64>> = vec![(0..dim).map(|i| 1u64 << i).collect()];
            let mut attempts = 0;
            while seeds.len() < opts.union_samples + 1 && attempts < 64 * (opts.union_samples + 1) {
                attempts += 1;
                let masks: Vec<u64> = (0..dim).map(|_| rng.gen_range(1..(1u64 << kc.n))).collect();
                let basis: Vec<F2mElement> = masks
                    .iter()
                    .map(|&m| F2mElement::from_biguint(&BigUint::from(m), kc.n))
                    .collect();
                let unique: HashSet<BigUint> = span_f2(&basis, kc.n)
                    .iter()
                    .map(|x| x.to_biguint())
                    .collect();
                if unique.len() == 1usize << dim {
                    seeds.push(masks);
                }
            }
            for masks in seeds {
                push(FactorBaseSpec::FrobeniusUnion { seed_masks: masks });
            }
        }
    }
    if opts.families.contains(&Family::Subgroup) && kc.n < 64 {
        // One candidate per point budget in the dimension window, so the
        // sizes line up with what the union family reaches.
        let (lo, hi) = opts.union_seed_dimensions;
        for dim in lo.max(1)..=hi.min(12) {
            let points = (1usize << dim) * kc.n as usize;
            if points > 2 * opts.max_abscissae {
                continue;
            }
            for sample in 0..=opts.union_samples.min(2) {
                push(FactorBaseSpec::SubgroupOrbits {
                    seed: opts.seed ^ (0x5355_4247_5250_0000 + dim as u64 * 31 + sample as u64),
                    points,
                });
            }
        }
    }
    if opts.saturate && (&kc.cofactor % BigUint::from(2u32)).is_zero() {
        let base: Vec<FactorBaseSpec> = specs.clone();
        for spec in base {
            push_unique(
                &mut specs,
                &mut seen,
                FactorBaseSpec::TwoTorsionSaturated {
                    parent: Box::new(spec),
                },
            );
        }
    }
    specs
}

/// **Run the search**: score every candidate spec (and its pruned
/// variant) on one shared target set and rank them.
pub fn search(kc: &KoblitzCurve, opts: &SearchOptions) -> SearchReport {
    search_with_progress(kc, opts, &mut |_, _, _| {})
}

/// [`search`] with a callback `(index, total, candidate)` after each
/// spec is scored.
pub fn search_with_progress(
    kc: &KoblitzCurve,
    opts: &SearchOptions,
    progress: &mut dyn FnMut(usize, usize, &Candidate),
) -> SearchReport {
    let start = std::time::Instant::now();
    let targets = TargetSet::new(kc, opts.sample_targets, opts.exhaustive_cap, opts.seed);
    let specs = candidate_specs(kc, opts);
    let mut candidates = Vec::new();
    for (i, spec) in specs.iter().enumerate() {
        for candidate in evaluate_spec(kc, spec, &targets, opts, opts.prune) {
            progress(i + 1, specs.len(), &candidate);
            candidates.push(candidate);
        }
    }
    rank_candidates(&mut candidates);
    SearchReport {
        n: kc.n,
        a: kc.a,
        subgroup_order: kc.subgroup_order.to_string(),
        cofactor: kc.cofactor.to_string(),
        options: opts.clone(),
        targets: targets.len(),
        exhaustive_targets: targets.exhaustive,
        candidates,
        elapsed_ms: start.elapsed().as_secs_f64() * 1000.0,
    }
}

/// Per-orbit view of a census, for reports: canonical abscissa,
/// orbit size and witness count.
pub fn orbit_table(fb: &FrobeniusFactorBase, census: &YieldCensus) -> Vec<(u64, usize, usize)> {
    let reps = fb.signed_orbit_abscissa_representatives();
    let mut rows: BTreeMap<usize, (u64, usize, usize)> = BTreeMap::new();
    for (o, orbit) in fb.signed_orbits.iter().enumerate() {
        rows.insert(
            o,
            (
                reps[o].to_u64().unwrap_or(u64::MAX),
                orbit.len(),
                census.orbit_witnesses.get(o).copied().unwrap_or(0),
            ),
        );
    }
    rows.into_values().collect()
}

// ── Tests ──────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::koblitz_index_calculus::{enumerate_decompose, point_key};
    use num_traits::One;

    fn brute_coverage(
        kc: &KoblitzCurve,
        fb: &FrobeniusFactorBase,
        targets: &TargetSet,
        m: usize,
    ) -> usize {
        let index = fb.index_map();
        targets
            .points
            .iter()
            .filter(|t| enumerate_decompose(kc, fb, &index, t, m).is_some())
            .count()
    }

    /// The divisor-only search options the solve-cost objective needs:
    /// every candidate is a linear subspace, so every one can be priced.
    fn linear_only(m: usize, solve_cost_targets: Option<usize>) -> SearchOptions {
        SearchOptions {
            m,
            min_dimension: 3,
            max_dimension: 8,
            families: vec![Family::Divisor],
            prune: false,
            saturate: false,
            seed: 1,
            solve_cost_targets,
            ..SearchOptions::default()
        }
    }

    /// Coverage alone ranks the bases of `K_1/2^15` backwards.
    ///
    /// The point of `research/notes/index-calculus/RESEARCH_FACTOR_BASE_SOLVE_COST.md`: expected trials
    /// sees the relation columns and the coverage and not the `m·ℓ`
    /// unknowns of the Weil-restricted summation system, so it climbs the
    /// dimension ladder collecting yield while paying an order of
    /// magnitude in solving.  Scoring the solver instead must pick a
    /// different, smaller base — and the one it picks must really be the
    /// cheaper of the two when both are measured.
    #[test]
    fn solve_cost_scoring_picks_a_cheaper_base_than_expected_trials() {
        let kc = KoblitzCurve::new(1, 15).unwrap();

        let by_trials = search(&kc, &linear_only(2, None));
        let trials_pick = by_trials.best().expect("some base decomposes");
        assert!(
            trials_pick.expected_stage_ops.is_none(),
            "no measurement was asked for"
        );

        let by_cost = search(&kc, &linear_only(2, Some(8)));
        let cost_pick = by_cost.best().expect("some base decomposes");
        assert_ne!(
            cost_pick.spec, trials_pick.spec,
            "the two objectives must disagree on this curve"
        );

        // The disagreement is the documented one: the trials pick buys
        // coverage with dimension, and dimension is what the solver pays.
        assert!(cost_pick.dimension < trials_pick.dimension);
        assert!(cost_pick.expected_trials() > trials_pick.expected_trials());

        // And the pick is really cheaper, measured the same way on both.
        let measured = |spec: &FactorBaseSpec| {
            by_cost
                .candidates
                .iter()
                .find(|c| &c.spec == spec)
                .and_then(|c| c.expected_stage_ops)
                .expect("every linear-subspace candidate is priced")
        };
        assert!(
            measured(&cost_pick.spec) * 4.0 < measured(&trials_pick.spec),
            "cost pick {:?} at {:e} word XORs must beat trials pick {:?} at {:e}",
            cost_pick.spec,
            measured(&cost_pick.spec),
            trials_pick.spec,
            measured(&trials_pick.spec)
        );
    }

    /// A base that is a subset of the span its summation polynomial is
    /// restricted over cannot be priced on that span, and must not then
    /// win on a trials count while the priced candidates carry word XORs.
    #[test]
    fn only_linear_subspace_candidates_are_priced_and_they_rank_first() {
        let kc = KoblitzCurve::new(1, 15).unwrap();
        let opts = SearchOptions {
            m: 2,
            min_dimension: 3,
            max_dimension: 6,
            families: vec![Family::Divisor],
            prune: true,
            saturate: true,
            seed: 1,
            solve_cost_targets: Some(4),
            ..SearchOptions::default()
        };
        let report = search(&kc, &opts);
        let mut priced = 0;
        let mut seen_unpriced = false;
        for c in &report.candidates {
            match c.expected_stage_ops {
                Some(_) => {
                    priced += 1;
                    assert_eq!(
                        c.domain,
                        domain_label(&FactorBaseDomain::LinearSubspace),
                        "priced a base that is a subset of its own span: {:?}",
                        c.spec
                    );
                    assert!(c.solve_cost_skipped.is_none());
                    assert!(
                        !seen_unpriced,
                        "an unpriced candidate ranked above a priced one"
                    );
                }
                None => {
                    seen_unpriced = true;
                    assert!(
                        c.solve_cost_skipped.is_some() || c.skipped.is_some(),
                        "a candidate went unpriced without saying why: {:?}",
                        c.spec
                    );
                }
            }
        }
        assert!(priced > 0 && seen_unpriced, "the test needs both kinds");
    }

    #[test]
    fn census_coverage_matches_exhaustive_search_for_two_and_three_summands() {
        let kc = KoblitzCurve::new(1, 15).unwrap();
        let targets = TargetSet::new(&kc, 64, 4096, 7);
        assert!(targets.exhaustive, "r = 211 must be enumerated");
        for spec in [
            FactorBaseSpec::Divisor {
                indices: vec![0, 2],
            },
            FactorBaseSpec::Divisor { indices: vec![2] },
            FactorBaseSpec::FrobeniusUnion {
                seed_masks: vec![3468, 4413],
            },
        ] {
            let fb = spec.materialize(&kc).unwrap();
            let table = PairSumTable::build(&kc, &fb).unwrap();
            for m in [2usize, 3] {
                let witnesses = witness_list(&kc, &fb, &table, &targets, m);
                let census = census_from_witnesses(
                    &witnesses,
                    &targets,
                    m,
                    fb.signed_orbits.len(),
                    fb.unknowns(),
                    2,
                    0.0,
                );
                assert_eq!(
                    census.covered,
                    brute_coverage(&kc, &fb, &targets, m),
                    "{spec:?} m={m}"
                );
                // Every witness really sums to its target.
                let mut check = 0;
                table.witnesses(&kc, &fb, &targets.points[0], m, &mut |idxs| {
                    let sum = idxs
                        .iter()
                        .fold(BinaryPoint::Infinity, |s, &i| kc.add(&s, &fb.points[i]));
                    assert_eq!(sum, targets.points[0]);
                    assert!(
                        idxs.windows(2).all(|w| w[0] <= w[1]),
                        "witnesses are sorted"
                    );
                    check += 1;
                    true
                });
                assert_eq!(check, witnesses.iter().filter(|w| w.target == 0).count());
            }
        }
    }

    #[test]
    fn the_prior_review_numbers_reproduce() {
        // MATHEMATICS.md: at n = 15, divisor [0, 2] has 61 points and
        // covers 150/210 with three summands; the union seeded by
        // 3468, 4413 covers 210/210.
        let kc = KoblitzCurve::new(1, 15).unwrap();
        let targets = TargetSet::new(&kc, 64, 4096, 1);
        let opts = SearchOptions {
            m: 3,
            ..SearchOptions::default()
        };
        let divisor = evaluate_spec(
            &kc,
            &FactorBaseSpec::Divisor {
                indices: vec![0, 2],
            },
            &targets,
            &opts,
            false,
        );
        assert_eq!(divisor[0].points, 61);
        assert_eq!(divisor[0].census.as_ref().unwrap().covered, 150);
        let union = evaluate_spec(
            &kc,
            &FactorBaseSpec::FrobeniusUnion {
                seed_masks: vec![3468, 4413],
            },
            &targets,
            &opts,
            false,
        );
        assert_eq!(union[0].points, 61);
        assert_eq!(union[0].census.as_ref().unwrap().covered, 210);
    }

    #[test]
    fn pruned_specs_round_trip_and_never_raise_expected_trials() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let targets = TargetSet::new(&kc, 64, 4096, 3);
        let opts = SearchOptions {
            m: 2,
            projected_columns: false,
            ..SearchOptions::default()
        };
        let spec = FactorBaseSpec::Divisor {
            indices: vec![1, 2],
        };
        let candidates = evaluate_spec(&kc, &spec, &targets, &opts, true);
        assert!(!candidates.is_empty());
        let parent = &candidates[0];
        if let Some(pruned) = candidates.get(1) {
            assert!(pruned.expected_trials() <= parent.expected_trials());
            assert!(pruned.signed_orbits < parent.signed_orbits);
            // The recipe re-materialises to the same base.
            let fb = pruned.spec.materialize(&kc).unwrap();
            assert_eq!(fb.points.len(), pruned.points);
            assert_eq!(fb.signed_orbits.len(), pruned.signed_orbits);
            assert!(matches!(fb.domain, FactorBaseDomain::SubspaceSubset { .. }));
            // And it is still Frobenius- and negation-closed.
            let keys: HashSet<_> = fb.points.iter().map(point_key).collect();
            for p in &fb.points {
                assert!(keys.contains(&point_key(&kc.frobenius(p))));
                assert!(keys.contains(&point_key(&crate::binary_ecc::curve::point_neg(p))));
            }
            // JSON round trip.
            let text = serde_json::to_string(&pruned.spec).unwrap();
            let back: FactorBaseSpec = serde_json::from_str(&text).unwrap();
            assert_eq!(back, pruned.spec);
        }
    }

    #[test]
    fn greedy_prune_scores_are_exact_recounts() {
        let kc = KoblitzCurve::new(1, 15).unwrap();
        let targets = TargetSet::new(&kc, 64, 4096, 5);
        let fb = FactorBaseSpec::Divisor {
            indices: vec![0, 1, 2],
        }
        .materialize(&kc)
        .unwrap();
        let table = PairSumTable::build(&kc, &fb).unwrap();
        let witnesses = witness_list(&kc, &fb, &table, &targets, 3);
        let (keep, steps) = greedy_prune(&fb, &witnesses, targets.len(), 2, 1);
        assert_eq!(keep.len() + steps.len(), fb.signed_orbits.len());
        if let Some(last) = steps.last() {
            // Re-materialise the pruned base and recount from scratch.
            let pruned = restrict_factor_base_to_orbits(&kc, &fb, &keep).unwrap();
            let table = PairSumTable::build(&kc, &pruned).unwrap();
            let w = witness_list(&kc, &pruned, &table, &targets, 3);
            let census = census_from_witnesses(
                &w,
                &targets,
                3,
                pruned.signed_orbits.len(),
                pruned.signed_orbits.len(),
                2,
                0.0,
            );
            assert_eq!(census.covered, last.covered_after);
            assert_eq!(pruned.signed_orbits.len(), last.unknowns_after);
        }
    }

    #[test]
    fn solve_cost_ranking_prefers_the_base_the_oracle_is_cheapest_over() {
        // At K_1/2^15 the two objectives disagree: coverage saturates as
        // the subspace grows while the Weil-restricted system carries
        // m·ℓ unknowns and does not, so the trials-optimal base is one
        // the oracle is an order of magnitude slower on
        // (research/notes/index-calculus/RESEARCH_FACTOR_BASE_SOLVE_COST.md).  Ranking by measured
        // stage cost must put a six-dimensional base first; ranking by
        // trials alone must not.
        let kc = KoblitzCurve::new(1, 15).unwrap();
        let base = SearchOptions {
            m: 2,
            min_dimension: 6,
            max_dimension: 8,
            families: vec![Family::Divisor],
            prune: false,
            saturate: false,
            union_samples: 0,
            ..SearchOptions::default()
        };
        let by_trials = search(&kc, &base);
        let by_cost = search(
            &kc,
            &SearchOptions {
                solve_cost_targets: Some(24),
                ..base.clone()
            },
        );

        let dimension_of = |report: &SearchReport| -> u32 {
            report.best().expect("some base decomposes").dimension
        };
        assert_eq!(
            dimension_of(&by_trials),
            8,
            "the trials objective is expected to prefer the larger subspace here"
        );
        assert_eq!(
            dimension_of(&by_cost),
            6,
            "measured stage cost must prefer the smaller system"
        );

        let best = by_cost.best().unwrap();
        assert!(
            best.measured_ops_per_target.unwrap_or(0.0) > 0.0,
            "the oracle must actually have been run"
        );
        assert!(best.expected_stage_ops.unwrap_or(f64::INFINITY).is_finite());
        // Every scored candidate carries the same kind of score, and the
        // report is sorted by it.
        let scores: Vec<f64> = by_cost.candidates.iter().map(Candidate::score).collect();
        assert!(scores.windows(2).all(|w| w[0] <= w[1]));
        // The ranking must be a real reordering, not a relabelling of
        // the same order.
        let trials_first = by_trials.best().unwrap().expected_stage_ops;
        assert!(trials_first.is_none());
        let cheapest = best.expected_stage_ops.unwrap();
        let trials_choice = by_cost
            .candidates
            .iter()
            .filter(|c| c.expected_trials().is_finite())
            .min_by(|x, y| x.expected_trials().total_cmp(&y.expected_trials()))
            .unwrap();
        assert!(
            trials_choice.expected_stage_ops.unwrap() > 2.0 * cheapest,
            "the disagreement should be large, not marginal: {:?} against {cheapest}",
            trials_choice.expected_stage_ops
        );
    }

    #[test]
    fn trace_zero_is_the_divisibility_test_on_every_candidate() {
        // ker g(σ) ⊆ ker Tr exactly when (x+1) ∤ g, because
        // Tr = h(σ) with h = (t^n + 1)/(t + 1).  The search computes the
        // trace directly, so this pins the two against each other.
        for (a, n) in [(0u8, 9u32), (1, 15), (1, 17)] {
            let kc = KoblitzCurve::new(a, n).unwrap();
            let opts = SearchOptions {
                m: 2,
                min_dimension: 2,
                max_dimension: 9,
                families: vec![Family::Divisor],
                prune: false,
                saturate: false,
                union_samples: 0,
                ..SearchOptions::default()
            };
            let report = search(&kc, &opts);
            let mut checked = 0;
            for c in &report.candidates {
                let FactorBaseSpec::Divisor { indices } = &c.spec else {
                    continue;
                };
                if c.skipped.is_some() {
                    continue;
                }
                // Index 0 is `x + 1` in `all_factors_of_x_n_minus_1`.
                assert_eq!(
                    c.trace_zero,
                    !indices.contains(&0),
                    "K_{a}/2^{n} divisor {indices:?}"
                );
                checked += 1;
            }
            assert!(checked > 2, "K_{a}/2^{n} scored too few divisors to test");
        }
    }

    #[test]
    fn search_ranks_a_solvable_base_first_where_the_legacy_one_fails() {
        // ic's default base at n = 15 (factor index 0) yields nothing;
        // the search must find one that does.
        let kc = KoblitzCurve::new(1, 15).unwrap();
        let opts = SearchOptions {
            m: 2,
            max_dimension: 8,
            union_samples: 1,
            ..SearchOptions::default()
        };
        let report = search(&kc, &opts);
        let legacy = report
            .candidates
            .iter()
            .find(|c| c.spec == FactorBaseSpec::Factor { index: 0 })
            .expect("legacy candidate is scored");
        assert_eq!(legacy.census.as_ref().unwrap().covered, 0);
        let best = report.best().expect("some base decomposes");
        assert!(best.expected_trials().is_finite());
        assert!(best.census.as_ref().unwrap().covered > 0);
        // Ranking is monotone in expected trials.
        let scores: Vec<f64> = report
            .candidates
            .iter()
            .map(Candidate::expected_trials)
            .collect();
        assert!(scores.windows(2).all(|w| w[0] <= w[1]));
        // The best candidate must actually solve a DLP end to end.
        use crate::cryptanalysis::koblitz_index_calculus::{
            koblitz_index_calculus_dlp_with_factor_base, DecompositionStrategy, KoblitzIcOptions,
        };
        let fb = best.spec.materialize(&kc).unwrap();
        let d = BigUint::from(97u32);
        let target = kc.mul(kc.generator(), &d);
        let ic = KoblitzIcOptions {
            m: 2,
            strategy: DecompositionStrategy::PairTable,
            collapse_projected_orbits: true,
            allow_direct_relation: false,
            ..KoblitzIcOptions::default()
        };
        let report = koblitz_index_calculus_dlp_with_factor_base(&kc, &target, &fb, &ic).unwrap();
        assert_eq!(report.log, Some(d));
        assert_eq!(report.inconsistent_relations, 0);
        assert_eq!(report.verification_failures, 0);
        assert!(report.relations >= BigUint::one().to_usize().unwrap());
    }
}
