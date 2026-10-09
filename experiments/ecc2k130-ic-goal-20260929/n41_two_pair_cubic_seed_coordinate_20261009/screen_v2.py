#!/usr/bin/env python3
"""Corrected mixed-cubic rank gate with four distinct folded columns."""

from __future__ import annotations

import hashlib
import json
import random
import resource
import sys
import time
from pathlib import Path

import screen as algebra

HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "protocol_v2.json"
RESULT = HERE / "result_v2.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pair_states(curve: algebra.Curve, rows: list) -> list[tuple[int, tuple[int, int], int]]:
    states = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            if rows[i][2] == rows[j][2]:
                continue
            point = curve.add(tuple(rows[i][:2]), tuple(rows[j][:2]))
            if point is None:
                raise ValueError("admissible pair unexpectedly sums to identity")
            states.append((rows[i][3] ^ rows[j][3], point,
                           (1 << rows[i][2]) | (1 << rows[j][2])))
    if len(states) != 1956:
        raise ValueError("frozen pair-domain size changed")
    return states


def main() -> None:
    if RESULT.exists():
        raise FileExistsError("preserve first distinct-column rank result")
    protocol = json.loads(PROTOCOL.read_text())
    input_paths = {name: Path(value) for name, value in protocol["inputs"].items()}
    if sha(Path(__file__)) != protocol["source_sha256"]["screen_v2"]:
        raise ValueError("v2 source changed after freeze")
    for name, path in input_paths.items():
        if sha(path) != protocol["input_sha256"][name]:
            raise ValueError(f"frozen input changed: {name}")
    if (sha(HERE / "screen.py") != protocol["source_sha256"]["screen_v1"] or
            sha(HERE / "result.json") != protocol["input_sha256"]["result_v1"]):
        raise ValueError("first screen or its receipt changed")
    terms, term_index = algebra.feature_family()
    if len(terms) != protocol["feature_count"]:
        raise ValueError("feature family changed")
    decoded = json.loads(input_paths["decoded_rows"].read_text())
    holdout = json.loads(input_paths["holdout_rows"].read_text())
    geometry = json.loads(input_paths["geometry"].read_text())["n41"]
    if (decoded["curve_id"] != protocol["curve_id"] or
            holdout["curve_id"] != protocol["curve_id"] or
            geometry["curve_id"] != protocol["curve_id"] or
            len(decoded["rows"]) != 8192 or len(holdout["rows"]) != 8192):
        raise ValueError("frozen source rows or curve changed")
    field = algebra.Field(41, [0, 3])
    curve = algebra.Curve(field, 0)
    domains = [pair_states(curve, geometry["point_rows_by_unique_rotation"][str(r)])
               for r in protocol["pair_rotations"]]
    seen = {tuple(record["pair_state_indices"][-2:])
            for source in (decoded["rows"], holdout["rows"])
            for record in source}
    if len(seen) != protocol["unique_source_index_pairs"]:
        raise ValueError("source index-pair inventory changed")
    basis: dict[int, int] = {}
    coordinate_basis: dict[int, int] = {}
    valid_indices: list[tuple[int, int]] = []
    pivot_indices = []
    counts = {"source_rows_seen": 0, "source_column_rejects": 0,
              "source_rows_accepted": 0, "extra_draws": 0,
              "extra_duplicate_draws": 0, "extra_column_rejects": 0,
              "extra_rows_accepted": 0}
    start = time.monotonic_ns()
    deadline = start + int(protocol["limits"]["wall_seconds"] * 1e9)
    status = "SOURCE_EXHAUSTED"
    error = None

    def accept(i: int, j: int, expected: list[int] | None) -> bool:
        left, right = domains[0][i], domains[1][j]
        if left[2] & right[2]:
            return False
        total = curve.add(left[1], right[1])
        if total is None or (expected is not None and list(total) != expected):
            raise ValueError("saved or generated exact group sum changed")
        if total[0] & 1:
            raise ValueError("four-column subgroup sum has odd x trace")
        vector = algebra.row_bits(left[0], right[0], total[0], term_index)
        algebra.insert_high(coordinate_basis, algebra.coordinate_bits(total[0]))
        valid_indices.append((i, j))
        if algebra.insert_high(basis, vector):
            pivot_indices.append(len(valid_indices) - 1)
        return True

    try:
        for source_name, records in (("decoded", decoded["rows"]),
                                     ("holdout", holdout["rows"])):
            for record in records:
                counts["source_rows_seen"] += 1
                i, j = record["pair_state_indices"][-2:]
                left, right = domains[0][i], domains[1][j]
                if source_name == "decoded" and record["pair_seed_sums"] != [left[0], right[0]]:
                    raise ValueError("source seed sums changed")
                if left[2] & right[2]:
                    counts["source_column_rejects"] += 1
                    continue
                if accept(i, j, record["sum_point"]):
                    counts["source_rows_accepted"] += 1
                if len(basis) == len(terms):
                    status = "FULL_DISTINCT_COLUMN_MIXED_CUBIC_RANK"
                    break
                if counts["source_rows_seen"] % 64 == 0 and time.monotonic_ns() >= deadline:
                    status = "TIME_CAP"
                    break
            if status != "SOURCE_EXHAUSTED":
                break
        if status == "SOURCE_EXHAUSTED":
            rng = random.Random(protocol["extra_seed"])
            while counts["extra_draws"] < protocol["limits"]["max_extra_draws"]:
                i, j = rng.randrange(1956), rng.randrange(1956)
                counts["extra_draws"] += 1
                if (i, j) in seen:
                    counts["extra_duplicate_draws"] += 1
                    continue
                seen.add((i, j))
                if domains[0][i][2] & domains[1][j][2]:
                    counts["extra_column_rejects"] += 1
                    continue
                if accept(i, j, None):
                    counts["extra_rows_accepted"] += 1
                if len(basis) == len(terms):
                    status = "FULL_DISTINCT_COLUMN_MIXED_CUBIC_RANK"
                    break
                if counts["extra_draws"] % 64 == 0:
                    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                    if sys.platform != "darwin":
                        rss *= 1024
                    if time.monotonic_ns() >= deadline:
                        status = "TIME_CAP"
                        break
                    if rss >= protocol["limits"]["rss_bytes"]:
                        status = "MEMORY_CAP"
                        break
            else:
                status = "EXTRA_DRAW_CAP"
    except Exception as exc:
        status = "PRODUCER_FAILURE"
        error = {"type": type(exc).__name__, "message": str(exc)}

    coordinate_features = 1 + 40 + 40 * 39 // 2
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        rss *= 1024
    result = {
        "kind": protocol["kind"], "status": status, "error": error,
        "proposal_id": protocol["proposal_id"], "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "target_count": 1,
        "public_target_q": protocol["public_target_q"],
        "distinct_column_policy": "all four signed/Frobenius column IDs differ",
        "feature_count": len(terms), "coordinate_feature_count": coordinate_features,
        "rank": len(basis), "coordinate_rank": len(coordinate_basis),
        "mixed_excess_nullity": (len(terms) - len(basis)) -
                                 (coordinate_features - len(coordinate_basis)),
        "counts": counts,
        "valid_index_pairs_sha256": hashlib.sha256(
            ",".join(f"{i}:{j}" for i, j in valid_indices).encode()).hexdigest(),
        "pivotal_valid_row_indices_sha256": hashlib.sha256(
            ",".join(map(str, pivot_indices)).encode()).hexdigest(),
        "exploratory_wall_ns": time.monotonic_ns() - start,
        "peak_rss_bytes": rss,
        "source_sha256": {"protocol": sha(PROTOCOL),
                          "screen_v2": sha(Path(__file__)),
                          "screen_v1": sha(HERE / "screen.py"),
                          **{name: sha(path) for name, path in input_paths.items()}},
        "claim_boundary": protocol["claim_boundary"],
    }
    with RESULT.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": status, "rank": len(basis),
                      "coordinate_rank": len(coordinate_basis),
                      "valid_rows": len(valid_indices), "counts": counts,
                      "wall_s": result["exploratory_wall_ns"] / 1e9}, sort_keys=True))


if __name__ == "__main__":
    main()
