#!/usr/bin/env python3
"""Independent group-law replay of Q1410's exact-base N53 control."""

from __future__ import annotations

import argparse
import base64
import gzip
import json
from pathlib import Path

from run_probe import HERE, curves, field, sha

OUT = HERE / "runs/n53_q1410_balanced_control_replay.json"


def canonical_x(onb, x):
    masks = []
    start = x
    for _ in range(onb.m):
        masks.append(onb.toCoords(x))
        x = onb.sqr(x)
    assert x == start
    return min(masks)


def verify_relation(onb, curve, order, keys, receipt):
    relation = receipt["verified_relation"]
    assert relation is not None
    public = tuple(map(int, receipt["public_target"]))
    points = [curve.pointFromX(onb.fromCoords(value))
              for value in relation["leaf_x_coordinates"]]
    assert all(point is not None for point in points)
    assert [list(map(int, point)) for point in relation["leaf_points"]] == [
        list(point) for point in points]
    total = None
    columns = []
    for point, sign, projected_values in zip(
            points, relation["signs"], relation["projected_points"]):
        assert sign in (-1, 1)
        projected = curve.mul(point, 428)
        assert projected == tuple(map(int, projected_values))
        assert curve.mul(projected, order) is None
        column = canonical_x(onb, projected[0])
        assert column in keys
        columns.append(column)
        total = curve.add(total, point if sign == 1 else curve.neg(point))
    assert total == tuple(map(int, relation["raw_sum"]))
    assert curve.mul(total, 428) == public
    assert relation["public_target"] == [str(value) for value in public]
    return points, total, columns


def replay():
    protocol_path = HERE / "q1410_balanced_s3_n53_protocol.json"
    runtime_path = HERE / "q1410_sage_runtime_info.json"
    base_path = HERE / "bases/n53_weight3_orbits.json.gz"
    baseline_path = HERE / "runs/n53_ordinary_frozen.json"
    coset_path = HERE / "runs/n53_ordinary_raw_preimages.json"
    witness_path = HERE / "runs/n53_ordinary_multitarget_locked_verify.json"
    locked_path = HERE / "runs/n53_q1410_witness_locked.json"
    ordinary_path = HERE / "runs/n53_q1410_ordinary.json"
    protocol = json.loads(protocol_path.read_text())
    locked = json.loads(locked_path.read_text())
    ordinary = json.loads(ordinary_path.read_text())
    baseline = json.loads(baseline_path.read_text())
    coset = json.loads(coset_path.read_text())
    witness = json.loads(witness_path.read_text())
    with gzip.open(base_path, "rt") as stream:
        base = json.load(stream)
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    assert protocol["proposal_id"] == locked["proposal_id"] == "Q1410"
    assert protocol["candidate_id"] is locked["candidate_id"] is None
    assert protocol["isogeny"] == locked["isogeny"] == "none"
    assert protocol["base_archive_sha256"] == sha(base_path)
    assert protocol["ordinary_baseline_sha256"] == sha(baseline_path)
    assert protocol["ordinary_coset_sha256"] == sha(coset_path)
    assert protocol["ordinary_witness_sha256"] == sha(witness_path)
    assert locked["protocol_sha256"] == sha(protocol_path)
    assert ordinary["protocol_sha256"] == sha(protocol_path)
    assert locked["runtime_info_sha256"] == sha(runtime_path)
    assert ordinary["runtime_info_sha256"] == sha(runtime_path)
    assert ordinary["workload_id"] == baseline["workload_id"]
    assert ordinary["public_target"] == locked["public_target"] == [
        int(value) for value in baseline["public_subgroup_target"]]
    assert (ordinary["factor_base_enumerated_set_sha256"]
            == locked["factor_base_enumerated_set_sha256"]
            == base["factor_base"]["enumerated_set_sha256"])
    assert locked["status"] == "sat"
    assert locked["observed_verified_relation_count"] == 1
    assert locked["complete_solve_work_log2"] is None
    assert ordinary["complete_solve_work_log2"] is None
    packed = base64.b64decode(base["factor_base"]["packed_canonical_x_keys_base64"],
                              validate=True)
    keys = {int.from_bytes(packed[i:i + 7], "little")
            for i in range(0, len(packed), 7)}
    assert len(keys) == 227
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    order = int(base["curve"]["subgroup_order"])
    points, raw_sum, columns = verify_relation(onb, curve, order, keys, locked)
    assert len(set(columns)) == 4
    assert locked["attempts"][0]["four_distinct_columns"] is True
    assert locked["verified_relation"] == witness["relation"]
    assert [list(point) for point in points] == locked["fixture"]["raw_leaf_points"]
    signed = [point if sign == 1 else curve.neg(point)
              for point, sign in zip(points, witness["relation"]["signs"])]
    pair_sums = [curve.add(signed[0], signed[1]),
                 curve.add(signed[2], signed[3])]
    assert [list(point) for point in pair_sums] == locked["fixture"][
        "raw_pair_sum_points"]
    assert curve.add(*pair_sums) == raw_sum
    preimages = [tuple(map(int, point)) for point in coset["raw_target_points"]]
    assert raw_sum in preimages
    assert locked["attempts"][0]["decoded_choice"] == preimages.index(raw_sum)
    if ordinary["verified_relation"] is not None:
        verify_relation(onb, curve, order, keys, ordinary)
    else:
        assert ordinary["observed_verified_relation_count"] == 0
    return {
        "kind": "q1410_independent_checked_sage_balanced_control_replay",
        "status": "PASS", "proposal_id": "Q1410", "candidate_id": None,
        "curve_id": protocol["curve_id"], "isogeny": "none",
        "workload_id": protocol["ordinary_workload_id"],
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns": protocol["factor_base_folded_columns"],
        "factor_base_enumerated_set_sha256": protocol[
            "factor_base_enumerated_set_sha256"],
        "verified_locked_control_relation_count": 1,
        "locked_control_distinct_columns": 4,
        "ordinary_relation_count": ordinary["observed_verified_relation_count"],
        "is_natural_relation_yield_measurement": False,
        "complete_solve_work_log2": None,
        "protocol_sha256": sha(protocol_path),
        "runtime_info_sha256": sha(runtime_path),
        "locked_receipt_sha256": sha(locked_path),
        "ordinary_receipt_sha256": sha(ordinary_path),
        "witness_receipt_sha256": sha(witness_path),
        "base_archive_sha256": sha(base_path),
        "source_sha256": sha(Path(__file__)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = replay()
    content = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.check:
        assert OUT.read_text() == content
    else:
        assert not OUT.exists()
        OUT.write_text(content)
    print(json.dumps({"status": report["status"],
                      "ordinary_relation_count": report["ordinary_relation_count"]}))


if __name__ == "__main__":
    main()
