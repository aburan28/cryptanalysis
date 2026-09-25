//! # Index calculus for Koblitz (subfield) curves with Frobenius-invariant factor bases.
//!
//! Implementation of the algorithm of **Galbraith, Granger, Merz and
//! Petit**, *On index calculus algorithms for subfield curves*
//! (SAC 2020, ePrint 2020/1315).  A Koblitz curve
//!
//! ```text
//!     K_a :  y² + x y = x³ + a x² + 1,      a ∈ {0, 1}
//! ```
//!
//! is defined over `F_2` but used over `F_{2^n}`.  Because the curve
//! equation has `F_2`-coefficients, the `2`-power Frobenius
//!
//! ```text
//!     π(x, y) = (x², y²)
//! ```
//!
//! is an endomorphism of `E(F_{2^n})`, and on the large prime-order
//! subgroup `⟨P⟩` it acts as multiplication by a known scalar `λ`
//! (a root of `λ² − t λ + 2 ≡ 0 mod r`, `t = (−1)^{1−a}` the trace of
//! Frobenius over `F_2`).  Pollard rho exploits that with a `√n`
//! speed-up; the GGMP paper shows index calculus gets a **larger**
//! speed-up: `≈ n` in relation collection and `≈ n²` in the linear
//! algebra.
//!
//! ## Where the speed-up comes from
//!
//! Take a factor base `F ⊆ E(F_{2^n})` that is *Frobenius invariant*,
//! `π(F) = F`.  Then `F` splits into `π`-orbits, each of size dividing
//! `n`, and if `P' = π^k(Q)` with `Q` an orbit representative then
//!
//! ```text
//!     log_P P' = λ^k · log_P Q      (mod r).
//! ```
//!
//! Negation adds `log_P(-Q) = -log_P(Q)`, so the `|F|` unknowns of a
//! classical index calculus collapse to one per signed Frobenius orbit,
//! generically `≈ |F| / (2n)`. Consequences:
//!
//! - **Relation collection:** we need one relation per signed orbit
//!   unknown instead of one per factor-base point.
//! - **Linear algebra:** Frobenius shrinks the relation matrix by a factor `n` in
//!   *both* dimensions, so a quadratic (sparse-linear-algebra) solve
//!   costs `n²` less; negation removes the redundant opposite columns.
//! - **Symmetry breaking:** a decomposition `R = P_1 + … + P_m` is
//!   found `m!` times if the summands are searched independently.
//!   Distributing the summands over the shifted factor bases
//!   `F_i = π^{i−1}(F)` — which for an invariant base all equal `F` —
//!   and requiring the tuple to be ordered removes that `m!`.  Each
//!   summand `P_i = π^{k_i}(Q_{j_i})` contributes `λ^{k_i}` to column
//!   `j_i` of the relation, which is exactly the "rewrite the relation
//!   so that all `P'_i ∈ F_1 = F`" step of the paper.
//!
//! ## Frobenius-invariant factor bases from linearised polynomials
//!
//! The paper's construction (their §4, and the "Examples of Frobenius
//! invariant factor bases" slide of the SAC talk):
//!
//! 1. Factor `x^n − 1 = (x − 1) f_1 f_2 ⋯ f_s` in `F_2[x]`.
//!    For odd `n` the factors are distinct. When `n` is an odd prime,
//!    the nontrivial factors all have degree `ℓ := ord_n(2)` (GGMP,
//!    Lemma 4.1); for composite odd `n`, their degrees can differ.
//! 2. For `f_j = Σ_k f_{j,k} x^k` form the **linearised** polynomial
//!    `F_j(X) = Σ_k f_{j,k} X^{2^k}`.  Its root set in `F_{2^n}` is an
//!    `F_2`-subspace `V_j` of dimension `deg f_j` (the `F_2[x] ≅ {linearised
//!    polynomials under composition}` isomorphism sends `x^n − 1` to
//!    `X^{2^n} − X`, so `F_j` divides `X^{2^n} − X`), and `V_j` is
//!    closed under squaring because the `f_{j,k}` lie in `F_2`.
//! 3. `F := { P ∈ E(F_{2^n}) \ {O} : F_j(x(P)) = 0 }` is Frobenius
//!    invariant. Its rational-point count depends on which coordinates
//!    lift to the curve; only the coordinate count `|V_j| = 2^(deg f_j)`
//!    is exact from the kernel dimension.
//!
//! `V_j` is computed here as the kernel of the `F_2`-linear map
//! `v ↦ F_j(v)` on `F_{2^n}`, which is both simpler and self-checking
//! (the kernel dimension must come out equal to `deg f_j`).
//!
//! The implementation also supports smaller invariant nonlinear sets:
//! a seed subspace can be closed under Frobenius, then optionally under
//! translation by rational 2-torsion.  These domains are represented by
//! their exact finite coordinate set.  SAT constrains every summand with
//! a prefix trie for that set; it does not replace the nonlinear domain
//! with its full linear span.
//!
//! ## Honest scope
//!
//! - **Three decomposition oracles.**  "Is `R` a sum of `m` factor-base
//!   points?" can be answered by
//!   [`DecompositionStrategy::Groebner`] — Semaev's `S₃` Weil-restricted
//!   to a low-degree Boolean system over the invariant subspace and
//!   solved with matrix-F4 (see
//!   [`crate::cryptanalysis::koblitz_groebner`]) — by
//!   [`DecompositionStrategy::Sat`], which encodes the descended
//!   equations with native XOR rows and exact factor-base membership,
//!   or by
//!   [`DecompositionStrategy::Enumerate`], a table-driven search over
//!   ordered tuples costing `|F|^{m−1}` group operations.  They are
//!   cross-checked against each other on the toy cases in the tests.
//!   At the sizes this module can reach the search is still 10–100×
//!   *faster* in wall-clock terms: `|F|` is a few dozen points, so
//!   `|F|^{m−1}` is nothing, while the Macaulay matrix already has
//!   thousands of columns.  A completed Gröbner or SAT refutation proves
//!   that the encoded decomposition does not exist; an exhausted budget
//!   remains inconclusive.  The exact factor-base coverage results do not
//!   establish a SAT speedup or a solving-complexity bound.
//! - **Toy / research rungs only.**  Curve construction via
//!   [`KoblitzCurve::new`] is guarded by [`MAX_N`] (currently 63) so the
//!   factor base can be materialised and the group order factored.  This
//!   does not threaten sect163k1 or any other deployed Koblitz curve —
//!   as the paper's own conclusion puts it, index calculus remains
//!   *worse* than rho for curves used in practice.
//!
//! ## References
//!
//! - S. D. Galbraith, R. Granger, S.-P. Merz, C. Petit, *On index
//!   calculus algorithms for subfield curves*, SAC 2020,
//!   ePrint 2020/1315.
//! - J.-M. Couveignes, R. Lercier, *Elliptic periods for finite
//!   fields*, Finite Fields Appl. 15 (2009) — the other source of
//!   Frobenius-invariant factor bases mentioned in the talk.
//! - I. Semaev, *Summation polynomials and the discrete logarithm
//!   problem on elliptic curves*, ePrint 2004/031.
//! - R. Gallant, R. Lambert, S. Vanstone, *Improving the parallelized
//!   Pollard lambda search on anomalous binary curves*, Math. Comp. 69
//!   (2000) — the `√n` rho speed-up we compare against.

use std::collections::{HashMap, HashSet};
use std::sync::atomic::{AtomicU32, AtomicU64, Ordering};

use num_bigint::BigUint;
use num_traits::{One, Zero};
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use rayon::prelude::*;
use serde::{Deserialize, Serialize};

use crate::binary_ecc::curve::{point_add, point_neg, scalar_mul};
use crate::binary_ecc::{BinaryCurve, BinaryPoint, F2mElement, F2mPoly, IrreduciblePoly};
use crate::cryptanalysis::binary_semaev::solve_artin_schreier;
use crate::cryptanalysis::crossbred::{
    extract_crossbred, solve_crossbred, CrossbredParams, SearchOptions as CrossbredSearchOptions,
    SearchStats as CrossbredSearchStats,
};
use crate::cryptanalysis::ec_index_calculus::{gaussian_eliminate_mod_n, sqrt_mod_p};
use crate::cryptanalysis::f4_batch::{solve_lockstep, BatchDecider, LockstepReport};
use crate::cryptanalysis::koblitz_fast::{BatchScratch, FastCurve, FastPoint, FrobeniusCanon};
use crate::cryptanalysis::koblitz_groebner::{
    matrix_f4_f2, solve_boolean_system_filtered, split_rule_default, FieldStructure, SolveOptions,
    SolveStats, SolverEngine,
};
use crate::cryptanalysis::koblitz_relation_solver::{IncrementalRelationSolver, RowStatus};
use crate::cryptanalysis::koblitz_sparse_la::{
    self, SparseRow, SparseSolveOptions, SparseSolveOutcome, SparseSolveReport,
};
use crate::cryptanalysis::pq_groebner_f2::F2BoolPoly;
use crate::cryptanalysis::sat::SolveResult;
use crate::cryptanalysis::semaev_sat::{encode_boolean_system_with, XorEncoding};
use crate::utils::mod_inverse;

/// Largest extension degree this module will build a curve for.  The
/// factor base and the point-counting/factoring helpers are all
/// materialised, so this is a deliberate guard rail, not a limit of
/// the mathematics.  Field elements are packed in a `u64`, so the
/// absolute limit is `n < 64`.  Past `n ≈ 24` the generator is found
/// by deterministic sampling rather than a full abscissa sweep; point
/// counting still uses the closed Koblitz recurrence (no `2^n` scan).
/// Curve construction costs trial division to `√#E ≈ 2^{n/2}` and a
/// sparse irreducible search; both are still cheap at the
/// boundary-ledger rungs through `n = 53`.  What actually bounds a run
/// is the `2^dim` factor base and, for the meet-in-the-middle oracle,
/// its `|F|²` pair table.
pub const MAX_N: u32 = 63;

// ── F_2[x] helpers on `u64` bitmasks ───────────────────────────────
//
// Polynomials of degree < 64 over F_2, bit `i` = coefficient of `x^i`.
// Used for the irreducible-polynomial search and for factoring
// `x^n − 1`; the field arithmetic itself lives in `binary_ecc::f2m`.

/// Degree of a bitmask polynomial, or `None` for the zero polynomial.
fn poly_deg(f: u64) -> Option<u32> {
    if f == 0 {
        None
    } else {
        Some(63 - f.leading_zeros())
    }
}

/// Remainder of `a` modulo `f` in `F_2[x]`.
fn poly_rem(mut a: u64, f: u64) -> u64 {
    let df = match poly_deg(f) {
        Some(d) => d,
        None => return a,
    };
    while let Some(da) = poly_deg(a) {
        if da < df {
            break;
        }
        a ^= f << (da - df);
    }
    a
}

/// `a · b mod f` in `F_2[x]`.
fn poly_mulmod(a: u64, b: u64, f: u64) -> u64 {
    let mut acc = 0u64;
    let mut a = poly_rem(a, f);
    let mut b = b;
    while b != 0 {
        if b & 1 == 1 {
            acc ^= a;
        }
        b >>= 1;
        a <<= 1;
        a = poly_rem(a, f);
    }
    poly_rem(acc, f)
}

/// `gcd(a, b)` in `F_2[x]`, monic by construction (F_2 has one unit).
fn poly_gcd(mut a: u64, mut b: u64) -> u64 {
    while b != 0 {
        let r = poly_rem(a, b);
        a = b;
        b = r;
    }
    a
}

/// `x^(2^k) mod f` by repeated squaring of the residue.
fn poly_x_pow_2k(k: u32, f: u64) -> u64 {
    let mut acc = poly_rem(0b10, f); // x
    for _ in 0..k {
        acc = poly_mulmod(acc, acc, f);
    }
    acc
}

/// Distinct prime divisors of `n` (trial division; `n` is tiny here).
fn prime_divisors(mut n: u32) -> Vec<u32> {
    let mut out = Vec::new();
    let mut d = 2u32;
    while d * d <= n {
        if n.is_multiple_of(d) {
            out.push(d);
            while n.is_multiple_of(d) {
                n /= d;
            }
        }
        d += 1;
    }
    if n > 1 {
        out.push(n);
    }
    out
}

/// **Rabin's irreducibility test** for a degree-`d` polynomial of
/// `F_2[x]`: `f` is irreducible iff `x^(2^d) ≡ x (mod f)` and
/// `gcd(x^(2^(d/p)) − x, f) = 1` for every prime `p | d`.
pub fn is_irreducible_f2(f: u64) -> bool {
    let d = match poly_deg(f) {
        Some(d) if d >= 1 => d,
        _ => return false,
    };
    if f & 1 == 0 && d > 1 {
        return false; // divisible by x
    }
    if poly_x_pow_2k(d, f) != poly_rem(0b10, f) {
        return false;
    }
    for p in prime_divisors(d) {
        let t = poly_x_pow_2k(d / p, f) ^ 0b10;
        if poly_deg(poly_gcd(poly_rem(t, f), f)) != Some(0) {
            return false;
        }
    }
    true
}

/// Smallest (as an integer bitmask) irreducible polynomial of degree
/// `n` over `F_2`, which for every `n` in range is a trinomial or
/// pentanomial.  Returned as an [`IrreduciblePoly`].
pub fn find_irreducible(n: u32) -> Option<IrreduciblePoly> {
    if n == 0 || n >= 64 {
        return None;
    }
    let hi = 1u64 << n;
    for low in 0..hi {
        let f = hi | low;
        if is_irreducible_f2(f) {
            let low_terms = (0..n).filter(|i| (low >> i) & 1 == 1).collect();
            return Some(IrreduciblePoly {
                degree: n,
                low_terms,
            });
        }
    }
    None
}

/// **Sparse irreducible search**: the smallest-mask irreducible
/// polynomial of degree `n` over `F_2` among those with at most four
/// terms below `z^n` — i.e. trinomials and pentanomials.
///
/// [`find_irreducible`] scans all `2^n` masks, which is fine to `n ≈ 24`
/// and hopeless beyond.  For every degree in range the smallest
/// irreducible polynomial *is* sparse, so this returns the same answer
/// far faster (a test pins the agreement for `n ≤ 20`), and it is what
/// the measurement harness uses to reach `n = 63`.
pub fn find_irreducible_sparse(n: u32) -> Option<IrreduciblePoly> {
    if n == 0 || n >= 64 {
        return None;
    }
    if n == 1 {
        return Some(IrreduciblePoly {
            degree: 1,
            low_terms: vec![0],
        });
    }
    // An irreducible polynomial of degree ≥ 1 has a non-zero constant
    // term, so bit 0 is always set; try 0, 1, 2 further bits below n.
    let mut candidates: Vec<u64> = Vec::new();
    candidates.push(1);
    for i in 1..n {
        candidates.push(1 | (1 << i));
        for j in (i + 1)..n {
            candidates.push(1 | (1 << i) | (1 << j));
            for k in (j + 1)..n {
                candidates.push(1 | (1 << i) | (1 << j) | (1 << k));
            }
        }
    }
    candidates.sort_unstable();
    let hi = 1u64 << n;
    for low in candidates {
        if is_irreducible_f2(hi | low) {
            return Some(IrreduciblePoly {
                degree: n,
                low_terms: (0..n).filter(|i| (low >> i) & 1 == 1).collect(),
            });
        }
    }
    None
}

/// The `index`-th Frobenius-invariant subspace of `F_{2^n}`, as an
/// `F_2`-basis — the factor base's `x`-coordinate support, without
/// building the curve, counting its points, or materialising `F`.
///
/// Point counting and factoring cap [`KoblitzCurve::new`] at
/// [`MAX_N`]; the *system* the decomposition oracles solve needs only
/// the field and this subspace, so it can be measured much further out.
/// Returns `None` when `x^n − 1` has no `index`-th non-trivial factor.
pub fn invariant_subspace_basis(
    n: u32,
    index: usize,
) -> Option<(IrreduciblePoly, Vec<F2mElement>)> {
    let irr = find_irreducible_sparse(n)?;
    let f_j = *factor_x_n_minus_1(n).get(index)?;
    let ell = 63 - f_j.leading_zeros();
    let exps: Vec<u32> = (0..=ell).filter(|k| (f_j >> k) & 1 == 1).collect();
    let basis = linearised_kernel_basis(&exps, n, &irr);
    if basis.len() != ell as usize {
        return None;
    }
    Some((irr, basis))
}

/// Multiplicative order of `2` modulo odd `n` — the degree `ℓ` of every
/// non-trivial irreducible factor of `x^n − 1` over `F_2`.
pub fn order_of_2_mod_n(n: u32) -> Option<u32> {
    if n < 3 || n.is_multiple_of(2) {
        return None;
    }
    let mut acc = 1u64;
    for k in 1..=n {
        acc = (acc * 2) % n as u64;
        if acc == 1 {
            return Some(k);
        }
    }
    None
}

/// **The degree-`ord_n(2)` irreducible factors of `x^n − 1`** over
/// `F_2`, found by scanning the `2^ℓ` monic polynomials of that degree.
///
/// **Not a complete factorisation.**  `x^n − 1` has one irreducible
/// factor per 2-cyclotomic coset mod `n`, of degree equal to that
/// coset's size, and `ord_n(2)` is only the *largest* of those sizes.
/// At `n = 9` the cosets are `{0}`, `{3, 6}` and the six-element rest,
/// so `x^9 − 1` also has a degree-2 factor that this function does not
/// return.  Use [`all_factors_of_x_n_minus_1`] for the full list; this
/// one is kept as-is because
/// [`build_frobenius_factor_base`] indexes into it.
pub fn factor_x_n_minus_1(n: u32) -> Vec<u64> {
    let ell = match order_of_2_mod_n(n) {
        Some(l) if l < 40 => l,
        _ => return Vec::new(),
    };
    let mut out = Vec::new();
    let hi = 1u64 << ell;
    for low in 0..hi {
        let f = hi | low;
        if !is_irreducible_f2(f) {
            continue;
        }
        // f | x^n − 1  ⟺  x^n ≡ 1 (mod f).
        let mut xn = poly_rem(0b10, f);
        let mut acc = 1u64;
        let mut e = n;
        while e > 0 {
            if e & 1 == 1 {
                acc = poly_mulmod(acc, xn, f);
            }
            xn = poly_mulmod(xn, xn, f);
            e >>= 1;
        }
        if acc == 1 {
            out.push(f);
        }
    }
    out
}

// ── Koblitz curve over F_{2^n} ─────────────────────────────────────

/// A Koblitz curve `K_a : y² + xy = x³ + a x² + 1` over `F_2`, taken
/// over the extension `F_{2^n}`, together with everything the index
/// calculus needs: the prime-order subgroup, a generator, and the
/// scalar `λ` by which Frobenius acts on that subgroup.
#[derive(Clone, Debug)]
pub struct KoblitzCurve {
    /// Curve parameter `a ∈ {0, 1}`.
    pub a: u8,
    /// Extension degree `n`.
    pub n: u32,
    /// Underlying binary curve (arithmetic + generator + order).
    pub curve: BinaryCurve,
    /// Trace of Frobenius over `F_2`: `t = (−1)^{1−a}`, i.e. `−1` for
    /// `a = 0` and `+1` for `a = 1`.
    pub trace: i64,
    /// `#E(F_{2^n})`.
    pub group_order: BigUint,
    /// Prime order `r` of the subgroup the DLP lives in.
    pub subgroup_order: BigUint,
    /// `h = #E / r`.
    pub cofactor: BigUint,
    /// The eigenvalue of `π` on `⟨generator⟩`: `π(Q) = [λ]Q`.
    pub lambda: BigUint,
    /// Degree `k` of the subfield the curve is defined over, `q = 2^k`;
    /// `1` for a Koblitz curve.  `π` is the `q`-power Frobenius and
    /// `trace`, `lambda` refer to it.
    pub k: u32,
    /// `q = 2^k`.
    pub q: u64,
    /// Coordinates of `a` and `b` in `subfield_basis`; for `k = 1`
    /// these are `a` and `1`.
    pub a_index: u64,
    pub b_index: u64,
    /// An `F_2`-basis of `F_q ⊂ F_{2^n}` (the kernel of `X^q + X`).
    pub subfield_basis: Vec<F2mElement>,
}

/// Largest subfield degree [`KoblitzCurve::subfield`] accepts: the
/// curve's `F_q`-points are counted by enumeration, and `a` must fit
/// the byte the documents carry.
pub const MAX_SUBFIELD_DEGREE: u32 = 8;

/// `#E(K_a / F_{2^n}) = 2^n + 1 − s_n`, where `s_0 = 2`, `s_1 = t` and
/// `s_k = t·s_{k−1} − 2·s_{k−2}` (Koblitz's recurrence for the traces
/// of the Frobenius powers).
pub fn koblitz_point_count(a: u8, n: u32) -> BigUint {
    let t: i128 = if a == 0 { -1 } else { 1 };
    let (mut s_prev, mut s_cur) = (2i128, t);
    for _ in 1..n {
        let next = t * s_cur - 2 * s_prev;
        s_prev = s_cur;
        s_cur = next;
    }
    let count = (1i128 << n) + 1 - s_cur;
    BigUint::from(count as u128)
}

/// `#E(F_{q^e}) = q^e + 1 − s_e` from the trace `t` of the `q`-power
/// Frobenius (`s_0 = 2`, `s_1 = t`, `s_i = t·s_{i−1} − q·s_{i−2}`).
pub fn subfield_group_order(trace: i128, q: u64, e: u32) -> BigUint {
    let q = q as i128;
    let (mut s_prev, mut s_cur) = (2i128, trace);
    for _ in 1..e {
        let next = trace * s_cur - q * s_prev;
        s_prev = s_cur;
        s_cur = next;
    }
    let count = q.pow(e) + 1 - s_cur;
    BigUint::from(count as u128)
}

/// `#E(F_q)` for a curve whose coefficients lie in the subfield spanned
/// by `basis`, by enumerating the `q` abscissae and keeping the points
/// whose ordinate is also in `F_q`.
fn subfield_point_count(curve: &BinaryCurve, basis: &[F2mElement], k: u32) -> u64 {
    let n = curve.m;
    let irr = &curve.irreducible;
    let mut count = 1u64; // O
    for x in span_f2(basis, n) {
        for p in points_with_x(curve, &x) {
            if let BinaryPoint::Affine { y, .. } = &p {
                if y.square_k_times(k, irr) == *y {
                    count += 1;
                }
            }
        }
    }
    count
}

/// Trial-division factorisation into `(prime, exponent)` pairs.  Only
/// ever called on `#E` for toy `n`.
fn factorise(mut v: BigUint) -> Vec<(BigUint, u32)> {
    let mut out: Vec<(BigUint, u32)> = Vec::new();
    let mut d = BigUint::from(2u32);
    while &d * &d <= v {
        let mut e = 0;
        while (&v % &d).is_zero() {
            v /= &d;
            e += 1;
        }
        if e > 0 {
            out.push((d.clone(), e));
        }
        d += BigUint::one();
    }
    if v > BigUint::one() {
        out.push((v, 1));
    }
    out
}

impl KoblitzCurve {
    /// Build `K_a` over `F_{2^n}`: pick a defining irreducible
    /// polynomial, count points, split off the largest prime-order
    /// subgroup, find a generator of it, and determine `λ`.
    ///
    /// Returns `None` if `n` is out of range, if no irreducible
    /// polynomial is found, or if the largest prime factor of `#E` is
    /// too small for the subgroup to be usable (`r ≤ h`, or `r² | #E`).
    pub fn new(a: u8, n: u32) -> Option<Self> {
        if a > 1 {
            return None;
        }
        Self::subfield(1, n, u64::from(a), 1)
    }

    /// **A curve defined over `F_q`, `q = 2^k`, taken over `F_{2^n}`**
    /// with `n = k·e`, `e` odd: `y² + xy = x³ + a x² + b` with
    /// `a, b ∈ F_q` given by their coordinates `a_index` (`< q`) and
    /// `b_index` (`1 ≤ b_index < q`) in the `F_2`-basis of the subfield.
    /// `k = 1` is the Koblitz family (`b_index = 1`); `k ≤`
    /// [`MAX_SUBFIELD_DEGREE`].  The `q`-power Frobenius `π` is an
    /// endomorphism with `π² − tπ + q = 0`, `t` the trace over `F_q`
    /// (found by counting `E(F_q)`), and `#E(F_{2^n})` follows from the
    /// same recurrence as for `K_a`.  Everything else — the prime-order
    /// subgroup, its generator and `λ` — is as for [`Self::new`].
    pub fn subfield(k: u32, n: u32, a_index: u64, b_index: u64) -> Option<Self> {
        if k == 0 || k > MAX_SUBFIELD_DEGREE || !(3..=MAX_N).contains(&n) || !n.is_multiple_of(k) {
            return None;
        }
        let ext = n / k;
        if ext < 3 || ext.is_multiple_of(2) {
            return None;
        }
        let q = 1u64 << k;
        if a_index >= q || b_index == 0 || b_index >= q {
            return None;
        }
        // Identical to the exhaustive `find_irreducible` wherever both
        // are defined (a test pins that for every n ≤ 24) and far
        // cheaper past it, where the exhaustive scan would touch 2^n
        // masks: the sparse (trinomial/pentanomial) search is what
        // reaches the boundary-ledger rungs at n = 37 / n = 41.
        let irreducible = find_irreducible_sparse(n)?;
        // F_q ⊂ F_{2^n} is the kernel of X^{2^k} + X.
        let subfield_basis = linearised_kernel_basis(&[0, k], n, &irreducible);
        if subfield_basis.len() != k as usize {
            return None;
        }
        let combine = |index: u64| {
            let mut acc = F2mElement::zero(n);
            for (i, e) in subfield_basis.iter().enumerate() {
                if (index >> i) & 1 == 1 {
                    acc = acc.add(e);
                }
            }
            acc
        };
        let a_fe = combine(a_index);
        let b_fe = combine(b_index);
        let a = a_index as u8;

        // Arithmetic-only shell; generator/order are filled in below.
        let mut curve = BinaryCurve {
            m: n,
            irreducible,
            a: a_fe,
            b: b_fe,
            generator: BinaryPoint::Infinity,
            order: BigUint::zero(),
            cofactor: BigUint::one(),
        };

        let trace = q as i128 + 1 - subfield_point_count(&curve, &subfield_basis, k) as i128;
        let group_order = subfield_group_order(trace, q, ext);
        let factors = factorise(group_order.clone());
        let (r, e) = factors.last()?.clone();
        if e != 1 {
            return None;
        }
        let cofactor = &group_order / &r;
        if r <= cofactor {
            return None;
        }

        // A generator of the order-r subgroup: kill the cofactor on
        // curve points until the result is non-trivial.  Exhaustive
        // abscissa search is fine through ~24 bits; past that a full
        // `2^n` sweep is impossible, so sample deterministically from
        // a fixed LCG (reproducible across hosts).
        let mut generator = BinaryPoint::Infinity;
        let mask = if n >= 64 { u64::MAX } else { (1u64 << n) - 1 };
        let exhaustive = n <= 24;
        let budget = if exhaustive {
            1u64 << n
        } else {
            // ~1M trials is plenty: a random x hits the curve ~1/2 of
            // the time and survives the cofactor map with probability
            // ≈ 1 − 1/r ≫ 2^{-20} on admitted rungs.
            1u64 << 20
        };
        let mut state = 0x9e37_79b9_7f4a_7c15u64 ^ (n as u64) ^ ((a as u64) << 32);
        if k > 1 {
            state ^= (u64::from(k) << 40) ^ (b_index << 48);
        }
        for i in 0..budget {
            let raw = if exhaustive {
                i
            } else {
                state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
                state & mask
            };
            let x = F2mElement::from_biguint(&BigUint::from(raw), n);
            let pts = points_with_x(&curve, &x);
            let mut found = false;
            for p in pts {
                let cand = scalar_mul(&curve, &p, &cofactor);
                if cand != BinaryPoint::Infinity {
                    // Confirm order divides r (reject accidental torsion).
                    if scalar_mul(&curve, &cand, &r) == BinaryPoint::Infinity {
                        generator = cand;
                        found = true;
                        break;
                    }
                }
            }
            if found {
                break;
            }
        }
        if generator == BinaryPoint::Infinity {
            return None;
        }
        curve.generator = generator;
        curve.order = r.clone();
        curve.cofactor = cofactor.clone();

        let trace = i64::try_from(trace).ok()?;
        let lambda = frobenius_eigenvalue_q(&curve, trace, q, k, &r)?;

        Some(Self {
            a,
            n,
            curve,
            trace,
            group_order,
            subgroup_order: r,
            cofactor,
            lambda,
            k,
            q,
            a_index,
            b_index,
            subfield_basis,
        })
    }

    /// The `q`-power Frobenius `π(x, y) = (x^q, y^q)` — squaring for a
    /// Koblitz curve.
    pub fn frobenius(&self, p: &BinaryPoint) -> BinaryPoint {
        match p {
            BinaryPoint::Infinity => BinaryPoint::Infinity,
            BinaryPoint::Affine { x, y } => BinaryPoint::Affine {
                x: self.frobenius_x(x),
                y: self.frobenius_x(y),
            },
        }
    }

    /// `x ↦ x^q`, the Frobenius on abscissae.
    pub fn frobenius_x(&self, x: &F2mElement) -> F2mElement {
        x.square_k_times(self.k, &self.curve.irreducible)
    }

    /// The degree `e = n / k` of `F_{2^n}` over the subfield: the
    /// length every Frobenius orbit divides.
    pub fn extension_degree(&self) -> u32 {
        self.n / self.k
    }

    /// The subfield element with the given coordinates in
    /// [`Self::subfield_basis`].
    pub fn subfield_element(&self, index: u64) -> F2mElement {
        let mut acc = F2mElement::zero(self.n);
        for (i, e) in self.subfield_basis.iter().enumerate() {
            if (index >> i) & 1 == 1 {
                acc = acc.add(e);
            }
        }
        acc
    }

    /// Short label: `K_a / GF(2^n)`, or the subfield form
    /// `E_{a,b}/GF(2^k) over GF(2^n)`.
    pub fn label(&self) -> String {
        if self.k == 1 {
            format!("K_{} / GF(2^{})", self.a, self.n)
        } else {
            format!(
                "E_{{{},{}}}/GF(2^{}) over GF(2^{})",
                self.a_index, self.b_index, self.k, self.n
            )
        }
    }

    /// `[k]·P` on this curve.
    pub fn mul(&self, p: &BinaryPoint, k: &BigUint) -> BinaryPoint {
        if let Some(fast) = FastCurve::new(&self.curve) {
            let lifted = fast.lift(p);
            // Preserve the general path for coordinates whose representation
            // cannot be round-tripped through this curve's single-word field.
            if fast.lower(lifted) == *p {
                return fast.lower(fast.mul(lifted, k));
            }
        }
        scalar_mul(&self.curve, p, k)
    }

    /// `P + Q` on this curve.
    pub fn add(&self, p: &BinaryPoint, q: &BinaryPoint) -> BinaryPoint {
        point_add(&self.curve, p, q)
    }

    /// The generator of the prime-order subgroup.
    pub fn generator(&self) -> &BinaryPoint {
        &self.curve.generator
    }
}

/// Both points of `E` with the given `x`-coordinate, or an empty vector
/// when `x` is not the abscissa of any `F_{2^n}`-point.
///
/// For `x ≠ 0` the substitution `y = x·u` turns `y² + xy = x³ + ax² + b`
/// into the Artin–Schreier equation `u² + u = x + a + b/x²`, solvable
/// iff the right-hand side has absolute trace `0`.  For `x = 0` the
/// equation degenerates to `y² = b`, whose unique solution is `y = √b`.
pub fn points_with_x(curve: &BinaryCurve, x: &F2mElement) -> Vec<BinaryPoint> {
    let irr = &curve.irreducible;
    let m = curve.m;
    if x.is_zero() {
        // y² = b ⇒ y = b^(2^(m−1)) (squaring is a bijection).
        let y = curve.b.square_k_times(m - 1, irr);
        return vec![BinaryPoint::Affine { x: x.clone(), y }];
    }
    let x_inv = match x.flt_inverse(irr) {
        Some(v) => v,
        None => return Vec::new(),
    };
    let rhs = x.add(&curve.a).add(&curve.b.mul(&x_inv.square(irr), irr));
    let u = match solve_artin_schreier(&rhs, m, irr) {
        Some(u) => u,
        None => return Vec::new(),
    };
    let y = x.mul(&u, irr);
    let p = BinaryPoint::Affine { x: x.clone(), y };
    let np = point_neg(&p);
    if p == np {
        vec![p]
    } else {
        vec![p, np]
    }
}

/// Single-word version of `points_with_x` for an odd-degree field.
/// Reuse the field reduction tables across all coordinates of a factor base.
/// The same half-trace root is returned first, preserving sampling and indexing.
fn points_with_x_fast(curve: &FastCurve, x: &F2mElement) -> Vec<BinaryPoint> {
    debug_assert!(curve.n % 2 == 1);
    let field = &curve.field;
    let coordinate = field.from_element(x);
    if coordinate == 0 {
        return vec![curve.lower(FastPoint::affine(0, field.sqr_k(curve.b, curve.n - 1)))];
    }
    let inverse = field.inv(coordinate);
    let rhs = coordinate ^ curve.a ^ field.mul(curve.b, field.sqr(inverse));
    let mut root = rhs;
    let mut power = rhs;
    for _ in 0..(curve.n - 1) / 2 {
        power = field.sqr(field.sqr(power));
        root ^= power;
    }
    // H(rhs)^2 + H(rhs) = rhs + Tr(rhs) for odd degree. Testing the
    // equation is the same trace-zero admission check as the general solver.
    if field.sqr(root) ^ root != rhs {
        return Vec::new();
    }
    let point = FastPoint::affine(coordinate, field.mul(coordinate, root));
    vec![curve.lower(point), curve.lower(curve.neg(point))]
}

/// The scalar `λ` with `π(Q) = [λ]Q` for all `Q ∈ ⟨G⟩`.
///
/// `π` satisfies its characteristic equation `π² − tπ + 2 = 0`, so on
/// the order-`r` subgroup `λ` is one of the two roots of
/// `λ² − tλ + 2 ≡ 0 (mod r)`; which one is settled by testing
/// `π(G) = [λ]G`.
pub fn frobenius_eigenvalue(curve: &BinaryCurve, trace: i64, r: &BigUint) -> Option<BigUint> {
    frobenius_eigenvalue_q(curve, trace, 2, 1, r)
}

/// [`frobenius_eigenvalue`] for the `q`-power Frobenius, `q = 2^k`:
/// `λ` is a root of `λ² − tλ + q ≡ 0 (mod r)` with `π_q(G) = [λ]G`.
pub fn frobenius_eigenvalue_q(
    curve: &BinaryCurve,
    trace: i64,
    q: u64,
    k: u32,
    r: &BigUint,
) -> Option<BigUint> {
    let t = if trace >= 0 {
        BigUint::from(trace as u64) % r
    } else {
        r - (BigUint::from((-trace) as u64) % r)
    };
    // disc = t² − 4q
    let t_sq = (&t * &t) % r;
    let disc = (&t_sq + r - (BigUint::from(4 * q) % r)) % r;
    let s = sqrt_mod_p(&disc, r)?;
    let inv2 = mod_inverse(&BigUint::from(2u32), r)?;

    let g = &curve.generator;
    let pi_g = match g {
        BinaryPoint::Infinity => return None,
        BinaryPoint::Affine { x, y } => BinaryPoint::Affine {
            x: x.square_k_times(k, &curve.irreducible),
            y: y.square_k_times(k, &curve.irreducible),
        },
    };
    for sign in [true, false] {
        let num = if sign {
            (&t + &s) % r
        } else {
            (&t + r - &s) % r
        };
        let lambda = (num * &inv2) % r;
        if scalar_mul(curve, g, &lambda) == pi_g {
            return Some(lambda);
        }
    }
    None
}

// ── Frobenius-invariant factor base ────────────────────────────────

/// Algebraic description of the allowed abscissae.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum FactorBaseDomain {
    LinearSubspace,
    /// A subset of the signed Frobenius orbits of a linear subspace
    /// base, selected by the factor-base search.  The coordinates still
    /// live in the subspace (so the algebraic system keeps its `ℓ`
    /// variables per summand); SAT additionally constrains each summand
    /// to the retained abscissae with the exact domain trie.
    SubspaceSubset {
        retained_orbits: usize,
    },
    /// Union of Frobenius translates of an ell-dimensional seed space.
    /// The union need not be a linear subspace.
    FrobeniusUnion {
        seed_dimension: usize,
    },
    /// Explicit abscissa representatives, closed under Frobenius.
    ExplicitFrobeniusOrbits {
        representatives: usize,
    },
    /// Reciprocal closure from translation by rational 2-torsion.
    TwoTorsionSaturation,
}

/// A Frobenius-invariant factor base and its orbit structure.
#[derive(Clone, Debug)]
pub struct FrobeniusFactorBase {
    pub domain: FactorBaseDomain,
    /// Dimension of the linear ambient coordinates used for descent.
    /// For a nonlinear union this is n, not log2 of the base size.
    pub ell: u32,
    /// The chosen `f_j`, as an `F_2[x]` bitmask; zero for a nonlinear union.
    pub f_j: u64,
    /// Exponents `k` with `f_{j,k} = 1`, i.e. the linearised polynomial
    /// is `F_j(X) = Σ X^{2^k}` over these `k`.
    pub linearised_exponents: Vec<u32>,
    /// Allowed abscissae, closed under squaring. For LinearSubspace
    /// these are the 2^ell roots of F_j; for FrobeniusUnion they are a union.
    pub subspace: Vec<F2mElement>,
    /// Basis of the ambient linear space used to encode coordinates.
    /// A union uses the full field basis and requires domain constraints.
    pub subspace_basis: Vec<F2mElement>,
    /// The factor base itself: every point whose abscissa is a root.
    pub points: Vec<BinaryPoint>,
    /// `π`-orbits, as lists of indices into `points`.  Orbit `o` is
    /// `[i_0, i_1, …]` with `points[i_{k}] = π^k(points[i_0])`.
    pub orbits: Vec<Vec<usize>>,
    /// For each point index: `(orbit, k)` with `point = π^k(representative)`.
    pub orbit_of: Vec<(usize, u32)>,
    /// Orbits under Frobenius and negation. These are the relation
    /// columns because `log(-P) = -log(P)` adds no independent unknown.
    pub signed_orbits: Vec<Vec<usize>>,
    /// For each point: `(signed orbit, k, negated)` with
    /// `point = (-1)^negated π^k(representative)`.
    pub signed_orbit_of: Vec<(usize, u32, bool)>,
}

impl FrobeniusFactorBase {
    /// Number of unknowns the linear algebra actually carries — one per
    /// signed `π`-orbit, versus `points.len()` for a non-invariant base.
    pub fn unknowns(&self) -> usize {
        self.signed_orbits.len()
    }

    /// Whether the abscissae are encoded in the full polynomial basis
    /// of `F_{2^n}` (nonlinear unions and saturations) rather than in
    /// the `ℓ`-dimensional basis of an invariant subspace.
    pub fn uses_ambient_basis(&self) -> bool {
        !matches!(
            self.domain,
            FactorBaseDomain::LinearSubspace | FactorBaseDomain::SubspaceSubset { .. }
        )
    }

    /// Canonical abscissa of each signed orbit: the smallest `x` (as an
    /// integer) among its points.  Stable across rebuilds, so a search
    /// can name orbits by it.
    pub fn signed_orbit_abscissa_representatives(&self) -> Vec<BigUint> {
        self.signed_orbits
            .iter()
            .map(|orbit| {
                orbit
                    .iter()
                    .filter_map(|&i| match &self.points[i] {
                        BinaryPoint::Affine { x, .. } => Some(x.to_biguint()),
                        BinaryPoint::Infinity => None,
                    })
                    .min()
                    .expect("signed orbits contain affine points")
            })
            .collect()
    }

    /// The class `[r]P` of each factor-base point in the `h`-torsion,
    /// where `h = #E / r` is the cofactor.
    ///
    /// A target `R ∈ ⟨G⟩` has `[r]R = O`, so a decomposition
    /// `R = Σ P_i` forces `Σ [r]P_i = O`.  When the factor base does not
    /// meet `⟨G⟩` — which is the common case, since `x = 0` lies in
    /// every invariant subspace and carries the 2-torsion point — these
    /// classes are non-trivial and constrain which `m` can work at all.
    pub fn cofactor_classes(&self, kc: &KoblitzCurve) -> Vec<BinaryPoint> {
        self.points
            .iter()
            .map(|p| kc.mul(p, &kc.subgroup_order))
            .collect()
    }

    /// Distinct h-torsion classes `[r]P`, derived with one scalar
    /// multiplication per signed Frobenius orbit.
    ///
    /// Multiplication by `r` commutes with Frobenius and negation, so the
    /// remaining classes in an orbit are recovered with cheap public group
    /// operations. Multiplicity is irrelevant to exact-summand reachability
    /// because decomposition permits repeated factor-base points.
    pub fn distinct_cofactor_classes(&self, kc: &KoblitzCurve) -> Vec<BinaryPoint> {
        let mut classes = HashMap::new();
        for orbit in &self.signed_orbits {
            let Some(&representative) = orbit.first() else {
                continue;
            };
            let mut current = kc.mul(&self.points[representative], &kc.subgroup_order);
            for _ in 0..kc.n {
                for candidate in [current.clone(), point_neg(&current)] {
                    classes.entry(point_key(&candidate)).or_insert(candidate);
                }
                current = kc.frobenius(&current);
            }
        }
        classes.into_values().collect()
    }

    /// **Can an `m`-point decomposition of a target in `⟨G⟩` exist?**
    ///
    /// Not a statement about size — about cosets.  Every summand
    /// contributes its `h`-torsion class, and the classes must cancel.
    /// If every factor-base point lies in the non-trivial cofactor-2
    /// class, odd `m` is excluded and even `m` passes this class test.
    /// Passing is necessary only: it does not certify a decomposition of
    /// a prescribed target. Repeated summands are allowed.
    /// The check uses one public `[r]` multiplication per signed-orbit
    /// representative, followed by Frobenius/negation expansion and class
    /// reachability. It can reject decompositions that cannot exist.
    pub fn m_can_decompose(&self, kc: &KoblitzCurve, m: usize) -> bool {
        if self.points.is_empty() || m == 0 {
            return m == 0;
        }
        let classes = self.distinct_cofactor_classes(kc);
        if m == 1 {
            return classes.contains(&BinaryPoint::Infinity);
        }
        // `Σ c_i = O` with `m` summands ⇔ `−c_m` lies in the (m − 1)-fold
        // sumset, and the classes are closed under negation, so it is
        // enough to build `m − 1` layers and intersect with the classes.
        //
        // Every layer is closed under Frobenius and negation (the
        // classes are, and both commute with addition), so a layer is
        // generated by adding the classes to one representative per
        // signed Frobenius orbit of the previous layer and closing the
        // result under squaring and negation — cheap field squarings in
        // place of the `|layer| · |classes|` point additions the naive
        // walk pays.  Each layer holds at most `h` points.
        let identity = pack_point(&BinaryPoint::Infinity);
        let class_keys: HashSet<u64> = classes.iter().map(pack_point).collect();
        let mut layer: Vec<BinaryPoint> = vec![BinaryPoint::Infinity];
        let mut layer_keys: HashSet<u64> = HashSet::from([identity]);
        for _ in 1..m {
            let reps = signed_frobenius_orbit_representatives(kc, &layer);
            let mut next_keys: HashSet<u64> = HashSet::new();
            let mut next: Vec<BinaryPoint> = Vec::new();
            for q in &reps {
                for c in &classes {
                    let seed = kc.add(q, c);
                    if next_keys.contains(&pack_point(&seed)) {
                        continue;
                    }
                    // Close the orbit of `seed` under π and negation.
                    let mut current = seed;
                    for _ in 0..kc.n {
                        for candidate in [current.clone(), point_neg(&current)] {
                            if next_keys.insert(pack_point(&candidate)) {
                                next.push(candidate);
                            }
                        }
                        current = kc.frobenius(&current);
                    }
                }
            }
            layer = next;
            layer_keys = next_keys;
        }
        layer_keys.iter().any(|k| class_keys.contains(k))
    }

    /// The naive `m`-fold sumset walk over the cofactor classes —
    /// `|layer| · |classes|` point additions per layer.  Kept as the
    /// reference the orbit-generated walk is tested against.
    #[cfg(test)]
    fn m_can_decompose_reference(&self, kc: &KoblitzCurve, m: usize) -> bool {
        if self.points.is_empty() || m == 0 {
            return m == 0;
        }
        let classes = self.distinct_cofactor_classes(kc);
        let identity = pack_point(&BinaryPoint::Infinity);
        let mut layer: Vec<BinaryPoint> = vec![BinaryPoint::Infinity];
        for j in 1..=m {
            let mut seen: HashSet<u64> = HashSet::new();
            let mut next: Vec<BinaryPoint> = Vec::new();
            for acc in &layer {
                for c in &classes {
                    let sum = kc.add(acc, c);
                    if seen.insert(pack_point(&sum)) {
                        next.push(sum);
                    }
                }
            }
            if j == m {
                return seen.contains(&identity);
            }
            layer = next;
        }
        false
    }

    /// The summand counts in `2 ..= max_m` that [`Self::m_can_decompose`]
    /// admits — the ones worth trying.
    pub fn admissible_summand_counts(&self, kc: &KoblitzCurve, max_m: usize) -> Vec<usize> {
        (2..=max_m)
            .filter(|&m| self.m_can_decompose(kc, m))
            .collect()
    }

    /// Boolean unknowns an `m`-point decomposition over this base costs:
    /// `m·dim` subspace coordinates plus `(m − 2)·n` for the chained
    /// intermediates.  Tuning `dim` up to reach `m = 2` zeroes the
    /// second term, which is the whole point of the divisor bases.
    pub fn n_vars_for_summands(&self, n: u32, m: usize) -> usize {
        m * self.ell as usize + m.saturating_sub(2) * n as usize
    }

    /// Lookup table from point identity to factor-base index, as both
    /// decomposition oracles need.
    pub fn index_map(&self) -> HashMap<(BigUint, BigUint), usize> {
        self.points
            .iter()
            .enumerate()
            .map(|(i, p)| (point_key(p), i))
            .collect()
    }
}

/// One representative per orbit of a point set under Frobenius and
/// negation (the set is assumed closed under both).
fn signed_frobenius_orbit_representatives(
    kc: &KoblitzCurve,
    points: &[BinaryPoint],
) -> Vec<BinaryPoint> {
    let mut seen: HashSet<u64> = HashSet::with_capacity(points.len());
    let mut reps = Vec::new();
    for p in points {
        if seen.contains(&pack_point(p)) {
            continue;
        }
        reps.push(p.clone());
        let mut current = p.clone();
        for _ in 0..kc.n {
            seen.insert(pack_point(&current));
            seen.insert(pack_point(&point_neg(&current)));
            current = kc.frobenius(&current);
        }
    }
    reps
}

/// An `F_2`-**basis** of the kernel of the linearised polynomial
/// `F(X) = Σ_{k ∈ exps} X^{2^k}` acting `F_2`-linearly on `F_{2^n}`.
///
/// The map is written as an `n × n` matrix over `F_2` in the polynomial
/// basis `1, z, …, z^{n−1}`; the kernel basis is read off by row
/// reducing `[image | preimage]`.
pub fn linearised_kernel_basis(exps: &[u32], n: u32, irr: &IrreduciblePoly) -> Vec<F2mElement> {
    kernel_basis_of(n, |basis| {
        let mut img = F2mElement::zero(n);
        for &k in exps {
            img = img.add(&basis.square_k_times(k, irr));
        }
        img
    })
}

/// An `F_2`-basis of the kernel of the `q`-linearised polynomial
/// `L(X) = Σ_i c_i X^{q^i}`, `q = 2^k`, acting on `F_{2^n}`.  With
/// `c_i ∈ F_q` the kernel is `π_q`-invariant; for `c_i ∈ F_2` and
/// `k = 1` this is [`linearised_kernel_basis`].
pub fn q_linearised_kernel_basis(
    coeffs: &[F2mElement],
    k: u32,
    n: u32,
    irr: &IrreduciblePoly,
) -> Vec<F2mElement> {
    kernel_basis_of(n, |basis| {
        let mut img = F2mElement::zero(n);
        for (i, c) in coeffs.iter().enumerate() {
            if c.is_zero() {
                continue;
            }
            let power = basis.square_k_times(i as u32 * k, irr);
            img = img.add(&c.mul(&power, irr));
        }
        img
    })
}

/// Kernel basis of an `F_2`-linear map on `F_{2^n}` given by its action
/// on the polynomial basis.
fn kernel_basis_of(n: u32, image: impl Fn(&F2mElement) -> F2mElement) -> Vec<F2mElement> {
    // Column i = F(z^i), packed into the low n bits of a u64.
    let mut rows: Vec<(u64, u64)> = Vec::with_capacity(n as usize);
    for i in 0..n {
        let basis = F2mElement::from_bit_positions(&[i], n);
        let img = image(&basis);
        let img_bits = img.raw_bits().first().copied().unwrap_or(0);
        rows.push((img_bits, 1u64 << i));
    }

    // Gaussian elimination on the image halves; whatever reduces to
    // zero contributes its preimage to the kernel basis.
    let mut pivots: Vec<(u64, u64)> = Vec::new();
    let mut kernel_basis: Vec<u64> = Vec::new();
    for (mut img, mut pre) in rows {
        for &(pimg, ppre) in &pivots {
            let lead = 1u64 << (63 - pimg.leading_zeros());
            if img & lead != 0 {
                img ^= pimg;
                pre ^= ppre;
            }
        }
        if img == 0 {
            kernel_basis.push(pre);
        } else {
            pivots.push((img, pre));
            pivots.sort_by_key(|x| std::cmp::Reverse(x.0));
        }
    }

    kernel_basis
        .into_iter()
        .map(|v| F2mElement::from_biguint(&BigUint::from(v), n))
        .collect()
}

/// The kernel itself: every `F_2`-combination of
/// [`linearised_kernel_basis`], `2^dim` elements.
pub fn linearised_kernel(exps: &[u32], n: u32, irr: &IrreduciblePoly) -> Vec<F2mElement> {
    span_f2(&linearised_kernel_basis(exps, n, irr), n)
}

/// All `2^{|basis|}` `F_2`-combinations of `basis`.
pub fn span_f2(basis: &[F2mElement], n: u32) -> Vec<F2mElement> {
    let mut out = Vec::with_capacity(1usize << basis.len());
    for mask in 0..(1u64 << basis.len()) {
        let mut acc = F2mElement::zero(n);
        for (b, base) in basis.iter().enumerate() {
            if (mask >> b) & 1 == 1 {
                acc = acc.add(base);
            }
        }
        out.push(acc);
    }
    out
}

/// **The 2-cyclotomic cosets mod `n`**: orbits of `s ↦ 2s` on `Z/n`.
///
/// These classify every Frobenius-stable `F_2`-subspace of `F_{2^n}`.
/// A subspace closed under squaring is an `F_2[x]/(x^n − 1)`-submodule,
/// i.e. a binary cyclic code of length `n`, i.e. a divisor of
/// `x^n − 1`; and the irreducible factors of `x^n − 1` correspond one
/// for one with these cosets, a coset of size `d` giving a factor of
/// degree `d`.
///
/// So the *available dimensions* of an invariant factor base are
/// exactly the subset sums of the coset sizes — see
/// [`available_subspace_dimensions`].
pub fn cyclotomic_cosets(n: u32) -> Vec<Vec<u32>> {
    let mut seen = vec![false; n as usize];
    let mut out = Vec::new();
    for s in 0..n {
        if seen[s as usize] {
            continue;
        }
        let mut coset = Vec::new();
        let mut x = s;
        while !seen[x as usize] {
            seen[x as usize] = true;
            coset.push(x);
            x = (x * 2) % n;
        }
        coset.sort_unstable();
        out.push(coset);
    }
    out
}

/// **Every dimension a Frobenius-invariant factor base can have** over
/// `F_{2^n}`, in increasing order.
///
/// The subset sums of the cyclotomic coset sizes.  This is a complete
/// classification, not a heuristic: a stable subspace *is* a divisor of
/// `x^n − 1`, so no other dimension is achievable.
///
/// It is also the answer to "which `n` are worth attacking this way".
/// When `2` is primitive mod `n` — `n = 131` and `n = 163`, the sizes
/// that matter — there are only two cosets, `{0}` and everything else,
/// so the only dimensions are `0, 1, n − 1, n`: nothing usable.  When
/// `n` has many small cosets the sizes are dense, and the factor base
/// can be tuned to whatever `|F| = 2^dim` the sizing condition wants.
pub fn available_subspace_dimensions(n: u32) -> Vec<u32> {
    let mut reach = std::collections::BTreeSet::from([0u32]);
    for c in cyclotomic_cosets(n) {
        let d = c.len() as u32;
        for r in reach.clone() {
            reach.insert(r + d);
        }
    }
    reach.into_iter().collect()
}

/// Product of two `F_2[x]` polynomials given as bitmasks, without
/// reduction.  `None` if the product would not fit a `u64`.
fn poly_mul_full(a: u64, b: u64) -> Option<u64> {
    let (da, db) = (poly_deg(a), poly_deg(b));
    if let (Some(da), Some(db)) = (da, db) {
        if da + db >= 64 {
            return None;
        }
    }
    let mut acc = 0u64;
    let mut b = b;
    let mut shift = 0;
    while b != 0 {
        if b & 1 == 1 {
            acc ^= a << shift;
        }
        b >>= 1;
        shift += 1;
    }
    Some(acc)
}

/// **Every irreducible factor of `x^n − 1`** over `F_2`, including
/// `x + 1`, as bitmasks.
///
/// [`factor_x_n_minus_1`] returns only the non-trivial factors; a
/// divisor may use `x + 1` too, so the divisor-based constructions take
/// their indices into this list.
pub fn all_factors_of_x_n_minus_1(n: u32) -> Vec<u64> {
    let mut out = vec![0b11u64]; // x + 1
                                 // The degrees that occur are exactly the cyclotomic coset sizes;
                                 // the size-1 coset is {0}, already covered by x + 1 above.
    let mut degrees: Vec<u32> = cyclotomic_cosets(n)
        .iter()
        .map(|c| c.len() as u32)
        .filter(|d| *d > 1)
        .collect();
    degrees.sort_unstable();
    degrees.dedup();
    for d in degrees {
        if d > 24 {
            break; // the scan below is 2^d; beyond this it is not worth it
        }
        out.extend(irreducible_factors_of_degree(n, d));
    }
    out
}

/// Every irreducible factor of `x^n − 1` of degree exactly `d`.
///
/// Scans the `2^d` monic polynomials of that degree.  Used by
/// [`all_factors_of_x_n_minus_1`]; [`factor_x_n_minus_1`] is the
/// `d = ord_n(2)` case of the same search.
fn irreducible_factors_of_degree(n: u32, d: u32) -> Vec<u64> {
    let mut out = Vec::new();
    let hi = 1u64 << d;
    for low in 0..hi {
        let f = hi | low;
        if !is_irreducible_f2(f) {
            continue;
        }
        // f | x^n − 1  ⟺  x^n ≡ 1 (mod f).
        let mut xn = poly_rem(0b10, f);
        let mut acc = 1u64;
        let mut e = n;
        while e > 0 {
            if e & 1 == 1 {
                acc = poly_mulmod(acc, xn, f);
            }
            xn = poly_mulmod(xn, xn, f);
            e >>= 1;
        }
        if acc == 1 {
            out.push(f);
        }
    }
    out
}

/// An `F_2`-basis of the Frobenius-invariant subspace belonging to the
/// divisor `Π factors[i]`, `i ∈ indices` — dimension = total degree.
///
/// The single-factor case ([`invariant_subspace_basis`]) is stuck at
/// `dim = ord_n(2)`, which is the only dimension one irreducible factor
/// can give.  Products give every dimension in
/// [`available_subspace_dimensions`], so the factor base can be sized
/// to the instance instead of the instance to the factor base.
pub fn subspace_basis_for_divisor(
    n: u32,
    indices: &[usize],
    irr: &IrreduciblePoly,
) -> Option<Vec<F2mElement>> {
    let factors = all_factors_of_x_n_minus_1(n);
    let mut f = 1u64;
    for &i in indices {
        f = poly_mul_full(f, *factors.get(i)?)?;
    }
    let deg = poly_deg(f)?;
    if deg == 0 || deg >= n {
        return None;
    }
    let exps: Vec<u32> = (0..=deg).filter(|k| (f >> k) & 1 == 1).collect();
    let basis = linearised_kernel_basis(&exps, n, irr);
    if basis.len() != deg as usize {
        return None;
    }
    Some(basis)
}

// ── Invariant subspaces over a subfield ────────────────────────────

/// An `F_2[x]` bitmask as a polynomial with `F_{2^n}` coefficients.
fn bitmask_poly(mask: u64, n: u32) -> F2mPoly {
    let coeffs = (0..64)
        .map(|i| {
            if (mask >> i) & 1 == 1 {
                F2mElement::one(n)
            } else {
                F2mElement::zero(n)
            }
        })
        .collect();
    F2mPoly::from_coeffs(coeffs, n)
}

/// The bitmask of a polynomial whose coefficients are all `0` or `1`.
fn poly_bitmask(p: &F2mPoly) -> Option<u64> {
    let deg = p.degree()?;
    if deg >= 64 {
        return None;
    }
    let mut mask = 0u64;
    for i in 0..=deg {
        let c = p.coeff(i);
        if c.is_zero() {
            continue;
        }
        if c != F2mElement::one(p.m) {
            return None;
        }
        mask |= 1 << i;
    }
    Some(mask)
}

/// Canonical order of factor polynomials: by degree, then by the
/// coefficients from the leading one down.
fn poly_sort_key(p: &F2mPoly) -> (usize, Vec<BigUint>) {
    let deg = p.degree().unwrap_or(0);
    (
        deg,
        (0..=deg).rev().map(|i| p.coeff(i).to_biguint()).collect(),
    )
}

/// **Every monic irreducible factor of `x^e − 1` over `F_q`**,
/// `e = n / k`, with coefficients as elements of `F_q ⊂ F_{2^n}`, in a
/// canonical order.  These classify the `π_q`-invariant `F_q`-subspaces
/// of `F_{2^n}` exactly as the `F_2` factors classify the
/// Frobenius-stable subspaces of a Koblitz field
/// ([`all_factors_of_x_n_minus_1`], which this returns for `k = 1` in
/// the same order, so recipe indices are unchanged).
///
/// For `k > 1` the factorisation is Cantor–Zassenhaus over `F_q`
/// carried out inside `F_{2^n}`: distinct-degree splitting by
/// `gcd(x^{q^d} − x, ·)`, then equal-degree splitting with the
/// `F_2`-trace map `T(r) = Σ_{i < kd} r^{2^i}` of random `F_q[x]`
/// elements.
pub fn invariant_factors(kc: &KoblitzCurve) -> Vec<F2mPoly> {
    let n = kc.n;
    if kc.k == 1 {
        return all_factors_of_x_n_minus_1(n)
            .into_iter()
            .map(|mask| bitmask_poly(mask, n))
            .collect();
    }
    let irr = &kc.curve.irreducible;
    let ext = kc.extension_degree() as usize;
    let mut coeffs = vec![F2mElement::zero(n); ext + 1];
    coeffs[0] = F2mElement::one(n);
    coeffs[ext] = F2mElement::one(n);
    let mut remaining = F2mPoly::from_coeffs(coeffs, n);
    let mut rng =
        StdRng::seed_from_u64(0x5355_4246_4945_4c44 ^ u64::from(n) ^ (u64::from(kc.k) << 32));
    let mut factors: Vec<F2mPoly> = Vec::new();
    let x = F2mPoly::x(n);
    let mut h = x.clone();
    let mut d = 1usize;
    while let Some(deg) = remaining.degree() {
        if deg == 0 {
            break;
        }
        if 2 * d > deg {
            factors.push(remaining.monic(irr));
            break;
        }
        for _ in 0..kc.k {
            h = h.square_mod(&remaining, irr);
        }
        let g = remaining.gcd(&h.add(&x), irr);
        if g.degree().is_some_and(|gd| gd > 0) {
            equal_degree_split(kc, &g, d, &mut rng, &mut factors);
            remaining = remaining.divrem(&g, irr).0;
            if remaining.degree().is_some_and(|rd| rd > 0) {
                h = h.rem(&remaining, irr);
            }
        }
        d += 1;
    }
    factors.sort_by_key(poly_sort_key);
    factors
}

/// Split a product `g` of distinct irreducibles of degree `d` over
/// `F_q` into its factors (Cantor–Zassenhaus, characteristic 2).
fn equal_degree_split(
    kc: &KoblitzCurve,
    g: &F2mPoly,
    d: usize,
    rng: &mut StdRng,
    out: &mut Vec<F2mPoly>,
) {
    let irr = &kc.curve.irreducible;
    let n = kc.n;
    let Some(deg) = g.degree() else { return };
    if deg == d {
        out.push(g.monic(irr));
        return;
    }
    loop {
        let coeffs: Vec<F2mElement> = (0..deg)
            .map(|_| kc.subfield_element(rng.gen_range(0..kc.q)))
            .collect();
        let r = F2mPoly::from_coeffs(coeffs, n);
        if r.degree().is_none() {
            continue;
        }
        let mut t = r.rem(g, irr);
        let mut acc = t.clone();
        for _ in 1..(kc.k as usize * d) {
            t = t.square_mod(g, irr);
            acc = acc.add(&t);
        }
        let f = g.gcd(&acc, irr);
        if let Some(fd) = f.degree() {
            if fd > 0 && fd < deg {
                let other = g.divrem(&f, irr).0.monic(irr);
                equal_degree_split(kc, &f, d, rng, out);
                equal_degree_split(kc, &other, d, rng, out);
                return;
            }
        }
    }
}

/// Indices into [`invariant_factors`] of the factors of largest degree
/// — the legacy single-factor family ([`build_frobenius_factor_base`]).
/// For `k = 1` this is the order of [`factor_x_n_minus_1`].
pub fn top_factor_indices(kc: &KoblitzCurve) -> Vec<usize> {
    let factors = invariant_factors(kc);
    let top = factors
        .iter()
        .filter_map(F2mPoly::degree)
        .max()
        .unwrap_or(0);
    factors
        .iter()
        .enumerate()
        .filter(|(_, f)| f.degree() == Some(top) && top > 0)
        .map(|(i, _)| i)
        .collect()
}

/// An `F_2`-basis of the `π_q`-invariant subspace of the divisor
/// `Π factors[i]`, `i ∈ indices`, of `x^e − 1` over `F_q`, together
/// with the divisor itself: `F_2`-dimension `k · deg`.  `None` for an
/// empty or improper divisor.  For `k = 1` this is
/// [`subspace_basis_for_divisor`].
pub fn subspace_basis_for_factors(
    kc: &KoblitzCurve,
    indices: &[usize],
) -> Option<(Vec<F2mElement>, F2mPoly)> {
    let irr = &kc.curve.irreducible;
    let factors = invariant_factors(kc);
    let mut f = F2mPoly::one(kc.n);
    for &i in indices {
        f = f.mul(factors.get(i)?, irr);
    }
    let deg = f.degree()?;
    if deg == 0 || deg >= kc.extension_degree() as usize {
        return None;
    }
    let basis = q_linearised_kernel_basis(&f.coeffs, kc.k, kc.n, irr);
    if basis.len() != deg * kc.k as usize {
        return None;
    }
    Some((basis, f))
}

/// **Build a Frobenius-invariant factor base from a divisor** of
/// `x^e − 1` over the subfield (`e = n` for a Koblitz curve), rather
/// than from a single irreducible factor.
///
/// `indices` select factors from [`invariant_factors`]; the subspace
/// has `F_2`-dimension `k` times their total degree, so `|F| ≈ 2^dim`
/// is tunable.  That matters because the summand count `m` a
/// decomposition needs falls as `|F|` grows — `m ≈ n/dim` — and `m ≥ 3`
/// is what forces the chained system and its `(m − 2)·n` extra
/// unknowns.  A large enough invariant subspace buys `m = 2` and skips
/// the chaining entirely.
pub fn build_frobenius_factor_base_from_divisor(
    kc: &KoblitzCurve,
    indices: &[usize],
) -> Option<FrobeniusFactorBase> {
    let (subspace_basis, f) = subspace_basis_for_factors(kc, indices)?;
    let ell = subspace_basis.len() as u32;
    let (f_j, exps) = if kc.k == 1 {
        let mask = poly_bitmask(&f)?;
        (mask, (0..=ell).filter(|k| (mask >> k) & 1 == 1).collect())
    } else {
        (0, Vec::new())
    };
    finish_factor_base(kc, ell, f_j, exps, subspace_basis)
}

/// **Build a Frobenius-invariant factor base** for `curve` from the
/// `index`-th irreducible factor of largest degree of `x^e − 1` over
/// the subfield ([`top_factor_indices`]).
///
/// `index` selects which of the `(e − 1)/ℓ` factors to use; different
/// factors give different (and, as the paper notes, sometimes needed —
/// a single invariant base may not yield `n` independent relations)
/// factor bases of the same size.
pub fn build_frobenius_factor_base(kc: &KoblitzCurve, index: usize) -> Option<FrobeniusFactorBase> {
    let idx = *top_factor_indices(kc).get(index)?;
    build_frobenius_factor_base_from_divisor(kc, &[idx])
}

/// Shared tail of the factor-base constructors: span the subspace,
/// collect the points over it, and walk the `π`-orbits.
fn finish_factor_base(
    kc: &KoblitzCurve,
    ell: u32,
    f_j: u64,
    exps: Vec<u32>,
    subspace_basis: Vec<F2mElement>,
) -> Option<FrobeniusFactorBase> {
    let subspace = span_f2(&subspace_basis, kc.n);
    if subspace.len() != (1usize << ell) {
        return None;
    }

    finish_factor_base_domain(
        kc,
        ell,
        f_j,
        exps,
        subspace_basis,
        subspace,
        FactorBaseDomain::LinearSubspace,
    )
}

/// Materialise the union of all Frobenius translates of a seed space.
/// This permits small invariant *sets* even when no small invariant
/// linear subspace exists. Construction is charged: at most n*2^seed_dim
/// abscissae before deduplication; SAT uses an explicit domain trie.
/// This is a toy construction, not a claim of scalable relation solving.
pub fn build_frobenius_union_factor_base(
    kc: &KoblitzCurve,
    seed_basis: &[F2mElement],
) -> Option<FrobeniusFactorBase> {
    if seed_basis.is_empty() || seed_basis.len() > 12 {
        return None;
    }
    let seed = span_f2(seed_basis, kc.n);
    let unique: std::collections::HashSet<_> = seed.iter().map(|x| x.to_biguint()).collect();
    if unique.len() != (1usize << seed_basis.len()) {
        return None;
    }
    let mut xs = std::collections::BTreeMap::new();
    for mut x in seed {
        for _ in 0..kc.extension_degree() {
            xs.entry(x.to_biguint()).or_insert_with(|| x.clone());
            x = kc.frobenius_x(&x);
        }
    }
    let ambient: Vec<_> = (0..kc.n)
        .map(|i| F2mElement::from_bit_positions(&[i], kc.n))
        .collect();
    finish_factor_base_domain(
        kc,
        kc.n,
        0,
        Vec::new(),
        ambient,
        xs.into_values().collect(),
        FactorBaseDomain::FrobeniusUnion {
            seed_dimension: seed_basis.len(),
        },
    )
}

/// Build a factor base from explicit abscissa-orbit representatives.
///
/// Each supplied coordinate is closed under the `2`-power Frobenius;
/// rational points above the resulting coordinates are materialised and
/// constrained exactly by the SAT domain trie. This is the constructor
/// used for factor bases selected by a finite orbit search, where the
/// union need not be the Frobenius closure of a small linear seed space.
pub fn build_explicit_frobenius_orbit_factor_base(
    kc: &KoblitzCurve,
    representatives: &[F2mElement],
) -> Option<FrobeniusFactorBase> {
    if representatives.is_empty() {
        return None;
    }
    let mut xs = std::collections::BTreeMap::new();
    for representative in representatives {
        let mut x = F2mElement::from_biguint(&representative.to_biguint(), kc.n);
        for _ in 0..kc.extension_degree() {
            xs.entry(x.to_biguint()).or_insert_with(|| x.clone());
            x = kc.frobenius_x(&x);
        }
    }
    let ambient = (0..kc.n)
        .map(|i| F2mElement::from_bit_positions(&[i], kc.n))
        .collect();
    finish_factor_base_domain(
        kc,
        kc.n,
        0,
        Vec::new(),
        ambient,
        xs.into_values().collect(),
        FactorBaseDomain::ExplicitFrobeniusOrbits {
            representatives: representatives.len(),
        },
    )
}

/// **Build a factor base from the prime-order subgroup**: Frobenius
/// orbits of abscissae drawn pseudo-randomly from `seed`, keeping only
/// those whose points satisfy `[r]P = O`.
///
/// Sampling stops once the base holds at least `points` points, so the
/// result is reproducible from `(curve, seed, points)` alone and a
/// recipe naming those three is a complete description of the base.
///
/// Why the subgroup: a relation and a descent both ask for a target of
/// `⟨G⟩` to be a sum of `m` base points.  Points outside `⟨G⟩` can only
/// sum into it when their cofactor components happen to cancel, so a
/// base drawn from the whole curve wastes most of its sums on the wrong
/// coset.  Restricting to the subgroup removes that loss, and the test
/// `[r]P = O` needs no logarithm.
///
/// `None` when the field is too wide to sample abscissae as `u64`, or
/// when sampling cannot reach `points` (a degenerate curve).
pub fn build_subgroup_orbit_factor_base(
    kc: &KoblitzCurve,
    seed: u64,
    points: usize,
) -> Result<FrobeniusFactorBase, String> {
    if kc.n >= 64 {
        return Err("subgroup orbit sampling needs n < 64".into());
    }
    if points == 0 {
        return Err("a factor base needs at least one point".into());
    }
    let curve = FastCurve::new(&kc.curve).ok_or("field too wide for single-word arithmetic")?;
    let cofactor = &kc.cofactor;
    let mut rng = StdRng::seed_from_u64(seed);
    let mut representatives: Vec<F2mElement> = Vec::new();
    let mut seen: HashSet<u64> = HashSet::new();
    let mut base: Option<FrobeniusFactorBase> = None;
    // Each round adds a batch of orbits and rebuilds, so the loop stops at
    // the first base that reaches `points` rather than overshooting by a
    // whole batch's worth of Frobenius closure.
    let batch = 8usize;
    let cap = 1u64 << kc.n;
    let mut drawn = 0u64;
    let budget = 1024u64 * points as u64;
    // Rebuilding at every batch boundary is quadratic — 954 rebuilds over
    // a growing representative list to reach 15264 points at degree 53,
    // which is most of what selecting a base costs.  An abscissa carries
    // at most two points, so `2·|abscissae|` bounds what a representative
    // set can yield; while that bound is below the target a build could
    // only have come back short and the loop would have gone round again,
    // so skipping it changes nothing.  The abscissa set is maintained
    // here as the batches arrive, which costs one Frobenius orbit per new
    // representative rather than one per representative per round.
    let mut abscissae: HashSet<BigUint> = HashSet::new();
    while base.as_ref().is_none_or(|b| b.points.len() < points) {
        let mut added = 0usize;
        while added < batch {
            drawn += 1;
            if drawn > budget {
                return Err(format!(
                    "drew {drawn} abscissae without reaching {points} subgroup points on {}",
                    kc.label()
                ));
            }
            let x = F2mElement::from_biguint(&BigUint::from(rng.gen_range(1..cap)), kc.n);
            let lifts = if curve.n % 2 == 1 {
                points_with_x_fast(&curve, &x)
            } else {
                points_with_x(&kc.curve, &x)
            };
            let Some(point) = lifts.into_iter().next() else {
                continue;
            };
            // Multiply by the cofactor rather than rejecting: [h]P has
            // order dividing r for *every* P, so no sample is wasted, and
            // where the cofactor is large that is the difference between
            // one draw per base point and h of them.  Knowing P says
            // nothing about the logarithm of [h]P.
            let projected = curve.mul(curve.lift(&point), cofactor);
            if projected.infinity {
                continue;
            }
            if !seen.insert(projected.x) {
                continue;
            }
            let BinaryPoint::Affine { x, .. } = curve.lower(projected) else {
                continue;
            };
            let mut orbit = F2mElement::from_biguint(&x.to_biguint(), kc.n);
            for _ in 0..kc.extension_degree() {
                abscissae.insert(orbit.to_biguint());
                orbit = kc.frobenius_x(&orbit);
            }
            representatives.push(x);
            added += 1;
        }
        if 2 * abscissae.len() < points {
            continue;
        }
        base = build_explicit_frobenius_orbit_factor_base(kc, &representatives);
    }
    base.ok_or_else(|| "subgroup orbit sampling produced no base".into())
}

/// **Keep only the listed signed orbits** of a factor base.
///
/// The retained set is still closed under Frobenius and negation, so
/// every relation identity survives; what changes is the relation
/// column count (down to `keep.len()`) and, for the enumeration and
/// pair-table oracles, the per-target cost.  A subspace base stays in
/// its subspace coordinates ([`FactorBaseDomain::SubspaceSubset`]); a
/// nonlinear base becomes an explicit orbit union.  Returns `None` for
/// an empty or out-of-range selection.
pub fn restrict_factor_base_to_orbits(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    keep: &[usize],
) -> Option<FrobeniusFactorBase> {
    if keep.is_empty() || keep.iter().any(|&o| o >= fb.signed_orbits.len()) {
        return None;
    }
    let mut keep_sorted = keep.to_vec();
    keep_sorted.sort_unstable();
    keep_sorted.dedup();
    let mut xs = std::collections::BTreeMap::new();
    for &o in &keep_sorted {
        for &i in &fb.signed_orbits[o] {
            if let BinaryPoint::Affine { x, .. } = &fb.points[i] {
                xs.entry(x.to_biguint()).or_insert_with(|| x.clone());
            }
        }
    }
    if fb.uses_ambient_basis() {
        // One representative per retained orbit; the constructor closes
        // it under Frobenius again, which is a no-op here.
        let representatives: Vec<F2mElement> = keep_sorted
            .iter()
            .map(|&o| {
                let i = fb.signed_orbits[o][0];
                match &fb.points[i] {
                    BinaryPoint::Affine { x, .. } => x.clone(),
                    BinaryPoint::Infinity => unreachable!("factor bases hold affine points"),
                }
            })
            .collect();
        return build_explicit_frobenius_orbit_factor_base(kc, &representatives);
    }
    finish_factor_base_domain(
        kc,
        fb.ell,
        fb.f_j,
        fb.linearised_exponents.clone(),
        fb.subspace_basis.clone(),
        xs.into_values().collect(),
        FactorBaseDomain::SubspaceSubset {
            retained_orbits: keep_sorted.len(),
        },
    )
}

/// B union (B+T), omitting infinity, where T=(0,1) on K_a.
/// Since hT=O for even h, this changes the available torsion lifts
/// without adding projected points. Translation commutes with Frobenius.
/// Its x-coordinate action away from T is x -> 1/x.
pub fn saturate_factor_base_two_torsion(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
) -> Option<FrobeniusFactorBase> {
    let t = points_with_x(&kc.curve, &F2mElement::zero(kc.n))
        .into_iter()
        .next()?;
    if kc.mul(&t, &kc.cofactor) != BinaryPoint::Infinity {
        return None;
    }
    let mut xs = std::collections::BTreeMap::new();
    for p in &fb.points {
        for q in [p.clone(), kc.add(p, &t)] {
            if let BinaryPoint::Affine { x, .. } = q {
                xs.entry(x.to_biguint()).or_insert(x);
            }
        }
    }
    let ambient = (0..kc.n)
        .map(|i| F2mElement::from_bit_positions(&[i], kc.n))
        .collect();
    finish_factor_base_domain(
        kc,
        kc.n,
        0,
        Vec::new(),
        ambient,
        xs.into_values().collect(),
        FactorBaseDomain::TwoTorsionSaturation,
    )
}

fn finish_factor_base_domain(
    kc: &KoblitzCurve,
    ell: u32,
    f_j: u64,
    exps: Vec<u32>,
    subspace_basis: Vec<F2mElement>,
    subspace: Vec<F2mElement>,
    domain: FactorBaseDomain,
) -> Option<FrobeniusFactorBase> {
    let mut points: Vec<BinaryPoint> = Vec::new();
    let fast = if kc.n % 2 == 1 {
        FastCurve::new(&kc.curve)
    } else {
        None
    };
    for x in &subspace {
        let lifts = match &fast {
            Some(curve) => points_with_x_fast(curve, x),
            None => points_with_x(&kc.curve, x),
        };
        points.extend(lifts);
    }

    // Index points for the orbit walk and for relation lookups.
    let mut index_of: HashMap<(BigUint, BigUint), usize> = HashMap::new();
    for (i, p) in points.iter().enumerate() {
        index_of.insert(point_key(p), i);
    }

    let mut orbit_of: Vec<(usize, u32)> = vec![(usize::MAX, 0); points.len()];
    let mut orbits: Vec<Vec<usize>> = Vec::new();
    for start in 0..points.len() {
        if orbit_of[start].0 != usize::MAX {
            continue;
        }
        let o = orbits.len();
        let mut cycle = Vec::new();
        let mut cur = points[start].clone();
        let mut k = 0u32;
        loop {
            let idx = *index_of.get(&point_key(&cur))?;
            if orbit_of[idx].0 != usize::MAX {
                break;
            }
            orbit_of[idx] = (o, k);
            cycle.push(idx);
            cur = kc.frobenius(&cur);
            k += 1;
        }
        orbits.push(cycle);
    }

    let mut signed_orbit_of = vec![(usize::MAX, 0, false); points.len()];
    let mut signed_orbits = Vec::new();
    for start in 0..points.len() {
        if signed_orbit_of[start].0 != usize::MAX {
            continue;
        }
        let signed_orbit = signed_orbits.len();
        let mut members = Vec::new();
        let mut current = points[start].clone();
        for k in 0..kc.n {
            for (negated, point) in [(false, current.clone()), (true, point_neg(&current))] {
                let index = *index_of.get(&point_key(&point))?;
                if signed_orbit_of[index].0 == usize::MAX {
                    signed_orbit_of[index] = (signed_orbit, k, negated);
                    members.push(index);
                } else if signed_orbit_of[index].0 != signed_orbit {
                    return None;
                }
            }
            current = kc.frobenius(&current);
        }
        if current != points[start] {
            return None;
        }
        signed_orbits.push(members);
    }
    if signed_orbits.iter().map(Vec::len).sum::<usize>() != points.len() {
        return None;
    }

    Some(FrobeniusFactorBase {
        domain,
        ell,
        f_j,
        linearised_exponents: exps,
        subspace,
        subspace_basis,
        points,
        orbits,
        orbit_of,
        signed_orbits,
        signed_orbit_of,
    })
}

/// Hashable identity of a point — the key of
/// [`FrobeniusFactorBase::index_map`].
pub fn point_key(p: &BinaryPoint) -> (BigUint, BigUint) {
    match p {
        BinaryPoint::Infinity => (BigUint::zero(), BigUint::zero()),
        BinaryPoint::Affine { x, y } => {
            // Shift by one so that no affine point collides with the
            // all-zero key reserved for O.
            (x.to_biguint() + BigUint::one(), y.to_biguint())
        }
    }
}

// ── Relations ──────────────────────────────────────────────────────

/// One relation `[a]G + [b]Q = Σ_i P_i` rewritten over the orbit
/// representatives of a Frobenius-invariant factor base.
#[derive(Clone, Debug)]
pub struct KoblitzRelation {
    /// `a` in `R = [a]G + [b]Q`.
    pub coef_a: BigUint,
    /// `b` in `R = [a]G + [b]Q`.
    pub coef_b: BigUint,
    /// The decomposition, as `(signed orbit, k)` pairs. Consult
    /// [`Self::summand_negated`] for the sign of each summand.
    pub summands: Vec<(usize, u32)>,
    /// Whether each summand is `-π^k(rep)` rather than `π^k(rep)`.
    pub summand_negated: Vec<bool>,
    /// Dense row over the signed-orbit unknowns: entry `o` is
    /// `Σ_i (-1)^negated_i λ^{k_i}` over its summands, reduced mod `r`.
    pub row: Vec<BigUint>,
}

/// Search for a decomposition `R = P_1 + … + P_m` with all `P_i` in the
/// factor base, returning the summands as `(orbit, k)` pairs.
///
/// **Symmetry breaking.**  Only non-decreasing index tuples are
/// enumerated, so each decomposition is found once rather than `m!`
/// times — the enumeration analogue of the paper's trick of spreading
/// the summands over `F_1, π(F_1), …, π^{m−1}(F_1)` and rewriting
/// everything back into `F_1`.
/// **Exhaustive decomposition** (the reference oracle): search ordered
/// tuples of factor-base points for `R = P_1 + … + P_m`.
///
/// Costs `|F|^{m−1}` group operations per target whether or not a
/// decomposition exists.  [`groebner_decompose`] answers the same
/// question algebraically; the two are cross-checked in the tests.
pub fn enumerate_decompose(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    index_of: &HashMap<(BigUint, BigUint), usize>,
    target: &BinaryPoint,
    m: usize,
) -> Option<Vec<usize>> {
    decompose(kc, fb, index_of, target, m, 0)
}

fn decompose(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    index_of: &HashMap<(BigUint, BigUint), usize>,
    target: &BinaryPoint,
    m: usize,
    start: usize,
) -> Option<Vec<usize>> {
    if m == 0 {
        return if *target == BinaryPoint::Infinity {
            Some(Vec::new())
        } else {
            None
        };
    }
    if m == 1 {
        let idx = *index_of.get(&point_key(target))?;
        return if idx >= start { Some(vec![idx]) } else { None };
    }
    for i in start..fb.points.len() {
        let rest = kc.add(target, &point_neg(&fb.points[i]));
        if let Some(mut tail) = decompose(kc, fb, index_of, &rest, m - 1, i) {
            let mut out = vec![i];
            out.append(&mut tail);
            return Some(out);
        }
    }
    None
}

/// How the decomposition oracle answers "is `R` a sum of `m`
/// factor-base points?".
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DecompositionStrategy {
    /// Weil-restrict the Semaev condition `S₃ = 0` to a low-degree
    /// Boolean system over the factor-base subspace and solve it with a
    /// Gröbner basis. Subexponential cost requires additional, unproved
    /// assumptions about solving these systems. See
    /// [`crate::cryptanalysis::koblitz_groebner`].
    Groebner,
    /// Exhaustive ordered-tuple search over the materialised factor
    /// base.  Costs `|F|^{m−1}` group operations per target whether or
    /// not a decomposition exists; kept as the reference oracle the
    /// algebraic one is tested against.
    Enumerate,
    /// The same Semaev system, handed to the CDCL SAT solver instead of
    /// a Gröbner engine
    /// ([`crate::cryptanalysis::semaev_sat::encode_boolean_system_with`]).
    /// The default keeps descended parity equations as native XOR rows;
    /// the CNF path remains available as a controlled comparison.
    Sat,
    /// **Meet in the middle** over a precomputed table of all pair sums
    /// `P_i + P_j` ([`PairSumTable`]).  `m = 2` is one lookup, `m = 3`
    /// is `|F|` lookups, `m = 4` is `|F|²` lookups — against
    /// `|F|^{m−1}` group operations for [`Self::Enumerate`].  Exact and
    /// complete like enumeration; costs `|F|²` memory once per run.
    PairTable,
    /// The same Semaev system, solved by **Joux-Vitse Crossbred**
    /// ([`crate::cryptanalysis::crossbred`]): Macaulay preprocessing
    /// extracts polynomials linear in the non-enumerated variables,
    /// then `2^k` fixed assignments are swept, each leaving a linear
    /// solve.  Prices below matrix-F4 on the oracle ladder of
    /// `RESEARCH_ECC2K130_CROSSBRED.md`.  Like [`Self::Groebner`] it is
    /// a decomposition oracle only: relation collection stays `Θ(2^n)`
    /// with any oracle polynomial in the factor base.
    Crossbred,
    /// Same Semaev / Weil-restriction system as [`Self::Sat`], emitted in
    /// Trimoska ANF and solved by an external WDSat binary
    /// ([`crate::cryptanalysis::wdsat_oracle`]).  Requires
    /// [`KoblitzIcOptions::wdsat_binary`].
    Wdsat,
    /// Quadratic Semaev systems (`m = 2`) solved by ALMASTY-inspired FES
    /// ([`crate::cryptanalysis::mq_fes`]; <https://gitlab.lip6.fr/almasty/mq>):
    /// incremental Gray early-exit, Möbius all-roots, Monica past `n = 24`.
    /// Refuses cubic chained systems.
    MqFes,
}

/// Packed identity of a point for hashing and sorting, in one `u64`:
/// `0` for `O`, otherwise `2(x + 1) + s` where the sign bit `s`
/// separates `P = (x, y)` from `−P = (x, x + y)` by comparing `y` with
/// `x + y` as integers (they coincide only at `x = 0`, where `P = −P`).
/// Exact for every `n ≤ 62`.
pub fn pack_point(p: &BinaryPoint) -> u64 {
    match p {
        BinaryPoint::Infinity => 0,
        BinaryPoint::Affine { x, y } => {
            let xb = x.raw_bits().first().copied().unwrap_or(0);
            let yb = y.raw_bits().first().copied().unwrap_or(0);
            let sign = u64::from(yb > (xb ^ yb));
            ((xb + 1) << 1) | sign
        }
    }
}

/// Ask the processor to start fetching this address.
///
/// The three-summand search probes the presence filter once per base
/// point, at addresses that are random and far apart, so it spends most
/// of its time waiting on memory rather than computing.  The keys are
/// all known before any of them is needed, which is exactly the case a
/// prefetch is for: issue the loads for a block, then read them.
#[inline(always)]
fn prefetch(address: *const u64) {
    #[cfg(target_arch = "x86_64")]
    // SAFETY: a prefetch has no architectural effect beyond the cache;
    // any address is allowed, valid or not.
    unsafe {
        std::arch::x86_64::_mm_prefetch::<{ std::arch::x86_64::_MM_HINT_T0 }>(address as *const i8);
    }
    #[cfg(not(target_arch = "x86_64"))]
    let _ = address;
}

/// Hash of a packed pair sum for the presence filter, independent of the
/// bucket index (which uses the key's high bits).
#[inline]
fn pair_filter_hash(key: u64) -> u64 {
    let mut h = key.wrapping_mul(0xff51_afd7_ed55_8ccd);
    h ^= h >> 33;
    h.wrapping_mul(0xc4ce_b9fe_1a85_ec53)
}

/// **Every pair sum of a factor base**, `P_i + P_j` for `i ≤ j`, sorted
/// by packed point identity so a sum can be looked up by binary search.
///
/// This is the birthday-paradox half of a decomposition search: with
/// the table built once, "is `R` a sum of two base points" is one
/// lookup, "of three" is `|F|` lookups of `R − P_k`, and "of four" is
/// `|F|²` lookups of `R − (P_k + P_l)` walked off the table itself.
/// The factor-base search uses the same table to count *every*
/// witness of a target, which is what exact yield needs.
/// **Packed base point to its index**, open-addressed.
///
/// [`PairSumTable::recover_pair`] asks this `|F|` times for every witness
/// a search finds, so on a wide base it is one of the two things the
/// recovery scan is made of.  A `std::collections::HashMap` answers it
/// through SipHash, which is tens of nanoseconds on a `u64` key before
/// any memory is touched — a strong hash bought for keys that are
/// already the output of a packing, and paid `|F|` times over.
///
/// This uses the hash the presence filter already computes and probes
/// linearly.  A packed affine point is `2(x + 1) + s ≥ 2`, so zero is
/// free to mean *empty* and no separate occupancy word is needed.
#[derive(Clone, Debug, Default)]
struct PointIndex {
    /// `(packed point, index)`, zero key for an empty slot.
    slots: Vec<(u64, u32)>,
    mask: usize,
}

impl PointIndex {
    /// Load factor one half, rounded to a power of two.
    fn build(points: &[FastPoint]) -> Self {
        let capacity = (points.len() * 2).next_power_of_two().max(2);
        let mut index = Self {
            slots: vec![(0, 0); capacity],
            mask: capacity - 1,
        };
        for (i, p) in points.iter().enumerate() {
            let key = p.pack();
            if key == 0 {
                continue;
            }
            let mut at = (pair_filter_hash(key) as usize) & index.mask;
            while index.slots[at].0 != 0 {
                if index.slots[at].0 == key {
                    break;
                }
                at = (at + 1) & index.mask;
            }
            index.slots[at] = (key, i as u32);
        }
        index
    }

    #[inline]
    fn get(&self, key: u64) -> Option<u32> {
        if key == 0 || self.slots.is_empty() {
            return None;
        }
        let mut at = (pair_filter_hash(key) as usize) & self.mask;
        loop {
            let (k, i) = self.slots[at];
            if k == 0 {
                return None;
            }
            if k == key {
                return Some(i);
            }
            at = (at + 1) & self.mask;
        }
    }
}

#[derive(Clone, Debug)]
pub struct PairSumTable {
    /// `(packed sum, i, j)` with `i ≤ j`, sorted by the packed sum.
    /// Empty in the compact representation, which keeps `rests` instead.
    entries: Vec<(u64, u32, u32)>,
    /// The compact representation of the same set: the part of each
    /// packed sum that its bucket does not already determine, sorted
    /// within the bucket, and nothing else.
    ///
    /// A stored pair costs sixteen bytes as a `(key, i, j)` triple and
    /// four as a rest, and at a fixed memory budget the base is
    /// `|F| = √(2·budget/bytes per pair)`, so the descent's `2r/|F|²`
    /// probes scale directly with that width: a quarter of the bytes is
    /// four times the reach at the same memory.  What it gives up is the
    /// summands — a hit knows a decomposition exists but not of what —
    /// and those are recovered by one `|F|`-long scan
    /// ([`Self::recover_pair`]).  Hits are rare by construction, so that
    /// scan is paid about once per relation rather than once per probe.
    ///
    /// A rest is the key's hash narrowed to a word, so two keys in one
    /// bucket collide with probability `2⁻³²` and a bucket holds about
    /// sixteen: a lookup is wrong about one time in `2²⁸`.  Wrong in the
    /// harmless direction — never a false *negative*, so nothing is
    /// missed, and a false positive only spends a recovery scan that
    /// comes back empty.  Recovery checks the group itself
    /// (`target − P_i` is a base point or it is not), so what the table
    /// returns is right whatever the rest said.
    rests: Vec<u32>,
    /// `pack()` of each base point to its index, for recovering the
    /// summands of a compact hit.  `|F|` entries, not `|F|²`.
    index_of_point: PointIndex,
    /// Single-word arithmetic on the curve, for the table build and the
    /// `|F|` subtractions of a three-summand search.
    curve: FastCurve,
    /// The factor-base points, lifted once.
    points: Vec<FastPoint>,
    /// `−P_k` for every base point, the addends of `R − P_k`.
    negated: Vec<FastPoint>,
    /// `bucket_start[b]..bucket_start[b + 1]` is the run of entries whose
    /// packed sum has `b` as its top bits (`key >> bucket_shift`): a
    /// lookup lands in its bucket with one indexed load instead of
    /// walking a binary search across the whole table.
    bucket_start: Vec<u32>,
    bucket_shift: u32,
    /// One bit per hashed key, about four per stored sum: a lookup that
    /// finds its bit clear is certainly absent and never touches the
    /// entries.  Most lookups of a decomposition search miss, and the
    /// entries are far too large to cache, so this turns the hot path
    /// from a miss in a table of hundreds of megabytes into one in a
    /// few.  No false negatives, so the answer is unchanged.
    present: Vec<u64>,
    present_mask: u64,
    /// Whether the stored keys are folded by the signed Frobenius group
    /// `G = ⟨π, −1⟩`.
    ///
    /// The factor base is closed under `π` and under negation, so the
    /// set of pair sums is closed under both too — `π(P_i + P_j) =
    /// π(P_i) + π(P_j)` and `−(P_i + P_j) = (−P_i) + (−P_j)` are again
    /// sums of base points.  A table answering `rest ∈ S?` therefore
    /// needs one key per `G`-orbit rather than one per pair, which is
    /// `2n` times fewer, and at a fixed budget that is a base `√(2n)`
    /// times wider and a descent dividing `2r/|F|²` by `2n`.
    ///
    /// What it costs is that a lookup must canonicalise first
    /// ([`Self::canon_key`]), which is `n − 1` squarings — so the fold
    /// is taken only when the unfolded table would not fit at all, and
    /// the tiers in [`Self::build_within`] reach for it last.
    fold: bool,
    /// The basis change that makes a canonical key a rotation rather
    /// than a chain of squarings.  `None` on an unfolded table, and on a
    /// folded one only if no normal element was found — in which case
    /// the squaring chain stands, giving the same answers more slowly.
    canon: Option<FrobeniusCanon>,
    /// The signed Frobenius orbits of the base, as a flat CSR: orbit `o`
    /// is `orbit_members[orbit_start[o]..orbit_start[o + 1]]`, holding
    /// indices into `points`.  `|F|` entries in all.  Empty unless the
    /// table is folded and carries orbit tags.
    orbit_start: Vec<u32>,
    orbit_members: Vec<u32>,
    /// Whether a stored word is `(orbit << 16) | rest16` rather than a
    /// full 32-bit rest.  See [`Self::compact_rest`].
    tagged: bool,
}

impl PairSumTable {
    /// Entries a table may occupy before [`Self::build`] refuses: 4 GiB,
    /// which is a base of about 16000 points.
    pub const DEFAULT_BYTE_BUDGET: u128 = 4 << 30;

    /// Build the table with `|F|(|F|+1)/2` point additions — one field
    /// inversion per row by Montgomery's trick, rows in parallel; 16
    /// bytes per entry.  Returns `None` when the field is too wide to
    /// pack a point into a `u64`.
    pub fn build(kc: &KoblitzCurve, fb: &FrobeniusFactorBase) -> Option<Self> {
        Self::build_within(kc, fb, Self::DEFAULT_BYTE_BUDGET)
    }

    /// Bytes the entries of a table for this base would occupy.
    pub fn byte_size(points: usize) -> u128 {
        Self::pair_count(points) * std::mem::size_of::<(u64, u32, u32)>() as u128
    }

    /// Stored pairs for a base of this size.
    fn pair_count(points: usize) -> u128 {
        points as u128 * (points as u128 + 1) / 2
    }

    /// [`Self::byte_size`] for the compact representation: four bytes a
    /// pair for the rest, plus the bucket index and the presence filter.
    /// A quarter of the full table's width, which at a fixed budget is
    /// twice the base and four times the `|F|²` the descent divides by.
    pub fn compact_byte_size(points: usize, degree: u32) -> u128 {
        let pairs = Self::pair_count(points);
        let buckets = 1u128 << Self::compact_bucket_bits(pairs, degree);
        pairs * 4 + buckets * 4 + pairs / 2
    }

    /// Stored keys for a folded table: one per `(orbit representative,
    /// base point)` pair.
    ///
    /// Every `G`-orbit of ordered pairs is reached: given `(P, Q)`, let
    /// `g ∈ G` carry `P` to the representative `R` of its own signed
    /// orbit; then `(R, gQ)` lies in the same orbit of pairs and is
    /// enumerated.  That holds whatever the stabilisers are, so the
    /// enumeration is onto the orbits and the table has no false
    /// negatives — it is only redundant, by the factor two that the
    /// unordered `i ≤ j` symmetry would otherwise remove.
    fn folded_pair_count(orbits: usize, points: usize) -> u128 {
        // Row `α` walks only the points in orbits `≥ α`, which over all
        // rows is half the rectangle: each sum orbit is stored once
        // rather than once from each of its two summands.
        orbits as u128 * points as u128 / 2 + points as u128
    }

    /// Bits of a canonical key: `1 + min_k x^{2^k}` is at most `2^n`.
    fn folded_key_bits(degree: u32) -> u32 {
        degree + 1
    }

    /// [`Self::compact_bucket_bits`] for a canonical key, which is one
    /// bit narrower than a packed point rather than one wider — so the
    /// bucket index has to be clamped to it, or the shift underflows at
    /// the small degrees where run length would ask for everything.
    fn folded_bucket_bits(pairs: u128, degree: u32) -> u32 {
        Self::compact_bucket_bits(pairs, degree).min(Self::folded_key_bits(degree))
    }

    /// [`Self::compact_byte_size`] for the folded table.
    pub fn folded_byte_size(orbits: usize, points: usize, degree: u32) -> u128 {
        let pairs = Self::folded_pair_count(orbits, points);
        let buckets = 1u128 << Self::folded_bucket_bits(pairs, degree);
        pairs * 4 + buckets * 4 + pairs / 2
    }

    /// Bucket bits for the compact table: about one bucket per sixteen
    /// pairs, which keeps a bucket's run inside a cache line, capped so
    /// the index itself stays small.
    fn compact_bucket_bits(pairs: u128, degree: u32) -> u32 {
        let key_bits = degree + 2;
        let by_run = (128 - (pairs.max(1) >> 4).leading_zeros()).max(1);
        by_run.min(key_bits).min(26)
    }

    /// [`Self::build`] with an explicit ceiling on the entries.
    ///
    /// The table is quadratic in the base, so the difference between a
    /// base that fits and one that does not is a single doubling.
    /// Refusing by a stated budget turns that into a `None` the caller
    /// can report, instead of an allocation the machine cannot meet.
    pub fn build_within(
        kc: &KoblitzCurve,
        fb: &FrobeniusFactorBase,
        byte_budget: u128,
    ) -> Option<Self> {
        if fb.points.len() > u32::MAX as usize {
            return None;
        }
        if Self::byte_size(fb.points.len()) > byte_budget {
            // Too wide to store the summands; the compact table may
            // still fit, and a base that fits only compactly is exactly
            // the base worth having.
            return Self::build_compact_within(kc, fb, byte_budget);
        }
        let curve = FastCurve::new(&kc.curve)?;
        let points: Vec<FastPoint> = fb.points.iter().map(|p| curve.lift(p)).collect();
        let negated: Vec<FastPoint> = points.iter().map(|&p| curve.neg(p)).collect();
        let mut entries: Vec<(u64, u32, u32)> = (0..points.len())
            .into_par_iter()
            .flat_map_iter(|i| {
                let mut sums = Vec::with_capacity(points.len() - i);
                let mut scratch = BatchScratch::default();
                curve.add_many(points[i], &points[i..], &mut sums, &mut scratch);
                sums.into_iter()
                    .enumerate()
                    .map(move |(offset, sum)| (sum.pack(), i as u32, (i + offset) as u32))
            })
            .collect();
        entries.par_sort_unstable();
        if entries.len() > u32::MAX as usize {
            return None;
        }
        // Packed sums are `< 2^(n+2)`; about one bucket per entry, at
        // most 2^26 of them.
        let key_bits = curve.n + 2;
        let bucket_bits = (usize::BITS - entries.len().leading_zeros())
            .clamp(1, 26)
            .min(key_bits);
        let bucket_shift = key_bits - bucket_bits;
        let buckets = 1usize << bucket_bits;
        let mut bucket_start = vec![0u32; buckets + 1];
        for &(key, _, _) in &entries {
            bucket_start[(key >> bucket_shift) as usize + 1] += 1;
        }
        for b in 0..buckets {
            bucket_start[b + 1] += bucket_start[b];
        }
        // Four bits per entry, rounded up to a power of two.
        let filter_bits = (usize::BITS - (entries.len().max(1) * 4).leading_zeros()).clamp(6, 32);
        let present_mask = (1u64 << filter_bits) - 1;
        let mut present = vec![0u64; (1usize << filter_bits) / 64];
        for &(key, _, _) in &entries {
            let h = (pair_filter_hash(key) & present_mask) as usize;
            present[h >> 6] |= 1u64 << (h & 63);
        }
        Some(Self {
            entries,
            rests: Vec::new(),
            index_of_point: PointIndex::default(),
            curve,
            points,
            negated,
            bucket_start,
            bucket_shift,
            present,
            present_mask,
            fold: false,
            canon: None,
            orbit_start: Vec::new(),
            orbit_members: Vec::new(),
            tagged: false,
        })
    }

    /// The compact table: every pair sum's bucket and rest, and no
    /// summands.
    ///
    /// Built without a comparison sort — the bucket of a key is known
    /// before any key is compared, so counting the buckets and
    /// scattering into them puts every rest in place in two linear
    /// passes.  A run of rests is sorted afterwards, which is a handful
    /// of elements per bucket.
    fn build_compact_within(
        kc: &KoblitzCurve,
        fb: &FrobeniusFactorBase,
        byte_budget: u128,
    ) -> Option<Self> {
        let n_points = fb.points.len();
        if n_points > u32::MAX as usize {
            return None;
        }
        if Self::compact_byte_size(n_points, kc.n) > byte_budget {
            // Folding by the signed Frobenius group stores `2n` times
            // fewer keys, so a base too wide even for the compact table
            // may still fit — at the cost of canonicalising every
            // lookup.  It is the last tier because for a base that fits
            // without it the fold only spends squarings.
            return Self::build_folded_within(kc, fb, byte_budget);
        }
        let pairs = Self::pair_count(n_points);
        if pairs > u32::MAX as u128 {
            return None;
        }
        let curve = FastCurve::new(&kc.curve)?;
        let key_bits = curve.n + 2;
        let bucket_bits = Self::compact_bucket_bits(pairs, curve.n);
        let bucket_shift = key_bits - bucket_bits;
        let buckets = 1usize << bucket_bits;
        let points: Vec<FastPoint> = fb.points.iter().map(|p| curve.lift(p)).collect();
        let negated: Vec<FastPoint> = points.iter().map(|&p| curve.neg(p)).collect();

        // A counting sort in two passes over the pairs, both parallel.
        // The bucket of a key is known before any key is compared, so
        // nothing is sorted: counting the buckets and scattering into
        // them puts every rest in its run, and a run is short enough to
        // scan.  The pair sums are recomputed rather than held between
        // the passes — holding them would cost the eight bytes a pair
        // that this representation exists to avoid.
        let counts: Vec<AtomicU32> = (0..buckets + 1).map(|_| AtomicU32::new(0)).collect();
        let each_row = |i: usize, f: &mut dyn FnMut(u64)| {
            let mut sums = Vec::with_capacity(n_points - i);
            let mut scratch = BatchScratch::default();
            curve.add_many(points[i], &points[i..], &mut sums, &mut scratch);
            for sum in &sums {
                f(sum.pack());
            }
        };
        (0..n_points).into_par_iter().for_each(|i| {
            each_row(i, &mut |key| {
                counts[(key >> bucket_shift) as usize + 1].fetch_add(1, Ordering::Relaxed);
            });
        });
        let mut bucket_start: Vec<u32> = counts.iter().map(|c| c.load(Ordering::Relaxed)).collect();
        for b in 0..buckets {
            bucket_start[b + 1] += bucket_start[b];
        }
        let total = bucket_start[buckets] as usize;
        let cursor: Vec<AtomicU32> = bucket_start.iter().map(|&c| AtomicU32::new(c)).collect();
        let mut rests = vec![0u32; total];
        let filter_bits = (usize::BITS - (total.max(1) * 4).leading_zeros()).clamp(6, 32);
        let present_mask = (1u64 << filter_bits) - 1;
        let words = (1usize << filter_bits) / 64;
        let present_atomic: Vec<AtomicU64> = (0..words).map(|_| AtomicU64::new(0)).collect();
        // Each pair claims its slot with one atomic increment, and no
        // two pairs claim the same one, so the writes never overlap.
        // The presence filter is set in the same pass: both want only
        // the key, and a pass costs `|F|²/2` point additions.
        let slots = rests.as_mut_ptr() as usize;
        (0..n_points).into_par_iter().for_each(|i| {
            each_row(i, &mut |key| {
                let bucket = (key >> bucket_shift) as usize;
                let slot = cursor[bucket].fetch_add(1, Ordering::Relaxed) as usize;
                // SAFETY: `slot` is this pair's own index, handed out
                // once by the bucket's cursor and inside the run the
                // counting pass measured for that bucket.
                unsafe {
                    *(slots as *mut u32).add(slot) = Self::compact_rest(key);
                }
                let h = (pair_filter_hash(key) & present_mask) as usize;
                present_atomic[h >> 6].fetch_or(1u64 << (h & 63), Ordering::Relaxed);
            });
        });
        let present: Vec<u64> = present_atomic
            .iter()
            .map(|w| w.load(Ordering::Relaxed))
            .collect();
        let index_of_point = PointIndex::build(&points);
        Some(Self {
            entries: Vec::new(),
            rests,
            index_of_point,
            curve,
            points,
            negated,
            bucket_start,
            bucket_shift,
            present,
            present_mask,
            fold: false,
            canon: None,
            orbit_start: Vec::new(),
            orbit_members: Vec::new(),
            tagged: false,
        })
    }

    /// **The folded table**: one key per orbit of the signed Frobenius
    /// group, built by walking `i` over one representative of each
    /// signed orbit and `j` over the whole base.
    ///
    /// That enumerates `|F|²/2n` pairs rather than `|F|²/2`, so nothing
    /// quadratic is canonicalised that need not be, and the keys it
    /// produces cover every orbit the full enumeration would reach.
    /// Duplicate `(bucket, rest)` pairs are left in place: two keys that
    /// agree there are indistinguishable to a lookup anyway, so storing
    /// one twice costs four bytes and can never lose an answer.
    fn build_folded_within(
        kc: &KoblitzCurve,
        fb: &FrobeniusFactorBase,
        byte_budget: u128,
    ) -> Option<Self> {
        let n_points = fb.points.len();
        if n_points > u32::MAX as usize {
            return None;
        }
        // One representative per signed Frobenius orbit.
        // `(orbit index, representative point)`, keeping the orbit's own
        // index rather than a position among the non-empty ones: the
        // stored tag names an orbit of `signed_orbits`, and the two
        // would drift apart if any orbit were empty.
        let reps: Vec<(u32, usize)> = fb
            .signed_orbits
            .iter()
            .enumerate()
            .filter_map(|(o, orbit)| orbit.first().map(|&i| (o as u32, i)))
            .collect();
        if reps.is_empty() {
            return None;
        }
        if Self::folded_byte_size(reps.len(), n_points, kc.n) > byte_budget {
            return None;
        }
        let pairs = Self::folded_pair_count(reps.len(), n_points);
        if pairs > u32::MAX as u128 {
            return None;
        }
        let curve = FastCurve::new(&kc.curve)?;
        // The normal basis, once, for the whole table: the build
        // canonicalises every stored pair and every lookup canonicalises
        // its target, and the two must name orbits the same way.
        let canon = FrobeniusCanon::new(&curve.field, curve.n);
        // A canonical key is one bit wider than an abscissa and two
        // narrower than a packed point.
        let bucket_bits = Self::folded_bucket_bits(pairs, curve.n);
        // Buckets come off the top of the key's hash, not the key: see
        // [`Self::bucket_of`] for why a canonical key cannot be bucketed
        // on its own high bits.
        let bucket_shift = 64 - bucket_bits;
        let buckets = 1usize << bucket_bits;
        let points: Vec<FastPoint> = fb.points.iter().map(|p| curve.lift(p)).collect();
        let negated: Vec<FastPoint> = points.iter().map(|&p| curve.neg(p)).collect();

        // The orbit of one summand survives the fold, because `G` maps
        // orbits to themselves — so tagging each stored word with it
        // turns recovery from a walk of the base into a walk of `2n`
        // points.  It fits in the rest's high half and costs no memory;
        // only a base with more orbits than a tag can name goes without.
        let tagged = fb.signed_orbits.len() <= Self::MAX_TAGGED_ORBITS;
        // **Half the rows again.**  A sum orbit is enumerated twice, once
        // from each of its two summands' orbits, and one of the two is
        // enough: keeping the entry whose row is the *smaller* of the two
        // orbits stores each sum orbit once and still tags it with an
        // orbit a summand really lies in.
        //
        // The rule is "row `α` keeps `j` only when `orbit(j) ≥ α`", and
        // covering survives it: given `rest = P_a + P_b` with
        // `orbit(a) = α ≤ β = orbit(b)`, the `g` carrying `P_a` to
        // `rep(α)` puts `g · rest` in row `α` with its second summand in
        // orbit `β ≥ α`, so `canon(rest)` is still produced.  Row `β`
        // skips the mirror image, and nothing else does.
        //
        // Ordering the base by orbit makes "orbit at least `α`" a
        // suffix, so a row is a slice and no addend list is ever built.
        let orbit_of_point: Vec<u32> = fb
            .signed_orbit_of
            .iter()
            .map(|&(o, _, _)| o as u32)
            .collect();
        let mut order: Vec<u32> = (0..n_points as u32).collect();
        order.sort_unstable_by_key(|&i| (orbit_of_point[i as usize], i));
        let by_orbit: Vec<FastPoint> = order.iter().map(|&i| points[i as usize]).collect();
        // `suffix[o]` is where the points of orbit `o` begin.
        let mut suffix = vec![0u32; fb.signed_orbits.len() + 1];
        for (position, &i) in order.iter().enumerate() {
            suffix[orbit_of_point[i as usize] as usize + 1] = position as u32 + 1;
        }
        for o in 0..fb.signed_orbits.len() {
            suffix[o + 1] = suffix[o + 1].max(suffix[o]);
        }
        let counts: Vec<AtomicU32> = (0..buckets + 1).map(|_| AtomicU32::new(0)).collect();
        let each_row = |r: usize, f: &mut dyn FnMut(u64, u32)| {
            let mut sums = Vec::with_capacity(n_points);
            let mut scratch = BatchScratch::default();
            let (orbit, rep) = reps[r];
            let from = suffix[orbit as usize] as usize;
            curve.add_many(points[rep], &by_orbit[from..], &mut sums, &mut scratch);
            for &p in &sums {
                f(Self::canon_key_with(&curve, canon.as_ref(), p), orbit);
            }
        };
        (0..reps.len()).into_par_iter().for_each(|r| {
            each_row(r, &mut |key, _| {
                let bucket = (pair_filter_hash(key) >> bucket_shift) as usize;
                counts[bucket + 1].fetch_add(1, Ordering::Relaxed);
            });
        });
        let mut bucket_start: Vec<u32> = counts.iter().map(|c| c.load(Ordering::Relaxed)).collect();
        for b in 0..buckets {
            bucket_start[b + 1] += bucket_start[b];
        }
        let total = bucket_start[buckets] as usize;
        let cursor: Vec<AtomicU32> = bucket_start.iter().map(|&c| AtomicU32::new(c)).collect();
        let mut rests = vec![0u32; total];
        let filter_bits = (usize::BITS - (total.max(1) * 4).leading_zeros()).clamp(6, 32);
        let present_mask = (1u64 << filter_bits) - 1;
        let words = (1usize << filter_bits) / 64;
        let present_atomic: Vec<AtomicU64> = (0..words).map(|_| AtomicU64::new(0)).collect();
        let slots = rests.as_mut_ptr() as usize;
        (0..reps.len()).into_par_iter().for_each(|r| {
            each_row(r, &mut |key, orbit| {
                let bucket = (pair_filter_hash(key) >> bucket_shift) as usize;
                let slot = cursor[bucket].fetch_add(1, Ordering::Relaxed) as usize;
                // SAFETY: `slot` is this pair's own index, handed out
                // once by the bucket's cursor and inside the run the
                // counting pass measured for that bucket.
                unsafe {
                    *(slots as *mut u32).add(slot) = if tagged {
                        Self::tagged_rest(key, orbit)
                    } else {
                        Self::compact_rest(key)
                    };
                }
                let h = (pair_filter_hash(key) & present_mask) as usize;
                present_atomic[h >> 6].fetch_or(1u64 << (h & 63), Ordering::Relaxed);
            });
        });
        let present: Vec<u64> = present_atomic
            .iter()
            .map(|w| w.load(Ordering::Relaxed))
            .collect();
        let index_of_point = PointIndex::build(&points);
        // The orbits flat, in the order `reps` indexes them, so a tag is
        // a slice of `orbit_members` and nothing is allocated per hit.
        let mut orbit_start = Vec::with_capacity(fb.signed_orbits.len() + 1);
        let mut orbit_members: Vec<u32> = Vec::with_capacity(n_points);
        orbit_start.push(0u32);
        for orbit in &fb.signed_orbits {
            orbit_members.extend(orbit.iter().map(|&i| i as u32));
            orbit_start.push(orbit_members.len() as u32);
        }
        Some(Self {
            entries: Vec::new(),
            rests,
            index_of_point,
            curve,
            points,
            negated,
            bucket_start,
            bucket_shift,
            present,
            present_mask,
            fold: true,
            canon,
            orbit_start,
            orbit_members,
            tagged,
        })
    }

    /// The word a key is stored as: a hash, so the bucket width is free
    /// to be chosen for run length alone.
    ///
    /// The alternative is the key's own low bits, which a bucket index
    /// wide enough leaves exactly 32 of — but "wide enough" is
    /// `key_bits − 32`, and a packed sum is `n + 2` bits.  At `n = 53`
    /// that asks for 23 bucket bits and run length already wants 26, so
    /// it costs nothing; at `n = 59` it asks for 29 and at `n = 61` for
    /// 31, and an index of `2³¹` words is four gibibytes spent on
    /// nothing but making a rest fit.  A 36000-point base needs 2.97 GiB
    /// hashed at any degree, against 4.72 at `n = 59` and 6.72 at
    /// `n = 61` — over the budget, so the wide base was simply not
    /// available there.
    ///
    /// Neither form can give a wrong answer: build and lookup narrow a
    /// key the same way, so there are no false negatives either way.
    /// Only one of them fits.
    fn compact_rest(key: u64) -> u32 {
        pair_filter_hash(key) as u32
    }

    /// **The stored word of a folded, tagged table**: the orbit of one
    /// summand in the high half, sixteen bits of the key's hash in the
    /// low half.
    ///
    /// This is the whole of the recovery fix, and it costs no memory at
    /// all — it spends half the rest rather than adding a field.
    ///
    /// A folded entry was built as `canon(P_{rep(r)} + P_j)`, so a
    /// target whose key matches it satisfies `g · target = P_{rep(r)} +
    /// P_j` for some `g ∈ G`, and therefore `target = g⁻¹P_{rep(r)} +
    /// g⁻¹P_j` with the first summand somewhere in the *same signed
    /// orbit* `r` — orbits being what `G` preserves.  So recovery need
    /// not walk the base at all: it walks the `2n` points of orbit `r`.
    /// That is `O(n)` where it was `O(|F|)`, 122 points against 177632.
    ///
    /// The price is a shorter rest.  A bucket holds about sixteen, so a
    /// sixteen-bit rest lets a probe through wrongly about one time in
    /// four thousand rather than one in `2²⁸` — and a wrong admission
    /// now costs an orbit walk of a few microseconds instead of a scan
    /// of the base.  Over the seventeen thousand probes a decomposition
    /// spends that is some four false positives and tens of
    /// microseconds, against the milliseconds the shortened scan saves.
    /// Still no false negatives: the hash is computed the same way on
    /// both sides, and the group has the last word either way.
    #[inline]
    fn tagged_rest(key: u64, orbit: u32) -> u32 {
        (orbit << 16) | (pair_filter_hash(key) as u32 & 0xffff)
    }

    /// Largest orbit count a tag can name.
    const MAX_TAGGED_ORBITS: usize = 1 << 16;

    #[cfg(test)]
    /// **The canonical key of a point under `⟨π, −1⟩`**: the least
    /// abscissa in its Frobenius orbit, plus one so that `O` can be `0`.
    ///
    /// Negation never moves the abscissa — `−(x, y) = (x, x + y)` — so
    /// the sign half of the fold costs nothing at all, and `π` acts on
    /// the abscissa as a squaring.  The key is therefore
    /// `1 + min_k x^{2^k}`, which takes `n − 1` squarings and a running
    /// minimum and no memory at all.
    ///
    /// It is a key, not a point: it identifies the orbit and nothing
    /// else.  Recovering which base points actually sum to a target is
    /// done in the group, by [`Self::recover_pair`], and is unaffected.
    #[inline]
    fn canon_key(curve: &FastCurve, p: FastPoint) -> u64 {
        Self::canon_key_with(curve, None, p)
    }

    /// [`Self::canon_key`] using a normal basis when one is in hand.
    ///
    /// The two disagree on what an orbit is *called* — one takes the
    /// least element of the Frobenius orbit, the other the least
    /// rotation of the normal coordinates — and agree exactly on which
    /// points share a name, which is all a key has to do.  A table is of
    /// course built and queried with the same one.
    #[inline]
    fn canon_key_with(curve: &FastCurve, canon: Option<&FrobeniusCanon>, p: FastPoint) -> u64 {
        if p.infinity {
            return 0;
        }
        if let Some(canon) = canon {
            return canon.canon(p.x) + 1;
        }
        let mut x = p.x;
        let mut best = x;
        for _ in 1..curve.n {
            x = curve.field.sqr(x);
            if x < best {
                best = x;
            }
        }
        best + 1
    }

    /// The key this table stores a point under: the packed point, or its
    /// orbit's canonical key when the table is folded.
    #[inline]
    fn key_of(&self, p: FastPoint) -> u64 {
        if self.fold {
            Self::canon_key_with(&self.curve, self.canon.as_ref(), p)
        } else {
            p.pack()
        }
    }

    /// [`Self::key_of`] over a slice, keeping `LANES` canonicalisations
    /// in flight.
    ///
    /// A squaring chain is a dependency chain, so one point at a time
    /// runs at the latency of `n − 1` squarings; a decomposition scan
    /// has a whole row of rests in hand at once and none of them depend
    /// on each other.  Interleaving them turns the chain from
    /// latency-bound into throughput-bound.  `out` is cleared first.
    fn keys_of(&self, points: &[FastPoint], out: &mut Vec<u64>) {
        out.clear();
        if !self.fold {
            out.extend(points.iter().map(|p| p.pack()));
            return;
        }
        if let Some(canon) = self.canon.as_ref() {
            // A rotation has no dependency chain worth interleaving.
            out.extend(
                points
                    .iter()
                    .map(|p| if p.infinity { 0 } else { canon.canon(p.x) + 1 }),
            );
            return;
        }
        const LANES: usize = 8;
        let n = self.curve.n;
        let field = &self.curve.field;
        out.resize(points.len(), 0);
        for (chunk, keys) in points.chunks(LANES).zip(out.chunks_mut(LANES)) {
            let mut x = [0u64; LANES];
            let mut best = [0u64; LANES];
            for (l, &p) in chunk.iter().enumerate() {
                x[l] = p.x;
                best[l] = p.x;
            }
            for _ in 1..n {
                for l in 0..chunk.len() {
                    x[l] = field.sqr(x[l]);
                    if x[l] < best[l] {
                        best[l] = x[l];
                    }
                }
            }
            for (l, &p) in chunk.iter().enumerate() {
                keys[l] = if p.infinity { 0 } else { best[l] + 1 };
            }
        }
    }

    /// Which representation this table is, for a run to record.
    ///
    /// The tiers differ by an order of magnitude in build cost and in
    /// resident memory, and a run that selected a different one than its
    /// author believed looks exactly like a run that did not.  A report
    /// that does not name the tier cannot be compared with another.
    pub fn tier(&self) -> &'static str {
        if self.fold {
            "folded"
        } else if self.is_compact() {
            "compact"
        } else {
            "full"
        }
    }

    /// Whether this table folds its keys by the signed Frobenius group.
    pub fn is_folded(&self) -> bool {
        self.fold
    }

    /// Whether this table keeps the summands of each pair.
    pub fn is_compact(&self) -> bool {
        self.entries.is_empty() && !self.rests.is_empty()
    }

    /// Number of stored pair sums (with multiplicity).
    pub fn len(&self) -> usize {
        if self.is_compact() {
            return self.rests.len();
        }
        self.entries.len()
    }

    /// Whether the table is empty.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// The single-word curve the table was built on.
    pub fn curve(&self) -> &FastCurve {
        &self.curve
    }

    /// The bucket a key's run lives in.
    ///
    /// An unfolded table keys on the packed point, whose abscissa is
    /// spread evenly over the field, so its high bits are a fair bucket.
    /// A *canonical* key is not: it is a minimum over the `n` rotations
    /// of a word, and a minimum of `n` draws sits far below the middle
    /// of the range.  Bucketing on those high bits piles the whole table
    /// into the first few buckets — the presence filter hides it,
    /// because a probe that misses never reaches a run, but every hit
    /// then walks an enormous one.  The hash the filter and the rest are
    /// already made of is flat, so a folded table buckets on that.
    #[inline]
    fn bucket_of(&self, key: u64) -> usize {
        if self.fold {
            (pair_filter_hash(key) >> self.bucket_shift) as usize
        } else {
            (key >> self.bucket_shift) as usize
        }
    }

    /// Index of the filter word holding this key's bit.
    #[inline]
    fn filter_word(&self, key: u64) -> usize {
        ((pair_filter_hash(key) & self.present_mask) as usize) >> 6
    }

    /// Whether the filter admits this key.  A `false` is certain; a
    /// `true` still has to be checked against the entries.
    #[inline]
    fn admitted(&self, key: u64) -> bool {
        let h = (pair_filter_hash(key) & self.present_mask) as usize;
        self.present[h >> 6] >> (h & 63) & 1 == 1
    }

    /// All `(i, j)` with `P_i + P_j` equal to the packed point.
    ///
    /// Compact tables do not store those triples, so this returns an
    /// empty slice for them.  [`Self::pairs_for`] answers either
    /// representation.
    #[inline]
    pub fn lookup(&self, key: u64) -> &[(u64, u32, u32)] {
        if self.is_compact() || self.fold || !self.admitted(key) {
            return &[];
        }
        self.lookup_admitted(key)
    }

    /// [`Self::lookup`] for a key the filter has already admitted.
    #[inline]
    /// Whether the compact table may hold this key: never a false
    /// negative, and a false positive about one time in `2²⁸`, which
    /// costs a recovery scan that comes back empty.
    fn compact_contains(&self, key: u64) -> bool {
        let bucket = self.bucket_of(key);
        let Some(&lo) = self.bucket_start.get(bucket) else {
            return false;
        };
        let hi = self.bucket_start[bucket + 1];
        let run = &self.rests[lo as usize..hi as usize];
        // A run holds about sixteen rests, which is one cache line: a
        // scan beats a search and spares the build any ordering.
        if self.tagged {
            let rest = (pair_filter_hash(key) as u32) & 0xffff;
            return run.iter().any(|&w| w & 0xffff == rest);
        }
        run.contains(&Self::compact_rest(key))
    }

    /// The orbits a tagged table offers for this key, as the high halves
    /// of the run's matching words.  `out` is cleared first.
    fn candidate_orbits(&self, key: u64, out: &mut Vec<u32>) {
        out.clear();
        let bucket = self.bucket_of(key);
        let Some(&lo) = self.bucket_start.get(bucket) else {
            return;
        };
        let hi = self.bucket_start[bucket + 1];
        let rest = (pair_filter_hash(key) as u32) & 0xffff;
        for &word in &self.rests[lo as usize..hi as usize] {
            if word & 0xffff == rest {
                out.push(word >> 16);
            }
        }
        // Sorted rather than checked on the way in.  A run normally
        // yields one orbit and either would do, but a degenerate key can
        // yield thousands — `O` is the sum of every `±` pair, so every
        // orbit representative stores one — and a linear membership test
        // per push makes that quadratic.
        if out.len() > 1 {
            out.sort_unstable();
            out.dedup();
        }
    }

    /// The summands of a pair the compact table holds, recovered by one
    /// pass over the base: `target − P_i` is a base point exactly when
    /// `i` is a summand.  Paid on a hit, which is rare — that is the
    /// trade the compact table makes.
    fn recover_pair(&self, target: FastPoint, out: &mut Vec<(u32, u32)>) {
        // A block at a time rather than the whole base at once: the
        // differences are written and then read back exactly once, and
        // at `|F| = 177632` a buffer for all of them is four megabytes
        // that leaves the cache before it is used.  One batched
        // inversion per block is still one per thousand additions.
        const BLOCK: usize = 4096;
        let mut rests = Vec::with_capacity(BLOCK);
        let mut scratch = BatchScratch::default();
        if self.tagged {
            self.recover_pair_tagged(target, out);
            return;
        }
        for (b, addends) in self.negated.chunks(BLOCK).enumerate() {
            rests.clear();
            self.curve
                .add_many(target, addends, &mut rests, &mut scratch);
            for (offset, rest) in rests.iter().enumerate() {
                if rest.infinity {
                    continue;
                }
                if let Some(j) = self.index_of_point.get(rest.pack()) {
                    let i = (b * BLOCK + offset) as u32;
                    if i <= j {
                        out.push((i, j));
                    }
                }
            }
        }
    }

    /// **Whether `target` is a sum of two base points**, without
    /// recovering which two.
    ///
    /// This is the probe the descent actually spends: a decomposition
    /// search asks this `2r/|F|²` times and recovers summands only on
    /// the rare hit.  Separating it matters for measurement as well as
    /// for callers — on a wide base the recovery scan is `O(|F|)` and
    /// would otherwise be charged to the probes it sits among.
    ///
    /// A `false` is certain.  A `true` may be a false positive of the
    /// stored rest, about one time in `2²⁸`, which [`Self::pairs_for`]
    /// then resolves in the group.
    pub fn contains_pair(&self, target: FastPoint) -> bool {
        self.contains_key(self.probe_key(target))
    }

    /// The key half of [`Self::contains_pair`], exposed so a benchmark
    /// can time the two halves apart.
    #[doc(hidden)]
    pub fn probe_key(&self, target: FastPoint) -> u64 {
        self.key_of(target)
    }

    /// The prefetch the blocked descent loop issues ahead of a key,
    /// exposed so a benchmark can model that loop exactly.
    #[doc(hidden)]
    pub fn prefetch_key(&self, key: u64) {
        prefetch(&self.present[self.filter_word(key)]);
    }

    /// The lookup half of [`Self::contains_pair`].
    #[doc(hidden)]
    pub fn contains_key(&self, key: u64) -> bool {
        if !self.admitted(key) {
            return false;
        }
        if self.is_compact() {
            return self.compact_contains(key);
        }
        !self.lookup_admitted(key).is_empty()
    }

    /// [`Self::recover_pair`] on a tagged folded table: the `2n` points
    /// of each candidate orbit rather than the whole base.
    ///
    /// The stored word names the signed orbit one summand lies in
    /// ([`Self::tagged_rest`]), so the search is over that orbit alone.
    /// It is still the group that decides: `target − P` is a base point
    /// or it is not, so a tag that came from a sixteen-bit collision
    /// costs this walk and yields nothing.
    fn recover_pair_tagged(&self, target: FastPoint, out: &mut Vec<(u32, u32)>) {
        let key = self.key_of(target);
        let mut orbits = Vec::new();
        self.candidate_orbits(key, &mut orbits);
        let mut rests = Vec::new();
        let mut scratch = BatchScratch::default();
        let mut addends = Vec::new();
        for orbit in orbits {
            let (lo, hi) = (orbit as usize, orbit as usize + 1);
            let (Some(&start), Some(&end)) = (self.orbit_start.get(lo), self.orbit_start.get(hi))
            else {
                continue;
            };
            let members = &self.orbit_members[start as usize..end as usize];
            addends.clear();
            addends.extend(members.iter().map(|&i| self.negated[i as usize]));
            rests.clear();
            self.curve
                .add_many(target, &addends, &mut rests, &mut scratch);
            for (slot, rest) in rests.iter().enumerate() {
                if rest.infinity {
                    continue;
                }
                let i = members[slot];
                if let Some(j) = self.index_of_point.get(rest.pack()) {
                    out.push(if i <= j { (i, j) } else { (j, i) });
                }
            }
        }
        // A pair whose two summands lie in different candidate orbits is
        // found once from each, so the answer is deduplicated — by
        // sorting, for the same reason as above.
        if out.len() > 1 {
            out.sort_unstable();
            out.dedup();
        }
    }

    /// The summand pairs of `target`, however the table stores them.
    /// `out` is cleared first.
    pub fn pairs_for(&self, target: FastPoint, out: &mut Vec<(u32, u32)>) {
        let key = self.key_of(target);
        self.pairs_for_key(target, key, out)
    }

    /// [`Self::pairs_for`] for a target whose key is already in hand, so
    /// that a scan canonicalising a row at a time does not do it twice.
    fn pairs_for_key(&self, target: FastPoint, key: u64, out: &mut Vec<(u32, u32)>) {
        out.clear();
        if !self.admitted(key) {
            return;
        }
        if self.is_compact() {
            if self.compact_contains(key) {
                self.recover_pair(target, out);
            }
            return;
        }
        out.extend(self.lookup_admitted(key).iter().map(|&(_, i, j)| (i, j)));
    }

    fn lookup_admitted(&self, key: u64) -> &[(u64, u32, u32)] {
        if self.entries.is_empty() {
            return &[];
        }
        let bucket = (key >> self.bucket_shift) as usize;
        let Some(&lo) = self.bucket_start.get(bucket) else {
            return &[];
        };
        let hi = self.bucket_start[bucket + 1];
        let run = &self.entries[lo as usize..hi as usize];
        let start = run.partition_point(|e| e.0 < key);
        let end = start + run[start..].partition_point(|e| e.0 == key);
        &run[start..end]
    }

    /// **Decompose** `target` into exactly `m ∈ {2, 3, 4}` base points,
    /// returning sorted indices, or `None` when no decomposition exists
    /// (a complete search) or `m` is unsupported.  The returned sum is
    /// re-checked in the general group arithmetic before it is handed
    /// back.
    pub fn decompose(
        &self,
        kc: &KoblitzCurve,
        fb: &FrobeniusFactorBase,
        target: &BinaryPoint,
        m: usize,
    ) -> Option<Vec<usize>> {
        let idxs = self.decompose_fast(self.curve.lift(target), m)?;
        let sum = idxs
            .iter()
            .fold(BinaryPoint::Infinity, |s, &i| kc.add(&s, &fb.points[i]));
        (sum == *target).then_some(idxs)
    }

    /// [`Self::decompose`] on a lifted target, re-checked in the
    /// single-word arithmetic.
    pub fn decompose_fast(&self, target: FastPoint, m: usize) -> Option<Vec<usize>> {
        let mut found: Option<Vec<usize>> = None;
        // Any witness, not the sorted one: one decomposition is wanted,
        // and insisting on `j ≤ k` here throws away two recoveries in
        // three to get the same answer later.  Sorted on the way out, so
        // what a caller sees is unchanged.
        self.witnesses_fast_inner(target, m, false, &mut |witness| {
            found = Some(witness.to_vec());
            false
        });
        let mut idxs = found?;
        idxs.sort_unstable();
        let sum = idxs.iter().fold(FastPoint::INFINITY, |s, &i| {
            self.curve.add(s, self.points[i])
        });
        (sum == target).then_some(idxs)
    }

    /// Decompose scanning only a cyclic window of the base.
    ///
    /// The full `m = 3` scan spends `|F|` filter probes per target and
    /// finds each decomposition three times over — once as `k = i`,
    /// once as `k = j`, once as `k = k` — then throws two of the three
    /// away to keep witnesses sorted.  A window of `len` summands keeps
    /// all three chances but pays for only `len` of them: a triple is
    /// caught whenever *any* of its three indices falls in the window,
    /// so the yield per probe falls by `1 − (1 − f)³ ≈ 3f` while the
    /// cost falls by `f`.  Per *lookup* that is three times the
    /// relations, bought with more targets rather than more scanning.
    ///
    /// `start` is taken modulo the base size and the window wraps.  A
    /// window at least as long as the base is the full scan.  Witnesses
    /// come back unsorted, and the sum is re-checked in the group
    /// exactly as [`Self::decompose_fast`] checks it.
    pub fn decompose_fast_window(
        &self,
        target: FastPoint,
        m: usize,
        start: usize,
        len: usize,
    ) -> Option<Vec<usize>> {
        let mut found: Option<Vec<usize>> = None;
        self.witnesses_fast_window(target, m, start, len, &mut |witness| {
            found = Some(witness.to_vec());
            false
        });
        let idxs = found?;
        let sum = idxs.iter().fold(FastPoint::INFINITY, |s, &i| {
            self.curve.add(s, self.points[i])
        });
        (sum == target).then_some(idxs)
    }

    /// [`Self::decompose_fast_window`]'s enumerator.  For `m = 2` the
    /// lookup is already `O(1)` and the window is ignored; for `m = 3`
    /// the window bounds the third summand and witnesses may repeat a
    /// triple up to three times, once per index that lands in it.
    pub fn witnesses_fast_window(
        &self,
        target: FastPoint,
        m: usize,
        start: usize,
        len: usize,
        sink: &mut dyn FnMut(&[usize]) -> bool,
    ) {
        let base = self.points.len();
        if m != 3 || base == 0 || len >= base {
            self.witnesses_fast(target, m, sink);
            return;
        }
        if len == 0 {
            return;
        }
        let start = start % base;
        let tail = len.min(base - start);
        let mut rests = Vec::with_capacity(len);
        let mut scratch = BatchScratch::default();
        self.curve.add_many(
            target,
            &self.negated[start..start + tail],
            &mut rests,
            &mut scratch,
        );
        if tail < len {
            self.curve.add_many(
                target,
                &self.negated[..len - tail],
                &mut rests,
                &mut scratch,
            );
        }
        // Keys a block at a time: enough to keep `LANES`
        // canonicalisations interleaved — and, with a
        // [`FrobeniusCanon`], enough to let consecutive lookups overlap
        // their memory round trips, which the key's own latency
        // prevents when the two are fused; see the `m = 3` arm of
        // [`Self::witnesses_fast_inner`].  Little enough that a search
        // stopping at its first witness has not paid for the rest.
        const BLOCK: usize = 1024;
        const LOOKAHEAD: usize = 32;
        let mut keys = Vec::with_capacity(BLOCK);
        let mut pairs = Vec::new();
        for (b, block) in rests.chunks(BLOCK).enumerate() {
            self.keys_of(block, &mut keys);
            for &key in keys.iter().take(LOOKAHEAD) {
                prefetch(&self.present[self.filter_word(key)]);
            }
            for (within, rest) in block.iter().enumerate() {
                if let Some(&ahead) = keys.get(within + LOOKAHEAD) {
                    prefetch(&self.present[self.filter_word(ahead)]);
                }
                if !self.admitted(keys[within]) {
                    continue;
                }
                let offset = b * BLOCK + within;
                let k = if offset < tail {
                    start + offset
                } else {
                    offset - tail
                };
                self.pairs_for_key(*rest, keys[within], &mut pairs);
                for &(i, j) in &pairs {
                    if !sink(&[i as usize, j as usize, k]) {
                        return;
                    }
                }
            }
        }
    }

    /// **Enumerate every sorted witness** `i_1 ≤ … ≤ i_m` with
    /// `Σ P_{i_k} = target`, calling `sink` for each; the sink returns
    /// `true` to continue and `false` to stop.  Supports `m ∈ {2, 3, 4}`.
    pub fn witnesses(
        &self,
        _kc: &KoblitzCurve,
        _fb: &FrobeniusFactorBase,
        target: &BinaryPoint,
        m: usize,
        sink: &mut dyn FnMut(&[usize]) -> bool,
    ) {
        self.witnesses_fast(self.curve.lift(target), m, sink)
    }

    /// [`Self::witnesses`] on a lifted target.
    pub fn witnesses_fast(
        &self,
        target: FastPoint,
        m: usize,
        sink: &mut dyn FnMut(&[usize]) -> bool,
    ) {
        self.witnesses_fast_inner(target, m, true, sink)
    }

    /// [`Self::witnesses_fast`], optionally without the sorted-witness
    /// condition.
    ///
    /// Enumerating every *sorted* witness is what exact yield needs, and
    /// the condition `j ≤ k` is how a triple found three times over —
    /// once for each of its indices playing the role of `k` — is counted
    /// once.  A search that wants a single decomposition needs none of
    /// that: it rejects two witnesses in three *after* paying the
    /// `O(|F|)` recovery scan that produced them, which on a wide base
    /// is the dominant cost of the whole search.  With `sorted` false
    /// the same triples come back unordered and possibly repeated, and
    /// a witness arrives about three times sooner.
    fn witnesses_fast_inner(
        &self,
        target: FastPoint,
        m: usize,
        sorted: bool,
        sink: &mut dyn FnMut(&[usize]) -> bool,
    ) {
        match m {
            2 => {
                let mut pairs = Vec::new();
                self.pairs_for(target, &mut pairs);
                for (i, j) in pairs {
                    if !sink(&[i as usize, j as usize]) {
                        return;
                    }
                }
            }
            3 => {
                // `R − P_k` for every `k`, a block at a time.
                //
                // Everything this loop does before it probes —
                // subtracting a base point, and on a folded table
                // canonicalising the difference — is linear in the base,
                // and the search stops at its first witness.  Done a row
                // at a time that setup is paid in full however early the
                // stop comes, and on a base wide enough to decompose
                // most targets it is then the whole cost: at `|F| =
                // 177632` the scan finds its witness in about three
                // thousand probes and would have prepared a hundred and
                // seventy-seven thousand.  A block is long enough to
                // amortise one field inversion and to keep `LANES`
                // squaring chains interleaved, and short enough that an
                // early exit throws away at most a block.
                //
                // The block earns its keep on a folded table even where
                // there is nothing to interleave.  With a
                // [`FrobeniusCanon`] the key is a rotation and
                // [`Self::keys_of`] runs it one point at a time, but it
                // is still some seventy-six nanoseconds of dependent
                // work before the address it will load is known — long
                // enough that consecutive probes' memory round trips do
                // not overlap when the two are fused.  Split, the
                // lookups are adjacent and independent and do overlap.
                // A compact table, whose key is a `pack`, gains a third
                // where this gains four fifths, which is what says the
                // cause is the length of the key; which resource the
                // length exhausts is not established.
                // `examples/koblitz_orbit_fold_width.rs` measures the
                // sweep, `docs/ic/runs/koblitz-probe-shape-20260913.json`
                // records it.  Do not unroll this back into a single
                // loop.
                const BLOCK: usize = 1024;
                const LOOKAHEAD: usize = 32;
                let mut rests = Vec::with_capacity(BLOCK);
                let mut scratch = BatchScratch::default();
                let mut keys = Vec::with_capacity(BLOCK);
                let mut pairs = Vec::new();
                for (b, addends) in self.negated.chunks(BLOCK).enumerate() {
                    // `add_many` appends, so the block starts empty.
                    rests.clear();
                    self.curve
                        .add_many(target, addends, &mut rests, &mut scratch);
                    let block = &rests[..];
                    self.keys_of(block, &mut keys);
                    for &key in keys.iter().take(LOOKAHEAD) {
                        prefetch(&self.present[self.filter_word(key)]);
                    }
                    for (offset, rest) in block.iter().enumerate() {
                        if let Some(&ahead) = keys.get(offset + LOOKAHEAD) {
                            prefetch(&self.present[self.filter_word(ahead)]);
                        }
                        if !self.admitted(keys[offset]) {
                            continue;
                        }
                        let k = b * BLOCK + offset;
                        self.pairs_for_key(*rest, keys[offset], &mut pairs);
                        for &(i, j) in &pairs {
                            if (!sorted || j as usize <= k) && !sink(&[i as usize, j as usize, k]) {
                                return;
                            }
                        }
                    }
                }
            }
            4 => {
                // Every second half `R − (P_k + P_l)`, walked over the
                // base rather than over the stored triples: the compact
                // representation does not keep those, and walking them
                // there would have reported no witness for a target that
                // has one — a false "no" from an oracle, which is worse
                // than a loud failure.  One batched inversion a row
                // keeps the arithmetic close to what the triples cost.
                let mut sums = Vec::new();
                let mut scratch = BatchScratch::default();
                let mut pairs = Vec::new();
                for l in 0..self.points.len() {
                    sums.clear();
                    self.curve.add_many(
                        self.points[l],
                        &self.points[..=l],
                        &mut sums,
                        &mut scratch,
                    );
                    for (k, &pair) in sums.iter().enumerate() {
                        let rest = self.curve.add(target, self.curve.neg(pair));
                        self.pairs_for(rest, &mut pairs);
                        for &(i, j) in &pairs {
                            if (!sorted || j as usize <= k)
                                && !sink(&[i as usize, j as usize, k, l])
                            {
                                return;
                            }
                        }
                    }
                }
            }
            _ => {}
        }
    }
}

/// Lift a tuple of candidate `x`-coordinates to factor-base points
/// whose sum really is `target`.
///
/// `S₃ = 0` constrains abscissae only, so it pins the summands down to
/// sign: each `x` admits up to two points `(x, y)` and `(x, x+y)`, both
/// of which lie in the (negation-closed) factor base.  This walks the
/// `≤ 2^m` sign choices and returns the first that closes the group
/// identity, so a spurious root of the polynomial system can never
/// become a relation.
pub(crate) fn lift_candidate(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    index_of: &HashMap<(BigUint, BigUint), usize>,
    xs: &[F2mElement],
    target: &BinaryPoint,
) -> Option<Vec<usize>> {
    fn walk(
        kc: &KoblitzCurve,
        fb: &FrobeniusFactorBase,
        index_of: &HashMap<(BigUint, BigUint), usize>,
        xs: &[F2mElement],
        depth: usize,
        acc: &BinaryPoint,
        chosen: &mut Vec<usize>,
        target: &BinaryPoint,
    ) -> bool {
        if depth == xs.len() {
            return acc == target;
        }
        for p in points_with_x(&kc.curve, &xs[depth]) {
            let idx = match index_of.get(&point_key(&p)) {
                Some(i) => *i,
                None => continue,
            };
            chosen.push(idx);
            let next = kc.add(acc, &fb.points[idx]);
            if walk(kc, fb, index_of, xs, depth + 1, &next, chosen, target) {
                return true;
            }
            chosen.pop();
        }
        false
    }

    let mut chosen = Vec::with_capacity(xs.len());
    if walk(
        kc,
        fb,
        index_of,
        xs,
        0,
        &BinaryPoint::Infinity,
        &mut chosen,
        target,
    ) {
        chosen.sort_unstable();
        Some(chosen)
    } else {
        None
    }
}

/// **Algebraic decomposition**: solve the Semaev system for
/// `R = P_1 + … + P_m` over the factor base.
///
/// Returns the factor-base indices of a decomposition, plus the solver
/// statistics, or `None` when the system has no root that lifts.  A
/// `None` from a completed solve is a *proof* that no decomposition
/// exists over this factor base; a `None` with `stats.exhausted` set
/// only means the node budget ran out.
pub fn groebner_decompose(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    index_of: &HashMap<(BigUint, BigUint), usize>,
    st: &FieldStructure,
    target: &BinaryPoint,
    m: usize,
    engine: SolverEngine,
    node_budget: usize,
) -> (Option<Vec<usize>>, SolveStats) {
    let x_r = match target {
        BinaryPoint::Affine { x, .. } => x.clone(),
        BinaryPoint::Infinity => return (None, SolveStats::default()),
    };
    let sys = match crate::cryptanalysis::polynomial_reuse::build_decomposition_system_reusing(
        &fb.subspace_basis,
        &x_r,
        &kc.curve.b,
        m,
        st,
    ) {
        Some(sys) => sys,
        None => return (None, SolveStats::default()),
    };
    // A root of S₃ fixes the summands only up to sign, so some roots do
    // not lift.  Lift each as it is found and stop at the first that
    // closes the group identity.
    let opts = SolveOptions {
        engine,
        max_solutions: usize::MAX,
        node_budget,
        split_rule: split_rule_default(),
    };
    let mut found: Option<Vec<usize>> = None;
    let (_, stats) = solve_boolean_system_filtered(&sys.equations, sys.n_vars, &opts, |root| {
        let xs: Vec<F2mElement> = (0..m)
            .map(|i| sys.summand_x(&fb.subspace_basis, root, i, kc.n))
            .collect();
        match lift_candidate(kc, fb, index_of, &xs, target) {
            Some(idxs) => {
                found = Some(idxs);
                true
            }
            None => false,
        }
    });
    (found, stats)
}

/// [`groebner_decompose`] for a batch of targets: their searches run in
/// lockstep ([`crate::cryptanalysis::f4_batch::solve_lockstep`]) and each
/// round's Macaulay matrices are decided together by `decider` — the host
/// kernel, a GPU, or the GPU kernel's emulator.
///
/// Per target the result is [`groebner_decompose`]'s: the same
/// decomposition (the first root, in the same search order, that lifts)
/// and the same [`SolveStats`], whichever decider answers.
pub fn groebner_decompose_batch(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    index_of: &HashMap<(BigUint, BigUint), usize>,
    st: &FieldStructure,
    targets: &[BinaryPoint],
    m: usize,
    engine: SolverEngine,
    node_budget: usize,
    decider: &mut dyn BatchDecider,
) -> (Vec<(Option<Vec<usize>>, SolveStats)>, LockstepReport) {
    let mut built = Vec::new();
    let mut systems = Vec::new();
    let mut slot = vec![None; targets.len()];
    for (t, target) in targets.iter().enumerate() {
        let BinaryPoint::Affine { x: x_r, .. } = target else {
            continue;
        };
        if let Some(sys) =
            crate::cryptanalysis::polynomial_reuse::build_decomposition_system_reusing(
                &fb.subspace_basis,
                x_r,
                &kc.curve.b,
                m,
                st,
            )
        {
            slot[t] = Some(built.len());
            systems.push((sys.equations.clone(), sys.n_vars));
            built.push((sys, t));
        }
    }
    let opts = SolveOptions {
        engine,
        max_solutions: usize::MAX,
        node_budget,
        split_rule: split_rule_default(),
    };
    let lift = |i: usize, root: u64| -> Option<Vec<usize>> {
        let (sys, t) = &built[i];
        let xs: Vec<F2mElement> = (0..m)
            .map(|j| sys.summand_x(&fb.subspace_basis, root, j, kc.n))
            .collect();
        lift_candidate(kc, fb, index_of, &xs, &targets[*t])
    };
    let (outcomes, report) =
        solve_lockstep(&systems, &opts, decider, &|i, root| lift(i, root).is_some());
    let results = slot
        .iter()
        .map(|s| match s {
            None => (None, SolveStats::default()),
            Some(i) => {
                let o = &outcomes[*i];
                (o.accepted.and_then(|root| lift(*i, root)), o.stats.clone())
            }
        })
        .collect();
    (results, report)
}

/// Decompose `target` with **Crossbred** ([`crate::cryptanalysis::crossbred`]).
///
/// The same Semaev system [`groebner_decompose`] builds, handed to a
/// different engine.  Preprocessing extracts a crossbred space at
/// degree `D`; the search then sweeps `2^k` assignments of the first
/// `k` variables, each leaving a linear solve in the rest.
///
/// `params` fixes `(D, k)`; `None` takes `D` from the system's own
/// degree and `k = n_vars / 2`, capped by the search's enumeration
/// budget.  As in the Gröbner path a root of `S₃` fixes the summands
/// only up to sign, so each is lifted and the first that closes the
/// group identity wins.
///
/// Returns `(None, stats)` with `stats.exhausted` set when no crossbred
/// space exists at those parameters — that is "cannot say", not a
/// refutation, and the caller records it as
/// [`KoblitzRelationAttemptDisposition::Unknown`].
pub fn crossbred_decompose(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    index_of: &HashMap<(BigUint, BigUint), usize>,
    st: &FieldStructure,
    target: &BinaryPoint,
    m: usize,
    params: Option<CrossbredParams>,
) -> (Option<Vec<usize>>, CrossbredSearchStats) {
    let unknown = || CrossbredSearchStats {
        exhausted: true,
        ..CrossbredSearchStats::default()
    };
    let x_r = match target {
        BinaryPoint::Affine { x, .. } => x.clone(),
        BinaryPoint::Infinity => return (None, CrossbredSearchStats::default()),
    };
    let sys = match crate::cryptanalysis::polynomial_reuse::build_decomposition_system_reusing(
        &fb.subspace_basis,
        &x_r,
        &kc.curve.b,
        m,
        st,
    ) {
        Some(sys) => sys,
        None => return (None, CrossbredSearchStats::default()),
    };
    let params = params.unwrap_or_else(|| crossbred_params_for(&sys.equations, sys.n_vars));
    let xb = match extract_crossbred(&sys.equations, sys.n_vars, &params) {
        Some(xb) => xb,
        None => return (None, unknown()),
    };
    let (roots, stats) = solve_crossbred(&sys.equations, &xb, &CrossbredSearchOptions::default());
    for root in roots {
        let xs: Vec<F2mElement> = (0..m)
            .map(|i| sys.summand_x(&fb.subspace_basis, root, i, kc.n))
            .collect();
        if let Some(idxs) = lift_candidate(kc, fb, index_of, &xs, target) {
            return (Some(idxs), stats);
        }
    }
    (None, stats)
}

/// Default `(D, k)` for a system this shape.
///
/// `D` is the system's own degree, which is the smallest Macaulay
/// degree that can produce anything, and `k = n_vars / 2` splits the
/// variables evenly — the sweep in `RESEARCH_ECC2K130_CROSSBRED.md`
/// found the kernel grows with `k` and the search cost grows as `2^k`,
/// so the midpoint is the defensible default rather than a tuned one.
/// `k` is capped so the sweep stays inside the search's memory budget.
fn crossbred_params_for(system: &[F2BoolPoly], n_vars: usize) -> CrossbredParams {
    let degree = system
        .iter()
        .flat_map(|p| p.terms.iter())
        .map(|t| t.mask.count_ones())
        .max()
        .unwrap_or(2)
        .max(2);
    let budget = CrossbredSearchOptions::default().max_enumerated_bits as usize;
    CrossbredParams {
        macaulay_degree: degree,
        enumerated: (n_vars / 2).clamp(1, n_vars.saturating_sub(1).min(budget)),
        target_degree: 1,
        ..CrossbredParams::default()
    }
}

/// What a SAT decomposition attempt cost and concluded.
#[derive(Clone, Debug, Default)]
pub struct SatDecompositionStats {
    /// CDCL solve calls (one per model examined, plus the final one).
    pub solver_calls: usize,
    /// Roots the solver produced, including any that failed to lift.
    pub models: usize,
    /// The search ended in UNSAT, so "no decomposition" is *proven* —
    /// the SAT analogue of the Gröbner infeasibility certificate.
    pub refuted: bool,
    /// The model cap or the solver's conflict budget was hit, so a
    /// `None` result is inconclusive rather than a refutation.
    pub exhausted: bool,
    /// Models that did not satisfy the original system — always zero
    /// unless the CNF encoding is wrong.
    pub spurious: usize,
    /// Implied Macaulay rows added to the CNF (see
    /// [`sat_decompose`]'s `macaulay_degree`).
    pub implied_rows: usize,
    /// Conflicts across every solve call — a machine-independent
    /// measure of search effort.
    pub conflicts: u64,
}

/// Encode a finite set of coordinates without enumerating its complement.
/// Missing branches of the binary trie become forbidden-prefix clauses.
/// No auxiliary variables are needed; at most O(ell * |codes|) clauses.
fn add_coordinate_domain(
    solver: &mut crate::cryptanalysis::sat::Solver,
    offset: usize,
    ell: usize,
    codes: &[u64],
) {
    fn visit(
        solver: &mut crate::cryptanalysis::sat::Solver,
        offset: usize,
        bit: usize,
        codes: &[u64],
        prefix: &mut Vec<i32>,
    ) {
        if codes.is_empty() {
            solver.add_clause(prefix.clone());
            return;
        }
        if bit == 0 {
            return;
        }
        let b = bit - 1;
        let split = codes.partition_point(|code| (code >> b) & 1 == 0);
        let lit = (offset + b + 1) as i32;
        prefix.push(lit); // forbid prefix with this bit zero
        visit(solver, offset, b, &codes[..split], prefix);
        *prefix.last_mut().unwrap() = -lit;
        visit(solver, offset, b, &codes[split..], prefix);
        prefix.pop();
    }
    visit(solver, offset, ell, codes, &mut Vec::new());
}

/// Absolute trace F_(2^n) -> F_2 in the configured field representation.
fn absolute_trace_bit(x: &F2mElement, n: u32, irr: &IrreduciblePoly) -> bool {
    let mut t = F2mElement::zero(n);
    let mut power = x.clone();
    for _ in 0..n {
        t = t.add(&power);
        power = power.square(irr);
    }
    debug_assert!(t.is_zero() || t == F2mElement::one(n));
    !t.is_zero()
}

/// SAT controls for a paired comparison on the same decomposition system.
#[derive(Clone, Copy, Debug)]
pub struct SatDecompositionOptions {
    pub encoding: XorEncoding,
    /// Prioritize summand coordinates; all other variables remain eligible.
    pub branch_on_summands: bool,
    /// Exclude summand coordinates without a rational factor-base point.
    /// Costs O(m * ell * 2^ell) preprocessing; for materialised bases only.
    pub restrict_to_factor_base: bool,
    /// Add the group homomorphism Tr(x(P) + a) as one linear XOR row.
    pub trace_constraint: bool,
    /// Cumulative conflict cap across every model of one target.
    pub conflict_budget: u64,
    /// Order the summands lexicographically by subspace code,
    /// `code(x_1) ≤ code(x_2) ≤ … ≤ code(x_m)`.  The summands are
    /// interchangeable, so if any decomposition exists a sorted one
    /// does (for a chained system the intermediates simply follow the
    /// new order), and the constraint is exact: no verdict changes.
    ///
    /// **Off by default, because it does not pay here.**  Measured with
    /// `koblitz_sat_symmetry_ablation` (conflict budget 400 000, verdicts
    /// cross-checked against search on every target):
    ///
    /// | instance | targets | conflicts off | conflicts on |
    /// |:---------|--------:|--------------:|-------------:|
    /// | K_0/2^9, m = 3 | 8 | 5 512 | 6 412 |
    /// | K_1/2^9, m = 2 | 16 | 428 | 823 |
    /// | K_0/2^7, m = 2 | 16 | 70 | 79 |
    /// | K_1/2^15, m = 3 | 8 | 0 | 0 |
    ///
    /// The degree-2 Macaulay rows and the trace row already leave these
    /// systems almost propagation-closed, and the `ℓ − 1` "equal so far"
    /// auxiliaries per adjacent pair add decisions without removing
    /// search.  Kept as a control for larger chained instances.
    pub symmetry_breaking: bool,
}

impl Default for SatDecompositionOptions {
    fn default() -> Self {
        Self {
            encoding: XorEncoding::Native,
            branch_on_summands: false,
            restrict_to_factor_base: false,
            trace_constraint: true,
            conflict_budget: u64::MAX,
            symmetry_breaking: false,
        }
    }
}

/// Install `code(a) ≤ code(b)` (unsigned, bit `width − 1` most
/// significant) between two blocks of `width` solver variables that
/// start at 1-indexed `a_first` and `b_first`.
///
/// One "equal so far" auxiliary per bit position below the top; the
/// auxiliaries are only ever *forced true* by equality, never forced
/// false, so the constraint admits exactly the assignments with
/// `a ≤ b` and nothing else is excluded.
fn add_lex_leq(
    solver: &mut crate::cryptanalysis::sat::Solver,
    a_first: u32,
    b_first: u32,
    width: usize,
) {
    if width == 0 {
        return;
    }
    let aux = solver.add_vars(width as u32 - 1);
    let aux: Vec<i32> = aux.map(|v| v as i32).collect();
    let a = |t: usize| (a_first + t as u32) as i32;
    let b = |t: usize| (b_first + t as u32) as i32;
    // Top bit: a_top → b_top.
    let top = width - 1;
    solver.add_clause(vec![-a(top), b(top)]);
    // e_t means "a and b agree on every bit above t".
    for t in (0..top).rev() {
        let e_t = aux[t];
        // e_t is forced by equality at bit t+1 given e_{t+1} (or the
        // top level, which is unconditional).
        let above: Option<i32> = if t + 1 == top { None } else { Some(aux[t + 1]) };
        for (la, lb) in [(a(t + 1), b(t + 1)), (-a(t + 1), -b(t + 1))] {
            let mut clause = vec![la, lb, e_t];
            if let Some(e_above) = above {
                clause.push(-e_above);
            }
            solver.add_clause(clause);
        }
        // Under e_t: a_t → b_t.
        solver.add_clause(vec![-e_t, -a(t), b(t)]);
    }
}

/// **SAT decomposition**: the same Semaev system as
/// [`groebner_decompose`], solved by CDCL.
///
/// Models are enumerated by blocking clause: each root that fails to
/// lift to a genuine point decomposition is excluded and the instance
/// re-solved, so a final UNSAT proves no decomposition exists.  Every
/// model is checked against the original equations before use, and the
/// lifted points are re-checked in the group, so neither an encoding
/// bug nor a sign ambiguity can produce a false relation.
pub fn sat_decompose(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    index_of: &HashMap<(BigUint, BigUint), usize>,
    st: &FieldStructure,
    target: &BinaryPoint,
    m: usize,
    max_models: usize,
    macaulay_degree: Option<u32>,
) -> (Option<Vec<usize>>, SatDecompositionStats) {
    sat_decompose_with(
        kc,
        fb,
        index_of,
        st,
        target,
        m,
        max_models,
        macaulay_degree,
        SatDecompositionOptions::default(),
    )
}

/// Configurable SAT decomposition, retaining CNF as an explicit control.
/// Pass `macaulay_degree = None` for a SAT-only run without F4 preprocessing.
/// Three-point unions use the wide S4 encoder (no Macaulay preprocessing);
/// its optional group trace row is native even with CNF polynomial equations.
pub fn sat_decompose_with(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    index_of: &HashMap<(BigUint, BigUint), usize>,
    st: &FieldStructure,
    target: &BinaryPoint,
    m: usize,
    max_models: usize,
    macaulay_degree: Option<u32>,
    options: SatDecompositionOptions,
) -> (Option<Vec<usize>>, SatDecompositionStats) {
    if m == 3 && fb.uses_ambient_basis() {
        return sat_decompose_union_s4(kc, fb, index_of, target, max_models, options);
    }
    let mut stats = SatDecompositionStats::default();
    let x_r = match target {
        BinaryPoint::Affine { x, .. } => x.clone(),
        BinaryPoint::Infinity => return (None, stats),
    };
    let sys = match crate::cryptanalysis::polynomial_reuse::build_decomposition_system_reusing(
        &fb.subspace_basis,
        &x_r,
        &kc.curve.b,
        m,
        st,
    ) {
        Some(sys) => sys,
        None => return (None, stats),
    };

    // Algebraic preprocessing: hand the solver the degree-`D` Macaulay
    // consequences of the system alongside the system itself.  Each row
    // is an `F_2`-combination of multiples of the equations, so it is
    // implied and adding it cannot change the answer — but it can save
    // the search from rediscovering it.  Measured on the refuting
    // instances this cuts conflicts several-fold where the system is
    // overdetermined, and does nothing where it is not.
    //
    // The rows are **added, never substituted**.  `matrix_f4_f2` skips
    // input polynomials of degree above `D`, so replacing the system
    // with its degree-2 rows silently drops every cubic equation of a
    // chained (`m ≥ 3`) system — which turns UNSAT into SAT.
    let mut equations = sys.equations.clone();
    if options.trace_constraint {
        use crate::cryptanalysis::pq_groebner_f2::{F2BoolMono, F2BoolPoly};
        // For a rational point, delta(P)=Tr(x(P)+a), delta(O)=0,
        // is a homomorphism to F_2 (Kosters--Yeo, arXiv:1503.08001).
        // Thus sum Tr(x_i) = Tr(x_R) + (m+1)Tr(a). This is a
        // necessary group condition, not an assumption about polynomial roots.
        let rhs = absolute_trace_bit(&x_r, kc.n, &kc.curve.irreducible)
            ^ (m.is_multiple_of(2) && absolute_trace_bit(&kc.curve.a, kc.n, &kc.curve.irreducible));
        let mut terms = Vec::new();
        for (j, basis_element) in fb.subspace_basis.iter().enumerate() {
            if absolute_trace_bit(basis_element, kc.n, &kc.curve.irreducible) {
                for i in 0..m {
                    terms.push(F2BoolMono::var((i * fb.subspace_basis.len() + j) as u32));
                }
            }
        }
        if rhs {
            terms.push(F2BoolMono::one());
        }
        equations.push(F2BoolPoly::from_monos(terms, sys.n_vars));
    }
    if let Some(d) = macaulay_degree {
        if let Some(rows) = matrix_f4_f2(&sys.equations, sys.n_vars, d) {
            stats.implied_rows = rows.len();
            equations.extend(rows);
        }
    }

    // Enumerate models incrementally: encode once, then add a blocking
    // clause per rejected root and re-solve.  Re-encoding from scratch
    // each time costs a full Tseitin/XOR build per model examined, and
    // with `max_models` in the dozens that dominated the loop.
    let mut enc = encode_boolean_system_with(sys.n_vars, &equations, &[], options.encoding);
    enc.solver.conflict_budget = options.conflict_budget;
    if options.symmetry_breaking {
        let ell = fb.subspace_basis.len();
        for i in 1..m {
            add_lex_leq(
                &mut enc.solver,
                ((i - 1) * ell + 1) as u32,
                (i * ell + 1) as u32,
                ell,
            );
        }
    }
    if options.branch_on_summands {
        enc.solver
            .set_branch_priority(&(1..=(m * fb.subspace_basis.len()) as u32).collect::<Vec<_>>());
    }
    if options.restrict_to_factor_base || fb.domain != FactorBaseDomain::LinearSubspace {
        let ell = fb.subspace_basis.len();
        let legal_x: std::collections::HashSet<BigUint> = fb
            .points
            .iter()
            .filter_map(|p| match p {
                BinaryPoint::Affine { x, .. } => Some(x.to_biguint()),
                BinaryPoint::Infinity => None,
            })
            .collect();
        let mut codes: Vec<u64> = if fb.uses_ambient_basis() {
            // Union construction uses the full polynomial field basis.
            legal_x
                .iter()
                .map(|x| x.to_u64_digits().first().copied().unwrap_or(0))
                .collect()
        } else {
            (0..(1u64 << ell))
                .filter(|&code| {
                    legal_x.contains(
                        &sys.summand_x(&fb.subspace_basis, code, 0, kc.n)
                            .to_biguint(),
                    )
                })
                .collect()
        };
        codes.sort_unstable();
        codes.dedup();
        for i in 0..m {
            add_coordinate_domain(&mut enc.solver, i * ell, ell, &codes);
        }
    }
    let mut blocked: Vec<u64> = Vec::new();
    loop {
        stats.solver_calls += 1;
        if enc.trivially_unsat {
            stats.refuted = true;
            return (None, stats);
        }
        let outcome = enc.solver.solve();
        // The solver counter is cumulative across incremental calls.
        stats.conflicts = enc.solver.conflicts();
        match outcome {
            SolveResult::Unsat => {
                stats.refuted = true;
                return (None, stats);
            }
            SolveResult::Unknown => {
                stats.exhausted = true;
                return (None, stats);
            }
            SolveResult::Sat => {
                let root = enc.model_assignment();
                if !sys.equations.iter().all(|e| e.eval(root) == 0) {
                    // Fail closed: a bad model invalidates this attempt.
                    // Blocking it and later reporting UNSAT would hide a bug.
                    stats.spurious += 1;
                    stats.exhausted = true;
                    return (None, stats);
                }
                stats.models += 1;
                let xs: Vec<F2mElement> = (0..m)
                    .map(|i| sys.summand_x(&fb.subspace_basis, root, i, kc.n))
                    .collect();
                if let Some(idxs) = lift_candidate(kc, fb, index_of, &xs, target) {
                    return (Some(idxs), stats);
                }
                blocked.push(root);
                if blocked.len() >= max_models {
                    stats.exhausted = true;
                    return (None, stats);
                }
                // Forbid this assignment and search again.
                enc.solver.reset_search();
                let clause: Vec<i32> = (0..sys.n_vars)
                    .map(|i| {
                        let lit = (i + 1) as i32;
                        if (root >> i) & 1 == 1 {
                            -lit
                        } else {
                            lit
                        }
                    })
                    .collect();
                enc.solver.add_clause(clause);
            }
        }
    }
}

/// The wide symmetrised S4 encoder already supports more than 64
/// problem variables. Reuse it for three-point union decompositions;
/// the finite coordinate domain keeps each X inside the union.
fn sat_decompose_union_s4(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    index_of: &HashMap<(BigUint, BigUint), usize>,
    target: &BinaryPoint,
    max_models: usize,
    options: SatDecompositionOptions,
) -> (Option<Vec<usize>>, SatDecompositionStats) {
    use crate::cryptanalysis::semaev_sat::encode_semaev_s4;
    let mut stats = SatDecompositionStats::default();
    let BinaryPoint::Affine { x: x_r, .. } = target else {
        stats.exhausted = true;
        return (None, stats);
    };
    let mut enc = encode_semaev_s4(
        kc.n,
        kc.n,
        &kc.curve.irreducible,
        &kc.curve.b,
        x_r,
        options.encoding,
    );
    enc.solver.conflict_budget = options.conflict_budget;
    let mut codes: Vec<_> = fb
        .points
        .iter()
        .filter_map(|p| match p {
            BinaryPoint::Affine { x, .. } => Some(x.raw_bits().first().copied().unwrap_or(0)),
            BinaryPoint::Infinity => None,
        })
        .collect();
    codes.sort_unstable();
    codes.dedup();
    for i in 0..3 {
        add_coordinate_domain(&mut enc.solver, i * kc.n as usize, kc.n as usize, &codes);
    }
    if options.trace_constraint {
        let mut vars = Vec::new();
        for j in 0..kc.n {
            if absolute_trace_bit(
                &F2mElement::from_bit_positions(&[j], kc.n),
                kc.n,
                &kc.curve.irreducible,
            ) {
                for i in 0..3 {
                    vars.push(i * kc.n + j + 1);
                }
            }
        }
        let rhs = absolute_trace_bit(x_r, kc.n, &kc.curve.irreducible);
        // This optional group row is native, including when the
        // polynomial equations use the CNF control encoding.
        enc.solver.add_xor(&vars, rhs);
    }
    loop {
        stats.solver_calls += 1;
        let result = enc.solver.solve();
        stats.conflicts = enc.solver.conflicts();
        match result {
            SolveResult::Unsat => {
                stats.refuted = true;
                return (None, stats);
            }
            SolveResult::Unknown => {
                stats.exhausted = true;
                return (None, stats);
            }
            SolveResult::Sat => {
                let xs = enc.decode();
                if !crate::cryptanalysis::binary_semaev::binary_semaev_s4(
                    &xs[0],
                    &xs[1],
                    &xs[2],
                    x_r,
                    &kc.curve.b,
                    &kc.curve.irreducible,
                )
                .is_zero()
                {
                    stats.spurious += 1;
                    stats.exhausted = true;
                    return (None, stats);
                }
                stats.models += 1;
                if let Some(ids) = lift_candidate(kc, fb, index_of, &xs, target) {
                    return (Some(ids), stats);
                }
                if stats.models >= max_models {
                    stats.exhausted = true;
                    return (None, stats);
                }
                let model = enc.solver.model();
                enc.solver.reset_search();
                // The x coordinates determine all S4 auxiliaries, so
                // block the x tuple, including every failed rational lift.
                let clause = (0..3 * kc.n as usize)
                    .map(|i| {
                        let lit = (i + 1) as i32;
                        if model[i] {
                            -lit
                        } else {
                            lit
                        }
                    })
                    .collect();
                enc.solver.add_clause(clause);
            }
        }
    }
}

#[cfg(test)]
/// Turn a decomposition into a relation row over the orbit unknowns.
///
/// With `x_o := log_G ([h]·rep_o)` and
/// `P_i = (-1)^{s_i}π^{k_i}(rep_{o_i})`,
/// multiplying `R = Σ_i P_i` by the cofactor `h` gives
///
/// ```text
///     h·a + h·b·d  ≡  Σ_i (-1)^{s_i} λ^{k_i} · x_{o_i}   (mod r),
/// ```
///
/// because `π` acts as `[λ]` on the order-`r` subgroup and `[h]P_i`
/// lands in that subgroup whatever `P_i` was.
fn relation_from_decomposition(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    idxs: &[usize],
    coef_a: &BigUint,
    coef_b: &BigUint,
) -> KoblitzRelation {
    relation_from_decomposition_with_mode(kc, fb, idxs, coef_a, coef_b, true, None)
}

fn relation_from_decomposition_with_mode(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    idxs: &[usize],
    coef_a: &BigUint,
    coef_b: &BigUint,
    collapse_negation: bool,
    projected_orbits: Option<&ProjectedSignedOrbitMap>,
) -> KoblitzRelation {
    let r = &kc.subgroup_order;
    let unknowns = projected_orbits.map_or_else(
        || {
            if collapse_negation {
                fb.unknowns()
            } else {
                fb.orbits.len()
            }
        },
        |projected| projected.representatives.len(),
    );
    let mut row = vec![BigUint::zero(); unknowns];
    let mut summands = Vec::with_capacity(idxs.len());
    let mut summand_negated = Vec::with_capacity(idxs.len());
    for &i in idxs {
        let location = if let Some(projected) = projected_orbits {
            projected.orbit_of[i]
        } else if collapse_negation {
            Some(fb.signed_orbit_of[i])
        } else {
            let (o, k) = fb.orbit_of[i];
            Some((o, k, false))
        };
        let Some((o, k, negated)) = location else {
            // [h]P = O, so this summand contributes zero after the
            // relation is projected into the prime-order subgroup.
            continue;
        };
        let mut coeff = kc.lambda.modpow(&BigUint::from(k), r);
        if negated && !coeff.is_zero() {
            coeff = r - coeff;
        }
        row[o] = (&row[o] + coeff) % r;
        summands.push((o, k));
        summand_negated.push(negated);
    }
    KoblitzRelation {
        coef_a: coef_a.clone(),
        coef_b: coef_b.clone(),
        summands,
        summand_negated,
        row,
    }
}

// ── Driver ─────────────────────────────────────────────────────────

#[derive(Clone, Debug)]
struct ProjectedSignedOrbitMap {
    /// For each factor-base point P, the signed Frobenius location of
    /// [h]P. `None` means [h]P = O and therefore contributes no column.
    orbit_of: Vec<Option<(usize, u32, bool)>>,
    representatives: Vec<BinaryPoint>,
}

/// Build the quotient factor-base columns after public cofactor projection.
///
/// The ordinary factor-base orbit table can contain several columns whose
/// cofactor projections are the same point, or signed Frobenius translates
/// of one another, in the prime-order subgroup. Those columns are
/// algebraically dependent before any relation is collected. Merging them
/// uses only point multiplication, equality, negation and Frobenius; it does
/// not compute or attach a discrete logarithm.
fn projected_signed_orbit_map(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
) -> ProjectedSignedOrbitMap {
    if let Some(map) = projected_signed_orbit_map_fast(kc, fb) {
        return map;
    }
    let projected: Vec<_> = fb
        .points
        .iter()
        .map(|point| kc.mul(point, &kc.cofactor))
        .collect();
    let mut representatives: Vec<BinaryPoint> = Vec::new();
    let mut seen = HashSet::new();

    for point in &projected {
        if *point == BinaryPoint::Infinity || seen.contains(&point_key(point)) {
            continue;
        }
        let mut current = point.clone();
        let mut canonical = point.clone();
        let mut canonical_key = point_key(point);
        for _ in 0..kc.n {
            for candidate in [current.clone(), point_neg(&current)] {
                let key = point_key(&candidate);
                seen.insert(key.clone());
                if key < canonical_key {
                    canonical = candidate;
                    canonical_key = key;
                }
            }
            current = kc.frobenius(&current);
        }
        representatives.push(canonical);
    }
    representatives.sort_by_key(point_key);

    let mut location_by_key = HashMap::new();
    for (orbit, representative) in representatives.iter().enumerate() {
        let mut current = representative.clone();
        for k in 0..kc.n {
            location_by_key
                .entry(point_key(&current))
                .or_insert((orbit, k, false));
            location_by_key
                .entry(point_key(&point_neg(&current)))
                .or_insert((orbit, k, true));
            current = kc.frobenius(&current);
        }
    }
    let orbit_of = projected
        .iter()
        .map(|point| {
            if *point == BinaryPoint::Infinity {
                return None;
            }
            Some(
                *location_by_key
                    .get(&point_key(point))
                    .expect("cofactor projection was not found in its canonical orbit"),
            )
        })
        .collect();

    ProjectedSignedOrbitMap {
        orbit_of,
        representatives,
    }
}

/// [`projected_signed_orbit_map`] in single-word arithmetic, or `None`
/// when the field is too wide for it.
///
/// Same answer, point for point.  The ordering the general map
/// canonicalises and sorts by is [`point_key`], `(x + 1, y)`
/// lexicographically; [`FastPoint::pack`] is `((x + 1) << 1 | sign)`
/// with `sign` marking which of `y` and `x ^ y` is the larger, so within
/// one abscissa it separates `P` from `−P` in the same order `y` does.
/// The two orders agree, and so do the representatives they pick.
///
/// This is worth doing because the map is not a small cost: it projects
/// every base point by the cofactor and then walks each one's whole
/// signed Frobenius orbit, which at degree 53 on a 15264-point base is
/// about 1.6 million point operations — 8.2 seconds in big-integer
/// arithmetic, and a large share of a precompute that no longer spends
/// most of its time collecting.
fn projected_signed_orbit_map_fast(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
) -> Option<ProjectedSignedOrbitMap> {
    let fc = FastCurve::new(&kc.curve)?;
    let projected: Vec<FastPoint> = fb
        .points
        .par_iter()
        .map(|point| fc.mul(fc.lift(point), &kc.cofactor))
        .collect();
    let mut representatives: Vec<FastPoint> = Vec::new();
    let mut seen: HashSet<u64> = HashSet::new();
    for &point in &projected {
        if point.infinity || seen.contains(&point.pack()) {
            continue;
        }
        let mut current = point;
        let mut canonical = point;
        let mut canonical_key = point.pack();
        for _ in 0..kc.n {
            for candidate in [current, fc.neg(current)] {
                let key = candidate.pack();
                seen.insert(key);
                if key < canonical_key {
                    canonical = candidate;
                    canonical_key = key;
                }
            }
            current = fc.frobenius_k(current, kc.k);
        }
        representatives.push(canonical);
    }
    representatives.sort_unstable_by_key(|p| p.pack());

    let mut location_by_key: HashMap<u64, (usize, u32, bool)> = HashMap::new();
    for (orbit, &representative) in representatives.iter().enumerate() {
        let mut current = representative;
        for k in 0..kc.n {
            location_by_key
                .entry(current.pack())
                .or_insert((orbit, k, false));
            location_by_key
                .entry(fc.neg(current).pack())
                .or_insert((orbit, k, true));
            current = fc.frobenius_k(current, kc.k);
        }
    }
    let orbit_of = projected
        .iter()
        .map(|point| {
            if point.infinity {
                return None;
            }
            Some(
                *location_by_key
                    .get(&point.pack())
                    .expect("cofactor projection was not found in its canonical orbit"),
            )
        })
        .collect();

    Some(ProjectedSignedOrbitMap {
        orbit_of,
        representatives: representatives.into_iter().map(|p| fc.lower(p)).collect(),
    })
}

/// Number of nonzero signed-Frobenius columns remaining after every
/// factor-base point is projected into the prime-order subgroup by `[h]`.
/// This is a public algebraic property of the factor base, not a log rank.
pub fn projected_signed_orbit_count(kc: &KoblitzCurve, fb: &FrobeniusFactorBase) -> usize {
    projected_signed_orbit_map(kc, fb).representatives.len()
}

/// Tuning knobs for [`koblitz_index_calculus_dlp`].
#[derive(Clone, Debug)]
pub struct KoblitzIcOptions {
    /// Number of factor-base points a relation decomposes into.
    pub m: usize,
    /// Summands the **descent** asks for, when it should differ from
    /// `m`.  Collection and descent share the factor base and its pair
    /// table but nothing forces them to share this: a relation is worth
    /// the same however many base points it names, and the two have
    /// different cost shapes.
    ///
    /// Three summands need `3!·r/|F|³` probes of `|F|` lookups each; two
    /// need `2r/|F|²` probes of one lookup. Collection wants few probes
    /// because each costs a scalar multiplication, so it takes three.
    /// The descent walks its probes by `+G` and batches the inversions,
    /// which makes a probe nearly free, so two wins there — measured 3.7
    /// times cheaper per logarithm at degree 41 on a 10496-point base.
    ///
    /// `None` uses `m`.
    pub descent_m: Option<usize>,
    /// Factor-base summands relation collection scans per probe, when it
    /// should scan fewer than all of them.
    ///
    /// A full `m = 3` scan encounters a triple with each of its indices
    /// standing as the third summand, and keeps only the sorted witness.
    /// Scanning a window of `w` summands accepts any of those three raw
    /// witnesses and pays for `w` of them. The yield per probe falls to
    /// about `3w/|F|` of the full scan's while the cost falls to
    /// `w/|F|`, so relations per *lookup* can rise towards three times
    /// as the window shrinks. The added probes are walked instead of
    /// multiplied.
    ///
    /// Small windows eventually lose to probe arithmetic, so callers
    /// must tune the window on a separate selection run. `None` scans
    /// the whole base and draws every probe with its own scalar
    /// multiplication, the behaviour before this option was added.
    pub collection_window: Option<usize>,
    /// Index of the irreducible factor of `x^n − 1` defining the
    /// factor base.
    pub factor_index: usize,
    /// Relations to collect beyond the number of orbit unknowns.
    pub extra_relations: usize,
    /// Cap on random `(a, b)` trials during relation collection.
    pub max_trials: usize,
    /// Seed for the `(a, b)` sampler, so runs are reproducible.
    pub seed: u64,
    /// How to answer the decomposition question.
    pub strategy: DecompositionStrategy,
    /// Which algebraic engine reduces the Semaev system.  Ignored by
    /// [`DecompositionStrategy::Enumerate`].
    pub engine: SolverEngine,
    /// Experimental exact S3 decomposition on a validated Frobenius chart
    /// cover. Applies only to two-summand Groebner collection/descent. Plan
    /// construction is caller-owned precomputation and must be charged.
    pub weil_charts: Option<std::sync::Arc<super::weil_charts::WeilChartPlan>>,
    /// Splitting nodes (Gröbner-basis computations) one decomposition
    /// may spend before it gives up.  Ignored by
    /// [`DecompositionStrategy::Enumerate`].
    pub node_budget: usize,
    /// Models one [`DecompositionStrategy::Sat`] decomposition may
    /// examine before giving up.
    pub max_models: usize,
    /// Macaulay degree whose implied rows are handed to the SAT solver
    /// alongside the system, or `None` to encode the system alone.
    /// Degree 2 is cheap and helps on overdetermined instances; degree
    /// 3 buys fewer conflicts but far more clauses.
    pub sat_macaulay_degree: Option<u32>,
    /// Native-XOR/CNF, branching, domain, trace, and conflict controls
    /// for [`DecompositionStrategy::Sat`].
    pub sat_options: SatDecompositionOptions,
    /// Path to a WDSat `wdsat_solver` binary for
    /// [`DecompositionStrategy::Wdsat`].  Ignored by every other strategy.
    pub wdsat_binary: Option<std::path::PathBuf>,
    /// Soft wall-clock budget for one WDSat child process.
    pub wdsat_timeout_ms: u64,
    /// Identify `P` and `-P` as one signed Frobenius relation unknown.
    /// Disable only for a matched Frobenius-only control.
    pub collapse_negation: bool,
    /// Attempt the relation solve as soon as `unknowns + 1` equations
    /// are available and stop only when the recovered scalar verifies.
    /// Disable to retain the fixed-surplus collection control.
    pub stop_on_verified_rank: bool,
    /// Independent SAT targets launched per deterministic relation batch.
    /// Values above one use Rayon; non-SAT strategies remain serial.
    pub relation_batch_size: usize,
    /// Permit `aG+bQ=O` to recover the target scalar without the factor-base
    /// relation matrix. Disable in index-calculus benchmarks so this generic
    /// direct relation is counted and skipped rather than credited as a solve.
    pub allow_direct_relation: bool,
    /// Merge factor-base columns whose cofactor projections are equal up to
    /// signed Frobenius. This removes public algebraic dependencies without
    /// computing any factor-base logarithm.
    pub collapse_projected_orbits: bool,
    /// How [`solve_factor_base_logs`] solves the relation matrix.
    pub linear_algebra: LinearAlgebra,
    /// Macaulay degree `D` and enumerated-variable count `k` for
    /// [`DecompositionStrategy::Crossbred`], or `None` to pick `k` from
    /// the system size at each call.  Ignored by every other strategy.
    pub crossbred: Option<CrossbredParams>,
    /// Run a relation batch's Gröbner searches in lockstep and decide
    /// their Macaulay matrices together on this backend (the host kernel,
    /// a GPU, or the GPU kernel's host emulator; see
    /// [`super::f4_gpu::decider_from_spec`]) instead of one search at a
    /// time.  Every search takes the same steps either way, so relations,
    /// counters and the recovered logarithm are unchanged; only where the
    /// matrices are reduced moves.  Applies to
    /// [`DecompositionStrategy::Groebner`] collection without Weil charts;
    /// `None` keeps one search per target.
    pub f4_batch: Option<SharedDecider>,
}

/// A [`BatchDecider`] shared by the options of one run, for
/// [`KoblitzIcOptions::f4_batch`].
#[derive(Clone)]
pub struct SharedDecider(pub std::sync::Arc<std::sync::Mutex<Box<dyn BatchDecider>>>);

impl SharedDecider {
    /// Share `decider`.
    pub fn new(decider: Box<dyn BatchDecider>) -> Self {
        SharedDecider(std::sync::Arc::new(std::sync::Mutex::new(decider)))
    }

    /// The decider's label.
    pub fn name(&self) -> String {
        self.0
            .lock()
            .map(|d| d.name())
            .unwrap_or_else(|_| "poisoned".into())
    }
}

impl std::fmt::Debug for SharedDecider {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "SharedDecider({})", self.name())
    }
}

/// The linear-algebra stage of the factor-base logarithm precompute.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LinearAlgebra {
    /// Dense big-integer Gaussian elimination
    /// ([`crate::cryptanalysis::ec_index_calculus::gaussian_eliminate_mod_n`]),
    /// attempted after every new relation once there are as many rows
    /// as columns.  The reference path.
    Dense,
    /// Relation filtering followed by block Wiedemann on the reduced
    /// core ([`crate::cryptanalysis::koblitz_sparse_la`]); falls back to
    /// [`Self::Dense`] when the subgroup order does not fit the `u64`
    /// arithmetic.
    Sparse(SparseSolveOptions),
}

impl Default for KoblitzIcOptions {
    fn default() -> Self {
        Self {
            m: 2,
            descent_m: None,
            collection_window: None,
            factor_index: 0,
            extra_relations: 4,
            max_trials: 20_000,
            seed: 0x4b_6f_62_6c_69_74_7a_00, // "Koblitz\0"
            strategy: DecompositionStrategy::Groebner,
            engine: SolverEngine::default(),
            weil_charts: None,
            node_budget: 4096,
            max_models: 64,
            sat_macaulay_degree: Some(2),
            sat_options: SatDecompositionOptions::default(),
            wdsat_binary: None,
            wdsat_timeout_ms: 5_000,
            collapse_negation: true,
            stop_on_verified_rank: true,
            relation_batch_size: 1,
            allow_direct_relation: true,
            crossbred: None,
            collapse_projected_orbits: false,
            linear_algebra: LinearAlgebra::Dense,
            f4_batch: None,
        }
    }
}

/// What a run of the algorithm did.
#[derive(Clone, Debug)]
pub struct KoblitzIcReport {
    /// `|F|`.
    pub factor_base_size: usize,
    /// Number of signed `π`-orbits, i.e. the number of unknowns
    /// actually solved for.
    pub orbit_count: usize,
    /// `ℓ = ord_n(2)`, the dimension of the invariant subspace.
    pub ell: u32,
    /// Relations collected.
    pub relations: usize,
    /// Relations that raised the rank of the reduced relation matrix.
    pub independent_relations: usize,
    /// Relations that were linear combinations of earlier ones.
    pub dependent_relations: usize,
    /// Relations contradicting earlier ones.  Any nonzero value means a
    /// wrong relation was produced; the run fails closed.
    pub inconsistent_relations: usize,
    /// Pinned scalars that did not verify as `[d]G = Q`.  Any nonzero
    /// value likewise invalidates the run.
    pub verification_failures: usize,
    /// Random `(a, b)` pairs tried.
    pub trials: usize,
    /// Recovered discrete logarithm, if the run succeeded.
    pub log: Option<BigUint>,
    /// Algebraic reductions (F4 passes or Gröbner bases) computed
    /// across every decomposition attempt.
    pub reductions: usize,
    /// Decomposition branches closed by a basis reducing to `{1}` —
    /// targets rejected algebraically instead of by search.
    pub infeasible_branches: usize,
    /// CDCL solve calls across every decomposition attempt.
    pub sat_calls: usize,
    /// Targets the SAT oracle refuted outright (UNSAT).
    pub sat_refutations: usize,
    /// Inconclusive attempts (model/conflict caps or invalid models).
    pub sat_unknowns: usize,
    /// Encoding/model verification failures; any nonzero value invalidates a run.
    pub sat_invalid_models: usize,
    /// SAT models examined across relation collection.
    pub sat_models: usize,
    /// Cumulative CDCL conflicts across relation collection.
    pub sat_conflicts: u64,
    /// Time spent generating candidate targets and decomposing them.
    pub relation_collection_ns: u128,
    /// Time spent solving the final modular relation matrix.
    pub linear_algebra_ns: u128,
    /// Modular relation solves attempted, including rank-deficient ones.
    pub linear_solve_attempts: usize,
    /// Whether negation was folded into signed Frobenius columns.
    pub collapse_negation: bool,
    /// Requested SAT target batch size.
    pub relation_batch_size: usize,
    /// Relation batches actually launched.
    pub relation_batches: usize,
    /// The backend that decided the batched Gröbner searches'
    /// matrices ([`KoblitzIcOptions::f4_batch`]), if any.
    pub f4_batch_backend: Option<String>,
    /// Lockstep rounds, i.e. calls to that backend.
    pub f4_batch_rounds: usize,
    /// Macaulay matrices those rounds carried.
    pub f4_batch_requests: usize,
    /// Nanoseconds inside the backend.
    pub f4_batch_decide_ns: u128,
    /// Log recovered from R = O directly, bypassing the relation matrix.
    pub direct_relation: bool,
    /// Direct `aG+bQ=O` trials skipped because the benchmark forbade the
    /// relation-matrix bypass.
    pub direct_relations_skipped: usize,
    /// Whether the factor base's cofactor classes can sum to zero with
    /// exactly the requested number of summands.
    pub m_cofactor_admissible: bool,
    /// Whether public cofactor-projection dependencies were merged.
    pub collapse_projected_orbits: bool,
    /// Time spent constructing the public signed-Frobenius projection map.
    pub projected_orbit_construction_ns: u128,
    /// Time spent proving the requested summand count can reach the subgroup.
    pub cofactor_admission_ns: u128,
    /// Pair sums stored by the meet-in-the-middle oracle (zero for
    /// every other strategy).
    pub pair_table_entries: usize,
    /// Time spent building that table.
    pub pair_table_ns: u128,
    /// One exact record for every generated relation candidate, including
    /// refutations, capped Unknown outcomes, invalid models, and skipped direct
    /// relations. This is public synthetic replay material, not a log label.
    pub attempt_records: Vec<KoblitzRelationAttemptRecord>,
    /// Every admitted relation row in collection order. The rows are learned
    /// from point decompositions; no factor-base discrete logarithm is supplied.
    pub relation_matrix: Vec<KoblitzRelation>,
    /// Final matrix dimensions, including the target-log column.
    pub matrix_rows: usize,
    pub matrix_columns: usize,
    /// Rank of the final matrix over the prime subgroup order.
    pub terminal_matrix_rank: usize,
    /// Number of modular elimination attempts.
    pub rank_checks: usize,
    /// Rank and verification result for each modular elimination attempt.
    pub rank_history: Vec<KoblitzRankRecord>,
}

/// Terminal classification for one relation candidate.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum KoblitzRelationAttemptDisposition {
    RelationFound,
    Refuted,
    Unknown,
    InvalidModel,
    DirectSkipped,
    DirectSolved,
}

/// Exact public replay record for one relation candidate `[a]G + [b]Q`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct KoblitzRelationAttemptRecord {
    pub trial: usize,
    pub coefficient_a: BigUint,
    pub coefficient_b: BigUint,
    pub target: BinaryPoint,
    pub disposition: KoblitzRelationAttemptDisposition,
    pub decomposition_indices: Option<Vec<usize>>,
    pub solver_calls: usize,
    pub models: usize,
    pub conflicts: u64,
    pub implied_rows: usize,
}

/// One modular relation-matrix rank/solve attempt.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct KoblitzRankRecord {
    pub rows: usize,
    pub columns: usize,
    pub rank: usize,
    pub candidate_produced: bool,
    pub candidate_verified: bool,
}

struct RelationSolveResult {
    candidate: Option<BigUint>,
    rows: usize,
    columns: usize,
    rank: usize,
}

fn solve_relation_system(
    relations: &[KoblitzRelation],
    relation_unknowns: usize,
    cofactor: &BigUint,
    modulus: &BigUint,
) -> RelationSolveResult {
    let h = cofactor % modulus;
    let mut matrix = Vec::with_capacity(relations.len());
    let mut rhs = Vec::with_capacity(relations.len());
    for relation in relations {
        let mut row = relation.row.clone();
        row.push((modulus - (&h * &relation.coef_b) % modulus) % modulus);
        matrix.push(row);
        rhs.push((&h * &relation.coef_a) % modulus);
    }
    let solution = gaussian_eliminate_mod_n(&mut matrix, &mut rhs, modulus);
    let rank = matrix
        .iter()
        .filter(|row| row.iter().any(|value| !value.is_zero()))
        .count();
    RelationSolveResult {
        candidate: solution.and_then(|values| values.get(relation_unknowns).cloned()),
        rows: relations.len(),
        columns: relation_unknowns + 1,
        rank,
    }
}

enum RelationAttemptOutcome {
    Direct,
    Enumerated(Option<Vec<usize>>),
    Groebner(Option<Vec<usize>>, SolveStats),
    Sat(Option<Vec<usize>>, SatDecompositionStats),
    Crossbred(Option<Vec<usize>>, CrossbredSearchStats),
}

/// Live milestones from the existing small-curve pipeline.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum KoblitzIcEvent {
    FactorBaseStarted,
    FactorBaseReady {
        points: usize,
        orbits: usize,
    },
    /// The meet-in-the-middle pair table was built.
    PairTableReady {
        entries: usize,
    },
    RelationCollectionStarted {
        wanted: usize,
    },
    RelationProgress {
        collected: usize,
        wanted: usize,
        trials: usize,
    },
    /// Exact completion record for one generated relation candidate.
    RelationAttemptFinished {
        trial: usize,
        disposition: KoblitzRelationAttemptDisposition,
        conflicts: u64,
        collected: usize,
    },
    RelationCollectionFinished {
        collected: usize,
        trials: usize,
    },
    LinearAlgebraStarted {
        rows: usize,
        columns: usize,
    },
    LinearAlgebraFinished,
    /// The current relation matrix did not yield a candidate.
    LinearAlgebraIncomplete,
    MatrixRank {
        rows: usize,
        columns: usize,
        rank: usize,
        candidate_produced: bool,
    },
    LinearAlgebraSkipped,
    VerificationStarted,
    VerificationFinished {
        verified: bool,
    },
}

/// **Solve `Q = [d]·G`** on a Koblitz curve by index calculus over a
/// Frobenius-invariant factor base.
///
/// Returns the report; `report.log` carries the answer on success.  The
/// result is always verified by recomputing `[d]G` before it is
/// returned, so a `Some` is never a false positive.
pub fn koblitz_index_calculus_dlp(
    kc: &KoblitzCurve,
    q: &BinaryPoint,
    opts: &KoblitzIcOptions,
) -> Option<KoblitzIcReport> {
    koblitz_index_calculus_dlp_with_progress(kc, q, opts, &mut |_| {})
}

/// The same small-curve solver with synchronous progress notifications.
/// Events follow real operations and can repeat when rank checks resume collection.
pub fn koblitz_index_calculus_dlp_with_progress(
    kc: &KoblitzCurve,
    q: &BinaryPoint,
    opts: &KoblitzIcOptions,
    progress: &mut dyn FnMut(KoblitzIcEvent),
) -> Option<KoblitzIcReport> {
    progress(KoblitzIcEvent::FactorBaseStarted);
    let fb = build_frobenius_factor_base(kc, opts.factor_index)?;
    koblitz_index_calculus_dlp_observed(kc, q, &fb, opts, progress)
}

/// Run index calculus with a caller-supplied invariant factor base.
///
/// This admits explicit nonlinear orbit unions selected by a finite
/// search while retaining the same enumeration, Gröbner, and SAT
/// decomposition controls as [`koblitz_index_calculus_dlp`].
pub fn koblitz_index_calculus_dlp_with_factor_base(
    kc: &KoblitzCurve,
    q: &BinaryPoint,
    fb: &FrobeniusFactorBase,
    opts: &KoblitzIcOptions,
) -> Option<KoblitzIcReport> {
    koblitz_index_calculus_dlp_observed(kc, q, fb, opts, &mut |_| {})
}

/// Run index calculus on an arbitrary public subgroup target with a
/// caller-supplied algebraic factor base and exact synchronous progress.
/// Emits [`KoblitzIcEvent::FactorBaseReady`] but not `FactorBaseStarted`,
/// since the base was built by the caller.
pub fn koblitz_index_calculus_dlp_with_factor_base_and_progress(
    kc: &KoblitzCurve,
    q: &BinaryPoint,
    fb: &FrobeniusFactorBase,
    opts: &KoblitzIcOptions,
    progress: &mut dyn FnMut(KoblitzIcEvent),
) -> Option<KoblitzIcReport> {
    koblitz_index_calculus_dlp_observed(kc, q, fb, opts, progress)
}

fn koblitz_index_calculus_dlp_observed(
    kc: &KoblitzCurve,
    q: &BinaryPoint,
    fb: &FrobeniusFactorBase,
    opts: &KoblitzIcOptions,
    progress: &mut dyn FnMut(KoblitzIcEvent),
) -> Option<KoblitzIcReport> {
    if let Some(plan) = &opts.weil_charts {
        if opts.strategy != DecompositionStrategy::Groebner
            || opts.m != 2
            || opts.descent_m.is_some_and(|m| m != 2)
            || !plan.matches(kc, fb)
        {
            return None;
        }
    }
    let r = &kc.subgroup_order;
    let g = kc.generator().clone();
    let projection_start = std::time::Instant::now();
    let projected_orbits = opts
        .collapse_projected_orbits
        .then(|| projected_signed_orbit_map(kc, fb));
    let projected_orbit_construction_ns = projection_start.elapsed().as_nanos();
    let relation_unknowns = projected_orbits.as_ref().map_or_else(
        || {
            if opts.collapse_negation {
                fb.unknowns()
            } else {
                fb.orbits.len()
            }
        },
        |projected| projected.representatives.len(),
    );
    let admission_start = std::time::Instant::now();
    let m_cofactor_admissible = fb.m_can_decompose(kc, opts.m);
    let cofactor_admission_ns = admission_start.elapsed().as_nanos();

    let index_of = fb.index_map();
    progress(KoblitzIcEvent::FactorBaseReady {
        points: fb.points.len(),
        orbits: relation_unknowns,
    });

    let mut report = KoblitzIcReport {
        factor_base_size: fb.points.len(),
        orbit_count: relation_unknowns,
        ell: fb.ell,
        relations: 0,
        independent_relations: 0,
        dependent_relations: 0,
        inconsistent_relations: 0,
        verification_failures: 0,
        trials: 0,
        log: None,
        reductions: 0,
        infeasible_branches: 0,
        sat_calls: 0,
        sat_refutations: 0,
        sat_unknowns: 0,
        sat_invalid_models: 0,
        sat_models: 0,
        sat_conflicts: 0,
        relation_collection_ns: 0,
        linear_algebra_ns: 0,
        linear_solve_attempts: 0,
        collapse_negation: opts.collapse_negation,
        relation_batch_size: opts.relation_batch_size.max(1),
        relation_batches: 0,
        f4_batch_backend: None,
        f4_batch_rounds: 0,
        f4_batch_requests: 0,
        f4_batch_decide_ns: 0,
        direct_relation: false,
        direct_relations_skipped: 0,
        m_cofactor_admissible,
        collapse_projected_orbits: opts.collapse_projected_orbits,
        projected_orbit_construction_ns,
        cofactor_admission_ns,
        pair_table_entries: 0,
        pair_table_ns: 0,
        attempt_records: Vec::new(),
        relation_matrix: Vec::new(),
        matrix_rows: 0,
        matrix_columns: relation_unknowns + 1,
        terminal_matrix_rank: 0,
        rank_checks: 0,
        rank_history: Vec::new(),
    };
    let wanted = relation_unknowns + opts.extra_relations.max(1);
    if fb.points.is_empty() || !m_cofactor_admissible {
        progress(KoblitzIcEvent::RelationCollectionStarted { wanted });
        progress(KoblitzIcEvent::RelationCollectionFinished {
            collected: 0,
            trials: 0,
        });
        progress(KoblitzIcEvent::LinearAlgebraStarted {
            rows: 0,
            columns: relation_unknowns + 1,
        });
        report.linear_solve_attempts = 1;
        report.rank_checks = 1;
        let linear_start = std::time::Instant::now();
        let solved = solve_relation_system(&[], relation_unknowns, &kc.cofactor, r);
        report.linear_algebra_ns = linear_start.elapsed().as_nanos();
        report.matrix_rows = solved.rows;
        report.matrix_columns = solved.columns;
        report.terminal_matrix_rank = solved.rank;
        report.rank_history.push(KoblitzRankRecord {
            rows: solved.rows,
            columns: solved.columns,
            rank: solved.rank,
            candidate_produced: solved.candidate.is_some(),
            candidate_verified: false,
        });
        progress(KoblitzIcEvent::MatrixRank {
            rows: solved.rows,
            columns: solved.columns,
            rank: solved.rank,
            candidate_produced: solved.candidate.is_some(),
        });
        progress(KoblitzIcEvent::LinearAlgebraIncomplete);
        return Some(report);
    }

    // The meet-in-the-middle oracle needs its table once per run.
    let pair_table = if opts.strategy == DecompositionStrategy::PairTable {
        let start = std::time::Instant::now();
        let table = PairSumTable::build(kc, fb)?;
        report.pair_table_ns = start.elapsed().as_nanos();
        report.pair_table_entries = table.len();
        progress(KoblitzIcEvent::PairTableReady {
            entries: table.len(),
        });
        Some(table)
    } else {
        None
    };

    let field = FieldStructure::new(kc.n, &kc.curve.irreducible);
    let mut relations: Vec<KoblitzRelation> = Vec::with_capacity(wanted);
    // Incremental reduced echelon form over Z/rZ; the dense big-integer
    // solver is the fallback for a modulus wider than 64 bits.
    let mut echelon = IncrementalRelationSolver::new(relation_unknowns, r);
    let mut rng = StdRng::seed_from_u64(opts.seed);
    let r_u64 = r.to_u64_digits().first().copied().unwrap_or(1).max(2);
    let relation_start = std::time::Instant::now();

    // Record the exact incremental rank and, when allowed and pinned,
    // announce and verify the target scalar. `Some(true)` means solved;
    // `Some(false)` means a pinned scalar failed verification, which only
    // a wrong relation can cause. `None` is an honest incomplete rank check.
    let finish_incremental = |echelon: &IncrementalRelationSolver,
                              report: &mut KoblitzIcReport,
                              progress: &mut dyn FnMut(KoblitzIcEvent),
                              allow_verification: bool|
     -> Option<bool> {
        let rows = echelon.rows_seen();
        let columns = relation_unknowns + 1;
        let rank = echelon.rank();
        let candidate = echelon.target_biguint();
        let candidate_produced = candidate.is_some();
        progress(KoblitzIcEvent::LinearAlgebraStarted { rows, columns });
        report.linear_solve_attempts += 1;
        report.rank_checks += 1;
        report.matrix_rows = rows;
        report.matrix_columns = columns;
        report.terminal_matrix_rank = rank;
        progress(KoblitzIcEvent::MatrixRank {
            rows,
            columns,
            rank,
            candidate_produced,
        });
        if !allow_verification {
            report.rank_history.push(KoblitzRankRecord {
                rows,
                columns,
                rank,
                candidate_produced,
                candidate_verified: false,
            });
            progress(KoblitzIcEvent::LinearAlgebraIncomplete);
            return None;
        }
        let Some(d) = candidate else {
            report.rank_history.push(KoblitzRankRecord {
                rows,
                columns,
                rank,
                candidate_produced: false,
                candidate_verified: false,
            });
            progress(KoblitzIcEvent::LinearAlgebraIncomplete);
            return None;
        };
        progress(KoblitzIcEvent::LinearAlgebraFinished);
        progress(KoblitzIcEvent::VerificationStarted);
        let verified = kc.mul(&g, &d) == *q;
        progress(KoblitzIcEvent::VerificationFinished { verified });
        if verified {
            report.log = Some(d);
        } else {
            report.verification_failures += 1;
        }
        report.rank_history.push(KoblitzRankRecord {
            rows,
            columns,
            rank,
            candidate_produced: true,
            candidate_verified: verified,
        });
        Some(verified)
    };

    progress(KoblitzIcEvent::RelationCollectionStarted { wanted });
    while relations.len() < wanted && report.trials < opts.max_trials {
        let remaining_trials = opts.max_trials - report.trials;
        let batch_size = opts.relation_batch_size.max(1).min(remaining_trials);
        let attempts: Vec<_> = (0..batch_size)
            .map(|_| {
                let a = BigUint::from(rng.gen_range(1..r_u64));
                let b = BigUint::from(rng.gen_range(1..r_u64));
                let target = kc.add(&kc.mul(&g, &a), &kc.mul(q, &b));
                (a, b, target)
            })
            .collect();
        report.trials += attempts.len();
        report.relation_batches += 1;

        let evaluate = |(_, _, target): &(BigUint, BigUint, BinaryPoint)| {
            if *target == BinaryPoint::Infinity {
                return RelationAttemptOutcome::Direct;
            }
            match opts.strategy {
                DecompositionStrategy::Enumerate => RelationAttemptOutcome::Enumerated(decompose(
                    kc, fb, &index_of, target, opts.m, 0,
                )),
                DecompositionStrategy::PairTable => RelationAttemptOutcome::Enumerated(
                    pair_table
                        .as_ref()
                        .and_then(|table| table.decompose(kc, fb, target, opts.m)),
                ),
                DecompositionStrategy::Groebner => {
                    if let Some(plan) = &opts.weil_charts {
                        let options = SolveOptions {
                            engine: opts.engine,
                            node_budget: opts.node_budget,
                            split_rule: split_rule_default(),
                            ..Default::default()
                        };
                        let (idxs, stats) = plan
                            .decompose(kc, fb, &index_of, target, &options)
                            .expect("chart cover validated at pipeline entry");
                        return RelationAttemptOutcome::Groebner(idxs, stats.solver);
                    }
                    let (idxs, stats) = groebner_decompose(
                        kc,
                        fb,
                        &index_of,
                        &field,
                        target,
                        opts.m,
                        opts.engine,
                        opts.node_budget,
                    );
                    RelationAttemptOutcome::Groebner(idxs, stats)
                }
                DecompositionStrategy::Crossbred => {
                    let (idxs, stats) = crossbred_decompose(
                        kc,
                        fb,
                        &index_of,
                        &field,
                        target,
                        opts.m,
                        opts.crossbred,
                    );
                    RelationAttemptOutcome::Crossbred(idxs, stats)
                }
                DecompositionStrategy::Sat => {
                    let (idxs, stats) = sat_decompose_with(
                        kc,
                        fb,
                        &index_of,
                        &field,
                        target,
                        opts.m,
                        opts.max_models,
                        opts.sat_macaulay_degree,
                        opts.sat_options,
                    );
                    RelationAttemptOutcome::Sat(idxs, stats)
                }
                DecompositionStrategy::Wdsat => {
                    let binary = match &opts.wdsat_binary {
                        Some(path) => path.clone(),
                        None => {
                            return RelationAttemptOutcome::Sat(
                                None,
                                SatDecompositionStats {
                                    exhausted: true,
                                    ..SatDecompositionStats::default()
                                },
                            )
                        }
                    };
                    let wopts = crate::cryptanalysis::wdsat_oracle::WdsatSolveOptions {
                        binary,
                        work_dir: None,
                        timeout: std::time::Duration::from_millis(opts.wdsat_timeout_ms),
                        keep_anf: None,
                    };
                    let (idxs, stats) = crate::cryptanalysis::wdsat_oracle::wdsat_decompose(
                        kc, fb, &index_of, &field, target, opts.m, &wopts,
                    );
                    RelationAttemptOutcome::Sat(idxs, stats)
                }
                DecompositionStrategy::MqFes => {
                    let (idxs, stats) = crate::cryptanalysis::mq_fes::mq_fes_decompose(
                        kc, fb, &index_of, &field, target, opts.m,
                    );
                    RelationAttemptOutcome::Sat(idxs, stats)
                }
            }
        };
        // Targets are drawn serially above and consumed in order below,
        // so the outcome is independent of thread scheduling.
        let lockstep = match (&opts.f4_batch, opts.strategy, &opts.weil_charts) {
            (Some(shared), DecompositionStrategy::Groebner, None) => Some(shared),
            _ => None,
        };
        let outcomes: Vec<_> = if let Some(shared) = lockstep {
            let targets: Vec<BinaryPoint> = attempts.iter().map(|(_, _, t)| t.clone()).collect();
            let mut decider = shared.0.lock().expect("F4 batch decider poisoned");
            report.f4_batch_backend = Some(decider.name());
            let (results, rounds) = groebner_decompose_batch(
                kc,
                fb,
                &index_of,
                &field,
                &targets,
                opts.m,
                opts.engine,
                opts.node_budget,
                decider.as_mut(),
            );
            report.f4_batch_rounds += rounds.rounds;
            report.f4_batch_requests += rounds.requests;
            report.f4_batch_decide_ns += rounds.decide_ns;
            targets
                .iter()
                .zip(results)
                .map(|(t, (idxs, stats))| {
                    if *t == BinaryPoint::Infinity {
                        RelationAttemptOutcome::Direct
                    } else {
                        RelationAttemptOutcome::Groebner(idxs, stats)
                    }
                })
                .collect()
        } else if batch_size > 1 {
            attempts.par_iter().map(evaluate).collect()
        } else {
            attempts.iter().map(evaluate).collect()
        };

        let mut inconsistent = false;
        for ((a, b, target), outcome) in attempts.into_iter().zip(outcomes) {
            let trial = report.attempt_records.len() + 1;
            let mut solver_calls = 0usize;
            let mut models = 0usize;
            let mut conflicts = 0u64;
            let mut implied_rows = 0usize;
            let (found, disposition) = match outcome {
                RelationAttemptOutcome::Direct => {
                    if !opts.allow_direct_relation {
                        report.direct_relations_skipped += 1;
                        (None, KoblitzRelationAttemptDisposition::DirectSkipped)
                    } else {
                        let d = solve_for_d(&a, &b, r)?;
                        progress(KoblitzIcEvent::RelationCollectionFinished {
                            collected: relations.len(),
                            trials: report.trials,
                        });
                        progress(KoblitzIcEvent::LinearAlgebraSkipped);
                        progress(KoblitzIcEvent::VerificationStarted);
                        let verified = kc.mul(&g, &d) == *q;
                        progress(KoblitzIcEvent::VerificationFinished { verified });
                        report.attempt_records.push(KoblitzRelationAttemptRecord {
                            trial,
                            coefficient_a: a,
                            coefficient_b: b,
                            target,
                            disposition: KoblitzRelationAttemptDisposition::DirectSolved,
                            decomposition_indices: None,
                            solver_calls,
                            models,
                            conflicts,
                            implied_rows,
                        });
                        progress(KoblitzIcEvent::RelationAttemptFinished {
                            trial,
                            disposition: KoblitzRelationAttemptDisposition::DirectSolved,
                            conflicts,
                            collected: relations.len(),
                        });
                        if verified {
                            report.log = Some(d);
                            report.direct_relation = true;
                            report.relations = relations.len();
                            report.independent_relations =
                                echelon.as_ref().map_or(0, IncrementalRelationSolver::rank);
                            report.relation_matrix = relations.clone();
                            report.matrix_rows = relations.len();
                            report.terminal_matrix_rank = report.independent_relations;
                            report.relation_collection_ns = relation_start
                                .elapsed()
                                .as_nanos()
                                .saturating_sub(report.linear_algebra_ns);
                            return Some(report);
                        }
                        progress(KoblitzIcEvent::RelationCollectionStarted { wanted });
                        continue;
                    }
                }
                RelationAttemptOutcome::Enumerated(idxs) => {
                    let disposition = if idxs.is_some() {
                        KoblitzRelationAttemptDisposition::RelationFound
                    } else {
                        KoblitzRelationAttemptDisposition::Refuted
                    };
                    (idxs, disposition)
                }
                RelationAttemptOutcome::Groebner(idxs, stats) => {
                    report.reductions += stats.reductions;
                    report.infeasible_branches += stats.infeasible_branches;
                    let disposition = if idxs.is_some() {
                        KoblitzRelationAttemptDisposition::RelationFound
                    } else if stats.exhausted {
                        KoblitzRelationAttemptDisposition::Unknown
                    } else {
                        KoblitzRelationAttemptDisposition::Refuted
                    };
                    (idxs, disposition)
                }
                RelationAttemptOutcome::Crossbred(idxs, stats) => {
                    let disposition = if idxs.is_some() {
                        KoblitzRelationAttemptDisposition::RelationFound
                    } else if stats.exhausted {
                        KoblitzRelationAttemptDisposition::Unknown
                    } else {
                        KoblitzRelationAttemptDisposition::Refuted
                    };
                    (idxs, disposition)
                }
                RelationAttemptOutcome::Sat(idxs, stats) => {
                    solver_calls = stats.solver_calls;
                    models = stats.models;
                    conflicts = stats.conflicts;
                    implied_rows = stats.implied_rows;
                    report.sat_calls += stats.solver_calls;
                    report.sat_refutations += usize::from(stats.refuted);
                    report.sat_unknowns += usize::from(stats.exhausted);
                    report.sat_invalid_models += stats.spurious;
                    report.sat_models += stats.models;
                    report.sat_conflicts += stats.conflicts;
                    let disposition = if stats.spurious != 0 {
                        KoblitzRelationAttemptDisposition::InvalidModel
                    } else if idxs.is_some() {
                        KoblitzRelationAttemptDisposition::RelationFound
                    } else if stats.refuted {
                        KoblitzRelationAttemptDisposition::Refuted
                    } else {
                        KoblitzRelationAttemptDisposition::Unknown
                    };
                    let admitted =
                        if disposition == KoblitzRelationAttemptDisposition::RelationFound {
                            idxs
                        } else {
                            None
                        };
                    (admitted, disposition)
                }
            };
            let decomposition_indices = found.clone();
            if let Some(idxs) = found {
                let relation = relation_from_decomposition_with_mode(
                    kc,
                    fb,
                    &idxs,
                    &a,
                    &b,
                    opts.collapse_negation,
                    projected_orbits.as_ref(),
                );
                if let Some(echelon) = echelon.as_mut() {
                    let linear_start = std::time::Instant::now();
                    let status = echelon.add_relation(&relation, &kc.cofactor);
                    report.linear_algebra_ns += linear_start.elapsed().as_nanos();
                    match status {
                        RowStatus::Independent => report.independent_relations += 1,
                        RowStatus::Dependent => report.dependent_relations += 1,
                        RowStatus::Inconsistent => {
                            report.inconsistent_relations += 1;
                            inconsistent = true;
                        }
                    }
                }
                relations.push(relation);
            }
            report.attempt_records.push(KoblitzRelationAttemptRecord {
                trial,
                coefficient_a: a,
                coefficient_b: b,
                target,
                disposition,
                decomposition_indices,
                solver_calls,
                models,
                conflicts,
                implied_rows,
            });
            progress(KoblitzIcEvent::RelationAttemptFinished {
                trial,
                disposition,
                conflicts,
                collected: relations.len(),
            });
        }
        if report.sat_invalid_models != 0 {
            break;
        }

        progress(KoblitzIcEvent::RelationProgress {
            collected: relations.len(),
            wanted,
            trials: report.trials,
        });
        if inconsistent {
            // A relation contradicts the others: only a wrong
            // decomposition-to-row rewrite can do that.  Fail closed.
            break;
        }
        if opts.stop_on_verified_rank {
            if let Some(echelon) = echelon.as_ref() {
                if echelon.target_biguint().is_some() {
                    progress(KoblitzIcEvent::RelationCollectionFinished {
                        collected: relations.len(),
                        trials: report.trials,
                    });
                    let linear_start = std::time::Instant::now();
                    let outcome = finish_incremental(echelon, &mut report, progress, true);
                    report.linear_algebra_ns += linear_start.elapsed().as_nanos();
                    match outcome {
                        Some(true) => {
                            report.relations = relations.len();
                            report.relation_matrix = relations.clone();
                            report.relation_collection_ns = relation_start
                                .elapsed()
                                .as_nanos()
                                .saturating_sub(report.linear_algebra_ns);
                            return Some(report);
                        }
                        // Pinned but wrong: a wrong relation slipped in.
                        Some(false) => break,
                        None => {}
                    }
                }
            } else if relations.len() > relation_unknowns {
                progress(KoblitzIcEvent::RelationCollectionFinished {
                    collected: relations.len(),
                    trials: report.trials,
                });
                progress(KoblitzIcEvent::LinearAlgebraStarted {
                    rows: relations.len(),
                    columns: relation_unknowns + 1,
                });
                report.linear_solve_attempts += 1;
                report.rank_checks += 1;
                let linear_start = std::time::Instant::now();
                let solved = solve_relation_system(&relations, relation_unknowns, &kc.cofactor, r);
                report.linear_algebra_ns += linear_start.elapsed().as_nanos();
                report.matrix_rows = solved.rows;
                report.matrix_columns = solved.columns;
                report.terminal_matrix_rank = solved.rank;
                let candidate_produced = solved.candidate.is_some();
                progress(KoblitzIcEvent::MatrixRank {
                    rows: solved.rows,
                    columns: solved.columns,
                    rank: solved.rank,
                    candidate_produced,
                });
                let mut candidate_verified = false;
                let candidate = if let Some(d) = solved.candidate {
                    progress(KoblitzIcEvent::LinearAlgebraFinished);
                    progress(KoblitzIcEvent::VerificationStarted);
                    candidate_verified = kc.mul(&g, &d) == *q;
                    progress(KoblitzIcEvent::VerificationFinished {
                        verified: candidate_verified,
                    });
                    candidate_verified.then_some(d)
                } else {
                    progress(KoblitzIcEvent::LinearAlgebraIncomplete);
                    None
                };
                report.rank_history.push(KoblitzRankRecord {
                    rows: solved.rows,
                    columns: solved.columns,
                    rank: solved.rank,
                    candidate_produced,
                    candidate_verified,
                });
                if let Some(d) = candidate {
                    report.log = Some(d);
                    report.relations = relations.len();
                    report.relation_matrix = relations.clone();
                    report.relation_collection_ns = relation_start
                        .elapsed()
                        .as_nanos()
                        .saturating_sub(report.linear_algebra_ns);
                    return Some(report);
                }
                if candidate_produced {
                    report.verification_failures += 1;
                    break;
                }
                progress(KoblitzIcEvent::RelationCollectionStarted { wanted });
            }
        }
    }
    report.relation_collection_ns = relation_start
        .elapsed()
        .as_nanos()
        .saturating_sub(report.linear_algebra_ns);
    report.relations = relations.len();
    report.relation_matrix = relations.clone();
    report.matrix_rows = relations.len();
    progress(KoblitzIcEvent::RelationCollectionFinished {
        collected: relations.len(),
        trials: report.trials,
    });
    if report.verification_failures > 0 {
        return Some(report);
    }

    // Unknowns: x_1 … x_s (orbit logs) and d, in the last column.
    //   Σ_o c_o x_o  −  (h·b)·d  ≡  h·a   (mod r)
    if let Some(echelon) = echelon.as_ref() {
        let allow_verification =
            report.sat_invalid_models == 0 && report.inconsistent_relations == 0;
        let linear_start = std::time::Instant::now();
        finish_incremental(echelon, &mut report, progress, allow_verification);
        report.linear_algebra_ns += linear_start.elapsed().as_nanos();
        return Some(report);
    }
    progress(KoblitzIcEvent::LinearAlgebraStarted {
        rows: relations.len(),
        columns: relation_unknowns + 1,
    });
    report.linear_solve_attempts += 1;
    report.rank_checks += 1;
    let linear_start = std::time::Instant::now();
    let solved = solve_relation_system(&relations, relation_unknowns, &kc.cofactor, r);
    report.linear_algebra_ns += linear_start.elapsed().as_nanos();
    report.matrix_rows = solved.rows;
    report.matrix_columns = solved.columns;
    report.terminal_matrix_rank = solved.rank;
    let candidate_produced = solved.candidate.is_some();
    progress(KoblitzIcEvent::MatrixRank {
        rows: solved.rows,
        columns: solved.columns,
        rank: solved.rank,
        candidate_produced,
    });
    if report.sat_invalid_models != 0 || report.inconsistent_relations != 0 {
        report.rank_history.push(KoblitzRankRecord {
            rows: solved.rows,
            columns: solved.columns,
            rank: solved.rank,
            candidate_produced,
            candidate_verified: false,
        });
        progress(KoblitzIcEvent::LinearAlgebraIncomplete);
        return Some(report);
    }
    let Some(d) = solved.candidate else {
        report.rank_history.push(KoblitzRankRecord {
            rows: solved.rows,
            columns: solved.columns,
            rank: solved.rank,
            candidate_produced: false,
            candidate_verified: false,
        });
        progress(KoblitzIcEvent::LinearAlgebraIncomplete);
        return Some(report);
    };
    progress(KoblitzIcEvent::LinearAlgebraFinished);
    progress(KoblitzIcEvent::VerificationStarted);
    let verified = kc.mul(&g, &d) == *q;
    if verified {
        report.log = Some(d);
    } else {
        report.verification_failures += 1;
    }
    report.rank_history.push(KoblitzRankRecord {
        rows: solved.rows,
        columns: solved.columns,
        rank: solved.rank,
        candidate_produced: true,
        candidate_verified: verified,
    });
    progress(KoblitzIcEvent::VerificationFinished { verified });
    Some(report)
}

/// `d = −a / b (mod r)`, the degenerate relation `[a]G + [b]Q = O`.
fn solve_for_d(a: &BigUint, b: &BigUint, r: &BigUint) -> Option<BigUint> {
    let b_inv = mod_inverse(&(b % r), r)?;
    Some(((r - (a % r)) * b_inv) % r)
}

/// Controls for the same-target signed-Frobenius/negation quotient rho walk.
#[derive(Clone, Debug)]
pub struct KoblitzSignedRhoOptions {
    pub seed: u64,
    pub jump_count: usize,
    pub max_restarts: u32,
    pub max_iterations_per_restart: u64,
    pub progress_interval: u64,
    /// Independent walks stepped together, sharing one jump table, one
    /// table of stored points and — in the single-word arithmetic — one
    /// field inversion per round.  Collisions between two walks are
    /// exactly as useful as collisions within one, so this is the
    /// standard way to make the inversion a point addition needs cost
    /// `3 + 1/w` multiplications instead of `2n`.
    pub parallel_walks: usize,
}

impl Default for KoblitzSignedRhoOptions {
    fn default() -> Self {
        Self {
            seed: 0x52_48_4f_2d_41_55_54_4f,
            jump_count: 16,
            max_restarts: 64,
            max_iterations_per_restart: 1 << 28,
            progress_interval: 256,
            parallel_walks: 32,
        }
    }
}

/// Exact operation ledger for one signed-Frobenius rho run.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct KoblitzSignedRhoCharges {
    pub coefficient_draws: u64,
    pub setup_scalar_multiplications: u64,
    pub setup_group_additions: u64,
    pub walk_group_additions: u64,
    pub candidate_verification_scalar_multiplications: u64,
    pub canonicalizations: u64,
    pub frobenius_maps: u64,
    pub negations_examined: u64,
    pub partition_hashes: u64,
    pub collisions: u64,
    pub failed_collisions: u64,
    /// Collisions of two identical states — a fruitless cycle of the
    /// quotient walk — escaped by doubling instead of restarting.
    pub fruitless_cycles: u64,
    /// Doublings spent escaping those cycles.  Each is also counted in
    /// `walk_group_additions`, so the walk's addition ledger closes as
    /// `walk_group_additions = partition_hashes + cycle_escape_doublings`.
    pub cycle_escape_doublings: u64,
}

/// Terminal report for an arbitrary public target. A missing log is an honest
/// incomplete result and is never an UNSAT or security conclusion.
#[derive(Clone, Debug)]
pub struct KoblitzSignedRhoReport {
    pub recovered_log: Option<BigUint>,
    pub verified: bool,
    pub exhausted: bool,
    pub iterations: u64,
    pub restarts_attempted: u32,
    pub jump_table_rebuilds: u32,
    /// Walks actually stepped together per restart, after scaling the
    /// requested count down to what the instance can use.  The setup
    /// ledger closes as `setup_group_additions = (jump_count +
    /// parallel_walks) · jump_table_rebuilds`.
    pub parallel_walks: usize,
    pub setup_ns: u128,
    pub walk_ns: u128,
    pub verification_ns: u128,
    pub charges: KoblitzSignedRhoCharges,
}

/// Live signed-rho milestones. Counters are cumulative and exact.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum KoblitzSignedRhoEvent {
    RestartStarted { restart: u32 },
    JumpTableReady { restart: u32, jumps: usize },
    WalkProgress { restart: u32, iterations: u64 },
    Collision { restart: u32, verified: bool },
    Finished { verified: bool, exhausted: bool },
}

#[derive(Clone)]
struct KoblitzSignedRhoState {
    point: BinaryPoint,
    coefficient_a: BigUint,
    coefficient_b: BigUint,
}

fn canonicalize_signed_rho(
    curve: &KoblitzCurve,
    state: KoblitzSignedRhoState,
    charges: &mut KoblitzSignedRhoCharges,
) -> KoblitzSignedRhoState {
    charges.canonicalizations += 1;
    if state.point == BinaryPoint::Infinity {
        return state;
    }
    let modulus = &curve.subgroup_order;
    let mut current = state.point.clone();
    let mut lambda_k = BigUint::one();
    let mut best: Option<(Option<(BigUint, BigUint)>, BinaryPoint, BigUint)> = None;
    for _ in 0..curve.n {
        let negated = point_neg(&current);
        charges.negations_examined += 1;
        for (is_negated, candidate) in [(false, current.clone()), (true, negated)] {
            let key = match &candidate {
                BinaryPoint::Infinity => None,
                BinaryPoint::Affine { x, y } => Some((x.to_biguint(), y.to_biguint())),
            };
            let factor = if is_negated && !lambda_k.is_zero() {
                modulus - &lambda_k
            } else {
                lambda_k.clone()
            };
            if best.as_ref().is_none_or(|(old, _, _)| key < *old) {
                best = Some((key, candidate, factor));
            }
        }
        current = curve.frobenius(&current);
        charges.frobenius_maps += 1;
        lambda_k = (&lambda_k * &curve.lambda) % modulus;
    }
    let (_, point, factor) = best.expect("nonempty signed Frobenius orbit");
    KoblitzSignedRhoState {
        point,
        coefficient_a: (&state.coefficient_a * &factor) % modulus,
        coefficient_b: (&state.coefficient_b * &factor) % modulus,
    }
}

fn rho_sub_mod(left: &BigUint, right: &BigUint, modulus: &BigUint) -> BigUint {
    if left >= right {
        (left - right) % modulus
    } else {
        let difference = (right - left) % modulus;
        if difference.is_zero() {
            BigUint::zero()
        } else {
            modulus - difference
        }
    }
}

/// The jump-table partition of a canonical point.  The low bits of `x`
/// are not usable on their own: on `K_0` every subgroup point has
/// `Tr(x) = 0`, which in a basis where only `Tr(1) ≠ 0` fixes the low
/// bit of `x`, so the coordinates are mixed through a multiply first.
#[inline]
fn rho_bucket(x: u64, y: u64, jumps: usize) -> usize {
    (rho_mix(x, y) >> 32) as usize % jumps
}

/// Mix both coordinates into every bit, so that the jump partition and
/// the choice of stored points are independent of each other.
#[inline]
fn rho_mix(x: u64, y: u64) -> u64 {
    (x ^ y.rotate_left(17)).wrapping_mul(0x9e37_79b9_7f4a_7c15)
}

/// [`FastRhoWalk::escape_cycle`] in the general arithmetic: enumerate the
/// fruitless cycle, take its smallest state as the cycle's
/// representative, and double that `attempt + 1` times.
fn escape_cycle_reference(
    curve: &KoblitzCurve,
    jumps: &[(BinaryPoint, BigUint, BigUint)],
    state: KoblitzSignedRhoState,
    attempt: u32,
    charges: &mut KoblitzSignedRhoCharges,
) -> (KoblitzSignedRhoState, (BigUint, BigUint)) {
    const MAX_CYCLE: usize = 64;
    let start = point_key(&state.point);
    let mut best_key = start.clone();
    let mut best = state.clone();
    let mut current = state;
    for _ in 0..MAX_CYCLE {
        current = signed_rho_step(curve, jumps, current, charges);
        let key = point_key(&current.point);
        if key == start {
            break;
        }
        if key < best_key {
            best_key = key;
            best = current.clone();
        }
    }
    let modulus = &curve.subgroup_order;
    let two = BigUint::from(2u32);
    let mut escaped = best;
    for _ in 0..=attempt {
        charges.walk_group_additions += 1;
        charges.cycle_escape_doublings += 1;
        escaped = canonicalize_signed_rho(
            curve,
            KoblitzSignedRhoState {
                point: curve.add(&escaped.point, &escaped.point),
                coefficient_a: (&escaped.coefficient_a * &two) % modulus,
                coefficient_b: (&escaped.coefficient_b * &two) % modulus,
            },
            charges,
        );
    }
    (escaped, best_key)
}

fn signed_rho_step(
    curve: &KoblitzCurve,
    jumps: &[(BinaryPoint, BigUint, BigUint)],
    state: KoblitzSignedRhoState,
    charges: &mut KoblitzSignedRhoCharges,
) -> KoblitzSignedRhoState {
    let bucket = match &state.point {
        BinaryPoint::Infinity => 0,
        BinaryPoint::Affine { x, y } => {
            let x0 = x.to_biguint().iter_u64_digits().next().unwrap_or(0);
            let y0 = y.to_biguint().iter_u64_digits().next().unwrap_or(0);
            rho_bucket(x0, y0, jumps.len())
        }
    };
    charges.partition_hashes += 1;
    charges.walk_group_additions += 1;
    let jump = &jumps[bucket];
    canonicalize_signed_rho(
        curve,
        KoblitzSignedRhoState {
            point: curve.add(&state.point, &jump.0),
            coefficient_a: (&state.coefficient_a + &jump.1) % &curve.subgroup_order,
            coefficient_b: (&state.coefficient_b + &jump.2) % &curve.subgroup_order,
        },
        charges,
    )
}

/// Recover the discrete logarithm of an arbitrary public subgroup target with
/// a signed-Frobenius/negation quotient rho walk. The target scalar is neither
/// an input nor used for verification; success is checked only by `[d]G == Q`.
///
/// The walk runs in single-word arithmetic ([`FastCurve`]) whenever the
/// field fits, and is step-for-step the same walk as
/// [`koblitz_signed_frobenius_rho_reference`]: the same jumps, the same
/// partition, the same canonical representative and the same operation
/// ledger, so the two agree on every counter and the recovered log.
pub fn koblitz_signed_frobenius_rho_with_progress(
    curve: &KoblitzCurve,
    target: &BinaryPoint,
    options: &KoblitzSignedRhoOptions,
    progress: &mut dyn FnMut(KoblitzSignedRhoEvent),
) -> KoblitzSignedRhoReport {
    match FastCurve::new(&curve.curve) {
        Some(fc) => signed_rho_fast(&fc, curve, target, options, progress),
        None => koblitz_signed_frobenius_rho_reference(curve, target, options, progress),
    }
}

#[derive(Clone, Copy)]
struct FastRhoState {
    point: FastPoint,
    coefficient_a: u64,
    coefficient_b: u64,
}

/// The walk's constants: the curve, the subgroup order and `±λ^k mod r`
/// for every `k < n`.
struct FastRhoWalk<'a> {
    fc: &'a FastCurve,
    frobenius_degree: u32,
    orbit_length: u32,
    modulus: u64,
    lambda_pow: Vec<u64>,
    /// A point is stored when the mixed bits of its coordinates end in
    /// this many zeros, so the table holds about `2^16` of them however
    /// long the walk is.
    trail_mask: u64,
}

#[inline]
fn mulmod_u64(a: u64, b: u64, m: u64) -> u64 {
    ((a as u128 * b as u128) % m as u128) as u64
}

/// The expected number of walk steps before a useful collision, for a
/// subgroup of order `r` under the signed Frobenius group of order
/// `2n`: `√(πr/2) / √(2n)`.  The birthday bound divided by the square
/// root of the automorphism group, which is the discount the walk
/// actually gets and the figure the ledger quotes.
pub fn rho_expected_steps(r: u64, n: u32) -> f64 {
    (std::f64::consts::PI * r as f64 / 2.0).sqrt() / f64::from(2 * n).sqrt()
}

/// Slots in the direct-mapped cache of recently visited points every
/// walk keeps beside its table of stored points.  It costs one indexed
/// compare per step and catches both a fruitless cycle (the same state
/// again) and a genuine collision (the same point with different
/// coefficients) as long as the repeat is within a few thousand steps —
/// which is what the quotient walk's cycles are.  The table of stored
/// points is what catches a repeat further back than that.
const RECENT_SLOTS: usize = 1 << 12;

/// A recently visited point: its key and the coefficients it was
/// reached with.  `None` for an empty slot.
type RecentSlot<K> = Option<(K, u64, u64)>;

/// The slot a key occupies in the recent-point cache.
#[inline]
fn recent_slot(x: u64, y: u64) -> usize {
    (rho_mix(x, y) >> 20) as usize & (RECENT_SLOTS - 1)
}

/// `trail_mask` for a walk expected to take `steps` of them: a point is
/// stored once in about `2^6` of the expected walk length, so the table
/// costs a hash lookup on a small fraction of the steps and still holds
/// enough points that the walk cannot cycle past all of them.  Storing
/// far more than that makes the hash table, not the curve arithmetic,
/// the cost of the walk; storing far fewer risks a cycle with no stored
/// point in it.
fn rho_trail_mask(steps: f64) -> u64 {
    let bits = (steps.max(1.0).log2().round() as i64 - 6).clamp(0, 12) as u32;
    (1u64 << bits) - 1
}

impl FastRhoWalk<'_> {
    /// Whether this point is one of the stored ones.
    #[inline]
    fn is_stored(&self, key: (u64, u64)) -> bool {
        rho_mix(key.0, key.1) & self.trail_mask == 0
    }

    /// The smallest `(x, y)` over the signed Frobenius orbit of the
    /// state, with the coefficients scaled by the matching `±λ^k`.
    fn canonicalize(
        &self,
        state: FastRhoState,
        charges: &mut KoblitzSignedRhoCharges,
    ) -> FastRhoState {
        charges.canonicalizations += 1;
        if state.point.infinity {
            return state;
        }
        // Negation leaves `x` alone, so the orbit minimum is decided by
        // the abscissae first: walk `x` through the orbit (one squaring
        // chain, no `y`), then lift `y` to the winning power only and
        // pick the sign there.  Same representative as comparing every
        // `(x, y)` pair, at a little over half the squarings.
        let field = &self.fc.field;
        let mut x = state.point.x;
        let mut best_x = x;
        let mut best_k = 0u32;
        for k in 1..self.orbit_length {
            x = field.sqr_k(x, self.frobenius_degree);
            if x < best_x {
                best_x = x;
                best_k = k;
            }
        }
        charges.frobenius_maps += u64::from(self.orbit_length);
        charges.negations_examined += u64::from(self.orbit_length);
        let y = field.sqr_k(state.point.y, best_k * self.frobenius_degree);
        let negated_y = best_x ^ y;
        let lambda_k = self.lambda_pow[best_k as usize];
        let (point, factor) = if negated_y < y {
            (
                FastPoint::affine(best_x, negated_y),
                if lambda_k == 0 {
                    0
                } else {
                    self.modulus - lambda_k
                },
            )
        } else {
            (FastPoint::affine(best_x, y), lambda_k)
        };
        FastRhoState {
            point,
            coefficient_a: mulmod_u64(state.coefficient_a, factor, self.modulus),
            coefficient_b: mulmod_u64(state.coefficient_b, factor, self.modulus),
        }
    }

    /// **Escape a fruitless cycle.**  Negating the point flips the sign
    /// of the coefficients, so a cycle of the quotient walk can return
    /// to its own starting state: the jump sums cancel and the
    /// collision the cycle produces carries no information.  Both
    /// walkers sit on the same state when that happens, which is what
    /// [`KoblitzSignedRhoCharges::fruitless_cycles`] counts.
    ///
    /// The way out has to be a function of the **cycle**, not of the
    /// state the walkers happen to stand on: every path that later
    /// enters the same cycle must leave it at the same point, or the
    /// walk stops being a deterministic map and collisions stop
    /// appearing at all.  So enumerate the cycle, take its smallest
    /// state as the representative, and double that.  `attempt` counts
    /// how often this same cycle was escaped before, and the
    /// representative is doubled that many times — a cycle whose double
    /// walks straight back into it is still left on the next encounter.
    fn escape_cycle(
        &self,
        jumps: &[(FastPoint, u64, u64)],
        state: FastRhoState,
        attempt: u32,
        charges: &mut KoblitzSignedRhoCharges,
    ) -> (FastRhoState, (u64, u64)) {
        // Enumerate the cycle through `state` and keep its smallest
        // member.  A fruitless cycle is short (two states in the
        // overwhelming majority); the bound only stops a pathological
        // walk from enumerating a long rho cycle.
        const MAX_CYCLE: usize = 64;
        let mut best = state;
        let mut current = state;
        for _ in 0..MAX_CYCLE {
            current = self.step(jumps, current, charges);
            if (current.point.x, current.point.y) == (state.point.x, state.point.y) {
                break;
            }
            if (current.point.x, current.point.y) < (best.point.x, best.point.y) {
                best = current;
            }
        }
        let key = (best.point.x, best.point.y);
        let mut escaped = best;
        for _ in 0..=attempt {
            charges.walk_group_additions += 1;
            charges.cycle_escape_doublings += 1;
            escaped = self.canonicalize(
                FastRhoState {
                    point: self.fc.double(escaped.point),
                    coefficient_a: (escaped.coefficient_a * 2) % self.modulus,
                    coefficient_b: (escaped.coefficient_b * 2) % self.modulus,
                },
                charges,
            );
        }
        (escaped, key)
    }

    fn step(
        &self,
        jumps: &[(FastPoint, u64, u64)],
        state: FastRhoState,
        charges: &mut KoblitzSignedRhoCharges,
    ) -> FastRhoState {
        let bucket = if state.point.infinity {
            0
        } else {
            rho_bucket(state.point.x, state.point.y, jumps.len())
        };
        charges.partition_hashes += 1;
        charges.walk_group_additions += 1;
        let jump = &jumps[bucket];
        let m = self.modulus;
        self.canonicalize(
            FastRhoState {
                point: self.fc.add(state.point, jump.0),
                coefficient_a: (state.coefficient_a + jump.1) % m,
                coefficient_b: (state.coefficient_b + jump.2) % m,
            },
            charges,
        )
    }
}

/// How many walks to actually step together: every extra walk costs two
/// scalar multiplications of setup, which is wasted on an instance whose
/// whole walk is a few hundred steps.  Keep the batch well under the
/// expected walk length, and never above what the caller asked for.
fn rho_effective_walks(requested: usize, expected_steps: f64) -> usize {
    let affordable = (expected_steps / 64.0) as usize;
    requested.min(affordable.max(1)).max(1)
}

/// Turn a collision into a candidate logarithm, verify it in the general
/// arithmetic and charge the verification separately from the walk.
/// `Some(report)` means the walk is finished; `None` means the relation
/// was unusable and the caller should restart.
#[allow(clippy::too_many_arguments)]
fn rho_finish_collision(
    curve: &KoblitzCurve,
    target: &BinaryPoint,
    modulus: &BigUint,
    first: (u64, u64),
    second: (u64, u64),
    restart: u32,
    walk_started: std::time::Instant,
    report: &mut KoblitzSignedRhoReport,
    progress: &mut dyn FnMut(KoblitzSignedRhoEvent),
) -> Option<KoblitzSignedRhoReport> {
    report.charges.collisions += 1;
    let numerator = rho_sub_mod(&BigUint::from(first.0), &BigUint::from(second.0), modulus);
    let denominator = rho_sub_mod(&BigUint::from(second.1), &BigUint::from(first.1), modulus);
    let candidate =
        mod_inverse(&denominator, modulus).map(|inverse| (&numerator * inverse) % modulus);
    // Close the walk segment before collision processing.  Candidate
    // verification is a separately charged stage and must never be
    // counted in `walk_ns` as well.
    report.walk_ns += walk_started.elapsed().as_nanos();
    let verification_started = std::time::Instant::now();
    // Verified in the general arithmetic, independently of the walk.
    let verified = candidate.as_ref().is_some_and(|value| {
        report.charges.candidate_verification_scalar_multiplications += 1;
        curve.mul(curve.generator(), value) == *target
    });
    report.verification_ns += verification_started.elapsed().as_nanos();
    progress(KoblitzSignedRhoEvent::Collision { restart, verified });
    if verified {
        report.recovered_log = candidate;
        report.verified = true;
        report.exhausted = false;
        progress(KoblitzSignedRhoEvent::Finished {
            verified: true,
            exhausted: false,
        });
        return Some(report.clone());
    }
    report.charges.failed_collisions += 1;
    None
}

fn signed_rho_fast(
    fc: &FastCurve,
    curve: &KoblitzCurve,
    target: &BinaryPoint,
    options: &KoblitzSignedRhoOptions,
    progress: &mut dyn FnMut(KoblitzSignedRhoEvent),
) -> KoblitzSignedRhoReport {
    assert!(options.jump_count > 0, "rho needs at least one jump");
    assert!(options.parallel_walks > 0, "rho needs at least one walk");
    let modulus_big = &curve.subgroup_order;
    let modulus = modulus_big.to_u64_digits().first().copied().unwrap_or(0);
    assert!(modulus > 2, "rho subgroup order must fit u64");
    assert_eq!(modulus_big.bits(), 64 - modulus.leading_zeros() as u64);
    let lambda = (&curve.lambda % modulus_big)
        .to_u64_digits()
        .first()
        .copied()
        .unwrap_or(0);
    let mut lambda_pow = Vec::with_capacity(curve.n as usize);
    let mut current = 1u64;
    for _ in 0..curve.n {
        lambda_pow.push(current);
        current = mulmod_u64(current, lambda, modulus);
    }
    let walk = FastRhoWalk {
        fc,
        frobenius_degree: curve.k,
        orbit_length: curve.n,
        modulus,
        lambda_pow,
        trail_mask: rho_trail_mask(rho_expected_steps(modulus, curve.n)),
    };
    let g = fc.lift(curve.generator());
    let q = fc.lift(target);
    let mut rng = StdRng::seed_from_u64(options.seed);
    let mut report = KoblitzSignedRhoReport {
        recovered_log: None,
        verified: false,
        exhausted: true,
        iterations: 0,
        restarts_attempted: 0,
        jump_table_rebuilds: 0,
        parallel_walks: 0,
        setup_ns: 0,
        walk_ns: 0,
        verification_ns: 0,
        charges: KoblitzSignedRhoCharges::default(),
    };

    'restarts: for restart in 0..options.max_restarts {
        report.restarts_attempted += 1;
        progress(KoblitzSignedRhoEvent::RestartStarted { restart });
        let setup_started = std::time::Instant::now();
        let mut draw = |report: &mut KoblitzSignedRhoReport| {
            let a = rng.gen_range(1..modulus);
            let b = rng.gen_range(1..modulus);
            report.charges.coefficient_draws += 2;
            report.charges.setup_scalar_multiplications += 2;
            report.charges.setup_group_additions += 1;
            (fc.add(fc.mul_u64(g, a), fc.mul_u64(q, b)), a, b)
        };
        let jumps = (0..options.jump_count)
            .map(|_| draw(&mut report))
            .collect::<Vec<_>>();
        report.jump_table_rebuilds += 1;
        progress(KoblitzSignedRhoEvent::JumpTableReady {
            restart,
            jumps: jumps.len(),
        });
        report.parallel_walks =
            rho_effective_walks(options.parallel_walks, rho_expected_steps(modulus, curve.n));
        let mut states: Vec<FastRhoState> = (0..report.parallel_walks)
            .map(|_| {
                let (point, a, b) = draw(&mut report);
                walk.canonicalize(
                    FastRhoState {
                        point,
                        coefficient_a: a,
                        coefficient_b: b,
                    },
                    &mut report.charges,
                )
            })
            .collect();
        report.setup_ns += setup_started.elapsed().as_nanos();

        let walk_started = std::time::Instant::now();
        if options.max_iterations_per_restart == 0 {
            report.walk_ns += walk_started.elapsed().as_nanos();
            continue;
        }
        // Stored points, shared by every walk of this restart; the
        // recent-point cache beside it catches the short cycles.
        let mut table: HashMap<(u64, u64), (u64, u64)> = HashMap::new();
        let mut recent: Vec<RecentSlot<(u64, u64)>> = vec![None; RECENT_SLOTS];
        let mut escapes: HashMap<(u64, u64), u32> = HashMap::new();
        let mut addends: Vec<FastPoint> = Vec::with_capacity(states.len());
        let mut points: Vec<FastPoint> = Vec::with_capacity(states.len());
        let mut sums: Vec<FastPoint> = Vec::with_capacity(states.len());
        let mut scratch = BatchScratch::default();
        let mut next_progress = options.progress_interval;
        while report.iterations < options.max_iterations_per_restart {
            let mut examined = 0u64;
            for index in 0..states.len() {
                if report.iterations >= options.max_iterations_per_restart {
                    break;
                }
                report.iterations += 1;
                examined += 1;
                let state = states[index];
                let key = (state.point.x, state.point.y);
                let slot = recent_slot(key.0, key.1);
                let seen = match recent[slot] {
                    Some((k, a0, b0)) if k == key => Some((a0, b0)),
                    _ => None,
                };
                // A state the walks have already been in carries no
                // information and means one of them is cycling.
                let repeated = match seen {
                    Some(previous) => Some(previous),
                    None => {
                        recent[slot] = Some((key, state.coefficient_a, state.coefficient_b));
                        if walk.is_stored(key) {
                            match table.get(&key) {
                                Some(&previous) => Some(previous),
                                None => {
                                    table.insert(key, (state.coefficient_a, state.coefficient_b));
                                    None
                                }
                            }
                        } else {
                            None
                        }
                    }
                };
                match repeated {
                    None => {}
                    Some(previous) if previous == (state.coefficient_a, state.coefficient_b) => {
                        report.charges.fruitless_cycles += 1;
                        let attempt = escapes.get(&key).copied().unwrap_or(0);
                        let (escaped, cycle_key) =
                            walk.escape_cycle(&jumps, state, attempt, &mut report.charges);
                        *escapes.entry(cycle_key).or_insert(0) += 1;
                        states[index] = escaped;
                    }
                    Some(previous) => {
                        if let Some(outcome) = rho_finish_collision(
                            curve,
                            target,
                            modulus_big,
                            previous,
                            (state.coefficient_a, state.coefficient_b),
                            restart,
                            walk_started,
                            &mut report,
                            progress,
                        ) {
                            return outcome;
                        }
                        continue 'restarts;
                    }
                }
            }
            if options.progress_interval != 0 && report.iterations >= next_progress {
                progress(KoblitzSignedRhoEvent::WalkProgress {
                    restart,
                    iterations: report.iterations,
                });
                next_progress = report.iterations + options.progress_interval;
            }
            if report.iterations >= options.max_iterations_per_restart {
                // The advance past the final examined state is never
                // looked at, so it is never charged either.
                break;
            }
            // Advance every walk, sharing one field inversion.
            addends.clear();
            points.clear();
            for state in states.iter().take(examined as usize) {
                let bucket = if state.point.infinity {
                    0
                } else {
                    rho_bucket(state.point.x, state.point.y, jumps.len())
                };
                report.charges.partition_hashes += 1;
                report.charges.walk_group_additions += 1;
                addends.push(jumps[bucket].0);
                points.push(state.point);
            }
            sums.clear();
            fc.add_pairwise(&points, &addends, &mut sums, &mut scratch);
            for (index, &sum) in sums.iter().enumerate() {
                let state = states[index];
                let bucket = if state.point.infinity {
                    0
                } else {
                    rho_bucket(state.point.x, state.point.y, jumps.len())
                };
                let jump = &jumps[bucket];
                states[index] = walk.canonicalize(
                    FastRhoState {
                        point: sum,
                        coefficient_a: (state.coefficient_a + jump.1) % modulus,
                        coefficient_b: (state.coefficient_b + jump.2) % modulus,
                    },
                    &mut report.charges,
                );
            }
        }
        report.walk_ns += walk_started.elapsed().as_nanos();
    }
    progress(KoblitzSignedRhoEvent::Finished {
        verified: false,
        exhausted: true,
    });
    report
}

/// The general-arithmetic reference walk of
/// [`koblitz_signed_frobenius_rho_with_progress`]: the same algorithm on
/// [`BinaryPoint`]s, kept for fields wider than a word and as the
/// oracle the single-word walk is tested against.
pub fn koblitz_signed_frobenius_rho_reference(
    curve: &KoblitzCurve,
    target: &BinaryPoint,
    options: &KoblitzSignedRhoOptions,
    progress: &mut dyn FnMut(KoblitzSignedRhoEvent),
) -> KoblitzSignedRhoReport {
    assert!(options.jump_count > 0, "rho needs at least one jump");
    assert!(options.parallel_walks > 0, "rho needs at least one walk");
    let modulus = &curve.subgroup_order;
    let modulus_u64 = modulus.to_u64_digits().first().copied().unwrap_or(0);
    assert!(modulus_u64 > 2, "rho subgroup order must fit u64");
    let mut rng = StdRng::seed_from_u64(options.seed);
    let mut report = KoblitzSignedRhoReport {
        recovered_log: None,
        verified: false,
        exhausted: true,
        iterations: 0,
        restarts_attempted: 0,
        jump_table_rebuilds: 0,
        parallel_walks: 0,
        setup_ns: 0,
        walk_ns: 0,
        verification_ns: 0,
        charges: KoblitzSignedRhoCharges::default(),
    };

    'restarts: for restart in 0..options.max_restarts {
        report.restarts_attempted += 1;
        progress(KoblitzSignedRhoEvent::RestartStarted { restart });
        let setup_started = std::time::Instant::now();
        let mut draw = |report: &mut KoblitzSignedRhoReport| {
            let a = BigUint::from(rng.gen_range(1..modulus_u64));
            let b = BigUint::from(rng.gen_range(1..modulus_u64));
            report.charges.coefficient_draws += 2;
            report.charges.setup_scalar_multiplications += 2;
            report.charges.setup_group_additions += 1;
            let point = curve.add(&curve.mul(curve.generator(), &a), &curve.mul(target, &b));
            (point, a, b)
        };
        let jumps = (0..options.jump_count)
            .map(|_| draw(&mut report))
            .collect::<Vec<_>>();
        report.jump_table_rebuilds += 1;
        progress(KoblitzSignedRhoEvent::JumpTableReady {
            restart,
            jumps: jumps.len(),
        });
        report.parallel_walks = rho_effective_walks(
            options.parallel_walks,
            rho_expected_steps(modulus_u64, curve.n),
        );
        let mut states: Vec<KoblitzSignedRhoState> = (0..report.parallel_walks)
            .map(|_| {
                let (point, a, b) = draw(&mut report);
                canonicalize_signed_rho(
                    curve,
                    KoblitzSignedRhoState {
                        point,
                        coefficient_a: a,
                        coefficient_b: b,
                    },
                    &mut report.charges,
                )
            })
            .collect();
        report.setup_ns += setup_started.elapsed().as_nanos();

        let walk_started = std::time::Instant::now();
        if options.max_iterations_per_restart == 0 {
            report.walk_ns += walk_started.elapsed().as_nanos();
            continue;
        }
        let trail_mask = rho_trail_mask(rho_expected_steps(modulus_u64, curve.n));
        let coordinates = |point: &BinaryPoint| -> (u64, u64) {
            match point {
                BinaryPoint::Infinity => (0, 0),
                BinaryPoint::Affine { x, y } => (
                    x.to_biguint().iter_u64_digits().next().unwrap_or(0),
                    y.to_biguint().iter_u64_digits().next().unwrap_or(0),
                ),
            }
        };
        let mut table: HashMap<(BigUint, BigUint), (u64, u64)> = HashMap::new();
        let mut recent: Vec<RecentSlot<(BigUint, BigUint)>> = vec![None; RECENT_SLOTS];
        let mut escapes: HashMap<(BigUint, BigUint), u32> = HashMap::new();
        let mut next_progress = options.progress_interval;
        while report.iterations < options.max_iterations_per_restart {
            let mut examined = 0usize;
            for index in 0..states.len() {
                if report.iterations >= options.max_iterations_per_restart {
                    break;
                }
                report.iterations += 1;
                examined += 1;
                let state = states[index].clone();
                let key = point_key(&state.point);
                let (x0, y0) = coordinates(&state.point);
                let coefficients = (
                    state
                        .coefficient_a
                        .to_u64_digits()
                        .first()
                        .copied()
                        .unwrap_or(0),
                    state
                        .coefficient_b
                        .to_u64_digits()
                        .first()
                        .copied()
                        .unwrap_or(0),
                );
                let slot = recent_slot(x0, y0);
                let seen = match &recent[slot] {
                    Some((k, a0, b0)) if *k == key => Some((*a0, *b0)),
                    _ => None,
                };
                let repeated = match seen {
                    Some(previous) => Some(previous),
                    None => {
                        recent[slot] = Some((key.clone(), coefficients.0, coefficients.1));
                        if rho_mix(x0, y0) & trail_mask == 0 {
                            match table.get(&key) {
                                Some(&previous) => Some(previous),
                                None => {
                                    table.insert(key.clone(), coefficients);
                                    None
                                }
                            }
                        } else {
                            None
                        }
                    }
                };
                match repeated {
                    None => {}
                    Some(previous) if previous == coefficients => {
                        report.charges.fruitless_cycles += 1;
                        let attempt = escapes.get(&key).copied().unwrap_or(0);
                        let (escaped, cycle_key) = escape_cycle_reference(
                            curve,
                            &jumps,
                            state,
                            attempt,
                            &mut report.charges,
                        );
                        *escapes.entry(cycle_key).or_insert(0) += 1;
                        states[index] = escaped;
                    }
                    Some(previous) => {
                        if let Some(outcome) = rho_finish_collision(
                            curve,
                            target,
                            modulus,
                            previous,
                            coefficients,
                            restart,
                            walk_started,
                            &mut report,
                            progress,
                        ) {
                            return outcome;
                        }
                        continue 'restarts;
                    }
                }
            }
            if options.progress_interval != 0 && report.iterations >= next_progress {
                progress(KoblitzSignedRhoEvent::WalkProgress {
                    restart,
                    iterations: report.iterations,
                });
                next_progress = report.iterations + options.progress_interval;
            }
            if report.iterations >= options.max_iterations_per_restart {
                // The advance past the final examined state is never
                // looked at, so it is never charged either.
                break;
            }
            for index in 0..examined {
                states[index] =
                    signed_rho_step(curve, &jumps, states[index].clone(), &mut report.charges);
            }
        }
        report.walk_ns += walk_started.elapsed().as_nanos();
    }
    progress(KoblitzSignedRhoEvent::Finished {
        verified: false,
        exhausted: true,
    });
    report
}

// ── Cost model ─────────────────────────────────────────────────────

/// Predicted savings from the Frobenius structure, in the units the
/// GGMP paper states them.
#[derive(Clone, Debug)]
pub struct KoblitzSpeedup {
    /// Extension degree.
    pub n: u32,
    /// Factor-base size `|F|`.
    pub factor_base_size: usize,
    /// Unknowns after collapsing signed `π`-orbits.
    pub unknowns: usize,
    /// `|F| / unknowns` — the measured relation-collection speed-up,
    /// which is generically `≈ 2n` after Frobenius and negation.
    pub relation_collection_speedup: f64,
    /// `(|F| / unknowns)²` — the measured linear-algebra speed-up for a
    /// quadratic-cost sparse solve, generically `≈ 4n²` after both
    /// identifications. The Frobenius contribution alone is `n²`.
    pub linear_algebra_speedup: f64,
    /// `m!`, the symmetry-breaking saving in the decomposition search.
    pub symmetry_breaking_factor: f64,
    /// The Gallant–Lambert–Vanstone / Wiener–Zuccherato speed-up that
    /// Pollard rho already gets from the same endomorphism, `√(2n)`.
    pub rho_speedup: f64,
}

/// Cost model for a Frobenius-invariant index calculus on `n`, a factor
/// base of `fb_size` points collapsing to `unknowns` signed orbits, with
/// `m`-point decompositions.
///
/// The point of the table is the comparison in the paper's conclusion:
/// index calculus gains more from the Koblitz structure than rho does
/// (`n` and `n²` from Frobenius, plus the standard negation quotient,
/// versus `√(2n)`) — and yet stays the worse attack for
/// the curves anyone deploys, because its un-accelerated cost is so
/// much higher to begin with.
pub fn koblitz_speedup_model(n: u32, fb_size: usize, unknowns: usize, m: usize) -> KoblitzSpeedup {
    let ratio = if unknowns == 0 {
        1.0
    } else {
        fb_size as f64 / unknowns as f64
    };
    let fact = (1..=m).map(|i| i as f64).product::<f64>();
    KoblitzSpeedup {
        n,
        factor_base_size: fb_size,
        unknowns,
        relation_collection_speedup: ratio,
        linear_algebra_speedup: ratio * ratio,
        symmetry_breaking_factor: fact,
        rho_speedup: (2.0 * n as f64).sqrt(),
    }
}

// ── Factor-base logarithms and individual-logarithm descent ─────────
//
// A CADO-NFS-style pipeline separates two costs that the plain driver
// above conflates.  The plain driver bakes the target `Q` into every
// relation (`R = [a]G + [b]Q`) and rebuilds the whole relation matrix
// per target.  A production pipeline instead:
//
//   1. **precomputes**, once per curve and factor base, the discrete
//      logarithm of every relation column — the *factor-base logarithm
//      database*;
//   2. **descends** each target with a single relation, reading the
//      column logs out of that database — the *individual logarithm*.
//
// Both stages live here because they need the private projected-orbit
// map and relation builder.  Only the projected representation is
// supported (the `ic` default): its columns are the canonical
// cofactor projections `R_o ∈ ⟨G⟩`, so a column logarithm
// `x_o = log_G R_o` is a genuine discrete log that certifies itself —
// `[x_o]G == R_o` — with no reliance on the collection being correct.

/// A solved factor-base logarithm database: for each relation column,
/// the point `R_o ∈ ⟨G⟩` and its discrete logarithm `x_o = log_G R_o`.
///
/// Reusable across every target on the same curve and factor base.  The
/// table is self-certifying: [`Self::verify`] rechecks `[x_o]G == R_o`
/// for every column with one scalar multiplication each, so a loaded
/// table cannot silently carry a wrong logarithm.
#[derive(Clone, Debug)]
pub struct FactorBaseLogTable {
    /// `(R_o, log_G R_o)` per relation column, in projected-column order.
    pub columns: Vec<(BinaryPoint, BigUint)>,
}

impl FactorBaseLogTable {
    /// The number of column logarithms.
    pub fn len(&self) -> usize {
        self.columns.len()
    }

    /// Whether the table has no columns.
    pub fn is_empty(&self) -> bool {
        self.columns.is_empty()
    }

    /// Recheck every stored logarithm by `[x_o]G == R_o`.  Cheap
    /// (one scalar multiplication per column) and total: it depends on
    /// nothing but the curve and the table itself.
    pub fn verify(&self, kc: &KoblitzCurve) -> bool {
        let g = kc.generator();
        self.columns.iter().all(|(point, log)| {
            *point != BinaryPoint::Infinity && log < &kc.subgroup_order && &kc.mul(g, log) == point
        })
    }

    /// Look a column point's logarithm up by point identity.
    fn log_of(&self) -> HashMap<(BigUint, BigUint), BigUint> {
        self.columns
            .iter()
            .map(|(point, log)| (point_key(point), log.clone()))
            .collect()
    }
}

/// What a factor-base logarithm precomputation did.
#[derive(Clone, Debug, Default)]
pub struct LogTableReport {
    /// Relation columns solved (equals the table length on success).
    pub columns: usize,
    /// `[a]G` probes drawn.
    pub trials: usize,
    /// Probes that decomposed into a usable relation.
    pub relations: usize,
    /// Whether every column logarithm verified as `[x_o]G == R_o`.
    pub verified: bool,
    /// Linear solves attempted (each on the relations collected so far).
    pub solve_attempts: usize,
    /// Wall time spent in those solves.
    pub linear_algebra_seconds: f64,
    /// Whether the sparse path (filtering + block Wiedemann) was used.
    pub sparse: bool,
    /// Filtering and block Wiedemann statistics of the last sparse
    /// attempt, when the sparse path was used.
    pub sparse_report: Option<SparseSolveReport>,
    /// Wall time spent drawing and decomposing probes (or, for a solve
    /// from collected relations, re-verifying them).
    pub collection_seconds: f64,
    /// Collected relations that failed re-verification in the group.
    pub rejected_relations: usize,
    /// Collected relations identical to an earlier one.
    pub duplicate_relations: usize,
}

/// Dispatch one decomposition question `target = Σ_{i} P_{i}` (`m`
/// summands) to the requested oracle, mirroring the driver's own
/// dispatch.  A prebuilt pair table is used when supplied.
#[allow(clippy::too_many_arguments)]
fn decompose_once(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    index_of: &HashMap<(BigUint, BigUint), usize>,
    field: &FieldStructure,
    pair: Option<&PairSumTable>,
    opts: &KoblitzIcOptions,
    target: &BinaryPoint,
) -> Option<Vec<usize>> {
    if let Some(plan) = &opts.weil_charts {
        if opts.strategy != DecompositionStrategy::Groebner || opts.m != 2 || !plan.matches(kc, fb)
        {
            return None;
        }
    }
    match opts.strategy {
        DecompositionStrategy::Enumerate => decompose(kc, fb, index_of, target, opts.m, 0),
        DecompositionStrategy::PairTable => pair
            .expect("pair table required")
            .decompose(kc, fb, target, opts.m),
        DecompositionStrategy::Crossbred => {
            crossbred_decompose(kc, fb, index_of, field, target, opts.m, opts.crossbred).0
        }
        DecompositionStrategy::Groebner => {
            if let Some(plan) = &opts.weil_charts {
                let options = SolveOptions {
                    engine: opts.engine,
                    node_budget: opts.node_budget,
                    split_rule: split_rule_default(),
                    ..Default::default()
                };
                return plan
                    .decompose(kc, fb, index_of, target, &options)
                    .and_then(|(ids, _)| ids);
            }
            groebner_decompose(
                kc,
                fb,
                index_of,
                field,
                target,
                opts.m,
                opts.engine,
                opts.node_budget,
            )
            .0
        }
        DecompositionStrategy::Sat => {
            sat_decompose_with(
                kc,
                fb,
                index_of,
                field,
                target,
                opts.m,
                opts.max_models,
                opts.sat_macaulay_degree,
                opts.sat_options,
            )
            .0
        }
        DecompositionStrategy::Wdsat => {
            let binary = opts.wdsat_binary.as_ref()?;
            let wopts = crate::cryptanalysis::wdsat_oracle::WdsatSolveOptions {
                binary: binary.clone(),
                work_dir: None,
                timeout: std::time::Duration::from_millis(opts.wdsat_timeout_ms),
                keep_anf: None,
            };
            crate::cryptanalysis::wdsat_oracle::wdsat_decompose(
                kc, fb, index_of, field, target, opts.m, &wopts,
            )
            .0
        }
        DecompositionStrategy::MqFes => {
            crate::cryptanalysis::mq_fes::mq_fes_decompose(kc, fb, index_of, field, target, opts.m)
                .0
        }
    }
}

// ── Relation collection in work units ──────────────────────────────

/// One relation `[a]G = Σ_i P_{points[i]}` as a collector reports it:
/// the trial number, the probe scalar and the factor-base point indices,
/// nothing else.  A consumer rebuilds the row and re-checks the equation
/// in the group ([`verify_collected_relation`]) before using it, so a
/// corrupt or forged relation from a remote worker cannot enter the
/// linear algebra.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct CollectedRelation {
    /// Trial index within the seed's probe sequence.
    pub trial: u64,
    /// The probe scalar, `R = [a]G`.
    pub a: u64,
    /// Indices into the factor base, `R = Σ points[i]` (with repetition).
    pub points: Vec<usize>,
}

/// A slice `[start, start + count)` of a seed's probe sequence.  Probe
/// `t` depends only on `(seed, t)` ([`probe_scalar`]), so any partition
/// of the trial range into units yields the same relations, in any
/// order, on any number of machines.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct RelationWorkUnit {
    pub seed: u64,
    pub start: u64,
    pub count: u64,
}

/// What collecting one work unit did.
#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct CollectionReport {
    /// Probes drawn.
    pub trials: usize,
    /// Probes that decomposed.
    pub relations: usize,
    /// Factor-base summands scanned across every probe: the lookups the
    /// unit actually paid for, which a window makes smaller than
    /// `trials × |F|`.
    #[serde(default)]
    pub summands_scanned: u64,
    pub elapsed_seconds: f64,
}

/// The probe scalar of trial `t` under `seed`: uniform in `1..r`, drawn
/// from a generator keyed by the pair, so trials are independent of one
/// another and of the order in which they are visited.
pub fn probe_scalar(seed: u64, trial: u64, r_u64: u64) -> u64 {
    let key =
        seed ^ 0x5052_4f42_4553_4551 ^ trial.wrapping_mul(0x9e37_79b9_7f4a_7c15).rotate_left(17);
    StdRng::seed_from_u64(key).gen_range(1..r_u64.max(2))
}

/// Trials sharing one scalar multiplication when the collector walks
/// its probes.  A run costs one multiplication and `PROBE_RUN − 1`
/// additions, so the arithmetic per probe falls by roughly the run
/// length while the run stays short enough to keep the trial range
/// worth parallelising.
const PROBE_RUN: u64 = 64;

/// The step a walked run takes between consecutive trials, fixed by the
/// seed so the sequence is reproducible.
fn probe_run_stride(seed: u64, r_u64: u64) -> u64 {
    StdRng::seed_from_u64(seed ^ 0x5354_5249_4445_5f30).gen_range(1..r_u64.max(2))
}

/// The probe scalar of trial `t` when the collector walks its probes:
/// run `t / PROBE_RUN` starts at [`probe_scalar`] of the run index and
/// each trial within it adds one [`probe_run_stride`].  Still a function
/// of `(seed, t)` alone, so any partition of the trial range yields the
/// same relations — a unit that starts mid-run simply pays for its own
/// first multiplication.
/// A run's scalar may come back as `0`, meaning the probe is the point
/// at infinity; such a trial decomposes into nothing and reports no
/// relation, so every reported `a` still satisfies `0 < a < r`.
fn walked_probe_scalar(seed: u64, trial: u64, r_u64: u64) -> u64 {
    let r = r_u64.max(2) as u128;
    let anchor = probe_scalar(seed, trial / PROBE_RUN, r_u64) as u128;
    let offset = (trial % PROBE_RUN) as u128 * probe_run_stride(seed, r_u64) as u128;
    ((anchor + offset) % r) as u64
}

enum PairSource<'a> {
    None,
    Owned(Box<PairSumTable>),
    Borrowed(&'a PairSumTable),
}

/// Decomposition state shared by every trial of a collector: the point
/// index map, the field structure and, for the pair-table oracle, the
/// table.  Built once per process and reused across work units.
pub struct RelationCollector<'a> {
    kc: &'a KoblitzCurve,
    fb: &'a FrobeniusFactorBase,
    opts: &'a KoblitzIcOptions,
    index_of: HashMap<(BigUint, BigUint), usize>,
    field: FieldStructure,
    pair: PairSource<'a>,
    /// Single-word curve and lifted generator when the field fits.
    fast: Option<(FastCurve, FastPoint)>,
    r_u64: u64,
}

/// Trials collected per batch by [`solve_factor_base_logs`] between
/// solve attempts; every batch runs in parallel.
pub const PRECOMPUTE_BATCH_TRIALS: usize = 64;

impl<'a> RelationCollector<'a> {
    /// `None` when the base cannot decompose with `opts.m` summands or
    /// the field is too wide for the pair table.
    pub fn new(
        kc: &'a KoblitzCurve,
        fb: &'a FrobeniusFactorBase,
        opts: &'a KoblitzIcOptions,
    ) -> Option<Self> {
        let pair = if opts.strategy == DecompositionStrategy::PairTable {
            PairSource::Owned(Box::new(PairSumTable::build(kc, fb)?))
        } else {
            PairSource::None
        };
        Self::with_pair(kc, fb, opts, pair)
    }

    /// Like [`Self::new`] but reusing a pair table the caller already
    /// built (required when the strategy is
    /// [`DecompositionStrategy::PairTable`]).
    pub fn with_pair_table(
        kc: &'a KoblitzCurve,
        fb: &'a FrobeniusFactorBase,
        opts: &'a KoblitzIcOptions,
        pair: Option<&'a PairSumTable>,
    ) -> Option<Self> {
        let pair = match (opts.strategy, pair) {
            (DecompositionStrategy::PairTable, Some(p)) => PairSource::Borrowed(p),
            (DecompositionStrategy::PairTable, None) => return None,
            _ => PairSource::None,
        };
        Self::with_pair(kc, fb, opts, pair)
    }

    fn with_pair(
        kc: &'a KoblitzCurve,
        fb: &'a FrobeniusFactorBase,
        opts: &'a KoblitzIcOptions,
        pair: PairSource<'a>,
    ) -> Option<Self> {
        if !fb.m_can_decompose(kc, opts.m) {
            return None;
        }
        let r_u64 = kc
            .subgroup_order
            .to_u64_digits()
            .first()
            .copied()
            .unwrap_or(1)
            .max(2);
        let fast = FastCurve::new(&kc.curve).map(|fc| {
            let g = fc.lift(kc.generator());
            (fc, g)
        });
        Some(Self {
            kc,
            fb,
            opts,
            index_of: fb.index_map(),
            field: FieldStructure::new(kc.n, &kc.curve.irreducible),
            pair,
            fast,
            r_u64,
        })
    }

    /// The pair table, when the oracle uses one.
    pub fn pair_table(&self) -> Option<&PairSumTable> {
        match &self.pair {
            PairSource::None => None,
            PairSource::Owned(p) => Some(p),
            PairSource::Borrowed(p) => Some(p),
        }
    }

    /// The largest probe scalar drawn, `r − 1` (or 1 for a degenerate order).
    pub fn scalar_bound(&self) -> u64 {
        self.r_u64
    }

    /// The window of factor-base summands a probe scans, and whether
    /// probes are walked: `Some(w)` when
    /// [`KoblitzIcOptions::collection_window`] asks for fewer summands
    /// than the base has and the fast oracle can honour it.
    fn window(&self) -> Option<usize> {
        let w = self.opts.collection_window?;
        if self.opts.m != 3
            || self.opts.strategy != DecompositionStrategy::PairTable
            || self.fast.is_none()
            || self.pair_table().is_none()
            || w == 0
            || w >= self.fb.points.len()
        {
            return None;
        }
        Some(w)
    }

    /// Collect the relations of one work unit, trials in parallel,
    /// returned in trial order.
    pub fn collect(&self, unit: RelationWorkUnit) -> (Vec<CollectedRelation>, CollectionReport) {
        if let Some(window) = self.window() {
            return self.collect_walked(unit, window);
        }
        let begin = std::time::Instant::now();
        let g = self.kc.generator();
        let end = unit.start.saturating_add(unit.count);
        let probe = |t: u64| -> Option<CollectedRelation> {
            let a = probe_scalar(unit.seed, t, self.r_u64);
            let points = match (&self.fast, self.pair_table()) {
                // [a]G and the decomposition in single-word arithmetic.
                (Some((fc, g_fast)), Some(pair))
                    if self.opts.strategy == DecompositionStrategy::PairTable =>
                {
                    let target = fc.mul_u64(*g_fast, a);
                    if target.infinity {
                        return None;
                    }
                    pair.decompose_fast(target, self.opts.m)?
                }
                _ => {
                    let target = match &self.fast {
                        Some((fc, g_fast)) => fc.lower(fc.mul_u64(*g_fast, a)),
                        None => self.kc.mul(g, &BigUint::from(a)),
                    };
                    if target == BinaryPoint::Infinity {
                        return None;
                    }
                    decompose_once(
                        self.kc,
                        self.fb,
                        &self.index_of,
                        &self.field,
                        self.pair_table(),
                        self.opts,
                        &target,
                    )?
                }
            };
            Some(CollectedRelation {
                trial: t,
                a,
                points,
            })
        };
        let mut relations: Vec<CollectedRelation> = (unit.start..end)
            .into_par_iter()
            .filter_map(probe)
            .collect();
        relations.sort_by_key(|r| r.trial);
        let trials = (end - unit.start) as usize;
        let report = CollectionReport {
            trials,
            relations: relations.len(),
            summands_scanned: if self.opts.m == 3
                && self.opts.strategy == DecompositionStrategy::PairTable
            {
                trials as u64 * self.fb.points.len() as u64
            } else {
                0
            },
            elapsed_seconds: begin.elapsed().as_secs_f64(),
        };
        (relations, report)
    }

    /// [`Self::collect`] with a windowed third summand and walked
    /// probes: trials are grouped into runs of [`PROBE_RUN`], each run
    /// paying one scalar multiplication and then stepping by the seed's
    /// stride, and each probe scanning `window` summands from a rotating
    /// offset so no column is favoured.  Runs are independent, so the
    /// unit still parallelises and still depends only on `(seed, t)`.
    fn collect_walked(
        &self,
        unit: RelationWorkUnit,
        window: usize,
    ) -> (Vec<CollectedRelation>, CollectionReport) {
        let begin = std::time::Instant::now();
        let end = unit.start.saturating_add(unit.count);
        if end == unit.start {
            return (
                Vec::new(),
                CollectionReport {
                    trials: 0,
                    relations: 0,
                    summands_scanned: 0,
                    elapsed_seconds: begin.elapsed().as_secs_f64(),
                },
            );
        }
        let (fc, g_fast) = self.fast.as_ref().expect("window() checked the fast curve");
        let pair = self.pair_table().expect("window() checked the pair table");
        let base = self.fb.points.len();
        let stride = probe_run_stride(unit.seed, self.r_u64);
        let stride_point = fc.mul_u64(*g_fast, stride);
        // Runs of the probe sequence this unit covers, clipped to it.
        let first_run = unit.start / PROBE_RUN;
        let last_run = end.saturating_sub(1) / PROBE_RUN;
        let mut relations: Vec<CollectedRelation> = (first_run..=last_run)
            .into_par_iter()
            .flat_map_iter(|run| {
                let run_start = (run * PROBE_RUN).max(unit.start);
                let run_end = ((run + 1) * PROBE_RUN).min(end);
                let mut a = walked_probe_scalar(unit.seed, run_start, self.r_u64);
                let mut point = fc.mul_u64(*g_fast, a);
                let mut found = Vec::new();
                for t in run_start..run_end {
                    if !point.infinity && a != 0 {
                        // A rotating offset, so no column is favoured by
                        // sitting where the window always starts.
                        let offset =
                            pair_filter_hash(unit.seed ^ t.wrapping_mul(0x9e37_79b9_7f4a_7c15))
                                as usize
                                % base;
                        if let Some(points) = pair.decompose_fast_window(point, 3, offset, window) {
                            found.push(CollectedRelation {
                                trial: t,
                                a,
                                points,
                            });
                        }
                    }
                    // The next trial of the run is one stride further
                    // along, matching [`walked_probe_scalar`] without
                    // re-deriving the run's anchor.
                    a = ((a as u128 + stride as u128) % self.r_u64.max(2) as u128) as u64;
                    point = fc.add(point, stride_point);
                }
                found
            })
            .collect();
        relations.sort_by_key(|r| r.trial);
        let trials = (end - unit.start) as usize;
        let report = CollectionReport {
            trials,
            relations: relations.len(),
            summands_scanned: trials as u64 * window as u64,
            elapsed_seconds: begin.elapsed().as_secs_f64(),
        };
        (relations, report)
    }
}

/// Re-check a reported relation in the group: exactly `m` indices, all
/// in range, `0 < a < r`, and `[a]G == Σ P_i`.
pub fn verify_collected_relation(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    m: usize,
    rel: &CollectedRelation,
) -> bool {
    let r_u64 = kc
        .subgroup_order
        .to_u64_digits()
        .first()
        .copied()
        .unwrap_or(0);
    if rel.points.len() != m || rel.a == 0 || rel.a >= r_u64 {
        return false;
    }
    if rel.points.iter().any(|&i| i >= fb.points.len()) {
        return false;
    }
    let mut sum = BinaryPoint::Infinity;
    for &i in &rel.points {
        sum = kc.add(&sum, &fb.points[i]);
    }
    sum != BinaryPoint::Infinity && sum == kc.mul(kc.generator(), &BigUint::from(rel.a))
}

/// The relation rows of a logarithm precompute, dense or sparse per the
/// options, and the solve attempt shared by every entry point.
struct LogSystem<'a> {
    kc: &'a KoblitzCurve,
    fb: &'a FrobeniusFactorBase,
    opts: &'a KoblitzIcOptions,
    projected: ProjectedSignedOrbitMap,
    n_cols: usize,
    r_u64: u64,
    h: BigUint,
    sparse_opts: Option<SparseSolveOptions>,
    dense_matrix: Vec<Vec<BigUint>>,
    dense_rhs: Vec<BigUint>,
    sparse_rows: Vec<SparseRow>,
}

impl<'a> LogSystem<'a> {
    /// `None` when the base has no projected columns.
    fn new(
        kc: &'a KoblitzCurve,
        fb: &'a FrobeniusFactorBase,
        opts: &'a KoblitzIcOptions,
    ) -> Option<Self> {
        let r = &kc.subgroup_order;
        let projected = projected_signed_orbit_map(kc, fb);
        let n_cols = projected.representatives.len();
        if n_cols == 0 {
            return None;
        }
        let sparse_opts = match opts.linear_algebra {
            LinearAlgebra::Sparse(s) if koblitz_sparse_la::modulus_supported(r) => Some(s),
            _ => None,
        };
        Some(Self {
            kc,
            fb,
            opts,
            projected,
            n_cols,
            r_u64: r.to_u64_digits().first().copied().unwrap_or(1).max(2),
            h: &kc.cofactor % r,
            sparse_opts,
            dense_matrix: Vec::new(),
            dense_rhs: Vec::new(),
            sparse_rows: Vec::new(),
        })
    }

    fn rows(&self) -> usize {
        if self.sparse_opts.is_some() {
            self.sparse_rows.len()
        } else {
            self.dense_matrix.len()
        }
    }

    /// Rewrite `[a]G = Σ P_i` as a row over the projected columns.
    fn push(&mut self, rel: &CollectedRelation) {
        let r = &self.kc.subgroup_order;
        let a = BigUint::from(rel.a);
        let relation = relation_from_decomposition_with_mode(
            self.kc,
            self.fb,
            &rel.points,
            &a,
            &BigUint::zero(),
            self.opts.collapse_negation,
            Some(&self.projected),
        );
        let rhs = (&self.h * &a) % r;
        if self.sparse_opts.is_some() {
            self.sparse_rows
                .push(SparseRow::from_dense(&relation.row, &rhs, self.r_u64));
        } else {
            self.dense_matrix.push(relation.row);
            self.dense_rhs.push(rhs);
        }
    }

    /// Solve with the rows so far; `Some` only for a table certified in
    /// the group.  Attempts, timing and sparse statistics go to `report`.
    fn attempt(&self, report: &mut LogTableReport) -> Option<FactorBaseLogTable> {
        report.solve_attempts += 1;
        let begin = std::time::Instant::now();
        let solution = match self.sparse_opts {
            Some(sopts) => {
                let (outcome, sreport) = koblitz_sparse_la::solve_sparse_system(
                    &self.sparse_rows,
                    self.n_cols,
                    self.r_u64,
                    &sopts,
                );
                report.sparse_report = Some(sreport);
                match outcome {
                    SparseSolveOutcome::Solved(x) => {
                        Some(x.into_iter().map(BigUint::from).collect())
                    }
                    SparseSolveOutcome::Undetermined | SparseSolveOutcome::Inconsistent => None,
                }
            }
            None => {
                let mut m = self.dense_matrix.clone();
                let mut b = self.dense_rhs.clone();
                gaussian_eliminate_mod_n(&mut m, &mut b, &self.kc.subgroup_order)
            }
        };
        report.linear_algebra_seconds += begin.elapsed().as_secs_f64();
        let table = self.table_from(solution?);
        table.verify(self.kc).then_some(table)
    }

    fn table_from(&self, solution: Vec<BigUint>) -> FactorBaseLogTable {
        let columns = self
            .projected
            .representatives
            .iter()
            .zip(solution)
            .map(|(point, log)| (point.clone(), log))
            .collect();
        FactorBaseLogTable { columns }
    }

    /// Whether an attempt is due: enough rows, and enough new ones since
    /// the last attempt (a failed block Wiedemann run costs a whole Krylov
    /// sequence, so the sparse path waits for a batch of new rows; the
    /// dense path attempts after every batch).
    fn attempt_interval(&self) -> usize {
        if self.sparse_opts.is_some() {
            (self.n_cols / 32).max(1)
        } else {
            1
        }
    }
}

/// **Precompute the factor-base logarithm database.**
///
/// Draws `R = [a]G` probes (`b = 0`, so the target plays no part),
/// decomposes each over the factor base, and rewrites it as a row
/// `Σ_o c_o x_o ≡ h·a (mod r)` over the projected columns.  Once the
/// rows determine every column, the whole logarithm vector is read off
/// in one solve and each entry is certified by `[x_o]G == R_o`.
///
/// This is the once-per-curve cost a per-target descent then amortises.
/// Returns `None` only for a degenerate factor base (no projected
/// columns, or the field too wide for the pair table); an exhausted
/// trial budget yields a report with `verified = false`.
///
/// Probes are drawn in parallel batches of [`PRECOMPUTE_BATCH_TRIALS`]
/// from the seed's probe sequence ([`probe_scalar`]), the same sequence
/// a set of [`RelationCollector`] work units would draw, so a
/// single-process run and a distributed one see identical relations.
/// The linear algebra is chosen by [`KoblitzIcOptions::linear_algebra`].
/// The sparse path keeps only the nonzero entries of each row (at most
/// `m` per relation), skips the solve until every column occurs in some
/// row, and then filters the matrix and runs block Wiedemann on the
/// core; the dense path re-eliminates the full big-integer matrix.
pub fn solve_factor_base_logs(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    opts: &KoblitzIcOptions,
) -> Option<(FactorBaseLogTable, LogTableReport)> {
    let mut system = LogSystem::new(kc, fb, opts)?;
    let collector = RelationCollector::new(kc, fb, opts)?;
    let mut report = LogTableReport {
        sparse: system.sparse_opts.is_some(),
        columns: system.n_cols,
        ..LogTableReport::default()
    };
    let interval = system.attempt_interval();
    let batch = opts.relation_batch_size.max(PRECOMPUTE_BATCH_TRIALS);
    let mut last_attempt = 0usize;
    while report.trials < opts.max_trials {
        let count = batch.min(opts.max_trials - report.trials);
        let unit = RelationWorkUnit {
            seed: opts.seed,
            start: report.trials as u64,
            count: count as u64,
        };
        let (relations, creport) = collector.collect(unit);
        report.trials += creport.trials;
        report.collection_seconds += creport.elapsed_seconds;
        for rel in &relations {
            system.push(rel);
        }
        report.relations = system.rows();
        if report.relations >= system.n_cols && report.relations - last_attempt >= interval {
            last_attempt = report.relations;
            if let Some(table) = system.attempt(&mut report) {
                report.verified = true;
                return Some((table, report));
            }
        }
    }
    // Best effort with whatever was collected; unverified.
    let columns = system
        .attempt(&mut report)
        .map(|t| t.columns)
        .unwrap_or_default();
    Some((FactorBaseLogTable { columns }, report))
}

/// **Solve the logarithm database from relations collected elsewhere.**
///
/// Every relation is re-verified in the group first and rejected if it
/// fails (`report.rejected_relations`); exact duplicates are dropped
/// (`report.duplicate_relations`).  The accepted rows go through the same
/// linear algebra and certification as [`solve_factor_base_logs`].
/// `None` for a base with no projected columns; a set of relations that
/// does not determine every column yields `verified = false`.
/// **The logarithm system of one factor base, fed relations over time.**
///
/// The setup a solve needs — the signed-orbit map of the base, the
/// column order, the modular workspace — costs `Θ(|F|·n)` to build, and
/// a relation costs a group re-verification.  A driver that collects
/// more relations when the columns are not yet determined would pay
/// both again on every round: this pays each exactly once.
pub struct FactorBaseLogSolver<'a> {
    kc: &'a KoblitzCurve,
    fb: &'a FrobeniusFactorBase,
    opts: &'a KoblitzIcOptions,
    system: LogSystem<'a>,
    seen: HashSet<(u64, Vec<usize>)>,
    report: LogTableReport,
}

impl<'a> FactorBaseLogSolver<'a> {
    /// `None` when the base has no projected columns.
    pub fn new(
        kc: &'a KoblitzCurve,
        fb: &'a FrobeniusFactorBase,
        opts: &'a KoblitzIcOptions,
    ) -> Option<Self> {
        let system = LogSystem::new(kc, fb, opts)?;
        let report = LogTableReport {
            sparse: system.sparse_opts.is_some(),
            columns: system.n_cols,
            ..LogTableReport::default()
        };
        Some(Self {
            kc,
            fb,
            opts,
            system,
            seen: HashSet::new(),
            report,
        })
    }

    /// Verify these relations in the group and keep the ones that are
    /// new.  A forged or duplicate relation is counted and dropped, so a
    /// remote worker cannot enter anything into the linear algebra.
    pub fn push(&mut self, relations: &[CollectedRelation]) {
        let begin = std::time::Instant::now();
        let verdicts: Vec<bool> = relations
            .par_iter()
            .map(|rel| verify_collected_relation(self.kc, self.fb, self.opts.m, rel))
            .collect();
        for (rel, ok) in relations.iter().zip(verdicts) {
            if !ok {
                self.report.rejected_relations += 1;
                continue;
            }
            let mut key = rel.points.clone();
            key.sort_unstable();
            if !self.seen.insert((rel.a, key)) {
                self.report.duplicate_relations += 1;
                continue;
            }
            self.system.push(rel);
        }
        self.report.collection_seconds += begin.elapsed().as_secs_f64();
        self.report.relations = self.system.rows();
    }

    /// Relations accepted so far.
    pub fn relations(&self) -> usize {
        self.system.rows()
    }

    /// Columns the relations must determine.
    pub fn columns(&self) -> usize {
        self.system.n_cols
    }

    /// Try to solve with what has been pushed.  `None` means more
    /// relations are needed; the solver stays usable either way.
    pub fn try_solve(&mut self) -> Option<(FactorBaseLogTable, LogTableReport)> {
        if self.system.rows() < self.system.n_cols {
            return None;
        }
        let mut report = self.report.clone();
        let table = self.system.attempt(&mut report)?;
        report.verified = true;
        self.report.solve_attempts = report.solve_attempts;
        Some((table, report))
    }

    /// The report as it stands, for a solve that has not succeeded.
    pub fn report(&self) -> LogTableReport {
        self.report.clone()
    }
}

pub fn solve_factor_base_logs_from_relations(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    opts: &KoblitzIcOptions,
    relations: &[CollectedRelation],
) -> Option<(FactorBaseLogTable, LogTableReport)> {
    let mut solver = FactorBaseLogSolver::new(kc, fb, opts)?;
    solver.push(relations);
    if let Some(solved) = solver.try_solve() {
        return Some(solved);
    }
    Some((
        FactorBaseLogTable {
            columns: Vec::new(),
        },
        solver.report(),
    ))
}

/// What an individual-logarithm descent did.
#[derive(Clone, Debug, Default)]
pub struct IndividualLogReport {
    /// `[a]G + [b]Q` probes drawn before one descended.
    pub trials: usize,
    /// The recovered logarithm, if the descent succeeded and verified.
    pub log: Option<BigUint>,
}

/// **Recover `log_G Q` with one relation, reusing a solved table.**
///
/// Draws `R = [a]G + [b]Q` probes until one decomposes over the factor
/// base; that single relation gives
/// `h·a + h·b·d ≡ Σ_o c_o x_o (mod r)`, and with the column logs `x_o`
/// already known the scalar `d = log_G Q` falls out of one modular
/// inverse.  The recovered `d` is re-checked as `[d]G == Q` before it
/// is returned, so a `Some` is never a false positive.
///
/// This is the per-target half of the split: no relation matrix, just
/// one decomposition and a lookup.  The table must belong to the same
/// curve and factor base (its columns are matched to the rebuilt
/// projected columns by point identity).
pub fn individual_log(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    table: &FactorBaseLogTable,
    q: &BinaryPoint,
    opts: &KoblitzIcOptions,
) -> Option<(BigUint, IndividualLogReport)> {
    let pair = if opts.strategy == DecompositionStrategy::PairTable {
        Some(PairSumTable::build(kc, fb)?)
    } else {
        None
    };
    individual_log_with_pair_table(kc, fb, table, q, opts, pair.as_ref())
}

/// [`individual_log`] with a caller-supplied pair table, so a batch of
/// targets over one factor base builds the `|F|²` table once instead
/// of once per target.  `pair` is required when the strategy is
/// [`DecompositionStrategy::PairTable`] and ignored otherwise.  For a
/// batch of targets build one [`IndividualLogSolver`] instead: this
/// rebuilds the orbit map of the base for every call.
pub fn individual_log_with_pair_table(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    table: &FactorBaseLogTable,
    q: &BinaryPoint,
    opts: &KoblitzIcOptions,
    pair: Option<&PairSumTable>,
) -> Option<(BigUint, IndividualLogReport)> {
    IndividualLogSolver::new(kc, fb, table, opts, pair)?.solve(q)
}

/// The target-independent half of a descent — the signed-orbit map of
/// the base, its column logarithms, the decomposition oracle's tables
/// and the single-word curve for the probes — built once and reused
/// for every target of a batch.
pub struct IndividualLogSolver<'a> {
    kc: &'a KoblitzCurve,
    fb: &'a FrobeniusFactorBase,
    opts: &'a KoblitzIcOptions,
    pair: Option<&'a PairSumTable>,
    projected: ProjectedSignedOrbitMap,
    column_log: Vec<BigUint>,
    index_of: HashMap<(BigUint, BigUint), usize>,
    field: FieldStructure,
    /// Single-word curve and lifted generator when the field fits.
    fast: Option<(FastCurve, FastPoint)>,
    h: BigUint,
    r_u64: u64,
}

impl<'a> IndividualLogSolver<'a> {
    /// `None` when the table's columns do not match the base's signed
    /// orbits, a column has no logarithm, or the strategy needs a pair
    /// table and none was supplied.
    pub fn new(
        kc: &'a KoblitzCurve,
        fb: &'a FrobeniusFactorBase,
        table: &FactorBaseLogTable,
        opts: &'a KoblitzIcOptions,
        pair: Option<&'a PairSumTable>,
    ) -> Option<Self> {
        let projected = projected_signed_orbit_map(kc, fb);
        if projected.representatives.len() != table.columns.len() {
            return None;
        }
        if opts.strategy == DecompositionStrategy::PairTable && pair.is_none() {
            return None;
        }
        let log_of = table.log_of();
        let column_log: Vec<BigUint> = projected
            .representatives
            .iter()
            .map(|point| log_of.get(&point_key(point)).cloned())
            .collect::<Option<Vec<_>>>()?;
        let r = &kc.subgroup_order;
        let fast = FastCurve::new(&kc.curve).map(|fc| {
            let g = fc.lift(kc.generator());
            (fc, g)
        });
        Some(Self {
            kc,
            fb,
            opts,
            pair,
            projected,
            column_log,
            index_of: fb.index_map(),
            field: FieldStructure::new(kc.n, &kc.curve.irreducible),
            fast,
            h: &kc.cofactor % r,
            r_u64: r.to_u64_digits().first().copied().unwrap_or(1).max(2),
        })
    }

    /// Decompose `[a]G + [b]Q` for the probe `(a, b)`, or `None` when the
    /// probe is `O` (reported separately) or does not decompose.
    fn probe(&self, q: &BinaryPoint, q_fast: Option<FastPoint>, a: u64, b: u64) -> Probe {
        if let (Some((fc, g)), Some(qf)) = (&self.fast, q_fast) {
            let target = fc.add(fc.mul_u64(*g, a), fc.mul_u64(qf, b));
            if target.infinity {
                return Probe::Degenerate;
            }
            let idxs = match (self.opts.strategy, self.pair) {
                (DecompositionStrategy::PairTable, Some(pair)) => {
                    pair.decompose_fast(target, self.opts.m)
                }
                _ => decompose_once(
                    self.kc,
                    self.fb,
                    &self.index_of,
                    &self.field,
                    self.pair,
                    self.opts,
                    &fc.lower(target),
                ),
            };
            return idxs.map_or(Probe::Miss, Probe::Decomposed);
        }
        let g = self.kc.generator();
        let target = self.kc.add(
            &self.kc.mul(g, &BigUint::from(a)),
            &self.kc.mul(q, &BigUint::from(b)),
        );
        if target == BinaryPoint::Infinity {
            return Probe::Degenerate;
        }
        decompose_once(
            self.kc,
            self.fb,
            &self.index_of,
            &self.field,
            self.pair,
            self.opts,
            &target,
        )
        .map_or(Probe::Miss, Probe::Decomposed)
    }

    /// Summands the descent asks for.
    fn descent_m(&self) -> usize {
        self.opts.descent_m.unwrap_or(self.opts.m)
    }

    /// Turn a decomposition of `[a]G + [b]Q` into the logarithm, or
    /// `None` when this relation cannot give one.
    fn logarithm_from(&self, q: &BinaryPoint, idxs: &[usize], a: u64, b: u64) -> Option<BigUint> {
        let kc = self.kc;
        let r = &kc.subgroup_order;
        let (a, b) = (BigUint::from(a), BigUint::from(b));
        let relation = relation_from_decomposition_with_mode(
            kc,
            self.fb,
            idxs,
            &a,
            &b,
            self.opts.collapse_negation,
            Some(&self.projected),
        );
        // Σ_o c_o x_o − h·a ≡ h·b·d (mod r).
        let mut sum = BigUint::zero();
        for (coeff, log) in relation.row.iter().zip(&self.column_log) {
            if !coeff.is_zero() {
                sum = (sum + coeff * log) % r;
            }
        }
        let ha = (&self.h * &a) % r;
        let numerator = (sum + r - ha) % r;
        let hb = (&self.h * &b) % r;
        let d = (numerator * mod_inverse(&hb, r)?) % r;
        (kc.mul(kc.generator(), &d) == *q).then_some(d)
    }

    /// **Walk the probes instead of drawing them.**
    ///
    /// A probe is any `[a]G + [b]Q`, and stepping one by `+G` costs a
    /// single point addition against the two scalar multiplications a
    /// fresh draw costs. Several walks step together so one field
    /// inversion serves them all, which brings a probe under the cost
    /// of the table lookup that follows it — the regime where asking
    /// for two summands beats asking for three.
    ///
    /// `None` when the field is too wide for the single-word
    /// arithmetic; the caller falls back to drawing.
    fn solve_by_walking(
        &self,
        q: &BinaryPoint,
        report: &mut IndividualLogReport,
    ) -> Option<Option<BigUint>> {
        let (fc, g) = self.fast.as_ref()?;
        let pair = self.pair?;
        let m = self.descent_m();
        let q_fast = fc.lift(q);
        const WALKS: usize = 64;
        // Walks must not tread on each other, so they start one stride
        // apart on the same line and each is stepped by G.  Building
        // them that way costs three scalar multiplications and 63
        // additions, where drawing each start costs two scalar
        // multiplications apiece — which on a walk of a few hundred
        // rounds is most of the descent.
        let stride = (self.r_u64 / WALKS as u64).max(1 << 20);
        let mut rng = StdRng::seed_from_u64(self.opts.seed ^ 0x57_41_4c_4b_44_45_53_00);
        let a0 = rng.gen_range(1..self.r_u64);
        let b = rng.gen_range(1..self.r_u64);
        let stride_point = fc.mul_u64(*g, stride);
        let mut coefficients: Vec<(u64, u64)> = Vec::with_capacity(WALKS);
        let mut states: Vec<FastPoint> = Vec::with_capacity(WALKS);
        let mut state = fc.add(fc.mul_u64(*g, a0), fc.mul_u64(q_fast, b));
        let mut a = a0;
        for _ in 0..WALKS {
            coefficients.push((a, b));
            states.push(state);
            state = fc.add(state, stride_point);
            a = (a + stride) % self.r_u64;
        }
        let step = vec![*g; WALKS];
        let mut advanced = Vec::with_capacity(WALKS);
        let mut scratch = BatchScratch::default();
        while report.trials < self.opts.max_trials {
            for (state, (a, b)) in states.iter().zip(coefficients.iter()) {
                report.trials += 1;
                if state.infinity {
                    // [a]G + [b]Q = O already yields d.
                    if let Some(d) = solve_for_d(
                        &BigUint::from(*a),
                        &BigUint::from(*b),
                        &self.kc.subgroup_order,
                    ) {
                        if self.kc.mul(self.kc.generator(), &d) == *q {
                            return Some(Some(d));
                        }
                    }
                    continue;
                }
                let Some(idxs) = pair.decompose_fast(*state, m) else {
                    continue;
                };
                if let Some(d) = self.logarithm_from(q, &idxs, *a, *b) {
                    return Some(Some(d));
                }
            }
            // Advance every walk by G, sharing one inversion.
            advanced.clear();
            fc.add_pairwise(&states, &step, &mut advanced, &mut scratch);
            states.copy_from_slice(&advanced);
            for (a, _) in coefficients.iter_mut() {
                *a = (*a + 1) % self.r_u64;
            }
        }
        Some(None)
    }

    /// The logarithm of `q` to the base's generator, verified as
    /// `[d]G = Q` in the general arithmetic before it is returned.
    pub fn solve(&self, q: &BinaryPoint) -> Option<(BigUint, IndividualLogReport)> {
        let kc = self.kc;
        let r = &kc.subgroup_order;
        let g = kc.generator();
        let mut report = IndividualLogReport::default();
        if *q == BinaryPoint::Infinity {
            // Q = O has logarithm 0.
            report.log = Some(BigUint::zero());
            return Some((BigUint::zero(), report));
        }
        // The walk needs the single-word arithmetic and a pair table;
        // without either, fall through to drawing probes.
        if self.opts.strategy == DecompositionStrategy::PairTable {
            if let Some(found) = self.solve_by_walking(q, &mut report) {
                return found.map(|d| {
                    report.log = Some(d.clone());
                    (d, report)
                });
            }
        }
        let q_fast = self.fast.as_ref().map(|(fc, _)| fc.lift(q));
        let mut rng = StdRng::seed_from_u64(self.opts.seed ^ 0x44_45_53_43_45_4e_54_00);
        while report.trials < self.opts.max_trials {
            report.trials += 1;
            let a = rng.gen_range(1..self.r_u64);
            let b = rng.gen_range(1..self.r_u64);
            let idxs = match self.probe(q, q_fast, a, b) {
                Probe::Decomposed(idxs) => idxs,
                Probe::Miss => continue,
                Probe::Degenerate => {
                    // Degenerate relation [a]G + [b]Q = O already yields d.
                    if let Some(d) = solve_for_d(&BigUint::from(a), &BigUint::from(b), r) {
                        if kc.mul(g, &d) == *q {
                            report.log = Some(d.clone());
                            return Some((d, report));
                        }
                    }
                    continue;
                }
            };
            let a = BigUint::from(a);
            let b = BigUint::from(b);
            let relation = relation_from_decomposition_with_mode(
                kc,
                self.fb,
                &idxs,
                &a,
                &b,
                self.opts.collapse_negation,
                Some(&self.projected),
            );
            // Σ_o c_o x_o − h·a ≡ h·b·d (mod r).
            let mut sum = BigUint::zero();
            for (coeff, log) in relation.row.iter().zip(&self.column_log) {
                if !coeff.is_zero() {
                    sum = (sum + coeff * log) % r;
                }
            }
            let ha = (&self.h * &a) % r;
            let numerator = (sum + r - ha) % r;
            let hb = (&self.h * &b) % r;
            let Some(hb_inv) = mod_inverse(&hb, r) else {
                continue;
            };
            let d = (numerator * hb_inv) % r;
            if kc.mul(g, &d) == *q {
                report.log = Some(d.clone());
                return Some((d, report));
            }
            // A non-matching d means this factor base cannot place Q in the
            // span its columns log (e.g. Q outside the reachable subgroup);
            // keep trying other relations before giving up.
        }
        None
    }
}

/// Outcome of one descent probe.
enum Probe {
    /// `[a]G + [b]Q = O`.
    Degenerate,
    /// The probe did not decompose.
    Miss,
    /// The probe decomposed into these base indices.
    Decomposed(Vec<usize>),
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::koblitz_groebner::build_decomposition_system;

    #[test]
    fn koblitz_mul_dispatch_matches_general_arithmetic() {
        let mut checked = 0usize;
        for (a, n) in [
            (0, 5),
            (0, 9),
            (1, 11),
            (0, 13),
            (1, 17),
            (0, 19),
            (1, 19),
            (0, 23),
            (0, 31),
            (0, 53),
            (0, 61),
        ] {
            let Some(kc) = KoblitzCurve::new(a, n) else {
                continue;
            };
            let mut points = vec![
                BinaryPoint::Infinity,
                kc.generator().clone(),
                point_neg(kc.generator()),
            ];
            for x in 0..8u64 {
                points.extend(points_with_x(
                    &kc.curve,
                    &F2mElement::from_biguint(&BigUint::from(x), n),
                ));
            }
            let scalars = [
                BigUint::zero(),
                BigUint::one(),
                BigUint::from(2u32),
                &kc.subgroup_order - BigUint::one(),
                kc.subgroup_order.clone(),
                &kc.subgroup_order + BigUint::one(),
                (BigUint::one() << 80usize) + BigUint::from(123u32),
            ];
            for point in &points {
                for scalar in &scalars {
                    assert_eq!(
                        kc.mul(point, scalar),
                        scalar_mul(&kc.curve, point, scalar),
                        "scalar dispatch at n={n}, a={a}, k={scalar}"
                    );
                    checked += 1;
                }
            }
            // A different field-width encoding must use the generic fallback.
            if let BinaryPoint::Affine { x, y } = kc.generator() {
                let wider = BinaryPoint::Affine {
                    x: F2mElement::from_biguint(&x.to_biguint(), n + 1),
                    y: F2mElement::from_biguint(&y.to_biguint(), n + 1),
                };
                assert_eq!(
                    kc.mul(&wider, &BigUint::one()),
                    scalar_mul(&kc.curve, &wider, &BigUint::one())
                );
            }
        }
        assert!(
            checked >= 200,
            "insufficient independent arithmetic cases: {checked}"
        );
    }

    #[test]
    fn fast_base_lifts_preserve_roots_and_order() {
        for n in [5, 7, 9, 11, 13, 17, 19, 23, 31, 53, 61] {
            let Some(kc) = KoblitzCurve::new(0, n) else {
                continue;
            };
            for (a, b) in [(0u64, 1u64), (1, 1), (3, 5)] {
                let mut curve = kc.curve.clone();
                curve.a = F2mElement::from_biguint(&BigUint::from(a), n);
                curve.b = F2mElement::from_biguint(&BigUint::from(b), n);
                let fast = FastCurve::new(&curve).unwrap();
                let samples = if n <= 11 { 1u64 << n } else { 128 };
                let mut rng = StdRng::seed_from_u64(73015 + u64::from(n));
                for i in 0..samples {
                    let bits = if n <= 11 || i == 0 {
                        i
                    } else {
                        rng.gen_range(0..1u64 << n)
                    };
                    let x = F2mElement::from_biguint(&BigUint::from(bits), n);
                    assert_eq!(
                        points_with_x_fast(&fast, &x),
                        points_with_x(&curve, &x),
                        "ordered roots at n={n}, a={a}, b={b}, x={bits}",
                    );
                }
            }
        }
    }

    #[test]
    #[ignore]
    fn subgroup_sizes_by_degree() {
        for n in 31..=59u32 {
            for a in [0u8, 1] {
                if let Some(kc) = KoblitzCurve::new(a, n) {
                    let r = kc.subgroup_order.to_string();
                    eprintln!(
                        "RUNG n={n} a={a} r={r} h={} bits={}",
                        kc.cofactor,
                        kc.subgroup_order.bits()
                    );
                }
            }
        }
    }

    #[test]
    fn descent_summands_may_differ_from_the_collection_summands() {
        // The log database is built with three summands; the descent
        // asks for two, walking its probes.  Both must return the same
        // logarithm, and the walk must not need more probes than the
        // 2r/|F|^2 its rate predicts.
        let kc = KoblitzCurve::new(0, 23).unwrap();
        let fb = build_subgroup_orbit_factor_base(&kc, 3, 900).unwrap();
        let collect = KoblitzIcOptions {
            m: 3,
            strategy: DecompositionStrategy::PairTable,
            max_trials: 200_000,
            ..KoblitzIcOptions::default()
        };
        let (table, _) = solve_factor_base_logs(&kc, &fb, &collect).expect("log database");
        let pair = PairSumTable::build(&kc, &fb).unwrap();
        let walking = KoblitzIcOptions {
            descent_m: Some(2),
            ..collect.clone()
        };
        let three = IndividualLogSolver::new(&kc, &fb, &table, &collect, Some(&pair)).unwrap();
        let two = IndividualLogSolver::new(&kc, &fb, &table, &walking, Some(&pair)).unwrap();
        let r = kc.subgroup_order.to_u64_digits()[0];
        for d in [3u64, 11, 12_345 % r, r - 5] {
            let d = BigUint::from(d);
            let q = kc.mul(kc.generator(), &d);
            let (found3, _) = three.solve(&q).expect("three summands descend");
            let (found2, report2) = two.solve(&q).expect("two summands descend");
            assert_eq!(found3, d);
            assert_eq!(found2, d);
            // Rate is |F|^2/(2r) per probe, so a run of 64 times the mean
            // would be a broken walk rather than bad luck.
            let expected = 2.0 * r as f64 / (fb.points.len() as f64).powi(2);
            assert!(
                (report2.trials as f64) < 64.0 * expected.max(1.0),
                "two-summand walk took {} probes against a {expected:.0}-probe mean",
                report2.trials
            );
        }
    }

    #[test]
    fn pair_table_refuses_a_base_beyond_its_byte_budget() {
        let kc = KoblitzCurve::new(0, 19).unwrap();
        let fb = build_subgroup_orbit_factor_base(&kc, 5, 400).unwrap();
        let full = PairSumTable::byte_size(fb.points.len());
        let compact = PairSumTable::compact_byte_size(fb.points.len(), kc.n);
        assert!(compact < full, "the compact table is the narrower one");
        // A budget that fits the summands keeps them.
        let wide = PairSumTable::build_within(&kc, &fb, full).expect("fits with summands");
        assert!(!wide.is_compact());
        // One that does not falls back to the compact table rather than
        // refusing: a base that fits only compactly is worth having.
        let narrow = PairSumTable::build_within(&kc, &fb, full - 1).expect("fits compactly");
        assert!(narrow.is_compact());
        assert_eq!(wide.len(), narrow.len());
        // Below even that, the fold is the last tier: `2n` times fewer
        // keys, bought with a canonicalisation on every lookup.
        let folded_bytes =
            PairSumTable::folded_byte_size(fb.signed_orbits.len(), fb.points.len(), kc.n);
        assert!(folded_bytes < compact, "the folded table is narrower still");
        let folded = PairSumTable::build_within(&kc, &fb, compact - 1).expect("fits folded");
        assert!(folded.is_folded() && folded.is_compact());
        assert!(folded.len() < narrow.len(), "the fold stored no less");
        // And below that it refuses with a number rather than an
        // allocation the machine cannot meet.
        assert!(PairSumTable::build_within(&kc, &fb, folded_bytes - 1).is_none());
        // The default budget is far above a base this size.
        assert!(full < PairSumTable::DEFAULT_BYTE_BUDGET);
        assert!(PairSumTable::build(&kc, &fb).is_some());
    }

    #[test]
    fn subgroup_orbit_bases_are_reproducible_and_inside_the_subgroup() {
        for (a, n) in [(0u8, 19u32), (1, 19), (0, 23)] {
            let kc = KoblitzCurve::new(a, n).unwrap();
            let fb = build_subgroup_orbit_factor_base(&kc, 7, 200).unwrap();
            assert!(fb.points.len() >= 200);
            // Every point is in the prime-order subgroup, and the base is
            // still closed under Frobenius and negation.
            for p in &fb.points {
                assert_eq!(kc.mul(p, &kc.subgroup_order), BinaryPoint::Infinity);
                assert!(fb.points.contains(&kc.frobenius(p)));
                assert!(fb.points.contains(&point_neg(p)));
            }
            // The recipe is the whole description: same seed, same base.
            let again = build_subgroup_orbit_factor_base(&kc, 7, 200).unwrap();
            assert_eq!(fb.points, again.points);
            let other = build_subgroup_orbit_factor_base(&kc, 8, 200).unwrap();
            assert_ne!(fb.points, other.points);
        }
    }

    #[test]
    fn subgroup_orbit_bases_decompose_far_more_often_than_a_subspace_union() {
        // The measurement this family exists for: how often a random
        // subgroup point is a sum of three base points.
        let kc = KoblitzCurve::new(0, 37).unwrap();
        let fc = FastCurve::new(&kc.curve).unwrap();
        let r = kc.subgroup_order.to_u64_digits()[0];
        let g = fc.lift(kc.generator());
        let rate = |fb: &FrobeniusFactorBase| -> f64 {
            let table = PairSumTable::build(&kc, fb).unwrap();
            let mut rng = StdRng::seed_from_u64(4);
            let trials = 600;
            let hits = (0..trials)
                .filter(|_| {
                    let target = fc.mul_u64(g, rng.gen_range(1..r));
                    table.decompose_fast(target, 3).is_some()
                })
                .count();
            hits as f64 / trials as f64
        };
        let seeds: Vec<F2mElement> = (0..3)
            .map(|i| F2mElement::from_bit_positions(&[i], kc.n))
            .collect();
        let union = build_frobenius_union_factor_base(&kc, &seeds).unwrap();
        let subgroup = build_subgroup_orbit_factor_base(&kc, 11, union.points.len()).unwrap();
        let (union_rate, subgroup_rate) = (rate(&union), rate(&subgroup));
        // Same size, same column order of magnitude, far better yield.
        assert!(subgroup.points.len() >= union.points.len());
        // Both bases must be in the scarce regime, or the comparison is
        // vacuous.
        assert!(union_rate < 0.5, "union base saturates: {union_rate}");
        assert!(
            subgroup_rate > 2.0 * union_rate,
            "union {union_rate:.4} from {} points, subgroup {subgroup_rate:.4} from {} points",
            union.points.len(),
            subgroup.points.len()
        );
    }

    #[test]
    fn subgroup_orbit_base_precomputes_logs_and_descends() {
        let kc = KoblitzCurve::new(0, 19).unwrap();
        let fb = build_subgroup_orbit_factor_base(&kc, 3, 400).unwrap();
        let opts = KoblitzIcOptions {
            m: 3,
            descent_m: None,
            strategy: DecompositionStrategy::PairTable,
            max_trials: 200_000,
            ..KoblitzIcOptions::default()
        };
        let (table, report) = solve_factor_base_logs(&kc, &fb, &opts).expect("log database");
        assert!(report.relations >= table.columns.len());
        let pair = PairSumTable::build(&kc, &fb).unwrap();
        let solver = IndividualLogSolver::new(&kc, &fb, &table, &opts, Some(&pair)).unwrap();
        let r = kc.subgroup_order.to_u64_digits()[0];
        for d in [1u64, 5, 9_999 % r, r - 2] {
            let d = BigUint::from(d);
            let q = kc.mul(kc.generator(), &d);
            let (found, _) = solver.solve(&q).expect("descends");
            assert_eq!(found, d);
        }
    }

    #[test]
    fn rho_charge_ledgers_close() {
        // The custody validators of the unknown-scalar panel check these
        // identities on every rho run, so the walk has to hold them by
        // construction.
        for (a, n, jumps, walks) in [(0u8, 9u32, 16usize, 1usize), (1, 19, 8, 4), (0, 31, 16, 32)] {
            let kc = KoblitzCurve::new(a, n).unwrap();
            let r = kc.subgroup_order.to_u64_digits()[0];
            for seed in 0..3u64 {
                let d = BigUint::from((seed * 65_537 + 3) % r);
                let q = kc.mul(kc.generator(), &d);
                let report = koblitz_signed_frobenius_rho_with_progress(
                    &kc,
                    &q,
                    &KoblitzSignedRhoOptions {
                        seed,
                        jump_count: jumps,
                        max_restarts: 8,
                        max_iterations_per_restart: 1 << 20,
                        progress_interval: 0,
                        parallel_walks: walks,
                    },
                    &mut |_| {},
                );
                let c = &report.charges;
                let rebuilds = u64::from(report.jump_table_rebuilds);
                let setup_points = (jumps + report.parallel_walks) as u64;
                assert_eq!(report.jump_table_rebuilds, report.restarts_attempted);
                assert_eq!(c.setup_group_additions, setup_points * rebuilds);
                assert_eq!(c.setup_scalar_multiplications, 2 * setup_points * rebuilds);
                assert_eq!(c.coefficient_draws, c.setup_scalar_multiplications);
                // Every advance is one addition and one partition hash;
                // the extra additions are the escape doublings.
                assert_eq!(
                    c.walk_group_additions,
                    c.partition_hashes + c.cycle_escape_doublings
                );
                // One canonicalization per setup point, per advance and
                // per escape doubling.
                assert_eq!(
                    c.canonicalizations,
                    report.parallel_walks as u64 * rebuilds
                        + c.partition_hashes
                        + c.cycle_escape_doublings
                );
                // Each charged iteration examines one state, which either
                // advances (one hash) or escapes (at least one hash, at
                // most the 64-state enumeration bound).
                assert!(
                    report
                        .iterations
                        .saturating_sub(report.parallel_walks as u64)
                        <= c.partition_hashes
                );
                assert!(c.partition_hashes <= report.iterations + 64 * c.fruitless_cycles);
                assert_eq!(c.frobenius_maps, c.negations_examined);
                assert_eq!(c.frobenius_maps % u64::from(n), 0);
                assert!(c.frobenius_maps <= c.canonicalizations * u64::from(n));
                assert!(c.collisions >= c.failed_collisions);
                assert!(report.parallel_walks >= 1 && report.parallel_walks <= walks);
            }
        }
    }

    #[test]
    fn every_stored_pair_sum_is_found_by_lookup() {
        // The presence filter must never hide an entry.
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let table = PairSumTable::build(&kc, &fb).unwrap();
        let fc = FastCurve::new(&kc.curve).unwrap();
        for i in 0..fb.points.len() {
            for j in i..fb.points.len() {
                let sum = fc.add(fc.lift(&fb.points[i]), fc.lift(&fb.points[j]));
                let hits = table.lookup(sum.pack());
                assert!(
                    hits.iter()
                        .any(|&(_, a, b)| (a as usize, b as usize) == (i, j)),
                    "pair ({i}, {j}) missing from the table"
                );
            }
        }
        // And a point that is no pair sum is reported absent.
        let mut absent = 0usize;
        for k in 1..512u64 {
            if table.lookup(k * 2 + 1_000_001).is_empty() {
                absent += 1;
            }
        }
        assert!(absent > 0, "the filter claimed every probe was present");
    }

    #[test]
    fn rho_escapes_fruitless_cycles_instead_of_restarting() {
        // Two jumps make the negation 2-cycle of the quotient walk
        // frequent; every walk must still end in a verified log.
        let kc = KoblitzCurve::new(1, 19).unwrap();
        let r = kc.subgroup_order.to_u64_digits()[0];
        let mut escaped_total = 0;
        for seed in 0..12u64 {
            let d = BigUint::from((seed * 104_729 + 7) % r);
            let q = kc.mul(kc.generator(), &d);
            let options = KoblitzSignedRhoOptions {
                seed,
                jump_count: 2,
                max_restarts: 4,
                max_iterations_per_restart: 1 << 20,
                progress_interval: 0,
                parallel_walks: 4,
            };
            let report = koblitz_signed_frobenius_rho_with_progress(&kc, &q, &options, &mut |_| {});
            assert!(report.verified, "seed {seed}");
            assert_eq!(report.recovered_log, Some(d));
            escaped_total += report.charges.fruitless_cycles;
        }
        assert!(
            escaped_total > 0,
            "the two-jump walk never met a fruitless cycle"
        );
    }

    #[test]
    fn rho_step_count_tracks_the_birthday_bound() {
        // The walk must cost about √(πr/2)/√(2n) steps: a walk that
        // mixes badly, or one whose fruitless cycles are not escaped,
        // shows up here as a step count far above the bound.
        for (a, n) in [(0u8, 19u32), (1, 19), (0, 31)] {
            let kc = KoblitzCurve::new(a, n).unwrap();
            let r = kc.subgroup_order.to_u64_digits()[0];
            let expected = rho_expected_steps(r, n);
            let mut total = 0f64;
            let trials = 6u64;
            for seed in 0..trials {
                let d = BigUint::from((seed * 7_919 + 11) % r);
                let q = kc.mul(kc.generator(), &d);
                let report = koblitz_signed_frobenius_rho_with_progress(
                    &kc,
                    &q,
                    &KoblitzSignedRhoOptions {
                        seed,
                        progress_interval: 0,
                        ..KoblitzSignedRhoOptions::default()
                    },
                    &mut |_| {},
                );
                assert!(
                    report.verified,
                    "K_{a}/2^{n} seed {seed} did not recover the log"
                );
                assert_eq!(report.recovered_log, Some(d));
                total += report.iterations as f64;
            }
            let mean = total / trials as f64;
            assert!(
                mean < 8.0 * expected,
                "K_{a}/2^{n}: {mean:.0} steps on average against a {expected:.0}-step bound"
            );
        }
    }

    #[test]
    #[ignore = "a few seconds per target in release; the degree-41 rung of the ledger"]
    fn rho_recovers_logs_at_degree_41() {
        let kc = KoblitzCurve::new(0, 41).unwrap();
        let r = kc.subgroup_order.to_u64_digits()[0];
        let expected = rho_expected_steps(r, 41);
        for seed in 0..2u64 {
            let d = BigUint::from((seed * 1_000_003 + 123_456_789) % r);
            let q = kc.mul(kc.generator(), &d);
            let report = koblitz_signed_frobenius_rho_with_progress(
                &kc,
                &q,
                &KoblitzSignedRhoOptions {
                    seed,
                    progress_interval: 0,
                    ..KoblitzSignedRhoOptions::default()
                },
                &mut |_| {},
            );
            assert!(
                report.verified,
                "seed {seed}: {} steps, {} fruitless cycles",
                report.iterations, report.charges.fruitless_cycles
            );
            assert_eq!(report.recovered_log, Some(d));
            assert!((report.iterations as f64) < 20.0 * expected);
        }
    }

    #[test]
    fn single_word_rho_walk_matches_the_reference_step_for_step() {
        for (a, n, seed) in [(0u8, 9u32, 1u64), (1, 11, 2), (1, 15, 3), (0, 9, 4)] {
            let kc = KoblitzCurve::new(a, n).unwrap();
            let r = kc.subgroup_order.to_u64_digits()[0];
            let d = BigUint::from(seed * 7919 % r + 1);
            let q = kc.mul(kc.generator(), &d);
            let options = KoblitzSignedRhoOptions {
                seed,
                jump_count: 8,
                max_restarts: 8,
                max_iterations_per_restart: 1 << 16,
                progress_interval: 0,
                parallel_walks: 4,
            };
            let fast = koblitz_signed_frobenius_rho_with_progress(&kc, &q, &options, &mut |_| {});
            let reference = koblitz_signed_frobenius_rho_reference(&kc, &q, &options, &mut |_| {});
            assert!(fast.verified, "K_{a}/2^{n}: fast walk found the log");
            assert_eq!(fast.recovered_log, Some(d.clone()));
            assert_eq!(fast.recovered_log, reference.recovered_log);
            assert_eq!(fast.iterations, reference.iterations);
            assert_eq!(fast.restarts_attempted, reference.restarts_attempted);
            assert_eq!(fast.charges, reference.charges);
        }
    }

    #[test]
    fn descent_solver_reuses_its_setup_across_targets() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let opts = KoblitzIcOptions {
            m: 2,
            strategy: DecompositionStrategy::PairTable,
            ..KoblitzIcOptions::default()
        };
        let (table, _) = solve_factor_base_logs(&kc, &fb, &opts).unwrap();
        let pair = PairSumTable::build(&kc, &fb).unwrap();
        let solver = IndividualLogSolver::new(&kc, &fb, &table, &opts, Some(&pair)).unwrap();
        let r = kc.subgroup_order.to_u64_digits()[0];
        for d in [1u64, 2, 17, r / 2, r - 1] {
            let d = BigUint::from(d);
            let q = kc.mul(kc.generator(), &d);
            let (found, report) = solver.solve(&q).expect("descends");
            assert_eq!(found, d);
            let (again, report_again) =
                individual_log_with_pair_table(&kc, &fb, &table, &q, &opts, Some(&pair)).unwrap();
            assert_eq!(again, d);
            assert_eq!(report.trials, report_again.trials);
        }
        assert_eq!(
            solver.solve(&BinaryPoint::Infinity).unwrap().0,
            BigUint::zero()
        );
    }

    #[test]
    fn irreducibility_test_matches_known_polynomials() {
        // x² + x + 1, x³ + x + 1, x⁴ + x + 1 are irreducible.
        assert!(is_irreducible_f2(0b111));
        assert!(is_irreducible_f2(0b1011));
        assert!(is_irreducible_f2(0b10011));
        // x² + 1 = (x + 1)², x³ + 1 = (x + 1)(x² + x + 1).
        assert!(!is_irreducible_f2(0b101));
        assert!(!is_irreducible_f2(0b1001));
    }

    #[test]
    fn find_irreducible_returns_degree_n_irreducible() {
        for n in 3..=16u32 {
            let irr = find_irreducible(n).expect("degree-n irreducible exists");
            assert_eq!(irr.degree, n);
            let mut mask = 1u64 << n;
            for t in &irr.low_terms {
                mask |= 1 << t;
            }
            assert!(is_irreducible_f2(mask), "n = {n}");
        }
    }

    #[test]
    fn constructs_past_prior_ceiling_n53() {
        // Ledger next factor-base / vs_rho rung past MAX_N=41.
        let curve = KoblitzCurve::new(0, 53).expect("K_0/F_2^53 must construct");
        assert_eq!(curve.n, 53);
        assert!(curve.subgroup_order.bits() >= 40);
        assert_eq!(
            scalar_mul(&curve.curve, curve.generator(), &curve.subgroup_order),
            BinaryPoint::Infinity
        );
    }

    #[test]
    fn x_n_minus_1_factors_have_degree_ord_2_mod_n() {
        // x⁷ − 1 = (x − 1)(x³ + x + 1)(x³ + x² + 1); ord_7(2) = 3.
        assert_eq!(order_of_2_mod_n(7), Some(3));
        let f7 = factor_x_n_minus_1(7);
        assert_eq!(f7.len(), 2);
        assert!(f7.contains(&0b1011));
        assert!(f7.contains(&0b1101));

        // ord_9(2) = 6, so a single degree-6 factor x⁶ + x³ + 1.
        assert_eq!(order_of_2_mod_n(9), Some(6));
        let f9 = factor_x_n_minus_1(9);
        assert_eq!(f9.len(), 1);
        assert_eq!(f9[0], 0b1001001);
    }

    #[test]
    fn point_counts_match_direct_enumeration() {
        for a in 0..=1u8 {
            for n in 3..=9u32 {
                let irr = find_irreducible(n).unwrap();
                let curve = BinaryCurve {
                    m: n,
                    irreducible: irr,
                    a: if a == 0 {
                        F2mElement::zero(n)
                    } else {
                        F2mElement::one(n)
                    },
                    b: F2mElement::one(n),
                    generator: BinaryPoint::Infinity,
                    order: BigUint::zero(),
                    cofactor: BigUint::one(),
                };
                let mut count = 1u64; // O
                for raw in 0..(1u64 << n) {
                    let x = F2mElement::from_biguint(&BigUint::from(raw), n);
                    count += points_with_x(&curve, &x).len() as u64;
                }
                assert_eq!(
                    BigUint::from(count),
                    koblitz_point_count(a, n),
                    "a = {a}, n = {n}"
                );
            }
        }
    }

    #[test]
    fn frobenius_acts_as_lambda_on_the_subgroup() {
        let kc = KoblitzCurve::new(0, 9).expect("K_0 over F_512");
        assert_eq!(kc.subgroup_order, BigUint::from(127u32));
        let g = kc.generator().clone();
        // π = [λ] must hold across the whole subgroup, not just on G.
        for k in 1..20u32 {
            let p = kc.mul(&g, &BigUint::from(k));
            assert_eq!(kc.frobenius(&p), kc.mul(&p, &kc.lambda));
        }
        // λ is a root of the characteristic polynomial λ² − tλ + 2.
        let r = &kc.subgroup_order;
        let t = r - BigUint::one(); // t = −1 for a = 0
        let lhs = (&kc.lambda * &kc.lambda + BigUint::from(2u32)) % r;
        assert_eq!(lhs, (&t * &kc.lambda) % r);
    }

    #[test]
    fn cyclotomic_cosets_partition_and_classify() {
        for n in [7u32, 9, 15, 21, 31, 63] {
            let cosets = cyclotomic_cosets(n);
            let mut all: Vec<u32> = cosets.iter().flatten().copied().collect();
            all.sort_unstable();
            assert_eq!(
                all,
                (0..n).collect::<Vec<_>>(),
                "cosets must partition Z/{n}"
            );
            // Each coset is closed under doubling.
            for c in &cosets {
                for s in c {
                    assert!(c.contains(&((s * 2) % n)));
                }
            }
        }
        // 2 is primitive mod 131 and mod 163, so there are only two
        // cosets and no usable invariant subspace exists at all — the
        // sizes that matter are exactly the ones this construction
        // cannot serve.
        for n in [131u32, 163] {
            assert_eq!(cyclotomic_cosets(n).len(), 2);
            assert_eq!(available_subspace_dimensions(n), vec![0, 1, n - 1, n]);
        }
    }

    #[test]
    fn the_factorisation_is_complete() {
        // One irreducible factor per cyclotomic coset, of that coset's
        // degree — so the degrees sum to n, and the dimensions the
        // divisors reach are exactly the classification's.
        for n in [7u32, 9, 15, 21, 31, 63] {
            let factors = all_factors_of_x_n_minus_1(n);
            assert_eq!(factors.len(), cyclotomic_cosets(n).len(), "n = {n}");
            let degrees: Vec<u32> = factors.iter().map(|f| 63 - f.leading_zeros()).collect();
            assert_eq!(
                degrees.iter().sum::<u32>(),
                n,
                "degrees must sum to n = {n}"
            );

            let mut reach = std::collections::BTreeSet::from([0u32]);
            for d in &degrees {
                for r in reach.clone() {
                    reach.insert(r + d);
                }
            }
            assert_eq!(
                reach.into_iter().collect::<Vec<_>>(),
                available_subspace_dimensions(n),
                "reachable dimensions must match the coset classification at n = {n}"
            );
        }
    }

    #[test]
    fn divisor_factor_bases_are_invariant_and_sized_to_the_divisor() {
        let kc = KoblitzCurve::new(1, 15).unwrap();
        for indices in [vec![1usize], vec![1, 2], vec![1, 2, 3]] {
            let fb = build_frobenius_factor_base_from_divisor(&kc, &indices).unwrap();
            let expected: u32 = indices
                .iter()
                .map(|&i| 63 - all_factors_of_x_n_minus_1(15)[i].leading_zeros())
                .sum();
            assert_eq!(fb.ell, expected, "dimension is the divisor's degree");
            assert_eq!(fb.subspace.len(), 1usize << expected);

            let keys: std::collections::HashSet<_> = fb.points.iter().map(point_key).collect();
            for p in &fb.points {
                assert!(keys.contains(&point_key(&kc.frobenius(p))), "π(F) ⊆ F");
                assert!(keys.contains(&point_key(&point_neg(p))), "−F ⊆ F");
            }
            assert_eq!(
                fb.orbits.iter().map(|o| o.len()).sum::<usize>(),
                fb.points.len()
            );
        }
    }

    #[test]
    fn a_bigger_invariant_subspace_grows_the_base_the_divisor_asks_for() {
        // The point of divisor bases: |F| is tunable, so the summand
        // count m ≈ n/dim a decomposition needs can be brought down to
        // 2 — which also replaces the cubic chained system with a
        // quadratic one.
        let kc = KoblitzCurve::new(1, 7).unwrap();
        let small = build_frobenius_factor_base_from_divisor(&kc, &[1]).unwrap();
        let large = build_frobenius_factor_base_from_divisor(&kc, &[1, 2]).unwrap();
        assert_eq!((small.ell, large.ell), (3, 6));
        assert_eq!(small.points.len(), 15);
        assert_eq!(large.points.len(), 71);
        assert!(large.orbits.len() > small.orbits.len());
    }

    #[test]
    fn a_divisor_base_solves_a_curve_the_single_factor_base_cannot() {
        // K_0 / F_2^31, r = 1 439 393.  One irreducible factor gives
        // dim 5, |F| = 63: at m = 2 the pairs cover ~2 000 of 1.4M group
        // elements so almost nothing decomposes, and m = 4 would need
        // 4·5 + 2·31 = 82 unknowns, past the 64-variable cap.  The
        // construction simply cannot reach this curve.
        //
        // A divisor of x^31 − 1 gives dim 10, |F| = 1179, and m = 2
        // solves it — 20 unknowns, quadratic, no chaining.
        let kc = KoblitzCurve::new(0, 31).unwrap();
        let g = kc.generator().clone();
        let d = BigUint::from(123_456u32);
        let q = kc.mul(&g, &d);

        let single = build_frobenius_factor_base_from_divisor(&kc, &[1]).unwrap();
        assert_eq!((single.ell, single.points.len()), (5, 63));
        assert_eq!(
            single.n_vars_for_summands(31, 4),
            82,
            "m = 4 is over the cap"
        );
        // m = 2 over a 63-point base: sample targets, expect no hits.
        let single_idx = single.index_map();
        let hits = (1..40u32)
            .filter(|k| {
                let t = kc.mul(&g, &BigUint::from(*k));
                enumerate_decompose(&kc, &single, &single_idx, &t, 2).is_some()
            })
            .count();
        assert_eq!(
            hits, 0,
            "dim 5 is far too small for 2-point decompositions here"
        );

        let divisor = build_frobenius_factor_base_from_divisor(&kc, &[1, 2]).unwrap();
        assert_eq!((divisor.ell, divisor.points.len()), (10, 1179));
        assert_eq!(divisor.n_vars_for_summands(31, 2), 20);
        let opts = KoblitzIcOptions {
            m: 2,
            strategy: DecompositionStrategy::Enumerate,
            extra_relations: 8,
            max_trials: 60_000,
            ..KoblitzIcOptions::default()
        };
        let report = koblitz_index_calculus_dlp_with_factor_base(&kc, &q, &divisor, &opts).unwrap();
        assert_eq!(report.log, Some(d), "the divisor base must solve it");
        assert!(!report.direct_relation, "not the degenerate shortcut");
    }

    #[test]
    fn the_cofactor_class_decides_which_m_can_decompose() {
        // Not a size effect: on K_1/F_2^7 (cofactor 2) no factor-base
        // point lies in ⟨G⟩, so a sum of m of them reaches ⟨G⟩ only for
        // even m.  Odd m decomposes nothing however big the base is.
        let kc = KoblitzCurve::new(1, 7).unwrap();
        let g = kc.generator().clone();
        for indices in [vec![1usize], vec![1, 2]] {
            let fb = build_frobenius_factor_base_from_divisor(&kc, &indices).unwrap();
            let index_of = fb.index_map();
            assert!(
                fb.cofactor_classes(&kc)
                    .iter()
                    .all(|c| *c != BinaryPoint::Infinity),
                "no point of this base lies in ⟨G⟩"
            );
            assert_eq!(fb.admissible_summand_counts(&kc, 4), vec![2, 4]);

            // …and the predicate matches what search actually finds.
            for m in 2..=4usize {
                let hits = (1..12u32)
                    .filter(|k| {
                        let t = kc.mul(&g, &BigUint::from(*k));
                        enumerate_decompose(&kc, &fb, &index_of, &t, m).is_some()
                    })
                    .count();
                if fb.m_can_decompose(&kc, m) {
                    assert_eq!(hits, 11, "m = {m} is admissible and should decompose");
                } else {
                    assert_eq!(
                        hits, 0,
                        "m = {m} is inadmissible and must decompose nothing"
                    );
                }
            }
        }
    }

    #[test]
    fn orbit_derived_cofactor_classes_match_pointwise_projection() {
        for (a, n, indices) in [(1, 15, vec![2usize, 4]), (0, 23, vec![0usize, 2])] {
            let kc = KoblitzCurve::new(a, n).unwrap();
            let fb = build_frobenius_factor_base_from_divisor(&kc, &indices).unwrap();
            let pointwise: HashSet<_> = fb.cofactor_classes(&kc).iter().map(point_key).collect();
            let orbit_derived: HashSet<_> = fb
                .distinct_cofactor_classes(&kc)
                .iter()
                .map(point_key)
                .collect();
            assert_eq!(orbit_derived, pointwise, "a={a}, n={n}");
        }
    }

    #[test]
    fn projected_orbit_map_is_algebraic_and_exact() {
        let kc = KoblitzCurve::new(1, 15).unwrap();
        let fb = build_frobenius_factor_base_from_divisor(&kc, &[0, 2]).unwrap();
        let projected = projected_signed_orbit_map(&kc, &fb);
        assert_eq!(
            projected.representatives.len(),
            projected_signed_orbit_count(&kc, &fb)
        );
        assert!(projected.representatives.len() < fb.unknowns());
        for (index, point) in fb.points.iter().enumerate() {
            let expected = kc.mul(point, &kc.cofactor);
            let Some((orbit, k, negated)) = projected.orbit_of[index] else {
                assert_eq!(expected, BinaryPoint::Infinity);
                continue;
            };
            let mut reconstructed = projected.representatives[orbit].clone();
            for _ in 0..k {
                reconstructed = kc.frobenius(&reconstructed);
            }
            if negated {
                reconstructed = point_neg(&reconstructed);
            }
            assert_eq!(reconstructed, expected);
        }
    }

    #[test]
    fn inadmissible_summand_count_stops_before_relation_search() {
        let kc = KoblitzCurve::new(1, 7).unwrap();
        let fb = build_frobenius_factor_base_from_divisor(&kc, &[1]).unwrap();
        let report = koblitz_index_calculus_dlp_with_factor_base(
            &kc,
            kc.generator(),
            &fb,
            &KoblitzIcOptions {
                m: 3,
                strategy: DecompositionStrategy::Sat,
                allow_direct_relation: false,
                collapse_projected_orbits: true,
                ..KoblitzIcOptions::default()
            },
        )
        .unwrap();
        assert!(!report.m_cofactor_admissible);
        assert_eq!(
            (report.trials, report.sat_calls, report.relations),
            (0, 0, 0)
        );
        assert_eq!(report.log, None);
    }

    #[test]
    fn factor_base_is_frobenius_invariant() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        assert_eq!(fb.ell, 6);
        assert_eq!(fb.subspace.len(), 64);

        let keys: std::collections::HashSet<_> = fb.points.iter().map(point_key).collect();
        for p in &fb.points {
            // π(F) = F, and the base is closed under negation too.
            assert!(keys.contains(&point_key(&kc.frobenius(p))));
            assert!(keys.contains(&point_key(&point_neg(p))));
        }

        // Orbit bookkeeping: point = π^k(representative).
        for (i, p) in fb.points.iter().enumerate() {
            let (o, k) = fb.orbit_of[i];
            let mut rep = fb.points[fb.orbits[o][0]].clone();
            for _ in 0..k {
                rep = kc.frobenius(&rep);
            }
            assert_eq!(&rep, p);
        }
        // Signed-orbit bookkeeping additionally identifies -P with P.
        for (i, p) in fb.points.iter().enumerate() {
            let (o, k, negated) = fb.signed_orbit_of[i];
            let mut rep = fb.points[fb.signed_orbits[o][0]].clone();
            for _ in 0..k {
                rep = kc.frobenius(&rep);
            }
            if negated {
                rep = point_neg(&rep);
            }
            assert_eq!(&rep, p);
        }
        // The orbits partition the factor base.
        assert_eq!(
            fb.orbits.iter().map(|o| o.len()).sum::<usize>(),
            fb.points.len()
        );
        assert_eq!(
            fb.signed_orbits.iter().map(|o| o.len()).sum::<usize>(),
            fb.points.len()
        );
        assert!(fb.signed_orbits.len() <= fb.orbits.len());
        let negated_index = fb
            .signed_orbit_of
            .iter()
            .position(|location| location.2)
            .expect("the negation-closed base has a negative representative");
        let (signed_orbit, k, _) = fb.signed_orbit_of[negated_index];
        let relation = relation_from_decomposition(
            &kc,
            &fb,
            &[negated_index],
            &BigUint::zero(),
            &BigUint::zero(),
        );
        let lambda_k = kc.lambda.modpow(&BigUint::from(k), &kc.subgroup_order);
        assert_eq!(relation.row[signed_orbit], &kc.subgroup_order - lambda_k);
        assert_eq!(relation.summand_negated, vec![true]);
        // Collapsing them is where the factor-n saving comes from.
        assert!(fb.unknowns() * 2 < fb.points.len());
    }

    #[test]
    fn subspace_is_closed_under_squaring() {
        let kc = KoblitzCurve::new(1, 9).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let set: std::collections::HashSet<BigUint> =
            fb.subspace.iter().map(|v| v.to_biguint()).collect();
        for v in &fb.subspace {
            let sq = v.square(&kc.curve.irreducible);
            assert!(set.contains(&sq.to_biguint()));
        }
    }

    #[test]
    fn selected_explicit_orbit_base_has_four_relation_columns() {
        let kc = KoblitzCurve::new(1, 19).unwrap();
        let representatives: Vec<_> = [16795u64, 1315, 8461, 6685]
            .into_iter()
            .map(|value| F2mElement::from_biguint(&BigUint::from(value), kc.n))
            .collect();
        let fb = build_explicit_frobenius_orbit_factor_base(&kc, &representatives).unwrap();
        assert_eq!(
            fb.domain,
            FactorBaseDomain::ExplicitFrobeniusOrbits { representatives: 4 }
        );
        assert_eq!(fb.subspace.len(), 76);
        assert_eq!(fb.points.len(), 152);
        assert_eq!(fb.orbits.len(), 8);
        assert_eq!(fb.signed_orbits.len(), 4);
        assert_eq!(fb.unknowns(), 4);
    }

    #[test]
    #[ignore = "seconds; deliberate n=19 selected-base SAT round trip"]
    fn selected_explicit_orbit_base_sat_round_trip_n19() {
        let kc = KoblitzCurve::new(1, 19).unwrap();
        let representatives: Vec<_> = [16795u64, 1315, 8461, 6685]
            .into_iter()
            .map(|value| F2mElement::from_biguint(&BigUint::from(value), kc.n))
            .collect();
        let fb = build_explicit_frobenius_orbit_factor_base(&kc, &representatives).unwrap();
        let index = fb.index_map();
        let target = [203u64, 2143, 2901]
            .into_iter()
            .map(|scalar| kc.mul(kc.generator(), &BigUint::from(scalar)))
            .fold(BinaryPoint::Infinity, |sum, point| kc.add(&sum, &point));
        let field = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let options = SatDecompositionOptions {
            branch_on_summands: true,
            restrict_to_factor_base: true,
            conflict_budget: 2_000_000,
            ..Default::default()
        };
        let (decomposition, stats) =
            sat_decompose_with(&kc, &fb, &index, &field, &target, 3, 1024, None, options);
        eprintln!("selected explicit-orbit SAT stats: {stats:?}");
        assert_eq!(stats.spurious, 0);
        assert!(!stats.exhausted, "selected-base SAT exhausted: {stats:?}");
        let decomposition = decomposition.expect("planted target must decompose");
        let sum = decomposition
            .iter()
            .fold(BinaryPoint::Infinity, |sum, &i| kc.add(&sum, &fb.points[i]));
        assert_eq!(sum, target);
    }

    #[test]
    fn relation_rows_are_consistent_with_the_orbit_logs() {
        // A relation must satisfy h·a + h·b·d ≡ Σ +-λ^k x_o with
        // x_o = log_G([h]·rep_o); check that against brute-forced logs.
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let r = &kc.subgroup_order;
        let g = kc.generator().clone();

        // Brute-force log table for the (tiny) subgroup.
        let mut logs: HashMap<(BigUint, BigUint), BigUint> = HashMap::new();
        let mut acc = BinaryPoint::Infinity;
        let mut i = BigUint::zero();
        while &i < r {
            logs.insert(point_key(&acc), i.clone());
            acc = kc.add(&acc, &g);
            i += BigUint::one();
        }

        let mut index_of = HashMap::new();
        for (idx, p) in fb.points.iter().enumerate() {
            index_of.insert(point_key(p), idx);
        }
        let a = BigUint::from(11u32);
        let b = BigUint::from(23u32);
        let d = BigUint::from(37u32);
        let q = kc.mul(&g, &d);
        let target = kc.add(&kc.mul(&g, &a), &kc.mul(&q, &b));
        let idxs = decompose(&kc, &fb, &index_of, &target, 2, 0)
            .expect("a 2-point decomposition exists for this target");
        let rel = relation_from_decomposition(&kc, &fb, &idxs, &a, &b);

        let h = &kc.cofactor % r;
        let lhs = (&h * &a + &h * &b * &d) % r;
        let mut rhs = BigUint::zero();
        for (o, coeff) in rel.row.iter().enumerate() {
            if coeff.is_zero() {
                continue;
            }
            let rep = fb.points[fb.signed_orbits[o][0]].clone();
            let scaled = kc.mul(&rep, &kc.cofactor);
            let x_o = logs.get(&point_key(&scaled)).expect("in ⟨G⟩ after ×h");
            rhs = (rhs + coeff * x_o) % r;
        }
        assert_eq!(lhs, rhs);
    }

    #[test]
    fn reciprocal_saturation_preserves_projection_and_contains_the_base() {
        let kc = KoblitzCurve::new(1, 15).unwrap();
        let fb = build_frobenius_factor_base_from_divisor(&kc, &[0, 3]).unwrap();
        let saturated = saturate_factor_base_two_torsion(&kc, &fb).unwrap();
        let keys: std::collections::HashSet<_> = saturated.points.iter().map(point_key).collect();
        for p in &fb.points {
            assert!(keys.contains(&point_key(p)));
        }
        let project = |base: &FrobeniusFactorBase| -> std::collections::HashSet<_> {
            base.points
                .iter()
                .map(|p| point_key(&kc.mul(p, &kc.cofactor)))
                .collect()
        };
        assert_eq!(project(&fb), project(&saturated));
        let t = points_with_x(&kc.curve, &F2mElement::zero(kc.n)).remove(0);
        for p in &saturated.points {
            assert!(keys.contains(&point_key(&kc.frobenius(p))));
            if let BinaryPoint::Affine { x, .. } = p {
                if !x.is_zero() {
                    let BinaryPoint::Affine {
                        x: translated_x, ..
                    } = kc.add(p, &t)
                    else {
                        panic!("non-torsion point");
                    };
                    assert_eq!(
                        x.mul(&translated_x, &kc.curve.irreducible),
                        F2mElement::one(kc.n)
                    );
                }
            }
        }
    }

    #[test]
    fn domain_trie_accepts_exactly_the_allowed_coordinates() {
        use crate::cryptanalysis::sat::{SolveResult, Solver};
        for ell in 1..=5usize {
            for mode in 0..4 {
                let codes: Vec<_> = (0..(1u64 << ell))
                    .filter(|x| match mode {
                        0 => false,
                        1 => true,
                        2 => x % 3 == 0,
                        _ => x & 1 == 1,
                    })
                    .collect();
                for x in 0..(1u64 << ell) {
                    let mut solver = Solver::new(ell as u32 + 2);
                    add_coordinate_domain(&mut solver, 2, ell, &codes);
                    for j in 0..ell {
                        let lit = (j + 3) as i32;
                        solver.add_clause(vec![if (x >> j) & 1 == 1 { lit } else { -lit }]);
                    }
                    assert_eq!(solver.solve() == SolveResult::Sat, codes.contains(&x));
                }
            }
        }
    }

    #[test]
    fn frobenius_union_domain_is_invariant_and_sat_matches_search() {
        let kc = KoblitzCurve::new(1, 7).unwrap();
        let basis = vec![F2mElement::one(7), F2mElement::from_bit_positions(&[1], 7)];
        let fb = build_frobenius_union_factor_base(&kc, &basis).unwrap();
        let keys: std::collections::HashSet<_> = fb.points.iter().map(point_key).collect();
        for p in &fb.points {
            assert!(keys.contains(&point_key(&kc.frobenius(p))));
            assert!(keys.contains(&point_key(&point_neg(p))));
        }
        assert!(matches!(
            fb.domain,
            FactorBaseDomain::FrobeniusUnion { seed_dimension: 2 }
        ));
        let index = fb.index_map();
        let st = FieldStructure::new(7, &kc.curve.irreducible);
        for m in [2, 3] {
            for k in 1u32..=6 {
                let target = kc.mul(kc.generator(), &BigUint::from(k));
                let reference = enumerate_decompose(&kc, &fb, &index, &target, m);
                let (out, stats) = sat_decompose_with(
                    &kc,
                    &fb,
                    &index,
                    &st,
                    &target,
                    m,
                    128,
                    None,
                    SatDecompositionOptions {
                        conflict_budget: 100_000,
                        ..Default::default()
                    },
                );
                assert_eq!(stats.spurious, 0);
                assert!(!stats.exhausted);
                assert_eq!(out.is_some(), reference.is_some());
            }
        }
    }

    #[test]
    fn trace_bit_is_a_group_homomorphism_including_torsion() {
        for a in [0, 1] {
            let kc = KoblitzCurve::new(a, 7).unwrap();
            let delta = |p: &BinaryPoint| match p {
                BinaryPoint::Infinity => false,
                BinaryPoint::Affine { x, .. } => {
                    absolute_trace_bit(x, kc.n, &kc.curve.irreducible) ^ (a == 1)
                }
            };
            let torsion = points_with_x(&kc.curve, &F2mElement::zero(kc.n)).remove(0);
            for x in 0..(1u32 << kc.n) {
                let x = F2mElement::from_biguint(&BigUint::from(x), kc.n);
                for p in points_with_x(&kc.curve, &x) {
                    for q in [&p, &point_neg(&p), kc.generator(), &torsion] {
                        assert_eq!(delta(&kc.add(&p, q)), delta(&p) ^ delta(q));
                    }
                }
            }
        }
    }

    #[test]
    fn native_sat_domain_filter_preserves_group_decompositions() {
        for (a, n, m) in [(1, 7, 2), (0, 9, 3)] {
            let kc = KoblitzCurve::new(a, n).unwrap();
            let fb = build_frobenius_factor_base(&kc, 0).unwrap();
            let index = fb.index_map();
            let st = FieldStructure::new(n, &kc.curve.irreducible);
            for k in 1u32..=6 {
                let target = kc.mul(kc.generator(), &BigUint::from(k));
                let reference = enumerate_decompose(&kc, &fb, &index, &target, m);
                for restrict in [false, true] {
                    let (out, stats) = sat_decompose_with(
                        &kc,
                        &fb,
                        &index,
                        &st,
                        &target,
                        m,
                        128,
                        None,
                        SatDecompositionOptions {
                            restrict_to_factor_base: restrict,
                            conflict_budget: 1_000_000,
                            ..Default::default()
                        },
                    );
                    assert!(!stats.exhausted);
                    assert_eq!(stats.spurious, 0);
                    assert_eq!(out.is_some(), reference.is_some());
                    assert_eq!(stats.refuted, out.is_none());
                    if let Some(ids) = out {
                        let sum = ids
                            .iter()
                            .fold(BinaryPoint::Infinity, |p, &i| kc.add(&p, &fb.points[i]));
                        assert_eq!(sum, target);
                    }
                }
            }
        }
    }

    #[test]
    fn sparse_and_exhaustive_irreducible_searches_agree_up_to_the_old_cap() {
        // KoblitzCurve::new now uses the sparse search; every field
        // representation a fixture could have been generated with before
        // is unchanged.
        for n in 3..=24u32 {
            let full = find_irreducible(n).expect("exhaustive search finds one");
            let sparse = find_irreducible_sparse(n).expect("sparse search finds one");
            assert_eq!(
                (full.degree, full.low_terms),
                (sparse.degree, sparse.low_terms),
                "n = {n}"
            );
        }
    }

    #[test]
    fn pair_table_agrees_with_enumeration_for_two_three_and_four_summands() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let index = fb.index_map();
        let table = PairSumTable::build(&kc, &fb).unwrap();
        assert_eq!(table.len(), fb.points.len() * (fb.points.len() + 1) / 2);
        let r = kc.subgroup_order.to_u64_digits()[0];
        for m in [2usize, 3, 4] {
            // m = 4 costs |F|³ per enumerated target; keep that one short.
            let scalars: Vec<u64> = if m == 4 {
                (1..=12).collect()
            } else {
                (1..r).collect()
            };
            for k in scalars {
                let target = kc.mul(kc.generator(), &BigUint::from(k));
                let reference = enumerate_decompose(&kc, &fb, &index, &target, m);
                let tabled = table.decompose(&kc, &fb, &target, m);
                assert_eq!(tabled.is_some(), reference.is_some(), "m = {m}, k = {k}");
                if let Some(idxs) = tabled {
                    assert_eq!(idxs.len(), m);
                    assert!(idxs.windows(2).all(|w| w[0] <= w[1]));
                    let sum = idxs
                        .iter()
                        .fold(BinaryPoint::Infinity, |s, &i| kc.add(&s, &fb.points[i]));
                    assert_eq!(sum, target);
                }
            }
        }
        // Every witness the table enumerates is genuine and distinct.
        let target = kc.mul(kc.generator(), &BigUint::from(53u32));
        let mut seen = HashSet::new();
        table.witnesses(&kc, &fb, &target, 3, &mut |idxs| {
            let sum = idxs
                .iter()
                .fold(BinaryPoint::Infinity, |s, &i| kc.add(&s, &fb.points[i]));
            assert_eq!(sum, target);
            assert!(seen.insert(idxs.to_vec()), "duplicate witness {idxs:?}");
            true
        });
    }

    #[test]
    fn crossbred_decompose_agrees_with_enumeration() {
        // The oracle gate for `DecompositionStrategy::Crossbred`: on every
        // target of the subgroup, the crossbred search must find a
        // decomposition exactly when exhaustive enumeration does, and the
        // witness it returns must sum to the target.  A `None` carrying
        // `exhausted` is "cannot say" and is not held to the first half.
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let index = fb.index_map();
        let field = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let r = kc.subgroup_order.to_u64_digits()[0];
        let mut decided = 0usize;
        for k in 1..r {
            let target = kc.mul(kc.generator(), &BigUint::from(k));
            let reference = enumerate_decompose(&kc, &fb, &index, &target, 2);
            let (found, stats) = crossbred_decompose(&kc, &fb, &index, &field, &target, 2, None);
            if let Some(idxs) = &found {
                let sum = idxs
                    .iter()
                    .fold(BinaryPoint::Infinity, |s, &i| kc.add(&s, &fb.points[i]));
                assert_eq!(sum, target, "k = {k}: witness does not sum to the target");
                assert!(reference.is_some(), "k = {k}: invented a decomposition");
            }
            if !stats.exhausted {
                decided += 1;
                assert_eq!(
                    found.is_some(),
                    reference.is_some(),
                    "k = {k}: disagrees with enumeration"
                );
            }
        }
        assert!(
            decided > 0,
            "every target came back exhausted; nothing was tested"
        );
    }

    #[test]
    fn packed_point_keys_are_injective() {
        let kc = KoblitzCurve::new(1, 11).unwrap();
        let mut keys = HashSet::new();
        let mut count = 1usize;
        keys.insert(pack_point(&BinaryPoint::Infinity));
        for raw in 0..(1u64 << kc.n) {
            let x = F2mElement::from_biguint(&BigUint::from(raw), kc.n);
            for p in points_with_x(&kc.curve, &x) {
                assert!(keys.insert(pack_point(&p)), "collision at {p:?}");
                count += 1;
            }
        }
        assert_eq!(BigUint::from(count), kc.group_order);
    }

    #[test]
    fn pruned_subspace_bases_keep_every_oracle_honest() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let parent = build_frobenius_factor_base_from_divisor(&kc, &[1, 2]).unwrap();
        assert!(parent.signed_orbits.len() >= 4);
        let keep: Vec<usize> = (0..parent.signed_orbits.len()).step_by(2).collect();
        let fb = restrict_factor_base_to_orbits(&kc, &parent, &keep).unwrap();
        assert_eq!(
            fb.domain,
            FactorBaseDomain::SubspaceSubset {
                retained_orbits: keep.len()
            }
        );
        assert_eq!(fb.signed_orbits.len(), keep.len());
        assert_eq!(fb.subspace_basis, parent.subspace_basis);
        assert!(!fb.uses_ambient_basis());
        let parent_keys: HashSet<_> = parent.points.iter().map(point_key).collect();
        assert!(fb
            .points
            .iter()
            .all(|p| parent_keys.contains(&point_key(p))));
        let index = fb.index_map();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let table = PairSumTable::build(&kc, &fb).unwrap();
        let mut found = 0;
        for m in [2usize, 3] {
            for k in 1u32..=40 {
                let target = kc.mul(kc.generator(), &BigUint::from(k));
                let reference = enumerate_decompose(&kc, &fb, &index, &target, m);
                assert_eq!(
                    table.decompose(&kc, &fb, &target, m).is_some(),
                    reference.is_some()
                );
                let (sat, stats) = sat_decompose_with(
                    &kc,
                    &fb,
                    &index,
                    &st,
                    &target,
                    m,
                    256,
                    Some(2),
                    SatDecompositionOptions {
                        conflict_budget: 1_000_000,
                        ..Default::default()
                    },
                );
                assert_eq!(stats.spurious, 0);
                assert!(!stats.exhausted, "m = {m}, k = {k}: {stats:?}");
                assert_eq!(sat.is_some(), reference.is_some(), "m = {m}, k = {k}");
                if let Some(idxs) = sat {
                    // Only retained points may appear.
                    assert!(idxs.iter().all(|&i| i < fb.points.len()));
                    let sum = idxs
                        .iter()
                        .fold(BinaryPoint::Infinity, |s, &i| kc.add(&s, &fb.points[i]));
                    assert_eq!(sum, target);
                    found += 1;
                }
                let (groebner, _) = groebner_decompose(
                    &kc,
                    &fb,
                    &index,
                    &st,
                    &target,
                    m,
                    SolverEngine::default(),
                    20_000,
                );
                assert_eq!(
                    groebner.is_some(),
                    reference.is_some(),
                    "F4 m = {m}, k = {k}"
                );
            }
        }
        assert!(found > 0, "the pruned base must still decompose something");
    }

    #[test]
    fn lex_leader_constraint_admits_exactly_the_sorted_pairs() {
        use crate::cryptanalysis::sat::Solver;
        for width in 1..=4usize {
            let mut solver = Solver::new(2 * width as u32);
            add_lex_leq(&mut solver, 1, width as u32 + 1, width);
            let mut models = HashSet::new();
            loop {
                if solver.solve() != SolveResult::Sat {
                    break;
                }
                let model = solver.model();
                let code = |first: usize| {
                    (0..width).fold(0u32, |acc, t| acc | (u32::from(model[first + t]) << t))
                };
                let (a, b) = (code(0), code(width));
                assert!(a <= b, "width {width}: {a} > {b}");
                assert!(models.insert((a, b)));
                solver.reset_search();
                let clause = (0..2 * width)
                    .map(|i| {
                        if model[i] {
                            -((i + 1) as i32)
                        } else {
                            (i + 1) as i32
                        }
                    })
                    .collect();
                solver.add_clause(clause);
            }
            let total = 1u32 << width;
            assert_eq!(
                models.len() as u32,
                total * (total + 1) / 2,
                "width {width}"
            );
        }
    }

    #[test]
    fn symmetry_breaking_changes_no_sat_verdict() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let index = fb.index_map();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        for m in [2usize, 3] {
            for k in 1u32..=24 {
                let target = kc.mul(kc.generator(), &BigUint::from(k));
                let reference = enumerate_decompose(&kc, &fb, &index, &target, m);
                let (out, stats) = sat_decompose_with(
                    &kc,
                    &fb,
                    &index,
                    &st,
                    &target,
                    m,
                    256,
                    Some(2),
                    SatDecompositionOptions {
                        symmetry_breaking: true,
                        conflict_budget: 2_000_000,
                        ..Default::default()
                    },
                );
                assert_eq!(stats.spurious, 0);
                assert!(!stats.exhausted, "m = {m}, k = {k}: {stats:?}");
                assert_eq!(out.is_some(), reference.is_some(), "m = {m}, k = {k}");
                if let Some(idxs) = out {
                    let sum = idxs
                        .iter()
                        .fold(BinaryPoint::Infinity, |s, &i| kc.add(&s, &fb.points[i]));
                    assert_eq!(sum, target);
                }
            }
        }
    }

    #[test]
    fn curves_past_the_old_cap_construct_with_a_consistent_frobenius_eigenvalue() {
        // Only these degrees above 24 have a prime-order subgroup larger
        // than its cofactor; the others are rejected by the constructor.
        for (a, n, r) in [(1u8, 29u32, 42_457u64), (0, 31, 1_439_393)] {
            let kc = KoblitzCurve::new(a, n).expect("usable curve");
            assert_eq!(kc.subgroup_order, BigUint::from(r));
            let g = kc.generator().clone();
            assert_eq!(kc.mul(&g, &kc.subgroup_order), BinaryPoint::Infinity);
            for k in [2u32, 3, 1000] {
                let p = kc.mul(&g, &BigUint::from(k));
                assert_eq!(kc.frobenius(&p), kc.mul(&p, &kc.lambda));
            }
        }
        for (a, n) in [(0u8, 25u32), (1, 27), (1, 33)] {
            assert!(KoblitzCurve::new(a, n).is_none(), "K_{a}/2^{n}");
        }
    }

    #[test]
    fn factor_base_logs_precompute_and_descend_every_target() {
        // The CADO split: solve the column logs once, then recover every
        // target with a single descent, and cross-check against both a
        // brute-forced discrete log and the plain matrix driver.
        // Bases whose projected columns a two-summand relation search
        // determines in full (high coverage), so the whole log vector
        // is solvable: K_0/2^9 (3 columns) and K_1/2^11 (45 columns).
        for (a, n) in [(0u8, 9u32), (1, 11)] {
            let kc = KoblitzCurve::new(a, n).unwrap();
            let fb = build_frobenius_factor_base(&kc, 0).unwrap();
            let opts = KoblitzIcOptions {
                m: 2,
                strategy: DecompositionStrategy::PairTable,
                collapse_negation: true,
                collapse_projected_orbits: true,
                allow_direct_relation: false,
                max_trials: 20_000,
                ..KoblitzIcOptions::default()
            };
            let (table, report) = solve_factor_base_logs(&kc, &fb, &opts).unwrap();
            assert!(report.verified, "K_{a}/2^{n}: log table did not verify");
            assert!(table.verify(&kc));
            assert_eq!(table.len(), report.columns);
            // Every column really is the log of its point.
            for (point, log) in &table.columns {
                assert_eq!(&kc.mul(kc.generator(), log), point);
                assert!(*point != BinaryPoint::Infinity);
            }
            // Descend a batch of known-answer targets; one shared table.
            let r = kc.subgroup_order.to_u64_digits()[0];
            let g = kc.generator().clone();
            for k in [1u64, 2, 7, 53, r / 2, r - 1] {
                let expected = BigUint::from(k % r);
                let q = kc.mul(&g, &expected);
                let (recovered, ir) = individual_log(&kc, &fb, &table, &q, &opts)
                    .unwrap_or_else(|| panic!("K_{a}/2^{n}: no descent for k = {k}"));
                assert_eq!(recovered, expected, "K_{a}/2^{n} k = {k}");
                assert_eq!(ir.log.as_ref(), Some(&expected));
                assert!(ir.trials >= 1);
                assert_eq!(kc.mul(&g, &recovered), q);
            }
            // O has logarithm 0 without any probing.
            let (zero, _) =
                individual_log(&kc, &fb, &table, &BinaryPoint::Infinity, &opts).unwrap();
            assert!(zero.is_zero());
        }
    }

    #[test]
    fn a_wrong_column_log_fails_the_table_verification() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let opts = KoblitzIcOptions {
            strategy: DecompositionStrategy::Enumerate,
            allow_direct_relation: false,
            ..KoblitzIcOptions::default()
        };
        let (mut table, report) = solve_factor_base_logs(&kc, &fb, &opts).unwrap();
        assert!(report.verified && table.verify(&kc));
        // Corrupt one logarithm; verification must catch it.
        table.columns[0].1 = (&table.columns[0].1 + BigUint::one()) % &kc.subgroup_order;
        assert!(!table.verify(&kc));
    }

    #[test]
    fn sparse_and_dense_linear_algebra_certify_the_same_log_table() {
        // Same curve, base, oracle and seed: the two linear-algebra paths
        // see the same relations and must certify the same logarithms.
        // (The bases whose two-summand coverage determines every column:
        // K_0/2^9 with 3 columns, K_1/2^11 with 45.)
        for (a, n) in [(0u8, 9u32), (1, 11)] {
            let kc = KoblitzCurve::new(a, n).unwrap();
            let fb = build_frobenius_factor_base(&kc, 0).unwrap();
            let base = KoblitzIcOptions {
                m: 2,
                strategy: DecompositionStrategy::PairTable,
                collapse_negation: true,
                collapse_projected_orbits: true,
                allow_direct_relation: false,
                max_trials: 40_000,
                ..KoblitzIcOptions::default()
            };
            let dense = KoblitzIcOptions {
                linear_algebra: LinearAlgebra::Dense,
                ..base.clone()
            };
            let sparse = KoblitzIcOptions {
                linear_algebra: LinearAlgebra::Sparse(SparseSolveOptions {
                    wiedemann: koblitz_sparse_la::BlockWiedemannOptions {
                        block_m: 2,
                        block_n: 3,
                        margin: 8,
                    },
                    ..SparseSolveOptions::default()
                }),
                ..base.clone()
            };
            let (dt, dr) = solve_factor_base_logs(&kc, &fb, &dense).unwrap();
            let (st, sr) = solve_factor_base_logs(&kc, &fb, &sparse).unwrap();
            assert!(
                dr.verified && !dr.sparse && dr.sparse_report.is_none(),
                "K_{a}/2^{n} dense"
            );
            assert!(sr.verified && sr.sparse, "K_{a}/2^{n} sparse: {sr:?}");
            assert!(dt.verify(&kc) && st.verify(&kc));
            assert_eq!(
                dt.columns, st.columns,
                "K_{a}/2^{n}: the two paths disagree"
            );
            let srep = sr.sparse_report.as_ref().expect("sparse statistics");
            assert_eq!(srep.filter.columns_in, st.len());
            assert_eq!(srep.core_dimension + srep.reconstructed_columns, st.len());
            assert!(sr.solve_attempts >= 1 && dr.solve_attempts >= 1);
            assert!(sr.linear_algebra_seconds >= 0.0);
            // The sparse path never attempts a solve before every column
            // is covered, so it needs at least as many relations as
            // columns and no more attempts than the dense path.
            assert!(sr.relations >= st.len());
            assert!(
                sr.solve_attempts <= dr.solve_attempts,
                "K_{a}/2^{n}: {} > {}",
                sr.solve_attempts,
                dr.solve_attempts
            );
        }
    }

    fn collector_options() -> KoblitzIcOptions {
        KoblitzIcOptions {
            m: 2,
            strategy: DecompositionStrategy::PairTable,
            collapse_negation: true,
            collapse_projected_orbits: true,
            allow_direct_relation: false,
            max_trials: 40_000,
            ..KoblitzIcOptions::default()
        }
    }

    /// The window options a windowed-collection test uses.
    fn windowed_options(window: usize) -> KoblitzIcOptions {
        KoblitzIcOptions {
            m: 3,
            strategy: DecompositionStrategy::PairTable,
            collection_window: Some(window),
            collapse_negation: true,
            collapse_projected_orbits: true,
            allow_direct_relation: false,
            max_trials: 200_000,
            ..KoblitzIcOptions::default()
        }
    }

    /// The general orbit map, with the single-word path removed, so the
    /// fast one can be checked against it rather than against itself.
    fn projected_signed_orbit_map_general(
        kc: &KoblitzCurve,
        fb: &FrobeniusFactorBase,
    ) -> (Vec<Option<(usize, u32, bool)>>, Vec<BinaryPoint>) {
        let projected: Vec<_> = fb
            .points
            .iter()
            .map(|point| kc.mul(point, &kc.cofactor))
            .collect();
        let mut representatives: Vec<BinaryPoint> = Vec::new();
        let mut seen = HashSet::new();
        for point in &projected {
            if *point == BinaryPoint::Infinity || seen.contains(&point_key(point)) {
                continue;
            }
            let mut current = point.clone();
            let mut canonical = point.clone();
            let mut canonical_key = point_key(point);
            for _ in 0..kc.n {
                for candidate in [current.clone(), point_neg(&current)] {
                    let key = point_key(&candidate);
                    seen.insert(key.clone());
                    if key < canonical_key {
                        canonical = candidate;
                        canonical_key = key;
                    }
                }
                current = kc.frobenius(&current);
            }
            representatives.push(canonical);
        }
        representatives.sort_by_key(point_key);
        let mut location_by_key = HashMap::new();
        for (orbit, representative) in representatives.iter().enumerate() {
            let mut current = representative.clone();
            for k in 0..kc.n {
                location_by_key
                    .entry(point_key(&current))
                    .or_insert((orbit, k, false));
                location_by_key
                    .entry(point_key(&point_neg(&current)))
                    .or_insert((orbit, k, true));
                current = kc.frobenius(&current);
            }
        }
        let orbit_of = projected
            .iter()
            .map(|point| {
                (*point != BinaryPoint::Infinity).then(|| {
                    *location_by_key
                        .get(&point_key(point))
                        .expect("in its orbit")
                })
            })
            .collect();
        (orbit_of, representatives)
    }

    #[test]
    fn the_signed_frobenius_orbit_closes_the_pair_sums() {
        // The fold is only sound because the set of pair sums is closed
        // under `π` and negation.  That is one line of algebra —
        // `π(P + Q) = π(P) + π(Q)` — and this is the line being checked
        // against the actual base the pipeline builds.
        for degree in [13u32, 19, 23] {
            let kc = KoblitzCurve::new(0, degree).unwrap();
            let fb = build_subgroup_orbit_factor_base(&kc, 1, 60).unwrap();
            let fc = FastCurve::new(&kc.curve).unwrap();
            let points: Vec<FastPoint> = fb.points.iter().map(|p| fc.lift(p)).collect();
            let base: HashSet<u64> = points.iter().map(|p| p.pack()).collect();
            for &p in &points {
                assert!(base.contains(&fc.neg(p).pack()), "base not negation-closed");
                assert!(
                    base.contains(&fc.frobenius_k(p, 1).pack()),
                    "base not Frobenius-closed"
                );
            }
            let mut sums = HashSet::new();
            for i in 0..points.len() {
                for j in i..points.len() {
                    sums.insert(fc.add(points[i], points[j]).pack());
                }
            }
            for i in 0..points.len() {
                for j in i..points.len() {
                    let s = fc.add(points[i], points[j]);
                    assert!(sums.contains(&fc.neg(s).pack()), "sums not negation-closed");
                    assert!(
                        sums.contains(&fc.frobenius_k(s, 1).pack()),
                        "sums not Frobenius-closed"
                    );
                }
            }
        }
    }

    #[test]
    fn the_fold_is_exactly_two_n_and_reaches_every_orbit() {
        // Two claims the memory law rests on: the fold is worth `2n`,
        // not some smaller factor, and walking one representative per
        // signed orbit against the whole base reaches every orbit — so
        // the folded table has no false negatives.
        for degree in [13u32, 19, 23] {
            let kc = KoblitzCurve::new(0, degree).unwrap();
            let fb = build_subgroup_orbit_factor_base(&kc, 1, 60).unwrap();
            let fc = FastCurve::new(&kc.curve).unwrap();
            let points: Vec<FastPoint> = fb.points.iter().map(|p| fc.lift(p)).collect();

            let mut keys = HashSet::new();
            let mut orbits = HashSet::new();
            for i in 0..points.len() {
                for j in i..points.len() {
                    let s = fc.add(points[i], points[j]);
                    keys.insert(s.pack());
                    orbits.insert(PairSumTable::canon_key(&fc, s));
                }
            }
            let fold = keys.len() as f64 / orbits.len() as f64;
            let want = 2.0 * degree as f64;
            assert!(
                (fold - want).abs() < 0.15 * want,
                "degree {degree}: fold {fold:.1}, expected about {want}"
            );

            let reached: HashSet<u64> = fb
                .signed_orbits
                .iter()
                .filter_map(|o| o.first().copied())
                .flat_map(|r| {
                    points
                        .iter()
                        .map(|&q| PairSumTable::canon_key(&fc, fc.add(points[r], q)))
                        .collect::<Vec<_>>()
                })
                .collect();
            assert_eq!(
                reached, orbits,
                "degree {degree}: reps x base missed a sum orbit"
            );
        }
    }

    #[test]
    fn the_rotation_names_the_same_orbits_as_the_squaring_chain() {
        // The normal basis renames every orbit — the least rotation of
        // the coordinates is not the least element of the orbit — and
        // must partition the field exactly as the squaring chain does,
        // since that partition is what the folded table indexes by.
        for degree in [13u32, 19, 23, 31, 53, 61] {
            let kc = KoblitzCurve::new(0, degree).unwrap();
            let fc = FastCurve::new(&kc.curve).unwrap();
            let canon = FrobeniusCanon::new(&fc.field, fc.n)
                .unwrap_or_else(|| panic!("degree {degree}: no normal element found"));
            assert_eq!(canon.degree(), degree);
            let mask = (1u64 << degree) - 1;
            // A rotation is constant on a Frobenius orbit.
            let mut x = 1u64;
            let mut sample = Vec::new();
            for _ in 0..2000 {
                x = x.wrapping_mul(0x9e37_79b9_7f4a_7c15) ^ (x >> 31);
                sample.push(x & mask);
            }
            for &v in &sample {
                let mut w = v;
                for _ in 0..degree {
                    w = fc.field.sqr(w);
                    assert_eq!(
                        canon.canon(v),
                        canon.canon(w),
                        "degree {degree}: the rotation moved within an orbit"
                    );
                }
            }
            // And it separates points the squaring chain separates: the
            // two induce the same equivalence relation.
            let chain = |v: u64| {
                let mut x = v;
                let mut best = v;
                for _ in 1..degree {
                    x = fc.field.sqr(x);
                    best = best.min(x);
                }
                best
            };
            let mut by_chain: HashMap<u64, u64> = HashMap::new();
            for &v in &sample {
                let c = chain(v);
                let r = canon.canon(v);
                match by_chain.entry(c) {
                    std::collections::hash_map::Entry::Occupied(e) => assert_eq!(
                        *e.get(),
                        r,
                        "degree {degree}: one orbit got two rotation names"
                    ),
                    std::collections::hash_map::Entry::Vacant(e) => {
                        e.insert(r);
                    }
                }
            }
            let names: HashSet<u64> = by_chain.values().copied().collect();
            assert_eq!(
                names.len(),
                by_chain.len(),
                "degree {degree}: two orbits shared a rotation name"
            );
        }
    }

    #[test]
    fn the_folded_table_answers_exactly_as_the_full_one() {
        for (degree, points) in [(19u32, 300usize), (31, 400), (61, 400)] {
            the_folded_table_agrees_at(degree, points);
        }
    }

    fn the_folded_table_agrees_at(degree: u32, points: usize) {
        let kc = KoblitzCurve::new(0, degree).unwrap();
        let fb = build_subgroup_orbit_factor_base(&kc, 3, points).unwrap();
        let full = PairSumTable::build(&kc, &fb).unwrap();
        let orbits = fb.signed_orbits.len();
        // A budget under the compact table's width but over the folded
        // one's is exactly the tier that reaches for the fold.
        let folded = PairSumTable::build_within(
            &kc,
            &fb,
            PairSumTable::folded_byte_size(orbits, fb.points.len(), kc.n),
        )
        .expect("the folded table fits its own budget");
        assert!(
            folded.is_folded(),
            "degree {degree}: expected the fold tier"
        );
        assert!(
            folded.len() < full.len(),
            "degree {degree}: the fold stored no less"
        );
        // A folded table keeps no summands, so `lookup` must say so
        // rather than slice an empty `entries`.
        assert!(folded.lookup(1_000_001).is_empty());

        let fc = FastCurve::new(&kc.curve).unwrap();
        let g = fc.lift(kc.generator());
        let mut hits = 0usize;
        let mut misses = 0usize;
        for t in 1u64..900 {
            let target = fc.mul_u64(g, t);
            if target.infinity {
                continue;
            }
            let mut a = Vec::new();
            let mut b = Vec::new();
            full.pairs_for(target, &mut a);
            folded.pairs_for(target, &mut b);
            a.sort_unstable();
            b.sort_unstable();
            assert_eq!(a, b, "degree {degree}: disagreed on [{t}]G");
            if a.is_empty() {
                misses += 1;
            } else {
                hits += 1;
            }
        }
        for i in 0..fb.points.len().min(64) {
            for j in i..fb.points.len().min(64) {
                let sum = fc.add(fc.lift(&fb.points[i]), fc.lift(&fb.points[j]));
                if sum.infinity {
                    continue;
                }
                let mut a = Vec::new();
                let mut b = Vec::new();
                full.pairs_for(sum, &mut a);
                folded.pairs_for(sum, &mut b);
                a.sort_unstable();
                b.sort_unstable();
                assert!(a.contains(&(i as u32, j as u32)));
                assert_eq!(a, b, "degree {degree}: disagreed on a stored pair sum");
                hits += 1;
            }
        }
        assert!(
            hits > 0 && misses > 0,
            "degree {degree}: the test checked only one side"
        );
    }

    #[test]
    fn the_folded_table_answers_the_degenerate_key_too() {
        // `O` is the sum of every `±` pair, so every orbit
        // representative stores an entry under its key: the one target
        // whose lookup offers every orbit at once.  It is the worst case
        // the orbit tag has, and it has to give the same answer as the
        // full table and take a sane amount of time doing it.
        let kc = KoblitzCurve::new(0, 19).unwrap();
        let fb = build_subgroup_orbit_factor_base(&kc, 3, 400).unwrap();
        let full = PairSumTable::build(&kc, &fb).unwrap();
        let folded = PairSumTable::build_within(
            &kc,
            &fb,
            PairSumTable::folded_byte_size(fb.signed_orbits.len(), fb.points.len(), kc.n),
        )
        .unwrap();
        assert!(folded.is_folded());
        let mut a = Vec::new();
        let mut b = Vec::new();
        full.pairs_for(FastPoint::INFINITY, &mut a);
        folded.pairs_for(FastPoint::INFINITY, &mut b);
        a.sort_unstable();
        a.dedup();
        b.sort_unstable();
        b.dedup();
        assert_eq!(a, b, "the two disagreed on the point at infinity");
        // And every pair it names really does sum to `O`.
        let fc = FastCurve::new(&kc.curve).unwrap();
        for &(i, j) in &b {
            let sum = fc.add(
                fc.lift(&fb.points[i as usize]),
                fc.lift(&fb.points[j as usize]),
            );
            assert!(sum.infinity, "({i}, {j}) does not sum to O");
        }
    }

    #[test]
    fn the_orbit_tag_really_names_a_summand_of_the_key() {
        // The claim the tag rests on: a folded entry was built as
        // `canon(P_rep(r) + P_j)`, so any target with that key satisfies
        // `g·target = P_rep(r) + P_j` for some `g ∈ G` and therefore has
        // a summand in signed orbit `r`, orbits being what `G` preserves.
        // Recovery walks only that orbit, so if the claim were false the
        // table would report no witness for a target that has one.
        for (degree, points) in [(19u32, 300usize), (31, 400)] {
            let kc = KoblitzCurve::new(0, degree).unwrap();
            let fb = build_subgroup_orbit_factor_base(&kc, 3, points).unwrap();
            let folded = PairSumTable::build_within(
                &kc,
                &fb,
                PairSumTable::folded_byte_size(fb.signed_orbits.len(), fb.points.len(), kc.n),
            )
            .unwrap();
            assert!(folded.is_folded());
            let fc = FastCurve::new(&kc.curve).unwrap();
            let mut checked = 0usize;
            let mut out = Vec::new();
            for i in 0..fb.points.len().min(48) {
                for j in i..fb.points.len().min(48) {
                    let sum = fc.add(fc.lift(&fb.points[i]), fc.lift(&fb.points[j]));
                    if sum.infinity {
                        continue;
                    }
                    folded.pairs_for(sum, &mut out);
                    assert!(
                        out.contains(&(i as u32, j as u32)),
                        "degree {degree}: the orbit tag lost the pair ({i}, {j})"
                    );
                    // Every pair the tag leads to is a real one.
                    for &(a, b) in &out {
                        let s = fc.add(
                            fc.lift(&fb.points[a as usize]),
                            fc.lift(&fb.points[b as usize]),
                        );
                        assert_eq!(s, sum, "degree {degree}: ({a}, {b}) is not a summand pair");
                    }
                    checked += 1;
                }
            }
            assert!(checked > 0, "degree {degree}: nothing was checked");
        }
    }

    #[test]
    fn the_folded_table_decomposes_at_every_summand_count() {
        // The trap the compact table fell into once: a search path that
        // walks `entries` reports no witness for a target that has one.
        // Every `m` has to go through the folded lookup.
        let kc = KoblitzCurve::new(0, 19).unwrap();
        let fb = build_subgroup_orbit_factor_base(&kc, 3, 200).unwrap();
        let full = PairSumTable::build(&kc, &fb).unwrap();
        let folded = PairSumTable::build_within(
            &kc,
            &fb,
            PairSumTable::folded_byte_size(fb.signed_orbits.len(), fb.points.len(), kc.n),
        )
        .unwrap();
        assert!(folded.is_folded());
        let fc = FastCurve::new(&kc.curve).unwrap();
        let g = fc.lift(kc.generator());
        for m in [2usize, 3, 4] {
            let mut agreed = 0usize;
            let mut found = 0usize;
            for t in 1u64..120 {
                let target = fc.mul_u64(g, t);
                if target.infinity {
                    continue;
                }
                let a = full.decompose_fast(target, m).is_some();
                let b = folded.decompose_fast(target, m).is_some();
                assert_eq!(a, b, "m = {m}: disagreed on whether [{t}]G decomposes");
                agreed += 1;
                if b {
                    found += 1;
                    // And the witness the folded table returns really sums.
                    let w = folded.decompose_fast(target, m).unwrap();
                    let sum = w.iter().fold(FastPoint::INFINITY, |s, &i| {
                        fc.add(s, fc.lift(&fb.points[i]))
                    });
                    assert_eq!(sum, target, "m = {m}: witness did not sum to its target");
                }
            }
            assert!(agreed > 0 && found > 0, "m = {m}: nothing was decomposed");
        }
    }

    #[test]
    fn the_compact_table_answers_exactly_as_the_full_one() {
        // Degree 61 is the one that matters for the rest's width: a
        // packed sum there is 63 bits, more than a bucket index can
        // leave over, so the rest has to be a hash rather than the key's
        // own low bits and the two tables must still agree.
        for (degree, points) in [(19u32, 300usize), (31, 400), (61, 400)] {
            the_compact_table_agrees_at(degree, points);
        }
    }

    fn the_compact_table_agrees_at(degree: u32, points: usize) {
        let kc = KoblitzCurve::new(0, degree).unwrap();
        let fb = build_subgroup_orbit_factor_base(&kc, 3, points).unwrap();
        let full = PairSumTable::build(&kc, &fb).unwrap();
        // A budget below the full table's width but above the compact
        // one's forces the compact representation of the same base.
        let compact = PairSumTable::build_within(
            &kc,
            &fb,
            PairSumTable::compact_byte_size(fb.points.len(), kc.n),
        )
        .expect("the compact table fits its own budget");
        assert!(!full.is_compact() && compact.is_compact());
        assert_eq!(full.len(), compact.len(), "the two hold the same pairs");

        let fc = FastCurve::new(&kc.curve).unwrap();
        let g = fc.lift(kc.generator());
        // An admitted key used to slice the empty `entries` vector.
        // lookup must return empty, not panic.
        let stored = fc.add(fc.lift(&fb.points[0]), fc.lift(&fb.points[0]));
        let _ = compact.lookup(stored.pack());
        let _ = compact.lookup(1_000_001);
        // Every stored sum, and a stream of points that mostly are not.
        let mut checked_hits = 0usize;
        let mut checked_misses = 0usize;
        for t in 1u64..900 {
            let target = fc.mul_u64(g, t);
            if target.infinity {
                continue;
            }
            let mut a = Vec::new();
            let mut b = Vec::new();
            full.pairs_for(target, &mut a);
            compact.pairs_for(target, &mut b);
            a.sort_unstable();
            b.sort_unstable();
            assert_eq!(a, b, "the two disagreed on [{t}]G");
            if a.is_empty() {
                checked_misses += 1;
            } else {
                checked_hits += 1;
            }
        }
        for i in 0..fb.points.len().min(64) {
            for j in i..fb.points.len().min(64) {
                let sum = fc.add(fc.lift(&fb.points[i]), fc.lift(&fb.points[j]));
                if sum.infinity {
                    continue;
                }
                let mut a = Vec::new();
                let mut b = Vec::new();
                full.pairs_for(sum, &mut a);
                compact.pairs_for(sum, &mut b);
                a.sort_unstable();
                b.sort_unstable();
                assert!(a.contains(&(i as u32, j as u32)), "full lost a stored pair");
                assert_eq!(a, b, "the two disagreed on a stored pair sum");
                checked_hits += 1;
            }
        }
        assert!(
            checked_hits > 0 && checked_misses > 0,
            "degree {degree}: the test checked only one side"
        );
    }

    #[test]
    fn the_compact_table_decomposes_at_every_summand_count() {
        // The three and four summand searches used to walk the stored
        // triples, which the compact table does not keep: a compact
        // table would have reported no witness for a target that has
        // one.  A false "no" from a decomposition oracle is silent, so
        // it is pinned here rather than left to a panic.
        let kc = KoblitzCurve::new(0, 19).unwrap();
        let fb = build_subgroup_orbit_factor_base(&kc, 3, 200).unwrap();
        let full = PairSumTable::build(&kc, &fb).unwrap();
        let compact = PairSumTable::build_within(
            &kc,
            &fb,
            PairSumTable::compact_byte_size(fb.points.len(), kc.n),
        )
        .expect("the compact table fits its own budget");
        assert!(compact.is_compact() && !full.is_compact());

        let fc = FastCurve::new(&kc.curve).unwrap();
        for m in [2usize, 3, 4] {
            let mut found = 0usize;
            // Sums of exactly m base points, which both must decompose.
            for t in 0..24usize {
                let mut target = FastPoint::INFINITY;
                let mut chosen = Vec::new();
                for s in 0..m {
                    let idx = (t * 7 + s * 13) % fb.points.len();
                    chosen.push(idx);
                    target = fc.add(target, fc.lift(&fb.points[idx]));
                }
                if target.infinity {
                    continue;
                }
                let a = full.decompose_fast(target, m);
                let b = compact.decompose_fast(target, m);
                assert_eq!(
                    a.is_some(),
                    b.is_some(),
                    "m = {m}: the two representations disagreed on whether a target decomposes"
                );
                if let Some(idxs) = b {
                    assert_eq!(idxs.len(), m);
                    let sum = idxs.iter().fold(FastPoint::INFINITY, |acc, &i| {
                        fc.add(acc, fc.lift(&fb.points[i]))
                    });
                    assert_eq!(
                        sum, target,
                        "m = {m}: a compact witness did not sum to its target"
                    );
                    found += 1;
                }
            }
            assert!(
                found > 0,
                "m = {m}: the compact table decomposed nothing at all"
            );
        }
    }

    #[test]
    fn the_single_word_orbit_map_agrees_with_the_general_one() {
        // Both the subspace bases the algebraic oracles want and the
        // subgroup bases the pair table wants, at several degrees.
        let mut checked = 0;
        for (degree, points) in [(15u32, 300usize), (19, 400), (31, 600), (37, 800)] {
            let Some(kc) = KoblitzCurve::new(0, degree) else {
                continue;
            };
            let Ok(fb) = build_subgroup_orbit_factor_base(&kc, 3, points) else {
                continue;
            };
            checked += 1;
            let fast =
                projected_signed_orbit_map_fast(&kc, &fb).expect("these fields fit in a word");
            let (orbit_of, representatives) = projected_signed_orbit_map_general(&kc, &fb);
            assert_eq!(
                fast.representatives, representatives,
                "degree {degree}: the two maps chose different orbit representatives"
            );
            assert_eq!(
                fast.orbit_of, orbit_of,
                "degree {degree}: the two maps placed a point differently"
            );
        }
        // The exact algebraic recipe used by the n=41 public-target run.
        let kc = KoblitzCurve::new(0, 41).expect("degree 41 curve");
        let basis: Vec<F2mElement> = (0..6)
            .map(|i| F2mElement::from_biguint(&BigUint::from(1u64 << i), 41))
            .collect();
        let union = build_frobenius_union_factor_base(&kc, &basis).expect("Frobenius union");
        let fb = saturate_factor_base_two_torsion(&kc, &union).expect("two-torsion closure");
        let fast = projected_signed_orbit_map_fast(&kc, &fb).expect("degree 41 fits in a word");
        let (orbit_of, representatives) = projected_signed_orbit_map_general(&kc, &fb);
        assert_eq!(
            fast.representatives, representatives,
            "algebraic representatives"
        );
        assert_eq!(fast.orbit_of, orbit_of, "algebraic orbit placements");
        checked += 1;
        assert_eq!(
            checked, 5,
            "a degree this test relies on stopped being available"
        );
    }

    #[test]
    fn a_windowed_witness_still_sums_to_its_target() {
        let kc = KoblitzCurve::new(0, 19).unwrap();
        let fb = build_subgroup_orbit_factor_base(&kc, 3, 400).unwrap();
        let pair = PairSumTable::build(&kc, &fb).unwrap();
        let opts = windowed_options(fb.points.len() / 8);
        let collector = RelationCollector::with_pair_table(&kc, &fb, &opts, Some(&pair)).unwrap();
        let (relations, report) = collector.collect(RelationWorkUnit {
            seed: 5,
            start: 0,
            count: 4096,
        });
        assert!(report.relations > 0, "the window found nothing to check");
        assert_eq!(
            report.summands_scanned,
            report.trials as u64 * opts.collection_window.unwrap() as u64
        );
        for rel in &relations {
            assert_eq!(rel.points.len(), 3);
            assert_eq!(
                rel.a,
                walked_probe_scalar(5, rel.trial, collector.scalar_bound())
            );
            // Unsorted witnesses are fine; the group equation is not.
            assert!(verify_collected_relation(&kc, &fb, 3, rel));
        }
    }

    #[test]
    fn a_window_finds_more_relations_per_lookup_than_the_full_scan() {
        let kc = KoblitzCurve::new(0, 19).unwrap();
        let fb = build_subgroup_orbit_factor_base(&kc, 3, 400).unwrap();
        let pair = PairSumTable::build(&kc, &fb).unwrap();
        let base = fb.points.len();
        // Both scan the same number of summands, so the comparison is
        // relations bought per unit of the cost that actually dominates.
        let divisor = 16;
        let full = KoblitzIcOptions {
            collection_window: None,
            ..windowed_options(base)
        };
        let windowed = windowed_options(base / divisor);
        let measure = |opts: &KoblitzIcOptions, trials: u64| {
            let collector =
                RelationCollector::with_pair_table(&kc, &fb, opts, Some(&pair)).expect("collector");
            collector
                .collect(RelationWorkUnit {
                    seed: 9,
                    start: 0,
                    count: trials,
                })
                .1
        };
        let a = measure(&full, 2048);
        let b = measure(&windowed, 2048 * divisor as u64);
        assert_eq!(
            a.summands_scanned, b.summands_scanned,
            "the two runs must pay for the same number of lookups"
        );
        assert!(
            b.relations > a.relations * 2,
            "a window keeps all three chances per triple, so the same lookups \
             should buy nearly three times the relations: full {} windowed {}",
            a.relations,
            b.relations
        );
    }

    #[test]
    fn walked_work_units_partition_the_probe_sequence_exactly() {
        let kc = KoblitzCurve::new(0, 19).unwrap();
        let fb = build_subgroup_orbit_factor_base(&kc, 3, 400).unwrap();
        let pair = PairSumTable::build(&kc, &fb).unwrap();
        let opts = windowed_options(fb.points.len() / 8);
        let collector = RelationCollector::with_pair_table(&kc, &fb, &opts, Some(&pair)).unwrap();
        let whole = collector
            .collect(RelationWorkUnit {
                seed: 12,
                start: 0,
                count: 2000,
            })
            .0;
        // Boundaries deliberately cut runs of PROBE_RUN in half: a unit
        // that starts mid-run pays for its own first multiplication and
        // must still report the same relations.
        let mut split = Vec::new();
        for (start, count) in [(0u64, 37u64), (37, 512), (549, 3), (552, 1448)] {
            split.extend(
                collector
                    .collect(RelationWorkUnit {
                        seed: 12,
                        start,
                        count,
                    })
                    .0,
            );
        }
        split.sort_by_key(|r| r.trial);
        assert!(!whole.is_empty());
        assert_eq!(whole, split);
    }

    #[test]
    fn windowed_collection_precomputes_the_same_logarithms() {
        let kc = KoblitzCurve::new(0, 19).unwrap();
        let fb = build_subgroup_orbit_factor_base(&kc, 3, 400).unwrap();
        let opts = windowed_options(fb.points.len() / 8);
        let (table, report) = solve_factor_base_logs(&kc, &fb, &opts).expect("log database");
        assert!(report.relations >= table.columns.len());
        // Every column's logarithm checked against the group itself.
        for (point, log) in &table.columns {
            assert_eq!(*point, kc.mul(kc.generator(), log));
        }
    }

    #[test]
    fn work_units_partition_the_probe_sequence_exactly() {
        let kc = KoblitzCurve::new(1, 11).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let opts = collector_options();
        let r = kc.subgroup_order.to_u64_digits()[0];
        let collector = RelationCollector::new(&kc, &fb, &opts).unwrap();
        let (whole, report) = collector.collect(RelationWorkUnit {
            seed: 7,
            start: 0,
            count: 600,
        });
        assert_eq!(report.trials, 600);
        assert_eq!(report.relations, whole.len());
        assert!(whole.len() > 10, "{} relations", whole.len());
        // Any partition of the range, in any order, gives the same relations.
        let mut parts = Vec::new();
        for (start, count) in [(350u64, 250u64), (0, 100), (100, 250)] {
            parts.extend(
                collector
                    .collect(RelationWorkUnit {
                        seed: 7,
                        start,
                        count,
                    })
                    .0,
            );
        }
        parts.sort_by_key(|rel| rel.trial);
        assert_eq!(whole, parts);
        for rel in &whole {
            assert!(verify_collected_relation(&kc, &fb, 2, rel));
            assert_eq!(rel.a, probe_scalar(7, rel.trial, r));
            assert_eq!(rel.points.len(), 2);
            assert!((0..600).contains(&rel.trial));
        }
        // Another seed is another sequence.
        let (other, _) = collector.collect(RelationWorkUnit {
            seed: 8,
            start: 0,
            count: 600,
        });
        assert_ne!(whole, other);
        // Forgeries are rejected: wrong scalar, wrong point, wrong count, bad index.
        let good = whole[0].clone();
        let mut bad = good.clone();
        bad.a = if bad.a == 1 { 2 } else { bad.a - 1 };
        assert!(!verify_collected_relation(&kc, &fb, 2, &bad));
        let mut bad = good.clone();
        bad.points[0] = (bad.points[0] + 1) % fb.points.len();
        assert!(!verify_collected_relation(&kc, &fb, 2, &bad));
        let mut bad = good.clone();
        bad.points.push(0);
        assert!(!verify_collected_relation(&kc, &fb, 2, &bad));
        let mut bad = good.clone();
        bad.points[0] = usize::MAX;
        assert!(!verify_collected_relation(&kc, &fb, 2, &bad));
        let mut bad = good.clone();
        bad.a = 0;
        assert!(!verify_collected_relation(&kc, &fb, 2, &bad));
        assert!(!verify_collected_relation(&kc, &fb, 3, &good));
    }

    #[test]
    fn logs_from_collected_relations_match_the_single_process_precompute() {
        for (a, n, la) in [
            (0u8, 9u32, LinearAlgebra::Dense),
            (1, 11, LinearAlgebra::Sparse(SparseSolveOptions::default())),
        ] {
            let kc = KoblitzCurve::new(a, n).unwrap();
            let fb = build_frobenius_factor_base(&kc, 0).unwrap();
            let opts = KoblitzIcOptions {
                linear_algebra: la,
                ..collector_options()
            };
            let (table, report) = solve_factor_base_logs(&kc, &fb, &opts).unwrap();
            assert!(report.verified, "K_{a}/2^{n}: {report:?}");
            assert!(report.collection_seconds > 0.0);
            // The same probe range collected as two work units, delivered
            // out of order with a duplicate and a forgery mixed in.
            let collector = RelationCollector::new(&kc, &fb, &opts).unwrap();
            let total = report.trials as u64;
            let (first, _) = collector.collect(RelationWorkUnit {
                seed: opts.seed,
                start: 0,
                count: total / 2,
            });
            let (second, _) = collector.collect(RelationWorkUnit {
                seed: opts.seed,
                start: total / 2,
                count: total - total / 2,
            });
            let mut all = second.clone();
            all.extend(first.iter().cloned());
            all.push(first[0].clone());
            let mut forged = first[0].clone();
            forged.a = if forged.a == 1 { 2 } else { forged.a - 1 };
            all.push(forged);
            let (t2, rep2) = solve_factor_base_logs_from_relations(&kc, &fb, &opts, &all).unwrap();
            assert!(rep2.verified, "K_{a}/2^{n}: {rep2:?}");
            assert_eq!(rep2.rejected_relations, 1);
            // The single-process run keeps repeated probes (a tiny
            // subgroup repeats scalars); the merge drops them, plus the
            // one duplicate added above.
            assert!(rep2.duplicate_relations >= 1);
            assert_eq!(
                rep2.relations + rep2.duplicate_relations,
                report.relations + 1,
                "K_{a}/2^{n}"
            );
            assert_eq!(rep2.sparse, report.sparse);
            assert_eq!(t2.columns, table.columns, "K_{a}/2^{n}: tables differ");
            assert!(t2.verify(&kc));
            // Too few relations: unverified, never a wrong table.
            let (t3, rep3) =
                solve_factor_base_logs_from_relations(&kc, &fb, &opts, &first[..1]).unwrap();
            assert!(!rep3.verified && t3.is_empty());
        }
    }

    #[test]
    fn orbit_generated_admissibility_walk_matches_the_naive_one() {
        for (a, n, indices) in [
            (1u8, 7u32, vec![1usize]),
            (1, 7, vec![0, 1]),
            (0, 9, vec![1]),
            (0, 9, vec![1, 2]),
            (1, 15, vec![2]),
            (1, 15, vec![0, 2]),
            (1, 15, vec![0, 1, 2]),
            (0, 13, vec![0]),
        ] {
            let kc = KoblitzCurve::new(a, n).unwrap();
            let fb = build_frobenius_factor_base_from_divisor(&kc, &indices).unwrap();
            for m in 1..=4 {
                assert_eq!(
                    fb.m_can_decompose(&kc, m),
                    fb.m_can_decompose_reference(&kc, m),
                    "K_{a}/2^{n} divisor {indices:?} m = {m}"
                );
            }
            // And on a nonlinear union, which has more cofactor classes.
            let union =
                build_frobenius_union_factor_base(&kc, &[F2mElement::one(n), F2mElement::z(n)])
                    .unwrap();
            for m in 1..=4 {
                assert_eq!(
                    union.m_can_decompose(&kc, m),
                    union.m_can_decompose_reference(&kc, m),
                    "K_{a}/2^{n} union m = {m}"
                );
            }
        }
    }

    #[test]
    fn all_three_oracles_answer_every_target_identically() {
        // Exhaustive search, Gröbner and SAT must agree on *both*
        // answers: the same decomposability verdict, and whatever they
        // return must be a genuine decomposition.
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let index_of = fb.index_map();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let g = kc.generator().clone();

        let mut agreed = 0;
        let mut decomposable = 0;
        for k in 1..40u32 {
            let target = kc.mul(&g, &BigUint::from(k));
            let by_search = enumerate_decompose(&kc, &fb, &index_of, &target, 2);
            let (by_algebra, stats) = groebner_decompose(
                &kc,
                &fb,
                &index_of,
                &st,
                &target,
                2,
                SolverEngine::default(),
                20_000,
            );
            assert!(!stats.exhausted, "budget should suffice at n = 9");
            let (by_sat, sat_stats) =
                sat_decompose(&kc, &fb, &index_of, &st, &target, 2, 64, Some(2));
            assert!(!sat_stats.exhausted, "model cap should suffice at n = 9");
            assert_eq!(sat_stats.spurious, 0, "the CNF encoding must be exact");
            assert_eq!(
                by_search.is_some(),
                by_algebra.is_some(),
                "search and Gröbner disagree on [{k}]G"
            );
            assert_eq!(
                by_search.is_some(),
                by_sat.is_some(),
                "search and SAT disagree on [{k}]G"
            );
            if let Some(idxs) = by_sat {
                let mut acc = BinaryPoint::Infinity;
                for i in &idxs {
                    acc = kc.add(&acc, &fb.points[*i]);
                }
                assert_eq!(acc, target, "SAT decomposition of [{k}]G is wrong");
            }
            if let Some(idxs) = by_algebra {
                decomposable += 1;
                // Whatever it returned must actually sum to the target.
                let mut acc = BinaryPoint::Infinity;
                for i in &idxs {
                    acc = kc.add(&acc, &fb.points[*i]);
                }
                assert_eq!(acc, target, "algebraic decomposition of [{k}]G is wrong");
            }
            agreed += 1;
        }
        assert_eq!(agreed, 39);
        assert!(decomposable > 0, "some targets must decompose");
    }

    #[test]
    fn chained_s3_handles_three_summands() {
        // m ≥ 3 chains S₃ over intermediate field unknowns instead of
        // resolving S_{m+1}; check the chain against exhaustive search.
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let index_of = fb.index_map();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let g = kc.generator().clone();

        for k in [5u32, 29, 88] {
            let target = kc.mul(&g, &BigUint::from(k));
            let by_search = enumerate_decompose(&kc, &fb, &index_of, &target, 3);
            let (by_algebra, _) = groebner_decompose(
                &kc,
                &fb,
                &index_of,
                &st,
                &target,
                3,
                SolverEngine::default(),
                50_000,
            );
            assert_eq!(by_search.is_some(), by_algebra.is_some(), "3-point, [{k}]G");
            if let Some(idxs) = by_algebra {
                assert_eq!(idxs.len(), 3);
                let mut acc = BinaryPoint::Infinity;
                for i in &idxs {
                    acc = kc.add(&acc, &fb.points[*i]);
                }
                assert_eq!(acc, target);
            }
        }
    }

    #[test]
    fn the_two_algebraic_engines_agree() {
        // Matrix-F4 and textbook Buchberger must reach the same verdict;
        // only the cost differs.
        let kc = KoblitzCurve::new(1, 9).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let index_of = fb.index_map();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let g = kc.generator().clone();

        for k in 1..6u32 {
            let target = kc.mul(&g, &BigUint::from(k));
            let (f4, _) = groebner_decompose(
                &kc,
                &fb,
                &index_of,
                &st,
                &target,
                2,
                SolverEngine::MatrixF4 { max_degree: 3 },
                20_000,
            );
            let (bb, _) = groebner_decompose(
                &kc,
                &fb,
                &index_of,
                &st,
                &target,
                2,
                SolverEngine::Buchberger,
                20_000,
            );
            assert_eq!(f4.is_some(), bb.is_some(), "engines disagree on [{k}]G");
        }
    }

    #[test]
    fn undecomposable_targets_are_rejected_algebraically() {
        // The point of the Gröbner step: a target with no decomposition
        // is *refuted* by the algebra — the reduction produces the
        // constant 1 — rather than by searching the factor base.
        //
        // `K_0 / F_2^7` is the clean case: its invariant subspace has 8
        // elements but only one of them is the abscissa of a curve
        // point, so no target decomposes at all.
        let kc = KoblitzCurve::new(0, 7).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        assert_eq!(fb.points.len(), 1, "the degenerate factor base");
        let index_of = fb.index_map();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let g = kc.generator().clone();

        let mut certified = 0;
        for k in 1..29u32 {
            let target = kc.mul(&g, &BigUint::from(k));
            assert!(enumerate_decompose(&kc, &fb, &index_of, &target, 2).is_none());
            let (out, stats) = groebner_decompose(
                &kc,
                &fb,
                &index_of,
                &st,
                &target,
                2,
                SolverEngine::default(),
                20_000,
            );
            assert!(out.is_none(), "[{k}]G must not decompose");
            assert!(
                stats.infeasible_branches > 0,
                "[{k}]G should be closed by an infeasibility certificate"
            );
            assert_eq!(stats.splits, 0, "no search should have been needed");
            certified += 1;
        }
        assert_eq!(certified, 28);
    }

    #[test]
    fn sat_refutes_undecomposable_targets() {
        // The SAT analogue of the Gröbner certificate: on the
        // degenerate `K_0 / F_2^7` factor base nothing decomposes, and
        // every instance comes back UNSAT rather than merely unsolved.
        let kc = KoblitzCurve::new(0, 7).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let index_of = fb.index_map();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let g = kc.generator().clone();

        for k in 1..29u32 {
            let target = kc.mul(&g, &BigUint::from(k));
            let (out, stats) = sat_decompose(&kc, &fb, &index_of, &st, &target, 2, 64, Some(2));
            assert!(out.is_none(), "[{k}]G must not decompose");
            assert!(stats.refuted, "[{k}]G should be refuted by UNSAT");
            assert!(!stats.exhausted);
            assert_eq!(stats.spurious, 0);
        }
    }

    #[test]
    fn macaulay_rows_may_be_added_but_never_substituted() {
        // The trap this preprocessing has to avoid, pinned as a test.
        //
        // `matrix_f4_f2` skips input polynomials whose degree exceeds
        // the Macaulay degree it is asked for.  So the degree-2 rows of
        // a *cubic* system — every chained m ≥ 3 system — describe only
        // its quadratic part.  Adding them is sound; replacing the
        // system with them drops constraints, and on a refuting
        // instance that turns UNSAT into SAT.
        let kc = KoblitzCurve::new(1, 15).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let g = kc.generator().clone();
        let target = kc.mul(&g, &BigUint::from(6u32));
        let x_r = match &target {
            BinaryPoint::Affine { x, .. } => x.clone(),
            BinaryPoint::Infinity => unreachable!(),
        };
        let sys =
            build_decomposition_system(&fb.subspace_basis, &x_r, &kc.curve.b, 3, &st).unwrap();

        let deg = |p: &crate::cryptanalysis::pq_groebner_f2::F2BoolPoly| {
            p.terms
                .iter()
                .map(|t| t.mask.count_ones())
                .max()
                .unwrap_or(0)
        };
        assert_eq!(
            sys.equations.iter().map(deg).max(),
            Some(3),
            "the chained system is cubic"
        );

        // The mechanism: no degree-2 row can carry a cubic monomial, so
        // the cubic equations are simply absent from that row set.
        let rows = matrix_f4_f2(&sys.equations, sys.n_vars, 2).unwrap();
        assert!(
            rows.iter().all(|r| deg(r) <= 2),
            "a degree-2 Macaulay row cannot contain a cubic term"
        );
        assert!(
            sys.equations.iter().any(|e| deg(e) == 3),
            "and the system does contain cubic equations, which those rows drop"
        );
    }

    #[test]
    fn macaulay_rows_are_implied_by_the_system() {
        // The other half: adding rows is sound.  Every row is an
        // F_2-combination of multiples of the equations, so it vanishes
        // wherever the system does.  Verified exhaustively on a
        // quadratic m = 2 system, which is small enough to scan.
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let g = kc.generator().clone();
        let target = kc.mul(&g, &BigUint::from(11u32));
        let x_r = match &target {
            BinaryPoint::Affine { x, .. } => x.clone(),
            BinaryPoint::Infinity => unreachable!(),
        };
        let sys =
            build_decomposition_system(&fb.subspace_basis, &x_r, &kc.curve.b, 2, &st).unwrap();
        assert_eq!(sys.n_vars, 12);

        let mut solutions = 0;
        for d in [2u32, 3] {
            let rows = matrix_f4_f2(&sys.equations, sys.n_vars, d).unwrap();
            solutions = 0;
            for pt in 0..(1u64 << sys.n_vars) {
                if sys.equations.iter().all(|e| e.eval(pt) == 0) {
                    solutions += 1;
                    assert!(
                        rows.iter().all(|e| e.eval(pt) == 0),
                        "a degree-{d} row rejected a real solution"
                    );
                }
            }
        }
        assert!(solutions > 0, "the instance must have solutions to check");
    }

    #[test]
    fn macaulay_preprocessing_does_not_change_any_verdict() {
        // Whatever it does to the cost, it must not touch the answers.
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let index_of = fb.index_map();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let g = kc.generator().clone();
        for k in 1..12u32 {
            let target = kc.mul(&g, &BigUint::from(k));
            let (plain, s1) = sat_decompose(&kc, &fb, &index_of, &st, &target, 2, 64, None);
            let (hybrid, s2) = sat_decompose(&kc, &fb, &index_of, &st, &target, 2, 64, Some(2));
            assert_eq!(
                plain.is_some(),
                hybrid.is_some(),
                "verdict changed at [{k}]G"
            );
            assert_eq!(s1.refuted, s2.refuted, "refutation changed at [{k}]G");
            assert_eq!(s1.implied_rows, 0);
            assert_eq!((s1.spurious, s2.spurious), (0, 0));
        }
    }

    #[test]
    fn sat_handles_the_cubic_chained_system() {
        // With m ≥ 3 the chained S₃ is cubic, so the encoding needs
        // Tseitin auxiliaries above degree 2.
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let index_of = fb.index_map();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let g = kc.generator().clone();

        for k in [5u32, 29] {
            let target = kc.mul(&g, &BigUint::from(k));
            let by_search = enumerate_decompose(&kc, &fb, &index_of, &target, 3);
            let (by_sat, stats) = sat_decompose(&kc, &fb, &index_of, &st, &target, 3, 64, Some(2));
            assert_eq!(stats.spurious, 0);
            assert_eq!(by_search.is_some(), by_sat.is_some(), "3-point, [{k}]G");
            if let Some(idxs) = by_sat {
                let mut acc = BinaryPoint::Infinity;
                for i in &idxs {
                    acc = kc.add(&acc, &fb.points[*i]);
                }
                assert_eq!(acc, target);
            }
        }
    }

    #[test]
    fn solves_the_dlp_with_the_sat_oracle() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let g = kc.generator().clone();
        let d = BigUint::from(53u32);
        let q = kc.mul(&g, &d);
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let mut signed_fixed_relations = None;
        let mut signed_early_relations = None;
        for (collapse_negation, stop_on_verified_rank) in
            [(false, false), (true, false), (true, true)]
        {
            let opts = KoblitzIcOptions {
                strategy: DecompositionStrategy::Sat,
                collapse_negation,
                stop_on_verified_rank,
                ..KoblitzIcOptions::default()
            };
            let report = koblitz_index_calculus_dlp_with_factor_base(&kc, &q, &fb, &opts).unwrap();
            assert_eq!(report.log, Some(d.clone()));
            assert_eq!(report.collapse_negation, collapse_negation);
            assert_eq!(
                report.orbit_count,
                if collapse_negation {
                    fb.unknowns()
                } else {
                    fb.orbits.len()
                }
            );
            assert!(report.sat_calls > 0, "the SAT path must have run");
            assert_eq!(report.reductions, 0, "no Gröbner work on this path");
            if !stop_on_verified_rank {
                assert_eq!(report.relations, report.orbit_count + opts.extra_relations);
            }
            if collapse_negation && stop_on_verified_rank {
                signed_early_relations = Some(report.relations);
            } else if collapse_negation {
                signed_fixed_relations = Some(report.relations);
            }
        }
        assert!(signed_early_relations.unwrap() < signed_fixed_relations.unwrap());
    }

    #[test]
    fn projected_orbit_columns_recover_unknown_scalar_without_labels() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let d = BigUint::from(53u32);
        let q = kc.mul(kc.generator(), &d);
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let report = koblitz_index_calculus_dlp_with_factor_base(
            &kc,
            &q,
            &fb,
            &KoblitzIcOptions {
                strategy: DecompositionStrategy::Sat,
                allow_direct_relation: false,
                collapse_projected_orbits: true,
                ..KoblitzIcOptions::default()
            },
        )
        .unwrap();
        assert!(report.m_cofactor_admissible);
        assert!(report.collapse_projected_orbits);
        assert_eq!(report.orbit_count, projected_signed_orbit_count(&kc, &fb));
        assert_eq!(report.log, Some(d));
        assert!(!report.direct_relation);
        assert_eq!(report.sat_invalid_models, 0);
    }

    #[test]
    fn incomplete_ic_retains_a_terminal_matrix_rank() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let q = kc.mul(kc.generator(), &BigUint::from(53u32));
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let report = koblitz_index_calculus_dlp_with_factor_base(
            &kc,
            &q,
            &fb,
            &KoblitzIcOptions {
                strategy: DecompositionStrategy::Sat,
                max_trials: 0,
                allow_direct_relation: false,
                ..KoblitzIcOptions::default()
            },
        )
        .unwrap();
        assert!(report.log.is_none());
        assert_eq!(report.trials, 0);
        assert_eq!(report.relations, 0);
        assert_eq!(report.matrix_rows, 0);
        assert_eq!(report.matrix_columns, report.orbit_count + 1);
        assert_eq!(report.terminal_matrix_rank, 0);
        assert_eq!(report.rank_checks, 1);
        assert_eq!(report.linear_solve_attempts, 1);
        assert_eq!(report.rank_history.len(), 1);
        assert_eq!(report.rank_history[0].rank, 0);
        assert!(!report.rank_history[0].candidate_produced);
        assert!(!report.rank_history[0].candidate_verified);
    }

    #[test]
    fn rho_walk_timing_stops_before_collision_verification_progress() {
        let kc = KoblitzCurve::new(1, 7).unwrap();
        let q = kc.mul(kc.generator(), &BigUint::from(17u32));
        let started = std::time::Instant::now();
        let mut delayed_collision = false;
        let report = koblitz_signed_frobenius_rho_with_progress(
            &kc,
            &q,
            &KoblitzSignedRhoOptions {
                seed: 8_981_096_000_249_929_860,
                jump_count: 16,
                max_restarts: 16,
                max_iterations_per_restart: 1 << 20,
                progress_interval: 256,
                parallel_walks: 4,
            },
            &mut |event| {
                if matches!(event, KoblitzSignedRhoEvent::Collision { .. }) && !delayed_collision {
                    delayed_collision = true;
                    std::thread::sleep(std::time::Duration::from_millis(50));
                }
            },
        );
        let elapsed_ns = started.elapsed().as_nanos();
        assert!(report.verified);
        assert!(delayed_collision);
        let charged_ns = report.setup_ns + report.walk_ns + report.verification_ns;
        assert!(
            elapsed_ns.saturating_sub(charged_ns)
                >= std::time::Duration::from_millis(40).as_nanos(),
            "collision callback leaked into a timed algorithm stage: elapsed={elapsed_ns}, charged={charged_ns}"
        );
    }

    #[test]
    fn exhausted_rho_does_not_charge_an_unused_final_advance() {
        let kc = KoblitzCurve::new(1, 7).unwrap();
        let q = kc.mul(kc.generator(), &BigUint::from(17u32));
        let (report, events) = (0..1024)
            .find_map(|seed| {
                let mut events = Vec::new();
                let report = koblitz_signed_frobenius_rho_with_progress(
                    &kc,
                    &q,
                    &KoblitzSignedRhoOptions {
                        seed,
                        jump_count: 16,
                        max_restarts: 1,
                        max_iterations_per_restart: 1,
                        progress_interval: 0,
                        parallel_walks: 4,
                    },
                    &mut |event| events.push(event),
                );
                (report.exhausted && report.charges.collisions == 0).then_some((report, events))
            })
            .expect("a one-comparison restart should exhaust without a collision");
        assert!(!report.verified);
        assert!(report.exhausted);
        assert_eq!(report.restarts_attempted, 1);
        assert_eq!(report.iterations, 1);
        // One comparison, no advance past it: the walk is a single
        // trajectory, so an advance is one group addition and this
        // restart makes none.
        assert_eq!(report.charges.walk_group_additions, 0);
        assert!(matches!(
            events.last(),
            Some(KoblitzSignedRhoEvent::Finished {
                verified: false,
                exhausted: true,
            })
        ));
    }

    #[test]
    fn parallel_sat_relation_batches_recover_the_same_log() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let d = BigUint::from(53u32);
        let q = kc.mul(kc.generator(), &d);
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let opts = KoblitzIcOptions {
            strategy: DecompositionStrategy::Sat,
            relation_batch_size: 4,
            ..KoblitzIcOptions::default()
        };
        let report = koblitz_index_calculus_dlp_with_factor_base(&kc, &q, &fb, &opts).unwrap();
        assert_eq!(report.log, Some(d));
        assert_eq!(report.relation_batch_size, 4);
        assert!(report.relation_batches < report.trials);
        assert_eq!(report.sat_invalid_models, 0);
    }

    #[test]
    fn solves_the_dlp_by_enumeration_too() {
        // The reference oracle drives the same solver to the same log.
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let g = kc.generator().clone();
        let d = BigUint::from(53u32);
        let q = kc.mul(&g, &d);
        let opts = KoblitzIcOptions {
            strategy: DecompositionStrategy::Enumerate,
            ..KoblitzIcOptions::default()
        };
        let report = koblitz_index_calculus_dlp(&kc, &q, &opts).unwrap();
        assert_eq!(report.log, Some(d));
        // No algebra ran on this path.
        assert_eq!(report.reductions, 0);
    }

    #[test]
    fn solves_the_dlp_on_k0_over_f512() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let g = kc.generator().clone();
        for d in [
            BigUint::from(5u32),
            BigUint::from(61u32),
            BigUint::from(118u32),
        ] {
            let q = kc.mul(&g, &d);
            let opts = KoblitzIcOptions::default();
            let report = koblitz_index_calculus_dlp(&kc, &q, &opts).unwrap();
            assert_eq!(report.log, Some(d.clone()), "report = {report:?}");
        }
    }

    #[test]
    fn solves_the_dlp_on_k1_over_f512() {
        let kc = KoblitzCurve::new(1, 9).unwrap();
        let g = kc.generator().clone();
        let d = BigUint::from(29u32);
        let q = kc.mul(&g, &d);
        let report = koblitz_index_calculus_dlp(&kc, &q, &KoblitzIcOptions::default()).unwrap();
        assert_eq!(report.log, Some(d));
    }

    #[test]
    fn speedup_model_tracks_the_predicted_factors() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let model = koblitz_speedup_model(kc.n, fb.points.len(), fb.unknowns(), 2);
        // Signed orbits have size up to 2n. Short or self-negative
        // orbits make the measured saving smaller than that ceiling.
        assert!(model.relation_collection_speedup <= 2.0 * kc.n as f64);
        assert!(model.relation_collection_speedup > kc.n as f64 * 0.5);
        assert!(
            (model.linear_algebra_speedup
                - model.relation_collection_speedup * model.relation_collection_speedup)
                .abs()
                < 1e-9
        );
        assert_eq!(model.symmetry_breaking_factor, 2.0);
        // The paper's headline comparison: more than rho's √(2n).
        assert!(model.relation_collection_speedup > model.rho_speedup);
    }
}
#[cfg(test)]
mod subfield_tests {
    use super::*;
    use crate::cryptanalysis::koblitz_factor_base_search::{search, Family, SearchOptions};

    fn opts(m: usize) -> KoblitzIcOptions {
        KoblitzIcOptions {
            m,
            strategy: DecompositionStrategy::PairTable,
            collapse_negation: true,
            collapse_projected_orbits: true,
            allow_direct_relation: false,
            max_trials: 40_000,
            ..KoblitzIcOptions::default()
        }
    }

    #[test]
    fn the_subfield_constructor_reproduces_the_koblitz_curves() {
        for (a, n) in [(0u8, 9u32), (1, 11), (1, 15), (0, 13), (1, 7)] {
            let koblitz = KoblitzCurve::new(a, n).unwrap();
            let general = KoblitzCurve::subfield(1, n, u64::from(a), 1).unwrap();
            assert_eq!(koblitz.group_order, general.group_order);
            assert_eq!(koblitz.subgroup_order, general.subgroup_order);
            assert_eq!(koblitz.cofactor, general.cofactor);
            assert_eq!(koblitz.lambda, general.lambda);
            assert_eq!(koblitz.trace, general.trace);
            assert_eq!(koblitz.curve.generator, general.curve.generator);
            assert_eq!(koblitz.group_order, koblitz_point_count(a, n));
            assert_eq!(
                (koblitz.k, koblitz.q, koblitz.a_index, koblitz.b_index),
                (1, 2, u64::from(a), 1)
            );
            assert_eq!(koblitz.subfield_basis, vec![F2mElement::one(n)]);
            assert_eq!(koblitz.label(), format!("K_{a} / GF(2^{n})"));
            // The factor list and the legacy family are the F_2 ones.
            let masks: Vec<u64> = invariant_factors(&koblitz)
                .iter()
                .map(|f| poly_bitmask(f).unwrap())
                .collect();
            assert_eq!(masks, all_factors_of_x_n_minus_1(n));
            assert_eq!(
                top_factor_indices(&koblitz).len(),
                factor_x_n_minus_1(n).len()
            );
            for (i, &idx) in top_factor_indices(&koblitz).iter().enumerate() {
                assert_eq!(masks[idx], factor_x_n_minus_1(n)[i]);
            }
        }
        assert!(KoblitzCurve::new(2, 9).is_none());
        assert!(
            KoblitzCurve::subfield(1, 9, 0, 2).is_none(),
            "b must be 1 over F_2"
        );
        assert!(
            KoblitzCurve::subfield(2, 9, 0, 1).is_none(),
            "k must divide n"
        );
        assert!(
            KoblitzCurve::subfield(2, 12, 0, 1).is_none(),
            "n / k must be odd"
        );
        assert!(KoblitzCurve::subfield(2, 10, 4, 1).is_none(), "a below q");
        assert!(KoblitzCurve::subfield(9, 27, 0, 1).is_none(), "k ≤ 8");
    }

    #[test]
    fn subfield_curves_count_points_correctly() {
        // #E(F_{2^n}) from #E(F_q) and the trace recurrence against a
        // full enumeration of the abscissae; the coefficients lie in
        // the subfield and the group order is where it should be.
        let mut checked = 0;
        for (k, n, a, b) in [
            (2u32, 6u32, 0u64, 2u64),
            (2, 10, 0, 2),
            (2, 14, 0, 2),
            (3, 9, 1, 1),
            (3, 9, 2, 5),
            (4, 12, 3, 5),
            (2, 10, 3, 3),
        ] {
            let Some(kc) = KoblitzCurve::subfield(k, n, a, b) else {
                continue;
            };
            checked += 1;
            let irr = &kc.curve.irreducible;
            let q = 1u64 << k;
            assert_eq!(kc.q, q);
            assert_eq!(kc.extension_degree(), n / k);
            assert_eq!(kc.subfield_basis.len(), k as usize);
            for e in &kc.subfield_basis {
                assert_eq!(e.square_k_times(k, irr), *e, "basis lies in F_q");
            }
            assert_eq!(kc.curve.a.square_k_times(k, irr), kc.curve.a);
            assert_eq!(kc.curve.b.square_k_times(k, irr), kc.curve.b);
            assert!(!kc.curve.b.is_zero());
            let mut count = 1u64;
            for raw in 0..(1u64 << n) {
                let x = F2mElement::from_biguint(&BigUint::from(raw), n);
                count += points_with_x(&kc.curve, &x).len() as u64;
            }
            assert_eq!(
                BigUint::from(count),
                kc.group_order,
                "k={k} n={n} a={a} b={b}"
            );
            assert_eq!(&kc.subgroup_order * &kc.cofactor, kc.group_order);
            assert!(
                (kc.trace.unsigned_abs() as f64) <= 2.0 * (q as f64).sqrt() + 1e-9,
                "Hasse over F_q"
            );
            assert_eq!(
                kc.mul(kc.generator(), &kc.subgroup_order),
                BinaryPoint::Infinity
            );
        }
        assert!(checked >= 3, "only {checked} instances constructed");
    }

    #[test]
    fn the_q_frobenius_acts_as_lambda_on_subfield_curves() {
        for (k, n, a, b) in [
            (2u32, 10u32, 0u64, 2u64),
            (2, 14, 0, 2),
            (2, 14, 1, 2),
            (3, 15, 1, 3),
        ] {
            let Some(kc) = KoblitzCurve::subfield(k, n, a, b) else {
                continue;
            };
            let r = &kc.subgroup_order;
            // λ² − tλ + q ≡ 0 (mod r).
            let t = if kc.trace >= 0 {
                BigUint::from(kc.trace as u64) % r
            } else {
                r - BigUint::from((-kc.trace) as u64) % r
            };
            let lhs = (&kc.lambda * &kc.lambda + BigUint::from(kc.q)) % r;
            let rhs = (&t * &kc.lambda) % r;
            assert_eq!(lhs, rhs, "characteristic equation");
            let g = kc.generator();
            for s in [1u64, 2, 3, 17, 1000] {
                let p = kc.mul(g, &BigUint::from(s));
                assert_eq!(
                    kc.frobenius(&p),
                    kc.mul(&p, &kc.lambda),
                    "k={k} n={n}: π ≠ [λ] on [{s}]G"
                );
                assert_eq!(
                    kc.frobenius(&p),
                    BinaryPoint::Affine {
                        x: match &p {
                            BinaryPoint::Affine { x, .. } =>
                                x.square_k_times(k, &kc.curve.irreducible),
                            _ => unreachable!(),
                        },
                        y: match &p {
                            BinaryPoint::Affine { y, .. } =>
                                y.square_k_times(k, &kc.curve.irreducible),
                            _ => unreachable!(),
                        },
                    }
                );
            }
        }
    }

    #[test]
    fn invariant_factors_over_the_subfield_factor_x_e_minus_1() {
        for (k, n, a, b) in [
            (2u32, 10u32, 0u64, 2u64),
            (2, 14, 0, 2),
            (2, 18, 2, 2),
            (3, 15, 1, 3),
            (4, 20, 3, 5),
            (2, 26, 0, 2),
        ] {
            let Some(kc) = KoblitzCurve::subfield(k, n, a, b) else {
                continue;
            };
            let irr = &kc.curve.irreducible;
            let e = kc.extension_degree();
            let factors = invariant_factors(&kc);
            // Product is x^e − 1, every factor monic with coefficients in F_q.
            let mut product = F2mPoly::one(n);
            for f in &factors {
                assert_eq!(f.lead(), F2mElement::one(n));
                for c in &f.coeffs {
                    assert_eq!(c.square_k_times(k, irr), *c, "coefficient outside F_q");
                }
                product = product.mul(f, irr);
            }
            let mut coeffs = vec![F2mElement::zero(n); e as usize + 1];
            coeffs[0] = F2mElement::one(n);
            coeffs[e as usize] = F2mElement::one(n);
            assert!(
                product.eq_poly(&F2mPoly::from_coeffs(coeffs, n)),
                "k={k} n={n}: product is not x^e − 1"
            );
            // Degrees are the q-cyclotomic coset sizes mod e.
            let q_mod = (kc.q % u64::from(e)) as u32;
            let mut seen = vec![false; e as usize];
            let mut sizes = Vec::new();
            for start in 0..e {
                if seen[start as usize] {
                    continue;
                }
                let mut x = start;
                let mut size = 0;
                while !seen[x as usize] {
                    seen[x as usize] = true;
                    size += 1;
                    x = (x * q_mod) % e;
                }
                sizes.push(size);
            }
            sizes.sort_unstable();
            let mut degrees: Vec<usize> = factors.iter().map(|f| f.degree().unwrap()).collect();
            degrees.sort_unstable();
            assert_eq!(degrees, sizes, "k={k} n={n}");
            assert!(top_factor_indices(&kc)
                .iter()
                .all(|&i| factors[i].degree() == Some(*sizes.last().unwrap())));
            // The canonical order is deterministic across rebuilds.
            let again = invariant_factors(&kc);
            assert!(factors.iter().zip(&again).all(|(x, y)| x.eq_poly(y)));
            // Each factor's kernel is π_q-invariant, of F_2-dimension k·deg,
            // and annihilated by the linearised polynomial.
            for (idx, f) in factors.iter().enumerate() {
                let (basis, _) = subspace_basis_for_factors(&kc, &[idx]).unwrap();
                assert_eq!(basis.len(), k as usize * f.degree().unwrap());
                let span = span_f2(&basis, n);
                let keys: HashSet<BigUint> = span.iter().map(F2mElement::to_biguint).collect();
                assert_eq!(keys.len(), span.len());
                for x in &span {
                    assert!(
                        keys.contains(&kc.frobenius_x(x).to_biguint()),
                        "not π_q-invariant"
                    );
                    let mut img = F2mElement::zero(n);
                    for (i, c) in f.coeffs.iter().enumerate() {
                        img = img.add(&c.mul(&x.square_k_times(i as u32 * k, irr), irr));
                    }
                    assert!(img.is_zero(), "not in the kernel");
                }
            }
        }
    }

    #[test]
    fn subfield_factor_bases_are_invariant_and_solve_the_dlp() {
        // E_{0,2}/GF(4) over GF(2^14): r = 4159, h = 4.
        let kc = KoblitzCurve::subfield(2, 14, 0, 2).unwrap();
        let factors = invariant_factors(&kc);
        let idx = (0..factors.len())
            .filter_map(|i| {
                build_frobenius_factor_base_from_divisor(&kc, &[i]).map(|fb| (fb.points.len(), i))
            })
            .max()
            .map(|(_, i)| i)
            .unwrap();
        let fb = build_frobenius_factor_base_from_divisor(&kc, &[idx]).unwrap();
        assert!(fb.points.len() > 20, "{} points", fb.points.len());
        let keys = fb.index_map();
        for p in &fb.points {
            assert!(
                keys.contains_key(&point_key(&kc.frobenius(p))),
                "base not π_q-invariant"
            );
            assert!(keys.contains_key(&point_key(&point_neg(p))));
        }
        for orbit in &fb.orbits {
            assert_eq!(
                kc.extension_degree() % orbit.len() as u32,
                0,
                "orbit length divides e"
            );
        }
        assert!(fb.m_can_decompose(&kc, 2));
        let o = opts(2);
        // Relation rows are consistent with the true logarithms.
        let (table, report) = solve_factor_base_logs(&kc, &fb, &o).unwrap();
        assert!(report.verified, "{report:?}");
        assert!(table.verify(&kc));
        for k in [1u64, 2, 53, 4000] {
            let expected = BigUint::from(k);
            let q = kc.mul(kc.generator(), &expected);
            let (d, _) = individual_log(&kc, &fb, &table, &q, &o).unwrap();
            assert_eq!(d, expected);
        }
        // And the one-shot driver on the same base.
        let target = kc.mul(kc.generator(), &BigUint::from(777u32));
        let rep = koblitz_index_calculus_dlp_with_factor_base(&kc, &target, &fb, &o).unwrap();
        assert_eq!(rep.log, Some(BigUint::from(777u32)));
        // The search enumerates the subfield factor families and scores them.
        let sopts = SearchOptions {
            m: 2,
            min_dimension: 2,
            max_dimension: 8,
            max_abscissae: 4096,
            families: vec![Family::Factor, Family::Divisor],
            union_seed_dimensions: (2, 2),
            union_samples: 0,
            sample_targets: 64,
            exhaustive_cap: 4096,
            extra_relations: 2,
            prune: false,
            saturate: false,
            projected_columns: true,
            seed: 1,
            solve_cost_targets: None,
        };
        let sreport = search(&kc, &sopts);
        assert!(sreport.candidates.len() >= factors.len());
        assert!(sreport.best().is_some());
    }

    #[test]
    fn a_curve_without_points_over_a_binomial_subspace_is_reported_not_solved() {
        // E_{2,1}/GF(4) over GF(2^18): Tr(a) = 1, b = 1, x^9 − 1 splits
        // into binomials, and every invariant subspace carries only x = 0.
        let kc = KoblitzCurve::subfield(2, 18, 2, 1).unwrap();
        for idx in 0..invariant_factors(&kc).len() {
            let fb = build_frobenius_factor_base_from_divisor(&kc, &[idx]).unwrap();
            assert_eq!(fb.points.len(), 1);
            assert!(solve_factor_base_logs(&kc, &fb, &opts(2)).is_none());
        }
    }
}
