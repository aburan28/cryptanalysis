//! Stage-23 public-synthetic unknown-scalar panel producer.
//!
//! Target generation, index calculus, and signed-Frobenius rho are separate
//! process modes. Solver modes receive only a public point and a public walk
//! seed; no target scalar is constructed or supplied.

use cryptanalysis_suite::binary_ecc::{BinaryPoint, F2mElement};
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::SolverEngine;
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base_from_divisor,
    koblitz_index_calculus_dlp_with_factor_base_and_progress,
    koblitz_signed_frobenius_rho_with_progress, DecompositionStrategy, KoblitzCurve,
    KoblitzIcEvent, KoblitzIcOptions, KoblitzRelation, KoblitzRelationAttemptDisposition,
    KoblitzRelationAttemptRecord, KoblitzSignedRhoEvent, KoblitzSignedRhoOptions, LinearAlgebra,
    SatDecompositionOptions,
};
use cryptanalysis_suite::cryptanalysis::koblitz_pdp_phase_a::decode_uniform_affine_draw;
use cryptanalysis_suite::cryptanalysis::semaev_sat::XorEncoding;
use num_bigint::BigUint;
use num_traits::ToPrimitive;
use serde_json::{json, Value};
use std::collections::HashSet;
use std::env;
use std::time::Instant;

const TARGET_DOMAIN: &[u8] = b"koblitz-stage23-public-target-v1\0";
const IC_SEED_DOMAIN: &[u8] = b"koblitz-stage23-ic-seed-v1\0";
const RHO_SEED_DOMAIN: &[u8] = b"koblitz-stage23-rho-seed-v1\0";
const TARGET_ID_DOMAIN: &[u8] = b"koblitz-stage23-target-id-v1\0";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Profile {
    Production,
    Smoke,
}

impl Profile {
    fn parse(value: &str) -> Result<Self, String> {
        match value {
            "production" => Ok(Self::Production),
            "smoke" => Ok(Self::Smoke),
            _ => Err("profile must be production or smoke".into()),
        }
    }

    fn name(self) -> &'static str {
        match self {
            Self::Production => "production",
            Self::Smoke => "smoke",
        }
    }

    fn n(self) -> u32 {
        match self {
            Self::Production => 23,
            Self::Smoke => 7,
        }
    }

    fn curve_a(self) -> u8 {
        1 - u8::from(self == Self::Production)
    }

    fn divisor_indices(self) -> &'static [usize] {
        &[0, 2]
    }

    fn target_count(self) -> usize {
        match self {
            Self::Production => 5,
            Self::Smoke => 2,
        }
    }

    fn conflict_budget(self) -> u64 {
        match self {
            Self::Production => 100_000,
            Self::Smoke => 10_000,
        }
    }

    fn max_trials(self) -> usize {
        match self {
            Self::Production => 1_000,
            Self::Smoke => 1_000,
        }
    }

    fn rho_max_iterations(self) -> u64 {
        match self {
            Self::Production => 1 << 28,
            Self::Smoke => 1 << 20,
        }
    }

    fn rho_max_restarts(self) -> u32 {
        match self {
            Self::Production => 64,
            Self::Smoke => 16,
        }
    }
}

fn point_json(point: &BinaryPoint) -> Value {
    match point {
        BinaryPoint::Infinity => Value::Null,
        BinaryPoint::Affine { x, y } => json!({
            "x":x.to_biguint().to_string(),
            "y":y.to_biguint().to_string()
        }),
    }
}

fn pack_point(point: &BinaryPoint, n: u32) -> Result<u64, String> {
    match point {
        BinaryPoint::Infinity => Ok(0),
        BinaryPoint::Affine { x, y } => {
            if n == 0 || 2 * n >= 63 {
                return Err("packed point requires 0 < 2*n < 63".into());
            }
            let x = x
                .to_biguint()
                .to_u64()
                .ok_or_else(|| "x does not fit u64".to_string())?;
            let y = y
                .to_biguint()
                .to_u64()
                .ok_or_else(|| "y does not fit u64".to_string())?;
            ((x << n) | y)
                .checked_add(1)
                .ok_or_else(|| "packed point overflow".into())
        }
    }
}

fn hash_bytes(domain: &[u8], parts: &[&[u8]]) -> blake3::Hash {
    let mut hasher = blake3::Hasher::new();
    hasher.update(domain);
    for part in parts {
        hasher.update(part);
    }
    hasher.finalize()
}

fn seed_from_target(domain: &[u8], target_id: &str) -> u64 {
    let hash = hash_bytes(domain, &[target_id.as_bytes()]);
    let mut bytes = [0u8; 8];
    bytes.copy_from_slice(&hash.as_bytes()[..8]);
    u64::from_le_bytes(bytes)
}

fn target_id(profile: Profile, ordinal: usize, packed: u64) -> String {
    hash_bytes(
        TARGET_ID_DOMAIN,
        &[
            profile.name().as_bytes(),
            &(ordinal as u64).to_le_bytes(),
            &packed.to_le_bytes(),
        ],
    )
    .to_hex()
    .to_string()
}

fn generate_targets(profile: Profile) -> Result<Value, String> {
    let started = Instant::now();
    let curve = KoblitzCurve::new(profile.curve_a(), profile.n())
        .ok_or_else(|| "public curve construction failed".to_string())?;
    let mut targets = Vec::with_capacity(profile.target_count());
    let mut used = HashSet::new();
    let mut counter = 0u64;
    let mut attempts_since_acceptance = 0u64;
    let mut hash_candidates = 0u64;
    let mut decode_rejections = 0u64;
    let mut projection_calls = 0u64;
    let mut infinity_rejections = 0u64;
    let mut duplicate_rejections = 0u64;

    while targets.len() < profile.target_count() && counter < 100_000 {
        attempts_since_acceptance += 1;
        hash_candidates += 1;
        let hash = hash_bytes(
            TARGET_DOMAIN,
            &[
                profile.name().as_bytes(),
                &curve.n.to_le_bytes(),
                &[curve.a],
                &counter.to_le_bytes(),
            ],
        );
        let draw_counter = counter;
        counter += 1;
        let mut x_bytes = [0u8; 8];
        x_bytes.copy_from_slice(&hash.as_bytes()[..8]);
        let x_bits = u64::from_le_bytes(x_bytes) & ((1u64 << curve.n) - 1);
        let sign = hash.as_bytes()[8] & 1 == 1;
        let Some(raw) = decode_uniform_affine_draw(&curve.curve, x_bits, sign) else {
            decode_rejections += 1;
            continue;
        };
        projection_calls += 1;
        let point = curve.mul(&raw, &curve.cofactor);
        if point == BinaryPoint::Infinity {
            infinity_rejections += 1;
            continue;
        }
        let packed = pack_point(&point, curve.n)?;
        if !used.insert(packed) {
            duplicate_rejections += 1;
            continue;
        }
        let ordinal = targets.len();
        let id = target_id(profile, ordinal, packed);
        targets.push(json!({
            "ordinal":ordinal,
            "target_id":id,
            "point":point_json(&point),
            "packed_point":packed,
            "draw_counter":draw_counter,
            "candidate_attempts":attempts_since_acceptance,
            "ic_seed":seed_from_target(IC_SEED_DOMAIN, &id),
            "rho_seed":seed_from_target(RHO_SEED_DOMAIN, &id)
        }));
        attempts_since_acceptance = 0;
    }
    if targets.len() != profile.target_count() {
        return Err("target stream did not fill the frozen panel".into());
    }
    let identity = json!({
        "schema":"koblitz_unknown_scalar_target_panel_identity.v1",
        "profile":profile.name(),
        "n":curve.n,
        "a":curve.a,
        "group_order":curve.group_order.to_string(),
        "subgroup_order":curve.subgroup_order.to_string(),
        "cofactor":curve.cofactor.to_string(),
        "target_domain_hex":hex::encode(TARGET_DOMAIN),
        "ic_seed_domain_hex":hex::encode(IC_SEED_DOMAIN),
        "rho_seed_domain_hex":hex::encode(RHO_SEED_DOMAIN),
        "target_id_domain_hex":hex::encode(TARGET_ID_DOMAIN),
        "targets":targets
    });
    let identity_bytes = serde_json::to_vec(&identity).map_err(|error| error.to_string())?;
    Ok(json!({
        "schema":"koblitz_unknown_scalar_target_panel.v1",
        "status":"complete",
        "evidence_class":if profile == Profile::Production {"public_synthetic_targets"} else {"operational_smoke"},
        "target_scalar_constructed_or_recorded":false,
        "factor_base_log_labels_constructed_or_recorded":false,
        "identity":identity,
        "identity_blake3":blake3::hash(&identity_bytes).to_hex().to_string(),
        "generation":{
            "hash_candidates":hash_candidates,
            "uniform_affine_decode_rejections":decode_rejections,
            "cofactor_projection_calls":projection_calls,
            "projected_infinity_rejections":infinity_rejections,
            "duplicate_rejections":duplicate_rejections,
            "timing_ns":started.elapsed().as_nanos()
        },
        "claim_boundary":"Public synthetic target generation only; no discrete-log label, key material, solver result, or security claim"
    }))
}

fn parse_public_target(
    profile: Profile,
    x: &str,
    y: &str,
) -> Result<(KoblitzCurve, BinaryPoint), String> {
    let curve = KoblitzCurve::new(profile.curve_a(), profile.n())
        .ok_or_else(|| "public curve construction failed".to_string())?;
    let x = x
        .parse::<BigUint>()
        .map_err(|_| "invalid target x".to_string())?;
    let y = y
        .parse::<BigUint>()
        .map_err(|_| "invalid target y".to_string())?;
    if x.bits() > u64::from(curve.n) || y.bits() > u64::from(curve.n) {
        return Err("target coordinate exceeds the field".into());
    }
    let point = BinaryPoint::Affine {
        x: F2mElement::from_biguint(&x, curve.n),
        y: F2mElement::from_biguint(&y, curve.n),
    };
    if !curve.curve.is_on_curve(&point) {
        return Err("target is not on the frozen curve".into());
    }
    if curve.mul(&point, &curve.subgroup_order) != BinaryPoint::Infinity {
        return Err("target is not in the frozen prime-order subgroup".into());
    }
    Ok((curve, point))
}

fn disposition_name(value: KoblitzRelationAttemptDisposition) -> &'static str {
    match value {
        KoblitzRelationAttemptDisposition::RelationFound => "relation_found",
        KoblitzRelationAttemptDisposition::Refuted => "refuted",
        KoblitzRelationAttemptDisposition::Unknown => "unknown",
        KoblitzRelationAttemptDisposition::InvalidModel => "invalid_model",
        KoblitzRelationAttemptDisposition::DirectSkipped => "direct_skipped",
        KoblitzRelationAttemptDisposition::DirectSolved => "direct_solved",
    }
}

fn ic_event_json(event: &KoblitzIcEvent) -> Value {
    match event {
        KoblitzIcEvent::FactorBaseStarted => json!({"event":"factor_base_started"}),
        KoblitzIcEvent::FactorBaseReady { points, orbits } => {
            json!({"event":"factor_base_ready","points":points,"orbits":orbits})
        }
        KoblitzIcEvent::PairTableReady { entries } => {
            json!({"event":"pair_table_ready","entries":entries})
        }
        KoblitzIcEvent::RelationCollectionStarted { wanted } => {
            json!({"event":"relation_collection_started","wanted":wanted})
        }
        KoblitzIcEvent::RelationProgress {
            collected,
            wanted,
            trials,
        } => json!({
            "event":"relation_progress","collected":collected,"wanted":wanted,"trials":trials
        }),
        KoblitzIcEvent::RelationAttemptFinished {
            trial,
            disposition,
            conflicts,
            collected,
        } => json!({
            "event":"relation_attempt_finished","trial":trial,
            "disposition":disposition_name(*disposition),"conflicts":conflicts,"collected":collected
        }),
        KoblitzIcEvent::RelationCollectionFinished { collected, trials } => json!({
            "event":"relation_collection_finished","collected":collected,"trials":trials
        }),
        KoblitzIcEvent::LinearAlgebraStarted { rows, columns } => {
            json!({"event":"linear_algebra_started","rows":rows,"columns":columns})
        }
        KoblitzIcEvent::LinearAlgebraFinished => json!({"event":"linear_algebra_finished"}),
        KoblitzIcEvent::LinearAlgebraIncomplete => json!({"event":"linear_algebra_incomplete"}),
        KoblitzIcEvent::LinearAlgebraSkipped => json!({"event":"linear_algebra_skipped"}),
        KoblitzIcEvent::MatrixRank {
            rows,
            columns,
            rank,
            candidate_produced,
        } => json!({
            "event":"matrix_rank","rows":rows,"columns":columns,"rank":rank,
            "candidate_produced":candidate_produced
        }),
        KoblitzIcEvent::VerificationStarted => json!({"event":"verification_started"}),
        KoblitzIcEvent::VerificationFinished { verified } => {
            json!({"event":"verification_finished","verified":verified})
        }
    }
}

fn rho_event_json(event: &KoblitzSignedRhoEvent) -> Value {
    match event {
        KoblitzSignedRhoEvent::RestartStarted { restart } => {
            json!({"event":"rho_restart_started","restart":restart})
        }
        KoblitzSignedRhoEvent::JumpTableReady { restart, jumps } => {
            json!({"event":"rho_jump_table_ready","restart":restart,"jumps":jumps})
        }
        KoblitzSignedRhoEvent::WalkProgress {
            restart,
            iterations,
        } => json!({
            "event":"rho_walk_progress","restart":restart,"iterations":iterations
        }),
        KoblitzSignedRhoEvent::Collision { restart, verified } => json!({
            "event":"rho_collision","restart":restart,"verified":verified
        }),
        KoblitzSignedRhoEvent::Finished {
            verified,
            exhausted,
        } => json!({
            "event":"rho_finished","verified":verified,"exhausted":exhausted
        }),
    }
}

fn emit_progress(target_id: &str, algorithm: &str, ordinal: usize, event: &Value) {
    eprintln!(
        "{}",
        serde_json::to_string(&json!({
            "schema":"koblitz_unknown_scalar_progress.v1",
            "target_id":target_id,
            "algorithm":algorithm,
            "ordinal":ordinal,
            "event":event
        }))
        .expect("progress JSON")
    );
}

fn record_progress(
    rows: &mut Vec<Value>,
    ordinal: &mut usize,
    target_id: &str,
    algorithm: &str,
    event: Value,
) {
    emit_progress(target_id, algorithm, *ordinal, &event);
    rows.push(event);
    *ordinal += 1;
}

fn attempt_json(record: &KoblitzRelationAttemptRecord) -> Value {
    json!({
        "trial":record.trial,
        "coefficient_a":record.coefficient_a.to_string(),
        "coefficient_b":record.coefficient_b.to_string(),
        "target":point_json(&record.target),
        "disposition":disposition_name(record.disposition),
        "decomposition_indices":record.decomposition_indices,
        "solver_calls":record.solver_calls,
        "models":record.models,
        "conflicts":record.conflicts,
        "implied_rows":record.implied_rows
    })
}

fn relation_json(relation: &KoblitzRelation) -> Value {
    json!({
        "coefficient_a":relation.coef_a.to_string(),
        "coefficient_b":relation.coef_b.to_string(),
        "summands":relation.summands,
        "summand_negated":relation.summand_negated,
        "row":relation.row.iter().map(ToString::to_string).collect::<Vec<_>>()
    })
}

fn factor_base_identity(
    curve: &KoblitzCurve,
    points: &[BinaryPoint],
    ell: u32,
    f_j: u64,
) -> Result<Value, String> {
    let mut keys = points
        .iter()
        .map(|point| pack_point(point, curve.n))
        .collect::<Result<Vec<_>, _>>()?;
    keys.sort_unstable();
    let identity = json!({
        "n":curve.n,"a":curve.a,"m":2,
        "divisor_indices":[0,2],"divisor_polynomial":f_j,"dimension":ell,
        "rational_points":points.len(),"point_order":"ascending packed point key",
        "factor_base_logs_constructed":false,"target_subgroup_enumerated":false
    });
    let mut hasher = blake3::Hasher::new();
    hasher.update(b"koblitz-stage23-factor-base-v1\0");
    hasher.update(&serde_json::to_vec(&identity).map_err(|error| error.to_string())?);
    for key in keys {
        hasher.update(&key.to_le_bytes());
    }
    Ok(json!({"identity":identity,"blake3":hasher.finalize().to_hex().to_string()}))
}

fn run_ic(profile: Profile, target_id: &str, x: &str, y: &str, seed: u64) -> Result<Value, String> {
    let total_started = Instant::now();
    let mut progress_rows = Vec::new();
    let mut progress_ordinal = 0usize;
    record_progress(
        &mut progress_rows,
        &mut progress_ordinal,
        target_id,
        "index_calculus",
        json!({"event":"target_and_subgroup_validation_started"}),
    );
    let curve_started = Instant::now();
    let (curve, target) = parse_public_target(profile, x, y)?;
    let curve_ns = curve_started.elapsed().as_nanos();
    record_progress(
        &mut progress_rows,
        &mut progress_ordinal,
        target_id,
        "index_calculus",
        json!({"event":"target_and_subgroup_validation_finished"}),
    );
    record_progress(
        &mut progress_rows,
        &mut progress_ordinal,
        target_id,
        "index_calculus",
        json!({"event":"factor_base_predicate_and_materialization_started"}),
    );
    let factor_started = Instant::now();
    let factor_base = build_frobenius_factor_base_from_divisor(&curve, profile.divisor_indices())
        .ok_or_else(|| "frozen algebraic factor base failed".to_string())?;
    let factor_ns = factor_started.elapsed().as_nanos();
    record_progress(
        &mut progress_rows,
        &mut progress_ordinal,
        target_id,
        "index_calculus",
        json!({"event":"factor_base_predicate_and_materialization_finished","points":factor_base.points.len(),"orbits":factor_base.unknowns()}),
    );
    if profile == Profile::Production
        && (factor_base.ell != 12
            || factor_base.f_j != 5279
            || factor_base.points.len() != 4281
            || factor_base.unknowns() != 95)
    {
        return Err("production factor-base identity changed".into());
    }
    let factor_identity = factor_base_identity(
        &curve,
        &factor_base.points,
        factor_base.ell,
        factor_base.f_j,
    )?;
    let options = KoblitzIcOptions {
        m: 2,
        descent_m: None,
        collection_window: None,
        factor_index: 0,
        extra_relations: 2,
        max_trials: profile.max_trials(),
        seed,
        strategy: DecompositionStrategy::Sat,
        engine: SolverEngine::default(),
        // Caller-owned precomputation that this panel does not use; the field
        // was added to KoblitzIcOptions without updating this initializer.
        weil_charts: None,
        node_budget: 0,
        max_models: 64,
        sat_macaulay_degree: None,
        sat_options: SatDecompositionOptions {
            encoding: XorEncoding::Native,
            branch_on_summands: true,
            restrict_to_factor_base: true,
            trace_constraint: true,
            conflict_budget: profile.conflict_budget(),
            symmetry_breaking: false,
        },
        collapse_negation: true,
        stop_on_verified_rank: true,
        relation_batch_size: 1,
        allow_direct_relation: false,
        collapse_projected_orbits: true,
        crossbred: None,
        wdsat_binary: None,
        wdsat_timeout_ms: 5_000,
        linear_algebra: LinearAlgebra::Dense,
    };
    let solve_started = Instant::now();
    let report = koblitz_index_calculus_dlp_with_factor_base_and_progress(
        &curve,
        &target,
        &factor_base,
        &options,
        &mut |event| {
            let row = ic_event_json(&event);
            record_progress(
                &mut progress_rows,
                &mut progress_ordinal,
                target_id,
                "index_calculus",
                row,
            );
        },
    )
    .ok_or_else(|| "index-calculus API returned no report".to_string())?;
    let solve_ns = solve_started.elapsed().as_nanos();
    let verified = report
        .log
        .as_ref()
        .is_some_and(|value| curve.mul(curve.generator(), value) == target);
    let attempts = report
        .attempt_records
        .iter()
        .map(attempt_json)
        .collect::<Vec<_>>();
    let matrix = report
        .relation_matrix
        .iter()
        .map(relation_json)
        .collect::<Vec<_>>();
    let attempts_blake3 =
        blake3::hash(&serde_json::to_vec(&attempts).map_err(|error| error.to_string())?)
            .to_hex()
            .to_string();
    let matrix_blake3 =
        blake3::hash(&serde_json::to_vec(&matrix).map_err(|error| error.to_string())?)
            .to_hex()
            .to_string();
    let progress_blake3 =
        blake3::hash(&serde_json::to_vec(&progress_rows).map_err(|error| error.to_string())?)
            .to_hex()
            .to_string();
    let mut outcomes = json!({"relation_found":0,"refuted":0,"unknown":0,"invalid_model":0,"direct_skipped":0,"direct_solved":0});
    for record in &report.attempt_records {
        let key = disposition_name(record.disposition);
        outcomes[key] = json!(outcomes[key].as_u64().unwrap_or(0) + 1);
    }
    Ok(json!({
        "schema":"koblitz_unknown_scalar_ic_result.v1",
        "status":if verified {"complete_verified"} else {"incomplete"},
        "evidence_class":if profile == Profile::Production {"public_synthetic_unknown_scalar_candidate"} else {"operational_smoke"},
        "profile":profile.name(),"target_id":target_id,"target":point_json(&target),"seed":seed,
        "target_scalar_constructed_or_supplied":false,
        "factor_base":factor_identity,
        "factor_base_logs_constructed_or_supplied":false,
        "options":{"m":2,"conflict_budget_per_target":profile.conflict_budget(),"max_trials":profile.max_trials(),"max_models":64,"relation_batch_size":1,"parallel_workers":1,"direct_relation_forbidden":true,"collapse_projected_orbits":true},
        "report":{
            "factor_base_size":report.factor_base_size,"orbit_count":report.orbit_count,"ell":report.ell,
            "relations":report.relations,"trials":report.trials,"outcomes":outcomes,
            "sat_calls":report.sat_calls,"sat_refutations":report.sat_refutations,
            "sat_unknowns":report.sat_unknowns,"sat_invalid_models":report.sat_invalid_models,
            "sat_models":report.sat_models,"sat_conflicts":report.sat_conflicts,
            "direct_relation":report.direct_relation,"direct_relations_skipped":report.direct_relations_skipped,
            "linear_solve_attempts":report.linear_solve_attempts,"rank_checks":report.rank_checks,
            "matrix_rows":report.matrix_rows,"matrix_columns":report.matrix_columns,
            "terminal_matrix_rank":report.terminal_matrix_rank,
            "rank_history":report.rank_history.iter().map(|rank| json!({"rows":rank.rows,"columns":rank.columns,"rank":rank.rank,"candidate_produced":rank.candidate_produced,"candidate_verified":rank.candidate_verified})).collect::<Vec<_>>(),
            "recovered_scalar":report.log.as_ref().map(ToString::to_string),
            "recovered_scalar_point_verified":verified
        },
        "attempt_records":attempts,"attempt_records_blake3":attempts_blake3,
        "relation_matrix":matrix,"relation_matrix_blake3":matrix_blake3,
        "progress":progress_rows,"progress_blake3":progress_blake3,
        "timing_ns":{"curve_target_and_subgroup_validation":curve_ns,"factor_base_predicate_and_materialization":factor_ns,"projected_orbit_construction":report.projected_orbit_construction_ns,"cofactor_admission":report.cofactor_admission_ns,"relation_collection":report.relation_collection_ns,"linear_algebra":report.linear_algebra_ns,"driver_solve":solve_ns,"end_to_end":total_started.elapsed().as_nanos()},
        "resource_accounting_boundary":{"single_core_elapsed_seconds":Value::Null,"total_core_seconds":Value::Null,"peak_rss_bytes":Value::Null,"external_process_receipt_required":true},
        "claim_boundary":"One public synthetic arbitrary-target IC attempt; incomplete remains inconclusive and success requires [d]G=Q"
    }))
}

fn run_rho(
    profile: Profile,
    target_id: &str,
    x: &str,
    y: &str,
    seed: u64,
) -> Result<Value, String> {
    let total_started = Instant::now();
    let mut progress_rows = Vec::new();
    let mut progress_ordinal = 0usize;
    record_progress(
        &mut progress_rows,
        &mut progress_ordinal,
        target_id,
        "signed_frobenius_rho",
        json!({"event":"target_and_subgroup_validation_started"}),
    );
    let validation_started = Instant::now();
    let (curve, target) = parse_public_target(profile, x, y)?;
    let target_validation_ns = validation_started.elapsed().as_nanos();
    record_progress(
        &mut progress_rows,
        &mut progress_ordinal,
        target_id,
        "signed_frobenius_rho",
        json!({"event":"target_and_subgroup_validation_finished"}),
    );
    let options = KoblitzSignedRhoOptions {
        seed,
        jump_count: 16,
        max_restarts: profile.rho_max_restarts(),
        max_iterations_per_restart: profile.rho_max_iterations(),
        progress_interval: 256,
        ..KoblitzSignedRhoOptions::default()
    };
    let report =
        koblitz_signed_frobenius_rho_with_progress(&curve, &target, &options, &mut |event| {
            let row = rho_event_json(&event);
            record_progress(
                &mut progress_rows,
                &mut progress_ordinal,
                target_id,
                "signed_frobenius_rho",
                row,
            );
        });
    let progress_blake3 =
        blake3::hash(&serde_json::to_vec(&progress_rows).map_err(|error| error.to_string())?)
            .to_hex()
            .to_string();
    Ok(json!({
        "schema":"koblitz_unknown_scalar_rho_result.v1",
        "status":if report.verified {"complete_verified"} else {"incomplete"},
        "evidence_class":if profile == Profile::Production {"public_synthetic_same_target_rho_candidate"} else {"operational_smoke"},
        "profile":profile.name(),"target_id":target_id,"target":point_json(&target),"seed":seed,
        "target_scalar_constructed_or_supplied":false,
        "algorithm":"signed-Frobenius/negation quotient rho with a fresh deterministic jump table per restart",
        "options":{"jump_count":options.jump_count,"max_restarts":options.max_restarts,"max_iterations_per_restart":options.max_iterations_per_restart,"parallel_workers":1},
        "report":{"recovered_scalar":report.recovered_log.as_ref().map(ToString::to_string),"recovered_scalar_point_verified":report.verified,"exhausted":report.exhausted,"iterations":report.iterations,"restarts_attempted":report.restarts_attempted,"jump_table_rebuilds":report.jump_table_rebuilds,"parallel_walks":report.parallel_walks},
        "charges":{"coefficient_draws":report.charges.coefficient_draws,"setup_scalar_multiplications":report.charges.setup_scalar_multiplications,"setup_group_additions":report.charges.setup_group_additions,"walk_group_additions":report.charges.walk_group_additions,"candidate_verification_scalar_multiplications":report.charges.candidate_verification_scalar_multiplications,"canonicalizations":report.charges.canonicalizations,"frobenius_maps":report.charges.frobenius_maps,"negations_examined":report.charges.negations_examined,"partition_hashes":report.charges.partition_hashes,"collisions":report.charges.collisions,"failed_collisions":report.charges.failed_collisions,"fruitless_cycles":report.charges.fruitless_cycles,"cycle_escape_doublings":report.charges.cycle_escape_doublings},
        "progress":progress_rows,"progress_blake3":progress_blake3,
        "timing_ns":{"target_and_subgroup_validation":target_validation_ns,"rho_setup":report.setup_ns,"rho_walk":report.walk_ns,"candidate_verification":report.verification_ns,"end_to_end":total_started.elapsed().as_nanos()},
        "resource_accounting_boundary":{"single_core_elapsed_seconds":Value::Null,"total_core_seconds":Value::Null,"peak_rss_bytes":Value::Null,"external_process_receipt_required":true},
        "claim_boundary":"Same public synthetic target rho control; incomplete remains inconclusive and no crossover or SOTA claim follows"
    }))
}

fn real_main() -> Result<(), String> {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let output = match args.as_slice() {
        [mode, profile] if mode == "targets" => generate_targets(Profile::parse(profile)?),
        [mode, profile, target_id, x, y, seed] if mode == "ic" => run_ic(
            Profile::parse(profile)?,
            target_id,
            x,
            y,
            seed.parse().map_err(|_| "invalid IC seed".to_string())?,
        ),
        [mode, profile, target_id, x, y, seed] if mode == "rho" => run_rho(
            Profile::parse(profile)?,
            target_id,
            x,
            y,
            seed.parse().map_err(|_| "invalid rho seed".to_string())?,
        ),
        _ => Err("usage: koblitz_unknown_scalar_panel targets <production|smoke> | <ic|rho> <production|smoke> TARGET_ID X Y SEED".into()),
    }?;
    println!(
        "{}",
        serde_json::to_string_pretty(&output).map_err(|error| error.to_string())?
    );
    Ok(())
}

fn main() {
    if let Err(error) = real_main() {
        eprintln!("koblitz_unknown_scalar_panel: {error}");
        std::process::exit(2);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn smoke_targets_are_deterministic_and_have_no_scalar() {
        let first = generate_targets(Profile::Smoke).unwrap();
        let second = generate_targets(Profile::Smoke).unwrap();
        assert_eq!(first["identity_blake3"], second["identity_blake3"]);
        assert_eq!(first["identity"]["targets"].as_array().unwrap().len(), 2);
        assert_eq!(first["target_scalar_constructed_or_recorded"], false);
        assert!(!serde_json::to_string(&first)
            .unwrap()
            .contains("\"secret\""));
    }

    #[test]
    fn arbitrary_target_ic_and_rho_smoke_verify() {
        let panel = generate_targets(Profile::Smoke).unwrap();
        let target = &panel["identity"]["targets"][0];
        let id = target["target_id"].as_str().unwrap();
        let x = target["point"]["x"].as_str().unwrap();
        let y = target["point"]["y"].as_str().unwrap();
        let ic = run_ic(
            Profile::Smoke,
            id,
            x,
            y,
            target["ic_seed"].as_u64().unwrap(),
        )
        .unwrap();
        let rho = run_rho(
            Profile::Smoke,
            id,
            x,
            y,
            target["rho_seed"].as_u64().unwrap(),
        )
        .unwrap();
        assert_eq!(ic["target_scalar_constructed_or_supplied"], false);
        assert_eq!(rho["target_scalar_constructed_or_supplied"], false);
        assert_eq!(ic["status"], "complete_verified");
        assert_eq!(rho["status"], "complete_verified");
        assert_eq!(
            ic["report"]["recovered_scalar"],
            rho["report"]["recovered_scalar"]
        );
        assert_eq!(
            ic["report"]["trials"],
            ic["attempt_records"].as_array().unwrap().len()
        );
        assert_eq!(
            ic["report"]["relations"],
            ic["relation_matrix"].as_array().unwrap().len()
        );
    }
}
