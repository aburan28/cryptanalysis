//! **The cost distribution of index calculus across a binary Koblitz
//! isogeny class.**
//!
//! Enumerate the isogeny class of `K₀ / F_{2^n}`, run a complete
//! Gröbner-based index calculus on every member with a brute-forced DLP as
//! ground truth, and report the distribution of Gröbner solve time, relation
//! yield, and observed first fall degree across the class.
//!
//! *Flat* confirms the folklore that the class is cost-homogeneous — at this
//! size, on this instrument, over these members.  *Spread* says a structural
//! property is present, and naming it is the next experiment, not this one's
//! conclusion.
//!
//! Three parts, in the order the argument needs them:
//!
//! 1. **Reach** — what it would take to name a class member at each degree.
//!    This is where the 30–40-bit sizes are declined, with a reason: the
//!    class is small (`2^12.8` at `n = 31`), but the only isogeny degrees
//!    that move are the prime factors of the conductor of `Z[π]`, and this
//!    repository tabulates `Φ_ℓ` for `ℓ ∈ {2, 3}` only and implements no
//!    kernel polynomial.  The fallback — an exhaustive trace scan — is
//!    `O(4^n)`, which is `2^62` at `n = 31`.
//! 2. **Census** — the class enumerated exactly at the degrees where the
//!    scan is affordable, cross-validated against `Σ_{f | c} h(O_f)` from
//!    the CM side.  Two independent routes to one number.
//! 3. **Sweep** — the full measurement on every member, and the verdict.
//!
//! Run: `cargo run --release --example koblitz_isogeny_cost_sweep [n ...]`
//! Snapshot → `experiments/koblitz_isogeny_cost_sweep.json`

use cryptanalysis_suite::cryptanalysis::koblitz_isogeny_cost::*;
use std::collections::BTreeMap;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

/// Degrees the reach table reports on.  `13..=23` are the prime degrees the
/// scan can afford; `29..=41` are the 30–40-bit sizes the experiment was
/// asked for, reported with the reason they are declined.
const REACH_DEGREES: &[u32] = &[13, 17, 19, 23, 29, 31, 37, 41];

/// Degrees the sweep actually runs, unless overridden on the command line.
const DEFAULT_SWEEP_DEGREES: &[u32] = &[13, 17];

/// Subspace dimension per degree.  `ℓ` fixes the factor base at `2^ℓ`
/// abscissae, so it fixes both the unknown count and the decomposition
/// probability; it must be the same for every member of one class or the
/// distribution compares different experiments.
fn subspace_dimension(n: u32) -> u32 {
    match n {
        0..=13 => 5,
        14..=19 => 5,
        _ => 6,
    }
}

fn main() {
    let args: Vec<u32> = std::env::args()
        .skip(1)
        .filter_map(|s| s.parse::<u32>().ok())
        .collect();
    let sweep_degrees: Vec<u32> = if args.is_empty() {
        DEFAULT_SWEEP_DEGREES.to_vec()
    } else {
        args
    };

    println!("════════════════════════════════════════════════════════════════");
    println!("Index-calculus cost distribution across a binary Koblitz isogeny class");
    println!("════════════════════════════════════════════════════════════════");
    println!("K_a: y² + xy = x³ + a₆ over F_2^n, n prime; the class is every a₆");
    println!("whose curve has exactly #E(K₀) points, so a₆ names the vertex.");

    // ── Part 1: reach ───────────────────────────────────────────────
    println!("\n── Part 1: what it takes to name a class member ──");
    println!(
        "\n   {:>4} {:>16} {:>12} {:>10} {:>22} {:>8} {:>10}",
        "n", "#E", "class size", "log2", "isogeny degrees ℓ | c", "Φ_ℓ?", "scan log2"
    );
    let mut reach_rows = Vec::new();
    for &n in REACH_DEGREES {
        let r = class_reach_report(n);
        println!(
            "   {:>4} {:>16} {:>12} {:>10} {:>22} {:>8} {:>10}",
            n,
            r.order.to_string(),
            r.class_size.to_string(),
            format!("2^{:.2}", r.log2_class_size),
            r.nontrivial_degrees
                .iter()
                .map(|d| d.to_string())
                .collect::<Vec<_>>()
                .join(","),
            if r.modular_polynomial_available {
                "yes"
            } else {
                "no"
            },
            format!("2^{:.0}", r.log2_exhaustive_scan),
        );
        reach_rows.push(r);
    }
    println!("\n   'scan log2' is the O(4^n) exhaustive trace scan, the only route to a");
    println!("   named vertex when no tabulated Φ_ℓ divides the conductor. Declined:");
    for r in &reach_rows {
        if let Some(why) = &r.blocked_because {
            println!("     n={:<3} {why}", r.n);
        }
    }
    println!("\n   Note the shape of the barrier: at n = 31 the class has only 2^12.81");
    println!("   vertices — it is not too big to enumerate, it is unnameable, because");
    println!("   every edge has prime degree 7193 and nothing here can walk one.");

    // ── Parts 2 and 3: census and sweep ─────────────────────────────
    let mut sweeps = Vec::new();
    for &n in &sweep_degrees {
        let Some(irr) = field_for(n) else {
            println!("\n   n={n}: no sparse irreducible available; skipped.");
            continue;
        };
        let l = subspace_dimension(n);
        let Some((a2, r, h)) = preferred_family(n) else {
            println!("\n   n={n}: neither family has a usable prime subgroup; skipped.");
            continue;
        };

        println!("\n════════════════════════════════════════════════════════════════");
        println!("── Part 2: the class at n = {n}, enumerated exactly ──");
        println!(
            "   family a₂ = {a2} (chosen for its subgroup: r = {r}, {} bits, cofactor {h})",
            64 - r.leading_zeros()
        );
        let t0 = Instant::now();
        let census = enumerate_class_exact(n, &irr, a2);
        let scan_s = t0.elapsed().as_secs_f64();
        println!(
            "   scanned {} curves in {scan_s:.1}s: {} in the class, {} on the twist",
            census.scanned,
            census.members.len(),
            census.twist_members
        );
        println!(
            "   #E = {}, twist #E = {}",
            census.target_order, census.twist_order
        );
        println!(
            "   CM prediction Σ_(f|c) h(O_f) = {} → {}",
            census.predicted_class_size,
            if census.agrees_with_cm {
                "AGREES with the scan"
            } else {
                "DISAGREES with the scan — one of the two is wrong"
            }
        );
        if !census.agrees_with_cm {
            println!("   The sweep below is reported anyway, but its class membership is");
            println!("   not established, and no flatness claim rests on it.");
        }
        println!(
            "   Koblitz curve a₆ = 1 in the class: {}",
            census.members.contains(&1)
        );

        println!("\n── Part 3: index calculus on every member (ℓ = {l}, m = 2, a₂ = {a2}) ──");
        let opts = IcCostOptions {
            l,
            m: 2,
            ffd_targets: 12,
            ffd_d_max: 6,
            max_trials: 60_000,
            ..Default::default()
        };
        let t1 = Instant::now();
        let (rows, summary) = sweep_class(n, &irr, a2, &census.members, &opts);
        let sweep_s = t1.elapsed().as_secs_f64();
        println!(
            "   measured {} of {} members in {sweep_s:.1}s ({} skipped)",
            summary.measured,
            census.members.len(),
            summary.skipped
        );
        if summary.skipped > 0 {
            let mut why: BTreeMap<String, usize> = BTreeMap::new();
            for a6 in &census.members {
                if let Err(reason) = diagnose_member(n, &irr, a2, *a6, opts.seed) {
                    *why.entry(format!("{reason:?}")).or_insert(0) += 1;
                }
            }
            for (reason, count) in &why {
                println!("     {count} skipped: {reason}");
            }
        }
        println!(
            "   verification failures: {}   inconsistent relation rows: {}",
            summary.verification_failures, summary.inconsistent_rows
        );
        println!(
            "   transported instance: d = {} handed to every member; {} of {} recovered it → {}",
            summary
                .transported_secret
                .map(|d| d.to_string())
                .unwrap_or_else(|| "-".into()),
            summary.members_recovering_secret,
            summary.measured,
            if summary.all_recovered_transported_secret {
                "THE WHOLE CLASS SOLVED THE SAME DLP"
            } else {
                "MEMBERS DISAGREE — not a class measurement"
            }
        );

        // Per-member table, truncated but always showing the extremes and
        // the Koblitz curve itself — the baseline the folklore is about.
        let mut sorted: Vec<&IcCostRow> = rows.iter().collect();
        sorted.sort_by(|a, b| {
            a.reductions_per_call()
                .unwrap_or(f64::INFINITY)
                .partial_cmp(&b.reductions_per_call().unwrap_or(f64::INFINITY))
                .unwrap()
        });
        println!(
            "\n   {:>8} {:>8} {:>6} {:>8} {:>10} {:>11} {:>9} {:>8} {:>6}",
            "a₆", "unknowns", "probes", "rels", "yield", "reductions", "µs/call", "FFD", "ok"
        );
        let show: Vec<&&IcCostRow> = if sorted.len() <= 12 {
            sorted.iter().collect()
        } else {
            sorted
                .iter()
                .take(5)
                .chain(sorted.iter().skip(sorted.len() - 5))
                .collect()
        };
        let mut shown: Vec<u64> = show.iter().map(|r| r.a6).collect();
        for r in show {
            print_row(r);
        }
        if let Some(k) = rows.iter().find(|r| r.is_koblitz) {
            if !shown.contains(&k.a6) {
                println!("   {:-^80}", " the Koblitz curve ");
                print_row(k);
                shown.push(k.a6);
            }
        }

        println!(
            "\n   reductions/call : min {:.3}  max {:.3}  mean {:.3}  cv {:.4}  max/min {:.3}",
            summary.reductions_per_call.min,
            summary.reductions_per_call.max,
            summary.reductions_per_call.mean,
            summary.reductions_per_call.cv(),
            summary.reductions_per_call.ratio()
        );
        println!(
            "   µs/call         : min {:.1}  max {:.1}  mean {:.1}  cv {:.4}",
            summary.ns_per_call.min / 1000.0,
            summary.ns_per_call.max / 1000.0,
            summary.ns_per_call.mean / 1000.0,
            summary.ns_per_call.cv()
        );
        println!(
            "   relations/probe : min {:.5}  max {:.5}  mean {:.5}  cv {:.4}",
            summary.yield_per_probe.min,
            summary.yield_per_probe.max,
            summary.yield_per_probe.mean,
            summary.yield_per_probe.cv()
        );
        println!(
            "   normalised yield: min {:.4}  max {:.4}  mean {:.4}  cv {:.4}   (yield ÷ |F|²/2r)",
            summary.normalised_yield.min,
            summary.normalised_yield.max,
            summary.normalised_yield.mean,
            summary.normalised_yield.cv()
        );
        println!(
            "   yield variance  : observed {:.3e}  sampling {:.3e}  ratio {:.2}  [gate {YIELD_VARIANCE_GATE}]",
            summary.yield_per_probe.stddev.powi(2),
            summary.yield_sampling_variance,
            summary.yield_variance_ratio
        );
        println!(
            "   after ÷|F|²/2r  : variance ratio {:.2}  [gate {YIELD_VARIANCE_GATE}] — a residual below the gate is the estimator, not a second effect",
            summary.normalised_variance_ratio
        );
        println!(
            "   |F| (unknowns)  : min {:.0}  max {:.0}  mean {:.1}  cv {:.4}",
            summary.unknowns.min,
            summary.unknowns.max,
            summary.unknowns.mean,
            summary.unknowns.cv()
        );
        println!(
            "   pooled first fall {:?}   modal FFD per member {:?}",
            summary.pooled_first_fall, summary.first_fall_modes
        );
        println!("   pooled D*         {:?}", summary.pooled_d_star);
        if let (Some(k), Some(ratio)) = (
            summary.koblitz_reductions_per_call,
            summary.best_ratio_to_koblitz,
        ) {
            println!(
                "   Koblitz curve {k:.3} reductions/call; cheapest member is {ratio:.3}× that"
            );
        }
        println!("\n   ── verdict at n = {n} ──");
        println!(
            "      algebraic (reductions/call, first fall): {}   [flat iff cv < {FLATNESS_CV} and one modal FFD]",
            summary.verdict()
        );
        println!(
            "      combinatorial (relation yield):          {}",
            summary.yield_verdict()
        );

        sweeps.push((n, l, a2, census, rows, summary, scan_s, sweep_s));
    }

    write_json(&reach_rows, &sweeps);
}

fn print_row(r: &IcCostRow) {
    println!(
        "   {:>8} {:>8} {:>6} {:>8} {:>10.5} {:>11.3} {:>9.1} {:>8} {:>6}{}",
        r.a6,
        r.unknowns,
        r.trials,
        r.relations,
        r.yield_per_probe().unwrap_or(0.0),
        r.reductions_per_call().unwrap_or(0.0),
        r.ns_per_call().unwrap_or(0.0) / 1000.0,
        r.modal_first_fall()
            .map(|(d, c)| format!("{d} ({c})"))
            .unwrap_or_else(|| "-".into()),
        if r.verified { "yes" } else { "NO" },
        if r.is_koblitz { "  ← K₀" } else { "" }
    );
}

fn write_json(
    reach: &[ClassReachReport],
    sweeps: &[(
        u32,
        u32,
        u8,
        ClassCensus,
        Vec<IcCostRow>,
        ClassCostSummary,
        f64,
        f64,
    )],
) {
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let mut s = String::new();
    s.push_str("{\n  \"schema\": \"koblitz_isogeny_cost_sweep/v1\",\n");
    s.push_str(&format!("  \"generated_unix\": {ts},\n"));
    s.push_str(&format!("  \"flatness_cv\": {FLATNESS_CV},\n"));
    s.push_str("  \"reach\": [\n");
    for (i, r) in reach.iter().enumerate() {
        s.push_str(&format!(
            "    {{\"n\": {}, \"order\": \"{}\", \"conductor\": \"{}\", \"conductor_fully_factored\": {}, \
             \"class_size\": \"{}\", \"log2_class_size\": {:.4}, \"nontrivial_degrees\": [{}], \
             \"modular_polynomial_available\": {}, \"log2_exhaustive_scan\": {:.1}, \"blocked_because\": {}}}{}\n",
            r.n, r.order, r.conductor, r.conductor_fully_factored, r.class_size, r.log2_class_size,
            r.nontrivial_degrees.iter().map(|d| format!("\"{d}\"")).collect::<Vec<_>>().join(", "),
            r.modular_polynomial_available, r.log2_exhaustive_scan,
            match &r.blocked_because { Some(w) => format!("\"{}\"", w.replace('"', "'")), None => "null".into() },
            if i + 1 == reach.len() { "" } else { "," }
        ));
    }
    s.push_str("  ],\n  \"sweeps\": [\n");
    for (i, (n, l, a2, census, rows, sum, scan_s, sweep_s)) in sweeps.iter().enumerate() {
        s.push_str(&format!(
            "    {{\n      \"n\": {n}, \"l\": {l}, \"a2\": {a2}, \"m\": {},\n      \"scan_seconds\": {scan_s:.3}, \"sweep_seconds\": {sweep_s:.3},\n",
            sum.m
        ));
        s.push_str(&format!(
            "      \"census\": {{\"a2\": {}, \"scanned\": {}, \"members\": {}, \"twist_members\": {}, \"target_order\": {}, \"twist_order\": {}, \"predicted_class_size\": \"{}\", \"agrees_with_cm\": {}}},\n",
            census.a2, census.scanned, census.members.len(), census.twist_members, census.target_order,
            census.twist_order, census.predicted_class_size, census.agrees_with_cm
        ));
        s.push_str(&format!(
            "      \"summary\": {{\"measured\": {}, \"skipped\": {}, \"verification_failures\": {}, \"inconsistent_rows\": {}, \"transported_secret\": {}, \"members_recovering_secret\": {}, \"all_recovered_transported_secret\": {}, \"verdict\": \"{}\",\n",
            sum.measured, sum.skipped, sum.verification_failures, sum.inconsistent_rows,
            opt_u64(sum.transported_secret), sum.members_recovering_secret,
            sum.all_recovered_transported_secret, sum.verdict()
        ));
        s.push_str(&format!(
            "        \"reductions_per_call\": {}, \"ns_per_call\": {}, \"yield_per_probe\": {}, \"normalised_yield\": {}, \"unknowns\": {}, \"yield_verdict\": \"{}\",\n",
            spread_json(&sum.reductions_per_call),
            spread_json(&sum.ns_per_call),
            spread_json(&sum.yield_per_probe),
            spread_json(&sum.normalised_yield),
            spread_json(&sum.unknowns),
            sum.yield_verdict()
        ));
        s.push_str(&format!(
            "        \"pooled_first_fall\": {}, \"pooled_d_star\": {}, \"first_fall_modes\": {},\n",
            hist_json(&sum.pooled_first_fall),
            hist_json(&sum.pooled_d_star),
            usize_hist_json(&sum.first_fall_modes)
        ));
        s.push_str(&format!(
            "        \"yield_variance_ratio\": {:.6}, \"yield_sampling_variance\": {:.9}, \"normalised_variance_ratio\": {:.6}, \"yield_probes\": {},\n        \"koblitz_reductions_per_call\": {}, \"best_ratio_to_koblitz\": {}}},\n",
            sum.yield_variance_ratio, sum.yield_sampling_variance, sum.normalised_variance_ratio, sum.yield_probes,
            opt_f64(sum.koblitz_reductions_per_call),
            opt_f64(sum.best_ratio_to_koblitz)
        ));
        s.push_str("      \"rows\": [\n");
        for (k, r) in rows.iter().enumerate() {
            s.push_str(&format!(
                "        {{\"a6\": {}, \"j\": {}, \"is_koblitz\": {}, \"order\": {}, \"r\": {}, \"cofactor\": {}, \
                 \"unknowns\": {}, \"factor_base_points\": {}, \"trials\": {}, \"relations\": {}, \
                 \"independent_relations\": {}, \"dependent_relations\": {}, \"inconsistent_relations\": {}, \
                 \"refutations\": {}, \"unknown_probes\": {}, \"direct_skipped\": {}, \
                 \"groebner_ns\": {}, \"groebner_calls\": {}, \"reductions\": {}, \"infeasible_branches\": {}, \
                 \"linear_algebra_ns\": {}, \"row_ops\": {}, \"planted\": {}, \"log\": {}, \"bsgs_log\": {}, \
                 \"verified\": {}, \"closure_trials\": {}, \"closure_relations\": {}, \"solved_at_probe\": {}, \"refutable_targets\": {}, \"first_fall_hist\": {}, \"d_star_hist\": {}}}{}\n",
                r.a6, r.j, r.is_koblitz, r.order, r.r, r.cofactor, r.unknowns, r.factor_base_points,
                r.trials, r.relations, r.independent_relations, r.dependent_relations,
                r.inconsistent_relations, r.refutations, r.unknown_probes, r.direct_skipped,
                r.groebner_ns, r.groebner_calls, r.reductions, r.infeasible_branches,
                r.linear_algebra_ns, r.row_ops, r.planted,
                opt_u64(r.log), opt_u64(r.bsgs_log), r.verified,
                r.closure_trials, r.closure_relations,
                r.solved_at_probe.map(|v| v.to_string()).unwrap_or_else(|| "null".into()),
                r.refutable_targets,
                hist_json(&r.first_fall_hist), hist_json(&r.d_star_hist),
                if k + 1 == rows.len() { "" } else { "," }
            ));
        }
        s.push_str("      ]\n    }");
        s.push_str(if i + 1 == sweeps.len() { "\n" } else { ",\n" });
    }
    s.push_str("  ]\n}\n");

    let path = "experiments/koblitz_isogeny_cost_sweep.json";
    match std::fs::write(path, &s) {
        Ok(()) => println!("\nwrote {path}"),
        Err(e) => println!("\ncould not write {path}: {e}"),
    }
}

fn spread_json(s: &Spread) -> String {
    format!(
        "{{\"n\": {}, \"min\": {:.6}, \"max\": {:.6}, \"mean\": {:.6}, \"stddev\": {:.6}, \"cv\": {:.6}, \"ratio\": {:.6}}}",
        s.n, s.min, s.max, s.mean, s.stddev, s.cv(),
        if s.ratio().is_finite() { s.ratio() } else { -1.0 }
    )
}

fn hist_json(h: &BTreeMap<u32, u32>) -> String {
    let body: Vec<String> = h.iter().map(|(d, c)| format!("\"{d}\": {c}")).collect();
    format!("{{{}}}", body.join(", "))
}

fn usize_hist_json(h: &BTreeMap<u32, usize>) -> String {
    let body: Vec<String> = h.iter().map(|(d, c)| format!("\"{d}\": {c}")).collect();
    format!("{{{}}}", body.join(", "))
}

fn opt_f64(v: Option<f64>) -> String {
    v.map(|x| format!("{x:.6}"))
        .unwrap_or_else(|| "null".into())
}

fn opt_u64(v: Option<u64>) -> String {
    v.map(|x| x.to_string()).unwrap_or_else(|| "null".into())
}
