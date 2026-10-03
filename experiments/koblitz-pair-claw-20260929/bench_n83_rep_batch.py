#!/usr/bin/env python3
"""Pair native n83 representative-batch sizes on one frozen rectangle."""

import argparse
import hashlib
import json
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
ORDER = (8, 16, 32, 32, 16, 8)
M = 1 << 24
R = 1 << 20
QUERY_START = 1 << 30


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def modeled_field_calls(batch):
    inversions = 2 * ((M + 1023) // 1024) + 2 * ((R + batch - 1) // batch)
    return 26 * M + 13 * R + 13 * R * 83 + 90 * inversions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch-dir", type=Path, required=True)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert args.scratch_dir.is_absolute() and args.scratch_dir.is_dir()
    assert not args.out.exists(), "refusing to overwrite benchmark receipt"
    assert json.loads(args.runtime_info.read_text())["status"] == "verified"
    assert platform.machine().lower() in ("arm64", "aarch64")
    screen = json.loads(SCREEN.read_text())
    frozen = json.loads(FROZEN.read_text())
    assert frozen["curve_id"] == screen["curve_id"]
    assert frozen["factor_base"] == screen["factor_base"]
    assert frozen["table_descriptors"] == M
    assert frozen["query_representatives"] == R
    assert frozen["query_start"] == QUERY_START
    base = HERE / screen["factor_base"]["key_and_log_file"]
    assert sha(base) == screen["factor_base"]["key_and_log_file_sha256"]
    onb = field.Onb(83)
    target = frozen["public_target"]
    target_x = format(onb.toCoords(target[0]), "x")
    target_y = format(onb.toCoords(target[1]), "x")
    table = frozen["table_schedule"]
    query = frozen["query_representative_schedule"]
    binary = args.scratch_dir / "ecc2k83-portable-rep-batch"
    compile_command = [
        "c++", "-O3", "-std=c++17", "-march=armv8.2-a+crypto",
        "-DECC2K83_ORBITS=48194", "-DECC2K83_FAST_KEYER=1",
        str(SOURCE), "-o", str(binary),
    ]
    subprocess.run(compile_command, check=True)
    env = os.environ.copy()
    env["ECC2K83_CANDIDATE_TMPDIR"] = str(args.scratch_dir)
    rows = []
    for index, batch in enumerate(ORDER):
        command = [
            str(binary), str(base), target_x, target_y,
            str(M), str(R), "1024", str(table["step"]),
            str(table["offset"]), str(query["step"]),
            str(query["offset"]), "20", "10",
            "0", str(QUERY_START), "4", str(batch),
        ]
        begun = time.perf_counter_ns()
        result = subprocess.run(command, text=True, capture_output=True,
                                env=env)
        wall = (time.perf_counter_ns() - begun) / 1e9
        row = {"index": index, "representative_batch": batch,
               "native_wall_seconds": wall,
               "modeled_native_field_calls": str(modeled_field_calls(batch))}
        if result.returncode:
            row.update(status="failed", returncode=result.returncode,
                       stderr_tail=result.stderr[-4000:])
        else:
            native = json.loads(result.stdout)
            assert native["actual_B"] == screen["factor_base"][
                "actual_usable_points_B_before_folding"]
            assert native["table_descriptors"] == M
            assert native["query_representatives"] == R
            assert native["query_start"] == QUERY_START
            assert native["representative_batch"] == batch
            assert native["bloom_bits_per_key"] == 20
            assert native["bloom_hashes"] == 10
            assert native["candidate_store_mode"] == "unlinked_file"
            row.update(status="completed", native_result=native)
        rows.append(row)
        print(json.dumps({"index": index, "batch": batch,
                          "status": row["status"],
                          "query_seconds": row.get("native_result", {}).get(
                              "query_seconds")}), flush=True)
    complete = all(row["status"] == "completed" for row in rows)
    exact_outcomes_match = (complete and len({
        (row["native_result"]["exact_hit_queries"],
         row["native_result"]["bloom_positive_queries"])
        for row in rows}) == 1)
    query_ratios = {}
    wall_ratios = {}
    if complete and exact_outcomes_match:
        for batch, first, second in ((16, 1, 4), (32, 2, 3)):
            query_ratios[str(batch)] = [
                rows[0]["native_result"]["query_seconds"] /
                rows[first]["native_result"]["query_seconds"],
                rows[5]["native_result"]["query_seconds"] /
                rows[second]["native_result"]["query_seconds"],
            ]
            wall_ratios[str(batch)] = [
                rows[0]["native_wall_seconds"] /
                rows[first]["native_wall_seconds"],
                rows[5]["native_wall_seconds"] /
                rows[second]["native_wall_seconds"],
            ]
    receipt = {
        "kind": "n83_q1070_portable_representative_batch_paired",
        "proposal_id": "Q1070", "candidate_id": None, "run_id": None,
        "curve_id": screen["curve_id"],
        "curve_identity_record": screen["curve_identity_record"],
        "isogeny": "none", "public_target": target,
        "factor_base": screen["factor_base"],
        "table_descriptors": M, "query_representatives": R,
        "query_start": QUERY_START,
        "comparison": "same frozen public target, table/query schedules, native source, host, and resource shape; only representative batch changes",
        "run_order_representative_batch": list(ORDER),
        "rows": rows, "all_runs_completed": complete,
        "exact_outcomes_match": exact_outcomes_match,
        "query_speedup_vs_batch8_paired_ratios": query_ratios,
        "query_speedup_vs_batch8_medians": {
            key: statistics.median(value)
            for key, value in query_ratios.items()},
        "full_wall_speedup_vs_batch8_paired_ratios": wall_ratios,
        "full_wall_speedup_vs_batch8_medians": {
            key: statistics.median(value)
            for key, value in wall_ratios.items()},
        "verified_natural_relation_count": 0 if complete and
            all(row["native_result"]["exact_hit_queries"] == 0
                for row in rows) else None,
        "complete_solve_work_log2": None,
        "limits": [
            "A bounded ARM stage comparison is not a physical-x86 full-size speedup or a natural-yield estimate.",
            "Native field-call totals are modeled and omit keying, Bloom, memory, and disk work.",
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
    print(json.dumps({"proposal_id": "Q1070",
                      "query_speedup_medians": receipt[
                          "query_speedup_vs_batch8_medians"],
                      "full_wall_speedup_medians": receipt[
                          "full_wall_speedup_vs_batch8_medians"],
                      "out": str(args.out)}), flush=True)


if __name__ == "__main__":
    main()
