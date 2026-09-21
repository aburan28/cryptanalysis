//! # Prime-field hyperelliptic curves and Jacobian arithmetic.
//!
//! Companion to [`crate::binary_ecc::hyperelliptic`] for **odd
//! characteristic** (`p ≠ 2`).  Provides:
//!
//! - [`fp_poly::FpPoly`] — polynomial ring `F_p[x]` with the
//!   Euclidean machinery (add / mul / divrem / gcd / ext_gcd /
//!   evaluation / monic).
//! - [`curve::HyperellipticCurveP`] — `C : y² = f(x)` over `F_p` with
//!   `deg f ∈ {2g+1, 2g+2}`, `f` squarefree.
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
//!   `L`-polynomial relation `#Jac = L(1)`.  Faster: `O(p)` instead
//!   of `O(p²)`.
//!
//! This module is the substrate for
//! [`crate::cryptanalysis::p256_isogeny_cover`] — the Phase-1
//! existence indicator for the Kunzweiler–Pope `(N, N)`-split-
//! cover question applied to the Weil restriction of an `F_p`
//! elliptic curve.
//!
//! ## Scope
//!
//! - **Genus 2 only.**  The Mumford machinery generalises, but the
//!   probe needs only genus 2 (dim-2 abelian varieties).
//! - **Toy sizes only.**  All counting and enumeration routines are
//!   `O(p^c)` for small `c`; appropriate for `p ≤ ~10^3`.

pub mod curve;
pub mod fp2;
pub mod fp_poly;

pub use curve::{
    brute_force_jac_order, brute_force_jac_order_via_lpoly, count_points, count_points_fp2,
    fast_frob_ab, fast_point_counts, frob_ab_and_jac, jac_order_via_lpoly, FrobABForJac,
    HyperellipticCurveP, MumfordDivisorP,
};
pub use fp2::{enumerate_fp2, Fp2, Fp2Ctx};
pub use fp_poly::FpPoly;
