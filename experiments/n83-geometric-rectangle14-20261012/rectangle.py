#!/usr/bin/env python3
"""Exhaustive lift bound and exact orbit replay for width-14 rectangles."""

import hashlib
import itertools
import json
import math
import sys
import time
from decimal import Decimal, localcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/n83-geometric-two-shift12-20261012"
sys.path.insert(0, str(PARENT))
from screen import exact_keys  # noqa: E402
sys.path[:0] = [str(ROOT / "ecc2k130/codegen"),
                str(ROOT / "experiments/koblitz-pair-claw-20260929")]
from curves import Curve  # noqa: E402
from field import Onb  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rectangle_scores(rows):
    """Each four-vertex set has three distinct K2,2 edge rectangles."""
    count = {tuple(row["shift_coordinates"]): row["valid_lifts"] for row in rows}
    assert len(count) == math.comb(71, 2)
    leaders = []
    scanned = 0
    for a, b, c, d in itertools.combinations(range(12, 83), 4):
        # Pair a with one of b,c,d; the other two form the opposite side.
        for left, right in ((b, (c, d)), (c, (b, d)), (d, (b, c))):
            edge = tuple(sorted((tuple(sorted((a, right[0]))),
                                 tuple(sorted((a, right[1]))),
                                 tuple(sorted((left, right[0]))),
                                 tuple(sorted((left, right[1]))))))
            score = sum(count[e] for e in edge)
            scanned += 1
            candidate = (score, edge)
            if len(leaders) < 2:
                leaders.append(candidate)
                leaders.sort(reverse=True)
            elif candidate > leaders[-1]:
                leaders[-1] = candidate
                leaders.sort(reverse=True)
    assert scanned == 3 * math.comb(71, 4) == 2914905
    assert leaders[0][0] > leaders[1][0]
    return scanned, leaders


def main():
    output = HERE / "rectangle.json"
    key_file = HERE / "rectangle_keys.bin"
    assert not output.exists() and not key_file.exists(), "refusing to overwrite evidence"
    protocol = json.loads((HERE / "protocol.json").read_text())
    screen_file = PARENT / "screen.json"
    prior_file = ROOT / "experiments/n83-geometric-width14-20261012/frontier.json"
    assert sha(screen_file) == protocol["screen_sha256"]
    assert sha(prior_file) == protocol["prior_frontier_sha256"]
    assert sha(PARENT / "screen.py") == protocol["screen_source_sha256"]
    assert sha(ROOT / "ecc2k130/codegen/curves.py") == protocol["curve_source_sha256"]
    assert sha(ROOT / "ecc2k130/codegen/field.py") == protocol["field_source_sha256"]
    assert sha(ROOT / "experiments/koblitz-pair-claw-20260929/orbit_key.py") == protocol["orbit_source_sha256"]
    assert sha(ROOT / "experiments/compact-s3-m4-20261003/field_bridges/n83_onb_poly.json") == protocol["bridge_sha256"]
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    screen = json.loads(screen_file.read_text())
    prior = json.loads(prior_file.read_text())["rows"][0]
    assert prior["dimension"] == 14 and prior["folded_columns_K"] == 8261
    assert screen["curve_id"] == protocol["curve_id"]

    start = time.perf_counter_ns()
    scanned, leaders = rectangle_scores(screen["rows"])
    winner_score, winner_edges = leaders[0]
    runner_score, runner_edges = leaders[1]
    assert winner_score == 8532 and runner_score == 8509
    onb = Onb(83)
    curve = Curve(onb)
    orbit = OrbitKey(onb)
    component = []
    key_sets = []
    for edge in winner_edges:
        geometry, keys = exact_keys((1 << edge[0]) ^ (1 << edge[1]),
                                    onb, curve, orbit)
        expected = next(row["valid_lifts"] for row in screen["rows"]
                        if tuple(row["shift_coordinates"]) == edge)
        assert geometry["valid_lifts"] == expected
        component.append({"shift_coordinates": list(edge), **geometry})
        key_sets.append(keys)
    union = set().union(*key_sets)
    K = len(union)
    assert K > runner_score, "cannot certify a unique optimum from the lift bound"
    B = 166 * K
    key_file.write_bytes(b"".join(k.to_bytes(21, "little") for k in sorted(union)))
    with localcontext() as context:
        context.prec = 50
        first_moment = str(Decimal(math.comb(B, 5)) /
                           Decimal(protocol["subgroup_order"]))
    result = {
        "kind": "n83_width14_four_coset_rectangle_optimum_v1",
        "status": "complete_geometry",
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "protocol_sha256": sha(HERE / "protocol.json"),
        "producer_source_sha256": sha(Path(__file__)),
        "screen_sha256": sha(screen_file),
        "prior_frontier_sha256": sha(prior_file),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "rectangle_count": scanned,
        "winner_edges": [list(edge) for edge in winner_edges],
        "winner_rational_lift_bound": winner_score,
        "runner_edges": [list(edge) for edge in runner_edges],
        "other_rectangle_column_upper_bound": runner_score,
        "components": component,
        "folded_columns_K": K,
        "actual_usable_points_B_before_folding": B,
        "duplicate_orbit_seeds_in_union": winner_score - sum(c["identity_projections"] for c in component) - K,
        "five_subset_first_moment": first_moment,
        "prior_shifted_width14_K": prior["folded_columns_K"],
        "prior_shifted_width14_B": prior["actual_usable_points_B_before_folding"],
        "prior_five_subset_first_moment": prior["five_subset_first_moment"],
        "key_file": key_file.name,
        "key_sha256": sha(key_file),
        "geometry_wall_ns_exploratory": time.perf_counter_ns() - start,
        "ordinary_query_relation_yield": None,
        "novel_rank_per_query": None,
        "one_target_online_ms": None,
    }
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"rectangles": scanned, "winner_lifts": winner_score,
                      "runner_lifts": runner_score, "K": K, "B": B}), flush=True)


if __name__ == "__main__":
    main()
