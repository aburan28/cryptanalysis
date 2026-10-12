#!/usr/bin/env python3
"""Run the source-bound Q1479 solver on the exact Q1476 matched inputs."""

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
Q1476 = PARENT / "q1476_trace_syndrome"
sys.path.insert(0, str(PARENT))
from q1476_trace_syndrome.audit import verify_model  # noqa: E402
from q1476_trace_syndrome.prepare_inputs import CASES  # noqa: E402

PROTOCOL = HERE / "protocol.json"
BINARY = HERE / "native_solver"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(name: str) -> None:
    protocol = json.loads(PROTOCOL.read_text())
    manifest = json.loads((Q1476 / "input_manifest.json").read_text())
    assert name in CASES and list(CASES) == protocol["run_order"]
    assert protocol["proposal_id"] == "Q1479"
    assert protocol["candidate_id"] is protocol["run_id"] is None
    assert protocol["isogeny"] == "none"
    assert sha(Q1476 / "input_manifest.json") == protocol[
        "input_manifest_sha256"]
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert sha(BINARY) == protocol["solver_binary_sha256"]
    assert sha(HERE / "compile_receipt.json") == protocol[
        "solver_compile_receipt_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "runtime_info_sha256"]
    cell = manifest["cases"][name]
    n = cell["degree_n"]
    assert cell["workload_id"] == protocol["cases"][name]["workload_id"]
    assert protocol["cases"][name]["stage_config_id"] == protocol[
        "stages"][str(n)]["stage_config_id"]
    input_dir = Q1476 / "inputs" / name
    output = HERE / "runs" / name
    assert not output.exists(), "refuse overwrite"
    for leaf, digest in cell["input_sha256"].items():
        assert sha(input_dir / leaf) == digest
        assert digest == protocol["cases"][name]["input_sha256"][leaf]
    raw = gzip.decompress((input_dir / "system.cnf.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == cell["cnf_sha256"]
    field_file = PARENT / f"q1420_root_theory/n{n}_field.txt"
    assert sha(field_file) == protocol["field_file_sha256"][str(n)]
    output.mkdir(parents=True)
    cnf = output / "system.cnf"
    model = output / "solver.model.txt"
    prep_start = time.perf_counter_ns()
    cnf.write_bytes(raw)
    prep_ns = time.perf_counter_ns() - prep_start
    command = [str(BINARY), str(field_file), str(cnf),
               str(input_dir / "variables.txt"), str(model),
               str(protocol["conflict_cap"]),
               str(protocol["native_wall_cap_seconds"]),
               str(input_dir / "targets.txt"),
               str(protocol["pair_candidate_cap"]),
               protocol["decision_policy"]]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    began = time.perf_counter_ns()
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
    solver_ns = time.perf_counter_ns() - began
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    stdout_path, stderr_path = (output / "solver.stdout.txt",
                                output / "solver.stderr.txt")
    stdout_path.write_text(stdout)
    stderr_path.write_text(stderr)
    cnf.unlink()
    report = report_error = None
    if stdout.strip():
        try:
            report = json.loads(stdout)
            assert report["status"] == {
                "sat": 10, "censored": 0, "unsat": 20}[status]
            assert report["decision_policy"] == protocol["decision_policy"]
            assert report["pair_cap"] == protocol["pair_candidate_cap"]
            assert report["domain_pair_cap"] == protocol["domain_pair_cap"]
            assert report["domain_cache_cap"] == protocol["domain_cache_cap"]
            assert report["cnf_variables"] == cell["cnf_variables"]
            assert report["cnf_clauses"] == cell["cnf_clauses"]
            assert report["target_preimage_count"] == cell[
                "target_preimage_x_count"]
            assert report["propagations"] >= 0
        except Exception as error:
            report_error = repr(error)
            report = None
    check_start = time.perf_counter_ns()
    relation = relation_error = None
    if status == "sat" and report is not None:
        try:
            relation = verify_model(name, model)
        except Exception as error:
            relation_error = repr(error)
    check_ns = time.perf_counter_ns() - check_start
    verified = int(relation is not None and relation.get("status") ==
                   "verified_four_point_relation")
    receipt = {
        "proposal_id": "Q1479", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "stage_config_id": protocol["cases"][name]["stage_config_id"],
        "stage_run_id": protocol["cases"][name]["stage_run_id"],
        "case": name, "input_role": cell["input_role"],
        "leaves_pinned": cell["leaves_pinned"],
        "curve_id": cell["curve_id"], "degree_n": n,
        "factor_base_actual_B": cell["factor_base_actual_B"],
        "folded_columns_K": cell["folded_columns_K"],
        "factor_base_enumerated_set_sha256": cell[
            "factor_base_enumerated_set_sha256"],
        "workload_id": cell["workload_id"],
        "parent_workload_id": cell["workload_id"],
        "parent_q1476_receipt_sha256": protocol["cases"][name][
            "parent_q1476_receipt_sha256"],
        "public_target": cell["public_target"],
        "trace_syndrome": cell["trace_syndrome"],
        "cnf_sha256": cell["cnf_sha256"],
        "input_sha256": cell["input_sha256"],
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
        "solver_binary_sha256": sha(BINARY),
        "protocol_sha256": sha(PROTOCOL),
        "runner_source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "cpu_isolation_receipt": None,
        "controlled_wall_speedup": None,
    }
    (output / "receipt.json").write_text(json.dumps(
        receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"case": name, "status": status,
                      "verified": verified,
                      "propagations": (report or {}).get("propagations"),
                      "conflicts": (report or {}).get("conflicts"),
                      "solver_wall_seconds": solver_ns / 1e9}), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=CASES, required=True)
    args = parser.parse_args()
    run(args.case)


if __name__ == "__main__":
    main()
