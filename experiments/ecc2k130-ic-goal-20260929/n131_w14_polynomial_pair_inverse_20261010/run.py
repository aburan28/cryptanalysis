#!/usr/bin/env python3
"""Frozen W14 same-rotation joint inverse and exhaustive-scan controls."""
import json
import resource
import statistics
import sys
import time
from pathlib import Path

import freeze
import oracle

HERE = Path(__file__).resolve().parent


def peak_rss():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value*1024


def check_pair(candidate, pair, z):
    a, b = pair
    options_a = candidate.point_options(a)
    options_b = candidate.point_options(b)
    outputs = {candidate.phi_of(candidate.curve.add(left, right))
               for left in options_a for right in options_b}
    if z not in outputs:
        raise ValueError("algebraic pair inverse failed raw group replay")


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    inputs = json.loads((HERE / "inputs.json").read_text())
    if protocol["status"] != "FROZEN_BEFORE_PAIR_QUERIES":
        raise ValueError("protocol status changed")
    if protocol["source_sha256"] != {name: freeze.sha(path)
                                      for name, path in freeze.sources().items()}:
        raise ValueError("executed source differs from freeze")
    if protocol["inputs_sha256"] != freeze.sha(HERE / "inputs.json"):
        raise ValueError("frozen query inputs changed")
    started = time.monotonic_ns()
    candidate = oracle.PairOracle(oracle.load_support(freeze.SUPPORT / "support_w14.tsv"))
    field = candidate.field
    rotated = []
    for w in candidate.basis_w:
        for _ in range(13):
            w = field.mul(w, w)
        rotated.append(w)
    mixed_rank = len(oracle.echelon([
        field.mul(a, b) for a in candidate.basis_w for b in rotated])[0])
    if mixed_rank != 131:
        raise ValueError("adjacent-rotation product span unexpectedly shrank")
    if oracle.solve(oracle.echelon(candidate.basis_u)[0], 1) is not None:
        raise ValueError("exceptional output z=1 needs explicit branch")
    setup_ns = time.monotonic_ns() - started
    interleaved = []
    for i in range(32):
        interleaved.append(("positive", i, inputs["positives"][i]))
        interleaved.append(("uniform_field", i, inputs["controls"][i]))
    interleaved.extend(("exceptional", i-32, inputs["controls"][i])
                       for i in range(32, 34))
    records = []
    query_started = time.monotonic_ns()
    for kind, index, item in interleaved:
        t0 = time.monotonic_ns()
        pairs, detail = candidate.joint(item["z"])
        query_ns = time.monotonic_ns() - t0
        replay_start = time.monotonic_ns()
        if kind == "positive":
            expected = tuple(sorted(item["masks"]))
            if expected not in pairs:
                raise ValueError(f"positive pair {index} lost from exact inverse")
            leaf_points = [tuple(point) for point in item["raw_leaves"]]
            if (not all(candidate.curve.on_curve(point) for point in leaf_points)
                    or candidate.curve.add(*leaf_points) != tuple(item["raw_sum"])
                    or candidate.phi_of(tuple(item["raw_sum"])) != item["z"]):
                raise ValueError(f"positive raw group fixture {index} changed")
        for pair in pairs:
            check_pair(candidate, pair, item["z"])
        replay_ns = time.monotonic_ns() - replay_start
        records.append({"kind": kind, "input_index": index,
                        "z": item["z"], "pairs": [list(pair) for pair in pairs],
                        "detail": detail, "query_wall_ns": query_ns,
                        "group_replay_ns": replay_ns})
        if (time.monotonic_ns() - started >
                protocol["wall_cap_seconds"]*1_000_000_000 or
                peak_rss() > protocol["rss_cap_bytes"]):
            raise RuntimeError("joint query cap exceeded")
    joint_panel_ns = time.monotonic_ns() - query_started
    comparisons = []
    for kind, index in (("positive", 0), ("uniform_field", 0)):
        item = inputs["positives"][index] if kind == "positive" else inputs["controls"][index]
        t0 = time.monotonic_ns()
        exhaustive = candidate.full_scan(item["z"])
        elapsed = time.monotonic_ns() - t0
        joint_row = next(row for row in records
                         if row["kind"] == kind and row["input_index"] == index)
        if [list(pair) for pair in exhaustive] != joint_row["pairs"]:
            raise ValueError(f"exhaustive pair-set disagreement on {kind}")
        comparisons.append({"kind": kind, "input_index": index,
                            "full_scan_wall_ns": elapsed,
                            "joint_wall_ns": joint_row["query_wall_ns"],
                            "pair_count": len(exhaustive),
                            "seed_sums_full_scan": oracle.DOMAIN-1,
                            "seed_sums_joint": 1 if kind == "positive" else 0})
        if (time.monotonic_ns() - started >
                protocol["wall_cap_seconds"]*1_000_000_000 or
                peak_rss() > protocol["rss_cap_bytes"]):
            raise RuntimeError("exhaustive comparator cap exceeded")
    statuses = {}
    ranks = {}
    for row in records:
        key = row["detail"]["status"]
        statuses[key] = statuses.get(key, 0) + 1
        key = str(row["detail"]["rank"])
        ranks[key] = ranks.get(key, 0) + 1
    positive_ns = [row["query_wall_ns"] for row in records
                   if row["kind"] == "positive"]
    uniform_ns = [row["query_wall_ns"] for row in records
                  if row["kind"] == "uniform_field"]
    result = {"status": "PASS_EXACT_W14_JOINT_PAIR_INVERSE_CONTROLS",
              "candidate_id": None, "curve_id": protocol["curve_id"],
              "same_rotation_product_span_rank": candidate.product_rank,
              "adjacent_rotation_product_span_rank": mixed_rank,
              "joint_column_count": 41,
              "status_histogram": statuses, "rank_histogram": ranks,
              "setup_wall_ns": setup_ns,
              "joint_panel_wall_ns": joint_panel_ns,
              "median_positive_joint_query_ns": statistics.median(positive_ns),
              "median_uniform_joint_query_ns": statistics.median(uniform_ns),
              "comparisons": comparisons,
              "queries": records,
              "total_wall_ns": time.monotonic_ns() - started,
              "peak_process_rss_bytes": peak_rss(),
              "source_sha256": {"protocol": freeze.sha(HERE / "protocol.json"),
                                "inputs": freeze.sha(HERE / "inputs.json"),
                                **{name: freeze.sha(path)
                                   for name, path in freeze.sources().items()}}}
    freeze.save(HERE / "result.json", result)
    print(json.dumps({"status": result["status"],
                      "product_ranks": [candidate.product_rank, mixed_rank],
                      "status_histogram": statuses,
                      "total_wall_seconds": result["total_wall_ns"]/1e9,
                      "peak_rss_bytes": result["peak_process_rss_bytes"]}))


if __name__ == "__main__":
    main()
