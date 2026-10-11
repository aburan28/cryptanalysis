#!/usr/bin/env python3
"""Price a disjoint continuation after the measured Q1090 zero-yield wave."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "n83_q1091_holdout_m32_continuation_plan.json"
AUDIT = HERE / "n83_q1090_terminal_wave_audit.json"
LOCAL_CONTROLS = (
    HERE / "runs" / "n83_holdout_q1090_smoke_M20_R14.json",
    HERE / "runs" / "n83_q1091_first_range_smoke_M20_R14.json",
)
LOCAL_CONTROL_SAGE = (
    HERE / "runs" / "n83_holdout_q1090_smoke_M20_R14_sage_verify.json",
    HERE / "runs" / "n83_q1091_first_range_smoke_M20_R14_sage_verify.json",
)
OUTPUT = HERE / "n83_q1091_resource_budget.json"
PRIOR_JOBS = 16
NEW_JOBS = 64
VCPU_PER_JOB = 4
ASSUMED_CLOCK_HZ = 8_000_000_000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads(PLAN.read_text())
    audit = json.loads(AUDIT.read_text())
    assert plan["proposal_id"] == "Q1090"
    assert plan["wave_proposal_id"] == "Q1091"
    assert plan["status"] == "ready_for_dispatch"
    assert plan["prior_Q1090_terminal_audit_sha256"] == sha(AUDIT)
    assert audit["candidate_id"] == plan["candidate_id"]
    assert audit["workload_id"] == plan["workload_id"]
    assert audit["run_id"] == plan["run_id"]
    assert audit["curve_id"] == plan["curve_id"]
    assert audit["isogeny"] == plan["isogeny"] == "none"
    assert audit["completed_jobs"] == PRIOR_JOBS
    assert audit["failed_jobs"] == audit["exact_hit_queries"] == 0
    assert audit["independently_verified_natural_relations"] == 0
    assert audit["query_end_exclusive"] == plan[
        "prior_completed_query_end_exclusive"]
    assert len(plan["query_starts"]) == NEW_JOBS
    assert plan["query_starts"] == [
        (PRIOR_JOBS + i) * (1 << 29) for i in range(NEW_JOBS)]
    per_job = int(plan["modeled_native_field_calls_per_job"])
    assert int(audit["native_regular_path_field_api_call_model"]) == (
        PRIOR_JOBS * per_job)
    cumulative_calls = (PRIOR_JOBS + NEW_JOBS) * per_job
    assert math.isclose(math.log2(cumulative_calls), plan[
        "modeled_native_field_calls_cumulative_80_jobs_log2"])
    local_controls = [json.loads(path.read_text()) for path in
                      LOCAL_CONTROLS]
    local_sage = [json.loads(path.read_text()) for path in
                  LOCAL_CONTROL_SAGE]
    for control, sage, receipt_path in zip(
            local_controls, local_sage, LOCAL_CONTROLS):
        assert control["workload_id"] == plan["workload_id"]
        assert control["public_target"] == plan["public_target"]
        assert control["native_result"]["exact_hit_queries"] == 0
        assert sage["receipt_sha256"] == sha(receipt_path)
        assert sage["verified_relation_count"] == 0
    control_calls = int(local_controls[0][
        "native_field_add_mul_sqr_call_model"])
    assert all(int(row["native_field_add_mul_sqr_call_model"]) ==
               control_calls for row in local_controls)
    assert int(audit["control_regular_path_field_api_call_model"]) == (
        PRIOR_JOBS * control_calls)
    inclusive_calls = cumulative_calls + (
        PRIOR_JOBS + NEW_JOBS + len(local_controls)) * control_calls
    max_seconds = plan["timeout_seconds_per_job"]
    assert max_seconds == 6 * 3600
    cumulative_capacity = ((PRIOR_JOBS + NEW_JOBS) * max_seconds *
                           VCPU_PER_JOB * ASSUMED_CLOCK_HZ)
    assert cumulative_capacity < 1 << 61
    report = {
        "kind": "n83_q1091_conditional_cumulative_holdout_resource_budget",
        "status": "prior_wave_measured_zero_yield_next_wave_planned",
        "curve_id": plan["curve_id"],
        "isogeny": "none",
        "candidate_id": plan["candidate_id"],
        "workload_id": plan["workload_id"],
        "run_id": plan["run_id"],
        "actual_usable_points_B_before_folding": plan[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": plan["signed_frobenius_columns"],
        "prior_completed_jobs": PRIOR_JOBS,
        "prior_exact_hits": 0,
        "prior_independently_verified_relations": 0,
        "new_planned_jobs": NEW_JOBS,
        "per_job_regular_path_field_api_call_model": str(per_job),
        "prior_completed_regular_path_field_api_call_model": audit[
            "native_regular_path_field_api_call_model"],
        "all_80_job_regular_path_field_api_call_model": str(
            cumulative_calls),
        "all_80_job_regular_path_field_api_call_model_log2": math.log2(
            cumulative_calls),
        "per_bounded_control_regular_path_field_api_call_model": str(
            control_calls),
        "local_bounded_controls_completed": len(local_controls),
        "all_80_jobs_plus_local_controls_field_api_call_model": str(
            inclusive_calls),
        "all_80_jobs_plus_local_controls_field_api_call_model_log2":
            math.log2(inclusive_calls),
        "all_80_job_timeout_seconds_per_job_including_setup": max_seconds,
        "assumed_vcpu_per_standard_ubuntu_job": VCPU_PER_JOB,
        "assumed_clock_hz_ceiling_per_vcpu": ASSUMED_CLOCK_HZ,
        "all_80_job_cpu_core_cycle_capacity": str(cumulative_capacity),
        "all_80_job_cpu_core_cycle_capacity_log2": math.log2(
            cumulative_capacity),
        "below_2_61_under_stated_resource_assumptions": True,
        "complete_discrete_logarithm": None,
        "measured_complete_solve_operations": None,
        "one_target_online_wall_ms": None,
        "paired_rho_online_wall_ms": None,
        "limits": [
            "Q1090's sixteen disjoint jobs completed with zero exact hits and zero independently verified relations.",
            "The 64 Q1091 jobs are a frozen continuation on the same public target and run ID; their outcome is not yet measured.",
            "The cumulative field-call figure models regular-path native arithmetic only. It omits keying, Bloom, memory, disk, exceptional work, and independent replay.",
            "The inclusive field-call model charges the two local bounded controls and every same-host bounded CI control, including repeated target-dependent work.",
            "The CPU capacity charges all 80 jobs the full six-hour limit on four-vCPU standard runners at an assumed 8 GHz per vCPU. It is a conditional resource ceiling, not measured instructions or calibrated field operations.",
            "The reusable factor-base build, two local bounded controls, and any other work on local hosts are outside this CI-job cycle capacity. No completed DLP is claimed from a resource budget.",
        ],
        "github_runner_specification":
            "https://docs.github.com/en/actions/reference/runners/github-hosted-runners",
        "prior_audit_sha256": sha(AUDIT),
        "local_control_receipt_sha256": [sha(path) for path in
                                         LOCAL_CONTROLS],
        "local_control_sage_sha256": [sha(path) for path in
                                      LOCAL_CONTROL_SAGE],
        "continuation_plan_sha256": sha(PLAN),
        "source_sha256": sha(Path(__file__)),
    }
    assert not OUTPUT.exists(), "refusing to overwrite Q1091 budget"
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "prior_verified_relations": 0,
        "all_80_job_field_model_log2": math.log2(cumulative_calls),
        "all_80_job_cpu_capacity_log2": math.log2(cumulative_capacity),
    }))


if __name__ == "__main__":
    main()
