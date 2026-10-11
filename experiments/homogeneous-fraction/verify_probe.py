#!/usr/bin/env python3
"""Independent C curve replay of a selected-positive fraction witness."""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "pdp-degree-heuristics"))
from toycurve import ToyCurve  # noqa: E402


def verify(result, base):
    stages = result["stages"]
    if stages[-1]["stage"] != "exact_fallback_extracted":
        raise AssertionError("no extracted witness")
    w = stages[-1]["witness"]
    points = [tuple(p) for p in w["points"]]
    E = ToyCurve(13)
    assert (E.mod, E.order, E.r, E.h) == (0x2027, 8012, 2003, 4)
    ec = E.K
    G = tuple(base["generator"])
    input_stage = stages[0]
    rng = random.Random(result["seed"])
    scalar = [rng.randrange(1, E.r) for _ in range(result["target_index"] + 1)][-1]
    assert scalar == input_stage["target_scalar"]
    Q = tuple(input_stage["target_point"])
    assert ec.smul(G, scalar) == Q
    assert ec.smul(G, E.r) == ec.smul(G, 0) and G != ec.smul(G, 0)
    original = {tuple(p) for p in base["original_points"]}
    assert all(p in original for p in points)
    for word, point in zip(w["words"], points):
        a, b = word & 7, word >> 3
        assert b and ec.mul(a, ec.inv(b)) == point[0]
    assert ec.add(ec.add(points[0], points[1]), points[2]) == Q
    rhs = ec.smul(Q, 4)
    assert ec.add(ec.add(ec.smul(points[0], 4), ec.smul(points[1], 4)),
                  ec.smul(points[2], 4)) == rhs
    assert ec.smul(G, w["projected_rhs_scalar"]) == rhs
    reps = [tuple(p) for p in base["signed_representatives"]]
    signed = {p: (i, sign) for i, rep in enumerate(reps)
              for p, sign in ((rep, 1), (ec.neg(rep), -1))}
    row = [0] * len(reps)
    for p in points:
        p4 = ec.smul(p, 4)
        if p4 != ec.smul(G, 0):
            col, sign = signed[p4]
            row[col] += sign
    assert row == w["coefficients"] and any(row) and w["rank"] == 1
    return {"implementation": "ToyCurve / pdpkernel.c", "status": "PASS",
            "exact_signed_relation": True, "subgroup_rank": 1}


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("relation_probe_completed.json")
    base = json.loads(Path("relation_gate_results.json").read_text())["runs"][0]["base"]
    print(json.dumps(verify(json.loads(path.read_text()), base)))
