#!/usr/bin/env python3
"""Freeze a longer unpinned, known-satisfiable N83 S3-chain control."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1467 = PARENT / "q1467_density_bridge"
Q1466 = PARENT / "q1466_leaf_rotation"
SOURCE_FILES = (
    "experiments/compact-s3-m4-20261003/q1470_n83_long_control/run.py",
    "experiments/compact-s3-m4-20261003/q1470_n83_long_control/freeze_protocol.py",
    "experiments/compact-s3-m4-20261003/q1467_density_bridge/build_inputs.py",
    "experiments/compact-s3-m4-20261003/q1438_dense_base/verify_solver.py",
    "experiments/compact-s3-m4-20261003/q1466_leaf_rotation/native_solver.cpp",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render() -> dict:
    parent_path = Q1467 / "solver_protocol.json"
    parent = json.loads(parent_path.read_text())
    cell = parent["cells"]["n83_planted_unpinned"]
    assert cell["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert cell["factor_base_actual_B"] == 1934066
    assert cell["folded_columns_K"] == 11651
    assert cell["leaves_pinned"] is False
    assert cell["input_role"] == "planted"
    assert parent["pair_candidate_cap"] == 250000
    return {
        "kind": "q1470_n83_extended_known_satisfiable_control_protocol",
        "proposal_id": "Q1470", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "curve_id": cell["curve_id"], "degree_n": 83,
        "factor_base_actual_B": cell["factor_base_actual_B"],
        "folded_columns_K": cell["folded_columns_K"],
        "factor_base_enumerated_set_sha256": cell[
            "factor_base_enumerated_set_sha256"],
        "workload_id": cell["workload_id"],
        "public_target": cell["public_target"],
        "input_role": "known_satisfiable_planted_unpinned_control",
        "known_satisfiable_source": "Q1467 fully pinned same public target",
        "input_sha256": cell["input_sha256"],
        "cnf_sha256": cell["cnf_sha256"],
        "cnf_variables": cell["cnf_variables"],
        "cnf_clauses": cell["cnf_clauses"],
        "pair_candidate_cap": parent["pair_candidate_cap"],
        "decision_policy": parent["decision_policy"],
        "conflict_cap": 10_000_000,
        "wall_cap_seconds": 600,
        "external_safeguard_seconds": 630,
        "q1467_protocol_sha256": sha(parent_path),
        "q1467_prior_receipt_sha256": sha(
            Q1467 / "runs/n83_planted_unpinned/receipt.json"),
        "q1467_pinned_receipt_sha256": sha(
            Q1467 / "runs/n83_planted/receipt.json"),
        "binary_sha256": sha(Q1466 / "native_solver"),
        "compile_receipt_sha256": sha(Q1466 / "compile_receipt.json"),
        "field_file_sha256": sha(PARENT / "q1420_root_theory/n83_field.txt"),
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "source_sha256": {name: sha(ROOT / name) for name in SOURCE_FILES},
        "measurement_scope": (
            "N83 known-satisfiable unpinned solver limit extension on "
            "exact Q1467 CNF; no ordinary relation-yield inference"),
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "cpu_isolation_receipt": None,
        "controlled_wall_speedup": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = HERE / "protocol.json"
    result = render()
    if args.check:
        assert result == json.loads(path.read_text())
    else:
        assert not path.exists(), "refuse overwrite"
        path.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "pass", "proposal_id": "Q1470",
                      "wall_cap_seconds": result["wall_cap_seconds"]}))


if __name__ == "__main__":
    main()
