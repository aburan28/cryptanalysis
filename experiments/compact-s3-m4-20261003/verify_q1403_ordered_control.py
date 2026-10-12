#!/usr/bin/env python3
"""Independent checked-Sage replay of Q1403's ordered planted control."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from q1325_inputs import read_inputs
from run_probe import HERE, ROOT, curves, field, sha


sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))
from orbit_key import OrbitKey  # noqa: E402


OUT = HERE / "runs/n83_q1403_ordered_control_replay.json"


def replay():
    protocol_path = HERE / "q1403_ordered_q1325_protocol.json"
    stage_path = HERE / "runs/n83_q1403_planted_locked.json"
    ordinary_path = HERE / "runs/n83_q1403_ordinary.json"
    unpinned_path = HERE / "runs/n83_q1403_planted_unpinned.json"
    runtime_path = HERE / "q1403_sage_runtime_info.json"
    protocol = json.loads(protocol_path.read_text())
    stage = json.loads(stage_path.read_text())
    ordinary = json.loads(ordinary_path.read_text())
    unpinned = json.loads(unpinned_path.read_text())
    base_path, base, key_path, keys, _, _ = read_inputs()
    assert protocol["proposal_id"] == stage["proposal_id"] == "Q1403"
    assert stage["status"] == "sat" and stage["oracle_assisted"]
    assert stage["protocol_sha256"] == sha(protocol_path)
    assert stage["runtime_info_sha256"] == sha(runtime_path)
    assert protocol["q1325_base_receipt_sha256"] == sha(base_path)
    assert protocol["q1325_point_keys_sha256"] == sha(key_path)
    assert stage["factor_base_enumerated_set_sha256"] == protocol[
        "factor_base_enumerated_set_sha256"]
    assert stage["workload_id"] is None
    assert ordinary["workload_id"] == protocol["ordinary_workload_id"]
    assert ordinary["observed_verified_relation_count"] == 0
    assert unpinned["observed_verified_relation_count"] == 0
    assert unpinned["public_target"] == stage["public_target"]
    assert unpinned["fixture"] == stage["fixture"]
    assert stage["complete_solve_work_log2"] is None
    assert ordinary["complete_solve_work_log2"] is None

    onb = field.Onb(83)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    order = int(base["curve"]["subgroup_order"])
    key_set = set(keys)
    fixture = stage["fixture"]
    raw_x = fixture["raw_leaf_x"]
    assert len(raw_x) == 4 and raw_x == sorted(set(raw_x))
    assert all(value.bit_count() == 5 for value in raw_x)
    target = tuple(map(int, stage["public_target"]))
    assert curve.onCurve(target) and curve.mul(target, order) is None

    fixture_points = [tuple(map(int, point)) for point in fixture[
        "projected_leaf_points"]]
    for raw, expected in zip(raw_x, fixture_points):
        lift = curve.pointFromX(onb.fromCoords(raw))
        assert lift is not None
        subgroup = curve.mul(lift, 4)
        assert subgroup == expected
        assert curve.mul(subgroup, order) is None
        assert orbit.canonical(subgroup)[0] in key_set
    first = curve.add(fixture_points[0], fixture_points[1])
    second = curve.add(first, fixture_points[2])
    assert [list(first), list(second)] == fixture["intermediate_points"]
    assert curve.add(second, fixture_points[3]) == target

    relation = stage["verified_relation"]
    assert relation is not None
    relation_points = [tuple(map(int, point)) for point in relation[
        "leaf_points"]]
    assert len(relation_points) == 4
    signs = relation["signs"]
    assert len(signs) == 4 and all(sign in (1, -1) for sign in signs)
    assert relation["leaf_x_coordinates"] == stage[
        "projected_leaf_x_coordinates"]
    assert [onb.toCoords(point[0]) for point in relation_points] == relation[
        "leaf_x_coordinates"]
    total = None
    columns = []
    for projected, point, sign in zip(fixture_points, relation_points, signs):
        assert point[0] == projected[0]
        assert curve.onCurve(point) and curve.mul(point, order) is None
        column = orbit.canonical(point)[0]
        assert column in key_set
        columns.append(column)
        total = curve.add(total, point if sign == 1 else curve.neg(point))
    assert total == target
    assert relation["raw_sum"] == [str(x) for x in target]
    assert relation["public_target"] == [str(x) for x in target]

    return {
        "kind": "q1403_independent_checked_sage_ordered_control_replay",
        "status": "PASS",
        "proposal_id": "Q1403",
        "candidate_id": None,
        "run_id": None,
        "curve_id": protocol["curve_id"],
        "workload_id": None,
        "isogeny": "none",
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns": protocol["factor_base_folded_columns"],
        "factor_base_enumerated_set_sha256": protocol[
            "factor_base_enumerated_set_sha256"],
        "ordered_raw_masks_verified": raw_x,
        "four_projected_points_reconstructed": True,
        "four_relation_points_in_exact_base": True,
        "four_distinct_columns": len(set(columns)) == 4,
        "public_target_sum_verified": True,
        "verified_control_relation_count": 1,
        "ordinary_relation_count": 0,
        "is_natural_relation_yield_measurement": False,
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "protocol_sha256": sha(protocol_path),
        "locked_stage_sha256": sha(stage_path),
        "ordinary_stage_sha256": sha(ordinary_path),
        "unpinned_stage_sha256": sha(unpinned_path),
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
