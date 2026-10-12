#!/usr/bin/env python3
"""Freeze a longer, conflict-bounded search on Q1452's exact N53 XCNF."""

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

from q1451_phi5_fixed_target.build_formula import build  # noqa: E402
from q1449_phi5_native_xor.common import sha, sha_bytes, xcnf_bytes  # noqa: E402

OUTPUT = HERE / "protocol.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    parent_path = PARENT / "q1452_known_satisfiable_phi5/protocol.json"
    parent = json.loads(parent_path.read_text())
    controls_path = PARENT / "q1452_known_satisfiable_phi5/controls.json"
    controls = json.loads(controls_path.read_text())
    assert parent["proposal_id"] == "Q1452"
    assert controls["proposal_id"] == "Q1452"
    assert controls["status"] == "pass"
    assert parent["controls_sha256"] == sha(controls_path)
    assert controls["target_preimage_index"] == 201
    assert controls["witness_not_supplied_to_ordinary_solver"] is True
    assert controls["archived_pinned_verified_relation"]["status"] == (
        "verified_four_point_relation")
    binary = shutil.which("cryptominisat5")
    assert binary is not None
    binary_path = Path(binary).resolve()
    assert controls["cms_binary_sha256"] == sha(binary_path)
    cells = {}
    for n in (53,):
        formula, meta = build(n, target_index=201)
        raw = xcnf_bytes(formula)
        matched = parent["cells"][str(n)]
        for name in ("curve_id", "factor_base_actual_B",
                     "folded_columns_K",
                     "factor_base_enumerated_set_sha256", "public_target"):
            assert meta[name] == matched[name], name
        assert meta["target_preimage_index"] == 201
        assert meta["target_preimage_x_count"] == 1
        assert meta["full_target_preimage_x_count"] == matched[
            "full_target_preimage_x_count"]
        assert meta["raw_target_x_values"] == [controls[
            "selected_raw_target_x"]]
        assert formula.variables == matched["xcnf_variables"]
        assert len(formula.clauses) == matched["cnf_clauses"]
        assert len(formula.xors) == matched["native_xor_rows"]
        assert len(formula.and_cache) == matched["and_gates"]
        assert sha_bytes(raw) == matched["initial_xcnf_sha256"]
        assert len(raw) == matched["initial_xcnf_bytes"]
        cells[str(n)] = dict(matched)
    new_sources = (
        "freeze_protocol.py", "run_stage.py", "verify_archive.py")
    source_sha256 = dict(parent["source_sha256"])
    for name in new_sources:
        path = HERE / name
        source_sha256[str(path.relative_to(ROOT))] = sha(path)
    input_sha256 = dict(parent["input_sha256"])
    for path in (parent_path, HERE / "sage_runtime_info.json"):
        input_sha256[str(path.relative_to(ROOT))] = sha(path)
    version = subprocess.run(
        [str(binary_path), "--version"], capture_output=True, text=True,
        check=True).stdout.strip()
    protocol = {
        "kind": "q1454_phi5_conflict_cap_ordinary_protocol",
        "proposal_id": "Q1454", "candidate_id": None,
        "isogeny": "none",
        "point_decomposition_stage_code": "PDP4phi5",
        "method": (
            "Q1452 exact XCNF and model replay on the archived "
            "known-satisfiable N53 ordinary preimage 201; allow "
            "CryptoMiniSat to reach one million conflicts per attempt "
            "or a "
            "480-second wall cap and request final statistics"),
        "controlled_variable": (
            "extended wall allowance versus Q1452's 60-second cap; "
            "the exact XCNF, binary, target, factor base, and Gaussian "
            "settings are unchanged"),
        "cells": cells,
        "run_order": ["n53_known_satisfiable_ordinary"],
        "solver_wall_cap_seconds": 480,
        "solver_conflict_cap": 1000000,
        "max_models": 32,
        "external_process_safeguard_seconds": 485,
        "solver_final_stats_verbosity": 3,
        "max_matrix_columns": 8192,
        "max_matrix_rows": 512,
        "max_matrices": 8,
        "auto_disable_gauss": False,
        "cms_binary_path": str(binary_path),
        "cms_binary_sha256": sha(binary_path),
        "cms_version": version,
        "parent_q1452_protocol_sha256": sha(parent_path),
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
        print("Q1454 frozen N53 conflict-cap protocol: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(protocol, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1454",
                          "degrees": [53],
                          "xcnf_sha256": {n: cell["initial_xcnf_sha256"]
                                           for n, cell in cells.items()}}))


if __name__ == "__main__":
    main()
