#!/usr/bin/env python3
"""Build Q1436's compact S3 CNF with an exact denser Q1438 base."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT / "q1419_partial_pin"))

from chain_s3 import Formula, field, multiplication_table, square_destinations  # noqa: E402
from chain_s3_factored import s3_link_factored  # noqa: E402
from chain_s3_multitarget import choose_target_x  # noqa: E402
from q1419_partial_pin.run_cell import pin_bits, read_profile  # noqa: E402
from q1420_root_theory.build_formula import convert_to_cnf  # noqa: E402
from q1425_reverse_pair.relax_control import serialize_cnf  # noqa: E402

CONTROL = PARENT / "q1419_partial_pin/protocol.json"
ORDINARY = {53: PARENT / "runs/n53_q1410_ordinary.json",
            83: PARENT / "runs/n83_q1408_ordinary.json"}


def build(n: int, cell: str, weight_override=None):
    assert n in (53, 83) and cell in ("free_partner", "ordinary")
    protocol = json.loads((HERE / "protocol.json").read_text())
    instance = protocol["instances"][str(n)]
    base = json.loads((HERE / f"n{n}_w{instance['new_weight_bound']}_base.json").read_text())
    assert base["curve_id"] == instance["curve_id"]
    control_profile, control_parent, fixture = read_profile(
        json.loads(CONTROL.read_text()), n)
    parent = (control_parent if cell == "free_partner" else
              json.loads(ORDINARY[n].read_text()))
    raw_targets = parent["raw_preimage_x_coordinates"]
    assert raw_targets and len(set(raw_targets)) == len(raw_targets)
    onb = field.Onb(n)
    formula = Formula()
    leaves = [[formula.new() for _ in range(n)] for _ in range(4)]
    mids = [[formula.new() for _ in range(n)] for _ in range(2)]
    weight = (instance["new_weight_bound"] if weight_override is None
              else weight_override)
    for leaf in leaves:
        formula.at_most(leaf, weight)
        formula.clauses.append(leaf[:])
    target, selector = choose_target_x(formula, n, raw_targets)
    table = multiplication_table(onb)
    square_dest = square_destinations(onb)
    s3_link_factored(formula, mids[0], mids[1], target, table, square_dest)
    if cell == "free_partner":
        data = fixture["fixture"]
        for index in (0, 2):
            bits, value = leaves[index], data["raw_leaf_x"][index]
            assert int(value).bit_count() <= weight
            pin_bits(formula, bits, value)
        chosen = onb.toCoords(int(data["raw_sum"][0]))
        pin_bits(formula, selector, raw_targets.index(chosen))
        for bits, point in zip(mids, data["raw_pair_sum_points"]):
            pin_bits(formula, bits, onb.toCoords(int(point[0])))
    s3_link_factored(formula, leaves[2], leaves[3], mids[1], table,
                     square_dest)
    meta = {
        "proposal_id": "Q1438", "candidate_id": None,
        "isogeny": "none", "curve_id": instance["curve_id"],
        "degree_n": n, "cell": cell,
        "normal_basis_weight_bound": weight,
        "factor_base_actual_B": base[
            "actual_usable_points_B_before_folding"],
        "folded_columns_K": base["signed_frobenius_columns_K"],
        "factor_base_enumerated_set_sha256": base[
            "enumerated_set_sha256"],
        "public_target": parent["public_target"],
        "target_preimage_x_count": len(raw_targets),
        "leaf_variables": leaves, "pair_mid_variables": mids,
        "target_selector_variables": selector,
        "input_law": ("archived known-witness first leaf of each pair and "
                      "both pair intermediates pinned; partners free"
                      if cell == "free_partner" else
                      "one archived ordinary public target; no witness pins"),
    }
    return formula, meta


def encode_map(meta: dict) -> bytes:
    n = meta["degree_n"]
    lines = [f"Q1420MAP1 {n} {meta['normal_basis_weight_bound']}"]
    for bits in meta["leaf_variables"] + meta["pair_mid_variables"]:
        lines.append(" ".join(map(str, bits)))
    selector = meta["target_selector_variables"]
    lines.append(str(len(selector)) + " " + " ".join(map(str, selector)))
    return ("\n".join(lines) + "\n").encode("ascii")


def build_cnf(n: int, cell: str, weight_override=None):
    formula, meta = build(n, cell, weight_override)
    variables, clauses = convert_to_cnf(formula)
    raw = serialize_cnf(variables, clauses)
    return raw, encode_map(meta), formula, meta, variables, len(clauses)
