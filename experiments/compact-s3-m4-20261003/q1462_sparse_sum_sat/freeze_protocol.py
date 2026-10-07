#!/usr/bin/env python3
"""Freeze Q1462's exact-base N53/N83 ordinary SAT comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1438 = PARENT / "q1438_dense_base"
Q1446 = PARENT / "q1446_joint_pair_span"
Q1461 = PARENT / "q1461_sparse_sum_inverse"
OUTPUT = HERE / "protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_protocol() -> dict:
    prior = json.loads((Q1446 / "protocol.json").read_text())
    parent = json.loads((Q1438 / "solver_protocol.json").read_text())
    controls = json.loads((HERE / "control_result.json").read_text())
    build = json.loads((HERE / "compile_receipt.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    q1461 = json.loads((Q1461 / "result.json").read_text())
    assert prior["proposal_id"] == "Q1446"
    assert parent["proposal_id"] == "Q1438"
    assert controls["proposal_id"] == build["proposal_id"] == "Q1462"
    assert controls["status"] == "pass"
    assert q1461["proposal_id"] == "Q1461"
    assert runtime["status"] == "verified"
    binary_sha = sha(HERE / "native_solver")
    assert build["binary_sha256"]["native_solver"] == binary_sha
    assert controls["solver_binary_sha256"] == binary_sha
    assert controls["solver_source_sha256"] == sha(HERE / "native_solver.cpp")
    assert all(row["direct_guard_control"]["positive_exact_pairs"] > 0
               and row["direct_guard_control"]["negative_guard_literals"] >
               row["degree_n"] for row in controls["rows"])
    source_paths = [HERE / name for name in (
        "native_solver.cpp", "control_guard.cpp", "build.py",
        "validate_controls.py", "freeze_protocol.py", "run_stage.py",
        "verify_archive.py")]
    source_paths += [PARENT / name for name in (
        "q1461_sparse_sum_inverse/sparse_sum.hpp",
        "q1446_joint_pair_span/theory_solver.cpp",
        "q1438_dense_base/build_formula.py",
        "q1438_dense_base/verify_solver.py",
        "q1432_coefficient_cache/cached_span.hpp",
        "q1431_guarded_span/span_filter.hpp",
        "q1423_target_coupled/target_inputs.py",
        "q1422_leaf_lift_gate/lift_gate.hpp",
        "q1420_root_theory/root_field.hpp",
        "chain_s3.py")]
    input_paths = [HERE / name for name in (
        "compile_receipt.json", "control_result.json",
        "sage_runtime_info.json")]
    input_paths += [Q1438 / "solver_protocol.json",
                    Q1446 / "protocol.json",
                    Q1461 / "protocol.json", Q1461 / "result.json",
                    Q1461 / "compile_receipt.json"]
    for n in (53, 83):
        input_paths += [
            Q1438 / f"n{n}_w{4 if n == 53 else 6}_base.json",
            Q1446 / f"runs/n{n}_ordinary/receipt.json",
            Q1446 / f"runs/n{n}_ordinary/variables.txt",
            Q1446 / f"runs/n{n}_ordinary/targets.txt",
            Q1461 / f"n{n}_inputs.txt",
            PARENT / f"q1420_root_theory/n{n}_field.txt",
        ]
    cells = {}
    for n in (53, 83):
        original = prior["cells"][str(n)]
        workload = parent["workloads"][f"n{n}_ordinary"]
        baseline = json.loads((Q1446 /
            f"runs/n{n}_ordinary/receipt.json").read_text())
        for key in ("curve_id", "factor_base_actual_B", "folded_columns_K",
                    "factor_base_enumerated_set_sha256", "public_target",
                    "cnf_raw_sha256", "variable_map_sha256",
                    "target_input_sha256"):
            assert original[key] == workload[key] == baseline[key], key
        assert baseline["solver_status"] == "censored"
        assert baseline["verified_relation_count"] == 0
        assert original["matched_q1438_workload_id"] == workload[
            "workload_id"]
        cells[str(n)] = {
            key: original[key] for key in (
                "curve_id", "cofactor", "subgroup_order", "field", "curve",
                "factor_base_actual_B", "folded_columns_K",
                "factor_base_enumerated_set_sha256",
                "factor_base_receipt_sha256", "weight_bound",
                "public_target", "target_preimage_x_count",
                "cnf_raw_sha256", "cnf_raw_bytes", "cnf_variables",
                "cnf_clauses", "variable_map_sha256",
                "target_input_sha256", "solver_conflict_cap",
                "solver_wall_cap_seconds",
                "external_process_safeguard_seconds")}
        cells[str(n)].update({
            "workload_id": workload["workload_id"],
            "matched_q1438_workload_id": workload["workload_id"],
            "baseline_q1446_workload_id": original["workload_id"],
            "baseline_q1446_receipt_sha256": sha(Q1446 /
                f"runs/n{n}_ordinary/receipt.json"),
            "sum_candidate_cap": 100000,
            "input_role": "ordinary_full_target",
            "target_count": 1,
        })
    return {
        "kind": "q1462_sparse_sum_sat_protocol",
        "proposal_id": "Q1462", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "method": (
            "Q1446 target-linked mids-first chained-S3 SAT policy plus "
            "Q1461 exact fixed-nonzero-midpoint sparse-sum no-pair guard "
            "on both partial leaf pairs; zero midpoints use Q1446's "
            "complete/reverse exact rules"),
        "policy": "sparse_sum_joint_pair_span",
        "controlled_variable": (
            "add the Q1461 sum-domain guard under its 100000-sum cap; "
            "retain Q1446 ordinary inputs, decision order, and limits"),
        "run_order": ["n53_ordinary", "n83_ordinary"],
        "cells": cells,
        "source_sha256": {str(p.relative_to(ROOT)): sha(p)
                          for p in source_paths},
        "input_sha256": {str(p.relative_to(ROOT)): sha(p)
                         for p in input_paths},
        "solver_binary_sha256": binary_sha,
        "compile_receipt_sha256": sha(HERE / "compile_receipt.json"),
        "control_result_sha256": sha(HERE / "control_result.json"),
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "cpu_isolation_receipt": None,
        "natural_relation_yield_estimate": None,
        "cost_per_useful_row": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = make_protocol()
    if args.check:
        assert result == json.loads(OUTPUT.read_text())
        print("Q1462 frozen protocol: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1462", "status": "frozen",
                          "workloads": {n: c["workload_id"]
                                        for n, c in result["cells"].items()}}))


if __name__ == "__main__":
    main()
