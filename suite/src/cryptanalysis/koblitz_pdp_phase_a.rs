//! Phase-A preparation for balanced random-target binary-Koblitz PDP panels.
//!
//! This module prepares public toy point-decomposition instances.  It never
//! performs relation collection, discrete-log recovery, or solver execution.
//! Ground-truth labels come only from an exhaustive `m = 3` factor-base
//! sumset census.  Solver-facing records deliberately omit those labels and
//! their witnesses.

use crate::binary_ecc::curve::point_add;
use crate::binary_ecc::{BinaryCurve, BinaryPoint, F2mElement};
use crate::cryptanalysis::koblitz_index_calculus::{
    factor_x_n_minus_1, find_irreducible_sparse, invariant_subspace_basis, koblitz_point_count,
    points_with_x,
};
use crate::hash::sha256;
use num_bigint::BigUint;
use num_traits::{One, ToPrimitive, Zero};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeSet, BinaryHeap, HashMap};

pub const PROTOCOL_SCHEMA: &str = "koblitz_balanced_pdp_phase_a_protocol.v1";
pub const BLIND_BUNDLE_SCHEMA: &str = "koblitz_pdp_blind_bundle.v1";
pub const BLIND_INSTANCE_SCHEMA: &str = "koblitz_pdp_blind_instance.v1";
pub const ORACLE_LEDGER_SCHEMA: &str = "koblitz_pdp_sealed_oracle_ledger.v1";
pub const MAX_FACTOR_SPACE_DIMENSION: usize = 16;

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct ClassQuotas {
    pub decomposable: usize,
    pub nondecomposable: usize,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct PhaseACell {
    pub id: String,
    pub n: u32,
    pub ell: usize,
    pub m: usize,
    pub basis: String,
    pub curve_a: u8,
    pub factor_index: usize,
    #[serde(default)]
    pub expected_factor_points: Option<usize>,
    #[serde(default)]
    pub expected_affine_targets: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct PhaseAProtocol {
    pub schema: String,
    pub status: String,
    pub master_seed_hex: String,
    #[serde(default)]
    pub master_seed_anchor_hex: Option<String>,
    pub quotas_per_cell: ClassQuotas,
    pub max_unconditional_draws_per_cell: u64,
    pub cells: Vec<PhaseACell>,
}

impl PhaseAProtocol {
    pub fn validate(&self) -> Result<[u8; 32], String> {
        if self.schema != PROTOCOL_SCHEMA {
            return Err(format!("unsupported protocol schema {}", self.schema));
        }
        if self.status != "frozen_before_preparation" {
            return Err("protocol status must be frozen_before_preparation".to_string());
        }
        if self.quotas_per_cell.decomposable == 0
            || self.quotas_per_cell.decomposable != self.quotas_per_cell.nondecomposable
        {
            return Err("class quotas must be equal and nonzero".to_string());
        }
        if self.max_unconditional_draws_per_cell < self.quotas_per_cell.nondecomposable as u64 {
            return Err("unconditional draw cap is below the nondecomposable quota".to_string());
        }
        if self.cells.is_empty() {
            return Err("protocol has no cells".to_string());
        }
        let mut ids = BTreeSet::new();
        for cell in &self.cells {
            if !ids.insert(cell.id.clone()) {
                return Err(format!("duplicate cell id {}", cell.id));
            }
            if cell.m != 3 {
                return Err(format!("{}: Phase A currently requires m=3", cell.id));
            }
            if cell.n < 3 || cell.n > 63 || cell.ell == 0 {
                return Err(format!("{}: unsupported n or ell", cell.id));
            }
            if cell.ell > cell.n as usize {
                return Err(format!(
                    "{}: factor-space dimension ell={} exceeds field degree n={}",
                    cell.id, cell.ell, cell.n
                ));
            }
            if cell.ell > MAX_FACTOR_SPACE_DIMENSION {
                return Err(format!(
                    "{}: factor-space dimension ell={} exceeds planning ceiling {}",
                    cell.id, cell.ell, MAX_FACTOR_SPACE_DIMENSION
                ));
            }
            if cell.curve_a > 1 || !matches!(cell.basis.as_str(), "standard" | "ggmp") {
                return Err(format!("{}: invalid curve or basis kind", cell.id));
            }
        }
        let seed = parse_seed(&self.master_seed_hex)?;
        if let Some(anchor_text) = &self.master_seed_anchor_hex {
            let anchor = parse_seed(anchor_text)
                .map_err(|error| format!("invalid master seed anchor: {error}"))?;
            let mut material = b"KOBLITZ-BALANCED-PDP-v1\0".to_vec();
            material.extend_from_slice(&anchor);
            let expected = sha256(&material);
            if seed != expected {
                return Err("master seed does not match its frozen Stage13 anchor".to_string());
            }
        }
        Ok(seed)
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub struct AffinePointRecord {
    pub x: String,
    pub y: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct BlindInstance {
    pub schema: String,
    pub blind_instance_id: String,
    /// Public class-blind nonce passed through the legacy exporter `seed`
    /// position and bound by the explicit-target v2 source identity.
    pub source_nonce: u64,
    /// Class-blind cluster key for the x-only Semaev source system.  Targets
    /// related by binary-curve negation share this key and must be resampled
    /// together in any later statistical analysis.
    pub source_system_id: String,
    pub cell_id: String,
    pub n: u32,
    pub ell: usize,
    pub m: usize,
    pub basis: String,
    pub curve_a: u8,
    pub factor_index: usize,
    pub target: AffinePointRecord,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct BlindBundle {
    pub schema: String,
    pub scope: String,
    pub instance_count: usize,
    pub instances: Vec<BlindInstance>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct OracleEntry {
    pub blind_instance_id: String,
    pub cell_id: String,
    pub target: AffinePointRecord,
    pub target_class: String,
    pub witness_indices: Option<[usize; 3]>,
    pub unconditional_draw_index: Option<u64>,
    pub selection_priority_hex: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CensusReceipt {
    pub schema: String,
    pub cell_id: String,
    pub factor_points: usize,
    pub factor_base_sha256: String,
    pub canonical_pairs: u128,
    pub canonical_triples: u128,
    pub group_additions: u128,
    pub distinct_affine_sum_targets: usize,
    pub affine_sumset_sha256: String,
    pub digest_encoding: String,
    pub independent_distinct_affine_sum_targets: usize,
    pub independent_affine_sumset_sha256: String,
    pub independent_group_additions: u128,
    pub independent_replay_equal: bool,
    pub affine_target_population: String,
    pub natural_decomposable_numerator: String,
    pub natural_decomposable_denominator: String,
    pub exhaustive: bool,
    pub selected_witnesses_revalidated: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct OracleCell {
    pub cell: PhaseACell,
    pub census: CensusReceipt,
    pub sampler: SamplerReceipt,
    pub entries: Vec<OracleEntry>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SamplerReceipt {
    pub schema: String,
    pub cell_id: String,
    pub stream_domain: String,
    pub draw_cap: u64,
    pub draws_examined: u64,
    pub accepted_affine_draws: u64,
    pub affine_decode_rejections: u64,
    pub decomposable_rejections: u64,
    pub duplicate_rejections: u64,
    pub selected_nondecomposable: usize,
    pub accepted_stream_sha256: String,
    pub digest_encoding: String,
    pub exact_uniform_affine_mapping: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct OracleLedger {
    pub schema: String,
    pub scope: String,
    pub cells: Vec<OracleCell>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CellPlan {
    pub cell_id: String,
    pub n: u32,
    pub ell: usize,
    pub basis: String,
    pub curve_a: u8,
    pub factor_points: usize,
    pub canonical_pairs: u128,
    pub canonical_triples: u128,
    pub affine_target_population: String,
    pub selected_instances: usize,
    pub planned_solver_runs: usize,
    pub census_executed: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct PreparationPlan {
    pub schema: String,
    pub protocol_schema: String,
    pub cells: Vec<CellPlan>,
    pub selected_cell_ids: Vec<String>,
    pub requested_max_canonical_triples: Option<u128>,
    pub total_selected_instances: usize,
    pub total_planned_solver_runs: usize,
    pub largest_canonical_triple_count: u128,
    pub census_executed: bool,
    pub interpretation: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct PreparationArtifacts {
    pub blind: BlindBundle,
    pub oracle: OracleLedger,
    pub plan: PreparationPlan,
}

#[derive(Clone, Copy, Debug, Hash, PartialEq, Eq, PartialOrd, Ord)]
struct PointKey(u64, u64);

#[derive(Clone, Debug)]
struct CellGeometry {
    curve: BinaryCurve,
    factor_points: Vec<BinaryPoint>,
}

#[derive(Clone, Debug)]
struct SelectedPoint {
    point: AffinePointRecord,
    target_class: &'static str,
    witness: Option<[usize; 3]>,
    draw_index: Option<u64>,
    selection_priority: [u8; 32],
}

fn parse_seed(text: &str) -> Result<[u8; 32], String> {
    let bytes = hex::decode(text).map_err(|error| format!("master seed is not hex: {error}"))?;
    bytes
        .try_into()
        .map_err(|_| "master seed must contain exactly 32 bytes".to_string())
}

fn point_key(point: &BinaryPoint) -> Option<PointKey> {
    match point {
        BinaryPoint::Infinity => None,
        BinaryPoint::Affine { x, y } => Some(PointKey(
            x.to_biguint().to_u64().expect("n <= 63 point x fits u64"),
            y.to_biguint().to_u64().expect("n <= 63 point y fits u64"),
        )),
    }
}

fn record_from_key(key: &PointKey) -> AffinePointRecord {
    AffinePointRecord {
        x: key.0.to_string(),
        y: key.1.to_string(),
    }
}

fn key_bytes(key: &PointKey) -> [u8; 16] {
    let mut out = [0u8; 16];
    out[..8].copy_from_slice(&key.0.to_le_bytes());
    out[8..].copy_from_slice(&key.1.to_le_bytes());
    out
}

fn keyed_digest(seed: &[u8; 32], domain: &str, cell_id: &str, key: &PointKey) -> [u8; 32] {
    let mut hasher = blake3::Hasher::new_keyed(seed);
    hasher.update(domain.as_bytes());
    hasher.update(&[0]);
    hasher.update(cell_id.as_bytes());
    hasher.update(&[0]);
    hasher.update(&key_bytes(key));
    *hasher.finalize().as_bytes()
}

fn digest_keys<'a>(keys: impl IntoIterator<Item = &'a PointKey>) -> String {
    let mut bytes = Vec::new();
    for key in keys {
        bytes.extend_from_slice(&key_bytes(key));
    }
    hex::encode(sha256(&bytes))
}

fn choose2(n: usize) -> u128 {
    let n = n as u128;
    n * (n + 1) / 2
}

fn choose3(n: usize) -> u128 {
    let n = n as u128;
    n * (n + 1) * (n + 2) / 6
}

fn build_geometry(cell: &PhaseACell) -> Result<CellGeometry, String> {
    let (irreducible, basis) = match cell.basis.as_str() {
        "standard" => {
            let irreducible = find_irreducible_sparse(cell.n)
                .ok_or_else(|| format!("{}: no sparse irreducible polynomial", cell.id))?;
            let basis = (0..cell.ell)
                .map(|index| F2mElement::from_bit_positions(&[index as u32], cell.n))
                .collect();
            (irreducible, basis)
        }
        "ggmp" => {
            let (irreducible, basis) = invariant_subspace_basis(cell.n, cell.factor_index)
                .ok_or_else(|| format!("{}: no requested GGMP invariant subspace", cell.id))?;
            if basis.len() != cell.ell {
                return Err(format!(
                    "{}: GGMP basis dimension {} differs from frozen ell {}",
                    cell.id,
                    basis.len(),
                    cell.ell
                ));
            }
            let _ = factor_x_n_minus_1(cell.n)
                .get(cell.factor_index)
                .ok_or_else(|| format!("{}: GGMP factor index is out of range", cell.id))?;
            (irreducible, basis)
        }
        _ => return Err(format!("{}: unsupported basis kind", cell.id)),
    };
    let curve = BinaryCurve {
        m: cell.n,
        irreducible,
        a: if cell.curve_a == 0 {
            F2mElement::zero(cell.n)
        } else {
            F2mElement::one(cell.n)
        },
        b: F2mElement::one(cell.n),
        generator: BinaryPoint::Infinity,
        order: BigUint::zero(),
        cofactor: BigUint::one(),
    };
    let mut factor_points = Vec::new();
    for mask in 0..(1usize << basis.len()) {
        let mut x = F2mElement::zero(cell.n);
        for (index, element) in basis.iter().enumerate() {
            if (mask >> index) & 1 == 1 {
                x = x.add(element);
            }
        }
        factor_points.extend(points_with_x(&curve, &x));
    }
    factor_points.sort_by_key(point_key);
    factor_points.dedup_by_key(|point| point_key(point));
    if let Some(expected) = cell.expected_factor_points {
        if factor_points.len() != expected {
            return Err(format!(
                "{}: factor-point count {} differs from frozen {}",
                cell.id,
                factor_points.len(),
                expected
            ));
        }
    }
    Ok(CellGeometry {
        curve,
        factor_points,
    })
}

/// Decode one exactly uniform draw from `F_(2^n) x {0,1}`.
///
/// Each accepted affine point has exactly one accepted preimage: the two
/// nonzero-x lifts use their canonical y-order, while the unique x=0 lift
/// accepts only sign zero.  Rejection therefore gives a uniform affine point.
pub fn decode_uniform_affine_draw(
    curve: &BinaryCurve,
    x_bits: u64,
    sign: bool,
) -> Option<BinaryPoint> {
    if curve.m > 63 || x_bits >= (1u64 << curve.m) {
        return None;
    }
    let x = F2mElement::from_biguint(&BigUint::from(x_bits), curve.m);
    let mut lifts = points_with_x(curve, &x);
    lifts.sort_by_key(point_key);
    if x_bits == 0 {
        if sign || lifts.len() != 1 {
            return None;
        }
        return lifts.into_iter().next();
    }
    if lifts.len() != 2 {
        return None;
    }
    Some(lifts[usize::from(sign)].clone())
}

fn uniform_affine_draw(
    curve: &BinaryCurve,
    seed: &[u8; 32],
    cell_id: &str,
    draw_index: u64,
) -> Option<BinaryPoint> {
    let mut hasher = blake3::Hasher::new_keyed(seed);
    hasher.update(b"uniform-affine-draw-v1\0");
    hasher.update(cell_id.as_bytes());
    hasher.update(&[0]);
    hasher.update(&draw_index.to_le_bytes());
    let digest = hasher.finalize();
    let bytes = digest.as_bytes();
    let mut x_bytes = [0u8; 8];
    x_bytes.copy_from_slice(&bytes[..8]);
    let mask = (1u64 << curve.m) - 1;
    decode_uniform_affine_draw(curve, u64::from_le_bytes(x_bytes) & mask, bytes[8] & 1 == 1)
}

fn complete_m3_sumset(
    curve: &BinaryCurve,
    factor_points: &[BinaryPoint],
) -> (HashMap<PointKey, [u16; 3]>, u128) {
    assert!(factor_points.len() <= usize::from(u16::MAX));
    let mut pairs = Vec::with_capacity(usize::try_from(choose2(factor_points.len())).unwrap());
    let mut additions = 0u128;
    for i in 0..factor_points.len() {
        for j in i..factor_points.len() {
            pairs.push((i, j, point_add(curve, &factor_points[i], &factor_points[j])));
            additions += 1;
        }
    }
    let mut sums = HashMap::new();
    for (i, j, pair) in pairs {
        for k in j..factor_points.len() {
            additions += 1;
            if let Some(key) = point_key(&point_add(curve, &pair, &factor_points[k])) {
                sums.entry(key).or_insert([i as u16, j as u16, k as u16]);
            }
        }
    }
    (sums, additions)
}

/// Independently materialize the canonical triple stream into a flat packed
/// vector, then numeric-sort and deduplicate it.  This intentionally shares
/// neither the primary pair cache nor its hash-table accumulation path.
fn independent_m3_sumset_digest(
    curve: &BinaryCurve,
    factor_points: &[BinaryPoint],
) -> (usize, String, u128) {
    let expected_triples = choose3(factor_points.len());
    let mut keys = Vec::with_capacity(usize::try_from(expected_triples).unwrap());
    let mut additions = 0u128;
    for i in 0..factor_points.len() {
        for j in i..factor_points.len() {
            let pair = point_add(curve, &factor_points[i], &factor_points[j]);
            additions += 1;
            for k in j..factor_points.len() {
                additions += 1;
                if let Some(key) = point_key(&point_add(curve, &pair, &factor_points[k])) {
                    keys.push(key);
                }
            }
        }
    }
    keys.sort_unstable();
    keys.dedup();
    let digest = digest_keys(keys.iter());
    (keys.len(), digest, additions)
}

fn blind_id(seed: &[u8; 32], cell_id: &str, key: &PointKey) -> String {
    format!(
        "b-{}",
        hex::encode(keyed_digest(seed, "blind-instance-id-v1", cell_id, key))
    )
}

fn source_system_id(seed: &[u8; 32], cell_id: &str, key: &PointKey) -> String {
    let x_only = PointKey(key.0, 0);
    format!(
        "x-{}",
        hex::encode(keyed_digest(
            seed,
            "source-system-cluster-id-v1",
            cell_id,
            &x_only,
        ))
    )
}

fn source_nonce(seed: &[u8; 32], cell_id: &str, key: &PointKey) -> u64 {
    let digest = keyed_digest(seed, "explicit-export-source-nonce-v1", cell_id, key);
    u64::from_le_bytes(digest[..8].try_into().unwrap())
}

fn prepare_cell(
    protocol: &PhaseAProtocol,
    seed: &[u8; 32],
    cell: &PhaseACell,
) -> Result<(Vec<(BlindInstance, [u8; 32])>, OracleCell), String> {
    let geometry = build_geometry(cell)?;
    let factor_keys: Vec<_> = geometry
        .factor_points
        .iter()
        .filter_map(point_key)
        .collect();
    let (sumset, group_additions) = complete_m3_sumset(&geometry.curve, &geometry.factor_points);
    let expected_additions =
        choose2(geometry.factor_points.len()) + choose3(geometry.factor_points.len());
    if group_additions != expected_additions {
        return Err(format!(
            "{}: census addition count {} differs from expected {}",
            cell.id, group_additions, expected_additions
        ));
    }
    let mut sumset_keys: Vec<_> = sumset.keys().copied().collect();
    sumset_keys.sort_unstable();
    let primary_sumset_digest = digest_keys(sumset_keys.iter());
    drop(sumset_keys);
    let (
        independent_distinct_affine_sum_targets,
        independent_affine_sumset_sha256,
        independent_group_additions,
    ) = independent_m3_sumset_digest(&geometry.curve, &geometry.factor_points);
    if independent_group_additions != expected_additions
        || independent_distinct_affine_sum_targets != sumset.len()
        || independent_affine_sumset_sha256 != primary_sumset_digest
    {
        return Err(format!(
            "{}: independent sorted-sumset replay disagrees with primary census",
            cell.id
        ));
    }
    let quota = &protocol.quotas_per_cell;
    if sumset.len() < quota.decomposable {
        return Err(format!(
            "{}: only {} decomposable affine targets for quota {}",
            cell.id,
            sumset.len(),
            quota.decomposable
        ));
    }

    let mut ranked_sat = BinaryHeap::with_capacity(quota.decomposable + 1);
    for (key, witness) in &sumset {
        let candidate = (
            keyed_digest(seed, "decomposable-target-priority-v1", &cell.id, key),
            *key,
            (*witness).map(usize::from),
        );
        if ranked_sat.len() < quota.decomposable {
            ranked_sat.push(candidate);
        } else if ranked_sat
            .peek()
            .is_some_and(|largest_selected| candidate < *largest_selected)
        {
            ranked_sat.pop();
            ranked_sat.push(candidate);
        }
    }
    let mut ranked_sat = ranked_sat.into_vec();
    ranked_sat.sort_by(|left, right| left.0.cmp(&right.0).then(left.1.cmp(&right.1)));
    let mut selected: Vec<SelectedPoint> = ranked_sat
        .into_iter()
        .take(quota.decomposable)
        .map(|(priority, key, witness)| SelectedPoint {
            point: record_from_key(&key),
            target_class: "decomposable",
            witness: Some(witness),
            draw_index: None,
            selection_priority: priority,
        })
        .collect();

    let mut seen_unsat = BTreeSet::new();
    let mut draws_examined = 0u64;
    let mut accepted_affine_draws = 0u64;
    let mut affine_decode_rejections = 0u64;
    let mut decomposable_rejections = 0u64;
    let mut duplicate_rejections = 0u64;
    let mut accepted_stream_bytes = Vec::new();
    for draw_index in 0..protocol.max_unconditional_draws_per_cell {
        if seen_unsat.len() == quota.nondecomposable {
            break;
        }
        draws_examined = draw_index + 1;
        let Some(point) = uniform_affine_draw(&geometry.curve, seed, &cell.id, draw_index) else {
            affine_decode_rejections += 1;
            continue;
        };
        let key = point_key(&point).expect("sampler emits affine points");
        accepted_affine_draws += 1;
        accepted_stream_bytes.extend_from_slice(&key_bytes(&key));
        if sumset.contains_key(&key) {
            decomposable_rejections += 1;
            continue;
        }
        if !seen_unsat.insert(key) {
            duplicate_rejections += 1;
            continue;
        }
        selected.push(SelectedPoint {
            point: record_from_key(&key),
            target_class: "nondecomposable",
            witness: None,
            draw_index: Some(draw_index),
            selection_priority: keyed_digest(
                seed,
                "nondecomposable-target-priority-v1",
                &cell.id,
                &key,
            ),
        });
    }
    if seen_unsat.len() != quota.nondecomposable {
        return Err(format!(
            "{}: draw cap produced {} nondecomposable targets for quota {}",
            cell.id,
            seen_unsat.len(),
            quota.nondecomposable
        ));
    }

    let mut blind = Vec::with_capacity(selected.len());
    let mut oracle_entries = Vec::with_capacity(selected.len());
    let mut ids = BTreeSet::new();
    for item in selected {
        let key = PointKey(
            item.point.x.parse().expect("prepared target x fits u64"),
            item.point.y.parse().expect("prepared target y fits u64"),
        );
        if let Some([i, j, k]) = item.witness {
            let witness_sum = point_add(
                &geometry.curve,
                &point_add(
                    &geometry.curve,
                    &geometry.factor_points[i],
                    &geometry.factor_points[j],
                ),
                &geometry.factor_points[k],
            );
            if point_key(&witness_sum) != Some(key) {
                return Err(format!(
                    "{}: selected witness failed exact revalidation",
                    cell.id
                ));
            }
        }
        let id = blind_id(seed, &cell.id, &key);
        if !ids.insert(id.clone()) {
            return Err(format!("{}: blind instance id collision", cell.id));
        }
        let presentation = keyed_digest(seed, "blind-presentation-priority-v1", &cell.id, &key);
        blind.push((
            BlindInstance {
                schema: BLIND_INSTANCE_SCHEMA.to_string(),
                blind_instance_id: id.clone(),
                source_nonce: source_nonce(seed, &cell.id, &key),
                source_system_id: source_system_id(seed, &cell.id, &key),
                cell_id: cell.id.clone(),
                n: cell.n,
                ell: cell.ell,
                m: cell.m,
                basis: cell.basis.clone(),
                curve_a: cell.curve_a,
                factor_index: cell.factor_index,
                target: item.point.clone(),
            },
            presentation,
        ));
        oracle_entries.push(OracleEntry {
            blind_instance_id: id,
            cell_id: cell.id.clone(),
            target: item.point,
            target_class: item.target_class.to_string(),
            witness_indices: item.witness,
            unconditional_draw_index: item.draw_index,
            selection_priority_hex: hex::encode(item.selection_priority),
        });
    }
    oracle_entries.sort_by(|left, right| left.blind_instance_id.cmp(&right.blind_instance_id));

    let affine_population = koblitz_point_count(cell.curve_a, cell.n) - BigUint::one();
    if let Some(expected) = &cell.expected_affine_targets {
        if &affine_population.to_string() != expected {
            return Err(format!(
                "{}: affine population {} differs from frozen {}",
                cell.id, affine_population, expected
            ));
        }
    }
    let receipt = CensusReceipt {
        schema: "koblitz_pdp_complete_m3_sumset_census.v1".to_string(),
        cell_id: cell.id.clone(),
        factor_points: geometry.factor_points.len(),
        factor_base_sha256: digest_keys(factor_keys.iter()),
        canonical_pairs: choose2(geometry.factor_points.len()),
        canonical_triples: choose3(geometry.factor_points.len()),
        group_additions,
        distinct_affine_sum_targets: sumset.len(),
        affine_sumset_sha256: primary_sumset_digest,
        digest_encoding:
            "numeric lexicographic order by (x,y), then LE64(x)||LE64(y), concatenated without separators"
                .to_string(),
        independent_distinct_affine_sum_targets,
        independent_affine_sumset_sha256,
        independent_group_additions,
        independent_replay_equal: true,
        affine_target_population: affine_population.to_string(),
        natural_decomposable_numerator: sumset.len().to_string(),
        natural_decomposable_denominator: affine_population.to_string(),
        exhaustive: true,
        selected_witnesses_revalidated: true,
    };
    Ok((
        blind,
        OracleCell {
            cell: cell.clone(),
            census: receipt,
            sampler: SamplerReceipt {
                schema: "koblitz_pdp_uniform_affine_sampler_receipt.v1".to_string(),
                cell_id: cell.id.clone(),
                stream_domain: "uniform-affine-draw-v1".to_string(),
                draw_cap: protocol.max_unconditional_draws_per_cell,
                draws_examined,
                accepted_affine_draws,
                affine_decode_rejections,
                decomposable_rejections,
                duplicate_rejections,
                selected_nondecomposable: seen_unsat.len(),
                accepted_stream_sha256: hex::encode(sha256(&accepted_stream_bytes)),
                digest_encoding: "accepted decoded points in draw order as LE64(x)||LE64(y)"
                    .to_string(),
                exact_uniform_affine_mapping: true,
            },
            entries: oracle_entries,
        },
    ))
}

pub fn plan_protocol(protocol: &PhaseAProtocol) -> Result<PreparationPlan, String> {
    protocol.validate()?;
    let per_cell_instances =
        protocol.quotas_per_cell.decomposable + protocol.quotas_per_cell.nondecomposable;
    let mut cells = Vec::new();
    for cell in &protocol.cells {
        let geometry = build_geometry(cell)?;
        let affine_population = koblitz_point_count(cell.curve_a, cell.n) - BigUint::one();
        if let Some(expected) = &cell.expected_affine_targets {
            if &affine_population.to_string() != expected {
                return Err(format!("{}: frozen affine population mismatch", cell.id));
            }
        }
        cells.push(CellPlan {
            cell_id: cell.id.clone(),
            n: cell.n,
            ell: cell.ell,
            basis: cell.basis.clone(),
            curve_a: cell.curve_a,
            factor_points: geometry.factor_points.len(),
            canonical_pairs: choose2(geometry.factor_points.len()),
            canonical_triples: choose3(geometry.factor_points.len()),
            affine_target_population: affine_population.to_string(),
            selected_instances: per_cell_instances,
            planned_solver_runs: per_cell_instances * 3,
            census_executed: false,
        });
    }
    let total_selected_instances = per_cell_instances * cells.len();
    Ok(PreparationPlan {
        schema: "koblitz_balanced_pdp_phase_a_plan.v1".to_string(),
        protocol_schema: protocol.schema.clone(),
        largest_canonical_triple_count: cells
            .iter()
            .map(|cell| cell.canonical_triples)
            .max()
            .unwrap_or(0),
        total_selected_instances,
        total_planned_solver_runs: total_selected_instances * 3,
        cells,
        selected_cell_ids: protocol.cells.iter().map(|cell| cell.id.clone()).collect(),
        requested_max_canonical_triples: None,
        census_executed: false,
        interpretation:
            "Planning and static factor-base geometry only; no sumset census or solver run"
                .to_string(),
    })
}

pub fn prepare_protocol(
    protocol: &PhaseAProtocol,
    selected_cells: &[String],
    max_canonical_triples: u128,
) -> Result<PreparationArtifacts, String> {
    let seed = protocol.validate()?;
    let plan = plan_protocol(protocol)?;
    let selected: BTreeSet<_> = if selected_cells.is_empty() {
        protocol.cells.iter().map(|cell| cell.id.clone()).collect()
    } else {
        selected_cells.iter().cloned().collect()
    };
    for requested in &selected {
        if !protocol.cells.iter().any(|cell| &cell.id == requested) {
            return Err(format!("unknown selected cell {requested}"));
        }
    }
    for cell_plan in plan
        .cells
        .iter()
        .filter(|cell| selected.contains(&cell.cell_id))
    {
        if cell_plan.canonical_triples > max_canonical_triples {
            return Err(format!(
                "{} requires {} canonical triples, above explicit ceiling {}",
                cell_plan.cell_id, cell_plan.canonical_triples, max_canonical_triples
            ));
        }
    }

    let mut blind_with_priority = Vec::new();
    let mut oracle_cells = Vec::new();
    for cell in protocol
        .cells
        .iter()
        .filter(|cell| selected.contains(&cell.id))
    {
        let (mut blind, oracle) = prepare_cell(protocol, &seed, cell)?;
        blind_with_priority.append(&mut blind);
        oracle_cells.push(oracle);
    }
    blind_with_priority.sort_by(|left, right| {
        left.1
            .cmp(&right.1)
            .then(left.0.blind_instance_id.cmp(&right.0.blind_instance_id))
    });
    let global_ids: BTreeSet<_> = blind_with_priority
        .iter()
        .map(|(instance, _)| instance.blind_instance_id.as_str())
        .collect();
    if global_ids.len() != blind_with_priority.len() {
        return Err("blind instance id collision across cells".to_string());
    }
    let instances: Vec<_> = blind_with_priority
        .into_iter()
        .map(|(instance, _)| instance)
        .collect();
    let selected_plan_cells: Vec<_> = plan
        .cells
        .iter()
        .filter(|cell| selected.contains(&cell.cell_id))
        .cloned()
        .map(|mut cell| {
            cell.census_executed = true;
            cell
        })
        .collect();
    let selected_instances: usize = selected_plan_cells
        .iter()
        .map(|cell| cell.selected_instances)
        .sum();
    let prepared_plan = PreparationPlan {
        schema: plan.schema,
        protocol_schema: plan.protocol_schema,
        largest_canonical_triple_count: selected_plan_cells
            .iter()
            .map(|cell| cell.canonical_triples)
            .max()
            .unwrap_or(0),
        total_selected_instances: selected_instances,
        total_planned_solver_runs: selected_instances * 3,
        cells: selected_plan_cells,
        selected_cell_ids: selected.iter().cloned().collect(),
        requested_max_canonical_triples: Some(max_canonical_triples),
        census_executed: true,
        interpretation: "Phase-A class preparation only; no SAT backend or long panel execution"
            .to_string(),
    };
    Ok(PreparationArtifacts {
        blind: BlindBundle {
            schema: BLIND_BUNDLE_SCHEMA.to_string(),
            scope: "Opaque public toy PDP targets for a separately metered solver phase"
                .to_string(),
            instance_count: instances.len(),
            instances,
        },
        oracle: OracleLedger {
            schema: ORACLE_LEDGER_SCHEMA.to_string(),
            scope: "Sealed Phase-A ground truth from exhaustive direct m=3 sumset census"
                .to_string(),
            cells: oracle_cells,
        },
        plan: prepared_plan,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeMap;

    fn tiny_cell() -> PhaseACell {
        PhaseACell {
            id: "tiny-n7-standard".to_string(),
            n: 7,
            ell: 2,
            m: 3,
            basis: "standard".to_string(),
            curve_a: 0,
            factor_index: 0,
            expected_factor_points: None,
            expected_affine_targets: None,
        }
    }

    fn tiny_protocol() -> PhaseAProtocol {
        PhaseAProtocol {
            schema: PROTOCOL_SCHEMA.to_string(),
            status: "frozen_before_preparation".to_string(),
            master_seed_hex: "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
                .to_string(),
            master_seed_anchor_hex: None,
            quotas_per_cell: ClassQuotas {
                decomposable: 2,
                nondecomposable: 2,
            },
            max_unconditional_draws_per_cell: 10_000,
            cells: vec![tiny_cell()],
        }
    }

    #[test]
    fn affine_draw_encoding_is_exactly_one_to_one_on_tiny_curve() {
        let geometry = build_geometry(&tiny_cell()).unwrap();
        let mut counts = BTreeMap::<PointKey, usize>::new();
        for x in 0..(1u64 << geometry.curve.m) {
            for sign in [false, true] {
                if let Some(point) = decode_uniform_affine_draw(&geometry.curve, x, sign) {
                    *counts.entry(point_key(&point).unwrap()).or_default() += 1;
                }
            }
        }
        assert!(counts.values().all(|count| *count == 1));
        assert_eq!(
            BigUint::from(counts.len()),
            koblitz_point_count(tiny_cell().curve_a, tiny_cell().n) - BigUint::one()
        );
    }

    #[test]
    fn mitm_sumset_matches_independent_ordered_triple_enumeration() {
        let geometry = build_geometry(&tiny_cell()).unwrap();
        let (mitm, additions) = complete_m3_sumset(&geometry.curve, &geometry.factor_points);
        let mut brute = BTreeSet::new();
        for left in &geometry.factor_points {
            for middle in &geometry.factor_points {
                for right in &geometry.factor_points {
                    let sum = point_add(
                        &geometry.curve,
                        &point_add(&geometry.curve, left, middle),
                        right,
                    );
                    if let Some(key) = point_key(&sum) {
                        brute.insert(key);
                    }
                }
            }
        }
        assert_eq!(mitm.keys().cloned().collect::<BTreeSet<_>>(), brute);
        let mut primary_keys: Vec<_> = mitm.keys().copied().collect();
        primary_keys.sort_unstable();
        let (independent_count, independent_digest, independent_additions) =
            independent_m3_sumset_digest(&geometry.curve, &geometry.factor_points);
        assert_eq!(independent_count, mitm.len());
        assert_eq!(independent_digest, digest_keys(primary_keys.iter()));
        assert_eq!(independent_additions, additions);
        for (key, [i, j, k]) in mitm {
            let [i, j, k] = [i, j, k].map(usize::from);
            let sum = point_add(
                &geometry.curve,
                &point_add(
                    &geometry.curve,
                    &geometry.factor_points[i],
                    &geometry.factor_points[j],
                ),
                &geometry.factor_points[k],
            );
            assert_eq!(point_key(&sum), Some(key));
        }
    }

    #[test]
    fn inverse_targets_have_distinct_blind_ids_and_one_source_cluster() {
        let cell = tiny_cell();
        let geometry = build_geometry(&cell).unwrap();
        let seed = parse_seed(&tiny_protocol().master_seed_hex).unwrap();
        let lifts = (1..(1u64 << cell.n))
            .find_map(|x| {
                let points = points_with_x(
                    &geometry.curve,
                    &F2mElement::from_biguint(&BigUint::from(x), cell.n),
                );
                (points.len() == 2).then_some(points)
            })
            .expect("tiny ordinary curve has a two-lift x coordinate");
        let left = point_key(&lifts[0]).unwrap();
        let right = point_key(&lifts[1]).unwrap();
        assert_ne!(
            blind_id(&seed, &cell.id, &left),
            blind_id(&seed, &cell.id, &right)
        );
        assert_eq!(
            source_system_id(&seed, &cell.id, &left),
            source_system_id(&seed, &cell.id, &right)
        );
    }

    #[test]
    fn preparation_is_deterministic_and_solver_bundle_has_no_oracle_fields() {
        let protocol = tiny_protocol();
        let first = prepare_protocol(&protocol, &[], 10_000).unwrap();
        let second = prepare_protocol(&protocol, &[], 10_000).unwrap();
        assert_eq!(first, second);
        assert_eq!(first.blind.instance_count, 4);
        assert_eq!(first.oracle.cells[0].entries.len(), 4);
        assert_eq!(first.oracle.cells[0].sampler.selected_nondecomposable, 2);
        let blind = serde_json::to_string(&first.blind).unwrap();
        for forbidden in [
            "decomposable",
            "nondecomposable",
            "target_class",
            "witness_indices",
            "selection_priority",
            "unconditional_draw_index",
            "planted",
        ] {
            assert!(
                !blind.contains(forbidden),
                "blind bundle leaked {forbidden}"
            );
        }
        let labels: BTreeMap<_, _> = first.oracle.cells[0]
            .entries
            .iter()
            .map(|entry| (entry.target_class.as_str(), 1usize))
            .fold(BTreeMap::new(), |mut counts, (label, one)| {
                *counts.entry(label).or_default() += one;
                counts
            });
        assert_eq!(labels.get("decomposable"), Some(&2));
        assert_eq!(labels.get("nondecomposable"), Some(&2));
    }

    #[test]
    fn frozen_tiny_vector() {
        let prepared = prepare_protocol(&tiny_protocol(), &[], 10_000).unwrap();
        let blind_bytes = serde_json::to_vec(&prepared.blind).unwrap();
        let oracle_bytes = serde_json::to_vec(&prepared.oracle).unwrap();
        assert_eq!(
            prepared.oracle.cells[0].census.factor_base_sha256,
            "2f2f859ca57976f3f1edf3f7bb9964787a3f2bc5096dc00d0f724b4695a3990e"
        );
        assert_eq!(
            prepared.oracle.cells[0].census.affine_sumset_sha256,
            "2f2f859ca57976f3f1edf3f7bb9964787a3f2bc5096dc00d0f724b4695a3990e"
        );
        assert_eq!(
            hex::encode(sha256(&blind_bytes)),
            "7997616ca68548bea6df2b0c1552e528f4a02acc09f0b6e5498749927c58e032"
        );
        assert_eq!(
            hex::encode(sha256(&oracle_bytes)),
            "05997f0d822042b74aedd08efc34f56fe5a51a155743005cd11c5064a878175e"
        );
        assert_eq!(
            prepared.blind.instances[0].blind_instance_id,
            "b-93b793dcd04412d49ae9409c9e14845b6e57cb490b777c27d5e3d333fbe64b71"
        );
    }

    #[test]
    fn explicit_ceiling_blocks_large_census_before_preparation() {
        let protocol = tiny_protocol();
        let plan = plan_protocol(&protocol).unwrap();
        assert!(!plan.census_executed);
        let error = prepare_protocol(&protocol, &[], 0).unwrap_err();
        assert!(error.contains("above explicit ceiling"));
    }

    #[test]
    fn protocol_rejects_impossible_and_oversized_factor_spaces() {
        let mut impossible = tiny_protocol();
        impossible.cells[0].ell = 8;
        assert!(impossible
            .validate()
            .unwrap_err()
            .contains("exceeds field degree"));

        let mut oversized = tiny_protocol();
        oversized.cells[0].n = 31;
        oversized.cells[0].ell = MAX_FACTOR_SPACE_DIMENSION + 1;
        assert!(oversized
            .validate()
            .unwrap_err()
            .contains("exceeds planning ceiling"));
    }
}
