#!/usr/bin/env python3
"""Freeze inverse-free phi5 N53/N83 ordinary queries before execution."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))

from q1453_projective_phi5.build_formula import build  # noqa: E402
from q1449_phi5_native_xor.common import sha, sha_bytes, xcnf_bytes  # noqa: E402

OUTPUT = HERE / "protocol.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    parent_path = PARENT / "q1452_known_satisfiable_phi5/protocol.json"
    n83_parent_path = PARENT / "q1451_phi5_fixed_target/protocol.json"
    parent = json.loads(parent_path.read_text())
    n83_parent = json.loads(n83_parent_path.read_text())
    controls_path = HERE / "controls.json"
    controls = json.loads(controls_path.read_text())
    algebra_path = HERE / "algebra_validation.json"
    algebra = json.loads(algebra_path.read_text())
    assert parent["proposal_id"] == "Q1452"
    assert n83_parent["proposal_id"] == "Q1451"
    assert controls["proposal_id"] == "Q1453"
    assert controls["status"] == "pass"
    assert algebra["status"] == "pass"
    assert controls["parent_q1452_protocol_sha256"] == sha(parent_path)
    assert controls["n83_parent_q1451_protocol_sha256"] == sha(
        n83_parent_path)
    assert controls["algebra_validation_sha256"] == sha(algebra_path)
    assert all(row["verified_relation"]["status"] ==
               "verified_four_point_relation" for row in controls["rows"])
    binary = shutil.which("cryptominisat5")
    assert binary is not None
    binary_path = Path(binary).resolve()
    assert controls["cms_binary_sha256"] == sha(binary_path)
    cells = {}
    for n, target_index in ((53, 201), (83, 0)):
        formula, meta = build(n, target_index=target_index)
        raw = xcnf_bytes(formula)
        matched = (parent if n == 53 else n83_parent)["cells"][str(n)]
        for name in ("curve_id", "factor_base_actual_B",
                     "folded_columns_K",
                     "factor_base_enumerated_set_sha256", "public_target"):
            assert meta[name] == matched[name], name
        assert meta["target_preimage_index"] == target_index
        assert meta["target_preimage_x_count"] == 1
        assert meta["full_target_preimage_x_count"] == matched[
            "full_target_preimage_x_count"]
        if n == 53:
            assert meta["raw_target_x_values"] == [next(
                row["raw_target_x"] for row in controls["rows"]
                if row["degree_n"] == 53)]
        cells[str(n)] = {
            "curve_id": matched["curve_id"],
            "workload_id": matched["workload_id"],
            "factor_base_actual_B": matched["factor_base_actual_B"],
            "folded_columns_K": matched["folded_columns_K"],
            "factor_base_enumerated_set_sha256": matched[
                "factor_base_enumerated_set_sha256"],
            "public_target": matched["public_target"],
            "target_preimage_index": target_index,
            "selected_raw_target_x": meta["raw_target_x_values"][0],
            "target_preimage_x_count": 1,
            "full_target_preimage_x_count": matched[
                "full_target_preimage_x_count"],
            "selected_slice_known_satisfiable_by_archived_witness": (
                n == 53),
            "run_label": ("n53_known_satisfiable_ordinary" if n == 53
                          else "n83_ordinary"),
            "instance": matched["instance"],
            "xcnf_variables": formula.variables,
            "cnf_clauses": len(formula.clauses),
            "native_xor_rows": len(formula.xors),
            "and_gates": len(formula.and_cache),
            "max_native_xor_row_length": max(
                len(row) for row, _ in formula.xors),
            "initial_xcnf_sha256": sha_bytes(raw),
            "initial_xcnf_bytes": len(raw),
        }
    new_sources = (
        "build_formula.py", "validate_algebra.py", "validate_controls.py",
        "verify_model.py", "freeze_protocol.py", "run_stage.py",
        "verify_archive.py")
    source_sha256 = dict(parent["source_sha256"])
    for name in new_sources:
        path = HERE / name
        source_sha256[str(path.relative_to(ROOT))] = sha(path)
    input_sha256 = dict(parent["input_sha256"])
    for path in (parent_path, n83_parent_path, controls_path, algebra_path,
                 HERE / "sage_runtime_info.json"):
        input_sha256[str(path.relative_to(ROOT))] = sha(path)
    version = subprocess.run(
        [str(binary_path), "--version"], capture_output=True, text=True,
        check=True).stdout.strip()
    protocol = {
        "kind": "q1453_projective_phi5_ordinary_protocol",
        "proposal_id": "Q1453", "candidate_id": None,
        "isogeny": "none",
        "point_decomposition_stage_code": "PDP4phi5",
        "method": (
            "inverse-free denominator-cleared projective phi5 circuit "
            "in sparse x coordinates; fixed public-target preimage, "
            "CryptoMiniSat 5 bounded Gaussian settings and exact group "
            "replay with model blocking"),
        "controlled_variable": (
            "division-free phi5 representation versus Q1452 N53 and "
            "Q1451 N83 inverse-constrained representations on their "
            "respective matched ordinary public targets and preimages"),
        "cells": cells,
        "run_order": ["n53_known_satisfiable_ordinary", "n83_ordinary"],
        "solver_wall_cap_seconds": 60,
        "solver_conflict_cap": 1000000,
        "max_models": 32,
        "external_process_safeguard_seconds": 75,
        "max_matrix_columns": 8192,
        "max_matrix_rows": 512,
        "max_matrices": 8,
        "auto_disable_gauss": False,
        "cms_binary_path": str(binary_path),
        "cms_binary_sha256": sha(binary_path),
        "cms_version": version,
        "parent_q1452_protocol_sha256": sha(parent_path),
        "n83_parent_q1451_protocol_sha256": sha(n83_parent_path),
        "algebra_validation_sha256": sha(algebra_path),
        "controls_sha256": sha(controls_path),
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "source_sha256": source_sha256,
        "input_sha256": input_sha256,
        "cpu_isolation_receipt": None,
        "ordinary_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }
    if args.check:
        assert protocol == json.loads(OUTPUT.read_text())
        print("Q1453 frozen projective-phi5 protocol: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(protocol, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1453",
                          "degrees": [53, 83],
                          "xcnf_sha256": {n: cell["initial_xcnf_sha256"]
                                           for n, cell in cells.items()}}))


if __name__ == "__main__":
    main()
