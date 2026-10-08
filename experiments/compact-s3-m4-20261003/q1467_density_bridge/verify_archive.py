#!/usr/bin/env python3
"""Independently replay Q1467 models and audit frozen run artifacts."""

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

from q1438_dense_base.verify_solver import model_relation  # noqa: E402
from q1467_density_bridge.build_inputs import base, make_case  # noqa: E402

PROTOCOL = HERE / "solver_protocol.json"
RESULT = HERE / "archive_verification.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def replay(name: str, model: Path) -> dict:
    folder = HERE / "inputs" / name
    raw, varmap, targets, meta, variables, clauses, formula = make_case(name)
    assert raw == gzip.decompress((folder / "system.cnf.gz").read_bytes())
    assert varmap == (folder / "variables.txt").read_bytes()
    assert targets == (folder / "targets.txt").read_bytes()
    assert meta == json.loads((folder / "meta.json").read_text())
    instances = json.loads((PARENT /
        "q1438_dense_base/solver_protocol.json").read_text())["instances"]
    instance = dict(instances[str(meta["degree_n"])])
    instance["new_weight_bound"] = meta["normal_basis_weight_bound"]
    relation = model_relation(raw, formula, meta, variables, len(clauses),
                              model, instance)
    if relation["status"] == "verified_four_point_relation" and (
            meta["degree_n"] == 53):
        allowed = set(base(53)["allowed"])
        assert all(mask in allowed for mask in relation["raw_leaf_x"])
    return relation


def describe() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1467"
    assert protocol["protocol_revision"] == 2
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "runtime_info_sha256"]
    assert sha(PARENT / "q1466_leaf_rotation/native_solver") == protocol[
        "binary_sha256"]
    assert sha(HERE / "solver_protocol_v1.json") == protocol[
        "supersedes_protocol_sha256"]
    rows = []
    for name in protocol["run_order"]:
        cell = protocol["cells"][name]
        folder = HERE / "inputs" / name
        output = HERE / "runs" / name
        for leaf, digest in cell["input_sha256"].items():
            assert sha(folder / leaf) == digest, (name, leaf)
        receipt_path = output / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["proposal_id"] == "Q1467"
        assert receipt["candidate_id"] is None
        assert receipt["run_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["protocol_sha256"] == sha(PROTOCOL)
        assert receipt["runner_source_sha256"] == protocol[
            "source_sha256"]["experiments/compact-s3-m4-20261003/"
                             "q1467_density_bridge/run_stage.py"]
        assert receipt["runtime_info_sha256"] == protocol[
            "runtime_info_sha256"]
        assert receipt["binary_sha256"] == protocol["binary_sha256"]
        for key in ("curve_id", "degree_n", "factor_base_actual_B",
                    "folded_columns_K", "factor_base_enumerated_set_sha256",
                    "workload_id", "public_target", "input_role", "leaves_pinned",
                    "cnf_sha256", "cnf_variables", "cnf_clauses"):
            assert receipt[key] == cell[key], (name, key)
        assert receipt["solver_stdout_sha256"] == sha(
            output / "solver.stdout.txt")
        assert receipt["solver_stderr_sha256"] == sha(
            output / "solver.stderr.txt")
        assert receipt["solver_process_wall_ns_exploratory"] > 0
        assert receipt["complete_n131_log2_work"] is None
        assert receipt["challenge_run_admitted"] is False
        status = receipt["solver_status"]
        report = receipt["solver_report"]
        assert receipt["solver_report_error"] is None
        assert report is not None
        assert report["status"] == {"sat": 10, "censored": 0,
                                     "unsat": 20}[status]
        assert report["cnf_variables"] == cell["cnf_variables"]
        assert report["cnf_clauses"] == cell["cnf_clauses"]
        assert report["pair_cap"] == protocol["pair_candidate_cap"]
        model = output / "solver.model.txt"
        relation_status = None
        if status == "sat":
            assert receipt["solver_model_sha256"] == sha(model)
            assert receipt["model_check_error"] is None
            relation = replay(name, model)
            assert relation == receipt["model_check"]
            relation_status = relation["status"]
            assert receipt["verified_relation_count"] == int(
                relation_status == "verified_four_point_relation")
        else:
            assert not model.exists()
            assert receipt["solver_model_sha256"] is None
            assert receipt["model_check"] is None
            assert receipt["verified_relation_count"] == 0
        rows.append({
            "case": name, "solver_status": status,
            "model_status": relation_status,
            "verified_relation_count": receipt["verified_relation_count"],
            "joint_eligible_checks": report["joint_eligible_checks"],
            "solver_process_wall_ns_exploratory": receipt[
                "solver_process_wall_ns_exploratory"],
            "receipt_sha256": sha(receipt_path),
        })
    assert [row["verified_relation_count"] for row in rows] == [1, 1, 0,
                                                                0, 0, 0]
    old = HERE / "runs_v1/n53_planted"
    old_receipt = json.loads((old / "receipt.json").read_text())
    assert old_receipt["protocol_sha256"] == sha(HERE /
        "solver_protocol_v1.json")
    assert old_receipt["solver_status"] == "sat"
    assert old_receipt["verified_relation_count"] == 0
    assert old_receipt["model_check_error"] == "AssertionError()"
    old_relation = replay("n53_planted", old / "solver.model.txt")
    assert old_relation["status"] == "verified_four_point_relation"
    return {
        "kind": "q1467_density_bridge_archive_verification",
        "status": "passed", "proposal_id": "Q1467",
        "candidate_id": None, "isogeny": "none",
        "protocol_sha256": sha(PROTOCOL),
        "verifier_source_sha256": sha(Path(__file__)),
        "rows": rows,
        "superseded_v1": {
            "case": "n53_planted",
            "receipt_sha256": sha(old / "receipt.json"),
            "protocol_sha256": sha(HERE / "solver_protocol_v1.json"),
            "original_model_check_error": old_receipt["model_check_error"],
            "posthoc_model_status": old_relation["status"],
            "scope": "verification wrapper passed a clause list instead of its length; archived receipt remains unchanged",
        },
        "claim_scope": (
            "exact model replay and archive integrity; pinned controls are "
            "correctness only; censored ordinary cells do not estimate "
            "natural yield or successful point-decomposition cost"),
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert not (args.emit and args.check)
    result = describe()
    if args.emit:
        assert not RESULT.exists(), "refuse overwrite"
        RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    elif args.check:
        assert result == json.loads(RESULT.read_text())
    print(json.dumps({"status": result["status"],
                      "verified_relation_count": sum(
                          row["verified_relation_count"]
                          for row in result["rows"]),
                      "censored_count": sum(
                          row["solver_status"] == "censored"
                          for row in result["rows"])}), flush=True)


if __name__ == "__main__":
    main()
