#!/usr/bin/env python3
"""Bind the fresh n83 Q1091 solve to the extended whole-work capacity.

The result requires a terminal source-bound CI inventory, every successful
Q1091 artifact's independent Sage audit, and the two terminal local Q1093
receipts. CPU cycles are an assumed capacity bound, not measured field work.
"""

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from audit_n83_holdout_cycle_envelope import audit as audit_ci
from aggregate_n83_holdout_run import aggregate
import watch_n83_q1093_local_result as first_watcher
import watch_n83_q1093_second_local_result as second_watcher

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
TARGET = HERE / "n83_holdout_target_20261001.json"
CAPACITY = HERE / "n83_holdout_extended_resource_ceiling.json"
Q1091_PLAN = HERE / "n83_q1091_holdout_m32_continuation_plan.json"
Q1092_PLAN = HERE / "n83_q1092_holdout_m32_continuation_plan.json"
LOCAL_PLANS = (
    HERE / "n83_q1093_local_arm_m32_r30_plan.json",
    HERE / "n83_q1093_second_local_arm_m32_r30_plan.json",
)
WATCHERS = (first_watcher, second_watcher)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def audit(workflow_path, artifact_audits, as_of=None, evidence_root=None):
    as_of = as_of or datetime.now(timezone.utc)
    assert as_of.tzinfo is not None and as_of.utcoffset().total_seconds() == 0
    ci = audit_ci(workflow_path, artifact_audits, as_of=as_of)
    assert ci["status"] == "verified_dlp_conditional_cycle_envelope"
    assert ci["scheduled_ci_jobs_charged"] == 80
    assert ci["observed_terminal_ci_jobs"] == 80
    assert ci["independently_verified_relation_count"] >= 1
    scalar = int(ci["verified_fresh_target_scalar"])
    reconciliation = aggregate(workflow_path, artifact_audits)
    assert reconciliation["status"] == "terminal_inventory_reconciled"
    assert reconciliation["Q1091_terminal_jobs"] == 64
    assert reconciliation["Q1091_success_jobs_missing_complete_audit"] == 0
    assert reconciliation["Q1091_reported_unverified_hits_in_partial_artifacts"] == 0
    assert reconciliation["Q1091_verified_relations"] == ci[
        "independently_verified_relation_count"]
    assert int(reconciliation["verified_fresh_target_scalar"]) == scalar
    successful = sum(row["github_conclusion"] == "success" for row in
                     reconciliation["jobs"])
    canceled = sum(row["github_conclusion"] == "cancelled" for row in
                   reconciliation["jobs"])
    assert successful == 56 and canceled == 8
    assert len(list(artifact_audits.glob("*.json"))) == successful

    target, capacity, plan = load(TARGET), load(CAPACITY), load(Q1091_PLAN)
    assert target["fixture_scalar_retained"] is False
    assert not Q1092_PLAN.exists(), (
        "Q1092 dispatch would require its own CI inventory")
    assert capacity["source_sha256"] == sha(
        HERE / "n83_holdout_extended_resource_ceiling.py")
    for name, digest in capacity["input_sha256"].items():
        path = HERE / name if (HERE / name).is_file() else RUNS / name
        assert path.is_file() and sha(path) == digest, name
    for key in ("curve_id", "workload_id", "isogeny",
                "factor_base_enumerated_set_sha256",
                "actual_usable_points_B_before_folding",
                "signed_frobenius_columns"):
        assert capacity[key] == plan[key] == target[key], key
    assert capacity["candidate_ids"][0] == ci["candidate_id"] == plan[
        "candidate_id"]
    assert capacity["run_ids"][0] == ci["run_id"] == plan["run_id"]
    assert target["public_target"] == plan["public_target"]
    assert capacity["scenarios"]["80"]["scheduled_ci_jobs"] == 80
    reserve_start, reserve_end = map(utc, (
        capacity["local_reserve_start_utc"],
        capacity["local_reserve_end_utc"]))
    assert reserve_start <= as_of < reserve_end

    local = []
    for index, (local_plan_path, watcher) in enumerate(zip(
            LOCAL_PLANS, WATCHERS)):
        local_plan = load(local_plan_path)
        if evidence_root is None:
            result_path, replay_path, runtime_path = (
                watcher.RESULT, watcher.AUDIT, watcher.RUNTIME)
            assert not watcher.STARTED.exists() and not watcher.FAILURE.exists()
            prefix = ("n83_q1093_m32_r30" if index == 0 else
                      "n83_q1093_second_m32_r30")
            binary_path = Path("/private/tmp") / (prefix + "_native")
            source_dir = Path("/private/tmp") / (prefix + "_sources")
        else:
            local_dir = evidence_root / "q1093" / (
                "first" if index == 0 else "second")
            result_path = local_dir / "receipt.json"
            replay_path = local_dir / "sage_verify.json"
            runtime_path = local_dir / "runtime_info.json"
            binary_path = local_dir / "native_binary"
            source_dir = local_dir / "sources"
        assert result_path.is_file() and replay_path.is_file()
        assert runtime_path.is_file() and binary_path.is_file()
        receipt, replay, runtime = map(load, (
            result_path, replay_path, runtime_path))
        assert runtime["status"] == "verified"
        assert local_plan["candidate_manifest_sha256"] == sha(
            HERE / local_plan["candidate_manifest"])
        original_result, original_runtime = watcher.RESULT, watcher.RUNTIME
        try:
            watcher.RESULT, watcher.RUNTIME = result_path, runtime_path
            watcher.check_result(local_plan, receipt)
            watcher.check_audit(local_plan, receipt, replay)
        finally:
            watcher.RESULT, watcher.RUNTIME = original_result, original_runtime
        for field, path in (
            ("compiled_binary_sha256", binary_path),
            ("native_source_sha256", source_dir / "alt_main.cpp"),
            ("bloom_core_sha256", source_dir / "alt_core.hpp"),
            ("native_pairs_sha256", source_dir / "alt_pairs.cpp"),
            ("generated_field_sha256", source_dir / "eccF83.h"),
        ):
            assert path.is_file() and receipt[field] == sha(path), field
        assert receipt["kind"] == (
            "n83_holdout_signed_x_query_k48194_exact_replay_chunk")
        assert local_plan["candidate_id"] == capacity["candidate_ids"][1]
        assert local_plan["run_id"] == capacity["run_ids"][1]
        assert local_plan["curve_id"] == ci["curve_id"]
        assert local_plan["workload_id"] == ci["workload_id"]
        assert local_plan["isogeny"] == "none"
        assert local_plan["public_target"] == target["public_target"]
        assert local_plan["factor_base_enumerated_set_sha256"] == capacity[
            "factor_base_enumerated_set_sha256"]
        assert reserve_start <= utc(receipt["started_at_utc"]) < reserve_end
        assert reserve_start <= utc(receipt["finished_at_utc"]) < reserve_end
        assert all(row["scalar_replay"] and row["four_point_sum"]
                   for row in replay["verified_relations"])
        assert {int(row["recovered_scalar"]) for row in replay[
            "verified_relations"]} <= {scalar}
        local.append({
            "candidate_id": local_plan["candidate_id"],
            "run_id": local_plan["run_id"],
            "query_start": receipt["query_start"],
            "query_representatives": receipt["query_representatives"],
            "verified_natural_relations": replay["verified_relation_count"],
            "target_online_seconds": receipt["target_online_seconds"],
            "regular_path_field_api_call_model_log2": receipt[
                "native_field_add_mul_sqr_call_model_log2"],
            "plan_sha256": sha(local_plan_path),
            "terminal_receipt_sha256": sha(result_path),
            "sage_replay_sha256": sha(replay_path),
            "runtime_info_sha256": sha(runtime_path),
        })
    assert local[0]["query_start"] + local[0]["query_representatives"] == (
        local[1]["query_start"])
    assert local[0]["query_start"] >= plan["query_end_exclusive"]

    ci_cycles = int(ci["ci_job_cycle_envelope"])
    local_cycles = int(capacity["local_reserved_cycle_capacity"])
    extra_base_cycles = int(capacity["base_build_extra_cycle_capacity"])
    total = ci_cycles + local_cycles + extra_base_cycles
    assert total >= int(capacity["scenarios"]["80"][
        "total_conditional_cycle_capacity"])
    assert total < 1 << 61
    return {
        "kind": "n83_fresh_target_terminal_dlp_extended_work_capacity",
        "status": "verified_dlp_under_conditional_cpu_cycle_capacity",
        "curve_id": plan["curve_id"],
        "field_degree_n": 83,
        "isogeny": "none",
        "candidate_ids": capacity["candidate_ids"],
        "run_ids": capacity["run_ids"],
        "workload_id": plan["workload_id"],
        "factor_base_enumerated_set_sha256": plan[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": plan[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": plan["signed_frobenius_columns"],
        "verified_fresh_target_scalar": str(scalar),
        "independently_verified_Q1091_natural_relations": ci[
            "independently_verified_relation_count"],
        "Q1090_Q1091_scheduled_ci_jobs_charged": 80,
        "Q1091_terminal_jobs": 64,
        "Q1091_successful_jobs": successful,
        "Q1091_cancelled_after_hit": canceled,
        "ci_job_cycle_capacity": str(ci_cycles),
        "local_reserved_cycle_capacity": str(local_cycles),
        "base_build_extra_cycle_capacity": str(extra_base_cycles),
        "whole_work_conditional_cpu_cycle_capacity": str(total),
        "whole_work_conditional_cpu_cycle_capacity_log2": math.log2(total),
        "below_2_61_under_stated_resource_assumptions": True,
        "measured_complete_field_operations_log2": None,
        "one_target_online_wall_ms": ci["one_target_online_wall_ms"],
        "paired_rho_online_wall_ms": ci["paired_rho_online_wall_ms"],
        "local_jobs": local,
        "as_of_utc": as_of.isoformat(),
        "Q1091_workflow_snapshot_sha256": sha(workflow_path),
        "Q1091_artifact_audit_count": len(list(artifact_audits.glob("*.json"))),
        "Q1091_terminal_reconciliation_sha256": hashlib.sha256(
            json.dumps(reconciliation, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False).encode("utf-8")).hexdigest(),
        "CI_cycle_auditor_source_sha256": ci["source_sha256"],
        "extended_capacity_sha256": sha(CAPACITY),
        "target_sha256": sha(TARGET),
        "source_sha256": sha(Path(__file__)),
        "limits": [
            "A natural Q1091 relation and fresh scalar passed independent checked-Sage replay; all 56 successful Q1091 receipts were independently audited.",
            "All 80 scheduled Q1090/Q1091 jobs are charged at least six hours on four vCPUs, with longer observed job walls charged instead; the eight canceled jobs are included.",
            "Both disjoint local Q1093 jobs finished and passed independent checked-Sage zero-hit replay; their work is included in the continuous local-host reserve.",
            "The local bound charges all 14 host cores from August 1 through October 29 at an assumed 8 GHz and charges the measured base-build loop again. Work on another host or outside the interval needs additional accounting.",
            "CPU core cycles are conditional resource capacity, not measured cycles or calibrated field operations; the 8 GHz ceiling is an explicit assumption.",
            "The run has no paired same-point rho online wall result or verified IC/rho speedup.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow-run", type=Path, required=True)
    parser.add_argument("--artifact-audits", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path,
                        help="extracted n83 terminal evidence archive")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), "refusing to overwrite terminal audit"
    result = audit(args.workflow_run, args.artifact_audits,
                   evidence_root=args.evidence_root)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in (
        "verified_fresh_target_scalar",
        "independently_verified_Q1091_natural_relations",
        "whole_work_conditional_cpu_cycle_capacity_log2",
        "below_2_61_under_stated_resource_assumptions")}))


if __name__ == "__main__":
    main()
