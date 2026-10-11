#!/usr/bin/env python3
"""Replay the coefficient audit with depth-thirty-seven metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from audit_candidate_coefficients import build_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    report = build_report(args.candidates)
    report["publication_status"] = (
        "prospective_depth_thirty_seven_deterministic_audit"
    )
    eligible = report["results"]["eligible_candidates"]
    report["finding"] = (
        "No depth-36/37 candidate passes the low-operation coefficient gate."
        if not eligible
        else (
            f"{eligible} depth-36/37 candidate(s) pass the low-operation "
            "coefficient gate."
        )
    )
    if args.verify:
        frozen = json.loads(args.output.read_text(encoding="utf-8"))
        if frozen != report:
            raise AssertionError(
                "depth-thirty-seven coefficient audit does not reproduce"
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
                "new_candidates": report["coverage"]["new_candidates"],
                "minimum_lower_bound": report["results"]["minimum_bit_length_row"][
                    "signed_addition_chain_operation_lower_bound"
                ],
                "minimum_binary_upper_bound": report["results"][
                    "minimum_binary_upper_bound_row"
                ]["binary_double_and_add_operation_upper_bound"],
                "eligible_candidates": eligible,
                "publication_status": report["publication_status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
