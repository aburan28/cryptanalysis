#!/usr/bin/env python3
"""Coordinate-quadratic rank on independently sampled N41 curve points."""

from __future__ import annotations

import hashlib
import json
import random
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
sys.path.insert(0, str(GOAL))
from run_n41_disjoint_s5_sat import Curve, Field, points_with_x  # noqa: E402
from holdout import FEATURES, feature_vector, insert_high, sha  # noqa: E402


def main() -> None:
    rows_out = HERE / "curve_control_rows.json"
    result_out = HERE / "curve_control_result.json"
    if rows_out.exists() or result_out.exists():
        raise FileExistsError("preserve first control")
    start = time.monotonic_ns()
    protocol_path = HERE / "protocol_curve_control.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {name: (HERE / protocol[name]).resolve()
             for name in ("feature_script", "curve_arithmetic")}
    for name, path in paths.items():
        assert sha(path) == protocol[f"{name}_sha256"]
    assert protocol["feature_count"] == FEATURES
    field = Field(41, [0, 3])
    curve = Curve(field, 0)
    rng = random.Random(protocol["seed"])
    seen_x = set()
    rows = []
    basis: dict[int, int] = {}
    pivots = []
    attempts = 0
    no_point = 0
    duplicate_x = 0
    status = "SAMPLE_RANK_DEFICIT"
    while len(rows) < protocol["maximum_accepted_points"]:
        attempts += 1
        x = rng.getrandbits(40) << 1
        if x in seen_x:
            duplicate_x += 1
            continue
        seen_x.add(x)
        choices = points_with_x(curve, x)
        if not choices:
            no_point += 1
            continue
        assert len(choices) == 2 and all(curve.on_curve(p) for p in choices)
        y = choices[rng.randrange(2)][1]
        rows.append([x, y])
        if insert_high(basis, feature_vector(x, y)):
            pivots.append(len(rows) - 1)
        if len(basis) == FEATURES:
            status = "FULL_COORDINATE_RANK"
            break
        if len(rows) % 64 == 0:
            if time.monotonic_ns() - start >= protocol["limits"]["wall_seconds"] * 10**9:
                status = "TIME_CAP"
                break
            if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss >= protocol["limits"]["peak_rss_bytes"]:
                status = "MEMORY_CAP"
                break
    row_record = {
        "kind": "n41_curve_coordinate_quadratic_control_rows",
        "curve_id": protocol["curve_id"],
        "status": status,
        "seed": protocol["seed"],
        "points": rows,
    }
    rows_out.write_text(json.dumps(row_record, sort_keys=True, separators=(",", ":")) + "\n")
    result = {
        "kind": protocol["kind"],
        "status": status,
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None,
        "run_id": None,
        "curve_id": protocol["curve_id"],
        "feature_count": FEATURES,
        "rank": len(basis),
        "accepted_points": len(rows),
        "attempted_x": attempts,
        "x_without_curve_point": no_point,
        "duplicate_x": duplicate_x,
        "pivotal_row_indices": pivots,
        "basis_pivots_sha256": hashlib.sha256(
            ",".join(map(str, sorted(basis))).encode()).hexdigest(),
        "exploratory_wall_ns": time.monotonic_ns() - start,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "source_sha256": {**{name: sha(path) for name, path in paths.items()},
                          "protocol": sha(protocol_path),
                          "control": sha(Path(__file__)),
                          "control_rows": sha(rows_out)},
        "claim_boundary": protocol["claim_boundary"],
    }
    result_out.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": status, "rank": len(basis),
                      "accepted_points": len(rows), "attempted_x": attempts,
                      "wall_s": result["exploratory_wall_ns"] / 1e9}))


if __name__ == "__main__":
    main()
