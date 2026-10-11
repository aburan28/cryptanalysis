//! EXP-R6 — lever **L5**: the curve-side lever.  Can an isogeny make the
//! Gröbner basis easier?
//!
//! Levers L1–L4 all change the *presentation* of one curve's decomposition
//! ideal.  L5 changes the curve.  It is legitimate because the ECDLP
//! transports along an isogeny of degree coprime to the subgroup order, so
//! an attacker may solve on any curve in the isogeny class of ECC2K-130 and
//! pull the answer back — the Galbraith–Hess–Smart move, which worked for
//! Weil-descent genus, asked of the Gröbner solving degree instead.
//!
//! ## Boundaries, stated before measuring
//!
//! | # | Boundary | Kind | Value |
//! |---|---|---|---|
//! | **A** | the isogeny class has more vertices than ρ has group operations | floor (counting) | `2^65.06` vertices vs `2^60.81` ρ operations (`2^64.83` for ρ without automorphisms) |
//! | **B** | vertices reachable by a computable isogeny | floor (reachability) | `263` of `2^65.06`, i.e. `2^-56.9` of the class |
//! | **C** | the curve enters the descended system **below** the leading form | exact, algebraic | `d_reg` and fall-availability are constant on the class |
//! | **D** | the only measured `D*`-lowering mechanism (L1 subfield) needs a subfield | exact | `131` is prime; isogenies do not change the field |
//! | ref | the unmodified Koblitz curve, and `2^N` enumeration | reference | measured in the same unit below |
//!
//! Boundary C leaves exactly one surface: the **affine** refutation degree
//! `D*` (the degree at which `1` enters the Macaulay row space), which is a
//! property of the inhomogeneous system — and the curve controls precisely
//! the inhomogeneous part.  `D*` therefore does vary with the curve, and
//! this experiment measures whether that variation is a *curve* effect an
//! attacker can move to, or a *target* effect they cannot.
//!
//! ## Pre-registered gate G-R6
//!
//! Decided **at the largest measured `n`**, following the thread's existing
//! convention (G-R2: "killed if the gap is `≤ 0` at the largest size").
//!
//! *Supported* if some curve keeps a mean-`D*` margin `≥ 0.5` degrees over
//! the Koblitz curve on a **disjoint holdout** target set at every measured
//! `n`, **and** the between-curve variance of mean `D*` exceeds twice what
//! independent sampling from the pooled distribution predicts.
//!
//! *Killed* if, at the largest size, the holdout margin is `≤ 0` while the
//! selection margin is positive (a winner's curse) — or if the count of
//! curves holding the `D* = 2` floor across *every* target reaches zero, since
//! then no curve is uniformly easier whatever a dozen targets suggested.
//!
//! *Blocked* otherwise: a margin that is positive but shrinking.
//!
//! Run: `cargo run --release --example isogeny_class_search [seed]`
//! Snapshot → `experiments/isogeny_class_search.json`

use cryptanalysis_suite::binary_ecc::{F2mElement, IrreduciblePoly};
use cryptanalysis_suite::cryptanalysis::binary_isogeny::{
    find_roots_in_f2m, j_invariant, phi_l_mod2_in_x,
};
use cryptanalysis_suite::cryptanalysis::degree_reduction::{
    log2_enumeration_cost, log2_expected_cost, log2_macaulay_cost,
};
use cryptanalysis_suite::cryptanalysis::descent_expansion::enumerate_irreducibles;
use cryptanalysis_suite::cryptanalysis::ghs_descent::ECurve;
use cryptanalysis_suite::cryptanalysis::isogeny_class_search::*;
use num_bigint::BigInt;
use std::collections::BTreeMap;
use std::time::{SystemTime, UNIX_EPOCH};

const OMEGA: f64 = 2.807;
/// The 130-bit prime subgroup order of ECC2K-130.
const SUBGROUP_ORDER: f64 = 680564733841876926932320129493409985129f64;

/// Expected ρ iterations on a group of order `r` whose automorphism group has
/// order `m` and acts freely: the walk is on `r/m` classes, so the birthday
/// bound is `√(π(r/m)/2) = √(πr/2m)`.
///
/// Writing it once, parameterised by `m`, is deliberate.  `√(πr/4)` is *already*
/// `m = 2` (negation), so dividing that by `√(2·131)` applies negation twice and
/// understates ρ by half a bit — the error this function replaces.
fn log2_rho(m: f64) -> f64 {
    (std::f64::consts::PI * SUBGROUP_ORDER / (2.0 * m))
        .sqrt()
        .log2()
}

/// ECC2K-130's automorphism group: negation together with the 131 Frobenius
/// powers, so `m = 2 · 131 = 262`.
const RHO_AUT_ORDER: f64 = 262.0;

fn main() {
    let seed = std::env::args()
        .nth(1)
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(7);

    println!("════════════════════════════════════════════════════════════════");
    println!("EXP-R6 — lever L5: the curve-side (isogeny) lever");
    println!("seed={seed}  omega={OMEGA}");
    println!("════════════════════════════════════════════════════════════════");

    // ── Boundaries A and B: the class, exactly ──────────────────────
    println!("\n── Boundary A/B: the ECC2K-130 isogeny class, exactly ──");
    let class = koblitz_isogeny_class(131, 5_000_000);
    println!("   E: y² + xy = x³ + 1  over F_2^131,  j(E) = 1");
    println!("   t_131        = {}", class.trace);
    println!("   #E           = {}", class.order);
    println!(
        "   conductor c  = {}  ({} bits), fully factored: {}",
        class.conductor,
        class.conductor.bits(),
        class.fully_factored
    );
    print!("   c            =");
    for (i, (l, e)) in class.conductor_factors.iter().enumerate() {
        print!("{} {}^{}", if i == 0 { "" } else { " ·" }, l, e);
    }
    println!();
    println!(
        "   crater size  = h(-7) = {}  ⇒ E is the only maximal-order curve in its class",
        class.crater_size
    );
    println!(
        "   class size   = Σ_(f|c) h(O_f) = {}  = 2^{:.2}",
        class.class_size,
        class.log2_class_size()
    );
    let log2_rho_aut = log2_rho(RHO_AUT_ORDER);
    let log2_rho_plain = log2_rho(1.0);
    println!(
        "   ρ reference  = 2^{:.2} iterations, √(πr/2m) with m = 262 (negation × 131 Frobenius)",
        log2_rho_aut
    );
    println!(
        "                  2^{:.2} for plain ρ with no automorphisms (m = 1)",
        log2_rho_plain
    );
    println!(
        "   ⇒ enumerating the class costs 2^{:.2}× the automorphism-assisted ρ, and 2^{:.2}× plain ρ.",
        class.log2_class_size() - log2_rho_aut,
        class.log2_class_size() - log2_rho_plain
    );
    println!("     The sign is what Boundary A rests on, and it holds either way; the margin");
    println!("     against plain ρ is thin, so the boundary is reported with both.");

    println!("\n   per-prime volcano structure:");
    println!(
        "   {:>22} {:>6} {:>5} {:>11} {:>24}",
        "ℓ", "v_ℓ(c)", "(−7/ℓ)", "horizontal", "descending from crater"
    );
    for p in &class.primes {
        println!(
            "   {:>22} {:>6} {:>5} {:>11} {:>24}",
            p.ell.to_string(),
            p.depth,
            p.kronecker,
            p.horizontal_from_crater,
            p.descending_from_crater.to_string()
        );
    }
    println!(
        "   Horizontal isogenies act through Cl(O_K) = {}, so they return to E (j ↦ j).",
        class.crater_size
    );
    println!("   Descending ones exist only for ℓ | c — hence the next table.");

    println!("\n── Boundary B: what a degree budget actually reaches ──");
    println!(
        "   {:>18} {:>22} {:>10} {:>12} {:>11}",
        "degree budget", "vertices reached", "log2", "of class", "exhaustive?"
    );
    let mut reach_rows = Vec::new();
    for budget in [
        BigInt::from(100u32),
        BigInt::from(263u32),
        BigInt::from(1_000_000u32),
        "146505763881528721".parse::<BigInt>().unwrap(),
    ] {
        let r = class.reach_within_degree(&budget);
        println!(
            "   {:>18} {:>22} {:>10} {:>12} {:>11}",
            budget.to_string(),
            r.reachable.to_string(),
            format!("2^{:.1}", r.log2_reachable),
            format!("2^{:.1}", r.log2_fraction()),
            if r.exhaustive { "yes" } else { "no" }
        );
        reach_rows.push((budget.to_string(), r));
    }
    let feasible = class.reach_within_degree(&BigInt::from(1_000_000u32));
    println!(
        "\n   The blocked direction is ℓ = {}: kernel-polynomial degree 2^{:.1},",
        feasible.blocking_primes[0],
        feasible.log2_min_blocking_kernel_degree.unwrap()
    );
    println!(
        "   and √élu — the best known evaluation — still costs 2^{:.1} field operations,",
        feasible.log2_min_blocking_sqrt_velu.unwrap()
    );
    println!("   with its kernel points living in an extension of F_2^131 of degree | ℓ−1.");
    println!(
        "   ⇒ THE EXHAUSTIVE SEARCH OVER THE REACHABLE CLASS IS {} CURVES, AND IT TERMINATES.",
        feasible.reachable
    );

    // ── Boundary B, cross-checked a different way ───────────────────
    println!("\n── Boundary B cross-check: Φ_ℓ(X, j) over the real F_2^131 ──");
    println!("   Independent of the CM/conductor argument above: root-find the");
    println!("   modular polynomial mod 2 at j(E) = 1 and see what is adjacent.");
    let irr131 = IrreduciblePoly::deg_131();
    let e131 = ECurve::new(
        131,
        irr131.clone(),
        F2mElement::zero(131),
        F2mElement::one(131),
    );
    let j131 = j_invariant(&e131);
    let mut phi_rows = Vec::new();
    for l in [2u32, 3] {
        let poly = phi_l_mod2_in_x(l, &j131, 131, &irr131);
        let roots = find_roots_in_f2m(&poly, 131, &irr131);
        let only_self = roots.iter().all(|r| *r == j131);
        let predicted_trivial = class.ell_graph_is_trivial(&BigInt::from(l));
        println!(
            "   ℓ={l}: deg Φ_ℓ(X,j) = {:>2}, roots = {:?}  → {} (CM predicted trivial: {})",
            poly.degree().unwrap_or(0),
            roots
                .iter()
                .map(|r| r.to_biguint().to_string())
                .collect::<Vec<_>>(),
            if roots.is_empty() {
                "no ℓ-isogenous curve"
            } else if only_self {
                "only E itself"
            } else {
                "A NEW CURVE"
            },
            predicted_trivial
        );
        assert!(
            only_self && predicted_trivial,
            "ℓ={l}: modular polynomial disagrees with the CM prediction"
        );
        phi_rows.push((l, poly.degree().unwrap_or(0), roots.len(), only_self));
    }

    // ── Boundary C: the curve sits below the leading form ───────────
    println!("\n── Boundary C: does the curve reach the leading form? ──");
    println!("   Exact, per coefficient: descend S₃ for many curves at a fixed");
    println!("   factor base and target, and see which Boolean degrees move.");
    let mut witness_rows = Vec::new();
    for (n, l) in [(8u32, 4u32), (10, 5), (12, 6)] {
        let irr = first_irr(n);
        let x3 = elt((1u64 << l) + 1, n);
        let a6s: Vec<F2mElement> = (1u64..=64).map(|v| elt(v, n)).collect();
        let w = leading_form_witness(n, l, &irr, &x3, &a6s);
        println!(
            "   n={:>2} l={} vars={:>2} eqs={:>2}: {} curves compared, a₆ touches Boolean degrees {:?} of ≤{} → degree ≥1 identical: {}",
            n, l, w.num_vars, w.num_eqs, w.curves_compared, w.degrees_touched_by_a6, w.top_degree, w.degree_ge1_identical
        );
        assert!(w.degree_ge1_identical, "Boundary C failed at n={n}");
        witness_rows.push(w);
    }
    println!("   ⇒ d_reg (a Hilbert invariant of the leading forms) is CONSTANT on the class.");
    println!("     The affine refutation degree D* is not covered, and is measured next.");

    // ── The mechanism behind the D* variation ───────────────────────
    println!("\n── The mechanism: which curves refute at the D* = 2 floor ──");
    println!("   With f_i = h_i + c_i and S = {{λ : Σ λ_i h_i = 0}} (curve-independent),");
    println!("   Σ λ_i f_i = ⟨λ,c⟩ is constant for λ ∈ S, so D* = 2 ⟺ c ∉ S^⊥.");
    println!("   c is the coordinate vector of a₆, so the 'good' curves are the");
    println!("   complement of a subspace fixed BY THE TARGET, not by the curve.");
    println!(
        "\n   {:>8} {:>8} {:>8} {:>11} {:>12} {:>11} {:>11}",
        "n", "target", "dim S", "escaped", "refuted@2", "mismatches", "c = bits(a₆)"
    );
    let mut mech_rows = Vec::new();
    for (n, l) in [(8u32, 4u32), (10, 5)] {
        let irr = first_irr(n);
        for t in [(1u64 << l) + 1, (1u64 << l) + 5] {
            let row = syzygy_mechanism(n, l, 6, &irr, &elt(t, n));
            println!(
                "   {:>8} {:>8} {:>8} {:>11} {:>12} {:>11} {:>11}",
                n,
                row.target,
                row.leading_nullity,
                row.outside_perp,
                row.refuted_at_2,
                row.mismatches,
                row.constant_is_a6
            );
            assert_eq!(row.mismatches, 0, "the criterion must be exact");
            mech_rows.push((n, row));
        }
    }
    println!("   ⇒ the criterion is EXACT: zero disagreements with the solver, every curve.");

    // ── G-R6: is the curve the explanatory variable? ────────────────
    println!("\n── G-R6: exhaustive curve sweep with a disjoint holdout ──");
    println!("   Every curve over F_2^n — all 2^n − 1 values of a₆, a SUPERSET of");
    println!("   every isogeny class at that size, the Koblitz one included.");
    println!(
        "\n   {:>4} {:>3} {:>8} {:>9} {:>9} {:>7} {:>8} {:>8} {:>8} {:>8} {:>7}",
        "n",
        "l",
        "curves",
        "var ratio",
        "best a₆",
        "sel μ",
        "hold μ",
        "kob sel",
        "kob hold",
        "margin",
        "floor∩"
    );
    let mut effect_rows = Vec::new();
    for (n, l, t) in [(6u32, 3u32, 12u32), (8, 4, 12), (10, 5, 12)] {
        let irr = first_irr(n);
        let e = curve_effect_test(n, l, 7, t, t, &irr);
        println!(
            "   {:>4} {:>3} {:>8} {:>9.3} {:>9} {:>7.3} {:>8.3} {:>8.3} {:>8.3} {:>+8.3} {:>7}",
            e.n,
            e.l,
            e.curves,
            e.variance_ratio,
            e.best_a6,
            e.best_select_mean,
            e.best_holdout_mean,
            e.koblitz_select_mean,
            e.koblitz_holdout_mean,
            e.margin_holdout,
            e.curves_at_floor_both
        );
        effect_rows.push(e);
    }
    println!("   'margin' is the HOLDOUT margin (Koblitz − best-selected), the honest one.");
    println!("   'floor∩' counts curves at the D* = 2 floor on BOTH disjoint target sets.");

    // ── The decisive consequence: no uniformly good curve exists ────
    println!("\n── The consequence: is any curve on the floor for EVERY target? ──");
    println!("   The criterion above says the good set is the complement of a subspace");
    println!("   fixed by the TARGET. So a uniformly good curve would have to escape");
    println!("   S^⊥(x_R) for every x_R at once. If goodness were a curve property the");
    println!("   count would be flat in T; if it is a (curve, target) property it decays.");
    println!(
        "\n   {:>5} {:>4} {:>10} {:>20} {:>16} {:>14}",
        "n", "l", "curves", "on the floor ∀ target", "fraction", "Koblitz mean"
    );
    let mut survivor_rows = Vec::new();
    // `n = 10` carries two extra target counts: at `T = 64` a single curve
    // (`a₆ = 13`) is still on the floor, and reporting the decay without the
    // rows that retire it would leave a survivor on the page that is only a
    // small-sample artifact of the target count.
    for (n, l, grid) in [
        (8u32, 4u32, &[8u32, 16, 32, 48, 64][..]),
        (10, 5, &[8, 16, 32, 48, 64, 128, 256][..]),
    ] {
        let irr = first_irr(n);
        for &t in grid {
            let fs = uniform_floor_survivors(n, l, 7, t, &irr);
            // Name the survivors while there are few enough to name: the last
            // one to fall is the curve the thread's own caveat was about, and
            // a count alone would not show that.
            let named = if !fs.survivors.is_empty() && fs.survivors.len() <= 4 {
                format!("   a₆ = {:?}", fs.survivors)
            } else {
                String::new()
            };
            println!(
                "   {:>5} {:>4} {:>10} {:>20} {:>16.5} {:>14.3}{named}",
                format!("{n}"),
                l,
                fs.curves,
                format!("{} (T={})", fs.survivors.len(), t),
                fs.survivors.len() as f64 / fs.curves as f64,
                fs.koblitz_mean
            );
            survivor_rows.push((n, l, t, fs.survivors.len(), fs.curves, fs.koblitz_mean));
        }
    }
    for size in [8u32, 10] {
        let first_zero = survivor_rows
            .iter()
            .find(|(n, _, _, c, _, _)| *n == size && *c == 0)
            .map(|(_, _, t, _, _, _)| *t);
        match first_zero {
            Some(t) => println!(
                "   ⇒ at n={size} the count reaches ZERO by T={t}: no curve over the field is"
            ),
            None => println!("   ⇒ at n={size} some curve is still on the floor at every T tested"),
        }
    }
    println!("     on the floor for every target, so there is nothing to move to.");

    // ── The one table ───────────────────────────────────────────────
    println!("\n══ THE TABLE — one unit: log₂ operations for the decomposition solve ══");
    let (n_t, l_t, t_t) = (10u32, 5u32, 12u32);
    let irr_t = first_irr(n_t);
    let eff = curve_effect_test(n_t, l_t, 7, t_t, t_t, &irr_t);
    let vars = 2 * l_t;
    let eqs = n_t;
    let floor = log2_macaulay_cost(vars, eqs, 2, OMEGA);
    let enumeration = log2_enumeration_cost(vars, eqs);

    let hist_of = |a6: u64, targets_from: u32, count: u32| -> BTreeMap<u32, u32> {
        let base = 1u64 << l_t;
        let tg: Vec<F2mElement> = (0..count)
            .map(|i| elt(base + (targets_from + i) as u64, n_t))
            .collect();
        measure_curve(n_t, l_t, 7, &irr_t, &elt(a6, n_t), &tg).0
    };
    let kob_hold = hist_of(1, t_t, t_t);
    let best_sel = hist_of(eff.best_a6, 0, t_t);
    let best_hold = hist_of(eff.best_a6, t_t, t_t);

    let rows: Vec<(&str, f64, &str, &str)> = vec![
        (
            "floor — every cell at the D* = 2 Nullstellensatz floor",
            floor,
            "n/a",
            "floor",
        ),
        (
            "Koblitz curve a₆ = 1 (the baseline L5 moves away from)",
            log2_expected_cost(&kob_hold, vars, eqs, OMEGA),
            "yes",
            "reference",
        ),
        (
            "best curve selected on target set A, scored on A",
            log2_expected_cost(&best_sel, vars, eqs, OMEGA),
            "yes",
            "selection (biased)",
        ),
        (
            "the same curve, scored on the disjoint holdout B",
            log2_expected_cost(&best_hold, vars, eqs, OMEGA),
            "yes",
            "accounting",
        ),
        ("2^N enumeration of V × V", enumeration, "yes", "reference"),
    ];
    println!(
        "\n   {:<56} {:>10} {:>12} {:>8}  class",
        format!("variant (n={n_t}, l={l_t}, ω={OMEGA})"),
        "log₂ ops",
        "ratio/floor",
        "correct"
    );
    let mut table_rows = Vec::new();
    for (label, cost, correct, klass) in &rows {
        println!(
            "   {:<56} {:>10.2} {:>12} {:>8}  {}",
            label,
            cost,
            format!("2^{:+.2}", cost - floor),
            correct,
            klass
        );
        table_rows.push((label.to_string(), *cost, cost - floor, klass.to_string()));
    }

    // ── Verdict ─────────────────────────────────────────────────────
    // G-R6 is decided at the LARGEST measured size, following the thread's
    // existing convention (G-R2: "killed if the gap is ≤ 0 at the largest
    // size").  Sizes below it are reported but do not vote: a margin that
    // survives at n = 6 and dies at n = 10 is a small-size artifact, which is
    // the failure mode this gate exists to catch.
    let largest = effect_rows
        .iter()
        .max_by_key(|e| e.n)
        .expect("at least one operating point");
    let all_margins_clear = effect_rows.iter().all(|e| e.margin_holdout >= 0.5);
    let all_variance_real = effect_rows.iter().all(|e| e.variance_ratio >= 2.0);
    let survivors_reach_zero = survivor_rows
        .iter()
        .any(|(_, _, _, count, _, _)| *count == 0);
    let verdict = if all_margins_clear && all_variance_real {
        "SUPPORTED"
    } else if largest.margin_holdout <= 0.0 && largest.margin_select > 0.0 {
        // Winner's curse at the largest size: the selection manufactured a
        // margin that fresh targets destroyed.
        "KILLED"
    } else if survivors_reach_zero {
        // Even where a holdout margin survives, no curve holds the floor for
        // every target, so there is nothing for an attacker to move to.
        "KILLED"
    } else {
        "BLOCKED"
    };
    println!("\n── G-R6 verdict: {verdict} ──");
    for e in &effect_rows {
        println!(
            "   n={:>2}: selection margin {:+.3}, holdout margin {:+.3}, variance ratio {:.3}",
            e.n, e.margin_select, e.margin_holdout, e.variance_ratio
        );
    }
    println!("\n   Reading: the selection margin is positive by construction — picking");
    println!("   the minimum of a noisy statistic always looks like a win. The holdout");
    println!("   margin is what an attacker would actually get, and the variance ratio");
    println!("   says whether the curve explains anything at all.");

    write_json(
        seed,
        &class,
        &reach_rows,
        &phi_rows,
        &witness_rows,
        &mech_rows,
        &effect_rows,
        &survivor_rows,
        &table_rows,
        floor,
        verdict,
        log2_rho_aut,
        log2_rho_plain,
    );
}

fn first_irr(n: u32) -> IrreduciblePoly {
    enumerate_irreducibles(n, 1)
        .into_iter()
        .next()
        .expect("an irreducible of every small degree exists")
}

fn elt(v: u64, n: u32) -> F2mElement {
    let bits: Vec<u32> = (0..n).filter(|i| (v >> i) & 1 == 1).collect();
    F2mElement::from_bit_positions(&bits, n)
}

#[allow(clippy::too_many_arguments)]
fn write_json(
    seed: u64,
    class: &IsogenyClassStructure,
    reach: &[(String, ReachAccounting)],
    phi: &[(u32, usize, usize, bool)],
    witness: &[LeadingFormWitness],
    mech: &[(u32, MechanismRow)],
    effect: &[CurveEffectTest],
    survivors: &[(u32, u32, u32, usize, usize, f64)],
    table: &[(String, f64, f64, String)],
    floor: f64,
    verdict: &str,
    log2_rho: f64,
    log2_rho_plain: f64,
) {
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let mut s = String::new();
    s.push_str("{\n  \"schema\": \"isogeny_class_search/v1\",\n  \"experiment\": \"EXP-R6\",\n");
    s.push_str(&format!("  \"lever\": \"L5 curve-side (isogeny)\",\n  \"seed\": {seed},\n  \"generated_unix\": {ts},\n  \"omega\": {OMEGA},\n"));
    s.push_str(&format!("  \"verdict\": \"{verdict}\",\n"));
    s.push_str("  \"class\": {\n");
    s.push_str(&format!(
        "    \"n\": 131,\n    \"trace\": \"{}\",\n    \"order\": \"{}\",\n    \"conductor\": \"{}\",\n    \"fully_factored\": {},\n",
        class.trace, class.order, class.conductor, class.fully_factored
    ));
    s.push_str("    \"conductor_factors\": [");
    for (i, (l, e)) in class.conductor_factors.iter().enumerate() {
        s.push_str(&format!(
            "{}{{\"ell\": \"{}\", \"valuation\": {}}}",
            if i == 0 { "" } else { ", " },
            l,
            e
        ));
    }
    s.push_str("],\n");
    s.push_str(&format!(
        "    \"crater_size\": {},\n    \"class_size\": \"{}\",\n    \"log2_class_size\": {:.4},\n    \"log2_rho_reference\": {:.4},\n    \"rho_automorphism_order\": 262,\n    \"log2_rho_plain\": {:.4},\n    \"log2_class_over_rho\": {:.4},\n    \"log2_class_over_rho_plain\": {:.4}\n  }},\n",
        class.crater_size,
        class.class_size,
        class.log2_class_size(),
        log2_rho,
        log2_rho_plain,
        class.log2_class_size() - log2_rho,
        class.log2_class_size() - log2_rho_plain
    ));
    s.push_str("  \"reach\": [\n");
    for (i, (b, r)) in reach.iter().enumerate() {
        s.push_str(&format!(
            "    {{\"degree_budget\": \"{}\", \"reachable\": \"{}\", \"log2_reachable\": {:.4}, \"log2_fraction_of_class\": {:.4}, \"exhaustive\": {}}}{}\n",
            b, r.reachable, r.log2_reachable, r.log2_fraction(), r.exhaustive,
            if i + 1 == reach.len() { "" } else { "," }
        ));
    }
    s.push_str("  ],\n  \"modular_polynomial_crosscheck\": [\n");
    for (i, (l, d, nroots, only_self)) in phi.iter().enumerate() {
        s.push_str(&format!(
            "    {{\"ell\": {l}, \"phi_degree\": {d}, \"roots\": {nroots}, \"only_self\": {only_self}}}{}\n",
            if i + 1 == phi.len() { "" } else { "," }
        ));
    }
    s.push_str("  ],\n  \"leading_form_witness\": [\n");
    for (i, w) in witness.iter().enumerate() {
        s.push_str(&format!(
            "    {{\"n\": {}, \"l\": {}, \"vars\": {}, \"eqs\": {}, \"curves_compared\": {}, \"degrees_touched_by_a6\": {:?}, \"top_degree\": {}, \"degree_ge1_identical\": {}}}{}\n",
            w.n, w.l, w.num_vars, w.num_eqs, w.curves_compared, w.degrees_touched_by_a6, w.top_degree, w.degree_ge1_identical,
            if i + 1 == witness.len() { "" } else { "," }
        ));
    }
    s.push_str("  ],\n  \"mechanism\": [\n");
    for (i, (n, m)) in mech.iter().enumerate() {
        s.push_str(&format!(
            "    {{\"n\": {n}, \"target\": {}, \"dim_S\": {}, \"escaped_perp\": {}, \"refuted_at_2\": {}, \"mismatches\": {}, \"constant_is_a6\": {}, \"escape_density\": {:.6}}}{}\n",
            m.target, m.leading_nullity, m.outside_perp, m.refuted_at_2, m.mismatches, m.constant_is_a6, m.outside_perp_density,
            if i + 1 == mech.len() { "" } else { "," }
        ));
    }
    s.push_str("  ],\n  \"curve_effect\": [\n");
    for (i, e) in effect.iter().enumerate() {
        s.push_str(&format!(
            "    {{\"n\": {}, \"l\": {}, \"curves\": {}, \"targets_select\": {}, \"targets_holdout\": {}, \"pooled_mean\": {:.6}, \"pooled_var\": {:.6}, \"between_curve_var\": {:.6}, \"no_effect_var\": {:.6}, \"variance_ratio\": {:.6}, \"best_a6\": {}, \"best_select_mean\": {:.6}, \"best_holdout_mean\": {:.6}, \"koblitz_select_mean\": {:.6}, \"koblitz_holdout_mean\": {:.6}, \"margin_select\": {:.6}, \"margin_holdout\": {:.6}, \"curves_at_floor_select\": {}, \"curves_at_floor_holdout\": {}, \"curves_at_floor_both\": {}}}{}\n",
            e.n, e.l, e.curves, e.targets_select, e.targets_holdout, e.pooled_mean, e.pooled_var,
            e.between_curve_var, e.no_effect_var, e.variance_ratio, e.best_a6, e.best_select_mean,
            e.best_holdout_mean, e.koblitz_select_mean, e.koblitz_holdout_mean, e.margin_select,
            e.margin_holdout, e.curves_at_floor_select, e.curves_at_floor_holdout, e.curves_at_floor_both,
            if i + 1 == effect.len() { "" } else { "," }
        ));
    }
    s.push_str("  ],\n  \"uniform_floor_survivors\": [\n");
    for (i, (n, l, t, c, total, kob)) in survivors.iter().enumerate() {
        s.push_str(&format!(
            "    {{\"n\": {n}, \"l\": {l}, \"targets\": {t}, \"survivors\": {c}, \"curves\": {total}, \"fraction\": {:.8}, \"koblitz_mean\": {kob:.6}}}{}\n",
            *c as f64 / *total as f64,
            if i + 1 == survivors.len() { "" } else { "," }
        ));
    }
    s.push_str("  ],\n");
    s.push_str(&format!(
        "  \"table_floor_log2\": {floor:.4},\n  \"table\": [\n"
    ));
    for (i, (label, cost, ratio, klass)) in table.iter().enumerate() {
        s.push_str(&format!(
            "    {{\"variant\": \"{label}\", \"log2_ops\": {cost:.4}, \"log2_ratio_to_floor\": {ratio:.4}, \"class\": \"{klass}\"}}{}\n",
            if i + 1 == table.len() { "" } else { "," }
        ));
    }
    s.push_str("  ]\n}\n");

    let path = "experiments/isogeny_class_search.json";
    match std::fs::write(path, &s) {
        Ok(()) => println!("\nwrote {path}"),
        Err(e) => println!("\ncould not write {path}: {e}"),
    }
}
