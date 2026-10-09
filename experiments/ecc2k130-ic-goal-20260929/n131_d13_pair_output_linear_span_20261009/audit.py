#!/usr/bin/env sage -python
"""Independent Sage point and GF(2) rank replay of the saved witness."""

import hashlib
import json
import sys
from pathlib import Path

from sage.all import GF, matrix

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
STATIC = GOAL / "n131_phi_torsion_frobenius_domains_20261005/m12_d13_static"
CODEGEN = GOAL.parents[1] / "ecc2k130/codegen"
sys.path.insert(0, str(CODEGEN))
import curves
import field


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError("preserve independent span audit")
    protocol_path = HERE / "protocol.json"
    result_path = HERE / "result.json"
    protocol = json.loads(protocol_path.read_text())
    result = json.loads(result_path.read_text())
    geometry_path = STATIC / "d13_exact_geometry_v1.json"
    paired = GOAL / "n131_d13_same_rotation_pairs_20261009"
    sources = {"producer": HERE / "produce.py",
               "runtime": HERE / "runtime_info.json",
               "geometry": geometry_path,
               "valid_codes": paired / "valid_codes.json",
               "pair_result": paired / "result.json",
               "pair_source": paired / "run.py",
               "field": CODEGEN / "field.py",
               "curves": CODEGEN / "curves.py"}
    if (result["source_sha256"]["protocol"] != sha(protocol_path) or
            any(sha(path) != protocol["source_sha256"][key] or
                sha(path) != result["source_sha256"][key]
                for key, path in sources.items()) or
            result["status"] != "PASS_FULL_AFFINE_SPAN_CERTIFICATE"):
        raise ValueError("producer inputs or terminal status mismatch")
    geometry = json.loads(geometry_path.read_text())
    basis = [int(value, 16) for value in
             geometry["domain"]["basis_coordinate_masks_hex"]]
    valid = set(json.loads(sources["valid_codes"].read_text()))
    onb = field.Onb(131)
    curve = curves.Curve(onb)
    rows = []
    checked = set()
    for witness in result["witnesses"]:
        codes = witness["codes"]
        if (len(codes) != 2 or codes[0] >= codes[1] or
                any(code not in valid for code in codes)):
            raise ValueError("invalid saved pair selector")
        points = []
        for code in codes:
            value = onb.zero()
            for bit, basis_mask in enumerate(basis):
                if (code >> bit) & 1:
                    value = onb.add(value, onb.fromCoords(basis_mask))
            point = curve.pointFromX(onb.add(onb.inv(value), onb.one()))
            if point is None or curve.mul(point, 4) is None:
                raise ValueError("point outside usable subgroup base")
            points.append(point)
            checked.add(code)
        group_sum = curve.add(points[0], points[1])
        if group_sum is None or group_sum[0] == onb.one():
            raise ValueError("exceptional saved group output")
        mask = onb.toCoords(onb.inv(onb.add(group_sum[0], onb.one())))
        if mask != witness["output_phi_mask"]:
            raise ValueError("saved output differs from exact group sum")
        augmented = 1 | (mask << 1)
        rows.append([(augmented >> bit) & 1 for bit in range(132)])
    rank = int(matrix(GF(2), rows).rank())
    if rank != len(rows) or rank != 132:
        raise ValueError("affine-span certificate failed independent GF(2) rank")
    receipt = {
        "kind": "n131_d13_pair_output_affine_span_independent_audit",
        "status": "PASS_FULL_AFFINE_SPAN_AND_GROUP_REPLAY",
        "curve_id": protocol["curve_id"],
        "independent_rank": rank,
        "witness_rows_replayed": len(rows),
        "distinct_leaf_selectors_checked": len(checked),
        "source_sha256": {"audit": sha(Path(__file__)),
                          "protocol": sha(protocol_path),
                          "result": sha(result_path),
                          "geometry": sha(geometry_path)},
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "independent_rank", "witness_rows_replayed")}))


if __name__ == "__main__":
    main()
