#!/usr/bin/env python3
"""Compare Bloom hash counts on one frozen n=83 signed-x query workload."""

import hashlib
import json
import math
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
REFERENCE = HERE.parent / "ecc2k130-quotient-pair-probe-20260926" / "runs" / "n83_perf_prefix.json"
BASE = HERE / "runs" / "n83_knownlog_orbit_base_k48194.json"
SCHEDULE = HERE / "runs" / "n53_n83_unique_schedule_perf.json"
RUNTIME = HERE / "runs" / "n83_signed_x_hashes_runtime_info.json"
OUTPUT = HERE / "runs" / "n83_signed_x_hashes_paired.json"
SOURCE = HERE / "native_n83_orbit_query_signed_x.cpp"
CORE = HERE / "native_n83_bloom_core.hpp"
PAIRS = HERE / "native_n83_pairs.cpp"
BINARY = Path("/private/tmp/ecc2k83-signed-x-hash-sweep")
K, L = 48194, 166
M, R = 1 << 20, 1 << 22
TABLE_START, QUERY_START = 4096, 1 << 20
WORKERS, HASH_ORDER = 14, (14, 8, 10, 12, 12, 10, 8, 14)
sys.path.insert(0, str(CODEGEN))

import field


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def main():
    runtime = json.loads(RUNTIME.read_text())
    assert runtime["status"] == "verified"
    reference = json.loads(REFERENCE.read_text())
    base = json.loads(BASE.read_text())
    schedule = json.loads(SCHEDULE.read_text())["runs"][1]
    identity = reference["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    factor = base["factor_base"]
    assert curve_id == reference["curve_id"] == base["curve_id"]
    assert base["isogeny"] == "none"
    assert factor["actual_usable_points_B_before_folding"] == K * L
    assert factor["signed_frobenius_columns"] == K
    key_path = HERE / factor["key_and_log_file"]
    assert sha(key_path) == factor["key_and_log_file_sha256"]
    domain = math.comb(K, 2) * L
    table_step = schedule["table_schedule"]["step"]
    table_offset = schedule["table_schedule"]["offset"]
    query_offset = (table_offset + 123456789) % domain
    assert math.gcd(table_step, domain) == 1
    assert TABLE_START + M <= domain and QUERY_START + R <= domain
    target = tuple(reference["workload"]["target"])
    onb = field.Onb(83)
    compiler = ["clang++", "-O3", "-std=c++17",
                "-march=armv8.2-a+crypto", f"-DECC2K83_ORBITS={K}",
                str(SOURCE), "-o", str(BINARY)]
    subprocess.run(compiler, check=True)
    report = {
        "kind": "n83_signed_x_bloom_hash_count_bounded_query_stage",
        "scope": "same public target, table/query schedules, base, and 14-worker envelope; stage diagnostic only",
        "proposal_id": "Q1055", "candidate_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "isogeny": "none", "public_target": list(target),
        "factor_base_enumerated_set_sha256": factor["enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": K * L,
        "signed_frobenius_columns": K,
        "table_start": TABLE_START, "table_descriptors": M,
        "query_start": QUERY_START, "query_representatives": R,
        "query_workers": WORKERS, "bits_per_key": 20,
        "representative_batch": 8, "hash_order": list(HASH_ORDER),
        "runs": [], "summaries": {},
        "natural_relation_yield_verified": False,
        "complete_solve_work_log2": None,
        "compiler_command": compiler, "binary_sha256": sha(BINARY),
        "native_source_sha256": sha(SOURCE),
        "bloom_core_sha256": sha(CORE), "native_pairs_sha256": sha(PAIRS),
        "base_receipt_sha256": sha(BASE), "key_file_sha256": sha(key_path),
        "schedule_receipt_sha256": sha(SCHEDULE),
        "sage_runtime_info_sha256": sha(RUNTIME),
        "source_sha256": sha(Path(__file__)),
    }
    for hashes in HASH_ORDER:
        command = [str(BINARY), str(key_path),
                   format(onb.toCoords(target[0]), "x"),
                   format(onb.toCoords(target[1]), "x"),
                   str(M), str(R), "1024", str(table_step), str(table_offset),
                   str(table_step), str(query_offset), "20", str(hashes),
                   str(TABLE_START), str(QUERY_START), str(WORKERS), "8"]
        cpu_before = resource.getrusage(resource.RUSAGE_CHILDREN)
        wall_before = time.perf_counter()
        result = subprocess.run(command, capture_output=True, text=True)
        wall_seconds = time.perf_counter() - wall_before
        cpu_after = resource.getrusage(resource.RUSAGE_CHILDREN)
        entry = {"hashes": hashes, "command": command,
                 "exit_code": result.returncode,
                 "subprocess_wall_seconds": wall_seconds,
                 "subprocess_user_cpu_seconds": cpu_after.ru_utime - cpu_before.ru_utime,
                 "subprocess_system_cpu_seconds": cpu_after.ru_stime - cpu_before.ru_stime}
        if result.returncode == 0:
            native = json.loads(result.stdout)
            assert native["actual_B"] == K * L
            assert native["table_descriptors"] == M
            assert native["query_representatives"] == R
            assert native["table_start"] == TABLE_START
            assert native["query_start"] == QUERY_START
            assert native["query_workers"] == WORKERS
            assert native["bloom_hashes"] == hashes
            entry["native_result"] = native
        else:
            entry["stderr_tail"] = result.stderr[-2000:]
        report["runs"].append(entry)
        OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"hashes": hashes, "exit_code": result.returncode,
                          "query_seconds": entry.get("native_result", {}).get("query_seconds"),
                          "positives": entry.get("native_result", {}).get("bloom_positive_queries")} ),
              flush=True)
        if result.returncode != 0:
            raise RuntimeError(f"native hash-count run failed: {hashes}")
    results = [entry["native_result"] for entry in report["runs"]]
    for key in ("exact_hit_keys", "exact_hit_queries",
                "complement_identity_queries"):
        assert len({entry[key] for entry in results}) == 1, key
    for hashes in sorted(set(HASH_ORDER)):
        group = [entry for entry in results if entry["bloom_hashes"] == hashes]
        assert len(group) == 2
        report["summaries"][str(hashes)] = {
            "median_query_seconds": statistics.median(
                entry["query_seconds"] for entry in group),
            "median_stage_seconds": statistics.median(
                entry["allocation_seconds"] + entry["build_seconds"] +
                entry["query_seconds"] + entry["exact_replay_seconds"]
                for entry in group),
            "median_process_cpu_seconds_including_startup": statistics.median(
                run["subprocess_user_cpu_seconds"] +
                run["subprocess_system_cpu_seconds"]
                for run in report["runs"] if run["hashes"] == hashes),
            "bloom_positive_queries": [entry["bloom_positive_queries"]
                                       for entry in group],
            "candidate_vector_capacity_bytes": [entry["candidate_vector_capacity_bytes"]
                                         for entry in group],
            "peak_rss_bytes": [entry["peak_rss_bytes"] for entry in group],
        }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
