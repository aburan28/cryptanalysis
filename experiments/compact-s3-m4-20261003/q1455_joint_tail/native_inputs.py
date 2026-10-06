"""Deterministic Q1455 native controls and ordinary compact-S3 inputs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from q1419_partial_pin.run_cell import pin_bits  # noqa: E402
from q1420_root_theory.build_formula import convert_to_cnf  # noqa: E402
from q1423_target_coupled.target_inputs import (  # noqa: E402
    encode_targets, target_list)
from q1425_reverse_pair.relax_control import serialize_cnf  # noqa: E402
from q1438_dense_base.build_formula import build, encode_map  # noqa: E402
from q1455_joint_tail.run_controls import partial_witness  # noqa: E402

CASES = ("n53_partial_control", "n83_partial_control",
         "n53_known_sat_unpinned", "n53_ordinary", "n83_ordinary")


def make_case(name: str):
    if name not in CASES:
        raise ValueError(name)
    n = 53 if "n53" in name else 83
    planted = name == "n83_partial_control"
    cell = "free_partner" if planted else "ordinary"
    formula, meta = build(n, cell)
    if planted:
        pin_vars = {bit for row in (meta["leaf_variables"][0],
                                    meta["leaf_variables"][2],
                                    *meta["pair_mid_variables"])
                    for bit in row}
        original = len(formula.clauses)
        formula.clauses = [row for row in formula.clauses
                           if not (len(row) == 1 and abs(row[0]) in pin_vars)]
        assert original - len(formula.clauses) == 4 * n
    if "partial_control" in name:
        if n == 53:
            witness = json.loads((PARENT /
                "q1452_known_satisfiable_phi5/controls.json").read_text())[
                    "known_witness_raw_leaf_x"]
        else:
            witness = json.loads((PARENT /
                "q1446_joint_pair_span/validation.json").read_text())[
                    "controls"][1]["point_relation"]["raw_leaf_x"]
        partial = partial_witness(witness, n)
        for leaf, state in enumerate(partial):
            for j, bit in enumerate(meta["leaf_variables"][leaf]):
                if state.fixed_mask >> j & 1:
                    formula.clauses.append([bit if state.fixed_ones >> j & 1
                                            else -bit])
    if n == 53 and name != "n53_ordinary":
        pin_bits(formula, meta["target_selector_variables"], 201)
    q1436 = json.loads((PARENT /
        "q1436_affine_pair/protocol.json").read_text())["workloads"][
            f"n{n}_{cell}"]
    q1420 = json.loads((PARENT /
        "q1420_root_theory/protocol.json").read_text())["workloads"][
            q1436["parent_q1420_key"]]
    targets = target_list(n, "free_mids" if planted else "ordinary", q1420)
    if n == 53 and name != "n53_ordinary":
        expected = json.loads((PARENT /
            "q1452_known_satisfiable_phi5/controls.json").read_text())[
                "selected_raw_target_x"]
        assert targets[201] == expected
    if planted:
        assert targets[3] == 2752645346031481868456053
    variables, clauses = convert_to_cnf(formula)
    raw = serialize_cnf(variables, clauses)
    varmap = encode_map(meta)
    encoded_targets = encode_targets(n, targets)
    return raw, varmap, encoded_targets, formula, meta, variables, len(clauses)
