//! Solver options and statistics.

use std::mem::MaybeUninit;

use cryptanalysis_sys as sys;

/// Which algorithm [`Group::dlog`](crate::Group::dlog) uses inside each
/// prime-power subgroup after the Pohlig-Hellman reduction.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Default)]
#[repr(i32)]
pub enum Solver {
    /// BSGS for prime factors up to [`Options::bsgs_max_prime`], rho above.
    #[default]
    Auto = sys::CA_SOLVER_AUTO,
    /// Baby-step giant-step.
    Bsgs = sys::CA_SOLVER_BSGS,
    /// Pollard rho.
    Rho = sys::CA_SOLVER_RHO,
    /// Pollard kangaroo.
    Kangaroo = sys::CA_SOLVER_KANGAROO,
    /// Grumpy giants.
    Grumpy = sys::CA_SOLVER_GRUMPY,
    /// Exhaustive search (tiny subgroups / testing).
    Brute = sys::CA_SOLVER_BRUTE,
}

impl Solver {
    fn from_raw(v: i32) -> Solver {
        match v {
            sys::CA_SOLVER_BSGS => Solver::Bsgs,
            sys::CA_SOLVER_RHO => Solver::Rho,
            sys::CA_SOLVER_KANGAROO => Solver::Kangaroo,
            sys::CA_SOLVER_GRUMPY => Solver::Grumpy,
            sys::CA_SOLVER_BRUTE => Solver::Brute,
            _ => Solver::Auto,
        }
    }
}

/// Options shared by every discrete-logarithm solver.
///
/// Mirrors `ca_ffi_options`.  `Options::default()` returns the library
/// defaults (`ca_ffi_options_default`); each field documents its "auto"
/// value.  Fields that do not apply to the solver being called are ignored.
///
/// ```
/// use cryptanalysis::{Options, Solver};
/// let opts = Options { seed: 7, threads: 4, solver: Solver::Rho, ..Options::default() };
/// assert_eq!(opts.rho_dp_bits, -1);
/// ```
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Options {
    /// Worker threads for rho (0 => 1).
    pub threads: u32,
    /// RNG seed (0 => random).
    pub seed: u64,
    /// Work limit in group operations; solvers return
    /// [`Error::Limit`](crate::Error::Limit) when it is hit (0 => unlimited).
    pub max_ops: u64,
    /// BSGS: baby-step table size (0 => sqrt(width)).
    pub bsgs_table_size: u64,
    /// Rho: number of partitions of the walk (0 => auto).
    pub rho_r: u32,
    /// Rho: distinguished-point bits (-1 => auto).
    pub rho_dp_bits: i32,
    /// Rho: parallel walks per thread (0 => auto).
    pub rho_walks_per_thread: u32,
    /// Rho: use the negation map when the group supports it.
    pub rho_negation_map: bool,
    /// Rho: cap on distinguished-point table entries (0 => unlimited).
    pub rho_max_table_entries: u64,
    /// Kangaroo: herd size (0 => auto).
    pub kangaroo_herd_size: u32,
    /// Kangaroo: distinguished-point bits (-1 => auto).
    pub kangaroo_dp_bits: i32,
    /// Kangaroo: number of jump sizes (0 => auto).
    pub kangaroo_jumps: u32,
    /// Grumpy giants: m (0 => alpha*sqrt(width)).
    pub grumpy_m: u64,
    /// Grumpy giants: alpha (0 => 0.7).
    pub grumpy_alpha: f64,
    /// Solver used by [`Group::dlog`](crate::Group::dlog).
    pub solver: Solver,
    /// `Solver::Auto`: use BSGS for prime factors <= this (0 => 2^36).
    pub bsgs_max_prime: u64,
}

impl Default for Options {
    fn default() -> Self {
        let mut raw = MaybeUninit::<sys::CaFfiOptions>::uninit();
        // SAFETY: ca_ffi_options_default fully initialises the struct.
        let raw = unsafe {
            sys::ca_ffi_options_default(raw.as_mut_ptr());
            raw.assume_init()
        };
        Options::from_raw(&raw)
    }
}

impl Options {
    /// Convert to the C representation.
    pub fn to_raw(&self) -> sys::CaFfiOptions {
        sys::CaFfiOptions {
            threads: self.threads,
            reserved0: 0,
            seed: self.seed,
            max_ops: self.max_ops,
            bsgs_table_size: self.bsgs_table_size,
            rho_r: self.rho_r,
            rho_dp_bits: self.rho_dp_bits,
            rho_walks_per_thread: self.rho_walks_per_thread,
            rho_negation_map: i32::from(self.rho_negation_map),
            rho_max_table_entries: self.rho_max_table_entries,
            kangaroo_herd_size: self.kangaroo_herd_size,
            kangaroo_dp_bits: self.kangaroo_dp_bits,
            kangaroo_jumps: self.kangaroo_jumps,
            reserved1: 0,
            grumpy_m: self.grumpy_m,
            grumpy_alpha: self.grumpy_alpha,
            solver: self.solver as i32,
            reserved2: 0,
            bsgs_max_prime: self.bsgs_max_prime,
        }
    }

    /// Build from the C representation.
    pub fn from_raw(raw: &sys::CaFfiOptions) -> Options {
        Options {
            threads: raw.threads,
            seed: raw.seed,
            max_ops: raw.max_ops,
            bsgs_table_size: raw.bsgs_table_size,
            rho_r: raw.rho_r,
            rho_dp_bits: raw.rho_dp_bits,
            rho_walks_per_thread: raw.rho_walks_per_thread,
            rho_negation_map: raw.rho_negation_map != 0,
            rho_max_table_entries: raw.rho_max_table_entries,
            kangaroo_herd_size: raw.kangaroo_herd_size,
            kangaroo_dp_bits: raw.kangaroo_dp_bits,
            kangaroo_jumps: raw.kangaroo_jumps,
            grumpy_m: raw.grumpy_m,
            grumpy_alpha: raw.grumpy_alpha,
            solver: Solver::from_raw(raw.solver),
            bsgs_max_prime: raw.bsgs_max_prime,
        }
    }
}

/// Options for the precomputation solver [`Group::precomp`](crate::Group::precomp).
///
/// Mirrors the subset of `ca_precomp_params` exposed through the flat ABI.
/// `PrecompOptions::default()` selects the library defaults for every field.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PrecompOptions {
    /// Distinguished-point bits (`-1` => `round(log2(n) / 3)`).
    pub dp_bits: i32,
    /// Number of chains to build (0 => `coverage * n / 2^{2 dp_bits}`).
    pub table_size: u64,
    /// Precomputation coverage factor (0 => 1.0).
    pub coverage: f64,
    /// Build worker threads (0 => 1).
    pub threads: u32,
    /// RNG seed (0 => random).
    pub seed: u64,
}

impl Default for PrecompOptions {
    fn default() -> Self {
        PrecompOptions {
            dp_bits: -1,
            table_size: 0,
            coverage: 0.0,
            threads: 0,
            seed: 0,
        }
    }
}

/// Work statistics reported by every solver (`ca_stats`).
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct Stats {
    /// Group operations performed (adds/muls).
    pub group_ops: u64,
    /// Algorithm-specific step counter (e.g. exponentiations for Cheon).
    pub iterations: u64,
    /// Entries stored in lookup tables.
    pub table_entries: u64,
    /// Useful collisions / relations found.
    pub collisions: u64,
    /// Approximate peak heap usage of tables, in bytes.
    pub bytes_peak: u64,
    /// Wall-clock time spent.
    pub seconds: f64,
    /// Threads used.
    pub threads: u32,
}

impl Stats {
    pub(crate) fn from_raw(raw: &sys::CaStats) -> Stats {
        Stats {
            group_ops: raw.group_ops,
            iterations: raw.iterations,
            table_entries: raw.table_entries,
            collisions: raw.collisions,
            bytes_peak: raw.bytes_peak,
            seconds: raw.seconds,
            threads: raw.threads,
        }
    }
}
