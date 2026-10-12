#!/usr/bin/env python3
"""Freeze Q1446 exact-base joint-pair inputs before ordinary queries."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1438 = PARENT / "q1438_dense_base"
PROTOCOL = HERE / "protocol.json"

SOURCE_PATHS = [
    "experiments/compact-s3-m4-20261003/q1446_joint_pair_span/"
    "theory_solver.cpp",
    "experiments/compact-s3-m4-20261003/q1446_joint_pair_span/"
    "build_solver.py",
    "experiments/compact-s3-m4-20261003/q1446_joint_pair_span/"
    "validate_controls.py",
    "experiments/compact-s3-m4-20261003/q1446_joint_pair_span/"
    "freeze_protocol.py",
    "experiments/compact-s3-m4-20261003/q1446_joint_pair_span/"
    "run_stage.py",
    "experiments/compact-s3-m4-20261003/q1446_joint_pair_span/"
    "verify_archive.py",
    "experiments/compact-s3-m4-20261003/q1438_dense_base/"
    "build_formula.py",
    "experiments/compact-s3-m4-20261003/q1438_dense_base/"
    "verify_solver.py",
    "experiments/compact-s3-m4-20261003/q1432_coefficient_cache/"
    "cached_span.hpp",
    "experiments/compact-s3-m4-20261003/q1431_guarded_span/"
    "span_filter.hpp",
    "experiments/compact-s3-m4-20261003/q1428_bilinear_span/"
    "screen.py",
    "experiments/compact-s3-m4-20261003/q1423_target_coupled/"
    "target_inputs.py",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/"
    "root_field.hpp",
    "experiments/compact-s3-m4-20261003/q1422_leaf_lift_gate/"
    "lift_gate.hpp",
    "experiments/compact-s3-m4-20261003/chain_s3.py",
]
INPUT_PATHS = [
    "experiments/compact-s3-m4-20261003/q1438_dense_base/"
    "solver_protocol.json",
    "experiments/compact-s3-m4-20261003/q1438_dense_base/"
    "protocol.json",
    "experiments/compact-s3-m4-20261003/q1438_dense_base/"
    "n53_w4_base.json",
    "experiments/compact-s3-m4-20261003/q1438_dense_base/"
    "n83_w6_base.json",
    "experiments/compact-s3-m4-20261003/q1432_coefficient_cache/"
    "cache_validation.json",
    "experiments/compact-s3-m4-20261003/q1446_joint_pair_span/"
    "compile_receipt.json",
    "experiments/compact-s3-m4-20261003/q1446_joint_pair_span/"
    "validation.json",
    "experiments/compact-s3-m4-20261003/q1446_joint_pair_span/"
    "sage_runtime_info.json",
]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def produce():
    parent = json.loads((Q1438 / "solver_protocol.json").read_text())
    validation = json.loads((HERE / "validation.json").read_text())
    compile_receipt = json.loads((HERE / "compile_receipt.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert parent["proposal_id"] == "Q1438"
    assert validation["proposal_id"] == "Q1446"
    assert validation["status"] == "pass"
    assert validation["partial_n53_control"]["span_checks_pair0"] > 0
    assert validation["partial_n53_control"]["span_checks_pair1"] > 0
    assert runtime["status"] == "verified"
    binary_sha = sha(HERE / "theory_solver")
    assert compile_receipt["binary_sha256"] == binary_sha
    assert validation["solver_binary_sha256"] == binary_sha
    assert validation["solver_source_sha256"] == sha(
        HERE / "theory_solver.cpp")
    cells = {}
    for n in (53, 83):
        old = parent["workloads"][f"n{n}_ordinary"]
        instance = parent["instances"][str(n)]
        base_path = Q1438 / f"n{n}_w{instance['new_weight_bound']}_base.json"
        base = json.loads(base_path.read_text())
        assert base["curve_id"] == old["curve_id"] == instance["curve_id"]
        assert base["actual_usable_points_B_before_folding"] == old[
            "factor_base_actual_B"]
        assert base["signed_frobenius_columns_K"] == old[
            "folded_columns_K"]
        assert base["enumerated_set_sha256"] == old[
            "factor_base_enumerated_set_sha256"]
        assert sha(base_path) == old["factor_base_receipt_sha256"]
        workload = {
            "curve_id": old["curve_id"],
            "subgroup_order": instance["subgroup_order"],
            "public_target": old["public_target"],
            "target_count": 1,
            "target_input_law": "one archived ordinary public subgroup point",
            "factor_base_actual_B": old["factor_base_actual_B"],
            "folded_columns_K": old["folded_columns_K"],
            "factor_base_enumerated_set_sha256": old[
                "factor_base_enumerated_set_sha256"],
            "weight_bound": instance["new_weight_bound"],
            "target_preimage_x_count": old["target_preimage_x_count"],
            "solver_policy": "joint_pair_span",
            "solver_conflict_cap": 1_000_000,
            "solver_wall_cap_seconds": 60,
            "external_process_safeguard_seconds": 75,
            "cold_or_warm": "one target; no target-dependent cache reused",
        }
        cells[str(n)] = {
            "curve_id": old["curve_id"],
            "cofactor": instance["cofactor"],
            "subgroup_order": instance["subgroup_order"],
            "field": instance["field"],
            "curve": instance["curve"],
            "factor_base_actual_B": old["factor_base_actual_B"],
            "folded_columns_K": old["folded_columns_K"],
            "factor_base_enumerated_set_sha256": old[
                "factor_base_enumerated_set_sha256"],
            "factor_base_receipt_sha256": sha(base_path),
            "weight_bound": instance["new_weight_bound"],
            "public_target": old["public_target"],
            "target_preimage_x_count": old["target_preimage_x_count"],
            "cnf_raw_sha256": old["cnf_raw_sha256"],
            "cnf_raw_bytes": old["cnf_raw_bytes"],
            "cnf_variables": old["cnf_variables"],
            "cnf_clauses": old["cnf_clauses"],
            "variable_map_sha256": old["variable_map_sha256"],
            "target_input_sha256": old["target_input_sha256"],
            "matched_q1438_workload_id": old["workload_id"],
            "solver_conflict_cap": 1_000_000,
            "solver_wall_cap_seconds": 60,
            "external_process_safeguard_seconds": 75,
            "workload": workload,
            "workload_id": hashlib.sha256(canonical_json(workload)).hexdigest()[
                :12],
        }
    return {
        "proposal_id": "Q1446", "candidate_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "method": (
            "compact chained S3; target-linked mids before leaves; all "
            "four leaves interleaved; cached sound sparse-pair span on both pairs"),
        "policy": "joint_pair_span",
        "run_order": ["n53_ordinary", "n83_ordinary"],
        "cells": cells,
        "source_sha256": {name: sha(ROOT / name) for name in SOURCE_PATHS},
        "input_sha256": {name: sha(ROOT / name) for name in INPUT_PATHS},
        "solver_binary_sha256": binary_sha,
        "compile_receipt_sha256": sha(HERE / "compile_receipt.json"),
        "validation_sha256": sha(HERE / "validation.json"),
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "parent_q1438_solver_protocol_sha256": sha(
            Q1438 / "solver_protocol.json"),
        "cpu_isolation_receipt": None,
        "natural_relation_yield_estimate": None,
        "cost_per_useful_row": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = produce()
    if args.check:
        assert json.loads(PROTOCOL.read_text()) == expected
        print("Q1446 frozen protocol: PASS")
    else:
        assert not PROTOCOL.exists(), "refuse overwrite"
        PROTOCOL.write_text(json.dumps(expected, sort_keys=True, indent=2) +
                            "\n")
        print(json.dumps({"proposal_id": "Q1446",
                          "workloads": {n: c["workload_id"]
                                        for n, c in expected["cells"].items()},
                          "protocol_sha256": sha(PROTOCOL)}, sort_keys=True))
