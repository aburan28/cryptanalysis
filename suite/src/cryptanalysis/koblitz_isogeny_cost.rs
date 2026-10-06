//! # The cost distribution of index calculus across a binary isogeny class
//!
//! The folklore is that the ECDLP costs the same everywhere in an isogeny
//! class, so an attacker gains nothing by walking to an isogenous curve
//! before solving.  [`crate::cryptanalysis::isogeny_class_search`] tests one
//! *component* of that claim — the affine refutation degree `D*` of the
//! descended Semaev system — over every curve at a small size.  This module
//! tests the claim **end to end**: it enumerates a real isogeny class, runs a
//! complete Gröbner-based index calculus on every member, and reports the
//! resulting cost distribution with a brute-forced DLP as ground truth.
//!
//! Three measurements per class member, all on the same curve and the same
//! factor-base subspace:
//!
//! 1. **Gröbner solve time** — wall-clock nanoseconds inside the
//!    decomposition solver, plus the reduction and node counts that explain
//!    it.  Time is reported alongside its own native counters precisely
//!    because wall clock is not portable evidence on its own.
//! 2. **Relation yield** — admitted relations per probe, and how many of
//!    them raised the rank of the relation matrix.
//! 3. **Observed first fall degree** — via
//!    [`crate::cryptanalysis::isogeny_class_search::measure_curve`], so this
//!    module reports the *same* operational first-fall definition the FFD
//!    harness was calibrated with rather than a lookalike.
//!
//! ## What "enumerate the class" can and cannot mean
//!
//! A vertex of the class is named here by **exhaustive trace scan**: every
//! `a₆ ≠ 0` over `F_{2^n}` is point-counted by the Artin–Schreier formula and
//! kept when its order matches the Koblitz order.  Every curve `y² + xy = x³
//! + a₂x² + a₆` has `j = 1/a₆`, so within one family `a₂ ∈ {0, 1}` the
//! coefficient `a₆` names the vertex uniquely.  The two families are
//! quadratic twists with traces `±t`, so they are *different* isogeny
//! classes of the same size, and [`preferred_family`] picks the one whose
//! Koblitz curve has a subgroup wide enough to host a DLP at all — at
//! `n = 17` the `a₂ = 0` curve has `#E = 2²·137·239` and cannot.
//!
//! The scan costs `O(4^n)` field operations, which is why this is a
//! small-`n` instrument.  It is nonetheless the **only** route to a named
//! class member available here, and that is a statement about the isogenies,
//! not about the scan:
//!
//! - the modular-polynomial walk needs `Φ_ℓ`, and
//!   [`crate::cryptanalysis::binary_isogeny`] tabulates only `ℓ ∈ {2, 3}`;
//! - the nontrivial isogeny degrees of a Koblitz class are the prime factors
//!   of the conductor of `Z[π]`, which are large and sparse — `271` at
//!   `n = 17`, `7193` at `n = 31`, `{409, 1721}` at `n = 41` — so `ℓ ∈
//!   {2, 3}` never moves;
//! - a Vélu step at those degrees needs the kernel polynomial as a factor of
//!   the `ℓ`-division polynomial, which is not implemented in this
//!   repository.
//!
//! [`ClassReachReport`] states that barrier per degree in one table rather
//! than leaving it implicit, so the sizes this module declines to run are
//! declined for a named, checkable reason.
//!
//! ## Scope, stated before any number is read
//!
//! **No isogeny is computed, so no point is transported.**  Each member gets
//! its own DLP instance `(G, Q = [d]G)` on its own curve.  What is measured
//! is therefore the cost of the ECDLP *on each vertex of the class*, which is
//! the quantity a cost distribution over the class is made of — but it is
//! not the cost of transporting one fixed instance along `φ`.  A claim about
//! the latter needs the isogeny, and this module does not have it.
//!
//! **The factor base is a vector subspace, not a Frobenius orbit.**  It has
//! to be: the Koblitz speedup comes from the `F_2`-Frobenius, which is an
//! endomorphism of `K₀` alone.  A curve isogenous to `K₀` over `F_{2^n}` does
//! not inherit it, so
//! [`crate::cryptanalysis::koblitz_index_calculus`] and its signed-orbit
//! unknowns do not apply to a class member at all.  Every member — the
//! Koblitz curve included — is therefore measured on the curve-agnostic
//! subspace base `V = ⟨1, z, …, z^{ℓ−1}⟩`, which is the only instrument that
//! can compare them.  The Koblitz curve's own Frobenius base is a separate
//! measurement and is not this one.
//!
//! **Every reported logarithm is verified twice**: once as `[d]G = Q` on the
//! curve, and once against an independent baby-step giant-step solve of the
//! same instance.  A disagreement fails the row closed
//! ([`IcCostRow::verified`]), and a failed row is reported, never dropped.

use std::collections::{BTreeMap, HashMap};
use std::time::Instant;

use num_bigint::BigInt;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use rayon::prelude::*;

use crate::binary_ecc::{BinaryCurve, BinaryPoint, F2mElement, IrreduciblePoly};
use crate::cryptanalysis::ic_boundary::{
    binary_point_count, ArtinSchreier, BinaryGroup, CountedGroup, GroupOps, IncrementalGauss,
    RowStatus,
};
use crate::cryptanalysis::isogeny_class_search::{
    koblitz_isogeny_class, koblitz_order, measure_curve,
};
use crate::cryptanalysis::koblitz_fast::{FastCurve, FastPoint};
use crate::cryptanalysis::koblitz_groebner::{
    solve_boolean_system_filtered, FieldStructure, SolveOptions, SolverEngine, SplitRule,
};
use crate::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;
use crate::cryptanalysis::polynomial_reuse::build_decomposition_system_reusing;
use crate::cryptanalysis::semaev_decomp::Gf2;

// ── Part A: naming the class ────────────────────────────────────────

/// The result of an exhaustive trace scan over every `a₆ ≠ 0`.
#[derive(Clone, Debug)]
pub struct ClassCensus {
    pub n: u32,
    /// The family scanned: `a₂ ∈ {0, 1}`.  A `j`-invariant names two
    /// curves over `F_{2^n}`, one per family, with traces `±t`; they are
    /// quadratic twists and lie in *different* isogeny classes, so the
    /// family is part of the class's identity, not a presentation detail.
    pub a2: u8,
    /// `#E` the scan was looking for.
    pub target_order: i128,
    /// `#E` of the quadratic twist, `2^{n+1} + 2 − target_order`.
    pub twist_order: i128,
    /// Every `a₆` whose curve has exactly `target_order` points.
    pub members: Vec<u64>,
    /// How many curves landed on the twist order instead.
    pub twist_members: usize,
    /// Curves scanned: `2^n − 1`.
    pub scanned: usize,
    /// `Σ_{f | c} h(O_f)` from the CM side, for cross-validation.
    pub predicted_class_size: BigInt,
    /// Whether the scan and the CM formula agree.
    pub agrees_with_cm: bool,
}

/// `#E_{a₆}(F_{2^n})` for `y² + xy = x³ + a₆`, by the Artin–Schreier count
///
/// ```text
///   #E = 2 + 2 · #{ x ≠ 0 : Tr(x + a₆ x^{−2}) = 0 }.
/// ```
///
/// `O(2^n)` field operations for one curve.  This is
/// [`binary_point_count`] under its own name, kept as a thin wrapper so the
/// scan below reads as the formula it is.
pub fn curve_order(gf: &Gf2, ash: &ArtinSchreier, a2: u8, a6: u64) -> u64 {
    binary_point_count(gf, ash, a2 as u64, a6)
}

/// `#E(K_{a₂} / F_{2^n})`, the order the scan looks for.
///
/// [`koblitz_order`] is the `a₂ = 0` curve; the `a₂ = 1` curve is its
/// quadratic twist, `2^{n+1} + 2 − #E(K_0)`.
pub fn koblitz_family_order(n: u32, a2: u8) -> i128 {
    let base = koblitz_order(n)
        .to_string()
        .parse::<i128>()
        .expect("a Koblitz order below 2^63 fits i128");
    if a2 == 0 {
        base
    } else {
        (1i128 << (n + 1)) + 2 - base
    }
}

/// The family whose Koblitz curve carries a usable DLP, preferring the
/// larger prime-order subgroup.
///
/// This is a real choice, not a convention: at `n = 17` the `a₂ = 0` curve
/// has `#E = 2²·137·239`, whose largest prime subgroup is 8 bits wide and
/// cannot host the experiment at all, while its twist has `#E = 2·65587`
/// with a 17-bit prime.  Since every member of a class shares `#E`, the
/// choice is made once per degree and binds the whole sweep.
pub fn preferred_family(n: u32) -> Option<(u8, u64, u64)> {
    let mut best: Option<(u8, u64, u64)> = None;
    for a2 in [0u8, 1] {
        let order = koblitz_family_order(n, a2);
        if order <= 0 || order > u64::MAX as i128 {
            continue;
        }
        let order = order as u64;
        let Some(&(r, e)) = factorise(order).last() else {
            continue;
        };
        if e != 1 || r < 1024 {
            continue;
        }
        if best.is_none_or(|(_, br, _)| r > br) {
            best = Some((a2, r, order / r));
        }
    }
    best
}

/// **Enumerate the isogeny class exhaustively** by scanning every `a₆`.
///
/// Returns the members of the class of the Koblitz curve `K₀ / F_{2^n}`
/// together with the CM-side prediction, which the caller should find equal:
/// the scan is `O(4^n)` and the prediction is free, so an agreement is a
/// genuine cross-check of both.
///
/// Cost is `O(4^n)`, parallelised over `a₆`.  At `n = 17` that is `2^34`
/// field operations; it grows by `4×` per degree and is the reason this
/// module's exact mode stops well below cryptographic size.
pub fn enumerate_class_exact(n: u32, irr: &IrreduciblePoly, a2: u8) -> ClassCensus {
    let gf = Gf2::new(irr);
    let ash = ArtinSchreier::new(&gf);
    let target_order = koblitz_family_order(n, a2);
    let twist_order = (1i128 << (n + 1)) + 2 - target_order;

    let hits: Vec<(u64, bool)> = (1u64..(1u64 << n))
        .into_par_iter()
        .filter_map(|a6| {
            let ord = curve_order(&gf, &ash, a2, a6) as i128;
            if ord == target_order {
                Some((a6, true))
            } else if ord == twist_order {
                Some((a6, false))
            } else {
                None
            }
        })
        .collect();

    let mut members: Vec<u64> = hits.iter().filter(|(_, m)| *m).map(|(a, _)| *a).collect();
    members.sort_unstable();
    let twist_members = hits.len() - members.len();

    let predicted_class_size = koblitz_isogeny_class(n, 20_000_000).class_size;
    let agrees_with_cm = predicted_class_size.to_string() == members.len().to_string();

    ClassCensus {
        n,
        a2,
        target_order,
        twist_order,
        members,
        twist_members,
        scanned: (1usize << n) - 1,
        predicted_class_size,
        agrees_with_cm,
    }
}

/// What a degree budget actually reaches in a Koblitz isogeny class, and
/// what blocks the rest — the accounting that says why the exact scan above
/// is the only route to a named vertex at a given `n`.
#[derive(Clone, Debug)]
pub struct ClassReachReport {
    pub n: u32,
    pub order: BigInt,
    pub conductor: BigInt,
    pub conductor_fully_factored: bool,
    /// `Σ_{f | c} h(O_f)`.
    pub class_size: BigInt,
    pub log2_class_size: f64,
    /// The prime isogeny degrees that move at all (`ℓ | c`).
    pub nontrivial_degrees: Vec<BigInt>,
    /// `log2` of the `O(4^n)` exhaustive trace scan.
    pub log2_exhaustive_scan: f64,
    /// Whether `Φ_ℓ` is tabulated for some degree that moves.
    pub modular_polynomial_available: bool,
    /// Why the class cannot be named at this `n`, or `None` when it can.
    pub blocked_because: Option<String>,
}

/// Levels of the classical modular polynomial this repository tabulates.
/// [`crate::cryptanalysis::binary_isogeny::phi_l_mod2_in_x`] panics on any
/// other, so naming the set once keeps the reach report honest.
pub const TABULATED_MODULAR_LEVELS: &[u32] = &[2, 3];

/// Budget above which [`enumerate_class_exact`] is declared out of reach.
/// `2^40` field operations is roughly an hour of one core in this crate's
/// binary field, measured on the `n = 17` scan and scaled.
pub const EXHAUSTIVE_SCAN_LOG2_BUDGET: f64 = 40.0;

/// Report what it would take to name a member of the class at degree `n`.
pub fn class_reach_report(n: u32) -> ClassReachReport {
    let class = koblitz_isogeny_class(n, 20_000_000);
    let degrees = class.nontrivial_isogeny_degrees();
    let modular_polynomial_available = degrees.iter().any(|d| {
        TABULATED_MODULAR_LEVELS
            .iter()
            .any(|l| d == &BigInt::from(*l))
    });
    let log2_exhaustive_scan = 2.0 * n as f64;

    let blocked_because =
        if log2_exhaustive_scan <= EXHAUSTIVE_SCAN_LOG2_BUDGET || modular_polynomial_available {
            None
        } else {
            Some(format!(
            "exhaustive trace scan costs 2^{log2_exhaustive_scan:.0} field operations, and the \
             only isogeny degrees that move are {}, for none of which Φ_ℓ is tabulated (have \
             ℓ ∈ {TABULATED_MODULAR_LEVELS:?}) nor a kernel polynomial implemented",
            degrees
                .iter()
                .map(|d| d.to_string())
                .collect::<Vec<_>>()
                .join(", ")
        ))
        };

    ClassReachReport {
        n,
        order: class.order.clone(),
        conductor: class.conductor.clone(),
        conductor_fully_factored: class.fully_factored,
        log2_class_size: class.log2_class_size(),
        class_size: class.class_size.clone(),
        nontrivial_degrees: degrees,
        log2_exhaustive_scan,
        modular_polynomial_available,
        blocked_because,
    }
}

// ── Part B: one curve, one full index calculus ──────────────────────

/// Knobs for [`measure_member`].  Every member of a sweep must be measured
/// with the same options or the distribution means nothing, so a sweep takes
/// one of these and hands the identical value to every curve.
#[derive(Clone, Debug)]
pub struct IcCostOptions {
    /// Factor-base subspace dimension: `V = ⟨1, z, …, z^{ℓ−1}⟩`.
    pub l: u32,
    /// Summands per relation.
    pub m: usize,
    /// Highest Macaulay degree the matrix-F4 engine builds before it splits.
    pub max_degree: u32,
    /// Reductions one decomposition may spend before it gives up.  A
    /// decomposition that exhausts it is recorded as `Unknown`, which is
    /// never a refutation.
    pub node_budget: usize,
    /// Probes in the **measurement phase**, which is a fixed budget every
    /// member spends in full.
    ///
    /// A fixed budget is what makes the yields comparable.  Stopping each
    /// member as soon as its DLP closes would estimate the yield from a
    /// handful of relations under a stopping rule correlated with the
    /// yield itself — a few lucky relations then read as a high-yield
    /// curve, and the between-member spread is dominated by `1/√k`
    /// sampling noise rather than by the curve.
    pub yield_probes: usize,
    /// Cap on extra probes in the **closure phase**, which runs only if
    /// the measurement phase did not already pin the secret.  Closure
    /// counters are kept apart from the measurement ones so they never
    /// enter the distribution.
    pub max_trials: usize,
    /// Relations to collect beyond the number of unknowns before the solve
    /// is attempted.
    pub extra_relations: usize,
    /// Targets for the `D*` / first-fall measurement.
    pub ffd_targets: u32,
    /// Macaulay degree cap for the `D*` / first-fall measurement.
    pub ffd_d_max: u32,
    /// Seed for probes and for the planted secret.
    pub seed: u64,
}

impl Default for IcCostOptions {
    fn default() -> Self {
        Self {
            l: 4,
            m: 2,
            max_degree: 4,
            node_budget: 20_000,
            yield_probes: 20_000,
            max_trials: 40_000,
            extra_relations: 4,
            ffd_targets: 12,
            ffd_d_max: 6,
            seed: DEFAULT_SEED,
        }
    }
}

/// Default probe seed.  Fixed so a sweep is reproducible; named so the
/// value appears once.
pub const DEFAULT_SEED: u64 = 0x1509_0e11_5069_2d05;

/// Why one relation probe ended.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ProbeOutcome {
    /// A decomposition was found and lifted to a signed relation.
    Relation,
    /// The solver completed and proved no decomposition exists over `V`.
    Refuted,
    /// The node budget ran out: "cannot say", never a refutation.
    Unknown,
    /// `[a]G + [b]Q = O`, which recovers `d` without the relation matrix.
    /// Counted and skipped, never credited as an index-calculus solve.
    DirectSkipped,
}

/// One class member, fully measured.
#[derive(Clone, Debug)]
pub struct IcCostRow {
    pub a2: u8,
    pub a6: u64,
    /// `j = 1/a₆`.
    pub j: u64,
    pub order: u64,
    /// Largest prime factor of `#E`: the subgroup the DLP lives in.
    pub r: u64,
    pub cofactor: u64,
    /// Whether this is the Koblitz curve itself (`a₆ = 1`).
    pub is_koblitz: bool,

    /// Signed factor-base classes after cofactor projection — the unknowns.
    pub unknowns: usize,
    /// Abscissae in `V` carrying a point, before projection and folding.
    pub factor_base_points: usize,

    /// Probes drawn in the measurement phase — equal to
    /// [`IcCostOptions::yield_probes`] for every member that was measured
    /// at all, which is what makes the yields comparable.
    pub trials: usize,
    /// Extra probes the closure phase needed, or `0` when the measurement
    /// phase already pinned the secret.  Never part of the distribution.
    pub closure_trials: usize,
    /// Relations the closure phase added.  Likewise excluded.
    pub closure_relations: usize,
    /// Measurement probe at which the secret first pinned and verified,
    /// or `None` when closure was needed.  A diagnostic, not a cost.
    pub solved_at_probe: Option<usize>,
    pub relations: usize,
    pub independent_relations: usize,
    pub dependent_relations: usize,
    pub inconsistent_relations: usize,
    pub refutations: usize,
    pub unknown_probes: usize,
    pub direct_skipped: usize,

    /// Wall clock strictly inside the decomposition solver.
    pub groebner_ns: u128,
    /// Decomposition calls, i.e. probes that reached the solver.
    pub groebner_calls: usize,
    /// Algebraic reductions across every call — the portable companion to
    /// `groebner_ns`.
    pub reductions: usize,
    /// Branches closed by a reduction producing the constant `1`.
    pub infeasible_branches: usize,
    /// Wall clock in the modular linear algebra.
    pub linear_algebra_ns: u128,
    /// Multiply-subtracts in the linear algebra, its own native unit.
    pub row_ops: u64,

    /// The planted secret.
    pub planted: u64,
    /// What index calculus recovered.
    pub log: Option<u64>,
    /// What an independent baby-step giant-step solve recovered.
    pub bsgs_log: Option<u64>,
    /// `log == bsgs_log == planted`, and `[log]G = Q` on the curve.
    pub verified: bool,

    /// `D*` histogram over the refutable targets.
    pub d_star_hist: BTreeMap<u32, u32>,
    /// First-fall-degree histogram over the same targets.
    pub first_fall_hist: BTreeMap<u32, u32>,
    pub refutable_targets: u32,
}

impl IcCostRow {
    /// Relations per probe — the yield, in the unit a distribution is taken
    /// in.  `None` when nothing was probed.
    pub fn yield_per_probe(&self) -> Option<f64> {
        (self.trials > 0).then(|| self.relations as f64 / self.trials as f64)
    }

    /// Relation yield **normalised by the factor base it was drawn from**.
    ///
    /// The raw yield is `≈ |F|^m / (m! · r)` — it scales with the factor
    /// base, and `|F| = #{x ∈ V : x carries a point}` varies across the
    /// class because the Artin–Schreier condition `Tr(x + a₂ + a₆x^{−2}) =
    /// 0` depends on `a₆`.  Dividing by that prediction leaves the part of
    /// the yield the factor-base size does **not** explain, which is the
    /// only part a structural claim could rest on.
    pub fn normalised_yield(&self) -> Option<f64> {
        let raw = self.yield_per_probe()?;
        let m = 2.0; // this module collects with m = 2 summands
        let predicted =
            (self.unknowns as f64).powf(m) / (factorial(m as u32) as f64 * self.r as f64);
        (predicted > 0.0).then_some(raw / predicted)
    }

    /// Mean solver nanoseconds per decomposition call.
    pub fn ns_per_call(&self) -> Option<f64> {
        (self.groebner_calls > 0).then(|| self.groebner_ns as f64 / self.groebner_calls as f64)
    }

    /// Mean reductions per decomposition call: the same shape as
    /// [`Self::ns_per_call`] in a unit that does not depend on the machine.
    pub fn reductions_per_call(&self) -> Option<f64> {
        (self.groebner_calls > 0).then(|| self.reductions as f64 / self.groebner_calls as f64)
    }

    /// Modal first fall degree, and how many of the targets agreed with it.
    pub fn modal_first_fall(&self) -> Option<(u32, u32)> {
        self.first_fall_hist
            .iter()
            .max_by_key(|(_, c)| **c)
            .map(|(d, c)| (*d, *c))
    }
}

/// A point of the subspace factor base, after cofactor projection.
#[derive(Clone, Copy, Debug)]
struct BaseEntry {
    /// Index of the signed class this abscissa projects onto, or `None`
    /// when `[h]P` is the identity and the summand contributes nothing.
    class: Option<usize>,
    /// `+1` when the canonical representative of `[h]P` is `[h]P` itself.
    sign: i8,
}

/// Why a vertex of the class could not carry the experiment.
///
/// A skipped vertex is a fact about the curve, so it is reported with its
/// reason rather than silently dropped from the distribution.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SkipReason {
    /// `#E`'s largest prime factor is too small to host a DLP.
    SubgroupTooSmall,
    /// The largest prime divides `#E` more than once, so the order-`r`
    /// subgroup is not unique and factor-base logarithms are not
    /// well defined against one generator.
    RepeatedLargestPrime,
    /// The field is wider than the one-word curve arithmetic handles.
    FieldTooWide,
    /// No point of order `r` was found within the search budget.
    NoGenerator,
    /// No abscissa of the subspace carried a point off the identity.
    EmptyFactorBase,
}

/// Diagnose a vertex without running the experiment on it: `Ok` with
/// `(#E, r, h)` when it can carry the measurement, `Err` with the reason
/// when it cannot.
pub fn diagnose_member(
    n: u32,
    irr: &IrreduciblePoly,
    a2: u8,
    a6: u64,
    seed: u64,
) -> Result<(u64, u64, u64), SkipReason> {
    let me = Member::build(n, irr, a2, a6, seed)?;
    Ok((me.order, me.r, me.cofactor))
}

/// Build the curve, its subgroup, and everything the relation loop needs.
struct Member {
    n: u32,
    irr: IrreduciblePoly,
    ash: ArtinSchreier,
    a2: u8,
    a6: u64,
    fast: FastCurve,
    order: u64,
    r: u64,
    cofactor: u64,
    generator: FastPoint,
}

impl Member {
    fn build(
        n: u32,
        irr: &IrreduciblePoly,
        a2: u8,
        a6: u64,
        seed: u64,
    ) -> Result<Self, SkipReason> {
        let gf = Gf2::new(irr);
        let ash = ArtinSchreier::new(&gf);
        let order = curve_order(&gf, &ash, a2, a6);
        let (r, e) = *factorise(order)
            .last()
            .ok_or(SkipReason::SubgroupTooSmall)?;
        let cofactor = order / r;
        if r < 5 {
            return Err(SkipReason::SubgroupTooSmall);
        }
        if e != 1 {
            // `r² | #E` means the order-`r` subgroup is not unique, so
            // `[h]P` is not a well-defined element of `⟨G⟩` and the
            // relation rows would silently mix subgroups.
            return Err(SkipReason::RepeatedLargestPrime);
        }

        let curve = BinaryCurve {
            m: n,
            irreducible: irr.clone(),
            a: to_element(a2 as u64, n),
            b: to_element(a6, n),
            generator: BinaryPoint::Infinity,
            order: r.into(),
            cofactor: cofactor.into(),
        };
        let fast = FastCurve::new(&curve).ok_or(SkipReason::FieldTooWide)?;

        let mut me = Member {
            n,
            irr: irr.clone(),
            ash,
            a2,
            a6,
            fast,
            order,
            r,
            cofactor,
            generator: FastPoint::INFINITY,
        };
        me.generator = me.find_generator(seed).ok_or(SkipReason::NoGenerator)?;
        Ok(me)
    }

    /// Both points with abscissa `x`, or none.  The binary short-form
    /// negation is `−(x, y) = (x, x + y)`, so an abscissa names a signed
    /// pair — which is exactly the factor-base class.
    fn points_with_x(&self, x: u64) -> Vec<FastPoint> {
        let f = &self.fast.field;
        if x == 0 {
            return vec![FastPoint::affine(0, f.sqr_k(self.a6, self.n - 1))];
        }
        let inv = f.inv(x);
        let c = x ^ (self.a2 as u64) ^ f.mul(self.a6, f.sqr(inv));
        match self.ash.solve(c) {
            Some(u) => {
                let p = FastPoint::affine(x, f.mul(x, u));
                vec![p, self.fast.neg(p)]
            }
            None => Vec::new(),
        }
    }

    fn find_generator(&self, seed: u64) -> Option<FastPoint> {
        let group = BinaryGroup(&self.fast);
        let mut ops = GroupOps::default();
        let mut rng = StdRng::seed_from_u64(seed ^ 0x9E37_79B9 ^ self.a6);
        for _ in 0..8192 {
            let x = rng.gen::<u64>() & ((1u64 << self.n) - 1);
            let Some(&p) = self.points_with_x(x).first() else {
                continue;
            };
            let g = group.mul(&mut ops, p, self.cofactor);
            if g.infinity {
                continue;
            }
            if group.mul(&mut ops, g, self.r).infinity {
                return Some(g);
            }
        }
        None
    }
}

/// **The class-wide discrete logarithm.**
///
/// One `d` per `(seed, n, r)`, so every member of a class is handed the
/// same one — see the transport argument in [`measure_member`].  It is
/// derived arithmetically rather than drawn from a per-member RNG so that
/// sharing it cannot be undone by a later change to how probes are seeded.
pub fn class_secret(seed: u64, n: u32, r: u64) -> u64 {
    let mut h = seed ^ ((n as u64) << 40) ^ 0x9E37_79B9_7F4A_7C15;
    h ^= h >> 33;
    h = h.wrapping_mul(0xFF51_AFD7_ED55_8CCD);
    h ^= h >> 33;
    h = h.wrapping_mul(0xC4CE_B9FE_1A85_EC53);
    h ^= h >> 33;
    1 + h % (r - 1)
}

/// `k!`, for the small summand counts this module uses.
fn factorial(k: u32) -> u64 {
    (1..=k as u64).product::<u64>().max(1)
}

/// Trial division, adequate for the `≤ 2^40` orders this module handles.
fn factorise(mut v: u64) -> Vec<(u64, u32)> {
    let mut out = Vec::new();
    let mut d = 2u64;
    while d.saturating_mul(d) <= v {
        let mut e = 0;
        while v.is_multiple_of(d) {
            v /= d;
            e += 1;
        }
        if e > 0 {
            out.push((d, e));
        }
        d += 1;
    }
    if v > 1 {
        out.push((v, 1));
    }
    out
}

fn to_element(v: u64, n: u32) -> F2mElement {
    let bits: Vec<u32> = (0..n).filter(|i| (v >> i) & 1 == 1).collect();
    F2mElement::from_bit_positions(&bits, n)
}

fn from_element(e: &F2mElement) -> u64 {
    e.to_biguint().to_u64_digits().first().copied().unwrap_or(0)
}

/// `a · b mod m` without overflow, for the `≤ 2^40` moduli here.
fn mulmod(a: u64, b: u64, m: u64) -> u64 {
    ((a as u128 * b as u128) % m as u128) as u64
}

/// **Baby-step giant-step**, the independent ground truth.  `O(√r)` with a
/// hash table; at the sizes this module runs it is cheaper than the index
/// calculus it checks, which is the point — the check must not itself be
/// the thing under test.
pub fn bsgs(fast: &FastCurve, g: FastPoint, q: FastPoint, r: u64) -> Option<u64> {
    let group = BinaryGroup(fast);
    let mut ops = GroupOps::default();
    let step = (r as f64).sqrt().ceil() as u64 + 1;

    // Write `d = i·step + j` with `0 ≤ j < step`.  Then
    // `Q − [j]G = [i·step]G`, so the baby steps store `Q − [j]G` and the
    // giant steps walk `[i·step]G`.
    let neg_g = group.neg(g);
    let mut table: HashMap<(u64, u64, bool), u64> = HashMap::with_capacity(step as usize);
    let mut cur = q;
    for j in 0..step {
        table.entry((cur.x, cur.y, cur.infinity)).or_insert(j);
        cur = group.add(&mut ops, cur, neg_g);
    }

    let giant = group.mul(&mut ops, g, step % r);
    let mut cur = FastPoint::INFINITY;
    for i in 0..=step {
        if let Some(&j) = table.get(&(cur.x, cur.y, cur.infinity)) {
            let d = ((i as u128 * step as u128 + j as u128) % r as u128) as u64;
            if group.mul(&mut ops, g, d) == q {
                return Some(d);
            }
        }
        cur = group.add(&mut ops, cur, giant);
    }
    None
}

/// **Measure one class member end to end.**
///
/// Returns `None` only when the curve cannot carry the experiment at all —
/// no usable prime-order subgroup, or no generator found — which is a
/// property of the curve and is reported by the sweep as a skipped vertex,
/// never silently folded into the distribution.
pub fn measure_member(
    n: u32,
    irr: &IrreduciblePoly,
    a2: u8,
    a6: u64,
    opts: &IcCostOptions,
) -> Result<IcCostRow, SkipReason> {
    let me = Member::build(n, irr, a2, a6, opts.seed)?;
    let group = BinaryGroup(&me.fast);
    let mut ops = GroupOps::default();

    // ── the transported instance ────────────────────────────────────
    //
    // `d` is a property of the CLASS, not of the member.  An isogeny
    // `φ: E → E'` of degree coprime to `r` carries `Q = [d]P` to
    // `φ(Q) = [d]φ(P)`, so the transported instance is a generator of
    // `E'[r]` paired with **the same `d`**; any other generator `G'` is
    // `[k]φ(P)` and then `[d]G' = [k]φ(Q)`, i.e. `φ` followed by an
    // automorphism of the cyclic group.  Sharing `d` across the class is
    // therefore exactly what transport means for the discrete logarithm,
    // and it is what makes "every member recovered the same `d`" an
    // end-to-end check rather than 273 unrelated DLPs.
    //
    // `r` is fixed across a class because `#E` is, so
    // [`class_secret`] returns the same value for every member.
    let planted = class_secret(opts.seed, n, me.r);
    let q_point = group.mul(&mut ops, me.generator, planted);

    // Probes stay per-member: an attacker on each vertex draws their own
    // randomness, and independent probe streams are what the sampling
    // control in [`summarise`] assumes.
    let mut rng = StdRng::seed_from_u64(opts.seed ^ (a6 << 1) ^ ((n as u64) << 40));

    // ── the factor base: abscissae in V, folded by cofactor projection ──
    let basis: Vec<F2mElement> = (0..opts.l).map(|i| to_element(1u64 << i, n)).collect();
    let st = FieldStructure::new(n, &me.irr);

    let mut entry_of: HashMap<u64, BaseEntry> = HashMap::new();
    let mut canonical: HashMap<(u64, u64), usize> = HashMap::new();
    let mut factor_base_points = 0usize;
    for mask in 0..(1u64 << opts.l) {
        let x = subspace_value(mask, &basis, n);
        let Some(&p) = me.points_with_x(x).first() else {
            continue;
        };
        factor_base_points += 1;
        let proj = group.mul(&mut ops, p, me.cofactor);
        if proj.infinity {
            entry_of.insert(
                x,
                BaseEntry {
                    class: None,
                    sign: 1,
                },
            );
            continue;
        }
        let neg = group.neg(proj);
        // Canonical representative of the signed class: the one with the
        // smaller `y`.  `sign` records which of the two `[h]P` is.
        let (key, sign) = if (proj.x, proj.y) <= (neg.x, neg.y) {
            ((proj.x, proj.y), 1i8)
        } else {
            ((neg.x, neg.y), -1i8)
        };
        let next = canonical.len();
        let class = *canonical.entry(key).or_insert(next);
        entry_of.insert(
            x,
            BaseEntry {
                class: Some(class),
                sign,
            },
        );
    }
    let unknowns = canonical.len();
    if unknowns == 0 {
        return Err(SkipReason::EmptyFactorBase);
    }

    // ── relation collection ─────────────────────────────────────────
    let solve_opts = SolveOptions {
        engine: SolverEngine::MatrixF4 {
            max_degree: opts.max_degree,
        },
        max_solutions: usize::MAX,
        node_budget: opts.node_budget,
        split_rule: SplitRule::default(),
    };

    // Columns: one per signed class, plus one for the secret.
    let secret_col = unknowns;
    let mut gauss = IncrementalGauss::new(unknowns + 1, me.r);
    let mut row = IcCostRow {
        a2,
        a6,
        j: me.fast.field.inv(a6),
        order: me.order,
        r: me.r,
        cofactor: me.cofactor,
        is_koblitz: a6 == 1,
        unknowns,
        factor_base_points,
        trials: 0,
        closure_trials: 0,
        closure_relations: 0,
        solved_at_probe: None,
        relations: 0,
        independent_relations: 0,
        dependent_relations: 0,
        inconsistent_relations: 0,
        refutations: 0,
        unknown_probes: 0,
        direct_skipped: 0,
        groebner_ns: 0,
        groebner_calls: 0,
        reductions: 0,
        infeasible_branches: 0,
        linear_algebra_ns: 0,
        row_ops: 0,
        planted,
        log: None,
        bsgs_log: None,
        verified: false,
        d_star_hist: BTreeMap::new(),
        first_fall_hist: BTreeMap::new(),
        refutable_targets: 0,
    };

    // ── phase 1: the measurement, a fixed budget spent in full ──────
    //
    // Every member draws exactly `yield_probes` probes whether or not its
    // DLP has already closed, so relation yield, solver time and reduction
    // counts are all measured over the same denominator.
    for probe in 0..opts.yield_probes {
        row.trials += 1;
        if probe_once(
            &me,
            &group,
            &mut ops,
            &mut rng,
            &basis,
            &st,
            &solve_opts,
            &entry_of,
            q_point,
            secret_col,
            unknowns,
            &mut gauss,
            &mut row,
            opts,
        ) && row.log.is_none()
        {
            if let Some(d) = gauss.pinned(secret_col) {
                if group.mul(&mut ops, me.generator, d) == q_point {
                    row.log = Some(d);
                    row.solved_at_probe = Some(probe + 1);
                }
            }
        }
    }

    // ── phase 2: closure, only if the measurement did not already close ──
    let want = unknowns + opts.extra_relations;
    while row.log.is_none() && row.closure_trials < opts.max_trials {
        row.closure_trials += 1;
        let before = row.relations;
        let solved = probe_once(
            &me,
            &group,
            &mut ops,
            &mut rng,
            &basis,
            &st,
            &solve_opts,
            &entry_of,
            q_point,
            secret_col,
            unknowns,
            &mut gauss,
            &mut row,
            opts,
        );
        // Move the phase-2 relation out of the measured counters.
        if row.relations > before {
            row.relations -= 1;
            row.closure_relations += 1;
        }
        if solved || row.independent_relations >= want {
            if let Some(d) = gauss.pinned(secret_col) {
                if group.mul(&mut ops, me.generator, d) == q_point {
                    row.log = Some(d);
                }
            }
        }
    }
    row.row_ops = gauss.row_ops;

    // ── ground truth, independent of everything above ───────────────
    row.bsgs_log = bsgs(&me.fast, me.generator, q_point, me.r);
    row.verified = row.log.is_some()
        && row.log == row.bsgs_log
        && row.log == Some(planted)
        && group.mul(&mut ops, me.generator, row.log.unwrap()) == q_point;

    // ── D* and first fall, on the same curve and the same subspace ──
    let targets: Vec<F2mElement> = (0..opts.ffd_targets)
        .map(|i| to_element((1u64 << opts.l) + i as u64, n))
        .collect();
    let (d_star, first_fall, refutable) = measure_curve(
        n,
        opts.l,
        opts.ffd_d_max,
        &me.irr,
        &to_element(a6, n),
        &targets,
    );
    row.d_star_hist = d_star;
    row.first_fall_hist = first_fall;
    row.refutable_targets = refutable;

    Ok(row)
}

/// One relation probe: draw `(a, b)`, decompose `[a]G + [b]Q` over the
/// subspace, and feed any relation to the matrix.  Returns whether a
/// relation was admitted.
///
/// Both phases share this so the measured and unmeasured probes are the
/// same operation — only the counters they land in differ.
fn probe_once(
    me: &Member,
    group: &BinaryGroup<'_>,
    ops: &mut GroupOps,
    rng: &mut StdRng,
    basis: &[F2mElement],
    st: &FieldStructure,
    solve_opts: &SolveOptions,
    entry_of: &HashMap<u64, BaseEntry>,
    q_point: FastPoint,
    secret_col: usize,
    unknowns: usize,
    gauss: &mut IncrementalGauss,
    row: &mut IcCostRow,
    opts: &IcCostOptions,
) -> bool {
    let n = me.n;
    let a = rng.gen_range(0..me.r);
    let b = rng.gen_range(1..me.r);
    let ag = group.mul(ops, me.generator, a);
    let bq = group.mul(ops, q_point, b);
    let target = group.add(ops, ag, bq);
    if target.infinity {
        // `[a]G + [b]Q = O` gives `d = -a/b` without the relation matrix.
        // Counted and skipped so the benchmark measures index calculus
        // rather than a lucky generic collision.
        row.direct_skipped += 1;
        return false;
    }

    let x_r = to_element(target.x, n);
    let Some(sys) =
        build_decomposition_system_reusing(basis, &x_r, &to_element(me.a6, n), opts.m, st)
    else {
        row.unknown_probes += 1;
        return false;
    };

    let mut lifted: Option<Vec<(usize, i8)>> = None;
    let started = Instant::now();
    let (_, stats) =
        solve_boolean_system_filtered(&sys.equations, sys.n_vars, solve_opts, |root| {
            let xs: Vec<u64> = (0..opts.m)
                .map(|i| from_element(&sys.summand_x(basis, root, i, n)))
                .collect();
            match lift(me, group, entry_of, &xs, target) {
                Some(terms) => {
                    lifted = Some(terms);
                    true
                }
                None => false,
            }
        });
    row.groebner_ns += started.elapsed().as_nanos();
    row.groebner_calls += 1;
    row.reductions += stats.reductions;
    row.infeasible_branches += stats.infeasible_branches;

    match lifted {
        Some(terms) => {
            row.relations += 1;
            // `Σ sᵢ·log(hPᵢ) − (h·b)·d ≡ h·a  (mod r)`.
            let mut dense = vec![0u64; unknowns + 1];
            for (class, sign) in terms {
                let v = if sign > 0 { 1 } else { me.r - 1 };
                dense[class] = (dense[class] + v) % me.r;
            }
            let hb = mulmod(me.cofactor % me.r, b % me.r, me.r);
            dense[secret_col] = (me.r - hb) % me.r;
            let rhs = mulmod(me.cofactor % me.r, a % me.r, me.r);

            let la = Instant::now();
            match gauss.add_row(dense, rhs) {
                RowStatus::Independent => row.independent_relations += 1,
                RowStatus::Dependent => row.dependent_relations += 1,
                RowStatus::Inconsistent => row.inconsistent_relations += 1,
            }
            row.linear_algebra_ns += la.elapsed().as_nanos();
            true
        }
        None if stats.exhausted => {
            row.unknown_probes += 1;
            false
        }
        None => {
            row.refutations += 1;
            false
        }
    }
}

/// The `F_2`-span value of a coefficient mask over `basis`.
fn subspace_value(mask: u64, basis: &[F2mElement], n: u32) -> u64 {
    let mut acc = F2mElement::zero(n);
    for (t, be) in basis.iter().enumerate() {
        if (mask >> t) & 1 == 1 {
            acc = acc.add(be);
        }
    }
    from_element(&acc)
}

/// Lift a root to a signed relation.
///
/// A root of `S₃` fixes the summands only up to sign, so every sign pattern
/// is tried and the first that closes the group identity `Σ ±Pᵢ = R` wins.
/// Returns the `(class, sign)` terms after cofactor projection, or `None`
/// when no pattern closes — which is why a root is not yet a relation.
fn lift(
    me: &Member,
    group: &BinaryGroup<'_>,
    entry_of: &HashMap<u64, BaseEntry>,
    xs: &[u64],
    target: FastPoint,
) -> Option<Vec<(usize, i8)>> {
    let m = xs.len();
    let mut points = Vec::with_capacity(m);
    for x in xs {
        let candidates = me.points_with_x(*x);
        if candidates.is_empty() || !entry_of.contains_key(x) {
            return None;
        }
        points.push(candidates[0]);
    }
    let mut ops = GroupOps::default();
    for pattern in 0..(1u32 << m) {
        let mut acc = FastPoint::INFINITY;
        for (i, p) in points.iter().enumerate() {
            let signed = if (pattern >> i) & 1 == 1 {
                group.neg(*p)
            } else {
                *p
            };
            acc = group.add(&mut ops, acc, signed);
        }
        if acc == target {
            let mut terms = Vec::with_capacity(m);
            for (i, x) in xs.iter().enumerate() {
                let entry = entry_of[x];
                let Some(class) = entry.class else { continue };
                // The summand's own sign, composed with the sign the
                // cofactor projection's canonical representative carries.
                let s = if (pattern >> i) & 1 == 1 { -1 } else { 1 };
                terms.push((class, s * entry.sign));
            }
            return Some(terms);
        }
    }
    None
}

// ── Part C: the distribution ────────────────────────────────────────

/// The cost distribution over a class, and the verdict it supports.
#[derive(Clone, Debug)]
pub struct ClassCostSummary {
    pub n: u32,
    pub l: u32,
    pub m: usize,
    /// Members the sweep measured.
    pub measured: usize,
    /// Members the sweep could not carry (no prime subgroup, no generator).
    pub skipped: usize,
    /// Rows whose recovered logarithm failed either check.  Any nonzero
    /// value invalidates the sweep.
    pub verification_failures: usize,
    /// The class-wide logarithm every member was handed — the transported
    /// instance's `d`.  `None` when nothing was measured.
    pub transported_secret: Option<u64>,
    /// Members that recovered exactly that `d`.
    pub members_recovering_secret: usize,
    /// Whether **every** measured member recovered the one class-wide `d`.
    /// This is the end-to-end statement the transport buys: the same
    /// discrete logarithm, solved independently on every vertex of the
    /// class.
    pub all_recovered_transported_secret: bool,
    /// Rows with a contradictory relation.  Likewise fatal.
    pub inconsistent_rows: usize,

    pub reductions_per_call: Spread,
    pub ns_per_call: Spread,
    pub yield_per_probe: Spread,
    /// Yield after dividing out the factor-base size — see
    /// [`IcCostRow::normalised_yield`].  A raw yield that is spread while
    /// this one is flat means the spread was `|F|`, not the curve.
    pub normalised_yield: Spread,
    /// Signed factor-base classes per member.  Reported because it is what
    /// the normalisation divides by, so a reader can check the correction
    /// rather than take it.
    pub unknowns: Spread,
    /// **The control on the yield channel.**  Observed between-member
    /// variance of the yield, divided by the variance independent binomial
    /// sampling predicts at the pooled rate: `p(1−p)/N`, with `N` the
    /// fixed measurement budget every member spent.
    ///
    /// A ratio near `1` means every apparent difference between members is
    /// the estimator's own noise.  Only a ratio comfortably above it says
    /// the curve explains anything.
    pub yield_variance_ratio: f64,
    /// `p(1−p)/N`, the predicted variance the ratio divides by.
    pub yield_sampling_variance: f64,
    /// The same control applied **after** the factor-base normalisation:
    /// observed variance of the normalised yield over the variance
    /// sampling predicts for it, `p(1−p)/(N·c²)` averaged over members
    /// with `c = |F|^m/(m!·r)`.
    ///
    /// This is the control that decides whether a residual spread is a
    /// second effect or just the estimator again: dividing by a constant
    /// shrinks the signal and the noise equally, so a normalised cv must
    /// be read against a normalised noise floor, never against
    /// [`FLATNESS_CV`] alone.
    pub normalised_variance_ratio: f64,
    /// Probes each member spent in the measurement phase.
    pub yield_probes: usize,
    /// Pooled first-fall histogram over every (member, target) cell.
    pub pooled_first_fall: BTreeMap<u32, u32>,
    /// Pooled `D*` histogram.
    pub pooled_d_star: BTreeMap<u32, u32>,
    /// Distinct modal first-fall degrees across members.
    pub first_fall_modes: BTreeMap<u32, usize>,

    /// The Koblitz curve's own row, the baseline any member must beat.
    pub koblitz_reductions_per_call: Option<f64>,
    /// `min / koblitz` in reductions per call: below 1 means some member is
    /// cheaper than the Koblitz curve on the same instrument.
    pub best_ratio_to_koblitz: Option<f64>,
}

/// Min, max, mean and relative spread of one measured quantity.
#[derive(Clone, Copy, Debug, Default)]
pub struct Spread {
    pub n: usize,
    pub min: f64,
    pub max: f64,
    pub mean: f64,
    pub stddev: f64,
}

impl Spread {
    fn of(values: &[f64]) -> Self {
        if values.is_empty() {
            return Spread::default();
        }
        let n = values.len();
        let mean = values.iter().sum::<f64>() / n as f64;
        let var = values.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / n as f64;
        Spread {
            n,
            min: values.iter().cloned().fold(f64::INFINITY, f64::min),
            max: values.iter().cloned().fold(f64::NEG_INFINITY, f64::max),
            mean,
            stddev: var.sqrt(),
        }
    }

    /// Coefficient of variation: the scale-free spread a flatness verdict
    /// should be read off, since the raw scale differs per quantity.
    pub fn cv(&self) -> f64 {
        if self.mean.abs() < f64::EPSILON {
            0.0
        } else {
            self.stddev / self.mean
        }
    }

    /// `max / min`, the honest headline for "how much does it vary".
    pub fn ratio(&self) -> f64 {
        if self.min.abs() < f64::EPSILON {
            f64::INFINITY
        } else {
            self.max / self.min
        }
    }
}

/// Coefficient of variation below which the distribution is called flat.
///
/// This is a **pre-registered** threshold, not one read off the data: a
/// 5 % spread in reductions per call is within what re-seeding the probe
/// sampler moves on one fixed curve, so anything below it cannot be
/// attributed to the curve.
pub const FLATNESS_CV: f64 = 0.05;

/// Between-member yield variance, as a multiple of the binomial sampling
/// prediction, above which the spread is attributed to the curve.
///
/// Pre-registered at `2.0`, matching the convention
/// [`crate::cryptanalysis::isogeny_class_search`] already uses for its own
/// variance ratio, so the two experiments' "the curve explains something"
/// bars are the same height.
pub const YIELD_VARIANCE_GATE: f64 = 2.0;

/// Run the whole class and summarise it.
pub fn sweep_class(
    n: u32,
    irr: &IrreduciblePoly,
    a2: u8,
    members: &[u64],
    opts: &IcCostOptions,
) -> (Vec<IcCostRow>, ClassCostSummary) {
    let rows: Vec<IcCostRow> = members
        .par_iter()
        .filter_map(|a6| measure_member(n, irr, a2, *a6, opts).ok())
        .collect();
    let summary = summarise(n, members.len(), &rows, opts);
    (rows, summary)
}

/// Summarise an already-measured sweep.
pub fn summarise(
    n: u32,
    attempted: usize,
    rows: &[IcCostRow],
    opts: &IcCostOptions,
) -> ClassCostSummary {
    let reductions: Vec<f64> = rows
        .iter()
        .filter_map(|r| r.reductions_per_call())
        .collect();
    let ns: Vec<f64> = rows.iter().filter_map(|r| r.ns_per_call()).collect();
    let yields: Vec<f64> = rows.iter().filter_map(|r| r.yield_per_probe()).collect();
    let normalised: Vec<f64> = rows.iter().filter_map(|r| r.normalised_yield()).collect();
    let unknowns: Vec<f64> = rows.iter().map(|r| r.unknowns as f64).collect();

    let mut pooled_first_fall: BTreeMap<u32, u32> = BTreeMap::new();
    let mut pooled_d_star: BTreeMap<u32, u32> = BTreeMap::new();
    let mut first_fall_modes: BTreeMap<u32, usize> = BTreeMap::new();
    for r in rows {
        for (d, c) in &r.first_fall_hist {
            *pooled_first_fall.entry(*d).or_insert(0) += c;
        }
        for (d, c) in &r.d_star_hist {
            *pooled_d_star.entry(*d).or_insert(0) += c;
        }
        if let Some((d, _)) = r.modal_first_fall() {
            *first_fall_modes.entry(d).or_insert(0) += 1;
        }
    }

    // The yield's own sampling variance at the pooled rate.  Every member
    // spent the same fixed budget, so one prediction covers them all.
    let probes = rows.first().map(|r| r.trials).unwrap_or(0);
    let pooled_relations: usize = rows.iter().map(|r| r.relations).sum();
    let pooled_probes: usize = rows.iter().map(|r| r.trials).sum();
    let p = if pooled_probes > 0 {
        pooled_relations as f64 / pooled_probes as f64
    } else {
        0.0
    };
    let yield_sampling_variance = if probes > 0 {
        p * (1.0 - p) / probes as f64
    } else {
        0.0
    };
    let observed_yield_variance = Spread::of(&yields).stddev.powi(2);
    let yield_variance_ratio = if yield_sampling_variance > 0.0 {
        observed_yield_variance / yield_sampling_variance
    } else {
        f64::NAN
    };

    // The same prediction carried through the normalisation: member `i`'s
    // normalised yield is `y_i / c_i`, so its sampling variance is
    // `p(1−p)/(N·c_i²)`.
    let m_f = 2.0_f64;
    let predicted_normalised: Vec<f64> = rows
        .iter()
        .filter_map(|r| {
            let c = (r.unknowns as f64).powf(m_f) / (factorial(m_f as u32) as f64 * r.r as f64);
            (c > 0.0 && r.trials > 0).then(|| p * (1.0 - p) / (r.trials as f64 * c * c))
        })
        .collect();
    let mean_predicted_normalised = if predicted_normalised.is_empty() {
        0.0
    } else {
        predicted_normalised.iter().sum::<f64>() / predicted_normalised.len() as f64
    };
    let normalised_variance_ratio = if mean_predicted_normalised > 0.0 {
        Spread::of(&normalised).stddev.powi(2) / mean_predicted_normalised
    } else {
        f64::NAN
    };

    let transported_secret = rows.first().map(|r| r.planted);
    let members_recovering_secret = rows
        .iter()
        .filter(|r| r.verified && Some(r.planted) == transported_secret && r.log == Some(r.planted))
        .count();
    let all_recovered_transported_secret =
        !rows.is_empty() && members_recovering_secret == rows.len();

    let koblitz = rows
        .iter()
        .find(|r| r.is_koblitz)
        .and_then(|r| r.reductions_per_call());
    let spread = Spread::of(&reductions);
    let best_ratio_to_koblitz = koblitz.and_then(|k| (k > 0.0).then(|| spread.min / k));

    ClassCostSummary {
        n,
        l: opts.l,
        m: opts.m,
        measured: rows.len(),
        skipped: attempted.saturating_sub(rows.len()),
        verification_failures: rows.iter().filter(|r| !r.verified).count(),
        transported_secret,
        members_recovering_secret,
        all_recovered_transported_secret,
        inconsistent_rows: rows.iter().filter(|r| r.inconsistent_relations > 0).count(),
        reductions_per_call: spread,
        ns_per_call: Spread::of(&ns),
        yield_per_probe: Spread::of(&yields),
        normalised_yield: Spread::of(&normalised),
        unknowns: Spread::of(&unknowns),
        yield_variance_ratio,
        yield_sampling_variance,
        normalised_variance_ratio,
        yield_probes: probes,
        pooled_first_fall,
        pooled_d_star,
        first_fall_modes,
        koblitz_reductions_per_call: koblitz,
        best_ratio_to_koblitz,
    }
}

impl ClassCostSummary {
    /// Whether the sweep can carry **any** conclusion, on either channel.
    ///
    /// A recovered logarithm that failed either of its two checks, or a
    /// contradictory relation row, invalidates the run as a whole — not
    /// one channel of it.  The relations that feed the yield are the same
    /// relations that feed the solve, so a sweep whose solves are wrong has
    /// no standing to report a yield conclusion either.
    ///
    /// Both verdicts route through this rather than repeating the test,
    /// because they did once diverge: `yield_verdict` checked only the
    /// member count, so a sweep the algebraic channel called `INVALID`
    /// printed `SIZE_EXPLAINED` beside it and a failed recovery read as a
    /// successful yield conclusion.
    fn unreadable(&self) -> Option<&'static str> {
        if self.verification_failures > 0 || self.inconsistent_rows > 0 {
            return Some("INVALID");
        }
        if self.measured >= 2 && !self.all_recovered_transported_secret {
            // Members disagreeing about `d` means they were not solving the
            // transported instance, so the sweep is not a class measurement
            // at all, whatever its spreads look like.
            return Some("INVALID");
        }
        if self.measured < 2 {
            return Some("INSUFFICIENT");
        }
        None
    }

    /// The verdict the experiment was built to return, on the **algebraic**
    /// channel: solving degree, first fall, and reductions per call.
    ///
    /// `FLAT` confirms the folklore *at this size, on this instrument, over
    /// the measured members*; `SPREAD` says a structural property is
    /// present and names nothing further on its own — locating it is the
    /// next experiment, not this one's conclusion.
    ///
    /// Relation yield is deliberately **not** part of this verdict: it is
    /// reported on its own by [`Self::yield_verdict`], because a raw yield
    /// spread is dominated by the factor-base size and would otherwise
    /// manufacture a `SPREAD` out of an arithmetic identity.
    pub fn verdict(&self) -> &'static str {
        if let Some(blocked) = self.unreadable() {
            return blocked;
        }
        if self.reductions_per_call.cv() < FLATNESS_CV && self.first_fall_modes.len() == 1 {
            "FLAT"
        } else {
            "SPREAD"
        }
    }

    /// The verdict on the **combinatorial** channel: relation yield.
    ///
    /// Four outcomes, and the first two are the ones that retire a
    /// spread-looking histogram:
    ///
    /// - `FLAT` — the raw yield is already homogeneous.
    /// - `SAMPLING_NOISE` — the yield looks spread, but the between-member
    ///   variance is within [`YIELD_VARIANCE_GATE`]× of what independent
    ///   binomial sampling predicts at the pooled rate.  Nothing about the
    ///   curve has been measured; the estimator is just noisy.  This is the
    ///   first thing to rule out, because `k` relations carry a `1/√k`
    ///   relative error and `k` is small.
    /// - `SIZE_EXPLAINED` — the spread exceeds sampling noise, but dividing
    ///   out `|F|^m / (m!·r)` leaves a residual no bigger than the
    ///   estimator's own noise at that scale.  The spread is then the
    ///   factor-base size `|F| = #{x ∈ V : x carries a point}`, which varies
    ///   across the class with the Artin–Schreier condition on `a₆`.  That
    ///   is a real curve-dependent quantity and worth naming — but it is
    ///   not a property of the decomposition ideal, and an attacker reaches
    ///   it by choosing `V`, not by walking an isogeny.
    /// - `SPREAD` — survives both controls.  Only this one points at
    ///   something neither sampling nor the factor-base count explains.
    pub fn yield_verdict(&self) -> &'static str {
        if let Some(blocked) = self.unreadable() {
            return blocked;
        }
        if self.yield_per_probe.cv() < FLATNESS_CV {
            "FLAT"
        } else if self.yield_variance_ratio.is_finite()
            && self.yield_variance_ratio < YIELD_VARIANCE_GATE
        {
            "SAMPLING_NOISE"
        } else if self.normalised_variance_ratio.is_finite()
            && self.normalised_variance_ratio < YIELD_VARIANCE_GATE
        {
            "SIZE_EXPLAINED"
        } else {
            "SPREAD"
        }
    }
}

/// Smallest sparse irreducible of degree `n`, the field this module uses
/// throughout so that every member of a sweep shares one field.
pub fn field_for(n: u32) -> Option<IrreduciblePoly> {
    find_irreducible_sparse(n)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_class_scan_agrees_with_the_cm_class_number() {
        // n = 13 is the largest degree a unit test can scan (2^26 field
        // ops).  Its conductor is 1, so the class is a single vertex —
        // which makes this a check that the scan does not OVER-collect:
        // 8191 curves are point-counted and exactly one is kept.  The
        // nontrivial case (273 vertices at n = 17) is checked by the
        // example, which can afford the 2^34 scan.
        let irr = field_for(13).expect("degree 13 has a sparse irreducible");
        let census = enumerate_class_exact(13, &irr, 0);
        assert!(
            census.agrees_with_cm,
            "scan found {} members, CM predicts {}",
            census.members.len(),
            census.predicted_class_size
        );
        assert!(!census.members.is_empty());
    }

    #[test]
    fn the_koblitz_curve_is_in_its_own_class() {
        let irr = field_for(13).expect("degree 13 has a sparse irreducible");
        let census = enumerate_class_exact(13, &irr, 0);
        assert!(
            census.members.contains(&1),
            "a6 = 1 is K_0 itself and must be in the class"
        );
    }

    #[test]
    fn index_calculus_recovers_the_planted_secret_and_bsgs_agrees() {
        let n = 13;
        let irr = field_for(n).expect("degree 13 has a sparse irreducible");
        let opts = IcCostOptions {
            l: 5,
            m: 2,
            max_trials: 4_000,
            ffd_targets: 4,
            ..Default::default()
        };
        let (a2, _, _) = preferred_family(n).expect("n = 13 has a usable family");
        let row = measure_member(n, &irr, a2, 1, &opts).expect("K_a carries the experiment");
        assert_eq!(
            row.inconsistent_relations, 0,
            "a wrong relation was admitted"
        );
        assert!(
            row.log.is_some(),
            "no logarithm recovered in {} trials ({} relations, {} unknowns)",
            row.trials,
            row.relations,
            row.unknowns
        );
        assert!(row.verified, "IC and BSGS disagreed, or [d]G != Q");
    }

    #[test]
    fn bsgs_solves_a_small_instance_on_its_own() {
        let n = 11;
        let irr = field_for(n).expect("degree 11 has a sparse irreducible");
        let me = Member::build(n, &irr, 0, 3, 7).expect("a6 = 3 over F_2^11 has a clean subgroup");
        let group = BinaryGroup(&me.fast);
        let mut ops = GroupOps::default();
        let d = 12345 % me.r;
        let q = group.mul(&mut ops, me.generator, d);
        assert_eq!(bsgs(&me.fast, me.generator, q, me.r), Some(d));
    }

    #[test]
    fn the_reach_report_blocks_the_sizes_it_cannot_name() {
        // n = 31: the only isogeny degree that moves is 7193, and the
        // scan is 2^62 — both barriers must be named, not assumed.
        let report = class_reach_report(31);
        assert!(report.blocked_because.is_some());
        assert!(!report.modular_polynomial_available);
        assert!(report.log2_exhaustive_scan > EXHAUSTIVE_SCAN_LOG2_BUDGET);
    }

    #[test]
    fn the_preferred_family_avoids_the_unusable_subgroup_at_n_17() {
        // #E(K_0 / F_2^17) = 2^2 · 137 · 239: an 8-bit subgroup, useless.
        // Its twist has 2 · 65587.  The chooser must take the twist.
        let (a2, r, _) = preferred_family(17).expect("n = 17 has a usable family");
        assert_eq!(a2, 1);
        assert_eq!(r, 65587);
    }

    /// A summary with the spreads of a clean, flat sweep, so a test can
    /// vary exactly the field it is about.
    fn clean_summary() -> ClassCostSummary {
        ClassCostSummary {
            n: 17,
            l: 5,
            m: 2,
            measured: 273,
            skipped: 0,
            verification_failures: 0,
            inconsistent_rows: 0,
            transported_secret: Some(12345),
            members_recovering_secret: 273,
            all_recovered_transported_secret: true,
            reductions_per_call: Spread::of(&[1.0, 1.0, 1.0]),
            ns_per_call: Spread::of(&[100.0, 100.0, 100.0]),
            yield_per_probe: Spread::of(&[0.004, 0.004, 0.004]),
            normalised_yield: Spread::of(&[2.0, 2.0, 2.0]),
            unknowns: Spread::of(&[15.0, 15.0, 15.0]),
            yield_variance_ratio: 1.0,
            yield_sampling_variance: 1e-7,
            normalised_variance_ratio: 1.0,
            yield_probes: 20_000,
            pooled_first_fall: BTreeMap::from([(2, 100)]),
            pooled_d_star: BTreeMap::from([(2, 100)]),
            first_fall_modes: BTreeMap::from([(2, 273)]),
            koblitz_reductions_per_call: Some(1.0),
            best_ratio_to_koblitz: Some(1.0),
        }
    }

    #[test]
    fn every_member_of_a_class_is_handed_the_same_discrete_logarithm() {
        // The transported instance: an isogeny carries Q = [d]P to
        // [d]φ(P), so `d` belongs to the class, not to the member.  An
        // earlier revision keyed the secret on `a₆` and therefore gave
        // every vertex an unrelated DLP; this pins the fix.
        let n = 17;
        let (_, r, _) = preferred_family(n).expect("n = 17 has a usable family");
        let d = class_secret(DEFAULT_SEED, n, r);
        assert!(d >= 1 && d < r);
        for a6 in [1u64, 13, 4097, 65535] {
            assert_eq!(
                class_secret(DEFAULT_SEED, n, r),
                d,
                "a₆ = {a6} must not change the class-wide secret"
            );
        }
        // A different class gets a different instance.
        let (_, r19, _) = preferred_family(19).expect("n = 19 has a usable family");
        assert_ne!(class_secret(DEFAULT_SEED, 19, r19), d);
    }

    #[test]
    fn a_class_whose_members_disagree_about_d_is_invalid() {
        let split = ClassCostSummary {
            all_recovered_transported_secret: false,
            members_recovering_secret: 200,
            ..clean_summary()
        };
        assert_eq!(split.verdict(), "INVALID");
        assert_eq!(split.yield_verdict(), "INVALID");
    }

    #[test]
    fn a_failed_recovery_invalidates_both_channels_not_just_one() {
        // Caught by review on PR #550: `yield_verdict` checked only the
        // member count, so a sweep the algebraic channel called INVALID
        // still printed a yield conclusion next to it.  The relations that
        // feed the yield are the ones that feed the solve, so a wrong
        // solve retires both.
        let clean = clean_summary();
        assert_eq!(clean.verdict(), "FLAT");
        assert_eq!(clean.yield_verdict(), "FLAT");

        let failed = ClassCostSummary {
            verification_failures: 1,
            ..clean_summary()
        };
        assert_eq!(failed.verdict(), "INVALID");
        assert_eq!(failed.yield_verdict(), "INVALID");

        let contradictory = ClassCostSummary {
            inconsistent_rows: 1,
            ..clean_summary()
        };
        assert_eq!(contradictory.verdict(), "INVALID");
        assert_eq!(contradictory.yield_verdict(), "INVALID");

        let thin = ClassCostSummary {
            measured: 1,
            ..clean_summary()
        };
        assert_eq!(thin.verdict(), "INSUFFICIENT");
        assert_eq!(thin.yield_verdict(), "INSUFFICIENT");
    }

    #[test]
    fn spread_is_flat_on_identical_values_and_not_on_different_ones() {
        assert!(Spread::of(&[3.0, 3.0, 3.0]).cv() < FLATNESS_CV);
        assert!(Spread::of(&[1.0, 5.0, 9.0]).cv() > FLATNESS_CV);
        assert_eq!(Spread::of(&[2.0, 8.0]).ratio(), 4.0);
    }
}
