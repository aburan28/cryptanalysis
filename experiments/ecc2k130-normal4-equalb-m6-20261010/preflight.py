#!/usr/bin/env python3
"""Check the frozen Q1420/Q1421 source identities without deriving queries."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strict_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate JSON key")
    return result


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(), object_pairs_hook=strict_pairs)


def validate(config: dict) -> dict:
    bound = {}
    for name, record in config["bound_inputs"].items():
        path = ROOT / record["path"]
        actual = sha256(path)
        if actual != record["sha256"]:
            raise ValueError(f"bound source changed: {name}")
        bound[name] = load_json(path)

    q1421 = bound["q1421_producer"]
    q1421_replay = bound["q1421_verification"]
    q1421_manifest = bound["q1421_manifest"]
    q1420 = bound["q1420_config"]
    q1420_base = bound["q1420_base_selection"]
    q1420_replay = bound["q1420_verification"]
    primary = bound["q1420_primary_workload"]
    route = bound["route_manifest"]
    equal = config["equal_base"]
    if (q1421_manifest["status"] != "PASS_FULL_SAGE_ORBIT_AND_POINT_REPLAY"
            or q1421_replay["status"] != "PASS_FULL_SAGE_ORBIT_AND_POINT_REPLAY"
            or q1421_manifest["paths_and_sha256"]["producer_receipt"]["sha256"]
            != config["bound_inputs"]["q1421_producer"]["sha256"]
            or q1421_replay["producer_result_sha256"]
            != config["bound_inputs"]["q1421_producer"]["sha256"]
            or q1421_replay["observed"]["actual_usable_points_B"]
            != q1421["actual_usable_points_B"]
            or q1421_replay["observed"]["signed_frobenius_columns_K"]
            != q1421["signed_frobenius_columns_K"]
            or q1421["actual_usable_points_B"] != equal["actual_usable_points_B"]
            or q1421["sign_folded_columns_C"] != equal["signed_classes_each"]
            or q1421["rational_orbits"] != equal["normal4_rational_orbits"]
            or q1421["reciprocal_partner_orbits"]
            != equal["normal4_reciprocal_partner_orbits"]
            or q1421["signed_frobenius_columns_K"]
            != equal["normal4_potential_signed_frobenius_columns"]):
        raise ValueError("Q1421 count or independent replay mismatch")
    if (q1420_replay["status"] != "PASS_EXACT_BASE_ROUTE_AND_PUBLIC_FIXTURES"
            or q1420_base["source"]["selected_usable_points_B"]
            != q1420_base["descendant_native"]["selected_usable_points_B"]
            or q1420_base["source"]["selected_usable_points_B"]
            < equal["actual_usable_points_B"]):
        raise ValueError("Q1420 base or route replay mismatch")
    if equal["actual_usable_points_B"] != 2 * equal["signed_classes_each"]:
        raise ValueError("wrong equal-B sign accounting")
    for name in ("source", "descendant_native"):
        archive = config["w24_archives"][name]
        path = ROOT / archive["path"]
        if (sha256(path) != archive["gzip_sha256"]
                or archive["full_signed_classes"] < equal["signed_classes_each"]
                or archive["full_signed_classes"]
                != (q1420["source_full_signed_columns"] if name == "source"
                    else q1420["descendant_full_signed_columns"])):
            raise ValueError(f"W24 archive mismatch: {name}")
    target = config["primary_target"]
    if (primary["target_count"] != 1 or target["target_count"] != 1
            or primary["workload_id"] != target["workload_id"]):
        raise ValueError("primary one-target workload mismatch")
    canonical = dict(primary)
    canonical.pop("workload_id")
    workload_digest = hashlib.sha256(json.dumps(
        canonical, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode()).hexdigest()[:12]
    if workload_digest != target["workload_id"]:
        raise ValueError("primary workload ID does not match its record")
    if (route["route_id"] != config["route_id"]
            or q1420["route_id"] != config["route_id"]
            or q1420["route_manifest_sha256"]
            != config["bound_inputs"]["route_manifest"]["sha256"]
            or q1420["source_curve_id"] != config["source_curve_id"]
            or q1420["descendant_curve_id"] != config["descendant_curve_id"]
            or str(primary["subgroup_order"]) != config["subgroup_order"]):
        raise ValueError("curve, subgroup, or oriented route mismatch")
    return {
        "status": "PASS_FROZEN_INPUT_PREFLIGHT",
        "q1421_B": q1421["actual_usable_points_B"],
        "q1421_K": q1421["signed_frobenius_columns_K"],
        "w24_prefix_signed_classes": equal["signed_classes_each"],
        "primary_workload_id": primary["workload_id"],
        "archive_gzip_sha256": {
            name: config["w24_archives"][name]["gzip_sha256"]
            for name in ("source", "descendant_native")
        },
        "config_sha256": sha256(CONFIG),
    }


def main() -> None:
    result = validate(load_json(CONFIG))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
