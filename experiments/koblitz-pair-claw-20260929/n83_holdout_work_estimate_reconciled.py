#!/usr/bin/env python3
"""Bind the frozen search shape to the superseding resource ceiling."""

import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEARCH = HERE / "n83_q1093_combined_search_work_screen.json"
CAPACITY = HERE / "n83_holdout_extended_resource_ceiling.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    search = json.loads(SEARCH.read_text())
    cap = json.loads(CAPACITY.read_text())
    for key in ("curve_id", "workload_id", "isogeny",
                "factor_base_enumerated_set_sha256",
                "actual_usable_points_B_before_folding",
                "signed_frobenius_columns"):
        assert search[key] == cap[key], key
    assert search["ci_candidate_id"] == cap["candidate_ids"][0]
    assert search["local_candidate_id"] == cap["candidate_ids"][1]
    assert search["ci_run_id"] == cap["run_ids"][0]
    assert search["local_run_id"] == cap["run_ids"][1]
    assert search["measured_natural_relations_on_fresh_target"] is None
    assert search["verified_fresh_target_scalar"] is None
    assert cap["verified_fresh_target_discrete_logarithm"] is None
    scenarios = {}
    for jobs, model_key in (
        ("80", "all_80_ci_jobs_controls_and_two_local_regular_path_model"),
        ("208", "all_208_conditional_ci_jobs_controls_and_two_local_regular_path_model"),
    ):
        row = cap["scenarios"][jobs]
        assert row["scheduled_ci_jobs"] == int(jobs)
        assert math.isclose(math.log2(int(search[model_key])),
                            search[model_key + "_log2"], rel_tol=0,
                            abs_tol=1e-12)
        assert math.isclose(math.log2(int(row[
            "total_conditional_cycle_capacity"])), row[
                "total_conditional_cycle_capacity_log2"], rel_tol=0,
                            abs_tol=1e-12)
        scenarios[jobs] = {
            "scheduled_ci_jobs": int(jobs),
            "regular_path_field_api_call_model": search[model_key],
            "regular_path_field_api_call_model_log2": search[model_key + "_log2"],
            "conditional_cpu_core_cycle_capacity": row[
                "total_conditional_cycle_capacity"],
            "conditional_cpu_core_cycle_capacity_log2": row[
                "total_conditional_cycle_capacity_log2"],
            "natural_relation_count": None,
            "verified_scalar": None,
            "measured_complete_solve_operations_log2": None,
        }
    return {
        "kind": "n83_holdout_two_candidate_one_target_reconciled_work_estimate",
        "status": "model_and_conditional_capacity_no_fresh_solve",
        "curve_id": cap["curve_id"],
        "field_degree_n": cap["field_degree_n"],
        "isogeny": "none",
        "factor_base_enumerated_set_sha256": cap[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": cap[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": cap["signed_frobenius_columns"],
        "workload_id": cap["workload_id"],
        "candidate_ids": cap["candidate_ids"],
        "run_ids": cap["run_ids"],
        "local_disjoint_query_intervals": search[
            "local_disjoint_query_intervals"],
        "scenarios": scenarios,
        "search_screen_sha256": sha(SEARCH),
        "extended_capacity_sha256": sha(CAPACITY),
        "source_sha256": sha(Path(__file__)),
        "interpretation": [
            "Field API calls are full-shape regular-path models, not measured complete-solve operations or bounds on Bloom, memory, failed, and canceled work.",
            "CPU core cycles are conditional resource-capacity estimates under the extended reserve and CI job assumptions, not measured cycles or calibrated field operations.",
            "The 208-job scenario is dormant until Q1091 independently audits all 64 shards as terminal zero-hit.",
            "A successful solve requires a natural relation, fresh scalar, independent replay, and complete attempt ledger; all are pending for this workload.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), "refusing to overwrite work estimate"
    report = build()
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({jobs: {
        "field_model_log2": row["regular_path_field_api_call_model_log2"],
        "cycle_capacity_log2": row["conditional_cpu_core_cycle_capacity_log2"],
    } for jobs, row in report["scenarios"].items()}))


if __name__ == "__main__":
    main()
