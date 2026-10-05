#!/usr/bin/env python3
"""Freeze short exact-domain profiles on Q1455's ordinary inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1455 = PARENT / "q1455_joint_tail"
OUTPUT = HERE / "protocol.json"
RUN_ORDER = ("n53_known_sat_unpinned", "n53_ordinary", "n83_ordinary")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_protocol() -> dict:
    control_result = json.loads((HERE / "control_result.json").read_text())
    build = json.loads((HERE / "compile_receipt.json").read_text())
    parent = json.loads((Q1455 / "native_protocol.json").read_text())
    assert control_result["proposal_id"] == build["proposal_id"] == "Q1456"
    assert control_result["status"] == "pass"
    assert build["binary_sha256"] == sha(HERE / "domain_probe")
    assert parent["proposal_id"] == "Q1455"
    cells = {}
    for name in RUN_ORDER:
        previous = parent["cells"][name]
        parent_run = Q1455 / "runs" / name
        receipt = json.loads((parent_run / "receipt.json").read_text())
        assert receipt["workload_id"] == previous["workload_id"]
        assert receipt["cnf_raw_sha256"] == previous["cnf_sha256"]
        for key in ("curve_id", "factor_base_actual_B",
                    "folded_columns_K",
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
            "parent_cnf_archive_sha256": sha(parent_run /
                                              "system.cnf.gz"),
            "pair_candidate_cap": previous["pair_candidate_cap"],
            "conflict_cap": 1000000,
            "wall_cap_seconds": 15,
            "external_safeguard_seconds": 25,
        }
    source_paths = [HERE / name for name in (
        "domain_probe.cpp", "joint_base.cpp", "smoke.py", "build.py",
        "freeze_protocol.py", "run_stage.py", "verify_archive.py")]
    source_paths += [PARENT / name for name in (
        "q1446_joint_pair_span/theory_solver.cpp",
        "q1455_joint_tail/joint_tail.py",
        "q1455_joint_tail/native_inputs.py",
        "q1438_dense_base/verify_solver.py")]
    input_paths = [HERE / name for name in (
        "control_result.json", "compile_receipt.json",
        "sage_runtime_info.json")]
    input_paths += [Q1455 / "native_protocol.json",
                    Q1455 / "native_verification.json"]
    input_paths += [PARENT / f"q1420_root_theory/n{n}_field.txt"
                    for n in (53, 83)]
    for name in RUN_ORDER:
        input_paths += [Q1455 / "runs" / name / leaf for leaf in (
            "receipt.json", "system.cnf.gz", "variables.txt",
            "targets.txt")]
    return {
        "kind": "q1456_exact_joint_domain_profile_protocol",
        "proposal_id": "Q1456", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "method": (
            "instrument Q1455's unchanged joint-tail search to count the "
            "exact number of sparse completions for both pairs at every "
            "distinct partial target-dependent state with unfixed "
            "intermediates; profile the same frozen CNFs under 15-second "
            "diagnostic caps"),
        "controlled_variable": (
            "exact over-cap pair-domain sizes, not a new decomposition "
            "algorithm or a successful-solve timing comparison"),
        "run_order": list(RUN_ORDER), "cells": cells,
        "control_result_sha256": sha(HERE / "control_result.json"),
        "compile_receipt_sha256": sha(HERE / "compile_receipt.json"),
        "binary_sha256": sha(HERE / "domain_probe"),
        "parent_q1455_protocol_sha256": sha(Q1455 / "native_protocol.json"),
        "source_sha256": {str(path.relative_to(ROOT)): sha(path)
                          for path in source_paths},
        "input_sha256": {str(path.relative_to(ROOT)): sha(path)
                         for path in input_paths},
        "cpu_isolation_receipt": None,
        "natural_relation_yield_estimate": None,
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
        print("Q1456 frozen exact-domain protocol: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1456",
                          "run_order": result["run_order"]}))


if __name__ == "__main__":
    main()
