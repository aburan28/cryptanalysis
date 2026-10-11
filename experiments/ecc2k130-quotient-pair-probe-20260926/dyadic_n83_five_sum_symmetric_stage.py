#!/usr/bin/env python3
"""Build the n83 two-G witness index once per unordered seed-orbit pair."""

import hashlib
import json
import random
import time
from pathlib import Path

import numpy as np

import curves
import field
from dyadic_base_geometry import enumerate_points
from dyadic_n83_compact_index import (
    PackedIndex, ROW_DTYPE, encode_key,
)
from dyadic_n83_five_sum_packed_stage import frozen, peak_rss_bytes
from perf_probe import sha
from quotient_pair_probe import CountedCurve
from x_only_cycle import XOnlyCycle

HERE = Path(__file__).resolve().parent
PROPOSAL_ID = "Q1028"
WINDOW = 32


def build_symmetric(curve, left_reps, right_base, canonicalize):
    """Keep orbit i on the left and orbit j >= i on the right.

    Each omitted (j, i) pair has a retained (i, j) representative: swap
    summands and apply the same signed Frobenius action to both points.
    """
    total_started = time.perf_counter()
    orbit_keys = [canonicalize.key_and_shift(curve, rep)[0]
                  for rep in left_reps]
    assert len(set(orbit_keys)) == len(left_reps)
    orbit_number = {key: i for i, key in enumerate(orbit_keys)}
    right_buckets = [[] for _ in left_reps]
    for right_index, point in enumerate(right_base):
        key = canonicalize.key_and_shift(curve, point)[0]
        right_buckets[orbit_number[key]].append(right_index)
    assert sum(map(len, right_buckets)) == len(right_base)
    assert len(set(map(len, right_buckets))) == 1
    generators = sum(len(bucket) * (i + 1)
                     for i, bucket in enumerate(right_buckets))
    rows = np.empty(generators, dtype=ROW_DTYPE)
    counted = CountedCurve(curve)
    started = time.perf_counter()
    at = 0
    for left_index, left in enumerate(left_reps):
        for bucket in right_buckets[left_index:]:
            for right_index in bucket:
                total = counted.add(left, right_base[right_index])
                key, shift = canonicalize.key_and_shift(counted, total)
                hi, lo = encode_key(key)
                witness = (left_index * len(right_base) + right_index) * 83 + shift
                rows[at] = (hi, lo, witness)
                at += 1
    assert at == generators
    rows.sort(order=["hi", "lo"], kind="quicksort")
    keep = np.empty(generators, dtype=np.bool_)
    keep[0] = True
    keep[1:] = ((rows["hi"][1:] != rows["hi"][:-1]) |
                (rows["lo"][1:] != rows["lo"][:-1]))
    unique = rows[keep].copy()
    elapsed = time.perf_counter() - started
    total_elapsed = time.perf_counter() - total_started
    index = PackedIndex(unique, left_reps, right_base, curve, canonicalize)
    return index, {
        "pair_generators": generators,
        "quotient_keys": len(unique),
        "build_seconds_excluding_orbit_partition": elapsed,
        "build_seconds_including_orbit_partition": total_elapsed,
        "point_operations": counted.counts,
        "row_bytes": ROW_DTYPE.itemsize,
        "raw_array_bytes": rows.nbytes,
        "retained_array_bytes": unique.nbytes,
        "retained_array_sha256": hashlib.sha256(unique.tobytes()).hexdigest(),
        "key_sha256": hashlib.sha256(frozen(list(index.keys()))).hexdigest(),
        "peak_rss_bytes": peak_rss_bytes(),
    }


def main():
    reference_path = HERE / "runs" / "n83_perf_prefix.json"
    baseline_path = HERE / "runs" / "n83_dyadic_five_sum_stage.json"
    packed_path = HERE / "runs" / "n83_dyadic_five_sum_packed_stage.json"
    reference = json.loads(reference_path.read_text())
    baseline = json.loads(baseline_path.read_text())
    packed_receipt = json.loads(packed_path.read_text())
    assert reference["curve_id"] == baseline["curve_id"] == packed_receipt[
        "curve_id"]
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    target = tuple(reference["workload"]["target"])
    order = int(reference["subgroup_order"])
    lam = int(baseline["frobenius_eigenvalue_mod_r"])
    labels, representatives, digests = enumerate_points(
        curve, onb, [generator, target], WINDOW, lam, order)
    assert digests["enumerated_set_sha256"] == packed_receipt[
        "factor_base"]["enumerated_set_sha256"]
    g_reps = [point for point in sorted(representatives)
              if labels[point][0] == 0]
    g_base = [point for point in sorted(labels) if labels[point][0] == 0]
    assert len(g_reps) == WINDOW and len(g_base) == 166 * WINDOW
    canonicalize = XOnlyCycle(onb)
    index, build = build_symmetric(curve, g_reps, g_base, canonicalize)
    assert build["pair_generators"] == 83 * WINDOW * (WINDOW + 1)
    assert build["quotient_keys"] == packed_receipt["packed_build"][
        "quotient_keys"] == 80868
    assert build["key_sha256"] == packed_receipt["full_key_set_sha256"]
    rng = random.Random(202609300836)
    sampled = [next(index.keys()), *rng.sample(list(index.keys()), 1000)]
    for key in sampled:
        representative, pair = index.get(key)
        assert curve.add(*pair) == representative
        assert canonicalize.key_and_shift(curve, representative) == (key, 0)
    planted = packed_receipt["planted_positive_control"]
    g_pair = tuple(map(tuple, planted["point_witness"][:2]))
    g_sum = curve.add(*g_pair)
    key, shift = canonicalize.key_and_shift(curve, g_sum)
    assert index.get(key) is not None
    workload = {
        "curve_id": reference["curve_id"],
        "target": target,
        "doubling_window": WINDOW,
        "index_variant": "unordered_seed_orbit_triangle_packed_two_G",
        "witness_sample_seed": 202609300836,
        "witness_sample_count": len(sampled),
    }
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    report = {
        "kind": "n83_L32_symmetric_packed_two_G_witness_index",
        "scope": "complete L32 key and sampled witness controls; index build only, no ordinary relation or DLP",
        "proposal_id": PROPOSAL_ID,
        "candidate_id": None,
        "run_id": f"{PROPOSAL_ID}W{workload_id}R1",
        "workload_id": workload_id,
        "workload": workload,
        "curve_id": reference["curve_id"],
        "curve_identity_record": reference["curve_identity_record"],
        "isogeny": "none",
        "endomorphism_order_conductor": None,
        "factor_base": packed_receipt["factor_base"],
        "build": build,
        "reference_full_pair_generators": packed_receipt["packed_build"][
            "pair_generators"],
        "reference_full_key_sha256": packed_receipt["full_key_set_sha256"],
        "sampled_witness_replays": len(sampled),
        "planted_G_pair_key": key,
        "planted_G_pair_shift": shift,
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "source_sha256": sha(Path(__file__)),
        "dependency_sha256": {name: sha(HERE / name) for name in (
            "dyadic_base_geometry.py", "dyadic_n83_compact_index.py",
            "dyadic_n83_five_sum_packed_stage.py", "quotient_pair_probe.py",
            "x_only_cycle.py", "curves.py", "field.py")},
        "reference_sha256": sha(reference_path),
        "baseline_sha256": sha(baseline_path),
        "packed_receipt_sha256": sha(packed_path),
    }
    out = HERE / "runs" / "n83_dyadic_five_sum_symmetric_stage.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"pair_generators": build["pair_generators"],
                      "quotient_keys": len(index),
                      "build_seconds": build[
                          "build_seconds_including_orbit_partition"],
                      "retained_array_bytes": build["retained_array_bytes"],
                      "peak_rss_bytes": build["peak_rss_bytes"]}))


if __name__ == "__main__":
    main()
