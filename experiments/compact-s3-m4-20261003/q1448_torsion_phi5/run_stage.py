#!/usr/bin/env python3
"""Run one frozen Q1448 ordinary target through the compact phi5 SAT stage."""

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

from q1420_root_theory.build_formula import convert_to_cnf  # noqa: E402
from q1425_reverse_pair.relax_control import serialize_cnf  # noqa: E402
from q1448_torsion_phi5.build_formula import build  # noqa: E402
from q1448_torsion_phi5.verify_model import replay  # noqa: E402

PROTOCOL = HERE / "protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1448"
    assert protocol["candidate_id"] is None and protocol["isogeny"] == "none"
    cell = protocol["cells"][str(args.degree)]
    assert sha(HERE / "validation.json") == protocol["validation_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "sage_runtime_info_sha256"]
    assert sha(Path(protocol["cadical_binary_path"])) == protocol[
        "cadical_binary_sha256"]
    for path, digest in protocol["source_sha256"].items():
        assert sha(ROOT / path) == digest
    for path, digest in protocol["input_sha256"].items():
        assert sha(ROOT / path) == digest
    output = HERE / "runs" / f"n{args.degree}_ordinary"
    if output.exists():
        raise FileExistsError(f"refuse overwrite of {output}")

    stage_start = time.perf_counter_ns()
    build_start = stage_start
    formula, meta = build(args.degree)
    variables, clauses = convert_to_cnf(formula)
    raw = serialize_cnf(variables, clauses)
    build_ns = time.perf_counter_ns() - build_start
    assert meta["curve_id"] == cell["curve_id"]
    assert meta["factor_base_actual_B"] == cell["factor_base_actual_B"]
    assert meta["folded_columns_K"] == cell["folded_columns_K"]
    assert meta["factor_base_enumerated_set_sha256"] == cell[
        "factor_base_enumerated_set_sha256"]
    assert meta["public_target"] == cell["public_target"]
    assert hashlib.sha256(raw).hexdigest() == cell["cnf_raw_sha256"]
    assert variables == cell["cnf_variables"]
    assert len(clauses) == cell["cnf_clauses"]
    assert len(raw) == cell["cnf_raw_bytes"]

    output.mkdir(parents=True)
    cnf_path = output / "system.cnf"
    archive = output / "system.cnf.gz"
    model_path = output / "solver.model.txt"
    cnf_path.write_bytes(raw)
    archive.write_bytes(gzip.compress(raw, mtime=0))
    command = [protocol["cadical_binary_path"], "-t",
               str(protocol["solver_wall_cap_seconds"]), "-c",
               str(protocol["solver_conflict_cap"]), "-w", str(model_path),
               str(cnf_path)]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    solver_start = time.perf_counter_ns()
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True,
            timeout=protocol["external_process_safeguard_seconds"],
            check=False)
        stdout, stderr = completed.stdout, completed.stderr
        exit_code = completed.returncode
        status = {10: "sat", 20: "unsat", 0: "censored"}.get(
            exit_code, "error")
    except subprocess.TimeoutExpired as error:
        stdout = (error.stdout or b"").decode(errors="replace")
        stderr = (error.stderr or b"").decode(errors="replace")
        exit_code, status = None, "external_timeout"
    solver_ns = time.perf_counter_ns() - solver_start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    (output / "solver.stdout.txt").write_text(stdout)
    (output / "solver.stderr.txt").write_text(stderr)
    cnf_path.unlink()

    model_check_start = time.perf_counter_ns()
    check = error_text = None
    if status == "sat":
        try:
            check = replay(formula, meta, model_path, cell["instance"])
        except Exception as error:
            error_text = repr(error)
    check_ns = time.perf_counter_ns() - model_check_start
    verified = int(check is not None and check.get("status") ==
                   "verified_four_point_relation")
    receipt = {
        "kind": "q1448_torsion_phi5_ordinary_stage_run",
        "proposal_id": "Q1448", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4phi5",
        "degree_n": args.degree,
        "curve_id": cell["curve_id"],
        "workload_id": cell["workload_id"],
        "factor_base_actual_B": cell["factor_base_actual_B"],
        "folded_columns_K": cell["folded_columns_K"],
        "factor_base_enumerated_set_sha256": cell[
            "factor_base_enumerated_set_sha256"],
        "public_target": cell["public_target"],
        "target_preimage_x_count": cell["target_preimage_x_count"],
        "solver_status": status,
        "solver_exit_code": exit_code,
        "solver_command": command,
        "solver_stdout_sha256": sha(output / "solver.stdout.txt"),
        "solver_stderr_sha256": sha(output / "solver.stderr.txt"),
        "solver_model_sha256": sha(model_path) if model_path.exists() else None,
        "model_check": check,
        "model_check_error": error_text,
        "verified_relation_count": verified,
        "cnf_raw_sha256": hashlib.sha256(raw).hexdigest(),
        "cnf_archive_sha256": sha(archive),
        "cnf_variables": variables,
        "cnf_clauses": len(clauses),
        "cnf_raw_bytes": len(raw),
        "formula_build_wall_ns_exploratory": build_ns,
        "solver_process_wall_ns_exploratory": solver_ns,
        "model_replay_wall_ns_exploratory": check_ns,
        "charged_target_dependent_stage_wall_ns_exploratory":
            time.perf_counter_ns() - stage_start,
        "peak_child_rss_raw": after.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
        "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
        "natural_relation_yield_estimate": None,
        "novel_rank_per_query": None,
        "cost_per_useful_row": None,
        "complete_n131_log2_work": None,
        "cpu_isolation_receipt": None,
        "protocol_sha256": sha(PROTOCOL),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "cadical_binary_sha256": sha(Path(protocol["cadical_binary_path"])),
        "runner_source_sha256": sha(Path(__file__)),
    }
    (output / "receipt.json").write_text(json.dumps(
        receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"degree_n": args.degree, "status": status,
                      "verified_relation_count": verified,
                      "model_check_error": error_text,
                      "solver_seconds": solver_ns / 1e9}), flush=True)


if __name__ == "__main__":
    main()
