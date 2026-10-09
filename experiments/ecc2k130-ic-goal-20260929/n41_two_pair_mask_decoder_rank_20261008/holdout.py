#!/usr/bin/env python3
"""Independent-pair holdout for candidate coordinate-only quadratic relations."""

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
from run_n41_disjoint_s5_sat import Curve, Field  # noqa: E402

COORD_BITS = 81
FEATURES = 1 + COORD_BITS + COORD_BITS * (COORD_BITS - 1) // 2


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def feature_vector(x: int, y: int) -> int:
    assert x & 1 == 0
    mask = (x >> 1) | (y << 40)
    active = [i for i in range(COORD_BITS) if mask >> i & 1]
    value = 1
    for i in active:
        value |= 1 << (1 + i)
    for at, i in enumerate(active):
        base = 1 + COORD_BITS + i * (2 * COORD_BITS - i - 1) // 2
        for j in active[at + 1:]:
            value |= 1 << (base + j - i - 1)
    return value


def insert_high(basis: dict[int, int], value: int) -> bool:
    while value:
        pivot = value.bit_length() - 1
        prior = basis.get(pivot)
        if prior is None:
            basis[pivot] = value
            return True
        value ^= prior
    return False


def main() -> None:
    rows_out = HERE / "holdout_rows.json"
    result_out = HERE / "holdout_result.json"
    if rows_out.exists() or result_out.exists():
        raise FileExistsError("preserve first holdout")
    start = time.monotonic_ns()
    protocol_path = HERE / "protocol_holdout.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {name: (HERE / protocol[name]).resolve() for name in
             ("initial_rows", "initial_result", "geometry", "curve_arithmetic")}
    for name, path in paths.items():
        assert sha(path) == protocol[f"{name}_sha256"]
    initial = json.loads(paths["initial_rows"].read_text())
    initial_result = json.loads(paths["initial_result"].read_text())
    geometry = json.loads(paths["geometry"].read_text())["n41"]
    assert initial_result["sample_rows_consumed"] == len(initial["rows"]) == 8192
    assert initial_result["status"] == "SAMPLE_RANK_DEFICIT"
    assert geometry["curve_id"] == protocol["curve_id"]
    assert protocol["coordinate_feature_count"] == FEATURES
    basis: dict[int, int] = {}
    for row in initial["rows"]:
        insert_high(basis, feature_vector(*row["sum_point"]))
    rank_before = len(basis)
    assert rank_before == protocol["initial_coordinate_rank"]

    field = Field(41, [0, 3])
    curve = Curve(field, 0)
    domains = []
    for rotation in (20, 30):
        points = geometry["point_rows_by_unique_rotation"][str(rotation)]
        states = []
        for i in range(64):
            for j in range(i + 1, 64):
                if points[i][2] == points[j][2]:
                    continue
                total = curve.add(tuple(points[i][:2]), tuple(points[j][:2]))
                assert total is not None
                states.append(total)
        assert len(states) == 1956
        domains.append(states)

    rng = random.Random(protocol["holdout_seed"])
    seen = {tuple(row["pair_state_indices"]) for row in initial["rows"]}
    holdout = []
    pivotal = []
    trials = 0
    status = "HOLDOUT_RANK_DEFICIT"
    while len(holdout) < protocol["maximum_new_unique_pair_combinations"]:
        trials += 1
        i = rng.randrange(1956)
        j = rng.randrange(1956)
        if (i, j) in seen:
            continue
        seen.add((i, j))
        total = curve.add(domains[0][i], domains[1][j])
        assert total is not None
        x, y = total
        holdout.append({"pair_state_indices": [i, j], "sum_point": [x, y]})
        if insert_high(basis, feature_vector(x, y)):
            pivotal.append(len(holdout) - 1)
        if len(basis) == FEATURES:
            status = "FULL_COORDINATE_RANK"
            break
        if len(holdout) % 64 == 0:
            if time.monotonic_ns() - start >= protocol["limits"]["wall_seconds"] * 10**9:
                status = "TIME_CAP"
                break
            if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss >= protocol["limits"]["peak_rss_bytes"]:
                status = "MEMORY_CAP"
                break

    row_record = {
        "kind": "n41_two_pair_coordinate_quadratic_holdout_rows",
        "curve_id": protocol["curve_id"],
        "status": status,
        "seed": protocol["holdout_seed"],
        "rows": holdout,
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
        "initial_rank": rank_before,
        "combined_rank": len(basis),
        "new_rows_consumed": len(holdout),
        "draws_including_duplicates": trials,
        "pivotal_holdout_row_indices": pivotal,
        "basis_pivots_sha256": hashlib.sha256(
            ",".join(map(str, sorted(basis))).encode()).hexdigest(),
        "exploratory_wall_ns": time.monotonic_ns() - start,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "source_sha256": {**{name: sha(path) for name, path in paths.items()},
                          "protocol": sha(protocol_path),
                          "holdout": sha(Path(__file__)),
                          "holdout_rows": sha(rows_out)},
        "claim_boundary": protocol["claim_boundary"],
    }
    result_out.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": status, "initial_rank": rank_before,
                      "combined_rank": len(basis),
                      "new_rows": len(holdout),
                      "wall_s": result["exploratory_wall_ns"] / 1e9}))


if __name__ == "__main__":
    main()
