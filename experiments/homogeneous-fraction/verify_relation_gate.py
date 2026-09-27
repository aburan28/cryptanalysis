#!/usr/bin/env python3
"""Independently replay the fraction-base receipts through the repo's C curve."""

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "pdp-degree-heuristics"))

from toycurve import ToyCurve  # noqa: E402

ORDER = 2003


def rank(rows):
    pivots = {}
    for row in rows:
        vector = [int(x) % ORDER for x in row]
        for col in sorted(pivots):
            if vector[col]:
                f = vector[col]
                vector = [(a - f * b) % ORDER for a, b in zip(vector, pivots[col])]
        col = next((i for i, x in enumerate(vector) if x), None)
        if col is not None:
            inv = pow(vector[col], ORDER - 2, ORDER)
            pivots[col] = [x * inv % ORDER for x in vector]
    return len(pivots)


def verify(path):
    runs = json.loads(path.read_text())["runs"]
    tiny = ToyCurve(7)
    assert (tiny.mod, tiny.order, tiny.r, tiny.h) == (0x83, 116, 29, 4)
    tiny_xs = set()
    for word in range(1 << 4):
        a = (1 if word & 1 else 0) ^ (2 if word & 2 else 0)
        b = (1 if word & 4 else 0) ^ (2 if word & 8 else 0)
        if b:
            tiny_xs.add(tiny.K.mul(a, tiny.K.inv(b)))
    tiny_points = []
    for x in tiny_xs:
        point = tiny.K.lift(x)
        if point is not None:
            tiny_points.append(point)
            if x:
                tiny_points.append(tiny.K.neg(point))
    assert len(tiny_points) == 3
    assert all(tiny.K.smul(point, 4)[0] == tiny.K.smul(tiny.G, 0)[0]
               for point in tiny_points)
    curve = ToyCurve(13)
    assert curve.mod == 0x2027
    assert (curve.order, curve.r, curve.h) == (8012, ORDER, 4)
    ec = curve.K
    inf = ec.smul(curve.G, 0)
    cases = successes = 0
    for run in runs:
        assert len(run["attempts"]) == run["counts"]["ordinary_attempts"]
        assert len(run["targets"]) == run["counts"]["attempt_budget"]
        if run["target_rank"]:
            assert run["status"] == "rank_reached"
            assert run["attempts"][-1]["rank_after"] == run["target_rank"]
            assert all(a["rank_after"] < run["target_rank"] for a in run["attempts"][:-1])
        else:
            assert run["status"] == "fixed_attempts_complete"
            assert len(run["attempts"]) == len(run["targets"])
        base = run["base"]
        original = [tuple(point) for point in base["original_points"]]
        projected = {point: ec.smul(point, 4) for point in original}
        images = {p for p in projected.values() if p != inf}
        assert sorted(images) == [tuple(p) for p in base["projected_points"]]
        reps = [tuple(p) for p in base["signed_representatives"]]
        assert len(images) == 16 and len(reps) == 8
        for point in images:
            assert ec.smul(point, ORDER) == inf
        signed_column = {point: (i, sign) for i, rep in enumerate(reps)
                         for point, sign in ((rep, 1), (ec.neg(rep), -1))}
        assert len(signed_column) == 16
        G = tuple(base["generator"])
        assert ec.smul(G, ORDER) == inf and G != inf
        pair_sums = collections.Counter(
            ec.add(original[i], original[j])
            for i in range(len(original))
            for j in range(i, len(original)))
        assert sum(pair_sums.values()) == 630
        rows = []
        counts = collections.Counter()
        for attempt in run["attempts"]:
            cases += 1
            Q = tuple(attempt["target_point"])
            scalar = attempt["target_scalar"]
            assert Q == ec.smul(G, scalar)
            exists = any(pair_sums[ec.add(Q, ec.neg(p))]
                         for p in original)
            assert exists == (attempt["status"] != "no_relation")
            counts[attempt["status"]] += 1
            if attempt["status"] == "new_independent_relation":
                record = attempt["relation"]
                points = [tuple(p) for p in record["points"]]
                assert all(p in projected for p in points)
                assert ec.add(ec.add(points[0], points[1]), points[2]) == Q
                projected_sum = ec.add(
                    ec.add(projected[points[0]], projected[points[1]]),
                    projected[points[2]])
                assert projected_sum == ec.smul(Q, 4)
                assert ec.smul(G, record["projected_rhs_scalar"]) == projected_sum
                vector = [0] * len(reps)
                for point in points:
                    p4 = projected[point]
                    if p4 != inf:
                        j, sign = signed_column[p4]
                        vector[j] += sign
                assert tuple(vector) == tuple(record["coefficients"])
                rows.append(vector)
                successes += 1
            assert attempt["rank_after"] == rank(rows)
        assert counts["new_independent_relation"] == run["counts"]["novel_rows"]
        assert counts["no_relation"] == run["counts"]["failed_targets"]
        assert counts["dependent_relation"] == run["counts"]["dependent_targets"]
        assert rank(rows) == run["counts"]["rank"] <= 8
        costs = run["timings_ns"]
        assert sum(v for k, v in costs.items() if k != "charged_total") == costs["charged_total"]
        assert run["driver_wall_ns_including_startup"] >= costs["charged_total"]
    return {"independent_implementation": "ToyCurve / pdpkernel.c",
            "prior_n7_k1_fraction_points": 3, "prior_n7_k1_nonidentity_projected": 0,
            "runs": len(runs), "attempts_checked": cases,
            "novel_point_and_rank_certificates_checked": successes,
            "status": "PASS"}


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("relation_gate_results.json")
    print(json.dumps(verify(path)))
