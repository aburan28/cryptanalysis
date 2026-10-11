#!/usr/bin/env python3
"""Verify the frozen full-registry endomorphism-conductor audit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from audit_retained_conductors import build_report

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "conductor-audit-20261007"
FROZEN = RESULTS / "audit.json"
RECEIPT = ROOT / "receipt-conductor-audit-20261007.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    frozen = load(FROZEN)
    assert frozen == build_report()

    receipt = load(RECEIPT)
    manifest = ROOT / receipt["source"]["manifest"]
    assert sha256(manifest) == receipt["source"]["manifest_sha256"]
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        assert sha256(ROOT / relative) == expected, relative
    for relative, expected in receipt["artifacts"].items():
        assert sha256(ROOT / relative) == expected, relative

    coverage = frozen["coverage"]
    assert coverage["retained_curves_including_p256"] == 2226
    assert coverage["records_reconstructed"] == 2226
    assert coverage["unique_candidate_ids"] == 2226
    assert coverage["source_registries"] == 14
    assert coverage["stored_path_edge_occurrences_classified"] == 26162
    assert coverage["unique_stored_directed_path_edges"] == 2225

    common = frozen["common_isogeny_class"]
    assert common["D_pi_fundamental"]
    assert common["factorization_squarefree"]
    assert common["factor_primality_certificates_verified"]
    assert common["frobenius_order_conductor_in_maximal_order"] == 1

    results = frozen["results"]
    assert results["curves_with_endomorphism_conductor_one"] == 2226
    assert results["curves_with_nontrivial_endomorphism_conductor"] == 0
    assert results["curves_with_unknown_endomorphism_conductor"] == 0
    assert results["path_edges_horizontal"] == 26162
    assert results["unique_path_edges_horizontal"] == 2225
    assert results["path_edges_vertical"] == 0
    assert len(results["candidate_rows"]) == 2226
    assert len(results["unique_path_edge_rows"]) == 2225
    assert all(
        edge["orientation"] == "horizontal"
        and edge["domain_volcano_level"] == 0
        and edge["codomain_volcano_level"] == 0
        for edge in results["unique_path_edge_rows"]
    )
    for row in results["candidate_rows"]:
        assert row["common_isogeny_class_invariants_verified"]
        assert row["frobenius_order_conductor_in_maximal_order"] == 1
        assert row["endomorphism_ring_conductor_in_maximal_order"] == 1
        assert row["possible_endomorphism_orders"] == 1
        assert row["determination"] == {
            "independent_curve_specific_endomorphism_ring_computation": False,
            "method": "class-wide order squeeze",
            "status": "proved_exactly",
        }
        assert all(level == 0 for level in row["path_prime_volcano_levels"].values())
        assert row["all_path_edges_horizontal_at_level_zero"]
        assert row["path_depth"] == len(row["path_edge_degrees"])

    assert receipt["decision"] == "No conductor-varying candidate or vertical path exists."
    print(
        json.dumps(
            {
                "status": "verified",
                "curves": 2226,
                "endomorphism_conductor": 1,
                "horizontal_path_edges": 26162,
                "vertical_path_edges": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
