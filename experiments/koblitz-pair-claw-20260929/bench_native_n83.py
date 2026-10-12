#!/usr/bin/env python3
"""Build, cross-check, and time the bounded native n83 pair kernel."""

import hashlib
import json
import platform
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
GENERATED = HERE.parents[1] / "ecc2k130" / "runner" / "generated" / "eccF83.h"
REFERENCE = HERE.parent / "ecc2k130-quotient-pair-probe-20260926" / "runs" / "n83_perf_prefix.json"
BASE_RECEIPT = HERE / "runs" / "n83_knownlog_orbit_base.json"
SCHEDULE = HERE / "runs" / "n53_n83_unique_schedule_perf.json"
SOURCE = HERE / "native_n83_pairs.cpp"
OUTPUT = HERE / "runs" / "n83_native_pair_perf.json"
BINARY = Path("/private/tmp/ecc2k83-native-pairs")
SAMPLES = 1 << 20
BATCH_SIZES = (64, 256, 1024)
REPETITIONS = 3
sys.path.insert(0, str(CODEGEN))

import curves
import field
from batch_quotient import x_orbit_key
from bench_n83_full_base import CompactOrbitBase
from bench_n83_knownlog import load_keys_logs
from orbit_key import OrbitKey
from pair_schedule import affine_rank, cross_orbit_pair, unordered_pair
from run_n23 import frozen, sha


def main():
    reference = json.loads(REFERENCE.read_text())
    base_receipt = json.loads(BASE_RECEIPT.read_text())
    scheduled = json.loads(SCHEDULE.read_text())["runs"][1]
    identity = reference["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert reference["curve_id"] == base_receipt["curve_id"] == scheduled["curve_id"] == curve_id
    assert scheduled["proposal_id"] == "Q1045"
    record = base_receipt["factor_base"]
    assert record["actual_usable_points_B_before_folding"] == 4000102
    assert record["signed_frobenius_columns"] == 24097
    key_path = HERE / record["key_and_log_file"]
    assert sha(key_path) == record["key_and_log_file_sha256"]
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    keys, _ = load_keys_logs(key_path)
    base = CompactOrbitBase(orbit, keys)
    target = tuple(reference["workload"]["target"])
    assert curve.onCurve(target)
    table_schedule = scheduled["table_schedule"]
    query_schedule = scheduled["query_schedule"]
    cross_domain = scheduled["cross_orbit_zero_pair_class_domain"]
    query_domain = scheduled["unordered_query_pair_domain"]
    expected_table = []
    expected_query = []
    for position in range(256):
        rank = affine_rank(position, cross_domain,
                           table_schedule["step"], table_schedule["offset"])
        i, j, shift = cross_orbit_pair(rank, len(keys), 166)
        expected_table.append(format(x_orbit_key(
            orbit, curve.add(base[i * 166], base[j * 166 + shift])), "x"))
        rank = affine_rank(position, query_domain,
                           query_schedule["step"], query_schedule["offset"])
        i, j = unordered_pair(rank, len(base))
        pair = curve.add(base[i], base[j])
        expected_query.append(format(x_orbit_key(
            orbit, curve.add(target, curve.neg(pair))), "x"))

    compile_command = [
        "clang++", "-O3", "-std=c++17", "-march=armv8.2-a+crypto",
        str(SOURCE), "-o", str(BINARY),
    ]
    subprocess.run(compile_command, check=True)
    batch_rows = []
    for batch_size in BATCH_SIZES:
        command = [
            str(BINARY), str(key_path),
            format(onb.toCoords(target[0]), "x"),
            format(onb.toCoords(target[1]), "x"),
            str(SAMPLES), str(batch_size),
            str(table_schedule["step"]), str(table_schedule["offset"]),
            str(query_schedule["step"]), str(query_schedule["offset"]),
            str(REPETITIONS),
        ]
        raw = subprocess.run(command, check=True, capture_output=True, text=True)
        native = json.loads(raw.stdout)
        assert native["actual_B"] == len(base)
        assert native["table_first_256_xkeys_hex"] == expected_table
        assert native["query_first_256_xkeys_hex"] == expected_query
        table_each = [seconds * 1e9 / SAMPLES
                      for seconds in native["table_seconds_each"]]
        query_each = [seconds * 1e9 / SAMPLES
                      for seconds in native["query_seconds_each"]]
        batch_rows.append({
            "batch_size": batch_size,
            "table_ns_per_sample_each": table_each,
            "query_ns_per_sample_each": query_each,
            "table_ns_per_sample_median": statistics.median(table_each),
            "query_ns_per_sample_median": statistics.median(query_each),
            "native_table_xor_checksum_hex": native["table_xor_checksum_hex"],
            "native_query_xor_checksum_hex": native["query_xor_checksum_hex"],
        })
    assert len({row["native_table_xor_checksum_hex"]
                for row in batch_rows}) == 1
    assert len({row["native_query_xor_checksum_hex"]
                for row in batch_rows}) == 1
    chosen = min(batch_rows, key=lambda row: row["query_ns_per_sample_median"])
    report = {
        "kind": "n83_knownlog_base_native_quotient_pair_stage_benchmark",
        "scope": "bounded native table and target-complement pair stages; no large table, target relation, or DLP",
        "proposal_id": "Q1046", "candidate_id": None, "run_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "isogeny": "none", "public_target": list(target),
        "factor_base": record,
        "samples_per_phase": SAMPLES,
        "timing_repetitions": REPETITIONS,
        "batch_rows": batch_rows,
        "chosen_batch_size_by_query_median": chosen["batch_size"],
        "table_ns_per_sample_median": chosen["table_ns_per_sample_median"],
        "query_ns_per_sample_median": chosen["query_ns_per_sample_median"],
        "native_first_256_table_keys_match_python": True,
        "native_first_256_query_keys_match_python": True,
        "native_table_xor_checksum_hex": chosen["native_table_xor_checksum_hex"],
        "native_query_xor_checksum_hex": chosen["native_query_xor_checksum_hex"],
        "verified_relation_count": 0,
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "compiler_command": compile_command,
        "compiler_version": subprocess.run(["clang++", "--version"],
                                           check=True, capture_output=True,
                                           text=True).stdout.splitlines()[0],
        "runtime": {"python": sys.version, "platform": platform.platform()},
        "source_sha256": sha(Path(__file__)),
        "native_source_sha256": sha(SOURCE),
        "compiled_binary_sha256": sha(BINARY),
        "generated_field_sha256": sha(GENERATED),
        "base_receipt_sha256": sha(BASE_RECEIPT),
        "key_and_log_file_sha256": sha(key_path),
        "schedule_receipt_sha256": sha(SCHEDULE),
        "reference_sha256": sha(REFERENCE),
        "local_dependency_sha256": {
            name: sha(HERE / name) for name in (
                "batch_quotient.py", "bench_n83_full_base.py",
                "bench_n83_knownlog.py", "orbit_key.py",
                "pair_schedule.py", "run_n23.py")
        },
        "codegen_dependency_sha256": {
            name: sha(CODEGEN / name)
            for name in ("curves.py", "field.py")
        },
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "curve_id": curve_id,
        "table_ns_per_sample_median": report["table_ns_per_sample_median"],
        "query_ns_per_sample_median": report["query_ns_per_sample_median"],
        "chosen_batch_size": chosen["batch_size"],
        "first_256_keys_each_phase_verified": True,
    }))


if __name__ == "__main__":
    main()
