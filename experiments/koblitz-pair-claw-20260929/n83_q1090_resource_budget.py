#!/usr/bin/env python3
"""Price the frozen holdout wave without confusing shape costs with a solve."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "n83_q1090_holdout_m32_wave_plan.json"
HOLDOUT = HERE / "n83_holdout_target_20261001.json"
OUTPUT = HERE / "n83_q1090_resource_budget.json"
JOBS = 16
STANDARD_RUNNER_VCPU = 4
ASSUMED_CLOCK_HZ = 8_000_000_000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads(PLAN.read_text())
    target = json.loads(HOLDOUT.read_text())
    assert plan["proposal_id"] == "Q1090"
    assert plan["status"] == "ready_for_dispatch"
    assert plan["curve_id"] == target["curve_id"]
    assert plan["workload_id"] == target["workload_id"]
    assert plan["public_target"] == target["public_target"]
    assert plan["holdout_target_sha256"] == sha(HOLDOUT)
    assert plan["candidate_id"].startswith(
        "IC1N83Ckb1fb8000204PDP4qtableRCdirectLAnoneTDdirectISO0h")
    assert plan["run_id"] == (
        plan["candidate_id"] + "W" + plan["workload_id"] + "R1")
    assert len(plan["query_starts"]) == JOBS
    assert len(set(plan["query_starts"])) == JOBS
    assert plan["query_starts"] == [i * (1 << 29) for i in range(JOBS)]
    assert plan["table_descriptors"] == 1 << 32
    assert plan["query_representatives"] == 1 << 29
    per_job_calls = int(plan["modeled_native_field_calls_per_job"])
    modeled_calls = JOBS * per_job_calls
    assert math.isclose(math.log2(modeled_calls), plan[
        "modeled_native_field_calls_sixteen_jobs_log2"])
    max_job_seconds = plan["timeout_seconds_per_job"]
    assert max_job_seconds == 6 * 3600
    capacity = (JOBS * max_job_seconds * STANDARD_RUNNER_VCPU *
                ASSUMED_CLOCK_HZ)
    assert capacity < 1 << 61
    report = {
        "kind": "n83_q1090_planned_wave_conditional_resource_budget",
        "status": "planned_capacity_not_measured_solve",
        "curve_id": plan["curve_id"], "isogeny": "none",
        "candidate_id": plan["candidate_id"],
        "workload_id": plan["workload_id"],
        "run_id": plan["run_id"],
        "actual_usable_points_B_before_folding": plan[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": plan["signed_frobenius_columns"],
        "planned_jobs": JOBS,
        "per_job_field_api_call_model": str(per_job_calls),
        "all_job_field_api_call_model": str(modeled_calls),
        "all_job_field_api_call_model_log2": math.log2(modeled_calls),
        "job_timeout_seconds_including_setup": max_job_seconds,
        "assumed_vcpu_per_standard_ubuntu_job": STANDARD_RUNNER_VCPU,
        "assumed_clock_hz_ceiling_per_vcpu": ASSUMED_CLOCK_HZ,
        "all_job_cpu_core_cycle_capacity": str(capacity),
        "all_job_cpu_core_cycle_capacity_log2": math.log2(capacity),
        "below_2_61_under_stated_resource_assumptions": True,
        "verified_natural_relation_count": None,
        "complete_discrete_logarithm": None,
        "measured_complete_solve_operations": None,
        "one_target_online_wall_ms": None,
        "paired_rho_online_wall_ms": None,
        "limits": [
            "This is the entire planned 16-job search envelope, not observed CPU cycles or an instruction count.",
            "The field-call model includes completed regular-path native arithmetic at full planned shapes, not keying, Bloom, memory, disk, exceptional branches, setup, verification, or interrupted attempts.",
            "The cycle capacity assumes standard GitHub Ubuntu runners have four vCPUs and no vCPU exceeds an assumed 8 GHz; it is conditional on those assumptions and jobs staying within their six-hour timeout.",
            "The factor base was precomputed for reuse and is outside this wave's job capacity. Its cost must be included separately for cold-start accounting.",
            "A below-threshold planned capacity says nothing about relation yield or a completed DLP until a natural hit is independently verified.",
        ],
        "github_runner_specification":
            "https://docs.github.com/en/actions/reference/runners/github-hosted-runners",
        "plan_sha256": sha(PLAN),
        "holdout_target_sha256": sha(HOLDOUT),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in (
        "all_job_field_api_call_model_log2",
        "all_job_cpu_core_cycle_capacity_log2",
        "verified_natural_relation_count")}))


if __name__ == "__main__":
    main()
