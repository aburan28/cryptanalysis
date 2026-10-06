//! The research command lines that predate `crax`, as library modules.
//!
//! Each keeps its own parser, output format and exit status; `crax` hands
//! its `ic`, `icx` and suite subcommands to them unchanged, and the
//! `ca-ic`, `ca-icx` and `ca-suite` binaries are shims over the same code.

pub mod ic;
pub mod icx;
pub mod suite;
