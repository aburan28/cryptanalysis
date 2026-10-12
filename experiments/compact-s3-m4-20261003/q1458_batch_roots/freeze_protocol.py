#!/usr/bin/env python3
"""Freeze Q1458's batched roots against Q1457's exact solver inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1455 = PARENT / "q1455_joint_tail"
Q1456 = PARENT / "q1456_joint_domain_profile"
Q1457 = PARENT / "q1457_joint_cap4096"
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
    baseline = json.loads((Q1457 / "protocol.json").read_text())
    build = json.loads((HERE / "compile_receipt.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert controls["proposal_id"] == build["proposal_id"] == "Q1458"
    assert controls["status"] == "pass"
    assert controls["pair_candidate_cap"] == PAIR_CAP
    assert parent["proposal_id"] == "Q1455"
    assert profile["proposal_id"] == "Q1456" and profile["status"] == "pass"
    assert baseline["proposal_id"] == "Q1457"
    assert baseline["run_order"] == list(RUN_ORDER)
    assert runtime["status"] == "verified"
    binary = HERE / "native_batch_solver"
    assert controls["binary_sha256"] == build[
        "solver_binary_sha256"] == sha(binary)
    assert build["smoke_binary_sha256"] == sha(HERE / "smoke_roots")
    for n in (53, 83):
        expected = (HERE / f"smoke_n{n}.jsonl").read_text()
        observed = subprocess.run(
            [str(HERE / "smoke_roots"),
             str(PARENT / f"q1420_root_theory/n{n}_field.txt")],
            check=True, capture_output=True, text=True).stdout
        assert observed == expected
        smoke_rows = [json.loads(line) for line in expected.splitlines()]
        assert [row["inputs"] for row in smoke_rows] == [1, 32, 512, 4096]
        assert smoke_rows[-1]["batch_inv"] == 2
        assert smoke_rows[-1]["serial_inv"] > 6000
    rows = {row["case"]: row for row in profile["rows"]}
    cells = {}
    for name in RUN_ORDER:
        previous = parent["cells"][name]
        parent_run = Q1455 / "runs" / name
        receipt = json.loads((parent_run / "receipt.json").read_text())
        baseline_run = Q1457 / "runs" / name
        baseline_receipt = json.loads((baseline_run / "receipt.json").read_text())
        assert receipt["workload_id"] == previous["workload_id"]
        assert receipt["cnf_raw_sha256"] == previous["cnf_sha256"]
        assert baseline_receipt["solver_status"] == "censored"
        assert baseline_receipt["workload_id"] == previous["workload_id"]
        assert baseline["cells"][name]["pair_candidate_cap"] == PAIR_CAP
        assert baseline["cells"][name]["cnf_sha256"] == previous[
            "cnf_sha256"]
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
            "baseline_q1457_receipt_sha256": sha(baseline_run /
                                                  "receipt.json"),
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
        "native_batch_solver.cpp", "batch_roots.hpp", "smoke_roots.cpp",
        "build.py", "run_controls.py", "run_stage.py",
        "verify_archive.py", "freeze_protocol.py")]
    source_paths += [PARENT / name for name in (
        "q1455_joint_tail/native_joint_solver.cpp",
        "q1455_joint_tail/joint_tail.py",
        "q1455_joint_tail/native_inputs.py",
        "q1438_dense_base/verify_solver.py",
        "q1446_joint_pair_span/theory_solver.cpp")]
    input_paths = [HERE / name for name in (
        "control_result.json", "compile_receipt.json",
        "smoke_n53.jsonl", "smoke_n83.jsonl",
        "sage_runtime_info.json")]
    input_paths += [Q1455 / "native_protocol.json",
                    Q1455 / "native_compile_receipt.json",
                    Q1456 / "threshold_interpretation.json",
                    Q1456 / "verification.json",
                    Q1457 / "protocol.json",
                    Q1457 / "verification.json"]
    input_paths += [PARENT / f"q1420_root_theory/n{n}_field.txt"
                    for n in (53, 83)]
    for name in RUN_ORDER:
        input_paths += [Q1455 / "runs" / name / leaf for leaf in (
            "receipt.json", "system.cnf.gz", "variables.txt",
            "targets.txt")]
        input_paths.append(Q1457 / "runs" / name / "receipt.json")
    return {
        "kind": "q1458_batched_s3_root_protocol",
        "proposal_id": "Q1458", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "method": (
            "reuse Q1457's exact CNFs, target points, decision policy, "
            "pair cap 4096, and resource caps; compute each joint S3 "
            "pair-root set with batched inversions instead of serial "
            "per-root inversions"),
        "controlled_variable": "joint-rule S3 root evaluation only",
        "decision_policy": "joint_tail_leaf_interleave",
        "run_order": list(RUN_ORDER), "cells": cells,
        "control_result_sha256": sha(HERE / "control_result.json"),
        "binary_sha256": sha(binary),
        "compile_receipt_sha256": sha(HERE / "compile_receipt.json"),
        "parent_q1455_protocol_sha256": sha(Q1455 / "native_protocol.json"),
        "baseline_q1457_protocol_sha256": sha(Q1457 / "protocol.json"),
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
        print("Q1458 frozen batched-root protocol: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1458",
                          "run_order": result["run_order"]}))


if __name__ == "__main__":
    main()
