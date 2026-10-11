#!/usr/bin/env python3
"""Assemble the depth-five low-degree frontier and its new native panel."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

EXPERIMENT = Path(__file__).resolve().parents[1]
RESULTS = EXPERIMENT / "results"
OUTPUT = RESULTS / "sage-low-degree-depth-five-20261006"

DEPTH_FIVE = OUTPUT / "candidates.json"
PRIOR_UNION = (
    RESULTS / "sage-wide-depth-one-199-20261006" / "retained-union.json"
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
    return {
        "path": str(path.relative_to(EXPERIMENT)),
        "sha256": sha256(path),
    }


def write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main() -> None:
    depth_five = load(DEPTH_FIVE)
    prior_union = load(PRIOR_UNION)
    candidates = depth_five["candidates"]
    assert candidates[0]["candidate_id"] == "p256-root"
    assert depth_five["search"]["ells"] == [3, 5, 11, 13]
    assert depth_five["search"]["depth"] == 5
    assert len(candidates) == len({row["candidate_id"] for row in candidates})

    prior_ids = prior_union["candidate_ids"]
    prior_set = set(prior_ids)
    new_candidates = [
        row for row in candidates if row["candidate_id"] not in prior_set
    ]
    new_ids = [row["candidate_id"] for row in new_candidates]
    assert all(len(row["path"]) in {4, 5} for row in new_candidates)

    native_panel = {
        "schema_version": 1,
        "description": (
            "P-256 plus every previously unscreened curve first reached within "
            "five hops using degrees 3, 5, 11, and 13"
        ),
        "search": {
            "algorithm": "selection from the complete depth-five registry",
            "ells": [3, 5, 11, 13],
            "maximum_depth": 5,
            "nodes_found": len(new_candidates) + 1,
            "new_non_root_curves": len(new_candidates),
            "depth_counts": {
                str(depth): count
                for depth, count in sorted(
                    Counter(len(row["path"]) for row in new_candidates).items()
                )
            },
            "source": source(DEPTH_FIVE),
            "prior_union": source(PRIOR_UNION),
        },
        "candidates": [candidates[0], *new_candidates],
    }
    write(OUTPUT / "new-candidates.json", native_panel)

    combined_ids = [*prior_ids, *new_ids]
    assert len(combined_ids) == len(set(combined_ids))
    combined = {
        "schema_version": 1,
        "description": (
            "Unique retained curves across the complete one-hop-through-199 "
            "registry and the low-degree depth-five registry"
        ),
        "inputs": [source(PRIOR_UNION), source(DEPTH_FIVE)],
        "prior_unique_curves_including_p256": len(prior_ids),
        "low_degree_depth_five_curves_including_p256": len(candidates),
        "overlap_curves_including_p256": len(candidates) - len(new_candidates),
        "new_non_root_curves": len(new_candidates),
        "new_depth_counts": native_panel["search"]["depth_counts"],
        "unique_curves_including_p256": len(combined_ids),
        "unique_non_root_curves": len(combined_ids) - 1,
        "new_candidate_ids": new_ids,
        "candidate_ids": combined_ids,
    }
    write(OUTPUT / "retained-union.json", combined)

    print(
        json.dumps(
            {
                "depth_five_curves": len(candidates),
                "new_depth_four_curves": native_panel["search"]["depth_counts"].get(
                    "4", 0
                ),
                "new_depth_five_curves": native_panel["search"]["depth_counts"].get(
                    "5", 0
                ),
                "new_non_root_curves": len(new_candidates),
                "retained_union_curves": len(combined_ids),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
