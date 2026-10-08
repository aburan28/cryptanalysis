#!/usr/bin/env python3
"""Run Q1470 on the exact unpinned Q1467 N83 planted CNF."""

from __future__ import annotations

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
INPUT = Q1467 / "inputs/n83_planted_unpinned"
OUT = HERE / "run"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q1470"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert not OUT.exists(), "refuse overwrite"
    for name, digest in protocol["source_sha256"].items():
        assert sha(ROOT / name) == digest, name
    assert sha(Q1467 / "solver_protocol.json") == protocol[
        "q1467_protocol_sha256"]
    assert sha(Q1467 / "runs/n83_planted_unpinned/receipt.json") == protocol[
        "q1467_prior_receipt_sha256"]
    assert sha(Q1467 / "runs/n83_planted/receipt.json") == protocol[
        "q1467_pinned_receipt_sha256"]
    pinned = json.loads((Q1467 / "runs/n83_planted/receipt.json").read_text())
    assert pinned["verified_relation_count"] == 1
    assert pinned["public_target"] == protocol["public_target"]
    assert sha(Q1466 / "native_solver") == protocol["binary_sha256"]
    assert sha(Q1466 / "compile_receipt.json") == protocol[
        "compile_receipt_sha256"]
    assert sha(PARENT / "q1420_root_theory/n83_field.txt") == protocol[
        "field_file_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "sage_runtime_info_sha256"]
    for name, digest in protocol["input_sha256"].items():
        assert sha(INPUT / name) == digest, name
    raw = gzip.decompress((INPUT / "system.cnf.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == protocol["cnf_sha256"]
    header = next(line for line in raw.splitlines() if line.startswith(b"p cnf "))
    _, _, variables, clauses = header.split()
    assert int(variables) == protocol["cnf_variables"]
    assert int(clauses) == protocol["cnf_clauses"]
    OUT.mkdir()
    cnf = OUT / "system.cnf"
    model = OUT / "solver.model.txt"
    prep_start = time.perf_counter_ns()
    cnf.write_bytes(raw)
    prep_ns = time.perf_counter_ns() - prep_start
    command = [
        str(Q1466 / "native_solver"),
        str(PARENT / "q1420_root_theory/n83_field.txt"),
        str(cnf), str(INPUT / "variables.txt"), str(model),
        str(protocol["conflict_cap"]),
        str(protocol["wall_cap_seconds"]),
        str(INPUT / "targets.txt"),
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
    stdout_path = OUT / "solver.stdout.txt"
    stderr_path = OUT / "solver.stderr.txt"
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
            assert report["cnf_variables"] == protocol["cnf_variables"]
            assert report["cnf_clauses"] == protocol["cnf_clauses"]
            assert report["decision_policy"] == protocol["decision_policy"]
        except Exception as error:
            report_error = repr(error)
            report = None
    check_start = time.perf_counter_ns()
    relation = relation_error = None
    if status == "sat" and report is not None:
        try:
            regenerated, varmap, targets, meta, variables, clauses, formula = (
                make_case("n83_planted_unpinned"))
            assert regenerated == raw
            assert varmap == (INPUT / "variables.txt").read_bytes()
            assert targets == (INPUT / "targets.txt").read_bytes()
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
        "proposal_id": "Q1470", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "curve_id": protocol["curve_id"], "degree_n": 83,
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "folded_columns_K": protocol["folded_columns_K"],
        "factor_base_enumerated_set_sha256": protocol[
            "factor_base_enumerated_set_sha256"],
        "workload_id": protocol["workload_id"],
        "public_target": protocol["public_target"],
        "input_role": protocol["input_role"],
        "known_satisfiable_control": True,
        "native_status": status,
        "native_exit_code": exit_code,
        "native_report": report,
        "native_report_error": report_error,
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
    (OUT / "receipt.json").write_text(json.dumps(
        receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": status, "verified": verified,
                      "conflicts": (report or {}).get("conflicts"),
                      "wall_seconds": solver_ns / 1e9}), flush=True)


if __name__ == "__main__":
    main()
