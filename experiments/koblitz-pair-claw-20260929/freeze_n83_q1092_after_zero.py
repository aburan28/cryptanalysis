#!/usr/bin/env python3
"""Freeze same-candidate Q1092 ranges only after an audited Q1091 zero wave.

This writes a source-bound plan. It does not create or dispatch a workflow.
"""

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

from aggregate_n83_holdout_run import aggregate

HERE = Path(__file__).resolve().parent
Q1091 = HERE / "n83_q1091_holdout_m32_continuation_plan.json"
DESIGN = HERE / "n83_q1092_conditional_same_candidate_fallback.json"
PRIOR_JOBS = 80
ADDITIONAL_JOBS = 128


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def freeze(workflow_path, audit_dir):
    terminal = aggregate(workflow_path, audit_dir)
    prior = json.loads(Q1091.read_text())
    design = json.loads(DESIGN.read_text())
    reps = prior["query_representatives"]
    assert terminal["status"] == "terminal_inventory_reconciled", (
        "Q1091 must have a terminal independently audited result")
    assert terminal["workflow_status"] == "completed"
    assert terminal["workflow_conclusion"] == "success"
    assert terminal["Q1091_terminal_jobs"] == 64
    assert terminal["Q1091_failed_or_canceled_jobs"] == 0
    assert terminal["Q1091_success_jobs_missing_complete_audit"] == 0
    assert terminal["Q1091_reported_unverified_hits_in_partial_artifacts"] == 0
    assert terminal["Q1091_verified_relations"] == 0
    assert terminal["verified_fresh_target_scalar"] is None
    assert terminal["credited_disjoint_query_representatives"] == (
        PRIOR_JOBS * reps)
    row = terminal["run_level_measurement_row"]
    assert row is not None and row["status"] == "no_verified_dlp"
    assert row["independently_verified_relation_count"] == 0
    assert row["recovered_scalar"] is None
    assert all(job["github_status"] == "completed" and
               job["github_conclusion"] == "success" and
               job["artifact_audit_status"] ==
               "completed_independently_verified_zero" and
               job["coverage_credit"] == reps for job in terminal["jobs"])
    for key in ("curve_id", "candidate_id", "workload_id", "run_id",
                "actual_usable_points_B_before_folding",
                "signed_frobenius_columns"):
        assert terminal[key] == prior[key] == design[key]
    assert terminal["isogeny"] == prior["isogeny"] == design[
        "isogeny"] == "none"
    assert prior["candidate_manifest_sha256"] == design[
        "candidate_manifest_sha256"] == sha(HERE / prior[
            "candidate_manifest"])
    assert design["Q1091_plan_sha256"] == sha(Q1091)
    assert design["wave_proposal_id"] == "Q1092"
    assert design["prior_jobs_if_Q1091_terminal_zero"] == PRIOR_JOBS
    assert design["additional_conditional_jobs"] == ADDITIONAL_JOBS
    assert design["below_2_61_under_stated_resource_assumptions"]
    starts = design["additional_query_starts"]
    assert len(starts) == ADDITIONAL_JOBS
    assert starts == [(PRIOR_JOBS + i) * reps
                      for i in range(ADDITIONAL_JOBS)]
    assert starts[0] == prior["query_end_exclusive"]
    assert starts[-1] + reps == design["query_end_exclusive"]

    candidate = json.loads((HERE / prior["candidate_manifest"]).read_text())
    assert candidate["candidate_id"] == prior["candidate_id"]
    assert candidate["point_decomposition"][
        "table_descriptors_per_job"] == prior["table_descriptors"]
    assert candidate["point_decomposition"][
        "query_representatives_per_job"] == reps
    assert design["query_end_exclusive"] <= candidate[
        "point_decomposition"]["query_representative_schedule"]["domain"]

    plan = copy.deepcopy(prior)
    plan.update({
        "kind": "n83_q1092_fresh_holdout_source_bound_m32_r29_zero_fallback",
        "wave_proposal_id": "Q1092",
        "query_starts": starts,
        "query_end_exclusive": design["query_end_exclusive"],
        "prior_completed_query_end_exclusive": prior[
            "query_end_exclusive"],
        "prior_Q1091_terminal_reconciliation_sha256": canonical_sha(terminal),
        "prior_Q1091_workflow_run_sha256": sha(workflow_path),
        "prior_Q1091_artifact_audit_sha256": [
            job["artifact_audit_sha256"] for job in terminal["jobs"]],
        "prior_Q1091_plan_sha256": sha(Q1091),
        "Q1092_design_screen_sha256": sha(DESIGN),
        "modeled_native_field_calls_added_jobs_log2": math.log2(
            ADDITIONAL_JOBS * int(prior[
                "modeled_native_field_calls_per_job"])),
        "modeled_native_field_calls_cumulative_208_jobs_log2": math.log2(
            (PRIOR_JOBS + ADDITIONAL_JOBS) * int(prior[
                "modeled_native_field_calls_per_job"])),
        "measured_prior_wave_natural_relations": 0,
        "source_sha256": sha(Path(__file__)),
        "limits": [
            "All 64 Q1091 jobs completed successfully and each disjoint full receipt passed independent zero-hit audit before this plan was frozen.",
            "The Q1092 rectangles preserve the exact curve, factor base, candidate, workload, one target, M32/R29 method, and run ID.",
            "The additional ranges do not overlap the 80 audited Q1090/Q1091 rectangles and remain inside the candidate's representative domain.",
            "The field-call figures model regular-path shape, not a calibrated complete solve.",
            "This file freezes ranges only; a separately reviewed workflow and resource budget are required before dispatch.",
        ],
    })
    assert plan["status"] == "ready_for_dispatch"
    assert plan["proposal_id"] == "Q1090"  # frozen raw runner label
    assert plan["candidate_id"] == design["candidate_id"]
    assert plan["run_id"] == design["run_id"]
    return plan


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow-run", type=Path, required=True)
    parser.add_argument("--artifact-audits", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), "refusing to overwrite frozen plan"
    plan = freeze(args.workflow_run, args.artifact_audits)
    args.out.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"candidate_id": plan["candidate_id"],
                      "run_id": plan["run_id"],
                      "additional_ranges": len(plan["query_starts"]),
                      "query_end_exclusive": plan["query_end_exclusive"]}))


if __name__ == "__main__":
    main()
