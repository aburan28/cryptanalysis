#!/usr/bin/env python3
"""Independently audit Q1486's exact-window inputs and six stage attempts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1482 = HERE.parent / "q1482_window_s3"
sys.path.insert(0, str(Q1482))
from build_formula import build_cnf  # noqa: E402
from prepare_inputs import prepare
from verify_model import model_relation
from prepare_window_maps import render as render_window_map  # noqa: E402

ROOT = HERE.parents[2]
BINARY = HERE / "native_solver"
PROTOCOL = HERE / "protocol.json"


def sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_one(case: str, protocol: dict) -> dict:
    entry = protocol["cases"][case]
    assert prepare(case, True)["status"] == "checked"
    output = HERE / "runs" / case
    receipt_path = output / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["proposal_id"] == "Q1486"
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
    window_dir = HERE / "inputs" / case
    window_map = window_dir / "windows.map"
    window_receipt = window_dir / "map_receipt.json"
    assert receipt["window_sidecar_sha256"] == sha(window_map) == (
        entry["window_sidecar_sha256"])
    assert receipt["window_sidecar_receipt_sha256"] == sha(
        window_receipt) == entry["window_sidecar_receipt_sha256"]
    rebuilt_map, rebuilt_receipt = render_window_map(
        case, json.loads((Q1482 / "protocol.json").read_text()))
    assert window_map.read_bytes() == rebuilt_map
    assert json.loads(window_receipt.read_text()) == rebuilt_receipt
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["solver_binary_sha256"] == sha(BINARY)
    assert receipt["runner_source_sha256"] == protocol["source_sha256"][
        "experiments/compact-s3-m4-20261003/q1486_window_aware_pair/run_stage.py"]
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
        assert report["window_selector_count"] == 4 * entry["degree_n"]
        assert report["decision_policy"] == protocol["decision_policy"]
        assert report["propagations"] >= 0
    else:
        report = receipt["native_report"]
    if status == "sat":
        model_path = output / "solver.model.txt"
        assert receipt["solver_model_sha256"] == sha(model_path)
        n = entry["degree_n"]
        raw, _, _, formula, meta, variables, clauses = build_cnf(
            n, entry["role"])
        try:
            checked = model_relation(raw, formula, meta, variables,
                                     clauses, model_path)
            check_error = None
        except Exception as error:
            checked, check_error = None, repr(error)
        assert checked == receipt["independent_model_check"]
        assert check_error == receipt["independent_model_check_error"]
        assert receipt["verified_relation_count"] == int(
            checked is not None and
            checked.get("status") == "verified_four_point_relation")
        outcome = checked["status"] if checked else "unverified_sat_model"
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
        "forced_window_decisions": (report or {}).get(
            "forced_window_decisions"),
        "window_option_values_enumerated": (report or {}).get(
            "window_option_values_enumerated"),
        "coupled_eligible_checks": (report or {}).get(
            "coupled_eligible_checks"),
        "coupled_rejections": (report or {}).get(
            "coupled_rejections"),
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
    assert protocol["proposal_id"] == "Q1486"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert sha(Q1482 / "protocol.json") == protocol[
        "parent_q1482_protocol_sha256"]
    assert sha(BINARY) == protocol["solver_binary_sha256"]
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    rows = [audit_one(case, protocol) for case in protocol["run_order"]]
    assert [row["case"] for row in rows] == protocol["run_order"]
    pinned_passed = rows[0]["verified_relation_count"] == 1 and (
        rows[1]["verified_relation_count"] == 1)
    n83_ordinary = next(row for row in rows if row["case"] ==
                        "n83_ordinary")
    result = {
        "kind": "q1486_exact_window_compact_s3_archive_audit",
        "proposal_id": "Q1486", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "protocol_sha256": sha(PROTOCOL), "rows": rows,
        "audit_source_sha256": sha(Path(__file__)),
        "pinned_correctness_controls_passed": pinned_passed,
        "ordinary_verified_relations": sum(
            row["verified_relation_count"] for row in rows
            if row["role"] == "ordinary"),
        "successful_n83_ordinary_stage_wall_ns_exploratory": (
            n83_ordinary["charged_stage_wall_ns_exploratory"]
            if n83_ordinary["verified_relation_count"] else None),
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "status": "passed" if pinned_passed else "failed_controls",
    }
    path = HERE / "archive_audit.json"
    if args.check or path.exists():
        assert json.loads(path.read_text()) == result
        print("Q1486 archive audit checked (archived)")
    else:
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print("Q1486 archive audit checked")


if __name__ == "__main__":
    main()
