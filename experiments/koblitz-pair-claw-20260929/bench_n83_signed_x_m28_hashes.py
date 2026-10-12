#!/usr/bin/env python3
"""Guarded ABBA hash-count calibration on a larger n=83 Bloom filter."""

import hashlib
import json
import math
import os
import resource
import shutil
import signal
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")
RUNNER = HERE / "run_n83_signed_x_chunk.py"
BASELINE = RUNS / "n83_signed_x_hashes_paired.json"
OUTPUT = RUNS / "n83_signed_x_m28_hashes_paired.json"
M_LOG2, R_LOG2 = 28, 24
QUERY_START = 1 << 30
ORDER = (14, 10, 10, 14)
MIN_START_FREE = 5 << 29  # 2.5 GiB
MIN_RUNNING_FREE = 3 << 29  # 1.5 GiB
PREFLIGHT_SWAP_LIMIT = 128
RUN_SWAP_LIMIT = 1024


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def swapouts():
    output = subprocess.run(["vm_stat"], check=True, capture_output=True,
                            text=True).stdout
    for line in output.splitlines():
        if line.startswith("Swapouts:"):
            return int(line.split(":", 1)[1].strip().rstrip("."))
    raise RuntimeError("vm_stat omitted Swapouts")


def free_bytes():
    return shutil.disk_usage("/").free


def receipt_path(index, hashes):
    return RUNS / (f"n83_signed_x_m28_hash{hashes}_R24_"
                   f"qstart{QUERY_START}_abba{index}.json")


def write_report(report):
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")


def check_receipt(path, hashes, reference):
    item = json.loads(path.read_text())
    assert item["proposal_id"] == ("Q1054" if hashes == 14 else "Q1055")
    assert item["candidate_id"] is None
    assert item["curve_id"] == reference["curve_id"]
    assert item["isogeny"] == "none"
    assert item["public_target"] == reference["public_target"]
    factor = item.get("factor_base", item)
    assert factor.get("enumerated_set_sha256", factor.get(
        "factor_base_enumerated_set_sha256")) == reference[
            "factor_base_enumerated_set_sha256"]
    assert factor["actual_usable_points_B_before_folding"] == 8000204
    assert item["table_start"] == 0 and item["table_descriptors"] == 1 << M_LOG2
    assert item["query_start"] == QUERY_START
    assert item["query_representatives"] == 1 << R_LOG2
    assert item["query_workers"] == 14
    assert item["bits_per_key"] == 20 and item["hashes"] == hashes
    return item


def main():
    reference = json.loads(BASELINE.read_text())
    assert reference["proposal_id"] == "Q1055"
    assert reference["candidate_id"] is None
    assert reference["isogeny"] == "none"
    assert reference["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert reference["actual_usable_points_B_before_folding"] == 8000204
    assert reference["signed_frobenius_columns"] == 48194
    report = {
        "kind": "n83_signed_x_m28_bloom_hash_count_paired_stage",
        "scope": "same n83 curve, public target, base, M=2^28 table, R=2^24 query, and 14-worker envelope; stage diagnostic only",
        "proposal_ids": ["Q1054", "Q1055"], "candidate_id": None,
        "curve_id": reference["curve_id"], "isogeny": "none",
        "public_target": reference["public_target"],
        "factor_base_enumerated_set_sha256": reference[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": 8000204,
        "signed_frobenius_columns": 48194,
        "table_start": 0, "table_descriptors": 1 << M_LOG2,
        "query_start": QUERY_START, "query_representatives": 1 << R_LOG2,
        "query_workers": 14, "hash_order": list(ORDER),
        "minimum_start_system_free_bytes": MIN_START_FREE,
        "minimum_running_system_free_bytes": MIN_RUNNING_FREE,
        "maximum_preflight_swapout_growth_pages": PREFLIGHT_SWAP_LIMIT,
        "maximum_run_swapout_growth_pages": RUN_SWAP_LIMIT,
        "runs": [], "summary": None,
        "ordinary_n83_relation_measured": False,
        "complete_solve_work_log2": None,
        "baseline_receipt_sha256": sha(BASELINE),
        "runner_source_sha256": sha(RUNNER),
        "source_sha256": sha(Path(__file__)),
    }
    if OUTPUT.exists():
        old = json.loads(OUTPUT.read_text())
        for key in ("curve_id", "public_target", "factor_base_enumerated_set_sha256",
                    "baseline_receipt_sha256", "runner_source_sha256",
                    "source_sha256", "hash_order"):
            assert old[key] == report[key], key
    for index, hashes in enumerate(ORDER, 1):
        path = receipt_path(index, hashes)
        marker = path.with_suffix(".started.json")
        if marker.exists():
            raise RuntimeError(f"existing active or stale marker: {marker}")
        if path.exists():
            item = check_receipt(path, hashes, reference)
            if item["kind"].endswith("chunk_failed"):
                raise RuntimeError(f"failed terminal receipt requires review: {path}")
            assert item["kind"].endswith("exact_replay_chunk")
            report["runs"].append({"hashes": hashes, "receipt": str(path),
                                   "receipt_sha256": sha(path),
                                   "field_call_model": item[
                                       "native_field_add_mul_sqr_call_model"],
                                   "native_result": item["native_result"]})
            continue
        competing = sorted(RUNS.glob("n83_*.started.json"))
        if competing:
            raise RuntimeError(f"another n83 job marker exists: {competing}")
        free0, swap0 = free_bytes(), swapouts()
        if free0 < MIN_START_FREE:
            raise RuntimeError("insufficient system-volume free space for M28")
        time.sleep(10)
        free1, swap1 = free_bytes(), swapouts()
        if (free1 < MIN_START_FREE or
                swap1 - swap0 > PREFLIGHT_SWAP_LIMIT):
            raise RuntimeError("M28 preflight disk/swap stability failed")
        if list(RUNS.glob("n83_*.started.json")):
            raise RuntimeError("another n83 job started during preflight")
        runtime_path = path.with_suffix(".runtime.json")
        runtime = subprocess.run([str(SAGE), "--runtime-info"], check=True,
                                 capture_output=True, text=True).stdout
        runtime_path.write_text(runtime)
        assert json.loads(runtime)["status"] == "verified"
        command = [str(SAGE), "-python", str(RUNNER),
                   "--proposal-id", "Q1054" if hashes == 14 else "Q1055",
                   "--table-log2", str(M_LOG2), "--query-reps-log2", str(R_LOG2),
                   "--table-start", "0", "--query-start", str(QUERY_START),
                   "--workers", "14", "--rep-batch", "8",
                   "--bits-per-key", "20", "--hashes", str(hashes),
                   "--runtime-info", str(runtime_path), "--out", str(path)]
        log_path = path.with_suffix(".console.log")
        cpu_before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.perf_counter()
        reason = None
        with log_path.open("w") as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            while child.poll() is None:
                time.sleep(5)
                free_now, swap_now = free_bytes(), swapouts()
                reason = ("system_volume" if free_now < MIN_RUNNING_FREE else
                          "swap_growth" if swap_now - swap1 > RUN_SWAP_LIMIT else
                          None)
                if reason and child.poll() is None:
                    os.killpg(child.pid, signal.SIGINT)
                    break
            child.wait()
        cpu_after = resource.getrusage(resource.RUSAGE_CHILDREN)
        if not path.exists():
            raise RuntimeError(f"child exited without terminal receipt: {path}")
        item = check_receipt(path, hashes, reference)
        entry = {
            "hashes": hashes, "receipt": str(path), "receipt_sha256": sha(path),
            "runtime_info": str(runtime_path),
            "runtime_info_sha256": sha(runtime_path),
            "exit_code": child.returncode, "guard_reason": reason,
            "subprocess_wall_seconds": time.perf_counter() - start,
            "subprocess_cpu_seconds":
                cpu_after.ru_utime - cpu_before.ru_utime +
                cpu_after.ru_stime - cpu_before.ru_stime,
            "swapouts_before": swap1, "swapouts_after": swapouts(),
            "system_free_before_bytes": free1,
            "system_free_after_bytes": free_bytes(),
            "field_call_model": item.get(
                "native_field_add_mul_sqr_call_model"),
            "native_result": item.get("native_result"),
        }
        report["runs"].append(entry)
        write_report(report)
        print(json.dumps({"index": index, "hashes": hashes,
                          "exit_code": child.returncode, "guard_reason": reason,
                          "query_seconds": (entry["native_result"] or {}).get(
                              "query_seconds"),
                          "exact_hits": (entry["native_result"] or {}).get(
                              "exact_hit_queries")}), flush=True)
        if child.returncode or item["kind"].endswith("chunk_failed"):
            raise RuntimeError(f"M28 run interrupted or failed: {path}")
        if item["verified_public_target_quotient_table_dlp"]:
            report["ordinary_n83_relation_measured"] = True
            write_report(report)
            return
    assert len(report["runs"]) == len(ORDER)
    groups = {h: [entry["native_result"] for entry in report["runs"]
                  if entry["hashes"] == h] for h in (10, 14)}
    assert all(len(group) == 2 for group in groups.values())
    for key in ("exact_hit_queries", "complement_identity_queries"):
        assert len({row[key] for group in groups.values() for row in group}) == 1
    median = lambda h, key: sorted(row[key] for row in groups[h])[0] / 2 + \
        sorted(row[key] for row in groups[h])[1] / 2
    report["summary"] = {
        "median_query_seconds": {str(h): median(h, "query_seconds")
                                 for h in (10, 14)},
        "median_build_seconds": {str(h): median(h, "build_seconds")
                                 for h in (10, 14)},
        "query_speedup_14_over_10": median(14, "query_seconds") /
            median(10, "query_seconds"),
        "bloom_positive_queries": {str(h): groups[h][0][
            "bloom_positive_queries"] for h in (10, 14)},
        "peak_rss_bytes": {str(h): [row["peak_rss_bytes"] for row in groups[h]]
                           for h in (10, 14)},
        "four_runs_field_call_model_log2": math.log2(sum(
            int(entry["field_call_model"]) for entry in report["runs"])),
    }
    write_report(report)
    print(json.dumps(report["summary"]), flush=True)


if __name__ == "__main__":
    main()
