#!/usr/bin/env python3
"""Project first-hit search work after the audited Q1090 zero-hit prefix.

This finite-support placement model is a diagnostic. It is neither an
empirical yield rate nor a complete discrete-logarithm work measurement.
"""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT = HERE / "n83_q1090_terminal_wave_audit.json"
PLAN = HERE / "n83_q1091_holdout_m32_continuation_plan.json"
BASE = HERE / "n83_large_knownlog_base_screen.json"
BUDGET = HERE / "n83_q1091_resource_budget.json"
OUTPUT = HERE / "n83_q1091_conditional_first_hit_projection.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    audit = json.loads(AUDIT.read_text())
    plan = json.loads(PLAN.read_text())
    base = json.loads(BASE.read_text())
    budget = json.loads(BUDGET.read_text())
    assert audit["completed_jobs"] == 16
    assert audit["exact_hit_queries"] == 0
    assert audit["independently_verified_natural_relations"] == 0
    assert plan["prior_Q1090_terminal_audit_sha256"] == sha(AUDIT)
    assert budget["prior_audit_sha256"] == sha(AUDIT)
    assert budget["continuation_plan_sha256"] == sha(PLAN)
    assert len(plan["query_starts"]) == 64
    assert plan["query_starts"] == [
        (16 + i) * plan["query_representatives"] for i in range(64)]
    assert plan["candidate_id"] == audit["candidate_id"] == budget[
        "candidate_id"]
    assert plan["workload_id"] == audit["workload_id"] == budget[
        "workload_id"]
    assert plan["run_id"] == audit["run_id"] == budget["run_id"]
    assert plan["curve_id"] == base["curve_id"] == audit["curve_id"]
    assert plan["isogeny"] == base["isogeny"] == audit["isogeny"] == "none"
    assert plan["factor_base_enumerated_set_sha256"] == base[
        "factor_base"]["enumerated_set_sha256"]
    assert plan["actual_usable_points_B_before_folding"] == base[
        "factor_base"]["actual_usable_points_B_before_folding"]
    assert plan["signed_frobenius_columns"] == base[
        "factor_base"]["signed_frobenius_columns"]

    descriptor_domain = base["zero_pair_key_cap_before_accidental_collisions"]
    pair_domain = base["unordered_query_pair_domain"]
    orbit_size = base["factor_base"]["signed_frobenius_orbit_size"]
    mean_relations = base["heuristic_mean_four_point_multisets"]
    point_count = plan["actual_usable_points_B_before_folding"]
    column_count = plan["signed_frobenius_columns"]
    subgroup_order = base["curve_identity_record"]["curve"][
        "subgroup_order"]
    assert pair_domain == point_count * (point_count + 1) // 2
    assert descriptor_domain == (math.comb(column_count, 2) * orbit_size +
                                 column_count * (orbit_size // 2))
    assert math.isclose(mean_relations,
                        math.comb(point_count + 3, 4) / subgroup_order)
    table_fraction = plan["table_descriptors"] / descriptor_domain
    queries_per_job = plan["query_representatives"] * orbit_size
    query_fraction_per_job = queries_per_job / pair_domain
    assert 0 < table_fraction < 1
    assert 80 * query_fraction_per_job < 1
    assert plan["table_descriptors"] <= descriptor_domain

    def intensity(total_jobs):
        coverage = table_fraction * query_fraction_per_job * total_jobs
        return mean_relations * (1 - (1 - coverage) ** 6)

    prior_intensity = intensity(16)
    per_full_calls = int(plan["modeled_native_field_calls_per_job"])
    per_control_calls = int(budget[
        "per_bounded_control_regular_path_field_api_call_model"])
    local_controls = budget["local_bounded_controls_completed"]

    def charged_calls(added_jobs):
        total_jobs = 16 + added_jobs
        return (total_jobs * per_full_calls +
                (total_jobs + local_controls) * per_control_calls)

    probabilities = [0.0]
    rows = []
    for added_jobs in range(1, 65):
        added_intensity = intensity(16 + added_jobs) - prior_intensity
        probability = -math.expm1(-added_intensity)
        assert probability > probabilities[-1]
        probabilities.append(probability)
        if added_jobs % 8 == 0:
            rows.append({
                "additional_completed_rectangles": added_jobs,
                "total_completed_rectangles": 16 + added_jobs,
                "model_conditional_first_hit_probability": probability,
                "cumulative_regular_path_field_api_call_model_log2":
                    math.log2(charged_calls(added_jobs)),
            })
    assert math.isclose(rows[-1][
        "cumulative_regular_path_field_api_call_model_log2"], budget[
            "all_80_jobs_plus_local_controls_field_api_call_model_log2"])
    hit_probability = probabilities[-1]
    expected_jobs_given_hit = sum(
        index * (probabilities[index] - probabilities[index - 1])
        for index in range(1, 65)) / hit_probability
    quantiles = {
        str(q): next((index for index, probability in
                      enumerate(probabilities) if probability >= q), None)
        for q in (0.5, 0.9, 0.95)
    }
    result = {
        "kind": "n83_q1091_holdout_conditional_finite_support_first_hit_projection",
        "status": "prior_16_zero_hits_measured_next_64_outcomes_unknown",
        "proposal_id": None,
        "raw_prior_proposal_id": "Q1090",
        "raw_continuation_proposal_id": "Q1091",
        "candidate_id": plan["candidate_id"],
        "workload_id": plan["workload_id"],
        "run_id": plan["run_id"],
        "curve_id": plan["curve_id"],
        "isogeny": "none",
        "factor_base_enumerated_set_sha256": plan[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": plan[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": plan["signed_frobenius_columns"],
        "measured_prior_completed_rectangles": 16,
        "measured_prior_exact_hits": 0,
        "planned_additional_rectangles": 64,
        "model_unordered_pair_domain": pair_domain,
        "model_quotient_key_cap_before_collisions": descriptor_domain,
        "model_mean_four_point_multisets": mean_relations,
        "model_table_key_fraction": table_fraction,
        "model_query_pair_fraction_per_rectangle": query_fraction_per_job,
        "model_prior_intensity": prior_intensity,
        "model_future_intensity_given_zero_prefix":
            intensity(80) - prior_intensity,
        "model_conditional_hit_probability_by_64": hit_probability,
        "model_conditional_no_hit_probability_by_64":
            1 - hit_probability,
        "model_expected_additional_rectangle_index_given_hit_by_64":
            expected_jobs_given_hit,
        "model_expected_cumulative_field_api_calls_given_hit_by_64_log2":
            math.log2(charged_calls(expected_jobs_given_hit)),
        "model_cumulative_field_api_calls_at_50pct_first_hit_log2":
            math.log2(charged_calls(quantiles["0.5"])),
        "model_first_hit_rectangle_thresholds": quantiles,
        "model_rate_sensitivity": [{
            "intensity_multiplier": factor,
            "conditional_hit_probability_by_64": -math.expm1(
                -factor * (intensity(80) - prior_intensity)),
        } for factor in (0.25, 0.5, 1.0, 2.0)],
        "model_eight_rectangle_checkpoints": rows,
        "all_80_rectangles_plus_controls_regular_path_field_api_call_model_log2":
            budget["all_80_jobs_plus_local_controls_field_api_call_model_log2"],
        "all_80_ci_job_conditional_cpu_cycle_capacity_log2": budget[
            "all_80_job_cpu_core_cycle_capacity_log2"],
        "predicted_complete_solve_operations_log2": None,
        "measured_complete_solve_operations_log2": None,
        "verified_fresh_target_discrete_logarithm": False,
        "one_target_online_wall_ms": None,
        "paired_rho_online_wall_ms": None,
        "prior_audit_sha256": sha(AUDIT),
        "continuation_plan_sha256": sha(PLAN),
        "base_screen_sha256": sha(BASE),
        "resource_budget_sha256": sha(BUDGET),
        "source_sha256": sha(Path(__file__)),
        "limits": [
            "The finite-support random-placement intensity is a heuristic, not an empirical rate for this fixed target; zero prior hits do not supply a positive yield lower bound.",
            "The first-hit index treats disjoint rectangles in query order. Eight concurrent jobs can consume work beyond that index before cancellation or verification.",
            "Field API-call counts model the regular native path and include same-host bounded controls and two local controls, but exclude keying, Bloom, memory, disk, exceptional work, and replay.",
            "The conditional CPU-cycle capacity covers CI jobs at four vCPUs and an assumed 8 GHz per vCPU; it excludes local controls and reusable base construction.",
            "Neither the model probability nor the resource budget is a measured complete discrete-logarithm work exponent. A verified scalar and all charged phase costs are required.",
        ],
    }
    assert not OUTPUT.exists(), "refusing to overwrite projection"
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in (
        "model_conditional_hit_probability_by_64",
        "model_expected_additional_rectangle_index_given_hit_by_64",
        "model_expected_cumulative_field_api_calls_given_hit_by_64_log2",
        "model_first_hit_rectangle_thresholds",
        "all_80_rectangles_plus_controls_regular_path_field_api_call_model_log2",
        "predicted_complete_solve_operations_log2")}))


if __name__ == "__main__":
    main()
