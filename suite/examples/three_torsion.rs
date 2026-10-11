//! Rational 3-torsion on `j = 0` curves `y² = x³ + b` (with `p ≡ 1 mod 3`
//! so the order-3 automorphism `ω: (x, y) ↦ (ωx, y)` is rational).
//!
//! A 3-torsion translation `τ_T`, `T = (0, √b)`, does not act on the
//! `x`-line (only 2-torsion translations do), so on `x` the quotient
//! engine can only recover Vélu's 3-isogeny.  But `τ_T` commutes with `ω`,
//! whose quotient is the `y`-line, and there it *is* a Möbius map:
//! `y ↦ √b (y − 3√b) / (y + √b)`, of order 3, with fixed points
//! `±√b·√−3`.  The chart `v = (y − s)/(y + s)`, `s = √b √−3`, turns it
//! into `v ↦ ω v` and negation into `v ↦ 1/v`: the 3-torsion analogue of
//! the 2-torsion sign frame.  This example runs the quotient engine on
//! both lines, then tests which of the resulting invariants descend to
//! `F_p` in Gaudry's setting over `F_{31³}`.
//!
//! ```bash
//! cargo run --release --example three_torsion            # m = 2
//! cargo run --release --example three_torsion -- 3       # m = 3
//! ```

use cryptanalysis_suite::cryptanalysis::coordinate_descent::{
    compare_arms, format_arms, Arm, DescentArm, F4Verdict,
};
use cryptanalysis_suite::cryptanalysis::coordinate_quotients::{
    format_quotient, run_quotient_boxed, torsion_points, two_torsion_frame, Chart, PointMap, Seed,
};
use cryptanalysis_suite::cryptanalysis::coordinate_search::{
    Auto, Curve, Gf, Mobius, Pt, Rng64, INF,
};
use std::time::Instant;

/// A primitive cube root of unity in `f` (`q ≡ 1 mod 3`).
fn omega(f: &Gf) -> u64 {
    (2..f.q)
        .find(|&u| u != 1 && f.pow(u, 3) == 1)
        .expect("q ≡ 1 mod 3")
}

/// `y² = x³ + b` together with its rational 3-torsion point `(0, √b)`.
fn j0_curve(f: Gf, b: u64, label: &str) -> (Curve, Pt) {
    let t = f.sqrt(b).expect("b a square");
    let c = Curve::short_weierstrass(f, 0, b, label);
    let tp = Pt::Aff(0, t);
    assert!(c.is_on(tp));
    assert_eq!(c.mul(tp, 3), Pt::Inf, "(0, √b) has order 3");
    (c, tp)
}

/// The chart `v = (y − s)/(y + s)`, `s = √b·√−3`, on which `τ_T` is
/// `v ↦ ω^{±1} v` and `−1` is `v ↦ 1/v`.  Verified on every point.
fn three_torsion_chart(curve: &Curve, t3: Pt) -> Chart {
    let f = &curve.f;
    let t = t3.y();
    let three = f.add(f.add(1, 1), 1);
    let r = f.sqrt(f.neg(three)).expect("−3 a square when q ≡ 1 mod 3");
    let s = f.mul(t, r);
    let mob = Mobius {
        a: 1,
        b: f.neg(s),
        c: 1,
        d: s,
    };
    let chart = Chart::y(mob);
    let w = omega(f);
    let w2 = f.mul(w, w);
    for &p in &curve.affine_points() {
        let v = chart.apply(f, p);
        let vt = chart.apply(f, curve.add(p, t3));
        let vn = chart.apply(f, curve.neg(p));
        if v == INF || vt == INF || vn == INF || v == 0 {
            continue;
        }
        assert!(
            vt == f.mul(w, v) || vt == f.mul(w2, v),
            "τ_T is not v ↦ ωv at {p:?}"
        );
        assert_eq!(vn, f.inv(v), "−1 is not v ↦ 1/v at {p:?}");
    }
    chart
}

fn points(m: usize) -> Vec<Seed> {
    (0..=m).map(Seed::Point).collect()
}

fn points_product(m: usize) -> Vec<Seed> {
    let mut v = points(m);
    v.push(Seed::Product);
    v
}

fn points_sum_product(m: usize) -> Vec<Seed> {
    let mut v = points_product(m);
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
    // `--only SUBSTR` (repeatable) restricts the runs to matching labels
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

fn median(v: Vec<f64>) -> f64 {
    let mut v: Vec<f64> = v.into_iter().filter(|x| x.is_finite()).collect();
    if v.is_empty() {
        return f64::NAN;
    }
    v.sort_by(|a, b| a.total_cmp(b));
    v[v.len() / 2]
}

/// Gaudry's setting: `y² = x³ + b` over `F_{p³}` with `b ∉ F_p`, one
/// factor base per chart (`x ∈ F_p`, then `v ∈ F_p`), the same arms on
/// each, medians of the Buchberger time over `targets` decomposable targets.
fn descent(m: usize, targets: usize, rng: &mut Rng64) {
    let f = Gf::extension(31, 3);
    // b ∉ F_p, a square (so T = (0, √b) is rational over F_{p³}), and −b a
    // cube: the base {v ∈ F_p} is {y ∈ s·F_p}, whose x³ = −b(3r² + 1) with
    // r ∈ F_p, and every element of F_p is a cube in F_{p³} (p ≡ 1 mod 3),
    // so that base is ~3p points when −b is a cube and ~2 when it is not.
    // (−b a cube is rational 2-torsion, E[2] ⊂ E(F_{p³}).)
    let cube = |a: u64| f.pow(a, (f.q - 1) / 3) == 1;
    let b = (f.p..f.q)
        .find(|&b| !f.in_subfield(b, 1) && f.sqrt(b).is_some() && cube(f.neg(b)))
        .unwrap();
    let (c, t3) = j0_curve(f.clone(), b, "y²=x³+b");
    let f = &c.f;
    let pts = c.affine_points();
    let vchart = three_torsion_chart(&c, t3);
    let xchart = Chart::x(Mobius::identity());
    println!(
        "== {} over {}, b = {} ∉ F_p: #E = {}, T₃ = (0, {}), curve over F_p^{}",
        c.label,
        f.name(),
        f.show(b),
        pts.len() + 1,
        f.show(t3.y()),
        c.subfield_degree().unwrap_or(1)
    );
    let arms = |m: usize| -> Vec<Arm> {
        vec![
            (
                "x, ⟨−⟩ (Gaudry)".into(),
                vec![PointMap::negate()],
                xchart,
                points(m - 1),
            ),
            (
                "x, ⟨τ₃, −⟩ (Vélu)".into(),
                vec![PointMap::translate(t3), PointMap::negate()],
                xchart,
                points_product(m - 1),
            ),
            (
                "v, ⟨−⟩".into(),
                vec![PointMap::negate()],
                vchart,
                points_product(m - 1),
            ),
            (
                "v, ⟨τ₃, −⟩".into(),
                vec![PointMap::translate(t3), PointMap::negate()],
                vchart,
                points_product(m - 1),
            ),
        ]
    };
    for (base_label, base_chart) in [("x ∈ F_p", xchart), ("v ∈ F_p", vchart)] {
        let base: Vec<Pt> = pts
            .iter()
            .copied()
            .filter(|&p| {
                let u = base_chart.apply(f, p);
                u != INF && f.in_subfield(u, 1)
            })
            .collect();
        println!("-- base {{{base_label}}}: {} points", base.len());
        let mut rows: Vec<Vec<DescentArm>> = Vec::new();
        let mut tries = 0;
        while rows.len() < targets && tries < 10_000 {
            tries += 1;
            let t = (0..m).fold(Pt::Inf, |acc, _| {
                c.add(acc, base[rng.below(base.len() as u64) as usize])
            });
            let Pt::Aff(..) = t else { continue };
            if c.neg(t) == t || base.contains(&t) {
                continue;
            }
            rows.push(compare_arms(&c, &pts, t, m, base_chart, arms(m), rng));
        }
        if let Some(first) = rows.first() {
            print!("{}", format_arms(first));
            println!(
                "   medians over {} decomposable targets (Buchberger | F4):",
                rows.len()
            );
            for ai in 0..first.len() {
                let ms: Vec<f64> = rows.iter().map(|r| r[ai].groebner_ms).collect();
                let refuted = rows.iter().filter(|r| r[ai].inconsistent).count();
                let f4_ms: Vec<f64> = rows.iter().map(|r| r[ai].f4_ms).collect();
                let f4_deg: Vec<f64> = rows
                    .iter()
                    .filter(|r| r[ai].f4_verdict != F4Verdict::NotRun)
                    .map(|r| r[ai].f4_degree as f64)
                    .collect();
                let f4_refuted = rows
                    .iter()
                    .filter(|r| r[ai].f4_verdict == F4Verdict::Refuted)
                    .count();
                let f4_undet = rows
                    .iter()
                    .filter(|r| r[ai].f4_verdict == F4Verdict::Undetermined)
                    .count();
                println!(
                    "      {:<22} GB {:>8.1} ms (refuted {refuted}/{}) | F4 {:>8.1} ms, solving degree {:>4.1}, refuted {f4_refuted}, undetermined {f4_undet}",
                    first[ai].label,
                    median(ms),
                    rows.len(),
                    median(f4_ms),
                    median(f4_deg)
                );
            }
        }
    }
}

fn main() {
    let m: usize = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(2);
    let descent_only = std::env::args().any(|a| a == "--descent-only");
    if descent_only {
        let mut rng = Rng64::new(0x3333);
        descent(m, if m == 2 { 6 } else { 2 }, &mut rng);
        return;
    }
    let max_tuples = if m == 2 { 4_000_000 } else { 2_000_000 };
    // At m = 3 the relations are of total degree beyond what 3000
    // monomials allow in five unknowns, but of bounded degree in each
    // point invariant (Semaev: 4 in each x; the 3-torsion frame: 3 in
    // each V): box the interpolation by point / tuple degree.
    let (deg, caps) = if m == 2 {
        (9, None)
    } else {
        (16, Some((4, 8)))
    };
    // On the v-line the point invariants have degree 3 (measured under
    // ⟨τ₃⟩ alone), so a tighter point cap leaves room for the tuple
    // unknown's degree within the monomial cap.
    let (vdeg, vcaps) = if m == 2 {
        (9, None)
    } else {
        (20, Some((3, 8)))
    };
    // `THREE_TORSION_VCAPS=point,tuple` overrides the v-line box at m = 3;
    // the total degree then covers the whole box.
    let vcaps = std::env::var("THREE_TORSION_VCAPS")
        .ok()
        .and_then(|v| {
            let mut it = v.split(',').filter_map(|x| x.trim().parse::<u32>().ok());
            Some((it.next()?, it.next()?))
        })
        .or(vcaps);
    let vdeg = vcaps.map_or(vdeg, |(pc, tc)| vdeg.max((m as u32 + 1) * pc + tc));
    let mut rng = Rng64::new(0x3333);
    println!("=== 3-torsion seeds on j = 0 curves, m = {m} ===");
    println!();

    // ---- Curve A: rational 3-torsion, no rational 2-torsion (−b not a cube)
    let f = Gf::prime(1009);
    assert_eq!(f.p % 3, 1);
    let cube = |a: u64| f.pow(a, (f.p - 1) / 3) == 1;
    let b_a = (1..f.p)
        .find(|&b| f.sqrt(b).is_some() && !cube(f.neg(b)))
        .unwrap();
    let (ca, t3) = j0_curve(f.clone(), b_a, "y²=x³+b (A)");
    let pts = ca.affine_points();
    let vchart = three_torsion_chart(&ca, t3);
    let w = omega(&f);
    println!(
        "== {} / F_{}, b = {b_a}: #E = {}, E[2](F_p) = {} points, T₃ = {:?}, ω = {w}",
        ca.label,
        f.p,
        pts.len() + 1,
        ca.two_torsion().len(),
        t3
    );
    println!(
        "   v = {} (τ₃: v ↦ ωv, −1: v ↦ 1/v, verified)",
        vchart.describe(&f)
    );
    let tau = PointMap::translate(t3);
    let neg = PointMap::negate();
    let om = PointMap {
        auto: Auto::Scale(w),
        t: Pt::Inf,
    };
    let xid = Chart::x(Mobius::identity());
    let yid = Chart::y(Mobius::identity());
    run(
        &ca,
        &pts,
        "x, ⟨−⟩: Semaev control",
        &[neg],
        xid,
        &points(m),
        m,
        deg,
        caps,
        max_tuples,
        &mut rng,
    );
    // The x-line quotients only recover Vélu's isogeny (§13.1); at m = 3
    // their tuple invariants blow the monomial cap for nothing.
    if m == 2 {
        run(
            &ca,
            &pts,
            "x, ⟨τ₃, −⟩: points+Σ+Π",
            &[tau, neg],
            xid,
            &points_sum_product(m),
            m,
            deg,
            caps,
            max_tuples,
            &mut rng,
        );
        run(
            &ca,
            &pts,
            "x, ⟨τ₃, −, ω⟩: points+Π",
            &[tau, neg, om],
            xid,
            &points_product(m),
            m,
            deg,
            caps,
            max_tuples,
            &mut rng,
        );
    }
    // y-Semaev at m = 3 has degree 9 per point: over the monomial cap.
    if m == 2 {
        run(
            &ca,
            &pts,
            "y, ⟨−⟩: y-Semaev",
            &[neg],
            yid,
            &points_sum_product(m),
            m,
            deg,
            caps,
            max_tuples,
            &mut rng,
        );
    }
    run(
        &ca,
        &pts,
        "v, ⟨τ₃⟩: points+Π",
        &[tau],
        vchart,
        &points_product(m),
        m,
        vdeg,
        vcaps,
        max_tuples,
        &mut rng,
    );
    run(
        &ca,
        &pts,
        "v, ⟨τ₃, −⟩: points+Π",
        &[tau, neg],
        vchart,
        &points_product(m),
        m,
        vdeg,
        vcaps,
        max_tuples,
        &mut rng,
    );
    run(
        &ca,
        &pts,
        "v, ⟨τ₃, −, ω⟩: points+Π",
        &[tau, neg, om],
        vchart,
        &points_product(m),
        m,
        vdeg,
        vcaps,
        max_tuples,
        &mut rng,
    );
    run(
        &ca,
        &pts,
        "v, ⟨τ₃, −, ω⟩: points+Σ+Π",
        &[tau, neg, om],
        vchart,
        &points_sum_product(m),
        m,
        vdeg,
        vcaps,
        max_tuples,
        &mut rng,
    );
    println!();

    // ---- Curve B: y² = x³ + 1, rational 2- and 3-torsion (a 6-torsion point)
    let (cb, t3b) = j0_curve(f.clone(), 1, "y²=x³+1 (B)");
    let pts = cb.affine_points();
    let t2 = torsion_points(&cb, &pts, 2);
    let fr2 = two_torsion_frame(&cb, &pts, &mut rng);
    println!(
        "== {} / F_{}: #E = {}, E[2](F_p) = {:?}, T₃ = {:?}, 2-torsion frame u = {}",
        cb.label,
        f.p,
        pts.len() + 1,
        t2,
        t3b,
        fr2.describe(&f)
    );
    let taub = PointMap::translate(t3b);
    let tau2 = PointMap::translate(t2[0]);
    run(
        &cb,
        &pts,
        "u, ⟨τ₂, −⟩: points+Σ+Π (control)",
        &[tau2, neg],
        Chart::x(fr2),
        &points_sum_product(m),
        m,
        deg,
        caps,
        max_tuples,
        &mut rng,
    );
    // 14 invariants at m = 3: over the monomial cap at total degree 4.
    if m == 2 {
        run(
            &cb,
            &pts,
            "u, ⟨τ₂, τ₃, −⟩ = ⟨τ₆, −⟩: points+Σ+Π",
            &[tau2, taub, neg],
            Chart::x(fr2),
            &points_sum_product(m),
            m,
            deg,
            caps,
            max_tuples,
            &mut rng,
        );
    }
    let vb = three_torsion_chart(&cb, t3b);
    run(
        &cb,
        &pts,
        "v, ⟨τ₃, −, ω⟩: points+Π",
        &[taub, neg, om],
        vb,
        &points_product(m),
        m,
        vdeg,
        vcaps,
        max_tuples,
        &mut rng,
    );
    println!();

    // ---- Gaudry's setting over F_31^3
    if m == 2 {
        descent(2, 6, &mut rng);
    } else {
        descent(m, 2, &mut rng);
    }
}
