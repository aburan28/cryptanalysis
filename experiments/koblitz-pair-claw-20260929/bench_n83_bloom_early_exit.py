#!/usr/bin/env python3
"""Paired n83 test of short-circuiting a negative Bloom lookup."""

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
ORDER = ("base", "early", "early", "base")
FROZEN_M, FROZEN_R, QUERY_START = 1 << 24, 1 << 20, 1 << 30

OLD_CONTAINS = """    bool contains(V key) const {
        bool found = true;
        positions(key, [&](size_t b, unsigned bit) {
            found &= bool(blocks[b].word[bit >> 6] &
                          (U(1) << (bit & 63)));
        });
        return found;
    }
"""
NEW_CONTAINS = """    bool contains(V key) const {
        U h = hash83(key);
        size_t block0 = size_t(h % blocks.size());
        size_t block1 = size_t(mix64(h ^ 0xbb67ae8584caa73bull) %
                               blocks.size());
        U stream = h ^ 0x6a09e667f3bcc909ull;
        for (unsigned j = 0; j < hashes; ++j) {
            stream += 0x9e3779b97f4a7c15ull;
            size_t block = (j & 1) ? block1 : block0;
            unsigned bit = unsigned(mix64(stream) & 511);
            if (!(blocks[block].word[bit >> 6] & (U(1) << (bit & 63))))
                return false;
        }
        return true;
    }
"""


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch-dir", type=Path, required=True)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--table-log2", type=int, default=24)
    parser.add_argument("--query-reps-log2", type=int, default=20)
    args = parser.parse_args()
    assert 18 <= args.table_log2 <= 24
    assert 10 <= args.query_reps_log2 <= 20
    M, R = 1 << args.table_log2, 1 << args.query_reps_log2
    assert args.scratch_dir.is_absolute() and args.scratch_dir.is_dir()
    assert not args.out.exists(), "refusing to overwrite benchmark receipt"
    assert json.loads(args.runtime_info.read_text())["status"] == "verified"
    assert platform.machine().lower() in ("arm64", "aarch64")

    screen = json.loads(SCREEN.read_text())
    frozen = json.loads(FROZEN.read_text())
    assert frozen["curve_id"] == screen["curve_id"]
    assert frozen["factor_base"] == screen["factor_base"]
    assert (frozen["table_descriptors"], frozen["query_representatives"],
            frozen["query_start"]) == (FROZEN_M, FROZEN_R, QUERY_START)
    base = HERE / screen["factor_base"]["key_and_log_file"]
    assert sha(base) == screen["factor_base"]["key_and_log_file_sha256"]

    core_text = CORE.read_text()
    source_text = SOURCE.read_text()
    old_include = '#include "native_n83_bloom_core_portable.hpp"'
    assert core_text.count(OLD_CONTAINS) == 1
    assert source_text.count(old_include) == 1
    variant_core = args.scratch_dir / "n83_early_exit.hpp"
    variant_source = args.scratch_dir / "n83_early_exit.cpp"
    variant_core.write_text(core_text.replace(OLD_CONTAINS, NEW_CONTAINS))
    variant_source.write_text(source_text.replace(
        old_include, '#include "n83_early_exit.hpp"'))
    binaries = {name: args.scratch_dir / f"n83-bloom-{name}"
                for name in ("base", "early")}
    compile_commands = {}
    for name, path in (("base", SOURCE), ("early", variant_source)):
        command = ["c++", "-O3", "-std=c++17", "-march=armv8.2-a+crypto",
                   "-DECC2K83_ORBITS=48194", "-DECC2K83_FAST_KEYER=1",
                   "-I", str(HERE), str(path), "-o", str(binaries[name])]
        subprocess.run(command, check=True)
        compile_commands[name] = command

    onb = field.Onb(83)
    target_x, target_y = (format(onb.toCoords(v), "x")
                          for v in frozen["public_target"])
    table, query = (frozen["table_schedule"],
                    frozen["query_representative_schedule"])
    env = os.environ.copy()
    env["ECC2K83_CANDIDATE_TMPDIR"] = str(args.scratch_dir)
    rows = []
    for index, name in enumerate(ORDER):
        command = [str(binaries[name]), str(base), target_x, target_y,
                   str(M), str(R), "1024", str(table["step"]),
                   str(table["offset"]), str(query["step"]),
                   str(query["offset"]), "20", "10", "0",
                   str(QUERY_START), "4", "8"]
        started = time.perf_counter_ns()
        result = subprocess.run(command, text=True, capture_output=True,
                                env=env)
        row = {"index": index, "variant": name,
               "native_wall_seconds": (time.perf_counter_ns() - started) / 1e9}
        if result.returncode:
            row.update(status="failed", returncode=result.returncode,
                       stderr_tail=result.stderr[-4000:])
        else:
            native = json.loads(result.stdout)
            assert native["actual_B"] == screen["factor_base"][
                "actual_usable_points_B_before_folding"]
            assert (native["table_descriptors"],
                    native["query_representatives"],
                    native["query_start"],
                    native["bloom_bits_per_key"],
                    native["bloom_hashes"],
                    native["representative_batch"]) == (M, R, QUERY_START,
                                                         20, 10, 8)
            row.update(status="completed", native_result=native)
        rows.append(row)
        print(json.dumps({"index": index, "variant": name,
                          "status": row["status"],
                          "query_seconds": row.get("native_result", {}).get(
                              "query_seconds")}), flush=True)

    complete = all(row["status"] == "completed" for row in rows)
    outcome_keys = ("bloom_positive_queries", "exact_hit_queries",
                    "candidate_spill_bytes", "hits")
    outcomes_match = complete and all(
        row["native_result"][key] == rows[0]["native_result"][key]
        for row in rows for key in outcome_keys)
    query_ratios = []
    wall_ratios = []
    if outcomes_match:
        for base_index, early_index in ((0, 1), (3, 2)):
            query_ratios.append(
                rows[base_index]["native_result"]["query_seconds"] /
                rows[early_index]["native_result"]["query_seconds"])
            wall_ratios.append(rows[base_index]["native_wall_seconds"] /
                               rows[early_index]["native_wall_seconds"])
    receipt = {
        "kind": "n83_q1072_bloom_early_exit_paired",
        "proposal_id": "Q1072", "candidate_id": None, "run_id": None,
        "curve_id": screen["curve_id"],
        "curve_identity_record": screen["curve_identity_record"],
        "isogeny": "none", "public_target": frozen["public_target"],
        "factor_base": screen["factor_base"],
        "table_descriptors": M, "query_representatives": R,
        "query_start": QUERY_START,
        "comparison": "same public target, exact base, schedules, M/R, 20-bit Bloom, ten hashes, batch-8 policy, and host; only Bloom negative-lookup exit changes",
        "run_order_variants": list(ORDER), "rows": rows,
        "all_runs_completed": complete,
        "exact_outcomes_match": outcomes_match,
        "query_speedup_early_exit_paired_ratios": query_ratios,
        "query_speedup_early_exit_median": (statistics.median(query_ratios)
                                           if query_ratios else None),
        "full_wall_speedup_early_exit_paired_ratios": wall_ratios,
        "full_wall_speedup_early_exit_median": (statistics.median(wall_ratios)
                                               if wall_ratios else None),
        "verified_natural_relation_count": (0 if outcomes_match and
            rows[0]["native_result"]["exact_hit_queries"] == 0 else None),
        "complete_solve_work_log2": None,
        "limits": [
            "This bounded ARM stage comparison is not a full-size x86 speedup or a natural-yield estimate.",
            "Native field-call totals are unchanged; keying, Bloom, memory, and disk work are not in that model."],
        "runtime_info_sha256": sha(args.runtime_info),
        "frozen_receipt_sha256": sha(FROZEN),
        "base_file_sha256": sha(base),
        "native_source_sha256": sha(SOURCE),
        "native_core_sha256": sha(CORE),
        "native_pairs_sha256": sha(PAIRS),
        "variant_source_sha256": sha(variant_source),
        "variant_core_sha256": sha(variant_core),
        "compiled_binary_sha256": {name: sha(path)
                                   for name, path in binaries.items()},
        "compiler_commands": compile_commands,
        "source_sha256": sha(Path(__file__)),
        "runtime": {"python": sys.version,
                    "platform": platform.platform()},
    }
    args.out.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"proposal_id": "Q1072",
                      "query_speedup_median": receipt[
                          "query_speedup_early_exit_median"],
                      "full_wall_speedup_median": receipt[
                          "full_wall_speedup_early_exit_median"],
                      "out": str(args.out)}), flush=True)


if __name__ == "__main__":
    main()
