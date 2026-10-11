#!/usr/bin/env python3
"""Planted exact-hit control for a nonzero n=83 table shard."""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
sys.path.insert(0, str(CODEGEN))

import curves
import field
from bench_n83_full_base import CompactOrbitBase
from bench_n83_knownlog import load_keys_logs
from bench_native_n83_table import verify_hit
from orbit_key import OrbitKey
from pair_schedule import affine_rank, cross_orbit_pair, unordered_pair
from run_n23 import sha


def main():
    base_receipt = json.loads((HERE / "runs" /
                               "n83_knownlog_orbit_base.json").read_text())
    schedule = json.loads((HERE / "runs" /
                           "n53_n83_unique_schedule_perf.json").read_text())["runs"][1]
    record = base_receipt["factor_base"]
    key_path = HERE / record["key_and_log_file"]
    assert sha(key_path) == record["key_and_log_file_sha256"]
    keys, logs = load_keys_logs(key_path)
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    base = CompactOrbitBase(orbit, keys)
    assert len(base) == record["actual_usable_points_B_before_folding"]
    table_start = 1024
    t = schedule["table_schedule"]
    q = schedule["query_schedule"]
    table_rank = affine_rank(table_start,
                             schedule["cross_orbit_zero_pair_class_domain"],
                             t["step"], t["offset"])
    oi, oj, relative = cross_orbit_pair(table_rank, len(keys), 166)
    query_rank = affine_rank(0, schedule["unordered_query_pair_domain"],
                             q["step"], q["offset"])
    qi, qj = unordered_pair(query_rank, len(base))
    fixture = None
    for index in (oi * 166, oj * 166 + relative, qi, qj):
        fixture = curve.add(fixture, base[index])
    assert fixture is not None and curve.onCurve(fixture)
    binary = Path("/private/tmp/ecc2k83-native-bloom-shard-control")
    source = HERE / "native_n83_bloom.cpp"
    subprocess.run(["clang++", "-O3", "-std=c++17",
                    "-march=armv8.2-a+crypto", str(source), "-o",
                    str(binary)], check=True)
    command = [
        str(binary), str(key_path),
        format(onb.toCoords(fixture[0]), "x"),
        format(onb.toCoords(fixture[1]), "x"),
        "4096", "256", "256", str(t["step"]), str(t["offset"]),
        str(q["step"]), str(q["offset"]),
        "20", "14", "0", "4", str(table_start),
    ]
    native = json.loads(subprocess.run(
        command, check=True, capture_output=True, text=True).stdout)
    assert native["table_start"] == table_start
    assert native["query_start"] == 0
    assert native["exact_hit_queries"] >= 1
    hit = next(hit for hit in native["hits"]
               if hit["table_position"] == table_start and
               hit["query_position"] == 0)
    identity = base_receipt["curve_identity_record"]["curve"]
    certificate = verify_hit(
        curve, orbit, base, logs, fixture, tuple(identity["generator"]),
        identity["subgroup_order"],
        record["frobenius_eigenvalue_mod_r"], hit, schedule)
    assert certificate["independent_scalar_replay"] is True
    print(json.dumps({
        "curve_id": base_receipt["curve_id"],
        "table_start": table_start,
        "query_start": 0,
        "bits_per_key": 20,
        "hashes": 14,
        "exact_hit_queries": native["exact_hit_queries"],
        "fixture_target": list(fixture),
        "verified_relation": certificate,
        "native_source_sha256": sha(source),
        "binary_sha256": sha(binary),
        "natural_relation_yield": False,
    }, indent=2))


if __name__ == "__main__":
    main()
