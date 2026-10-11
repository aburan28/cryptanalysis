#!/usr/bin/env python3
"""Name the complete Q1457+Q1461 IC candidate and charge its measured stages."""
from __future__ import annotations
import hashlib
import json
import math
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1419 = PARENT / "q1419_partial_pin/runs/n53_full_lock/receipt.json"
PAIR = PARENT / "q20261011_n53_native_pair"
SETUP = PARENT / "q20261011_n53_full_pipeline"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def main() -> None:
    assert not (HERE / "candidate_manifest.json").exists()
    assert not (HERE / "pipeline_receipt.json").exists()
    q1419 = json.loads(Q1419.read_text())
    stage = q1419["stage_config_hash_input"]
    field = stage["field"]
    curve = stage["curve"]
    stripped = dict(curve)
    stripped.pop("curve_id")
    curve_hash = hashlib.sha256(canonical({"field": field, "curve": stripped})).hexdigest()
    assert curve["curve_id"] == "EC1N53Ckb1h" + curve_hash[:12]
    protocol = json.loads((HERE / "protocol.json").read_text())
    public = json.loads((HERE / "public_target.json").read_text())
    fixture = json.loads((HERE / "target_fixture.json").read_text())
    exported = json.loads((PAIR / "export_receipt.json").read_text())
    setup_measure = json.loads((SETUP / "native_measurement.json").read_text())
    setup_replay = json.loads((SETUP / "independent_replay.json").read_text())
    target_measure = json.loads((HERE / "native_measurement.json").read_text())
    recovery = json.loads((HERE / "recovery.json").read_text())
    assert setup_replay["matrix_rank"] == 227
    assert setup_replay["factor_base_log_status"] == "solved_and_replayed"
    assert target_measure["status"] == "first_match"
    assert recovery["status"] == "SCALAR_RECOVERED_AND_REPLAYED"
    assert recovery["scalar"] == fixture["scalar"]
    assert public["workload_id"] == fixture["workload_id"]
    assert curve["curve_id"] == protocol["curve_id"]
    assert stage["factor_base"]["enumerated_set_sha256"] == protocol["factor_base_enumerated_set_sha256"]
    source = {
        "base_export": sha(PAIR / "export.py"),
        "base_export_indexcalc": sha(PAIR / "indexcalc.py"),
        "base_enumerator": sha(PARENT / "enumerate_weight_base.py"),
        "base_chain": sha(PARENT / "chain_s3.py"),
        "base_probe": sha(HERE.parents[2] / "experiments/koblitz-pair-claw-20260929/probe_n53_relation.py"),
        "base_run_probe": sha(PARENT / "run_probe.py"),
        "native_field53": sha(PAIR / "native_field53.hpp"),
        "python_curve": sha(HERE.parents[2] / "ecc2k130/codegen/curves.py"),
        "python_field": sha(HERE.parents[2] / "ecc2k130/codegen/field.py"),
        "orbit_key": sha(HERE.parents[2] / "experiments/koblitz-pair-claw-20260929/orbit_key.py"),
        "setup_prepare": sha(SETUP / "prepare.py"),
        "setup_native": sha(SETUP / "native_sweep.cpp"),
        "setup_replay_and_LA": sha(SETUP / "verify.py"),
        "target_native": sha(HERE / "native_first.cpp"),
        "target_recovery": sha(HERE / "recover.py")}
    candidate_record = {
        "field": field, "curve": curve, "isogeny": "none",
        "endomorphism": {"order_conductor": None,
                         "frobenius_order_conductor": None,
                         "volcano_levels": None,
                         "status": "not_used"},
        "factor_base": {**stage["factor_base"],
                        "base_export_source_sha256": source["base_export"]},
        "point_decomposition": {
            "m": 4, "solver_family": "mitm", "stage_code": "PDP4mitm",
            "summation_policy": "two base-pair sums matched by signed Frobenius quotient group key",
            "table_policy": "complete 2743068-state index; all descriptors retained",
            "table_states": 2743068,
            "query_policy": "uniform with replacement over actual base-point pairs",
            "encoding": "native ONB group arithmetic, no Weil-descent polynomial",
            "equation_order": "none", "monomial_order": "none",
            "internal_matrix_kernel": "none", "cache_policy": "target-independent pair table",
            "setup_native_source_sha256": source["setup_native"],
            "target_native_source_sha256": source["target_native"],
            "native_field_source_sha256": source["native_field53"]},
        "relation_collection": {
            "stage_code": "RCenum", "setup_target": "generator G with known log one",
            "sample_rule": "uniform with replacement over actual base-point pairs",
            "verification": "four-point group sum and exact base membership",
            "duplicate_handling": "retain all occurrences; rank distinct equations",
            "stop_criterion": "accept factor-base logs only at full 227-column rank; query cap is run data",
            "source_sha256": source["setup_replay_and_LA"]},
        "relation_linear_algebra": {
            "stage_code": "LAgauss", "modulus": protocol["subgroup_order"],
            "columns": 227, "row_construction": "signed Frobenius eigenvalue coefficients",
            "rank_criterion": "227 independent columns",
            "solver": "modular dense Gaussian elimination",
            "solution_check": "replay all 227 representative logs against G",
            "source_sha256": source["setup_replay_and_LA"]},
        "target_descent": {
            "stage_code": "TDdirect", "policy": "stop after first matched target query",
            "recovery": "sum four signed Frobenius factor-base logs modulo subgroup order",
            "verification": "independent scalar multiplication equals public target",
            "source_sha256": source["target_recovery"]},
        "implementation": {"source_sha256": source,
                           "compiler_flags": ["-O3", "-std=c++17"],
                           "algorithm_affecting_flags": "none"}}
    hash_full = hashlib.sha256(canonical(candidate_record)).hexdigest()
    candidate_id = ("IC1N53Ckb1fb24062PDP4mitmRCenumLAgaussTDdirectISO0h" +
                    hash_full[:12])
    run_id = candidate_id + "W" + public["workload_id"] + "R1"
    manifest = {"candidate_id": candidate_id,
                "canonical_candidate_sha256": hash_full,
                "canonical_candidate_record": candidate_record,
                "curve_id_verified_sha256": curve_hash,
                "curve_trace_derived": (1 << 53) + 1 - curve["order"]}
    (HERE / "candidate_manifest.json").write_text(json.dumps(manifest, indent=2,
                                                             sort_keys=True) + "\n")
    setup_phases = setup_measure["phase_wall_ns"]
    target_phases = target_measure["native"]["phase_wall_ns"]
    target_relation = recovery["target_relation_and_recovery_ns"]
    target_replay = recovery["target_scalar_replay_ns"]
    online_sum = target_phases["target_query_and_lookup"] + target_relation + target_replay
    assert online_sum == recovery["target_online_phase_sum_ns"]
    fixture_check_started = time.perf_counter_ns()
    assert recovery["scalar"] == fixture["scalar"]
    fixture_check_ns = time.perf_counter_ns() - fixture_check_started
    counted_pair_add_attempts = (setup_measure["charged_pair_add_attempts"] +
                                 target_measure["charged_pair_add_attempts"])
    receipt = {
        "candidate_id": candidate_id, "workload_id": public["workload_id"],
        "run_id": run_id, "curve_id": curve["curve_id"], "isogeny": "none",
        "factor_base_actual_B": 24062, "factor_base_folded_columns_K": 227,
        "factor_base_enumerated_set_sha256": protocol["factor_base_enumerated_set_sha256"],
        "target_count": 1, "target_onb_xy": public["target_onb_xy"],
        "recovered_scalar": recovery["scalar"],
        "scalar_replayed": True, "fixture_scalar_match": True,
        "fixture_check_ns_outside_online": fixture_check_ns,
        "setup_query_count": setup_measure["query_samples_processed"],
        "setup_verified_relation_occurrences": setup_replay["verified_relation_occurrences"],
        "setup_distinct_quotient_rows": setup_replay["distinct_quotient_rows"],
        "setup_final_rank": setup_replay["matrix_rank"],
        "setup_replayed_log_columns": setup_replay["replayed_log_columns"],
        "target_query_count": target_measure["native"]["query_samples_processed"],
        "target_verified_relation_count": len(recovery["verified_first_match_relations"]),
        "target_independent_phases_ns_exploratory": {
            "base_export_setup": exported["base_setup_ns"],
            "setup_input_load": setup_phases["input_load"],
            "setup_table_allocation": setup_phases["table_allocation"],
            "setup_table_build": setup_phases["table_build"],
            "setup_generator_queries": setup_phases["target_query_and_lookup"],
            "setup_base_rebuild": setup_replay["base_rebuild_ns"],
            "setup_relation_replay_and_matrix_build": setup_replay["relation_replay_and_matrix_build_ns"],
            "setup_checkpoint_rank_diagnostic": setup_replay["checkpoint_rank_ns"],
            "setup_final_relation_LA": setup_replay["final_relation_LA_ns"],
            "setup_log_replay": setup_replay["factor_base_log_replay_ns"],
            "target_process_input_load": target_phases["input_load"],
            "target_process_table_allocation": target_phases["table_allocation"],
            "target_process_table_build": target_phases["table_build"],
            "target_recovery_base_rebuild": recovery["base_rebuild_ns_target_independent"]},
        "target_dependent_exclusive_phases_ns_exploratory": {
            "T_target_query_plus_PDP": target_phases["target_query_and_lookup"],
            "T_target_relation_check_plus_descent": target_relation,
            "T_target_recovery_check": target_replay},
        "unseparated_subphases_ns": {
            "T_target_query": None, "T_target_PDP": None,
            "T_target_relation_check": None, "T_target_descent": None},
        "target_online_phase_sum_ns_exploratory": online_sum,
        "contiguous_one_target_online_wall_ns": None,
        "online_interval_note": "native target-query and Python relation/recovery phases were timed separately after reusable preparation; their sum is not a contiguous stopwatch interval",
        "counted_pair_add_attempts_setup": setup_measure["charged_pair_add_attempts"],
        "counted_pair_add_attempts_target_process": target_measure["charged_pair_add_attempts"],
        "counted_pair_add_attempts_combined": counted_pair_add_attempts,
        "counted_pair_add_attempts_log2": math.log2(counted_pair_add_attempts),
        "counted_pair_addition_boundary": "two native complete-table builds plus setup and target query group-add attempts; excludes factor-base construction, modular LA, scalar replay and input generation",
        "complete_solve_work_log2": None,
        "rho_online_ms": None, "online_speedup": None,
        "resource_conditions": {"host_isolation": "none; exploratory timings",
                                "setup_peak_rss_bytes": setup_measure["peak_rss_bytes"],
                                "target_peak_rss_bytes": target_measure["native"]["peak_rss_bytes"]},
        "candidate_manifest_sha256": sha(HERE / "candidate_manifest.json"),
        "q1457_measurement_sha256": sha(SETUP / "native_measurement.json"),
        "q1457_replay_sha256": sha(SETUP / "independent_replay.json"),
        "q1461_measurement_sha256": sha(HERE / "native_measurement.json"),
        "q1461_recovery_sha256": sha(HERE / "recovery.json"),
        "workload_record": fixture["workload_record"],
        "workload_hash_full": fixture["workload_hash_full"]}
    (HERE / "pipeline_receipt.json").write_text(json.dumps(receipt, indent=2,
                                                           sort_keys=True) + "\n")
    print(candidate_id, run_id, online_sum / 1e9, counted_pair_add_attempts)


if __name__ == "__main__":
    main()
