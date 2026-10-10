#!/usr/bin/env sage -python
"""Lift a W16 five-pair reciprocal model to ten exact raw curve atoms."""

import importlib.util
import itertools
from pathlib import Path

HERE = Path(__file__).resolve().parent
W15 = HERE.parent / "n131_w15_coupled_sixpair_20261010"
W16 = HERE.parent / "n131_w16_w18_sixpair_width_gate_20261010"
spec = importlib.util.spec_from_file_location("fivepair_original_lift", W15 / "w15_lift.py")
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)


def w16_source():
    columns = {int(a): int(b) for a, b in
               (line.split() for line in (W16 / "support_w16.tsv").read_text().splitlines())}
    _, field, curve, _, _ = original.run.source()
    assert len(columns) == 32796 and len(set(columns.values())) == 32675
    basis_w = [1 << i for i in range(1, 17)]
    half_trace = original.run.prior.inverse_module.prior.half_trace
    basis_u = [half_trace(field, w) for w in basis_w]
    assert all(field.mul(u, u) ^ u == w for u, w in zip(basis_u, basis_w))
    return columns, field, curve, basis_w, basis_u


original.source = w16_source


def lift(masks, middle_reciprocals, residual_q, target_index, fixed_columns):
    columns, field, curve, basis_w, basis_u = original.source()
    if len(masks) != 10 or len(middle_reciprocals) != 8:
        raise ValueError("ten masks and eight intermediate reciprocals required")
    if any(mask not in columns for mask in masks):
        raise ValueError("mask outside audited W16 support")
    folded = [columns[mask] for mask in masks]
    if len(set(folded + list(fixed_columns))) != 12:
        raise ValueError("folded-column collision with fixed pair")
    if masks[2] ^ masks[3] != masks[4] ^ masks[5] or \
            masks[6] ^ masks[7] != masks[8] ^ masks[9]:
        raise ValueError("seed-sum equality failed")
    rotations = original.run.prior.ROTATIONS[2:]
    signed = []
    for i, mask in enumerate(masks):
        plus = original.frobenius(field,
                                  original.atom(field, curve, basis_w, basis_u, mask),
                                  rotations[i])
        signed.append((plus, curve.neg(plus)))
    pair_options = []
    for i in range(5):
        options = []
        for bits in itertools.product((0, 1), repeat=2):
            leaves = (signed[2*i][bits[0]], signed[2*i+1][bits[1]])
            total = curve.add(*leaves)
            if original.reciprocal(field, total) == middle_reciprocals[i]:
                options.append((bits, leaves, total))
        pair_options.append(options)
    raw_targets = original.run.prior.prior.old.target_preimages(curve, residual_q)
    if target_index not in range(4):
        raise ValueError("invalid target-fiber index")
    solutions = []
    for choices in itertools.product(*pair_options):
        pair_sums = [item[2] for item in choices]
        upper = [curve.add(pair_sums[0], pair_sums[1]),
                 curve.add(pair_sums[2], pair_sums[3])]
        upper.append(curve.add(upper[0], upper[1]))
        if [original.reciprocal(field, point) for point in upper] != \
                middle_reciprocals[5:]:
            continue
        total = curve.add(upper[2], pair_sums[4])
        if total != raw_targets[target_index] or curve.mul(4, total) != residual_q:
            continue
        leaves = [leaf for choice in choices for leaf in choice[1]]
        signs = [sign for choice in choices for sign in choice[0]]
        solutions.append({"masks": masks, "signs": signs,
                          "folded_columns": folded,
                          "raw_leaves": [list(point) for point in leaves],
                          "raw_sum": list(total),
                          "projected_sum": list(residual_q),
                          "target_preimage_index": target_index})
    return {"status": "GROUP_LIFT_FOUND" if solutions else "NO_GROUP_LIFT",
            "pair_option_counts": [len(options) for options in pair_options],
            "solutions": solutions}
