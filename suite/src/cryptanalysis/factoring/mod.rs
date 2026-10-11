//! **Integer factorisation** — the attacks on RSA's hardness assumption,
//! from trial division to the Number Field Sieve.
//!
//! | module | method | cost to find `p \| n` | sweet spot here |
//! |---|---|---|---|
//! | [`rho_factor`] | Pollard–Brent rho | `O(√p)` | `p` ≲ 15 digits |
//! | [`pm1`](mod@pm1) | Pollard `p − 1`, Williams `p + 1` | `p ∓ 1` smooth | lucky `p` |
//! | [`crate::cryptanalysis::ecm`] | Lenstra ECM | `L_p[1/2, √2]` | `p` ≲ 25 digits (this ECM) |
//! | [`qs`](mod@qs) | self-initialising quadratic sieve | `L_n[1/2, 1]` | `n` ≲ 65 digits (60 digits ≈ 11 s) |
//! | [`nfs`] | general / special number field sieve | `L_n[1/3, 1.92]` / `L_n[1/3, 1.53]` | GNFS ≲ 60 digits (50 ≈ 5 s), SNFS difficulty ≲ 80 digits |
//! | [`rsa_attacks`] | Fermat, Wiener, Håstad, common modulus, cube root, batch GCD, `(n, e, d) → p, q` | structure, not size | weak RSA keys |
//! | [`auto`] | the ladder of all of the above | — | full factorisation |
//!
//! `L_n[α, c] = exp((c + o(1)) (ln n)^α (ln ln n)^{1−α})`.
//!
//! # Conventions
//!
//! Every entry point takes the number and a small `…Params` /
//! `…Options` struct whose [`Default`] is sensible, returns a result
//! struct that derives [`serde::Serialize`] (big integers serialise as
//! decimal strings), never prints, and **never reports a factor it has
//! not verified by multiplication**.  The long-running sieves accept an
//! optional [`ProgressFn`] callback.
//!
//! # Scale — read this before quoting a timing
//!
//! This is an educational implementation with production habits
//! (verification, statistics, tests), not msieve, YAFU or CADO-NFS.  It
//! has no lattice sieve, no bucket sieve, no Block Lanczos, no Kleinjung
//! polynomial selection and no SIMD.  Measured sizes and timings are in
//! the suite README and in `examples/nfs_demo.rs`; the per-module docs
//! state the limits.

pub mod arith;
pub mod auto;
pub mod nfs;
pub mod pm1;
pub mod qs;
pub mod rho_factor;
pub mod rsa_attacks;

pub use auto::{factor, FactorOptions, FactorReport, Method};
pub use nfs::gnfs::{gnfs, GnfsParams};
pub use nfs::snfs::{snfs, SnfsInput, SnfsParams};
pub use nfs::{NfsParams, NfsReport};
pub use pm1::{pm1, pp1, Pm1Params, Pm1Result, Pp1Params};
pub use qs::{qs, QsParams, QsReport};
pub use rho_factor::{rho, RhoParams, RhoResult};

/// A progress notification from a long-running sieve.
#[derive(Clone, Debug, serde::Serialize)]
pub struct Progress {
    /// Stage name: `"polyselect"`, `"sieve"`, `"filter"`, `"linalg"`, `"sqrt"`.
    pub stage: &'static str,
    /// Work done so far in this stage (relations, dependencies, …).
    pub done: u64,
    /// Target for this stage, if known.
    pub target: u64,
    /// Seconds since the method started.
    pub seconds: f64,
}

/// Optional progress callback: called from the calling thread only,
/// between batches of work.  `None` disables reporting.
pub type ProgressFn<'a> = Option<&'a dyn Fn(&Progress)>;

/// `serde` adapters that write big integers as decimal strings.
pub mod serde_big {
    /// `BigUint` as a decimal string.
    pub mod biguint {
        use num_bigint::BigUint;
        use serde::Serializer;
        /// Serialise.
        pub fn serialize<S: Serializer>(x: &BigUint, s: S) -> Result<S::Ok, S::Error> {
            s.serialize_str(&x.to_str_radix(10))
        }
    }
    /// `Option<BigUint>` as a decimal string or `null`.
    pub mod opt_biguint {
        use num_bigint::BigUint;
        use serde::Serializer;
        /// Serialise.
        pub fn serialize<S: Serializer>(x: &Option<BigUint>, s: S) -> Result<S::Ok, S::Error> {
            match x {
                Some(v) => s.serialize_str(&v.to_str_radix(10)),
                None => s.serialize_none(),
            }
        }
    }
    /// `Vec<BigUint>` as a list of decimal strings.
    pub mod vec_biguint {
        use num_bigint::BigUint;
        use serde::ser::{SerializeSeq, Serializer};
        /// Serialise.
        pub fn serialize<S: Serializer>(x: &[BigUint], s: S) -> Result<S::Ok, S::Error> {
            let mut seq = s.serialize_seq(Some(x.len()))?;
            for v in x {
                seq.serialize_element(&v.to_str_radix(10))?;
            }
            seq.end()
        }
    }
    /// `BigInt` as a decimal string.
    pub mod bigint {
        use num_bigint::BigInt;
        use serde::Serializer;
        /// Serialise.
        pub fn serialize<S: Serializer>(x: &BigInt, s: S) -> Result<S::Ok, S::Error> {
            s.serialize_str(&x.to_str_radix(10))
        }
    }
    /// `Vec<BigInt>` as a list of decimal strings.
    pub mod vec_bigint {
        use num_bigint::BigInt;
        use serde::ser::{SerializeSeq, Serializer};
        /// Serialise.
        pub fn serialize<S: Serializer>(x: &[BigInt], s: S) -> Result<S::Ok, S::Error> {
            let mut seq = s.serialize_seq(Some(x.len()))?;
            for v in x {
                seq.serialize_element(&v.to_str_radix(10))?;
            }
            seq.end()
        }
    }
}
