#!/usr/bin/env python3
"""Launch the frozen disjoint ARM holdout rectangle after resource checks."""

import hashlib
import json
import math
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PLAN = HERE / "n83_q1093_local_arm_m32_r30_plan.json"
TARGET = HERE / "n83_holdout_target_20261001.json"
RESERVE = HERE / "n83_holdout_revised_30day_resource_ceiling.json"
Q1092 = HERE / "n83_q1092_conditional_same_candidate_fallback.json"
FREEZER = HERE / "freeze_n83_q1093_local_arm.py"
WRAPPER = HERE / "run_n83_holdout_arm_q1093.py"
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")
SPILL_ROOT = Path("/private/tmp")
SPILL = SPILL_ROOT / "n83_q1093_m32_r30_spill"
SOURCE_DIR = SPILL_ROOT / "n83_q1093_m32_r30_sources"
BINARY = SPILL_ROOT / "n83_q1093_m32_r30_native"
PREFLIGHT = RUNS / "n83_q1093_local_arm_m32_r30_preflight.json"
RUNTIME = RUNS / "n83_q1093_local_arm_m32_r30_runtime_info.json"
RESULT = RUNS / "n83_q1093_local_arm_m32_r30.json"
LOG = RUNS / "n83_q1093_local_arm_m32_r30.launch.log"
LAUNCH_FAILURE = RUNS / "n83_q1093_local_arm_m32_r30_launcher_failure.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_now():
    return datetime.now(timezone.utc)


def preflight():
    assert platform.machine().lower() in ("arm64", "aarch64")
    assert sys.platform == "darwin"
    assert SAGE.is_file()
    assert not any(path.exists() for path in (SPILL, SOURCE_DIR, BINARY,
                   PREFLIGHT, RUNTIME, RESULT, LOG, LAUNCH_FAILURE,
                   RESULT.with_suffix(".started.json")))
    plan = json.loads(PLAN.read_text())
    target = json.loads(TARGET.read_text())
    reserve = json.loads(RESERVE.read_text())
    candidate_path = HERE / plan["candidate_manifest"]
    candidate = json.loads(candidate_path.read_text())
    canonical_candidate = json.dumps({
        k: v for k, v in candidate.items() if k not in
        ("candidate_id", "candidate_record_sha256")}, sort_keys=True,
        separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    assert hashlib.sha256(canonical_candidate).hexdigest() == candidate[
        "candidate_record_sha256"]
    assert plan["proposal_id"] == "Q1093"
    assert plan["status"] == "ready_for_dispatch"
    assert plan["candidate_id"] == candidate["candidate_id"]
    assert candidate_path.stem == plan["candidate_id"]
    assert plan["candidate_manifest_sha256"] == sha(candidate_path)
    assert plan["run_id"] == plan["candidate_id"] + "W" + plan[
        "workload_id"] + "R1"
    assert plan["workload_id"] == target["workload_id"]
    assert plan["curve_id"] == target["curve_id"] == candidate[
        "curve"]["curve_id"]
    assert plan["isogeny"] == target["isogeny"] == candidate[
        "isogeny"] == "none"
    assert plan["public_target"] == target["public_target"]
    assert target["fixture_scalar_retained"] is False
    assert plan["factor_base_enumerated_set_sha256"] == target[
        "factor_base_enumerated_set_sha256"] == candidate[
            "factor_base"]["enumerated_set_sha256"]
    assert plan["actual_usable_points_B_before_folding"] == 8000204
    assert plan["signed_frobenius_columns"] == 48194
    assert plan["table_start"] == 0
    assert plan["table_descriptors"] == 1 << 32
    assert plan["query_starts"] == [208 * (1 << 29)]
    assert plan["query_representatives"] == 1 << 30
    assert plan["query_end_exclusive"] == 210 * (1 << 29)
    assert plan["q1090_q1091_q1092_query_end_exclusive"] == 208 * (1 << 29)
    assert plan["query_end_exclusive"] <= math.comb(48194, 2) * 166
    assert plan["q1092_coverage_design_sha256"] == sha(Q1092)
    assert json.loads(Q1092.read_text())["query_end_exclusive"] == plan[
        "query_starts"][0]
    assert plan["cpu_backend"] == candidate["implementation"][
        "cpu_backend"] == "arm_pmull"
    assert plan["workers"] == 4
    assert plan["bits_per_key"] == 20 and plan["hashes"] == 10
    assert plan["representative_batch"] == 8
    assert plan["preferred_spill_root"] == str(SPILL_ROOT)
    assert plan["runner_source_sha256"] == candidate[
        "implementation"]["wrapper_source_sha256"] == sha(WRAPPER)
    assert plan["source_sha256"] == sha(FREEZER)
    assert candidate["point_decomposition"]["table_descriptors_per_job"] == (
        plan["table_descriptors"])
    assert candidate["point_decomposition"][
        "query_representatives_per_job"] == plan["query_representatives"]
    assert plan["holdout_target_sha256"] == sha(TARGET)
    assert plan["revised_30day_resource_ceiling_sha256"] == sha(RESERVE)
    assert reserve["q1090_q1091_q1092_plus_local_cycle_capacity_log2"] < 61
    assert utc_now() < datetime.fromisoformat(reserve["local_reserve_end_utc"])
    assert SPILL_ROOT.is_dir()
    pressure = subprocess.run(["memory_pressure", "-Q"], check=True,
                              capture_output=True, text=True).stdout
    capacity = re.search(r"The system has\s+(\d+)\s+\(", pressure)
    free = re.search(r"System-wide memory free percentage:\s*(\d+)%",
                     pressure)
    assert capacity and free
    free_mem = int(capacity.group(1)) * int(free.group(1)) // 100
    assert free_mem >= plan["minimum_mem_available_bytes"]
    spill_free = shutil.disk_usage(SPILL_ROOT).free
    repo_free = shutil.disk_usage(HERE).free
    assert spill_free >= plan["minimum_spill_free_bytes"]
    assert repo_free >= plan["minimum_root_free_bytes"]
    return plan, {
        "kind": "n83_q1093_local_arm_m32_r30_preflight",
        "status": "passed_before_launch",
        "checked_at_utc": utc_now().isoformat(),
        "curve_id": plan["curve_id"],
        "candidate_id": plan["candidate_id"],
        "workload_id": plan["workload_id"],
        "run_id": plan["run_id"],
        "isogeny": "none",
        "factor_base_enumerated_set_sha256": plan[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": 8000204,
        "signed_frobenius_columns": 48194,
        "table_start": 0,
        "table_descriptors": 1 << 32,
        "query_start": plan["query_starts"][0],
        "query_representatives": 1 << 30,
        "system_memory_capacity_bytes": int(capacity.group(1)),
        "system_free_memory_pct": int(free.group(1)),
        "estimated_system_free_memory_bytes": free_mem,
        "spill_free_bytes": spill_free,
        "repo_free_bytes": repo_free,
        "spill_dir": str(SPILL),
        "plan_sha256": sha(PLAN),
        "candidate_manifest_sha256": sha(candidate_path),
        "revised_30day_resource_ceiling_sha256": sha(RESERVE),
        "launcher_source_sha256": sha(Path(__file__)),
    }


def main():
    plan, receipt = preflight()
    SPILL.mkdir(mode=0o700)
    SOURCE_DIR.mkdir(mode=0o700)
    PREFLIGHT.write_text(json.dumps(receipt, indent=2) + "\n")
    with RUNTIME.open("x") as handle:
        subprocess.run([str(SAGE), "--runtime-info"], check=True,
                       stdout=handle)
    assert json.loads(RUNTIME.read_text())["status"] == "verified"
    command = [str(SAGE), "-python", str(WRAPPER),
               "--table-log2", "32", "--query-reps-log2", "30",
               "--table-start", "0", "--query-start", str(plan["query_starts"][0]),
               "--workers", str(plan["workers"]),
               "--rep-batch", str(plan["representative_batch"]),
               "--bits-per-key", str(plan["bits_per_key"]),
               "--hashes", str(plan["hashes"]),
               "--cpu-backend", plan["cpu_backend"],
               "--spill-dir", str(SPILL),
               "--source-dir", str(SOURCE_DIR),
               "--binary", str(BINARY),
               "--frozen-plan", str(PLAN),
               "--runtime-info", str(RUNTIME),
               "--out", str(RESULT)]
    print(json.dumps({"preflight": str(PREFLIGHT),
                      "runtime_info": str(RUNTIME),
                      "command": command}), flush=True)
    try:
        with LOG.open("x") as handle:
            process = subprocess.Popen(command, stdout=handle,
                                       stderr=subprocess.STDOUT,
                                       start_new_session=True)
            try:
                returncode = process.wait(timeout=plan["timeout_seconds_per_job"])
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                raise RuntimeError("frozen 12-hour local job timeout")
            assert returncode == 0, f"checked-Sage wrapper exit {returncode}"
        assert RESULT.is_file()
        print(json.dumps({"result": str(RESULT),
                          "result_sha256": sha(RESULT)}), flush=True)
    except BaseException as exc:
        LAUNCH_FAILURE.write_text(json.dumps({
            "kind": "n83_q1093_local_arm_launcher_failure",
            "failed_at_utc": utc_now().isoformat(),
            "plan_sha256": sha(PLAN),
            "preflight_sha256": sha(PREFLIGHT),
            "runtime_info_sha256": sha(RUNTIME),
            "terminal_status": type(exc).__name__,
            "message": str(exc),
            "result_exists": RESULT.exists(),
            "result_sha256": sha(RESULT) if RESULT.exists() else None,
        }, indent=2) + "\n")
        raise


if __name__ == "__main__":
    main()
