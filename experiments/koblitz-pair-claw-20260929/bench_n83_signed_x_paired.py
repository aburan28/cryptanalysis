#!/usr/bin/env python3
"""Pair the original and signed-x n=83 query kernels on frozen inputs."""

import hashlib
import json
import math
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
REFERENCE = HERE.parent / "ecc2k130-quotient-pair-probe-20260926" / "runs" / "n83_perf_prefix.json"
BASE = HERE / "runs" / "n83_knownlog_orbit_base_k48194.json"
SCHEDULE = HERE / "runs" / "n53_n83_unique_schedule_perf.json"
RUNTIME_INFO = HERE / "runs" / "n83_signed_x_runtime_info.json"
OUTPUT = HERE / "runs" / "n83_signed_x_paired_bounded.json"
CORE = HERE / "native_n83_bloom_core.hpp"
PAIRS = HERE / "native_n83_pairs.cpp"
SOURCES = {
    "original": HERE / "native_n83_orbit_query.cpp",
    "signed_x": HERE / "native_n83_orbit_query_signed_x.cpp",
}
BINARIES = {
    name: Path(f"/private/tmp/ecc2k83-{name}-signed-x-paired")
    for name in SOURCES
}
K = 48194
L = 166
M = 1 << 20
R = 1 << 18
TABLE_START = 4096
QUERY_START = 1 << 20
ORDER = ("original", "signed_x", "signed_x", "original")
sys.path.insert(0, str(CODEGEN))

import field


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def main():
    runtime = json.loads(RUNTIME_INFO.read_text())
    assert runtime["status"] == "verified"
    reference = json.loads(REFERENCE.read_text())
    base = json.loads(BASE.read_text())
    schedule = json.loads(SCHEDULE.read_text())["runs"][1]
    identity = reference["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert curve_id == reference["curve_id"] == base["curve_id"]
    assert base["proposal_id"] == "Q1051" and base["isogeny"] == "none"
    factor = base["factor_base"]
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
    compilers = {}
    for name, source in SOURCES.items():
        command = [
            "clang++", "-O3", "-std=c++17", "-march=armv8.2-a+crypto",
            f"-DECC2K83_ORBITS={K}", str(source), "-o", str(BINARIES[name]),
        ]
        subprocess.run(command, check=True)
        compilers[name] = command
    results = []
    for name in ORDER:
        command = [
            str(BINARIES[name]), str(key_path),
            format(onb.toCoords(target[0]), "x"),
            format(onb.toCoords(target[1]), "x"),
            str(M), str(R), "1024", str(table_step), str(table_offset),
            str(table_step), str(query_offset), "20", "14",
            str(TABLE_START), str(QUERY_START), "1", "8",
        ]
        native = json.loads(subprocess.run(
            command, check=True, capture_output=True, text=True).stdout)
        assert native["actual_B"] == K * L
        assert native["table_descriptors"] == M
        assert native["query_representatives"] == R
        assert native["table_start"] == TABLE_START
        assert native["query_start"] == QUERY_START
        assert native["query_workers"] == 1
        results.append({"variant": name, "native_result": native})
    original = [entry["native_result"] for entry in results
                if entry["variant"] == "original"]
    signed_x = [entry["native_result"] for entry in results
                if entry["variant"] == "signed_x"]
    for key in ("bloom_positive_queries", "exact_hit_keys",
                "exact_hit_queries", "false_positive_queries",
                "complement_identity_queries"):
        assert len({entry[key] for entry in original + signed_x}) == 1, key
    def median(name):
        return statistics.median(entry["native_result"]["query_seconds"]
                                 for entry in results
                                 if entry["variant"] == name)
    original_median = median("original")
    signed_x_median = median("signed_x")
    original_times = [entry["query_seconds"] for entry in original]
    signed_x_times = [entry["query_seconds"] for entry in signed_x]
    paired_speedups = [original_times[i] / signed_x_times[i]
                       for i in range(2)]
    report = {
        "kind": "n83_signed_x_paired_bounded_query_stage",
        "scope": "same public target, table/query ranges, base, and resource envelope; stage performance only",
        "proposal_id": "Q1054", "candidate_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "isogeny": "none", "public_target": list(target),
        "factor_base_enumerated_set_sha256": factor["enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": K * L,
        "signed_frobenius_columns": K,
        "table_start": TABLE_START, "table_descriptors": M,
        "query_start": QUERY_START, "query_representatives": R,
        "query_workers": 1, "bits_per_key": 20, "hashes": 14,
        "representative_batch": 8, "pairing_order": list(ORDER),
        "median_original_query_seconds": original_median,
        "median_signed_x_query_seconds": signed_x_median,
        "original_query_seconds_range": [min(original_times),
                                         max(original_times)],
        "signed_x_query_seconds_range": [min(signed_x_times),
                                         max(signed_x_times)],
        "paired_query_speedup_ratios": paired_speedups,
        "bounded_query_speedup_original_over_signed_x":
            original_median / signed_x_median,
        "natural_relation_yield_verified": False,
        "complete_solve_work_log2": None,
        "runs": results,
        "compiler_commands": compilers,
        "binary_sha256": {name: sha(path) for name, path in BINARIES.items()},
        "native_source_sha256": {name: sha(path) for name, path in SOURCES.items()},
        "bloom_core_sha256": sha(CORE),
        "native_pairs_sha256": sha(PAIRS),
        "base_receipt_sha256": sha(BASE),
        "key_file_sha256": sha(key_path),
        "schedule_receipt_sha256": sha(SCHEDULE),
        "sage_runtime_info_sha256": sha(RUNTIME_INFO),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"original_query_seconds": original_median,
                      "signed_x_query_seconds": signed_x_median,
                      "speedup": original_median / signed_x_median,
                      "exact_hits": original[0]["exact_hit_queries"]}))


if __name__ == "__main__":
    main()
