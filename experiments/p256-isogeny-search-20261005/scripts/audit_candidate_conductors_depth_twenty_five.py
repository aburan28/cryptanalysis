#!/usr/bin/env python3
"""Replay the conductor audit with the depth-twenty-five publication label."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from audit_candidate_conductors import build_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    report = build_report(args.candidates)
    report["publication_status"] = "prospective_depth_twenty_five_exact_audit"
    if args.verify:
        frozen = json.loads(args.output.read_text(encoding="utf-8"))
        if frozen != report:
            raise AssertionError(
                "depth-twenty-five conductor audit does not reproduce"
            )
        status = "verified"
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(args.output)
        status = "written"

    print(
        json.dumps(
            {
                "status": status,
                **report["coverage"],
                "endomorphism_conductor": 1,
                "publication_status": report["publication_status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
