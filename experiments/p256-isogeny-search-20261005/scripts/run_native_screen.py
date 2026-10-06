#!/usr/bin/env python3
"""Run root-controlled native screening blocks over retained candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

EXPERIMENT = Path(__file__).resolve().parents[1]
REPOSITORY = EXPERIMENT.parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else REPOSITORY / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, action="append", required=True)
    parser.add_argument("--exclude-results", type=Path)
    parser.add_argument("--block-size", type=int, default=6)
    parser.add_argument("--seconds", type=float, default=0.5)
    parser.add_argument("--rotations", type=int, default=1)
    parser.add_argument("--warmup-seconds", type=float, default=0.05)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.block_size < 1 or args.seconds <= 0 or args.rotations < 1:
        raise SystemExit("block-size >= 1, seconds > 0, and rotations >= 1 required")
    binary = resolve_repo_path(args.binary)
    candidate_paths = [resolve_repo_path(path) for path in args.candidates]
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = EXPERIMENT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    ordered_ids: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    for path in candidate_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for candidate in payload["candidates"]:
            candidate_id = candidate["candidate_id"]
            if candidate_id not in by_id:
                ordered_ids.append(candidate_id)
                by_id[candidate_id] = candidate

    excluded: set[str] = set()
    if args.exclude_results is not None:
        exclude_path = resolve_repo_path(args.exclude_results)
        payload = json.loads(exclude_path.read_text(encoding="utf-8"))
        excluded = {
            row["candidate_id"]
            for row in payload["results"]
            if row["candidate_id"] != "p256-root"
        }
    selected = [
        candidate_id
        for candidate_id in ordered_ids
        if candidate_id != "p256-root" and candidate_id not in excluded
    ]
    blocks = [
        selected[index : index + args.block_size]
        for index in range(0, len(selected), args.block_size)
    ]

    block_records = []
    candidate_results = []
    root_controls = []
    for block_index, candidate_ids in enumerate(blocks, start=1):
        output = output_dir / f"block-{block_index:02d}.json"
        trials = (len(candidate_ids) + 1) * args.rotations
        command = [str(binary)]
        for path in candidate_paths:
            command.extend(["--candidates", str(path.relative_to(REPOSITORY))])
        for candidate_id in candidate_ids:
            command.extend(["--candidate-id", candidate_id])
        command.extend(
            [
                "--seconds",
                str(args.seconds),
                "--trials",
                str(trials),
                "--warmup-seconds",
                str(args.warmup_seconds),
                "--output",
                str(output.relative_to(REPOSITORY)),
            ]
        )
        print(
            f"block {block_index}/{len(blocks)}: "
            f"{len(candidate_ids)} candidates, {trials} trials each",
            flush=True,
        )
        subprocess.run(command, cwd=REPOSITORY, check=True)
        payload = json.loads(output.read_text(encoding="utf-8"))
        assert payload["results"][0]["candidate_id"] == "p256-root"
        assert [row["candidate_id"] for row in payload["results"][1:]] == candidate_ids
        root_controls.append({"block": block_index, **payload["results"][0]})
        candidate_results.extend(
            {"block": block_index, **row} for row in payload["results"][1:]
        )
        block_records.append(
            {
                "block": block_index,
                "candidate_ids": candidate_ids,
                "trials_per_candidate": trials,
                "artifact": str(output.relative_to(EXPERIMENT)),
                "artifact_sha256": sha256(output),
            }
        )

    significant = [
        row for row in candidate_results if row["paired_speedup_significant_at_95_percent"]
    ]
    aggregate = {
        "schema_version": 1,
        "benchmark": "blockwise matched-native screen of previously untested explicit paths",
        "binary": {
            "path": str(binary.relative_to(REPOSITORY)),
            "sha256": sha256(binary),
        },
        "inputs": [
            {"path": str(path.relative_to(EXPERIMENT)), "sha256": sha256(path)}
            for path in candidate_paths
        ],
        "design": {
            "candidate_universe": len(by_id),
            "excluded_prior_native_panel": len(excluded),
            "screened_candidates": len(selected),
            "block_size": args.block_size,
            "blocks": len(blocks),
            "seconds_per_trial": args.seconds,
            "complete_position_rotations_per_block": args.rotations,
            "warmup_seconds_per_candidate": args.warmup_seconds,
            "screening_rule": "unadjusted paired 95% interval with lower bound above 1.0; any hit requires fresh holdout",
            "host_cpu_isolation": "unverified; wall-time results are exploratory",
        },
        "blocks": block_records,
        "root_controls": root_controls,
        "results": candidate_results,
        "unadjusted_screening_hits": significant,
    }
    aggregate_path = output_dir / "screening-summary.json"
    aggregate_path.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n")
    print(
        f"screened {len(selected)} candidates; "
        f"unadjusted hits: {len(significant)}; {aggregate_path}",
        flush=True,
    )


if __name__ == "__main__":
    main()
