#!/usr/bin/env python3
"""Reconcile the Q1090/Q1091 segments of one frozen n=83 target run.

The output preserves missing and interrupted Q1091 attempts. It does not
promote modeled field calls or a conditional CPU ceiling to measured solve
operations, and it emits no run-level measurement row while work is live.
"""

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE / "n83_q1090_terminal_wave_audit.json"
PLAN = HERE / "n83_q1091_holdout_m32_continuation_plan.json"
BUDGET = HERE / "n83_q1091_resource_budget.json"
CEILING = HERE / "n83_q1091_total_resource_ceiling.json"
RUN_ID = 37069216423
RUN_HEAD = "26fb34f3ae66ac6442245f24c4eb4c3552f9d328"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def aggregate(workflow_path, audit_dir):
    prior = load(PRIOR)
    plan = load(PLAN)
    budget = load(BUDGET)
    ceiling = load(CEILING)
    workflow = load(workflow_path)
    assert workflow["databaseId"] == RUN_ID
    assert workflow["headSha"] == RUN_HEAD
    assert len(workflow["jobs"]) == len(plan["query_starts"]) == 64
    assert plan["prior_Q1090_terminal_audit_sha256"] == sha(PRIOR)
    assert budget["prior_audit_sha256"] == sha(PRIOR)
    assert budget["continuation_plan_sha256"] == sha(PLAN)
    assert ceiling["resource_budget_sha256"] == sha(BUDGET)
    for row in (prior, budget, ceiling):
        assert row["curve_id"] == plan["curve_id"]
        assert row["isogeny"] == plan["isogeny"] == "none"
        assert row["candidate_id"] == plan["candidate_id"]
        assert row["workload_id"] == plan["workload_id"]
        assert row["run_id"] == plan["run_id"]
    assert prior["completed_jobs"] == 16
    assert prior["exact_hit_queries"] == 0
    assert prior["independently_verified_natural_relations"] == 0
    assert prior["query_end_exclusive"] == plan[
        "prior_completed_query_end_exclusive"]
    assert plan["query_starts"] == [
        (16 + i) * plan["query_representatives"] for i in range(64)]

    jobs = {}
    for job in workflow["jobs"]:
        match = re.fullmatch(r"physical-x86-holdout-wave \((\d+)\)",
                             job["name"])
        assert match is not None
        shard = int(match.group(1))
        assert 0 <= shard < 64 and shard not in jobs
        jobs[shard] = job
    assert set(jobs) == set(range(64))

    audits = {}
    for path in sorted(audit_dir.glob("*.json")):
        row = load(path)
        assert row["kind"] == "n83_holdout_artifact_audit"
        assert row["curve_id"] == plan["curve_id"]
        assert row["isogeny"] == "none"
        assert row["candidate_id"] == plan["candidate_id"]
        assert row["workload_id"] == plan["workload_id"]
        assert row["run_id"] == plan["run_id"]
        start = row["query_start"]
        assert start in plan["query_starts"] and start not in audits
        assert row["query_end_exclusive"] == start + plan[
            "query_representatives"]
        assert row["plan_sha256"] == sha(PLAN)
        audits[start] = (path, row)

    rows = []
    verified_scalars = set()
    verified_relations = 0
    control_verified_scalars = set()
    control_verified_relations = 0
    partial_full_replay_scalars = set()
    partial_full_replay_relations = 0
    credited_representatives = prior["total_query_representatives"]
    modeled_calls = int(prior["combined_full_and_control_field_api_call_model"])
    modeled_calls += (budget["local_bounded_controls_completed"] * int(
        budget["per_bounded_control_regular_path_field_api_call_model"]))
    terminal_jobs = 0
    failed_or_canceled = 0
    incomplete_terminal_artifacts = 0
    reported_unverified_hits = 0
    for shard in range(64):
        job = jobs[shard]
        start = plan["query_starts"][shard]
        item = audits.get(start)
        audit = item[1] if item else None
        terminal = job["status"] == "completed"
        if terminal:
            terminal_jobs += 1
        if terminal and job["conclusion"] != "success":
            failed_or_canceled += 1
        complete_audit = bool(audit and audit["terminal_status"] in (
            "completed_verified_hit", "completed_control_verified_hit",
            "completed_independently_verified_zero"))
        if audit and not complete_audit:
            partial_count = audit.get(
                "partial_full_sage_verified_relations", 0)
            reported_unverified_hits += max(0, (audit.get(
                "reported_full_exact_hit_queries") or 0) - partial_count)
            partial_full_replay_relations += partial_count
            partial_full_replay_scalars.update(audit.get(
                "partial_full_sage_verified_scalars", []))
            control_verified_relations += audit.get(
                "control_independently_verified_relations", 0)
            control_verified_scalars.update(audit.get(
                "control_verified_scalars", []))
        if terminal and job["conclusion"] == "success" and not complete_audit:
            incomplete_terminal_artifacts += 1
        # A complete independently audited receipt proves coverage even if
        # the CI wrapper later failed during packaging or artifact upload.
        credited = bool(terminal and complete_audit)
        if credited:
            assert audit["coverage_credit"] == plan["query_representatives"]
            credited_representatives += audit["coverage_credit"]
            modeled_calls += int(audit[
                "native_regular_path_field_api_call_model"])
            modeled_calls += int(audit[
                "control_regular_path_field_api_call_model"])
            verified_relations += audit["independently_verified_relations"]
            verified_scalars.update(audit["verified_scalars"])
            control_verified_relations += audit.get(
                "control_independently_verified_relations", 0)
            control_verified_scalars.update(audit.get(
                "control_verified_scalars", []))
        rows.append({
            "shard": shard,
            "query_start": start,
            "query_end_exclusive": start + plan["query_representatives"],
            "github_job_id": job["databaseId"],
            "github_status": job["status"],
            "github_conclusion": job["conclusion"],
            "artifact_audit_status": audit["terminal_status"] if audit else
                None,
            "artifact_audit_sha256": sha(item[0]) if item else None,
            "coverage_credit": plan["query_representatives"] if credited
                else 0,
            "actual_work_for_unfinished_attempt": None,
        })
    assert len(verified_scalars) <= 1, "conflicting target scalars"
    assert len(control_verified_scalars) <= 1, "conflicting control scalars"
    assert len(partial_full_replay_scalars) <= 1, (
        "conflicting partial full-replay scalars")
    if verified_scalars and control_verified_scalars:
        assert verified_scalars == control_verified_scalars, (
            "candidate and control recovered different scalars")
    if verified_scalars and partial_full_replay_scalars:
        assert verified_scalars == partial_full_replay_scalars, (
            "complete and partial full replays recovered different scalars")
    all_jobs_terminal = terminal_jobs == 64
    final_audits_ready = (workflow["status"] == "completed" and
                          all_jobs_terminal and
                          incomplete_terminal_artifacts == 0)
    measurement_row = None
    if final_audits_ready:
        measurement_row = {
            "candidate_id": plan["candidate_id"],
            "workload_id": plan["workload_id"],
            "run_id": plan["run_id"],
            "curve_id": plan["curve_id"],
            "isogeny": "none",
            "target_count": 1,
            "public_target": plan["public_target"],
            "status": "verified_dlp" if verified_scalars else
                "no_verified_dlp",
            "independently_verified_relation_count": verified_relations,
            "recovered_scalar": next(iter(verified_scalars), None),
            "control_verified_relation_count": control_verified_relations,
            "control_recovered_scalar": next(iter(control_verified_scalars),
                                                 None),
            "scheduled_ci_jobs": 80,
            "terminal_ci_job_records": 16 + terminal_jobs,
            "attempts_that_started_native_work": None,
            "failed_or_canceled_jobs": failed_or_canceled,
            "completed_receipts_field_api_call_model": str(modeled_calls),
            "incomplete_attempt_actual_work": None if (
                failed_or_canceled or incomplete_terminal_artifacts) else
                "none",
            "complete_calibrated_operations": None,
            "one_target_online_wall_ms": None,
            "paired_rho_online_wall_ms": None,
            "online_speedup": None,
        }
    report = {
        "kind": "n83_q1090_q1091_one_target_run_reconciliation",
        "scope": "one IC1 candidate, one workload, one run across two CI waves",
        "status": ("terminal_inventory_reconciled" if final_audits_ready else
                   "live_or_awaiting_artifact_audit"),
        "curve_id": plan["curve_id"],
        "isogeny": "none",
        "candidate_id": plan["candidate_id"],
        "workload_id": plan["workload_id"],
        "run_id": plan["run_id"],
        "actual_usable_points_B_before_folding": plan[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": plan["signed_frobenius_columns"],
        "prior_Q1090_completed_jobs": prior["completed_jobs"],
        "prior_Q1090_verified_relations": 0,
        "Q1091_terminal_jobs": terminal_jobs,
        "Q1091_failed_or_canceled_jobs": failed_or_canceled,
        "Q1091_success_jobs_missing_complete_audit":
            incomplete_terminal_artifacts,
        "Q1091_reported_unverified_hits_in_partial_artifacts":
            reported_unverified_hits,
        "Q1091_verified_relations": verified_relations,
        "verified_fresh_target_scalar": next(iter(verified_scalars), None),
        "Q1091_control_verified_relations": control_verified_relations,
        "control_verified_fresh_target_scalar": next(
            iter(control_verified_scalars), None),
        "Q1091_partial_full_sage_replay_relations":
            partial_full_replay_relations,
        "partial_full_sage_replay_scalar": next(
            iter(partial_full_replay_scalars), None),
        "credited_disjoint_query_representatives": credited_representatives,
        "completed_receipts_regular_path_field_api_call_model": str(
            modeled_calls),
        "completed_receipts_regular_path_field_api_call_model_log2":
            math.log2(modeled_calls),
        "incomplete_attempt_actual_work": None if (
            not all_jobs_terminal or failed_or_canceled or
            incomplete_terminal_artifacts) else "none",
        "conditional_whole_run_cpu_cycle_capacity_log2": ceiling[
            "whole_run_conditional_cycle_capacity_log2"],
        "measured_complete_solve_operations_log2": None,
        "one_target_online_wall_ms": None,
        "paired_rho_online_wall_ms": None,
        "run_level_measurement_row": measurement_row,
        "workflow_run_id": RUN_ID,
        "workflow_status": workflow["status"],
        "workflow_conclusion": workflow["conclusion"],
        "workflow_snapshot_sha256": sha(workflow_path),
        "prior_audit_sha256": sha(PRIOR),
        "continuation_plan_sha256": sha(PLAN),
        "resource_budget_sha256": sha(BUDGET),
        "whole_run_ceiling_sha256": sha(CEILING),
        "source_sha256": sha(Path(__file__)),
        "jobs": rows,
        "limits": [
            "Only terminal Q1091 jobs with complete independent artifact audits receive disjoint coverage credit, even if the CI wrapper subsequently failed.",
            "The M20/R14 control has no candidate ID. Its verified relations and scalar are reported separately and never credited to the M32/R29 IC1 candidate.",
            "A full-receipt hit replayed in Sage from a partial artifact is reported provisionally; it receives no candidate coverage or completed-run credit until the missing source-bound evidence is audited.",
            "Active, failed, canceled, and missing-artifact attempts remain visible; their actual consumed field work is unknown unless separately recovered.",
            "The field-call sum is a regular-path shape model for completed receipts, plus two local bounded controls. It excludes non-field work and is not a complete-solve operation count.",
            "The CPU figure is a conditional physical capacity under the frozen host, clock, timeout, and local-reserve assumptions.",
            "The primary one-target online interval and same-point rho baseline remain unmeasured; no speedup claim follows from this reconciliation.",
        ],
    }
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow-run", type=Path, required=True)
    parser.add_argument("--artifact-audits", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), "refusing to overwrite run reconciliation"
    result = aggregate(args.workflow_run, args.artifact_audits)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in (
        "status", "Q1091_terminal_jobs", "Q1091_verified_relations",
        "verified_fresh_target_scalar",
        "credited_disjoint_query_representatives")}))


if __name__ == "__main__":
    main()
