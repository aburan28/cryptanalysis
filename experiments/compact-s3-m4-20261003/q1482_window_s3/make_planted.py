#!/usr/bin/env python3
"""Construct deterministic four-point positive controls on Q1481 bases."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1481 = PARENT / "q1481_window_orbit_base"
sys.path.insert(0, str(Q1481))
from enumerate_base import (  # noqa: E402
    canonical_rotation, curves, field, onb_x_from_cycle_mask,
    representatives, OrbitKey,
)

DESIGN = HERE / "design_protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make(n: int) -> dict:
    design = json.loads(DESIGN.read_text())
    item = design["instances"][str(n)]
    d = item["nominal_window_dimension_d"]
    base = json.loads((Q1481 / f"n{n}_d{d}_base.json").read_text())
    assert base["curve_id"] == item["curve_id"]
    assert base["actual_usable_points_B_before_folding"] == item[
        "actual_usable_B"]
    assert base["enumerated_set_sha256"] == item[
        "enumerated_set_sha256"]
    assert sha(Q1481 / f"n{n}_d{d}_projected_keys.bin") == item[
        "enumerated_set_sha256"]
    protocol = json.loads((Q1481 / "protocol.json").read_text())
    instance = protocol["instances"][str(n)]
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    chosen = []
    keys = set()
    scanned = 0
    for cycle_mask, _ in representatives(d):
        scanned += 1
        x = onb_x_from_cycle_mask(cycle_mask, onb, orbit)
        point = curve.pointFromX(x)
        if point is None:
            continue
        subgroup = curve.mul(point, instance["cofactor"])
        if subgroup is None:
            continue
        key = canonical_rotation(orbit.cycle_bits(subgroup[0]), n)
        if key in keys:
            continue
        if len(chosen) < 3:
            chosen.append((cycle_mask, point, subgroup, key))
            keys.add(key)
            continue
        candidate = chosen + [(cycle_mask, point, subgroup, key)]
        raw_sum = None
        for _, raw, _, _ in candidate:
            raw_sum = curve.add(raw_sum, raw)
        if raw_sum is None:
            continue
        public = curve.mul(raw_sum, instance["cofactor"])
        if public is None:
            continue
        chosen = candidate
        keys.add(key)
        break
    assert len(chosen) == len(keys) == 4
    assert raw_sum is not None and public is not None
    assert curve.mul(public, instance["subgroup_order"]) is None
    left = curve.add(chosen[0][1], chosen[1][1])
    right = curve.add(chosen[2][1], chosen[3][1])
    assert left is not None and right is not None
    assert curve.add(left, right) == raw_sum
    return {
        "kind": "q1482_deterministic_four_point_planted_control",
        "proposal_id": "Q1482", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "curve_id": item["curve_id"], "degree_n": n,
        "factor_base_actual_B": item["actual_usable_B"],
        "folded_columns_K": item["folded_K"],
        "factor_base_enumerated_set_sha256": item[
            "enumerated_set_sha256"],
        "nominal_window_dimension_d": d,
        "representatives_scanned": scanned,
        "raw_cycle_masks": [mask for mask, _, _, _ in chosen],
        "raw_leaf_x_coordinates": [onb.toCoords(raw[0])
                                   for _, raw, _, _ in chosen],
        "projected_orbit_keys": [key for _, _, _, key in chosen],
        "raw_pair_mid_x_coordinates": [onb.toCoords(left[0]),
                                       onb.toCoords(right[0])],
        "raw_target_x_coordinate": onb.toCoords(raw_sum[0]),
        "raw_sum_point": [int(x) for x in raw_sum],
        "public_target": [int(x) for x in public],
        "cofactor": instance["cofactor"],
        "subgroup_order": instance["subgroup_order"],
        "design_sha256": sha(DESIGN),
        "base_receipt_sha256": sha(Q1481 / f"n{n}_d{d}_base.json"),
        "is_ordinary_yield_measurement": False,
        "complete_solve_work_log2": None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = HERE / f"n{args.degree}_planted_fixture.json"
    result = make(args.degree)
    if args.check or path.exists():
        assert json.loads(path.read_text()) == result
        print(f"Q1482 N{args.degree} planted fixture verified")
    else:
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(f"Q1482 N{args.degree} planted fixture frozen")


if __name__ == "__main__":
    main()
