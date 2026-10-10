#!/usr/bin/env python3
"""Replay coefficient normalization on every candidate in a frozen registry."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from analyze_model_eligibility import normalize_short_a

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_report(candidate_path: Path) -> dict[str, Any]:
    candidate_path = candidate_path.resolve()
    payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    rows = []
    target_counts: Counter[str] = Counter()
    for candidate in payload["candidates"]:
        curve = candidate["curve"]
        result = normalize_short_a(
            p=int(curve["p"]),
            a=int(curve["a"]),
            b=int(curve["b"]),
            x=int(curve["generator"]["x"]),
            y=int(curve["generator"]["y"]),
        )
        target_counts[result["target_a"]] += 1
        rows.append(
            {
                "candidate_id": candidate["candidate_id"],
                "source_a_legendre_symbol": result["source_a_legendre_symbol"],
                "target_a": result["target_a"],
                "scaling_u": result["scaling_u"],
                "target_b": result["target_b"],
                "transported_generator": result["transported_generator"],
                "u_fourth_equals_a_over_target_a": result[
                    "u_fourth_equals_a_over_target_a"
                ],
                "transported_generator_on_target": result[
                    "transported_generator_on_target"
                ],
            }
        )
    return {
        "schema_version": 1,
        "input": {
            "path": str(candidate_path.relative_to(ROOT)),
            "sha256": sha256(candidate_path),
        },
        "curves_including_p256": len(rows),
        "target_a_counts": dict(sorted(target_counts.items())),
        "all_fourth_root_certificates_verified": all(
            row["u_fourth_equals_a_over_target_a"] for row in rows
        ),
        "all_transported_generators_on_target": all(
            row["transported_generator_on_target"] for row in rows
        ),
        "interpretation": (
            "Every retained model normalizes to a=1 or a=3 over F_p; P-256 is in "
            "the a=1 class, so this audit identifies no neighbor-only small-a shortcut."
        ),
        "candidates": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    report = build_report(args.candidates)
    if args.verify:
        frozen = json.loads(args.output.read_text(encoding="utf-8"))
        if frozen != report:
            raise AssertionError("candidate model audit does not reproduce")
        status = "verified"
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(args.output)
        status = "written"
    print(json.dumps({
        "status": status,
        "curves_including_p256": report["curves_including_p256"],
        "target_a_counts": report["target_a_counts"],
        "all_certificates_verified": report["all_fourth_root_certificates_verified"] and report["all_transported_generators_on_target"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
