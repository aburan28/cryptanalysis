#!/usr/bin/env python3
"""Audit normalized 3b coefficient costs for one frozen candidate registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from audit_retained_coefficients import coefficient_row, sha256

ROOT = Path(__file__).resolve().parents[1]


def build_report(candidate_path: Path) -> dict:
    candidate_path = candidate_path.resolve()
    payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    origin = str(candidate_path.relative_to(ROOT))
    rows = [
        coefficient_row(row["candidate_id"], row, origin)
        for row in payload["candidates"]
    ]
    new_rows = [row for row in rows if row["candidate_id"] != "p256-root"]
    ranking = sorted(
        new_rows,
        key=lambda row: (
            row["binary_double_and_add_operation_upper_bound"],
            row["normalized_3b_absolute_bit_length"],
            row["normalized_3b_absolute_popcount"],
            row["candidate_id"],
        ),
    )
    by_bit_length = sorted(
        new_rows,
        key=lambda row: (
            row["normalized_3b_absolute_bit_length"],
            row["normalized_3b_absolute_popcount"],
            row["candidate_id"],
        ),
    )
    threshold = 32
    eligible = [
        row
        for row in new_rows
        if row["signed_addition_chain_operation_lower_bound"] <= threshold
    ]
    return {
        "schema_version": 1,
        "publication_status": "prospective_depth_nineteen_deterministic_audit",
        "input": {"path": origin, "sha256": sha256(candidate_path)},
        "cost_model": {
            "normalized_models": "a in {1,3}",
            "rho_complete_addition_coefficient": "3b",
            "signed_addition_chain_lower_bound": "bit_length(abs(3b))-1",
            "binary_double_and_add_upper_bound": "bit_length(abs(3b))+popcount(abs(3b))-2",
            "eligibility_gate_maximum_lower_bound_operations": threshold,
        },
        "coverage": {
            "curves_including_p256": len(rows),
            "new_candidates": len(new_rows),
        },
        "results": {
            "minimum_bit_length_row": by_bit_length[0],
            "minimum_binary_upper_bound_row": ranking[0],
            "minimum_popcount": min(
                row["normalized_3b_absolute_popcount"] for row in new_rows
            ),
            "eligible_candidate_ids": [row["candidate_id"] for row in eligible],
            "eligible_candidates": len(eligible),
            "all_normalizations_verified": all(
                row["normalization_fourth_root_verified"]
                and row["transported_generator_verified"]
                for row in rows
            ),
        },
        "finding": (
            "No depth-18/19 candidate passes the low-operation coefficient gate."
            if not eligible
            else f"{len(eligible)} depth-18/19 candidate(s) pass the low-operation coefficient gate."
        ),
        "candidate_metrics": rows,
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
            raise AssertionError("candidate coefficient audit does not reproduce")
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
                "eligible_candidates": report["results"]["eligible_candidates"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
