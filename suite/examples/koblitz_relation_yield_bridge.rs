//! Stage-21 distributional relation-yield bridge for the frozen degree-23
//! Koblitz factor base.
//!
//! Production takes no arguments and fixes the public-synthetic panel at 256
//! natural hash-to-subgroup targets, 64 planted two-point sums, and 64
//! exact-pair-table-proven non-decomposable targets:
//!
//! ```text
//! cargo run --release --example koblitz_relation_yield_bridge
//! ```
//!
//! A deliberately ineligible small fixture exercises the same paths:
//!
//! ```text
//! cargo run --example koblitz_relation_yield_bridge -- --smoke 8 4 4
//! ```

use cryptanalysis_suite::binary_ecc::curve::point_neg;
use cryptanalysis_suite::binary_ecc::BinaryPoint;
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base_from_divisor, projected_signed_orbit_count, KoblitzCurve,
};
use cryptanalysis_suite::cryptanalysis::koblitz_pdp_phase_a::decode_uniform_affine_draw;
use num_traits::ToPrimitive;
use serde_json::{json, Value};
use std::collections::{BinaryHeap, HashMap, HashSet};
use std::env;
use std::mem::size_of;
use std::time::Instant;

const PRODUCTION_N: u32 = 23;
const PRODUCTION_A: u8 = 0;
const PRODUCTION_M: usize = 2;
const PRODUCTION_DIVISOR_INDICES: &[usize] = &[0, 2];
const PRODUCTION_NATURAL: usize = 256;
const PRODUCTION_PLANTED: usize = 64;
const PRODUCTION_PROVEN_UNSAT: usize = 64;
const PRODUCTION_FACTOR_BITMASK: u64 = 5_279;
const PRODUCTION_DIMENSION: u32 = 12;
const PRODUCTION_ABSCISSAE: usize = 4_096;
const PRODUCTION_FACTOR_POINTS: usize = 4_281;
const PRODUCTION_SIGNED_ORBITS: usize = 95;
const PRODUCTION_PROJECTED_COLUMNS: usize = 93;
const PRODUCTION_SUBGROUP_ORDER: u64 = 2_095_853;
const PRODUCTION_GROUP_ORDER: u64 = 8_383_412;
const PRODUCTION_COFACTOR: u64 = 4;

// These byte strings are the exact seed_hex values in the frozen protocol.
const NATURAL_DOMAIN: &[u8] = b"koblitz-stage21-natural-v1";
const PLANTED_DOMAIN: &[u8] = b"koblitz-stage21-planted-v1";
const PROVEN_UNSAT_DOMAIN: &[u8] = b"koblitz-stage21-unsat-v1";
const HASH_TO_CURVE_DOMAIN: &[u8] = b"koblitz-stage21-hash-to-curve-x-v1\0";
const PAIR_PRIORITY_DOMAIN: &[u8] = b"koblitz-stage21-pair-priority-v1\0";

#[derive(Clone, Debug, PartialEq, Eq)]
struct Config {
    n: u32,
    a: u8,
    m: usize,
    divisor_indices: Vec<usize>,
    natural_count: usize,
    planted_count: usize,
    proven_unsat_count: usize,
    production_defaults_used: bool,
}

impl Config {
    fn production() -> Self {
        Self {
            n: PRODUCTION_N,
            a: PRODUCTION_A,
            m: PRODUCTION_M,
            divisor_indices: PRODUCTION_DIVISOR_INDICES.to_vec(),
            natural_count: PRODUCTION_NATURAL,
            planted_count: PRODUCTION_PLANTED,
            proven_unsat_count: PRODUCTION_PROVEN_UNSAT,
            production_defaults_used: true,
        }
    }

    fn smoke(natural_count: usize, planted_count: usize, proven_unsat_count: usize) -> Self {
        // This exact algebraic n=7 base has mixed m=2 subgroup coverage. The
        // full smoke table is 120 canonical pairs and 71 distinct targets.
        Self {
            n: 7,
            a: 1,
            m: 2,
            divisor_indices: vec![0, 2],
            natural_count,
            planted_count,
            proven_unsat_count,
            production_defaults_used: false,
        }
    }

    fn validate(&self) -> Result<(), String> {
        if self.m != 2 {
            return Err("the Stage-21 bridge is an exact m=2 pair-table experiment".into());
        }
        if self.n == 0 || 2 * self.n >= 63 {
            return Err("the exact packed point key requires 0 < 2*n < 63".into());
        }
        if self.divisor_indices.is_empty() {
            return Err("the algebraic divisor must contain at least one factor".into());
        }
        if self.natural_count == 0 || self.planted_count == 0 || self.proven_unsat_count == 0 {
            return Err(
                "all three arms are mandatory: natural, planted_sat, and proven_unsat counts must be positive"
                    .into(),
            );
        }
        if !self.production_defaults_used
            && (self.natural_count > 1_024
                || self.planted_count > 1_024
                || self.proven_unsat_count > 1_024)
        {
            return Err("smoke-arm counts are capped at 1024".into());
        }
        Ok(())
    }
}

#[derive(Clone, Debug)]
struct Target {
    point: BinaryPoint,
    packed: u64,
    candidate_attempts: u64,
    selection_counter: u64,
    candidate_kind: &'static str,
    construction_witness: Option<(u32, u32)>,
    selection_priority: Option<[u8; 32]>,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
struct GenerationOps {
    candidates: u64,
    hash_candidates: u64,
    uniform_affine_decode_successes: u64,
    cofactor_projection_scalar_multiplications: u64,
    rejected_affine_decode: u64,
    rejected_infinity: u64,
    rejected_duplicate: u64,
    rejected_pair_table_hit: u64,
    selection_table_lookups: u64,
}

#[derive(Clone, Debug)]
struct ArmSelection {
    targets: Vec<Target>,
    generation_ns: u128,
    ops: GenerationOps,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
struct QueryOps {
    table_lookups: u64,
    witness_verification_additions: u64,
}

#[derive(Clone, Debug)]
struct ArmResult {
    count: usize,
    hits: usize,
    misses: usize,
    query_ns: u128,
    witness_verification_ns: u128,
    verified_witnesses: usize,
    target_hash: String,
    witness_hash: String,
    witnesses: Vec<Option<(u32, u32)>>,
    ops: QueryOps,
}

#[derive(Clone, Debug)]
struct PlantedCandidate {
    target: Target,
    priority: [u8; 32],
}

#[derive(Debug)]
struct PairBuild {
    table: HashMap<u64, (u32, u32)>,
    canonical_pairs: u64,
    enumerated_pairs: u64,
    transcript_hash: String,
    construction_and_selection_ns: u128,
    cofactor_class_construction_ns: u128,
    cofactor_class_scalar_multiplications: u64,
    cofactor_class_negations: u64,
    planted_priority_hashes: u64,
    planted_final_verification_ns: u128,
    planted_final_subgroup_scalar_multiplications: u64,
    planted_construction_witness_verification_additions: u64,
    planted: ArmSelection,
}

fn parse_args(args: &[String]) -> Result<Config, String> {
    match args {
        [] => {
            let config = Config::production();
            config.validate()?;
            Ok(config)
        }
        [flag] if flag == "--smoke" => {
            let config = Config::smoke(8, 4, 4);
            config.validate()?;
            Ok(config)
        }
        [flag, natural, planted, proven_unsat] if flag == "--smoke" => {
            let parse = |name: &str, value: &str| {
                value
                    .parse::<usize>()
                    .map_err(|_| format!("invalid {name} count: {value}"))
            };
            let config = Config::smoke(
                parse("natural", natural)?,
                parse("planted", planted)?,
                parse("proven-unsat", proven_unsat)?,
            );
            config.validate()?;
            Ok(config)
        }
        _ => Err(
            "usage: koblitz_relation_yield_bridge [--smoke [NATURAL PLANTED PROVEN_UNSAT]]".into(),
        ),
    }
}

/// Exact injection for the supported binary fields. Infinity is zero; affine
/// `(x,y)` is `1 + (x << n | y)`. Both coordinates occupy exactly n bits.
fn pack_point(point: &BinaryPoint, n: u32) -> Result<u64, String> {
    if n == 0 || 2 * n >= 63 {
        return Err("packed point key requires 0 < 2*n < 63".into());
    }
    match point {
        BinaryPoint::Infinity => Ok(0),
        BinaryPoint::Affine { x, y } => {
            let x = x
                .to_biguint()
                .to_u64()
                .ok_or_else(|| "x coordinate does not fit u64".to_string())?;
            let y = y
                .to_biguint()
                .to_u64()
                .ok_or_else(|| "y coordinate does not fit u64".to_string())?;
            let limit = 1u64 << n;
            if x >= limit || y >= limit {
                return Err("coordinate exceeds the configured binary field width".into());
            }
            ((x << n) | y)
                .checked_add(1)
                .ok_or_else(|| "packed point key overflow".into())
        }
    }
}

fn affine_coordinates(point: &BinaryPoint) -> Result<(u64, u64), String> {
    match point {
        BinaryPoint::Infinity => Err("selected target must not be infinity".into()),
        BinaryPoint::Affine { x, y } => Ok((
            x.to_biguint()
                .to_u64()
                .ok_or_else(|| "x coordinate does not fit u64".to_string())?,
            y.to_biguint()
                .to_u64()
                .ok_or_else(|| "y coordinate does not fit u64".to_string())?,
        )),
    }
}

fn hash_json(value: &Value) -> Result<String, String> {
    let encoded = serde_json::to_vec(value).map_err(|error| error.to_string())?;
    Ok(blake3::hash(&encoded).to_hex().to_string())
}

fn hash_targets(domain: &[u8], targets: &[Target]) -> String {
    let mut hasher = blake3::Hasher::new();
    hasher.update(domain);
    for target in targets {
        hasher.update(&target.packed.to_le_bytes());
    }
    hasher.finalize().to_hex().to_string()
}

fn selection_attempt_cap(requested: usize) -> usize {
    requested.saturating_mul(10_000).saturating_add(10_000)
}

fn hash_to_subgroup_candidate(
    curve: &KoblitzCurve,
    arm_domain: &[u8],
    counter: u64,
    ops: &mut GenerationOps,
) -> Result<Option<BinaryPoint>, String> {
    ops.candidates += 1;
    ops.hash_candidates += 1;
    let mut hasher = blake3::Hasher::new();
    hasher.update(HASH_TO_CURVE_DOMAIN);
    hasher.update(arm_domain);
    hasher.update(&curve.n.to_le_bytes());
    hasher.update(&[curve.a]);
    hasher.update(&counter.to_le_bytes());
    let digest = hasher.finalize();
    let digest_bytes = digest.as_bytes();
    let mut x_bytes = [0u8; 8];
    x_bytes.copy_from_slice(&digest_bytes[..8]);
    let x_mask = (1u64 << curve.n) - 1;
    let x_bits = u64::from_le_bytes(x_bytes) & x_mask;
    let sign = digest_bytes[8] & 1 == 1;
    let Some(raw_point) = decode_uniform_affine_draw(&curve.curve, x_bits, sign) else {
        ops.rejected_affine_decode += 1;
        return Ok(None);
    };
    ops.uniform_affine_decode_successes += 1;
    let projected = curve.mul(&raw_point, &curve.cofactor);
    ops.cofactor_projection_scalar_multiplications += 1;
    if projected == BinaryPoint::Infinity {
        ops.rejected_infinity += 1;
        return Ok(None);
    }
    Ok(Some(projected))
}

fn select_hash_targets(
    curve: &KoblitzCurve,
    count: usize,
    arm_domain: &[u8],
    pair_table: Option<&HashMap<u64, (u32, u32)>>,
    require_table_miss: bool,
    used: &mut HashSet<u64>,
) -> Result<ArmSelection, String> {
    if require_table_miss != pair_table.is_some() {
        return Err("pair-table selection influence must be explicit and confined to UNSAT".into());
    }
    let started = Instant::now();
    let mut targets = Vec::with_capacity(count);
    let mut ops = GenerationOps::default();
    let cap = selection_attempt_cap(count) as u64;
    let mut counter = 0u64;
    let mut attempts_since_acceptance = 0u64;

    while targets.len() < count && counter < cap {
        attempts_since_acceptance += 1;
        let candidate = hash_to_subgroup_candidate(curve, arm_domain, counter, &mut ops)?;
        let accepted_counter = counter;
        counter += 1;
        let Some(point) = candidate else {
            continue;
        };
        let packed = pack_point(&point, curve.n)?;
        if used.contains(&packed) {
            ops.rejected_duplicate += 1;
            continue;
        }
        if let Some(table) = pair_table {
            ops.selection_table_lookups += 1;
            if table.contains_key(&packed) {
                ops.rejected_pair_table_hit += 1;
                continue;
            }
        }
        used.insert(packed);
        targets.push(Target {
            point,
            packed,
            candidate_attempts: attempts_since_acceptance,
            selection_counter: accepted_counter,
            candidate_kind: "domain_separated_blake3_uniform_affine_then_cofactor_projection",
            construction_witness: None,
            selection_priority: None,
        });
        attempts_since_acceptance = 0;
    }
    if targets.len() != count {
        return Err(format!(
            "{} arm selected {} of {count} targets before its deterministic cap",
            if require_table_miss {
                "proven-unsat"
            } else {
                "natural"
            },
            targets.len()
        ));
    }
    Ok(ArmSelection {
        targets,
        generation_ns: started.elapsed().as_nanos(),
        ops,
    })
}

fn pair_priority(left: u32, right: u32, packed: u64) -> [u8; 32] {
    let mut hasher = blake3::Hasher::new();
    hasher.update(PAIR_PRIORITY_DOMAIN);
    hasher.update(PLANTED_DOMAIN);
    hasher.update(&left.to_le_bytes());
    hasher.update(&right.to_le_bytes());
    hasher.update(&packed.to_le_bytes());
    *hasher.finalize().as_bytes()
}

fn discard_stale_heap_entries(
    heap: &mut BinaryHeap<([u8; 32], u64)>,
    selected: &HashMap<u64, PlantedCandidate>,
) {
    while let Some((priority, packed)) = heap.peek() {
        let current = selected
            .get(packed)
            .is_some_and(|candidate| &candidate.priority == priority);
        if current {
            break;
        }
        heap.pop();
    }
}

fn consider_planted_candidate(
    selected: &mut HashMap<u64, PlantedCandidate>,
    heap: &mut BinaryHeap<([u8; 32], u64)>,
    limit: usize,
    candidate: PlantedCandidate,
) {
    let packed = candidate.target.packed;
    if let Some(existing) = selected.get(&packed) {
        if (candidate.priority, candidate.target.construction_witness)
            < (existing.priority, existing.target.construction_witness)
        {
            selected.insert(packed, candidate.clone());
            heap.push((candidate.priority, packed));
        }
        return;
    }
    if selected.len() < limit {
        selected.insert(packed, candidate.clone());
        heap.push((candidate.priority, packed));
        return;
    }
    discard_stale_heap_entries(heap, selected);
    let Some((worst_priority, worst_packed)) = heap.peek().copied() else {
        return;
    };
    if (candidate.priority, packed) < (worst_priority, worst_packed) {
        heap.pop();
        selected.remove(&worst_packed);
        selected.insert(packed, candidate.clone());
        heap.push((candidate.priority, packed));
    }
}

fn build_pair_table_and_select_planted(
    curve: &KoblitzCurve,
    factor_points: &[BinaryPoint],
    planted_count: usize,
    natural_keys: &HashSet<u64>,
) -> Result<PairBuild, String> {
    let point_count = factor_points.len() as u64;
    let canonical_pairs = point_count
        .checked_mul(point_count + 1)
        .and_then(|value| value.checked_div(2))
        .ok_or_else(|| "canonical pair count overflow".to_string())?;

    // A pair sum lies in the prime-order subgroup iff its two [r]P
    // cofactor classes cancel. Precomputing those classes avoids millions of
    // scalar multiplications during the complete pair scan.
    let cofactor_started = Instant::now();
    let cofactor_classes = factor_points
        .iter()
        .map(|point| curve.mul(point, &curve.subgroup_order))
        .collect::<Vec<_>>();
    let class_keys = cofactor_classes
        .iter()
        .map(|class| pack_point(class, curve.n))
        .collect::<Result<Vec<_>, _>>()?;
    let negative_class_keys = cofactor_classes
        .iter()
        .map(|class| pack_point(&point_neg(class), curve.n))
        .collect::<Result<Vec<_>, _>>()?;
    let cofactor_class_construction_ns = cofactor_started.elapsed().as_nanos();

    let capacity_bound = canonical_pairs.min(curve.group_order.to_u64().unwrap_or(canonical_pairs));
    let mut table: HashMap<u64, (u32, u32)> = HashMap::with_capacity(capacity_bound as usize);
    let mut selected: HashMap<u64, PlantedCandidate> = HashMap::with_capacity(planted_count);
    let mut heap: BinaryHeap<([u8; 32], u64)> = BinaryHeap::new();
    let mut transcript_hasher = blake3::Hasher::new();
    transcript_hasher.update(b"koblitz-stage21-canonical-pairs-v1\0");
    let started = Instant::now();
    let mut enumerated_pairs = 0u64;
    let mut planted_priority_hashes = 0u64;

    for left in 0..factor_points.len() {
        for right in left..factor_points.len() {
            let sum = curve.add(&factor_points[left], &factor_points[right]);
            let packed = pack_point(&sum, curve.n)?;
            transcript_hasher.update(&(left as u32).to_le_bytes());
            transcript_hasher.update(&(right as u32).to_le_bytes());
            transcript_hasher.update(&packed.to_le_bytes());
            table.entry(packed).or_insert((left as u32, right as u32));
            enumerated_pairs += 1;

            let in_subgroup = class_keys[right] == negative_class_keys[left];
            if !in_subgroup || packed == 0 || natural_keys.contains(&packed) {
                continue;
            }
            let priority = pair_priority(left as u32, right as u32, packed);
            planted_priority_hashes += 1;
            consider_planted_candidate(
                &mut selected,
                &mut heap,
                planted_count,
                PlantedCandidate {
                    target: Target {
                        point: sum,
                        packed,
                        candidate_attempts: enumerated_pairs,
                        selection_counter: enumerated_pairs - 1,
                        candidate_kind: "complete_canonical_pair_priority_scan",
                        construction_witness: Some((left as u32, right as u32)),
                        selection_priority: Some(priority),
                    },
                    priority,
                },
            );
        }
    }
    let construction_and_selection_ns = started.elapsed().as_nanos();
    if enumerated_pairs != canonical_pairs {
        return Err("canonical pair enumeration was incomplete".into());
    }
    if selected.len() != planted_count {
        return Err(format!(
            "planted priority selection retained {} of {planted_count} distinct subgroup targets",
            selected.len()
        ));
    }
    let mut selected = selected.into_values().collect::<Vec<_>>();
    selected.sort_by_key(|candidate| (candidate.priority, candidate.target.packed));
    let final_verification_started = Instant::now();
    for candidate in &selected {
        let (left, right) = candidate
            .target
            .construction_witness
            .ok_or_else(|| "planted candidate lacks its construction witness".to_string())?;
        let recomputed = curve.add(
            factor_points
                .get(left as usize)
                .ok_or_else(|| "planted left witness index is out of range".to_string())?,
            factor_points
                .get(right as usize)
                .ok_or_else(|| "planted right witness index is out of range".to_string())?,
        );
        if recomputed != candidate.target.point
            || pack_point(&recomputed, curve.n)? != candidate.target.packed
        {
            return Err("planted construction witness failed exact re-addition".into());
        }
        if curve.mul(&candidate.target.point, &curve.subgroup_order) != BinaryPoint::Infinity {
            return Err("planted target failed independent subgroup verification".into());
        }
    }
    let planted_final_verification_ns = final_verification_started.elapsed().as_nanos();
    let targets = selected
        .into_iter()
        .map(|candidate| candidate.target)
        .collect::<Vec<_>>();

    Ok(PairBuild {
        table,
        canonical_pairs,
        enumerated_pairs,
        transcript_hash: transcript_hasher.finalize().to_hex().to_string(),
        construction_and_selection_ns,
        cofactor_class_construction_ns,
        cofactor_class_scalar_multiplications: factor_points.len() as u64,
        cofactor_class_negations: factor_points.len() as u64,
        planted_priority_hashes,
        planted_final_verification_ns,
        planted_final_subgroup_scalar_multiplications: planted_count as u64,
        planted_construction_witness_verification_additions: planted_count as u64,
        planted: ArmSelection {
            targets,
            generation_ns: construction_and_selection_ns,
            ops: GenerationOps {
                candidates: canonical_pairs,
                ..GenerationOps::default()
            },
        },
    })
}

fn query_arm(
    curve: &KoblitzCurve,
    factor_points: &[BinaryPoint],
    pair_table: &HashMap<u64, (u32, u32)>,
    targets: &[Target],
    target_hash_domain: &[u8],
) -> Result<ArmResult, String> {
    let query_started = Instant::now();
    let witnesses = targets
        .iter()
        .map(|target| pair_table.get(&target.packed).copied())
        .collect::<Vec<_>>();
    let query_ns = query_started.elapsed().as_nanos();

    let verification_started = Instant::now();
    let mut verified_witnesses = 0usize;
    let mut witness_verification_additions = 0u64;
    let mut witness_hasher = blake3::Hasher::new();
    witness_hasher.update(b"koblitz-stage21-witness-sequence-v1\0");
    for (target, witness) in targets.iter().zip(&witnesses) {
        witness_hasher.update(&target.packed.to_le_bytes());
        match witness {
            Some((left, right)) => {
                let recomputed = curve.add(
                    factor_points.get(*left as usize).ok_or_else(|| {
                        "pair-table left witness index is out of range".to_string()
                    })?,
                    factor_points.get(*right as usize).ok_or_else(|| {
                        "pair-table right witness index is out of range".to_string()
                    })?,
                );
                witness_verification_additions += 1;
                if recomputed != target.point || pack_point(&recomputed, curve.n)? != target.packed
                {
                    return Err("pair-table witness failed exact point re-addition".into());
                }
                witness_hasher.update(&left.to_le_bytes());
                witness_hasher.update(&right.to_le_bytes());
                verified_witnesses += 1;
            }
            None => {
                witness_hasher.update(&u64::MAX.to_le_bytes());
            }
        }
    }
    let witness_verification_ns = verification_started.elapsed().as_nanos();
    let hits = witnesses.iter().filter(|witness| witness.is_some()).count();

    Ok(ArmResult {
        count: targets.len(),
        hits,
        misses: targets.len() - hits,
        query_ns,
        witness_verification_ns,
        verified_witnesses,
        target_hash: hash_targets(target_hash_domain, targets),
        witness_hash: witness_hasher.finalize().to_hex().to_string(),
        witnesses,
        ops: QueryOps {
            table_lookups: targets.len() as u64,
            witness_verification_additions,
        },
    })
}

fn wilson_interval_95(successes: usize, trials: usize) -> Option<(f64, f64)> {
    if trials == 0 {
        return None;
    }
    let n = trials as f64;
    let p = successes as f64 / n;
    let z = 1.959_963_984_540_054_f64;
    let z2 = z * z;
    let denominator = 1.0 + z2 / n;
    let center = (p + z2 / (2.0 * n)) / denominator;
    let half_width = z * ((p * (1.0 - p) / n + z2 / (4.0 * n * n)).sqrt()) / denominator;
    Some((
        (center - half_width).max(0.0),
        (center + half_width).min(1.0),
    ))
}

fn generation_ops_json(ops: GenerationOps) -> Value {
    json!({
        "candidates":ops.candidates,
        "hash_candidates":ops.hash_candidates,
        "uniform_affine_decode_successes":ops.uniform_affine_decode_successes,
        "cofactor_projection_scalar_multiplications":ops.cofactor_projection_scalar_multiplications,
        "rejected_affine_decode":ops.rejected_affine_decode,
        "rejected_infinity":ops.rejected_infinity,
        "rejected_duplicate":ops.rejected_duplicate,
        "rejected_pair_table_hit":ops.rejected_pair_table_hit,
        "selection_pair_table_lookups":ops.selection_table_lookups
    })
}

fn arm_json(selection: &ArmSelection, result: &ArmResult) -> Value {
    let hit_rate = result.hits as f64 / result.count as f64;
    let (ci_low, ci_high) = wilson_interval_95(result.hits, result.count)
        .expect("validated non-empty arm must have a confidence interval");
    json!({
        "count":result.count,
        "hits":result.hits,
        "misses":result.misses,
        "hit_rate":hit_rate,
        "wilson_95_ci":{"low":ci_low,"high":ci_high},
        "targets_blake3":result.target_hash,
        "witness_results_blake3":result.witness_hash,
        "verified_point_witnesses":result.verified_witnesses,
        "timing_ns":{
            "target_generation_and_selection":selection.generation_ns,
            "exact_pair_table_queries":result.query_ns,
            "point_witness_verification":result.witness_verification_ns
        },
        "high_level_operations":{
            "generation":generation_ops_json(selection.ops),
            "final_pair_table_lookups":result.ops.table_lookups,
            "point_witness_verification_additions":result.ops.witness_verification_additions
        }
    })
}

fn frobenius_orbit_length(curve: &KoblitzCurve, point: &BinaryPoint) -> Result<u32, String> {
    let mut current = point.clone();
    for length in 1..=curve.n {
        current = curve.frobenius(&current);
        if current == *point {
            return Ok(length);
        }
    }
    Err("target Frobenius orbit did not close within n applications".into())
}

fn covariate_rows(
    curve: &KoblitzCurve,
    arms: &[(&str, &ArmSelection, &ArmResult)],
) -> Result<(Vec<Value>, u128, u64), String> {
    let started = Instant::now();
    let mut rows = Vec::new();
    let mut frobenius_applications = 0u64;
    let hex_width = curve.n.div_ceil(4) as usize;
    let mut global_ordinal = 0usize;

    for (arm, selection, result) in arms {
        if selection.targets.len() != result.witnesses.len() {
            return Err("target and witness row counts differ".into());
        }
        for (arm_ordinal, (target, witness)) in
            selection.targets.iter().zip(&result.witnesses).enumerate()
        {
            let (x, y) = affine_coordinates(&target.point)?;
            let orbit_length = frobenius_orbit_length(curve, &target.point)?;
            frobenius_applications += u64::from(orbit_length);
            let construction_witness = target
                .construction_witness
                .map(|(left, right)| vec![left, right]);
            let verified_witness = witness.map(|(left, right)| vec![left, right]);
            rows.push(json!({
                "global_ordinal":global_ordinal,
                "arm":arm,
                "arm_ordinal":arm_ordinal,
                "packed_target":target.packed,
                "x_hex":format!("{x:0hex_width$x}"),
                "y_hex":format!("{y:0hex_width$x}"),
                "x_hamming_weight":x.count_ones(),
                "y_hamming_weight":y.count_ones(),
                "frobenius_orbit_length":orbit_length,
                "candidate_attempts":target.candidate_attempts,
                "candidate_kind":target.candidate_kind,
                "candidate_attempts_scope":if target.construction_witness.is_some() {
                    "one-based canonical-pair scan position of the selected construction witness"
                } else {
                    "hash candidates since the preceding accepted target in this arm"
                },
                "selection_counter":target.selection_counter,
                "selection_priority_blake3":target.selection_priority.map(hex::encode),
                "construction_witness_indices":construction_witness,
                "construction_witness_verified":target.construction_witness.map(|_| true),
                "exact_pair_table_hit":witness.is_some(),
                "verified_witness_indices":verified_witness,
                "point_witness_verified":witness.map(|_| true)
            }));
            global_ordinal += 1;
        }
    }
    Ok((rows, started.elapsed().as_nanos(), frobenius_applications))
}

fn run_experiment(config: &Config) -> Result<Value, String> {
    config.validate()?;
    let total_started = Instant::now();

    let curve_started = Instant::now();
    let curve = KoblitzCurve::new(config.a, config.n)
        .ok_or_else(|| "the configured public Koblitz curve is unavailable".to_string())?;
    let curve_construction_ns = curve_started.elapsed().as_nanos();
    let subgroup_order = curve
        .subgroup_order
        .to_u64()
        .ok_or_else(|| "subgroup order does not fit u64".to_string())?;
    let group_order = curve
        .group_order
        .to_u64()
        .ok_or_else(|| "group order does not fit u64".to_string())?;
    let cofactor = curve
        .cofactor
        .to_u64()
        .ok_or_else(|| "cofactor does not fit u64".to_string())?;

    // The complete algebraic base is materialized before any target stream.
    // Its identity cannot depend on a target, oracle result, or log label.
    let factor_base_started = Instant::now();
    let factor_base =
        build_frobenius_factor_base_from_divisor(&curve, config.divisor_indices.as_slice())
            .ok_or_else(|| {
                "the frozen divisor did not construct its algebraic factor base".to_string()
            })?;
    let factor_base_materialization_ns = factor_base_started.elapsed().as_nanos();
    let projected_columns_started = Instant::now();
    let projected_signed_columns = projected_signed_orbit_count(&curve, &factor_base);
    let projected_columns_ns = projected_columns_started.elapsed().as_nanos();

    if config.production_defaults_used
        && (config.n != PRODUCTION_N
            || config.a != PRODUCTION_A
            || config.m != PRODUCTION_M
            || config.divisor_indices != PRODUCTION_DIVISOR_INDICES
            || factor_base.f_j != PRODUCTION_FACTOR_BITMASK
            || factor_base.ell != PRODUCTION_DIMENSION
            || factor_base.subspace.len() != PRODUCTION_ABSCISSAE
            || factor_base.points.len() != PRODUCTION_FACTOR_POINTS
            || factor_base.unknowns() != PRODUCTION_SIGNED_ORBITS
            || projected_signed_columns != PRODUCTION_PROJECTED_COLUMNS
            || subgroup_order != PRODUCTION_SUBGROUP_ORDER
            || group_order != PRODUCTION_GROUP_ORDER
            || cofactor != PRODUCTION_COFACTOR)
    {
        return Err(
            "production factor-base identity differs from the frozen Stage-10 selection".into(),
        );
    }
    if factor_base.points.is_empty() || factor_base.points.len() > u32::MAX as usize {
        return Err("factor-base point count is outside the exact table representation".into());
    }

    let predicate = json!({
        "curve":{
            "n":config.n,
            "a":config.a,
            "irreducible_low_terms":curve.curve.irreducible.low_terms
        },
        "group_order":curve.group_order.to_string(),
        "subgroup_order":curve.subgroup_order.to_string(),
        "cofactor":curve.cofactor.to_string(),
        "m":config.m,
        "construction_method":"linearized kernel of a frozen divisor of T^n-1 over F2",
        "divisor_indices":config.divisor_indices,
        "divisor_polynomial_bitmask":factor_base.f_j,
        "linearised_exponents":factor_base.linearised_exponents,
        "dimension":factor_base.ell,
        "abscissae":factor_base.subspace.len(),
        "rational_points":factor_base.points.len(),
        "signed_frobenius_orbits_before_projection":factor_base.unknowns(),
        "projected_signed_frobenius_columns":projected_signed_columns
    });
    let predicate_hash = hash_json(&predicate)?;
    let mut keyed_factor_points = factor_base
        .points
        .iter()
        .map(|point| pack_point(point, curve.n).map(|packed| (packed, point.clone())))
        .collect::<Result<Vec<_>, _>>()?;
    keyed_factor_points.sort_by_key(|(packed, _)| *packed);
    let sorted_factor_keys = keyed_factor_points
        .iter()
        .map(|(packed, _)| *packed)
        .collect::<Vec<_>>();
    if sorted_factor_keys.windows(2).any(|pair| pair[0] == pair[1]) {
        return Err("factor-base materialization contains duplicate points".into());
    }
    let factor_points = keyed_factor_points
        .into_iter()
        .map(|(_, point)| point)
        .collect::<Vec<_>>();
    let mut base_hasher = blake3::Hasher::new();
    base_hasher.update(b"koblitz-stage21-factor-base-v1\0");
    base_hasher.update(predicate_hash.as_bytes());
    for packed in &sorted_factor_keys {
        base_hasher.update(&packed.to_le_bytes());
    }
    let factor_base_hash = base_hasher.finalize().to_hex().to_string();

    // Natural targets are frozen before the pair oracle exists. This ordering
    // makes oracle-dependent natural-arm selection impossible.
    let mut used_targets = HashSet::with_capacity(
        config.natural_count + config.planted_count + config.proven_unsat_count,
    );
    let natural = select_hash_targets(
        &curve,
        config.natural_count,
        NATURAL_DOMAIN,
        None,
        false,
        &mut used_targets,
    )?;
    let natural_keys = used_targets.clone();

    let pair_build = build_pair_table_and_select_planted(
        &curve,
        &factor_points,
        config.planted_count,
        &natural_keys,
    )?;
    let planted = pair_build.planted.clone();
    for target in &planted.targets {
        if !used_targets.insert(target.packed) {
            return Err("planted target overlaps a previous arm".into());
        }
    }

    let proven_unsat = select_hash_targets(
        &curve,
        config.proven_unsat_count,
        PROVEN_UNSAT_DOMAIN,
        Some(&pair_build.table),
        true,
        &mut used_targets,
    )?;
    if natural.targets.len() != config.natural_count
        || planted.targets.len() != config.planted_count
        || proven_unsat.targets.len() != config.proven_unsat_count
        || used_targets.len()
            != config.natural_count + config.planted_count + config.proven_unsat_count
    {
        return Err("an arm was omitted, incomplete, or not disjoint".into());
    }

    let natural_result = query_arm(
        &curve,
        &factor_points,
        &pair_build.table,
        &natural.targets,
        b"koblitz-stage21-natural-targets-v1\0",
    )?;
    let planted_result = query_arm(
        &curve,
        &factor_points,
        &pair_build.table,
        &planted.targets,
        b"koblitz-stage21-planted-targets-v1\0",
    )?;
    let proven_unsat_result = query_arm(
        &curve,
        &factor_points,
        &pair_build.table,
        &proven_unsat.targets,
        b"koblitz-stage21-proven-unsat-targets-v1\0",
    )?;

    if planted_result.hits != config.planted_count
        || planted_result.verified_witnesses != config.planted_count
    {
        return Err("the planted-SAT arm did not return and verify every exact witness".into());
    }
    if proven_unsat_result.hits != 0 || proven_unsat_result.verified_witnesses != 0 {
        return Err("the exact-table-proven-UNSAT arm contained a decomposition".into());
    }
    if natural_result.verified_witnesses != natural_result.hits {
        return Err("a natural-arm hit lacked exact point-witness verification".into());
    }

    let (natural_ci_low, natural_ci_high) =
        wilson_interval_95(natural_result.hits, natural_result.count)
            .ok_or_else(|| "natural arm was unexpectedly empty".to_string())?;
    let natural_hit_rate = natural_result.hits as f64 / natural_result.count as f64;
    let trials_per_relation = if natural_result.hits > 0 {
        json!(natural_result.count as f64 / natural_result.hits as f64)
    } else {
        Value::String("infinity".into())
    };

    let policy = json!({
        "schema":"koblitz_relation_yield_policy.v1",
        "n":config.n,
        "a":config.a,
        "m":config.m,
        "irreducible_low_terms":curve.curve.irreducible.low_terms,
        "group_order":curve.group_order.to_string(),
        "subgroup_order":curve.subgroup_order.to_string(),
        "cofactor":curve.cofactor.to_string(),
        "divisor_indices":config.divisor_indices,
        "target_mix":{
            "natural":config.natural_count,
            "planted_sat":config.planted_count,
            "proven_unsat":config.proven_unsat_count
        },
        "seed_hex":{
            "natural":hex::encode(NATURAL_DOMAIN),
            "planted_sat":hex::encode(PLANTED_DOMAIN),
            "proven_unsat":hex::encode(PROVEN_UNSAT_DOMAIN)
        },
        "point_encoding":"u64 little-endian; 0 for infinity; 1 + (x << n | y) for affine",
        "hash_to_curve":{
            "hash":"BLAKE3",
            "domain_hex":hex::encode(HASH_TO_CURVE_DOMAIN),
            "message":"domain || arm_seed || n_le_u32 || a_u8 || counter_le_u64",
            "x_draw":"low n bits of digest bytes 0..8 interpreted little-endian; exact uniform power-of-two reduction",
            "lift":"decode_uniform_affine_draw with digest byte 8 low bit; every accepted affine point has one preimage",
            "projection":"multiply the accepted affine point by the public cofactor",
            "rejections":["uniform affine decode rejection","projected infinity","prior-arm or same-arm duplicate"],
            "target_scalar_constructed_or_recorded":false
        },
        "selection":{
            "natural":"first distinct nonidentity hash-to-curve/cofactor targets; pair oracle unavailable and unused",
            "planted_sat":"64 lowest BLAKE3 priorities over distinct nonidentity subgroup pair-sum targets in the complete canonical pair scan",
            "proven_unsat":"first distinct hash-to-curve/cofactor targets absent from the complete canonical pair table",
            "arms_disjoint":true,
            "hash_arm_attempt_cap_formula":"10000*requested + 10000"
        },
        "pair_priority":{
            "hash":"BLAKE3",
            "domain_hex":hex::encode(PAIR_PRIORITY_DOMAIN),
            "message":"domain || planted_seed || left_le_u32 || right_le_u32 || packed_target_le_u64"
        },
        "oracle":"all canonical i<=j factor-base pairs exactly once, with repetition allowed"
    });
    let policy_hash = hash_json(&policy)?;

    let (rows, covariate_extraction_ns, frobenius_applications) = covariate_rows(
        &curve,
        &[
            ("natural", &natural, &natural_result),
            ("planted_sat", &planted, &planted_result),
            ("proven_unsat", &proven_unsat, &proven_unsat_result),
        ],
    )?;
    if rows.len() != config.natural_count + config.planted_count + config.proven_unsat_count {
        return Err("ordered covariate rows do not cover every selected target".into());
    }
    let rows_hash = hash_json(&Value::Array(rows.clone()))?;

    let field_bytes = config.n.div_ceil(8) as u64;
    let encoded_point_bytes = 1 + 2 * field_bytes;
    let factor_base_payload_lower_bound = factor_base.subspace.len() as u64 * field_bytes
        + factor_base.subspace_basis.len() as u64 * field_bytes
        + factor_base.points.len() as u64 * encoded_point_bytes;
    let canonical_factor_point_clone_payload_lower_bound =
        factor_points.len() as u64 * encoded_point_bytes;
    let pair_table_live_payload_lower_bound =
        pair_build.table.len() as u64 * (size_of::<u64>() + 2 * size_of::<u32>()) as u64;
    let pair_table_capacity_payload_lower_bound =
        pair_build.table.capacity() as u64 * (size_of::<u64>() + 2 * size_of::<u32>()) as u64;
    let selected_targets_payload_lower_bound = used_targets.len() as u64 * encoded_point_bytes;

    let natural_json = arm_json(&natural, &natural_result);
    let planted_json = arm_json(&planted, &planted_result);
    let proven_unsat_json = arm_json(&proven_unsat, &proven_unsat_result);
    let arm_hashes = json!({
        "natural_targets":natural_result.target_hash,
        "natural_witness_results":natural_result.witness_hash,
        "planted_targets":planted_result.target_hash,
        "planted_witness_results":planted_result.witness_hash,
        "proven_unsat_targets":proven_unsat_result.target_hash,
        "proven_unsat_witness_results":proven_unsat_result.witness_hash
    });
    let result_binding = json!({
        "policy_blake3":policy_hash,
        "predicate_blake3":predicate_hash,
        "factor_base_blake3":factor_base_hash,
        "canonical_pair_transcript_blake3":pair_build.transcript_hash,
        "ordered_covariate_rows_blake3":rows_hash,
        "arm_hashes":arm_hashes,
        "natural_hits":natural_result.hits,
        "planted_hits":planted_result.hits,
        "proven_unsat_hits":proven_unsat_result.hits
    });
    let result_binding_hash = hash_json(&result_binding)?;

    Ok(json!({
        "schema":"koblitz_relation_yield_bridge.v1",
        "status":"complete",
        "evidence_class":if config.production_defaults_used {
            "finite_public_synthetic_measurement_pending_independent_replay_and_external_resource_receipt"
        } else {
            "operational_smoke_only_ineligible_for_ledger_promotion"
        },
        "production_defaults_used":config.production_defaults_used,
        "ledger_promotion_eligible_from_this_output_alone":false,
        "measurement_schema":{
            "stage":"relation_yield",
            "n_or_bits":config.n,
            "base_id_or_hash":factor_base_hash,
            "eta_or_coverage_policy":{
                "m":config.m,
                "target_distribution":"domain-separated BLAKE3 uniform-affine decoding and public cofactor projection",
                "oracle":"exact canonical pair table over the complete materialized factor base",
                "policy_blake3":policy_hash
            },
            "pr_decomposition_or_hit_rate_with_ci":{
                "natural_hit_rate":natural_hit_rate,
                "wilson_95_ci":{"low":natural_ci_low,"high":natural_ci_high}
            },
            "trials_per_relation":trials_per_relation,
            "target_mix":{
                "natural":natural_result.count,
                "planted_sat":planted_result.count,
                "proven_unsat":proven_unsat_result.count
            }
        },
        "frozen_policy":policy,
        "factor_base":{
            "predicate":predicate,
            "predicate_blake3":predicate_hash,
            "factor_base_blake3":factor_base_hash,
            "point_order":"ascending exact packed point key",
            "selection_and_construction_boundaries":{
                "public_field_and_curve_parameters_only":true,
                "target_available_during_selection":false,
                "target_subgroup_enumerated_for_factor_base":false,
                "factor_base_discrete_log_labels_constructed":false,
                "target_discrete_log_labels_constructed":false,
                "relation_yield_used_for_selection":false,
                "solver_timing_used_for_selection":false
            }
        },
        "exact_pair_table":{
            "summands":2,
            "repeated_factor_points_allowed":true,
            "canonical_pair_policy":"all indices i<=j exactly once",
            "canonical_pairs":pair_build.canonical_pairs,
            "enumerated_pairs":pair_build.enumerated_pairs,
            "unique_target_entries":pair_build.table.len(),
            "hash_table_capacity":pair_build.table.capacity(),
            "duplicate_pair_sums":pair_build.canonical_pairs - pair_build.table.len() as u64,
            "packed_key":"0 for infinity; 1 + (x << n | y) for affine points",
            "canonical_pair_transcript_blake3":pair_build.transcript_hash,
            "unsat_proof_boundary":"absence proves no two-point sum over this exact complete materialized factor base; it is not a SAT-solver or higher-summand UNSAT claim"
        },
        "arms":{
            "natural":natural_json,
            "planted_sat":planted_json,
            "proven_unsat":proven_unsat_json
        },
        "ordered_covariate_rows":rows,
        "ordered_covariate_rows_blake3":rows_hash,
        "timing_ns":{
            "clock":"std::time::Instant monotonic elapsed wall time",
            "curve_and_subgroup_construction":curve_construction_ns,
            "factor_base_predicate_and_materialization":factor_base_materialization_ns,
            "factor_base_projected_column_census":projected_columns_ns,
            "natural_target_generation":natural.generation_ns,
            "cofactor_class_construction":pair_build.cofactor_class_construction_ns,
            "canonical_pair_table_and_planted_priority_selection":pair_build.construction_and_selection_ns,
            "planted_construction_witness_and_subgroup_verification":pair_build.planted_final_verification_ns,
            "proven_unsat_target_screening":proven_unsat.generation_ns,
            "covariate_extraction":covariate_extraction_ns,
            "end_to_end":total_started.elapsed().as_nanos(),
            "overlap_note":"planted target selection is performed inside the canonical pair-table scan and is not an additive stage"
        },
        "high_level_operation_counts":{
            "pair_table_group_additions":pair_build.canonical_pairs,
            "factor_base_projection_scalar_multiplications":factor_base.points.len(),
            "cofactor_class_scalar_multiplications":pair_build.cofactor_class_scalar_multiplications,
            "cofactor_class_negations":pair_build.cofactor_class_negations,
            "planted_pair_priority_hashes":pair_build.planted_priority_hashes,
            "planted_final_subgroup_scalar_multiplications":pair_build.planted_final_subgroup_scalar_multiplications,
            "planted_construction_witness_verification_additions":pair_build.planted_construction_witness_verification_additions,
            "target_frobenius_applications":frobenius_applications,
            "natural":{
                "generation":generation_ops_json(natural.ops),
                "final_pair_table_lookups":natural_result.ops.table_lookups,
                "witness_verification_group_additions":natural_result.ops.witness_verification_additions
            },
            "planted_sat":{
                "canonical_pair_candidates":planted.ops.candidates,
                "final_pair_table_lookups":planted_result.ops.table_lookups,
                "witness_verification_group_additions":planted_result.ops.witness_verification_additions
            },
            "proven_unsat":{
                "generation":generation_ops_json(proven_unsat.ops),
                "final_pair_table_lookups":proven_unsat_result.ops.table_lookups,
                "witness_verification_group_additions":proven_unsat_result.ops.witness_verification_additions
            },
            "scope_note":"scalar-multiplication internals and factor-base-constructor internals are covered by elapsed wall time but are not relabeled as counted group additions"
        },
        "retained_size_lower_bounds_bytes":{
            "scope":"encoded or flat key/value payload lower bounds; Rust object headers, allocator metadata, hash-table control bytes, and unrelated capacity are excluded",
            "field_element_bytes":field_bytes,
            "encoded_point_bytes":encoded_point_bytes,
            "factor_base_payload":factor_base_payload_lower_bound,
            "canonical_factor_point_clone_payload":canonical_factor_point_clone_payload_lower_bound,
            "pair_table_live_key_and_witness_payload":pair_table_live_payload_lower_bound,
            "pair_table_capacity_key_and_witness_payload":pair_table_capacity_payload_lower_bound,
            "selected_target_coordinate_payload":selected_targets_payload_lower_bound,
            "sum_using_pair_table_capacity_payload":factor_base_payload_lower_bound
                + canonical_factor_point_clone_payload_lower_bound
                + pair_table_capacity_payload_lower_bound
                + selected_targets_payload_lower_bound
        },
        "hashes":{
            "policy_blake3":policy_hash,
            "predicate_blake3":predicate_hash,
            "factor_base_blake3":factor_base_hash,
            "canonical_pair_transcript_blake3":pair_build.transcript_hash,
            "ordered_covariate_rows_blake3":rows_hash,
            "arms":arm_hashes,
            "result_binding_blake3":result_binding_hash
        },
        "resource_accounting_boundary":{
            "single_core_elapsed_seconds":Value::Null,
            "user_cpu_seconds":Value::Null,
            "system_cpu_seconds":Value::Null,
            "total_core_seconds":Value::Null,
            "peak_rss_bytes":Value::Null,
            "host_identity":Value::Null,
            "executable_hash":Value::Null,
            "source_revision":Value::Null,
            "external_process_receipt_required":true,
            "reason":"portable Rust cannot truthfully infer process-scoped CPU, RSS, executable/source identity, or a stable host identity; bind this JSON under a separate process meter"
        },
        "claim_boundary":"Finite public-synthetic exact m=2 relation-yield control for one frozen toy factor base. This is not relation-matrix rank, linear algebra, unknown-scalar recovery, a rho crossover, an asymptotic result, external reproduction, novelty evidence, key recovery, or a deployed-curve security claim.",
        "non_claims":[
            "no SAT-solver speed claim",
            "no higher-summand UNSAT claim",
            "no natural prevalence claim outside the frozen hash-to-subgroup distribution, base, and policy",
            "no single-core, CPU, RSS, or retained-heap claim from in-process timing",
            "no SOTA or cryptographic-size security conclusion"
        ]
    }))
}

fn real_main() -> Result<(), String> {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let config = parse_args(&args)?;
    let output = run_experiment(&config)?;
    println!(
        "{}",
        serde_json::to_string_pretty(&output).map_err(|error| error.to_string())?
    );
    Ok(())
}

fn main() {
    if let Err(error) = real_main() {
        eprintln!("koblitz_relation_yield_bridge: {error}");
        std::process::exit(2);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn arm_omission_is_rejected() {
        assert!(Config::smoke(0, 1, 1).validate().is_err());
        assert!(Config::smoke(1, 0, 1).validate().is_err());
        assert!(Config::smoke(1, 1, 0).validate().is_err());
    }

    #[test]
    fn production_defaults_are_exact() {
        let config = Config::production();
        assert_eq!(config.n, 23);
        assert_eq!(config.a, 0);
        assert_eq!(config.divisor_indices, vec![0, 2]);
        assert_eq!(
            (
                config.natural_count,
                config.planted_count,
                config.proven_unsat_count
            ),
            (256, 64, 64)
        );
        assert_eq!(
            hex::encode(NATURAL_DOMAIN),
            "6b6f626c69747a2d737461676532312d6e61747572616c2d7631"
        );
        assert_eq!(
            hex::encode(PLANTED_DOMAIN),
            "6b6f626c69747a2d737461676532312d706c616e7465642d7631"
        );
        assert_eq!(
            hex::encode(PROVEN_UNSAT_DOMAIN),
            "6b6f626c69747a2d737461676532312d756e7361742d7631"
        );
    }

    #[test]
    fn wilson_interval_contains_observed_fraction() {
        let (low, high) = wilson_interval_95(7, 10).unwrap();
        assert!(low < 0.7 && 0.7 < high);
        assert_eq!(wilson_interval_95(0, 0), None);
    }

    #[test]
    fn packed_key_is_injective_on_every_smoke_curve_point() {
        let curve = KoblitzCurve::new(1, 7).unwrap();
        let mut keys = HashSet::new();
        keys.insert(pack_point(&BinaryPoint::Infinity, curve.n).unwrap());
        for x_bits in 0..(1u64 << curve.n) {
            for sign in [false, true] {
                if let Some(point) = decode_uniform_affine_draw(&curve.curve, x_bits, sign) {
                    assert!(keys.insert(pack_point(&point, curve.n).unwrap()));
                }
            }
        }
        assert_eq!(keys.len() as u64, curve.group_order.to_u64().unwrap());
    }

    #[test]
    fn planted_heap_matches_exhaustive_distinct_priority_order() {
        let config = Config::smoke(8, 4, 4);
        let curve = KoblitzCurve::new(config.a, config.n).unwrap();
        let factor_base =
            build_frobenius_factor_base_from_divisor(&curve, config.divisor_indices.as_slice())
                .unwrap();
        let mut keyed_points = factor_base
            .points
            .iter()
            .map(|point| (pack_point(point, curve.n).unwrap(), point.clone()))
            .collect::<Vec<_>>();
        keyed_points.sort_by_key(|(packed, _)| *packed);
        let points = keyed_points
            .into_iter()
            .map(|(_, point)| point)
            .collect::<Vec<_>>();
        let mut used = HashSet::new();
        select_hash_targets(
            &curve,
            config.natural_count,
            NATURAL_DOMAIN,
            None,
            false,
            &mut used,
        )
        .unwrap();
        let built =
            build_pair_table_and_select_planted(&curve, &points, config.planted_count, &used)
                .unwrap();

        let mut expected_by_target: HashMap<u64, ([u8; 32], u32, u32)> = HashMap::new();
        for left in 0..points.len() {
            for right in left..points.len() {
                let sum = curve.add(&points[left], &points[right]);
                let packed = pack_point(&sum, curve.n).unwrap();
                if packed == 0
                    || used.contains(&packed)
                    || curve.mul(&sum, &curve.subgroup_order) != BinaryPoint::Infinity
                {
                    continue;
                }
                let candidate = (
                    pair_priority(left as u32, right as u32, packed),
                    left as u32,
                    right as u32,
                );
                expected_by_target
                    .entry(packed)
                    .and_modify(|current| {
                        if candidate < *current {
                            *current = candidate;
                        }
                    })
                    .or_insert(candidate);
            }
        }
        let mut expected = expected_by_target
            .into_iter()
            .map(|(packed, (priority, _, _))| (priority, packed))
            .collect::<Vec<_>>();
        expected.sort_unstable();
        expected.truncate(config.planted_count);
        let actual = built
            .planted
            .targets
            .iter()
            .map(|target| (target.selection_priority.unwrap(), target.packed))
            .collect::<Vec<_>>();
        assert_eq!(actual, expected);
    }

    #[test]
    fn smoke_fixture_is_complete_and_deterministic() {
        let config = Config::smoke(8, 4, 4);
        let first = run_experiment(&config).expect("first smoke run");
        let second = run_experiment(&config).expect("second smoke run");

        assert_eq!(first["status"], "complete");
        assert_eq!(
            first["evidence_class"],
            "operational_smoke_only_ineligible_for_ledger_promotion"
        );
        assert_eq!(first["measurement_schema"]["target_mix"]["natural"], 8);
        assert_eq!(first["measurement_schema"]["target_mix"]["planted_sat"], 4);
        assert_eq!(first["measurement_schema"]["target_mix"]["proven_unsat"], 4);
        assert_eq!(first["arms"]["planted_sat"]["hits"], 4);
        assert_eq!(first["arms"]["planted_sat"]["verified_point_witnesses"], 4);
        assert_eq!(first["arms"]["proven_unsat"]["hits"], 0);
        assert_eq!(
            first["ordered_covariate_rows"].as_array().unwrap().len(),
            16
        );
        assert_eq!(
            first["resource_accounting_boundary"]["peak_rss_bytes"],
            Value::Null
        );
        assert_eq!(first["hashes"], second["hashes"]);
        assert!(!serde_json::to_string(&first)
            .unwrap()
            .contains("\"target_scalar\":"));
    }
}
