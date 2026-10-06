#!/usr/bin/env python3
"""Launch the audited Q1084 local search on an SSD spill volume."""

import argparse
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import n83_full_spill_segment_work as segment_work
import n83_q1084_full_plan as plan_builder
from n83_full_spill_screen import field_calls

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RUNS = HERE / "runs"
PLAN = HERE / "n83_q1084_local_m33_plan.json"
LEDGER = HERE / "n83_full_spill_segment_work.json"
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")
WRAPPER = HERE / "run_n83_portable_chunk.py"
PREFLIGHT = RUNS / "n83_local_arm_m33_r30_q1084_preflight.json"
RUNTIME = RUNS / "n83_local_arm_m33_r30_q1084_runtime_info.json"
RESULT = RUNS / "n83_local_arm_m33_r30_q1084.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_file(path, digest):
    assert path.is_file(), str(path)
    assert sha(path) == digest, str(path)


def preflight(plan, spill_dir, binary):
    assert plan["proposal_id"] == "Q1084"
    assert plan["status"] == "ready_for_local_launch"
    assert plan["candidate_id"] is None and plan["run_id"] is None
    assert plan["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert plan["isogeny"] == "none"
    assert plan["factor_base_enumerated_set_sha256"] == (
        "7e3c95f988225da1d586578529953ad61ae5ed62ca740eb92c2aea6d841a5a02")
    assert plan["actual_usable_points_B_before_folding"] == 8000204
    assert plan["signed_frobenius_columns"] == 48194
    assert plan["table_start"] == 0
    assert plan["table_descriptors"] == 1 << 33
    assert plan["query_start"] == 35433480192
    assert plan["query_representatives"] == 1 << 30
    assert plan["query_end_exclusive"] == plan["query_start"] + (
        1 << 30)
    assert plan["cpu_backend"] == "arm_pmull"
    assert plan["query_workers"] == 4
    assert plan["representative_batch"] == 8
    assert plan["bits_per_key"] == 20 and plan["hashes"] == 10
    assert int(plan["modeled_native_field_calls"]) == field_calls(
        1 << 33, 1 << 30)
    assert math.isclose(plan["modeled_native_field_calls_log2"], math.log2(
        int(plan["modeled_native_field_calls"])))
    assert plan["M33_vs_four_M32_same_host_online_time_ratio"] < 1
    check_file(HERE / "n83_q1084_local_m33_design.json",
               plan["Q1084_design_sha256"])
    check_file(HERE / "n83_q1084_full_plan.py", plan["source_sha256"])
    check_file(Path(__file__), plan["local_launcher_source_sha256"])
    current = plan_builder.freeze()
    for key in ("curve_id", "isogeny", "factor_base_enumerated_set_sha256",
                "actual_usable_points_B_before_folding",
                "signed_frobenius_columns", "public_target", "target_count",
                "table_start", "table_descriptors", "query_start",
                "query_representatives", "query_end_exclusive",
                "cpu_backend", "query_workers", "representative_batch",
                "bits_per_key", "hashes", "Q1074_terminal_audit",
                "Q1071_terminal_audit", "terminal_prior_Q1081_audits",
                "M33_vs_four_M32_same_host_online_time_ratio"):
        assert plan[key] == current[key], key
    check_file(WRAPPER, plan["portable_wrapper_source_sha256"])
    for key, path in (
        ("portable_native_source_sha256", HERE /
         "native_n83_orbit_query_spill_portable.cpp"),
        ("portable_core_source_sha256", HERE /
         "native_n83_bloom_core_portable.hpp"),
        ("portable_pairs_source_sha256", HERE /
         "native_n83_pairs_portable.cpp"),
        ("generated_field_header_sha256", REPO /
         "ecc2k130/runner/generated/eccF83.h"),
        ("base_receipt_sha256", RUNS /
         "n83_knownlog_orbit_base_k48194.json"),
        ("Q1074_receipt_sha256", RUNS /
         "n83_local_arm_m33_r30_q1074.json")):
        check_file(path, plan[key])
    for audit in (plan["Q1074_terminal_audit"],
                  plan["Q1071_terminal_audit"],
                  *plan["terminal_prior_Q1081_audits"]):
        check_file(HERE / audit["receipt"], audit["receipt_sha256"])
        check_file(HERE / audit["sage_audit"], audit["sage_audit_sha256"])
        if "bundle" in audit:
            check_file(HERE / audit["bundle"], audit["bundle_sha256"])
    assert len(plan["terminal_prior_Q1081_audits"]) == 8

    ledger = json.loads(LEDGER.read_text())
    assert ledger["source_sha256"] == sha(Path(segment_work.__file__)), (
        "regenerate the coverage ledger after source changes")
    assert ledger["curve_id"] == plan["curve_id"]
    assert ledger["isogeny"] == "none"
    assert ledger["factor_base_enumerated_set_sha256"] == plan[
        "factor_base_enumerated_set_sha256"]
    assert not ledger["verified_quotient_table_dlp_receipts"]
    assert not ledger["unverified_exact_hit_receipts"]
    credited = {row["path"]: row["sha256"] for row in ledger[
        "completed_receipts"]}
    assert credited[segment_work.repo_path(RUNS /
        "n83_local_arm_m33_r30_q1074.json")] == plan[
            "Q1074_receipt_sha256"]
    start, end = plan["query_start"], plan["query_end_exclusive"]
    for entry in ledger["completed_receipts"]:
        row = json.loads((REPO / entry["path"]).read_text())
        begin, finish = row["query_start"], row["query_start"] + row[
            "query_representatives"]
        assert max(begin, start) >= min(finish, end), entry["path"]
    for path in RUNS.rglob("*.started.json"):
        row = json.loads(path.read_text())
        if row.get("curve_id") != plan["curve_id"]:
            continue
        begin, finish = row["query_start"], row["query_start"] + row[
            "query_representatives"]
        assert max(begin, start) >= min(finish, end), str(path)
    q1083_path = HERE / "n83_q1083_m32_wave_plan.json"
    if q1083_path.exists():
        q1083 = json.loads(q1083_path.read_text())
        assert q1083["curve_id"] == plan["curve_id"]
        assert q1083["query_end_exclusive"] <= start

    assert platform.machine().lower() in ("arm64", "aarch64")
    assert sys.platform == "darwin"
    assert spill_dir.is_absolute() and spill_dir.is_dir()
    root = Path(plan["preferred_spill_root"]).resolve()
    assert spill_dir.resolve().is_relative_to(root)
    assert os.stat(spill_dir).st_dev == os.stat(root).st_dev
    assert binary.is_absolute() and binary.parent.is_dir()
    assert binary.resolve().parent.is_relative_to(root)
    assert os.stat(binary.parent).st_dev == os.stat(root).st_dev
    assert not binary.exists()
    pressure = subprocess.run(["memory_pressure", "-Q"], check=True,
                              capture_output=True, text=True).stdout
    capacity = re.search(r"The system has\s+(\d+)\s+\(", pressure)
    free = re.search(r"System-wide memory free percentage:\s*(\d+)%",
                     pressure)
    assert capacity and free, "cannot parse memory_pressure output"
    system_bytes = int(capacity.group(1))
    free_pct = int(free.group(1))
    free_bytes = system_bytes * free_pct // 100
    spill_free = shutil.disk_usage(spill_dir).free
    assert free_bytes >= plan[
        "minimum_system_free_memory_bytes_before_launch"]
    assert spill_free >= plan[
        "minimum_spill_volume_free_bytes_before_launch"]
    assert not PREFLIGHT.exists() and not RUNTIME.exists()
    assert not RESULT.exists() and not RESULT.with_suffix(
        ".started.json").exists()
    q1086_preflight = RUNS / "n83_local_arm_m34_r31_q1086_preflight.json"
    q1086_receipt = RUNS / "n83_local_arm_m34_r31_q1086.json"
    assert not (q1086_preflight.exists() and not q1086_receipt.exists()), (
        "Q1086 may be active or interrupted on the same host")
    assert SAGE.is_file()
    return {
        "kind": "n83_q1084_local_arm_M33_R30_preflight",
        "proposal_id": "Q1084", "candidate_id": None, "run_id": None,
        "status": "passed_before_launch",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "curve_id": plan["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": plan[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": 8000204,
        "signed_frobenius_columns": 48194,
        "public_target": plan["public_target"],
        "table_start": 0, "table_descriptors": 1 << 33,
        "query_start": start, "query_representatives": 1 << 30,
        "system_memory_bytes": system_bytes,
        "system_free_memory_pct": free_pct,
        "estimated_system_free_memory_bytes": free_bytes,
        "spill_free_bytes": spill_free,
        "spill_dir": str(spill_dir), "binary": str(binary),
        "plan_sha256": sha(PLAN), "coverage_ledger_sha256": sha(LEDGER),
        "launcher_source_sha256": sha(Path(__file__)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spill-dir", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    assert PLAN.is_file(), "Q1084 audited executable plan has not been frozen"
    plan = json.loads(PLAN.read_text())
    report = preflight(plan, args.spill_dir, args.binary)
    with PREFLIGHT.open("x") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    with RUNTIME.open("x") as handle:
        subprocess.run([str(SAGE), "--runtime-info"], check=True,
                       stdout=handle)
    assert json.loads(RUNTIME.read_text())["status"] == "verified"
    command = [
        str(SAGE), "-python", str(WRAPPER),
        "--table-log2", "33", "--query-reps-log2", "30",
        "--table-start", "0", "--query-start", str(plan["query_start"]),
        "--workers", str(plan["query_workers"]),
        "--rep-batch", str(plan["representative_batch"]),
        "--bits-per-key", str(plan["bits_per_key"]),
        "--hashes", str(plan["hashes"]),
        "--cpu-backend", plan["cpu_backend"],
        "--spill-dir", str(args.spill_dir),
        "--binary", str(args.binary),
        "--runtime-info", str(RUNTIME), "--out", str(RESULT),
    ]
    print(json.dumps({"preflight": str(PREFLIGHT),
                      "command": command}), flush=True)
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
