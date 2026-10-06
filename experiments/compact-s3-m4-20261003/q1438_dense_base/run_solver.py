#!/usr/bin/env python3
"""Run one frozen Q1438 dense-base compact-S3 control or ordinary query."""

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
PARENT = HERE.parent
Q1420 = PARENT / "q1420_root_theory"
Q1436 = PARENT / "q1436_affine_pair"
sys.path.insert(0, str(PARENT))
from q1423_target_coupled.target_inputs import (  # noqa: E402
    encode_targets, target_list)
from q1438_dense_base.build_formula import build_cnf  # noqa: E402
from q1438_dense_base.verify_solver import model_relation  # noqa: E402
from run_probe import sha  # noqa: E402

PROTOCOL = HERE / "solver_protocol.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    parser.add_argument("--cell", choices=("free_partner", "ordinary"),
                        required=True)
    args = parser.parse_args()
    key = f"n{args.degree}_{args.cell}"
    protocol = json.loads(PROTOCOL.read_text())
    workload = protocol["workloads"][key]
    instance = protocol["instances"][str(args.degree)]
    assert key in protocol["run_order"]
    assert protocol["proposal_id"] == "Q1438"
    assert sha(Q1436 / "theory_solver") == protocol["solver_binary_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "runtime_info_sha256"]
    for name, digest in protocol["source_sha256"].items():
        assert sha(HERE / name) == digest
    for name, digest in protocol["dependency_sha256"].items():
        assert sha(PARENT.parents[1] / name) == digest
    assert sha(HERE / f"n{args.degree}_w{instance['new_weight_bound']}_base.json") == workload[
        "factor_base_receipt_sha256"]

    build_start = time.perf_counter()
    raw, varmap, formula, meta, variables, clauses = build_cnf(
        args.degree, args.cell)
    build_seconds = time.perf_counter() - build_start
    assert hashlib.sha256(raw).hexdigest() == workload["cnf_raw_sha256"]
    assert hashlib.sha256(varmap).hexdigest() == workload[
        "variable_map_sha256"]
    assert variables == workload["cnf_variables"]
    assert clauses == workload["cnf_clauses"]
    q1436 = json.loads((Q1436 / "protocol.json").read_text())[
        "workloads"][key]
    q1420 = json.loads((Q1420 / "protocol.json").read_text())[
        "workloads"][q1436["parent_q1420_key"]]
    targets = encode_targets(args.degree, target_list(
        args.degree, "free_mids" if args.cell == "free_partner" else
        "ordinary", q1420))
    assert hashlib.sha256(targets).hexdigest() == workload[
        "target_input_sha256"]

    output = HERE / "runs" / key
    assert not output.exists(), "refuse to overwrite frozen solver run"
    output.mkdir(parents=True)
    cnf_path = output / "system.cnf"
    map_path = output / "variables.txt"
    target_path = output / "targets.txt"
    model_path = output / "solver.model.txt"
    cnf_path.write_bytes(raw)
    map_path.write_bytes(varmap)
    target_path.write_bytes(targets)
    command = [str(Q1436 / "theory_solver"),
               str(Q1420 / f"n{args.degree}_field.txt"),
               str(cnf_path), str(map_path), str(model_path),
               str(protocol["solver_conflict_cap"]),
               str(protocol["solver_wall_cap_seconds"]),
               "interleave_pair1", str(target_path)]
    start = time.perf_counter()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    try:
        completed = subprocess.run(command, capture_output=True, text=True,
                                   timeout=protocol[
                                       "external_process_safeguard_seconds"])
        stdout, stderr = completed.stdout, completed.stderr
        exit_code = completed.returncode
        solver_status = {0: "sat", 10: "censored", 20: "unsat"}.get(
            exit_code, "error")
    except subprocess.TimeoutExpired as error:
        stdout = (error.stdout or b"").decode(errors="replace")
        stderr = (error.stderr or b"").decode(errors="replace")
        exit_code, solver_status = None, "external_timeout"
    process_seconds = time.perf_counter() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    (output / "solver.stdout.txt").write_text(stdout)
    (output / "solver.stderr.txt").write_text(stderr)
    archive = output / "system.cnf.gz"
    archive.write_bytes(gzip.compress(raw, mtime=0))
    cnf_path.unlink()

    report = report_error = None
    if stdout.strip():
        try:
            report = json.loads(stdout)
            assert report["status"] == {"sat": 10, "censored": 0,
                                         "unsat": 20}[solver_status]
            assert report["decision_policy"] == "interleave_pair1"
            assert report["target_coupled_active"] is True
            assert report["cnf_variables"] == variables
            assert report["cnf_clauses"] == clauses
        except Exception as error:
            report_error = repr(error)
            report = None

    checked = check_error = None
    verify_start = time.perf_counter()
    if solver_status == "sat":
        try:
            checked = model_relation(raw, formula, meta, variables, clauses,
                                     model_path, instance)
        except Exception as error:
            check_error = repr(error)
    verify_seconds = time.perf_counter() - verify_start
    verified_count = int(checked is not None and checked.get("status") ==
                         "verified_four_point_relation")
    receipt = {
        "kind": "q1438_dense_base_compact_s3_stage_run",
        "proposal_id": "Q1438", "candidate_id": None,
        "curve_id": workload["curve_id"], "isogeny": "none",
        "field_degree_n": args.degree, "cell": args.cell,
        "factor_base_actual_B": workload["factor_base_actual_B"],
        "folded_columns_K": workload["folded_columns_K"],
        "factor_base_enumerated_set_sha256": workload[
            "factor_base_enumerated_set_sha256"],
        "factor_base_receipt_sha256": workload["factor_base_receipt_sha256"],
        "workload_id": workload["workload_id"],
        "stage_config_id": workload["stage_config_id"],
        "stage_run_id": workload["stage_run_id"],
        "public_target": workload["public_target"],
        "input_law": workload["input_law"],
        "target_preimage_x_count": workload["target_preimage_x_count"],
        "solver_status": solver_status, "solver_exit_code": exit_code,
        "solver_report": report, "solver_report_error": report_error,
        "model_check": checked, "model_check_error": check_error,
        "verified_relation_count": verified_count,
        "natural_relation_yield_estimate": None,
        "cost_per_useful_row": None,
        "complete_solve_work_log2": None,
        "cnf_variables": variables, "cnf_clauses": clauses,
        "cnf_raw_bytes": len(raw),
        "cnf_raw_sha256": hashlib.sha256(raw).hexdigest(),
        "cnf_archive_sha256": sha(archive),
        "variable_map_sha256": sha(map_path),
        "target_input_sha256": sha(target_path),
        "solver_stdout_sha256": sha(output / "solver.stdout.txt"),
        "solver_stderr_sha256": sha(output / "solver.stderr.txt"),
        "solver_model_sha256": sha(model_path) if model_path.exists() else None,
        "formula_build_wall_seconds_exploratory": build_seconds,
        "solver_process_wall_seconds_exploratory": process_seconds,
        "recovery_check_wall_seconds_exploratory": verify_seconds,
        "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
        "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
        "peak_child_rss_raw": after.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "solver_binary_sha256": sha(Q1436 / "theory_solver"),
        "runner_source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "protocol_sha256": sha(PROTOCOL),
        "cpu_wall_speedup_claim": False,
    }
    (output / "receipt.json").write_text(json.dumps(
        receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"key": key, "status": solver_status,
                      "verified_relation_count": verified_count,
                      "report_error": report_error,
                      "model_check_error": check_error,
                      "solver_seconds": process_seconds}), flush=True)


if __name__ == "__main__":
    main()
