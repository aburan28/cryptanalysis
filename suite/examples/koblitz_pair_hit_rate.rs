//! How the two-summand hit rate actually scales with the factor base.
//!
//! The descent is costed at `2r/|F|²` probes, which assumes `|F|²/2`
//! distinct pair sums spread uniformly over the subgroup. This measures
//! the rate instead of assuming it.
//!
//! cargo run --release --example koblitz_pair_hit_rate -- 61 200000
use cryptanalysis_suite::cryptanalysis::koblitz_fast::FastCurve;
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::*;
use serde_json::json;
use std::collections::HashSet;

fn main() {
    let mut args = std::env::args().skip(1);
    let degree: u32 = args.next().map_or(61, |a| a.parse().unwrap());
    let probes: u64 = args.next().map_or(200_000, |a| a.parse().unwrap());

    let kc = KoblitzCurve::new(0, degree).expect("curve");
    let r = kc.subgroup_order.to_u64_digits()[0] as f64;
    let fc = FastCurve::new(&kc.curve).expect("single-word curve");
    let g = fc.lift(kc.generator());

    for points in [2000usize, 4000, 9000, 18000, 36000] {
        let Ok(fb) = build_subgroup_orbit_factor_base(&kc, 1, points) else {
            continue;
        };
        let n = fb.points.len();
        let Some(table) = PairSumTable::build(&kc, &fb) else {
            continue;
        };
        // Distinct pair sums, for bases small enough to enumerate.
        let distinct = if n <= 9000 {
            let lifted: Vec<_> = fb.points.iter().map(|p| fc.lift(p)).collect();
            let mut seen = HashSet::new();
            for i in 0..n {
                for j in i..n {
                    seen.insert(fc.add(lifted[i], lifted[j]).pack());
                }
            }
            Some(seen.len())
        } else {
            None
        };
        // Empirical hit rate on walked points.
        let stride = fc.mul_u64(g, 0x9e37_79b9_7f4a_7c15);
        let mut target = fc.mul_u64(g, 1_234_567);
        let mut pairs = Vec::new();
        let mut hits = 0u64;
        // Enough probes for a few dozen hits at the predicted rate, so
        // the exponent is measured rather than sampled once.
        let predicted = (n as f64).powi(2) / (2.0 * r);
        let probes = ((probes as f64 / predicted) as u64).clamp(probes, 4_000_000_000);
        for _ in 0..probes {
            if !target.infinity {
                table.pairs_for(target, &mut pairs);
                hits += u64::from(!pairs.is_empty());
            }
            target = fc.add(target, stride);
        }
        let rate = hits as f64 / probes as f64;
        println!(
            "{}",
            json!({
                "base_points": n,
                "stored_pairs": table.len(),
                "distinct_pair_sums": distinct,
                "distinct_over_stored": distinct.map(|d| d as f64 / table.len() as f64),
                "probes": probes,
                "hits": hits,
                "hit_rate": rate,
                "predicted_rate": (n as f64).powi(2) / (2.0 * r),
                "measured_over_predicted": rate / ((n as f64).powi(2) / (2.0 * r)),
            })
        );
    }
}
