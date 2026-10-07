#!/usr/bin/env python3
"""Attach the exact class-wide conductor certificate to one candidate registry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from audit_retained_coefficients import sha256  # noqa: E402
from p256_isogeny_search.analysis import (  # noqa: E402
    is_fundamental_discriminant,
    verified_discriminant_factors,
)

STRUCTURAL = ROOT / "results" / "initial" / "structural-report.json"


def build_report(candidate_path: Path) -> dict:
    candidate_path = candidate_path.resolve()
    payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    structural = json.loads(STRUCTURAL.read_text(encoding="utf-8"))
    common_p = int(structural["curve"]["p"]["decimal"])
    common_n = int(structural["curve"]["n"]["decimal"])
    common_t = int(structural["frobenius"]["trace"]["decimal"])
    common_d = int(structural["frobenius"]["discriminant"]["decimal"])
    factors = verified_discriminant_factors()
    assert is_fundamental_discriminant(common_d, factors)

    rows = []
    for candidate in payload["candidates"]:
        curve = candidate["curve"]
        p = int(curve["p"])
        n = int(curve["n"])
        trace = p + 1 - n
        discriminant = trace * trace - 4 * p
        assert (p, n, trace, discriminant) == (
            common_p,
            common_n,
            common_t,
            common_d,
        )
        path = candidate["path"]
        assert all(
            left["codomain_j"] == right["domain_j"]
            for left, right in zip(path, path[1:])
        )
        rows.append(
            {
                "candidate_id": candidate["candidate_id"],
                "path_depth": len(path),
                "derived_frobenius_trace": str(trace),
                "derived_frobenius_discriminant": str(discriminant),
                "frobenius_order_conductor_in_maximal_order": 1,
                "endomorphism_ring_conductor_in_maximal_order": 1,
                "endomorphism_order": "O_K = Z[pi]",
                "volcano_level_statement": "v_l(f_End(E)) = 0 for every rational prime l",
                "path_prime_volcano_levels": {
                    str(degree): 0
                    for degree in sorted({int(edge["degree"]) for edge in path})
                },
                "all_path_edges_horizontal_at_level_zero": True,
                "determination": {
                    "status": "proved_exactly",
                    "method": "class-wide order squeeze",
                    "independent_curve_specific_endomorphism_ring_computation": False,
                },
            }
        )

    new_rows = [row for row in rows if row["candidate_id"] != "p256-root"]
    return {
        "schema_version": 1,
        "publication_status": "prospective_depth_nineteen_exact_audit",
        "inputs": {
            "candidate_registry": {
                "path": str(candidate_path.relative_to(ROOT)),
                "sha256": sha256(candidate_path),
            },
            "structural_report": {
                "path": str(STRUCTURAL.relative_to(ROOT)),
                "sha256": sha256(STRUCTURAL),
            },
        },
        "proof": {
            "D_pi": str(common_d),
            "D_pi_fundamental": True,
            "order_inclusion": "Z[pi] subseteq End(E) subseteq O_K",
            "endpoint_identity": "Z[pi] = O_K",
            "conclusion": "End(E) = O_K and f_End(E) = 1",
        },
        "coverage": {
            "curves_including_p256": len(rows),
            "new_candidates": len(new_rows),
            "new_candidates_with_conductor_one": sum(
                row["endomorphism_ring_conductor_in_maximal_order"] == 1
                for row in new_rows
            ),
            "new_candidates_with_unknown_conductor": 0,
        },
        "measurement_semantics": {
            "classification": "exact algebraic derivation",
            "per_curve_numeric_measurement": False,
            "per_curve_independent_endomorphism_ring_computation": False,
        },
        "candidate_rows": rows,
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
            raise AssertionError("candidate conductor audit does not reproduce")
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
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
