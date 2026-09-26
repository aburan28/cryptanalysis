//! **What the `m = 4` arm actually pays per `(k, l)`.**
//!
//! `RESEARCH_KOBLITZ_INDEX_CALCULUS.md` names the `m = 4` arm as the
//! one place that still probes a folded table one target at a time,
//! and prices that at "the 265 rather than the 145".  That is the
//! smaller half of what the loop does one at a time.  Its inner step
//! is
//!
//! ```ignore
//! let rest = self.curve.add(target, self.curve.neg(pair));
//! self.pairs_for(rest, &mut pairs);
//! ```
//!
//! and `FastCurve::add` calls `Gf2::inv`, a Fermat inversion — `n − 1`
//! squarings and as many multiplications — where the `m = 3` arm's
//! `add_many` amortises one inversion over a whole block by
//! Montgomery's trick.  This prices the two against each other.
use std::time::Instant;

use cryptanalysis_suite::cryptanalysis::koblitz_fast::{BatchScratch, FastCurve, FastPoint};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::*;

fn main() {
    let degree: u32 = 61;
    let kc = KoblitzCurve::new(0, degree).expect("curve");
    let fc = FastCurve::new(&kc.curve).expect("fast curve");
    let g = fc.lift(kc.generator());
    let n = 200_000usize;

    let pts: Vec<FastPoint> = (1u64..=n as u64)
        .map(|t| fc.mul_u64(g, t * 1_000_003 + 5))
        .filter(|p| !p.infinity)
        .collect();
    let target = fc.mul_u64(g, 7_700_017);
    let xs: Vec<u64> = pts.iter().map(|p| p.x).collect();

    // The Fermat inversion on its own.
    let t0 = Instant::now();
    let mut acc = 0u64;
    for &x in &xs {
        acc ^= fc.field.inv(x);
    }
    let inv_ns = t0.elapsed().as_secs_f64() * 1e9 / xs.len() as f64;
    std::hint::black_box(acc);

    // What the `m = 4` inner step does: one `add` per pair, which is
    // one inversion per pair.
    let negs: Vec<FastPoint> = pts.iter().map(|&p| fc.neg(p)).collect();
    let t0 = Instant::now();
    let mut sink = 0u64;
    for &q in &negs {
        sink ^= fc.add(target, q).x;
    }
    let add_ns = t0.elapsed().as_secs_f64() * 1e9 / negs.len() as f64;
    std::hint::black_box(sink);

    // What the `m = 3` arm does instead: one inversion a block.
    let mut scratch = BatchScratch::default();
    let mut out = Vec::new();
    let t0 = Instant::now();
    for block in negs.chunks(1024) {
        out.clear();
        fc.add_many(target, block, &mut out, &mut scratch);
        sink ^= out[0].x;
    }
    let add_many_ns = t0.elapsed().as_secs_f64() * 1e9 / negs.len() as f64;
    std::hint::black_box(sink);

    println!("at n = {degree}, {} points:", negs.len());
    println!("  Gf2::inv alone                        {inv_ns:8.1} ns");
    println!("  FastCurve::add      (m = 4's step)    {add_ns:8.1} ns  <- one inversion each");
    println!("  add_many, 1024 wide (m = 3's step)    {add_many_ns:8.1} ns");
    println!();
    println!(
        "  the unbatched inversion costs {:.1} ns a pair, {:.0}x the batched step",
        add_ns - add_many_ns,
        add_ns / add_many_ns
    );
    println!(
        "  for comparison, the lone-vs-blocked PROBE difference is about 104 ns,\n  \
         so the inversion is {:.1}x the cost the note named",
        (add_ns - add_many_ns) / 104.0
    );

    // And the arm itself, which is the figure that matters: the `m = 4`
    // scan with a sink that never stops, so the whole `|F|²/2` walk
    // happens and the number is a true per-`(k, l)` cost.  A smaller
    // degree than the rest of this file, because the walk is quadratic
    // and the table has to be built — but not so small that the group
    // is crowded.  At `n = 19` a base this wide decomposes almost every
    // target tens of thousands of ways, and the `|F|`-long compact
    // recovery each hit pays then swamps the walk this is measuring;
    // at `n = 61` the group is far larger than `|F|⁴`, so a target has
    // essentially none and what is left is the walk itself — the
    // arithmetic and the probe, which is where the inversion sits.
    // That isolation is the point: with hits in the stream the
    // `|F|`-long compact recovery each one pays swamps the difference
    // this is measuring.
    let small = KoblitzCurve::new(0, 61).expect("curve");
    let fb = build_subgroup_orbit_factor_base(&small, 5, 400).expect("base");
    let width = fb.points.len();
    let table = PairSumTable::build(&small, &fb).expect("table");
    let sc = FastCurve::new(&small.curve).expect("fast curve");
    let sg = sc.lift(small.generator());
    let pairs_walked = width * (width + 1) / 2;
    let mut walked = 0usize;
    let mut found = 0usize;
    let start = Instant::now();
    for t in 1u64..=4 {
        let target = sc.mul_u64(sg, t * 7_700_017 + 3);
        table.witnesses_fast(target, 4, &mut |_| {
            found += 1;
            true
        });
        walked += pairs_walked;
    }
    let arm_ns = start.elapsed().as_secs_f64() * 1e9 / walked as f64;
    println!();
    println!(
        "  the m = 4 arm at n = {}, |F| = {width} ({} tier), 4 targets:\n  \
         {arm_ns:8.1} ns a (k, l)   [{walked} walked, {found} witnesses]",
        small.n,
        table.tier()
    );
}
