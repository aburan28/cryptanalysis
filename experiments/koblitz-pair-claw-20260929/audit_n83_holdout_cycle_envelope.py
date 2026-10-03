#!/usr/bin/env python3
"""Bound physical CPU cycles for the Q1090/Q1091 one-target run.

Every scheduled CI job is charged at least its full six-hour limit, including
queued, failed, and canceled jobs. A longer observed terminal wall interval
is charged instead. The local host gets its full 24-hour reserve. This is a
conditional hardware-capacity bound, not a measured field-operation count.
"""

import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

from aggregate_n83_holdout_run import aggregate

HERE = Path(__file__).resolve().parent
Q1090_ARCHIVE = HERE / "runs/q1090_raw_ci_36891418377"
Q1090_WORKFLOW = Q1090_ARCHIVE / "workflow_run.json"
Q1090_AUDIT = HERE / "n83_q1090_terminal_wave_audit.json"
Q1091_PLAN = HERE / "n83_q1091_holdout_m32_continuation_plan.json"
RESOURCE = HERE / "n83_q1091_resource_budget.json"
CEILING = HERE / "n83_q1091_total_resource_ceiling.json"
ASSUMED_CLOCK_HZ = 8_000_000_000
LOCAL_SECONDS = 24 * 3600
LOCAL_CORES = 14
CI_VCPU = 4


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def parse_utc(value):
    if not value or value.startswith("0001-"):
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def charged_job_seconds(job, minimum_seconds):
    start = parse_utc(job.get("startedAt"))
    end = parse_utc(job.get("completedAt"))
    observed = None
    if start and end:
        observed = max(0.0, (end - start).total_seconds())
    return max(minimum_seconds, observed or 0.0), observed


def audit(workflow_path, artifact_audits):
    prior_workflow = load(Q1090_WORKFLOW)
    prior_audit = load(Q1090_AUDIT)
    workflow = load(workflow_path)
    plan = load(Q1091_PLAN)
    resource = load(RESOURCE)
    ceiling = load(CEILING)
    reconciliation = aggregate(workflow_path, artifact_audits)
    assert prior_audit["workflow_run_sha256"] == sha(Q1090_WORKFLOW)
    assert prior_workflow["status"] == "completed"
    assert prior_workflow["conclusion"] == "success"
    assert len(prior_workflow["jobs"]) == prior_audit["completed_jobs"] == 16
    assert all(job["status"] == "completed" and job["conclusion"] ==
               "success" for job in prior_workflow["jobs"])
    assert len(workflow["jobs"]) == 64
    assert plan["timeout_seconds_per_job"] == resource[
        "all_80_job_timeout_seconds_per_job_including_setup"] == 21600
    assert resource["assumed_vcpu_per_standard_ubuntu_job"] == CI_VCPU
    assert resource["assumed_clock_hz_ceiling_per_vcpu"] == ceiling[
        "assumed_clock_hz_ceiling_per_core"] == ASSUMED_CLOCK_HZ
    assert ceiling["local_reserve_seconds_including_base_controls_and_replay"] == (
        LOCAL_SECONDS)
    assert ceiling["local_host_physical_cores"] == LOCAL_CORES
    assert ceiling["resource_budget_sha256"] == sha(RESOURCE)
    for row in (prior_audit, plan, resource, ceiling, reconciliation):
        assert row["curve_id"] == plan["curve_id"]
        assert row["isogeny"] == "none"
        assert row["candidate_id"] == plan["candidate_id"]
        assert row["workload_id"] == plan["workload_id"]
        assert row["run_id"] == plan["run_id"]
    assert reconciliation["workflow_run_id"] == workflow["databaseId"]
    assert reconciliation["workflow_snapshot_sha256"] == sha(workflow_path)
    jobs = []
    charged_seconds = 0.0
    observed_seconds = 0.0
    for wave, inventory in (("Q1090", prior_workflow), ("Q1091", workflow)):
        for job in inventory["jobs"]:
            charged, observed = charged_job_seconds(
                job, plan["timeout_seconds_per_job"])
            charged_seconds += charged
            observed_seconds += observed or 0.0
            jobs.append({
                "wave": wave,
                "github_job_id": job["databaseId"],
                "github_status": job["status"],
                "github_conclusion": job["conclusion"],
                "observed_job_wall_seconds": observed,
                "charged_job_wall_seconds": charged,
            })
    assert len(jobs) == 80
    ci_cycles = math.ceil(charged_seconds * CI_VCPU * ASSUMED_CLOCK_HZ)
    local_cycles = LOCAL_SECONDS * LOCAL_CORES * ASSUMED_CLOCK_HZ
    total_cycles = ci_cycles + local_cycles
    assert total_cycles >= int(ceiling["whole_run_conditional_cycle_capacity"])
    verified_scalar = reconciliation["verified_fresh_target_scalar"]
    terminal = reconciliation["status"] == "terminal_inventory_reconciled"
    if verified_scalar is not None:
        assert reconciliation["Q1091_verified_relations"] > 0
    result = {
        "kind": "n83_q1090_q1091_one_target_conditional_cpu_cycle_envelope",
        "status": ("verified_dlp_conditional_cycle_envelope" if terminal and
                   verified_scalar is not None else
                   "terminal_no_verified_dlp" if terminal else
                   "live_capacity_only"),
        "curve_id": plan["curve_id"],
        "isogeny": "none",
        "candidate_id": plan["candidate_id"],
        "workload_id": plan["workload_id"],
        "run_id": plan["run_id"],
        "verified_fresh_target_scalar": verified_scalar,
        "independently_verified_relation_count": reconciliation[
            "Q1091_verified_relations"],
        "scheduled_ci_jobs_charged": len(jobs),
        "observed_terminal_ci_job_wall_seconds_sum": observed_seconds,
        "charged_ci_job_wall_seconds_sum": charged_seconds,
        "assumed_vcpu_per_ci_job": CI_VCPU,
        "assumed_clock_hz_ceiling_per_vcpu": ASSUMED_CLOCK_HZ,
        "ci_job_cycle_envelope": str(ci_cycles),
        "local_host_physical_cores": LOCAL_CORES,
        "local_reserved_seconds_including_base_controls_and_replay":
            LOCAL_SECONDS,
        "local_reserved_cycle_capacity": str(local_cycles),
        "whole_run_conditional_cycle_envelope": str(total_cycles),
        "whole_run_conditional_cycle_envelope_log2": math.log2(total_cycles),
        "below_2_61_under_stated_resource_assumptions": total_cycles < 1 << 61,
        "measured_complete_field_operations_log2": None,
        "one_target_online_wall_ms": reconciliation["one_target_online_wall_ms"],
        "paired_rho_online_wall_ms": reconciliation["paired_rho_online_wall_ms"],
        "Q1090_workflow_run_sha256": sha(Q1090_WORKFLOW),
        "Q1090_terminal_audit_sha256": sha(Q1090_AUDIT),
        "Q1091_workflow_run_sha256": sha(workflow_path),
        "Q1091_plan_sha256": sha(Q1091_PLAN),
        "Q1091_resource_budget_sha256": sha(RESOURCE),
        "whole_run_ceiling_sha256": sha(CEILING),
        "reconciliation_source_sha256": reconciliation["source_sha256"],
        "source_sha256": sha(Path(__file__)),
        "limits": [
            "Every one of the 80 scheduled CI jobs is charged at least its full six-hour limit, including queued, failed, and canceled jobs; longer observed terminal job walls supersede that limit.",
            "The 8 GHz per-vCPU figure is an assumed ceiling, not a measured clock or an equivalence to field operations.",
            "The local 24-hour, 14-core reserve is conditional on all local work for this workload remaining within that reservation.",
            "A CPU-cycle capacity below 2^61 is not a successful-solve result until a fresh scalar is independently verified and the complete terminal inventory is reconciled.",
            "No same-point rho online comparison or calibrated complete field-operation total is inferred from this capacity envelope.",
        ],
        "jobs": jobs,
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow-run", type=Path, required=True)
    parser.add_argument("--artifact-audits", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), "refusing to overwrite resource envelope"
    result = audit(args.workflow_run, args.artifact_audits)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in (
        "status", "verified_fresh_target_scalar",
        "whole_run_conditional_cycle_envelope_log2",
        "below_2_61_under_stated_resource_assumptions")}))


if __name__ == "__main__":
    main()
