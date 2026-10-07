#!/usr/bin/env python3
"""Run a fresh native holdout for every unadjusted screening hit."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

EXPERIMENT = Path(__file__).resolve().parents[1]
REPOSITORY = EXPERIMENT.parents[1]


def repo_path(path: Path) -> Path:
    return path if path.is_absolute() else REPOSITORY / path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--screening", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=2.0)
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--warmup-seconds", type=float, default=0.2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    binary = repo_path(args.binary)
    candidates = repo_path(args.candidates)
    screening = repo_path(args.screening)
    output = repo_path(args.output)
    payload = json.loads(screening.read_text(encoding="utf-8"))
    hit_ids = [row["candidate_id"] for row in payload["unadjusted_screening_hits"]]

    command = [
        str(binary),
        "--candidates",
        str(candidates.relative_to(REPOSITORY)),
    ]
    for candidate_id in hit_ids:
        command.extend(["--candidate-id", candidate_id])
    command.extend(
        [
            "--seconds",
            str(args.seconds),
            "--trials",
            str(args.trials),
            "--warmup-seconds",
            str(args.warmup_seconds),
            "--output",
            str(output.relative_to(REPOSITORY)),
        ]
    )
    print(json.dumps({"holdout_candidates": hit_ids, "command": command}), flush=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(command, cwd=REPOSITORY, check=True)


if __name__ == "__main__":
    main()
