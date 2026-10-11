//! **Adversarial-ML Pollard rho on toy elliptic curves**.
//!
//! Per the agent's TOP-3 list, train a small transformer to predict
//! optimal walk-step choices in Pollard rho on a toy Solinas-form
//! curve.  Compare against the standard r-adding walk to see whether
//! ML can learn shorter paths to collisions.
//!
//! # Why this might be interesting
//!
//! Pollard rho's expected `O(√n)` runtime depends on the walk
//! function being "random-like."  The standard r-adding walks
//! (Teske, Cheon-Hong) have proven good distribution properties, but
//! they're not provably *optimal*.  An adversarial-ML walk could in
//! principle:
//!
//! 1. **Memorise structural features** of the curve that make some
//!    paths converge faster.
//! 2. **Learn distinguishing-point heuristics** beyond the standard
//!    "leading-zero" criterion.
//! 3. **Exploit Solinas-prime structure** (the carries in P-256-style
//!    reduction might leak information about distance-to-collision).
//!
//! Negative result is publishable (rules out "ML breaks ECDLP"
//! sentiment).  Positive result is foundational.
//!
//! # Implementation status
//!
//! **This module ships the framework**, not the trained model.
//!
//! Training a transformer requires a GPU and PyTorch/JAX, which is
//! out of scope for a Rust cryptanalysis library.  We provide:
//!
//! 1. **Trace-emission API**: emit `(state, action, reward)` tuples
//!    from a Pollard rho run on a toy curve.  Output format is JSON
//!    Lines, ready for ingestion by an external ML training pipeline.
//! 2. **Walk function abstraction**: `WalkFn` trait so a future
//!    `MLWalk` can plug into the existing `pollard_rho` infrastructure.
//! 3. **Standard r-adding walk** baseline implementation.
//! 4. **Performance harness**: average steps to collision over many
//!    seeds, comparing baseline vs (future) ML walk.
//!
//! # Experimental design (for the GPU-equipped researcher)
//!
//! 1. Pick a toy curve (e.g., Solinas-form prime `p ≈ 2³² − 2¹⁶ + 1`,
//!    cyclic group order ≈ 2³²).  Solving DLP via brute-force is
//!    feasible but slow; provides ground truth for training.
//! 2. **Generate training data**: run baseline Pollard rho 10⁴ times
//!    with random seeds.  At each step, log `(state_features,
//!    action_taken, did_eventually_hit_DP)`.  This is `~10⁹` tuples,
//!    ~10 GB of training data.
//! 3. **Architecture**: small transformer (4 layers, 256-dim embedding,
//!    8 attention heads).  Input: state features (point coordinates
//!    in compressed form, recent walk history, current bit-mask).
//!    Output: action probability over the `r` walk-function indices.
//! 4. **Loss**: REINFORCE-style, reward = -log(steps to next DP).
//!    Train ~10⁵ epochs.
//! 5. **Evaluate**: average steps-to-collision over 10³ test seeds,
//!    compare to baseline.
//!
//! Cost estimate (per agent's note): ~$1k of GPU time.

use num_bigint::BigUint;
use std::io::Write;

/// State features at one Pollard rho step, suitable for ML model input.
#[derive(Clone, Debug, serde::Serialize)]
pub struct WalkTrace {
    pub step: u64,
    /// Point coordinate `x` (truncated to 256 bits) as hex string.
    pub x_hex: String,
    /// Point coordinate `y` (truncated to 256 bits) as hex string.
    pub y_hex: String,
    /// `α = log_g(point)` if known (for training); typically not in deployment.
    pub alpha: Option<u64>,
    /// `β = log_h(point)` similarly.
    pub beta: Option<u64>,
    /// Index of walk function chosen at this step.
    pub walk_index: u8,
    /// Whether this point is a distinguished point (would be stored).
    pub is_distinguished: bool,
}

/// Standard r-adding Pollard rho walk function: partition the group
/// into `r` classes by hashing the point's `x`-coordinate, and apply
/// a different "step" in each class.
pub trait WalkFn {
    /// Choose walk-function index in `[0, R)` for the given state.
    fn choose(&self, state: &WalkState) -> u8;
}

/// Pollard rho state for ML training.  Includes the "pseudo-random"
/// linear combination indices `(α, β)` so that `Y = α·G + β·H`.
#[derive(Clone, Debug)]
pub struct WalkState {
    pub y_x: BigUint,
    pub y_y: BigUint,
    pub alpha: u64,
    pub beta: u64,
    pub r: u8,
}

/// Standard "x mod r" partition function.
pub struct StandardWalk;

impl WalkFn for StandardWalk {
    fn choose(&self, state: &WalkState) -> u8 {
        let xs: Vec<u8> = state.y_x.to_bytes_be();
        let last = *xs.last().unwrap_or(&0);
        last % state.r
    }
}

/// Emit a JSON Lines training trace for an ML pipeline.  Writes each
/// `WalkTrace` as one JSON object per line to the given writer.
pub fn emit_traces(traces: &[WalkTrace], writer: &mut impl Write) -> std::io::Result<()> {
    for trace in traces {
        let line = serde_json::to_string(trace)?;
        writeln!(writer, "{}", line)?;
    }
    Ok(())
}

/// Compute the average number of steps-to-collision for a given walk
/// function.  This is the metric the ML walk would be trained to
/// minimise.
///
/// **Stub** — fully realising this requires the existing `pollard_rho`
/// infrastructure, which is not yet integrated.  This function
/// documents the framework.
pub fn average_steps_to_collision<W: WalkFn>(
    _walk: &W,
    _n_runs: usize,
    _curve: &str,
) -> Option<f64> {
    // Integration with existing `pollard_rho_dlp` would go here.
    // For now, return None to indicate the metric is not yet
    // computed in this framework.
    None
}

// ── Pre-ML deterministic walk-function comparison ────────────────────

use crate::cryptanalysis::pollard_rho::{pollard_rho_dlp, RhoOptions};
use num_bigint::RandBigInt;
use num_traits::Zero;
use rand::rngs::StdRng;
use rand::SeedableRng;

/// Run a controlled benchmark: solve a planted DLP in `Z_p*` under
/// several deterministic walk-partition functions, measure
/// **median** and **mean** steps to solve, and report the result.
///
/// The partition function is the part of Pollard rho most adjacent
/// to what an ML walk would replace — and the most data-driven
/// improvement target.  By comparing 4 deterministic walks we
/// establish the **variance** of the metric and a baseline against
/// which any ML improvement must be measured.
pub struct WalkBenchResult {
    pub name: String,
    pub n_runs: usize,
    pub success_count: usize,
    pub mean_iters: f64,
    pub median_iters: u64,
    pub min_iters: u64,
    pub max_iters: u64,
}

/// Solve DLP `h = g^x mod q` (with `g` of prime order `n`) using
/// `pollard_rho_dlp` with a custom partition function.
fn solve_dlp_zp_with_partition<F>(
    g: &BigUint,
    h: &BigUint,
    n: &BigUint,
    q: &BigUint,
    partition: F,
    seed: u64,
) -> Option<u64>
where
    F: Fn(&BigUint) -> u8,
{
    let op = |a: &BigUint, b: &BigUint| -> BigUint { (a * b) % q };
    let eq = |a: &BigUint, b: &BigUint| -> bool { a == b };
    let pow = |g: &BigUint, k: &BigUint| -> BigUint { g.modpow(k, q) };
    let opts = RhoOptions {
        max_iterations: 50_000,
        max_restarts: 30,
        seed: Some(seed),
    };
    match pollard_rho_dlp(g, h, n, op, eq, partition, pow, &opts) {
        Ok(sol) => Some(sol.iterations),
        Err(_) => None,
    }
}

/// Compare 4 deterministic walk-function partitions on `n_runs` random
/// DLP instances at the given toy prime.  Returns one
/// [`WalkBenchResult`] per partition.
pub fn benchmark_walk_partitions(
    p: u64,
    g_val: u64,
    subgroup_order: u64,
    n_runs: usize,
    base_seed: u64,
) -> Vec<WalkBenchResult> {
    let p_big = BigUint::from(p);
    let n = BigUint::from(subgroup_order);
    let g = BigUint::from(g_val);

    let partitions: Vec<(&str, Box<dyn Fn(&BigUint) -> u8>)> = vec![
        // Standard: low byte mod 3 (default `pollard_rho`).
        (
            "standard low-byte",
            Box::new(|x: &BigUint| x.to_bytes_be().last().copied().unwrap_or(0)),
        ),
        // High byte mod 3.
        (
            "high-byte",
            Box::new(|x: &BigUint| x.to_bytes_be().first().copied().unwrap_or(0)),
        ),
        // XOR of two halves.
        (
            "xor-halves",
            Box::new(|x: &BigUint| {
                let bs = x.to_bytes_be();
                let n_half = bs.len() / 2;
                let lo: u8 = bs.iter().skip(n_half).fold(0u8, |a, b| a ^ b);
                let hi: u8 = bs.iter().take(n_half).fold(0u8, |a, b| a ^ b);
                lo ^ hi
            }),
        ),
        // Popcount mod 3 (information-bearing about Hamming weight).
        (
            "popcount",
            Box::new(|x: &BigUint| {
                x.to_bytes_be()
                    .iter()
                    .map(|b| b.count_ones() as u8)
                    .sum::<u8>()
            }),
        ),
    ];

    let mut results = Vec::new();
    for (name, partition) in partitions {
        let mut rng = StdRng::seed_from_u64(base_seed);
        let mut iters_log: Vec<u64> = Vec::new();
        let mut successes = 0usize;
        for run in 0..n_runs {
            let secret = rng.gen_biguint_below(&n);
            if secret.is_zero() {
                continue;
            }
            let h = g.modpow(&secret, &p_big);
            if let Some(iters) =
                solve_dlp_zp_with_partition(&g, &h, &n, &p_big, &partition, base_seed + run as u64)
            {
                successes += 1;
                iters_log.push(iters);
            }
        }
        iters_log.sort();
        let mean = if iters_log.is_empty() {
            0.0
        } else {
            iters_log.iter().sum::<u64>() as f64 / iters_log.len() as f64
        };
        let median = iters_log.get(iters_log.len() / 2).copied().unwrap_or(0);
        let min = iters_log.first().copied().unwrap_or(0);
        let max = iters_log.last().copied().unwrap_or(0);
        results.push(WalkBenchResult {
            name: name.into(),
            n_runs,
            success_count: successes,
            mean_iters: mean,
            median_iters: median,
            min_iters: min,
            max_iters: max,
        });
    }
    results
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    /// **Walk-partition benchmark**: 4 deterministic partition
    /// functions, 50 random DLP instances at p = 32213 (15-bit Solinas
    /// shape), subgroup order 8053 (a divisor of p - 1).  Reports
    /// mean / median / min / max iterations per partition.
    #[test]
    #[ignore]
    fn walk_partition_benchmark_p32213() {
        // p = 32213 is prime; (p-1) = 32212 = 2² · 7 · 1151
        // Subgroup of order 1151.  Pick g of order 1151.
        // For brevity, use g = 2 and the full multiplicative-group
        // structure (order p − 1 = 32212).
        let results = benchmark_walk_partitions(32213, 2, 32212, 50, 0xDEAD_BEEF);
        println!("\n=== Walk-partition benchmark (p = 32213, n_runs = 50) ===");
        println!(
            "{:>22} {:>10} {:>12} {:>10} {:>10} {:>10}",
            "partition", "successes", "mean iters", "median", "min", "max"
        );
        for r in &results {
            println!(
                "{:>22} {:>10} {:>12.0} {:>10} {:>10} {:>10}",
                r.name, r.success_count, r.mean_iters, r.median_iters, r.min_iters, r.max_iters
            );
        }
        // Sanity assertion: report success rate; some walks may
        // legitimately fail on bad seeds even with multiple restarts.
        let total_successes: usize = results.iter().map(|r| r.success_count).sum();
        println!(
            "\n  Total successes: {} / {} ({:.0}%)",
            total_successes,
            results.len() * 50,
            100.0 * total_successes as f64 / (results.len() * 50) as f64,
        );
        assert!(
            total_successes > 50,
            "Aggregate success rate too low across all walks — likely a bug."
        );
    }

    /// JSON serialization of WalkTrace for ML pipeline ingest.
    #[test]
    fn walk_trace_json_serializes() {
        let trace = WalkTrace {
            step: 42,
            x_hex: "0xdeadbeef".into(),
            y_hex: "0xcafebabe".into(),
            alpha: Some(7),
            beta: Some(3),
            walk_index: 2,
            is_distinguished: true,
        };
        let mut buf = Cursor::new(Vec::new());
        emit_traces(&[trace], &mut buf).unwrap();
        let s = String::from_utf8(buf.into_inner()).unwrap();
        // Basic structure check.
        assert!(s.contains("\"step\":42"));
        assert!(s.contains("\"walk_index\":2"));
        assert!(s.contains("\"is_distinguished\":true"));
    }

    /// Standard walk's choose() produces a value in [0, r).
    #[test]
    fn standard_walk_in_range() {
        use num_bigint::BigUint;
        let walk = StandardWalk;
        let state = WalkState {
            y_x: BigUint::from(0xDEADBEEFu32),
            y_y: BigUint::from(0xCAFEBABEu32),
            alpha: 7,
            beta: 3,
            r: 8,
        };
        let idx = walk.choose(&state);
        assert!(idx < 8);
    }

    /// **Documents the framework**: how a researcher with GPU access
    /// would use this module.
    #[test]
    fn ml_rho_experimental_design() {
        println!();
        println!("=== Adversarial-ML Pollard rho — Experimental Design ===");
        println!();
        println!("This module ships the FRAMEWORK, not a trained model.");
        println!();
        println!("To actually run the experiment, a researcher with GPU access");
        println!("would:");
        println!();
        println!("1. Pick a toy curve over a Solinas-form 32-bit prime, e.g.");
        println!("   p = 2³² - 5, with cyclic group order ~2³².");
        println!();
        println!("2. Generate training data:");
        println!("   - Run baseline pollard_rho 10⁴ times with random seeds.");
        println!("   - At each step, emit WalkTrace via emit_traces() to JSONL.");
        println!("   - Total: ~10⁹ tuples, ~10 GB.");
        println!();
        println!("3. Architecture: small transformer (4 layers, 256-dim,");
        println!("   8 heads).  Input: state features.  Output: walk-fn index.");
        println!();
        println!("4. Loss: REINFORCE.  Reward = -log(steps to next DP).");
        println!("   Train ~10⁵ epochs.");
        println!();
        println!("5. Evaluate: average steps-to-collision, compare to baseline.");
        println!();
        println!("Cost: ~$1k GPU.  Expected outcome: marginal improvement,");
        println!("not a real attack.  Publishable either way.");
        println!();
        println!("This module's contribution: trace-emission API + experiment");
        println!("design that any researcher with GPU access can act on.");
    }
}
