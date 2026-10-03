#!/usr/bin/env python3
"""Project the same-candidate first hit through conditional Q1092.

Only the frozen independently audited zero prefix is observed. Q1092 is a
design-stage continuation and this script never credits it with a hit.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "n83_q1091_holdout_m32_continuation_plan.json"
BASE = HERE / "n83_large_knownlog_base_screen.json"
BUDGET = HERE / "n83_q1091_resource_budget.json"
FALLBACK = HERE / "n83_q1092_conditional_same_candidate_fallback.json"
LOCAL = HERE / "n83_q1093_combined_search_work_screen.json"
CAPACITY = HERE / "n83_holdout_extended_resource_ceiling.json"


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project(stage_path):
    stage, plan, base, budget, fallback, local, capacity = map(
        load, (stage_path, PLAN, BASE, BUDGET, FALLBACK, LOCAL, CAPACITY))
    assert stage["kind"] == "n83_q1090_q1091_audited_zero_prefix_stage_diagnostic"
    assert stage["combined_independently_verified_natural_relations"] == 0
    assert stage["prior_Q1090_completed_zero_shards"] == 16
    assert stage["Q1091_completed_independently_verified_zero_shards"] == 24
    assert stage["frozen_Q1091_zero_prefix_shards"] == 24
    assert stage["Q1091_plan_sha256"] == sha(PLAN)
    for key in ("curve_id", "candidate_id", "workload_id", "run_id",
                "isogeny", "factor_base_enumerated_set_sha256",
                "actual_usable_points_B_before_folding",
                "signed_frobenius_columns"):
        assert stage[key] == plan[key] == fallback[key], key
        if key in budget:
            assert stage[key] == budget[key], key
    assert local["ci_candidate_id"] == plan["candidate_id"]
    assert local["ci_run_id"] == plan["run_id"]
    for key in ("curve_id", "workload_id", "isogeny",
                "factor_base_enumerated_set_sha256",
                "actual_usable_points_B_before_folding",
                "signed_frobenius_columns"):
        assert local[key] == plan[key], key
    assert capacity["candidate_ids"][1] == local["local_candidate_id"]
    assert capacity["run_ids"][1] == local["local_run_id"]
    assert capacity["candidate_ids"][0] == plan["candidate_id"]
    assert fallback["prior_jobs_if_Q1091_terminal_zero"] == 80
    assert fallback["additional_conditional_jobs"] == 128
    assert fallback["query_representatives_per_job"] == plan["query_representatives"]
    assert fallback["table_descriptors_per_job"] == plan["table_descriptors"]
    assert fallback["Q1091_plan_sha256"] == sha(PLAN)
    assert fallback["base_screen_sha256"] == sha(BASE)
    assert plan["factor_base_enumerated_set_sha256"] == base[
        "factor_base"]["enumerated_set_sha256"]

    credited = 40
    horizon = 80 + fallback["additional_conditional_jobs"]
    key_fraction = plan["table_descriptors"] / base[
        "zero_pair_key_cap_before_accidental_collisions"]
    query_fraction = (plan["query_representatives"] * base[
        "factor_base"]["signed_frobenius_orbit_size"] /
        base["unordered_query_pair_domain"])
    mean = base["heuristic_mean_four_point_multisets"]

    def intensity(jobs):
        coverage = jobs * key_fraction * query_fraction
        assert 0 <= coverage <= 1
        return mean * (1 - (1 - coverage) ** 6)

    def hit_by(jobs):
        return -math.expm1(-(intensity(jobs) - intensity(credited)))

    assert math.isclose(
        -math.expm1(-(intensity(horizon) - intensity(80))),
        fallback["model_conditional_hit_probability_if_zero_after_80"],
        rel_tol=0, abs_tol=1e-12)
    assert math.isclose(math.exp(-intensity(horizon)),
                        fallback["model_no_hit_probability_after_all_208_from_start"],
                        rel_tol=0, abs_tol=1e-12)
    probabilities = [hit_by(jobs) for jobs in range(credited, horizon + 1)]
    hit_probability = probabilities[-1]
    expected_job_given_hit = sum(
        (credited + offset) * (probabilities[offset] - probabilities[offset - 1])
        for offset in range(1, len(probabilities))) / hit_probability
    per_full = int(plan["modeled_native_field_calls_per_job"])
    per_control = int(budget[
        "per_bounded_control_regular_path_field_api_call_model"])
    controls = budget["local_bounded_controls_completed"]

    def cumulative_calls(jobs):
        return jobs * per_full + (jobs + controls) * per_control

    assert cumulative_calls(horizon) == int(fallback[
        "all_208_jobs_plus_controls_regular_path_field_api_call_model"])
    local_calls = int(local["local_regular_path_field_api_call_model"])
    assert cumulative_calls(horizon) + local_calls == int(local[
        "all_208_conditional_ci_jobs_controls_and_two_local_regular_path_model"])
    expected_calls = cumulative_calls(expected_job_given_hit)
    capacity_log2 = capacity["scenarios"]["208"][
        "total_conditional_cycle_capacity_log2"]
    return {
        "kind": "n83_q1091_q1092_frozen_zero_prefix_conditional_first_hit_projection",
        "status": "model_only_Q1092_dormant_no_fresh_dlp",
        "curve_id": plan["curve_id"],
        "candidate_id": plan["candidate_id"],
        "workload_id": plan["workload_id"],
        "run_id": plan["run_id"],
        "separately_charged_local_candidate_id": local["local_candidate_id"],
        "separately_charged_local_run_id": local["local_run_id"],
        "isogeny": "none",
        "factor_base_enumerated_set_sha256": plan[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": plan[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": plan["signed_frobenius_columns"],
        "audited_zero_rectangles": credited,
        "model_horizon_rectangles": horizon,
        "Q1092_status": "design_only_pending_terminal_Q1091_zero_audit",
        "model_conditional_hit_probability_by_208": hit_probability,
        "model_no_hit_probability_by_208": 1 - hit_probability,
        "model_expected_first_hit_rectangle_given_hit_by_208": expected_job_given_hit,
        "model_expected_cumulative_regular_path_field_api_calls_given_hit_log2": (
            math.log2(expected_calls)),
        "model_expected_cumulative_plus_two_full_local_rectangles_log2": (
            math.log2(expected_calls + local_calls)),
        "all_208_jobs_controls_and_two_local_regular_path_model_log2": (
            math.log2(cumulative_calls(horizon) + local_calls)),
        "conditional_208_job_plus_local_cpu_cycle_capacity_log2": capacity_log2,
        "measured_complete_solve_operations_log2": None,
        "verified_fresh_target_discrete_logarithm": None,
        "source_sha256": sha(Path(__file__)),
        "stage_diagnostic_sha256": sha(stage_path),
        "Q1091_plan_sha256": sha(PLAN),
        "base_screen_sha256": sha(BASE),
        "resource_budget_sha256": sha(BUDGET),
        "Q1092_design_screen_sha256": sha(FALLBACK),
        "two_local_search_screen_sha256": sha(LOCAL),
        "extended_capacity_sha256": sha(CAPACITY),
        "limits": [
            "The finite-support placement law is a heuristic, not measured natural relation yield.",
            "Q1092 dispatch requires all 64 Q1091 shards to finish and independently audit as zero-hit; that condition has not occurred.",
            "The conditional expectation excludes the explicit no-hit mass and assumes a sequential first-hit order; concurrent jobs may consume more.",
            "The two local ARM rectangles are separately modeled as fully consumed work regardless of their pending outcomes; they use a different candidate ID and earn no hit credit here.",
            "Field API calls exclude Bloom, keying, memory, incomplete attempts, and independent replay; CPU cycles are conditional resource capacity, not measured operations.",
            "No fresh scalar or complete calibrated solve-work exponent follows from this projection.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), "refusing to overwrite frozen projection"
    result = project(args.stage)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in (
        "model_conditional_hit_probability_by_208",
        "model_expected_cumulative_regular_path_field_api_calls_given_hit_log2",
        "model_expected_cumulative_plus_two_full_local_rectangles_log2")}))


if __name__ == "__main__":
    main()
