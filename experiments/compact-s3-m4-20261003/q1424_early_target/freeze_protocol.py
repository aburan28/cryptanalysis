#!/usr/bin/env python3
"""Freeze two early-target decision orders on archived N53/N83 inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from q1423_target_coupled.target_inputs import (  # noqa: E402
    encode_targets, target_list)

PARENT = HERE.parent / "q1420_root_theory"
MATCH = HERE.parent / "q1423_target_coupled"
LIFT = HERE.parent / "q1422_leaf_lift_gate"
PROTOCOL = HERE / "protocol.json"
SOURCE_NAMES = ("build_binaries.py", "freeze_protocol.py", "run_stage.py",
                "theory_solver.cpp", "verify_archive.py")
DEPENDENCIES = {
    "q1420_root_field.hpp": PARENT / "root_field.hpp",
    "q1420_build_formula.py": PARENT / "build_formula.py",
    "q1420_verify_archive.py": PARENT / "verify_archive.py",
    "q1422_lift_gate.hpp": LIFT / "lift_gate.hpp",
    "q1423_target_inputs.py": MATCH / "target_inputs.py",
}
POLICIES = ("target_first", "target_mid_first")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build():
    parent_protocol_path = PARENT / "protocol.json"
    parent = json.loads(parent_protocol_path.read_text())
    matched_protocol_path = MATCH / "protocol.json"
    matched = json.loads(matched_protocol_path.read_text())
    compiler_path = HERE / "compile_receipt.json"
    compiler = json.loads(compiler_path.read_text())
    runtime_path = HERE / "sage_runtime_info.json"
    runtime = json.loads(runtime_path.read_text())
    assert runtime["status"] == "verified"
    assert compiler["source_sha256"] == sha(HERE / "theory_solver.cpp")
    assert compiler["binary_sha256"] == sha(HERE / "theory_solver")
    assert compiler["root_field_header_sha256"] == sha(
        DEPENDENCIES["q1420_root_field.hpp"])
    assert compiler["lift_gate_header_sha256"] == sha(
        DEPENDENCIES["q1422_lift_gate.hpp"])
    sources = {name: sha(HERE / name) for name in SOURCE_NAMES}
    dependencies = {name: sha(path) for name, path in DEPENDENCIES.items()}
    workloads = {}
    for n in (53, 83):
        for cell in ("free_mids", "ordinary"):
            parent_key = f"n{n}_{cell}"
            matched_key = f"{parent_key}_target"
            parent_workload = parent["workloads"][parent_key]
            matched_workload = matched["workloads"][matched_key]
            assert parent_workload["workload_id"] == matched_workload[
                "workload_id"]
            parent_dir = PARENT / "runs" / parent_key
            parent_receipt_path = parent_dir / "receipt.json"
            parent_meta = json.loads((parent_dir / "meta.json").read_text())
            matched_receipt_path = MATCH / "runs" / matched_key / "receipt.json"
            parent_receipt = json.loads(parent_receipt_path.read_text())
            matched_receipt = json.loads(matched_receipt_path.read_text())
            assert matched_receipt["stage_run_id"] == matched_workload[
                "stage_run_id"]
            assert matched_receipt["solver_status"] in ("sat", "censored")
            target_bytes = encode_targets(
                n, target_list(n, cell, parent_workload))
            assert len(target_bytes.splitlines()) - 1 == parent_meta[
                "target_preimage_x_count"]
            target_hash = hashlib.sha256(target_bytes).hexdigest()
            assert target_hash == matched_workload["target_input_sha256"]
            for policy in POLICIES:
                config = dict(matched_workload["stage_config_hash_input"])
                pdp = dict(config["point_decomposition"])
                pdp["decision_policy"] = (
                    "external cb_decide: target selector, " +
                    ("first pair intermediate, first leaf pair, second leaf pair"
                     if policy == "target_mid_first" else
                     "first leaf pair, first pair intermediate, second leaf pair"))
                pdp["policy_variant"] = policy
                # Target values belong to the workload, not the method hash.
                pdp.pop("target_input_sha256", None)
                pdp["source_sha256"] = {
                    "q1420_build_formula.py": dependencies[
                        "q1420_build_formula.py"],
                    "q1420_root_field.hpp": dependencies[
                        "q1420_root_field.hpp"],
                    "q1422_lift_gate.hpp": dependencies[
                        "q1422_lift_gate.hpp"],
                    "q1423_target_inputs.py": dependencies[
                        "q1423_target_inputs.py"],
                    "theory_solver.cpp": sources["theory_solver.cpp"],
                }
                pdp["solver_binary_sha256"] = compiler["binary_sha256"]
                config["point_decomposition"] = pdp
                full = digest(config)
                stage = (f"PS1N{n}Ckb1fb{parent_workload['factor_base_actual_B']}"
                         f"PDP4theoryh{full[:12]}")
                key = f"{parent_key}_{policy}"
                workloads[key] = {
                    "parent_key": parent_key,
                    "parent_stage_run_id": parent_workload["stage_run_id"],
                    "parent_receipt_sha256": sha(parent_receipt_path),
                    "parent_meta_sha256": sha(parent_dir / "meta.json"),
                    "parent_cnf_archive_sha256": sha(
                        parent_dir / "system.cnf.gz"),
                    "parent_variable_map_sha256": sha(
                        parent_dir / "variables.txt"),
                    "matched_q1423_key": matched_key,
                    "matched_q1423_stage_run_id": matched_workload[
                        "stage_run_id"],
                    "matched_q1423_receipt_sha256": sha(matched_receipt_path),
                    "target_input_sha256": target_hash,
                    "target_preimage_x_count": parent_meta[
                        "target_preimage_x_count"],
                    "curve_id": parent_workload["curve_id"],
                    "factor_base_actual_B": parent_workload[
                        "factor_base_actual_B"],
                    "folded_columns_K": parent_workload["folded_columns_K"],
                    "factor_base_enumerated_set_sha256": parent_workload[
                        "factor_base_enumerated_set_sha256"],
                    "public_target": parent_workload["public_target"],
                    "decision_policy": policy,
                    "input_law": parent_receipt["input_law"],
                    "workload_record": parent_workload["workload_record"],
                    "workload_id": parent_workload["workload_id"],
                    "stage_config_hash_input": config,
                    "stage_config_sha256_full": full,
                    "stage_config_id": stage,
                    "stage_run_id": (f"{stage}W{parent_workload['workload_id']}R1"),
                }
    return {
        "kind": "q1424_frozen_early_target_root_protocol",
        "proposal_id": "Q1424", "candidate_id": None, "isogeny": "none",
        "question": (
            "Does placing the target selector or target plus first pair "
            "intermediate before leaf decisions activate exact final S3 "
            "roots early enough to recover ordinary N53/N83 relations?"),
        "parent_q1420_protocol_sha256": sha(parent_protocol_path),
        "matched_q1423_protocol_sha256": sha(matched_protocol_path),
        "workloads": workloads,
        "run_order": [f"n{n}_{cell}_{policy}" for n in (53, 83)
                      for cell in ("free_mids", "ordinary")
                      for policy in POLICIES],
        "solver_conflict_cap": 1_000_000,
        "solver_wall_cap_seconds": 60,
        "external_process_safeguard_seconds": 75,
        "solver_binary_sha256": compiler["binary_sha256"],
        "compile_receipt_sha256": sha(compiler_path),
        "sage_runtime_info_sha256": sha(runtime_path),
        "source_sha256": sources,
        "dependency_sha256": dependencies,
        "claim_boundary": (
            "Known-witness controls test correctness only. One ordinary "
            "point per degree is a solver gate, not natural relation yield. "
            "CPU wall time is exploratory on an unisolated host. Formula "
            "build, complete collection, useful rank, final matrix, descent, "
            "and replay are not supplied by this stage."),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = json.dumps(build(), sort_keys=True, indent=2) + "\n"
    if args.check:
        assert PROTOCOL.read_text() == raw
    else:
        assert not PROTOCOL.exists()
        PROTOCOL.write_text(raw)
    print(PROTOCOL)


if __name__ == "__main__":
    main()
