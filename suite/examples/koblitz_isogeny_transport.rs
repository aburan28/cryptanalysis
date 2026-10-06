//! **Transport one ECDLP instance across explicit isogenies.**
//!
//! [`koblitz_isogeny_cost`] measures the class by handing every member the
//! same `d`, which is what an isogeny does to the logarithm.  This computes
//! the isogeny, so the transport is a computation:
//!
//! ```text
//!   φ: E → E'          explicit, from Vélu in char 2
//!   P, Q = [d]P  ↦  φ(P), φ(Q)
//!   check          x([d]φ(P)) == x(φ(Q))     on E'
//! ```
//!
//! Three parts:
//!
//! 1. **One hop**, verified against the tabulated `Φ₃` so the machinery is
//!    checked by something that does not share its derivation.
//! 2. **A walk**, composing hops, so the instance lands on a vertex several
//!    isogenies away and is still the same instance.
//! 3. **The reach**, stated in the same units as
//!    `koblitz_isogeny_cost::class_reach_report`: which vertices this can
//!    actually name, and what the rest would cost.
//!
//! Run: `cargo run --release --example koblitz_isogeny_transport`

use std::collections::{BTreeMap, BTreeSet, VecDeque};

use cryptanalysis_suite::binary_ecc::{F2mElement, F2mPoly};
use cryptanalysis_suite::cryptanalysis::binary_isogeny::find_roots_in_f2m;
use cryptanalysis_suite::cryptanalysis::binary_velu::*;
use cryptanalysis_suite::cryptanalysis::ic_boundary::{CountedGroup, GroupOps};
use cryptanalysis_suite::cryptanalysis::isogeny_class_search::koblitz_isogeny_class;
use cryptanalysis_suite::cryptanalysis::koblitz_fast::FastPoint;
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;

/// Degrees where `ℓ = 3` divides the conductor, so a 3-isogeny moves.
/// `ℓ = 3` is the one degree whose kernels need no factorisation: the
/// kernel polynomial is linear, so the kernels are simply the roots of the
/// degree-4 `ψ₃`.
const CASES: &[(u32, u8)] = &[(12, 0), (16, 0), (16, 1), (20, 0)];

fn factorise(mut v: u64) -> Vec<(u64, u32)> {
    let mut out = Vec::new();
    let mut d = 2u64;
    while d.saturating_mul(d) <= v {
        let mut e = 0;
        while v.is_multiple_of(d) {
            v /= d;
            e += 1;
        }
        if e > 0 {
            out.push((d, e));
        }
        d += 1;
    }
    if v > 1 {
        out.push((v, 1));
    }
    out
}

/// Every 3-isogeny out of `E`, as `(kernel polynomial, codomain a₆)`.
fn three_isogenies(curve: &Curve) -> Vec<(F2mPoly, u64)> {
    let n = curve.n;
    let psi3 = division_polynomial(&elt(curve.a6, n), 3, n, &curve.irr);
    find_roots_in_f2m(&psi3, n, &curve.irr)
        .into_iter()
        .filter_map(|root| {
            let h = F2mPoly::from_coeffs(vec![root, F2mElement::one(n)], n);
            let a6p = to_u64(&velu_codomain(&elt(curve.a6, n), &h, n, &curve.irr));
            (a6p != 0).then_some((h, a6p))
        })
        .collect()
}

fn main() {
    println!("════════════════════════════════════════════════════════════════");
    println!("Transporting one ECDLP instance across explicit isogenies");
    println!("════════════════════════════════════════════════════════════════");
    println!("E: y² + xy = x³ + a₂x² + a₆ over F_2^n.  Vélu in char 2:");
    println!("   a₆' = a₆ + t + t²,   X = x + A + A²,  A = (d mod 2) + x·h'/h");
    println!("Only ℓ = 3 is walked: its kernel polynomial is linear, so the");
    println!("kernels are the roots of ψ₃ and no factorisation is needed.");

    let mut one_hop_rows = Vec::new();
    let mut walk_rows = Vec::new();

    for &(n, a2) in CASES {
        let Some(irr) = find_irreducible_sparse(n) else {
            continue;
        };
        let Some(base) = Curve::new(n, &irr, a2, 1) else {
            continue;
        };
        let f = factorise(base.order);
        let (r, e) = *f.last().expect("a factor");
        if e != 1 || r < 50 {
            println!(
                "\n── n={n} a₂={a2}: #E = {} has no clean prime subgroup; skipped.",
                base.order
            );
            continue;
        }
        let cofactor = base.order / r;

        println!("\n════════════════════════════════════════════════════════════════");
        println!("── n = {n}, a₂ = {a2}, a₆ = 1 ──");
        println!(
            "   #E = {} = {}   subgroup r = {r} ({} bits), cofactor {cofactor}",
            base.order,
            f.iter()
                .map(|(p, e)| format!("{p}^{e}"))
                .collect::<Vec<_>>()
                .join("·"),
            64 - r.leading_zeros()
        );

        // ── the instance ────────────────────────────────────────────
        let group = base.group();
        let mut ops = GroupOps::default();
        let mut gen = FastPoint::INFINITY;
        for x in 0..(1u64 << n) {
            let Some(&p) = base.points_with_x(x).first() else {
                continue;
            };
            let g = group.mul(&mut ops, p, cofactor);
            if !g.infinity && group.mul(&mut ops, g, r).infinity {
                gen = g;
                break;
            }
        }
        if gen.infinity {
            println!("   no generator of order {r} found; skipped.");
            continue;
        }
        let d = 1 + (0x9E37_79B9u64 % (r - 1));
        let q_pt = group.mul(&mut ops, gen, d);
        println!("   P = (0x{:x}, 0x{:x}),  d = {d},  Q = [d]P", gen.x, gen.y);

        // ── part 1: one hop ─────────────────────────────────────────
        let isos = three_isogenies(&base);
        println!(
            "\n   ── one hop: the {} three-isogenies out of this curve ──",
            isos.len()
        );
        println!(
            "      {:>10} {:>10} {:>10} {:>8} {:>9} {:>10} {:>9}",
            "ker root", "a₆'", "#E'", "order=", "x(φP)", "x(φQ)", "transport"
        );
        for (h, a6p) in &isos {
            let iso = isogeny_from_kernel(&base, h.clone(), 3);
            let Some(rep) = transport_instance(&base, &iso, gen, q_pt, d, r) else {
                continue;
            };
            println!(
                "      {:>10} {:>10} {:>10} {:>8} {:>9} {:>10} {:>9}",
                to_u64(&h.coeff(0)),
                a6p,
                rep.codomain_order,
                if rep.order_preserved { "yes" } else { "NO" },
                rep.x_phi_p
                    .map(|v| format!("{v:x}"))
                    .unwrap_or_else(|| "ker".into()),
                rep.x_phi_q
                    .map(|v| format!("{v:x}"))
                    .unwrap_or_else(|| "ker".into()),
                if rep.transported && rep.image_order_ok {
                    "✓"
                } else if rep.transported {
                    "x only"
                } else {
                    "FAIL"
                }
            );
            one_hop_rows.push((
                n,
                a2,
                *a6p,
                rep.order_preserved,
                rep.transported,
                rep.image_order_ok,
            ));
        }

        // ── part 2: a walk, composing hops ──────────────────────────
        println!("\n   ── the walk: carry the instance along composed isogenies ──");
        let mut depth: BTreeMap<u64, u32> = BTreeMap::new();
        depth.insert(base.a6, 0);
        let mut queue: VecDeque<(u64, FastPoint, FastPoint, u32)> = VecDeque::new();
        queue.push_back((base.a6, gen, q_pt, 0));
        let mut verified = 0usize;
        let mut failed = 0usize;
        let mut reached: BTreeSet<u64> = BTreeSet::new();
        reached.insert(base.a6);

        while let Some((a6, p_here, q_here, dep)) = queue.pop_front() {
            if dep >= 6 {
                continue;
            }
            let Some(cur) = Curve::new(n, &irr, a2, a6) else {
                continue;
            };
            for (h, a6p) in three_isogenies(&cur) {
                if depth.contains_key(&a6p) {
                    continue;
                }
                // Push the instance itself along this edge.
                let Some(xp) = velu_x_map(&elt(p_here.x, n), &h, n, &irr) else {
                    continue;
                };
                let Some(xq) = velu_x_map(&elt(q_here.x, n), &h, n, &irr) else {
                    continue;
                };
                let Some(next) = Curve::new(n, &irr, a2, a6p) else {
                    continue;
                };
                let Some(&pp) = next.points_with_x(to_u64(&xp)).first() else {
                    continue;
                };
                let Some(&qq) = next.points_with_x(to_u64(&xq)).first() else {
                    continue;
                };
                let g2 = next.group();
                let mut o2 = GroupOps::default();
                let ok = g2.mul(&mut o2, pp, r).infinity && {
                    let dp = g2.mul(&mut o2, pp, d % r);
                    !dp.infinity && dp.x == qq.x
                };
                if ok {
                    verified += 1;
                } else {
                    failed += 1;
                }
                depth.insert(a6p, dep + 1);
                reached.insert(a6p);
                queue.push_back((a6p, pp, qq, dep + 1));
            }
        }

        let by_depth = depth
            .values()
            .fold(BTreeMap::new(), |mut m: BTreeMap<u32, usize>, d| {
                *m.entry(*d).or_insert(0) += 1;
                m
            });
        println!(
            "      reached {} vertices by composed 3-isogenies; depth histogram {:?}",
            reached.len(),
            by_depth
        );
        println!(
            "      instance verified on {verified} edges, failed on {failed} → {}",
            if failed == 0 && verified > 0 {
                "THE SAME d SURVIVES EVERY HOP"
            } else if verified == 0 {
                "nothing verified"
            } else {
                "SOME HOP LOST THE INSTANCE"
            }
        );

        let cls = koblitz_isogeny_class(n, 5_000_000);
        let degs: Vec<String> = cls
            .nontrivial_isogeny_degrees()
            .iter()
            .map(|d| d.to_string())
            .collect();
        println!(
            "      class size {} (degrees {:?}); the 3-isogeny component is {} of it",
            cls.class_size,
            degs,
            reached.len()
        );
        walk_rows.push((
            n,
            a2,
            reached.len(),
            verified,
            failed,
            cls.class_size.to_string(),
            degs.join(","),
        ));
    }

    // ── part 3: the reach, in the same units as the cost sweep ──────
    println!("\n════════════════════════════════════════════════════════════════");
    println!("── Part 3: what this route can and cannot name ──");
    println!(
        "\n   {:>4} {:>14} {:>22} {:>14} {:>16}",
        "n", "class size", "isogeny degrees ℓ|c", "deg ψ_ℓ", "kernel route"
    );
    for n in [8u32, 12, 16, 17, 19, 20] {
        let cls = koblitz_isogeny_class(n, 5_000_000);
        let degs: Vec<u64> = cls
            .nontrivial_isogeny_degrees()
            .iter()
            .filter_map(|d| d.to_string().parse().ok())
            .collect();
        let maxd = degs.iter().copied().max().unwrap_or(0);
        let psideg = if maxd == 0 { 0 } else { (maxd * maxd - 1) / 2 };
        println!(
            "   {:>4} {:>14} {:>22} {:>14} {:>16}",
            n,
            cls.class_size.to_string(),
            degs.iter()
                .map(|d| d.to_string())
                .collect::<Vec<_>>()
                .join(","),
            psideg,
            if maxd == 3 {
                "roots of ψ₃"
            } else if maxd <= 31 {
                "factor ψ_ℓ"
            } else {
                "factor ψ_ℓ (large)"
            }
        );
    }
    println!("\n   ℓ = 3 needs no factorisation at all: the kernel polynomial is");
    println!("   linear, so the kernels are the four roots of a degree-4 ψ₃.");
    println!("   Every larger ℓ needs the degree-(ℓ−1)/2 factors of ψ_ℓ, which is");
    println!("   where n = 17 (ℓ=271, deg ψ = 36720) and n = 19 (ℓ=457, deg ψ =");
    println!("   104424) sit.  That is a factorisation problem, not a Vélu one:");
    println!("   the formulas above already work at any ℓ, given the kernel.");

    println!("\n── summary ──");
    let hops_ok = one_hop_rows.iter().filter(|r| r.3 && r.4 && r.5).count();
    println!(
        "   single hops verified: {} of {}",
        hops_ok,
        one_hop_rows.len()
    );
    for (n, a2, reached, v, f, cls, degs) in &walk_rows {
        println!(
            "   n={n:<3} a₂={a2}  walk reached {reached:<4} vertices, {v} edges verified, {f} failed  (class {cls}, degrees {degs})"
        );
    }
}
