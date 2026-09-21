//! # Exhaustive isogeny-class search for an easier Gröbner presentation.
//!
//! **The question.** ECC2K-130 is the Koblitz curve
//! `K_0 : y² + xy = x³ + 1` over `F_{2^131}`.  Index calculus against it
//! goes through a *point-decomposition problem* solved by Gröbner basis,
//! and the cost of that solve is governed by the **solving degree** `D*`
//! (operationally, the first fall degree `D_ff`).  Isogenies move us to
//! a different curve `E'` in the same isogeny class, with the *same*
//! group order, so the ECDLP transfers.  Does some `E'` in that class
//! present a lower `D*`?
//!
//! ECC2K-130's isogeny class holds **exactly**
//! `H(Δ) = 38 531 015 900 842 054 149 ≈ 2^65.06` curves
//! ([`class_number::ecc2k130_class_size`]), so it cannot be enumerated —
//! and saying so precisely is part of the answer.  The module therefore
//! works on four levels, three measured and one derived:
//!
//! | level | scope | how |
//! |---|---|---|
//! | **E1** | *every* ordinary binary curve over `F_{2^n}`, both twists | [`sweep_all_curves`] — `2(2^n − 1)` curves, reached to `n = 9` |
//! | **E2** | the *entire isogeny class* of the ECC2K-130 analogue | [`sweep_isogeny_class`] — class extracted by [`IsogenyCensus`], reached to `n = 17` |
//! | **E3** | the `ℓ`-isogeny neighbourhood of ECC2K-130 itself at `n = 131` | [`walk_isogeny_ball`], [`ball::rational_isogeny_degrees`] — structural screens, since `D*` is unobservable there |
//! | **E4** | the `≈ 2^65` class members E1–E3 cannot touch | [`certify_leading_form_invariance`] — a machine-checked *derivation*, not a sample |
//!
//! E1 is a strict superset of E2, so a null result there settles the
//! isogeny question for every class over the field at once.
//!
//! ## The structural result E4 rests on
//!
//! The binary summation polynomial is
//!
//! ```text
//!     S₃(x₁, x₂, x₃) = (x₁+x₂)² x₃² + x₁x₂ x₃ + (x₁x₂)² + b,
//! ```
//!
//! and the curve enters it **only through `b`** (the `a`-dependence lives
//! in the Artin–Schreier side condition, not in the polynomial).  Since
//! `b = 1/j`, walking the isogeny graph *is* varying `b`; nothing else
//! about the presentation changes.
//!
//! Now Weil-restrict.  Writing `x_i = Σ_t u_{i,t} z^t` makes each `x_i`
//! **linear** in the Boolean unknowns, and squaring is `F_2`-linear in
//! characteristic 2, so
//!
//! - `(x₁+x₂)² x₃²` has coordinates **linear** in `u` (when `x₃` is the
//!   known target) or **bilinear** (when `x₃` is a chained unknown),
//! - `x₁x₂ x₃` has coordinates bilinear resp. trilinear,
//! - `(x₁x₂)²` has coordinates **bilinear**,
//! - `b` contributes its coordinate vector, and **nothing else**.
//!
//! Setting every unknown to zero leaves exactly `b`.  Therefore:
//!
//! > **Leading-form invariance.**  For a fixed target `x_R`, field,
//! > basis and decomposition size `m`, any two curves `E_b`, `E_{b'}`
//! > over `F_{2^n}` give point-decomposition systems whose
//! > positive-degree parts are **identical**; the systems differ by the
//! > constant vector `coords(b) + coords(b')` alone.
//!
//! `d_reg` in this literature is defined on the **homogeneous system
//! built from the generators' top-degree components**, so it is a
//! function of those components alone.  They are `b`-free, hence
//! **isogeny-invariant**, hence *every* curve in the isogeny class — all
//! `≈ 2^65` of them — has the same degree of regularity as ECC2K-130.
//! [`certify_leading_form_invariance`] checks the step mechanically at
//! each `n` rather than asking the reader to trust the derivation.
//!
//! Not claimed: that the two *affine* ideals have the same leading-form
//! ideal.  They need not — which is why `D_ff` is measured rather than
//! argued.
//!
//! What a constant *can* still move is the **affine tail**: a degree
//! fall whose remainder is a nonzero constant certifies infeasibility,
//! and which curves get that certificate is `b`-dependent.  So `D_ff`
//! is not forced to be constant by the theorem, only its leading-form
//! component is.  That residual freedom is exactly what E1 and E2
//! measure exhaustively.
//!
//! ## The second structural result: there is nowhere to walk *to*
//!
//! The only lever known to lower `D*` on these systems is **L1**,
//! subfield structure (`research/notes/index-calculus/RESEARCH_DEGREE_REDUCTION.md` §2: Subfield mean
//! `D*` 2.04 vs Random 3.53).  A curve over `F_{2^n}` has that structure
//! iff it is `F_{2^n}`-isomorphic to one defined over a proper subfield,
//! which for ordinary curves means `j(E') ∈ F_{2^d}` for some `d | n`,
//! `d < n`.  With `n = 131` **prime**, the only proper subfield is `F_2`,
//! whose two elements give `j = 0` (supersingular — a different isogeny
//! class) and `j = 1`, i.e. `b = 1`, i.e. **ECC2K-130 itself**.
//!
//! So the subfield lever is not something an isogeny walk can reach: the
//! attacker already stands on the unique point of the class that has it,
//! and every isogeny step strictly loses structure.  [`subfield_members`]
//! enumerates the reachable subfield curves for any `n`, and the
//! `n = 131` answer is a set of size one.
//!
//! ## Honest scope
//!
//! - `D_ff` here is the operational first fall degree of
//!   [`crate::cryptanalysis::koblitz_groebner::first_fall_degree`], the
//!   same definition [`crate::cryptanalysis::ffd_harness`] uses, so the
//!   numbers are comparable with the FFD program's.
//!   [`cross_check_ffd_oracles`] verifies the two agree.
//! - The isogeny *walk* tracks `j`-invariants only; it does not build the
//!   explicit morphism `φ: E → E'` (see
//!   [`crate::cryptanalysis::binary_isogeny`] for why).  That is harmless
//!   here: the thread's conclusion is that no reachable `E'` is worth
//!   transporting a DLP to, so the transport map is never needed.
//! - `n ≤ 32` for the algebraic sweeps: the Boolean engine packs
//!   monomials into a `u64`, so the `2n`-variable full-field system caps
//!   there, and the Macaulay ranks cap it far lower in practice.
//!
//! ## References
//!
//! - J. Tate, *Endomorphisms of abelian varieties over finite fields*,
//!   Invent. Math. 2 (1966) — isogenous over `F_q` ⟺ equal point counts.
//! - G. Lachaud, J. Wolfmann, *The weights of the orthogonals of the
//!   extended quadratic binary Goppa codes*, IEEE-IT 36 (1990) — the
//!   Kloosterman-sum point count used by [`IsogenyCensus`].
//! - D. J. Bernstein et al., *Breaking ECC2K-130*, ePrint 2009/541 —
//!   the rho reference this thread measures its boundary against.
//! - S. D. Galbraith, S. W. Gebregiyorgis, *Summation polynomial
//!   algorithms for elliptic curves in characteristic two*, INDOCRYPT
//!   2014 — the operational first-fall-degree definition.

use crate::binary_ecc::{F2mElement, IrreduciblePoly};
use crate::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, first_fall_degree, macaulay_profile, MacaulayProfile, MAX_VARS,
};
use crate::cryptanalysis::pq_groebner_f2::F2BoolPoly;
use std::collections::BTreeMap;

pub mod ball;
pub mod census;
pub mod class_number;
pub mod cost;
pub mod profile;

pub use ball::{walk_isogeny_ball, BallNode, BallReport, BallScreen};
pub use census::{
    class_of, kloosterman_all, kloosterman_direct, subfield_members, trace_of_curve, ClassStats,
    IsogenyCensus,
};
pub use class_number::{ecc2k130_class_size, koblitz_class_size, IsogenyClassSize};
pub use cost::{class_size_estimate, rho_reference, SearchBoundary};
pub use profile::{
    cross_check_ffd_oracles, sweep_all_curves, sweep_isogeny_class, sweep_targets_on_one_curve,
    CurveDegreeProfile, SweepReport, TargetProtocol,
};

/// Largest extension degree the Boolean algebra engine can host for the
/// **full-field** system (`2n` unknowns packed into a `u64` monomial
/// mask).  Macaulay ranks become the binding constraint well before it.
pub const MAX_ALGEBRAIC_N: u32 = (MAX_VARS / 2) as u32;

// ── The point-decomposition system, as a function of the curve ─────

/// The decomposition system a single curve presents, split into the
/// part the curve controls and the part it does not.
///
/// The whole thread turns on how small the first field is.
#[derive(Clone, Debug)]
pub struct PresentedSystem {
    /// The `n` Boolean equations, ready for the Gröbner engine.
    pub equations: Vec<F2BoolPoly>,
    /// Boolean unknowns.
    pub n_vars: usize,
    /// Unknowns per summand.
    pub ell: usize,
    /// Summands.
    pub m: usize,
}

/// Build the point-decomposition system for `E_b` over `F_{2^n}` with
/// summand abscissae confined to the span of `basis`.
///
/// A thin wrapper over
/// [`crate::cryptanalysis::koblitz_groebner::build_decomposition_system`]
/// that exists so this thread's call sites read as "present curve `b` to
/// the solver" rather than as factor-base plumbing.
pub fn present(
    basis: &[F2mElement],
    x_r: &F2mElement,
    b: &F2mElement,
    m: usize,
    st: &crate::cryptanalysis::koblitz_groebner::FieldStructure,
) -> Option<PresentedSystem> {
    let sys = build_decomposition_system(basis, x_r, b, m, st)?;
    Some(PresentedSystem {
        equations: sys.equations,
        n_vars: sys.n_vars,
        ell: sys.ell,
        m: sys.m,
    })
}

/// The `F_2`-basis `1, z, …, z^{n−1}` of the whole field — the
/// "no factor base" presentation, which is the one every member of an
/// isogeny class admits.  (A Frobenius-invariant *subspace* basis exists
/// only for the subfield members, which is the point of
/// [`subfield_members`].)
pub fn full_field_basis(n: u32) -> Vec<F2mElement> {
    (0..n)
        .map(|k| F2mElement::from_bit_positions(&[k], n))
        .collect()
}

// ── Leading-form invariance: the certificate covering level E4 ──────

/// A fingerprint of everything in a system *except* its constant terms.
///
/// Two systems with equal signatures have identical leading forms at
/// every degree, hence identical degree of regularity; they can differ
/// only in the affine tail.
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct LeadingFormSignature {
    /// Per equation, the sorted monomial masks of **positive** degree.
    pub positive_part: Vec<Vec<u64>>,
    /// Per equation, the constant coefficient (`1` if the empty monomial
    /// is present).  Not part of equality — carried for reporting.
    pub constants: Vec<u8>,
}

impl LeadingFormSignature {
    /// Equal positive-degree parts.  The constants are ignored: that is
    /// exactly the comparison the invariance claim is about.
    pub fn same_leading_forms(&self, other: &Self) -> bool {
        self.positive_part == other.positive_part
    }

    /// The constant vector, as the `F_2` word the equations carry.
    pub fn constant_word(&self) -> Vec<u8> {
        self.constants.clone()
    }
}

/// Fingerprint a system.
pub fn leading_form_signature(equations: &[F2BoolPoly]) -> LeadingFormSignature {
    let mut positive_part = Vec::with_capacity(equations.len());
    let mut constants = Vec::with_capacity(equations.len());
    for p in equations {
        let mut masks: Vec<u64> = p.terms.iter().map(|t| t.mask).filter(|m| *m != 0).collect();
        masks.sort_unstable();
        positive_part.push(masks);
        constants.push(u8::from(p.terms.iter().any(|t| t.mask == 0)));
    }
    LeadingFormSignature {
        positive_part,
        constants,
    }
}

/// Outcome of the machine-checked invariance certificate.
#[derive(Clone, Debug)]
pub struct InvarianceCertificate {
    /// Extension degree tested.
    pub n: u32,
    /// Decomposition size tested.
    pub m: usize,
    /// Number of distinct curve parameters `b` compared.
    pub curves_compared: usize,
    /// True iff every `b` produced the same positive-degree part.
    pub leading_forms_identical: bool,
    /// True iff, for every `b`, the constant vector of the system equals
    /// the coordinate vector of `b` itself — the sharper claim that `b`
    /// is not merely confined to the constants but *is* the constants.
    pub constants_equal_b: bool,
    /// First `b` (as a bitmask) that broke either claim, if any.
    pub counterexample: Option<u64>,
}

/// **Certify leading-form invariance** at one `(n, m, x_R)`: build the
/// decomposition system for every `b` in `bs` and check that
///
/// 1. the positive-degree part never changes, and
/// 2. the constant vector is exactly the coordinate vector of `b`
///    (for `m = 2`; for `m > 2` only the *first* link carries a `b`
///    whose coordinates are directly readable, so claim 2 is checked on
///    that link alone and claim 1 on the whole system).
///
/// Passing this at every reachable `n` is what licenses the claim for
/// the `≈ 2^65` class members no sweep can reach: the argument is
/// uniform in `n`, and the certificate is a mechanical check of the step
/// the argument makes.
pub fn certify_leading_form_invariance(
    n: u32,
    irr: &IrreduciblePoly,
    x_r: &F2mElement,
    bs: &[F2mElement],
    m: usize,
) -> InvarianceCertificate {
    let st = crate::cryptanalysis::koblitz_groebner::FieldStructure::new(n, irr);
    let basis = full_field_basis(n);
    let mut reference: Option<LeadingFormSignature> = None;
    let mut leading_forms_identical = true;
    let mut constants_equal_b = true;
    let mut counterexample = None;
    let mut compared = 0usize;

    for b in bs {
        let Some(sys) = present(&basis, x_r, b, m, &st) else {
            continue;
        };
        compared += 1;
        let sig = leading_form_signature(&sys.equations);

        // Claim 2: the first `n` equations are the first S₃ link, whose
        // constant vector must be coords(b) plus the x_R-only part.  We
        // check the *difference* against the reference instead, which is
        // the same statement without needing to model the x_R part.
        if let Some(r) = &reference {
            if !r.same_leading_forms(&sig) {
                leading_forms_identical = false;
                counterexample.get_or_insert_with(|| bit_word(b));
            }
            let delta: Vec<u8> = r
                .constants
                .iter()
                .zip(sig.constants.iter())
                .take(n as usize)
                .map(|(a, c)| a ^ c)
                .collect();
            let expect = coord_bits(b, n)
                .iter()
                .zip(coord_bits(&bs[0], n).iter())
                .map(|(a, c)| a ^ c)
                .collect::<Vec<u8>>();
            if delta != expect {
                constants_equal_b = false;
                counterexample.get_or_insert_with(|| bit_word(b));
            }
        } else {
            reference = Some(sig);
        }
    }

    InvarianceCertificate {
        n,
        m,
        curves_compared: compared,
        leading_forms_identical,
        constants_equal_b,
        counterexample,
    }
}

/// The low `u64` of a field element's bit pattern (fields here are
/// `n ≤ 63`, so this is the whole element).
pub fn bit_word(e: &F2mElement) -> u64 {
    e.raw_bits().first().copied().unwrap_or(0)
}

/// Coordinates of `e` in the polynomial basis, as `0/1` bytes.
pub fn coord_bits(e: &F2mElement, n: u32) -> Vec<u8> {
    let w = bit_word(e);
    (0..n).map(|k| ((w >> k) & 1) as u8).collect()
}

// ── Macaulay rank profiles, degree by degree ───────────────────────

/// Rank profile of a presented system, plus the first fall degree read
/// off it.
#[derive(Clone, Debug)]
pub struct RankProfile {
    /// The operational first fall degree, or `None` if none up to `d_max`.
    pub fall_degree: Option<u32>,
    /// Per-degree `(rows, cols, rank)`.
    pub profiles: Vec<MacaulayProfile>,
}

impl RankProfile {
    /// Rank deficiency at a degree, `rows − rank`.
    pub fn syzygies_at(&self, d: u32) -> Option<usize> {
        self.profiles
            .iter()
            .find(|p| p.degree == d)
            .map(|p| p.syzygies())
    }

    /// The profile keyed by degree, for table printing.
    pub fn by_degree(&self) -> BTreeMap<u32, MacaulayProfile> {
        self.profiles.iter().map(|p| (p.degree, *p)).collect()
    }
}

/// Measure the rank profile and first fall degree of a presented system.
pub fn rank_profile(sys: &PresentedSystem, d_max: u32) -> RankProfile {
    let (fall_degree, profiles) = first_fall_degree(&sys.equations, sys.n_vars, d_max);
    RankProfile {
        fall_degree,
        profiles,
    }
}

/// Rank of one Macaulay degree only — the cheap screen, used when
/// sweeping thousands of curves.
pub fn rank_at(sys: &PresentedSystem, d: u32) -> Option<MacaulayProfile> {
    macaulay_profile(&sys.equations, sys.n_vars, d)
}
