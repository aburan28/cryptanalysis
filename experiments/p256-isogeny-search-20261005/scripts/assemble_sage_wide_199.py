#!/usr/bin/env python3
"""Assemble the successful one-hop degree panels and their resource boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

EXPERIMENT = Path(__file__).resolve().parents[1]
RESULTS = EXPERIMENT / "results"
OUTPUT = RESULTS / "sage-wide-depth-one-199-20261006"

PRIOR_WIDE = RESULTS / "sage-wide-depth-one-20261006" / "candidates.json"
DEPTH_THREE = RESULTS / "sage-depth-three-20261006" / "depth-three-candidates.json"
PANEL_4G = OUTPUT / "degrees" / "panel-status.json"
PANEL_8G = OUTPUT / "degrees-8g" / "panel-status.json"
NEW_DEGREES = {
    59: OUTPUT / "degrees" / "degree-59.json",
    97: OUTPUT / "degrees" / "degree-97.json",
    101: OUTPUT / "degrees-8g" / "degree-101.json",
    103: OUTPUT / "degrees" / "degree-103.json",
}

ATTEMPTED_DEGREES = [
    3,
    5,
    11,
    13,
    17,
    23,
    29,
    37,
    41,
    43,
    47,
    59,
    97,
    101,
    103,
    137,
    149,
    151,
    157,
    163,
    179,
    181,
    191,
    197,
    199,
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def relative(path: Path) -> str:
    return str(path.relative_to(EXPERIMENT))


def source(path: Path) -> dict[str, Any]:
    return {"path": relative(path), "sha256": sha256(path)}


def write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def compact_records(panel: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for row in panel["records"]:
        compact = {
            "ell": row["ell"],
            "status": row["status"],
            "elapsed_seconds": row["elapsed_seconds"],
        }
        if row["status"] == "completed":
            compact.update(
                {"nodes_found": row["nodes_found"], "artifact": row["artifact"]}
            )
        else:
            compact.update(
                {
                    "exception_type": row["exception_type"],
                    "pari_stack_overflow_in_traceback": (
                        "PARI stack overflows" in row["traceback"]
                    ),
                }
            )
        records.append(compact)
    return records


def main() -> None:
    source_paths = [PRIOR_WIDE, *NEW_DEGREES.values()]
    candidates: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for path in source_paths:
        for candidate in load(path)["candidates"]:
            candidate_id = candidate["candidate_id"]
            prior = by_id.get(candidate_id)
            if prior is None:
                by_id[candidate_id] = candidate
                candidates.append(candidate)
            else:
                assert prior["curve"] == candidate["curve"], candidate_id
                assert prior["path"] == candidate["path"], candidate_id

    completed_degrees = sorted(
        {
            edge["degree"]
            for candidate in candidates
            for edge in candidate["path"]
        }
    )
    extended = {
        "schema_version": 1,
        "description": (
            "P-256 one-hop horizontal isogeny candidates successfully retained "
            "while attempting all ramified or split prime degrees through 199"
        ),
        "search": {
            "algorithm": "union of independent breadth-first depth-one Sage panels",
            "attempted_ells": ATTEMPTED_DEGREES,
            "completed_ells": completed_degrees,
            "depth": 1,
            "nodes_found": len(candidates),
            "sources": [source(path) for path in source_paths],
        },
        "candidates": candidates,
    }
    extended_path = OUTPUT / "extended-candidates.json"
    write(extended_path, extended)

    depth_three = load(DEPTH_THREE)
    union_ids = []
    seen = set()
    for candidate in [*depth_three["candidates"], *candidates]:
        candidate_id = candidate["candidate_id"]
        if candidate_id not in seen:
            union_ids.append(candidate_id)
            seen.add(candidate_id)
    new_ids = [
        candidate["candidate_id"]
        for ell in NEW_DEGREES
        for candidate in load(NEW_DEGREES[ell])["candidates"]
        if candidate["candidate_id"] != "p256-root"
    ]
    union = {
        "schema_version": 1,
        "description": "Unique retained curves across depth three and the extended one-hop scan",
        "inputs": [source(DEPTH_THREE), source(extended_path)],
        "unique_curves_including_p256": len(union_ids),
        "unique_non_root_curves": len(union_ids) - 1,
        "new_one_hop_non_root_curves": len(new_ids),
        "new_candidate_ids": new_ids,
        "candidate_ids": union_ids,
    }
    write(OUTPUT / "retained-union.json", union)

    panel_4g = load(PANEL_4G)
    panel_8g = load(PANEL_8G)
    boundary = {
        "schema_version": 1,
        "description": "Exact success and resource boundary for the attempted one-hop extension",
        "scope": {
            "classification": "every rational prime degree <= 199 with Kronecker symbol 0 or 1",
            "attempted_ells": ATTEMPTED_DEGREES,
            "successful_ells": completed_degrees,
            "unresolved_ells": [137, 149, 151, 157, 163, 179, 181, 191, 197, 199],
        },
        "unretained_preliminary_attempts": [
            {
                "design": "monolithic all-degree traversal",
                "pari_stack_gib": 1,
                "status": "failed",
                "exception_type": "NotImplementedError after PARI stack overflow",
                "raw_artifact_retained": False,
            },
            {
                "design": "monolithic all-degree traversal",
                "pari_stack_gib": 4,
                "status": "failed",
                "exception_type": "NotImplementedError after PARI stack overflow",
                "raw_artifact_retained": False,
            },
        ],
        "independent_panels": [
            {
                "pari_stack_gib": panel_4g["pari_stack_gib"],
                "requested_ells": panel_4g["requested_ells"],
                "records": compact_records(panel_4g),
                "raw_status": source(PANEL_4G),
            },
            {
                "pari_stack_gib": panel_8g["pari_stack_gib"],
                "requested_ells": panel_8g["requested_ells"],
                "records": compact_records(panel_8g),
                "raw_status": source(PANEL_8G),
                "termination": {
                    "completed": [101],
                    "failed_at_full_8_gib": [137, 149, 151],
                    "operator_interrupted_during": 157,
                    "not_started_at_8_gib": [163, 179, 181, 191, 197, 199],
                    "reason": (
                        "stopped after three consecutive higher-degree attempts "
                        "exhausted the full 8 GiB stack; all remaining degrees had "
                        "already failed independently at 4 GiB"
                    ),
                },
            },
        ],
        "claim_boundary": (
            "Explicit one-hop paths are retained through degree 103 where Sage "
            "completed. Degrees 137 and above remain unresolved; this is not a "
            "complete one-hop enumeration through 199."
        ),
    }
    write(OUTPUT / "resource-boundary.json", boundary)

    print(
        json.dumps(
            {
                "extended_one_hop_curves": len(candidates),
                "new_neighbors": len(new_ids),
                "retained_union_curves": len(union_ids),
                "completed_degrees": completed_degrees,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
