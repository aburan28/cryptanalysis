#!/usr/bin/env python3
"""Gate and launch the disjoint Q1073 M33 search on a physical ARM host."""

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

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RUNS = HERE / "runs"
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")
PLAN = HERE / "n83_local_arm_m33_q1073_plan.json"
WAVE_PLAN = HERE / "n83_m32_wave_launch_plan.json"
WRAPPER = HERE / "run_n83_portable_chunk.py"
PREFLIGHT = RUNS / "n83_local_arm_m33_q1073_preflight.json"
RUNTIME = RUNS / "n83_local_arm_m33_q1073_runtime_info.json"
RESULT = RUNS / "n83_local_arm_m33_q1073.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audited_zero(receipt_path, audit_path):
    receipt = json.loads(receipt_path.read_text())
    audit = json.loads(audit_path.read_text())
    assert receipt["native_result"]["exact_hit_queries"] == 0
    assert not receipt["verified_public_target_quotient_table_dlp"]
    assert audit["receipt_sha256"] == sha(receipt_path)
    assert audit["curve_id"] == receipt["curve_id"]
    assert audit["verified_relation_count"] == 0
    assert not audit["natural_public_target_relation_verified"]
    return {"receipt": str(receipt_path.relative_to(REPO)),
            "receipt_sha256": sha(receipt_path),
            "audit_sha256": sha(audit_path)}


def preflight(plan, spill_dir):
    assert plan["proposal_id"] == "Q1073"
    assert plan["status"] == (
        "frozen_ready_if_active_searches_zero_hit_and_resources_pass")
    assert plan["candidate_id"] is None and plan["run_id"] is None
    assert plan["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert plan["isogeny"] == "none"
    assert plan["actual_usable_points_B_before_folding"] == 8000204
    assert plan["signed_frobenius_columns"] == 48194
    assert plan["table_start"] == 0
    assert plan["table_descriptors"] == 1 << 33
    assert plan["query_representatives"] == 1 << 29
    assert plan["query_start"] == plan["prior_Q1071_end_exclusive"]
    assert plan["query_end_exclusive"] == (
        plan["query_start"] + plan["query_representatives"])
    assert plan["cpu_backend"] == "arm_pmull"
    assert plan["query_workers"] == 4
    assert plan["representative_batch"] == 8
    assert plan["bits_per_key"] == 20 and plan["hashes"] == 10
    assert plan["Q1071_plan_sha256"] == sha(
        HERE / "n83_local_arm_m32_q1071_plan.json")
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

    q1071_path = RUNS / "n83_local_arm_m32_q1071.json"
    q1071 = audited_zero(
        q1071_path, RUNS / "n83_local_arm_m32_q1071_sage_verify.json")
    q1071_row = json.loads(q1071_path.read_text())
    assert q1071_row["query_start"] + q1071_row[
        "query_representatives"] == plan["query_start"]
    assert q1071_row["public_target"] == plan["public_target"]
    assert q1071_row["factor_base"]["enumerated_set_sha256"] == plan[
        "factor_base_enumerated_set_sha256"]
    q1068_dir = RUNS / "n83_portable_q1068_M32_R29_ci_36698966100"
    q1068 = audited_zero(q1068_dir / "full.json",
                         q1068_dir / "sage_verify.json")
    wave = json.loads(WAVE_PLAN.read_text())
    assert wave["proposal_id"] == "Q1069"
    assert wave["query_end_exclusive"] == q1071_row["query_start"]
    assert len(wave["query_starts"]) == 8
    terminal_wave = []
    for start in wave["query_starts"]:
        directory = RUNS / (
            f"n83_portable_q1069_M32_R29_ci_36706324060_qstart{start}")
        bundle = json.loads((directory / "bundle.json").read_text())
        assert bundle["proposal_id"] == "Q1069"
        assert bundle["query_start"] == start
        assert bundle["curve_id"] == plan["curve_id"]
        assert bundle["isogeny"] == "none"
        assert bundle["factor_base_enumerated_set_sha256"] == plan[
            "factor_base_enumerated_set_sha256"]
        assert bundle["query_representatives"] == 1 << 29
        if bundle["status"] == "completed_zero_hit":
            row = audited_zero(directory / "full.json",
                               directory / "sage_verify.json")
            row["status"] = bundle["status"]
        else:
            assert bundle["status"] == "failed_full_segment_unknown_work"
            failed_path = directory / "full.json"
            if failed_path.exists():
                failed = json.loads(failed_path.read_text())
                assert failed["kind"] == (
                    "n83_public_target_signed_x_query_k48194_chunk_failed")
                assert not failed["verified_public_target_quotient_table_dlp"]
                assert bundle["artifact_sha256"]["full.json"] == sha(
                    failed_path)
            row = {"status": bundle["status"],
                   "failed_receipt_sha256": (
                       sha(failed_path) if failed_path.exists() else None)}
        row["query_start"] = start
        row["bundle_sha256"] = sha(directory / "bundle.json")
        terminal_wave.append(row)

    assert platform.machine().lower() in ("arm64", "aarch64")
    assert sys.platform == "darwin"
    pressure = subprocess.run(
        ["memory_pressure", "-Q"], check=True,
        capture_output=True, text=True).stdout
    capacity = re.search(r"The system has\s+(\d+)\s+\(", pressure)
    assert capacity, "cannot parse memory_pressure system capacity"
    system_bytes = int(capacity.group(1))
    match = re.search(r"System-wide memory free percentage:\s*(\d+)%",
                      pressure)
    assert match, "cannot parse memory_pressure free percentage"
    free_pct = int(match.group(1))
    free_bytes = system_bytes * free_pct // 100
    spill_free = shutil.disk_usage(spill_dir).free
    assert free_bytes >= plan["minimum_system_free_memory_bytes_before_launch"]
    assert spill_free >= plan["minimum_spill_volume_free_bytes_before_launch"]
    assert not PREFLIGHT.exists() and not RUNTIME.exists() and not RESULT.exists()
    assert not RESULT.with_suffix(".started.json").exists()
    return {
        "kind": "n83_q1073_local_arm_M33_R29_preflight",
        "proposal_id": "Q1073", "candidate_id": None, "run_id": None,
        "status": "passed_before_launch",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "curve_id": plan["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": plan[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": plan[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": plan["signed_frobenius_columns"],
        "query_start": plan["query_start"],
        "query_representatives": plan["query_representatives"],
        "table_descriptors": plan["table_descriptors"],
        "public_target": plan["public_target"],
        "system_memory_bytes": system_bytes,
        "system_free_memory_pct": free_pct,
        "estimated_system_free_memory_bytes": free_bytes,
        "spill_free_bytes": spill_free,
        "minimum_system_free_memory_bytes": plan[
            "minimum_system_free_memory_bytes_before_launch"],
        "minimum_spill_free_bytes": plan[
            "minimum_spill_volume_free_bytes_before_launch"],
        "spill_dir": str(spill_dir),
        "Q1068_zero_audit": q1068,
        "Q1071_zero_audit": q1071,
        "Q1069_terminal_rows": terminal_wave,
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
        "--table-log2", "33", "--query-reps-log2", "29",
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
