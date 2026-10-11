//! Speed-oriented implementations of the post-quantum schemes.
//!
//! Each module here is byte-for-byte interchangeable with its readable
//! counterpart in the parent module, and the tests say so: every one is
//! differentially tested against the reference implementation, which is itself
//! validated against the NIST vectors. The reference stays; this is not a
//! replacement but a second implementation held to the first.
//!
//! Measured costs, and what moved them, are in `docs/pqc-speed.md`.
//!
//! The same caveat as the rest of the library applies with more force here:
//! **this is not constant-time and must not be used in production.** Speed work
//! and side-channel resistance pull in opposite directions, and only the first
//! was the goal. See `SECURITY.md`.

pub mod isogeny;
pub mod keccak;
pub mod ml_dsa;
pub mod ml_kem;
