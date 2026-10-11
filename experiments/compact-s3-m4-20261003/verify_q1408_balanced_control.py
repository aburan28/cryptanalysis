#!/usr/bin/env python3
"""Independently replay Q1408's balanced planted control in checked Sage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from q1325_inputs import read_inputs
from run_probe import HERE, ROOT, curves, field, sha


sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))
from orbit_key import OrbitKey  # noqa: E402


OUT = HERE / "runs/n83_q1408_balanced_control_replay.json"


def recover_preimage_points(onb, curve, target, raw_xs):
    points = []
    for x in raw_xs:
        lift = curve.pointFromX(onb.fromCoords(x))
        assert lift is not None
        if curve.mul(lift, 4) != target:
            lift = curve.neg(lift)
        assert curve.mul(lift, 4) == target
        points.append(lift)
    assert len(points) == 4 and len(set(points)) == 4
    return points


def replay():
    protocol_path = HERE / "q1408_balanced_s3_w5_protocol.json"
    locked_path = HERE / "runs/n83_q1408_planted_locked.json"
    unpinned_path = HERE / "runs/n83_q1408_planted_unpinned.json"
    ordinary_path = HERE / "runs/n83_q1408_ordinary.json"
    runtime_path = HERE / "q1408_sage_runtime_info.json"
    protocol = json.loads(protocol_path.read_text())
    locked = json.loads(locked_path.read_text())
    unpinned = json.loads(unpinned_path.read_text())
    ordinary = json.loads(ordinary_path.read_text())
    base_path, base, key_path, keys, baseline_path, baseline = read_inputs()
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    assert protocol["proposal_id"] == locked["proposal_id"] == "Q1408"
    assert protocol["candidate_id"] is locked["candidate_id"] is None
    assert protocol["isogeny"] == locked["isogeny"] == "none"
    assert protocol["q1325_base_receipt_sha256"] == sha(base_path)
    assert protocol["q1325_point_keys_sha256"] == sha(key_path)
    assert protocol["ordinary_target_receipt_sha256"] == sha(baseline_path)
    assert locked["protocol_sha256"] == sha(protocol_path)
    assert locked["runtime_info_sha256"] == sha(runtime_path)
    assert locked["factor_base_enumerated_set_sha256"] == base[
        "factor_base"]["enumerated_set_sha256"]
    assert ordinary["workload_id"] == baseline["workload_id"]
    assert ordinary["public_target"] == [int(value) for value in baseline[
        "public_subgroup_target"]]
    assert unpinned["public_target"] == locked["public_target"]
    assert unpinned["fixture"] == locked["fixture"]
    assert locked["status"] == "sat"
    assert locked["observed_verified_relation_count"] == 1
    assert all(row["complete_solve_work_log2"] is None
               for row in (locked, unpinned, ordinary))

    onb = field.Onb(83)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    order = int(base["curve"]["subgroup_order"])
    key_set = set(keys)
    target = tuple(map(int, locked["public_target"]))
    assert curve.onCurve(target) and curve.mul(target, order) is None
    fixture = locked["fixture"]
    raw_x = fixture["raw_leaf_x"]
    assert len(raw_x) == len(set(raw_x)) == 4
    assert all(value.bit_count() == 5 for value in raw_x)
    raw_points = [curve.pointFromX(onb.fromCoords(value)) for value in raw_x]
    assert raw_points == [tuple(map(int, point)) for point in fixture[
        "raw_leaf_points"]]
    first = curve.add(raw_points[0], raw_points[1])
    second = curve.add(raw_points[2], raw_points[3])
    raw_sum = curve.add(first, second)
    assert [list(first), list(second)] == fixture[
        "raw_pair_sum_points"]
    assert list(raw_sum) == fixture["raw_sum"]
    assert curve.mul(raw_sum, 4) == target

    preimages = recover_preimage_points(
        onb, curve, target, locked["raw_preimage_x_coordinates"])
    assert raw_sum in preimages
    attempt = locked["attempts"][0]
    assert attempt["decoded_choice"] == preimages.index(raw_sum)
    assert attempt["decoded_raw_target_x"] == onb.toCoords(raw_sum[0])
    assert attempt["lift_status"] == "verified_four_point_relation"
    relation = locked["verified_relation"]
    assert relation == attempt["verified_relation"]
    assert relation is not None
    assert relation["leaf_x_coordinates"] == raw_x
    signs = relation["signs"]
    assert len(signs) == 4 and all(sign in (1, -1) for sign in signs)
    leaves = [tuple(map(int, point)) for point in relation["leaf_points"]]
    assert leaves == raw_points
    total = None
    columns = []
    for leaf, sign, projected_values in zip(
            leaves, signs, relation["projected_points"]):
        assert curve.onCurve(leaf)
        projected = curve.mul(leaf, 4)
        assert projected == tuple(map(int, projected_values))
        assert curve.mul(projected, order) is None
        column = orbit.canonical(projected)[0]
        assert column in key_set
        columns.append(column)
        total = curve.add(total, leaf if sign == 1 else curve.neg(leaf))
    assert total == raw_sum and curve.mul(total, 4) == target
    assert relation["raw_sum"] == [str(value) for value in raw_sum]
    assert relation["public_target"] == [str(value) for value in target]

    return {
        "kind": "q1408_independent_checked_sage_balanced_control_replay",
        "status": "PASS",
        "proposal_id": "Q1408",
        "candidate_id": None,
        "run_id": None,
        "curve_id": protocol["curve_id"],
        "workload_id": None,
        "isogeny": "none",
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns": protocol[
            "factor_base_folded_columns"],
        "factor_base_enumerated_set_sha256": protocol[
            "factor_base_enumerated_set_sha256"],
        "four_raw_leaves_reconstructed": True,
        "complete_four_preimage_coset_checked": True,
        "four_projected_leaves_in_exact_q1325_base": True,
        "four_distinct_columns": len(set(columns)) == 4,
        "raw_and_public_sums_verified": True,
        "verified_control_relation_count": 1,
        "ordinary_relation_count": ordinary[
            "observed_verified_relation_count"],
        "is_natural_relation_yield_measurement": False,
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "protocol_sha256": sha(protocol_path),
        "locked_stage_sha256": sha(locked_path),
        "unpinned_stage_sha256": sha(unpinned_path),
        "ordinary_stage_sha256": sha(ordinary_path),
        "base_receipt_sha256": sha(base_path),
        "point_key_file_sha256": sha(key_path),
        "runtime_info_sha256": sha(runtime_path),
        "field_source_sha256": sha(Path(field.__file__)),
        "curve_source_sha256": sha(Path(curves.__file__)),
        "orbit_source_sha256": sha(
            ROOT / "experiments/koblitz-pair-claw-20260929/orbit_key.py"),
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
        assert not OUT.exists(), "refusing to overwrite frozen replay"
        OUT.write_text(content)
    print(json.dumps({"status": report["status"],
                      "verified_control_relation_count": report[
                          "verified_control_relation_count"],
                      "ordinary_relation_count": report[
                          "ordinary_relation_count"]}))


if __name__ == "__main__":
    main()
