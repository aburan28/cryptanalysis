#![recursion_limit = "256"]
//! Same-point A1 target scanner with a frozen full or cross-class pair index.

use crypto_lib::cryptanalysis::koblitz_fast_arith::{FastBinaryCurve, FastPoint};
use crypto_lib::cryptanalysis::koblitz_index_calculus::KoblitzCurve;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::env;
use std::fs;
use std::io::{BufReader, Read};
use std::time::Instant;

const DEGREE: usize = 53;
const ORDER: u64 = 21_044_858_204_113;
const INDEX_RECORD_BYTES: usize = 12;
const PACKED_RECORD_BYTES: usize = 10;
const BLOOM_ORBITS: usize = 442_994;
const BLOOM_BLOCK_BITS: usize = 512;
const BLOOM_BLOCKS: usize = (BLOOM_ORBITS * DEGREE * 8 + BLOOM_BLOCK_BITS - 1) / BLOOM_BLOCK_BITS;
const BLOOM_BITS: usize = BLOOM_BLOCKS * BLOOM_BLOCK_BITS;
const BLOOM_HASHES: u64 = 5;
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
struct Block([u8; 64]);

struct Bloom { blocks: Vec<Block> }

fn sha256_hex(raw: &[u8]) -> String {
    Sha256::digest(raw).iter().map(|byte| format!("{byte:02x}")).collect()
}

fn current_binary_sha256() -> String {
    sha256_hex(&fs::read(env::current_exe().unwrap()).unwrap())
}

#[derive(Default)]
struct ScanCounters {
    nonidentity_differences: usize,
    bloom_negative_checks: usize,
    bloom_positive_checks: usize,
    orbit_key_computations: usize,
    indexed_hits: usize,
    positive_lookup_misses: usize,
}

fn splitmix64_finalizer(mut value: u64) -> u64 {
    value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^ (value >> 31)
}

impl Bloom {
    fn new() -> Self {
        assert_eq!(BLOOM_BITS % 8, 0);
        let bloom = Self { blocks: vec![Block([0u8; 64]); BLOOM_BLOCKS] };
        bloom.assert_alignment();
        bloom
    }

    fn read_direct(path: &str) -> (Self, String, u128) {
        let started = Instant::now();
        let file = fs::File::open(path).unwrap();
        assert_eq!(file.metadata().unwrap().len(), (BLOOM_BITS/8) as u64);
        let mut reader = BufReader::with_capacity(1 << 20, file);
        let mut bloom = Self::new();
        let mut hasher = Sha256::new();
        for block in &mut bloom.blocks {
            reader.read_exact(&mut block.0).unwrap();
            hasher.update(&block.0);
        }
        let mut trailing = [0u8; 1];
        assert_eq!(reader.read(&mut trailing).unwrap(), 0);
        bloom.assert_alignment();
        let bits_sha256: String = hasher.finalize().iter()
            .map(|byte| format!("{byte:02x}")).collect();
        (bloom, bits_sha256, started.elapsed().as_nanos())
    }

    fn to_bytes(&self) -> Vec<u8> {
        let mut bits = Vec::with_capacity(BLOOM_BITS/8);
        for block in &self.blocks { bits.extend_from_slice(&block.0); }
        assert_eq!(bits.len(), BLOOM_BITS/8);
        bits
    }

    fn len_bytes(&self) -> usize { self.blocks.len() * 64 }

    fn pointer_mod64(&self) -> usize { (self.blocks.as_ptr() as usize) % 64 }

    fn assert_alignment(&self) {
        assert_eq!(std::mem::align_of::<Block>(), 64);
        assert_eq!(std::mem::size_of::<Block>(), 64);
        assert_eq!(self.pointer_mod64(), 0);
    }

    fn positions(value: u64) -> [usize; BLOOM_HASHES as usize] {
        let first = splitmix64_finalizer(value ^ BLOOM_SALT_ONE);
        let step = splitmix64_finalizer(value ^ BLOOM_SALT_TWO) | 1;
        let block_start = ((first as usize) % BLOOM_BLOCKS) * BLOOM_BLOCK_BITS;
        let mut positions = [0usize; BLOOM_HASHES as usize];
        for (i,position) in positions.iter_mut().enumerate() {
            let offset = ((first >> 32).wrapping_add((i as u64).wrapping_mul(step))
                          & (BLOOM_BLOCK_BITS as u64 - 1)) as usize;
            *position = block_start + offset;
        }
        positions
    }

    fn insert(&mut self, value: u64) {
        for position in Self::positions(value) {
            self.blocks[position >> 9].0[(position >> 3) & 63] |= 1u8 << (position & 7);
        }
    }

    fn contains(&self, value: u64) -> bool {
        Self::positions(value).into_iter().all(|position|
            self.blocks[position >> 9].0[(position >> 3) & 63] &
            (1u8 << (position & 7)) != 0)
    }
}

fn check_bloom(curve: &FastBinaryCurve, index: &HashMap<u64,u32>, bloom: &Bloom) -> u128 {
    let checked = Instant::now();
    for &key in index.keys() {
        let mut conjugate = key;
        for _ in 0..DEGREE {
            assert!(bloom.contains(conjugate));
            conjugate = curve.gf.sqr(conjugate);
        }
        assert_eq!(conjugate, key);
    }
    checked.elapsed().as_nanos()
}

fn build_bloom(curve: &FastBinaryCurve, index: &HashMap<u64,u32>) -> (Bloom,u128,u128) {
    assert_eq!(index.len(), BLOOM_ORBITS);
    let started = Instant::now();
    let mut bloom = Bloom::new();
    for &key in index.keys() {
        let mut conjugate = key;
        for _ in 0..DEGREE {
            bloom.insert(conjugate);
            conjugate = curve.gf.sqr(conjugate);
        }
        assert_eq!(conjugate, key);
    }
    let build_ns = started.elapsed().as_nanos();
    let check_ns = check_bloom(curve,index,&bloom);
    assert_eq!(bloom.len_bytes(), BLOOM_BITS/8);
    (bloom,build_ns,check_ns)
}

fn verify_cache_manifest(manifest: &Value, raw_index: &[u8], bits_sha256: &str, bits_len: usize) {
    assert_eq!(manifest["status"], "verified");
    assert_eq!(as_u64(&manifest["schema_version"]), 1);
    assert_eq!(as_u64(&manifest["field_degree"]), DEGREE as u64);
    assert_eq!(as_u64(&manifest["pair_index_orbits"]), BLOOM_ORBITS as u64);
    assert_eq!(as_u64(&manifest["bit_count"]), BLOOM_BITS as u64);
    assert_eq!(as_u64(&manifest["block_bits"]), BLOOM_BLOCK_BITS as u64);
    assert_eq!(as_u64(&manifest["block_count"]), BLOOM_BLOCKS as u64);
    assert_eq!(as_u64(&manifest["allocation_alignment_bytes"]), 64);
    assert_eq!(as_u64(&manifest["builder_allocation_pointer_mod64"]), 0);
    assert_eq!(as_u64(&manifest["byte_count"]), bits_len as u64);
    assert_eq!(as_u64(&manifest["hash_count"]), BLOOM_HASHES);
    assert_eq!(as_u64(&manifest["salt_one"]), BLOOM_SALT_ONE);
    assert_eq!(as_u64(&manifest["salt_two"]), BLOOM_SALT_TWO);
    assert_eq!(manifest["builder_exhaustive_check"], true);
    assert_eq!(manifest["index_sha256"], sha256_hex(raw_index));
    assert_eq!(manifest["bits_sha256"], bits_sha256);
    assert_eq!(manifest["binary_sha256"], current_binary_sha256());
    assert_eq!(bits_len, BLOOM_BITS/8);
}

fn cache_mode(args: &[String]) {
    assert!(args.len() == 4 || args.len() == 5);
    let raw_index = fs::read(&args[2]).unwrap();
    let index = load_index(&raw_index,BLOOM_ORBITS,120,PACKED_RECORD_BYTES);
    let curve_source = KoblitzCurve::new(0,DEGREE as u32).unwrap();
    assert_eq!(curve_source.curve.irreducible.low_terms,vec![0,1,2,6]);
    let curve = FastBinaryCurve::new(&curve_source.curve.irreducible,0).unwrap();
    if args[1] == "--build-cache" {
        assert_eq!(args.len(),4);
        assert!(!std::path::Path::new(&args[3]).exists());
        let (bloom,build_ns,check_ns) = build_bloom(&curve,&index);
        bloom.assert_alignment();
        let serialized = bloom.to_bytes();
        fs::write(&args[3],&serialized).unwrap();
        println!("{}",json!({"status":"verified","mode":"build-cache",
            "index_sha256":sha256_hex(&raw_index),
            "bits_sha256":sha256_hex(&serialized),
            "binary_sha256":current_binary_sha256(),
            "pair_index_orbits":BLOOM_ORBITS,"bit_count":BLOOM_BITS,
            "block_bits":BLOOM_BLOCK_BITS,"block_count":BLOOM_BLOCKS,
            "byte_count":bloom.len_bytes(),"hash_count":BLOOM_HASHES,
            "allocation_alignment_bytes":64,
            "allocation_pointer_mod64":bloom.pointer_mod64(),
            "salt_one":BLOOM_SALT_ONE,"salt_two":BLOOM_SALT_TWO,
            "build_wall_ns_exploratory":build_ns,
            "exhaustive_check_wall_ns_exploratory":check_ns,
            "builder_exhaustive_check":true}));
    } else {
        assert_eq!(args[1],"--check-cache");
        assert_eq!(args.len(),5);
        let (bloom,bits_sha256,direct_load_hash_ns) = Bloom::read_direct(&args[3]);
        let manifest: Value = serde_json::from_slice(&fs::read(&args[4]).unwrap()).unwrap();
        verify_cache_manifest(&manifest,&raw_index,&bits_sha256,bloom.len_bytes());
        let check_ns = check_bloom(&curve,&index,&bloom);
        println!("{}",json!({"status":"verified","mode":"check-cache",
            "index_sha256":sha256_hex(&raw_index),
            "bits_sha256":manifest["bits_sha256"],
            "binary_sha256":current_binary_sha256(),
            "pair_index_orbits":BLOOM_ORBITS,
            "allocation_alignment_bytes":64,
            "allocation_pointer_mod64":bloom.pointer_mod64(),
            "direct_load_hash_wall_ns_exploratory":direct_load_hash_ns,
            "exhaustive_check_wall_ns_exploratory":check_ns,
            "all_index_conjugates_positive":true}));
    }
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

fn scan(curve: &FastBinaryCurve, query: FastPoint, start: usize,
        base: &[BasePoint], index: &HashMap<u64, u32>, bloom: &Bloom)
        -> (Option<Witness>, usize, ScanCounters) {
    let mut checked = 0;
    let mut counters = ScanCounters::default();
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
            if !bloom.contains(x) {
                counters.bloom_negative_checks += 1;
                continue;
            }
            counters.bloom_positive_checks += 1;
            counters.orbit_key_computations += 1;
            let key = orbit_key(curve, x);
            if let Some(&packed) = index.get(&key) {
                counters.indexed_hits += 1;
                return (Some(Witness {
                    pair: unpack_pair(packed), third: (start + block_start + offset) % base.len(), difference,
                }), checked, counters);
            }
            counters.positive_lookup_misses += 1;
        }
    }
    (None, checked, counters)
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

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() > 1 && (args[1] == "--build-cache" || args[1] == "--check-cache") {
        cache_mode(&args);
        return;
    }
    assert_eq!(args.len(), 7,
               "usage: a1-conjugate-bloom <base-export.json> <pair-index.bin> <schedule.json> <target-receipt.json> <bloom-bits.bin> <cache-manifest.json>");
    let exported: Value = serde_json::from_slice(&fs::read(&args[1]).unwrap()).unwrap();
    let workload: Value = serde_json::from_slice(&fs::read(&args[3]).unwrap()).unwrap();
    let receipt: Value = serde_json::from_slice(&fs::read(&args[4]).unwrap()).unwrap();
    assert_eq!(exported["status"], "completed");
    assert_eq!(as_u64(&exported["subgroup_order"]), ORDER);
    assert_eq!(as_u64(&workload["subgroup_order"]), ORDER);
    assert_eq!(as_u64(&receipt["subgroup_order"]), ORDER);
    assert_eq!(workload["target_count"], 1);
    assert_eq!(workload["generator"], receipt["seed_points"][0]);
    assert_eq!(workload["target_point"], receipt["fresh_target"]["point"]);
    assert_eq!(exported["seed_points"], receipt["seed_points"]);
    assert_eq!(exported["base_sha256"], receipt["base_sha256"]);
    let curve_source = KoblitzCurve::new(0, DEGREE as u32).unwrap();
    assert_eq!(curve_source.subgroup_order.to_string().parse::<u64>().unwrap(), ORDER);
    assert_eq!(curve_source.curve.irreducible.low_terms, vec![0, 1, 2, 6]);
    let curve = FastBinaryCurve::new(&curve_source.curve.irreducible, 0).unwrap();
    let seeds: Vec<FastPoint> = exported["seed_points"].as_array().unwrap().iter().map(point).collect();
    assert_eq!(seeds.len(), 6);
    let logs: Vec<u64> = exported["seed_logs"].as_array().unwrap().iter().map(as_u64).collect();
    assert_eq!(logs.len(), 6);
    assert_eq!(logs[0], 1);
    for j in 0..6 { assert_eq!(scalar_mul(&curve, seeds[0], logs[j]), seeds[j]); }
    let reps: Vec<Representative> = exported["representatives"].as_array().unwrap().iter().map(|v| {
        Representative { point: point(&v["point"]), scalar: as_u64(&v["scalar"]),
                         seed: as_u64(&v["seed_index"]) as usize }
    }).collect();
    assert_eq!(reps.len(), 120);
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
    assert_eq!(base.len(), 12_720);
    for item in &base {
        assert!(item.rep < 120 && item.shift < DEGREE && (item.sign == 1 || item.sign == -1));
        let mut expected = powers[item.rep][item.shift];
        if item.sign == -1 { expected = FastBinaryCurve::neg(expected); }
        assert_eq!(expected, item.point);
    }
    let lam = as_u64(&exported["frobenius_scalar"]);
    let mut lam_powers = vec![1u64; DEGREE + 1];
    for i in 1..=DEGREE { lam_powers[i] = mul_mod(lam_powers[i-1], lam); }
    assert_eq!(lam_powers[DEGREE], 1);
    for j in 0..6 { assert_eq!(frobenius(&curve, seeds[j]), scalar_mul(&curve, seeds[j], lam)); }
    let expected_orbits = as_u64(&workload["pair_index_orbits"]) as usize;
    assert!(expected_orbits == 735_000 || expected_orbits == 369_162 || expected_orbits == 442_994);
    let raw_index = fs::read(&args[2]).unwrap();
    let record_bytes = exported.get("pair_index_record_bytes")
        .map(|value| as_u64(value) as usize).unwrap_or(INDEX_RECORD_BYTES);
    if record_bytes == PACKED_RECORD_BYTES {
        assert_eq!(exported["pair_index_trailer"], "u32_le_record_count");
    } else { assert_eq!(record_bytes, INDEX_RECORD_BYTES); }
    let index = load_index(&raw_index, expected_orbits, reps.len(), record_bytes);
    assert_eq!(record_bytes, PACKED_RECORD_BYTES);
    assert_eq!(expected_orbits, BLOOM_ORBITS);
    let (bloom,bits_sha256,cache_direct_load_hash_ns) = Bloom::read_direct(&args[5]);
    let cache_manifest_raw = fs::read(&args[6]).unwrap();
    let cache_verify_started = Instant::now();
    let cache_manifest: Value = serde_json::from_slice(&cache_manifest_raw).unwrap();
    verify_cache_manifest(&cache_manifest,&raw_index,&bits_sha256,bloom.len_bytes());
    let cache_verify_ns = cache_verify_started.elapsed().as_nanos();
    let cache_manifest_sha256 = sha256_hex(&cache_manifest_raw);
    let target = point(&workload["target_point"]);
    let fixture_scalar = as_u64(&receipt["fresh_target"]["fixture_scalar"]);
    let attempts = workload["attempts"].as_array().unwrap();
    assert_eq!(attempts.len(), as_u64(&workload["attempt_count"]) as usize);
    assert_eq!(attempts.len(), 1_000);
    let online_started = Instant::now();
    let mut query_ns = 0u128;
    let mut pdp_ns = 0u128;
    let mut relation_check_ns = 0u128;
    let mut descent_ns = 0u128;
    let mut recovery_check_ns = 0u128;
    let mut points_checked = 0usize;
    let mut completed_attempts = 0usize;
    let mut nonidentity_differences = 0usize;
    let mut bloom_negative_checks = 0usize;
    let mut bloom_positive_checks = 0usize;
    let mut orbit_key_computations = 0usize;
    let mut indexed_hits = 0usize;
    let mut positive_lookup_misses = 0usize;
    let mut answer = None;
    let mut event = None;
    let query_started = Instant::now();
    assert!(on_curve(&curve, target));
    assert_eq!(scalar_mul(&curve, target, ORDER), None);
    query_ns += query_started.elapsed().as_nanos();
    for (attempt_index, item) in attempts.iter().enumerate() {
        let query_started = Instant::now();
        let offset = as_u64(&item["offset_scalar"]);
        let start = as_u64(&item["base_start"]) as usize;
        assert!(offset < ORDER && start < base.len());
        let query = if offset == 0 { target } else {
            curve.add(target, scalar_mul(&curve, seeds[0], offset))
        };
        query_ns += query_started.elapsed().as_nanos();
        let pdp_started = Instant::now();
        let (found, checked, counters) = scan(&curve, query, start, &base, &index, &bloom);
        pdp_ns += pdp_started.elapsed().as_nanos();
        completed_attempts += 1;
        points_checked += checked;
        nonidentity_differences += counters.nonidentity_differences;
        bloom_negative_checks += counters.bloom_negative_checks;
        bloom_positive_checks += counters.bloom_positive_checks;
        orbit_key_computations += counters.orbit_key_computations;
        indexed_hits += counters.indexed_hits;
        positive_lookup_misses += counters.positive_lookup_misses;
        let Some(witness) = found else { continue; };
        let check_started = Instant::now();
        let (row, global_shift, global_sign) = verify_and_row(
            &curve, query, witness, &base, &reps, &powers, &seeds, &lam_powers);
        relation_check_ns += check_started.elapsed().as_nanos();
        let descent_started = Instant::now();
        let mut scalar = 0u64;
        for j in 0..6 { scalar = add_mod(scalar, mul_mod(row[j], logs[j])); }
        scalar = sub_mod(scalar, offset);
        descent_ns += descent_started.elapsed().as_nanos();
        let replay_started = Instant::now();
        assert_eq!(scalar_mul(&curve, seeds[0], scalar), target);
        assert_eq!(scalar, fixture_scalar);
        recovery_check_ns += replay_started.elapsed().as_nanos();
        answer = Some(scalar);
        event = Some(json!({"attempt_index": attempt_index + 1,
                            "offset_scalar": offset, "base_start": start,
                            "points_checked_this_attempt": checked,
                            "query_point": query.map(|(x,y)| vec![x,y]),
                            "row": row, "pair_record": [witness.pair.left as i64,
                                                           witness.pair.right as i64,
                                                           witness.pair.relative as i64,
                                                           witness.pair.side as i64],
                            "third_base_index": witness.third,
                            "global_shift": global_shift,
                            "global_sign": global_sign}));
        break;
    }
    let online_ns = online_started.elapsed().as_nanos();
    let phase_sum = query_ns + pdp_ns + relation_check_ns + descent_ns + recovery_check_ns;
    let timer_residual_ns = online_ns.saturating_sub(phase_sum);
    query_ns += timer_residual_ns;
    assert_eq!(nonidentity_differences, bloom_negative_checks+bloom_positive_checks);
    assert_eq!(bloom_positive_checks, orbit_key_computations);
    assert_eq!(orbit_key_computations, indexed_hits+positive_lookup_misses);
    let record = json!({
        "status": if answer.is_some() { "verified" } else { "censored" },
        "curve": "y^2+xy=x^3+1 over F_(2^53)",
        "subgroup_order": ORDER,
        "generator": seeds[0].map(|(x,y)| vec![x,y]),
        "target_point": target.map(|(x,y)| vec![x,y]),
        "target_count": 1,
        "recovered_scalar": answer,
        "fixture_scalar_outside_online": fixture_scalar,
        "actual_usable_B": base.len(),
        "pair_index_orbits": index.len(),
        "pair_index_record_bytes":record_bytes,"pair_index_binary_bytes":raw_index.len(),
        "bloom_filter_bytes":bloom.len_bytes(),
        "bloom_bits":BLOOM_BITS,"bloom_hashes":BLOOM_HASHES,
        "bloom_block_bits":BLOOM_BLOCK_BITS,"bloom_block_count":BLOOM_BLOCKS,
        "bloom_allocation_alignment_bytes":64,
        "bloom_allocation_pointer_mod64":bloom.pointer_mod64(),
        "bloom_build_wall_ns_exploratory_outside_online":Value::Null,
        "bloom_exhaustive_check_wall_ns_exploratory_outside_online":Value::Null,
        "bloom_artifact_build_wall_ns_exploratory":cache_manifest["build_wall_ns_exploratory"],
        "bloom_artifact_builder_check_wall_ns_exploratory":cache_manifest["exhaustive_check_wall_ns_exploratory"],
        "bloom_cache_read_wall_ns_exploratory_outside_online":Value::Null,
        "bloom_cache_verify_wall_ns_exploratory_outside_online":cache_verify_ns,
        "bloom_cache_align_copy_wall_ns_exploratory_outside_online":Value::Null,
        "bloom_cache_direct_load_hash_wall_ns_exploratory_outside_online":cache_direct_load_hash_ns,
        "bloom_cache_manifest_sha256":cache_manifest_sha256,
        "bloom_cache_bits_sha256":cache_manifest["bits_sha256"],
        "bloom_all_index_conjugates_positive":cache_manifest["builder_exhaustive_check"],
        "nonidentity_differences":nonidentity_differences,
        "bloom_negative_checks":bloom_negative_checks,
        "bloom_positive_checks":bloom_positive_checks,
        "orbit_key_computations":orbit_key_computations,
        "indexed_hits":indexed_hits,
        "positive_lookup_misses":positive_lookup_misses,
        "attempts": completed_attempts,
        "base_points_checked": points_checked,
        "hit_event": event,
        "online_phase_ns": {"target_query": query_ns,
                            "target_PDP": pdp_ns,
                            "target_relation_check": relation_check_ns,
                            "target_descent": descent_ns,
                            "target_recovery_check": recovery_check_ns},
        "timer_residual_ns_in_target_query": timer_residual_ns,
        "online_wall_ns": online_ns,
        "precompute_loaded_before_online": true,
        "cpu_isolation": "unverified",
        "workload_id": workload["workload_id"],
    });
    assert_eq!(query_ns + pdp_ns + relation_check_ns + descent_ns + recovery_check_ns,
               online_ns);
    println!("{}", record);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn archived_witness_lookup_preserves_exact_fallback() {
        let fixture: Value = serde_json::from_str(include_str!("../fixtures/single_hit.json"))
            .expect("valid single-hit fixture");
        assert_eq!(as_u64(&fixture["field_degree"]), DEGREE as u64);
        assert_eq!(as_u64(&fixture["curve_a"]), 0);
        let source_curve = KoblitzCurve::new(0, DEGREE as u32).unwrap();
        let curve = FastBinaryCurve::new(&source_curve.curve.irreducible, 0).unwrap();
        let query = point(&fixture["query_point"]);
        let third = point(&fixture["third_base_point"]);
        let difference = curve.add(query, FastBinaryCurve::neg(third));
        let x = difference.expect("nonidentity difference").0;
        let key = orbit_key(&curve, x);
        assert_eq!(key, as_u64(&fixture["canonical_difference_x"]));

        let pair = fixture["pair_record"].as_array().unwrap();
        let record = PairRecord {
            left: as_u64(&pair[0]) as usize,
            right: as_u64(&pair[1]) as usize,
            relative: as_u64(&pair[2]) as usize,
            side: pair[3].as_i64().unwrap() as i8,
        };
        let packed = pack_pair(record);
        let exact_index = HashMap::from([(key, packed)]);
        let base = [BasePoint {
            point: third,
            rep: as_u64(&fixture["third_representative_index"]) as usize,
            shift: as_u64(&fixture["third_frobenius_shift"]) as usize,
            sign: fixture["third_sign"].as_i64().unwrap() as i8,
        }];

        // The source key is inserted with its full Frobenius x-orbit. Every
        // conjugate must pass the prefilter before exact canonical lookup.
        let mut bloom = Bloom::new();
        let mut conjugate = key;
        for _ in 0..DEGREE {
            bloom.insert(conjugate);
            conjugate = curve.gf.sqr(conjugate);
        }
        assert_eq!(conjugate, key);
        let mut conjugate = key;
        for _ in 0..DEGREE {
            assert!(bloom.contains(conjugate));
            assert_eq!(orbit_key(&curve, conjugate), key);
            conjugate = curve.gf.sqr(conjugate);
        }
        let (hit, checked, counters) = scan(&curve, query, 0, &base, &exact_index, &bloom);
        let hit = hit.expect("archived witness must survive Bloom lookup");
        assert_eq!(checked, 1);
        assert_eq!(hit.third, 0);
        assert_eq!(hit.difference, difference);
        assert_eq!(pack_pair(hit.pair), packed);
        assert_eq!(counters.indexed_hits, 1);
        assert_eq!(counters.orbit_key_computations, 1);

        let seeds: Vec<FastPoint> = fixture["seed_points"].as_array().unwrap()
            .iter().map(point).collect();
        let logs: Vec<u64> = fixture["seed_logs"].as_array().unwrap()
            .iter().map(as_u64).collect();
        assert_eq!(seeds.len(), 6);
        assert_eq!(logs.len(), 6);
        let mut reps = vec![Representative { point: seeds[0], scalar: 1, seed: 0 }; 91];
        for index in [8usize, 58, 90] {
            let label = index.to_string();
            let source = &fixture["representatives"][label.as_str()];
            reps[index] = Representative {
                point: point(&source["point"]),
                scalar: as_u64(&source["scalar"]),
                seed: as_u64(&source["seed_index"]) as usize,
            };
            assert_eq!(scalar_mul(&curve, seeds[reps[index].seed], reps[index].scalar),
                       reps[index].point);
        }
        let mut powers = vec![Vec::new(); reps.len()];
        let mut power = reps[58].point;
        for _ in 0..DEGREE {
            powers[58].push(power);
            power = frobenius(&curve, power);
        }
        assert_eq!(power, reps[58].point);
        let lam = as_u64(&fixture["frobenius_scalar"]);
        let mut lam_powers = vec![1u64; DEGREE + 1];
        for i in 1..=DEGREE { lam_powers[i] = mul_mod(lam_powers[i - 1], lam); }
        assert_eq!(lam_powers[DEGREE], 1);
        let (row, shift, sign) = verify_and_row(
            &curve, query, hit, &base, &reps, &powers, &seeds, &lam_powers);
        let expected_row: Vec<u64> = fixture["expected_row"].as_array().unwrap()
            .iter().map(as_u64).collect();
        assert_eq!(row.to_vec(), expected_row);
        assert_eq!(shift, as_u64(&fixture["expected_global_shift"]) as usize);
        assert_eq!(sign, fixture["expected_global_sign"].as_i64().unwrap() as i8);
        let mut scalar = 0u64;
        for i in 0..6 { scalar = add_mod(scalar, mul_mod(row[i], logs[i])); }
        scalar = sub_mod(scalar, as_u64(&fixture["offset_scalar"]));
        assert_eq!(scalar, as_u64(&fixture["recovered_scalar"]));
        assert_eq!(scalar_mul(&curve, seeds[0], scalar), point(&fixture["target_point"]));

        let other_query = curve.add(query, point(&fixture["generator"]));
        let other_difference = curve.add(other_query, FastBinaryCurve::neg(third))
            .expect("nonidentity miss");
        assert_ne!(orbit_key(&curve, other_difference.0), key);
        assert!(!bloom.contains(other_difference.0));
        let (miss, checked, counters) =
            scan(&curve, other_query, 0, &base, &exact_index, &bloom);
        assert!(miss.is_none());
        assert_eq!(checked, 1);
        assert_eq!(counters.bloom_negative_checks, 1);
        assert_eq!(counters.orbit_key_computations, 0);

        // Force a positive result for a missing x. The canonical exact lookup
        // must still reject it, so a Bloom positive cannot invent a witness.
        bloom.insert(other_difference.0);
        let (miss, checked, counters) =
            scan(&curve, other_query, 0, &base, &exact_index, &bloom);
        assert!(miss.is_none());
        assert_eq!(checked, 1);
        assert_eq!(counters.bloom_positive_checks, 1);
        assert_eq!(counters.orbit_key_computations, 1);
        assert_eq!(counters.positive_lookup_misses, 1);
    }
}
