#!/usr/bin/env sage -python
"""Enumerate complete first-link phi roots for the two frozen leaf cubes."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE.parent / "n131_phi_torsion_frobenius_domains_20261005/"
          "d13_m12_probe")
sys.path.insert(0, str(SOURCE))
import run_public_q_first_relation as runner


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def leaf(onb, curve, basis, code, position):
    mask = 0
    for bit, value in enumerate(basis):
        if (code >> bit) & 1:
            mask ^= value
    phi = onb.frob(onb.fromCoords(mask), position)
    if phi == onb.zero():
        raise ValueError("zero leaf phi")
    point = curve.pointFromX(onb.add(onb.inv(phi), onb.one()))
    if point is None:
        raise ValueError("pinned code is not a curve point")
    return phi, point


def main():
    output = HERE / "first_link_candidates.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    runtime_path = HERE / "runtime_info.json"
    if json.loads(runtime_path.read_text())["status"] != "verified":
        raise ValueError("checked Sage runtime is unverified")
    geometry_path = runner.GEOMETRY
    geometry = json.loads(geometry_path.read_text())
    basis = [int(value, 16) for value in
             geometry["domain"]["basis_coordinate_masks_hex"]]
    if len(basis) != 13 or protocol["pinned_positions"] != [0, 1]:
        raise ValueError("wrong first-link domain")
    onb = runner.field.Onb(131)
    curve = runner.curves.Curve(onb)
    cube_rows = []
    for index, cube in enumerate(protocol["cubes"]):
        codes = cube["leaf_codes"]
        phi0, p0 = leaf(onb, curve, basis, codes[0], 0)
        phi1, p1 = leaf(onb, curve, basis, codes[1], 1)
        y0 = onb.add(onb.sqr(phi0), phi0)
        y1 = onb.add(onb.sqr(phi1), phi1)
        a = onb.mul(y0, y1)
        if onb.add(a, onb.one()) == onb.zero():
            raise ValueError("first-link quadratic lost degree")
        candidates = {}
        for relative_sign in (0, 1):
            second = p1 if relative_sign == 0 else curve.neg(p1)
            summed = curve.add(p0, second)
            if summed is None or summed[0] == onb.one():
                raise ValueError("exceptional first-link output")
            phi = onb.inv(onb.add(summed[0], onb.one()))
            total = onb.add(onb.add(phi0, phi1), phi)
            equation = onb.add(onb.mul(a, onb.add(onb.sqr(phi), phi)),
                               onb.sqr(total))
            if equation != onb.zero():
                raise ValueError("curve sum fails the exact first-link S3 equation")
            mask = onb.toCoords(phi)
            candidates[mask] = relative_sign
        if len(candidates) != 2:
            raise ValueError("first-link quadratic did not have two distinct roots")
        cube_rows.append({"cube": index, "leaf_codes": codes,
                          "partial0_phi_masks": sorted(candidates),
                          "relative_sign_by_mask": {str(k): v for k, v in candidates.items()},
                          "quadratic_degree": 2,
                          "all_roots_from_curve_group_addition": True,
                          "both_roots_pass_exact_s3": True})
    record = {
        "kind": "n131_d13_two_leaf_first_link_exact_phi_roots",
        "status": "PASS_TWO_COMPLETE_ROOTS_PER_CUBE",
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None, "run_id": None,
        "target_count": 1, "cubes": cube_rows,
        "source_sha256": {"protocol": sha(protocol_path),
                          "geometry": sha(geometry_path),
                          "runtime": sha(runtime_path),
                          "script": sha(Path(__file__))},
    }
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": record["status"],
                      "roots": [row["partial0_phi_masks"] for row in cube_rows]}))


if __name__ == "__main__":
    main()
