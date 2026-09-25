#!/usr/bin/env python3
"""Build a deterministic design catalog; never turn proposals into measured results."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from itertools import product
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CRYPTO = ROOT.parent / "crypto"

if not __debug__:
    raise RuntimeError("catalog validation requires Python assertions; do not run with -O")

PDP_METHODS = {
    "sat": ["ecc2k130/codegen/indexcalc_e2e.py", "experiments/pdp-scaling/solve.py"],
    "f4": ["crypto:src/cryptanalysis/koblitz_groebner.rs"],
    "f5b": ["experiments/pdp-scaling/boolean_f5b_native.cpp"],
    "f5m4ri": ["experiments/pdp-scaling/boolean_f5b_m4ri.cpp"],
    "polybori": ["experiments/pdp-scaling/solve.py"],
}
COLLECTION_POLICIES = {
    "first": "first verified witness",
    "uniform": "uniform among verified witnesses",
    "rankscan": "scan verified witnesses until one adds rank",
    "rankscan16": "scan at most 16 verified witnesses for novel rank",
    "allnovel": "retain every independent verified row from one query",
}
RELATION_LA = ("gauss", "bw")
PDP_BUDGET_MS = (50, 1000)
EXPECTED_COUNT = 1000


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def load_json(name: str) -> dict:
    return json.loads((HERE / name).read_text())


def evidence_path(ref: str) -> Path:
    if ref.startswith("crypto:"):
        return CRYPTO / ref.removeprefix("crypto:")
    return ROOT / ref


def validate_routes(data: dict) -> dict[str, dict]:
    assert data["schema_version"] == 1
    nodes = {node["ref"]: node for node in data["curve_nodes"]}
    edges = {edge["id"]: edge for edge in data["edges"]}
    routes = {route["id"]: route for route in data["routes"]}
    assert len(nodes) == len(data["curve_nodes"])
    assert len(edges) == len(data["edges"])
    assert len(routes) == len(data["routes"])
    assert routes["none"]["status"] == "identity"
    for edge in edges.values():
        assert edge["source_curve_ref"] in nodes
        assert edge["target_curve_ref"] in nodes
        assert edge["degree"] >= 2
        if edge["status"] == "verified":
            for key in ("explicit_map_sha256", "subgroup_transport_certificate_sha256",
                        "map_artifact_ref", "kernel_certificate_sha256"):
                assert edge.get(key), f"verified edge {edge['id']} lacks {key}"
            for key in ("explicit_map_sha256", "subgroup_transport_certificate_sha256",
                        "kernel_certificate_sha256"):
                assert re.fullmatch(r"[0-9a-f]{64}", edge[key]), f"bad {key} on {edge['id']}"
    for route in routes.values():
        status = route["status"]
        if status == "identity":
            assert not route["edge_ids"] and route["search_prime"] is None
        elif status == "search_only":
            assert route["source_curve_ref"] in nodes
            assert route["target_curve_ref"] is None and not route["edge_ids"]
            assert route["search_prime"] >= 2
        elif status == "verified":
            assert route["source_curve_ref"] in nodes
            assert route["target_curve_ref"] in nodes
            assert route["edge_ids"]
            current = route["source_curve_ref"]
            for edge_id in route["edge_ids"]:
                edge = edges[edge_id]
                assert edge["status"] == "verified"
                assert edge["source_curve_ref"] == current
                current = edge["target_curve_ref"]
            assert current == route["target_curve_ref"]
        else:
            raise ValueError(f"unknown route status: {status}")
    return routes


def validate_profiles(profiles: list[dict], routes: dict[str, dict]) -> None:
    assert len(profiles) == 10
    assert len({p["id"] for p in profiles}) == len(profiles)
    for profile in profiles:
        assert profile["field_degree"] > 1
        assert profile["summands"] >= 2
        assert profile["isogeny_route_ref"] in routes
        assert profile["evidence"]
        count = profile["actual_factor_base_points"]
        assert count is None or count > 0
        if count is None:
            assert profile["base_digest"] is None
        elif profile["base_digest"] is not None:
            assert len(profile["base_digest"]) == 64
        else:
            assert profile.get("receipt_sha256") and profile.get("representative_keys_blake3")
        if routes[profile["isogeny_route_ref"]]["status"] == "search_only":
            assert count is None and profile["readiness"].startswith("blocked_")

    toy_anchors = load_json("toy_base_anchors.json")["bases"]
    assert {item["profile_id"] for item in toy_anchors} == {"n13_same_d3_m4", "n19_shifted_d3_m5"}
    by_id = {profile["id"]: profile for profile in profiles}
    for anchor in toy_anchors:
        profile = by_id[anchor["profile_id"]]
        slots = [{tuple(point) for point in points} for points in anchor["slot_points"]]
        union = sorted(set().union(*slots))
        assert anchor["union_points"] == [list(point) for point in union]
        assert len(union) == profile["actual_factor_base_points"]
        assert hashlib.sha256(canonical(anchor["union_points"]).encode()).hexdigest() == profile["base_digest"]
        if anchor["profile_id"] == "n19_shifted_d3_m5":
            assert len(slots) == profile["summands"]
            assert all(slots[i].isdisjoint(slots[j]) for i in range(len(slots)) for j in range(i))

    n131 = next(p for p in profiles if p["id"] == "n131_poly_d7_m4")
    n131_receipt = evidence_path("experiments/nonfrobenius-ic/results/ecc2k130-run01.json")
    if n131_receipt.is_file():
        assert hashlib.sha256(n131_receipt.read_bytes()).hexdigest() == n131["receipt_sha256"]
        receipt = json.loads(n131_receipt.read_text())
        assert receipt["factor_base"]["size"] == n131["actual_factor_base_points"]
        assert hashlib.sha256(canonical(receipt["factor_base"]["points"]).encode()).hexdigest() == n131["base_digest"]
    n53 = next(p for p in profiles if p["id"] == "n53_retained_m5")
    n53_receipt = evidence_path(n53["evidence"][0])
    if n53_receipt.is_file():
        assert hashlib.sha256(n53_receipt.read_bytes()).hexdigest() == n53["receipt_sha256"]
        receipt = json.loads(n53_receipt.read_text())
        assert receipt["factor_base_points"] == n53["actual_factor_base_points"]
        assert receipt["orbit_columns"] == n53["effective_columns"]
        assert receipt["base_hash"] == n53["representative_keys_blake3"]


def proposals(profiles: list[dict], routes: dict[str, dict]) -> list[dict]:
    rows = []
    for profile in profiles:
        route = routes[profile["isogeny_route_ref"]]
        for pdp, collection, la, budget in product(
            PDP_METHODS, COLLECTION_POLICIES, RELATION_LA, PDP_BUDGET_MS
        ):
            blockers = ["pipeline_combination_unverified"]
            if profile["actual_factor_base_points"] is None:
                blockers.append("factor_base_not_materialized")
            if collection != "first":
                blockers.append("multi_witness_adapter_unverified")
            if route["status"] == "search_only":
                blockers.append("explicit_isogeny_map_missing")
            if la == "bw":
                blockers.append("relation_matrix_bw_adapter_unverified")
            rows.append({
                "proposal_id": f"Q{len(rows) + 1}",
                "status": "proposed_unmeasured",
                "candidate_id": None,
                "profile_id": profile["id"],
                "field_degree": profile["field_degree"],
                "curve_ref": profile["curve_ref"],
                "factor_base_recipe": profile["factor_base_recipe"],
                "actual_factor_base_points": profile["actual_factor_base_points"],
                "effective_columns": profile["effective_columns"],
                "summands": profile["summands"],
                "pdp_method": pdp,
                "pdp_source_refs": PDP_METHODS[pdp],
                "pdp_budget_ms": budget,
                "collection_policy": collection,
                "relation_la": la,
                "isogeny_route_ref": route["id"],
                "activation_blockers": blockers,
                "measured_cost": None,
                "evidence_profile_ref": "profiles.json#" + profile["id"],
            })
    assert len(rows) == EXPECTED_COUNT
    assert len({canonical({k: row[k] for k in (
        "profile_id", "pdp_method", "pdp_budget_ms", "collection_policy", "relation_la"
    )}) for row in rows}) == EXPECTED_COUNT
    return rows


def output_bytes(rows: list[dict], profiles: list[dict]) -> dict[str, bytes]:
    catalog = ("\n".join(canonical(row) for row in rows) + "\n").encode()
    summary = {
        "schema_version": 1,
        "status": "proposal_catalog_not_measurements",
        "proposal_count": len(rows),
        "candidate_ids_issued": 0,
        "measured_results": 0,
        "profiles": {p["id"]: 100 for p in profiles},
        "field_degree_counts": dict(sorted(Counter(str(row["field_degree"]) for row in rows).items())),
        "isogeny_search_proposals": sum(row["isogeny_route_ref"] != "none" for row in rows),
        "pdp_methods": list(PDP_METHODS),
        "collection_policies": list(COLLECTION_POLICIES),
        "relation_la_methods": list(RELATION_LA),
        "pdp_budgets_ms": list(PDP_BUDGET_MS),
        "catalog_sha256": hashlib.sha256(catalog).hexdigest(),
    }
    return {"candidates.jsonl": catalog, "summary.json": (json.dumps(summary, indent=2) + "\n").encode()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify saved catalog and evidence anchors")
    args = parser.parse_args()
    profiles = load_json("profiles.json")["profiles"]
    routes = validate_routes(load_json("isogeny_routes.json"))
    validate_profiles(profiles, routes)
    outputs = output_bytes(proposals(profiles, routes), profiles)
    for name, expected in outputs.items():
        path = HERE / name
        if args.check:
            assert path.read_bytes() == expected, f"stale {path}"
        else:
            path.write_bytes(expected)
    print("validated 1000 distinct unmeasured proposals; no candidate IDs issued")


if __name__ == "__main__":
    main()
