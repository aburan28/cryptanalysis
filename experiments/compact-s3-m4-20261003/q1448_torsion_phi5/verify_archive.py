#!/usr/bin/env python3
"""Independently audit frozen Q1448 ordinary CNFs and model receipts."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))

from q1420_root_theory.build_formula import convert_to_cnf  # noqa: E402
from q1425_reverse_pair.relax_control import serialize_cnf  # noqa: E402
from q1448_torsion_phi5.build_formula import build  # noqa: E402
from q1448_torsion_phi5.verify_model import (  # noqa: E402
    model_from_file, replay)

PROTOCOL = HERE / "protocol.json"
OUTPUT = HERE / "verification.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_cnf(raw: bytes, model: dict[int, bool], variables: int,
              clause_count: int) -> None:
    lines = raw.decode("ascii").splitlines()
    assert lines.pop(0).split() == ["p", "cnf", str(variables),
                                    str(clause_count)]
    assert set(model) == set(range(1, variables + 1))
    assert len(lines) == clause_count
    for line in lines:
        lits = [int(token) for token in line.split()]
        assert lits and lits[-1] == 0
        assert any(model[abs(lit)] == (lit > 0) for lit in lits[:-1])


def audit() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1448"
    assert protocol["candidate_id"] is None and protocol["isogeny"] == "none"
    assert protocol["point_decomposition_stage_code"] == "PDP4phi5"
    assert protocol["complete_n131_log2_work"] is None
    assert protocol["challenge_run_admitted"] is False
    for name, digest in protocol["source_sha256"].items():
        assert sha(ROOT / name) == digest
    for name, digest in protocol["input_sha256"].items():
        assert sha(ROOT / name) == digest
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "sage_runtime_info_sha256"]
    assert sha(HERE / "validation.json") == protocol["validation_sha256"]
    assert sha(Path(protocol["cadical_binary_path"])) == protocol[
        "cadical_binary_sha256"]
    parent = json.loads((PARENT / "q1438_dense_base/solver_protocol.json").read_text())
    rows = []
    for n in (53, 83):
        cell = protocol["cells"][str(n)]
        matched = parent["workloads"][f"n{n}_ordinary"]
        for a, b in (("curve_id", "curve_id"),
                     ("factor_base_actual_B", "factor_base_actual_B"),
                     ("folded_columns_K", "folded_columns_K"),
                     ("factor_base_enumerated_set_sha256",
                      "factor_base_enumerated_set_sha256"),
                     ("public_target", "public_target")):
            assert cell[a] == matched[b]
        formula, meta = build(n)
        variables, clauses = convert_to_cnf(formula)
        raw = serialize_cnf(variables, clauses)
        assert hashlib.sha256(raw).hexdigest() == cell["cnf_raw_sha256"]
        assert variables == cell["cnf_variables"]
        assert len(clauses) == cell["cnf_clauses"]
        assert len(raw) == cell["cnf_raw_bytes"]
        output = HERE / "runs" / f"n{n}_ordinary"
        receipt_path = output / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["proposal_id"] == "Q1448"
        assert receipt["candidate_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["point_decomposition_stage_code"] == "PDP4phi5"
        assert receipt["curve_id"] == cell["curve_id"]
        assert receipt["workload_id"] == cell["workload_id"]
        assert receipt["factor_base_actual_B"] == cell[
            "factor_base_actual_B"]
        assert receipt["folded_columns_K"] == cell["folded_columns_K"]
        assert receipt["factor_base_enumerated_set_sha256"] == cell[
            "factor_base_enumerated_set_sha256"]
        assert receipt["public_target"] == cell["public_target"]
        assert receipt["protocol_sha256"] == sha(PROTOCOL)
        assert receipt["runner_source_sha256"] == sha(HERE / "run_stage.py")
        assert receipt["runtime_info_sha256"] == protocol[
            "sage_runtime_info_sha256"]
        assert receipt["cnf_raw_sha256"] == cell["cnf_raw_sha256"]
        assert receipt["cnf_archive_sha256"] == sha(
            output / "system.cnf.gz")
        assert gzip.decompress((output / "system.cnf.gz").read_bytes()) == raw
        assert receipt["solver_stdout_sha256"] == sha(
            output / "solver.stdout.txt")
        assert receipt["solver_stderr_sha256"] == sha(
            output / "solver.stderr.txt")
        assert receipt["natural_relation_yield_estimate"] is None
        assert receipt["complete_n131_log2_work"] is None
        if receipt["solver_status"] == "sat":
            model_path = output / "solver.model.txt"
            assert receipt["solver_model_sha256"] == sha(model_path)
            model = model_from_file(model_path)
            check_cnf(raw, model, variables, len(clauses))
            checked = replay(formula, meta, model_path, cell["instance"])
            assert checked == receipt["model_check"]
            assert receipt["verified_relation_count"] == int(
                checked["status"] == "verified_four_point_relation")
            status = checked["status"]
        else:
            assert receipt["solver_status"] in (
                "censored", "external_timeout", "unsat", "error")
            assert receipt["verified_relation_count"] == 0
            assert receipt["model_check"] is None
            status = receipt["solver_status"]
        rows.append({
            "degree_n": n,
            "curve_id": cell["curve_id"],
            "status": status,
            "solver_status": receipt["solver_status"],
            "verified_relation_count": receipt["verified_relation_count"],
            "receipt_sha256": sha(receipt_path),
            "cnf_archive_sha256": sha(output / "system.cnf.gz"),
        })
    return {
        "kind": "q1448_torsion_phi5_archive_audit",
        "proposal_id": "Q1448", "candidate_id": None,
        "isogeny": "none", "status": "pass",
        "rows": rows,
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "ordinary_n83_relation_measured": bool(rows[1][
            "verified_relation_count"]),
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.emit == args.check:
        parser.error("choose --emit or --check")
    result = audit()
    if args.emit:
        if OUTPUT.exists():
            raise FileExistsError(f"refuse overwrite of {OUTPUT}")
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    else:
        assert json.loads(OUTPUT.read_text()) == result
        print("Q1448 independent N53/N83 archive audit: PASS")


if __name__ == "__main__":
    main()
