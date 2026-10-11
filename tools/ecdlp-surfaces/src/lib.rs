//! Exact small-field examples of elliptic-curve representations and ECDLP transfers.
//!
//! A containing quadric has the elliptic group law only on the embedded curve.
//! These constructions do not establish an ECDLP speedup.

pub mod cli;
pub mod curve;
pub mod frobenius;
pub mod json;

pub type Result<T> = std::result::Result<T, String>;
