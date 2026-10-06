//! End-to-end GHS / Hess Weil-descent demo.
//!
//! Build a toy binary trapdoor curve, run the full pipeline (isogeny
//! walk, descent, HCDLP, lift), and print the attack report.
//!
//! Run with: `cargo run --example ghs_attack_demo`

use cryptanalysis_suite::binary_ecc::{F2mElement, IrreduciblePoly};
use cryptanalysis_suite::cryptanalysis::binary_isogeny::{
    j_invariant, l_isogenous_neighbours, phi_l_mod2_in_x,
};
use cryptanalysis_suite::cryptanalysis::ec_trapdoor::{audit_curve, magic_number_full, FieldTower};
use cryptanalysis_suite::cryptanalysis::ec_trapdoor::{DescentRow, TrapdoorCurve};
use cryptanalysis_suite::cryptanalysis::ghs_descent::{descend_m2_abstract, ECurve, Pt};
use cryptanalysis_suite::cryptanalysis::ghs_full_attack::{
    format_report, run_full_attack, AttackOptions,
};
use num_bigint::BigUint;

fn banner(s: &str) {
    println!();
    println!("════════════════════════════════════════════════════════════════════");
    println!(" {}", s);
    println!("════════════════════════════════════════════════════════════════════");
}

fn main() {
    banner("GHS / Hess Weil-descent pipeline demo");
    println!(
        "
This demo walks through the four steps of the GHS / Hess attack on a
binary elliptic curve E/F_{{2^N}} that admits a Weil descent:

  1. Isogeny walk: explore the l-isogeny graph to find E' with the
     right magic number for descent.
  2. Descent: build the descended hyperelliptic curve C/F_{{2^l}}.
  3. HCDLP: solve discrete log on Jac(C)(F_{{2^l}}).
  4. Lift: transport the recovered scalar back to E.

We exercise each component at a scale where it actually runs.
"
    );

    // ── Scenario A: m=1 trapdoor (end-to-end recovery) ─────────────
    banner("Scenario A: m = 1 trapdoor on F_{2^6} = F_{(2^3)^2}");
    println!(
        "
Pick a 'w-curve' E/F_{{2^6}} whose b-coefficient lies in F_{{2^3}} ⊂ F_{{2^6}}.
The trapdoor: viewed via the (n=2, l=3) factorisation, E has magic
number m = 1, so the trace-map descent collapses E(F_{{2^6}}) into
E(F_{{2^3}}) — a much smaller group, where ECDLP is trivially solvable.
"
    );

    // F_{2^6}: x^6 + x + 1.
    let irr = IrreduciblePoly {
        degree: 6,
        low_terms: vec![0, 1],
    };
    let big_n = 6;
    let n = 2;
    let l = 3;
    let tower = FieldTower::new(big_n, n, l, irr.clone());
    // Find b ∈ F_{2^3} \ F_2.
    let mut b_pick = None;
    for candidate in 2u64..(1u64 << 6) {
        let cand = F2mElement::from_biguint(&BigUint::from(candidate), big_n);
        if tower.is_in_subfield(&cand, l) && !tower.is_in_subfield(&cand, 1) {
            b_pick = Some(cand);
            break;
        }
    }
    let b = b_pick.expect("subfield curve");
    let a = F2mElement::one(big_n);
    let tc_a = TrapdoorCurve {
        big_n,
        n,
        l,
        big_irr: irr.clone(),
        a: a.clone(),
        b: b.clone(),
        sqrt_b: tower.sqrt(&b),
        row: DescentRow::default(),
        full_audit: None,
    };
    println!(
        "  Curve E: y² + xy = x³ + 1·x² + ({:?})  over F_{{2^6}}",
        b.to_biguint()
    );
    println!("  b ∈ F_{{2^3}}: {}", tower.is_in_subfield(&b, l));
    let aud = audit_curve(big_n, &irr, &a, &b);
    println!("  Auditor table:");
    println!("    (n, l)    magic_m  genus  type_I");
    for row in &aud {
        println!(
            "    ({:>2}, {:>2})       {}      {:>3}  {}",
            row.n, row.l, row.magic_m, row.genus, row.type_i
        );
    }

    // Pick a generic point on E and a discrete log challenge.
    let curve = ECurve::new(big_n, irr.clone(), a.clone(), b.clone());
    let mut p_opt = None;
    for xi in 1u64..(1u64 << 6) {
        let x = F2mElement::from_biguint(&BigUint::from(xi), big_n);
        for yi in 1u64..(1u64 << 6) {
            let y = F2mElement::from_biguint(&BigUint::from(yi), big_n);
            let cand = Pt::Aff {
                x: x.clone(),
                y: y.clone(),
            };
            if curve.is_on_curve(&cand) {
                p_opt = Some(cand);
                break;
            }
        }
        if p_opt.is_some() {
            break;
        }
    }
    let p = p_opt.expect("a point on E(K) exists");
    // Pick a scalar such that Q = d·P is NON-trivial (not at infinity).
    // For toy parameters small d can loop around the group order.
    let mut d_true = BigUint::from(0u32);
    let mut q = Pt::Inf;
    for k in 2u32..50 {
        let cand_d = BigUint::from(k);
        let cand_q = curve.scalar_mul(&p, &cand_d);
        if !matches!(cand_q, Pt::Inf) {
            d_true = cand_d;
            q = cand_q;
            break;
        }
    }
    println!();
    println!("  ECDLP instance: find d such that Q = d·P on E.");
    println!(
        "  (hidden true d = {}, Q is {} the identity)",
        d_true,
        if matches!(q, Pt::Inf) { "AT" } else { "NOT at" }
    );

    let opts = AttackOptions {
        target_magic: 1,
        walk_max_visited: 32,
        walk_degrees: vec![2, 3],
        ecdlp_bound: BigUint::from(200u32),
    };
    let report_a = run_full_attack(&tc_a, &p, &q, &opts);
    println!();
    print!("{}", format_report(&report_a, &irr));

    if let Some(d) = &report_a.recovered_scalar {
        if report_a.ecdlp_solved {
            println!("\n  ✓ end-to-end attack solved ECDLP: recovered d = {}", d);
        } else {
            println!(
                "\n  ◐ partial recovery: d = {} on the descended subgroup",
                d
            );
        }
    } else {
        println!("\n  - descent ran but did not recover d (trace killed P)");
    }

    // ── Scenario B: m=2 trapdoor (structural demo) ────────────────
    banner("Scenario B: m = 2 trapdoor on F_{2^6} = F_{(2^2)^3}");
    println!(
        "
Pick a curve with magic m = 2 — the smallest 'genuine descent' case.
We use the factorisation (n=3, l=2) of F_{{2^6}} rather than (n=4, l=2):
at n=4 the σ-action on V_E(σ) can only have order dividing 4, never 3,
so type II (β_2 = β_0 + β_1, requiring σ of order 3 on V) is impossible
there. With n=3, type II IS possible, and the descended curve has
genus 2 — the favourable Hess regime.

The m=2 abstract descent below produces the σ-fixed Artin-Schreier
generators of the descended function field; converting them to a
single canonical y² + h(x)y = f(x) genus-2 equation is the next step
(not implemented here — see DescentM2Abstract::smooth_model_status).
"
    );
    let big_n_b = 6;
    let n_b = 3;
    let l_b = 2;
    let irr_b = IrreduciblePoly {
        degree: 6,
        low_terms: vec![0, 1],
    };
    // The construct_trapdoor_curve helper requires m·l | N (sufficient
    // but not necessary). For (N=6, n=3, l=2) with m=2 that demands
    // 4 | 6 which fails, so we search directly: enumerate b ∈ F_{2^6},
    // compute its magic via FieldTower, and accept the first
    // (m=2, type-II) hit.
    let tower_b = FieldTower::new(big_n_b, n_b, l_b, irr_b.clone());
    let a_b = F2mElement::one(big_n_b);
    let mut found: Option<(TrapdoorCurve, _)> = None;
    for b_candidate in 1u64..(1u64 << big_n_b) {
        let b_elt = F2mElement::from_biguint(&BigUint::from(b_candidate), big_n_b);
        if b_elt.is_zero() {
            continue;
        }
        let m = magic_number_full(&tower_b, &a_b, &b_elt);
        if m != 2 {
            continue;
        }
        let sqrt_b = tower_b.sqrt(&b_elt);
        let tc = TrapdoorCurve {
            big_n: big_n_b,
            n: n_b,
            l: l_b,
            big_irr: irr_b.clone(),
            a: a_b.clone(),
            b: b_elt.clone(),
            sqrt_b,
            row: DescentRow::default(),
            full_audit: None,
        };
        if let Some(d2) = descend_m2_abstract(&tc) {
            if d2.is_type_ii {
                found = Some((tc, d2));
                break;
            }
            if found.is_none() {
                found = Some((tc, d2));
            }
        }
    }
    match found {
        Some((tc_b, d2)) => {
            println!(
                "  Found magic-2 trapdoor: E/F_{{2^{}}} with (n={}, l={})",
                big_n_b, n_b, l_b
            );
            println!(
                "    b = {:?}, sqrt_b = {:?}",
                tc_b.b.to_biguint(),
                tc_b.sqrt_b.to_biguint()
            );
            let tower_b = FieldTower::new(big_n_b, n_b, l_b, irr_b.clone());
            let m = magic_number_full(&tower_b, &tc_b.a, &tc_b.b);
            println!("    magic_m = {} (verified)", m);
            println!(
                "    β_0 = {:?}, β_1 = {:?}, β_2 = {:?}",
                d2.beta_0.to_biguint(),
                d2.beta_1.to_biguint(),
                d2.beta_2.to_biguint()
            );
            println!("    type II (β_2 = β_0 + β_1): {}", d2.is_type_ii);
            println!("    σ-fixed AS generator w_0 satisfies w_0² + w_0 = x + a");
            println!("    status: {}", d2.smooth_model_status());
        }
        None => println!("  no magic-2 trapdoor found in the search budget"),
    }

    // ── Scenario C: Φ_l(X, j) magic spectrum ─────────────────────
    banner("Scenario C: isogeny-neighbour magic spectrum");
    println!(
        "
For Scenario A's starting curve, list the magic numbers of every
2- and 3-isogenous neighbour. This is what the Hess search would
trawl over for c2pnb176w1 (where direct magic is 1 and the goal is
to find a neighbour with magic ~5).
"
    );
    let start_curve = ECurve::new(big_n, irr.clone(), a, b);
    for &iso_l in &[2u32, 3u32] {
        // Show the Φ_l(X, j(E)) polynomial reduced mod 2.
        let j = j_invariant(&start_curve);
        let phi_x = phi_l_mod2_in_x(iso_l, &j, big_n, &irr);
        println!(
            "  Φ_{}(X, j(E)) in F_{{2^6}}[X]:  degree {}, coefficients (low → high):",
            iso_l,
            phi_x.degree().unwrap_or(0)
        );
        for (i, c) in phi_x.coeffs.iter().enumerate() {
            if !c.is_zero() {
                println!("    X^{} · {:?}", i, c.to_biguint());
            }
        }
        let nbs = l_isogenous_neighbours(&start_curve, iso_l);
        println!("  l = {}: {} neighbour curve(s)", iso_l, nbs.len());
        for nb in &nbs {
            let m_nb = magic_number_full(&tower, &nb.a, &nb.b);
            println!(
                "    j' = {:?}, a' = {:?}, b' = {:?}, magic = {}",
                j_invariant(nb).to_biguint(),
                nb.a.to_biguint(),
                nb.b.to_biguint(),
                m_nb
            );
        }
    }

    banner("Summary — what's runnable vs structural");
    println!(
        "
  Step                        | Status in this demo
  ────────────────────────────┼─────────────────────────────────────
  1. Isogeny walk             | ✓ runs (j-invariant level, Φ_l roots)
  2. Descent: m=1             | ✓ runs (trace map, end-to-end)
  2. Descent: m=2 abstract    | ✓ σ-fixed AS generators produced
  2. Descent: m=2 smooth (h,f)| ✗ not implemented (research-grade)
  3. HCDLP on Jac(C)(k)       | ✓ for any concrete C from step 2
  4. Lift through isogeny     | ✓ trivial for m=1; needs Vélu for m≥2

  For the c2pnb176w1 target specifically (m=11 over F_{{2^176}}, direct
  magic 1, Hess-reachable m'=5 per Menezes-Teske):

    - the isogeny walk in this demo scales structurally to c2pnb176w1's
      F_{{2^176}} field, but a useful traversal needs Φ_l for ℓ ≥ 5
      (storage grows fast: Φ_5 alone has ~750 coefficients of up to
      ~20-digit integer magnitude pre-reduction);
    - the m=2 abstract construction generalises to magic-5 at the same
      level of abstraction (5-dim F_2-orbit, 32-orbit element σ-action)
      but converting to a single hyperelliptic equation of genus 16 is
      where Hess's algorithm 'really' kicks in;
    - genus-16 index calculus over F_{{2^16}} is itself a research-grade
      implementation (Diem/GTTD, ~2^57 ops per Menezes-Teske).

  This module makes the structural attack inspectable and the easy
  cases runnable; the c2pnb176w1 numerical break stays out of scope.
"
    );
}
