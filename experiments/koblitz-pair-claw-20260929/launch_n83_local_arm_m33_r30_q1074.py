#!/usr/bin/env python3
"""Launch the next disjoint M33/R30 target search after audited Q1073 zero."""

import argparse
import hashlib
import json
import math
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from n83_full_spill_screen import field_calls

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RUNS = HERE / "runs"
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")
PLAN = HERE / "n83_local_arm_m33_r30_q1074_plan.json"
PRIOR_PLAN = HERE / "n83_local_arm_m33_q1073_plan.json"
WRAPPER = HERE / "run_n83_portable_chunk.py"
PREFLIGHT = RUNS / "n83_local_arm_m33_r30_q1074_preflight.json"
RUNTIME = RUNS / "n83_local_arm_m33_r30_q1074_runtime_info.json"
RESULT = RUNS / "n83_local_arm_m33_r30_q1074.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_zero_receipt(receipt_path, audit_path):
    receipt = json.loads(receipt_path.read_text())
    audit = json.loads(audit_path.read_text())
    assert receipt["kind"] == (
        "n83_public_target_signed_x_query_k48194_exact_replay_chunk")
    assert receipt["native_result"]["exact_hit_queries"] == 0
    assert receipt["verified_public_target_relations"] == []
    assert not receipt["verified_public_target_quotient_table_dlp"]
    assert audit["receipt_sha256"] == sha(receipt_path)
    assert audit["curve_id"] == receipt["curve_id"]
    assert audit["verified_relation_count"] == 0
    assert not audit["natural_public_target_relation_verified"]
    return receipt


def preflight(plan, spill_dir):
    assert plan["proposal_id"] == "Q1074"
    assert plan["status"] == (
        "frozen_conditional_on_Q1073_audited_zero_and_resources")
    assert plan["candidate_id"] is None and plan["run_id"] is None
    assert plan["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert plan["isogeny"] == "none"
    assert plan["actual_usable_points_B_before_folding"] == 8000204
    assert plan["signed_frobenius_columns"] == 48194
    assert plan["table_start"] == 0
    assert plan["table_descriptors"] == 1 << 33
    assert plan["query_representatives"] == 1 << 30
    assert plan["query_start"] == plan["prior_Q1073_end_exclusive"]
    assert plan["query_end_exclusive"] == (
        plan["query_start"] + plan["query_representatives"])
    assert plan["cpu_backend"] == "arm_pmull"
    assert plan["query_workers"] == 4
    assert plan["representative_batch"] == 8
    assert plan["bits_per_key"] == 20 and plan["hashes"] == 10
    assert int(plan["modeled_native_field_calls"]) == field_calls(
        plan["table_descriptors"], plan["query_representatives"])
    assert math.isclose(plan["modeled_native_field_calls_log2"],
                        math.log2(int(plan["modeled_native_field_calls"])))
    assert plan["Q1073_plan_sha256"] == sha(PRIOR_PLAN)
    assert plan["Q1073_preflight_sha256"] == sha(
        RUNS / "n83_local_arm_m33_q1073_preflight.json")
    assert plan["Q1073_runtime_info_sha256"] == sha(
        RUNS / "n83_local_arm_m33_q1073_runtime_info.json")
    for key, path in (
            ("portable_native_source_sha256",
             HERE / "native_n83_orbit_query_spill_portable.cpp"),
            ("portable_core_source_sha256",
             HERE / "native_n83_bloom_core_portable.hpp"),
            ("portable_pairs_source_sha256",
             HERE / "native_n83_pairs_portable.cpp"),
            ("portable_wrapper_source_sha256", WRAPPER),
            ("generated_field_header_sha256",
             REPO / "ecc2k130/runner/generated/eccF83.h"),
            ("base_receipt_sha256",
             RUNS / "n83_knownlog_orbit_base_k48194.json")):
        assert plan[key] == sha(path), key

    prior_path = RUNS / "n83_local_arm_m33_q1073.json"
    assert not prior_path.with_suffix(".started.json").exists(), (
        "Q1073 still has a start marker")
    prior = checked_zero_receipt(
        prior_path, RUNS / "n83_local_arm_m33_q1073_sage_verify.json")
    assert prior["curve_id"] == plan["curve_id"]
    assert prior["isogeny"] == "none"
    assert prior["candidate_id"] is None and prior["run_id"] is None
    assert prior["factor_base"]["enumerated_set_sha256"] == plan[
        "factor_base_enumerated_set_sha256"]
    assert prior["factor_base"]["actual_usable_points_B_before_folding"] == plan[
        "actual_usable_points_B_before_folding"]
    assert prior["factor_base"]["signed_frobenius_columns"] == plan[
        "signed_frobenius_columns"]
    assert prior["public_target"] == plan["public_target"]
    assert prior["query_start"] + prior[
        "query_representatives"] == plan["query_start"]
    assert prior["table_start"] == plan["table_start"]
    assert prior["table_descriptors"] == plan["table_descriptors"]

    # A new ledger may include Q1073; every charged receipt must stay clear
    # of this query interval, regardless of its table shard.
    ledger = json.loads((HERE / "n83_full_spill_segment_work.json").read_text())
    for entry in ledger["completed_receipts"]:
        row = json.loads((REPO / entry["path"]).read_text())
        start = row["query_start"]
        end = start + row["query_representatives"]
        assert max(start, plan["query_start"]) >= min(
            end, plan["query_end_exclusive"]), entry["path"]
    assert platform.machine().lower() in ("arm64", "aarch64")
    assert sys.platform == "darwin"
    pressure = subprocess.run(
        ["memory_pressure", "-Q"], check=True,
        capture_output=True, text=True).stdout
    capacity = re.search(r"The system has\s+(\d+)\s+\(", pressure)
    free = re.search(r"System-wide memory free percentage:\s*(\d+)%",
                     pressure)
    assert capacity and free, "cannot parse memory_pressure output"
    system_bytes = int(capacity.group(1))
    free_pct = int(free.group(1))
    free_bytes = system_bytes * free_pct // 100
    spill_free = shutil.disk_usage(spill_dir).free
    assert free_bytes >= plan["minimum_system_free_memory_bytes_before_launch"]
    assert spill_free >= plan["minimum_spill_volume_free_bytes_before_launch"]
    assert not PREFLIGHT.exists() and not RUNTIME.exists() and not RESULT.exists()
    assert not RESULT.with_suffix(".started.json").exists()
    return {
        "kind": "n83_q1074_local_arm_M33_R30_preflight",
        "proposal_id": "Q1074", "candidate_id": None, "run_id": None,
        "status": "passed_before_launch",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "curve_id": plan["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": plan[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": plan[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": plan["signed_frobenius_columns"],
        "public_target": plan["public_target"],
        "table_descriptors": plan["table_descriptors"],
        "query_start": plan["query_start"],
        "query_representatives": plan["query_representatives"],
        "Q1073_receipt_sha256": sha(prior_path),
        "Q1073_audit_sha256": sha(
            RUNS / "n83_local_arm_m33_q1073_sage_verify.json"),
        "coverage_ledger_sha256": sha(
            HERE / "n83_full_spill_segment_work.json"),
        "system_memory_bytes": system_bytes,
        "system_free_memory_pct": free_pct,
        "estimated_system_free_memory_bytes": free_bytes,
        "spill_free_bytes": spill_free,
        "minimum_system_free_memory_bytes": plan[
            "minimum_system_free_memory_bytes_before_launch"],
        "minimum_spill_free_bytes": plan[
            "minimum_spill_volume_free_bytes_before_launch"],
        "spill_dir": str(spill_dir),
        "plan_sha256": sha(PLAN),
        "launcher_source_sha256": sha(Path(__file__)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spill-dir", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    assert args.spill_dir.is_absolute() and args.spill_dir.is_dir()
    assert args.binary.is_absolute() and args.binary.parent.is_dir()
    assert SAGE.is_file()
    plan = json.loads(PLAN.read_text())
    report = preflight(plan, args.spill_dir)
    PREFLIGHT.write_text(json.dumps(report, indent=2) + "\n")
    with RUNTIME.open("x") as handle:
        subprocess.run([str(SAGE), "--runtime-info"], check=True,
                       stdout=handle)
    assert json.loads(RUNTIME.read_text())["status"] == "verified"
    command = [
        str(SAGE), "-python", str(WRAPPER),
        "--table-log2", "33", "--query-reps-log2", "30",
        "--table-start", "0", "--query-start", str(plan["query_start"]),
        "--workers", "4", "--rep-batch", "8",
        "--bits-per-key", "20", "--hashes", "10",
        "--cpu-backend", "arm_pmull",
        "--spill-dir", str(args.spill_dir),
        "--binary", str(args.binary),
        "--runtime-info", str(RUNTIME),
        "--out", str(RESULT),
    ]
    print(json.dumps({"preflight": str(PREFLIGHT),
                      "command": command}), flush=True)
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
