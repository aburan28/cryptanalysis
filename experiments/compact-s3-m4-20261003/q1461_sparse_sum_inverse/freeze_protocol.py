#!/usr/bin/env python3
"""Freeze Q1461 exact fixed-midpoint sparse-sum pair-inversion study."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1446 = PARENT / "q1446_joint_pair_span"
Q1448 = PARENT / "q1448_torsion_phi5"
OUTPUT = HERE / "protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_protocol() -> dict:
    build = json.loads((HERE / "compile_receipt.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert build["proposal_id"] == "Q1461"
    assert runtime["status"] == "verified"
    sources = [HERE / name for name in (
        "build.py", "prepare_inputs.py", "freeze_protocol.py", "run.py",
        "probe.cpp", "sparse_sum.hpp")]
    sources += [PARENT / name for name in (
        "q1420_root_theory/root_field_cli.cpp",
        "q1420_root_theory/root_field.hpp",
        "q1422_leaf_lift_gate/lift_gate.hpp")]
    inputs = [HERE / name for name in (
        "compile_receipt.json", "sage_runtime_info.json",
        "n53_inputs.txt", "n83_inputs.txt")]
    inputs += [Q1446 / f"runs/n{n}_ordinary/receipt.json" for n in (53, 83)]
    inputs += [PARENT / "q1420_root_theory" / f"n{n}_field.txt"
               for n in (53, 83)]
    inputs += [Q1448 / "validation.json"]
    cells = {}
    for n in (53, 83):
        receipt = json.loads((Q1446 / f"runs/n{n}_ordinary/receipt.json").read_text())
        assert receipt["curve_id"].startswith(f"EC1N{n}Ckb1h")
        cells[f"n{n}_ordinary"] = {
            "curve_id": receipt["curve_id"],
            "degree_n": n,
            "normal_basis_weight_bound": 4 if n == 53 else 6,
            "factor_base_actual_B": receipt["factor_base_actual_B"],
            "folded_columns_K": receipt["folded_columns_K"],
            "factor_base_enumerated_set_sha256": receipt[
                "factor_base_enumerated_set_sha256"],
            "public_target": receipt["public_target"],
            "workload_id": receipt["matched_q1438_workload_id"],
            "input_role": "archived ordinary SAT partial states",
            "archived_state_count": 16,
        }
    return {
        "kind": "q1461_sparse_sum_inverse_protocol",
        "proposal_id": "Q1461", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "method": (
            "For fixed nonzero midpoint m and sparse leaves a,b, enumerate "
            "s=a+b under the partial weight bounds. Solve the affine-linear "
            "product equation p^2+mp=m^2s^2+1 by half-trace, then solve "
            "a^2+sa=p with binary elimination; verify both leaves lift "
            "and satisfy S3. Compare the exact ordered pair set with "
            "separate direct enumeration."),
        "scope": "fixed-midpoint pair kernel only; no full PDP or adaptive search claim",
        "midpoint_zero_policy": "skip; caller must use a separate exact fallback",
        "sum_candidate_cap": 100000,
        "direct_pair_cap": 1000000,
        "run_order": ["n53_planted", "n53_ordinary", "n83_planted",
                      "n83_ordinary"],
        "cells": cells,
        "positive_control_source": "Q1448 independently verified four-leaf witnesses",
        "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in sources},
        "input_sha256": {str(p.relative_to(ROOT)): sha(p) for p in inputs},
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
    protocol = make_protocol()
    if args.check:
        assert protocol == json.loads(OUTPUT.read_text())
        print("Q1461 fixed protocol: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(protocol, sort_keys=True, indent=2) + "\n")
        print("Q1461 protocol frozen")


if __name__ == "__main__":
    main()
