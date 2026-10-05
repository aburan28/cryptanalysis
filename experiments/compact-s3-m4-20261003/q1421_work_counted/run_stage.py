#!/usr/bin/env python3
"""Run one pre-registered Q1421 root-theory stage on a Q1420 formula."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import resource
import subprocess
import sys
import time
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    parser.add_argument("--cell", choices=("free_mids", "ordinary"),
                        required=True)
    parser.add_argument("--policy", choices=("default", "leaf_first"),
                        required=True)
    args = parser.parse_args()
    key = f"n{args.degree}_{args.cell}_{args.policy}"
    protocol = json.loads(PROTOCOL.read_text())
    assert key in protocol["run_order"]
    assert protocol["source_sha256"]["run_stage.py"] == sha(Path(__file__))
    for name, digest in protocol["source_sha256"].items():
        assert sha(HERE / name) == digest
    for name, digest in protocol["dependency_sha256"].items():
        assert sha(PARENT / name) == digest
    binary = HERE / "theory_solver"
    assert sha(binary) == protocol["solver_binary_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "sage_runtime_info_sha256"]
    assert sha(PARENT / "protocol.json") == protocol[
        "parent_q1420_protocol_sha256"]
    workload = protocol["workloads"][key]
    parent = PARENT / "runs" / workload["parent_key"]
    parent_receipt_path = parent / "receipt.json"
    assert sha(parent_receipt_path) == workload["parent_receipt_sha256"]
    parent_receipt = json.loads(parent_receipt_path.read_text())
    assert sha(parent / "meta.json") == workload["parent_meta_sha256"]
    assert sha(parent / "system.cnf.gz") == workload[
        "parent_cnf_archive_sha256"]
    assert sha(parent / "variables.txt") == workload[
        "parent_variable_map_sha256"]
    assert parent_receipt["curve_id"] == workload["curve_id"]
    assert parent_receipt["factor_base_actual_B"] == workload[
        "factor_base_actual_B"]
    assert parent_receipt["folded_columns_K"] == workload["folded_columns_K"]
    assert parent_receipt["workload_id"] == workload["workload_id"]
    raw_cnf = gzip.decompress((parent / "system.cnf.gz").read_bytes())
    assert hashlib.sha256(raw_cnf).hexdigest() == parent_receipt[
        "cnf_raw_sha256"]
    output = HERE / "runs" / key
    assert not output.exists()
    output.mkdir(parents=True)
    cnf_path = output / "system.cnf"
    cnf_path.write_bytes(raw_cnf)
    model_path = output / "solver.model.txt"
    command = [str(binary), str(PARENT / f"n{args.degree}_field.txt"),
               str(cnf_path), str(parent / "variables.txt"),
               str(model_path), str(protocol["solver_conflict_cap"]),
               str(protocol["solver_wall_cap_seconds"]), args.policy]
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
            assert report["decision_policy"] == args.policy
            assert report["cnf_variables"] == parent_receipt["cnf_variables"]
            assert report["cnf_clauses"] == parent_receipt["cnf_clauses"]
        except (AssertionError, KeyError, ValueError) as error:
            report_error, report = repr(error), None
    checked, check_error = None, None
    check_start = time.perf_counter()
    if status == "sat":
        try:
            model = model_from_file(model_path)
            check_cnf(raw_cnf, model, parent_receipt["cnf_variables"],
                      parent_receipt["cnf_clauses"])
            formula, _ = build(args.degree, "ordinary" if
                               args.cell == "ordinary" else "control",
                               args.cell)
            meta = json.loads((parent / "meta.json").read_text())
            checked = check_math(formula, meta, model)
        except (AssertionError, KeyError, OSError, ValueError) as error:
            check_error = repr(error)
    check_seconds = time.perf_counter() - check_start
    receipt = {
        "proposal_id": "Q1421", "candidate_id": None,
        "isogeny": "none", "degree_n": args.degree,
        "cell": args.cell, "decision_policy": args.policy,
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
        "parent_stage_run_id": workload["parent_stage_run_id"],
        "parent_receipt_sha256": sha(parent_receipt_path),
        "parent_cnf_archive_sha256": sha(parent / "system.cnf.gz"),
        "parent_cnf_raw_sha256": parent_receipt["cnf_raw_sha256"],
        "parent_formula_build_wall_seconds_exploratory": parent_receipt[
            "formula_build_wall_seconds_exploratory"],
        "parent_formula_build_field_mul_calls": parent_receipt[
            "formula_build_field_mul_calls"],
        "parent_formula_build_field_sqr_calls": parent_receipt[
            "formula_build_field_sqr_calls"],
        "solver_status": status, "solver_return_code": return_code,
        "solver_process_wall_seconds_exploratory": process_seconds,
        "solver_report": report,
        "solver_report_error": report_error,
        "solver_stdout_sha256": sha(stdout_path),
        "solver_stderr_sha256": sha(stderr_path),
        "solver_model_sha256": (sha(model_path)
                                if model_path.exists() else None),
        "model_check": checked,
        "model_check_error": check_error,
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
        receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"key": key, "status": status,
                      "verified_relation_count": receipt[
                          "verified_relation_count"],
                      "solver_process_wall_seconds": process_seconds,
                      "pair_assignments": (report or {}).get(
                          "cached_pair_assignments")}))


if __name__ == "__main__":
    main()
