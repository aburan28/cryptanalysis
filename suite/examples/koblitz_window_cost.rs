//! What a windowed `m = 3` scan costs per summand, against the window.
//!
//! The collection-window round priced its scans with the constant
//! measured on the *full* scan — `witnesses_fast` over the whole base —
//! because that was the only scan shape measured.  A windowed scan is
//! not that shape: it pays the same per-target prologue over `w`
//! summands instead of `|F|` of them, so its cost per summand rises as
//! the window narrows, and pricing a 256-summand window at the full
//! scan's figure undercharges it.
//!
//! This measures the curve, so a windowed run can be charged at the
//! figure for the window it used.  A window at least as wide as the base
//! is the full scan and is the right-hand end of the same curve, which
//! is what makes the two comparable.
//!
//! The per-target cost has to be the one collection pays, which is one
//! addition to walk to the next probe.  A first version of this drew
//! each target with a scalar multiplication instead; that is about 59
//! chained additions, and dividing it over 256 summands rather than
//! 15,744 invented a fourfold window penalty out of the harness.  The
//! walk is not a detail of the measurement, it is the thing measured.
//!
//!     cargo run --release --example koblitz_window_cost -- 41 15300
use cryptanalysis_suite::cryptanalysis::koblitz_fast::{BatchScratch, FastCurve, FastPoint};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::*;
use std::time::Instant;

const ADDS: usize = 2_000_000;
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
    let kc = KoblitzCurve::new(0, degree).expect("curve");
    let fb = build_subgroup_orbit_factor_base(&kc, 1, points).expect("factor base");
    let fc = FastCurve::new(&kc.curve).expect("fast curve");
    let table = PairSumTable::build_folded_within(&kc, &fb, PairSumTable::DEFAULT_BYTE_BUDGET)
        .expect("folded table");
    let base = fb.points.len();

    let g = fc.lift(kc.generator());
    let batch: Vec<FastPoint> = (0..1024).map(|i| fc.lift(&fb.points[i % base])).collect();
    let mut bscratch = BatchScratch::default();
    let mut out: Vec<FastPoint> = Vec::with_capacity(batch.len());
    let rounds = ADDS / batch.len();
    let t = Instant::now();
    for _ in 0..rounds {
        out.clear();
        fc.add_many(g, &batch, &mut out, &mut bscratch);
    }
    let add_ns = t.elapsed().as_secs_f64() * 1e9 / (rounds * batch.len()) as f64;
    std::hint::black_box(out.len());
    println!("base {base} points, degree {degree}");
    println!("one batched group addition = {add_ns:.2} ns   <- the unit");
    println!(
        "\n{:>8} {:>10} {:>11} {:>14}",
        "window", "ns/summand", "adds/summand", "vs full scan"
    );

    let mut windows: Vec<usize> = vec![64, 128, 256, 512, 1024, 2048, 4096, 8192, base];
    windows.retain(|&w| w <= base);
    windows.dedup();
    let mut full: Option<f64> = None;
    let mut scratch = ScanScratch::default();
    // The target is *walked*, by one addition, exactly as collection
    // walks it.  Drawing each target with `mul_u64` instead would put a
    // scalar multiplication — some 59 chained additions, about 39 us on
    // this host — inside the per-target cost, which a narrow window
    // divides over few summands and a full scan over many: the window
    // curve would then be a picture of the harness rather than of the
    // scan.  Collection pays one addition per trial, so this does.
    let stride = fc.mul_u64(g, 7_700_017);
    for &w in &windows {
        let mut scanned = 0usize;
        let mut targets = 0usize;
        let mut t = fc.mul_u64(g, 12_345);
        let start = Instant::now();
        while start.elapsed().as_secs_f64() < SECONDS {
            targets += 1;
            t = fc.add(t, stride);
            // The never-stopping sink, so the whole window is walked and
            // the figure is a true per-summand cost rather than one that
            // depends on how soon a witness turns up.
            table.witnesses_fast_scan(
                t,
                3,
                Scan::Cyclic {
                    start: (targets * 7919) % base,
                    len: w,
                },
                &mut scratch,
                &mut |_| true,
            );
            scanned += w;
        }
        let ns = start.elapsed().as_secs_f64() * 1e9 / scanned as f64;
        let adds = ns / add_ns;
        if w == base {
            full = Some(adds);
        }
        println!(
            "{w:>8} {ns:>10.1} {adds:>11.2} {:>14}",
            match full {
                Some(f) => format!("{:.2}", adds / f),
                None => "-".to_string(),
            }
        );
    }
    if let Some(f) = full {
        println!(
            "\nfull scan is {f:.2} adds a summand; a narrow window costs more per\n\
             summand, so a windowed run priced at the full scan's figure has been\n\
             undercharged.  Re-price with the row for the window it ran."
        );
    }
}
