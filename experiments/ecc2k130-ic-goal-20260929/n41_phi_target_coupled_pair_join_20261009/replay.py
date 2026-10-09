#!/usr/bin/env sage -python
"""Independent point, subgroup, and full XCNF replay of one N41 join row."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BASE = GOAL / "n41_phi_second_link_control_20261009"
TEMPLATE = GOAL / "n131_phi_torsion_frobenius_domains_20261005/m16_static"
sys.path.insert(0, str(TEMPLATE))
import phi_frobenius_sat_gate_m16_sparse_seed_v1 as template


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def point_from_code(onb, curve, basis, code, position, sign):
    mask = 0
    for bit, value in enumerate(basis):
        if (code >> bit) & 1:
            mask ^= value
    phi = onb.frob(onb.fromCoords(mask), position)
    x = onb.add(onb.inv(phi), onb.one())
    point = curve.pointFromX(x)
    if point is None:
        raise ValueError("witness leaf lacks a curve point")
    return curve.neg(point) if sign else point


def phi_mask(onb, point):
    if point is None or point[0] == onb.one():
        raise ValueError("witness chain has undefined phi coordinate")
    return onb.toCoords(onb.inv(onb.add(point[0], onb.one())))


def main():
    output = HERE / "replay.json"
    if output.exists():
        raise FileExistsError(output)
    result_path, protocol_path = HERE / "result.json", HERE / "protocol.json"
    result = json.loads(result_path.read_text())
    protocol = json.loads(protocol_path.read_text())
    source = json.loads((BASE / "protocol.json").read_text())
    table = json.loads((BASE / "table.json").read_text())
    witness = result["witness"]
    if (result["status"] != "VERIFIED_ORDINARY_RELATION" or witness is None or
            result["source_sha256"]["protocol"] != sha(protocol_path) or
            protocol["source_sha256"]["source_protocol"] != sha(BASE / "protocol.json") or
            protocol["source_sha256"]["source_table"] != sha(BASE / "table.json") or
            protocol["source_sha256"]["run_join"] != sha(HERE / "run_join.py") or
            len(witness["slot_code_sign"]) != 12 or
            len(witness["slot_indices"]) != 12 or
            len(witness["raw_points"]) != 12):
        raise ValueError("frozen successful witness or sources changed")
    template.N, template.DIM, template.M = 41, 6, 12
    onb = template.field.Onb(41)
    curve = template.curves.Curve(onb)
    basis = table["basis_coordinate_masks"]
    valid_codes = set(table["valid_codes"])
    target = tuple(onb.fromCoords(value) for value in source["target_coordinates"])
    endpoint = curve.mul(target, pow(4, -1, source["subgroup_order"]))
    if endpoint != tuple(onb.fromCoords(value)
                         for value in source["endpoint_coordinates"]):
        raise ValueError("target endpoint changed")
    points = []
    codes = []
    signs = []
    for position, (code, sign) in enumerate(witness["slot_code_sign"]):
        slot = witness["slot_indices"][position]
        if (code not in valid_codes or sign not in (0, 1) or slot < 0 or
                slot >= 60 or
                [table["valid_codes"][slot // 2], slot % 2] != [code, sign]):
            raise ValueError("witness selector escapes frozen slot domain")
        point = point_from_code(onb, curve, basis, code, position, sign)
        if (not curve.onCurve(point) or
                [onb.toCoords(value) for value in point] !=
                witness["raw_points"][position]):
            raise ValueError("saved witness point differs from exact leaf")
        subgroup_point = curve.mul(point, 4)
        if subgroup_point is None or curve.mul(subgroup_point, source["subgroup_order"]) is not None:
            raise ValueError("witness leaf is not subgroup usable")
        points.append(point)
        codes.append(code)
        signs.append(sign)
    if (codes[:2] != table["first_link_leaf_codes"] or
            len({point[0] for point in points}) != 12):
        raise ValueError("witness violates first-link branch or distinct x")
    running = None
    partials = []
    for position, point in enumerate(points):
        running = curve.add(running, point)
        if 1 <= position < 11:
            partials.append(phi_mask(onb, running))
    if (running != endpoint or curve.mul(running, 4) != target or
            partials[0] != table["selected_first_link_root"] or
            len(partials) != 10 or
            partials[1] not in next(row[1:] for row in table["rows"]
                                    if row[0] == codes[2])):
        raise ValueError("independent group/second-link replay failed")
    endpoint_phi = phi_mask(onb, running)
    if endpoint_phi != source["endpoint_phi_mask"]:
        raise ValueError("source public endpoint phi changed")
    formula, primary, roots, prog, node_lits, linear = template.build_formula(
        onb, basis, table["valid_codes"], [endpoint_phi] * 4)
    pins = {f"leaf{position}": [(codes[position] >> bit) & 1
                                for bit in range(6)] for position in range(12)}
    pins.update({f"partial{position}": [(mask >> bit) & 1
                 for bit in range(41)] for position, mask in enumerate(partials)})
    pins["endpoint"] = [0, 0]
    assignment = template.evaluate_and_check(formula, primary, pins, prog,
                                             node_lits, linear)
    if (len(roots) != 11 * 41 or
            not all(value is not None for value in assignment[1:])):
        raise ValueError("public-target XCNF witness is incomplete")
    receipt = {"kind": "n41_phi_join_independent_group_and_xcnf_replay",
               "status": "PASS_ORDINARY_RELATION_AND_PUBLIC_XCNF",
               "target_count": 1, "candidate_id": None, "run_id": None,
               "leaf_codes": codes, "leaf_signs": signs,
               "partial_phi_masks": partials,
               "checked_formula_variables": formula.nVars,
               "checked_formula_clauses": len(formula.clauses),
               "checked_formula_xors": len(formula.xors),
               "source_sha256": {"result": sha(result_path),
                                 "protocol": sha(protocol_path),
                                 "source_protocol": sha(BASE / "protocol.json"),
                                 "source_table": sha(BASE / "table.json"),
                                 "replay": sha(Path(__file__))}}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"], "leaf_codes": codes,
                      "leaf_signs": signs}))


if __name__ == "__main__":
    main()
