#!/usr/bin/env python3
"""Validate IC identity metadata without running elliptic-curve arithmetic.

The same file is kept in crypto/docs/curves/ic/.  It checks syntax, canonical
hashes, references, and evidence *presence*.  A passing result is not a proof
of a curve order, isogeny map, or DLP transport; those need their own replays.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import jsonschema
import yaml


HEX64 = re.compile(r"[0-9a-f]{64}\Z")
CURVE_ID = re.compile(r"EC1(N[1-9][0-9]*|P[1-9][0-9]*|Q[1-9][0-9]*D[1-9][0-9]*)C([a-z][a-z0-9]*)h([0-9a-f]{12,64})\Z")
UNKNOWN = {"unknown", "unmeasured", "not_evaluated", "unproved_in_this_registry", "not_applicable"}
PINNED = ("curves.yaml", "curves.schema.json", "curve-links/link.schema.json")
PEER_FILES = PINNED + ("validate_semantics.py", "test_validate_semantics.py")


def canonical(value: object) -> bytes:
    def check(v: object) -> None:
        if v is None or type(v) in (str, int, bool):
            return
        if isinstance(v, list):
            for item in v:
                check(item)
            return
        if isinstance(v, dict) and all(isinstance(k, str) for k in v):
            for item in v.values():
                check(item)
            return
        raise ValueError("identity record contains a float, non-string key, or non-JSON value")

    check(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def repo_artifact(root: Path, reference: object) -> Path | None:
    if not isinstance(reference, str) or not reference:
        return None
    relative = Path(reference)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    root = root.resolve()
    resolved = (root / relative).resolve()
    return resolved if resolved.is_relative_to(root) else None


def check(condition: bool, errors: list[str], where: str, message: str) -> None:
    if not condition:
        errors.append(f"{where}: {message}")


def namespace(field: dict) -> str:
    p = field.get("p", field.get("characteristic"))
    n = field.get("n", field.get("degree"))
    if type(p) is not int or p < 2 or type(n) is not int or n < 1:
        raise ValueError("field needs integer characteristic p >= 2 and degree n >= 1")
    return f"N{n}" if p == 2 else f"P{p.bit_length()}" if n == 1 else f"Q{p}D{n}"


def curve_hash(field: dict, curve: dict) -> str:
    return digest({"field": field, "curve": {k: v for k, v in curve.items() if k != "curve_id"}})


def check_curve_identity(field: dict, curve: dict, curve_id: str, tag: str,
                         uid: str | None, errors: list[str], where: str) -> None:
    m = CURVE_ID.fullmatch(curve_id) if isinstance(curve_id, str) else None
    check(m is not None, errors, where, "invalid EC1 curve ID grammar")
    if not m:
        return
    try:
        prefix, sha = namespace(field), curve_hash(field, curve)
    except (TypeError, ValueError) as exc:
        errors.append(f"{where}: {exc}")
        return
    check(m[1] == prefix and m[2] == tag and sha.startswith(m[3]), errors, where,
          "EC1 curve ID does not match the canonical field and curve record")
    if uid is not None:
        check(uid == f"urn:ec-record:1:sha256:{sha}", errors, where,
              "full curve UID does not match the canonical field and curve record")


def check_curve_math_metadata(entry: dict, errors: list[str], where: str) -> None:
    field, curve = entry["field"], entry["curve"]
    p = field.get("p", field.get("characteristic"))
    n = field.get("n", field.get("degree"))
    order = curve.get("curve_order", curve.get("order"))
    r = curve.get("subgroup_order", curve.get("r"))
    cofactor = curve.get("cofactor")
    trace = curve.get("trace")
    generator = curve.get("generator_G", curve.get("generator", curve.get("G")))
    check(bool(field.get("representation", field.get("basis"))), errors, where,
          "field representation or basis is missing")
    check(bool(field.get("element_encoding")), errors, where, "field element encoding is missing")
    if type(n) is int and n > 1:
        check(any(field.get(key) is not None for key in
                  ("defining_polynomial_int", "defining_modulus_low_terms", "modulus_exponents",
                   "modulus", "defining_polynomial")), errors, where,
              "extension-field defining modulus is missing")
    check(bool(curve.get("model", curve.get("weierstrass_equation"))), errors, where,
          "curve model or Weierstrass equation is missing")
    check(any(key in curve for key in ("coefficients", "coefficients_a1_a2_a3_a4_a6", "a2", "a6")),
          errors, where, "exact curve coefficients are missing")
    check(type(r) is int and r > 0, errors, where, "subgroup order must be a positive integer")
    check(type(cofactor) is int and cofactor > 0, errors, where, "cofactor must be a positive integer")
    check(isinstance(generator, list) and len(generator) == 2, errors, where,
          "generator must have two encoded coordinates")
    check(isinstance(curve.get("target_group"), str) and bool(curve["target_group"]),
          errors, where, "target group is missing")
    if type(order) is int and type(r) is int and type(cofactor) is int:
        check(order == r * cofactor, errors, where, "curve order differs from subgroup order times cofactor")
    if all(type(v) is int for v in (p, n, order, trace)):
        check(order == p**n + 1 - trace, errors, where, "curve order and trace disagree")


def validate_registry(directory: Path, errors: list[str]) -> tuple[dict, dict, dict]:
    data = yaml.safe_load((directory / "curves.yaml").read_text(encoding="utf-8"))
    schema = read_json(directory / "curves.schema.json")
    for issue in jsonschema.Draft202012Validator(schema).iter_errors(data):
        errors.append(f"curves.yaml/{'/'.join(map(str, issue.absolute_path))}: {issue.message}")
    if not isinstance(data, dict) or not isinstance(data.get("curves"), dict):
        return {}, {}, {}
    by_uid, by_ref, by_id = {}, {}, {}
    for alias, entry in data["curves"].items():
        where = f"curves.yaml:{alias}"
        if not isinstance(entry, dict) or not isinstance(entry.get("field"), dict) or not isinstance(entry.get("curve"), dict):
            errors.append(f"{where}: field and curve must be objects")
            continue
        check_curve_identity(entry["field"], entry["curve"], entry.get("curve_id"),
                             entry.get("curve_tag"), entry.get("curve_uid"), errors, where)
        check_curve_math_metadata(entry, errors, where)
        uid, ref, cid = entry.get("curve_uid"), entry.get("curve_ref"), entry.get("curve_id")
        for key, table, label in ((uid, by_uid, "UID"), (ref, by_ref, "curve_ref"), (cid, by_id, "curve ID")):
            if key is not None:
                check(key not in table, errors, where, f"duplicate {label}: {key}")
                table[key] = entry
        for name, trait in entry.get("trait_status", {}).items():
            if not isinstance(trait, dict):
                continue
            status, value = trait.get("status"), trait.get("value")
            if status in UNKNOWN:
                check(value is None, errors, where, f"{name}: {status} needs value: null")
            elif status in ("proved", "derived_from_model"):
                check(value is not None, errors, where, f"{name}: {status} needs a value")
                if status == "proved":
                    check(bool(trait.get("proof_ref")), errors, where, f"{name}: proved needs proof_ref")
        endo = entry.get("endomorphism", {})
        if isinstance(endo, dict):
            for name in ("endomorphism_order_conductor", "frobenius_order_conductor"):
                value = endo.get(name)
                check(value is None or (type(value) is int and value > 0), errors, where,
                      f"{name} must be null or a positive integer")
            for ell, position in (endo.get("volcano_levels") or {}).items():
                level = position.get("level") if isinstance(position, dict) else None
                status = position.get("status") if isinstance(position, dict) else None
                check(str(ell).isdigit() and int(ell) > 1, errors, where, f"invalid volcano prime {ell}")
                check((type(level) is int and level >= 0) if status == "proved" else level is None,
                      errors, where, f"V{ell}: level requires proved status, otherwise null")
                if status == "proved":
                    check(bool(position.get("proof_ref")), errors, where, f"V{ell}: missing proof_ref")
                    characteristic = entry["field"].get("p", entry["field"].get("characteristic"))
                    check(not (characteristic == 2 and str(ell) == "2"), errors, where,
                          "characteristic-two degree-2 edge cannot carry an ordinary V2 level")
        for kind, inventory in entry.get("representation_links", {}).items():
            if not isinstance(inventory, dict):
                continue
            if inventory.get("status") == "not_enumerated":
                check(inventory.get("scope") is None and inventory.get("links") == [], errors, where,
                      f"{kind}: not_enumerated must have null scope and no links")
            elif inventory.get("status") == "complete_for_declared_scope":
                check(bool(inventory.get("scope")), errors, where,
                      f"{kind}: complete inventory needs a declared scope")
        identity = entry.get("icv1_identity", {})
        if isinstance(identity, dict):
            status = identity.get("status")
            if status in ("unregistered_general_binary_model", "unresolved"):
                check(identity.get("slug") is None and identity.get("full") is None, errors, where,
                      "unregistered or unresolved ICV1 identity must stay null")
            elif status in ("model_match_only", "registered_representation"):
                check(bool(identity.get("slug")) and bool(identity.get("full")), errors, where,
                      "matched ICV1 identity needs slug and full string")
    return by_uid, by_ref, by_id


def link_identity_record(item: dict) -> dict:
    """Stable mathematical content; paths and mutable verification stay outside."""
    kind = item.get("kind")
    details = item.get(kind, {})
    keys = {"same_field_isomorphism": ("generator_relation",),
            "twist": ("twist_kind", "twist_parameter", "extension_degree"),
            "base_change": ("extension_degree",)}.get(kind, ())
    return {"schema_version": item.get("schema_version"), "kind": kind,
            "source_curve_uid": item.get("source_curve_uid"),
            "target_curve_uid": item.get("target_curve_uid"),
            "map_sha256": item.get("map_sha256"),
            "details": {key: details.get(key) for key in keys}}


def validate_links(directory: Path, by_uid: dict, errors: list[str]) -> None:
    schema = read_json(directory / "curve-links/link.schema.json")
    links = {}
    for path in sorted((directory / "curve-links").glob("*.json")):
        if path.name == "link.schema.json":
            continue
        where = str(path.relative_to(directory))
        try:
            item = read_json(path)
        except (ValueError, OSError) as exc:
            errors.append(f"{where}: {exc}")
            continue
        for issue in jsonschema.Draft202012Validator(schema).iter_errors(item):
            errors.append(f"{where}/{'/'.join(map(str, issue.absolute_path))}: {issue.message}")
        if not isinstance(item, dict):
            continue
        check(bool(HEX64.fullmatch(path.stem)), errors, where, "link filename must be a full SHA-256 digest")
        check(path.stem == digest(link_identity_record(item)), errors, where,
              "link filename disagrees with its canonical mathematical record")
        check(item.get("source_curve_uid") in by_uid, errors, where, "source curve UID is absent from registry")
        target = item.get("target_curve_uid")
        if target is not None:
            check(target in by_uid, errors, where, "target curve UID is absent from registry")
        if item.get("status") == "verified":
            check(target is not None, errors, where, "verified link needs target curve UID")
            check(bool(item.get("map_artifact_ref")) and bool(item.get("map_sha256")) and bool(item.get("proof_refs")),
                  errors, where, "verified link needs map and proof references")
            transport = item.get("subgroup_transport", {})
            if transport.get("status") == "verified":
                check(bool(transport.get("evidence_ref")), errors, where,
                      "verified subgroup transport needs evidence_ref")
            if directory.parts[-2:] == ("experiments", "ic-candidate-catalog"):
                artifact_ref = item.get("map_artifact_ref")
                artifact = repo_artifact(directory.parents[1], artifact_ref)
                check(artifact is not None and artifact.is_file(), errors, where,
                      f"map artifact is missing or outside repository: {artifact_ref}")
                if artifact is not None and artifact.is_file() and isinstance(item.get("map_sha256"), str):
                    check(hashlib.sha256(artifact.read_bytes()).hexdigest() == item["map_sha256"],
                          errors, where, "map artifact SHA-256 differs")
            if target in by_uid and item.get("source_curve_uid") in by_uid:
                source_field = by_uid[item["source_curve_uid"]]["field"]
                target_field = by_uid[target]["field"]
                if item.get("kind") in ("twist", "same_field_isomorphism"):
                    check(namespace(source_field) == namespace(target_field), errors, where,
                          "twist or same-field isomorphism must retain field characteristic and degree")
                elif item.get("kind") == "base_change":
                    sp = source_field.get("p", source_field.get("characteristic"))
                    tp = target_field.get("p", target_field.get("characteristic"))
                    sn = source_field.get("n", source_field.get("degree"))
                    tn = target_field.get("n", target_field.get("degree"))
                    check(sp == tp and type(sn) is int and type(tn) is int and tn > sn and tn % sn == 0,
                          errors, where, "base change must use a proper extension of the same characteristic")
        links[path.name] = item
    for uid, entry in by_uid.items():
        for inventory_kind, inventory in entry.get("representation_links", {}).items():
            expected_kind = {"same_field_isomorphisms": "same_field_isomorphism", "twists": "twist",
                             "base_changes": "base_change"}.get(inventory_kind)
            for ref in inventory.get("links", []):
                name = Path(ref).name
                item = links.get(name)
                check(item is not None, errors, f"{uid}/{inventory_kind}", f"missing link manifest {ref}")
                if item is not None:
                    check(item.get("kind") == expected_kind and uid in (item.get("source_curve_uid"), item.get("target_curve_uid")),
                          errors, f"{uid}/{inventory_kind}", f"link {ref} has wrong kind or endpoints")
    for name, item in links.items():
        key = {"same_field_isomorphism": "same_field_isomorphisms", "twist": "twists", "base_change": "base_changes"}.get(item.get("kind"))
        if key:
            for uid in (item.get("source_curve_uid"), item.get("target_curve_uid")):
                if uid in by_uid:
                    refs = by_uid[uid].get("representation_links", {}).get(key, {}).get("links", [])
                    check(name in [Path(ref).name for ref in refs], errors, name,
                          f"endpoint {uid} does not list this link")


def validate_routes(directory: Path, by_ref: dict, errors: list[str]) -> dict:
    graph = read_json(directory / "isogeny_routes.json")
    nodes = {node.get("ref"): node for node in graph.get("curve_nodes", [])}
    edges = {edge.get("id"): edge for edge in graph.get("edges", [])}
    routes = {route.get("id"): route for route in graph.get("routes", [])}
    check(len(nodes) == len(graph.get("curve_nodes", [])), errors, "isogeny_routes.json", "duplicate node ref")
    check(len(edges) == len(graph.get("edges", [])), errors, "isogeny_routes.json", "duplicate edge ID")
    check(len(routes) == len(graph.get("routes", [])), errors, "isogeny_routes.json", "duplicate route ID")
    for ref, node in nodes.items():
        check(ref in by_ref, errors, f"isogeny node {ref}", "missing curve registry entry")
        if ref in by_ref:
            check(node.get("curve_id") == by_ref[ref].get("curve_id"), errors,
                  f"isogeny node {ref}", "curve ID differs from registry")
    for edge_id, edge in edges.items():
        where = f"isogeny edge {edge_id}"
        source, target = edge.get("source_curve_ref"), edge.get("target_curve_ref")
        check(source in nodes and target in nodes, errors, where, "endpoint absent from graph")
        degree = edge.get("degree")
        check(type(degree) is int and degree > 1, errors, where, "degree must be an integer greater than one")
        if edge.get("status") == "verified":
            for key in ("explicit_map_sha256", "kernel_certificate_sha256", "subgroup_transport_certificate_sha256"):
                check(isinstance(edge.get(key), str) and bool(HEX64.fullmatch(edge[key])), errors, where,
                      f"verified edge needs {key}")
            artifact_ref = edge.get("map_artifact_ref")
            check(bool(artifact_ref), errors, where, "verified edge needs map artifact ref")
            if artifact_ref is not None:
                artifact = repo_artifact(directory.parents[1], artifact_ref)
                check(artifact is not None and artifact.is_file(), errors, where,
                      f"map artifact is missing or outside repository: {artifact_ref}")
        if source in by_ref and target in by_ref:
            a, b = by_ref[source], by_ref[target]
            for key in ("curve_order", "trace", "subgroup_order"):
                av, bv = a["curve"].get(key), b["curve"].get(key)
                if av is not None and bv is not None:
                    check(av == bv, errors, where, f"isogenous endpoints disagree on {key}")
            p = a["field"].get("p", a["field"].get("characteristic"))
            if degree != p and edge.get("direction") in ("descending", "ascending", "horizontal"):
                x = (a.get("endomorphism", {}).get("volcano_levels") or {}).get(str(degree))
                y = (b.get("endomorphism", {}).get("volcano_levels") or {}).get(str(degree))
                if isinstance(x, dict) and isinstance(y, dict) and x.get("status") == y.get("status") == "proved":
                    delta = {"descending": 1, "ascending": -1, "horizontal": 0}[edge["direction"]]
                    check(y.get("level") == x.get("level") + delta, errors, where,
                          "direction disagrees with proved volcano levels")
    for route_id, route in routes.items():
        if route.get("status") != "verified":
            continue
        where = f"isogeny route {route_id}"
        sequence = route.get("edge_ids", [])
        check(bool(sequence), errors, where, "verified route has no edges")
        current = route.get("source_curve_ref")
        check(current in by_ref, errors, where, "source curve absent from registry")
        for edge_id in sequence:
            edge = edges.get(edge_id)
            check(edge is not None and edge.get("status") == "verified", errors, where,
                  f"edge {edge_id} is absent or unverified")
            if edge is None:
                break
            check(edge.get("source_curve_ref") == current, errors, where, f"edge {edge_id} breaks route order")
            current = edge.get("target_curve_ref")
        check(current == route.get("target_curve_ref") and current in by_ref, errors, where,
              "verified route target differs from ordered edges or registry")
    for ref, entry in by_ref.items():
        declared = entry.get("isogeny_routes", {})
        for direction in ("incoming", "outgoing"):
            expected = {route_id for route_id, route in routes.items() if route.get("status") == "verified" and
                        route.get("target_curve_ref" if direction == "incoming" else "source_curve_ref") == ref}
            check(set(declared.get(direction, [])) == expected, errors, f"curves.yaml:{ref}",
                  f"{direction} route inventory differs from verified graph routes")
    return routes


def validate_candidates(root: Path, routes: dict, errors: list[str]) -> None:
    base = root / "experiments/ic-bench"
    archive = root / "experiments/fb-archive/index.csv"
    indexed = set()
    if archive.exists():
        with archive.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                indexed.add((row["curve_id"], row["enumerated_set_sha256"], row["fb_points"]))
    candidate_curves = set()
    for path in sorted((base / "candidates").glob("*.json")):
        where = str(path.relative_to(root))
        item = read_json(path)
        curve, field, fb = item["curve"], item["field"], item["factor_base"]
        cid = curve.get("curve_id")
        m = CURVE_ID.fullmatch(cid) if isinstance(cid, str) else None
        check_curve_identity(field, curve, cid, m[2] if m else "", None, errors, where)
        check_curve_math_metadata(item, errors, where)
        candidate_curves.add(cid)
        check("candidate_id" not in item, errors, where, "candidate_id must not enter its own hash input")
        stages = [item.get(k, {}).get("stage_code", "") for k in
                  ("point_decomposition", "relation_collection", "relation_linear_algebra", "target_descent")]
        summands = item.get("point_decomposition", {}).get("summands")
        family = item.get("point_decomposition", {}).get("solver_family")
        check(stages[0] == f"PDP{summands}{family}", errors, where, "PDP stage code disagrees with summands or solver family")
        check(all(re.fullmatch(prefix + r"[a-z0-9]+", code) for prefix, code in
                  zip(("PDP", "RC", "LA", "TD"), stages)), errors, where, "invalid stage code")
        count = fb.get("actual_usable_point_count")
        check(type(count) is int and count > 0, errors, where, "fb count must be an actual positive integer")
        check(fb.get("curve_id") == cid, errors, where, "factor-base curve ID differs from candidate curve")
        check(isinstance(fb.get("enumerated_set_sha256"), str) and
              bool(HEX64.fullmatch(fb["enumerated_set_sha256"])), errors, where,
              "factor-base point-set digest is missing")
        if type(count) is int:
            check((cid, fb.get("enumerated_set_sha256"), str(count)) in indexed, errors, where,
                  "factor base is absent from archive or its actual point count disagrees")
        route = item.get("isogeny")
        iso = "0" if route == "none" else "1"
        if iso == "1":
            route_id = route.get("route_id") if isinstance(route, dict) else None
            check(route_id in routes and routes[route_id].get("status") == "verified", errors, where,
                  "ISO1 needs a verified route ID")
        prefix = f"IC1{m[1]}C{m[2]}fb{count}{''.join(stages)}ISO{iso}h" if m else ""
        suffix = path.stem[len(prefix):] if path.stem.startswith(prefix) else ""
        check(bool(prefix) and 12 <= len(suffix) <= 64 and bool(re.fullmatch(r"[0-9a-f]+", suffix))
              and digest(item).startswith(suffix), errors, where,
              "IC1 name disagrees with stages, actual base size, or canonical hash")
        implementation = item.get("implementation", {}).get("sources_sha256", {})
        check(bool(implementation) and all(isinstance(v, str) and bool(HEX64.fullmatch(v))
                                               for v in implementation.values()), errors, where,
              "implementation needs source SHA-256 digests")
    for path in sorted((base / "workloads").glob("*.json")):
        where = str(path.relative_to(root))
        item = read_json(path)
        check(12 <= len(path.stem) <= 64 and bool(re.fullmatch(r"[0-9a-f]+", path.stem))
              and digest(item).startswith(path.stem), errors, where,
              "workload filename disagrees with canonical hash")
        check(item.get("curve_id") in candidate_curves, errors, where, "workload curve has no archived IC1 candidate")
        check(type(item.get("target_count")) is int and item["target_count"] == len(item.get("targets", [])),
              errors, where, "target_count differs from stored targets")


def validate(root: Path, peer: Path | None = None) -> list[str]:
    errors: list[str] = []
    ca = root / "experiments/ic-candidate-catalog"
    crypto = root / "docs/curves/ic"
    directory = ca if ca.is_dir() else crypto
    if not directory.is_dir():
        return [f"{root}: neither IC curve registry layout exists"]
    lock = read_json(directory / "mirror-lock.json")
    for name in PINNED:
        file = directory / name
        actual = hashlib.sha256(file.read_bytes()).hexdigest()
        check(lock.get(name) == actual, errors, name, "mirror-lock SHA-256 differs from file")
    if peer is not None:
        for name in PEER_FILES:
            file = directory / name
            other = peer / ("docs/curves/ic" if directory == ca else "experiments/ic-candidate-catalog") / name
            check(other.exists() and file.read_bytes() == other.read_bytes(), errors, name,
                  "peer repository mirror differs")
    by_uid, by_ref, _ = validate_registry(directory, errors)
    validate_links(directory, by_uid, errors)
    if directory == ca:
        routes = validate_routes(directory, by_ref, errors)
        validate_candidates(root, routes, errors)
    else:
        registry = read_json(root / "docs/curves/registry.json")
        identities = {record["slug"]: record for record in registry.get("curves", [])}
        for uid, entry in by_uid.items():
            crosswalk = entry.get("icv1_identity", {})
            slug = crosswalk.get("slug")
            if slug is not None:
                record = identities.get(slug)
                check(record is not None and record.get("icv1") == crosswalk.get("full"), errors, uid,
                      "ICV1 crosswalk does not match crypto registry")
                if crosswalk.get("status") == "registered_representation" and record is not None:
                    check(any(rep.get("curve_uid") == uid for rep in record.get("representations", [])),
                          errors, uid, "registered ICV1 representation does not contain this exact curve UID")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2] if
                        "experiments" in Path(__file__).parts else Path(__file__).resolve().parents[3])
    parser.add_argument("--peer", type=Path, help="compare the three mirrored files with a local peer checkout")
    args = parser.parse_args()
    try:
        errors = validate(args.root.resolve(), args.peer.resolve() if args.peer else None)
    except (OSError, ValueError, KeyError, jsonschema.SchemaError) as exc:
        errors = [f"invalid metadata: {exc}"]
    for error in errors:
        print(error, file=sys.stderr)
    print(f"IC semantic metadata: {'FAIL' if errors else 'PASS'} ({len(errors)} errors)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
