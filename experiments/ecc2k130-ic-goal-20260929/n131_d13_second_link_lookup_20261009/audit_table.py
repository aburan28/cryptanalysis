#!/usr/bin/env sage -python
"""Independently replay every finite second-link lookup entry."""

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
PROBE = GOAL / "n131_phi_torsion_frobenius_domains_20261005/d13_m12_probe"
RAW = PROBE / "official_q_phi_fiber_d13_m12_v1.xcnf"
GEOMETRY = GOAL / "n131_phi_torsion_frobenius_domains_20261005/m12_d13_static/d13_exact_geometry_v1.json"
CODEGEN = GOAL.parents[1] / "ecc2k130/codegen"
sys.path.insert(0, str(CODEGEN))
import curves
import field


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def source_codes():
    forbidden = set()
    variables = set(range(28, 41))
    for line in RAW.read_text(encoding="ascii").splitlines():
        if line.startswith(("p", "c", "x")):
            continue
        terms = [int(value) for value in line.split()]
        if (len(terms) == 14 and terms[-1] == 0 and
                {abs(value) for value in terms[:-1]} == variables):
            forbidden.add(sum(1 << (abs(value) - 28) for value in terms[:-1]
                              if value < 0))
    if len(forbidden) != 4058:
        raise ValueError("exact third-leaf domain changed")
    return sorted(set(range(8192)) - forbidden)


def leaf(onb, curve, basis, code):
    mask = 0
    for bit, value in enumerate(basis):
        if (code >> bit) & 1:
            mask ^= value
    phi = onb.frob(onb.fromCoords(mask), 2)
    if phi == onb.zero():
        raise ValueError("zero leaf phi")
    point = curve.pointFromX(onb.add(onb.inv(phi), onb.one()))
    if point is None:
        raise ValueError("third-leaf code does not lift")
    return phi, point


def group_phi_mask(onb, point):
    if point is None or point[0] == onb.one():
        raise ValueError("nonfinite second-link output")
    return onb.toCoords(onb.inv(onb.add(point[0], onb.one())))


def main():
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path, table_path = HERE / "protocol.json", HERE / "table.json"
    protocol = json.loads(protocol_path.read_text())
    table = json.loads(table_path.read_text())
    runtime = HERE / "runtime_info.json"
    if (protocol["status"] != "FROZEN_ENUMERATION" or
            table["status"] != "PASS_TWO_COMPLETE_ROOTS_PER_CODE" or
            table["source_sha256"]["protocol"] != sha(protocol_path) or
            protocol["source_sha256"]["raw_xcnf"] != sha(RAW) or
            protocol["source_sha256"]["geometry"] != sha(GEOMETRY) or
            protocol["source_sha256"]["runtime"] != sha(runtime) or
            json.loads(runtime.read_text())["status"] != "verified"):
        raise ValueError("frozen source or checked runtime mismatch")
    codes = source_codes()
    if table["valid_codes"] != codes or len(codes) != 4134:
        raise ValueError("table does not cover the exact third-leaf domain")
    basis = [int(value, 16) for value in json.loads(GEOMETRY.read_text())
             ["domain"]["basis_coordinate_masks_hex"]]
    if len(basis) != 13:
        raise ValueError("basis changed")
    onb = field.Onb(131)
    curve = curves.Curve(onb)
    leaves = {code: leaf(onb, curve, basis, code) for code in codes}
    branch_stats = []
    for branch, item in enumerate(table["branches"]):
        if (item["branch"] != branch or item["exceptional"] or
                item["complete_two_root_rows"] != len(codes) or
                len(item["rows"]) != len(codes)):
            raise ValueError("incomplete branch table")
        root_mask = item["partial0_phi_mask"]
        root_phi = onb.fromCoords(root_mask)
        root_point = curve.pointFromX(onb.add(onb.inv(root_phi), onb.one()))
        if root_point is None:
            raise ValueError("first-link root does not lift")
        output_counts = Counter()
        for code, (row_code, mask0, mask1) in zip(codes, item["rows"]):
            if code != row_code or not (0 < mask0 < mask1 < (1 << 131)):
                raise ValueError("row order or masks invalid")
            phi_leaf, point_leaf = leaves[code]
            y_root = onb.add(onb.sqr(root_phi), root_phi)
            y_leaf = onb.add(onb.sqr(phi_leaf), phi_leaf)
            a = onb.mul(y_root, y_leaf)
            leading = onb.add(a, onb.one())
            if leading == onb.zero():
                raise ValueError("second-link quadratic degree dropped")
            constant = onb.sqr(onb.add(root_phi, phi_leaf))
            roots = [onb.fromCoords(mask0), onb.fromCoords(mask1)]
            for value in roots:
                equation = onb.add(
                    onb.add(onb.mul(leading, onb.sqr(value)), onb.mul(a, value)),
                    constant)
                if equation != onb.zero():
                    raise ValueError("lookup mask fails expanded S3 equation")
            if onb.add(roots[0], roots[1]) != onb.mul(a, onb.inv(leading)):
                raise ValueError("lookup masks fail quadratic root-sum identity")
            group_masks = sorted((
                group_phi_mask(onb, curve.add(root_point, point_leaf)),
                group_phi_mask(onb, curve.add(root_point, curve.neg(point_leaf))),
            ))
            if group_masks != [mask0, mask1]:
                raise ValueError("lookup roots differ from independent group additions")
            output_counts[mask0] += 1
            output_counts[mask1] += 1
        branch_stats.append({
            "branch": branch, "checked_codes": len(codes),
            "checked_outputs": 2 * len(codes),
            "distinct_output_masks": len(output_counts),
            "repeated_output_masks": sum(1 for count in output_counts.values()
                                         if count > 1),
            "largest_mask_multiplicity": max(output_counts.values()),
        })
    receipt = {
        "kind": "n131_d13_second_link_lookup_independent_full_audit",
        "status": "PASS_EXACT_COMPLETE_TWO_ROOT_TABLES",
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
        "target_count": 1, "branch_stats": branch_stats,
        "source_sha256": {
            "protocol": sha(protocol_path), "table": sha(table_path),
            "raw_xcnf": sha(RAW), "geometry": sha(GEOMETRY),
            "audit_script": sha(Path(__file__)),
        },
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"], "branches": branch_stats}))


if __name__ == "__main__":
    main()
