//! Search for point coordinates that make decomposition relations cheaper,
//! on toy curves over prime fields, binary fields and Koblitz curves.
//!
//! ```bash
//! cargo run --release --example coordinate_search            # m = 3 (S₄)
//! cargo run --release --example coordinate_search -- 2       # m = 2 (S₃)
//! ```
//!
//! See `research/notes/index-calculus/RESEARCH_EXOTIC_COORDINATES.md` for what the columns mean.

use cryptanalysis_suite::cryptanalysis::coordinate_search::{
    detect_symmetries, format_report, linearising_frame, scan_subfield_frames, search, Curve,
    FrameKind, Gf, Rng64, SearchOptions, SymmetryKind,
};
use std::time::Instant;

fn run(curve: &Curve, m: usize, l: Option<u32>) {
    let t0 = Instant::now();
    let report = search(
        curve,
        &SearchOptions {
            m,
            seed: 0x5EED,
            factor_base_dim: l,
            collapse_samples: 9,
        },
    );
    print!("{}", format_report(&curve.f, &report));
    println!("   ({:.1} s)", t0.elapsed().as_secs_f64());
    println!();
}

/// First `b` for which `y² = x³ + x + b` over `F_p` has a rational 2-torsion
/// point whose translation has rational fixed points on the x-line (so a
/// sign frame exists).
fn prime_curve_with_sign_frame(p: u64) -> Option<Curve> {
    for b in 1..200u64 {
        let c = Curve::short_weierstrass(Gf::prime(p), 1, b, &format!("y²=x³+x+{b}"));
        if c.j_invariant().is_none() {
            continue;
        }
        let pts = c.affine_points();
        let mut rng = Rng64::new(b);
        for s in detect_symmetries(&c, &pts, &mut rng) {
            if let (SymmetryKind::TwoTorsion(_), Some(g)) = (&s.kind, s.mobius) {
                if linearising_frame(&c.f, &g).kind == FrameKind::Sign {
                    return Some(c);
                }
            }
        }
    }
    None
}

/// First `b` for which `y² = x³ + x + b` has a rational 2-torsion point but
/// no rational sign frame (the involution's fixed points are irrational).
fn prime_curve_with_trace_frame_only(p: u64) -> Option<Curve> {
    for b in 1..200u64 {
        let c = Curve::short_weierstrass(Gf::prime(p), 1, b, &format!("y²=x³+x+{b}"));
        if c.j_invariant().is_none() {
            continue;
        }
        let pts = c.affine_points();
        let mut rng = Rng64::new(b);
        let syms = detect_symmetries(&c, &pts, &mut rng);
        let two: Vec<_> = syms
            .iter()
            .filter(|s| matches!(s.kind, SymmetryKind::TwoTorsion(_)))
            .collect();
        if two.len() == 1
            && linearising_frame(&c.f, &two[0].mobius.unwrap()).kind == FrameKind::Trace
        {
            return Some(c);
        }
    }
    None
}

fn main() {
    let m: usize = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(3);
    println!(
        "=== Coordinate search, m = {m} summands (S_{}), toy fields ===",
        m + 1
    );
    println!();
    println!("Columns: vars/degrees/terms of the interpolated relation polynomial;");
    println!("collapse = relation tuples per coordinate vector (median, permutations excluded);");
    println!("Frob = coordinate commutes with the subfield Frobenius; descent = unknowns/equations/degree");
    println!("of the Boolean system for a subspace factor base.");
    println!();

    println!("---------------- prime fields ----------------");
    println!();
    let p = 1009u64;
    run(
        &Curve::short_weierstrass(Gf::prime(p), 3, 7, "y²=x³+3x+7"),
        m,
        None,
    );
    if let Some(c) = prime_curve_with_sign_frame(p) {
        run(&c, m, None);
    }
    if let Some(c) = prime_curve_with_trace_frame_only(p) {
        run(&c, m, None);
    }
    // full rational 2-torsion and j = 1728 (p ≡ 1 mod 4, so i ∈ F_p)
    run(
        &Curve::short_weierstrass(Gf::prime(p), p - 1, 0, "y²=x³−x"),
        m,
        None,
    );
    // j = 0, secp256k1's shape (p ≡ 1 mod 3, so ω ∈ F_p)
    run(
        &Curve::short_weierstrass(Gf::prime(p), 0, 7, "y²=x³+7"),
        m,
        None,
    );

    println!("---------------- Koblitz curves ----------------");
    println!();
    for n in [7u32, 9, 11, 13] {
        for a in [0u8, 1] {
            run(&Curve::koblitz(a, n), m, None);
        }
    }
    // Which frames over F_2 linearise the 2-torsion at all?  Brute force.
    let k = Curve::koblitz(1, 7);
    let pts = k.affine_points();
    let mut rng = Rng64::new(1);
    for s in detect_symmetries(&k, &pts, &mut rng) {
        if let (SymmetryKind::TwoTorsion(_), Some(g)) = (&s.kind, s.mobius) {
            println!(
                "   all six frames of PGL_2(F_2) applied to x ↦ {} on K_1:",
                g.describe(&k.f)
            );
            for (n, kind) in scan_subfield_frames(&k.f, 1, &g) {
                println!("     u = {:<14} turns it into {:?}", n.describe(&k.f), kind);
            }
            println!();
        }
    }

    // The Koblitz polynomials have F_2 coefficients (the curve does), so
    // they are the same for every n.  Print them once.
    {
        use cryptanalysis_suite::cryptanalysis::coordinate_search::{
            interpolate_relation, CoordinateSystem, Frame,
        };
        let k = Curve::koblitz(1, 9);
        let pts = k.affine_points();
        let mut rng = Rng64::new(4);
        let syms = detect_symmetries(&k, &pts, &mut rng);
        let g = syms
            .iter()
            .find_map(|s| match s.kind {
                SymmetryKind::TwoTorsion(_) => s.mobius,
                _ => None,
            })
            .expect("2-torsion");
        let frame = linearising_frame(&k.f, &g);
        println!(
            "   S_{} for K_a in each coordinate system (coefficients in F_2, valid for every n):",
            m + 1
        );
        for cs in [
            CoordinateSystem::plain(&Frame::weierstrass(), false),
            CoordinateSystem::with_involution(&k.f, &frame, &g, false),
            CoordinateSystem::with_involution(&k.f, &frame, &g, true),
        ] {
            match interpolate_relation(&k, &pts, &cs, m, &mut rng) {
                Ok(r) => println!("     [{}]\n       {}", cs.name, r.poly.render(&k.f, 40)),
                Err(e) => println!("     [{}] {e}", cs.name),
            }
        }
        println!();
    }

    println!("---------------- other binary curves ----------------");
    println!();
    // Defined over F_8 ⊂ F_2^9: Frobenius of degree 3 only.
    let f9 = Gf::binary(9);
    let f8: Vec<u64> = f9
        .subfield_elements(3)
        .into_iter()
        .filter(|&a| a > 1)
        .collect();
    run(
        &Curve::binary(f9.clone(), 0, f8[0], "y²+xy=x³+b, b∈F_8"),
        m,
        None,
    );
    // Not a subfield curve at all.
    run(&Curve::binary(f9, 1, 0x1a5, "y²+xy=x³+x²+0x1a5"), m, None);
}
