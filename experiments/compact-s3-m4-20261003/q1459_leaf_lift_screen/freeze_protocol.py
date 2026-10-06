#!/usr/bin/env python3
"""Freeze exact lift-filtered sparse-domain admission diagnostics."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1456 = PARENT / "q1456_joint_domain_profile"
Q1458 = PARENT / "q1458_batch_roots"
OUTPUT = HERE / "protocol.json"
RUN_ORDER = ("n53_known_sat_unpinned", "n53_ordinary", "n83_ordinary")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make_protocol() -> dict:
    parent = json.loads((Q1456 / "protocol.json").read_text())
    verification = json.loads((Q1456 / "verification.json").read_text())
    baseline = json.loads((Q1458 / "protocol.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert parent["proposal_id"] == verification["proposal_id"] == "Q1456"
    assert verification["status"] == "pass"
    assert verification["protocol_sha256"] == sha(Q1456 / "protocol.json")
    assert baseline["proposal_id"] == "Q1458"
    assert parent["run_order"] == baseline["run_order"] == list(RUN_ORDER)
    assert runtime["status"] == "verified"
    cells = {}
    for name in RUN_ORDER:
        prior = parent["cells"][name]
        measured = baseline["cells"][name]
        for key in ("degree_n", "input_role", "curve_id",
                    "factor_base_actual_B", "folded_columns_K",
                    "factor_base_enumerated_set_sha256",
                    "normal_basis_weight_bound", "public_target",
                    "workload_id", "cnf_sha256"):
            assert prior[key] == measured[key], (name, key)
        cells[name] = {
            key: prior[key] for key in (
                "degree_n", "input_role", "curve_id",
                "factor_base_actual_B", "folded_columns_K",
                "factor_base_enumerated_set_sha256",
                "normal_basis_weight_bound", "public_target",
                "workload_id", "cnf_sha256")}
        cells[name]["parent_receipt_sha256"] = sha(Q1456 / "runs" /
                                                    name / "receipt.json")
    source_paths = [HERE / name for name in (
        "freeze_protocol.py", "screen_lift.py")]
    source_paths += [PARENT / name for name in (
        "chain_s3.py", "q1455_joint_tail/joint_tail.py",
        "q1422_leaf_lift_gate/lift_gate.hpp")]
    source_paths.append(ROOT / "ecc2k130/codegen/field.py")
    input_paths = [HERE / "sage_runtime_info.json",
                   Q1456 / "protocol.json",
                   Q1456 / "verification.json",
                   Q1458 / "protocol.json",
                   Q1458 / "verification.json",
                   PARENT / "q1422_leaf_lift_gate/n53_lift_validation.json",
                   PARENT / "q1422_leaf_lift_gate/n83_lift_validation.json"]
    input_paths += [Q1456 / "runs" / name / "receipt.json"
                    for name in RUN_ORDER]
    return {
        "kind": "q1459_lift_filtered_domain_screen_protocol",
        "proposal_id": "Q1459", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "method": (
            "on each archived Q1456 partial four-leaf state, enumerate "
            "each sparse leaf domain only when every domain has at most "
            "4096 options; retain exactly the x values that lift to "
            "y^2+xy=x^3+1 by Tr(x+x^-1)=0; recount pair products and "
            "compare cap admission without evaluating pair S3 roots"),
        "controlled_variable": (
            "exact single-leaf curve-lift filtering before the Q1458 "
            "4096 pair-product eligibility check"),
        "leaf_option_cap": 4096,
        "pair_candidate_cap": 4096,
        "run_order": list(RUN_ORDER), "cells": cells,
        "parent_q1456_protocol_sha256": sha(Q1456 / "protocol.json"),
        "baseline_q1458_protocol_sha256": sha(Q1458 / "protocol.json"),
        "source_sha256": {str(path.relative_to(ROOT)): sha(path)
                          for path in source_paths},
        "input_sha256": {str(path.relative_to(ROOT)): sha(path)
                         for path in input_paths},
        "cpu_isolation_receipt": None,
        "successful_decomposition_cost": None,
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = make_protocol()
    if args.check:
        assert result == json.loads(OUTPUT.read_text())
        print("Q1459 frozen lift-filtered domain screen: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1459",
                          "run_order": result["run_order"]}))


if __name__ == "__main__":
    main()
