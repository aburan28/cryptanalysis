//! Cryptanalysis of ML-KEM and ML-DSA: the lattice attacks, their cost models,
//! and the implementation-level attacks that actually break deployments.
//!
//! # Layout
//!
//! * [`params`] — the six standardised parameter sets restated as LWE and SIS
//!   instances.
//! * [`cost`] — what BKZ-β achieves (basis profiles) and what it costs (SVP
//!   models). Every disagreement in the literature about these schemes' margins
//!   lives here, not in the attacks.
//! * [`primal`] — the primal/uSVP attack: embed, reduce, read off the secret.
//! * [`dual`] — the dual attack, including the MATZOV-style variant with
//!   guessing, modulus switching and an FFT distinguisher, plus the
//!   Ducas–Pulles contradictory-regime check and the smoothing condition that
//!   the provable analyses rely on.
//! * [`hybrid`] — hybrid attacks: trade lattice dimension for guessing, which
//!   a bounded secret makes worthwhile.
//! * [`sieve`] — actual working sieves (Gauss, Nguyen–Vidick, and a bucketed
//!   near-neighbour sieve) and a progressive-BKZ driver over them. These *run*,
//!   in dimensions where running is possible, and exist so the cost models
//!   above are anchored to something measured rather than only asserted.
//! * [`report`] — every attack against every parameter set in every cost model,
//!   as one table.
//!
//! # What this module is and is not
//!
//! It is an estimator and a set of working attack implementations at research
//! scale. It reproduces the *structure* of the published attacks and, where a
//! closed-form condition exists, that condition exactly. It is not a
//! re-derivation of any paper's tables: several of the refined cost models in
//! the literature involve fitted constants and optimisation choices that their
//! authors' own code makes, and where we simplify, the doc comment says so.
//!
//! When a number here disagrees with a published one, the safe reading is that
//! the models differ, and [`cost::BkzModel::label`] says which one produced it.

pub mod cost;
pub mod dual;
pub mod hybrid;
pub mod params;
pub mod primal;
pub mod report;
pub mod sieve;

pub use cost::{BkzModel, Profile, Reps, SvpModel};
pub use params::{Category, LweInstance, Norm, SisInstance};
