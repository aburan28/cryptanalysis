//! Probe: does specialising the parent's reduced Macaulay basis cost less
//! than reducing the child's matrix from scratch, on the real node systems
//! of the Koblitz decomposition oracle?
//!
//! ```bash
//! cargo run --release --example inherited_f4_probe -- [a] [n] [targets] [degree]
//! ```
//!
//! Runs the production oracle on frozen targets with `KIC_F4_NODE_DUMP`
//! set, so every system the splitting solver reduces is captured; then,
//! for each captured node, reduces its degree-`D` matrix from scratch,
//! specialises the result on the lowest occurring variable both ways, and
//! compares the inherited child's cost with a from-scratch reduction of the
//! child's matrix.  Every child's decisive rows are cross-checked between
//! the two paths.  Unit: 64-bit word operations, the specialisation's
//! reads and writes included.  Stage diagnostic only (AGENTS.md §8).

use cryptanalysis_suite::cryptanalysis::inherited_f4::{substitute, ReducedBasis};
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    f4_profile, f4_profile_reset, split_rule_default, FieldStructure, SolveOptions, SolverEngine,
    SplitRule,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base, groebner_decompose, KoblitzCurve,
};
use cryptanalysis_suite::cryptanalysis::pq_groebner_f2::F2BoolPoly;
use num_bigint::BigUint;
use std::io::BufRead;

fn target_scalar(i: u32) -> BigUint {
    BigUint::from(1u64 + (i as u64).wrapping_mul(2_654_435_761) % 1_000_003)
}

fn canonical(mut rows: Vec<F2BoolPoly>) -> Vec<String> {
    rows.retain(|p| !p.is_zero());
    let mut out: Vec<String> = rows.iter().map(|p| format!("{:?}", p.terms)).collect();
    out.sort();
    out
}

/// What the solver does with decisive rows: refute on `1`, otherwise
/// propagate the forced variables.  The from-scratch step multiplies by
/// the assigned variable too, so once `1` is in its row space `x_v·1 = x_v`
/// joins its tail; the solver never reads past the `1`.
fn solver_view(rows: Vec<F2BoolPoly>) -> Vec<String> {
    if rows
        .iter()
        .any(|p| p.terms.len() == 1 && p.terms[0].mask == 0)
    {
        vec!["refuted".into()]
    } else {
        canonical(rows)
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let a: u8 = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(1);
    let n: u32 = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(17);
    let targets: u32 = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(8);
    let degree: u32 = args.get(4).and_then(|s| s.parse().ok()).unwrap_or(3);
    let m: usize = args.get(5).and_then(|s| s.parse().ok()).unwrap_or(2);

    let dump = format!(
        "/tmp/inherited_f4_probe_{}_{}_{}.jsonl",
        a,
        n,
        std::process::id()
    );
    let _ = std::fs::remove_file(&dump);
    std::env::set_var("KIC_F4_NODE_DUMP", &dump);

    let kc = KoblitzCurve::new(a, n).expect("Koblitz curve");
    let fb = build_frobenius_factor_base(&kc, 0).expect("factor base");
    let index_of = fb.index_map();
    let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
    let g = kc.generator().clone();
    f4_profile_reset();
    let solve_started = std::time::Instant::now();
    let mut solve_stats = (0usize, 0usize, 0usize, 0usize);
    for i in 0..targets {
        let target = kc.mul(&g, &target_scalar(i));
        let (_, stats) = groebner_decompose(
            &kc,
            &fb,
            &index_of,
            &st,
            &target,
            m,
            SolverEngine::default(),
            20_000,
        );
        solve_stats.0 += stats.reductions;
        solve_stats.1 += stats.infeasible_branches;
        solve_stats.2 += stats.propagations;
        solve_stats.3 += stats.splits;
    }
    let solve_wall = solve_started.elapsed();
    let profile = f4_profile();
    std::env::remove_var("KIC_F4_NODE_DUMP");
    println!();
    println!(
        "=== whole solve, engine {:?}: {} reductions, {} refutations, {} propagations, {} splits, {:.2} s ===",
        SolverEngine::default().effective(),
        solve_stats.0,
        solve_stats.1,
        solve_stats.2,
        solve_stats.3,
        solve_wall.as_secs_f64()
    );
    println!(
        "F4 calls {} · word ops {} (specialisation {}) · rows {} · cols {} · build {:.0} ms · reduce {:.0} ms · readback {:.0} ms",
        profile.calls,
        profile.word_ops,
        profile.specialise_word_ops,
        profile.rows,
        profile.cols,
        profile.build_ns as f64 / 1e6,
        profile.reduce_ns as f64 / 1e6,
        profile.readback_ns as f64 / 1e6,
    );

    let file = std::fs::File::open(&dump).expect("dump written");
    let mut systems: Vec<(Vec<F2BoolPoly>, usize)> = Vec::new();
    for line in std::io::BufReader::new(file).lines() {
        let line = line.unwrap();
        let doc: serde_json::Value = serde_json::from_str(&line).unwrap();
        let n_vars = doc["n_vars"].as_u64().unwrap() as usize;
        let system: Vec<F2BoolPoly> = serde_json::from_value(doc["system"].clone()).unwrap();
        systems.push((system, n_vars));
    }
    let _ = std::fs::remove_file(&dump);

    let mut nodes = 0u64;
    let mut scratch_parent = 0u64;
    let mut scratch_child = 0u64;
    let mut inherited_child = 0u64;
    let mut inherited_reduce = 0u64;
    let mut inherited_specialise = 0u64;
    let mut displaced = 0u64;
    let mut ranks = 0u64;
    let mut completion = 0u64;
    let mut mismatches = 0u64;
    let mut raw_mismatches = 0u64;
    let mut children = 0u64;
    let mut wall_scratch = 0u128;
    let mut wall_inherit = 0u128;

    // Specialise on the variable the production solver would split on:
    // the smallest free variable under `HighestFree`, the lowest-indexed
    // one under the historical rule.
    let rule = SolveOptions {
        split_rule: split_rule_default(),
        ..SolveOptions::default()
    }
    .resolve()
    .split_rule;
    println!("split rule for the probe's children: {rule:?}");
    for (system, n_vars) in &systems {
        let occurring = system
            .iter()
            .flat_map(|p| p.terms.iter())
            .fold(0u64, |a, t| a | t.mask);
        if occurring == 0 {
            continue;
        }
        let v = match rule {
            SplitRule::HighestFree => 63 - occurring.leading_zeros(),
            _ => occurring.trailing_zeros(),
        };
        let Some((root, root_cost)) = ReducedBasis::from_system(system, *n_vars, degree) else {
            continue;
        };
        nodes += 1;
        scratch_parent += root_cost.word_ops();
        ranks += root.rank() as u64;
        for value in [false, true] {
            let child_system: Vec<F2BoolPoly> = system
                .iter()
                .map(|p| substitute(p, v, value))
                .filter(|p| !p.is_zero())
                .collect();
            if child_system
                .iter()
                .any(|p| p.terms.len() == 1 && p.terms[0].mask == 0)
            {
                continue; // the solver refutes before reducing
            }
            let t0 = std::time::Instant::now();
            let Some((mut scratch, mut scratch_cost)) =
                ReducedBasis::from_system(&child_system, *n_vars, degree)
            else {
                continue;
            };
            let scratch_rows = scratch.decisive_rows(&mut scratch_cost);
            wall_scratch += t0.elapsed().as_nanos();

            let t1 = std::time::Instant::now();
            let (mut child, mut cost) = root.specialise(v, value);
            let child_rows = child.decisive_rows(&mut cost);
            wall_inherit += t1.elapsed().as_nanos();

            scratch_child += scratch_cost.word_ops();
            inherited_child += cost.word_ops();
            inherited_reduce += cost.reduce_word_ops;
            inherited_specialise += cost.specialise_word_ops;
            displaced += cost.displaced_rows;
            completion += cost.completion_rows;
            children += 1;
            if canonical(scratch_rows.clone()) != canonical(child_rows.clone()) {
                raw_mismatches += 1;
            }
            if solver_view(scratch_rows) != solver_view(child_rows) {
                mismatches += 1;
            }
        }
    }

    let per = |x: u64| x as f64 / nodes.max(1) as f64;
    println!();
    println!(
        "=== inherited F4 probe: K_{a}/2^{n}, m = {m}, {targets} targets, degree {degree} ==="
    );
    println!(
        "node systems captured: {} (reduced: {nodes})",
        systems.len()
    );
    println!("mean rank per node: {:.1}", per(ranks));
    println!();
    println!("| quantity | total word ops | per node |");
    println!("|:--|--:|--:|");
    println!(
        "| parent from scratch | {scratch_parent} | {:.0} |",
        per(scratch_parent)
    );
    println!(
        "| children from scratch (both values) | {scratch_child} | {:.0} |",
        per(scratch_child)
    );
    println!(
        "| children inherited (both values) | {inherited_child} | {:.0} |",
        per(inherited_child)
    );
    println!(
        "|   of which re-reduction XORs | {inherited_reduce} | {:.0} |",
        per(inherited_reduce)
    );
    println!(
        "|   of which specialisation reads+writes | {inherited_specialise} | {:.0} |",
        per(inherited_specialise)
    );
    println!(
        "| displaced rows (both children) | {displaced} | {:.1} |",
        per(displaced)
    );
    println!(
        "| completion rows (both children) | {completion} | {:.2} |",
        per(completion)
    );
    println!();
    println!(
        "ratio from-scratch / inherited (children): {:.2}×",
        scratch_child as f64 / inherited_child.max(1) as f64
    );
    println!(
        "wall from-scratch / inherited (children): {:.2}×",
        wall_scratch as f64 / wall_inherit.max(1) as f64
    );
    println!(
        "children compared: {children}; solver-view mismatches: {mismatches}; \
         raw decisive-row differences (refuted nodes where the from-scratch tail also holds x_v·1): {raw_mismatches}"
    );
    println!(
        "{}",
        serde_json::json!({
            "curve": format!("K_{a}/2^{n}"), "m": m, "targets": targets, "degree": degree,
            "nodes": nodes, "children": children, "mean_rank": per(ranks),
            "raw_decisive_row_differences": raw_mismatches,
            "scratch_parent_word_ops": scratch_parent,
            "scratch_child_word_ops": scratch_child,
            "inherited_child_word_ops": inherited_child,
            "inherited_reduce_word_ops": inherited_reduce,
            "inherited_specialise_word_ops": inherited_specialise,
            "displaced_rows": displaced, "completion_rows": completion,
            "mismatches": mismatches,
            "wall_scratch_ns": wall_scratch, "wall_inherit_ns": wall_inherit,
        })
    );
}
