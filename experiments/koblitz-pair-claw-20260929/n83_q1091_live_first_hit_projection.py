#!/usr/bin/env python3
"""Update the Q1091 first-hit model from an audited zero-hit checkpoint.

Only independently credited complete rectangles enter the zero-hit prefix.
The output remains a placement-model diagnostic, not measured solve work.
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


def project(reconciliation_path):
    run = load(reconciliation_path)
    plan = load(PLAN)
    base = load(BASE)
    budget = load(BUDGET)
    for key in ("curve_id", "candidate_id", "workload_id", "run_id"):
        assert run[key] == plan[key] == budget[key]
    assert run["isogeny"] == plan["isogeny"] == budget["isogeny"] == "none"
    assert run["actual_usable_points_B_before_folding"] == plan[
        "actual_usable_points_B_before_folding"]
    assert run["signed_frobenius_columns"] == plan[
        "signed_frobenius_columns"]
    assert run["prior_Q1090_completed_jobs"] == PRIOR_JOBS
    assert run["Q1091_verified_relations"] == 0
    assert run.get("Q1091_control_verified_relations", 0) == 0
    assert run.get("Q1091_partial_full_sage_replay_relations", 0) == 0
    assert run["verified_fresh_target_scalar"] is None
    assert run["Q1091_reported_unverified_hits_in_partial_artifacts"] == 0
    assert run["Q1091_failed_or_canceled_jobs"] == 0
    assert run["Q1091_success_jobs_missing_complete_audit"] == 0
    assert plan["factor_base_enumerated_set_sha256"] == base[
        "factor_base"]["enumerated_set_sha256"]
    assert plan["actual_usable_points_B_before_folding"] == base[
        "factor_base"]["actual_usable_points_B_before_folding"]
    assert plan["signed_frobenius_columns"] == base[
        "factor_base"]["signed_frobenius_columns"]
    reps = plan["query_representatives"]
    credited, remainder = divmod(
        run["credited_disjoint_query_representatives"], reps)
    assert remainder == 0 and PRIOR_JOBS <= credited < TOTAL_JOBS
    assert credited - PRIOR_JOBS == run["Q1091_terminal_jobs"]
    assert all(row["coverage_credit"] in (0, reps) for row in run["jobs"])
    assert sum(row["coverage_credit"] for row in run["jobs"]) == (
        (credited - PRIOR_JOBS) * reps)
    assert [row["coverage_credit"] for row in run["jobs"]] == (
        [reps] * (credited - PRIOR_JOBS) +
        [0] * (TOTAL_JOBS - credited)), (
            "first-hit projection requires a consecutive audited zero prefix")

    orbit_size = base["factor_base"]["signed_frobenius_orbit_size"]
    key_fraction = (plan["table_descriptors"] /
                    base["zero_pair_key_cap_before_accidental_collisions"])
    query_fraction = (reps * orbit_size /
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
    expected_added_given_hit = sum(
        added * (probabilities[added] - probabilities[added - 1])
        for added in range(1, len(probabilities))) / hit_probability
    per_full = int(plan["modeled_native_field_calls_per_job"])
    per_control = int(budget[
        "per_bounded_control_regular_path_field_api_call_model"])
    local_controls = budget["local_bounded_controls_completed"]
    def cumulative_calls(jobs):
        return (jobs * per_full +
                (jobs + local_controls) * per_control)

    conditional_quantiles = {}
    for label, quantile in (("p05", 0.05), ("p50", 0.50),
                            ("p95", 0.95)):
        added = next(i for i in range(1, len(probabilities))
                     if probabilities[i] >= quantile * hit_probability)
        conditional_quantiles[label] = {
            "additional_rectangle_index": added,
            "cumulative_regular_path_field_api_calls_log2": math.log2(
                cumulative_calls(credited + added)),
        }
    expected_total_jobs = credited + expected_added_given_hit
    expected_calls = cumulative_calls(expected_total_jobs)
    all_80_calls = cumulative_calls(TOTAL_JOBS)
    assert math.isclose(math.log2(all_80_calls), budget[
        "all_80_jobs_plus_local_controls_field_api_call_model_log2"])
    return {
        "kind": "n83_q1091_audited_zero_prefix_conditional_first_hit_projection",
        "status": "model_only_no_fresh_dlp",
        "curve_id": plan["curve_id"],
        "isogeny": "none",
        "candidate_id": plan["candidate_id"],
        "workload_id": plan["workload_id"],
        "run_id": plan["run_id"],
        "factor_base_enumerated_set_sha256": plan[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": plan[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": plan["signed_frobenius_columns"],
        "independently_audited_zero_rectangles": credited,
        "Q1091_audited_zero_rectangles": credited - PRIOR_JOBS,
        "remaining_planned_rectangles": TOTAL_JOBS - credited,
        "model_conditional_hit_probability_by_80": hit_probability,
        "model_no_hit_probability_by_80": 1 - hit_probability,
        "model_expected_additional_rectangle_index_given_hit_by_80":
            expected_added_given_hit,
        "model_expected_cumulative_regular_path_field_api_calls_given_hit_log2":
            math.log2(expected_calls),
        "model_first_hit_work_quantiles_given_hit_by_80":
            conditional_quantiles,
        "all_80_jobs_plus_controls_regular_path_field_api_call_model_log2":
            math.log2(all_80_calls),
        "predicted_complete_solve_operations_log2": None,
        "measured_complete_solve_operations_log2": None,
        "verified_fresh_target_discrete_logarithm": False,
        "reconciliation_sha256": sha(reconciliation_path),
        "plan_sha256": sha(PLAN),
        "base_screen_sha256": sha(BASE),
        "resource_budget_sha256": sha(BUDGET),
        "source_sha256": sha(Path(__file__)),
        "limits": [
            "The finite-support random-placement intensity is a heuristic, not an empirical rate for this fixed target.",
            "Only independently audited zero-hit rectangles are conditioned on; live and missing-artifact jobs are not treated as zero hits.",
            "The first-hit index treats disjoint rectangles in query order. Concurrent jobs can consume additional work before cancellation.",
            "The conditional quantiles exclude the explicit no-hit mass at rectangle 80; they are not unconditional solve-work quantiles.",
            "Field API calls model the regular native path; non-field work, incomplete attempts, and replay are outside this search-shape figure.",
            "A verified scalar and an audit of all charged work are required for a measured complete-solve exponent.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reconciliation", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), "refusing to overwrite projection"
    result = project(args.reconciliation)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in (
        "independently_audited_zero_rectangles",
        "remaining_planned_rectangles",
        "model_conditional_hit_probability_by_80",
        "model_expected_cumulative_regular_path_field_api_calls_given_hit_log2")},
        indent=2))


if __name__ == "__main__":
    main()
