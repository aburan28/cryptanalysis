#!/usr/bin/env python3
"""Independently replay a Q1483 fixed-window model through exact group law."""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

from build_formula import HERE, PARENT, Q1481, build_cnf

sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT / "q1420_root_theory"))
from q1420_root_theory.verify_archive import check_cnf, model_from_file  # noqa: E402
from run_probe import curves, field  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402

sys.path.insert(0, str(Q1481))
from enumerate_base import canonical_rotation, OrbitKey  # noqa: E402


def cyclic_window_contains(cycle_mask: int, n: int, d: int) -> bool:
    full = (1 << n) - 1
    for start in range(n):
        window = ((1 << d) - 1) << start
        window = (window | (window >> n)) & full
        if cycle_mask & ~window == 0:
            return True
    return False


def archived_key_contains(packed: bytes, key: int, n: int) -> bool:
    width = (n + 7) // 8
    assert len(packed) % width == 0
    lo, hi = 0, len(packed) // width
    while lo < hi:
        mid = (lo + hi) // 2
        value = int.from_bytes(packed[mid * width:(mid + 1) * width],
                               "little")
        if value < key:
            lo = mid + 1
        else:
            hi = mid
    return lo < len(packed) // width and int.from_bytes(
        packed[lo * width:(lo + 1) * width], "little") == key


def model_relation(raw: bytes, formula, meta: dict, variables: int,
                   clauses: int, model_path: Path) -> dict:
    model = model_from_file(model_path)
    check_cnf(raw, model, variables, clauses)
    assert all(any(model[abs(lit)] == (lit > 0) for lit in clause)
               for clause in formula.clauses)
    assert all((sum(model[bit] for bit in row) & 1) == int(rhs)
               for row, rhs in formula.xors)
    n = meta["degree_n"]
    d = meta["nominal_window_dimension_d"]
    protocol = json.loads((Q1481 / "protocol.json").read_text())
    instance = protocol["instances"][str(n)]
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    packed = (Q1481 / f"n{n}_d{d}_projected_keys.bin").read_bytes()

    def value(bits):
        return sum(1 << i for i, bit in enumerate(bits) if model[bit])

    leaves = meta["leaf_variables"]
    mids = meta["pair_mid_variables"]
    raw_masks = [value(bits) for bits in leaves]
    mids_coords = [value(bits) for bits in mids]
    target_choice = value(meta["target_selector_variables"])
    assert target_choice < len(meta["raw_target_x_coordinates"])
    target_coords = meta["raw_target_x_coordinates"][target_choice]
    for a, b, c in ((onb.fromCoords(raw_masks[0]),
                     onb.fromCoords(raw_masks[1]), mids_coords[0]),
                    (onb.fromCoords(raw_masks[2]),
                     onb.fromCoords(raw_masks[3]), mids_coords[1]),
                    (onb.fromCoords(mids_coords[0]),
                     onb.fromCoords(mids_coords[1]), target_coords)):
        roots = {onb.toCoords(x) for x in s3_roots(onb, a, b)}
        assert c in roots

    raw_points, projected_points, projected_keys = [], [], []
    for coord_mask in raw_masks:
        assert coord_mask != 0
        x = onb.fromCoords(coord_mask)
        cycle_mask = orbit.cycle_bits(x)
        assert cyclic_window_contains(cycle_mask, n, d)
        point = curve.pointFromX(x)
        if point is None:
            return {"status": "nonrational_raw_x",
                    "raw_leaf_x_coordinates": raw_masks}
        projected = curve.mul(point, instance["cofactor"])
        if projected is None:
            return {"status": "identity_projection",
                    "raw_leaf_x_coordinates": raw_masks}
        assert curve.mul(projected, instance["subgroup_order"]) is None
        key = canonical_rotation(orbit.cycle_bits(projected[0]), n)
        assert archived_key_contains(packed, key, n)
        raw_points.append(point)
        projected_points.append(projected)
        projected_keys.append(key)
    if len(set(projected_keys)) != 4:
        return {"status": "duplicate_columns",
                "raw_leaf_x_coordinates": raw_masks}
    public = tuple(map(int, meta["public_target"]))
    for signs in itertools.product((1, -1), repeat=4):
        total = None
        for point, sign in zip(raw_points, signs):
            total = curve.add(total, point if sign == 1 else curve.neg(point))
        if total is not None and curve.mul(total, instance["cofactor"]) == public:
            return {
                "status": "verified_four_point_relation",
                "raw_leaf_x_coordinates": raw_masks,
                "signs": list(signs),
                "projected_points": [[int(x), int(y)]
                                     for x, y in projected_points],
                "projected_columns": projected_keys,
                "distinct_columns": 4,
                "selected_raw_target_index": target_choice,
                "public_target": list(public),
            }
    return {"status": "no_signed_public_sum",
            "raw_leaf_x_coordinates": raw_masks}


def verify_case(case: str, model_path: Path) -> dict:
    n_text, role = case.split("_", 1)
    n = int(n_text[1:])
    raw, _, _, formula, meta, variables, clauses = build_cnf(n, role)
    return model_relation(raw, formula, meta, variables, clauses, model_path)
