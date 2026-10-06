#!/usr/bin/env python3
"""Guarded ABBA comparison of exact and byte-table n=83 quotient keys."""

import hashlib
import json
import math
import os
import resource
import shutil
import signal
import statistics
import subprocess
import time
from pathlib import Path

import bench_n83_signed_x_14worker_paired as baseline

HERE = baseline.HERE
RUNTIME = HERE / "runs" / "n83_fast_keyer_paired_runtime_info.json"
MICRO = HERE / "runs" / "n83_fast_keyer_microbenchmark.json"
OUTPUT = HERE / "runs" / "n83_fast_keyer_paired.json"
SOURCE = HERE / "native_n83_orbit_query_signed_x.cpp"
PAIRS = HERE / "native_n83_pairs.cpp"
CORE = HERE / "native_n83_bloom_core.hpp"
TMP = Path("/Volumes/SSD990/llm/tmp")
BINARIES = {"reference": TMP / "ecc2k83-keyer-reference",
            "fast": TMP / "ecc2k83-keyer-byte-table"}
ORDER = ("reference", "fast", "fast", "reference")
MIN_START_FREE = 2 << 30  # 2 GiB
MIN_RUNNING_FREE = 1 << 30  # 1 GiB
SWAP_LIMIT = 1024


def swapouts():
    output = subprocess.run(["vm_stat"], check=True, capture_output=True,
                            text=True).stdout
    for line in output.splitlines():
        if line.startswith("Swapouts:"):
            return int(line.split(":", 1)[1].strip().rstrip("."))
    raise RuntimeError("vm_stat omitted Swapouts")


def free_bytes():
    return shutil.disk_usage("/").free


def persist(report):
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")


def main():
    runtime = json.loads(RUNTIME.read_text())
    assert runtime["status"] == "verified"
    micro = json.loads(MICRO.read_text())
    assert micro["proposal_id"] == "Q1056"
    assert micro["test_result"]["all_keys_equal"]
    assert micro["native_pairs_source_sha256"] == baseline.sha(PAIRS)
    reference = json.loads(baseline.REFERENCE.read_text())
    base = json.loads(baseline.BASE.read_text())
    schedule = json.loads(baseline.SCHEDULE.read_text())["runs"][1]
    identity = reference["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(
        baseline.frozen(identity)).hexdigest()[:12]
    factor = base["factor_base"]
    assert curve_id == reference["curve_id"] == base["curve_id"]
    assert base["isogeny"] == "none"
    assert factor["actual_usable_points_B_before_folding"] == 8000204
    assert factor["signed_frobenius_columns"] == 48194
    key_path = HERE / factor["key_and_log_file"]
    assert baseline.sha(key_path) == factor["key_and_log_file_sha256"]
    target = tuple(reference["workload"]["target"])
    domain = math.comb(48194, 2) * 166
    table_step = schedule["table_schedule"]["step"]
    table_offset = schedule["table_schedule"]["offset"]
    query_offset = (table_offset + 123456789) % domain
    assert math.gcd(table_step, domain) == 1
    onb = baseline.field.Onb(83)
    if free_bytes() < MIN_START_FREE:
        raise RuntimeError("system volume lacks bounded-query headroom")
    env = os.environ.copy()
    env["TMPDIR"] = str(TMP)
    compilers = {}
    for name in BINARIES:
        command = ["clang++", "-O3", "-std=c++17",
                   "-march=armv8.2-a+crypto", "-DECC2K83_ORBITS=48194"]
        if name == "fast":
            command.append("-DECC2K83_FAST_KEYER=1")
        command.extend([str(SOURCE), "-o", str(BINARIES[name])])
        subprocess.run(command, check=True, env=env)
        compilers[name] = command
    report = {
        "kind": "n83_fast_keyer_paired_bounded_query_stage",
        "scope": "same public target, base, M=2^20 table, R=2^22 query, 14 workers and 14 Bloom hashes; key conversion variant only",
        "proposal_ids": ["Q1054", "Q1056"], "candidate_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "isogeny": "none", "public_target": list(target),
        "factor_base_enumerated_set_sha256": factor["enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": 8000204,
        "signed_frobenius_columns": 48194,
        "table_start": baseline.TABLE_START,
        "table_descriptors": baseline.M,
        "query_start": baseline.QUERY_START,
        "query_representatives": baseline.R,
        "query_workers": baseline.WORKERS,
        "bits_per_key": 20, "hashes": 14,
        "pairing_order": list(ORDER),
        "runs": [], "summary": None,
        "natural_relation_yield_verified": False,
        "complete_solve_work_log2": None,
        "compiler_commands": compilers,
        "binary_sha256": {name: baseline.sha(path)
                          for name, path in BINARIES.items()},
        "native_source_sha256": baseline.sha(SOURCE),
        "native_pairs_sha256": baseline.sha(PAIRS),
        "bloom_core_sha256": baseline.sha(CORE),
        "base_receipt_sha256": baseline.sha(baseline.BASE),
        "key_file_sha256": baseline.sha(key_path),
        "schedule_receipt_sha256": baseline.sha(baseline.SCHEDULE),
        "microbenchmark_receipt_sha256": baseline.sha(MICRO),
        "sage_runtime_info_sha256": baseline.sha(RUNTIME),
        "source_sha256": baseline.sha(Path(__file__)),
    }
    if free_bytes() < MIN_START_FREE:
        raise RuntimeError("system volume lacks bounded-query headroom")
    swap0 = swapouts()
    time.sleep(5)
    if free_bytes() < MIN_START_FREE or swapouts() - swap0 > 128:
        raise RuntimeError("bounded-query disk/swap preflight failed")
    for name in ORDER:
        command = [str(BINARIES[name]), str(key_path),
                   format(onb.toCoords(target[0]), "x"),
                   format(onb.toCoords(target[1]), "x"),
                   str(baseline.M), str(baseline.R), "1024",
                   str(table_step), str(table_offset),
                   str(table_step), str(query_offset), "20", "14",
                   str(baseline.TABLE_START), str(baseline.QUERY_START),
                   str(baseline.WORKERS), "8"]
        if free_bytes() < MIN_START_FREE:
            raise RuntimeError("system volume lost bounded-query headroom")
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        started = time.perf_counter()
        initial_swap = swapouts()
        reason = None
        child = subprocess.Popen(command, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True,
                                 start_new_session=True)
        while child.poll() is None:
            time.sleep(1)
            reason = ("system_volume" if free_bytes() < MIN_RUNNING_FREE else
                      "swap_growth" if swapouts() - initial_swap > SWAP_LIMIT
                      else None)
            if reason and child.poll() is None:
                os.killpg(child.pid, signal.SIGINT)
                break
        stdout, stderr = child.communicate()
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        entry = {
            "variant": name, "command": command,
            "exit_code": child.returncode, "guard_reason": reason,
            "subprocess_wall_seconds": time.perf_counter() - started,
            "subprocess_cpu_seconds":
                after.ru_utime - before.ru_utime +
                after.ru_stime - before.ru_stime,
            "swapouts_before": initial_swap,
            "swapouts_after": swapouts(),
            "system_volume_free_after_bytes": free_bytes(),
        }
        if child.returncode == 0:
            native = json.loads(stdout)
            assert native["actual_B"] == 8000204
            assert native["table_descriptors"] == baseline.M
            assert native["query_representatives"] == baseline.R
            assert native["table_start"] == baseline.TABLE_START
            assert native["query_start"] == baseline.QUERY_START
            assert native["query_workers"] == baseline.WORKERS
            assert native["bloom_hashes"] == 14
            entry["native_result"] = native
        else:
            entry["native_result"] = None
            entry["stderr_tail"] = stderr[-2000:]
        report["runs"].append(entry)
        persist(report)
        print(json.dumps({"variant": name, "exit_code": child.returncode,
                          "guard_reason": reason,
                          "query_seconds": (entry["native_result"] or {}).get(
                              "query_seconds")}), flush=True)
        if child.returncode:
            raise RuntimeError(f"keyer paired run failed: {name}")
    groups = {name: [entry["native_result"] for entry in report["runs"]
                     if entry["variant"] == name]
              for name in ("reference", "fast")}
    for key in ("bloom_positive_queries", "exact_hit_keys",
                "exact_hit_queries", "false_positive_queries",
                "complement_identity_queries"):
        assert len({row[key] for group in groups.values() for row in group}) == 1
    median = lambda name, key: statistics.median(
        row[key] for row in groups[name])
    report["summary"] = {
        "median_query_seconds": {name: median(name, "query_seconds")
                                 for name in groups},
        "median_full_native_stage_seconds": {name: statistics.median(
            sum(row[key] for key in ("allocation_seconds", "build_seconds",
                                    "query_seconds", "exact_replay_seconds"))
            for row in groups[name]) for name in groups},
        "query_speedup_reference_over_fast":
            median("reference", "query_seconds") /
            median("fast", "query_seconds"),
        "bloom_positive_queries": groups["reference"][0][
            "bloom_positive_queries"],
        "exact_hit_queries": groups["reference"][0]["exact_hit_queries"],
    }
    persist(report)
    print(json.dumps(report["summary"]), flush=True)


if __name__ == "__main__":
    main()
