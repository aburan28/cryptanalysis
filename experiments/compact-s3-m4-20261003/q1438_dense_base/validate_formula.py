#!/usr/bin/env python3
"""Check dense-base ordinary CNF wiring against Q1426 at the old weights."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))
from q1426_symbolic_pair.build_formula import build_cnf as old_build  # noqa: E402
from q1438_dense_base.build_formula import build_cnf as dense_build  # noqa: E402
from run_probe import sha  # noqa: E402


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    rows = []
    for n in (53, 83):
        oldw = protocol["instances"][str(n)]["reference_weight_bound"]
        for cell in ("free_partner", "ordinary"):
            old_raw, _, _, _, old_vars, old_clauses = old_build(n, cell)
            new_raw, new_map, _, meta, new_vars, new_clauses = dense_build(
                n, cell, weight_override=oldw)
            assert old_raw == new_raw
            assert old_vars == new_vars and old_clauses == new_clauses
            assert meta["normal_basis_weight_bound"] == oldw
            parent_cell = "full_lock" if cell == "free_partner" else "ordinary"
            old_map = (PARENT / "q1420_root_theory/runs" /
                       f"n{n}_{parent_cell}/variables.txt").read_bytes()
            assert old_map == new_map
            rows.append({"degree_n": n, "cell": cell,
                         "reference_weight_bound": oldw,
                         "identical_cnf_sha256": hashlib.sha256(
                             old_raw).hexdigest(),
                         "identical_variable_map_sha256": hashlib.sha256(
                             new_map).hexdigest(),
                         "cnf_variables": old_vars,
                         "cnf_clauses": old_clauses})
    result = {"kind": "q1438_old_weight_formula_byte_equivalence",
              "status": "passed", "proposal_id": "Q1438",
              "candidate_id": None, "isogeny": "none", "rows": rows,
              "base_protocol_sha256": sha(HERE / "protocol.json"),
              "builder_sha256": sha(HERE / "build_formula.py"),
              "source_sha256": sha(Path(__file__)),
              "scope": "Q1426 control and ordinary CNF/map byte equivalence at old weights; higher-weight cells are new workloads"}
    output = HERE / "formula_validation.json"
    if output.exists():
        assert json.loads(output.read_text()) == result
    else:
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "passed", "degrees": [53, 83],
                      "cells": len(rows)}), flush=True)


if __name__ == "__main__":
    main()
