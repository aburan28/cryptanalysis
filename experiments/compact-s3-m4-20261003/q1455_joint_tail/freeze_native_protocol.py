#!/usr/bin/env python3
"""Freeze Q1455 native controls and ordinary cells before measurement."""

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

from q1423_target_coupled.target_inputs import target_source  # noqa: E402
from q1455_joint_tail.native_inputs import CASES, make_case  # noqa: E402
from q1455_joint_tail.run_controls import partial_witness  # noqa: E402

OUTPUT = HERE / "native_protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def workload_id(record: dict) -> str:
    payload = json.dumps(record, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def make_protocol() -> dict:
    parent_control = json.loads((HERE / "protocol.json").read_text())
    control_result = json.loads((HERE / "controls.json").read_text())
    assert parent_control["proposal_id"] == control_result[
        "proposal_id"] == "Q1455"
    assert control_result["status"] == "pass"
    assert control_result["protocol_sha256"] == sha(HERE / "protocol.json")
    build_receipt = json.loads((HERE / "native_compile_receipt.json").read_text())
    assert build_receipt["proposal_id"] == "Q1455"
    assert build_receipt["binary_sha256"] == sha(HERE / "native_joint_solver")
    parent = json.loads((PARENT /
        "q1438_dense_base/solver_protocol.json").read_text())
    cells = {}
    for name in CASES:
        n = 53 if "n53" in name else 83
        raw, varmap, targets, _, meta, variables, clauses = make_case(name)
        role = ("partial_witness_control" if "partial_control" in name
                else "known_satisfiable_selected_preimage" if
                name == "n53_known_sat_unpinned" else
                "ordinary_full_target")
        selected = 201 if n == 53 and role != "ordinary_full_target" else (
            3 if name == "n83_partial_control" else None)
        pinned_masks = pinned_ones = None
        if role == "partial_witness_control":
            witness = parent_control["archived_controls"][str(n)][
                "archived_group_verified_leaf_x"]
            partial = partial_witness(witness, n)
            pinned_masks = [state.fixed_mask for state in partial]
            pinned_ones = [state.fixed_ones for state in partial]
        record = {
            "curve_id": meta["curve_id"],
            "subgroup_order": parent["instances"][str(n)]["subgroup_order"],
            "public_target": meta["public_target"],
            "factor_base_enumerated_set_sha256": meta[
                "factor_base_enumerated_set_sha256"],
            "target_count": 1,
            "target_input_role": role,
            "selected_target_preimage_index": selected,
            "leaf_fixed_masks": pinned_masks,
            "leaf_fixed_ones": pinned_ones,
            "input_seed": "deterministic_archived",
            "target_cache": "empty",
        }
        cells[name] = {
            "degree_n": n, "input_role": role,
            "curve_id": meta["curve_id"],
            "factor_base_actual_B": meta["factor_base_actual_B"],
            "folded_columns_K": meta["folded_columns_K"],
            "factor_base_enumerated_set_sha256": meta[
                "factor_base_enumerated_set_sha256"],
            "normal_basis_weight_bound": meta[
                "normal_basis_weight_bound"],
            "public_target": meta["public_target"],
            "selected_target_preimage_index": selected,
            "workload_record": record,
            "workload_id": workload_id(record),
            "cnf_sha256": hashlib.sha256(raw).hexdigest(),
            "cnf_bytes": len(raw),
            "cnf_variables": variables,
            "cnf_clauses": clauses,
            "variable_map_sha256": hashlib.sha256(varmap).hexdigest(),
            "targets_sha256": hashlib.sha256(targets).hexdigest(),
            "target_preimage_count": meta["target_preimage_x_count"],
            "pair_candidate_cap": 256 if n == 53 else 1024,
            "solver_conflict_cap": 1000000,
            "solver_wall_cap_seconds": (30 if role ==
                                        "partial_witness_control" else 60),
            "external_process_safeguard_seconds": (40 if role ==
                                                    "partial_witness_control"
                                                    else 75),
        }
    source_paths = [HERE / name for name in (
        "joint_tail.py", "run_controls.py", "native_inputs.py",
        "native_joint_solver.cpp", "build_native.py", "smoke_native.py",
        "run_native_stage.py", "verify_native_stage.py",
        "freeze_native_protocol.py")]
    source_paths += [PARENT / name for name in (
        "q1446_joint_pair_span/theory_solver.cpp",
        "q1438_dense_base/build_formula.py",
        "q1438_dense_base/verify_solver.py",
        "q1423_target_coupled/target_inputs.py",
        "q1420_root_theory/root_field.hpp",
        "s3_root_oracle.py", "chain_s3.py")]
    input_paths = [HERE / name for name in (
        "protocol.json", "controls.json", "sage_runtime_info.json",
        "native_compile_receipt.json")]
    input_paths += [PARENT / name for name in (
        "q1438_dense_base/protocol.json",
        "q1438_dense_base/solver_protocol.json",
        "q1438_dense_base/n53_w4_base.json",
        "q1438_dense_base/n83_w6_base.json",
        "q1419_partial_pin/protocol.json",
        "q1436_affine_pair/protocol.json",
        "q1420_root_theory/protocol.json",
        "q1420_root_theory/n53_field.txt",
        "q1420_root_theory/n83_field.txt",
        "q1452_known_satisfiable_phi5/controls.json",
        "q1446_joint_pair_span/validation.json",
        "runs/n53_q1410_ordinary.json", "runs/n83_q1408_ordinary.json")]
    for n in (53, 83):
        input_paths.append(target_source(n, "free_mids"))
    return {
        "kind": "q1455_native_joint_tail_protocol",
        "proposal_id": "Q1455", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "decision_policy": "joint_tail_leaf_interleave",
        "method": (
            "interleave decisions across four sparse leaves before either "
            "pair midpoint; when both pair completion products fit their "
            "cap, join all exact S3 pair-output sets through the selected "
            "target and reject a partial state only when no chain exists"),
        "controlled_variable": (
            "Q1455 exact unfixed-midpoint joint feasibility rule versus "
            "Q1446 fixed-midpoint span rule and Q1454 phi5 SAT stage"),
        "run_order": list(CASES), "cells": cells,
        "parent_control_protocol_sha256": sha(HERE / "protocol.json"),
        "parent_control_result_sha256": sha(HERE / "controls.json"),
        "native_compile_receipt_sha256": sha(
            HERE / "native_compile_receipt.json"),
        "native_binary_sha256": sha(HERE / "native_joint_solver"),
        "source_sha256": {str(path.relative_to(ROOT)): sha(path)
                          for path in source_paths},
        "input_sha256": {str(path.relative_to(ROOT)): sha(path)
                         for path in input_paths},
        "cpu_isolation_receipt": None,
        "natural_relation_yield_estimate": None,
        "cost_per_useful_row": None,
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
        print("Q1455 frozen native joint-tail protocol: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1455",
                          "run_order": result["run_order"]}))


if __name__ == "__main__":
    main()
