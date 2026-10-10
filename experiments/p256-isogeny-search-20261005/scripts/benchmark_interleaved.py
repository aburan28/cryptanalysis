#!/usr/bin/env python3
"""Run the order-balanced candidate benchmark and write a JSON report."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from p256_isogeny_search.interleaved import (  # noqa: E402
    benchmark_candidates_interleaved,
)
from p256_isogeny_search.registry import load_candidates  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=1.0)
    parser.add_argument("--trials", type=int, default=7)
    parser.add_argument("--table-size", type=int, default=16)
    parser.add_argument("--batch-width", type=int, default=64)
    parser.add_argument("--warmup-seconds", type=float, default=0.1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = benchmark_candidates_interleaved(
        load_candidates(args.candidates),
        seconds=args.seconds,
        trials=args.trials,
        table_size=args.table_size,
        batch_width=args.batch_width,
        warmup_seconds=args.warmup_seconds,
    )
    payload = {
        "run": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "python": sys.version,
            "platform": platform.platform(),
        },
        **report,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(args.output)


if __name__ == "__main__":
    main()
