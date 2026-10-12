#!/usr/bin/env python3
"""Freeze matched N83 S3-chain cells with a wider exact-join admission cap."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1467 = PARENT / "q1467_density_bridge"
Q1466 = PARENT / "q1466_leaf_rotation"
NAMES = ("n83_planted_unpinned", "n83_ordinary")
SOURCES = (
    "experiments/compact-s3-m4-20261003/q1471_n83_wide_join/run.py",
    "experiments/compact-s3-m4-20261003/q1471_n83_wide_join/freeze_protocol.py",
    "experiments/compact-s3-m4-20261003/q1467_density_bridge/build_inputs.py",
    "experiments/compact-s3-m4-20261003/q1438_dense_base/verify_solver.py",
    "experiments/compact-s3-m4-20261003/q1466_leaf_rotation/native_solver.cpp",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render() -> dict:
    q1467_path = Q1467 / "solver_protocol.json"
    q1467 = json.loads(q1467_path.read_text())
    cells = {name: q1467["cells"][name] for name in NAMES}
    assert all(cell["curve_id"] == "EC1N83Ckb1h876c2921cb64"
               for cell in cells.values())
    assert all(cell["factor_base_actual_B"] == 1934066 and
               cell["folded_columns_K"] == 11651
               for cell in cells.values())
    assert all(cell["leaves_pinned"] is False for cell in cells.values())
    assert cells[NAMES[0]]["input_role"] == "planted"
    assert cells[NAMES[1]]["input_role"] == "ordinary"
    return {
        "kind": "q1471_n83_wide_join_protocol",
        "proposal_id": "Q1471", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "curve_id": "EC1N83Ckb1h876c2921cb64", "degree_n": 83,
        "factor_base_actual_B": 1934066,
        "folded_columns_K": 11651,
        "factor_base_enumerated_set_sha256": cells[NAMES[0]][
            "factor_base_enumerated_set_sha256"],
        "run_order": list(NAMES),
        "cells": {name: {
            "workload_id": cell["workload_id"],
            "public_target": cell["public_target"],
            "input_role": cell["input_role"],
            "input_sha256": cell["input_sha256"],
            "cnf_sha256": cell["cnf_sha256"],
            "cnf_variables": cell["cnf_variables"],
            "cnf_clauses": cell["cnf_clauses"],
            "q1467_prior_receipt_sha256": sha(Q1467 / "runs" / name /
                                              "receipt.json"),
        } for name, cell in cells.items()},
        "controlled_variable": (
            "raise exact joint-pair admission cap from 250000 to 1000000; "
            "reuse exact Q1467 CNFs, target points, base, solver binary, "
            "and decision policy"),
        "pair_candidate_cap": 1_000_000,
        "conflict_cap": 10_000_000,
        "wall_cap_seconds": 120,
        "external_safeguard_seconds": 180,
        "decision_policy": q1467["decision_policy"],
        "q1467_protocol_sha256": sha(q1467_path),
        "q1470_receipt_sha256": sha(PARENT /
            "q1470_n83_long_control/run/receipt.json"),
        "binary_sha256": sha(Q1466 / "native_solver"),
        "compile_receipt_sha256": sha(Q1466 / "compile_receipt.json"),
        "field_file_sha256": sha(PARENT / "q1420_root_theory/n83_field.txt"),
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "source_sha256": {name: sha(ROOT / name) for name in SOURCES},
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "cpu_isolation_receipt": None,
        "controlled_wall_speedup": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = HERE / "protocol.json"
    result = render()
    if args.check:
        assert result == json.loads(path.read_text())
    else:
        assert not path.exists(), "refuse overwrite"
        path.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "pass", "proposal_id": "Q1471",
                      "pair_cap": result["pair_candidate_cap"]}))


if __name__ == "__main__":
    main()
