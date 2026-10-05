#!/usr/bin/env python3
"""Freeze Q1438 matched dense-base compact-S3 solver cells."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parents[1]
sys.path.insert(0, str(PARENT))
from q1423_target_coupled.target_inputs import (  # noqa: E402
    encode_targets, target_list)
from q1438_dense_base.build_formula import build_cnf  # noqa: E402

Q1420 = PARENT / "q1420_root_theory"
Q1436 = PARENT / "q1436_affine_pair"
PROTOCOL = HERE / "solver_protocol.json"
SOURCE_NAMES = ("build_formula.py", "validate_formula.py",
                "run_solver.py", "verify_solver.py",
                "freeze_solver_protocol.py")
DEPENDENCIES = (
    "experiments/compact-s3-m4-20261003/chain_s3.py",
    "experiments/compact-s3-m4-20261003/chain_s3_factored.py",
    "experiments/compact-s3-m4-20261003/chain_s3_multitarget.py",
    "experiments/compact-s3-m4-20261003/q1419_partial_pin/run_cell.py",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/build_formula.py",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/verify_archive.py",
    "experiments/compact-s3-m4-20261003/q1423_target_coupled/target_inputs.py",
    "experiments/compact-s3-m4-20261003/q1425_reverse_pair/relax_control.py",
    "experiments/compact-s3-m4-20261003/q1436_affine_pair/theory_solver.cpp",
    "experiments/compact-s3-m4-20261003/q1436_affine_pair/affine_pair.hpp",
    "experiments/compact-s3-m4-20261003/s3_root_oracle.py",
    "experiments/compact-s3-m4-20261003/enumerate_q1413_projected_x.py",
    "experiments/koblitz-pair-claw-20260929/orbit_key.py",
    "experiments/compact-s3-m4-20261003/run_probe.py",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(record):
    raw = json.dumps(record, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def make():
    base_protocol_path = HERE / "protocol.json"
    base_protocol = json.loads(base_protocol_path.read_text())
    base_verification_path = HERE / "verification.json"
    base_verification = json.loads(base_verification_path.read_text())
    assert base_verification["status"] == "passed"
    formula_validation_path = HERE / "formula_validation.json"
    formula_validation = json.loads(formula_validation_path.read_text())
    assert formula_validation["status"] == "passed"
    assert [(row["degree_n"], row["cell"])
            for row in formula_validation["rows"]] == [
                (n, cell) for n in (53, 83)
                for cell in ("free_partner", "ordinary")]
    matched_protocol_path = Q1436 / "protocol.json"
    matched = json.loads(matched_protocol_path.read_text())
    solver_binary = Q1436 / "theory_solver"
    assert sha(solver_binary) == matched["solver_binary_sha256"]
    runtime = HERE / "sage_runtime_info.json"
    assert json.loads(runtime.read_text())["status"] == "verified"
    sources = {name: sha(HERE / name) for name in SOURCE_NAMES}
    dependencies = {name: sha(ROOT / name) for name in DEPENDENCIES}
    workloads = {}
    for n in (53, 83):
        instance = base_protocol["instances"][str(n)]
        base_path = HERE / f"n{n}_w{instance['new_weight_bound']}_base.json"
        base = json.loads(base_path.read_text())
        assert base["protocol_sha256"] == sha(base_protocol_path)
        assert base["curve_id"] == instance["curve_id"]
        for cell in ("free_partner", "ordinary"):
            key = f"n{n}_{cell}"
            old = matched["workloads"][key]
            assert old["curve_id"] == instance["curve_id"]
            raw, varmap, _, meta, variables, clauses = build_cnf(n, cell)
            assert meta["factor_base_actual_B"] == base[
                "actual_usable_points_B_before_folding"]
            assert meta["folded_columns_K"] == base[
                "signed_frobenius_columns_K"]
            assert meta["factor_base_enumerated_set_sha256"] == base[
                "enumerated_set_sha256"]
            parent = json.loads((Q1420 / "protocol.json").read_text())[
                "workloads"][old["parent_q1420_key"]]
            targets = encode_targets(n, target_list(
                n, "free_mids" if cell == "free_partner" else "ordinary",
                parent))
            assert hashlib.sha256(targets).hexdigest() == old[
                "target_input_sha256"]
            assert meta["public_target"] == old["public_target"]
            config = copy.deepcopy(old["stage_config_hash_input"])
            fb = config["factor_base"]
            fb["normal_basis_weight_bound"] = instance["new_weight_bound"]
            fb["nominal_x_mask_count"] = base["nominal_x_mask_count"]
            fb["actual_usable_points_B_before_folding"] = base[
                "actual_usable_points_B_before_folding"]
            fb["signed_frobenius_columns"] = base[
                "signed_frobenius_columns_K"]
            fb["enumerated_set_sha256"] = base["enumerated_set_sha256"]
            fb["cofactor_projection"] = instance["cofactor"]
            pdp = config["point_decomposition"]
            pdp["source_sha256"]["q1438_build_formula.py"] = sources[
                "build_formula.py"]
            pdp["dense_base_receipt_sha256"] = sha(base_path)
            pdp["solver_binary_sha256"] = sha(solver_binary)
            config_hash = digest(config)
            stage = (f"PS1N{n}Ckb1fb{base['actual_usable_points_B_before_folding']}"
                     f"PDP4theoryh{config_hash[:12]}")
            old_receipt = Q1436 / "runs" / key / "receipt.json"
            workloads[key] = {
                "degree_n": n, "cell": cell,
                "curve_id": instance["curve_id"],
                "factor_base_actual_B": base[
                    "actual_usable_points_B_before_folding"],
                "folded_columns_K": base["signed_frobenius_columns_K"],
                "factor_base_enumerated_set_sha256": base[
                    "enumerated_set_sha256"],
                "factor_base_receipt_sha256": sha(base_path),
                "public_target": old["public_target"],
                "input_law": meta["input_law"],
                "target_preimage_x_count": meta[
                    "target_preimage_x_count"],
                "target_input_sha256": hashlib.sha256(targets).hexdigest(),
                "cnf_raw_sha256": hashlib.sha256(raw).hexdigest(),
                "cnf_raw_bytes": len(raw),
                "variable_map_sha256": hashlib.sha256(varmap).hexdigest(),
                "cnf_variables": variables, "cnf_clauses": clauses,
                "stage_config_hash_input": config,
                "stage_config_sha256_full": config_hash,
                "stage_config_id": stage,
                "workload_record": old["workload_record"],
                "workload_id": old["workload_id"],
                "stage_run_id": f"{stage}W{old['workload_id']}R1",
                "matched_q1436_stage_run_id": old["stage_run_id"],
                "matched_q1436_receipt_sha256": sha(old_receipt),
                "controlled_variable": (
                    "factor-base weight bound and resulting exact B/K/set; "
                    "same curve, public target, compact S3 solver binary, "
                    "decision policy, and resource caps"),
            }
    return {
        "kind": "q1438_frozen_dense_base_solver_protocol",
        "proposal_id": "Q1438", "candidate_id": None,
        "isogeny": "none", "instances": base_protocol["instances"],
        "workloads": workloads,
        "run_order": [f"n{n}_{cell}" for n in (53, 83)
                      for cell in ("free_partner", "ordinary")],
        "solver_conflict_cap": 1_000_000,
        "solver_wall_cap_seconds": 60,
        "external_process_safeguard_seconds": 75,
        "solver_binary_sha256": sha(solver_binary),
        "runtime_info_sha256": sha(runtime),
        "source_sha256": sources,
        "dependency_sha256": dependencies,
        "base_protocol_sha256": sha(base_protocol_path),
        "base_verification_sha256": sha(base_verification_path),
        "formula_validation_sha256": sha(formula_validation_path),
        "matched_q1436_protocol_sha256": sha(matched_protocol_path),
        "claim_boundary": (
            "Known-witness controls test correctness. Ordinary rows include "
            "failures and timeouts. Base size and matrix width change, so "
            "this is not a controlled solver-only speed ratio. CPU wall "
            "times on this host are exploratory. One relation is not a "
            "natural yield estimate; no complete N131 2^x follows without "
            "collection, final matrix, target descent, and replay."),
    }


def main():
    data = make()
    if PROTOCOL.exists():
        assert json.loads(PROTOCOL.read_text()) == data
        print("Q1438 solver protocol verified")
    else:
        PROTOCOL.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        print("Q1438 solver protocol frozen")


if __name__ == "__main__":
    main()
