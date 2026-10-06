//! Frozen benchmark for the **Gröbner stage** of the Koblitz /
//! ECC2K-130 decomposition oracle.
//!
//! ```bash
//! cargo run --release --example groebner_stage_bench -- --out DIR
//! ```
//!
//! ## What it measures, and what it does not
//!
//! The oracle asks `is R = P_1 + … + P_m with every P_i in the
//! Frobenius-invariant factor base?`, and answers it by Weil-restricting
//! the Semaev condition to a Boolean system and reducing it with
//! matrix-F4 plus splitting (`koblitz_groebner`).  This harness runs
//! exactly that stage on a frozen ladder of instances and frozen
//! targets, and reports
//!
//! - **`word_ops`** — 64-bit word XORs in the Macaulay eliminations,
//!   the repository's unit for this stage (`crossbred_bench`,
//!   `blocked_macaulay_bench` use the same one);
//! - the **phase split** of wall time inside the stage: building each
//!   Macaulay matrix, reducing it, reading the reduced rows back;
//! - the solver's own counters (reductions, infeasibility certificates,
//!   propagations, splits), which must not move;
//! - a **verdict digest** over every target's answer, so a candidate is
//!   only comparable when it decided every instance identically.
//!
//! The profile counters are process-wide and cumulative, so a scoped
//! measurement resets before the work and reads after it, with no other
//! thread solving in between; this harness decides its targets on one
//! thread.
//!
//! Per `AGENTS.md` §8 this is a **stage diagnostic**.  A gain here is
//! not an end-to-end ECDLP speedup and is not reported as one: the
//! stage is one phase of relation collection, which is one phase of the
//! attack, and the decomposition-oracle cost at `n = 131` is bounded
//! below by the counting argument in `research/notes/ecc2k130/RESEARCH_ECC2K130_DECOMPOSITION.md`
//! §5 regardless of how fast one Macaulay matrix reduces.

use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    f4_build_subprofile, f4_build_subprofile_reset, f4_layout_stats, f4_layout_stats_reset,
    f4_profile, f4_profile_reset, split_rule_default, F4Profile, FieldStructure, SolveOptions,
    SolverEngine,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base, groebner_decompose, KoblitzCurve,
};
use num_bigint::BigUint;
use std::time::Instant;

/// One frozen instance: curve `K_a / F_2^n`, factor-base divisor index,
/// summands, and how many targets to decide.
struct Instance {
    a: u8,
    n: u32,
    factor_index: usize,
    m: usize,
    targets: u32,
    /// Index of the first target scalar (`target_scalar(first + i)`).
    first: u32,
}

/// The ladder.  `K_1/2^21` and `K_1/2^23` are the instances the Koblitz
/// note measures the Gröbner oracle on at its slowest (20.6 s at
/// `n = 23` on 4 cores); the smaller rungs keep the cheap regime — where
/// per-call overhead rather than elimination dominates — in the table.
/// `n = 21` is absent because `3 | 21` leaves no Koblitz curve here.
/// `n = 19` is in the holdout ladder instead: its systems are well
/// within the size caps (72 F4 calls over two targets, no oversize) but
/// materialising its 261,745-point factor base costs 4.7 s against a
/// sub-second stage, so it would price setup rather than the stage.
#[rustfmt::skip]
const LADDER: &[Instance] = &[
    Instance { a: 0, n: 9, factor_index: 0, m: 2, targets: 40, first: 0 },
    Instance { a: 0, n: 9, factor_index: 0, m: 3, targets: 16, first: 0 },
    Instance { a: 0, n: 13, factor_index: 0, m: 2, targets: 40, first: 0 },
    Instance { a: 1, n: 15, factor_index: 0, m: 2, targets: 32, first: 0 },
    Instance { a: 1, n: 17, factor_index: 0, m: 2, targets: 32, first: 0 },
    Instance { a: 1, n: 23, factor_index: 0, m: 2, targets: 16, first: 0 },
];

/// The holdout ladder, selected with `--ladder holdout`: instances that
/// are *not* part of the frozen baseline comparison, kept for checking a
/// change against shapes it was not tuned on.  `n = 19` is the widest
/// regime the oracle reaches here — a few hundred rows against a couple
/// of thousand columns — which is where a blocked elimination is most at
/// risk of costing more than it saves.
#[rustfmt::skip]
const HOLDOUT: &[Instance] = &[
    Instance { a: 0, n: 19, factor_index: 0, m: 2, targets: 12, first: 0 },
    Instance { a: 1, n: 17, factor_index: 1, m: 2, targets: 24, first: 0 },
];

/// The chained ladder, selected with `--ladder chain`: `m ≥ 3` cells,
/// where the variables of the chain's intermediate points enter the
/// system and the split order and linear elimination of
/// `research/notes/ecc2k130/RESEARCH_CHAIN_SPLIT_ORDER.md` act.  These are
/// the cells that change was found on (its §1 lists the exploratory runs),
/// so they are its tuning set, not its evidence.
#[rustfmt::skip]
const CHAIN: &[Instance] = &[
    Instance { a: 0, n: 9, factor_index: 0, m: 3, targets: 16, first: 0 },
    Instance { a: 0, n: 13, factor_index: 0, m: 3, targets: 8, first: 0 },
    Instance { a: 0, n: 15, factor_index: 0, m: 3, targets: 8, first: 0 },
    Instance { a: 1, n: 17, factor_index: 0, m: 3, targets: 4, first: 0 },
    Instance { a: 0, n: 9, factor_index: 0, m: 4, targets: 8, first: 0 },
];

/// The chained holdout, selected with `--ladder chain-holdout`: cells no
/// arm of that change was run on before it was registered — other curves,
/// other degrees, and fresh targets on two tuning cells.  A cell whose
/// curve or factor base does not exist, or whose cofactor makes `m`
/// inadmissible, is skipped by the harness as on every ladder.
#[rustfmt::skip]
const CHAIN_HOLDOUT: &[Instance] = &[
    Instance { a: 1, n: 9, factor_index: 0, m: 3, targets: 16, first: 0 },
    Instance { a: 0, n: 11, factor_index: 0, m: 3, targets: 8, first: 0 },
    Instance { a: 1, n: 11, factor_index: 0, m: 3, targets: 8, first: 0 },
    Instance { a: 1, n: 13, factor_index: 0, m: 3, targets: 8, first: 0 },
    Instance { a: 1, n: 15, factor_index: 0, m: 3, targets: 8, first: 0 },
    Instance { a: 0, n: 17, factor_index: 0, m: 3, targets: 4, first: 0 },
    Instance { a: 1, n: 9, factor_index: 0, m: 4, targets: 8, first: 0 },
    Instance { a: 0, n: 15, factor_index: 0, m: 4, targets: 8, first: 0 },
    Instance { a: 1, n: 15, factor_index: 0, m: 4, targets: 8, first: 0 },
    Instance { a: 0, n: 13, factor_index: 0, m: 3, targets: 8, first: 1000 },
    Instance { a: 1, n: 17, factor_index: 0, m: 3, targets: 4, first: 1000 },
];

/// The supplementary holdout, selected with `--ladder chain-holdout-2`:
/// every cell of `examples/chain_ladder_screen.rs`'s grid that exists, is
/// admissible for its `m`, fits in 64 unknowns and on which no arm of the
/// change had run when it was registered (§5 of
/// `RESEARCH_CHAIN_SPLIT_ORDER.md`); the first registered holdout lost seven
/// of its eleven cells to admissibility.
#[rustfmt::skip]
const CHAIN_HOLDOUT_2: &[Instance] = &[
    Instance { a: 1, n: 11, factor_index: 0, m: 4, targets: 4, first: 0 },
    Instance { a: 0, n: 15, factor_index: 1, m: 3, targets: 8, first: 0 },
    Instance { a: 0, n: 15, factor_index: 1, m: 4, targets: 8, first: 0 },
    Instance { a: 0, n: 15, factor_index: 2, m: 3, targets: 8, first: 0 },
    Instance { a: 0, n: 15, factor_index: 2, m: 4, targets: 8, first: 0 },
    Instance { a: 1, n: 15, factor_index: 1, m: 4, targets: 8, first: 0 },
    Instance { a: 1, n: 15, factor_index: 2, m: 4, targets: 8, first: 0 },
    Instance { a: 0, n: 23, factor_index: 0, m: 3, targets: 4, first: 0 },
    Instance { a: 0, n: 23, factor_index: 1, m: 3, targets: 4, first: 0 },
];

/// The round-2 holdout, selected with `--ladder r2-holdout`
/// (`RESEARCH_SUPPORT_LOCAL_MULTIPLIERS.md` §2): the four admissible cells
/// the widened screen found that no ladder had used, and fresh targets
/// (`5000…`) on every admissible cell of the original screen.  Registered
/// before any arm ran on it.
#[rustfmt::skip]
const R2_HOLDOUT: &[Instance] = &[
    Instance { a: 0, n: 31, factor_index: 0, m: 3, targets: 8, first: 0 },
    Instance { a: 0, n: 31, factor_index: 1, m: 3, targets: 8, first: 0 },
    Instance { a: 0, n: 31, factor_index: 5, m: 3, targets: 8, first: 0 },
    Instance { a: 1, n: 29, factor_index: 0, m: 4, targets: 8, first: 0 },
    Instance { a: 0, n: 9, factor_index: 0, m: 3, targets: 16, first: 5000 },
    Instance { a: 0, n: 9, factor_index: 0, m: 4, targets: 8, first: 5000 },
    Instance { a: 1, n: 9, factor_index: 0, m: 4, targets: 8, first: 5000 },
    Instance { a: 1, n: 11, factor_index: 0, m: 4, targets: 4, first: 5000 },
    Instance { a: 0, n: 13, factor_index: 0, m: 3, targets: 8, first: 5000 },
    Instance { a: 0, n: 15, factor_index: 0, m: 4, targets: 8, first: 5000 },
    Instance { a: 0, n: 15, factor_index: 1, m: 3, targets: 8, first: 5000 },
    Instance { a: 0, n: 15, factor_index: 1, m: 4, targets: 8, first: 5000 },
    Instance { a: 0, n: 15, factor_index: 2, m: 3, targets: 8, first: 5000 },
    Instance { a: 0, n: 15, factor_index: 2, m: 4, targets: 8, first: 5000 },
    Instance { a: 1, n: 15, factor_index: 0, m: 4, targets: 8, first: 5000 },
    Instance { a: 1, n: 15, factor_index: 1, m: 4, targets: 8, first: 5000 },
    Instance { a: 1, n: 15, factor_index: 2, m: 4, targets: 8, first: 5000 },
    Instance { a: 0, n: 23, factor_index: 0, m: 3, targets: 4, first: 5000 },
    Instance { a: 0, n: 23, factor_index: 1, m: 3, targets: 4, first: 5000 },
];

/// Deterministic target scalars: a fixed multiplier sequence, so every
/// run decides the same points in the same order.
fn target_scalar(i: u32) -> BigUint {
    BigUint::from(1u64 + (i as u64).wrapping_mul(2_654_435_761) % 1_000_003)
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let out = args
        .windows(2)
        .find(|w| w[0] == "--out")
        .map(|w| w[1].clone());
    let label = args
        .windows(2)
        .find(|w| w[0] == "--label")
        .map(|w| w[1].clone())
        .unwrap_or_else(|| "unlabelled".into());

    let (ladder, ladder_name) = match args
        .windows(2)
        .find(|w| w[0] == "--ladder")
        .map(|w| w[1].as_str())
    {
        Some("holdout") => (HOLDOUT, "holdout"),
        Some("chain") => (CHAIN, "chain"),
        Some("chain-holdout") => (CHAIN_HOLDOUT, "chain-holdout"),
        Some("chain-holdout-2") => (CHAIN_HOLDOUT_2, "chain-holdout-2"),
        Some("r2-holdout") => (R2_HOLDOUT, "r2-holdout"),
        _ => (LADDER, "frozen"),
    };

    // `--rung i` runs only the ladder's `i`-th entry (0-based, counting
    // inadmissible entries too), so a profiler can price one rung.
    let only: Option<usize> = args
        .windows(2)
        .find(|w| w[0] == "--rung")
        .and_then(|w| w[1].parse().ok());

    let mut rows = Vec::new();
    println!();
    println!("=== Gröbner stage: frozen decomposition ladder ({label}) ===");
    println!();
    println!(
        "| instance | m | ℓ | targets | decomposed | word XORs | F4 calls | \
         build ms | reduce ms | read ms | wall s |"
    );
    println!(
        "|:---------|--:|--:|--------:|-----------:|----------:|---------:|\
         ---------:|----------:|--------:|-------:|"
    );

    for (position, inst) in ladder.iter().enumerate() {
        if only.is_some_and(|i| i != position) {
            continue;
        }
        let Some(kc) = KoblitzCurve::new(inst.a, inst.n) else {
            continue;
        };
        let Some(fb) = build_frobenius_factor_base(&kc, inst.factor_index) else {
            continue;
        };
        if !fb.m_can_decompose(&kc, inst.m) {
            // Cofactor-inadmissible: every oracle rejects up front and
            // the stage is never entered.  Not a measurement.
            continue;
        }
        let index_of = fb.index_map();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let g = kc.generator().clone();

        f4_profile_reset();
        f4_layout_stats_reset();
        f4_build_subprofile_reset();
        let mut verdicts: Vec<String> = Vec::new();
        let mut decomposed = 0u32;
        let mut stats_total = (0usize, 0usize, 0usize, 0usize, 0usize);
        let mut eliminated = 0usize;
        let mut exhausted = 0u32;
        let wall = Instant::now();
        for i in 0..inst.targets {
            let target = kc.mul(&g, &target_scalar(inst.first + i));
            let (idxs, stats) = groebner_decompose(
                &kc,
                &fb,
                &index_of,
                &st,
                &target,
                inst.m,
                SolverEngine::default(),
                20_000,
            );
            verdicts.push(match &idxs {
                Some(v) => {
                    decomposed += 1;
                    let mut v = v.clone();
                    v.sort_unstable();
                    format!("{i}:{v:?}")
                }
                None => format!("{i}:none{}", if stats.exhausted { "!" } else { "" }),
            });
            stats_total.0 += stats.reductions;
            stats_total.1 += stats.infeasible_branches;
            stats_total.2 += stats.propagations;
            stats_total.3 += stats.splits;
            stats_total.4 += stats.oversize;
            eliminated += stats.eliminated;
            exhausted += u32::from(stats.exhausted);
        }
        let wall_ns = wall.elapsed().as_nanos();
        let p: F4Profile = f4_profile();
        let (layout_hits, layout_misses) = f4_layout_stats();
        let (row_build_ns, matrix_pack_ns) = f4_build_subprofile();
        let digest = blake3::hash(verdicts.join("|").as_bytes())
            .to_hex()
            .to_string();

        println!(
            "| `K_{}/2^{}` | {} | {} | {} | {} | {} | {} | {:.1} | {:.1} | {:.1} | {:.2} |",
            inst.a,
            inst.n,
            inst.m,
            fb.ell,
            inst.targets,
            decomposed,
            p.word_ops,
            p.calls,
            p.build_ns as f64 / 1e6,
            p.reduce_ns as f64 / 1e6,
            p.readback_ns as f64 / 1e6,
            wall_ns as f64 / 1e9,
        );

        rows.push(serde_json::json!({
            "curve": format!("K_{}/2^{}", inst.a, inst.n),
            "a": inst.a, "n": inst.n, "m": inst.m,
            "factor_index": inst.factor_index,
            "ell": fb.ell,
            "factor_base_points": fb.points.len(),
            "targets": inst.targets,
            "decomposed": decomposed,
            "verdict_digest": digest,
            "word_ops": p.word_ops,
            "f4_calls": p.calls,
            "f4_oversize": p.oversize,
            "matrix_rows": p.rows,
            "matrix_cols": p.cols,
            "build_ns": p.build_ns,
            "reduce_ns": p.reduce_ns,
            "readback_ns": p.readback_ns,
            "rows_pruned": p.rows_pruned,
            "criterion_word_ops": p.criterion_word_ops,
            "specialise_word_ops": p.specialise_word_ops,
            "layout_hits": layout_hits,
            "layout_misses": layout_misses,
            "row_build_ns": row_build_ns,
            "matrix_pack_ns": matrix_pack_ns,
            "wall_ns": wall_ns,
            "reductions": stats_total.0,
            "infeasible_branches": stats_total.1,
            "propagations": stats_total.2,
            "splits": stats_total.3,
            "oversize": stats_total.4,
            "exhausted": exhausted,
            "eliminated": eliminated,
            "first_target": inst.first,
        }));
    }

    println!();
    println!("Unit: 64-bit word XORs in the Macaulay eliminations; wall time is the whole");
    println!("stage including building and reading back every matrix.  Per AGENTS.md §8 this");
    println!("is a solver-stage diagnostic, not an end-to-end ECDLP measurement.");

    if let Some(dir) = out {
        std::fs::create_dir_all(&dir).expect("create output directory");
        let path = format!("{dir}/stage.json");
        assert!(
            !std::path::Path::new(&path).exists(),
            "{path} exists; save each iteration in a new directory"
        );
        let doc = serde_json::json!({
            "label": label,
            "harness": "examples/groebner_stage_bench.rs",
            "unit": "64-bit word XORs in the Macaulay elimination",
            "scope": "decomposition-oracle stage only; not an end-to-end ECDLP cost",
            "threads": 1,
            "ladder": ladder_name,
            // The retained controls of RESEARCH_CHAIN_SPLIT_ORDER.md, as
            // set for this run (unset means the engine's default).
            "policy": {
                "KIC_F4_MULTIPLIERS": std::env::var("KIC_F4_MULTIPLIERS").ok(),
                "KIC_F4_DROP": std::env::var("KIC_F4_DROP").ok(),
                "KIC_LINEAR_ELIM": std::env::var("KIC_LINEAR_ELIM").ok(),
                "KIC_CHAIN_ORDER": std::env::var("KIC_CHAIN_ORDER").ok(),
            },
            "reducer": std::env::var("F4_F2_RREF").unwrap_or_else(|_| "m4ri".into()),
            // The engine actually run: `SolverEngine::default()` after the
            // retained-control overrides, so a saved run names its variant.
            "engine": format!("{:?}", SolverEngine::default().effective()),
            "split_rule": format!(
                "{:?}",
                SolveOptions { split_rule: split_rule_default(), ..SolveOptions::default() }
                    .resolve()
                    .split_rule
            ),
            "criterion": std::env::var("KIC_F4_CRITERION").unwrap_or_else(|_| "none".into()),
            "inherit_root": std::env::var("KIC_F4_INHERIT_ROOT").unwrap_or_else(|_| "ref".into()),
            "rows": rows,
        });
        std::fs::write(&path, serde_json::to_string_pretty(&doc).unwrap()).unwrap();
        println!();
        println!("Wrote {path}");
    }
}
