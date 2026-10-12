#!/usr/bin/env python3
"""Independently replay the terminal second Q1093 local receipt when it appears."""

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PLAN = HERE / "n83_q1093_second_local_arm_m32_r30_plan.json"
RESULT = RUNS / "n83_q1093_second_local_arm_m32_r30.json"
STARTED = RESULT.with_suffix(".started.json")
FAILURE = RUNS / "n83_q1093_second_local_arm_m32_r30_launcher_failure.json"
RUNTIME = RUNS / "n83_q1093_second_local_arm_m32_r30_runtime_info.json"
AUDIT = RUNS / "n83_q1093_second_local_arm_m32_r30_sage_verify.json"
VERIFIER = HERE / "verify_n83_holdout_q1093_receipt_sage.py"
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_result(plan, result):
    assert result["proposal_id"] == "Q1093"
    assert result["candidate_id"] == plan["candidate_id"]
    assert result["run_id"] == plan["run_id"]
    assert result["workload_id"] == plan["workload_id"]
    assert result["curve_id"] == plan["curve_id"]
    assert result["isogeny"] == "none"
    assert result["factor_base"]["enumerated_set_sha256"] == plan[
        "factor_base_enumerated_set_sha256"]
    assert result["factor_base"]["actual_usable_points_B_before_folding"] == (
        plan["actual_usable_points_B_before_folding"])
    assert result["factor_base"]["signed_frobenius_columns"] == plan[
        "signed_frobenius_columns"]
    assert result["public_target"] == plan["public_target"]
    assert result["table_start"] == plan["table_start"]
    assert result["table_descriptors"] == plan["table_descriptors"]
    assert result["query_start"] == plan["query_starts"][0]
    assert result["query_representatives"] == plan["query_representatives"]
    assert result["cpu_backend"] == plan["cpu_backend"]
    assert result["bits_per_key"] == plan["bits_per_key"]
    assert result["hashes"] == plan["hashes"]
    assert result["sage_runtime_info_sha256"] == sha(RUNTIME)
    assert result["wrapper_source_sha256"] == plan[
        "runner_source_sha256"]
    assert result["holdout_target_sha256"] == plan[
        "holdout_target_sha256"]
    assert result["verified_public_target_quotient_table_dlp"] == bool(
        result["verified_public_target_relations"])


def check_audit(plan, result, audit):
    assert audit["proposal_id"] == "Q1093"
    assert audit["candidate_id"] == plan["candidate_id"]
    assert audit["workload_id"] == plan["workload_id"]
    assert audit["curve_id"] == plan["curve_id"]
    assert audit["isogeny"] == "none"
    assert audit["receipt_sha256"] == sha(RESULT)
    assert audit["sage_runtime_info_sha256"] == sha(RUNTIME)
    assert audit["source_sha256"] == sha(VERIFIER)
    assert audit["verified_relation_count"] == len(result[
        "verified_public_target_relations"])
    assert audit["natural_public_target_relation_verified"] == bool(
        result["verified_public_target_relations"])
    assert all(row["scalar_replay"] and row["four_point_sum"] for row in
               audit["verified_relations"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=45)
    args = parser.parse_args()
    assert 1 <= args.poll_seconds <= 60
    plan = json.loads(PLAN.read_text())
    assert plan["proposal_id"] == "Q1093"
    assert plan["candidate_manifest_sha256"] == sha(
        HERE / plan["candidate_manifest"])
    assert json.loads(RUNTIME.read_text())["status"] == "verified"
    if STARTED.exists():
        assert json.loads(STARTED.read_text())["run_id"] == plan["run_id"]
    else:
        assert RESULT.exists()
    while not RESULT.exists() or STARTED.exists():
        if FAILURE.exists():
            raise RuntimeError(f"launcher failure: {FAILURE}")
        if not args.watch:
            print(json.dumps({"status": "pending", "run_id": plan["run_id"]}),
                  flush=True)
            return
        time.sleep(args.poll_seconds)
    result = json.loads(RESULT.read_text())
    if result["kind"] == "n83_holdout_signed_x_query_k48194_chunk_failed":
        raise RuntimeError(f"terminal failed receipt: {RESULT}")
    assert result["kind"] == "n83_holdout_signed_x_query_k48194_exact_replay_chunk"
    check_result(plan, result)
    if not AUDIT.exists():
        subprocess.run([str(SAGE), "-python", str(VERIFIER),
                        "--receipt", str(RESULT),
                        "--runtime-info", str(RUNTIME),
                        "--out", str(AUDIT)], check=True)
    audit = json.loads(AUDIT.read_text())
    check_audit(plan, result, audit)
    print(json.dumps({
        "status": "independently_verified",
        "run_id": plan["run_id"],
        "verified_natural_relations": audit["verified_relation_count"],
        "complete_discrete_logarithm": audit[
            "natural_public_target_relation_verified"],
        "modeled_field_api_calls_log2": result[
            "native_field_add_mul_sqr_call_model_log2"],
        "target_online_seconds": result["target_online_seconds"],
        "receipt_sha256": sha(RESULT),
        "audit_sha256": sha(AUDIT),
    }), flush=True)


if __name__ == "__main__":
    main()
