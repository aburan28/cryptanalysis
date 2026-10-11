#!/usr/bin/env python3
"""Assemble the resumed depth-thirty-nine frontier with the retained union."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

EXPERIMENT = Path(__file__).resolve().parents[1]
RESULTS = EXPERIMENT / "results"
OUTPUT = RESULTS / "sage-low-degree-depth-thirty-nine-20261008"
DELTA = OUTPUT / "candidates-delta.json"
PRIOR_UNION = (
    RESULTS / "sage-low-degree-depth-thirty-seven-20261008" / "retained-union.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def source(path: Path) -> dict[str, str]:
    return {"path": str(path.relative_to(EXPERIMENT)), "sha256": sha256(path)}


def main() -> None:
    delta = load(DELTA)
    prior = load(PRIOR_UNION)
    candidates = delta["candidates"]
    assert candidates[0]["candidate_id"] == "p256-root"
    new_candidates = candidates[1:]
    new_ids = [row["candidate_id"] for row in new_candidates]
    prior_ids = prior["candidate_ids"]
    assert len(prior_ids) == len(set(prior_ids)) == 10706
    assert len(new_ids) == len(set(new_ids))
    assert 0 < len(new_ids) <= 2000
    assert not set(new_ids).intersection(prior_ids)
    depth_counts = Counter(len(row["path"]) for row in new_candidates)
    assert set(depth_counts) == {38, 39}
    assert all(depth_counts[depth] > 0 for depth in (38, 39))

    combined_ids = [*prior_ids, *new_ids]
    assert len(combined_ids) == len(set(combined_ids))
    payload = {
        "schema_version": 1,
        "description": (
            "Unique retained curves across the complete one-hop-through-199 registry "
            "and the low-degree traversal through depth thirty-nine"
        ),
        "inputs": [source(PRIOR_UNION), source(DELTA)],
        "prior_unique_curves_including_p256": len(prior_ids),
        "new_non_root_curves": len(new_ids),
        "new_depth_counts": {
            str(depth): depth_counts[depth] for depth in sorted(depth_counts)
        },
        "unique_curves_including_p256": len(combined_ids),
        "unique_non_root_curves": len(combined_ids) - 1,
        "new_candidate_ids": new_ids,
        "candidate_ids": combined_ids,
    }
    destination = OUTPUT / "retained-union.json"
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "new_non_root_curves": len(new_ids),
                "new_depth_counts": payload["new_depth_counts"],
                "retained_union_curves": len(combined_ids),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
