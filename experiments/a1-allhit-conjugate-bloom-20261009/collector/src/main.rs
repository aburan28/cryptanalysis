//! Frozen A1 relation collection stopping at rank five on the full or cross index.

use crypto_lib::cryptanalysis::koblitz_fast_arith::{FastBinaryCurve, FastPoint};
use crypto_lib::cryptanalysis::koblitz_index_calculus::KoblitzCurve;
use serde_json::{json, Value};
use std::collections::{HashMap, HashSet};
use std::env;
use std::fs;
use std::time::Instant;

const DEGREE: usize = 53;
const ORDER: u64 = 21_044_858_204_113;
const INDEX_RECORD_BYTES: usize = 12;
const PACKED_RECORD_BYTES: usize = 10;
const BLOOM_BLOCK_BITS: usize = 512;
const BLOOM_HASHES: usize = 5;
const BLOOM_SALT_ONE: u64 = 0x6a09_e667_f3bc_c909;
const BLOOM_SALT_TWO: u64 = 0xbb67_ae85_84ca_a73b;

#[derive(Clone, Copy)]
struct PairRecord { left: usize, right: usize, relative: usize, side: i8 }

#[derive(Clone, Copy)]
struct Representative { point: FastPoint, scalar: u64, seed: usize }

#[derive(Clone, Copy)]
struct BasePoint { point: FastPoint, rep: usize, shift: usize, sign: i8 }

#[derive(Clone, Copy)]
struct Witness { pair: PairRecord, third: usize, difference: FastPoint }

#[repr(align(64))]
#[derive(Clone)]
struct BloomBlock([u8; 64]);

struct ConjugateBloom { blocks: Vec<BloomBlock> }

#[derive(Default)]
struct ScanCounters {
    nonidentity_differences: usize,
    bloom_negative_checks: usize,
    bloom_positive_checks: usize,
    orbit_key_computations: usize,
    indexed_hits: usize,
    exact_lookup_misses: usize,
}

fn splitmix64_finalizer(mut value: u64) -> u64 {
    value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^ (value >> 31)
}

impl ConjugateBloom {
    fn new(orbits: usize) -> Self {
        // Eight bits per inserted conjugate. Allocate whole 512-bit blocks so
        // every query touches one cache line, including for partial blocks.
        let blocks = (orbits * DEGREE * 8 + BLOOM_BLOCK_BITS - 1) / BLOOM_BLOCK_BITS;
        assert!(blocks > 0);
        let answer = Self { blocks: vec![BloomBlock([0; 64]); blocks] };
        assert_eq!((answer.blocks.as_ptr() as usize) % 64, 0);
        answer
    }

    fn byte_count(&self) -> usize { self.blocks.len() * 64 }

    fn positions(&self, value: u64) -> [usize; BLOOM_HASHES] {
        let first = splitmix64_finalizer(value ^ BLOOM_SALT_ONE);
        let step = splitmix64_finalizer(value ^ BLOOM_SALT_TWO) | 1;
        let block = (first as usize) % self.blocks.len();
        let mut answer = [0; BLOOM_HASHES];
        for (i, position) in answer.iter_mut().enumerate() {
            let offset = ((first >> 32).wrapping_add((i as u64).wrapping_mul(step)) & 511) as usize;
            *position = block * BLOOM_BLOCK_BITS + offset;
        }
        answer
    }

    fn insert(&mut self, value: u64) {
        for position in self.positions(value) {
            self.blocks[position >> 9].0[(position >> 3) & 63] |= 1 << (position & 7);
        }
    }

    fn contains(&self, value: u64) -> bool {
        self.positions(value).into_iter().all(|position|
            self.blocks[position >> 9].0[(position >> 3) & 63] & (1 << (position & 7)) != 0)
    }
}

fn build_bloom(curve: &FastBinaryCurve, index: &HashMap<u64, u32>) -> (ConjugateBloom, u128, u128) {
    let started = Instant::now();
    let mut bloom = ConjugateBloom::new(index.len());
    for &key in index.keys() {
        let mut conjugate = key;
        for _ in 0..DEGREE {
            bloom.insert(conjugate);
            conjugate = curve.gf.sqr(conjugate);
        }
        assert_eq!(conjugate, key);
    }
    let build_ns = started.elapsed().as_nanos();
    let started = Instant::now();
    for &key in index.keys() {
        let mut conjugate = key;
        for _ in 0..DEGREE {
            assert!(bloom.contains(conjugate));
            conjugate = curve.gf.sqr(conjugate);
        }
        assert_eq!(conjugate, key);
    }
    (bloom, build_ns, started.elapsed().as_nanos())
}

fn point(value: &Value) -> FastPoint {
    let coords = value.as_array().expect("encoded affine point");
    assert_eq!(coords.len(), 2);
    Some((coords[0].as_u64().unwrap(), coords[1].as_u64().unwrap()))
}

fn as_u64(value: &Value) -> u64 { value.as_u64().expect("unsigned integer") }

fn mul_mod(a: u64, b: u64) -> u64 { ((a as u128 * b as u128) % ORDER as u128) as u64 }

fn add_mod(a: u64, b: u64) -> u64 {
    let sum = a + b;
    if sum >= ORDER { sum - ORDER } else { sum }
}

fn sub_mod(a: u64, b: u64) -> u64 {
    if a >= b { a - b } else { ORDER - (b - a) }
}

fn signed_mul(a: u64, b: u64, sign: i8) -> u64 {
    let product = mul_mod(a, b);
    if sign == -1 && product != 0 { ORDER - product } else { product }
}

fn scalar_mul(curve: &FastBinaryCurve, mut base: FastPoint, mut scalar: u64) -> FastPoint {
    let mut answer = None;
    while scalar != 0 {
        if scalar & 1 != 0 { answer = curve.add(answer, base); }
        scalar >>= 1;
        if scalar != 0 { base = curve.add(base, base); }
    }
    answer
}

fn frobenius(curve: &FastBinaryCurve, p: FastPoint) -> FastPoint {
    p.map(|(x, y)| (curve.gf.sqr(x), curve.gf.sqr(y)))
}

fn on_curve(curve: &FastBinaryCurve, p: FastPoint) -> bool {
    let Some((x, y)) = p else { return true; };
    let gf = &curve.gf;
    gf.sqr(y) ^ gf.mul(x, y) == gf.mul(gf.sqr(x), x) ^ 1
}

fn orbit_key(curve: &FastBinaryCurve, x: u64) -> u64 {
    let mut current = x;
    let mut minimum = x;
    for _ in 1..DEGREE {
        current = curve.gf.sqr(current);
        minimum = minimum.min(current);
    }
    minimum
}

fn pack_pair(pair: PairRecord) -> u32 {
    assert!(pair.left <= pair.right && pair.right < 128);
    assert!(pair.relative < 64 && (pair.side == 1 || pair.side == -1));
    let positive = u32::from(pair.side == 1);
    (pair.left as u32) | ((pair.right as u32) << 7)
        | ((pair.relative as u32) << 14) | (positive << 20)
}

fn unpack_pair(packed: u32) -> PairRecord {
    assert_eq!(packed >> 21, 0);
    PairRecord { left: (packed & 127) as usize,
                 right: ((packed >> 7) & 127) as usize,
                 relative: ((packed >> 14) & 63) as usize,
                 side: if (packed >> 20) & 1 == 1 { 1 } else { -1 } }
}

fn load_index(raw: &[u8], expected_orbits: usize, representative_count: usize,
              record_bytes: usize) -> HashMap<u64, u32> {
    assert!(record_bytes == INDEX_RECORD_BYTES || record_bytes == PACKED_RECORD_BYTES);
    let payload = if record_bytes == PACKED_RECORD_BYTES {
        assert_eq!(raw.len(), expected_orbits * record_bytes + 4);
        let trailer = u32::from_le_bytes(raw[raw.len()-4..].try_into().unwrap());
        assert_eq!(trailer as usize, expected_orbits);
        &raw[..raw.len()-4]
    } else {
        assert_eq!(raw.len(), expected_orbits * record_bytes);
        raw
    };
    let mut index = HashMap::with_capacity(expected_orbits);
    let mut previous = None;
    for chunk in payload.chunks_exact(record_bytes) {
        let (key, packed) = if record_bytes == PACKED_RECORD_BYTES {
            let mut key_bytes = [0u8; 8];
            key_bytes[..7].copy_from_slice(&chunk[..7]);
            let packed = u32::from_le_bytes([chunk[7], chunk[8], chunk[9], 0]);
            assert_eq!(packed >> 21, 0);
            (u64::from_le_bytes(key_bytes), packed)
        } else {
            let key = u64::from_le_bytes(chunk[0..8].try_into().unwrap());
            let pair = PairRecord { left: chunk[8] as usize, right: chunk[9] as usize,
                                    relative: chunk[10] as usize,
                                    side: if chunk[11] == 1 { 1 } else { -1 } };
            assert!(chunk[11] <= 1);
            (key, pack_pair(pair))
        };
        if let Some(old) = previous { assert!(key > old); }
        previous = Some(key);
        assert!(key < (1u64 << DEGREE));
        let pair = unpack_pair(packed);
        assert!(pair.left <= pair.right && pair.right < representative_count);
        assert!(pair.relative < DEGREE);
        assert!(index.insert(key, packed).is_none());
    }
    assert_eq!(index.len(), expected_orbits);
    index
}

fn scan_all(curve: &FastBinaryCurve, query: FastPoint, start: usize,
            base: &[BasePoint], index: &HashMap<u64, u32>,
            bloom: Option<&ConjugateBloom>, counters: &mut ScanCounters) -> Vec<(Witness, usize)> {
    let mut checked = 0;
    let mut hits = Vec::new();
    let mut pairs = Vec::with_capacity(256);
    for block_start in (0..base.len()).step_by(256) {
        pairs.clear();
        let block_end = (block_start + 256).min(base.len());
        for offset in block_start..block_end {
            let third = base[(start + offset) % base.len()].point.unwrap();
            let (qx, qy, qinf) = match query {
                Some((x, y)) => (x, y, false),
                None => (0, 0, true),
            };
            pairs.push((qx, qy, third.0, third.0 ^ third.1, qinf, false));
        }
        let differences = curve.batch_add(&pairs);
        for (offset, difference) in differences.into_iter().enumerate() {
            checked += 1;
            let Some((x, _)) = difference else { continue; };
            counters.nonidentity_differences += 1;
            if let Some(filter) = bloom {
                if !filter.contains(x) {
                    counters.bloom_negative_checks += 1;
                    continue;
                }
                counters.bloom_positive_checks += 1;
            }
            counters.orbit_key_computations += 1;
            let key = orbit_key(curve, x);
            if let Some(&packed) = index.get(&key) {
                counters.indexed_hits += 1;
                hits.push((Witness {
                    pair: unpack_pair(packed), third: (start + block_start + offset) % base.len(), difference,
                }, checked));
            } else {
                counters.exact_lookup_misses += 1;
            }
        }
    }
    assert_eq!(checked, base.len());
    hits
}

fn verify_and_row(curve: &FastBinaryCurve, query: FastPoint, witness: Witness,
                  base: &[BasePoint], reps: &[Representative], powers: &[Vec<FastPoint>],
                  seeds: &[FastPoint], lam_powers: &[u64]) -> ([u64; 6], usize, i8) {
    let pair = witness.pair;
    let first = reps[pair.left].point;
    let mut second = powers[pair.right][pair.relative];
    if pair.side == -1 { second = FastBinaryCurve::neg(second); }
    let mut sum = curve.add(first, second);
    assert!(sum.is_some());
    let mut alignment = None;
    for shift in 0..DEGREE {
        if witness.difference == sum { alignment = Some((shift, 1)); break; }
        if witness.difference == FastBinaryCurve::neg(sum) {
            alignment = Some((shift, -1)); break;
        }
        sum = frobenius(curve, sum);
    }
    let (shift, global_sign) = alignment.expect("orbit key must reconstruct an exact pair");
    let third = base[witness.third];
    assert_eq!(curve.add(witness.difference, third.point), query);
    let mut row = [0u64; 6];
    let terms = [
        (pair.left, signed_mul(reps[pair.left].scalar, lam_powers[shift], global_sign)),
        (pair.right, signed_mul(reps[pair.right].scalar,
                                lam_powers[(shift + pair.relative) % DEGREE],
                                global_sign * pair.side)),
        (third.rep, signed_mul(reps[third.rep].scalar,
                                lam_powers[third.shift], third.sign)),
    ];
    for (rep, coefficient) in terms {
        let seed = reps[rep].seed;
        row[seed] = add_mod(row[seed], coefficient);
    }
    let mut replay = None;
    for j in 0..6 { replay = curve.add(replay, scalar_mul(curve, seeds[j], row[j])); }
    assert_eq!(replay, query);
    (row, shift, global_sign)
}

fn pow_mod(mut base: u64, mut exponent: u64) -> u64 {
    let mut answer = 1u64;
    while exponent != 0 {
        if exponent & 1 != 0 { answer = mul_mod(answer, base); }
        exponent >>= 1;
        if exponent != 0 { base = mul_mod(base, base); }
    }
    answer
}

fn rank_mod(rows: &[[u64; 5]]) -> usize {
    let mut work = rows.to_vec();
    let mut pivot = 0;
    for column in 0..5 {
        let Some(next) = (pivot..work.len()).find(|&i| work[i][column] != 0) else { continue; };
        work.swap(pivot, next);
        let inv = pow_mod(work[pivot][column], ORDER - 2);
        for j in column..5 { work[pivot][j] = mul_mod(work[pivot][j], inv); }
        for i in 0..work.len() {
            if i == pivot || work[i][column] == 0 { continue; }
            let factor = work[i][column];
            for j in column..5 {
                work[i][j] = sub_mod(work[i][j], mul_mod(factor, work[pivot][j]));
            }
        }
        pivot += 1;
        if pivot == work.len() { break; }
    }
    pivot
}

fn main() {
    let args: Vec<String> = env::args().collect();
    assert_eq!(args.len(), 4,
        "usage: a1-holdout-scanner <base-export.json> <pair-index.bin> <holdout-workload.json>");
    let started = Instant::now();
    let exported: Value = serde_json::from_slice(&fs::read(&args[1]).unwrap()).unwrap();
    let workload: Value = serde_json::from_slice(&fs::read(&args[3]).unwrap()).unwrap();
    assert_eq!(exported["status"], "completed");
    assert_eq!(as_u64(&exported["subgroup_order"]), ORDER);
    assert_eq!(as_u64(&workload["subgroup_order"]), ORDER);
    assert_eq!(workload["seed_points"], exported["seed_points"]);
    if let Some(label) = exported.get("label") { assert_eq!(&workload["label"], label); }
    let curve_source = KoblitzCurve::new(0, DEGREE as u32).unwrap();
    assert_eq!(curve_source.subgroup_order.to_string().parse::<u64>().unwrap(), ORDER);
    assert_eq!(curve_source.curve.irreducible.low_terms, vec![0, 1, 2, 6]);
    let curve = FastBinaryCurve::new(&curve_source.curve.irreducible, 0).unwrap();
    let seeds: Vec<FastPoint> = exported["seed_points"].as_array().unwrap().iter().map(point).collect();
    assert_eq!(seeds.len(), 6);
    let reps: Vec<Representative> = exported["representatives"].as_array().unwrap().iter().map(|v| {
        Representative { point: point(&v["point"]), scalar: as_u64(&v["scalar"]),
                         seed: as_u64(&v["seed_index"]) as usize }
    }).collect();
    assert!(reps.len() == 60 || reps.len() == 120);
    for rep in &reps {
        assert!(rep.seed < 6 && on_curve(&curve, rep.point));
        assert_eq!(scalar_mul(&curve, seeds[rep.seed], rep.scalar), rep.point);
    }
    let mut powers = Vec::with_capacity(reps.len());
    for rep in &reps {
        let mut orbit = Vec::with_capacity(DEGREE);
        let mut p = rep.point;
        for _ in 0..DEGREE { orbit.push(p); p = frobenius(&curve, p); }
        assert_eq!(p, rep.point);
        powers.push(orbit);
    }
    let base: Vec<BasePoint> = exported["ordered_base"].as_array().unwrap().iter().map(|v| {
        BasePoint { point: point(&v["point"]), rep: as_u64(&v["rep_index"]) as usize,
                    shift: as_u64(&v["frobenius_shift"]) as usize,
                    sign: v["sign"].as_i64().unwrap() as i8 }
    }).collect();
    assert_eq!(base.len(), reps.len() * 106);
    for item in &base {
        assert!(item.rep < reps.len() && item.shift < DEGREE && (item.sign == 1 || item.sign == -1));
        let mut expected = powers[item.rep][item.shift];
        if item.sign == -1 { expected = FastBinaryCurve::neg(expected); }
        assert_eq!(expected, item.point);
    }
    let lam = as_u64(&exported["frobenius_scalar"]);
    let mut lam_powers = vec![1u64; DEGREE + 1];
    for i in 1..=DEGREE { lam_powers[i] = mul_mod(lam_powers[i-1], lam); }
    assert_eq!(lam_powers[DEGREE], 1);
    let raw_index = fs::read(&args[2]).unwrap();
    let record_bytes = exported.get("pair_index_record_bytes")
        .map(|value| as_u64(value) as usize).unwrap_or(INDEX_RECORD_BYTES);
    let expected_orbits = if record_bytes == PACKED_RECORD_BYTES {
        assert_eq!(exported["pair_index_trailer"], "u32_le_record_count");
        assert!(raw_index.len() >= 4 && (raw_index.len()-4) % record_bytes == 0);
        (raw_index.len()-4) / record_bytes
    } else {
        assert_eq!(record_bytes, INDEX_RECORD_BYTES);
        assert_eq!(raw_index.len() % record_bytes, 0);
        raw_index.len() / record_bytes
    };
    if let Some(orbits) = exported.get("distinct_nonidentity_pair_orbits") {
        assert_eq!(expected_orbits, as_u64(orbits) as usize);
    } else {
        assert!(reps.len() == 120 && expected_orbits == 735_000);
    }
    let index = load_index(&raw_index, expected_orbits, reps.len(), record_bytes);
    let bloom_enabled = match env::var("A1_CONJUGATE_BLOOM") {
        Ok(value) if value == "1" => true,
        Ok(value) if value == "0" => false,
        Err(env::VarError::NotPresent) => false,
        other => panic!("A1_CONJUGATE_BLOOM must be 0 or 1: {other:?}"),
    };
    let (bloom, bloom_build_ns, bloom_check_ns) = if bloom_enabled {
        let (filter, build_ns, check_ns) = build_bloom(&curve, &index);
        (Some(filter), build_ns, check_ns)
    } else { (None, 0, 0) };
    let queries = workload["queries"].as_array().unwrap();
    assert_eq!(queries.len(), as_u64(&workload["query_count"]) as usize);
    assert_eq!(queries.len(), 2_048);
    let setup_wall_ns = started.elapsed().as_nanos();

    let collection_started = Instant::now();
    let mut query_ns = 0u128;
    let mut pdp_ns = 0u128;
    let mut relation_check_ns = 0u128;
    let mut rank_update_ns = 0u128;
    let mut checked_total = 0usize;
    let mut processed_queries = 0usize;
    let mut events = Vec::new();
    let mut rank_rows: Vec<[u64; 5]> = Vec::new();
    let mut raw_hit_incidences = 0usize;
    let mut distinct_weighted_rows = 0usize;
    let mut scan_counters = ScanCounters::default();
    for (query_index, query_record) in queries.iter().enumerate() {
        processed_queries += 1;
        let tick = Instant::now();
        let scalar = as_u64(&query_record["known_scalar"]);
        let original_start = as_u64(&query_record["base_start"]);
        assert!(0 < scalar && scalar < ORDER && original_start < 12_720);
        let base_start = original_start as usize % base.len();
        let query = scalar_mul(&curve, seeds[0], scalar);
        query_ns += tick.elapsed().as_nanos();
        let tick = Instant::now();
        let hits = scan_all(&curve, query, base_start, &base, &index,
                            bloom.as_ref(), &mut scan_counters);
        pdp_ns += tick.elapsed().as_nanos();
        checked_total += base.len();
        raw_hit_incidences += hits.len();
        if !hits.is_empty() {
            let tick = Instant::now();
            let mut incidence_records = Vec::new();
            let mut seen_rows = HashSet::new();
            let mut new_rows = Vec::new();
            for (witness, position) in hits {
                let (row, shift, global_sign) = verify_and_row(
                    &curve, query, witness, &base, &reps, &powers, &seeds, &lam_powers);
                let pair = witness.pair;
                if seen_rows.insert(row) { new_rows.push(row); }
                incidence_records.push(json!({"position":position, "third_base_index":witness.third,
                    "pair_record":[pair.left,pair.right,pair.relative,pair.side],
                    "global_shift":shift,"global_sign":global_sign,"row":row}));
            }
            relation_check_ns += tick.elapsed().as_nanos();
            let tick = Instant::now();
            distinct_weighted_rows += new_rows.len();
            for row in &new_rows { rank_rows.push([row[1], row[2], row[3], row[4], row[5]]); }
            let rank = rank_mod(&rank_rows);
            rank_update_ns += tick.elapsed().as_nanos();
            events.push(json!({"query_index": query_index + 1,
                "source_batch":query_record["source_batch"],
                "source_query_index":query_record["source_query_index"],
                "known_scalar": scalar,"base_start":base_start,
                "raw_hit_incidences":incidence_records.len(),
                "distinct_weighted_rows":new_rows.len(),"rows":new_rows,
                "incidences":incidence_records,"matrix_rank":rank}));
            if rank == 5 { break; }
        }
    }
    let wall_ns = collection_started.elapsed().as_nanos();
    let residual = wall_ns.saturating_sub(query_ns + pdp_ns + relation_check_ns + rank_update_ns);
    query_ns += residual;
    assert_eq!(query_ns + pdp_ns + relation_check_ns + rank_update_ns, wall_ns);
    let final_rank = rank_mod(&rank_rows);
    assert_eq!(checked_total, processed_queries * base.len());
    assert_eq!(scan_counters.orbit_key_computations,
               scan_counters.indexed_hits + scan_counters.exact_lookup_misses);
    assert_eq!(scan_counters.indexed_hits, raw_hit_incidences);
    if bloom_enabled {
        assert_eq!(scan_counters.nonidentity_differences,
                   scan_counters.bloom_negative_checks + scan_counters.bloom_positive_checks);
        assert_eq!(scan_counters.orbit_key_computations, scan_counters.bloom_positive_checks);
    } else {
        assert_eq!(scan_counters.nonidentity_differences, scan_counters.orbit_key_computations);
    }
    println!("{}", json!({"status":if final_rank == 5 { "verified" } else { "censored" }, "label":workload["label"],
        "workload_id":workload["workload_id"], "query_stream_id":workload["query_stream_id"],
        "actual_usable_B":base.len(),"pair_index_orbits":index.len(),
        "pair_index_record_bytes":record_bytes,"pair_index_binary_bytes":raw_index.len(),
        "query_count":processed_queries,"available_query_count":queries.len(),
        "stop_criterion":"five_unknown_seed_log_columns_rank_five",
        "verified_relation_queries":events.len(),
        "raw_hit_incidences":raw_hit_incidences,"distinct_weighted_rows":distinct_weighted_rows,
        "initial_rank":0,"final_rank":final_rank,"base_points_checked":checked_total,
        "conjugate_bloom_enabled":bloom_enabled,
        "conjugate_bloom_bytes":bloom.as_ref().map_or(0, ConjugateBloom::byte_count),
        "conjugate_bloom_build_ns_excluded":bloom_build_ns,
        "conjugate_bloom_check_ns_excluded":bloom_check_ns,
        "nonidentity_differences":scan_counters.nonidentity_differences,
        "bloom_negative_checks":scan_counters.bloom_negative_checks,
        "bloom_positive_checks":scan_counters.bloom_positive_checks,
        "orbit_key_computations":scan_counters.orbit_key_computations,
        "indexed_hits":scan_counters.indexed_hits,
        "exact_lookup_misses":scan_counters.exact_lookup_misses,
        "relation_events":events,"collection_wall_ns":wall_ns,
        "collection_phase_ns":{"queries":query_ns,"PDP":pdp_ns,
            "relation_check":relation_check_ns,"rank_update":rank_update_ns},
        "timer_residual_ns_in_queries":residual,"setup_wall_ns_excluded":setup_wall_ns,
        "cpu_isolation":"unverified"}));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_conjugate_is_present_and_exact_lookup_rejects_false_positives() {
        let source = KoblitzCurve::new(0, DEGREE as u32).unwrap();
        let curve = FastBinaryCurve::new(&source.curve.irreducible, 0).unwrap();
        let index: HashMap<u64, u32> = (2..8).map(|x| (orbit_key(&curve, x), 0)).collect();
        let (bloom, _, _) = build_bloom(&curve, &index);
        for &key in index.keys() {
            let mut conjugate = key;
            for _ in 0..DEGREE {
                assert!(bloom.contains(conjugate));
                assert!(index.contains_key(&orbit_key(&curve, conjugate)));
                conjugate = curve.gf.sqr(conjugate);
            }
        }
        let mut negatives = 0;
        let mut positive_exact_misses = 0;
        for x in 0..10_000 {
            let exact = index.contains_key(&orbit_key(&curve, x));
            let maybe = bloom.contains(x);
            assert!(!exact || maybe);
            if !maybe { negatives += 1; }
            if maybe && !exact { positive_exact_misses += 1; }
        }
        assert!(negatives > 0);
        assert!(positive_exact_misses > 0);
    }
}
