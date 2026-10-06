#!/usr/bin/env python3
"""Screen a disjoint same-candidate fallback if Q1091 ends with zero hits.

This freezes neither a workflow nor a terminal Q1091 result. It is a
conditional placement/resource calculation that must be refreshed against
Q1091's independently audited terminal receipts before any dispatch.
"""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "n83_q1091_holdout_m32_continuation_plan.json"
PRIOR = HERE / "n83_q1090_terminal_wave_audit.json"
BASE = HERE / "n83_large_knownlog_base_screen.json"
BUDGET = HERE / "n83_q1091_resource_budget.json"
CEILING = HERE / "n83_q1091_total_resource_ceiling.json"
OUTPUT = HERE / "n83_q1092_conditional_same_candidate_fallback.json"
PRIOR_JOBS = 80
ADDITIONAL_JOBS = 128
LOCAL_RESERVE_SECONDS = 24 * 3600
LOCAL_CORES = 14
ASSUMED_CLOCK_HZ = 8_000_000_000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads(PLAN.read_text())
    prior = json.loads(PRIOR.read_text())
    base = json.loads(BASE.read_text())
    budget = json.loads(BUDGET.read_text())
    ceiling = json.loads(CEILING.read_text())
    candidate_path = HERE / plan["candidate_manifest"]
    candidate = json.loads(candidate_path.read_text())
    assert plan["candidate_manifest_sha256"] == sha(candidate_path)
    assert candidate["candidate_id"] == plan["candidate_id"]
    assert plan["prior_Q1090_terminal_audit_sha256"] == sha(PRIOR)
    assert prior["completed_jobs"] == 16
    assert prior["exact_hit_queries"] == 0
    assert len(plan["query_starts"]) == 64
    assert plan["query_end_exclusive"] == (PRIOR_JOBS *
                                            plan["query_representatives"])
    assert budget["continuation_plan_sha256"] == sha(PLAN)
    assert ceiling["resource_budget_sha256"] == sha(BUDGET)
    for row in (plan, prior, budget, ceiling):
        assert row["curve_id"] == base["curve_id"]
        assert row["isogeny"] == "none"
        assert row["candidate_id"] == plan["candidate_id"]
        assert row["workload_id"] == plan["workload_id"]
        assert row["run_id"] == plan["run_id"]
    assert plan["factor_base_enumerated_set_sha256"] == base[
        "factor_base"]["enumerated_set_sha256"]
    assert plan["actual_usable_points_B_before_folding"] == base[
        "factor_base"]["actual_usable_points_B_before_folding"]
    assert plan["signed_frobenius_columns"] == base[
        "factor_base"]["signed_frobenius_columns"]
    assert plan["table_descriptors"] == 1 << 32
    assert plan["query_representatives"] == 1 << 29
    assert candidate["point_decomposition"][
        "table_descriptors_per_job"] == plan["table_descriptors"]
    assert candidate["point_decomposition"][
        "query_representatives_per_job"] == plan["query_representatives"]
    starts = [(PRIOR_JOBS + i) * plan["query_representatives"]
              for i in range(ADDITIONAL_JOBS)]
    end = starts[-1] + plan["query_representatives"]
    assert starts[0] == plan["query_end_exclusive"]
    assert end <= candidate["point_decomposition"][
        "query_representative_schedule"]["domain"]
    assert all(starts[i] + plan["query_representatives"] <= starts[i + 1]
               for i in range(len(starts) - 1))

    key_fraction = (plan["table_descriptors"] /
                    base["zero_pair_key_cap_before_accidental_collisions"])
    pair_fraction_per_job = (plan["query_representatives"] *
                             base["factor_base"]["signed_frobenius_orbit_size"] /
                             base["unordered_query_pair_domain"])
    mean = base["heuristic_mean_four_point_multisets"]

    def intensity(jobs):
        coverage = jobs * key_fraction * pair_fraction_per_job
        assert 0 <= coverage <= 1
        return mean * (1 - (1 - coverage) ** 6)

    added_intensity = intensity(PRIOR_JOBS + ADDITIONAL_JOBS) - intensity(
        PRIOR_JOBS)
    conditional_hit = -math.expm1(-added_intensity)
    total_jobs = PRIOR_JOBS + ADDITIONAL_JOBS
    per_full_calls = int(plan["modeled_native_field_calls_per_job"])
    per_control_calls = int(budget[
        "per_bounded_control_regular_path_field_api_call_model"])
    local_controls = budget["local_bounded_controls_completed"]
    total_modeled_calls = (total_jobs * per_full_calls +
                           (total_jobs + local_controls) * per_control_calls)
    ci_cycle_capacity = (total_jobs * plan["timeout_seconds_per_job"] *
                         budget["assumed_vcpu_per_standard_ubuntu_job"] *
                         ASSUMED_CLOCK_HZ)
    local_cycle_reserve = (LOCAL_RESERVE_SECONDS * LOCAL_CORES *
                           ASSUMED_CLOCK_HZ)
    assert local_cycle_reserve == int(ceiling["local_reserved_cycle_capacity"])
    all_cycle_capacity = ci_cycle_capacity + local_cycle_reserve
    assert all_cycle_capacity < 1 << 61
    result = {
        "kind": "n83_q1092_conditional_same_candidate_zero_hit_fallback_screen",
        "status": "design_only_Q1091_live_no_terminal_result",
        "proposal_id": None,
        "wave_proposal_id": "Q1092",
        "raw_runner_proposal_id": plan["proposal_id"],
        "curve_id": plan["curve_id"],
        "isogeny": "none",
        "candidate_id": plan["candidate_id"],
        "workload_id": plan["workload_id"],
        "run_id": plan["run_id"],
        "actual_usable_points_B_before_folding": plan[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": plan["signed_frobenius_columns"],
        "factor_base_enumerated_set_sha256": plan[
            "factor_base_enumerated_set_sha256"],
        "table_descriptors_per_job": plan["table_descriptors"],
        "query_representatives_per_job": plan["query_representatives"],
        "prior_jobs_if_Q1091_terminal_zero": PRIOR_JOBS,
        "additional_conditional_jobs": ADDITIONAL_JOBS,
        "additional_query_starts": starts,
        "query_end_exclusive": end,
        "model_conditional_hit_probability_if_zero_after_80":
            conditional_hit,
        "model_no_hit_probability_after_all_208_from_start": math.exp(
            -intensity(total_jobs)),
        "model_intensity_added_after_80": added_intensity,
        "all_208_jobs_plus_controls_regular_path_field_api_call_model": str(
            total_modeled_calls),
        "all_208_jobs_plus_controls_regular_path_field_api_call_model_log2":
            math.log2(total_modeled_calls),
        "all_208_ci_job_cycle_capacity_log2": math.log2(
            ci_cycle_capacity),
        "all_208_plus_local_reserve_cycle_capacity_log2": math.log2(
            all_cycle_capacity),
        "below_2_61_under_stated_resource_assumptions": True,
        "Q1091_terminal_audit": None,
        "executable_plan": None,
        "workflow": None,
        "measured_natural_relations": None,
        "measured_complete_solve_operations_log2": None,
        "verified_discrete_logarithm": None,
        "one_target_online_wall_ms": None,
        "prior_Q1090_terminal_audit_sha256": sha(PRIOR),
        "Q1091_plan_sha256": sha(PLAN),
        "Q1091_budget_sha256": sha(BUDGET),
        "Q1091_whole_run_ceiling_sha256": sha(CEILING),
        "base_screen_sha256": sha(BASE),
        "candidate_manifest_sha256": sha(candidate_path),
        "source_sha256": sha(Path(__file__)),
        "limits": [
            "This screen assumes all 64 Q1091 jobs finish with independently audited zero exact hits; that condition is not yet observed.",
            "The 128 extra rectangles preserve the candidate's frozen M32/R29 method and continue its one-target run without reusing query representatives.",
            "The 95.99% conditional hit chance is a finite-support placement heuristic, not measured relation yield or guaranteed success.",
            "The field-call figure is a regular-path search-shape model; the CPU figure is a conditional full-timeout capacity with the same local reserve as Q1091.",
            "No executable plan or workflow is frozen. Any dispatch requires a terminal Q1091 audit and an updated complete-work ledger.",
        ],
    }
    assert not OUTPUT.exists(), "refusing to overwrite fallback screen"
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in (
        "model_conditional_hit_probability_if_zero_after_80",
        "all_208_jobs_plus_controls_regular_path_field_api_call_model_log2",
        "all_208_plus_local_reserve_cycle_capacity_log2",
        "verified_discrete_logarithm")}))


if __name__ == "__main__":
    main()
