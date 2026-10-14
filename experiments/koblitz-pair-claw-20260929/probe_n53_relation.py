#!/usr/bin/env python3
"""Bounded ordinary n=53 four-point relation probe on a full weight-3 base."""

import hashlib
import json
import math
import platform
import random
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
REFERENCE = (HERE.parent / "ecc2k130-quotient-pair-probe-20260926" /
             "runs" / "n53_perf_prefix.json")
sys.path.insert(0, str(CODEGEN))

import curves
import field
import indexcalc
from run_n23 import digest_state, frozen, point_digest, replay_endpoint, sha, step

N = 53
WEIGHT = 3
DP_BITS = 10
MAX_TRAIL = 32768
MAX_WALK_EVALS = 5000000
WALK_SEED = 530929


def base_and_columns(curve, onb, order, cofactor):
    points = set()
    rational_x = 0
    for support in indexcalc.combinationsUpTo(N, WEIGHT):
        if not support:
            continue
        x = onb.fromCoords(sum(1 << bit for bit in support))
        point = curve.pointFromX(x)
        if point is None:
            continue
        rational_x += 1
        projected = curve.mul(point, cofactor)
        if projected is None:
            continue
        assert curve.mul(projected, order) is None
        points.add(projected)
        points.add(curve.neg(projected))
    points = sorted(points)
    visited = set()
    representatives = []
    for point in points:
        if point in visited:
            continue
        representatives.append(point)
        current = point
        for _ in range(N):
            visited.add(current)
            visited.add(curve.neg(current))
            current = curve.frob(current)
    assert visited == set(points)
    return points, representatives, rational_x


def distinguished(point):
    digest = digest_state(point)
    return int.from_bytes(digest[12:16], "little") & ((1 << DP_BITS) - 1) == 0


def walk(curve, base, generator, order, target):
    rng = random.Random(WALK_SEED)
    endpoints = {}
    evaluations = 0
    trails = 0
    replays = 0
    rejected = 0
    discarded = 0
    started = time.perf_counter_ns()
    while evaluations < MAX_WALK_EVALS:
        seed = curve.mul(generator, rng.randrange(1, order))
        state, length = seed, 0
        while length < MAX_TRAIL and evaluations < MAX_WALK_EVALS:
            state, _ = step(curve, base, target, state)
            evaluations += 1
            length += 1
            if distinguished(state):
                break
        if not distinguished(state):
            discarded += 1
            continue
        trails += 1
        earlier = endpoints.get(state)
        if earlier is None:
            endpoints[state] = (seed, length)
            continue
        replays += 1
        relation = replay_endpoint(curve, base, target,
                                   earlier, (seed, length))
        if relation is not None:
            return {"status": "verified_four_point_relation",
                    "step_evaluations_excluding_replay": evaluations,
                    "wall_ns": time.perf_counter_ns() - started,
                    "trails": trails, "endpoint_rows": len(endpoints),
                    "endpoint_replays": replays,
                    "rejected_replays": rejected,
                    "discarded_no_endpoint": discarded,
                    "relation": relation}
        rejected += 1
    return {"status": "budget", "step_evaluations_excluding_replay": evaluations,
            "wall_ns": time.perf_counter_ns() - started,
            "trails": trails, "endpoint_rows": len(endpoints),
            "endpoint_replays": replays, "rejected_replays": rejected,
            "discarded_no_endpoint": discarded, "relation": None}


def main():
    reference = json.loads(REFERENCE.read_text())
    identity = reference["curve_identity_record"]
    curve_id = "EC1N53Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert reference["curve_id"] == curve_id
    order = int(reference["subgroup_order"])
    cofactor = identity["curve"]["cofactor"]
    assert identity["curve"]["order"] == cofactor * order
    onb = field.Onb(N)
    curve = curves.Curve(onb)
    generator = tuple(identity["curve"]["generator"])
    target = tuple(reference["workload"]["target"])
    assert curve.onCurve(generator) and curve.onCurve(target)
    assert curve.mul(generator, order) is None
    assert curve.mul(target, order) is None

    setup_started = time.perf_counter_ns()
    base, representatives, rational_x = base_and_columns(curve, onb,
                                                           order, cofactor)
    setup_ns = time.perf_counter_ns() - setup_started
    assert len(base) > 10000
    workload = {"curve_id": curve_id, "target": list(target),
                "target_count": 1, "target_input_law": "fixed public subgroup point",
                "normal_x_weight_bound": WEIGHT, "walk_seed": WALK_SEED,
                "distinguished_bits": DP_BITS, "max_trail": MAX_TRAIL,
                "max_walk_evaluations": MAX_WALK_EVALS}
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    result = walk(curve, base, generator, order, target)
    if result["relation"] is not None:
        points = [tuple(point) for point in result["relation"]["points"]]
        assert len(points) == 4 and all(point in base for point in points)
        total = None
        for point in points:
            total = curve.add(total, point)
        assert total == target
    report = {
        "kind": "n53_full_weight3_base_bounded_pair_claw_relation_probe",
        "scope": "one ordinary public target; relation stage only, no base logs or DLP",
        "proposal_id": "Q1037", "candidate_id": None, "run_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "workload_id": workload_id, "workload": workload,
        "isogeny": "none",
        "factor_base": {
            "construction": "all nonzero type-II ONB x supports of weight at most three; rational lift; cofactor projection; both signs; full Frobenius closure",
            "cofactor_projection": cofactor,
            "nominal_nonzero_x_coordinates": sum(math.comb(N, j)
                                                  for j in range(1, WEIGHT + 1)),
            "rational_x_coordinates": rational_x,
            "actual_usable_points_B_before_folding": len(base),
            "signed_frobenius_columns": len(representatives),
            "enumerated_set_sha256": point_digest(base)},
        "target_independent_base_and_column_setup_ns": setup_ns,
        "ordinary_query": result,
        "verified_relation_count": int(result["relation"] is not None),
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "peak_parent_rss_bytes": (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                                  if platform.system() == "Darwin" else
                                  resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
        "runtime": {"python": sys.version, "platform": platform.platform()},
        "source_sha256": sha(Path(__file__)),
        "walk_source_sha256": sha(HERE / "run_n23.py"),
        "reference_sha256": sha(REFERENCE),
        "dependency_sha256": {name: sha(CODEGEN / name)
                              for name in ("curves.py", "field.py", "indexcalc.py")},
    }
    path = HERE / "runs" / "n53_weight3_relation_probe.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"curve_id": curve_id, "B": len(base),
                      "columns": len(representatives),
                      "status": result["status"],
                      "walk_evaluations": result["step_evaluations_excluding_replay"],
                      "wall_s": result["wall_ns"] / 1e9,
                      "receipt": str(path)}))


if __name__ == "__main__":
    main()
