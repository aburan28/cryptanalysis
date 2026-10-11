//! Where selecting a factor base spends its 79.5 additions a point.
//!
//! Selection is 23.4% of the `n = 41` pipeline now that collection's
//! relation count is at its floor, and it costs 79.5 group-addition
//! equivalents for each of the 15,744 points it produces.  The algebra a
//! point *requires* is much less than that: half of one half-trace
//! quadratic solve, because an abscissa carries two points, plus half a
//! Frobenius step to place it in its orbit.  So before optimising
//! anything, this measures the floor and then decomposes the measured
//! cost against it.
//!
//! The floor is the lift that produces a point plus the single Frobenius
//! step that places it in its orbit, both unconverted. Note that a
//! half-trace solve yields *two* points, and that every figure here is
//! per point, so the lift term needs no halving -- the first version of
//! this halved it and the orbit step too, and understated the floor by a
//! factor of two.
//!
//! The boundary here is a **floor derived from the field operations
//! selection cannot skip**, measured on this host rather than counted by
//! hand: no implementation of this phase can beat the cost of lifting
//! the abscissae it needs. Anything above that floor is representation,
//! not mathematics, and representation is negotiable.
//!
//! The candidates for the gap, read off the code before measuring:
//!
//!   * `points_with_x_fast` does its arithmetic in single words and then
//!     calls `lower`, which allocates two `BigUint`s per point.
//!   * `finish_factor_base_domain` keys its point index on
//!     `(BigUint, BigUint)` via `point_key` — two allocations and a
//!     two-`BigUint` hash per insert, and again per lookup.
//!   * the orbit and signed-orbit walks each step with `kc.frobenius` on
//!     a `BigUint`-backed `BinaryPoint`, and look up `point_key` at every
//!     step, so a point is keyed about three times over.
//!
//!     cargo run --release --example koblitz_select_decomposition -- 41 15300
use cryptanalysis_suite::binary_ecc::{BinaryPoint, F2mElement};
use cryptanalysis_suite::cryptanalysis::koblitz_fast::{BatchScratch, FastCurve, FastPoint};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::*;
use std::time::Instant;

const ADDS: usize = 2_000_000;

fn main() {
    let degree: u32 = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(41);
    let points: usize = std::env::args()
        .nth(2)
        .and_then(|s| s.parse().ok())
        .unwrap_or(15300);
    let seed: u64 = std::env::args()
        .nth(3)
        .and_then(|s| s.parse().ok())
        .unwrap_or(1);
    let kc = KoblitzCurve::new(0, degree).expect("curve");
    let fc = FastCurve::new(&kc.curve).expect("fast curve");

    // The unit: one batched affine addition, as everywhere else on the
    // scoreboard.
    let seedfb = build_subgroup_orbit_factor_base(&kc, seed, 64).expect("seed base");
    let g = fc.lift(kc.generator());
    let batch: Vec<FastPoint> = (0..1024)
        .map(|i| fc.lift(&seedfb.points[i % seedfb.points.len()]))
        .collect();
    let mut scratch = BatchScratch::default();
    let mut out: Vec<FastPoint> = Vec::with_capacity(batch.len());
    let rounds = ADDS / batch.len();
    let t = Instant::now();
    for _ in 0..rounds {
        out.clear();
        fc.add_many(g, &batch, &mut out, &mut scratch);
    }
    let add_ns = t.elapsed().as_secs_f64() * 1e9 / (rounds * batch.len()) as f64;
    std::hint::black_box(out.len());

    // The base this is all about, and its representatives, so each phase
    // can be re-run on exactly the inputs the real call gave it.
    let t = Instant::now();
    let (fb, cost) =
        build_subgroup_orbit_factor_base_with_cost(&kc, seed, points).expect("selection");
    let whole_ns = t.elapsed().as_secs_f64() * 1e9;
    let n_points = fb.points.len();
    let n_orbits = fb.signed_orbits.len();
    println!("degree {degree}, base {n_points} points, {n_orbits} signed orbits");
    println!("one batched group addition = {add_ns:.2} ns   <- the unit");
    println!(
        "selection, whole call: {:.1} ms = {:.0} adds = {:.1} adds a point",
        whole_ns / 1e6,
        whole_ns / add_ns,
        whole_ns / add_ns / n_points as f64
    );
    println!(
        "  {} abscissae drawn, {} lifts, {} frobenius squarings, {} rebuild(s)",
        cost.abscissae_drawn, cost.lifts_found, cost.frobenius_squarings, cost.rebuilds
    );

    // Representatives, one per signed orbit, in the form the rebuild takes.
    let reps: Vec<F2mElement> = fb
        .signed_orbits
        .iter()
        .filter_map(|o| match &fb.points[o[0]] {
            BinaryPoint::Affine { x, .. } => Some(x.clone()),
            BinaryPoint::Infinity => None,
        })
        .collect();

    // Every abscissa of the base, for the lift-only phase.
    let mut xs: Vec<F2mElement> = fb
        .points
        .iter()
        .filter_map(|p| match p {
            BinaryPoint::Affine { x, .. } => Some(x.clone()),
            BinaryPoint::Infinity => None,
        })
        .collect();
    xs.sort_by_key(|x| x.to_biguint());
    xs.dedup_by_key(|x| x.to_biguint());

    let per = |ns: f64| (ns / add_ns, ns / add_ns / n_points as f64);
    println!(
        "\nrows marked [counterfactual] are the BigUint steps the builder used\n\
         BEFORE this round and no longer performs; their share column is what\n\
         they would be, not what the call above spends."
    );
    println!(
        "\n{:<44}{:>11}{:>13}{:>13}{:>9}",
        "phase", "ms", "adds", "adds/point", "share"
    );

    let row = |name: &str, ns: f64| {
        let (adds, app) = per(ns);
        println!(
            "{name:<44}{:>11.2}{:>13.0}{:>13.2}{:>8.1}%",
            ns / 1e6,
            adds,
            app,
            100.0 * ns / whole_ns
        );
        adds
    };

    // The rebuild, on the representatives the real call ended with.
    let t = Instant::now();
    let rebuilt = build_explicit_frobenius_orbit_factor_base(&kc, &reps).expect("rebuild");
    let rebuild_ns = t.elapsed().as_secs_f64() * 1e9;
    assert_eq!(
        rebuilt.points.len(),
        n_points,
        "the rebuild is not the same base"
    );
    row("rebuild: build_explicit_..._factor_base", rebuild_ns);

    // Inside it: the lifts, which are the algebra plus a `lower`.
    let t = Instant::now();
    let mut lifted = 0usize;
    for x in &xs {
        lifted += points_with_x_fast(&fc, x).len();
    }
    let lift_ns = t.elapsed().as_secs_f64() * 1e9;
    std::hint::black_box(lifted);
    row("  of which lifts (points_with_x_fast)", lift_ns);

    // `lower` alone, the BigUint conversion at the end of a lift.
    let fast_points: Vec<FastPoint> = fb.points.iter().map(|p| fc.lift(p)).collect();
    let t = Instant::now();
    let mut acc = 0usize;
    for &p in &fast_points {
        acc += usize::from(fc.lower(p) != BinaryPoint::Infinity);
    }
    let lower_ns = t.elapsed().as_secs_f64() * 1e9;
    std::hint::black_box(acc);
    row("    of which lower() to BigUint", lower_ns);

    // Keying: `point_key` over the base, which the builder pays about
    // three times over (one insert, one orbit walk, one signed walk).
    let t = Instant::now();
    let mut keyed = 0usize;
    for p in &fb.points {
        keyed += usize::from(point_key(p).0 != num_bigint::BigUint::from(0u32));
    }
    let key_ns = t.elapsed().as_secs_f64() * 1e9;
    std::hint::black_box(keyed);
    row("  [counterfactual] point_key over the base, once", key_ns);
    row(
        "  [counterfactual] point_key x3, the old builder",
        key_ns * 3.0,
    );

    // The orbit walks' step: `kc.frobenius` on a BigUint-backed point.
    let t = Instant::now();
    let mut walked = 0usize;
    for p in &fb.points {
        walked += usize::from(kc.frobenius(p) != BinaryPoint::Infinity);
    }
    let frob_ns = t.elapsed().as_secs_f64() * 1e9;
    std::hint::black_box(walked);
    row(
        "  [counterfactual] kc.frobenius over the base, once",
        frob_ns,
    );
    row(
        "  [counterfactual] kc.frobenius x2, the old walks",
        frob_ns * 2.0,
    );

    // The same step in single words, for comparison: what the walk would
    // cost if the builder used the representation the rest of the
    // pipeline already uses.
    let t = Instant::now();
    let mut fastwalk = 0u64;
    for &p in &fast_points {
        fastwalk ^= fc.frobenius_k(p, kc.k).pack();
    }
    let fastfrob_ns = t.elapsed().as_secs_f64() * 1e9;
    std::hint::black_box(fastwalk);
    row(
        "  orbit step, packed (fc.frobenius_k) <- now used",
        fastfrob_ns,
    );

    // And the packed key, likewise.
    let t = Instant::now();
    let mut packed = 0u64;
    for &p in &fast_points {
        packed ^= p.pack();
    }
    let pack_ns = t.elapsed().as_secs_f64() * 1e9;
    std::hint::black_box(packed);
    row("  index key, packed (FastPoint::pack) <- now used", pack_ns);

    // The floor: the algebra a point cannot avoid, which is the lift that
    // produces it plus the one Frobenius step that places it in its
    // orbit, both in the representation the field arithmetic actually
    // uses and with no conversion at the end.
    //
    // No halving anywhere, and that is worth spelling out because the
    // first version of this halved both terms and understated the floor
    // twofold. `lift_ns` is measured over the *abscissae*, of which there
    // are half as many as points, and every figure in this table is
    // divided by the point count -- so 'adds a point' already carries
    // the fact that one solve yields two points. Likewise `fastfrob_ns`
    // is measured over every point, and an orbit walk does visit every
    // point once, so that is one step per point and not half of one. A
    // floor is only a boundary if it is derived at the same
    // normalisation as the thing it bounds.
    let floor_ns = (lift_ns - lower_ns) + fastfrob_ns;
    println!();
    let floor_adds = row(
        "FLOOR: lift algebra + one orbit step, unconverted",
        floor_ns,
    );
    let whole_adds = whole_ns / add_ns;
    println!(
        "\nselection is {:.1}x its floor ({:.1} adds a point against {:.2})",
        whole_adds / floor_adds,
        whole_adds / n_points as f64,
        floor_adds / n_points as f64
    );
    println!(
        "had the builder kept the BigUint keying and walks, they alone would\n\
         cost {:.1} adds a point -- {:.1}x this whole call.",
        (key_ns * 3.0 + frob_ns * 2.0) / add_ns / n_points as f64,
        (key_ns * 3.0 + frob_ns * 2.0) / whole_ns
    );
    println!(
        "what the floor is made of, a point: {:.2} lift algebra + {:.2} orbit step",
        (lift_ns - lower_ns) / add_ns / n_points as f64,
        fastfrob_ns / add_ns / n_points as f64
    );
}
