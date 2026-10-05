#!/usr/bin/env python3
"""Run one frozen Q1420 root-theory PDP stage and retain all raw outcomes."""

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
ROOT = PARENT.parents[1]
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT / "q1419_partial_pin"))

from build_formula import build, write_artifacts  # noqa: E402
from run_cell import read_profile, verify_relation  # noqa: E402
from run_probe import field, parse_model, sha  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402

PROTOCOL = HERE / "protocol.json"
CONTROL_PROTOCOL = PARENT / "q1419_partial_pin/protocol.json"


def check_model(formula, model, leaves, mids, n):
    assert model is not None
    assert set(model) == set(range(1, max(model) + 1))
    assert max(model) >= formula.variables
    assert all(any(model[abs(lit)] == (lit > 0) for lit in clause)
               for clause in formula.clauses)
    assert all((sum(model[bit] for bit in row) & 1) == int(rhs)
               for row, rhs in formula.xors)
    onb = field.Onb(n)
    for pair in range(2):
        a = sum(1 << j for j, bit in enumerate(leaves[2 * pair])
                if model[bit])
        b = sum(1 << j for j, bit in enumerate(leaves[2 * pair + 1])
                if model[bit])
        mid = sum(1 << j for j, bit in enumerate(mids[pair])
                  if model[bit])
        roots = [onb.toCoords(root) for root in s3_roots(
            onb, onb.fromCoords(a), onb.fromCoords(b))]
        assert mid in roots


def check_cnf(cnf: Path, model: dict[int, bool]):
    with cnf.open() as stream:
        head = stream.readline().split()
        assert len(head) == 4 and head[:2] == ["p", "cnf"]
        variables, expected = map(int, head[2:])
        assert set(model) == set(range(1, variables + 1))
        count = 0
        for line in stream:
            literals = [int(value) for value in line.split()]
            assert literals and literals[-1] == 0
            assert all(1 <= abs(lit) <= variables for lit in literals[:-1])
            assert any(model[abs(lit)] == (lit > 0)
                       for lit in literals[:-1])
            count += 1
        assert count == expected
    return {"variables": variables, "clauses": count}


def archive(path: Path):
    output = path.with_suffix(path.suffix + ".gz")
    with output.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream,
                           mtime=0, compresslevel=9) as zipped:
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1 << 20), b""):
                    zipped.write(chunk)
    path.unlink()
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    parser.add_argument("--cell", choices=("full_lock", "free_mids", "ordinary"),
                        required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1420"
    assert protocol["candidate_id"] is None and protocol["isogeny"] == "none"
    assert protocol["source_sha256"]["run_stage.py"] == sha(Path(__file__))
    for name, digest in protocol["source_sha256"].items():
        assert sha(HERE / name) == digest
    for relative, digest in protocol["dependency_sha256"].items():
        assert sha(ROOT / relative) == digest
    binary = HERE / "theory_solver"
    assert sha(binary) == protocol["solver_binary_sha256"]
    assert sha(CONTROL_PROTOCOL) == protocol["q1419_protocol_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "sage_runtime_info_sha256"]
    assert sha(HERE / f"n{args.degree}_root_validation.json") == protocol[
        "root_validation_sha256"][str(args.degree)]
    key = f"n{args.degree}_{args.cell}"
    assert key in protocol["workloads"]
    workload = protocol["workloads"][key]
    kind = "ordinary" if args.cell == "ordinary" else "control"
    output = HERE / "runs" / key
    assert not output.exists()
    stage_start = time.perf_counter()
    formula, meta = build(args.degree, kind, args.cell)
    assert meta["curve_id"] == workload["curve_id"]
    assert meta["public_target"] == workload["public_target"]
    assert meta["factor_base_actual_B"] == workload[
        "factor_base_actual_B"]
    assert meta["folded_columns_K"] == workload["folded_columns_K"]
    assert meta["parent_receipt_sha256"] == workload[
        "parent_receipt_sha256"]
    assert meta["field_bridge_export_sha256"] == workload[
        "field_bridge_export_sha256"]
    variables, clauses = write_artifacts(formula, meta, output)
    build_seconds = time.perf_counter() - stage_start
    cnf = output / "system.cnf"
    model_path = output / "solver.model.txt"
    command = [str(binary), str(HERE / f"n{args.degree}_field.txt"),
               str(cnf), str(output / "variables.txt"), str(model_path),
               str(protocol["solver_conflict_cap"])]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    solve_start = time.perf_counter()
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True,
            timeout=protocol["solver_wall_cap_seconds"])
        stdout, stderr, return_code = (completed.stdout, completed.stderr,
                                       completed.returncode)
        status = {0: "sat", 10: "censored", 20: "unsat"}.get(
            return_code, "error")
    except subprocess.TimeoutExpired as error:
        stdout = (error.stdout or b"").decode(errors="replace")
        stderr = (error.stderr or b"").decode(errors="replace")
        return_code, status = None, "external_timeout"
    solver_process_seconds = time.perf_counter() - solve_start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    stdout_path = output / "solver.stdout.txt"
    stderr_path = output / "solver.stderr.txt"
    stdout_path.write_text(stdout)
    stderr_path.write_text(stderr)
    solver = None
    solver_report_error = None
    if stdout.strip():
        try:
            solver = json.loads(stdout)
            expected_status = {"sat": 10, "censored": 0, "unsat": 20}
            assert solver["status"] == expected_status[status]
            assert solver["cnf_variables"] == variables
            assert solver["cnf_clauses"] == clauses
        except (AssertionError, KeyError, ValueError) as error:
            solver_report_error = repr(error)
            solver = None
    checked = None
    verification_error = None
    check_start = time.perf_counter()
    if status == "sat":
        try:
            model = parse_model(model_path.read_text())
            check_cnf(cnf, model)
            check_model(formula, model, meta["leaf_variables"],
                        meta["pair_mid_variables"], args.degree)
            control = json.loads(CONTROL_PROTOCOL.read_text())
            profile, _, _ = read_profile(control, args.degree)
            profile = dict(profile)
            profile["public_target"] = meta["public_target"]
            checked = verify_relation(profile, model, meta["leaf_variables"])
        except (AssertionError, KeyError, OSError, ValueError) as error:
            verification_error = repr(error)
    check_seconds = time.perf_counter() - check_start
    archive_path = archive(cnf)
    receipt = {
        "proposal_id": "Q1420", "candidate_id": None,
        "stage_config_id": workload["stage_config_id"],
        "workload_id": workload["workload_id"],
        "stage_run_id": workload["stage_run_id"],
        "curve_id": meta["curve_id"], "isogeny": "none",
        "degree_n": args.degree, "cell": args.cell,
        "input_law": meta["input_law"],
        "factor_base_actual_B": meta["factor_base_actual_B"],
        "folded_columns_K": meta["folded_columns_K"],
        "factor_base_enumerated_set_sha256": meta[
            "factor_base_enumerated_set_sha256"],
        "public_target": meta["public_target"],
        "cnf_variables": variables, "cnf_clauses": clauses,
        "cnf_raw_bytes": meta["cnf_bytes"],
        "cnf_raw_sha256": meta["cnf_sha256"],
        "cnf_archive_sha256": sha(archive_path),
        "variable_map_sha256": sha(output / "variables.txt"),
        "metadata_sha256": sha(output / "meta.json"),
        "solver_status": status,
        "solver_return_code": return_code,
        "solver_process_wall_seconds_exploratory": solver_process_seconds,
        "formula_build_wall_seconds_exploratory": build_seconds,
        "model_check_wall_seconds_exploratory": check_seconds,
        "solver_report": solver,
        "solver_report_error": solver_report_error,
        "solver_stdout_sha256": sha(stdout_path),
        "solver_stderr_sha256": sha(stderr_path),
        "solver_model_sha256": sha(model_path) if model_path.exists() else None,
        "peak_child_rss_raw": after.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
        "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
        "model_check": checked,
        "verification_error": verification_error,
        "verified_relation_count": int(checked is not None and checked[
            "status"] == "verified_four_point_relation"),
        "formula_build_field_mul_calls": args.degree ** 2,
        "formula_build_field_sqr_calls": args.degree,
        "complete_field_operation_equivalent_count": None,
        "natural_relation_yield_estimate": None,
        "complete_solve_work_log2": None,
        "protocol_sha256": sha(PROTOCOL),
        "runner_source_sha256": sha(Path(__file__)),
        "solver_binary_sha256": sha(binary),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2,
                                                    sort_keys=True) + "\n")
    print(json.dumps({"degree": args.degree, "cell": args.cell,
                      "status": status,
                      "verified_relations": receipt["verified_relation_count"],
                      "solver_process_seconds": solver_process_seconds,
                      "oracle_pairs": (solver or {}).get(
                          "cached_pair_assignments")}))


if __name__ == "__main__":
    main()
