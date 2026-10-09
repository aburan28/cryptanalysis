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
PRIOR_EXTENSION_DEGREES = {
    59: OUTPUT / "degrees" / "degree-59.json",
    97: OUTPUT / "degrees" / "degree-97.json",
    101: OUTPUT / "degrees-8g" / "degree-101.json",
    103: OUTPUT / "degrees" / "degree-103.json",
}
MODULAR_VALIDATION = OUTPUT / "modular-degrees" / "degree-103.json"
MODULAR_PANEL = OUTPUT / "modular-degrees" / "panel-status.json"
MODULAR_DEGREES = {
    ell: OUTPUT / "modular-degrees" / f"degree-{ell}.json"
    for ell in [137, 149, 151, 157, 163, 179, 181, 191, 197, 199]
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
    source_paths = [
        PRIOR_WIDE,
        *PRIOR_EXTENSION_DEGREES.values(),
        *MODULAR_DEGREES.values(),
    ]
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
    prior_extension_ids = [
        candidate["candidate_id"]
        for ell in PRIOR_EXTENSION_DEGREES
        for candidate in load(PRIOR_EXTENSION_DEGREES[ell])["candidates"]
        if candidate["candidate_id"] != "p256-root"
    ]
    modular_ids = [
        candidate["candidate_id"]
        for ell in MODULAR_DEGREES
        for candidate in load(MODULAR_DEGREES[ell])["candidates"]
        if candidate["candidate_id"] != "p256-root"
    ]
    new_ids = [*prior_extension_ids, *modular_ids]
    union = {
        "schema_version": 1,
        "description": "Unique retained curves across depth three and the extended one-hop scan",
        "inputs": [source(DEPTH_THREE), source(extended_path)],
        "unique_curves_including_p256": len(union_ids),
        "unique_non_root_curves": len(union_ids) - 1,
        "new_since_degree_47_non_root_curves": len(new_ids),
        "new_modular_recovery_non_root_curves": len(modular_ids),
        "new_candidate_ids": new_ids,
        "new_modular_candidate_ids": modular_ids,
        "candidate_ids": union_ids,
    }
    write(OUTPUT / "retained-union.json", union)

    high_candidates = [candidates[0]] + [by_id[candidate_id] for candidate_id in modular_ids]
    write(
        OUTPUT / "new-high-candidates.json",
        {
            "schema_version": 1,
            "description": "P-256 plus the 20 newly recovered degree-137 through degree-199 neighbors",
            "search": {
                "algorithm": "selection from the complete one-hop registry",
                "ells": list(MODULAR_DEGREES),
                "nodes_found": len(high_candidates),
                "source": source(extended_path),
            },
            "candidates": high_candidates,
        },
    )

    panel_4g = load(PANEL_4G)
    panel_8g = load(PANEL_8G)
    modular_panel = load(MODULAR_PANEL)
    legacy_103 = {
        candidate["candidate_id"]: candidate
        for candidate in load(PRIOR_EXTENSION_DEGREES[103])["candidates"]
    }
    modular_103 = {
        candidate["candidate_id"]: candidate
        for candidate in load(MODULAR_VALIDATION)["candidates"]
    }
    validation_matches = (
        legacy_103.keys() == modular_103.keys()
        and all(
            legacy_103[candidate_id]["curve"] == modular_103[candidate_id]["curve"]
            and legacy_103[candidate_id]["path"] == modular_103[candidate_id]["path"]
            for candidate_id in legacy_103
        )
    )
    assert validation_matches
    boundary = {
        "schema_version": 1,
        "description": "Exact success and resource boundary for the attempted one-hop extension",
        "scope": {
            "classification": "every rational prime degree <= 199 with Kronecker symbol 0 or 1",
            "attempted_ells": ATTEMPTED_DEGREES,
            "successful_ells": completed_degrees,
            "unresolved_ells": [],
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
        "superseded_division_polynomial_panels": [
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
        "successful_modular_recovery": {
            "method": (
                "instantiated classical modular polynomial, first-partial "
                "normalized codomain formula, and BMSS kernel recovery"
            ),
            "pari_stack_gib": modular_panel["pari_stack_gib"],
            "requested_ells": modular_panel["requested_ells"],
            "records": compact_records(modular_panel),
            "raw_status": source(MODULAR_PANEL),
            "degree_103_validation": {
                "legacy_artifact": source(PRIOR_EXTENSION_DEGREES[103]),
                "modular_artifact": source(MODULAR_VALIDATION),
                "candidate_ids_curves_and_paths_match_exactly": validation_matches,
            },
        },
        "claim_boundary": (
            "Every rational ramified or split prime degree through 199 is "
            "explicitly enumerated. This does not cover larger prime degrees "
            "or the entire P-256 isogeny class."
        ),
    }
    write(OUTPUT / "resource-boundary.json", boundary)

    print(
        json.dumps(
            {
                "extended_one_hop_curves": len(candidates),
                "new_since_degree_47_neighbors": len(new_ids),
                "new_modular_neighbors": len(modular_ids),
                "retained_union_curves": len(union_ids),
                "completed_degrees": completed_degrees,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
