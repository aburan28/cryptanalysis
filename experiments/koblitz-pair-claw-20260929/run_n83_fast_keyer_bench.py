#!/usr/bin/env python3
"""Freeze the exact n=83 fast-keyer equality and microbenchmark receipt."""

import hashlib
import json
import os
import statistics
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEST = HERE / "bench_n83_fast_keyer.cpp"
PAIRS = HERE / "native_n83_pairs.cpp"
FIELD = HERE.parents[1] / "ecc2k130" / "runner" / "generated" / "eccF83.h"
REFERENCE = HERE / "runs" / "n83_signed_x_hashes_paired.json"
RUNTIME = HERE / "runs" / "n83_fast_keyer_runtime_info.json"
OUTPUT = HERE / "runs" / "n83_fast_keyer_microbenchmark.json"
TMP = Path("/Volumes/SSD990/llm/tmp")
BINARY = TMP / "ecc2k83-fast-keyer-bench"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def main():
    runtime = json.loads(RUNTIME.read_text())
    assert runtime["status"] == "verified"
    reference = json.loads(REFERENCE.read_text())
    identity = reference["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert curve_id == reference["curve_id"]
    assert reference["isogeny"] == "none"
    assert reference["actual_usable_points_B_before_folding"] == 8000204
    command = ["clang++", "-O3", "-std=c++17",
               "-march=armv8.2-a+crypto", "-DECC2K83_ORBITS=48194",
               "-DECC2K83_FAST_KEYER=1", str(TEST), "-o", str(BINARY)]
    environment = os.environ.copy()
    environment["TMPDIR"] = str(TMP)
    subprocess.run(command, check=True, env=environment)
    result = json.loads(subprocess.run([str(BINARY)], check=True,
                                       capture_output=True, text=True).stdout)
    assert result["all_keys_equal"] is True
    assert result["frobenius_checks"] == 1024
    assert result["samples"] == 1 << 20
    names = result["variant_order"]
    times = result["seconds"]
    assert names == ["reference", "fast", "fast", "reference",
                     "fast", "reference", "reference", "fast"]
    assert len(times) == 8 and all(t > 0 for t in times)
    reference_times = [t for name, t in zip(names, times)
                       if name == "reference"]
    fast_times = [t for name, t in zip(names, times)
                  if name == "fast"]
    reference_median = statistics.median(reference_times)
    fast_median = statistics.median(fast_times)
    report = {
        "kind": "n83_fast_keyer_exact_equality_and_microbenchmark",
        "scope": "native field-coordinate-to-orbit-key kernel only; no factor-base search, relation yield, or DLP",
        "proposal_id": "Q1056", "candidate_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "isogeny": "none", "factor_base": None,
        "actual_usable_points_B_before_folding": None,
        "signed_frobenius_columns": None,
        "compile_macro": "ECC2K83_FAST_KEYER=1",
        "test_result": result,
        "reference_median_seconds": reference_median,
        "fast_median_seconds": fast_median,
        "reference_seconds_range": [min(reference_times),
                                    max(reference_times)],
        "fast_seconds_range": [min(fast_times), max(fast_times)],
        "microbenchmark_speedup_reference_over_fast":
            reference_median / fast_median,
        "natural_relation_yield_verified": False,
        "complete_solve_work_log2": None,
        "compiler_command": command,
        "binary_sha256": sha(BINARY),
        "test_source_sha256": sha(TEST),
        "native_pairs_source_sha256": sha(PAIRS),
        "generated_field_sha256": sha(FIELD),
        "reference_receipt_sha256": sha(REFERENCE),
        "sage_runtime_info_sha256": sha(RUNTIME),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"all_keys_equal": True,
                      "reference_seconds": reference_median,
                      "fast_seconds": fast_median,
                      "microbenchmark_speedup": reference_median /
                          fast_median}))


if __name__ == "__main__":
    main()
