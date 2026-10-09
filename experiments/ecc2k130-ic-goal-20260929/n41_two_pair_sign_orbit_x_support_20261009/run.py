#!/usr/bin/env python3
"""Certify an exact x-only completion predicate from sign orbits."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import resource
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "n41_two_free_pair_occupancy_20261009"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs():
    protocol = json.loads((HERE / "protocol.json").read_text())
    names = {
        "geometry": PARENT / "geometry_snapshot.json",
        "arithmetic": PARENT / "arithmetic_snapshot.py",
        "census_result": PARENT / "result.json",
        "census_sage_audit": PARENT / "audit.json",
        "producer": HERE / "run.py",
        "auditor": HERE / "audit.py",
    }
    if {name: sha(path) for name, path in names.items()} != protocol["source_sha256"]:
        raise ValueError("frozen source or input hash changed")
    geometry = json.loads(names["geometry"].read_text())
    census = json.loads(names["census_result"].read_text())
    audit = json.loads(names["census_sage_audit"].read_text())
    if (geometry["n41"]["curve_id"] != protocol["curve_id"] or
            geometry["n41"]["public_target_q"] != protocol["public_target_q"] or
            census["status"] != "COMPLETE_EXACT_OCCUPANCY_AND_TARGET_CENSUS" or
            audit["status"] != "PASS_FULL_EXACT_RECOUNT_AND_GROUP_REPLAY" or
            census["counts"] != audit["counts"] or
            census["counts"]["suffix_valid_assignments"] != protocol["expected"]["valid_suffix_assignments"] or
            census["counts"]["suffix_distinct_group_sums"] != protocol["expected"]["unique_suffix_group_sums"] or
            census["counts"]["suffix_duplicate_assignments"] != protocol["expected"]["duplicate_suffix_group_sums"]):
        raise ValueError("prior independently audited census does not match protocol")
    spec = importlib.util.spec_from_file_location("frozen_arithmetic", names["arithmetic"])
    if spec is None or spec.loader is None:
        raise ValueError("cannot load frozen arithmetic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return protocol, geometry["n41"], census, module.Curve(module.Field(41, [0, 3]), 0)


def build_domain(curve, source):
    if len(source) != 64:
        raise ValueError("point-domain cardinality changed")
    lookup = {(row[0], row[1]): i for i, row in enumerate(source)}
    if len(lookup) != len(source):
        raise ValueError("duplicate source point")
    signs = []
    for i, row in enumerate(source):
        point = (row[0], row[1])
        if not curve.on_curve(point) or point[0] == 0:
            raise ValueError("invalid source point or 2-torsion")
        j = lookup.get(curve.neg(point))
        if j is None or j == i or source[j][2:4] != row[2:4]:
            raise ValueError("sign partner missing or changes folded column/seed")
        signs.append(j)
    if any(signs[signs[i]] != i for i in range(64)):
        raise ValueError("point sign map is not an involution")
    pairs = []
    pair_index = {}
    for i in range(64):
        for j in range(i + 1, 64):
            if source[i][2] == source[j][2]:
                continue
            total = curve.add((source[i][0], source[i][1]),
                              (source[j][0], source[j][1]))
            if total is None:
                raise ValueError("valid pair sums to identity")
            pair_index[(i, j)] = len(pairs)
            pairs.append((total, (1 << source[i][2]) | (1 << source[j][2]),
                          source[i][3] ^ source[j][3], i, j))
    if len(pairs) != 1956:
        raise ValueError("pair-domain cardinality changed")
    neg_pair = []
    for p, (total, columns, seed_sum, i, j) in enumerate(pairs):
        a, b = sorted((signs[i], signs[j]))
        q = pair_index[(a, b)]
        other = pairs[q]
        if (q == p or other[0] != curve.neg(total) or
                other[1] != columns or other[2] != seed_sum):
            raise ValueError("pair sign map fails group, column, or seed check")
        neg_pair.append(q)
    if any(neg_pair[neg_pair[p]] != p for p in range(1956)):
        raise ValueError("pair sign map is not an involution")
    return pairs, neg_pair


def main() -> None:
    if (HERE / "result.json").exists():
        raise FileExistsError("preserve first sign-orbit result")
    start = time.monotonic_ns()
    protocol, n41, census, curve = load_inputs()
    domains = []
    negations = []
    for rotation in protocol["pair_rotations"]:
        pairs, neg_pair = build_domain(curve, n41["point_rows_by_unique_rotation"][str(rotation)])
        domains.append(pairs)
        negations.append(neg_pair)
    left, right = domains[2], domains[3]
    left_neg, right_neg = negations[2], negations[3]
    valid = orbits = 0
    by_seed = Counter()
    for i, p in enumerate(left):
        for j, q in enumerate(right):
            if p[1] & q[1]:
                continue
            valid += 1
            if i * 1956 + j < left_neg[i] * 1956 + right_neg[j]:
                orbits += 1
                by_seed[(p[2], q[2])] += 1
    if valid != protocol["expected"]["valid_suffix_assignments"] or orbits * 2 != valid:
        raise ValueError("suffix sign-orbit partition differs from audited census")
    if census["counts"]["suffix_distinct_group_sums"] != valid:
        raise ValueError("uniqueness premise failed")
    elapsed = time.monotonic_ns() - start
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        peak *= 1024
    if elapsed > protocol["producer_wall_cap_seconds"] * 10**9 or peak > protocol["rss_cap_bytes"]:
        raise ValueError("frozen producer resource cap exceeded")
    result = {
        "status": "PASS_EXACT_SIGN_ORBITS_AND_X_FIBERS",
        "curve_id": protocol["curve_id"],
        "candidate_id": None,
        "run_id": None,
        "point_counts": [64] * 4,
        "pair_counts": [len(domain) for domain in domains],
        "valid_suffix_assignments": valid,
        "free_sign_orbits": orbits,
        "distinct_suffix_x_coordinates_derived": orbits,
        "seed_sum_pair_bins": len(by_seed),
        "seed_sum_pair_orbits_min": min(by_seed.values()),
        "seed_sum_pair_orbits_max": max(by_seed.values()),
        "prior_independent_unique_group_sums": census["counts"]["suffix_distinct_group_sums"],
        "prior_public_residual_support_hits": census["counts"]["prefix_residual_support_hits"],
        "prior_complete_relations": census["counts"]["eight_column_relations"],
        "implication": "Every valid completion point has its inverse with identical seed sums and folded columns; over the odd-order subgroup, exact suffix membership is an x-coordinate predicate. The x-count uses the prior independently audited no-collision census.",
        "producer_wall_ns": elapsed,
        "peak_rss_bytes": peak,
        "protocol_sha256": sha(HERE / "protocol.json"),
    }
    with (HERE / "result.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "orbits": orbits,
                      "seed_sum_pair_bins": result["seed_sum_pair_bins"]}, sort_keys=True))


if __name__ == "__main__":
    main()
