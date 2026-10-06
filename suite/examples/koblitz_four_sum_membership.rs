//! Exhaustive, exact group-law four-sum oracle for frozen compact toy bases.
//!
//! Protocol: research/notes/ecc2k130/four_sum_membership_20260925/PROTOCOL.md.
//! Input is a #747 base-header JSON file, a point-only target JSONL file,
//! and a target-count prefix. This is a diagnostic MITM oracle, not a DLP.

use cryptanalysis_suite::cryptanalysis::koblitz_fast_arith::{FastBinaryCurve, FastPoint};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::KoblitzCurve;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::env;
use std::fs;
use std::time::Instant;

const CHUNK: usize = 8192;
type Pair = (u16, u16);

fn encoded(p: FastPoint) -> Value {
    match p {
        None => Value::Null,
        Some((x, y)) => json!([x, y]),
    }
}

fn add_many(curve: &FastBinaryCurve, args: &[(FastPoint, FastPoint)]) -> Vec<FastPoint> {
    let flattened: Vec<_> = args
        .iter()
        .map(|&(p, q)| {
            let (x1, y1, inf1) = p.map_or((0, 0, true), |(x, y)| (x, y, false));
            let (x2, y2, inf2) = q.map_or((0, 0, true), |(x, y)| (x, y, false));
            (x1, y1, x2, y2, inf1, inf2)
        })
        .collect();
    curve.batch_add(&flattened)
}

fn emit_pairs(
    curve: &FastBinaryCurve,
    points: &[FastPoint],
    buffer: &mut Vec<(Pair, FastPoint, FastPoint)>,
    buckets: &mut HashMap<FastPoint, Vec<Pair>>,
) {
    if buffer.is_empty() {
        return;
    }
    let args: Vec<_> = buffer.iter().map(|(_, p, q)| (*p, *q)).collect();
    let sums = add_many(curve, &args);
    for ((pair, p, q), sum) in buffer.drain(..).zip(sums) {
        debug_assert_eq!(p, points[pair.0 as usize]);
        debug_assert_eq!(q, points[pair.1 as usize]);
        buckets.entry(sum).or_default().push(pair);
    }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    assert_eq!(
        args.len(),
        4,
        "usage: koblitz_four_sum_membership BASE_JSON TARGET_JSONL COUNT"
    );
    let base: Value =
        serde_json::from_slice(&fs::read(&args[1]).expect("base file")).expect("base header JSON");
    let n = base["n"].as_u64().expect("n") as u32;
    let r = base["orbit_columns"].as_u64().expect("R") as usize;
    assert!(matches!((n, r), (37, 3) | (41, 8) | (41, 12)));
    assert_eq!(base["a"].as_u64(), Some(0));
    let source = KoblitzCurve::new(0, n).expect("Koblitz toy curve");
    let field = FastBinaryCurve::new(&source.curve.irreducible, 0).expect("single-word curve");
    assert_eq!(
        source.subgroup_order.to_string(),
        base["subgroup_order"].to_string().trim_matches('"')
    );
    let points_raw: Vec<[u64; 2]> =
        serde_json::from_value(base["factor_base_point_coordinates"].clone()).expect("base points");
    assert_eq!(
        points_raw.len(),
        base["factor_base_points"].as_u64().unwrap() as usize
    );
    assert!(points_raw.len() <= u16::MAX as usize);
    let points: Vec<FastPoint> = points_raw.into_iter().map(|[x, y]| Some((x, y))).collect();
    let mut unique_points = BTreeSet::new();
    for &p in &points {
        let (x, y) = p.unwrap();
        assert!(unique_points.insert((x, y)), "duplicate base point");
        assert!(x < (1 << n) && y < (1 << n));
        let lhs = field.gf.sqr(y) ^ field.gf.mul(x, y);
        let rhs = field.gf.mul(field.gf.sqr(x), x) ^ 1;
        assert_eq!(lhs, rhs, "off-curve base point");
    }
    let requested: usize = args[3].parse().expect("target count");
    assert!(requested > 0 && requested <= 512);
    let targets: Vec<[u64; 2]> = fs::read_to_string(&args[2])
        .expect("target file")
        .lines()
        .filter(|line| !line.is_empty())
        .take(requested)
        .map(|line| serde_json::from_str(line).expect("target [x,y]"))
        .collect();
    assert_eq!(targets.len(), requested);

    let started = Instant::now();
    let mut buckets: HashMap<FastPoint, Vec<Pair>> = HashMap::new();
    let mut buffer = Vec::with_capacity(CHUNK);
    for i in 0..points.len() {
        for j in i..points.len() {
            buffer.push(((i as u16, j as u16), points[i], points[j]));
            if buffer.len() == CHUNK {
                emit_pairs(&field, &points, &mut buffer, &mut buckets);
            }
        }
    }
    emit_pairs(&field, &points, &mut buffer, &mut buckets);
    let pair_build_ms = started.elapsed().as_secs_f64() * 1000.0;
    let pair_entries = points.len() * (points.len() + 1) / 2;
    let mut sums: Vec<FastPoint> = buckets.keys().copied().collect();
    sums.sort_unstable();
    let bucket_histogram: BTreeMap<usize, usize> = {
        let mut histogram = BTreeMap::new();
        for pairs in buckets.values() {
            *histogram.entry(pairs.len()).or_default() += 1;
        }
        histogram
    };
    assert_eq!(buckets.values().map(Vec::len).sum::<usize>(), pair_entries);
    println!(
        "{}",
        json!({
            "kind":"complete_four_sum_header", "schema_version":"1.0", "n":n, "R":r,
            "factor_base_points":points.len(), "target_count":targets.len(),
            "pair_entries":pair_entries, "unique_pair_sums":sums.len(),
            "pair_collisions":pair_entries-sums.len(),
            "infinity_pair_entries":buckets.get(&None).map_or(0, Vec::len),
            "bucket_histogram":bucket_histogram,
            "pair_build_ms":pair_build_ms,
            "algorithm":"all i<=j pairs; all distinct sum complements; exact group law; repeated indices and infinity retained"
        })
    );

    let mut query_pairs: Vec<(FastPoint, FastPoint)> = Vec::with_capacity(CHUNK);
    for (index, &[x, y]) in targets.iter().enumerate() {
        assert!(x < (1 << n) && y < (1 << n));
        assert_eq!(
            field.gf.sqr(y) ^ field.gf.mul(x, y),
            field.gf.mul(field.gf.sqr(x), x) ^ 1,
            "off-curve target"
        );
        let target = Some((x, y));
        let query_start = Instant::now();
        let mut tuples: BTreeSet<[u16; 4]> = BTreeSet::new();
        let mut matched_pair_partition_products = 0u64;
        let mut matched_sum_complements = 0u64;
        for chunk in sums.chunks(CHUNK) {
            query_pairs.clear();
            query_pairs.extend(chunk.iter().map(|&sum| (target, FastBinaryCurve::neg(sum))));
            let complements = add_many(&field, &query_pairs);
            for (&sum, remainder) in chunk.iter().zip(complements) {
                let Some(right_pairs) = buckets.get(&remainder) else {
                    continue;
                };
                let left_pairs = &buckets[&sum];
                matched_sum_complements += 1;
                matched_pair_partition_products += (left_pairs.len() * right_pairs.len()) as u64;
                for &(i, j) in left_pairs {
                    for &(k, l) in right_pairs {
                        let mut tuple = [i, j, k, l];
                        tuple.sort_unstable();
                        tuples.insert(tuple);
                    }
                }
            }
        }
        for tuple in &tuples {
            let actual = tuple
                .iter()
                .fold(None, |acc, &i| field.add(acc, points[i as usize]));
            assert_eq!(actual, target, "witness group law mismatch");
        }
        let witnesses: Vec<_> = tuples.into_iter().collect();
        println!(
            "{}",
            json!({
                "kind":"complete_four_sum_target", "index":index, "target":encoded(target),
                "member":!witnesses.is_empty(), "distinct_four_multisets":witnesses.len(),
                "matched_sum_complements":matched_sum_complements,
                "matched_pair_partition_products":matched_pair_partition_products,
                "duplicate_partition_products":matched_pair_partition_products - witnesses.len() as u64,
                "unique_sum_probes":sums.len(), "lookup_count":sums.len(),
                "witnesses":witnesses,
                "query_ms":query_start.elapsed().as_secs_f64() * 1000.0
            })
        );
    }
}
