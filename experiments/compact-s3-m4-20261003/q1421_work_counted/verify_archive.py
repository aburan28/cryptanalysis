#!/usr/bin/env python3
"""Audit Q1421 receipts against frozen inputs and exact S3/group laws."""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "q1420_root_theory"
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(PARENT))

from build_formula import build  # noqa: E402
from q1420_root_theory.verify_archive import (  # noqa: E402
    check_cnf, check_math, model_from_file)
from run_probe import sha  # noqa: E402

PROTOCOL = HERE / "protocol.json"


def verify_cell(protocol, key):
    workload = protocol["workloads"][key]
    output = HERE / "runs" / key
    receipt_path = output / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    parent = PARENT / "runs" / workload["parent_key"]
    parent_receipt = json.loads((parent / "receipt.json").read_text())
    assert sha(parent / "receipt.json") == workload["parent_receipt_sha256"]
    assert sha(parent / "meta.json") == workload["parent_meta_sha256"]
    assert sha(parent / "system.cnf.gz") == workload[
        "parent_cnf_archive_sha256"]
    assert sha(parent / "variables.txt") == workload[
        "parent_variable_map_sha256"]
    assert receipt["proposal_id"] == "Q1421"
    assert receipt["candidate_id"] is None and receipt["isogeny"] == "none"
    assert receipt["stage_config_id"] == workload["stage_config_id"]
    assert receipt["workload_id"] == workload["workload_id"]
    assert receipt["stage_run_id"] == workload["stage_run_id"]
    assert receipt["parent_stage_run_id"] == workload["parent_stage_run_id"]
    assert receipt["parent_receipt_sha256"] == sha(parent / "receipt.json")
    assert receipt["parent_cnf_archive_sha256"] == sha(
        parent / "system.cnf.gz")
    assert receipt["curve_id"] == workload["curve_id"]
    assert receipt["factor_base_actual_B"] == workload["factor_base_actual_B"]
    assert receipt["folded_columns_K"] == workload["folded_columns_K"]
    assert receipt["factor_base_enumerated_set_sha256"] == workload[
        "factor_base_enumerated_set_sha256"]
    assert receipt["public_target"] == workload["public_target"]
    assert receipt["decision_policy"] == workload["decision_policy"]
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["runner_source_sha256"] == protocol["source_sha256"][
        "run_stage.py"]
    assert receipt["solver_binary_sha256"] == protocol[
        "solver_binary_sha256"]
    assert receipt["runtime_info_sha256"] == protocol[
        "sage_runtime_info_sha256"]
    assert receipt["solver_stdout_sha256"] == sha(
        output / "solver.stdout.txt")
    assert receipt["solver_stderr_sha256"] == sha(
        output / "solver.stderr.txt")
    raw = gzip.decompress((parent / "system.cnf.gz").read_bytes())
    assert receipt["parent_cnf_raw_sha256"] == parent_receipt[
        "cnf_raw_sha256"]
    report = receipt["solver_report"]
    if report is not None:
        assert report["status"] == {"sat": 10, "censored": 0,
                                     "unsat": 20}[receipt["solver_status"]]
        assert report["decision_policy"] == receipt["decision_policy"]
        assert report["cnf_variables"] == parent_receipt["cnf_variables"]
        assert report["cnf_clauses"] == parent_receipt["cnf_clauses"]
        assert report["cached_pair_assignments"] >= 0
        assert report["field_mul_calls"] >= 0
        assert report["field_sqr_calls"] >= 0
        assert report["field_inv_calls"] >= 0
        assert report["s3_root_calls"] >= 0
    if receipt["solver_status"] == "sat":
        assert receipt["solver_model_sha256"] == sha(
            output / "solver.model.txt")
        model = model_from_file(output / "solver.model.txt")
        check_cnf(raw, model, parent_receipt["cnf_variables"],
                  parent_receipt["cnf_clauses"])
        n, cell = receipt["degree_n"], receipt["cell"]
        formula, _ = build(n, "ordinary" if cell == "ordinary" else
                           "control", cell)
        meta = json.loads((parent / "meta.json").read_text())
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


def main():
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
        "kind": "q1421_archive_verification",
        "proposal_id": "Q1421",
        "protocol_sha256": sha(PROTOCOL),
        "verifier_source_sha256": sha(Path(__file__)),
        "checks": checks, "missing": missing, "complete": not missing,
        "natural_relation_yield_estimate": None,
        "complete_solve_work_log2": None,
    }
    if args.emit:
        (HERE / "verification.json").write_text(json.dumps(
            report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"checked": len(checks), "missing": missing,
                      "verified_relations": sum(row[
                          "verified_relation_count"] for row in checks)}))


if __name__ == "__main__":
    main()
