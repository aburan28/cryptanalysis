#!/usr/bin/env sage -python
"""Enumerate exact second-link outputs for both frozen first-link roots."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
PREVIOUS = GOAL / "n131_d13_first_link_branches_20261009"
ROOT_SOURCE = GOAL / "n131_d13_two_leaf_cubes_20261009"
PROBE = GOAL / "n131_phi_torsion_frobenius_domains_20261005/d13_m12_probe"
RAW = PROBE / "official_q_phi_fiber_d13_m12_v1.xcnf"
GEOMETRY = GOAL / "n131_phi_torsion_frobenius_domains_20261005/m12_d13_static/d13_exact_geometry_v1.json"
sys.path.insert(0, str(ROOT_SOURCE))
import first_link_candidates as first


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def valid_codes():
    forbidden = set()
    expected = set(range(28, 41))
    with RAW.open("rt", encoding="ascii") as stream:
        for line in stream:
            if line.startswith(("p", "c", "x")):
                continue
            fields = [int(item) for item in line.split()]
            if (len(fields) == 14 and fields[-1] == 0 and
                    {abs(item) for item in fields[:-1]} == expected):
                code = sum(1 << (abs(item) - 28) for item in fields[:-1]
                           if item < 0)
                forbidden.add(code)
    if len(forbidden) != 4058:
        raise ValueError("the exact third-leaf selector domain changed")
    return sorted(set(range(8192)) - forbidden)


def phi_of(onb, point):
    if point is None or point[0] == onb.one():
        return None
    return onb.inv(onb.add(point[0], onb.one()))


def main():
    protocol_path = HERE / "protocol.json"
    table_path = HERE / "table.json"
    if protocol_path.exists() or table_path.exists():
        raise FileExistsError("preserve the frozen table and protocol")
    previous_path = PREVIOUS / "protocol.json"
    previous = json.loads(previous_path.read_text())
    roots_path = ROOT_SOURCE / "first_link_candidates.json"
    roots = json.loads(roots_path.read_text())
    runtime_path = HERE / "runtime_info.json"
    runtime = json.loads(runtime_path.read_text())
    geometry = json.loads(GEOMETRY.read_text())
    if (runtime["status"] != "verified" or
            roots["status"] != "PASS_TWO_COMPLETE_ROOTS_PER_CUBE" or
            previous["target_count"] != 1 or
            previous["source_sha256"]["roots"] != sha(roots_path) or
            geometry["status"] != "PASS" or
            geometry["factor_base"]["distinct_nonidentity_signed_subgroup_options_per_position"] != 4134):
        raise ValueError("frozen curve, roots, domain, or runtime changed")
    basis = [int(mask, 16) for mask in
             geometry["domain"]["basis_coordinate_masks_hex"]]
    if len(basis) != 13:
        raise ValueError("wrong factor-base dimension")
    codes = valid_codes()
    if len(codes) != 4134:
        raise ValueError("wrong exact selector count")
    onb = first.runner.field.Onb(131)
    curve = first.runner.curves.Curve(onb)
    one = onb.one()
    leaf_data = {}
    for code in codes:
        leaf_phi, leaf_point = first.leaf(onb, curve, basis, code, 2)
        leaf_data[code] = (leaf_phi, leaf_point)

    branch_records = []
    for branch, declared in enumerate(previous["cubes"]):
        root_mask = declared["partial0_phi_mask"]
        if root_mask != roots["cubes"][0]["partial0_phi_masks"][branch]:
            raise ValueError("first-link root order changed")
        root_phi = onb.fromCoords(root_mask)
        root_point = curve.pointFromX(onb.add(onb.inv(root_phi), one))
        if root_point is None:
            raise ValueError("root did not lift to a curve point")
        root_y = onb.add(onb.sqr(root_phi), root_phi)
        rows = []
        exceptional = []
        for code in codes:
            leaf_phi, leaf_point = leaf_data[code]
            leaf_y = onb.add(onb.sqr(leaf_phi), leaf_phi)
            a = onb.mul(root_y, leaf_y)
            if onb.add(a, one) == onb.zero():
                exceptional.append({"code": code, "reason": "quadratic_degree_drop"})
                continue
            candidates = set()
            for second in (leaf_point, curve.neg(leaf_point)):
                value = phi_of(onb, curve.add(root_point, second))
                if value is None:
                    exceptional.append({"code": code, "reason": "nonfinite_group_output"})
                    continue
                total = onb.add(onb.add(root_phi, leaf_phi), value)
                equation = onb.add(onb.mul(a, onb.add(onb.sqr(value), value)),
                                   onb.sqr(total))
                if equation != onb.zero():
                    raise ValueError(f"code {code} group output fails second S3")
                candidates.add(onb.toCoords(value))
            if len(candidates) != 2:
                exceptional.append({"code": code, "reason": "not_two_distinct_finite_roots",
                                    "finite_masks": sorted(candidates)})
                continue
            masks = sorted(candidates)
            # The quadratic has nonzero leading coefficient; two distinct
            # checked group outputs are therefore its complete root set.
            rows.append([code, masks[0], masks[1]])
        branch_records.append({
            "branch": branch, "partial0_phi_mask": root_mask,
            "rows": rows, "complete_two_root_rows": len(rows),
            "exceptional": exceptional,
        })
    if any(item["exceptional"] for item in branch_records):
        raise ValueError("exceptional second-link cases require explicit encoding")
    protocol = {
        "kind": "n131_d13_exact_second_link_lookup_protocol",
        "status": "FROZEN_ENUMERATION", "proposal_id": "Q20261009132300",
        "candidate_id": None, "run_id": None,
        "curve_id": previous["curve_id"], "workload_id": previous["workload_id"],
        "target_count": 1, "branch_count": 2,
        "leaf_position": 2, "valid_code_count": len(codes),
        "row_semantics": "[third-leaf code, both complete finite partial1 phi roots]",
        "source_sha256": {
            "previous_protocol": sha(previous_path), "roots": sha(roots_path),
            "raw_xcnf": sha(RAW), "geometry": sha(GEOMETRY),
            "runtime": sha(runtime_path), "builder": sha(Path(__file__)),
        },
    }
    protocol_path.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    table = {
        "kind": "n131_d13_exact_second_link_lookup",
        "status": "PASS_TWO_COMPLETE_ROOTS_PER_CODE",
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
        "target_count": 1, "valid_codes": codes,
        "branches": branch_records,
        "source_sha256": {"protocol": sha(protocol_path),
                          "builder": sha(Path(__file__))},
    }
    table_path.write_text(json.dumps(table, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": table["status"],
                      "rows_per_branch": [b["complete_two_root_rows"]
                                          for b in branch_records]}))


if __name__ == "__main__":
    main()
