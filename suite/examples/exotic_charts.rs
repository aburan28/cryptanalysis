//! Point representations beyond the `x`-line: charts on which a torsion
//! translation that is *not* a Möbius map on `x` becomes one.
//!
//! - **`x²`-line, `j = 1728`** (`y² = x³ + ax`, `i ∈ F_p`): the order-4
//!   automorphism `(x, y) ↦ (−x, −iy)` has quotient `x²`, and the
//!   2-torsion translation `x ↦ a/x` becomes `x² ↦ a²/x²` with fixed
//!   points `±a` — rational even when `±√a` (the fixed points on the
//!   `x`-line) are not.  So a sign frame exists on `x²` for every `a`.
//! - **2-isogeny line, rational 4-torsion** (Tate normal form
//!   `y² + xy − by = x³ − bx²`, `T₄ = (0, 0)`): on `x′ = x(P) + x(P + T₂)`,
//!   the `x`-line of `E/⟨T₂⟩`, the 4-torsion translation is a Möbius
//!   involution (its image on `E/⟨T₂⟩` is 2-torsion).
//! - **3-isogeny line, rational 6-torsion** (`y² = x³ + 1`, `T₃ = (0, 1)`,
//!   `T₂ = (−1, 0)`): on `x″ = x(P) + x(P + T₃) + x(P − T₃)` (Vélu), the
//!   2-torsion translation stays a Möbius involution and `ω` a scaling,
//!   so the whole 6-torsion and the automorphisms act by Möbius maps.
//!
//! For each, the induced Möbius map is fitted and verified on every
//! point, linearised where its fixed points are rational, and the
//! quotient engine measures the invariants, relation degree and collapse
//! against the plain `x`-line control.
//!
//! ```bash
//! cargo run --release --example exotic_charts            # m = 2
//! cargo run --release --example exotic_charts -- 3       # m = 3
//! ```

use cryptanalysis_suite::cryptanalysis::coordinate_quotients::{
    format_quotient, linearised_chart, run_quotient_boxed, torsion_points, two_torsion_frame,
    Chart, Line, PointMap, Seed,
};
use cryptanalysis_suite::cryptanalysis::coordinate_search::{Auto, Curve, Gf, Mobius, Pt, Rng64};
use std::time::Instant;

fn points(m: usize) -> Vec<Seed> {
    (0..=m).map(Seed::Point).collect()
}

fn points_sum_product(m: usize) -> Vec<Seed> {
    let mut v = points(m);
    v.push(Seed::Product);
    v.push(Seed::Sum);
    v
}

#[allow(clippy::too_many_arguments)]
fn run(
    curve: &Curve,
    pts: &[Pt],
    label: &str,
    gens: &[PointMap],
    chart: Chart,
    seeds: &[Seed],
    m: usize,
    max_deg: u32,
    caps: Option<(u32, u32)>,
    max_tuples: usize,
    rng: &mut Rng64,
) {
    let only: Vec<String> = {
        let a: Vec<String> = std::env::args().collect();
        a.iter()
            .enumerate()
            .filter(|(_, x)| x.as_str() == "--only")
            .filter_map(|(i, _)| a.get(i + 1).cloned())
            .collect()
    };
    if !only.is_empty() && !only.iter().any(|o| label.contains(o.as_str())) {
        return;
    }
    let t0 = Instant::now();
    match run_quotient_boxed(
        curve, pts, label, gens, chart, seeds, m, max_deg, caps, max_tuples, rng,
    ) {
        Some(r) => print!("{}", format_quotient(&curve.f, &r)),
        None => println!("   [{label}] no system (empty Γ or no non-constant invariant)"),
    }
    println!("      ({:.1} s)", t0.elapsed().as_secs_f64());
}

/// Fit, verify and report the chart in which `g` is linearised on `line`.
fn chart_for(curve: &Curve, pts: &[Pt], line: Line, g: &PointMap, what: &str) -> Option<Chart> {
    let f = &curve.f;
    match linearised_chart(curve, pts, line, g) {
        Some((chart, kind, m)) => {
            println!(
                "   {what} acts on the {:?} line as t ↦ {} (verified on every point); frame {:?}: {}",
                line,
                m.describe(f),
                kind,
                chart.describe(f)
            );
            Some(chart)
        }
        None => {
            println!("   {what} is NOT a Möbius map on the {:?} line", line);
            None
        }
    }
}

fn main() {
    let m: usize = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(2);
    let max_tuples = if m == 2 { 4_000_000 } else { 2_000_000 };
    let (deg, caps) = if m == 2 {
        (9, None)
    } else {
        (20, Some((4, 8)))
    };
    let mut rng = Rng64::new(0x4444);
    println!("=== Exotic charts: x²-line, 2-isogeny line, 3-isogeny line; m = {m} ===");
    println!();
    let f = Gf::prime(1009);
    let neg = PointMap::negate();

    // ---- (a) j = 1728: y² = x³ + ax, a a non-square (no rational sign
    //         frame on the x-line), then a square (both frames exist)
    let i = (2..f.p)
        .find(|&u| f.mul(u, u) == f.neg(1))
        .expect("p ≡ 1 mod 4");
    for want_square in [false, true] {
        let a = (2..f.p)
            .find(|&a| f.sqrt(a).is_some() == want_square)
            .unwrap();
        let c = Curve::short_weierstrass(f.clone(), a, 0, "y²=x³+ax");
        let pts = c.affine_points();
        let t = Pt::Aff(0, 0);
        assert!(c.is_on(t));
        let tau = PointMap::translate(t);
        let iota = PointMap {
            auto: Auto::Scale(i),
            t: Pt::Inf,
        };
        let fr_x = two_torsion_frame(&c, &pts, &mut rng);
        println!(
            "== {} / F_{}, a = {a} ({}), #E = {}, E[2](F_p) = {} points, i = {i}",
            c.label,
            f.p,
            if want_square {
                "a square"
            } else {
                "a non-square"
            },
            pts.len() + 1,
            c.two_torsion().len()
        );
        println!("   x-line frame for τ_T: u = {}", fr_x.describe(&f));
        let Some(x2) = chart_for(&c, &pts, Line::X2, &tau, "τ_T") else {
            continue;
        };
        run(
            &c,
            &pts,
            "x, ⟨τ_T, −⟩ (control)",
            &[tau, neg],
            Chart::x(fr_x),
            &points_sum_product(m),
            m,
            deg,
            caps,
            max_tuples,
            &mut rng,
        );
        run(
            &c,
            &pts,
            "x², ⟨τ_T, −⟩: points+Σ+Π",
            &[tau, neg],
            x2,
            &points_sum_product(m),
            m,
            deg,
            caps,
            max_tuples,
            &mut rng,
        );
        run(
            &c,
            &pts,
            "x², ⟨τ_T, i⟩: points+Σ+Π",
            &[tau, iota],
            x2,
            &points_sum_product(m),
            m,
            deg,
            caps,
            max_tuples,
            &mut rng,
        );
        println!();
    }

    // ---- (b) rational 4-torsion: Tate normal form y² + xy − by = x³ − bx²
    let b = (2..f.p)
        .find(|&b| {
            // Δ = b⁴(1 + 16b) ≠ 0
            f.add(1, f.mul(16 % f.p, b)) != 0
        })
        .unwrap();
    let c4 = Curve {
        a1: 1,
        a2: f.neg(b),
        a3: f.neg(b),
        a4: 0,
        a6: 0,
        label: format!("y²+xy−{b}y=x³−{b}x²"),
        f: f.clone(),
    };
    let pts = c4.affine_points();
    let t4 = Pt::Aff(0, 0);
    assert!(c4.is_on(t4));
    let t2 = c4.mul(t4, 2);
    assert_ne!(t2, Pt::Inf);
    assert_eq!(c4.mul(t4, 4), Pt::Inf, "(0, 0) has order 4");
    let tau4 = PointMap::translate(t4);
    let tau2 = PointMap::translate(t2);
    let fr_x = two_torsion_frame(&c4, &pts, &mut rng);
    println!(
        "== {} / F_{}: #E = {}, T₄ = {:?}, T₂ = {:?}, E[2](F_p) = {} points",
        c4.label,
        f.p,
        pts.len() + 1,
        t4,
        t2,
        c4.two_torsion().len()
    );
    println!("   x-line frame for τ_{{T₂}}: u = {}", fr_x.describe(&f));
    let _ = chart_for(&c4, &pts, Line::X, &tau4, "τ_{T₄}");
    if let Some(iso) = chart_for(&c4, &pts, Line::Iso2(t2), &tau4, "τ_{T₄}") {
        run(
            &c4,
            &pts,
            "x, ⟨τ_{T₂}, −⟩ (control)",
            &[tau2, neg],
            Chart::x(fr_x),
            &points_sum_product(m),
            m,
            deg,
            caps,
            max_tuples,
            &mut rng,
        );
        run(
            &c4,
            &pts,
            "x′, ⟨τ_{T₄}, −⟩: points+Σ+Π",
            &[tau4, neg],
            iso,
            &points_sum_product(m),
            m,
            deg,
            caps,
            max_tuples,
            &mut rng,
        );
    }
    println!();

    // ---- (c) rational 6-torsion on y² = x³ + 1
    let cb = Curve::short_weierstrass(f.clone(), 0, 1, "y²=x³+1");
    let pts = cb.affine_points();
    let t3 = Pt::Aff(0, 1);
    assert_eq!(cb.mul(t3, 3), Pt::Inf);
    let t2s = torsion_points(&cb, &pts, 2);
    let t2 = t2s[0];
    let omega = (2..f.p).find(|&u| u != 1 && f.pow(u, 3) == 1).unwrap();
    let om = PointMap {
        auto: Auto::Scale(omega),
        t: Pt::Inf,
    };
    let tau3 = PointMap::translate(t3);
    let tau2 = PointMap::translate(t2);
    let fr_x = two_torsion_frame(&cb, &pts, &mut rng);
    println!(
        "== {} / F_{}: #E = {}, T₃ = {:?}, T₂ = {:?}, ω = {omega}",
        cb.label,
        f.p,
        pts.len() + 1,
        t3,
        t2
    );
    println!("   x-line frame for τ_{{T₂}}: u = {}", fr_x.describe(&f));
    let _ = chart_for(&cb, &pts, Line::X, &tau3, "τ_{T₃}");
    if let Some(iso3) = chart_for(&cb, &pts, Line::Iso3(t3), &tau2, "τ_{T₂}") {
        let _ = chart_for(&cb, &pts, Line::Iso3(t3), &om, "ω");
        run(
            &cb,
            &pts,
            "x, ⟨τ_{T₂}, −⟩ (control)",
            &[tau2, neg],
            Chart::x(fr_x),
            &points_sum_product(m),
            m,
            deg,
            caps,
            max_tuples,
            &mut rng,
        );
        run(
            &cb,
            &pts,
            "x″, ⟨τ_{T₂}, τ_{T₃}, −⟩: points+Σ+Π",
            &[tau2, tau3, neg],
            iso3,
            &points_sum_product(m),
            m,
            deg,
            caps,
            max_tuples,
            &mut rng,
        );
        run(
            &cb,
            &pts,
            "x″, ⟨τ_{T₂}, τ_{T₃}, −, ω⟩: points+Σ+Π",
            &[tau2, tau3, neg, om],
            iso3,
            &points_sum_product(m),
            m,
            deg,
            caps,
            max_tuples,
            &mut rng,
        );
    }
    let _ = Mobius::identity();
}
