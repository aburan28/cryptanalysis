#!/usr/bin/env sage -python
"""Lift a W15 reciprocal S3 model to twelve exact curve atoms."""

import importlib.util
import itertools
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent / "n131_w14_coupled_sixpair_sat_20261010"
SOURCE = HERE.parent / "n131_w15_coupled_sixpair_20261010"

spec = importlib.util.spec_from_file_location("w15_lift_original_run", ORIGINAL / "run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


def frobenius(field, point, steps):
    x, y = point
    for _ in range(steps):
        x, y = field.mul(x, x), field.mul(y, y)
    return x, y


def reciprocal(field, point):
    return None if point is None or point[0] == 0 else field.inv(point[0])


def source():
    columns = {int(a): int(b) for a, b in
               (line.split() for line in (SOURCE / "support_w15.tsv").read_text().splitlines())}
    _, field, curve, _, _ = run.source()
    assert len(columns) == 16441 and len(set(columns.values())) == 16381
    basis_w = [1 << i for i in range(1, 16)]
    half_trace = run.prior.inverse_module.prior.half_trace
    basis_u = [half_trace(field, w) for w in basis_w]
    assert all(field.mul(u, u) ^ u == w for u, w in zip(basis_u, basis_w))
    return columns, field, curve, basis_w, basis_u


def atom(field, curve, basis_w, basis_u, mask):
    coordinate = run.prior.inverse_module.prior.coordinate
    w = coordinate(basis_w, mask)
    u = coordinate(basis_u, mask)
    point_options = run.prior.inverse_module.prior.points_with_x(curve, 1 ^ field.inv(u))
    assert len(point_options) == 2
    point = point_options[0]
    diagonal = curve.add(point, frobenius(field, point, 1))
    assert diagonal is not None and diagonal[0] == field.inv(w)
    return diagonal


def lift(masks, middle_reciprocals, q, target_index):
    columns, field, curve, basis_w, basis_u = source()
    if len(masks) != 12 or len(middle_reciprocals) != 10:
        raise ValueError("twelve masks and ten intermediate reciprocals required")
    if any(mask not in columns for mask in masks):
        raise ValueError("mask outside audited W15 support")
    folded = [columns[mask] for mask in masks]
    if len(set(folded)) != 12:
        raise ValueError("folded-column collision")
    signed = []
    for i, mask in enumerate(masks):
        plus = frobenius(field, atom(field, curve, basis_w, basis_u, mask),
                         run.prior.ROTATIONS[i])
        signed.append((plus, curve.neg(plus)))
    pair_options = []
    for i in range(6):
        options = []
        for bits in itertools.product((0, 1), repeat=2):
            leaves = (signed[2*i][bits[0]], signed[2*i+1][bits[1]])
            total = curve.add(*leaves)
            if reciprocal(field, total) == middle_reciprocals[i]:
                options.append((bits, leaves, total))
        pair_options.append(options)
    raw_targets = run.prior.prior.old.target_preimages(curve, q)
    if target_index not in range(4):
        raise ValueError("invalid target-fiber index")
    solutions = []
    for choices in itertools.product(*pair_options):
        pair_sums = [item[2] for item in choices]
        upper = [curve.add(pair_sums[0], pair_sums[1]),
                 curve.add(pair_sums[2], pair_sums[3]),
                 curve.add(pair_sums[4], pair_sums[5])]
        upper.append(curve.add(upper[0], upper[1]))
        if [reciprocal(field, point) for point in upper] != middle_reciprocals[6:]:
            continue
        total = curve.add(upper[3], upper[2])
        if total != raw_targets[target_index] or curve.mul(4, total) != q:
            continue
        leaves = [leaf for choice in choices for leaf in choice[1]]
        signs = [sign for choice in choices for sign in choice[0]]
        solutions.append({"masks": masks, "signs": signs,
                          "folded_columns": folded,
                          "raw_leaves": [list(point) for point in leaves],
                          "raw_sum": list(total), "projected_sum": list(q),
                          "target_preimage_index": target_index})
    return {"status": "GROUP_LIFT_FOUND" if solutions else "NO_GROUP_LIFT",
            "pair_option_counts": [len(options) for options in pair_options],
            "solutions": solutions}
