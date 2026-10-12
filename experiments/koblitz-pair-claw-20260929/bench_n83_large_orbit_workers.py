#!/usr/bin/env python3
"""Pair worker-count timing on one frozen extended-base n=83 workload."""

import json
import math
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
BASE_RECEIPT = HERE / "runs" / "n83_knownlog_orbit_base_k48194.json"
REFERENCE = (HERE.parent / "ecc2k130-quotient-pair-probe-20260926" /
             "runs" / "n83_perf_prefix.json")
SCHEDULE = HERE / "runs" / "n53_n83_unique_schedule_perf.json"
SOURCE = HERE / "native_n83_orbit_query.cpp"
CORE = HERE / "native_n83_bloom_core.hpp"
PAIRS = HERE / "native_n83_pairs.cpp"
BINARY = Path("/private/tmp/ecc2k83-native-orbit-k48194-workers")
OUTPUT = HERE / "runs" / "n83_large_orbit_worker_count_paired.json"
K = 48194
L = 166
M = 1 << 24
R = 1 << 18
WORKERS = (8, 12, 14, 16, 16, 14, 12, 8)
sys.path.insert(0, str(CODEGEN))

import field
from run_n23 import sha


def main():
    base_receipt = json.loads(BASE_RECEIPT.read_text())
    reference = json.loads(REFERENCE.read_text())
    record = base_receipt["factor_base"]
    assert base_receipt["curve_id"] == reference["curve_id"]
    assert base_receipt["isogeny"] == "none"
    assert record["actual_usable_points_B_before_folding"] == K * L
    key_path = HERE / record["key_and_log_file"]
    assert sha(key_path) == record["key_and_log_file_sha256"]
    schedule = json.loads(SCHEDULE.read_text())["runs"][1]
    domain = math.comb(K, 2) * L
    step = schedule["table_schedule"]["step"]
    offset = schedule["table_schedule"]["offset"]
    query_offset = (offset + 123456789) % domain
    assert math.gcd(step, domain) == 1
    target = tuple(reference["workload"]["target"])
    onb = field.Onb(83)
    compiler = [
        "clang++", "-O3", "-std=c++17", "-march=armv8.2-a+crypto",
        f"-DECC2K83_ORBITS={K}", str(SOURCE), "-o", str(BINARY),
    ]
    subprocess.run(compiler, check=True)
    rows = []
    expected = None
    for workers in WORKERS:
        command = [
            str(BINARY), str(key_path),
            format(onb.toCoords(target[0]), "x"),
            format(onb.toCoords(target[1]), "x"),
            str(M), str(R), "1024", str(step), str(offset),
            str(step), str(query_offset), "20", "14",
            "0", "0", str(workers), "8",
        ]
        native = json.loads(subprocess.run(
            command, check=True, capture_output=True,
            text=True).stdout)
        assert native["actual_B"] == K * L
        assert native["table_descriptors"] == M
        assert native["query_representatives"] == R
        assert native["lifted_query_pairs"] == R * L
        counts = (native["bloom_positive_queries"],
                  native["false_positive_queries"],
                  native["exact_hit_queries"])
        if expected is None:
            expected = counts
        assert counts == expected
        rows.append({
            "workers": workers,
            "query_seconds": native["query_seconds"],
            "query_ns_per_lifted_pair": 1e9 * native[
                "query_seconds"] / (R * L),
            "build_seconds": native["build_seconds"],
            "exact_replay_seconds": native["exact_replay_seconds"],
            "bloom_positive_queries": counts[0],
            "exact_hit_queries": counts[2],
            "hit_samples_pending_independent_verification": native[
                "hits"],
        })
    medians = {str(workers): statistics.median(
        row["query_ns_per_lifted_pair"] for row in rows
        if row["workers"] == workers) for workers in sorted(set(WORKERS))}
    report = {
        "kind": "n83_extended_base_paired_query_worker_count_stage",
        "scope": "same frozen public target, base, table/query positions, and filter; query phase only; no natural relation or DLP",
        "proposal_id": "Q1051", "candidate_id": None,
        "curve_id": base_receipt["curve_id"],
        "curve_identity_record": base_receipt["curve_identity_record"],
        "isogeny": "none",
        "factor_base_enumerated_set_sha256": record[
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": K * L,
        "signed_frobenius_columns": K,
        "public_target": list(target),
        "table_descriptors": M,
        "query_representatives": R,
        "lifted_query_pairs": R * L,
        "worker_sequence": list(WORKERS),
        "rows": rows,
        "median_query_ns_per_lifted_pair": medians,
        "identical_exact_outcomes": True,
        "verified_public_target_quotient_table_dlp": False,
        "native_exact_hits_pending_independent_verification":
            expected[2],
        "compiler_command": compiler,
        "compiled_binary_sha256": sha(BINARY),
        "native_source_sha256": sha(SOURCE),
        "bloom_core_sha256": sha(CORE),
        "native_pairs_sha256": sha(PAIRS),
        "base_receipt_sha256": sha(BASE_RECEIPT),
        "key_file_sha256": sha(key_path),
        "reference_sha256": sha(REFERENCE),
        "schedule_receipt_sha256": sha(SCHEDULE),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"curve_id": report["curve_id"],
                      "worker_medians": medians,
                      "exact_hits": expected[2]}))


if __name__ == "__main__":
    main()
