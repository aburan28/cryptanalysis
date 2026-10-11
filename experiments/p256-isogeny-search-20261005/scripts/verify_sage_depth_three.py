#!/usr/bin/env python3
"""Verify the frozen depth-two screen, holdout, and depth-three traversal."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "receipt-sage-depth-three-20261006.json"
RESULTS = ROOT / "results" / "sage-depth-three-20261006"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(name: str) -> dict:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def depth_counts(payload: dict) -> dict[int, int]:
    counts: dict[int, int] = {}
    for candidate in payload["candidates"]:
        depth = len(candidate["path"])
        counts[depth] = counts.get(depth, 0) + 1
    return counts


def main() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    manifest = ROOT / receipt["source"]["manifest"]
    assert sha256(manifest) == receipt["source"]["manifest_sha256"]
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        assert sha256(ROOT / relative) == expected, relative
    for relative, expected in receipt["artifacts"].items():
        assert sha256(ROOT / relative) == expected, relative

    depth_two = load("depth-two-candidates.json")
    depth_three = load("depth-three-candidates.json")
    assert depth_counts(depth_two) == {0: 1, 1: 6, 2: 17}
    assert depth_counts(depth_three) == {0: 1, 1: 6, 2: 17, 3: 32}
    for payload in (depth_two, depth_three):
        assert all(
            candidate["properties"]["explicit_path_verified"]
            for candidate in payload["candidates"]
        )
        assert all(
            candidate["properties"]["automorphism_order_geometric"] == 2
            for candidate in payload["candidates"]
        )

    screening = load("screening-summary.json")
    assert screening["candidate_count"] == len(screening["results"]) == 17
    assert len({row["candidate_id"] for row in screening["results"]}) == 17
    assert all(row["linear_relation_verified"] for row in screening["results"])
    assert sum(
        row["paired_speedup_significant_at_95_percent"]
        for row in screening["results"]
    ) == 1

    holdout_candidates = load("holdout-candidates.json")["candidates"]
    products = sorted(
        math.prod(step["degree"] for step in candidate["path"])
        for candidate in holdout_candidates
        if candidate["candidate_id"] != "p256-root"
    )
    assert products == [33, 39, 65]
    holdout = load("holdout-benchmark.json")
    assert len(holdout["results"]) == 4
    assert all(row["trials"] == 20 for row in holdout["results"])
    assert all(row["linear_relation_verified"] for row in holdout["results"])
    neighbors = [
        row for row in holdout["results"] if row["candidate_id"] != "p256-root"
    ]
    assert all(
        low <= 1.0 <= high
        for low, high in (
            row["paired_relative_iteration_speed_95_percent_ci"]
            for row in neighbors
        )
    )
    assert not any(
        row["paired_speedup_significant_at_95_percent"] for row in neighbors
    )
    print(
        json.dumps(
            {
                "status": "verified",
                "depth_three_curves": len(depth_three["candidates"]),
                "depth_two_screened": len(screening["results"]),
                "holdout_speedups": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
