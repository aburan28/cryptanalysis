#!/usr/bin/env python3
"""Materialize bounded exact n83 quotient tables and time real lookups."""

import hashlib
import json
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
SOURCE = HERE / "native_n83_table.cpp"
PAIRS_SOURCE = HERE / "native_n83_pairs.cpp"
OUTPUT = HERE / "runs" / "n83_native_exact_table_perf.json"
BINARY = Path("/private/tmp/ecc2k83-native-table")
TABLE_LOG2 = (20, 24, 26, 28)
QUERY_PAIRS = 1 << 20
BATCH = 1024
sys.path.insert(0, str(CODEGEN))

import curves
import field
from bench_n83_knownlog import load_keys_logs
from bench_n83_full_base import CompactOrbitBase
from orbit_key import OrbitKey
from pair_schedule import affine_rank, cross_orbit_pair, unordered_pair
from run_n23 import frozen, sha


def verify_hit(curve, orbit, base, canonical_logs, target, generator,
               order, eigen, hit, schedule):
    table = schedule["table_schedule"]
    query = schedule["query_schedule"]
    rank0 = affine_rank(hit["table_position"],
                        schedule["cross_orbit_zero_pair_class_domain"],
                        table["step"], table["offset"])
    orbit_i, orbit_j, relative = cross_orbit_pair(
        rank0, len(canonical_logs), 166)
    first0, second0 = orbit_i * 166, orbit_j * 166 + relative
    rank1 = affine_rank(hit["query_position"],
                        schedule["unordered_query_pair_domain"],
                        query["step"], query["offset"])
    first1, second1 = unordered_pair(rank1, len(base))
    zero_pair = curve.add(base[first0], base[second0])
    query_pair = curve.add(base[first1], base[second1])
    complement = curve.add(target, curve.neg(query_pair))
    key0, exponent0, sign0 = orbit.canonical(zero_pair)
    key1, exponent1, sign1 = orbit.canonical(complement)
    assert key0 == key1
    assert key0 >> 83 == int(hit["x_key_hex"], 16)
    shift = (exponent0 - exponent1) % 83
    sign = sign0 * sign1
    left = [curve.frob(base[first0], shift),
            curve.frob(base[second0], shift)]
    if sign < 0:
        left = [curve.neg(point) for point in left]
    points = left + [base[first1], base[second1]]
    assert all(points[i] != curve.neg(points[j])
               for i in range(4) for j in range(i))
    total = None
    for point in points:
        total = curve.add(total, point)
    assert total == target
    eigen_powers = [pow(eigen, i, order) for i in range(83)]

    def log_at(index):
        orbit_index, within = divmod(index, 166)
        sign_at = -1 if within >= 83 else 1
        return sign_at * eigen_powers[within % 83] * canonical_logs[orbit_index] % order

    recovered = (sign * eigen_powers[shift] *
                 (log_at(first0) + log_at(second0)) +
                 log_at(first1) + log_at(second1)) % order
    assert curve.mul(generator, recovered) == target
    return {
        "verified_relation_points": [list(point) for point in points],
        "zero_pair_indices": [first0, second0],
        "query_pair_indices": [first1, second1],
        "frobenius_shift": shift,
        "sign": sign,
        "recovered_scalar": recovered,
        "independent_scalar_replay": True,
    }


def main():
    reference = json.loads(REFERENCE.read_text())
    base_receipt = json.loads(BASE_RECEIPT.read_text())
    scheduled = json.loads(SCHEDULE.read_text())["runs"][1]
    identity = reference["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert reference["curve_id"] == base_receipt["curve_id"] == scheduled["curve_id"] == curve_id
    record = base_receipt["factor_base"]
    key_path = HERE / record["key_and_log_file"]
    assert sha(key_path) == record["key_and_log_file_sha256"]
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    target = tuple(reference["workload"]["target"])
    generator = tuple(identity["curve"]["generator"])
    order = identity["curve"]["subgroup_order"]
    assert curve.onCurve(target)
    assert curve.mul(generator, order) is None
    compiler_command = [
        "clang++", "-O3", "-std=c++17", "-march=armv8.2-a+crypto",
        str(SOURCE), "-o", str(BINARY),
    ]
    subprocess.run(compiler_command, check=True)
    rows = []
    verified_hits = []
    base = None
    for exponent in TABLE_LOG2:
        M = 1 << exponent
        command = [
            str(BINARY), str(key_path),
            format(onb.toCoords(target[0]), "x"),
            format(onb.toCoords(target[1]), "x"),
            str(M), str(QUERY_PAIRS), str(BATCH),
            str(scheduled["table_schedule"]["step"]),
            str(scheduled["table_schedule"]["offset"]),
            str(scheduled["query_schedule"]["step"]),
            str(scheduled["query_schedule"]["offset"]),
        ]
        raw = subprocess.run(command, check=True, capture_output=True, text=True)
        row = json.loads(raw.stdout)
        assert row["actual_B"] == 4000102
        assert row["table_descriptors"] == M
        assert row["query_pairs"] == QUERY_PAIRS
        assert row["table_distinct_keys"] + row["table_duplicate_keys"] == M
        assert row["table_capacity"] * row["table_slot_bytes"] == row["table_bytes"]
        row["table_ns_per_descriptor"] = row["table_seconds"] * 1e9 / M
        row["query_ns_per_pair_including_exact_lookup"] = (
            row["query_seconds"] * 1e9 / QUERY_PAIRS)
        if row["key_hits"]:
            if base is None:
                keys, logs = load_keys_logs(key_path)
                base = CompactOrbitBase(orbit, keys)
                eigen = record["frobenius_eigenvalue_mod_r"]
            for hit in row["hits"]:
                started = time.perf_counter_ns()
                certificate = verify_hit(
                    curve, orbit, base, logs, target, generator, order,
                    eigen, hit, scheduled)
                certificate["python_relation_and_scalar_check_ns"] = (
                    time.perf_counter_ns() - started)
                verified_hits.append(certificate)
        rows.append(row)
    report = {
        "kind": "n83_knownlog_exact_xkey_hash_table_and_target_lookup_benchmark",
        "scope": "bounded materialized tables and unique target query pairs; no large-table solve unless a verified hit occurs",
        "proposal_id": "Q1047", "candidate_id": None, "run_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "isogeny": "none", "public_target": list(target),
        "factor_base": record,
        "table_log2_sizes": list(TABLE_LOG2),
        "query_pairs_each_size": QUERY_PAIRS,
        "batch_size": BATCH, "runs": rows,
        "verified_hits": verified_hits,
        "verified_relation_count": len(verified_hits),
        "verified_single_target_dlp": bool(verified_hits),
        "complete_work_log2": None,
        "table_algorithm": "12-byte exact x-key slots, linear probing, 70% requested occupancy; no witnesses stored, replay deterministic table schedule on a hit",
        "online_interval_if_hit": "first target-complement query through native table replay, Python relation verification, and independent scalar replay",
        "compiler_command": compiler_command,
        "compiler_version": subprocess.run(["clang++", "--version"],
                                           check=True, capture_output=True,
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
                "bench_n83_knownlog.py", "bench_n83_full_base.py",
                "orbit_key.py", "pair_schedule.py", "run_n23.py")
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
            "table_ns_per_descriptor": row["table_ns_per_descriptor"],
            "query_ns_per_pair": row[
                "query_ns_per_pair_including_exact_lookup"],
            "table_bytes": row["table_bytes"],
            "key_hits": row["key_hits"],
        } for exponent, row in zip(TABLE_LOG2, rows)],
        "verified_relation_count": len(verified_hits),
    }))


if __name__ == "__main__":
    main()
