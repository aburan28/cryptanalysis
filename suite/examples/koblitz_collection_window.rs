//! Relation collection with a windowed third summand and walked probes:
//! what the window does to the yield, the cost, and the relations a
//! second of collection buys.
//!
//! The full `m = 3` scan finds every triple three times and keeps one.
//! A window of `w` summands keeps all three chances at `w/|F|` of the
//! cost, so relations per *lookup* rise towards three times the full
//! scan's as the window shrinks — paid for with more targets, which is
//! why the probes are walked rather than multiplied.
//!
//! cargo run --release --example koblitz_collection_window -- 41 6000 4096
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::*;
use serde_json::json;
use std::time::Instant;

fn main() {
    let mut args = std::env::args().skip(1);
    let degree: u32 = args.next().map_or(41, |a| a.parse().unwrap());
    let points: usize = args.next().map_or(6000, |a| a.parse().unwrap());
    let trials: u64 = args.next().map_or(4096, |a| a.parse().unwrap());

    let kc = KoblitzCurve::new(0, degree).expect("curve");
    let fb = build_subgroup_orbit_factor_base(&kc, 11, points).expect("factor base");
    let built = Instant::now();
    let pair = PairSumTable::build(&kc, &fb).expect("pair table");
    let build_seconds = built.elapsed().as_secs_f64();
    let base = fb.points.len();

    println!(
        "{}",
        json!({
            "curve": format!("K_0 / F_2^{degree}"),
            "subgroup_order": kc.subgroup_order.to_string(),
            "base_points": base,
            "orbit_columns": fb.unknowns(),
            "pair_entries": pair.len(),
            "pair_build_seconds": build_seconds,
        })
    );

    // Divisor 1 is the full scan with multiplied probes: the control.
    for divisor in [1usize, 2, 4, 8, 16, 32, 64] {
        let window = (divisor > 1).then(|| (base / divisor).max(1));
        let opts = KoblitzIcOptions {
            m: 3,
            strategy: DecompositionStrategy::PairTable,
            collection_window: window,
            ..KoblitzIcOptions::default()
        };
        let collector =
            RelationCollector::with_pair_table(&kc, &fb, &opts, Some(&pair)).expect("collector");
        let unit = RelationWorkUnit {
            seed: 7,
            start: 0,
            count: trials * divisor as u64,
        };
        let (relations, report) = collector.collect(unit);
        // Every relation re-checked in the group, as a consumer would.
        assert!(
            relations
                .iter()
                .all(|r| verify_collected_relation(&kc, &fb, 3, r)),
            "a collected relation failed its group check"
        );
        println!(
            "{}",
            json!({
                "window_divisor": divisor,
                "window": window.unwrap_or(base),
                "walked": window.is_some(),
                "trials": report.trials,
                "relations": report.relations,
                "seconds": report.elapsed_seconds,
                "relations_per_second": report.relations as f64 / report.elapsed_seconds,
                "summands_scanned": report.summands_scanned,
                "summands_per_relation": report.summands_scanned as f64
                    / report.relations.max(1) as f64,
                "seconds_per_relation": report.elapsed_seconds / report.relations.max(1) as f64,
            })
        );
    }
}
