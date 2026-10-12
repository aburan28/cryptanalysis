#!/usr/bin/env python3
"""Run one source-bound N83 S3-chain cell with wider exact-join admission."""

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
from q1467_density_bridge.build_inputs import make_case  # noqa: E402

Q1467 = PARENT / "q1467_density_bridge"
Q1466 = PARENT / "q1466_leaf_rotation"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(name: str) -> None:
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q1471"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert name in protocol["run_order"]
    cell = protocol["cells"][name]
    input_dir = Q1467 / "inputs" / name
    output = HERE / "runs" / name
    assert not output.exists(), "refuse overwrite"
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert sha(Q1467 / "solver_protocol.json") == protocol[
        "q1467_protocol_sha256"]
    assert sha(PARENT / "q1470_n83_long_control/run/receipt.json") == (
        protocol["q1470_receipt_sha256"])
    assert sha(Q1467 / "runs" / name / "receipt.json") == cell[
        "q1467_prior_receipt_sha256"]
    assert sha(Q1466 / "native_solver") == protocol["binary_sha256"]
    assert sha(Q1466 / "compile_receipt.json") == protocol[
        "compile_receipt_sha256"]
    assert sha(PARENT / "q1420_root_theory/n83_field.txt") == protocol[
        "field_file_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "sage_runtime_info_sha256"]
    for leaf, digest in cell["input_sha256"].items():
        assert sha(input_dir / leaf) == digest, (name, leaf)
    raw = gzip.decompress((input_dir / "system.cnf.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == cell["cnf_sha256"]
    header = next(line for line in raw.splitlines() if line.startswith(b"p cnf "))
    _, _, variables, clauses = header.split()
    assert int(variables) == cell["cnf_variables"]
    assert int(clauses) == cell["cnf_clauses"]
    output.mkdir(parents=True)
    cnf = output / "system.cnf"
    model = output / "solver.model.txt"
    prep_start = time.perf_counter_ns()
    cnf.write_bytes(raw)
    prep_ns = time.perf_counter_ns() - prep_start
    command = [
        str(Q1466 / "native_solver"),
        str(PARENT / "q1420_root_theory/n83_field.txt"),
        str(cnf), str(input_dir / "variables.txt"), str(model),
        str(protocol["conflict_cap"]),
        str(protocol["wall_cap_seconds"]),
        str(input_dir / "targets.txt"),
        str(protocol["pair_candidate_cap"]),
        protocol["decision_policy"],
    ]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter_ns()
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True,
            timeout=protocol["external_safeguard_seconds"])
        stdout, stderr, exit_code = (completed.stdout, completed.stderr,
                                     completed.returncode)
        status = {0: "sat", 10: "censored", 20: "unsat"}.get(
            exit_code, "error")
    except subprocess.TimeoutExpired as error:
        stdout = (error.stdout or b"").decode(errors="replace")
        stderr = (error.stderr or b"").decode(errors="replace")
        exit_code, status = None, "external_timeout"
    solver_ns = time.perf_counter_ns() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    stdout_path = output / "solver.stdout.txt"
    stderr_path = output / "solver.stderr.txt"
    stdout_path.write_text(stdout)
    stderr_path.write_text(stderr)
    cnf.unlink()
    report = report_error = None
    if stdout.strip():
        try:
            report = json.loads(stdout)
            assert report["status"] == {
                "sat": 10, "censored": 0, "unsat": 20}[status]
            assert report["pair_cap"] == protocol["pair_candidate_cap"]
            assert report["cnf_variables"] == cell["cnf_variables"]
            assert report["cnf_clauses"] == cell["cnf_clauses"]
            assert report["decision_policy"] == protocol["decision_policy"]
        except Exception as error:
            report_error = repr(error)
            report = None
    check_start = time.perf_counter_ns()
    relation = relation_error = None
    if status == "sat" and report is not None:
        try:
            regenerated, varmap, targets, meta, variables, clauses, formula = (
                make_case(name))
            assert regenerated == raw
            assert varmap == (input_dir / "variables.txt").read_bytes()
            assert targets == (input_dir / "targets.txt").read_bytes()
            instance = dict(json.loads((PARENT /
                "q1438_dense_base/solver_protocol.json").read_text())[
                    "instances"]["83"])
            instance["new_weight_bound"] = meta[
                "normal_basis_weight_bound"]
            relation = model_relation(raw, formula, meta, variables,
                                      len(clauses), model, instance)
        except Exception as error:
            relation_error = repr(error)
    check_ns = time.perf_counter_ns() - check_start
    verified = int(relation is not None and relation.get("status") ==
                   "verified_four_point_relation")
    receipt = {
        "proposal_id": "Q1471", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "case": name, "input_role": cell["input_role"],
        "curve_id": protocol["curve_id"], "degree_n": 83,
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "folded_columns_K": protocol["folded_columns_K"],
        "factor_base_enumerated_set_sha256": protocol[
            "factor_base_enumerated_set_sha256"],
        "workload_id": cell["workload_id"],
        "public_target": cell["public_target"],
        "cnf_sha256": cell["cnf_sha256"],
        "native_status": status, "native_exit_code": exit_code,
        "native_report": report, "native_report_error": report_error,
        "independent_model_check": relation,
        "independent_model_check_error": relation_error,
        "verified_relation_count": verified,
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "input_materialization_wall_ns_exploratory": prep_ns,
        "solver_process_wall_ns_exploratory": solver_ns,
        "relation_check_wall_ns_exploratory": check_ns,
        "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
        "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
        "peak_child_rss_raw": after.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "solver_stdout_sha256": sha(stdout_path),
        "solver_stderr_sha256": sha(stderr_path),
        "solver_model_sha256": sha(model) if model.exists() else None,
        "protocol_sha256": sha(protocol_path),
        "runner_source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "cpu_isolation_receipt": None,
        "controlled_wall_speedup": None,
    }
    (output / "receipt.json").write_text(json.dumps(
        receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"case": name, "status": status,
                      "verified": verified,
                      "joint_checks": (report or {}).get(
                          "joint_eligible_checks"),
                      "conflicts": (report or {}).get("conflicts"),
                      "solver_wall_seconds": solver_ns / 1e9}), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=(
        "n83_planted_unpinned", "n83_ordinary"), required=True)
    args = parser.parse_args()
    run(args.case)


if __name__ == "__main__":
    main()
