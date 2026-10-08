#!/usr/bin/env python3
"""Build balanced compact S3 CNFs on exact Q1481 window-orbit bases."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1481 = PARENT / "q1481_window_orbit_base"
Q1438 = PARENT / "q1438_dense_base"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT / "q1419_partial_pin"))
from chain_s3 import Formula, field, multiplication_table, square_destinations  # noqa: E402
from chain_s3_factored import s3_link_factored  # noqa: E402
from chain_s3_multitarget import choose_target_x  # noqa: E402
from q1419_partial_pin.run_cell import pin_bits  # noqa: E402
from q1420_root_theory.build_formula import convert_to_cnf  # noqa: E402
from q1425_reverse_pair.relax_control import serialize_cnf  # noqa: E402
from q1423_target_coupled.target_inputs import encode_targets  # noqa: E402

sys.path.insert(0, str(Q1481))
from enumerate_base import OrbitKey  # noqa: E402

DESIGN = HERE / "design_protocol.json"
ORDINARY = {53: PARENT / "runs/n53_q1410_ordinary.json",
            83: PARENT / "runs/n83_q1408_ordinary.json"}


def window_membership(formula: Formula, leaf: list[int],
                      coordinate_cycle: list[int], d: int) -> list[int]:
    n = len(leaf)
    assert len(coordinate_cycle) == n and 2 * d < n
    selectors = [formula.new() for _ in range(n)]
    formula.clauses.append(selectors[:])
    for start, selected in enumerate(selectors):
        allowed = {(start + j) % n for j in range(d)}
        for cycle_index, coordinate_index in enumerate(coordinate_cycle):
            if cycle_index not in allowed:
                formula.clauses.append([-selected, -leaf[coordinate_index]])
    formula.clauses.append(leaf[:])
    return selectors


def raw_targets_and_public(n: int, role: str):
    if role == "ordinary":
        parent = json.loads(ORDINARY[n].read_text())
        values = [int(x) for x in parent["raw_preimage_x_coordinates"]]
        assert values and len(values) == len(set(values))
        return values, parent["public_target"]
    fixture = json.loads((HERE / f"n{n}_planted_fixture.json").read_text())
    assert fixture["proposal_id"] == "Q1482"
    return [fixture["raw_target_x_coordinate"]], fixture[
        "public_target"]


def build(n: int, role: str):
    assert n in (53, 83)
    assert role in ("planted_pinned", "planted_unpinned", "ordinary")
    design = json.loads(DESIGN.read_text())
    item = design["instances"][str(n)]
    d = item["nominal_window_dimension_d"]
    base = json.loads((Q1481 / f"n{n}_d{d}_base.json").read_text())
    assert base["curve_id"] == item["curve_id"]
    assert base["actual_usable_points_B_before_folding"] == item[
        "actual_usable_B"]
    assert base["signed_frobenius_columns_K"] == item["folded_K"]
    assert base["enumerated_set_sha256"] == item[
        "enumerated_set_sha256"]
    onb = field.Onb(n)
    orbit = OrbitKey(onb)
    formula = Formula()
    leaves = [[formula.new() for _ in range(n)] for _ in range(4)]
    mids = [[formula.new() for _ in range(n)] for _ in range(2)]
    windows = [window_membership(formula, leaf, orbit.coordinate_cycle, d)
               for leaf in leaves]
    raw_targets, public = raw_targets_and_public(n, role)
    target, selector = choose_target_x(formula, n, raw_targets)
    table = multiplication_table(onb)
    square_dest = square_destinations(onb)
    s3_link_factored(formula, mids[0], mids[1], target,
                     table, square_dest)
    s3_link_factored(formula, leaves[2], leaves[3], mids[1],
                     table, square_dest)
    if role == "planted_pinned":
        fixture = json.loads((HERE / f"n{n}_planted_fixture.json").read_text())
        for bits, value in zip(leaves, fixture["raw_leaf_x_coordinates"]):
            pin_bits(formula, bits, value)
        for bits, value in zip(mids,
                               fixture["raw_pair_mid_x_coordinates"]):
            pin_bits(formula, bits, value)
        pin_bits(formula, selector, 0)
    meta = {
        "proposal_id": "Q1482", "candidate_id": None,
        "isogeny": "none", "degree_n": n,
        "curve_id": item["curve_id"], "role": role,
        "nominal_window_dimension_d": d,
        "factor_base_actual_B": item["actual_usable_B"],
        "folded_columns_K": item["folded_K"],
        "factor_base_enumerated_set_sha256": item[
            "enumerated_set_sha256"],
        "public_target": public,
        "raw_target_x_coordinates": raw_targets,
        "target_preimage_x_count": len(raw_targets),
        "leaf_variables": leaves,
        "pair_mid_variables": mids,
        "window_selector_variables": windows,
        "target_selector_variables": selector,
        "input_law": ("archived ordinary public target, no witness pins"
                      if role == "ordinary" else
                      "deterministic planted public target, raw leaves and "
                      "both pair mids pinned" if role == "planted_pinned"
                      else "deterministic planted public target, no pins"),
    }
    return formula, meta


def encode_map(meta: dict) -> bytes:
    n = meta["degree_n"]
    d = meta["nominal_window_dimension_d"]
    lines = [f"Q1420MAP1 {n} {d}"]
    for bits in meta["leaf_variables"] + meta["pair_mid_variables"]:
        lines.append(" ".join(map(str, bits)))
    selector = meta["target_selector_variables"]
    lines.append(str(len(selector)) + " " + " ".join(map(str, selector)))
    return ("\n".join(lines) + "\n").encode("ascii")


def build_cnf(n: int, role: str):
    formula, meta = build(n, role)
    variables, clauses = convert_to_cnf(formula)
    raw = serialize_cnf(variables, clauses)
    targets = encode_targets(n, meta["raw_target_x_coordinates"])
    return (raw, encode_map(meta), targets, formula, meta, variables,
            len(clauses))
