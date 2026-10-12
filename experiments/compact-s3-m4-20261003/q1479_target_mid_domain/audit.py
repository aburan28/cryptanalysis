#!/usr/bin/env python3
"""Audit Q1479 source custody, matched workloads, and every solver receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1476 = PARENT / "q1476_trace_syndrome"
sys.path.insert(0, str(PARENT))

from q1476_trace_syndrome.audit import verify_model  # noqa: E402
from q1479_target_mid_domain.freeze_protocol import render  # noqa: E402
from q1479_target_mid_domain.validate_domain import (  # noqa: E402
    describe as validate_domain,
)

RESULT = HERE / "archive_audit.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def describe() -> dict:
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol == render()
    assert protocol["candidate_id"] is protocol["run_id"] is None
    assert protocol["isogeny"] == "none"
    assert sha(HERE / "native_solver") == protocol["solver_binary_sha256"]
    assert sha(HERE / "compile_receipt.json") == protocol[
        "solver_compile_receipt_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "runtime_info_sha256"]
    assert sha(Q1476 / "protocol.json") == protocol[
        "parent_q1476_protocol_sha256"]
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert json.loads((HERE / "domain_validation.json").read_text()) == (
        validate_domain())
    manifest = json.loads((Q1476 / "input_manifest.json").read_text())
    assert sha(Q1476 / "input_manifest.json") == protocol[
        "input_manifest_sha256"]
    rows = []
    for name in protocol["run_order"]:
        cell = manifest["cases"][name]
        stage = protocol["cases"][name]
        assert stage["curve_id"] == cell["curve_id"]
        assert stage["workload_id"] == cell["workload_id"]
        assert stage["input_sha256"] == cell["input_sha256"]
        assert sha(Q1476 / "runs" / name / "receipt.json") == stage[
            "parent_q1476_receipt_sha256"]
        for leaf, digest in cell["input_sha256"].items():
            assert sha(Q1476 / "inputs" / name / leaf) == digest
        folder = HERE / "runs" / name
        receipt = json.loads((folder / "receipt.json").read_text())
        assert receipt["proposal_id"] == "Q1479"
        assert receipt["candidate_id"] is receipt["run_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["stage_config_id"] == stage["stage_config_id"]
        assert receipt["stage_run_id"] == stage["stage_run_id"]
        assert receipt["curve_id"] == cell["curve_id"]
        assert receipt["workload_id"] == cell["workload_id"]
        assert receipt["factor_base_actual_B"] == cell[
            "factor_base_actual_B"]
        assert receipt["folded_columns_K"] == cell["folded_columns_K"]
        assert receipt["factor_base_enumerated_set_sha256"] == cell[
            "factor_base_enumerated_set_sha256"]
        assert receipt["input_sha256"] == cell["input_sha256"]
        assert receipt["cnf_sha256"] == cell["cnf_sha256"]
        assert receipt["solver_binary_sha256"] == protocol[
            "solver_binary_sha256"]
        assert receipt["protocol_sha256"] == sha(HERE / "protocol.json")
        assert receipt["runtime_info_sha256"] == protocol[
            "runtime_info_sha256"]
        assert receipt["complete_n131_log2_work"] is None
        assert receipt["challenge_run_admitted"] is False
        assert receipt["cpu_isolation_receipt"] is None
        assert receipt["controlled_wall_speedup"] is None
        stdout = folder / "solver.stdout.txt"
        stderr = folder / "solver.stderr.txt"
        model = folder / "solver.model.txt"
        assert sha(stdout) == receipt["solver_stdout_sha256"]
        assert sha(stderr) == receipt["solver_stderr_sha256"]
        assert (sha(model) if model.exists() else None) == receipt[
            "solver_model_sha256"]
        report = receipt["native_report"]
        if report is not None:
            assert json.loads(stdout.read_text()) == report
            assert report["decision_policy"] == protocol["decision_policy"]
            assert report["pair_cap"] == protocol["pair_candidate_cap"]
            assert report["domain_pair_cap"] == protocol["domain_pair_cap"]
            assert report["domain_cache_cap"] == protocol["domain_cache_cap"]
            assert report["cnf_variables"] == cell["cnf_variables"]
            assert report["cnf_clauses"] == cell["cnf_clauses"]
            assert report["target_preimage_count"] == cell[
                "target_preimage_x_count"]
            assert report["field_mul_calls"] >= report[
                "domain_field_mul_calls"]
            assert report["field_sqr_calls"] >= report[
                "domain_field_sqr_calls"]
            assert report["field_inv_calls"] >= report[
                "domain_field_inv_calls"]
        if receipt["native_status"] == "sat":
            assert report is not None and report["status"] == 10
            independent = verify_model(name, model)
            assert independent == receipt["independent_model_check"]
            verified = int(independent["status"] ==
                           "verified_four_point_relation")
        else:
            assert not model.exists()
            assert receipt["independent_model_check"] is None
            verified = 0
        assert verified == receipt["verified_relation_count"]
        rows.append({
            "case": name, "status": receipt["native_status"],
            "stop_reason": None if report is None else report["stop_reason"],
            "verified_relation_count": verified,
            "domain_builds": None if report is None else report[
                "domain_builds"],
            "domain_rejections": None if report is None else report[
                "domain_rejections"],
            "domain_implications": None if report is None else report[
                "domain_implications"],
            "field_mul_calls": None if report is None else report[
                "field_mul_calls"],
            "field_sqr_calls": None if report is None else report[
                "field_sqr_calls"],
            "field_inv_calls": None if report is None else report[
                "field_inv_calls"],
            "propagations": None if report is None else report[
                "propagations"],
        })
    return {"kind": "q1479_source_bound_archive_audit",
            "status": "passed", "proposal_id": "Q1479",
            "protocol_sha256": sha(HERE / "protocol.json"),
            "domain_validation_sha256": sha(HERE / "domain_validation.json"),
            "rows": rows,
            "complete_n131_log2_work": None,
            "challenge_run_admitted": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = describe()
    if args.check:
        assert result == json.loads(RESULT.read_text())
    else:
        assert not RESULT.exists(), "refuse overwrite"
        RESULT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "passed", "cases": len(result["rows"]),
                      "verified": sum(x["verified_relation_count"] for x in
                                      result["rows"])}, sort_keys=True),
          flush=True)


if __name__ == "__main__":
    main()
