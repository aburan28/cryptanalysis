//! **L1 of the performance plan** (`docs/ic/perf/OPTIMIZATION_PLAN.md`):
//! the point decomposition problem, `R = P_1 + … + P_m` with every `P_i`
//! in the Frobenius-invariant factor base, over a frozen ladder of
//! `m = 2 … 6`.
//!
//! ```bash
//! cargo run --release --example pdp_bench -- [--out FILE] [--tier reach|frontier|aspiration|all]
//!                                           [--budget SECONDS] [--engines groebner,wide,sat,mitm,enumerate]
//! ```
//!
//! Every cell decides the same frozen targets with each engine:
//!
//! - **planted** targets are sums of `m` factor-base points drawn from a
//!   fixed seed, so a decomposition is known to exist and a `None` is a
//!   miss (budget or incompleteness), never a correct answer;
//! - **random** targets are `[k]G` for frozen `k`, where the true answer
//!   is usually "no", and `enumerate` (when affordable) says which.
//!
//! Every returned decomposition is re-checked in the group.  A wrong one
//! aborts the run.
//!
//! Per cell and engine it reports planted hits, random decompositions,
//! mean seconds per target, and — when the system cannot be built at all
//! — why not (for instance the 64-variable monomial cap), so the
//! frontier is visible rather than silently skipped.  An engine that
//! exceeds `--budget` seconds on a cell stops there and the cell is
//! recorded as **unreached**: a budget is never negative evidence
//! (`CLAUDE.md` rule 3).
//!
//! Tiers: **reach** cells are solved today and pin regressions;
//! **frontier** cells are slow today; **aspiration** cells are the
//! `m = 5, 6` targets.  This is an oracle-stage measurement, not an
//! end-to-end ECDLP number (`AGENTS.md` §8).

use cryptanalysis_suite::binary_ecc::BinaryPoint;
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, FieldStructure, SolverEngine,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base_from_divisor, enumerate_decompose, groebner_decompose,
    invariant_factors, sat_decompose, FrobeniusFactorBase, KoblitzCurve, PairSumTable,
};
use cryptanalysis_suite::cryptanalysis::wide_groebner::{wide_groebner_decompose, MAX_WIDE_VARS};
use num_bigint::BigUint;
use rand::{rngs::StdRng, Rng, SeedableRng};
use std::time::Instant;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Tier {
    Reach,
    Frontier,
    Aspiration,
}

struct Cell {
    tier: Tier,
    n: u32,
    /// Factor-base dimension: the subspace of a divisor of `x^n − 1`
    /// whose factor degrees sum to `ell`.
    ell: u32,
    m: usize,
    planted: u32,
    random: u32,
}

const fn cell(tier: Tier, n: u32, ell: u32, m: usize, planted: u32, random: u32) -> Cell {
    Cell {
        tier,
        n,
        ell,
        m,
        planted,
        random,
    }
}

/// The frozen ladder.  Every rung is **balanced**, `m·ℓ ≈ n`: the
/// factor base is just large enough that a random target decomposes with
/// probability of order one — the regime index calculus runs in, where
/// most answers are "no" and the solver has to prove them.  (With
/// `m·ℓ ≫ n` almost every point decomposes and any oracle looks fast; an
/// earlier draft of this ladder measured exactly that.)
///
/// `vars` is the chained system's `m·ℓ + (m − 2)·n`; rungs above 64 are
/// kept so the monomial cap shows up as a status, not as a gap.
const LADDER: &[Cell] = &[
    cell(Tier::Reach, 17, 8, 2, 16, 16),
    cell(Tier::Reach, 23, 11, 2, 8, 8),
    cell(Tier::Reach, 9, 3, 3, 16, 16),
    cell(Tier::Reach, 15, 5, 3, 8, 8),
    cell(Tier::Frontier, 31, 10, 3, 2, 2),
    cell(Tier::Frontier, 39, 13, 3, 2, 2),
    cell(Tier::Frontier, 15, 4, 4, 4, 4),
    cell(Tier::Frontier, 31, 6, 4, 2, 2),
    cell(Tier::Aspiration, 15, 3, 5, 2, 2),
    cell(Tier::Aspiration, 31, 6, 5, 2, 2),
    cell(Tier::Aspiration, 7, 1, 6, 4, 4),
    cell(Tier::Aspiration, 31, 5, 6, 2, 2),
];

/// The curve and divisor for a rung: over `K_0` and `K_1`, every subset
/// of [`invariant_factors`] whose degrees sum to `ell` and whose base can
/// reach every cofactor class with `m` summands, keeping the one with the
/// **most points** (first in `(a, subset)` order on a tie, so the choice
/// is frozen).  Taking merely the first subset of the right degree can
/// pick a subspace with one curve point on it, whose "decompositions"
/// are all the same point.
fn choose_base(
    n: u32,
    ell: u32,
    m: usize,
) -> Option<(u8, KoblitzCurve, FrobeniusFactorBase, Vec<usize>)> {
    let mut best: Option<(u8, KoblitzCurve, FrobeniusFactorBase, Vec<usize>)> = None;
    for a in 0u8..=1 {
        let Some(kc) = KoblitzCurve::new(a, n) else {
            continue;
        };
        let degs: Vec<usize> = invariant_factors(&kc)
            .iter()
            .map(|f| f.degree().unwrap_or(0))
            .collect();
        let k = degs.len().min(16);
        for mask in 1u32..1 << k {
            let idx: Vec<usize> = (0..k).filter(|&i| mask >> i & 1 == 1).collect();
            if idx.iter().map(|&i| degs[i]).sum::<usize>() != ell as usize {
                continue;
            }
            let Some(fb) = build_frobenius_factor_base_from_divisor(&kc, &idx) else {
                continue;
            };
            if !fb.m_can_decompose(&kc, m) {
                continue;
            }
            if best
                .as_ref()
                .is_none_or(|b| fb.points.len() > b.2.points.len())
            {
                best = Some((a, kc.clone(), fb, idx));
            }
        }
    }
    best
}

#[derive(Default)]
struct EngineResult {
    planted_hits: u32,
    planted_done: u32,
    random_hits: u32,
    random_done: u32,
    seconds: f64,
    unreached: bool,
    verdicts: Vec<String>,
}

/// `−P` on a binary curve: `(x, x + y)`.
fn neg(p: &BinaryPoint) -> BinaryPoint {
    match p {
        BinaryPoint::Infinity => BinaryPoint::Infinity,
        BinaryPoint::Affine { x, y } => BinaryPoint::Affine {
            x: x.clone(),
            y: x.add(y),
        },
    }
}

/// Meet in the middle: the pair table answers `m ≤ 4` directly (`|F|^{m−2}`
/// lookups); above that the first `m − 4` summands are enumerated in
/// non-decreasing index order and the table finishes each remainder, for
/// `|F|^{m−2}` lookups overall.  Exact and complete: the reference any
/// algebraic oracle must beat on the same cell.
fn mitm_decompose(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    table: &PairSumTable,
    target: &BinaryPoint,
    m: usize,
    start: usize,
) -> Option<Vec<usize>> {
    if m <= 4 {
        return table.decompose(kc, fb, target, m);
    }
    for i in start..fb.points.len() {
        let rest = kc.add(target, &neg(&fb.points[i]));
        if let Some(mut tail) = mitm_decompose(kc, fb, table, &rest, m - 1, i) {
            tail.push(i);
            return Some(tail);
        }
    }
    None
}

fn verify(
    kc: &KoblitzCurve,
    points: &[BinaryPoint],
    idxs: &[usize],
    target: &BinaryPoint,
    m: usize,
) -> bool {
    if idxs.len() != m || idxs.iter().any(|&i| i >= points.len()) {
        return false;
    }
    let sum = idxs
        .iter()
        .fold(BinaryPoint::Infinity, |acc, &i| kc.add(&acc, &points[i]));
    sum == *target
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let flag = |name: &str| args.windows(2).find(|w| w[0] == name).map(|w| w[1].clone());
    let out = flag("--out");
    let budget: f64 = flag("--budget")
        .and_then(|v| v.parse().ok())
        .unwrap_or(120.0);
    let tier = flag("--tier").unwrap_or_else(|| "all".into());
    let engines: Vec<String> = flag("--engines")
        .unwrap_or_else(|| "groebner,wide,sat,mitm,enumerate".into())
        .split(',')
        .map(str::to_string)
        .collect();

    if let Some(idx) = flag("--child").and_then(|v| v.parse::<usize>().ok()) {
        // One cell, one engine, in a process the parent can kill.
        run_cells(&LADDER[idx..=idx], "all", &engines, budget, true);
        return;
    }

    println!("| tier | curve | ℓ | m | vars | eqs | engine | planted hit | random decomposed | s / target | status |");
    println!("|:--|:--|--:|--:|--:|--:|:--|--:|--:|--:|:--|");
    // Each (cell, engine) runs in a child process: a single target can
    // outlast any in-process budget check (a Macaulay matrix is not
    // interruptible), so the parent enforces the budget by killing it.
    // The child reports after every target, so a killed run still says
    // how far it got.
    let exe = std::env::current_exe().expect("own path");
    let mut rows = Vec::new();
    for (idx, c) in LADDER.iter().enumerate() {
        let wanted = match tier.as_str() {
            "reach" => c.tier == Tier::Reach,
            "frontier" => c.tier == Tier::Frontier,
            "aspiration" => c.tier == Tier::Aspiration,
            _ => true,
        };
        if !wanted {
            continue;
        }
        for engine in &engines {
            let mut child = std::process::Command::new(&exe)
                .args([
                    "--child",
                    &idx.to_string(),
                    "--engines",
                    engine,
                    "--budget",
                    &budget.to_string(),
                ])
                .stdout(std::process::Stdio::piped())
                .spawn()
                .expect("spawn child");
            let stdout = child.stdout.take().expect("piped");
            let reader = std::thread::spawn(move || {
                use std::io::BufRead;
                std::io::BufReader::new(stdout)
                    .lines()
                    .map_while(Result::ok)
                    .collect::<Vec<String>>()
            });
            // Setup (curve, factor base, pair table) is not in the
            // budget; the kill deadline allows for it.
            let deadline =
                Instant::now() + std::time::Duration::from_secs_f64(budget * 1.25 + 120.0);
            let mut killed = false;
            loop {
                if child.try_wait().expect("wait").is_some() {
                    break;
                }
                if Instant::now() > deadline {
                    let _ = child.kill();
                    let _ = child.wait();
                    killed = true;
                    break;
                }
                std::thread::sleep(std::time::Duration::from_millis(50));
            }
            let lines = reader.join().unwrap_or_default();
            let last = |tag: &str| {
                lines
                    .iter()
                    .rev()
                    .find_map(|l| l.strip_prefix(tag))
                    .and_then(|j| serde_json::from_str::<serde_json::Value>(j).ok())
            };
            let mut row = match last("FINAL ").or_else(|| last("PROGRESS ")) {
                Some(v) => v,
                None => serde_json::json!({
                    "tier": format!("{:?}", c.tier), "n": c.n, "ell": c.ell, "m": c.m,
                    "engine": engine, "status": "unreached: killed during setup or first target",
                }),
            };
            if killed {
                row["status"] = serde_json::json!("unreached: killed at the budget");
            }
            print_row(&row);
            rows.push(row);
        }
    }
    println!();
    println!("Oracle-stage measurement (AGENTS.md §8), not an end-to-end ECDLP number.");
    if let Some(path) = out {
        let doc = serde_json::json!({
            "schema_version": 1,
            "operation": "pdp_bench",
            "budget_seconds_per_engine_cell": budget,
            "engines": engines,
            "threads": rayon::current_num_threads(),
            "cells": rows,
        });
        std::fs::write(&path, serde_json::to_string_pretty(&doc).unwrap()).expect("write --out");
        println!("wrote {path}");
    }
}

fn print_row(r: &serde_json::Value) {
    let g = |k: &str| match &r[k] {
        serde_json::Value::Null => String::new(),
        serde_json::Value::String(s) => s.clone(),
        serde_json::Value::Number(x) => {
            if let Some(f) = x.as_f64().filter(|_| x.is_f64()) {
                format!("{f:.4}")
            } else {
                x.to_string()
            }
        }
        v => v.to_string(),
    };
    let frac = |a: &str, b: &str| {
        if r[b].is_null() {
            String::new()
        } else {
            format!("{}/{}", g(a), g(b))
        }
    };
    println!(
        "| {} | `{}` | {} | {} | {} | {} | {} | {} | {} | {} | {} |",
        g("tier"),
        g("curve"),
        g("ell"),
        g("m"),
        g("vars"),
        g("equations"),
        g("engine"),
        frac("planted_hits", "planted_done"),
        frac("random_hits", "random_done"),
        g("seconds_per_target"),
        g("status")
    );
}

fn report(row: &serde_json::Value, emit: bool, tag: &str) {
    if emit {
        println!("{tag}{row}");
    } else {
        print_row(row);
    }
}

/// Run `cells` in this process; with `emit`, print a `PROGRESS` JSON line
/// after every target and a `FINAL` one per engine, for the parent.
fn run_cells(cells: &[Cell], tier: &str, engines: &[String], budget: f64, emit: bool) {
    let mut rows: Vec<serde_json::Value> = Vec::new();
    for c in cells {
        let wanted = match tier {
            "reach" => c.tier == Tier::Reach,
            "frontier" => c.tier == Tier::Frontier,
            "aspiration" => c.tier == Tier::Aspiration,
            _ => true,
        };
        if !wanted {
            continue;
        }
        let found = choose_base(c.n, c.ell, c.m);
        let Some((a, kc, fb, divisor)) = found else {
            for engine in engines {
                let row = serde_json::json!({
                    "tier": format!("{:?}", c.tier), "curve": format!("2^{}", c.n), "n": c.n,
                    "ell": c.ell, "m": c.m, "engine": engine,
                    "status": "no admissible curve and divisor",
                });
                report(&row, emit, "FINAL ");
                rows.push(row);
            }
            continue;
        };
        let fb: FrobeniusFactorBase = fb;
        let curve = format!("K_{a}/2^{}", c.n);
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let index_of = fb.index_map();
        // System size, from the builder itself, for one target abscissa.
        let probe_x = match kc.mul(kc.generator(), &BigUint::from(12345u32)) {
            BinaryPoint::Affine { x, .. } => x,
            BinaryPoint::Infinity => unreachable!("generator has large order"),
        };
        let (vars, eqs) =
            match build_decomposition_system(&fb.subspace_basis, &probe_x, &kc.curve.b, c.m, &st) {
                Some(sys) => (Some(sys.n_vars), Some(sys.equations.len())),
                None => (None, None),
            };

        // Frozen targets.
        let mut rng = StdRng::seed_from_u64(0x5044_5042 ^ (c.n as u64) << 8 ^ c.m as u64);
        let mut targets: Vec<(bool, BinaryPoint)> = Vec::new();
        for _ in 0..c.planted {
            let t = (0..c.m).fold(BinaryPoint::Infinity, |acc, _| {
                kc.add(&acc, &fb.points[rng.gen_range(0..fb.points.len())])
            });
            targets.push((true, t));
        }
        for _ in 0..c.random {
            let k = BigUint::from(rng.gen_range(1u64..u64::MAX));
            targets.push((false, kc.mul(kc.generator(), &k)));
        }

        let enum_cost = (fb.points.len() as f64).powi(c.m as i32 - 1);
        let mitm_cost = (fb.points.len() as f64).powi(c.m as i32 - 2);
        let mut table: Option<(PairSumTable, f64)> = None;
        for engine in engines {
            if engine == "enumerate" && enum_cost > 2e7 {
                continue;
            }
            if engine == "mitm" {
                if mitm_cost > 1e9 {
                    continue;
                }
                if table.is_none() {
                    let t0 = Instant::now();
                    let Some(t) = PairSumTable::build(&kc, &fb) else {
                        continue;
                    };
                    table = Some((t, t0.elapsed().as_secs_f64()));
                }
            }
            let chained_vars = c.m as u32 * fb.ell + (c.m as u32 - 2) * c.n;
            // Past MAX_WIDE_VARS the wide engine recurses on a chain
            // suffix; it needs at least one link of ℓ + n unknowns to fit.
            if engine == "wide" && (fb.ell + c.n) as usize > MAX_WIDE_VARS {
                let row = serde_json::json!({
                    "tier": format!("{:?}", c.tier), "curve": curve, "n": c.n, "ell": fb.ell,
                    "m": c.m, "vars": chained_vars, "engine": engine,
                    "status": format!("not buildable: one link needs {} variables > {MAX_WIDE_VARS}", fb.ell + c.n),
                });
                report(&row, emit, "FINAL ");
                rows.push(row);
                continue;
            }
            if !matches!(engine.as_str(), "enumerate" | "mitm" | "wide") && vars.is_none() {
                let chained = c.m as u32 * fb.ell + (c.m as u32 - 2) * c.n;
                let row = serde_json::json!({
                    "tier": format!("{:?}", c.tier), "curve": curve, "n": c.n, "ell": fb.ell,
                    "m": c.m, "vars": chained, "engine": engine,
                    "status": format!("system not buildable: {chained} variables > 64-bit monomials"),
                });
                report(&row, emit, "FINAL ");
                rows.push(row);
                continue;
            }
            let mut r = EngineResult::default();
            let started = Instant::now();
            for (i, (planted, target)) in targets.iter().enumerate() {
                if started.elapsed().as_secs_f64() > budget {
                    r.unreached = true;
                    break;
                }
                if *target == BinaryPoint::Infinity {
                    continue;
                }
                let found = match engine.as_str() {
                    "groebner" => {
                        groebner_decompose(
                            &kc,
                            &fb,
                            &index_of,
                            &st,
                            target,
                            c.m,
                            SolverEngine::default(),
                            20_000,
                        )
                        .0
                    }
                    "sat" => sat_decompose(&kc, &fb, &index_of, &st, target, c.m, 64, Some(2)).0,
                    "enumerate" => enumerate_decompose(&kc, &fb, &index_of, target, c.m),
                    "wide" => {
                        wide_groebner_decompose(&kc, &fb, &index_of, &st, target, c.m, 1 << 22).0
                    }
                    "mitm" => {
                        let (t, _) = table.as_ref().expect("built above");
                        mitm_decompose(&kc, &fb, t, target, c.m, 0)
                    }
                    other => panic!("unknown engine {other}"),
                };
                if let Some(idxs) = &found {
                    if !verify(&kc, &fb.points, idxs, target, c.m) {
                        eprintln!(
                            "{curve} m={} {engine}: WRONG decomposition for target {i}",
                            c.m
                        );
                        std::process::exit(1);
                    }
                }
                let hit = found.is_some();
                if *planted {
                    r.planted_done += 1;
                    r.planted_hits += u32::from(hit);
                } else {
                    r.random_done += 1;
                    r.random_hits += u32::from(hit);
                }
                r.verdicts.push(format!("{i}:{}", u8::from(hit)));
                if emit {
                    let elapsed = started.elapsed().as_secs_f64();
                    let done = r.planted_done + r.random_done;
                    println!(
                        "PROGRESS {}",
                        serde_json::json!({
                            "tier": format!("{:?}", c.tier), "curve": curve, "n": c.n,
                            "ell": fb.ell, "factor_base_points": fb.points.len(), "m": c.m,
                            "vars": vars, "equations": eqs, "engine": engine,
                            "planted_done": r.planted_done, "planted_hits": r.planted_hits,
                            "random_done": r.random_done, "random_hits": r.random_hits,
                            "seconds": elapsed, "seconds_per_target": elapsed / done as f64,
                            "status": "partial",
                        })
                    );
                }
            }
            r.seconds = started.elapsed().as_secs_f64();
            let done = r.planted_done + r.random_done;
            let per = if done > 0 {
                r.seconds / done as f64
            } else {
                f64::NAN
            };
            let row = serde_json::json!({
                "tier": format!("{:?}", c.tier), "curve": curve, "a": a, "n": c.n,
                "divisor": divisor, "ell": fb.ell, "factor_base_points": fb.points.len(),
                "m": c.m, "vars": vars.or(Some(chained_vars as usize)), "equations": eqs, "engine": engine,
                "planted": c.planted, "random": c.random,
                "planted_done": r.planted_done, "planted_hits": r.planted_hits,
                "random_done": r.random_done, "random_hits": r.random_hits,
                "seconds": r.seconds, "seconds_per_target": per,
                "status": if r.unreached {
                    format!("unreached: budget {budget:.0} s after {done} targets")
                } else {
                    "complete".to_string()
                },
                "setup_seconds": if engine == "mitm" { table.as_ref().map(|t| t.1) } else { None },
                "verdict_digest": blake3::hash(r.verdicts.join("|").as_bytes()).to_hex().to_string(),
            });
            report(&row, emit, "FINAL ");
            rows.push(row);
        }
    }
    let _ = rows;
}
