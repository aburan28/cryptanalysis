#!/usr/bin/env python3
"""Independent group replay and exact direct-support check of frozen runs."""

import hashlib
import itertools
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
import curves  # noqa: E402
import field  # noqa: E402


def group_sum(curve, points):
    result = None
    for point in points:
        result = curve.add(result, point)
    return result


def canonical_point(curve, point, degree):
    best = None
    current = point
    for _ in range(degree):
        for value in (current, curve.neg(current)):
            if best is None or value < best:
                best = value
        current = curve.frob(current)
    return best


def reconstruct_base(run, curve):
    geometry = run["geometry"]
    conjugates = geometry["normal_basis_conjugates"]
    degree = run["degree"]
    points = set()
    for weight in range(1, run["weight_at_most"] + 1):
        for support in itertools.combinations(range(degree), weight):
            x = 0
            for position in support:
                x ^= conjugates[position]
            raw = curve.pointFromX(x)
            if raw is None:
                continue
            point = curve.mul(raw, 4)
            if point is not None:
                points.add(point)
                points.add(curve.neg(point))
    if len(points) != geometry["preselection_usable_points_B"]:
        raise AssertionError("preselection base count differs")
    orbit_limit = geometry["selected_signed_frobenius_orbits"]
    if orbit_limit is not None:
        keys = {point: canonical_point(curve, point, degree) for point in points}
        chosen = set(sorted(set(keys.values()))[:orbit_limit])
        points = {point for point in points if keys[point] in chosen}
    ordered = sorted(points)
    encoded = json.dumps(ordered, separators=(",", ":")).encode()
    if hashlib.sha256(encoded).hexdigest() != geometry["base_sha256"]:
        raise AssertionError("base digest differs")
    if len(ordered) != geometry["usable_points_B"]:
        raise AssertionError("usable base count differs")
    return ordered


def verify(path):
    run = json.loads(path.read_text())
    degree = run["degree"]
    geometry = run["geometry"]
    curve = curves.CurvePb(field.Pb(degree, geometry["field_modulus"]))
    order = geometry["subgroup_order"]
    base = reconstruct_base(run, curve)
    base_set = set(base)
    if any(curve.mul(point, order) is not None for point in base):
        raise AssertionError("base point is outside subgroup")
    sums = set()
    for i, left in enumerate(base):
        for right in base[i:]:
            sums.add(curve.add(left, right))
    generator = tuple(run["workload"]["curve"][-1])
    if not curve.onCurve(generator) or curve.mul(generator, order) is not None:
        raise AssertionError("invalid workload generator")
    rng = random.Random(run["seed"])
    if curve.randomPointOfOrder(order, 4, rng) != generator:
        raise AssertionError("generator fixture does not reproduce")
    statuses = []
    for fixture, result in zip(run["workload"]["target_points"], run["results"]):
        target = tuple(fixture)
        if target != tuple(result["target"]):
            raise AssertionError("target mismatch")
        scalar = rng.randrange(1, order)
        if curve.mul(generator, scalar) != target:
            raise AssertionError("target fixture scalar does not replay")
        supported = any(curve.add(target, curve.neg(left)) in sums for left in sums)
        if supported != (result["status"] == "verified_decomposition"):
            raise AssertionError("independent direct-support result differs")
        if supported:
            witness = [tuple(point) for point in result["points"]]
            if len(witness) != 4 or any(point not in base_set for point in witness):
                raise AssertionError("witness outside exact base")
            if group_sum(curve, witness) != target:
                raise AssertionError("independent witness replay differs")
        statuses.append(result["status"])
    if len(statuses) != run["query_count"]:
        raise AssertionError("query count differs")
    return {"receipt": str(path.relative_to(HERE)),
            "receipt_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "actual_B": len(base), "distinct_direct_pair_sums": len(sums),
            "verified_decompositions": statuses.count("verified_decomposition"),
            "proved_absent": statuses.count("proved_no_four_sum_in_base")}


def verify_perf(path):
    """Replay inputs for a timed prefix without claiming a complete query."""
    run = json.loads(path.read_text())
    degree = run["field_degree"]
    curve = curves.Curve(field.Onb(degree))
    order = int(run["subgroup_order"])
    selected = run["base"]["selected_orbits"]
    points = set()
    for row in selected:
        x = curve.f.fromCoords(sum(1 << i for i in row["normal_support"]))
        raw = tuple(row["raw"])
        projected = tuple(row["projected"])
        if curve.pointFromX(x) != raw or curve.mul(raw, run["cofactor"]) != projected:
            raise AssertionError("perf base orbit does not reconstruct")
        if curve.mul(projected, order) is not None:
            raise AssertionError("perf base orbit is outside subgroup")
        current = projected
        for _ in range(degree):
            points.add(current)
            points.add(curve.neg(current))
            current = curve.frob(current)
    ordered = sorted(points)
    digest = hashlib.sha256(json.dumps(ordered, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()
    if digest != run["base"]["base_sha256"]:
        raise AssertionError("perf base digest differs")
    if len(ordered) != run["base"]["actual_usable_points_B"]:
        raise AssertionError("perf base count differs")
    generator = tuple(run["curve_identity_record"]["curve"]["generator"])
    target = tuple(run["workload"]["target"])
    if (not curve.onCurve(generator) or curve.mul(generator, order) is not None
            or curve.mul(generator, run["target_fixture_scalar"]) != target):
        raise AssertionError("perf ordinary-target scalar replay differs")
    index = run["index_prefix"]
    if index["generators_processed"] != index["eligible_generator_pairs"]:
        raise AssertionError("perf index is not complete for selected base")
    if any(query["status"] != "budgeted_prefix" or
           query["lookups"] != run["query_lookup_budget"]
           for query in run["query_runs"]):
        raise AssertionError("perf query prefix record differs")
    return {"receipt": str(path.relative_to(HERE)),
            "receipt_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "actual_B": len(ordered),
            "complete_selected_base_index_generators": index["generators_processed"],
            "bounded_query_lookups_per_repetition": run["query_lookup_budget"],
            "target_fixture_replayed": True}


def main():
    paths = sorted((HERE / "runs").glob("n*_w*_s260926.json"))
    rows = [verify(path) for path in paths]
    perf_rows = [verify_perf(path) for path in
                 sorted((HERE / "runs").glob("n*_perf_prefix.json"))]
    report = {"kind": "independent_quotient_pair_stage_replay",
              "scope": "exact toy four-sum support and bounded n53/n83 stage input replay",
              "candidate_id": None, "rows": rows, "perf_rows": perf_rows,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "curve_source_sha256": hashlib.sha256((HERE / "curves.py").read_bytes()).hexdigest()}
    (HERE / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"rows": rows, "perf_rows": perf_rows}, indent=2))


if __name__ == "__main__":
    main()
