#!/usr/bin/env python3
"""Measure bounded n83 Bloom-filter quotient search with exact second pass."""

import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
GENERATED = HERE.parents[1] / "ecc2k130" / "runner" / "generated" / "eccF83.h"
REFERENCE = HERE.parent / "ecc2k130-quotient-pair-probe-20260926" / "runs" / "n83_perf_prefix.json"
BASE_RECEIPT = HERE / "runs" / "n83_knownlog_orbit_base.json"
SCHEDULE = HERE / "runs" / "n53_n83_unique_schedule_perf.json"
SOURCE = HERE / "native_n83_bloom.cpp"
PAIRS_SOURCE = HERE / "native_n83_pairs.cpp"
OUTPUT = HERE / "runs" / "n83_native_bloom_exact_replay_perf.json"
BINARY = Path("/private/tmp/ecc2k83-native-bloom")
TABLE_LOG2 = (24, 28)
QUERY_PAIRS = 1 << 24
BATCH = 1024
BITS_PER_KEY = 24
HASHES = 17
BLOCKS_PER_KEY = 2
sys.path.insert(0, str(CODEGEN))

import curves
import field
from bench_n83_full_base import CompactOrbitBase
from bench_n83_knownlog import load_keys_logs
from bench_native_n83_table import verify_hit
from orbit_key import OrbitKey
from pair_schedule import affine_rank, cross_orbit_pair, unordered_pair
from run_n23 import frozen, sha


def wilson(successes, trials):
    if not trials:
        return [0.0, 1.0]
    z = 1.959963984540054
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(p * (1 - p) / trials +
                         z * z / (4 * trials * trials)) / denominator
    return [max(0.0, center - half), min(1.0, center + half)]


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
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    target = tuple(reference["workload"]["target"])
    generator = tuple(identity["curve"]["generator"])
    order = identity["curve"]["subgroup_order"]
    eigen = record["frobenius_eigenvalue_mod_r"]
    assert curve.onCurve(target) and curve.mul(generator, order) is None
    compiler_command = [
        "clang++", "-O3", "-std=c++17", "-march=armv8.2-a+crypto",
        str(SOURCE), "-o", str(BINARY),
    ]
    subprocess.run(compiler_command, check=True)

    def execute(point, table_entries, query_pairs, batch_size):
        command = [
            str(BINARY), str(key_path),
            format(onb.toCoords(point[0]), "x"),
            format(onb.toCoords(point[1]), "x"),
            str(table_entries), str(query_pairs), str(batch_size),
            str(scheduled["table_schedule"]["step"]),
            str(scheduled["table_schedule"]["offset"]),
            str(scheduled["query_schedule"]["step"]),
            str(scheduled["query_schedule"]["offset"]),
            str(BITS_PER_KEY), str(HASHES),
        ]
        return json.loads(subprocess.run(
            command, check=True, capture_output=True, text=True).stdout)

    rows = []
    verified_hits = []
    base = None
    logs = None
    for exponent in TABLE_LOG2:
        M = 1 << exponent
        row = execute(target, M, QUERY_PAIRS, BATCH)
        assert row["actual_B"] == record["actual_usable_points_B_before_folding"]
        assert row["table_descriptors"] == M and row["query_pairs"] == QUERY_PAIRS
        assert row["bloom_positive_queries"] == (row["false_positive_queries"] +
                                                  row["exact_hit_queries"])
        assert row["exact_hit_queries"] >= row["exact_hit_keys"]
        assert row["bloom_bytes"] == ((M * BITS_PER_KEY + 511) // 512 + 1024) * 64
        assert row["bloom_blocks_per_key"] == BLOCKS_PER_KEY
        assert row["candidate_record_bytes"] == 24
        assert row["candidate_exact_slot_bytes"] == 28
        assert row["candidate_vector_capacity_bytes"] >= (
            row["bloom_positive_queries"] * 24)
        row["build_ns_per_descriptor"] = row["build_seconds"] * 1e9 / M
        row["query_ns_per_pair_including_filter"] = (
            row["query_seconds"] * 1e9 / QUERY_PAIRS)
        row["exact_replay_ns_per_descriptor"] = (
            row["exact_replay_seconds"] * 1e9 / M)
        row["false_positive_rate"] = row["false_positive_queries"] / QUERY_PAIRS
        row["false_positive_rate_wilson95"] = wilson(
            row["false_positive_queries"], QUERY_PAIRS)
        if row["exact_hit_queries"]:
            if base is None:
                keys, logs = load_keys_logs(key_path)
                base = CompactOrbitBase(orbit, keys)
            for hit in row["hits"]:
                certificate = verify_hit(
                    curve, orbit, base, logs, target, generator, order,
                    eigen, hit, scheduled)
                verified_hits.append(certificate)
        rows.append(row)

    if base is None:
        keys, logs = load_keys_logs(key_path)
        base = CompactOrbitBase(orbit, keys)
    t = scheduled["table_schedule"]
    q = scheduled["query_schedule"]
    rank0 = affine_rank(
        0, scheduled["cross_orbit_zero_pair_class_domain"],
        t["step"], t["offset"])
    orbit_i, orbit_j, relative = cross_orbit_pair(rank0, len(keys), 166)
    rank1 = affine_rank(
        0, scheduled["unordered_query_pair_domain"],
        q["step"], q["offset"])
    first1, second1 = unordered_pair(rank1, len(base))
    indices = (orbit_i * 166, orbit_j * 166 + relative, first1, second1)
    fixture_target = None
    for index in indices:
        fixture_target = curve.add(fixture_target, base[index])
    assert fixture_target is not None and curve.onCurve(fixture_target)
    planted = execute(fixture_target, 4096, 256, 256)
    assert planted["exact_hit_queries"] >= 1
    assert planted["hits"][0]["query_position"] == 0
    assert planted["hits"][0]["table_position"] == 0
    started = time.perf_counter_ns()
    planted_certificate = verify_hit(
        curve, orbit, base, logs, fixture_target, generator, order,
        eigen, planted["hits"][0], scheduled)
    planted_check_ns = time.perf_counter_ns() - started

    report = {
        "kind": "n83_knownlog_blocked_bloom_filter_with_exact_second_pass",
        "scope": "bounded public-target stage plus planted correctness control; no large run or ordinary n83 target relation",
        "proposal_id": "Q1048", "candidate_id": None, "run_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "isogeny": "none", "public_target": list(target),
        "factor_base": record,
        "table_log2_sizes": list(TABLE_LOG2),
        "query_pairs_each_size": QUERY_PAIRS,
        "batch_size": BATCH,
        "bloom_bits_per_table_descriptor": BITS_PER_KEY,
        "bloom_hashes_per_key": HASHES,
        "bloom_blocks_per_key": BLOCKS_PER_KEY,
        "public_target_runs": rows,
        "verified_public_target_relations": verified_hits,
        "verified_public_target_quotient_table_dlp": bool(verified_hits),
        "complete_public_target_work_log2": None,
        "planted_control": {
            "fixture_target": list(fixture_target),
            "fixture_from_base_indices": list(indices),
            "native_stage": planted,
            "verified_relation": planted_certificate,
            "verification_ns": planted_check_ns,
            "natural_relation_yield": False,
        },
        "algorithm": "Each exact x key sets 17 independently mixed bits across two 64-byte Bloom blocks; all positives retain query descriptors; the filter is freed; a second deterministic table pass checks every positive in an exact 83-bit candidate table",
        "compiler_command": compiler_command,
        "compiler_version": subprocess.run(
            ["clang++", "--version"], check=True, capture_output=True,
            text=True).stdout.splitlines()[0],
        "runtime": {"python": sys.version, "platform": platform.platform()},
        "source_sha256": sha(Path(__file__)),
        "native_source_sha256": sha(SOURCE),
        "native_pairs_source_sha256": sha(PAIRS_SOURCE),
        "compiled_binary_sha256": sha(BINARY),
        "generated_field_sha256": sha(GENERATED),
        "base_receipt_sha256": sha(BASE_RECEIPT),
        "key_and_log_file_sha256": sha(key_path),
        "schedule_receipt_sha256": sha(SCHEDULE),
        "reference_sha256": sha(REFERENCE),
        "local_dependency_sha256": {
            name: sha(HERE / name) for name in (
                "bench_native_n83_table.py", "bench_n83_knownlog.py",
                "bench_n83_full_base.py", "orbit_key.py", "pair_schedule.py",
                "run_n23.py")
        },
        "codegen_dependency_sha256": {
            name: sha(CODEGEN / name)
            for name in ("curves.py", "field.py")
        },
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "curve_id": curve_id,
        "runs": [{
            "M_log2": exponent,
            "bloom_bytes": row["bloom_bytes"],
            "build_ns_per_descriptor": row["build_ns_per_descriptor"],
            "query_ns_per_pair": row["query_ns_per_pair_including_filter"],
            "false_positive_queries": row["false_positive_queries"],
            "exact_hit_queries": row["exact_hit_queries"],
        } for exponent, row in zip(TABLE_LOG2, rows)],
        "planted_scalar_replayed": True,
    }))


if __name__ == "__main__":
    main()
