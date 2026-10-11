#!/usr/bin/env python3
"""Exact four-point group MITM with a signed-Frobenius pair-sum index.

This is a stage diagnostic on public toy curves, not an IC candidate.  The
index is target independent; query work includes every failed complement
lookup.  We count group operations separately from field operations.
"""

import argparse
import hashlib
import itertools
import json
import platform
import random
import resource
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE
import curves  # noqa: E402


def point_key(point):
    return (-1, -1) if point is None else point


class CountedCurve:
    def __init__(self, curve):
        self.curve = curve
        self.counts = {"add": 0, "neg": 0, "frob": 0, "lookup": 0}

    def add(self, left, right):
        self.counts["add"] += 1
        return self.curve.add(left, right)

    def neg(self, point):
        self.counts["neg"] += 1
        return self.curve.neg(point)

    def frob(self, point):
        self.counts["frob"] += 1
        return self.curve.frob(point)


def canonical(curve, point, degree):
    """Return min(±Frob^j(P)), with the transform taking P to that min."""
    best = None
    best_shift = 0
    best_sign = 1
    current = point
    for shift in range(degree):
        for sign, value in ((1, current), (-1, curve.neg(current))):
            key = point_key(value)
            if best is None or key < best:
                best, best_shift, best_sign = key, shift, sign
        current = curve.frob(current)
    return best, best_shift, best_sign


def transform(curve, point, shift, sign):
    if sign == -1:
        point = curve.neg(point)
    for _ in range(shift):
        point = curve.frob(point)
    return point


def make_base(degree, weight, orbit_limit=None):
    view = curves.NormalView(degree)
    curve = curves.CurvePb(view.pb)
    order = curves.curveOrder(degree)
    subgroup_order = order // 4
    if order != 4 * subgroup_order or not curves.isPrimeBig(subgroup_order):
        raise ValueError("this probe requires #E = 4 times a prime")
    points = set()
    candidate_x = rational_x = 0
    for size in range(1, weight + 1):
        for support in itertools.combinations(range(degree), size):
            coords = sum(1 << bit for bit in support)
            candidate_x += 1
            raw = curve.pointFromX(view.fromCoords(coords))
            if raw is None:
                continue
            rational_x += 1
            projected = curve.mul(raw, 4)
            if projected is None:
                continue
            if curve.mul(projected, subgroup_order) is not None:
                raise AssertionError("cofactor projection left the declared subgroup")
            points.add(projected)
            points.add(curve.neg(projected))
    full_count = len(points)
    if orbit_limit is not None:
        representative = {point: canonical(curve, point, degree)[0]
                          for point in points}
        selected = set(sorted(set(representative.values()))[:orbit_limit])
        points = {point for point in points if representative[point] in selected}
    base = sorted(points)
    base_bytes = json.dumps(base, separators=(",", ":")).encode()
    return view, curve, subgroup_order, base, {
        "normal_basis_conjugates": view.conj,
        "field_modulus": view.poly,
        "curve_order": order,
        "subgroup_order": subgroup_order,
        "cofactor": 4,
        "candidate_x": candidate_x,
        "rational_x": rational_x,
        "geometric_points": 2 * rational_x,
        "preselection_usable_points_B": full_count,
        "usable_points_B": len(base),
        "selected_signed_frobenius_orbits": orbit_limit,
        "base_sha256": hashlib.sha256(base_bytes).hexdigest(),
    }


def build_index(curve, base, degree):
    """One witness per pair-sum orbit, using orbit reps for the first point.

    For any (P,Q), a signed Frobenius transform takes P to its orbit
    representative and takes Q to another member of the signed-closed base.
    Therefore reps(base) x base covers every pair-sum orbit exactly enough
    for a complete existence oracle; no B^2 raw-pair scan is needed.
    """
    counted = CountedCurve(curve)
    index = {}
    start = time.perf_counter_ns()
    representatives = sorted({canonical(counted, point, degree)[0]
                              for point in base})
    if any(rep not in base for rep in representatives):
        raise AssertionError("base is not closed under signed Frobenius")
    for left in representatives:
        for right in base:
            total = counted.add(left, right)
            key, shift, sign = canonical(counted, total, degree)
            if key not in index:
                index[key] = (
                    transform(counted, left, shift, sign),
                    transform(counted, right, shift, sign),
                )
    wall_ns = time.perf_counter_ns() - start
    for key, pair in index.items():
        if point_key(curve.add(*pair)) != key:
            raise AssertionError("canonical pair witness does not replay")
    frozen_index = json.dumps(sorted((key, pair) for key, pair in index.items()),
                              separators=(",", ":")).encode()
    return index, {
        "raw_unordered_pair_count": len(base) * (len(base) + 1) // 2,
        "first_point_orbit_representatives": len(representatives),
        "quotient_generators_enumerated": len(representatives) * len(base),
        "quotient_pair_sum_keys": len(index),
        "build_wall_ns": wall_ns,
        "build_operations": counted.counts,
        "serialized_index_bytes": len(frozen_index),
        "index_sha256": hashlib.sha256(frozen_index).hexdigest(),
    }


def build_direct_index(curve, base):
    """Independent ordinary pair-sum table for exact membership cross-check."""
    start = time.perf_counter_ns()
    index = {}
    for i, left in enumerate(base):
        for right in base[i:]:
            total = curve.add(left, right)
            index.setdefault(point_key(total), (left, right))
    return index, {"distinct_pair_sum_keys": len(index),
                   "build_wall_ns": time.perf_counter_ns() - start}


def solve_direct(curve, index, target):
    start = time.perf_counter_ns()
    checks = 0
    for key, first in index.items():
        checks += 1
        left_sum = None if key == (-1, -1) else key
        complement = curve.add(target, curve.neg(left_sum))
        second = index.get(point_key(complement))
        if second is not None:
            answer = first + second
            replay = None
            for point in answer:
                replay = curve.add(replay, point)
            if replay != target:
                raise AssertionError("direct pair reconstruction failed")
            return {"status": "verified_decomposition", "lookups": checks,
                    "query_wall_ns": time.perf_counter_ns() - start}
    return {"status": "proved_no_four_sum_in_base", "lookups": len(index),
            "query_wall_ns": time.perf_counter_ns() - start}


def solve_query(curve, index, target, degree):
    counted = CountedCurve(curve)
    start = time.perf_counter_ns()
    checks = 0
    for key, left_pair in index.items():
        if key == (-1, -1):
            representative = None
        else:
            representative = key
        current = representative
        for shift in range(degree):
            for sign in (1, -1):
                candidate = current if sign == 1 else counted.neg(current)
                complement = counted.add(target, counted.neg(candidate))
                complement_key, canonical_shift, canonical_sign = canonical(
                    counted, complement, degree)
                checks += 1
                counted.counts["lookup"] += 1
                match = index.get(complement_key)
                if match is None:
                    continue
                first = tuple(transform(counted, p, shift, sign) for p in left_pair)
                second = tuple(transform(counted, p, (-canonical_shift) % degree,
                                         canonical_sign) for p in match)
                answer = first + second
                replay = None
                for point in answer:
                    replay = curve.add(replay, point)
                if replay != target:
                    raise AssertionError("quotient reconstruction failed")
                return {
                    "status": "verified_decomposition",
                    "points": answer,
                    "sum_replay": replay,
                    "pair_representatives_examined": checks,
                    "query_wall_ns": time.perf_counter_ns() - start,
                    "query_operations": counted.counts,
                }
            current = counted.frob(current)
    return {
        "status": "proved_no_four_sum_in_base",
        "points": None,
        "sum_replay": None,
        "pair_representatives_examined": checks,
        "query_wall_ns": time.perf_counter_ns() - start,
        "query_operations": counted.counts,
    }


def run(degree, weight, seed, queries, orbit_limit=None):
    start = time.perf_counter_ns()
    view, curve, subgroup_order, base, geometry = make_base(degree, weight, orbit_limit)
    base_wall_ns = time.perf_counter_ns() - start
    rng = random.Random(seed)
    generator = curve.randomPointOfOrder(subgroup_order, 4, rng)
    fixtures = []
    for _ in range(queries):
        scalar = rng.randrange(1, subgroup_order)
        target = curve.mul(generator, scalar)
        fixtures.append({"target": target, "fixture_scalar": scalar})
    workload = {"curve": [degree, geometry["field_modulus"], 0, 1,
                           subgroup_order, 4, generator],
                "target_points": [row["target"] for row in fixtures],
                "target_seed": seed,
                "target_count": queries,
                "input_law": "uniform_nonzero_scalar_times_generator"}
    workload_id = hashlib.sha256(json.dumps(workload, sort_keys=True,
                           separators=(",", ":")).encode()).hexdigest()[:12]
    index, index_info = build_index(curve, base, degree)
    direct_index, direct_info = build_direct_index(curve, base)
    base_set = set(base)
    rows = []
    for fixture in fixtures:
        answer = solve_query(curve, index, fixture["target"], degree)
        direct = solve_direct(curve, direct_index, fixture["target"])
        if answer["status"] != direct["status"]:
            raise AssertionError("quotient and direct indexes disagree on coverage")
        if answer["points"] is not None:
            if any(point not in base_set for point in answer["points"]):
                raise AssertionError("witness point is outside factor base")
            if curve.mul(generator, fixture["fixture_scalar"]) != answer["sum_replay"]:
                raise AssertionError("fixture scalar replay failed")
        rows.append({"target": fixture["target"], **answer,
                     "direct_oracle": direct,
                     "scalar_replay_verified": answer["points"] is not None})
    source_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() != "Darwin":
        peak_rss *= 1024
    return {"kind": "four_point_signed_frobenius_quotient_pair_stage_probe",
            "scope": "toy public subgroup queries; PDP stage and exact pair-index oracle only",
            "stage_id": "quotient_pair_stage_20260926",
            "proposal_id": None,
            "candidate_id": None,
            "online_speedup": None,
            "degree": degree, "weight_at_most": weight,
            "summand_count": 4, "base_policy": "normal_basis_x_weight_then_cofactor_4_projection_and_both_signs; optional first_canonical_orbits",
            "query_count": queries, "seed": seed, "workload_id": workload_id,
            "workload": workload, "geometry": geometry,
            "base_build_wall_ns": base_wall_ns, "index": index_info,
            "direct_index": direct_info,
            "results": rows, "python": platform.python_version(),
            "peak_process_rss_bytes": peak_rss,
            "source_sha256": source_sha,
            "codegen_source_sha256": {name: hashlib.sha256((CODEGEN / name).read_bytes()).hexdigest()
                                      for name in ("curves.py", "field.py")}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(13, 19, 23), required=True)
    parser.add_argument("--weight", type=int, choices=(1, 2), required=True)
    parser.add_argument("--seed", type=int, default=260926)
    parser.add_argument("--queries", type=int, default=3)
    parser.add_argument("--orbit-limit", type=int, default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.queries < 1:
        parser.error("--queries must be positive")
    if args.orbit_limit is not None and args.orbit_limit < 1:
        parser.error("--orbit-limit must be positive")
    report = run(args.degree, args.weight, args.seed, args.queries, args.orbit_limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"degree": args.degree, "weight": args.weight,
                      "usable_points_B": report["geometry"]["usable_points_B"],
                      "quotient_pair_sum_keys": report["index"]["quotient_pair_sum_keys"],
                      "statuses": [row["status"] for row in report["results"]],
                      "query_wall_ns": [row["query_wall_ns"] for row in report["results"]]}))


if __name__ == "__main__":
    main()
