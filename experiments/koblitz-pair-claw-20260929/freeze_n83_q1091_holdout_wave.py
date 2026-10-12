#!/usr/bin/env python3
"""Freeze 64 disjoint continuation rectangles after Q1090's zero-hit audit."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR_PLAN = HERE / "n83_q1090_holdout_m32_wave_plan.json"
PRIOR_AUDIT = HERE / "n83_q1090_terminal_wave_audit.json"
TARGET = HERE / "n83_holdout_target_20261001.json"
OUTPUT = HERE / "n83_q1091_holdout_m32_continuation_plan.json"
ADDED_JOBS = 64
PRIOR_JOBS = 16


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    prior = json.loads(PRIOR_PLAN.read_text())
    audit = json.loads(PRIOR_AUDIT.read_text())
    target = json.loads(TARGET.read_text())
    assert prior["proposal_id"] == "Q1090"
    assert prior["status"] == "ready_for_dispatch"
    assert audit["raw_proposal_id"] == "Q1090"
    assert audit["proposal_id"] is None
    assert audit["completed_jobs"] == PRIOR_JOBS
    assert audit["failed_jobs"] == 0
    assert audit["exact_hit_queries"] == 0
    assert audit["independently_verified_natural_relations"] == 0
    assert audit["complete_discrete_logarithm"] is False
    assert audit["plan_sha256"] == sha(PRIOR_PLAN)
    assert audit["target_sha256"] == sha(TARGET)
    assert prior["candidate_id"] == audit["candidate_id"]
    assert prior["workload_id"] == audit["workload_id"] == target[
        "workload_id"]
    assert prior["run_id"] == audit["run_id"]
    assert prior["curve_id"] == audit["curve_id"] == target["curve_id"]
    assert prior["isogeny"] == audit["isogeny"] == "none"
    assert prior["public_target"] == target["public_target"]
    assert prior["factor_base_enumerated_set_sha256"] == audit[
        "factor_base_enumerated_set_sha256"]
    assert prior["actual_usable_points_B_before_folding"] == audit[
        "actual_usable_points_B_before_folding"] == 8000204
    assert prior["signed_frobenius_columns"] == audit[
        "signed_frobenius_columns"] == 48194
    assert prior["table_descriptors"] == 1 << 32
    assert prior["query_representatives"] == 1 << 29
    assert audit["query_end_exclusive"] == PRIOR_JOBS * (1 << 29)
    assert audit["total_query_representatives"] == PRIOR_JOBS * (1 << 29)
    assert len(audit["rows"]) == PRIOR_JOBS
    assert all(row["terminal_status"] == "completed_zero_exact_hits"
               for row in audit["rows"])
    assert all(row["independent_sage_audit_sha256"] for row in audit["rows"])
    assert prior["runner_source_sha256"] == sha(
        HERE / "run_n83_holdout_chunk.py")
    assert prior["candidate_manifest_sha256"] == sha(
        HERE / prior["candidate_manifest"])

    query_count = prior["query_representatives"]
    starts = [(PRIOR_JOBS + i) * query_count for i in range(ADDED_JOBS)]
    assert starts[0] == audit["query_end_exclusive"]
    assert starts[-1] + query_count <= math.comb(48194, 2) * 166
    per_job = int(prior["modeled_native_field_calls_per_job"])
    plan = dict(prior)
    plan.update({
        "kind": "n83_q1091_fresh_holdout_source_bound_m32_r29_continuation",
        "proposal_id": "Q1090",
        "wave_proposal_id": "Q1091",
        "status": "ready_for_dispatch",
        "query_starts": starts,
        "query_end_exclusive": starts[-1] + query_count,
        "prior_completed_query_end_exclusive": audit[
            "query_end_exclusive"],
        "prior_Q1090_plan_sha256": sha(PRIOR_PLAN),
        "prior_Q1090_terminal_audit_sha256": sha(PRIOR_AUDIT),
        "modeled_native_field_calls_added_jobs_log2": math.log2(
            ADDED_JOBS * per_job),
        "modeled_native_field_calls_cumulative_80_jobs_log2": math.log2(
            (PRIOR_JOBS + ADDED_JOBS) * per_job),
        "measured_prior_wave_natural_relations": 0,
        "measured_natural_relations": None,
        "measured_complete_solve_work_log2": None,
        "source_sha256": sha(Path(__file__)),
        "limits": [
            "Q1090's sixteen terminal disjoint rectangles had zero exact hits; all sixteen zero-hit claims passed checked-Sage audit.",
            "The Q1091 rectangles continue the same candidate, one frozen point, and run ID without reusing query representatives.",
            "The added and cumulative field-call figures are regular-path shape models, not calibrated end-to-end solve work.",
            "Any exact hit must be independently replayed in checked Sage before claiming a DLP.",
        ],
    })
    plan.pop("modeled_native_field_calls_sixteen_jobs_log2")
    assert not OUTPUT.exists(), "refusing to overwrite frozen Q1091 plan"
    OUTPUT.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"wave_proposal_id": "Q1091",
                      "candidate_id": plan["candidate_id"],
                      "run_id": plan["run_id"],
                      "added_jobs": ADDED_JOBS,
                      "cumulative_field_model_log2": plan[
                          "modeled_native_field_calls_cumulative_80_jobs_log2"]}))


if __name__ == "__main__":
    main()
