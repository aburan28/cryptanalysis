#!/usr/bin/env python3
"""Frozen N41 two-pair sums for a full-coordinate mixed-cubic rank screen."""

from __future__ import annotations

import hashlib
import json
import random
import resource
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
sys.path.insert(0, str(GOAL / "n41_two_free_pair_occupancy_20261009"))
from arithmetic_snapshot import Curve, Field  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pair_states(curve: Curve, rows: list) -> list[tuple[int, tuple[int, int], int]]:
    states = []
    for a in range(len(rows)):
        for b in range(a + 1, len(rows)):
            if rows[a][2] == rows[b][2]:
                continue
            point = curve.add(tuple(rows[a][:2]), tuple(rows[b][:2]))
            if point is None:
                raise ValueError("pair sum is identity")
            states.append((rows[a][3] ^ rows[b][3], point,
                           (1 << rows[a][2]) | (1 << rows[b][2])))
    if len(states) != 1956:
        raise ValueError("pair domain size changed")
    return states


def main() -> None:
    protocol_file = HERE / "protocol.json"
    protocol = json.loads(protocol_file.read_text())
    for name, value in protocol["inputs"].items():
        if digest(Path(value)) != protocol["input_sha256"][name]:
            raise ValueError(f"input changed: {name}")
    if digest(Path(__file__)) != protocol["source_sha256"]["produce.py"]:
        raise ValueError("producer changed after freeze")
    rows_file = HERE / "rows.bin"
    receipt_file = HERE / "production.json"
    if rows_file.exists() or receipt_file.exists():
        raise FileExistsError("preserve first frozen production")
    start = time.monotonic_ns()
    decoded = json.loads(Path(protocol["inputs"]["decoded"]).read_text())
    holdout = json.loads(Path(protocol["inputs"]["holdout"]).read_text())
    geometry = json.loads(Path(protocol["inputs"]["geometry"]).read_text())["n41"]
    for source in (decoded, holdout, geometry):
        if source["curve_id"] != protocol["curve_id"]:
            raise ValueError("curve ID changed")
    curve = Curve(Field(41, [0, 3]), 0)
    domains = [pair_states(curve, geometry["point_rows_by_unique_rotation"][str(r)])
               for r in protocol["pair_rotations"]]
    seen = set()
    selected = []
    counts = {"source_examined": 0, "source_column_rejects": 0,
              "source_duplicate_rejects": 0, "source_accepted": 0,
              "random_draws": 0, "random_duplicate_rejects": 0,
              "random_column_rejects": 0, "random_accepted": 0}

    def accept(i: int, j: int, expected: list[int] | None) -> bytes:
        left, right = domains[0][i], domains[1][j]
        if left[2] & right[2]:
            raise ValueError("repeated folded column")
        point = curve.add(left[1], right[1])
        if point is None or (expected is not None and list(point) != expected):
            raise ValueError("exact group sum changed")
        if point[0] & 1:
            raise ValueError("subgroup sum has odd x trace")
        selected.append((i, j))
        return (bytes([left[0], right[0]]) + point[0].to_bytes(6, "little") +
                point[1].to_bytes(6, "little") + struct.pack("<HH", i, j))

    records = bytearray()
    for source in (decoded["rows"], holdout["rows"]):
        for record in source:
            counts["source_examined"] += 1
            i, j = record["pair_state_indices"][-2:]
            if (i, j) in seen:
                counts["source_duplicate_rejects"] += 1
                continue
            seen.add((i, j))
            if domains[0][i][2] & domains[1][j][2]:
                counts["source_column_rejects"] += 1
                continue
            records.extend(accept(i, j, record["sum_point"]))
            counts["source_accepted"] += 1
    rng = random.Random(protocol["random_seed"])
    while len(selected) < protocol["row_count"]:
        if counts["random_draws"] >= protocol["limits"]["max_random_draws"]:
            raise TimeoutError("random draw cap before requested row count")
        i, j = rng.randrange(1956), rng.randrange(1956)
        counts["random_draws"] += 1
        if (i, j) in seen:
            counts["random_duplicate_rejects"] += 1
            continue
        seen.add((i, j))
        if domains[0][i][2] & domains[1][j][2]:
            counts["random_column_rejects"] += 1
            continue
        records.extend(accept(i, j, None))
        counts["random_accepted"] += 1
    if len(records) != protocol["row_count"] * 18:
        raise ValueError("binary row width changed")
    rows_file.write_bytes(records)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    peak = usage.ru_maxrss * (1 if sys.platform == "darwin" else 1024)
    receipt = {"status": "EXACT_ROWS_WRITTEN", "kind": protocol["kind"],
               "proposal_id": protocol["proposal_id"], "candidate_id": None,
               "curve_id": protocol["curve_id"], "rows": len(selected),
               "counts": counts, "rows_sha256": digest(rows_file),
               "index_pairs_sha256": hashlib.sha256(
                   ",".join(f"{i}:{j}" for i, j in selected).encode()).hexdigest(),
               "source_sha256": {"protocol": digest(protocol_file),
                                 "producer": digest(Path(__file__))},
               "exploratory_wall_ns": time.monotonic_ns() - start,
               "peak_rss_bytes": peak}
    receipt_file.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "rows": len(selected),
                      "counts": counts, "wall_s": receipt["exploratory_wall_ns"] / 1e9}))


if __name__ == "__main__":
    main()
