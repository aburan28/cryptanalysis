#!/usr/bin/env python3
"""Planted n83 hit control for the native exact table and witness replay."""

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
REFERENCE = HERE.parent / "ecc2k130-quotient-pair-probe-20260926" / "runs" / "n83_perf_prefix.json"
BASE_RECEIPT = HERE / "runs" / "n83_knownlog_orbit_base.json"
SCHEDULE = HERE / "runs" / "n53_n83_unique_schedule_perf.json"
SOURCE = HERE / "native_n83_table.cpp"
OUTPUT = HERE / "runs" / "n83_native_planted_control.json"
BINARY = Path("/private/tmp/ecc2k83-native-table")
sys.path.insert(0, str(CODEGEN))

import curves
import field
from bench_n83_full_base import CompactOrbitBase
from bench_n83_knownlog import load_keys_logs
from bench_native_n83_table import verify_hit
from orbit_key import OrbitKey
from pair_schedule import affine_rank, cross_orbit_pair, unordered_pair
from run_n23 import frozen, sha


def main():
    reference = json.loads(REFERENCE.read_text())
    base_receipt = json.loads(BASE_RECEIPT.read_text())
    schedule = json.loads(SCHEDULE.read_text())["runs"][1]
    identity = reference["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert reference["curve_id"] == base_receipt["curve_id"] == schedule["curve_id"] == curve_id
    key_path = HERE / base_receipt["factor_base"]["key_and_log_file"]
    assert sha(key_path) == base_receipt["factor_base"]["key_and_log_file_sha256"]
    keys, logs = load_keys_logs(key_path)
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    base = CompactOrbitBase(orbit, keys)
    generator = tuple(identity["curve"]["generator"])
    order = identity["curve"]["subgroup_order"]
    eigen = base_receipt["factor_base"]["frobenius_eigenvalue_mod_r"]
    t = schedule["table_schedule"]
    q = schedule["query_schedule"]
    table_rank = affine_rank(0, schedule["cross_orbit_zero_pair_class_domain"],
                             t["step"], t["offset"])
    orbit_i, orbit_j, relative = cross_orbit_pair(table_rank, len(keys), 166)
    first0, second0 = orbit_i * 166, orbit_j * 166 + relative
    query_rank = affine_rank(0, schedule["unordered_query_pair_domain"],
                             q["step"], q["offset"])
    first1, second1 = unordered_pair(query_rank, len(base))
    target = None
    for index in (first0, second0, first1, second1):
        target = curve.add(target, base[index])
    assert target is not None and curve.onCurve(target)
    compile_command = [
        "clang++", "-O3", "-std=c++17", "-march=armv8.2-a+crypto",
        str(SOURCE), "-o", str(BINARY),
    ]
    subprocess.run(compile_command, check=True)
    command = [
        str(BINARY), str(key_path),
        format(onb.toCoords(target[0]), "x"),
        format(onb.toCoords(target[1]), "x"),
        str(4096), str(256), str(256),
        str(t["step"]), str(t["offset"]),
        str(q["step"]), str(q["offset"]),
    ]
    native = json.loads(subprocess.run(
        command, check=True, capture_output=True, text=True).stdout)
    assert native["key_hits"] >= 1
    assert native["hits"][0]["query_position"] == 0
    assert native["hits"][0]["table_position"] == 0
    started = time.perf_counter_ns()
    certificate = verify_hit(curve, orbit, base, logs, target, generator,
                             order, eigen, native["hits"][0], schedule)
    check_ns = time.perf_counter_ns() - started
    eigen_powers = [pow(eigen, i, order) for i in range(83)]

    def log_at(index):
        orbit_index, within = divmod(index, 166)
        sign = -1 if within >= 83 else 1
        return sign * eigen_powers[within % 83] * logs[orbit_index] % order

    fixture_scalar = sum(log_at(index) for index in
                         (first0, second0, first1, second1)) % order
    assert certificate["recovered_scalar"] == fixture_scalar
    report = {
        "kind": "n83_native_exact_table_planted_hit_control",
        "scope": "fixture assembled from four known base points; tests hit replay and scalar recovery only, not natural relation yield",
        "proposal_id": "Q1047", "candidate_id": None, "run_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "isogeny": "none", "factor_base": base_receipt["factor_base"],
        "planted_control": True, "public_target_used": False,
        "fixture_target": list(target),
        "fixture_scalar_validation_only": fixture_scalar,
        "native_stage": native,
        "verified_relation": certificate,
        "relation_and_scalar_check_ns": check_ns,
        "verified_fixture_dlp": True,
        "natural_relation_yield_measured": False,
        "verified_public_target_dlp_by_quotient_table": False,
        "complete_public_target_work_log2": None,
        "compiler_command": compile_command,
        "source_sha256": sha(Path(__file__)),
        "native_source_sha256": sha(SOURCE),
        "native_pairs_source_sha256": sha(HERE / "native_n83_pairs.cpp"),
        "native_table_driver_source_sha256":
            sha(HERE / "bench_native_n83_table.py"),
        "compiled_binary_sha256": sha(BINARY),
        "base_receipt_sha256": sha(BASE_RECEIPT),
        "schedule_receipt_sha256": sha(SCHEDULE),
        "key_and_log_file_sha256": sha(key_path),
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
        "planted_control": True,
        "native_key_hits": native["key_hits"],
        "recovered_scalar_replayed": True,
    }))


if __name__ == "__main__":
    main()
