#!/usr/bin/env python3
"""Freeze reverse-S3 partner-root stages on archived N53/N83 inputs."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from q1423_target_coupled.target_inputs import (  # noqa: E402
    encode_targets, target_list)
from q1425_reverse_pair.relax_control import relax_cnf  # noqa: E402

PARENT = HERE.parent / "q1420_root_theory"
MATCH = HERE.parent / "q1424_early_target"
TARGETS = HERE.parent / "q1423_target_coupled"
LIFT = HERE.parent / "q1422_leaf_lift_gate"
PROTOCOL = HERE / "protocol.json"
SOURCE_NAMES = ("build_binaries.py", "freeze_protocol.py", "relax_control.py",
                "run_stage.py", "theory_solver.cpp", "verify_archive.py")
DEPENDENCIES = {
    "q1420_root_field.hpp": PARENT / "root_field.hpp",
    "q1420_build_formula.py": PARENT / "build_formula.py",
    "q1420_verify_archive.py": PARENT / "verify_archive.py",
    "q1422_lift_gate.hpp": LIFT / "lift_gate.hpp",
    "q1423_target_inputs.py": TARGETS / "target_inputs.py",
}
POLICIES = ("reverse_target", "reverse_mid")


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
        for cell in ("free_partner", "ordinary"):
            parent_key = f"n{n}_{'full_lock' if cell == 'free_partner' else cell}"
            parent_workload = parent["workloads"][parent_key]
            parent_dir = PARENT / "runs" / parent_key
            parent_receipt_path = parent_dir / "receipt.json"
            parent_meta = json.loads((parent_dir / "meta.json").read_text())
            parent_receipt = json.loads(parent_receipt_path.read_text())
            raw_cnf = gzip.decompress((parent_dir / "system.cnf.gz").read_bytes())
            assert hashlib.sha256(raw_cnf).hexdigest() == parent_receipt[
                "cnf_raw_sha256"]
            removed = 0
            if cell == "free_partner":
                solver_cnf, removed = relax_cnf(
                    raw_cnf, (parent_dir / "variables.txt").read_bytes(), n)
            else:
                solver_cnf = raw_cnf
            target_bytes = encode_targets(
                n, target_list(n, "free_mids" if cell == "free_partner"
                               else cell, parent_workload))
            assert len(target_bytes.splitlines()) - 1 == parent_meta[
                "target_preimage_x_count"]
            target_hash = hashlib.sha256(target_bytes).hexdigest()
            for policy in POLICIES:
                matched_key = (f"n{n}_{'free_mids' if cell == 'free_partner' else cell}_"
                               f"{'target_first' if policy == 'reverse_target' else 'target_mid_first'}")
                matched_workload = matched["workloads"][matched_key]
                assert parent_workload["workload_id"] == matched_workload[
                    "workload_id"]
                matched_receipt_path = (MATCH / "runs" / matched_key /
                                        "receipt.json")
                matched_receipt = json.loads(matched_receipt_path.read_text())
                assert matched_receipt["stage_run_id"] == matched_workload[
                    "stage_run_id"]
                assert matched_receipt["solver_status"] in ("sat", "censored")
                assert target_hash == matched_workload["target_input_sha256"]
                config = dict(matched_workload["stage_config_hash_input"])
                pdp = dict(config["point_decomposition"])
                pdp["decision_policy"] = (
                    "external cb_decide: target selector, " +
                    ("both pair intermediates, leaf0, leaf2, leaf1, leaf3"
                     if policy == "reverse_mid" else
                     "leaf0, leaf1, both pair intermediates, leaf2, leaf3"))
                pdp["policy_variant"] = policy
                pdp["pinning_policy"] = (
                    "archived full-lock witness with leaf1 and leaf3 unit pins "
                    "removed; leaf0, leaf2, both intermediates and target "
                    "selector remain pinned" if cell == "free_partner" else
                    "none")
                pdp["reverse_partner_root_propagation"] = (
                    "for a fixed pair intermediate and one complete nonzero "
                    "leaf, exact symmetric S3 roots constrain the partner; "
                    "zero intermediate uses inverse; discard zero, weight "
                    "above bound or non-lifting roots under full guards")
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
                    "relax_control.py": sources["relax_control.py"],
                    "theory_solver.cpp": sources["theory_solver.cpp"],
                }
                pdp["solver_binary_sha256"] = compiler["binary_sha256"]
                config["point_decomposition"] = pdp
                full = digest(config)
                stage = (f"PS1N{n}Ckb1fb{parent_workload['factor_base_actual_B']}"
                         f"PDP4theoryh{full[:12]}")
                key = f"n{n}_{cell}_{policy}"
                workloads[key] = {
                    "parent_key": parent_key,
                    "parent_stage_run_id": parent_workload["stage_run_id"],
                    "parent_receipt_sha256": sha(parent_receipt_path),
                    "parent_meta_sha256": sha(parent_dir / "meta.json"),
                    "parent_cnf_archive_sha256": sha(
                        parent_dir / "system.cnf.gz"),
                    "parent_variable_map_sha256": sha(
                        parent_dir / "variables.txt"),
                    "matched_q1424_key": matched_key,
                    "matched_q1424_stage_run_id": matched_workload[
                        "stage_run_id"],
                    "matched_q1424_receipt_sha256": sha(matched_receipt_path),
                    "solver_cnf_raw_sha256": hashlib.sha256(solver_cnf).hexdigest(),
                    "solver_cnf_variables": parent_receipt["cnf_variables"],
                    "solver_cnf_clauses": parent_receipt["cnf_clauses"] - removed,
                    "removed_partner_pin_units": removed,
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
                    "input_law": (
                        "known-satisfiable archived witness control with "
                        "partner leaf pins removed" if cell == "free_partner"
                        else parent_receipt["input_law"]),
                    "workload_record": parent_workload["workload_record"],
                    "workload_id": parent_workload["workload_id"],
                    "stage_config_hash_input": config,
                    "stage_config_sha256_full": full,
                    "stage_config_id": stage,
                    "stage_run_id": (f"{stage}W{parent_workload['workload_id']}R1"),
                }
    return {
        "kind": "q1425_frozen_reverse_pair_root_protocol",
        "proposal_id": "Q1425", "candidate_id": None, "isogeny": "none",
        "question": (
            "Can exact reverse S3 partner roots reject or force sparse "
            "second leaves before the large pair enumeration seen in Q1424, "
            "and recover an ordinary N53/N83 relation under matched caps?"),
        "parent_q1420_protocol_sha256": sha(parent_protocol_path),
        "matched_q1424_protocol_sha256": sha(matched_protocol_path),
        "workloads": workloads,
        "run_order": [f"n{n}_{cell}_{policy}" for n in (53, 83)
                      for cell in ("free_partner", "ordinary")
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
            "Freed-partner known-witness controls test root-propagation "
            "correctness only. One ordinary point per degree and policy is "
            "a solver gate, not a natural relation-yield estimate. "
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
