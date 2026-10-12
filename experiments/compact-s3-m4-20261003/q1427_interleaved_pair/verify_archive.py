#!/usr/bin/env python3
"""Verify Q1427's exact CNFs, solver receipts, and any returned relations."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1420 = PARENT / "q1420_root_theory"
Q1426 = PARENT / "q1426_symbolic_pair"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(Q1420))

from q1420_root_theory.verify_archive import (  # noqa: E402
    check_cnf, check_math, model_from_file)
from q1426_symbolic_pair.build_formula import build_cnf  # noqa: E402

PROTOCOL = HERE / "protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_cell(protocol: dict, key: str) -> dict:
    workload = protocol["workloads"][key]
    output = HERE / "runs" / key
    receipt_path = output / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    n, cell = receipt["degree_n"], receipt["cell"]
    assert key == f"n{n}_{cell}"
    assert receipt["proposal_id"] == "Q1427"
    assert receipt["candidate_id"] is None
    assert receipt["isogeny"] == "none"
    for name in ("curve_id", "factor_base_actual_B", "folded_columns_K",
                 "factor_base_enumerated_set_sha256", "public_target",
                 "stage_config_id", "workload_id", "stage_run_id",
                 "target_input_sha256", "target_preimage_x_count",
                 "removed_partner_pin_units"):
        assert receipt[name] == workload[name]
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["runner_source_sha256"] == protocol["source_sha256"][
        "run_stage.py"]
    assert receipt["solver_binary_sha256"] == protocol[
        "solver_binary_sha256"]
    assert receipt["runtime_info_sha256"] == protocol[
        "sage_runtime_info_sha256"]
    parent_path = (Q1420 / "runs" / workload["parent_q1420_key"] /
                   "receipt.json")
    assert sha(parent_path) == workload[
        "parent_q1420_receipt_sha256"] == receipt[
            "parent_q1420_receipt_sha256"]
    matched_path = (Q1426 / "runs" / workload["matched_q1426_key"] /
                    "receipt.json")
    assert sha(matched_path) == workload[
        "matched_q1426_receipt_sha256"] == receipt[
            "matched_q1426_receipt_sha256"]
    matched = json.loads(matched_path.read_text())
    assert matched["stage_run_id"] == receipt[
        "matched_q1426_stage_run_id"] == workload[
            "matched_q1426_stage_run_id"]
    for name in ("workload_id", "curve_id", "factor_base_actual_B",
                 "folded_columns_K", "factor_base_enumerated_set_sha256",
                 "public_target", "target_input_sha256"):
        assert matched[name] == receipt[name]
    raw, formula, meta, removed, variables, clauses = build_cnf(n, cell)
    assert sha(output / "solver.stdout.txt") == receipt[
        "solver_stdout_sha256"]
    assert sha(output / "solver.stderr.txt") == receipt[
        "solver_stderr_sha256"]
    assert hashlib.sha256(raw).hexdigest() == receipt[
        "cnf_raw_sha256"] == workload["cnf_raw_sha256"]
    assert len(raw) == workload["cnf_raw_bytes"]
    assert variables == receipt["cnf_variables"] == workload["cnf_variables"]
    assert clauses == receipt["cnf_clauses"] == workload["cnf_clauses"]
    assert removed == workload["removed_partner_pin_units"]
    assert meta["curve_id"] == workload["curve_id"]
    report = receipt["solver_report"]
    if report is not None:
        assert report["status"] == {"sat": 10, "censored": 0,
                                     "unsat": 20}[receipt["solver_status"]]
        assert report["decision_policy"] == "interleave_pair1"
        assert report["target_coupled_active"] is True
        assert report["reverse_pair_active"] is True
        assert report["cnf_variables"] == variables
        assert report["cnf_clauses"] == clauses
        assert report["target_preimage_count"] == workload[
            "target_preimage_x_count"]
        assert report["cached_pair_assignments"] == (
            report["pair0_root_calls"] + report["pair1_root_calls"])
        assert report["cached_reverse_assignments"] == (
            report["reverse_pair0_calls"] + report["reverse_pair1_calls"])
        assert report["cached_reverse_assignments"] == (
            report["reverse_zero_candidates"] +
            report["reverse_one_candidate"] +
            report["reverse_two_candidates"])
    if receipt["solver_status"] == "sat":
        assert receipt["solver_model_sha256"] == sha(
            output / "solver.model.txt")
        model = model_from_file(output / "solver.model.txt")
        check_cnf(raw, model, variables, clauses)
        relation = check_math(formula, meta, model)
        assert relation == receipt["model_check"]
        assert receipt["verified_relation_count"] == int(
            relation["status"] == "verified_four_point_relation")
    else:
        assert receipt["solver_model_sha256"] is None
        assert receipt["model_check"] is None
        assert receipt["verified_relation_count"] == 0
        assert receipt["solver_status"] in ("censored", "external_timeout",
                                            "unsat", "error")
    assert receipt["natural_relation_yield_estimate"] is None
    assert receipt["complete_solve_work_log2"] is None
    return {
        "key": key, "status": receipt["solver_status"],
        "verified_relation_count": receipt["verified_relation_count"],
        "solver_process_wall_seconds_exploratory": receipt[
            "solver_process_wall_seconds_exploratory"],
        "receipt_sha256": sha(receipt_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--emit", action="store_true")
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["source_sha256"]["verify_archive.py"] == sha(
        Path(__file__))
    checks, missing = [], []
    for key in protocol["run_order"]:
        if (HERE / "runs" / key / "receipt.json").exists():
            checks.append(verify_cell(protocol, key))
        else:
            missing.append(key)
    assert not args.require_complete or not missing
    report = {
        "kind": "q1427_interleaved_second_pair_archive_verification",
        "proposal_id": "Q1427", "candidate_id": None,
        "protocol_sha256": sha(PROTOCOL),
        "verifier_source_sha256": sha(Path(__file__)),
        "checks": checks, "missing": missing, "complete": not missing,
        "natural_relation_yield_estimate": None,
        "complete_solve_work_log2": None,
    }
    if args.emit:
        (HERE / "verification.json").write_text(json.dumps(
            report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"checked": len(checks), "missing": missing,
                      "verified_relations": sum(row[
                          "verified_relation_count"] for row in checks)}))


if __name__ == "__main__":
    main()
