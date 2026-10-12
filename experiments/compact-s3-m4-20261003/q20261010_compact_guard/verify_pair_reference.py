#!/usr/bin/env python3
"""Replay the matched N53 pair-table relation and constructive base membership."""

import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
sys.path.insert(0, str(STAGE))
from cofactor_preimages import kernel_of_cofactor  # noqa: E402
from run_probe import curves, field  # noqa: E402


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    receipt_path = STAGE / "runs/n53_ordinary_matched_pair_table.json"
    archive_path = STAGE / "bases/n53_weight3_orbits.json.gz"
    receipt = json.loads(receipt_path.read_text())
    with gzip.open(archive_path, "rt") as stream:
        archive = json.load(stream)
    assert receipt["curve_id"] == archive["curve"]["curve_id"]
    assert receipt["factor_base_archive_sha256"] == digest(archive_path)
    assert receipt["factor_base_enumerated_set_sha256"] == archive[
        "factor_base"]["enumerated_set_sha256"]
    assert receipt["factor_base_actual_B"] == archive[
        "factor_base"]["actual_usable_points_B_before_folding"]
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    order = int(archive["curve"]["subgroup_order"])
    cofactor = int(archive["curve"]["cofactor"])
    assert cofactor == 428
    target = tuple(map(int, receipt["target"]))
    points = [tuple(map(int, point)) for point in
              receipt["ordinary_query"]["relation"]["points"]]
    assert len(points) == len(set(points)) == 4
    assert curve.onCurve(target) and curve.mul(target, order) is None
    kernel, _, _ = kernel_of_cofactor(curve, onb, order, cofactor, 130053)
    inverse = pow(cofactor, -1, order)
    witnesses = []
    total = None
    for projected in points:
        assert curve.onCurve(projected)
        assert curve.mul(projected, order) is None
        base = curve.mul(projected, inverse)
        raw = [curve.add(base, torsion) for torsion in kernel]
        assert len(set(raw)) == cofactor
        assert all(point is not None and curve.mul(point, cofactor) == projected
                   for point in raw)
        accepted = sorted((onb.hammingWeight(point[0]),
                           onb.toCoords(point[0])) for point in raw
                          if onb.hammingWeight(point[0]) <= 3)
        assert accepted
        witnesses.append({"projected_point": list(projected),
                          "qualifying_raw_x": accepted})
        total = curve.add(total, projected)
    assert total == target
    print(json.dumps({"status": "PASS", "curve_id": receipt["curve_id"],
                      "workload_id": receipt["workload_id"],
                      "factor_base_actual_B": receipt["factor_base_actual_B"],
                      "factor_base_set_sha256": receipt[
                          "factor_base_enumerated_set_sha256"],
                      "four_point_sum_matches_public_target": True,
                      "cofactor_membership_witnesses": witnesses}, sort_keys=True))


if __name__ == "__main__":
    main()
