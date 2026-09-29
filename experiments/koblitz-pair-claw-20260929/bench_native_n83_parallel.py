#!/usr/bin/env python3
"""Pair n83 quotient-query worker counts and check disjoint query ranges."""

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
REFERENCE = HERE.parent / "ecc2k130-quotient-pair-probe-20260926" / "runs" / "n83_perf_prefix.json"
BASE_RECEIPT = HERE / "runs" / "n83_knownlog_orbit_base.json"
SCHEDULE = HERE / "runs" / "n53_n83_unique_schedule_perf.json"
SOURCE = HERE / "native_n83_bloom.cpp"
PAIRS_SOURCE = HERE / "native_n83_pairs.cpp"
OUTPUT = HERE / "runs" / "n83_native_bloom_parallel_perf.json"
BINARY = Path("/private/tmp/ecc2k83-native-bloom-parallel")
BATCH = 1024
BITS_PER_KEY = 24
HASHES = 17
sys.path.insert(0, str(CODEGEN))

import field
from run_n23 import frozen, sha


def main():
    reference = json.loads(REFERENCE.read_text())
    base_receipt = json.loads(BASE_RECEIPT.read_text())
    scheduled = json.loads(SCHEDULE.read_text())["runs"][1]
    identity = reference["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert reference["curve_id"] == base_receipt["curve_id"] == scheduled["curve_id"] == curve_id
    record = base_receipt["factor_base"]
    assert record["actual_usable_points_B_before_folding"] == 4000102
    assert record["signed_frobenius_columns"] == 24097
    key_path = HERE / record["key_and_log_file"]
    assert sha(key_path) == record["key_and_log_file_sha256"]
    onb = field.Onb(83)
    target = tuple(reference["workload"]["target"])
    compiler_command = [
        "clang++", "-O3", "-std=c++17", "-march=armv8.2-a+crypto",
        str(SOURCE), "-o", str(BINARY),
    ]
    subprocess.run(compiler_command, check=True)

    def run(label, table_entries, query_start, query_pairs, workers):
        command = [
            str(BINARY), str(key_path),
            format(onb.toCoords(target[0]), "x"),
            format(onb.toCoords(target[1]), "x"),
            str(table_entries), str(query_pairs), str(BATCH),
            str(scheduled["table_schedule"]["step"]),
            str(scheduled["table_schedule"]["offset"]),
            str(scheduled["query_schedule"]["step"]),
            str(scheduled["query_schedule"]["offset"]),
            str(BITS_PER_KEY), str(HASHES), str(query_start), str(workers),
        ]
        raw = json.loads(subprocess.run(
            command, check=True, capture_output=True, text=True).stdout)
        assert raw["actual_B"] == 4000102
        assert raw["table_descriptors"] == table_entries
        assert raw["query_start"] == query_start
        assert raw["query_pairs"] == query_pairs
        assert raw["query_workers"] == workers
        assert raw["exact_hit_queries"] == 0
        raw["label"] = label
        raw["query_ns_per_pair"] = raw["query_seconds"] * 1e9 / query_pairs
        return raw

    M_small = 1 << 24
    Q_small = 1 << 24
    small = [run(f"full_{workers}_workers", M_small, 0, Q_small, workers)
             for workers in (1, 4, 8)]
    half = Q_small // 2
    left = run("left_half_4_workers", M_small, 0, half, 4)
    right = run("right_half_4_workers", M_small, half, half, 4)
    assert sum(row["bloom_positive_queries"] for row in (left, right)) == (
        small[0]["bloom_positive_queries"])
    assert sum(row["false_positive_queries"] for row in (left, right)) == (
        small[0]["false_positive_queries"])
    assert sum(row["complement_identity_queries"] for row in (left, right)) == (
        small[0]["complement_identity_queries"])
    for row in small[1:]:
        assert row["bloom_positive_queries"] == small[0]["bloom_positive_queries"]
        assert row["false_positive_queries"] == small[0]["false_positive_queries"]

    M_large = 1 << 28
    Q_large = 1 << 25
    large = [run(f"large_{workers}_workers", M_large, 0, Q_large, workers)
             for workers in (1, 4, 8)]
    for row in large[1:]:
        assert row["bloom_positive_queries"] == large[0]["bloom_positive_queries"]
        assert row["false_positive_queries"] == large[0]["false_positive_queries"]
    small_speedups = {str(row["query_workers"]):
                    small[0]["query_seconds"] / row["query_seconds"]
                    for row in small}
    large_speedups = {str(row["query_workers"]):
                    large[0]["query_seconds"] / row["query_seconds"]
                    for row in large}
    report = {
        "kind": "n83_knownlog_blocked_bloom_disjoint_ranges_and_parallel_query_perf",
        "scope": "paired bounded public-target query stages only; no ordinary relation or complete quotient-table DLP",
        "proposal_id": "Q1049", "candidate_id": None, "run_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "isogeny": "none", "public_target": list(target),
        "factor_base": record,
        "small_table_descriptors": M_small,
        "small_query_pairs": Q_small,
        "small_full_runs": small,
        "small_split_runs": [left, right],
        "large_table_descriptors": M_large,
        "large_query_pairs": Q_large,
        "large_full_runs": large,
        "small_query_speedup_vs_one_worker": small_speedups,
        "large_query_speedup_vs_one_worker": large_speedups,
        "disjoint_range_partition_checks_passed": True,
        "identical_full_query_outcomes_across_worker_counts": True,
        "verified_public_target_relations": 0,
        "verified_public_target_quotient_table_dlp": False,
        "complete_work_log2": None,
        "compiler_command": compiler_command,
        "compiler_version": subprocess.run(
            ["clang++", "--version"], check=True, capture_output=True,
            text=True).stdout.splitlines()[0],
        "runtime": {"python": sys.version, "platform": platform.platform()},
        "source_sha256": sha(Path(__file__)),
        "native_source_sha256": sha(SOURCE),
        "native_pairs_source_sha256": sha(PAIRS_SOURCE),
        "compiled_binary_sha256": sha(BINARY),
        "base_receipt_sha256": sha(BASE_RECEIPT),
        "key_and_log_file_sha256": sha(key_path),
        "schedule_receipt_sha256": sha(SCHEDULE),
        "reference_sha256": sha(REFERENCE),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "curve_id": curve_id,
        "small_speedups": small_speedups,
        "large_speedups": large_speedups,
        "disjoint_range_partition_checks_passed": True,
        "large_false_positive_queries": large[0]["false_positive_queries"],
    }))


if __name__ == "__main__":
    main()
