#!/usr/bin/env python3
"""Audit Q1420 receipts, serialized CNFs and any returned SAT models."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT / "q1419_partial_pin"))

from build_formula import build, convert_to_cnf  # noqa: E402
from run_cell import read_profile, verify_relation  # noqa: E402
from run_probe import field, sha  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402

PROTOCOL = HERE / "protocol.json"
CONTROL_PROTOCOL = PARENT / "q1419_partial_pin/protocol.json"


def model_from_file(path):
    text = path.read_text()
    assert "s SATISFIABLE" in text
    model = {}
    for line in text.splitlines():
        if line.startswith("v "):
            for token in line[2:].split():
                lit = int(token)
                if lit:
                    assert abs(lit) not in model
                    model[abs(lit)] = lit > 0
    return model


def check_cnf(raw, model, expected_variables, expected_clauses):
    lines = raw.decode("ascii").splitlines()
    head = lines.pop(0).split()
    assert head == ["p", "cnf", str(expected_variables),
                    str(expected_clauses)]
    assert set(model) == set(range(1, expected_variables + 1))
    assert len(lines) == expected_clauses
    for line in lines:
        lits = [int(token) for token in line.split()]
        assert lits and lits[-1] == 0
        assert all(1 <= abs(lit) <= expected_variables for lit in lits[:-1])
        assert any(model[abs(lit)] == (lit > 0) for lit in lits[:-1])


def check_math(formula, meta, model):
    assert all(any(model[abs(lit)] == (lit > 0) for lit in clause)
               for clause in formula.clauses)
    assert all((sum(model[bit] for bit in row) & 1) == int(rhs)
               for row, rhs in formula.xors)
    n = meta["degree_n"]
    onb = field.Onb(n)
    for pair in range(2):
        values = []
        for bits in meta["leaf_variables"][2 * pair:2 * pair + 2]:
            values.append(sum(1 << j for j, bit in enumerate(bits)
                              if model[bit]))
        mid = sum(1 << j for j, bit in enumerate(
            meta["pair_mid_variables"][pair]) if model[bit])
        roots = {onb.toCoords(value) for value in s3_roots(
            onb, *(onb.fromCoords(value) for value in values))}
        assert mid in roots
    profile, _, _ = read_profile(json.loads(CONTROL_PROTOCOL.read_text()), n)
    profile = dict(profile)
    profile["public_target"] = meta["public_target"]
    return verify_relation(profile, model, meta["leaf_variables"])


def verify_cell(protocol, key):
    expected = protocol["workloads"][key]
    path = HERE / "runs" / key
    receipt_path = path / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    meta = json.loads((path / "meta.json").read_text())
    n = meta["degree_n"]
    cell = meta["cell"]
    assert key == f"n{n}_{cell}"
    assert receipt["proposal_id"] == "Q1420"
    assert receipt["candidate_id"] is None and receipt["isogeny"] == "none"
    for field_name in ("curve_id", "factor_base_actual_B",
                       "folded_columns_K", "factor_base_enumerated_set_sha256",
                       "public_target"):
        assert receipt[field_name] == expected[field_name] == meta[field_name]
    assert receipt["stage_config_id"] == expected["stage_config_id"]
    assert receipt["workload_id"] == expected["workload_id"]
    assert receipt["stage_run_id"] == expected["stage_run_id"]
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["runner_source_sha256"] == protocol["source_sha256"][
        "run_stage.py"]
    assert receipt["solver_binary_sha256"] == protocol[
        "solver_binary_sha256"]
    assert receipt["runtime_info_sha256"] == protocol[
        "sage_runtime_info_sha256"]
    assert receipt["metadata_sha256"] == sha(path / "meta.json")
    assert receipt["variable_map_sha256"] == sha(path / "variables.txt")
    assert receipt["solver_stdout_sha256"] == sha(path / "solver.stdout.txt")
    assert receipt["solver_stderr_sha256"] == sha(path / "solver.stderr.txt")
    compressed = path / "system.cnf.gz"
    assert receipt["cnf_archive_sha256"] == sha(compressed)
    raw = gzip.decompress(compressed.read_bytes())
    assert len(raw) == receipt["cnf_raw_bytes"]
    assert hashlib.sha256(raw).hexdigest() == receipt["cnf_raw_sha256"]
    assert receipt["cnf_raw_sha256"] == meta["cnf_sha256"]
    formula, rebuilt_meta = build(n, "ordinary" if cell == "ordinary"
                                 else "control", cell)
    variables, clauses = convert_to_cnf(formula)
    assert variables == receipt["cnf_variables"]
    assert len(clauses) == receipt["cnf_clauses"]
    assert rebuilt_meta["public_target"] == meta["public_target"]
    if receipt["solver_status"] == "sat":
        model_path = path / "solver.model.txt"
        assert receipt["solver_model_sha256"] == sha(model_path)
        model = model_from_file(model_path)
        check_cnf(raw, model, variables, len(clauses))
        relation = check_math(formula, meta, model)
        assert relation == receipt["model_check"]
        assert receipt["verified_relation_count"] == int(
            relation["status"] == "verified_four_point_relation")
        status = relation["status"]
    else:
        assert receipt["solver_model_sha256"] is None
        assert receipt["model_check"] is None
        assert receipt["verified_relation_count"] == 0
        assert receipt["solver_status"] in (
            "censored", "external_timeout", "unsat", "error")
        status = receipt["solver_status"]
    assert receipt["natural_relation_yield_estimate"] is None
    assert receipt["complete_solve_work_log2"] is None
    return {"key": key, "status": status,
            "verified_relation_count": receipt["verified_relation_count"],
            "solver_process_wall_seconds_exploratory": receipt[
                "solver_process_wall_seconds_exploratory"],
            "receipt_sha256": sha(receipt_path)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--emit", action="store_true")
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["source_sha256"]["verify_archive.py"] == sha(
        Path(__file__))
    checks, missing = [], []
    for key in protocol["run_order"]:
        if (HERE / "runs" / key / "receipt.json").exists():
            checks.append(verify_cell(protocol, key))
        else:
            missing.append(key)
    assert not args.require_complete or not missing
    report = {"kind": "q1420_archive_verification",
              "proposal_id": "Q1420", "protocol_sha256": sha(PROTOCOL),
              "verifier_source_sha256": sha(Path(__file__)),
              "checks": checks, "missing": missing,
              "complete": not missing,
              "natural_relation_yield_estimate": None,
              "complete_solve_work_log2": None}
    if args.emit:
        (HERE / "verification.json").write_text(json.dumps(
            report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"checked": len(checks), "missing": missing,
                      "verified_relations": sum(row[
                          "verified_relation_count"] for row in checks)}))


if __name__ == "__main__":
    main()
