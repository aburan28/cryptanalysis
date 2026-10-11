#!/usr/bin/env python3
"""Replay the fixed N13 same-base SAT stream under one declared PDP budget."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOURCE = ROOT / "experiments/shifted-base-geometry/solver_cost.py"
sys.path.insert(0, str(SOURCE.parent))
import solver_cost  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget-ms", type=int, choices=(50, 1000), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output already exists")
    solver_cost.QUERY_SECONDS = args.budget_ms / 1000
    row = solver_cost.collect(base_seed=87006, stream_seed=91001,
                              shifted=False, cap=32)
    assert row["base_points"] == 6 and row["columns"] == 2
    assert row["native_query_budget_seconds"] == args.budget_ms / 1000
    report = {
        "kind": "bounded_n13_same_base_chained_s3_sat_stage",
        "catalog_scope": "N13 SAT first-witness PDP stage only; no complete IC or online DLP timing",
        "compatible_proposal_ids": ["Q1", "Q2", "Q3", "Q4"],
        "matched_budget_proposal_ids": ["Q1", "Q3"] if args.budget_ms == 50 else ["Q2", "Q4"],
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": platform.python_version(),
        "budget_ms": args.budget_ms,
        "row": row,
        "full_dlp_speedup": None,
    }
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
