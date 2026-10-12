#!/usr/bin/env python3
"""Run one frozen ordinary Q1462 sparse-sum SAT cell."""

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
ROOT = HERE.parents[2]
Q1420 = PARENT / "q1420_root_theory"
Q1438 = PARENT / "q1438_dense_base"
Q1446 = PARENT / "q1446_joint_pair_span"
sys.path.insert(0, str(PARENT))

from q1423_target_coupled.target_inputs import (  # noqa: E402
    encode_targets, target_list)
from q1438_dense_base.build_formula import build_cnf  # noqa: E402
from q1438_dense_base.verify_solver import model_relation  # noqa: E402

PROTOCOL = HERE / "protocol.json"
POLICY = "sparse_sum_joint_pair_span"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(n):
    protocol = json.loads(PROTOCOL.read_text())
    cell = protocol["cells"][str(n)]
    output = HERE / f"runs/n{n}_ordinary"
    assert not output.exists(), "refuse overwrite"
    assert protocol["proposal_id"] == "Q1462"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert protocol["policy"] == POLICY
    assert protocol["run_order"] == ["n53_ordinary", "n83_ordinary"]
    for name, digest in protocol["source_sha256"].items():
        assert sha(ROOT / name) == digest, name
    for name, digest in protocol["input_sha256"].items():
        assert sha(ROOT / name) == digest, name
    binary = HERE / "native_solver"
    assert sha(binary) == protocol["solver_binary_sha256"]
    assert sha(HERE / "compile_receipt.json") == protocol[
        "compile_receipt_sha256"]
    assert sha(HERE / "control_result.json") == protocol[
        "control_result_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "sage_runtime_info_sha256"]
    assert json.loads((HERE / "sage_runtime_info.json").read_text())[
        "status"] == "verified"
    parent = json.loads((Q1438 / "solver_protocol.json").read_text())
    workload = parent["workloads"][f"n{n}_ordinary"]
    instance = parent["instances"][str(n)]
    for name in ("curve_id", "factor_base_actual_B", "folded_columns_K",
                 "factor_base_enumerated_set_sha256", "public_target",
                 "cnf_raw_sha256", "variable_map_sha256",
                 "target_input_sha256"):
        assert cell[name] == workload[name], name
    assert cell["subgroup_order"] == instance["subgroup_order"]
    assert cell["cofactor"] == instance["cofactor"]
    assert cell["workload_id"] == workload["workload_id"]
    assert sha(Q1446 / f"runs/n{n}_ordinary/receipt.json") == cell[
        "baseline_q1446_receipt_sha256"]
    assert sha(Q1438 / f"n{n}_w{cell['weight_bound']}_base.json") == cell[
        "factor_base_receipt_sha256"]

    online_start = time.perf_counter_ns()
    build_start = online_start
    raw, varmap, formula, meta, variables, clauses = build_cnf(n, "ordinary")
    q1436 = json.loads((PARENT / "q1436_affine_pair/protocol.json").read_text())[
        "workloads"][f"n{n}_ordinary"]
    q1420 = json.loads((Q1420 / "protocol.json").read_text())[
        "workloads"][q1436["parent_q1420_key"]]
    targets = encode_targets(n, target_list(n, "ordinary", q1420))
    formula_build_ns = time.perf_counter_ns() - build_start
    assert hashlib.sha256(raw).hexdigest() == cell["cnf_raw_sha256"]
    assert hashlib.sha256(varmap).hexdigest() == cell["variable_map_sha256"]
    assert hashlib.sha256(targets).hexdigest() == cell["target_input_sha256"]
    assert len(raw) == cell["cnf_raw_bytes"]
    assert variables == cell["cnf_variables"]
    assert clauses == cell["cnf_clauses"]
    assert meta["curve_id"] == cell["curve_id"]
    assert meta["factor_base_actual_B"] == cell["factor_base_actual_B"]
    assert meta["folded_columns_K"] == cell["folded_columns_K"]
    assert meta["factor_base_enumerated_set_sha256"] == cell[
        "factor_base_enumerated_set_sha256"]
    output.mkdir(parents=True)
    cnf_path = output / "system.cnf"
    map_path = output / "variables.txt"
    target_path = output / "targets.txt"
    model_path = output / "solver.model.txt"
    cnf_path.write_bytes(raw)
    map_path.write_bytes(varmap)
    target_path.write_bytes(targets)
    command = [str(binary), str(Q1420 / f"n{n}_field.txt"),
               str(cnf_path), str(map_path), str(model_path),
               str(cell["solver_conflict_cap"]),
               str(cell["solver_wall_cap_seconds"]),
               POLICY, str(target_path),
               str(cell["sum_candidate_cap"])]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    process_start = time.perf_counter_ns()
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True,
            timeout=cell["external_process_safeguard_seconds"])
        stdout, stderr = completed.stdout, completed.stderr
        exit_code = completed.returncode
        status = {0: "sat", 10: "censored", 20: "unsat"}.get(
            exit_code, "error")
    except subprocess.TimeoutExpired as error:
        stdout = (error.stdout or b"").decode(errors="replace")
        stderr = (error.stderr or b"").decode(errors="replace")
        exit_code, status = None, "external_timeout"
    process_ns = time.perf_counter_ns() - process_start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    stdout_path = output / "solver.stdout.txt"
    stderr_path = output / "solver.stderr.txt"
    stdout_path.write_text(stdout)
    stderr_path.write_text(stderr)
    archive_path = output / "system.cnf.gz"
    archive_path.write_bytes(gzip.compress(raw, mtime=0))
    cnf_path.unlink()
    report = report_error = None
    if stdout.strip():
        try:
            report = json.loads(stdout)
            assert report["status"] == {"sat": 10, "censored": 0,
                                         "unsat": 20}[status]
            assert report["decision_policy"] == POLICY
            assert report["sum_cap"] == cell["sum_candidate_cap"]
            assert report["cnf_variables"] == variables
            assert report["cnf_clauses"] == clauses
            assert report["sum_checks"] == (
                report["sum_checks_pair0"] + report["sum_checks_pair1"])
            assert report["sum_rejections"] == (
                report["sum_rejections_pair0"] +
                report["sum_rejections_pair1"])
            assert report["sum_check_mul_calls"] <= report[
                "field_mul_calls"]
            assert report["span_checks"] == (
                report["span_checks_pair0"] + report["span_checks_pair1"])
            assert report["span_rejections"] == (
                report["span_rejections_pair0"] +
                report["span_rejections_pair1"])
        except Exception as error:
            report_error = repr(error)
            report = None
    replay_start = time.perf_counter_ns()
    checked = check_error = None
    if status == "sat":
        try:
            checked = model_relation(raw, formula, meta, variables, clauses,
                                     model_path, instance)
        except Exception as error:
            check_error = repr(error)
    replay_ns = time.perf_counter_ns() - replay_start
    verified = int(checked is not None and checked.get("status") ==
                   "verified_four_point_relation")
    online_ns = time.perf_counter_ns() - online_start
    other_ns = online_ns - formula_build_ns - process_ns - replay_ns
    assert other_ns >= 0
    receipt = {
        "proposal_id": "Q1462", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "policy": POLICY, "degree_n": n,
        "curve_id": cell["curve_id"],
        "factor_base_actual_B": cell["factor_base_actual_B"],
        "folded_columns_K": cell["folded_columns_K"],
        "factor_base_enumerated_set_sha256": cell[
            "factor_base_enumerated_set_sha256"],
        "sum_candidate_cap": cell["sum_candidate_cap"],
        "public_target": cell["public_target"],
        "workload_id": cell["workload_id"],
        "matched_q1438_workload_id": cell["matched_q1438_workload_id"],
        "solver_status": status, "solver_exit_code": exit_code,
        "solver_report": report, "solver_report_error": report_error,
        "model_check": checked, "model_check_error": check_error,
        "verified_relation_count": verified,
        "natural_relation_yield_estimate": None,
        "novel_rank_per_query": None,
        "cost_per_useful_row": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "formula_build_wall_ns_exploratory": formula_build_ns,
        "solver_process_wall_ns_exploratory": process_ns,
        "recovery_check_wall_ns_exploratory": replay_ns,
        "other_online_wall_ns_exploratory": other_ns,
        "online_stage_wall_ns_exploratory": online_ns,
        "online_stage_interval": (
            "from target-dependent compact-S3 formula construction through "
            "native solve and relation replay; stage only, not DLP"),
        "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
        "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
        "peak_child_rss_raw": after.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "cnf_variables": variables, "cnf_clauses": clauses,
        "cnf_raw_bytes": len(raw),
        "cnf_raw_sha256": hashlib.sha256(raw).hexdigest(),
        "cnf_archive_sha256": sha(archive_path),
        "variable_map_sha256": sha(map_path),
        "target_input_sha256": sha(target_path),
        "baseline_q1446_receipt_sha256": sha(Q1446 /
            f"runs/n{n}_ordinary/receipt.json"),
        "solver_binary_sha256": sha(binary),
        "solver_stdout_sha256": sha(stdout_path),
        "solver_stderr_sha256": sha(stderr_path),
        "solver_model_sha256": sha(model_path) if model_path.exists() else None,
        "runner_source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "protocol_sha256": sha(PROTOCOL),
        "cpu_isolation_receipt": None,
        "controlled_wall_speedup": None,
    }
    (output / "receipt.json").write_text(json.dumps(
        receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"degree": n, "status": status,
                      "verified_relations": verified,
                      "sum_checks_pair0": (report or {}).get(
                          "sum_checks_pair0"),
                      "sum_checks_pair1": (report or {}).get(
                          "sum_checks_pair1"),
                      "online_stage_wall_seconds": online_ns / 1e9},
                     sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    run(parser.parse_args().degree)
