#!/usr/bin/env python3
"""Run one frozen Q1487 inverse-partner stage, retaining censored attempts."""

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
Q1482 = HERE.parent / "q1482_window_s3"
Q1486 = HERE.parent / "q1486_window_aware_pair"
sys.path.insert(0, str(Q1482))
from build_formula import PARENT, build_cnf  # noqa: E402
from verify_model import model_relation

ROOT = HERE.parents[2]
PROTOCOL = HERE / "protocol.json"
BINARY = HERE / "native_solver"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case: str):
    protocol = json.loads(PROTOCOL.read_text())
    assert case in protocol["run_order"]
    assert protocol["proposal_id"] == "Q1487"
    assert protocol["candidate_id"] is protocol["run_id"] is None
    assert protocol["isogeny"] == "none"
    assert sha(BINARY) == protocol["solver_binary_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "runtime_info_sha256"]
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    entry = protocol["cases"][case]
    n = entry["degree_n"]
    input_dir = Q1482 / "inputs" / case
    assert sha(input_dir / "input.json") == entry["input_receipt_sha256"]
    for name, digest in entry["input_sha256"].items():
        assert sha(input_dir / name) == digest
    window_dir = Q1486 / "inputs" / case
    window_map = window_dir / "windows.map"
    map_receipt = window_dir / "map_receipt.json"
    assert sha(window_map) == entry["window_sidecar_sha256"]
    assert sha(map_receipt) == entry["window_sidecar_receipt_sha256"]
    assert json.loads(map_receipt.read_text())[
        "q1482_cnf_raw_sha256"] == entry["cnf_raw_sha256"]
    output = HERE / "runs" / case
    assert not output.exists(), "refuse to overwrite frozen run"

    encode_start = time.perf_counter_ns()
    raw, varmap, targets, formula, meta, variables, clauses = build_cnf(
        n, entry["role"])
    encode_ns = time.perf_counter_ns() - encode_start
    assert hashlib.sha256(raw).hexdigest() == entry["cnf_raw_sha256"]
    assert hashlib.sha256(varmap).hexdigest() == entry[
        "input_sha256"]["variables.txt"]
    assert hashlib.sha256(targets).hexdigest() == entry[
        "input_sha256"]["targets.txt"]
    assert gzip.decompress((input_dir / "system.cnf.gz").read_bytes()) == raw
    assert variables == entry["cnf_variables"]
    assert clauses == entry["cnf_clauses"]
    assert meta["public_target"] == entry["public_target"]
    assert meta["target_preimage_x_count"] == entry[
        "target_preimage_x_count"]
    assert meta["factor_base_actual_B"] == entry[
        "factor_base_actual_B"]
    field_file = PARENT / f"q1420_root_theory/n{n}_field.txt"
    assert sha(field_file) == protocol["field_file_sha256"][str(n)]
    output.mkdir(parents=True)
    cnf = output / "system.cnf"
    model = output / "solver.model.txt"
    materialize_start = time.perf_counter_ns()
    cnf.write_bytes(raw)
    materialize_ns = time.perf_counter_ns() - materialize_start
    command = [str(BINARY), str(field_file), str(cnf),
               str(input_dir / "variables.txt"), str(model),
               str(protocol["conflict_cap"]),
               str(protocol["native_wall_cap_seconds"]),
               str(input_dir / "targets.txt"),
               str(protocol["anchor_option_cap"]),
               protocol["decision_policy"], str(window_map)]
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
            assert report["anchor_option_cap"] == protocol[
                "anchor_option_cap"]
            assert report["window_selector_count"] == 4 * n
            assert report["window_dimension_d"] == protocol["stages"][
                str(n)]["stage_config_hash_input"]["point_decomposition"][
                    "theory_hamming_weight_superset_bound"]
            assert report["cnf_variables"] == variables
            assert report["cnf_clauses"] == clauses
            assert report["target_preimage_count"] == entry[
                "target_preimage_x_count"]
            assert report["propagations"] >= 0
        except Exception as error:
            report_error = repr(error)
            report = None
    check_start = time.perf_counter_ns()
    relation = relation_error = None
    if status == "sat" and report is not None:
        try:
            relation = model_relation(raw, formula, meta, variables,
                                      clauses, model)
        except Exception as error:
            relation_error = repr(error)
    check_ns = time.perf_counter_ns() - check_start
    verified = int(relation is not None and relation.get("status") ==
                   "verified_four_point_relation")
    charged_stage_ns = encode_ns + materialize_ns + solver_ns + check_ns
    receipt = {
        "kind": "q1487_inverse_partner_compact_s3_stage_run",
        "proposal_id": "Q1487", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "stage_config_id": entry["stage_config_id"],
        "stage_run_id": entry["stage_run_id"],
        "case": case, "input_role": entry["role"],
        "curve_id": entry["curve_id"], "degree_n": n,
        "factor_base_actual_B": entry["factor_base_actual_B"],
        "folded_columns_K": entry["folded_columns_K"],
        "factor_base_enumerated_set_sha256": entry[
            "factor_base_enumerated_set_sha256"],
        "workload_id": entry["workload_id"],
        "parent_workload_id": entry["parent_workload_id"],
        "public_target": entry["public_target"],
        "cnf_raw_sha256": entry["cnf_raw_sha256"],
        "input_sha256": entry["input_sha256"],
        "input_receipt_sha256": entry["input_receipt_sha256"],
        "window_sidecar_sha256": entry["window_sidecar_sha256"],
        "window_sidecar_receipt_sha256": entry[
            "window_sidecar_receipt_sha256"],
        "native_status": status, "native_exit_code": exit_code,
        "native_report": report, "native_report_error": report_error,
        "independent_model_check": relation,
        "independent_model_check_error": relation_error,
        "verified_relation_count": verified,
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "target_encoding_wall_ns_exploratory": encode_ns,
        "input_materialization_wall_ns_exploratory": materialize_ns,
        "solver_process_wall_ns_exploratory": solver_ns,
        "relation_check_wall_ns_exploratory": check_ns,
        "charged_stage_wall_ns_exploratory": charged_stage_ns,
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
        receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case": case, "status": status,
                      "verified": verified,
                      "propagations": (report or {}).get("propagations"),
                      "conflicts": (report or {}).get("conflicts"),
                      "charged_stage_seconds": charged_stage_ns / 1e9}),
          flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=json.loads(PROTOCOL.read_text())[
        "run_order"], required=True)
    args = parser.parse_args()
    run(args.case)


if __name__ == "__main__":
    main()
