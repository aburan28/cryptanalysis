#!/usr/bin/env python3
"""Check that the catalog's verified edge matches its frozen map artifacts."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / "ecc2k130_degree263_route_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["source_sha256"] == file_sha(
        HERE / "build_ecc2k130_263_route_manifest.py")
    field = manifest["field"]
    for tag, role in (("kb1", "source"), ("bin", "target")):
        curve = dict(manifest["curve_nodes"][role])
        curve_id = curve.pop("curve_id")
        assert curve_id == "EC1N131C" + tag + "h" + digest({
            "field": field, "curve": curve})[:12]
    assert manifest["route_id"] == "IW1E263d1h" + digest(
        manifest["route_identity_record"])[:12]
    assert manifest["candidate_id"] is None
    assert manifest["evidence"]["forward_report_sha256"] == file_sha(
        HERE / "ecc2k130_degree263_isogeny_control.json")
    assert manifest["evidence"]["dual_report_sha256"] == file_sha(
        HERE / "ecc2k130_degree263_dual_control.json")
    assert manifest["evidence"]["independent_replay_sha256"] == file_sha(
        HERE / "ecc2k130_degree263_isogeny_sage_replay.json")
    assert manifest["evidence"]["exceptional_replay_sha256"] == file_sha(
        HERE / "ecc2k130_degree263_exceptional_replay.json")
    assert manifest["evidence"]["exceptional_runtime_info_sha256"] == file_sha(
        HERE / "ecc2k130_degree263_exceptional_runtime_info.json")
    replay = json.loads((HERE / "ecc2k130_degree263_isogeny_sage_replay.json").read_text())
    assert replay["cyclic_kernel_check"]
    assert replay["dual_composition_on_two_points"]
    for name, script in (("ecc2k130_degree263_isogeny_control.json",
                          "sage_construct_ecc2k130_263_isogeny.py"),
                         ("ecc2k130_degree263_dual_control.json",
                          "sage_construct_ecc2k130_263_dual.py"),
                         ("ecc2k130_degree263_isogeny_sage_replay.json",
                          "sage_replay_ecc2k130_263_isogeny.py")):
        assert json.loads((HERE / name).read_text())["source_sha256"] == file_sha(
            HERE / script)
    exceptional = json.loads((HERE / "ecc2k130_degree263_exceptional_replay.json").read_text())
    assert exceptional["status"] == "verified" and exceptional["candidate_id"] is None
    assert exceptional["forward_nonzero_kernel_points_mapped_to_infinity"] == 262
    assert exceptional["dual_nonzero_kernel_points_mapped_to_infinity"] == 262
    assert exceptional["all_kernel_roots_have_no_base_field_y_lift"]
    assert exceptional["rational_order_two_composition"]
    assert exceptional["ordinary_subgroup_wrapper_and_dual_composition"]
    assert exceptional["ordinary_quadratic_extension_wrapper_agrees"]
    assert exceptional["forward_report_sha256"] == manifest["evidence"]["forward_report_sha256"]
    assert exceptional["dual_report_sha256"] == manifest["evidence"]["dual_report_sha256"]
    assert exceptional["source_sha256"] == file_sha(
        HERE / "sage_verify_ecc2k130_263_exceptional.py")
    assert exceptional["transport_source_sha256"] == file_sha(
        HERE / "degree263_transport.py")

    registry = json.loads((ROOT / "experiments/ic-candidate-catalog/isogeny_routes.json").read_text())
    route = next(route for route in registry["routes"]
                 if route["id"] == manifest["route_id"])
    assert route["status"] == "verified"
    assert len(route["edge_ids"]) == 1
    edge = next(edge for edge in registry["edges"]
                if edge["id"] == route["edge_ids"][0])
    assert edge["id"] == manifest["edge_id"]
    assert manifest["route_identity_record"]["ordered_edges"][0]["edge_id"] == edge["id"]
    assert edge["status"] == "verified" and edge["degree"] == 263
    assert edge["map_artifact_ref"] == str(manifest_path.relative_to(ROOT))
    assert edge["explicit_map_sha256"] == digest(manifest["isogeny"]["forward_map"])
    assert edge["kernel_certificate_sha256"] == digest(
        manifest["isogeny"]["kernel_certificate"])
    assert edge["subgroup_transport_certificate_sha256"] == digest(
        manifest["isogeny"]["subgroup_transport_certificate"])
    nodes = {node["ref"]: node for node in registry["curve_nodes"]}
    assert nodes[edge["source_curve_ref"]]["curve_id"] == manifest[
        "curve_nodes"]["source"]["curve_id"]
    assert nodes[edge["target_curve_ref"]]["curve_id"] == manifest[
        "curve_nodes"]["target"]["curve_id"]
    assert nodes[edge["source_curve_ref"]]["proved_volcano_levels"]["263"] == 0
    assert nodes[edge["target_curve_ref"]]["proved_volcano_levels"]["263"] == 1
    print(json.dumps({"route_id": route["id"], "verified_edge": edge["id"],
                      "curve_ids": [manifest["curve_nodes"][role]["curve_id"]
                                    for role in ("source", "target")],
                      "artifact_hashes_match": True}, indent=2))


if __name__ == "__main__":
    main()
