//! `ic rho` — the counted Pollard-rho references, run paired, and the
//! re-pricing of frozen reports against the matched one.
//!
//! ```text
//! ic rho --prime-bits 16,20,24,28 --char2-degrees 17,21,25,29 --runs 64
//! ic rho --prime-bits 12,16,20,24 --jumps 4,8,16         # calibrate the table size
//! ic rho --reprice docs/ic/runs/ic-boundary-ledger-round5-headline-2026-09-22.json
//! ```
//!
//! **Ladder mode** runs, on every instance and on the same planted
//! logarithms and seeds, three walks: the plain walk every ledger row was
//! priced against through §17 of the boundary note (`frozen-plain`,
//! `A = 1`), the tuned walk on points (`tuned-plain`, `A = 1`) and the
//! tuned walk on `{P, −P}` (`negation`, `A = 2`, the matched reference).
//! The first two differ only in tuning, the last two only in the
//! automorphism, so the paired ratios separate the two.
//!
//! **Re-price mode** reads a frozen `ic boundary` or `ic bench` report,
//! rebuilds each instance from what the report recorded, re-runs the
//! frozen plain walk on the recorded seeds — it must reproduce the
//! recorded counts exactly, or nothing is re-priced — and then runs the
//! matched walk on the same seeds and targets and divides every recorded
//! row's `S` by the new mean.  The index-calculus rows themselves are not
//! re-run: their counts did not change, only the reference did.
//!
//! **Batch mode** (`--batch-koblitz 0/41 --batch-sizes 1,4,16,32
//! --batches 16`) solves `k` targets at a time by batch rho on a Koblitz
//! curve's signed-Frobenius classes, the reference for a figure that
//! amortises one build over `k` targets (ledger §19).  Every batch draws
//! fresh targets, every logarithm is checked against the planted one, and
//! the cost per target is the batch's total over `k·√r`.

use std::path::PathBuf;

use clap::Args;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use serde_json::{json, Value};

use crate::cryptanalysis::ic_boundary::{
    find_prime_order_curve, generic_floor_ops, generic_floor_s, koblitz_instance,
    koblitz_instance_best, prime_instance_for, random_binary_instance, rho_cap, rho_reference,
    rho_reference_walk, roster_prime_instance, signed_frobenius_rho, signed_frobenius_rho_batch,
    BinaryGroup, BinaryInstance, CountedGroup, GroupOps, PrimeInstance, RhoResult, RhoWalk,
};

#[derive(Args, Clone, Debug)]
pub struct RhoArgs {
    /// Prime-field ladder, in subgroup bits (roster curves up to 20 bits,
    /// generated prime-order curves above).
    #[arg(long, value_delimiter = ',')]
    pub prime_bits: Vec<u32>,
    /// Random binary ladder, in field degrees (cofactor at most 8).
    #[arg(long, value_delimiter = ',')]
    pub char2_degrees: Vec<u32>,
    /// Koblitz ladder, in field degrees (`K_a` with the smaller
    /// cofactor): the frozen walk, the negation walk and the repository's
    /// signed-Frobenius walk, paired — the two walks `ic bench` chooses
    /// between on a Koblitz curve.
    #[arg(long, value_delimiter = ',')]
    pub koblitz_degrees: Vec<u32>,
    /// Runs per instance and walk; each plants a fresh logarithm, and
    /// every walk sees the same ones.
    #[arg(long, default_value_t = 64)]
    pub runs: usize,
    /// Picks the curves (above the roster), the planted logarithms and
    /// the walk seeds.
    #[arg(long, default_value_t = 0x5248_4F2D_5245_46)]
    pub seed: u64,
    /// Run the tuned walks at each of these jump counts instead of the
    /// size rule: the calibration of `rho_jumps_for`.
    #[arg(long, value_delimiter = ',')]
    pub jumps: Vec<usize>,
    /// Re-price a frozen `ic boundary` or `ic bench` report.
    #[arg(long)]
    pub reprice: Option<PathBuf>,
    /// Largest cofactor of a rebuilt random binary curve: the `ic bench`
    /// default, which every frozen bench run used.
    #[arg(long, default_value_t = 8)]
    pub max_cofactor: u64,
    /// Generate every prime curve from the seed, even where the roster
    /// has one, so a run's curves are disjoint from another seed's.
    #[arg(long)]
    pub generated_primes: bool,
    /// Batch mode (ledger §19): Koblitz curves as `a/n` (`0/41,0/53`),
    /// each solved in batches of every size in `--batch-sizes` by batch
    /// rho on the signed-Frobenius classes, fresh targets every batch.
    #[arg(long, value_delimiter = ',')]
    pub batch_koblitz: Vec<String>,
    /// Targets per batch.
    #[arg(long, value_delimiter = ',', default_value = "1,4,16,32")]
    pub batch_sizes: Vec<usize>,
    /// Batches per curve and size.
    #[arg(long, default_value_t = 16)]
    pub batches: usize,
}

/// The walks a ladder runs, by name.
#[derive(Clone, Copy, Debug)]
enum Walk {
    FrozenPlain,
    Tuned(RhoWalk),
}

impl Walk {
    fn name(&self) -> String {
        match self {
            Walk::FrozenPlain => "frozen-plain".into(),
            Walk::Tuned(w) => {
                let base = if w.negation {
                    "negation"
                } else {
                    "tuned-plain"
                };
                if w.jumps == 0 {
                    base.into()
                } else {
                    format!("{base}-j{}", w.jumps)
                }
            }
        }
    }

    fn run<G: CountedGroup>(
        &self,
        g: &G,
        gen: G::Elt,
        q: G::Elt,
        r: u64,
        seed: u64,
        cap: u64,
    ) -> RhoResult {
        match self {
            Walk::FrozenPlain => rho_reference(g, gen, q, r, seed, cap),
            Walk::Tuned(w) => rho_reference_walk(g, gen, q, r, seed, cap, *w),
        }
    }
}

/// What a set of runs of one walk on one instance came to.
fn summarise(walk: &str, r: u64, runs: &[(u64, u64, RhoResult)]) -> Value {
    let n = runs.len().max(1) as f64;
    let mean = |f: &dyn Fn(&RhoResult) -> f64| runs.iter().map(|(_, _, x)| f(x)).sum::<f64>() / n;
    let mut s: Vec<f64> = runs.iter().map(|(_, _, x)| x.s).collect();
    s.sort_by(f64::total_cmp);
    let median = if s.is_empty() {
        f64::NAN
    } else {
        s[s.len() / 2]
    };
    let a = runs.first().map_or(1, |(_, _, x)| x.automorphisms);
    let mut counters = serde_json::Map::new();
    for (_, _, x) in runs {
        for (k, v) in &x.counters {
            let e = counters.entry(k.clone()).or_insert(json!(0u64));
            *e = json!(e.as_u64().unwrap_or(0) + v);
        }
    }
    let verified = runs
        .iter()
        .all(|(planted, _, x)| x.verified && x.recovered == Some(*planted));
    json!({
        "walk": walk,
        "method": runs.first().map(|(_, _, x)| x.method.clone()),
        "automorphisms": a,
        "runs": runs.len(),
        "mean_gae": mean(&|x| x.gae),
        "mean_s": mean(&|x| x.s),
        "median_s": median,
        "mean_s_walk": mean(&|x| x.s_walk),
        // Walk operations over the walk's own floor, √(πr/2A).
        "walk_over_own_floor": mean(&|x| x.steps_over_expected),
        "floor_s_own": generic_floor_s(a as f64),
        "mean_wall_ms": mean(&|x| x.wall_ns as f64 / 1e6),
        "all_verified": verified,
        "counters_summed": counters,
        "per_run": runs.iter().map(|(planted, seed, x)| json!({
            "planted": planted, "seed": seed, "s": x.s, "s_walk": x.s_walk, "steps": x.steps,
            "gae": x.gae, "verified": x.verified && x.recovered == Some(*planted),
        })).collect::<Vec<_>>(),
        "r": r,
    })
}

/// Every walk on one instance, paired: the same planted logarithms and
/// seeds for each.
fn ladder_instance<G: CountedGroup>(
    g: &G,
    gen: G::Elt,
    r: u64,
    seed: u64,
    runs: usize,
    walks: &[Walk],
) -> Vec<Value> {
    let mut rng = StdRng::seed_from_u64(seed ^ r.rotate_left(17));
    let draws: Vec<(u64, u64)> = (0..runs)
        .map(|_| (rng.gen_range(1..r), rng.gen::<u64>()))
        .collect();
    let cap = rho_cap(r, 64.0);
    walks
        .iter()
        .map(|w| {
            let results: Vec<(u64, u64, RhoResult)> = draws
                .iter()
                .map(|&(planted, s)| {
                    let mut ops = GroupOps::default();
                    let q = g.mul(&mut ops, gen, planted);
                    (planted, s, w.run(g, gen, q, r, s, cap))
                })
                .collect();
            summarise(&w.name(), r, &results)
        })
        .collect()
}

/// The Koblitz walks on one instance, paired like [`ladder_instance`]:
/// the frozen walk, the negation walk, and the signed-Frobenius walk
/// priced as the Koblitz regime prices it.
fn koblitz_ladder_instance(inst: &BinaryInstance, seed: u64, runs: usize) -> Vec<Value> {
    let bg = BinaryGroup(&inst.fast);
    let (gen, r) = (inst.generator, inst.r);
    let mut rng = StdRng::seed_from_u64(seed ^ r.rotate_left(17));
    let draws: Vec<(u64, u64)> = (0..runs)
        .map(|_| (rng.gen_range(1..r), rng.gen::<u64>()))
        .collect();
    let cap = rho_cap(r, 64.0);
    let mut out = Vec::new();
    for name in ["frozen-plain", "negation", "signed-frobenius"] {
        let results: Vec<(u64, u64, RhoResult)> = draws
            .iter()
            .map(|&(planted, s)| {
                let mut ops = GroupOps::default();
                let q = bg.mul(&mut ops, gen, planted);
                let res = match name {
                    "frozen-plain" => rho_reference(&bg, gen, q, r, s, cap),
                    "negation" => rho_reference_walk(&bg, gen, q, r, s, cap, RhoWalk::negation()),
                    _ => signed_frobenius_rho(inst, q, planted, s).expect("a Koblitz instance"),
                };
                (planted, s, res)
            })
            .collect();
        out.push(summarise(name, r, &results));
    }
    out
}

/// Automorphisms beyond negation a generic algorithm could use on a
/// prime curve: `j = 0` (`a = 0`, order 6 when `p ≡ 1 mod 3`) and
/// `j = 1728` (`b = 0`, order 4 when `p ≡ 1 mod 4`).
fn prime_exclusions(inst: &PrimeInstance) -> Value {
    let c = &inst.curve;
    let extra = if c.a == 0 && c.p % 3 == 1 {
        Some("j = 0: an order-6 automorphism group")
    } else if c.b == 0 && c.p % 4 == 1 {
        Some("j = 1728: an order-4 automorphism group")
    } else {
        None
    };
    json!({
        "a_is_zero": c.a == 0,
        "b_is_zero": c.b == 0,
        "additional_automorphisms": extra,
        "matched_rho_eligible": if extra.is_none() { "negation only (A = 2)" } else { "NOT MATCHED: the curve has more" },
    })
}

/// Whether a random binary curve is defined over a proper subfield: `b`
/// fixed by `x ↦ x^{2^k}` for a proper divisor `k` of `n` (`a` is in
/// `F_2` already).  Such a curve has a Frobenius of order `n/k` and the
/// negation-only walk would not be matched.
fn binary_exclusions(inst: &BinaryInstance) -> Value {
    let n = inst.n;
    let f = &inst.fast.field;
    let subfields: Vec<u32> = (1..n)
        .filter(|k| n.is_multiple_of(*k) && f.sqr_k(inst.b, *k) == inst.b)
        .collect();
    json!({
        "koblitz": inst.koblitz.is_some(),
        "defined_over_proper_subfields_of_degree": subfields,
        "matched_rho_eligible": if inst.koblitz.is_some() {
            "Koblitz: signed Frobenius (A = 2n) and negation"
        } else if subfields.is_empty() {
            "negation only (A = 2)"
        } else {
            "NOT MATCHED: the curve is defined over a proper subfield"
        },
    })
}

fn walks_for(args: &RhoArgs) -> Vec<Walk> {
    let mut walks = vec![Walk::FrozenPlain];
    if args.jumps.is_empty() {
        walks.push(Walk::Tuned(RhoWalk::plain()));
        walks.push(Walk::Tuned(RhoWalk::negation()));
    } else {
        for &j in &args.jumps {
            walks.push(Walk::Tuned(RhoWalk {
                jumps: j,
                ..RhoWalk::plain()
            }));
            walks.push(Walk::Tuned(RhoWalk {
                jumps: j,
                ..RhoWalk::negation()
            }));
        }
    }
    walks
}

/// Least squares `y = αx + c`, with `R²`.
fn fit(xs: &[f64], ys: &[f64]) -> Option<(f64, f64)> {
    let n = xs.len() as f64;
    if xs.len() < 2 {
        return None;
    }
    let (mx, my) = (xs.iter().sum::<f64>() / n, ys.iter().sum::<f64>() / n);
    let sxx: f64 = xs.iter().map(|x| (x - mx).powi(2)).sum();
    let sxy: f64 = xs.iter().zip(ys).map(|(x, y)| (x - mx) * (y - my)).sum();
    let syy: f64 = ys.iter().map(|y| (y - my).powi(2)).sum();
    if sxx == 0.0 {
        return None;
    }
    let alpha = sxy / sxx;
    let r2 = if syy == 0.0 {
        1.0
    } else {
        (sxy * sxy) / (sxx * syy)
    };
    Some((alpha, r2))
}

fn fmt(v: f64) -> String {
    if !v.is_finite() {
        "—".into()
    } else if v >= 100.0 {
        format!("{v:.0}")
    } else if v >= 10.0 {
        format!("{v:.1}")
    } else {
        format!("{v:.3}")
    }
}

fn ladder(args: &RhoArgs, json_only: bool) -> Result<Value, String> {
    let walks = walks_for(args);
    let mut instances = Vec::new();
    for &bits in &args.prime_bits {
        if !(8..=32).contains(&bits) {
            return Err(format!("prime bits must lie in 8..=32, got {bits}"));
        }
        let inst = if args.generated_primes {
            find_prime_order_curve(bits, args.seed)
        } else {
            prime_instance_for(bits, args.seed)
        };
        if !json_only {
            eprintln!("  prime {bits}: {} r = {}", inst.name, inst.r);
        }
        let rows = ladder_instance(
            &inst.curve,
            inst.generator_point(),
            inst.r,
            args.seed,
            args.runs,
            &walks,
        );
        instances.push(json!({
            "regime": "prime", "instance": inst.name, "r": inst.r, "log2_r": (inst.r as f64).log2(),
            "cofactor": inst.cofactor, "exclusions": prime_exclusions(&inst), "walks": rows,
        }));
    }
    for &n in &args.char2_degrees {
        if !(5..=62).contains(&n) {
            return Err(format!("field degrees must lie in 5..=62, got {n}"));
        }
        let inst = random_binary_instance(n, args.seed, args.max_cofactor)
            .ok_or_else(|| format!("no random binary curve at n = {n}"))?;
        if !json_only {
            eprintln!("  char2 {n}: {} r = {}", inst.name, inst.r);
        }
        let rows = ladder_instance(
            &BinaryGroup(&inst.fast),
            inst.generator,
            inst.r,
            args.seed,
            args.runs,
            &walks,
        );
        instances.push(json!({
            "regime": "char2", "instance": inst.name, "r": inst.r, "log2_r": (inst.r as f64).log2(),
            "cofactor": inst.cofactor, "exclusions": binary_exclusions(&inst), "walks": rows,
        }));
    }
    for &n in &args.koblitz_degrees {
        if !(5..=62).contains(&n) {
            return Err(format!("field degrees must lie in 5..=62, got {n}"));
        }
        let inst = koblitz_instance_best(n)
            .ok_or_else(|| format!("no usable Koblitz curve at n = {n}"))?;
        if !json_only {
            eprintln!("  koblitz {n}: {} r = {}", inst.name, inst.r);
        }
        let rows = koblitz_ladder_instance(&inst, args.seed, args.runs);
        instances.push(json!({
            "regime": "koblitz", "instance": inst.name, "r": inst.r, "log2_r": (inst.r as f64).log2(),
            "cofactor": inst.cofactor, "exclusions": binary_exclusions(&inst), "walks": rows,
        }));
    }

    // The table: one unit, every walk a row, ratios to the floor (A = 2,
    // what a generic algorithm may use on these curves) and to the matched
    // walk on the same instance.
    let mut md = String::from(
        "| regime | instance | log₂ r | walk | A | jumps | runs | S | S median | S walk | walk / own floor | vs floor (A=2) | vs matched | ok |\n|:--|:--|--:|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|\n",
    );
    for inst in &instances {
        let rows = inst["walks"].as_array().cloned().unwrap_or_default();
        // The matched reference: the negation walk, or on a Koblitz
        // curve the cheaper of it and the signed-Frobenius walk.
        let matched = rows
            .iter()
            .filter(|w| w["walk"] == "negation" || w["walk"] == "signed-frobenius")
            .filter_map(|w| w["mean_s"].as_f64())
            .fold(f64::NAN, f64::min);
        for w in &rows {
            let s = w["mean_s"].as_f64().unwrap_or(f64::NAN);
            let jumps = w["counters_summed"]["jumps"]
                .as_u64()
                .map(|j| j / w["runs"].as_u64().unwrap_or(1).max(1));
            md.push_str(&format!(
                "| {} | {} | {:.1} | {} | {} | {} | {} | {} | {} | {} | {} | {}× | {} | {} |\n",
                inst["regime"].as_str().unwrap_or("?"),
                inst["instance"].as_str().unwrap_or("?"),
                inst["log2_r"].as_f64().unwrap_or(0.0),
                w["walk"].as_str().unwrap_or("?"),
                w["automorphisms"],
                jumps.map_or("16".to_string(), |j| j.to_string()),
                w["runs"],
                fmt(s),
                fmt(w["median_s"].as_f64().unwrap_or(f64::NAN)),
                fmt(w["mean_s_walk"].as_f64().unwrap_or(f64::NAN)),
                fmt(w["walk_over_own_floor"].as_f64().unwrap_or(f64::NAN)),
                fmt(s / generic_floor_s(2.0)),
                if matched.is_finite() {
                    format!("{}×", fmt(s / matched))
                } else {
                    "—".into()
                },
                if w["all_verified"] == true {
                    "✓"
                } else {
                    "✗"
                },
            ));
        }
    }
    // Exponents of the mean total operations against r, per regime and
    // walk, over every size the ladder ran.
    let mut fits = Vec::new();
    md.push_str("\n| regime | walk | α (total ops ∝ r^α) | R² | sizes |\n|:--|:--|--:|--:|--:|\n");
    for regime in ["prime", "char2", "koblitz"] {
        let mut names: Vec<String> = Vec::new();
        for i in instances.iter().filter(|i| i["regime"] == regime) {
            for w in i["walks"].as_array().into_iter().flatten() {
                let n = w["walk"].as_str().unwrap_or("?").to_string();
                if !names.contains(&n) {
                    names.push(n);
                }
            }
        }
        for name in names {
            let pts: Vec<(f64, f64)> = instances
                .iter()
                .filter(|i| i["regime"] == regime)
                .filter_map(|i| {
                    let row = i["walks"]
                        .as_array()?
                        .iter()
                        .find(|x| x["walk"] == name.as_str())?;
                    Some((i["log2_r"].as_f64()?, row["mean_gae"].as_f64()?.log2()))
                })
                .collect();
            if pts.len() < 2 {
                continue;
            }
            let xs: Vec<f64> = pts.iter().map(|p| p.0).collect();
            let ys: Vec<f64> = pts.iter().map(|p| p.1).collect();
            if let Some((alpha, r2)) = fit(&xs, &ys) {
                md.push_str(&format!(
                    "| {regime} | {name} | {alpha:.3} | {r2:.3} | {} |\n",
                    pts.len()
                ));
                fits.push(json!({"regime": regime, "walk": name, "alpha": alpha, "r_squared": r2, "sizes": pts.len()}));
            }
        }
    }
    let all_verified = instances.iter().all(|i| {
        i["walks"]
            .as_array()
            .is_some_and(|w| w.iter().all(|x| x["all_verified"] == true))
    });
    if !json_only {
        eprintln!("\n{md}");
    }
    Ok(json!({
        "schema_version": 1,
        "operation": "rho",
        "status": if all_verified && !instances.is_empty() { "complete" } else { "incomplete" },
        "what_this_is": "Counted Pollard rho walks run paired on the same instances, planted logarithms and seeds: the plain walk the boundary ledger priced every row against through section 17, the same tuning on points, and the negation-map walk that is the matched reference (A = 2). S = group-addition equivalents / sqrt(r), everything inside: table, starts, walk, verification.",
        "what_this_is_not": [
            "not an index-calculus result: no relation is collected here",
            "not a wall-clock benchmark: wall time is a practicality note",
            "not a claim about any deployed curve"
        ],
        "config": {"prime_bits": args.prime_bits, "char2_degrees": args.char2_degrees, "runs": args.runs,
                   "seed": args.seed, "jumps": args.jumps, "max_cofactor": args.max_cofactor,
                   "generated_primes": args.generated_primes,
                   "cap": "rho_cap(r, 64): 64 x sqrt(pi r / 2) + 4096 operations per run"},
        "all_verified": all_verified,
        "instances": instances,
        "fits": fits,
        "markdown": md,
    }))
}

// ── Re-pricing frozen reports ─────────────────────────────────────

/// Whether a re-run of the frozen plain walk reproduced the recorded run.
fn same_run(recorded: &Value, rerun: &RhoResult) -> Result<(), String> {
    let u = |k: &str| recorded[k].as_u64();
    let ops = &recorded["group_ops"];
    let checks = [
        ("steps", u("steps"), Some(rerun.steps)),
        ("walks", u("walks"), Some(rerun.walks)),
        (
            "distinguished_points",
            u("distinguished_points"),
            Some(rerun.distinguished_points),
        ),
        ("adds", ops["adds"].as_u64(), Some(rerun.group_ops.adds)),
        (
            "doubles",
            ops["doubles"].as_u64(),
            Some(rerun.group_ops.doubles),
        ),
        (
            "scalar_mults",
            ops["scalar_mults"].as_u64(),
            Some(rerun.group_ops.scalar_mults),
        ),
        ("recovered", recorded["recovered"].as_u64(), rerun.recovered),
    ];
    for (what, a, b) in checks {
        if a != b {
            return Err(format!("{what}: recorded {a:?}, re-run {b:?}"));
        }
    }
    let s = recorded["s"].as_f64().unwrap_or(f64::NAN);
    if (s - rerun.s).abs() > 1e-9 * s.abs().max(1.0) {
        return Err(format!("s: recorded {s}, re-run {}", rerun.s));
    }
    Ok(())
}

fn rebuild_prime(name: &str, bits_list: &[u32], seed: u64) -> Option<PrimeInstance> {
    for &b in bits_list {
        let inst = prime_instance_for(b, seed);
        if inst.name == name {
            return Some(inst);
        }
    }
    (8..=20)
        .filter_map(roster_prime_instance)
        .find(|i| i.name == name)
}

/// One ledger instance of a frozen `ic boundary` report, re-priced.
fn reprice_boundary_instance(
    inst: &Value,
    cfg: &Value,
    identity: &mut Vec<String>,
    progress: &mut dyn FnMut(&str),
) -> Result<Value, String> {
    let regime = inst["regime"].as_str().unwrap_or("?").to_string();
    let name = inst["curve"]["name"].as_str().unwrap_or("?").to_string();
    let r = inst["r"].as_u64().ok_or("instance without r")?;
    let seed = cfg["seed"].as_u64().ok_or("config without seed")?;
    let rho_repeats = cfg["rho_repeats"].as_u64().unwrap_or(1).max(1) as usize;
    let multiple = cfg["rho_cap_multiple"].as_f64().unwrap_or(64.0);
    let seeds: Vec<u64> = inst["seeds"]
        .as_array()
        .ok_or("no seeds")?
        .iter()
        .filter_map(Value::as_u64)
        .collect();
    let targets: Vec<u64> = inst["targets"]
        .as_array()
        .ok_or("no targets")?
        .iter()
        .filter_map(Value::as_u64)
        .collect();
    let frozen_rho = inst["rho"].as_array().cloned().unwrap_or_default();
    if regime == "koblitz" {
        // Already priced against the signed-Frobenius walk (A = 2n).
        return Ok(json!({
            "regime": regime, "instance": name, "r": r,
            "unchanged": "the Koblitz regime has been priced against the signed-Frobenius walk (A = 2n) since Round 1",
            "frozen_rho_s_mean": inst["rho_s_mean"],
        }));
    }
    progress(&format!("{regime} {name}: rebuilding"));
    // (per-rep matched S means, all runs, identity failures)
    let mut matched_runs: Vec<RhoResult> = Vec::new();
    let mut per_rep_matched: Vec<f64> = Vec::new();
    let mut per_rep_frozen: Vec<f64> = Vec::new();
    let cap = rho_cap(r, multiple);
    let mut run_one =
        |g_run: &mut dyn FnMut(u64, u64, RhoWalkOrPlain) -> RhoResult| -> Result<(), String> {
            for (rep, (&seed_rep, &d)) in seeds.iter().zip(&targets).enumerate() {
                let (mut sum_m, mut sum_f) = (0.0, 0.0);
                for k in 0..rho_repeats {
                    let rho_seed = seed_rep ^ (k as u64 * 0x5EED);
                    let plain = g_run(d, rho_seed, RhoWalkOrPlain::Plain);
                    let recorded = frozen_rho
                        .get(rep * rho_repeats + k)
                        .ok_or_else(|| format!("{name}: no recorded rho run {rep}/{k}"))?;
                    if let Err(why) = same_run(recorded, &plain) {
                        identity.push(format!("{name} rep {rep} run {k}: {why}"));
                    }
                    sum_f += plain.s;
                    let matched = g_run(d, rho_seed, RhoWalkOrPlain::Negation);
                    sum_m += matched.s;
                    matched_runs.push(matched);
                }
                per_rep_matched.push(sum_m / rho_repeats as f64);
                per_rep_frozen.push(sum_f / rho_repeats as f64);
            }
            Ok(())
        };
    let exclusions = match regime.as_str() {
        "prime" => {
            let bits_list: Vec<u32> = cfg["prime_bits"]
                .as_array()
                .map(|a| {
                    a.iter()
                        .filter_map(|b| b.as_u64().map(|b| b as u32))
                        .collect()
                })
                .unwrap_or_default();
            let p = rebuild_prime(&name, &bits_list, seed)
                .ok_or_else(|| format!("cannot rebuild {name}"))?;
            if p.r != r {
                return Err(format!(
                    "{name}: rebuilt r = {} but the report has {r}",
                    p.r
                ));
            }
            let g = p.generator_point();
            run_one(&mut |d, s, which| {
                let mut ops = GroupOps::default();
                let q = p.curve.mul(&mut ops, g, d);
                match which {
                    RhoWalkOrPlain::Plain => rho_reference(&p.curve, g, q, r, s, cap),
                    RhoWalkOrPlain::Negation => {
                        rho_reference_walk(&p.curve, g, q, r, s, cap, RhoWalk::negation())
                    }
                }
            })?;
            prime_exclusions(&p)
        }
        "char2" => {
            let n = inst["curve"]["field"]["degree"]
                .as_u64()
                .ok_or("binary instance without a degree")? as u32;
            let b = random_binary_instance(n, seed, 8)
                .ok_or_else(|| format!("cannot rebuild {name}"))?;
            if b.name != name || b.r != r {
                return Err(format!("{name}: rebuilt {} with r = {}", b.name, b.r));
            }
            let bg = BinaryGroup(&b.fast);
            run_one(&mut |d, s, which| {
                let mut ops = GroupOps::default();
                let q = bg.mul(&mut ops, b.generator, d);
                match which {
                    RhoWalkOrPlain::Plain => rho_reference(&bg, b.generator, q, r, s, cap),
                    RhoWalkOrPlain::Negation => {
                        rho_reference_walk(&bg, b.generator, q, r, s, cap, RhoWalk::negation())
                    }
                }
            })?;
            binary_exclusions(&b)
        }
        other => return Err(format!("unknown regime {other}")),
    };
    let matched_mean =
        matched_runs.iter().map(|x| x.s).sum::<f64>() / matched_runs.len().max(1) as f64;
    let matched_verified = matched_runs.iter().all(|x| x.verified);
    let frozen_mean = inst["rho_s_mean"].as_f64().unwrap_or(f64::NAN);
    // Variant rows: which repeat each belongs to, by the logarithm it
    // recovered (every frozen row is verified), then its ratio to that
    // repeat's reference — the per-row `ratio_to_rho` — and the table's
    // mean over the name.
    let variants = inst["variants"].as_array().cloned().unwrap_or_default();
    let mut names: Vec<String> = Vec::new();
    let mut rows = Vec::new();
    for v in &variants {
        let vname = v["name"].as_str().unwrap_or("?").to_string();
        if !names.contains(&vname) {
            names.push(vname.clone());
        }
        let rep = v["recovered"]
            .as_u64()
            .and_then(|d| targets.iter().position(|&t| t == d));
        let s = v["s"].as_f64().unwrap_or(f64::NAN);
        rows.push(json!({
            "variant": vname, "rep": rep, "s": s,
            "ratio_to_rho_frozen": v["ratio_to_rho"],
            "ratio_to_rho_matched": rep.map(|k| s / per_rep_matched[k]),
            "verified": v["verified"],
        }));
    }
    let table: Vec<Value> = names
        .iter()
        .map(|n| {
            let ss: Vec<f64> = variants
                .iter()
                .filter(|v| v["name"] == n.as_str())
                .filter_map(|v| v["s"].as_f64())
                .collect();
            let mean = ss.iter().sum::<f64>() / ss.len().max(1) as f64;
            json!({
                "variant": n, "mean_s": mean,
                "vs_rho_frozen": mean / frozen_mean,
                "vs_rho_matched": mean / matched_mean,
                "vs_floor": mean / generic_floor_s(2.0),
            })
        })
        .collect();
    Ok(json!({
        "regime": regime, "instance": name, "r": r, "log2_r": (r as f64).log2(),
        "exclusions": exclusions,
        "frozen_reference": {"method": frozen_rho.first().map(|x| x["method"].clone()), "automorphisms": 1,
                             "mean_s": frozen_mean, "per_rep_mean_s": per_rep_frozen},
        "matched_reference": {"method": matched_runs.first().map(|x| x.method.clone()), "automorphisms": 2,
                              "runs": matched_runs.len(), "mean_s": matched_mean,
                              "mean_s_walk": matched_runs.iter().map(|x| x.s_walk).sum::<f64>() / matched_runs.len().max(1) as f64,
                              "walk_over_own_floor": matched_runs.iter().map(|x| x.steps_over_expected).sum::<f64>() / matched_runs.len().max(1) as f64,
                              "per_rep_mean_s": per_rep_matched, "all_verified": matched_verified,
                              "per_run": matched_runs.iter().map(|x| json!({"s": x.s, "s_walk": x.s_walk, "gae": x.gae, "verified": x.verified, "recovered": x.recovered, "counters": x.counters})).collect::<Vec<_>>()},
        "frozen_over_matched": frozen_mean / matched_mean,
        "variants": table,
        "rows": rows,
    }))
}

#[derive(Clone, Copy)]
enum RhoWalkOrPlain {
    Plain,
    Negation,
}

/// A frozen `ic bench` report, re-priced.  The instance is rebuilt from
/// the recorded name and the seed the rho runs carry (`seed ^
/// (0x5248_4F00 + k)`), then checked against the recorded order.
fn reprice_bench(
    doc: &Value,
    max_cofactor: u64,
    identity: &mut Vec<String>,
) -> Result<Value, String> {
    let name = doc["instance"]
        .as_str()
        .ok_or("bench report without an instance")?
        .to_string();
    let regime = doc["regime"].as_str().unwrap_or("?").to_string();
    let per_run = doc["rho_reference"]["per_run"]
        .as_array()
        .cloned()
        .ok_or("bench report without rho_reference.per_run")?;
    let first_seed = per_run
        .first()
        .and_then(|x| x["seed"].as_u64())
        .ok_or("no rho runs")?;
    let seed = first_seed ^ 0x5248_4F00;
    let r = doc["rows"][0]["r"].as_u64().ok_or("no row carries r")?;
    let max_steps = (generic_floor_ops(r as f64, 1.0) * 64.0) as u64 + 4096;
    let degree = |name: &str| -> Option<u32> {
        let at = name.find("-n")? + 2;
        name[at..].split('-').next()?.parse().ok()
    };
    // (planted, run seed) of every recorded run.
    let draws: Vec<(u64, u64, Value)> = per_run
        .iter()
        .filter_map(|x| Some((x["planted"].as_u64()?, x["seed"].as_u64()?, x.clone())))
        .collect();
    let check = |recorded: &Value, rerun: &RhoResult| -> Result<(), String> {
        let steps = recorded["steps"].as_u64();
        let s = recorded["s"].as_f64().unwrap_or(f64::NAN);
        if steps != Some(rerun.steps) || (s - rerun.s).abs() > 1e-9 * s.abs().max(1.0) {
            return Err(format!(
                "recorded steps {steps:?} S {s}, re-run steps {} S {}",
                rerun.steps, rerun.s
            ));
        }
        Ok(())
    };
    let mut matched: Vec<RhoResult> = Vec::new();
    let mut signed: Vec<RhoResult> = Vec::new();
    let exclusions = match regime.as_str() {
        "char2" | "koblitz" => {
            let inst = if regime == "char2" {
                let n = degree(&name).ok_or_else(|| format!("no degree in {name}"))?;
                random_binary_instance(n, seed, max_cofactor)
                    .ok_or_else(|| format!("cannot rebuild {name}"))?
            } else {
                let n: u32 = name
                    .split("2^")
                    .nth(1)
                    .and_then(|t| t.trim_end_matches(')').parse().ok())
                    .ok_or_else(|| format!("no degree in {name}"))?;
                koblitz_instance(1, n)
                    .filter(|i| i.name == name)
                    .or_else(|| koblitz_instance(0, n))
                    .ok_or("no Koblitz curve")?
            };
            if inst.name != name || inst.r != r {
                return Err(format!("{name}: rebuilt {} with r = {}", inst.name, inst.r));
            }
            let bg = BinaryGroup(&inst.fast);
            for (k, (planted, s, recorded)) in draws.iter().enumerate() {
                let mut ops = GroupOps::default();
                let q = bg.mul(&mut ops, inst.generator, *planted);
                let plain = rho_reference(&bg, inst.generator, q, r, *s, max_steps);
                if let Err(why) = check(recorded, &plain) {
                    identity.push(format!("{name} run {k}: {why}"));
                }
                matched.push(rho_reference_walk(
                    &bg,
                    inst.generator,
                    q,
                    r,
                    *s,
                    max_steps,
                    RhoWalk::negation(),
                ));
                if inst.koblitz.is_some() {
                    if let Some(x) = signed_frobenius_rho(&inst, q, *planted, *s) {
                        signed.push(x);
                    }
                }
            }
            binary_exclusions(&inst)
        }
        "prime" => {
            let inst = (8..=20)
                .filter_map(roster_prime_instance)
                .find(|i| i.name == name)
                .ok_or_else(|| format!("cannot rebuild {name}"))?;
            let g = inst.generator_point();
            for (k, (planted, s, recorded)) in draws.iter().enumerate() {
                let mut ops = GroupOps::default();
                let q = inst.curve.mul(&mut ops, g, *planted);
                let plain = rho_reference(&inst.curve, g, q, r, *s, max_steps);
                if let Err(why) = check(recorded, &plain) {
                    identity.push(format!("{name} run {k}: {why}"));
                }
                matched.push(rho_reference_walk(
                    &inst.curve,
                    g,
                    q,
                    r,
                    *s,
                    max_steps,
                    RhoWalk::negation(),
                ));
            }
            prime_exclusions(&inst)
        }
        other => return Err(format!("unknown regime {other}")),
    };
    let mean = |v: &[RhoResult]| v.iter().map(|x| x.s).sum::<f64>() / v.len().max(1) as f64;
    let (mut matched_mean, mut method) =
        (mean(&matched), matched.first().map(|x| x.method.clone()));
    let signed_mean = (!signed.is_empty()).then(|| mean(&signed));
    if let Some(sm) = signed_mean {
        if sm < matched_mean && signed.iter().all(|x| x.verified) {
            matched_mean = sm;
            method = signed.first().map(|x| x.method.clone());
        }
    }
    let frozen_mean = doc["rho_reference"]["mean_s"].as_f64().unwrap_or(f64::NAN);
    let verified = matched.iter().all(|x| x.verified)
        && draws
            .iter()
            .zip(&matched)
            .all(|((p, _, _), x)| x.recovered == Some(*p));
    let rows: Vec<Value> = doc["rows"]
        .as_array()
        .cloned()
        .unwrap_or_default()
        .iter()
        .map(|row| {
            let s = row["s"].as_f64().unwrap_or(f64::NAN);
            json!({
                "label": row["label"], "s": s, "verified": row["verified"],
                "vs_rho_frozen": s / frozen_mean, "vs_rho_matched": s / matched_mean,
            })
        })
        .collect();
    Ok(json!({
        "regime": regime, "instance": name, "r": r, "log2_r": (r as f64).log2(), "bench_seed": seed,
        "exclusions": exclusions,
        "frozen_reference": {"method": doc["rho_reference"]["method"], "automorphisms": 1, "mean_s": frozen_mean,
                             "runs": draws.len()},
        "matched_reference": {"method": method, "mean_s": matched_mean, "all_verified": verified,
                              "negation_mean_s": mean(&matched), "signed_frobenius_mean_s": signed_mean,
                              "mean_s_walk": matched.iter().map(|x| x.s_walk).sum::<f64>() / matched.len().max(1) as f64,
                              "walk_over_own_floor": matched.iter().map(|x| x.steps_over_expected).sum::<f64>() / matched.len().max(1) as f64,
                              "per_run": matched.iter().map(|x| json!({"s": x.s, "s_walk": x.s_walk, "gae": x.gae, "verified": x.verified, "recovered": x.recovered, "counters": x.counters})).collect::<Vec<_>>()},
        "frozen_over_matched": frozen_mean / matched_mean,
        "rows": rows,
    }))
}

fn reprice(path: &PathBuf, args: &RhoArgs, json_only: bool) -> Result<Value, String> {
    let bytes = std::fs::read(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let hash = blake3::hash(&bytes).to_hex().to_string();
    let doc: Value =
        serde_json::from_slice(&bytes).map_err(|e| format!("{}: {e}", path.display()))?;
    let mut identity: Vec<String> = Vec::new();
    let mut progress = |line: &str| {
        if !json_only {
            eprintln!("  {line}");
        }
    };
    let (kind, instances) = match doc["operation"].as_str() {
        Some("boundary") => {
            let cfg = &doc["config"];
            let mut out = Vec::new();
            for inst in doc["ledger"]["instances"]
                .as_array()
                .cloned()
                .unwrap_or_default()
            {
                out.push(reprice_boundary_instance(
                    &inst,
                    cfg,
                    &mut identity,
                    &mut progress,
                )?);
            }
            ("boundary", out)
        }
        Some("bench") => (
            "bench",
            vec![reprice_bench(&doc, args.max_cofactor, &mut identity)?],
        ),
        other => return Err(format!("cannot re-price a report of operation {other:?}")),
    };
    let identity_ok = identity.is_empty();
    let matched_ok = instances.iter().all(|i| {
        i.get("matched_reference")
            .is_none_or(|m| m["all_verified"] == true)
    });
    // The re-priced table.
    let mut md = String::from(
        "| instance | log₂ r | row | S | vs rho (frozen, A = 1) | vs rho (matched) | vs floor (A = 2) |\n|:--|--:|:--|--:|--:|--:|--:|\n",
    );
    for inst in &instances {
        let label_rows: Vec<Value> = match kind {
            "boundary" => inst["variants"].as_array().cloned().unwrap_or_default(),
            _ => inst["rows"].as_array().cloned().unwrap_or_default(),
        };
        if let (Some(f), Some(m)) = (
            inst["frozen_reference"]["mean_s"].as_f64(),
            inst["matched_reference"]["mean_s"].as_f64(),
        ) {
            md.push_str(&format!(
                "| {} | {:.1} | **rho** (frozen {} → matched {}) | | | | |\n",
                inst["instance"].as_str().unwrap_or("?"),
                inst["log2_r"].as_f64().unwrap_or(0.0),
                fmt(f),
                fmt(m)
            ));
        }
        for row in label_rows {
            let s = row["mean_s"]
                .as_f64()
                .or(row["s"].as_f64())
                .unwrap_or(f64::NAN);
            md.push_str(&format!(
                "| {} | {:.1} | {} | {} | {}× | {}× | {}× |\n",
                inst["instance"].as_str().unwrap_or("?"),
                inst["log2_r"].as_f64().unwrap_or(0.0),
                row["variant"]
                    .as_str()
                    .or(row["label"].as_str())
                    .unwrap_or("?"),
                fmt(s),
                fmt(row["vs_rho_frozen"].as_f64().unwrap_or(f64::NAN)),
                fmt(row["vs_rho_matched"].as_f64().unwrap_or(f64::NAN)),
                fmt(s / generic_floor_s(2.0)),
            ));
        }
    }
    if !json_only {
        eprintln!("\n{md}");
        if !identity_ok {
            eprintln!(
                "  IDENTITY FAILED: {} frozen runs did not reproduce",
                identity.len()
            );
        }
    }
    Ok(json!({
        "schema_version": 1,
        "operation": "rho-reprice",
        "status": if identity_ok && matched_ok { "complete" } else { "incomplete" },
        "what_this_is": "A frozen report's rows re-priced against the matched rho reference (negation map, A = 2, on the same instance, seeds and targets) instead of the plain A = 1 walk they were priced against. The frozen plain walk is re-run first on the recorded seeds and must reproduce the recorded counts exactly.",
        "what_this_is_not": [
            "not a re-run of any index-calculus row: their counts are the frozen ones",
            "not a speedup of anything: the reference moved, which is accounting"
        ],
        "source": path.display().to_string(),
        "source_blake3": hash,
        "source_operation": kind,
        "identity": {"all_reproduced": identity_ok, "failures": identity},
        "instances": instances,
        "markdown": md,
    }))
}

// ── Batch rho ──────────────────────────────────────────────────────

/// A seed for one piece of one batch, from the run's seed.
fn derive(seed: u64, parts: &[u64]) -> u64 {
    let mut h = seed ^ 0x9E37_79B9_7F4A_7C15;
    for &p in parts {
        h = (h ^ p).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        h ^= h >> 31;
    }
    h
}

/// The batch law's per-target share at `k` targets, relative to one
/// target alone: `Σ_{i<k} C(2i, i)/4^i / k` (Kuhn–Struik), about
/// `√(2/πk)` for large `k`.
fn batch_law(k: usize) -> f64 {
    let mut term = 1.0f64;
    let mut sum = 0.0f64;
    for i in 0..k {
        sum += term;
        // C(2i+2, i+1)/4^{i+1} = C(2i, i)/4^i · (2i+1)/(2i+2)
        term *= (2 * i + 1) as f64 / (2 * i + 2) as f64;
    }
    sum / k.max(1) as f64
}

fn mean_sd(v: &[f64]) -> (f64, f64) {
    let n = v.len() as f64;
    if v.is_empty() {
        return (f64::NAN, f64::NAN);
    }
    let m = v.iter().sum::<f64>() / n;
    let var = if v.len() > 1 {
        v.iter().map(|x| (x - m).powi(2)).sum::<f64>() / (n - 1.0)
    } else {
        0.0
    };
    (m, var.sqrt())
}

fn batch(args: &RhoArgs, json_only: bool) -> Result<Value, String> {
    let mut curves = Vec::new();
    for spec in &args.batch_koblitz {
        let (a, n) = spec
            .split_once('/')
            .and_then(|(a, n)| Some((a.trim().parse::<u8>().ok()?, n.trim().parse::<u32>().ok()?)))
            .ok_or_else(|| format!("a Koblitz curve is `a/n`, e.g. 0/41; got {spec:?}"))?;
        if a > 1 || !(5..=62).contains(&n) {
            return Err(format!("no Koblitz curve K_{a} / GF(2^{n}) here"));
        }
        let inst =
            koblitz_instance(a, n).ok_or_else(|| format!("K_{a} / GF(2^{n}) is not usable"))?;
        curves.push((a, inst));
    }
    if args.batch_sizes.is_empty() || args.batch_sizes.contains(&0) {
        return Err("batch sizes must be positive".into());
    }
    let mut out = Vec::new();
    let mut md = String::from(
        "| curve | log₂ r | A | k | batches | S per target | sd | walk S per target | over k = 1 | batch law | floor S (one target) | own trail | earlier trail | ok |\n|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|\n",
    );
    for (a, inst) in &curves {
        let (n, r) = (inst.n, inst.r);
        let bg = BinaryGroup(&inst.fast);
        let floor = generic_floor_s(2.0 * n as f64);
        if !json_only {
            eprintln!(
                "  {}: r = {r} (2^{:.2}), A = {}",
                inst.name,
                (r as f64).log2(),
                2 * n
            );
        }
        let mut sizes = Vec::new();
        let mut single_mean = None;
        for &k in &args.batch_sizes {
            let mut runs = Vec::new();
            let mut s_values = Vec::new();
            let mut walk_values = Vec::new();
            let (mut own, mut earlier) = (0u64, 0u64);
            let mut all_ok = true;
            for b in 0..args.batches {
                let tseed = derive(args.seed, &[u64::from(*a), n as u64, k as u64, b as u64, 1]);
                let wseed = derive(args.seed, &[u64::from(*a), n as u64, k as u64, b as u64, 2]);
                let mut rng = StdRng::seed_from_u64(tseed);
                let planted: Vec<u64> = (0..k).map(|_| rng.gen_range(1..r)).collect();
                let mut ops = GroupOps::default();
                let targets: Vec<_> = planted
                    .iter()
                    .map(|&d| bg.mul(&mut ops, inst.generator, d))
                    .collect();
                let res = signed_frobenius_rho_batch(inst, &targets, wseed)
                    .ok_or("not a Koblitz instance")?;
                let ok = res
                    .per_target
                    .iter()
                    .zip(&planted)
                    .all(|(t, &d)| t.verified && t.recovered == Some(d));
                all_ok &= ok;
                own += res.counters["solved_on_own_trail"];
                earlier += res.counters["solved_on_an_earlier_trail"];
                s_values.push(res.s_per_target);
                walk_values.push(res.s_walk_per_target);
                if !json_only {
                    eprintln!(
                        "    k = {k:>2} batch {b:>2}: S/target {:.4}, {} of {k} verified, {:.1} s",
                        res.s_per_target,
                        res.per_target.iter().filter(|t| t.verified).count(),
                        res.wall_ns as f64 / 1e9
                    );
                }
                runs.push(json!({
                    "batch": b, "target_seed": tseed, "walk_seed": wseed, "planted": planted,
                    "all_verified": ok, "gae": res.gae, "setup_gae": res.setup_ops.gae(),
                    "s_per_target": res.s_per_target, "s_walk_per_target": res.s_walk_per_target,
                    "wall_ms": res.wall_ns as f64 / 1e6, "counters": res.counters,
                    "per_target": res.per_target.iter().zip(&planted).map(|(t, &d)| json!({
                        "planted": d, "recovered": t.recovered, "verified": t.verified && t.recovered == Some(d),
                        "solved_by": t.solved_by, "gae": t.gae, "group_ops": t.group_ops, "steps": t.steps,
                        "walks": t.walks, "distinguished_points": t.distinguished_points,
                        "wall_ms": t.wall_ns as f64 / 1e6,
                    })).collect::<Vec<_>>(),
                }));
            }
            let (mean, sd) = mean_sd(&s_values);
            let (walk_mean, _) = mean_sd(&walk_values);
            if k == 1 {
                single_mean = Some(mean);
            }
            let over_one = single_mean.map(|s1| mean / s1);
            md.push_str(&format!(
                "| {} | {:.2} | {} | {k} | {} | {} | {} | {} | {} | {:.3} | {:.4} | {own} | {earlier} | {} |\n",
                inst.name,
                (r as f64).log2(),
                2 * n,
                args.batches,
                fmt(mean),
                fmt(sd),
                fmt(walk_mean),
                over_one.map_or("—".into(), fmt),
                batch_law(k),
                floor,
                if all_ok { "✓" } else { "✗" },
            ));
            sizes.push(json!({
                "k": k, "batches": args.batches, "mean_s_per_target": mean, "sd_s_per_target": sd,
                "mean_s_walk_per_target": walk_mean, "per_target_over_k1": over_one,
                "batch_law": batch_law(k), "solved_on_own_trail": own, "solved_on_an_earlier_trail": earlier,
                "all_verified": all_ok, "runs": runs,
            }));
        }
        out.push(json!({
            "regime": "koblitz", "instance": inst.name, "a": a, "n": n, "r": r, "log2_r": (r as f64).log2(),
            "cofactor": inst.cofactor, "automorphisms": 2 * n, "floor_s_single": floor,
            "curve": inst.describe(), "exclusions": binary_exclusions(inst), "sizes": sizes,
        }));
    }
    let all_verified = out.iter().all(|c| {
        c["sizes"]
            .as_array()
            .is_some_and(|s| s.iter().all(|x| x["all_verified"] == true))
    });
    if !json_only {
        eprintln!("\n{md}");
    }
    Ok(json!({
        "schema_version": 1,
        "operation": "rho-batch",
        "status": if all_verified && !out.is_empty() { "complete" } else { "incomplete" },
        "what_this_is": "Batch Pollard rho (Kuhn-Struik) on Koblitz curves: k targets solved in sequence by the tuned walk on the signed-Frobenius classes (A = 2n), jumps in G only, one distinguished-point table shared by the batch, so a later target's walk can finish on an earlier target's trail. S per target = the batch's group-addition equivalents (the shared jump table, each target's start stride, starts, walks and verification) / (k sqrt r). Every target is fresh and its recovered logarithm is checked against the planted one.",
        "what_this_is_not": [
            "not an index-calculus result: no relation is collected here",
            "not the price of a step: canonicalisations are counted (canonicalisations_uncharged) and not charged, as in every rho count in the ledger",
            "not a wall-clock benchmark: wall time is a practicality note"
        ],
        "config": {"batch_koblitz": args.batch_koblitz, "batch_sizes": args.batch_sizes, "batches": args.batches,
                   "seed": args.seed, "walk": "RhoWalk::negation() shape on SignedFrobeniusClasses; per-target budget rho_cap(r, 64)"},
        "all_verified": all_verified,
        "curves": out,
        "markdown": md,
    }))
}

pub fn run(args: RhoArgs, json_only: bool) -> Result<Value, String> {
    if let Some(path) = &args.reprice {
        return reprice(path, &args, json_only);
    }
    if !args.batch_koblitz.is_empty() {
        return batch(&args, json_only);
    }
    if args.prime_bits.is_empty()
        && args.char2_degrees.is_empty()
        && args.koblitz_degrees.is_empty()
    {
        return Err("give --prime-bits, --char2-degrees and/or --koblitz-degrees, --batch-koblitz a/n, or --reprice FILE".into());
    }
    ladder(&args, json_only)
}
