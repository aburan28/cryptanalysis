#!/usr/bin/env python3
"""Verify the widened one-hop registry and timing screen."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "receipt-sage-wide-depth-one-20261006.json"
RESULTS = ROOT / "results" / "sage-wide-depth-one-20261006"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    receipt = load(RECEIPT)
    manifest = ROOT / receipt["source"]["manifest"]
    assert sha256(manifest) == receipt["source"]["manifest_sha256"]
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        assert sha256(ROOT / relative) == expected, relative
    for relative, expected in receipt["artifacts"].items():
        assert sha256(ROOT / relative) == expected, relative

    candidates = load(RESULTS / "candidates.json")["candidates"]
    assert len(candidates) == 21
    assert all(
        candidate["properties"]["explicit_path_verified"] for candidate in candidates
    )
    assert all(
        candidate["properties"]["automorphism_order_geometric"] == 2
        for candidate in candidates
    )
    degrees = sorted(
        candidate["path"][0]["degree"]
        for candidate in candidates
        if candidate["candidate_id"] != "p256-root"
    )
    assert degrees == [3, 5, 11, 11, 13, 13, 17, 17, 23, 23, 29, 29, 37, 37, 41, 41, 43, 43, 47, 47]

    depth_three = load(
        ROOT / "results" / "sage-depth-three-20261006" / "depth-three-candidates.json"
    )["candidates"]
    wide_ids = {candidate["candidate_id"] for candidate in candidates}
    depth_three_ids = {candidate["candidate_id"] for candidate in depth_three}
    assert len(wide_ids & depth_three_ids) == 7
    assert len(wide_ids - depth_three_ids) == 14
    assert len(wide_ids | depth_three_ids) == 70

    screening = load(RESULTS / "screening-summary.json")
    assert screening["candidate_count"] == len(screening["results"]) == 14
    assert all(row["linear_relation_verified"] for row in screening["results"])
    assert not any(
        row["paired_speedup_significant_at_95_percent"]
        for row in screening["results"]
    )
    assert all(
        low <= 1.0 <= high
        for low, high in (
            row["paired_relative_iteration_speed_95_percent_ci"]
            for row in screening["results"]
        )
    )
    print(
        json.dumps(
            {
                "status": "verified",
                "wide_neighbors": 20,
                "new_neighbors_screened": 14,
                "combined_unique_curves": 70,
                "significant_speedups": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
