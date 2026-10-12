#!/usr/bin/env python3
"""Pair direct and pair-orbit n=83 Bloom query timings in ABBA order."""

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
REFERENCE = HERE.parent / "ecc2k130-quotient-pair-probe-20260926" / "runs" / "n83_perf_prefix.json"
BASE = HERE / "runs" / "n83_knownlog_orbit_base.json"
SCHEDULE = HERE / "runs" / "n53_n83_unique_schedule_perf.json"
DIRECT_SOURCE = HERE / "native_n83_bloom.cpp"
ORBIT_SOURCE = HERE / "native_n83_orbit_query.cpp"
CORE = HERE / "native_n83_bloom_core.hpp"
PAIRS = HERE / "native_n83_pairs.cpp"
OUTPUT = HERE / "runs" / "n83_orbit_reuse_vs_direct_ABBA_bounded.json"
DIRECT_BINARY = Path("/private/tmp/ecc2k83-native-bloom-ABBA-direct")
ORBIT_BINARY = Path("/private/tmp/ecc2k83-native-bloom-ABBA-orbit")
sys.path.insert(0, str(CODEGEN))

import field
from run_n23 import sha


def main():
    reference = json.loads(REFERENCE.read_text())
    base_receipt = json.loads(BASE.read_text())
    scheduled = json.loads(SCHEDULE.read_text())["runs"][1]
    record = base_receipt["factor_base"]
    curve_id = reference["curve_id"]
    assert curve_id == base_receipt["curve_id"] == scheduled["curve_id"]
    key_path = HERE / record["key_and_log_file"]
    assert sha(key_path) == record["key_and_log_file_sha256"]
    target = reference["workload"]["target"]
    onb = field.Onb(83)
    M = 1 << 24
    R = 1 << 18
    Q = 166 * R
    t = scheduled["table_schedule"]
    q = scheduled["query_schedule"]
    d_cross = scheduled["cross_orbit_zero_pair_class_domain"]
    q_offset = (t["offset"] + 123456789) % d_cross
    compilers = [
        ["clang++", "-O3", "-std=c++17", "-march=armv8.2-a+crypto",
         str(DIRECT_SOURCE), "-o", str(DIRECT_BINARY)],
        ["clang++", "-O3", "-std=c++17", "-march=armv8.2-a+crypto",
         str(ORBIT_SOURCE), "-o", str(ORBIT_BINARY)],
    ]
    for command in compilers:
        subprocess.run(command, check=True)
    common = [
        str(key_path), format(onb.toCoords(target[0]), "x"),
        format(onb.toCoords(target[1]), "x"),
    ]
    direct_args = [
        *common, str(M), str(Q), "1024",
        str(t["step"]), str(t["offset"]),
        str(q["step"]), str(q["offset"]),
        "20", "14", "0", "8", "0",
    ]
    orbit_args = [
        *common, str(M), str(R), "1024",
        str(t["step"]), str(t["offset"]),
        str(t["step"]), str(q_offset),
        "20", "14", "0", "0", "8", "8",
    ]
    config = {
        "direct": (DIRECT_BINARY, direct_args),
        "orbit": (ORBIT_BINARY, orbit_args),
    }
    rows = []
    for variant in ("direct", "orbit", "orbit", "direct"):
        binary, args = config[variant]
        native = json.loads(subprocess.run(
            [str(binary), *args], check=True,
            capture_output=True, text=True).stdout)
        assert native["actual_B"] == record[
            "actual_usable_points_B_before_folding"]
        assert native["table_descriptors"] == M
        assert (native["query_pairs"] if variant == "direct" else
                native["lifted_query_pairs"]) == Q
        rows.append({
            "variant": variant,
            "native": native,
            "query_ns_per_lifted_pair": 1e9 * native[
                "query_seconds"] / Q,
            "binary_sha256": sha(binary),
        })
        print(variant, rows[-1]["query_ns_per_lifted_pair"],
              flush=True)
    means = {variant: sum(row["query_ns_per_lifted_pair"]
                          for row in rows if row["variant"] == variant) / 2
             for variant in ("direct", "orbit")}
    assert rows[0]["native"]["bloom_positive_queries"] == rows[3][
        "native"]["bloom_positive_queries"]
    assert rows[1]["native"]["bloom_positive_queries"] == rows[2][
        "native"]["bloom_positive_queries"]
    report = {
        "kind": "n83_orbit_reuse_vs_direct_ABBA_bounded_query",
        "scope": "paired bounded query timings with different deterministic pair schedules; source-stage diagnostic, not a complete solve",
        "proposal_id": "Q1050", "candidate_id": None,
        "curve_id": curve_id,
        "curve_identity_record": reference["curve_identity_record"],
        "isogeny": "none",
        "factor_base_enumerated_set_sha256": record[
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": record[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": record[
            "signed_frobenius_columns"],
        "table_descriptors": M,
        "query_representatives_orbit": R,
        "lifted_query_pairs_each": Q,
        "bits_per_key": 20,
        "hashes": 14,
        "workers": 8,
        "direct_query_schedule": q,
        "orbit_query_representative_schedule": {
            "domain": d_cross, "step": t["step"],
            "offset": q_offset},
        "different_query_pair_schedules": True,
        "concurrent_full_shard_running": True,
        "rows": rows,
        "mean_query_ns_per_pair": means,
        "direct_to_orbit_query_speedup": (
            means["direct"] / means["orbit"]),
        "ordinary_target_exact_hits": [row["native"][
            "exact_hit_queries"] for row in rows],
        "complete_solve_work_log2": None,
        "compiler_commands": compilers,
        "direct_source_sha256": sha(DIRECT_SOURCE),
        "orbit_source_sha256": sha(ORBIT_SOURCE),
        "bloom_core_sha256": sha(CORE),
        "native_pairs_sha256": sha(PAIRS),
        "base_receipt_sha256": sha(BASE),
        "schedule_receipt_sha256": sha(SCHEDULE),
        "reference_sha256": sha(REFERENCE),
        "source_sha256": sha(Path(__file__)),
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": {"python": sys.version,
                    "platform": platform.platform()},
        "timing_limit": "ABBA pairing reduces linear drift, but a separate full-size shard ran concurrently; full-size orbit performance is unmeasured",
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "curve_id": curve_id,
        "speedup": report["direct_to_orbit_query_speedup"],
        "ordinary_target_exact_hits": report[
            "ordinary_target_exact_hits"],
    }), flush=True)


if __name__ == "__main__":
    main()
