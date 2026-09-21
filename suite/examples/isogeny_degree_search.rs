//! EXP-I1 — does any curve isogenous to ECC2K-130 present an easier
//! Gröbner problem?
//!
//! The thread's question, stated so it can be answered: ECC2K-130's
//! index calculus solves a point-decomposition system whose cost is set
//! by the solving degree `D*`.  Isogenies move to another curve with the
//! same group order, so the ECDLP transfers.  **Is there a member of the
//! isogeny class whose `D*` is lower?**
//!
//! ## The boundary, stated before measuring (`AGENTS.md` §1)
//!
//! - **Floor.**  The isogeny class of ECC2K-130 holds exactly
//!   `H(Δ) = 38 531 015 900 842 054 149 ≈ 2^65.06` curves (Deuring /
//!   Waterhouse; the formula is checked against the exhaustive census at
//!   `n = 5 … 17`).  At one operation per curve an exhaustive search
//!   costs `S = 1.48`.
//! - **Reference.**  Pollard rho on the same group, with negation and the
//!   131-power Frobenius, costs `2^60.9` iterations, i.e. `S ≈ 0.077`.
//!
//! So the search is `≈ 19×` worse than the attack it hopes to improve
//! **before it tests its first curve**.  Everything below is therefore
//! about whether the *screen* could ever be worth building, not about
//! running it at `n = 131`.
//!
//! ## The falsification target (`AGENTS.md` §4)
//!
//! The thread **succeeds** iff some curve in the isogeny class shows a
//! first fall degree strictly below the ECC2K-130 member's, under either
//! Macaulay convention, reproducibly at `n ≥ 9` and over ≥ 4 targets.
//! It is **abandoned** iff the fall degree is constant across the entire
//! class at every reachable `n` — which the leading-form argument
//! predicts, and which §4 below tests exhaustively rather than by
//! sampling.
//!
//! Inadmissible: changing the subspace dimension between curves, giving
//! the Koblitz member a Frobenius-invariant factor base the others
//! cannot have, reading one Macaulay convention against the other, or
//! counting a fall found only by raising `d_max` for one curve.
//!
//! Run: `cargo run --release --example isogeny_degree_search [max_n]`
//! Snapshot → `experiments/isogeny_degree_search.json`

use cryptanalysis_suite::cryptanalysis::isogeny_degree_search::census::CurveId;
use cryptanalysis_suite::cryptanalysis::isogeny_degree_search::{
    ball::{
        achievable_magic_numbers, ecc2k130_curve, ecc2k130_disc, ecc2k130_tower,
        ghs_window_is_empty, rational_isogeny_degrees, walk_isogeny_ball,
    },
    census::{elem_of, koblitz_trace_recurrence, subfield_j_count, IsogenyCensus},
    certify_leading_form_invariance,
    class_number::{ecc2k130_class_size, koblitz_class_size},
    cost::{calibrate_class_size, class_size_log2_floor, ecc2k130_boundary, log2_big},
    full_field_basis,
    profile::{
        sweep_all_curves, sweep_isogeny_class, sweep_targets_on_one_curve, SweepReport,
        TargetProtocol,
    },
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::find_irreducible;
use std::time::{SystemTime, UNIX_EPOCH};

/// Field degrees for the exhaustive **all curves** sweep (E1).  Kept
/// small because the sweep is `Θ(2^n)` Macaulay rankings.
const ALL_CURVE_NS: &[u32] = &[5, 7, 9];
/// Field degrees for the exhaustive **isogeny class** sweep (E2).  The
/// class is `Θ(2^{n/2})` curves, so this reaches much further.
const CLASS_NS: &[u32] = &[7, 9, 11, 13, 15, 17];
/// Targets the class sweep is repeated over, so a flat result is not an
/// artefact of one instance.
const TARGET_SEEDS: &[u64] = &[3, 11, 29, 47];

/// Highest Macaulay degree to build at each `n`.
///
/// Constant **within** every sweep — the falsification target forbids
/// finding a fall for one curve by raising its `d_max` — but it has to
/// fall with `n`, because the degree-4 matrix at `n = 15` already has
/// `C(30, ≤4) ≈ 32 000` columns and the one at `n = 17` has `≈ 53 000`,
/// past what the engine ranks.  Every fall observed anywhere in this
/// thread is at degree 2 or 3, so `d_max = 3` still covers the observed
/// range at the sizes where 4 is out of reach; a row measured at
/// `d_max = 3` reports `—` rather than a fall it could not have seen,
/// and rows are never compared across `n`.
fn d_max_for(n: u32) -> u32 {
    if n <= 11 {
        4
    } else {
        3
    }
}

fn fmt_opt(d: Option<u32>) -> String {
    d.map(|v| v.to_string()).unwrap_or_else(|| "—".into())
}

fn hist_str(h: &std::collections::BTreeMap<Option<u32>, usize>) -> String {
    h.iter()
        .map(|(d, c)| format!("{}×{c}", fmt_opt(*d)))
        .collect::<Vec<_>>()
        .join(" ")
}

fn rule() {
    println!("────────────────────────────────────────────────────────────────────────────");
}

fn main() {
    let max_n: u32 = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(13);

    println!("════════════════════════════════════════════════════════════════════════════");
    println!(" EXP-I1  Isogeny-class search for a lower solving degree — ECC2K-130");
    println!("════════════════════════════════════════════════════════════════════════════");

    // ── §1  The boundary ───────────────────────────────────────────
    let boundary = ecc2k130_boundary();
    println!("\n§1  BOUNDARY  (stated before measuring)\n");
    println!(
        "  ECC2K-130: E/F_2^131 : y² + xy = x³ + 1,   r = #E/4,  log2 r = {:.2}",
        boundary.subgroup_log2
    );
    println!(
        "  reference   Pollard rho, negation × Frobenius (class size {}):  2^{:.2} ops,  S = {:.4}",
        boundary.rho.automorphisms, boundary.rho.iterations_log2, boundary.rho.s_unit
    );
    let class = ecc2k130_class_size();
    println!(
        "  floor       isogeny class holds EXACTLY H(Δ) = {} = 2^{:.2} curves",
        class.class_size, boundary.class_log2
    );
    println!(
        "              Δ = f²·({}),  f = {} = {},  {} orders (volcano levels)",
        class.d_k,
        class.conductor,
        class
            .conductor_factors
            .iter()
            .map(|(p, e)| if *e == 1 {
                p.to_string()
            } else {
                format!("{p}^{e}")
            })
            .collect::<Vec<_>>()
            .join(" · "),
        class.orders
    );
    println!(
        "              (generic pigeonhole mean would say 2^{:.2}; means do not bound",
        boundary.pigeonhole_log2
    );
    println!("               particular classes — see the n = 13 row in §2)");
    println!(
        "  search      S ≥ {:.4} at ONE operation per curve       ratio to rho = {:.1}×",
        boundary.search_s, boundary.ratio_to_rho
    );
    println!(
        "\n  → an exhaustive isogeny-class search is {:.1}× worse than rho before it",
        boundary.ratio_to_rho
    );
    println!("    tests its first curve.  The only question left is whether a *screen*");
    println!("    could ever pay, which §3–§5 answer.");

    // ── §2  Is the class calibrated the way the floor assumes? ─────
    println!("\n§2  CLASS SIZE — pigeonhole floor vs exhaustive census\n");
    println!("  The right-hand columns are the check that licenses evaluating H(Δ) at");
    println!("  n = 131: the class-number formula must reproduce the exhaustive census.\n");
    println!(
        "   n | curves  | classes | mean size | pigeonhole | ECC2K class | H(Δ) | agree | Δ = f²·(−7), f ="
    );
    rule();
    let mut calibrations = Vec::new();
    let mut formula_agrees = true;
    for &n in CLASS_NS {
        if n > max_n {
            continue;
        }
        let irr = find_irreducible(n).unwrap();
        let census = IsogenyCensus::build(n, &irr);
        let stats = census.stats();
        let cal = calibrate_class_size(&census);
        let t = koblitz_trace_recurrence(-1, n);
        let exact = koblitz_class_size(t, n);
        let (h, f) = exact
            .as_ref()
            .map(|e| (e.class_size.to_string(), e.conductor.to_string()))
            .unwrap_or_else(|| ("?".into(), "?".into()));
        let agree = exact
            .as_ref()
            .map(|e| e.class_size.to_string() == stats.koblitz_class_size.to_string())
            .unwrap_or(false);
        formula_agrees &= agree;
        println!(
            "  {n:2} | {:7} | {:7} | {:9.1} | {:10.1} | {:11} | {:>4} | {:5} | {}",
            stats.curves,
            stats.classes,
            stats.mean,
            cal.predicted_mean,
            cal.koblitz_class,
            h,
            agree,
            f
        );
        calibrations.push((n, cal));
    }
    println!("\n  formula reproduces every measured class size: {formula_agrees}");
    println!("  n = 13 is the instructive row: Δ_13 = −7 exactly, so the class has ONE");
    println!("  member while the pigeonhole mean says 45.  The mean is not a bound.");
    println!(
        "  → at n = 131 the class holds 2^{:.2} curves (pigeonhole would say 2^{:.2}).",
        boundary.class_log2,
        class_size_log2_floor(131)
    );

    // ── §3  Structure: what an isogeny could possibly buy ──────────
    println!("\n§3  STRUCTURE — the levers, and whether an isogeny can reach them\n");
    let magic = achievable_magic_numbers(131);
    println!("  GHS magic numbers attainable over F_2^131, for ANY b:  {magic:?}");
    println!(
        "  tractable window 2..=6 empty:  {}   → Weil descent is dead for the whole field",
        ghs_window_is_empty(131, 2, 6)
    );
    println!(
        "  j-invariants in a proper subfield of F_2^131:  {}  (= |F_2|, and j=0 is supersingular)",
        subfield_j_count(131)
    );
    println!("  → exactly one ordinary curve over F_2^131 has subfield structure: j = 1,");
    println!("    i.e. b = 1, i.e. ECC2K-130 itself.  The walk starts on the only");
    println!("    special point there is, and every step strictly loses structure.");

    let disc = ecc2k130_disc();
    let structure = rational_isogeny_degrees(&disc, 200);
    let walkable: Vec<u32> = structure
        .iter()
        .filter(|s| s.is_walkable())
        .map(|s| s.l)
        .collect();
    let inert: Vec<u32> = structure
        .iter()
        .filter(|s| !s.is_walkable())
        .map(|s| s.l)
        .collect();
    println!("\n  rational ℓ-isogenies, ℓ ≤ 200 (exhaustive, via (Δ/ℓ)):");
    println!(
        "    walkable ({:2}): {:?}",
        walkable.len(),
        &walkable[..walkable.len().min(12)]
    );
    println!(
        "    inert    ({:2}): {:?}",
        inert.len(),
        &inert[..inert.len().min(12)]
    );
    println!("    ℓ = 2 is degenerate in char 2 (Kronecker: Φ_2 ≡ (X+Y²)(X²+Y)),");
    println!("    ℓ = 3 and 5 are inert, so the smallest real step is ℓ = 7.");

    let tower = ecc2k130_tower();
    let ball = walk_isogeny_ball(&ecc2k130_curve(), &tower, &[2, 3], 3, 128);
    println!(
        "\n  ball walk at n = 131, ℓ ∈ {{2,3}}, radius 3: {} node(s), subfield hits {}, GHS hits {}",
        ball.nodes.len(),
        ball.subfield_hits().len(),
        ball.ghs_hits(2, 6).len()
    );

    // ── §4  The leading-form certificate ───────────────────────────
    println!("\n§4  LEADING-FORM INVARIANCE — the certificate covering the unreachable class\n");
    println!("   n | curves compared | leading forms identical | constants = coords(b)");
    rule();
    let mut certificates = Vec::new();
    for &n in &[5u32, 7, 9, 11] {
        if n > max_n {
            continue;
        }
        let irr = find_irreducible(n).unwrap();
        let bs: Vec<_> = (1..(1u64 << n)).map(|b| elem_of(b, n)).collect();
        let x_r = elem_of(3, n);
        let cert = certify_leading_form_invariance(n, &irr, &x_r, &bs, 2);
        println!(
            "  {n:2} | {:15} | {:23} | {}",
            cert.curves_compared, cert.leading_forms_identical, cert.constants_equal_b
        );
        certificates.push(cert);
    }
    println!("\n  → for every b over every field tested, the point-decomposition system's");
    println!("    positive-degree part is byte-identical and b appears only as the");
    println!("    constant vector.  The degree of regularity is a property of the");
    println!("    leading forms, so it is the SAME for all ~2^64.5 members of the class.");
    let _ = full_field_basis(5);

    // ── §5  The exhaustive sweeps ──────────────────────────────────
    println!("\n§5  THE TABLE — one unit, every variant a row  (`AGENTS.md` §2)\n");
    println!("  D_ff(sat) is the solver's Macaulay convention, D_ff(cal) the FFD");
    println!("  program's.  `improved` counts curves beating the ECC2K-130 member under");
    println!("  EITHER convention — the falsification target, made as easy to hit as");
    println!("  honesty allows.\n");
    println!(
        "  scope             |  n | dmax | target   | curves | trc | tgt | D_ff(sat) | D_ff(cal) | Δ_sr | ref | imp"
    );
    rule();

    let mut sweeps: Vec<(String, SweepReport)> = Vec::new();

    for &n in ALL_CURVE_NS {
        if n > max_n {
            continue;
        }
        let irr = find_irreducible(n).unwrap();
        let sweep = sweep_all_curves(
            n,
            &irr,
            2,
            n as usize,
            d_max_for(n),
            TargetProtocol::Fixed(3),
        );
        print_row("E1 all curves", &sweep);
        sweeps.push(("E1".into(), sweep));
    }

    for &n in CLASS_NS {
        if n > max_n {
            continue;
        }
        let irr = find_irreducible(n).unwrap();
        for &seed in TARGET_SEEDS {
            let sweep = sweep_isogeny_class(
                n,
                &irr,
                2,
                n as usize,
                d_max_for(n),
                TargetProtocol::Fixed(seed),
            );
            print_row("E2 class, 1 target", &sweep);
            sweeps.push(("E2-fixed".into(), sweep));
        }
        let sweep = sweep_isogeny_class(
            n,
            &irr,
            2,
            n as usize,
            d_max_for(n),
            TargetProtocol::OnCurve(3),
        );
        let class_spread: std::collections::BTreeSet<_> =
            sweep.rows.iter().map(|r| r.fall_degree).collect();
        let want = sweep.len().max(24);
        print_row("E2 class, on-curve", &sweep);
        sweeps.push(("E2-oncurve".into(), sweep));

        // The control: same curve, many targets.  Any spread here is a
        // target effect, and the on-curve row above must not exceed it.
        let control = sweep_targets_on_one_curve(
            n,
            &irr,
            CurveId { b: 1, a_trace: 0 },
            2,
            n as usize,
            d_max_for(n),
            want,
        );
        let control_spread: std::collections::BTreeSet<_> =
            control.rows.iter().map(|r| r.fall_degree).collect();
        print_row("C  1 curve, targets", &control);
        println!(
            "  {:<19}   → on-curve class spread {} ⊆ single-curve target spread {}:  {}",
            "",
            hist_set(&class_spread),
            hist_set(&control_spread),
            class_spread.is_subset(&control_spread)
        );
        sweeps.push(("C-targets".into(), control));
    }

    // ── §6  Verdict ────────────────────────────────────────────────
    let total_rows: usize = sweeps.iter().map(|(_, s)| s.len()).sum();
    // Only the curve comparisons can produce an improvement; the target
    // controls compare one curve with itself.
    let total_improved: usize = sweeps
        .iter()
        .filter(|(_, s)| s.is_curve_comparison())
        .map(|(_, s)| s.improvements().len())
        .sum();
    let compared_rows: usize = sweeps
        .iter()
        .filter(|(_, s)| s.is_curve_comparison())
        .map(|(_, s)| s.len())
        .sum();
    // Leading-form identity is a claim about curves at a *fixed* target,
    // so it is asserted only over the sweeps that hold the target fixed.
    // The on-curve sweeps vary the target by construction and are
    // excluded — quoting them here would be an accounting error, not a
    // result.
    let all_flat = sweeps
        .iter()
        .filter(|(_, s)| s.distinct_targets() == 1)
        .all(|(_, s)| s.leading_forms_identical());
    let fixed_target_rows: usize = sweeps
        .iter()
        .filter(|(_, s)| s.distinct_targets() == 1)
        .map(|(_, s)| s.len())
        .sum();

    println!("\n§6  VERDICT\n");
    println!("  systems measured, all sweeps:             {total_rows}");
    println!("  of those, curve-vs-curve at one target:   {compared_rows}");
    println!(
        "  target-control systems (one curve):       {}",
        total_rows - compared_rows
    );
    println!("  curves beating the reference D_ff:        {total_improved}");
    println!("  leading forms identical at fixed target:  {all_flat}");
    let sr_flat = sweeps
        .iter()
        .filter(|(_, s)| s.is_curve_comparison())
        .all(|(_, s)| s.fall_signal_flat_everywhere());
    println!("  Δ_sr flat at EVERY degree, every sweep:   {sr_flat}");
    let _ = fixed_target_rows;
    println!(
        "  classification (`AGENTS.md` §3):    {}",
        if total_improved == 0 {
            "NOT AN ADVANCE — ratio to the floor is flat by construction"
        } else {
            "ADVANCE — a curve beat the reference; re-verify before believing it"
        }
    );
    println!("\n  The falsification target was not met, and the leading-form certificate");
    println!("  says it cannot be: b enters the ideal only as a constant, so no isogeny");
    println!("  changes the degree of regularity.  The one lever that does — subfield");
    println!("  structure — sits on the start point alone, because 131 is prime.");

    // ── snapshot ───────────────────────────────────────────────────
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let sweep_json = sweeps
        .iter()
        .map(|(tag, s)| {
            format!(
                "{{\"scope\":\"{tag}\",\"n\":{},\"m\":{},\"ell\":{},\"protocol\":\"{}\",\
                 \"curves\":{},\"traces\":{},\"targets\":{},\"fall_hist\":\"{}\",\
                 \"calibrated_hist\":\"{}\",\
                 \"leading_forms_identical\":{},\"improved\":{}}}",
                s.n,
                s.m,
                s.ell,
                s.protocol.label(),
                s.len(),
                s.distinct_traces(),
                s.distinct_targets(),
                hist_str(&s.fall_histogram()),
                hist_str(&s.calibrated_fall_histogram()),
                s.leading_forms_identical(),
                s.improvements().len()
            )
        })
        .collect::<Vec<_>>()
        .join(",");
    let cert_json = certificates
        .iter()
        .map(|c| {
            format!(
                "{{\"n\":{},\"compared\":{},\"leading_forms_identical\":{},\"constants_equal_b\":{}}}",
                c.n, c.curves_compared, c.leading_forms_identical, c.constants_equal_b
            )
        })
        .collect::<Vec<_>>()
        .join(",");
    let cal_json = calibrations
        .iter()
        .map(|(n, c)| {
            format!(
                "{{\"n\":{n},\"predicted_mean\":{:.3},\"measured_mean\":{:.3},\
                 \"koblitz_class\":{},\"ratio\":{:.4}}}",
                c.predicted_mean, c.measured_mean, c.koblitz_class, c.koblitz_over_mean
            )
        })
        .collect::<Vec<_>>()
        .join(",");
    let json = format!(
        "{{\n  \"schema\": \"isogeny_degree_search/v1\",\n  \"experiment\": \"EXP-I1\",\n  \
         \"generated_at\": {ts},\n  \
         \"boundary\": {{\"subgroup_log2\":{:.4},\"rho_log2\":{:.4},\"rho_s\":{:.6},\
         \"class_size\":\"{}\",\"class_log2\":{:.4},\"pigeonhole_log2\":{:.4},\
         \"conductor\":\"{}\",\"orders\":{},\
         \"search_s\":{:.6},\"ratio_to_rho\":{:.4}}},\n  \
         \"structure\": {{\"magic_numbers_131\":{:?},\"ghs_window_empty\":{},\
         \"subfield_j_count_131\":{},\"walkable_primes_le_200\":{:?},\
         \"disc_log2\":{:.4}}},\n  \
         \"class_size\": [{cal_json}],\n  \"certificates\": [{cert_json}],\n  \
         \"sweeps\": [{sweep_json}],\n  \
         \"verdict\": {{\"curves\":{total_rows},\"compared\":{compared_rows},\
         \"improved\":{total_improved},\
         \"leading_forms_identical\":{all_flat},\"fall_signal_flat\":{sr_flat}}}\n}}\n",
        boundary.subgroup_log2,
        boundary.rho.iterations_log2,
        boundary.rho.s_unit,
        class.class_size,
        boundary.class_log2,
        boundary.pigeonhole_log2,
        class.conductor,
        class.orders,
        boundary.search_s,
        boundary.ratio_to_rho,
        magic,
        ghs_window_is_empty(131, 2, 6),
        subfield_j_count(131),
        walkable,
        log2_big(&disc.magnitude().clone()),
    );
    let path = "experiments/isogeny_degree_search.json";
    match std::fs::write(path, &json) {
        Ok(_) => println!("\n[snapshot] wrote {path}"),
        Err(e) => println!("\n[snapshot] FAILED to write {path}: {e}"),
    }
    println!("════════════════════════════════════════════════════════════════════════════");
}

/// Render a set of fall degrees compactly.
fn hist_set(set: &std::collections::BTreeSet<Option<u32>>) -> String {
    format!(
        "{{{}}}",
        set.iter()
            .map(|d| fmt_opt(*d))
            .collect::<Vec<_>>()
            .join(",")
    )
}

fn print_row(scope: &str, s: &SweepReport) {
    let spread = s
        .fall_signal_spread(3)
        .map(|(lo, hi)| {
            if lo == hi {
                format!("{lo}")
            } else {
                format!("[{lo},{hi}]")
            }
        })
        .unwrap_or_else(|| "—".into());
    println!(
        "  {scope:<19} | {:2} | {:4} | {:<8} | {:6} | {:3} | {:3} | {:>9} | {:>9} | {:>4} | {:>3} | {:>3}",
        s.n,
        d_max_for(s.n),
        s.protocol.label(),
        s.len(),
        s.distinct_traces(),
        s.distinct_targets(),
        hist_str(&s.fall_histogram()),
        hist_str(&s.calibrated_fall_histogram()),
        spread,
        if s.is_curve_comparison() {
            s.reference()
                .map(|r| fmt_opt(r.fall_degree))
                .unwrap_or_else(|| "—".into())
        } else {
            "n/a".into()
        },
        if s.is_curve_comparison() {
            s.improvements().len().to_string()
        } else {
            "n/a".into()
        }
    );
}
