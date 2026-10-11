#!/usr/bin/env python3
"""Attach the exact endomorphism-order conductor proof to every retained curve."""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from audit_retained_coefficients import (  # noqa: E402
    SOURCE_REGISTRIES,
    UNION,
    reconstruct,
    source,
)
from p256_isogeny_search.analysis import (  # noqa: E402
    is_fundamental_discriminant,
    verified_discriminant_factors,
)

STRUCTURAL_REPORT = ROOT / "results" / "initial" / "structural-report.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def edge_rows(
    path: list[dict[str, Any]], degree_classes: dict[int, str]
) -> list[dict[str, Any]]:
    rows = []
    for index, edge in enumerate(path):
        degree = int(edge["degree"])
        if degree not in degree_classes:
            raise AssertionError(f"unclassified path degree {degree}")
        rows.append(
            {
                "edge_index": index,
                "degree": degree,
                "prime_splitting_in_cm_field": degree_classes[degree],
                "domain_j": str(edge["domain_j"]),
                "codomain_j": str(edge["codomain_j"]),
                "domain_volcano_level": 0,
                "codomain_volcano_level": 0,
                "orientation": "horizontal",
            }
        )
    return rows


def candidate_row(
    candidate_id: str,
    record: dict[str, Any],
    origin: str,
    *,
    common_p: int,
    common_n: int,
    common_trace: int,
    common_discriminant: int,
    degree_classes: dict[int, str],
) -> dict[str, Any]:
    curve = record["curve"]
    p = int(curve["p"])
    n = int(curve["n"])
    trace = p + 1 - n
    discriminant = trace * trace - 4 * p
    if (p, n, trace, discriminant) != (
        common_p,
        common_n,
        common_trace,
        common_discriminant,
    ):
        raise AssertionError(f"isogeny-class invariant mismatch for {candidate_id}")

    path = record.get("path", [])
    j = str(curve["j_invariant"])
    if path:
        for left, right in zip(path, path[1:]):
            if str(left["codomain_j"]) != str(right["domain_j"]):
                raise AssertionError(f"broken path chain for {candidate_id}")
        if str(path[-1]["codomain_j"]) != j:
            raise AssertionError(f"path endpoint mismatch for {candidate_id}")
    elif candidate_id != "p256-root":
        raise AssertionError(f"non-root curve has an empty path: {candidate_id}")

    edges = edge_rows(path, degree_classes)
    return {
        "candidate_id": candidate_id,
        "record_source": origin,
        "path_depth": len(path),
        "curve_j_invariant": j,
        "curve_p": str(p),
        "curve_order_n": str(n),
        "derived_frobenius_trace": str(trace),
        "derived_frobenius_discriminant": str(discriminant),
        "common_isogeny_class_invariants_verified": True,
        "frobenius_order_conductor_in_maximal_order": 1,
        "endomorphism_ring_conductor_in_maximal_order": 1,
        "endomorphism_order": "O_K = Z[pi]",
        "endomorphism_order_discriminant": str(common_discriminant),
        "possible_endomorphism_orders": 1,
        "volcano_level_statement": "v_l(f_End(E)) = v_l(1) = 0 for every rational prime l",
        "path_prime_volcano_levels": {
            str(degree): 0 for degree in sorted({edge["degree"] for edge in edges})
        },
        "path_edge_degrees": [edge["degree"] for edge in edges],
        "all_path_edges_horizontal_at_level_zero": True,
        "edge_classification_reference": (
            "results.unique_path_edge_rows keyed by domain_j, codomain_j, and degree"
        ),
        "determination": {
            "status": "proved_exactly",
            "method": "class-wide order squeeze",
            "independent_curve_specific_endomorphism_ring_computation": False,
        },
    }


def build_report() -> dict[str, Any]:
    structural = load(STRUCTURAL_REPORT)
    candidate_ids, records, origins = reconstruct()

    common_p = int(structural["curve"]["p"]["decimal"])
    common_n = int(structural["curve"]["n"]["decimal"])
    common_trace = int(structural["frobenius"]["trace"]["decimal"])
    common_discriminant = int(structural["frobenius"]["discriminant"]["decimal"])
    if common_trace != common_p + 1 - common_n:
        raise AssertionError("stored Frobenius trace does not equal p + 1 - n")
    if common_discriminant != common_trace * common_trace - 4 * common_p:
        raise AssertionError("stored Frobenius discriminant does not equal t^2 - 4p")

    factors = verified_discriminant_factors()
    if [str(value) for value in factors] != structural["frobenius"][
        "absolute_discriminant_prime_factors"
    ]:
        raise AssertionError("stored and certificate-verified factorizations differ")
    if not is_fundamental_discriminant(common_discriminant, factors):
        raise AssertionError("Frobenius discriminant is not fundamental")
    if not structural["frobenius"]["prime_factor_certificates_verified"]:
        raise AssertionError("frozen structural report lacks verified primality certificates")

    degree_classes: dict[int, str] = {}
    for class_name in ("ramified", "split", "inert"):
        for degree in structural["small_rational_isogeny_degrees"][class_name]:
            degree_classes[int(degree)] = class_name

    rows = [
        candidate_row(
            candidate_id,
            records[candidate_id],
            origins[candidate_id],
            common_p=common_p,
            common_n=common_n,
            common_trace=common_trace,
            common_discriminant=common_discriminant,
            degree_classes=degree_classes,
        )
        for candidate_id in candidate_ids
    ]
    all_edges = [
        edge
        for candidate_id in candidate_ids
        for edge in edge_rows(records[candidate_id].get("path", []), degree_classes)
    ]
    edge_counts = collections.Counter(edge["degree"] for edge in all_edges)
    unique_edge_map = {}
    for edge in all_edges:
        key = (edge["domain_j"], edge["codomain_j"], edge["degree"])
        unique_edge_map[key] = {
            field: value for field, value in edge.items() if field != "edge_index"
        }
    unique_edge_rows = [
        unique_edge_map[key]
        for key in sorted(unique_edge_map, key=lambda value: (value[2], value[0], value[1]))
    ]
    unique_path_degrees = sorted(edge_counts)

    return {
        "schema_version": 1,
        "publication_status": "retrospective_exact_audit",
        "question": (
            "What is the endomorphism-ring conductor and the corresponding volcano "
            "level for every curve and explicit isogeny path in the retained P-256 registry?"
        ),
        "inputs": {
            "structural_report": source(STRUCTURAL_REPORT),
            "retained_union": source(UNION),
            "candidate_registries": [source(path) for path in SOURCE_REGISTRIES],
        },
        "coverage": {
            "retained_curves_including_p256": len(candidate_ids),
            "records_reconstructed": len(records),
            "unique_candidate_ids": len(set(candidate_ids)),
            "source_registries": len(SOURCE_REGISTRIES),
            "stored_path_edge_occurrences_classified": sum(edge_counts.values()),
            "unique_stored_directed_path_edges": len(unique_edge_rows),
            "unique_path_prime_degrees": unique_path_degrees,
            "path_edge_occurrences_by_degree": {
                str(degree): edge_counts[degree] for degree in unique_path_degrees
            },
        },
        "common_isogeny_class": {
            "ordinary": True,
            "p": str(common_p),
            "n": str(common_n),
            "frobenius_trace_t": str(common_trace),
            "frobenius_discriminant_D_pi": str(common_discriminant),
            "absolute_discriminant_prime_factors": [str(value) for value in factors],
            "factorization_squarefree": len(set(factors)) == len(factors),
            "factor_primality_certificates_verified": True,
            "D_pi_fundamental": True,
            "frobenius_order_conductor_in_maximal_order": 1,
        },
        "proof": {
            "order_inclusion": "Z[pi] subseteq End(E) subseteq O_K",
            "endpoint_identity": "D_pi fundamental implies Z[pi] = O_K",
            "conclusion": "End(E) = O_K and f_End(E) = 1 for every curve in the class",
            "volcano_conclusion": "v_l(f_End(E)) = 0 for every rational prime l",
            "path_edge_conclusion": (
                "Every retained prime-degree path edge joins level-zero curves and is horizontal."
            ),
            "scope": "geometric endomorphism order of each ordinary curve over F_p",
        },
        "primary_sources": [
            {
                "citation": "Waterhouse, Abelian varieties over finite fields (1969)",
                "url": "https://www.numdam.org/item/ASENS_1969_4_2_4_521_0/",
                "role": "endomorphism-order classification in an ordinary finite-field isogeny class",
            },
            {
                "citation": "Sutherland, Isogeny volcanoes (2013)",
                "url": "https://doi.org/10.2140/obs.2013.1.507",
                "role": "volcano levels and horizontal/vertical edge terminology",
            },
        ],
        "measurement_semantics": {
            "classification": "exact algebraic derivation",
            "per_curve_numeric_measurement": False,
            "per_curve_independent_endomorphism_ring_computation": False,
            "reason": (
                "The class-wide inclusion has identical endpoints, so repeating a separate "
                "endomorphism-ring computation on each model would add no mathematical information."
            ),
            "registry_checks_per_curve": (
                "p, n, t, D_pi, explicit path continuity, endpoint j, and every stored edge classification"
            ),
        },
        "cost_accounting": {
            "discovery_and_certificate_verification": "reusable class-wide work",
            "per_curve_registry_audit": "deterministic replay; not used as a performance claim",
            "per_key_attack_cost": None,
            "new_rho_measurement": None,
        },
        "results": {
            "curves_with_endomorphism_conductor_one": len(rows),
            "curves_with_nontrivial_endomorphism_conductor": 0,
            "curves_with_unknown_endomorphism_conductor": 0,
            "path_edges_horizontal": sum(edge_counts.values()),
            "unique_path_edges_horizontal": len(unique_edge_rows),
            "unique_path_edge_rows": unique_edge_rows,
            "path_edges_vertical": 0,
            "candidate_rows": rows,
        },
        "obligations": [
            {
                "name": "class_discriminant_and_factorization",
                "status": "supported",
                "scope": "exact arithmetic plus complete certificate-verified factorization",
            },
            {
                "name": "all_retained_candidate_conductors",
                "status": "supported",
                "scope": f"{len(rows)} reconstructed candidate records",
            },
            {
                "name": "all_retained_path_edge_orientations",
                "status": "supported",
                "scope": f"{sum(edge_counts.values())} stored path-edge occurrences",
            },
            {
                "name": "entire_isogeny_class_enumerated",
                "status": "not_claimed",
                "scope": "the proof is class-wide, but the explicit retained registry is bounded",
            },
            {
                "name": "dramatic_end_to_end_ecdlp_speedup",
                "status": "unknown",
                "scope": "conductor one removes vertical-level variation but is not a speed measurement",
            },
        ],
        "finding": (
            "All retained curves have endomorphism-ring conductor 1. Every stored path edge "
            "is horizontal at volcano level zero; no candidate offers a different conductor level."
        ),
        "exploration_boundary": {
            "explicit_curves": len(rows),
            "maximum_low_degree_path_depth": 17,
            "one_hop_prime_degree_bound": 199,
            "class_wide_claim": (
                "conductor 1 and zero volcano levels for all curves in the P-256 F_p-isogeny class"
            ),
            "enumeration_claim": "only the retained bounded registry is enumerated",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "curves": report["coverage"]["retained_curves_including_p256"],
                "endomorphism_conductor": 1,
                "horizontal_path_edges": report["results"]["path_edges_horizontal"],
                "vertical_path_edges": report["results"]["path_edges_vertical"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
