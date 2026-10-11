#!/usr/bin/env python3
"""Pair two-table quotient search against two separate table searches."""

import hashlib
import json
import math
import platform
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
REFERENCE = (HERE.parent / "ecc2k130-quotient-pair-probe-20260926" /
             "runs" / "n83_perf_prefix.json")
BASE = HERE / "runs" / "n83_knownlog_orbit_base_k48194.json"
SCHEDULE = HERE / "runs" / "n53_n83_unique_schedule_perf.json"
SINGLE_SOURCE = HERE / "native_n83_orbit_query.cpp"
DOUBLE_SOURCE = HERE / "native_n83_orbit_query_two_shard.cpp"
CORE = HERE / "native_n83_bloom_core.hpp"
PAIRS = HERE / "native_n83_pairs.cpp"
SINGLE_BINARY = Path("/private/tmp/ecc2k83-native-orbit-single-paired")
DOUBLE_BINARY = Path("/private/tmp/ecc2k83-native-orbit-two-paired")
OUTPUT = HERE / "runs" / "n83_two_shard_paired_bounded.json"
K = 48194
L = 166
M = 1 << 20
R = 1 << 18
sys.path.insert(0, str(CODEGEN))

import field


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command):
    raw = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(raw.stdout)


def main():
    reference = json.loads(REFERENCE.read_text())
    base_receipt = json.loads(BASE.read_text())
    scheduled = json.loads(SCHEDULE.read_text())["runs"][1]
    identity = reference["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(json.dumps(
        identity, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode()).hexdigest()[:12]
    assert curve_id == reference["curve_id"] == base_receipt["curve_id"]
    assert base_receipt["candidate_id"] is None
    assert base_receipt["isogeny"] == "none"
    factor_base = base_receipt["factor_base"]
    assert factor_base["actual_usable_points_B_before_folding"] == K * L
    key_path = HERE / factor_base["key_and_log_file"]
    assert sha(key_path) == factor_base["key_and_log_file_sha256"]
    onb = field.Onb(83)
    target = reference["workload"]["target"]
    d_cross = math.comb(K, 2) * L
    step = scheduled["table_schedule"]["step"]
    table_offset = scheduled["table_schedule"]["offset"]
    query_offset = (table_offset + 123456789) % d_cross
    assert math.gcd(step, d_cross) == 1
    compiler_prefix = ["clang++", "-O3", "-std=c++17",
                       "-march=armv8.2-a+crypto",
                       f"-DECC2K83_ORBITS={K}"]
    compiler_commands = [
        compiler_prefix + [str(SINGLE_SOURCE), "-o", str(SINGLE_BINARY)],
        compiler_prefix + [str(DOUBLE_SOURCE), "-o", str(DOUBLE_BINARY)],
    ]
    for command in compiler_commands:
        subprocess.run(command, check=True)
    common = [str(key_path), format(onb.toCoords(target[0]), "x"),
              format(onb.toCoords(target[1]), "x"), str(M), str(R),
              "1024", str(step), str(table_offset), str(step),
              str(query_offset), "20", "14"]
    commands = {
        "single_0": [str(SINGLE_BINARY), *common, "0", "0", "1", "8"],
        "single_1": [str(SINGLE_BINARY), *common, str(M), "0", "1", "8"],
        "double": [str(DOUBLE_BINARY), *common, "0", "0", "1", "8",
                   str(M)],
    }
    order = ["single_0", "single_1", "double", "double",
             "single_1", "single_0"]
    runs = [{"variant": variant, "native_result": run(commands[variant])}
            for variant in order]
    singles = {variant: [item["native_result"] for item in runs
                         if item["variant"] == variant]
               for variant in ("single_0", "single_1")}
    doubles = [item["native_result"] for item in runs
               if item["variant"] == "double"]
    for variant in singles:
        assert len(singles[variant]) == 2
        for key in ("bloom_positive_queries", "duplicate_positive_keys",
                    "exact_hit_keys", "exact_hit_queries"):
            assert singles[variant][0][key] == singles[variant][1][key]
    assert len(doubles) == 2
    for double in doubles:
        assert double["actual_B"] == K * L
        assert double["table_shards"] == 2
        assert double["table_starts"] == [0, M]
        assert double["query_representatives"] == R
        assert double["bloom_positive_queries"] == sum(
            item["bloom_positive_queries"] for item in double["per_shard"])
        for shard, variant in enumerate(("single_0", "single_1")):
            for key in ("bloom_positive_queries", "duplicate_positive_keys",
                        "exact_hit_keys", "exact_hit_queries"):
                assert double["per_shard"][shard][key] == singles[
                    variant][0][key]
    assert doubles[0]["per_shard"] == doubles[1]["per_shard"]
    separate_query_seconds = sum(statistics.median(
        item["query_seconds"] for item in singles[variant])
        for variant in ("single_0", "single_1"))
    shared_query_seconds = statistics.median(
        item["query_seconds"] for item in doubles)
    report = {
        "kind": "n83_two_shard_vs_two_separate_shards_paired_bounded",
        "scope": "stage diagnostic on the fixed public target; concurrent full-size Q1051 run may affect timing; no natural relation or complete DLP",
        "proposal_id": "Q1052", "candidate_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "isogeny": "none", "public_target": target,
        "factor_base_enumerated_set_sha256": factor_base[
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": K * L,
        "signed_frobenius_columns": K,
        "table_descriptors_per_shard": M,
        "query_representatives": R,
        "query_workers": 1,
        "representative_batch": 8,
        "bits_per_key": 20, "hashes": 14,
        "pairing_order": order,
        "runs": runs,
        "identical_per_shard_exact_outcomes": True,
        "median_two_separate_query_seconds_total": separate_query_seconds,
        "median_shared_two_shard_query_seconds": shared_query_seconds,
        "bounded_query_speedup_separate_over_shared": (
            separate_query_seconds / shared_query_seconds),
        "natural_relation_yield_measured": False,
        "complete_solve_work_log2": None,
        "compiler_commands": compiler_commands,
        "single_binary_sha256": sha(SINGLE_BINARY),
        "double_binary_sha256": sha(DOUBLE_BINARY),
        "single_source_sha256": sha(SINGLE_SOURCE),
        "double_source_sha256": sha(DOUBLE_SOURCE),
        "bloom_core_sha256": sha(CORE),
        "native_pairs_sha256": sha(PAIRS),
        "base_receipt_sha256": sha(BASE),
        "key_file_sha256": sha(key_path),
        "schedule_receipt_sha256": sha(SCHEDULE),
        "reference_sha256": sha(REFERENCE),
        "runtime": {"python": sys.version, "platform": platform.platform()},
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "curve_id": curve_id,
        "per_shard_positive_counts": [
            item["bloom_positive_queries"] for item in doubles[0]["per_shard"]],
        "exact_hit_queries": doubles[0]["exact_hit_queries"],
        "bounded_query_speedup_separate_over_shared":
            report["bounded_query_speedup_separate_over_shared"],
    }))


if __name__ == "__main__":
    main()
