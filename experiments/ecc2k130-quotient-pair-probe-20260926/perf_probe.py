#!/usr/bin/env python3
"""Bounded n=53/83 stage throughput for the signed-Frobenius pair index.

The selected two-orbit base is complete when all eligible generators are
processed. Query prefixes price exact complement probes; they do not
measure relation yield or a discrete logarithm.
"""

import argparse
import hashlib
import itertools
import json
import os
import platform
import random
import resource
import statistics
import time
from pathlib import Path

import curves
import field
from quotient_pair_probe import CountedCurve, canonical, point_key, transform

HERE = Path(__file__).resolve().parent
COFACTOR = {53: 428, 83: 4}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def base_prefix(degree, cofactor, subgroup_order, orbit_count):
    started = time.perf_counter_ns()
    onb = field.Onb(degree)
    curve = curves.Curve(onb)
    seen_x = set()
    selected = []
    trials = 0
    for support in itertools.combinations(range(degree), 2):
        coords = (1 << support[0]) | (1 << support[1])
        x = onb.fromCoords(coords)
        if x in seen_x:
            continue
        trials += 1
        current = x
        for _ in range(degree):
            seen_x.add(current)
            current = onb.frob(current, 1)
        raw = curve.pointFromX(x)
        if raw is None:
            continue
        point = curve.mul(raw, cofactor)
        if point is None:
            continue
        if curve.mul(point, subgroup_order) is not None:
            raise AssertionError("projected point is outside the subgroup")
        selected.append({"normal_support": support, "raw": raw,
                         "projected": point})
        if len(selected) == orbit_count:
            break
    if len(selected) != orbit_count:
        raise AssertionError("not enough rational weight-two x orbits")
    points = set()
    for row in selected:
        current = row["projected"]
        for _ in range(degree):
            points.add(current)
            points.add(curve.neg(current))
            current = curve.frob(current)
    ordered = sorted(points)
    reps = sorted({canonical(curve, row["projected"], degree)[0]
                   for row in selected})
    if len(reps) != orbit_count or len(ordered) != 2 * degree * orbit_count:
        raise AssertionError("selected signed Frobenius orbits overlap")
    return onb, curve, ordered, reps, {
        "selected_orbits": selected,
        "rational_x_orbits_examined": trials,
        "actual_usable_points_B": len(ordered),
        "base_sha256": hashlib.sha256(frozen_json(ordered)).hexdigest(),
        "base_build_ns": time.perf_counter_ns() - started,
    }


def build_prefix(curve, base, reps, degree, max_generators):
    counted = CountedCurve(curve)
    index = {}
    started = time.perf_counter_ns()
    generated = 0
    for left in reps:
        for right in base:
            if generated == max_generators:
                break
            generated += 1
            total = counted.add(left, right)
            key, shift, sign = canonical(counted, total, degree)
            if key not in index:
                index[key] = (transform(counted, left, shift, sign),
                              transform(counted, right, shift, sign))
        if generated == max_generators:
            break
    wall = time.perf_counter_ns() - started
    if generated != max_generators:
        raise AssertionError("generator budget exceeds eligible pairs")
    for key, pair in index.items():
        if point_key(curve.add(*pair)) != key:
            raise AssertionError("pair witness failed independent group replay")
    return index, {"eligible_generator_pairs": len(reps) * len(base),
                   "generators_processed": generated,
                   "index_keys_in_prefix": len(index),
                   "index_prefix_sha256": hashlib.sha256(frozen_json(
                       sorted((key, pair) for key, pair in index.items()))).hexdigest(),
                   "build_wall_ns": wall, "build_operations": counted.counts}


def query_prefix(curve, index, target, degree, max_lookups):
    counted = CountedCurve(curve)
    started = time.perf_counter_ns()
    verified = 0
    lookups = 0
    for key, left_pair in index.items():
        current = None if key == (-1, -1) else key
        for shift in range(degree):
            for sign in (1, -1):
                candidate = current if sign == 1 else counted.neg(current)
                complement = counted.add(target, counted.neg(candidate))
                comp_key, comp_shift, comp_sign = canonical(
                    counted, complement, degree)
                lookups += 1
                counted.counts["lookup"] += 1
                match = index.get(comp_key)
                if match is not None:
                    first = tuple(transform(counted, point, shift, sign)
                                  for point in left_pair)
                    second = tuple(transform(counted, point,
                                             (-comp_shift) % degree, comp_sign)
                                   for point in match)
                    total = None
                    for point in first + second:
                        total = curve.add(total, point)
                    if total != target:
                        raise AssertionError("partial-index hit failed group replay")
                    verified += 1
                if lookups == max_lookups:
                    return {"status": "budgeted_prefix", "lookups": lookups,
                            "verified_hits_in_prefix": verified,
                            "wall_ns": time.perf_counter_ns() - started,
                            "operations": counted.counts}
            current = counted.frob(current)
    raise AssertionError("lookup budget exceeds available prefix traversal")


def run(degree, seed, orbit_count, max_generators, max_lookups, repetitions):
    cofactor = COFACTOR[degree]
    curve_order = curves.curveOrder(degree)
    assert curve_order % cofactor == 0
    subgroup_order = curve_order // cofactor
    if not curves.isPrimeBig(subgroup_order):
        raise AssertionError("declared subgroup order failed primality check")
    onb, curve, base, reps, base_info = base_prefix(
        degree, cofactor, subgroup_order, orbit_count)
    rng = random.Random(seed)
    generator = curve.randomPointOfOrder(subgroup_order, cofactor, rng)
    scalar = rng.randrange(1, subgroup_order)
    target = curve.mul(generator, scalar)
    if target is None or curve.mul(generator, scalar) != target:
        raise AssertionError("target fixture failed scalar replay")
    index, index_info = build_prefix(curve, base, reps, degree,
                                     max_generators)
    queries = [query_prefix(curve, index, target, degree, max_lookups)
               for _ in range(repetitions)]
    if any(row["lookups"] != max_lookups for row in queries):
        raise AssertionError("query budget was not charged")
    identity = {"field": {"p": 2, "n": degree, "basis": "type_ii_optimal_normal",
                          "defining_modulus": f"symmetric subalgebra of F2[z]/(z^{2 * degree + 1}-1), modulo sum(z^i, i=0..{2 * degree})",
                          "basis_coordinates": "bit i-1 is coefficient of gamma_i=zeta^i+zeta^-i, i=1..n",
                          "element_encoding": "nonnegative integer native ONB symmetric bit vector, normalized bit zero"},
                "curve": {"model": "y^2 + x*y = x^3 + 1", "a1": 1,
                          "a2": 0, "a3": 0, "a4": 0, "a6": 1,
                          "order": curve_order, "subgroup_order": subgroup_order,
                          "cofactor": cofactor, "generator": generator,
                          "target_group": "subgroup generated by generator"}}
    curve_id = "EC1N%dCkb1h%s" % (
        degree, hashlib.sha256(frozen_json(identity)).hexdigest()[:12])
    workload = {"curve_id": curve_id, "target": target, "seed": seed,
                "target_count": 1,
                "input_law": "uniform nonzero scalar times fixed subgroup generator"}
    workload_id = hashlib.sha256(frozen_json(workload)).hexdigest()[:12]
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() != "Darwin":
        peak *= 1024
    return {
        "kind": "bounded_quotient_pair_stage_throughput",
        "claim_boundary": "one public ordinary subgroup target; selected two-orbit base and fixed query prefix; no coverage, DLP, or rho speedup claim",
        "candidate_id": None, "proposal_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "workload_id": workload_id, "workload": workload,
        "field_degree": degree, "cofactor": cofactor,
        "subgroup_order": str(subgroup_order),
        "basis": "type_ii_optimal_normal",
        "base_policy": "first two rational normal-weight-two x orbits, cofactor projected, both signs",
        "normal_weight": 2, "orbit_count": orbit_count,
        "base": base_info, "index_prefix": index_info,
        "query_lookup_budget": max_lookups, "query_repetitions": repetitions,
        "query_runs": queries,
        "query_wall_ns_median": int(statistics.median(
            row["wall_ns"] for row in queries)),
        "target_fixture_scalar": scalar,
        "target_fixture_scalar_replay_verified": True,
        "peak_process_rss_bytes": peak,
        "host": {"machine": platform.machine(), "system": platform.system(),
                 "python": platform.python_version(), "cpu_count": os.cpu_count()},
        "source_sha256": sha(Path(__file__)),
        "dependency_sha256": {name: sha(HERE / name) for name in (
            "quotient_pair_probe.py", "curves.py", "field.py")},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    parser.add_argument("--seed", type=int, default=260926)
    parser.add_argument("--orbits", type=int, default=2)
    parser.add_argument("--generators", type=int, default=128)
    parser.add_argument("--lookups", type=int, default=128)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if min(args.orbits, args.generators, args.lookups,
           args.repetitions) < 1:
        parser.error("budgets and repetitions must be positive")
    result = run(args.degree, args.seed, args.orbits, args.generators,
                 args.lookups, args.repetitions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"degree": args.degree,
                      "actual_B": result["base"]["actual_usable_points_B"],
                      "index_keys": result["index_prefix"]["index_keys_in_prefix"],
                      "index_build_ns": result["index_prefix"]["build_wall_ns"],
                      "query_median_ns": result["query_wall_ns_median"],
                      "query_status": [row["status"] for row in result["query_runs"]]}))


if __name__ == "__main__":
    main()
