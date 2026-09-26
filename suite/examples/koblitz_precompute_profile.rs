//! Where the logarithm precompute's wall time goes at a given degree.
//! cargo run --release --example koblitz_precompute_profile -- 53 15000
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::*;
use serde_json::json;
use std::time::Instant;

fn main() {
    let mut args = std::env::args().skip(1);
    let degree: u32 = args.next().map_or(53, |a| a.parse().unwrap());
    let points: usize = args.next().map_or(15000, |a| a.parse().unwrap());

    let t = Instant::now();
    let kc = KoblitzCurve::new(0, degree).expect("curve");
    let curve_seconds = t.elapsed().as_secs_f64();

    let t = Instant::now();
    let fb = build_subgroup_orbit_factor_base(&kc, 1, points).expect("factor base");
    let base_seconds = t.elapsed().as_secs_f64();

    let t = Instant::now();
    let columns = projected_signed_orbit_count(&kc, &fb);
    let orbit_map_seconds = t.elapsed().as_secs_f64();

    let t = Instant::now();
    let pair = PairSumTable::build(&kc, &fb).expect("pair table");
    let pair_seconds = t.elapsed().as_secs_f64();

    println!(
        "{}",
        json!({
            "degree": degree,
            "base_points": fb.points.len(),
            "columns": columns,
            "pair_entries": pair.len(),
            "pair_table_compact": pair.is_compact(),
            "pair_table_bytes": if pair.is_compact() {
                PairSumTable::compact_byte_size(fb.points.len(), kc.n)
            } else {
                PairSumTable::byte_size(fb.points.len())
            },
            "curve_seconds": curve_seconds,
            "factor_base_seconds": base_seconds,
            "orbit_map_seconds": orbit_map_seconds,
            "pair_table_seconds": pair_seconds,
        })
    );
}
