#!/usr/bin/env python3
"""Set a conditional whole-run CPU resource ceiling for the fresh holdout.

This is a capacity bound under explicit host, clock, and local-time caps.
It becomes a complete-solve bound only after a verified hit and an audit of
every target-dependent attempt on this one workload.
"""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUDGET = HERE / "n83_q1091_resource_budget.json"
BASE = HERE / "runs/n83_knownlog_orbit_base_k48194.json"
HOST = HERE / "runs/n83_local_resource_host_audit_20261001.json"
Q1090_CONTROL = HERE / "runs/n83_holdout_q1090_smoke_M20_R14.json"
Q1091_CONTROL = HERE / "runs/n83_q1091_first_range_smoke_M20_R14.json"
OUTPUT = HERE / "n83_q1091_total_resource_ceiling.json"
LOCAL_RESERVE_SECONDS = 24 * 3600
ASSUMED_CLOCK_HZ = 8_000_000_000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    budget = json.loads(BUDGET.read_text())
    base = json.loads(BASE.read_text())
    host = json.loads(HOST.read_text())
    controls = [json.loads(path.read_text()) for path in
                (Q1090_CONTROL, Q1091_CONTROL)]
    assert budget["run_id"] == (budget["candidate_id"] + "W" +
                                budget["workload_id"] + "R1")
    assert budget["curve_id"] == base["curve_id"]
    assert budget["isogeny"] == base["isogeny"] == "none"
    assert budget["actual_usable_points_B_before_folding"] == base[
        "factor_base"]["actual_usable_points_B_before_folding"]
    assert budget["signed_frobenius_columns"] == base[
        "factor_base"]["signed_frobenius_columns"]
    assert base["factor_base"]["unknown_log_columns"] == 0
    assert budget["local_control_receipt_sha256"] == [
        sha(path) for path in (Q1090_CONTROL, Q1091_CONTROL)]
    assert all(control["workload_id"] == budget["workload_id"] and
               control["curve_id"] == budget["curve_id"] and
               control["native_result"]["exact_hit_queries"] == 0
               for control in controls)
    assert host["architecture"] == "arm64"
    assert host["physical_core_count"] == 14
    base_seconds = base["target_independent_base_build_wall_ns"] / 1e9
    control_seconds = sum(control["wrapper_subprocess_wall_seconds"]
                          for control in controls)
    assert base_seconds + control_seconds < LOCAL_RESERVE_SECONDS
    ci_capacity = int(budget["all_80_job_cpu_core_cycle_capacity"])
    expected_ci_capacity = (
        (budget["prior_completed_jobs"] + budget["new_planned_jobs"]) *
        budget["all_80_job_timeout_seconds_per_job_including_setup"] *
        budget["assumed_vcpu_per_standard_ubuntu_job"] *
        ASSUMED_CLOCK_HZ)
    assert ci_capacity == expected_ci_capacity
    local_capacity = (LOCAL_RESERVE_SECONDS * host["physical_core_count"] *
                      ASSUMED_CLOCK_HZ)
    total_capacity = ci_capacity + local_capacity
    assert total_capacity < 1 << 61
    report = {
        "kind": "n83_q1091_conditional_whole_run_cpu_resource_ceiling",
        "scope": "one fresh target; Q1090 plus Q1091 CI jobs and all associated local computation within one reserved host window",
        "status": "conditional_capacity_not_a_measured_solve",
        "curve_id": budget["curve_id"],
        "isogeny": "none",
        "candidate_id": budget["candidate_id"],
        "workload_id": budget["workload_id"],
        "run_id": budget["run_id"],
        "actual_usable_points_B_before_folding": budget[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": budget["signed_frobenius_columns"],
        "base_build_measured_wall_seconds": base_seconds,
        "two_local_controls_measured_wrapper_seconds": control_seconds,
        "local_host_physical_cores": host["physical_core_count"],
        "local_host_architecture": host["architecture"],
        "local_reserve_seconds_including_base_controls_and_replay":
            LOCAL_RESERVE_SECONDS,
        "assumed_clock_hz_ceiling_per_core": ASSUMED_CLOCK_HZ,
        "all_80_ci_job_cycle_capacity": str(ci_capacity),
        "all_80_ci_job_cycle_capacity_log2": math.log2(ci_capacity),
        "local_reserved_cycle_capacity": str(local_capacity),
        "local_reserved_cycle_capacity_log2": math.log2(local_capacity),
        "whole_run_conditional_cycle_capacity": str(total_capacity),
        "whole_run_conditional_cycle_capacity_log2": math.log2(
            total_capacity),
        "below_2_61_if_all_conditions_hold": True,
        "complete_discrete_logarithm": None,
        "measured_complete_solve_operations_log2": None,
        "one_target_online_wall_ms": None,
        "paired_rho_online_wall_ms": None,
        "resource_budget_sha256": sha(BUDGET),
        "base_build_receipt_sha256": sha(BASE),
        "local_host_audit_sha256": sha(HOST),
        "local_control_receipt_sha256": [
            sha(path) for path in (Q1090_CONTROL, Q1091_CONTROL)],
        "source_sha256": sha(Path(__file__)),
        "conditions": [
            "All 80 hosted CI jobs, including setup, bounded controls, failed attempts, and cleanup, fit their six-hour job limits on standard four-vCPU runners.",
            "All local computation associated with this workload, including fixture construction, the measured base build, both measured bounded controls, and future independent replay, together uses at most one 24-hour window on the audited 14-core host.",
            "No additional target-dependent attempt or host outside these two CI waves and the local reserve is used without being added to this ledger.",
            "The 8 GHz per-core value is an assumed physical ceiling, not a measured clock rate or calibrated field-operation equivalence.",
            "A fresh exact relation and discrete logarithm must still pass independent checked-Sage replay; until then this is not successful solve work.",
        ],
    }
    assert not OUTPUT.exists(), "refusing to overwrite ceiling"
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in (
        "whole_run_conditional_cycle_capacity_log2",
        "below_2_61_if_all_conditions_hold",
        "complete_discrete_logarithm")}))


if __name__ == "__main__":
    main()
