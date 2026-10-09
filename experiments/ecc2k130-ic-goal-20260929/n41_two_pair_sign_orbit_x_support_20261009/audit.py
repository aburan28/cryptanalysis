#!/usr/bin/env python3
"""Independent installed-Sage audit of the N41 sign-orbit certificate."""

from __future__ import annotations

import hashlib
import json
import resource
import sys
import time
from collections import Counter
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "n41_two_free_pair_occupancy_20261009"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if (HERE / "audit.json").exists():
        raise FileExistsError("preserve first independent Sage audit")
    start = time.monotonic_ns()
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
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
    geometry = json.loads(names["geometry"].read_text())["n41"]
    prior = json.loads(names["census_result"].read_text())
    prior_audit = json.loads(names["census_sage_audit"].read_text())
    if (result["status"] != "PASS_EXACT_SIGN_ORBITS_AND_X_FIBERS" or
            result["protocol_sha256"] != sha(HERE / "protocol.json") or
            geometry["curve_id"] != protocol["curve_id"] or
            geometry["public_target_q"] != protocol["public_target_q"] or
            prior["counts"] != prior_audit["counts"] or
            prior_audit["status"] != "PASS_FULL_EXACT_RECOUNT_AND_GROUP_REPLAY"):
        raise ValueError("result, curve, or prior independent census differs")
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**41, "t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(ring([(value >> k) & 1 for k in range(41)]))

    domains = []
    sign_maps = []
    subgroup_order = int(geometry["subgroup_order"])
    for rotation in protocol["pair_rotations"]:
        source = geometry["point_rows_by_unique_rotation"][str(rotation)]
        if len(source) != protocol["expected"]["per_rotation_points"]:
            raise ValueError("source cardinality changed")
        points = [curve(decode(row[0]), decode(row[1])) for row in source]
        if any(subgroup_order * point != curve(0) for point in points):
            raise ValueError("source point outside subgroup")
        lookup = {point: i for i, point in enumerate(points)}
        if len(lookup) != len(points):
            raise ValueError("duplicate source point")
        neg_point = []
        for i, point in enumerate(points):
            j = lookup.get(-point)
            if j is None or j == i or source[i][2:4] != source[j][2:4]:
                raise ValueError("Sage source-point sign map fails")
            neg_point.append(j)
        pairs = []
        lookup_pair = {}
        for i in range(64):
            for j in range(i + 1, 64):
                if source[i][2] == source[j][2]:
                    continue
                lookup_pair[(i, j)] = len(pairs)
                pairs.append((points[i] + points[j],
                              (1 << source[i][2]) | (1 << source[j][2]),
                              source[i][3] ^ source[j][3], i, j))
        if len(pairs) != protocol["expected"]["per_rotation_pair_states"]:
            raise ValueError("Sage pair-domain cardinality differs")
        neg_pair = []
        for p, (sum_point, columns, seed_sum, i, j) in enumerate(pairs):
            a, b = sorted((neg_point[i], neg_point[j]))
            q = lookup_pair[(a, b)]
            other = pairs[q]
            if (q == p or other[0] != -sum_point or other[1] != columns or
                    other[2] != seed_sum):
                raise ValueError("Sage pair involution fails")
            neg_pair.append(q)
        if any(neg_pair[neg_pair[p]] != p for p in range(len(pairs))):
            raise ValueError("Sage pair sign map is not an involution")
        domains.append(pairs)
        sign_maps.append(neg_pair)
    left, right = domains[2], domains[3]
    left_neg, right_neg = sign_maps[2], sign_maps[3]
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
        if time.monotonic_ns() - start > protocol["audit_wall_cap_seconds"] * 10**9:
            raise TimeoutError("frozen independent Sage audit wall cap")
    if (valid != result["valid_suffix_assignments"] or
            orbits != result["free_sign_orbits"] or
            orbits * 2 != valid or
            len(by_seed) != result["seed_sum_pair_bins"] or
            min(by_seed.values()) != result["seed_sum_pair_orbits_min"] or
            max(by_seed.values()) != result["seed_sum_pair_orbits_max"] or
            prior["counts"]["suffix_distinct_group_sums"] != valid or
            prior["counts"]["suffix_duplicate_assignments"] != 0 or
            result["distinct_suffix_x_coordinates_derived"] != orbits):
        raise ValueError("Sage sign-orbit, seed-bin, or x-fiber count differs")
    elapsed = time.monotonic_ns() - start
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        peak *= 1024
    if elapsed > protocol["audit_wall_cap_seconds"] * 10**9 or peak > protocol["rss_cap_bytes"]:
        raise ValueError("frozen independent Sage audit resource cap")
    audit = {
        "status": "PASS_INDEPENDENT_SAGE_SIGN_AND_X_FIBER_AUDIT",
        "curve_id": protocol["curve_id"],
        "checked_source_points": sum(len(geometry["point_rows_by_unique_rotation"][str(r)])
                                     for r in protocol["pair_rotations"]),
        "checked_pair_states": sum(map(len, domains)),
        "valid_suffix_assignments": valid,
        "free_sign_orbits": orbits,
        "distinct_suffix_x_coordinates_derived": orbits,
        "seed_sum_pair_bins": len(by_seed),
        "audit_wall_ns": elapsed,
        "peak_rss_bytes": peak,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "result_sha256": sha(HERE / "result.json"),
        "runtime_sha256": sha(HERE / "sage_runtime_info.json"),
    }
    with (HERE / "audit.json").open("x") as stream:
        json.dump(audit, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": audit["status"], "x_fibers": orbits}, sort_keys=True))


if __name__ == "__main__":
    main()
