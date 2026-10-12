#!/usr/bin/env python3
"""Check the E6 conductor profile import against the catalog's proved route."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
DEFAULT_ROUTES = HERE / "isogeny_routes.json"


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(data: bytes) -> dict:
    result = json.loads(data, object_pairs_hook=unique_object)
    if not isinstance(result, dict):
        raise ValueError("expected a JSON object")
    return result


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def decimal(value: object, name: str) -> int:
    require(isinstance(value, (str, int)) and not isinstance(value, bool), f"{name}: expected decimal integer")
    spelling = str(value)
    require(spelling.isdecimal() and (spelling == "0" or not spelling.startswith("0")), f"{name}: noncanonical decimal integer")
    return int(spelling)


def depths_from_conductor(conductor: int, prime_depths: dict[str, int]) -> dict[str, int]:
    levels: dict[str, int] = {}
    remainder = conductor
    for name, maximum in prime_depths.items():
        prime = decimal(name, "prime")
        level = 0
        while remainder % prime == 0:
            remainder //= prime
            level += 1
        require(level <= maximum, f"endomorphism conductor exceeds {prime}-depth")
        levels[name] = level
    require(remainder == 1, "endomorphism conductor has a prime outside the Frobenius conductor")
    return levels


def validate_records(routes: dict, profile: dict) -> dict[str, int]:
    require(routes.get("schema_version") == 1, "unsupported route schema")
    imported = routes.get("volcano_profile_import")
    require(isinstance(imported, dict), "missing volcano profile import")
    rungs = profile.get("rungs")
    require(isinstance(rungs, dict) and "131" in rungs, "missing n=131 profile")
    row = rungs["131"]
    require(row.get("n") == 131, "profile degree mismatch")
    require(row.get("order") == (1 << 131) + 1 - row.get("trace", 0), "profile order/trace mismatch")
    prime_depths = row.get("f_factorization")
    require(isinstance(prime_depths, dict) and prime_depths, "missing Frobenius conductor factorization")
    require(all(type(v) is int and v > 0 for v in prime_depths.values()), "invalid prime depths")
    product = 1
    for name, depth in prime_depths.items():
        product *= decimal(name, "prime") ** depth
    require(product == row.get("conductor_f"), "profile conductor factorization mismatch")
    require({str(p["ell"]): p["depth"] for p in row.get("primes", [])} == prime_depths,
            "profile prime records disagree with factorization")

    nodes = routes.get("curve_nodes")
    edges = routes.get("edges")
    walks = routes.get("routes")
    require(isinstance(nodes, list) and isinstance(edges, list) and isinstance(walks, list),
            "missing route manifest arrays")
    by_ref = {n["ref"]: n for n in nodes}
    by_edge = {e["id"]: e for e in edges}
    by_walk = {w["id"]: w for w in walks}
    require(len(by_ref) == len(nodes) and len(by_edge) == len(edges) and len(by_walk) == len(walks),
            "duplicate curve, edge, or route id")
    require(len({n["curve_id"] for n in nodes}) == len(nodes), "duplicate curve identity")

    for node in nodes:
        ref = node["ref"]
        require(node.get("field_degree") == 131, f"{ref}: wrong field degree")
        require(decimal(node.get("subgroup_order"), f"{ref} subgroup") * 4 == row["order"],
                f"{ref}: subgroup order does not match profile")
        frobenius = decimal(node.get("frobenius_order_conductor_over_f2_131"), f"{ref} Frobenius conductor")
        require(frobenius == row["conductor_f"], f"{ref}: Frobenius conductor mismatch")
        position = node.get("volcano_position")
        require(isinstance(position, dict) and position.get("profile_rung") == "131", f"{ref}: missing profile link")
        require(position.get("prime_depths") == prime_depths, f"{ref}: imported prime depths differ")
        conductor = decimal(node.get("endomorphism_order_conductor"), f"{ref} endomorphism conductor")
        require(conductor > 0 and frobenius % conductor == 0, f"{ref}: impossible endomorphism conductor")
        levels = depths_from_conductor(conductor, prime_depths)
        require(node.get("proved_volcano_levels") == levels, f"{ref}: proved levels disagree with conductor")
        if conductor == 1:
            require(position.get("component") == "surface" and position.get("reachable_via") == "none",
                    f"{ref}: invalid surface position")
        else:
            walk_id = position.get("reachable_via")
            require(position.get("component") == "reachable_263_floor" and conductor == 263,
                    f"{ref}: unsupported component claim")
            require(walk_id in by_walk and by_walk[walk_id].get("status") == "verified",
                    f"{ref}: missing verified route")
            require(by_walk[walk_id].get("target_curve_ref") == ref, f"{ref}: route target mismatch")

    for edge in edges:
        require(edge.get("status") == "verified" and edge.get("degree") == 263 and edge.get("direction") == "descending",
                f"{edge['id']}: unsupported verified edge")
        source = by_ref.get(edge.get("source_curve_ref"))
        target = by_ref.get(edge.get("target_curve_ref"))
        require(source is not None and target is not None, f"{edge['id']}: unknown endpoint")
        require(source["proved_volcano_levels"]["263"] + 1 == target["proved_volcano_levels"]["263"],
                f"{edge['id']}: direction disagrees with level change")
        require(edge.get("separable") is True, f"{edge['id']}: separability unverified")
        for key in ("explicit_map_sha256", "kernel_certificate_sha256", "subgroup_transport_certificate_sha256"):
            value = edge.get(key)
            require(isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value),
                    f"{edge['id']}: missing {key}")

    for walk in walks:
        if walk.get("status") != "verified":
            continue
        chain = walk.get("edge_ids")
        require(isinstance(chain, list) and chain, f"{walk['id']}: empty verified route")
        require(all(edge_id in by_edge for edge_id in chain), f"{walk['id']}: unknown edge")
        require(by_edge[chain[0]]["source_curve_ref"] == walk.get("source_curve_ref") and
                by_edge[chain[-1]]["target_curve_ref"] == walk.get("target_curve_ref"),
                f"{walk['id']}: endpoint mismatch")
        require(all(by_edge[a]["target_curve_ref"] == by_edge[b]["source_curve_ref"]
                    for a, b in zip(chain, chain[1:])), f"{walk['id']}: disconnected route")
    return {"curves": len(nodes), "verified_edges": len(edges),
            "verified_routes": sum(w.get("status") == "verified" for w in walks)}


def validate_files(routes_path: Path, profile_path: Path | None = None) -> dict[str, int]:
    routes = load_json(routes_path.read_bytes())
    imported = routes.get("volcano_profile_import")
    require(isinstance(imported, dict), "missing volcano profile import")
    require(imported.get("file") == "volcano_profiles_20261008.json", "unexpected profile filename")
    selected = profile_path or routes_path.with_name(imported["file"])
    data = selected.read_bytes()
    require(hashlib.sha256(data).hexdigest() == imported.get("sha256"), "imported profile hash mismatch")
    return validate_records(routes, load_json(data))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--routes", type=Path, default=DEFAULT_ROUTES)
    parser.add_argument("--profile", type=Path, help="override profile path while keeping the pinned digest")
    args = parser.parse_args()
    try:
        counts = validate_files(args.routes, args.profile)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"volcano manifest: FAIL: {error}\n")
    print(f"volcano manifest: PASS: {counts['curves']} curves, {counts['verified_edges']} verified edge, "
          f"{counts['verified_routes']} verified route")


if __name__ == "__main__":
    main()
