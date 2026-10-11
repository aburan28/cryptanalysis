//! # EXP-R6 / lever **L5** — the curve-side lever: can an isogeny make the
//! Gröbner basis easier?
//!
//! `research/notes/index-calculus/RESEARCH_DEGREE_REDUCTION.md` measures four levers (L1–L4), all of
//! which change the *presentation* of one fixed curve's decomposition
//! ideal.  This module measures the one lever that changes the **curve**:
//! the ECDLP transports along an isogeny `φ: E → E'` of degree coprime to
//! the subgroup order, so an attacker is free to solve the problem on any
//! curve in the isogeny class of `E` and pull the answer back.  If some
//! `E'` in the class had a materially lower solving degree `D*`, that would
//! be an attack on `E`.  This is the Galbraith–Hess–Smart move ("walk to a
//! weaker isogenous curve", which worked for Weil descent) asked of
//! Gröbner-basis solving degree instead of GHS genus.
//!
//! The module answers the question for ECC2K-130 specifically, and the
//! answer is negative for three independent reasons, each *derived* rather
//! than measured.  They are the thread's boundaries, so they are stated
//! before any search runs.
//!
//! ## Boundary A — the class is bigger than ρ
//!
//! For the Koblitz curve `E: y² + xy = x³ + 1` over `F_{2^131}`,
//! `End(E) ⊗ Q = Q(√−7)` with `d_K = −7`, `h(−7) = 1`.  Writing
//! `τ² + τ + 2 = 0` for the Frobenius of `F_2` and `π = τ^131`, the
//! conductor of `Z[π]` in `O_K = Z[τ]` is
//!
//! ```text
//!   c = 38531015900842053623 = 263 · 146505763881528721   (both prime)
//! ```
//!
//! and the class — every curve `F_{2^131}`-isogenous to `E` — has exactly
//!
//! ```text
//!   Σ_{f | c} h(O_f) = 38531015900842054149 ≈ 2^65.06     vertices,
//!   h(O_f) = f · Π_{ℓ | f} (1 − (d_K/ℓ)/ℓ)                (h_K = 1, unit index 1).
//! ```
//!
//! Pollard ρ on a group of order `r` whose automorphism group has order `m`
//! and acts freely walks on `r/m` classes, so the birthday bound is
//! `√(π(r/m)/2) = √(πr/2m)`.  For ECC2K-130 the automorphism group is
//! negation together with the 131 Frobenius powers, `m = 2 · 131 = 262`:
//!
//! ```text
//!   plain ρ, m = 1      √(πr/2)    = 2^64.83
//!   negation, m = 2     √(πr/4)    = 2^64.33
//!   full, m = 262       √(πr/524)  = 2^60.81   ← the ECC2K-130 effort's target
//! ```
//!
//! **Enumerating the isogeny class costs more than solving the DLP by ρ**, at
//! one operation per vertex, before any per-vertex Gröbner work is charged —
//! `2^4.25×` against the automorphism-assisted ρ.  The margin is much thinner
//! against plain ρ, only `2^0.24×`, so Boundary A is reported against both:
//! the *sign* is what it rests on, and that holds either way.
//!
//! (An earlier revision of this module divided `√(πr/4)` by `√(2·131)`.  That
//! applies negation twice — `√(πr/4)` is already `m = 2` — and understated ρ
//! by half a bit.  Caught in review on PR #203.)
//!
//! ## Boundary B — 263 of those `2^65` vertices are reachable, and that is all
//!
//! Because `h(−7) = 1` the crater of every `ℓ`-volcano is a **single
//! vertex, `E` itself**: horizontal `ℓ`-isogenies act through
//! `Cl(O_K) = 1`, so they return to `E` (`j ↦ j`), and descending
//! `ℓ`-isogenies exist only for `ℓ | c`.  Hence
//!
//! - for **every** prime `ℓ ∉ {263, 146505763881528721}` the `ℓ`-isogeny
//!   graph of `E` is a single vertex — there is no small-`ℓ` walk to take;
//! - `ℓ = 263` splits (`(−7/263) = +1`), giving `263 − 1 = 262` descending
//!   isogenies onto a depth-1 floor, all adjacent to `E`;
//! - `ℓ = p = 146505763881528721` is inert, giving `p + 1` descending
//!   isogenies — each with a kernel polynomial of degree `(p−1)/2 ≈ 2^56`,
//!   whose kernel points live in an extension of `F_{2^131}` of degree
//!   dividing `p − 1`.  Unreachable.
//!
//! So the **exhaustive, terminating** search over the computationally
//! reachable part of the class is over `1 + 262 = 263` curves — `2^8` of
//! `2^65.06`, a fraction of `6.8 × 10^{-18}`.  [`ReachAccounting`] does
//! this bookkeeping for any degree budget.
//!
//! ## Boundary C — the curve enters *below* the leading form
//!
//! Boundaries A and B bound the search.  This one says what a search could
//! possibly find.  For a binary curve `y² + xy = x³ + a₂x² + a₆`, Semaev's
//! `S₃` is
//!
//! ```text
//!   S₃(x₁,x₂,x₃) = (x₁x₂)² + (x₁x₃)² + (x₂x₃)² + x₁x₂x₃ + a₆
//! ```
//!
//! — independent of `a₂`, and `a₆` appears as an **additive constant**.
//! `a₆ = 1/j` is therefore the *entire* curve-dependence of the `m = 2`
//! decomposition system, and after Weil descent into `n` Boolean equations
//! it moves **only the constant term of each equation**: the degree-`≥ 1`
//! part is byte-identical for every curve over the field.
//!
//! At `m = 3` the same holds with room to spare.  Expanding
//! `S₄ = Res_X(S₃(X₁,X₂,X), S₃(X₃,x_R,X))` in `a₆` gives exactly
//!
//! ```text
//!   S₄ = [A₁(X₃x_R)² + A₂(X₁X₂)²]²                 a₆-free, Boolean degree 3
//!      + (A₁B₂ + A₂B₁)(B₁(X₃x_R)² + B₂(X₁X₂)²)     a₆-free, Boolean degree 6
//!      + a₆  · (A₁B₂ + A₂B₁)(B₁ + B₂)              Boolean degree 4
//!      + a₆² · (A₁ + A₂)²                          Boolean degree 1
//! ```
//!
//! with `A₁ = (X₁+X₂)², B₁ = X₁X₂, A₂ = (X₃+x_R)², B₂ = X₃x_R`, and Boolean
//! degrees counted with squaring free (`F_2`-linear), so `A₁, A₂, B₂` are
//! degree 1 and `B₁` is degree 2.  The top Boolean degree is 6 and it is
//! `a₆`-free; every `a₆`-carrying term sits at degree `4` or below, exactly
//! two degrees under the top — the same two-degree gap EXP-R6b then computed
//! at every `m ≤ 5` (`research/notes/ecc2k130/RESEARCH_ISOGENY_CLASS_SEARCH.md` §2C).
//! An earlier revision of this block wrote `≤ 5` here, a product-of-factor-degrees
//! bound: Boolean degree is `Σ wt(eᵢ)`, so `A₂B₁ · B₁` collapses rather than
//! adding.  The identity is verified, not asserted — see
//! `s4_a6_expansion_is_quadratic_with_subleading_coefficients`.
//!
//! **What this does and does not cover.**  The leading-form ideal is
//! curve-independent, so the degree of regularity in the
//! Bardet–Faugère–Salvy sense — a Hilbert-series invariant of the
//! leading forms — is constant on the whole isogeny class, and so is the
//! degree at which any top-degree cancellation first becomes *available*.
//! It does **not** cover the affine refutation degree `D*` that this
//! repository actually measures (`pc_degree_harness::refutation_scan`: the
//! degree at which `1` enters the Macaulay row space).  `D*` is a property
//! of the *inhomogeneous* system, and the curve controls precisely the
//! inhomogeneous part, so `D*` does vary with `a₆`.  Measured at `n = 8`,
//! `l = 4` over all 255 curves it takes values `{2, 3, 4}`.  That variation
//! is the lever's entire remaining surface, so it is what EXP-R6 measures.
//!
//! ## The mechanism, derived
//!
//! The variation is not mysterious and it is not a curve *quality*.  Write
//! the descended system as `f_i = h_i + c_i` with `h_i` the degree-`≥ 1`
//! part (curve-independent) and `c_i ∈ F_2` the constant.  Let
//!
//! ```text
//!   S = { λ ∈ F_2^n : Σ λ_i h_i = 0 }
//! ```
//!
//! be the left null space of the leading parts — again curve-independent.
//! For `λ ∈ S`, `Σ λ_i f_i = ⟨λ, c⟩` is a *constant*, so the Macaulay matrix
//! refutes already at degree 2 exactly when `⟨λ, c⟩ = 1` for some `λ ∈ S`:
//!
//! ```text
//!   D* = 2   ⟺   c ∉ S^⊥,   so the fraction of curves refuting at
//!                degree 2 is 1 − 2^{−dim S}.
//! ```
//!
//! Since `a₆ ↦ c` is an affine bijection `F_{2^n} → F_2^n`, sweeping the
//! curve *is* sweeping the constant vector over the whole space.  So the
//! set of "good" curves is the complement of an affine subspace — and that
//! subspace **depends on the target `x_R`**.  A curve that is good for one
//! target is good for a `1 − 2^{−dim S}` fraction of targets and no more:
//! there is no curve that is good for all of them, and an attack has to
//! solve one decomposition instance per relation, each with its own target.
//! [`syzygy_mechanism`] measures `dim S` and checks the predicted density
//! against the exhaustive count; [`curve_effect_test`] checks the
//! consequence — that a curve selected as best on one target set keeps no
//! margin on a disjoint one.
//!
//! ## Boundary D — factor-base structure belongs to the field, not the curve
//!
//! The only lever the FFD program has measured to lower `D*` materially is
//! L1, a **subfield** factor base (mean `D*` 2.04 against 3.53 for a random
//! base).  An isogeny is defined over the field it starts in, so `F_{2^131}`
//! and every `F_2`-subspace of it are identical before and after: whatever
//! factor-base structure exists over that field is available on **every curve
//! in the class equally**, and so distinguishes none of them.  An isogeny
//! cannot make a factor-base mechanism available that `E` did not already
//! have.
//!
//! An earlier revision argued instead that `131` is prime, so `F_{2^131}` has
//! no proper subfield and L1 is therefore unreachable.  True of proper
//! subfields but too strong as a claim about the mechanism: subfield-*like*
//! bases do not need one — quasi-subfield polynomials
//! (Huang–Kosters–Petit–Yeo–Yun) supply them at prime `n`, and
//! `research/notes/index-calculus/RESEARCH_QUASI_SUBFIELD.md` exhibits genuine non-subfield examples over
//! `F_{2^7}`.  The field-invariance form above does not depend on that question
//! either way.  For `n = 131` the census in that note happens to find no
//! quasi-subfield cell either, so the mechanism is doubly out of reach here.
//!
//! ## What is therefore measured
//!
//! Boundary C is a statement about *all* curves, so it is tested the
//! strongest way available: [`exhaustive_a6_sweep`] measures `D*` for
//! **every** curve over `F_{2^n}` — all `2^n − 1` values of `a₆`, a superset
//! of every isogeny class at that size, the Koblitz one included.  The
//! containment is what makes an exhaustive statement possible at a size
//! where the `2^65` class is not enumerable: whatever the isogeny-reachable
//! curves do, the sweep has already done it.
//!
//! Three numbers come out, and the third is the one that decides:
//!
//! 1. `dim S` and the predicted-versus-measured density of `D* = 2`
//!    ([`syzygy_mechanism`]) — does the derived mechanism hold exactly?
//! 2. the between-curve variance of mean `D*` against what independent
//!    sampling from the pooled distribution predicts — is the curve the
//!    explanatory variable at all?
//! 3. the **holdout margin** ([`curve_effect_test`]): take the curve that
//!    looks best on one target set, re-measure it on a disjoint one.  A
//!    lever that is real keeps its margin; a winner's curse does not.
//!
//! ## References
//!
//! - **D. Kohel**, *Endomorphism rings of elliptic curves over finite
//!   fields*, PhD thesis 1996 — the volcano structure used by
//!   [`VolcanoPrime`].
//! - **S. Galbraith, F. Hess, N. Smart**, *Extending the GHS Weil descent
//!   attack*, EUROCRYPT 2002 — the isogeny-walk move this module scores.
//! - **I. Semaev**, *Summation polynomials and the discrete logarithm
//!   problem on elliptic curves*, eprint 2004/031.
//! - **S. Galbraith, S. Gebregiyorgis**, *Summation polynomial algorithms
//!   for elliptic curves in characteristic two*, INDOCRYPT 2014.
//! - **D. Bailey et al.**, *Breaking ECC2K-130*, eprint 2009/541 — the
//!   ρ reference cost this module compares against.

use num_bigint::BigInt;
use num_integer::Integer;
use num_traits::{One, Signed, Zero};
use std::collections::BTreeMap;

use crate::binary_ecc::{F2mElement, IrreduciblePoly};
use crate::cryptanalysis::ffd_harness::{weil_descend_s3_subspace, F2BoolPoly};
use crate::cryptanalysis::pc_degree_harness::{is_decomposable, refutation_scan};

/// CM discriminant of both Koblitz curves over `F_2`: `Q(√−7)`.
pub const CM_DISCRIMINANT: i64 = -7;
/// `h(−7) = 1` — the reason every crater in this class is a single vertex.
pub const CM_CLASS_NUMBER: u64 = 1;
/// Frobenius trace of `E: y² + xy = x³ + 1` over `F_2` (`#E(F_2) = 4`).
pub const KOBLITZ_TRACE_F2: i64 = -1;

// ── Part A: the isogeny class, exactly ──────────────────────────────

/// `τⁿ = a + bτ` in `O_K = Z[τ]`, where `τ² + τ + 2 = 0` is the Frobenius
/// of `F_2` acting on `E: y² + xy = x³ + 1`.
///
/// Returned as `(a, b)`.  The conductor of `Z[π]` in `O_K` for
/// `π = τⁿ` is `|b|`, since `Z[π] = Z + Z·bτ` has index `|b|` in
/// `Z + Zτ`.
pub fn frobenius_power(n: u32) -> (BigInt, BigInt) {
    assert!(n >= 1, "n must be at least 1");
    // τ¹ = 0 + 1·τ.
    let mut a = BigInt::zero();
    let mut b = BigInt::one();
    for _ in 1..n {
        // (a + bτ)·τ = aτ + bτ² = aτ + b(−τ − 2) = −2b + (a − b)τ.
        let next_a = -(BigInt::from(2u8) * &b);
        let next_b = &a - &b;
        a = next_a;
        b = next_b;
    }
    (a, b)
}

/// Frobenius trace of `E: y² + xy = x³ + 1` over `F_{2^n}`.
///
/// `t_n = π + π̄ = 2a + b·t_1` for `τⁿ = a + bτ`, with `t_1 = −1`.
pub fn koblitz_trace(n: u32) -> BigInt {
    let (a, b) = frobenius_power(n);
    BigInt::from(2u8) * a + b * BigInt::from(KOBLITZ_TRACE_F2)
}

/// `#E(F_{2^n}) = 2^n + 1 − t_n`.
pub fn koblitz_order(n: u32) -> BigInt {
    (BigInt::one() << n) + BigInt::one() - koblitz_trace(n)
}

/// Conductor of `Z[π]` in `O_K`: the `|b|` of [`frobenius_power`].
pub fn koblitz_conductor(n: u32) -> BigInt {
    frobenius_power(n).1.abs()
}

/// Kronecker symbol `(−7/ℓ)` for an odd prime `ℓ`.  `ℓ = 7` gives `0`
/// (ramified); `ℓ = 2` is handled separately by the caller because `2` is
/// the characteristic here.
pub fn kronecker_minus7(ell: &BigInt) -> i32 {
    let seven = BigInt::from(7u8);
    if ell == &BigInt::from(2u8) {
        // −7 ≡ 1 (mod 8) ⇒ 2 splits.  Only used for reporting.
        return 1;
    }
    let d = (-seven).mod_floor(ell);
    if d.is_zero() {
        return 0;
    }
    // Euler's criterion: d^((ℓ−1)/2) mod ℓ.
    let exp = (ell - BigInt::one()) / BigInt::from(2u8);
    let r = d.modpow(&exp, ell);
    if r.is_one() {
        1
    } else {
        -1
    }
}

/// `h(O_f) = f · Π_{ℓ | f} (1 − (d_K/ℓ)/ℓ)` for the order of conductor
/// `f` in `O_K = Z[(1+√−7)/2]`.
///
/// `h_K = 1` and the unit index `[O_K^* : O_f^*]` is `1` because
/// `d_K = −7 < −4`, so the classical formula collapses to the product
/// `Π_i ℓ_i^{e_i − 1} (ℓ_i − (d_K/ℓ_i))` over the factorisation
/// `f = Π ℓ_i^{e_i}`.
pub fn class_number_of_conductor(factors: &[(BigInt, u32)]) -> BigInt {
    let mut h = BigInt::one();
    for (ell, e) in factors {
        let chi = BigInt::from(kronecker_minus7(ell));
        h *= ell.pow(e - 1) * (ell - chi);
    }
    h
}

/// One prime of the conductor, with its volcano.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct VolcanoPrime {
    /// The prime `ℓ`.
    pub ell: BigInt,
    /// `v_ℓ(c)` — the depth of the `ℓ`-volcano below the crater.
    pub depth: u32,
    /// `(−7/ℓ)`: `+1` split, `−1` inert, `0` ramified.
    pub kronecker: i32,
    /// `1 + (−7/ℓ)` horizontal `ℓ`-isogenies leave the crater — and all
    /// return to `E`, because the crater has `h(−7) = 1` vertex.
    pub horizontal_from_crater: u32,
    /// `ℓ − (−7/ℓ)` descending `ℓ`-isogenies leave the crater, each onto a
    /// distinct level-1 vertex.
    pub descending_from_crater: BigInt,
    /// `h(O_{ℓ^i})` for `i = 1..=depth` — the population of each level.
    pub level_sizes: Vec<BigInt>,
}

/// The exact isogeny class of the Koblitz curve over `F_{2^n}`.
#[derive(Clone, Debug)]
pub struct IsogenyClassStructure {
    /// Extension degree.
    pub n: u32,
    /// `t_n`.
    pub trace: BigInt,
    /// `#E(F_{2^n})`.
    pub order: BigInt,
    /// Conductor `c` of `Z[π]` in `O_K`.
    pub conductor: BigInt,
    /// Factorisation of `c`, ascending.  Empty iff `c = 1`.
    pub conductor_factors: Vec<(BigInt, u32)>,
    /// `false` if the factoring budget ran out — then `class_size` and the
    /// volcano list are **not** exact and must not be reported as such.
    pub fully_factored: bool,
    /// `Σ_{f | c} h(O_f)` — the number of vertices in the class.
    pub class_size: BigInt,
    /// The crater: `h(O_K) = h(−7) = 1`.
    pub crater_size: u64,
    /// One entry per prime of `c`.
    pub primes: Vec<VolcanoPrime>,
}

impl IsogenyClassStructure {
    /// `log₂` of the class size, for the ρ comparison.
    pub fn log2_class_size(&self) -> f64 {
        log2_bigint(&self.class_size)
    }

    /// Every prime `ℓ` for which `E` has a non-trivial `ℓ`-isogenous
    /// neighbour.  By Boundary B this is exactly the set of primes dividing
    /// the conductor: for any other `ℓ` the graph is the single vertex `E`.
    pub fn nontrivial_isogeny_degrees(&self) -> Vec<BigInt> {
        self.conductor_factors
            .iter()
            .map(|(l, _)| l.clone())
            .collect()
    }

    /// Is the `ℓ`-isogeny graph of `E` a single vertex?  True for every
    /// prime not dividing the conductor — including, for ECC2K-130, every
    /// prime below 263.
    pub fn ell_graph_is_trivial(&self, ell: &BigInt) -> bool {
        !self.conductor_factors.iter().any(|(l, _)| l == ell)
    }

    /// Vertices reachable from `E` using only isogenies of prime degree
    /// `≤ budget`.
    ///
    /// A vertex is determined by the conductor `f | c` of its endomorphism
    /// ring together with its position at that level, and moving the
    /// `ℓ`-exponent of `f` requires an `ℓ`-isogeny.  So the reachable set is
    /// the sub-class `{f | c : ℓ ∤ f for every prime ℓ > budget}`, and each
    /// `ℓ`-volcano below the budget is fully traversable because its crater
    /// is the single vertex `E` and all `h(O_ℓ)` level-1 vertices are
    /// adjacent to it.
    pub fn reach_within_degree(&self, budget: &BigInt) -> ReachAccounting {
        let (allowed, blocked): (Vec<_>, Vec<_>) = self
            .conductor_factors
            .iter()
            .cloned()
            .partition(|(l, _)| l <= budget);
        let reachable = sum_over_divisor_orders(&allowed);
        let blocking_primes: Vec<BigInt> = blocked.iter().map(|(l, _)| l.clone()).collect();
        let min_blocking = blocking_primes.iter().min().cloned();
        ReachAccounting {
            degree_budget: budget.clone(),
            reachable: reachable.clone(),
            class_size: self.class_size.clone(),
            log2_reachable: log2_bigint(&reachable),
            log2_class_size: log2_bigint(&self.class_size),
            log2_min_blocking_kernel_degree: min_blocking
                .as_ref()
                .map(|p| log2_bigint(&((p - BigInt::one()) / BigInt::from(2u8)))),
            log2_min_blocking_sqrt_velu: min_blocking.as_ref().map(|p| log2_bigint(p) / 2.0),
            blocking_primes,
            exhaustive: min_blocking.is_none(),
        }
    }
}

/// Coverage bookkeeping for a search bounded by isogeny degree.
#[derive(Clone, Debug)]
pub struct ReachAccounting {
    /// Largest prime isogeny degree the search is allowed to compute.
    pub degree_budget: BigInt,
    /// Vertices reachable within that budget.
    pub reachable: BigInt,
    /// Vertices in the whole class.
    pub class_size: BigInt,
    pub log2_reachable: f64,
    pub log2_class_size: f64,
    /// Primes of the conductor above the budget — the reason the search is
    /// not exhaustive over the class.
    pub blocking_primes: Vec<BigInt>,
    /// `log₂` of `(ℓ−1)/2`, the kernel-polynomial degree of the cheapest
    /// blocked isogeny.  `None` when nothing is blocked.
    pub log2_min_blocking_kernel_degree: Option<f64>,
    /// `log₂ √ℓ` — the √élu cost of the cheapest blocked isogeny, which is
    /// a *lower* bound on evaluating it even with the best known algorithm.
    pub log2_min_blocking_sqrt_velu: Option<f64>,
    /// True when the budget covers every prime of the conductor, i.e. the
    /// search really is exhaustive over the class.
    pub exhaustive: bool,
}

impl ReachAccounting {
    /// Fraction of the class the search covers.
    pub fn log2_fraction(&self) -> f64 {
        self.log2_reachable - self.log2_class_size
    }
}

/// `Σ_{f | Π ℓ_i^{d_i}} h(O_f)` over every divisor of the given
/// factorisation.
fn sum_over_divisor_orders(factors: &[(BigInt, u32)]) -> BigInt {
    // Every divisor f of c, as an exponent vector.
    let mut total = BigInt::zero();
    let mut exps = vec![0u32; factors.len()];
    loop {
        let divisor: Vec<(BigInt, u32)> = factors
            .iter()
            .zip(exps.iter())
            .filter(|(_, e)| **e > 0)
            .map(|((l, _), e)| (l.clone(), *e))
            .collect();
        total += class_number_of_conductor(&divisor);
        // Odometer over 0..=d_i.
        let mut i = 0;
        loop {
            if i == factors.len() {
                return total;
            }
            if exps[i] < factors[i].1 {
                exps[i] += 1;
                break;
            }
            exps[i] = 0;
            i += 1;
        }
    }
}

/// Build the exact class structure for `E: y² + xy = x³ + 1` over
/// `F_{2^n}`.
///
/// `factor_budget` caps the Pollard-rho iteration count per composite; when
/// it is exhausted `fully_factored` is `false` and the derived quantities
/// are lower bounds rather than exact.
pub fn koblitz_isogeny_class(n: u32, factor_budget: u64) -> IsogenyClassStructure {
    let trace = koblitz_trace(n);
    let order = koblitz_order(n);
    let conductor = koblitz_conductor(n);
    let (conductor_factors, fully_factored) = factor_bigint(&conductor, factor_budget);

    let mut primes = Vec::new();
    for (ell, depth) in &conductor_factors {
        let chi = kronecker_minus7(ell);
        let descending = ell - BigInt::from(chi);
        let level_sizes = (1..=*depth)
            .map(|i| class_number_of_conductor(&[(ell.clone(), i)]))
            .collect();
        primes.push(VolcanoPrime {
            ell: ell.clone(),
            depth: *depth,
            kronecker: chi,
            horizontal_from_crater: (1 + chi).max(0) as u32,
            descending_from_crater: descending,
            level_sizes,
        });
    }

    let class_size = sum_over_divisor_orders(&conductor_factors);
    IsogenyClassStructure {
        n,
        trace,
        order,
        conductor,
        conductor_factors,
        fully_factored,
        class_size,
        crater_size: CM_CLASS_NUMBER,
        primes,
    }
}

// ── Part B: the leading-form invariance witness ─────────────────────

/// Evidence that the curve coefficient does not reach the leading form of
/// the descended system.
///
/// For `m = 2` this is exact and complete: [`F2BoolPoly`] stores the
/// constant at index 0, the linear monomials next and the quadratic ones
/// last, so "`a₆` moves only the constant" is a coefficient-by-coefficient
/// comparison over a set of curves.
#[derive(Clone, Debug)]
pub struct LeadingFormWitness {
    pub n: u32,
    /// Factor-base subspace dimension.
    pub l: u32,
    pub num_vars: u32,
    pub num_eqs: usize,
    /// How many distinct `a₆` were compared against the first.
    pub curves_compared: usize,
    /// True iff every equation's degree-`≥ 1` coefficients agree across all
    /// compared curves.  Boundary C predicts `true`.
    pub degree_ge1_identical: bool,
    /// The Boolean degrees at which some coefficient *did* vary.  Boundary C
    /// predicts `[0]`.
    pub degrees_touched_by_a6: Vec<u32>,
    /// Top Boolean degree of the system (2 for the descended `S₃`).
    pub top_degree: u32,
}

/// Compare the descended `S₃` systems of several curves at a fixed factor
/// base and target, and report which Boolean degrees the curve coefficient
/// reaches.
pub fn leading_form_witness(
    n: u32,
    l: u32,
    irr: &IrreduciblePoly,
    x3: &F2mElement,
    a6_values: &[F2mElement],
) -> LeadingFormWitness {
    assert!(a6_values.len() >= 2, "need at least two curves to compare");
    let num_vars = 2 * l;
    let systems: Vec<Vec<F2BoolPoly>> = a6_values
        .iter()
        .map(|a6| weil_descend_s3_subspace(n, l, irr, a6, x3))
        .collect();
    let base = &systems[0];

    let mut touched: Vec<u32> = Vec::new();
    let mut degree_ge1_identical = true;
    for other in &systems[1..] {
        assert_eq!(base.len(), other.len(), "descent must be shape-preserving");
        for (f, g) in base.iter().zip(other.iter()) {
            let len = f.coeffs.len().max(g.coeffs.len());
            for idx in 0..len {
                let a = f.coeffs.get(idx).copied().unwrap_or(false);
                let b = g.coeffs.get(idx).copied().unwrap_or(false);
                if a == b {
                    continue;
                }
                let deg = coeff_index_degree(idx, num_vars);
                if !touched.contains(&deg) {
                    touched.push(deg);
                }
                if deg >= 1 {
                    degree_ge1_identical = false;
                }
            }
        }
    }
    touched.sort_unstable();

    LeadingFormWitness {
        n,
        l,
        num_vars,
        num_eqs: base.len(),
        curves_compared: a6_values.len() - 1,
        degree_ge1_identical,
        degrees_touched_by_a6: touched,
        top_degree: 2,
    }
}

/// Boolean degree of the monomial stored at `idx` in an [`F2BoolPoly`]:
/// index 0 is the constant, `1..=num_vars` the linear monomials, and the
/// rest the quadratics.
fn coeff_index_degree(idx: usize, num_vars: u32) -> u32 {
    if idx == 0 {
        0
    } else if idx <= num_vars as usize {
        1
    } else {
        2
    }
}

// ── Part C: the exhaustive curve sweep ──────────────────────────────

/// One curve of the sweep: `E_{a₆}: y² + xy = x³ + a₆`.
#[derive(Clone, Debug)]
pub struct CurveRow {
    /// `a₆` as an integer in the polynomial basis.
    pub a6: u64,
    /// `j = 1/a₆`.
    pub j: u64,
    /// `#E_{a₆}(F_{2^n})`, when the sweep computed it exactly.
    pub order: Option<i128>,
    /// `t` of `E_{a₆}`; `|t| = |t_n|` iff some twist of `E_{a₆}` lies in the
    /// Koblitz isogeny class.
    pub trace: Option<i128>,
    /// True iff a twist of `E_{a₆}` is `F_{2^n}`-isogenous to the Koblitz
    /// curve.
    pub in_koblitz_class: bool,
    /// Targets tried.
    pub targets: u32,
    /// Targets that were not decomposable over the factor base — the ones on
    /// which `D*` is defined.
    pub refutable_targets: u32,
    /// `D*` histogram over the refutable targets.
    pub d_star_hist: BTreeMap<u32, u32>,
    /// First-fall-degree histogram over the same targets.
    pub first_fall_hist: BTreeMap<u32, u32>,
}

impl CurveRow {
    /// Mean `D*`, or `None` when every target was decomposable.
    pub fn d_star_mean(&self) -> Option<f64> {
        hist_mean(&self.d_star_hist)
    }
    /// Largest `D*` seen — the degree an attacker would have to budget for.
    pub fn d_star_max(&self) -> Option<u32> {
        self.d_star_hist.keys().max().copied()
    }
}

fn hist_mean(h: &BTreeMap<u32, u32>) -> Option<f64> {
    let total: u32 = h.values().sum();
    if total == 0 {
        return None;
    }
    let sum: u64 = h.iter().map(|(d, c)| *d as u64 * *c as u64).sum();
    Some(sum as f64 / total as f64)
}

/// Result of sweeping every curve over `F_{2^n}`.
#[derive(Clone, Debug)]
pub struct SweepSummary {
    pub n: u32,
    pub l: u32,
    pub num_vars: u32,
    pub d_max: u32,
    /// Number of curves swept: `2^n − 1`, every `a₆ ≠ 0`.
    pub curves: usize,
    /// Curves with at least one refutable target.
    pub curves_measured: usize,
    /// Pooled `D*` histogram over every (curve, target) cell.
    pub pooled_d_star: BTreeMap<u32, u32>,
    /// Pooled first-fall histogram.
    pub pooled_first_fall: BTreeMap<u32, u32>,
    /// Distinct per-curve mean `D*` values, each with how many curves hit it.
    pub per_curve_mean_spectrum: BTreeMap<String, usize>,
    /// Curves whose twist lies in the Koblitz class, by exact trace.
    pub koblitz_class_members: Option<usize>,
    /// The class size predicted by [`koblitz_isogeny_class`], for
    /// cross-validation against `koblitz_class_members`.
    pub predicted_class_size: BigInt,
    /// Every row, in `a₆` order.
    pub rows: Vec<CurveRow>,
}

impl SweepSummary {
    /// Smallest `D*` anywhere in the sweep — the floor of Boundary C, and a
    /// lower bound for every isogeny-reachable curve by containment.
    pub fn min_d_star(&self) -> Option<u32> {
        self.pooled_d_star.keys().min().copied()
    }
    pub fn max_d_star(&self) -> Option<u32> {
        self.pooled_d_star.keys().max().copied()
    }
    /// True iff `D*` took the same value on every measured cell.
    ///
    /// This is **not** what Boundary C predicts, and in practice it is false:
    /// `C` governs the leading forms, while `D*` is an affine quantity the
    /// curve does move (`{2, 3, 4}` over all 255 curves at `n = 8`).  The
    /// predicate is kept because a flat sweep would mean the instrument had
    /// stopped discriminating, which is worth being able to detect.
    pub fn d_star_is_constant(&self) -> bool {
        self.pooled_d_star.len() == 1
    }
    /// `D*` of the Koblitz curve itself (`a₆ = 1`), the baseline any
    /// isogenous curve has to beat.
    pub fn koblitz_row(&self) -> Option<&CurveRow> {
        self.rows.iter().find(|r| r.a6 == 1)
    }
}

/// Options for [`exhaustive_a6_sweep`].
#[derive(Clone, Debug)]
pub struct SweepOptions {
    /// Extension degree.
    pub n: u32,
    /// Factor-base subspace dimension `l`; `V = ⟨1, z, …, z^{l−1}⟩`.
    pub l: u32,
    /// Macaulay degree cap.
    pub d_max: u32,
    /// How many targets `x_R` to try per curve.  Targets are drawn from a
    /// fixed deterministic list so that every curve sees the *same* targets
    /// — `a₆` is then the only input that varies.
    pub targets: u32,
    /// Compute exact traces (cost `O(4^n)` for the whole sweep).  Needed to
    /// cross-validate the class-size formula; skip it at larger `n`.
    pub exact_traces: bool,
}

/// Sweep **every** curve `y² + xy = x³ + a₆` over `F_{2^n}` — all `2^n − 1`
/// choices of `a₆` — measuring `D*` of the descended `S₃` system on a fixed
/// list of targets.
///
/// This is the containment measurement behind Boundary C: the set of
/// systems reachable by isogeny from any particular curve is a *subset* of
/// what this sweep covers, so a flat histogram here rules the lever out for
/// every isogeny class over `F_{2^n}` at once, without enumerating any of
/// them.
pub fn exhaustive_a6_sweep(opts: &SweepOptions, irr: &IrreduciblePoly) -> SweepSummary {
    let n = opts.n;
    assert!(n <= 24, "the sweep is 2^n curves; keep n small");
    assert!(opts.l >= 1 && opts.l <= n, "need 1 ≤ l ≤ n");
    let num_vars = 2 * opts.l;

    // Targets: the first `targets` field elements above the factor-base
    // subspace, so that a target is not trivially inside `V`.
    let target_values: Vec<F2mElement> = (0..opts.targets)
        .map(|i| f2m_from_u64((1u64 << opts.l) + i as u64, n))
        .collect();

    let traces = if opts.exact_traces {
        Some(all_traces(n, irr))
    } else {
        None
    };
    let koblitz_t = koblitz_trace(n);
    let koblitz_t_i128: i128 = koblitz_t
        .to_string()
        .parse()
        .expect("trace fits in i128 for small n");

    let mut rows = Vec::with_capacity((1usize << n) - 1);
    let mut pooled_d_star: BTreeMap<u32, u32> = BTreeMap::new();
    let mut pooled_first_fall: BTreeMap<u32, u32> = BTreeMap::new();
    let mut per_curve_mean_spectrum: BTreeMap<String, usize> = BTreeMap::new();
    let mut curves_measured = 0usize;
    let mut class_members = 0usize;

    for a6_int in 1u64..(1u64 << n) {
        let a6 = f2m_from_u64(a6_int, n);
        let j = a6
            .flt_inverse(irr)
            .expect("a₆ ≠ 0 is invertible")
            .to_biguint();
        let j_u64: u64 = j.to_u64_digits().first().copied().unwrap_or(0);

        let (order, trace) = match &traces {
            Some(t) => {
                let cnt = t[a6_int as usize];
                let q = 1i128 << n;
                (Some(cnt), Some(q + 1 - cnt))
            }
            None => (None, None),
        };
        let in_class = match trace {
            Some(t) => t.abs() == koblitz_t_i128.abs(),
            None => false,
        };
        if in_class {
            class_members += 1;
        }

        let mut d_star_hist: BTreeMap<u32, u32> = BTreeMap::new();
        let mut first_fall_hist: BTreeMap<u32, u32> = BTreeMap::new();
        let mut refutable = 0u32;
        for x3 in &target_values {
            // `D*` is the degree at which the Macaulay matrix proves the
            // system unsatisfiable, so it is only defined on targets that
            // do not decompose over the factor base.
            if is_decomposable(n, opts.l, irr, &a6, x3) {
                continue;
            }
            refutable += 1;
            let eqs = weil_descend_s3_subspace(n, opts.l, irr, &a6, x3);
            let (ff, dstar, _) = refutation_scan(&eqs, num_vars, opts.d_max);
            if let Some(d) = dstar {
                *d_star_hist.entry(d).or_insert(0) += 1;
                *pooled_d_star.entry(d).or_insert(0) += 1;
            }
            if let Some(d) = ff {
                *first_fall_hist.entry(d).or_insert(0) += 1;
                *pooled_first_fall.entry(d).or_insert(0) += 1;
            }
        }
        if !d_star_hist.is_empty() {
            curves_measured += 1;
            let mean = hist_mean(&d_star_hist).unwrap();
            *per_curve_mean_spectrum
                .entry(format!("{mean:.4}"))
                .or_insert(0) += 1;
        }

        rows.push(CurveRow {
            a6: a6_int,
            j: j_u64,
            order,
            trace,
            in_koblitz_class: in_class,
            targets: opts.targets,
            refutable_targets: refutable,
            d_star_hist,
            first_fall_hist,
        });
    }

    SweepSummary {
        n,
        l: opts.l,
        num_vars,
        d_max: opts.d_max,
        curves: rows.len(),
        curves_measured,
        pooled_d_star,
        pooled_first_fall,
        per_curve_mean_spectrum,
        koblitz_class_members: traces.as_ref().map(|_| class_members),
        predicted_class_size: koblitz_isogeny_class(n, 1_000_000).class_size,
        rows,
    }
}

/// `#E_{a₆}(F_{2^n})` for every `a₆`, indexed by `a₆` as an integer.
///
/// Uses the Artin–Schreier count: with `y = xu` for `x ≠ 0` the curve
/// equation becomes `u² + u = x + a₆/x²`, which has two solutions when
/// `Tr(x + a₆/x²) = 0` and none otherwise.  Adding the point `(0, √a₆)`
/// and the point at infinity,
///
/// ```text
///   #E_{a₆} = 2 + 2 · #{ x ≠ 0 : Tr(x + a₆ x^{−2}) = 0 }.
/// ```
///
/// Cost is `O(4^n)` field multiplications in total, so this is for the
/// small-`n` cross-validation only.
pub fn all_traces(n: u32, irr: &IrreduciblePoly) -> Vec<i128> {
    let size = 1usize << n;
    // Precompute x^{-2} and Tr(x) for every x ≠ 0.
    let mut inv_sq = vec![0u64; size];
    let mut tr_x = vec![false; size];
    for x_int in 1..size as u64 {
        let x = f2m_from_u64(x_int, n);
        let inv = x.flt_inverse(irr).expect("x ≠ 0");
        let is = inv.square(irr);
        inv_sq[x_int as usize] = f2m_to_u64(&is);
        tr_x[x_int as usize] = f2m_trace(&x, n, irr);
    }

    let mut out = vec![0i128; size];
    for a6_int in 1..size as u64 {
        let a6 = f2m_from_u64(a6_int, n);
        let mut hits = 0i128;
        for x_int in 1..size as u64 {
            let t = a6.mul(&f2m_from_u64(inv_sq[x_int as usize], n), irr);
            let bit = f2m_trace(&t, n, irr) ^ tr_x[x_int as usize];
            if !bit {
                hits += 1;
            }
        }
        out[a6_int as usize] = 2 + 2 * hits;
    }
    out
}

/// `Tr_{F_{2^n}/F_2}(v) = v + v² + … + v^{2^{n−1}}`, as a bit.
pub fn f2m_trace(v: &F2mElement, n: u32, irr: &IrreduciblePoly) -> bool {
    let mut acc = v.clone();
    let mut tr = v.clone();
    for _ in 1..n {
        acc = acc.square(irr);
        tr = tr.add(&acc);
    }
    !tr.is_zero()
}

fn f2m_from_u64(v: u64, n: u32) -> F2mElement {
    let bits: Vec<u32> = (0..n).filter(|i| (v >> i) & 1 == 1).collect();
    F2mElement::from_bit_positions(&bits, n)
}

fn f2m_to_u64(v: &F2mElement) -> u64 {
    v.to_biguint().to_u64_digits().first().copied().unwrap_or(0)
}

// ── Part D: the mechanism, and the curve-effect test ────────────────

/// Measure one curve on a fixed target list.  Returns
/// `(D* histogram, first-fall histogram, refutable target count)`.
///
/// `D*` is only defined on targets that do **not** decompose over the
/// factor base — a decomposable target makes the system satisfiable, so
/// there is nothing to refute — and decomposability depends on `a₆`, so the
/// refutable count is reported rather than assumed.
pub fn measure_curve(
    n: u32,
    l: u32,
    d_max: u32,
    irr: &IrreduciblePoly,
    a6: &F2mElement,
    targets: &[F2mElement],
) -> (BTreeMap<u32, u32>, BTreeMap<u32, u32>, u32) {
    let num_vars = 2 * l;
    let mut d_star = BTreeMap::new();
    let mut first_fall = BTreeMap::new();
    let mut refutable = 0u32;
    for x3 in targets {
        if is_decomposable(n, l, irr, a6, x3) {
            continue;
        }
        refutable += 1;
        let eqs = weil_descend_s3_subspace(n, l, irr, a6, x3);
        let (ff, ds) = {
            let (ff, ds, _) = refutation_scan(&eqs, num_vars, d_max);
            (ff, ds)
        };
        if let Some(d) = ds {
            *d_star.entry(d).or_insert(0) += 1;
        }
        if let Some(d) = ff {
            *first_fall.entry(d).or_insert(0) += 1;
        }
    }
    (d_star, first_fall, refutable)
}

/// Why some curves refute at degree 2 and others do not, for one target.
///
/// The derivation is in the module docs: with `f_i = h_i + c_i`, the left
/// null space `S = {λ : Σ λ_i h_i = 0}` of the **curve-independent** leading
/// parts controls everything, because `Σ λ_i f_i = ⟨λ, c⟩` is a constant for
/// `λ ∈ S`.  Hence the exact criterion
///
/// ```text
///   D* = 2   ⟺   ∃ λ ∈ S with ⟨λ, c⟩ = 1   ⟺   c ∉ S^⊥
/// ```
///
/// and the constant vector `c` of the descended `S₃` system is simply the
/// coordinate vector of `a₆` (because `S₃(0, 0, x_R) = a₆`).  So the curves
/// that refute at the Nullstellensatz floor are exactly those whose `a₆`
/// escapes a **fixed subspace `S^⊥` determined by the target alone**.
///
/// This is checked as a per-curve equivalence rather than as a density,
/// because the density is conditioned by decomposability: a target that
/// decomposes makes the system satisfiable, and every such curve necessarily
/// has `c ∈ S^⊥`, so filtering on refutability enriches the complement.
#[derive(Clone, Debug)]
pub struct MechanismRow {
    /// The target `x_R`, as an integer.
    pub target: u64,
    /// `dim S` — curve-independent, by Boundary C.
    pub leading_nullity: u32,
    /// Curves (`a₆ ≠ 0`) whose constant vector escapes `S^⊥`.
    pub outside_perp: usize,
    /// `(2^n − 2^{n−dim S}) / (2^n − 1)` — the exact density of the above.
    pub outside_perp_density: f64,
    /// Curves measured to refute at degree 2.
    pub refuted_at_2: usize,
    /// Curves where the criterion and the measurement disagree.  The
    /// mechanism predicts `0`.
    pub mismatches: usize,
    /// Curves whose system was refutable at all (target not decomposable).
    pub curves_refutable: usize,
    /// True iff the constant terms of the descended system are the
    /// coordinate vector of `a₆`, as the derivation claims.
    pub constant_is_a6: bool,
}

/// Compute `S`, then check the exact per-curve criterion against the
/// measured refutation degree over **every** curve over `F_{2^n}`.
pub fn syzygy_mechanism(
    n: u32,
    l: u32,
    d_max: u32,
    irr: &IrreduciblePoly,
    x3: &F2mElement,
) -> MechanismRow {
    // The leading parts do not depend on a₆, so any curve exhibits them.
    let probe = F2mElement::one(n);
    let eqs = weil_descend_s3_subspace(n, l, irr, &probe, x3);
    let basis = leading_part_left_nullspace(&eqs);
    let nullity = basis.len() as u32;

    let mut outside = 0usize;
    let mut refuted = 0usize;
    let mut mismatches = 0usize;
    let mut refutable = 0usize;
    let mut constant_is_a6 = true;

    for a6_int in 1u64..(1u64 << n) {
        let a6 = f2m_from_u64(a6_int, n);
        let sys = weil_descend_s3_subspace(n, l, irr, &a6, x3);
        // c_i = constant term of equation i.
        let c: Vec<bool> = sys
            .iter()
            .map(|f| f.coeffs.first().copied().unwrap_or(false))
            .collect();
        for (i, bit) in c.iter().enumerate() {
            if *bit != ((a6_int >> i) & 1 == 1) {
                constant_is_a6 = false;
            }
        }
        // Criterion: ∃ λ ∈ S with ⟨λ, c⟩ = 1.
        let escapes = basis
            .iter()
            .any(|lam| lam.iter().zip(c.iter()).filter(|(a, b)| **a && **b).count() % 2 == 1);
        if escapes {
            outside += 1;
        }
        let (hist, _, r) = measure_curve(n, l, d_max, irr, &a6, std::slice::from_ref(x3));
        if r == 0 {
            // Satisfiable: nothing to refute.  The criterion must agree that
            // the constant did not escape, or the mechanism is wrong.
            if escapes {
                mismatches += 1;
            }
            continue;
        }
        refutable += 1;
        let at_2 = hist.contains_key(&2);
        if at_2 {
            refuted += 1;
        }
        if at_2 != escapes {
            mismatches += 1;
        }
    }

    let total = (1u64 << n) as f64 - 1.0;
    let perp = 2f64.powi((n - nullity) as i32);
    MechanismRow {
        target: f2m_to_u64(x3),
        leading_nullity: nullity,
        outside_perp: outside,
        outside_perp_density: (2f64.powi(n as i32) - perp) / total,
        refuted_at_2: refuted,
        mismatches,
        curves_refutable: refutable,
        constant_is_a6,
    }
}

/// A basis of `{ λ ∈ F_2^{#eqs} : Σ λ_i · (degree-≥1 part of f_i) = 0 }`.
///
/// Gaussian elimination over `F_2` on `[ leading coefficients | identity ]`;
/// the rows whose left half clears are the null-space vectors.
pub fn leading_part_left_nullspace(eqs: &[F2BoolPoly]) -> Vec<Vec<bool>> {
    let m = eqs.len();
    let width = eqs.iter().map(|e| e.coeffs.len()).max().unwrap_or(1);
    // Drop the constant column; augment each row with an identity tag so the
    // elimination records which combination produced it.
    let cols = width.saturating_sub(1);
    let mut rows: Vec<(Vec<bool>, Vec<bool>)> = Vec::with_capacity(m);
    for (i, e) in eqs.iter().enumerate() {
        let mut left = vec![false; cols];
        for (idx, bit) in e.coeffs.iter().enumerate().skip(1) {
            if *bit {
                left[idx - 1] = true;
            }
        }
        let mut tag = vec![false; m];
        tag[i] = true;
        rows.push((left, tag));
    }

    let mut rank = 0usize;
    for col in 0..cols {
        let Some(piv) = (rank..rows.len()).find(|&i| rows[i].0[col]) else {
            continue;
        };
        rows.swap(rank, piv);
        for i in 0..rows.len() {
            if i != rank && rows[i].0[col] {
                for k in 0..cols {
                    rows[i].0[k] ^= rows[rank].0[k];
                }
                for k in 0..m {
                    rows[i].1[k] ^= rows[rank].1[k];
                }
            }
        }
        rank += 1;
        if rank == rows.len() {
            break;
        }
    }
    rows.into_iter()
        .filter(|(left, _)| !left.iter().any(|b| *b))
        .map(|(_, tag)| tag)
        .collect()
}

/// `dim S` — the nullity of the curve-independent leading parts.
pub fn leading_part_nullity(eqs: &[F2BoolPoly]) -> u32 {
    leading_part_left_nullspace(eqs).len() as u32
}

/// Curves that sit on the `D* = 2` floor for **every** one of `t`
/// consecutive targets, and the Koblitz curve's mean for comparison.
///
/// This is the statistic that decides lever L5, and it is the direct
/// consequence of the criterion in [`syzygy_mechanism`]: the "good" set is
/// the complement of a subspace fixed by the *target*, so a curve has to
/// escape `S^⊥(x_R)` for every `x_R` at once.  If goodness were a property of
/// the curve the count would be flat in `t`; if it is a property of the
/// `(curve, target)` pair the count decays and reaches zero.
#[derive(Clone, Debug)]
pub struct FloorSurvivors {
    pub n: u32,
    pub l: u32,
    pub targets: u32,
    /// Curves swept: `2^n − 1`.
    pub curves: usize,
    /// Every `a₆` whose system refuted at degree 2 on all `targets`.
    pub survivors: Vec<u64>,
    /// Mean `D*` of the Koblitz curve `a₆ = 1` over the same targets.
    pub koblitz_mean: f64,
}

/// Sweep every curve over `F_{2^n}` and keep the ones that never leave the
/// `D* = 2` floor across `targets` consecutive targets.
pub fn uniform_floor_survivors(
    n: u32,
    l: u32,
    d_max: u32,
    targets: u32,
    irr: &IrreduciblePoly,
) -> FloorSurvivors {
    let base = 1u64 << l;
    let tg: Vec<F2mElement> = (0..targets)
        .map(|i| f2m_from_u64(base + i as u64, n))
        .collect();
    let mut survivors = Vec::new();
    let mut koblitz_mean = f64::NAN;
    for a6_int in 1u64..(1u64 << n) {
        let a6 = f2m_from_u64(a6_int, n);
        let (hist, _, refutable) = measure_curve(n, l, d_max, irr, &a6, &tg);
        if a6_int == 1 {
            koblitz_mean = hist_mean(&hist).unwrap_or(f64::NAN);
        }
        // On the floor everywhere: at least one refutable target, and every
        // refutation happened at degree 2.
        if refutable > 0 && hist.len() == 1 && hist.contains_key(&2) {
            survivors.push(a6_int);
        }
    }
    FloorSurvivors {
        n,
        l,
        targets,
        curves: (1usize << n) - 1,
        survivors,
        koblitz_mean,
    }
}

/// Is the curve the explanatory variable for `D*`, or is the target?
///
/// Selection and holdout target sets are disjoint.  A lever that is real
/// keeps its margin on the holdout; a winner's curse does not.
#[derive(Clone, Debug)]
pub struct CurveEffectTest {
    pub n: u32,
    pub l: u32,
    pub d_max: u32,
    pub curves: usize,
    pub targets_select: u32,
    pub targets_holdout: u32,
    /// Pooled mean `D*` over every (curve, selection target) cell.
    pub pooled_mean: f64,
    /// Pooled variance of `D*` over the same cells.
    pub pooled_var: f64,
    /// Observed variance of the per-curve mean `D*`.
    pub between_curve_var: f64,
    /// `pooled_var / harmonic mean of the per-curve target counts` — the
    /// between-curve variance expected if the curve explains nothing.
    pub no_effect_var: f64,
    /// `between_curve_var / no_effect_var`.  `≈ 1` means no curve effect;
    /// `≈ targets_select` would mean `D*` is a deterministic function of the
    /// curve.
    pub variance_ratio: f64,
    /// The curve that looked best on the selection set.
    pub best_a6: u64,
    pub best_select_mean: f64,
    /// The same curve, re-measured on the disjoint holdout set.
    pub best_holdout_mean: f64,
    /// The Koblitz curve `a₆ = 1`, the baseline an isogeny would move away
    /// from.
    pub koblitz_select_mean: f64,
    pub koblitz_holdout_mean: f64,
    /// `koblitz − best` on each set.  Positive means the selected curve is
    /// genuinely easier.
    pub margin_select: f64,
    pub margin_holdout: f64,
    /// Curves whose mean `D*` sits exactly on the `D* = 2`
    /// Nullstellensatz floor, on the selection set and on the holdout set.
    pub curves_at_floor_select: usize,
    pub curves_at_floor_holdout: usize,
    /// Curves at the floor on **both** disjoint sets.  This is the count
    /// that has to stay positive for the lever to exist; it decays
    /// geometrically in the target count if the mechanism above is right.
    pub curves_at_floor_both: usize,
}

/// Run the curve-effect test over **every** curve over `F_{2^n}`.
pub fn curve_effect_test(
    n: u32,
    l: u32,
    d_max: u32,
    targets_select: u32,
    targets_holdout: u32,
    irr: &IrreduciblePoly,
) -> CurveEffectTest {
    // Disjoint target lists, both outside the factor-base subspace.
    let base = 1u64 << l;
    let sel: Vec<F2mElement> = (0..targets_select)
        .map(|i| f2m_from_u64(base + i as u64, n))
        .collect();
    let hold: Vec<F2mElement> = (0..targets_holdout)
        .map(|i| f2m_from_u64(base + (targets_select + i) as u64, n))
        .collect();

    let mut per_curve: Vec<(u64, Option<f64>, Option<f64>)> = Vec::new();
    let mut cells: Vec<f64> = Vec::new();
    let mut target_counts: Vec<u32> = Vec::new();
    for a6_int in 1u64..(1u64 << n) {
        let a6 = f2m_from_u64(a6_int, n);
        let (hs, _, _) = measure_curve(n, l, d_max, irr, &a6, &sel);
        let (hh, _, _) = measure_curve(n, l, d_max, irr, &a6, &hold);
        for (d, c) in &hs {
            for _ in 0..*c {
                cells.push(*d as f64);
            }
        }
        let cnt: u32 = hs.values().sum();
        if cnt > 0 {
            target_counts.push(cnt);
        }
        per_curve.push((a6_int, hist_mean(&hs), hist_mean(&hh)));
    }

    let pooled_mean = cells.iter().sum::<f64>() / cells.len().max(1) as f64;
    let pooled_var =
        cells.iter().map(|v| (v - pooled_mean).powi(2)).sum::<f64>() / cells.len().max(1) as f64;
    let means: Vec<f64> = per_curve.iter().filter_map(|(_, m, _)| *m).collect();
    let mm = means.iter().sum::<f64>() / means.len().max(1) as f64;
    let between_curve_var =
        means.iter().map(|v| (v - mm).powi(2)).sum::<f64>() / means.len().max(1) as f64;
    // Harmonic mean of per-curve target counts: the effective sample size of
    // a per-curve mean when the counts are unequal.
    let harmonic = if target_counts.is_empty() {
        1.0
    } else {
        target_counts.len() as f64 / target_counts.iter().map(|c| 1.0 / *c as f64).sum::<f64>()
    };
    let no_effect_var = pooled_var / harmonic;

    let (best_a6, best_select_mean, best_holdout_mean) = per_curve
        .iter()
        .filter(|(_, m, h)| m.is_some() && h.is_some())
        .min_by(|a, b| a.1.unwrap().partial_cmp(&b.1.unwrap()).unwrap())
        .map(|(a, m, h)| (*a, m.unwrap(), h.unwrap()))
        .unwrap_or((0, f64::NAN, f64::NAN));
    let kob = per_curve.iter().find(|(a, _, _)| *a == 1);
    let koblitz_select_mean = kob.and_then(|(_, m, _)| *m).unwrap_or(f64::NAN);
    let koblitz_holdout_mean = kob.and_then(|(_, _, h)| *h).unwrap_or(f64::NAN);

    let at_floor = |v: Option<f64>| v.map(|m| (m - 2.0).abs() < 1e-12).unwrap_or(false);
    let curves_at_floor_select = per_curve.iter().filter(|(_, m, _)| at_floor(*m)).count();
    let curves_at_floor_holdout = per_curve.iter().filter(|(_, _, h)| at_floor(*h)).count();
    let curves_at_floor_both = per_curve
        .iter()
        .filter(|(_, m, h)| at_floor(*m) && at_floor(*h))
        .count();

    CurveEffectTest {
        n,
        l,
        d_max,
        curves: per_curve.len(),
        targets_select,
        targets_holdout,
        pooled_mean,
        pooled_var,
        between_curve_var,
        no_effect_var,
        variance_ratio: between_curve_var / no_effect_var.max(f64::MIN_POSITIVE),
        best_a6,
        best_select_mean,
        best_holdout_mean,
        koblitz_select_mean,
        koblitz_holdout_mean,
        margin_select: koblitz_select_mean - best_select_mean,
        margin_holdout: koblitz_holdout_mean - best_holdout_mean,
        curves_at_floor_select,
        curves_at_floor_holdout,
        curves_at_floor_both,
    }
}

// ── Part E: what the residual per-curve variation actually is ───────

/// Spearman rank correlation, with ties averaged.
pub fn spearman(xs: &[f64], ys: &[f64]) -> f64 {
    fn ranks(v: &[f64]) -> Vec<f64> {
        let mut idx: Vec<usize> = (0..v.len()).collect();
        idx.sort_by(|a, b| v[*a].partial_cmp(&v[*b]).unwrap());
        let mut r = vec![0.0; v.len()];
        let mut i = 0;
        while i < idx.len() {
            let mut j = i;
            while j + 1 < idx.len() && v[idx[j + 1]] == v[idx[i]] {
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
    let (rx, ry) = (ranks(xs), ranks(ys));
    let n = xs.len() as f64;
    let mx = rx.iter().sum::<f64>() / n;
    let my = ry.iter().sum::<f64>() / n;
    let mut num = 0.0;
    let mut dx = 0.0;
    let mut dy = 0.0;
    for i in 0..xs.len() {
        num += (rx[i] - mx) * (ry[i] - my);
        dx += (rx[i] - mx).powi(2);
        dy += (ry[i] - my).powi(2);
    }
    if dx == 0.0 || dy == 0.0 {
        return 0.0;
    }
    num / (dx.sqrt() * dy.sqrt())
}

/// Why per-curve `D*` statistics vary at all, once the exact criterion is
/// known.
///
/// The criterion of [`syzygy_mechanism`] partitions the targets of a given
/// curve three ways:
///
/// 1. `a₆ ∉ S^⊥(x_R)` — refutes at the `D* = 2` floor.
/// 2. `a₆ ∈ S^⊥(x_R)` and the target **decomposes** — satisfiable, so `D*` is
///    undefined and the cell is skipped.  For an attacker this is a *success*:
///    a decomposition is a relation.
/// 3. `a₆ ∈ S^⊥(x_R)` and it does not decompose — refutes **above** the floor.
///    This is the only case that costs an attacker anything.
///
/// Case 3 is therefore squeezed by case 2: a curve whose factor base
/// decomposes more targets has fewer chances to land above the floor.  If that
/// is what drives the residual variation, then the "curve effect" on the
/// solving degree is really variation in **relation yield** — a different
/// quantity, and one where more yield helps the attacker for reasons unrelated
/// to `d_reg`.
#[derive(Clone, Debug)]
pub struct YieldExplanation {
    pub n: u32,
    pub l: u32,
    pub targets: usize,
    pub curves: usize,
    /// Per curve: how many targets decompose (case 2).
    pub decomposable_min: u32,
    pub decomposable_max: u32,
    pub decomposable_mean: f64,
    /// Per curve: how many refute above the floor (case 3).
    pub above_floor_min: u32,
    pub above_floor_max: u32,
    pub above_floor_mean: f64,
    /// `ρ_s` between the case-2 count and the case-3 count.  The hypothesis
    /// predicts a clearly negative value.
    pub rho_count: f64,
    /// `ρ_s` between the case-2 count and the case-3 *rate* (per refutable
    /// target), which removes the mechanical "fewer refutable targets means
    /// fewer bad ones" effect.
    pub rho_rate: f64,
    /// Curves with no above-floor target at all, over every target in the
    /// field — the uniformly-easy curves an isogeny walk would need.
    pub zero_above_floor: Vec<u64>,
}

/// Measure the case-2 / case-3 relationship over **every** curve and **every**
/// target above the factor-base subspace.
pub fn yield_explanation(n: u32, l: u32, d_max: u32, irr: &IrreduciblePoly) -> YieldExplanation {
    let base = 1u64 << l;
    let max_t = (1u64 << n) - base;
    let targets: Vec<F2mElement> = (0..max_t).map(|i| f2m_from_u64(base + i, n)).collect();

    let mut decomposable = Vec::with_capacity((1 << n) - 1);
    let mut above = Vec::with_capacity((1 << n) - 1);
    let mut rate = Vec::with_capacity((1 << n) - 1);
    let mut zero_above_floor = Vec::new();

    for a6_int in 1u64..(1u64 << n) {
        let a6 = f2m_from_u64(a6_int, n);
        let d = targets
            .iter()
            .filter(|x| is_decomposable(n, l, irr, &a6, x))
            .count() as u32;
        let (hist, _, refutable) = measure_curve(n, l, d_max, irr, &a6, &targets);
        let ab: u32 = hist.iter().filter(|(k, _)| **k > 2).map(|(_, c)| *c).sum();
        decomposable.push(d as f64);
        above.push(ab as f64);
        rate.push(if refutable > 0 {
            ab as f64 / refutable as f64
        } else {
            0.0
        });
        if ab == 0 {
            zero_above_floor.push(a6_int);
        }
    }

    let mean = |v: &[f64]| v.iter().sum::<f64>() / v.len() as f64;
    YieldExplanation {
        n,
        l,
        targets: targets.len(),
        curves: decomposable.len(),
        decomposable_min: decomposable.iter().cloned().fold(f64::MAX, f64::min) as u32,
        decomposable_max: decomposable.iter().cloned().fold(0.0, f64::max) as u32,
        decomposable_mean: mean(&decomposable),
        above_floor_min: above.iter().cloned().fold(f64::MAX, f64::min) as u32,
        above_floor_max: above.iter().cloned().fold(0.0, f64::max) as u32,
        above_floor_mean: mean(&above),
        rho_count: spearman(&decomposable, &above),
        rho_rate: spearman(&decomposable, &rate),
        zero_above_floor,
    }
}

// ── Small numeric helpers ───────────────────────────────────────────

/// `log₂` of a positive `BigInt`, accurate enough for cost reporting.
pub fn log2_bigint(v: &BigInt) -> f64 {
    if v.is_zero() {
        return f64::NEG_INFINITY;
    }
    let bits = v.bits();
    if bits <= 52 {
        return (v.to_string().parse::<f64>().unwrap()).log2();
    }
    // Scale the top 52 bits and add back the shift.
    let shift = bits - 52;
    let top = v.clone() >> shift;
    let top_f: f64 = top.to_string().parse().unwrap();
    top_f.log2() + shift as f64
}

/// Miller–Rabin, deterministic for the sizes reached here.
pub fn is_probable_prime(n: &BigInt) -> bool {
    let two = BigInt::from(2u8);
    if n < &two {
        return false;
    }
    for p in [
        2u32, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53,
    ] {
        let bp = BigInt::from(p);
        if n == &bp {
            return true;
        }
        if (n % &bp).is_zero() {
            return false;
        }
    }
    let n_minus_1 = n - BigInt::one();
    let mut d = n_minus_1.clone();
    let mut s = 0u32;
    while (&d % &two).is_zero() {
        d /= &two;
        s += 1;
    }
    for a in [
        2u32, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53,
    ] {
        let a = BigInt::from(a);
        // A witness that is a multiple of `n` gives `x = 0`, which never
        // reaches `n - 1`, and would report a prime as composite.  The
        // trial-division prefix above now covers every base in this list, so
        // this guard is unreachable as the two lists stand; it is kept
        // because that is precisely the coupling that broke once — bases ran
        // to 53 while trial division stopped at 37, so 41, 43, 47 and 53
        // were reported composite — and extending one list without the other
        // must not be able to reintroduce it.  Skipping is sound rather than
        // merely convenient: it can only ever trigger at `n <= 53`, where
        // the retained bases 2..37 are the first twelve primes and
        // deterministic for every `n` below 3.317e24.
        if &a >= n {
            continue;
        }
        let mut x = a.modpow(&d, n);
        if x.is_one() || x == n_minus_1 {
            continue;
        }
        let mut composite = true;
        for _ in 0..s - 1 {
            x = (&x * &x) % n;
            if x == n_minus_1 {
                composite = false;
                break;
            }
        }
        if composite {
            return false;
        }
    }
    true
}

/// Pollard rho with Brent's cycle detection, bounded by `budget`
/// iterations.  Returns `None` when the budget is exhausted.
fn pollard_rho(n: &BigInt, budget: u64) -> Option<BigInt> {
    let two = BigInt::from(2u8);
    if (n % &two).is_zero() {
        return Some(two);
    }
    let mut c = BigInt::one();
    for _attempt in 0..16u32 {
        let mut x = BigInt::from(2u8);
        let mut y = x.clone();
        let mut d = BigInt::one();
        let mut steps = 0u64;
        while d.is_one() {
            steps += 1;
            if steps > budget {
                return None;
            }
            x = (&x * &x + &c) % n;
            y = (&y * &y + &c) % n;
            y = (&y * &y + &c) % n;
            d = (&x - &y).abs().gcd(n);
        }
        if &d != n {
            return Some(d);
        }
        c += BigInt::one();
    }
    None
}

/// Factor `v` completely: trial division by small primes, then Pollard rho.
/// The `bool` is `false` if a composite cofactor survived the budget, in
/// which case it is returned with exponent 1 and every derived class number
/// is a lower bound only.
pub fn factor_bigint(v: &BigInt, budget: u64) -> (Vec<(BigInt, u32)>, bool) {
    let mut out: Vec<(BigInt, u32)> = Vec::new();
    let mut rest = v.clone();
    if rest.is_one() {
        return (out, true);
    }
    let mut p: u64 = 2;
    while p < 100_000 {
        let bp = BigInt::from(p);
        if &bp * &bp > rest {
            break;
        }
        let mut e = 0u32;
        while (&rest % &bp).is_zero() {
            rest /= &bp;
            e += 1;
        }
        if e > 0 {
            out.push((bp, e));
        }
        p += if p == 2 { 1 } else { 2 };
    }
    let mut complete = true;
    let mut stack = vec![rest];
    while let Some(m) = stack.pop() {
        if m.is_one() {
            continue;
        }
        if is_probable_prime(&m) {
            bump(&mut out, m);
            continue;
        }
        match pollard_rho(&m, budget) {
            Some(d) => {
                let other = &m / &d;
                stack.push(d);
                stack.push(other);
            }
            None => {
                complete = false;
                bump(&mut out, m);
            }
        }
    }
    out.sort_by(|a, b| a.0.cmp(&b.0));
    (out, complete)
}

fn bump(out: &mut Vec<(BigInt, u32)>, p: BigInt) {
    if let Some(slot) = out.iter_mut().find(|(q, _)| *q == p) {
        slot.1 += 1;
    } else {
        out.push((p, 1));
    }
}

// ── Tests ───────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::binary_semaev::binary_semaev_s4;

    /// The published ECC2K-130 order: `#E = 4 · r` with `r` the 130-bit
    /// prime the Certicom challenge quotes.  This pins the whole derivation
    /// — trace, order and conductor all come from the same recursion.
    #[test]
    fn ecc2k130_order_matches_the_published_challenge() {
        let order = koblitz_order(131);
        let r: BigInt = "680564733841876926932320129493409985129".parse().unwrap();
        assert_eq!(order, BigInt::from(4u8) * &r);
        assert!(is_probable_prime(&r));
        assert_eq!(
            koblitz_trace(131),
            "-22283658519494248867".parse::<BigInt>().unwrap()
        );
    }

    /// `disc(Z[π]) = t² − 4q = c²·(−7)` — the identity that makes `|b|` the
    /// conductor, checked independently of how it was computed.
    #[test]
    fn conductor_reproduces_the_discriminant() {
        for n in [11u32, 31, 41, 131] {
            let t = koblitz_trace(n);
            let q = BigInt::one() << n;
            let disc = &t * &t - BigInt::from(4u8) * &q;
            let c = koblitz_conductor(n);
            assert_eq!(disc, BigInt::from(CM_DISCRIMINANT) * &c * &c, "n = {n}");
        }
    }

    /// The conductor of ECC2K-130 factors as `263 · 146505763881528721`,
    /// both prime — Boundary B rests on this.
    #[test]
    fn ecc2k130_conductor_factors_into_two_primes() {
        let class = koblitz_isogeny_class(131, 5_000_000);
        assert!(class.fully_factored);
        assert_eq!(
            class.conductor,
            "38531015900842053623".parse::<BigInt>().unwrap()
        );
        let expect = vec![
            (BigInt::from(263u32), 1u32),
            ("146505763881528721".parse::<BigInt>().unwrap(), 1u32),
        ];
        assert_eq!(class.conductor_factors, expect);
        assert_eq!(
            class.class_size,
            "38531015900842054149".parse::<BigInt>().unwrap()
        );
        // 263 splits, p is inert.
        assert_eq!(class.primes[0].kronecker, 1);
        assert_eq!(class.primes[0].descending_from_crater, BigInt::from(262u32));
        assert_eq!(class.primes[1].kronecker, -1);
    }

    /// Boundary A: the class has more vertices than ρ has group operations —
    /// against ρ *with* its automorphism speedup and against plain ρ, because
    /// the margin differs by four bits between them and only the sign is
    /// load-bearing.
    #[test]
    fn class_is_larger_than_the_rho_reference() {
        let class = koblitz_isogeny_class(131, 5_000_000);
        let log2_class = class.log2_class_size();
        assert!((log2_class - 65.06).abs() < 0.02, "got 2^{log2_class}");

        // √(πr/2m): the walk is on r/m classes, so m enters once and once only.
        let r = 680564733841876926932320129493409985129f64;
        let log2_rho = |m: f64| (std::f64::consts::PI * r / (2.0 * m)).sqrt().log2();

        let aut = log2_rho(262.0); // negation × 131 Frobenius powers
        let plain = log2_rho(1.0);
        assert!((aut - 60.81).abs() < 0.02, "aut rho 2^{aut}");
        assert!((plain - 64.83).abs() < 0.02, "plain rho 2^{plain}");
        // Pin the specific error this replaced: taking the m = 2 form and
        // dividing it by √262 double-counts negation and lands exactly half a
        // bit low.  If someone reintroduces that expression, this fires.
        let double_counted = log2_rho(2.0) - 0.5 * 262f64.log2();
        assert!(
            (aut - double_counted - 0.5).abs() < 0.01,
            "the double-counted form should sit exactly 0.5 bits below the \
             correct one; got {:.4} vs {:.4}",
            double_counted,
            aut
        );

        assert!(
            log2_class > aut,
            "class 2^{log2_class:.2} vs aut rho 2^{aut:.2}"
        );
        assert!(
            log2_class > plain,
            "class 2^{log2_class:.2} vs plain rho 2^{plain:.2}"
        );
    }

    /// Boundary B: only 263 vertices are reachable with a feasible isogeny
    /// degree, and the search over them terminates.
    #[test]
    fn feasible_reach_is_263_curves() {
        let class = koblitz_isogeny_class(131, 5_000_000);
        let reach = class.reach_within_degree(&BigInt::from(1_000_000u32));
        assert_eq!(reach.reachable, BigInt::from(263u32));
        assert!(!reach.exhaustive, "the p-direction is still blocked");
        assert_eq!(reach.blocking_primes.len(), 1);
        assert!(reach.log2_fraction() < -56.0);
        // Budget above p covers everything.
        let all = class.reach_within_degree(&("146505763881528721".parse::<BigInt>().unwrap()));
        assert!(all.exhaustive);
        assert_eq!(all.reachable, class.class_size);
    }

    /// Boundary B, the small-`ℓ` half: for every prime below 263 the
    /// `ℓ`-isogeny graph of ECC2K-130 is a single vertex, so there is no
    /// small-degree walk to search.
    #[test]
    fn every_small_ell_graph_is_trivial() {
        let class = koblitz_isogeny_class(131, 5_000_000);
        for ell in [2u32, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 101, 257] {
            assert!(
                class.ell_graph_is_trivial(&BigInt::from(ell)),
                "ℓ = {ell} should have no non-trivial neighbour"
            );
        }
        assert!(!class.ell_graph_is_trivial(&BigInt::from(263u32)));
    }

    /// The class-size formula, cross-validated the hard way: count the
    /// curves over `F_{2^n}` whose trace matches by exact point counting,
    /// and compare with `Σ_{f|c} h(O_f)`.
    #[test]
    fn class_size_formula_matches_exact_point_counting() {
        for n in [5u32, 7, 9] {
            let irr = first_irreducible(n);
            let traces = all_traces(n, &irr);
            let t_n: i128 = koblitz_trace(n).to_string().parse().unwrap();
            let q = 1i128 << n;
            let matching = (1..(1usize << n))
                .filter(|&a6| {
                    let t = q + 1 - traces[a6];
                    t.abs() == t_n.abs()
                })
                .count();
            let predicted = koblitz_isogeny_class(n, 1_000_000).class_size;
            assert_eq!(
                BigInt::from(matching),
                predicted,
                "n = {n}: counted {matching} curves in the class"
            );
        }
    }

    /// Boundary C at `m = 2`, exactly: across curves the descended `S₃`
    /// system differs **only** in its constant terms.
    #[test]
    fn a6_moves_only_the_constant_term_of_the_descended_system() {
        let n = 8u32;
        let irr = first_irreducible(n);
        let x3 = f2m_from_u64(0b1010_1101, n);
        let a6s: Vec<F2mElement> = (1u64..=40).map(|v| f2m_from_u64(v, n)).collect();
        let w = leading_form_witness(n, 4, &irr, &x3, &a6s);
        assert!(w.degree_ge1_identical, "a₆ must not reach degree ≥ 1");
        assert_eq!(w.degrees_touched_by_a6, vec![0]);
        assert!(w.top_degree > *w.degrees_touched_by_a6.iter().max().unwrap());
    }

    /// Boundary C at `m = 3`: `S₄` is quadratic in `a₆` with exactly the
    /// coefficients the module documents, both of which have lower degree
    /// than the `a₆`-free leading part.
    #[test]
    fn s4_a6_expansion_is_quadratic_with_subleading_coefficients() {
        let n = 8u32;
        let irr = first_irreducible(n);
        for seed in [3u64, 29, 77, 145, 201] {
            let x1 = f2m_from_u64(seed.wrapping_mul(0x9E37).max(1) & 0xFF | 1, n);
            let x2 = f2m_from_u64(seed.wrapping_mul(0x5B7C).max(1) & 0xFF | 2, n);
            let x3 = f2m_from_u64(seed.wrapping_mul(0x1F3D).max(1) & 0xFF | 4, n);
            let xr = f2m_from_u64(seed.wrapping_mul(0xA13B).max(1) & 0xFF | 8, n);

            // Documented coefficients of the a₆-expansion.
            let a1 = x1.add(&x2).square(&irr);
            let b1 = x1.mul(&x2, &irr);
            let a2 = x3.add(&xr).square(&irr);
            let b2 = x3.mul(&xr, &irr);
            let c2_coeff = a1.add(&a2).square(&irr);
            let c1_coeff = a1
                .mul(&b2, &irr)
                .add(&a2.mul(&b1, &irr))
                .mul(&b1.add(&b2), &irr);
            let zero = F2mElement::zero(n);
            let c0 = binary_semaev_s4(&x1, &x2, &x3, &xr, &zero, &irr);

            for v in 1u64..=60 {
                let a6 = f2m_from_u64(v, n);
                let lhs = binary_semaev_s4(&x1, &x2, &x3, &xr, &a6, &irr);
                let rhs = c0
                    .add(&a6.mul(&c1_coeff, &irr))
                    .add(&a6.square(&irr).mul(&c2_coeff, &irr));
                assert_eq!(lhs, rhs, "S₄ a₆-expansion failed at seed {seed}, a₆ {v}");
            }
        }
    }

    /// The sweep is exhaustive over curves, and the Koblitz curve is not
    /// special within it.  `D*` is *not* constant — Boundary C governs the
    /// leading forms, and `D*` is an affine quantity the curve does move —
    /// so what is asserted here is coverage plus the class-size
    /// cross-validation, not flatness.
    #[test]
    fn exhaustive_sweep_covers_every_curve() {
        let n = 6u32;
        let irr = first_irreducible(n);
        let opts = SweepOptions {
            n,
            l: 3,
            d_max: 6,
            targets: 3,
            exact_traces: true,
        };
        let s = exhaustive_a6_sweep(&opts, &irr);
        assert_eq!(s.curves, (1usize << n) - 1, "every a₆ ≠ 0 must be swept");
        assert!(s.curves_measured > 0, "some target must refute");
        // D* is bounded below by the Nullstellensatz floor.
        assert_eq!(s.min_d_star(), Some(2));
        assert!(s.koblitz_row().is_some(), "a₆ = 1 is in the sweep");
        // Class-size cross-validation rides along.
        assert_eq!(
            BigInt::from(s.koblitz_class_members.unwrap()),
            s.predicted_class_size
        );
    }

    /// The derived mechanism, as an exact per-curve equivalence: the system
    /// refutes at the `D* = 2` floor **iff** the curve's `a₆` escapes the
    /// subspace `S^⊥` fixed by the target.  Checked over every curve.
    #[test]
    fn degree_two_refutation_matches_the_syzygy_criterion() {
        let n = 8u32;
        let irr = first_irreducible(n);
        for t in [1u64 << 4, (1u64 << 4) + 1, (1u64 << 4) + 5, 0xC3] {
            let x3 = f2m_from_u64(t, n);
            let row = syzygy_mechanism(n, 4, 6, &irr, &x3);
            assert!(row.constant_is_a6, "c must be the coordinate vector of a₆");
            assert_eq!(
                row.mismatches, 0,
                "target {t}: criterion disagreed with the solver on {} curves \
                 (dim S = {}, escaped {}, refuted-at-2 {})",
                row.mismatches, row.leading_nullity, row.outside_perp, row.refuted_at_2
            );
            assert_eq!(
                row.outside_perp, row.refuted_at_2,
                "target {t}: every escaping curve must refute at degree 2"
            );
            assert!(row.leading_nullity >= 1, "some syzygy must exist");
        }
    }

    /// The consequence: a curve selected as best on one target set keeps no
    /// margin on a disjoint one, and the between-curve variance of mean `D*`
    /// is what independent sampling already predicts.  This is the gate that
    /// decides lever L5.
    #[test]
    fn selected_best_curve_keeps_no_holdout_margin() {
        let n = 8u32;
        let irr = first_irreducible(n);
        let t = curve_effect_test(n, 4, 6, 8, 8, &irr);
        assert_eq!(t.curves, (1usize << n) - 1);
        // The curve explains no more than sampling noise.
        assert!(
            t.variance_ratio < 2.0,
            "between-curve variance ratio {:.3} — a real curve effect would \
             push this toward the target count",
            t.variance_ratio
        );
        // Selection margin is positive by construction; the holdout margin is
        // the honest one, and it must not survive.
        assert!(
            t.margin_select > 0.0,
            "selection must pick a better-looking curve"
        );
        assert!(
            t.margin_holdout < t.margin_select,
            "holdout margin {:.3} should shrink from the selection margin {:.3}",
            t.margin_holdout,
            t.margin_select
        );
    }

    /// The conductor is **always odd** for this curve family, so the
    /// characteristic never appears as a volcano prime and Kohel's `ℓ ≠ p`
    /// theory always applies to the primes that matter.
    ///
    /// Proof, in the recursion: `a_{k+1} = −2b_k` is even for `k ≥ 1`, so
    /// `b_{k+1} = a_k − b_k ≡ b_k (mod 2)` for `k ≥ 2`, and `b_1 = 1` is odd.
    #[test]
    fn conductor_is_always_odd() {
        for n in 1..=140u32 {
            let c = koblitz_conductor(n);
            assert!(
                !(&c % BigInt::from(2u8)).is_zero(),
                "conductor even at n = {n}: {c}"
            );
        }
    }

    /// Reach accounting is monotone in the budget and is bracketed by
    /// `{E}` alone and the whole class.
    #[test]
    fn reach_is_monotone_in_the_budget() {
        let class = koblitz_isogeny_class(131, 5_000_000);
        let mut prev = BigInt::zero();
        for b in [2u32, 100, 263, 1_000_000] {
            let r = class.reach_within_degree(&BigInt::from(b));
            assert!(r.reachable >= prev, "reach must not shrink with budget");
            assert!(r.reachable <= class.class_size);
            prev = r.reachable;
        }
    }

    /// The decisive consequence: no curve stays on the `D* = 2` floor once
    /// enough targets are demanded.  At `n = 8` the count reaches **zero**,
    /// so "a curve that is easy for every target" does not exist — which is
    /// what an attacker moving along an isogeny class would need.
    #[test]
    fn no_curve_stays_on_the_floor_for_every_target() {
        let n = 8u32;
        let irr = first_irreducible(n);
        let mut counts = Vec::new();
        for t in [8u32, 16, 32] {
            let fs = uniform_floor_survivors(n, 4, 7, t, &irr);
            counts.push(fs.survivors.len());
        }
        assert!(
            counts.windows(2).all(|w| w[1] <= w[0]),
            "survivor count must not grow with the target count: {counts:?}"
        );
        assert_eq!(
            counts[2], 0,
            "some curve survived 32 targets on the floor: {counts:?}"
        );
    }

    /// The same statement at `n = 10`, where the decay is slower: one curve
    /// (`a₆ = 13`) is still on the floor at `T = 64`, and it is the curve
    /// this thread's own iteration-1 caveat was about.  It falls at
    /// `T = 128`, so the survivor is an artifact of the target count and not
    /// a curve property.
    ///
    /// Ignored by default: `uniform_floor_survivors` is `Θ(curves · T)`
    /// Gröbner refutations, so `T = 128` over 1023 curves runs for minutes
    /// rather than seconds.  Run it with
    /// `cargo test --release --lib the_last_n10_floor_survivor -- --ignored`.
    #[test]
    #[ignore = "minutes: 1023 curves × 128 targets of Macaulay refutation"]
    fn the_last_n10_floor_survivor_falls_by_128_targets() {
        let (n, l) = (10u32, 5u32);
        let irr = first_irreducible(n);
        let at64 = uniform_floor_survivors(n, l, 7, 64, &irr);
        assert_eq!(
            at64.survivors,
            vec![13],
            "the T=64 survivor set should be exactly the caveat curve a₆ = 13"
        );
        let at128 = uniform_floor_survivors(n, l, 7, 128, &irr);
        assert!(
            at128.survivors.is_empty(),
            "a curve survived 128 targets on the floor at n = 10: {:?}",
            at128.survivors
        );
    }

    /// The residual per-curve variation is decomposition yield, not a
    /// solving-degree property: a curve whose factor base decomposes more
    /// targets has fewer targets left that can refute above the floor.
    #[test]
    fn above_floor_count_is_explained_by_decomposition_yield() {
        let n = 8u32;
        let irr = first_irreducible(n);
        let y = yield_explanation(n, 4, 7, &irr);
        println!(
            "n={} l={} targets={} curves={}\n               decomposable per curve: min {} max {} mean {:.1}\n               above-floor per curve:  min {} max {} mean {:.1}\n               rho_s(decomposable, above-floor count) = {:+.4}\n               rho_s(decomposable, above-floor rate)  = {:+.4}\n               curves with zero above-floor targets: {} {:?}",
            y.n, y.l, y.targets, y.curves,
            y.decomposable_min, y.decomposable_max, y.decomposable_mean,
            y.above_floor_min, y.above_floor_max, y.above_floor_mean,
            y.rho_count, y.rho_rate,
            y.zero_above_floor.len(),
            &y.zero_above_floor[..y.zero_above_floor.len().min(10)]
        );
        assert_eq!(y.curves, (1usize << n) - 1, "every curve must be swept");
        assert!(y.targets > 0);
        // Case 3 is squeezed by case 2, so the correlation is negative.
        assert!(
            y.rho_count < -0.3,
            "expected a clearly negative count correlation, got {:.4}",
            y.rho_count
        );
        // Sanity: the spread is real, not a constant column.
        assert!(y.above_floor_max > y.above_floor_min);
        assert!(y.decomposable_max > y.decomposable_min);
    }

    /// Spearman on known input.
    #[test]
    fn spearman_matches_hand_values() {
        // Perfectly anti-correlated.
        assert!((spearman(&[1.0, 2.0, 3.0, 4.0], &[4.0, 3.0, 2.0, 1.0]) + 1.0).abs() < 1e-12);
        // Perfectly correlated.
        assert!((spearman(&[1.0, 2.0, 3.0], &[10.0, 20.0, 30.0]) - 1.0).abs() < 1e-12);
        // A constant column has no rank variation.
        assert_eq!(spearman(&[1.0, 1.0, 1.0], &[1.0, 2.0, 3.0]), 0.0);
    }

    /// `h(O_f)` against hand values: `h(O_263) = 262` because 263 splits,
    /// and the multiplicativity over prime powers.
    #[test]
    fn class_number_of_conductor_known_values() {
        assert_eq!(
            class_number_of_conductor(&[(BigInt::from(263u32), 1)]),
            BigInt::from(262u32)
        );
        // 3 is inert in Q(√−7): (−7/3) = (2/3) = −1, so h(O_3) = 3 + 1 = 4.
        assert_eq!(kronecker_minus7(&BigInt::from(3u32)), -1);
        assert_eq!(
            class_number_of_conductor(&[(BigInt::from(3u32), 1)]),
            BigInt::from(4u32)
        );
        // 7 ramifies: h(O_7) = 7.
        assert_eq!(kronecker_minus7(&BigInt::from(7u32)), 0);
        assert_eq!(
            class_number_of_conductor(&[(BigInt::from(7u32), 1)]),
            BigInt::from(7u32)
        );
        // Prime power: h(O_9) = 3·(3+1) = 12.
        assert_eq!(
            class_number_of_conductor(&[(BigInt::from(3u32), 2)]),
            BigInt::from(12u32)
        );
    }

    /// Cross-check the primality test against a sieve rather than against a
    /// hand-picked list, so a witness/trial-division mismatch cannot hide in
    /// the gap between the two.  Bugbot caught exactly such a gap: the bases
    /// run to 53 but trial division stopped at 37, so 41, 43, 47 and 53 were
    /// reported composite because the witness `a = n` gives `x = 0`.
    #[test]
    fn primality_agrees_with_a_sieve_below_1000() {
        const LIMIT: usize = 1000;
        let mut sieve = vec![true; LIMIT];
        sieve[0] = false;
        sieve[1] = false;
        for i in 2..LIMIT {
            if sieve[i] {
                let mut j = i * i;
                while j < LIMIT {
                    sieve[j] = false;
                    j += i;
                }
            }
        }
        for (n, &expected) in sieve.iter().enumerate() {
            assert_eq!(
                is_probable_prime(&BigInt::from(n)),
                expected,
                "primality disagrees with the sieve at {n}"
            );
        }
        // The four values the witness list used to swallow, named explicitly
        // so a regression reports them rather than only a sieve index.
        for p in [41u32, 43, 47, 53] {
            assert!(is_probable_prime(&BigInt::from(p)), "{p} must be prime");
        }
        // And a factorisation whose final cofactor is one of them now
        // completes instead of surviving the rho budget.  1763 = 41 · 43.
        let (factors, complete) = factor_bigint(&BigInt::from(1763u32), 1 << 12);
        assert!(complete, "41 · 43 must factor completely");
        assert_eq!(
            factors,
            vec![(BigInt::from(41u32), 1), (BigInt::from(43u32), 1)]
        );
    }

    fn first_irreducible(n: u32) -> IrreduciblePoly {
        crate::cryptanalysis::descent_expansion::enumerate_irreducibles(n, 1)
            .into_iter()
            .next()
            .expect("an irreducible of every small degree exists")
    }
}
