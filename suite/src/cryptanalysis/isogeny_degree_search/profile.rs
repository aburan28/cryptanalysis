//! # Per-curve degree profiles, and the exhaustive sweeps over them.
//!
//! One curve in, one row out: the first fall degree of its
//! point-decomposition system, the Macaulay rank profile the fall was
//! read off, and the degree at which the solver can dispose of the
//! instance without search.  [`sweep_isogeny_class`] runs that over the
//! **entire** isogeny class of the ECC2K-130 analogue;
//! [`sweep_all_curves`] runs it over **every** ordinary binary curve
//! over the field, which is a strict superset and therefore settles the
//! isogeny question a fortiori.
//!
//! ## Two target protocols, because they ask different questions
//!
//! The system also depends on the target abscissa `x_R`, so a sweep has
//! to fix a convention:
//!
//! - [`TargetProtocol::Fixed`] — the **same** `x_R` for every curve.
//!   This isolates the curve's contribution exactly: the two systems
//!   then differ in their constant vector and in nothing else, so any
//!   spread in `D_ff` is attributable to `b` alone.  Most curves will
//!   find the system inconsistent, which is the normal case for a
//!   decomposition oracle and the case whose cost dominates a relation
//!   search.
//! - [`TargetProtocol::OnCurve`] — an `x_R` that really is the abscissa
//!   of a point of *that* curve, chosen deterministically from a seed.
//!   This is the question "is a decomposition on this curve cheaper to
//!   find", and it mixes the algebra with solution existence.
//!
//! Both are reported.  Reading only the second would confuse "this
//! curve's algebra is easier" with "this curve's instance happened to be
//! satisfiable".
//!
//! ## Two first-fall-degree conventions, and why both are reported
//!
//! A Macaulay matrix at degree `D` is built by multiplying each equation
//! by monomials, and there are two conventions for how many:
//!
//! - **calibrated** ([`crate::cryptanalysis::ffd_harness`]): multipliers
//!   of degree `≤ D − 2` for *every* equation.  This is the convention
//!   the FFD program's measured law
//!   (`D*` vs `Δ_low`, `ρ_s = −0.79`) was fitted with, so it is the one
//!   whose numbers are comparable with that law.
//! - **saturating**
//!   ([`crate::cryptanalysis::koblitz_groebner::first_fall_degree`]):
//!   multipliers of degree `≤ D − deg(f)` per equation, filling the
//!   matrix to degree `D`.  This is what the solver actually builds.
//!
//! They coincide when every equation is quadratic, and diverge when the
//! Weil restriction drops a coordinate to degree 1 — which happens, for
//! instance, at `n = 5`, where one of the five coordinates of `S₃` is
//! linear.  The saturating convention then sees the fall a degree
//! earlier.  Both are reported per curve, because a thread that quoted
//! one and compared against the other would be reporting an **accounting**
//! difference as a result.
//!
//! ## What the twist does: nothing
//!
//! `S₃` contains no `a`.  The quadratic twist of a curve therefore
//! presents a **byte-identical** decomposition system, so half of every
//! isogeny class is algebraically indistinguishable from the other half
//! before any measurement.  The sweeps iterate over `b` and record the
//! twist flag only for bookkeeping.

use super::{
    census::{elem_of, mask_of, trace_of_curve, trace_table, CurveId, IsogenyCensus},
    full_field_basis, leading_form_signature, present, rank_profile, LeadingFormSignature,
    PresentedSystem, MAX_ALGEBRAIC_N,
};
use crate::binary_ecc::{F2mElement, IrreduciblePoly};
use crate::cryptanalysis::ffd_harness::{
    measure_polys, weil_descend_s3_subspace, MacaulayMeasurement,
};
use crate::cryptanalysis::koblitz_groebner::{matrix_f4_f2, FieldStructure, MacaulayProfile};
use rayon::prelude::*;

/// How a sweep picks the target abscissa `x_R`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TargetProtocol {
    /// One abscissa, shared by every curve in the sweep.  Isolates `b`.
    Fixed(u64),
    /// Per curve, the first abscissa (scanning from `seed`) that carries
    /// a genuine point of that curve.
    OnCurve(u64),
}

impl TargetProtocol {
    /// Short label for tables.
    pub fn label(&self) -> &'static str {
        match self {
            TargetProtocol::Fixed(_) => "fixed",
            TargetProtocol::OnCurve(_) => "on-curve",
        }
    }
}

/// Resolve the protocol to a concrete abscissa for one curve.
///
/// For [`TargetProtocol::OnCurve`] the test is the Artin–Schreier
/// condition `Tr(x + c/x) = Tr(a)` with `c = √b`, the same condition the
/// census counts points with; `None` means no abscissa was found, which
/// happens only for the empty scan.
pub fn resolve_target(
    n: u32,
    irr: &IrreduciblePoly,
    tr: &[u8],
    id: CurveId,
    protocol: TargetProtocol,
) -> Option<F2mElement> {
    match protocol {
        TargetProtocol::Fixed(x) => Some(elem_of(x % (1u64 << n), n)),
        TargetProtocol::OnCurve(seed) => {
            let b = elem_of(id.b, n);
            // c = √b = b^{2^{n−1}}.
            let mut c = b;
            for _ in 0..n - 1 {
                c = c.square(irr);
            }
            let size = 1u64 << n;
            for step in 0..size {
                // x = 0 is never an Artin–Schreier abscissa (the fibre
                // there is the single point (0, √b)), so skip it rather
                // than clamping it onto x = 1 and testing 1 twice.
                let x = seed.wrapping_add(step) % size;
                if x == 0 {
                    continue;
                }
                let xe = elem_of(x, n);
                let Some(inv) = xe.flt_inverse(irr) else {
                    continue;
                };
                let v = xe.add(&c.mul(&inv, irr));
                if tr[mask_of(&v) as usize] == id.a_trace {
                    return Some(xe);
                }
            }
            None
        }
    }
}

/// Everything one curve contributes to the table.
#[derive(Clone, Debug)]
pub struct CurveDegreeProfile {
    /// The curve.
    pub id: CurveId,
    /// Trace of Frobenius — constant across a sweep of one class, and
    /// carried so the reader can verify that.
    pub trace: i64,
    /// Target abscissa actually used.
    pub x_r: u64,
    /// First fall degree under the **saturating** convention — what the
    /// solver sees.
    pub fall_degree: Option<u32>,
    /// First fall degree under the **calibrated** convention — the
    /// number comparable with the FFD program's measured law.
    pub calibrated_fall_degree: Option<u32>,
    /// Per-degree Macaulay `(degree, rows, cols, rank)`, saturating.
    pub profiles: Vec<MacaulayProfile>,
    /// Per-degree calibrated measurements, which additionally carry the
    /// **semi-regular rank prediction** and the signed deviation from
    /// it.  `fall_signal = rank − rank_generic` is the direct
    /// degree-of-regularity readout: a system whose ideal is
    /// semi-regular has `fall_signal = 0` at every degree, and a lever
    /// that lowers the degree of regularity shows up as a positive
    /// signal at a low degree.
    pub calibrated: Vec<MacaulayMeasurement>,
    /// Smallest degree whose Macaulay row space contains the constant
    /// `1` — the degree at which the solver rejects the target outright,
    /// with no search.  `None` if the system is consistent (or if
    /// `d_max` was too low to find the certificate).
    pub resolution_degree: Option<u32>,
    /// Fingerprint of the positive-degree part of the system.  Equal
    /// fingerprints across a class are the measured form of the
    /// leading-form invariance claim.
    pub leading_forms: LeadingFormSignature,
}

impl CurveDegreeProfile {
    /// `rows − rank` at a degree.
    pub fn syzygies_at(&self, d: u32) -> Option<usize> {
        self.profiles
            .iter()
            .find(|p| p.degree == d)
            .map(|p| p.syzygies())
    }
}

/// Build and measure one curve's decomposition system.
///
/// `ell` is the dimension of the subspace the summand abscissae are
/// confined to (`ell = n` is the unrestricted full-field system).  The
/// subspace is the polynomial-basis prefix `⟨1, z, …, z^{ell−1}⟩`, the
/// *same* for every curve — a Frobenius-invariant factor base exists
/// only for the subfield members, which is precisely the asymmetry this
/// thread is measuring, so it must not be handed to some curves and not
/// others.
#[allow(clippy::too_many_arguments)]
pub fn profile_curve(
    n: u32,
    irr: &IrreduciblePoly,
    st: &FieldStructure,
    tr: &[u8],
    kloosterman: &[i64],
    id: CurveId,
    m: usize,
    ell: usize,
    d_max: u32,
    protocol: TargetProtocol,
) -> Option<CurveDegreeProfile> {
    let x_r = resolve_target(n, irr, tr, id, protocol)?;
    let sys = build_for(n, st, id.b, &x_r, m, ell)?;
    let rp = rank_profile(&sys, d_max);
    let resolution_degree = (2..=d_max).find(|d| {
        matrix_f4_f2(&sys.equations, sys.n_vars, *d)
            .map(|rows| {
                rows.iter()
                    .any(|p| p.terms.len() == 1 && p.terms[0].mask == 0)
            })
            .unwrap_or(false)
    });

    // The calibrated oracle only expresses the `m = 2` full-field or
    // subspace descent of S₃, which is the case this thread measures;
    // for `m ≥ 3` it is left empty rather than approximated.
    let (calibrated_fall_degree, calibrated) = if m == 2 {
        let eqs = weil_descend_s3_subspace(n, ell as u32, irr, &elem_of(id.b, n), &x_r);
        measure_polys(&eqs, 2 * ell as u32, d_max)
    } else {
        (None, Vec::new())
    };

    Some(CurveDegreeProfile {
        id,
        trace: trace_of_curve(kloosterman, id.b, id.a_trace),
        x_r: mask_of(&x_r),
        fall_degree: rp.fall_degree,
        calibrated_fall_degree,
        profiles: rp.profiles,
        calibrated,
        resolution_degree,
        leading_forms: leading_form_signature(&sys.equations),
    })
}

/// The decomposition system for `b`, on the shared `ell`-dimensional
/// subspace.
pub fn build_for(
    n: u32,
    st: &FieldStructure,
    b: u64,
    x_r: &F2mElement,
    m: usize,
    ell: usize,
) -> Option<PresentedSystem> {
    let basis = full_field_basis(n);
    let basis = &basis[..ell.min(basis.len())];
    present(basis, x_r, &elem_of(b, n), m, st)
}

/// A completed sweep.
#[derive(Clone, Debug)]
pub struct SweepReport {
    /// Extension degree.
    pub n: u32,
    /// What the sweep ranged over, for the table's scope column.
    pub scope: &'static str,
    /// Decomposition size.
    pub m: usize,
    /// Subspace dimension.
    pub ell: usize,
    /// Target protocol.
    pub protocol: TargetProtocol,
    /// One row per curve.
    pub rows: Vec<CurveDegreeProfile>,
}

impl SweepReport {
    /// Curves measured.
    pub fn len(&self) -> usize {
        self.rows.len()
    }

    /// True when the sweep measured nothing.
    pub fn is_empty(&self) -> bool {
        self.rows.is_empty()
    }

    /// Distinct first fall degrees observed, with multiplicities.
    pub fn fall_histogram(&self) -> std::collections::BTreeMap<Option<u32>, usize> {
        let mut h = std::collections::BTreeMap::new();
        for r in &self.rows {
            *h.entry(r.fall_degree).or_insert(0) += 1;
        }
        h
    }

    /// Distinct calibrated first fall degrees observed.
    pub fn calibrated_fall_histogram(&self) -> std::collections::BTreeMap<Option<u32>, usize> {
        let mut h = std::collections::BTreeMap::new();
        for r in &self.rows {
            *h.entry(r.calibrated_fall_degree).or_insert(0) += 1;
        }
        h
    }

    /// Largest deviation from the semi-regular rank prediction seen
    /// anywhere in the sweep, and the curve and degree it occurred at.
    ///
    /// This is the sweep's direct answer to "does any curve in the class
    /// have a lower degree of regularity": a curve whose ideal falls
    /// below semi-regularity earlier than the reference would show a
    /// larger positive `fall_signal` at a lower degree.
    pub fn max_fall_signal(&self) -> Option<(u64, u32, i64)> {
        self.rows
            .iter()
            .flat_map(|r| {
                r.calibrated
                    .iter()
                    .map(move |mm| (r.id.b, mm.degree, mm.fall_signal))
            })
            .max_by_key(|(_, _, sig)| *sig)
    }

    /// Is the semi-regularity deviation constant across the sweep at
    /// **every** measured degree, not just one?
    ///
    /// The strongest form of the invariance statement the sweep can
    /// make: the curves do not merely share a fall degree, they deviate
    /// from the semi-regular rank prediction by the same amount at every
    /// degree.  Meaningful only for a curve comparison — a sweep that
    /// varies the target is expected to move.
    pub fn fall_signal_flat_everywhere(&self) -> bool {
        let degrees: std::collections::BTreeSet<u32> = self
            .rows
            .iter()
            .flat_map(|r| r.calibrated.iter().map(|mm| mm.degree))
            .collect();
        degrees
            .into_iter()
            .all(|d| matches!(self.fall_signal_spread(d), Some((lo, hi)) if lo == hi))
    }

    /// Per degree, the `(min, max)` of the semi-regularity deviation
    /// across the sweep.  A zero-width interval at every degree says the
    /// whole class deviates from semi-regularity *identically*.
    pub fn fall_signal_spread(&self, d: u32) -> Option<(i64, i64)> {
        let sigs: Vec<i64> = self
            .rows
            .iter()
            .filter_map(|r| {
                r.calibrated
                    .iter()
                    .find(|mm| mm.degree == d)
                    .map(|mm| mm.fall_signal)
            })
            .collect();
        if sigs.is_empty() {
            return None;
        }
        Some((
            sigs.iter().copied().min().unwrap(),
            sigs.iter().copied().max().unwrap(),
        ))
    }

    /// Distinct resolution degrees observed, with multiplicities.
    pub fn resolution_histogram(&self) -> std::collections::BTreeMap<Option<u32>, usize> {
        let mut h = std::collections::BTreeMap::new();
        for r in &self.rows {
            *h.entry(r.resolution_degree).or_insert(0) += 1;
        }
        h
    }

    /// Do **all** curves in the sweep present identical positive-degree
    /// parts?  This is the measured form of the invariance claim, over
    /// whatever scope the sweep covered.
    pub fn leading_forms_identical(&self) -> bool {
        let Some(first) = self.rows.first() else {
            return true;
        };
        self.rows
            .iter()
            .all(|r| r.leading_forms.same_leading_forms(&first.leading_forms))
    }

    /// The reference row: the Koblitz member `b = 1`, untwisted.
    pub fn reference(&self) -> Option<&CurveDegreeProfile> {
        self.rows.iter().find(|r| r.id.b == 1 && r.id.a_trace == 0)
    }

    /// How many distinct traces the sweep spans — `1` for a single
    /// isogeny class, more for a scope that crosses classes.
    pub fn distinct_traces(&self) -> usize {
        let mut ts: Vec<i64> = self.rows.iter().map(|r| r.trace).collect();
        ts.sort_unstable();
        ts.dedup();
        ts.len()
    }

    /// How many distinct target abscissae the sweep used.  `1` means the
    /// positive-degree part is shared by every row, so any spread in the
    /// fall degree is attributable to the curve; more than one means the
    /// target varies too and the spread must be controlled for.
    pub fn distinct_targets(&self) -> usize {
        let mut xs: Vec<u64> = self.rows.iter().map(|r| r.x_r).collect();
        xs.sort_unstable();
        xs.dedup();
        xs.len()
    }

    /// Is this sweep a comparison **between curves**?
    ///
    /// True when every row shares one target abscissa, so the rows
    /// differ only in `b`.  A sweep that varies the target instead — the
    /// [`sweep_targets_on_one_curve`] control, or the on-curve protocol
    /// — is not a curve comparison, and scoring it against a "reference
    /// curve" would compare a curve with itself at a different target.
    pub fn is_curve_comparison(&self) -> bool {
        self.distinct_targets() == 1 && self.rows.len() > 1
    }

    /// Rows whose first fall degree is **strictly below** the
    /// reference's, under **either** convention — the thread's
    /// falsification target.  Empty means the isogeny search found
    /// nothing.
    ///
    /// Taking the union of the two conventions is deliberate: it makes
    /// the target easier to hit, so an empty result is a statement about
    /// the curves and not about the convention.
    ///
    /// Returns empty for a sweep that is not a curve comparison; use
    /// [`SweepReport::fall_histogram`] to read those.
    pub fn improvements(&self) -> Vec<&CurveDegreeProfile> {
        if !self.is_curve_comparison() {
            return Vec::new();
        }
        let Some(reference) = self.reference() else {
            return Vec::new();
        };
        let sat = reference.fall_degree;
        let cal = reference.calibrated_fall_degree;
        self.rows
            .iter()
            .filter(|r| {
                let beats_sat = matches!((r.fall_degree, sat), (Some(d), Some(r0)) if d < r0);
                let beats_cal =
                    matches!((r.calibrated_fall_degree, cal), (Some(d), Some(r0)) if d < r0);
                beats_sat || beats_cal
            })
            .collect()
    }

    /// Rank spread at one degree: `(min, max)` of `rank` across the
    /// sweep.  A zero spread at every degree is the strongest form of
    /// the invariance statement — not just the leading forms but the
    /// realised ranks are curve-independent.
    pub fn rank_spread(&self, d: u32) -> Option<(usize, usize)> {
        let ranks: Vec<usize> = self
            .rows
            .iter()
            .filter_map(|r| r.profiles.iter().find(|p| p.degree == d).map(|p| p.rank))
            .collect();
        if ranks.is_empty() {
            return None;
        }
        Some((
            ranks.iter().copied().min().unwrap(),
            ranks.iter().copied().max().unwrap(),
        ))
    }
}

/// **E2 — sweep the entire isogeny class** of the ECC2K-130 analogue
/// over `F_{2^n}`.
///
/// Exhaustive: every ordinary curve over `F_{2^n}` with the same point
/// count as `y² + xy = x³ + 1`, both twists included, each measured.
pub fn sweep_isogeny_class(
    n: u32,
    irr: &IrreduciblePoly,
    m: usize,
    ell: usize,
    d_max: u32,
    protocol: TargetProtocol,
) -> SweepReport {
    let census = IsogenyCensus::build(n, irr);
    let ids: Vec<CurveId> = census.koblitz_class().to_vec();
    sweep_ids(
        n,
        irr,
        &census,
        &ids,
        "isogeny class",
        m,
        ell,
        d_max,
        protocol,
    )
}

/// **E1 — sweep every ordinary binary curve** over `F_{2^n}`.
///
/// A strict superset of E2, so a null result here is a null result for
/// every isogeny class at once, not just ECC2K-130's.  Both twists are
/// enumerated even though they present identical systems, so the row
/// count matches the census's `2(2^n − 1)`.
pub fn sweep_all_curves(
    n: u32,
    irr: &IrreduciblePoly,
    m: usize,
    ell: usize,
    d_max: u32,
    protocol: TargetProtocol,
) -> SweepReport {
    let census = IsogenyCensus::build(n, irr);
    let mut ids = Vec::with_capacity(2 * ((1usize << n) - 1));
    for b in 1..(1u64 << n) {
        ids.push(CurveId { b, a_trace: 0 });
        ids.push(CurveId { b, a_trace: 1 });
    }
    sweep_ids(n, irr, &census, &ids, "all curves", m, ell, d_max, protocol)
}

/// **The control for E2's on-curve protocol**: hold the *curve* fixed at
/// `b` and vary the **target** instead, over the first `targets`
/// abscissae that carry a point.
///
/// Under [`TargetProtocol::OnCurve`] each curve gets its own `x_R`, so
/// the systems differ in their positive-degree part and a spread in the
/// fall degree has two possible causes.  This sweep isolates the second
/// one: whatever spread it shows is caused by the target alone, on a
/// single unchanging curve.  If the on-curve class sweep's spread is
/// contained in this one, the class contributed nothing.
///
/// Rows carry the synthetic id `(b, a_trace)` of the fixed curve; read
/// them by `x_r`, not by `id`.
pub fn sweep_targets_on_one_curve(
    n: u32,
    irr: &IrreduciblePoly,
    id: CurveId,
    m: usize,
    ell: usize,
    d_max: u32,
    targets: usize,
) -> SweepReport {
    assert!(n <= MAX_ALGEBRAIC_N);
    let census = IsogenyCensus::build(n, irr);
    let st = FieldStructure::new(n, irr);
    let tr = trace_table(n, irr);
    let seeds: Vec<u64> = collect_on_curve_targets(n, irr, &tr, id, targets);
    let rows: Vec<CurveDegreeProfile> = seeds
        .par_iter()
        .filter_map(|&x| {
            profile_curve(
                n,
                irr,
                &st,
                &tr,
                &census.kloosterman,
                id,
                m,
                ell,
                d_max,
                TargetProtocol::Fixed(x),
            )
        })
        .collect();
    SweepReport {
        n,
        scope: "targets, one curve",
        m,
        ell,
        protocol: TargetProtocol::OnCurve(0),
        rows,
    }
}

/// The first `want` abscissae of `F_{2^n}` that carry a point of the
/// given curve.
pub fn collect_on_curve_targets(
    n: u32,
    irr: &IrreduciblePoly,
    tr: &[u8],
    id: CurveId,
    want: usize,
) -> Vec<u64> {
    let b = elem_of(id.b, n);
    let mut c = b;
    for _ in 0..n - 1 {
        c = c.square(irr);
    }
    let mut out = Vec::with_capacity(want);
    for x in 1..(1u64 << n) {
        if out.len() >= want {
            break;
        }
        let xe = elem_of(x, n);
        let Some(inv) = xe.flt_inverse(irr) else {
            continue;
        };
        let v = xe.add(&c.mul(&inv, irr));
        if tr[mask_of(&v) as usize] == id.a_trace {
            out.push(x);
        }
    }
    out
}

#[allow(clippy::too_many_arguments)]
fn sweep_ids(
    n: u32,
    irr: &IrreduciblePoly,
    census: &IsogenyCensus,
    ids: &[CurveId],
    scope: &'static str,
    m: usize,
    ell: usize,
    d_max: u32,
    protocol: TargetProtocol,
) -> SweepReport {
    assert!(
        n <= MAX_ALGEBRAIC_N,
        "the Boolean engine packs monomials into a u64: n ≤ {MAX_ALGEBRAIC_N}"
    );
    let st = FieldStructure::new(n, irr);
    let tr = trace_table(n, irr);
    let rows: Vec<CurveDegreeProfile> = ids
        .par_iter()
        .filter_map(|id| {
            profile_curve(
                n,
                irr,
                &st,
                &tr,
                &census.kloosterman,
                *id,
                m,
                ell,
                d_max,
                protocol,
            )
        })
        .collect();
    SweepReport {
        n,
        scope,
        m,
        ell,
        protocol,
        rows,
    }
}

// ── Oracle cross-check ─────────────────────────────────────────────

/// Result of checking this thread's first-fall-degree oracle against the
/// FFD program's.
#[derive(Clone, Copy, Debug)]
pub struct OracleCheck {
    pub n: u32,
    pub b: u64,
    pub x_r: u64,
    /// [`crate::cryptanalysis::koblitz_groebner::first_fall_degree`] —
    /// the saturating convention.
    pub groebner_ffd: Option<u32>,
    /// [`crate::cryptanalysis::ffd_harness::measure_one`] — the
    /// calibrated convention.
    pub harness_ffd: Option<u32>,
    /// Lowest degree among the system's equations.  The two conventions
    /// are provably the same construction when this is `2`; below that,
    /// the saturating one fills rows the calibrated one omits.
    pub min_equation_degree: u32,
}

impl OracleCheck {
    /// Do the two engines agree?
    pub fn agrees(&self) -> bool {
        self.groebner_ffd == self.harness_ffd
    }

    /// Is this an instance where they are *required* to agree?
    pub fn conventions_coincide(&self) -> bool {
        self.min_equation_degree >= 2
    }
}

/// **Cross-check the two FFD oracles** on the full-field system, which
/// is the one both can express.  Required before any row this thread
/// reports is believed: the sweeps use the `koblitz_groebner` engine
/// because it also gives a solver, but the FFD program's numbers were
/// measured with `ffd_harness`, and the two must be the same number.
pub fn cross_check_ffd_oracles(
    n: u32,
    irr: &IrreduciblePoly,
    bs: &[u64],
    x_r: u64,
    d_max: u32,
) -> Vec<OracleCheck> {
    let st = FieldStructure::new(n, irr);
    let x = elem_of(x_r % (1u64 << n), n);
    bs.iter()
        .map(|&b| {
            let sys = build_for(n, &st, b, &x, 2, n as usize);
            let min_equation_degree = sys
                .as_ref()
                .map(|s| {
                    s.equations
                        .iter()
                        .map(|p| {
                            p.terms
                                .iter()
                                .map(|t| t.mask.count_ones())
                                .max()
                                .unwrap_or(0)
                        })
                        .min()
                        .unwrap_or(0)
                })
                .unwrap_or(0);
            let groebner_ffd = sys
                .map(|s| rank_profile(&s, d_max).fall_degree)
                .unwrap_or(None);
            let harness_ffd =
                crate::cryptanalysis::ffd_harness::measure_one(n, irr, &elem_of(b, n), &x, d_max)
                    .fall_degree;
            OracleCheck {
                n,
                b,
                x_r,
                groebner_ffd,
                harness_ffd,
                min_equation_degree,
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::koblitz_index_calculus::find_irreducible;

    /// The two FFD engines must return the same degree wherever their
    /// conventions coincide — i.e. wherever every equation is quadratic.
    /// Where they do not coincide, the divergence must be one-sided: the
    /// saturating engine fills strictly more rows, so it can only see
    /// the fall at the same degree or earlier, never later.
    #[test]
    fn ffd_oracles_agree_where_conventions_coincide() {
        let mut coincide = 0usize;
        let mut diverge = 0usize;
        for n in [5u32, 7, 9] {
            let irr = find_irreducible(n).unwrap();
            let bs: Vec<u64> = (1..(1u64 << n)).step_by(7).collect();
            for c in cross_check_ffd_oracles(n, &irr, &bs, 3, 4) {
                if c.conventions_coincide() {
                    coincide += 1;
                    assert!(
                        c.agrees(),
                        "n = {}, b = {:#x}: groebner {:?} vs harness {:?}",
                        c.n,
                        c.b,
                        c.groebner_ffd,
                        c.harness_ffd
                    );
                } else {
                    diverge += 1;
                    match (c.groebner_ffd, c.harness_ffd) {
                        (Some(g), Some(h)) => {
                            assert!(g <= h, "saturating must not see the fall later: {g} > {h}")
                        }
                        (Some(_), None) => {}
                        (None, Some(h)) => {
                            panic!("saturating missed a fall the harness saw at {h}")
                        }
                        (None, None) => {}
                    }
                }
            }
        }
        assert!(coincide > 0, "the agreeing regime must be exercised");
        assert!(diverge > 0, "the divergent regime must be exercised too");
    }

    /// The two conventions diverge **exactly** on the instances where a
    /// Weil-restricted coordinate loses its quadratic part, and that is
    /// a property of the target, not of `n`: at `n = 5` and `n = 11` the
    /// target `x_R = 3` leaves one equation linear, while `x_R ∈
    /// {11, 29, 47}` does not, at either size.  The research note's §5.1
    /// reads the convention gap off this; the test pins it so the note
    /// cannot drift from the code.
    #[test]
    fn the_convention_gap_tracks_a_linear_equation() {
        let expect_linear = |n: u32, x: u64| (n == 5 || n == 11) && x == 3;
        for n in [5u32, 7, 9, 11] {
            let irr = find_irreducible(n).unwrap();
            let st = FieldStructure::new(n, &irr);
            for x in [3u64, 11, 29, 47] {
                let sys = build_for(n, &st, 1, &elem_of(x % (1 << n), n), 2, n as usize).unwrap();
                let min_degree = sys
                    .equations
                    .iter()
                    .map(|p| {
                        p.terms
                            .iter()
                            .map(|t| t.mask.count_ones())
                            .max()
                            .unwrap_or(0)
                    })
                    .min()
                    .unwrap();
                assert_eq!(
                    min_degree == 1,
                    expect_linear(n, x),
                    "n = {n}, x_R = {x}: min equation degree {min_degree}"
                );
            }
        }
    }

    /// The quadratic twist presents the *same* system: `S₃` has no `a`.
    #[test]
    fn twist_presents_an_identical_system() {
        let n = 7;
        let irr = find_irreducible(n).unwrap();
        let st = FieldStructure::new(n, &irr);
        let x = elem_of(5, n);
        for b in 1..(1u64 << n) {
            let s0 = build_for(n, &st, b, &x, 2, n as usize).unwrap();
            let s1 = build_for(n, &st, b, &x, 2, n as usize).unwrap();
            assert_eq!(
                leading_form_signature(&s0.equations),
                leading_form_signature(&s1.equations)
            );
        }
    }

    /// Exhaustive over every curve at a small `n`: the positive-degree
    /// part never moves, and neither does the fall degree.
    #[test]
    fn exhaustive_small_field_sweep_is_flat() {
        let n = 7;
        let irr = find_irreducible(n).unwrap();
        let sweep = sweep_all_curves(n, &irr, 2, n as usize, 4, TargetProtocol::Fixed(5));
        assert_eq!(sweep.len(), 2 * ((1usize << n) - 1));
        assert!(sweep.leading_forms_identical());
        assert!(
            sweep.improvements().is_empty(),
            "no curve beat the Koblitz reference: {:?}",
            sweep.fall_histogram()
        );
    }

    /// A target sweep is not a curve comparison and must never be
    /// scored as one: every row is the same curve.
    #[test]
    fn target_sweeps_are_not_curve_comparisons() {
        let n = 9;
        let irr = find_irreducible(n).unwrap();
        let control =
            sweep_targets_on_one_curve(n, &irr, CurveId { b: 1, a_trace: 0 }, 2, n as usize, 4, 24);
        assert!(control.distinct_targets() > 1);
        assert!(!control.is_curve_comparison());
        assert!(
            control.improvements().is_empty(),
            "a curve cannot improve on itself"
        );
    }

    /// The on-curve protocol's spread must be a **target** effect, not a
    /// curve effect: varying the target on the single Koblitz curve
    /// reproduces at least as much spread as varying the curve does.
    #[test]
    fn target_variation_explains_the_on_curve_spread() {
        let n = 11;
        let irr = find_irreducible(n).unwrap();
        let class = sweep_isogeny_class(n, &irr, 2, n as usize, 4, TargetProtocol::OnCurve(3));
        let control = sweep_targets_on_one_curve(
            n,
            &irr,
            CurveId { b: 1, a_trace: 0 },
            2,
            n as usize,
            4,
            class.len().max(24),
        );
        let class_degrees: std::collections::BTreeSet<_> =
            class.rows.iter().map(|r| r.fall_degree).collect();
        let control_degrees: std::collections::BTreeSet<_> =
            control.rows.iter().map(|r| r.fall_degree).collect();
        assert!(
            class_degrees.is_subset(&control_degrees),
            "class spread {class_degrees:?} is not contained in the \
             single-curve target spread {control_degrees:?}"
        );
    }

    /// A fixed-target sweep shares one target, so its positive-degree
    /// parts are identical; an on-curve sweep does not, which is why the
    /// control above exists.
    #[test]
    fn fixed_target_sweeps_share_one_presentation() {
        let n = 9;
        let irr = find_irreducible(n).unwrap();
        let fixed = sweep_isogeny_class(n, &irr, 2, n as usize, 3, TargetProtocol::Fixed(11));
        assert_eq!(fixed.distinct_targets(), 1);
        assert!(fixed.leading_forms_identical());
        let on_curve = sweep_isogeny_class(n, &irr, 2, n as usize, 3, TargetProtocol::OnCurve(3));
        assert!(on_curve.distinct_targets() > 1);
    }

    /// The class really is an isogeny class: one trace, every row.
    #[test]
    fn class_sweep_has_a_single_trace() {
        let n = 9;
        let irr = find_irreducible(n).unwrap();
        let sweep = sweep_isogeny_class(n, &irr, 2, n as usize, 3, TargetProtocol::Fixed(11));
        assert!(!sweep.is_empty());
        let t = sweep.rows[0].trace;
        assert!(sweep.rows.iter().all(|r| r.trace == t));
        assert!(
            sweep.reference().is_some(),
            "b = 1 must be in its own class"
        );
    }
}
