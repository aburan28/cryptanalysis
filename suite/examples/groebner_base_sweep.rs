//! Which Frobenius-invariant factor base is cheapest **to solve**, not
//! merely likeliest to yield?
//!
//! ```bash
//! cargo run --release --example groebner_base_sweep -- --out DIR
//! ```
//!
//! ## The gap this measures
//!
//! `koblitz_factor_base_search` selects a base by **expected trials**,
//!
//! ```text
//!     T(F) = (U(F) + 1 + extra) / p_m(F)
//! ```
//!
//! — relation columns over coverage — and says so in its own module
//! documentation: *"solving cost per trial is a separate axis that
//! depends on the oracle, and the report carries the standard proxies
//! … alongside so a caller can trade them off."*  The proxies are
//! `|F|^{m−1}` enumeration work and a SAT variable count.  Neither is
//! what the Gröbner oracle actually costs.
//!
//! A trial costs whether or not it succeeds, so the quantity that
//! decides collection is
//!
//! ```text
//!     C(F) = (U(F) + 1) · E[stage word XORs per target] / p_m(F)
//! ```
//!
//! with the expectation over *all* targets, refutations included.  `T`
//! is `C` with the middle factor set to one — that is, with every base
//! assumed equally hard to solve.  Whether that assumption holds is
//! measurable, and this harness measures it: same curve, same targets,
//! same oracle, one row per admissible invariant subspace.
//!
//! ## Why the choice is narrow, and at ECC2K-130 empty
//!
//! An `F_2`-subspace of `F_{2^n}` is Frobenius-stable exactly when it is
//! `ker g(σ)` for a divisor `g` of `t^n − 1` (`research/notes/index-calculus/RESEARCH_QUASI_SUBFIELD.md`
//! §3), so the candidates are the divisors, and their dimensions are the
//! sums of cyclotomic coset sizes.  At `n = 131` the order of `2` mod
//! `131` is `130`: `t^131 − 1 = (t+1)·(irreducible of degree 130)`, and
//! the only invariant subspaces are dimension `1` and `130`.  The first
//! holds two abscissae, the second is the trace hyperplane — half the
//! field.  **There is no invariant linear factor base to optimise at the
//! challenge degree**, which is why this sweep runs at the degrees where
//! the lattice is non-trivial and reports the census beside it.

use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    f4_profile, f4_profile_reset, FieldStructure, SolverEngine,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    all_factors_of_x_n_minus_1, available_subspace_dimensions,
    build_frobenius_factor_base_from_divisor, cyclotomic_cosets, groebner_decompose,
    order_of_2_mod_n, top_factor_indices, KoblitzCurve,
};
use num_bigint::BigUint;
use std::time::Instant;

struct Rung {
    a: u8,
    n: u32,
    m: usize,
    targets: u32,
}

/// Degrees whose divisor lattice offers a choice at all, with `m` set so
/// that `m·ℓ ≥ n` is reachable within the variable cap below.
const RUNGS: &[Rung] = &[
    Rung {
        a: 0,
        n: 9,
        m: 2,
        targets: 64,
    },
    Rung {
        a: 0,
        n: 9,
        m: 3,
        targets: 32,
    },
    Rung {
        a: 1,
        n: 15,
        m: 2,
        targets: 64,
    },
    Rung {
        a: 1,
        n: 17,
        m: 2,
        targets: 48,
    },
    Rung {
        a: 1,
        n: 23,
        m: 2,
        targets: 24,
    },
    Rung {
        a: 0,
        n: 31,
        m: 2,
        targets: 12,
    },
];

/// The Boolean system has `m·ℓ` unknowns for `m = 2` and `m·ℓ + (m−2)·n`
/// once the chain appears; past this the degree-3 Macaulay matrix stops
/// fitting the caps and the row would price the cap, not the base.
const MAX_VARS: usize = 34;
/// Materialising a base is charged in wall time, but a sweep that spends
/// minutes per candidate measures the enumeration, not the algebra.
const MAX_POINTS: usize = 200_000;
/// A candidate that outruns this decides fewer targets; the row then
/// reports what it decided and is marked, rather than being dropped.
const CANDIDATE_BUDGET: std::time::Duration = std::time::Duration::from_secs(400);

fn target_scalar(i: u32, seed: u64) -> BigUint {
    let mut x = seed ^ (i as u64).wrapping_mul(0x9E37_79B9_7F4A_7C15);
    x ^= x >> 33;
    x = x.wrapping_mul(0xFF51_AFD7_ED55_8CCD);
    x ^= x >> 29;
    BigUint::from(1 + x % 1_000_003)
}

/// Divisors of `x^n − 1` built from at most three irreducible factors.
///
/// The invariant subspaces are exactly the kernels of the divisors, so
/// this enumerates the candidate lattice directly.  Three factors is
/// what `n = 31` needs to reach `m·ℓ ≥ n`, where its six degree-5 cosets
/// give six distinct subspaces of the same dimension — the cleanest
/// same-`ℓ` comparison available.  At most `PER_DIMENSION` candidates of
/// any one dimension are kept, so a rich lattice does not turn the sweep
/// into an enumeration of itself.
const PER_DIMENSION: usize = 6;

fn candidate_divisors(n: u32, m: usize) -> Vec<Vec<usize>> {
    let factors = all_factors_of_x_n_minus_1(n);
    let degree = |f: u64| 63 - f.leading_zeros() as usize;
    let mut all: Vec<Vec<usize>> = Vec::new();
    for i in 0..factors.len() {
        all.push(vec![i]);
        for j in (i + 1)..factors.len() {
            all.push(vec![i, j]);
            for k in (j + 1)..factors.len() {
                all.push(vec![i, j, k]);
            }
        }
    }
    // The yield law needs `m·ℓ ≥ n` before anything decomposes, so keep
    // every base that can reach it plus one dimension below, as the
    // control that shows the law biting.
    let want = (n as usize).div_ceil(m);
    let mut kept: std::collections::BTreeMap<usize, usize> = Default::default();
    let mut out = Vec::new();
    for d in all {
        let ell: usize = d.iter().map(|&i| degree(factors[i])).sum();
        if ell + 2 < want || ell > n as usize {
            continue;
        }
        let slot = kept.entry(ell).or_default();
        if *slot >= PER_DIMENSION {
            continue;
        }
        *slot += 1;
        out.push(d);
    }
    out
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let out = args
        .windows(2)
        .find(|w| w[0] == "--out")
        .map(|w| w[1].clone());
    // A different target seed draws an independent target sample, which
    // is how the ranking below is checked rather than assumed.
    let seed: u64 = args
        .windows(2)
        .find(|w| w[0] == "--target-seed")
        .and_then(|w| w[1].parse().ok())
        .unwrap_or(0x5EED_0001);
    let only: Option<Vec<u32>> = args
        .windows(2)
        .find(|w| w[0] == "--degrees")
        .map(|w| w[1].split(',').filter_map(|x| x.parse().ok()).collect());

    println!();
    println!("=== Invariant-subspace census ===");
    println!();
    println!("| n | ord₂(n) | coset sizes | invariant dimensions 0 < ℓ < n |");
    println!("|--:|--------:|:------------|:-------------------------------|");
    let mut census = Vec::new();
    for n in [9u32, 13, 15, 17, 19, 23, 31, 41, 53, 73, 127, 131, 163] {
        let dims: Vec<u32> = available_subspace_dimensions(n)
            .into_iter()
            .filter(|d| *d > 0 && *d < n)
            .collect();
        let mut sizes: std::collections::BTreeMap<usize, usize> = Default::default();
        for c in cyclotomic_cosets(n) {
            *sizes.entry(c.len()).or_default() += 1;
        }
        let shown = if dims.len() > 12 {
            format!(
                "{:?} … {:?} ({} in all)",
                &dims[..4],
                dims.last().unwrap(),
                dims.len()
            )
        } else {
            format!("{dims:?}")
        };
        println!(
            "| {n} | {} | {} | {shown} |",
            order_of_2_mod_n(n)
                .map(|o| o.to_string())
                .unwrap_or_else(|| "—".into()),
            sizes
                .iter()
                .map(|(k, v)| format!("{k}×{v}"))
                .collect::<Vec<_>>()
                .join(", "),
        );
        census.push(serde_json::json!({
            "n": n,
            "order_of_2": order_of_2_mod_n(n),
            "invariant_dimensions": dims,
        }));
    }

    println!();
    println!("=== Cost of a relation, by factor base ===");
    println!();
    println!(
        "| curve | m | divisor | ℓ | \\|F\\| | U | coverage | ops/target | \
         T = (U+1)/p | C = T·ops/target | C / best |"
    );
    println!(
        "|:------|--:|:--------|--:|------:|--:|---------:|-----------:|\
         ------------:|-----------------:|---------:|"
    );

    let mut rows = Vec::new();
    for rung in RUNGS {
        if let Some(only) = &only {
            if !only.contains(&rung.n) {
                continue;
            }
        }
        let Some(kc) = KoblitzCurve::new(rung.a, rung.n) else {
            continue;
        };
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let g = kc.generator().clone();
        let mut scored: Vec<serde_json::Value> = Vec::new();
        // What the pipeline picks today with no factor-base recipe: the
        // first of the largest-degree factors.
        let default_divisor: Vec<usize> = top_factor_indices(&kc)
            .first()
            .map(|&i| vec![i])
            .unwrap_or_default();

        for divisor in candidate_divisors(rung.n, rung.m) {
            let Some(fb) = build_frobenius_factor_base_from_divisor(&kc, &divisor) else {
                continue;
            };
            let vars = rung.m * fb.ell as usize + rung.m.saturating_sub(2) * rung.n as usize;
            if vars > MAX_VARS || fb.points.len() > MAX_POINTS || fb.points.is_empty() {
                continue;
            }
            if !fb.m_can_decompose(&kc, rung.m) {
                // Cofactor-inadmissible: rejected before the oracle runs,
                // so it has no solve cost to measure.
                scored.push(serde_json::json!({
                    "divisor": divisor, "ell": fb.ell, "points": fb.points.len(),
                    "is_pipeline_default": divisor == default_divisor,
                    "unknowns": fb.unknowns(), "admissible": false,
                }));
                continue;
            }
            let index_of = fb.index_map();
            f4_profile_reset();
            let wall = Instant::now();
            let (mut decomposed, mut splits, mut max_degree) = (0u32, 0usize, 0u32);
            let mut decided = 0u32;
            for i in 0..rung.targets {
                if wall.elapsed() > CANDIDATE_BUDGET {
                    break;
                }
                let target = kc.mul(&g, &target_scalar(i, seed));
                let (idxs, stats) = groebner_decompose(
                    &kc,
                    &fb,
                    &index_of,
                    &st,
                    &target,
                    rung.m,
                    SolverEngine::default(),
                    20_000,
                );
                decided += 1;
                if idxs.is_some() {
                    decomposed += 1;
                }
                splits += stats.splits;
                max_degree = max_degree.max(stats.max_degree_built);
            }
            let p = f4_profile();
            let coverage = decomposed as f64 / decided.max(1) as f64;
            let ops_per_target = p.word_ops as f64 / decided.max(1) as f64;
            let unknowns = fb.unknowns();
            let (trials, cost) = if coverage > 0.0 {
                let t = (unknowns as f64 + 1.0) / coverage;
                (t, t * ops_per_target)
            } else {
                (f64::INFINITY, f64::INFINITY)
            };
            scored.push(serde_json::json!({
                "divisor": divisor, "ell": fb.ell, "points": fb.points.len(),
                "is_pipeline_default": divisor == default_divisor,
                "unknowns": unknowns, "admissible": true,
                "targets": rung.targets, "decided": decided,
                "budget_exhausted": decided < rung.targets,
                "decomposed": decomposed, "coverage": coverage,
                "word_ops": p.word_ops, "ops_per_target": ops_per_target,
                "f4_calls": p.calls, "splits": splits, "max_degree_built": max_degree,
                "expected_trials": trials, "expected_stage_ops": cost,
                "wall_ns": wall.elapsed().as_nanos(),
            }));
        }

        let best = scored
            .iter()
            .filter_map(|c| c["expected_stage_ops"].as_f64())
            .filter(|c| c.is_finite())
            .fold(f64::INFINITY, f64::min);
        let best_trials = scored
            .iter()
            .filter_map(|c| c["expected_trials"].as_f64())
            .filter(|c| c.is_finite())
            .fold(f64::INFINITY, f64::min);
        let show = |c: &serde_json::Value| -> String {
            let d: Vec<i64> = c["divisor"]
                .as_array()
                .unwrap()
                .iter()
                .map(|x| x.as_i64().unwrap())
                .collect();
            let mut s = d
                .iter()
                .map(|x| x.to_string())
                .collect::<Vec<_>>()
                .join("·")
                .to_string();
            if c["is_pipeline_default"] == serde_json::Value::Bool(true) {
                s.push_str(" ᴅ");
            }
            s
        };
        for c in &scored {
            let label = format!("`K_{}/2^{}`", rung.a, rung.n);
            if c["admissible"] == serde_json::Value::Bool(false) {
                println!(
                    "| {label} | {} | {} | {} | {} | {} | — | — | — | — | inadmissible |",
                    rung.m,
                    show(c),
                    c["ell"],
                    c["points"],
                    c["unknowns"],
                );
                continue;
            }
            let cost = c["expected_stage_ops"].as_f64().unwrap_or(f64::INFINITY);
            let trials = c["expected_trials"].as_f64().unwrap_or(f64::INFINITY);
            let mark = |is_best: bool| if is_best { " ★" } else { "" };
            println!(
                "| {label} | {} | {} | {} | {} | {} | {:.0}%{} | {:.3e} | {}{} | {}{} | {} |",
                rung.m,
                show(c),
                c["ell"],
                c["points"],
                c["unknowns"],
                100.0 * c["coverage"].as_f64().unwrap_or(0.0),
                if c["budget_exhausted"] == serde_json::Value::Bool(true) {
                    " (budget)"
                } else {
                    ""
                },
                c["ops_per_target"].as_f64().unwrap_or(0.0),
                fmt(trials),
                mark(trials <= best_trials * 1.0000001),
                fmt(cost),
                mark(cost <= best * 1.0000001),
                if cost.is_finite() && best.is_finite() {
                    format!("{:.2}×", cost / best)
                } else {
                    "—".into()
                },
            );
        }
        rows.push(serde_json::json!({
            "curve": format!("K_{}/2^{}", rung.a, rung.n),
            "a": rung.a, "n": rung.n, "m": rung.m,
            "candidates": scored,
        }));
    }

    println!();
    println!("`U` is the signed-orbit count — the relation columns.  `p` is the measured");
    println!("fraction of targets that decompose, `T` the expected trials the factor-base");
    println!("search minimises today, and `C = T · ops/target` the expected word XORs the");
    println!("stage spends to collect one determining system.  Per AGENTS.md §8 this prices");
    println!("one stage of relation collection, not an attack.");

    if let Some(dir) = out {
        std::fs::create_dir_all(&dir).expect("create output directory");
        let path = format!("{dir}/base_sweep.json");
        assert!(!std::path::Path::new(&path).exists(), "{path} exists");
        let doc = serde_json::json!({
            "harness": "examples/groebner_base_sweep.rs",
            "unit": "64-bit word XORs in the Macaulay elimination",
            "scope": "decomposition-oracle stage only; not an end-to-end ECDLP cost",
            "metric": "C = (U+1)/p * E[word XORs per target], expectation over all targets",
            "target_seed": seed,
            "census": census,
            "rungs": rows,
        });
        std::fs::write(&path, serde_json::to_string_pretty(&doc).unwrap()).unwrap();
        println!();
        println!("Wrote {path}");
    }
}

fn fmt(x: f64) -> String {
    if x.is_finite() {
        format!("{x:.3e}")
    } else {
        "∞".into()
    }
}
