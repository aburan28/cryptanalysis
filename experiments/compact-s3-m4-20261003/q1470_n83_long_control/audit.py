#!/usr/bin/env python3
"""Check the extended N83 unpinned solver archive against its frozen inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from q1438_dense_base.verify_solver import model_relation  # noqa: E402
from q1467_density_bridge.build_inputs import make_case  # noqa: E402

Q1467 = PARENT / "q1467_density_bridge"
OUT = HERE / "run"
RESULT = HERE / "archive_audit.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def describe() -> dict:
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    receipt_path = OUT / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    assert protocol["proposal_id"] == receipt["proposal_id"] == "Q1470"
    assert protocol["candidate_id"] is receipt["candidate_id"] is None
    assert protocol["isogeny"] == receipt["isogeny"] == "none"
    assert receipt["protocol_sha256"] == sha(protocol_path)
    assert receipt["runner_source_sha256"] == protocol["source_sha256"][
        "experiments/compact-s3-m4-20261003/q1470_n83_long_control/run.py"]
    assert receipt["runtime_info_sha256"] == protocol[
        "sage_runtime_info_sha256"]
    assert receipt["curve_id"] == protocol["curve_id"]
    assert receipt["workload_id"] == protocol["workload_id"]
    assert receipt["public_target"] == protocol["public_target"]
    assert receipt["factor_base_actual_B"] == protocol[
        "factor_base_actual_B"]
    assert receipt["folded_columns_K"] == protocol["folded_columns_K"]
    assert receipt["factor_base_enumerated_set_sha256"] == protocol[
        "factor_base_enumerated_set_sha256"]
    assert receipt["known_satisfiable_control"] is True
    assert receipt["solver_stdout_sha256"] == sha(OUT / "solver.stdout.txt")
    assert receipt["solver_stderr_sha256"] == sha(OUT / "solver.stderr.txt")
    assert receipt["solver_model_sha256"] == (
        sha(OUT / "solver.model.txt") if (OUT / "solver.model.txt").exists()
        else None)
    assert receipt["native_report_error"] is None
    report = json.loads((OUT / "solver.stdout.txt").read_text())
    assert report == receipt["native_report"]
    assert report["cnf_variables"] == protocol["cnf_variables"]
    assert report["cnf_clauses"] == protocol["cnf_clauses"]
    assert report["pair_cap"] == protocol["pair_candidate_cap"]
    assert report["decision_policy"] == protocol["decision_policy"]
    assert report["target_preimage_count"] == 1
    assert report["batch_root_inputs"] == sum(report["root_cache_misses"])
    for lane, logical in enumerate((report["joint_pair0_root_calls"],
                                    report["joint_pair1_root_calls"],
                                    report["joint_final_root_calls"])):
        assert logical == (report["root_cache_hits"][lane] +
                           report["root_cache_misses"][lane] +
                           report["root_batch_reuses"][lane])
    status = receipt["native_status"]
    assert status in ("sat", "censored"), status
    assert receipt["native_exit_code"] == (0 if status == "sat" else 10)
    assert report["status"] == (10 if status == "sat" else 0)
    assert receipt["solver_process_wall_ns_exploratory"] > 0
    assert receipt["input_materialization_wall_ns_exploratory"] > 0
    assert receipt["complete_n131_log2_work"] is None
    assert receipt["challenge_run_admitted"] is False
    if status == "sat":
        assert receipt["verified_relation_count"] == 1
        assert receipt["independent_model_check_error"] is None
        regenerated, varmap, targets, meta, variables, clauses, formula = (
            make_case("n83_planted_unpinned"))
        assert hashlib.sha256(regenerated).hexdigest() == protocol[
            "cnf_sha256"]
        assert varmap == (Q1467 /
            "inputs/n83_planted_unpinned/variables.txt").read_bytes()
        assert targets == (Q1467 /
            "inputs/n83_planted_unpinned/targets.txt").read_bytes()
        instance = dict(json.loads((PARENT /
            "q1438_dense_base/solver_protocol.json").read_text())[
                "instances"]["83"])
        instance["new_weight_bound"] = meta["normal_basis_weight_bound"]
        relation = model_relation(
            regenerated, formula, meta, variables, len(clauses),
            OUT / "solver.model.txt", instance)
        assert relation == receipt["independent_model_check"]
        assert relation["status"] == "verified_four_point_relation"
    else:
        assert receipt["verified_relation_count"] == 0
        assert receipt["independent_model_check"] is None
        assert report["stop_reason"] in ("wall_cap", "conflict_cap")
    prior = json.loads((Q1467 /
        "runs/n83_planted_unpinned/receipt.json").read_text())
    assert prior["solver_status"] == "censored"
    assert prior["workload_id"] == receipt["workload_id"]
    assert prior["cnf_sha256"] == protocol["cnf_sha256"]
    prior_report = prior["solver_report"]
    assert prior_report["stop_reason"] == "wall_cap"
    assert prior_report["conflicts"] < report["conflicts"]
    prior_field_calls = {
        "mul": prior_report["field_mul_calls"],
        "sqr": prior_report["field_sqr_calls"],
        "inv": prior_report["field_inv_calls"],
        "s3_roots": prior_report["field_s3_root_calls"],
    }
    field_calls = {
        "mul": report["field_mul_calls"],
        "sqr": report["field_sqr_calls"],
        "inv": report["field_inv_calls"],
        "s3_roots": report["field_s3_root_calls"],
    }
    return {
        "kind": "q1470_n83_extended_control_archive_audit",
        "status": "passed", "proposal_id": "Q1470",
        "candidate_id": None, "isogeny": "none",
        "curve_id": protocol["curve_id"],
        "workload_id": protocol["workload_id"],
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "folded_columns_K": protocol["folded_columns_K"],
        "factor_base_enumerated_set_sha256": protocol[
            "factor_base_enumerated_set_sha256"],
        "solver_status": status,
        "stop_reason": report["stop_reason"],
        "verified_relation_count": receipt["verified_relation_count"],
        "conflicts": report["conflicts"],
        "decisions": report["decisions"],
        "joint_eligible_checks": report["joint_eligible_checks"],
        "joint_partial_events": report["joint_partial_events"],
        "joint_cap_skips": report["joint_cap_skips"],
        "field_calls": field_calls,
        "field_calls_equal_prior_60_second_run": (
            field_calls == prior_field_calls),
        "prior_60_second_conflicts": prior_report["conflicts"],
        "prior_60_second_field_calls": prior_field_calls,
        "prior_60_second_solver_process_wall_ns_exploratory": prior[
            "solver_process_wall_ns_exploratory"],
        "prior_60_second_peak_child_rss_raw": prior["peak_child_rss_raw"],
        "input_materialization_wall_ns_exploratory": receipt[
            "input_materialization_wall_ns_exploratory"],
        "solver_process_wall_ns_exploratory": receipt[
            "solver_process_wall_ns_exploratory"],
        "relation_check_wall_ns_exploratory": receipt[
            "relation_check_wall_ns_exploratory"],
        "peak_child_rss_raw": receipt["peak_child_rss_raw"],
        "peak_child_rss_units": receipt["peak_child_rss_units"],
        "is_natural_yield_estimate": False,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "protocol_sha256": sha(protocol_path),
        "receipt_sha256": sha(receipt_path),
        "auditor_source_sha256": sha(Path(__file__)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert args.emit != args.check
    result = describe()
    if args.emit:
        assert not RESULT.exists(), "refuse overwrite"
        RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) +
                          "\n")
    else:
        assert result == json.loads(RESULT.read_text())
    print(json.dumps({"status": result["status"],
                      "solver_status": result["solver_status"],
                      "verified_relations": result["verified_relation_count"]}))


if __name__ == "__main__":
    main()
