//! Klein invariants in Gaudry's setting: descend the fixed-target quotient
//! systems over `F_{p^k}` to `F_p` and time the repo's Buchberger on them.
//!
//! ```bash
//! cargo run --release --example klein_descent
//! ```

use cryptanalysis_suite::cryptanalysis::coordinate_descent::{
    compare_arms, format_arms, standard_arms, DescentArm, F4Verdict,
};
use cryptanalysis_suite::cryptanalysis::coordinate_quotients::two_torsion_frame;
use cryptanalysis_suite::cryptanalysis::coordinate_search::{Curve, Gf, Pt, Rng64, INF};

fn median(v: Vec<f64>) -> f64 {
    let mut v: Vec<f64> = v.into_iter().filter(|x| x.is_finite()).collect();
    if v.is_empty() {
        return f64::NAN;
    }
    v.sort_by(|a, b| a.total_cmp(b));
    v[v.len() / 2]
}

fn run(
    curve: &Curve,
    m: usize,
    decomposable: usize,
    random: usize,
    skip: &[String],
    rng: &mut Rng64,
) {
    let f = &curve.f;
    let pts = curve.affine_points();
    // The base every arm shares: u ∈ F_p and finite, in the sign frame
    // (x ∈ F_p minus the frame's pole).  Targets are built from it so a
    // "decomposable" target is decomposable for every arm.
    let frame = two_torsion_frame(curve, &pts, rng);
    let base: Vec<Pt> = pts
        .iter()
        .copied()
        .filter(|p| {
            let u = frame.apply(f, p.x());
            u != INF && f.in_subfield(u, 1)
        })
        .collect();
    println!(
        "== {} over {}: #E = {}, base |x ∈ F_p| = {}, 2-torsion points {}",
        curve.label,
        f.name(),
        pts.len() + 1,
        base.len(),
        curve.two_torsion().len()
    );
    let mut targets: Vec<(Pt, &str)> = Vec::new();
    // decomposable targets: sums of m base points, affine, not 2-torsion,
    // and with x(R) ∉ F_p so the target is a genuine extension-field point
    let mut tries = 0;
    while targets.len() < decomposable && tries < 10_000 {
        tries += 1;
        let t = (0..m).fold(Pt::Inf, |acc, _| {
            curve.add(acc, base[rng.below(base.len() as u64) as usize])
        });
        if let Pt::Aff(x, _) = t {
            if curve.neg(t) != t && !f.in_subfield(x, 1) {
                targets.push((t, "decomposable"));
            }
        }
    }
    for _ in 0..random {
        let t = pts[rng.below(pts.len() as u64) as usize];
        if curve.neg(t) != t {
            targets.push((t, "random"));
        }
    }
    // Per-arm medians over the targets, split by kind.
    let mut rows: Vec<(String, Vec<DescentArm>)> = Vec::new();
    let (base_chart, all_arms) = standard_arms(curve, &pts, m, rng);
    let all_arms: Vec<_> = all_arms
        .into_iter()
        .filter(|a| !skip.iter().any(|s| a.0.contains(s.as_str())))
        .collect();
    for (t, kind) in &targets {
        // one arm at a time, with progress on stderr: at m = 3 a single
        // Buchberger run can take minutes
        let mut arms = Vec::new();
        for arm in &all_arms {
            let t0 = std::time::Instant::now();
            let mut r = compare_arms(curve, &pts, *t, m, base_chart, vec![arm.clone()], rng);
            eprintln!(
                "   [{kind} target {:?}] {} done in {:.1} s",
                t,
                arm.0,
                t0.elapsed().as_secs_f64()
            );
            arms.append(&mut r);
        }
        rows.push((kind.to_string(), arms));
    }
    // print the first decomposable target's table in full
    if let Some((_, arms)) = rows.first() {
        print!("{}", format_arms(arms));
    }
    let n_arms = rows.first().map(|r| r.1.len()).unwrap_or(0);
    println!("   medians over targets:");
    for ai in 0..n_arms {
        for kind in ["decomposable", "random"] {
            let ms: Vec<f64> = rows
                .iter()
                .filter(|(k, _)| k == kind)
                .filter_map(|(_, arms)| arms.get(ai))
                .filter(|a| a.error.is_none())
                .map(|a| a.groebner_ms)
                .collect();
            let refuted = rows
                .iter()
                .filter(|(k, _)| k == kind)
                .filter_map(|(_, arms)| arms.get(ai))
                .filter(|a| a.inconsistent)
                .count();
            let f4_ms: Vec<f64> = rows
                .iter()
                .filter(|(k, _)| k == kind)
                .filter_map(|(_, arms)| arms.get(ai))
                .filter(|a| a.error.is_none())
                .map(|a| a.f4_ms)
                .collect();
            let f4_deg: Vec<f64> = rows
                .iter()
                .filter(|(k, _)| k == kind)
                .filter_map(|(_, arms)| arms.get(ai))
                .filter(|a| a.error.is_none() && a.f4_verdict != F4Verdict::NotRun)
                .map(|a| a.f4_degree as f64)
                .collect();
            let f4_refuted = rows
                .iter()
                .filter(|(k, _)| k == kind)
                .filter_map(|(_, arms)| arms.get(ai))
                .filter(|a| a.f4_verdict == F4Verdict::Refuted)
                .count();
            let f4_undet = rows
                .iter()
                .filter(|(k, _)| k == kind)
                .filter_map(|(_, arms)| arms.get(ai))
                .filter(|a| a.f4_verdict == F4Verdict::Undetermined)
                .count();
            let label = rows[0].1[ai].label.clone();
            println!(
                "     {:<34} {:<12} n = {:>2}  median GB ms {:>8.1}  refuted {}   | F4 median ms {:>8.1}  solving degree {:>4.1}  refuted {}  undetermined {}",
                label,
                kind,
                ms.len(),
                median(ms),
                refuted,
                median(f4_ms),
                median(f4_deg),
                f4_refuted,
                f4_undet
            );
        }
    }
    println!();
}

/// `y² = x(x² − αx + 1)`: `T = (0, 0)` rational with `x(P + T) = 1/x`,
/// whose fixed points `±1` are in `F_p`, so the sign frame is `F_p`-rational
/// and the base `{u ∈ F_p} = {x ∈ F_p}` — while for `α ∉ F_p` the curve is
/// not over `F_p`, so that base is not a subgroup (Gaudry's setting).  The
/// other two 2-torsion points are rational iff `α² − 4` is a square.
fn alpha_curve(f: Gf, want_full_two_torsion: bool) -> Curve {
    let four = f.add(f.add(1, 1), f.add(1, 1));
    let alpha = (f.p..f.q)
        .find(|&a| {
            !f.in_subfield(a, 1) && {
                let disc = f.sub(f.mul(a, a), four);
                disc != 0 && f.sqrt(disc).is_some() == want_full_two_torsion
            }
        })
        .expect("an α");
    Curve {
        a1: 0,
        a2: f.neg(alpha),
        a3: 0,
        a4: 1,
        a6: 0,
        label: format!("y²=x(x²−αx+1), α={}", f.show(alpha)),
        f,
    }
}

fn main() {
    let m: usize = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(2);
    // `klein_descent [m] [--targets N] [--skip LABEL]...`
    let args: Vec<String> = std::env::args().collect();
    let mut targets = 4usize;
    let mut skip: Vec<String> = Vec::new();
    let mut i = 2;
    while i < args.len() {
        match args[i].as_str() {
            "--targets" => {
                targets = args.get(i + 1).and_then(|s| s.parse().ok()).unwrap_or(4);
                i += 2;
            }
            "--skip" => {
                if let Some(l) = args.get(i + 1) {
                    skip.push(l.clone());
                }
                i += 2;
            }
            _ => i += 1,
        }
    }
    let mut rng = Rng64::new(0x5EED);
    println!("=== Klein invariants over F_p^k, fixed-target systems descended to F_p, m = {m} ===");
    println!();
    println!("F_p-unk = unknowns over F_p; F_p-eq = k equations per field relation plus the");
    println!(
        "descended identities among the invariants; GB = reduced Gröbner basis by Buchberger."
    );
    println!();
    println!("-- Gaudry's setting: curves over F_p^k not defined over F_p, base {{x ∈ F_p}} not a subgroup --");
    println!();
    run(
        &alpha_curve(Gf::extension(29, 3), true),
        m,
        targets,
        targets,
        &skip,
        &mut rng,
    );
    run(
        &alpha_curve(Gf::extension(29, 3), false),
        m,
        targets,
        targets,
        &skip,
        &mut rng,
    );
    run(
        &alpha_curve(Gf::extension(17, 3), true),
        m,
        targets,
        targets,
        &skip,
        &mut rng,
    );
    if m == 2 {
        run(
            &alpha_curve(Gf::extension(13, 4), true),
            m,
            targets,
            targets,
            &skip,
            &mut rng,
        );
    }
    println!(
        "-- Degenerate control: a curve over F_p, where {{x ∈ F_p}} = E(F_p) is a subgroup --"
    );
    println!();
    run(
        &Curve::short_weierstrass(Gf::extension(29, 3), 28, 0, "y²=x³−x"),
        m,
        targets,
        targets,
        &skip,
        &mut rng,
    );
}
