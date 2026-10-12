#!/usr/bin/env python3
"""Freeze matched Q1449 native-XOR inputs and solver limits before queries."""

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

from q1448_torsion_phi5.build_formula import build  # noqa: E402
from q1449_phi5_native_xor.common import sha, sha_bytes, xcnf_bytes  # noqa: E402

OUTPUT = HERE / "protocol.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    parent_path = PARENT / "q1448_torsion_phi5/protocol.json"
    parent = json.loads(parent_path.read_text())
    controls_path = HERE / "controls.json"
    controls = json.loads(controls_path.read_text())
    assert parent["proposal_id"] == "Q1448"
    assert controls["proposal_id"] == "Q1449"
    assert controls["status"] == "pass"
    assert controls["parent_q1448_protocol_sha256"] == sha(parent_path)
    binary = shutil.which("cryptominisat5")
    assert binary is not None
    binary_path = Path(binary).resolve()
    assert controls["cms_binary_sha256"] == sha(binary_path)
    cells = {}
    for n in (53, 83):
        formula, meta = build(n)
        raw = xcnf_bytes(formula)
        matched = parent["cells"][str(n)]
        for name in ("curve_id", "factor_base_actual_B",
                     "folded_columns_K",
                     "factor_base_enumerated_set_sha256", "public_target",
                     "target_preimage_x_count"):
            assert meta[name] == matched[name], name
        cells[str(n)] = {
            "curve_id": matched["curve_id"],
            "workload_id": matched["workload_id"],
            "factor_base_actual_B": matched["factor_base_actual_B"],
            "folded_columns_K": matched["folded_columns_K"],
            "factor_base_enumerated_set_sha256": matched[
                "factor_base_enumerated_set_sha256"],
            "public_target": matched["public_target"],
            "target_preimage_x_count": matched["target_preimage_x_count"],
            "instance": matched["instance"],
            "xcnf_variables": formula.variables,
            "cnf_clauses": len(formula.clauses),
            "native_xor_rows": len(formula.xors),
            "max_native_xor_row_length": max(
                len(row) for row, _ in formula.xors),
            "initial_xcnf_sha256": sha_bytes(raw),
            "initial_xcnf_bytes": len(raw),
        }
    new_sources = (
        "common.py", "validate_controls.py", "freeze_protocol.py",
        "run_stage.py", "verify_archive.py")
    source_sha256 = dict(parent["source_sha256"])
    for name in new_sources:
        path = HERE / name
        source_sha256[str(path.relative_to(ROOT))] = sha(path)
    input_sha256 = dict(parent["input_sha256"])
    for path in (parent_path, controls_path, HERE / "sage_runtime_info.json"):
        input_sha256[str(path.relative_to(ROOT))] = sha(path)
    version = subprocess.run(
        [str(binary_path), "--version"], capture_output=True, text=True,
        check=True).stdout.strip()
    protocol = {
        "kind": "q1449_phi5_native_xor_ordinary_protocol",
        "proposal_id": "Q1449", "candidate_id": None,
        "isogeny": "none",
        "point_decomposition_stage_code": "PDP4phi5",
        "method": (
            "Q1448 compact phi5 circuit with original GF(2) XOR rows in XCNF; "
            "CryptoMiniSat 5 single-thread solving; every algebraic model "
            "is group-replayed and an invalid ordered leaf-x/target tuple "
            "is blocked before continuing"),
        "controlled_variable": (
            "native XOR equations and CryptoMiniSat with invalid-model "
            "blocking versus Q1448 expanded CNF and CaDiCaL"),
        "cells": cells,
        "run_order": ["n53_ordinary", "n83_ordinary"],
        "solver_wall_cap_seconds": 60,
        "solver_conflict_cap": 1000000,
        "max_models": 32,
        "external_process_safeguard_seconds": 75,
        "cms_binary_path": str(binary_path),
        "cms_binary_sha256": sha(binary_path),
        "cms_version": version,
        "parent_q1448_protocol_sha256": sha(parent_path),
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
        print("Q1449 frozen native-XOR protocol: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(protocol, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1449",
                          "degrees": [53, 83],
                          "xcnf_sha256": {n: cell["initial_xcnf_sha256"]
                                           for n, cell in cells.items()}}))


if __name__ == "__main__":
    main()
