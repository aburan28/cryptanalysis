#!/usr/bin/env python3
"""Exact affine-span screen for all N41 seed-sum bucket pairs."""

import collections
import hashlib
import json
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
PRIOR = BASE / "n131_w14_s3_prefix_rank_20261010"
sys.path.insert(0, str(PRIOR))
import run as arithmetic  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trace_mask(field):
    bits = 0
    for i in range(field.n):
        value = 1 << i
        tr = 0
        for _ in range(field.n):
            tr ^= value
            value = field.mul(value, value)
        if tr not in (0, 1):
            raise AssertionError("field trace did not land in GF(2)")
        bits |= tr << i
    return bits


def rank_product(field, left, right):
    pivots = {}
    operations = 0
    for a in left:
        for b in right:
            value = field.mul(a, b)
            operations += 1
            while value:
                bit = value.bit_length() - 1
                if bit not in pivots:
                    pivots[bit] = value
                    break
                value ^= pivots[bit]
        if len(pivots) == field.n:
            break
    return len(pivots), operations


def main():
    output = HERE / "affine_rank_result.json"
    if output.exists():
        raise FileExistsError(output)
    protocol = json.loads((HERE / "protocol.json").read_text())
    for key, path in [("affine_source", Path(__file__)),
                      ("arithmetic_source", PRIOR / "run.py"),
                      ("geometry", arithmetic.GEOMETRY)]:
        if sha(path) != protocol["sha256"][key]:
            raise ValueError("frozen digest mismatch: " + key)
    started = time.monotonic_ns()
    record = json.loads(arithmetic.GEOMETRY.read_text())["n41"]
    field = arithmetic.Field(41, [0, 3])
    mask = trace_mask(field)
    buckets = []
    statistics = []
    for rotation in [20, 30]:
        rows = record["point_rows_by_unique_rotation"][str(rotation)]
        groups = collections.defaultdict(set)
        for point, i, j in arithmetic.pair_states(field, rows):
            groups[rows[i][3] ^ rows[j][3]].add(point[0])
        if set(groups) != set(range(1, 64)):
            raise AssertionError("seed-sum bucket coverage changed")
        affine = {}
        for seed_sum, xs in groups.items():
            origin = min(xs)
            affine[seed_sum] = [x ^ origin for x in sorted(xs)[1:]]
        bucket_traces = {s: sorted({bin(x & mask).count("1") & 1 for x in xs})
                         for s, xs in groups.items()}
        buckets.append(affine)
        statistics.append({"rotation": rotation, "buckets": len(groups),
                           "pair_output_x_count": len(set.union(*groups.values())),
                           "bucket_size_min": min(map(len, groups.values())),
                           "bucket_size_max": max(map(len, groups.values())),
                           "bucket_trace_histogram": dict(collections.Counter(
                               str(v[0]) if len(v) == 1 else "mixed"
                               for v in bucket_traces.values()))})
    residual = tuple(protocol["positive_residual"])
    if bin(residual[0] & mask).count("1") & 1:
        raise AssertionError("positive residual x trace changed")
    histogram = collections.Counter()
    product_calls = 0
    examples = []
    for s in range(1, 64):
        for t in range(1, 64):
            dimension, calls = rank_product(field, buckets[0][s], buckets[1][t])
            histogram[dimension] += 1
            product_calls += calls
            if dimension < 41:
                examples.append([s, t, dimension])
    elapsed = time.monotonic_ns() - started
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (
        1 if sys.platform == "darwin" else 1024)
    if elapsed > protocol["affine_wall_cap_seconds"] * 10**9 or peak > protocol["rss_cap_bytes"]:
        raise RuntimeError("frozen affine resource cap reached")
    result = {"status": "COMPLETE_EXACT_AFFINE_SCAN", "proposal_id": protocol["proposal_id"],
              "candidate_id": None, "target_count": 0,
              "source_sha256": sha(Path(__file__)), "protocol_sha256": sha(HERE / "protocol.json"),
              "field_trace_mask": mask, "residual_x_trace": 0,
              "domains": statistics, "bucket_pairs": 63*63,
              "cross_product_rank_histogram": dict(histogram),
              "nonfull_bucket_pairs": examples, "field_product_calls": product_calls,
              "elapsed_wall_ns": elapsed, "peak_rss_bytes": peak}
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "bucket_pairs": result["bucket_pairs"],
                      "rank_histogram": result["cross_product_rank_histogram"],
                      "elapsed_wall_ns": elapsed}))


if __name__ == "__main__":
    main()
