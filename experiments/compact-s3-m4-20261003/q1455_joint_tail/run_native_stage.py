#!/usr/bin/env python3
"""Run one frozen Q1455 native joint-tail cell and preserve every outcome."""

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
sys.path.insert(0, str(PARENT))

from q1438_dense_base.verify_solver import model_relation  # noqa: E402
from q1455_joint_tail.native_inputs import CASES, make_case  # noqa: E402

PROTOCOL = HERE / "native_protocol.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(name: str) -> None:
    protocol = json.loads(PROTOCOL.read_text())
    cell = protocol["cells"][name]
    output = HERE / "runs" / name
    assert not output.exists(), "refuse overwrite"
    assert protocol["proposal_id"] == "Q1455"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert name in protocol["run_order"]
    assert protocol["parent_control_protocol_sha256"] == sha(
        HERE / "protocol.json")
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    for relative, digest in protocol["input_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    binary = HERE / "native_joint_solver"
    assert sha(binary) == protocol["native_binary_sha256"]
    assert sha(HERE / "native_compile_receipt.json") == protocol[
        "native_compile_receipt_sha256"]
    assert json.loads((HERE / "sage_runtime_info.json").read_text())[
        "status"] == "verified"

    online_start = time.perf_counter_ns()
    build_start = online_start
    raw, varmap, targets, formula, meta, variables, clauses = make_case(name)
    build_ns = time.perf_counter_ns() - build_start
    assert hashlib.sha256(raw).hexdigest() == cell["cnf_sha256"]
    assert hashlib.sha256(varmap).hexdigest() == cell["variable_map_sha256"]
    assert hashlib.sha256(targets).hexdigest() == cell["targets_sha256"]
    assert len(raw) == cell["cnf_bytes"]
    assert variables == cell["cnf_variables"]
    assert clauses == cell["cnf_clauses"]
    for key in ("curve_id", "factor_base_actual_B", "folded_columns_K",
                "factor_base_enumerated_set_sha256", "public_target"):
        assert meta[key] == cell[key], key

    output.mkdir(parents=True)
    materialize_start = time.perf_counter_ns()
    cnf_path = output / "system.cnf"
    map_path = output / "variables.txt"
    target_path = output / "targets.txt"
    model_path = output / "solver.model.txt"
    cnf_path.write_bytes(raw)
    map_path.write_bytes(varmap)
    target_path.write_bytes(targets)
    materialize_ns = time.perf_counter_ns() - materialize_start
    n = cell["degree_n"]
    command = [str(binary),
               str(PARENT / f"q1420_root_theory/n{n}_field.txt"),
               str(cnf_path), str(map_path), str(model_path),
               str(cell["solver_conflict_cap"]),
               str(cell["solver_wall_cap_seconds"]), str(target_path),
               str(cell["pair_candidate_cap"]),
               protocol["decision_policy"]]
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
    report = report_error = None
    if stdout.strip():
        try:
            report = json.loads(stdout)
            assert report["status"] == {"sat": 10, "censored": 0,
                                         "unsat": 20}[status]
            assert report["decision_policy"] == protocol[
                "decision_policy"]
            assert report["cnf_variables"] == variables
            assert report["cnf_clauses"] == clauses
            assert report["pair_cap"] == cell["pair_candidate_cap"]
        except Exception as error:
            report_error = repr(error)
            report = None
    parent = json.loads((PARENT /
        "q1438_dense_base/solver_protocol.json").read_text())
    replay_start = time.perf_counter_ns()
    relation = replay_error = None
    if status == "sat":
        try:
            relation = model_relation(raw, formula, meta, variables,
                                      clauses, model_path,
                                      parent["instances"][str(n)])
        except Exception as error:
            replay_error = repr(error)
    replay_ns = time.perf_counter_ns() - replay_start
    verified = int(relation is not None and relation.get("status") ==
                   "verified_four_point_relation")
    online_ns = time.perf_counter_ns() - online_start
    other_ns = online_ns - build_ns - materialize_ns - process_ns - replay_ns
    assert other_ns >= 0
    archive_start = time.perf_counter_ns()
    archive_path = output / "system.cnf.gz"
    archive_path.write_bytes(gzip.compress(raw, mtime=0))
    cnf_path.unlink()
    archive_ns = time.perf_counter_ns() - archive_start
    receipt = {
        "proposal_id": "Q1455", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "case": name, "input_role": cell["input_role"],
        "degree_n": n, "curve_id": cell["curve_id"],
        "factor_base_actual_B": cell["factor_base_actual_B"],
        "folded_columns_K": cell["folded_columns_K"],
        "factor_base_enumerated_set_sha256": cell[
            "factor_base_enumerated_set_sha256"],
        "public_target": cell["public_target"],
        "workload_id": cell["workload_id"],
        "solver_status": status, "solver_exit_code": exit_code,
        "solver_report": report, "solver_report_error": report_error,
        "model_check": relation, "model_check_error": replay_error,
        "verified_relation_count": verified,
        "successful_ordinary_pdp_cost_measured": bool(
            verified and cell["input_role"] == "ordinary_full_target"),
        "natural_relation_yield_estimate": None,
        "novel_rank_per_query": None,
        "cost_per_useful_row": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "formula_build_wall_ns_exploratory": build_ns,
        "input_materialize_wall_ns_exploratory": materialize_ns,
        "solver_process_wall_ns_exploratory": process_ns,
        "recovery_check_wall_ns_exploratory": replay_ns,
        "other_online_wall_ns_exploratory": other_ns,
        "online_stage_wall_ns_exploratory": online_ns,
        "archive_wall_ns_outside_stage": archive_ns,
        "online_stage_interval": (
            "from target-dependent compact-S3 formula construction "
            "through native solving and relation replay; stage only, "
            "not a complete target DLP"),
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
    print(json.dumps({"case": name, "status": status,
                      "verified_relations": verified,
                      "joint_checks": (report or {}).get(
                          "joint_eligible_checks"),
                      "joint_rejections": (report or {}).get(
                          "joint_no_chain_rejections"),
                      "online_stage_wall_seconds": online_ns / 1e9},
                     sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=CASES, required=True)
    run(parser.parse_args().case)
