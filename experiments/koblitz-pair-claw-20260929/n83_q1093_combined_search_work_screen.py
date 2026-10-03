#!/usr/bin/env python3
"""Combine the frozen CI and two local n83 search shapes without a solve claim."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "n83_holdout_target_20261001.json"
PRIOR = HERE / "n83_q1090_terminal_wave_audit.json"
CI_PLAN = HERE / "n83_q1091_holdout_m32_continuation_plan.json"
CI_BUDGET = HERE / "n83_q1091_resource_budget.json"
Q1092 = HERE / "n83_q1092_conditional_same_candidate_fallback.json"
LOCAL_FIRST = HERE / "n83_q1093_local_arm_m32_r30_plan.json"
LOCAL_SECOND = HERE / "n83_q1093_second_local_arm_m32_r30_plan.json"
RESERVE = HERE / "n83_holdout_revised_30day_resource_ceiling.json"
OUTPUT = HERE / "n83_q1093_combined_search_work_screen.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def screen():
    target = load(TARGET)
    prior = load(PRIOR)
    ci_plan = load(CI_PLAN)
    budget = load(CI_BUDGET)
    q1092 = load(Q1092)
    first = load(LOCAL_FIRST)
    second = load(LOCAL_SECOND)
    reserve = load(RESERVE)
    assert target["fixture_scalar_retained"] is False
    assert target["workload"]["target_count"] == 1
    assert prior["completed_jobs"] == 16
    assert prior["independently_verified_natural_relations"] == 0
    assert prior["query_end_exclusive"] == ci_plan[
        "prior_completed_query_end_exclusive"]
    assert ci_plan["query_starts"] == [
        (16 + i) * (1 << 29) for i in range(64)]
    assert ci_plan["query_end_exclusive"] == 80 * (1 << 29)
    assert q1092["query_end_exclusive"] == 208 * (1 << 29)
    assert first["query_starts"] == [q1092["query_end_exclusive"]]
    assert second["query_starts"] == [first["query_end_exclusive"]]
    assert first["query_representatives"] == second[
        "query_representatives"] == 1 << 30
    assert second["query_end_exclusive"] == 212 * (1 << 29)
    assert first["table_start"] == second["table_start"] == 0
    assert first["table_descriptors"] == second["table_descriptors"] == 1 << 32
    assert first["candidate_id"] == second["candidate_id"]
    assert first["run_id"] == second["run_id"]
    assert first["candidate_id"] != ci_plan["candidate_id"]
    assert first["candidate_manifest_sha256"] == second[
        "candidate_manifest_sha256"] == sha(HERE / first["candidate_manifest"])
    assert second["prior_Q1093_local_plan_sha256"] == sha(LOCAL_FIRST)
    assert budget["continuation_plan_sha256"] == sha(CI_PLAN)
    assert budget["prior_audit_sha256"] == sha(PRIOR)
    assert reserve["prior_budget_sha256"] == sha(CI_BUDGET)
    assert reserve["Q1092_design_sha256"] == sha(Q1092)
    for row in (prior, ci_plan, budget, q1092, first, second, reserve):
        assert row["curve_id"] == target["curve_id"]
        assert row["workload_id"] == target["workload_id"]
        assert row["isogeny"] == "none"
        assert row["actual_usable_points_B_before_folding"] == target[
            "actual_usable_points_B_before_folding"] == 8000204
        assert row["signed_frobenius_columns"] == target[
            "signed_frobenius_columns"] == 48194
    for row in (prior, ci_plan, q1092, first, second, reserve):
        assert row["factor_base_enumerated_set_sha256"] == target[
            "factor_base_enumerated_set_sha256"]
    for row in (prior, ci_plan, budget, q1092, reserve):
        assert row["candidate_id"] == ci_plan["candidate_id"]
        assert row["run_id"] == ci_plan["run_id"]
    for row in (first, second):
        assert row["public_target"] == target["public_target"]
        assert row["candidate_id"] == first["candidate_id"]
        assert row["run_id"] == first["run_id"]
    local_calls = 2 * int(first["modeled_native_field_calls_per_job"])
    assert first["modeled_native_field_calls_per_job"] == second[
        "modeled_native_field_calls_per_job"]
    ci80 = int(budget["all_80_jobs_plus_local_controls_field_api_call_model"])
    ci208 = int(q1092[
        "all_208_jobs_plus_controls_regular_path_field_api_call_model"])
    total80 = ci80 + local_calls
    total208 = ci208 + local_calls
    assert math.log2(local_calls) < 61
    assert reserve["q1090_q1091_plus_local_cycle_capacity_log2"] < 61
    assert reserve["q1090_q1091_q1092_plus_local_cycle_capacity_log2"] < 61
    return {
        "kind": "n83_q1093_two_candidate_one_target_search_work_screen",
        "status": "planned_and_live_search_no_fresh_solve",
        "curve_id": target["curve_id"],
        "workload_id": target["workload_id"],
        "isogeny": "none",
        "factor_base_enumerated_set_sha256": target[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": 8000204,
        "signed_frobenius_columns": 48194,
        "ci_candidate_id": ci_plan["candidate_id"],
        "ci_run_id": ci_plan["run_id"],
        "local_candidate_id": first["candidate_id"],
        "local_run_id": first["run_id"],
        "local_disjoint_query_intervals": [
            [first["query_starts"][0], first["query_end_exclusive"]],
            [second["query_starts"][0], second["query_end_exclusive"]],
        ],
        "local_regular_path_field_api_call_model": str(local_calls),
        "local_regular_path_field_api_call_model_log2": math.log2(local_calls),
        "all_80_ci_jobs_controls_and_two_local_regular_path_model": str(total80),
        "all_80_ci_jobs_controls_and_two_local_regular_path_model_log2": (
            math.log2(total80)),
        "all_208_conditional_ci_jobs_controls_and_two_local_regular_path_model": (
            str(total208)),
        "all_208_conditional_ci_jobs_controls_and_two_local_regular_path_model_log2": (
            math.log2(total208)),
        "all_80_ci_jobs_plus_full_local_reserve_cpu_cycle_capacity_log2": (
            reserve["q1090_q1091_plus_local_cycle_capacity_log2"]),
        "all_208_conditional_ci_jobs_plus_full_local_reserve_cpu_cycle_capacity_log2": (
            reserve["q1090_q1091_q1092_plus_local_cycle_capacity_log2"]),
        "measured_natural_relations_on_fresh_target": None,
        "verified_fresh_target_scalar": None,
        "measured_complete_solve_work_log2": None,
        "target_sha256": sha(TARGET),
        "prior_Q1090_audit_sha256": sha(PRIOR),
        "Q1091_plan_sha256": sha(CI_PLAN),
        "Q1091_budget_sha256": sha(CI_BUDGET),
        "Q1092_design_sha256": sha(Q1092),
        "first_local_plan_sha256": sha(LOCAL_FIRST),
        "second_local_plan_sha256": sha(LOCAL_SECOND),
        "revised_30day_reserve_sha256": sha(RESERVE),
        "source_sha256": sha(Path(__file__)),
        "limits": [
            "Field API-call sums are regular-path full-shape models for scheduled jobs, not measured or upper-bounded complete-solve operations; failed, canceled, and partial work require terminal reconciliation.",
            "The 208-job case is conditional on a Q1091 terminal-zero gate; it is not a dispatched Q1092 result.",
            "CPU figures are assumed hardware capacity ceilings that charge all 14 local cores continuously for 30 days and each scheduled CI job a full six hours on four vCPUs at assumed 8 GHz.",
            "The two local rectangles use a distinct canonical candidate but the same curve, factor base, and previously unseen one-target workload.",
            "No natural relation, fresh scalar, paired one-target rho speedup, or measured complete-solve work is established by this screen.",
        ],
    }


def main():
    result = screen()
    content = json.dumps(result, indent=2) + "\n"
    if OUTPUT.exists():
        assert OUTPUT.read_text() == content
    else:
        OUTPUT.write_text(content)
    print(json.dumps({key: result[key] for key in (
        "local_regular_path_field_api_call_model_log2",
        "all_80_ci_jobs_controls_and_two_local_regular_path_model_log2",
        "all_208_conditional_ci_jobs_controls_and_two_local_regular_path_model_log2",
        "all_208_conditional_ci_jobs_plus_full_local_reserve_cpu_cycle_capacity_log2")}))


if __name__ == "__main__":
    main()
