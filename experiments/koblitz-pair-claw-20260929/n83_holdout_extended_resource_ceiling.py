#!/usr/bin/env python3
"""Supersede the n83 holdout capacity screen with explicit base-build charge.

The output is a conditional CPU capacity ceiling, not measured instructions,
field operations, a relation, or a complete discrete-logarithm solve.
"""

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE / "n83_holdout_revised_30day_resource_ceiling.json"
BUDGET = HERE / "n83_q1091_resource_budget.json"
DESIGN = HERE / "n83_q1092_conditional_same_candidate_fallback.json"
BASE = HERE / "runs/n83_knownlog_orbit_base_k48194.json"
HOST = HERE / "runs/n83_local_resource_host_audit_20261001.json"
PLANS = (
    HERE / "n83_q1093_local_arm_m32_r30_plan.json",
    HERE / "n83_q1093_second_local_arm_m32_r30_plan.json",
)
START = datetime(2026, 8, 1, tzinfo=timezone.utc)
END = datetime(2026, 10, 29, tzinfo=timezone.utc)
ASSUMED_HZ = 8_000_000_000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def build():
    old, budget, design, base, host = map(load, (OLD, BUDGET, DESIGN, BASE, HOST))
    plans = [load(path) for path in PLANS]
    identity = ("curve_id", "workload_id", "isogeny",
                "actual_usable_points_B_before_folding",
                "signed_frobenius_columns")
    for row in (budget, design, *plans):
        assert all(row[key] == old[key] for key in identity), row.get("kind")
    assert all(row["candidate_id"] == old["candidate_id"] and
               row["run_id"] == old["run_id"] for row in (budget, design))
    assert plans[0]["candidate_id"] == plans[1]["candidate_id"]
    assert plans[0]["run_id"] == plans[1]["run_id"]
    assert plans[0]["candidate_id"] != old["candidate_id"]
    assert all(row["factor_base_enumerated_set_sha256"] ==
               old["factor_base_enumerated_set_sha256"]
               for row in (design, *plans))
    assert base["curve_id"] == old["curve_id"]
    assert base["isogeny"] == old["isogeny"] == "none"
    assert base["factor_base"]["enumerated_set_sha256"] == old[
        "factor_base_enumerated_set_sha256"]
    assert base["factor_base"]["actual_usable_points_B_before_folding"] == old[
        "actual_usable_points_B_before_folding"]
    assert base["factor_base"]["signed_frobenius_columns"] == old[
        "signed_frobenius_columns"]
    assert host["physical_core_count"] == old["local_host_physical_cores"] == 14
    assert old["assumed_clock_hz_ceiling_per_core"] == ASSUMED_HZ
    assert budget["assumed_clock_hz_ceiling_per_vcpu"] == ASSUMED_HZ
    assert budget["assumed_vcpu_per_standard_ubuntu_job"] == 4
    assert budget["all_80_job_timeout_seconds_per_job_including_setup"] == 21600
    assert old["q1090_q1091_scheduled_ci_jobs"] == 80
    assert old["q1090_q1091_q1092_conditional_ci_jobs"] == 208
    assert design["prior_jobs_if_Q1091_terminal_zero"] == 80
    assert design["additional_conditional_jobs"] == 128
    assert (END - START).days == 89
    assert datetime.fromisoformat(old["local_reserve_start_utc"]) >= START
    assert datetime.fromisoformat(old["local_reserve_end_utc"]) == END

    # The base receipt lacks a start timestamp. Charge its measured loop again
    # outside the continuous reserve; overlap only makes this ceiling looser.
    base_ns = base["target_independent_base_build_wall_ns"]
    assert isinstance(base_ns, int) and base_ns > 0
    base_extra_seconds = (base_ns + 1_000_000_000 - 1) // 1_000_000_000
    local_seconds = int((END - START).total_seconds())
    local_cycles = local_seconds * 14 * ASSUMED_HZ
    base_extra_cycles = base_extra_seconds * 14 * ASSUMED_HZ
    ci_job_cycles = 21600 * 4 * ASSUMED_HZ
    totals = {str(jobs): local_cycles + base_extra_cycles +
              jobs * ci_job_cycles for jobs in (80, 208)}
    assert int(old["per_ci_job_full_timeout_cycle_capacity"]) == ci_job_cycles
    assert int(old["q1090_q1091_full_timeout_ci_cycle_capacity"]) == 80 * ci_job_cycles
    assert int(old["q1090_q1091_q1092_full_timeout_ci_cycle_capacity"]) == 208 * ci_job_cycles
    assert all(value < 1 << 61 for value in totals.values())

    return {
        "kind": "n83_holdout_extended_continuous_local_cpu_resource_ceiling",
        "status": "conditional_capacity_not_a_measured_solve",
        "curve_id": old["curve_id"],
        "field_degree_n": 83,
        "isogeny": "none",
        "factor_base_enumerated_set_sha256": old["factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": old[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": old["signed_frobenius_columns"],
        "workload_id": old["workload_id"],
        "candidate_ids": [old["candidate_id"], plans[0]["candidate_id"]],
        "run_ids": [old["run_id"], plans[0]["run_id"]],
        "local_reserve_start_utc": START.isoformat(),
        "local_reserve_end_utc": END.isoformat(),
        "local_reserve_days": 89,
        "local_reserve_seconds": local_seconds,
        "local_host_physical_cores": 14,
        "assumed_clock_hz_ceiling_per_core_or_vcpu": ASSUMED_HZ,
        "local_reserved_cycle_capacity": str(local_cycles),
        "base_build_measured_wall_ns": base_ns,
        "base_build_extra_charged_seconds": base_extra_seconds,
        "base_build_extra_cycle_capacity": str(base_extra_cycles),
        "base_build_may_be_double_charged": True,
        "ci_job_full_timeout_seconds": 21600,
        "ci_job_vcpu_count": 4,
        "per_ci_job_full_timeout_cycle_capacity": str(ci_job_cycles),
        "scenarios": {
            jobs: {
                "scheduled_ci_jobs": int(jobs),
                "ci_full_timeout_cycle_capacity": str(int(jobs) * ci_job_cycles),
                "total_conditional_cycle_capacity": str(total),
                "total_conditional_cycle_capacity_log2": math.log2(total),
                "below_2_61_under_stated_resource_assumptions": True,
            } for jobs, total in totals.items()
        },
        "verified_fresh_target_discrete_logarithm": None,
        "measured_complete_solve_operations_log2": None,
        "one_target_online_wall_ms": None,
        "paired_rho_online_wall_ms": None,
        "source_sha256": sha(Path(__file__)),
        "input_sha256": {path.name: sha(path) for path in
                         (OLD, BUDGET, DESIGN, BASE, HOST, *PLANS)},
        "conditions": [
            "All local work associated with the fresh n83 target other than the separately charged base-build loop occurs on the audited 14-core host from 2026-08-01 00:00 UTC to 2026-10-29 00:00 UTC; charge any work outside this interval separately.",
            "The measured 129.525-second base-build loop is charged again even if it ran inside the local reserve; any other work before 2026-08-01 must be added.",
            "Each of the 80 scheduled CI jobs, or all 208 jobs if Q1092 is dispatched, is charged six full hours on four vCPUs, including failures and controls; supersede for a longer job or an additional host.",
            "The 8 GHz rate is an assumed CPU cycle-capacity ceiling, not a measured cycle count, instruction count, or field-operation calibration.",
            "A natural relation and independently verified fresh-target scalar, plus a complete attempt and phase ledger, are required before this conditional bound can describe a successful solve.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), "refusing to overwrite resource ceiling"
    report = build()
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({jobs: row["total_conditional_cycle_capacity_log2"]
                      for jobs, row in report["scenarios"].items()}))


if __name__ == "__main__":
    main()
