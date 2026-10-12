#!/usr/bin/env python3
"""Pair equal-area M/R shapes on one frozen n=83 public target."""

import argparse
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
sys.path.insert(0, str(CODEGEN))
import field  # noqa: E402

SCREEN = HERE / "n83_full_spill_screen.json"
FROZEN = (HERE / "runs" /
          "n83_portable_q1061_k48194_chunk_M24_R20_tstart0_"
          "qstart1073741824_b20_h10_rb8.json")
SOURCE = HERE / "native_n83_orbit_query_spill_portable.cpp"
CORE = HERE / "native_n83_bloom_core_portable.hpp"
PAIRS = HERE / "native_n83_pairs_portable.cpp"
ORDER = ((24, 20), (25, 19), (25, 19), (24, 20))
QUERY_START = 1 << 30


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def field_calls(m, r):
    inversions = 2 * math.ceil(m / 1024) + 2 * math.ceil(r / 8)
    return 26 * m + 13 * r + 13 * r * 83 + 90 * inversions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch-dir", type=Path, required=True)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert args.scratch_dir.is_absolute() and args.scratch_dir.is_dir()
    assert not args.out.exists(), "refusing to overwrite benchmark receipt"
    runtime = json.loads(args.runtime_info.read_text())
    assert runtime["status"] == "verified"
    assert platform.machine().lower() in ("arm64", "aarch64")
    screen = json.loads(SCREEN.read_text())
    frozen = json.loads(FROZEN.read_text())
    assert frozen["curve_id"] == screen["curve_id"]
    assert frozen["factor_base"] == screen["factor_base"]
    assert frozen["table_descriptors"] == 1 << 24
    assert frozen["query_representatives"] == 1 << 20
    assert frozen["query_start"] == QUERY_START
    assert frozen["native_result"]["exact_hit_queries"] == 0
    base = HERE / screen["factor_base"]["key_and_log_file"]
    assert sha(base) == screen["factor_base"]["key_and_log_file_sha256"]
    target = frozen["public_target"]
    onb = field.Onb(83)
    target_x = format(onb.toCoords(target[0]), "x")
    target_y = format(onb.toCoords(target[1]), "x")
    table = frozen["table_schedule"]
    query = frozen["query_representative_schedule"]
    binary = args.scratch_dir / "ecc2k83-portable-shape"
    compile_command = [
        "c++", "-O3", "-std=c++17", "-march=armv8.2-a+crypto",
        "-DECC2K83_ORBITS=48194", "-DECC2K83_FAST_KEYER=1",
        str(SOURCE), "-o", str(binary),
    ]
    subprocess.run(compile_command, check=True)
    env = os.environ.copy()
    env["ECC2K83_CANDIDATE_TMPDIR"] = str(args.scratch_dir)
    rows = []
    for index, (m_log2, r_log2) in enumerate(ORDER):
        m, r = 1 << m_log2, 1 << r_log2
        command = [
            str(binary), str(base), target_x, target_y,
            str(m), str(r), "1024", str(table["step"]),
            str(table["offset"]), str(query["step"]),
            str(query["offset"]), "20", "10",
            "0", str(QUERY_START), "4", "8",
        ]
        begun = time.perf_counter_ns()
        result = subprocess.run(command, check=True, text=True,
                                capture_output=True, env=env)
        wall = (time.perf_counter_ns() - begun) / 1e9
        native = json.loads(result.stdout)
        assert native["actual_B"] == screen["factor_base"][
            "actual_usable_points_B_before_folding"]
        assert native["table_descriptors"] == m
        assert native["query_representatives"] == r
        assert native["query_start"] == QUERY_START
        assert native["bloom_hashes"] == 10
        assert native["candidate_store_mode"] == "unlinked_file"
        assert native["exact_hit_queries"] == 0
        assert native["false_positive_queries"] == native[
            "bloom_positive_queries"]
        rows.append({"index": index, "table_log2": m_log2,
                     "query_log2": r_log2,
                     "modeled_native_field_calls": str(field_calls(m, r)),
                     "native_wall_seconds": wall,
                     "native_result": native})
        print(json.dumps({"index": index, "table_log2": m_log2,
                          "query_log2": r_log2,
                          "query_seconds": native["query_seconds"],
                          "bloom_positive_queries": native[
                              "bloom_positive_queries"]}), flush=True)
    full_ratios = [rows[0]["native_wall_seconds"] /
                   rows[1]["native_wall_seconds"],
                   rows[3]["native_wall_seconds"] /
                   rows[2]["native_wall_seconds"]]
    model_ratio = (field_calls(1 << 24, 1 << 20) /
                   field_calls(1 << 25, 1 << 19))
    full_model_ratio = (field_calls(1 << 31, 1 << 29) /
                        field_calls(1 << 32, 1 << 28))
    receipt = {
        "kind": "n83_q1064_portable_equal_area_shape_paired",
        "proposal_id": "Q1064", "candidate_id": None, "run_id": None,
        "curve_id": screen["curve_id"],
        "curve_identity_record": screen["curve_identity_record"],
        "isogeny": "none",
        "public_target": target,
        "factor_base": screen["factor_base"],
        "query_start": QUERY_START,
        "comparison": "same frozen target, affine table/query schedules, source, host, and table-query area; only M/R shape changes",
        "run_order_shape_log2": [list(shape) for shape in ORDER],
        "rows": rows,
        "bounded_modeled_field_call_ratio_M24R20_over_M25R19": model_ratio,
        "full_size_modeled_field_call_ratio_M31R29_over_M32R28": full_model_ratio,
        "bounded_wall_ratio_M24R20_over_M25R19_paired": full_ratios,
        "bounded_wall_ratio_M24R20_over_M25R19_median":
            statistics.median(full_ratios),
        "verified_natural_relation_count": 0,
        "complete_solve_work_log2": None,
        "limits": [
            "A bounded ARM shape comparison is not a physical-x86 full-size speedup or a memory-safety gate for M32.",
            "Equal descriptor-query area is a model comparison, not empirically equal relation yield.",
            "Zero-hit controls do not estimate natural relation yield.",
        ],
        "runtime_info_sha256": sha(args.runtime_info),
        "frozen_receipt_sha256": sha(FROZEN),
        "base_file_sha256": sha(base),
        "native_source_sha256": sha(SOURCE),
        "bloom_core_sha256": sha(CORE),
        "native_pairs_sha256": sha(PAIRS),
        "compiled_binary_sha256": sha(binary),
        "compiler_command": compile_command,
        "source_sha256": sha(Path(__file__)),
        "runtime": {"python": sys.version,
                    "platform": platform.platform()},
    }
    args.out.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({
        "proposal_id": "Q1064",
        "bounded_wall_ratio_M24R20_over_M25R19_median": receipt[
            "bounded_wall_ratio_M24R20_over_M25R19_median"],
        "out": str(args.out),
    }), flush=True)


if __name__ == "__main__":
    main()
