#!/usr/bin/env python3
"""Freeze the Q1457 cap-only change before ordinary-query measurements."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1455 = PARENT / "q1455_joint_tail"
Q1456 = PARENT / "q1456_joint_domain_profile"
OUTPUT = HERE / "protocol.json"
RUN_ORDER = ("n53_known_sat_unpinned", "n53_ordinary", "n83_ordinary")
PAIR_CAP = 4096


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make_protocol() -> dict:
    controls = json.loads((HERE / "control_result.json").read_text())
    parent = json.loads((Q1455 / "native_protocol.json").read_text())
    profile = json.loads((Q1456 / "threshold_interpretation.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert controls["proposal_id"] == "Q1457" and controls["status"] == "pass"
    assert controls["pair_candidate_cap"] == PAIR_CAP
    assert parent["proposal_id"] == "Q1455"
    assert profile["proposal_id"] == "Q1456" and profile["status"] == "pass"
    assert runtime["status"] == "verified"
    binary = Q1455 / "native_joint_solver"
    assert controls["binary_sha256"] == parent["native_binary_sha256"] == sha(binary)
    rows = {row["case"]: row for row in profile["rows"]}
    cells = {}
    for name in RUN_ORDER:
        previous = parent["cells"][name]
        parent_run = Q1455 / "runs" / name
        receipt = json.loads((parent_run / "receipt.json").read_text())
        assert receipt["workload_id"] == previous["workload_id"]
        assert receipt["cnf_raw_sha256"] == previous["cnf_sha256"]
        assert rows[name]["workload_id"] == previous["workload_id"]
        assert rows[name]["eligible_unique_states_by_pair_cap"][str(PAIR_CAP)] > 0
        for key in ("curve_id", "factor_base_actual_B", "folded_columns_K",
                    "factor_base_enumerated_set_sha256", "public_target"):
            assert receipt[key] == previous[key], key
        cells[name] = {
            "degree_n": previous["degree_n"],
            "input_role": previous["input_role"],
            "curve_id": previous["curve_id"],
            "factor_base_actual_B": previous["factor_base_actual_B"],
            "folded_columns_K": previous["folded_columns_K"],
            "factor_base_enumerated_set_sha256": previous[
                "factor_base_enumerated_set_sha256"],
            "normal_basis_weight_bound": previous[
                "normal_basis_weight_bound"],
            "public_target": previous["public_target"],
            "workload_id": previous["workload_id"],
            "cnf_sha256": previous["cnf_sha256"],
            "cnf_variables": previous["cnf_variables"],
            "cnf_clauses": previous["cnf_clauses"],
            "variable_map_sha256": previous["variable_map_sha256"],
            "targets_sha256": previous["targets_sha256"],
            "parent_receipt_sha256": sha(parent_run / "receipt.json"),
            "parent_cnf_archive_sha256": sha(parent_run / "system.cnf.gz"),
            "profile_unique_states_admitted": rows[name][
                "eligible_unique_states_by_pair_cap"][str(PAIR_CAP)],
            "pair_candidate_cap": PAIR_CAP,
            "conflict_cap": previous["solver_conflict_cap"],
            "wall_cap_seconds": previous["solver_wall_cap_seconds"],
            "external_safeguard_seconds": previous[
                "external_process_safeguard_seconds"],
        }
    source_paths = [HERE / name for name in (
        "run_controls.py", "run_stage.py", "verify_archive.py",
        "freeze_protocol.py")]
    source_paths += [PARENT / name for name in (
        "q1455_joint_tail/native_joint_solver.cpp",
        "q1455_joint_tail/joint_tail.py",
        "q1455_joint_tail/native_inputs.py",
        "q1438_dense_base/verify_solver.py",
        "q1446_joint_pair_span/theory_solver.cpp")]
    input_paths = [HERE / name for name in (
        "control_result.json", "sage_runtime_info.json")]
    input_paths += [Q1455 / "native_protocol.json",
                    Q1455 / "native_compile_receipt.json",
                    Q1456 / "threshold_interpretation.json",
                    Q1456 / "verification.json"]
    input_paths += [PARENT / f"q1420_root_theory/n{n}_field.txt"
                    for n in (53, 83)]
    for name in RUN_ORDER:
        input_paths += [Q1455 / "runs" / name / leaf for leaf in (
            "receipt.json", "system.cnf.gz", "variables.txt",
            "targets.txt")]
    return {
        "kind": "q1457_joint_tail_cap4096_protocol",
        "proposal_id": "Q1457", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "method": (
            "reuse the exact Q1455 joint-tail solver, CNFs, target points, "
            "decision policy, and resource caps; change only the maximum "
            "pair completion product from 256/1024 to 4096"),
        "controlled_variable": "pair completion cap only",
        "decision_policy": "joint_tail_leaf_interleave",
        "run_order": list(RUN_ORDER), "cells": cells,
        "control_result_sha256": sha(HERE / "control_result.json"),
        "binary_sha256": sha(binary),
        "parent_q1455_protocol_sha256": sha(Q1455 / "native_protocol.json"),
        "profile_q1456_threshold_sha256": sha(Q1456 /
                                              "threshold_interpretation.json"),
        "source_sha256": {str(path.relative_to(ROOT)): sha(path)
                          for path in source_paths},
        "input_sha256": {str(path.relative_to(ROOT)): sha(path)
                         for path in input_paths},
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
        print("Q1457 frozen cap-4096 protocol: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1457",
                          "run_order": result["run_order"]}))


if __name__ == "__main__":
    main()
