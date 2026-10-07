#!/usr/bin/env python3
"""Rebuild Q1483 inputs and independently audit every frozen run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_formula import HERE, build_cnf
from prepare_inputs import prepare
from run_stage import BINARY, PROTOCOL, sha
from verify_model import model_relation


def audit_one(case: str, protocol: dict) -> dict:
    entry = protocol["cases"][case]
    assert prepare(case, True)["status"] == "checked"
    output = HERE / "runs" / case
    receipt_path = output / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["proposal_id"] == "Q1483"
    assert receipt["candidate_id"] is receipt["run_id"] is None
    assert receipt["isogeny"] == "none"
    assert receipt["case"] == case
    assert receipt["stage_config_id"] == entry["stage_config_id"]
    assert receipt["stage_run_id"] == entry["stage_run_id"]
    assert receipt["workload_id"] == entry["workload_id"]
    assert receipt["parent_workload_id"] == entry["parent_workload_id"]
    assert receipt["curve_id"] == entry["curve_id"]
    assert receipt["factor_base_actual_B"] == entry[
        "factor_base_actual_B"]
    assert receipt["folded_columns_K"] == entry["folded_columns_K"]
    assert receipt["factor_base_enumerated_set_sha256"] == entry[
        "factor_base_enumerated_set_sha256"]
    assert receipt["cnf_raw_sha256"] == entry["cnf_raw_sha256"]
    assert receipt["input_sha256"] == entry["input_sha256"]
    assert receipt["input_receipt_sha256"] == entry[
        "input_receipt_sha256"]
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["solver_binary_sha256"] == sha(BINARY)
    assert receipt["runner_source_sha256"] == protocol["source_sha256"][
        "experiments/compact-s3-m4-20261003/q1483_fixed_window_s3/run_stage.py"]
    assert receipt["runtime_info_sha256"] == protocol[
        "runtime_info_sha256"]
    assert receipt["solver_stdout_sha256"] == sha(output /
                                                   "solver.stdout.txt")
    assert receipt["solver_stderr_sha256"] == sha(output /
                                                   "solver.stderr.txt")
    assert receipt["charged_stage_wall_ns_exploratory"] == sum(
        receipt[name] for name in (
            "target_encoding_wall_ns_exploratory",
            "input_materialization_wall_ns_exploratory",
            "solver_process_wall_ns_exploratory",
            "relation_check_wall_ns_exploratory"))
    assert receipt["natural_relation_yield_estimate"] is None
    assert receipt["complete_n131_log2_work"] is None
    assert receipt["challenge_run_admitted"] is False
    status = receipt["native_status"]
    assert status in ("sat", "censored", "unsat", "error",
                      "external_timeout")
    if status in ("sat", "censored", "unsat"):
        report = receipt["native_report"]
        assert receipt["native_report_error"] is None
        assert report is not None
        assert report["cnf_variables"] == entry["cnf_variables"]
        assert report["cnf_clauses"] == entry["cnf_clauses"]
        assert report["target_preimage_count"] == entry[
            "target_preimage_x_count"]
        assert report["propagations"] >= 0
    else:
        report = receipt["native_report"]
    if status == "sat":
        model_path = output / "solver.model.txt"
        assert receipt["solver_model_sha256"] == sha(model_path)
        n = entry["degree_n"]
        raw, _, _, formula, meta, variables, clauses = build_cnf(
            n, entry["role"])
        checked = model_relation(raw, formula, meta, variables,
                                 clauses, model_path)
        assert checked == receipt["independent_model_check"]
        assert receipt["independent_model_check_error"] is None
        assert receipt["verified_relation_count"] == int(
            checked["status"] == "verified_four_point_relation")
        outcome = checked["status"]
    else:
        assert receipt["solver_model_sha256"] is None
        assert receipt["verified_relation_count"] == 0
        assert receipt["independent_model_check"] is None
        outcome = status
    return {
        "case": case, "degree_n": entry["degree_n"],
        "role": entry["role"], "status": status, "outcome": outcome,
        "verified_relation_count": receipt["verified_relation_count"],
        "sat_propagations": (report or {}).get("propagations"),
        "sat_conflicts": (report or {}).get("conflicts"),
        "field_mul_calls": (report or {}).get("field_mul_calls"),
        "field_sqr_calls": (report or {}).get("field_sqr_calls"),
        "field_inv_calls": (report or {}).get("field_inv_calls"),
        "charged_stage_wall_ns_exploratory": receipt[
            "charged_stage_wall_ns_exploratory"],
        "peak_child_rss_raw": receipt["peak_child_rss_raw"],
        "receipt_sha256": sha(receipt_path),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1483"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    rows = [audit_one(case, protocol) for case in protocol["run_order"]]
    assert [row["case"] for row in rows] == protocol["run_order"]
    assert rows[0]["verified_relation_count"] == 1
    assert rows[1]["verified_relation_count"] == 1
    n83_ordinary = next(row for row in rows if row["case"] ==
                        "n83_ordinary")
    result = {
        "kind": "q1483_fixed_window_compact_s3_archive_audit",
        "proposal_id": "Q1483", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "protocol_sha256": sha(PROTOCOL), "rows": rows,
        "pinned_correctness_controls_passed": True,
        "ordinary_verified_relations": sum(
            row["verified_relation_count"] for row in rows
            if row["role"] == "ordinary"),
        "successful_n83_ordinary_stage_wall_ns_exploratory": (
            n83_ordinary["charged_stage_wall_ns_exploratory"]
            if n83_ordinary["verified_relation_count"] else None),
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "status": "passed",
    }
    path = HERE / "archive_audit.json"
    if args.check or path.exists():
        assert json.loads(path.read_text()) == result
        print("Q1483 archive audit PASS (archived)")
    else:
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print("Q1483 archive audit PASS")


if __name__ == "__main__":
    main()
