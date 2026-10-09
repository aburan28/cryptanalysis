#!/usr/bin/env sage -python
"""Prove the two-leaf suffix maps to partial8 on a planted full chain."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BASE = GOAL / "n41_phi_second_link_control_20261009"
TEMPLATE = (GOAL / "n131_phi_torsion_frobenius_domains_20261005/"
            "m16_static")
sys.path.insert(0, str(TEMPLATE))
import phi_frobenius_sat_gate_m16_sparse_seed_v1 as template

N, DIM, M = 41, 6, 12


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def leaf(onb, curve, basis, code, position):
    mask = 0
    for bit, value in enumerate(basis):
        if (code >> bit) & 1:
            mask ^= value
    phi = onb.frob(onb.fromCoords(mask), position)
    point = curve.pointFromX(onb.add(onb.inv(phi), onb.one()))
    if point is None:
        raise ValueError("planted selector has no curve point")
    return point


def phi_mask(onb, point):
    if point is None or point[0] == onb.one():
        raise ValueError("nonfinite planted partial")
    return onb.toCoords(onb.inv(onb.add(point[0], onb.one())))


def main():
    output = HERE / "semantic_control.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path = HERE / "protocol.json"
    planted_path = BASE / "planted_control.json"
    table_path = BASE / "table.json"
    protocol = json.loads(protocol_path.read_text())
    planted = json.loads(planted_path.read_text())
    table = json.loads(table_path.read_text())
    if (protocol["status"] != "FROZEN" or
            planted["status"] != "PASS_FULL_PLANTED_XCNF_AND_LOOKUP_ROOT" or
            len(planted["leaf_codes"]) != M or len(planted["leaf_signs"]) != M or
            len(planted["partial_phi_masks"]) != M - 2):
        raise ValueError("frozen planted control changed")
    template.N, template.DIM, template.M = N, DIM, M
    onb = template.field.Onb(N)
    curve = template.curves.Curve(onb)
    basis = table["basis_coordinate_masks"]
    signed_points = []
    for position, (code, sign) in enumerate(zip(planted["leaf_codes"],
                                               planted["leaf_signs"])):
        point = leaf(onb, curve, basis, code, position)
        signed_points.append(point if sign == 0 else curve.neg(point))
    prefix = None
    for point in signed_points[:10]:
        prefix = curve.add(prefix, point)
    partial9 = curve.add(prefix, signed_points[10])
    endpoint = curve.add(partial9, signed_points[11])
    suffix = curve.add(signed_points[10], signed_points[11])
    residual = curve.add(endpoint, curve.neg(suffix))
    if (residual != prefix or
            phi_mask(onb, residual) != planted["partial_phi_masks"][8] or
            phi_mask(onb, partial9) != planted["partial_phi_masks"][9] or
            phi_mask(onb, endpoint) != planted["synthetic_endpoint_phi_mask"]):
        raise ValueError("two-leaf suffix does not land on partial8")
    _formula, primary, roots, _prog, _nodes, _linear = template.build_formula(
        onb, basis, table["valid_codes"],
        [planted["synthetic_endpoint_phi_mask"]] * 4)
    if (primary["partial8"] != list(range(402, 443)) or
            primary["partial9"] != list(range(443, 484)) or
            len(roots) != (M - 1) * N):
        raise ValueError("formula primary layout differs from chain semantics")
    receipt = {
        "kind": "n41_phi_suffix2_partial8_semantic_regression",
        "status": "PASS_SUFFIX_RESIDUAL_IS_PARTIAL8",
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None, "run_id": None,
        "planted_partial8_phi_mask": planted["partial_phi_masks"][8],
        "planted_partial9_phi_mask": planted["partial_phi_masks"][9],
        "residual_matches_first_ten_signed_leaves": True,
        "partial8_variables": primary["partial8"],
        "partial9_variables": primary["partial9"],
        "source_sha256": {"protocol": sha(protocol_path),
                          "planted_control": sha(planted_path),
                          "table": sha(table_path),
                          "script": sha(Path(__file__))},
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "partial8": receipt["planted_partial8_phi_mask"]}))


if __name__ == "__main__":
    main()
