//! # Binary elliptic-curve cryptography over `F_{2^m}`.
//!
//! Classical-side implementation of the building blocks in
//! **Putranto, Wardhani, Cho, Kim 2024** — *ECPM Cryptanalysis
//! Resource Estimation* (eprint, IEEE Access companion).  That
//! paper estimates quantum-circuit resources for Shor-based attacks
//! on binary elliptic curves; we ship the underlying **classical
//! reference implementation** that those quantum circuits compute
//! in superposition.
//!
//! ## Module map (matching the paper's ECC hierarchy)
//!
//! - **Level 1 — finite-field arithmetic in `F_{2^m}`**
//!   - [`f2m`] — polynomial-basis field elements, reduction modulo
//!     a fixed irreducible polynomial `m(z)`.
//!   - `f2m::karatsuba_mul` — the improved Karatsuba multiplication
//!     from Putranto et al. §3.1.
//!   - `f2m::flt_inverse` — Fermat-little-theorem inversion via
//!     Itoh-Tsujii (squaring chain), §3.2.
//!
//! - **Level 2 — point operations on `y² + xy = x³ + ax² + b`**
//!   - [`curve::BinaryCurve`] — curve parameters (a, b, irreducible
//!     polynomial, generator, order).
//!   - [`curve::BinaryPoint`] — affine point with explicit infinity.
//!   - [`curve::point_add`] — Point Addition (PA), formula in §3
//!     of the paper.
//!   - [`curve::point_double`] — Point Doubling (PD), §3.
//!
//! - **Level 3 — ECPM**
//!   - [`curve::scalar_mul`] — binary scalar multiplication
//!     (double-and-add), the operation whose quantum circuit
//!     `2n PD + 2 PA` was the paper's resource-estimation target.
//!
//! ## Standardised parameters (NIST / SEC 2)
//!
//! The paper analyses curves over `F_{2^n}` for `n ∈ {163, 233,
//! 283, 409, 571}`.  We ship the legacy sect113/sect131/sect163
//! families plus IKE/Oakley Group 3 for historical audit coverage,
//! and toy curves at smaller `n` for testing.
//!
//! ## Honest scope
//!
//! - **Classical, not quantum.**  The Putranto paper estimates
//!   quantum-circuit resources (qubits, gate depth) for these same
//!   operations executed in superposition under Shor's algorithm.
//!   Building those quantum circuits requires Qiskit or an
//!   equivalent simulator — out of scope for a Rust crypto library.
//!   This module provides the **classical reference** that those
//!   quantum circuits would have to compute in their core, plus the
//!   formula-level analysis used in the resource-counting tables.
//!
//! - **Variable-time.**  Like the rest of `zk` and `bls12_381`,
//!   these primitives use BigUint-style arithmetic without
//!   constant-time discipline.  Suitable for prover-side reference
//!   computation; not for attacker-controlled timing contexts.

pub mod curve;
pub mod f2m;
pub mod hyperelliptic;
pub mod poly_f2m;

pub use curve::{BinaryCurve, BinaryPoint};
pub use f2m::{F2mElement, IrreduciblePoly};
pub use hyperelliptic::{hcdlp_bsgs, hcdlp_pollard_rho, HyperellipticCurve, MumfordDivisor};
pub use poly_f2m::F2mPoly;
