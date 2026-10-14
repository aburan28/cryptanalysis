//! # Prime-field hyperelliptic curves and Jacobian arithmetic.
//!
//! Companion to [`crate::binary_ecc::hyperelliptic`] for **odd
//! characteristic** (`p ≠ 2`).  Provides:
//!
//! - [`fp_poly::FpPoly`] — polynomial ring `F_p[x]` with the
//!   Euclidean machinery (add / mul / divrem / gcd / ext_gcd /
//!   evaluation / monic).
//! - [`curve::HyperellipticCurveP`] — `C : y² = f(x)` over a
//!   deterministically validated odd prime of at most 64 bits, with `f` monic
//!   and squarefree of exact degree `2g+1`.
//! - [`curve::MumfordDivisorP`] — reduced Mumford rep `(u, v)` with
//!   `u | v² − f`.
//! - **Cantor's algorithm**, char-`p` form: composition `gcd(u_1,
//!   u_2) → d_1`, `gcd(d_1, v_1 + v_2) → d`, combine; reduce by
//!   `u_new = (f − v²)/u` until `deg u ≤ g`.  The "no `h(x)`"
//!   simplification — char-`p` Mumford reps don't carry an
//!   `h(x) y` term.
//! - [`curve::brute_force_jac_order`] — exhaustive `#Jac(C)(F_p)`
//!   via Mumford-rep enumeration.  Toy-only (`p ≤ a few hundred`).
//! - [`curve::brute_force_jac_order_via_lpoly`] — alternative
//!   counting via `#C(F_p)` and `#C(F_{p²})`, then the genus-2
//!   `L`-polynomial relation `#Jac = L(1)`.  Its present exhaustive
//!   `F_{p²}` point counter is `O(p²)`, versus `O(p⁴)` for the
//!   naive Mumford-pair enumerator.
//!
//! This module is the substrate for
//! [`crate::cryptanalysis::p256_isogeny_cover`] — the Phase-1
//! existence indicator for the Kunzweiler–Pope `(N, N)`-split-
//! cover question applied to the Weil restriction of an `F_p`
//! elliptic curve.
//!
//! ## Scope
//!
//! - **One rational point at infinity only.**  Even-degree `2g+2` models
//!   require different divisor bookkeeping and are rejected.  In particular,
//!   this module does not implement the Jacobian of the repository's monic
//!   sextic `prime_quadratic_pullback_v1` cover.
//! - The checked Mumford arithmetic is genus-generic; exhaustive order
//!   enumeration and the `L`-polynomial counters remain genus-2 utilities.
//! - **Toy sizes only.**  All counting and enumeration routines are
//!   `O(p^c)` for small `c`; appropriate for `p ≤ ~10^3`.

pub mod curve;
pub mod fp2;
pub mod fp_poly;

pub use curve::{
    brute_force_jac_order, brute_force_jac_order_via_lpoly, count_points, count_points_fp2,
    fast_frob_ab, fast_point_counts, frob_ab_and_jac, jac_order_via_lpoly, FrobABForJac,
    HyperellipticCurveP, MumfordDivisorP, PrimeHyperellipticError, MAX_CHECKED_PRIME_BITS,
    MAX_POINT_ENUMERATION_PRIME, MAX_QUADRATIC_POINT_COUNT_PRIME,
};
pub use fp2::{enumerate_fp2, Fp2, Fp2ContextError, Fp2Ctx, MAX_FP2_MODULUS};
pub use fp_poly::FpPoly;
