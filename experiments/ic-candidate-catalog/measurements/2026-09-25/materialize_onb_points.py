#!/usr/bin/env python3
"""Freeze the exact shared subgroup-usable ONB point set for HW2 and HW3."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
CODE = HERE.parents[3] / "ecc2k130/codegen"
sys.path.insert(0, str(CODE))
import curves  # noqa: E402
import field  # noqa: E402
import indexcalc  # noqa: E402


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def main() -> None:
    output = HERE / "n131_onb_hw2_hw3_usable_points.json"
    if output.exists():
        raise SystemExit("output already exists")
    hw2 = json.loads((HERE / "n131_onb_hw2_base.json").read_text())
    hw3 = json.loads((HERE / "n131_onb_hw3_base.json").read_text())
    assert hw2["status"] == hw3["status"] == "complete"
    assert hw2["point_set_sha256"] == hw3["point_set_sha256"]
    onb = field.Onb(131)
    curve = curves.Curve(onb)
    order = curves.curveOrder(131) // 4
    points, orbits = indexcalc.factorBase(onb, curve, 2)
    usable_reps = [rep for rep in orbits if curve.mul(points[rep], order) is None]
    assert len(usable_reps) == hw2["subgroup_usable_x_orbits"] == 14
    encoded = []
    for rep in usable_reps:
        representative = points[rep]
        for coordinate in orbits[rep]:
            point = points[coordinate]
            assert curve.onCurve(point)
            assert onb.trace(point[0]) == 0
            encoded.extend(([onb.toCoords(point[0]), onb.toCoords(point[1])],
                            [onb.toCoords(point[0]), onb.toCoords(curve.neg(point)[1])]))
        frobenius_x = {onb.toCoords(curve.frob(representative, j)[0]) for j in range(131)}
        assert frobenius_x == set(orbits[rep])
    encoded.sort()
    assert len(encoded) == len({tuple(point) for point in encoded}) == 3668
    digest = hashlib.sha256(canonical(encoded).encode()).hexdigest()
    assert digest == hw2["point_set_sha256"] == hw3["point_set_sha256"]
    report = {
        "kind": "exact_shared_n131_onb_hw2_hw3_subgroup_point_set",
        "field_representation": "permuted_type_II_optimal_normal_basis",
        "point_encoding": "[x_coordinate_mask_decimal,y_coordinate_mask_decimal]",
        "subgroup_order": str(order),
        "point_count": len(encoded),
        "signed_frobenius_orbit_count": len(usable_reps),
        "point_set_sha256": digest,
        "trace_zero_and_frobenius_checks": True,
        "points": encoded,
    }
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
