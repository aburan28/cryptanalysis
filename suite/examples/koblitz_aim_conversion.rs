//! What an aimed scan costs per summand, as a function of how many
//! summands it is aiming at.
//!
//! [`Scan::Indices`] gathers its summands, because a column's points are
//! not contiguous in the base ordering, and that gather is a scattered
//! read.  Its cost is therefore not one number: a scan aimed at two
//! remaining columns touches a few hundred points that stay in cache
//! across trials, while one aimed at half the base touches more than the
//! cache holds and pays a miss per summand.
//!
//! A run's aimed set *shrinks* as coverage grows, so pricing every aimed
//! scan at the cost measured on a large set overcharges the end of the
//! run and pricing them all at a small set's cost undercharges the
//! start.  This measures the curve so each unit can be charged at the
//! size it actually scanned.
//!
//! The subsets are unions of whole signed orbits, which is what aiming
//! really scans — not a stride, whose reads are evenly spread and so
//! neither as local as a small target set nor as costly as a scattered
//! one.
//!
//!     cargo run --release --example koblitz_aim_conversion -- 41 15300
use cryptanalysis_suite::cryptanalysis::koblitz_fast::{BatchScratch, FastCurve, FastPoint};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::*;
use std::time::Instant;

const ADDS: usize = 2_000_000;
/// Seconds per shape, long enough that the clock is not the measurement.
const SECONDS: f64 = 2.0;

fn main() {
    let degree: u32 = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(41);
    let points: usize = std::env::args()
        .nth(2)
        .and_then(|s| s.parse().ok())
        .unwrap_or(15300);
    let window: usize = std::env::args()
        .nth(3)
        .and_then(|s| s.parse().ok())
        .unwrap_or(256);
    let kc = KoblitzCurve::new(0, degree).expect("curve");
    let fb = build_subgroup_orbit_factor_base(&kc, 1, points).expect("factor base");
    let fc = FastCurve::new(&kc.curve).expect("fast curve");
    let table = PairSumTable::build_folded_within(&kc, &fb, PairSumTable::DEFAULT_BYTE_BUDGET)
        .expect("folded table");
    let base = fb.points.len();
    let columns = fb.signed_orbits.len();

    // The unit: one batched affine addition, as everywhere else.
    let g = fc.lift(kc.generator());
    let batch: Vec<FastPoint> = (0..1024).map(|i| fc.lift(&fb.points[i % base])).collect();
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
    println!("base {base} points, {columns} columns, degree {degree}, window {window}");
    println!("one batched group addition = {add_ns:.2} ns   <- the unit");

    // The swept window, for the same window width, as the reference the
    // aimed scan has to beat per relation rather than per scan.
    // The target is walked by one addition, as collection walks it: a
    // scalar multiplication per target is some 59 chained additions and
    // would sit inside the per-summand figure, larger the narrower the
    // scan.
    let stride = fc.mul_u64(g, 7_700_017);
    let mut swept = 0usize;
    let mut n_targets = 0usize;
    let mut t = fc.mul_u64(g, 12_345);
    let start = Instant::now();
    while start.elapsed().as_secs_f64() < SECONDS {
        n_targets += 1;
        t = fc.add(t, stride);
        table.decompose_fast_window(t, 3, (n_targets * 7919) % base, window);
        swept += window;
    }
    let swept_ns = start.elapsed().as_secs_f64() * 1e9 / swept as f64;
    println!(
        "\nswept window: {swept_ns:.1} ns a summand = {:.2} adds",
        swept_ns / add_ns
    );

    println!(
        "\n{:>8} {:>8} {:>9} {:>9} {:>9} {:>9}",
        "columns", "points", "window", "ns/scan", "adds/scan", "vs swept"
    );
    // Column counts spanning what a run really aims at: the last column
    // or two at the end, a tenth of the base in the middle, and the
    // whole base at the start, where aiming is the sweep.
    let mut counts: Vec<usize> = vec![1, 2, 4, 8, 16, 32, 64, 96, 128, 160, columns];
    counts.retain(|&c| c <= columns);
    counts.dedup();
    for &ncols in &counts {
        // Whole orbits, taken evenly across the base so the set is as
        // scattered as a real set of missing columns.
        let col_stride = (columns / ncols).max(1);
        let mut idxs: Vec<u32> = Vec::new();
        for c in (0..columns).step_by(col_stride).take(ncols) {
            idxs.extend(fb.signed_orbits[c].iter().map(|&i| i as u32));
        }
        idxs.sort_unstable();
        let w = window.min(idxs.len());
        // The doubled list the collector builds, so the rotation is a
        // contiguous slice exactly as it is in a run.
        let mut doubled = idxs.clone();
        doubled.extend_from_slice(&idxs[..w]);
        let mut scratch = ScanScratch::default();
        let mut scanned = 0usize;
        let mut targets = 0usize;
        let mut t = fc.mul_u64(g, 12_345);
        let start = Instant::now();
        while start.elapsed().as_secs_f64() < SECONDS {
            targets += 1;
            t = fc.add(t, stride);
            let off = (targets * 7919) % idxs.len();
            table.decompose_fast_scan(t, 3, Scan::Indices(&doubled[off..off + w]), &mut scratch);
            scanned += w;
        }
        let ns = start.elapsed().as_secs_f64() * 1e9 / scanned as f64;
        println!(
            "{ncols:>8} {:>8} {w:>9} {ns:>9.1} {:>9.2} {:>9.2}",
            idxs.len(),
            ns / add_ns,
            ns / swept_ns
        );
    }
    println!(
        "\nprice each unit at the figure for the set it scanned: a run's aimed\n\
         set shrinks as coverage grows, so one constant over the whole run is\n\
         an assumption, not a measurement."
    );
}
