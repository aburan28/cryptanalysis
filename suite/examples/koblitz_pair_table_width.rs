//! What a compact pair table buys: the base a memory budget affords, and
//! the descent probes that base implies.
//!
//! A stored pair costs sixteen bytes as a `(key, i, j)` triple and about
//! four and a half as an exact rest plus its index and filter. At a
//! fixed budget the base is `|F| = √(2·budget/bytes per pair)`, and the
//! descent needs `2r/|F|²` probes, so the width is what the reach is
//! made of.
//!
//! cargo run --release --example koblitz_pair_table_width -- 53 4
use cryptanalysis_suite::cryptanalysis::koblitz_fast::FastCurve;
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::*;
use serde_json::json;
use std::time::Instant;

/// The largest base of this family whose table fits `budget`.
fn widest(kc: &KoblitzCurve, budget: u128, compact: bool) -> usize {
    let mut lo = 64usize;
    let mut hi = 1 << 20;
    while lo < hi {
        let mid = (lo + hi).div_ceil(2);
        let fits = if compact {
            PairSumTable::compact_byte_size(mid, kc.n) <= budget
        } else {
            PairSumTable::byte_size(mid) <= budget
        };
        if fits {
            lo = mid;
        } else {
            hi = mid - 1;
        }
    }
    lo
}

fn main() {
    let mut args = std::env::args().skip(1);
    let degree: u32 = args.next().map_or(53, |a| a.parse().unwrap());
    let gibibytes: u128 = args.next().map_or(4, |a| a.parse().unwrap());
    let budget = gibibytes << 30;

    let kc = KoblitzCurve::new(0, degree).expect("curve");
    let r = kc.subgroup_order.to_u64_digits()[0] as f64;
    let full = widest(&kc, budget, false);
    let compact = widest(&kc, budget, true);
    println!(
        "{}",
        json!({
            "curve": format!("K_0 / F_2^{degree}"),
            "subgroup_order": kc.subgroup_order.to_string(),
            "budget_gibibytes": gibibytes,
            "widest_base": {"full": full, "compact": compact},
            "descent_probes_per_target": {
                "full": 2.0 * r / (full as f64).powi(2),
                "compact": 2.0 * r / (compact as f64).powi(2),
            },
            "probe_ratio": (compact as f64 / full as f64).powi(2),
        })
    );

    // The same base built both ways, to price the representation itself.
    let points: usize = args.next().map_or(3000, |a| a.parse().unwrap());
    let fb = build_subgroup_orbit_factor_base(&kc, 1, points).expect("factor base");
    let n = fb.points.len();
    for (name, budget) in [
        ("full", PairSumTable::byte_size(n)),
        ("compact", PairSumTable::compact_byte_size(n, kc.n)),
    ] {
        let started = Instant::now();
        let table = PairSumTable::build_within(&kc, &fb, budget).expect("table");
        let build_seconds = started.elapsed().as_secs_f64();
        // Probe cost on points that mostly do not decompose.
        let fc = FastCurve::new(&kc.curve).unwrap();
        let g = fc.lift(kc.generator());
        let mut pairs = Vec::new();
        let mut hits = 0usize;
        let probes = 2_000_000u64;
        // Walked, as the descent walks them, so the timing is the
        // lookup and not a scalar multiplication.
        let stride = fc.mul_u64(g, 0x9e37_79b9);
        let mut target = fc.mul_u64(g, 12345);
        let started = Instant::now();
        for _ in 0..probes {
            if !target.infinity {
                table.pairs_for(target, &mut pairs);
                hits += usize::from(!pairs.is_empty());
            }
            target = fc.add(target, stride);
        }
        let probe_seconds = started.elapsed().as_secs_f64();
        println!(
            "{}",
            json!({
                "representation": name,
                "base_points": n,
                "stored_pairs": table.len(),
                "compact": table.is_compact(),
                "bytes_per_pair": budget as f64 / table.len().max(1) as f64,
                "build_seconds": build_seconds,
                "probes": probes,
                "hits": hits,
                "probe_microseconds": probe_seconds * 1e6 / probes as f64,
            })
        );
    }
}
