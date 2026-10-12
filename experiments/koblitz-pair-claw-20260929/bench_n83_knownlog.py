#!/usr/bin/env python3
"""Bounded quotient-pair sampling on the exact n=83 known-log base."""

import hashlib
import json
import platform
import random
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
BASE_RECEIPT = HERE / "runs" / "n83_knownlog_orbit_base.json"
REFERENCE = (HERE.parent / "ecc2k130-quotient-pair-probe-20260926" /
             "runs" / "n83_perf_prefix.json")
OUTPUT = HERE / "runs" / "n83_knownlog_pair_perf.json"
sys.path.insert(0, str(CODEGEN))

import curves
import field
from bench_n83_full_base import CompactOrbitBase
from bench_steps import CountingOnb
from orbit_key import OrbitKey
from run_n23 import frozen, sha

TABLE_SAMPLES = 100000
QUERY_SAMPLES = 100000
COUNT_SAMPLES = 4096
TABLE_SEED = 830930
QUERY_SEED = 830931


def load_keys_logs(path):
    data = path.read_bytes()
    assert len(data) % 32 == 0
    keys = []
    logs = []
    for offset in range(0, len(data), 32):
        keys.append(int.from_bytes(data[offset:offset + 21], "little"))
        logs.append(int.from_bytes(data[offset + 21:offset + 32], "little"))
    return keys, logs


def main():
    base_receipt = json.loads(BASE_RECEIPT.read_text())
    reference = json.loads(REFERENCE.read_text())
    identity = base_receipt["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert base_receipt["curve_id"] == reference["curve_id"] == curve_id
    key_path = HERE / base_receipt["factor_base"]["key_and_log_file"]
    assert sha(key_path) == base_receipt["factor_base"]["key_and_log_file_sha256"]
    keys, logs = load_keys_logs(key_path)
    assert len(keys) == len(logs) == 24097
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    base = CompactOrbitBase(orbit, keys)
    assert len(base) == 4000102
    generator = tuple(identity["curve"]["generator"])
    target = tuple(reference["workload"]["target"])
    for index in (0, 1, 42, 12048, 24096):
        assert curve.mul(generator, logs[index]) == orbit.point_from_key(keys[index])

    table_rng = random.Random(TABLE_SEED)
    table = {}
    table_start = time.perf_counter_ns()
    for _ in range(TABLE_SAMPLES):
        first = table_rng.randrange(len(base))
        second = table_rng.randrange(len(base))
        pair = curve.add(base[first], base[second])
        if pair is not None:
            table.setdefault(orbit.canonical(pair)[0], (first, second))
    table_ns = time.perf_counter_ns() - table_start
    query_rng = random.Random(QUERY_SEED)
    hits = 0
    query_start = time.perf_counter_ns()
    for _ in range(QUERY_SAMPLES):
        first = query_rng.randrange(len(base))
        second = query_rng.randrange(len(base))
        pair = curve.add(base[first], base[second])
        if pair is not None:
            complement = curve.add(target, curve.neg(pair))
            hits += int(orbit.canonical(complement)[0] in table)
    query_ns = time.perf_counter_ns() - query_start

    counted_onb = CountingOnb(83)
    counted_curve = curves.Curve(counted_onb)
    counted_orbit = OrbitKey(counted_onb)
    counted_base = CompactOrbitBase(counted_orbit, keys)
    counted_table_rng = random.Random(TABLE_SEED)
    for _ in range(COUNT_SAMPLES):
        first = counted_table_rng.randrange(len(counted_base))
        second = counted_table_rng.randrange(len(counted_base))
        pair = counted_curve.add(counted_base[first], counted_base[second])
        if pair is not None:
            counted_orbit.canonical(pair)
    table_field_calls = dict(counted_onb.calls)
    counted_query_rng = random.Random(QUERY_SEED)
    for _ in range(COUNT_SAMPLES):
        first = counted_query_rng.randrange(len(counted_base))
        second = counted_query_rng.randrange(len(counted_base))
        pair = counted_curve.add(counted_base[first], counted_base[second])
        if pair is not None:
            counted_orbit.canonical(counted_curve.add(
                target, counted_curve.neg(pair)))
    query_field_calls = {name: counted_onb.calls[name] - table_field_calls.get(name, 0)
                         for name in counted_onb.calls}

    report = {
        "kind": "n83_exact_knownlog_four_million_point_base_quotient_pair_stage_benchmark",
        "scope": "measured bounded table and target-complement pair samples on known-log base; no target relation or DLP",
        "proposal_id": "Q1043", "candidate_id": None, "run_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "isogeny": "none", "public_target": list(target),
        "factor_base": base_receipt["factor_base"],
        "table_seed": TABLE_SEED, "query_seed": QUERY_SEED,
        "table_samples": TABLE_SAMPLES,
        "table_distinct_keys": len(table),
        "table_wall_ns": table_ns,
        "table_ns_per_sample": table_ns / TABLE_SAMPLES,
        "query_samples": QUERY_SAMPLES,
        "query_table_key_hits": hits,
        "query_wall_ns": query_ns,
        "query_ns_per_sample": query_ns / QUERY_SAMPLES,
        "field_api_count_samples_each_phase": COUNT_SAMPLES,
        "table_field_api_calls_per_sample": {name: count / COUNT_SAMPLES
                                             for name, count in table_field_calls.items()},
        "query_field_api_calls_per_sample": {name: count / COUNT_SAMPLES
                                             for name, count in query_field_calls.items()},
        "field_api_accounting": "logical calls on a separate instrumented run; square invokes Frobenius, so categories are nested and not summed; inversion cost in multiplication equivalents is uncalibrated",
        "verified_relation_count": 0,
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "peak_parent_rss_bytes": (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                                  if platform.system() == "Darwin" else
                                  resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
        "runtime": {"python": sys.version, "platform": platform.platform()},
        "source_sha256": sha(Path(__file__)),
        "base_receipt_sha256": sha(BASE_RECEIPT),
        "key_and_log_file_sha256": sha(key_path),
        "reference_sha256": sha(REFERENCE),
        "orbit_key_sha256": sha(HERE / "orbit_key.py"),
        "compact_base_sha256": sha(HERE / "bench_n83_full_base.py"),
        "dependency_sha256": {name: sha(CODEGEN / name)
                              for name in ("curves.py", "field.py", "indexcalc.py")},
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"curve_id": curve_id, "actual_B": len(base),
                      "table_ns_per_sample": report["table_ns_per_sample"],
                      "query_ns_per_sample": report["query_ns_per_sample"],
                      "table_hits": hits,
                      "rss_mib": report["peak_parent_rss_bytes"] / 2**20}))


if __name__ == "__main__":
    main()
