#!/usr/bin/env python3
"""Pair one unified Bloom filter with the two-filter Q1052 control."""

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
Q1052_RECEIPT = HERE / "runs" / "n83_two_shard_paired_bounded.json"
PLANTED = HERE / "runs" / "n83_unified_second_table_planted.json"
SOURCES = {
    "two_filters": HERE / "native_n83_orbit_query_two_shard.cpp",
    "unified": HERE / "native_n83_orbit_query_unified.cpp",
}
BINARIES = {
    "two_filters": Path("/private/tmp/ecc2k83-two-filter-unified-pair"),
    "unified": Path("/private/tmp/ecc2k83-unified-filter-pair"),
}
CORE = HERE / "native_n83_bloom_core.hpp"
PAIRS = HERE / "native_n83_pairs.cpp"
OUTPUT = HERE / "runs" / "n83_unified_paired_bounded.json"
K, L, M, R = 48194, 166, 1 << 20, 1 << 18
sys.path.insert(0, str(CODEGEN))

import field


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command):
    return json.loads(subprocess.run(
        command, check=True, capture_output=True, text=True).stdout)


def main():
    reference = json.loads(REFERENCE.read_text())
    base_receipt = json.loads(BASE.read_text())
    scheduled = json.loads(SCHEDULE.read_text())["runs"][1]
    prior = json.loads(Q1052_RECEIPT.read_text())
    planted = json.loads(PLANTED.read_text())
    identity = reference["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(json.dumps(
        identity, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode()).hexdigest()[:12]
    assert curve_id == reference["curve_id"] == base_receipt[
        "curve_id"] == prior["curve_id"] == planted["curve_id"]
    assert base_receipt["isogeny"] == prior["isogeny"] == planted[
        "isogeny"] == "none"
    assert prior["proposal_id"] == "Q1052"
    assert planted["proposal_id"] == "Q1053"
    assert planted["verified_relation"]["independent_scalar_replay"] is True
    factor = base_receipt["factor_base"]
    assert factor["actual_usable_points_B_before_folding"] == K * L
    assert prior["factor_base_enumerated_set_sha256"] == planted[
        "factor_base_enumerated_set_sha256"] == factor[
            "enumerated_set_sha256"]
    key_path = HERE / factor["key_and_log_file"]
    assert sha(key_path) == factor["key_and_log_file_sha256"]
    onb = field.Onb(83)
    target = reference["workload"]["target"]
    domain = math.comb(K, 2) * L
    step = scheduled["table_schedule"]["step"]
    table_offset = scheduled["table_schedule"]["offset"]
    query_offset = (table_offset + 123456789) % domain
    assert math.gcd(step, domain) == 1
    compiler_prefix = ["clang++", "-O3", "-std=c++17",
                       "-march=armv8.2-a+crypto",
                       f"-DECC2K83_ORBITS={K}"]
    compilers = {variant: compiler_prefix + [str(SOURCES[variant]),
                                        "-o", str(BINARIES[variant])]
                 for variant in SOURCES}
    for command in compilers.values():
        subprocess.run(command, check=True)
    common = [str(key_path), format(onb.toCoords(target[0]), "x"),
              format(onb.toCoords(target[1]), "x"), str(M), str(R),
              "1024", str(step), str(table_offset), str(step),
              str(query_offset), "20", "14", "0", "0", "1", "8", str(M)]
    commands = {variant: [str(BINARIES[variant]), *common]
                for variant in SOURCES}
    order = ["two_filters", "unified", "unified", "two_filters"]
    runs = [{"variant": variant, "native_result": run(commands[variant])}
            for variant in order]
    by_variant = {variant: [entry["native_result"] for entry in runs
                            if entry["variant"] == variant]
                  for variant in SOURCES}
    for variant, records in by_variant.items():
        assert len(records) == 2
        for record in records:
            assert record["actual_B"] == K * L
            assert record["table_shards"] == 2
            assert record["table_starts"] == [0, M]
            assert record["query_start"] == 0
            assert record["query_representatives"] == R
            assert record["query_workers"] == 1
        for key in ("bloom_positive_queries", "duplicate_positive_keys",
                    "exact_hit_keys", "exact_hit_queries"):
            assert records[0][key] == records[1][key], (variant, key)
    for record in by_variant["two_filters"]:
        assert [item["bloom_positive_queries"] for item in record[
            "per_shard"]] == [3245, 3288]
    assert all(record["exact_hit_queries"] == 0
               for records in by_variant.values() for record in records)
    two_seconds = statistics.median(record["query_seconds"]
                                    for record in by_variant["two_filters"])
    unified_seconds = statistics.median(record["query_seconds"]
                                        for record in by_variant["unified"])
    report = {
        "kind": "n83_unified_vs_two_filter_paired_bounded",
        "scope": "fixed public-target stage diagnostic under concurrent full-size Q1051 work; planted correctness separate; no natural n83 relation",
        "proposal_id": "Q1053", "candidate_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "isogeny": "none", "public_target": target,
        "factor_base_enumerated_set_sha256": factor[
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
        "median_two_filter_query_seconds": two_seconds,
        "median_unified_filter_query_seconds": unified_seconds,
        "bounded_query_speedup_two_filter_over_unified": (
            two_seconds / unified_seconds),
        "unified_bloom_positives": by_variant["unified"][0][
            "bloom_positive_queries"],
        "two_filter_bloom_positives": by_variant["two_filters"][0][
            "bloom_positive_queries"],
        "matched_exact_hit_counts": True,
        "planted_second_table_scalar_replay_passed": True,
        "natural_relation_yield_measured": False,
        "complete_solve_work_log2": None,
        "compiler_commands": compilers,
        "binary_sha256": {name: sha(path) for name, path in BINARIES.items()},
        "native_source_sha256": {name: sha(path) for name, path in SOURCES.items()},
        "bloom_core_sha256": sha(CORE),
        "native_pairs_sha256": sha(PAIRS),
        "prior_two_filter_receipt_sha256": sha(Q1052_RECEIPT),
        "planted_receipt_sha256": sha(PLANTED),
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
        "two_filter_query_seconds": two_seconds,
        "unified_query_seconds": unified_seconds,
        "query_speedup": report[
            "bounded_query_speedup_two_filter_over_unified"],
        "unified_bloom_positives": report["unified_bloom_positives"],
        "two_filter_bloom_positives": report["two_filter_bloom_positives"],
        "exact_hit_queries": by_variant["unified"][0]["exact_hit_queries"],
    }))


if __name__ == "__main__":
    main()
