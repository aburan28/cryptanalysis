#!/usr/bin/env python3
"""Correct the holdout resource ceiling after the 24-hour local window failed.

The frozen 24-hour artifact is retained for provenance. This replacement
charges a continuous 30-day, 14-core local window as well as full-timeout CI
jobs. It remains conditional hardware capacity, not measured solve work.
"""

import argparse
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE / "n83_q1091_total_resource_ceiling.json"
BUDGET = HERE / "n83_q1091_resource_budget.json"
DESIGN = HERE / "n83_q1092_conditional_same_candidate_fallback.json"
FIRST = HERE / "runs/n83_holdout_q1090_smoke_M20_R14.json"
SECOND = HERE / "runs/n83_q1091_first_range_smoke_M20_R14.json"
START = datetime(2026, 9, 29, tzinfo=timezone.utc)
DAYS = 30
LOCAL_CORES = 14
ASSUMED_HZ = 8_000_000_000
CI_JOBS_Q1091 = 80
CI_JOBS_Q1092 = 208


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def build():
    old, budget, design = load(OLD), load(BUDGET), load(DESIGN)
    first, second = load(FIRST), load(SECOND)
    for row in (budget, design):
        for key in ("curve_id", "candidate_id", "workload_id", "run_id",
                    "isogeny"):
            assert row[key] == old[key], key
    assert old["isogeny"] == "none"
    assert old["local_host_physical_cores"] == LOCAL_CORES
    assert old["assumed_clock_hz_ceiling_per_core"] == ASSUMED_HZ
    assert old["local_reserve_seconds_including_base_controls_and_replay"] == 86400
    assert old["local_control_receipt_sha256"] == [sha(FIRST), sha(SECOND)]
    assert budget["assumed_clock_hz_ceiling_per_vcpu"] == ASSUMED_HZ
    assert budget["assumed_vcpu_per_standard_ubuntu_job"] == 4
    assert budget["all_80_job_timeout_seconds_per_job_including_setup"] == 21600
    assert budget["all_80_job_cpu_core_cycle_capacity"] == old[
        "all_80_ci_job_cycle_capacity"]
    assert design["prior_jobs_if_Q1091_terminal_zero"] == CI_JOBS_Q1091
    assert design["additional_conditional_jobs"] == (
        CI_JOBS_Q1092 - CI_JOBS_Q1091)
    assert first["curve_id"] == second["curve_id"] == old["curve_id"]
    assert first["workload_id"] == second["workload_id"] == old["workload_id"]
    first_start = datetime.fromisoformat(first["started_at_utc"])
    second_finish = datetime.fromisoformat(second["finished_at_utc"])
    observed_span = (second_finish - first_start).total_seconds()
    assert observed_span > 86400, "the historical 24-hour gap is not observed"
    end = START + timedelta(days=DAYS)
    assert START <= first_start < second_finish < end

    local_seconds = DAYS * 24 * 3600
    local_cycles = local_seconds * LOCAL_CORES * ASSUMED_HZ
    per_ci_job_cycles = 21600 * 4 * ASSUMED_HZ
    q1091_ci_cycles = CI_JOBS_Q1091 * per_ci_job_cycles
    q1092_ci_cycles = CI_JOBS_Q1092 * per_ci_job_cycles
    assert q1091_ci_cycles == int(old["all_80_ci_job_cycle_capacity"])
    assert q1092_ci_cycles.bit_length() < 61
    q1091_total = local_cycles + q1091_ci_cycles
    q1092_total = local_cycles + q1092_ci_cycles
    assert q1091_total < 1 << 61 and q1092_total < 1 << 61
    return {
        "kind": "n83_holdout_revised_continuous_local_window_cpu_resource_ceiling",
        "status": "conditional_capacity_not_a_measured_solve",
        "curve_id": old["curve_id"],
        "candidate_id": old["candidate_id"],
        "workload_id": old["workload_id"],
        "run_id": old["run_id"],
        "isogeny": "none",
        "factor_base_enumerated_set_sha256": design[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": old[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": old["signed_frobenius_columns"],
        "legacy_24_hour_ceiling_sha256": sha(OLD),
        "legacy_24_hour_condition_refuted_by_controls": True,
        "first_local_control_start_utc": first_start.isoformat(),
        "second_local_control_finish_utc": second_finish.isoformat(),
        "observed_control_span_seconds": observed_span,
        "old_local_reserve_seconds": 86400,
        "local_reserve_start_utc": START.isoformat(),
        "local_reserve_end_utc": end.isoformat(),
        "local_reserve_seconds": local_seconds,
        "local_host_physical_cores": LOCAL_CORES,
        "assumed_clock_hz_ceiling_per_core": ASSUMED_HZ,
        "local_reserved_cycle_capacity": str(local_cycles),
        "local_reserved_cycle_capacity_log2": math.log2(local_cycles),
        "per_ci_job_full_timeout_cycle_capacity": str(per_ci_job_cycles),
        "q1090_q1091_scheduled_ci_jobs": CI_JOBS_Q1091,
        "q1090_q1091_full_timeout_ci_cycle_capacity": str(q1091_ci_cycles),
        "q1090_q1091_plus_local_cycle_capacity": str(q1091_total),
        "q1090_q1091_plus_local_cycle_capacity_log2": math.log2(q1091_total),
        "q1090_q1091_q1092_conditional_ci_jobs": CI_JOBS_Q1092,
        "q1090_q1091_q1092_full_timeout_ci_cycle_capacity": str(
            q1092_ci_cycles),
        "q1090_q1091_q1092_plus_local_cycle_capacity": str(q1092_total),
        "q1090_q1091_q1092_plus_local_cycle_capacity_log2": math.log2(
            q1092_total),
        "below_2_61_under_stated_resource_assumptions": True,
        "verified_fresh_target_discrete_logarithm": None,
        "measured_complete_solve_operations_log2": None,
        "prior_budget_sha256": sha(BUDGET),
        "Q1092_design_sha256": sha(DESIGN),
        "local_control_receipt_sha256": [sha(FIRST), sha(SECOND)],
        "source_sha256": sha(Path(__file__)),
        "conditions": [
            "All local computation for this holdout, including fixture construction, base construction, local controls, artifact intake, independent replay, and future Q1092 work, occurs within the declared 30-day interval on the audited 14-core host.",
            "All scheduled CI jobs, including failed, canceled, and queued jobs, are charged six full hours on four vCPUs; any observed job longer than six hours must supersede this ceiling.",
            "The 8 GHz per-core and per-vCPU rate is an assumed capacity ceiling, not a measured clock or a calibration to field operations.",
            "Any additional host or computation outside the declared interval must be added before a below-2^61 work claim.",
            "A natural relation, fresh scalar, and independently verified complete DLP are still required for a successful-solve claim.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), "refusing to overwrite revised ceiling"
    result = build()
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in (
        "observed_control_span_seconds",
        "q1090_q1091_plus_local_cycle_capacity_log2",
        "q1090_q1091_q1092_plus_local_cycle_capacity_log2",
        "below_2_61_under_stated_resource_assumptions")}))


if __name__ == "__main__":
    main()
