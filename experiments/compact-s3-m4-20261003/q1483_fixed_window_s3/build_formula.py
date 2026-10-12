#!/usr/bin/env python3
"""Pin each Q1482 leaf to the zero-start cyclic normal-basis window."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1481 = PARENT / "q1481_window_orbit_base"
Q1438 = PARENT / "q1438_dense_base"
Q1482 = PARENT / "q1482_window_s3"
sys.path.insert(0, str(PARENT))
from q1482_window_s3.build_formula import (  # noqa: E402
    ORDINARY, build as parent_build, encode_map,
)
from q1420_root_theory.build_formula import convert_to_cnf  # noqa: E402
from q1425_reverse_pair.relax_control import serialize_cnf  # noqa: E402
from q1423_target_coupled.target_inputs import encode_targets  # noqa: E402

DESIGN = HERE / "design_protocol.json"


def build(n: int, role: str):
    design = json.loads(DESIGN.read_text())
    item = design["instances"][str(n)]
    formula, meta = parent_build(n, role)
    assert meta["curve_id"] == item["curve_id"]
    assert meta["factor_base_actual_B"] == item["actual_usable_B"]
    assert meta["folded_columns_K"] == item["folded_K"]
    assert meta["factor_base_enumerated_set_sha256"] == item[
        "enumerated_set_sha256"]
    starts = design["fixed_window_starts"][str(n)]
    assert len(starts) == len(meta["window_selector_variables"]) == 4
    for selectors, start in zip(meta["window_selector_variables"], starts):
        assert 0 <= start < len(selectors)
        formula.clauses.append([selectors[start]])
    meta["proposal_id"] = "Q1483"
    meta["fixed_window_starts"] = starts
    meta["input_law"] += "; all four windows fixed before search"
    return formula, meta


def build_cnf(n: int, role: str):
    formula, meta = build(n, role)
    variables, clauses = convert_to_cnf(formula)
    raw = serialize_cnf(variables, clauses)
    targets = encode_targets(n, meta["raw_target_x_coordinates"])
    return (raw, encode_map(meta), targets, formula, meta, variables,
            len(clauses))
