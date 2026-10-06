//! # Isogeny / Complex-Multiplication research module.
//!
//! Research-grade infrastructure for studying whether the isogeny class
//! structure of CM elliptic curves leaks information about the discrete
//! logarithm.  The intended workflow is:
//!
//! 1. Pick a small curve `E/F_p` (60–80 bits in this implementation).
//! 2. Compute its Frobenius trace, CM discriminant, and endomorphism
//!    ring conductor ([`cm`]).
//! 3. Walk the `ℓ`-isogeny volcano around `E` ([`volcano`], [`velu`]).
//! 4. Build the full `ℓ`-isogeny graph for a chosen set of small
//!    primes ([`graph`]).
//! 5. Run a battery of generic and CM-aware attacks across every
//!    curve in the class ([`attack`]) and compare empirical cost
//!    ([`experiment`]).
//!
//! ## Mathematical references
//!
//! - **Sutherland, A.**: *Isogeny volcanoes*.  ANTS-X, 2013.
//!   The canonical modern treatment of the volcano structure of the
//!   `ℓ`-isogeny graph of ordinary curves.
//! - **Kohel, D.**: *Endomorphism rings of elliptic curves over
//!   finite fields*.  PhD thesis, UC Berkeley, 1996.  Original
//!   source of the "Kohel algorithm" for computing
//!   `End(E)` via volcano traversal.
//! - **Couveignes, J.-M.**: *Hard homogeneous spaces*.  IACR ePrint
//!   2006/291.  The class-group action on CM curves that underpins
//!   CSIDH and the older Rostovtsev–Stolbunov construction.
//! - **Rostovtsev, A., Stolbunov, A.**: *Public-key cryptosystem
//!   based on isogenies*.  IACR ePrint 2006/145.  Independent
//!   rediscovery of the same action.
//! - **Vélu, J.**: *Isogénies entre courbes elliptiques*.
//!   C. R. Acad. Sci. Paris, 1971.  The original explicit formulas
//!   for the codomain curve and the rational maps of an isogeny
//!   from its kernel.
//! - **Cohen, H.**: *A course in computational algebraic number
//!   theory*, GTM 138, 1993.  §5.3 (binary quadratic forms),
//!   §5.6 (class number).
//! - **Silverman, J.**: *The arithmetic of elliptic curves*, GTM 106.
//!   Chapter III for isogenies; Appendix A for CM.
//!
//! ## Scale caveat
//!
//! Nothing here is intended to scale to cryptographic-size curves
//! (secp256k1, P-256).  The Frobenius trace is computed by brute-
//! force point counting (`O(p)`), Vélu uses explicit point
//! enumeration of the kernel, and class-group composition uses
//! plain Gauss reduction without NUCOMP/NUDUPL.  All asymptotically
//! better algorithms (SEA point counting, structured Vélu, NUCOMP)
//! are documented in their respective modules but not implemented
//! — see [`crate::cryptanalysis::hilbert_class_poly`] and
//! [`crate::cryptanalysis::modular_polynomial`] for the
//! cryptographic-scale-aware machinery already in the crate.

pub mod attack;
pub mod class_group;
pub mod cm;
pub mod experiment;
pub mod graph;
pub mod secp256k1_analysis;
pub mod velu;
pub mod volcano;

// ── Top-level re-exports for the most-used types ──────────────────────────────
pub use class_group::{class_number, BinaryQuadraticForm, ClassGroup};
pub use cm::{cm_discriminant, frobenius_trace, CmData, EndomorphismRing};
pub use experiment::{run_experiment, ExperimentConfig, ExperimentReport};
pub use graph::{IsogenyGraph, IsogenyNode};
pub use velu::{velu_isogeny_2, velu_isogeny_odd, VeluIsogeny};
pub use volcano::{VolcanoLevel, VolcanoMap};

// ── Small toy curves used by the unit tests and CLI demo ─────────────────────
//
// These are deliberately tiny so a human can run point-by-point through
// them on paper.  They are *not* cryptographically secure; they exist
// so that every algorithm in this module can be exercised in
// milliseconds with predictable, hand-checkable output.

use num_bigint::BigUint;

/// Toy curve `y² = x³ + 4x + 4` over `F_2003`.  Ordinary, with CM by
/// the order of discriminant `D = -7995` (after Frobenius trace
/// computation), good for shaking out volcano walks at `ℓ ∈ {2, 3, 5}`.
pub fn toy_curve_a() -> SmallCurve {
    SmallCurve {
        name: "toy-2003",
        p: 2003,
        a: 4,
        b: 4,
    }
}

/// Toy curve `y² = x³ + x + 1` over `F_101`.  The textbook example
/// used by Sutherland's *Isogeny volcanoes* lecture notes; the
/// 2-volcano has crater size 1 and depth 1.
pub fn toy_curve_b() -> SmallCurve {
    SmallCurve {
        name: "toy-101",
        p: 101,
        a: 1,
        b: 1,
    }
}

/// Toy curve `y² = x³ + 1` over `F_103` (the smallest j=0 example).
/// Has CM by `Z[ω]` where `ω = (-1 + √-3)/2`, just like secp256k1.
pub fn toy_curve_j0() -> SmallCurve {
    SmallCurve {
        name: "toy-j0-103",
        p: 103,
        a: 0,
        b: 1,
    }
}

/// A tiny `u64`-only curve descriptor used throughout this module's
/// experimental harness.  Working in `u64` makes Frobenius-trace
/// point counting and full-graph enumeration fit comfortably in
/// memory; we marshal to `BigUint` only when bridging to the
/// existing [`crate::ecc::point::Point`] arithmetic.
#[derive(Clone, Copy, Debug, PartialEq, Eq, serde::Serialize)]
pub struct SmallCurve {
    pub name: &'static str,
    /// Field prime.  Must satisfy `p < 2^62` for the experimental
    /// harness to avoid overflow in unmodulated intermediates.
    pub p: u64,
    /// Coefficient `a` in `y² = x³ + ax + b`.
    pub a: u64,
    /// Coefficient `b` in `y² = x³ + ax + b`.
    pub b: u64,
}

impl SmallCurve {
    /// Promote to a `CurveParams`-shaped record so the existing
    /// [`crate::ecc::point::Point`] arithmetic can be used over this
    /// curve.  We do not know the group order until point-counting
    /// has run, so we leave `n = 0` and let the caller fill it in.
    pub fn to_curve_params(&self) -> crate::ecc::curve::CurveParams {
        crate::ecc::curve::CurveParams {
            // CurveParams::name is &'static str; we keep this field
            // referencing the SmallCurve's static name.
            name: self.name,
            p: BigUint::from(self.p),
            a: BigUint::from(self.a),
            b: BigUint::from(self.b),
            gx: BigUint::from(0u32),
            gy: BigUint::from(0u32),
            n: BigUint::from(0u32),
            h: 1,
        }
    }

    /// Right-hand side of the Weierstrass equation,
    /// `x³ + a·x + b  mod  p`.
    pub fn rhs(&self, x: u64) -> u64 {
        let p = self.p as u128;
        let xm = (x as u128) % p;
        let x2 = (xm * xm) % p;
        let x3 = (x2 * xm) % p;
        let ax = ((self.a as u128) * xm) % p;
        ((x3 + ax + self.b as u128) % p) as u64
    }
}
