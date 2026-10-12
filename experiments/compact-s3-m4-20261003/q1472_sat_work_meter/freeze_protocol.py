#!/usr/bin/env python3
"""Freeze exact SAT propagation metering on all Q1467 N53/N83 cells."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1467 = PARENT / "q1467_density_bridge"
SOURCE_FILES = (
    "experiments/compact-s3-m4-20261003/q1472_sat_work_meter/freeze_protocol.py",
    "experiments/compact-s3-m4-20261003/q1472_sat_work_meter/run.py",
    "experiments/compact-s3-m4-20261003/q1472_sat_work_meter/build.py",
    "experiments/compact-s3-m4-20261003/q1472_sat_work_meter/native_solver.cpp",
    "experiments/compact-s3-m4-20261003/q1467_density_bridge/build_inputs.py",
    "experiments/compact-s3-m4-20261003/q1438_dense_base/verify_solver.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render() -> dict:
    q1467_path = Q1467 / "solver_protocol.json"
    q1467 = json.loads(q1467_path.read_text())
    names = q1467["run_order"]
    assert names == ["n53_planted", "n83_planted",
                     "n53_planted_unpinned", "n83_planted_unpinned",
                     "n53_ordinary", "n83_ordinary"]
    cells = {}
    for name in names:
        parent = q1467["cells"][name]
        cells[name] = {
            "curve_id": parent["curve_id"],
            "degree_n": parent["degree_n"],
            "factor_base_actual_B": parent["factor_base_actual_B"],
            "folded_columns_K": parent["folded_columns_K"],
            "factor_base_enumerated_set_sha256": parent[
                "factor_base_enumerated_set_sha256"],
            "workload_id": parent["workload_id"],
            "public_target": parent["public_target"],
            "input_role": parent["input_role"],
            "leaves_pinned": parent["leaves_pinned"],
            "input_sha256": parent["input_sha256"],
            "cnf_sha256": parent["cnf_sha256"],
            "cnf_variables": parent["cnf_variables"],
            "cnf_clauses": parent["cnf_clauses"],
            "prior_receipt_sha256": sha(Q1467 / "runs" / name /
                                        "receipt.json"),
        }
    assert q1467["pair_candidate_cap"] == 250_000
    assert q1467["conflict_cap"] == 1_000_000
    assert q1467["wall_cap_seconds"] == 60
    return {
        "kind": "q1472_exact_sat_work_meter_protocol",
        "proposal_id": "Q1472", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "controlled_variable": (
            "add CaDiCaL get_statistic_value('propagations') after solve; "
            "retain Q1467's exact CNFs, targets, solver behavior, "
            "resource caps and decision policy"),
        "run_order": names,
        "cells": cells,
        "pair_candidate_cap": q1467["pair_candidate_cap"],
        "conflict_cap": q1467["conflict_cap"],
        "wall_cap_seconds": q1467["wall_cap_seconds"],
        "external_safeguard_seconds": q1467[
            "external_safeguard_seconds"],
        "decision_policy": q1467["decision_policy"],
        "q1467_protocol_sha256": sha(q1467_path),
        "q1466_source_sha256": sha(PARENT /
            "q1466_leaf_rotation/native_solver.cpp"),
        "q1472_binary_sha256": sha(HERE / "native_solver"),
        "q1472_compile_receipt_sha256": sha(HERE / "compile_receipt.json"),
        "n53_field_file_sha256": sha(PARENT /
            "q1420_root_theory/n53_field.txt"),
        "n83_field_file_sha256": sha(PARENT /
            "q1420_root_theory/n83_field.txt"),
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "source_sha256": {name: sha(ROOT / name) for name in SOURCE_FILES},
        "measurement_units": {
            "sat_propagations": "exact CaDiCaL reported count",
            "sat_conflicts": "exact CaDiCaL reported count",
            "sat_decisions": "exact CaDiCaL reported count",
            "field_mul_sqr_inv": "native binary-field primitive call counts",
            "wall_ns": "exploratory unisolated native solver-process interval",
        },
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
    current = render()
    if args.check:
        assert current == json.loads(path.read_text())
    else:
        assert not path.exists(), "refuse overwrite"
        path.write_text(json.dumps(current, sort_keys=True, indent=2) +
                        "\n")
    print(json.dumps({"status": "pass", "proposal_id": "Q1472",
                      "cells": len(current["run_order"])}))


if __name__ == "__main__":
    main()
