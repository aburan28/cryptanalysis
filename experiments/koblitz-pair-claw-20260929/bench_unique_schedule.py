#!/usr/bin/env python3
"""Bounded unique zero-pair-class and query-pair schedules at n53/n83."""

import hashlib
import json
import platform
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
from batch_quotient import x_orbit_key
from bench_batch_xkey import load_base
from orbit_key import OrbitKey
from pair_schedule import (affine_parameters, affine_rank,
                           cross_orbit_pair, unordered_pair)
from run_n23 import frozen, sha

SAMPLES = 32768
REPETITIONS = 3


def benchmark_once(n):
    reference = json.loads((REFS / f"n{n}_perf_prefix.json").read_text())
    identity = reference["curve_identity_record"]
    curve_id = f"EC1N{n}Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert curve_id == reference["curve_id"]
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    base, base_receipt = load_base(n, curve, orbit, identity)
    target = tuple(reference["workload"]["target"])
    K = len(base.keys)
    L = 2 * n
    P = len(base) * (len(base) + 1) // 2
    D_cross = K * (K - 1) // 2 * L
    table_step, table_offset = affine_parameters(D_cross, 104400 + n)
    query_step, query_offset = affine_parameters(P, 104500 + n)
    assert SAMPLES < min(D_cross, P)
    table_ranks = []
    query_ranks = []
    table_keys = []
    query_keys = []
    table_started = time.perf_counter_ns()
    for position in range(SAMPLES):
        rank = affine_rank(position, D_cross, table_step, table_offset)
        table_ranks.append(rank)
        i, j, shift = cross_orbit_pair(rank, K, L)
        pair = curve.add(base[i * L], base[j * L + shift])
        table_keys.append(x_orbit_key(orbit, pair))
    table_ns = time.perf_counter_ns() - table_started
    query_started = time.perf_counter_ns()
    for position in range(SAMPLES):
        rank = affine_rank(position, P, query_step, query_offset)
        query_ranks.append(rank)
        i, j = unordered_pair(rank, len(base))
        pair = curve.add(base[i], base[j])
        complement = curve.add(target, curve.neg(pair))
        query_keys.append(x_orbit_key(orbit, complement))
    query_ns = time.perf_counter_ns() - query_started
    assert len(set(table_ranks)) == len(set(query_ranks)) == SAMPLES
    return {
        "curve_id": curve_id, "curve_identity_record": identity,
        "isogeny": "none", "public_target": list(target),
        "proposal_id": "Q1044" if n == 53 else "Q1045",
        "candidate_id": None, "run_id": None,
        "actual_usable_points_B_before_folding": len(base),
        "signed_frobenius_columns": K,
        "base_enumerated_set_sha256": base_receipt["factor_base"]["enumerated_set_sha256"],
        "cross_orbit_zero_pair_class_domain": D_cross,
        "unordered_query_pair_domain": P,
        "samples_per_phase": SAMPLES,
        "table_schedule": {"seed": 104400 + n, "step": table_step,
                           "offset": table_offset},
        "query_schedule": {"seed": 104500 + n, "step": query_step,
                           "offset": query_offset},
        "unique_table_descriptors_checked": len(table_ranks),
        "unique_query_pair_ranks_checked": len(query_ranks),
        "distinct_table_x_keys": len(set(table_keys)),
        "distinct_query_x_keys": len(set(query_keys)),
        "table_key_matches_in_query_sample": len(set(table_keys) &
                                                 set(query_keys)),
        "table_wall_ns": table_ns, "query_wall_ns": query_ns,
        "table_ns_per_sample": table_ns / SAMPLES,
        "query_ns_per_sample": query_ns / SAMPLES,
        "verified_relation_count": 0,
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
    }


def benchmark(n):
    observations = [benchmark_once(n) for _ in range(REPETITIONS)]
    first = observations[0]
    for other in observations[1:]:
        for name in ("curve_id", "actual_usable_points_B_before_folding",
                     "signed_frobenius_columns", "table_schedule",
                     "query_schedule", "distinct_table_x_keys",
                     "distinct_query_x_keys"):
            assert other[name] == first[name]
    table_each = [row["table_ns_per_sample"] for row in observations]
    query_each = [row["query_ns_per_sample"] for row in observations]
    first["timing_repetitions"] = REPETITIONS
    first["table_ns_per_sample_each"] = table_each
    first["query_ns_per_sample_each"] = query_each
    first["table_ns_per_sample"] = statistics.median(table_each)
    first["query_ns_per_sample"] = statistics.median(query_each)
    first["table_wall_ns"] = statistics.median(
        row["table_wall_ns"] for row in observations)
    first["query_wall_ns"] = statistics.median(
        row["query_wall_ns"] for row in observations)
    return first


def main():
    runs = [benchmark(n) for n in (53, 83)]
    report = {
        "kind": "n53_n83_exact_base_unique_quotient_class_and_query_pair_schedule_perf",
        "scope": "bounded stage timing and unique-rank checks; no n83 relation or DLP",
        "runs": runs,
        "peak_parent_rss_bytes": (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                                  if platform.system() == "Darwin" else
                                  resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
        "runtime": {"python": sys.version, "platform": platform.platform()},
        "source_sha256": sha(Path(__file__)),
        "schedule_source_sha256": sha(HERE / "pair_schedule.py"),
        "xkey_source_sha256": sha(HERE / "batch_quotient.py"),
        "base_loader_source_sha256": sha(HERE / "bench_batch_xkey.py"),
        "local_dependency_sha256": {
            name: sha(HERE / name) for name in (
                "bench_n83_full_base.py", "bench_n83_knownlog.py",
                "knownlog_n53.py", "orbit_key.py", "run_n23.py")
        },
        "reference_sha256": {str(n): sha(REFS / f"n{n}_perf_prefix.json")
                             for n in (53, 83)},
        "dependency_sha256": {name: sha(CODEGEN / name)
                              for name in ("curves.py", "field.py")},
    }
    path = HERE / "runs" / "n53_n83_unique_schedule_perf.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"runs": [
        {"curve_id": row["curve_id"],
         "table_ns_per_sample": row["table_ns_per_sample"],
         "query_ns_per_sample": row["query_ns_per_sample"],
         "distinct_table_x_keys": row["distinct_table_x_keys"],
         "distinct_query_x_keys": row["distinct_query_x_keys"]}
        for row in runs]}))


if __name__ == "__main__":
    main()
