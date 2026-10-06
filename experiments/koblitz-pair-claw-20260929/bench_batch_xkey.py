#!/usr/bin/env python3
"""Paired direct/batched quotient-key benchmarks on the exact n53/n83 bases."""

import hashlib
import json
import math
import platform
import random
import resource
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
REFS = HERE.parent / "ecc2k130-quotient-pair-probe-20260926" / "runs"
sys.path.insert(0, str(CODEGEN))

import curves
import field
from batch_quotient import batch_add, x_orbit_key
from bench_n83_full_base import CompactOrbitBase
from bench_n83_knownlog import load_keys_logs
from bench_steps import CountingOnb
from knownlog_n53 import build_knownlog_base
from orbit_key import OrbitKey
from run_n23 import frozen, sha

SAMPLES = 32768
COUNT_SAMPLES = 2048
BATCH_SIZES = (64, 256, 1024)
REPETITIONS = 3


def load_base(n, curve, orbit, identity):
    if n == 53:
        order = identity["curve"]["subgroup_order"]
        generator = tuple(identity["curve"]["generator"])
        eigen = curves.frobeniusEigenvalue(curve, generator, order)
        keys, logs, _ = build_knownlog_base(curve, orbit, generator,
                                             order, eigen)
        receipt = json.loads((HERE / "runs" /
                              "n53_knownlog_one_target.json").read_text())
        assert [str(key) for key in keys] == receipt["factor_base"]["canonical_orbit_keys"]
        assert logs == receipt["factor_base"]["canonical_logs"]
    else:
        receipt = json.loads((HERE / "runs" /
                              "n83_knownlog_orbit_base.json").read_text())
        path = HERE / receipt["factor_base"]["key_and_log_file"]
        assert sha(path) == receipt["factor_base"]["key_and_log_file_sha256"]
        keys, _ = load_keys_logs(path)
    assert receipt["curve_id"] == (f"EC1N{n}Ckb1h" +
                                  hashlib.sha256(frozen(identity)).hexdigest()[:12])
    base = CompactOrbitBase(orbit, keys)
    assert len(base) == receipt["factor_base"]["actual_usable_points_B_before_folding"]
    return base, receipt


def direct(curve, orbit, base, target, draws, x_only=False):
    encode = (lambda point: x_orbit_key(orbit, point)) if x_only else (
        lambda point: orbit.canonical(point)[0])
    table = []
    query = []
    started = time.perf_counter_ns()
    for first, second in draws:
        pair = curve.add(base[first], base[second])
        table.append(encode(pair) if pair is not None else -1)
    table_ns = time.perf_counter_ns() - started
    started = time.perf_counter_ns()
    for first, second in draws:
        pair = curve.add(base[first], base[second])
        complement = curve.add(target, curve.neg(pair))
        query.append(encode(complement))
    query_ns = time.perf_counter_ns() - started
    return table, query, table_ns, query_ns


def batched(curve, orbit, base, target, draws, batch_size):
    table = []
    query = []
    started = time.perf_counter_ns()
    for offset in range(0, len(draws), batch_size):
        points = [(base[a], base[b]) for a, b in draws[offset:offset + batch_size]]
        sums = batch_add(curve, points)
        table.extend(x_orbit_key(orbit, pair) for pair in sums)
    table_ns = time.perf_counter_ns() - started
    started = time.perf_counter_ns()
    for offset in range(0, len(draws), batch_size):
        points = [(base[a], base[b]) for a, b in draws[offset:offset + batch_size]]
        sums = batch_add(curve, points)
        complements = batch_add(curve, [
            (target, curve.neg(pair)) for pair in sums])
        query.extend(x_orbit_key(orbit, point) for point in complements)
    query_ns = time.perf_counter_ns() - started
    return table, query, table_ns, query_ns


def repeated(run):
    first = run()
    table_ns = [first[2]]
    query_ns = [first[3]]
    for _ in range(REPETITIONS - 1):
        result = run()
        assert result[0] == first[0] and result[1] == first[1]
        table_ns.append(result[2])
        query_ns.append(result[3])
    return (first[0], first[1], statistics.median(table_ns),
            statistics.median(query_ns), table_ns, query_ns)


def counts(n, keys, draws, target, batch_size):
    onb = CountingOnb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    base = CompactOrbitBase(orbit, keys)
    for offset in range(0, len(draws), batch_size):
        points = [(base[a], base[b]) for a, b in
                  draws[offset:offset + batch_size]]
        sums = batch_add(curve, points)
        for point in sums:
            x_orbit_key(orbit, point)
    table_calls = dict(onb.calls)
    for offset in range(0, len(draws), batch_size):
        points = [(base[a], base[b]) for a, b in
                  draws[offset:offset + batch_size]]
        sums = batch_add(curve, points)
        complements = batch_add(curve, [(target, curve.neg(point))
                                         for point in sums])
        for point in complements:
            x_orbit_key(orbit, point)
    extra_calls = {name: onb.calls[name] - table_calls.get(name, 0)
                   for name in onb.calls}
    return ({name: value / len(draws) for name, value in table_calls.items()},
            {name: value / len(draws) for name, value in extra_calls.items()})


def benchmark(n):
    reference_path = REFS / f"n{n}_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    identity = reference["curve_identity_record"]
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    base, receipt = load_base(n, curve, orbit, identity)
    target = tuple(reference["workload"]["target"])
    draws_rng = random.Random(530931 if n == 53 else 830931)
    draws = [(draws_rng.randrange(len(base)), draws_rng.randrange(len(base)))
             for _ in range(SAMPLES)]
    old_table, old_query, old_table_ns, old_query_ns, old_table_each, old_query_each = repeated(
        lambda: direct(curve, orbit, base, target, draws))
    x_table, x_query, x_table_ns, x_query_ns, x_table_each, x_query_each = repeated(
        lambda: direct(curve, orbit, base, target, draws, x_only=True))
    assert all((old == -1 and new == -1) or
               old >> n == new for old, new in zip(old_table, x_table))
    assert all(old >> n == new for old, new in zip(old_query, x_query))
    results = []
    for batch_size in BATCH_SIZES:
        new_table, new_query, table_ns, query_ns, table_each, query_each = repeated(
            lambda: batched(curve, orbit, base, target, draws, batch_size))
        # Every signed-Frobenius full key must map to exactly the same x key.
        assert all((old == -1 and new == -1) or
                   (old >> n == new) for old, new in zip(old_table, new_table))
        assert all(old >> n == new for old, new in zip(old_query, new_query))
        assert len(set(old_table)) == len(set(new_table))
        assert len(set(old_query)) == len(set(new_query))
        assert new_table == x_table and new_query == x_query
        result = {"batch_size": batch_size,
                  "table_ns_per_sample": table_ns / SAMPLES,
                  "query_ns_per_sample": query_ns / SAMPLES,
                  "table_ns_per_sample_each": [value / SAMPLES for value in table_each],
                  "query_ns_per_sample_each": [value / SAMPLES for value in query_each],
                  "table_speedup": old_table_ns / table_ns,
                  "query_speedup": old_query_ns / query_ns}
        if batch_size == 256:
            keys = base.keys
            table_calls, query_calls = counts(
                n, keys, draws[:COUNT_SAMPLES], target, batch_size)
            result["table_field_api_calls_per_sample"] = table_calls
            result["query_field_api_calls_per_sample"] = query_calls
        results.append(result)
    return {"curve_id": receipt["curve_id"],
            "proposal_id": "Q1044" if n == 53 else "Q1045",
            "curve_identity_record": identity,
            "isogeny": "none", "public_target": list(target),
            "factor_base_receipt_sha256": sha(HERE / "runs" /
                ("n53_knownlog_one_target.json" if n == 53 else
                 "n83_knownlog_orbit_base.json")),
            "actual_usable_points_B_before_folding": len(base),
            "signed_frobenius_columns": len(base.keys),
            "samples_per_phase": SAMPLES,
            "timing_repetitions": REPETITIONS,
            "sample_index_seed": 530931 if n == 53 else 830931,
            "direct_full_key_table_ns_per_sample": old_table_ns / SAMPLES,
            "direct_full_key_query_ns_per_sample": old_query_ns / SAMPLES,
            "direct_full_key_table_ns_per_sample_each":
                [value / SAMPLES for value in old_table_each],
            "direct_full_key_query_ns_per_sample_each":
                [value / SAMPLES for value in old_query_each],
            "direct_xkey_table_ns_per_sample": x_table_ns / SAMPLES,
            "direct_xkey_query_ns_per_sample": x_query_ns / SAMPLES,
            "direct_xkey_table_ns_per_sample_each":
                [value / SAMPLES for value in x_table_each],
            "direct_xkey_query_ns_per_sample_each":
                [value / SAMPLES for value in x_query_each],
            "distinct_table_keys": len(set(old_table)),
            "distinct_query_keys": len(set(old_query)),
            "exact_key_equivalence_checks_per_phase": SAMPLES,
            "batched_xkey": results}


def main():
    runs = [benchmark(n) for n in (53, 83)]
    report = {
        "kind": "paired_batch_inversion_x_only_quotient_stage_benchmark",
        "scope": "exact known-log factor bases and same sampled pairs; stage only, no n83 relation or DLP",
        "proposal_ids": ["Q1044", "Q1045"],
        "candidate_id": None, "run_id": None,
        "runs": runs,
        "field_api_accounting": "add/mul/sqr/inv are disjoint logical calls except sqr invokes frob; one inversion per batch per point-add layer when no exceptional pair occurs",
        "measured_n83_relation_yield": None,
        "verified_n83_dlp": False,
        "complete_work_log2": None,
        "peak_parent_rss_bytes": (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                                  if platform.system() == "Darwin" else
                                  resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
        "runtime": {"python": sys.version, "platform": platform.platform()},
        "source_sha256": sha(Path(__file__)),
        "batch_source_sha256": sha(HERE / "batch_quotient.py"),
        "local_dependency_sha256": {
            name: sha(HERE / name) for name in (
                "bench_n83_full_base.py", "bench_n83_knownlog.py",
                "bench_steps.py", "knownlog_n53.py", "orbit_key.py",
                "run_n23.py")
        },
        "reference_sha256": {str(n): sha(REFS / f"n{n}_perf_prefix.json")
                             for n in (53, 83)},
        "dependency_sha256": {name: sha(CODEGEN / name)
                              for name in ("curves.py", "field.py")},
    }
    path = HERE / "runs" / "n53_n83_batch_xkey_perf.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"runs": [{"curve_id": run["curve_id"],
                                  "direct_query_us": run["direct_full_key_query_ns_per_sample"] / 1000,
                                  "batched_query_us": [row["query_ns_per_sample"] / 1000
                                                       for row in run["batched_xkey"]]}
                                 for run in runs]}))


if __name__ == "__main__":
    main()
