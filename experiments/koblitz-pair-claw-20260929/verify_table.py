#!/usr/bin/env python3
"""Independently replay the n=53 signed-Frobenius quotient-table witness."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
sys.path.insert(0, str(CODEGEN))

import curves
import field
from orbit_key import OrbitKey
from probe_n53_relation import base_and_columns
from run_n23 import frozen, point_digest, sha


def verify():
    receipt_path = HERE / "runs" / "n53_weight3_quotient_table_probe.json"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["source_sha256"] == sha(HERE / "probe_n53_table.py")
    assert receipt["base_source_sha256"] == sha(HERE / "probe_n53_relation.py")
    assert receipt["orbit_key_sha256"] == sha(HERE / "orbit_key.py")
    for name, digest in receipt["dependency_sha256"].items():
        assert digest == sha(CODEGEN / name)
    reference_path = (HERE.parent / "ecc2k130-quotient-pair-probe-20260926" /
                      "runs" / "n53_perf_prefix.json")
    assert receipt["reference_sha256"] == sha(reference_path)
    reference = json.loads(reference_path.read_text())
    identity = receipt["curve_identity_record"]
    assert receipt["curve_id"] == reference["curve_id"]
    assert receipt["curve_id"] == ("EC1N53Ckb1h" +
                                   hashlib.sha256(frozen(identity)).hexdigest()[:12])
    assert receipt["workload_id"] == hashlib.sha256(frozen(
        receipt["workload"])).hexdigest()[:12]
    assert receipt["isogeny"] == "none"
    assert receipt["candidate_id"] is None
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    order = identity["curve"]["subgroup_order"]
    cofactor = identity["curve"]["cofactor"]
    target = tuple(receipt["workload"]["target"])
    generator = tuple(identity["curve"]["generator"])
    assert target == tuple(reference["workload"]["target"])
    assert curve.mul(target, order) is None
    assert curve.mul(generator, order) is None
    base, representatives, rational = base_and_columns(curve, onb,
                                                         order, cofactor)
    base_record = receipt["factor_base"]
    assert len(base) == base_record["actual_usable_points_B_before_folding"] == 24062
    assert len(representatives) == base_record["signed_frobenius_columns"] == 227
    assert rational == base_record["rational_x_coordinates"] == 12031
    assert point_digest(base) == base_record["enumerated_set_sha256"]

    result = receipt["ordinary_query"]
    assert result["status"] == "verified_four_point_relation"
    assert result["table_samples"] == 500000
    assert result["table_distinct_keys"] == 457277
    assert result["query_samples"] == 165899
    relation = result["relation"]
    zero = relation["zero_meta"]
    one = relation["one_meta"]
    zero_pair = curve.add(base[zero[0]], base[zero[1]])
    one_pair = curve.add(base[one[0]], base[one[1]])
    one_output = curve.add(target, curve.neg(one_pair))
    zero_key, zero_exp, zero_sign = orbit.canonical(zero_pair)
    one_key, one_exp, one_sign = orbit.canonical(one_output)
    assert zero_key == one_key
    assert [zero_exp, zero_sign] == zero[2:]
    assert [one_exp, one_sign] == one[2:]
    shift = (zero_exp - one_exp) % 53
    sign = zero_sign * one_sign
    assert shift == relation["frobenius_shift_of_zero_pair"]
    assert sign == relation["sign_of_zero_pair"]
    points = [curve.frob(base[zero[0]], shift),
              curve.frob(base[zero[1]], shift),
              base[one[0]], base[one[1]]]
    if sign < 0:
        points[:2] = [curve.neg(point) for point in points[:2]]
    assert [list(point) for point in points] == relation["points"]
    assert all(point in set(base) for point in points)
    assert all(points[i] != curve.neg(points[j])
               for i in range(4) for j in range(i))
    total = None
    for point in points:
        total = curve.add(total, point)
    assert total == target
    assert receipt["verified_relation_count"] == 1
    assert receipt["verified_single_target_dlp"] is False
    assert receipt["complete_work_log2"] is None
    return {"curve_id": receipt["curve_id"], "B": len(base),
            "columns": len(representatives),
            "table_samples": result["table_samples"],
            "query_samples": result["query_samples"],
            "verified_relation": True}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
