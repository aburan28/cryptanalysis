#!/usr/bin/env sage -python
"""Replay the affine-span witnesses with Sage's independent EC arithmetic."""

import hashlib
import json
import sys
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, matrix

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
CODEGEN = GOAL.parents[1] / "ecc2k130/codegen"
sys.path.insert(0, str(CODEGEN))
import curves
import field


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "sage_group_audit.json"
    if output.exists():
        raise FileExistsError("preserve independent Sage group audit")
    result_path = HERE / "result.json"
    protocol_path = HERE / "protocol.json"
    geometry_path = (GOAL / "n131_phi_torsion_frobenius_domains_20261005"
                     / "m12_d13_static/d13_exact_geometry_v1.json")
    result = json.loads(result_path.read_text())
    protocol = json.loads(protocol_path.read_text())
    geometry = json.loads(geometry_path.read_text())
    if (result["status"] != "PASS_FULL_AFFINE_SPAN_CERTIFICATE" or
            result["source_sha256"]["protocol"] != sha(protocol_path) or
            result["source_sha256"]["geometry"] != sha(geometry_path)):
        raise ValueError("source-bound span certificate changed")
    n = 131
    R = PolynomialRing(GF(2), "t")
    t = R.gen()
    F = GF(2**n, name="t", modulus=t**n + t**13 + t**2 + t + 1)
    zeta = F.multiplicative_generator() ** ((2**n - 1) // 263)
    if zeta == 1 or zeta**263 != 1:
        raise ValueError("Sage 263rd-root embedding failed")
    gamma = [zeta**i + zeta**(-i) for i in range(1, n + 1)]
    if matrix(GF(2), [[int(x) for x in g.polynomial().list()] +
                      [0] * (n - len(g.polynomial().list())) for g in gamma]).rank() != n:
        raise ValueError("Sage normal basis is incomplete")

    def sage_from_mask(mask):
        value = F.zero()
        while mask:
            bit = mask & -mask
            value += gamma[bit.bit_length() - 1]
            mask ^= bit
        return value

    onb = field.Onb(n)
    native_curve = curves.Curve(onb)
    E = EllipticCurve(F, [1, 0, 0, 0, 1])
    if sage_from_mask(onb.toCoords(onb.one())) != F.one():
        raise ValueError("normal-basis identity mismatch")
    basis_masks = [int(value, 16) for value in
                   geometry["domain"]["basis_coordinate_masks_hex"]]
    rows = []
    checked_points = set()
    for witness in result["witnesses"]:
        sage_points = []
        for code in witness["codes"]:
            phi_mask = 0
            for bit, basis_mask in enumerate(basis_masks):
                if (code >> bit) & 1:
                    phi_mask ^= basis_mask
            phi_native = onb.fromCoords(phi_mask)
            x_native = onb.add(onb.inv(phi_native), onb.one())
            native_point = native_curve.pointFromX(x_native)
            if native_point is None:
                raise ValueError("saved leaf has no point lift")
            point = E(sage_from_mask(onb.toCoords(native_point[0])),
                      sage_from_mask(onb.toCoords(native_point[1])))
            if 4 * point == E(0):
                raise ValueError("saved leaf does not project into factor base")
            sage_points.append(point)
            checked_points.add(code)
        summed = sage_points[0] + sage_points[1]
        if summed == E(0) or summed[0] == 1:
            raise ValueError("exceptional saved pair sum")
        expected_phi = sage_from_mask(witness["output_phi_mask"])
        if 1 / (summed[0] + 1) != expected_phi:
            raise ValueError("Sage EC addition disagrees with output mask")
        row = 1 | (witness["output_phi_mask"] << 1)
        rows.append([(row >> bit) & 1 for bit in range(132)])
    rank = int(matrix(GF(2), rows).rank())
    if rank != 132:
        raise ValueError("independent affine rank below 132")
    receipt = {"kind": "n131_d13_pair_output_sage_ec_audit",
               "status": "PASS_SAGE_EC_AND_AFFINE_RANK",
               "sage_affine_rank": rank,
               "witness_pairs_checked": len(rows),
               "distinct_leaf_selectors_checked": len(checked_points),
               "source_sha256": {"auditor": sha(Path(__file__)),
                                 "protocol": sha(protocol_path),
                                 "result": sha(result_path),
                                 "geometry": sha(geometry_path)}}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "sage_affine_rank", "witness_pairs_checked")}))


if __name__ == "__main__":
    main()
