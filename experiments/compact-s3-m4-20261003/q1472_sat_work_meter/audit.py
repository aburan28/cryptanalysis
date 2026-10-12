#!/usr/bin/env python3
"""Audit exact CaDiCaL propagations and all matched four-point controls."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))

from q1438_dense_base.verify_solver import model_relation  # noqa: E402
from q1467_density_bridge.build_inputs import make_case  # noqa: E402

Q1467 = PARENT / "q1467_density_bridge"
RESULT = HERE / "archive_audit.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_instrumentation_only() -> None:
    parent = (PARENT / "q1466_leaf_rotation/native_solver.cpp").read_text()
    expected = parent.replace(
        "// Q1466: diversify normal-basis coordinates of the four leaf decisions.",
        "// Q1472: Q1466 solver with exact CaDiCaL propagation accounting.", 1)
    expected = expected.replace(
        '        int64_t decisions = solver.get_statistic_value("decisions");\n',
        '        int64_t decisions = solver.get_statistic_value("decisions");\n'
        '        int64_t propagations = '
        'solver.get_statistic_value("propagations");\n'
        '        require(propagations >= 0,\n'
        '                "CaDiCaL propagations statistic unavailable");\n', 1)
    expected = expected.replace(
        '                  << ",\\\"decisions\\\":" << decisions\n',
        '                  << ",\\\"decisions\\\":" << decisions\n'
        '                  << ",\\\"propagations\\\":" << propagations\n', 1)
    assert expected == (HERE / "native_solver.cpp").read_text()


def describe() -> dict:
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q1472"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert protocol["run_order"] == [
        "n53_planted", "n83_planted", "n53_planted_unpinned",
        "n83_planted_unpinned", "n53_ordinary", "n83_ordinary"]
    check_instrumentation_only()
    assert sha(Q1467 / "solver_protocol.json") == protocol[
        "q1467_protocol_sha256"]
    assert sha(PARENT / "q1466_leaf_rotation/native_solver.cpp") == (
        protocol["q1466_source_sha256"])
    assert sha(HERE / "native_solver") == protocol["q1472_binary_sha256"]
    assert sha(HERE / "compile_receipt.json") == protocol[
        "q1472_compile_receipt_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "sage_runtime_info_sha256"]
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    rows = []
    for name in protocol["run_order"]:
        cell = protocol["cells"][name]
        output = HERE / "runs" / name
        input_dir = Q1467 / "inputs" / name
        for leaf, digest in cell["input_sha256"].items():
            assert sha(input_dir / leaf) == digest, (name, leaf)
        receipt_path = output / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["proposal_id"] == "Q1472"
        assert receipt["candidate_id"] is None
        assert receipt["run_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["case"] == name
        for key in ("curve_id", "degree_n", "factor_base_actual_B",
                    "folded_columns_K", "factor_base_enumerated_set_sha256",
                    "workload_id", "public_target", "input_role",
                    "leaves_pinned", "cnf_sha256"):
            assert receipt[key] == cell[key], (name, key)
        assert receipt["protocol_sha256"] == sha(protocol_path)
        assert receipt["runner_source_sha256"] == protocol[
            "source_sha256"]["experiments/compact-s3-m4-20261003/"
                             "q1472_sat_work_meter/run.py"]
        assert receipt["runtime_info_sha256"] == protocol[
            "sage_runtime_info_sha256"]
        assert receipt["solver_stdout_sha256"] == sha(
            output / "solver.stdout.txt")
        assert receipt["solver_stderr_sha256"] == sha(
            output / "solver.stderr.txt")
        assert receipt["solver_model_sha256"] == (
            sha(output / "solver.model.txt")
            if (output / "solver.model.txt").exists() else None)
        assert receipt["native_report_error"] is None
        report = json.loads((output / "solver.stdout.txt").read_text())
        assert report == receipt["native_report"]
        assert report["cnf_variables"] == cell["cnf_variables"]
        assert report["cnf_clauses"] == cell["cnf_clauses"]
        assert report["decision_policy"] == protocol["decision_policy"]
        assert report["pair_cap"] == protocol["pair_candidate_cap"]
        assert report["propagations"] >= 0
        assert report["conflicts"] >= 0
        assert report["decisions"] >= 0
        assert report["batch_root_inputs"] == sum(
            report["root_cache_misses"])
        for lane, logical in enumerate((report["joint_pair0_root_calls"],
                                        report["joint_pair1_root_calls"],
                                        report["joint_final_root_calls"])):
            assert logical == (report["root_cache_hits"][lane] +
                               report["root_cache_misses"][lane] +
                               report["root_batch_reuses"][lane])
        status = receipt["native_status"]
        assert status in ("sat", "censored"), (name, status)
        assert receipt["native_exit_code"] == (0 if status == "sat" else 10)
        assert report["status"] == (10 if status == "sat" else 0)
        if status == "sat":
            assert receipt["verified_relation_count"] == 1
            assert receipt["independent_model_check_error"] is None
            regenerated, varmap, targets, meta, variables, clauses, formula = (
                make_case(name))
            assert hashlib.sha256(regenerated).hexdigest() == cell[
                "cnf_sha256"]
            assert varmap == (input_dir / "variables.txt").read_bytes()
            assert targets == (input_dir / "targets.txt").read_bytes()
            instance = dict(json.loads((PARENT /
                "q1438_dense_base/solver_protocol.json").read_text())[
                    "instances"][str(cell["degree_n"])])
            instance["new_weight_bound"] = meta["normal_basis_weight_bound"]
            relation = model_relation(
                regenerated, formula, meta, variables, len(clauses),
                output / "solver.model.txt", instance)
            assert relation == receipt["independent_model_check"]
            assert relation["status"] == "verified_four_point_relation"
        else:
            assert receipt["verified_relation_count"] == 0
            assert receipt["independent_model_check"] is None
            assert report["stop_reason"] in ("wall_cap", "conflict_cap")
        assert receipt["complete_n131_log2_work"] is None
        assert receipt["challenge_run_admitted"] is False
        prior_path = Q1467 / "runs" / name / "receipt.json"
        prior = json.loads(prior_path.read_text())
        assert sha(prior_path) == cell["prior_receipt_sha256"]
        for key in ("curve_id", "factor_base_actual_B",
                    "folded_columns_K", "factor_base_enumerated_set_sha256",
                    "workload_id", "public_target", "cnf_sha256"):
            assert prior[key] == receipt[key], (name, key)
        assert prior["solver_status"] == status
        assert prior["verified_relation_count"] == receipt[
            "verified_relation_count"]
        rows.append({
            "case": name, "degree_n": cell["degree_n"],
            "input_role": cell["input_role"],
            "leaves_pinned": cell["leaves_pinned"],
            "curve_id": cell["curve_id"],
            "factor_base_actual_B": cell["factor_base_actual_B"],
            "folded_columns_K": cell["folded_columns_K"],
            "factor_base_enumerated_set_sha256": cell[
                "factor_base_enumerated_set_sha256"],
            "workload_id": cell["workload_id"],
            "public_target": cell["public_target"],
            "native_status": status,
            "stop_reason": report["stop_reason"],
            "verified_relation_count": receipt["verified_relation_count"],
            "sat_work": {
                "propagations": report["propagations"],
                "conflicts": report["conflicts"],
                "decisions": report["decisions"],
            },
            "field_calls": {
                "mul": report["field_mul_calls"],
                "sqr": report["field_sqr_calls"],
                "inv": report["field_inv_calls"],
                "s3_roots": report["field_s3_root_calls"],
            },
            "joint_eligible_checks": report["joint_eligible_checks"],
            "joint_cap_skips": report["joint_cap_skips"],
            "input_materialization_wall_ns_exploratory": receipt[
                "input_materialization_wall_ns_exploratory"],
            "solver_process_wall_ns_exploratory": receipt[
                "solver_process_wall_ns_exploratory"],
            "relation_check_wall_ns_exploratory": receipt[
                "relation_check_wall_ns_exploratory"],
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "peak_child_rss_units": receipt["peak_child_rss_units"],
            "prior_receipt_sha256": sha(prior_path),
            "receipt_sha256": sha(receipt_path),
        })
    assert len(rows) == 6
    return {
        "kind": "q1472_exact_sat_work_meter_archive_audit",
        "status": "passed", "proposal_id": "Q1472",
        "candidate_id": None, "isogeny": "none",
        "controlled_variable": protocol["controlled_variable"],
        "rows": rows,
        "measurement_units": protocol["measurement_units"],
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "protocol_sha256": sha(protocol_path),
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
                      "cases": [(row["case"], row["native_status"],
                                 row["sat_work"]["propagations"])
                                for row in result["rows"]]}))


if __name__ == "__main__":
    main()
