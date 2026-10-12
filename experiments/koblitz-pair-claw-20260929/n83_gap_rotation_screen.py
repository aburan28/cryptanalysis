#!/usr/bin/env python3
"""Record the exact but slower n=83 cyclic-gap key experiment."""

import hashlib
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "runs" / "n83_gap_rotation_raw.json"
RUNTIME = HERE / "runs" / "n83_gap_rotation_runtime_info.json"
BASELINE = HERE / "runs" / "n83_fast_keyer_microbenchmark.json"
TEST = HERE / "bench_n83_gap_rotation.cpp"
PAIRS = HERE / "native_n83_pairs.cpp"
FIELD = HERE.parents[1] / "ecc2k130" / "runner" / "generated" / "eccF83.h"
BINARY = Path("/Volumes/SSD990/llm/tmp/ecc2k83-gap-rotation-bench")
OUTPUT = HERE / "runs" / "n83_gap_rotation_screen.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    raw = json.loads(RAW.read_text())
    runtime = json.loads(RUNTIME.read_text())
    baseline = json.loads(BASELINE.read_text())
    assert runtime["status"] == "verified"
    assert baseline["proposal_id"] == "Q1056"
    assert baseline["candidate_id"] is None
    assert baseline["native_pairs_source_sha256"] == sha(PAIRS)
    assert raw["all_keys_equal"] is True
    assert raw["samples"] == 1 << 20
    assert raw["two_bit_patterns_checked"] == 3403
    assert raw["frobenius_checks"] == 1024
    assert raw["variant_order"] == [0, 1, 2, 2, 1, 0,
                                   0, 1, 2, 2, 1, 0]
    grouped = {i: [seconds for variant, seconds in zip(
        raw["variant_order"], raw["seconds"]) if variant == i]
        for i in range(3)}
    assert all(len(group) == 4 and all(t > 0 for t in group)
               for group in grouped.values())
    medians = {"reference": statistics.median(grouped[0]),
               "byte_table": statistics.median(grouped[1]),
               "byte_table_plus_gap": statistics.median(grouped[2])}
    assert medians["byte_table_plus_gap"] > medians["byte_table"]
    report = {
        "kind": "n83_exact_cyclic_gap_rotation_negative_microbenchmark",
        "scope": "standalone key kernel on deterministic field inputs; not a full query, relation-yield, or DLP measurement",
        "proposal_id": "Q1057", "candidate_id": None,
        "curve_id": baseline["curve_id"],
        "curve_identity_record": baseline["curve_identity_record"],
        "isogeny": "none", "factor_base": None,
        "sample_count": raw["samples"],
        "two_bit_patterns_checked": raw["two_bit_patterns_checked"],
        "frobenius_checks": raw["frobenius_checks"],
        "all_keys_equal": True,
        "median_seconds": medians,
        "gap_over_byte_time_ratio": medians[
            "byte_table_plus_gap"] / medians["byte_table"],
        "decision": "reject this gap-scanning implementation for the native query path; retain Q1056 byte-table conversion",
        "natural_relation_yield_verified": False,
        "complete_solve_work_log2": None,
        "compile_flags": ["-O3", "-std=c++17",
                          "-march=armv8.2-a+crypto",
                          "-DECC2K83_ORBITS=48194",
                          "-DECC2K83_FAST_KEYER=1"],
        "binary_sha256": sha(BINARY),
        "test_source_sha256": sha(TEST),
        "native_pairs_source_sha256": sha(PAIRS),
        "generated_field_sha256": sha(FIELD),
        "raw_receipt_sha256": sha(RAW),
        "baseline_receipt_sha256": sha(BASELINE),
        "sage_runtime_info_sha256": sha(RUNTIME),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"all_keys_equal": True,
                      "byte_table_seconds": medians["byte_table"],
                      "gap_seconds": medians["byte_table_plus_gap"],
                      "gap_over_byte_time_ratio": report[
                          "gap_over_byte_time_ratio"]}))


if __name__ == "__main__":
    main()
