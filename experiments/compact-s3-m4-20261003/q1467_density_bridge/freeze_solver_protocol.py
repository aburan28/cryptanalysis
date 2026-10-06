#!/usr/bin/env python3
"""Freeze Q1467 solver inputs, implementation, limits, and run order."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PARENT = HERE.parent
PROTOCOL = HERE / "solver_protocol.json"
ORDER = ("n53_planted", "n83_planted", "n53_planted_unpinned",
         "n83_planted_unpinned", "n53_ordinary", "n83_ordinary")
SOURCES = (
    "experiments/compact-s3-m4-20261003/q1467_density_bridge/"
    "build_inputs.py",
    "experiments/compact-s3-m4-20261003/q1467_density_bridge/"
    "run_stage.py",
    "experiments/compact-s3-m4-20261003/q1467_density_bridge/"
    "freeze_solver_protocol.py",
    "experiments/compact-s3-m4-20261003/q1467_density_bridge/"
    "select_n53_base.py",
    "experiments/compact-s3-m4-20261003/q1438_dense_base/"
    "verify_solver.py",
    "experiments/compact-s3-m4-20261003/q1438_dense_base/"
    "solver_protocol.json",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/"
    "n53_field.txt",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/"
    "n83_field.txt",
)
LEAVES = ("system.cnf.gz", "variables.txt", "targets.txt", "meta.json")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def describe() -> dict:
    base_protocol = json.loads((HERE / "protocol.json").read_text())
    assert base_protocol["proposal_id"] == "Q1467"
    assert base_protocol["candidate_id"] is None
    assert base_protocol["isogeny"] == "none"
    assert json.loads((HERE / "sage_runtime_info.json").read_text())[
        "status"] == "verified"
    compile_receipt = json.loads((PARENT /
        "q1466_leaf_rotation/compile_receipt.json").read_text())
    binary = PARENT / "q1466_leaf_rotation/native_solver"
    assert compile_receipt["solver_binary_sha256"] == sha(binary)
    cells = {}
    for name in ORDER:
        folder = HERE / "inputs" / name
        assert {path.name for path in folder.iterdir()} == set(LEAVES)
        meta = json.loads((folder / "meta.json").read_text())
        n = meta["degree_n"]
        profile = next(p for p in base_protocol["profiles"]
                       if p["degree_n"] == n)
        assert meta["curve_id"] == profile["curve_id"]
        assert meta["factor_base_actual_B"] == profile[
            "factor_base_actual_B"]
        assert meta["folded_columns_K"] == profile["folded_columns_K"]
        assert meta["candidate_id"] is None
        assert meta["isogeny"] == "none"
        assert meta["case"] == name
        if n == 83:
            assert meta["factor_base_enumerated_set_sha256"] == profile[
                "enumerated_set_sha256"]
        else:
            receipt = json.loads((HERE / "n53_w3_26_orbits.json").read_text())
            assert meta["factor_base_enumerated_set_sha256"] == receipt[
                "selected_projected_orbit_keys_digest_sha256"]
        raw = gzip.decompress((folder / "system.cnf.gz").read_bytes())
        header = next(line for line in raw.splitlines()
                      if line.startswith(b"p cnf "))
        _, _, variables, clauses = header.split()
        cells[name] = {
            key: meta[key] for key in (
                "curve_id", "degree_n", "factor_base_actual_B",
                "folded_columns_K", "factor_base_enumerated_set_sha256",
                "workload_id", "public_target", "input_role", "leaves_pinned",
                "normal_basis_weight_bound")}
        cells[name].update({
            "cnf_sha256": hashlib.sha256(raw).hexdigest(),
            "cnf_variables": int(variables),
            "cnf_clauses": int(clauses),
            "input_sha256": {leaf: sha(folder / leaf) for leaf in LEAVES},
            "target_preimage_x_count": meta["target_preimage_x_count"],
            "prior_ordinary_workload_receipt_sha256": (
                sha(PARENT / "q1466_leaf_rotation/runs" / name /
                    "receipt.json") if meta["input_role"] == "ordinary"
                else None),
        })
    assert cells["n53_planted"]["workload_id"] == cells[
        "n53_planted_unpinned"]["workload_id"]
    assert cells["n83_planted"]["workload_id"] == cells[
        "n83_planted_unpinned"]["workload_id"]
    return {
        "kind": "q1467_chained_s3_density_bridge_solver_protocol",
        "protocol_revision": 2,
        "supersedes_protocol_sha256": sha(HERE / "solver_protocol_v1.json"),
        "proposal_id": "Q1467", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "run_order": list(ORDER), "cells": cells,
        "decision_policy": "joint_tail_leaf_quarter_shift",
        "pair_candidate_cap": 250000,
        "conflict_cap": 1000000,
        "wall_cap_seconds": 60,
        "external_safeguard_seconds": 75,
        "claim_scope": (
            "stage correctness and censored or successful point-decomposition "
            "diagnostics on these exact targets; planted targets do not "
            "estimate natural yield; ordinary failures do not prove absence "
            "of a decomposition"),
        "natural_relation_yield_estimate": None,
        "cost_per_useful_row": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "cpu_isolation_receipt": None,
        "controlled_wall_speedup": None,
        "source_sha256": {relative: sha(ROOT / relative)
                          for relative in SOURCES},
        "base_protocol_sha256": sha(HERE / "protocol.json"),
        "n53_base_receipt_sha256": sha(HERE / "n53_w3_26_orbits.json"),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "compile_receipt_sha256": sha(PARENT /
            "q1466_leaf_rotation/compile_receipt.json"),
        "binary_sha256": sha(binary),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    current = describe()
    if args.check:
        assert current == json.loads(PROTOCOL.read_text())
        print("Q1467 solver protocol: PASS")
    else:
        assert not PROTOCOL.exists(), "refuse overwrite"
        PROTOCOL.write_text(json.dumps(current, sort_keys=True, indent=2) +
                            "\n")
        print(json.dumps({"proposal_id": "Q1467",
                          "run_order": current["run_order"],
                          "protocol_sha256": sha(PROTOCOL)}))


if __name__ == "__main__":
    main()
