#!/usr/bin/env sage -python
"""Explore independent one-hop degrees while preserving partial successes."""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

try:
    from sage.all import pari
    from sage.env import SAGE_VERSION
except ImportError as exc:  # pragma: no cover - executed only outside Sage
    raise SystemExit("This program must run under `sage -python`.") from exc

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import explore_sage  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ells", required=True)
    parser.add_argument("--pari-stack-gib", type=int, default=4)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.pari_stack_gib < 1:
        raise SystemExit("--pari-stack-gib must be positive")
    ells = [int(value) for value in args.ells.split(",") if value]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pari.allocatemem(args.pari_stack_gib * 1024**3, silent=True)

    started = time.time()
    records = []
    for ell in ells:
        print(f"degree {ell}: starting", flush=True)
        degree_started = time.time()
        output = args.output_dir / f"degree-{ell}.json"
        try:
            payload = explore_sage.explore([ell], 1, 3)
            output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            record = {
                "ell": ell,
                "status": "completed",
                "nodes_found": payload["search"]["nodes_found"],
                "elapsed_seconds": time.time() - degree_started,
                "artifact": output.name,
            }
            print(
                f"degree {ell}: completed with {record['nodes_found'] - 1} neighbors",
                flush=True,
            )
        except Exception as exc:  # retain every other degree after one failure
            record = {
                "ell": ell,
                "status": "failed",
                "elapsed_seconds": time.time() - degree_started,
                "exception_type": type(exc).__name__,
                "exception": str(exc),
                "traceback": traceback.format_exc(),
            }
            print(f"degree {ell}: failed: {type(exc).__name__}: {exc}", flush=True)
        records.append(record)
        panel = {
            "schema_version": 1,
            "sage_version": str(SAGE_VERSION),
            "pari_stack_gib": args.pari_stack_gib,
            "requested_ells": ells,
            "records": records,
            "elapsed_wall_seconds": time.time() - started,
        }
        (args.output_dir / "panel-status.json").write_text(
            json.dumps(panel, indent=2, sort_keys=True) + "\n"
        )


if __name__ == "__main__":
    main()
