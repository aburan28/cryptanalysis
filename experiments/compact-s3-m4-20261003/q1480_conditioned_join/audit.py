#!/usr/bin/env python3
"""Audit Q1480 source custody, exact inputs, and public-point results."""

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

from q1480_conditioned_join.freeze_protocol import render  # noqa: E402
from q1480_conditioned_join.run_stage import verify_relation  # noqa: E402
from q1480_conditioned_join.validate_conditioned import (  # noqa: E402
    describe as validate_conditioned,
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
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert json.loads((HERE / "conditioned_validation.json").read_text()) == (
        validate_conditioned())
    rows = []
    for name in protocol["run_order"]:
        cell = protocol["cases"][name]
        input_dir = ROOT / cell["input_dir"]
        for leaf, digest in cell["input_sha256"].items():
            assert sha(input_dir / leaf) == digest
        raw = gzip.decompress((input_dir / "system.cnf.gz").read_bytes())
        assert hashlib.sha256(raw).hexdigest() == cell[
            "cnf_raw_sha256"]
        parent_receipt = (
            PARENT / "q1476_trace_syndrome/runs" / cell["source_case"] /
            "receipt.json" if cell["input_source"] == "Q1476" else
            input_dir / "receipt.json")
        assert sha(parent_receipt) == cell["parent_receipt_sha256"]
        folder = HERE / "runs" / name
        receipt = json.loads((folder / "receipt.json").read_text())
        assert receipt["proposal_id"] == "Q1480"
        assert receipt["candidate_id"] is receipt["run_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["stage_config_id"] == cell["stage_config_id"]
        assert receipt["stage_run_id"] == cell["stage_run_id"]
        assert receipt["curve_id"] == cell["curve_id"]
        assert receipt["workload_id"] == cell["workload_id"]
        assert receipt["factor_base_actual_B"] == cell[
            "factor_base_actual_B"]
        assert receipt["folded_columns_K"] == cell["folded_columns_K"]
        assert receipt["factor_base_enumerated_set_sha256"] == cell[
            "factor_base_enumerated_set_sha256"]
        assert receipt["input_sha256"] == cell["input_sha256"]
        assert receipt["cnf_raw_sha256"] == cell["cnf_raw_sha256"]
        assert receipt["parent_receipt_sha256"] == cell[
            "parent_receipt_sha256"]
        assert receipt["solver_binary_sha256"] == protocol[
            "solver_binary_sha256"]
        assert receipt["protocol_sha256"] == sha(HERE / "protocol.json")
        assert receipt["runtime_info_sha256"] == protocol[
            "runtime_info_sha256"]
        assert receipt["runner_source_sha256"] == sha(HERE /
                                                    "run_stage.py")
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
                "joint_field_mul_calls"]
            assert report["field_sqr_calls"] >= report[
                "joint_field_sqr_calls"]
            assert report["field_inv_calls"] >= report[
                "joint_field_inv_calls"]
        if receipt["native_status"] == "sat":
            assert report is not None and report["status"] == 10
            independent = verify_relation(cell, raw, model)
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
            "input_source": cell["input_source"],
            "curve_id": cell["curve_id"],
            "workload_id": cell["workload_id"],
            "factor_base_actual_B": cell["factor_base_actual_B"],
            "folded_columns_K": cell["folded_columns_K"],
            "verified_relation_count": verified,
            "stop_reason": None if report is None else report["stop_reason"],
            "conditioned_eligible_checks": None if report is None else report[
                "joint_eligible_checks"],
            "conditioned_rejections": None if report is None else report[
                "joint_no_chain_rejections"],
            "conditioned_left_s3_evals": None if report is None else report[
                "conditioned_left_s3_evals"],
            "conditioned_right_s3_evals": None if report is None else report[
                "conditioned_right_s3_evals"],
            "domain_builds": None if report is None else report[
                "domain_builds"],
            "field_mul_calls": None if report is None else report[
                "field_mul_calls"],
            "field_sqr_calls": None if report is None else report[
                "field_sqr_calls"],
            "field_inv_calls": None if report is None else report[
                "field_inv_calls"],
            "propagations": None if report is None else report[
                "propagations"],
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "solver_process_wall_ns_exploratory": receipt[
                "solver_process_wall_ns_exploratory"],
        })
    controls = rows[:2]
    return {
        "kind": "q1480_source_bound_archive_audit",
        "status": "passed", "proposal_id": "Q1480",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "protocol_sha256": sha(HERE / "protocol.json"),
        "conditioned_validation_sha256": sha(HERE /
                                             "conditioned_validation.json"),
        "pinned_correctness_controls_passed": all(
            row["status"] == "sat" and row["verified_relation_count"] == 1
            for row in controls),
        "rows": rows,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


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
                                      result["rows"]),
                      "pinned_controls": result[
                          "pinned_correctness_controls_passed"]},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
