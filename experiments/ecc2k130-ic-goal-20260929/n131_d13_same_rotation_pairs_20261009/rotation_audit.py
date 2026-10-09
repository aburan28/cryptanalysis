#!/usr/bin/env sage -python
"""Verify one cached pair inverse transports to every proposed Frobenius pair."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
STATIC = GOAL / "n131_phi_torsion_frobenius_domains_20261005/m12_d13_static"
CODEGEN = GOAL.parents[1] / "ecc2k130/codegen"
sys.path.insert(0, str(CODEGEN))
import curves
import field
import audit


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seed(onb, basis, code):
    mask = 0
    for bit in range(13):
        if (code >> bit) & 1:
            mask ^= basis[bit]
    return onb.fromCoords(mask)


def phi_mask(onb, point):
    if point is None or point[0] == onb.one():
        return None
    return onb.toCoords(onb.inv(onb.add(point[0], onb.one())))


def main():
    output = HERE / "rotation_audit.json"
    if output.exists():
        raise FileExistsError(output)
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    geometry = json.loads((STATIC / "d13_exact_geometry_v1.json").read_text())
    if (result["status"] != "PASS_EXACT_PAIR_INVERSE_CONTROLS" or
            result["source_sha256"]["protocol"] != sha(HERE / "protocol.json") or
            result["source_sha256"]["pivots"] != sha(HERE / "pivots.bin")):
        raise ValueError("frozen pair index changed")
    basis = [int(value, 16)
             for value in geometry["domain"]["basis_coordinate_masks_hex"]]
    onb = field.Onb(131)
    curve = curves.Curve(onb)
    pivots = audit.read_index(HERE / "pivots.bin")
    rotations = sorted(set(protocol["rotation_schedule"]))
    if rotations != [0, 22, 44, 66, 88, 110]:
        raise ValueError("six-pair rotation schedule changed")
    checks = 0
    for rotation in rotations:
        for item in result["positive_controls"][:8]:
            a, b = item["codes"]
            z_mask = item["output_phi_mask"]
            points = [curve.pointFromX(onb.add(onb.inv(seed(onb, basis, code)),
                                                 onb.one()))
                      for code in (a, b)]
            choices = [curve.add(points[0], points[1]),
                       curve.add(points[0], curve.neg(points[1]))]
            source = next(point for point in choices
                          if phi_mask(onb, point) == z_mask)
            rotated = curve.frob(source, rotation)
            rotated_mask = phi_mask(onb, rotated)
            unrotated_mask = onb.toCoords(onb.frob(
                onb.fromCoords(rotated_mask), 131 - rotation))
            if unrotated_mask != z_mask:
                raise ValueError("pair output Frobenius normalization changed")
            rotated_leaves = [curve.frob(point, rotation) for point in points]
            rotated_choices = {
                phi_mask(onb, curve.add(rotated_leaves[0], rotated_leaves[1])),
                phi_mask(onb, curve.add(rotated_leaves[0],
                                       curve.neg(rotated_leaves[1])))}
            if rotated_mask not in rotated_choices:
                raise ValueError("rotated output escapes signed pair roots")
            s = a ^ b
            z = onb.fromCoords(unrotated_mask)
            factor = audit.t(onb, z)
            right = onb.mul(onb.sqr(onb.add(seed(onb, basis, s), z)),
                            onb.inv(factor))
            recovered = audit.solve_rows(pivots[s], onb.toCoords(right))
            if recovered is None or {recovered, recovered ^ s} != {a, b}:
                raise ValueError("cached inverse lost a rotated positive pair")
            checks += 1
    receipt = {"kind": "n131_d13_same_rotation_pair_transport_audit",
               "status": "PASS_ALL_SIX_PAIR_ROTATIONS",
               "checked_rotations": rotations,
               "checked_positive_cases": checks,
               "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                                 "result": sha(HERE / "result.json"),
                                 "pivots": sha(HERE / "pivots.bin"),
                                 "audit": sha(Path(__file__))}}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"], "cases": checks}))


if __name__ == "__main__":
    main()
