#!/usr/bin/env python3
"""Freeze exact Q1448 inputs, circuit hashes, and caps before ordinary runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))

from q1420_root_theory.build_formula import convert_to_cnf  # noqa: E402
from q1425_reverse_pair.relax_control import serialize_cnf  # noqa: E402
from q1448_torsion_phi5.build_formula import build  # noqa: E402

PROTOCOL = HERE / "protocol.json"
Q1438 = PARENT / "q1438_dense_base/solver_protocol.json"
SOURCE_PATHS = (
    "experiments/compact-s3-m4-20261003/q1448_torsion_phi5/build_formula.py",
    "experiments/compact-s3-m4-20261003/q1448_torsion_phi5/validate_controls.py",
    "experiments/compact-s3-m4-20261003/q1448_torsion_phi5/freeze_protocol.py",
    "experiments/compact-s3-m4-20261003/q1448_torsion_phi5/run_stage.py",
    "experiments/compact-s3-m4-20261003/q1448_torsion_phi5/verify_model.py",
    "experiments/compact-s3-m4-20261003/q1448_torsion_phi5/verify_archive.py",
    "experiments/compact-s3-m4-20261003/chain_s3.py",
    "experiments/compact-s3-m4-20261003/chain_s3_multitarget.py",
    "experiments/compact-s3-m4-20261003/q1419_partial_pin/run_cell.py",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/build_formula.py",
    "experiments/compact-s3-m4-20261003/q1425_reverse_pair/relax_control.py",
    "experiments/compact-s3-m4-20261003/enumerate_q1413_projected_x.py",
    "experiments/koblitz-pair-claw-20260929/orbit_key.py",
    "ecc2k130/codegen/field.py",
    "ecc2k130/codegen/curves.py",
)
INPUT_PATHS = (
    "AGENTS.md",
    "experiments/compact-s3-m4-20261003/q1448_torsion_phi5/protocol_v1_failed.json",
    "experiments/compact-s3-m4-20261003/q1448_torsion_phi5/failed_preflight.json",
    "experiments/compact-s3-m4-20261003/q1438_dense_base/solver_protocol.json",
    "experiments/compact-s3-m4-20261003/q1438_dense_base/n53_w4_base.json",
    "experiments/compact-s3-m4-20261003/q1438_dense_base/n83_w6_base.json",
    "experiments/compact-s3-m4-20261003/runs/n53_q1410_ordinary.json",
    "experiments/compact-s3-m4-20261003/runs/n83_q1408_ordinary.json",
    "experiments/compact-s3-m4-20261003/q1446_joint_pair_span/validation.json",
    "experiments/compact-s3-m4-20261003/q1448_torsion_phi5/validation.json",
    "experiments/compact-s3-m4-20261003/q1448_torsion_phi5/sage_runtime_info.json",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def produce() -> dict:
    parent = json.loads(Q1438.read_text())
    validation = json.loads((HERE / "validation.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert parent["proposal_id"] == "Q1438"
    assert validation["proposal_id"] == "Q1448"
    assert validation["status"] == "pass"
    assert validation["builder_source_sha256"] == sha(
        HERE / "build_formula.py")
    assert runtime["status"] == "verified"
    cadical = shutil.which("cadical")
    assert cadical is not None and Path(cadical).is_absolute()
    cells = {}
    for n in (53, 83):
        matched = parent["workloads"][f"n{n}_ordinary"]
        instance = parent["instances"][str(n)]
        workload = matched["workload_record"]
        assert hashlib.sha256(canonical_json(workload)).hexdigest()[
            :12] == matched["workload_id"]
        formula, meta = build(n)
        variables, clauses = convert_to_cnf(formula)
        raw = serialize_cnf(variables, clauses)
        assert meta["curve_id"] == matched["curve_id"]
        for a, b in (("factor_base_actual_B", "factor_base_actual_B"),
                     ("folded_columns_K", "folded_columns_K"),
                     ("factor_base_enumerated_set_sha256",
                      "factor_base_enumerated_set_sha256"),
                     ("public_target", "public_target"),
                     ("target_preimage_x_count", "target_preimage_x_count")):
            assert meta[a] == matched[b]
        cells[str(n)] = {
            "curve_id": matched["curve_id"],
            "instance": instance,
            "public_target": matched["public_target"],
            "factor_base_actual_B": matched["factor_base_actual_B"],
            "folded_columns_K": matched["folded_columns_K"],
            "factor_base_enumerated_set_sha256": matched[
                "factor_base_enumerated_set_sha256"],
            "factor_base_receipt_sha256": matched[
                "factor_base_receipt_sha256"],
            "target_preimage_x_count": matched[
                "target_preimage_x_count"],
            "target_source_receipt_sha256": workload[
                "source_parent_receipt_sha256"],
            "workload": workload,
            "workload_id": matched["workload_id"],
            "matched_q1438_workload_id": matched["workload_id"],
            "cnf_raw_sha256": hashlib.sha256(raw).hexdigest(),
            "cnf_raw_bytes": len(raw),
            "cnf_variables": variables,
            "cnf_clauses": len(clauses),
            "original_formula_variables": formula.variables,
            "original_formula_cnf_clauses": len(formula.clauses),
            "original_formula_xor_rows": len(formula.xors),
            "and_gates": len(formula.and_cache),
        }
    return {
        "kind": "q1448_torsion_symmetrized_phi5_sat_protocol",
        "proposal_id": "Q1448", "candidate_id": None,
        "isogeny": "none",
        "point_decomposition_stage_code": "PDP4phi5",
        "method": "published 2-torsion symmetrized five-input polynomial in phi=1/(x+1), compact invariant circuit, exact sparse-x inverse constraints, CaDiCaL",
        "source_paper": "https://www.iacr.org/archive/eurocrypt2014/84410158/84410158.pdf",
        "run_order": ["n53_ordinary", "n83_ordinary"],
        "cells": cells,
        "solver_conflict_cap": 1_000_000,
        "solver_wall_cap_seconds": 60,
        "external_process_safeguard_seconds": 75,
        "cadical_binary_path": cadical,
        "cadical_binary_sha256": sha(Path(cadical)),
        "cadical_version": validation["cadical_version"],
        "validation_sha256": sha(HERE / "validation.json"),
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "source_sha256": {path: sha(ROOT / path) for path in SOURCE_PATHS},
        "input_sha256": {path: sha(ROOT / path) for path in INPUT_PATHS},
        "cpu_isolation_receipt": None,
        "ordinary_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = produce()
    if args.check:
        assert json.loads(PROTOCOL.read_text()) == expected
        print("Q1448 frozen protocol: PASS")
    else:
        if PROTOCOL.exists():
            raise FileExistsError(f"refuse overwrite of {PROTOCOL}")
        PROTOCOL.write_text(json.dumps(expected, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1448",
                          "workloads": {n: c["workload_id"]
                                        for n, c in expected["cells"].items()},
                          "protocol_sha256": sha(PROTOCOL)}))


if __name__ == "__main__":
    main()
