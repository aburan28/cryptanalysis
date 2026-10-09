#!/usr/bin/env sage -python
"""Fold the verified N41 target equation into exact sign/Frobenius columns."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BASE = GOAL / "n41_phi_second_link_control_20261009"
CODEGEN = GOAL.parents[1] / "ecc2k130/codegen"
sys.path.insert(0, str(CODEGEN))
import curves
import field


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def point_from_code(onb, curve, basis, code, position, sign):
    mask = 0
    for bit, value in enumerate(basis):
        if (code >> bit) & 1:
            mask ^= value
    phi = onb.frob(onb.fromCoords(mask), position)
    point = curve.pointFromX(onb.add(onb.inv(phi), onb.one()))
    if point is None:
        raise ValueError("factor-base code lacks curve point")
    return curve.neg(point) if sign else point


def coords(onb, point):
    return tuple(onb.toCoords(value) for value in point)


def main():
    output = HERE / "factor_base_row.json"
    if output.exists():
        raise FileExistsError(output)
    source = json.loads((BASE / "protocol.json").read_text())
    table = json.loads((BASE / "table.json").read_text())
    replay = json.loads((HERE / "replay.json").read_text())
    if replay["status"] != "PASS_ORDINARY_RELATION_AND_PUBLIC_XCNF":
        raise ValueError("independent relation replay is absent")
    onb = field.Onb(41)
    curve = curves.Curve(onb)
    r = source["subgroup_order"]
    basis = table["basis_coordinate_masks"]
    canonical = {}
    full = set()
    for code in table["valid_codes"]:
        raw = point_from_code(onb, curve, basis, code, 0, 0)
        projected = curve.mul(raw, 4)
        if projected is None or curve.mul(projected, r) is not None:
            raise ValueError("factor-base point is not subgroup usable")
        orbit = []
        for shift in range(41):
            moved = curve.frob(projected, shift)
            orbit.extend((moved, curve.neg(moved)))
        if len(set(orbit)) != 82:
            raise ValueError("base orbit has unexpected size")
        for point in orbit:
            full.add(point)
        representative = min(orbit, key=lambda point: coords(onb, point))
        canonical[coords(onb, representative)] = representative
    keys = sorted(canonical)
    if not keys or len(full) != len(keys) * 82:
        raise ValueError("factor-base orbits overlap unexpectedly")
    eigenvalue = curves.frobeniusEigenvalue(curve, canonical[keys[0]], r)
    orbit_map = {}
    for key in keys:
        representative = canonical[key]
        for shift in range(41):
            moved = curve.frob(representative, shift)
            coefficient = pow(eigenvalue, shift, r)
            for point, signed in ((moved, coefficient),
                                  (curve.neg(moved), -coefficient % r)):
                if point in orbit_map:
                    raise ValueError("two folded columns share a point")
                orbit_map[point] = (key, signed)
    if len(orbit_map) != len(full):
        raise ValueError("folded orbit map omits a factor-base point")
    coefficients = {key: 0 for key in keys}
    for position, (code, sign) in enumerate(zip(replay["leaf_codes"],
                                               replay["leaf_signs"])):
        raw = point_from_code(onb, curve, basis, code, position, sign)
        projected = curve.mul(raw, 4)
        if projected not in orbit_map:
            raise ValueError("ordinary relation leaf escapes full factor base")
        key, coefficient = orbit_map[projected]
        coefficients[key] = (coefficients[key] + coefficient) % r
    nonzero = [(key, coefficient) for key, coefficient in coefficients.items()
               if coefficient]
    check = None
    for key, coefficient in nonzero:
        check = curve.add(check, curve.mul(canonical[key], coefficient))
    target = tuple(onb.fromCoords(value) for value in source["target_coordinates"])
    if check != target:
        raise ValueError("folded log equation does not sum to public target")
    receipt = {"kind": "n41_phi_full_base_and_target_row_geometry",
               "status": "PASS_EXACT_FOLDED_TARGET_EQUATION",
               "candidate_id": None, "run_id": None,
               "cofactor": 4, "subgroup_order": r,
               "base_policy": "30 valid d6 codes, all 41 Frobenius rotations, both curve signs, projected by four",
               "actual_factor_base_points_B": len(full),
               "effective_folded_columns_K": len(keys),
               "frobenius_eigenvalue_mod_r": eigenvalue,
               "relation_nonzero_columns": len(nonzero),
               "relation_coefficients": [[list(key), coefficient]
                                         for key, coefficient in nonzero],
               "source_sha256": {"source_protocol": sha(BASE / "protocol.json"),
                                 "source_table": sha(BASE / "table.json"),
                                 "replay": sha(HERE / "replay.json"),
                                 "script": sha(Path(__file__))}}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "B": len(full), "K": len(keys),
                      "row_nonzero_columns": len(nonzero)}))


if __name__ == "__main__":
    main()
