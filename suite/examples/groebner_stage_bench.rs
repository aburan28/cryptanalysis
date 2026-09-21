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
    f4_profile, f4_profile_reset, F4Profile, FieldStructure, SolverEngine,
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
const LADDER: &[Instance] = &[
    Instance {
        a: 0,
        n: 9,
        factor_index: 0,
        m: 2,
        targets: 40,
    },
    Instance {
        a: 0,
        n: 9,
        factor_index: 0,
        m: 3,
        targets: 16,
    },
    Instance {
        a: 0,
        n: 13,
        factor_index: 0,
        m: 2,
        targets: 40,
    },
    Instance {
        a: 1,
        n: 15,
        factor_index: 0,
        m: 2,
        targets: 32,
    },
    Instance {
        a: 1,
        n: 17,
        factor_index: 0,
        m: 2,
        targets: 32,
    },
    Instance {
        a: 1,
        n: 23,
        factor_index: 0,
        m: 2,
        targets: 16,
    },
];

/// The holdout ladder, selected with `--ladder holdout`: instances that
/// are *not* part of the frozen baseline comparison, kept for checking a
/// change against shapes it was not tuned on.  `n = 19` is the widest
/// regime the oracle reaches here — a few hundred rows against a couple
/// of thousand columns — which is where a blocked elimination is most at
/// risk of costing more than it saves.
const HOLDOUT: &[Instance] = &[
    Instance {
        a: 0,
        n: 19,
        factor_index: 0,
        m: 2,
        targets: 12,
    },
    Instance {
        a: 1,
        n: 17,
        factor_index: 1,
        m: 2,
        targets: 24,
    },
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

    let ladder = match args
        .windows(2)
        .find(|w| w[0] == "--ladder")
        .map(|w| w[1].as_str())
    {
        Some("holdout") => HOLDOUT,
        _ => LADDER,
    };

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

    for inst in ladder {
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
        let mut verdicts: Vec<String> = Vec::new();
        let mut decomposed = 0u32;
        let mut stats_total = (0usize, 0usize, 0usize, 0usize, 0usize);
        let wall = Instant::now();
        for i in 0..inst.targets {
            let target = kc.mul(&g, &target_scalar(i));
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
        }
        let wall_ns = wall.elapsed().as_nanos();
        let p: F4Profile = f4_profile();
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
            "wall_ns": wall_ns,
            "reductions": stats_total.0,
            "infeasible_branches": stats_total.1,
            "propagations": stats_total.2,
            "splits": stats_total.3,
            "oversize": stats_total.4,
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
            "ladder": if std::ptr::eq(ladder, HOLDOUT) { "holdout" } else { "frozen" },
            "reducer": std::env::var("F4_F2_RREF").unwrap_or_else(|_| "m4ri".into()),
            "rows": rows,
        });
        std::fs::write(&path, serde_json::to_string_pretty(&doc).unwrap()).unwrap();
        println!();
        println!("Wrote {path}");
    }
}
