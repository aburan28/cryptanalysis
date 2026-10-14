#!/usr/bin/env python3
"""Run one frozen Q1432 cached-span solver cell."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1420 = PARENT / "q1420_root_theory"
Q1426 = PARENT / "q1426_symbolic_pair"
Q1427 = PARENT / "q1427_interleaved_pair"
Q1430 = PARENT / "q1430_partial_trail"
Q1431 = PARENT / "q1431_guarded_span"
Q1423 = PARENT / "q1423_target_coupled"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(Q1420))

from q1420_root_theory.verify_archive import (  # noqa: E402
    check_cnf, check_math, model_from_file)
from q1423_target_coupled.target_inputs import (  # noqa: E402
    encode_targets, target_list)
from q1426_symbolic_pair.build_formula import build_cnf  # noqa: E402

PROTOCOL = HERE / "protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    parser.add_argument("--cell", choices=("free_partner", "ordinary"),
                        required=True)
    args = parser.parse_args()
    key = f"n{args.degree}_{args.cell}"
    protocol = json.loads(PROTOCOL.read_text())
    workload = protocol["workloads"][key]
    assert key in protocol["run_order"]
    assert protocol["proposal_id"] == "Q1432"
    for name, digest in protocol["source_sha256"].items():
        assert sha(HERE / name) == digest
    from q1432_coefficient_cache.freeze_protocol import DEPENDENCIES
    for name, digest in protocol["dependency_sha256"].items():
        assert sha(DEPENDENCIES[name]) == digest
    assert sha(Q1420 / "protocol.json") == protocol[
        "parent_q1420_protocol_sha256"]
    assert sha(Q1431 / "protocol.json") == protocol[
        "matched_q1431_protocol_sha256"]
    assert sha(PARENT / "q1429_unsaturated_span/protocol.json") == protocol[
        "q1429_protocol_sha256"]
    assert sha(HERE / "compile_receipt.json") == protocol[
        "compile_receipt_sha256"]
    assert sha(HERE / "cache_validation.json") == protocol[
        "cache_validation_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "sage_runtime_info_sha256"]
    binary = HERE / "theory_solver"
    assert sha(binary) == protocol["solver_binary_sha256"]
    matched = Q1431 / "runs" / workload["matched_q1431_key"]
    matched_path = matched / "receipt.json"
    assert sha(matched_path) == workload["matched_q1431_receipt_sha256"]
    matched_receipt = json.loads(matched_path.read_text())
    assert matched_receipt["stage_run_id"] == workload[
        "matched_q1431_stage_run_id"]
    parent = Q1420 / "runs" / workload["parent_q1420_key"]
    parent_path = parent / "receipt.json"
    assert sha(parent_path) == workload["parent_q1420_receipt_sha256"]
    parent_protocol = json.loads((Q1420 / "protocol.json").read_text())
    parent_workload = parent_protocol["workloads"][workload[
        "parent_q1420_key"]]
    target_bytes = encode_targets(args.degree, target_list(
        args.degree, "free_mids" if args.cell == "free_partner" else
        "ordinary", parent_workload))
    assert hashlib.sha256(target_bytes).hexdigest() == workload[
        "target_input_sha256"]
    build_start = time.perf_counter()
    raw, formula, meta, removed, variables, clauses = build_cnf(
        args.degree, args.cell)
    build_seconds = time.perf_counter() - build_start
    assert hashlib.sha256(raw).hexdigest() == workload["cnf_raw_sha256"]
    assert len(raw) == workload["cnf_raw_bytes"]
    assert variables == workload["cnf_variables"]
    assert clauses == workload["cnf_clauses"]
    assert removed == workload["removed_partner_pin_units"]
    assert meta["curve_id"] == workload["curve_id"]
    assert meta["factor_base_actual_B"] == workload[
        "factor_base_actual_B"]
    assert meta["folded_columns_K"] == workload["folded_columns_K"]
    assert meta["factor_base_enumerated_set_sha256"] == workload[
        "factor_base_enumerated_set_sha256"]
    output = HERE / "runs" / key
    assert not output.exists()
    output.mkdir(parents=True)
    cnf_path = output / "system.cnf"
    target_path = output / "targets.txt"
    model_path = output / "solver.model.txt"
    cnf_path.write_bytes(raw)
    target_path.write_bytes(target_bytes)
    command = [str(binary), str(Q1420 / f"n{args.degree}_field.txt"),
               str(cnf_path), str(parent / "variables.txt"),
               str(model_path), str(protocol["solver_conflict_cap"]),
               str(protocol["solver_wall_cap_seconds"]), "interleave_pair1",
               str(target_path)]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter()
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True,
            timeout=protocol["external_process_safeguard_seconds"])
        stdout, stderr, return_code = (completed.stdout, completed.stderr,
                                       completed.returncode)
        status = {0: "sat", 10: "censored", 20: "unsat"}.get(
            return_code, "error")
    except subprocess.TimeoutExpired as error:
        stdout = (error.stdout or b"").decode(errors="replace")
        stderr = (error.stderr or b"").decode(errors="replace")
        return_code, status = None, "external_timeout"
    process_seconds = time.perf_counter() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cnf_path.unlink()
    target_path.unlink()
    stdout_path = output / "solver.stdout.txt"
    stderr_path = output / "solver.stderr.txt"
    stdout_path.write_text(stdout)
    stderr_path.write_text(stderr)
    report, report_error = None, None
    if stdout.strip():
        try:
            report = json.loads(stdout)
            assert report["status"] == {"sat": 10, "censored": 0,
                                         "unsat": 20}[status]
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
            assert report["screen_window_free_threshold_each_leaf"] == (
                14 if args.degree == 53 else 20)
            assert report["screen_window_distinct_capped"] <= 256
            assert len(report["screen_snapshots"]) <= 16
            assert report["screen_window_events"] <= (
                report["unsaturated_mid1_events"])
            assert report["unsaturated_mid1_events"] <= (
                report["both_partial_mid1_events"])
            assert report["span_checks"] == report[
                "span_checked_state_count"]
            assert report["span_checks"] <= report[
                "screen_window_events"]
            assert report["span_rejections"] <= report["span_checks"]
            assert report["span_field_inv_calls"] == 0
            assert report["span_field_mul_calls"] <= report[
                "field_mul_calls"]
            assert report["span_field_sqr_calls"] <= report[
                "field_sqr_calls"]
            assert report["cache_gamma_tables_retained"] <= 64
            assert report["cache_linear_rows_retained"] <= 16384
            assert report["cache_pair_build_mul_calls"] == report[
                "cache_pair_build_sqr_calls"]
            assert report["cache_gamma_build_mul_calls"] >= report[
                "cache_gamma_table_builds"]
            assert report["cache_pair_build_mul_calls"] + report[
                "cache_gamma_build_mul_calls"] <= report[
                    "span_field_mul_calls"]
            assert len(report["span_rejection_snapshots"]) <= 16
        except (AssertionError, KeyError, ValueError) as error:
            report_error, report = repr(error), None
    checked, check_error = None, None
    check_start = time.perf_counter()
    if status == "sat":
        try:
            model = model_from_file(model_path)
            check_cnf(raw, model, variables, clauses)
            checked = check_math(formula, meta, model)
        except (AssertionError, KeyError, OSError, ValueError) as error:
            check_error = repr(error)
    check_seconds = time.perf_counter() - check_start
    receipt = {
        "proposal_id": "Q1432", "candidate_id": None,
        "isogeny": "none", "degree_n": args.degree, "cell": args.cell,
        "curve_id": workload["curve_id"],
        "factor_base_actual_B": workload["factor_base_actual_B"],
        "folded_columns_K": workload["folded_columns_K"],
        "factor_base_enumerated_set_sha256": workload[
            "factor_base_enumerated_set_sha256"],
        "public_target": workload["public_target"],
        "input_law": workload["input_law"],
        "stage_config_id": workload["stage_config_id"],
        "workload_id": workload["workload_id"],
        "stage_run_id": workload["stage_run_id"],
        "matched_q1431_stage_run_id": workload[
            "matched_q1431_stage_run_id"],
        "matched_q1431_receipt_sha256": sha(matched_path),
        "target_input_sha256": workload["target_input_sha256"],
        "target_preimage_x_count": workload["target_preimage_x_count"],
        "parent_q1420_receipt_sha256": sha(parent_path),
        "cnf_raw_sha256": hashlib.sha256(raw).hexdigest(),
        "cnf_variables": variables, "cnf_clauses": clauses,
        "removed_partner_pin_units": removed,
        "formula_build_wall_seconds_exploratory": build_seconds,
        "solver_status": status, "solver_return_code": return_code,
        "solver_process_wall_seconds_exploratory": process_seconds,
        "solver_report": report, "solver_report_error": report_error,
        "solver_stdout_sha256": sha(stdout_path),
        "solver_stderr_sha256": sha(stderr_path),
        "solver_model_sha256": sha(model_path) if model_path.exists() else None,
        "model_check": checked, "model_check_error": check_error,
        "model_check_wall_seconds_exploratory": check_seconds,
        "verified_relation_count": int(checked is not None and
                                       checked["status"] ==
                                       "verified_four_point_relation"),
        "peak_child_rss_raw": after.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
        "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
        "natural_relation_yield_estimate": None,
        "complete_field_operation_equivalent_count": None,
        "complete_solve_work_log2": None,
        "protocol_sha256": sha(PROTOCOL),
        "runner_source_sha256": sha(Path(__file__)),
        "solver_binary_sha256": sha(binary),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
    }
    (output / "receipt.json").write_text(json.dumps(
        receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"key": key, "status": status,
                      "verified_relation_count": receipt[
                          "verified_relation_count"],
                      "solver_process_wall_seconds": process_seconds,
                      "pair_assignments": (report or {}).get(
                          "cached_pair_assignments")}))


if __name__ == "__main__":
    main()
