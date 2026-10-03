#!/usr/bin/env python3
"""Project first-hit search shape from a frozen audited Q1091 zero prefix.

This independently reuses the finite-support placement formula of the live
projection. The input is a compact source-bound stage record, so the model
does not depend on a mutable GitHub workflow API snapshot.
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
PRIOR_JOBS = 16
TOTAL_JOBS = 80


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def project(stage_path):
    stage, plan, base, budget = map(load, (stage_path, PLAN, BASE, BUDGET))
    assert stage["kind"] == "n83_q1090_q1091_audited_zero_prefix_stage_diagnostic"
    assert stage["combined_independently_verified_natural_relations"] == 0
    assert stage["prior_Q1090_completed_zero_shards"] == PRIOR_JOBS
    prefix = stage["Q1091_completed_independently_verified_zero_shards"]
    assert prefix == stage["frozen_Q1091_zero_prefix_shards"]
    assert 1 <= prefix < 64
    for key in ("curve_id", "candidate_id", "workload_id", "run_id",
                "isogeny", "factor_base_enumerated_set_sha256",
                "actual_usable_points_B_before_folding",
                "signed_frobenius_columns"):
        assert stage[key] == plan[key], key
        if key in budget:
            assert stage[key] == budget[key], key
    assert stage["Q1091_plan_sha256"] == sha(PLAN)
    assert plan["factor_base_enumerated_set_sha256"] == base[
        "factor_base"]["enumerated_set_sha256"]
    assert stage["combined_credited_query_representatives"] == (
        (PRIOR_JOBS + prefix) * plan["query_representatives"])
    credited = PRIOR_JOBS + prefix
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

    probabilities = [0.0]
    for added in range(1, TOTAL_JOBS - credited + 1):
        probabilities.append(-math.expm1(-(
            intensity(credited + added) - intensity(credited))))
    hit_probability = probabilities[-1]
    assert 0 < hit_probability < 1
    expected_added_given_hit = sum(
        added * (probabilities[added] - probabilities[added - 1])
        for added in range(1, len(probabilities))) / hit_probability
    per_full = int(plan["modeled_native_field_calls_per_job"])
    per_control = int(budget[
        "per_bounded_control_regular_path_field_api_call_model"])
    controls = budget["local_bounded_controls_completed"]

    def cumulative_calls(jobs):
        return jobs * per_full + (jobs + controls) * per_control

    expected_calls = cumulative_calls(credited + expected_added_given_hit)
    all_80_calls = cumulative_calls(TOTAL_JOBS)
    assert math.isclose(math.log2(all_80_calls), budget[
        "all_80_jobs_plus_local_controls_field_api_call_model_log2"],
        rel_tol=0, abs_tol=1e-12)
    return {
        "kind": "n83_q1091_frozen_zero_prefix_conditional_first_hit_projection",
        "status": "model_only_no_fresh_dlp",
        "curve_id": plan["curve_id"],
        "candidate_id": plan["candidate_id"],
        "workload_id": plan["workload_id"],
        "run_id": plan["run_id"],
        "isogeny": "none",
        "factor_base_enumerated_set_sha256": plan[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": plan[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": plan["signed_frobenius_columns"],
        "audited_zero_rectangles": credited,
        "remaining_Q1091_rectangles": TOTAL_JOBS - credited,
        "model_conditional_hit_probability_by_80": hit_probability,
        "model_no_hit_probability_by_80": 1 - hit_probability,
        "model_expected_additional_rectangle_index_given_hit_by_80": (
            expected_added_given_hit),
        "model_expected_cumulative_regular_path_field_api_calls_given_hit_log2": (
            math.log2(expected_calls)),
        "all_80_jobs_plus_controls_regular_path_field_api_call_model_log2": (
            math.log2(all_80_calls)),
        "measured_complete_solve_operations_log2": None,
        "verified_fresh_target_discrete_logarithm": None,
        "stage_diagnostic_sha256": sha(stage_path),
        "Q1091_plan_sha256": sha(PLAN),
        "base_screen_sha256": sha(BASE),
        "resource_budget_sha256": sha(BUDGET),
        "source_sha256": sha(Path(__file__)),
        "limits": [
            "The finite-support placement law is a heuristic for this fixed target, not measured natural relation yield.",
            "Only the frozen independently audited zero prefix conditions the model; live jobs have no zero-hit credit.",
            "The expectation is conditional on a hit by rectangle 80; explicit no-hit probability remains.",
            "Field API calls describe the full regular native path and exclude Bloom, keying, memory, incomplete attempts, and independent replay.",
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
        "audited_zero_rectangles", "remaining_Q1091_rectangles",
        "model_conditional_hit_probability_by_80",
        "model_expected_cumulative_regular_path_field_api_calls_given_hit_log2")}))


if __name__ == "__main__":
    main()
