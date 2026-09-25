//! Bounded experiments on internally generated, known-answer toy instances.
use super::params::{self, Field, Fixture, Parameters};
use clap::{Args, ValueEnum};
use cryptanalysis_suite::binary_ecc::{BinaryPoint, F2mElement};
use cryptanalysis_suite::cryptanalysis::koblitz_factor_base_search::{
    search_with_progress, Candidate, FactorBaseSpec, Family, SearchOptions, SearchReport,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    factor_x_n_minus_1, individual_log, koblitz_index_calculus_dlp_with_factor_base_and_progress,
    order_of_2_mod_n, solve_factor_base_logs, DecompositionStrategy, FactorBaseLogTable,
    FrobeniusFactorBase, KoblitzCurve, KoblitzIcEvent, KoblitzIcOptions, LinearAlgebra,
    LogTableReport, SharedDecider, MAX_N, MAX_SUBFIELD_DEGREE,
};
use cryptanalysis_suite::cryptanalysis::koblitz_sparse_la::{
    BlockWiedemannOptions, SparseSolveOptions,
};
use num_bigint::BigUint;
use rand::{rngs::StdRng, Rng, SeedableRng};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    fs::{File, OpenOptions},
    io::{Read, Write},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    time::{Duration, Instant},
};

/// Largest subspace dimension the legacy single-factor family may
/// materialise (`2^13` abscissae).  Spec-based bases are held to the
/// same abscissa count.
///
/// What the cap is really protecting is the pair table, which holds
/// `|F|(|F|+1)/2` entries of 16 bytes for `|F| ≈ 2·abscissae`: at 8192
/// abscissae that is about 2 GB, and every further doubling multiplies
/// it by four.  `PairSumTable::build` refuses past its own byte
/// budget, so a base that is too large for the machine fails with a
/// number rather than an allocation.
pub const MAX_FACTOR_DIMENSION: u32 = 13;
/// Abscissae a base may materialise to.
///
/// This was `1 << MAX_FACTOR_DIMENSION`, which is the right bound for a
/// subspace base — its abscissae are a dimension's worth and nothing
/// else chooses them.  A subgroup-orbit base has no such dimension, and
/// what actually bounds it is the pair table: while a stored pair cost
/// sixteen bytes the table refused anything past about 23000 points at
/// four gibibytes, which is under this cap anyway.  The compact table
/// stores four and a half bytes a pair and reaches about 42000 points at
/// the same budget, so this cap became the binding one.  It is raised to
/// sit above the memory bound rather than below it, and
/// `PairSumTable::build` still refuses past its own byte budget with a
/// number rather than an allocation.
///
/// Raised again for the same reason.  Folding the table by the signed
/// Frobenius group stores `n` times fewer pairs and reaches about 330000
/// points at four gibibytes — some 165000 abscissae — and `1 << 16` was
/// under that, so the cap was once more the thing refusing a base the
/// memory could hold.  `1 << 19` sits above the memory bound at every
/// degree this pipeline runs.
pub const MAX_ABSCISSAE: usize = 1 << 19;
pub fn degree(value: &str) -> Result<u32, String> {
    let n = value
        .parse::<u32>()
        .map_err(|_| "degree must be an integer")?;
    if !(3..=MAX_N).contains(&n) || n % 2 == 0 {
        return Err(format!(
            "synthetic degree must be odd and 3..={}",
            MAX_N - 1
        ));
    }
    Ok(n)
}
/// A field degree for a subfield curve: `k` times an odd number, so
/// even values are allowed here and the parity of `n / k` is checked
/// once `k` is known ([`curve`]).
pub fn field_degree(value: &str) -> Result<u32, String> {
    let n = value
        .parse::<u32>()
        .map_err(|_| "degree must be an integer")?;
    if !(3..=MAX_N).contains(&n) {
        return Err(format!("synthetic degree must be 3..={MAX_N}"));
    }
    Ok(n)
}
/// Label of a synthetic curve from its parameters, before it is built.
pub(crate) fn curve_label(n: u32, a: u8, k: u32, b: u64) -> String {
    if k == 1 {
        format!("K_{a} / GF(2^{n})")
    } else {
        format!("E_{{{a},{b}}}/GF(2^{k}) over GF(2^{n})")
    }
}
fn one_u32() -> u32 {
    1
}
fn one_u64() -> u64 {
    1
}
fn is_one_u32(v: &u32) -> bool {
    *v == 1
}
fn is_one_u64(v: &u64) -> bool {
    *v == 1
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, ValueEnum, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Solver {
    Groebner,
    Sat,
    Enumerate,
    /// Meet-in-the-middle over a precomputed pair-sum table.
    PairTable,
    /// Trimoska WDSat on the same Semaev ANF as `sat`.
    Wdsat,
    /// ALMASTY-inspired quadratic Semaev FES (`m = 2`): Gray early-exit,
    /// Möbius all-roots, Monica past `n = 24`.
    MqFes,
}
impl Solver {
    pub fn name(self) -> &'static str {
        match self {
            Self::Groebner => "groebner",
            Self::Sat => "sat",
            Self::Enumerate => "enumerate",
            Self::PairTable => "pair-table",
            Self::Wdsat => "wdsat",
            Self::MqFes => "mq-fes",
        }
    }
    fn strategy(self) -> DecompositionStrategy {
        match self {
            Self::Groebner => DecompositionStrategy::Groebner,
            Self::Sat => DecompositionStrategy::Sat,
            Self::Enumerate => DecompositionStrategy::Enumerate,
            Self::PairTable => DecompositionStrategy::PairTable,
            Self::Wdsat => DecompositionStrategy::Wdsat,
            Self::MqFes => DecompositionStrategy::MqFes,
        }
    }
}
/// How the factor-base logarithm precompute solves its relation matrix.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, ValueEnum, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LinearAlgebraMode {
    /// Dense big-integer Gaussian elimination after every new relation.
    Dense,
    /// Relation filtering (duplicates, singletons, excess, merge), then
    /// block Wiedemann on the reduced core.
    #[default]
    Sparse,
}
impl LinearAlgebraMode {
    pub fn name(self) -> &'static str {
        match self {
            Self::Dense => "dense",
            Self::Sparse => "sparse",
        }
    }
}
/// Select the linear-algebra path of `solve_factor_base_logs`.
pub(crate) fn with_linear_algebra(
    mut opts: KoblitzIcOptions,
    mode: LinearAlgebraMode,
    sparse: SparseSolveOptions,
) -> KoblitzIcOptions {
    opts.linear_algebra = match mode {
        LinearAlgebraMode::Dense => LinearAlgebra::Dense,
        LinearAlgebraMode::Sparse => LinearAlgebra::Sparse(sparse),
    };
    opts
}
/// Sparse-solve options with one block size for both sides of the
/// Krylov sequence; everything else at its default.
pub(crate) fn sparse_options(block_size: usize) -> SparseSolveOptions {
    SparseSolveOptions {
        wiedemann: BlockWiedemannOptions {
            block_m: block_size,
            block_n: block_size,
            ..BlockWiedemannOptions::default()
        },
        ..SparseSolveOptions::default()
    }
}
/// The linear-algebra part of a precompute report.
pub(crate) fn linear_algebra_json(report: &LogTableReport) -> Value {
    json!({
        "mode": if report.sparse { "sparse" } else { "dense" },
        "attempts": report.solve_attempts,
        "seconds": report.linear_algebra_seconds,
        "sparse": report.sparse_report.as_ref().map(|r| serde_json::to_value(r).unwrap_or(Value::Null)),
    })
}
/// A factor-base recipe saved by `ic search`, bound to the curve it was
/// found on so it cannot be replayed on a different one by accident.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FactorBaseDocument {
    pub schema_version: u32,
    pub degree: u32,
    pub curve_a: u8,
    /// Subfield degree `k` (1 for a Koblitz curve) and the coordinate of
    /// `b`; both default so Koblitz documents are unchanged.
    #[serde(default = "one_u32", skip_serializing_if = "is_one_u32")]
    pub subfield: u32,
    #[serde(default = "one_u64", skip_serializing_if = "is_one_u64")]
    pub curve_b: u64,
    pub spec: FactorBaseSpec,
}
impl FactorBaseDocument {
    /// Whether the document was written for `c`.
    pub fn matches(&self, c: &KoblitzCurve) -> bool {
        self.degree == c.n
            && self.curve_a == c.a
            && self.subfield == c.k
            && self.curve_b == c.b_index
    }
    pub fn label(&self) -> String {
        curve_label(self.degree, self.curve_a, self.subfield, self.curve_b)
    }
}
pub fn load_factor_base(path: &Path) -> Result<FactorBaseDocument, String> {
    let mut data = Vec::new();
    File::open(path)
        .map_err(|e| format!("{}: {e}", path.display()))?
        .take(1_048_577)
        .read_to_end(&mut data)
        .map_err(|e| e.to_string())?;
    if data.len() > 1_048_576 {
        return Err("factor-base file exceeds 1 MiB".into());
    }
    let doc: FactorBaseDocument =
        serde_json::from_slice(&data).map_err(|e| format!("invalid factor-base JSON: {e}"))?;
    if doc.schema_version != 1 {
        return Err("unsupported factor-base schema version".into());
    }
    Ok(doc)
}
#[derive(Clone, Debug, PartialEq, Args, Serialize)]
pub struct RunArgs {
    /// Field degree n of a generated GF(2^n) test curve (odd for the Koblitz family).
    #[arg(long,default_value_t=9,value_parser=field_degree)]
    pub degree: u32,
    /// Coefficient a: 0 or 1 for a Koblitz curve, else its coordinate in the subfield basis.
    #[arg(long,default_value_t=0,value_parser=clap::value_parser!(u8).range(0..=255))]
    pub curve_a: u8,
    /// Degree k of the subfield the curve is defined over (q = 2^k); 1 is the Koblitz family.
    #[arg(long,default_value_t=1,value_parser=clap::value_parser!(u32).range(1..=MAX_SUBFIELD_DEGREE as i64))]
    pub subfield: u32,
    /// Coordinate of b in the subfield basis (1 for Koblitz curves); 1..2^k.
    #[arg(long,default_value_t=1,value_parser=clap::value_parser!(u64).range(1..=255))]
    pub curve_b: u64,
    /// Public logarithm; defaults to 53 unless --random-target is selected.
    #[arg(long,value_parser=clap::value_parser!(u64).range(1..),conflicts_with="random_target")]
    pub known_log: Option<u64>,
    /// Generate a deterministic random known-answer target from --seed.
    #[arg(long)]
    pub random_target: bool,
    #[arg(long, default_value_t = 0x4b_6f_62_6c_69_74_7a_00u64)]
    pub seed: u64,
    /// Candidate index in the legacy degree-ord_n(2) factor-base family.
    #[arg(long, default_value_t = 0, conflicts_with = "factor_base")]
    pub factor_index: usize,
    /// Factor-base recipe saved by `ic search` (JSON); replaces --factor-index.
    #[arg(long)]
    pub factor_base: Option<PathBuf>,
    /// Factor-base points per relation (2, 3 or 4).
    #[arg(long,default_value_t=2,value_parser=clap::value_parser!(u8).range(2..=4))]
    pub summands: u8,
    #[arg(long,default_value_t=20_000,value_parser=clap::value_parser!(u32).range(1..=1_000_000))]
    pub max_trials: u32,
    #[arg(long,value_enum,default_value_t=Solver::Groebner)]
    pub solver: Solver,
    /// Path to a WDSat `wdsat_solver` binary; required for `--solver wdsat`.
    #[arg(long)]
    pub wdsat_binary: Option<PathBuf>,
    /// Soft wall-clock budget for one WDSat child process, in milliseconds.
    #[arg(long, default_value_t = 5_000)]
    pub wdsat_timeout_ms: u64,
    /// Targets decomposed per batch (in parallel); 0 selects the CPU count.
    #[arg(long,default_value_t=0,value_parser=clap::value_parser!(u32).range(0..=4096))]
    pub batch: u32,
    /// Legacy accounting: one column per Frobenius orbit, no cofactor
    /// projection merge, and a fixed-surplus collection before one solve.
    #[arg(long)]
    pub control: bool,
    /// Run each batch's Gröbner searches in lockstep and decide their
    /// Macaulay matrices together on this backend: `cpu`, `cuda[:N]` (an
    /// NVIDIA device, through libcuda and NVRTC), or `emulate[:threads]`
    /// (the GPU kernel on the host; needs the `gpu-emulator` feature).
    /// Relations, counters and the recovered logarithm are the same as
    /// without it.
    #[arg(long)]
    pub f4_backend: Option<String>,
}
impl Default for RunArgs {
    fn default() -> Self {
        Self {
            degree: 9,
            curve_a: 0,
            subfield: 1,
            curve_b: 1,
            known_log: None,
            random_target: false,
            seed: 0x4b_6f_62_6c_69_74_7a_00,
            factor_index: 0,
            factor_base: None,
            summands: 2,
            max_trials: 20_000,
            solver: Solver::Groebner,
            wdsat_binary: None,
            wdsat_timeout_ms: 5_000,
            batch: 0,
            control: false,
            f4_backend: None,
        }
    }
}
#[derive(Clone, Debug, Args)]
pub struct GenerateArgs {
    #[arg(long,default_value_t=9,value_parser=degree)]
    pub degree: u32,
    #[arg(long,default_value_t=0,value_parser=clap::value_parser!(u8).range(0..=1))]
    pub curve_a: u8,
    #[arg(long, default_value_t = 1)]
    pub seed: u64,
}
#[derive(Clone, Debug, Args)]
pub struct CompareArgs {
    #[arg(long,default_value_t=7,value_parser=degree)]
    pub degree: u32,
    #[arg(long,default_value_t=1,value_parser=clap::value_parser!(u8).range(0..=1))]
    pub curve_a: u8,
    #[arg(long, default_value_t = 1)]
    pub seed: u64,
    /// Identical generated training fixtures per candidate.
    #[arg(long,default_value_t=3,value_parser=clap::value_parser!(u32).range(1..=8))]
    pub samples: u32,
    /// Independent generated fixtures used to check the training winner.
    #[arg(long,default_value_t=2,value_parser=clap::value_parser!(u32).range(1..=8))]
    pub holdout: u32,
    #[arg(long,default_value_t=2000,value_parser=clap::value_parser!(u32).range(1..=20_000))]
    pub max_trials: u32,
    #[arg(long,default_value_t=30,value_parser=clap::value_parser!(u32).range(1..=120))]
    pub timeout_seconds: u32,
    #[arg(long,value_enum,default_value_t=Solver::Enumerate)]
    pub solver: Solver,
    #[arg(long,default_value_t=2,value_parser=clap::value_parser!(u8).range(2..=4))]
    pub summands: u8,
    #[arg(long)]
    pub control: bool,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, ValueEnum, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum FamilyArg {
    Factor,
    Divisor,
    Union,
    Subgroup,
    All,
}
#[derive(Clone, Debug, Args)]
pub struct SearchArgs {
    #[arg(long,default_value_t=15,value_parser=field_degree)]
    pub degree: u32,
    #[arg(long,default_value_t=1,value_parser=clap::value_parser!(u8).range(0..=255))]
    pub curve_a: u8,
    /// Degree k of the subfield the curve is defined over (q = 2^k); 1 is the Koblitz family.
    #[arg(long,default_value_t=1,value_parser=clap::value_parser!(u32).range(1..=MAX_SUBFIELD_DEGREE as i64))]
    pub subfield: u32,
    /// Coordinate of b in the subfield basis (1 for Koblitz curves); 1..2^k.
    #[arg(long,default_value_t=1,value_parser=clap::value_parser!(u64).range(1..=255))]
    pub curve_b: u64,
    /// Factor-base points per relation the base is scored for.
    #[arg(long,default_value_t=2,value_parser=clap::value_parser!(u8).range(2..=4))]
    pub summands: u8,
    /// Candidate families to score.
    #[arg(long,value_enum,default_value_t=FamilyArg::All)]
    pub family: FamilyArg,
    #[arg(long,default_value_t=3,value_parser=clap::value_parser!(u32).range(1..=MAX_FACTOR_DIMENSION as i64))]
    pub min_dimension: u32,
    #[arg(long,default_value_t=10,value_parser=clap::value_parser!(u32).range(1..=MAX_FACTOR_DIMENSION as i64))]
    pub max_dimension: u32,
    /// Skip candidates with more abscissae than this (pair table is quadratic in it).
    #[arg(long,default_value_t=2048,value_parser=clap::value_parser!(u32).range(2..=MAX_ABSCISSAE as i64))]
    pub max_abscissae: u32,
    /// Smallest and largest seed-space dimension for Frobenius unions.
    #[arg(long,default_value_t=2,value_parser=clap::value_parser!(u32).range(1..=10))]
    pub union_min_seed: u32,
    #[arg(long,default_value_t=5,value_parser=clap::value_parser!(u32).range(1..=10))]
    pub union_max_seed: u32,
    /// Random seed spaces per dimension, besides the standard basis.
    #[arg(long,default_value_t=3,value_parser=clap::value_parser!(u32).range(0..=64))]
    pub union_samples: u32,
    /// Sampled subgroup targets when the subgroup is too large to enumerate.
    #[arg(long,default_value_t=1024,value_parser=clap::value_parser!(u32).range(16..=65_536))]
    pub targets: u32,
    /// Enumerate every subgroup point when r − 1 is at most this.
    #[arg(long, default_value_t = 4096)]
    pub exhaustive_cap: u64,
    /// Surplus relations assumed when scoring.
    #[arg(long,default_value_t=2,value_parser=clap::value_parser!(u32).range(0..=64))]
    pub extra_relations: u32,
    /// Do not greedily prune orbits.
    #[arg(long)]
    pub no_prune: bool,
    /// Do not try 2-torsion saturations.
    #[arg(long)]
    pub no_saturate: bool,
    /// Score raw signed orbits instead of cofactor-projected columns.
    #[arg(long)]
    pub raw_columns: bool,
    /// Measure the Gröbner oracle on this many targets per candidate and
    /// rank by expected stage word XORs instead of expected trials.
    ///
    /// A trial is paid whether or not it succeeds, and the Weil-restricted
    /// system carries m·ℓ unknowns, so coverage alone can rank bases
    /// backwards: see research/notes/index-calculus/RESEARCH_FACTOR_BASE_SOLVE_COST.md. Off by default,
    /// so existing searches score exactly as before.
    #[arg(long,value_parser=clap::value_parser!(u32).range(1..=4096))]
    pub solve_cost_targets: Option<u32>,
    #[arg(long, default_value_t = 1)]
    pub seed: u64,
    /// Candidates (best census first) validated by real end-to-end runs.
    #[arg(long,default_value_t=3,value_parser=clap::value_parser!(u32).range(0..=16))]
    pub validate_top: u32,
    /// Generated holdout fixtures each validated candidate must solve.
    #[arg(long,default_value_t=2,value_parser=clap::value_parser!(u32).range(1..=8))]
    pub holdout: u32,
    #[arg(long,default_value_t=2000,value_parser=clap::value_parser!(u32).range(1..=20_000))]
    pub max_trials: u32,
    #[arg(long,default_value_t=60,value_parser=clap::value_parser!(u32).range(1..=600))]
    pub timeout_seconds: u32,
    /// Decomposition oracle used by the validation runs.
    #[arg(long,value_enum,default_value_t=Solver::PairTable)]
    pub solver: Solver,
    /// Write the selected factor-base recipe here (never overwrites).
    #[arg(long)]
    pub spec_out: Option<PathBuf>,
}
/// Precompute the factor-base logarithm database once for a curve.
#[derive(Clone, Debug, Args)]
pub struct LogsArgs {
    #[arg(long,default_value_t=9,value_parser=field_degree)]
    pub degree: u32,
    #[arg(long,default_value_t=0,value_parser=clap::value_parser!(u8).range(0..=255))]
    pub curve_a: u8,
    /// Degree k of the subfield the curve is defined over (q = 2^k); 1 is the Koblitz family.
    #[arg(long,default_value_t=1,value_parser=clap::value_parser!(u32).range(1..=MAX_SUBFIELD_DEGREE as i64))]
    pub subfield: u32,
    /// Coordinate of b in the subfield basis (1 for Koblitz curves); 1..2^k.
    #[arg(long,default_value_t=1,value_parser=clap::value_parser!(u64).range(1..=255))]
    pub curve_b: u64,
    /// Candidate index in the legacy degree-ord_n(2) factor-base family.
    #[arg(long, default_value_t = 0, conflicts_with = "factor_base")]
    pub factor_index: usize,
    /// Factor-base recipe saved by `ic search` (JSON); replaces --factor-index.
    #[arg(long)]
    pub factor_base: Option<PathBuf>,
    /// Factor-base points per relation (2, 3 or 4).
    #[arg(long,default_value_t=2,value_parser=clap::value_parser!(u8).range(2..=4))]
    pub summands: u8,
    #[arg(long,default_value_t=200_000,value_parser=clap::value_parser!(u32).range(1..=1_000_000))]
    pub max_trials: u32,
    #[arg(long,value_enum,default_value_t=Solver::PairTable)]
    pub solver: Solver,
    #[arg(long, default_value_t = 0x4b_6f_62_6c_69_74_7a_00u64)]
    pub seed: u64,
    /// How the relation matrix is solved: filtering + block Wiedemann
    /// (sparse) or dense big-integer elimination.
    #[arg(long, value_enum, default_value_t = LinearAlgebraMode::Sparse)]
    pub linear_algebra: LinearAlgebraMode,
    /// Block size (both sides) of the block Wiedemann Krylov sequence.
    #[arg(long,default_value_t=4,value_parser=clap::value_parser!(u8).range(1..=64))]
    pub block_size: u8,
    /// Write the logarithm database here; an existing path is never overwritten.
    #[arg(long = "database")]
    pub database: PathBuf,
}
/// Recover a target's logarithm by descent, reusing a saved database.
#[derive(Clone, Debug, Args)]
pub struct SolveArgs {
    #[arg(long,default_value_t=9,value_parser=field_degree)]
    pub degree: u32,
    #[arg(long,default_value_t=0,value_parser=clap::value_parser!(u8).range(0..=255))]
    pub curve_a: u8,
    /// Degree k of the subfield the curve is defined over (q = 2^k); 1 is the Koblitz family.
    #[arg(long,default_value_t=1,value_parser=clap::value_parser!(u32).range(1..=MAX_SUBFIELD_DEGREE as i64))]
    pub subfield: u32,
    /// Coordinate of b in the subfield basis (1 for Koblitz curves); 1..2^k.
    #[arg(long,default_value_t=1,value_parser=clap::value_parser!(u64).range(1..=255))]
    pub curve_b: u64,
    /// Logarithm database written by `ic logs`.
    #[arg(long)]
    pub logs: PathBuf,
    /// Public logarithm of the synthetic target; defaults to 53 unless --random-target.
    #[arg(long,value_parser=clap::value_parser!(u64).range(1..),conflicts_with="random_target")]
    pub known_log: Option<u64>,
    /// Draw a deterministic random known-answer target from --seed.
    #[arg(long)]
    pub random_target: bool,
    #[arg(long, default_value_t = 0x4b_6f_62_6c_69_74_7a_00u64)]
    pub seed: u64,
    #[arg(long,default_value_t=2,value_parser=clap::value_parser!(u8).range(2..=4))]
    pub summands: u8,
    #[arg(long,default_value_t=200_000,value_parser=clap::value_parser!(u32).range(1..=1_000_000))]
    pub max_trials: u32,
    #[arg(long,value_enum,default_value_t=Solver::PairTable)]
    pub solver: Solver,
}
/// A serialised factor-base logarithm database, bound to its curve and
/// factor base so it cannot be replayed on another.
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LogTableDocument {
    pub schema_version: u32,
    pub degree: u32,
    pub curve_a: u8,
    #[serde(default = "one_u32", skip_serializing_if = "is_one_u32")]
    pub subfield: u32,
    #[serde(default = "one_u64", skip_serializing_if = "is_one_u64")]
    pub curve_b: u64,
    pub spec: FactorBaseSpec,
    pub subgroup_order: String,
    pub cofactor: String,
    pub summands: u8,
    pub solver: Solver,
    /// `(x, y, log_G point)` per relation column; coordinates hex, log decimal.
    pub columns: Vec<LogColumn>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LogColumn {
    pub x: String,
    pub y: String,
    pub log: String,
}
pub fn load_log_table(path: &Path) -> Result<LogTableDocument, String> {
    let mut data = Vec::new();
    File::open(path)
        .map_err(|e| format!("{}: {e}", path.display()))?
        .take(16_777_217)
        .read_to_end(&mut data)
        .map_err(|e| e.to_string())?;
    if data.len() > 16_777_216 {
        return Err("logarithm database exceeds 16 MiB".into());
    }
    let doc: LogTableDocument = serde_json::from_slice(&data)
        .map_err(|e| format!("invalid logarithm database JSON: {e}"))?;
    if doc.schema_version != 1 {
        return Err("unsupported logarithm database schema version".into());
    }
    Ok(doc)
}
pub(crate) fn ic_options(
    strategy: Solver,
    summands: u8,
    max_trials: u32,
    seed: u64,
) -> KoblitzIcOptions {
    ic_options_with_descent(strategy, summands, None, None, max_trials, seed)
}

/// [`ic_options`] with a separate summand count for the descent and a
/// window for collection's third summand.
pub(crate) fn ic_options_with_descent(
    strategy: Solver,
    summands: u8,
    descent_summands: Option<u8>,
    collection_window: Option<u32>,
    max_trials: u32,
    seed: u64,
) -> KoblitzIcOptions {
    KoblitzIcOptions {
        m: summands as usize,
        descent_m: descent_summands.map(usize::from),
        collection_window: collection_window.map(|w| w as usize),
        strategy: strategy.strategy(),
        collapse_negation: true,
        collapse_projected_orbits: true,
        crossbred: None,
        allow_direct_relation: false,
        max_trials: max_trials as usize,
        seed,
        ..KoblitzIcOptions::default()
    }
}
/// Serialise a solved logarithm table, bound to its curve and factor base.
pub(crate) fn log_table_to_doc(
    c: &KoblitzCurve,
    spec: &FactorBaseSpec,
    summands: u8,
    solver: Solver,
    table: &FactorBaseLogTable,
) -> LogTableDocument {
    let columns: Vec<LogColumn> = table
        .columns
        .iter()
        .map(|(point, log)| match point {
            BinaryPoint::Affine { x, y } => LogColumn {
                x: params::hex(&x.to_biguint()),
                y: params::hex(&y.to_biguint()),
                log: log.to_string(),
            },
            BinaryPoint::Infinity => unreachable!("projected columns are affine"),
        })
        .collect();
    LogTableDocument {
        schema_version: 1,
        degree: c.n,
        curve_a: c.a,
        subfield: c.k,
        curve_b: c.b_index,
        spec: spec.clone(),
        subgroup_order: c.subgroup_order.to_string(),
        cofactor: c.cofactor.to_string(),
        summands,
        solver,
        columns,
    }
}
/// Rebuild a logarithm table from its document and re-verify every column
/// against the reconstructed curve; a tampered or mismatched table is an error.
pub(crate) fn log_table_from_doc(
    c: &KoblitzCurve,
    doc: &LogTableDocument,
) -> Result<FactorBaseLogTable, String> {
    if doc.degree != c.n
        || doc.curve_a != c.a
        || doc.subfield != c.k
        || doc.curve_b != c.b_index
        || doc.subgroup_order != c.subgroup_order.to_string()
    {
        return Err("logarithm database does not belong to this curve".into());
    }
    let mut columns = Vec::with_capacity(doc.columns.len());
    for col in &doc.columns {
        let x = F2mElement::from_biguint(&params::number(&col.x)?, c.n);
        let y = F2mElement::from_biguint(&params::number(&col.y)?, c.n);
        let log = params::number(&col.log)?;
        columns.push((BinaryPoint::Affine { x, y }, log));
    }
    let table = FactorBaseLogTable { columns };
    if !table.verify(c) {
        return Err("logarithm database failed re-verification: a column log does not satisfy [x]G == point".into());
    }
    Ok(table)
}
pub fn logs(args: LogsArgs, quiet: bool) -> Result<Value, String> {
    let begin = Instant::now();
    if std::fs::symlink_metadata(&args.database).is_ok() {
        return Err(format!(
            "logarithm database already exists: {}",
            args.database.display()
        ));
    }
    let spec = match &args.factor_base {
        Some(path) => {
            let doc = load_factor_base(path)?;
            if doc.degree != args.degree
                || doc.curve_a != args.curve_a
                || doc.subfield != args.subfield
                || doc.curve_b != args.curve_b
            {
                return Err(format!(
                    "factor-base recipe was found on {}, not {}",
                    doc.label(),
                    curve_label(args.degree, args.curve_a, args.subfield, args.curve_b)
                ));
            }
            doc.spec
        }
        None => {
            validate_factor_size(args.degree, args.subfield)?;
            FactorBaseSpec::Factor {
                index: args.factor_index,
            }
        }
    };
    let c = curve(args.degree, args.curve_a, args.subfield, args.curve_b)?;
    let fb = materialize(&c, &spec)?;
    if !quiet {
        println!(
            "ic — factor-base logarithm precomputation on {}; r = {}\nFactor base: {}; {} summands; engine {}; linear algebra {}",
            c.label(), c.subgroup_order,
            serde_json::to_string(&spec).unwrap_or_default(), args.summands, args.solver.name(),
            args.linear_algebra.name()
        );
        let _ = std::io::stdout().flush();
    }
    let opts = with_linear_algebra(
        ic_options(args.solver, args.summands, args.max_trials, args.seed),
        args.linear_algebra,
        sparse_options(usize::from(args.block_size)),
    );
    let (table, report) = solve_factor_base_logs(&c, &fb, &opts)
        .ok_or("factor base has no usable projected columns for this summand count")?;
    if !report.verified {
        return Ok(
            json!({"schema_version":1,"operation":"logs","status":"incomplete",
            "evidence_scope":"synthetic_known_answer",
            "reason":"relations did not determine every column logarithm within the trial budget",
            "degree":c.n,"curve_a":c.a,"factor_base":factor_base_json(&spec,&fb,report.columns),
            "counts":{"columns":report.columns,"trials":report.trials,"relations":report.relations},
            "linear_algebra":linear_algebra_json(&report),
            "elapsed_seconds":begin.elapsed().as_secs_f64(),"resources":resources()}),
        );
    }
    let doc = log_table_to_doc(&c, &spec, args.summands, args.solver, &table);
    write_new(
        &args.database,
        &serde_json::to_value(&doc).map_err(|e| e.to_string())?,
    )?;
    Ok(
        json!({"schema_version":1,"operation":"logs","status":"complete",
        "evidence_scope":"synthetic_known_answer","degree":c.n,"curve_a":c.a,
        "subgroup_order":c.subgroup_order.to_string(),"cofactor":c.cofactor.to_string(),
        "factor_base":factor_base_json(&spec,&fb,report.columns),
        "counts":{"columns":report.columns,"trials":report.trials,"relations":report.relations},
        "linear_algebra":linear_algebra_json(&report),
        "verified":true,"out":args.database.display().to_string(),
        "elapsed_seconds":begin.elapsed().as_secs_f64(),"resources":resources(),
        "scope":"once-per-curve factor-base logarithm database; every column log certified by [x]G == point",
        "limitations":["No imported target was used.","This precomputation does not establish scaling or challenge readiness."]}),
    )
}
pub fn solve(args: SolveArgs, quiet: bool) -> Result<Value, String> {
    let begin = Instant::now();
    let doc = load_log_table(&args.logs)?;
    if doc.degree != args.degree
        || doc.curve_a != args.curve_a
        || doc.subfield != args.subfield
        || doc.curve_b != args.curve_b
    {
        return Err(format!(
            "logarithm database was built on {}, not {}",
            curve_label(doc.degree, doc.curve_a, doc.subfield, doc.curve_b),
            curve_label(args.degree, args.curve_a, args.subfield, args.curve_b)
        ));
    }
    let c = curve(args.degree, args.curve_a, args.subfield, args.curve_b)?;
    if doc.subgroup_order != c.subgroup_order.to_string() {
        return Err(
            "logarithm database subgroup order does not match the reconstructed curve".into(),
        );
    }
    let fb = materialize(&c, &doc.spec)?;
    // Reconstruct the table and re-verify every column against the curve.
    let table = log_table_from_doc(&c, &doc)?;
    // Build the synthetic known-answer target.
    let k = if args.random_target {
        let mut rng = StdRng::seed_from_u64(args.seed ^ 0x534f_4c56_4552_5447);
        BigUint::from(rng.gen_range(1..c.subgroup_order.to_u64_digits()[0]))
    } else {
        BigUint::from(args.known_log.unwrap_or(53))
    };
    if k >= c.subgroup_order {
        return Err(format!(
            "known logarithm must be nonzero and smaller than subgroup order {}",
            c.subgroup_order
        ));
    }
    let target = c.mul(c.generator(), &k);
    if !quiet {
        println!(
            "ic — individual-logarithm descent on {}; r = {}\nDatabase: {} columns (verified); target log {k}; {} summands; engine {}",
            c.label(), c.subgroup_order, table.len(), args.summands, args.solver.name()
        );
        let _ = std::io::stdout().flush();
    }
    let opts = ic_options(args.solver, args.summands, args.max_trials, args.seed);
    let outcome = individual_log(&c, &fb, &table, &target, &opts);
    let (recovered, report) = match outcome {
        Some((d, r)) => (Some(d), r),
        None => (None, cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::IndividualLogReport::default()),
    };
    let verified = recovered.as_ref() == Some(&k)
        && recovered
            .as_ref()
            .is_some_and(|d| c.mul(c.generator(), d) == target);
    Ok(json!({"schema_version":1,"operation":"solve",
        "status":if verified{"complete"}else{"incomplete"},
        "evidence_scope":"synthetic_known_answer","degree":c.n,"curve_a":c.a,
        "database":{"columns":table.len(),"reverified":true,"spec":doc.spec,
            "source":args.logs.display().to_string(),"summands_precomputed":doc.summands},
        "result":{"expected":k.to_string(),"recovered":recovered.as_ref().map(ToString::to_string),"verified":verified},
        "counts":{"descent_trials":report.trials},
        "elapsed_seconds":begin.elapsed().as_secs_f64(),"resources":resources(),
        "scope":"per-target individual logarithm: one relation over a reused, re-verified factor-base logarithm database",
        "limitations":["No imported target was used.","This run does not establish scaling or challenge readiness."]}))
}
pub(crate) fn curve(n: u32, a: u8, k: u32, b: u64) -> Result<KoblitzCurve, String> {
    // Keep this guard even for internal callers, independently of Clap.
    if !(3..=MAX_N).contains(&n) || k == 0 || k > MAX_SUBFIELD_DEGREE || !n.is_multiple_of(k) {
        return Err("unsupported synthetic curve parameters: the degree must be a multiple of the subfield degree k, 1 ≤ k ≤ 8".into());
    }
    let e = n / k;
    if e < 3 || e.is_multiple_of(2) {
        return Err(format!(
            "unsupported synthetic curve parameters: the extension degree n/k = {e} must be odd and at least 3"
        ));
    }
    let q = 1u64 << k;
    if u64::from(a) >= q || b == 0 || b >= q {
        return Err(format!(
            "curve coefficients must be subfield coordinates: 0 ≤ a < {q} and 1 ≤ b < {q}"
        ));
    }
    KoblitzCurve::subfield(k, n, u64::from(a), b).ok_or_else(|| {
        format!(
            "{} has no usable prime-order subgroup in the existing constructor",
            curve_label(n, a, k, b)
        )
    })
}
fn known(curve: &KoblitzCurve, args: &RunArgs) -> Result<BigUint, String> {
    let n = if args.random_target {
        let mut rng = StdRng::seed_from_u64(args.seed ^ 0x534f_4c56_4552_5447);
        BigUint::from(rng.gen_range(1..curve.subgroup_order.to_u64_digits()[0]))
    } else {
        BigUint::from(args.known_log.unwrap_or(53))
    };
    if n >= curve.subgroup_order {
        return Err(format!(
            "known logarithm must be nonzero and smaller than subgroup order {}",
            curve.subgroup_order
        ));
    }
    Ok(n)
}
pub(crate) fn validate_factor_size(n: u32, k: u32) -> Result<u32, String> {
    // The legacy family is the top-degree factor of x^{n/k} − 1 over
    // GF(2^k): F_2-dimension k · ord_{n/k}(2^k).
    let e = if k >= 1 && n.is_multiple_of(k) {
        n / k
    } else {
        n
    };
    let order = if k == 1 {
        order_of_2_mod_n(e)
    } else {
        let q = (1u64 << k) % u64::from(e).max(1);
        let mut acc = 1u64;
        (1..=e).find(|_| {
            acc = acc * q % u64::from(e);
            acc == 1
        })
    };
    let dim = order
        .map(|o| o * k)
        .ok_or("no supported factor-base family for this degree")?;
    if dim > MAX_FACTOR_DIMENSION {
        return Err(format!("factor-base dimension {dim} exceeds the materialization limit {MAX_FACTOR_DIMENSION}; use ic search and --factor-base, or inspection and fixture generation"));
    }
    Ok(dim)
}
/// Resolve the factor base a run asks for: a saved recipe, or the
/// legacy single-factor family.
fn factor_base_spec(args: &RunArgs) -> Result<FactorBaseSpec, String> {
    match &args.factor_base {
        Some(path) => {
            let doc = load_factor_base(path)?;
            if doc.degree != args.degree
                || doc.curve_a != args.curve_a
                || doc.subfield != args.subfield
                || doc.curve_b != args.curve_b
            {
                return Err(format!(
                    "factor-base recipe was found on {}, not {}",
                    doc.label(),
                    curve_label(args.degree, args.curve_a, args.subfield, args.curve_b)
                ));
            }
            Ok(doc.spec)
        }
        None => {
            validate_factor_size(args.degree, args.subfield)?;
            Ok(FactorBaseSpec::Factor {
                index: args.factor_index,
            })
        }
    }
}
pub(crate) fn materialize(
    kc: &KoblitzCurve,
    spec: &FactorBaseSpec,
) -> Result<FrobeniusFactorBase, String> {
    let fb = spec.materialize(kc)?;
    if fb.subspace.len() > MAX_ABSCISSAE {
        return Err(format!(
            "factor base has {} abscissae, above the materialization limit {MAX_ABSCISSAE}",
            fb.subspace.len()
        ));
    }
    Ok(fb)
}
pub(crate) fn factor_base_json(
    spec: &FactorBaseSpec,
    fb: &FrobeniusFactorBase,
    columns: usize,
) -> Value {
    json!({"spec":spec,"family":spec.family(),
        "domain":cryptanalysis_suite::cryptanalysis::koblitz_factor_base_search::domain_label(&fb.domain),
        "dimension":fb.ell,"abscissae":fb.subspace.len(),"points":fb.points.len(),
        "signed_orbits":fb.unknowns(),"columns":columns})
}
fn parameters(c: &KoblitzCurve, k: &BigUint, seed: u64) -> Parameters {
    let mut terms = c.curve.irreducible.low_terms.clone();
    terms.push(c.n);
    Parameters {
        schema_version: 1,
        name: format!("synthetic-k{}-n{}", c.a, c.n),
        field: Field::Binary {
            degree: c.n,
            polynomial_terms: terms,
        },
        a: c.a.to_string(),
        b: "1".into(),
        subgroup_order: c.subgroup_order.to_string(),
        cofactor: c.cofactor.to_string(),
        generator: params::binary_coordinates(c.generator()),
        point: params::binary_coordinates(&c.mul(c.generator(), k)),
        fixture: Some(Fixture {
            known_log: k.to_string(),
            seed,
        }),
    }
}
pub fn generate(args: GenerateArgs) -> Result<Value, String> {
    let c = curve(args.degree, args.curve_a, 1, 1)?;
    let run = RunArgs {
        degree: args.degree,
        curve_a: args.curve_a,
        random_target: true,
        seed: args.seed,
        ..RunArgs::default()
    };
    let k = known(&c, &run)?;
    serde_json::to_value(parameters(&c, &k, args.seed)).map_err(|e| e.to_string())
}
pub fn resources() -> Value {
    #[cfg(any(target_os = "macos", target_os = "linux"))]
    {
        // libc defines the platform-specific layout; no shell/process inspection is used.
        let mut usage: libc::rusage = unsafe { std::mem::zeroed() };
        if unsafe { libc::getrusage(libc::RUSAGE_SELF, &mut usage) } == 0 {
            let multiplier = if cfg!(target_os = "macos") { 1 } else { 1024 };
            let seconds = |t: libc::timeval| t.tv_sec as f64 + t.tv_usec as f64 / 1_000_000.0;
            return json!({"cpu_seconds":seconds(usage.ru_utime)+seconds(usage.ru_stime),
                "peak_rss_bytes":usage.ru_maxrss.max(0) as u64*multiplier,
                "scope":"process counters sampled before report emission; peak resident memory, not allocated bytes"});
        }
    }
    json!({"cpu_seconds":null,"peak_rss_bytes":null,"scope":"measurement unavailable on this platform"})
}
fn batch_size(requested: u32) -> usize {
    if requested == 0 {
        std::thread::available_parallelism()
            .map(|n| n.get())
            .unwrap_or(1)
    } else {
        requested as usize
    }
}
pub fn run(args: RunArgs, quiet: bool) -> Result<Value, String> {
    let begin = Instant::now();
    if args.max_trials == 0 || args.max_trials > 1_000_000 {
        return Err("trial limit must be 1..=1000000".into());
    }
    if args.solver == Solver::Wdsat && args.wdsat_binary.is_none() {
        return Err("--solver wdsat requires --wdsat-binary".into());
    }
    let spec = factor_base_spec(&args)?;
    if !quiet {
        println!(
            "ic — synthetic index-calculus experiment\nConstructing {} ...",
            curve_label(args.degree, args.curve_a, args.subfield, args.curve_b)
        );
        let _ = std::io::stdout().flush();
    }
    let c = curve(args.degree, args.curve_a, args.subfield, args.curve_b)?;
    let k = known(&c, &args)?;
    let supplied = parameters(&c, &k, args.seed);
    let target = c.mul(c.generator(), &k);
    let batch = batch_size(args.batch);
    if !quiet {
        println!(
            "Known logarithm: {k}; subgroup order: {}\nEngine: {}; summands: {}; factor base: {}; batch: {batch}{}",
            c.subgroup_order,
            args.solver.name(),
            args.summands,
            serde_json::to_string(&spec).unwrap_or_default(),
            if args.control { "; control accounting" } else { "" }
        );
    }
    let f4_setup = Instant::now();
    let f4_batch = match &args.f4_backend {
        Some(spec) => Some(SharedDecider::new(
            cryptanalysis_suite::cryptanalysis::f4_gpu::decider_from_spec(spec)
                .map_err(|e| format!("--f4-backend {spec}: {e}"))?,
        )),
        None => None,
    };
    let f4_setup_seconds = f4_setup.elapsed().as_secs_f64();
    let opts = KoblitzIcOptions {
        m: args.summands as usize,
        strategy: args.solver.strategy(),
        factor_index: args.factor_index,
        max_trials: args.max_trials as usize,
        seed: args.seed,
        collapse_negation: !args.control,
        collapse_projected_orbits: !args.control,
        crossbred: None,
        stop_on_verified_rank: !args.control,
        allow_direct_relation: false,
        relation_batch_size: batch,
        wdsat_binary: args.wdsat_binary.clone(),
        wdsat_timeout_ms: args.wdsat_timeout_ms,
        f4_batch,
        ..KoblitzIcOptions::default()
    };
    let mut stages = Vec::new();
    let mut stage_start = Instant::now();
    let record = |stages: &mut Vec<Value>,
                  stage: &str,
                  state: &str,
                  details: Value,
                  stage_start: &mut Instant| {
        if state == "started" {
            *stage_start = Instant::now();
        }
        let elapsed = stage_start.elapsed().as_secs_f64();
        if !quiet {
            let (index, label) = match stage {
                "factor_base" => (1, "Factor base"),
                "pair_table" => (1, "Pair table"),
                "relation_collection" => (2, "Relation collection"),
                "linear_algebra" => (3, "Linear algebra"),
                _ => (4, "Verification"),
            };
            println!("[{index}/4] {label}: {state} {details} ({elapsed:.3}s)");
            let _ = std::io::stdout().flush();
        }
        stages.push(
            json!({"stage":stage,"status":state,"details":details,"elapsed_seconds":elapsed}),
        );
    };
    record(
        &mut stages,
        "factor_base",
        "started",
        json!({}),
        &mut stage_start,
    );
    let fb = match materialize(&c, &spec) {
        Ok(fb) => fb,
        Err(reason) => {
            return Ok(
                json!({"schema_version":1,"operation":"run","status":"incomplete","evidence_scope":"synthetic_known_answer",
                "reason":format!("factor-base construction failed: {reason}"),"arguments":args,"parameters":supplied,
                "factor_base":{"spec":spec},"stages":stages,"elapsed_seconds":begin.elapsed().as_secs_f64(),"resources":resources()}),
            );
        }
    };
    let mut columns = 0usize;
    let report = koblitz_index_calculus_dlp_with_factor_base_and_progress(
        &c,
        &target,
        &fb,
        &opts,
        &mut |event| {
            let (stage, state, details) = match event {
                KoblitzIcEvent::FactorBaseStarted => ("factor_base", "started", json!({})),
                KoblitzIcEvent::FactorBaseReady { points, orbits } => {
                    columns = orbits;
                    (
                        "factor_base",
                        "complete",
                        json!({"points":points,"columns":orbits}),
                    )
                }
                KoblitzIcEvent::PairTableReady { entries } => {
                    ("pair_table", "complete", json!({"entries":entries}))
                }
                KoblitzIcEvent::RelationCollectionStarted { wanted } => {
                    ("relation_collection", "started", json!({"wanted":wanted}))
                }
                KoblitzIcEvent::RelationProgress {
                    collected,
                    wanted,
                    trials,
                } => {
                    if !quiet {
                        println!(
                            "      {collected}/{wanted} relations; {trials} trials; {:.3}s",
                            stage_start.elapsed().as_secs_f64()
                        );
                        let _ = std::io::stdout().flush();
                    }
                    return;
                }
                KoblitzIcEvent::RelationAttemptFinished { .. } => return,
                KoblitzIcEvent::RelationCollectionFinished { collected, trials } => (
                    "relation_collection",
                    "stopped",
                    json!({"collected":collected,"trials":trials}),
                ),
                KoblitzIcEvent::LinearAlgebraStarted { rows, columns } => (
                    "linear_algebra",
                    "started",
                    json!({"rows":rows,"columns":columns}),
                ),
                KoblitzIcEvent::LinearAlgebraFinished => ("linear_algebra", "complete", json!({})),
                KoblitzIcEvent::LinearAlgebraIncomplete => {
                    ("linear_algebra", "incomplete", json!({}))
                }
                KoblitzIcEvent::MatrixRank {
                    rows,
                    columns,
                    rank,
                    candidate_produced,
                } => (
                    "linear_algebra",
                    "rank",
                    json!({"rows":rows,"columns":columns,"rank":rank,
                        "candidate_produced":candidate_produced}),
                ),
                KoblitzIcEvent::LinearAlgebraSkipped => ("linear_algebra", "skipped", json!({})),
                KoblitzIcEvent::VerificationStarted => ("verification", "started", json!({})),
                KoblitzIcEvent::VerificationFinished { verified } => (
                    "verification",
                    if verified { "pass" } else { "fail" },
                    json!({}),
                ),
            };
            record(&mut stages, stage, state, details, &mut stage_start);
        },
    );
    let factor_base = factor_base_json(&spec, &fb, columns);
    let mode = json!({"control":args.control,"collapse_negation":!args.control,
        "collapse_projected_orbits":!args.control,"early_solve":!args.control,"batch":batch});
    let Some(r) = report else {
        return Ok(
            json!({"schema_version":1,"operation":"run","status":"incomplete","evidence_scope":"synthetic_known_answer",
            "reason":"factor-base construction or pipeline operation did not complete; no result asserted",
            "arguments":args,"parameters":supplied,"factor_base":factor_base,"mode":mode,"stages":stages,
            "elapsed_seconds":begin.elapsed().as_secs_f64(),"resources":resources()}),
        );
    };
    let verified = r.sat_invalid_models == 0
        && r.inconsistent_relations == 0
        && r.verification_failures == 0
        && r.log.as_ref() == Some(&k)
        && r.log
            .as_ref()
            .is_some_and(|d| c.mul(c.generator(), d) == target)
        && !r.direct_relation;
    Ok(
        json!({"schema_version":1,"operation":"run","status":if verified{"complete"}else{"incomplete"},
        "evidence_scope":"synthetic_known_answer","arguments":args,"parameters":supplied,"factor_base":factor_base,"mode":mode,"stages":stages,
        "result":{"expected":k.to_string(),"recovered":r.log.as_ref().map(ToString::to_string),"verified":verified},
        "counts":{"factor_base_points":r.factor_base_size,"columns":r.orbit_count,"relations":r.relations,
            "independent_relations":r.independent_relations,"dependent_relations":r.dependent_relations,
            "inconsistent_relations":r.inconsistent_relations,"verification_failures":r.verification_failures,
            "trials":r.trials,"batches":r.relation_batches,"pair_table_entries":r.pair_table_entries,
            "algebra_cache_current_thread":cryptanalysis_suite::cryptanalysis::algebra_cache::stats(),
            "f4_reductions":r.reductions,
            "f4_word_ops":cryptanalysis_suite::cryptanalysis::koblitz_groebner::f4_profile().word_ops,"sat_calls":r.sat_calls,"sat_unknowns":r.sat_unknowns,"sat_invalid_models":r.sat_invalid_models,
            "sat_conflicts":r.sat_conflicts,"linear_solve_attempts":r.linear_solve_attempts,"cofactor_admissible":r.m_cofactor_admissible},
        "timing_seconds":{"pair_table":r.pair_table_ns as f64/1e9,"relation_collection":r.relation_collection_ns as f64/1e9,
            "linear_algebra":r.linear_algebra_ns as f64/1e9},
        "f4_batch":{"backend":r.f4_batch_backend,"rounds":r.f4_batch_rounds,"requests":r.f4_batch_requests,
            "decide_seconds":r.f4_batch_decide_ns as f64/1e9,"setup_seconds":f4_setup_seconds,
            "kernel":format!("{:?}",cryptanalysis_suite::cryptanalysis::koblitz_groebner::f4_kernel()),
            "f5":cryptanalysis_suite::cryptanalysis::f4_gf2::default_options().f5},
        "attempt_dispositions":disposition_counts(&r.attempt_records),
        "elapsed_seconds":begin.elapsed().as_secs_f64(),"resources":resources(),
        "limitations":["No imported target was used.","This run does not establish scaling or challenge readiness."]}),
    )
}
/// How every relation attempt ended, by disposition: the decomposition
/// oracle's outcome mix, failed and budget-exhausted attempts included.
fn disposition_counts(
    records: &[cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::KoblitzRelationAttemptRecord],
) -> Value {
    let mut counts = std::collections::BTreeMap::<String, usize>::new();
    for r in records {
        *counts.entry(format!("{:?}", r.disposition)).or_default() += 1;
    }
    json!(counts)
}

fn child(args: &RunArgs, seconds: u32) -> Result<Value, String> {
    let start = Instant::now();
    let mut command = Command::new(std::env::current_exe().map_err(|e| e.to_string())?);
    command.args([
        "run",
        "--json",
        "--degree",
        &args.degree.to_string(),
        "--curve-a",
        &args.curve_a.to_string(),
        "--seed",
        &args.seed.to_string(),
        "--max-trials",
        &args.max_trials.to_string(),
        "--solver",
        args.solver.name(),
        "--summands",
        &args.summands.to_string(),
        "--batch",
        &args.batch.to_string(),
    ]);
    match &args.factor_base {
        Some(path) => {
            command.arg("--factor-base").arg(path);
        }
        None => {
            command.args(["--factor-index", &args.factor_index.to_string()]);
        }
    }
    if args.control {
        command.arg("--control");
    }
    if args.random_target {
        command.arg("--random-target");
    } else if let Some(k) = args.known_log {
        command.args(["--known-log", &k.to_string()]);
    }
    let mut proc = command
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| e.to_string())?;
    let stdout = proc.stdout.take().unwrap();
    let stderr = proc.stderr.take().unwrap();
    let out = std::thread::spawn(move || {
        let mut v = Vec::new();
        stdout.take(1_048_577).read_to_end(&mut v).map(|_| v)
    });
    let err = std::thread::spawn(move || {
        let mut v = Vec::new();
        stderr.take(65_537).read_to_end(&mut v).map(|_| v)
    });
    let mut timed_out = false;
    let status = loop {
        if let Some(s) = proc.try_wait().map_err(|e| e.to_string())? {
            break s;
        }
        if start.elapsed() >= Duration::from_secs(seconds as u64) {
            timed_out = true;
            let _ = proc.kill();
            break proc.wait().map_err(|e| e.to_string())?;
        }
        std::thread::sleep(Duration::from_millis(10));
    };
    let stdout = out
        .join()
        .map_err(|_| "output reader failed")?
        .map_err(|e| e.to_string())?;
    let stderr = err
        .join()
        .map_err(|_| "error reader failed")?
        .map_err(|e| e.to_string())?;
    if timed_out {
        return Ok(
            json!({"status":"timed_out","elapsed_seconds":start.elapsed().as_secs_f64(),"arguments":args,"resources":null}),
        );
    }
    if stdout.len() > 1_048_576 {
        return Err("child report exceeded its output limit".into());
    }
    let mut report: Value = serde_json::from_slice(&stdout).unwrap_or_else(
        |_| json!({"status":"failed","error":String::from_utf8_lossy(&stderr),"arguments":args}),
    );
    if !status.success() && report["status"] == "complete" {
        report["status"] = json!("failed");
    }
    report["process_elapsed_seconds"] = json!(start.elapsed().as_secs_f64());
    Ok(report)
}
fn median(values: &mut [f64]) -> f64 {
    values.sort_by(f64::total_cmp);
    let n = values.len();
    if n.is_multiple_of(2) {
        (values[n / 2 - 1] + values[n / 2]) / 2.0
    } else {
        values[n / 2]
    }
}
pub fn compare(args: CompareArgs, quiet: bool) -> Result<Value, String> {
    let started = Instant::now();
    validate_factor_size(args.degree, 1)?;
    let _ = curve(args.degree, args.curve_a, 1, 1)?;
    let count = factor_x_n_minus_1(args.degree).len();
    if count == 0 || count > 16 {
        return Err("candidate count is outside the bounded comparison range 1..=16".into());
    }
    let mut candidates = Vec::new();
    let mut winner = None;
    let mut best = f64::INFINITY;
    for index in 0..count {
        let mut trials = Vec::new();
        let mut costs = Vec::new();
        for sample in 0..args.samples {
            if !quiet {
                println!(
                    "Candidate {}/{}; training fixture {}/{}",
                    index + 1,
                    count,
                    sample + 1,
                    args.samples
                );
                let _ = std::io::stdout().flush();
            }
            let opts = RunArgs {
                degree: args.degree,
                curve_a: args.curve_a,
                random_target: true,
                seed: args.seed.wrapping_add(sample as u64),
                factor_index: index,
                max_trials: args.max_trials,
                solver: args.solver,
                summands: args.summands,
                control: args.control,
                ..RunArgs::default()
            };
            let result = child(&opts, args.timeout_seconds)?;
            if result["status"] == "complete" && result["result"]["verified"] == true {
                if let Some(cost) = result["process_elapsed_seconds"].as_f64() {
                    costs.push(cost);
                }
            }
            trials.push(result);
        }
        let eligible = costs.len() == args.samples as usize;
        let med = if eligible {
            Some(median(&mut costs))
        } else {
            None
        };
        if let Some(cost) = med {
            if cost < best {
                best = cost;
                winner = Some(index);
            }
        }
        candidates.push(json!({"factor_index":index,"eligible":eligible,"median_process_seconds":med,"training":trials}));
    }
    let mut holdout = Vec::new();
    if let Some(index) = winner {
        for sample in 0..args.holdout {
            if !quiet {
                println!(
                    "Candidate {index}; holdout fixture {}/{}",
                    sample + 1,
                    args.holdout
                );
                let _ = std::io::stdout().flush();
            }
            let opts = RunArgs {
                degree: args.degree,
                curve_a: args.curve_a,
                random_target: true,
                seed: (args.seed ^ 0x484f_4c44_4f55_5400).wrapping_add(sample as u64),
                factor_index: index,
                max_trials: args.max_trials,
                solver: args.solver,
                summands: args.summands,
                control: args.control,
                ..RunArgs::default()
            };
            holdout.push(child(&opts, args.timeout_seconds)?);
        }
    }
    let accepted = winner.is_some()
        && holdout.len() == args.holdout as usize
        && holdout
            .iter()
            .all(|v| v["status"] == "complete" && v["result"]["verified"] == true);
    Ok(
        json!({"schema_version":1,"operation":"compare","status":if accepted{"complete"}else{"inconclusive"},
        "evidence_scope":"bounded_synthetic_comparison","degree":args.degree,"curve_a":args.curve_a,
        "seed":args.seed,"solver":args.solver,"summands":args.summands,"control":args.control,"samples":args.samples,"holdout_samples":args.holdout,
        "candidate_family":"degree-ord_n(2) irreducible factors used by the existing materialized builder",
        "candidate_count":count,"candidates":candidates,"training_winner":winner,"selected_factor_index":if accepted{winner}else{None},
        "holdout":holdout,"elapsed_seconds":started.elapsed().as_secs_f64(),"resources":resources(),
        "selection_metric":"median child-process wall time including startup, construction, collection, solve, verification, and report emission",
        "completion_poll_interval_ms":10,
        "scope":"fastest observed eligible candidate on these training fixtures, with correctness checked on separate holdout fixtures",
        "limitations":["Not a global optimum or an asymptotic result.","Failed and timed-out cases remain in the report and are ineligible.",
            "Child resource metrics cover separate processes; parent metrics exclude child CPU and memory.","No imported target was used."]}),
    )
}
/// Exclusive creation of a JSON document; an existing path is an error.
pub fn write_new(path: &Path, value: &Value) -> Result<(), String> {
    let text = serde_json::to_string_pretty(value).map_err(|e| e.to_string())?;
    OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(path)
        .and_then(|mut f| {
            f.write_all(text.as_bytes())?;
            f.write_all(b"\n")?;
            f.sync_all()
        })
        .map_err(|e| format!("could not create {}: {e}", path.display()))
}
struct TempSpec(PathBuf);
impl TempSpec {
    fn new(doc: &FactorBaseDocument, tag: usize) -> Result<Self, String> {
        let path = std::env::temp_dir().join(format!(
            "ic-search-{}-{}-{tag}.json",
            std::process::id(),
            doc.degree
        ));
        let _ = std::fs::remove_file(&path);
        write_new(
            &path,
            &serde_json::to_value(doc).map_err(|e| e.to_string())?,
        )?;
        Ok(Self(path))
    }
}
impl Drop for TempSpec {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.0);
    }
}
fn candidate_summary(c: &Candidate) -> Value {
    let census = c.census.as_ref();
    json!({"spec":c.spec,"family":c.family,"domain":c.domain,"dimension":c.dimension,
        "abscissae":c.abscissae,"points":c.points,"signed_orbits":c.signed_orbits,
        "projected_columns":c.projected_columns,"unknowns":c.unknowns,"cofactor_admissible":c.cofactor_admissible,
        "coverage":census.map(|x| x.coverage),"covered":census.map(|x| x.covered),
        "mean_witnesses":census.map(|x| x.mean_witnesses),
        "expected_trials":census.map(|x| if x.expected_trials.is_finite(){json!(x.expected_trials)}else{Value::Null}),
        "enumeration_ops_per_trial":c.enumeration_ops_per_trial,"pair_table_lookups_per_trial":c.pair_table_lookups_per_trial,
        "sat_variables":c.sat_variables,"build_ms":c.build_ms,"census_ms":census.map(|x| x.census_ms),
        "trace_zero":c.trace_zero,
        "measured_ops_per_target":c.measured_ops_per_target,
        "expected_stage_ops":c.expected_stage_ops,
        "solve_cost_skipped":c.solve_cost_skipped,
        "prune_steps":c.prune_steps,"skipped":c.skipped})
}
pub fn search(args: SearchArgs, quiet: bool) -> Result<Value, String> {
    let started = Instant::now();
    if args.min_dimension > args.max_dimension || args.union_min_seed > args.union_max_seed {
        return Err("dimension windows must be non-decreasing".into());
    }
    if let Some(path) = &args.spec_out {
        if std::fs::symlink_metadata(path).is_ok() {
            return Err(format!("spec output already exists: {}", path.display()));
        }
    }
    // Scoring one oracle and running another selects for the wrong thing.
    if args.solve_cost_targets.is_some() {
        if args.solver != Solver::Groebner {
            return Err(format!(
                "--solve-cost-targets measures the Gröbner oracle, but the runs would use {}; \
                 pass --solver groebner or drop --solve-cost-targets",
                args.solver.name()
            ));
        }
        // A replayed reduction reports as free, so a warm cache would price
        // the candidates measured later at a fraction of their cost.
        // Only a replayed *reduction* skips the counter: word_ops is added
        // inside matrix_f4_f2_counted, so a preprocessing hit still runs F4.
        use cryptanalysis_suite::cryptanalysis::algebra_cache::{enabled, Layer};
        if enabled(Layer::ExactReduction) {
            return Err(
                "--solve-cost-targets cannot measure while replayed reductions report as free; \
                 unset IC_REDUCTION_CACHE"
                    .into(),
            );
        }
    }
    let kc = curve(args.degree, args.curve_a, args.subfield, args.curve_b)?;
    let families = match args.family {
        FamilyArg::Factor => vec![Family::Factor],
        FamilyArg::Divisor => vec![Family::Divisor],
        FamilyArg::Union => vec![Family::Union],
        FamilyArg::Subgroup => vec![Family::Subgroup],
        FamilyArg::All => vec![
            Family::Factor,
            Family::Divisor,
            Family::Union,
            Family::Subgroup,
        ],
    };
    let options = SearchOptions {
        m: args.summands as usize,
        min_dimension: args.min_dimension,
        max_dimension: args.max_dimension,
        max_abscissae: args.max_abscissae as usize,
        families,
        union_seed_dimensions: (args.union_min_seed, args.union_max_seed),
        union_samples: args.union_samples as usize,
        sample_targets: args.targets as usize,
        exhaustive_cap: args.exhaustive_cap,
        extra_relations: args.extra_relations as usize,
        prune: !args.no_prune,
        saturate: !args.no_saturate,
        projected_columns: !args.raw_columns,
        seed: args.seed,
        solve_cost_targets: args.solve_cost_targets.map(|t| t as usize),
    };
    if !quiet {
        println!(
            "ic — factor-base search on {}; r = {}; h = {}; {} summands",
            kc.label(),
            kc.subgroup_order,
            kc.cofactor,
            args.summands
        );
        let _ = std::io::stdout().flush();
    }
    let report: SearchReport = search_with_progress(&kc, &options, &mut |i, total, c| {
        if !quiet {
            let census = c.census.as_ref();
            println!(
                "  [{i}/{total}] {:<22} points {:>5}  columns {:>4}  coverage {}  expected trials {}{}",
                c.family,
                c.points,
                c.unknowns,
                census.map_or("   —  ".into(), |x| format!("{:6.3}", x.coverage)),
                census.map_or("—".into(), |x| if x.expected_trials.is_finite() {
                    format!("{:.1}", x.expected_trials)
                } else {
                    "∞".into()
                }),
                c.expected_stage_ops
                    .map(|ops| format!("  stage word XORs {ops:.3e}"))
                    .or_else(|| c.solve_cost_skipped.as_ref().map(|r| format!("  (unpriced: {r})")))
                    .unwrap_or_default()
                    + &c.skipped
                        .as_ref()
                        .map_or(String::new(), |s| format!("  ({s})"))
            );
            let _ = std::io::stdout().flush();
        }
    });
    let census_ms = started.elapsed().as_secs_f64() * 1000.0;

    // Validate the best few by real end-to-end runs on fresh fixtures.
    let mut validations = Vec::new();
    let mut winner: Option<(usize, f64)> = None;
    let scored: Vec<(usize, &Candidate)> = report
        .candidates
        .iter()
        .enumerate()
        .filter(|(_, c)| c.score().is_finite())
        .take(args.validate_top as usize)
        .collect();
    for (rank, candidate) in scored {
        let doc = FactorBaseDocument {
            schema_version: 1,
            degree: kc.n,
            curve_a: kc.a,
            subfield: kc.k,
            curve_b: kc.b_index,
            spec: candidate.spec.clone(),
        };
        let temp = TempSpec::new(&doc, rank)?;
        let mut runs = Vec::new();
        let mut costs = Vec::new();
        for sample in 0..args.holdout {
            if !quiet {
                println!(
                    "Validating candidate #{}: {}; holdout fixture {}/{}",
                    rank + 1,
                    serde_json::to_string(&candidate.spec).unwrap_or_default(),
                    sample + 1,
                    args.holdout
                );
                let _ = std::io::stdout().flush();
            }
            let run_args = RunArgs {
                degree: kc.n,
                curve_a: kc.a,
                random_target: true,
                seed: (args.seed ^ 0x5345_4152_4348_4f55).wrapping_add(sample as u64),
                factor_base: Some(temp.0.clone()),
                summands: args.summands,
                max_trials: args.max_trials,
                solver: args.solver,
                ..RunArgs::default()
            };
            let result = child(&run_args, args.timeout_seconds)?;
            if result["status"] == "complete" && result["result"]["verified"] == true {
                if let Some(cost) = result["process_elapsed_seconds"].as_f64() {
                    costs.push(cost);
                }
            }
            runs.push(result);
        }
        let eligible = costs.len() == args.holdout as usize;
        let med = eligible.then(|| median(&mut costs));
        if let Some(cost) = med {
            if winner.is_none_or(|(_, best)| cost < best) {
                winner = Some((rank, cost));
            }
        }
        validations.push(
            json!({"rank":rank+1,"spec":candidate.spec,"eligible":eligible,
            "median_process_seconds":med,"holdout":runs}),
        );
    }
    let selected = winner.map(|(rank, _)| &report.candidates[rank]);
    let selected_doc = selected.map(|c| FactorBaseDocument {
        schema_version: 1,
        degree: kc.n,
        curve_a: kc.a,
        subfield: kc.k,
        curve_b: kc.b_index,
        spec: c.spec.clone(),
    });
    if let (Some(path), Some(doc)) = (&args.spec_out, &selected_doc) {
        write_new(path, &serde_json::to_value(doc).map_err(|e| e.to_string())?)?;
    }
    let status = if selected.is_some() {
        "complete"
    } else if args.validate_top == 0 && report.best().is_some() {
        "unvalidated"
    } else {
        "inconclusive"
    };
    // What ranked the report is what was measured, not what was requested.
    let measured_any = report
        .candidates
        .iter()
        .any(|c| c.expected_stage_ops.is_some());
    let mut limitations = vec![
        "Coverage is exact on the target set, which is the whole subgroup only when exhaustive_targets is true.".to_string(),
        "Selected means fastest validated on these holdout fixtures, not a global optimum.".to_string(),
        "No imported target was used.".to_string(),
    ];
    let scoring = if let (Some(t), true) = (args.solve_cost_targets, measured_any) {
        limitations.push(format!(
            "Solve cost is the mean over {t} census targets of one oracle, the Gröbner one, and only for \
             linear-subspace candidates; pruned, saturated, union and orbit bases are left unmeasured and \
             ranked below every measured one (see solve_cost_skipped)."
        ));
        limitations.push(
            "Base construction, lifting, filtering and the relation linear algebra are not in the score; \
             all of them grow with the base size, so pricing them would favour the smaller base further."
                .to_string(),
        );
        "expected_stage_ops = expected_trials × measured Gröbner word XORs per census target, charged on \
         decomposing and refuted targets alike; expected_trials = (columns + 1 + extra) / coverage"
    } else {
        if args.solve_cost_targets.is_some() {
            limitations.push(
                "Solve cost was requested but no candidate could be priced, so this report is ranked by \
                 expected trials; see solve_cost_skipped on each candidate."
                    .to_string(),
            );
        }
        limitations.push(
            "Expected trials ignore per-trial oracle cost; the validation runs measure wall time with the \
             chosen oracle. Pass --solve-cost-targets to rank by measured solving cost instead."
                .to_string(),
        );
        "expected_trials = (columns + 1 + extra) / coverage, coverage measured exactly on the shared target \
         set by enumerating every m-summand witness through a pair-sum table"
    };
    Ok(
        json!({"schema_version":1,"operation":"search","status":status,
        "evidence_scope":"exact_yield_census_with_synthetic_validation",
        "degree":kc.n,"curve_a":kc.a,"subgroup_order":kc.subgroup_order.to_string(),"cofactor":kc.cofactor.to_string(),
        "summands":args.summands,"options":report.options,"targets":report.targets,"exhaustive_targets":report.exhaustive_targets,
        "candidate_count":report.candidates.len(),
        "candidates":report.candidates.iter().map(candidate_summary).collect::<Vec<_>>(),
        // best_census keeps its name for frozen consumers; best_scored is the
        // same candidate named after the objective that actually ranked it.
        "best_census":report.best().map(|c| c.spec.clone()),
        "best_scored":report.best().map(|c| c.spec.clone()),
        "validation":{"solver":args.solver,"holdout_samples":args.holdout,"max_trials":args.max_trials,
            "timeout_seconds":args.timeout_seconds,"validated_top":args.validate_top,"runs":validations},
        "selected":selected_doc,"selected_summary":selected.map(candidate_summary),
        "spec_out":args.spec_out.as_ref().filter(|_| selected.is_some()).map(|p| p.display().to_string()),
        "census_ms":census_ms,"elapsed_seconds":started.elapsed().as_secs_f64(),"resources":resources(),
        "scoring":scoring,"scoring_objective":if measured_any{"expected_stage_ops"}else{"expected_trials"},
        "limitations":limitations}),
    )
}
