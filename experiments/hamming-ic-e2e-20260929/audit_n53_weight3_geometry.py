#!/usr/bin/env python3
"""Exact weight-three normal-basis geometry for a possible N53 four-sum gate."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from math import comb
from pathlib import Path
import time

from n53_group import COFACTOR, Curve, Field, N, R, normal_basis

HERE = Path(__file__).resolve().parent
W2 = HERE / "runs/n53_scale_v1/fc/receipt.json"
WEIGHT, SUMMANDS = 3, 4


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(points):
    return hashlib.sha256(json.dumps([list(p) for p in sorted(points)],
                sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def signed_orbit_key(field, curve, point):
    values = []
    current = point
    for _ in range(N):
        values.extend((current, curve.neg(current)))
        current = field.square(current[0]), field.square(current[1])
    assert current == point
    return min(values)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError("geometry receipt is immutable")
    out.mkdir(parents=True)
    start = time.perf_counter_ns()
    old = json.loads(W2.read_text())
    field = Field()
    curve = Curve(field)
    _, conjugates = normal_basis(field)
    visited = set()
    raw, projected, columns = set(), set(), set()
    rational_orbits = 0
    for mask in itertools.combinations(range(N), WEIGHT):
        if mask in visited:
            continue
        orbit = {tuple(sorted((index + shift) % N for index in mask))
                 for shift in range(N)}
        assert len(orbit) == N
        visited.update(orbit)
        x = 0
        for index in mask:
            x ^= conjugates[index]
        points = curve.lift(x)
        if points:
            assert len(points) == 2
            rational_orbits += 1
        for point in points:
            image = curve.mul(point, COFACTOR)
            assert image is not None and curve.mul(image, R) is None
            columns.add(signed_orbit_key(field, curve, image))
            current_raw, current_image = point, image
            for _ in range(N):
                raw.add(current_raw)
                projected.add(current_image)
                current_raw = field.square(current_raw[0]), field.square(current_raw[1])
                current_image = field.square(current_image[0]), field.square(current_image[1])
            assert current_raw == point and current_image == image
    nominal = comb(N, WEIGHT)
    assert len(visited) == nominal
    assert rational_orbits == 221
    assert len(raw) == len(projected) == 23426
    assert len(columns) == 221
    raw_multisets = comb(len(raw) + SUMMANDS - 1, SUMMANDS)
    record = {
        "kind": "n53_weight3_four_summand_geometry_proposal",
        "curve_id": old["curve_id"], "candidate_id": None,
        "source_w2_receipt_sha256": sha(W2),
        "source_sha256": {"audit_n53_weight3_geometry.py": sha(Path(__file__)),
                          "n53_group.py": sha(HERE / "n53_group.py")},
        "normal_element": 3, "nominal_hamming_weight": WEIGHT,
        "nominal_masks": nominal, "mask_frobenius_orbits": len(visited) // N,
        "rational_x_orbits": rational_orbits,
        "rational_x_count": len(raw) // 2,
        "geometric_points": len(raw),
        "actual_usable_projected_points": len(projected),
        "effective_signed_frobenius_columns": len(columns),
        "raw_set_sha256": digest(raw),
        "projected_set_sha256": digest(projected),
        "column_set_sha256": digest(columns),
        "proposed_summands": SUMMANDS,
        "raw_four_multisets_with_repetition": str(raw_multisets),
        "ambient_curve_order": str(R * COFACTOR),
        "raw_tuple_count_to_ambient_order_ratio": format(raw_multisets / (R * COFACTOR), ".12f"),
        "wall_ns": time.perf_counter_ns() - start,
        "claim_boundary": "Exact geometry and combinatorial tuple count only. The ratio is not a measured natural relation yield, verified PDP, or IC candidate."}
    (out / "receipt.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: record[key] for key in
                      ("nominal_masks", "rational_x_count",
                       "actual_usable_projected_points",
                       "effective_signed_frobenius_columns",
                       "raw_tuple_count_to_ambient_order_ratio", "wall_ns")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
