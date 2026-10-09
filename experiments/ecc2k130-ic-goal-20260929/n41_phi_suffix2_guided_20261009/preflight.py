#!/usr/bin/env sage -python
"""Independently audit exact target-conditioned suffix support and XCNF."""

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

N, DIM, M = 41, 6, 12
PARTIAL9 = 2 + M * DIM + 9 * N


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def leaf(onb, curve, basis, code, position):
    mask = 0
    for bit in range(DIM):
        if (code >> bit) & 1:
            mask ^= basis[bit]
    phi = onb.frob(onb.fromCoords(mask), position)
    point = curve.pointFromX(onb.add(onb.inv(phi), onb.one()))
    if point is None:
        raise ValueError("suffix code lacks a curve lift")
    return point


def coordinate(onb, point):
    if point is None or point[0] == onb.one():
        return None
    return onb.toCoords(onb.inv(onb.add(point[0], onb.one())))


def group_check(protocol, suffix, previous):
    onb = field.Onb(N)
    curve = curves.Curve(onb)
    endpoint = tuple(onb.fromCoords(value) for value in
                     protocol["endpoint_coordinates"])
    target = tuple(onb.fromCoords(value) for value in
                   protocol["target_coordinates"])
    if curve.mul(endpoint, 4) != target:
        raise ValueError("endpoint transport to target changed")
    basis = json.loads((BASE / "table.json").read_text())["basis_coordinate_masks"]
    codes = json.loads((BASE / "table.json").read_text())["valid_codes"]
    options = []
    for position in (10, 11):
        points = []
        for code in codes:
            point = leaf(onb, curve, basis, code, position)
            points.extend((point, curve.neg(point)))
        options.append(points)
    if len(options[0]) != 60 or len(options[1]) != 60:
        raise ValueError("signed suffix domain changed")
    positive = set()
    negative = set()
    exceptional = 0
    for left in options[0]:
        for right in options[1]:
            pair = curve.add(left, right)
            mask = coordinate(onb, curve.add(endpoint, curve.neg(pair)))
            opposite = coordinate(onb, curve.add(curve.neg(endpoint),
                                                 curve.neg(pair)))
            if mask is None or opposite is None:
                exceptional += 1
            if mask is not None:
                positive.add(mask)
            if opposite is not None:
                negative.add(opposite)
    if (exceptional != suffix["nonfinite_residual_cases"] or
            sorted(positive) != suffix["masks"] or
            positive != negative or
            len(positive) != suffix["distinct_finite_partial9_masks"]):
        raise ValueError("saved suffix masks omit a valid endpoint-sign case")
    return {"signed_pair_cases": 3600, "distinct_partial9_masks": len(positive),
            "opposite_endpoint_mask_set_equal": True,
            "nonfinite_cases": exceptional}


def formula_check(suffix, protocol):
    source = BASE / "lookup.xcnf"
    guided = HERE / "guided.xcnf"
    if (sha(source) != protocol["source_sha256"]["previous_lookup"] or
            sha(guided) != protocol["source_sha256"]["guided"]):
        raise ValueError("guided source or output hash changed")
    masks = suffix["masks"]
    with source.open("rt", encoding="ascii") as src, guided.open(
            "rt", encoding="ascii") as dst:
        old = src.readline().split()
        new = dst.readline().split()
        if old != ["p", "cnf", "34365", "54513"]:
            raise ValueError("source header changed")
        original_vars, original_records = int(old[2]), int(old[3])
        if new != ["p", "cnf", str(original_vars + len(masks)),
                   str(original_records + len(masks) * N + 1)]:
            raise ValueError("guided formula header mismatch")
        for line in src:
            if dst.readline() != line:
                raise ValueError("guided formula changed a source record")
        for index, mask in enumerate(masks):
            selector = original_vars + index + 1
            for bit in range(N):
                variable = PARTIAL9 + bit
                literal = variable if (mask >> bit) & 1 else -variable
                if dst.readline() != f"{-selector} {literal} 0\n":
                    raise ValueError("suffix membership implication changed")
        disjunction = " ".join(str(original_vars + index + 1)
                               for index in range(len(masks))) + " 0\n"
        if dst.readline() != disjunction or dst.readline():
            raise ValueError("suffix selector disjunction changed")
    return {"source_records_preserved": original_records,
            "appended_binary_clauses": len(masks) * N,
            "appended_disjunction_clauses": 1,
            "guided_variables": original_vars + len(masks),
            "guided_records": original_records + len(masks) * N + 1}


def main():
    output = HERE / "preflight.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path, suffix_path, runtime_path = (HERE / name for name in
                                               ("protocol.json", "suffix_masks.json",
                                                "runtime_info.json"))
    protocol = json.loads(protocol_path.read_text())
    suffix = json.loads(suffix_path.read_text())
    previous = json.loads((BASE / "protocol.json").read_text())
    if (protocol["status"] != "FROZEN" or suffix["status"] != "FROZEN_ENUMERATION" or
            protocol["source_sha256"]["suffix"] != sha(suffix_path) or
            protocol["source_sha256"]["runtime"] != sha(runtime_path) or
            protocol["source_sha256"]["previous_protocol"] != sha(BASE / "protocol.json") or
            json.loads(runtime_path.read_text())["status"] != "verified" or
            protocol["target_count"] != 1 or protocol["batch"] is not False):
        raise ValueError("frozen suffix proposal changed")
    group = group_check(protocol, suffix, previous)
    formula = formula_check(suffix, protocol)
    receipt = {"kind": "n41_phi_target_conditioned_suffix2_independent_preflight",
               "status": "PASS_COMPLETE_SUFFIX_AND_XCNF",
               "proposal_id": protocol["proposal_id"],
               "candidate_id": None, "run_id": None,
               "target_count": 1, "group": group, "formula": formula,
               "source_sha256": {"protocol": sha(protocol_path),
                                 "suffix": sha(suffix_path),
                                 "guided": sha(HERE / "guided.xcnf"),
                                 "auditor": sha(Path(__file__))}}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"], "group": group}))


if __name__ == "__main__":
    main()
