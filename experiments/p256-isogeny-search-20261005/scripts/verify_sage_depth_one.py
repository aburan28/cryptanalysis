#!/usr/bin/env python3
"""Verify hashes and claim-limiting invariants for the frozen Sage run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "receipt-sage-depth-one-20261006.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    manifest = ROOT / receipt["source"]["manifest"]
    assert sha256(manifest) == receipt["source"]["manifest_sha256"]
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        assert sha256(ROOT / relative) == expected, relative
    for relative, expected in receipt["artifacts"].items():
        assert sha256(ROOT / relative) == expected, relative

    result_dir = ROOT / "results" / "sage-depth-one-20261006"
    candidates = json.loads((result_dir / "candidates.json").read_text())
    benchmark = json.loads((result_dir / "benchmark-interleaved.json").read_text())
    assert candidates["search"]["nodes_found"] == len(candidates["candidates"]) == 7
    assert sorted(
        step["degree"]
        for candidate in candidates["candidates"]
        for step in candidate["path"]
    ) == [3, 5, 11, 11, 13, 13]
    assert all(
        candidate["properties"]["explicit_path_verified"]
        for candidate in candidates["candidates"]
    )
    assert all(
        candidate["properties"]["automorphism_order_geometric"] == 2
        for candidate in candidates["candidates"]
    )
    assert len(benchmark["benchmark_design"]["execution_order_by_trial"]) == 7
    assert all(row["linear_relation_verified"] for row in benchmark["results"])
    neighbors = [
        row for row in benchmark["results"] if row["candidate_id"] != "p256-root"
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
                "candidates": len(candidates["candidates"]),
                "explicit_paths": len(neighbors),
                "significant_speedups": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
