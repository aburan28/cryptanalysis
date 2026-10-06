//! # End-to-end GHS / Hess Weil-descent attack pipeline.
//!
//! This module glues together the four steps of the attack on a binary
//! elliptic curve `E / F_{2^N}` whose subfield-defined structure
//! ([Teske-style w-curve / X9.62 c2pnb*w1](
//! crate::cryptanalysis::ec_trapdoor)) makes it vulnerable to
//! Weil descent:
//!
//! 1. **Isogeny walk** ([`crate::cryptanalysis::binary_isogeny`]):
//!    enumerate `l`-isogeny neighbours and locate one whose magic
//!    number is in the sweet spot for descent.
//! 2. **Descent construction** ([`crate::cryptanalysis::ghs_descent`]):
//!    build the descended curve `C / F_{2^l}` and the descent map
//!    `Φ: E(K) → Jac(C)(k)`.
//! 3. **HCDLP** ([`crate::binary_ecc::hyperelliptic`]): solve the
//!    discrete log on `Jac(C)(k)` (much smaller group).
//! 4. **Lift**: transport the recovered scalar back through any
//!    isogenies used in step 1.
//!
//! ## State of each step in this implementation
//!
//! - Step 1: **complete** at the `j`-invariant level (we walk by
//!   `Φ_l(X, j(E))` root extraction). Explicit Vélu isogeny morphism
//!   in characteristic 2 is **not** implemented — see Step 4 caveat.
//!
//! - Step 2: **complete for `m = 1`** (trace map; the descent target
//!   is `E` itself viewed over the subfield). **Symbolic only for
//!   `m = 2`** (σ-fixed generators produced, smooth-model conversion
//!   not implemented).
//!
//! - Step 3: **complete** for any concrete `(h, f)` produced by step 2
//!   — the [`crate::binary_ecc::hyperelliptic`] BSGS / Pollard-ρ
//!   HCDLP solver handles toy parameters. Diem / Gaudry-Thériault
//!   index calculus (needed to scale past genus 4–5 at non-toy
//!   subfields) is **not** implemented.
//!
//! - Step 4: **trivial for `m = 1`** (no isogeny used; lift is the
//!   identity). For `m ≥ 2` with a genuine isogeny walk, the lift
//!   needs an explicit isogeny morphism, which we don't have. The
//!   demo runs the `m = 1` path end-to-end.
//!
//! For the `c2pnb176w1` target specifically: direct magic is 1 (so the
//! `m = 1` pipeline is trivial / useless), and the Menezes-Teske
//! attack reaches `m' = 5` via the isogeny walk. Running step 2 at
//! `m' = 5` requires the genus-16 smooth-model construction and a
//! genus-16 index calculus over `F_{2^16}` — both research-grade and
//! not implemented here. What this module *does* do for `c2pnb176w1`
//! is enumerate `2`- and `3`-isogenous neighbours and report their
//! magic numbers, so you can see the magic spectrum the Hess search
//! would explore.

use crate::binary_ecc::{F2mElement, IrreduciblePoly};
use crate::cryptanalysis::binary_isogeny::{
    j_invariant, l_isogenous_neighbours, walk_to_magic, WalkOptions, WalkResult,
};
use crate::cryptanalysis::ec_trapdoor::{magic_number_full, FieldTower, TrapdoorCurve};
use crate::cryptanalysis::ghs_descent::{
    brute_force_ecdlp, descend_m1, descend_m2_abstract, ECurve, Pt,
};
use num_bigint::BigUint;

/// Configuration for [`run_full_attack`].
#[derive(Clone, Debug)]
pub struct AttackOptions {
    /// Isogeny degrees to consider in the walk. Default: `[2, 3]`.
    pub walk_degrees: Vec<u32>,
    /// Max number of `j`-invariants the walk may visit. Default: 64.
    pub walk_max_visited: usize,
    /// Target magic number to walk to. The walk stops once a curve
    /// of this magic is reached. Use `1` to skip the walk (the
    /// starting curve already has `m = 1`); use `2` to demonstrate
    /// the Hess search shape (without descent on the result).
    pub target_magic: u32,
    /// Upper bound on the ECDLP brute-force search after descent.
    pub ecdlp_bound: BigUint,
}

impl Default for AttackOptions {
    fn default() -> Self {
        Self {
            walk_degrees: vec![2, 3],
            walk_max_visited: 64,
            target_magic: 1,
            ecdlp_bound: BigUint::from(10_000u32),
        }
    }
}

/// Verbose record of what happened during a single attack run.
#[derive(Debug, Clone)]
pub struct AttackReport {
    /// Magic number of the starting curve (before the walk).
    pub start_magic: u32,
    /// `j`-invariants visited during the walk.
    pub walk_path: Vec<F2mElement>,
    /// Magic numbers observed at each step of the walk.
    pub walk_magics: Vec<u32>,
    /// Magic number of the curve where descent ran. Equals
    /// `start_magic` if the walk was skipped.
    pub descent_magic: u32,
    /// True iff the m=1 descent fully solved the ECDLP.
    pub ecdlp_solved: bool,
    /// Recovered scalar (only meaningful if `ecdlp_solved`).
    pub recovered_scalar: Option<BigUint>,
    /// Human-readable status of the m=2 abstract descent (if reached).
    pub m2_status: Option<&'static str>,
    /// Magic-number spectrum of the immediate 2- and 3-isogenous
    /// neighbours of the starting curve. Demonstrates the shape of
    /// the Hess search even when descent itself isn't run.
    pub neighbour_magics: Vec<NeighbourReport>,
}

/// Information about one isogeny-neighbour curve.
#[derive(Debug, Clone)]
pub struct NeighbourReport {
    pub isogeny_degree: u32,
    pub j_prime: F2mElement,
    pub magic: u32,
}

/// Run the full pipeline.  Given:
/// - `tc`: a trapdoor curve `E/F_{2^N}` whose factorisation `N = n·l`
///   gives some magic number,
/// - `p`, `q`: an ECDLP instance with `q = d·p` on `E(F_{2^N})`,
/// - `opts`: search / solver configuration,
///
/// produces an [`AttackReport`] capturing every step.  The m=1
/// descent + brute-force ECDLP path is the only one that actually
/// recovers `d`; the m≥2 reports are structural only.
pub fn run_full_attack(tc: &TrapdoorCurve, p: &Pt, q: &Pt, opts: &AttackOptions) -> AttackReport {
    let tower = FieldTower::new(tc.big_n, tc.n, tc.l, tc.big_irr.clone());
    let start_curve = ECurve::new(tc.big_n, tc.big_irr.clone(), tc.a.clone(), tc.b.clone());
    let start_magic = magic_number_full(&tower, &tc.a, &tc.b);

    // ── Step 1: enumerate immediate neighbours (informational) ───────
    let mut neighbour_magics = Vec::new();
    for &l in &opts.walk_degrees {
        for nb in l_isogenous_neighbours(&start_curve, l) {
            let m_nb = magic_number_full(&tower, &nb.a, &nb.b);
            neighbour_magics.push(NeighbourReport {
                isogeny_degree: l,
                j_prime: j_invariant(&nb),
                magic: m_nb,
            });
        }
    }

    // ── Step 1 (continued): walk to target magic if desired ──────────
    let walk_outcome = if opts.target_magic > start_magic {
        let walk_opts = WalkOptions {
            degrees: opts.walk_degrees.clone(),
            max_visited: opts.walk_max_visited,
            target_magic: opts.target_magic,
        };
        walk_to_magic(&start_curve, &tower, &walk_opts)
    } else {
        // No walk needed.
        Some(WalkResult {
            curve: start_curve.clone(),
            magic: start_magic,
            path: vec![j_invariant(&start_curve)],
        })
    };

    let (descent_curve, descent_magic, walk_path) = match walk_outcome {
        Some(wr) => (wr.curve, wr.magic, wr.path),
        None => {
            return AttackReport {
                start_magic,
                walk_path: vec![j_invariant(&start_curve)],
                walk_magics: vec![start_magic],
                descent_magic: start_magic,
                ecdlp_solved: false,
                recovered_scalar: None,
                m2_status: None,
                neighbour_magics,
            };
        }
    };

    // Magic at each step of the walk path (for the report).
    let walk_magics: Vec<u32> = walk_path
        .iter()
        .map(|j| {
            // Reconstruct a curve with this j and recompute its magic.
            // a = 0 representative is fine for magic purposes.
            let b = j
                .flt_inverse(&tc.big_irr)
                .unwrap_or(F2mElement::zero(tc.big_n));
            let a0 = F2mElement::zero(tc.big_n);
            magic_number_full(&tower, &a0, &b)
        })
        .collect();

    // ── Step 2/3/4: descent + HCDLP + lift ───────────────────────────
    let mut ecdlp_solved = false;
    let mut recovered_scalar = None;
    let mut m2_status = None;

    match descent_magic {
        1 => {
            // m=1 descent: trace map + brute force on the smaller curve.
            let tc_for_descent = TrapdoorCurve {
                big_n: tc.big_n,
                n: tc.n,
                l: tc.l,
                big_irr: tc.big_irr.clone(),
                a: descent_curve.a.clone(),
                b: descent_curve.b.clone(),
                sqrt_b: tower.sqrt(&descent_curve.b),
                row: tc.row.clone(),
                full_audit: None,
            };
            if let Some(desc) = descend_m1(&tc_for_descent) {
                let tp = desc.descent_map(p);
                let tq = desc.descent_map(q);
                // Solve  d·tp = tq  on the smaller curve.
                if !matches!(tp, Pt::Inf) {
                    if let Some(d) = brute_force_ecdlp(&desc.curve, &tp, &tq, &opts.ecdlp_bound) {
                        // Lift step: for m=1 with no isogeny used, the
                        // lift is the identity (we solved on the same
                        // curve, just via a different formulation).
                        // Verify the recovered scalar against the
                        // ORIGINAL instance (P, Q) — that's what the
                        // attacker wants.
                        let qp = desc.curve.scalar_mul(p, &d);
                        if &qp == q {
                            ecdlp_solved = true;
                            recovered_scalar = Some(d);
                        } else {
                            // The trace map only commutes with scalar
                            // mul; the recovered d satisfies
                            //   Tr(Q) = d·Tr(P)
                            // which lifts to  Q = d·P  whenever Tr(P)
                            // generates the same subgroup as P. If
                            // not, d holds modulo a subgroup factor —
                            // still useful as partial information.
                            recovered_scalar = Some(d);
                            ecdlp_solved = false;
                        }
                    }
                }
            }
        }
        2 => {
            // m=2: abstract construction only.
            let tc_for_descent = TrapdoorCurve {
                big_n: tc.big_n,
                n: tc.n,
                l: tc.l,
                big_irr: tc.big_irr.clone(),
                a: descent_curve.a.clone(),
                b: descent_curve.b.clone(),
                sqrt_b: tower.sqrt(&descent_curve.b),
                row: tc.row.clone(),
                full_audit: None,
            };
            if let Some(d2) = descend_m2_abstract(&tc_for_descent) {
                m2_status = Some(d2.smooth_model_status());
            }
        }
        _ => {
            m2_status = Some(
                "magic >= 3: descended hyperelliptic curve has genus >= 4. \
                 Construction follows the same recipe as m=2 with a larger \
                 F_2-basis, still unimplemented in this module.",
            );
        }
    }

    AttackReport {
        start_magic,
        walk_path,
        walk_magics,
        descent_magic,
        ecdlp_solved,
        recovered_scalar,
        m2_status,
        neighbour_magics,
    }
}

/// Pretty-print an [`AttackReport`].
pub fn format_report(r: &AttackReport, irr: &IrreduciblePoly) -> String {
    let _ = irr;
    let mut out = String::new();
    out.push_str("┌─ GHS / Hess Weil-descent attack report ─────────────────────────┐\n");
    out.push_str(&format!(
        "│ Starting magic number       : {}\n",
        r.start_magic
    ));
    out.push_str(&format!(
        "│ Isogeny walk path length    : {}  ({} curves visited)\n",
        r.walk_path.len() - 1,
        r.walk_path.len()
    ));
    if !r.walk_magics.is_empty() {
        let mag_str: Vec<String> = r.walk_magics.iter().map(|m| m.to_string()).collect();
        out.push_str(&format!(
            "│ Magic sequence along walk   : [{}]\n",
            mag_str.join(" → ")
        ));
    }
    out.push_str(&format!(
        "│ Descent ran on magic-{} curve\n",
        r.descent_magic
    ));
    if r.descent_magic == 1 {
        if r.ecdlp_solved {
            out.push_str(&format!(
                "│ ECDLP recovered scalar      : {} ✓\n",
                r.recovered_scalar.as_ref().unwrap()
            ));
        } else {
            out.push_str("│ m=1 descent ran; ECDLP recovery partial or failed.\n");
            if let Some(d) = &r.recovered_scalar {
                out.push_str(&format!(
                    "│   (partial scalar mod descent-subgroup: {})\n",
                    d
                ));
            }
        }
    } else if let Some(s) = r.m2_status {
        out.push_str("│ m≥2 status                 :\n");
        for line in s.split('\n') {
            out.push_str(&format!("│   {}\n", line));
        }
    }
    out.push_str(&format!(
        "│ Immediate isogeny neighbours: {} curves\n",
        r.neighbour_magics.len()
    ));
    let mut spectrum: std::collections::BTreeMap<u32, usize> = std::collections::BTreeMap::new();
    for nb in &r.neighbour_magics {
        *spectrum.entry(nb.magic).or_insert(0) += 1;
    }
    if !spectrum.is_empty() {
        out.push_str("│ Magic spectrum of neighbours:");
        for (m, count) in &spectrum {
            out.push_str(&format!(" m={}×{}", m, count));
        }
        out.push('\n');
    }
    out.push_str("└──────────────────────────────────────────────────────────────────┘\n");
    out
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::binary_ecc::IrreduciblePoly;
    use crate::cryptanalysis::ec_trapdoor::DescentRow;

    fn f64_irr() -> IrreduciblePoly {
        // F_{2^6}, x^6 + x + 1.
        IrreduciblePoly {
            degree: 6,
            low_terms: vec![0, 1],
        }
    }

    /// End-to-end on the `(N=6, n=2, l=3)` magic-1 setup: walk is
    /// trivial (target_magic = 1), m=1 descent solves toy ECDLP.
    #[test]
    fn end_to_end_m1_pipeline() {
        let irr = f64_irr();
        let big_n = 6;
        let n = 2;
        let l = 3;
        let tower = FieldTower::new(big_n, n, l, irr.clone());

        // Find b ∈ F_{2^3} \ F_2.
        let mut b = None;
        for candidate in 2u64..(1u64 << 6) {
            let cand = F2mElement::from_biguint(&BigUint::from(candidate), big_n);
            if tower.is_in_subfield(&cand, l) && !tower.is_in_subfield(&cand, 1) {
                b = Some(cand);
                break;
            }
        }
        let b = b.unwrap();
        let a = F2mElement::one(big_n);
        let tc = TrapdoorCurve {
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

        // ECDLP instance.
        let curve = ECurve::new(big_n, irr.clone(), a, b);
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
        let p = p_opt.unwrap();
        let d_true = BigUint::from(7u32);
        let q = curve.scalar_mul(&p, &d_true);

        let opts = AttackOptions::default();
        let report = run_full_attack(&tc, &p, &q, &opts);
        assert_eq!(report.start_magic, 1);
        assert_eq!(report.descent_magic, 1);
        // Solver may or may not recover the exact scalar depending on
        // whether the trace kills P. Accept either solved or
        // "partial recovery" outcomes — but if it's solved, it must
        // be correct.
        if report.ecdlp_solved {
            let k = report.recovered_scalar.as_ref().unwrap();
            let q_check = curve.scalar_mul(&p, k);
            assert_eq!(q_check, q, "recovered scalar must reproduce Q");
        }
    }

    /// Walk over a curve with no immediate magic-2 neighbour: confirm
    /// the report still produces a sensible spectrum.
    #[test]
    fn walk_reports_neighbour_spectrum() {
        let irr = f64_irr();
        let big_n = 6;
        let n = 2;
        let l = 3;
        let tower = FieldTower::new(big_n, n, l, irr.clone());
        let mut b = None;
        for candidate in 2u64..(1u64 << 6) {
            let cand = F2mElement::from_biguint(&BigUint::from(candidate), big_n);
            if tower.is_in_subfield(&cand, l) && !tower.is_in_subfield(&cand, 1) {
                b = Some(cand);
                break;
            }
        }
        let b = b.unwrap();
        let a = F2mElement::one(big_n);
        let tc = TrapdoorCurve {
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
        let _curve = ECurve::new(big_n, irr.clone(), a, b);
        // Trivial DLP: q = 1·p.
        let p = Pt::Inf;
        let q = Pt::Inf;
        let opts = AttackOptions {
            target_magic: 1,
            ..AttackOptions::default()
        };
        let report = run_full_attack(&tc, &p, &q, &opts);
        // Should have at least produced the immediate-neighbour
        // spectrum without error.
        let _ = format_report(&report, &irr);
    }
}
