#!/usr/bin/env python3
"""Name the exact Q1083 quotient-table candidate and one-target workload."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
HIT = HERE / "runs/n83_zero_run_q1083_M32_R29_ci_36817149475_qstart27380416512"
CANDIDATES = HERE / "candidates"


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(frozen(value)).hexdigest()


def main():
    hit = json.loads((HIT / "full.json").read_text())
    screen = json.loads((HERE / "n83_full_spill_screen.json").read_text())
    identity = hit["curve_identity_record"]
    assert identity == screen["curve_identity_record"]
    assert hit["isogeny"] == "none"
    base = hit["factor_base"]
    assert base["actual_usable_points_B_before_folding"] == 8000204
    assert base["signed_frobenius_columns"] == 48194
    assert hit["verified_public_target_quotient_table_dlp"]
    curve_id = hit["curve_id"]
    assert curve_id == "EC1N83Ckb1h" + digest(identity)[:12]
    curve = dict(identity["curve"], curve_id=curve_id)
    candidate = {
        "schema_version": 1,
        "field": identity["field"],
        "curve": curve,
        "isogeny": "none",
        "endomorphism": {
            "endomorphism_order_conductor": None,
            "frobenius_order_conductor": None,
            "volcano_levels": "not_applicable_for_degree_two_in_characteristic_two",
        },
        "factor_base": {
            "construction": base["construction"],
            "seed_scalar_rng": base["seed_scalar_rng"],
            "seed": base["seed"],
            "selected_point_orbits": base["selected_point_orbits"],
            "signed_frobenius_orbit_size": base["signed_frobenius_orbit_size"],
            "actual_usable_points_B_before_folding": base[
                "actual_usable_points_B_before_folding"],
            "signed_frobenius_columns": base["signed_frobenius_columns"],
            "initially_known_log_columns": base["initially_known_log_columns"],
            "unknown_log_columns": base["unknown_log_columns"],
            "frobenius_eigenvalue_mod_r": base["frobenius_eigenvalue_mod_r"],
            "enumerated_set_encoding": base["enumerated_set_encoding"],
            "enumerated_set_sha256": base["enumerated_set_sha256"],
            "canonical_log_encoding": base["canonical_log_encoding"],
            "canonical_log_sha256": base["canonical_log_sha256"],
            "key_and_log_record_bytes": base["key_and_log_record_bytes"],
            "key_and_log_file_bytes": base["key_and_log_file_bytes"],
            "key_and_log_file_sha256": base["key_and_log_file_sha256"],
        },
        "point_decomposition": {
            "m": 4,
            "summation_chain": "group-law pair table and target complement modulo signed Frobenius",
            "solver_family": "quotient_pair_table",
            "stage_code": "PDP4qtable",
            "table_descriptors_per_job": hit["table_descriptors"],
            "query_representatives_per_job": hit["query_representatives"],
            "query_pair_lifts": 83,
            "table_schedule": hit["table_schedule"],
            "query_representative_schedule": hit[
                "query_representative_schedule"],
            "canonicalization": "signed Frobenius, exact longest zero run",
            "filter": {"bits_per_key": hit["bits_per_key"],
                       "hashes": hit["hashes"]},
            "candidate_spill_enabled": hit["candidate_spill_enabled"],
            "exact_replay": True,
            "representative_batch": hit["representative_batch"],
            "implementation_sha256": hit["native_source_sha256"],
        },
        "relation_collection": {
            "policy": "none; factor-base logs known by construction",
            "stage_code": "RCdirect",
            "implementation_sha256": hit["wrapper_source_sha256"],
        },
        "relation_linear_algebra": "none",
        "target_descent": {
            "policy": "match one ordinary four-point relation and sum known factor-base logs",
            "stage_code": "TDdirect",
            "implementation_sha256": hit["wrapper_source_sha256"],
        },
        "implementation": {
            "native_source_sha256": hit["native_source_sha256"],
            "native_pairs_sha256": hit["native_pairs_sha256"],
            "bloom_core_sha256": hit["bloom_core_sha256"],
            "generated_field_sha256": hit["generated_field_sha256"],
            "wrapper_source_sha256": hit["wrapper_source_sha256"],
            "zero_run_source_generator_sha256": hit[
                "zero_run_source_generator_sha256"],
            "fast_keyer_enabled": hit["fast_keyer_enabled"],
            "keyer_variant": hit["keyer_variant"],
            "cpu_backend": hit["cpu_backend"],
        },
    }
    candidate_hash = digest(candidate)
    candidate_id = ("IC1N83Ckb1fb8000204PDP4qtableRCdirectLAnoneTDdirect"
                    "ISO0h" + candidate_hash[:12])
    candidate["candidate_id"] = candidate_id
    candidate["candidate_record_sha256"] = candidate_hash
    assert digest({k: v for k, v in candidate.items() if k not in (
        "candidate_id", "candidate_record_sha256")}) == candidate_hash
    CANDIDATES.mkdir(exist_ok=True)
    candidate_path = CANDIDATES / (candidate_id + ".json")
    candidate_path.write_text(json.dumps(candidate, indent=2) + "\n")

    workload = {
        "schema_version": 1,
        "curve_id": curve_id,
        "subgroup_order": curve["subgroup_order"],
        "generator": curve["generator"],
        "targets": [hit["public_target"]],
        "input_law": "one fixed public subgroup point; no planted decomposition",
        "target_count": 1,
        "cache_state": "reusable known-log factor base and table schedule fixed before target query",
        "query_range_starts": json.loads((HERE /
            "n83_q1083_m32_wave_plan.json").read_text())["query_starts"],
    }
    workload_id = digest(workload)[:12]
    named = {
        "kind": "n83_q1083_verified_one_target_candidate_link",
        "candidate_id": candidate_id,
        "candidate_record_sha256": candidate_hash,
        "workload_id": workload_id,
        "run_id": f"{candidate_id}W{workload_id}R1",
        "workload": workload,
        "curve_id": curve_id,
        "isogeny": "none",
        "proposal_id": None,
        "raw_proposal_id": "Q1083",
        "factor_base_enumerated_set_sha256": base[
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": base[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": base["signed_frobenius_columns"],
        "raw_hit_receipt_sha256": hashlib.sha256((HIT /
            "full.json").read_bytes()).hexdigest(),
        "independent_sage_audit_sha256": hashlib.sha256((HIT /
            "sage_verify.json").read_bytes()).hexdigest(),
        "verified_recovered_scalar": hit[
            "verified_public_target_relations"][0]["recovered_scalar"],
        "verified_natural_relation_count": 1,
        "complete_calibrated_solve_operations": None,
        "online_speedup_vs_paired_rho": None,
        "historical_target_specific_attempts_charged_separately": True,
        "note": "Exact method identity and workload link; raw Q1083 receipts are immutable. This is not a fully priced IC/rho comparison.",
    }
    output = HERE / "n83_verified_solve_named_run.json"
    output.write_text(json.dumps(named, indent=2) + "\n")
    print(json.dumps({"candidate_id": candidate_id,
                      "workload_id": workload_id, "run_id": named["run_id"]},
                     indent=2))


if __name__ == "__main__":
    main()
