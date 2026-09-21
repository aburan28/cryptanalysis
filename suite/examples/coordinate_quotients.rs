//! Second coordinate search: invariants of a finite group of point maps by
//! orbit sums — the joint 2-torsion group on prime curves and the 4-torsion
//! of `K₀` on tuples.
//!
//! ```bash
//! cargo run --release --example coordinate_quotients            # m = 2
//! cargo run --release --example coordinate_quotients -- 3       # m = 3 (exact collapse skipped where too large)
//! ```

use cryptanalysis_suite::cryptanalysis::coordinate_quotients::{
    format_quotient, run_quotient, torsion_points, two_torsion_frame, PointMap, Seed,
};
use cryptanalysis_suite::cryptanalysis::coordinate_search::{Curve, Gf, Mobius, Pt, Rng64};
use std::time::Instant;

fn points_only(m: usize) -> Vec<Seed> {
    (0..=m).map(Seed::Point).collect()
}

fn seeds(m: usize, pairs: bool, product: bool) -> Vec<Seed> {
    let mut v: Vec<Seed> = (0..=m).map(Seed::Point).collect();
    v.push(Seed::Sum);
    if product {
        v.push(Seed::Product);
    }
    if pairs {
        for i in 0..=m {
            for j in (i + 1)..=m {
                v.push(Seed::PairSum(i, j));
                v.push(Seed::PairDiff(i, j));
            }
        }
    }
    v
}

fn run(
    curve: &Curve,
    label: &str,
    gens: &[PointMap],
    frame: Mobius,
    seeds: &[Seed],
    m: usize,
    max_deg: u32,
    max_tuples: usize,
    rng: &mut Rng64,
) {
    let pts = curve.affine_points();
    let t0 = Instant::now();
    match run_quotient(
        curve, &pts, label, gens, frame, seeds, m, max_deg, max_tuples, rng,
    ) {
        Some(r) => print!("{}", format_quotient(&curve.f, &r)),
        None => println!("   [{label}] no system (empty Γ or no non-constant invariant)"),
    }
    println!("      ({:.1} s)", t0.elapsed().as_secs_f64());
}

fn main() {
    let m: usize = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(2);
    let max_tuples = if m == 2 { 4_000_000 } else { 2_000_000 };
    let mut rng = Rng64::new(0x5EED);
    println!("=== Coordinate quotients, m = {m} ===");
    println!();

    // ---- Koblitz K_1: 2-torsion only (control, reproduces the first search)
    let k1 = Curve::koblitz(1, 7);
    let pts = k1.affine_points();
    let t2 = torsion_points(&k1, &pts, 2);
    let fr1 = two_torsion_frame(&k1, &pts, &mut rng);
    println!(
        "== K_1/F_2^7 (#E = {}), frame u = {}",
        pts.len() + 1,
        fr1.describe(&k1.f)
    );
    run(
        &k1,
        "T2, points+Σ",
        &[PointMap::translate(t2[0]), PointMap::negate()],
        fr1,
        &seeds(m, false, false),
        m,
        6,
        max_tuples,
        &mut rng,
    );
    run(
        &k1,
        "T2, points+Σ+Π",
        &[PointMap::translate(t2[0]), PointMap::negate()],
        fr1,
        &seeds(m, false, true),
        m,
        4,
        max_tuples,
        &mut rng,
    );
    println!();

    // ---- Koblitz K_0: rational 4-torsion
    let k0 = Curve::koblitz(0, 7);
    let pts = k0.affine_points();
    let t4: Vec<Pt> = torsion_points(&k0, &pts, 4)
        .into_iter()
        .filter(|&p| k0.mul(p, 2) != Pt::Inf)
        .collect();
    let t2 = torsion_points(&k0, &pts, 2);
    let fr0 = two_torsion_frame(&k0, &pts, &mut rng);
    println!(
        "== K_0/F_2^7 (#E = {}), T4 = {:?}, frame u = {}",
        pts.len() + 1,
        t4[0],
        fr0.describe(&k0.f)
    );
    run(
        &k0,
        "T2 only, points+Σ",
        &[PointMap::translate(t2[0]), PointMap::negate()],
        fr0,
        &seeds(m, false, false),
        m,
        6,
        max_tuples,
        &mut rng,
    );
    run(
        &k0,
        "T4, points only",
        &[PointMap::translate(t4[0]), PointMap::negate()],
        fr0,
        &points_only(m),
        m,
        5,
        max_tuples,
        &mut rng,
    );
    run(
        &k0,
        "T4, points+Σ",
        &[PointMap::translate(t4[0]), PointMap::negate()],
        fr0,
        &seeds(m, false, false),
        m,
        4,
        max_tuples,
        &mut rng,
    );
    run(
        &k0,
        "T4, points+Σ+Π",
        &[PointMap::translate(t4[0]), PointMap::negate()],
        fr0,
        &seeds(m, false, true),
        m,
        4,
        max_tuples,
        &mut rng,
    );
    run(
        &k0,
        "T4, points+Σ+pairs",
        &[PointMap::translate(t4[0]), PointMap::negate()],
        fr0,
        &seeds(m, true, false),
        m,
        3,
        max_tuples / 4,
        &mut rng,
    );
    println!();

    // ---- Prime curve with full rational 2-torsion and j = 1728
    let c = Curve::short_weierstrass(Gf::prime(1009), 1008, 0, "y²=x³−x");
    let pts = c.affine_points();
    let t2 = torsion_points(&c, &pts, 2);
    let fr = two_torsion_frame(&c, &pts, &mut rng);
    println!(
        "== y²=x³−x / F_1009 (#E = {}), E[2] = {:?}, frame u = {}",
        pts.len() + 1,
        t2,
        fr.describe(&c.f)
    );
    run(
        &c,
        "one T, points+Σ+Π",
        &[PointMap::translate(t2[0]), PointMap::negate()],
        fr,
        &seeds(m, false, true),
        m,
        4,
        max_tuples,
        &mut rng,
    );
    let gens: Vec<PointMap> = t2
        .iter()
        .map(|&t| PointMap::translate(t))
        .chain([PointMap::negate()])
        .collect();
    run(
        &c,
        "E[2], points only",
        &gens,
        fr,
        &points_only(m),
        m,
        5,
        max_tuples,
        &mut rng,
    );
    run(
        &c,
        "E[2], points+Σ+Π",
        &gens,
        fr,
        &seeds(m, false, true),
        m,
        4,
        max_tuples,
        &mut rng,
    );
    let mut gens_aut = gens.clone();
    for a in c.automorphisms() {
        gens_aut.push(PointMap {
            auto: a,
            t: Pt::Inf,
        });
    }
    run(
        &c,
        "E[2]+Aut, points+Σ+Π",
        &gens_aut,
        fr,
        &seeds(m, false, true),
        m,
        4,
        max_tuples,
        &mut rng,
    );
    println!();

    // ---- Prime curve with one rational 2-torsion point, sign frame
    let c1 = Curve::short_weierstrass(Gf::prime(1009), 1, 2, "y²=x³+x+2");
    let pts = c1.affine_points();
    let t2 = torsion_points(&c1, &pts, 2);
    let fr = two_torsion_frame(&c1, &pts, &mut rng);
    println!(
        "== y²=x³+x+2 / F_1009 (#E = {}), E[2] = {} points, frame u = {}",
        pts.len() + 1,
        t2.len(),
        fr.describe(&c1.f)
    );
    let gens: Vec<PointMap> = t2
        .iter()
        .map(|&t| PointMap::translate(t))
        .chain([PointMap::negate()])
        .collect();
    run(
        &c1,
        "E[2], points+Σ+Π",
        &gens,
        fr,
        &seeds(m, false, true),
        m,
        4,
        max_tuples,
        &mut rng,
    );
}
